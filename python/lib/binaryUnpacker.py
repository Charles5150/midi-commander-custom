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
    CMD_NO_CMD_NIBBLE,
    CMD_WAIT_MODE,
    CMD_RAMP_MODE,
    CMD_CYCLE_MODE,
    CMD_LEAVE_MODE,
    CMD_EXP_MODE,
    CMD_LFO_MODE,
    CMD_MMC_MODE,
    CMD_SONG_MODE,
    CMD_CHAN_MODE,
    CHAN_15_BIT,
    CHAN_16_BIT,
    channel_list_text,
    CMD_SEQ_MODE,
    steps_text,
    CMD_VAR_MODE,
    VAR_MODES,
    VAR_DEFAULT_TOP,
    CMD_IF_MODE,
    CMD_MACRO_MODE,
    MACRO_LISTS,
    IF_TESTS,
    IF_BUTTON_TESTS,
    IF_VALUE_TESTS,
    button_name,
    MMC_COMMANDS,
    MMC_LOCATE,
    SONG_MODES,
    SONG_POSITION,
    LFO_DIVISIONS,
    LFO_SHAPES,
    EXP_TARGET_OFF,
    CYCLE_LABEL_COUNT,
    CYCLE_LABEL_LEN,
    PC_REL_MARKERS,
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
    CMD_PANIC_NIBBLE,
    CMD_SCENE_NIBBLE,
    SCENE_BUTTONS,
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
# Expression pedal CC and channel per bank (firmware 0.28), 4 bytes per bank
BANK_EXP_OFFSET = SETLIST_OFFSET + SETLIST_MAX
BANK_EXP_STRIDE = 4
BANK_EXP_CC_OFF = 0x80
# Expression pedal output range per bank (firmware 0.33), 4 bytes per bank
BANK_EXP_RANGE_OFFSET = BANK_EXP_OFFSET + NUM_BANKS * BANK_EXP_STRIDE
BANK_EXP_RANGE_STRIDE = 4
# Labels of the states of cycle buttons (firmware 0.38), 4 chars each
CYCLE_LABELS_OFFSET = BANK_EXP_RANGE_OFFSET + NUM_BANKS * BANK_EXP_RANGE_STRIDE
CONFIG_SIZE = CYCLE_LABELS_OFFSET + CYCLE_LABEL_COUNT * CYCLE_LABEL_LEN
# Double press commands follow the slot's 12 pages, in the extension area the
# firmware maps there (firmware 0.26). Same shape as the long press commands.
FLASH_PAGE_SIZE = 2048
SLOT_PAGES = 12
DOUBLE_PRESS_OFFSET = SLOT_PAGES * FLASH_PAGE_SIZE
DOUBLE_PRESS_SIZE = NUM_BANKS * len(BUTTON_IDS) * BUTTON_STRIDE
DOUBLE_PRESS_PAGES = 5
IMAGE_SIZE = DOUBLE_PRESS_OFFSET + DOUBLE_PRESS_PAGES * FLASH_PAGE_SIZE
EXP_CURVE_NAMES = {0: "Linear", 1: "Log", 2: "Exp"}
EXP_OUTPUT_NAMES = {0: "CC", 1: "PitchBend", 2: "CC14"}
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
_MMC_NAMES = {code: name for name, code in MMC_COMMANDS.items()}


def _ascii(chunk: bytes) -> str:
    """Printable ASCII from a fixed-width field; erased flash (0xFF) reads as empty."""
    return "".join(chr(b) if 0x20 <= b <= 0x7E else " " for b in chunk).rstrip()


def _led_mode_name(value: int) -> str:
    return LED_MODE_NAMES.get(value, "Normal")


def _button_led_byte(value: int) -> tuple:
    """(Light_Mode, Group, Momentary_Hold, Tempo_Flash, Global) from a button's
    LED mode byte: the mode in bits 0-1, the tempo flash in bit 2, global in
    bit 3, the exclusive group in bits 4-6, momentary hold in bit 7. Erased
    flash is Normal, with none of the four."""
    if value == 0xFF:
        return "Normal", "", "", "", ""
    group = (value >> 4) & 0x07
    hold = "Y" if value & 0x80 else ""
    flash = "Y" if value & 0x04 else ""
    glob = "Y" if value & 0x08 else ""
    return (_led_mode_name(value & 0x03), str(group) if group else "", hold,
            flash, glob)


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
        ("Clock_Follow", "Y" if g[34] == 1 else "N"),
        ("LED_Feedback", "Y" if g[35] == 1 else "N"),
        ("Double_Press_ms", str((g[36] if 0 < g[36] < 0xFF else 30) * 10)),
        ("Remote_Mode", {1: "CC", 2: "Note"}.get(g[38], "Off")),
        ("Remote_Channel", str(g[39]) if 1 <= g[39] <= 16 else "Any"),
        ("Remote_First", str(g[40] if g[40] <= 118 else 102)),
        ("Global_Channel", str(g[41]) if 1 <= g[41] <= 16 else "Off"),
        ("Edit_Lock", "Y" if g[42] == 1 else "N"),
        ("Kemper_Mode", "Y" if g[43] == 1 else "N"),
        ("Global_Bank", str(g[44] - 1) if 1 <= g[44] <= 32 else "Off"),
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


def unpack_cycle_labels(data: bytes) -> list:
    """The cycle label table; entries past the end of the data read as blank."""
    labels = []
    for i in range(CYCLE_LABEL_COUNT):
        start = CYCLE_LABELS_OFFSET + i * CYCLE_LABEL_LEN
        labels.append(_ascii(data[start : start + CYCLE_LABEL_LEN]).strip())
    return labels


def unpack_command(raw: bytes, cycle_labels=None) -> dict:
    """Decode one 4 byte command into its CSV fields. ``cycle_labels`` is the
    configuration's cycle label table, see unpack_cycle_labels."""
    b0, b1, b2, b3 = raw
    cmd = _empty_cmd()
    cmd_type = b0 & 0xF0

    channel = str((b0 & 0x0F) + 1)
    toggle = "Y" if b1 & 0x80 else "N"

    if cmd_type == CMD_NO_CMD_NIBBLE and (b0 & 0x0F) == CMD_WAIT_MODE:
        cmd["CommandType"] = "Wait"
        cmd["Duration_(Note/PB)"] = str(b2 * 10)
    elif cmd_type == CMD_NO_CMD_NIBBLE and (b0 & 0x0F) == CMD_RAMP_MODE:
        cmd["CommandType"] = "Ramp"
        cmd["Duration_(Note/PB)"] = str((b2 | (b3 << 8)) * 10)
    elif cmd_type == CMD_NO_CMD_NIBBLE and (b0 & 0x0F) == CMD_CYCLE_MODE:
        cmd["CommandType"] = "Cycle"
        if cycle_labels is not None and b1 < len(cycle_labels):
            cmd["OnValue_(CC/PB)"] = cycle_labels[b1]
    elif cmd_type == CMD_NO_CMD_NIBBLE and (b0 & 0x0F) == CMD_LEAVE_MODE:
        cmd["CommandType"] = "Leave"
    elif cmd_type == CMD_NO_CMD_NIBBLE and (b0 & 0x0F) == CMD_EXP_MODE:
        cmd["CommandType"] = "Exp"
        cmd["OnValue_(CC/PB)"] = str((b1 & 0x7F) + 1)
        cmd["Toggle_(CC/PB/Note)"] = toggle
        if b2 == EXP_TARGET_OFF:
            cmd["KeyMode_(Key)"] = "Off"
        elif b2 < 0x80:
            cmd["KeyMode_(Key)"] = "CC"
            cmd["Number_(PC/CC/Note)"] = str(b2)
            if 1 <= b3 <= 16:
                cmd["Channel_(PC/CC/Note/PB)"] = str(b3)
        else:
            cmd["KeyMode_(Key)"] = "Own"
    elif cmd_type == CMD_NO_CMD_NIBBLE and (b0 & 0x0F) == CMD_LFO_MODE:
        cmd["CommandType"] = "LFO"
        cmd["OnValue_(CC/PB)"] = LFO_DIVISIONS[min(b2, len(LFO_DIVISIONS) - 1)]
        cmd["KeyMode_(Key)"] = LFO_SHAPES[b3] if b3 < len(LFO_SHAPES) else LFO_SHAPES[0]
    elif cmd_type == CMD_NO_CMD_NIBBLE and (b0 & 0x0F) == CMD_SEQ_MODE:
        cmd["CommandType"] = "Seq"
        cmd["KeyMode_(Key)"] = LFO_DIVISIONS[min(b1 & 0x0F, len(LFO_DIVISIONS) - 1)]
        cmd["OnValue_(CC/PB)"] = steps_text([b2, b3])
    elif cmd_type == CMD_NO_CMD_NIBBLE and (b0 & 0x0F) == CMD_MMC_MODE:
        cmd["CommandType"] = "MMC"
        cmd["KeyMode_(Key)"] = _MMC_NAMES.get(b1, "Play")
        if b1 == MMC_LOCATE:
            cmd["OnValue_(CC/PB)"] = str((b2 & 0x7F) | ((b3 & 0x7F) << 7))
    elif cmd_type == CMD_NO_CMD_NIBBLE and (b0 & 0x0F) == CMD_SONG_MODE:
        cmd["CommandType"] = "Song"
        cmd["KeyMode_(Key)"] = SONG_MODES[1] if b1 == SONG_POSITION else SONG_MODES[0]
        cmd["OnValue_(CC/PB)"] = str((b2 & 0x7F) | ((b3 & 0x7F) << 7))
    elif cmd_type == CMD_NO_CMD_NIBBLE and (b0 & 0x0F) == CMD_VAR_MODE:
        cmd["CommandType"] = "Value"
        cmd["Number_(PC/CC/Note)"] = str((b1 & 0x07) + 1)
        mode = (b1 >> 4) & 0x03
        cmd["KeyMode_(Key)"] = VAR_MODES[mode] if mode < len(VAR_MODES) else VAR_MODES[0]
        cmd["OnValue_(CC/PB)"] = str(b2 & 0x7F)
        cmd["OffValue_(CC)"] = str((b3 & 0x7F) or VAR_DEFAULT_TOP)
    elif cmd_type == CMD_NO_CMD_NIBBLE and (b0 & 0x0F) == CMD_IF_MODE:
        cmd["CommandType"] = "If"
        test = b1 & 0x7F
        cmd["KeyMode_(Key)"] = IF_TESTS[test] if test < len(IF_TESTS) else IF_TESTS[0]
        if test in IF_BUTTON_TESTS:
            cmd["Number_(PC/CC/Note)"] = button_name(b2 & 0x07)
        elif test in IF_VALUE_TESTS:
            cmd["Number_(PC/CC/Note)"] = str((b2 & 0x07) + 1)
            cmd["OnValue_(CC/PB)"] = str(b3 & 0x7F)
        else:
            cmd["OnValue_(CC/PB)"] = str(b3 & 0x7F)
    elif cmd_type == CMD_NO_CMD_NIBBLE and (b0 & 0x0F) == CMD_MACRO_MODE:
        cmd["CommandType"] = "Macro"
        cmd["OnValue_(CC/PB)"] = str(b1 & 0x7F)
        cmd["Number_(PC/CC/Note)"] = button_name(b2 & 0x07)
        which = (b2 >> 4) & 0x03
        cmd["KeyMode_(Key)"] = MACRO_LISTS[which] if which < len(MACRO_LISTS) else MACRO_LISTS[0]
    elif cmd_type == CMD_NO_CMD_NIBBLE and (b0 & 0x0F) == CMD_CHAN_MODE:
        cmd["CommandType"] = "Chan"
        mask = (b2 & 0x7F) | ((b3 & 0x7F) << 7)
        if b1 & CHAN_15_BIT:
            mask |= 1 << 14
        if b1 & CHAN_16_BIT:
            mask |= 1 << 15
        cmd["Channel_(PC/CC/Note/PB)"] = channel_list_text(mask)
    elif cmd_type == CMD_PC_NIBBLE and b2 in PC_REL_MARKERS:
        cmd["CommandType"] = "PCInc"
        cmd["Channel_(PC/CC/Note/PB)"] = channel
        cmd["OffValue_(CC)"] = str(b1 & 0x7F)
        cmd["Number_(PC/CC/Note)"] = str(b3 & 0x7F)
        index = PC_REL_MARKERS.index(b2)
        cmd["KeyMode_(Key)"] = ("Down" if index & 1 else "Up") + (" Repeat" if index & 2 else "")
        cmd["Toggle_(CC/PB/Note)"] = "Y" if b3 & 0x80 else "N"
    elif cmd_type == CMD_PC_NIBBLE:
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
        cmd["OffValue_(CC)"] = str(b2 & 0x7F)
        cmd["KeyMode_(Key)"] = ("Down" if b3 & 0x80 else "Up") + (" Repeat" if b2 & 0x80 else "")
        cmd["Toggle_(CC/PB/Note)"] = "Y" if b1 & 0x80 else "N"
    elif cmd_type == CMD_TAP_NIBBLE:
        cmd["CommandType"] = "Tap"
        mode = b0 & 0x0F
        if mode == 1:
            cmd["KeyMode_(Key)"] = "Clock"
        elif mode == 2:
            cmd["KeyMode_(Key)"] = "Set"
            cmd["OnValue_(CC/PB)"] = str((b2 & 0x7F) | ((b3 & 0x7F) << 7))
        elif mode in (3, 4):
            cmd["KeyMode_(Key)"] = ("Down" if mode == 4 else "Up") + (" Repeat" if b2 & 0x80 else "")
            cmd["OffValue_(CC)"] = str(b2 & 0x7F)
        else:
            cmd["KeyMode_(Key)"] = "Tap"
    elif cmd_type == CMD_SYSEX_NIBBLE:
        cmd["CommandType"] = "SysEx"
        cmd["Number_(PC/CC/Note)"] = str(b1)
    elif cmd_type == CMD_BANK_NIBBLE:
        cmd["CommandType"] = "Bank"
        mode = b0 & 0x0F
        cmd["KeyMode_(Key)"] = {1: "Up", 2: "Down", 3: "Config", 4: "NextConfig", 5: "Page", 6: "Back"}.get(mode, "GoTo")
        if mode == 3:
            cmd["OnValue_(CC/PB)"] = str(min(b1, 3) + 1)   # slots are 1-4 for people
        elif mode == 4 or mode == 6:
            cmd["OnValue_(CC/PB)"] = ""
        else:
            cmd["OnValue_(CC/PB)"] = str(b1)
    elif cmd_type == CMD_START_NIBBLE:
        cmd["CommandType"] = "Start"
    elif cmd_type == CMD_STOP_NIBBLE:
        cmd["CommandType"] = "Stop"
    elif cmd_type == CMD_PANIC_NIBBLE:
        cmd["CommandType"] = "Panic"
    elif cmd_type == CMD_SCENE_NIBBLE:
        cmd["CommandType"] = "Scene"
        cmd["OnValue_(CC/PB)"] = "".join(
            ("+" if (b2 >> i) & 1 else "-") if (b1 >> i) & 1 else "."
            for i in range(len(SCENE_BUTTONS))
        )
    # 0x00 (no command) and 0xF0 (erased flash) leave the empty template

    return cmd


def unpack_button_settings(data: bytes) -> pd.DataFrame:
    columns = ["Bank_Number", "Button_Identifier", "Label"]
    for slot in SLOT_NAMES:
        columns += [f"{slot}_{f}" for f in CMD_FIELDS]
    columns += ["Light_Mode", "Group", "Momentary_Hold", "Tempo_Flash", "Global"]
    columns += [f"{slot}_KeyMode_(Key)" for slot in SLOT_NAMES]

    cycle_labels = unpack_cycle_labels(data)
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
                cmd = unpack_command(data[offset : offset + CMD_SIZE], cycle_labels)
                for f in CMD_FIELDS:
                    row[f"{slot}_{f}"] = cmd[f]
                row[f"{slot}_KeyMode_(Key)"] = cmd["KeyMode_(Key)"]
            (row["Light_Mode"], row["Group"], row["Momentary_Hold"],
             row["Tempo_Flash"], row["Global"]) = _button_led_byte(
                data[LED_MODES_OFFSET + button_number])
            rows.append(row)

    return pd.DataFrame(rows, columns=columns)


def unpack_long_press_settings(data: bytes) -> pd.DataFrame:
    return _unpack_button_lists(data, LONG_PRESS_OFFSET)


def unpack_double_press_settings(data: bytes) -> pd.DataFrame:
    """Double press commands from a full image (IMAGE_SIZE bytes).

    A dump that stops at CONFIG_SIZE, read from firmware older than 0.26, has
    none: every button then decodes as empty, exactly like erased flash.
    """
    if len(data) < DOUBLE_PRESS_OFFSET + DOUBLE_PRESS_SIZE:
        data = bytes(DOUBLE_PRESS_OFFSET + DOUBLE_PRESS_SIZE)
    return _unpack_button_lists(data, DOUBLE_PRESS_OFFSET)


def _unpack_button_lists(data: bytes, base: int) -> pd.DataFrame:
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
                offset = base + button_number * BUTTON_STRIDE + slot_index * CMD_SIZE
                cmd = unpack_command(data[offset : offset + CMD_SIZE])
                for f in CMD_FIELDS:
                    row[f"{slot}_{f}"] = cmd[f]
                row[f"{slot}_KeyMode_(Key)"] = cmd["KeyMode_(Key)"]
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def unpack_bank_expression_settings(data: bytes) -> pd.DataFrame:
    """Per bank CC, channel and output range of each expression pedal; empty
    cells keep the pedal's own."""
    def cc_text(b):
        if b == BANK_EXP_CC_OFF:
            return "Off"
        return str(b) if b <= 127 else ""

    def channel_text(b):
        return str(b) if 1 <= b <= 16 else ""

    def range_text(b):
        return str(b) if b <= 127 else ""

    def chunk_at(offset, stride):
        chunk = bytes(data[offset : offset + stride])
        return chunk + b"\xff" * (stride - len(chunk))

    rows = []
    for bank in range(NUM_BANKS):
        chunk = chunk_at(BANK_EXP_OFFSET + bank * BANK_EXP_STRIDE, BANK_EXP_STRIDE)
        rng = chunk_at(BANK_EXP_RANGE_OFFSET + bank * BANK_EXP_RANGE_STRIDE, BANK_EXP_RANGE_STRIDE)
        rows.append({
            "Bank_Number": str(bank),
            "Exp1_CC": cc_text(chunk[0]),
            "Exp1_Channel": channel_text(chunk[1]),
            "Exp1_Min": range_text(rng[0]),
            "Exp1_Max": range_text(rng[1]),
            "Exp2_CC": cc_text(chunk[2]),
            "Exp2_Channel": channel_text(chunk[3]),
            "Exp2_Min": range_text(rng[2]),
            "Exp2_Max": range_text(rng[3]),
        })
    return pd.DataFrame(rows, columns=["Bank_Number", "Exp1_CC", "Exp1_Channel", "Exp1_Min", "Exp1_Max",
                                       "Exp2_CC", "Exp2_Channel", "Exp2_Min", "Exp2_Max"])


def unpack_expression_settings(data: bytes) -> pd.DataFrame:
    rows = []
    for i in range(2):
        p = data[EXP_OFFSET + i * EXP_STRIDE : EXP_OFFSET + (i + 1) * EXP_STRIDE]
        lo = p[0] | (p[1] << 8)
        hi = p[2] | (p[3] << 8)
        if lo > 4095 or hi > 4095 or lo + 100 > hi:
            lo, hi = 80, 3900  # blank or invalid: firmware falls back to defaults
        # Output range, read as the firmware does: older tools wrote zeros
        out_min = p[11] if p[11] <= 127 else 0
        out_max = p[12] if p[12] <= 127 else 127
        if p[11] == 0 and p[12] == 0:
            out_max = 127
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
                "Out_Min": str(out_min),
                "Out_Max": str(out_max),
                "Auto_Button": EXP_BUTTON_IDS[p[13] - 1] if 1 <= p[13] <= 8 else "None",
                "Auto_Off_ms": str(p[14] * 10 if p[14] not in (0, 0xFF) else 500),
                "Output": EXP_OUTPUT_NAMES.get(p[15], "CC"),
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
    if len(data) < CYCLE_LABELS_OFFSET:
        raise ValueError(
            f"Settings dump is {len(data)} bytes, expected at least {CONFIG_SIZE}"
        )
    # A dump saved by tools older than 0.38 stops before the cycle labels
    if len(data) < CONFIG_SIZE:
        data = bytes(data) + b"\xff" * (CONFIG_SIZE - len(data))
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
