import pandas as pd

MIDI_NUM_COMMANDS_PER_SWITCH = 10

CMD_NO_CMD_NIBBLE = 0x00
CMD_PC_NIBBLE = 0xC0
CMD_CC_NIBBLE = 0xB0
CMD_PB_NIBBLE = 0xE0
CMD_NOTE_NIBBLE = 0x90
CMD_START_NIBBLE = 0x10
CMD_STOP_NIBBLE = 0x20
CMD_KEY_NIBBLE = 0xD0


# Standard command
# byte 1
# Upper 4 bits -> command types
# Lower 4 bits -> channel
# byte 2
# Most significant bit -> toggle control


def safe_int(val, default=0):
    try:
        if pd.isna(val) or str(val).strip() == "":
            return default
        return int(float(str(val)))
    except:
        return default


def get_hid_code(val):
    s_val = str(val).strip()

    # Map common keys (Single chars)
    if len(s_val) == 1:
        c = s_val.lower()
        if "a" <= c <= "z":
            return 4 + (ord(c) - ord("a"))
        if "1" <= c <= "9":
            return 30 + (int(c) - 1)
        if c == "0":
            return 39
        if c == " ":
            return 44  # Space

    # Special keys
    special = {
        "enter": 40,
        "esc": 41,
        "escape": 41,
        "backspace": 42,
        "tab": 43,
        "space": 44,
        "minus": 45,
        "equal": 46,
        "leftbr": 47,
        "rightbr": 48,
        "backslash": 49,
        "semicolon": 51,
        "quote": 52,
        "grave": 53,
        "comma": 54,
        "dot": 55,
        "slash": 56,
        "f1": 58,
        "f2": 59,
        "f3": 60,
        "f4": 61,
        "f5": 62,
        "f6": 63,
        "f7": 64,
        "f8": 65,
        "f9": 66,
        "f10": 67,
        "f11": 68,
        "f12": 69,
    }
    if s_val.lower() in special:
        return special[s_val.lower()]

    # Fallback to raw int
    try:
        return int(float(s_val))
    except:
        return 0


def get_toggle_bit(toggle_str):
    if not isinstance(toggle_str, str):
        return 0
    if "Y" in toggle_str:
        return 0x80
    else:
        return 0


# Program Change (or patch change) command, including back select
def cmd_pc(cmd):
    bank_select_low = safe_int(cmd["BankSelect_(PC)"]) & 0x7F

    bs_high_str = str(cmd["BankSelectHighByte_(PC)"])
    if "Y" in bs_high_str:
        bank_select_high = (safe_int(cmd["BankSelect_(PC)"]) >> 7) & 0x7F
    else:
        bank_select_high = 0x80

    cmd_bytes = [
        CMD_PC_NIBBLE
        | safe_int(cmd["Channel_(PC/CC/Note/PB)"] - 1),  # Command and channel
        safe_int(cmd["Number_(PC/CC/Note)"]) & 0x7F,  # Patch number
        bank_select_high,
        bank_select_low,
    ]

    return cmd_bytes


def cmd_cc(cmd):
    cmd_bytes = [
        CMD_CC_NIBBLE
        | safe_int(cmd["Channel_(PC/CC/Note/PB)"] - 1),  # Command and channel
        safe_int(cmd["Number_(PC/CC/Note)"]) & 0x7F
        | get_toggle_bit(str(cmd["Toggle_(CC/PB/Note)"])),  # command number & toggle
        safe_int(cmd["OnValue_(CC/PB)"]) & 0x7F,
        safe_int(cmd["OffValue_(CC)"]),
    ]
    return cmd_bytes


def cmd_note(cmd):
    cmd_bytes = [
        CMD_NOTE_NIBBLE
        | safe_int(cmd["Channel_(PC/CC/Note/PB)"] - 1),  # Command and channel
        safe_int(cmd["Number_(PC/CC/Note)"]) & 0x7F
        | get_toggle_bit(str(cmd["Toggle_(CC/PB/Note)"])),  # note number & toggle
        safe_int(cmd["Velocity_(Note)"]) & 0x7F,
        safe_int(cmd["Duration_(Note/PB)"]) & 0x7F,
    ]
    return cmd_bytes


def cmd_pb(cmd):
    # The pitch in the CSV file will be -8192 to 8191, this needs to be centered
    # around 0x2000

    if -8192 > safe_int(cmd["OnValue_(CC/PB)"]) > 8191:
        raise ValueError("PB outside of range: ", cmd["OnValue_(CC/PB)"])

    pitch = int(safe_int(cmd["OnValue_(CC/PB)"]) + 0x2000)

    pitch_LSB = pitch & 0x7F
    pitch_MSB = (pitch >> 7) & 0x7F

    cmd_bytes = [
        CMD_PB_NIBBLE
        | safe_int(cmd["Channel_(PC/CC/Note/PB)"] - 1),  # Command and channel
        pitch_LSB
        | get_toggle_bit(
            str(cmd["Toggle_(CC/PB/Note)"])
        ),  # high byte of value & toggle
        pitch_MSB,
        safe_int(cmd["Duration_(Note/PB)"]) & 0x7F,
    ]
    return cmd_bytes


def cmd_start(cmd):
    return [CMD_START_NIBBLE, 0, 0, 0]


# Helper to get Key Mode Nibble from string
# Normal (0), Down (1), Up (2)
def _get_key_mode_nibble(mode_str):
    if not isinstance(mode_str, str):
        return 0
    s = mode_str.lower()
    if "down" in s:
        return 1
    elif "up" in s:
        return 2
    return 0


def cmd_key(cmd):
    # Mode Logic:
    # We expect a "Key Mode" column if using GUI, or assume Normal if missing.
    # To support CSVs without the column, default to Normal.
    # The Mode is packed into lower 4 bits of Byte 0.

    # Try to find Mode column. It might be named "Toggle_(CC/PB/Note/KeyMode)" or separate?
    # User asked for "Up and Down next to On/Off Value".
    # Let's look for "KeyMode_(Key)" column?
    # Or overload Toggle?
    # User said: "Up and Down ... selectable".
    # I will assume the column is named "KeyMode_(Key)".

    mode_nibble = 0
    # Check for KeyMode_(Key) in keys. Note that prefix is already stripped in pack_row.
    if "KeyMode_(Key)" in cmd:
        mode_nibble = _get_key_mode_nibble(str(cmd["KeyMode_(Key)"]))

    # Duration / Delay logic
    # Duration_(Note/PB) is shared.
    byte3_val = safe_int(cmd.get("Duration_(Note/PB)", 0)) & 0x7F

    # Toggle (Hold) logic: If Toggle is 'Y', we set MSB.
    # But for Keys, Toggle might be conflicting with Mode.
    # Firmware Priority: Toggle (Hold) > Mode (Momentary actions).
    # If user wants Hold, they check Toggle.

    toggle_bit = get_toggle_bit(str(cmd["Toggle_(CC/PB/Note)"]))

    cmd_bytes = [
        CMD_KEY_NIBBLE | mode_nibble,
        safe_int(cmd["Number_(PC/CC/Note)"])
        & 0xFF,  # Modifier logic (previously stored in Number?) Wait.
        # Original cmd_key: safe_int(cmd["Number_(PC/CC/Note)"]) & 0xFF -> Modifier
        # get_hid_code(cmd["OnValue_(CC/PB)"]) & 0xFF -> KeyCode
        get_hid_code(cmd.get("OnValue_(CC/PB)", "")) & 0xFF,  # KeyCode
        byte3_val | toggle_bit,  # Duration/Delay + Toggle
    ]
    return cmd_bytes


def cmd_stop(cmd):
    return [CMD_STOP_NIBBLE, 0, 0, 0]


def cmd_none(cmd):
    return [0, 0, 0, 0]


cmd_route_table = {
    "PC": cmd_pc,
    "CC": cmd_cc,
    "Note": cmd_note,
    "PB": cmd_pb,
    "Start": cmd_start,
    "Stop": cmd_stop,
    "Key": cmd_key,
}


def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text


def pack_row(row):
    row_byte_list = []

    # Check Light Mode for this button (row)
    # Default is Normal
    light_mode = "Normal"
    if "Light_Mode" in row:
        light_mode = str(row["Light_Mode"]).strip()

    for i in range(0, MIDI_NUM_COMMANDS_PER_SWITCH):
        cmd_prefix = f"{chr(ord('A') + i)}_"
        # Check if cmd exists in row columns
        # Filter columns starting with prefix
        current_cols = [c for c in row.index if c.startswith(cmd_prefix)]
        if not current_cols:
            # Should not happen given how logic works usually, but safety
            cmd_byte_list = cmd_none(None)
        else:
            cmd = row[current_cols]
            # Remove prefix from index to match cmd_xxx expectations
            cmd.index = cmd.index.str.replace(cmd_prefix, "", regex=False)

            func = cmd_route_table.get(cmd["CommandType"], cmd_none)
            cmd_byte_list = func(cmd)

        # Inject Light Mode bits into Slot A (i=0)
        # Using MSB of Byte 3 (index 2) and Byte 4 (index 3)
        # Byte 3 MSB -> Reverse
        # Byte 4 MSB -> Always On
        if i == 0 and len(cmd_byte_list) >= 4:
            if light_mode == "Reverse":
                cmd_byte_list[2] |= 0x80
            elif light_mode == "AlwaysOn":
                cmd_byte_list[3] |= 0x80

        row_byte_list += cmd_byte_list

    return row_byte_list
