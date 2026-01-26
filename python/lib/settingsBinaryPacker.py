GLOBAL_SETTINGS_CHANNEL = 0
GLOBAL_SETTINGS_REALTIME_PASS = 1
GLOBAL_SETTINGS_EXP1_CC = 2
GLOBAL_SETTINGS_EXP2_CC = 3

def pack_global_settings(df):
    # global settings will be 32 bytes long
    bin_list = [0] * 16
    bin_list[GLOBAL_SETTINGS_CHANNEL] = int(df.loc["MIDI_Channel", "Value"]) & 0xF
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

    # print('{:8.8}'.format(df.loc['ConfigName'].Value))
    bin_list += ("{:16.16}".format(df.loc["ConfigName"].Value)).encode("ASCII")

    return bin_list


def pack_bank_strings(df):
    bin_list = []
    for index, row in df.iterrows():
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
