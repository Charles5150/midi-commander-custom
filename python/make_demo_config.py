#! env python3
# -*- coding: utf-8 -*-
"""Generate the demo configuration, which exercises every feature.

The result, python/demo-all-features.csv, doubles as a reference for the CSV
format and as a manual test plan: each bank concentrates on one feature and
its button labels say what to expect. Run this again after adding a feature so
the demo keeps covering everything:

    python3 python/make_demo_config.py
"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib.binaryUnpacker import CMD_FIELDS, SLOT_NAMES  # noqa: E402
from lib.configCsv import write_config_csv  # noqa: E402
from lib.configPacker import (  # noqa: E402
    BUTTON_IDS,
    NUM_BANKS,
    empty_bank_enter_settings,
    empty_bank_switch_settings,
    empty_expression_settings,
    empty_sysex_strings,
)

OUT = os.path.join(HERE, "demo-all-features.csv")

# What each bank is for. Banks past the themed ones become a setlist, which is
# what the Bank commands in bank 0 and the long-press bank jumps are for.
BANKS = {
    0: ("HOME", "index"),
    1: ("LOOP", "looper"),
    2: ("FX", "led modes"),
    3: ("PTCH", "prog chg"),
    4: ("KEYS", "keyboard"),
    5: ("MEDI", "media"),
    6: ("TMPO", "tap+clock"),
    7: ("KNOB", "cc+ramp"),
    8: ("SYX", "sysex"),
    9: ("NOTE", "note+bend"),
    10: ("NAV", "bank jump"),
    11: ("MIX", "mixed"),
}
SETLIST_FROM = 12   # banks 12..30 are "songs"
PAGE_BANK = 31      # the second page of the first song
# The order Bank Up/Down follow with Setlist_Mode on: home, then songs out of
# numeric order, which is the point of having a setlist at all
DEMO_SETLIST = [0, 12, 15, 13, 14, 18, 16, 17, 19, 20]


def blank_button_rows():
    """One row per bank/button with every column present and empty."""
    columns = ["Bank_Number", "Button_Identifier", "Label"]
    for slot in SLOT_NAMES:
        columns += [f"{slot}_{f}" for f in CMD_FIELDS]
    columns += ["Light_Mode", "Group", "Momentary_Hold", "Tempo_Flash"]
    columns += [f"{slot}_KeyMode_(Key)" for slot in SLOT_NAMES]

    rows = []
    for bank in range(NUM_BANKS):
        for btn in BUTTON_IDS:
            row = {c: "" for c in columns}
            row.update(
                {
                    "Bank_Number": str(bank),
                    "Button_Identifier": btn,
                    "Label": "",
                    "Light_Mode": "Normal",
                }
            )
            for slot in SLOT_NAMES:
                row[f"{slot}_Toggle_(CC/PB/Note)"] = "N"
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)


class Demo:
    def __init__(self):
        self.buttons = blank_button_rows()
        self.long = empty_long_rows()
        self.double = empty_long_rows()
        from lib.configPacker import empty_bank_expression_settings
        self.bank_exp = empty_bank_expression_settings()
        self.enter = empty_bank_enter_settings()
        self.sysex = empty_sysex_strings()
        self.bank_switch_frame = empty_bank_switch_settings()
        self.exp = empty_expression_settings()

    # --- helpers --------------------------------------------------------
    def _index(self, frame, bank, btn=None):
        mask = frame["Bank_Number"].astype(str) == str(bank)
        if btn is not None:
            mask &= frame["Button_Identifier"].astype(str) == btn
        found = frame[mask]
        assert len(found) == 1, (bank, btn, len(found))
        return found.index[0]

    def button(self, bank, btn, label=None, light=None, slot="A", **fields):
        i = self._index(self.buttons, bank, btn)
        if label is not None:
            self.buttons.at[i, "Label"] = label
        if light is not None:
            self.buttons.at[i, "Light_Mode"] = light
        for key, value in fields.items():
            self.buttons.at[i, f"{slot}_{key}"] = value

    def long_press(self, bank, btn, slot="A", **fields):
        i = self._index(self.long, bank, btn)
        for key, value in fields.items():
            self.long.at[i, f"{slot}_{key}"] = value

    def bank_expression(self, bank, **fields):
        i = self._index(self.bank_exp, bank)
        for key, value in fields.items():
            self.bank_exp.at[i, key] = value

    def double_press(self, bank, btn, slot="A", **fields):
        i = self._index(self.double, bank, btn)
        for key, value in fields.items():
            self.double.at[i, f"{slot}_{key}"] = value

    def bank_switch(self, switch, press, slot="A", **fields):
        """A command on one of the Bank Down/Up switches."""
        frame = self.bank_switch_frame
        mask = (frame["Switch"].astype(str) == switch) & (frame["Press"].astype(str) == press)
        found = frame[mask]
        assert len(found) == 1, (switch, press, len(found))
        i = found.index[0]
        for key, value in fields.items():
            column = f"{slot}_{key}"
            assert column in frame.columns, column
            frame.at[i, column] = value

    def on_enter(self, bank, slot="A", **fields):
        i = self._index(self.enter, bank)
        for key, value in fields.items():
            self.enter.at[i, f"{slot}_{key}"] = value

    # --- shorthands for each command type --------------------------------
    def group(self, bank, btn, group):
        self.buttons.at[self._index(self.buttons, bank, btn), "Group"] = str(group)

    def momentary_hold(self, bank, btn):
        self.buttons.at[self._index(self.buttons, bank, btn), "Momentary_Hold"] = "Y"

    def tempo_flash(self, bank, btn):
        self.buttons.at[self._index(self.buttons, bank, btn), "Tempo_Flash"] = "Y"

    def cc(self, bank, btn, label, number, on="127", off="0", toggle="N", ch="1", light=None, slot="A"):
        self.button(bank, btn, label, light, slot, CommandType="CC",
                    **{"Channel_(PC/CC/Note/PB)": ch, "Number_(PC/CC/Note)": number,
                       "OnValue_(CC/PB)": on, "OffValue_(CC)": off,
                       "Toggle_(CC/PB/Note)": toggle})

    def pc(self, bank, btn, label, program, ch="1", bank_select="", msb="N", slot="A"):
        self.button(bank, btn, label, None, slot, CommandType="PC",
                    **{"Channel_(PC/CC/Note/PB)": ch, "Number_(PC/CC/Note)": program,
                       "BankSelect_(PC)": bank_select, "BankSelectHighByte_(PC)": msb})

    def key(self, bank, btn, label, mods, keyname, mode="Normal", duration="", toggle="N", slot="A"):
        self.button(bank, btn, label, None, slot, CommandType="Key",
                    **{"Number_(PC/CC/Note)": mods, "OnValue_(CC/PB)": keyname,
                       "KeyMode_(Key)": mode, "Duration_(Note/PB)": duration,
                       "Toggle_(CC/PB/Note)": toggle})

    def media(self, bank, btn, label, keyname, slot="A"):
        self.button(bank, btn, label, None, slot, CommandType="Media",
                    **{"OnValue_(CC/PB)": keyname})

    def bank_cmd(self, bank, btn, label, action, value, slot="A"):
        self.button(bank, btn, label, None, slot, CommandType="Bank",
                    **{"KeyMode_(Key)": action, "OnValue_(CC/PB)": str(value)})

    def ccinc(self, bank, btn, label, number, direction, step, start, wrap="N", ch="1", slot="A"):
        self.button(bank, btn, label, None, slot, CommandType="CCInc",
                    **{"Channel_(PC/CC/Note/PB)": ch, "Number_(PC/CC/Note)": number,
                       "KeyMode_(Key)": direction, "OffValue_(CC)": str(step),
                       "OnValue_(CC/PB)": str(start), "Toggle_(CC/PB/Note)": wrap})

    def sysex_cmd(self, bank, btn, label, index, slot="A"):
        self.button(bank, btn, label, None, slot, CommandType="SysEx",
                    **{"Number_(PC/CC/Note)": str(index)})

    def tap(self, bank, btn, label, action, slot="A"):
        self.button(bank, btn, label, None, slot, CommandType="Tap",
                    **{"KeyMode_(Key)": action})

    def note(self, bank, btn, label, number, velocity="100", duration="", toggle="N", ch="1", slot="A"):
        self.button(bank, btn, label, None, slot, CommandType="Note",
                    **{"Channel_(PC/CC/Note/PB)": ch, "Number_(PC/CC/Note)": number,
                       "Velocity_(Note)": velocity, "Duration_(Note/PB)": duration,
                       "Toggle_(CC/PB/Note)": toggle})

    def bend(self, bank, btn, label, amount, duration="", toggle="N", ch="1", slot="A"):
        self.button(bank, btn, label, None, slot, CommandType="PB",
                    **{"Channel_(PC/CC/Note/PB)": ch, "OnValue_(CC/PB)": str(amount),
                       "Duration_(Note/PB)": duration, "Toggle_(CC/PB/Note)": toggle})

    def transport(self, bank, btn, label, kind, slot="A"):
        self.button(bank, btn, label, None, slot, CommandType=kind)


def empty_long_rows():
    from lib.configPacker import empty_long_press_settings

    return empty_long_press_settings()


def build() -> Demo:
    d = Demo()

    # --- bank 0: an index, one button per themed bank ---------------------
    for btn, target, label in (
        ("1", 1, "LOOP"), ("2", 2, "FX"), ("3", 3, "PTCH"), ("4", 4, "KEYS"),
        ("A", 5, "MEDI"), ("B", 6, "TMPO"), ("C", 7, "KNOB"), ("D", 12, "SONG"),
    ):
        d.bank_cmd(0, btn, label, "GoTo", target)
    # Holding a button here jumps further into the setlist
    for btn, target in (("D", 20),):
        d.long_press(0, btn, CommandType="Bank",
                     **{"KeyMode_(Key)": "GoTo", "OnValue_(CC/PB)": str(target)})
    # Hold 1 on HOME to move to the next configuration slot holding one. HOME
    # is where every bank leads back to and where a new configuration starts.
    d.long_press(0, "1", CommandType="Bank", **{"KeyMode_(Key)": "NextConfig"})

    # --- bank 1: looper, the everyday case -------------------------------
    d.cc(1, "1", "REC", "1", toggle="Y", light="AlwaysOn")
    d.cc(1, "2", "PLAY", "2", toggle="Y")
    d.cc(1, "3", "STOP", "3")
    d.cc(1, "4", "UNDO", "4")
    # Long press on UNDO clears the loop: the classic two-function button
    d.long_press(1, "4", CommandType="CC",
                 **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "5",
                    "OnValue_(CC/PB)": "127", "OffValue_(CC)": "0"})
    for btn, number, label in (("A", 6, "TRK1"), ("B", 7, "TRK2"), ("C", 8, "TRK3"), ("D", 9, "TRK4")):
        d.cc(1, btn, label, str(number), toggle="Y")
        # One track at a time: an exclusive group, so selecting a track
        # switches the previous one off
        d.group(1, btn, 1)

    # --- bank 2: the three LED modes, side by side -----------------------
    d.cc(2, "1", "NORM", "10", toggle="Y", light="Normal")
    d.cc(2, "2", "REVS", "11", toggle="Y", light="Reverse")
    d.cc(2, "3", "ALWY", "12", toggle="Y", light="AlwaysOn")
    d.cc(2, "4", "MOMT", "13")                       # momentary, no toggle
    d.cc(2, "A", "DIM", "14", toggle="Y", light="Reverse")
    d.cc(2, "B", "BLNK", "15", toggle="Y", light="AlwaysOn")
    d.cc(2, "C", "HALF", "16", on="64")              # a mid value
    d.cc(2, "D", "NOFF", "17", off="128")            # off value suppressed
    # Scenes on the long presses: 1, 2, 3, A and B are the toggles here, so
    # the scene strings leave 4, C and D alone
    d.long_press(2, "1", CommandType="Scene", **{"OnValue_(CC/PB)": "+++.++.."})   # all on
    d.long_press(2, "4", CommandType="Scene", **{"OnValue_(CC/PB)": "---.--.."})   # all off
    d.long_press(2, "A", CommandType="Scene", **{"OnValue_(CC/PB)": "+-+..-.."})   # a mix
    # MOMT does all three: a tap sends CC 13, holding it is the all-off scene
    # above, and a double press latches CC 18 on and off
    # Expression per bank: here pedal 1 is a modulation wheel instead of CC 11,
    # held between 20 and 100
    d.bank_expression(2, Exp1_CC="1", Exp1_Min="20", Exp1_Max="100")
    d.double_press(2, "4", CommandType="CC",
                   **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "18",
                      "OnValue_(CC/PB)": "127", "OffValue_(CC)": "0", "Toggle_(CC/PB/Note)": "Y"})

    # KNOB silences pedal 1 and moves pedal 2 to CC 7 on channel 2, a volume
    # that never drops below 40
    d.bank_expression(7, Exp1_CC="Off", Exp2_CC="7", Exp2_Channel="2", Exp2_Min="40")

    # --- bank 3: program changes, with and without bank select -----------
    d.pc(3, "1", "P 0", "0")
    d.pc(3, "2", "P 1", "1")
    d.pc(3, "3", "CH 5", "7", ch="5")
    d.pc(3, "4", "CH16", "42", ch="16")
    d.pc(3, "A", "BS 3", "3", bank_select="3")
    d.pc(3, "B", "BSM", "4", bank_select="300", msb="Y")
    # Previous / next preset, moving from whatever program was sent last on
    # the channel: entering this bank sends PC 0, so NEXT goes to 1
    d.button(3, "C", "PREV", None, "A", CommandType="PCInc",
             **{"Channel_(PC/CC/Note/PB)": "1", "KeyMode_(Key)": "Down", "OffValue_(CC)": "1",
                "Number_(PC/CC/Note)": "127", "Toggle_(CC/PB/Note)": "Y"})
    d.button(3, "D", "NEXT", None, "A", CommandType="PCInc",
             **{"Channel_(PC/CC/Note/PB)": "1", "KeyMode_(Key)": "Up", "OffValue_(CC)": "1",
                "Number_(PC/CC/Note)": "127", "Toggle_(CC/PB/Note)": "Y"})
    # Entering this bank already selects a patch
    d.on_enter(3, CommandType="PC",
               **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "0"})

    # --- bank 4: computer keyboard ----------------------------------------
    d.key(4, "1", "SPC", "0", "space")
    d.key(4, "2", "ENTR", "0", "enter")
    d.key(4, "3", "ESC", "0", "esc")
    d.key(4, "4", "TAB", "0", "tab")
    d.key(4, "A", "C+S", "1", "s")                    # Ctrl+S
    d.key(4, "B", "CMDZ", "8", "z")                   # Cmd+Z
    d.key(4, "C", "HOLD", "0", "a", toggle="Y")       # held until next press
    # Down then Up on two slots of one button: a combination built by hand
    d.key(4, "D", "SHFT", "2", "a", mode="Down")
    d.key(4, "D", None, "2", "a", mode="Up", duration="20", slot="B")

    # --- bank 5: media keys ------------------------------------------------
    for btn, name, label in (
        ("1", "play_pause", "PLAY"), ("2", "next", "NEXT"), ("3", "prev", "PREV"),
        ("4", "stop", "STOP"), ("A", "vol_up", "VOL+"), ("B", "vol_down", "VOL-"),
        ("C", "mute", "MUTE"), ("D", "record", "REC"),
    ):
        d.media(5, btn, label, name)
    # Held, the same buttons drive a recorder or a sequencer over MIDI instead
    # of the computer: MIDI Machine Control, Song Select and Song Position
    d.long_press(5, "1", CommandType="MMC", **{"KeyMode_(Key)": "Play"})
    d.long_press(5, "4", CommandType="MMC", **{"KeyMode_(Key)": "Stop"})
    d.long_press(5, "D", CommandType="MMC", **{"KeyMode_(Key)": "Record"})
    # Locate: back to the top, and to 1:02:05 into the song
    d.long_press(5, "A", CommandType="MMC",
                 **{"KeyMode_(Key)": "Locate", "OnValue_(CC/PB)": "0"})
    d.long_press(5, "B", CommandType="MMC",
                 **{"KeyMode_(Key)": "Locate", "OnValue_(CC/PB)": "3725"})
    d.long_press(5, "2", CommandType="Song",
                 **{"KeyMode_(Key)": "Select", "OnValue_(CC/PB)": "2"})
    d.long_press(5, "3", CommandType="Song",
                 **{"KeyMode_(Key)": "Position", "OnValue_(CC/PB)": "0"})

    # --- bank 6: tap tempo and clock ---------------------------------------
    d.tap(6, "1", "TAP", "Tap")
    d.tap(6, "2", "CLK", "Clock")
    d.transport(6, "3", "STRT", "Start")
    d.transport(6, "4", "STOP", "Stop")
    # An LFO locked to the tempo: while TREM is on, CC 14 swings between 127
    # and 40 once every eighth note, a tremolo that follows TAP and the clock
    d.button(6, "A", "TREM", slot="A", CommandType="LFO",
             **{"OnValue_(CC/PB)": "1/8", "KeyMode_(Key)": "Sine"})
    d.cc(6, "A", None, "14", on="127", off="40", toggle="Y", slot="B")
    d.cc(6, "B", "SYNC", "20", toggle="Y")
    # Any button can blink with the beat, not only the ones holding a Tap
    d.tempo_flash(6, "B")
    # The tempo a BPM at a time, faster while held; hold SYNC for 120 BPM
    d.button(6, "C", "BPM+", None, "A", CommandType="Tap",
             **{"KeyMode_(Key)": "Up Repeat", "OffValue_(CC)": "1"})
    d.button(6, "D", "BPM-", None, "A", CommandType="Tap",
             **{"KeyMode_(Key)": "Down Repeat", "OffValue_(CC)": "1"})
    d.long_press(6, "B", CommandType="Tap", **{"KeyMode_(Key)": "Set", "OnValue_(CC/PB)": "120"})
    # Hold STRT for a four note arpeggio, locked to the tempo: two Seq
    # commands hold its four steps, an eighth note each, and the note below
    # them plays one step at a time. Hold it again to stop
    d.long_press(6, "3", CommandType="Seq",
                 **{"OnValue_(CC/PB)": "60 64", "KeyMode_(Key)": "1/8"})
    d.long_press(6, "3", slot="B", CommandType="Seq",
                 **{"OnValue_(CC/PB)": "67 72", "KeyMode_(Key)": "1/8"})
    d.long_press(6, "3", slot="C", CommandType="Note",
                 **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "60",
                    "Velocity_(Note)": "100", "Toggle_(CC/PB/Note)": "Y"})
    # Hold STOP for panic: every sound and note off, on every channel
    d.long_press(6, "4", CommandType="Panic")

    # --- bank 7: relative CC and ramps ---------------------------------------
    # Held down, the volume keeps moving, faster and faster
    d.ccinc(7, "1", "VOL+", "7", "Up Repeat", 2, 64)
    d.ccinc(7, "2", "VOL-", "7", "Down Repeat", 2, 64)
    d.ccinc(7, "3", "PAN+", "10", "Up", 8, 64)
    d.ccinc(7, "4", "PAN-", "10", "Down", 8, 64)
    d.ccinc(7, "A", "WRP+", "11", "Up", 16, 0, wrap="Y")   # wraps past 127
    d.ccinc(7, "B", "WRP-", "11", "Down", 16, 0, wrap="Y")
    # Ramps: a toggle that swells CC 12 up to 127 over 2 s and fades it back
    # down when switched off, and a momentary CC 13 that rises in half a
    # second while held and falls back when let go
    d.button(7, "C", "SWEL", slot="A", CommandType="Ramp", **{"Duration_(Note/PB)": "2000"})
    d.cc(7, "C", None, "12", toggle="Y", slot="B")
    d.button(7, "D", "RISE", slot="A", CommandType="Ramp", **{"Duration_(Note/PB)": "500"})
    d.cc(7, "D", None, "13", slot="B")

    # --- bank 8: stored SysEx ----------------------------------------------
    d.sysex.loc[0, "Bytes"] = "7E 7F 06 01"            # universal device inquiry
    d.sysex.loc[1, "Bytes"] = "41 10 42 12 40 00 7F"   # Roland-style address write
    d.sysex.loc[2, "Bytes"] = "00 20 33 01 00"         # a maker-specific example
    d.sysex_cmd(8, "1", "INQ", 0)
    d.sysex_cmd(8, "2", "ROLD", 1)
    d.sysex_cmd(8, "3", "MAKR", 2)
    d.sysex_cmd(8, "4", "EMPT", 15)                    # empty entry: sends nothing
    d.cc(8, "A", "CC30", "30")
    # Exp commands: while VOL is on, pedal 1 is a volume pedal (CC 7) instead
    # of the wah, and switching it off gives the wah back; P2 X silences pedal 2
    # while it is on
    d.button(8, "B", "P2 X", slot="A", CommandType="Exp",
             **{"OnValue_(CC/PB)": "2", "KeyMode_(Key)": "Off", "Toggle_(CC/PB/Note)": "Y"})
    d.button(8, "C", "VOL", slot="A", CommandType="Exp",
             **{"OnValue_(CC/PB)": "1", "KeyMode_(Key)": "CC", "Number_(PC/CC/Note)": "7",
                "Toggle_(CC/PB/Note)": "Y"})
    # A wah switched by pedal 1 itself (auto-engage, see the pedals below)
    d.cc(8, "D", "WAH", "33", toggle="Y")

    # --- bank 9: notes and pitch bend ---------------------------------------
    d.note(9, "1", "C3", "60")
    d.note(9, "2", "E3", "64")
    d.note(9, "3", "G3", "67")
    d.note(9, "4", "HOLD", "72", toggle="Y")
    d.note(9, "A", "1SEC", "60", duration="100")       # releases after 1 s
    d.bend(9, "B", "UP", 4000)
    d.bend(9, "C", "DOWN", -4000)
    d.bend(9, "D", "BLIP", 8191, duration="20")

    # --- bank 10: bank navigation from buttons -------------------------------
    d.bank_cmd(10, "1", "HOME", "GoTo", 0)
    d.bank_cmd(10, "2", "UP 1", "Up", 1)
    d.bank_cmd(10, "3", "DN 1", "Down", 1)
    d.bank_cmd(10, "4", "UP 8", "Up", 8)
    d.bank_cmd(10, "A", "DN 8", "Down", 8)
    # Back returns to the bank you came from, for a detour and back
    d.bank_cmd(10, "B", "PREV", "Back", "")
    d.bank_cmd(10, "C", "SONG", "GoTo", SETLIST_FROM)
    # A button that sends MIDI and then changes bank: the order matters
    d.cc(10, "D", "GO+C", "40")
    d.button(10, "D", slot="B", CommandType="Bank",
             **{"KeyMode_(Key)": "GoTo", "OnValue_(CC/PB)": "1"})

    # --- bank 11: several commands on one button ------------------------------
    # One press fires a chain: PC, two CCs, a note and a key
    d.pc(11, "1", "ALL5", "5")
    d.cc(11, "1", None, "50", slot="B")
    d.cc(11, "1", None, "51", on="64", slot="C")
    d.note(11, "1", None, "60", duration="10", slot="D")
    d.key(11, "1", None, "0", "1", slot="E")
    # Short press versus long press on the same button
    d.cc(11, "2", "S/L", "52")
    d.long_press(11, "2", CommandType="CC",
                 **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "53",
                    "OnValue_(CC/PB)": "127", "OffValue_(CC)": "0"})
    # Long press with its own toggle, independent of the short press
    d.cc(11, "3", "TGLS", "54", toggle="Y")
    d.long_press(11, "3", CommandType="CC",
                 **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "55",
                    "OnValue_(CC/PB)": "127", "OffValue_(CC)": "0",
                    "Toggle_(CC/PB/Note)": "Y"})
    # A boost that latches on a tap and is momentary when held: hold it for a
    # solo and it goes back off when you let go
    d.cc(11, "4", "BOST", "56", toggle="Y", light="AlwaysOn")
    d.momentary_hold(11, "4")
    d.media(11, "A", "PLAY", "play_pause")
    # Held, the same button mutes three devices at once: the Chan above the CC
    # names the channels it goes out on, whatever the global channel says
    d.long_press(11, "A", CommandType="Chan", **{"Channel_(PC/CC/Note/PB)": "1 2 3"})
    d.long_press(11, "A", slot="B", CommandType="CC",
                 **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "60",
                    "OnValue_(CC/PB)": "127", "OffValue_(CC)": "0",
                    "Toggle_(CC/PB/Note)": "Y"})
    # A pause in the middle of a list: the program change goes out, and the CC
    # follows 200 ms later, once the device has finished loading the patch
    d.pc(11, "B", "WAIT", "6")
    d.button(11, "B", slot="B", CommandType="Wait", **{"Duration_(Note/PB)": "200"})
    d.cc(11, "B", None, "58", slot="C")   # None: keep the label the first slot set
    d.ccinc(11, "C", "NUDG", "57", "Up", 4, 0, wrap="Y")
    # A cycle button: four amp channels on one switch, one per press. Each
    # Cycle command starts the next state and names it on the display
    d.pc(11, "D", "CH A", "0", ch="2")
    for n, (slot, name) in enumerate((("B", "CH B"), ("D", "CH C"), ("F", "CH D")), start=1):
        d.button(11, "D", slot=slot, CommandType="Cycle", **{"OnValue_(CC/PB)": name})
        d.pc(11, "D", None, str(n), ch="2", slot=chr(ord(slot) + 1))
    # Entering the bank switches an effect on, and leaving it switches it off
    # again: the commands below the Leave go out on the way out
    d.on_enter(11, CommandType="CC",
               **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "59",
                  "OnValue_(CC/PB)": "127", "OffValue_(CC)": "0"})
    d.on_enter(11, slot="B", CommandType="Leave")
    d.on_enter(11, slot="C", CommandType="CC",
               **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "59",
                  "OnValue_(CC/PB)": "0", "OffValue_(CC)": "0"})

    # --- banks 12..31: a setlist, each selecting its patch on entry ----------
    for bank in range(SETLIST_FROM, PAGE_BANK):
        n = bank - SETLIST_FROM + 1
        BANKS[bank] = (f"S{n:02d}", f"song {n}")
        d.on_enter(bank, CommandType="PC",
                   **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": str(n)})
        # A usable set of looper controls in every song bank
        d.cc(bank, "1", "REC", "1", toggle="Y", light="AlwaysOn")
        d.cc(bank, "2", "PLAY", "2", toggle="Y")
        d.cc(bank, "3", "STOP", "3")
        d.cc(bank, "4", "UNDO", "4")
        d.bank_cmd(bank, "A", "HOME", "GoTo", 0)
        d.bank_cmd(bank, "B", "PREV", "Down", 1)
        d.bank_cmd(bank, "C", "NEXT", "Up", 1)
        d.tap(bank, "D", "TAP", "Tap")

    # --- bank 31: the first song's second page --------------------------------
    # D on song 1 shows bank 31's buttons in its place, and D there goes back.
    # Entering the page switches CC 70 on and going back switches it off.
    d.bank_cmd(SETLIST_FROM, "D", "PG 2", "Page", PAGE_BANK)
    BANKS[PAGE_BANK] = ("S01", "page 2")
    for btn, number in zip(("1", "2", "3", "4", "A", "B", "C"), range(60, 67)):
        d.cc(PAGE_BANK, btn, f"FX{number - 59}", str(number), toggle="Y")
    d.bank_cmd(PAGE_BANK, "D", "BACK", "Page", SETLIST_FROM)
    d.on_enter(PAGE_BANK, CommandType="CC",
               **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "70",
                  "OnValue_(CC/PB)": "127", "OffValue_(CC)": "0"})
    d.on_enter(PAGE_BANK, slot="B", CommandType="Leave")
    d.on_enter(PAGE_BANK, slot="C", CommandType="CC",
               **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "70",
                  "OnValue_(CC/PB)": "0", "OffValue_(CC)": "0"})

    # --- expression pedals ----------------------------------------------------
    # Pedal 1: plain sweep, and the toe stomps the looper's REC button
    d.exp.loc[0, ["Min_ADC", "Max_ADC", "Curve", "Invert", "Channel"]] = ["100", "3900", "Linear", "N", "Global"]
    # An unused direction is left empty: "None" would come back as a null when
    # the CSV is read again, since pandas treats that word as one.
    d.exp.loc[0, ["Toe_Button", "Toe_Level", "Heel_Button", "Heel_Level"]] = ["1", "115", "", "7"]
    # Auto-engage: leaving the heel switches D on, where it is a toggle (WAH in
    # bank 8, TRK4 in bank 1), and 600 ms resting at the heel switches it off
    d.exp.loc[0, ["Auto_Button", "Auto_Off_ms"]] = ["D", "600"]
    d.exp.loc[1, ["Auto_Button", "Auto_Off_ms"]] = ["", "500"]
    # Pedal 2: logarithmic and inverted, with both switch directions in use
    d.exp.loc[1, ["Min_ADC", "Max_ADC", "Curve", "Invert", "Channel"]] = ["100", "3900", "Log", "Y", "2"]
    d.exp.loc[1, ["Toe_Button", "Toe_Level", "Heel_Button", "Heel_Level"]] = ["C", "110", "D", "5"]
    # Pedal 1 keeps the plain 7-bit CC; pedal 2 sends a 14-bit CC pair, CC 4
    # and 36 (CC 7 and 39 in bank 7)
    d.exp.loc[0, "Output"] = "CC"
    d.exp.loc[1, "Output"] = "CC14"

    # The Bank Down/Up switches send MIDI of their own as well as changing
    # bank, which is what Bank_Switch_Mode = Bank+MIDI means. A host can use
    # these to follow the pedal, and the long presses are a mute and a tuner.
    d.bank_switch("Down", "Short", CommandType="CC",
                  **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "81",
                     "OnValue_(CC/PB)": "127", "OffValue_(CC)": "0",
                     "Toggle_(CC/PB/Note)": "N"})
    d.bank_switch("Up", "Short", CommandType="CC",
                  **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "82",
                     "OnValue_(CC/PB)": "127", "OffValue_(CC)": "0",
                     "Toggle_(CC/PB/Note)": "N"})
    # Long press Down: latching mute, so the toggle sends 127 then 0
    d.bank_switch("Down", "Long", CommandType="CC",
                  **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "83",
                     "OnValue_(CC/PB)": "127", "OffValue_(CC)": "0",
                     "Toggle_(CC/PB/Note)": "Y"})
    # Long press Up: tuner on the host, plus a program change to a clean patch
    d.bank_switch("Up", "Long", CommandType="CC",
                  **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "84",
                     "OnValue_(CC/PB)": "127", "OffValue_(CC)": "0",
                     "Toggle_(CC/PB/Note)": "Y"})
    d.bank_switch("Up", "Long", slot="B", CommandType="PC",
                  **{"Channel_(PC/CC/Note/PB)": "1", "Number_(PC/CC/Note)": "0",
                     "BankSelect_(PC)": "", "BankSelectHighByte_(PC)": "N"})

    return d


def global_settings() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Label": l, "Value": v}
            for l, v in (
                ("MIDI_Channel", "1"),
                ("RealTime_Passthrough", "Y"),
                ("ConfigName", "DEMO ALL"),
                ("Exp1_CC", "11"),
                ("Exp2_CC", "4"),
                ("Bank_Up_LED_Mode", "Normal"),
                ("Bank_Down_LED_Mode", "Normal"),
                ("USB_MIDI_Thru", "Y"),
                ("Remember_State", "Y"),
                ("Long_Press_ms", "500"),
                ("LED_Brightness", "100"),
                ("LED_Rest_Brightness", "25"),
                ("Bank_Jump_Step", "8"),
                ("Bank_Change_Mode", "CC"),
                ("Bank_Change_Channel", "Any"),
                ("Bank_Change_CC", "32"),
                ("Bank_Switch_Mode", "Bank+MIDI"),
                ("Sleep_After_Min", "15"),
                ("Setlist_Mode", "Y"),
                ("Clock_Follow", "Y"),
                ("LED_Feedback", "Y"),
                ("Double_Press_ms", "300"),
                ("Remote_Mode", "CC"),
                ("Remote_Channel", "16"),
                ("Remote_First", "102"),
                ("Global_Channel", "Off"),
            )
        ]
    )


def main() -> int:
    d = build()
    banks = pd.DataFrame(
        [
            {"Bank_Number": str(b), "Bank_Name_Large": BANKS[b][0], "Bank_Info_Small": BANKS[b][1]}
            for b in range(NUM_BANKS)
        ]
    )
    write_config_csv(
        OUT,
        global_settings(),
        banks,
        d.buttons,
        note="Demo configuration, generated by make_demo_config.py: every feature in use",
        df_long_press=d.long,
        df_double_press=d.double,
        df_bank_expression=d.bank_exp,
        df_expression=d.exp,
        df_bank_enter=d.enter,
        df_sysex=d.sysex,
        df_bank_switch=d.bank_switch_frame,
        df_setlist=pd.DataFrame(
            [{"Position": str(i + 1), "Bank_Number": str(b)} for i, b in enumerate(DEMO_SETLIST)],
            columns=["Position", "Bank_Number"],
        ),
    )
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
