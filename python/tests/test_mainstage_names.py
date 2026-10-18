"""A MainStage concert's patch names as the pedal's preset names (MainStage_Names.py)."""

import os
import plistlib
import subprocess
import sys
import tempfile
import unittest

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from lib.configCsv import read_config_csv  # noqa: E402
from lib.configPacker import pack_flash_image  # noqa: E402
from lib.mainstageConcert import Patch, concert_patches, preset_names, with_names  # noqa: E402

PYTHON = os.path.join(HERE, "..")
TEMPLATE = os.path.join(HERE, "..", "templates", "MainStage.csv")


def write_patch(folder, name, program=None, bank=None, nodes=None):
    """A .patch folder with its data.plist, binary as MainStage writes it."""
    os.makedirs(folder, exist_ok=True)
    engine = {"name": name, "hasProgramChange": program is not None, "patchChangeNum": program or 0,
              "hasBankSelect": bank is not None, "bankSelectNumber": bank or 0}
    data = {"channels": [], "patch": {"engineNode": engine}}
    if nodes is not None:
        data["nodes"] = nodes
    with open(os.path.join(folder, "data.plist"), "wb") as f:
        plistlib.dump(data, f, fmt=plistlib.FMT_BINARY)


def concert(tmp):
    """Two sets and a patch on its own, in the Patch List's order, not the folders'."""
    path = os.path.join(tmp, "Gig.concert")
    root = os.path.join(path, "Concert.patch")
    write_patch(root, "Concert", nodes=["Songs.patch", "Encore.patch", "Spare.patch"])
    songs = os.path.join(root, "Songs.patch")
    write_patch(songs, "Songs", nodes=["Zebra.patch", "Canción.patch", "Gone.patch"])
    write_patch(os.path.join(songs, "Zebra.patch"), "Zebra Intro", program=0)
    write_patch(os.path.join(songs, "Canción.patch"), "Canción", program=1)
    encore = os.path.join(root, "Encore.patch")
    write_patch(encore, "Encore", nodes=["Last.patch", "Again.patch", "Far.patch"])
    write_patch(os.path.join(encore, "Last.patch"), "Last Dance", program=2)
    write_patch(os.path.join(encore, "Again.patch"), "Again", program=2)
    write_patch(os.path.join(encore, "Far.patch"), "Far Away", program=3, bank=1)
    write_patch(os.path.join(root, "Spare.patch"), "Spare")
    return path


class ConcertTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.concert = concert(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_patches_in_order(self):
        self.assertEqual(concert_patches(self.concert), [
            Patch("Zebra Intro", 0, None, "Songs"), Patch("Canción", 1, None, "Songs"),
            Patch("Last Dance", 2, None, "Encore"), Patch("Again", 2, None, "Encore"),
            Patch("Far Away", 3, 1, "Encore"), Patch("Spare", None, None, None)])

    def test_the_names_and_what_is_left_out(self):
        names, notes = preset_names(concert_patches(self.concert))
        self.assertEqual(names, {0: "Zebra Intro", 1: "Canción", 2: "Last Dance"})
        self.assertEqual(len(notes), 3)
        self.assertIn("Last Dance's too", notes[0])
        self.assertIn("Bank Select 1", notes[1])
        self.assertIn("Spare: no Program Change", notes[2])

    def test_not_a_concert(self):
        with self.assertRaisesRegex(ValueError, "not a MainStage concert"):
            concert_patches(self.tmp.name)

    def test_names_put_in_kept_and_cut(self):
        old = pd.DataFrame([["1", "OLD"], ["9", "KEPT"]], columns=["Program", "Name"])
        df = with_names(old, {0: "Zebra Intro", 1: "Canción"})
        self.assertEqual(df.values.tolist(), [["0", "Zebra In"], ["1", "Cancion"], ["9", "KEPT"]])
        self.assertEqual(with_names(old, {0: "A"}, replace=True).values.tolist(), [["0", "A"]])

    def test_the_tool_writes_the_template(self):
        out = os.path.join(self.tmp.name, "mine.csv")
        result = subprocess.run([sys.executable, "MainStage_Names.py", self.concert, "--csv", TEMPLATE, "-o", out],
                                cwd=PYTHON, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PC   1  Cancion   Songs / Canción", result.stdout)
        self.assertIn("3 names written", result.stdout)
        sections = read_config_csv(out)
        self.assertEqual(sections["Preset_Names"].values.tolist(),
                         [["0", "Zebra In"], ["1", "Cancion"], ["2", "Last Dan"]])
        pack_flash_image(sections)
        # The template itself is left as it is
        self.assertNotIn("Preset_Names", read_config_csv(TEMPLATE))

    def test_the_tool_lists_without_a_csv(self):
        result = subprocess.run([sys.executable, "MainStage_Names.py", self.concert],
                                cwd=PYTHON, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("note: Spare: no Program Change, left out", result.stdout)
        result = subprocess.run([sys.executable, "MainStage_Names.py", self.tmp.name],
                                cwd=PYTHON, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


class TemplateTest(unittest.TestCase):
    def test_the_patch_steps_are_program_changes(self):
        sections = read_config_csv(TEMPLATE)
        buttons = sections["Button_Settings"]
        for bank, btn, direction in (("0", "1", "Down"), ("0", "2", "Up"), ("30", "2", "Up"), ("31", "3", "Down")):
            r = buttons[(buttons["Bank_Number"] == bank) & (buttons["Button_Identifier"] == btn)].iloc[0]
            self.assertEqual((r["A_CommandType"], r["A_KeyMode_(Key)"]), ("PCInc", direction), (bank, btn))
        banks = sections["Bank_Naming"]
        self.assertEqual(banks[banks["Bank_Number"] == "5"].iloc[0]["Bank_Info_Small"], "$N")


if __name__ == "__main__":
    unittest.main()
