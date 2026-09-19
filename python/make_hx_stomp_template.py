#! env python3
# -*- coding: utf-8 -*-
"""Generate the Line 6 HX Stomp template, python/templates/HX_Stomp.csv.

Unlike the FM3, the HX Stomp has a fixed MIDI map, so the CC numbers below
are the HX Stomp's own and nothing has to be assigned on it: only its MIDI
channel, Global Settings > MIDI/Tempo, has to match CHANNEL.

    python3 python/make_hx_stomp_template.py
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib.configCsv import write_config_csv  # noqa: E402
from lib.configPacker import NUM_BANKS  # noqa: E402
from make_demo_config import Demo  # noqa: E402

OUT = os.path.join(HERE, "templates", "HX_Stomp.csv")

CHANNEL = "1"           # the HX Stomp's MIDI Base Channel

# The HX Stomp's MIDI map
CC_EXP1 = "1"           # EXP 1 and EXP 2 pedals
CC_EXP2 = "2"
CC_FS = ("49", "50", "51", "52", "53")  # FS1-FS5, in Stomp mode
CC_LOOP_REC = "60"      # 64-127 record, 0-63 overdub
CC_LOOP_PLAY = "61"     # 64-127 play, 0-63 stop
CC_LOOP_ONCE = "62"
CC_LOOP_UNDO = "63"
CC_TAP = "64"
CC_LOOP_REV = "65"      # 64-127 reverse, 0-63 forward
CC_LOOP_HALF = "66"     # 64-127 half speed, 0-63 full speed
CC_TUNER = "68"
CC_SNAPSHOT = "69"      # 0-2 = snapshots 1-3, 8 = next, 9 = previous

PRESET_BANKS = 30       # banks 0-29 load presets 0-29, 01A to 10C
LOOP_BANK = 30
FS_BANK = 31
NO_SEND = "128"         # an off value of 128 sends nothing


def preset_name(program):
    """The HX Stomp's own name for a preset: 01A, 01B, 01C, 02A..."""
    return f"{program // 3 + 1:02d}{'ABC'[program % 3]}"


def tuner_and_tap(d, bank, tuner="4"):
    # The tuner opens on one press and closes on the next
    d.cc(bank, tuner, "TUNR", CC_TUNER, toggle="Y", ch=CHANNEL)
    # Tap sends only on the press; a second message on the release would
    # count as another tap
    d.cc(bank, "D", "TAP", CC_TAP, off=NO_SEND, ch=CHANNEL)


def build():
    d = Demo()
    names = {}

    for bank in range(PRESET_BANKS):
        names[bank] = (preset_name(bank), f"prst {bank:03d}")
        d.on_enter(bank, CommandType="PC",
                   **{"Channel_(PC/CC/Note/PB)": CHANNEL, "Number_(PC/CC/Note)": str(bank)})
        for btn, snapshot in (("1", 1), ("2", 2), ("3", 3)):
            # An exclusive group, so the LED and the display show the
            # snapshot last picked; switching it off sends nothing
            d.cc(bank, btn, f"SNP{snapshot}", CC_SNAPSHOT, on=str(snapshot - 1), off=NO_SEND,
                 toggle="Y", ch=CHANNEL)
            d.group(bank, btn, 1)
        for btn, number, fs in zip(("A", "B", "C"), CC_FS, (1, 2, 3)):
            # Each message presses the footswitch once, which switches
            # whatever is assigned to it
            d.cc(bank, btn, f"FS{fs}", number, toggle="Y", ch=CHANNEL)
        tuner_and_tap(d, bank)

    names[LOOP_BANK] = ("LOOP", "looper")
    d.cc(LOOP_BANK, "1", "REC", CC_LOOP_REC, off=NO_SEND, ch=CHANNEL)
    d.cc(LOOP_BANK, "2", "DUB", CC_LOOP_REC, on="0", off=NO_SEND, ch=CHANNEL)
    d.cc(LOOP_BANK, "3", "PLAY", CC_LOOP_PLAY, toggle="Y", ch=CHANNEL)
    d.cc(LOOP_BANK, "A", "ONCE", CC_LOOP_ONCE, off=NO_SEND, ch=CHANNEL)
    d.cc(LOOP_BANK, "B", "UNDO", CC_LOOP_UNDO, off=NO_SEND, ch=CHANNEL)
    d.cc(LOOP_BANK, "C", "REV", CC_LOOP_REV, toggle="Y", ch=CHANNEL)
    d.cc(LOOP_BANK, "4", "HALF", CC_LOOP_HALF, toggle="Y", ch=CHANNEL)
    d.cc(LOOP_BANK, "D", "TAP", CC_TAP, off=NO_SEND, ch=CHANNEL)

    names[FS_BANK] = ("FS", "stomps")
    for btn, number, fs in zip(("1", "2", "3", "A", "B"), CC_FS, range(1, 6)):
        d.cc(FS_BANK, btn, f"FS{fs}", number, toggle="Y", ch=CHANNEL)
    d.cc(FS_BANK, "C", "SNP-", CC_SNAPSHOT, on="9", off=NO_SEND, ch=CHANNEL)
    d.cc(FS_BANK, "4", "SNP+", CC_SNAPSHOT, on="8", off=NO_SEND, ch=CHANNEL)
    d.cc(FS_BANK, "D", "TUNR", CC_TUNER, toggle="Y", ch=CHANNEL)

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
                ("ConfigName", "HX Stomp"),
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
        note="Line 6 HX Stomp template, generated by make_hx_stomp_template.py",
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
