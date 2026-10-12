"""The desktop configurator opens, shows every tab and saves what it loads.

It needs a display, so it runs only with GUI_TEST=1: CI runs it under
xvfb-run, and on a desktop

    GUI_TEST=1 python -m unittest python/tests/test_gui.py

opens the configurator's window for a few seconds.

Each CSV that comes with the tools is loaded, saved back from the editor's
fields, and must pack to the same bytes: whatever the editor does not show
or does not read back would be lost there.
"""
import glob
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from lib.configCsv import read_config_csv  # noqa: E402
from lib.slotIO import pack_sections  # noqa: E402

CSVS = [os.path.join(ROOT, "demo-all-features.csv")] + sorted(glob.glob(os.path.join(ROOT, "templates", "*.csv")))


@unittest.skipUnless(os.environ.get("GUI_TEST") == "1", "needs a display: GUI_TEST=1")
class GuiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import gui_configurator as g
        cls.app = g.MidiCommanderGUI()
        cls.app.update()

    @classmethod
    def tearDownClass(cls):
        cls.app.saved_text = cls.app._config_text()     # nothing to ask about
        cls.app._on_close()

    def test_every_tab_shows(self):
        for name in self.app.tabview._name_list:
            with self.subTest(name):
                self.app.tabview.set(name)
                self.app.update()
                self.assertEqual(self.app.tabview.get(), name)

    def test_what_a_write_changes(self):
        import subprocess
        import types
        out = lambda code, text: lambda script, *a: subprocess.CompletedProcess([], code, text, "")
        fake = types.SimpleNamespace(CHANGES_SHOWN=2, _slot_args=lambda: [])
        changes = self.app._changes_on_pedal.__func__
        fake._run_tool = out(1, 'Slot 1 holds "X". Writing /tmp/a.csv to it changes:\nA\nB\nC\n3 changes\n')
        self.assertEqual(changes(fake, "/tmp/a.csv"),
                         'Slot 1 holds "X". Writing these settings to it changes:\n• A\n• B\n• … and 1 more\n3 changes')
        fake._run_tool = out(0, 'Slot 1 holds "X", already exactly this configuration: writing changes nothing.\n')
        self.assertTrue(changes(fake, "/tmp/a.csv").endswith("writing changes nothing."))
        fake._run_tool = out(3, "No matching MIDI device found: none\n")
        self.assertEqual(changes(fake, "/tmp/a.csv"),
                         "Could not read the pedal to say what changes. No matching MIDI device found: none")

    def test_a_calibration_sweep_is_checked(self):
        # Readings as the live view would bring them in, without a pedal
        app = self.app
        app.tabview.set("Expression")
        w = app.exp_widgets[0]
        app._calibrate_toggle(0)
        for raw in [100] * 5 + list(range(100, 4000, 100)) + [4000] * 5:
            app.calibrating[0].append(raw)
        app._sweep_draw(w, app.calibrating[0])
        app._calibrate_toggle(0)
        app.update()
        self.assertEqual((w["min"].get(), w["max"].get()), ("217", "3883"))
        self.assertIn("looks right", w["verdict"].cget("text"))
        app._calibrate_toggle(0)
        app.calibrating[0].extend([0, 2, 1, 3] * 10)
        app._calibrate_toggle(0)
        self.assertIn("TRS", w["verdict"].cget("text"))
        self.assertEqual(w["min"].get(), "217")         # left as it was

    def test_a_command_from_the_device_dictionary(self):
        import lib.deviceDictionary as dd
        self.app.load_csv(os.path.join(ROOT, "templates", "HX_Stomp.csv"))
        self.app.load_button_commands(0, "1")
        self.app.update()
        editor = self.app.slot_editors[-1]
        self.assertEqual(editor.values()["CommandType"], "")
        hx = dd.BY_NAME["HX Stomp"]
        editor.pick(hx, next(e for e in hx["commands"] if e["name"] == "FS4"))
        self.app.update()
        v = editor.values()
        self.assertEqual((v["CommandType"], v["Channel_(PC/CC/Note/PB)"], v["Number_(PC/CC/Note)"],
                          v["OnValue_(CC/PB)"], v["OffValue_(CC)"], v["Toggle_(CC/PB/Note)"]),
                         ("CC", "1", "52", "127", "0", "Y"))
        self.assertEqual(editor.name_label.cget("text"), "HX Stomp: FS4")

    def test_a_cheat_sheet_of_what_is_edited(self):
        from unittest import mock
        import gui_configurator as g
        self.app.load_csv(os.path.join(ROOT, "templates", "HX_Stomp.csv"))
        self.app.update()
        with mock.patch.object(g.webbrowser, "open") as browser:
            self.app.cheat_sheet()
        page = browser.call_args.args[0][len("file://"):]
        with open(page, encoding="utf-8") as f:
            self.assertIn("HX Stomp: Snapshot 1", f.read())
        os.remove(page)

    def test_a_pedal_in_zones(self):
        app = self.app
        app.load_csv(CSVS[0])
        app.update()
        w = app.exp_widgets[1]
        w["output"].set("Zones")
        w["zones"].set("3")
        w["zone_1"].set("A")
        w["zone_3"].set("C")
        w["zone_4"].set("D")                # past the third: not kept
        app._collect()
        self.assertEqual(app.df_exp.at[1, "Zones"], "A None C")
        app.load_csv(CSVS[0])               # back as it was, for the other tests

    def test_a_song_saved_and_loaded(self):
        app = self.app
        app.load_csv(CSVS[0])
        app.bank_selector.set("12")
        app.on_bank_change("12")
        with tempfile.TemporaryDirectory() as tmp:
            song = os.path.join(tmp, "s.song.csv")
            app.save_song(song)
            app.bank_selector.set("20")
            app.on_bank_change("20")
            app.load_song(song, ask=False)
        app.update()
        self.assertEqual(app.bank_selector.get(), "20")
        names = app.df_banks.set_index("Bank_Number")
        self.assertEqual(names.at["20", "Bank_Name_Large"], "S01")
        self.assertTrue(app._unsaved())
        buttons = app.df_buttons
        self.assertEqual(buttons[(buttons["Bank_Number"] == "20") & (buttons["Button_Identifier"] == "1")]["Label"].iloc[0], "REC")
        app.load_csv(CSVS[0])               # back as it was, for the other tests

    def test_a_rig(self):
        from unittest import mock
        import gui_configurator as g
        app = self.app
        app.saved_text = app._config_text()
        app.rig_wizard()
        win = app.rig_window
        (main, ch1, _), (other, ch2, follow) = win.rows[:2]
        main.set("HX Stomp")
        other.set("TimeLine")
        with mock.patch.object(g.messagebox, "showinfo") as info:
            win.make()
        app.update()
        self.assertIn("Bank 29 holds the TimeLine's FS, in place of the HX Stomp's 10C.", info.call_args.args[1])
        banks = app.df_banks.set_index("Bank_Number")
        self.assertEqual(banks.at["29", "Bank_Info_Small"], "TimeLine")
        self.assertTrue(app._unsaved())
        app.load_csv(CSVS[0])               # back as it was, for the other tests

    def test_several_setlists(self):
        from lib.configPacker import setlists
        app = self.app
        app.load_csv(CSVS[0])
        app.update()
        self.assertEqual(app.setlist_name.get(), "FULL SET")
        app._pick_setlist("Setlist 2")
        self.assertEqual(app.setlist_name.get(), "ACOUSTIC")
        self.assertEqual([w.value().split()[0] for w in app.setlist_widgets[:5]], ["12", "13", "17", "21", "(none)"])
        app.setlist_widgets[4].set(app.setlist_widgets[0].cget("values")[3])     # bank 2 at the end
        app._pick_setlist("Setlist 3")
        app.setlist_name.insert(0, "SPARE")
        app.apply_setlist_changes()
        self.assertEqual(setlists(app.df_setlist), {1: ("FULL SET", [0, 12, 15, 13, 14, 18, 16, 17, 19, 20]),
                                                    2: ("ACOUSTIC", [12, 13, 17, 21, 2]), 3: ("SPARE", []),
                                                    4: ("", [])})
        app.load_csv(CSVS[0])               # back as it was, for the other tests

    def test_a_command_from_a_community_device(self):
        import lib.deviceDictionary as dd
        self.app.load_csv(os.path.join(ROOT, "templates", "HX_Stomp.csv"))
        self.app.load_button_commands(0, "2")
        self.app.update()
        editor = self.app.slot_editors[-1]
        tmp = dd.find("Fender Tone Master Pro")
        editor.pick(tmp, next(e for e in tmp["commands"] if e["name"] == "Looper PLAY/STOP"))
        self.app.update()
        v = editor.values()
        self.assertEqual((v["CommandType"], v["Number_(PC/CC/Note)"], v["OnValue_(CC/PB)"], v["OffValue_(CC)"]),
                         ("CC", "104", "127", ""))
        self.assertEqual(editor.name_label.cget("text"), "Fender Tone Master Pro: Looper PLAY/STOP")

    def test_saved_as_loaded(self):
        for path in CSVS:
            with self.subTest(os.path.basename(path)):
                self.app.load_csv(path)
                self.app.update()
                with tempfile.TemporaryDirectory() as tmp:
                    out = os.path.join(tmp, "saved.csv")
                    self.app._collect()
                    self.app._write_csv(out)
                    self.assertEqual(pack_sections(read_config_csv(out)),
                                     pack_sections(read_config_csv(path)))


if __name__ == "__main__":
    unittest.main()
