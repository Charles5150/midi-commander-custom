#! env python3
# -*- coding: utf-8 -*-
"""Generate the Kemper Profiler Player template, python/templates/Kemper_Player.csv.

The Player answers a fixed set of MIDI commands, so the numbers below are its
own and nothing has to be assigned on it: only its MIDI In Channel, System
Settings, has to match CHANNEL (it listens on every channel by default).

    python3 python/make_kemper_player_template.py
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib.configCsv import write_config_csv  # noqa: E402
from lib.configPacker import NUM_BANKS  # noqa: E402
from make_demo_config import Demo  # noqa: E402

OUT = os.path.join(HERE, "templates", "Kemper_Player.csv")

CHANNEL = "1"           # the Player's MIDI In Channel, System Settings

# The Player's MIDI map
CC_WAH = "1"            # the two pedal nodes
CC_VOLUME = "7"
CC_ALL_FX = "16"        # inverts every module from A to REV
CC_MODULE_A = "17"
CC_MODULE_B = "18"
CC_DLY = "26"           # 26 and 28 cut the tails; 27 and 29 keep them
CC_DLY_TAIL = "27"
CC_REV = "28"
CC_REV_TAIL = "29"
CC_TAP = "30"
CC_TUNER = "31"
CC_ROTARY = "33"        # any value toggles slow/fast
CC_INFINITY = "34"      # any value toggles
CC_FREEZE = "35"        # any value toggles
CC_BANK = "47"          # value 0-9 preselects banks 1-10
CC_SLOT = ("50", "51", "52", "53", "54")    # load rig 1-5 of the bank
CC_FX_BUTTON = ("75", "76", "77", "78")     # the Player's effect buttons I-IIII

RIG_BANKS = 10          # banks 0-9 are the Player's ten banks of five rigs
FX_BANK = 10
TOOL_BANK = 11
NO_SEND = "128"         # an off value of 128 sends nothing


def build():
    d = Demo()
    names = {}

    for bank in range(RIG_BANKS):
        # The small line is the rig numbers of the bank, and fits in 8 characters
        names[bank] = (f"BK{bank + 1:02d}", f"{bank * 5 + 1} to {bank * 5 + 5}")
        # Entering the bank preselects it on the Player; the rig itself is
        # only loaded once one of the slot buttons below is pressed
        d.on_enter(bank, CommandType="CC",
                   **{"Channel_(PC/CC/Note/PB)": CHANNEL, "Number_(PC/CC/Note)": CC_BANK,
                      "OnValue_(CC/PB)": str(bank), "OffValue_(CC)": str(bank)})
        for btn, number, rig in zip(("1", "2", "3", "4", "A"), CC_SLOT, range(1, 6)):
            # An exclusive group, so the LED and the display show the rig last
            # picked; pressing the lit one again sends nothing
            d.cc(bank, btn, f"RIG{rig}", number, on="1", off=NO_SEND, toggle="Y", ch=CHANNEL)
            d.group(bank, btn, 1)
        # The Player's own effect buttons: whatever each rig has assigned to I
        # and II, which is the handiest pair to have under the foot
        d.cc(bank, "B", "FX1", CC_FX_BUTTON[0], toggle="Y", ch=CHANNEL)
        d.cc(bank, "C", "FX2", CC_FX_BUTTON[1], toggle="Y", ch=CHANNEL)
        # Tap sends only on the press; a second message on the release would
        # count as another tap
        d.cc(bank, "D", "TAP", CC_TAP, off=NO_SEND, ch=CHANNEL)

    names[FX_BANK] = ("FX", "modules")
    for btn, label, number in (("1", "FX A", CC_MODULE_A), ("2", "FX B", CC_MODULE_B),
                               ("3", "DLY", CC_DLY), ("4", "REV", CC_REV)):
        d.cc(FX_BANK, btn, label, number, toggle="Y", ch=CHANNEL)
    # The four effect buttons the Player itself has, I to IIII
    for btn, number, n in zip(("A", "B", "C", "D"), CC_FX_BUTTON, range(1, 5)):
        d.cc(FX_BANK, btn, f"FX{n}", number, toggle="Y", ch=CHANNEL)

    names[TOOL_BANK] = ("TOOL", "tuner...")
    d.cc(TOOL_BANK, "1", "TUNR", CC_TUNER, toggle="Y", ch=CHANNEL)
    # These three flip on any value, so both halves of the toggle send 127:
    # every press flips them on the Player and the LED follows along
    d.cc(TOOL_BANK, "2", "ROTY", CC_ROTARY, off="127", toggle="Y", ch=CHANNEL)
    d.cc(TOOL_BANK, "3", "INF", CC_INFINITY, off="127", toggle="Y", ch=CHANNEL)
    d.cc(TOOL_BANK, "4", "FRZ", CC_FREEZE, off="127", toggle="Y", ch=CHANNEL)
    d.cc(TOOL_BANK, "A", "ALL", CC_ALL_FX, off=NO_SEND, ch=CHANNEL)
    # Delay and reverb again, but switching them off here leaves the tails ringing
    d.cc(TOOL_BANK, "B", "DLY+", CC_DLY_TAIL, toggle="Y", ch=CHANNEL)
    d.cc(TOOL_BANK, "C", "REV+", CC_REV_TAIL, toggle="Y", ch=CHANNEL)
    d.cc(TOOL_BANK, "D", "TAP", CC_TAP, off=NO_SEND, ch=CHANNEL)

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
                ("ConfigName", "KEMPER PL"),
                ("Exp1_CC", CC_WAH),
                ("Exp2_CC", CC_VOLUME),
                ("Bank_Up_LED_Mode", "Normal"),
                ("Bank_Down_LED_Mode", "Normal"),
                ("RealTime_Passthrough", "N"),
                ("USB_MIDI_Thru", "N"),
                ("Remember_State", "N"),
                ("Long_Press_ms", "500"),
                ("LED_Brightness", "100"),
                ("LED_Rest_Brightness", "25"),
                ("Bank_Jump_Step", "5"),
                ("Bank_Switch_Mode", "Bank"),
                # Only the twelve banks below are in use, so Bank Up and Bank
                # Down walk the setlist instead of the empty banks past them
                ("Setlist_Mode", "Y"),
            )
        ]
    )


def main() -> int:
    d, names = build()
    banks = pd.DataFrame(
        [
            {
                "Bank_Number": str(b),
                "Bank_Name_Large": names.get(b, ("", ""))[0],
                "Bank_Info_Small": names.get(b, ("", ""))[1],
            }
            for b in range(NUM_BANKS)
        ]
    )
    setlist = pd.DataFrame(
        [{"Position": str(i + 1), "Bank_Number": str(b)} for i, b in enumerate(sorted(names))]
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    write_config_csv(
        OUT,
        global_settings(),
        banks,
        d.buttons,
        note="Kemper Profiler Player template, generated by make_kemper_player_template.py",
        df_long_press=d.long,
        df_double_press=d.double,
        df_bank_expression=d.bank_exp,
        df_expression=d.exp,
        df_bank_enter=d.enter,
        df_sysex=d.sysex,
        df_bank_switch=d.bank_switch_frame,
        df_setlist=setlist,
    )
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
