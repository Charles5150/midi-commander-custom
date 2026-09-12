"""Pack a parsed configuration CSV into the flash image the firmware expects.

Layout (must match firmware/Core/Src/flash_midi_settings.c):

    0..15    global settings
    16..31   config name
    32..127  bank strings
    128..    8 banks x 8 buttons x 10 commands x 4 bytes
    2688..   button LED mode table, one byte per button (bank * 8 + button)
    2752..   button labels, 4 ASCII chars per button, space padded
    3008..   long press commands, same layout as the main command area
    5568..   expression pedal calibration, 16 bytes per pedal
"""

import lib.cmdBinaryPacker as cbp
import lib.settingsBinaryPacker as sbp

NUM_BANKS = 8
NUM_BUTTONS = 8
BUTTON_IDS = ["1", "2", "3", "4", "A", "B", "C", "D"]
LABEL_LEN = 4
LONG_PRESS_SECTION = "LongPress_Settings"
EXPRESSION_SECTION = "Expression_Settings"
EXP_STRIDE = 16
EXP_CURVES = {"LINEAR": 0, "LOG": 1, "EXP": 2}
EXP_DEFAULTS = {"Min_ADC": "80", "Max_ADC": "3900", "Curve": "Linear", "Invert": "N", "Channel": "Global"}


def _key(bank, button) -> tuple:
    b = str(bank).strip()
    if b.endswith(".0"):
        b = b[:-2]
    return (b, str(button).strip().upper())


def empty_long_press_settings():
    """A LongPress_Settings frame with one blank row per bank/button."""
    import pandas as pd

    from lib.binaryUnpacker import CMD_FIELDS, SLOT_NAMES

    rows = []
    for bank in range(NUM_BANKS):
        for btn in BUTTON_IDS:
            row = {"Bank_Number": str(bank), "Button_Identifier": btn}
            for slot in SLOT_NAMES:
                for f in CMD_FIELDS:
                    row[f"{slot}_{f}"] = "N" if f.startswith("Toggle") else ""
                row[f"{slot}_KeyMode_(Key)"] = ""
            rows.append(row)
    return pd.DataFrame(rows)


def empty_expression_settings():
    """An Expression_Settings frame with the default calibration for both pedals."""
    import pandas as pd

    return pd.DataFrame(
        [{"Pedal": str(i + 1), **EXP_DEFAULTS} for i in range(2)]
    )


def _to_int(value, default):
    try:
        return int(float(str(value).strip()))
    except ValueError:
        return default


def pack_expression_settings(df) -> bytes:
    """Two 16 byte records: min/max ADC (LE), curve, invert, channel, zeros."""
    rows = {}
    if df is not None:
        for _, row in df.iterrows():
            rows[str(row.get("Pedal", "")).strip().rstrip(".0") or "?"] = row
    out = b""
    for i in range(2):
        row = rows.get(str(i + 1))
        get = (lambda k: row.get(k, EXP_DEFAULTS[k])) if row is not None else (lambda k: EXP_DEFAULTS[k])
        lo = max(0, min(4095, _to_int(get("Min_ADC"), 80)))
        hi = max(0, min(4095, _to_int(get("Max_ADC"), 3900)))
        curve = EXP_CURVES.get(str(get("Curve")).strip().upper()[:6].rstrip("ARITHM"), None)
        if curve is None:
            c = str(get("Curve")).strip().upper()
            curve = 1 if c.startswith("LOG") else 2 if c.startswith("EXP") else 0
        invert = 1 if str(get("Invert")).strip().upper().startswith("Y") else 0
        ch_text = str(get("Channel")).strip()
        channel = 0 if ch_text.upper().startswith("G") or ch_text == "" else max(0, min(16, _to_int(ch_text, 0)))
        out += bytes([lo & 0xFF, lo >> 8, hi & 0xFF, hi >> 8, curve, invert, channel]) + bytes(EXP_STRIDE - 7)
    return out


def pack_label(value) -> bytes:
    """Label cell -> LABEL_LEN ASCII bytes, space padded, non-ASCII as '?'."""
    text = "" if value is None else str(value)
    if text.strip().lower() == "nan":
        text = ""
    text = text.strip()[:LABEL_LEN]
    return text.encode("ascii", errors="replace").ljust(LABEL_LEN, b" ")


def pack_config(sections: dict) -> bytes:
    """``sections`` is the dict returned by ``configCsv.read_config_csv``."""
    df_global = sections["Global_Settings"].set_index("Label")
    df_banks = sections["Bank_Naming"].set_index("Bank_Number")
    df_buttons = sections["Button_Settings"]

    out = []
    out += sbp.pack_global_settings(df_global)
    out += sbp.pack_bank_strings(df_banks)

    if len(df_buttons) != NUM_BANKS * NUM_BUTTONS:
        raise ValueError(
            f"Button_Settings has {len(df_buttons)} rows, expected "
            f"{NUM_BANKS * NUM_BUTTONS} (8 banks x 8 buttons)"
        )

    light_modes = []
    labels = b""
    for _, row in df_buttons.iterrows():
        out += cbp.pack_row(row)
        light_modes.append(row.get("Light_Mode", "Normal"))
        labels += pack_label(row.get("Label", ""))
    out += cbp.pack_button_led_modes(light_modes)
    out += list(labels)

    # Long press command sets: rows are optional and may come in any order,
    # buttons without a row pack as "no command".
    long_rows = {}
    if LONG_PRESS_SECTION in sections:
        for _, row in sections[LONG_PRESS_SECTION].iterrows():
            long_rows[_key(row["Bank_Number"], row["Button_Identifier"])] = row
    for bank in range(NUM_BANKS):
        for btn in BUTTON_IDS:
            row = long_rows.get((str(bank), btn))
            if row is None:
                out += [0] * (cbp.MIDI_NUM_COMMANDS_PER_SWITCH * 4)
            else:
                out += cbp.pack_row(row)

    out += list(pack_expression_settings(sections.get(EXPRESSION_SECTION)))

    return bytes(out)
