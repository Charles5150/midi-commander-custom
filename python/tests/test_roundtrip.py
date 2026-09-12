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
import lib.settingsBinaryPacker as sbp  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402

SAMPLE_CSV = os.path.join(os.path.dirname(HERE), "MeloConfig_10_Cmds - RC-600.csv")


def pack_csv(path: str) -> bytes:
    """Pack a CSV exactly like CSV_to_Flash.py does."""
    sections = read_config_csv(path)
    df_global = sections["Global_Settings"].set_index("Label")
    df_banks = sections["Bank_Naming"].set_index("Bank_Number")
    df_buttons = sections["Button_Settings"].copy()
    # CSV_to_Flash reads numbers as floats; mimic that for the numeric columns
    # the packers do arithmetic on.
    for col in df_buttons.columns:
        if "Channel_" in col:
            df_buttons[col] = pd.to_numeric(df_buttons[col], errors="coerce")
    df_buttons = df_buttons.set_index(["Bank_Number", "Button_Identifier"])

    out = []
    out += sbp.pack_global_settings(df_global)
    out += sbp.pack_bank_strings(df_banks)
    for _, row in df_buttons.iterrows():
        out += cbp.pack_row(row)
    return bytes(out)


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
        cls.df_global, cls.df_banks, cls.df_buttons = unpacker.unpack_config(
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
        _, _, df = unpacker.unpack_config(blank)
        self.assertTrue((df["A_CommandType"] == "").all())
        self.assertTrue((df["Light_Mode"] == "Normal").all())


if __name__ == "__main__":
    unittest.main()
