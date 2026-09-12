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
"""

import pandas as pd

from lib.cmdBinaryPacker import (
    CMD_CC_NIBBLE,
    CMD_KEY_NIBBLE,
    CMD_NOTE_NIBBLE,
    CMD_PB_NIBBLE,
    CMD_PC_NIBBLE,
    CMD_START_NIBBLE,
    CMD_STOP_NIBBLE,
    HID_SPECIAL_KEYS,
    MIDI_NUM_COMMANDS_PER_SWITCH,
)

GLOBAL_SIZE = 32
BANK_STRINGS_SIZE = 8 * 12
NUM_BANKS = 8
BUTTON_IDS = ["1", "2", "3", "4", "A", "B", "C", "D"]
CMD_SIZE = 4
BUTTON_STRIDE = MIDI_NUM_COMMANDS_PER_SWITCH * CMD_SIZE
CONFIG_SIZE = (
    GLOBAL_SIZE + BANK_STRINGS_SIZE + NUM_BANKS * len(BUTTON_IDS) * BUTTON_STRIDE
)

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


def _ascii(chunk: bytes) -> str:
    return chunk.decode("ascii", errors="replace").rstrip(" \x00").replace(
        "\xff", ""
    )


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


def unpack_command(raw: bytes, slot_a: bool):
    """Decode one 4 byte command.

    Returns ``(fields, light_mode)``. ``light_mode`` is only meaningful for
    slot A, where the packer stores the button's LED mode in the MSB of
    bytes 2 (Reverse) and 3 (AlwaysOn). Those bits are stripped before the
    command itself is decoded so the CSV matches what was originally packed.

    Known ambiguity: a PC command in slot A without Bank Select MSB is stored
    as byte 2 == 0x80, which is indistinguishable from "Reverse + MSB 0". It is
    decoded as "no MSB, Normal", the far more common case.
    """
    b0, b1, b2, b3 = raw
    cmd = _empty_cmd()
    light_mode = "Normal"
    cmd_type = b0 & 0xF0

    if slot_a and cmd_type not in (0x00, 0xF0):
        if cmd_type == CMD_PC_NIBBLE and b2 == 0x80:
            pass  # "no bank select MSB", not Reverse
        elif b2 & 0x80:
            light_mode = "Reverse"
        if b3 & 0x80:
            light_mode = "AlwaysOn"
        b2 &= 0x7F
        b3 &= 0x7F

    channel = str((b0 & 0x0F) + 1)
    toggle = "Y" if b1 & 0x80 else "N"

    if cmd_type == CMD_PC_NIBBLE:
        cmd["CommandType"] = "PC"
        cmd["Channel_(PC/CC/Note/PB)"] = channel
        cmd["Number_(PC/CC/Note)"] = str(b1 & 0x7F)
        if b2 < 0x80:
            cmd["BankSelect_(PC)"] = str((b2 << 7) | (b3 & 0x7F))
            cmd["BankSelectHighByte_(PC)"] = "Y"
        else:
            cmd["BankSelect_(PC)"] = str(b3 & 0x7F)
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
    elif cmd_type == CMD_START_NIBBLE:
        cmd["CommandType"] = "Start"
    elif cmd_type == CMD_STOP_NIBBLE:
        cmd["CommandType"] = "Stop"
    # 0x00 (no command) and 0xF0 (erased flash) leave the empty template

    return cmd, light_mode


def unpack_button_settings(data: bytes) -> pd.DataFrame:
    columns = ["Bank_Number", "Button_Identifier"]
    for slot in SLOT_NAMES:
        columns += [f"{slot}_{f}" for f in CMD_FIELDS]
    columns.append("Light_Mode")
    columns += [f"{slot}_KeyMode_(Key)" for slot in SLOT_NAMES]

    rows = []
    base = GLOBAL_SIZE + BANK_STRINGS_SIZE
    for bank in range(NUM_BANKS):
        for btn_index, btn_id in enumerate(BUTTON_IDS):
            row = {"Bank_Number": str(bank), "Button_Identifier": btn_id}
            light_mode = "Normal"
            for slot_index, slot in enumerate(SLOT_NAMES):
                offset = (
                    base
                    + (bank * len(BUTTON_IDS) + btn_index) * BUTTON_STRIDE
                    + slot_index * CMD_SIZE
                )
                cmd, slot_light = unpack_command(
                    data[offset : offset + CMD_SIZE], slot_index == 0
                )
                if slot_index == 0:
                    light_mode = slot_light
                for f in CMD_FIELDS:
                    row[f"{slot}_{f}"] = cmd[f]
                row[f"{slot}_KeyMode_(Key)"] = cmd["KeyMode_(Key)"]
            row["Light_Mode"] = light_mode
            rows.append(row)

    return pd.DataFrame(rows, columns=columns)


def unpack_config(data: bytes):
    """Return ``(df_global, df_banks, df_buttons)`` from a settings dump."""
    if len(data) < CONFIG_SIZE:
        raise ValueError(
            f"Settings dump is {len(data)} bytes, expected at least {CONFIG_SIZE}"
        )
    return (
        unpack_global_settings(data),
        unpack_bank_strings(data),
        unpack_button_settings(data),
    )
