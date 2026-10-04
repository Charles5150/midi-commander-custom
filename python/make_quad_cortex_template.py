#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the Neural DSP Quad Cortex template, python/templates/Quad_Cortex.csv.

The Quad Cortex has a fixed MIDI map, the "Incoming MIDI CC List" of its
manual (CorOS 4.1.1), so the CC numbers below are its own and nothing has to
be assigned on it: only its MIDI channel, Settings > Device > MIDI, has to
match CHANNEL.

    python3 python/make_quad_cortex_template.py
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib.configCsv import write_config_csv  # noqa: E402
from lib.flashLayout import NUM_BANKS  # noqa: E402
from make_demo_config import Demo  # noqa: E402

OUT = os.path.join(HERE, "templates", "Quad_Cortex.csv")

CHANNEL = "1"           # the Quad Cortex's MIDI Channel
SETLIST = "1"           # CC#32 before each Program Change: 0 Factory Presets, 1 My Presets, 2-12 the user setlists

# The Quad Cortex's MIDI map
CC_EXP1 = "1"           # Expression Pedal 1 and 2
CC_EXP2 = "2"
CC_FS = ("35", "36", "37", "38", "39", "40", "41", "42")  # Footswitches A-H: any value is a press
CC_SCENE = "43"         # 0-7 = scenes A-H
CC_TAP = "44"           # any value is a tap
CC_TUNER = "45"         # 64-127 opens, 0-63 closes
CC_LOOPER = "48"        # 0-63 opens the Looper X view, 64-127 closes it
CC_ONCE = "50"          # Looper X: 64-127 toggles each of these
CC_HALF = "51"
CC_REC = "53"           # record, then overdub
CC_PLAY = "54"          # play / stop
CC_REV = "55"
CC_UNDO = "56"          # undo / redo

PRESET_BANKS = 30       # banks 0-29 load presets 0-29 of SETLIST
LOOP_BANK = 30
FS_BANK = 31
SCENE_BUTTONS = (("1", "A"), ("2", "B"), ("3", "C"), ("4", "D"), ("A", "E"), ("B", "F"))
# The pedal's bottom row, A-D, is the Quad Cortex's bottom row, A-D; the top
# row, 1-4, is its top row, E-H
FS_BUTTONS = ("A", "B", "C", "D", "1", "2", "3", "4")
NO_SEND = "128"         # an off value of 128 sends nothing
PRESS = "127"


def tuner_and_tap(d, bank):
    # The tuner opens on one press and closes on the next
    d.cc(bank, "C", "TUNR", CC_TUNER, toggle="Y", ch=CHANNEL)
    # Tap sends only on the press; a second message on the release would
    # count as another tap
    d.cc(bank, "D", "TAP", CC_TAP, off=NO_SEND, ch=CHANNEL)


def looper_switch(d, bank, btn, label, number):
    # Each 64-127 toggles the Looper X setting, so both presses send one;
    # the LED follows the setting from when the looper is opened
    d.cc(bank, btn, label, number, on=PRESS, off=PRESS, toggle="Y", ch=CHANNEL)


def build():
    d = Demo()
    names = {}

    for bank in range(PRESET_BANKS):
        names[bank] = (f"P{bank:03d}", "QC prst")
        d.on_enter(bank, CommandType="PC",
                   **{"Channel_(PC/CC/Note/PB)": CHANNEL, "Number_(PC/CC/Note)": str(bank),
                      "BankSelect_(PC)": SETLIST, "BankSelectHighByte_(PC)": "Y"})
        for btn, scene in SCENE_BUTTONS:
            # An exclusive group, so the LED and the display show the scene
            # last picked; switching it off sends nothing
            d.cc(bank, btn, f"SCN{scene}", CC_SCENE, on=str("ABCDEFGH".index(scene)), off=NO_SEND,
                 toggle="Y", ch=CHANNEL)
            d.group(bank, btn, 1)
        tuner_and_tap(d, bank)

    names[LOOP_BANK] = ("LOOP", "looper X")
    d.cc(LOOP_BANK, "1", "REC", CC_REC, off=NO_SEND, ch=CHANNEL)
    d.cc(LOOP_BANK, "2", "PLAY", CC_PLAY, off=NO_SEND, ch=CHANNEL)
    d.cc(LOOP_BANK, "3", "UNDO", CC_UNDO, off=NO_SEND, ch=CHANNEL)
    # Opens the Looper X view on one press, closes it on the next
    d.cc(LOOP_BANK, "4", "VIEW", CC_LOOPER, on="0", off=PRESS, toggle="Y", ch=CHANNEL)
    looper_switch(d, LOOP_BANK, "A", "ONCE", CC_ONCE)
    looper_switch(d, LOOP_BANK, "B", "HALF", CC_HALF)
    looper_switch(d, LOOP_BANK, "C", "REV", CC_REV)
    d.cc(LOOP_BANK, "D", "TAP", CC_TAP, off=NO_SEND, ch=CHANNEL)

    names[FS_BANK] = ("FS", "stomps")
    for btn, number, fs in zip(FS_BUTTONS, CC_FS, "ABCDEFGH"):
        # Each message presses the footswitch once, which switches whatever
        # is assigned to it
        d.cc(FS_BANK, btn, f"FS-{fs}", number, toggle="Y", ch=CHANNEL)

    # The expression pedals, calibrated end points left at the full range
    d.exp.loc[0, ["Min_ADC", "Max_ADC", "Curve", "Invert", "Channel"]] = ["100", "3900", "Linear", "N", "Global"]
    d.exp.loc[1, ["Min_ADC", "Max_ADC", "Curve", "Invert", "Channel"]] = ["100", "3900", "Linear", "N", "Global"]
    return d, names


def global_settings() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Label": l, "Value": v}
            for l, v in (
                ("MIDI_Channel", CHANNEL),
                ("ConfigName", "Quad Cortex"),
                ("Exp1_CC", CC_EXP1),
                ("Exp2_CC", CC_EXP2),
                ("Bank_Up_LED_Mode", "Normal"),
                ("Bank_Down_LED_Mode", "Normal"),
                ("RealTime_Passthrough", "N"),
                ("USB_MIDI_Thru", "N"),
                ("Remember_State", "N"),
                ("Long_Press_ms", "500"),
                ("LED_Brightness", "100"),
                ("LED_Rest_Brightness", "25"),
                ("Bank_Jump_Step", "10"),
                ("Bank_Switch_Mode", "Bank"),
            )
        ]
    )


def main() -> int:
    d, names = build()
    banks = pd.DataFrame(
        [
            {"Bank_Number": str(b), "Bank_Name_Large": names[b][0], "Bank_Info_Small": names[b][1]}
            for b in range(NUM_BANKS)
        ]
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    write_config_csv(
        OUT,
        global_settings(),
        banks,
        d.buttons,
        note="Neural DSP Quad Cortex template, generated by make_quad_cortex_template.py",
        df_long_press=d.long,
        df_double_press=d.double,
        df_bank_expression=d.bank_exp,
        df_expression=d.exp,
        df_bank_enter=d.enter,
        df_sysex=d.sysex,
        df_bank_switch=d.bank_switch_frame,
    )
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
