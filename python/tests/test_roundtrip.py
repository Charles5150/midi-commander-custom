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
        cls.df_global, cls.df_banks, cls.df_buttons, cls.df_long = unpacker.unpack_config(
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
        for (_, exp), (_, got) in zip(expected.iterrows(), self.df_banks.iterrows()):
            self.assertEqual(norm(got["Bank_Number"]), norm(exp["Bank_Number"]))
            self.assertEqual(
                norm(got["Bank_Name_Large"]), norm(exp["Bank_Name_Large"])[:4]
            )
            self.assertEqual(
                norm(got["Bank_Info_Small"]), norm(exp["Bank_Info_Small"])[:8]
            )

    def test_button_settings(self):
        expected = self.sections["Button_Settings"]
        self.assertEqual(len(expected), len(self.df_buttons))
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
        _, _, df, df_long = unpacker.unpack_config(blank)
        self.assertTrue((df["A_CommandType"] == "").all())
        self.assertTrue((df["Light_Mode"] == "Normal").all())
        self.assertTrue((df["Label"] == "").all())
        self.assertTrue((df_long["A_CommandType"] == "").all())

    def test_light_mode_does_not_touch_command_bytes(self):
        """LED modes live in their own table and never set bits in slot A."""
        sections = read_config_csv(SAMPLE_CSV)
        df = sections["Button_Settings"].copy()
        # Force every LED mode onto buttons with different slot A types
        df["Light_Mode"] = ["Reverse", "AlwaysOn"] * (len(df) // 2)
        modified = {**sections, "Button_Settings": df}
        packed = pack_config(modified)

        # Command bytes identical to the all-Normal packing
        base = pack_config(sections)
        self.assertEqual(
            packed[: unpacker.LED_MODES_OFFSET], base[: unpacker.LED_MODES_OFFSET]
        )
        # LED table carries the modes
        table = packed[unpacker.LED_MODES_OFFSET : unpacker.LABELS_OFFSET]
        self.assertEqual(list(table), [1, 2] * (len(df) // 2))
        # And they come back by name
        _, _, decoded, _ = unpacker.unpack_config(packed)
        self.assertEqual(decoded["Light_Mode"].tolist(), df["Light_Mode"].tolist())

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

        df_global, _, _, _ = unpacker.unpack_config(thru_on)
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
        df_global, _, _, _ = unpacker.unpack_config(packed)
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
        _, _, decoded, _ = unpacker.unpack_config(packed)
        self.assertEqual(decoded["Label"].tolist()[:3], ["REC", "TOOL", ""])
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
        self.assertEqual(set(base[unpacker.LONG_PRESS_OFFSET :]), {0})

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

        _, _, _, decoded = unpacker.unpack_config(packed)
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
        df_global, _, _, _ = unpacker.unpack_config(packed)
        self.assertEqual(df_global.set_index("Label")["Value"]["Long_Press_ms"], "750")

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
