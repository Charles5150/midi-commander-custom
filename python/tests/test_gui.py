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
