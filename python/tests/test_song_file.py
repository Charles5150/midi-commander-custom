"""Songs, lib/songFile.py: one bank saved to a file of its own and loaded into
a bank of any configuration, with what it runs elsewhere."""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import lib.songFile as sf  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
from lib.slotIO import pack_sections  # noqa: E402

DEMO = os.path.join(ROOT, "demo-all-features.csv")


def template(name):
    return read_config_csv(os.path.join(ROOT, "templates", f"{name}.csv"))


def song(sections, bank):
    """The song file of a bank, read back as a file would be."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(sf.save_song(sections, bank))
    try:
        return read_config_csv(f.name)
    finally:
        os.unlink(f.name)


def row(sections, name, bank, button=None):
    df = sections[name]
    keep = df["Bank_Number"].astype(str) == str(bank)
    if button is not None:
        keep &= df["Button_Identifier"].astype(str) == str(button)
    return df[keep].iloc[0]


def set_cells(sections, name, bank, button, **cells):
    df = sections[name]
    keep = (df["Bank_Number"].astype(str) == str(bank)) & (df["Button_Identifier"].astype(str) == str(button))
    for column, value in cells.items():
        df.loc[keep, column] = value


def commands(r):
    """{column: value} of a row's filled command cells."""
    return {c: v for c, v in r.items() if c[1:2] == "_" and sf._cell(v) and not c.endswith("Toggle_(CC/PB/Note)")}


class SongTest(unittest.TestCase):
    def setUp(self):
        self.demo = read_config_csv(DEMO)

    def test_every_demo_bank_goes_back_as_it_was(self):
        before = pack_sections(self.demo)
        for bank in range(32):
            with self.subTest(bank=bank):
                loaded, _ = sf.load_song(self.demo, song(self.demo, bank), bank)
                self.assertEqual(pack_sections(loaded), before)

    def test_into_another_bank_of_another_configuration(self):
        live = template("Ableton_Live")
        loaded, notes = sf.load_song(live, song(self.demo, 12), 5)
        self.assertEqual(row(loaded, "Bank_Naming", 5)["Bank_Name_Large"], "S01")
        for b in ("1", "2", "A"):
            self.assertEqual(commands(row(loaded, "Button_Settings", 5, b)),
                             commands(row(self.demo, "Button_Settings", 12, b)))
        # Its combination counts in bank 5 now, and runs what it ran, carried along
        combos = loaded["Combo_Settings"]
        mine = combos[combos["Bank"] == "5"]
        self.assertEqual(mine[["Switches", "Run_Bank", "Run_Button"]].values.tolist(), [["3+4", "30", "4"]])
        self.assertEqual(commands(row(loaded, "Button_Settings", 30, 4)), commands(row(self.demo, "Button_Settings", 30, 4)))
        self.assertIn("bank 30 button 4 was empty here and now holds what the song runs there", notes)
        # The name of the program it sends
        names = dict(loaded["Preset_Names"][["Program", "Name"]].values.tolist())
        self.assertEqual(names, {"1": "CRUNCH"})
        self.assertIn("it goes to other banks by number, as where it was saved: button A to 0, button D to 31", notes)
        pack_sections(loaded)

    def test_its_own_bank_follows_it(self):
        set_cells(self.demo, "Button_Settings", 12, "1", **{"J_CommandType": "Macro", "J_OnValue_(CC/PB)": "12",
                                                           "J_Number_(PC/CC/Note)": "2", "J_KeyMode_(Key)": "Short"})
        loaded, _ = sf.load_song(template("Ableton_Live"), song(self.demo, 12), 5)
        self.assertEqual(row(loaded, "Button_Settings", 5, "1")["J_OnValue_(CC/PB)"], "5")

    def test_a_sysex_string_finds_room(self):
        # String 0 holds other bytes here, in use by bank 8: the song's goes to a free one
        sysex = self.demo["SysEx_Strings"]
        sysex.loc[sysex["Index"] == "0", "Bytes"] = "7E 7F 06 02"
        loaded, notes = sf.load_song(self.demo, song(read_config_csv(DEMO), 8), 20)
        moved = row(loaded, "Button_Settings", 20, "1")
        self.assertEqual(moved["A_CommandType"], "SysEx")
        j = int(moved["A_Number_(PC/CC/Note)"])
        self.assertNotEqual(j, 0)
        strings = loaded["SysEx_Strings"]
        self.assertEqual(strings[strings["Index"] == str(j)]["Bytes"].iloc[0], "7E 7F 06 01")
        self.assertEqual(strings[strings["Index"] == "0"]["Bytes"].iloc[0], "7E 7F 06 02")
        self.assertIn(f"its SysEx string 0 is string {j} here", notes)
        # The strings the rest of bank 8 sends kept their numbers
        self.assertEqual(row(loaded, "Button_Settings", 20, "2")["A_Number_(PC/CC/Note)"], "1")

    def test_no_room_for_a_sysex_string(self):
        sysex = self.demo["SysEx_Strings"]
        sysex["Bytes"] = [f"00 {i:02X}" for i in range(16)]
        with self.assertRaisesRegex(ValueError, "all 16 strings here are in use"):
            sf.load_song(self.demo, song(read_config_csv(DEMO), 8), 20)

    def test_a_busy_place_moves_to_a_free_bank(self):
        live = template("Ableton_Live")
        set_cells(live, "Button_Settings", 30, "4", Label="MINE", A_CommandType="CC",
                  **{"A_Number_(PC/CC/Note)": "5", "A_Channel_(PC/CC/Note/PB)": "1"})
        live["Bank_Naming"].loc[live["Bank_Naming"]["Bank_Number"] == "30", "Bank_Name_Large"] = "MINE"
        loaded, notes = sf.load_song(live, song(self.demo, 12), 5)
        self.assertEqual(row(loaded, "Button_Settings", 30, "4")["Label"], "MINE")
        self.assertIn("what the song runs in bank 30 is in bank 31 here, which was empty", notes)
        self.assertEqual(commands(row(loaded, "Button_Settings", 31, 4)), commands(row(self.demo, "Button_Settings", 30, 4)))
        combos = loaded["Combo_Settings"]
        self.assertEqual(combos[combos["Bank"] == "5"]["Run_Bank"].tolist(), ["31"])

    def test_no_free_bank(self):
        with self.assertRaisesRegex(ValueError, "the song runs bank 30 button 4, which holds something else here, "
                                                "and no bank here is free"):
            sf.load_song(template("HX_Stomp"), song(self.demo, 12), 5)

    def test_into_a_bank_it_runs(self):
        # Bank 0 runs bank 11's button B: loaded into bank 11, that goes to a free bank
        live = template("Ableton_Live")
        loaded, notes = sf.load_song(live, song(self.demo, 0), 11)
        self.assertIn("what the song runs in bank 11 is in bank 31 here, which was empty", notes)
        self.assertEqual(row(loaded, "LongPress_Settings", 11, "2")["A_OnValue_(CC/PB)"], "31")

    def test_too_many_combinations(self):
        live = template("Ableton_Live")
        combos = [{"Switches": f"{a}+{b}", "Bank": "All", "Run_Bank": "0", "Run_Button": "1", "Run_List": "Short"}
                  for a, b in [("1", "2"), ("1", "3"), ("1", "4"), ("2", "3"), ("2", "4"), ("3", "4"),
                               ("A", "B"), ("A", "C"), ("A", "D"), ("B", "C"), ("B", "D"), ("C", "D")]]
        import pandas as pd
        live["Combo_Settings"] = pd.DataFrame(combos)
        with self.assertRaisesRegex(ValueError, "the song brings 1 combinations and this configuration has 12 "
                                                "for its other banks: at most 12 fit"):
            sf.load_song(live, song(self.demo, 12), 5)

    def test_a_program_named_otherwise_here(self):
        names = self.demo["Preset_Names"]
        names.loc[names["Program"] == "1", "Name"] = "DIRT"
        loaded, notes = sf.load_song(self.demo, song(read_config_csv(DEMO), 12), 20)
        self.assertIn("program 1 keeps the name DIRT it has here; the song calls it CRUNCH", notes)

    def test_a_configuration_is_no_song(self):
        with self.assertRaisesRegex(ValueError, "this is a whole configuration, not a song"):
            sf.load_song(self.demo, self.demo, 3)
        with self.assertRaisesRegex(ValueError, "there is no bank 32"):
            sf.save_song(self.demo, 32)

    def test_the_file_name(self):
        self.assertEqual(sf.file_name(self.demo, 12), "S01_song_1.song.csv")
        self.demo["Bank_Naming"].loc[self.demo["Bank_Naming"]["Bank_Number"] == "12",
                                     ["Bank_Name_Large", "Bank_Info_Small"]] = float("nan")
        self.assertEqual(sf.file_name(self.demo, 12), "bank-12.song.csv")

    def test_the_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            s, out = os.path.join(tmp, "s.song.csv"), os.path.join(tmp, "out.csv")
            r = subprocess.run([sys.executable, "Song.py", "save", DEMO, "12", "-o", s],
                               cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = subprocess.run([sys.executable, "Song.py", "load", os.path.join("templates", "Ableton_Live.csv"), s, "5",
                                "-o", out], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("Bank 30 button 4 was empty here", r.stdout)
            self.assertEqual(row(read_config_csv(out), "Bank_Naming", 5)["Bank_Name_Large"], "S01")
            r = subprocess.run([sys.executable, "Song.py", "load", os.path.join("templates", "HX_Stomp.csv"), s, "5",
                                "-o", out], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("no bank here is free", r.stdout)


if __name__ == "__main__":
    unittest.main()
