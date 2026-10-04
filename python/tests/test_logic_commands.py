"""The commands that decide: sequences, variables and conditions, macros, listening, buttons."""

import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# roundtrip_support also puts python/ on the path, for lib
from roundtrip_support import DEMO_CSV, norm  # noqa: E402
import lib.binaryUnpacker as unpacker  # noqa: E402
import lib.cmdBinaryPacker as cbp  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
import lib.configPacker as packer  # noqa: E402


class SequencerTest(unittest.TestCase):
    """The Seq command, a step sequencer above a CC or a Note (firmware 0.52)."""

    @staticmethod
    def pack_seq(steps, div=""):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row["A_CommandType"] = "Seq"
        row["A_OnValue_(CC/PB)"] = steps
        row["A_KeyMode_(Key)"] = div
        return bytes(cbp.pack_row(pd.Series(row)))[:4]

    def test_mode_and_bytes_match_firmware(self):
        """The Seq nibble and the two values a step byte can take instead."""
        import re

        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc", "midi_defines.h")
        with open(path) as handle:
            text = handle.read()
        modes = dict(re.findall(r"^#define\s+CMD_(\w+)_MODE\s+\((\d+)\)", text, re.M))
        self.assertEqual(int(modes["SEQ"]), cbp.CMD_SEQ_MODE)
        taken = [int(v) for v in modes.values()]
        self.assertEqual(len(taken), len(set(taken)))   # still a nibble each
        for name, value in (("SEQ_REST", cbp.SEQ_REST), ("SEQ_NO_STEP", cbp.SEQ_NO_STEP)):
            fw = re.search(r"^#define\s+" + name + r"\s+\((0x[0-9A-Fa-f]+)\)", text, re.M)
            self.assertEqual(int(fw.group(1), 16), value, name)
        fw = re.search(r"^#define\s+SEQ_MAX_STEPS\s+\((\d+)\)", text, re.M)
        self.assertEqual(int(fw.group(1)), cbp.SEQ_MAX_STEPS)
        # the whole sequence fits in the commands a button has above its CC
        self.assertEqual(cbp.SEQ_MAX_STEPS,
                         (cbp.MIDI_NUM_COMMANDS_PER_SWITCH - 1) * cbp.SEQ_STEPS_PER_CMD)

    def test_seq_round_trip(self):
        for text, div, packed_steps in (
                ("127 0", "1/8", [127, 0]),
                ("60 -", "1/16", [60, cbp.SEQ_REST]),
                ("- -", "1/4", [cbp.SEQ_REST, cbp.SEQ_REST]),
                ("90", "1/1", [90, cbp.SEQ_NO_STEP]),
                ("100,64", "", [100, 64])):
            packed = self.pack_seq(text, div)
            wanted_div = cbp.LFO_DIVISIONS.index(div or cbp.SEQ_DEFAULT_DIV)
            self.assertEqual(list(packed), [0x0A, wanted_div] + packed_steps, text)
            back = unpacker.unpack_command(packed)
            self.assertEqual(back["CommandType"], "Seq")
            self.assertEqual(back["KeyMode_(Key)"], div or cbp.SEQ_DEFAULT_DIV, text)
            self.assertEqual(back["OnValue_(CC/PB)"],
                             cbp.steps_text(packed_steps), text)

    def test_seq_rejects_what_is_not_a_step(self):
        for text in ("128", "-1", "loud", "1 2 3"):
            with self.assertRaises(ValueError, msg=text):
                self.pack_seq(text)
        with self.assertRaises(ValueError):
            self.pack_seq("1 2", "1/5")

    def test_seq_without_steps_ends_the_sequence(self):
        packed = self.pack_seq("")
        self.assertEqual(list(packed)[2:], [cbp.SEQ_NO_STEP, cbp.SEQ_NO_STEP])
        self.assertEqual(unpacker.unpack_command(packed)["OnValue_(CC/PB)"], "")

    def test_seq_is_not_an_empty_command(self):
        """It shares the empty command type, but zero is still no command."""
        self.assertEqual(unpacker.unpack_command(bytes([0, 0, 0, 0]))["CommandType"], "")
        self.assertEqual(unpacker.unpack_command(bytes([0x0A, 3, 60, 64]))["CommandType"], "Seq")

    def test_demo_holds_an_arpeggio(self):
        """Held, STRT of bank 6 plays four notes, an eighth note each."""
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        frames = unpacker.unpack_config(packed)
        long_press = next(f for f in frames
                          if "A_CommandType" in f.columns and "Label" not in f.columns)
        row = long_press[(long_press["Bank_Number"].astype(str) == "6")
                         & (long_press["Button_Identifier"].astype(str) == "3")].iloc[0]
        self.assertEqual((norm(row["A_CommandType"]), norm(row["A_OnValue_(CC/PB)"]),
                          norm(row["A_KeyMode_(Key)"])), ("Seq", "60 64", "1/8"))
        self.assertEqual((norm(row["B_CommandType"]), norm(row["B_OnValue_(CC/PB)"])),
                         ("Seq", "67 72"))
        self.assertEqual((norm(row["C_CommandType"]), norm(row["C_Number_(PC/CC/Note)"]),
                          norm(row["C_Toggle_(CC/PB/Note)"])), ("Note", "60", "Y"))

class ValuesAndConditionsTest(unittest.TestCase):
    """The Value and If commands (firmware 0.54)."""

    FIRMWARE = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core")

    @staticmethod
    def pack(cmd_type, **fields):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row["A_CommandType"] = cmd_type
        for field, value in fields.items():
            row[f"A_{field}"] = value
        return bytes(cbp.pack_row(pd.Series(row)))[:4]

    def defines(self):
        with open(os.path.join(self.FIRMWARE, "Inc", "midi_defines.h")) as handle:
            return handle.read()

    def test_modes_match_firmware(self):
        """Both share the empty command type, each with a nibble of its own."""
        import re

        text = self.defines()
        modes = dict(re.findall(r"^#define\s+CMD_(\w+)_MODE\s+\((\d+)\)", text, re.M))
        self.assertEqual(int(modes["VAR"]), cbp.CMD_VAR_MODE)
        self.assertEqual(int(modes["IF"]), cbp.CMD_IF_MODE)
        taken = [int(v) for v in modes.values()]
        self.assertEqual(len(taken), len(set(taken)))       # still a nibble each
        self.assertTrue(all(0 < v <= 15 for v in taken))

    def test_names_match_firmware(self):
        """What the tools offer is exactly what the firmware knows, in order."""
        import re

        text = self.defines()

        def value(name):
            found = re.search(r"^#define\s+" + name + r"\s+\((\d+)\)", text, re.M)
            self.assertIsNotNone(found, name)
            return int(found.group(1))

        for i, name in enumerate(("VAR_SET", "VAR_ADD", "VAR_SUB")):
            self.assertEqual(value(name), i, name)
        self.assertEqual(value("VAR_MODE_COUNT"), len(cbp.VAR_MODES))
        self.assertEqual(value("VAR_COUNT"), cbp.VAR_COUNT)
        tests = ("IF_BUTTON_ON", "IF_BUTTON_OFF", "IF_VALUE_EQ", "IF_VALUE_NE",
                 "IF_VALUE_LT", "IF_VALUE_GE", "IF_BANK", "IF_NOT_BANK")
        for i, name in enumerate(tests):
            self.assertEqual(value(name), i, name)
        self.assertEqual(value("IF_COUNT"), len(cbp.IF_TESTS))

    def test_firmware_answers_every_test(self):
        """if_holds has a case for each one, so none quietly lets a command by."""
        with open(os.path.join(self.FIRMWARE, "Src", "switch_router.c")) as handle:
            source = handle.read()
        holds = source.split("static bool if_holds", 1)[1].split("\n}", 1)[0]
        for name in ("IF_BUTTON_ON", "IF_BUTTON_OFF", "IF_VALUE_EQ", "IF_VALUE_NE",
                     "IF_VALUE_LT", "IF_VALUE_GE", "IF_BANK", "IF_NOT_BANK"):
            self.assertIn("case " + name + ":", holds, name)

    def test_value_round_trip(self):
        for which, mode, amount, top, packed in (
                ("1", "Set", "0", "", [0x0B, 0x00, 0, 127]),
                ("3", "Add", "1", "2", [0x0B, 0x12, 1, 2]),
                ("8", "Sub", "5", "100", [0x0B, 0x27, 5, 100]),
                ("2", "", "64", "", [0x0B, 0x01, 64, 127])):
            raw = self.pack("Value", **{"Number_(PC/CC/Note)": which,
                                        "KeyMode_(Key)": mode,
                                        "OnValue_(CC/PB)": amount,
                                        "OffValue_(CC)": top})
            self.assertEqual(list(raw), packed, which)
            back = unpacker.unpack_command(raw)
            self.assertEqual(back["CommandType"], "Value")
            self.assertEqual(back["Number_(PC/CC/Note)"], which)
            self.assertEqual(back["KeyMode_(Key)"], mode or "Set")
            self.assertEqual(back["OnValue_(CC/PB)"], amount)
            self.assertEqual(back["OffValue_(CC)"], top or "127")

    def test_value_keeps_the_toggle_bit_clear(self):
        """Byte 1 carries the value and the mode, never the toggling mark."""
        for mode in cbp.VAR_MODES:
            raw = self.pack("Value", **{"Number_(PC/CC/Note)": "8", "KeyMode_(Key)": mode})
            self.assertEqual(raw[1] & 0x80, 0, mode)

    def test_value_refuses_what_it_cannot_do(self):
        with self.assertRaises(ValueError):
            self.pack("Value", **{"KeyMode_(Key)": "Multiply"})

    def test_if_round_trip(self):
        for test, number, value, packed in (
                ("Button on", "4", "", [0x0C, 0, 3, 0]),
                ("Button off", "C", "", [0x0C, 1, 6, 0]),
                ("Value =", "3", "2", [0x0C, 2, 2, 2]),
                ("Value <>", "1", "0", [0x0C, 3, 0, 0]),
                ("Value <", "8", "64", [0x0C, 4, 7, 64]),
                ("Value >=", "2", "127", [0x0C, 5, 1, 127]),
                ("Bank is", "", "5", [0x0C, 6, 0, 5]),
                ("Bank is not", "", "0", [0x0C, 7, 0, 0])):
            raw = self.pack("If", **{"KeyMode_(Key)": test,
                                     "Number_(PC/CC/Note)": number,
                                     "OnValue_(CC/PB)": value})
            self.assertEqual(list(raw), packed, test)
            back = unpacker.unpack_command(raw)
            self.assertEqual(back["CommandType"], "If")
            self.assertEqual(back["KeyMode_(Key)"], test)
            self.assertEqual(back["Number_(PC/CC/Note)"], number, test)
            self.assertEqual(back["OnValue_(CC/PB)"], value, test)

    def test_if_refuses_a_test_it_does_not_know(self):
        with self.assertRaises(ValueError):
            self.pack("If", **{"KeyMode_(Key)": "Feels right"})

    def test_neither_is_an_empty_command(self):
        """They share the empty command type, but zero is still no command."""
        self.assertEqual(unpacker.unpack_command(bytes([0, 0, 0, 0]))["CommandType"], "")
        self.assertEqual(unpacker.unpack_command(bytes([0x0B, 0, 0, 0]))["CommandType"], "Value")
        self.assertEqual(unpacker.unpack_command(bytes([0x0C, 0, 0, 0]))["CommandType"], "If")

    def test_demo_holds_a_shift_layer_and_a_counter(self):
        """Bank 11: held, NUDG asks about BOST and ALL5 counts round three."""
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        frames = unpacker.unpack_config(packed)
        long_press = next(f for f in frames
                          if "A_CommandType" in f.columns and "Label" not in f.columns)

        def row_of(button):
            return long_press[(long_press["Bank_Number"].astype(str) == "11")
                              & (long_press["Button_Identifier"].astype(str) == button)].iloc[0]

        row = row_of("C")
        self.assertEqual((norm(row["A_CommandType"]), norm(row["A_KeyMode_(Key)"]),
                          norm(row["A_Number_(PC/CC/Note)"])), ("If", "Button on", "4"))
        self.assertEqual((norm(row["B_CommandType"]), norm(row["B_Number_(PC/CC/Note)"])),
                         ("CC", "61"))
        self.assertEqual((norm(row["C_CommandType"]), norm(row["C_KeyMode_(Key)"])),
                         ("If", "Button off"))
        self.assertEqual((norm(row["D_CommandType"]), norm(row["D_Number_(PC/CC/Note)"])),
                         ("CC", "62"))

        row = row_of("1")
        self.assertEqual((norm(row["A_CommandType"]), norm(row["A_KeyMode_(Key)"]),
                          norm(row["A_OnValue_(CC/PB)"]), norm(row["A_OffValue_(CC)"])),
                         ("Value", "Add", "1", "2"))
        for n, (test_slot, cmd_slot) in enumerate((("B", "C"), ("D", "E"), ("F", "G"))):
            self.assertEqual((norm(row[f"{test_slot}_CommandType"]),
                              norm(row[f"{test_slot}_KeyMode_(Key)"]),
                              norm(row[f"{test_slot}_OnValue_(CC/PB)"])),
                             ("If", "Value =", str(n)))
            self.assertEqual((norm(row[f"{cmd_slot}_CommandType"]),
                              norm(row[f"{cmd_slot}_Number_(PC/CC/Note)"])),
                             ("PC", str(10 + n)))

class MacroTest(unittest.TestCase):
    """The Macro command (firmware 0.56)."""

    FIRMWARE = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core")

    @staticmethod
    def pack(cmd_type, **fields):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row["A_CommandType"] = cmd_type
        for field, value in fields.items():
            row[f"A_{field}"] = value
        return bytes(cbp.pack_row(pd.Series(row)))[:4]

    def source(self, name):
        with open(os.path.join(self.FIRMWARE, name)) as handle:
            return handle.read()

    def test_nibble_and_lists_match_firmware(self):
        """One more nibble of the empty command type, and the three lists."""
        import re

        text = self.source(os.path.join("Inc", "midi_defines.h"))
        modes = dict(re.findall(r"^#define\s+CMD_(\w+)_MODE\s+\((\d+)\)", text, re.M))
        self.assertEqual(int(modes["MACRO"]), cbp.CMD_MACRO_MODE)
        taken = [int(v) for v in modes.values()]
        self.assertEqual(len(taken), len(set(taken)))       # still a nibble each
        self.assertTrue(all(0 < v <= 15 for v in taken))

        def value(name):
            found = re.search(r"^#define\s+" + name + r"\s+\((\d+)\)", text, re.M)
            self.assertIsNotNone(found, name)
            return int(found.group(1))

        for i, name in enumerate(("MACRO_LIST_SHORT", "MACRO_LIST_LONG", "MACRO_LIST_DOUBLE")):
            self.assertEqual(value(name), i, name)
        self.assertEqual(value("MACRO_LIST_COUNT"), len(cbp.MACRO_LISTS))
        depth = re.search(r"^#define\s+MACRO_DEPTH\s+\((\d+)\)", 
                          self.source(os.path.join("Src", "switch_router.c")), re.M)
        self.assertIsNotNone(depth)
        self.assertEqual(int(depth.group(1)), cbp.MACRO_DEPTH)

    def test_firmware_cannot_go_round_for_ever(self):
        """A list already running is never called again, however deep it goes."""
        source = self.source(os.path.join("Src", "switch_router.c"))
        self.assertIn("macro_on_stack", source)
        # Both the press and the release pass ask before calling
        self.assertEqual(source.count("depth >= MACRO_DEPTH || macro_on_stack"), 2)

    def test_round_trip(self):
        for bank, button, which, packed in (
                ("0", "1", "Short", [0x0D, 0, 0x00, 0]),
                ("11", "B", "Short", [0x0D, 11, 0x05, 0]),
                ("31", "D", "Long", [0x0D, 31, 0x17, 0]),
                ("5", "4", "Double", [0x0D, 5, 0x23, 0]),
                ("7", "A", "", [0x0D, 7, 0x04, 0])):
            raw = self.pack("Macro", **{"OnValue_(CC/PB)": bank,
                                        "Number_(PC/CC/Note)": button,
                                        "KeyMode_(Key)": which})
            self.assertEqual(list(raw), packed, bank + button)
            back = unpacker.unpack_command(raw)
            self.assertEqual(back["CommandType"], "Macro")
            self.assertEqual(back["OnValue_(CC/PB)"], bank)
            self.assertEqual(back["Number_(PC/CC/Note)"], button)
            self.assertEqual(back["KeyMode_(Key)"], which or "Short")

    def test_keeps_the_toggle_bit_clear(self):
        """Byte 1 carries the bank, never the toggling mark."""
        for bank in ("0", "31"):
            raw = self.pack("Macro", **{"OnValue_(CC/PB)": bank})
            self.assertEqual(raw[1] & 0x80, 0, bank)

    def test_refuses_a_list_it_does_not_know(self):
        with self.assertRaises(ValueError):
            self.pack("Macro", **{"KeyMode_(Key)": "Triple"})

    def test_is_not_an_empty_command(self):
        self.assertEqual(unpacker.unpack_command(bytes([0, 0, 0, 0]))["CommandType"], "")
        self.assertEqual(unpacker.unpack_command(bytes([0x0D, 0, 0, 0]))["CommandType"], "Macro")

    def test_costs_four_bytes_instead_of_the_whole_list(self):
        """The point of it: the call is one command wherever the list is used."""
        called = [self.pack("PC", **{"Channel_(PC/CC/Note/PB)": "1",
                                     "Number_(PC/CC/Note)": str(n)}) for n in range(10)]
        self.assertEqual(sum(len(c) for c in called), 40)
        self.assertEqual(len(self.pack("Macro", **{"OnValue_(CC/PB)": "11"})), 4)

    def test_demo_calls_the_stored_sequence(self):
        """HOME, held on 2, runs bank 11's WAIT list instead of copying it."""
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        frames = unpacker.unpack_config(packed)
        long_press = next(f for f in frames
                          if "A_CommandType" in f.columns and "Label" not in f.columns)
        row = long_press[(long_press["Bank_Number"].astype(str) == "0")
                         & (long_press["Button_Identifier"].astype(str) == "2")].iloc[0]
        self.assertEqual((norm(row["A_CommandType"]), norm(row["A_OnValue_(CC/PB)"]),
                          norm(row["A_Number_(PC/CC/Note)"]), norm(row["A_KeyMode_(Key)"])),
                         ("Macro", "11", "B", "Short"))

        # And what it calls is really a program change, a pause and a CC
        short = next(f for f in frames if "Label" in f.columns and "A_CommandType" in f.columns)
        called = short[(short["Bank_Number"].astype(str) == "11")
                       & (short["Button_Identifier"].astype(str) == "B")].iloc[0]
        self.assertEqual(norm(called["A_CommandType"]), "PC")
        self.assertEqual((norm(called["B_CommandType"]), norm(called["B_Duration_(Note/PB)"])),
                         ("Wait", "200"))
        self.assertEqual(norm(called["C_CommandType"]), "CC")

class ListenTest(unittest.TestCase):
    """The Listen command (firmware 0.69)."""

    FIRMWARE = MacroTest.FIRMWARE
    pack = staticmethod(MacroTest.pack)

    def test_nibble_matches_firmware(self):
        import re

        with open(os.path.join(self.FIRMWARE, "Inc", "midi_defines.h")) as handle:
            text = handle.read()
        modes = dict(re.findall(r"^#define\s+CMD_(\w+)_MODE\s+\((\d+)\)", text, re.M))
        self.assertEqual(int(modes["LISTEN"]), cbp.CMD_LISTEN_MODE)
        taken = [int(v) for v in modes.values()]
        self.assertEqual(len(taken), len(set(taken)))

    def test_round_trip(self):
        for number, on, off, packed in (
                ("22", "1", "0", [0x0E, 22, 1, 0]),
                ("80", "0", "127", [0x0E, 80, 0, 127]),
                ("127", "64", "63", [0x0E, 127, 64, 63])):
            raw = self.pack("Listen", **{"Number_(PC/CC/Note)": number,
                                         "OnValue_(CC/PB)": on, "OffValue_(CC)": off})
            self.assertEqual(list(raw), packed)
            back = unpacker.unpack_command(raw)
            self.assertEqual((back["CommandType"], back["Number_(PC/CC/Note)"],
                              back["OnValue_(CC/PB)"], back["OffValue_(CC)"]),
                             ("Listen", number, on, off))

    def test_empty_values_mean_127_and_0(self):
        raw = self.pack("Listen", **{"Number_(PC/CC/Note)": "9"})
        self.assertEqual(list(raw), [0x0E, 9, 127, 0])

    def test_never_marked_toggling(self):
        """Byte 1 is the CC: its top bit, the toggling mark, stays clear."""
        raw = self.pack("Listen", **{"Number_(PC/CC/Note)": "300", "Toggle_(CC/PB/Note)": "Y"})
        self.assertEqual(raw[1], 127)

    def test_demo_play_listens_on_cc_22(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        frames = unpacker.unpack_config(packed)
        buttons = next(f for f in frames if "Label" in f.columns and "A_CommandType" in f.columns)
        row = buttons[(buttons["Bank_Number"].astype(str) == "1")
                      & (buttons["Button_Identifier"].astype(str) == "2")].iloc[0]
        self.assertEqual((norm(row["A_CommandType"]), norm(row["A_Toggle_(CC/PB/Note)"])), ("CC", "Y"))
        self.assertEqual((norm(row["B_CommandType"]), norm(row["B_Number_(PC/CC/Note)"]),
                          norm(row["B_OnValue_(CC/PB)"]), norm(row["B_OffValue_(CC)"])),
                         ("Listen", "22", "1", "0"))

class ListenLookTest(unittest.TestCase):
    """How a Listen's LED shows the on value (firmware 0.72)."""

    FIRMWARE = MacroTest.FIRMWARE
    pack = staticmethod(MacroTest.pack)

    def test_looks_match_firmware(self):
        import re

        with open(os.path.join(self.FIRMWARE, "Inc", "midi_defines.h")) as handle:
            text = handle.read()
        looks = dict(re.findall(r"^#define\s+LISTEN_(STEADY|SLOW|FAST|DIM)\s+\((\d+)\)", text, re.M))
        self.assertEqual({name.title(): int(v) for name, v in looks.items()},
                         {name: i for i, name in enumerate(cbp.LISTEN_LOOKS)})

    def test_top_bits_carry_the_look(self):
        for look, packed in (("", [0x0E, 23, 1, 0]), ("Steady", [0x0E, 23, 1, 0]),
                             ("Slow", [0x0E, 23, 0x81, 0]), ("fast", [0x0E, 23, 1, 0x80]),
                             ("Dim", [0x0E, 23, 0x81, 0x80])):
            raw = self.pack("Listen", **{"Number_(PC/CC/Note)": "23", "OnValue_(CC/PB)": "1",
                                         "OffValue_(CC)": "0", "KeyMode_(Key)": look})
            self.assertEqual(list(raw), packed, look)
            back = unpacker.unpack_command(raw)
            self.assertEqual((back["OnValue_(CC/PB)"], back["OffValue_(CC)"]), ("1", "0"))
            want = "" if look.title() in ("", "Steady") else look.title()
            self.assertEqual(norm(back.get("KeyMode_(Key)", "")), want)

    def test_unknown_look_is_an_error(self):
        with self.assertRaises(ValueError):
            self.pack("Listen", **{"Number_(PC/CC/Note)": "23", "KeyMode_(Key)": "Strobe"})

    def test_demo_rec_blinks_while_recording(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        frames = unpacker.unpack_config(packed)
        buttons = next(f for f in frames if "Label" in f.columns and "A_CommandType" in f.columns)
        row = buttons[(buttons["Bank_Number"].astype(str) == "1")
                      & (buttons["Button_Identifier"].astype(str) == "1")].iloc[0]
        self.assertEqual([(norm(row[f"{c}_CommandType"]), norm(row[f"{c}_Number_(PC/CC/Note)"]),
                           norm(row[f"{c}_OnValue_(CC/PB)"]), norm(row[f"{c}_KeyMode_(Key)"]))
                          for c in "BC"],
                         [("Listen", "23", "1", "Fast"), ("Listen", "23", "2", "Slow")])

class ButtonCommandTest(unittest.TestCase):
    """The Button command: work another button as a foot would (firmware 0.73)."""

    FIRMWARE = MacroTest.FIRMWARE
    pack = staticmethod(MacroTest.pack)

    def test_actions_match_firmware(self):
        import re

        with open(os.path.join(self.FIRMWARE, "Inc", "midi_defines.h")) as handle:
            text = handle.read()
        acts = dict(re.findall(r"^#define\s+BUTTON_ACT_(\w+)\s+\((\d+)\)", text, re.M))
        self.assertEqual({name.replace("_", " ").title(): int(v) for name, v in acts.items()},
                         {name: i + 1 for i, name in enumerate(cbp.BUTTON_ACTIONS)})
        this = re.search(r"^#define\s+BUTTON_THIS_BANK\s+\((0x[0-9A-Fa-f]+)\)", text, re.M)
        self.assertEqual(int(this.group(1), 16), cbp.BUTTON_THIS_BANK)

    def test_packs_as_a_macro_with_an_action(self):
        cases = (
            ({"Number_(PC/CC/Note)": "3"}, [0x0D, 0x7F, 0x02, 1], ("", "3", "")),
            ({"OnValue_(CC/PB)": "31", "Number_(PC/CC/Note)": "4", "KeyMode_(Key)": "On"},
             [0x0D, 31, 0x03, 2], ("31", "4", "On")),
            ({"OnValue_(CC/PB)": "0", "Number_(PC/CC/Note)": "A", "KeyMode_(Key)": "off long"},
             [0x0D, 0, 0x14, 3], ("0", "A", "Off Long")),
            ({"Number_(PC/CC/Note)": "D", "KeyMode_(Key)": "Set On  Double"},
             [0x0D, 0x7F, 0x27, 4], ("", "D", "Set On Double")),
            ({"Number_(PC/CC/Note)": "1", "KeyMode_(Key)": "Set Off Short"},
             [0x0D, 0x7F, 0x00, 5], ("", "1", "Set Off")),
        )
        for fields, packed, back in cases:
            raw = self.pack("Button", **fields)
            self.assertEqual(list(raw), packed, fields)
            cmd = unpacker.unpack_command(raw)
            self.assertEqual(cmd["CommandType"], "Button")
            self.assertEqual((norm(cmd["OnValue_(CC/PB)"]), cmd["Number_(PC/CC/Note)"],
                              norm(cmd.get("KeyMode_(Key)", "")).replace("Press", "")), back)

    def test_a_macro_still_packs_a_zero(self):
        raw = self.pack("Macro", **{"OnValue_(CC/PB)": "11", "Number_(PC/CC/Note)": "B"})
        self.assertEqual(raw[3], 0)
        self.assertEqual(unpacker.unpack_command(raw)["CommandType"], "Macro")

    def test_unknown_action_is_an_error(self):
        with self.assertRaises(ValueError):
            self.pack("Button", **{"Number_(PC/CC/Note)": "1", "KeyMode_(Key)": "Flip"})

    def test_moving_a_bank_follows_it(self):
        from lib import bankReorder

        df = pd.DataFrame([{"A_CommandType": "Button", "A_OnValue_(CC/PB)": "5",
                            "A_KeyMode_(Key)": "On"},
                           {"A_CommandType": "Button", "A_OnValue_(CC/PB)": "",
                            "A_KeyMode_(Key)": ""}])
        out = bankReorder.remap_commands(df, bankReorder.move_map(5, 2))
        self.assertEqual(list(out["A_OnValue_(CC/PB)"]), ["2", ""])

    def test_demo_wait_sets_the_stage(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        frames = unpacker.unpack_config(packed)
        longs = next(f for f in frames if "Label" not in f.columns and "A_CommandType" in f.columns
                     and "Button_Identifier" in f.columns)
        row = longs[(longs["Bank_Number"].astype(str) == "11")
                    & (longs["Button_Identifier"].astype(str) == "B")].iloc[0]
        self.assertEqual([(norm(row[f"{c}_CommandType"]), norm(row[f"{c}_OnValue_(CC/PB)"]),
                           norm(row[f"{c}_Number_(PC/CC/Note)"]), norm(row[f"{c}_KeyMode_(Key)"]))
                          for c in "AB"],
                         [("Button", "", "3", "On"), ("Button", "31", "4", "On")])


if __name__ == "__main__":
    unittest.main()
