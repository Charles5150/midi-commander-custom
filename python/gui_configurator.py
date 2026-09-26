"""GUI configurator for the Midi Commander custom firmware.

Edits the sectioned configuration CSV (see lib/configCsv.py), reads the
configuration back from the device and flashes it. Every field with a bounded
set of values is a drop-down or a check box; numeric fields only accept
numbers inside their valid range.
"""

import collections
import datetime
import os
import re
import subprocess
import tempfile
import sys
from tkinter import filedialog, messagebox

import tkinter as tk

import customtkinter as ctk
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib.cmdBinaryPacker import (  # noqa: E402
    EXP_TARGETS, HID_SPECIAL_KEYS, LFO_DIVISIONS, LFO_SHAPES, MEDIA_KEYS, RAMP_MAX_MS,
    MMC_COMMANDS, MMC_LOCATE_MAX, SONG_MODES, SONG_POSITION_MAX,
    VAR_MODES, VAR_COUNT, VAR_DEFAULT_TOP, IF_TESTS, IF_BUTTON_TESTS, IF_VALUE_TESTS,
    SCENE_BUTTONS, MACRO_LISTS,
)
from lib.configCsv import read_config_csv, write_config_csv  # noqa: E402
from lib.configPacker import NUM_BANKS, BUTTON_IDS  # noqa: E402
from lib.configPacker import (  # noqa: E402
    BANK_ENTER_SECTION,
    BANK_SWITCH_SECTION,
    BANK_SWITCH_LISTS,
    SYSEX_SECTION,
    SYSEX_STRING_COUNT,
    empty_bank_enter_settings,
    empty_bank_switch_settings,
    SETLIST_SECTION,
    SETLIST_MAX,
    BANK_EXPRESSION_SECTION,
    BANK_EXP_COLUMNS,
    empty_bank_expression_settings,
    empty_setlist,
    empty_sysex_strings,
    COMBO_SECTION,
    COMBO_COUNT,
    COMBO_COLUMNS,
    empty_combos,
    parse_sysex_bytes,
)
from lib.configPacker import (  # noqa: E402
    EXPRESSION_SECTION,
    LONG_PRESS_SECTION,
    DOUBLE_PRESS_SECTION,
    empty_expression_settings,
    empty_long_press_settings,
    empty_double_press_settings,
)
from lib.midiDevice import (  # noqa: E402
    LED_LEVELS, SCREEN_HEIGHT, SCREEN_VISIBLE_WIDTH, VIRTUAL_SWITCHES, DeviceNotFound, DeviceTimeout,
    BANNER_TEXT_MAX, MidiCommander, banner_sysex, screen_rows, version_at_least,
)
from lib import bankClipboard as bank_clipboard  # noqa: E402
from lib import bankReorder as bank_reorder  # noqa: E402
from lib import midiLearn as midi_learn  # noqa: E402
from lib import midiMonitor as midi_monitor  # noqa: E402
from lib.firmwareUpdate import UpdateError, check_image  # noqa: E402

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# --- Look -------------------------------------------------------------------
# One palette and one type scale for the whole window. Blue is kept for actions,
# red for the one that writes to the pedal, green for Apply; values sit in a
# neutral grey so they no longer look like buttons.
BG = "#1c1c1e"
SIDEBAR_BG = "#161618"
CARD = "#242426"
CARD_EDGE = "#333336"
CARD_RAISED = "#2c2c2e"
FIELD = "#3a3a3c"
FIELD_HOVER = "#48484a"
FIELD_BUTTON = "#48484a"
FIELD_BUTTON_HOVER = "#5a5a5e"
ACCENT = "#0a84ff"
ACCENT_HOVER = "#0071e3"
DANGER = "#e5484d"
DANGER_HOVER = "#c93b40"
SUCCESS = "#2e9d57"
SUCCESS_HOVER = "#257f46"
TEXT = "#f2f2f7"
MUTED = "#98989f"
WARN = "#ff9f0a"

FONT_TITLE = ("", 20, "bold")
FONT_HEADING = ("", 15, "bold")
FONT_BODY = ("", 13)
FONT_SMALL = ("", 12)
FONT_SECTION = ("", 11, "bold")


def _apply_theme():
    t = ctk.ThemeManager.theme

    def both(widget, **kw):
        for key, color in kw.items():
            t[widget][key] = [color, color]

    both("CTk", fg_color=BG)
    both("CTkToplevel", fg_color=BG)
    both("CTkFrame", fg_color=CARD, top_fg_color=CARD, border_color=CARD_EDGE)
    both("CTkScrollableFrame", label_fg_color=CARD)
    both("CTkButton", fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#ffffff",
         text_color_disabled="#6e6e73", border_color=CARD_EDGE)
    both("CTkOptionMenu", fg_color=FIELD, button_color=FIELD_BUTTON,
         button_hover_color=FIELD_BUTTON_HOVER, text_color=TEXT, text_color_disabled="#6e6e73")
    both("CTkComboBox", fg_color=FIELD, border_color=FIELD_BUTTON, button_color=FIELD_BUTTON,
         button_hover_color=FIELD_BUTTON_HOVER, text_color=TEXT)
    both("CTkEntry", fg_color=FIELD, border_color=FIELD_BUTTON, text_color=TEXT)
    both("CTkCheckBox", fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=FIELD_BUTTON_HOVER,
         checkmark_color="#ffffff", text_color=TEXT)
    both("CTkSegmentedButton", fg_color=FIELD, selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
         unselected_color=FIELD, unselected_hover_color=FIELD_HOVER, text_color=TEXT)
    both("CTkLabel", text_color=TEXT)
    both("CTkProgressBar", fg_color=FIELD, progress_color=ACCENT, border_color=FIELD)
    both("DropdownMenu", fg_color=CARD, hover_color=FIELD_HOVER, text_color=TEXT)


_apply_theme()


class Help(ctk.CTkFrame):
    """A one line summary, with the full explanation behind a small "?" toggle."""

    def __init__(self, master, summary, details=None, wraplength=780):
        super().__init__(master, fg_color="transparent")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(anchor="w", fill="x")
        ctk.CTkLabel(row, text=summary, text_color=MUTED, font=FONT_BODY, justify="left",
                     wraplength=wraplength).pack(side="left")
        self.details = None
        if details:
            self.details = ctk.CTkLabel(self, text=details, text_color=MUTED, font=FONT_SMALL,
                                        justify="left", wraplength=wraplength)
            self.toggle = ctk.CTkButton(row, text="?", width=22, height=22, corner_radius=11,
                                        fg_color=FIELD, hover_color=FIELD_HOVER, font=FONT_SECTION,
                                        command=self._toggle)
            self.toggle.pack(side="left", padx=8)

    def _toggle(self):
        if self.details.winfo_ismapped():
            self.details.pack_forget()
        else:
            self.details.pack(anchor="w", pady=(4, 0))

# Loaded at start: the demo covers every feature, so it doubles as the
# reference for how anything is configured.
DEFAULT_CSV = os.path.join(HERE, "demo-all-features.csv")
TEMPLATES_DIR = os.path.join(HERE, "templates")
# Files that ship with the tools. They open as a starting point: saving one
# asks where to put the copy, so the originals are never overwritten.
REFERENCE_CSVS = (DEFAULT_CSV, os.path.join(HERE, "MeloConfig_10_Cmds - RC-600.csv"))


def is_reference_csv(path):
    """True for the demo, the sample and the templates that come with the tools."""
    real = os.path.realpath(path)
    return (real in {os.path.realpath(p) for p in REFERENCE_CSVS}
            or os.path.dirname(real) == os.path.realpath(TEMPLATES_DIR))

# --- Value sets -------------------------------------------------------------
LED_MODES = ["Normal", "Reverse", "AlwaysOn"]
BUTTON_GROUPS = ["None", "1", "2", "3", "4"]
CHANNELS = [str(i) for i in range(1, 17)]
NO_COMMAND = "(none)"
COMMAND_TYPES = [NO_COMMAND, "PC", "PCInc", "CC", "Note", "PB", "CCInc", "Key", "Media", "Bank", "SysEx", "Tap", "Start", "Stop", "MMC", "Song", "Panic", "Scene", "Wait", "Ramp", "LFO", "Seq", "Exp", "Chan", "Value", "If", "Macro", "Listen"]
# Cycle splits a button's short press list into states, so only that list offers it
SHORT_COMMAND_TYPES = COMMAND_TYPES + ["Cycle"]
# Leave splits a bank's enter list into the commands on entering and on leaving
ENTER_COMMAND_TYPES = COMMAND_TYPES + ["Leave"]
TAP_MODES = ["Tap", "Clock", "Set", "Up", "Down", "Up Repeat", "Down Repeat"]
# MIDI Machine Control actions, and which of the two song messages to send
MMC_ACTIONS = list(MMC_COMMANDS.keys())
# A scene leaves a button alone, or switches it on or off
SCENE_STATES = ["-", "On", "Off"]
BANK_SWITCH_MODES = ["Bank", "Bank+MIDI", "MIDI only"]
BANK_SWITCH_CHOICES = [f"{sw} / {pr}" for sw, pr in BANK_SWITCH_LISTS]
CCINC_DIRECTIONS = ["Up", "Down", "Up Repeat", "Down Repeat"]
BANK_MODES = ["GoTo", "Up", "Down", "Config", "NextConfig", "Page", "Back"]
CONFIG_SLOT_NAMES = ["1", "2", "3", "4"]
# Which configuration slot Read and Flash use; "Active" lets the pedal decide
SLOT_TARGETS = ["Active"] + CONFIG_SLOT_NAMES
BANKS = [str(i) for i in range(32)]
MEDIA_NAMES = list(MEDIA_KEYS.keys())
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

BOLD = ("", 13, "bold")
MONO = ("Menlo", 12) if sys.platform == "darwin" else ("Consolas", 11) if sys.platform == "win32" else ("DejaVu Sans Mono", 11)

# --- MIDI monitor -----------------------------------------------------------
MONITOR_POLL_MS = 50
MONITOR_ALL_PORTS = "All inputs"
MONITOR_HEADING = f"{'time':>9} {'since':>9}  {'port':<22}  {'chan':<5}  {'message':<38}  bytes"

# Virtual pedal, drawn like the pedal: five switches a row, 1-4 and Bank Up on
# top with their LEDs below, A-D and Bank Down underneath with their LEDs above,
# and the display between the rows, in the middle of the pedal.
PEDAL_ROWS = [["1", "2", "3", "4", "UP"], ["A", "B", "C", "D", "DOWN"]]
PEDAL_CAPTIONS = {"UP": "BANK \u25b2", "DOWN": "BANK \u25bc"}
PEDAL_COL_X = [110, 270, 430, 590, 750]
PEDAL_W, PEDAL_H = 860, 590
PEDAL_TOP_SWITCH_Y, PEDAL_TOP_LED_Y = 95, 168
PEDAL_BOT_LED_Y, PEDAL_BOT_SWITCH_Y = 422, 495
PEDAL_SCREEN_ZOOM = 3
PEDAL_SCREEN_CENTER = (PEDAL_W // 2, (PEDAL_TOP_LED_Y + PEDAL_BOT_LED_Y) // 2)
PEDAL_BG = "#242426"            # the tab behind the pedal (CARD)
PEDAL_BODY = "#1c1c1e"
PEDAL_BODY_EDGE = "#3a3a3c"
PEDAL_RING = "#3a3a3c"
PEDAL_NUT = "#7c7c80"
PEDAL_CAP = "#d1d1d6"
PEDAL_CAP_DOWN = "#8e8e93"
PEDAL_NUT_DOWN = "#5a5a5e"
PEDAL_LED_OFF = (0x2c, 0x2c, 0x2e)
PEDAL_LED_ON = (0xff, 0x45, 0x3a)
PEDAL_PIXEL_ON = "#eef6ff"
PEDAL_PIXEL_OFF = "#040506"
PEDAL_STATE_EVERY = 2   # poll the pedal state on every second live view tick (120 ms)


def blend(a, b, t) -> str:
    rgb = [round(x + (y - x) * max(0.0, min(1.0, t))) for x, y in zip(a, b)]
    return "#%02x%02x%02x" % tuple(rgb)


def led_color(level) -> str:
    """Screen colour for an LED at a PWM level 0..LED_LEVELS."""
    return blend(PEDAL_LED_OFF, PEDAL_LED_ON, level / LED_LEVELS)


def hex_rgb(color: str):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def clean(val) -> str:
    """CSV cell -> clean string: NaN/None -> '', '5.0' -> '5'."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if s.lower() == "nan":
        return ""
    if s.endswith(".0") and s[:-2].lstrip("-").isdigit():
        s = s[:-2]
    return s


def to_int(val, default=0) -> int:
    try:
        return int(float(clean(val)))
    except ValueError:
        return default


def is_yes(val) -> bool:
    return clean(val).upper().startswith("Y")


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
    ]),
    ("Banks", [
        ("Bank_Switch_Mode", "Bank switches", "what Bank Up / Down do, see the Bank Switch tab"),
        ("Bank_Jump_Step", "Long press jumps", "banks, 1-31"),
        ("Bank_Preview", "Preview banks", "seconds a bank shown by Bank Up / Down waits for a button to confirm it, 0 = off"),
        ("Setlist_Mode", "Follow the setlist", "Bank Up / Down use the order in the Setlist tab"),
        ("Bank_Change_Mode", "Change bank from MIDI", "an incoming PC or CC selects the bank"),
        ("Bank_Change_Channel", "\u2026 listening on channel", ""),
        ("Bank_Change_CC", "\u2026 with CC number", "when the mode is CC"),
        ("Global_Bank", "Global buttons bank", "the bank the buttons marked Global take everything from"),
    ]),
    ("USB MIDI", [
        ("USB_MIDI_Thru", "USB to DIN thru", "forward notes, CC, PC and other devices' SysEx"),
        ("RealTime_Passthrough", "Clock and transport thru", "forward Clock, Start, Continue and Stop"),
        ("Clock_Follow", "Follow the host's clock", "adopt the tempo of MIDI clock from USB"),
        ("Remote_Mode", "Press from the computer", "CC or notes from USB press the switches"),
        ("Remote_Channel", "\u2026 listening on channel", ""),
        ("Remote_First", "\u2026 from number", "1 2 3 4 A B C D, Bank Down, Bank Up take ten in a row"),
        ("Kemper_Mode", "Talk to a Kemper", "the rig name on the display and the modules on the LEDs"),
    ]),
    ("Power", [
        ("Sleep_After_Min", "Sleep after", "idle minutes before the display and LEDs go out, 0 = never"),
    ]),
]


# --- Validated widgets ------------------------------------------------------
class IntEntry(ctk.CTkEntry):
    """Entry that only accepts integers and clamps them to [lo, hi] on focus out."""

    def __init__(self, master, lo: int, hi: int, value="", width=60):
        vcmd = (master.register(self._validate), "%P")
        super().__init__(master, width=width, validate="key", validatecommand=vcmd)
        self.lo, self.hi = lo, hi
        value = clean(value)
        if value:
            self.insert(0, str(max(lo, min(hi, to_int(value)))))
        self.bind("<FocusOut>", lambda _e: self.value())

    def _validate(self, text: str) -> bool:
        if text == "":
            return True
        if text == "-":
            return self.lo < 0
        try:
            int(text)
        except ValueError:
            return False
        return True

    def value(self) -> str:
        text = self.get().strip()
        if text in ("", "-"):
            return ""
        clamped = str(max(self.lo, min(self.hi, int(text))))
        if clamped != text:
            self.delete(0, "end")
            self.insert(0, clamped)
        return clamped


class TextEntry(ctk.CTkEntry):
    """Entry limited to max_len characters."""

    def __init__(self, master, max_len: int, value="", width=150):
        vcmd = (master.register(lambda t: len(t) <= max_len), "%P")
        super().__init__(master, width=width, validate="key", validatecommand=vcmd)
        value = clean(value)[:max_len]
        if value:
            self.insert(0, value)

    def value(self) -> str:
        return self.get()


class Check(ctk.CTkCheckBox):
    def __init__(self, master, text="", checked=False, width=20):
        super().__init__(master, text=text, width=width)
        if checked:
            self.select()

    def value(self) -> str:
        return "Y" if self.get() == 1 else "N"


class Option(ctk.CTkOptionMenu):
    def __init__(self, master, values, value=None, width=90, command=None):
        super().__init__(master, values=values, width=width, command=command)
        value = clean(value)
        self.set(value if value in values else values[0])

    def value(self) -> str:
        return self.get()


class Combo(ctk.CTkComboBox):
    def __init__(self, master, values, value="", width=100):
        super().__init__(master, values=values, width=width)
        self.set(clean(value))

    def value(self) -> str:
        return self.get().strip()


# --- MIDI learn -------------------------------------------------------------
LEARN_SECONDS = 15
LEARN_POLL_MS = 40


class LearnSession:
    """One command listening for the MIDI it should send; one at a time."""

    editor = None
    listener = None
    root = None
    deadline = 0
    # Counts the sessions, so a poll left over from a stopped one does nothing
    session = 0

    @classmethod
    def toggle(cls, editor):
        was = cls.editor
        cls.stop()
        if was is editor:
            return
        try:
            cls.listener = midi_learn.Listener()
        except Exception as e:
            messagebox.showerror("MIDI learn", f"Cannot open the MIDI inputs: {e}")
            return
        if not cls.listener.ports:
            cls.listener.close()
            cls.listener = None
            messagebox.showinfo("MIDI learn", "The computer has no MIDI input to listen to.")
            return
        cls.editor = editor
        cls.root = editor.frame.winfo_toplevel()
        cls.deadline = LEARN_SECONDS * 1000
        cls.session += 1
        editor.learning(True)
        cls.root.after(LEARN_POLL_MS, cls._poll, cls.session)

    @classmethod
    def stop(cls):
        if cls.listener is not None:
            cls.listener.close()
            cls.listener = None
        if cls.editor is not None:
            editor, cls.editor = cls.editor, None
            editor.learning(False)

    @classmethod
    def _poll(cls, session):
        editor = cls.editor
        if session != cls.session or editor is None or cls.listener is None:
            return
        if not editor.frame.winfo_exists():
            cls.editor = None
            cls.stop()
            return
        got = cls.listener.poll()
        if got is not None:
            cls.stop()
            editor.learn(*got)
            return
        cls.deadline -= LEARN_POLL_MS
        if cls.deadline <= 0:
            cls.stop()
            editor.learned_text("nothing arrived")
            return
        cls.root.after(LEARN_POLL_MS, cls._poll, session)


# --- Slot editor ------------------------------------------------------------
class SlotEditor:
    """One row of the button editor: command type plus the fields it needs."""

    def __init__(self, parent, slot: str, initial: dict, types=COMMAND_TYPES):
        self.slot = slot
        self.initial = initial
        self.widgets = {}

        self.frame = ctk.CTkFrame(parent, fg_color="transparent", height=36)
        self.frame.pack(fill="x", padx=6, pady=1, anchor="w")

        ctk.CTkLabel(self.frame, text=slot, width=24, font=BOLD).pack(
            side="left", padx=(0, 4)
        )
        cmd_type = clean(initial.get("CommandType")) or NO_COMMAND
        self.type_menu = Option(
            self.frame, types, cmd_type, width=80, command=self._rebuild
        )
        self.type_menu.pack(side="left", padx=4)
        self.learn_button = ctk.CTkButton(
            self.frame, text="Learn", width=52, fg_color=FIELD, hover_color=FIELD_HOVER,
            command=lambda: LearnSession.toggle(self),
        )
        self.learn_button.pack(side="left", padx=(0, 4))

        # A frame with no children keeps its configured size instead of
        # shrinking, so give it a small one for slots without parameters.
        self.params = ctk.CTkFrame(self.frame, fg_color="transparent", width=10, height=30)
        self.params.pack(side="left")
        self._rebuild(self.type_menu.get())

    # MIDI learn ------------------------------------------------------------
    def learning(self, on: bool):
        if self.learn_button.winfo_exists():
            self.learn_button.configure(
                text="Stop" if on else "Learn",
                fg_color=WARN if on else FIELD,
                hover_color=WARN if on else FIELD_HOVER,
            )
        if on:
            self.learned_text(f"listening, {LEARN_SECONDS} s")
        elif getattr(self, "learn_note", None) is not None and self.learn_note.winfo_exists():
            self.learn_note.destroy()

    def learned_text(self, text: str):
        """A note on what learn heard, shown in the slot until it is rebuilt."""
        if getattr(self, "learn_note", None) is not None and self.learn_note.winfo_exists():
            self.learn_note.destroy()
        self.learn_note = ctk.CTkLabel(self.params, text=f"({text})", text_color=MUTED)
        self.learn_note.pack(side="left", padx=8)

    def learn(self, port: str, msg):
        """Fill the command from a message that arrived on `port`."""
        fields = midi_learn.learned_fields(msg, self.values())
        cmd_type = fields["CommandType"]
        if cmd_type not in self.type_menu.cget("values"):
            self.learned_text(f"{midi_learn.describe(msg)}: not a command for this list")
            return
        self.initial = fields
        self.type_menu.set(cmd_type)
        self._rebuild(cmd_type)
        # The fields show the type and channel; say what arrived and where from
        self.learned_text(f"{midi_learn.describe(msg, channel=False)} from {port}")

    # Small builders --------------------------------------------------------
    def _label(self, text):
        ctk.CTkLabel(self.params, text=text).pack(side="left", padx=(8, 2))

    def _channel(self):
        self._label("Ch")
        w = Option(self.params, CHANNELS, self.initial.get("Channel_(PC/CC/Note/PB)"), width=60)
        w.pack(side="left")
        self.widgets["channel"] = w

    def _int(self, key, label, field, lo, hi, width=55):
        self._label(label)
        w = IntEntry(self.params, lo, hi, self.initial.get(field), width=width)
        w.pack(side="left")
        self.widgets[key] = w

    def _check(self, key, text, field):
        w = Check(self.params, text=text, checked=is_yes(self.initial.get(field)), width=20)
        w.pack(side="left", padx=(10, 0))
        self.widgets[key] = w

    def _remode(self, cmd_type: str, mode: str):
        """A menu that changes the fields shown: keep the choice across the rebuild."""
        self.initial = dict(self.initial, **{"KeyMode_(Key)": mode})
        self._rebuild(cmd_type)

    def _rebuild(self, cmd_type: str):
        for w in self.params.winfo_children():
            w.destroy()
        self.widgets = {}

        if cmd_type == "PC":
            self._channel()
            self._int("number", "Program", "Number_(PC/CC/Note)", 0, 127)
            self._int("bank", "BankSel", "BankSelect_(PC)", 0, 16383, width=65)
            self._check("bank_msb", "Send bank MSB", "BankSelectHighByte_(PC)")
        elif cmd_type == "CC":
            self._channel()
            self._int("number", "CC#", "Number_(PC/CC/Note)", 0, 127)
            self._int("on", "On", "OnValue_(CC/PB)", 0, 127)
            self._int("off", "Off", "OffValue_(CC)", 0, 127)
            self._check("toggle", "Toggle", "Toggle_(CC/PB/Note)")
        elif cmd_type == "Note":
            self._channel()
            self._int("number", "Note", "Number_(PC/CC/Note)", 0, 127)
            self._int("velocity", "Vel", "Velocity_(Note)", 0, 127)
            self._int("duration", "Dur", "Duration_(Note/PB)", 0, 127)
            self._check("toggle", "Toggle", "Toggle_(CC/PB/Note)")
        elif cmd_type == "PB":
            self._channel()
            self._int("on", "Bend", "OnValue_(CC/PB)", -8192, 8191, width=65)
            self._int("duration", "Dur", "Duration_(Note/PB)", 0, 127)
            self._check("toggle", "Toggle", "Toggle_(CC/PB/Note)")
        elif cmd_type == "Key":
            mask = to_int(self.initial.get("Number_(PC/CC/Note)"))
            for name, bit in MODIFIERS:
                w = Check(self.params, text=name, checked=bool(mask & bit), width=20)
                w.pack(side="left", padx=(6, 0))
                self.widgets[f"mod_{bit}"] = w
            self._label("Key")
            w = Combo(self.params, KEY_NAMES, self.initial.get("OnValue_(CC/PB)"), width=85)
            w.pack(side="left")
            self.widgets["key"] = w
            self._label("Mode")
            w = Option(self.params, KEY_MODES, self.initial.get("KeyMode_(Key)"), width=78)
            w.pack(side="left")
            self.widgets["keymode"] = w
            self._int("duration", "Dur", "Duration_(Note/PB)", 0, 127, width=50)
            self._check("toggle", "Hold", "Toggle_(CC/PB/Note)")
        elif cmd_type == "CCInc":
            self._channel()
            self._int("number", "CC#", "Number_(PC/CC/Note)", 0, 127)
            self._label("Dir")
            w = Option(self.params, CCINC_DIRECTIONS, self.initial.get("KeyMode_(Key)"), width=110)
            w.pack(side="left")
            self.widgets["ccincdir"] = w
            self._int("step", "Step", "OffValue_(CC)", 1, 127, width=50)
            self._int("on", "Start", "OnValue_(CC/PB)", 0, 127, width=55)
            self._check("toggle", "Wrap", "Toggle_(CC/PB/Note)")
        elif cmd_type == "PCInc":
            self._channel()
            self._label("Dir")
            w = Option(self.params, CCINC_DIRECTIONS, self.initial.get("KeyMode_(Key)"), width=110)
            w.pack(side="left")
            self.widgets["ccincdir"] = w
            self._int("step", "Step", "OffValue_(CC)", 1, 127, width=50)
            self._label("Last")
            w = IntEntry(self.params, 0, 127, clean(self.initial.get("Number_(PC/CC/Note)")) or "127", width=50)
            w.pack(side="left")
            self.widgets["number"] = w
            self._check("toggle", "Wrap", "Toggle_(CC/PB/Note)")
        elif cmd_type == "Tap":
            self._label("Action")
            w = Option(self.params, TAP_MODES, self.initial.get("KeyMode_(Key)"), width=110,
                       command=lambda v: self._remode("Tap", v))
            w.pack(side="left")
            self.widgets["tapmode"] = w
            mode = w.get()
            if mode == "Set":
                self._label("BPM")
                v = IntEntry(self.params, 30, 300, self.initial.get("OnValue_(CC/PB)") or "120", width=55)
                v.pack(side="left")
                self.widgets["bpm"] = v
            elif mode.startswith(("Up", "Down")):
                self._label("Step")
                v = IntEntry(self.params, 1, 127, self.initial.get("OffValue_(CC)") or "1", width=50)
                v.pack(side="left")
                self.widgets["step"] = v
            else:
                ctk.CTkLabel(
                    self.params,
                    text="(Tap sets the tempo, Clock starts/stops the MIDI clock)",
                    text_color=MUTED,
                ).pack(side="left", padx=8)
        elif cmd_type == "SysEx":
            self._label("String")
            w = Option(self.params, [str(i) for i in range(SYSEX_STRING_COUNT)],
                       self.initial.get("Number_(PC/CC/Note)"), width=70)
            w.pack(side="left")
            self.widgets["sysexindex"] = w
            ctk.CTkLabel(self.params, text="(edit the bytes in the SysEx tab)",
                         text_color=MUTED).pack(side="left", padx=8)
        elif cmd_type == "Bank":
            self._label("Action")
            w = Option(self.params, BANK_MODES, self.initial.get("KeyMode_(Key)"), width=80,
                       command=lambda v: self._remode("Bank", v))
            w.pack(side="left")
            self.widgets["bankmode"] = w
            mode = w.get()
            v = None
            if mode in ("GoTo", "Page"):
                self._label("Bank")
                v = Option(self.params, BANKS, self.initial.get("OnValue_(CC/PB)"), width=70)
            elif mode == "Config":
                self._label("Slot")
                v = Option(self.params, CONFIG_SLOT_NAMES, self.initial.get("OnValue_(CC/PB)") or "1", width=60)
            elif mode == "NextConfig":
                ctk.CTkLabel(self.params, text="(next slot holding a configuration)",
                             text_color=MUTED).pack(side="left", padx=8)
            elif mode == "Back":
                ctk.CTkLabel(self.params, text="(the bank you came from)",
                             text_color=MUTED).pack(side="left", padx=8)
            else:
                self._label("Banks")
                v = IntEntry(self.params, 1, 31, self.initial.get("OnValue_(CC/PB)") or "8", width=55)
            if v is not None:
                v.pack(side="left")
                self.widgets["bankvalue"] = v
        elif cmd_type == "MMC":
            self._label("Action")
            w = Option(self.params, MMC_ACTIONS, self.initial.get("KeyMode_(Key)") or "Play",
                       width=115, command=lambda v: self._remode("MMC", v))
            w.pack(side="left")
            self.widgets["mmcaction"] = w
            if w.get() == "Locate":
                self._label("At (s)")
                v = IntEntry(self.params, 0, MMC_LOCATE_MAX,
                             clean(self.initial.get("OnValue_(CC/PB)")) or "0", width=60)
                v.pack(side="left")
                self.widgets["mmcvalue"] = v
            ctk.CTkLabel(self.params, text="(MIDI Machine Control, to every device)",
                         text_color=MUTED).pack(side="left", padx=8)
        elif cmd_type == "Song":
            self._label("Send")
            w = Option(self.params, SONG_MODES, self.initial.get("KeyMode_(Key)") or "Select",
                       width=90, command=lambda v: self._remode("Song", v))
            w.pack(side="left")
            self.widgets["songmode"] = w
            position = w.get() == "Position"
            self._label("Beat" if position else "Song")
            v = IntEntry(self.params, 0, SONG_POSITION_MAX if position else 127,
                         clean(self.initial.get("OnValue_(CC/PB)")) or "0", width=60)
            v.pack(side="left")
            self.widgets["songvalue"] = v
            ctk.CTkLabel(
                self.params,
                text="(sixteenth notes from the start)" if position else "(song number)",
                text_color=MUTED,
            ).pack(side="left", padx=8)
        elif cmd_type == "Media":
            self._label("Key")
            w = Option(self.params, MEDIA_NAMES, self.initial.get("OnValue_(CC/PB)"), width=130)
            w.pack(side="left")
            self.widgets["media"] = w
            self._int("duration", "Dur", "Duration_(Note/PB)", 0, 127, width=50)
            self._check("toggle", "Hold", "Toggle_(CC/PB/Note)")
        elif cmd_type == "Scene":
            text = clean(self.initial.get("OnValue_(CC/PB)"))
            names = {"+": "On", "-": "Off"}
            for i, button in enumerate("1234ABCD"):
                ch = text[i] if i < len(text) else "."
                self._label(button)
                w = Option(self.params, SCENE_STATES, names.get(ch, SCENE_STATES[0]), width=62)
                w.pack(side="left")
                self.widgets[f"scene_{i}"] = w
        elif cmd_type == "Wait":
            self._int("duration", "ms", "Duration_(Note/PB)", 0, 2550, width=65)
            ctk.CTkLabel(
                self.params,
                text="(pauses the commands below it, in steps of 10 ms)",
                text_color=MUTED,
            ).pack(side="left", padx=8)
        elif cmd_type == "Cycle":
            self._label("Label")
            w = TextEntry(self.params, 4, self.initial.get("OnValue_(CC/PB)"), width=70)
            w.pack(side="left")
            self.widgets["cyclelabel"] = w
            ctk.CTkLabel(
                self.params,
                text="(the commands below are the next state; empty = the button's label)",
                text_color=MUTED,
            ).pack(side="left", padx=8)
        elif cmd_type == "Leave":
            ctk.CTkLabel(
                self.params,
                text="(the commands below are sent on leaving the bank instead)",
                text_color=MUTED,
            ).pack(side="left", padx=8)
        elif cmd_type == "Chan":
            self._label("Channels")
            w = TextEntry(self.params, 47, clean(self.initial.get("Channel_(PC/CC/Note/PB)")), width=140)
            w.pack(side="left")
            self.widgets["chanlist"] = w
            ctk.CTkLabel(
                self.params,
                text="(the command right below goes out on each of them, \"1 2 3\" or \"1-3\")",
                text_color=MUTED,
            ).pack(side="left", padx=8)
        elif cmd_type == "Ramp":
            self._int("duration", "ms", "Duration_(Note/PB)", 0, RAMP_MAX_MS, width=75)
            ctk.CTkLabel(
                self.params,
                text="(the CC right below walks to its value over this time)",
                text_color=MUTED,
            ).pack(side="left", padx=8)
        elif cmd_type == "LFO":
            self._label("Every")
            w = Option(self.params, LFO_DIVISIONS, clean(self.initial.get("OnValue_(CC/PB)")) or "1/4", width=70)
            w.pack(side="left")
            self.widgets["lfodiv"] = w
            self._label("Shape")
            w = Option(self.params, LFO_SHAPES, clean(self.initial.get("KeyMode_(Key)")) or "Sine", width=90)
            w.pack(side="left")
            self.widgets["lfoshape"] = w
            ctk.CTkLabel(
                self.params,
                text="(the CC right below swings between Off and On, locked to the tempo)",
                text_color=MUTED,
            ).pack(side="left", padx=8)
        elif cmd_type == "Seq":
            self._label("Steps")
            w = TextEntry(self.params, 15, clean(self.initial.get("OnValue_(CC/PB)")), width=90)
            w.pack(side="left")
            self.widgets["seqsteps"] = w
            self._label("Every")
            w = Option(self.params, LFO_DIVISIONS, clean(self.initial.get("KeyMode_(Key)")) or "1/8", width=70)
            w.pack(side="left")
            self.widgets["seqdiv"] = w
            ctk.CTkLabel(
                self.params,
                text="(two steps, \"100 -\"; one Seq after another makes a longer sequence)",
                text_color=MUTED,
            ).pack(side="left", padx=8)
        elif cmd_type == "Value":
            self._label("Value")
            w = Option(self.params, [str(i) for i in range(1, VAR_COUNT + 1)],
                       clean(self.initial.get("Number_(PC/CC/Note)")) or "1", width=50)
            w.pack(side="left")
            self.widgets["varwhich"] = w
            self._label("Do")
            w = Option(self.params, VAR_MODES, clean(self.initial.get("KeyMode_(Key)")) or VAR_MODES[0], width=65)
            w.pack(side="left")
            self.widgets["varmode"] = w
            self._int("varamount", "By", "OnValue_(CC/PB)", 0, 127)
            self._label("Top")
            w = IntEntry(self.params, 0, 127,
                         clean(self.initial.get("OffValue_(CC)")) or str(VAR_DEFAULT_TOP), width=55)
            w.pack(side="left")
            self.widgets["vartop"] = w
            ctk.CTkLabel(
                self.params,
                text="(the pedal's own values, all zero at power on; past the top it starts again)",
                text_color=MUTED,
            ).pack(side="left", padx=8)
        elif cmd_type == "If":
            self._label("Only if")
            w = Option(self.params, IF_TESTS, clean(self.initial.get("KeyMode_(Key)")) or IF_TESTS[0],
                       width=115, command=lambda v: self._remode("If", v))
            w.pack(side="left")
            self.widgets["iftest"] = w
            test = IF_TESTS.index(w.get()) if w.get() in IF_TESTS else 0
            if test in IF_BUTTON_TESTS:
                self._label("Button")
                b = Option(self.params, list(SCENE_BUTTONS),
                           clean(self.initial.get("Number_(PC/CC/Note)")) or "1", width=50)
                b.pack(side="left")
                self.widgets["ifbutton"] = b
            elif test in IF_VALUE_TESTS:
                self._label("Value")
                b = Option(self.params, [str(i) for i in range(1, VAR_COUNT + 1)],
                           clean(self.initial.get("Number_(PC/CC/Note)")) or "1", width=50)
                b.pack(side="left")
                self.widgets["ifwhich"] = b
                self._int("ifvalue", "Is", "OnValue_(CC/PB)", 0, 127)
            else:
                self._int("ifvalue", "Bank", "OnValue_(CC/PB)", 0, 31)
            ctk.CTkLabel(
                self.params,
                text="(the command right below only goes out then; another If asks for both)",
                text_color=MUTED,
            ).pack(side="left", padx=8)
        elif cmd_type == "Macro":
            self._int("macrobank", "Bank", "OnValue_(CC/PB)", 0, 31)
            self._label("Button")
            w = Option(self.params, list(SCENE_BUTTONS),
                       clean(self.initial.get("Number_(PC/CC/Note)")) or "1", width=50)
            w.pack(side="left")
            self.widgets["macrobutton"] = w
            self._label("List")
            w = Option(self.params, MACRO_LISTS,
                       clean(self.initial.get("KeyMode_(Key)")) or MACRO_LISTS[0], width=80)
            w.pack(side="left")
            self.widgets["macrolist"] = w
            ctk.CTkLabel(
                self.params,
                text="(that button's list is run here, so a sequence used in many banks is stored once)",
                text_color=MUTED,
            ).pack(side="left", padx=8)
        elif cmd_type == "Listen":
            self._int("number", "CC", "Number_(PC/CC/Note)", 0, 127)
            self._int("on", "On", "OnValue_(CC/PB)", 0, 127)
            self._int("off", "Off", "OffValue_(CC)", 0, 127)
            ctk.CTkLabel(
                self.params,
                text="(the CC the device reports on; empty: 127/0)",
                text_color=MUTED,
            ).pack(side="left", padx=8)
        elif cmd_type == "Exp":
            self._label("Pedal")
            w = Option(self.params, ["1", "2"], self.initial.get("OnValue_(CC/PB)"), width=50)
            w.pack(side="left")
            self.widgets["exppedal"] = w
            self._label("To")
            w = Option(self.params, EXP_TARGETS, self.initial.get("KeyMode_(Key)"), width=65,
                       command=lambda v: self._remode("Exp", v))
            w.pack(side="left")
            self.widgets["exptarget"] = w
            if w.get() == "CC":
                self._int("number", "CC#", "Number_(PC/CC/Note)", 0, 127)
                self._label("Ch")
                c = Option(self.params, ["Own"] + CHANNELS,
                           self.initial.get("Channel_(PC/CC/Note/PB)"), width=65)
                c.pack(side="left")
                self.widgets["channel"] = c
            self._check("toggle", "Toggle", "Toggle_(CC/PB/Note)")
            ctk.CTkLabel(
                self.params,
                text="(until the bank changes; a toggle gives it back when off)",
                text_color=MUTED,
            ).pack(side="left", padx=8)
        # Start, Stop, Panic and (none) have no parameters

    # Read back ------------------------------------------------------------
    def values(self) -> dict:
        """Return every per-slot CSV field for this slot ('' = empty cell)."""
        out = {f: "" for f in CMD_FIELDS}
        out["Toggle_(CC/PB/Note)"] = "N"
        cmd_type = self.type_menu.get()
        out["CommandType"] = "" if cmd_type == NO_COMMAND else cmd_type
        w = self.widgets

        if "channel" in w:
            out["Channel_(PC/CC/Note/PB)"] = w["channel"].value()
        if "number" in w:
            out["Number_(PC/CC/Note)"] = w["number"].value()
        if "on" in w:
            out["OnValue_(CC/PB)"] = w["on"].value()
        if "off" in w:
            out["OffValue_(CC)"] = w["off"].value()
        if "bank" in w:
            out["BankSelect_(PC)"] = w["bank"].value()
        if "bank_msb" in w:
            out["BankSelectHighByte_(PC)"] = w["bank_msb"].value()
        if "velocity" in w:
            out["Velocity_(Note)"] = w["velocity"].value()
        if "duration" in w:
            out["Duration_(Note/PB)"] = w["duration"].value()
        if "toggle" in w:
            out["Toggle_(CC/PB/Note)"] = w["toggle"].value()
        if cmd_type == "Key":
            mask = sum(bit for _, bit in MODIFIERS if w[f"mod_{bit}"].get() == 1)
            out["Number_(PC/CC/Note)"] = str(mask)
            out["OnValue_(CC/PB)"] = w["key"].value()
            out["KeyMode_(Key)"] = w["keymode"].value()
        if cmd_type == "Media":
            out["OnValue_(CC/PB)"] = w["media"].value()
        if cmd_type == "Bank":
            out["KeyMode_(Key)"] = w["bankmode"].value()
            out["OnValue_(CC/PB)"] = w["bankvalue"].value() if "bankvalue" in w else ""
        if cmd_type in ("CCInc", "PCInc"):
            out["KeyMode_(Key)"] = w["ccincdir"].value()
            out["OffValue_(CC)"] = w["step"].value()
        if cmd_type == "SysEx":
            out["Number_(PC/CC/Note)"] = w["sysexindex"].value()
        if cmd_type == "Tap":
            out["KeyMode_(Key)"] = w["tapmode"].value()
            if "bpm" in w:
                out["OnValue_(CC/PB)"] = w["bpm"].value()
            if "step" in w:
                out["OffValue_(CC)"] = w["step"].value()
        if cmd_type == "MMC":
            out["KeyMode_(Key)"] = w["mmcaction"].value()
            out["OnValue_(CC/PB)"] = w["mmcvalue"].value() if "mmcvalue" in w else ""
        if cmd_type == "Song":
            out["KeyMode_(Key)"] = w["songmode"].value()
            out["OnValue_(CC/PB)"] = w["songvalue"].value()
        if cmd_type == "Chan":
            out["Channel_(PC/CC/Note/PB)"] = w["chanlist"].value().strip()
        if cmd_type == "Cycle":
            out["OnValue_(CC/PB)"] = w["cyclelabel"].value().strip()
        if cmd_type == "LFO":
            out["OnValue_(CC/PB)"] = w["lfodiv"].value()
            out["KeyMode_(Key)"] = w["lfoshape"].value()
        if cmd_type == "Seq":
            out["OnValue_(CC/PB)"] = w["seqsteps"].value().strip()
            out["KeyMode_(Key)"] = w["seqdiv"].value()
        if cmd_type == "Exp":
            out["OnValue_(CC/PB)"] = w["exppedal"].value()
            out["KeyMode_(Key)"] = w["exptarget"].value()
            if out["Channel_(PC/CC/Note/PB)"] == "Own":
                out["Channel_(PC/CC/Note/PB)"] = ""
        if cmd_type == "Value":
            out["Number_(PC/CC/Note)"] = w["varwhich"].value()
            out["KeyMode_(Key)"] = w["varmode"].value()
            out["OnValue_(CC/PB)"] = w["varamount"].value()
            out["OffValue_(CC)"] = w["vartop"].value()
        if cmd_type == "If":
            out["KeyMode_(Key)"] = w["iftest"].value()
            if "ifbutton" in w:
                out["Number_(PC/CC/Note)"] = w["ifbutton"].value()
            if "ifwhich" in w:
                out["Number_(PC/CC/Note)"] = w["ifwhich"].value()
            if "ifvalue" in w:
                out["OnValue_(CC/PB)"] = w["ifvalue"].value()
        if cmd_type == "Macro":
            out["OnValue_(CC/PB)"] = w["macrobank"].value()
            out["Number_(PC/CC/Note)"] = w["macrobutton"].value()
            out["KeyMode_(Key)"] = w["macrolist"].value()
        if cmd_type == "Scene":
            code = {"On": "+", "Off": "-"}
            out["OnValue_(CC/PB)"] = "".join(code.get(w[f"scene_{i}"].value(), ".") for i in range(8))
        return out


# --- Main window ------------------------------------------------------------
class MidiCommanderGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MIDI Commander Configurator")
        self.geometry("1200x720")

        self.df_global = None
        self.df_banks = None
        self.df_buttons = None
        self.df_long = None
        self.df_double = None
        self.df_exp = None
        self.df_enter = None
        self.enter_editors = []
        self.df_sysex = None
        self.df_bank_switch = None
        self.df_setlist = None
        self.df_combos = None
        self.combo_widgets = []
        self.df_bank_exp = None
        self.bank_exp_widgets = {}  # df index -> {column: widget}
        self.setlist_widgets = []
        self.bank_switch_editors = []
        self.bank_switch_row = None
        self.sysex_widgets = {}
        self.current_csv_path = None  # where Save writes; None asks
        self.loaded_name = None       # the file shown, a reference file included
        self.saved_text = None        # the configuration as last loaded or saved
        self.live = None            # MidiCommander while the live pedal view is on
        self.pedal_supported = False  # the connected firmware answers PRESS_BUTTON/GET_STATE
        self.pedal_tick = 0
        self.calibrating = {}       # pedal index -> [min_seen, max_seen]
        self.exp_widgets = {}       # pedal index -> dict of widgets
        self.press_mode = "Short press"
        self.editing_button = None  # (row_index, btn_id) of the button being edited
        self.bank_clipboard = None  # a copied bank, see lib/bankClipboard.py
        self.button_clipboard = None  # a copied button, see lib/bankReorder.py

        self.global_widgets = {}  # df index -> widget with .value()
        self.bank_widgets = {}  # df index -> (large, small)
        self.slot_editors = []
        self.editing_row = None
        self.light_mode = None
        self.label_entry = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar: the file on the left of the workflow, the pedal on the right
        self.sidebar = ctk.CTkFrame(self, width=210, corner_radius=0, fg_color=SIDEBAR_BG)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(20, weight=1)

        ctk.CTkLabel(self.sidebar, text="Midi Commander", font=FONT_TITLE).grid(
            row=0, column=0, padx=20, pady=(22, 0), sticky="w")
        ctk.CTkLabel(self.sidebar, text="Configurator", font=FONT_BODY, text_color=MUTED).grid(
            row=1, column=0, padx=20, pady=(0, 18), sticky="w")

        def section(row, text):
            ctk.CTkLabel(self.sidebar, text=text, font=FONT_SECTION, text_color=MUTED).grid(
                row=row, column=0, padx=20, pady=(14, 4), sticky="w")

        def action(row, text, command, **kw):
            b = ctk.CTkButton(self.sidebar, text=text, command=command, height=34, **kw)
            b.grid(row=row, column=0, padx=20, pady=4, sticky="ew")
            return b

        section(2, "FILE")
        action(3, "Load CSV\u2026", self.load_csv, fg_color=FIELD, hover_color=FIELD_HOVER)
        save_row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        save_row.grid(row=4, column=0, padx=20, pady=4, sticky="ew")
        save_row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(save_row, text="Save CSV", command=self.save_csv, height=34,
                      fg_color=FIELD, hover_color=FIELD_HOVER).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ctk.CTkButton(save_row, text="Save As\u2026", command=self.save_csv_as, height=34,
                      fg_color=FIELD, hover_color=FIELD_HOVER).grid(row=0, column=1, sticky="ew", padx=(3, 0))

        section(5, "PEDAL")
        # Configuration slot used by Read from Device and Flash to Device
        slot_row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        slot_row.grid(row=6, column=0, padx=20, pady=4, sticky="ew")
        ctk.CTkLabel(slot_row, text="Slot", font=FONT_BODY).pack(side="left")
        self.slot_selector = ctk.CTkOptionMenu(slot_row, values=SLOT_TARGETS, width=100)
        self.slot_selector.set("Active")
        self.slot_selector.pack(side="right")
        action(7, "Read from Device", self.read_device, fg_color=FIELD, hover_color=FIELD_HOVER)
        action(8, "Flash to Device", self.flash_device, fg_color=DANGER, hover_color=DANGER_HOVER,
               font=("", 13, "bold"))
        action(9, "Back Up All Slots\u2026", self.backup_slots, fg_color=FIELD, hover_color=FIELD_HOVER)
        action(10, "Restore Backup\u2026", self.restore_slots, fg_color=FIELD, hover_color=FIELD_HOVER)
        action(11, "Update Firmware\u2026", self.update_firmware, fg_color=FIELD, hover_color=FIELD_HOVER)
        action(12, "Banner Text\u2026", self.banner_text, fg_color=FIELD, hover_color=FIELD_HOVER)

        self.lbl_file = ctk.CTkLabel(self.sidebar, text="no file loaded", font=FONT_SMALL,
                                     text_color=MUTED, wraplength=170, justify="left")
        self.lbl_file.grid(row=21, column=0, padx=20, pady=(0, 18), sticky="sw")

        # Tabs
        self.tabview = ctk.CTkTabview(self, width=900, fg_color=CARD, segmented_button_fg_color=FIELD,
                                      segmented_button_selected_color=ACCENT,
                                      segmented_button_selected_hover_color=ACCENT_HOVER,
                                      segmented_button_unselected_color=FIELD,
                                      segmented_button_unselected_hover_color=FIELD_HOVER)
        self.tabview.grid(row=0, column=1, padx=16, pady=(12, 16), sticky="nsew")
        # In the order a configuration is usually built
        for name in ("Buttons", "Banks", "Bank Enter", "Bank Switch", "Combos", "Setlist",
                     "Expression", "SysEx", "Global", "Virtual Pedal", "Monitor"):
            self.tabview.add(name)

        self.global_scroll = ctk.CTkScrollableFrame(self.tabview.tab("Global"))
        self.global_scroll.pack(fill="both", expand=True)

        Help(
            self.tabview.tab("Banks"),
            "Each bank's name, and where the expression pedals send while it is selected.",
            "Pedal CC and channel: Default keeps the pedal's own (Expression and Global tabs), "
            "a number replaces it in this bank, Off silences the pedal here while its toe and "
            "heel switches keep working, and Speed makes it set how fast the LFOs and Seqs go. Min "
            "and Max, the values sent at the heel and at the toe, are left empty to keep the "
            "pedal's own range. After a bank change the pedal sends to the new target as soon as "
            "it moves.",
        ).pack(anchor="w", padx=10, pady=(10, 6))
        Help(
            self.tabview.tab("Banks"),
            "The arrows move a bank up or down the list; Move takes it to any place.",
            "The banks in between shift one place to make room, and everything that names a bank "
            "by number follows it: Bank GoTo and Page commands, If bank tests, Macros, the setlist, "
            "the global buttons bank and the combinations. A host that changes banks by number "
            "(Change bank from MIDI in the Global tab) is outside the configuration and has to be told.",
        ).pack(anchor="w", padx=10, pady=(0, 6))
        move = ctk.CTkFrame(self.tabview.tab("Banks"), fg_color="transparent")
        move.pack(fill="x", padx=10, pady=(0, 6))
        banks = [str(b) for b in range(NUM_BANKS)]
        ctk.CTkLabel(move, text="Move bank").pack(side="left")
        self.move_from = ctk.CTkOptionMenu(move, values=banks, width=70)
        self.move_from.pack(side="left", padx=6)
        ctk.CTkLabel(move, text="to place").pack(side="left")
        self.move_to = ctk.CTkOptionMenu(move, values=banks, width=70)
        self.move_to.pack(side="left", padx=6)
        ctk.CTkButton(move, text="Move", width=70, command=self.move_bank_to,
                      fg_color=FIELD, hover_color=FIELD_HOVER).pack(side="left", padx=6)
        self.bank_scroll = ctk.CTkScrollableFrame(self.tabview.tab("Banks"))
        self.bank_scroll.pack(fill="both", expand=True)

        self._setup_button_tab()
        self._setup_expression_tab()
        self._setup_pedal_tab()
        self._setup_monitor_tab()
        self._setup_bank_enter_tab()
        self._setup_sysex_tab()
        self._setup_bank_switch_tab()
        self._setup_setlist_tab()
        self._setup_combo_tab()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if os.path.exists(DEFAULT_CSV):
            self.load_csv(DEFAULT_CSV)

    # --- Button tab layout ----------------------------------------------------
    def _setup_button_tab(self):
        tab = self.tabview.tab("Buttons")
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(tab, height=40, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        ctk.CTkLabel(top, text="Bank:").pack(side="left", padx=10)
        self.bank_selector = ctk.CTkOptionMenu(top, command=self.on_bank_change, width=80)
        self.bank_selector.pack(side="left", padx=10)
        ctk.CTkButton(top, text="Copy bank", width=100, command=self.copy_bank,
                      fg_color=FIELD, hover_color=FIELD_HOVER).pack(side="left", padx=(20, 6))
        self.paste_bank_button = ctk.CTkButton(
            top, text="Paste bank", width=160, command=self.paste_bank, state="disabled",
            fg_color=FIELD, hover_color=FIELD_HOVER
        )
        self.paste_bank_button.pack(side="left", padx=6)
        ctk.CTkButton(top, text="Copy button", width=100, command=self.copy_button,
                      fg_color=FIELD, hover_color=FIELD_HOVER).pack(side="left", padx=(20, 6))
        self.paste_button_button = ctk.CTkButton(
            top, text="Paste button", width=170, command=self.paste_button, state="disabled",
            fg_color=FIELD, hover_color=FIELD_HOVER
        )
        self.paste_button_button.pack(side="left", padx=6)

        # The eight buttons laid out as on the pedal: 1-4 on top, A-D below
        self.button_matrix = ctk.CTkFrame(tab, fg_color="transparent")
        self.button_matrix.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 4))
        self.button_widgets = {}

        self.cmd_editor = ctk.CTkScrollableFrame(tab, fg_color=CARD_RAISED, corner_radius=10)
        self.cmd_editor.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        ctk.CTkLabel(self.cmd_editor, text="Select a button to edit", font=FONT_HEADING, text_color=MUTED).pack(
            pady=10
        )

    # --- Loading ----------------------------------------------------------------
    def load_csv(self, path=None):
        if path is None:
            if not self._may_discard("Load another file"):
                return
            path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
            if not path:
                return
        try:
            data = read_config_csv(path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to load CSV: {e}")
            return

        self._load(data)
        self.current_csv_path = None if is_reference_csv(path) else path
        self.loaded_name = os.path.basename(path)
        self._show_file()
        self.saved_text = self._config_text()

    def _load(self, data):
        self.editing_row = None
        self.slot_editors = []
        self._show_file()

        if "Global_Settings" in data:
            self.df_global = data["Global_Settings"].astype(object).reset_index(drop=True)
            self.df_global["Label"] = self.df_global["Label"].astype(str).str.strip()
            labels = self.df_global["Label"].tolist()
            defaults = [
                ("Exp1_CC", "11"),
                ("Exp2_CC", "4"),
                ("Bank_Up_LED_Mode", "Normal"),
                ("Bank_Down_LED_Mode", "Normal"),
                ("USB_MIDI_Thru", "N"),
                ("Remember_State", "N"),
                ("Long_Press_ms", "500"),
                ("LED_Brightness", "100"),
                ("LED_Rest_Brightness", "100"),
                ("Bank_Jump_Step", "8"),
                ("Bank_Change_Mode", "Off"),
                ("Bank_Change_Channel", "Any"),
                ("Bank_Change_CC", "0"),
                ("Bank_Switch_Mode", "Bank"),
                ("Sleep_After_Min", "0"),
                ("Setlist_Mode", "N"),
                ("Clock_Follow", "N"),
                ("LED_Feedback", "N"),
                ("Double_Press_ms", "300"),
                ("Remote_Mode", "Off"),
                ("Remote_Channel", "Any"),
                ("Remote_First", "102"),
                ("Global_Channel", "Off"),
                ("Edit_Lock", "N"),
                ("Kemper_Mode", "N"),
                ("Global_Bank", "Off"),
                ("Combo_ms", "80"),
                ("Boot_Banner", "Off"),
                ("Bank_Preview", "0"),
            ]
            missing = [{"Label": l, "Value": v} for l, v in defaults if l not in labels]
            if missing:
                self.df_global = pd.concat(
                    [self.df_global, pd.DataFrame(missing)], ignore_index=True
                )
            self.populate_global()

        self.df_bank_exp = self._pad_bank_exp(
            data[BANK_EXPRESSION_SECTION].astype(object).reset_index(drop=True)
            if BANK_EXPRESSION_SECTION in data else empty_bank_expression_settings()
        )

        if "Bank_Naming" in data:
            self.df_banks = self._pad_banks(
                data["Bank_Naming"].astype(object).reset_index(drop=True)
            )
            self.populate_banks()

        if "Button_Settings" in data:
            self.df_buttons = data["Button_Settings"].astype(object).reset_index(drop=True)
            df = self.df_buttons
            if "Label" not in df.columns:
                df.insert(2, "Label", "")
            if "Light_Mode" not in df.columns:
                df["Light_Mode"] = "Normal"
            else:
                df["Light_Mode"] = df["Light_Mode"].fillna("Normal")
            if "Group" not in df.columns:
                df.insert(df.columns.get_loc("Light_Mode") + 1, "Group", "")
            else:
                df["Group"] = df["Group"].fillna("")
            if "Momentary_Hold" not in df.columns:
                df.insert(df.columns.get_loc("Group") + 1, "Momentary_Hold", "")
            else:
                df["Momentary_Hold"] = df["Momentary_Hold"].fillna("")
            if "Tempo_Flash" not in df.columns:
                df.insert(df.columns.get_loc("Momentary_Hold") + 1, "Tempo_Flash", "")
            else:
                df["Tempo_Flash"] = df["Tempo_Flash"].fillna("")
            if "Global" not in df.columns:
                df.insert(df.columns.get_loc("Tempo_Flash") + 1, "Global", "")
            else:
                df["Global"] = df["Global"].fillna("")
            if "Reset_On_Bank" not in df.columns:
                df.insert(df.columns.get_loc("Global") + 1, "Reset_On_Bank", "")
            else:
                df["Reset_On_Bank"] = df["Reset_On_Bank"].fillna("")
            missing = [
                f"{slot}_{field}"
                for slot in SLOTS
                for field in CMD_FIELDS
                if f"{slot}_{field}" not in df.columns
            ]
            if missing:
                df = pd.concat(
                    [df, pd.DataFrame(float("nan"), index=df.index, columns=missing)],
                    axis=1,
                )
            self.df_buttons = df.copy()

            # Long press command sets: optional section, one row per button
            if LONG_PRESS_SECTION in data:
                self.df_long = data[LONG_PRESS_SECTION].astype(object).reset_index(drop=True)
            else:
                self.df_long = empty_long_press_settings()
            missing = [
                f"{slot}_{field}"
                for slot in SLOTS
                for field in CMD_FIELDS
                if f"{slot}_{field}" not in self.df_long.columns
            ]
            if missing:
                self.df_long = pd.concat(
                    [self.df_long, pd.DataFrame(float("nan"), index=self.df_long.index, columns=missing)],
                    axis=1,
                ).copy()

            # Double press command sets: optional section, same shape
            if DOUBLE_PRESS_SECTION in data:
                self.df_double = data[DOUBLE_PRESS_SECTION].astype(object).reset_index(drop=True)
            else:
                self.df_double = empty_double_press_settings()
            missing = [
                f"{slot}_{field}"
                for slot in SLOTS
                for field in CMD_FIELDS
                if f"{slot}_{field}" not in self.df_double.columns
            ]
            if missing:
                self.df_double = pd.concat(
                    [self.df_double, pd.DataFrame(float("nan"), index=self.df_double.index, columns=missing)],
                    axis=1,
                ).copy()

            self.df_exp = (
                data[EXPRESSION_SECTION].astype(object).reset_index(drop=True)
                if EXPRESSION_SECTION in data
                else empty_expression_settings()
            )
            for col, default in (("Out_Min", "0"), ("Out_Max", "127"), ("Auto_Button", "None"), ("Auto_Off_ms", "500"),
                                 ("Output", "CC")):
                if col not in self.df_exp.columns:
                    self.df_exp[col] = default
            self.populate_expression()

            self.df_enter = (
                data[BANK_ENTER_SECTION].astype(object).reset_index(drop=True)
                if BANK_ENTER_SECTION in data
                else empty_bank_enter_settings()
            )
            self.df_bank_switch = (
                data[BANK_SWITCH_SECTION].astype(object).reset_index(drop=True)
                if BANK_SWITCH_SECTION in data
                else empty_bank_switch_settings()
            )
            self.df_setlist = (
                data[SETLIST_SECTION].astype(object).reset_index(drop=True)
                if SETLIST_SECTION in data
                else empty_setlist()
            )
            self.populate_setlist()
            self.df_combos = (
                data[COMBO_SECTION].astype(object).reset_index(drop=True)
                if COMBO_SECTION in data
                else empty_combos()
            )
            self.populate_combos()
            self.df_sysex = (
                data[SYSEX_SECTION].astype(object).reset_index(drop=True)
                if SYSEX_SECTION in data
                else empty_sysex_strings()
            )
            self.populate_sysex()

            missing = [
                f"{slot}_{field}"
                for slot in SLOTS
                for field in CMD_FIELDS
                if f"{slot}_{field}" not in self.df_enter.columns
            ]
            if missing:
                self.df_enter = pd.concat(
                    [self.df_enter,
                     pd.DataFrame(float("nan"), index=self.df_enter.index, columns=missing)],
                    axis=1,
                ).copy()

            self.df_buttons = self._pad_buttons(self.df_buttons, with_extras=True)
            self.df_long = self._pad_buttons(self.df_long, with_extras=False)
            self.df_double = self._pad_buttons(self.df_double, with_extras=False)

            banks = [str(b) for b in range(NUM_BANKS)]
            self.bank_selector.configure(values=banks)
            self.bank_selector.set(banks[0])
            self.on_bank_change(banks[0])

            # Show the first bank's and switch's commands straight away. The
            # editors of a previous file must not be applied to this one.
            self.enter_editors = []
            self.enter_bank_selector.set(banks[0])
            self._on_enter_bank_change(banks[0])
            self.bank_switch_editors = []
            self.bank_switch_row = None
            self.bank_switch_selector.set(BANK_SWITCH_CHOICES[0])
            self._on_bank_switch_change(BANK_SWITCH_CHOICES[0])

    def _show_file(self):
        if hasattr(self, "lbl_file"):
            if self.current_csv_path:
                name = os.path.basename(self.current_csv_path)
            elif self.loaded_name:
                name = f"{self.loaded_name}\n(comes with the tools: Save asks where to keep your copy)"
            else:
                name = "no file loaded"
            self.lbl_file.configure(text=name)

    def _pad_bank_exp(self, df):
        """One BankExpression_Settings row per bank, in order, blanks as ''."""
        rows = {clean(r.get("Bank_Number")): r for _, r in df.iterrows()}
        out = []
        for b in range(NUM_BANKS):
            r = rows.get(str(b))
            row = {"Bank_Number": str(b)}
            for col in BANK_EXP_COLUMNS[1:]:
                row[col] = clean(r.get(col)) if r is not None else ""
            out.append(row)
        return pd.DataFrame(out, columns=BANK_EXP_COLUMNS)

    def _pad_banks(self, df):
        """Ensure one Bank_Naming row per bank, in order."""
        rows = {clean(r["Bank_Number"]): r for _, r in df.iterrows()}
        out = []
        for b in range(NUM_BANKS):
            r = rows.get(str(b))
            out.append(
                {
                    "Bank_Number": str(b),
                    "Bank_Name_Large": clean(r["Bank_Name_Large"]) if r is not None else "",
                    "Bank_Info_Small": clean(r["Bank_Info_Small"]) if r is not None else "",
                }
            )
        return pd.DataFrame(out)

    def _pad_buttons(self, df, with_extras):
        """Ensure one row per bank/button, in order, keeping existing values."""
        rows = {
            (clean(r["Bank_Number"]), clean(r["Button_Identifier"]).upper()): r
            for _, r in df.iterrows()
        }
        columns = ["Bank_Number", "Button_Identifier"]
        if with_extras:
            columns += ["Label"]
        for slot in SLOTS:
            columns += [f"{slot}_{f}" for f in CMD_FIELDS]
        if with_extras:
            columns += ["Light_Mode", "Group", "Momentary_Hold", "Tempo_Flash", "Global",
                        "Reset_On_Bank"]

        out = []
        for b in range(NUM_BANKS):
            for btn in BUTTON_IDS:
                src = rows.get((str(b), btn))
                row = {c: float("nan") for c in columns}
                row["Bank_Number"], row["Button_Identifier"] = str(b), btn
                if with_extras:
                    row["Label"] = ""
                    row["Light_Mode"] = "Normal"
                    row["Group"] = ""
                    row["Momentary_Hold"] = ""
                    row["Tempo_Flash"] = ""
                    row["Global"] = ""
                    row["Reset_On_Bank"] = ""
                if src is not None:
                    for c in columns:
                        if c in src.index and c not in ("Bank_Number", "Button_Identifier"):
                            row[c] = src[c]
                out.append(row)
        # object, or pandas makes a column no button uses float64 and then
        # refuses the first text typed into it
        return pd.DataFrame(out, columns=columns).astype(object)

    # --- Global tab ---------------------------------------------------------------
    def populate_global(self):
        for w in self.global_scroll.winfo_children():
            w.destroy()
        self.global_widgets = {}

        by_label = {str(r["Label"]): (idx, r["Value"]) for idx, r in self.df_global.iterrows()}
        known = {label for _, items in GLOBAL_GROUPS for label, _, _ in items}
        groups = list(GLOBAL_GROUPS)
        others = [(label, label, "") for label in by_label if label not in known]
        if others:
            groups.append(("Other", others))

        for title, items in groups:
            present = [item for item in items if item[0] in by_label]
            if not present:
                continue
            card = ctk.CTkFrame(self.global_scroll, fg_color=CARD_RAISED, corner_radius=10)
            card.pack(fill="x", padx=8, pady=(4, 10))
            card.grid_columnconfigure(1, minsize=200)   # hints line up from card to card
            card.grid_columnconfigure(2, weight=1)
            ctk.CTkLabel(card, text=title, font=FONT_HEADING).grid(
                row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 4))
            for i, (label, name, hint) in enumerate(present, start=1):
                idx, value = by_label[label]
                ctk.CTkLabel(card, text=name, font=FONT_BODY, anchor="w", width=200).grid(
                    row=i, column=0, sticky="w", padx=(16, 8), pady=4)
                w = self._global_widget(card, label, value)
                w.grid(row=i, column=1, sticky="w", padx=8, pady=4)
                detail = f"{hint}  \u00b7  {label}" if hint else label
                ctk.CTkLabel(card, text=detail, font=FONT_SMALL, text_color=MUTED, anchor="w").grid(
                    row=i, column=2, sticky="w", padx=(8, 16))
                self.global_widgets[idx] = w
            ctk.CTkFrame(card, height=8, fg_color="transparent").grid(row=len(present) + 1, column=0)

    def _global_widget(self, parent, label, value):
        if label == "MIDI_Channel":
            return Option(parent, CHANNELS, value, width=80)
        if label in ("RealTime_Passthrough", "USB_MIDI_Thru", "Remember_State", "Setlist_Mode",
                     "Clock_Follow", "LED_Feedback", "Edit_Lock", "Kemper_Mode"):
            return Check(parent, text="", checked=is_yes(value))
        if label in ("Bank_Up_LED_Mode", "Bank_Down_LED_Mode"):
            return Option(parent, LED_MODES, value, width=110)
        if label in ("Exp1_CC", "Exp2_CC", "Bank_Change_CC"):
            return IntEntry(parent, 0, 127, value, width=70)
        if label == "Long_Press_ms":
            return IntEntry(parent, 100, 2500, value, width=70)
        if label == "Double_Press_ms":
            return IntEntry(parent, 100, 1000, value, width=70)
        if label == "Combo_ms":
            return IntEntry(parent, 20, 250, value, width=70)
        if label == "Boot_Banner":
            return Option(parent, ["Off", "Slow", "Normal", "Fast"], value, width=100)
        if label in ("LED_Brightness", "LED_Rest_Brightness"):
            return IntEntry(parent, 1, 100, value, width=70)
        if label == "Bank_Preview":
            return IntEntry(parent, 0, 60, value, width=70)
        if label == "Bank_Jump_Step":
            return IntEntry(parent, 1, 31, value, width=70)
        if label == "Bank_Change_Mode":
            return Option(parent, ["Off", "PC", "CC"], value, width=80)
        if label == "Bank_Switch_Mode":
            return Option(parent, BANK_SWITCH_MODES, value, width=110)
        if label == "Sleep_After_Min":
            return IntEntry(parent, 0, 60, value, width=70)
        if label == "Remote_Mode":
            return Option(parent, ["Off", "CC", "Note"], value, width=80)
        if label == "Remote_First":
            return IntEntry(parent, 0, 118, value, width=70)
        if label == "Global_Channel":
            return Option(parent, ["Off"] + CHANNELS, value, width=80)
        if label == "Global_Bank":
            return Option(parent, ["Off"] + [str(b) for b in range(NUM_BANKS)], value, width=80)
        if label in ("Bank_Change_Channel", "Remote_Channel"):
            return Option(parent, ["Any"] + CHANNELS, value, width=80)
        if label == "ConfigName":
            return TextEntry(parent, 16, value, width=180)
        return TextEntry(parent, 64, value, width=180)

    # --- Bank tab -------------------------------------------------------------------
    def populate_banks(self):
        for w in self.bank_scroll.winfo_children():
            w.destroy()
        self.bank_widgets = {}
        self.bank_exp_widgets = {}

        for col, text in enumerate(("", "BANK", "NAME \u00b7 4 LARGE", "INFO \u00b7 8 SMALL",
                                    "PEDAL 1 CC", "CHANNEL", "MIN", "MAX",
                                    "PEDAL 2 CC", "CHANNEL", "MIN", "MAX")):
            ctk.CTkLabel(self.bank_scroll, text=text, font=FONT_SECTION, text_color=MUTED).grid(
                row=0, column=col, padx=(10, 16), pady=(8, 6), sticky="w")

        for row, (idx, r) in enumerate(self.df_banks.iterrows(), start=1):
            arrows = ctk.CTkFrame(self.bank_scroll, fg_color="transparent")
            arrows.grid(row=row, column=0, padx=(5, 0), pady=2)
            bank = row - 1
            for text, step in (("\u2191", -1), ("\u2193", 1)):
                to = bank + step
                ctk.CTkButton(arrows, text=text, width=26, height=26, fg_color=FIELD,
                              hover_color=FIELD_HOVER, state="normal" if 0 <= to < NUM_BANKS else "disabled",
                              command=lambda b=bank, t=to: self.move_bank(b, t)).pack(side="left", padx=1)
            ctk.CTkLabel(self.bank_scroll, text=clean(r["Bank_Number"])).grid(
                row=row, column=1, padx=5, pady=2
            )
            large = TextEntry(self.bank_scroll, 4, r["Bank_Name_Large"], width=100)
            large.grid(row=row, column=2, padx=5, pady=2)
            small = TextEntry(self.bank_scroll, 8, r["Bank_Info_Small"], width=150)
            small.grid(row=row, column=3, padx=5, pady=2)
            self.bank_widgets[idx] = (large, small)

            # Where the expression pedals send in this bank
            if self.df_bank_exp is not None and row - 1 < len(self.df_bank_exp):
                e = self.df_bank_exp.iloc[row - 1]
                widgets = {}
                for col, field in enumerate(BANK_EXP_COLUMNS[1:], start=4):
                    kind = field.split("_")[1]
                    if kind == "CC":
                        w = Combo(self.bank_scroll, ["Default", "Off", "Speed"], clean(e.get(field)) or "Default", width=100)
                    elif kind == "Channel":
                        w = Option(self.bank_scroll, ["Default"] + CHANNELS, clean(e.get(field)) or "Default", width=100)
                    else:  # output range, empty keeps the pedal's own
                        w = IntEntry(self.bank_scroll, 0, 127, e.get(field), width=50)
                    w.grid(row=row, column=col, padx=(16 if kind == "CC" else 5, 5), pady=2)
                    widgets[field] = w
                self.bank_exp_widgets[self.df_bank_exp.index[row - 1]] = widgets

    # --- Button tab -------------------------------------------------------------
    def on_bank_change(self, bank_val):
        self.apply_button_changes(silent=True)
        for w in self.button_matrix.winfo_children():
            w.destroy()
        self.button_widgets = {}

        rows = self.df_buttons[
            self.df_buttons["Bank_Number"].map(clean) == clean(bank_val)
        ]
        for idx, row_data in rows.iterrows():
            btn_id = clean(row_data["Button_Identifier"]).upper()
            if btn_id not in BUTTON_IDS:
                continue
            pos = BUTTON_IDS.index(btn_id)
            label = clean(row_data.get("Label"))
            b = ctk.CTkButton(
                self.button_matrix,
                text=f"{btn_id}\n{label}" if label else btn_id,
                width=96,
                height=52,
                corner_radius=10,
                font=BOLD,
                fg_color=FIELD,
                hover_color=FIELD_HOVER,
                command=lambda rid=idx, bid=btn_id: self.load_button_commands(rid, bid),
            )
            b.grid(row=pos // 4, column=pos % 4, padx=4, pady=4)
            self.button_widgets[btn_id] = b

        # Keep the highlight when the button being edited belongs to this bank
        editing = None
        if self.editing_button is not None and self.editing_row in rows.index:
            editing = self.editing_button[1]
        self._highlight_button(editing)

    def _highlight_button(self, btn_id):
        for bid, b in self.button_widgets.items():
            chosen = bid == btn_id
            b.configure(fg_color=ACCENT if chosen else FIELD,
                        hover_color=ACCENT_HOVER if chosen else FIELD_HOVER)

    # --- Copy and paste a whole bank -------------------------------------------------
    def copy_bank(self):
        if self.df_buttons is None:
            return
        # Take whatever is still in the editors along with it
        self.apply_button_changes(silent=True)
        self.apply_bank_enter_changes()
        self.apply_bank_changes()
        bank = self.bank_selector.get()
        self.bank_clipboard = bank_clipboard.copy_bank(
            self.df_buttons, self.df_long, self.df_enter, bank, df_double=self.df_double,
            df_bank_exp=self.df_bank_exp)
        self.paste_bank_button.configure(state="normal", text=f"Paste bank {clean(bank)} here",
                                         fg_color=ACCENT, hover_color=ACCENT_HOVER)

    def paste_bank(self):
        if not self.bank_clipboard or self.df_buttons is None:
            return
        target = clean(self.bank_selector.get())
        source = self.bank_clipboard["bank"]
        if target == source:
            return
        if not messagebox.askyesno(
            "Paste bank",
            f"Replace everything in bank {target} with bank {source}?\n\n"
            "Labels, LED modes, short, long and double press commands, the commands sent on "
            "entering the bank and its expression pedal settings are all replaced. The bank name is kept.",
        ):
            return
        self.apply_button_changes(silent=True)
        self.apply_bank_enter_changes()
        self.df_buttons, self.df_long, self.df_enter = bank_clipboard.paste_bank(
            self.df_buttons, self.df_long, self.df_enter, self.bank_clipboard, target
        )
        self.df_double = bank_clipboard.paste_double(self.df_double, self.bank_clipboard, target)
        self.apply_bank_changes()
        self.df_bank_exp = bank_clipboard.paste_bank_expression(self.df_bank_exp, self.bank_clipboard, target)
        self.populate_banks()
        self._drop_editors()
        self.on_bank_change(target)
        if self.enter_bank_selector.get():
            self._on_enter_bank_change(self.enter_bank_selector.get())

    def _drop_editors(self):
        """Forget the open editors, whose rows were just replaced or renumbered.

        Called before refreshing, or they would write the old values back.
        """
        self.editing_row = None
        self.editing_button = None
        self.slot_editors = []
        for w in self.cmd_editor.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.cmd_editor, text="Select a button to edit", font=FONT_HEADING, text_color=MUTED).pack(pady=10)
        self.enter_editors = []
        self.bank_switch_editors = []

    # --- Move a bank to another place ------------------------------------------------
    def move_bank_to(self):
        self.move_bank(int(self.move_from.get()), int(self.move_to.get()))

    def move_bank(self, src, dst):
        if self.df_buttons is None or src == dst:
            return
        self._collect()
        frames = {
            "global": self.df_global, "banks": self.df_banks, "buttons": self.df_buttons,
            "long": self.df_long, "double": self.df_double, "enter": self.df_enter,
            "bank_switch": self.df_bank_switch, "setlist": self.df_setlist,
            "bank_exp": self.df_bank_exp, "combos": self.df_combos,
        }
        moved = bank_reorder.move_bank(frames, src, dst)
        (self.df_global, self.df_banks, self.df_buttons, self.df_long, self.df_double, self.df_enter,
         self.df_bank_switch, self.df_setlist, self.df_bank_exp, self.df_combos) = (
            moved["global"], moved["banks"], moved["buttons"], moved["long"], moved["double"],
            moved["enter"], moved["bank_switch"], moved["setlist"], moved["bank_exp"], moved["combos"])
        mapping = bank_reorder.move_map(src, dst)
        # A copied bank or button keeps pointing at where it was copied from
        if self.bank_clipboard:
            self.bank_clipboard = None
            self.paste_bank_button.configure(state="disabled", text="Paste bank",
                                             fg_color=FIELD, hover_color=FIELD_HOVER)
        if self.button_clipboard:
            self.button_clipboard = None
            self.paste_button_button.configure(state="disabled", text="Paste button",
                                               fg_color=FIELD, hover_color=FIELD_HOVER)
        self._drop_editors()
        self._refresh_after_move()
        shown = str(mapping[int(clean(self.bank_selector.get()) or 0)])
        self.bank_selector.set(shown)
        self.on_bank_change(shown)
        enter = str(mapping[int(clean(self.enter_bank_selector.get()) or 0)])
        self.enter_bank_selector.set(enter)
        self._on_enter_bank_change(enter)
        self.bank_switch_row = None
        self._on_bank_switch_change(self.bank_switch_selector.get())
        self.move_from.set(str(dst))
        self.move_to.set(str(dst))

    def _refresh_after_move(self):
        """Show the moved frames in the widgets already there.

        Rebuilding the Banks tab takes seconds, and a move changes values only.
        """
        def put(w, value):
            value = clean(value)
            if isinstance(w, ctk.CTkOptionMenu):
                values = w.cget("values")
                w.set(value if value in values else values[0])
            elif isinstance(w, ctk.CTkComboBox):
                w.set(value)
            else:
                w.delete(0, "end")
                if value:
                    w.insert(0, value)

        for idx, (large, small) in self.bank_widgets.items():
            put(large, self.df_banks.at[idx, "Bank_Name_Large"])
            put(small, self.df_banks.at[idx, "Bank_Info_Small"])
        for idx, widgets in self.bank_exp_widgets.items():
            for field, w in widgets.items():
                value = clean(self.df_bank_exp.at[idx, field])
                if isinstance(w, ctk.CTkComboBox) and not value:
                    value = "Default"
                elif isinstance(w, ctk.CTkOptionMenu) and not value:
                    value = "Default"
                put(w, value)
        for idx, w in self.global_widgets.items():
            if clean(self.df_global.at[idx, "Label"]) == "Global_Bank":
                put(w, self.df_global.at[idx, "Value"])

        # The bank names in the choices moved with the banks
        choices = self._bank_choices()
        order = [clean(b) for b in self.df_setlist["Bank_Number"]] if self.df_setlist is not None else []
        for i, w in enumerate(self.setlist_widgets):
            w.configure(values=choices)
            try:
                put(w, choices[int(order[i]) + 1] if i < len(order) else NO_COMMAND)
            except (ValueError, IndexError):
                put(w, NO_COMMAND)
        banks = choices[1:]
        rows = [r for _, r in self.df_combos.iterrows() if clean(r.get("Switches"))] if self.df_combos is not None else []
        for i, widgets in enumerate(self.combo_widgets):
            widgets["scope"].configure(values=["All banks"] + banks)
            widgets["bank"].configure(values=banks)
            if i >= len(rows):
                continue
            scope = clean(rows[i].get("Bank"))
            try:
                put(widgets["scope"], banks[int(float(scope))] if scope and scope.upper() != "ALL" else "All banks")
                put(widgets["bank"], banks[int(float(clean(rows[i].get("Run_Bank"))))])
            except (ValueError, IndexError):
                pass

    # --- Copy and paste one button ------------------------------------------------
    def copy_button(self):
        if self.df_buttons is None or self.editing_button is None:
            messagebox.showinfo("Copy button", "Select the button to copy first.")
            return
        self.apply_button_changes(silent=True)
        row = self.df_buttons.loc[self.editing_button[0]]
        bank, btn = clean(row["Bank_Number"]), clean(row["Button_Identifier"]).upper()
        self.button_clipboard = bank_reorder.copy_button(self.df_buttons, self.df_long, self.df_double, bank, btn)
        self.paste_button_button.configure(state="normal", text=f"Paste button {bank}/{btn} here",
                                           fg_color=ACCENT, hover_color=ACCENT_HOVER)

    def paste_button(self):
        if not self.button_clipboard or self.df_buttons is None:
            return
        if self.editing_button is None:
            messagebox.showinfo("Paste button", "Select the button to paste over first.")
            return
        self.apply_button_changes(silent=True)
        row = self.df_buttons.loc[self.editing_button[0]]
        bank, btn = clean(row["Bank_Number"]), clean(row["Button_Identifier"]).upper()
        clip = self.button_clipboard
        if (clip["bank"], clip["button"]) == (bank, btn):
            return
        if not messagebox.askyesno(
            "Paste button",
            f"Replace button {btn} of bank {bank} with button {clip['button']} of bank {clip['bank']}?\n\n"
            "Its label, LED mode, flags and its short, long and double press commands are all replaced.",
        ):
            return
        self.df_buttons, self.df_long, self.df_double = bank_reorder.paste_button(
            self.df_buttons, self.df_long, self.df_double, clip, bank, btn)
        self._drop_editors()
        self.on_bank_change(bank)
        for idx, r in self.df_buttons.iterrows():
            if clean(r["Bank_Number"]) == bank and clean(r["Button_Identifier"]).upper() == btn:
                self.load_button_commands(idx, btn)
                break

    def _long_row_index(self, row_index):
        """Index in df_long of the button at df_buttons row_index (created if missing)."""
        return self._press_row_index("df_long", row_index)

    def _double_row_index(self, row_index):
        """Index in df_double of the button at df_buttons row_index (created if missing)."""
        return self._press_row_index("df_double", row_index)

    def _press_row_index(self, attr, row_index):
        frame = getattr(self, attr)
        short = self.df_buttons.loc[row_index]
        bank, btn = clean(short["Bank_Number"]), clean(short["Button_Identifier"]).upper()
        match = frame[
            (frame["Bank_Number"].map(clean) == bank)
            & (frame["Button_Identifier"].map(clean).str.upper() == btn)
        ]
        if len(match):
            return match.index[0]
        new_row = {c: float("nan") for c in frame.columns}
        new_row["Bank_Number"], new_row["Button_Identifier"] = bank, btn
        frame = pd.concat([frame, pd.DataFrame([new_row])], ignore_index=True)
        setattr(self, attr, frame)
        return frame.index[-1]

    def _set_press_mode(self, mode):
        if self.editing_button is None:
            return
        self.apply_button_changes(silent=True)
        self.slot_editors = []  # already applied; don't apply them again under the new mode
        self.press_mode = mode
        self.load_button_commands(*self.editing_button)

    def load_button_commands(self, row_index, btn_id):
        self.apply_button_changes(silent=True)

        for w in self.cmd_editor.winfo_children():
            w.destroy()
        self.slot_editors = []
        self.editing_row = row_index
        self.editing_button = (row_index, btn_id)
        self._highlight_button(clean(btn_id).upper())
        self.label_entry = None
        self.light_mode = None
        self.group = None
        self.momentary_hold = None
        self.tempo_flash = None
        self.button_global = None
        self.reset_on_bank = None
        long_mode = self.press_mode == "Long press"
        double_mode = self.press_mode == "Double press"

        ctk.CTkLabel(
            self.cmd_editor,
            text=f"Bank {self.bank_selector.get()} - Button {btn_id}",
            font=FONT_HEADING,
        ).pack(anchor="w", padx=10, pady=(5, 5))

        current = self.df_buttons.loc[row_index]

        if not (long_mode or double_mode):
            light_frame = ctk.CTkFrame(self.cmd_editor, fg_color="transparent")
            light_frame.pack(anchor="w", padx=10, pady=(0, 8))
            ctk.CTkLabel(light_frame, text="Display label:", font=BOLD).pack(side="left")
            self.label_entry = TextEntry(light_frame, 4, current.get("Label"), width=70)
            self.label_entry.pack(side="left", padx=(8, 20))
            ctk.CTkLabel(light_frame, text="LED light mode:", font=BOLD).pack(side="left")
            self.light_mode = Option(light_frame, LED_MODES, current.get("Light_Mode"), width=110)
            self.light_mode.pack(side="left", padx=8)
            ctk.CTkLabel(light_frame, text="Exclusive group:", font=BOLD).pack(side="left", padx=(12, 0))
            group = clean(current.get("Group"))
            group = str(int(float(group))) if group not in ("", "0") else "None"
            self.group = Option(light_frame, BUTTON_GROUPS, group, width=80)
            self.group.pack(side="left", padx=8)
            flags_frame = ctk.CTkFrame(self.cmd_editor, fg_color="transparent")
            flags_frame.pack(anchor="w", padx=10, pady=(0, 8))
            self.momentary_hold = Check(flags_frame, text="Momentary when held",
                                        checked=is_yes(current.get("Momentary_Hold")))
            self.momentary_hold.pack(side="left")
            self.tempo_flash = Check(flags_frame, text="Flash at the tempo",
                                     checked=is_yes(current.get("Tempo_Flash")))
            self.tempo_flash.pack(side="left", padx=(12, 0))
            self.button_global = Check(flags_frame, text="Global",
                                       checked=is_yes(current.get("Global")))
            self.button_global.pack(side="left", padx=(12, 0))
            self.reset_on_bank = Check(flags_frame, text="Reset on bank change",
                                       checked=is_yes(current.get("Reset_On_Bank")))
            self.reset_on_bank.pack(side="left", padx=(12, 0))
            Help(
                self.cmd_editor,
                "Exclusive group: switching this button on switches off the others of its group "
                "in this bank.",
                "They are pressed for you, so they send their off commands and their LEDs go out, "
                "like the radio buttons of an amp's channels. Pressing the lit one switches it off "
                "as usual. Only buttons with a toggle command take part.",
                wraplength=720,
            ).pack(anchor="w", padx=10, pady=(0, 4))
            Help(
                self.cmd_editor,
                "Momentary when held: a tap latches the button, holding it past Long_Press_ms "
                "makes it momentary.",
                "Held, it goes back to where it was when you let go: on only while held, or off "
                "only while held if it was on. For toggle buttons without a long press list "
                "(which would take the hold) and without Cycle commands.",
                wraplength=720,
            ).pack(anchor="w", padx=10, pady=(0, 4))
            Help(
                self.cmd_editor,
                "Flash at the tempo: this button's LED blinks on every beat, as a Tap button's does.",
                "The beat is the host's clock while it is followed, the pedal's clock while it "
                "runs, and otherwise the tempo running freely from the last tap. The flash sits "
                "on top of the LED, which goes on showing whatever it shows.",
                wraplength=720,
            ).pack(anchor="w", padx=10, pady=(0, 4))
            Help(
                self.cmd_editor,
                "Global: this button takes everything from the same button of the bank set aside "
                "for them in Global settings.",
                "Its three command lists, its label, its light and its on and off state come from "
                "there, so the tuner or the tap is written once and is the same wherever you are. "
                "Whatever is written on this button in this bank is left alone and unused; the "
                "bank set aside is where it is edited.",
                wraplength=720,
            ).pack(anchor="w", padx=10, pady=(0, 4))
            Help(
                self.cmd_editor,
                "Reset on bank change: this button goes back to off when you leave its bank.",
                "Without it a button is still on when you come back, as you left it: mark the boost "
                "and leave the noise gate unmarked, and only the boost starts off again. Its "
                "long and double press toggles go back off too, and a cycle button starts again "
                "from its first state. Nothing is sent: the bank you go to sets up your rig.",
                wraplength=720,
            ).pack(anchor="w", padx=10, pady=(0, 8))

        mode_frame = ctk.CTkFrame(self.cmd_editor, fg_color="transparent")
        mode_frame.pack(anchor="w", padx=10, pady=(0, 4))
        self.mode_switch = ctk.CTkSegmentedButton(
            mode_frame, values=["Short press", "Long press", "Double press"], command=self._set_press_mode
        )
        self.mode_switch.set(self.press_mode)
        self.mode_switch.pack(side="left")
        ctk.CTkLabel(
            mode_frame,
            text=(
                "commands sent in order A to J when the button is held past Long_Press_ms"
                if long_mode
                else "commands sent in order A to J on two presses within Double_Press_ms; "
                "a single press then waits that long"
                if double_mode
                else "commands sent in order A to J when the button is pressed"
            ),
            text_color=MUTED,
        ).pack(side="left", padx=10)

        if long_mode:
            current = self.df_long.loc[self._long_row_index(row_index)]
        elif double_mode:
            current = self.df_double.loc[self._double_row_index(row_index)]

        table = ctk.CTkFrame(self.cmd_editor)
        table.pack(fill="x", padx=10, pady=(0, 5))
        for slot in SLOTS:
            initial = {f: current.get(f"{slot}_{f}") for f in CMD_FIELDS}
            types = COMMAND_TYPES if (long_mode or double_mode) else SHORT_COMMAND_TYPES
            self.slot_editors.append(SlotEditor(table, slot, initial, types))

        if not (long_mode or double_mode):
            Help(
                self.cmd_editor,
                "Cycle: one button, several states.",
                "Each Cycle command starts a new state: the commands above the first one are "
                "state 1, those below it state 2, and so on. Every press sends the next state, "
                "back to the first after the last, and the display shows the label of the state "
                "just sent (the button's own label for state 1, or for a Cycle left without one). "
                "Needs firmware 0.38.",
                wraplength=720,
            ).pack(anchor="w", padx=10, pady=(0, 4))

        Help(
            self.cmd_editor,
            "What Learn, Dur, Bend, BankSel and Hold mean.",
            "Learn = press it, then move a knob or press a button on a device the computer hears: "
            "the first PC, CC, Note or Pitch Bend that arrives sets the command's type, channel and "
            "number (and its value, if it had none). Press Stop, or wait 15 s, to give up.\n"
            "Dur = duration in 10 ms steps (0-127). Bend = -8192..8191. BankSel = MIDI Bank Select "
            "sent before a PC (0..16383). Hold = the key (or media key) stays pressed until the next press.",
            wraplength=720,
        ).pack(anchor="w", padx=10)

        ctk.CTkButton(
            self.cmd_editor,
            text="Apply Changes to Memory",
            command=self.apply_button_changes,
            fg_color=SUCCESS,
            hover_color=SUCCESS_HOVER,
        ).pack(anchor="w", padx=10, pady=12)

    def apply_button_changes(self, silent=False):
        """Copy the editor widgets back into df_buttons."""
        if self.editing_row is None or not self.slot_editors:
            return
        if self.press_mode == "Long press":
            df, idx = self.df_long, self._long_row_index(self.editing_row)
        elif self.press_mode == "Double press":
            df, idx = self.df_double, self._double_row_index(self.editing_row)
        else:
            df, idx = self.df_buttons, self.editing_row
        for editor in self.slot_editors:
            for field, val in editor.values().items():
                df.at[idx, f"{editor.slot}_{field}"] = val if val != "" else float("nan")
        if self.light_mode is not None:
            self.df_buttons.at[idx, "Light_Mode"] = self.light_mode.value()
        if self.group is not None:
            g = self.group.value()
            self.df_buttons.at[idx, "Group"] = "" if g == "None" else g
        if self.momentary_hold is not None:
            self.df_buttons.at[idx, "Momentary_Hold"] = "Y" if self.momentary_hold.value() == "Y" else ""
        if self.tempo_flash is not None:
            self.df_buttons.at[idx, "Tempo_Flash"] = "Y" if self.tempo_flash.value() == "Y" else ""
        if self.button_global is not None:
            self.df_buttons.at[idx, "Global"] = "Y" if self.button_global.value() == "Y" else ""
        if self.reset_on_bank is not None:
            self.df_buttons.at[idx, "Reset_On_Bank"] = "Y" if self.reset_on_bank.value() == "Y" else ""
        if self.label_entry is not None:
            self.df_buttons.at[idx, "Label"] = self.label_entry.value().strip()

        if not silent:
            messagebox.showinfo(
                "Info", "Changes applied to memory (Don't forget to Save CSV!)"
            )

    # --- Expression tab -----------------------------------------------------------
    def _setup_expression_tab(self):
        tab = self.tabview.tab("Expression")
        self.exp_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self.exp_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def populate_expression(self):
        for w in self.exp_frame.winfo_children():
            w.destroy()
        self.exp_widgets = {}
        self.calibrating = {}

        Help(
            self.exp_frame,
            "To calibrate: connect, press Calibrate, sweep the pedal from heel to toe and back a "
            "couple of times, then press Done.",
        ).pack(anchor="w", pady=(0, 6))

        top = ctk.CTkFrame(self.exp_frame, fg_color="transparent")
        top.pack(anchor="w", pady=(0, 8))
        self.btn_live = ctk.CTkButton(top, text="Connect live view", width=150, command=self._live_toggle)
        self.btn_live.pack(side="left")
        self.lbl_live = ctk.CTkLabel(top, text="not connected", text_color=MUTED)
        self.lbl_live.pack(side="left", padx=10)

        for i, r in self.df_exp.iterrows():
            box = ctk.CTkFrame(self.exp_frame)
            box.pack(fill="x", pady=4)
            w = {}
            head = ctk.CTkFrame(box, fg_color="transparent")
            head.pack(fill="x", padx=8, pady=(6, 2))
            ctk.CTkLabel(head, text=f"Pedal {clean(r['Pedal'])}", font=BOLD).pack(side="left")
            w["raw"] = ctk.CTkLabel(head, text="raw --", width=90, anchor="w")
            w["raw"].pack(side="left", padx=(20, 4))
            w["bar"] = ctk.CTkProgressBar(head, width=260)
            w["bar"].set(0)
            w["bar"].pack(side="left", padx=4)
            w["cc"] = ctk.CTkLabel(head, text="CC --", width=60, anchor="w")
            w["cc"].pack(side="left", padx=4)
            w["cal"] = ctk.CTkButton(head, text="Calibrate", width=90, state="disabled", fg_color=FIELD, hover_color=FIELD_HOVER,
                                     command=lambda i=i: self._calibrate_toggle(i))
            w["cal"].pack(side="left", padx=(10, 0))

            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=(2, 8))
            ctk.CTkLabel(row, text="Min ADC").pack(side="left")
            w["min"] = IntEntry(row, 0, 4095, r.get("Min_ADC"), width=65)
            w["min"].pack(side="left", padx=(4, 12))
            ctk.CTkLabel(row, text="Max ADC").pack(side="left")
            w["max"] = IntEntry(row, 0, 4095, r.get("Max_ADC"), width=65)
            w["max"].pack(side="left", padx=(4, 12))
            ctk.CTkLabel(row, text="Curve").pack(side="left")
            w["curve"] = Option(row, ["Linear", "Log", "Exp"], r.get("Curve"), width=85)
            w["curve"].pack(side="left", padx=(4, 12))
            w["invert"] = Check(row, text="Invert", checked=is_yes(r.get("Invert")), width=20)
            w["invert"].pack(side="left", padx=(0, 12))
            ctk.CTkLabel(row, text="Channel").pack(side="left")
            w["channel"] = Option(row, ["Global"] + CHANNELS, r.get("Channel"), width=80)
            w["channel"].pack(side="left", padx=4)

            sw = ctk.CTkFrame(box, fg_color="transparent")
            sw.pack(fill="x", padx=8, pady=(0, 8))
            ctk.CTkLabel(sw, text="Acts as a switch:").pack(side="left")
            ctk.CTkLabel(sw, text="toe taps").pack(side="left", padx=(10, 2))
            w["toe_button"] = Option(sw, ["None"] + BUTTON_IDS, r.get("Toe_Button"), width=75)
            w["toe_button"].pack(side="left")
            ctk.CTkLabel(sw, text="above").pack(side="left", padx=(6, 2))
            w["toe_level"] = IntEntry(sw, 1, 127, r.get("Toe_Level") or "120", width=55)
            w["toe_level"].pack(side="left")
            ctk.CTkLabel(sw, text="| heel taps").pack(side="left", padx=(14, 2))
            w["heel_button"] = Option(sw, ["None"] + BUTTON_IDS, r.get("Heel_Button"), width=75)
            w["heel_button"].pack(side="left")
            ctk.CTkLabel(sw, text="below").pack(side="left", padx=(6, 2))
            w["heel_level"] = IntEntry(sw, 0, 127, r.get("Heel_Level") or "7", width=55)
            w["heel_level"].pack(side="left")

            out = ctk.CTkFrame(box, fg_color="transparent")
            out.pack(fill="x", padx=8, pady=(0, 8))
            ctk.CTkLabel(out, text="Sends from").pack(side="left")
            w["out_min"] = IntEntry(out, 0, 127, clean(r.get("Out_Min")) or "0", width=55)
            w["out_min"].pack(side="left", padx=(6, 2))
            ctk.CTkLabel(out, text="at the heel to").pack(side="left", padx=(6, 2))
            w["out_max"] = IntEntry(out, 0, 127, clean(r.get("Out_Max")) or "127", width=55)
            w["out_max"].pack(side="left", padx=(6, 2))
            ctk.CTkLabel(out, text="at the toe, as").pack(side="left", padx=(6, 2))
            w["output"] = Option(out, ["CC", "PitchBend", "CC14", "Speed"], clean(r.get("Output")) or "CC", width=100)
            w["output"].pack(side="left", padx=(6, 2))

            auto = ctk.CTkFrame(box, fg_color="transparent")
            auto.pack(fill="x", padx=8, pady=(0, 8))
            ctk.CTkLabel(auto, text="Auto-engage: leaving the heel switches on").pack(side="left")
            w["auto_button"] = Option(auto, ["None"] + BUTTON_IDS, clean(r.get("Auto_Button")) or "None", width=75)
            w["auto_button"].pack(side="left", padx=(6, 2))
            ctk.CTkLabel(auto, text=", off after resting at the heel for").pack(side="left", padx=(6, 2))
            w["auto_off"] = IntEntry(auto, 10, 2540, clean(r.get("Auto_Off_ms")) or "500", width=65)
            w["auto_off"].pack(side="left", padx=(6, 2))
            ctk.CTkLabel(auto, text="ms").pack(side="left", padx=(2, 2))

            self.exp_widgets[i] = w

        Help(
            self.exp_frame,
            "How curves, channels and the toe and heel switches work.",
            "Curve: Linear = proportional, Log = fast at the start, Exp = slow at the start. "
            "Channel Global = MIDI channel from the Global tab. CC numbers are set in the Global tab.\n"
            "The pedal sends values between the two ends of its range, e.g. 40 to 127 so a volume "
            "never drops to silence; the heel value can be the higher one. A bank can set its own "
            "range in the Banks tab.\n"
            "As CC the pedal sends 0-127. PitchBend sends Pitch Bend instead of its CC, and CC14 a "
            "14-bit CC pair, the CC and CC + 32 (CC below 32 only), both with 16384 steps; the range "
            "still counts in 0-127, so 64 is the middle of the bend. A bank or an Exp button sending "
            "the pedal to another CC sends that CC.\n"
            "Speed sends nothing: the pedal sets how fast every LFO and Seq goes, the heel slowest "
            "(4/1) and the toe fastest (1/16T), each note division taking an equal share of 0-127, "
            "so 37 to 127 sweeps from 1/2 up. Moving it off Speed gives each its own speed back.\n"
            "As a switch, reaching the toe or returning to the heel taps a button of the current "
            "bank, sending whatever that button is configured to send. Each direction re-arms only "
            "after the pedal moves back past the level, so resting on the edge does not retrigger.\n"
            "Auto-engage, for a wah: moving the pedal up past the heel level switches a toggle "
            "button of the current bank on, and resting at or below it for the time given switches "
            "it off again. The button can still be pressed by hand.",
        ).pack(anchor="w", pady=(6, 0))

    def _live_toggle(self):
        if self.live is not None:
            self._live_disconnect()
            return
        try:
            self.live = MidiCommander().__enter__()
            version = self.live.get_version()
        except (DeviceNotFound, DeviceTimeout) as e:
            self._live_disconnect()
            messagebox.showerror("Live view", f"Could not connect to the pedal: {e}")
            return
        if hasattr(self, "lbl_live") and self.lbl_live.winfo_exists():
            self.lbl_live.configure(text=f"connected, firmware {version}")
            self.btn_live.configure(text="Disconnect")
        for w in getattr(self, "exp_widgets", {}).values():
            w["cal"].configure(state="normal", fg_color=ACCENT, hover_color=ACCENT_HOVER)
        self.pedal_supported = version_at_least(version, 0, 27)
        self._pedal_connection_changed(version)
        self._live_poll()

    def _live_disconnect(self):
        if self.live is not None:
            try:
                self.live.__exit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
            self.live = None
        self.calibrating = {}
        if hasattr(self, "lbl_live") and self.lbl_live.winfo_exists():
            self.lbl_live.configure(text="not connected")
            self.btn_live.configure(text="Connect live view")
            for w in getattr(self, "exp_widgets", {}).values():
                w["cal"].configure(state="disabled", text="Calibrate", fg_color=FIELD, hover_color=FIELD_HOVER)
        self.pedal_supported = False
        if hasattr(self, "pedal_widgets"):
            self._pedal_connection_changed(None)

    def _live_poll(self):
        if self.live is None:
            return
        try:
            readings = self.live.get_pedals()
        except DeviceTimeout:
            readings = None
        if readings:
            for i, (raw, cc) in enumerate(readings):
                w = self.exp_widgets.get(i)
                if not w:
                    continue
                w["raw"].configure(text=f"raw {raw}")
                w["bar"].set(raw / 4095)
                w["cc"].configure(text=f"CC {cc}")
                if i in self.calibrating:
                    lo, hi = self.calibrating[i]
                    self.calibrating[i] = [min(lo, raw), max(hi, raw)]
                    w["cal"].configure(text=f"Done ({self.calibrating[i][0]}-{self.calibrating[i][1]})")
        # The virtual pedal's view of the display, labels and LEDs
        self.pedal_tick += 1
        if self.pedal_supported and self.pedal_tick % PEDAL_STATE_EVERY == 0:
            try:
                state = self.live.get_state(timeout=0.3)
                self._pedal_show(state)
                # Fetch the screen only when the pedal has redrawn it
                if state["frame"] is not None and (state["frame"], state["asleep"]) != self.pedal_frame:
                    screen = None if state["asleep"] else self.live.get_screen(timeout=0.3)
                    self._pedal_draw_screen(screen)
                    self.pedal_frame = (state["frame"], state["asleep"])
            except (DeviceTimeout, ValueError):
                pass
        self.after(60, self._live_poll)

    # --- Virtual Pedal tab --------------------------------------------------------
    def _setup_pedal_tab(self):
        tab = self.tabview.tab("Virtual Pedal")
        frame = ctk.CTkFrame(tab, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(anchor="w", pady=(0, 6))
        self.btn_pedal_live = ctk.CTkButton(top, text="Connect", width=150, command=self._live_toggle)
        self.btn_pedal_live.pack(side="left")
        self.lbl_pedal_live = ctk.CTkLabel(top, text="not connected", text_color=MUTED)
        self.lbl_pedal_live.pack(side="left", padx=10)

        Help(
            frame,
            "Click a switch to tap it, hold it for a long press, click twice quickly for a double press.",
            "The display and the LEDs are the pedal's own, read back as they are. The press goes "
            "through the same path as a foot. A switch held here lets go by itself after 10 seconds.",
        ).pack(anchor="w", pady=(0, 8))

        c = tk.Canvas(frame, width=PEDAL_W, height=PEDAL_H, bg=PEDAL_BG, highlightthickness=0)
        c.pack(anchor="w")
        # The eight values a Value command keeps, under the pedal
        self.lbl_pedal_values = ctk.CTkLabel(frame, text="", text_color=MUTED)
        self.lbl_pedal_values.pack(anchor="w", pady=(6, 0))
        self.pedal_canvas = c
        self._pedal_rounded_rect(8, 8, PEDAL_W - 8, PEDAL_H - 8, 26, fill=PEDAL_BODY, outline=PEDAL_BODY_EDGE, width=2)

        # The display, in its window
        cx, cy = PEDAL_SCREEN_CENTER
        sw, sh = SCREEN_VISIBLE_WIDTH * PEDAL_SCREEN_ZOOM, SCREEN_HEIGHT * PEDAL_SCREEN_ZOOM
        self._pedal_rounded_rect(cx - sw // 2 - 10, cy - sh // 2 - 10, cx + sw // 2 + 10, cy + sh // 2 + 10, 8,
                                 fill="#0b0b0c", outline="#48484a", width=2)
        self.pedal_screen_base = tk.PhotoImage(width=SCREEN_VISIBLE_WIDTH, height=SCREEN_HEIGHT)
        self.pedal_screen_image = None
        self.pedal_screen_item = c.create_image(cx, cy)
        self.pedal_screen_note = c.create_text(cx, cy, text="not connected", fill="#636366",
                                               font=FONT_BODY)
        self._pedal_draw_screen(None)

        self.pedal_widgets = {}
        self.pedal_shown = {}
        self.pedal_frame = None
        for r, row in enumerate(PEDAL_ROWS):
            switch_y = PEDAL_TOP_SWITCH_Y if r == 0 else PEDAL_BOT_SWITCH_Y
            led_y = PEDAL_TOP_LED_Y if r == 0 else PEDAL_BOT_LED_Y
            caption_y = switch_y - 62 if r == 0 else switch_y + 62
            for col, name in enumerate(row):
                sid = VIRTUAL_SWITCHES.index(name)
                x = PEDAL_COL_X[col]
                tag = f"sw{sid}"
                c.create_oval(x - 46, switch_y - 46, x + 46, switch_y + 46, fill=PEDAL_RING, outline="#0f0f10",
                              width=2, tags=tag)
                nut = c.create_oval(x - 36, switch_y - 36, x + 36, switch_y + 36, fill=PEDAL_NUT,
                                    outline="#48484a", tags=tag)
                cap = c.create_oval(x - 25, switch_y - 25, x + 25, switch_y + 25, fill=PEDAL_CAP,
                                    outline="#f2f2f7", tags=tag)
                c.create_text(x, caption_y, text=PEDAL_CAPTIONS.get(name, name), fill="#aeaeb2",
                              font=BOLD)
                glow = c.create_oval(x - 17, led_y - 17, x + 17, led_y + 17, fill=PEDAL_BODY, outline="")
                c.create_oval(x - 10, led_y - 10, x + 10, led_y + 10, fill="#0f0f10", outline="#48484a")
                lens = c.create_oval(x - 7, led_y - 7, x + 7, led_y + 7, fill=led_color(0), outline="")
                c.tag_bind(tag, "<ButtonPress-1>", lambda _e, i=sid: self._pedal_press(i, True))
                c.tag_bind(tag, "<ButtonRelease-1>", lambda _e, i=sid: self._pedal_press(i, False))
                c.tag_bind(tag, "<Enter>", lambda _e: self.pedal_canvas.configure(cursor="hand2"))
                c.tag_bind(tag, "<Leave>", lambda _e: self.pedal_canvas.configure(cursor=""))
                self.pedal_widgets[sid] = {"nut": nut, "cap": cap, "glow": glow, "lens": lens}

    def _pedal_rounded_rect(self, x1, y1, x2, y2, r, **kw):
        points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
                  x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.pedal_canvas.create_polygon(points, smooth=True, **kw)

    def _pedal_draw_screen(self, buffer):
        """Show the pedal's screen buffer pixel for pixel; None shows it dark."""
        if buffer is None:
            rows = [[False] * SCREEN_VISIBLE_WIDTH for _ in range(SCREEN_HEIGHT)]
        else:
            rows = screen_rows(buffer)
        data = " ".join(
            "{" + " ".join(PEDAL_PIXEL_ON if lit else PEDAL_PIXEL_OFF for lit in row) + "}" for row in rows
        )
        self.pedal_screen_base.put(data, to=(0, 0))
        self.pedal_screen_image = self.pedal_screen_base.zoom(PEDAL_SCREEN_ZOOM)
        self.pedal_canvas.itemconfigure(self.pedal_screen_item, image=self.pedal_screen_image)

    def _pedal_connection_changed(self, version):
        """Reflect the shared live connection in the Virtual Pedal tab."""
        if not hasattr(self, "lbl_pedal_live") or not self.lbl_pedal_live.winfo_exists():
            return
        self.pedal_frame = None
        self.pedal_shown = {}
        if version is None:
            self.lbl_pedal_live.configure(text="not connected", text_color=MUTED)
            self.btn_pedal_live.configure(text="Connect")
            self._pedal_draw_screen(None)
            self.pedal_canvas.itemconfigure(self.pedal_screen_note, text="not connected", state="normal")
            for w in self.pedal_widgets.values():
                self._pedal_led(w, 0)
                self._pedal_cap(w, False)
            return
        self.btn_pedal_live.configure(text="Disconnect")
        if self.pedal_supported:
            self.lbl_pedal_live.configure(text=f"connected, firmware {version}", text_color=MUTED)
            self.pedal_canvas.itemconfigure(self.pedal_screen_note, state="hidden")
        else:
            self.lbl_pedal_live.configure(
                text=f"firmware {version} has no virtual pedal: update to 0.27 or later",
                text_color=WARN)
            self.pedal_canvas.itemconfigure(self.pedal_screen_note, text="firmware 0.27 needed")

    def _pedal_cap(self, w, down):
        self.pedal_canvas.itemconfigure(w["cap"], fill=PEDAL_CAP_DOWN if down else PEDAL_CAP)
        self.pedal_canvas.itemconfigure(w["nut"], fill=PEDAL_NUT_DOWN if down else PEDAL_NUT)

    def _pedal_led(self, w, level):
        t = level / LED_LEVELS
        self.pedal_canvas.itemconfigure(w["lens"], fill=led_color(level))
        self.pedal_canvas.itemconfigure(w["glow"], fill=blend(hex_rgb(PEDAL_BODY), PEDAL_LED_ON, 0.35 * t))

    def _pedal_press(self, sid, down):
        if self.live is None or not self.pedal_supported:
            return
        self._pedal_cap(self.pedal_widgets[sid], down)
        try:
            self.live.press_button(sid, down, timeout=0.5)
        except DeviceTimeout:
            self.lbl_pedal_live.configure(text="the pedal did not answer", text_color=WARN)

    def _pedal_show(self, state):
        """Paint the LEDs the pedal reports, touching only what changed."""
        for sid, w in self.pedal_widgets.items():
            level = 0 if state.get("asleep") else state["leds"][sid]
            if self.pedal_shown.get(sid) != level:
                self.pedal_shown[sid] = level
                self._pedal_led(w, level)
        values = state.get("values")
        shown = ("values  " + "   ".join(f"{i + 1}:{v}" for i, v in enumerate(values))) if values else ""
        if self.pedal_shown.get("values") != shown:
            self.pedal_shown["values"] = shown
            self.lbl_pedal_values.configure(text=shown)
        note = "asleep: the display and LEDs are off" if state.get("asleep") else ""
        if self.pedal_shown.get("note") != note:
            self.pedal_shown["note"] = note
            text = self.lbl_pedal_live.cget("text").split("  \u2014  ")[0]
            self.lbl_pedal_live.configure(text=f"{text}  \u2014  {note}" if note else text)

    def _calibrate_toggle(self, i):
        w = self.exp_widgets[i]
        if i not in self.calibrating:
            self.calibrating[i] = [4095, 0]
            w["cal"].configure(text="Done", fg_color=WARN)
            return
        lo, hi = self.calibrating.pop(i)
        w["cal"].configure(text="Calibrate", fg_color=ACCENT)
        if hi - lo < 200:
            messagebox.showwarning(
                "Calibration", f"Pedal {i + 1} only moved {hi - lo} counts. Move it over its full range and try again."
            )
            return
        margin = max(20, (hi - lo) * 3 // 100)  # keep the end points reachable
        for key, val in (("min", lo + margin), ("max", hi - margin)):
            w[key].delete(0, "end")
            w[key].insert(0, str(val))

    def _on_close(self):
        if not self._may_discard("Quit"):
            return
        LearnSession.stop()
        self._monitor_stop()
        self._live_disconnect()
        self.destroy()

    # --- Monitor tab ---------------------------------------------------------------
    def _setup_monitor_tab(self):
        tab = self.tabview.tab("Monitor")
        frame = ctk.CTkFrame(tab, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.monitor = None           # midi_monitor.Monitor while listening
        self.monitor_entries = collections.deque(maxlen=midi_monitor.KEEP)
        self.monitor_filter = midi_monitor.Filter()
        self.monitor_last = None      # the last entry shown, for the time since it
        self.monitor_shown = 0

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", pady=(0, 6))
        self.btn_monitor = ctk.CTkButton(top, text="Start", width=110, command=self._monitor_toggle)
        self.btn_monitor.pack(side="left")
        ctk.CTkButton(top, text="Clear", width=80, fg_color=FIELD, hover_color=FIELD_HOVER,
                      command=self._monitor_clear).pack(side="left", padx=8)
        self.lbl_monitor = ctk.CTkLabel(top, text="not listening", text_color=MUTED)
        self.lbl_monitor.pack(side="left", padx=6)

        Help(
            frame,
            "Every MIDI message arriving at the computer, from the pedal and every other input.",
            "Each row has the time since Start, the time since the row above, the port, the "
            "channel, a plain reading and the raw bytes in hex. The filters work on what has "
            "already arrived too, over the last 2000 messages. Clock and the pedal's replies to "
            "the configurator's own questions (many a second while the Virtual Pedal is "
            "connected) start hidden. Scroll up to stop following; scroll to the bottom to follow again.",
        ).pack(anchor="w", pady=(0, 6))

        filters = ctk.CTkFrame(frame, fg_color="transparent")
        filters.pack(fill="x", pady=(0, 6))
        self.monitor_kinds = {}
        for k in midi_monitor.KINDS:
            box = ctk.CTkCheckBox(filters, text=k, width=20, command=self._monitor_filter_changed)
            if k in self.monitor_filter.kinds:
                box.select()
            box.pack(side="left", padx=(0, 10))
            self.monitor_kinds[k] = box
        choose = ctk.CTkFrame(frame, fg_color="transparent")
        choose.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(choose, text="Channel").pack(side="left")
        self.monitor_channel = ctk.CTkOptionMenu(choose, values=["Any"] + CHANNELS, width=80,
                                                 command=lambda _v: self._monitor_filter_changed())
        self.monitor_channel.pack(side="left", padx=(6, 16))
        ctk.CTkLabel(choose, text="Port").pack(side="left")
        self.monitor_port = ctk.CTkOptionMenu(choose, values=[MONITOR_ALL_PORTS], width=240,
                                              command=lambda _v: self._monitor_filter_changed())
        self.monitor_port.pack(side="left", padx=6)

        head = ctk.CTkLabel(frame, text=MONITOR_HEADING, font=MONO, text_color=MUTED, anchor="w")
        head.pack(fill="x", padx=(6, 0))
        self.monitor_text = ctk.CTkTextbox(frame, font=MONO, wrap="none", fg_color=BG)
        self.monitor_text.pack(fill="both", expand=True)
        self.monitor_text.configure(state="disabled")

    def _monitor_toggle(self):
        if self.monitor is not None:
            self._monitor_stop()
            return
        try:
            mon = midi_monitor.Monitor()
        except Exception as e:
            messagebox.showerror("MIDI monitor", f"Cannot open the MIDI inputs: {e}")
            return
        if not mon.ports:
            mon.close()
            messagebox.showinfo("MIDI monitor", "The computer has no MIDI input to listen to.")
            return
        self.monitor = mon
        self._monitor_clear()
        self.monitor_port.configure(values=[MONITOR_ALL_PORTS] + mon.names)
        if self.monitor_port.get() not in mon.names:
            self.monitor_port.set(MONITOR_ALL_PORTS)
            self._monitor_filter_changed()
        self.btn_monitor.configure(text="Stop", fg_color=WARN)
        self.after(MONITOR_POLL_MS, self._monitor_poll, mon)

    def _monitor_stop(self):
        if getattr(self, "monitor", None) is None:
            return
        mon, self.monitor = self.monitor, None
        mon.close()
        self.btn_monitor.configure(text="Start", fg_color=ACCENT)
        self._monitor_status()

    def _monitor_clear(self):
        self.monitor_entries.clear()
        self.monitor_last = None
        self.monitor_shown = 0
        if self.monitor is not None:
            self.monitor.start = self.monitor.clock()
            self.monitor.drain()
        self.monitor_text.configure(state="normal")
        self.monitor_text.delete("1.0", "end")
        self.monitor_text.configure(state="disabled")
        self._monitor_status()

    def _monitor_status(self):
        if self.monitor is None:
            text = "not listening"
        else:
            n = len(self.monitor.names)
            text = f"listening to {n} input{'s' if n != 1 else ''}"
        total = len(self.monitor_entries)
        if total:
            text += f"  \u2014  {total} message{'s' if total != 1 else ''}, {self.monitor_shown} shown"
        self.lbl_monitor.configure(text=text)

    def _monitor_filter_changed(self):
        channel = self.monitor_channel.get()
        port = self.monitor_port.get()
        self.monitor_filter = midi_monitor.Filter(
            kinds=frozenset(k for k, box in self.monitor_kinds.items() if box.get()),
            channel=None if channel == "Any" else int(channel),
            port=None if port == MONITOR_ALL_PORTS else port,
        )
        # Draw again from what has arrived, under the new filter
        self.monitor_last = None
        self.monitor_shown = 0
        self.monitor_text.configure(state="normal")
        self.monitor_text.delete("1.0", "end")
        self.monitor_text.configure(state="disabled")
        self._monitor_show(list(self.monitor_entries), follow=True)

    def _monitor_show(self, entries, follow):
        rows = []
        for e in entries:
            if self.monitor_filter.passes(e):
                rows.append(midi_monitor.line(e, self.monitor_last))
                self.monitor_last = e
        if rows:
            box = self.monitor_text
            box.configure(state="normal")
            box.insert("end", "\n".join(rows) + "\n")
            self.monitor_shown += len(rows)
            # Only the last rows are kept on screen
            extra = self.monitor_shown - midi_monitor.KEEP
            if extra > 0:
                box.delete("1.0", f"{extra + 1}.0")
                self.monitor_shown -= extra
            box.configure(state="disabled")
            if follow:
                box.see("end")
        self._monitor_status()

    def _monitor_poll(self, mon):
        if mon is not self.monitor:
            return
        got = mon.drain()
        if got:
            self.monitor_entries.extend(got)
            # Follow the new rows unless the user has scrolled back
            follow = self.monitor_text.yview()[1] >= 0.999
            self._monitor_show(got, follow)
        self.after(MONITOR_POLL_MS, self._monitor_poll, mon)

    # --- Bank Enter tab -----------------------------------------------------------
    def _setup_bank_enter_tab(self):
        tab = self.tabview.tab("Bank Enter")
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 4))
        Help(
            top,
            "Commands sent once whenever a bank is entered, typically a Program Change for its patch.",
            "From any source: the bank switches, a Bank command or an incoming MIDI message. "
            "No release is sent, and Bank commands are ignored here. "
            "A Leave command splits the list: the commands below it are sent on leaving the bank "
            "instead, just before the next bank's, for instance to switch off what the bank "
            "switched on. They go out without pauses; a Wait at the top of the next bank's list "
            "spaces the two out.",
        ).pack(anchor="w")

        sel = ctk.CTkFrame(tab, fg_color="transparent")
        sel.pack(fill="x", padx=10)
        ctk.CTkLabel(sel, text="Bank:").pack(side="left")
        self.enter_bank_selector = ctk.CTkOptionMenu(
            sel, values=[str(i) for i in range(NUM_BANKS)], width=80,
            command=self._on_enter_bank_change,
        )
        self.enter_bank_selector.pack(side="left", padx=8)

        self.enter_frame = ctk.CTkScrollableFrame(tab)
        self.enter_frame.pack(fill="both", expand=True, padx=10, pady=8)

    def _on_enter_bank_change(self, bank):
        self.apply_bank_enter_changes()
        for w in self.enter_frame.winfo_children():
            w.destroy()
        self.enter_editors = []
        if self.df_enter is None:
            return
        match = self.df_enter[self.df_enter["Bank_Number"].map(clean) == clean(bank)]
        if not len(match):
            return
        self.enter_row = match.index[0]
        current = self.df_enter.loc[self.enter_row]
        table = ctk.CTkFrame(self.enter_frame)
        table.pack(fill="x")
        for slot in SLOTS:
            initial = {f: current.get(f"{slot}_{f}") for f in CMD_FIELDS}
            self.enter_editors.append(SlotEditor(table, slot, initial, types=ENTER_COMMAND_TYPES))

    def apply_bank_enter_changes(self):
        if not self.enter_editors or self.df_enter is None:
            return
        for editor in self.enter_editors:
            for field, val in editor.values().items():
                self.df_enter.at[self.enter_row, f"{editor.slot}_{field}"] = (
                    val if val != "" else float("nan")
                )

    # --- Bank Switch tab -----------------------------------------------------------
    def _setup_bank_switch_tab(self):
        tab = self.tabview.tab("Bank Switch")
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 4))
        Help(
            top,
            "Commands sent by the Bank Down and Bank Up switches, the same in every bank.",
            "Bank_Switch_Mode in the Global tab decides whether they also change bank (Bank+MIDI), "
            "change bank silently (Bank) or stop changing bank altogether (MIDI only), which turns "
            "the pedal into a ten switch controller. Each list fires as a tap, press then release, "
            "so toggles flip once. Bank commands are ignored here.",
        ).pack(anchor="w")

        sel = ctk.CTkFrame(tab, fg_color="transparent")
        sel.pack(fill="x", padx=10)
        ctk.CTkLabel(sel, text="Switch:").pack(side="left")
        self.bank_switch_selector = ctk.CTkOptionMenu(
            sel, values=BANK_SWITCH_CHOICES, width=170,
            command=self._on_bank_switch_change,
        )
        self.bank_switch_selector.pack(side="left", padx=8)

        self.bank_switch_frame = ctk.CTkScrollableFrame(tab)
        self.bank_switch_frame.pack(fill="both", expand=True, padx=10, pady=8)

    def _on_bank_switch_change(self, choice):
        self.apply_bank_switch_changes()
        for w in self.bank_switch_frame.winfo_children():
            w.destroy()
        self.bank_switch_editors = []
        if self.df_bank_switch is None:
            return
        switch, press = [p.strip() for p in choice.split("/")]
        df = self.df_bank_switch
        match = df[(df["Switch"].map(clean) == switch) & (df["Press"].map(clean) == press)]
        if not len(match):
            return
        self.bank_switch_row = match.index[0]
        current = df.loc[self.bank_switch_row]
        table = ctk.CTkFrame(self.bank_switch_frame)
        table.pack(fill="x")
        for slot in SLOTS:
            initial = {f: current.get(f"{slot}_{f}") for f in CMD_FIELDS}
            self.bank_switch_editors.append(SlotEditor(table, slot, initial))

    def apply_bank_switch_changes(self):
        if not self.bank_switch_editors or self.df_bank_switch is None:
            return
        if self.bank_switch_row is None:
            return
        for editor in self.bank_switch_editors:
            for field, val in editor.values().items():
                self.df_bank_switch.at[self.bank_switch_row, f"{editor.slot}_{field}"] = (
                    val if val != "" else float("nan")
                )

    # --- Setlist tab ---------------------------------------------------------------
    def _setup_setlist_tab(self):
        tab = self.tabview.tab("Setlist")
        Help(
            tab,
            "The order Bank Up and Bank Down follow when Follow the setlist is on in the Global tab.",
            "Relative Bank commands follow it too; GoTo still jumps to an exact bank. From a bank "
            "that is not in the list, Up enters at the first entry and Down at the last. Up to 32 "
            "entries; the list ends at the first empty row.",
        ).pack(anchor="w", padx=10, pady=(10, 6))
        self.setlist_frame = ctk.CTkScrollableFrame(tab)
        self.setlist_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _bank_choices(self):
        names = {}
        if self.df_banks is not None:
            for _, r in self.df_banks.iterrows():
                names[clean(r.get("Bank_Number"))] = clean(r.get("Bank_Name_Large"))
        return [NO_COMMAND] + [f"{b} {names.get(str(b), '')}".strip() for b in range(NUM_BANKS)]

    def populate_setlist(self):
        for w in self.setlist_frame.winfo_children():
            w.destroy()
        self.setlist_widgets = []
        choices = self._bank_choices()
        entries = []
        if self.df_setlist is not None:
            for _, r in self.df_setlist.iterrows():
                try:
                    pos = float(clean(r.get("Position")))
                    bank = int(float(clean(r.get("Bank_Number"))))
                except ValueError:
                    continue
                if 0 <= bank < NUM_BANKS:
                    entries.append((pos, bank))
        order = [b for _, b in sorted(entries, key=lambda e: e[0])]
        for i in range(SETLIST_MAX):
            line = ctk.CTkFrame(self.setlist_frame, fg_color="transparent")
            line.pack(fill="x", pady=2)
            ctk.CTkLabel(line, text=f"{i + 1:>2}", width=28, font=BOLD).pack(side="left")
            current = choices[order[i] + 1] if i < len(order) else NO_COMMAND
            w = Option(line, choices, current, width=200)
            w.pack(side="left", padx=6)
            self.setlist_widgets.append(w)

    def apply_setlist_changes(self):
        if not self.setlist_widgets:
            return
        rows = []
        for w in self.setlist_widgets:
            v = w.value()
            if v == NO_COMMAND:
                break
            try:
                bank = int(v.split()[0])
            except (ValueError, IndexError):
                break
            rows.append({"Position": str(len(rows) + 1), "Bank_Number": str(bank)})
        self.df_setlist = pd.DataFrame(rows, columns=["Position", "Bank_Number"])

    # --- Combos tab ----------------------------------------------------------------
    COMBO_LISTS = ["Short", "Long", "Double"]

    def _setup_combo_tab(self):
        tab = self.tabview.tab("Combos")
        Help(
            tab,
            "Two switches pressed together run a list of their own, instead of what either does alone.",
            "A combination runs any button's short, long or double press list, as a Macro does, so "
            "its commands live on a button of a bank you keep spare. It counts in one bank or in "
            "all of them; one for the bank showing wins over one for all banks. A switch that belongs "
            "to a combination waits for the other one, Two switches together within in the Global "
            "tab, 80 ms unless changed, and carries on as a normal press if it does not come. Up to "
            f"{COMBO_COUNT} combinations.",
        ).pack(anchor="w", padx=10, pady=(10, 6))
        self.combo_frame = ctk.CTkScrollableFrame(tab)
        self.combo_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def populate_combos(self):
        for w in self.combo_frame.winfo_children():
            w.destroy()
        self.combo_widgets = []
        banks = self._bank_choices()[1:]
        scopes = ["All banks"] + banks
        switches = [NO_COMMAND] + list(BUTTON_IDS)
        for col, text in enumerate(("", "SWITCHES", "", "", "IN", "RUNS BANK", "BUTTON", "LIST")):
            ctk.CTkLabel(self.combo_frame, text=text, font=FONT_SECTION, text_color=MUTED).grid(
                row=0, column=col, padx=6, pady=(8, 6), sticky="w")
        rows = []
        if self.df_combos is not None:
            rows = [r for _, r in self.df_combos.iterrows() if clean(r.get("Switches"))]
        for i in range(COMBO_COUNT):
            r = rows[i] if i < len(rows) else {}
            names = clean(r.get("Switches")).upper().replace("+", " ").split()
            first, second = (names + [NO_COMMAND, NO_COMMAND])[:2]
            scope = clean(r.get("Bank"))
            try:
                scope = banks[int(float(scope))] if scope and scope.upper() != "ALL" else scopes[0]
            except (ValueError, IndexError):
                scope = scopes[0]
            try:
                run_bank = banks[int(float(clean(r.get("Run_Bank"))))]
            except (ValueError, IndexError):
                run_bank = banks[0]
            ctk.CTkLabel(self.combo_frame, text=f"{i + 1:>2}", width=28, font=BOLD).grid(row=i + 1, column=0)
            widgets = {
                "first": Option(self.combo_frame, switches, first, width=80),
                "second": Option(self.combo_frame, switches, second, width=80),
                "scope": Option(self.combo_frame, scopes, scope, width=150),
                "bank": Option(self.combo_frame, banks, run_bank, width=150),
                "button": Option(self.combo_frame, list(BUTTON_IDS), clean(r.get("Run_Button")).upper(), width=70),
                "list": Option(self.combo_frame, self.COMBO_LISTS, clean(r.get("Run_List")).title(), width=90),
            }
            widgets["first"].grid(row=i + 1, column=1, padx=4, pady=2)
            ctk.CTkLabel(self.combo_frame, text="+").grid(row=i + 1, column=2)
            widgets["second"].grid(row=i + 1, column=3, padx=4, pady=2)
            for col, key in enumerate(("scope", "bank", "button", "list"), start=4):
                widgets[key].grid(row=i + 1, column=col, padx=4, pady=2)
            self.combo_widgets.append(widgets)

    def apply_combo_changes(self):
        if not self.combo_widgets:
            return
        rows = []
        for w in self.combo_widgets:
            first, second = w["first"].value(), w["second"].value()
            if NO_COMMAND in (first, second):
                continue
            scope = w["scope"].value()
            rows.append({
                "Switches": f"{first}+{second}",
                "Bank": "All" if scope == "All banks" else scope.split()[0],
                "Run_Bank": w["bank"].value().split()[0],
                "Run_Button": w["button"].value(),
                "Run_List": w["list"].value(),
            })
        self.df_combos = pd.DataFrame(rows, columns=COMBO_COLUMNS)

    # --- SysEx tab -----------------------------------------------------------------
    def _setup_sysex_tab(self):
        tab = self.tabview.tab("SysEx")
        Help(
            tab,
            "SysEx messages a SysEx command can send, in hexadecimal as the device manual shows them.",
            "A leading F0 and trailing F7 are optional and added when sending. Up to 23 data bytes, "
            "each 00-7F. A line that cannot be parsed is stored empty and nothing is sent.",
        ).pack(anchor="w", padx=10, pady=(10, 6))
        self.sysex_frame = ctk.CTkScrollableFrame(tab)
        self.sysex_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def populate_sysex(self):
        for w in self.sysex_frame.winfo_children():
            w.destroy()
        self.sysex_widgets = {}
        rows = {clean(r.get("Index")): r for _, r in self.df_sysex.iterrows()}
        for i in range(SYSEX_STRING_COUNT):
            line = ctk.CTkFrame(self.sysex_frame, fg_color="transparent")
            line.pack(fill="x", pady=2)
            ctk.CTkLabel(line, text=f"{i:>2}", width=24, font=BOLD).pack(side="left")
            src = rows.get(str(i))
            entry = TextEntry(line, 80, clean(src.get("Bytes")) if src is not None else "", width=430)
            entry.pack(side="left", padx=6)
            status = ctk.CTkLabel(line, text="", text_color=MUTED, width=160, anchor="w")
            status.pack(side="left")
            self.sysex_widgets[i] = (entry, status)
            entry.bind("<KeyRelease>", lambda _e, n=i: self._sysex_status(n))
            self._sysex_status(i)

    def _sysex_status(self, i):
        entry, status = self.sysex_widgets[i]
        text = entry.value().strip()
        if not text:
            status.configure(text="", text_color=MUTED)
            return
        data = parse_sysex_bytes(text)
        if data:
            status.configure(text=f"{len(data)} bytes", text_color=MUTED)
        else:
            status.configure(text="cannot be parsed", text_color=WARN)

    def apply_sysex_changes(self):
        if self.df_sysex is None:
            return
        rows = [{"Index": str(i), "Bytes": w[0].value().strip()}
                for i, w in sorted(self.sysex_widgets.items())]
        if rows:
            self.df_sysex = pd.DataFrame(rows)

    # --- Saving / device -----------------------------------------------------------
    def _collect(self):
        """Pull every tab's widgets into the DataFrames."""
        self.apply_button_changes(silent=True)
        self.apply_bank_enter_changes()
        self.apply_bank_switch_changes()
        self.apply_setlist_changes()
        self.apply_combo_changes()
        self.apply_sysex_changes()
        for idx, w in self.global_widgets.items():
            self.df_global.at[idx, "Value"] = w.value()
        self.apply_bank_changes()
        for i, w in self.exp_widgets.items():
            self.df_exp.at[i, "Min_ADC"] = w["min"].value() or "80"
            self.df_exp.at[i, "Max_ADC"] = w["max"].value() or "3900"
            self.df_exp.at[i, "Curve"] = w["curve"].value()
            self.df_exp.at[i, "Invert"] = w["invert"].value()
            self.df_exp.at[i, "Channel"] = w["channel"].value()
            self.df_exp.at[i, "Toe_Button"] = w["toe_button"].value()
            self.df_exp.at[i, "Heel_Button"] = w["heel_button"].value()
            self.df_exp.at[i, "Toe_Level"] = w["toe_level"].value() or "120"
            self.df_exp.at[i, "Heel_Level"] = w["heel_level"].value() or "7"
            self.df_exp.at[i, "Out_Min"] = w["out_min"].value() or "0"
            self.df_exp.at[i, "Out_Max"] = w["out_max"].value() or "127"
            self.df_exp.at[i, "Auto_Button"] = w["auto_button"].value()
            self.df_exp.at[i, "Auto_Off_ms"] = w["auto_off"].value() or "500"
            self.df_exp.at[i, "Output"] = w["output"].value()

    def apply_bank_changes(self):
        """Bank names and per bank expression settings back into their frames."""
        for idx, (large, small) in self.bank_widgets.items():
            self.df_banks.at[idx, "Bank_Name_Large"] = large.value()
            self.df_banks.at[idx, "Bank_Info_Small"] = small.value()

        def cc(text):
            text = text.strip()
            if text.lower() in ("", "default"):
                return ""
            if text.lower() == "off":
                return "Off"
            try:
                return str(max(0, min(127, int(float(text)))))
            except ValueError:
                return ""

        def channel(text):
            return "" if text in ("", "Default") else text

        for idx, widgets in self.bank_exp_widgets.items():
            for field, w in widgets.items():
                kind = field.split("_")[1]
                text = w.value()
                if kind == "CC":
                    text = cc(text)
                elif kind == "Channel":
                    text = channel(text)
                self.df_bank_exp.at[idx, field] = text

    def _write_csv(self, path):
        write_config_csv(
            path,
            self.df_global,
            self.df_banks,
            self.df_buttons,
            df_long_press=self.df_long,
            df_double_press=self.df_double,
            df_expression=self.df_exp,
            df_bank_enter=self.df_enter,
            df_sysex=self.df_sysex,
            df_bank_switch=self.df_bank_switch,
            df_setlist=self.df_setlist,
            df_bank_expression=self.df_bank_exp,
            df_combos=self.df_combos,
        )

    def _config_text(self):
        """The configuration as it would be saved now, to tell whether it changed."""
        if self.df_global is None:
            return None
        self._collect()
        fd, tmp = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            self._write_csv(tmp)
            with open(tmp, encoding="utf-8") as f:
                return f.read()
        finally:
            os.remove(tmp)

    def _unsaved(self):
        return self.saved_text is not None and self._config_text() != self.saved_text

    def _may_discard(self, action):
        """True when there are no unsaved changes, or the user lets them go."""
        if not self._unsaved():
            return True
        return messagebox.askyesno(
            action, "The configuration has changes that are not saved. Discard them?")

    def _ask_save_path(self):
        initial = self.loaded_name or "my_config.csv"
        if not self.current_csv_path and self.loaded_name:
            initial = "my_" + self.loaded_name
        return filedialog.asksaveasfilename(
            title="Save configuration as", defaultextension=".csv",
            initialfile=initial, filetypes=[("CSV Files", "*.csv")])

    def save_csv(self, path=None):
        path = path or self.current_csv_path or self._ask_save_path()
        if not path:
            return False
        if is_reference_csv(path):
            messagebox.showerror(
                "Save CSV", f"{os.path.basename(path)} comes with the tools and is kept as it is. "
                "Choose another name or folder.")
            return False
        try:
            self._collect()
            self._write_csv(path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Could not save CSV: {e}")
            return False
        self.current_csv_path = path
        self.loaded_name = os.path.basename(path)
        self._show_file()
        self.saved_text = self._config_text()
        messagebox.showinfo("Success", "CSV Saved Successfully!")
        return True

    def save_csv_as(self):
        path = self._ask_save_path()
        if path:
            self.save_csv(path)

    def _slot_args(self):
        """--slot for the device tools, unless the pedal's active slot is wanted."""
        choice = self.slot_selector.get()
        return [] if choice == "Active" else ["--slot", choice]

    def _run_tool(self, script, *args):
        self._live_disconnect()
        cmd = [sys.executable, os.path.join(HERE, script), *args]
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)

    def read_device(self):
        save_path = filedialog.asksaveasfilename(
            title="Save device configuration as",
            defaultextension=".csv",
            initialfile="device_config.csv",
            filetypes=[("CSV Files", "*.csv")],
        )
        if not save_path:
            return
        try:
            p = self._run_tool("Flash_to_CSV.py", save_path, *self._slot_args())
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to run read script: {e}")
            return
        if p.returncode != 0:
            detail = (p.stdout + "\n" + p.stderr).strip()
            messagebox.showerror("Read Error", detail or f"Exit code {p.returncode}")
            return
        self.load_csv(save_path)
        messagebox.showinfo("Read Complete", p.stdout.strip().splitlines()[-1])

    def backup_slots(self):
        parent = filedialog.askdirectory(title="Folder to put the backup in")
        if not parent:
            return
        folder = os.path.join(parent, datetime.datetime.now().strftime("midi-commander-backup-%Y%m%d-%H%M%S"))
        try:
            p = self._run_tool("Backup_Slots.py", "backup", folder)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to run backup script: {e}")
            return
        detail = (p.stdout + "\n" + p.stderr).strip()
        if p.returncode != 0:
            messagebox.showerror("Backup Error", detail or f"Exit code {p.returncode}")
            return
        saved = [l.strip() for l in p.stdout.splitlines() if l.strip().startswith("saved ")]
        messagebox.showinfo("Backup Complete", "\n".join(saved + ["", p.stdout.strip().splitlines()[-1]]))

    def restore_slots(self):
        folder = filedialog.askdirectory(title="Backup folder to restore")
        if not folder:
            return
        found = sorted(n for n in os.listdir(folder) if re.match(r"^slot[1-4]\.csv$", n, re.IGNORECASE))
        if not found:
            messagebox.showwarning("Restore", "That folder holds no slot1.csv to slot4.csv.")
            return
        if not messagebox.askyesno(
            "Restore Backup",
            "Write these files to the matching slots of the pedal, replacing what they hold?\n\n"
            + "\n".join(found)
            + "\n\nSlots with no file are left as they are. The pedal restarts at the end.",
        ):
            return
        try:
            p = self._run_tool("Backup_Slots.py", "restore", folder, "--yes")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to run restore script: {e}")
            return
        if p.returncode != 0:
            detail = (p.stdout + "\n" + p.stderr).strip()
            messagebox.showerror("Restore Error", detail[-1500:] or f"Exit code {p.returncode}")
            return
        messagebox.showinfo("Restore Complete", p.stdout.strip().splitlines()[-1])

    def update_firmware(self):
        path = filedialog.askopenfilename(
            title="Firmware to flash",
            filetypes=[("DFU images", "*.dfu"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            size = check_image(path)
        except UpdateError as e:
            messagebox.showerror("Update Firmware", f"Not flashing {os.path.basename(path)}:\n{e}")
            return
        if not messagebox.askyesno(
            "Update Firmware",
            f"Flash {os.path.basename(path)} ({size} bytes) to the pedal?\n\n"
            "With firmware 0.58 or later on it the pedal restarts in DFU mode by itself; "
            "older firmware needs Bank Down and D held while switching it on first. "
            "The configuration is left as it is. This takes about half a minute.",
        ):
            return
        try:
            p = self._run_tool("Update_Firmware.py", path, "--yes")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to run update script: {e}")
            return
        detail = (p.stdout + "\n" + p.stderr).strip()
        if p.returncode != 0:
            messagebox.showerror("Update Error", detail[-1500:] or f"Exit code {p.returncode}")
            return
        messagebox.showinfo("Update Complete", p.stdout.strip().splitlines()[-1])

    def banner_text(self):
        """The power on banner's own text, which the pedal keeps outside the
        configurations (firmware 0.63): read it, then edit, clear or keep it."""
        try:
            p = self._run_tool("Send_Text.py", "--banner")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to run Send_Text.py: {e}")
            return
        if p.returncode != 0:
            messagebox.showerror("Banner Text", (p.stdout + p.stderr).strip() or f"Exit code {p.returncode}")
            return
        current = p.stdout.rstrip("\n")
        if current.startswith("(no text"):
            current = ""

        win = ctk.CTkToplevel(self)
        win.title("Banner Text")
        win.transient(self)
        ctk.CTkLabel(
            win, font=FONT_SMALL, text_color=MUTED, justify="left", wraplength=460,
            text=f"Up to {BANNER_TEXT_MAX} characters: a band, a show, a phone number in case the "
                 "pedal is lost. It crosses the display at power on when Boot_Banner is on, in "
                 "place of the configuration's name, and it belongs to the pedal: it stays "
                 "whatever configuration is loaded and through firmware updates. Empty shows "
                 "the name again.",
        ).pack(padx=16, pady=(14, 8), anchor="w")
        entry = ctk.CTkEntry(win, width=460)
        entry.insert(0, current)
        entry.pack(padx=16, pady=4)
        count = ctk.CTkLabel(win, font=FONT_SMALL, text_color=MUTED)
        count.pack(padx=16, anchor="e")

        def update_count(*_):
            n = len(entry.get().rstrip())
            count.configure(text=f"{n} / {BANNER_TEXT_MAX}", text_color=DANGER if n > BANNER_TEXT_MAX else MUTED)

        entry.bind("<KeyRelease>", update_count)
        update_count()

        def store(text):
            try:
                banner_sysex(text)
            except ValueError as e:
                messagebox.showerror("Banner Text", str(e), parent=win)
                return
            q = self._run_tool("Send_Text.py", "--banner", text)
            if q.returncode != 0:
                messagebox.showerror("Banner Text", (q.stdout + q.stderr).strip(), parent=win)
                return
            win.destroy()
            messagebox.showinfo("Banner Text", f"The pedal now holds:\n{q.stdout.strip()}")

        buttons = ctk.CTkFrame(win, fg_color="transparent")
        buttons.pack(padx=16, pady=(8, 14), fill="x")
        ctk.CTkButton(buttons, text="Store", width=100, command=lambda: store(entry.get())).pack(side="right")
        ctk.CTkButton(buttons, text="Clear", width=100, fg_color=FIELD, hover_color=FIELD_HOVER,
                      command=lambda: store("")).pack(side="right", padx=8)
        ctk.CTkButton(buttons, text="Cancel", width=100, fg_color=FIELD, hover_color=FIELD_HOVER,
                      command=win.destroy).pack(side="left")
        win.grab_set()
        entry.focus_set()

    def flash_device(self):
        if self.df_global is None:
            messagebox.showwarning("Warning", "Please load a CSV file first.")
            return
        if self.current_csv_path:
            question = (f"Save the current settings to {os.path.basename(self.current_csv_path)} "
                        "and flash them?")
        else:
            question = ("Flash the current settings? They are not saved to a file: "
                        f"{self.loaded_name or 'this file'} comes with the tools and stays as it is.")
        if not messagebox.askyesno(
            "Flash Device",
            question + " Ensure the Midi Commander is connected via USB.\n(This will take a few seconds)",
        ):
            return

        self._collect()
        tmp = None
        try:
            if self.current_csv_path:
                self._write_csv(self.current_csv_path)
                self.saved_text = self._config_text()
                path = self.current_csv_path
            else:
                fd, tmp = tempfile.mkstemp(suffix=".csv")
                os.close(fd)
                self._write_csv(tmp)
                path = tmp
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Could not save CSV before flashing: {e}")
            return

        try:
            p = self._run_tool("CSV_to_Flash.py", path, "--yes", *self._slot_args())
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to run flash script: {e}")
            return
        finally:
            if tmp:
                os.remove(tmp)

        if p.returncode == 0:
            messagebox.showinfo(
                "Flash Success", "Flash Complete!\nSettings have been written to the device."
            )
            return

        with open(os.path.join(HERE, "flash_error.log"), "w", encoding="utf-8") as f:
            f.write(f"Output:\n{p.stdout}\n\nError:\n{p.stderr}")

        out = (p.stdout + p.stderr).lower()
        if "no matching midi device" in out or "no midi" in out:
            msg = "Midi Commander not found or disconnected.\nPlease check the USB connection."
        elif "stopped responding" in out:
            msg = "The device stopped responding while flashing. Power cycle it and try again."
        else:
            msg = (
                "Failed to access MIDI device.\n\nMost likely, the device is being used by "
                "another application (DAW, Chrome, etc).\n\nPlease close other MIDI "
                "applications and try again."
            )
        msg += f"\n\n(Technical details: exit code {p.returncode})"
        if p.stderr.strip():
            msg += f"\nError: {p.stderr.strip()[:200]}"
        messagebox.showerror("Flash Error", msg)


if __name__ == "__main__":
    app = MidiCommanderGUI()
    app.mainloop()
