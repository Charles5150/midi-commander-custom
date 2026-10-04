"""The command types a button sends, packed and read back."""

import os
import re
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# roundtrip_support also puts python/ on the path, for lib
from roundtrip_support import DEMO_CSV, HERE, firmware_source, norm  # noqa: E402
import lib.binaryUnpacker as unpacker  # noqa: E402
import lib.cmdBinaryPacker as cbp  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
import lib.configPacker as packer  # noqa: E402
import lib.flashLayout as layout  # noqa: E402


class PanicTest(unittest.TestCase):
    """Panic command: no parameters, code 0x80."""

    def test_packs_and_unpacks(self):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row["A_CommandType"] = "Panic"
        row["A_KeyMode_(Key)"] = ""
        packed = bytes(cbp.pack_row(pd.Series(row)))[:4]
        self.assertEqual(list(packed), [0x80, 0, 0, 0])
        self.assertEqual(unpacker.unpack_command(packed)["CommandType"], "Panic")

    def test_demo_has_panic_on_long_stop(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        long_frame = unpacker.unpack_config(packed)[3]
        row = long_frame[(long_frame["Bank_Number"].astype(str) == "6")
                         & (long_frame["Button_Identifier"].astype(str) == "4")].iloc[0]
        self.assertEqual(row["A_CommandType"], "Panic")

class PcIncTest(unittest.TestCase):
    """Relative Program Change: next and previous preset."""

    @staticmethod
    def pack(direction="Up", step="1", last="", wrap="N", ch="1"):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row.update({
            "A_CommandType": "PCInc", "A_Channel_(PC/CC/Note/PB)": ch,
            "A_KeyMode_(Key)": direction, "A_OffValue_(CC)": step,
            "A_Number_(PC/CC/Note)": last, "A_Toggle_(CC/PB/Note)": wrap,
        })
        return bytes(cbp.pack_row(pd.Series(row)))[:4]

    def test_encoding(self):
        self.assertEqual(list(self.pack()), [0xC0, 1, 0x81, 127])
        self.assertEqual(list(self.pack("Down", "5", "125", "Y", "16")), [0xCF, 5, 0x82, 0x80 | 125])

    def test_defaults_and_clamps(self):
        self.assertEqual(list(self.pack(step="", last="")), [0xC0, 1, 0x81, 127])
        self.assertEqual(list(self.pack(step="999", last="999")), [0xC0, 127, 0x81, 127])
        self.assertEqual(list(self.pack(last="0")), [0xC0, 1, 0x81, 0])

    def test_round_trip(self):
        for args in (("Up", "1", "127", "N", "1"), ("Down", "4", "125", "Y", "10")):
            d = unpacker.unpack_command(self.pack(*args))
            self.assertEqual(d["CommandType"], "PCInc")
            self.assertEqual(
                (d["KeyMode_(Key)"], d["OffValue_(CC)"], d["Number_(PC/CC/Note)"],
                 d["Toggle_(CC/PB/Note)"], d["Channel_(PC/CC/Note/PB)"]), args)

    def test_not_a_toggle(self):
        """Byte 1 is the step and stays below 0x80: the button is no toggle."""
        self.assertEqual(self.pack(step="127")[1] & 0x80, 0)

    def test_plain_pc_unchanged(self):
        """An ordinary Program Change never carries the markers."""
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row.update({"A_CommandType": "PC", "A_Channel_(PC/CC/Note/PB)": "1",
                    "A_Number_(PC/CC/Note)": "5", "A_BankSelect_(PC)": "",
                    "A_BankSelectHighByte_(PC)": "N"})
        packed = bytes(cbp.pack_row(pd.Series(row)))[:4]
        self.assertNotIn(packed[2], cbp.PC_REL_MARKERS)
        self.assertEqual(unpacker.unpack_command(packed)["CommandType"], "PC")

    def test_demo_prev_next(self):
        buttons = unpacker.unpack_config(packer.pack_config(read_config_csv(DEMO_CSV)))[2]
        def btn(b):
            r = buttons[(buttons["Bank_Number"].astype(str) == "3")
                        & (buttons["Button_Identifier"].astype(str) == b)].iloc[0]
            return r["Label"], r["A_CommandType"], r["A_KeyMode_(Key)"]
        self.assertEqual(btn("C"), ("PREV", "PCInc", "Down"))
        self.assertEqual(btn("D"), ("NEXT", "PCInc", "Up"))

class WaitTest(unittest.TestCase):
    """Wait command: a pause before the rest of the button's commands."""

    @staticmethod
    def pack(ms, mode="", beats=""):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row["A_CommandType"] = "Wait"
        row["A_Duration_(Note/PB)"] = ms
        row["A_KeyMode_(Key)"] = mode
        row["A_Number_(PC/CC/Note)"] = beats
        return bytes(cbp.pack_row(pd.Series(row)))[:4]

    def test_beat_and_bar_encoding(self):
        """Byte 3 holds the beats of the grid, byte 2 stays 0 so older firmware
        sends at once; the time is not looked at."""
        self.assertEqual(list(self.pack("500", "Beat")), [0x01, 0, 0, 1])
        self.assertEqual(list(self.pack("", "bar")), [0x01, 0, 0, 4])
        self.assertEqual(list(self.pack("", "Bar", "3")), [0x01, 0, 0, 3])
        self.assertEqual(list(self.pack("", "Bar", "32")), [0x01, 0, 0, 32])
        self.assertEqual(list(self.pack("200", "Time")), [0x01, 0, 20, 0])

    def test_beat_and_bar_round_trip(self):
        for mode, beats in (("Beat", ""), ("Bar", "4"), ("Bar", "3"), ("Bar", "8")):
            decoded = unpacker.unpack_command(self.pack("", mode, beats))
            self.assertEqual((decoded["CommandType"], decoded["KeyMode_(Key)"],
                              decoded["Number_(PC/CC/Note)"], decoded["Duration_(Note/PB)"]),
                             ("Wait", mode, beats, ""))

    def test_count_encoding_and_round_trip(self):
        """A count-in is a Bar with byte 2 = 1: 0.85-0.87 wait for the bar."""
        self.assertEqual(list(self.pack("", "Count")), [0x01, 0, 1, 4])
        self.assertEqual(list(self.pack("", "count", "3")), [0x01, 0, 1, 3])
        for beats in ("4", "3", "1", "32"):
            decoded = unpacker.unpack_command(self.pack("", "Count", beats))
            self.assertEqual((decoded["CommandType"], decoded["KeyMode_(Key)"],
                              decoded["Number_(PC/CC/Note)"]), ("Wait", "Count", beats))

    def test_demo_record_after_a_count_in(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        longs = unpacker.unpack_config(packed)[3]
        row = longs[(longs["Bank_Number"].astype(str) == "6")
                    & (longs["Button_Identifier"].astype(str) == "2")].iloc[0]
        self.assertEqual((row["A_CommandType"], row["A_KeyMode_(Key)"], row["A_Number_(PC/CC/Note)"]),
                         ("Wait", "Count", "4"))
        self.assertEqual((row["B_CommandType"], row["B_Number_(PC/CC/Note)"]), ("CC", "21"))

    def test_bad_grid(self):
        for mode, beats in (("Bar", "0"), ("Bar", "33"), ("Count", "0"), ("Count", "33"),
                            ("Bars", ""), ("Beat 2", "")):
            with self.assertRaises(ValueError):
                self.pack("", mode, beats)

    def test_firmware_reads_the_grid_from_byte_3(self):
        with open(os.path.join(os.path.dirname(HERE), "..", "firmware", "Core", "Src", "switch_router.c")) as f:
            src = f.read()
        self.assertIn("if(pRom[3]) ms = tempo_grid_wait(pRom[3], &beat, &host, pRom[2] != 0);", src)

    def test_demo_record_on_the_next_bar(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        longs = unpacker.unpack_config(packed)[3]
        row = longs[(longs["Bank_Number"].astype(str) == "6")
                    & (longs["Button_Identifier"].astype(str) == "A")].iloc[0]
        self.assertEqual((row["A_CommandType"], row["A_KeyMode_(Key)"], row["A_Number_(PC/CC/Note)"]),
                         ("Wait", "Bar", "4"))
        self.assertEqual((row["B_CommandType"], row["B_Number_(PC/CC/Note)"]), ("CC", "21"))

    def test_encoding(self):
        """Byte 0 marks the pause, byte 2 holds it in steps of 10 ms."""
        self.assertEqual(list(self.pack("200")), [0x01, 0, 20, 0])
        self.assertEqual(list(self.pack("10")), [0x01, 0, 1, 0])
        self.assertEqual(list(self.pack("2550")), [0x01, 0, 255, 0])

    def test_rounded_and_clamped(self):
        self.assertEqual(list(self.pack("204")), [0x01, 0, 20, 0])
        self.assertEqual(list(self.pack("9999")), [0x01, 0, 255, 0])
        self.assertEqual(list(self.pack("")), [0x01, 0, 0, 0])

    def test_round_trip(self):
        for ms in ("10", "200", "1000", "2550"):
            decoded = unpacker.unpack_command(self.pack(ms))
            self.assertEqual(decoded["CommandType"], "Wait")
            self.assertEqual(decoded["Duration_(Note/PB)"], ms)

    def test_empty_command_is_still_empty(self):
        """Only the low nibble tells a pause from an unused command slot."""
        self.assertEqual(unpacker.unpack_command(bytes(4))["CommandType"], "")
        self.assertEqual(unpacker.unpack_command(b"\xff\xff\xff\xff")["CommandType"], "")

    def test_wait_cannot_look_like_a_toggle(self):
        """Byte 1 stays clear: its top bit is what marks a toggling command."""
        self.assertEqual(self.pack("2550")[1] & 0x80, 0)

    def test_demo_pause_between_pc_and_cc(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        buttons = unpacker.unpack_config(packed)[2]
        row = buttons[(buttons["Bank_Number"].astype(str) == "11")
                      & (buttons["Button_Identifier"].astype(str) == "B")].iloc[0]
        self.assertEqual(row["A_CommandType"], "PC")
        self.assertEqual((row["B_CommandType"], row["B_Duration_(Note/PB)"]), ("Wait", "200"))
        self.assertEqual(row["C_CommandType"], "CC")

class RampTest(unittest.TestCase):
    """Ramp command: the CC right below walks to its value over a time."""

    @staticmethod
    def pack(ms):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row["A_CommandType"] = "Ramp"
        row["A_Duration_(Note/PB)"] = ms
        row["A_KeyMode_(Key)"] = ""
        return bytes(cbp.pack_row(pd.Series(row)))[:4]

    def test_encoding(self):
        """Byte 0 marks the ramp, bytes 2 and 3 hold its time in steps of 10 ms."""
        self.assertEqual(list(self.pack("500")), [0x02, 0, 50, 0])
        self.assertEqual(list(self.pack("2000")), [0x02, 0, 200, 0])
        self.assertEqual(list(self.pack("60000")), [0x02, 0, 6000 & 0xFF, 6000 >> 8])

    def test_rounded_and_clamped(self):
        self.assertEqual(list(self.pack("504")), [0x02, 0, 50, 0])
        self.assertEqual(list(self.pack("9999999")), [0x02, 0, 0xFF, 0xFF])
        self.assertEqual(list(self.pack("")), [0x02, 0, 0, 0])

    def test_round_trip(self):
        for ms in ("10", "500", "2550", "2560", "60000", str(cbp.RAMP_MAX_MS)):
            decoded = unpacker.unpack_command(self.pack(ms))
            self.assertEqual(decoded["CommandType"], "Ramp")
            self.assertEqual(decoded["Duration_(Note/PB)"], ms)

    def test_ramp_cannot_look_like_a_toggle(self):
        """Byte 1 stays clear: its top bit is what marks a toggling command."""
        self.assertEqual(self.pack(str(cbp.RAMP_MAX_MS))[1] & 0x80, 0)

    def test_demo_ramps(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        buttons = unpacker.unpack_config(packed)[2]

        def row(b):
            return buttons[(buttons["Bank_Number"].astype(str) == "7")
                           & (buttons["Button_Identifier"].astype(str) == b)].iloc[0]
        swell, rise = row("C"), row("D")
        self.assertEqual((swell["A_CommandType"], swell["A_Duration_(Note/PB)"]), ("Ramp", "2000"))
        self.assertEqual((swell["B_CommandType"], swell["B_Number_(PC/CC/Note)"],
                          swell["B_Toggle_(CC/PB/Note)"]), ("CC", "12", "Y"))
        self.assertEqual((rise["A_CommandType"], rise["A_Duration_(Note/PB)"]), ("Ramp", "500"))
        self.assertEqual((rise["B_CommandType"], rise["B_Number_(PC/CC/Note)"],
                          rise["B_Toggle_(CC/PB/Note)"]), ("CC", "13", "N"))

class RepeatTest(unittest.TestCase):
    """Auto-repeat of CCInc and PCInc while the button is held."""

    @staticmethod
    def pack(cmd_type, mode, step="2", number="7", start="64", wrap="N"):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row.update({
            "A_CommandType": cmd_type, "A_Channel_(PC/CC/Note/PB)": "1",
            "A_Number_(PC/CC/Note)": number, "A_OnValue_(CC/PB)": start,
            "A_OffValue_(CC)": step, "A_KeyMode_(Key)": mode,
            "A_Toggle_(CC/PB/Note)": wrap,
        })
        return bytes(cbp.pack_row(pd.Series(row)))[:4]

    def test_ccinc_encoding(self):
        self.assertEqual(list(self.pack("CCInc", "Up Repeat")), [0x50, 7, 0x82, 64])
        self.assertEqual(list(self.pack("CCInc", "Down Repeat", step="127")), [0x50, 7, 0xFF, 0xC0])
        self.assertEqual(list(self.pack("CCInc", "Up")), [0x50, 7, 2, 64])

    def test_pcinc_encoding(self):
        self.assertEqual(list(self.pack("PCInc", "Up Repeat", number="127")), [0xC0, 2, 0x83, 127])
        self.assertEqual(list(self.pack("PCInc", "Down Repeat", number="127")), [0xC0, 2, 0x84, 127])

    def test_never_a_toggle(self):
        """Byte 1 bit 7 is the toggle bit: repeating must not set it."""
        for cmd_type in ("CCInc", "PCInc"):
            for mode in ("Up Repeat", "Down Repeat"):
                self.assertEqual(self.pack(cmd_type, mode, step="127")[1] & 0x80, 0)

    def test_round_trip(self):
        for cmd_type in ("CCInc", "PCInc"):
            for mode in ("Up", "Down", "Up Repeat", "Down Repeat"):
                d = unpacker.unpack_command(self.pack(cmd_type, mode, step="3"))
                self.assertEqual((d["CommandType"], d["KeyMode_(Key)"], d["OffValue_(CC)"]),
                                 (cmd_type, mode, "3"))

    def test_demo_volume(self):
        buttons = unpacker.unpack_config(packer.pack_config(read_config_csv(DEMO_CSV)))[2]
        def btn(b):
            r = buttons[(buttons["Bank_Number"].astype(str) == "7")
                        & (buttons["Button_Identifier"].astype(str) == b)].iloc[0]
            return r["Label"], r["A_CommandType"], r["A_KeyMode_(Key)"]
        self.assertEqual(btn("1"), ("VOL+", "CCInc", "Up Repeat"))
        self.assertEqual(btn("2"), ("VOL-", "CCInc", "Down Repeat"))

class TempoCommandTest(unittest.TestCase):
    """Tap commands that set the tempo or step it."""

    pack = staticmethod(RepeatTest.pack)

    def tap(self, mode, bpm="", step=""):
        return self.pack("Tap", mode, step=step, start=bpm, number="")

    def test_encoding(self):
        self.assertEqual(list(self.tap("Tap")), [0x70, 0, 0, 0])
        self.assertEqual(list(self.tap("Clock")), [0x71, 0, 0, 0])
        self.assertEqual(list(self.tap("Set", bpm="120")), [0x72, 0, 120, 0])
        self.assertEqual(list(self.tap("Set", bpm="300")), [0x72, 0, 300 & 0x7F, 2])
        self.assertEqual(list(self.tap("Up", step="5")), [0x73, 0, 5, 0])
        self.assertEqual(list(self.tap("Down Repeat", step="1")), [0x74, 0, 0x81, 0])

    def test_defaults_and_limits(self):
        self.assertEqual(list(self.tap("Set")), [0x72, 0, 120, 0])       # empty: 120
        self.assertEqual(list(self.tap("Set", bpm="10")), [0x72, 0, 30, 0])
        self.assertEqual(list(self.tap("Set", bpm="999")), [0x72, 0, 300 & 0x7F, 2])
        self.assertEqual(list(self.tap("Up")), [0x73, 0, 1, 0])          # empty: 1 BPM

    def test_never_a_toggle(self):
        for mode in ("Set", "Up Repeat", "Down Repeat"):
            self.assertEqual(self.tap(mode, bpm="300", step="127")[1] & 0x80, 0)

    def test_round_trip(self):
        d = unpacker.unpack_command(self.tap("Set", bpm="174"))
        self.assertEqual((d["CommandType"], d["KeyMode_(Key)"], d["OnValue_(CC/PB)"]),
                         ("Tap", "Set", "174"))
        for mode in ("Up", "Down", "Up Repeat", "Down Repeat"):
            d = unpacker.unpack_command(self.tap(mode, step="4"))
            self.assertEqual((d["CommandType"], d["KeyMode_(Key)"], d["OffValue_(CC)"]),
                             ("Tap", mode, "4"))
        for mode in ("Tap", "Clock"):
            self.assertEqual(unpacker.unpack_command(self.tap(mode))["KeyMode_(Key)"], mode)

    def test_demo_bank(self):
        sections = unpacker.unpack_config(packer.pack_config(read_config_csv(DEMO_CSV)))
        buttons, long_frame = sections[2], sections[3]
        def row(frame, b):
            return frame[(frame["Bank_Number"].astype(str) == "6")
                         & (frame["Button_Identifier"].astype(str) == b)].iloc[0]
        self.assertEqual((row(buttons, "C")["Label"], row(buttons, "C")["A_KeyMode_(Key)"]),
                         ("BPM+", "Up Repeat"))
        self.assertEqual((row(buttons, "D")["Label"], row(buttons, "D")["A_KeyMode_(Key)"]),
                         ("BPM-", "Down Repeat"))
        hold = row(long_frame, "B")
        self.assertEqual((hold["A_CommandType"], hold["A_KeyMode_(Key)"], hold["A_OnValue_(CC/PB)"]),
                         ("Tap", "Set", "120"))

class CycleCommandTest(unittest.TestCase):
    """Cycle commands, which split a short press list into states."""

    @classmethod
    def setUpClass(cls):
        cls.sections = read_config_csv(DEMO_CSV)
        cls.packed = packer.pack_config(cls.sections)
        cls.buttons = unpacker.unpack_config(cls.packed)[2]

    def demo_d(self):
        b = self.buttons
        return b[(b["Bank_Number"].astype(str) == "11") & (b["Button_Identifier"] == "D")].iloc[0]

    def test_encoding_and_label_table(self):
        labels = []
        cycle = lambda text: cbp.cmd_cycle(pd.Series({"OnValue_(CC/PB)": text}), labels)
        self.assertEqual(cycle("CH B"), [0x03, 0, 0, 0])
        self.assertEqual(cycle("CH C"), [0x03, 1, 0, 0])
        self.assertEqual(cycle("CH B"), [0x03, 0, 0, 0])      # stored once
        self.assertEqual(cycle("TOOLONG"), [0x03, 2, 0, 0])   # cut to 4 chars
        self.assertEqual(labels, ["CH B", "CH C", "TOOL"])
        self.assertEqual(cycle(""), [0x03, cbp.CYCLE_NO_LABEL, 0, 0])
        table = cbp.pack_cycle_labels(labels)
        self.assertEqual(len(table), cbp.CYCLE_LABEL_COUNT * 4)
        self.assertEqual(table[:12], b"CH BCH CTOOL")
        self.assertEqual(set(table[12:]), {0xFF})

    def test_too_many_labels(self):
        labels = [f"L{i}" for i in range(cbp.CYCLE_LABEL_COUNT)]
        with self.assertRaises(ValueError):
            cbp.cmd_cycle(pd.Series({"OnValue_(CC/PB)": "NEW"}), labels)
        # A label already in the full table still packs
        self.assertEqual(cbp.cmd_cycle(pd.Series({"OnValue_(CC/PB)": "L3"}), labels)[1], 3)

    def test_only_in_short_press_lists(self):
        row = pd.Series({"A_CommandType": "Cycle", "A_OnValue_(CC/PB)": "X"})
        with self.assertRaises(ValueError):
            cbp.pack_row(row)
        self.assertEqual(cbp.pack_row(row, [])[:4], [0x03, 0, 0, 0])

    def test_demo_round_trip(self):
        row = self.demo_d()
        got = [(row[f"{s}_CommandType"], norm(row[f"{s}_OnValue_(CC/PB)"]),
                norm(row[f"{s}_Number_(PC/CC/Note)"])) for s in "ABCDEFG"]
        self.assertEqual(got, [("PC", "", "0"), ("Cycle", "CH B", ""), ("PC", "", "1"),
                               ("Cycle", "CH C", ""), ("PC", "", "2"),
                               ("Cycle", "CH D", ""), ("PC", "", "3")])
        self.assertEqual(row["Label"], "CH A")
        table = self.packed[layout.CYCLE_LABELS_OFFSET : layout.CONFIG_SIZE]
        self.assertEqual(table[:12], b"CH BCH CCH D")

    def test_older_dump_without_the_table(self):
        # Tools before 0.38 read and saved a dump ending before the table
        buttons = unpacker.unpack_config(self.packed[: layout.CYCLE_LABELS_OFFSET])[2]
        row = buttons[(buttons["Bank_Number"].astype(str) == "11") & (buttons["Button_Identifier"] == "D")].iloc[0]
        self.assertEqual((row["B_CommandType"], norm(row["B_OnValue_(CC/PB)"])), ("Cycle", ""))

class LeaveCommandTest(unittest.TestCase):
    """Leave commands, which split a bank's enter list into entering and leaving."""

    def test_encoding(self):
        row = pd.Series({"A_CommandType": "Wait", "A_Duration_(Note/PB)": "100",
                         "B_CommandType": "Leave"})
        self.assertEqual(cbp.pack_row(row, leave=True)[:8], [0x01, 0, 10, 0, 0x04, 0, 0, 0])

    def test_only_in_bank_enter_lists(self):
        row = pd.Series({"A_CommandType": "Leave"})
        with self.assertRaises(ValueError):
            cbp.pack_row(row)
        with self.assertRaises(ValueError):
            cbp.pack_row(row, [])

    def test_a_single_one(self):
        row = pd.Series({"A_CommandType": "Leave", "B_CommandType": "Leave"})
        with self.assertRaises(ValueError):
            cbp.pack_row(row, leave=True)

    def test_demo_round_trip(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        enter = unpacker.unpack_config(packed)[5]
        row = enter[enter["Bank_Number"].astype(str) == "11"].iloc[0]
        got = [(row[f"{s}_CommandType"], norm(row[f"{s}_Number_(PC/CC/Note)"]),
                norm(row[f"{s}_OnValue_(CC/PB)"])) for s in "ABC"]
        self.assertEqual(got, [("CC", "59", "127"), ("Leave", "", ""), ("CC", "59", "0")])
        at = layout.BANK_ENTER_OFFSET + 11 * layout.BUTTON_STRIDE + 4
        self.assertEqual(packed[at : at + 4], bytes([0x04, 0, 0, 0]))

    def test_firmware_mode_matches(self):
        import re
        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc",
                            "midi_defines.h")
        with open(path) as handle:
            header = handle.read()
        m = re.search(r"#define\s+CMD_LEAVE_MODE\s+\((\d+)\)", header)
        self.assertEqual(int(m.group(1)), cbp.CMD_LEAVE_MODE)

class LfoCommandTest(unittest.TestCase):
    """LFO commands, which turn the CC below into an LFO locked to the tempo."""

    def pack(self, **fields):
        row = pd.Series({"A_CommandType": "LFO", **{f"A_{k}": v for k, v in fields.items()}})
        return cbp.pack_row(row)[:4]

    def test_encoding(self):
        self.assertEqual(self.pack(), [0x06, 0, cbp.LFO_DIVISIONS.index("1/4"), 0])
        self.assertEqual(self.pack(**{"OnValue_(CC/PB)": "1/16T", "KeyMode_(Key)": "Random"}),
                         [0x06, 0, 0, 5])
        self.assertEqual(self.pack(**{"OnValue_(CC/PB)": "4/1", "KeyMode_(Key)": "sawdown"}),
                         [0x06, 0, 13, 3])

    def test_bad_values(self):
        for fields in ({"OnValue_(CC/PB)": "1/3"}, {"KeyMode_(Key)": "Wobble"}):
            with self.assertRaises(ValueError, msg=fields):
                self.pack(**fields)

    def test_round_trip(self):
        for div in range(len(cbp.LFO_DIVISIONS)):
            for shape in range(len(cbp.LFO_SHAPES)):
                raw = [0x06, 0, div, shape]
                cmd = unpacker.unpack_command(bytes(raw))
                row = pd.Series({f"A_{k}": v for k, v in cmd.items()})
                self.assertEqual(cbp.pack_row(row)[:4], raw, cmd)

    def test_divisions_are_note_lengths(self):
        # 24 clocks a quarter note; a dot adds half, a triplet takes a third off
        whole = {"1/1": 96, "1/2": 48, "1/4": 24, "1/8": 12, "1/16": 6, "2/1": 192, "4/1": 384}
        for name, ticks in zip(cbp.LFO_DIVISIONS, cbp.LFO_DIV_TICKS):
            base = whole[name.rstrip(".T")]
            want = base * 3 // 2 if name.endswith(".") else base * 2 // 3 if name.endswith("T") else base
            self.assertEqual(ticks, want, name)
        self.assertEqual(cbp.LFO_DIV_TICKS, sorted(cbp.LFO_DIV_TICKS))

    def test_demo(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        at = layout.COMMANDS_OFFSET + (6 * 8 + 4) * layout.BUTTON_STRIDE
        self.assertEqual(packed[at : at + 4], bytes([0x06, 0, cbp.LFO_DIVISIONS.index("1/8"), 0]))
        self.assertEqual(packed[at + 4 : at + 8], bytes([0xB0, 0x80 | 14, 127, 40]))

    def test_firmware_values_match(self):
        import re
        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc",
                            "midi_defines.h")
        with open(path) as handle:
            header = handle.read()
        m = re.search(r"#define\s+CMD_LFO_MODE\s+\((\d+)\)", header)
        self.assertEqual(int(m.group(1)), cbp.CMD_LFO_MODE)
        m = re.search(r"#define\s+LFO_DIV_TICKS\s+\{([^}]*)\}", header)
        self.assertEqual([int(v) for v in m.group(1).split(",")], cbp.LFO_DIV_TICKS)
        for i, name in enumerate(("SINE", "TRIANGLE", "SAW_UP", "SAW_DOWN", "SQUARE", "RANDOM")):
            m = re.search(rf"#define\s+LFO_SHAPE_{name}\s+\((\d+)\)", header)
            self.assertEqual(int(m.group(1)), i, name)
            self.assertEqual(cbp.LFO_SHAPES[i].upper().replace("SAW", "SAW_"), name)

class SceneTest(unittest.TestCase):
    """Scene command: which toggle buttons to set, and to what."""

    @staticmethod
    def pack(text):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row["A_CommandType"] = "Scene"
        row["A_OnValue_(CC/PB)"] = text
        row["A_KeyMode_(Key)"] = ""
        return bytes(cbp.pack_row(pd.Series(row)))[:4]

    def test_encoding(self):
        # 1 on, 2 off, 3 on, B off: mask bits 0,1,2,5, states bits 0,2
        self.assertEqual(list(self.pack("+-+..-..")), [0xA0, 0x27, 0x05, 0])
        self.assertEqual(list(self.pack("++++++++")), [0xA0, 0xFF, 0xFF, 0])
        self.assertEqual(list(self.pack("--------")), [0xA0, 0xFF, 0x00, 0])
        self.assertEqual(list(self.pack("")), [0xA0, 0, 0, 0])

    def test_round_trip(self):
        for text in ("+-+..-..", "++++++++", "--------", "........", "+......-"):
            decoded = unpacker.unpack_command(self.pack(text))
            self.assertEqual(decoded["CommandType"], "Scene")
            self.assertEqual(decoded["OnValue_(CC/PB)"], text, text)

    def test_short_or_odd_strings(self):
        """Missing characters and anything but + and - mean leave it."""
        self.assertEqual(unpacker.unpack_command(self.pack("+-"))["OnValue_(CC/PB)"], "+-......")
        self.assertEqual(unpacker.unpack_command(self.pack("+x?-"))["OnValue_(CC/PB)"], "+..-....")

    def test_demo_scenes(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        long_frame = unpacker.unpack_config(packed)[3]
        def scene(btn):
            r = long_frame[(long_frame["Bank_Number"].astype(str) == "2")
                           & (long_frame["Button_Identifier"].astype(str) == btn)].iloc[0]
            return r["A_CommandType"], r["A_OnValue_(CC/PB)"]
        self.assertEqual(scene("1"), ("Scene", "+++.++.."))
        self.assertEqual(scene("4"), ("Scene", "---.--.."))
        self.assertEqual(scene("A"), ("Scene", "+-+..-.."))

class SceneSaveTest(unittest.TestCase):
    """Storing the toggles into a scene from the pedal, Scene Save (0.93)."""

    def source(self, *name):
        return firmware_source(*name)

    def test_command(self):
        for mode, button, raw in (("Save", "1", [0xA1, 0, 0x00, 0]), ("save long", "A", [0xA1, 0, 0x14, 0]),
                                  ("Save Double", "D", [0xA1, 0, 0x27, 0])):
            cmd = {"KeyMode_(Key)": mode, "Number_(PC/CC/Note)": button, "OnValue_(CC/PB)": "+++"}
            self.assertEqual(cbp.cmd_scene(cmd), raw)
            back = unpacker.unpack_command(bytes(raw))
            self.assertEqual((back["CommandType"], back["KeyMode_(Key)"].upper(), back["Number_(PC/CC/Note)"]),
                             ("Scene", mode.upper(), button))
        # Recall, named or left empty, is the scene as before
        for mode in ("", "Recall", "nan"):
            self.assertEqual(cbp.cmd_scene({"KeyMode_(Key)": mode, "OnValue_(CC/PB)": "+-."}), [0xA0, 3, 1, 0])
        with self.assertRaises(ValueError):
            cbp.cmd_scene({"KeyMode_(Key)": "Store"})

    def test_demo(self):
        """Double press of A on bank 2 stores into the mix scene held A recalls."""
        packed = packer.pack_flash_image(read_config_csv(DEMO_CSV))
        double = unpacker.unpack_double_press_settings(packed)
        a = double[(double["Bank_Number"] == "2") & (double["Button_Identifier"] == "A")].iloc[0]
        self.assertEqual((a["A_CommandType"], a["A_KeyMode_(Key)"], a["A_Number_(PC/CC/Note)"]),
                         ("Scene", "Save Long", "A"))
        long_press = unpacker.unpack_long_press_settings(packed)
        a = long_press[(long_press["Bank_Number"] == "2") & (long_press["Button_Identifier"] == "A")].iloc[0]
        self.assertEqual(a["A_CommandType"], "Scene")

    def test_firmware(self):
        defines = self.source("Inc", "midi_defines.h")
        self.assertRegex(defines, r"#define SCENE_SAVE\s+\(1\)")
        self.assertEqual(cbp.SCENE_SAVE, 1)
        router = self.source("Src", "switch_router.c")
        self.assertIn("if(*pRom & SCENE_SAVE) save_scene(pRom[2]);", router)
        self.assertIn("if(flash_settings_patch(p + 2, &states, 1)) display_show_saved();", router)

class ConfigSlotCommandTest(unittest.TestCase):
    """Bank command modes that switch configuration slot."""

    @staticmethod
    def pack(mode, value=""):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row["A_CommandType"] = "Bank"
        row["A_KeyMode_(Key)"] = mode
        row["A_OnValue_(CC/PB)"] = value
        return bytes(cbp.pack_row(pd.Series(row)))[:4]

    def test_config_goto(self):
        for slot in (1, 2, 3, 4):
            packed = self.pack("Config", str(slot))
            self.assertEqual(list(packed), [0x43, slot - 1, 0, 0])
            back = unpacker.unpack_command(packed)
            self.assertEqual((back["KeyMode_(Key)"], back["OnValue_(CC/PB)"]), ("Config", str(slot)))

    def test_config_slot_clamped(self):
        self.assertEqual(list(self.pack("Config", "9")), [0x43, 3, 0, 0])
        self.assertEqual(list(self.pack("Config", "")), [0x43, 0, 0, 0])

    def test_next_config(self):
        packed = self.pack("NextConfig")
        self.assertEqual(list(packed), [0x44, 0, 0, 0])
        back = unpacker.unpack_command(packed)
        self.assertEqual((back["KeyMode_(Key)"], back["OnValue_(CC/PB)"]), ("NextConfig", ""))

    def test_existing_modes_unchanged(self):
        self.assertEqual(list(self.pack("GoTo", "12")), [0x40, 12, 0, 0])
        self.assertEqual(list(self.pack("Up", "3")), [0x41, 3, 0, 0])
        self.assertEqual(list(self.pack("Down", "8")), [0x42, 8, 0, 0])

    def test_demo_has_next_config_on_long_home(self):
        """On a long press of 1 in HOME, bank 0, which every bank leads back to."""
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        long_frame = unpacker.unpack_config(packed)[3]
        row = long_frame[(long_frame["Bank_Number"].astype(str) == "0")
                         & (long_frame["Button_Identifier"].astype(str) == "1")].iloc[0]
        self.assertEqual((row["A_CommandType"], row["A_KeyMode_(Key)"]), ("Bank", "NextConfig"))

class PageCommandTest(unittest.TestCase):
    """Bank command mode Page: a second page of a bank (firmware 0.47)."""

    pack = staticmethod(ConfigSlotCommandTest.pack)

    def test_mode_matches_firmware(self):
        import re

        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc", "midi_defines.h")
        with open(path) as handle:
            value = re.search(r"^#define\s+BANK_MODE_PAGE\s+\((\d+)\)", handle.read(), re.M).group(1)
        self.assertEqual(list(self.pack("Page", "31"))[0], 0x40 | int(value))

    def test_round_trip(self):
        for bank in (0, 12, 31):
            packed = self.pack("Page", str(bank))
            self.assertEqual(list(packed), [0x45, bank, 0, 0])
            back = unpacker.unpack_command(packed)
            self.assertEqual((back["KeyMode_(Key)"], back["OnValue_(CC/PB)"]), ("Page", str(bank)))

    def test_bank_clamped(self):
        self.assertEqual(list(self.pack("Page", "40")), [0x45, 31, 0, 0])
        self.assertEqual(list(self.pack("Page", "")), [0x45, 0, 0, 0])

    def test_demo_song_has_a_page(self):
        """D on song 1 (bank 12) shows bank 31, and D there goes back."""
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        frames = unpacker.unpack_config(packed)
        buttons = next(f for f in frames if "A_CommandType" in f.columns and "Label" in f.columns)

        def row(bank, btn):
            return buttons[(buttons["Bank_Number"].astype(str) == str(bank))
                           & (buttons["Button_Identifier"].astype(str) == btn)].iloc[0]

        there, back = row(12, "D"), row(31, "D")
        self.assertEqual((there["A_CommandType"], there["A_KeyMode_(Key)"], str(there["A_OnValue_(CC/PB)"])),
                         ("Bank", "Page", "31"))
        self.assertEqual((back["A_CommandType"], back["A_KeyMode_(Key)"], str(back["A_OnValue_(CC/PB)"])),
                         ("Bank", "Page", "12"))

class BackCommandTest(unittest.TestCase):
    """Bank command mode Back: return to the bank you came from (firmware 0.49)."""

    pack = staticmethod(ConfigSlotCommandTest.pack)

    def test_mode_matches_firmware(self):
        import re

        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc", "midi_defines.h")
        with open(path) as handle:
            text = handle.read()
        value = re.search(r"^#define\s+BANK_MODE_BACK\s+\((\d+)\)", text, re.M).group(1)
        self.assertEqual(list(self.pack("Back"))[0], 0x40 | int(value))
        # A mode of its own: no other Bank mode took that nibble
        others = re.findall(r"^#define\s+BANK_MODE_(\w+)\s+\((\d+)\)", text, re.M)
        taken = [int(v) for name, v in others if name != "BACK"]
        self.assertNotIn(int(value), taken)

    def test_round_trip(self):
        packed = self.pack("Back")
        self.assertEqual(list(packed), [0x46, 0, 0, 0])
        back = unpacker.unpack_command(packed)
        self.assertEqual((back["KeyMode_(Key)"], back["OnValue_(CC/PB)"]), ("Back", ""))

    def test_value_is_ignored(self):
        """Back takes no bank: whatever the cell says, the bytes are the same."""
        self.assertEqual(list(self.pack("Back", "17")), [0x46, 0, 0, 0])

    def test_existing_modes_unchanged(self):
        for mode, value, want in (("GoTo", "12", [0x40, 12, 0, 0]), ("Up", "3", [0x41, 3, 0, 0]),
                                  ("Down", "8", [0x42, 8, 0, 0]), ("Page", "31", [0x45, 31, 0, 0])):
            self.assertEqual(list(self.pack(mode, value)), want)

    def test_demo_has_one(self):
        """B in bank 10, the navigation bank, goes back to the bank you came from."""
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        frames = unpacker.unpack_config(packed)
        buttons = next(f for f in frames if "A_CommandType" in f.columns and "Label" in f.columns)
        row = buttons[(buttons["Bank_Number"].astype(str) == "10")
                      & (buttons["Button_Identifier"].astype(str) == "B")].iloc[0]
        self.assertEqual((row["Label"], row["A_CommandType"], row["A_KeyMode_(Key)"]),
                         ("PREV", "Bank", "Back"))
        self.assertEqual(norm(row["A_OnValue_(CC/PB)"]), "")

class BankDirectTest(unittest.TestCase):
    """Choosing any bank with two presses, Bank Direct (0.92)."""

    def source(self, *name):
        return firmware_source(*name)

    def test_command(self):
        self.assertEqual(cbp.cmd_bank({"KeyMode_(Key)": "Direct", "OnValue_(CC/PB)": "7"}), [0x48, 0, 0, 0])
        cmd = unpacker.unpack_command(bytes([0x48, 0, 0, 0]))
        self.assertEqual((cmd["CommandType"], cmd["KeyMode_(Key)"], cmd["OnValue_(CC/PB)"]),
                         ("Bank", "Direct", ""))
        from lib.configSchema import BANK_MODES
        self.assertIn("Direct", BANK_MODES)

    def test_demo(self):
        """Held, button 3 of HOME opens the chooser."""
        packed = packer.pack_flash_image(read_config_csv(DEMO_CSV))
        long_press = unpacker.unpack_long_press_settings(packed)
        three = long_press[(long_press["Bank_Number"] == "0") & (long_press["Button_Identifier"] == "3")].iloc[0]
        self.assertEqual((three["A_CommandType"], three["A_KeyMode_(Key)"]), ("Bank", "Direct"))

    def test_firmware(self):
        defines = self.source("Inc", "midi_defines.h")
        self.assertRegex(defines, r"#define BANK_MODE_DIRECT\s+\(8\)")
        router = self.source("Src", "switch_router.c")
        self.assertIn("case BANK_MODE_DIRECT:      direct_show(PREVIEW_DIRECT); break;", router)
        self.assertIn("target = (uint8_t)((group - 1) * DIRECT_GROUP + i);", router)

class MmcAndSongTest(unittest.TestCase):
    """MMC and Song commands: driving a recorder or a sequencer (firmware 0.50)."""

    @staticmethod
    def pack(cmd_type, mode, value=""):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row["A_CommandType"] = cmd_type
        row["A_KeyMode_(Key)"] = mode
        row["A_OnValue_(CC/PB)"] = value
        return bytes(cbp.pack_row(pd.Series(row)))[:4]

    def test_modes_match_firmware(self):
        """The low nibbles and the MMC command bytes are the firmware's."""
        import re

        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc", "midi_defines.h")
        with open(path) as handle:
            text = handle.read()
        modes = dict(re.findall(r"^#define\s+CMD_(\w+)_MODE\s+\((\d+)\)", text, re.M))
        self.assertEqual(int(modes["MMC"]), cbp.CMD_MMC_MODE)
        self.assertEqual(int(modes["SONG"]), cbp.CMD_SONG_MODE)
        # Each one a nibble of its own, and never 0, which means "no command"
        taken = [int(v) for v in modes.values()]
        self.assertEqual(len(taken), len(set(taken)))
        self.assertNotIn(0, taken)
        for name, value in (("STOP", 0x01), ("PLAY", 0x02), ("RECORD_STROBE", 0x06),
                            ("PAUSE", 0x09), ("LOCATE", 0x44)):
            fw = int(re.search(r"^#define\s+MMC_" + name + r"\s+\((0x[0-9A-Fa-f]+)\)", text, re.M).group(1), 16)
            self.assertEqual(fw, value)

    def test_mmc_round_trip(self):
        for mode, command in (("Play", 0x02), ("Stop", 0x01), ("Record", 0x06),
                              ("Pause", 0x09), ("Rewind", 0x05), ("FastForward", 0x04),
                              ("Reset", 0x0D)):
            packed = self.pack("MMC", mode)
            self.assertEqual(list(packed), [0x07, command, 0, 0])
            back = unpacker.unpack_command(packed)
            self.assertEqual((back["CommandType"], back["KeyMode_(Key)"]), ("MMC", mode))
            self.assertEqual(norm(back["OnValue_(CC/PB)"]), "")

    def test_mmc_locate_carries_seconds(self):
        packed = self.pack("MMC", "Locate", "3725")   # 1:02:05 into the song
        self.assertEqual(list(packed), [0x07, 0x44, 3725 & 0x7F, 3725 >> 7])
        back = unpacker.unpack_command(packed)
        self.assertEqual((back["KeyMode_(Key)"], back["OnValue_(CC/PB)"]), ("Locate", "3725"))
        # And the clamp at the top of the range the two bytes hold
        self.assertEqual(list(self.pack("MMC", "Locate", "99999")), [0x07, 0x44, 0x7F, 0x7F])

    def test_mmc_empty_action_plays(self):
        self.assertEqual(list(self.pack("MMC", "")), [0x07, 0x02, 0, 0])

    def test_mmc_unknown_action_refused(self):
        with self.assertRaises(ValueError):
            self.pack("MMC", "Fly")

    def test_song_round_trip(self):
        packed = self.pack("Song", "Select", "2")
        self.assertEqual(list(packed), [0x08, 0, 2, 0])
        back = unpacker.unpack_command(packed)
        self.assertEqual((back["CommandType"], back["KeyMode_(Key)"], back["OnValue_(CC/PB)"]),
                         ("Song", "Select", "2"))
        packed = self.pack("Song", "Position", "3000")
        self.assertEqual(list(packed), [0x08, 1, 3000 & 0x7F, 3000 >> 7])
        back = unpacker.unpack_command(packed)
        self.assertEqual((back["KeyMode_(Key)"], back["OnValue_(CC/PB)"]), ("Position", "3000"))

    def test_song_values_clamped(self):
        """A song number is one byte; a position spans both."""
        self.assertEqual(list(self.pack("Song", "Select", "300")), [0x08, 0, 127, 0])
        self.assertEqual(list(self.pack("Song", "Position", "99999")), [0x08, 1, 0x7F, 0x7F])

    def test_empty_command_still_empty(self):
        """The new modes live in the empty command type: all zeroes is still none."""
        back = unpacker.unpack_command(bytes([0, 0, 0, 0]))
        self.assertEqual(back["CommandType"], "")

    def test_demo_holds_them(self):
        """Held, the media buttons of bank 5 drive a recorder instead."""
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        frames = unpacker.unpack_config(packed)
        long_press = next(f for f in frames
                          if "A_CommandType" in f.columns and "Label" not in f.columns)
        got = {}
        for _, row in long_press[long_press["Bank_Number"].astype(str) == "5"].iterrows():
            if norm(row["A_CommandType"]):
                got[str(row["Button_Identifier"])] = (norm(row["A_CommandType"]),
                                                      norm(row["A_KeyMode_(Key)"]),
                                                      norm(row["A_OnValue_(CC/PB)"]))
        self.assertEqual(got["1"], ("MMC", "Play", ""))
        self.assertEqual(got["4"], ("MMC", "Stop", ""))
        self.assertEqual(got["D"], ("MMC", "Record", ""))
        self.assertEqual(got["A"], ("MMC", "Locate", "0"))
        self.assertEqual(got["B"], ("MMC", "Locate", "3725"))
        self.assertEqual(got["2"], ("Song", "Select", "2"))
        self.assertEqual(got["3"], ("Song", "Position", "0"))

class ChannelsTest(unittest.TestCase):
    """The global channel and the Chan command (firmware 0.51)."""

    @staticmethod
    def pack_chan(channels):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row["A_CommandType"] = "Chan"
        row["A_Channel_(PC/CC/Note/PB)"] = channels
        return bytes(cbp.pack_row(pd.Series(row)))[:4]

    @staticmethod
    def pack_global(value):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        g.loc[g["Label"] == "Global_Channel", "Value"] = value
        return packer.pack_config(sections)

    def test_mode_and_byte_match_firmware(self):
        """The Chan nibble, its two top channel bits and the global setting byte."""
        import re

        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc", "midi_defines.h")
        with open(path) as handle:
            text = handle.read()
        modes = dict(re.findall(r"^#define\s+CMD_(\w+)_MODE\s+\((\d+)\)", text, re.M))
        self.assertEqual(int(modes["CHAN"]), cbp.CMD_CHAN_MODE)
        taken = [int(v) for v in modes.values()]
        self.assertEqual(len(taken), len(set(taken)))   # still a nibble each
        self.assertNotIn(0, taken)
        for name, value in (("CHAN_15_BIT", cbp.CHAN_15_BIT), ("CHAN_16_BIT", cbp.CHAN_16_BIT)):
            fw = re.search(r"^#define\s+" + name + r"\s+\((0x[0-9A-Fa-f]+)\)", text, re.M)
            self.assertEqual(int(fw.group(1), 16), value)
        byte = re.search(r"^#define\s+GLOBAL_SETTINGS_GLOBAL_CHANNEL\s+\((\d+)\)", text, re.M)
        self.assertEqual(int(byte.group(1)), 41)

    def test_chan_round_trip(self):
        for text, mask in (("1", 0x0001), ("1 2 3", 0x0007), ("2,4,6", 0x002A),
                           ("16", 0x8000), ("15 16", 0xC000), ("1-16", 0xFFFF)):
            packed = self.pack_chan(text)
            byte1 = (cbp.CHAN_15_BIT if mask & (1 << 14) else 0) | (cbp.CHAN_16_BIT if mask & (1 << 15) else 0)
            self.assertEqual(list(packed), [0x09, byte1, mask & 0x7F, (mask >> 7) & 0x7F], text)
            back = unpacker.unpack_command(packed)
            self.assertEqual(back["CommandType"], "Chan")
            wanted = " ".join(str(c + 1) for c in range(16) if mask & (1 << c))
            self.assertEqual(back["Channel_(PC/CC/Note/PB)"], wanted, text)

    def test_chan_needs_channels(self):
        for text in ("", "0", "17", "1 99"):
            with self.assertRaises(ValueError, msg=text):
                self.pack_chan(text)

    @staticmethod
    def pack_output(channels, output):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row["A_CommandType"] = "Chan"
        row["A_Channel_(PC/CC/Note/PB)"] = channels
        row["A_KeyMode_(Key)"] = output
        return bytes(cbp.pack_row(pd.Series(row)))[:4]

    def test_output_bits_match_firmware(self):
        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc", "midi_defines.h")
        with open(path) as handle:
            text = handle.read()
        for name, value in (("CHAN_NO_USB", cbp.CHAN_NO_USB), ("CHAN_NO_DIN", cbp.CHAN_NO_DIN)):
            fw = re.search(r"^#define\s+" + name + r"\s+\((0x[0-9A-Fa-f]+)\)", text, re.M)
            self.assertEqual(int(fw.group(1), 16), value)
        # clear of the channel bits and of the toggle bit
        self.assertEqual((cbp.CHAN_NO_USB | cbp.CHAN_NO_DIN) & (cbp.CHAN_15_BIT | cbp.CHAN_16_BIT | 0x80), 0)

    def test_output_round_trip(self):
        for channels, output, packed in (
                ("", "DIN", [0x09, 0x04, 0, 0]),
                ("", "usb", [0x09, 0x08, 0, 0]),
                ("1 2", "DIN", [0x09, 0x04, 0x03, 0]),
                ("16", "USB", [0x09, 0x0A, 0, 0]),
                ("3", "Both", [0x09, 0x00, 0x04, 0]),
                ("3", "", [0x09, 0x00, 0x04, 0])):
            got = self.pack_output(channels, output)
            self.assertEqual(list(got), packed, (channels, output))
            back = unpacker.unpack_command(got)
            self.assertEqual(back["CommandType"], "Chan")
            self.assertEqual(norm(back.get("Channel_(PC/CC/Note/PB)", "")), channels)
            wanted = {"both": "", "": ""}.get(output.lower(), output.upper())
            self.assertEqual(norm(back.get("KeyMode_(Key)", "")), wanted)

    def test_output_alone_or_nothing(self):
        """An output alone is enough; neither channels nor output is not."""
        self.assertEqual(list(self.pack_output("", "DIN")), [0x09, 0x04, 0, 0])
        for channels, output in (("", "Both"), ("", ""), ("1", "MIDI"), ("1", "5")):
            with self.assertRaises(ValueError, msg=(channels, output)):
                self.pack_output(channels, output)

    def test_chan_is_not_an_empty_command(self):
        """It shares the empty command type, but zero is still no command."""
        self.assertEqual(unpacker.unpack_command(bytes([0, 0, 0, 0]))["CommandType"], "")
        self.assertEqual(unpacker.unpack_command(bytes([0x09, 0, 1, 0]))["CommandType"], "Chan")

    def test_global_channel_round_trip(self):
        for text, byte in (("Off", 0), ("1", 1), ("10", 10), ("16", 16)):
            packed = self.pack_global(text)
            self.assertEqual(packed[41], byte, text)
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual(back["Global_Channel"], text, text)

    def test_global_channel_defaults_to_off(self):
        """A configuration written before 0.51 has erased flash in that byte."""
        image = bytearray(self.pack_global("5"))
        image[41] = 0xFF
        back = unpacker.unpack_config(bytes(image))[0].set_index("Label")["Value"]
        self.assertEqual(back["Global_Channel"], "Off")
        sections = read_config_csv(DEMO_CSV)
        sections["Global_Settings"] = sections["Global_Settings"][
            sections["Global_Settings"]["Label"] != "Global_Channel"]
        self.assertEqual(packer.pack_config(sections)[41], 0)

    def test_demo_holds_one(self):
        """Held, button A of bank 11 mutes three devices with one CC."""
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        frames = unpacker.unpack_config(packed)
        long_press = next(f for f in frames
                          if "A_CommandType" in f.columns and "Label" not in f.columns)
        row = long_press[(long_press["Bank_Number"].astype(str) == "11")
                         & (long_press["Button_Identifier"].astype(str) == "A")].iloc[0]
        self.assertEqual((norm(row["A_CommandType"]), norm(row["A_Channel_(PC/CC/Note/PB)"])),
                         ("Chan", "1 2 3"))
        self.assertEqual((norm(row["B_CommandType"]), norm(row["B_Number_(PC/CC/Note)"])),
                         ("CC", "60"))

class ParamTest(unittest.TestCase):
    """NRPN and RPN above a CC, and Channel Pressure (#137)."""

    @staticmethod
    def pack(ctype, **cols):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row["A_CommandType"] = ctype
        names = {"mode": "KeyMode_(Key)", "number": "Number_(PC/CC/Note)", "channel": "Channel_(PC/CC/Note/PB)",
                 "on": "OnValue_(CC/PB)", "off": "OffValue_(CC)", "toggle": "Toggle_(CC/PB/Note)"}
        for k, v in cols.items():
            row["A_" + names[k]] = v
        return bytes(cbp.pack_row(pd.Series(row)))[:4]

    def test_nrpn_encoding(self):
        """Low nibble 15 of the empty type, the kind in bits 4-6 of byte 1 and
        the parameter in bytes 2 (low) and 3 (high)."""
        self.assertEqual(list(self.pack("NRPN", number="300")), [0x0F, 0x00, 300 & 0x7F, 300 >> 7])
        self.assertEqual(list(self.pack("NRPN", mode="RPN", number="0")), [0x0F, 0x10, 0, 0])
        self.assertEqual(list(self.pack("nrpn", mode="nrpn 14-bit", number="16383")), [0x0F, 0x20, 0x7F, 0x7F])
        self.assertEqual(list(self.pack("NRPN", mode="RPN 14-bit", number="5")), [0x0F, 0x30, 5, 0])

    def test_pressure_encoding(self):
        self.assertEqual(list(self.pack("Pressure", channel="3", on="90", off="0", toggle="Y")),
                         [0x0F, 0x80 | 0x40 | 2, 90, 0])
        # Empty On is 127, empty Off sends nothing, as with a CC
        self.assertEqual(list(self.pack("Pressure")), [0x0F, 0x40, 127, 0x80])

    def test_round_trip(self):
        for mode, number in (("NRPN", "0"), ("RPN", "2"), ("NRPN 14-bit", "8191"), ("RPN 14-bit", "16383")):
            d = unpacker.unpack_command(self.pack("NRPN", mode=mode, number=number))
            self.assertEqual((d["CommandType"], d["KeyMode_(Key)"], d["Number_(PC/CC/Note)"]),
                             ("NRPN", mode, number))
        d = unpacker.unpack_command(self.pack("Pressure", channel="16", on="100", off="", toggle="Y"))
        self.assertEqual((d["CommandType"], d["Channel_(PC/CC/Note/PB)"], d["OnValue_(CC/PB)"],
                          d["OffValue_(CC)"], d["Toggle_(CC/PB/Note)"]), ("Pressure", "16", "100", "", "Y"))

    def test_bad_values(self):
        for cols in ({"number": "16384"}, {"number": "-1"}, {"number": ""}, {"number": "1", "mode": "RPN 7"}):
            with self.assertRaises(ValueError):
                self.pack("NRPN", **cols)
        with self.assertRaises(ValueError):
            self.pack("Pressure", on="128")

    def test_firmware_agrees(self):
        with open(os.path.join(os.path.dirname(HERE), "..", "firmware", "Core", "Inc", "midi_defines.h")) as f:
            defines = f.read()
        for name, value in (("CMD_PARAM_MODE", cbp.CMD_PARAM_MODE), ("PARAM_RPN", cbp.PARAM_RPN),
                            ("PARAM_FINE", cbp.PARAM_FINE), ("PARAM_PRESSURE", cbp.PARAM_PRESSURE)):
            self.assertRegex(defines, rf"#define\s+{name}\s+\({value}\)")


if __name__ == "__main__":
    unittest.main()
