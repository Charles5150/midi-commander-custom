"""The cheat sheet, lib/cheatSheet.py: every configuration that comes with
the tools makes one, and it says what the pedal would do in words."""
import glob
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import lib.webBridge as bridge  # noqa: E402
from lib.cheatSheet import cheat_sheet  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402

DEMO = os.path.join(ROOT, "demo-all-features.csv")
CSVS = [DEMO] + sorted(glob.glob(os.path.join(ROOT, "templates", "*.csv")))


def template(name):
    return read_config_csv(os.path.join(ROOT, "templates", f"{name}.csv"))


def set_global(sections, label, value):
    g = sections["Global_Settings"]
    g.loc[g["Label"] == label, "Value"] = value


class CheatSheetTest(unittest.TestCase):
    def test_every_configuration_makes_one(self):
        for path in CSVS:
            with self.subTest(os.path.basename(path)):
                page = cheat_sheet(read_config_csv(path))
                self.assertTrue(page.startswith("<!doctype html>"))
                self.assertIn("<h2>Banks</h2>", page)

    def test_the_demo(self):
        page = cheat_sheet(read_config_csv(DEMO))
        self.assertIn("<h1>DEMO ALL</h1>", page)
        # The switches as on the pedal, 1-4 then A-D, and the presses in words
        self.assertLess(page.index('<span class="id">4</span><b>KEYS'), page.index('<span class="id">A</span><b>MEDI'))
        self.assertIn("Bank go to 1 LOOP (looper)", page)
        self.assertIn("<i>Long:</i> Macro", page)
        self.assertIn("Key Cmd+z", page)
        self.assertIn("Program 1 CRUNCH, ch 1", page)
        self.assertIn("then ", page)                       # a Cycle's next state
        self.assertIn("<i>On entering:</i>", page)
        self.assertIn("<i>Pedals here:</i> pedal 1 off; pedal 2 CC 7 ch 2, 40 to max", page)
        # The setlist in its order, the combinations
        songs = [page.index(f"<td>{s}</td>") for s in ("S01", "S04", "S02", "S03")]
        self.assertEqual(songs, sorted(songs))
        self.assertIn("B+C together, in every bank", page)
        # A bank with nothing in it is left out
        self.assertNotIn("Bank 31 ", page.replace("Bank 31 S01", ""))

    def test_a_known_device_names_its_commands(self):
        page = cheat_sheet(template("HX_Stomp"))
        self.assertIn("HX Stomp: Snapshot 1", page)
        self.assertIn("HX Stomp: Preset (Program 0, ch 1)", page)
        self.assertIn("HX Stomp: EXP 1 (CC 1, ch 1)", page)

    def test_a_device_picked_names_them(self):
        sections = template("Ableton_Live")
        self.assertNotIn("Fender Tone Master Pro:", cheat_sheet(sections))
        page = cheat_sheet(sections, {"1": "Fender Tone Master Pro"})
        self.assertIn("Fender Tone Master Pro on channel 1", page)

    def test_the_setlist_tempo(self):
        sections = read_config_csv(DEMO)
        e = sections["BankEnter_Settings"]
        row = e.index[e["Bank_Number"] == "13"][0]
        e.loc[row, ["B_CommandType", "B_KeyMode_(Key)", "B_OnValue_(CC/PB)"]] = ["Tap", "Set", "96"]
        self.assertIn("<td>13</td><td>96 BPM</td>", cheat_sheet(sections))

    def test_a_pedal_in_zones(self):
        sections = read_config_csv(DEMO)
        e = sections["Expression_Settings"]
        e.loc[e["Pedal"] == "2", ["Output", "Zones"]] = ["Zones", "A None C"]
        self.assertIn("<td>Pedal 2</td><td>3 zones, heel first</td><td>zone 1 presses A, zone 3 presses C</td>",
                      cheat_sheet(sections))

    def test_text_is_escaped(self):
        sections = read_config_csv(DEMO)
        set_global(sections, "ConfigName", "R&B <live>")
        self.assertIn("<h1>R&amp;B &lt;live&gt;</h1>", cheat_sheet(sections))

    def test_a_mistake_is_said(self):
        sections = read_config_csv(DEMO)
        sections["Button_Settings"].loc[0, "A_CommandType"] = "Nonsense"
        with self.assertRaisesRegex(ValueError, "Nonsense"):
            cheat_sheet(sections)

    def test_the_page_gets_it(self):
        with open(DEMO, "rb") as f:
            text = bridge.csv_to_sections(f.read())
        self.assertEqual(bridge.cheat_sheet(text), cheat_sheet(read_config_csv(DEMO)))
        self.assertIn("Fender Tone Master Pro on channel 2",
                      bridge.cheat_sheet(text, json.dumps({"2": "Fender Tone Master Pro"})))

    def test_the_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "sheet.html")
            r = subprocess.run([sys.executable, "Cheat_Sheet.py", os.path.join("templates", "Volante.csv"), "-o", out,
                                "--device", "2=H90"], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            with open(out, encoding="utf-8") as f:
                self.assertIn("H90 on channel 2", f.read())
            r = subprocess.run([sys.executable, "Cheat_Sheet.py", "missing.csv"], cwd=ROOT, capture_output=True)
            self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
