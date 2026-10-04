"""The expression pedals: calibration, per bank settings, outputs and the Exp command."""

import os
import re
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# roundtrip_support also puts python/ on the path, for lib
from roundtrip_support import DEMO_CSV, FIRMWARE  # noqa: E402
import lib.binaryUnpacker as unpacker  # noqa: E402
import lib.cmdBinaryPacker as cbp  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
import lib.configPacker as packer  # noqa: E402
import lib.flashLayout as layout  # noqa: E402


class BankExpressionTest(unittest.TestCase):
    """Expression pedal CC and channel per bank (firmware 0.28)."""

    def setUp(self):
        self.sections = read_config_csv(DEMO_CSV)

    def region(self, packed, bank):
        base = layout.BANK_EXP_OFFSET + bank * layout.BANK_EXP_STRIDE
        return list(packed[base : base + layout.BANK_EXP_STRIDE])

    def test_demo_bytes(self):
        packed = packer.pack_config(self.sections)
        self.assertEqual(len(packed), layout.CONFIG_SIZE)
        self.assertEqual(self.region(packed, 2), [1, 0xFF, 0xFF, 0xFF])      # FX: pedal 1 on CC 1
        self.assertEqual(self.region(packed, 7), [0x80, 0xFF, 7, 2])        # KNOB: off, CC 7 ch 2
        self.assertEqual(self.region(packed, 0), [0xFF] * 4)                # HOME: defaults

    def test_round_trip(self):
        packed = packer.pack_config(self.sections)
        df = unpacker.unpack_bank_expression_settings(packed).set_index("Bank_Number")
        self.assertEqual(list(df.loc["7"]), ["Off", "", "", "", "7", "2", "40", ""])
        self.assertEqual(list(df.loc["2"]), ["1", "", "20", "100", "", "", "", ""])
        self.assertEqual(list(df.loc["0"]), [""] * 8)
        again = packer.pack_config({**self.sections, packer.BANK_EXPRESSION_SECTION: df.reset_index()})
        self.assertEqual(again, packed)

    def test_speed(self):
        df = unpacker.unpack_bank_expression_settings(packer.pack_config(self.sections))
        df.loc[3, "Exp1_CC"] = "speed"
        df.loc[3, "Exp2_CC"] = "Speed"
        packed = packer.pack_config({**self.sections, packer.BANK_EXPRESSION_SECTION: df})
        self.assertEqual(self.region(packed, 3)[0::2], [0x82, 0x82])
        back = unpacker.unpack_bank_expression_settings(packed)
        self.assertEqual(list(back.loc[3, ["Exp1_CC", "Exp2_CC"]]), ["Speed", "Speed"])

    def test_scroll(self):
        df = unpacker.unpack_bank_expression_settings(packer.pack_config(self.sections))
        df.loc[3, "Exp1_CC"] = "wheel"
        df.loc[3, "Exp2_CC"] = "Arrows"
        packed = packer.pack_config({**self.sections, packer.BANK_EXPRESSION_SECTION: df})
        self.assertEqual(self.region(packed, 3)[0::2], [0x84, 0x85])
        back = unpacker.unpack_bank_expression_settings(packed)
        self.assertEqual(list(back.loc[3, ["Exp1_CC", "Exp2_CC"]]), ["Wheel", "Arrows"])

    def test_missing_section_keeps_pedals_as_they_are(self):
        sections = {k: v for k, v in self.sections.items() if k != packer.BANK_EXPRESSION_SECTION}
        packed = packer.pack_config(sections)
        self.assertEqual(set(packed[layout.BANK_EXP_OFFSET : layout.CYCLE_LABELS_OFFSET]), {0xFF})

    def test_cell_values(self):
        cc, ch = packer.bank_exp_cc_byte, packer.bank_exp_channel_byte
        self.assertEqual([cc(v) for v in ("", "Default", "off", "0", "127", "200", "x", None)],
                         [0xFF, 0xFF, 0x80, 0, 127, 127, 0xFF, 0xFF])
        self.assertEqual([ch(v) for v in ("", "Default", "1", "16", "0", "17", "x")],
                         [0xFF, 0xFF, 1, 16, 0xFF, 0xFF, 0xFF])

    def test_older_image_reads_defaults(self):
        """An image written before 0.28 has erased flash where these bytes go."""
        image = bytearray(packer.pack_config(self.sections))
        image[layout.BANK_EXP_OFFSET :] = b"\xff" * (len(image) - layout.BANK_EXP_OFFSET)
        df = unpacker.unpack_bank_expression_settings(bytes(image))
        self.assertTrue((df[["Exp1_CC", "Exp1_Channel", "Exp2_CC", "Exp2_Channel"]] == "").all().all())

    def test_fits_the_slot(self):
        self.assertLessEqual(layout.CONFIG_SIZE, 12 * 2048)

    def test_copy_paste_bank_takes_it(self):
        from lib import bankClipboard

        s = self.sections
        exp = s[packer.BANK_EXPRESSION_SECTION]
        clip = bankClipboard.copy_bank(s["Button_Settings"], s.get(packer.LONG_PRESS_SECTION),
                                       s.get(packer.BANK_ENTER_SECTION), 7, df_bank_exp=exp)
        pasted = bankClipboard.paste_bank_expression(exp, clip, 9)
        packed = packer.pack_config({**s, packer.BANK_EXPRESSION_SECTION: pasted})
        self.assertEqual(self.region(packed, 9), [0x80, 0xFF, 7, 2])
        self.assertEqual(self.region(packed, 7), [0x80, 0xFF, 7, 2])

class ExpressionRangeTest(unittest.TestCase):
    """Output range of the expression pedals, per pedal and per bank (firmware 0.33)."""

    def setUp(self):
        self.sections = read_config_csv(DEMO_CSV)

    def pedal_bytes(self, packed, pedal):
        base = layout.EXP_OFFSET + pedal * layout.EXP_STRIDE
        return list(packed[base + 11 : base + 13])

    def bank_range(self, packed, bank):
        base = layout.BANK_EXP_RANGE_OFFSET + bank * layout.BANK_EXP_RANGE_STRIDE
        return list(packed[base : base + layout.BANK_EXP_RANGE_STRIDE])

    def test_pedal_defaults_to_full_range(self):
        packed = packer.pack_config(self.sections)
        self.assertEqual(self.pedal_bytes(packed, 0), [0, 127])
        exp = unpacker.unpack_config(packed)[4]
        self.assertEqual([exp.at[0, "Out_Min"], exp.at[0, "Out_Max"]], ["0", "127"])

    def test_pedal_range_round_trip(self):
        from lib.configPacker import empty_expression_settings

        df = empty_expression_settings()
        df.loc[0, ["Out_Min", "Out_Max"]] = ["40", "127"]
        df.loc[1, ["Out_Min", "Out_Max"]] = ["100", "10"]     # turned round
        packed = packer.pack_config({**self.sections, packer.EXPRESSION_SECTION: df})
        self.assertEqual(self.pedal_bytes(packed, 0), [40, 127])
        self.assertEqual(self.pedal_bytes(packed, 1), [100, 10])
        exp = unpacker.unpack_config(packed)[4]
        self.assertEqual(list(exp["Out_Min"]), ["40", "100"])
        self.assertEqual(list(exp["Out_Max"]), ["127", "10"])
        # Nothing else in the record moves: no auto-engage, default delay
        base = layout.EXP_OFFSET
        self.assertEqual(list(packed[base + 13 : base + 16]), [0, 50, 0])

    def test_older_records_have_the_full_range(self):
        """Older tools wrote zeros after byte 10, blank flash is 0xFF."""
        packed = bytearray(packer.pack_config(self.sections))
        base = layout.EXP_OFFSET
        packed[base + 11 : base + 13] = b"\x00\x00"
        packed[base + 16 + 11 : base + 16 + 13] = b"\xff\xff"
        exp = unpacker.unpack_config(bytes(packed))[4]
        self.assertEqual(list(exp["Out_Min"]), ["0", "0"])
        self.assertEqual(list(exp["Out_Max"]), ["127", "127"])

    def test_csv_without_the_columns(self):
        df = self.sections[packer.EXPRESSION_SECTION].drop(columns=["Out_Min", "Out_Max"])
        packed = packer.pack_config({**self.sections, packer.EXPRESSION_SECTION: df})
        self.assertEqual(self.pedal_bytes(packed, 1), [0, 127])

    def test_bank_range_bytes(self):
        packed = packer.pack_config(self.sections)
        self.assertEqual(self.bank_range(packed, 2), [20, 100, 0xFF, 0xFF])
        self.assertEqual(self.bank_range(packed, 7), [0xFF, 0xFF, 40, 0xFF])
        self.assertEqual(self.bank_range(packed, 0), [0xFF] * 4)
        # The CC and channel table in front of it does not move
        base = layout.BANK_EXP_OFFSET + 7 * layout.BANK_EXP_STRIDE
        self.assertEqual(list(packed[base : base + 4]), [0x80, 0xFF, 7, 2])

    def test_bank_csv_without_the_columns(self):
        df = self.sections[packer.BANK_EXPRESSION_SECTION].drop(
            columns=["Exp1_Min", "Exp1_Max", "Exp2_Min", "Exp2_Max"])
        packed = packer.pack_config({**self.sections, packer.BANK_EXPRESSION_SECTION: df})
        self.assertEqual(set(packed[layout.BANK_EXP_RANGE_OFFSET : layout.CYCLE_LABELS_OFFSET]), {0xFF})

    def test_range_values(self):
        r = packer.bank_exp_range_byte
        self.assertEqual([r(v) for v in ("", "Default", None, "0", "127", "200", "-3", "x")],
                         [0xFF, 0xFF, 0xFF, 0, 127, 127, 0, 0xFF])

    def test_image_read_from_older_firmware(self):
        """A dump that stops before the range table decodes as the pedal's own range."""
        packed = packer.pack_config(self.sections)[: layout.BANK_EXP_RANGE_OFFSET]
        df = unpacker.unpack_bank_expression_settings(packed)
        self.assertTrue((df[["Exp1_Min", "Exp1_Max", "Exp2_Min", "Exp2_Max"]] == "").all().all())

class AutoEngageTest(unittest.TestCase):
    """Auto-engage from the expression pedal, bytes 13 and 14 of its record (firmware 0.41)."""

    def setUp(self):
        self.sections = read_config_csv(DEMO_CSV)

    def auto_bytes(self, packed, pedal):
        base = layout.EXP_OFFSET + pedal * layout.EXP_STRIDE
        return list(packed[base + 13 : base + 15])

    def test_demo(self):
        packed = packer.pack_config(self.sections)
        # Pedal 1 switches D (index 7, stored + 1) and waits 600 ms; pedal 2 has none
        self.assertEqual(self.auto_bytes(packed, 0), [8, 60])
        self.assertEqual(self.auto_bytes(packed, 1), [0, 50])
        exp = unpacker.unpack_config(packed)[4]
        self.assertEqual(list(exp["Auto_Button"]), ["D", "None"])
        self.assertEqual(list(exp["Auto_Off_ms"]), ["600", "500"])

    def test_every_button_and_the_delay_limits(self):
        from lib.configPacker import empty_expression_settings

        for idx, name in enumerate(layout.EXP_BUTTON_IDS):
            df = empty_expression_settings()
            df.loc[0, ["Auto_Button", "Auto_Off_ms"]] = [name, "5"]
            df.loc[1, ["Auto_Button", "Auto_Off_ms"]] = ["None", "99999"]
            packed = packer.pack_config({**self.sections, packer.EXPRESSION_SECTION: df})
            self.assertEqual(self.auto_bytes(packed, 0), [idx + 1, 1])
            self.assertEqual(self.auto_bytes(packed, 1), [0, 254])
            exp = unpacker.unpack_config(packed)[4]
            self.assertEqual(list(exp["Auto_Button"]), [name, "None"])
            self.assertEqual(list(exp["Auto_Off_ms"]), ["10", "2540"])

    def test_older_records_have_none(self):
        """Older tools wrote zeros after byte 12, blank flash is 0xFF."""
        packed = bytearray(packer.pack_config(self.sections))
        base = layout.EXP_OFFSET
        packed[base + 13 : base + 15] = b"\x00\x00"
        packed[base + 16 + 13 : base + 16 + 15] = b"\xff\xff"
        exp = unpacker.unpack_config(bytes(packed))[4]
        self.assertEqual(list(exp["Auto_Button"]), ["None", "None"])
        self.assertEqual(list(exp["Auto_Off_ms"]), ["500", "500"])

    def test_csv_without_the_columns(self):
        df = self.sections[packer.EXPRESSION_SECTION].drop(columns=["Auto_Button", "Auto_Off_ms"])
        packed = packer.pack_config({**self.sections, packer.EXPRESSION_SECTION: df})
        self.assertEqual(self.auto_bytes(packed, 0), [0, 50])

class SendOnBankTest(unittest.TestCase):
    """Send_On_Bank of each pedal, bits 2 and 3 of global byte 35 beside
    LED_Feedback and Link_Toggles (firmware 0.87)."""

    def setUp(self):
        self.sections = read_config_csv(DEMO_CSV)

    def pack_with(self, one, two):
        df = self.sections[packer.EXPRESSION_SECTION].copy()
        df.loc[0, "Send_On_Bank"] = one
        df.loc[1, "Send_On_Bank"] = two
        return packer.pack_config({**self.sections, packer.EXPRESSION_SECTION: df})

    def test_demo_has_it_off(self):
        packed = packer.pack_config(self.sections)
        self.assertEqual(packed[35] & 0x0C, 0)
        exp = unpacker.unpack_config(packed)[4]
        self.assertEqual(list(exp["Send_On_Bank"]), ["N", "N"])

    def test_both_bits_round_trip_beside_the_others(self):
        for one, two, bits in (("N", "N", 0), ("Y", "N", 4), ("N", "Y", 8), ("Y", "Y", 12)):
            packed = self.pack_with(one, two)
            self.assertEqual(packed[35] & 0x0F, 3 | bits, (one, two))
            exp = unpacker.unpack_config(packed)[4]
            self.assertEqual(list(exp["Send_On_Bank"]), [one, two])
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual((back["LED_Feedback"], back["Link_Toggles"]), ("Y", "Y"))

    def test_erased_byte_and_missing_column_read_off(self):
        image = bytearray(self.pack_with("Y", "Y"))
        image[35] = 0xFF
        self.assertEqual(list(unpacker.unpack_config(bytes(image))[4]["Send_On_Bank"]), ["N", "N"])
        df = self.sections[packer.EXPRESSION_SECTION].drop(columns=["Send_On_Bank"], errors="ignore")
        packed = packer.pack_config({**self.sections, packer.EXPRESSION_SECTION: df})
        self.assertEqual(packed[35] & 0x0C, 0)

    def test_bits_match_firmware(self):
        text = open(os.path.join(FIRMWARE, "Core", "Inc", "midi_defines.h")).read()
        self.assertIn("#define EXP_SEND_ON_BANK(pedal)	(0x04U << (pedal))", text)

class ExpressionOutputTest(unittest.TestCase):
    """Pitch Bend and 14-bit CC from an expression pedal, byte 15 of its record (firmware 0.44)."""

    def setUp(self):
        self.sections = read_config_csv(DEMO_CSV)

    def output_bytes(self, packed):
        return [packed[layout.EXP_OFFSET + i * layout.EXP_STRIDE + 15] for i in range(2)]

    def with_outputs(self, a, b):
        from lib.configPacker import empty_expression_settings

        df = empty_expression_settings()
        df.loc[0, "Output"] = a
        df.loc[1, "Output"] = b
        return packer.pack_config({**self.sections, packer.EXPRESSION_SECTION: df})

    def test_demo(self):
        packed = packer.pack_config(self.sections)
        self.assertEqual(self.output_bytes(packed), [0, 2])
        exp = unpacker.unpack_config(packed)[4]
        self.assertEqual(list(exp["Output"]), ["CC", "CC14"])

    def test_every_kind_round_trips(self):
        for name, code in (("CC", 0), ("PitchBend", 1), ("CC14", 2), ("Speed", 3), ("Wheel", 4),
                           ("Arrows", 5), ("Switches", 6)):
            packed = self.with_outputs(name, "CC")
            self.assertEqual(self.output_bytes(packed), [code, 0])
            exp = unpacker.unpack_config(packed)[4]
            self.assertEqual(list(exp["Output"]), [name, "CC"])

    def test_spellings(self):
        for text, code in (("pitchbend", 1), ("PB", 1), ("Pitch Bend", 1), ("cc14", 2),
                           ("CC 14", 2), ("14-bit", 2), ("", 0), ("cc", 0)):
            self.assertEqual(self.output_bytes(self.with_outputs(text, "CC"))[0], code, text)

    def test_bad_value(self):
        with self.assertRaises(ValueError):
            self.with_outputs("NRPN", "CC")

    def test_older_records_send_cc(self):
        """Older tools wrote a zero in byte 15, blank flash is 0xFF."""
        packed = bytearray(packer.pack_config(self.sections))
        packed[layout.EXP_OFFSET + 15] = 0xFF
        packed[layout.EXP_OFFSET + layout.EXP_STRIDE + 15] = 0
        exp = unpacker.unpack_config(bytes(packed))[4]
        self.assertEqual(list(exp["Output"]), ["CC", "CC"])

    def test_csv_without_the_column(self):
        df = self.sections[packer.EXPRESSION_SECTION].drop(columns=["Output"])
        packed = packer.pack_config({**self.sections, packer.EXPRESSION_SECTION: df})
        self.assertEqual(self.output_bytes(packed), [0, 0])

    def test_firmware_values_match(self):
        import re
        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc",
                            "flash_midi_settings.h")
        with open(path) as handle:
            header = handle.read()
        for name, code in (("CC", 0), ("PITCHBEND", 1), ("CC14", 2), ("SPEED", 3), ("WHEEL", 4),
                           ("ARROWS", 5), ("SWITCHES", 6)):
            m = re.search(rf"#define\s+EXP_OUT_{name}\s+\((\d+)\)", header)
            self.assertEqual(int(m.group(1)), code, name)
            self.assertEqual(packer.EXP_OUTPUTS[name], code)

class SwitchBoxTest(unittest.TestCase):
    """A box of switches on an expression jack, Output Switches (firmware 1.10)."""

    def setUp(self):
        self.sections = read_config_csv(DEMO_CSV)

    def pack(self, **cells):
        from lib.configPacker import empty_expression_settings

        df = empty_expression_settings()
        for col, value in cells.items():
            df.loc[1, col] = value
        return packer.pack_config({**self.sections, packer.EXPRESSION_SECTION: df})

    def record(self, packed):
        at = layout.EXP_OFFSET + layout.EXP_STRIDE
        return packed[at:at + layout.EXP_STRIDE]

    def test_what_the_switches_hold_down(self):
        packed = self.pack(Output="Switches", Box_1="A", Box_2="Up", Box_3="down")
        p = self.record(packed)
        self.assertEqual(p[15], 6)
        self.assertEqual(list(p[7:10]), [4, 9, 8])
        self.assertEqual(p[13], 0)      # no auto-engage
        exp = unpacker.unpack_config(packed)[4]
        row = exp.iloc[1]
        self.assertEqual([row["Box_1"], row["Box_2"], row["Box_3"]], ["A", "Up", "Down"])
        self.assertEqual([row["Toe_Button"], row["Heel_Button"], row["Toe_Level"]], ["None", "None", "120"])

    def test_unused_switches(self):
        p = self.record(self.pack(Output="Switches", Box_1="1"))
        self.assertEqual(list(p[7:10]), [0, 0xFF, 0xFF])

    def test_a_pedal_ignores_the_box(self):
        packed = self.pack(Box_1="A", Toe_Button="B")
        p = self.record(packed)
        self.assertEqual(list(p[7:10]), [5, 0xFF, 120])
        row = unpacker.unpack_config(packed)[4].iloc[1]
        self.assertEqual([row["Toe_Button"], row["Box_1"]], ["B", "None"])

    def test_bad_switch(self):
        with self.assertRaises(ValueError):
            self.pack(Output="Switches", Box_2="E")

    def test_firmware_ids_match(self):
        """Down and Up are the virtual pedal's switches 8 and 9."""
        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc",
                            "switch_router.h")
        with open(path) as handle:
            header = handle.read()
        for name in ("DOWN", "UP"):
            m = re.search(rf"#define\s+SW_VIRTUAL_BANK_{name}\s+\((\d+)\)", header)
            self.assertEqual(layout.BOX_SWITCH_IDS[int(m.group(1))], name.title())

class ExpCommandTest(unittest.TestCase):
    """Exp commands, which point an expression pedal somewhere else."""

    def pack(self, **fields):
        row = pd.Series({"A_CommandType": "Exp", **{f"A_{k}": v for k, v in fields.items()}})
        return cbp.pack_row(row)[:4]

    def test_encoding(self):
        self.assertEqual(self.pack(**{"OnValue_(CC/PB)": "1", "KeyMode_(Key)": "CC",
                                      "Number_(PC/CC/Note)": "7"}), [0x05, 0, 7, 0])
        self.assertEqual(self.pack(**{"OnValue_(CC/PB)": "2", "Number_(PC/CC/Note)": "74",
                                      "Channel_(PC/CC/Note/PB)": "16",
                                      "Toggle_(CC/PB/Note)": "Y"}), [0x05, 0x81, 74, 16])
        self.assertEqual(self.pack(**{"OnValue_(CC/PB)": "2", "KeyMode_(Key)": "Off"}),
                         [0x05, 1, cbp.EXP_TARGET_OFF, 0])
        self.assertEqual(self.pack(**{"KeyMode_(Key)": "Own", "Channel_(PC/CC/Note/PB)": "5"}),
                         [0x05, 0, cbp.EXP_TARGET_OWN, 0])
        self.assertEqual(self.pack(**{"OnValue_(CC/PB)": "2", "KeyMode_(Key)": "speed",
                                      "Channel_(PC/CC/Note/PB)": "5", "Toggle_(CC/PB/Note)": "Y"}),
                         [0x05, 0x81, cbp.EXP_TARGET_SPEED, 0])
        self.assertEqual(self.pack(**{"OnValue_(CC/PB)": "2", "KeyMode_(Key)": "add",
                                      "Number_(PC/CC/Note)": "7", "Channel_(PC/CC/Note/PB)": "5"}),
                         [0x05, 1, cbp.EXP_TARGET_ADD, 0])
        self.assertEqual(self.pack(**{"OnValue_(CC/PB)": "1", "KeyMode_(Key)": "Wheel",
                                      "Channel_(PC/CC/Note/PB)": "5"}),
                         [0x05, 0, cbp.EXP_TARGET_WHEEL, 0])
        self.assertEqual(self.pack(**{"OnValue_(CC/PB)": "1", "KeyMode_(Key)": "arrows",
                                      "Toggle_(CC/PB/Note)": "Y"}),
                         [0x05, 0x80, cbp.EXP_TARGET_ARROWS, 0])

    def test_bad_values(self):
        for fields in ({"OnValue_(CC/PB)": "3", "Number_(PC/CC/Note)": "7"},
                       {"Number_(PC/CC/Note)": ""},
                       {"Number_(PC/CC/Note)": "128"},
                       {"Number_(PC/CC/Note)": "7", "Channel_(PC/CC/Note/PB)": "17"},
                       {"KeyMode_(Key)": "Wah"}):
            with self.assertRaises(ValueError, msg=fields):
                self.pack(**fields)

    def test_round_trip(self):
        for raw in ([0x05, 0, 7, 0], [0x05, 0x81, 74, 16], [0x05, 1, 0x80, 0], [0x05, 0x80, 0x81, 0],
                    [0x05, 0x81, 0x82, 0], [0x05, 0x80, 0x83, 0], [0x05, 0, 0x84, 0],
                    [0x05, 0x81, 0x85, 0]):
            cmd = unpacker.unpack_command(bytes(raw))
            row = pd.Series({f"A_{k}": v for k, v in cmd.items()})
            self.assertEqual(cbp.pack_row(row)[:4], raw, cmd)

    def test_demo(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        at = layout.COMMANDS_OFFSET + (8 * 8 + 5) * layout.BUTTON_STRIDE
        self.assertEqual(packed[at : at + 4], bytes([0x05, 0x81, cbp.EXP_TARGET_OFF, 0]))
        at += layout.BUTTON_STRIDE
        self.assertEqual(packed[at : at + 4], bytes([0x05, 0x80, 7, 0]))

    def test_firmware_values_match(self):
        import re
        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc",
                            "midi_defines.h")
        with open(path) as handle:
            header = handle.read()
        for name, value in (("CMD_EXP_MODE", cbp.CMD_EXP_MODE), ("EXP_TARGET_OFF", cbp.EXP_TARGET_OFF),
                            ("EXP_TARGET_RESET", cbp.EXP_TARGET_OWN),
                            ("EXP_TARGET_SPEED", cbp.EXP_TARGET_SPEED),
                            ("EXP_TARGET_ADD", cbp.EXP_TARGET_ADD),
                            ("EXP_TARGET_WHEEL", cbp.EXP_TARGET_WHEEL),
                            ("EXP_TARGET_ARROWS", cbp.EXP_TARGET_ARROWS)):
            m = re.search(rf"#define\s+{name}\s+\((0x[0-9A-Fa-f]+|\d+)\)", header)
            self.assertEqual(int(m.group(1), 0), value, name)


if __name__ == "__main__":
    unittest.main()
