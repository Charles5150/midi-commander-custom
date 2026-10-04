"""The device and host templates pack and read back as the manual describes.

Each row is a button of a template, as the pedal reads it back: its bank,
button, command, number and on / off values, or its key and modifiers.
The Quad Cortex, FM3, HX Stomp and Kemper Player ones have their own tests
in test_roundtrip.py.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import lib.binaryUnpacker as unpacker  # noqa: E402
import lib.configPacker as packer  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402

# (bank, button, type, number, on, off); "" off sends nothing
CC_BUTTONS = {
    "H90.csv": [(0, "1", "CC", "21", "127", "127"), (0, "D", "CC", "27", "127", ""),
                (31, "1", "CC", "40", "127", "127")],
    "TimeLine.csv": [(0, "1", "CC", "102", "0", "127"), (0, "D", "CC", "93", "127", ""),
                     (30, "1", "CC", "87", "127", ""), (31, "A", "CC", "80", "0", "127")],
    "BigSky.csv": [(0, "2", "CC", "97", "127", "0"), (31, "C", "CC", "81", "0", "127")],
    "Volante.csv": [(0, "4", "CC", "45", "127", "0"), (30, "2", "CC", "49", "127", ""),
                    (31, "1", "CC", "21", "127", "0")],
    "Iridium.csv": [(0, "2", "CC", "19", "2", ""), (0, "C", "CC", "18", "3", ""),
                    (0, "D", "CC", "102", "0", "127")],
    "Ampero_II.csv": [(0, "4", "CC", "25", "4", ""), (0, "A", "CC", "79", "127", "0"),
                      (30, "B", "CC", "65", "0", "127"), (31, "4", "CC", "78", "0", "2")],
    "RC-600.csv": [(0, "1", "CC", "80", "127", "0"), (31, "3", "CC", "88", "127", "0")],
    "Gig_Performer.csv": [(0, "D", "CC", "20", "127", "0")],
    "Cantabile.csv": [(0, "D", "CC", "20", "127", "0")],
    "Ableton_Live.csv": [(1, "D", "CC", "28", "127", "0")],
    "MainStage.csv": [(31, "A", "CC", "20", "127", "0")],
    "Enzo_X.csv": [(0, "4", "CC", "14", "0", "127"), (0, "D", "CC", "99", "127", ""),
                   (31, "2", "CC", "118", "127", "0"), (31, "3", "CC", "117", "127", "")],
    "LVX.csv": [(16, "D", "CC", "99", "127", ""), (31, "A", "CC", "100", "127", ""),
                (31, "4", "CC", "103", "127", "")],
    "MercuryX.csv": [(0, "D", "CC", "118", "127", "0"), (31, "1", "CC", "14", "0", "127")],
}
# (bank, button, key, modifiers)
KEYS = {
    "MainStage.csv": [(0, "1", "up", "0"), (0, "4", "right", "0"), (0, "C", "t", "8"), (0, "D", "t", "1")],
    "Gig_Performer.csv": [(0, "2", "down", "0"), (0, "C", "t", "2")],
    "Cantabile.csv": [(0, "1", "t", "2"), (0, "2", "t", "0")],
    "Ableton_Live.csv": [(0, "3", "enter", "0"), (0, "C", "f9", "0"), (0, "B", "space", "2")],
}
# The Program Change each bank sends on entering, bank: program
PROGRAMS = {
    "H90.csv": {0: 0, 30: 30}, "TimeLine.csv": {29: 29}, "BigSky.csv": {30: 30},
    "Volante.csv": {29: 29}, "Iridium.csv": {31: 31}, "Ampero_II.csv": {29: 29},
    "RC-600.csv": {0: 0, 30: 30}, "MainStage.csv": {30: 30}, "Gig_Performer.csv": {31: 31},
    "Cantabile.csv": {31: 31},
}


def norm(value):
    s = "" if value is None else str(value).strip()
    return "" if s.lower() in ("nan", "none") else s.removesuffix(".0")


def read(name):
    tables = unpacker.unpack_config(packer.pack_config(read_config_csv(os.path.join(ROOT, "templates", name))))
    return tables[0], tables[1], tables[2], tables[5]


def row(frame, bank, btn=None):
    mask = frame["Bank_Number"].astype(str) == str(bank)
    if btn is not None:
        mask &= frame["Button_Identifier"] == btn
    return frame[mask].iloc[0]


class TemplatesTest(unittest.TestCase):
    def test_cc_buttons(self):
        for name, rows in CC_BUTTONS.items():
            buttons = read(name)[2]
            for bank, btn, kind, number, on, off in rows:
                with self.subTest(f"{name} {bank} {btn}"):
                    r = row(buttons, bank, btn)
                    self.assertEqual(r["A_CommandType"], kind)
                    self.assertEqual(norm(r["A_Number_(PC/CC/Note)"]), number)
                    self.assertEqual(norm(r["A_OnValue_(CC/PB)"]), on)
                    self.assertEqual(norm(r["A_OffValue_(CC)"]), off)

    def test_keys(self):
        for name, rows in KEYS.items():
            buttons = read(name)[2]
            for bank, btn, key, mods in rows:
                with self.subTest(f"{name} {bank} {btn}"):
                    r = row(buttons, bank, btn)
                    self.assertEqual(r["A_CommandType"], "Key")
                    self.assertEqual(norm(r["A_OnValue_(CC/PB)"]), key)
                    self.assertEqual(norm(r["A_Number_(PC/CC/Note)"]) or "0", mods)

    def test_banks_load_their_program(self):
        for name, programs in PROGRAMS.items():
            enter = read(name)[3]
            for bank, program in programs.items():
                with self.subTest(f"{name} {bank}"):
                    r = row(enter, bank)
                    self.assertEqual(r["A_CommandType"], "PC")
                    self.assertEqual(norm(r["A_Number_(PC/CC/Note)"]), str(program))
                    self.assertEqual(norm(r["A_BankSelect_(PC)"]), "")    # no Bank Select

    def test_meris_presets_on_buttons(self):
        # Six presets a bank, 1 2 3 then A B C, and the favorites after 99
        for name in ("Enzo_X.csv", "LVX.csv", "MercuryX.csv"):
            tables = unpacker.unpack_config(packer.pack_config(read_config_csv(os.path.join(ROOT, "templates", name))))
            buttons, long_press = tables[2], tables[3]
            for bank, btn, program, label in ((0, "1", "1", "P01"), (0, "C", "6", "P06"), (15, "A", "94", "P94"),
                                              (16, "3", "99", "P99"), (16, "A", "100", "FAV1"),
                                              (16, "C", "102", "FAV3")):
                with self.subTest(f"{name} {bank} {btn}"):
                    r = row(buttons, bank, btn)
                    self.assertEqual((r["A_CommandType"], norm(r["A_Number_(PC/CC/Note)"]), r["Label"]),
                                     ("PC", program, label))
            with self.subTest(f"{name} tuner"):
                r = row(long_press, 5, "4")
                self.assertEqual((r["A_CommandType"], norm(r["A_Number_(PC/CC/Note)"])), ("CC", "117"))

    def test_navigation_keys_read_back(self):
        import lib.cmdBinaryPacker as cbp
        for name, code in (("up", 82), ("down", 81), ("left", 80), ("right", 79), ("pageup", 75),
                           ("pagedown", 78), ("home", 74), ("end", 77), ("delete", 76)):
            with self.subTest(name):
                self.assertEqual(cbp.get_hid_code(name), code)
                self.assertEqual(unpacker._HID_NAMES[code], name)

    def test_start_and_stop_for_the_rc600(self):
        buttons = read("RC-600.csv")[2]
        self.assertEqual((row(buttons, 0, "A")["A_CommandType"], row(buttons, 0, "B")["A_CommandType"]),
                         ("Start", "Stop"))

    def test_ableton_live_walks_its_two_banks(self):
        settings = read("Ableton_Live.csv")[0].set_index("Label")["Value"]
        self.assertEqual(norm(settings["Setlist_Mode"]), "Y")

    def test_expression_pedals(self):
        for name, ccs in (("H90.csv", ("16", "17")), ("TimeLine.csv", ("100", "14")), ("Iridium.csv", ("7", "13")),
                          ("Ampero_II.csv", ("11", "7")), ("RC-600.csv", ("70", "71")),
                          ("Enzo_X.csv", ("4", "60")), ("LVX.csv", ("4", "1")), ("MercuryX.csv", ("4", "1"))):
            with self.subTest(name):
                settings = read(name)[0].set_index("Label")["Value"]
                self.assertEqual((norm(settings["Exp1_CC"]), norm(settings["Exp2_CC"])), ccs)


if __name__ == "__main__":
    unittest.main()
