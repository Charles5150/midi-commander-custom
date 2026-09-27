"""The display's fonts: the pictures in fonts/*.txt, the packed tables
tools/pack_fonts.py makes from them in ssd1306_fonts.c, and what the
firmware promises to draw with them."""
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SSD1306 = os.path.join(ROOT, "firmware", "Middlewares", "stm32-ssd1306-master", "ssd1306")

spec = importlib.util.spec_from_file_location("pack_fonts", os.path.join(ROOT, "tools", "pack_fonts.py"))
pack_fonts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack_fonts)


class FontTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fonts = pack_fonts.load_fonts()

    def test_c_file_is_what_the_pictures_give(self):
        """ssd1306_fonts.c is tools/pack_fonts.py's output for fonts/*.txt, so a picture
        changed without running it, or a table edited by hand, is caught here."""
        with open(pack_fonts.C_FILE, encoding="ascii") as handle:
            self.assertEqual(handle.read(), pack_fonts.c_source(self.fonts))

    def test_packing_keeps_every_pixel(self):
        """A character packed to the bytes the firmware keeps unpacks, read as ssd1306_Glyph
        reads them, to the very rows of its picture; and the bytes are what the flash pays."""
        sizes = {}
        for name, (width, height, last, glyphs) in self.fonts:
            for i, rows in enumerate(glyphs):
                packed = pack_fonts.pack_glyph(rows, width)
                self.assertEqual(len(packed), pack_fonts.bytes_per_glyph(width, height))
                self.assertEqual(pack_fonts.unpack_glyph(packed, width, height), rows, f"{name} {chr(32 + i)!r}")
            sizes[name] = len(glyphs) * pack_fonts.bytes_per_glyph(width, height)
        self.assertEqual(sizes, {"6x8": 95 * 6, "7x10": 95 * 9, "11x18": 64 * 25})

    def test_fonts_cover_what_the_tools_send(self):
        """The small fonts hold every printable ASCII character, 0x20 to 0x7E, as display_text
        promises; the large one stops at _ to make room in flash, and the firmware draws
        lowercase in it as capitals."""
        last = {name: font[2] for name, font in self.fonts}
        self.assertEqual(last, {"6x8": "~", "7x10": "~", "11x18": "_"})
        with open(os.path.join(SSD1306, "ssd1306.c"), encoding="utf-8") as handle:
            self.assertIn("ch = (ch >= 'a' && ch <= 'z') ? ch - 32 : '?';", handle.read())

    def test_a_picture_is_checked(self):
        """A row of the wrong width, a character out of order or one short of rows is refused."""
        good = "width 2\nheight 2\nlast !\n[ ]\n..\n..\n[!]\n#.\n.#\n"
        self.assertEqual(pack_fonts.parse_font(good)[3], [[[0, 0], [0, 0]], [[1, 0], [0, 1]]])
        for bad in (good.replace("#.\n", "#..\n"), good.replace("[!]", "[\"]"), good.replace(".#\n", "")):
            with self.assertRaises(ValueError):
                pack_fonts.parse_font(bad)


if __name__ == "__main__":
    unittest.main()
