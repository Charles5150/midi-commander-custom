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
            f'<title>{title}</title>\n<defs>{arrow_heads(ACCENT, MUTED, GOOD, QUIET)}</defs>\n'
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


# --- Press types ---------------------------------------------------------------

PRESS_TYPES = {
    "en": {
        "title": "Short, long, double, two together: when each list goes out",
        "ms": "ms",
        "rows": [
            ("A button with a short press list only", "sends at once, as the switch goes down"),
            ("… and a long press list: a tap", "the short list goes out when you let go"),
            ("… and a long press list: held", "the long list goes out at Long_Press_ms, still held"),
            ("A button with a double press list", "a second press within Double_Press_ms"),
            ("Two switches of a combination", "the second within Combo_ms of the first"),
        ],
        "held": "switch held",
        "short": "short", "long": "long", "double": "double", "combo": "combo", "release": "release",
        "single": "or, no second press: short",
        "window_long": "Long_Press_ms 500", "window_double": "Double_Press_ms 300", "window_combo": "Combo_ms 80",
    },
    "es": {
        "title": "Corta, larga, doble, dos a la vez: cuándo sale cada lista",
        "ms": "ms",
        "rows": [
            ("Un botón solo con pulsación corta", "envía en el acto, al bajar el pulsador"),
            ("… y con lista larga: un toque", "la lista corta sale al soltar"),
            ("… y con lista larga: mantenido", "la lista larga sale en Long_Press_ms, aún pisado"),
            ("Un botón con lista de doble pulsación", "una segunda pisada dentro de Double_Press_ms"),
            ("Dos pulsadores de una combinación", "el segundo dentro de Combo_ms desde el primero"),
        ],
        "held": "pulsador pisado",
        "short": "corta", "long": "larga", "double": "doble", "combo": "combo", "release": "al soltar",
        "single": "o, sin segunda pisada: corta",
        "window_long": "Long_Press_ms 500", "window_double": "Double_Press_ms 300", "window_combo": "Combo_ms 80",
    },
}


def press_types(lang):
    t = PRESS_TYPES[lang]
    left, x0, px = 40, 400, 0.62          # label column, time zero, pixels per ms
    width = int(x0 + 1000 * px + 60)
    top, row_h = 120, 92

    def X(ms):
        return x0 + ms * px

    parts = [text(width / 2, 50, t["title"], 24, TEXT, "700")]
    # time axis
    ay = top - 26
    parts.append(f'<line x1="{X(0)}" y1="{ay}" x2="{X(1000)}" y2="{ay}" stroke="{EDGE}" stroke-width="2"/>')
    for ms in range(0, 1001, 100):
        parts.append(f'<line x1="{X(ms)}" y1="{ay - 5}" x2="{X(ms)}" y2="{ay + 5}" stroke="{EDGE}" stroke-width="2"/>')
        parts.append(f'<line x1="{X(ms)}" y1="{ay + 8}" x2="{X(ms)}" y2="{top + row_h * 5 - 20}" stroke="{EDGE}" stroke-opacity="0.35" stroke-width="1"/>')
        if ms % 200 == 0:
            parts.append(text(X(ms), ay - 12, f"{ms} {t['ms']}" if ms == 1000 else str(ms), 12, MUTED))

    def held(y, a, b, label=None):
        out = [f'<rect x="{X(a)}" y="{y - 9}" width="{(b - a) * px}" height="18" rx="9" fill="{ACCENT}" fill-opacity="0.85"/>']
        if label:
            out.append(text(X(a) + 10, y + 5, label, 11, BG, "700", "start"))
        return "\n".join(out)

    def fire(y, ms, label, colour=GOOD, above=True):
        ty = y - 22 if above else y + 32
        return "\n".join([
            f'<circle cx="{X(ms)}" cy="{y}" r="8" fill="{colour}" stroke="{BG}" stroke-width="3"/>',
            text(X(ms), ty, label, 13, colour, "700"),
        ])

    def window(y, a, b, label):
        return "\n".join([
            f'<rect x="{X(a)}" y="{y - 20}" width="{(b - a) * px}" height="40" rx="6" fill="{QUIET}" fill-opacity="0.10" '
            f'stroke="{QUIET}" stroke-opacity="0.6" stroke-dasharray="5 4"/>',
            text(X(a) + (b - a) * px / 2, y + 36, label, 11, QUIET, "600"),
        ])

    for i, (name, note) in enumerate(t["rows"]):
        y = top + i * row_h + 30
        if i % 2 == 0:
            parts.append(f'<rect x="16" y="{y - 40}" width="{width - 32}" height="{row_h}" rx="10" fill="#ffffff" fill-opacity="0.025"/>')
        parts.append(text(left, y - 4, name, 15, TEXT, "600", "start"))
        parts.append(text(left, y + 17, note, 13, MUTED, anchor="start"))
        if i == 0:
            parts.append(held(y, 0, 380, t["held"]))
            parts.append(fire(y, 0, t["short"]))
            parts.append(fire(y, 380, t["release"], MUTED))
        elif i == 1:
            parts.append(window(y, 0, 500, t["window_long"]))
            parts.append(held(y, 0, 260))
            parts.append(fire(y, 260, t["short"]))
        elif i == 2:
            parts.append(window(y, 0, 500, t["window_long"]))
            parts.append(held(y, 0, 900))
            parts.append(fire(y, 500, t["long"]))
            parts.append(fire(y, 900, t["release"], MUTED))
        elif i == 3:
            parts.append(held(y, 0, 140))
            parts.append(window(y, 140, 440, t["window_double"]))
            parts.append(held(y, 300, 400))
            parts.append(fire(y, 300, t["double"]))
            parts.append(text(X(440) + 14, y + 5, t["single"], 12, MUTED, anchor="start"))
        else:
            parts.append(window(y, 0, 80, t["window_combo"]))
            parts.append(f'<rect x="{X(0)}" y="{y - 12}" width="{600 * px}" height="9" rx="4.5" fill="{ACCENT}" fill-opacity="0.85"/>')
            parts.append(f'<rect x="{X(45)}" y="{y + 3}" width="{555 * px}" height="9" rx="4.5" fill="{ACCENT}" fill-opacity="0.85"/>')
            parts.append(text(X(600) + 10, y - 3, "3", 11, ACCENT, "700", "start"))
            parts.append(text(X(600) + 10, y + 12, "4", 11, ACCENT, "700", "start"))
            parts.append(fire(y, 45, t["combo"]))
    height = top + 5 * row_h + 10
    return svg(width, height, "\n".join(parts), t["title"])


# --- Setlist -------------------------------------------------------------------

SETLIST = {
    "en": {
        "title": "A setlist: Bank Up walks your songs, not the bank numbers",
        "plain": "Setlist_Mode N",
        "plain_note": "Bank Up / Down step through every bank in number order, wrapping round",
        "set": "Setlist_Mode Y",
        "set_note": "they step through the Setlist section, in its order, wrapping round",
        "foot": "A GoTo and a bank change from MIDI still reach any bank; a long press jumps Bank_Jump_Step entries of the list.",
        "bank": "bank",
    },
    "es": {
        "title": "Un setlist: Bank Up recorre tus canciones, no los números de banco",
        "plain": "Setlist_Mode N",
        "plain_note": "Bank Up / Down pasan por todos los bancos en orden de número, y dan la vuelta",
        "set": "Setlist_Mode Y",
        "set_note": "pasan por la sección Setlist, en su orden, y dan la vuelta",
        "foot": "Un GoTo y un cambio de banco por MIDI siguen llegando a cualquier banco; una pulsación larga salta Bank_Jump_Step puestos de la lista.",
        "bank": "banco",
    },
}

SETLIST_BANKS = {7: "INTR", 2: "BLUE", 9: "RIFF", 4: "SLOW", 11: "END"}
SETLIST_ORDER = [7, 2, 9, 4, 11]


def setlist(lang):
    t = SETLIST[lang]
    n, bw, gap, x0 = 12, 66, 12, 48
    width = x0 * 2 + n * bw + (n - 1) * gap

    def bx(i):
        return x0 + i * (bw + gap)

    parts = [text(width / 2, 50, t["title"], 24, TEXT, "700")]
    # without a setlist: every bank in turn
    y1 = 118
    parts.append(text(x0, y1 - 16, t["plain"], 15, TEXT, "700", "start"))
    parts.append(text(x0 + 140, y1 - 16, t["plain_note"], 13, MUTED, anchor="start"))
    for i in range(n):
        parts.append(f'<rect x="{bx(i)}" y="{y1}" width="{bw}" height="50" rx="8" fill="#232325" stroke="{EDGE}" stroke-width="1.5"/>')
        parts.append(text(bx(i) + bw / 2, y1 + 32, str(i), 20, MUTED, "700"))
        if i < n - 1:
            parts.append(arrow(bx(i) + bw - 10, y1 + 68, bx(i + 1) + 10, y1 + 68, MUTED))
    parts.append(text(bx(n - 1) + bw + 6, y1 + 31, "…31", 13, MUTED, anchor="start"))

    # with one: the songs in the list's order
    y2 = 290
    parts.append(text(x0, y2 - 40, t["set"], 15, TEXT, "700", "start"))
    parts.append(text(x0 + 140, y2 - 40, t["set_note"], 13, MUTED, anchor="start"))
    cw, cg = 150, (width - 2 * x0 - 5 * 150) / 4
    for k, bank in enumerate(SETLIST_ORDER):
        x = x0 + k * (cw + cg)
        parts.append(f'<rect x="{x}" y="{y2}" width="{cw}" height="74" rx="10" fill="#2c2c2e" stroke="{ACCENT}" stroke-width="2"/>')
        parts.append(f'<circle cx="{x + 22}" cy="{y2 + 22}" r="12" fill="{ACCENT}"/>')
        parts.append(text(x + 22, y2 + 27, str(k + 1), 13, BG, "700"))
        parts.append(text(x + cw / 2 + 12, y2 + 32, SETLIST_BANKS[bank], 20, TEXT, "700"))
        parts.append(text(x + cw / 2, y2 + 58, f"{t['bank']} {bank}", 13, MUTED))
        if k < len(SETLIST_ORDER) - 1:
            parts.append(arrow(x + cw + 8, y2 + 37, x + cw + cg - 8, y2 + 37))
    # round again
    xa = x0 + 4 * (cw + cg) + cw / 2
    xb = x0 + cw / 2
    yb = y2 + 74
    parts.append(f'<path d="M{xa},{yb + 4} C{xa},{yb + 56} {xb},{yb + 56} {xb},{yb + 10}" fill="none" stroke="{ACCENT}" '
                 f'stroke-width="2.5" stroke-dasharray="7 6" marker-end="url(#head-{ACCENT[1:]})"/>')
    fy = yb + 90
    parts.append(text(width / 2, fy, t["foot"], 13, MUTED))
    return svg(width, fy + 30, "\n".join(parts), t["title"])


# --- MIDI in and out -------------------------------------------------------------

MIDI_ROUTES = {
    "en": {
        "title": "Where MIDI goes in and out",
        "host": "Computer", "host2": "DAW, MainStage, a Kemper",
        "usb": "USB",
        "gear": "Your gear", "gear2": "amp, pedals, synth",
        "din": "MIDI OUT (DIN)",
        "pedal": "The pedal",
        "sources": "Switches · expression pedals · tempo, LFO, sequencer",
        "out_usb": "MIDI, and keyboard",
        "out_usb2": "and media keys",
        "out_din": "the same MIDI",
        "in_title": "What arrives over USB",
        "in": [
            ("Bank_Change_Mode", "a PC or CC selects a bank"),
            ("LED_Feedback", "a CC or note lights the toggles that send it"),
            ("Remote_Mode", "ten CCs or notes press the switches"),
            ("Clock_Follow", "the host's clock sets the tempo"),
            ("SysEx", "display text, the Kemper, configuration"),
        ],
        "thru": "USB_MIDI_Thru · RealTime_Passthrough: the rest, on to the DIN output",
        "no_in": "The pedal has no MIDI IN socket: only USB comes in.",
    },
    "es": {
        "title": "Por dónde entra y sale el MIDI",
        "host": "Ordenador", "host2": "DAW, MainStage, un Kemper",
        "usb": "USB",
        "gear": "Tu equipo", "gear2": "ampli, pedales, sinte",
        "din": "MIDI OUT (DIN)",
        "pedal": "La pedalera",
        "sources": "Pulsadores · pedales de expresión · tempo, LFO, secuenciador",
        "out_usb": "MIDI, teclado",
        "out_usb2": "y teclas multimedia",
        "out_din": "el mismo MIDI",
        "in_title": "Lo que llega por USB",
        "in": [
            ("Bank_Change_Mode", "un PC o CC elige banco"),
            ("LED_Feedback", "un CC o nota enciende sus toggles"),
            ("Remote_Mode", "diez CC o notas pisan los pulsadores"),
            ("Clock_Follow", "el reloj del ordenador fija el tempo"),
            ("SysEx", "texto en pantalla, el Kemper, configuración"),
        ],
        "thru": "USB_MIDI_Thru · RealTime_Passthrough: el resto, hacia la salida DIN",
        "no_in": "La pedalera no tiene toma MIDI IN: solo entra lo que llega por USB.",
    },
}


def box(x, y, w, h, title, sub=None, colour=EDGE, fill="#232325"):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{colour}" stroke-width="2"/>',
           text(x + w / 2, y + (h / 2 if not sub else h / 2 - 6), title, 18, TEXT, "700")]
    if sub:
        out.append(text(x + w / 2, y + h / 2 + 18, sub, 12, MUTED))
    return "\n".join(out)


def midi_routes(lang):
    t = MIDI_ROUTES[lang]
    width = 1220
    hx, hw = 36, 220                 # computer
    px, pw = 430, 470                # pedal
    gx, gw = 1040, 150               # gear
    top = 100
    parts = [text(width / 2, 50, t["title"], 24, TEXT, "700")]

    # the pedal and what is in it
    ph = 470
    parts.append(f'<rect x="{px}" y="{top}" width="{pw}" height="{ph}" rx="16" fill="#202022" stroke="{ACCENT}" stroke-width="2"/>')
    parts.append(text(px + pw / 2, top + 30, t["pedal"], 18, ACCENT, "700"))
    sy = top + 52
    parts.append(f'<rect x="{px + 20}" y="{sy}" width="{pw - 40}" height="56" rx="10" fill="#2c2c2e" stroke="{EDGE}"/>')
    parts.append(text(px + pw / 2, sy + 33, t["sources"], 13, TEXT, "600"))
    iy = sy + 100
    parts.append(text(px + 24, iy, t["in_title"], 14, QUIET, "700", "start"))
    for k, (name, what) in enumerate(t["in"]):
        ry = iy + 16 + k * 46
        parts.append(f'<rect x="{px + 20}" y="{ry}" width="{pw - 40}" height="38" rx="8" fill="{QUIET}" fill-opacity="0.08" stroke="{QUIET}" stroke-opacity="0.5"/>')
        parts.append(text(px + 34, ry + 24, name, 13, QUIET, "700", "start"))
        parts.append(text(px + 184, ry + 24, what, 13, TEXT, anchor="start"))

    # computer and gear
    cy_out = sy + 28                  # the level messages go out at
    hy = top + 40
    parts.append(box(hx, hy, hw, 110, t["host"], t["host2"]))
    parts.append(box(gx, hy, gw, 110, t["gear"], t["gear2"]))

    # out: to USB and to DIN
    parts.append(arrow(px - 6, cy_out + 30, hx + hw + 10, cy_out + 30, GOOD))
    parts.append(text((px + hx + hw) / 2, cy_out + 4, t["out_usb"], 12, GOOD, "600"))
    parts.append(text((px + hx + hw) / 2, cy_out + 20, t["out_usb2"], 12, GOOD, "600"))
    parts.append(arrow(px + pw + 6, cy_out + 30, gx - 10, cy_out + 30, GOOD))
    parts.append(text((px + pw + gx) / 2, cy_out + 20, t["out_din"], 12, GOOD, "600"))
    parts.append(text((px + pw + gx) / 2, cy_out + 52, t["din"], 11, MUTED, "600"))
    parts.append(text((px + hx + hw) / 2, cy_out + 52, t["usb"], 11, MUTED, "600"))

    # in: from USB into the list
    in_y = iy + 16 + 2 * 46 + 19
    host_bottom = hy + 110
    parts.append(f'<path d="M{hx + hw / 2},{host_bottom + 6} L{hx + hw / 2},{in_y} L{px - 10},{in_y}" fill="none" stroke="{QUIET}" '
                 f'stroke-width="3" marker-end="url(#head-{QUIET[1:]})"/>')
    parts.append(text(hx + hw / 2 + 12, (host_bottom + in_y) / 2, t["usb"], 12, QUIET, "700", "start"))

    # thru: under the list, on to the DIN output
    ty = iy + 16 + 5 * 46 + 22
    parts.append(f'<path d="M{hx + hw / 2},{in_y} L{hx + hw / 2},{ty} L{gx + gw / 2},{ty} L{gx + gw / 2},{hy + 118}" fill="none" '
                 f'stroke="{MUTED}" stroke-width="2.5" stroke-dasharray="7 6" marker-end="url(#head-{MUTED[1:]})"/>')
    parts.append(f'<rect x="{px + 20}" y="{ty - 16}" width="{pw - 40}" height="32" rx="8" fill="#202022"/>')
    parts.append(text(px + pw / 2, ty + 5, t["thru"], 12, MUTED, "600"))

    fy = top + ph + 36
    parts.append(text(width / 2, fy, t["no_in"], 13, MUTED))
    return svg(width, fy + 28, "\n".join(parts), t["title"])


# --- A command list ---------------------------------------------------------------

COMMAND_LIST = {
    "en": {
        "title": "One press, ten commands: a list runs top to bottom",
        "slot": "Slot", "command": "Command", "when": "When it goes out after the press",
        "ms": "ms",
        "rows": [
            ("PC", "Program 12", None),
            ("Wait", "200 ms", "holds the rest of the list back"),
            ("CC", "20 = 127, delay on", None),
            ("Ramp", "2000 ms", "turns the CC below into a ramp"),
            ("CC", "7: 0 → 127, a swell", None),
            ("If", "Button 4 on", "the command below only if it holds"),
            ("CC", "21 = 127, a boost", None),
            ("Macro", "bank 30, D, short", "runs that list here, in place"),
        ],
        "skipped": "only if 4 is on",
        "macro": "its commands",
        "foot": "Nothing waits for the ramp: the pedal carries on, and its switches keep working while a list pauses.",
    },
    "es": {
        "title": "Una pulsación, diez comandos: la lista se ejecuta de arriba abajo",
        "slot": "Casilla", "command": "Comando", "when": "Cuándo sale tras la pulsación",
        "ms": "ms",
        "rows": [
            ("PC", "Programa 12", None),
            ("Wait", "200 ms", "retiene el resto de la lista"),
            ("CC", "20 = 127, delay on", None),
            ("Ramp", "2000 ms", "convierte el CC de abajo en rampa"),
            ("CC", "7: 0 → 127, un swell", None),
            ("If", "Botón 4 on", "el comando de abajo solo si se cumple"),
            ("CC", "21 = 127, un boost", None),
            ("Macro", "banco 30, D, corta", "ejecuta esa lista aquí mismo"),
        ],
        "skipped": "solo si 4 está on",
        "macro": "sus comandos",
        "foot": "Nada espera a la rampa: la pedalera sigue, y sus pulsadores funcionan mientras una lista está en pausa.",
    },
}


def command_list(lang):
    t = COMMAND_LIST[lang]
    x0, row_h, top = 40, 50, 128
    tx0, px = 700, 0.2                 # timeline: zero, pixels per ms
    width = int(tx0 + 2400 * px + 60)

    def X(ms):
        return tx0 + ms * px

    parts = [text(width / 2, 50, t["title"], 24, TEXT, "700")]
    parts.append(text(x0, top - 22, t["slot"], 12, MUTED, "700", "start"))
    parts.append(text(x0 + 60, top - 22, t["command"], 12, MUTED, "700", "start"))
    parts.append(text(tx0, top - 22, t["when"], 12, MUTED, "700", "start"))
    # time axis at the bottom
    ay = top + len(t["rows"]) * row_h + 10
    parts.append(f'<line x1="{X(0)}" y1="{ay}" x2="{X(2400)}" y2="{ay}" stroke="{EDGE}" stroke-width="2"/>')
    for ms in range(0, 2401, 400):
        parts.append(f'<line x1="{X(ms)}" y1="{top - 8}" x2="{X(ms)}" y2="{ay}" stroke="{EDGE}" stroke-opacity="0.35"/>')
        parts.append(text(X(ms), ay + 20, f"{ms} {t['ms']}" if ms == 2400 else str(ms), 12, MUTED))

    kinds = {"PC": GOOD, "CC": GOOD, "Wait": QUIET, "Ramp": QUIET, "If": QUIET, "Macro": ACCENT}
    for i, (kind, what, note) in enumerate(t["rows"]):
        y = top + i * row_h
        cy = y + row_h / 2 - 4
        colour = kinds[kind]
        parts.append(f'<rect x="{x0 - 8}" y="{y}" width="{tx0 - x0 - 16}" height="{row_h - 8}" rx="8" fill="#ffffff" fill-opacity="0.03"/>')
        parts.append(text(x0 + 12, cy + 5, "ABCDEFGH"[i], 14, MUTED, "700"))
        parts.append(f'<rect x="{x0 + 50}" y="{cy - 13}" width="64" height="26" rx="13" fill="{colour}" fill-opacity="0.16" stroke="{colour}" stroke-width="1.5"/>')
        parts.append(text(x0 + 82, cy + 5, kind, 13, colour, "700"))
        parts.append(text(x0 + 128, cy + 5, what, 14, TEXT, "600", "start"))
        if note:
            parts.append(text(x0 + 300, cy + 5, note, 12, MUTED, anchor="start"))
        # when it goes out
        if kind == "PC":
            parts.append(f'<circle cx="{X(0)}" cy="{cy}" r="8" fill="{GOOD}" stroke="{BG}" stroke-width="3"/>')
        elif kind == "Wait":
            parts.append(f'<rect x="{X(0)}" y="{cy - 5}" width="{200 * px}" height="10" rx="5" fill="{QUIET}" fill-opacity="0.5"/>')
        elif kind == "CC" and i == 2:
            parts.append(f'<circle cx="{X(200)}" cy="{cy}" r="8" fill="{GOOD}" stroke="{BG}" stroke-width="3"/>')
        elif kind == "CC" and i == 4:
            parts.append(f'<path d="M{X(200)},{cy + 10} L{X(2200)},{cy - 12} L{X(2200)},{cy + 10} z" fill="{GOOD}" fill-opacity="0.35" stroke="{GOOD}" stroke-width="2"/>')
        elif kind == "CC" and i == 6:
            parts.append(f'<circle cx="{X(200)}" cy="{cy}" r="8" fill="none" stroke="{GOOD}" stroke-width="2.5" stroke-dasharray="3 3"/>')
            parts.append(text(X(200) + 16, cy + 5, t["skipped"], 12, MUTED, anchor="start"))
        elif kind == "Macro":
            for k, ms in enumerate((200, 200, 200)):
                parts.append(f'<circle cx="{X(ms) + k * 16}" cy="{cy}" r="6" fill="{ACCENT}" stroke="{BG}" stroke-width="2"/>')
            parts.append(text(X(200) + 50, cy + 5, t["macro"], 12, ACCENT, anchor="start"))
    # the modifiers point at the command below
    for i, (kind, _, _) in enumerate(t["rows"]):
        if kind in ("Ramp", "If"):
            y1 = top + i * row_h + row_h / 2 - 4
            y2 = y1 + row_h
            parts.append(f'<path d="M{x0 + 50},{y1} C{x0 + 26},{y1} {x0 + 26},{y2} {x0 + 46},{y2}" fill="none" stroke="{QUIET}" '
                         f'stroke-width="2" marker-end="url(#head-{QUIET[1:]})"/>')
    fy = ay + 58
    parts.append(text(width / 2, fy, t["foot"], 13, MUTED))
    return svg(width, fy + 28, "\n".join(parts), t["title"])


PICTURES = {"bank-preview": bank_preview, "press-types": press_types, "setlist": setlist, "midi-routes": midi_routes,
            "command-list": command_list}


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
