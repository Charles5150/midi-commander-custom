"""Round-trip test: CSV -> packer bytes -> unpacker -> compare with the CSV.

Run from the repository root:

    python -m unittest python/tests/test_roundtrip.py
"""

import os
import sys
import struct
import unittest

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lib.binaryUnpacker as unpacker  # noqa: E402
import lib.cmdBinaryPacker as cbp  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
import lib.configPacker as packer  # noqa: E402
import lib.kemperProtocol as kp  # noqa: E402
import Kemper_Sim as kemper_sim  # noqa: E402
from lib.configPacker import pack_config  # noqa: E402

SAMPLE_CSV = os.path.join(os.path.dirname(HERE), "MeloConfig_10_Cmds - RC-600.csv")
DEMO_CSV = os.path.join(os.path.dirname(HERE), "demo-all-features.csv")
FM3_CSV = os.path.join(os.path.dirname(HERE), "templates", "FM3.csv")
HX_STOMP_CSV = os.path.join(os.path.dirname(HERE), "templates", "HX_Stomp.csv")
KEMPER_PLAYER_CSV = os.path.join(os.path.dirname(HERE), "templates", "Kemper_Player.csv")


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
        from lib.slotIO import ALLOWED_NUM_FLASH_PAGES, FLASH_PAGE_SIZE

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
            ("CFG_BANK_EXP_OFF", "BANK_EXP_OFFSET"),
            ("CFG_BANK_EXP_STRIDE", "BANK_EXP_STRIDE"),
            ("BANK_EXP_CC_OFF", "BANK_EXP_CC_OFF"),
            ("BANK_EXP_CC_SPEED", "BANK_EXP_CC_SPEED"),
            ("SETLIST_MAX", "SETLIST_MAX"),
            ("CFG_CYCLE_LABELS_OFF", "CYCLE_LABELS_OFFSET"),
            ("CYCLE_LABEL_COUNT", "CYCLE_LABEL_COUNT"),
            ("CFG_COMBOS_OFF", "COMBOS_OFFSET"),
            ("COMBO_COUNT", "COMBO_COUNT"),
            ("COMBO_STRIDE", "COMBO_STRIDE"),
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
        g.loc[g["Label"] == "Link_Toggles", "Value"] = "N"
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


FIRMWARE = os.path.join(os.path.dirname(os.path.dirname(HERE)), "firmware")


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
            self.assertEqual(packed[35], byte, (feedback, link))
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual((back["LED_Feedback"], back["Link_Toggles"]), (feedback, link))

    def test_missing_setting_means_off(self):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        sections["Global_Settings"] = g[g["Label"] != "Link_Toggles"]
        self.assertEqual(packer.pack_config(sections)[35], 1)   # LED_Feedback alone

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


class HostTextTest(unittest.TestCase):
    """SysEx SET_TEXT: the host writes on the display (firmware 0.46)."""

    @classmethod
    def setUpClass(cls):
        import re

        root = os.path.join(os.path.dirname(__file__), "..", "..", "firmware")
        text = ""
        for rel in (("Core", "Inc", "midi_defines.h"), ("Core", "Inc", "display.h"), ("Core", "Src", "display.c")):
            with open(os.path.join(root, *rel)) as handle:
                text += handle.read() + "\n"
        cls.firmware = text
        cls.macros = {k: int(v) for k, v in re.findall(r"^#define\s+(\w+)\s+\((\d+)\)", text, re.M)}

    def test_codes_match_firmware(self):
        from lib import midiDevice as md

        self.assertEqual(self.macros["SYSEX_CMD_SET_TEXT"], md.SYSEX_CMD_SET_TEXT)
        self.assertEqual(self.macros["SYSEX_RSP_SET_TEXT"], md.SYSEX_RSP_SET_TEXT)
        places = {"info": "DISPLAY_TEXT_INFO", "name": "DISPLAY_TEXT_NAME",
                  "line": "DISPLAY_TEXT_LINE_LARGE", "small": "DISPLAY_TEXT_LINE_SMALL"}
        for name, macro in places.items():
            self.assertEqual(self.macros[macro], md.TEXT_PLACES[name], name)
        keeps = {"bank": "TEXT_KEEP_BANK", "always": "TEXT_KEEP_ALWAYS", "moment": "TEXT_KEEP_MOMENT"}
        for name, macro in keeps.items():
            self.assertEqual(self.macros[macro], md.TEXT_KEEP[name], name)

    def test_lengths_match_firmware(self):
        import re

        from lib import midiDevice as md

        self.assertEqual(self.macros["DISPLAY_TEXT_MAX"], md.TEXT_MAX)

        def px(name):
            return int(re.search(rf"#define {name}\s+\((\d+)\)", self.firmware).group(1))

        # What fits without scrolling: the room of each place over its font
        shown, name_w, info_x = px("SCREEN_SHOWN_W"), px("NAME_W"), px("INFO_X")
        rooms = {"info": (shown - info_x) // 7, "name": name_w // 11,
                 "line": shown // 11, "small": shown // 7}
        self.assertEqual(rooms, md.TEXT_FITS)

    def test_message(self):
        from lib.midiDevice import text_sysex

        self.assertEqual(text_sysex("Intro"), [0xF0, 0x7D, 72, 2, 0] + list(b"Intro") + [0xF7])
        self.assertEqual(text_sysex("Clean", "info", "moment")[3:5], [0, 2])
        self.assertEqual(text_sysex("SONG", " Name ", "Always")[3:5], [1, 1])
        self.assertEqual(text_sysex("", "line"), [0xF0, 0x7D, 72, 2, 0, 0xF7])

    def test_cut_to_fit_and_seven_bit(self):
        from lib.midiDevice import text_sysex

        self.assertEqual(bytes(text_sysex("Sweet Child O Mine")[5:-1]), b"Sweet Child O Mine")
        self.assertEqual(len(text_sysex("x" * 40, "name")[5:-1]), 32)
        self.assertEqual(bytes(text_sysex("Canción", "small")[5:-1]), b"Canci n")
        self.assertTrue(all(b < 0x80 for b in text_sysex("\u00f1\u00e9\u20ac\x7f", "small")[1:-1]))

    def test_fits_the_receive_buffer(self):
        """The longest message must fit the firmware's SysEx buffer, with room to spare."""
        from lib.midiDevice import text_sysex

        self.assertLessEqual(len(text_sysex("x" * 100, "small")), 64)

    def test_bad_place_or_keep(self):
        from lib.midiDevice import text_sysex

        with self.assertRaises(ValueError):
            text_sysex("x", "middle")
        with self.assertRaises(ValueError):
            text_sysex("x", "line", "forever")


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
        # The configuration itself is untouched, and since 0.59 it fills the
        # slot's pages, so the extension follows it with no gap
        self.assertEqual(image[: len(config)], config)
        self.assertEqual(len(config), U.DOUBLE_PRESS_OFFSET)
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

    def test_commands_of_the_empty_type_are_kept(self):
        """Wait, If, Macro, Button and the rest share the empty command type's
        nibble; only a slot with nothing in it is left erased (0.73)."""
        df = self.sections[packer.DOUBLE_PRESS_SECTION].copy()
        i = df[(df["Bank_Number"].astype(str) == "1") & (df["Button_Identifier"] == "3")].index[0]
        for slot, fields in (("A", {"CommandType": "Wait", "Duration_(Note/PB)": "200"}),
                             ("B", {"CommandType": "Button", "Number_(PC/CC/Note)": "B",
                                    "KeyMode_(Key)": "Set Off"})):
            for field, value in fields.items():
                df.at[i, f"{slot}_{field}"] = value
        image = packer.pack_flash_image({**self.sections, packer.DOUBLE_PRESS_SECTION: df})
        U = unpacker
        off = U.DOUBLE_PRESS_OFFSET + (1 * 8 + 2) * U.BUTTON_STRIDE
        self.assertEqual(list(image[off : off + 12]),
                         [0x01, 0, 20, 0, 0x0D, 0x7F, 0x05, 5] + [0xFF] * 4)
        back = unpacker.unpack_double_press_settings(image)
        row = back[(back["Bank_Number"] == "1") & (back["Button_Identifier"] == "3")].iloc[0]
        self.assertEqual((row["A_CommandType"], row["B_CommandType"]), ("Wait", "Button"))

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
                     "SYSEX_CMD_GET_SCREEN", "SYSEX_RSP_GET_SCREEN",
                     "SYSEX_CMD_SET_PEDAL", "SYSEX_RSP_SET_PEDAL"):
            m = re.search(r"#define\s+" + name + r"\s+\((\d+)\)", text)
            self.assertIsNotNone(m, name)
            self.assertEqual(int(m.group(1)), getattr(md, name), name)

    def test_set_pedal(self):
        from lib import midiDevice as md

        sent = []

        class Fake(md.MidiCommander):
            def __init__(self):
                pass

            def send(self, data):
                sent.append(list(data))

            def wait_for_sysex(self, rsp, timeout):
                return [0, 1]

        dev = Fake()
        dev.set_pedal(0, 0.5)
        dev.set_pedal(1, 1.0)
        dev.set_pedal(1, -0.2)
        dev.set_pedal(0, None)
        self.assertEqual(sent, [[md.SYSEX_CMD_SET_PEDAL, 0, 1, 64, 0],
                                [md.SYSEX_CMD_SET_PEDAL, 1, 1, 127, 127],
                                [md.SYSEX_CMD_SET_PEDAL, 1, 1, 0, 0],
                                [md.SYSEX_CMD_SET_PEDAL, 0, 0, 0, 0]])

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
        """Firmware answer: F0 7D code + 63 data bytes + F7 must fit its 80 byte buffer."""
        size = 3 + 4 + 4 + 8 * 4 + 10 + 3 + 8 + 1 + 1 + 1
        self.assertEqual(size, 67)
        root = os.path.join(os.path.dirname(__file__), "..", "..")
        with open(os.path.join(root, "firmware", "USB_DEVICE", "App", "usbd_midi_if.c")) as handle:
            source = handle.read()
        buffer = int(source.split("#define SYSEX_MAX_LENGTH", 1)[1].split()[0])
        self.assertLessEqual(size, buffer)

    def test_state_safe_mode(self):
        from lib.midiDevice import parse_state

        self.assertFalse(parse_state([0] * 61)["safe_mode"])     # before firmware 0.60
        self.assertFalse(parse_state([0] * 62)["safe_mode"])
        self.assertTrue(parse_state([0] * 61 + [1])["safe_mode"])

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


class BankExpressionTest(unittest.TestCase):
    """Expression pedal CC and channel per bank (firmware 0.28)."""

    def setUp(self):
        self.sections = read_config_csv(DEMO_CSV)

    def region(self, packed, bank):
        base = unpacker.BANK_EXP_OFFSET + bank * unpacker.BANK_EXP_STRIDE
        return list(packed[base : base + unpacker.BANK_EXP_STRIDE])

    def test_demo_bytes(self):
        packed = packer.pack_config(self.sections)
        self.assertEqual(len(packed), unpacker.CONFIG_SIZE)
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

    def test_missing_section_keeps_pedals_as_they_are(self):
        sections = {k: v for k, v in self.sections.items() if k != packer.BANK_EXPRESSION_SECTION}
        packed = packer.pack_config(sections)
        self.assertEqual(set(packed[unpacker.BANK_EXP_OFFSET : unpacker.CYCLE_LABELS_OFFSET]), {0xFF})

    def test_cell_values(self):
        cc, ch = packer.bank_exp_cc_byte, packer.bank_exp_channel_byte
        self.assertEqual([cc(v) for v in ("", "Default", "off", "0", "127", "200", "x", None)],
                         [0xFF, 0xFF, 0x80, 0, 127, 127, 0xFF, 0xFF])
        self.assertEqual([ch(v) for v in ("", "Default", "1", "16", "0", "17", "x")],
                         [0xFF, 0xFF, 1, 16, 0xFF, 0xFF, 0xFF])

    def test_older_image_reads_defaults(self):
        """An image written before 0.28 has erased flash where these bytes go."""
        image = bytearray(packer.pack_config(self.sections))
        image[unpacker.BANK_EXP_OFFSET :] = b"\xff" * (len(image) - unpacker.BANK_EXP_OFFSET)
        df = unpacker.unpack_bank_expression_settings(bytes(image))
        self.assertTrue((df[["Exp1_CC", "Exp1_Channel", "Exp2_CC", "Exp2_Channel"]] == "").all().all())

    def test_fits_the_slot(self):
        self.assertLessEqual(unpacker.CONFIG_SIZE, 12 * 2048)

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
        base = unpacker.EXP_OFFSET + pedal * unpacker.EXP_STRIDE
        return list(packed[base + 11 : base + 13])

    def bank_range(self, packed, bank):
        base = unpacker.BANK_EXP_RANGE_OFFSET + bank * unpacker.BANK_EXP_RANGE_STRIDE
        return list(packed[base : base + unpacker.BANK_EXP_RANGE_STRIDE])

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
        base = unpacker.EXP_OFFSET
        self.assertEqual(list(packed[base + 13 : base + 16]), [0, 50, 0])

    def test_older_records_have_the_full_range(self):
        """Older tools wrote zeros after byte 10, blank flash is 0xFF."""
        packed = bytearray(packer.pack_config(self.sections))
        base = unpacker.EXP_OFFSET
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
        base = unpacker.BANK_EXP_OFFSET + 7 * unpacker.BANK_EXP_STRIDE
        self.assertEqual(list(packed[base : base + 4]), [0x80, 0xFF, 7, 2])

    def test_bank_csv_without_the_columns(self):
        df = self.sections[packer.BANK_EXPRESSION_SECTION].drop(
            columns=["Exp1_Min", "Exp1_Max", "Exp2_Min", "Exp2_Max"])
        packed = packer.pack_config({**self.sections, packer.BANK_EXPRESSION_SECTION: df})
        self.assertEqual(set(packed[unpacker.BANK_EXP_RANGE_OFFSET : unpacker.CYCLE_LABELS_OFFSET]), {0xFF})

    def test_range_values(self):
        r = packer.bank_exp_range_byte
        self.assertEqual([r(v) for v in ("", "Default", None, "0", "127", "200", "-3", "x")],
                         [0xFF, 0xFF, 0xFF, 0, 127, 127, 0, 0xFF])

    def test_image_read_from_older_firmware(self):
        """A dump that stops before the range table decodes as the pedal's own range."""
        packed = packer.pack_config(self.sections)[: unpacker.BANK_EXP_RANGE_OFFSET]
        df = unpacker.unpack_bank_expression_settings(packed)
        self.assertTrue((df[["Exp1_Min", "Exp1_Max", "Exp2_Min", "Exp2_Max"]] == "").all().all())


class AutoEngageTest(unittest.TestCase):
    """Auto-engage from the expression pedal, bytes 13 and 14 of its record (firmware 0.41)."""

    def setUp(self):
        self.sections = read_config_csv(DEMO_CSV)

    def auto_bytes(self, packed, pedal):
        base = unpacker.EXP_OFFSET + pedal * unpacker.EXP_STRIDE
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

        for idx, name in enumerate(packer.EXP_BUTTON_IDS):
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
        base = unpacker.EXP_OFFSET
        packed[base + 13 : base + 15] = b"\x00\x00"
        packed[base + 16 + 13 : base + 16 + 15] = b"\xff\xff"
        exp = unpacker.unpack_config(bytes(packed))[4]
        self.assertEqual(list(exp["Auto_Button"]), ["None", "None"])
        self.assertEqual(list(exp["Auto_Off_ms"]), ["500", "500"])

    def test_csv_without_the_columns(self):
        df = self.sections[packer.EXPRESSION_SECTION].drop(columns=["Auto_Button", "Auto_Off_ms"])
        packed = packer.pack_config({**self.sections, packer.EXPRESSION_SECTION: df})
        self.assertEqual(self.auto_bytes(packed, 0), [0, 50])


class ExpressionOutputTest(unittest.TestCase):
    """Pitch Bend and 14-bit CC from an expression pedal, byte 15 of its record (firmware 0.44)."""

    def setUp(self):
        self.sections = read_config_csv(DEMO_CSV)

    def output_bytes(self, packed):
        return [packed[unpacker.EXP_OFFSET + i * unpacker.EXP_STRIDE + 15] for i in range(2)]

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
        for name, code in (("CC", 0), ("PitchBend", 1), ("CC14", 2), ("Speed", 3)):
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
        packed[unpacker.EXP_OFFSET + 15] = 0xFF
        packed[unpacker.EXP_OFFSET + unpacker.EXP_STRIDE + 15] = 0
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
        for name, code in (("CC", 0), ("PITCHBEND", 1), ("CC14", 2), ("SPEED", 3)):
            m = re.search(rf"#define\s+EXP_OUT_{name}\s+\((\d+)\)", header)
            self.assertEqual(int(m.group(1)), code, name)
            self.assertEqual(packer.EXP_OUTPUTS[name], code)


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


class ButtonGroupTest(unittest.TestCase):
    """Exclusive groups, stored in the top bits of each button's LED mode byte."""

    def test_packs_in_the_led_byte(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Button_Settings"].copy()
        df["Group"] = ""
        i = df.index[(df["Bank_Number"].astype(str) == "5") & (df["Button_Identifier"] == "B")][0]
        df.at[i, "Light_Mode"] = "AlwaysOn"
        df.at[i, "Group"] = "3"
        base = pack_config({**sections, "Button_Settings": df.assign(Group="")})
        packed = pack_config({**sections, "Button_Settings": df})
        at = unpacker.LED_MODES_OFFSET + 5 * 8 + unpacker.BUTTON_IDS.index("B")
        self.assertEqual(packed[at], 0x32)
        # Nothing else moves
        self.assertEqual(packed[:at] + packed[at + 1:], base[:at] + base[at + 1:])

    def test_round_trip(self):
        sections = read_config_csv(DEMO_CSV)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        df = sections["Button_Settings"]
        for bank, btn in (("1", "A"), ("1", "D")):
            row = decoded[(decoded["Bank_Number"] == bank) & (decoded["Button_Identifier"] == btn)]
            self.assertEqual(row["Group"].iloc[0], "1")
        self.assertEqual((decoded["Group"] != "").sum(), (df["Group"].map(norm) != "").sum())

    def test_older_configurations_have_no_group(self):
        """A CSV without the column packs exactly as before, all zero on top."""
        sections = read_config_csv(SAMPLE_CSV)
        self.assertNotIn("Group", sections["Button_Settings"].columns)
        packed = pack_config(sections)
        table = packed[unpacker.LED_MODES_OFFSET : unpacker.LABELS_OFFSET]
        self.assertTrue(all(b < 0x10 for b in table))
        _, _, decoded, *_ = unpacker.unpack_config(packed)
        self.assertTrue((decoded["Group"] == "").all())

    def test_erased_flash_has_no_group(self):
        blank = bytes([0xFF]) * unpacker.CONFIG_SIZE
        _, _, df, *_ = unpacker.unpack_config(blank)
        self.assertTrue((df["Group"] == "").all())
        self.assertTrue((df["Light_Mode"] == "Normal").all())

    def test_values(self):
        for cell, want in (("", 0), (float("nan"), 0), ("None", 0), ("0", 0), ("1", 1), ("4.0", 4)):
            self.assertEqual(cbp.button_group_value(cell), want, cell)
        for cell in ("5", "-1", "x"):
            with self.assertRaises(ValueError):
                cbp.button_group_value(cell)


class MomentaryHoldTest(unittest.TestCase):
    """Momentary hold, bit 7 of each button's LED mode byte."""

    def test_packs_in_the_led_byte(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Button_Settings"].copy()
        df["Momentary_Hold"] = ""
        i = df.index[(df["Bank_Number"].astype(str) == "5") & (df["Button_Identifier"] == "B")][0]
        df.at[i, "Light_Mode"] = "Reverse"
        df.at[i, "Group"] = "2"
        base = pack_config({**sections, "Button_Settings": df})
        df.at[i, "Momentary_Hold"] = "Y"
        packed = pack_config({**sections, "Button_Settings": df})
        at = unpacker.LED_MODES_OFFSET + 5 * 8 + unpacker.BUTTON_IDS.index("B")
        self.assertEqual(base[at], 0x21)
        self.assertEqual(packed[at], 0xA1)
        self.assertEqual(packed[:at] + packed[at + 1:], base[:at] + base[at + 1:])

    def test_round_trip(self):
        sections = read_config_csv(DEMO_CSV)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        row = decoded[(decoded["Bank_Number"] == "11") & (decoded["Button_Identifier"] == "4")]
        self.assertEqual(row["Momentary_Hold"].iloc[0], "Y")
        self.assertEqual(row["Light_Mode"].iloc[0], "AlwaysOn")
        self.assertEqual((decoded["Momentary_Hold"] == "Y").sum(), 1)

    def test_older_configurations_have_none(self):
        sections = read_config_csv(SAMPLE_CSV)
        self.assertNotIn("Momentary_Hold", sections["Button_Settings"].columns)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        self.assertTrue((decoded["Momentary_Hold"] == "").all())

    def test_erased_flash_has_none(self):
        blank = bytes([0xFF]) * unpacker.CONFIG_SIZE
        _, _, df, *_ = unpacker.unpack_config(blank)
        self.assertTrue((df["Momentary_Hold"] == "").all())

    def test_values(self):
        for cell, want in (("", False), (float("nan"), False), ("N", False), ("0", False),
                           ("Y", True), ("yes", True), ("1.0", True)):
            self.assertEqual(cbp.momentary_hold_value(cell), want, cell)
        with self.assertRaises(ValueError):
            cbp.momentary_hold_value("maybe")

    def test_firmware_bit_matches(self):
        import re
        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc",
                            "flash_midi_settings.h")
        with open(path) as handle:
            header = handle.read()
        m = re.search(r"#define\s+BUTTON_MOMENTARY_HOLD\s+\((0x[0-9A-Fa-f]+)\)", header)
        self.assertEqual(int(m.group(1), 16), cbp.BUTTON_MOMENTARY_HOLD)


class ResetOnBankTest(unittest.TestCase):
    """Reset on bank change, bit 7 of the first character of a button's label."""

    def _index(self, df, bank, btn):
        return df.index[(df["Bank_Number"].astype(str) == str(bank))
                        & (df["Button_Identifier"] == btn)][0]

    def test_packs_in_the_label(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Button_Settings"].copy()
        df["Reset_On_Bank"] = ""
        i = self._index(df, 5, "B")
        base = pack_config({**sections, "Button_Settings": df})
        df.at[i, "Reset_On_Bank"] = "Y"
        packed = pack_config({**sections, "Button_Settings": df})
        at = unpacker.LABELS_OFFSET + (5 * 8 + unpacker.BUTTON_IDS.index("B")) * unpacker.LABEL_LEN
        self.assertEqual(packed[at], base[at] | packer.LABEL_RESET_BIT)
        self.assertEqual(packed[:at] + packed[at + 1:], base[:at] + base[at + 1:])

    def test_an_empty_label_keeps_it(self):
        self.assertEqual(packer.pack_label("", reset=True), b"\xa0   ")
        self.assertEqual(packer.pack_label("BOST", reset=True), b"\xc2OST")
        self.assertEqual(packer.pack_label("BOST"), b"BOST")

    def test_round_trip(self):
        sections = read_config_csv(DEMO_CSV)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        row = decoded[(decoded["Bank_Number"] == "11") & (decoded["Button_Identifier"] == "4")]
        self.assertEqual(row["Reset_On_Bank"].iloc[0], "Y")
        self.assertEqual(row["Label"].iloc[0], "BOST")
        self.assertEqual((decoded["Reset_On_Bank"] == "Y").sum(), 1)

    def test_empty_label_round_trip(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Button_Settings"].copy()
        i = self._index(df, 5, "B")
        df.at[i, "Label"] = ""
        df.at[i, "Reset_On_Bank"] = "Y"
        _, _, decoded, *_ = unpacker.unpack_config(pack_config({**sections, "Button_Settings": df}))
        row = decoded[(decoded["Bank_Number"] == "5") & (decoded["Button_Identifier"] == "B")]
        self.assertEqual(norm(row["Label"].iloc[0]), "")
        self.assertEqual(row["Reset_On_Bank"].iloc[0], "Y")

    def test_older_configurations_have_none(self):
        sections = read_config_csv(SAMPLE_CSV)
        self.assertNotIn("Reset_On_Bank", sections["Button_Settings"].columns)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        self.assertTrue((decoded["Reset_On_Bank"] == "").all())

    def test_erased_flash_has_none(self):
        blank = bytes([0xFF]) * unpacker.CONFIG_SIZE
        _, _, df, *_ = unpacker.unpack_config(blank)
        self.assertTrue((df["Reset_On_Bank"] == "").all())

    def test_values(self):
        for cell, want in (("", False), (float("nan"), False), ("N", False),
                           ("Y", True), ("yes", True), ("1.0", True)):
            self.assertEqual(cbp.reset_on_bank_value(cell), want, cell)
        with self.assertRaises(ValueError):
            cbp.reset_on_bank_value("maybe")

    def test_firmware_bit_matches(self):
        import re
        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc",
                            "flash_midi_settings.h")
        with open(path) as handle:
            header = handle.read()
        m = re.search(r"#define\s+LABEL_RESET_BIT\s+\((0x[0-9A-Fa-f]+)\)", header)
        self.assertEqual(int(m.group(1), 16), packer.LABEL_RESET_BIT)


class TempoFlashTest(unittest.TestCase):
    """Flashing at the tempo, bit 2 of each button's LED mode byte."""

    def test_packs_in_the_led_byte(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Button_Settings"].copy()
        df["Tempo_Flash"] = ""
        i = df.index[(df["Bank_Number"].astype(str) == "5") & (df["Button_Identifier"] == "B")][0]
        df.at[i, "Light_Mode"] = "Reverse"
        df.at[i, "Group"] = "2"
        df.at[i, "Momentary_Hold"] = "Y"
        base = pack_config({**sections, "Button_Settings": df})
        df.at[i, "Tempo_Flash"] = "Y"
        packed = pack_config({**sections, "Button_Settings": df})
        at = unpacker.LED_MODES_OFFSET + 5 * 8 + unpacker.BUTTON_IDS.index("B")
        self.assertEqual(base[at], 0xA1)
        self.assertEqual(packed[at], 0xA5)
        self.assertEqual(packed[:at] + packed[at + 1:], base[:at] + base[at + 1:])

    def test_round_trip(self):
        sections = read_config_csv(DEMO_CSV)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        row = decoded[(decoded["Bank_Number"] == "6") & (decoded["Button_Identifier"] == "B")]
        self.assertEqual(row["Tempo_Flash"].iloc[0], "Y")
        # A plain CC toggle, not a Tap button: the flash is the button's own
        self.assertEqual(row["A_CommandType"].iloc[0], "CC")
        self.assertEqual((decoded["Tempo_Flash"] == "Y").sum(), 1)

    def test_older_configurations_have_none(self):
        sections = read_config_csv(SAMPLE_CSV)
        self.assertNotIn("Tempo_Flash", sections["Button_Settings"].columns)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        self.assertTrue((decoded["Tempo_Flash"] == "").all())

    def test_erased_flash_has_none(self):
        blank = bytes([0xFF]) * unpacker.CONFIG_SIZE
        _, _, df, *_ = unpacker.unpack_config(blank)
        self.assertTrue((df["Tempo_Flash"] == "").all())

    def test_values(self):
        for cell, want in (("", False), (float("nan"), False), ("N", False), ("0", False),
                           ("Y", True), ("yes", True), ("1.0", True)):
            self.assertEqual(cbp.tempo_flash_value(cell), want, cell)
        with self.assertRaises(ValueError):
            cbp.tempo_flash_value("maybe")

    def test_firmware_bits_match(self):
        import re
        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc",
                            "flash_midi_settings.h")
        with open(path) as handle:
            header = handle.read()
        m = re.search(r"#define\s+BUTTON_TEMPO_FLASH\s+\((0x[0-9A-Fa-f]+)\)", header)
        self.assertEqual(int(m.group(1), 16), cbp.BUTTON_TEMPO_FLASH)
        # The mode itself now stops below the flash bit, so the two never mix
        m = re.search(r"#define\s+LED_MODE_MASK\s+\((0x[0-9A-Fa-f]+)\)", header)
        self.assertEqual(int(m.group(1), 16), 0x03)
        self.assertLess(max(cbp.LED_MODE_VALUES.values()), cbp.BUTTON_TEMPO_FLASH)


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
    def pack(ms):
        row = {f"A_{f}": "" for f in unpacker.CMD_FIELDS}
        row["A_CommandType"] = "Wait"
        row["A_Duration_(Note/PB)"] = ms
        row["A_KeyMode_(Key)"] = ""
        return bytes(cbp.pack_row(pd.Series(row)))[:4]

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
        table = self.packed[unpacker.CYCLE_LABELS_OFFSET : unpacker.CONFIG_SIZE]
        self.assertEqual(table[:12], b"CH BCH CCH D")

    def test_older_dump_without_the_table(self):
        # Tools before 0.38 read and saved a dump ending before the table
        buttons = unpacker.unpack_config(self.packed[: unpacker.CYCLE_LABELS_OFFSET])[2]
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
        at = unpacker.BANK_ENTER_OFFSET + 11 * unpacker.BUTTON_STRIDE + 4
        self.assertEqual(packed[at : at + 4], bytes([0x04, 0, 0, 0]))

    def test_firmware_mode_matches(self):
        import re
        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc",
                            "midi_defines.h")
        with open(path) as handle:
            header = handle.read()
        m = re.search(r"#define\s+CMD_LEAVE_MODE\s+\((\d+)\)", header)
        self.assertEqual(int(m.group(1)), cbp.CMD_LEAVE_MODE)


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
                    [0x05, 0x81, 0x82, 0]):
            cmd = unpacker.unpack_command(bytes(raw))
            row = pd.Series({f"A_{k}": v for k, v in cmd.items()})
            self.assertEqual(cbp.pack_row(row)[:4], raw, cmd)

    def test_demo(self):
        packed = packer.pack_config(read_config_csv(DEMO_CSV))
        at = unpacker.COMMANDS_OFFSET + (8 * 8 + 5) * unpacker.BUTTON_STRIDE
        self.assertEqual(packed[at : at + 4], bytes([0x05, 0x81, cbp.EXP_TARGET_OFF, 0]))
        at += unpacker.BUTTON_STRIDE
        self.assertEqual(packed[at : at + 4], bytes([0x05, 0x80, 7, 0]))

    def test_firmware_values_match(self):
        import re
        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc",
                            "midi_defines.h")
        with open(path) as handle:
            header = handle.read()
        for name, value in (("CMD_EXP_MODE", cbp.CMD_EXP_MODE), ("EXP_TARGET_OFF", cbp.EXP_TARGET_OFF),
                            ("EXP_TARGET_RESET", cbp.EXP_TARGET_OWN),
                            ("EXP_TARGET_SPEED", cbp.EXP_TARGET_SPEED)):
            m = re.search(rf"#define\s+{name}\s+\((0x[0-9A-Fa-f]+|\d+)\)", header)
            self.assertEqual(int(m.group(1), 0), value, name)


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
        at = unpacker.COMMANDS_OFFSET + (6 * 8 + 4) * unpacker.BUTTON_STRIDE
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


class Fm3TemplateTest(unittest.TestCase):
    """The FM3 template packs and reads back as the template describes."""

    @classmethod
    def setUpClass(cls):
        packed = packer.pack_config(read_config_csv(FM3_CSV))
        tables = unpacker.unpack_config(packed)
        cls.banks, cls.buttons, cls.enter = tables[1], tables[2], tables[5]

    def button(self, bank, btn):
        b = self.buttons
        return b[(b["Bank_Number"].astype(str) == str(bank)) & (b["Button_Identifier"] == btn)].iloc[0]

    def test_preset_banks_load_their_preset(self):
        for bank in (0, 7, 29):
            row = self.enter[self.enter["Bank_Number"].astype(str) == str(bank)].iloc[0]
            self.assertEqual(row["A_CommandType"], "PC")
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), str(bank))

    def test_scene_buttons(self):
        for btn, value in (("1", 0), ("4", 3), ("A", 4), ("B", 5)):
            row = self.button(3, btn)
            self.assertEqual(row["A_CommandType"], "CC")
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), "34")
            self.assertEqual(norm(row["A_OnValue_(CC/PB)"]), str(value))
            self.assertEqual(norm(row["A_OffValue_(CC)"]), "128")   # sends nothing
            self.assertEqual(row["A_Toggle_(CC/PB/Note)"], "Y")
            self.assertEqual(norm(row["Group"]), "1")

    def test_tap_sends_only_on_the_press(self):
        row = self.button(0, "D")
        self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), "14")
        self.assertEqual(norm(row["A_OffValue_(CC)"]), "128")
        self.assertEqual(row["A_Toggle_(CC/PB/Note)"], "N")

    def test_looper_and_fx_banks(self):
        names = self.banks.set_index(self.banks["Bank_Number"].astype(str))["Bank_Name_Large"]
        self.assertEqual(names["30"], "LOOP")
        self.assertEqual(names["31"], "FX")
        self.assertEqual(norm(self.button(30, "1")["A_Number_(PC/CC/Note)"]), "20")
        self.assertEqual(self.button(31, "A")["A_Toggle_(CC/PB/Note)"], "Y")


class HxStompTemplateTest(unittest.TestCase):
    """The HX Stomp template packs and reads back as the template describes."""

    @classmethod
    def setUpClass(cls):
        packed = packer.pack_config(read_config_csv(HX_STOMP_CSV))
        tables = unpacker.unpack_config(packed)
        cls.globals, cls.banks, cls.buttons, cls.enter = tables[0], tables[1], tables[2], tables[5]

    def button(self, bank, btn):
        b = self.buttons
        return b[(b["Bank_Number"].astype(str) == str(bank)) & (b["Button_Identifier"] == btn)].iloc[0]

    def test_preset_banks_load_their_preset(self):
        names = self.banks.set_index(self.banks["Bank_Number"].astype(str))["Bank_Name_Large"]
        for bank, name in ((0, "01A"), (4, "02B"), (29, "10C")):
            row = self.enter[self.enter["Bank_Number"].astype(str) == str(bank)].iloc[0]
            self.assertEqual(row["A_CommandType"], "PC")
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), str(bank))
            self.assertEqual(names[str(bank)], name)

    def test_snapshot_buttons(self):
        for btn, value in (("1", 0), ("2", 1), ("3", 2)):
            row = self.button(5, btn)
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), "69")
            self.assertEqual(norm(row["A_OnValue_(CC/PB)"]), str(value))
            self.assertEqual(norm(row["A_OffValue_(CC)"]), "128")   # sends nothing
            self.assertEqual(norm(row["Group"]), "1")

    def test_footswitches_tuner_and_tap(self):
        for btn, number in (("A", "49"), ("B", "50"), ("C", "51"), ("4", "68")):
            row = self.button(0, btn)
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), number)
            self.assertEqual(row["A_Toggle_(CC/PB/Note)"], "Y")
        tap = self.button(0, "D")
        self.assertEqual(norm(tap["A_Number_(PC/CC/Note)"]), "64")
        self.assertEqual(norm(tap["A_OffValue_(CC)"]), "128")

    def test_looper_and_stomp_banks(self):
        self.assertEqual(norm(self.button(30, "1")["A_Number_(PC/CC/Note)"]), "60")
        self.assertEqual(norm(self.button(30, "2")["A_OnValue_(CC/PB)"]), "0")    # overdub
        self.assertEqual(norm(self.button(31, "B")["A_Number_(PC/CC/Note)"]), "53")  # FS5
        self.assertEqual(norm(self.button(31, "4")["A_OnValue_(CC/PB)"]), "8")    # next snapshot

    def test_expression_pedals_are_exp1_and_exp2(self):
        values = self.globals.set_index("Label")["Value"]
        self.assertEqual((norm(values["Exp1_CC"]), norm(values["Exp2_CC"])), ("1", "2"))


class KemperPlayerTemplateTest(unittest.TestCase):
    """The Kemper Player template packs and reads back as the template describes."""

    @classmethod
    def setUpClass(cls):
        packed = packer.pack_config(read_config_csv(KEMPER_PLAYER_CSV))
        tables = unpacker.unpack_config(packed)
        cls.globals, cls.banks, cls.buttons = tables[0], tables[1], tables[2]
        cls.enter, cls.setlist = tables[5], tables[8]

    def button(self, bank, btn):
        b = self.buttons
        return b[(b["Bank_Number"].astype(str) == str(bank)) & (b["Button_Identifier"] == btn)].iloc[0]

    def test_rig_banks_preselect_their_bank(self):
        names = self.banks.set_index(self.banks["Bank_Number"].astype(str))
        for bank, name, rigs in ((0, "BK01", "1 to 5"), (3, "BK04", "16 to 20"), (9, "BK10", "46 to 50")):
            row = self.enter[self.enter["Bank_Number"].astype(str) == str(bank)].iloc[0]
            self.assertEqual(row["A_CommandType"], "CC")
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), "47")
            self.assertEqual(norm(row["A_OnValue_(CC/PB)"]), str(bank))
            self.assertEqual(names.loc[str(bank), "Bank_Name_Large"], name)
            self.assertEqual(names.loc[str(bank), "Bank_Info_Small"], rigs)

    def test_slot_buttons(self):
        for btn, number in (("1", "50"), ("2", "51"), ("3", "52"), ("4", "53"), ("A", "54")):
            row = self.button(7, btn)
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), number)
            self.assertEqual(norm(row["A_OnValue_(CC/PB)"]), "1")
            self.assertEqual(norm(row["A_OffValue_(CC)"]), "128")   # sends nothing
            self.assertEqual(row["A_Toggle_(CC/PB/Note)"], "Y")
            self.assertEqual(norm(row["Group"]), "1")

    def test_effect_buttons_and_tap(self):
        for btn, number in (("B", "75"), ("C", "76")):
            row = self.button(0, btn)
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), number)
            self.assertEqual(row["A_Toggle_(CC/PB/Note)"], "Y")
        tap = self.button(0, "D")
        self.assertEqual(norm(tap["A_Number_(PC/CC/Note)"]), "30")
        self.assertEqual(norm(tap["A_OffValue_(CC)"]), "128")

    def test_fx_and_tool_banks(self):
        names = self.banks.set_index(self.banks["Bank_Number"].astype(str))["Bank_Name_Large"]
        self.assertEqual((names["10"], names["11"]), ("FX", "TOOL"))
        for btn, number in (("1", "17"), ("2", "18"), ("3", "26"), ("4", "28"), ("D", "78")):
            self.assertEqual(norm(self.button(10, btn)["A_Number_(PC/CC/Note)"]), number)
        # The tuner latches: 127 to open it and 0 to close it
        self.assertEqual(norm(self.button(11, "1")["A_Number_(PC/CC/Note)"]), "31")
        self.assertEqual(norm(self.button(11, "1")["A_OffValue_(CC)"]), "0")
        # What flips on any value sends 127 on both halves of the toggle
        for btn, number in (("2", "33"), ("3", "34"), ("4", "35")):
            row = self.button(11, btn)
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), number)
            self.assertEqual(norm(row["A_OnValue_(CC/PB)"]), "127")
            self.assertEqual(norm(row["A_OffValue_(CC)"]), "127")

    def test_only_the_twelve_used_banks_are_in_the_setlist(self):
        values = self.globals.set_index("Label")["Value"]
        self.assertEqual(values["Setlist_Mode"], "Y")
        self.assertEqual([norm(b) for b in self.setlist["Bank_Number"]], [str(b) for b in range(12)])

    def test_expression_pedals_are_wah_and_volume(self):
        values = self.globals.set_index("Label")["Value"]
        self.assertEqual((norm(values["Exp1_CC"]), norm(values["Exp2_CC"])), ("1", "7"))


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


class PedalEditorTest(unittest.TestCase):
    """Editing on the pedal (firmware 0.53)."""

    FIRMWARE = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core")

    def firmware(self, name):
        with open(os.path.join(self.FIRMWARE, name)) as handle:
            return handle.read()

    @staticmethod
    def pack_lock(value):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        g.loc[g["Label"] == "Edit_Lock", "Value"] = value
        return packer.pack_config(sections)

    def test_lock_byte_matches_firmware(self):
        """The setting the firmware reads before opening the editor."""
        import re

        text = self.firmware(os.path.join("Inc", "midi_defines.h"))
        byte = re.search(r"^#define\s+GLOBAL_SETTINGS_EDIT_LOCK\s+\((\d+)\)", text, re.M)
        self.assertEqual(int(byte.group(1)), 42)
        self.assertLess(42, unpacker.GLOBAL_SIZE)   # still inside the global settings

    def test_lock_round_trip(self):
        for text, byte in (("N", 0), ("Y", 1)):
            packed = self.pack_lock(text)
            self.assertEqual(packed[42], byte, text)
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual(back["Edit_Lock"], text, text)

    def test_lock_defaults_to_open(self):
        """A configuration written before 0.53 leaves that byte erased."""
        image = bytearray(self.pack_lock("Y"))
        image[42] = 0xFF
        back = unpacker.unpack_config(bytes(image))[0].set_index("Label")["Value"]
        self.assertEqual(back["Edit_Lock"], "N")
        sections = read_config_csv(DEMO_CSV)
        sections["Global_Settings"] = sections["Global_Settings"][
            sections["Global_Settings"]["Label"] != "Edit_Lock"]
        self.assertEqual(packer.pack_config(sections)[42], 0)

    def test_editor_settings_exist(self):
        """Every setting the editor offers is a real global settings byte."""
        import re

        editor = self.firmware(os.path.join("Src", "editor.c"))
        defines = self.firmware(os.path.join("Inc", "midi_defines.h"))
        known = dict(re.findall(r"^#define\s+(GLOBAL_SETTINGS_\w+)\s+\((\d+)\)", defines, re.M))
        used = re.findall(r"\{\"[^\"]+\",\s*(GLOBAL_SETTINGS_\w+)", editor)
        self.assertGreaterEqual(len(used), 10)
        # none of them twice, but for the bits of one byte (S_FLAG)
        flags = re.findall(r"\{\"[^\"]+\",\s*(GLOBAL_SETTINGS_\w+),\s*S_FLAG", editor)
        whole = [n for n in used if n not in flags]
        self.assertEqual(len(whole), len(set(whole)))
        self.assertFalse(set(whole) & set(flags))
        for name in used:
            self.assertIn(name, known, name)
            self.assertLess(int(known[name]), unpacker.GLOBAL_SIZE, name)

    def test_editor_types_are_the_tools_names(self):
        """What the editor calls a command is what the configurator calls it."""
        import re

        editor = self.firmware(os.path.join("Src", "editor.c"))
        block = re.search(r"type_names\[T_COUNT\]\s*=\s*\{([^}]*)\}", editor, re.S)
        names = re.findall(r'"([^"]+)"', block.group(1))
        self.assertEqual(names[0], "---")               # the empty command
        for name in names[1:]:
            self.assertIn(name, cbp.cmd_route_table, name)

    def test_editor_writes_one_page_at_a_time(self):
        """A command never straddles two pages, which the patch refuses."""
        page = 2048
        for base in (unpacker.COMMANDS_OFFSET, unpacker.LONG_PRESS_OFFSET):
            for at in range(base, base + unpacker.NUM_BANKS * 8 * unpacker.BUTTON_STRIDE, 4):
                self.assertEqual(at // page, (at + 3) // page, at)


class FakePedal:
    """A pedal in memory that answers the SysEx the slot tools use: four slots
    of flash, a target selected with SELECT_SLOT, erase, write and read."""

    def __init__(self, version="0.31", active=0, fail_write_at=None):
        self.version = version
        self.active = active
        self.target = active
        self.flash = {s: bytearray(b"\xff" * unpacker.IMAGE_SIZE) for s in range(4)}
        self.resets = 0
        self.fail_write_at = fail_write_at  # a byte offset whose write fails, as 0.71 answers
        self.answer = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_version(self, timeout=1.0):
        return self.version

    def firmware_at_least(self, major, minor, timeout=1.0):
        from lib.midiDevice import version_at_least
        return version_at_least(self.version, major, minor)

    def valid(self):
        # The firmware's rule: a slot holds a configuration when its name is
        # sixteen printable characters
        return [s for s, f in self.flash.items() if all(0x20 <= b <= 0x7E for b in f[16:32])]

    def select_slot(self, slot=None, timeout=1.0):
        if slot is not None:
            self.target = slot
        return self.target, self.active, self.valid()

    def read_settings(self, num_bytes, progress=None, start=0):
        return bytes(self.flash[self.target][start:start + num_bytes])

    def send(self, data):
        from lib import midiDevice as md
        if data[0] == md.SYSEX_CMD_ERASE_FLASH:
            self.flash[self.target] = bytearray(b"\xff" * unpacker.IMAGE_SIZE)
        elif data[0] == md.SYSEX_CMD_WRITE_FLASH:
            at = ((data[1] << 7) | data[2]) * 16
            nib = data[3:]
            self.flash[self.target][at:at + 16] = bytes(
                (nib[2 * i] << 4) | nib[2 * i + 1] for i in range(16))
            self.answer = [1] if at == self.fail_write_at else []
        elif data[0] == md.SYSEX_CMD_RESET:
            self.resets += 1

    def wait_for_sysex(self, expected_rsp, timeout=2.0):
        answer, self.answer = self.answer, []
        return answer


class BackupSlotsTest(unittest.TestCase):
    """Backup_Slots.py: every slot out to a folder, and back, byte for byte."""

    @classmethod
    def setUpClass(cls):
        import Backup_Slots
        from lib.slotIO import pack_sections, select_slot, write_image
        cls.tool = Backup_Slots
        cls.pack_sections = staticmethod(pack_sections)
        cls.select_slot = staticmethod(select_slot)
        cls.write_image = staticmethod(write_image)

    def setUp(self):
        # The pause between chunks paces a real pedal; the fake one needs none,
        # and with it these tests spent a hundred seconds asleep
        from unittest import mock
        import lib.slotIO as slot_io
        patcher = mock.patch.object(slot_io, "time", mock.Mock(sleep=lambda s: None))
        patcher.start()
        self.addCleanup(patcher.stop)

    def sections(self, name):
        s = read_config_csv(DEMO_CSV)
        g = s["Global_Settings"]
        g.loc[g["Label"] == "ConfigName", "Value"] = name
        return s

    def pedal_with(self, names):
        """A pedal whose slots hold the demo under the given names, {slot: name}."""
        pedal = FakePedal()
        for slot, name in names.items():
            self.select_slot(pedal, slot)
            self.write_image(pedal, *self.pack_sections(self.sections(name)))
        self.select_slot(pedal, None)
        return pedal

    def run_tool(self, pedal, *argv):
        import argparse
        import contextlib
        import io
        from unittest import mock
        args = argparse.Namespace(folder=argv[1], yes=True)
        with mock.patch.object(self.tool, "MidiCommander", lambda: pedal), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = self.tool.backup(args) if argv[0] == "backup" else self.tool.restore(args)
        return code, out.getvalue()

    def test_backup_then_restore_is_byte_exact(self):
        import tempfile
        source = self.pedal_with({0: "DEMO ONE", 2: "DEMO THREE"})
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "bk")
            self.assertEqual(self.run_tool(source, "backup", folder)[0], 0)
            self.assertEqual(sorted(os.listdir(folder)), ["backup.txt", "slot1.csv", "slot3.csv"])
            with open(os.path.join(folder, "backup.txt"), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("Slot 1: 'DEMO ONE", text)
            self.assertIn("Slot 2: empty", text)

            target = FakePedal()
            code, _ = self.run_tool(target, "restore", folder)
            self.assertEqual(code, 0)
            for slot in range(4):
                self.assertEqual(bytes(target.flash[slot]), bytes(source.flash[slot]), f"slot {slot + 1}")
            self.assertEqual(target.resets, 1)   # one restart for the whole restore

    def test_restore_leaves_other_slots_alone(self):
        import tempfile
        source = self.pedal_with({0: "DEMO ONE"})
        target = self.pedal_with({0: "OLD ONE", 1: "KEEP ME"})
        keep = bytes(target.flash[1])
        with tempfile.TemporaryDirectory() as tmp:
            self.run_tool(source, "backup", tmp)
            code, out = self.run_tool(target, "restore", tmp)
        self.assertEqual(code, 0)
        self.assertEqual(bytes(target.flash[1]), keep)
        self.assertEqual(bytes(target.flash[0]), bytes(source.flash[0]))
        self.assertIn("Left as they are: slot 2, 3, 4", out)

    def test_bad_file_writes_nothing(self):
        import tempfile
        source = self.pedal_with({0: "DEMO ONE", 1: "DEMO TWO"})
        target = self.pedal_with({0: "OLD ONE"})
        before = {s: bytes(f) for s, f in target.flash.items()}
        with tempfile.TemporaryDirectory() as tmp:
            self.run_tool(source, "backup", tmp)
            with open(os.path.join(tmp, "slot2.csv"), "w", encoding="utf-8") as f:
                f.write("* Global_Settings\nnot,a,configuration\n")
            code, out = self.run_tool(target, "restore", tmp)
        self.assertEqual(code, 1)
        self.assertIn("slot2.csv", out)
        self.assertEqual({s: bytes(f) for s, f in target.flash.items()}, before)
        self.assertEqual(target.resets, 0)

    def test_slot_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("slot1.csv", "Slot4.CSV", "slot5.csv", "slot1.csv.bak", "notes.csv"):
                open(os.path.join(tmp, name), "w").close()
            self.assertEqual(sorted(self.tool.slot_files(tmp)), [0, 3])

    def test_empty_pedal(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_tool(FakePedal(), "backup", os.path.join(tmp, "x"))
        self.assertEqual(code, 4)


class KemperModeTest(unittest.TestCase):
    """Two way talk with a Kemper Profiler (firmware 0.55)."""

    FIRMWARE = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core")

    def firmware(self, name):
        with open(os.path.join(self.FIRMWARE, name)) as handle:
            return handle.read()

    def kemper_c(self):
        return self.firmware(os.path.join("Src", "kemper.c"))

    def define(self, text, name):
        import re

        found = re.search(r"^#define\s+" + name + r"\s+\((0x[0-9A-Fa-f]+|\d+)\)", text, re.M)
        self.assertIsNotNone(found, name)
        return int(found.group(1), 0)

    def test_dialect_matches_firmware(self):
        """The tools and the pedal speak the amp's numbers the same way."""
        text = self.kemper_c()
        self.assertEqual((self.define(text, "KEMPER_MANUF_1"),
                          self.define(text, "KEMPER_MANUF_2"),
                          self.define(text, "KEMPER_MANUF_3")), kp.MANUFACTURER)
        self.assertEqual(self.define(text, "KEMPER_PRODUCT"), kp.PRODUCT)
        self.assertEqual(self.define(text, "KEMPER_DEVICE"), kp.DEVICE)
        self.assertEqual(self.define(text, "KEMPER_FN_PARAM"), kp.FN_PARAM)
        self.assertEqual(self.define(text, "KEMPER_FN_STRING"), kp.FN_STRING)
        self.assertEqual(self.define(text, "KEMPER_FN_REQ_PARAM"), kp.FN_REQ_PARAM)
        self.assertEqual(self.define(text, "KEMPER_FN_REQ_STRING"), kp.FN_REQ_STRING)
        self.assertEqual(self.define(text, "KEMPER_FN_BEACON"), kp.FN_BEACON)
        self.assertEqual(self.define(text, "KEMPER_PAGE_RIG"), kp.PAGE_RIG)
        self.assertEqual(self.define(text, "KEMPER_PARAM_RIG_NAME"), kp.PARAM_RIG_NAME)
        self.assertEqual(self.define(text, "KEMPER_PARAM_ON_OFF"), kp.PARAM_ON_OFF)
        self.assertEqual(self.define(text, "KEMPER_BEACON_SET"), kp.BEACON_SET)
        self.assertEqual(self.define(text, "KEMPER_BEACON_FIRST"), kp.BEACON_FIRST)
        self.assertEqual(self.define(text, "KEMPER_BEACON_AGAIN"), kp.BEACON_AGAIN)
        self.assertEqual(self.define(text, "KEMPER_BEACON_LEASE"), kp.BEACON_LEASE)

    def test_modules_match_firmware(self):
        """The same eight modules, each with its page and its Control Change."""
        import re

        table = self.kemper_c().split("modules[] = {", 1)[1].split("};", 1)[0]
        rows = [tuple(int(v, 0) for v in row)
                for row in re.findall(r"\{\s*(0x[0-9A-Fa-f]+),\s*(\d+),\s*(\d+)\s*\}", table)]
        self.assertEqual(rows, [(page, cc, tails) for _, page, cc, tails in kp.MODULES])

    def test_the_two_asked_for_are_the_last_two(self):
        """The amp reports six by itself; the delay and the reverb it does not."""
        text = self.kemper_c()
        first = self.define(text, "KEMPER_FIRST_ASKED")
        self.assertEqual([name for name, _, _, _ in kp.MODULES][first:], kp.ASKED)
        self.assertEqual([name for name, _, _, _ in kp.MODULES][:first], kp.PUSHED)

    def test_beacon_is_the_message_the_amp_expects(self):
        """Byte for byte, the frame the Profiler answers to."""
        self.assertEqual(kp.beacon(kp.BEACON_FIRST),
                         [0xF0, 0x00, 0x20, 0x33, 0x02, 0x7F,
                          0x7E, 0x00, 0x40, 0x02, 0x23, 0x05, 0xF7])
        self.assertEqual(kp.beacon()[10], kp.BEACON_AGAIN)   # the ones that keep it alive

    def test_the_amp_answers_with_zeroes(self):
        """It puts zeroes where the question carried the product and the device."""
        answer = kp.rig_name("AC30")
        self.assertEqual(answer[4:6], [0x00, 0x00])
        self.assertTrue(kp.is_kemper(answer))
        self.assertEqual(kp.function(answer), kp.FN_STRING)
        # and the firmware knows a message of the amp's by the maker's three
        # bytes alone, never by the two that follow
        source = self.kemper_c()
        reading = source.split("void kemper_sysex_chunk", 1)[1]
        self.assertIn("rx[1] == KEMPER_MANUF_1", reading)
        self.assertNotIn("KEMPER_PRODUCT", reading)
        self.assertNotIn("KEMPER_DEVICE", reading)

    def test_module_ccs_are_the_template_buttons(self):
        """Bank 10 of the Kemper template sends exactly the module CCs."""
        sections = read_config_csv(KEMPER_PLAYER_CSV)
        buttons = sections["Button_Settings"]
        bank = buttons[buttons["Bank_Number"].astype(str).str.strip() == "10"]
        numbers = [int(float(v)) for v in bank["A_Number_(PC/CC/Note)"][:4]]
        self.assertEqual(numbers, [kp.MODULE_CCS[name]
                                   for name in ("Stomp A", "Stomp B", "Delay", "Reverb")])
        toggles = [str(v).strip().upper() for v in bank["A_Toggle_(CC/PB/Note)"][:4]]
        self.assertEqual(toggles, ["Y"] * 4)    # or their LEDs could not follow

    def test_setting_round_trip(self):
        for text, byte in (("N", 0), ("Y", 1)):
            sections = read_config_csv(DEMO_CSV)
            g = sections["Global_Settings"]
            g.loc[g["Label"] == "Kemper_Mode", "Value"] = text
            packed = packer.pack_config(sections)
            self.assertEqual(packed[43], byte, text)
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual(back["Kemper_Mode"], text, text)

    def test_setting_defaults_to_off(self):
        """A configuration written before 0.55 says nothing, and stays quiet."""
        sections = read_config_csv(DEMO_CSV)
        sections["Global_Settings"] = sections["Global_Settings"][
            sections["Global_Settings"]["Label"] != "Kemper_Mode"]
        self.assertEqual(packer.pack_config(sections)[43], 0)
        image = bytearray(packer.pack_config(read_config_csv(DEMO_CSV)))
        image[43] = 0xFF        # an erased byte is not a yes either
        back = unpacker.unpack_config(bytes(image))[0].set_index("Label")["Value"]
        self.assertEqual(back["Kemper_Mode"], "N")

    def test_the_template_asks_for_it(self):
        """The Player answers over the same USB link, so the template says yes."""
        globals_ = read_config_csv(KEMPER_PLAYER_CSV)["Global_Settings"].set_index("Label")
        self.assertEqual(str(globals_.loc["Kemper_Mode", "Value"]).strip(), "Y")

    def test_the_make_believe_amp_answers_what_is_asked(self):
        """Kemper_Sim, without a pedal or a port in sight."""
        import mido

        class Port:
            def __init__(self, queue=None):
                self.queue = list(queue or [])
                self.sent = []

            def poll(self):
                return self.queue.pop(0) if self.queue else None

            def send(self, message):
                self.sent.append(message)

        asked = [mido.Message("sysex", data=kp.beacon()[1:-1]),
                 mido.Message("sysex", data=(list(kp.HEADER) + [kp.FN_REQ_STRING, 0x00,
                                             kp.PAGE_RIG, kp.PARAM_RIG_NAME])[1:]),
                 mido.Message("sysex", data=(list(kp.HEADER) + [kp.FN_REQ_PARAM, 0x00,
                                             kp.MODULE_PAGES["Delay"], kp.PARAM_ON_OFF])[1:])]
        inport, outport = Port(asked), Port()
        amp = kemper_sim.FakeKemper(inport, outport)
        amp.set_module("Delay", True)
        self.assertEqual(amp.poll(), ["beacon", "rig name", "Delay"])
        self.assertEqual(amp.beacons, 1)
        answers = [[0xF0] + list(m.data) + [0xF7] for m in outport.sent]
        self.assertIn(kp.rig_name(amp.rig), answers)
        self.assertIn(kp.module_state("Delay", True), answers)
        self.assertTrue(all(kp.is_kemper(a) for a in answers))


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


class GlobalButtonTest(unittest.TestCase):
    """Global buttons: one bank holds what is the same everywhere (0.57)."""

    FIRMWARE = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core")

    def source(self, *name):
        with open(os.path.join(self.FIRMWARE, *name)) as handle:
            return handle.read()

    def test_constants_match_firmware(self):
        import re

        header = self.source("Inc", "flash_midi_settings.h")
        bit = re.search(r"^#define\s+BUTTON_GLOBAL\s+\((0x[0-9A-Fa-f]+)\)", header, re.M)
        self.assertIsNotNone(bit)
        self.assertEqual(int(bit.group(1), 16), cbp.BUTTON_GLOBAL)
        # It is a bit of its own in the LED mode byte, taken by nothing else
        taken = [int(v, 16) for v in re.findall(
            r"^#define\s+(?:BUTTON_TEMPO_FLASH|BUTTON_MOMENTARY_HOLD)\s+\((0x[0-9A-Fa-f]+)\)",
            header, re.M)]
        group = int(re.search(r"^#define\s+BUTTON_GROUP_MASK\s+\((0x[0-9A-Fa-f]+)\)",
                              header, re.M).group(1), 16)
        shift = int(re.search(r"^#define\s+BUTTON_GROUP_SHIFT\s+\((\d+)\)", header, re.M).group(1))
        taken.append(group << shift)
        taken.append(int(re.search(r"^#define\s+LED_MODE_MASK\s+\((0x[0-9A-Fa-f]+)\)",
                                   header, re.M).group(1), 16))
        for other in taken:
            self.assertEqual(other & cbp.BUTTON_GLOBAL, 0, hex(other))

        defines = self.source("Inc", "midi_defines.h")
        byte = re.search(r"^#define\s+GLOBAL_SETTINGS_GLOBAL_BANK\s+\((\d+)\)", defines, re.M)
        self.assertIsNotNone(byte)
        import lib.settingsBinaryPacker as sbp
        self.assertEqual(int(byte.group(1)), sbp.GLOBAL_SETTINGS_GLOBAL_BANK)

    def test_firmware_redirects_every_list(self):
        """All three command lists of a button go through the same redirect."""
        source = self.source("Src", "switch_router.c")
        self.assertEqual(source.count("\tpage = button_bank(page, sw);"), 3)
        # And the bank set aside never follows itself
        self.assertIn("bank == g", source)

    def test_packs_in_the_led_byte(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Button_Settings"].copy()
        df["Global"] = ""
        i = df.index[(df["Bank_Number"].astype(str) == "5") & (df["Button_Identifier"] == "B")][0]
        df.at[i, "Light_Mode"] = "Reverse"
        df.at[i, "Group"] = "2"
        base = pack_config({**sections, "Button_Settings": df})
        df.at[i, "Global"] = "Y"
        packed = pack_config({**sections, "Button_Settings": df})
        at = unpacker.LED_MODES_OFFSET + 5 * 8 + unpacker.BUTTON_IDS.index("B")
        self.assertEqual(base[at], 0x21)
        self.assertEqual(packed[at], 0x29)
        self.assertEqual(packed[:at] + packed[at + 1:], base[:at] + base[at + 1:])

    def test_the_bank_is_held_as_one_more(self):
        """0 means no bank set aside, so an older configuration redirects nothing."""
        sections = read_config_csv(DEMO_CSV)
        df = sections["Global_Settings"].copy()
        where = df.index[df["Label"] == "Global_Bank"][0]
        for value, byte in (("0", 1), ("30", 31), ("31", 32), ("Off", 0), ("", 0)):
            df.at[where, "Value"] = value
            packed = pack_config({**sections, "Global_Settings": df})
            self.assertEqual(packed[44], byte, value)
            back = unpacker.unpack_global_settings(packed)
            row = back[back["Label"] == "Global_Bank"]["Value"].iloc[0]
            self.assertEqual(row, "Off" if byte == 0 else str(byte - 1), value)
        for bad in ("32", "-1", "twelve"):
            df.at[where, "Value"] = bad
            with self.assertRaises(ValueError, msg=bad):
                pack_config({**sections, "Global_Settings": df})

    def test_older_configurations_have_none(self):
        sections = read_config_csv(SAMPLE_CSV)
        self.assertNotIn("Global", sections["Button_Settings"].columns)
        packed = pack_config(sections)
        self.assertEqual(packed[44], 0)
        _, _, decoded, *_ = unpacker.unpack_config(packed)
        self.assertTrue((decoded["Global"] == "").all())

    def test_erased_flash_has_none(self):
        blank = bytes([0xFF]) * unpacker.CONFIG_SIZE
        _, _, df, *_ = unpacker.unpack_config(blank)
        self.assertTrue((df["Global"] == "").all())
        settings = unpacker.unpack_global_settings(blank)
        self.assertEqual(settings[settings["Label"] == "Global_Bank"]["Value"].iloc[0], "Off")

    def test_values(self):
        for cell, want in (("", False), (float("nan"), False), ("N", False),
                           ("Y", True), ("yes", True), ("1.0", True)):
            self.assertEqual(cbp.button_global_value(cell), want, cell)
        with self.assertRaises(ValueError):
            cbp.button_global_value("maybe")

    def test_demo_stores_the_tap_once(self):
        """The songs' tap is written in the bank set aside and followed."""
        sections = read_config_csv(DEMO_CSV)
        settings = sections["Global_Settings"]
        self.assertEqual(
            str(settings[settings["Label"] == "Global_Bank"]["Value"].iloc[0]), "30")

        buttons = sections["Button_Settings"]

        def row(bank, btn):
            return buttons[(buttons["Bank_Number"].astype(str) == str(bank))
                           & (buttons["Button_Identifier"].astype(str) == btn)].iloc[0]

        stored = row(30, "D")
        self.assertEqual(norm(stored["A_CommandType"]), "Tap")
        self.assertEqual(norm(stored["Label"]), "TAP")
        self.assertEqual(norm(stored["Global"]), "")     # it is the one stored

        # Song 1 keeps its own D, which is the way to its second page
        self.assertEqual(norm(row(12, "D")["Global"]), "")
        followers = [b for b in range(13, 30)]
        for bank in followers:
            here = row(bank, "D")
            self.assertEqual(norm(here["Global"]), "Y", bank)
            # Nothing of its own: the whole button comes from bank 30
            self.assertEqual(norm(here["A_CommandType"]), "", bank)
            self.assertEqual(norm(here["Label"]), "", bank)

        # What it saves: one list instead of one per bank
        self.assertEqual(len(followers) * cbp.MIDI_NUM_COMMANDS_PER_SWITCH * 4, 680)


class ComboTest(unittest.TestCase):
    """Two switches pressed together run a list of their own (0.59)."""

    FIRMWARE = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core")

    def source(self, *name):
        with open(os.path.join(self.FIRMWARE, *name)) as handle:
            return handle.read()

    def combos(self, rows):
        return pd.DataFrame(rows, columns=packer.COMBO_COLUMNS)

    def packed(self, rows, base=None):
        sections = dict(read_config_csv(base or DEMO_CSV))
        sections[packer.COMBO_SECTION] = self.combos(rows)
        return pack_config(sections)

    def table(self, packed):
        return packed[unpacker.COMBOS_OFFSET : unpacker.COMBOS_OFFSET + 48]

    def test_constants_agree(self):
        import re

        self.assertEqual(packer.COMBO_COUNT, unpacker.COMBO_COUNT)
        self.assertEqual(packer.COMBO_COLUMNS, unpacker.COMBO_COLUMNS)
        header = self.source("Inc", "flash_midi_settings.h")
        for name, want in (("COMBO_EVERY_BANK", 0), ("COMBO_UNUSED", 0xFF)):
            m = re.search(rf"^#define\s+{name}\s+\((0x[0-9A-Fa-f]+|\d+)\)", header, re.M)
            self.assertIsNotNone(m, name)
            self.assertEqual(int(m.group(1), 0), want, name)
        # The list is named as a Macro names it
        defines = self.source("Inc", "midi_defines.h")
        for i, name in enumerate(cbp.MACRO_LISTS):
            m = re.search(rf"^#define\s+MACRO_LIST_{name.upper()}\s+\((\d+)\)", defines, re.M)
            self.assertEqual(int(m.group(1)), i, name)
        # They take exactly the room the slot had left
        self.assertEqual(unpacker.CONFIG_SIZE, 12 * 2048)

    def test_packs_the_table(self):
        packed = self.packed([
            {"Switches": "1+2", "Bank": "All", "Run_Bank": "31", "Run_Button": "A", "Run_List": "Short"},
            {"Switches": "D + a", "Bank": "3", "Run_Bank": "5", "Run_Button": "b", "Run_List": "long"},
            {"Switches": "3 4", "Bank": "", "Run_Bank": "0", "Run_Button": "C", "Run_List": ""},
            {"Switches": "C,2", "Bank": "31", "Run_Bank": "30", "Run_Button": "D", "Run_List": "Double"},
        ])
        table = self.table(packed)
        self.assertEqual(table[:16], bytes([0x10, 0, 31, 0x04,  0x74, 4, 5, 0x15,
                                            0x32, 0, 0, 0x06,   0x61, 32, 30, 0x27]))
        self.assertEqual(table[16:], b"\xff" * 32)
        back = unpacker.unpack_combos(packed)
        self.assertEqual(back.to_dict("records"), [
            {"Switches": "1+2", "Bank": "All", "Run_Bank": "31", "Run_Button": "A", "Run_List": "Short"},
            {"Switches": "A+D", "Bank": "3", "Run_Bank": "5", "Run_Button": "B", "Run_List": "Long"},
            {"Switches": "3+4", "Bank": "All", "Run_Bank": "0", "Run_Button": "C", "Run_List": "Short"},
            {"Switches": "2+C", "Bank": "31", "Run_Bank": "30", "Run_Button": "D", "Run_List": "Double"},
        ])
        # and nothing else moved
        self.assertEqual(packed[: unpacker.COMBOS_OFFSET], pack_csv(DEMO_CSV)[: unpacker.COMBOS_OFFSET])

    def test_rows_without_switches_are_left_out(self):
        packed = self.packed([
            {"Switches": "", "Bank": "All", "Run_Bank": "1", "Run_Button": "A", "Run_List": "Short"},
            {"Switches": float("nan"), "Bank": "", "Run_Bank": "", "Run_Button": "", "Run_List": ""},
            {"Switches": "1+2", "Bank": "All", "Run_Bank": "1", "Run_Button": "A", "Run_List": "Short"},
        ])
        self.assertEqual(self.table(packed)[:4], bytes([0x10, 0, 1, 0x04]))
        self.assertEqual(len(unpacker.unpack_combos(packed)), 1)

    def test_refuses_what_it_cannot_store(self):
        good = {"Switches": "1+2", "Bank": "All", "Run_Bank": "1", "Run_Button": "A", "Run_List": "Short"}
        for field, bad in (("Switches", "1+1"), ("Switches", "1+E"), ("Switches", "1"), ("Switches", "1+2+3"),
                           ("Bank", "32"), ("Bank", "-1"), ("Bank", "some"),
                           ("Run_Bank", "32"), ("Run_Bank", ""), ("Run_Button", "E"), ("Run_Button", ""),
                           ("Run_List", "Triple")):
            with self.assertRaises(ValueError, msg=f"{field}={bad}"):
                self.packed([{**good, field: bad}])
        # the same pair twice for the same bank, whichever way round
        with self.assertRaises(ValueError):
            self.packed([good, {**good, "Switches": "2+1", "Run_Bank": "2"}])
        # but for another bank it is how one bank changes what the pair does
        self.packed([good, {**good, "Bank": "4"}])
        pairs = [f"{a}+{b}" for i, a in enumerate(packer.BUTTON_IDS) for b in packer.BUTTON_IDS[i + 1:]]
        self.packed([{**good, "Switches": p} for p in pairs[:packer.COMBO_COUNT]])
        with self.assertRaises(ValueError):
            self.packed([{**good, "Switches": p} for p in pairs[:packer.COMBO_COUNT + 1]])

    def test_older_configurations_have_none(self):
        sections = read_config_csv(SAMPLE_CSV)
        self.assertNotIn(packer.COMBO_SECTION, sections)
        packed = pack_config(sections)
        self.assertEqual(self.table(packed), b"\xff" * 48)
        self.assertEqual(packed[45], 8)   # and the window is the default
        # An older dump stops before the table, and erased flash is none either
        self.assertEqual(len(unpacker.unpack_combos(packed[: unpacker.COMBOS_OFFSET])), 0)
        self.assertEqual(len(unpacker.unpack_combos(b"\xff" * unpacker.CONFIG_SIZE)), 0)
        blank = unpacker.unpack_global_settings(b"\xff" * unpacker.CONFIG_SIZE)
        self.assertEqual(blank[blank["Label"] == "Combo_ms"]["Value"].iloc[0], "80")

    def test_invalid_entries_are_not_read(self):
        """What the firmware passes over the tools do not show either."""
        image = bytearray(pack_csv(SAMPLE_CSV))
        at = unpacker.COMBOS_OFFSET
        image[at : at + 20] = bytes([0x11, 0, 1, 0,   0x18, 0, 1, 0,   0x10, 33, 1, 0,
                                     0x10, 0, 32, 0,  0x21, 0, 2, 0x13])
        back = unpacker.unpack_combos(bytes(image))
        self.assertEqual(back["Switches"].tolist(), ["2+3"])
        source = self.source("Src", "switch_router.c")
        self.assertIn("a >= MIDI_NUM_SWITCHES || b >= MIDI_NUM_SWITCHES || a == b", source)

    def test_window(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Global_Settings"].copy()
        where = df.index[df["Label"] == "Combo_ms"][0]
        for value, byte in (("80", 8), ("20", 2), ("5", 2), ("250", 25), ("400", 25), ("", 8), ("x", 8)):
            df.at[where, "Value"] = value
            packed = pack_config({**sections, "Global_Settings": df})
            self.assertEqual(packed[45], byte, value)
            back = unpacker.unpack_global_settings(packed)
            self.assertEqual(back[back["Label"] == "Combo_ms"]["Value"].iloc[0], str(byte * 10))

    def test_csv_round_trip(self):
        import tempfile

        from lib import slotIO

        sections = dict(read_config_csv(DEMO_CSV))
        sections[packer.COMBO_SECTION] = self.combos([
            {"Switches": "1+2", "Bank": "7", "Run_Bank": "31", "Run_Button": "A", "Run_List": "Long"},
        ])
        image = packer.pack_flash_image(sections)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "back.csv")
            slotIO.save_csv(path, image[: unpacker.CONFIG_SIZE], image)
            again = read_config_csv(path)
            self.assertIn(packer.COMBO_SECTION, again)
            self.assertEqual(packer.pack_flash_image(again), image)

    def test_demo(self):
        """3+4 is the tuner everywhere, and on the first song the looper's clear."""
        sections = read_config_csv(DEMO_CSV)
        combos = sections[packer.COMBO_SECTION]
        self.assertEqual(combos["Switches"].tolist(), ["3+4", "3+4"])
        self.assertEqual(combos["Bank"].tolist(), ["All", "12"])
        buttons = sections["Button_Settings"]
        for _, c in combos.iterrows():
            row = buttons[(buttons["Bank_Number"].astype(str) == c["Run_Bank"])
                          & (buttons["Button_Identifier"] == c["Run_Button"])].iloc[0]
            self.assertEqual(norm(row["A_CommandType"]), "CC", c.to_dict())
        table = self.table(pack_config(sections))
        self.assertEqual(table[:8], bytes([0x32, 0, 30, 0x05, 0x32, 13, 30, 0x03]))


class BootBannerTest(unittest.TestCase):
    """The configuration's name crossing the display at power on (0.62)."""

    FIRMWARE = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core")

    def source(self, *name):
        with open(os.path.join(self.FIRMWARE, *name)) as handle:
            return handle.read()

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
        blank = unpacker.unpack_global_settings(b"\xff" * unpacker.CONFIG_SIZE)
        self.assertEqual(blank[blank["Label"] == "Boot_Banner"]["Value"].iloc[0], "Off")

    def test_demo_shows_it(self):
        self.assertEqual(pack_csv(DEMO_CSV)[46], 2)


class BannerTextTest(unittest.TestCase):
    """The banner's own text, kept by the pedal outside the slots (0.63)."""

    FIRMWARE = os.path.join(os.path.dirname(__file__), "..", "..", "firmware")

    def source(self, *name):
        with open(os.path.join(self.FIRMWARE, *name)) as handle:
            return handle.read()

    def define(self, name, *path):
        import re

        m = re.search(rf"#define\s+{name}\s+\((\d+)\)", self.source(*path))
        self.assertIsNotNone(m, name)
        return int(m.group(1))

    def test_numbers_match_firmware(self):
        from lib import midiDevice as md

        self.assertEqual(self.define("SYSEX_CMD_BANNER", "Core", "Inc", "midi_defines.h"), md.SYSEX_CMD_BANNER)
        self.assertEqual(self.define("SYSEX_RSP_BANNER", "Core", "Inc", "midi_defines.h"), md.SYSEX_RSP_BANNER)
        self.assertEqual(self.define("BANNER_TEXT_MAX", "Core", "Inc", "banner_store.h"), md.BANNER_TEXT_MAX)

    def test_message_fits_the_pedal_buffer(self):
        from lib import midiDevice as md

        import re

        m = re.search(r"#define\s+SYSEX_MAX_LENGTH\s+(\d+)", self.source("USB_DEVICE", "App", "usbd_midi_if.c"))
        msg = md.banner_sysex("x" * md.BANNER_TEXT_MAX)
        self.assertLessEqual(len(msg), int(m.group(1)))
        self.assertEqual(msg[:4], [0xF0, md.MIDI_MANUF_ID, md.SYSEX_CMD_BANNER, 1])
        self.assertEqual(msg[-1], 0xF7)

    def test_text_is_cleaned(self):
        from lib import midiDevice as md

        self.assertEqual(md.banner_sysex("Añil  \t"), [0xF0, md.MIDI_MANUF_ID, md.SYSEX_CMD_BANNER, 1,
                                                          ord("A"), 0x20, ord("i"), ord("l"), 0xF7])
        self.assertEqual(md.banner_sysex(""), [0xF0, md.MIDI_MANUF_ID, md.SYSEX_CMD_BANNER, 1, 0xF7])

    def test_too_long_is_refused(self):
        from lib import midiDevice as md

        with self.assertRaises(ValueError):
            md.banner_sysex("x" * (md.BANNER_TEXT_MAX + 1))
        md.banner_sysex("x" * md.BANNER_TEXT_MAX + "   ")   # trailing spaces do not count

    def test_page_is_outside_everything_else(self):
        # 0x0803A000: past slot 3 and below 256 kB, never written by the tools
        header = self.source("Core", "Inc", "flash_midi_settings.h")
        self.assertIn("#define FLASH_BANNER_ADDR		(FLASH_SLOTN_ADDR(CONFIG_SLOTS))", header)
        page, slot = 0x800, 12 * 0x800
        slot0, journal = 0x08020000, 4 * 0x800
        banner = slot0 + slot + journal + 3 * slot
        self.assertEqual(banner, 0x0803A000)
        self.assertLessEqual(banner + page, 0x08000000 + 256 * 1024)


class LatencyTest(unittest.TestCase):
    """The pedal times its own presses (0.65): the SysEx that reads them."""

    def source(self, *path):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "firmware")
        with open(os.path.join(root, *path)) as f:
            return f.read()

    def define(self, name, *path):
        import re

        m = re.search(rf"#define\s+{name}\s+\((\d+)\)", self.source(*path))
        self.assertIsNotNone(m, name)
        return int(m.group(1))

    def test_numbers_match_firmware(self):
        from lib import midiDevice as md

        self.assertEqual(self.define("SYSEX_CMD_GET_LATENCY", "Core", "Inc", "midi_defines.h"), md.SYSEX_CMD_GET_LATENCY)
        self.assertEqual(self.define("SYSEX_RSP_GET_LATENCY", "Core", "Inc", "midi_defines.h"), md.SYSEX_RSP_GET_LATENCY)

    def test_answer_fits_the_pedal_buffer(self):
        import re

        samples = self.define("LATENCY_SAMPLES", "Core", "Inc", "latency.h")
        m = re.search(r"#define\s+SYSEX_MAX_LENGTH\s+(\d+)", self.source("USB_DEVICE", "App", "usbd_midi_if.c"))
        # F0 7D 79, count (2), slowest (3), the samples (3 each), F7
        self.assertLessEqual(3 + 2 + 3 + 3 * samples + 1, int(m.group(1)))

    def test_parse(self):
        from lib import midiDevice as md

        def us(v):
            return [(v >> 14) & 0x7F, (v >> 7) & 0x7F, v & 0x7F]

        got = md.parse_latency([1, 2] + us(4500) + us(250) + us(123456))
        self.assertEqual(got["count"], 130)
        self.assertEqual(got["max"], 4.5)
        self.assertEqual(got["samples"], [0.25, 123.456])
        self.assertEqual(md.parse_latency([0, 0, 0, 0, 0]), {"count": 0, "max": 0.0, "samples": []})


class BankPreviewTest(unittest.TestCase):
    """Bank Up / Down only show a bank until a button confirms it (0.66)."""

    FIRMWARE = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core")

    def source(self, *name):
        with open(os.path.join(self.FIRMWARE, *name)) as handle:
            return handle.read()

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
        blank = unpacker.unpack_global_settings(b"\xff" * unpacker.CONFIG_SIZE)
        self.assertEqual(blank[blank["Label"] == "Bank_Preview"]["Value"].iloc[0], "0")

    def test_demo_leaves_it_off(self):
        # The stress and latency tests time Bank Up on the demo
        self.assertEqual(pack_csv(DEMO_CSV)[47], 0)

    def test_state_reports_it(self):
        from lib.midiDevice import parse_state

        self.assertIsNone(parse_state([0] * 62)["preview"])           # before firmware 0.66
        self.assertIsNone(parse_state([0] * 62 + [0x7F])["preview"])  # none
        self.assertEqual(parse_state([0] * 62 + [5])["preview"], 5)


class FirmwareUpdateTest(unittest.TestCase):
    """Entering DFU mode from software, and the files it will flash (0.58)."""

    ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

    def source(self, *name):
        with open(os.path.join(self.ROOT, *name)) as handle:
            return handle.read()

    def image(self, payload=None, address=None, **kw):
        sys.path.insert(0, os.path.join(self.ROOT, "tools"))
        import bin_to_dfuse

        from lib import firmwareUpdate as fu

        if payload is None:
            # A stack pointer at the top of RAM, then a reset vector
            payload = struct.pack("<II", 0x20010000, 0x08003135) + bytes(1000)
        fields = dict(alt_setting=0, target_name="ST...", vendor=0x0483, product=0xDF11,
                      device=0, dfu_version=0x011A)
        fields.update(kw)
        return bin_to_dfuse.generate_dfuse(
            payload, load_address=fu.APP_ADDRESS if address is None else address, **fields)

    def check(self, data):
        import tempfile

        from lib import firmwareUpdate as fu

        with tempfile.NamedTemporaryFile(suffix=".dfu", delete=False) as handle:
            handle.write(data)
        try:
            return fu.check_image(handle.name)
        finally:
            os.unlink(handle.name)

    def test_constants_match_firmware(self):
        import re

        from lib import midiDevice as md

        defines = self.source("firmware", "Core", "Inc", "midi_defines.h")
        for name in ("SYSEX_CMD_ENTER_DFU", "SYSEX_RSP_ENTER_DFU"):
            value = re.search(rf"^#define\s+{name}\s+\((\d+)\)", defines, re.M)
            self.assertIsNotNone(value, name)
            self.assertEqual(int(value.group(1)), getattr(md, name), name)
        # The check bytes the firmware wants are the ones the tool sends
        handler = self.source("firmware", "USB_DEVICE", "App", "usbd_midi_if.c")
        check = re.search(r"data_packet_start\[0\] != (0x[0-9A-F]+) \|\| data_packet_start\[1\] != "
                          r"(0x[0-9A-F]+)\)\{\n\t\treturn;\n\t\}\n\n\tbool possible", handler)
        self.assertIsNotNone(check)
        self.assertEqual((int(check.group(1), 16), int(check.group(2), 16)), md.ENTER_DFU_CHECK)

    def test_addresses_match_the_linker(self):
        import re

        from lib import firmwareUpdate as fu

        # Where the firmware zeroes the word is where it is linked, and the
        # biggest image the tool accepts is the room the linker gives it
        entry = self.source("firmware", "Core", "Src", "dfu_entry.c")
        self.assertIn("#define APP_START\t\t(FLASH_BASE + 0x3000U)", entry)
        ld = self.source("firmware", "STM32F103RETX_FLASH_DFU.ld")
        m = re.search(r"FLASH\s+\(rx\)\s+:\s+ORIGIN = \(0x8000000 \+ (0x[0-9A-F]+)\),\s+"
                      r"LENGTH = \((\d+)K - (0x[0-9A-F]+)\)", ld)
        self.assertIsNotNone(m)
        self.assertEqual(0x08000000 + int(m.group(1), 16), fu.APP_ADDRESS)
        self.assertEqual(int(m.group(2)) * 1024 - int(m.group(3), 16), fu.APP_MAX_SIZE)
        # Only a build that runs behind the bootloader may do it
        self.assertIn("return (uint32_t)g_pfnVectors == APP_START;", entry)

    def test_the_bootloaders_own_test(self):
        from lib import firmwareUpdate as fu

        # The stack pointer test the stock bootloader makes before starting the
        # firmware: zero is what the firmware writes to stay in DFU
        self.assertTrue(fu._stack_pointer_ok(0x20010000))
        self.assertTrue(fu._stack_pointer_ok(0x20005000))
        self.assertFalse(fu._stack_pointer_ok(0x00000000))
        self.assertFalse(fu._stack_pointer_ok(0xFFFFFFFF))   # erased flash
        self.assertFalse(fu._stack_pointer_ok(0x08003135))

    def test_a_good_image_passes(self):
        self.assertEqual(self.check(self.image()), 1008)
        # And the one the build makes, when it has been built
        latest = os.path.join(self.ROOT, "artifacts", "dfu", "platformio-latest.dfu")
        if os.path.exists(latest):
            with open(latest, "rb") as handle:
                self.assertGreater(self.check(handle.read()), 40000)

    def test_images_that_would_not_start_are_refused(self):
        from lib import firmwareUpdate as fu

        good = self.image()
        bad = {
            "not a dfu file": b"\x00" * 400,
            "a raw binary": struct.pack("<II", 0x20010000, 0x08003135) + bytes(1000),
            "linked at the start of flash": self.image(address=0x08000000),
            "no stack pointer": self.image(payload=bytes(1008)),
            "too big": self.image(payload=struct.pack("<II", 0x20010000, 0x08003135)
                                  + bytes(fu.APP_MAX_SIZE)),
            "cut short": good[:-100],
            "damaged": good[:400] + bytes([good[400] ^ 0xFF]) + good[401:],
            "another device": self.image(product=0x1234),
        }
        for why, data in bad.items():
            with self.assertRaises(fu.UpdateError, msg=why):
                self.check(data)

    def test_dfu_listing(self):
        from lib import firmwareUpdate as fu

        # What dfu-util --list printed for the pedal in DFU mode
        listing = (
            'Found DFU: [0483:df11] ver=0200, devnum=1, cfg=1, intf=0, path="0-1", alt=2, '
            'name="@NOR Flash : M29W128F/0x64000000/0256*64Kg", serial="48EB874D3938"\n'
            'Found DFU: [0483:df11] ver=0200, devnum=1, cfg=1, intf=0, path="0-1", alt=0, '
            'name="@Internal Flash  /0x08000000/06*002Ka,250*002Kg", serial="48EB874D3938"\n')
        self.assertTrue(fu.dfu_listed(listing))
        self.assertFalse(fu.dfu_listed("dfu-util 0.11\n\nCopyright 2005-2009 Weston Schmidt\n"))
        self.assertFalse(fu.dfu_listed(
            'Found DFU: [1234:5678] ver=0100, alt=0, name="@Internal Flash  /0x08000000/64*002Kg"\n'))


class SharpInCsvTest(unittest.TestCase):
    """Only a line that starts with # is a comment: a sharp in a name or a label is data."""

    def test_sharp_survives(self):
        import tempfile
        with open(DEMO_CSV, encoding="utf-8") as f:
            text = f.read()
        text = (text.replace("\n0,HOME,index", "\n0,F#m,index", 1)
                    .replace("11,D,CH A,", "11,D,C#1,", 1)
                    .replace(",Cycle,,,CH B,", ",Cycle,,,C#B,", 1))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sharp.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            sections = read_config_csv(path)
        self.assertEqual(len(sections["Bank_Naming"]), 32)
        df_banks, df_buttons = unpacker.unpack_config(pack_config(sections))[1:3]
        self.assertEqual(df_banks.iloc[0]["Bank_Name_Large"], "F#m")
        row = df_buttons[(df_buttons["Bank_Number"].astype(str) == "11")
                         & (df_buttons["Button_Identifier"] == "D")].iloc[0]
        self.assertEqual(row["Label"], "C#1")
        self.assertIn("C#B", [str(v) for v in row.values])
        # the demo's own comment lines are still skipped
        self.assertNotIn("# Notes", read_config_csv(DEMO_CSV))


class FlashWriteErrorTest(unittest.TestCase):
    """0.71 answers a write it could not do with 01, and the tools stop and say so."""

    def setUp(self):
        from unittest import mock
        import lib.slotIO as slot_io
        patcher = mock.patch.object(slot_io, "time", mock.Mock(sleep=lambda s: None))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_write_image_raises(self):
        from lib.slotIO import FlashWriteError, pack_sections, write_image
        pedal = FakePedal(fail_write_at=160)
        with self.assertRaises(FlashWriteError) as ctx:
            write_image(pedal, *pack_sections(read_config_csv(DEMO_CSV)))
        self.assertIn("at byte 160", str(ctx.exception))
        # nothing written after the chunk that failed
        self.assertEqual(bytes(pedal.flash[0][176:192]), b"\xff" * 16)

    def test_csv_to_flash_reports_it(self):
        import argparse
        import contextlib
        import io
        from unittest import mock
        import CSV_to_Flash as tool
        pedal = FakePedal(fail_write_at=160)
        args = argparse.Namespace(csv_file=DEMO_CSV, slot=None, yes=True)
        with mock.patch.object(tool, "MidiCommander", lambda: pedal), \
                mock.patch.object(tool, "select_slot", lambda dev, slot: (0, 0, [0])), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = tool.main(args)
        self.assertEqual(code, 4)
        self.assertIn("could not write its flash", out.getvalue())
        self.assertEqual(pedal.resets, 0)
