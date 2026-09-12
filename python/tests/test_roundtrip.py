"""Round-trip test: CSV -> packer bytes -> unpacker -> compare with the CSV.

Run from the repository root:

    python -m unittest python/tests/test_roundtrip.py
"""

import os
import sys
import unittest

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lib.binaryUnpacker as unpacker  # noqa: E402
import lib.cmdBinaryPacker as cbp  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
from lib.configPacker import pack_config  # noqa: E402

SAMPLE_CSV = os.path.join(os.path.dirname(HERE), "MeloConfig_10_Cmds - RC-600.csv")


def pack_csv(path: str) -> bytes:
    """Pack a CSV exactly like CSV_to_Flash.py does."""
    return pack_config(read_config_csv(path))


def norm(value) -> str:
    """Normalise a CSV cell for comparison: NaN/None -> '', '5.0' -> '5'."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).strip()
    if s.lower() == "nan":
        return ""
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
    except ValueError:
        pass
    return s


class RoundTripTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sections = read_config_csv(SAMPLE_CSV)
        cls.packed = pack_csv(SAMPLE_CSV)
        (cls.df_global, cls.df_banks, cls.df_buttons, cls.df_long, cls.df_exp,
         cls.df_enter, cls.df_sysex) = unpacker.unpack_config(
            cls.packed
        )

    def test_size(self):
        self.assertEqual(len(self.packed), unpacker.CONFIG_SIZE)

    def test_global_settings(self):
        expected = self.sections["Global_Settings"].set_index("Label")["Value"]
        got = self.df_global.set_index("Label")["Value"]
        for label in expected.index:
            self.assertEqual(norm(got[label]), norm(expected[label]), label)

    def test_bank_names(self):
        expected = self.sections["Bank_Naming"]
        self.assertEqual(len(self.df_banks), unpacker.NUM_BANKS)
        for (_, exp), (_, got) in zip(expected.iterrows(), self.df_banks.iterrows()):
            self.assertEqual(norm(got["Bank_Number"]), norm(exp["Bank_Number"]))
            self.assertEqual(
                norm(got["Bank_Name_Large"]), norm(exp["Bank_Name_Large"])[:4]
            )
            self.assertEqual(
                norm(got["Bank_Info_Small"]), norm(exp["Bank_Info_Small"])[:8]
            )

    def test_button_settings(self):
        # The sample CSV covers the first banks; the rest pack as empty
        expected = self.sections["Button_Settings"]
        self.assertEqual(len(self.df_buttons), unpacker.NUM_BANKS * 8)
        mismatches = []
        for (_, exp), (_, got) in zip(expected.iterrows(), self.df_buttons.iterrows()):
            key = f"bank {norm(exp['Bank_Number'])} button {exp['Button_Identifier']}"
            self.assertEqual(norm(got["Bank_Number"]), norm(exp["Bank_Number"]))
            self.assertEqual(got["Button_Identifier"], exp["Button_Identifier"])
            self.assertEqual(
                got["Light_Mode"], norm(exp.get("Light_Mode")) or "Normal", key
            )
            for slot in unpacker.SLOT_NAMES:
                ctype = norm(exp[f"{slot}_CommandType"])
                self.assertEqual(got[f"{slot}_CommandType"], ctype, f"{key} {slot}")
                if not ctype:
                    continue
                # Only the fields the packer actually stores for this type
                fields = {
                    "PC": ["Channel_(PC/CC/Note/PB)", "Number_(PC/CC/Note)"],
                    "CC": [
                        "Channel_(PC/CC/Note/PB)",
                        "Number_(PC/CC/Note)",
                        "OnValue_(CC/PB)",
                        "OffValue_(CC)",
                        "Toggle_(CC/PB/Note)",
                    ],
                    "Note": [
                        "Channel_(PC/CC/Note/PB)",
                        "Number_(PC/CC/Note)",
                        "Velocity_(Note)",
                        "Duration_(Note/PB)",
                        "Toggle_(CC/PB/Note)",
                    ],
                    "PB": [
                        "Channel_(PC/CC/Note/PB)",
                        "OnValue_(CC/PB)",
                        "Duration_(Note/PB)",
                        "Toggle_(CC/PB/Note)",
                    ],
                    "Key": ["Number_(PC/CC/Note)", "Duration_(Note/PB)"],
                }.get(ctype, [])
                for f in fields:
                    e, g = norm(exp[f"{slot}_{f}"]), norm(got[f"{slot}_{f}"])
                    if f == "Toggle_(CC/PB/Note)":
                        e = "Y" if "Y" in e else "N"
                    if f.startswith("Duration") or f.startswith("Velocity"):
                        e = e or "0"
                    if ctype == "Key" and f.startswith("Number"):
                        e = e or "0"  # empty modifier mask packs as 0
                    if e != g:
                        mismatches.append(f"{key} {slot}_{f}: csv={e!r} device={g!r}")
                if ctype == "Key":
                    e = norm(exp[f"{slot}_OnValue_(CC/PB)"]).lower()
                    g = norm(got[f"{slot}_OnValue_(CC/PB)"]).lower()
                    if cbp.get_hid_code(e) != cbp.get_hid_code(g):
                        mismatches.append(f"{key} {slot} key: csv={e!r} device={g!r}")
        self.assertEqual(mismatches, [], "\n" + "\n".join(mismatches))

    def test_erased_flash_decodes_as_empty(self):
        blank = bytes([0xFF]) * unpacker.CONFIG_SIZE
        _, _, df, df_long, df_exp, df_enter, df_sysex = unpacker.unpack_config(blank)
        self.assertTrue((df["A_CommandType"] == "").all())
        self.assertTrue((df["Light_Mode"] == "Normal").all())
        self.assertTrue((df["Label"] == "").all())
        self.assertTrue((df_long["A_CommandType"] == "").all())
        self.assertEqual(df_exp["Min_ADC"].tolist(), ["80", "80"])
        self.assertEqual(df_exp["Channel"].tolist(), ["Global", "Global"])

    def test_light_mode_does_not_touch_command_bytes(self):
        """LED modes live in their own table and never set bits in slot A."""
        sections = read_config_csv(SAMPLE_CSV)
        df = sections["Button_Settings"].copy()
        # Force every LED mode onto buttons with different slot A types
        df["Light_Mode"] = ["Reverse", "AlwaysOn"] * (len(df) // 2)
        covered = len(df)  # only the banks the sample CSV defines
        modified = {**sections, "Button_Settings": df}
        packed = pack_config(modified)

        # Command bytes identical to the all-Normal packing
        base = pack_config(sections)
        self.assertEqual(
            packed[: unpacker.LED_MODES_OFFSET], base[: unpacker.LED_MODES_OFFSET]
        )
        # LED table carries the modes
        table = packed[unpacker.LED_MODES_OFFSET : unpacker.LABELS_OFFSET]
        self.assertEqual(list(table[:covered]), [1, 2] * (covered // 2))
        self.assertEqual(set(table[covered:]), {0})  # padded banks are Normal
        # And they come back by name
        _, _, decoded, *_ = unpacker.unpack_config(packed)
        self.assertEqual(decoded["Light_Mode"].tolist()[:covered], df["Light_Mode"].tolist())

    def test_usb_midi_thru_flag(self):
        sections = read_config_csv(SAMPLE_CSV)
        g = sections["Global_Settings"].copy()
        thru_off = pack_config(sections)
        self.assertEqual(thru_off[6], 0)

        g.loc[g["Label"] == "USB_MIDI_Thru", "Value"] = "Y"
        thru_on = pack_config({**sections, "Global_Settings": g})
        self.assertEqual(thru_on[6], 1)
        # Nothing else moves
        self.assertEqual(thru_on[:6] + thru_on[7:], thru_off[:6] + thru_off[7:])

        df_global, *_ = unpacker.unpack_config(thru_on)
        value = df_global.set_index("Label")["Value"]["USB_MIDI_Thru"]
        self.assertEqual(value, "Y")

    def test_remember_state_flag(self):
        sections = read_config_csv(SAMPLE_CSV)
        g = sections["Global_Settings"].copy()
        g.loc[g["Label"] == "Remember_State", "Value"] = "N"
        self.assertEqual(pack_config({**sections, "Global_Settings": g})[7], 0)
        g.loc[g["Label"] == "Remember_State", "Value"] = "Y"
        packed = pack_config({**sections, "Global_Settings": g})
        self.assertEqual(packed[7], 1)
        df_global, *_ = unpacker.unpack_config(packed)
        self.assertEqual(df_global.set_index("Label")["Value"]["Remember_State"], "Y")

    def test_labels_round_trip(self):
        sections = read_config_csv(SAMPLE_CSV)
        df = sections["Button_Settings"].copy()
        labels = [f"L{i:02d}"[:4] for i in range(len(df))]
        labels[0] = "REC"          # short, gets space padded
        labels[1] = "TOOLONG"      # truncated to 4
        labels[2] = ""             # empty
        labels[3] = "cañón"        # non-ASCII replaced
        df["Label"] = labels
        packed = pack_config({**sections, "Button_Settings": df})
        self.assertEqual(len(packed), unpacker.CONFIG_SIZE)
        table = packed[unpacker.LABELS_OFFSET : unpacker.CONFIG_SIZE]
        self.assertEqual(table[:4], b"REC ")
        self.assertEqual(table[4:8], b"TOOL")
        self.assertEqual(table[8:12], b"    ")
        self.assertEqual(table[12:16], b"ca??")
        _, _, decoded, *_ = unpacker.unpack_config(packed)
        self.assertEqual(decoded["Label"].tolist()[:3], ["REC", "TOOL", ""])
        self.assertEqual(decoded["Label"].tolist()[len(df)], "")  # padded bank
        # A config without a Label column packs blank labels
        no_col = df.drop(columns=["Label"])
        packed2 = pack_config({**sections, "Button_Settings": no_col})
        self.assertEqual(set(packed2[unpacker.LABELS_OFFSET : unpacker.LONG_PRESS_OFFSET]), {0x20})

    def test_long_press_round_trip(self):
        from lib.configPacker import empty_long_press_settings

        sections = read_config_csv(SAMPLE_CSV)
        # Without the section every long press slot is empty
        base = pack_config({k: v for k, v in sections.items() if k != "LongPress_Settings"})
        self.assertEqual(len(base), unpacker.CONFIG_SIZE)
        self.assertEqual(set(base[unpacker.LONG_PRESS_OFFSET : unpacker.EXP_OFFSET]), {0})

        df_long = empty_long_press_settings()
        # Bank 0 button 4 (index 3): long press sends CC 20 = 127/0 momentary on ch 5
        i = 3
        df_long.at[i, "A_CommandType"] = "CC"
        df_long.at[i, "A_Channel_(PC/CC/Note/PB)"] = "5"
        df_long.at[i, "A_Number_(PC/CC/Note)"] = "20"
        df_long.at[i, "A_OnValue_(CC/PB)"] = "127"
        df_long.at[i, "A_OffValue_(CC)"] = "0"
        # Bank 7 button D (index 63): long press sends PC 9 on ch 1 as toggle-less PC
        df_long.at[63, "B_CommandType"] = "PC"
        df_long.at[63, "B_Channel_(PC/CC/Note/PB)"] = "1"
        df_long.at[63, "B_Number_(PC/CC/Note)"] = "9"
        packed = pack_config({**sections, "LongPress_Settings": df_long})
        off = unpacker.LONG_PRESS_OFFSET + 3 * unpacker.BUTTON_STRIDE
        self.assertEqual(list(packed[off : off + 4]), [0xB4, 20, 127, 0])
        off = unpacker.LONG_PRESS_OFFSET + 63 * unpacker.BUTTON_STRIDE + 4
        self.assertEqual(list(packed[off : off + 4]), [0xC0, 9, 0x80, 0])
        # Short press commands untouched
        self.assertEqual(packed[: unpacker.LONG_PRESS_OFFSET], base[: unpacker.LONG_PRESS_OFFSET])

        _, _, _, decoded, *_ = unpacker.unpack_config(packed)
        self.assertEqual(decoded.at[3, "A_CommandType"], "CC")
        self.assertEqual(decoded.at[3, "A_Number_(PC/CC/Note)"], "20")
        self.assertEqual(decoded.at[63, "B_CommandType"], "PC")
        self.assertEqual(decoded.at[62, "A_CommandType"], "")

    def test_long_press_threshold(self):
        sections = read_config_csv(SAMPLE_CSV)
        g = sections["Global_Settings"].copy()
        g.loc[g["Label"] == "Long_Press_ms", "Value"] = "750"
        packed = pack_config({**sections, "Global_Settings": g})
        self.assertEqual(packed[8], 75)
        df_global, *_ = unpacker.unpack_config(packed)
        self.assertEqual(df_global.set_index("Label")["Value"]["Long_Press_ms"], "750")

    def test_expression_settings_round_trip(self):
        from lib.configPacker import empty_expression_settings

        sections = read_config_csv(SAMPLE_CSV)
        # Missing section -> defaults
        base = pack_config({k: v for k, v in sections.items() if k != "Expression_Settings"})
        self.assertEqual(len(base), unpacker.CONFIG_SIZE)
        rec = base[unpacker.EXP_OFFSET : unpacker.EXP_OFFSET + 7]
        self.assertEqual(list(rec), [80, 0, 3900 & 0xFF, 3900 >> 8, 0, 0, 0])

        df = empty_expression_settings()
        df.loc[0, ["Min_ADC", "Max_ADC", "Curve", "Invert", "Channel"]] = ["150", "3800", "Log", "Y", "7"]
        df.loc[1, ["Min_ADC", "Max_ADC", "Curve", "Invert", "Channel"]] = ["0", "4095", "Exp", "N", "Global"]
        packed = pack_config({**sections, "Expression_Settings": df})
        r0 = packed[unpacker.EXP_OFFSET : unpacker.EXP_OFFSET + 7]
        r1 = packed[unpacker.EXP_OFFSET + 16 : unpacker.EXP_OFFSET + 23]
        self.assertEqual(list(r0), [150, 0, 3800 & 0xFF, 3800 >> 8, 1, 1, 7])
        self.assertEqual(list(r1), [0, 0, 0xFF, 0x0F, 2, 0, 0])
        decoded = unpacker.unpack_config(packed)[4]
        self.assertEqual(decoded.iloc[0].tolist(), ["1", "150", "3800", "Log", "Y", "7"])
        self.assertEqual(decoded.iloc[1].tolist(), ["2", "0", "4095", "Exp", "N", "Global"])

    def test_led_brightness(self):
        sections = read_config_csv(SAMPLE_CSV)
        g = sections["Global_Settings"].copy()
        # Sample defaults to 100 %
        base = pack_config(sections)
        self.assertEqual((base[9], base[10]), (100, 100))
        # Missing rows also default to 100
        g2 = g[~g["Label"].isin(["LED_Brightness", "LED_Rest_Brightness"])]
        self.assertEqual(pack_config({**sections, "Global_Settings": g2})[9:11], b"dd")
        g.loc[g["Label"] == "LED_Brightness", "Value"] = "30"
        g.loc[g["Label"] == "LED_Rest_Brightness", "Value"] = "250"  # clamped
        packed = pack_config({**sections, "Global_Settings": g})
        self.assertEqual((packed[9], packed[10]), (30, 100))
        # 0 is never written: the firmware reads it as "not set" (old configs)
        g.loc[g["Label"] == "LED_Rest_Brightness", "Value"] = "0"
        self.assertEqual(pack_config({**sections, "Global_Settings": g})[10], 1)
        # And an old config with zeroed bytes decodes as the 100 % default
        old = bytearray(base); old[9] = old[10] = 0
        df_old = unpacker.unpack_config(bytes(old))[0].set_index("Label")["Value"]
        self.assertEqual(df_old["LED_Brightness"], "100")
        df_global = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
        self.assertEqual((df_global["LED_Brightness"], df_global["LED_Rest_Brightness"]), ("30", "100"))

    def test_media_command(self):
        row = pd.Series({
            "A_CommandType": "Media", "A_OnValue_(CC/PB)": "play_pause",
            "A_Duration_(Note/PB)": "", "A_Toggle_(CC/PB/Note)": "N",
            "B_CommandType": "Media", "B_OnValue_(CC/PB)": "vol_up",
            "B_Duration_(Note/PB)": "5", "B_Toggle_(CC/PB/Note)": "Y",
            "C_CommandType": "Media", "C_OnValue_(CC/PB)": "0x0E9",   # raw usage
            "C_Duration_(Note/PB)": "", "C_Toggle_(CC/PB/Note)": "N",
        })
        packed = cbp.pack_row(row)
        self.assertEqual(packed[0:4], [0x30, 0xCD, 0x00, 0x00])
        self.assertEqual(packed[4:8], [0x30, 0xE9, 0x00, 0x85])
        self.assertEqual(packed[8:12], [0x30, 0xE9, 0x00, 0x00])
        a = unpacker.unpack_command(bytes(packed[0:4]))
        b = unpacker.unpack_command(bytes(packed[4:8]))
        self.assertEqual((a["CommandType"], a["OnValue_(CC/PB)"], a["Toggle_(CC/PB/Note)"]), ("Media", "play_pause", "N"))
        self.assertEqual((b["OnValue_(CC/PB)"], b["Duration_(Note/PB)"], b["Toggle_(CC/PB/Note)"]), ("vol_up", "5", "Y"))
        # The toggle bit of a media command lives in byte 3, never in the usage byte
        self.assertTrue(cbp.MEDIA_KEYS["play_pause"] & 0x80)

    def test_bank_command(self):
        row = pd.Series({
            "A_CommandType": "Bank", "A_OnValue_(CC/PB)": "17", "A_KeyMode_(Key)": "GoTo",
            "B_CommandType": "Bank", "B_OnValue_(CC/PB)": "4", "B_KeyMode_(Key)": "Up",
            "C_CommandType": "Bank", "C_OnValue_(CC/PB)": "4", "C_KeyMode_(Key)": "Down",
            "D_CommandType": "Bank", "D_OnValue_(CC/PB)": "99", "D_KeyMode_(Key)": "GoTo",
        })
        p = cbp.pack_row(row)
        self.assertEqual(p[0:4], [0x40, 17, 0, 0])   # go to bank 17
        self.assertEqual(p[4:8], [0x41, 4, 0, 0])    # up 4
        self.assertEqual(p[8:12], [0x42, 4, 0, 0])   # down 4
        self.assertEqual(p[12:16], [0x40, 31, 0, 0]) # clamped to the last bank
        d = unpacker.unpack_command(bytes(p[0:4]))
        self.assertEqual((d["CommandType"], d["KeyMode_(Key)"], d["OnValue_(CC/PB)"]), ("Bank", "GoTo", "17"))
        d = unpacker.unpack_command(bytes(p[4:8]))
        self.assertEqual((d["KeyMode_(Key)"], d["OnValue_(CC/PB)"]), ("Up", "4"))

    def test_bank_jump_step(self):
        sections = read_config_csv(SAMPLE_CSV)
        g = sections["Global_Settings"].copy()
        self.assertEqual(pack_config(sections)[11], 8)  # default
        g.loc[g["Label"] == "Bank_Jump_Step", "Value"] = "4"
        packed = pack_config({**sections, "Global_Settings": g})
        self.assertEqual(packed[11], 4)
        df = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
        self.assertEqual(df["Bank_Jump_Step"], "4")

    def test_fits_in_the_flash_pages(self):
        from CSV_to_Flash import ALLOWED_NUM_FLASH_PAGES, FLASH_PAGE_SIZE

        self.assertLessEqual(unpacker.CONFIG_SIZE, ALLOWED_NUM_FLASH_PAGES * FLASH_PAGE_SIZE)

    def test_bank_enter_commands(self):
        from lib.configPacker import empty_bank_enter_settings

        sections = read_config_csv(SAMPLE_CSV)
        # Without the section every bank's enter list is empty
        base = pack_config({k: v for k, v in sections.items() if k != "BankEnter_Settings"})
        self.assertEqual(len(base), unpacker.CONFIG_SIZE)
        self.assertEqual(set(base[unpacker.BANK_ENTER_OFFSET :]), {0})

        df = empty_bank_enter_settings()
        df.loc[3, ["A_CommandType", "A_Channel_(PC/CC/Note/PB)", "A_Number_(PC/CC/Note)"]] = ["PC", "2", "7"]
        packed = pack_config({**sections, "BankEnter_Settings": df})
        off = unpacker.BANK_ENTER_OFFSET + 3 * unpacker.BUTTON_STRIDE
        self.assertEqual(list(packed[off : off + 4]), [0xC1, 7, 0x80, 0])
        # Nothing before the section moved
        self.assertEqual(packed[: unpacker.BANK_ENTER_OFFSET], base[: unpacker.BANK_ENTER_OFFSET])
        decoded = unpacker.unpack_config(packed)[5]
        self.assertEqual(len(decoded), unpacker.NUM_BANKS)
        self.assertEqual(decoded.at[3, "A_CommandType"], "PC")
        self.assertEqual(decoded.at[2, "A_CommandType"], "")

    def test_bank_change_from_midi(self):
        sections = read_config_csv(SAMPLE_CSV)
        g = sections["Global_Settings"].copy()
        self.assertEqual(tuple(pack_config(sections)[12:15]), (0, 0, 0))  # off by default
        for label, value in (("Bank_Change_Mode", "CC"), ("Bank_Change_Channel", "3"), ("Bank_Change_CC", "32")):
            g.loc[g["Label"] == label, "Value"] = value
        packed = pack_config({**sections, "Global_Settings": g})
        self.assertEqual(tuple(packed[12:15]), (2, 3, 32))
        df = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
        self.assertEqual((df["Bank_Change_Mode"], df["Bank_Change_Channel"], df["Bank_Change_CC"]), ("CC", "3", "32"))
        # "Any" channel and PC mode
        g.loc[g["Label"] == "Bank_Change_Mode", "Value"] = "PC"
        g.loc[g["Label"] == "Bank_Change_Channel", "Value"] = "Any"
        packed = pack_config({**sections, "Global_Settings": g})
        self.assertEqual(tuple(packed[12:14]), (1, 0))
        df = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
        self.assertEqual(df["Bank_Change_Channel"], "Any")

    def test_ccinc_command(self):
        row = pd.Series({
            "A_CommandType": "CCInc", "A_Channel_(PC/CC/Note/PB)": "3",
            "A_Number_(PC/CC/Note)": "7", "A_OnValue_(CC/PB)": "64",
            "A_OffValue_(CC)": "5", "A_KeyMode_(Key)": "Up",
            "A_Toggle_(CC/PB/Note)": "N",
            "B_CommandType": "CCInc", "B_Channel_(PC/CC/Note/PB)": "3",
            "B_Number_(PC/CC/Note)": "7", "B_OnValue_(CC/PB)": "64",
            "B_OffValue_(CC)": "5", "B_KeyMode_(Key)": "Down",
            "B_Toggle_(CC/PB/Note)": "Y",
        })
        p = cbp.pack_row(row)
        self.assertEqual(p[0:4], [0x52, 7, 5, 64])          # up, no wrap
        self.assertEqual(p[4:8], [0x52, 7 | 0x80, 5, 0xC0])  # down, wrap, start 64
        d = unpacker.unpack_command(bytes(p[0:4]))
        self.assertEqual(
            (d["CommandType"], d["Number_(PC/CC/Note)"], d["OffValue_(CC)"],
             d["OnValue_(CC/PB)"], d["KeyMode_(Key)"], d["Toggle_(CC/PB/Note)"]),
            ("CCInc", "7", "5", "64", "Up", "N"))
        d = unpacker.unpack_command(bytes(p[4:8]))
        self.assertEqual((d["KeyMode_(Key)"], d["Toggle_(CC/PB/Note)"]), ("Down", "Y"))

    def test_sysex_strings(self):
        from lib.configPacker import empty_sysex_strings, parse_sysex_bytes

        # Parsing: hex, optional 0x, F0/F7 stripped, junk rejected
        self.assertEqual(parse_sysex_bytes("F0 41 10 42 12 F7"), bytes([0x41, 0x10, 0x42, 0x12]))
        self.assertEqual(parse_sysex_bytes("0x41 0x10"), bytes([0x41, 0x10]))
        self.assertEqual(parse_sysex_bytes("FF 01"), b"")   # not 7-bit
        self.assertEqual(parse_sysex_bytes("zz"), b"")
        self.assertEqual(parse_sysex_bytes(""), b"")

        sections = read_config_csv(SAMPLE_CSV)
        df = empty_sysex_strings()
        df.loc[0, "Bytes"] = "F0 41 10 42 12 00 7F F7"
        df.loc[3, "Bytes"] = "7E 7F 06 01"
        packed = pack_config({**sections, "SysEx_Strings": df})
        self.assertEqual(len(packed), unpacker.CONFIG_SIZE)
        e0 = packed[unpacker.SYSEX_OFFSET : unpacker.SYSEX_OFFSET + 8]
        self.assertEqual(list(e0), [6, 0x41, 0x10, 0x42, 0x12, 0x00, 0x7F, 0])
        e3 = packed[unpacker.SYSEX_OFFSET + 3 * unpacker.SYSEX_STRING_STRIDE :][:5]
        self.assertEqual(list(e3), [4, 0x7E, 0x7F, 0x06, 0x01])
        table = unpacker.unpack_config(packed)[6]
        self.assertEqual(table.at[0, "Bytes"], "41 10 42 12 00 7F")
        self.assertEqual(table.at[1, "Bytes"], "")

        # A SysEx command just references a table entry
        row = pd.Series({"A_CommandType": "SysEx", "A_Number_(PC/CC/Note)": "3"})
        self.assertEqual(cbp.pack_row(row)[0:4], [0x60, 3, 0, 0])
        d = unpacker.unpack_command(bytes([0x60, 3, 0, 0]))
        self.assertEqual((d["CommandType"], d["Number_(PC/CC/Note)"]), ("SysEx", "3"))

    def test_cc_alwayson_keeps_off_value(self):
        """Regression: AlwaysOn used to set bit 7 of the CC off value."""
        row = pd.Series(
            {
                "A_CommandType": "CC",
                "A_Channel_(PC/CC/Note/PB)": "5",
                "A_Number_(PC/CC/Note)": "5",
                "A_OnValue_(CC/PB)": "127",
                "A_OffValue_(CC)": "0",
                "A_Toggle_(CC/PB/Note)": "Y",
                "Light_Mode": "AlwaysOn",
            }
        )
        cmd_a = cbp.pack_row(row)[:4]
        self.assertEqual(cmd_a, [0xB0 | 4, 0x80 | 5, 127, 0])


if __name__ == "__main__":
    unittest.main()
