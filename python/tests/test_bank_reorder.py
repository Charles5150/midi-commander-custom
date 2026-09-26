"""Moving a bank in the list, and copying one button, in lib/bankReorder.py.

Run from the repository root:

    python -m unittest python/tests/test_bank_reorder.py
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lib.bankReorder as br  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
from lib.configPacker import pack_config  # noqa: E402

DEMO_CSV = os.path.join(os.path.dirname(HERE), "demo-all-features.csv")

SECTIONS = {
    "global": "Global_Settings",
    "banks": "Bank_Naming",
    "buttons": "Button_Settings",
    "long": "LongPress_Settings",
    "double": "DoublePress_Settings",
    "enter": "BankEnter_Settings",
    "bank_switch": "BankSwitch_Settings",
    "setlist": "Setlist",
    "bank_exp": "BankExpression_Settings",
    "combos": "Combo_Settings",
}


def frames_of(sections):
    return {name: sections[s] for name, s in SECTIONS.items() if s in sections}


def sections_of(sections, frames):
    out = dict(sections)
    for name, s in SECTIONS.items():
        if name in frames and frames[name] is not None:
            out[s] = frames[name]
    return out


def cell(df, bank, button, col):
    rows = df[(df["Bank_Number"].map(br._bank) == str(bank))
              & (df["Button_Identifier"].map(br._button) == button)]
    return br._cell(rows.iloc[0][col])


class MoveBankTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sections = read_config_csv(DEMO_CSV)
        cls.frames = frames_of(cls.sections)
        cls.packed = pack_config(cls.sections)

    def moved(self, src, dst):
        return br.move_bank(self.frames, src, dst)

    def test_move_map_shifts_the_banks_in_between(self):
        m = br.move_map(5, 2)
        self.assertEqual((m[5], m[2], m[3], m[4], m[6], m[0]), (2, 3, 4, 5, 6, 0))
        m = br.move_map(2, 5)
        self.assertEqual((m[2], m[3], m[4], m[5], m[6]), (5, 2, 3, 4, 6))

    def test_there_and_back_packs_the_same_bytes(self):
        for src, dst in ((12, 3), (0, 31), (30, 1), (7, 8)):
            there = br.move_bank(self.frames, src, dst)
            back = br.move_bank(there, dst, src)
            self.assertEqual(pack_config(sections_of(self.sections, back)), self.packed, (src, dst))

    def test_a_move_packs_different_bytes(self):
        moved = self.moved(12, 3)
        self.assertNotEqual(pack_config(sections_of(self.sections, moved)), self.packed)

    def test_the_bank_takes_its_content_along(self):
        moved = self.moved(12, 3)
        names = moved["banks"].set_index("Bank_Number")
        self.assertEqual(br._cell(names.loc["3", "Bank_Name_Large"]), "S01")
        self.assertEqual(br._cell(names.loc["4", "Bank_Name_Large"]), "PTCH")
        self.assertEqual(br._cell(names.loc["13", "Bank_Name_Large"]), "S02")
        self.assertEqual(cell(moved["buttons"], 3, "D", "Label"), "PG 2")
        self.assertEqual(list(moved["banks"]["Bank_Number"]), [str(b) for b in range(32)])

    def test_bank_commands_follow(self):
        moved = self.moved(12, 3)
        # HOME's third button went to bank 3, now at 4
        self.assertEqual(cell(moved["buttons"], 0, "3", "A_OnValue_(CC/PB)"), "4")
        # The page button of S01 still opens bank 31, whose Back returns to S01
        self.assertEqual(cell(moved["buttons"], 3, "D", "A_OnValue_(CC/PB)"), "31")
        self.assertEqual(cell(moved["buttons"], 31, "D", "A_OnValue_(CC/PB)"), "3")
        # Macro in HOME's long press list named MIX, bank 11, now 12
        self.assertEqual(cell(moved["long"], 0, "2", "A_OnValue_(CC/PB)"), "12")

    def test_relative_bank_commands_stay(self):
        frames = self.frames
        df = frames["buttons"]
        for idx in df.index:
            if br._cell(df.at[idx, "A_CommandType"]) == "Bank" and \
                    br._cell(df.at[idx, "A_KeyMode_(Key)"]).upper() in ("UP", "DOWN"):
                bank, btn = df.at[idx, "Bank_Number"], df.at[idx, "Button_Identifier"]
                before = br._cell(df.at[idx, "A_OnValue_(CC/PB)"])
                moved = br.move_bank(frames, 0, 31)
                new_bank = br.move_map(0, 31)[int(br._bank(bank))]
                self.assertEqual(cell(moved["buttons"], new_bank, br._button(btn), "A_OnValue_(CC/PB)"), before)
                return
        self.skipTest("no relative Bank command in the demo")

    def test_setlist_global_bank_and_combos_follow(self):
        moved = self.moved(30, 0)
        self.assertEqual(list(moved["setlist"]["Bank_Number"])[:3], ["1", "13", "16"])
        glob = moved["global"].set_index("Label")
        self.assertEqual(glob.loc["Global_Bank", "Value"], "0")
        self.assertEqual(list(moved["combos"]["Bank"])[:2], ["All", "13"])
        self.assertEqual(list(moved["combos"]["Run_Bank"])[:2], ["0", "0"])

    def test_if_bank_tests_follow_and_others_stay(self):
        df = self.frames["buttons"].copy().astype(object)
        idx = df.index[0]
        df.at[idx, "A_CommandType"], df.at[idx, "A_KeyMode_(Key)"], df.at[idx, "A_OnValue_(CC/PB)"] = "If", "Bank is", "5"
        df.at[idx, "B_CommandType"], df.at[idx, "B_KeyMode_(Key)"], df.at[idx, "B_OnValue_(CC/PB)"] = "If", "Value =", "5"
        df.at[idx, "C_CommandType"], df.at[idx, "C_OnValue_(CC/PB)"] = "CC", "5"
        out = br.remap_commands(df, br.move_map(5, 2))
        self.assertEqual(out.at[idx, "A_OnValue_(CC/PB)"], "2")
        self.assertEqual(out.at[idx, "B_OnValue_(CC/PB)"], "5")
        self.assertEqual(out.at[idx, "C_OnValue_(CC/PB)"], "5")

    def test_moving_in_place_changes_nothing(self):
        same = br.move_bank(self.frames, 4, 4)
        self.assertEqual(pack_config(sections_of(self.sections, same)), self.packed)


class CopyButtonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sections = read_config_csv(DEMO_CSV)

    def test_paste_makes_the_button_a_copy(self):
        s = self.sections
        buttons, long, double = s["Button_Settings"], s["LongPress_Settings"], s["DoublePress_Settings"]
        clip = br.copy_button(buttons, long, double, 11, "4")
        b2, l2, d2 = br.paste_button(buttons, long, double, clip, 2, "a")
        self.assertEqual(cell(b2, 2, "A", "Label"), cell(buttons, 11, "4", "Label"))
        self.assertEqual(cell(b2, 2, "A", "Reset_On_Bank"), cell(buttons, 11, "4", "Reset_On_Bank"))
        for df, src in ((b2, buttons), (l2, long), (d2, double)):
            for col in df.columns:
                if col in ("Bank_Number", "Button_Identifier"):
                    continue
                self.assertEqual(cell(df, 2, "A", col), cell(src, 11, "4", col), col)
        self.assertEqual(len(b2), len(buttons))
        # The source and the other buttons are untouched
        self.assertEqual(cell(b2, 11, "4", "Label"), cell(buttons, 11, "4", "Label"))
        self.assertEqual(cell(b2, 2, "B", "Label"), cell(buttons, 2, "B", "Label"))
        packed = pack_config({**s, "Button_Settings": b2, "LongPress_Settings": l2, "DoublePress_Settings": d2})
        self.assertNotEqual(packed, pack_config(s))

    def test_pasting_onto_itself_changes_nothing(self):
        s = self.sections
        buttons, long, double = s["Button_Settings"], s["LongPress_Settings"], s["DoublePress_Settings"]
        clip = br.copy_button(buttons, long, double, 3, "1")
        self.assertIs(br.paste_button(buttons, long, double, clip, 3, "1")[0], buttons)


if __name__ == "__main__":
    unittest.main()
