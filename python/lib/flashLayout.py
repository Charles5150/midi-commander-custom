"""Where everything lives in a configuration slot, and the global defaults.

The layout is firmware/Core/Inc/flash_midi_settings.h's; test_roundtrip checks
the two agree. The packer, the unpacker and the tools take it from here.
"""

from lib.cmdBinaryPacker import CYCLE_LABEL_COUNT, CYCLE_LABEL_LEN, MIDI_NUM_COMMANDS_PER_SWITCH

NUM_BANKS = 32
BUTTON_IDS = ["1", "2", "3", "4", "A", "B", "C", "D"]
NUM_BUTTONS = len(BUTTON_IDS)
# The switches an expression pedal can press, and those a box on the jack
# (Output Switches) holds down: a command switch, or Bank Down or Up
EXP_BUTTON_IDS = BUTTON_IDS
BOX_SWITCH_IDS = BUTTON_IDS + ["Down", "Up"]
LABEL_LEN = 4

FLASH_PAGE_SIZE = 2048
SLOT_PAGES = 12

GLOBAL_SIZE = 48
BANK_STRINGS_SIZE = NUM_BANKS * 12
CMD_SIZE = 4
BUTTON_STRIDE = MIDI_NUM_COMMANDS_PER_SWITCH * CMD_SIZE
COMMANDS_OFFSET = GLOBAL_SIZE + BANK_STRINGS_SIZE
LED_MODES_OFFSET = COMMANDS_OFFSET + NUM_BANKS * NUM_BUTTONS * BUTTON_STRIDE
LABELS_OFFSET = LED_MODES_OFFSET + NUM_BANKS * NUM_BUTTONS
LONG_PRESS_OFFSET = LABELS_OFFSET + NUM_BANKS * NUM_BUTTONS * LABEL_LEN
EXP_OFFSET = LONG_PRESS_OFFSET + NUM_BANKS * NUM_BUTTONS * BUTTON_STRIDE
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
# Expression pedal output range per bank (firmware 0.33), 4 bytes per bank
BANK_EXP_RANGE_OFFSET = BANK_EXP_OFFSET + NUM_BANKS * BANK_EXP_STRIDE
BANK_EXP_RANGE_STRIDE = 4
# Labels of the states of cycle buttons (firmware 0.38), 4 chars each
CYCLE_LABELS_OFFSET = BANK_EXP_RANGE_OFFSET + NUM_BANKS * BANK_EXP_RANGE_STRIDE
# Two switches pressed together (firmware 0.59), 4 bytes each: the pair, the
# bank it counts in plus one (0 every bank), and the bank, button and list it runs
COMBOS_OFFSET = CYCLE_LABELS_OFFSET + CYCLE_LABEL_COUNT * CYCLE_LABEL_LEN
COMBO_COUNT = 12
COMBO_STRIDE = 4
CONFIG_SIZE = COMBOS_OFFSET + COMBO_COUNT * COMBO_STRIDE

# Double press commands follow the slot's 12 pages, in the extension area the
# firmware maps there (firmware 0.26). Same shape as the long press commands.
DOUBLE_PRESS_OFFSET = SLOT_PAGES * FLASH_PAGE_SIZE
DOUBLE_PRESS_SIZE = NUM_BANKS * NUM_BUTTONS * BUTTON_STRIDE
DOUBLE_PRESS_PAGES = 5
IMAGE_SIZE = DOUBLE_PRESS_OFFSET + DOUBLE_PRESS_PAGES * FLASH_PAGE_SIZE

# The second extension area (firmware 0.90): two pages per slot after the
# double press area, counted only when it starts with EXT2_MARKER
EXT2_OFFSET = IMAGE_SIZE
EXT2_PAGES = 2
EXT2_MARKER = b"EXT2"
EXT2_MAP_OFFSET = 16
# MIDI map: messages arriving over USB turned into others on the DIN output
MIDI_MAP_COUNT = 32
MIDI_MAP_STRIDE = 12
# Long press labels (firmware 0.91), after the map
EXT2_LONG_LABELS_OFFSET = EXT2_MAP_OFFSET + MIDI_MAP_COUNT * MIDI_MAP_STRIDE
# The labels of Bank Down and Bank Up (firmware 1.08), after the long press
# labels: the screen shows them with Bank_Switch_Mode at MIDI only. The tools
# read and write in pieces of 16 bytes, so the two take that much.
EXT2_BANK_SWITCH_LABELS_OFFSET = EXT2_LONG_LABELS_OFFSET + NUM_BANKS * NUM_BUTTONS * LABEL_LEN
EXT2_BANK_SWITCH_LABELS_SIZE = 16
EXT2_SIZE = EXT2_BANK_SWITCH_LABELS_OFFSET + EXT2_BANK_SWITCH_LABELS_SIZE

# What a Global_Settings row reads as when it is missing, and what an erased
# or out of range byte unpacks to
GLOBAL_DEFAULTS = {
    "MIDI_Channel": "1",
    "RealTime_Passthrough": "N",
    "Exp1_CC": "11",
    "Exp2_CC": "4",
    "Bank_Up_LED_Mode": "Normal",
    "Bank_Down_LED_Mode": "Normal",
    "USB_MIDI_Thru": "N",
    "USB_Ports": "1",
    "Remember_State": "N",
    "Long_Press_ms": "500",
    "LED_Brightness": "100",
    "LED_Rest_Brightness": "100",
    "Bank_Jump_Step": "8",
    "Bank_Change_Mode": "Off",
    "Bank_Change_Channel": "Any",
    "Bank_Change_CC": "0",
    "Bank_Switch_Mode": "Bank",
    "Sleep_After_Min": "0",
    "Setlist_Mode": "N",
    "Clock_Follow": "N",
    "LED_Feedback": "N",
    "Link_Toggles": "N",
    "Beat_Counter": "Off",
    "Double_Press_ms": "300",
    "Remote_Mode": "Off",
    "Remote_Channel": "Any",
    "Remote_First": "102",
    "Global_Channel": "Off",
    "Edit_Lock": "N",
    "Kemper_Mode": "N",
    "GT1000_Mode": "N",
    "Global_Bank": "Off",
    "Combo_ms": "80",
    "Boot_Banner": "Off",
    "Bank_Preview": "0",
    "Setlist_Display": "N",
}


def default_int(label) -> int:
    return int(GLOBAL_DEFAULTS[label])
