"""Several setlists in a configuration (firmware 1.33): the first in the slot,
the other three and the names of all four in the second extension area, and
the Bank command that picks the one followed."""

import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# roundtrip_support also puts python/ on the path, for lib
from roundtrip_support import DEMO_CSV, firmware_source  # noqa: E402
import lib.binaryUnpacker as unpacker  # noqa: E402
import lib.cmdBinaryPacker as cbp  # noqa: E402
import lib.configPacker as packer  # noqa: E402
import lib.flashLayout as layout  # noqa: E402
from lib.cheatSheet import cheat_sheet  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
from lib.configDiff import config_sections, diff  # noqa: E402

SHOWS = {1: ("FULL SET", [0, 12, 15]), 2: ("", [3, 4]), 3: ("Bar gigs long", [7]), 4: ("SPARE", [])}


def with_setlist(frame):
    sections = dict(read_config_csv(DEMO_CSV))
    sections[packer.SETLIST_SECTION] = frame
    return sections


def bank_cmd(value):
    return {"CommandType": "Bank", "KeyMode_(Key)": "Setlist", "OnValue_(CC/PB)": value}


class SetlistsTest(unittest.TestCase):
    def test_layout_agrees(self):
        header = firmware_source("Inc", "flash_midi_settings.h")
        self.assertIn("#define SETLIST_COUNT			(4)", header)
        self.assertIn("#define SETLIST_NAME_LEN		(8)", header)
        self.assertIn("#define EXT2_SETLISTS_OFF		(EXT2_PRESET_NAMES_OFF + PRESET_NAME_COUNT * PRESET_NAME_LEN)",
                      header)
        self.assertIn("#define EXT2_SETLIST_NAMES_OFF	(EXT2_SETLISTS_OFF + (SETLIST_COUNT - 1) * SETLIST_MAX)",
                      header)
        self.assertIn("#define EXT2_SIZE				(EXT2_SETLIST_NAMES_OFF + SETLIST_COUNT * SETLIST_NAME_LEN)",
                      header)
        self.assertEqual(layout.EXT2_SETLISTS_OFFSET, 2464)
        self.assertEqual(layout.EXT2_SIZE, 2592)
        self.assertEqual(layout.EXT2_SIZE % 16, 0)        # the tools move it 16 bytes at a time
        self.assertIn("#define BANK_MODE_SETLIST	(11)", firmware_source("Inc", "midi_defines.h"))
        self.assertIn("#define SETLIST_NEXT		(0x7F)", firmware_source("Inc", "midi_defines.h"))

    def test_round_trip(self):
        image = packer.pack_flash_image(with_setlist(packer.setlist_frame(SHOWS)))
        lists = image[layout.SETLIST_OFFSET:layout.SETLIST_OFFSET + 32]
        self.assertEqual(lists, bytes([0, 12, 15] + [0xFF] * 29))      # the first, where it always was
        ext = image[layout.EXT2_OFFSET:]
        self.assertEqual(ext[layout.EXT2_SETLISTS_OFFSET:][:32], bytes([3, 4] + [0xFF] * 30))
        self.assertEqual(ext[layout.EXT2_SETLISTS_OFFSET + 32:][:32], bytes([7] + [0xFF] * 31))
        self.assertEqual(ext[layout.EXT2_SETLISTS_OFFSET + 64:][:32], b"\xff" * 32)
        self.assertEqual(ext[layout.EXT2_SETLIST_NAMES_OFFSET:][:32],
                         b"FULL SET" + b"\xff" * 8 + b"Bar gigs" + b"SPARE   ")
        back = unpacker.unpack_sections(image, image)["Setlist"]
        self.assertEqual(list(back.columns), ["Position", "Bank_Number", "List", "Name"])
        self.assertEqual(packer.setlists(back), {1: ("FULL SET", [0, 12, 15]), 2: ("", [3, 4]),
                                                 3: ("Bar gigs", [7]), 4: ("SPARE", [])})

    def test_one_setlist_reads_as_before(self):
        """A configuration with only the first setlist has neither the new
        columns nor, for its sake, the second extension area."""
        frame = packer.setlist_frame({1: ("", [0, 12]), 2: ("", [])})
        self.assertEqual(list(frame.columns), ["Position", "Bank_Number"])
        sections = with_setlist(frame)
        for name in (packer.MIDI_MAP_SECTION, packer.PRESET_NAMES_SECTION, packer.LONG_PRESS_SECTION,
                     packer.BANK_SWITCH_SECTION):
            sections.pop(name)
        sections[packer.EXPRESSION_SECTION] = sections[packer.EXPRESSION_SECTION].assign(
            Takeover="Jump", Display="Off")
        self.assertIsNone(packer.pack_ext2(sections))
        image = packer.pack_flash_image(sections)
        back = unpacker.unpack_sections(image, image)["Setlist"]
        self.assertEqual(back.values.tolist(), [["1", "0"], ["2", "12"]])

    def test_a_csv_of_before_is_the_first_setlist(self):
        frame = pd.DataFrame([{"Position": "2", "Bank_Number": "5"}, {"Position": "1", "Bank_Number": "9"}])
        self.assertEqual(packer.setlists(frame)[1], ("", [9, 5]))
        self.assertEqual(packer.pack_setlist(frame)[:3], bytes([9, 5, 0xFF]))

    def test_mistakes(self):
        with self.assertRaisesRegex(ValueError, "Setlist row 1, List must be 1-4, not '5'"):
            packer.setlists(pd.DataFrame([{"Position": "1", "Bank_Number": "3", "List": "5"}]))
        with self.assertRaisesRegex(ValueError, "setlist 2 is named both 'A' and 'B'"):
            packer.setlists(pd.DataFrame([{"Position": "1", "Bank_Number": "3", "List": "2", "Name": "A"},
                                          {"Position": "2", "Bank_Number": "4", "List": "2", "Name": "B"}]))

    def test_the_demo(self):
        lists = packer.setlists(read_config_csv(DEMO_CSV)["Setlist"])
        self.assertEqual(lists[1], ("FULL SET", [0, 12, 15, 13, 14, 18, 16, 17, 19, 20]))
        self.assertEqual(lists[2], ("ACOUSTIC", [12, 13, 17, 21]))

    def test_the_bank_command(self):
        self.assertEqual(cbp.cmd_bank(bank_cmd("2")), [0x4B, 1, 0, 0])
        self.assertEqual(cbp.cmd_bank(bank_cmd("")), [0x4B, 0, 0, 0])
        self.assertEqual(cbp.cmd_bank(bank_cmd("Next")), [0x4B, 0x7F, 0, 0])
        with self.assertRaisesRegex(ValueError, "setlist 1-4 or Next, not '5'"):
            cbp.cmd_bank(bank_cmd("5"))
        sections = dict(read_config_csv(DEMO_CSV))
        image = packer.pack_flash_image(sections)
        buttons = unpacker.unpack_sections(image, image)["Button_Settings"]
        row = buttons[(buttons["Bank_Number"] == "30") & (buttons["Button_Identifier"] == "1")].iloc[0]
        self.assertEqual((row["A_CommandType"], row["A_KeyMode_(Key)"], row["A_OnValue_(CC/PB)"]),
                         ("Bank", "Setlist", "Next"))

    def test_what_a_write_changes_and_the_cheat_sheet(self):
        old = with_setlist(packer.setlist_frame(SHOWS))
        new = with_setlist(packer.setlist_frame({**SHOWS, 2: ("PUB", [4, 3])}))
        self.assertEqual([line for line in diff(config_sections(old), config_sections(new)) if "Setlist" in line],
                         ["Setlist 2: banks: 3 4 -> 4 3", "Setlist 2: name: (empty) -> PUB"])
        sheet = cheat_sheet(new)
        self.assertIn("<h2>Setlist 1: FULL SET</h2>", sheet)
        self.assertIn("<h2>Setlist 2: PUB</h2>", sheet)
        self.assertNotIn("Setlist 4", sheet)                # no songs, nothing to print
        one = with_setlist(packer.setlist_frame({1: ("", [0, 12])}))
        self.assertIn("<h2>Setlist</h2>", cheat_sheet(one))


if __name__ == "__main__":
    unittest.main()
