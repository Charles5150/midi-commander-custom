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
    ....     commands sent when each bank is entered, one button's list per bank
"""

import lib.cmdBinaryPacker as cbp
import lib.settingsBinaryPacker as sbp

NUM_BANKS = 32
NUM_BUTTONS = 8
BUTTON_IDS = ["1", "2", "3", "4", "A", "B", "C", "D"]
LABEL_LEN = 4
LONG_PRESS_SECTION = "LongPress_Settings"
DOUBLE_PRESS_SECTION = "DoublePress_Settings"
FLASH_PAGE_SIZE = 2048
SLOT_PAGES = 12
DOUBLE_PRESS_OFFSET = SLOT_PAGES * FLASH_PAGE_SIZE
EXPRESSION_SECTION = "Expression_Settings"
BANK_ENTER_SECTION = "BankEnter_Settings"
SYSEX_SECTION = "SysEx_Strings"
BANK_SWITCH_SECTION = "BankSwitch_Settings"
SETLIST_SECTION = "Setlist"
BANK_EXPRESSION_SECTION = "BankExpression_Settings"
BANK_EXP_COLUMNS = ["Bank_Number", "Exp1_CC", "Exp1_Channel", "Exp1_Min", "Exp1_Max",
                    "Exp2_CC", "Exp2_Channel", "Exp2_Min", "Exp2_Max"]
BANK_EXP_CC_OFF = 0x80
SETLIST_MAX = 32
BANK_SWITCH_LISTS = [("Down", "Short"), ("Down", "Long"), ("Up", "Short"), ("Up", "Long")]
SYSEX_STRING_COUNT = 16
SYSEX_STRING_MAX = 23
SYSEX_STRING_STRIDE = SYSEX_STRING_MAX + 1
EXP_STRIDE = 16
EXP_CURVES = {"LINEAR": 0, "LOG": 1, "EXP": 2}
EXP_DEFAULTS = {
    "Min_ADC": "80", "Max_ADC": "3900", "Curve": "Linear", "Invert": "N",
    "Channel": "Global", "Toe_Button": "None", "Heel_Button": "None",
    "Toe_Level": "120", "Heel_Level": "7", "Out_Min": "0", "Out_Max": "127",
    "Auto_Button": "None", "Auto_Off_ms": "500",
}
EXP_BUTTON_IDS = ["1", "2", "3", "4", "A", "B", "C", "D"]


def _key(bank, button) -> tuple:
    b = str(bank).strip()
    if b.endswith(".0"):
        b = b[:-2]
    return (b, str(button).strip().upper())


def empty_long_press_settings(num_banks=NUM_BANKS):
    """A LongPress_Settings frame with one blank row per bank/button."""
    import pandas as pd

    from lib.binaryUnpacker import CMD_FIELDS, SLOT_NAMES

    rows = []
    for bank in range(num_banks):
        for btn in BUTTON_IDS:
            row = {"Bank_Number": str(bank), "Button_Identifier": btn}
            for slot in SLOT_NAMES:
                for f in CMD_FIELDS:
                    row[f"{slot}_{f}"] = "N" if f.startswith("Toggle") else ""
                row[f"{slot}_KeyMode_(Key)"] = ""
            rows.append(row)
    return pd.DataFrame(rows)


def parse_sysex_bytes(text) -> bytes:
    """Parse "F0 41 10 42 F7" into the 7-bit data bytes to store.

    Bytes are hexadecimal, the convention every device manual uses; an
    optional 0x prefix is accepted. A leading F0 and trailing F7 are stripped
    because they are added when sending. Everything else must be 0x00..0x7F;
    anything invalid yields an empty string rather than a wrong message.
    """
    if text is None:
        return b""
    s = str(text).strip()
    if s.lower() in ("", "nan"):
        return b""
    out = []
    for token in s.replace(",", " ").split():
        t = token.lower()
        if t.startswith("0x"):
            t = t[2:]
        try:
            v = int(t, 16)
        except ValueError:
            return b""
        if v > 0xFF:
            return b""
        out.append(v)
    while out and out[0] == 0xF0:
        out.pop(0)
    while out and out[-1] == 0xF7:
        out.pop()
    if any(v > 0x7F for v in out):
        return b""
    return bytes(out[:SYSEX_STRING_MAX])


def empty_bank_switch_settings():
    """A BankSwitch_Settings frame with one blank row per switch and press."""
    import pandas as pd

    from lib.binaryUnpacker import CMD_FIELDS, SLOT_NAMES

    rows = []
    for switch, press in BANK_SWITCH_LISTS:
        row = {"Switch": switch, "Press": press}
        for slot in SLOT_NAMES:
            for f in CMD_FIELDS:
                row[f"{slot}_{f}"] = "N" if f.startswith("Toggle") else ""
            row[f"{slot}_KeyMode_(Key)"] = ""
        rows.append(row)
    return pd.DataFrame(rows)


def empty_setlist():
    """A Setlist frame with no entries."""
    import pandas as pd

    return pd.DataFrame(columns=["Position", "Bank_Number"])


def pack_setlist(df):
    """Up to SETLIST_MAX bank numbers ordered by Position, padded with 0xFF.

    Rows may be in any order and may skip positions; invalid bank numbers are
    dropped rather than stored, since the firmware stops at the first one.
    """
    entries = []
    if df is not None:
        for _, row in df.iterrows():
            try:
                pos = float(str(row.get("Position", "")).strip())
                bank = int(float(str(row.get("Bank_Number", "")).strip()))
            except ValueError:
                continue
            if 0 <= bank < NUM_BANKS:
                entries.append((pos, bank))
    banks = [b for _, b in sorted(entries, key=lambda e: e[0])][:SETLIST_MAX]
    return bytes(banks + [0xFF] * (SETLIST_MAX - len(banks)))


def empty_sysex_strings():
    """An empty SysEx string table."""
    import pandas as pd

    return pd.DataFrame([{"Index": str(i), "Bytes": ""} for i in range(SYSEX_STRING_COUNT)])


def pack_sysex_strings(df) -> bytes:
    rows = {}
    if df is not None:
        for _, row in df.iterrows():
            key = str(row.get("Index", "")).strip()
            if key.endswith(".0"):
                key = key[:-2]
            rows[key] = row
    out = b""
    for i in range(SYSEX_STRING_COUNT):
        row = rows.get(str(i))
        payload = parse_sysex_bytes(row.get("Bytes")) if row is not None else b""
        out += bytes([len(payload)]) + payload.ljust(SYSEX_STRING_MAX, b"\x00")
    return out


def empty_bank_enter_settings(num_banks=NUM_BANKS):
    """A BankEnter_Settings frame with one blank row per bank."""
    import pandas as pd

    from lib.binaryUnpacker import CMD_FIELDS, SLOT_NAMES

    rows = []
    for bank in range(num_banks):
        row = {"Bank_Number": str(bank)}
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
    """Two 16 byte records: min/max ADC (LE), curve, invert, channel, toe and
    heel buttons and levels, output range, auto-engage button and off delay,
    zeros."""
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

        # Switch behaviour: a button per direction (0xFF when unused) and levels
        def button(key):
            text = str(get(key)).strip().upper()
            if text in ("", "NONE", "NAN", "OFF", "-"):
                return 0xFF
            return EXP_BUTTON_IDS.index(text) if text in EXP_BUTTON_IDS else 0xFF

        toe_btn, heel_btn = button("Toe_Button"), button("Heel_Button")
        toe_level = max(1, min(127, _to_int(get("Toe_Level"), 120)))
        heel_level = max(0, min(127, _to_int(get("Heel_Level"), 7)))
        # Output range; the firmware reads 0 to 0 as the full range, as older
        # tools wrote zeros there
        out_min = max(0, min(127, _to_int(get("Out_Min"), 0)))
        out_max = max(0, min(127, _to_int(get("Out_Max"), 127)))
        # Auto-engage: the button + 1, so the zeros older tools wrote mean none,
        # and the rest at the heel before it goes off, in 10 ms steps (0xFF is
        # erased flash)
        auto_btn = button("Auto_Button")
        auto_btn = 0 if auto_btn == 0xFF else auto_btn + 1
        auto_off = max(1, min(254, round(_to_int(get("Auto_Off_ms"), 500) / 10)))

        out += bytes([lo & 0xFF, lo >> 8, hi & 0xFF, hi >> 8, curve, invert, channel,
                      toe_btn, heel_btn, toe_level, heel_level,
                      out_min, out_max, auto_btn, auto_off]) + bytes(EXP_STRIDE - 15)
    return out


def pack_label(value) -> bytes:
    """Label cell -> LABEL_LEN ASCII bytes, space padded, non-ASCII as '?'."""
    text = "" if value is None else str(value)
    if text.strip().lower() == "nan":
        text = ""
    text = text.strip()[:LABEL_LEN]
    return text.encode("ascii", errors="replace").ljust(LABEL_LEN, b" ")


def empty_bank_expression_settings(num_banks=NUM_BANKS):
    """A BankExpression_Settings frame: every bank keeps the pedals' own settings."""
    import pandas as pd

    rows = [{"Bank_Number": str(b), **{c: "" for c in BANK_EXP_COLUMNS[1:]}}
            for b in range(num_banks)]
    return pd.DataFrame(rows, columns=BANK_EXP_COLUMNS)


def _cell(value) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in ("nan", "none", "default") else text


def bank_exp_cc_byte(value) -> int:
    """CSV cell -> stored byte: empty/Default 0xFF, Off 0x80, otherwise a CC 0-127."""
    text = _cell(value)
    if text == "":
        return 0xFF
    if text.lower() == "off":
        return BANK_EXP_CC_OFF
    try:
        return max(0, min(127, int(float(text))))
    except ValueError:
        return 0xFF


def bank_exp_channel_byte(value) -> int:
    """CSV cell -> stored byte: empty/Default 0xFF, otherwise a channel 1-16."""
    text = _cell(value)
    try:
        channel = int(float(text))
    except ValueError:
        return 0xFF
    return channel if 1 <= channel <= 16 else 0xFF


def bank_exp_range_byte(value) -> int:
    """CSV cell -> stored byte: empty/Default 0xFF, otherwise a value 0-127."""
    text = _cell(value)
    try:
        return max(0, min(127, int(float(text))))
    except ValueError:
        return 0xFF


def _bank_rows(df):
    """(bank, row) for each row of a per bank frame with a valid Bank_Number."""
    if df is None:
        return
    for _, row in df.iterrows():
        try:
            bank = int(float(_cell(row.get("Bank_Number"))))
        except ValueError:
            continue
        if 0 <= bank < NUM_BANKS:
            yield bank, row


def pack_bank_expression_range(df) -> bytes:
    """Four bytes per bank: pedal 1 lowest, highest, pedal 2 lowest, highest (0xFF = the pedal's own)."""
    out = bytearray(b"\xff" * (NUM_BANKS * 4))
    for bank, row in _bank_rows(df):
        base = bank * 4
        out[base] = bank_exp_range_byte(row.get("Exp1_Min"))
        out[base + 1] = bank_exp_range_byte(row.get("Exp1_Max"))
        out[base + 2] = bank_exp_range_byte(row.get("Exp2_Min"))
        out[base + 3] = bank_exp_range_byte(row.get("Exp2_Max"))
    return bytes(out)


def pack_bank_expression(df) -> bytes:
    """Four bytes per bank: pedal 1 CC, channel, pedal 2 CC, channel (0xFF = default)."""
    out = bytearray(b"\xff" * (NUM_BANKS * 4))
    for bank, row in _bank_rows(df):
        base = bank * 4
        out[base] = bank_exp_cc_byte(row.get("Exp1_CC"))
        out[base + 1] = bank_exp_channel_byte(row.get("Exp1_Channel"))
        out[base + 2] = bank_exp_cc_byte(row.get("Exp2_CC"))
        out[base + 3] = bank_exp_channel_byte(row.get("Exp2_Channel"))
    return bytes(out)


def empty_double_press_settings(num_banks=NUM_BANKS):
    """A DoublePress_Settings frame with one blank row per bank/button."""
    return empty_long_press_settings(num_banks)


def pack_double_press(sections: dict):
    """The double press commands, or None when no button has any.

    Empty command slots are packed as erased flash (0xFF), which the firmware
    reads as "no command", so the tools can skip those chunks entirely.
    """
    rows = {}
    if DOUBLE_PRESS_SECTION in sections:
        for _, row in sections[DOUBLE_PRESS_SECTION].iterrows():
            rows[_key(row["Bank_Number"], row["Button_Identifier"])] = row
    out = bytearray()
    for bank in range(NUM_BANKS):
        for btn in BUTTON_IDS:
            row = rows.get((str(bank), btn))
            packed = cbp.pack_row(row) if row is not None else [0] * (cbp.MIDI_NUM_COMMANDS_PER_SWITCH * 4)
            for i in range(0, len(packed), 4):
                cmd = packed[i:i + 4]
                out += bytes(cmd) if (cmd[0] & 0xF0) != 0 else b"\xff" * 4
    if out.count(0xFF) == len(out):
        return None
    return bytes(out)


def pack_flash_image(sections: dict) -> bytes:
    """Everything the tools write: the configuration and, when any button has
    one, the double press commands after the slot's pages (firmware 0.26)."""
    image = pack_config(sections)
    double = pack_double_press(sections)
    if double is None:
        return image
    return image.ljust(DOUBLE_PRESS_OFFSET, b"\xff") + double


def pack_config(sections: dict) -> bytes:
    """``sections`` is the dict returned by ``configCsv.read_config_csv``."""
    df_global = sections["Global_Settings"].set_index("Label")
    df_banks = sections["Bank_Naming"].set_index("Bank_Number")
    df_buttons = sections["Button_Settings"]

    out = []
    out += sbp.pack_global_settings(df_global)
    # Tells the firmware this slot's double press area was written, so it never
    # reads what older firmware or tools may have left there
    if pack_double_press(sections) is not None:
        out[sbp.GLOBAL_SETTINGS_DOUBLE_STORED] = 1
    out += sbp.pack_bank_strings(df_banks)

    # Rows may be missing (a configuration written for fewer banks) or in any
    # order; look each button up and pack an empty one when it is absent.
    button_rows = {}
    for _, row in df_buttons.iterrows():
        button_rows[_key(row["Bank_Number"], row["Button_Identifier"])] = row

    light_modes = []
    groups = []
    holds = []
    labels = b""
    cycle_labels = []
    for bank in range(NUM_BANKS):
        for btn in BUTTON_IDS:
            row = button_rows.get((str(bank), btn))
            if row is None:
                out += [0] * (cbp.MIDI_NUM_COMMANDS_PER_SWITCH * 4)
                light_modes.append("Normal")
                groups.append("")
                holds.append("")
                labels += pack_label("")
            else:
                out += cbp.pack_row(row, cycle_labels)
                light_modes.append(row.get("Light_Mode", "Normal"))
                groups.append(row.get("Group", ""))
                holds.append(row.get("Momentary_Hold", ""))
                labels += pack_label(row.get("Label", ""))
    out += cbp.pack_button_led_modes(light_modes, groups, holds)
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

    # Commands sent when a bank is entered; rows are optional
    enter_rows = {}
    if BANK_ENTER_SECTION in sections:
        for _, row in sections[BANK_ENTER_SECTION].iterrows():
            key = str(row["Bank_Number"]).strip()
            if key.endswith(".0"):
                key = key[:-2]
            enter_rows[key] = row
    for bank in range(NUM_BANKS):
        row = enter_rows.get(str(bank))
        if row is None:
            out += [0] * (cbp.MIDI_NUM_COMMANDS_PER_SWITCH * 4)
        else:
            out += cbp.pack_row(row, leave=True)

    out += list(pack_sysex_strings(sections.get(SYSEX_SECTION)))

    # Bank switch command lists; rows are optional and may be in any order
    sw_rows = {}
    if BANK_SWITCH_SECTION in sections:
        for _, row in sections[BANK_SWITCH_SECTION].iterrows():
            key = (str(row.get("Switch", "")).strip().title(),
                   str(row.get("Press", "")).strip().title())
            sw_rows[key] = row
    for key in BANK_SWITCH_LISTS:
        row = sw_rows.get(key)
        if row is None:
            out += [0] * (cbp.MIDI_NUM_COMMANDS_PER_SWITCH * 4)
        else:
            out += cbp.pack_row(row)

    out += list(pack_setlist(sections.get(SETLIST_SECTION)))
    out += list(pack_bank_expression(sections.get(BANK_EXPRESSION_SECTION)))
    out += list(pack_bank_expression_range(sections.get(BANK_EXPRESSION_SECTION)))
    out += list(cbp.pack_cycle_labels(cycle_labels))

    return bytes(out)
