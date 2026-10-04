"""The Global_Settings rows: what each packs to, and how it reads back."""

import os
import re
import struct
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# roundtrip_support also puts python/ on the path, for lib
from roundtrip_support import DEMO_CSV, FIRMWARE, FakePedal, SAMPLE_CSV, firmware_source, pack_csv  # noqa: E402
import lib.binaryUnpacker as unpacker  # noqa: E402
import lib.cmdBinaryPacker as cbp  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
import lib.configPacker as packer  # noqa: E402
from lib.configPacker import pack_config  # noqa: E402
import lib.flashLayout as layout  # noqa: E402


class BankSwitchTest(unittest.TestCase):
    """The Bank Down/Up switches send commands of their own (upstream issue 39)."""

    def test_demo_commands_round_trip(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        table = unpacker.unpack_config(packed)[7]
        rows = {(r["Switch"], r["Press"]): r for _, r in table.iterrows()}
        self.assertEqual(len(rows), 4)
        expected = {("Down", "Short"): "81", ("Up", "Short"): "82",
                    ("Down", "Long"): "83", ("Up", "Long"): "84"}
        for key, number in expected.items():
            self.assertEqual(rows[key]["A_CommandType"], "CC", key)
            self.assertEqual(rows[key]["A_Number_(PC/CC/Note)"], number, key)
        # Long presses latch, short presses do not
        self.assertEqual(rows[("Down", "Short")]["A_Toggle_(CC/PB/Note)"], "N")
        self.assertEqual(rows[("Down", "Long")]["A_Toggle_(CC/PB/Note)"], "Y")
        # A second slot on the same list is kept
        self.assertEqual(rows[("Up", "Long")]["B_CommandType"], "PC")

    def test_section_is_optional(self):
        """A CSV written before the section existed still packs."""
        sections = read_config_csv(DEMO_CSV)
        del sections[packer.BANK_SWITCH_SECTION]
        packed = packer.pack_config(sections)
        self.assertEqual(len(packed), layout.CONFIG_SIZE)
        table = unpacker.unpack_config(packed)[7]
        for _, row in table.iterrows():
            self.assertEqual(row["A_CommandType"], "")

    def test_mode_round_trips(self):
        for text, expected in (("Bank", 0), ("Bank+MIDI", 1), ("MIDI only", 2)):
            sections = read_config_csv(DEMO_CSV)
            g = sections["Global_Settings"]
            g.loc[g["Label"] == "Bank_Switch_Mode", "Value"] = text
            packed = packer.pack_config(sections)
            self.assertEqual(packed[15], expected, text)
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual(back["Bank_Switch_Mode"], text, text)

class BankSelectTest(unittest.TestCase):
    """A Program Change must only send Bank Select when one is configured.

    The firmware sends a Bank Select byte whenever its byte is below 0x80, so
    writing 0 for an empty field made every Program Change send an unwanted
    Bank Select LSB of 0, which changes bank on some devices.
    """

    @staticmethod
    def encode(bank_select, high_byte="N", number="7"):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row["A_CommandType"] = "PC"
        row["A_Channel_(PC/CC/Note/PB)"] = "1"
        row["A_Number_(PC/CC/Note)"] = number
        row["A_BankSelect_(PC)"] = bank_select
        row["A_BankSelectHighByte_(PC)"] = high_byte
        row["A_KeyMode_(Key)"] = ""
        return bytes(cbp.pack_row(pd.Series(row)))[:4]

    @staticmethod
    def sends_msb(packed):
        return packed[2] < 0x80

    @staticmethod
    def sends_lsb(packed):
        return packed[3] < 0x80

    def test_empty_sends_no_bank_select(self):
        for empty in ("", "  ", float("nan"), None):
            packed = self.encode(empty)
            self.assertFalse(self.sends_msb(packed), repr(empty))
            self.assertFalse(self.sends_lsb(packed), repr(empty))
            self.assertEqual(packed[1], 7, repr(empty))

    def test_zero_still_sends_bank_select_zero(self):
        """An explicit 0 is a real Bank Select and must survive."""
        packed = self.encode("0")
        self.assertFalse(self.sends_msb(packed))
        self.assertTrue(self.sends_lsb(packed))
        self.assertEqual(packed[3], 0)

    def test_low_byte_only(self):
        packed = self.encode("5")
        self.assertFalse(self.sends_msb(packed))
        self.assertTrue(self.sends_lsb(packed))
        self.assertEqual(packed[3], 5)

    def test_high_byte(self):
        packed = self.encode("1000", high_byte="Y")
        self.assertTrue(self.sends_msb(packed))
        self.assertTrue(self.sends_lsb(packed))
        self.assertEqual((packed[2] << 7) | (packed[3] & 0x7F), 1000)

    def test_round_trip(self):
        cases = [("", "N", ""), ("0", "N", "0"), ("5", "N", "5"), ("1000", "Y", "1000")]
        for value, high, expected in cases:
            decoded = unpacker.unpack_command(self.encode(value, high))
            self.assertEqual(decoded["BankSelect_(PC)"], expected, value)
            if expected:
                self.assertEqual(decoded["BankSelectHighByte_(PC)"], high, value)

    def test_demo_has_both_kinds(self):
        """The demo must keep covering a Program Change with and without one."""
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        with_bs = without_bs = 0
        regions = [(layout.COMMANDS_OFFSET, 256), (layout.LONG_PRESS_OFFSET, 256),
                   (layout.BANK_ENTER_OFFSET, 32), (layout.BANK_SWITCH_OFFSET, 4)]
        for start, count in regions:
            for i in range(count):
                for j in range(10):
                    o = start + i * layout.BUTTON_STRIDE + j * layout.CMD_SIZE
                    if packed[o] & 0xF0 == 0xC0:
                        if packed[o + 2] < 0x80 or packed[o + 3] < 0x80:
                            with_bs += 1
                        else:
                            without_bs += 1
        self.assertGreater(without_bs, 0, "no plain Program Change in the demo")
        self.assertGreater(with_bs, 0, "no Program Change with Bank Select in the demo")

class SleepTest(unittest.TestCase):
    """Idle sleep timeout, the first setting in the widened global area."""

    def pack_with(self, value):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        g.loc[g["Label"] == "Sleep_After_Min", "Value"] = value
        return packer.pack_config(sections)

    def test_round_trip(self):
        for text, expected in (("0", 0), ("1", 1), ("10", 10), ("60", 60)):
            packed = self.pack_with(text)
            self.assertEqual(packed[32], expected, text)
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual(back["Sleep_After_Min"], text, text)

    def test_out_of_range_is_clamped(self):
        self.assertEqual(self.pack_with("250")[32], 60)
        self.assertEqual(self.pack_with("-5")[32], 0)

    def test_missing_setting_means_off(self):
        """A configuration written before 0.18 has no such row."""
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        sections["Global_Settings"] = g[g["Label"] != "Sleep_After_Min"]
        packed = packer.pack_config(sections)
        self.assertEqual(packed[32], 0)
        self.assertEqual(len(packed), layout.CONFIG_SIZE)

    def test_name_still_fits_before_it(self):
        """Widening the area must not disturb ConfigName at 16..31."""
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        self.assertEqual(packed[16:32].decode("ascii").strip(), "DEMO ALL")

class SetlistTest(unittest.TestCase):
    """Bank Up/Down order when Setlist_Mode is on."""

    def packed_setlist(self, sections):
        packed = packer.pack_config(sections)
        start = layout.SETLIST_OFFSET
        return packed, list(packed[start:start + layout.SETLIST_MAX])

    def test_demo_order_round_trips(self):
        packed, raw = self.packed_setlist(read_config_csv(DEMO_CSV))
        expected = [0, 12, 15, 13, 14, 18, 16, 17, 19, 20]
        self.assertEqual(raw[:len(expected)], expected)
        self.assertEqual(raw[len(expected):], [0xFF] * (32 - len(expected)))
        self.assertEqual(packed[33], 2)     # with Setlist_Display on
        back = unpacker.unpack_config(packed)
        self.assertEqual([int(b) for b in back[8]["Bank_Number"]], expected)
        self.assertEqual(back[0].set_index("Label")["Value"]["Setlist_Mode"], "Y")

    def test_missing_section_is_empty(self):
        sections = read_config_csv(DEMO_CSV)
        del sections[packer.SETLIST_SECTION]
        packed, raw = self.packed_setlist(sections)
        self.assertEqual(raw, [0xFF] * 32)
        self.assertEqual(len(unpacker.unpack_config(packed)[8]), 0)

    def test_order_follows_position_not_row_order(self):
        sections = read_config_csv(DEMO_CSV)
        sections[packer.SETLIST_SECTION] = pd.DataFrame(
            [{"Position": "3", "Bank_Number": "7"},
             {"Position": "1", "Bank_Number": "5"},
             {"Position": "2", "Bank_Number": "6"}])
        _, raw = self.packed_setlist(sections)
        self.assertEqual(raw[:4], [5, 6, 7, 0xFF])

    def test_invalid_banks_dropped_and_length_capped(self):
        sections = read_config_csv(DEMO_CSV)
        rows = [{"Position": str(i), "Bank_Number": str(i % 40)} for i in range(1, 60)]
        rows.append({"Position": "0", "Bank_Number": "nonsense"})
        sections[packer.SETLIST_SECTION] = pd.DataFrame(rows)
        _, raw = self.packed_setlist(sections)
        self.assertTrue(all(b < 32 for b in raw))
        self.assertEqual(len(raw), 32)

    def test_mode_off_byte(self):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        g.loc[g["Label"] == "Setlist_Mode", "Value"] = "N"
        self.assertEqual(packer.pack_config(sections)[33], 0)

    def pack_modes(self, mode, shown):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        g.loc[g["Label"] == "Setlist_Mode", "Value"] = mode
        if shown is None:
            sections["Global_Settings"] = g[g["Label"] != "Setlist_Display"]
        else:
            g.loc[g["Label"] == "Setlist_Display", "Value"] = shown
        return packer.pack_config(sections)

    def test_display_round_trips(self):
        for mode, shown, byte in (("Y", "Y", 2), ("Y", "N", 1), ("N", "N", 0)):
            packed = self.pack_modes(mode, shown)
            self.assertEqual(packed[33], byte, (mode, shown))
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual((back["Setlist_Mode"], back["Setlist_Display"]), (mode, shown))

    def test_display_needs_the_setlist(self):
        """Showing the place means nothing when Bank Up/Down do not follow it."""
        self.assertEqual(self.pack_modes("N", "Y")[33], 0)

    def test_display_missing_means_off(self):
        """A CSV from before 0.94 keeps the setlist as it was."""
        self.assertEqual(self.pack_modes("Y", None)[33], 1)

class SetlistCompatibilityTest(unittest.TestCase):
    """A configuration flashed by 0.18 tools must read as setlist off and empty.

    Flashing erases every configuration page and writes only what the tool
    packed, so the bytes past a 0.18 configuration are left at 0xFF, and byte
    33 was packed as 0.
    """

    def test_018_image_reads_setlist_off(self):
        image = bytearray(packer.pack_config(read_config_csv(DEMO_CSV)))
        old_size = layout.SETLIST_OFFSET          # 0.18 ended where the setlist starts
        image[33] = 0                               # 0.18 always packed zero here
        image[old_size:] = b"\xff" * (len(image) - old_size)
        frames = unpacker.unpack_config(bytes(image))
        self.assertEqual(frames[0].set_index("Label")["Value"]["Setlist_Mode"], "N")
        self.assertEqual(len(frames[8]), 0)

class ClockFollowTest(unittest.TestCase):
    """Global byte 34: adopt the tempo of MIDI clock arriving over USB."""

    def pack_with(self, value):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        g.loc[g["Label"] == "Clock_Follow", "Value"] = value
        return packer.pack_config(sections)

    def test_round_trip(self):
        for text, byte in (("Y", 1), ("N", 0)):
            packed = self.pack_with(text)
            self.assertEqual(packed[34], byte, text)
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual(back["Clock_Follow"], text)

    def test_missing_setting_means_off(self):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        sections["Global_Settings"] = g[g["Label"] != "Clock_Follow"]
        self.assertEqual(packer.pack_config(sections)[34], 0)

    def test_neighbours_untouched(self):
        """The new byte must not disturb the settings either side of it."""
        packed = self.pack_with("Y")
        self.assertEqual(packed[33], 2)     # Setlist_Mode and Setlist_Display in the demo
        self.assertEqual(packed[32], 15)    # Sleep_After_Min in the demo

class LedFeedbackTest(unittest.TestCase):
    """Global byte 35: incoming CC and notes set the toggle buttons that send them."""

    def pack_with(self, value):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        g.loc[g["Label"] == "LED_Feedback", "Value"] = value
        g.loc[g["Label"] == "Link_Toggles", "Value"] = "N"
        return packer.pack_config(sections)

    def test_round_trip(self):
        for text, byte in (("Y", 1), ("N", 0)):
            packed = self.pack_with(text)
            self.assertEqual(packed[35] & 0x0F, byte, text)
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual(back["LED_Feedback"], text)

    def test_missing_setting_means_off(self):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        sections["Global_Settings"] = g[g["Label"] != "LED_Feedback"]
        self.assertEqual(packer.pack_config(sections)[35] & 0x01, 0)

    def test_erased_byte_reads_off(self):
        """Configurations written before 0.25 may hold 0 or erased flash here."""
        image = bytearray(self.pack_with("N"))
        for old in (0x00, 0xFF):
            image[35] = old
            back = unpacker.unpack_config(bytes(image))[0].set_index("Label")["Value"]
            self.assertEqual(back["LED_Feedback"], "N")

    def test_neighbours_untouched(self):
        packed = self.pack_with("Y")
        self.assertEqual(packed[34], 1)     # Clock_Follow in the demo
        self.assertEqual(packed[36], 30)    # Double_Press_ms in the demo
        self.assertEqual(packed[37], 1)     # the demo stores double press commands
        self.assertEqual(packed[38], 1)     # Remote_Mode CC in the demo

class LinkTogglesTest(unittest.TestCase):
    """Bit 1 of global byte 35, beside LED_Feedback in bit 0: what a toggle
    sends sets the other toggles sending the same CC or note (firmware 0.77)."""

    def pack_with(self, feedback, link):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        g.loc[g["Label"] == "LED_Feedback", "Value"] = feedback
        g.loc[g["Label"] == "Link_Toggles", "Value"] = link
        return packer.pack_config(sections)

    def test_both_bits_round_trip(self):
        for feedback, link, byte in (("N", "N", 0), ("Y", "N", 1), ("N", "Y", 2), ("Y", "Y", 3)):
            packed = self.pack_with(feedback, link)
            self.assertEqual(packed[35] & 0x0F, byte, (feedback, link))
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual((back["LED_Feedback"], back["Link_Toggles"]), (feedback, link))

    def test_missing_setting_means_off(self):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        sections["Global_Settings"] = g[g["Label"] != "Link_Toggles"]
        self.assertEqual(packer.pack_config(sections)[35] & 0x0F, 1)   # LED_Feedback alone

    def test_erased_byte_reads_off(self):
        image = bytearray(self.pack_with("N", "N"))
        image[35] = 0xFF
        back = unpacker.unpack_config(bytes(image))[0].set_index("Label")["Value"]
        self.assertEqual((back["LED_Feedback"], back["Link_Toggles"]), ("N", "N"))

    def test_bits_match_firmware(self):
        import re
        from lib import settingsBinaryPacker as sbp
        defines = open(os.path.join(FIRMWARE, "Core", "Inc", "midi_defines.h")).read()
        for name, value in (("LED_FEEDBACK_HOST", sbp.LED_FEEDBACK_HOST),
                            ("LED_FEEDBACK_LINK", sbp.LED_FEEDBACK_LINK)):
            m = re.search(r"#define\s+%s\s+\((0x[0-9A-Fa-f]+)\)" % name, defines)
            self.assertIsNotNone(m, name)
            self.assertEqual(int(m.group(1), 16), value, name)

    def test_on_pedal_editor_keeps_the_other_bit(self):
        """Both are S_FLAG entries on the same byte, so saving one keeps the other."""
        editor = open(os.path.join(FIRMWARE, "Core", "Src", "editor.c")).read()
        self.assertRegex(editor, r'"LEDFEEDB",\s*GLOBAL_SETTINGS_LED_FEEDBACK,\s*S_FLAG,\s*LED_FEEDBACK_HOST')
        self.assertRegex(editor, r'"LINKTOGL",\s*GLOBAL_SETTINGS_LED_FEEDBACK,\s*S_FLAG,\s*LED_FEEDBACK_LINK')

class RemotePressTest(unittest.TestCase):
    """Global bytes 38-40: CC or notes from USB press the switches."""

    def pack_with(self, **values):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        for label, value in values.items():
            g.loc[g["Label"] == label, "Value"] = value
        return packer.pack_config(sections)

    def decoded(self, packed):
        return unpacker.unpack_config(packed)[0].set_index("Label")["Value"]

    def test_demo(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        self.assertEqual(list(packed[38:41]), [1, 16, 102])

    def test_round_trip(self):
        for mode, byte in (("Off", 0), ("CC", 1), ("Note", 2)):
            for channel, ch_byte in (("Any", 0), ("1", 1), ("16", 16)):
                packed = self.pack_with(Remote_Mode=mode, Remote_Channel=channel, Remote_First="36")
                self.assertEqual(list(packed[38:41]), [byte, ch_byte, 36], (mode, channel))
                back = self.decoded(packed)
                self.assertEqual((back["Remote_Mode"], back["Remote_Channel"], back["Remote_First"]),
                                 (mode, channel, "36"))

    def test_spellings(self):
        for text, byte in (("off", 0), ("cc", 1), ("note", 2), ("Notes", 2), ("", 0)):
            self.assertEqual(self.pack_with(Remote_Mode=text)[38], byte, text)

    def test_bad_mode_rejected(self):
        with self.assertRaises(ValueError):
            self.pack_with(Remote_Mode="PC")

    def test_first_leaves_room_for_ten(self):
        self.assertEqual(self.pack_with(Remote_First="127")[40], 118)
        self.assertEqual(self.pack_with(Remote_First="-3")[40], 0)

    def test_missing_settings_mean_off(self):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        sections["Global_Settings"] = g[~g["Label"].str.startswith("Remote_")]
        self.assertEqual(list(packer.pack_config(sections)[38:41]), [0, 0, 102])

    def test_older_images_read_off(self):
        """Configurations written before 0.45 hold 0 here, or erased flash."""
        image = bytearray(self.pack_with(Remote_Mode="CC"))
        for old in (0x00, 0xFF):
            image[38] = image[39] = image[40] = old
            back = self.decoded(bytes(image))
            self.assertEqual(back["Remote_Mode"], "Off")
            self.assertEqual(back["Remote_Channel"], "Any")

class UsbPortsTest(unittest.TestCase):
    """USB_Ports, bit 1 of global byte 6 beside USB_MIDI_Thru in bit 0: the
    pedal as three USB MIDI ports (firmware 1.04)."""

    def pack_with(self, ports, thru="Y"):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        g.loc[g["Label"] == "USB_Ports", "Value"] = ports
        g.loc[g["Label"] == "USB_MIDI_Thru", "Value"] = thru
        return packer.pack_config(sections)

    def test_round_trip_beside_the_thru(self):
        for ports, thru, byte in (("1", "Y", 1), ("3", "Y", 3), ("3", "N", 2), ("1", "N", 0), ("", "N", 0)):
            packed = self.pack_with(ports, thru)
            self.assertEqual(packed[6], byte, (ports, thru))
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual((back["USB_Ports"], back["USB_MIDI_Thru"]), (ports or "1", thru))

    def test_bad_values_and_erased_byte(self):
        for text in ("2", "4", "three"):
            with self.assertRaises(ValueError, msg=text):
                self.pack_with(text)
        packed = bytearray(self.pack_with("3"))
        packed[6] = 0xFF
        back = unpacker.unpack_config(bytes(packed))[0].set_index("Label")["Value"]
        self.assertEqual((back["USB_Ports"], back["USB_MIDI_Thru"]), ("1", "N"))

    def test_bits_match_firmware(self):
        from lib import settingsBinaryPacker as sbp
        text = open(os.path.join(FIRMWARE, "Core", "Inc", "midi_defines.h")).read()
        self.assertIn("#define USB_THRU_ON		(0x%02X)" % sbp.USB_THRU_ON, text)
        self.assertIn("#define USB_THREE_PORTS		(0x%02X)" % sbp.USB_THREE_PORTS, text)

    def test_tools_pick_the_config_port_never_din(self):
        from lib import midiDevice as md
        mac = ["IAC Driver Bus 1", "MIDI Commander Custom Pedal", "MIDI Commander Custom DIN",
               "MIDI Commander Custom Config"]
        self.assertEqual(md._pedal_ports(mac), ["MIDI Commander Custom Config", "MIDI Commander Custom Pedal"])
        windows = ["MIDI Commander Custom", "MIDIOUT2 (MIDI Commander Custom)", "MIDIOUT3 (MIDI Commander Custom)"]
        self.assertEqual(md._pedal_ports(windows), ["MIDIOUT3 (MIDI Commander Custom)", "MIDI Commander Custom"])
        linux = ["MIDI Commander Custom:MIDI Commander Custom MIDI 1 20:0",
                 "MIDI Commander Custom:MIDI Commander Custom MIDI 2 20:1",
                 "MIDI Commander Custom:MIDI Commander Custom MIDI 3 20:2"]
        self.assertEqual(md._pedal_ports(linux), [linux[2], linux[0]])
        self.assertEqual(md._pedal_ports(["MIDI Commander Custom"]), ["MIDI Commander Custom"])
        # Only the pedal's own name: another STM32 MIDI device is not the pedal
        self.assertEqual(md._pedal_ports(["STM32 Virtual ComPort", "MIDI Commander"]), [])

    def test_output_of_the_port_the_input_opened(self):
        from unittest import mock

        from lib import midiDevice as md

        class Port:
            def __init__(self, name):
                self.name = name

            def poll(self):
                return None

            def close(self):
                pass

        def open_input(name):
            if "MIDIIN3" in name:
                raise OSError("in use")     # the Config port, taken by another program
            return Port(name)

        inputs = ["MIDIIN3 (MIDI Commander Custom)", "MIDI Commander Custom"]
        outputs = ["MIDIOUT3 (MIDI Commander Custom)", "MIDI Commander Custom"]
        with mock.patch.object(md, "find_port_names", return_value=(inputs, outputs)), \
                mock.patch.object(md.mido, "open_input", open_input), \
                mock.patch.object(md.mido, "open_output", Port):
            with md.MidiCommander() as dev:
                self.assertEqual((dev.inport.name, dev.outport.name),
                                 ("MIDI Commander Custom", "MIDI Commander Custom"))

class GlobalDefaultsTest(unittest.TestCase):
    """A Global_Settings row left out packs and reads back as its default, the
    one the configurator fills in."""

    def test_missing_rows_read_back_as_the_defaults(self):
        sections = dict(read_config_csv(DEMO_CSV))
        sections["Global_Settings"] = pd.DataFrame([{"Label": "ConfigName", "Value": "BARE"}])
        back = unpacker.unpack_config(pack_config(sections))[0].set_index("Label")["Value"]
        for label, value in layout.GLOBAL_DEFAULTS.items():
            self.assertEqual(back[label], value, label)
        self.assertEqual(set(back.index) - {"ConfigName"}, set(layout.GLOBAL_DEFAULTS))


class BeatCounterTest(unittest.TestCase):
    """Beat_Counter, bits 4-7 of global byte 35: bar.beat on the display in
    bars of that many beats, 0 = off (firmware 0.88)."""

    def pack_with(self, value):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        g.loc[g["Label"] == "Beat_Counter", "Value"] = value
        return packer.pack_config(sections)

    def test_demo_counts_in_four(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        self.assertEqual(packed[35] >> 4, 4)
        back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
        self.assertEqual(back["Beat_Counter"], "4")

    def test_round_trip_beside_the_other_bits(self):
        for text, beats, shown in (("Off", 0, "Off"), ("", 0, "Off"), ("0", 0, "Off"), ("N", 0, "Off"),
                                   ("1", 1, "1"), ("3", 3, "3"), ("7", 7, "7"), ("15", 15, "15")):
            packed = self.pack_with(text)
            self.assertEqual(packed[35], (beats << 4) | 3, text)   # the demo's LED_Feedback and Link_Toggles
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual((back["Beat_Counter"], back["LED_Feedback"], back["Link_Toggles"]),
                             (shown, "Y", "Y"), text)

    def test_bad_values(self):
        for text in ("16", "-1", "four", "4.5x"):
            with self.assertRaises(ValueError, msg=text):
                self.pack_with(text)

    def test_missing_setting_and_erased_byte_read_off(self):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        sections["Global_Settings"] = g[g["Label"] != "Beat_Counter"]
        packed = bytearray(packer.pack_config(sections))
        self.assertEqual(packed[35] >> 4, 0)
        packed[35] = 0xFF
        back = unpacker.unpack_config(bytes(packed))[0].set_index("Label")["Value"]
        self.assertEqual(back["Beat_Counter"], "Off")

    def test_bits_match_firmware(self):
        from lib import settingsBinaryPacker as sbp
        text = open(os.path.join(FIRMWARE, "Core", "Inc", "midi_defines.h")).read()
        self.assertIn("#define BEAT_COUNTER_MASK	(0xF0)", text)
        self.assertIn("#define BEAT_COUNTER_SHIFT	(%d)" % sbp.BEAT_COUNTER_SHIFT, text)
        editor = open(os.path.join(FIRMWARE, "Core", "Src", "editor.c")).read()
        self.assertRegex(editor, r'"BARBEATS",\s*GLOBAL_SETTINGS_LED_FEEDBACK,\s*S_FLAG,\s*BEAT_COUNTER_MASK,\s*%d'
                         % sbp.BEAT_COUNTER_MAX)

class BootBannerTest(unittest.TestCase):
    """The configuration's name crossing the display at power on (0.62)."""

    def source(self, *name):
        return firmware_source(*name)

    def with_banner(self, value):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Global_Settings"].copy()
        where = df.index[df["Label"] == "Boot_Banner"][0]
        df.at[where, "Value"] = value
        return pack_config({**sections, "Global_Settings": df})

    def test_byte_matches_firmware(self):
        import re

        from lib import settingsBinaryPacker as sbp

        m = re.search(r"#define\s+GLOBAL_SETTINGS_BANNER\s+\((\d+)\)", self.source("Inc", "midi_defines.h"))
        self.assertIsNotNone(m)
        self.assertEqual(int(m.group(1)), sbp.GLOBAL_SETTINGS_BANNER)
        # The firmware takes 1..3 and nothing else as a speed
        self.assertIn("speed == 0 || speed > 3", self.source("Src", "display.c"))
        self.assertEqual(sorted(sbp.BANNER_SPEEDS.values()), [0, 1, 2, 3])

    def test_speeds(self):
        for value, byte, back in (("Off", 0, "Off"), ("slow", 1, "Slow"), ("Normal", 2, "Normal"),
                                  ("FAST", 3, "Fast"), ("", 0, "Off")):
            packed = self.with_banner(value)
            self.assertEqual(packed[46], byte, value)
            got = unpacker.unpack_global_settings(packed)
            self.assertEqual(got[got["Label"] == "Boot_Banner"]["Value"].iloc[0], back, value)

    def test_unknown_speed_is_refused(self):
        with self.assertRaises(ValueError):
            self.with_banner("Quick")

    def test_older_configurations_have_none(self):
        # No Boot_Banner row, and erased flash: the fixed boot screen as before
        self.assertEqual(pack_csv(SAMPLE_CSV)[46], 0)
        blank = unpacker.unpack_global_settings(b"\xff" * layout.CONFIG_SIZE)
        self.assertEqual(blank[blank["Label"] == "Boot_Banner"]["Value"].iloc[0], "Off")

    def test_demo_shows_it(self):
        self.assertEqual(pack_csv(DEMO_CSV)[46], 2)

class BankPreviewTest(unittest.TestCase):
    """Bank Up / Down only show a bank until a button confirms it (0.66)."""

    def source(self, *name):
        return firmware_source(*name)

    def with_preview(self, value):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Global_Settings"].copy()
        where = df.index[df["Label"] == "Bank_Preview"][0]
        df.at[where, "Value"] = value
        return pack_config({**sections, "Global_Settings": df})

    def test_byte_matches_firmware(self):
        import re

        from lib import settingsBinaryPacker as sbp

        defines = self.source("Inc", "midi_defines.h")
        m = re.search(r"#define\s+GLOBAL_SETTINGS_BANK_PREVIEW\s+\((\d+)\)", defines)
        self.assertIsNotNone(m)
        self.assertEqual(int(m.group(1)), sbp.GLOBAL_SETTINGS_BANK_PREVIEW)
        m = re.search(r"#define\s+BANK_PREVIEW_MAX_S\s+\((\d+)\)", defines)
        self.assertEqual(int(m.group(1)), sbp.BANK_PREVIEW_MAX_S)
        # The last byte of the global block
        self.assertEqual(sbp.GLOBAL_SETTINGS_BANK_PREVIEW, 47)

    def test_seconds(self):
        for value, byte, back in (("0", 0, "0"), ("Off", 0, "0"), ("", 0, "0"), ("1", 1, "1"),
                                  ("5", 5, "5"), ("60", 60, "60")):
            packed = self.with_preview(value)
            self.assertEqual(packed[47], byte, value)
            got = unpacker.unpack_global_settings(packed)
            self.assertEqual(got[got["Label"] == "Bank_Preview"]["Value"].iloc[0], back, value)

    def test_out_of_range_is_refused(self):
        for value in ("61", "-1", "soon"):
            with self.assertRaises(ValueError, msg=value):
                self.with_preview(value)

    def test_older_configurations_have_none(self):
        self.assertEqual(pack_csv(SAMPLE_CSV)[47], 0)
        blank = unpacker.unpack_global_settings(b"\xff" * layout.CONFIG_SIZE)
        self.assertEqual(blank[blank["Label"] == "Bank_Preview"]["Value"].iloc[0], "0")

    def test_demo_leaves_it_off(self):
        # The stress and latency tests time Bank Up on the demo
        self.assertEqual(pack_csv(DEMO_CSV)[47], 0)

    def test_state_reports_it(self):
        from lib.midiDevice import parse_state

        self.assertIsNone(parse_state([0] * 62)["preview"])           # before firmware 0.66
        self.assertIsNone(parse_state([0] * 62 + [0x7F])["preview"])  # none
        self.assertEqual(parse_state([0] * 62 + [5])["preview"], 5)

class BankSwitchLabelTest(unittest.TestCase):
    """Labels for Bank Down and Bank Up, shown with Bank_Switch_Mode at MIDI only (1.08)."""

    def source(self, *name):
        return firmware_source(*name)

    def sections(self, labels, csv=None):
        sections = dict(read_config_csv(csv or SAMPLE_CSV))
        df = packer.empty_bank_switch_settings()
        for (switch, press), text in labels.items():
            df.loc[(df["Switch"] == switch) & (df["Press"] == press), "Label"] = text
        sections[packer.BANK_SWITCH_SECTION] = df
        return sections

    def test_layout_agrees(self):
        """After the long press labels, 16 bytes, in both the tools and the firmware."""
        header = self.source("Inc", "flash_midi_settings.h")
        self.assertIn("#define EXT2_BANK_SW_LABELS_OFF	(EXT2_LONG_LABELS_OFF + CFG_BUTTONS * BUTTON_LABEL_LEN)", header)
        self.assertIn("#define EXT2_BANK_SW_LABELS_SIZE	(16)", header)
        self.assertEqual(layout.EXT2_BANK_SWITCH_LABELS_SIZE, 16)
        self.assertEqual(layout.EXT2_SIZE, layout.EXT2_BANK_SWITCH_LABELS_OFFSET + 16)
        self.assertEqual(layout.EXT2_SIZE % 16, 0)        # the tools move it 16 bytes at a time
        self.assertEqual(packer.BANK_SWITCH_LABELED, ["Down", "Up"])

    def test_round_trip(self):
        image = packer.pack_flash_image(self.sections({("Down", "Short"): "PREV", ("Up", "Short"): "nxt"}))
        ext = image[layout.EXT2_OFFSET:]
        self.assertEqual(ext[:4], b"EXT2")             # the labels alone write the area
        self.assertEqual(ext[layout.EXT2_BANK_SWITCH_LABELS_OFFSET:], b"PREVnxt " + b"\xff" * 8)
        back = unpacker.unpack_bank_switch_settings(image).set_index(["Switch", "Press"])["Label"]
        self.assertEqual(back.to_dict(), {("Down", "Short"): "PREV", ("Down", "Long"): "",
                                          ("Up", "Short"): "nxt", ("Up", "Long"): ""})

    def test_one_label(self):
        image = packer.pack_flash_image(self.sections({("Up", "Short"): "NEXT"}))
        labels = image[layout.EXT2_OFFSET + layout.EXT2_BANK_SWITCH_LABELS_OFFSET:]
        self.assertEqual(labels[:8], b"    NEXT")         # spaces are no label to the firmware

    def test_no_labels_no_area(self):
        self.assertIsNone(packer.pack_ext2(self.sections({})))
        sections = dict(read_config_csv(SAMPLE_CSV))
        sections.pop(packer.BANK_SWITCH_SECTION, None)
        self.assertIsNone(packer.pack_ext2(sections))
        # a CSV written before 1.08 has no Label column
        df = packer.empty_bank_switch_settings().drop(columns=["Label"])
        sections[packer.BANK_SWITCH_SECTION] = df
        self.assertIsNone(packer.pack_ext2(sections))

    def test_long_press_row_has_none(self):
        """The screen shows one label a switch: a long press row's would be lost."""
        with self.assertRaises(ValueError) as caught:
            packer.pack_flash_image(self.sections({("Down", "Long"): "JUMP"}))
        self.assertIn("Down Long", str(caught.exception))

    def test_csv_round_trip(self):
        import tempfile

        from lib.configCsv import write_config_csv

        sections = self.sections({("Down", "Short"): "PREV", ("Up", "Short"): "NEXT"}, DEMO_CSV)
        image = packer.pack_flash_image(sections)
        frames = unpacker.unpack_config(image)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "back.csv")
            write_config_csv(out, frames[0], frames[1], frames[2], df_long_press=frames[3],
                             df_expression=frames[4], df_bank_enter=frames[5], df_sysex=frames[6],
                             df_bank_switch=frames[7], df_setlist=frames[8])
            again = read_config_csv(out)
        self.assertEqual(packer.pack_flash_image(again)[layout.EXT2_OFFSET:][layout.EXT2_BANK_SWITCH_LABELS_OFFSET:],
                         image[layout.EXT2_OFFSET:][layout.EXT2_BANK_SWITCH_LABELS_OFFSET:])

    def test_firmware(self):
        """Ten cells only with MIDI only and a label, Bank Up on top."""
        display = self.source("Src", "display.c")
        self.assertIn("!= BANK_SWITCH_MIDI_ONLY) return NULL;", display)
        self.assertIn("flash_settings_bank_switch_labels()", display)
        self.assertIn("draw_label_cell(4, which == 1, true, label, false);", display)

class MidiMapTest(unittest.TestCase):
    """Messages arriving over USB turned into others (0.90), in the second
    extension area."""

    def source(self, *name):
        return firmware_source(*name)

    def sections(self, rows):
        sections = dict(read_config_csv(DEMO_CSV))
        sections[packer.MIDI_MAP_SECTION] = pd.DataFrame(rows, columns=packer.MIDI_MAP_COLUMNS)
        return sections

    def ext2(self, rows):
        return packer.pack_flash_image(self.sections(rows))[layout.EXT2_OFFSET:]

    def test_constants_agree(self):
        header = self.source("Inc", "flash_midi_settings.h")
        for name, want in (("MIDI_MAP_UNUSED", 0xFF), ("MIDI_MAP_ANY", 0xFF), ("MIDI_MAP_NOTHING", 0),
                           ("MIDI_MAP_RUN", packer.MIDI_MAP_OUT_TYPES["Run"]), ("MIDI_MAP_KEEP", 1),
                           ("FLASH_EXT2_PAGES", layout.EXT2_PAGES),
                           ("EXT2_MARKER", struct.unpack("<I", layout.EXT2_MARKER)[0])):
            m = re.search(rf"^#define\s+{name}\s+\((0x[0-9A-Fa-f]+|\d+)U?\)", header, re.M)
            self.assertIsNotNone(m, name)
            self.assertEqual(int(m.group(1), 0), want, name)
        # The table fits its two pages, and they are above the banner's page
        self.assertLessEqual(layout.EXT2_SIZE, layout.EXT2_PAGES * 2048)
        self.assertIn("FLASH_BANNER_ADDR + FLASH_PAGE_SIZE", header)

    def test_packs_the_table(self):
        ext = self.ext2([
            {"In_Type": "PC", "In_Channel": "15", "Out_Type": "CC", "Out_Channel": "2", "Out_Number": "20",
             "Out_Min": "127"},
            {"In_Type": "cc", "In_Number": "7", "In_Min": "10", "In_Max": "100", "Out_Type": "PitchBend",
             "Out_Min": "0", "Out_Max": "127", "Keep": "Y"},
            {"In_Type": "Note", "In_Channel": "Any", "In_Number": "36", "Out_Type": "Run", "Run_Bank": "30",
             "Run_Button": "b", "Run_List": "long"},
            {"In_Type": "Pressure", "Out_Type": "Nothing"},
            {"In_Type": "Note", "In_Number": "60", "Out_Type": "", "Out_Channel": "3"},   # same type
            {"In_Type": "", "Out_Type": "CC"},                                           # left out
        ])
        self.assertEqual(ext[:16], b"EXT2" + b"\xff" * 12)
        table = ext[16:]
        self.assertEqual(table[:60], bytes([
            0xC0, 15, 0xFF, 0, 127, 0xB0, 2, 20, 127, 127, 0, 0xFF,
            0xB0, 0, 7, 10, 100, 0xE0, 0, 0xFF, 0, 127, 1, 0xFF,
            0x90, 0, 36, 0, 127, 0x01, 30, 0x15, 0xFF, 0xFF, 0, 0xFF,
            0xD0, 0, 0xFF, 0, 127, 0x00, 0, 0xFF, 0xFF, 0xFF, 0, 0xFF,
            0x90, 0, 60, 0, 127, 0x90, 3, 0xFF, 0xFF, 0xFF, 0, 0xFF,
        ]))
        self.assertEqual(table[60:layout.EXT2_LONG_LABELS_OFFSET - 16],
                         b"\xff" * (layout.EXT2_LONG_LABELS_OFFSET - 16 - 60))
        back = unpacker.unpack_midi_map(bytes(layout.EXT2_OFFSET) + ext)
        self.assertEqual(back["In_Type"].tolist(), ["PC", "CC", "Note", "Pressure", "Note"])
        self.assertEqual(back.iloc[2][["Run_Bank", "Run_Button", "Run_List"]].tolist(), ["30", "B", "Long"])
        self.assertEqual(back.iloc[1][["In_Min", "In_Max", "Out_Min", "Out_Max", "Keep"]].tolist(),
                         ["10", "100", "0", "127", "Y"])
        # and packed again it is the same
        again = self.sections([])
        again[packer.MIDI_MAP_SECTION] = back
        self.assertEqual(packer.pack_flash_image(again)[layout.EXT2_OFFSET:], ext)

    def test_refuses_what_it_cannot_store(self):
        good = {"In_Type": "CC", "In_Number": "1", "Out_Type": "CC", "Out_Number": "2"}
        for field, bad in (("In_Type", "SysEx"), ("In_Channel", "17"), ("In_Channel", "0"),
                           ("In_Number", "128"), ("In_Min", "x"), ("Out_Type", "Clock"),
                           ("Out_Channel", "17"), ("Out_Number", "-1"), ("Out_Min", "200")):
            with self.assertRaises(ValueError, msg=f"{field}={bad}"):
                self.ext2([{**good, field: bad}])
        with self.assertRaises(ValueError):
            self.ext2([{**good, "In_Min": "100", "In_Max": "10"}])
        # a pitch bend has no number: none to match, none to keep
        with self.assertRaises(ValueError):
            self.ext2([{**good, "In_Type": "PitchBend"}])
        with self.assertRaises(ValueError):
            self.ext2([{**good, "In_Type": "PitchBend", "In_Number": "", "Out_Number": ""}])
        self.ext2([{**good, "In_Type": "PitchBend", "In_Number": ""}])
        for field, bad in (("Run_Bank", "32"), ("Run_Bank", ""), ("Run_Button", "E"), ("Run_List", "Triple")):
            run = {"In_Type": "PC", "Out_Type": "Run", "Run_Bank": "1", "Run_Button": "A", "Run_List": "Short"}
            with self.assertRaises(ValueError, msg=f"{field}={bad}"):
                self.ext2([{**run, field: bad}])
        self.ext2([good] * layout.MIDI_MAP_COUNT)
        with self.assertRaises(ValueError):
            self.ext2([good] * (layout.MIDI_MAP_COUNT + 1))

    def test_without_a_map_the_area_is_not_written(self):
        sections = read_config_csv(SAMPLE_CSV)
        self.assertNotIn(packer.MIDI_MAP_SECTION, sections)
        self.assertIsNone(packer.pack_ext2(sections))
        self.assertLessEqual(len(packer.pack_flash_image(sections)), layout.EXT2_OFFSET)
        self.assertEqual(len(unpacker.unpack_midi_map(packer.pack_flash_image(sections))), 0)
        # Without the marker nothing there is read, whatever it holds
        image = bytes(layout.EXT2_OFFSET) + b"EXT1" + self.ext2([{"In_Type": "PC", "Out_Type": "PC"}])[4:]
        self.assertEqual(len(unpacker.unpack_midi_map(image)), 0)

    def test_demo(self):
        """A PC from the DAW becomes two CCs, the mod wheel turns round, a pad runs the tuner."""
        m = read_config_csv(DEMO_CSV)[packer.MIDI_MAP_SECTION]
        self.assertEqual(m["In_Type"].tolist(), ["PC", "PC", "CC", "Note", "PitchBend"])
        self.assertEqual(m["Out_Type"].tolist(), ["CC", "CC", "CC", "Run", "CC"])

    def test_write_and_read_back(self):
        from unittest import mock

        import lib.slotIO as slot_io

        sections = read_config_csv(DEMO_CSV)
        config, image = slot_io.pack_sections(sections)
        with mock.patch.object(slot_io, "time", mock.Mock(sleep=lambda s: None)):
            pedal = FakePedal(version="0.90")
            slot_io.write_image(pedal, config, image)
            data, back = slot_io.read_image(pedal, "0.90")
            self.assertEqual(back, image)
            # Older firmware: everything else is written, the map is not
            logged = []
            pedal = FakePedal(version="0.89")
            slot_io.write_image(pedal, config, image, log=logged.append)
            self.assertTrue(any("0.90" in line for line in logged), logged)
            self.assertEqual(bytes(pedal.flash[0][: layout.EXT2_OFFSET]), image[: layout.EXT2_OFFSET])
            self.assertEqual(bytes(pedal.flash[0][layout.EXT2_OFFSET:]).count(0xFF), 2 * 2048)
            data, back = slot_io.read_image(pedal, "0.89")
            self.assertEqual(back, image[: layout.EXT2_OFFSET])

    def test_csv_round_trip(self):
        import tempfile

        from lib import slotIO

        image = packer.pack_flash_image(read_config_csv(DEMO_CSV))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "back.csv")
            slotIO.save_csv(path, image[: layout.CONFIG_SIZE], image)
            again = read_config_csv(path)
            self.assertIn(packer.MIDI_MAP_SECTION, again)
            self.assertEqual(packer.pack_flash_image(again), image)

    def test_firmware(self):
        """Where the firmware looks at the map, and what it leaves alone."""
        rx = self.source("..", "USB_DEVICE", "App", "usbd_midi_if.c")
        self.assertIn("if(!midi_map_message(data, thru_add)) thru_push(data, len);", rx)
        self.assertEqual(rx.count("thru_channel(data, len);"), 3)
        flash = self.source("Src", "flash_midi_settings.c")
        self.assertIn("eraseInit.PageAddress = FLASH_EXT2_ADDR(target_slot);", flash)
        self.assertIn("== EXT2_MARKER ? ext + offset : NULL", flash)
        self.assertIn("return ext2_part(EXT2_MAP_OFF);", flash)


if __name__ == "__main__":
    unittest.main()
