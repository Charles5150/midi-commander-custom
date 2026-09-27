"""What each setting and command field is, for the editors.

The desktop configurator builds its global settings from GLOBAL_GROUPS and
GLOBAL_FIELDS; the web configurator (web/) builds everything from schema(),
as JSON. Plain data, no GUI toolkit: Pyodide runs this module in the browser.

A field is a dict:
  col      the CSV column (for a command, without its "A_" prefix)
  label    what the editor calls it
  kind     int (lo, hi), choice (options), check (Y/N), text (max, display:
           goes on the pedal's display), combo (options, free text allowed),
           and for commands the special modifiers, scene and button_mode
  blank    the choice stored as an empty cell
  default  what a new command starts with
  when     {col: [values]}: shown only while that column holds one of them
"""

from lib.cmdBinaryPacker import (
    BUTTON_ACTIONS, CHAN_OUTPUTS, EXP_TARGETS, HID_SPECIAL_KEYS, IF_BANK_TESTS, IF_BUTTON_TESTS,
    IF_TESTS, IF_VALUE_TESTS, LFO_DIVISIONS, LFO_SHAPES, LISTEN_LOOKS, MACRO_LISTS, MEDIA_KEYS,
    MMC_COMMANDS, MMC_LOCATE_MAX, NRPN_KINDS, NRPN_MAX, RAMP_MAX_MS, SCENE_BUTTONS, SCENE_MODES, SONG_MODES,
    SONG_POSITION_MAX, VAR_COUNT, VAR_DEFAULT_TOP, VAR_MODES, WAIT_BAR_MAX,
)
from lib.configPacker import (
    BUTTON_IDS, COMBO_COLUMNS, COMBO_COUNT, MIDI_MAP_COLUMNS, MIDI_MAP_COUNT, MIDI_MAP_OUT_TYPES,
    MIDI_MAP_TYPES, NUM_BANKS, SETLIST_MAX, SYSEX_STRING_COUNT,
)

CHANNELS = [str(i) for i in range(1, 17)]
BANKS = [str(b) for b in range(NUM_BANKS)]
LED_MODES = ["Normal", "Reverse", "AlwaysOn"]
BUTTON_GROUPS = ["None", "1", "2", "3", "4"]
BANK_SWITCH_MODES = ["Bank", "Bank+MIDI", "MIDI only"]
NO_COMMAND = "(none)"
THIS_BANK = "This bank"
COMMAND_TYPES = [NO_COMMAND, "PC", "PCInc", "CC", "Note", "PB", "CCInc", "Key", "Media", "Bank",
                 "SysEx", "Tap", "Start", "Stop", "MMC", "Song", "Panic", "Scene", "Wait", "Ramp",
                 "LFO", "Seq", "Exp", "Chan", "Value", "If", "Macro", "Button", "Listen", "NRPN",
                 "Pressure"]
# Cycle splits a button's short press list into states, so only that list offers it
SHORT_COMMAND_TYPES = COMMAND_TYPES + ["Cycle"]
# Leave splits a bank's enter list into the commands on entering and on leaving
ENTER_COMMAND_TYPES = COMMAND_TYPES + ["Leave"]
TAP_MODES = ["Tap", "Clock", "Set", "Up", "Down", "Up Repeat", "Down Repeat"]
WAIT_MODES = ["Time", "Beat", "Bar", "Count"]
CCINC_DIRECTIONS = ["Up", "Down", "Up Repeat", "Down Repeat"]
BANK_MODES = ["GoTo", "Up", "Down", "Config", "NextConfig", "Page", "Back", "Reveal", "Direct"]
CONFIG_SLOT_NAMES = ["1", "2", "3", "4"]
KEY_MODES = ["Normal", "Down", "Up"]
KEY_NAMES = (
    [chr(c) for c in range(ord("a"), ord("z") + 1)]
    + [str(d) for d in range(10)]
    + [k for k in HID_SPECIAL_KEYS if k != "escape"]
)
MODIFIERS = [("Ctrl", 1), ("Shift", 2), ("Alt", 4), ("Cmd", 8)]
SLOTS = [chr(ord("A") + i) for i in range(10)]

# Per-slot CSV columns (without the "A_" prefix)
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
    "KeyMode_(Key)",
]

# Global settings, grouped by what they are about: (CSV label, name, hint)
GLOBAL_GROUPS = [
    ("Configuration", [
        ("ConfigName", "Configuration name", "shown on the display at boot, 16 characters"),
        ("Boot_Banner", "Banner at power on", "the pedal's Banner Text or this name, then the version, cross the display; any switch skips it"),
        ("MIDI_Channel", "MIDI channel", "used by the expression pedals"),
        ("Global_Channel", "Global channel", "every command goes out on it, whatever channel it carries"),
        ("Exp1_CC", "Expression pedal 1 CC", "0-127"),
        ("Exp2_CC", "Expression pedal 2 CC", "0-127"),
    ]),
    ("Presses", [
        ("Long_Press_ms", "Long press after", "ms held, 100-2500"),
        ("Double_Press_ms", "Double press within", "ms between presses, 100-1000"),
        ("Combo_ms", "Two switches together within", "ms between them, 20-250, see the Combos tab"),
        ("Remember_State", "Remember state", "come back in the last bank with every toggle as it was"),
        ("Edit_Lock", "Lock on-pedal editing", "the two bank switches held together no longer open the editor"),
    ]),
    ("LEDs", [
        ("LED_Brightness", "Brightness", "% for a lit LED, 1-100"),
        ("LED_Rest_Brightness", "Brightness at rest", "% for LEDs lit at rest by Reverse and AlwaysOn"),
        ("Bank_Up_LED_Mode", "Bank Up LED", ""),
        ("Bank_Down_LED_Mode", "Bank Down LED", ""),
        ("LED_Feedback", "Follow the computer", "CC and notes from USB light the toggles that send them"),
        ("Link_Toggles", "Link toggles", "toggles sending the same CC or note share their state, in every bank"),
    ]),
    ("Banks", [
        ("Bank_Switch_Mode", "Bank switches", "what Bank Up / Down do, see the Bank Switch tab"),
        ("Bank_Jump_Step", "Long press jumps", "banks, 1-31"),
        ("Bank_Preview", "Preview banks", "seconds a bank shown by Bank Up / Down waits for a button to confirm it, 0 = off"),
        ("Setlist_Mode", "Follow the setlist", "Bank Up / Down use the order in the Setlist tab"),
        ("Bank_Change_Mode", "Change bank from MIDI", "an incoming PC or CC selects the bank"),
        ("Bank_Change_Channel", "… listening on channel", ""),
        ("Bank_Change_CC", "… with CC number", "when the mode is CC"),
        ("Global_Bank", "Global buttons bank", "the bank the buttons marked Global take everything from"),
    ]),
    ("USB MIDI", [
        ("USB_MIDI_Thru", "USB to DIN thru", "forward notes, CC, PC and other devices' SysEx"),
        ("RealTime_Passthrough", "Clock and transport thru", "forward Clock, Start, Continue and Stop"),
        ("Clock_Follow", "Follow the host's clock", "adopt the tempo of MIDI clock from USB"),
        ("Beat_Counter", "Bar and beat on the display", "beats in a bar, shown while a clock runs; Off = not shown"),
        ("Remote_Mode", "Press from the computer", "CC or notes from USB press the switches"),
        ("Remote_Channel", "… listening on channel", ""),
        ("Remote_First", "… from number", "1 2 3 4 A B C D, Bank Down, Bank Up take ten in a row"),
        ("Kemper_Mode", "Talk to a Kemper", "the rig name on the display and the modules on the LEDs"),
    ]),
    ("Power", [
        ("Sleep_After_Min", "Sleep after", "idle minutes before the display and LEDs go out, 0 = never"),
    ]),
]


def _int(lo, hi, **kw):
    return {"kind": "int", "lo": lo, "hi": hi, **kw}


def _choice(options, **kw):
    return {"kind": "choice", "options": list(options), **kw}


CHECK = {"kind": "check"}

# The editor of each global setting; a label not here is free text
GLOBAL_FIELDS = {
    "MIDI_Channel": _choice(CHANNELS),
    **{label: CHECK for label in ("RealTime_Passthrough", "USB_MIDI_Thru", "Remember_State",
                                  "Setlist_Mode", "Clock_Follow", "LED_Feedback", "Link_Toggles",
                                  "Edit_Lock", "Kemper_Mode")},
    "Bank_Up_LED_Mode": _choice(LED_MODES),
    "Bank_Down_LED_Mode": _choice(LED_MODES),
    "Exp1_CC": _int(0, 127),
    "Exp2_CC": _int(0, 127),
    "Bank_Change_CC": _int(0, 127),
    "Long_Press_ms": _int(100, 2500),
    "Double_Press_ms": _int(100, 1000),
    "Combo_ms": _int(20, 250),
    "Beat_Counter": _choice(["Off"] + [str(n) for n in range(1, 16)]),
    "Boot_Banner": _choice(["Off", "Slow", "Normal", "Fast"]),
    "LED_Brightness": _int(1, 100),
    "LED_Rest_Brightness": _int(1, 100),
    "Bank_Preview": _int(0, 60),
    "Bank_Jump_Step": _int(1, 31),
    "Bank_Change_Mode": _choice(["Off", "PC", "CC"]),
    "Bank_Switch_Mode": _choice(BANK_SWITCH_MODES),
    "Sleep_After_Min": _int(0, 60),
    "Remote_Mode": _choice(["Off", "CC", "Note"]),
    "Remote_First": _int(0, 118),
    "Global_Channel": _choice(["Off"] + CHANNELS),
    "Global_Bank": _choice(["Off"] + BANKS),
    "Bank_Change_Channel": _choice(["Any"] + CHANNELS),
    "Remote_Channel": _choice(["Any"] + CHANNELS),
    "ConfigName": {"kind": "text", "max": 16, "display": True},
}

# A button's own settings, besides its command lists
BUTTON_FIELDS = [
    {"col": "Label", "label": "Label", "kind": "text", "max": 4, "display": True},
    {"col": "Light_Mode", "label": "LED", **_choice(LED_MODES)},
    {"col": "Group", "label": "Exclusive group", **_choice(BUTTON_GROUPS, blank="None")},
    {"col": "Momentary_Hold", "label": "Momentary when held", "kind": "check", "off": ""},
    {"col": "Tempo_Flash", "label": "Flash at the tempo", "kind": "check", "off": ""},
    {"col": "Global", "label": "Global", "kind": "check", "off": ""},
    {"col": "Reset_On_Bank", "label": "Reset on bank change", "kind": "check", "off": ""},
]

CH = "Channel_(PC/CC/Note/PB)"
NUM = "Number_(PC/CC/Note)"
ON = "OnValue_(CC/PB)"
OFF = "OffValue_(CC)"
BS = "BankSelect_(PC)"
BSH = "BankSelectHighByte_(PC)"
TOG = "Toggle_(CC/PB/Note)"
VEL = "Velocity_(Note)"
DUR = "Duration_(Note/PB)"
MODE = "KeyMode_(Key)"


def _f(col, label, spec, **kw):
    return {"col": col, "label": label, **spec, **kw}


def _channel():
    return _f(CH, "Ch", _choice(CHANNELS))


def _toggle(label="Toggle"):
    return _f(TOG, label, CHECK)


def _when(col, *values):
    return {"when": {col: list(values)}}


# The fields each command type shows, as the desktop configurator's command
# editor has them; hint says what the command does, or hints by the value of
# hint_by. Start, Stop, Panic and (none) have none.
COMMAND_SPECS = {
    "PC": {"fields": [_channel(), _f(NUM, "Program", _int(0, 127)),
                      _f(BS, "BankSel", _int(0, 16383)), _f(BSH, "Send bank MSB", CHECK)]},
    "CC": {"fields": [_channel(), _f(NUM, "CC#", _int(0, 127)), _f(ON, "On", _int(0, 127)),
                      _f(OFF, "Off", _int(0, 127)), _toggle()]},
    "Pressure": {"fields": [_channel(), _f(ON, "On", _int(0, 127)), _f(OFF, "Off", _int(0, 127)),
                            _toggle()],
                 "hint": "Channel Pressure"},
    "NRPN": {"fields": [_f(MODE, "Kind", _choice(NRPN_KINDS, blank=NRPN_KINDS[0])),
                        _f(NUM, "Param", _int(0, NRPN_MAX))],
             "hint": "the CC below sends its values to this parameter"},
    "Note": {"fields": [_channel(), _f(NUM, "Note", _int(0, 127)), _f(VEL, "Vel", _int(0, 127)),
                        _f(DUR, "Dur", _int(0, 127)), _toggle()]},
    "PB": {"fields": [_channel(), _f(ON, "Bend", _int(-8192, 8191)), _f(DUR, "Dur", _int(0, 127)),
                      _toggle()]},
    "Key": {"fields": [_f(NUM, "Modifiers", {"kind": "modifiers",
                                             "options": [[n, b] for n, b in MODIFIERS]}),
                       _f(ON, "Key", {"kind": "combo", "options": KEY_NAMES}),
                       _f(MODE, "Mode", _choice(KEY_MODES)), _f(DUR, "Dur", _int(0, 127)),
                       _toggle("Hold")]},
    "CCInc": {"fields": [_channel(), _f(NUM, "CC#", _int(0, 127)),
                         _f(MODE, "Dir", _choice(CCINC_DIRECTIONS)),
                         _f(OFF, "Step", _int(1, 127)), _f(ON, "Start", _int(0, 127)),
                         _toggle("Wrap")]},
    "PCInc": {"fields": [_channel(), _f(MODE, "Dir", _choice(CCINC_DIRECTIONS)),
                         _f(OFF, "Step", _int(1, 127)), _f(NUM, "Last", _int(0, 127), default="127"),
                         _toggle("Wrap")]},
    "Tap": {"fields": [_f(MODE, "Action", _choice(TAP_MODES)),
                       _f(ON, "BPM", _int(30, 300), default="120", **_when(MODE, "Set")),
                       _f(OFF, "Step", _int(1, 127), default="1",
                          **_when(MODE, "Up", "Down", "Up Repeat", "Down Repeat"))],
            "hint_by": MODE,
            "hints": {"Tap": "Tap sets the tempo, Clock starts/stops the MIDI clock",
                      "Clock": "Tap sets the tempo, Clock starts/stops the MIDI clock"}},
    "SysEx": {"fields": [_f(NUM, "String", _choice([str(i) for i in range(SYSEX_STRING_COUNT)]))],
              "hint": "edit the bytes in SysEx strings"},
    "Bank": {"fields": [_f(MODE, "Action", _choice(BANK_MODES)),
                        _f(ON, "Bank", _choice(BANKS), **_when(MODE, "GoTo", "Page")),
                        _f(ON, "Slot", _choice(CONFIG_SLOT_NAMES), default="1", **_when(MODE, "Config")),
                        _f(ON, "Banks", _int(1, 31), default="8", **_when(MODE, "Up", "Down"))],
             "hint_by": MODE,
             "hints": {"NextConfig": "next slot holding a configuration",
                       "Back": "the bank you came from",
                       "Reveal": "while held, the buttons show their long press labels",
                       "Direct": "two presses choose any bank: its group of eight, then the bank"}},
    "MMC": {"fields": [_f(MODE, "Action", _choice(MMC_COMMANDS), default="Play"),
                       _f(ON, "At (s)", _int(0, MMC_LOCATE_MAX), default="0", **_when(MODE, "Locate"))],
            "hint": "MIDI Machine Control, to every device"},
    "Song": {"fields": [_f(MODE, "Send", _choice(SONG_MODES), default="Select"),
                        _f(ON, "Song", _int(0, 127), default="0", **_when(MODE, "Select")),
                        _f(ON, "Beat", _int(0, SONG_POSITION_MAX), default="0", **_when(MODE, "Position"))],
             "hint_by": MODE,
             "hints": {"Select": "song number", "Position": "sixteenth notes from the start"}},
    "Media": {"fields": [_f(ON, "Key", _choice(MEDIA_KEYS)), _f(DUR, "Dur", _int(0, 127)),
                         _toggle("Hold")]},
    "Scene": {"fields": [_f(MODE, "Do", _choice(SCENE_MODES, blank=SCENE_MODES[0])),
                         _f(ON, "Buttons", {"kind": "scene", "options": list(SCENE_BUTTONS)},
                            **_when(MODE, SCENE_MODES[0])),
                         _f(NUM, "Button", _choice(SCENE_BUTTONS), default="1",
                            **_when(MODE, *SCENE_MODES[1:]))],
              "hint_by": MODE,
              "hints": {m: "the toggles now go into its first scene"
                        for m in SCENE_MODES[1:]}},
    "Wait": {"fields": [_f(MODE, "Wait", _choice(WAIT_MODES, blank="Time")),
                        _f(DUR, "ms", _int(0, 2550), **_when(MODE, "Time")),
                        _f(NUM, "Beats", _int(1, WAIT_BAR_MAX), default="4", **_when(MODE, "Bar", "Count"))],
             "hint_by": MODE,
             "hints": {"Time": "pauses the commands below it, in steps of 10 ms",
                       "Beat": "the commands below wait for the next beat",
                       "Bar": "the commands below wait for the next bar",
                       "Count": "a count-in: a whole bar at least, counted down on the display"}},
    "Cycle": {"fields": [_f(ON, "Label", {"kind": "text", "max": 4, "display": True})],
              "hint": "the commands below are the next state; empty = the button's label"},
    "Leave": {"fields": [], "hint": "the commands below are sent on leaving the bank instead"},
    "Chan": {"fields": [_f(CH, "Channels", {"kind": "text", "max": 47}),
                        _f(MODE, "Output", _choice(CHAN_OUTPUTS, blank="Both"))],
             "hint": "\"1 2 3\" or \"1-3\"; empty: its own"},
    "Ramp": {"fields": [_f(DUR, "ms", _int(0, RAMP_MAX_MS))],
             "hint": "the CC right below walks to its value over this time"},
    "LFO": {"fields": [_f(ON, "Every", _choice(LFO_DIVISIONS), default="1/4"),
                       _f(MODE, "Shape", _choice(LFO_SHAPES), default="Sine")],
            "hint": "the CC right below swings between Off and On, locked to the tempo"},
    "Seq": {"fields": [_f(ON, "Steps", {"kind": "text", "max": 15}),
                       _f(MODE, "Every", _choice(LFO_DIVISIONS), default="1/8")],
            "hint": "two steps, \"100 -\"; one Seq after another makes a longer sequence"},
    "Value": {"fields": [_f(NUM, "Value", _choice([str(i) for i in range(1, VAR_COUNT + 1)]), default="1"),
                         _f(MODE, "Do", _choice(VAR_MODES)), _f(ON, "By", _int(0, 127)),
                         _f(OFF, "Top", _int(0, 127), default=str(VAR_DEFAULT_TOP))],
              "hint": "the pedal's own values, all zero at power on; past the top it starts again"},
    "If": {"fields": [_f(MODE, "Only if", _choice(IF_TESTS)),
                      _f(NUM, "Button", _choice(SCENE_BUTTONS), default="1",
                         **_when(MODE, *[IF_TESTS[i] for i in IF_BUTTON_TESTS])),
                      _f(NUM, "Value", _choice([str(i) for i in range(1, VAR_COUNT + 1)]), default="1",
                         **_when(MODE, *[IF_TESTS[i] for i in IF_VALUE_TESTS])),
                      _f(ON, "Is", _int(0, 127), **_when(MODE, *[IF_TESTS[i] for i in IF_VALUE_TESTS])),
                      _f(ON, "Bank", _int(0, 31), **_when(MODE, *[IF_TESTS[i] for i in IF_BANK_TESTS]))],
           "hint": "the command right below only goes out then; another If asks for both"},
    "Macro": {"fields": [_f(ON, "Bank", _int(0, 31)),
                         _f(NUM, "Button", _choice(SCENE_BUTTONS), default="1"),
                         _f(MODE, "List", _choice(MACRO_LISTS))],
              "hint": "that button's list is run here, so a sequence used in many banks is stored once"},
    "Button": {"fields": [_f(ON, "Bank", _choice([THIS_BANK] + BANKS, blank=THIS_BANK)),
                          _f(NUM, "Button", _choice(SCENE_BUTTONS), default="1"),
                          _f(MODE, "List / Do", {"kind": "button_mode", "lists": MACRO_LISTS,
                                                 "actions": BUTTON_ACTIONS})],
               "hint": "as a foot would; Set sends nothing"},
    "Listen": {"fields": [_f(NUM, "CC", _int(0, 127)), _f(ON, "On", _int(0, 127)),
                          _f(OFF, "Off", _int(0, 127)),
                          _f(MODE, "LED", _choice(LISTEN_LOOKS, blank=LISTEN_LOOKS[0]))],
               "hint": "the CC the device reports on; empty: 127/0. LED: how On shows"},
    "Exp": {"fields": [_f(ON, "Pedal", _choice(["1", "2"])), _f(MODE, "To", _choice(EXP_TARGETS)),
                       _f(NUM, "CC#", _int(0, 127), **_when(MODE, "CC")),
                       _f(CH, "Ch", _choice(["Own"] + CHANNELS, blank="Own"), **_when(MODE, "CC")),
                       _toggle()],
            "hint_by": MODE,
            "hints": {"Add": "also sends the CC below: Off at the heel, On at the toe"},
            "hint": "until the bank changes; a toggle gives it back when off"},
}

# The other sections, edited as tables: the columns each shows, and how
EXPRESSION_FIELDS = [
    {"col": "Min_ADC", "label": "Heel reading", **_int(0, 4095)},
    {"col": "Max_ADC", "label": "Toe reading", **_int(0, 4095)},
    {"col": "Curve", "label": "Curve", **_choice(["Linear", "Log", "Exp"])},
    {"col": "Invert", "label": "Invert", **CHECK},
    {"col": "Channel", "label": "Channel", **_choice(["Global"] + CHANNELS)},
    {"col": "Output", "label": "Sends", **_choice(["CC", "PitchBend", "CC14", "Speed"])},
    {"col": "Out_Min", "label": "Out min", **_int(0, 127)},
    {"col": "Out_Max", "label": "Out max", **_int(0, 127), "default": "127"},
    {"col": "Toe_Button", "label": "Toe taps", **_choice(["None"] + BUTTON_IDS, blank="None")},
    {"col": "Toe_Level", "label": "\u2026 above", **_int(1, 127), "default": "120"},
    {"col": "Heel_Button", "label": "Heel taps", **_choice(["None"] + BUTTON_IDS, blank="None")},
    {"col": "Heel_Level", "label": "\u2026 below", **_int(0, 127), "default": "7"},
    {"col": "Auto_Button", "label": "Auto-engage", **_choice(["None"] + BUTTON_IDS, blank="None")},
    {"col": "Auto_Off_ms", "label": "\u2026 off after ms", **_int(10, 2540), "default": "500"},
    {"col": "Send_On_Bank", "label": "Send on entering a bank", **CHECK},
]

SECTION_COLUMNS = {
    "SysEx_Strings": [{"col": "Bytes", "label": "Bytes (hex)", "kind": "text", "max": 80}],
    "Setlist": [{"col": "Bank_Number", "label": "Bank", **_choice([""] + BANKS)}],
    "BankExpression_Settings": [
        {"col": f"Exp{p}_{c}", "label": f"Pedal {p} {c}", "kind": "text", "max": 6}
        for p in (1, 2) for c in ("CC", "Channel", "Min", "Max")],
    "Combo_Settings": [
        {"col": "Switches", "label": "Switches", "kind": "text", "max": 7},
        {"col": "Bank", "label": "In bank", "kind": "text", "max": 3},
        {"col": "Run_Bank", "label": "Runs bank", **_int(0, 31)},
        {"col": "Run_Button", "label": "button", **_choice(BUTTON_IDS)},
        {"col": "Run_List", "label": "list", **_choice(MACRO_LISTS)},
    ],
    # Out_* only for a message, Run_* only for a list: "when" as in commands
    "MidiMap_Settings": [
        {"col": "In_Type", "label": "type", **_choice(list(MIDI_MAP_TYPES))},
        {"col": "In_Channel", "label": "ch", **_choice(["Any"] + CHANNELS, blank="Any")},
        {"col": "In_Number", "label": "number", "kind": "text", "max": 3,
         "when": {"In_Type": ["Note", "CC", "PC"]}},
        {"col": "In_Min", "label": "from", **_int(0, 127)},
        {"col": "In_Max", "label": "to", **_int(0, 127)},
        {"col": "Out_Type", "label": "type", **_choice(list(MIDI_MAP_OUT_TYPES))},
        {"col": "Out_Channel", "label": "ch", **_choice(["Same"] + CHANNELS, blank="Same"),
         "when": {"Out_Type": list(MIDI_MAP_TYPES)}},
        {"col": "Out_Number", "label": "number", "kind": "text", "max": 4,
         "when": {"Out_Type": list(MIDI_MAP_TYPES)}},
        {"col": "Out_Min", "label": "from", **_int(0, 127), "when": {"Out_Type": list(MIDI_MAP_TYPES)}},
        {"col": "Out_Max", "label": "to", **_int(0, 127), "when": {"Out_Type": list(MIDI_MAP_TYPES)}},
        {"col": "Run_Bank", "label": "bank", **_int(0, 31), "when": {"Out_Type": ["Run"]}},
        {"col": "Run_Button", "label": "button", **_choice(BUTTON_IDS), "when": {"Out_Type": ["Run"]}},
        {"col": "Run_List", "label": "list", **_choice(MACRO_LISTS), "when": {"Out_Type": ["Run"]}},
        {"col": "Keep", "label": "Also as it came", **CHECK},
    ],
}


def schema() -> dict:
    """Everything the web editor needs, as plain JSON data."""
    return {
        "numBanks": NUM_BANKS,
        "buttonIds": BUTTON_IDS,
        "slots": SLOTS,
        "cmdFields": CMD_FIELDS,
        "noCommand": NO_COMMAND,
        "commandTypes": COMMAND_TYPES,
        "shortCommandTypes": SHORT_COMMAND_TYPES,
        "enterCommandTypes": ENTER_COMMAND_TYPES,
        "commandSpecs": COMMAND_SPECS,
        "globalGroups": [[g, [list(item) for item in items]] for g, items in GLOBAL_GROUPS],
        "globalFields": GLOBAL_FIELDS,
        "buttonFields": BUTTON_FIELDS,
        "expressionFields": EXPRESSION_FIELDS,
        "sectionColumns": SECTION_COLUMNS,
        "setlistMax": SETLIST_MAX,
        "comboCount": COMBO_COUNT,
        "comboColumns": COMBO_COLUMNS,
        "midiMapCount": MIDI_MAP_COUNT,
        "midiMapColumns": MIDI_MAP_COLUMNS,
    }
