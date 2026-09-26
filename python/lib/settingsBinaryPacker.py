GLOBAL_SETTINGS_CHANNEL = 0
GLOBAL_SETTINGS_REALTIME_PASS = 1
GLOBAL_SETTINGS_EXP1_CC = 2
GLOBAL_SETTINGS_EXP2_CC = 3
GLOBAL_SETTINGS_USB_THRU = 6
GLOBAL_SETTINGS_REMEMBER_STATE = 7
GLOBAL_SETTINGS_LONG_PRESS = 8
GLOBAL_SETTINGS_LED_BRIGHTNESS = 9
GLOBAL_SETTINGS_LED_REST_BRIGHTNESS = 10
GLOBAL_SETTINGS_BANK_JUMP_STEP = 11
GLOBAL_SETTINGS_BANK_CHANGE_MODE = 12
GLOBAL_SETTINGS_BANK_CHANGE_CHANNEL = 13
GLOBAL_SETTINGS_BANK_CHANGE_CC = 14
GLOBAL_SETTINGS_BANK_SWITCH_MODE = 15
# 16..31 hold ConfigName, so new settings start at 32
GLOBAL_SETTINGS_SLEEP_AFTER_MIN = 32
GLOBAL_SETTINGS_SETLIST_MODE = 33
GLOBAL_SETTINGS_CLOCK_FOLLOW = 34
GLOBAL_SETTINGS_LED_FEEDBACK = 35
GLOBAL_SETTINGS_DOUBLE_PRESS = 36
GLOBAL_SETTINGS_REMOTE_MODE = 38
GLOBAL_SETTINGS_REMOTE_CHANNEL = 39
GLOBAL_SETTINGS_REMOTE_FIRST = 40
GLOBAL_SETTINGS_GLOBAL_CHANNEL = 41
GLOBAL_SETTINGS_EDIT_LOCK = 42
GLOBAL_SETTINGS_KEMPER_MODE = 43
GLOBAL_SETTINGS_GLOBAL_BANK = 44
GLOBAL_SETTINGS_COMBO = 45
GLOBAL_SETTINGS_BANNER = 46
GLOBAL_SETTINGS_BANK_PREVIEW = 47
BANK_PREVIEW_MAX_S = 60
# Set by configPacker when the image carries double press commands
GLOBAL_SETTINGS_DOUBLE_STORED = 37

BANK_SWITCH_MODES = {"BANK": 0, "BANK+MIDI": 1, "MIDI": 2}

BANK_CHANGE_MODES = {"OFF": 0, "PC": 1, "CC": 2}
REMOTE_MODES = {"OFF": 0, "CC": 1, "NOTE": 2}
BANNER_SPEEDS = {"OFF": 0, "SLOW": 1, "NORMAL": 2, "FAST": 3}

def pack_global_settings(df):
    # global settings will be 32 bytes long
    bin_list = [0] * 16
    # MIDI_Channel is 1-16 in the CSV (same convention as per-command
    # channels); the firmware expects the 0-15 wire value.
    midi_channel = int(df.loc["MIDI_Channel", "Value"])
    midi_channel = min(max(midi_channel, 1), 16)
    bin_list[GLOBAL_SETTINGS_CHANNEL] = (midi_channel - 1) & 0xF
    if "Y" in df.loc["RealTime_Passthrough", "Value"]:
        bin_list[GLOBAL_SETTINGS_REALTIME_PASS] = 0x1
    
    # Pack Expression Pedal CC numbers if present in CSV
    if "Exp1_CC" in df.index:
        bin_list[GLOBAL_SETTINGS_EXP1_CC] = int(df.loc["Exp1_CC", "Value"]) & 0x7F
    else:
        bin_list[GLOBAL_SETTINGS_EXP1_CC] = 11 # Default to CC 11 if missing

    if "Exp2_CC" in df.index:
        bin_list[GLOBAL_SETTINGS_EXP2_CC] = int(df.loc["Exp2_CC", "Value"]) & 0x7F
    else:
        bin_list[GLOBAL_SETTINGS_EXP2_CC] = 4  # Default to CC 4 if missing

    # Bank LED Modes (Index 4, 5)
    # 0=Normal, 1=Reverse, 2=AlwaysOn(Blink)
    GLOBAL_SETTINGS_BANK_UP_LED = 4
    GLOBAL_SETTINGS_BANK_DOWN_LED = 5
    
    def get_led_mode(val):
        s = str(val).upper()
        if "REVERSE" in s: return 1
        if "ALWAYS" in s: return 2
        return 0

    if "Bank_Up_LED_Mode" in df.index:
        bin_list[GLOBAL_SETTINGS_BANK_UP_LED] = get_led_mode(df.loc["Bank_Up_LED_Mode", "Value"])
    
    if "Bank_Down_LED_Mode" in df.index:
        bin_list[GLOBAL_SETTINGS_BANK_DOWN_LED] = get_led_mode(df.loc["Bank_Down_LED_Mode", "Value"])

    # USB to DIN thru: forward channel/system common/foreign SysEx (Y/N)
    if "USB_MIDI_Thru" in df.index and "Y" in str(df.loc["USB_MIDI_Thru", "Value"]).upper():
        bin_list[GLOBAL_SETTINGS_USB_THRU] = 0x1

    # Restore last bank and toggle states at power on (Y/N)
    if "Remember_State" in df.index and "Y" in str(df.loc["Remember_State", "Value"]).upper():
        bin_list[GLOBAL_SETTINGS_REMEMBER_STATE] = 0x1

    # Long press threshold in ms, stored in 10 ms units (10..2500 ms)
    long_ms = 500
    if "Long_Press_ms" in df.index:
        try:
            long_ms = int(float(str(df.loc["Long_Press_ms", "Value"])))
        except ValueError:
            long_ms = 500
    bin_list[GLOBAL_SETTINGS_LONG_PRESS] = max(1, min(250, round(long_ms / 10)))

    # LED brightness in percent (1-100); lit LEDs and LEDs lit at rest.
    # 0 is reserved: the firmware reads it as "not set" (older configs).
    def percent(label, default=100):
        if label not in df.index:
            return default
        try:
            return max(1, min(100, int(float(str(df.loc[label, "Value"])))))
        except ValueError:
            return default
    bin_list[GLOBAL_SETTINGS_LED_BRIGHTNESS] = percent("LED_Brightness")
    bin_list[GLOBAL_SETTINGS_LED_REST_BRIGHTNESS] = percent("LED_Rest_Brightness")

    # Banks skipped by a long press on Bank Up/Down
    step = 8
    if "Bank_Jump_Step" in df.index:
        try:
            step = int(float(str(df.loc["Bank_Jump_Step", "Value"])))
        except ValueError:
            step = 8
    bin_list[GLOBAL_SETTINGS_BANK_JUMP_STEP] = max(1, min(31, step))

    # Let an incoming Program Change or Control Change select a bank
    mode_text = str(df.loc["Bank_Change_Mode", "Value"]).strip().upper() if "Bank_Change_Mode" in df.index else "OFF"
    mode = BANK_CHANGE_MODES.get(mode_text[:2], 0) if mode_text[:2] in ("PC", "CC") else 0
    bin_list[GLOBAL_SETTINGS_BANK_CHANGE_MODE] = mode

    ch_text = str(df.loc["Bank_Change_Channel", "Value"]).strip() if "Bank_Change_Channel" in df.index else "Any"
    if ch_text.upper().startswith("A") or ch_text == "":
        channel = 0
    else:
        try:
            channel = max(0, min(16, int(float(ch_text))))
        except ValueError:
            channel = 0
    bin_list[GLOBAL_SETTINGS_BANK_CHANGE_CHANNEL] = channel

    cc = 0
    if "Bank_Change_CC" in df.index:
        try:
            cc = max(0, min(127, int(float(str(df.loc["Bank_Change_CC", "Value"])))))
        except ValueError:
            cc = 0
    bin_list[GLOBAL_SETTINGS_BANK_CHANGE_CC] = cc

    # What the Bank Up/Down switches do: change bank, both, or MIDI only
    mode_text = str(df.loc["Bank_Switch_Mode", "Value"]).strip().upper() if "Bank_Switch_Mode" in df.index else "BANK"
    mode_text = mode_text.replace(" ", "").replace("_", "")
    if mode_text.startswith("MIDIONLY") or mode_text == "MIDI":
        bsm = 2
    elif "MIDI" in mode_text:
        bsm = 1
    else:
        bsm = 0
    bin_list[GLOBAL_SETTINGS_BANK_SWITCH_MODE] = bsm

    # print('{:8.8}'.format(df.loc['ConfigName'].Value))
    bin_list += ("{:16.16}".format(df.loc["ConfigName"].Value)).encode("ASCII")

    # Bytes 32..47: settings added after the name filled the original 32
    bin_list += [0] * 16

    # Minutes of inactivity before the display and LEDs go out; 0 = never
    sleep_min = 0
    if "Sleep_After_Min" in df.index:
        try:
            sleep_min = int(float(str(df.loc["Sleep_After_Min", "Value"]).strip() or 0))
        except ValueError:
            sleep_min = 0
    bin_list[GLOBAL_SETTINGS_SLEEP_AFTER_MIN] = max(0, min(60, sleep_min))

    # Bank Up/Down follow the Setlist section instead of bank numbers
    if "Setlist_Mode" in df.index and "Y" in str(df.loc["Setlist_Mode", "Value"]).upper():
        bin_list[GLOBAL_SETTINGS_SETLIST_MODE] = 1

    # Adopt the tempo of MIDI clock arriving over USB
    if "Clock_Follow" in df.index and "Y" in str(df.loc["Clock_Follow", "Value"]).upper():
        bin_list[GLOBAL_SETTINGS_CLOCK_FOLLOW] = 1

    # Incoming CC and notes over USB set the toggle buttons that send them
    if "LED_Feedback" in df.index and "Y" in str(df.loc["LED_Feedback", "Value"]).upper():
        bin_list[GLOBAL_SETTINGS_LED_FEEDBACK] = 1

    # Double press window in ms, stored in 10 ms units (100..1000 ms)
    double_ms = 300
    if "Double_Press_ms" in df.index:
        try:
            double_ms = int(float(str(df.loc["Double_Press_ms", "Value"]).strip() or 300))
        except ValueError:
            double_ms = 300
    bin_list[GLOBAL_SETTINGS_DOUBLE_PRESS] = max(10, min(100, round(double_ms / 10)))

    # Remote press: ten CCs or notes from Remote_First press the ten switches
    mode_text = str(df.loc["Remote_Mode", "Value"]).strip().upper() if "Remote_Mode" in df.index else "OFF"
    if mode_text in ("", "NAN"):
        mode_text = "OFF"
    if mode_text.startswith("N"):
        mode_text = "NOTE"
    if mode_text not in REMOTE_MODES:
        raise ValueError(f"Remote_Mode must be Off, CC or Note, not {mode_text!r}")
    bin_list[GLOBAL_SETTINGS_REMOTE_MODE] = REMOTE_MODES[mode_text]

    ch_text = str(df.loc["Remote_Channel", "Value"]).strip() if "Remote_Channel" in df.index else "Any"
    if ch_text.upper().startswith("A") or ch_text in ("", "nan"):
        channel = 0
    else:
        try:
            channel = max(0, min(16, int(float(ch_text))))
        except ValueError:
            channel = 0
    bin_list[GLOBAL_SETTINGS_REMOTE_CHANNEL] = channel

    first = 102
    if "Remote_First" in df.index:
        try:
            first = int(float(str(df.loc["Remote_First", "Value"]).strip() or 102))
        except ValueError:
            first = 102
    bin_list[GLOBAL_SETTINGS_REMOTE_FIRST] = max(0, min(118, first))

    # The global channel: every command goes out on it instead of its own, so
    # one number moves a whole configuration to another channel. Off = each
    # command keeps the channel it carries.
    ch_text = str(df.loc["Global_Channel", "Value"]).strip() if "Global_Channel" in df.index else "Off"
    if ch_text.upper().startswith("O") or ch_text in ("", "nan"):
        channel = 0
    else:
        try:
            channel = max(0, min(16, int(float(ch_text))))
        except ValueError:
            channel = 0
    bin_list[GLOBAL_SETTINGS_GLOBAL_CHANNEL] = channel

    # Editing on the pedal: locked, the two bank switches held together no
    # longer open the editor, so nothing can be changed by accident on stage.
    lock = str(df.loc["Edit_Lock", "Value"]).strip() if "Edit_Lock" in df.index else "N"
    bin_list[GLOBAL_SETTINGS_EDIT_LOCK] = 1 if lock.upper().startswith("Y") else 0

    # Two way Kemper: the pedal asks the amp to report itself and follows what
    # comes back, the rig name on the display and the modules on the LEDs.
    kemper = str(df.loc["Kemper_Mode", "Value"]).strip() if "Kemper_Mode" in df.index else "N"
    bin_list[GLOBAL_SETTINGS_KEMPER_MODE] = 1 if kemper.upper().startswith("Y") else 0

    # The bank the global buttons are stored in: a button marked Global in any
    # other bank takes its lists, its label and its light from the same button
    # of this one. Off = no bank set aside, and nothing is redirected. Held as
    # the bank plus one, so a zero byte from an older configuration means Off.
    gb = str(df.loc["Global_Bank", "Value"]).strip() if "Global_Bank" in df.index else "Off"
    if gb.upper().startswith("O") or gb in ("", "nan"):
        bank = 0
    else:
        try:
            bank = int(float(gb)) + 1
        except ValueError:
            raise ValueError(f"Global_Bank must be Off or a bank 0-31, not {gb!r}")
        if not 1 <= bank <= 32:
            raise ValueError(f"Global_Bank must be Off or a bank 0-31, not {gb!r}")
    bin_list[GLOBAL_SETTINGS_GLOBAL_BANK] = bank

    # How long a switch of a combination waits for the other one, in ms,
    # stored in 10 ms units (20..250 ms)
    combo_ms = 80
    if "Combo_ms" in df.index:
        try:
            combo_ms = int(float(str(df.loc["Combo_ms", "Value"]).strip() or 80))
        except ValueError:
            combo_ms = 80
    bin_list[GLOBAL_SETTINGS_COMBO] = max(2, min(25, round(combo_ms / 10)))

    # The power on banner: the configuration's name and the firmware version
    # cross the display at this speed, instead of the fixed boot screen
    banner = str(df.loc["Boot_Banner", "Value"]).strip() if "Boot_Banner" in df.index else "Off"
    if banner in ("", "nan"):
        banner = "Off"
    if banner.upper() not in BANNER_SPEEDS:
        raise ValueError(f"Boot_Banner must be Off, Slow, Normal or Fast, not {banner!r}")
    bin_list[GLOBAL_SETTINGS_BANNER] = BANNER_SPEEDS[banner.upper()]

    # Bank preview: Bank Up / Down only show the bank there, and one of the
    # eight buttons confirms it within this many seconds. 0 or Off = off.
    preview = str(df.loc["Bank_Preview", "Value"]).strip() if "Bank_Preview" in df.index else "0"
    if preview in ("", "nan") or preview.upper() in ("OFF", "N", "NO"):
        preview = "0"
    try:
        seconds = int(float(preview))
    except ValueError:
        raise ValueError(f"Bank_Preview must be 0 (off) or 1-{BANK_PREVIEW_MAX_S} seconds, not {preview!r}")
    if not 0 <= seconds <= BANK_PREVIEW_MAX_S:
        raise ValueError(f"Bank_Preview must be 0 (off) or 1-{BANK_PREVIEW_MAX_S} seconds, not {preview!r}")
    bin_list[GLOBAL_SETTINGS_BANK_PREVIEW] = seconds

    return bin_list


def pack_bank_strings(df, num_banks=32):
    bin_list = []
    rows = {}
    for index, row in df.iterrows():
        key = str(index).strip()
        if key.endswith(".0"):
            key = key[:-2]
        rows[key] = row
    for bank in range(num_banks):
        row = rows.get(str(bank))
        if row is None:
            bin_list += b"    " + b"        "   # blank large + small name
            continue
        # Pack the bank info. The large name is 4 bytes and the small string is
        # 8 bytes. In case of an empty string, the value read from the CSV is
        # nan.
        large_name = str(row["Bank_Name_Large"])
        small_name = str(row["Bank_Info_Small"])
        if large_name == "nan":
            large_name = ""
        if small_name == "nan":
            small_name = ""
        bin_list += ("{:4.4}".format(large_name)).encode("ASCII")
        bin_list += ("{:8.8}".format(small_name)).encode("ASCII")

    return bin_list
