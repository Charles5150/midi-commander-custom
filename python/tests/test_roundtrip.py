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
import lib.configPacker as packer  # noqa: E402
from lib.configPacker import pack_config  # noqa: E402

SAMPLE_CSV = os.path.join(os.path.dirname(HERE), "MeloConfig_10_Cmds - RC-600.csv")
DEMO_CSV = os.path.join(os.path.dirname(HERE), "demo-all-features.csv")


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
         cls.df_enter, cls.df_sysex, cls.df_bank_switch, cls.df_setlist) = unpacker.unpack_config(
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
        _, _, df, df_long, df_exp, df_enter, df_sysex, *_ = unpacker.unpack_config(blank)
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
        # 0xFF in byte 3: no Bank Select configured, so none is sent
        self.assertEqual(list(packed[off : off + 4]), [0xC0, 9, 0x80, 0xFF])
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
        r0 = packed[unpacker.EXP_OFFSET : unpacker.EXP_OFFSET + 11]
        r1 = packed[unpacker.EXP_OFFSET + 16 : unpacker.EXP_OFFSET + 27]
        self.assertEqual(list(r0), [150, 0, 3800 & 0xFF, 3800 >> 8, 1, 1, 7, 0xFF, 0xFF, 120, 7])
        self.assertEqual(list(r1), [0, 0, 0xFF, 0x0F, 2, 0, 0, 0xFF, 0xFF, 120, 7])
        decoded = unpacker.unpack_config(packed)[4]
        self.assertEqual(decoded.iloc[0]["Min_ADC"], "150")
        self.assertEqual(decoded.iloc[0]["Toe_Button"], "None")
        self.assertEqual(decoded.iloc[1]["Channel"], "Global")

    def test_expression_as_switch(self):
        from lib.configPacker import empty_expression_settings

        sections = read_config_csv(SAMPLE_CSV)
        df = empty_expression_settings()
        df.loc[0, ["Toe_Button", "Toe_Level", "Heel_Button", "Heel_Level"]] = ["C", "110", "1", "5"]
        packed = pack_config({**sections, "Expression_Settings": df})
        rec = packed[unpacker.EXP_OFFSET : unpacker.EXP_OFFSET + 11]
        self.assertEqual(list(rec[7:11]), [6, 0, 110, 5])   # C is index 6, button 1 is index 0
        decoded = unpacker.unpack_config(packed)[4]
        self.assertEqual(
            [decoded.at[0, k] for k in ("Toe_Button", "Toe_Level", "Heel_Button", "Heel_Level")],
            ["C", "110", "1", "5"])
        # An unknown or absent button disables that direction
        df.loc[0, "Toe_Button"] = "Z"
        packed = pack_config({**sections, "Expression_Settings": df})
        self.assertEqual(packed[unpacker.EXP_OFFSET + 7], 0xFF)

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
        self.assertEqual(set(base[unpacker.BANK_ENTER_OFFSET : unpacker.SETLIST_OFFSET]), {0})
        # The setlist is the one section whose empty value is 0xFF: 0 is a valid bank
        self.assertEqual(set(base[unpacker.SETLIST_OFFSET :]), {0xFF})

        df = empty_bank_enter_settings()
        df.loc[3, ["A_CommandType", "A_Channel_(PC/CC/Note/PB)", "A_Number_(PC/CC/Note)"]] = ["PC", "2", "7"]
        packed = pack_config({**sections, "BankEnter_Settings": df})
        off = unpacker.BANK_ENTER_OFFSET + 3 * unpacker.BUTTON_STRIDE
        # 0xFF in byte 3: no Bank Select configured, so none is sent
        self.assertEqual(list(packed[off : off + 4]), [0xC1, 7, 0x80, 0xFF])
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

    def test_tap_command(self):
        row = pd.Series({
            "A_CommandType": "Tap", "A_KeyMode_(Key)": "Tap",
            "B_CommandType": "Tap", "B_KeyMode_(Key)": "Clock",
        })
        p = cbp.pack_row(row)
        self.assertEqual(p[0:4], [0x70, 0, 0, 0])
        self.assertEqual(p[4:8], [0x71, 0, 0, 0])
        a = unpacker.unpack_command(bytes(p[0:4]))
        b = unpacker.unpack_command(bytes(p[4:8]))
        self.assertEqual((a["CommandType"], a["KeyMode_(Key)"]), ("Tap", "Tap"))
        self.assertEqual((b["CommandType"], b["KeyMode_(Key)"]), ("Tap", "Clock"))

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
        self.assertEqual(len(packed), unpacker.CONFIG_SIZE)
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


class FirmwareLayoutTest(unittest.TestCase):
    """The Python offsets must match the CFG_* macros the firmware uses.

    A mismatch here silently writes every section to the wrong address, which
    is how the button labels were lost when the bank count went to 32.
    """

    HEADERS = ("flash_midi_settings.h", "midi_defines.h", "display.h", "expression.h")

    @classmethod
    def setUpClass(cls):
        import os
        import re

        inc = os.path.join(os.path.dirname(__file__), "..", "..",
                           "firmware", "Core", "Inc")
        text = ""
        for name in cls.HEADERS:
            path = os.path.join(inc, name)
            if os.path.exists(path):
                with open(path) as handle:
                    text += handle.read() + "\n"
        cls.macros = dict(
            re.findall(r"^#define\s+([A-Z_][A-Z0-9_]*)\s+(\(?[0-9A-Za-z_ ()*+\-]*\)?)\s*(?://.*)?$",
                       text, re.M)
        )

    def value(self, name):
        """Evaluate a macro, resolving the macros it refers to."""
        import re

        seen = set()

        def resolve(expr, depth=0):
            self.assertLess(depth, 20, expr)
            def sub(m):
                key = m.group(0)
                if key in self.macros:
                    return "(" + resolve(self.macros[key], depth + 1) + ")"
                return key
            return re.sub(r"[A-Za-z_][A-Za-z0-9_]*", sub, expr)

        self.assertIn(name, self.macros, name)
        expr = resolve(self.macros[name])
        self.assertNotRegex(expr, r"[A-Za-z_]", f"{name} -> {expr}")
        return eval(expr)  # noqa: S307 - integer arithmetic from our own headers

    def test_offsets_match(self):
        pairs = [
            ("CFG_GLOBAL_SIZE", "GLOBAL_SIZE"),
            ("CFG_BANK_STRINGS_SIZE", "BANK_STRINGS_SIZE"),
            ("CFG_CMDS_OFF", "COMMANDS_OFFSET"),
            ("CFG_LED_MODES_OFF", "LED_MODES_OFFSET"),
            ("CFG_LABELS_OFF", "LABELS_OFFSET"),
            ("CFG_LONG_CMDS_OFF", "LONG_PRESS_OFFSET"),
            ("CFG_EXP_OFF", "EXP_OFFSET"),
            ("CFG_BANK_ENTER_OFF", "BANK_ENTER_OFFSET"),
            ("CFG_SYSEX_OFF", "SYSEX_OFFSET"),
            ("CFG_BANK_SWITCH_OFF", "BANK_SWITCH_OFFSET"),
            ("CFG_SETLIST_OFF", "SETLIST_OFFSET"),
            ("SETLIST_MAX", "SETLIST_MAX"),
            ("CFG_TOTAL_SIZE", "CONFIG_SIZE"),
            ("CFG_DOUBLE_CMDS_OFF", "DOUBLE_PRESS_OFFSET"),
            ("CFG_DOUBLE_CMDS_SIZE", "DOUBLE_PRESS_SIZE"),
            ("FLASH_DOUBLE_PAGES", "DOUBLE_PRESS_PAGES"),
            ("FLASH_IMAGE_SIZE", "IMAGE_SIZE"),
            ("MIDI_NUM_BANKS", "NUM_BANKS"),
            ("MIDI_ROM_KEY_STRIDE", "BUTTON_STRIDE"),
            ("MIDI_ROM_CMD_SIZE", "CMD_SIZE"),
            ("SYSEX_STRING_COUNT", "SYSEX_STRING_COUNT"),
            ("SYSEX_STRING_STRIDE", "SYSEX_STRING_STRIDE"),
        ]
        for macro, attr in pairs:
            self.assertEqual(self.value(macro), getattr(unpacker, attr),
                             f"{macro} != binaryUnpacker.{attr}")

    def test_configuration_fits_the_erased_pages(self):
        pages = self.value("FLASH_SETTINGS_NO_PAGES")
        self.assertLessEqual(unpacker.CONFIG_SIZE, pages * 2048)
        # ...and no page is erased for nothing
        self.assertGreater(unpacker.CONFIG_SIZE, (pages - 1) * 2048)

    def test_global_settings_indices_match(self):
        from lib import settingsBinaryPacker as sbp

        checked = 0
        for name in dir(sbp):
            if name.startswith("GLOBAL_SETTINGS_") and name in self.macros:
                self.assertEqual(self.value(name), getattr(sbp, name), name)
                checked += 1
        self.assertGreaterEqual(checked, 10)


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
        regions = [(unpacker.COMMANDS_OFFSET, 256), (unpacker.LONG_PRESS_OFFSET, 256),
                   (unpacker.BANK_ENTER_OFFSET, 32), (unpacker.BANK_SWITCH_OFFSET, 4)]
        for start, count in regions:
            for i in range(count):
                for j in range(10):
                    o = start + i * unpacker.BUTTON_STRIDE + j * unpacker.CMD_SIZE
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
        self.assertEqual(len(packed), unpacker.CONFIG_SIZE)

    def test_name_still_fits_before_it(self):
        """Widening the area must not disturb ConfigName at 16..31."""
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        self.assertEqual(packed[16:32].decode("ascii").strip(), "DEMO ALL")


class SetlistTest(unittest.TestCase):
    """Bank Up/Down order when Setlist_Mode is on."""

    def packed_setlist(self, sections):
        packed = packer.pack_config(sections)
        start = unpacker.SETLIST_OFFSET
        return packed, list(packed[start:start + unpacker.SETLIST_MAX])

    def test_demo_order_round_trips(self):
        packed, raw = self.packed_setlist(read_config_csv(DEMO_CSV))
        expected = [0, 12, 15, 13, 14, 18, 16, 17, 19, 20]
        self.assertEqual(raw[:len(expected)], expected)
        self.assertEqual(raw[len(expected):], [0xFF] * (32 - len(expected)))
        self.assertEqual(packed[33], 1)
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


class SetlistCompatibilityTest(unittest.TestCase):
    """A configuration flashed by 0.18 tools must read as setlist off and empty.

    Flashing erases every configuration page and writes only what the tool
    packed, so the bytes past a 0.18 configuration are left at 0xFF, and byte
    33 was packed as 0.
    """

    def test_018_image_reads_setlist_off(self):
        image = bytearray(packer.pack_config(read_config_csv(DEMO_CSV)))
        old_size = unpacker.SETLIST_OFFSET          # 0.18 ended where the setlist starts
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
        self.assertEqual(packed[33], 1)     # Setlist_Mode in the demo
        self.assertEqual(packed[32], 15)    # Sleep_After_Min in the demo


class LedFeedbackTest(unittest.TestCase):
    """Global byte 35: incoming CC and notes set the toggle buttons that send them."""

    def pack_with(self, value):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        g.loc[g["Label"] == "LED_Feedback", "Value"] = value
        return packer.pack_config(sections)

    def test_round_trip(self):
        for text, byte in (("Y", 1), ("N", 0)):
            packed = self.pack_with(text)
            self.assertEqual(packed[35], byte, text)
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual(back["LED_Feedback"], text)

    def test_missing_setting_means_off(self):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        sections["Global_Settings"] = g[g["Label"] != "LED_Feedback"]
        self.assertEqual(packer.pack_config(sections)[35], 0)

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
        self.assertEqual(packed[38], 0)


class DoublePressTest(unittest.TestCase):
    """Double press commands, written after the slot's pages (firmware 0.26)."""

    def setUp(self):
        self.sections = read_config_csv(DEMO_CSV)

    def test_extension_fits_its_pages(self):
        U = unpacker
        self.assertLessEqual(U.DOUBLE_PRESS_SIZE, U.DOUBLE_PRESS_PAGES * U.FLASH_PAGE_SIZE)
        self.assertGreaterEqual(U.DOUBLE_PRESS_OFFSET, U.CONFIG_SIZE)

    def test_demo_image(self):
        image = packer.pack_flash_image(self.sections)
        config = packer.pack_config(self.sections)
        U = unpacker
        self.assertEqual(len(image), U.DOUBLE_PRESS_OFFSET + U.DOUBLE_PRESS_SIZE)
        # The configuration itself is untouched, the gap is erased flash
        self.assertEqual(image[: len(config)], config)
        self.assertEqual(set(image[len(config) : U.DOUBLE_PRESS_OFFSET]), {0xFF})
        # One command in the demo, everything else erased
        extension = image[U.DOUBLE_PRESS_OFFSET :]
        self.assertEqual(sum(1 for b in extension if b != 0xFF), 4)
        button = 2 * 8 + 3                     # bank 2, button 4
        off = U.DOUBLE_PRESS_OFFSET + button * U.BUTTON_STRIDE
        self.assertEqual(list(image[off : off + 4]), [0xB0, 18 | 0x80, 127, 0])

    def test_demo_round_trip(self):
        image = packer.pack_flash_image(self.sections)
        df = unpacker.unpack_double_press_settings(image)
        row = df[(df["Bank_Number"] == "2") & (df["Button_Identifier"] == "4")].iloc[0]
        self.assertEqual(row["A_CommandType"], "CC")
        self.assertEqual(row["A_Number_(PC/CC/Note)"], "18")
        self.assertEqual(row["A_Toggle_(CC/PB/Note)"], "Y")
        self.assertEqual(row["B_CommandType"], "")
        self.assertEqual((df["A_CommandType"] != "").sum(), 1)

    def test_without_double_press_image_is_the_config(self):
        sections = {k: v for k, v in self.sections.items() if k != packer.DOUBLE_PRESS_SECTION}
        self.assertEqual(packer.pack_flash_image(sections), packer.pack_config(sections))
        self.assertIsNone(packer.pack_double_press(sections))

    def test_stored_flag(self):
        """Byte 37 tells the firmware the double press area belongs to this image."""
        self.assertEqual(packer.pack_config(self.sections)[37], 1)
        sections = {k: v for k, v in self.sections.items() if k != packer.DOUBLE_PRESS_SECTION}
        self.assertEqual(packer.pack_config(sections)[37], 0)
        empty = {**self.sections, packer.DOUBLE_PRESS_SECTION: packer.empty_double_press_settings()}
        self.assertEqual(packer.pack_config(empty)[37], 0)

    def test_dump_from_older_firmware_has_none(self):
        df = unpacker.unpack_double_press_settings(packer.pack_config(self.sections))
        self.assertEqual((df["A_CommandType"] != "").sum(), 0)
        self.assertEqual(len(df), 32 * 8)

    def test_window(self):
        g = self.sections["Global_Settings"]
        for text, byte, back in (("450", 45, "450"), ("50", 10, "100"), ("5000", 100, "1000")):
            g.loc[g["Label"] == "Double_Press_ms", "Value"] = text
            packed = packer.pack_config(self.sections)
            self.assertEqual(packed[36], byte, text)
            decoded = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual(decoded["Double_Press_ms"], back)
        self.sections["Global_Settings"] = g[g["Label"] != "Double_Press_ms"]
        self.assertEqual(packer.pack_config(self.sections)[36], 30)

    def test_erased_window_reads_default(self):
        image = bytearray(packer.pack_config(self.sections))
        for old in (0x00, 0xFF):
            image[36] = old
            decoded = unpacker.unpack_config(bytes(image))[0].set_index("Label")["Value"]
            self.assertEqual(decoded["Double_Press_ms"], "300")

    def test_copy_paste_bank_takes_double_press(self):
        from lib import bankClipboard

        s = self.sections
        double = s[packer.DOUBLE_PRESS_SECTION]
        clip = bankClipboard.copy_bank(s["Button_Settings"], s.get(packer.LONG_PRESS_SECTION),
                                       s.get(packer.BANK_ENTER_SECTION), 2, df_double=double)
        pasted = bankClipboard.paste_double(double, clip, 9)
        image = packer.pack_flash_image({**s, packer.DOUBLE_PRESS_SECTION: pasted})
        df = unpacker.unpack_double_press_settings(image)
        row = df[(df["Bank_Number"] == "9") & (df["Button_Identifier"] == "4")].iloc[0]
        self.assertEqual(row["A_Number_(PC/CC/Note)"], "18")
        self.assertEqual((df["A_CommandType"] != "").sum(), 2)


class VirtualPedalTest(unittest.TestCase):
    """SysEx PRESS_BUTTON and GET_STATE, as the configurator's virtual pedal uses them."""

    def test_sysex_codes_match_firmware(self):
        import re
        from lib import midiDevice as md

        path = os.path.join(os.path.dirname(HERE), "..", "firmware", "Core", "Inc", "midi_defines.h")
        with open(path) as f:
            text = f.read()
        for name in ("SYSEX_CMD_PRESS_BUTTON", "SYSEX_RSP_PRESS_BUTTON",
                     "SYSEX_CMD_GET_STATE", "SYSEX_RSP_GET_STATE",
                     "SYSEX_CMD_GET_SCREEN", "SYSEX_RSP_GET_SCREEN"):
            m = re.search(r"#define\s+" + name + r"\s+\((\d+)\)", text)
            self.assertIsNotNone(m, name)
            self.assertEqual(int(m.group(1)), getattr(md, name), name)

    def test_switch_ids(self):
        from lib.midiDevice import switch_id

        self.assertEqual([switch_id(n) for n in ("1", "4", "a", "D", "down", "UP")], [0, 3, 4, 7, 8, 9])
        self.assertEqual(switch_id(9), 9)
        for bad in ("E", 10, -1, "5"):
            with self.assertRaises(ValueError):
                switch_id(bad)

    def test_parse_state(self):
        from lib.midiDevice import parse_state

        data = [2, 1, 0b0010101, 1]                      # bank 2, slot 2, toggles 1,3,5 and D
        data += list(b"FX  ")
        for label in ("NORM", "REVS", "ALWY", "MOMT", "DIM ", "BLNK", "HALF", "NOFF"):
            data += list(label.encode())
        data += [16, 0, 4, 0, 16, 16, 0, 0, 0, 20]       # LED levels, one out of range
        state = parse_state(data)
        self.assertEqual(state["bank"], 2)
        self.assertEqual(state["slot"], 1)
        self.assertEqual(state["toggles"], [True, False, True, False, True, False, False, True])
        self.assertEqual(state["bank_name"], "FX")
        self.assertEqual(state["labels"][4], "DIM")
        self.assertEqual(state["leds"], [16, 0, 4, 0, 16, 16, 0, 0, 0, 16])
        with self.assertRaises(ValueError):
            parse_state(data[:20])

    def test_state_fits_the_sysex_buffer(self):
        """Firmware answer: F0 7D code + 53 data bytes + F7 must fit its 64 byte buffer."""
        self.assertLessEqual(3 + 4 + 4 + 8 * 4 + 10 + 3 + 1, 64)

    def test_state_frame_and_sleep(self):
        from lib.midiDevice import parse_state

        data = [0] * 50 + [0x7F, 0x03, 1]
        state = parse_state(data)
        self.assertEqual(state["frame"], 0x7F | (3 << 7))
        self.assertTrue(state["asleep"])
        self.assertIsNone(parse_state([0] * 50)["frame"])

    @staticmethod
    def pack7(raw):
        """The firmware's packing, sysex_get_screen in usbd_midi_if.c."""
        out = []
        for i in range(0, len(raw), 7):
            chunk = raw[i:i + 7]
            out.append(sum(1 << k for k, b in enumerate(chunk) if b & 0x80))
            out += [b & 0x7F for b in chunk]
        return out

    def test_unpack7_round_trip(self):
        import random
        from lib.midiDevice import SCREEN_PART_BYTES, unpack7

        rng = random.Random(7)
        for raw in (bytes(range(256))[:SCREEN_PART_BYTES], bytes([0xFF] * SCREEN_PART_BYTES),
                    bytes(rng.randrange(256) for _ in range(SCREEN_PART_BYTES))):
            packed = self.pack7(raw)
            self.assertTrue(all(b < 0x80 for b in packed))
            self.assertEqual(unpack7(packed), raw)
        # 65 bytes: 9 groups of 7 and one of 2 -> 75 bytes, an 80 byte answer
        self.assertEqual(len(self.pack7(bytes(SCREEN_PART_BYTES))), 75)

    def test_screen_rows(self):
        from lib.midiDevice import SCREEN_HEIGHT, SCREEN_VISIBLE_WIDTH, SCREEN_WIDTH, screen_rows

        buffer = bytearray(SCREEN_WIDTH * SCREEN_HEIGHT // 8)
        buffer[0] = 0x01                       # x 0, y 0
        buffer[127 + 7 * SCREEN_WIDTH] = 0x80  # x 127, y 63
        buffer[129] = 0xFF                     # column 129: outside the drawn area
        rows = screen_rows(bytes(buffer))
        self.assertEqual((len(rows), len(rows[0])), (SCREEN_HEIGHT, SCREEN_VISIBLE_WIDTH))
        self.assertTrue(rows[0][0] and rows[63][127])
        self.assertEqual(sum(sum(r) for r in rows), 2)


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


class BankClipboardTest(unittest.TestCase):
    """Copy one bank over another, as the configurator's Copy/Paste bank does."""

    SRC, DST = 3, 9

    @staticmethod
    def region(packed, start, stride, bank):
        return packed[start + bank * stride:start + (bank + 1) * stride]

    def setUp(self):
        from lib import bankClipboard
        self.clip = bankClipboard
        self.sections = read_config_csv(DEMO_CSV)
        self.before = packer.pack_config(self.sections)

    def paste(self, src, dst):
        s = self.sections
        clip = self.clip.copy_bank(s["Button_Settings"], s.get(packer.LONG_PRESS_SECTION),
                                   s.get(packer.BANK_ENTER_SECTION), src)
        b, l, e = self.clip.paste_bank(s["Button_Settings"], s.get(packer.LONG_PRESS_SECTION),
                                       s.get(packer.BANK_ENTER_SECTION), clip, dst)
        new = dict(s)
        new["Button_Settings"], new[packer.LONG_PRESS_SECTION], new[packer.BANK_ENTER_SECTION] = b, l, e
        return new, packer.pack_config(new)

    def test_target_becomes_identical(self):
        _, after = self.paste(self.SRC, self.DST)
        U = unpacker
        for name, start, stride in (
            ("commands", U.COMMANDS_OFFSET, 8 * U.BUTTON_STRIDE),
            ("led modes", U.LED_MODES_OFFSET, 8),
            ("labels", U.LABELS_OFFSET, 32),
            ("long press", U.LONG_PRESS_OFFSET, 8 * U.BUTTON_STRIDE),
            ("bank enter", U.BANK_ENTER_OFFSET, U.BUTTON_STRIDE),
        ):
            self.assertEqual(self.region(after, start, stride, self.DST),
                             self.region(self.before, start, stride, self.SRC), name)

    def test_nothing_else_changes(self):
        _, after = self.paste(self.SRC, self.DST)
        U = unpacker
        diffs = [i for i in range(len(after)) if after[i] != self.before[i]]
        allowed = []
        for start, stride in ((U.COMMANDS_OFFSET, 8 * U.BUTTON_STRIDE), (U.LED_MODES_OFFSET, 8),
                              (U.LABELS_OFFSET, 32), (U.LONG_PRESS_OFFSET, 8 * U.BUTTON_STRIDE),
                              (U.BANK_ENTER_OFFSET, U.BUTTON_STRIDE)):
            allowed.append(range(start + self.DST * stride, start + (self.DST + 1) * stride))
        stray = [i for i in diffs if not any(i in r for r in allowed)]
        self.assertEqual(stray, [], "bytes outside the target bank changed")
        self.assertTrue(diffs, "the paste changed nothing")

    def test_bank_name_is_kept(self):
        _, after = self.paste(self.SRC, self.DST)
        name = self.region(after, unpacker.GLOBAL_SIZE, 12, self.DST)
        self.assertEqual(name, self.region(self.before, unpacker.GLOBAL_SIZE, 12, self.DST))

    def test_rows_keep_their_count(self):
        new, _ = self.paste(self.SRC, self.DST)
        self.assertEqual(len(new["Button_Settings"]), len(self.sections["Button_Settings"]))

    def test_target_extras_are_removed(self):
        """Bank 1 has a long press on button 4; bank 6 only one on button 4 too; bank 2 none."""
        s = self.sections
        long_frame = s[packer.LONG_PRESS_SECTION]
        def long_types(frame, bank):
            rows = frame[frame["Bank_Number"].astype(str).str.replace(".0", "", regex=False) == str(bank)]
            return sorted(str(r["A_CommandType"]) for _, r in rows.iterrows()
                          if str(r["A_CommandType"]) not in ("", "nan"))
        self.assertTrue(long_types(long_frame, 1))
        new, _ = self.paste(2, 1)
        self.assertEqual(long_types(new[packer.LONG_PRESS_SECTION], 1), long_types(long_frame, 2))

    def test_copy_is_a_snapshot(self):
        s = self.sections
        clip = self.clip.copy_bank(s["Button_Settings"], None, None, self.SRC)
        before = [dict(r) for r in clip["buttons"]]
        s["Button_Settings"].loc[:, "Label"] = "XXXX"
        self.assertEqual(clip["buttons"], before)

    def test_paste_onto_itself_is_a_no_op(self):
        _, after = self.paste(self.SRC, self.SRC)
        self.assertEqual(after, self.before)


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
