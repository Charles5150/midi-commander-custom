"""What changes between two configurations (lib/configDiff.py, Diff_Config.py)."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import Diff_Config  # noqa: E402
from lib import webBridge as wb  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
from lib.configDiff import command_text, config_sections, diff  # noqa: E402
from lib.configPacker import pack_config, pack_flash_image  # noqa: E402

DEMO = os.path.join(ROOT, "demo-all-features.csv")


def demo():
    return read_config_csv(DEMO)


def changed(edit):
    """diff() from the demo to the demo after edit(sections)."""
    sections = demo()
    edit(sections)
    return diff(config_sections(demo()), config_sections(sections))


def row(df, **match):
    mask = True
    for col, value in match.items():
        mask = mask & (df[col] == value)
    return df.index[mask][0]


class DiffTest(unittest.TestCase):
    def test_the_same_configuration_changes_nothing(self):
        self.assertEqual(diff(config_sections(demo()), config_sections(demo())), [])

    def test_what_the_pedal_does_not_keep_changes_nothing(self):
        # Columns in another order, and a field the command does not use
        def edit(s):
            b = s["Button_Settings"]
            s["Button_Settings"] = b[list(reversed(b.columns))]
            i = row(b, A_CommandType="Media")
            s["Button_Settings"].loc[i, "A_Number_(PC/CC/Note)"] = "99"
        self.assertEqual(changed(edit), [])

    def test_global_setting_by_its_name(self):
        def edit(s):
            g = s["Global_Settings"]
            g.loc[g["Label"] == "Skip_Same_PC", "Value"] = "N"
        self.assertEqual(changed(edit), ["Global: Don't resend the same PC: on -> off"])

    def test_a_field_of_a_command(self):
        def edit(s):
            lp = s["LongPress_Settings"]
            i = row(lp, Bank_Number="1", Button_Identifier="4")
            lp.loc[i, "A_Number_(PC/CC/Note)"] = "21"
            lp.loc[i, "A_Toggle_(CC/PB/Note)"] = "Y"
        self.assertEqual(changed(edit), ["Bank 1 LOOP, button 4, long press: A CC: CC#: 5 -> 21, Toggle: off -> on"])

    def test_a_command_added_and_the_label(self):
        def edit(s):
            b = s["Button_Settings"]
            i = row(b, Bank_Number="5", Button_Identifier="2")
            for col, v in (("CommandType", "CC"), ("Channel_(PC/CC/Note/PB)", "2"), ("Number_(PC/CC/Note)", "7"),
                           ("OnValue_(CC/PB)", "127")):
                b.loc[i, f"B_{col}"] = v
            b.loc[i, "Label"] = "NEW"
        self.assertEqual(changed(edit), ["Bank 5 MEDI, button 2: Label: NEXT -> NEW",
                                         "Bank 5 MEDI, button 2: B: CC Ch 2, CC# 7, On 127 added"])

    def test_force_is_a_check_box(self):
        def edit(s):
            b = s["Button_Settings"]
            b.loc[row(b, Bank_Number="3", Button_Identifier="1"), "A_KeyMode_(Key)"] = ""
        self.assertEqual(changed(edit), ["Bank 3 PTCH, button 1: A PC: Force: on -> off"])

    def test_banks_setlist_and_lists(self):
        def edit(s):
            s["Bank_Naming"].loc[row(s["Bank_Naming"], Bank_Number="4"), "Bank_Name_Large"] = "LEAD"
            s["Setlist"].loc[0, "Bank_Number"] = "3"
            s["MidiMap_Settings"].loc[0, "Out_Number"] = "30"
            s["BankSwitch_Settings"].loc[0, "A_Number_(PC/CC/Note)"] = "90"
            s["Expression_Settings"].loc[0, "Curve"] = "Exp"
        lines = changed(edit)
        self.assertIn("Bank 4: name: KEYS -> LEAD", lines)
        self.assertIn("Bank Down switch, short press: A CC: CC#: 81 -> 90", lines)
        self.assertIn("Expression pedal 1: Curve: Linear -> Exp", lines)
        self.assertIn("MIDI map row 1: Out_Number: 20 -> 30", lines)
        self.assertTrue(any(l.startswith("Setlist: banks: 0 12 15") and "-> 3 12 15" in l for l in lines))

    def test_command_text(self):
        self.assertEqual(command_text({"CommandType": "PC", "Channel_(PC/CC/Note/PB)": "1",
                                       "Number_(PC/CC/Note)": "5", "KeyMode_(Key)": "Y"}), "PC Ch 1, Program 5, Force")
        self.assertEqual(command_text({"CommandType": ""}), "(none)")


class ToolTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def run_tool(self, *argv, slot=None):
        args = types.SimpleNamespace(old=argv[0], new=argv[1] if len(argv) > 1 else None, slot=slot)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = Diff_Config.main(args)
        return code, out.getvalue().strip().splitlines()

    def copy(self, find=None, replace=None):
        with open(DEMO, encoding="utf-8") as f:
            text = f.read()
        if find:
            self.assertIn(find, text)
            text = text.replace(find, replace, 1)
        path = os.path.join(self.dir, f"c{len(os.listdir(self.dir))}.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_two_files(self):
        self.assertEqual(self.run_tool(DEMO, self.copy())[0], 0)
        code, lines = self.run_tool(DEMO, self.copy("Skip_Same_PC,Y", "Skip_Same_PC,N"))
        self.assertEqual(code, 1)
        self.assertEqual(lines, ["Global: Don't resend the same PC: on -> off", "1 change"])

    def test_a_mistake(self):
        code, lines = self.run_tool(DEMO, self.copy("MIDI_Channel,1", "MIDI_Channel,99"))
        self.assertEqual(code, 2)
        self.assertTrue(lines[0].startswith("ERROR: "))

    def test_against_the_pedal(self):
        sections = demo()
        config, image = pack_config(sections), pack_flash_image(sections)
        from lib.configDiff import image_sections
        read = [(1, image_sections(config, image))]
        original = Diff_Config._read_slot
        Diff_Config._read_slot = lambda slot: read[0]
        self.addCleanup(setattr, Diff_Config, "_read_slot", original)
        path = self.copy("Skip_Same_PC,Y", "Skip_Same_PC,N")
        code, lines = self.run_tool(path)
        self.assertEqual(code, 1)
        self.assertEqual(lines[0], f'Slot 1 holds "DEMO ALL". Writing {path} to it changes:')
        self.assertEqual(lines[1:], ["Global: Don't resend the same PC: on -> off", "1 change"])
        self.assertEqual(self.run_tool(DEMO),
                         (0, ['Slot 1 holds "DEMO ALL", already exactly this configuration: writing changes nothing.']))
        read[0] = (2, None)
        code, lines = self.run_tool(DEMO)
        self.assertEqual((code, lines), (1, ["Slot 2 holds no configuration: writing puts all of it there."]))

    def test_the_web_bridge_says_the_same(self):
        sections = demo()
        config, image = pack_config(sections), pack_flash_image(sections)
        text = wb.csv_to_sections(open(self.copy("Skip_Same_PC,Y", "Skip_Same_PC,N"), "rb").read())
        self.assertEqual(json.loads(wb.changes(config, image, text)), ["Global: Don't resend the same PC: on -> off"])
        self.assertEqual(json.loads(wb.changes(config, image, wb.csv_to_sections(open(DEMO, "rb").read()))), [])


if __name__ == "__main__":
    unittest.main()
