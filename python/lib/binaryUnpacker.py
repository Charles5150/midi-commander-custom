"""Decode the settings binary read back from the Midi Commander into DataFrames.

This is the inverse of ``settingsBinaryPacker`` and ``cmdBinaryPacker``. The
resulting DataFrames use exactly the same column layout the GUI configurator
and ``CSV_to_Flash.py`` expect, so a device dump can be saved as a CSV and
edited or re-flashed without any further conversion.

Memory layout (see firmware/Core/Src/flash_midi_settings.c):

    0..15    global settings
    16..31   config name (ASCII, space padded)
    32..127  8 banks x (4 byte large name + 8 byte small name)
    128..    8 banks x 8 buttons x 10 commands x 4 bytes
    2688..   button LED mode table, one byte per button (bank * 8 + button)
"""

import pandas as pd

from lib.cmdBinaryPacker import (
    CMD_CC_NIBBLE,
    CMD_BANK_NIBBLE,
    CMD_CCINC_NIBBLE,
    CMD_KEY_NIBBLE,
    CMD_MEDIA_NIBBLE,
    CMD_NOTE_NIBBLE,
    CMD_PB_NIBBLE,
    CMD_PC_NIBBLE,
    CMD_START_NIBBLE,
    CMD_SYSEX_NIBBLE,
    CMD_TAP_NIBBLE,
    CMD_STOP_NIBBLE,
    HID_SPECIAL_KEYS,
    MEDIA_KEYS,
    MIDI_NUM_COMMANDS_PER_SWITCH,
)

GLOBAL_SIZE = 48
NUM_BANKS = 32
BANK_STRINGS_SIZE = NUM_BANKS * 12
BUTTON_IDS = ["1", "2", "3", "4", "A", "B", "C", "D"]
CMD_SIZE = 4
BUTTON_STRIDE = MIDI_NUM_COMMANDS_PER_SWITCH * CMD_SIZE
LABEL_LEN = 4
COMMANDS_OFFSET = GLOBAL_SIZE + BANK_STRINGS_SIZE
LED_MODES_OFFSET = COMMANDS_OFFSET + NUM_BANKS * len(BUTTON_IDS) * BUTTON_STRIDE
LABELS_OFFSET = LED_MODES_OFFSET + NUM_BANKS * len(BUTTON_IDS)
LONG_PRESS_OFFSET = LABELS_OFFSET + NUM_BANKS * len(BUTTON_IDS) * LABEL_LEN
EXP_OFFSET = LONG_PRESS_OFFSET + NUM_BANKS * len(BUTTON_IDS) * BUTTON_STRIDE
EXP_STRIDE = 16
BANK_ENTER_OFFSET = EXP_OFFSET + 2 * EXP_STRIDE
SYSEX_OFFSET = BANK_ENTER_OFFSET + NUM_BANKS * BUTTON_STRIDE
SYSEX_STRING_COUNT = 16
SYSEX_STRING_MAX = 23
SYSEX_STRING_STRIDE = SYSEX_STRING_MAX + 1
BANK_SWITCH_OFFSET = SYSEX_OFFSET + SYSEX_STRING_COUNT * SYSEX_STRING_STRIDE
# 0 Down short, 1 Down long, 2 Up short, 3 Up long
BANK_SWITCH_LISTS = [("Down", "Short"), ("Down", "Long"), ("Up", "Short"), ("Up", "Long")]
SETLIST_OFFSET = BANK_SWITCH_OFFSET + len(BANK_SWITCH_LISTS) * BUTTON_STRIDE
SETLIST_MAX = 32
CONFIG_SIZE = SETLIST_OFFSET + SETLIST_MAX
EXP_CURVE_NAMES = {0: "Linear", 1: "Log", 2: "Exp"}
EXP_BUTTON_IDS = ["1", "2", "3", "4", "A", "B", "C", "D"]

SLOT_NAMES = [chr(ord("A") + i) for i in range(MIDI_NUM_COMMANDS_PER_SWITCH)]

# Per-command CSV columns, in the order the GUI writes them.
CMD_FIELDS = [
    "CommandType",
    "Channel_(PC/CC/Note/PB)",
    "Number_(PC/CC/Note)",
    "OnValue_(CC/PB)",
    "OffValue_(CC)",
    "BankSelect_(PC)",
    "BankSelectHighByte_(PC)",
    "Toggle_(CC/PB/Note)",
    "Velocity_(Note)",
    "Duration_(Note/PB)",
]

LED_MODE_NAMES = {0: "Normal", 1: "Reverse", 2: "AlwaysOn"}

# Reverse lookup for HID usage IDs -> key names. Letters and digits are
# generated; everything else comes from the packer's table. "esc" and
# "escape" share a code, keep the short spelling.
_HID_NAMES = {4 + i: chr(ord("a") + i) for i in range(26)}
_HID_NAMES.update({30 + i: str(i + 1) for i in range(9)})
_HID_NAMES[39] = "0"
for _name, _code in HID_SPECIAL_KEYS.items():
    _HID_NAMES.setdefault(_code, _name)
_MEDIA_NAMES = {code: name for name, code in MEDIA_KEYS.items()}


def _ascii(chunk: bytes) -> str:
    """Printable ASCII from a fixed-width field; erased flash (0xFF) reads as empty."""
    return "".join(chr(b) if 0x20 <= b <= 0x7E else " " for b in chunk).rstrip()


def _led_mode_name(value: int) -> str:
    return LED_MODE_NAMES.get(value, "Normal")


def unpack_global_settings(data: bytes) -> pd.DataFrame:
    g = data[:GLOBAL_SIZE]
    exp1 = g[2] if 0 < g[2] <= 127 else 11
    exp2 = g[3] if 0 < g[3] <= 127 else 4
    rows = [
        ("MIDI_Channel", str((g[0] & 0x0F) + 1)),
        ("RealTime_Passthrough", "Y" if g[1] == 1 else "N"),
        ("ConfigName", _ascii(g[16:32])),
        ("Exp1_CC", str(exp1)),
        ("Exp2_CC", str(exp2)),
        ("Bank_Up_LED_Mode", _led_mode_name(g[4])),
        ("Bank_Down_LED_Mode", _led_mode_name(g[5])),
        ("USB_MIDI_Thru", "Y" if g[6] == 1 else "N"),
        ("Remember_State", "Y" if g[7] == 1 else "N"),
        ("Long_Press_ms", str((g[8] if 0 < g[8] < 0xFF else 50) * 10)),
        ("LED_Brightness", str(g[9] if 0 < g[9] <= 100 else 100)),
        ("LED_Rest_Brightness", str(g[10] if 0 < g[10] <= 100 else 100)),
        ("Bank_Jump_Step", str(g[11] if 0 < g[11] < NUM_BANKS else 8)),
        ("Bank_Change_Mode", {1: "PC", 2: "CC"}.get(g[12], "Off")),
        ("Bank_Change_Channel", str(g[13]) if 1 <= g[13] <= 16 else "Any"),
        ("Bank_Change_CC", str(g[14] if g[14] <= 127 else 0)),
        ("Bank_Switch_Mode", {1: "Bank+MIDI", 2: "MIDI only"}.get(g[15], "Bank")),
        ("Sleep_After_Min", "0" if g[32] in (0, 0xFF) else str(min(g[32], 60))),
        ("Setlist_Mode", "Y" if g[33] == 1 else "N"),
    ]
    return pd.DataFrame(rows, columns=["Label", "Value"])


def unpack_bank_strings(data: bytes) -> pd.DataFrame:
    rows = []
    for bank in range(NUM_BANKS):
        base = GLOBAL_SIZE + bank * 12
        rows.append(
            (str(bank), _ascii(data[base : base + 4]), _ascii(data[base + 4 : base + 12]))
        )
    return pd.DataFrame(
        rows, columns=["Bank_Number", "Bank_Name_Large", "Bank_Info_Small"]
    )


def _empty_cmd() -> dict:
    cmd = {f: "" for f in CMD_FIELDS}
    cmd["Toggle_(CC/PB/Note)"] = "N"
    cmd["KeyMode_(Key)"] = ""
    return cmd


def unpack_command(raw: bytes) -> dict:
    """Decode one 4 byte command into its CSV fields."""
    b0, b1, b2, b3 = raw
    cmd = _empty_cmd()
    cmd_type = b0 & 0xF0

    channel = str((b0 & 0x0F) + 1)
    toggle = "Y" if b1 & 0x80 else "N"

    if cmd_type == CMD_PC_NIBBLE:
        cmd["CommandType"] = "PC"
        cmd["Channel_(PC/CC/Note/PB)"] = channel
        cmd["Number_(PC/CC/Note)"] = str(b1 & 0x7F)
        if b2 < 0x80:
            # High byte present, so the value spans both bytes
            cmd["BankSelect_(PC)"] = str((b2 << 7) | (b3 & 0x7F))
            cmd["BankSelectHighByte_(PC)"] = "Y"
        elif b3 < 0x80:
            cmd["BankSelect_(PC)"] = str(b3 & 0x7F)
            cmd["BankSelectHighByte_(PC)"] = "N"
        else:
            # Neither byte holds a value: the command sends no Bank Select
            cmd["BankSelect_(PC)"] = ""
            cmd["BankSelectHighByte_(PC)"] = "N"
    elif cmd_type == CMD_CC_NIBBLE:
        cmd["CommandType"] = "CC"
        cmd["Channel_(PC/CC/Note/PB)"] = channel
        cmd["Number_(PC/CC/Note)"] = str(b1 & 0x7F)
        cmd["OnValue_(CC/PB)"] = str(b2 & 0x7F)
        cmd["OffValue_(CC)"] = str(b3)
        cmd["Toggle_(CC/PB/Note)"] = toggle
    elif cmd_type == CMD_NOTE_NIBBLE:
        cmd["CommandType"] = "Note"
        cmd["Channel_(PC/CC/Note/PB)"] = channel
        cmd["Number_(PC/CC/Note)"] = str(b1 & 0x7F)
        cmd["Velocity_(Note)"] = str(b2 & 0x7F)
        cmd["Duration_(Note/PB)"] = str(b3 & 0x7F)
        cmd["Toggle_(CC/PB/Note)"] = toggle
    elif cmd_type == CMD_PB_NIBBLE:
        cmd["CommandType"] = "PB"
        cmd["Channel_(PC/CC/Note/PB)"] = channel
        pitch = (((b2 & 0x7F) << 7) | (b1 & 0x7F)) - 0x2000
        cmd["OnValue_(CC/PB)"] = str(pitch)
        cmd["Duration_(Note/PB)"] = str(b3 & 0x7F)
        cmd["Toggle_(CC/PB/Note)"] = toggle
    elif cmd_type == CMD_KEY_NIBBLE:
        cmd["CommandType"] = "Key"
        cmd["KeyMode_(Key)"] = {1: "Down", 2: "Up"}.get(b0 & 0x0F, "Normal")
        cmd["Number_(PC/CC/Note)"] = str(b1)
        cmd["OnValue_(CC/PB)"] = _HID_NAMES.get(b2, str(b2))
        cmd["Duration_(Note/PB)"] = str(b3 & 0x7F)
        cmd["Toggle_(CC/PB/Note)"] = "Y" if b3 & 0x80 else "N"
    elif cmd_type == CMD_MEDIA_NIBBLE:
        cmd["CommandType"] = "Media"
        usage = b1 | ((b2 & 0x03) << 8)
        cmd["OnValue_(CC/PB)"] = _MEDIA_NAMES.get(usage, str(usage))
        cmd["Duration_(Note/PB)"] = str(b3 & 0x7F)
        cmd["Toggle_(CC/PB/Note)"] = "Y" if b3 & 0x80 else "N"
    elif cmd_type == CMD_CCINC_NIBBLE:
        cmd["CommandType"] = "CCInc"
        cmd["Channel_(PC/CC/Note/PB)"] = channel
        cmd["Number_(PC/CC/Note)"] = str(b1 & 0x7F)
        cmd["OnValue_(CC/PB)"] = str(b3 & 0x7F)
        cmd["OffValue_(CC)"] = str(b2)
        cmd["KeyMode_(Key)"] = "Down" if b3 & 0x80 else "Up"
        cmd["Toggle_(CC/PB/Note)"] = "Y" if b1 & 0x80 else "N"
    elif cmd_type == CMD_TAP_NIBBLE:
        cmd["CommandType"] = "Tap"
        cmd["KeyMode_(Key)"] = "Clock" if (b0 & 0x0F) == 1 else "Tap"
    elif cmd_type == CMD_SYSEX_NIBBLE:
        cmd["CommandType"] = "SysEx"
        cmd["Number_(PC/CC/Note)"] = str(b1)
    elif cmd_type == CMD_BANK_NIBBLE:
        cmd["CommandType"] = "Bank"
        mode = b0 & 0x0F
        cmd["KeyMode_(Key)"] = {1: "Up", 2: "Down"}.get(mode, "GoTo")
        cmd["OnValue_(CC/PB)"] = str(b1)
    elif cmd_type == CMD_START_NIBBLE:
        cmd["CommandType"] = "Start"
    elif cmd_type == CMD_STOP_NIBBLE:
        cmd["CommandType"] = "Stop"
    # 0x00 (no command) and 0xF0 (erased flash) leave the empty template

    return cmd


def unpack_button_settings(data: bytes) -> pd.DataFrame:
    columns = ["Bank_Number", "Button_Identifier", "Label"]
    for slot in SLOT_NAMES:
        columns += [f"{slot}_{f}" for f in CMD_FIELDS]
    columns.append("Light_Mode")
    columns += [f"{slot}_KeyMode_(Key)" for slot in SLOT_NAMES]

    rows = []
    for bank in range(NUM_BANKS):
        for btn_index, btn_id in enumerate(BUTTON_IDS):
            button_number = bank * len(BUTTON_IDS) + btn_index
            label_start = LABELS_OFFSET + button_number * LABEL_LEN
            row = {
                "Bank_Number": str(bank),
                "Button_Identifier": btn_id,
                "Label": _ascii(data[label_start : label_start + LABEL_LEN]),
            }
            for slot_index, slot in enumerate(SLOT_NAMES):
                offset = (
                    COMMANDS_OFFSET + button_number * BUTTON_STRIDE + slot_index * CMD_SIZE
                )
                cmd = unpack_command(data[offset : offset + CMD_SIZE])
                for f in CMD_FIELDS:
                    row[f"{slot}_{f}"] = cmd[f]
                row[f"{slot}_KeyMode_(Key)"] = cmd["KeyMode_(Key)"]
            row["Light_Mode"] = _led_mode_name(data[LED_MODES_OFFSET + button_number])
            rows.append(row)

    return pd.DataFrame(rows, columns=columns)


def unpack_long_press_settings(data: bytes) -> pd.DataFrame:
    columns = ["Bank_Number", "Button_Identifier"]
    for slot in SLOT_NAMES:
        columns += [f"{slot}_{f}" for f in CMD_FIELDS]
    columns += [f"{slot}_KeyMode_(Key)" for slot in SLOT_NAMES]

    rows = []
    for bank in range(NUM_BANKS):
        for btn_index, btn_id in enumerate(BUTTON_IDS):
            button_number = bank * len(BUTTON_IDS) + btn_index
            row = {"Bank_Number": str(bank), "Button_Identifier": btn_id}
            for slot_index, slot in enumerate(SLOT_NAMES):
                offset = LONG_PRESS_OFFSET + button_number * BUTTON_STRIDE + slot_index * CMD_SIZE
                cmd = unpack_command(data[offset : offset + CMD_SIZE])
                for f in CMD_FIELDS:
                    row[f"{slot}_{f}"] = cmd[f]
                row[f"{slot}_KeyMode_(Key)"] = cmd["KeyMode_(Key)"]
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def unpack_expression_settings(data: bytes) -> pd.DataFrame:
    rows = []
    for i in range(2):
        p = data[EXP_OFFSET + i * EXP_STRIDE : EXP_OFFSET + (i + 1) * EXP_STRIDE]
        lo = p[0] | (p[1] << 8)
        hi = p[2] | (p[3] << 8)
        if lo > 4095 or hi > 4095 or lo + 100 > hi:
            lo, hi = 80, 3900  # blank or invalid: firmware falls back to defaults
        rows.append(
            {
                "Pedal": str(i + 1),
                "Min_ADC": str(lo),
                "Max_ADC": str(hi),
                "Curve": EXP_CURVE_NAMES.get(p[4], "Linear"),
                "Invert": "Y" if p[5] == 1 else "N",
                "Channel": str(p[6]) if 1 <= p[6] <= 16 else "Global",
                "Toe_Button": EXP_BUTTON_IDS[p[7]] if p[7] < 8 else "None",
                "Heel_Button": EXP_BUTTON_IDS[p[8]] if p[8] < 8 else "None",
                "Toe_Level": str(p[9] if 0 < p[9] <= 127 else 120),
                "Heel_Level": str(p[10] if p[10] <= 127 else 7),
            }
        )
    return pd.DataFrame(rows)


def unpack_bank_enter_settings(data: bytes) -> pd.DataFrame:
    """Commands sent when each bank is entered, one row per bank."""
    columns = ["Bank_Number"]
    for slot in SLOT_NAMES:
        columns += [f"{slot}_{f}" for f in CMD_FIELDS]
    columns += [f"{slot}_KeyMode_(Key)" for slot in SLOT_NAMES]

    rows = []
    for bank in range(NUM_BANKS):
        row = {"Bank_Number": str(bank)}
        for slot_index, slot in enumerate(SLOT_NAMES):
            offset = BANK_ENTER_OFFSET + bank * BUTTON_STRIDE + slot_index * CMD_SIZE
            cmd = unpack_command(data[offset : offset + CMD_SIZE])
            for f in CMD_FIELDS:
                row[f"{slot}_{f}"] = cmd[f]
            row[f"{slot}_KeyMode_(Key)"] = cmd["KeyMode_(Key)"]
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def unpack_bank_switch_settings(data: bytes) -> pd.DataFrame:
    """Command lists for the Bank Down/Up switches, short and long press."""
    columns = ["Switch", "Press"]
    for slot in SLOT_NAMES:
        columns += [f"{slot}_{f}" for f in CMD_FIELDS]
    columns += [f"{slot}_KeyMode_(Key)" for slot in SLOT_NAMES]

    rows = []
    for i, (switch, press) in enumerate(BANK_SWITCH_LISTS):
        row = {"Switch": switch, "Press": press}
        for slot_index, slot in enumerate(SLOT_NAMES):
            offset = BANK_SWITCH_OFFSET + i * BUTTON_STRIDE + slot_index * CMD_SIZE
            cmd = unpack_command(data[offset : offset + CMD_SIZE])
            for f in CMD_FIELDS:
                row[f"{slot}_{f}"] = cmd[f]
            row[f"{slot}_KeyMode_(Key)"] = cmd["KeyMode_(Key)"]
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def unpack_setlist(data: bytes) -> pd.DataFrame:
    """Bank numbers in setlist order; the list ends at the first invalid entry."""
    rows = []
    for i in range(SETLIST_MAX):
        bank = data[SETLIST_OFFSET + i]
        if bank >= NUM_BANKS:
            break
        rows.append({"Position": str(i + 1), "Bank_Number": str(bank)})
    return pd.DataFrame(rows, columns=["Position", "Bank_Number"])


def unpack_sysex_strings(data: bytes) -> pd.DataFrame:
    """The stored SysEx payloads, as space separated hex bytes."""
    rows = []
    for i in range(SYSEX_STRING_COUNT):
        entry = data[SYSEX_OFFSET + i * SYSEX_STRING_STRIDE :][:SYSEX_STRING_STRIDE]
        length = entry[0]
        payload = "" if length == 0 or length > SYSEX_STRING_MAX else " ".join(
            f"{b:02X}" for b in entry[1 : 1 + length]
        )
        rows.append({"Index": str(i), "Bytes": payload})
    return pd.DataFrame(rows)


def unpack_config(data: bytes):
    """Return the six configuration frames plus the SysEx string table."""
    if len(data) < CONFIG_SIZE:
        raise ValueError(
            f"Settings dump is {len(data)} bytes, expected at least {CONFIG_SIZE}"
        )
    return (
        unpack_global_settings(data),
        unpack_bank_strings(data),
        unpack_button_settings(data),
        unpack_long_press_settings(data),
        unpack_expression_settings(data),
        unpack_bank_enter_settings(data),
        unpack_sysex_strings(data),
        unpack_bank_switch_settings(data),
        unpack_setlist(data),
    )
