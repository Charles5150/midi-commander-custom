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
CMD_MEDIA_NIBBLE = 0x30
CMD_BANK_NIBBLE = 0x40
CMD_CCINC_NIBBLE = 0x50
CMD_TAP_NIBBLE = 0x70
CMD_SYSEX_NIBBLE = 0x60
CMD_PANIC_NIBBLE = 0x80
CMD_SCENE_NIBBLE = 0xA0
# A pause shares the empty command type, marked by its low nibble, so a command
# of all zeroes stays an empty command. Byte 2 holds the pause in 10 ms units.
CMD_WAIT_MODE = 1
# A ramp too: it turns the CC command right below it into a ramp. Bytes 2 (low)
# and 3 (high) hold its time in 10 ms units.
CMD_RAMP_MODE = 2
RAMP_MAX_MS = 0xFFFF * 10
# And a cycle step: in a button's short press list, each one starts a new
# state, and every press sends the next state. Byte 1 is the state's label, an
# index into the configuration's cycle label table, or CYCLE_NO_LABEL to show
# the button's own label. The label text goes in OnValue in the CSV.
CMD_CYCLE_MODE = 3
CYCLE_NO_LABEL = 0x7F
CYCLE_LABEL_COUNT = 48
CYCLE_LABEL_LEN = 4
# And the split of a bank's enter list: the commands above it are sent on
# entering the bank, those below it on leaving it. The other bytes are 0.
CMD_LEAVE_MODE = 4
# And a change of what an expression pedal sends, until another one or a bank
# change. Byte 1 is the pedal (0 or 1) with the toggle bit, byte 2 the CC,
# EXP_TARGET_OFF to silence the pedal, EXP_TARGET_OWN to give it back its own
# target or EXP_TARGET_SPEED to set the speed of the LFOs and sequences, byte 3 the channel 1-16 or 0 for the pedal's own. A toggling one gives
# the pedal back its own target when switched off.
CMD_EXP_MODE = 5
EXP_TARGET_OFF = 0x80
EXP_TARGET_OWN = 0x81
EXP_TARGET_SPEED = 0x82
EXP_TARGETS = ["CC", "Off", "Own", "Speed"]
# And an LFO: turns the CC command right below it into an LFO locked to the
# tempo, swinging between its Off and On values. Byte 2 is the cycle length,
# an index into LFO_DIVISIONS, byte 3 the shape, an index into LFO_SHAPES.
CMD_LFO_MODE = 6
LFO_DIVISIONS = ["1/16T", "1/16", "1/8T", "1/8", "1/4T", "1/8.", "1/4", "1/2T",
                 "1/4.", "1/2", "1/2.", "1/1", "2/1", "4/1"]
LFO_DIV_TICKS = [4, 6, 8, 12, 16, 18, 24, 32, 36, 48, 72, 96, 192, 384]
LFO_SHAPES = ["Sine", "Triangle", "SawUp", "SawDown", "Square", "Random"]
# And MIDI Machine Control: a message to every device (F0 7F 7F 06 ... F7) for
# a recorder or a DAW. Byte 1 is the MMC command byte, and for Locate bytes 2
# (low 7 bits) and 3 (high 7 bits) hold the position in seconds.
CMD_MMC_MODE = 7
MMC_COMMANDS = {
    "Stop": 0x01,
    "Play": 0x02,
    "DeferredPlay": 0x03,
    "FastForward": 0x04,
    "Rewind": 0x05,
    "Record": 0x06,
    "RecordExit": 0x07,
    "Pause": 0x09,
    "Eject": 0x0A,
    "Chase": 0x0B,
    "Reset": 0x0D,
    "Locate": 0x44,
}
MMC_LOCATE = 0x44
MMC_LOCATE_MAX = 16383   # seconds, the largest the two value bytes hold
# And Song Select (F3) or Song Position Pointer (F2). Byte 1 says which, bytes
# 2 and 3 the value: the song number, or the position in sixteenth notes.
CMD_SONG_MODE = 8
SONG_SELECT, SONG_POSITION = 0, 1
SONG_MODES = ["Select", "Position"]
SONG_POSITION_MAX = 16383
# Chan: sends the command right below it on the channels it names. The sixteen
# channels are a bit each: byte 2 holds channels 1-7, byte 3 channels 8-14, and
# the two low bits of byte 1 channels 15 and 16.
CMD_CHAN_MODE = 9
CHAN_15_BIT = 0x01
CHAN_16_BIT = 0x02
# And a step sequencer: a run of Seq commands above a CC or Note command plays
# it one step at a time, locked to the tempo. Each command holds two steps, in
# bytes 2 and 3, a step being a value 0-127, SEQ_REST for one that sends
# nothing or SEQ_NO_STEP where the sequence ends. Byte 1 is how long a step
# lasts, an index into LFO_DIVISIONS, read from the first command of the run.
CMD_SEQ_MODE = 10
SEQ_REST = 0x80
SEQ_NO_STEP = 0xFF
SEQ_STEPS_PER_CMD = 2
SEQ_MAX_STEPS = 18
SEQ_DEFAULT_DIV = "1/8"
# Var: changes one of the eight values the pedal keeps of its own, 0-127 each
# and all zero when it powers on. Byte 1 is the value 0-7 with the mode in bits
# 4-5, byte 2 the amount and byte 3 the highest it goes, 0 standing for 127.
CMD_VAR_MODE = 11
VAR_MODES = ["Set", "Add", "Sub"]
VAR_COUNT = 8
VAR_DEFAULT_TOP = 127
# If: the command right below it only goes out when the test holds, and an If
# under another asks for both. Byte 1 is the test, an index into IF_TESTS, byte
# 2 the button or stored value it looks at, byte 3 what it is compared with.
CMD_IF_MODE = 12
IF_TESTS = ["Button on", "Button off", "Value =", "Value <>", "Value <",
            "Value >=", "Bank is", "Bank is not"]
IF_BUTTON_TESTS = (0, 1)
IF_VALUE_TESTS = (2, 3, 4, 5)
IF_BANK_TESTS = (6, 7)
# Macro: runs another button's command list in place, so a sequence wanted in
# many banks is stored once. Byte 1 is the bank, byte 2 the button in its low
# nibble and which of that button's lists in the high one.
CMD_MACRO_MODE = 13
MACRO_LISTS = ["Short", "Long", "Double"]
MACRO_DEPTH = 4
# Listen: sends nothing; the CC a device reports the list's state on, when it
# is not the one the list sends. Byte 1 is the CC, byte 2 the value meaning on
# and byte 3 the value meaning off; one arriving counts as the nearer of them.
CMD_LISTEN_MODE = 14

# A relative Program Change is a PC whose Bank Select MSB byte, where 0x80 and
# above already meant "none", holds one of these markers
PC_REL_UP = 0x81
PC_REL_DOWN = 0x82
# The same, also firing again while the button is held
PC_REL_UP_REPEAT = 0x83
PC_REL_DOWN_REPEAT = 0x84
PC_REL_MARKERS = (PC_REL_UP, PC_REL_DOWN, PC_REL_UP_REPEAT, PC_REL_DOWN_REPEAT)
# In the step byte of CCInc: fire again while the button is held
CCINC_REPEAT_BIT = 0x80
# Button order of a scene string, one character each: + on, - off, . leave
SCENE_BUTTONS = "1234ABCD"

# Bank command modes, packed in the low nibble of byte 0
BANK_MODES = {"GOTO": 0, "UP": 1, "DOWN": 2}

# USB HID Consumer Control usage IDs (usage page 0x0C) for media keys
MEDIA_KEYS = {
    "play_pause": 0xCD,
    "play": 0xB0,
    "pause": 0xB1,
    "stop": 0xB7,
    "next": 0xB5,
    "prev": 0xB6,
    "record": 0xB2,
    "fast_forward": 0xB3,
    "rewind": 0xB4,
    "eject": 0xB8,
    "mute": 0xE2,
    "vol_up": 0xE9,
    "vol_down": 0xEA,
}


# Standard command
# byte 1
# Upper 4 bits -> command types
# Lower 4 bits -> channel
# byte 2
# Most significant bit -> toggle control


# USB HID usage IDs for named keys (keyboard/keypad page). Shared with the
# unpacker so that names round-trip through the device.
HID_SPECIAL_KEYS = {
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

    if s_val.lower() in HID_SPECIAL_KEYS:
        return HID_SPECIAL_KEYS[s_val.lower()]

    # Fallback to raw int
    try:
        return int(float(s_val))
    except:
        return 0


def channel_nibble(val) -> int:
    """CSV channel 1-16 -> wire value 0-15. Empty or invalid defaults to channel 1."""
    ch = safe_int(val, 1)
    return min(max(ch, 1), 16) - 1


def get_toggle_bit(toggle_str):
    if not isinstance(toggle_str, str):
        return 0
    if "Y" in toggle_str:
        return 0x80
    else:
        return 0


# Program Change (or patch change) command, including back select
def cmd_pc(cmd):
    """Encode a Program Change, with Bank Select only when one is asked for.

    The firmware sends a Bank Select byte whenever its byte is below 0x80, so
    0x80 or above is the only way to say "send none". Writing 0 for an empty
    field, as this used to, made every Program Change send an unwanted
    Bank Select LSB of 0, which on some devices changes bank.
    """
    raw = str(cmd["BankSelect_(PC)"]).strip()
    if raw.lower() in ("", "nan", "none"):
        # No Bank Select at all: both bytes marked as absent
        return [
            CMD_PC_NIBBLE | channel_nibble(cmd["Channel_(PC/CC/Note/PB)"]),
            safe_int(cmd["Number_(PC/CC/Note)"]) & 0x7F,
            0x80,
            0xFF,
        ]

    bank_select_low = safe_int(cmd["BankSelect_(PC)"]) & 0x7F

    bs_high_str = str(cmd["BankSelectHighByte_(PC)"])
    if "Y" in bs_high_str:
        bank_select_high = (safe_int(cmd["BankSelect_(PC)"]) >> 7) & 0x7F
    else:
        bank_select_high = 0x80

    cmd_bytes = [
        CMD_PC_NIBBLE
        | channel_nibble(cmd["Channel_(PC/CC/Note/PB)"]),  # Command and channel
        safe_int(cmd["Number_(PC/CC/Note)"]) & 0x7F,  # Patch number
        bank_select_high,
        bank_select_low,
    ]

    return cmd_bytes


def cmd_cc(cmd):
    cmd_bytes = [
        CMD_CC_NIBBLE
        | channel_nibble(cmd["Channel_(PC/CC/Note/PB)"]),  # Command and channel
        safe_int(cmd["Number_(PC/CC/Note)"]) & 0x7F
        | get_toggle_bit(str(cmd["Toggle_(CC/PB/Note)"])),  # command number & toggle
        safe_int(cmd["OnValue_(CC/PB)"]) & 0x7F,
        safe_int(cmd["OffValue_(CC)"]),
    ]
    return cmd_bytes


def cmd_note(cmd):
    cmd_bytes = [
        CMD_NOTE_NIBBLE
        | channel_nibble(cmd["Channel_(PC/CC/Note/PB)"]),  # Command and channel
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
        | channel_nibble(cmd["Channel_(PC/CC/Note/PB)"]),  # Command and channel
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


def get_media_usage(val) -> int:
    s_val = str(val).strip().lower().replace(" ", "_").replace("-", "_")
    if s_val in MEDIA_KEYS:
        return MEDIA_KEYS[s_val]
    try:
        return int(s_val, 16) if s_val.startswith("0x") else int(float(s_val))
    except ValueError:
        return 0


def cmd_media(cmd):
    usage = get_media_usage(cmd.get("OnValue_(CC/PB)", "")) & 0x3FF
    duration = safe_int(cmd.get("Duration_(Note/PB)", 0)) & 0x7F
    toggle_bit = get_toggle_bit(str(cmd.get("Toggle_(CC/PB/Note)", "")))
    return [CMD_MEDIA_NIBBLE, usage & 0xFF, (usage >> 8) & 0x03, duration | toggle_bit]


TAP_MODE_TAP, TAP_MODE_CLOCK, TAP_MODE_SET, TAP_MODE_UP, TAP_MODE_DOWN = range(5)
TAP_REPEAT_BIT = 0x80
TEMPO_BPM_MIN, TEMPO_BPM_MAX = 30, 300


def cmd_tap(cmd):
    """Tap tempo. KeyMode picks the action: Tap, Clock to start/stop the
    clock, Set to set the tempo to OnValue BPM, or Up/Down to move it by
    OffValue BPM (1 when empty), with Repeat to keep moving while held."""
    text = str(cmd.get("KeyMode_(Key)", "")).strip().upper()
    if text.startswith("CLOCK"):
        return [CMD_TAP_NIBBLE | TAP_MODE_CLOCK, 0, 0, 0]
    if text.startswith("SET"):
        bpm = max(TEMPO_BPM_MIN, min(TEMPO_BPM_MAX, safe_int(cmd.get("OnValue_(CC/PB)", ""), 120)))
        return [CMD_TAP_NIBBLE | TAP_MODE_SET, 0, bpm & 0x7F, bpm >> 7]
    if text.startswith("UP") or text.startswith("DOWN"):
        down, repeat = inc_mode(cmd)
        step = max(1, min(127, safe_int(cmd.get("OffValue_(CC)", 1)) or 1))
        return [CMD_TAP_NIBBLE | (TAP_MODE_DOWN if down else TAP_MODE_UP), 0,
                step | (TAP_REPEAT_BIT if repeat else 0), 0]
    return [CMD_TAP_NIBBLE | TAP_MODE_TAP, 0, 0, 0]


def inc_mode(cmd):
    """Direction and auto-repeat of a CCInc or PCInc, from KeyMode such as
    "Up", "Down" or "Down Repeat"."""
    text = str(cmd.get("KeyMode_(Key)", "")).strip().upper()
    return text.startswith("DOWN"), "REPEAT" in text


def cmd_ccinc(cmd):
    """Relative CC: each press moves the value by a step.

    OnValue is the starting value, OffValue the step, KeyMode the direction
    (Up/Down, with Repeat to fire again while held) and Toggle enables
    wrapping past the ends.
    """
    start = max(0, min(127, safe_int(cmd.get("OnValue_(CC/PB)", 0))))
    step = max(1, min(127, safe_int(cmd.get("OffValue_(CC)", 1)) or 1))
    down, repeat = inc_mode(cmd)
    wrap = get_toggle_bit(str(cmd.get("Toggle_(CC/PB/Note)", ""))) != 0
    return [
        CMD_CCINC_NIBBLE | channel_nibble(cmd["Channel_(PC/CC/Note/PB)"]),
        (safe_int(cmd["Number_(PC/CC/Note)"]) & 0x7F) | (0x80 if wrap else 0),
        step | (CCINC_REPEAT_BIT if repeat else 0),
        (0x80 if down else 0) | start,
    ]


def cmd_pcinc(cmd):
    """Relative Program Change: next or previous preset.

    Moves from the program last sent on the channel. OffValue is the step,
    Number the last program in the range (127 when empty), KeyMode the
    direction (Up/Down, with Repeat to fire again while held) and Toggle
    wraps round at the ends instead of stopping.
    """
    step = max(1, min(127, safe_int(cmd.get("OffValue_(CC)", 1)) or 1))
    top = max(0, min(127, safe_int(cmd.get("Number_(PC/CC/Note)", ""), 127)))
    down, repeat = inc_mode(cmd)
    wrap = get_toggle_bit(str(cmd.get("Toggle_(CC/PB/Note)", ""))) != 0
    return [
        CMD_PC_NIBBLE | channel_nibble(cmd["Channel_(PC/CC/Note/PB)"]),
        step,
        PC_REL_MARKERS[(1 if down else 0) + (2 if repeat else 0)],
        (0x80 if wrap else 0) | top,
    ]


def cmd_sysex(cmd):
    """Send a stored SysEx string. Number selects the table entry."""
    index = max(0, min(15, safe_int(cmd.get("Number_(PC/CC/Note)", 0))))
    return [CMD_SYSEX_NIBBLE, index, 0, 0]


def cmd_bank(cmd):
    """Bank change, or configuration switch.

    GoTo: OnValue is the bank. Up/Down: OnValue is the step. Config: OnValue is
    the configuration slot 1-4. NextConfig: moves to the next slot holding a
    configuration, no value. Page: OnValue is the bank shown as this bank's
    second page; pressed again, or on the page, it goes back. Back: returns to
    the bank left by the last bank change, no value.
    """
    mode_text = str(cmd.get("KeyMode_(Key)", "")).strip().upper().replace(" ", "")
    if mode_text.startswith("BACK"):
        return [CMD_BANK_NIBBLE | 6, 0, 0, 0]
    if mode_text.startswith("PAGE"):
        bank = max(0, min(31, safe_int(cmd.get("OnValue_(CC/PB)", 0))))
        return [CMD_BANK_NIBBLE | 5, bank, 0, 0]
    if mode_text.startswith("NEXT"):
        return [CMD_BANK_NIBBLE | 4, 0, 0, 0]
    if mode_text.startswith("CONFIG"):
        slot = max(1, min(4, safe_int(cmd.get("OnValue_(CC/PB)", 1)) or 1))
        return [CMD_BANK_NIBBLE | 3, slot - 1, 0, 0]
    mode = 1 if mode_text.startswith("UP") else 2 if mode_text.startswith("DOWN") else 0
    value = safe_int(cmd.get("OnValue_(CC/PB)", 0))
    if mode == 0:
        value = max(0, min(31, value))       # absolute bank number
    else:
        value = max(1, min(31, value or 1))  # relative step
    return [CMD_BANK_NIBBLE | mode, value, 0, 0]


def cmd_stop(cmd):
    return [CMD_STOP_NIBBLE, 0, 0, 0]


def cmd_panic(cmd):
    """All Sound Off and All Notes Off on every channel; no parameters."""
    return [CMD_PANIC_NIBBLE, 0, 0, 0]


def cmd_scene(cmd):
    """A scene string such as "+-+..-.." in OnValue: one character per button
    in SCENE_BUTTONS order, + to switch it on, - off, anything else to leave
    it. Byte 1 holds the buttons affected, byte 2 the states wanted."""
    text = str(cmd.get("OnValue_(CC/PB)", "")).strip()
    if text.lower() == "nan":
        text = ""
    mask = states = 0
    for i, ch in enumerate(text[:len(SCENE_BUTTONS)]):
        if ch == "+":
            mask |= 1 << i
            states |= 1 << i
        elif ch == "-":
            mask |= 1 << i
    return [CMD_SCENE_NIBBLE, mask, states, 0]


def cmd_wait(cmd):
    """Pause before the rest of the button's commands.

    Duration is the pause in milliseconds, stored in steps of 10 ms, so the
    longest pause is 2550 ms.
    """
    ms = safe_int(cmd.get("Duration_(Note/PB)", 0))
    return [CMD_NO_CMD_NIBBLE | CMD_WAIT_MODE, 0, max(0, min(255, round(ms / 10))), 0]


def cmd_ramp(cmd):
    """Turn the CC command right below into a ramp.

    Duration is the ramp time in milliseconds, stored in steps of 10 ms, so the
    longest ramp is RAMP_MAX_MS. The CC walks to its On value over that time on
    the press, and back to its Off value on the release or when a toggle is
    switched off.
    """
    ms = max(0, min(RAMP_MAX_MS, safe_int(cmd.get("Duration_(Note/PB)", 0))))
    steps = round(ms / 10)
    return [CMD_NO_CMD_NIBBLE | CMD_RAMP_MODE, 0, steps & 0xFF, (steps >> 8) & 0xFF]


def cmd_lfo(cmd):
    """Turn the CC command right below into an LFO locked to the tempo.

    OnValue is the length of one cycle as a note division (LFO_DIVISIONS, "1/4"
    when empty), KeyMode the shape (LFO_SHAPES, Sine when empty).
    """
    div = str(cmd.get("OnValue_(CC/PB)", "")).strip()
    if div in ("", "nan"):
        div = "1/4"
    if div not in LFO_DIVISIONS:
        raise ValueError(f"LFO division must be one of {', '.join(LFO_DIVISIONS)}, not {div!r}")
    shape = str(cmd.get("KeyMode_(Key)", "")).strip()
    if shape in ("", "nan"):
        shape = "Sine"
    shapes = {s.upper(): i for i, s in enumerate(LFO_SHAPES)}
    if shape.upper() not in shapes:
        raise ValueError(f"LFO shape must be one of {', '.join(LFO_SHAPES)}, not {shape!r}")
    return [CMD_NO_CMD_NIBBLE | CMD_LFO_MODE, 0, LFO_DIVISIONS.index(div), shapes[shape.upper()]]


def cmd_exp(cmd):
    """Point an expression pedal somewhere else.

    OnValue is the pedal, 1 or 2. KeyMode says where to: CC (the default) sends
    it to CC Number, on Channel if one is given or else on the pedal's own;
    Off silences it; Own gives it back its own target; Speed makes it set how
    fast the LFOs and sequences go.
    """
    pedal = safe_int(cmd.get("OnValue_(CC/PB)"), 1)
    if pedal not in (1, 2):
        raise ValueError(f"Exp pedal must be 1 or 2, not {cmd.get('OnValue_(CC/PB)')!r}")
    target = str(cmd.get("KeyMode_(Key)", "")).strip().upper()
    if target in ("", "NAN", "CC"):
        cc = safe_int(cmd.get("Number_(PC/CC/Note)"), -1)
        if not 0 <= cc <= 127:
            raise ValueError(f"Exp needs a CC number 0-127, not {cmd.get('Number_(PC/CC/Note)')!r}")
    elif target == "OFF":
        cc = EXP_TARGET_OFF
    elif target == "OWN":
        cc = EXP_TARGET_OWN
    elif target == "SPEED":
        cc = EXP_TARGET_SPEED
    else:
        raise ValueError(f"Exp target must be CC, Off, Own or Speed, not {cmd.get('KeyMode_(Key)')!r}")
    channel = 0
    ch = str(cmd.get("Channel_(PC/CC/Note/PB)", "")).strip().upper()
    if cc < 0x80 and ch not in ("", "NAN", "OWN"):
        channel = safe_int(ch, 0)
        if not 1 <= channel <= 16:
            raise ValueError(f"Exp channel must be empty or 1-16, not {ch!r}")
    toggle = get_toggle_bit(str(cmd.get("Toggle_(CC/PB/Note)", "")))
    return [CMD_NO_CMD_NIBBLE | CMD_EXP_MODE, (pedal - 1) | toggle, cc, channel]


def cmd_mmc(cmd):
    """MIDI Machine Control, to every device on the wire.

    KeyMode is the action, one of MMC_COMMANDS: Play, Stop, Record, Pause and
    the rest. Locate takes OnValue, where to go in seconds from the start.
    """
    text = str(cmd.get("KeyMode_(Key)", "")).strip().replace(" ", "")
    if text.lower() in ("", "nan"):
        text = "Play"
    names = {k.upper(): v for k, v in MMC_COMMANDS.items()}
    if text.upper() not in names:
        raise ValueError(f"MMC action must be one of {', '.join(MMC_COMMANDS)}, not {text!r}")
    command = names[text.upper()]
    seconds = 0
    if command == MMC_LOCATE:
        seconds = max(0, min(MMC_LOCATE_MAX, safe_int(cmd.get("OnValue_(CC/PB)", 0))))
    return [CMD_NO_CMD_NIBBLE | CMD_MMC_MODE, command, seconds & 0x7F, (seconds >> 7) & 0x7F]


def cmd_song(cmd):
    """Song Select or Song Position Pointer, neither of them on a channel.

    KeyMode picks which: Select sends the song number in OnValue, 0-127;
    Position sends where to start it, in sixteenth notes from the beginning.
    """
    text = str(cmd.get("KeyMode_(Key)", "")).strip().upper()
    which = SONG_POSITION if text.startswith("POS") else SONG_SELECT
    top = SONG_POSITION_MAX if which == SONG_POSITION else 127
    value = max(0, min(top, safe_int(cmd.get("OnValue_(CC/PB)", 0))))
    return [CMD_NO_CMD_NIBBLE | CMD_SONG_MODE, which, value & 0x7F, (value >> 7) & 0x7F]


def parse_channel_list(text) -> int:
    """The channels of a Chan command as a bit mask, bit 0 being channel 1.

    The cell holds them in any readable form: "1 2 3", "1,2,3" or "1-3".
    """
    text = str("" if text is None else text).strip()
    if text.lower() in ("", "nan"):
        return 0
    mask = 0
    for part in text.replace(",", " ").replace(";", " ").split():
        if "-" in part[1:]:
            first, last = part.split("-", 1)
            span = range(safe_int(first), safe_int(last) + 1)
        else:
            span = [safe_int(part)]
        for channel in span:
            if not 1 <= channel <= 16:
                raise ValueError(f"Chan channels must be 1-16, not {part!r}")
            mask |= 1 << (channel - 1)
    return mask


def channel_list_text(mask: int) -> str:
    """The channels of a Chan command back as text, "1 2 3"."""
    return " ".join(str(c + 1) for c in range(16) if mask & (1 << c))


def cmd_chan(cmd):
    """Send the command right below this one on several channels.

    Channel holds the list, "1 2 3" or "1-3". The command below goes out once
    per channel, whatever channel of its own it carries, and whatever the
    configuration's global channel says.
    """
    mask = parse_channel_list(cmd.get("Channel_(PC/CC/Note/PB)"))
    if mask == 0:
        raise ValueError("Chan needs a channel list, like 1 2 3")
    byte1 = 0
    if mask & (1 << 14):
        byte1 |= CHAN_15_BIT
    if mask & (1 << 15):
        byte1 |= CHAN_16_BIT
    return [CMD_NO_CMD_NIBBLE | CMD_CHAN_MODE, byte1, mask & 0x7F, (mask >> 7) & 0x7F]


def parse_steps(text) -> list:
    """The steps of one Seq command: values 0-127, or "-" for a silent step."""
    text = str("" if text is None else text).strip()
    if text.lower() in ("", "nan"):
        return []
    steps = []
    for part in text.replace(",", " ").replace(";", " ").split():
        if part in ("-", "_", "."):
            steps.append(SEQ_REST)
            continue
        value = safe_int(part, -1)
        if not 0 <= value <= 127:
            raise ValueError(f"Seq steps are 0-127, or - for a rest, not {part!r}")
        steps.append(value)
    if len(steps) > SEQ_STEPS_PER_CMD:
        raise ValueError(
            f"A Seq command holds {SEQ_STEPS_PER_CMD} steps; put the rest in the next one"
        )
    return steps


def steps_text(values) -> str:
    """The steps of a Seq command back as text, "100 -"."""
    return " ".join("-" if v == SEQ_REST else str(v) for v in values if v != SEQ_NO_STEP)


def cmd_seq(cmd):
    """Play the CC or Note command below the run of Seq commands step by step.

    OnValue holds this command's two steps, "100 -", and KeyMode how long a
    step lasts as a note division (LFO_DIVISIONS, "1/8" when empty), which
    only the first command of the run is asked for.
    """
    steps = parse_steps(cmd.get("OnValue_(CC/PB)"))
    div = str(cmd.get("KeyMode_(Key)", "")).strip()
    if div in ("", "nan"):
        div = SEQ_DEFAULT_DIV
    if div not in LFO_DIVISIONS:
        raise ValueError(f"Seq step must be one of {', '.join(LFO_DIVISIONS)}, not {div!r}")
    steps = steps + [SEQ_NO_STEP] * (SEQ_STEPS_PER_CMD - len(steps))
    return [CMD_NO_CMD_NIBBLE | CMD_SEQ_MODE, LFO_DIVISIONS.index(div), steps[0], steps[1]]


def cycle_label_text(value) -> str:
    """A Cycle command's label as stored: at most 4 ASCII characters."""
    text = "" if value is None else str(value)
    if text.strip().lower() == "nan":
        text = ""
    return text.strip()[:CYCLE_LABEL_LEN].encode("ascii", errors="replace").decode("ascii")


def cmd_cycle(cmd, cycle_labels):
    """Start the next state of a cycle button.

    ``cycle_labels`` is the configuration's label table, a list the label is
    looked up in and added to when new, so a label used on many buttons is
    stored once. None means the list being packed cannot hold states.
    """
    if cycle_labels is None:
        raise ValueError("Cycle commands only work in a button's short press list")
    label = cycle_label_text(cmd.get("OnValue_(CC/PB)", ""))
    if label == "":
        return [CMD_NO_CMD_NIBBLE | CMD_CYCLE_MODE, CYCLE_NO_LABEL, 0, 0]
    if label not in cycle_labels:
        if len(cycle_labels) >= CYCLE_LABEL_COUNT:
            raise ValueError(f"Too many different cycle labels, at most {CYCLE_LABEL_COUNT}")
        cycle_labels.append(label)
    return [CMD_NO_CMD_NIBBLE | CMD_CYCLE_MODE, cycle_labels.index(label), 0, 0]


def pack_cycle_labels(cycle_labels) -> bytes:
    """The cycle label table: used entries space padded, the rest erased."""
    out = b"".join(l.encode("ascii").ljust(CYCLE_LABEL_LEN, b" ") for l in cycle_labels)
    return out.ljust(CYCLE_LABEL_COUNT * CYCLE_LABEL_LEN, b"\xff")


def button_index(val) -> int:
    """A button as the CSV names it, "1"-"4" and "A"-"D" or 1-8, counted from 0."""
    text = str("" if val is None else val).strip().upper()
    if text in ("", "NAN"):
        return 0
    if text in SCENE_BUTTONS:
        return SCENE_BUTTONS.index(text)
    return max(0, min(len(SCENE_BUTTONS) - 1, safe_int(text, 1) - 1))


def button_name(index: int) -> str:
    """The button back as the CSV names it, "1" or "A"."""
    return SCENE_BUTTONS[index % len(SCENE_BUTTONS)]


def cmd_var(cmd):
    """Change one of the eight values the pedal keeps of its own.

    Number is the value 1-8, KeyMode what to do with it (VAR_MODES, Set when
    empty), OnValue the amount, and OffValue the highest it goes, 127 when
    empty: adding past it starts again at zero, taking away past zero starts
    again at it. The values start at zero when the pedal powers on.
    """
    which = max(1, min(VAR_COUNT, safe_int(cmd.get("Number_(PC/CC/Note)", 1) or 1))) - 1
    mode_text = str(cmd.get("KeyMode_(Key)", "")).strip()
    if mode_text in ("", "nan"):
        mode_text = VAR_MODES[0]
    modes = {m.upper(): i for i, m in enumerate(VAR_MODES)}
    if mode_text.upper() not in modes:
        raise ValueError(f"Value command must be one of {', '.join(VAR_MODES)}, not {mode_text!r}")
    amount = max(0, min(127, safe_int(cmd.get("OnValue_(CC/PB)", 0))))
    top = str(cmd.get("OffValue_(CC)", "")).strip()
    top = VAR_DEFAULT_TOP if top in ("", "nan") else max(0, min(127, safe_int(top, VAR_DEFAULT_TOP)))
    return [CMD_NO_CMD_NIBBLE | CMD_VAR_MODE,
            (modes[mode_text.upper()] << 4) | which, amount, top]


def cmd_if(cmd):
    """Hold back the command right below unless the test holds.

    KeyMode is the test (IF_TESTS), Number the button ("1"-"4", "A"-"D") or the
    stored value 1-8 it looks at, and OnValue what it is compared with: a value
    0-127, or the bank for the bank tests. An If under another asks for both,
    and the test is made again on the release, so a momentary command held back
    is not sent its Off value either.
    """
    test_text = str(cmd.get("KeyMode_(Key)", "")).strip()
    if test_text in ("", "nan"):
        test_text = IF_TESTS[0]
    tests = {t.upper(): i for i, t in enumerate(IF_TESTS)}
    if test_text.upper() not in tests:
        raise ValueError(f"If must be one of {', '.join(IF_TESTS)}, not {test_text!r}")
    test = tests[test_text.upper()]
    what = value = 0
    if test in IF_BUTTON_TESTS:
        what = button_index(cmd.get("Number_(PC/CC/Note)", "1"))
    elif test in IF_VALUE_TESTS:
        what = max(1, min(VAR_COUNT, safe_int(cmd.get("Number_(PC/CC/Note)", 1) or 1))) - 1
        value = max(0, min(127, safe_int(cmd.get("OnValue_(CC/PB)", 0))))
    else:
        value = max(0, min(31, safe_int(cmd.get("OnValue_(CC/PB)", 0))))
    return [CMD_NO_CMD_NIBBLE | CMD_IF_MODE, test, what, value]


def cmd_macro(cmd):
    """Run another button's command list in place.

    OnValue is the bank 0-31 the list lives in, Number the button ("1"-"4",
    "A"-"D") and KeyMode which of that button's lists (MACRO_LISTS, its short
    press list when empty). The called list runs with the toggle state of the
    button that called it, and macros call macros up to MACRO_DEPTH lists deep;
    a list already running is never called again, so one cannot go round for
    ever.
    """
    bank = max(0, min(31, safe_int(cmd.get("OnValue_(CC/PB)", 0))))
    button = button_index(cmd.get("Number_(PC/CC/Note)", "1"))
    list_text = str(cmd.get("KeyMode_(Key)", "")).strip()
    if list_text in ("", "nan"):
        list_text = MACRO_LISTS[0]
    lists = {m.upper(): i for i, m in enumerate(MACRO_LISTS)}
    if list_text.upper() not in lists:
        raise ValueError(f"Macro must be one of {', '.join(MACRO_LISTS)}, not {list_text!r}")
    return [CMD_NO_CMD_NIBBLE | CMD_MACRO_MODE, bank,
            (lists[list_text.upper()] << 4) | button, 0]


def cmd_listen(cmd):
    """The CC a device reports this list's state on.

    Number is the CC, OnValue the value meaning on (127 when empty) and
    OffValue the value meaning off (0 when empty); a value arriving counts as
    whichever of the two it is nearer. The list's toggle then follows that CC
    alone, on the channel of its first toggling command, with LED_Feedback on
    or off.
    """
    number = max(0, min(127, safe_int(cmd.get("Number_(PC/CC/Note)", 0))))
    on_text = str(cmd.get("OnValue_(CC/PB)", "")).strip()
    off_text = str(cmd.get("OffValue_(CC)", "")).strip()
    on = 127 if on_text in ("", "nan") else max(0, min(127, safe_int(on_text)))
    off = 0 if off_text in ("", "nan") else max(0, min(127, safe_int(off_text)))
    return [CMD_NO_CMD_NIBBLE | CMD_LISTEN_MODE, number, on, off]


def cmd_none(cmd):
    return [0, 0, 0, 0]


cmd_route_table = {
    "PC": cmd_pc,
    "CC": cmd_cc,
    "Note": cmd_note,
    "PB": cmd_pb,
    "Start": cmd_start,
    "Stop": cmd_stop,
    "Panic": cmd_panic,
    "Scene": cmd_scene,
    "Key": cmd_key,
    "Media": cmd_media,
    "Bank": cmd_bank,
    "CCInc": cmd_ccinc,
    "PCInc": cmd_pcinc,
    "Tap": cmd_tap,
    "SysEx": cmd_sysex,
    "Wait": cmd_wait,
    "Ramp": cmd_ramp,
    "Exp": cmd_exp,
    "LFO": cmd_lfo,
    "MMC": cmd_mmc,
    "Song": cmd_song,
    "Chan": cmd_chan,
    "Seq": cmd_seq,
    "Value": cmd_var,
    "If": cmd_if,
    "Macro": cmd_macro,
    "Listen": cmd_listen,
}


def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text


# Button LED modes. Stored in a separate table after the command area, one
# byte per button indexed by (bank * 8 + button). Kept out of the command
# bytes so they can never corrupt a command.
LED_MODE_VALUES = {"NORMAL": 0, "REVERSE": 1, "ALWAYSON": 2}
LED_MODE_NAMES = {v: k.title() if k != "ALWAYSON" else "AlwaysOn" for k, v in LED_MODE_VALUES.items()}


def led_mode_value(name) -> int:
    s = str(name).strip().upper().replace(" ", "").replace("_", "")
    if s in ("", "NAN"):
        return 0
    if "REVERSE" in s:
        return 1
    if "ALWAYS" in s:
        return 2
    return LED_MODE_VALUES.get(s, 0)


# The top bits of the same byte hold the button's exclusive group, 0 for none:
# switching on a toggle button of a group switches off the others of the group
# in its bank. Older configurations always left them at zero.
BUTTON_GROUP_SHIFT = 4
BUTTON_GROUP_MAX = 4


def button_group_value(value) -> int:
    """Group number 1..BUTTON_GROUP_MAX from a CSV cell; empty or None is 0."""
    s = str(value).strip().upper()
    if s in ("", "NAN", "NONE", "0"):
        return 0
    try:
        g = int(float(s))
    except ValueError:
        raise ValueError(f"Group must be empty or 1-{BUTTON_GROUP_MAX}, not {value!r}")
    if not 0 <= g <= BUTTON_GROUP_MAX:
        raise ValueError(f"Group must be empty or 1-{BUTTON_GROUP_MAX}, not {value!r}")
    return g


# Bit 2: the LED flashes at the tempo, as a Tap button's does. Older
# configurations always left it at zero.
BUTTON_TEMPO_FLASH = 0x04


def tempo_flash_value(value) -> bool:
    """Tempo_Flash cell: Y/Yes/1/True is on, empty, N or None is off."""
    return _yes_no(value, "Tempo_Flash")


# Bit 3: global. The button takes its three command lists, its label and its
# light from the same button of the bank named by Global_Bank, so the thing is
# stored once and a change to it is a change in every bank that follows it.
BUTTON_GLOBAL = 0x08


def button_global_value(value) -> bool:
    """Global cell: Y/Yes/1/True is on, empty, N or None is off."""
    return _yes_no(value, "Global")


# Bit 7: momentary when held. A toggle button held past Long_Press_ms goes
# back to its previous state when released; a tap still latches it.
BUTTON_MOMENTARY_HOLD = 0x80


def _yes_no(value, column) -> bool:
    """A Y/N cell: Y/Yes/1/True is on, empty, N or None is off."""
    s = str(value).strip().upper()
    if s in ("", "NAN", "NONE", "N", "NO", "0", "0.0", "FALSE"):
        return False
    if s in ("Y", "YES", "1", "1.0", "TRUE"):
        return True
    raise ValueError(f"{column} must be empty, Y or N, not {value!r}")


def momentary_hold_value(value) -> bool:
    """Momentary_Hold cell: Y/Yes/1/True is on, empty, N or None is off."""
    return _yes_no(value, "Momentary_Hold")


def reset_on_bank_value(value) -> bool:
    """Reset_On_Bank cell: Y/Yes/1/True is on, empty, N or None is off. Kept
    in the button's label, see configPacker.LABEL_RESET_BIT."""
    return _yes_no(value, "Reset_On_Bank")


def pack_button_led_modes(light_modes, groups=None, holds=None, flashes=None,
                          globals_=None) -> list:
    """Pack one LED mode byte per button from an iterable of mode names, with
    the exclusive group of each button, if given, in bits 4-6, its momentary
    hold, if given, in bit 7, its tempo flash, if given, in bit 2, and whether
    it is a global button, if given, in bit 3."""
    modes = [led_mode_value(m) for m in light_modes]
    if groups is not None:
        modes = [m | (button_group_value(g) << BUTTON_GROUP_SHIFT) for m, g in zip(modes, groups)]
    if holds is not None:
        modes = [m | (BUTTON_MOMENTARY_HOLD if momentary_hold_value(h) else 0) for m, h in zip(modes, holds)]
    if flashes is not None:
        modes = [m | (BUTTON_TEMPO_FLASH if tempo_flash_value(f) else 0) for m, f in zip(modes, flashes)]
    if globals_ is not None:
        modes = [m | (BUTTON_GLOBAL if button_global_value(g) else 0) for m, g in zip(modes, globals_)]
    return modes


def pack_row(row, cycle_labels=None, leave=False):
    """Pack a row's command list. ``cycle_labels`` is the configuration's
    cycle label table, for a short press list, where Cycle commands belong.
    ``leave`` allows one Leave command, for a bank's enter list."""
    row_byte_list = []
    leaves = 0
    # A plain dict per command: building a pandas Series for each of them made
    # packing a whole configuration take a second
    fields = row.to_dict() if hasattr(row, "to_dict") else dict(row)

    for i in range(0, MIDI_NUM_COMMANDS_PER_SWITCH):
        cmd_prefix = f"{chr(ord('A') + i)}_"
        cmd = {c[len(cmd_prefix):]: v for c, v in fields.items()
               if isinstance(c, str) and c.startswith(cmd_prefix)}
        if not cmd:
            # Should not happen given how logic works usually, but safety
            cmd_byte_list = cmd_none(None)
        else:

            cmd_type = str(cmd["CommandType"]).strip()
            if cmd_type == "Cycle":
                cmd_byte_list = cmd_cycle(cmd, cycle_labels)
            elif cmd_type == "Leave":
                if not leave:
                    raise ValueError("Leave commands only work in a bank's enter list")
                leaves += 1
                if leaves > 1:
                    raise ValueError("A bank's enter list takes a single Leave command")
                cmd_byte_list = [CMD_NO_CMD_NIBBLE | CMD_LEAVE_MODE, 0, 0, 0]
            else:
                cmd_byte_list = cmd_route_table.get(cmd_type, cmd_none)(cmd)

        row_byte_list += cmd_byte_list

    return row_byte_list
