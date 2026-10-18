"""The pedal's clock: Clock_Output, Clock_Burst and Clock_Off_Banks (firmware 1.39)."""

import os
import sys
import unittest

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from lib.binaryUnpacker import unpack_global_settings  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
from lib.configPacker import bank_list, clock_settings, pack_ext2, pack_flash_image  # noqa: E402
from lib.flashLayout import EXT2_CLOCK_OFFSET, EXT2_OFFSET  # noqa: E402

DEMO = os.path.join(HERE, "..", "demo-all-features.csv")


def global_frame(**values):
    return pd.DataFrame([[k, v] for k, v in values.items()], columns=["Label", "Value"])


def with_globals(sections, **values):
    g = sections["Global_Settings"].copy()
    for k, v in values.items():
        if (g["Label"] == k).any():
            g.loc[g["Label"] == k, "Value"] = v
        else:
            g.loc[len(g)] = [k, v]
    return {**sections, "Global_Settings": g}


def read_back(image, label):
    g = unpack_global_settings(image)
    return g.loc[g["Label"] == label, "Value"].iloc[0]


class ClockSettingsTest(unittest.TestCase):
    def test_the_defaults_are_erased_flash(self):
        self.assertEqual(clock_settings(None), b"\xff" * 6)
        self.assertEqual(clock_settings(global_frame(Clock_Output="Both", Clock_Burst="0", Clock_Off_Banks="")),
                         b"\xff" * 6)

    def test_the_bytes(self):
        out = clock_settings(global_frame(Clock_Output="usb", Clock_Burst="4", Clock_Off_Banks="0 5-7, 31"))
        self.assertEqual(out[0], 0xF7, "DIN's bit cleared")
        self.assertEqual(out[1], 4)
        self.assertEqual(int.from_bytes(out[2:6], "little"), 0xFFFFFFFF & ~(1 | 0xE0 | 1 << 31))
        self.assertEqual(clock_settings(global_frame(Clock_Output="DIN"))[0], 0xFB, "USB's bit cleared")

    def test_a_bank_list(self):
        self.assertEqual(bank_list("3 5-7"), [3, 5, 6, 7])
        self.assertEqual(bank_list("7, 3,3"), [3, 7])
        self.assertEqual(bank_list(""), [])
        for bad in ("32", "7-5", "x", "1-"):
            with self.assertRaises(ValueError, msg=bad):
                bank_list(bad)

    def test_mistakes_are_named(self):
        for values, says in (({"Clock_Output": "MIDI"}, "Clock_Output must be Both, USB or DIN"),
                             ({"Clock_Burst": "33"}, "Clock_Burst must be 0-32"),
                             ({"Clock_Off_Banks": "40"}, "banks must be 0-31")):
            with self.assertRaisesRegex(ValueError, says):
                pack_ext2({"Global_Settings": global_frame(**values)})

    def test_alone_they_write_the_second_extension_area(self):
        sections = {"Global_Settings": global_frame(Clock_Burst="2")}
        ext2 = pack_ext2(sections)
        self.assertEqual(ext2[:4], b"EXT2")
        self.assertEqual(ext2[EXT2_CLOCK_OFFSET + 1], 2)
        self.assertIsNone(pack_ext2({"Global_Settings": global_frame(Clock_Burst="0")}))

    def test_read_back_from_the_pedal(self):
        sections = with_globals(read_config_csv(DEMO), Clock_Output="DIN", Clock_Burst="8",
                                Clock_Off_Banks="9 2-4 3")
        image = pack_flash_image(sections)
        self.assertEqual(image[EXT2_OFFSET + EXT2_CLOCK_OFFSET], 0xFB)
        self.assertEqual(read_back(image, "Clock_Output"), "DIN")
        self.assertEqual(read_back(image, "Clock_Burst"), "8")
        self.assertEqual(read_back(image, "Clock_Off_Banks"), "2-4 9")
        plain = pack_flash_image(read_config_csv(DEMO))
        self.assertEqual((read_back(plain, "Clock_Output"), read_back(plain, "Clock_Burst"),
                          read_back(plain, "Clock_Off_Banks")), ("Both", "0", ""))


if __name__ == "__main__":
    unittest.main()
