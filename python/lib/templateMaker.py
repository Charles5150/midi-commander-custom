"""What the make_*_template.py scripts share: the global settings and the CSV.

Each template script builds a make_demo_config.Demo with its device's buttons
and a {bank: (name, info)} dict, then calls write_template.
"""
import os

import pandas as pd

from lib.configCsv import write_config_csv
from lib.configPacker import NUM_BANKS

NO_SEND = "128"         # an off value of 128 sends nothing


def full_range_pedals(d):
    """The expression pedals, calibrated end points left at the full range."""
    for i in (0, 1):
        d.exp.loc[i, ["Min_ADC", "Max_ADC", "Curve", "Invert", "Channel"]] = ["100", "3900", "Linear", "N", "Global"]


def global_settings(name, channel, exp1, exp2, extra=()) -> pd.DataFrame:
    rows = [
        ("MIDI_Channel", channel),
        ("ConfigName", name),
        ("Exp1_CC", exp1),
        ("Exp2_CC", exp2),
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
    ] + list(extra)
    return pd.DataFrame([{"Label": l, "Value": v} for l, v in rows])


def write_template(out, d, names, settings, note, setlist=None):
    """Write the template to `out`; banks missing from `names` stay unnamed.
    `setlist`, the banks Bank Up / Down walk, needs Setlist_Mode Y in `settings`."""
    for name, info in names.values():
        assert len(name) <= 4 and len(info) <= 8, (name, info)     # what the display holds
    for label in d.buttons["Label"]:
        assert len(str(label)) <= 4, label
    banks = pd.DataFrame(
        [
            {"Bank_Number": str(b), "Bank_Name_Large": names.get(b, ("", ""))[0],
             "Bank_Info_Small": names.get(b, ("", ""))[1]}
            for b in range(NUM_BANKS)
        ]
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    write_config_csv(
        out,
        settings,
        banks,
        d.buttons,
        note=note,
        df_long_press=d.long,
        df_double_press=d.double,
        df_bank_expression=d.bank_exp,
        df_expression=d.exp,
        df_bank_enter=d.enter,
        df_sysex=d.sysex,
        df_bank_switch=d.bank_switch_frame,
        df_setlist=None if setlist is None else pd.DataFrame(
            [{"Position": str(i + 1), "Bank_Number": str(b)} for i, b in enumerate(setlist)]),
    )
    print(f"wrote {out}")
    return 0
