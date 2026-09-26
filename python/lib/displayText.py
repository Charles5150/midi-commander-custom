"""Text as the pedal's display can draw it.

The display fonts hold the printable ASCII characters only, 0x20 to 0x7E. Every
name, label and text the tools send goes through display_text, so a letter
with an accent shows as the plain letter (Canción -> Cancion, Ñu -> Nu) and
anything else the display cannot draw as "?".
"""

import unicodedata

# Characters that do not come apart into a plain letter and a mark
SPELLED = {
    "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ø": "o", "Ø": "O",
    "đ": "d", "Đ": "D", "ł": "l", "Ł": "L", "ı": "i", "þ": "th", "Þ": "Th",
    "‘": "'", "’": "'", "‚": ",", "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
    "–": "-", "—": "-", "−": "-", "…": "...", "·": ".", "×": "x", "÷": "/",
    "¡": "!", "¿": "?", "º": "o", "ª": "a", "°": "o",
    " ": " ", "\t": " ",
}


def display_text(value) -> str:
    """``value`` with every character the display cannot draw replaced."""
    text = unicodedata.normalize("NFC", "" if value is None else str(value))
    out = []
    for c in text:
        if unicodedata.combining(c):
            continue    # a mark NFC could not join to its letter
        c = SPELLED.get(c, c)
        if len(c) == 1 and not 0x20 <= ord(c) <= 0x7E:
            c = "".join(p for p in unicodedata.normalize("NFKD", c)
                        if not unicodedata.combining(p))
        out.append("".join(p if 0x20 <= ord(p) <= 0x7E else "?" for p in c) or "?")
    return "".join(out)


def display_bytes(value, length: int) -> bytes:
    """``value`` as ``length`` display bytes: cut to fit, padded with spaces."""
    return display_text(value)[:length].ljust(length).encode("ascii")
