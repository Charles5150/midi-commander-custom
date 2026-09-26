"""Names and labels with characters the display cannot draw (#117).

Run from the repository root:

    python -m unittest python/tests/test_display_text.py
"""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lib.binaryUnpacker as unpacker  # noqa: E402
import lib.cmdBinaryPacker as cbp  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
from lib.configPacker import pack_config, pack_label  # noqa: E402
from lib.displayText import display_bytes, display_text  # noqa: E402
from lib.midiDevice import banner_sysex, text_sysex  # noqa: E402

DEMO_CSV = os.path.join(os.path.dirname(HERE), "demo-all-features.csv")


class DisplayTextTest(unittest.TestCase):
    def test_accents_become_the_plain_letter(self):
        self.assertEqual(display_text("Canción"), "Cancion")
        self.assertEqual(display_text("Ñu"), "Nu")
        self.assertEqual(display_text("Über Größe"), "Uber Grosse")
        self.assertEqual(display_text("Çà ê ï ø å"), "Ca e i o a")

    def test_a_mark_apart_from_its_letter(self):
        self.assertEqual(display_text("Canción"), "Cancion")
        self.assertEqual(display_text("́x"), "x")

    def test_punctuation_the_keyboard_turns_fancy(self):
        self.assertEqual(display_text("“Hola” – ‘yo’…"), '"Hola" - \'yo\'...')
        self.assertEqual(display_text("¿Qué?¡Sí!"), "?Que?!Si!")

    def test_anything_else_is_a_question_mark(self):
        self.assertEqual(display_text("5€ 😀 中"), "5? ? ?")
        self.assertEqual(display_text("a\x01b\x7fc"), "a?b?c")

    def test_what_the_display_draws_is_kept(self):
        text = "".join(chr(c) for c in range(0x20, 0x7F))
        self.assertEqual(display_text(text), text)
        self.assertEqual(display_text(None), "")

    def test_bytes_cut_and_padded(self):
        self.assertEqual(display_bytes("Ñu", 4), b"Nu  ")
        self.assertEqual(display_bytes("Straße", 5), b"Stras")


class PackTest(unittest.TestCase):
    """A whole configuration with names a Spanish speaker writes."""

    @classmethod
    def setUpClass(cls):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"].copy()
        g.loc[g["Label"] == "ConfigName", "Value"] = "Canción del Año"
        banks = sections["Bank_Naming"].copy()
        banks.loc[banks.index[0], "Bank_Name_Large"] = "Ñu"
        banks.loc[banks.index[0], "Bank_Info_Small"] = "Pequeño€"
        buttons = sections["Button_Settings"].copy()
        buttons.loc[buttons.index[0], "Label"] = "Días"
        cls.sections = {**sections, "Global_Settings": g, "Bank_Naming": banks,
                        "Button_Settings": buttons}
        cls.packed = pack_config(cls.sections)
        (cls.df_global, cls.df_banks, cls.df_buttons, *_) = unpacker.unpack_config(cls.packed)

    def test_packs(self):
        self.assertEqual(len(self.packed), unpacker.CONFIG_SIZE)

    def test_config_name(self):
        self.assertEqual(self.packed[16:32], b"Cancion del Ano ")
        got = self.df_global.set_index("Label")["Value"]
        self.assertEqual(got["ConfigName"], "Cancion del Ano")

    def test_bank_names(self):
        self.assertEqual(self.df_banks.iloc[0]["Bank_Name_Large"], "Nu")
        self.assertEqual(self.df_banks.iloc[0]["Bank_Info_Small"], "Pequeno?")

    def test_label(self):
        self.assertEqual(self.df_buttons.iloc[0]["Label"], "Dias")
        self.assertEqual(pack_label("ñ", reset=True), bytes([ord("n") | 0x80]) + b"   ")

    def test_cycle_label(self):
        labels = []
        cbp.cmd_cycle({"OnValue_(CC/PB)": "Más"}, labels)
        self.assertEqual(labels, ["Mas"])
        self.assertEqual(cbp.pack_cycle_labels(labels)[:4], b"Mas ")


class TextToThePedalTest(unittest.TestCase):
    def test_text_sysex(self):
        self.assertEqual(bytes(text_sysex("Canción")[5:-1]), b"Cancion")

    def test_banner_sysex(self):
        self.assertEqual(bytes(banner_sysex("Añoranza ")[4:-1]), b"Anoranza")


class CsvFromExcelTest(unittest.TestCase):
    """Excel saves "CSV UTF-8" with a mark at the start, and a plain "CSV" in
    Windows-1252 on Windows: both open, accents and all."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        with open(DEMO_CSV, encoding="utf-8") as f:
            self.text = f.read().replace("ConfigName,DEMO ALL", "ConfigName,Canción")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def read(self, encoding):
        path = os.path.join(self.dir, "c.csv")
        with open(path, "w", encoding=encoding, newline="\r\n") as f:
            f.write(self.text)
        sections = read_config_csv(path)
        name = sections["Global_Settings"].set_index("Label")["Value"]["ConfigName"]
        return sections, name

    def test_utf8_with_mark(self):
        sections, name = self.read("utf-8-sig")
        self.assertEqual(name, "Canción")
        self.assertEqual(set(sections), set(read_config_csv(DEMO_CSV)))

    def test_windows_1252(self):
        sections, name = self.read("cp1252")
        self.assertEqual(name, "Canción")
        self.assertEqual(pack_config(sections)[16:32], b"Cancion         ")

    def test_plain_utf8(self):
        self.assertEqual(self.read("utf-8")[1], "Canción")


if __name__ == "__main__":
    unittest.main()
