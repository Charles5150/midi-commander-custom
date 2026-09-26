"""Hand written CSVs: pack as written, or say what is wrong and where (#118)."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lib.cmdBinaryPacker as cbp  # noqa: E402
import lib.configPacker as packer  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402

DEMO_CSV = os.path.join(os.path.dirname(HERE), "demo-all-features.csv")


def demo():
    return read_config_csv(DEMO_CSV)


def set_command(sections, section, bank, button, letter, **fields):
    """Write ``fields`` into command ``letter`` of a button's row."""
    df = sections[section]
    at = (df["Bank_Number"].astype(str).str.replace(".0", "", regex=False) == str(bank)) \
        & (df["Button_Identifier"].astype(str) == button)
    assert at.any(), (section, bank, button)
    for name, value in fields.items():
        df.loc[at, f"{letter}_{name}"] = value
    return sections


def set_global(sections, **values):
    g = sections["Global_Settings"]
    for label, value in values.items():
        g.loc[g["Label"] == label, "Value"] = value
    return sections


def cc(**extra):
    fields = {"CommandType": "CC", "Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "20",
              "OnValue_(CC/PB)": "127", "OffValue_(CC)": "0"}
    fields.update(extra)
    return fields


class CommandTypeTest(unittest.TestCase):
    def test_any_case(self):
        want = packer.pack_config(set_command(demo(), "Button_Settings", 5, "A", "J", **cc()))
        for spelling in ("cc", "Cc", " CC "):
            got = packer.pack_config(set_command(demo(), "Button_Settings", 5, "A", "J",
                                                 **cc(CommandType=spelling)))
            self.assertEqual(got, want, spelling)

    def test_every_type_by_its_lower_case_name(self):
        for name in cbp.COMMAND_TYPES.values():
            self.assertEqual(cbp.command_type(name.lower()), name)
            self.assertEqual(cbp.command_type(name.upper()), name)

    def test_empty_and_none_are_no_command(self):
        for text in ("", None, float("nan"), "None", "none"):
            self.assertEqual(cbp.command_type(text), "")

    def test_unknown_is_an_error_that_says_where(self):
        sections = set_command(demo(), "Button_Settings", 5, "B", "C", **cc(CommandType="Program"))
        with self.assertRaises(ValueError) as e:
            packer.pack_config(sections)
        message = str(e.exception)
        self.assertIn("Button_Settings bank 5 button B, command C", message)
        self.assertIn("Unknown CommandType 'Program'", message)
        self.assertIn("PC", message)


class LocationTest(unittest.TestCase):
    def check(self, sections, *parts):
        with self.assertRaises(ValueError) as e:
            packer.pack_flash_image(sections)
        for part in parts:
            self.assertIn(part, str(e.exception))

    def test_short_press(self):
        self.check(set_command(demo(), "Button_Settings", 2, "3", "D", **cc(**{"Channel_(PC/CC/Note/PB)": "17"})),
                   "Button_Settings bank 2 button 3, command D (CC): Channel must be 1-16, not '17'")

    def test_long_press(self):
        sections = demo()
        row = sections["LongPress_Settings"].iloc[0]
        bank, button = int(float(row["Bank_Number"])), str(row["Button_Identifier"])
        set_command(sections, "LongPress_Settings", bank, button, "A", **cc(**{"Channel_(PC/CC/Note/PB)": "0"}))
        self.check(sections, f"LongPress_Settings bank {bank} button {button}, command A (CC)")

    def test_double_press(self):
        sections = demo()
        row = sections["DoublePress_Settings"].iloc[0]
        bank, button = int(float(row["Bank_Number"])), str(row["Button_Identifier"])
        set_command(sections, "DoublePress_Settings", bank, button, "B", CommandType="Nope")
        self.check(sections, f"DoublePress_Settings bank {bank} button {button}, command B")

    def test_button_column(self):
        sections = demo()
        df = sections["Button_Settings"]
        df.loc[(df["Bank_Number"].astype(str).str.replace(".0", "", regex=False) == "4")
               & (df["Button_Identifier"].astype(str) == "C"), "Group"] = "9"
        self.check(sections, "Button_Settings bank 4 button C, Group must be")

    def test_cycle_labels(self):
        sections = demo()
        for i in range(cbp.CYCLE_LABEL_COUNT + 1):
            bank, button = divmod(i, 8)
            set_command(sections, "Button_Settings", 20 + bank, packer.BUTTON_IDS[button], "J",
                        CommandType="Cycle", **{"OnValue_(CC/PB)": f"L{i}"})
        self.check(sections, "Button_Settings bank", "Too many different cycle labels")

    def test_global(self):
        self.check(set_global(demo(), Remote_Mode="PC"), "Global_Settings, Remote_Mode must be")


class ValueTest(unittest.TestCase):
    def pack_one(self, **fields):
        return cbp.pack_row({f"A_{name}": value for name, value in fields.items()})[:4]

    def test_pitch_bend_range(self):
        pb = {"CommandType": "PB", "Channel_(PC/CC/Note/PB)": "1"}
        for value in ("-8192", "0", "8191"):
            self.pack_one(**pb, **{"OnValue_(CC/PB)": value})
        for value in ("-8193", "8192", "20000"):
            with self.assertRaises(ValueError, msg=value):
                self.pack_one(**pb, **{"OnValue_(CC/PB)": value})

    def test_cc_off_value(self):
        self.assertEqual(self.pack_one(**cc(**{"OffValue_(CC)": "128"}))[3], 128)
        # Empty is no off message, as the manual says; 0 is written as 0
        self.assertEqual(self.pack_one(**cc(**{"OffValue_(CC)": ""}))[3], 128)
        self.assertEqual(self.pack_one(**cc(**{"OffValue_(CC)": "0"}))[3], 0)
        for value in ("256", "-1", "x"):
            with self.assertRaises(ValueError) as e:
                self.pack_one(**cc(**{"OffValue_(CC)": value}))
            self.assertIn("OffValue", str(e.exception))

    def test_cc_off_value_reads_back(self):
        from lib.binaryUnpacker import unpack_command
        for written, read in (("", ""), ("128", ""), ("0", "0"), ("64", "64")):
            raw = bytes(self.pack_one(**cc(**{"OffValue_(CC)": written})))
            self.assertEqual(unpack_command(raw)["OffValue_(CC)"], read, written)

    def test_channel(self):
        self.assertEqual(self.pack_one(**cc(**{"Channel_(PC/CC/Note/PB)": ""}))[0] & 0x0F, 0)
        self.assertEqual(self.pack_one(**cc(**{"Channel_(PC/CC/Note/PB)": "16"}))[0] & 0x0F, 15)
        for value in ("0", "17", "two"):
            with self.assertRaises(ValueError, msg=value):
                self.pack_one(**cc(**{"Channel_(PC/CC/Note/PB)": value}))

    def test_missing_columns_read_empty(self):
        self.assertEqual(self.pack_one(CommandType="cc", **{"Number_(PC/CC/Note)": "7"}),
                         [cbp.CMD_CC_NIBBLE, 7, 0, 128])

    def test_sysex_number(self):
        sysex = {"CommandType": "SysEx"}
        self.assertEqual(self.pack_one(**sysex, **{"Number_(PC/CC/Note)": "15"})[1], 15)
        with self.assertRaises(ValueError):
            self.pack_one(**sysex, **{"Number_(PC/CC/Note)": "16"})


class GlobalSettingsTest(unittest.TestCase):
    def test_empty_midi_channel_is_1(self):
        self.assertEqual(packer.pack_config(set_global(demo(), MIDI_Channel=""))[0], 0)

    def test_bad_midi_channel(self):
        for value in ("0", "17", "x"):
            with self.assertRaises(ValueError) as e:
                packer.pack_config(set_global(demo(), MIDI_Channel=value))
            self.assertIn("MIDI_Channel must be 1-16", str(e.exception))

    def test_empty_realtime_passthrough_is_off(self):
        self.assertEqual(packer.pack_config(set_global(demo(), RealTime_Passthrough=""))[1], 0)

    def test_missing_required_settings(self):
        sections = demo()
        g = sections["Global_Settings"]
        sections["Global_Settings"] = g[~g["Label"].isin(["MIDI_Channel", "RealTime_Passthrough"])]
        packed = packer.pack_config(sections)
        self.assertEqual(list(packed[0:2]), [0, 0])

    def test_remote_mode_no_is_off(self):
        for text in ("No", "None", "N"):
            self.assertEqual(packer.pack_config(set_global(demo(), Remote_Mode=text))[38], 0, text)

    def test_channels_out_of_range(self):
        for label in ("Remote_Channel", "Global_Channel"):
            with self.assertRaises(ValueError) as e:
                packer.pack_config(set_global(demo(), **{label: "17"}))
            self.assertIn(label, str(e.exception))

    def test_exp_cc(self):
        with self.assertRaises(ValueError):
            packer.pack_config(set_global(demo(), Exp1_CC="200"))


if __name__ == "__main__":
    unittest.main()
