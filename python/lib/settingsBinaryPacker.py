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

    # print('{:8.8}'.format(df.loc['ConfigName'].Value))
    bin_list += ("{:16.16}".format(df.loc["ConfigName"].Value)).encode("ASCII")

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
