#!/usr/bin/env python3
"""Packs the display's fonts, drawn in ssd1306/fonts/*.txt, into ssd1306_fonts.c.

A font is a text file: `width`, `height` and `last`, its last character, then
one block per character from the space to that one, `[A]` and its rows, a #
for a lit pixel and a . for a dark one; a line starting with ; is a remark.
The C file holds each font as bytes: the rows of a character one after the
other, `width` bits each with the leftmost pixel first, every character from
a byte boundary, and ssd1306_Glyph unpacks them. Run it after changing a
picture; a test checks the C file is what the pictures give.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SSD1306 = os.path.normpath(os.path.join(HERE, "..", "firmware", "Middlewares", "stm32-ssd1306-master", "ssd1306"))
FONTS_DIR = os.path.join(SSD1306, "fonts")
C_FILE = os.path.join(SSD1306, "ssd1306_fonts.c")
FONTS = ("6x8", "7x10", "11x18")   # in the order of the C file
MAX_HEIGHT = 18                    # SSD1306_FONT_MAX_HEIGHT, the buffer ssd1306_Glyph unpacks into


def parse_font(text):
    """The font of a picture: (width, height, last, glyphs), glyphs one list of
    rows per character from the space on, a row a list of 0 and 1."""
    keys = {}
    glyphs = []
    rows = None
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.startswith(";"):
            continue
        width = keys.get("width")
        if rows is not None and len(line) == width and not set(line) - {"#", "."}:
            if len(rows) == keys["height"]:
                raise ValueError(f"line {n}: more than {keys['height']} rows for [{chr(31 + len(glyphs))}]")
            rows.append([1 if p == "#" else 0 for p in line])
        elif len(line) == 3 and line[0] == "[" and line[2] == "]":
            for key in ("width", "height", "last"):
                if key not in keys:
                    raise ValueError(f"line {n}: {key} must come before the first character")
            if rows is not None and len(rows) != keys["height"]:
                raise ValueError(f"line {n}: [{chr(31 + len(glyphs))}] has {len(rows)} rows, not {keys['height']}")
            expected = chr(32 + len(glyphs))
            if line[1] != expected:
                raise ValueError(f"line {n}: [{line[1]}] where [{expected}] should come")
            rows = []
            glyphs.append(rows)
        elif rows is None and " " in line:
            key, value = line.split(" ", 1)
            if key in ("width", "height"):
                keys[key] = int(value)
            elif key == "last":
                keys[key] = value
            else:
                raise ValueError(f"line {n}: {key!r} is not width, height or last")
        else:
            raise ValueError(f"line {n}: {line!r} is neither a row nor a character")
    width, height, last = keys.get("width"), keys.get("height"), keys.get("last")
    if not (width and 1 <= width <= 16) or not (height and 1 <= height <= MAX_HEIGHT) or not last or len(last) != 1:
        raise ValueError(f"width 1 to 16, height 1 to {MAX_HEIGHT} and a last character are needed")
    if rows is None or len(rows) != height:
        raise ValueError("the last character is not complete")
    if len(glyphs) != ord(last) - 31:
        raise ValueError(f"{len(glyphs)} characters where a space to {last} are {ord(last) - 31}")
    return width, height, last, glyphs


def pack_glyph(rows, width):
    """The bytes of a character: its rows one after the other, width bits
    each, the leftmost pixel first, padded to whole bytes at the end."""
    bits = "".join(str(p) for row in rows for p in row)
    bits += "0" * (-len(bits) % 8)
    return int(bits, 2).to_bytes(len(bits) // 8, "big") if bits else b""


def unpack_glyph(data, width, height):
    """The rows a character's bytes hold, as ssd1306_Glyph reads them."""
    bits = "".join(f"{b:08b}" for b in data)
    return [[int(bits[i * width + j]) for j in range(width)] for i in range(height)]


def bytes_per_glyph(width, height):
    return (width * height + 7) // 8


def _name(ch):
    return {" ": "space", "\\": "backslash"}.get(ch, ch)


def _c_char(ch):
    return "'\\" + ch + "'" if ch in "'\\" else "'" + ch + "'"


def c_source(fonts):
    """ssd1306_fonts.c for fonts, a list of (name, parsed font)."""
    out = [
        "// The display's fonts, packed by tools/pack_fonts.py from the pictures in",
        "// fonts/: to change one, edit its picture and run the script, not this.",
        "// A character is its rows one after the other, FontWidth bits each with",
        "// the leftmost pixel first, from a byte boundary; ssd1306_Glyph unpacks it.",
        "",
        '#include "ssd1306_fonts.h"',
        "",
    ]
    for name, (width, height, last, glyphs) in fonts:
        per = bytes_per_glyph(width, height)
        out += [
            f"#ifdef SSD1306_INCLUDE_FONT_{name}",
            f"// From a space to {_name(last)}: {len(glyphs)} characters of {per} bytes, {height} rows of {width} bits",
            f"static const uint8_t Font{name}[] = {{",
        ]
        for i, rows in enumerate(glyphs):
            out.append("\t" + " ".join(f"0x{b:02X}," for b in pack_glyph(rows, width)) + f"  // {_name(chr(32 + i))}")
        out += [
            "};",
            f"_Static_assert({height} <= SSD1306_FONT_MAX_HEIGHT, \"ssd1306_Glyph's buffer is too small for Font{name}\");",
            f"const FontDef Font_{name} = {{{width}, {height}, {_c_char(last)}, Font{name}}};",
            "#endif",
            "",
        ]
    return "\n".join(out)


def load_fonts():
    fonts = []
    for name in FONTS:
        with open(os.path.join(FONTS_DIR, name + ".txt"), encoding="ascii") as handle:
            fonts.append((name, parse_font(handle.read())))
    return fonts


def main(argv):
    fonts = load_fonts()
    text = c_source(fonts)
    if "--check" in argv:
        with open(C_FILE, encoding="ascii") as handle:
            if handle.read() != text:
                print("ssd1306_fonts.c is not what fonts/*.txt give: run tools/pack_fonts.py")
                return 1
        print("ssd1306_fonts.c is up to date")
        return 0
    with open(C_FILE, "w", encoding="ascii") as handle:
        handle.write(text)
    for name, (width, height, last, glyphs) in fonts:
        print(f"Font{name}: {len(glyphs)} characters, {len(glyphs) * bytes_per_glyph(width, height)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
