"""Pack a parsed configuration CSV into the flash image the firmware expects.

Layout (must match firmware/Core/Src/flash_midi_settings.c):

    0..15    global settings
    16..31   config name
    32..127  bank strings
    128..    8 banks x 8 buttons x 10 commands x 4 bytes
    2688..   button LED mode table, one byte per button (bank * 8 + button)
"""

import lib.cmdBinaryPacker as cbp
import lib.settingsBinaryPacker as sbp

NUM_BANKS = 8
NUM_BUTTONS = 8


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
    for _, row in df_buttons.iterrows():
        out += cbp.pack_row(row)
        light_modes.append(row.get("Light_Mode", "Normal"))
    out += cbp.pack_button_led_modes(light_modes)

    return bytes(out)
