"""The notes the web configurator's Stage view shows, one per bank: a Notes
column in Bank_Naming that only the tools keep. The pedal never holds them,
so they change nothing it is sent, and they go wherever the bank's name goes:
through the CSV, the page's bridge and a song file."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from lib import webBridge as wb  # noqa: E402
import lib.songFile as sf  # noqa: E402
from lib.configCsv import read_config_csv, write_sections  # noqa: E402

DEMO = os.path.join(ROOT, "demo-all-features.csv")
# As the page stores it: a line break as \n, a backslash as \\
NOTE = 'Capo 2, key "Am"\\nVerse: ¡más fuerte! # not a comment\\n* nor a section \\\\o/'


def demo_json():
    with open(DEMO, "rb") as f:
        return json.loads(wb.csv_to_sections(f.read()))


def with_note(sections, bank, note):
    naming = sections["Bank_Naming"]
    if "Notes" not in naming["columns"]:
        naming["columns"].append("Notes")
        for r in naming["rows"]:
            r.append("")
    at = naming["columns"].index("Bank_Number")
    row = next(r for r in naming["rows"] if r[at] == str(bank))
    row[-1] = note
    return sections


def notes_of(sections):
    df = sections["Bank_Naming"]
    return {str(r["Bank_Number"]): r["Notes"] for _, r in df.iterrows() if isinstance(r["Notes"], str)}


class StageNotesTest(unittest.TestCase):
    def test_a_note_goes_through_the_csv_as_written(self):
        text = wb.sections_to_csv(json.dumps(with_note(demo_json(), 3, NOTE)))
        back = json.loads(wb.csv_to_sections(text.encode("utf-8")))
        naming = back["Bank_Naming"]
        notes = {r[0]: r[naming["columns"].index("Notes")] for r in naming["rows"]}
        self.assertEqual(notes["3"], NOTE)
        self.assertEqual({b for b, n in notes.items() if n}, {"3"})
        self.assertEqual(len(text.splitlines()), len(wb.sections_to_csv(json.dumps(demo_json())).splitlines()),
                         "a note is one line of the CSV")

    def test_a_note_changes_nothing_the_pedal_gets(self):
        plain = demo_json()
        self.assertEqual(wb.pack(json.dumps(with_note(demo_json(), 3, NOTE))), wb.pack(json.dumps(plain)))

    def test_a_song_carries_its_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "noted.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write(wb.sections_to_csv(json.dumps(with_note(demo_json(), 1, NOTE))))
            sections = read_config_csv(path)
            song_path = os.path.join(tmp, "s.song.csv")
            with open(song_path, "w", encoding="utf-8") as f:
                f.write(sf.save_song(sections, 1))
            song = read_config_csv(song_path)
            loaded, _ = sf.load_song(read_config_csv(DEMO), song, 30)
            self.assertEqual(notes_of(loaded), {"30": NOTE})
            again = os.path.join(tmp, "again.csv")
            write_sections(again, loaded, "test")
            self.assertEqual(notes_of(read_config_csv(again)), {"30": NOTE})


if __name__ == "__main__":
    unittest.main()
