#! env python3
"""Draws the manual's pictures as SVG, in English and in Spanish.

The screens in them are the pedal's own, read over SysEx GET_SCREEN and kept in
docs/manual/screens/ as one line of 128 zeros and ones per pixel row, so the
pictures can be drawn again without a pedal:

    python3 docs/manual/pictures.py

writes docs/manual/images/<name>-en.svg and <name>-es.svg.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SCREENS = os.path.join(HERE, "screens")
IMAGES = os.path.join(HERE, "images")

# Colours, the configurator's own
BG = "#1c1c1e"
EDGE = "#3a3a3c"
TEXT = "#f2f2f7"
MUTED = "#9a9aa0"
ACCENT = "#ff9f0a"      # what the player does
GOOD = "#30d158"        # what goes out
QUIET = "#64d2ff"       # what does not
PIXEL = "#e8f4ff"
FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""


def load_screen(name):
    with open(os.path.join(SCREENS, name + ".txt")) as f:
        return [line.strip() for line in f if line.strip()]


def oled(rows, x, y, scale):
    """The screen in its window: each run of lit pixels in a row is one rectangle."""
    w, h = len(rows[0]) * scale, len(rows) * scale
    out = [f'<rect x="{x - 8}" y="{y - 8}" width="{w + 16}" height="{h + 16}" rx="8" fill="#0b0b0c" stroke="#48484a" stroke-width="2"/>',
           f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#000"/>',
           f'<g fill="{PIXEL}">']
    for r, line in enumerate(rows):
        c = 0
        while c < len(line):
            if line[c] == "1":
                start = c
                while c < len(line) and line[c] == "1":
                    c += 1
                out.append(f'<rect x="{x + start * scale}" y="{y + r * scale}" width="{(c - start) * scale}" height="{scale}"/>')
            else:
                c += 1
    out.append("</g>")
    return "\n".join(out)


def footswitch(cx, cy, r=22, lit=False):
    return "\n".join([
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#2c2c2e" stroke="#000" stroke-opacity="0.4" stroke-width="2"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{r * 0.78:.1f}" fill="#7c7c80"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{r * 0.56:.1f}" fill="{ACCENT if lit else "#d1d1d6"}"/>',
    ])


def text(x, y, s, size=16, fill=TEXT, weight="normal", anchor="middle"):
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    return f'<text x="{x}" y="{y}" {FONT} font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{s}</text>'


def badge(cx, y, s, colour):
    w = 11 + len(s) * 8.2
    return "\n".join([
        f'<rect x="{cx - w / 2:.1f}" y="{y}" width="{w:.1f}" height="26" rx="13" fill="{colour}" fill-opacity="0.16" stroke="{colour}" stroke-width="1.5"/>',
        text(cx, y + 18, s, 14, colour, "600"),
    ])


def arrow(x1, y1, x2, y2, colour=ACCENT, dashed=False):
    dash = ' stroke-dasharray="7 6"' if dashed else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{colour}" stroke-width="3"{dash} marker-end="url(#head-{colour[1:]})"/>')


def arrow_heads(*colours):
    return "\n".join(
        f'<marker id="head-{c[1:]}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>' for c in colours)


def svg(width, height, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img">\n'
            f'<title>{title}</title>\n<defs>{arrow_heads(ACCENT, MUTED)}</defs>\n'
            f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="18" fill="{BG}" stroke="{EDGE}" stroke-width="2"/>\n'
            f'{body}\n</svg>\n')


# --- Bank preview --------------------------------------------------------------

BANK_PREVIEW = {
    "en": {
        "title": "Bank preview: look first, then go",
        "step1": "Playing song 1",
        "step1b": "bank 12",
        "step2": "Bank Up shows the next song",
        "step2b": "its name inverted",
        "step3": "Any of the eight buttons goes there",
        "step3b": "the press does nothing else",
        "press_up": "BANK ▲",
        "press_any": "1–4, A–D",
        "quiet": "nothing sent",
        "sent": "its patch goes out",
        "back": "no button for Bank_Preview seconds, or back to where you are: nothing changed",
    },
    "es": {
        "title": "Vista previa de banco: primero mira, luego ve",
        "step1": "Tocando la canción 1",
        "step1b": "banco 12",
        "step2": "Bank Up enseña la siguiente",
        "step2b": "su nombre invertido",
        "step3": "Cualquiera de los ocho botones va",
        "step3b": "esa pulsación no hace nada más",
        "press_up": "BANK ▲",
        "press_any": "1–4, A–D",
        "quiet": "no se envía nada",
        "sent": "sale su patch",
        "back": "sin tocar un botón en Bank_Preview segundos, o volviendo al banco actual: nada ha cambiado",
    },
}


def bank_preview(lang):
    t = BANK_PREVIEW[lang]
    scale, sw = 2, 256
    y = 110
    xs = [48, 424, 800]
    width = xs[2] + sw + 48
    parts = [text(width / 2, 50, t["title"], 24, TEXT, "700")]
    for x, name in zip(xs, ("home", "preview", "confirmed")):
        parts.append(oled(load_screen("bank-preview-" + name), x, y, scale))
    # steps under the screens
    for i, (x, a, b) in enumerate(zip(xs, (t["step1"], t["step2"], t["step3"]), (t["step1b"], t["step2b"], t["step3b"]))):
        cx = x + sw / 2
        parts.append(f'<circle cx="{x + 7}" cy="{y - 36}" r="15" fill="{ACCENT}"/>')
        parts.append(text(x + 7, y - 30.5, str(i + 1), 16, BG, "700"))
        parts.append(text(cx, y + 128 + 44, a, 16, TEXT, "600"))
        parts.append(text(cx, y + 128 + 66, b, 14, MUTED))
    # what goes out
    parts.append(badge(xs[1] + sw / 2, y + 128 + 84, t["quiet"], QUIET))
    parts.append(badge(xs[2] + sw / 2, y + 128 + 84, t["sent"], GOOD))
    # the presses between them
    for x, label in ((xs[0] + sw + 8, t["press_up"]), (xs[1] + sw + 8, t["press_any"])):
        mid = (x + x + 104) / 2 + 2
        parts.append(footswitch(mid, y + 34, 24, lit=True))
        parts.append(text(mid, y + 82, label, 13, ACCENT, "700"))
        parts.append(arrow(mid - 30, y + 104, mid + 28, y + 104))
    # and back
    by = y + 128 + 142
    x1, x2 = xs[1] + sw / 2, xs[0] + sw / 2
    parts.append(f'<path d="M{x1},{by - 20} C{x1},{by + 10} {x2},{by + 10} {x2},{by - 16}" fill="none" stroke="{MUTED}" '
                 f'stroke-width="2.5" stroke-dasharray="7 6" marker-end="url(#head-{MUTED[1:]})"/>')
    parts.append(text((x1 + x2) / 2, by + 26, t["back"], 13, MUTED))
    return svg(width, by + 50, "\n".join(parts), t["title"])


PICTURES = {"bank-preview": bank_preview}


def main():
    os.makedirs(IMAGES, exist_ok=True)
    for name, draw in PICTURES.items():
        for lang in ("en", "es"):
            path = os.path.join(IMAGES, f"{name}-{lang}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(draw(lang))
            print(path)


if __name__ == "__main__":
    main()
