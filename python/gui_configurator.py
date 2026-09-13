"""GUI configurator for the Midi Commander custom firmware.

Edits the sectioned configuration CSV (see lib/configCsv.py), reads the
configuration back from the device and flashes it. Every field with a bounded
set of values is a drop-down or a check box; numeric fields only accept
numbers inside their valid range.
"""

import os
import subprocess
import sys
from tkinter import filedialog, messagebox

import customtkinter as ctk
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib.cmdBinaryPacker import HID_SPECIAL_KEYS, MEDIA_KEYS  # noqa: E402
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
    empty_setlist,
    empty_sysex_strings,
    parse_sysex_bytes,
)
from lib.configPacker import (  # noqa: E402
    EXPRESSION_SECTION,
    LONG_PRESS_SECTION,
    empty_expression_settings,
    empty_long_press_settings,
)
from lib.midiDevice import DeviceNotFound, DeviceTimeout, MidiCommander  # noqa: E402
from lib import bankClipboard as bank_clipboard  # noqa: E402

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Loaded at start: the demo covers every feature, so it doubles as the
# reference for how anything is configured.
DEFAULT_CSV = os.path.join(HERE, "demo-all-features.csv")

# --- Value sets -------------------------------------------------------------
LED_MODES = ["Normal", "Reverse", "AlwaysOn"]
CHANNELS = [str(i) for i in range(1, 17)]
NO_COMMAND = "(none)"
COMMAND_TYPES = [NO_COMMAND, "PC", "CC", "Note", "PB", "CCInc", "Key", "Media", "Bank", "SysEx", "Tap", "Start", "Stop", "Panic", "Scene"]
TAP_MODES = ["Tap", "Clock"]
# A scene leaves a button alone, or switches it on or off
SCENE_STATES = ["-", "On", "Off"]
BANK_SWITCH_MODES = ["Bank", "Bank+MIDI", "MIDI only"]
BANK_SWITCH_CHOICES = [f"{sw} / {pr}" for sw, pr in BANK_SWITCH_LISTS]
CCINC_DIRECTIONS = ["Up", "Down"]
BANK_MODES = ["GoTo", "Up", "Down", "Config", "NextConfig"]
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

BOLD = ("Arial", 12, "bold")


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


# --- Slot editor ------------------------------------------------------------
class SlotEditor:
    """One row of the button editor: command type plus the fields it needs."""

    def __init__(self, parent, slot: str, initial: dict):
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
            self.frame, COMMAND_TYPES, cmd_type, width=80, command=self._rebuild
        )
        self.type_menu.pack(side="left", padx=4)

        # A frame with no children keeps its configured size instead of
        # shrinking, so give it a small one for slots without parameters.
        self.params = ctk.CTkFrame(self.frame, fg_color="transparent", width=10, height=30)
        self.params.pack(side="left")
        self._rebuild(self.type_menu.get())

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
            w = Option(self.params, CCINC_DIRECTIONS, self.initial.get("KeyMode_(Key)"), width=75)
            w.pack(side="left")
            self.widgets["ccincdir"] = w
            self._int("step", "Step", "OffValue_(CC)", 1, 127, width=50)
            self._int("on", "Start", "OnValue_(CC/PB)", 0, 127, width=55)
            self._check("toggle", "Wrap", "Toggle_(CC/PB/Note)")
        elif cmd_type == "Tap":
            self._label("Action")
            w = Option(self.params, TAP_MODES, self.initial.get("KeyMode_(Key)"), width=80)
            w.pack(side="left")
            self.widgets["tapmode"] = w
            ctk.CTkLabel(
                self.params,
                text="(Tap sets the tempo, Clock starts/stops the MIDI clock)",
                text_color="gray",
            ).pack(side="left", padx=8)
        elif cmd_type == "SysEx":
            self._label("String")
            w = Option(self.params, [str(i) for i in range(SYSEX_STRING_COUNT)],
                       self.initial.get("Number_(PC/CC/Note)"), width=70)
            w.pack(side="left")
            self.widgets["sysexindex"] = w
            ctk.CTkLabel(self.params, text="(edit the bytes in the SysEx tab)",
                         text_color="gray").pack(side="left", padx=8)
        elif cmd_type == "Bank":
            self._label("Action")
            w = Option(self.params, BANK_MODES, self.initial.get("KeyMode_(Key)"), width=80,
                       command=lambda _v: self._rebuild("Bank"))
            w.pack(side="left")
            self.widgets["bankmode"] = w
            mode = w.get()
            v = None
            if mode == "GoTo":
                self._label("Bank")
                v = Option(self.params, BANKS, self.initial.get("OnValue_(CC/PB)"), width=70)
            elif mode == "Config":
                self._label("Slot")
                v = Option(self.params, CONFIG_SLOT_NAMES, self.initial.get("OnValue_(CC/PB)") or "1", width=60)
            elif mode == "NextConfig":
                ctk.CTkLabel(self.params, text="(next slot holding a configuration)",
                             text_color="gray").pack(side="left", padx=8)
            else:
                self._label("Banks")
                v = IntEntry(self.params, 1, 31, self.initial.get("OnValue_(CC/PB)") or "8", width=55)
            if v is not None:
                v.pack(side="left")
                self.widgets["bankvalue"] = v
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
        if cmd_type == "CCInc":
            out["KeyMode_(Key)"] = w["ccincdir"].value()
            out["OffValue_(CC)"] = w["step"].value()
        if cmd_type == "SysEx":
            out["Number_(PC/CC/Note)"] = w["sysexindex"].value()
        if cmd_type == "Tap":
            out["KeyMode_(Key)"] = w["tapmode"].value()
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
        self.df_exp = None
        self.df_enter = None
        self.enter_editors = []
        self.df_sysex = None
        self.df_bank_switch = None
        self.df_setlist = None
        self.setlist_widgets = []
        self.bank_switch_editors = []
        self.bank_switch_row = None
        self.sysex_widgets = {}
        self.current_csv_path = None
        self.live = None            # MidiCommander while the live pedal view is on
        self.calibrating = {}       # pedal index -> [min_seen, max_seen]
        self.exp_widgets = {}       # pedal index -> dict of widgets
        self.press_mode = "Short press"
        self.editing_button = None  # (row_index, btn_id) of the button being edited
        self.bank_clipboard = None  # a copied bank, see lib/bankClipboard.py

        self.global_widgets = {}  # df index -> widget with .value()
        self.bank_widgets = {}  # df index -> (large, small)
        self.slot_editors = []
        self.editing_row = None
        self.light_mode = None
        self.label_entry = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(
            self.sidebar,
            text="Midi Commander\nConfigurator",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 10))

        ctk.CTkButton(self.sidebar, text="Load CSV", command=self.load_csv).grid(
            row=1, column=0, padx=20, pady=10
        )
        ctk.CTkButton(
            self.sidebar, text="Read from Device", command=self.read_device
        ).grid(row=2, column=0, padx=20, pady=10)
        ctk.CTkButton(self.sidebar, text="Save CSV", command=self.save_csv).grid(
            row=3, column=0, padx=20, pady=10
        )
        ctk.CTkButton(
            self.sidebar,
            text="FLASH TO DEVICE",
            fg_color="red",
            hover_color="darkred",
            command=self.flash_device,
        ).grid(row=4, column=0, padx=20, pady=20)

        # Configuration slot used by Read from Device and FLASH TO DEVICE
        slot_row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        slot_row.grid(row=5, column=0, padx=20, pady=(0, 10))
        ctk.CTkLabel(slot_row, text="Slot").pack(side="left", padx=(0, 8))
        self.slot_selector = ctk.CTkOptionMenu(slot_row, values=SLOT_TARGETS, width=90)
        self.slot_selector.set("Active")
        self.slot_selector.pack(side="left")

        # Tabs
        self.tabview = ctk.CTkTabview(self, width=900)
        self.tabview.grid(row=0, column=1, padx=(20, 0), pady=(20, 0), sticky="nsew")
        self.tabview.add("Global Settings")
        self.tabview.add("Button Config")
        self.tabview.add("Bank Names")
        self.tabview.add("Expression")
        self.tabview.add("Bank Enter")
        self.tabview.add("SysEx")
        self.tabview.add("Bank Switch")
        self.tabview.add("Setlist")

        self.global_scroll = ctk.CTkScrollableFrame(self.tabview.tab("Global Settings"))
        self.global_scroll.pack(fill="both", expand=True)

        self.bank_scroll = ctk.CTkScrollableFrame(self.tabview.tab("Bank Names"))
        self.bank_scroll.pack(fill="both", expand=True)

        self._setup_button_tab()
        self._setup_expression_tab()
        self._setup_bank_enter_tab()
        self._setup_sysex_tab()
        self._setup_bank_switch_tab()
        self._setup_setlist_tab()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if os.path.exists(DEFAULT_CSV):
            self.load_csv(DEFAULT_CSV)

    # --- Button tab layout ----------------------------------------------------
    def _setup_button_tab(self):
        tab = self.tabview.tab("Button Config")
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(tab, height=40)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        ctk.CTkLabel(top, text="Bank:").pack(side="left", padx=10)
        self.bank_selector = ctk.CTkOptionMenu(top, command=self.on_bank_change, width=80)
        self.bank_selector.pack(side="left", padx=10)
        ctk.CTkButton(top, text="Copy bank", width=100, command=self.copy_bank).pack(side="left", padx=(20, 6))
        self.paste_bank_button = ctk.CTkButton(
            top, text="Paste bank", width=160, command=self.paste_bank, state="disabled"
        )
        self.paste_bank_button.pack(side="left", padx=6)

        self.button_matrix = ctk.CTkFrame(tab, width=130)
        self.button_matrix.grid(row=1, column=0, sticky="ns", padx=(5, 0), pady=5)

        self.cmd_editor = ctk.CTkScrollableFrame(tab)
        self.cmd_editor.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        ctk.CTkLabel(self.cmd_editor, text="Select a button to edit", font=("Arial", 16)).pack(
            pady=10
        )

    # --- Loading ----------------------------------------------------------------
    def load_csv(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
            if not path:
                return
        try:
            data = read_config_csv(path)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to load CSV: {e}")
            return

        self.current_csv_path = path
        self.editing_row = None
        self.slot_editors = []

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
            ]
            missing = [{"Label": l, "Value": v} for l, v in defaults if l not in labels]
            if missing:
                self.df_global = pd.concat(
                    [self.df_global, pd.DataFrame(missing)], ignore_index=True
                )
            self.populate_global()

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

            self.df_exp = (
                data[EXPRESSION_SECTION].astype(object).reset_index(drop=True)
                if EXPRESSION_SECTION in data
                else empty_expression_settings()
            )
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

            banks = [str(b) for b in range(NUM_BANKS)]
            self.bank_selector.configure(values=banks)
            self.bank_selector.set(banks[0])
            self.on_bank_change(banks[0])

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
            columns += ["Light_Mode"]

        out = []
        for b in range(NUM_BANKS):
            for btn in BUTTON_IDS:
                src = rows.get((str(b), btn))
                row = {c: float("nan") for c in columns}
                row["Bank_Number"], row["Button_Identifier"] = str(b), btn
                if with_extras:
                    row["Label"] = ""
                    row["Light_Mode"] = "Normal"
                if src is not None:
                    for c in columns:
                        if c in src.index and c not in ("Bank_Number", "Button_Identifier"):
                            row[c] = src[c]
                out.append(row)
        return pd.DataFrame(out, columns=columns)

    # --- Global tab ---------------------------------------------------------------
    def populate_global(self):
        for w in self.global_scroll.winfo_children():
            w.destroy()
        self.global_widgets = {}

        for row, (idx, r) in enumerate(self.df_global.iterrows()):
            label = str(r["Label"])
            value = r["Value"]
            ctk.CTkLabel(self.global_scroll, text=label).grid(
                row=row, column=0, padx=10, pady=5, sticky="e"
            )

            if label == "MIDI_Channel":
                w = Option(self.global_scroll, CHANNELS, value, width=80)
            elif label in ("RealTime_Passthrough", "USB_MIDI_Thru", "Remember_State", "Setlist_Mode", "Clock_Follow", "LED_Feedback"):
                w = Check(self.global_scroll, text="", checked=is_yes(value))
            elif label in ("Bank_Up_LED_Mode", "Bank_Down_LED_Mode"):
                w = Option(self.global_scroll, LED_MODES, value, width=110)
            elif label in ("Exp1_CC", "Exp2_CC"):
                w = IntEntry(self.global_scroll, 0, 127, value, width=70)
            elif label == "Long_Press_ms":
                w = IntEntry(self.global_scroll, 100, 2500, value, width=70)
            elif label in ("LED_Brightness", "LED_Rest_Brightness"):
                w = IntEntry(self.global_scroll, 1, 100, value, width=70)
            elif label == "Bank_Jump_Step":
                w = IntEntry(self.global_scroll, 1, 31, value, width=70)
            elif label == "Bank_Change_Mode":
                w = Option(self.global_scroll, ["Off", "PC", "CC"], value, width=80)
            elif label == "Bank_Switch_Mode":
                w = Option(self.global_scroll, BANK_SWITCH_MODES, value, width=110)
            elif label == "Sleep_After_Min":
                w = IntEntry(self.global_scroll, 0, 60, value, width=70)
            elif label == "Bank_Change_Channel":
                w = Option(self.global_scroll, ["Any"] + CHANNELS, value, width=80)
            elif label == "Bank_Change_CC":
                w = IntEntry(self.global_scroll, 0, 127, value, width=70)
            elif label == "ConfigName":
                w = TextEntry(self.global_scroll, 16, value, width=180)
            else:
                w = TextEntry(self.global_scroll, 64, value, width=180)

            w.grid(row=row, column=1, padx=10, pady=5, sticky="w")
            self.global_widgets[idx] = w

        hints = {
            "MIDI_Channel": "channel used by the expression pedals",
            "RealTime_Passthrough": "forward Clock/Start/Continue/Stop from USB to DIN",
            "USB_MIDI_Thru": "forward all other MIDI from USB to DIN",
            "Remember_State": "restore the last bank and toggle states at power on",
            "Long_Press_ms": "hold time that turns a press into a long press (100-2500 ms)",
            "LED_Brightness": "brightness of a lit LED, 1-100 %",
            "LED_Rest_Brightness": "brightness of LEDs lit at rest by Reverse/AlwaysOn, 1-100 %",
            "Bank_Jump_Step": "banks skipped by a long press on Bank Up/Down (1-31)",
            "Bank_Change_Mode": "let an incoming PC or CC select a bank",
            "Bank_Change_Channel": "channel the pedal listens on for bank changes",
            "Bank_Change_CC": "CC number that selects a bank, when the mode is CC",
            "Bank_Switch_Mode": "what the Bank Up/Down switches do, see the Bank Switch tab",
            "Sleep_After_Min": "idle minutes before the display and LEDs go out, 0 = never",
            "Setlist_Mode": "Bank Up/Down follow the order in the Setlist tab",
            "Clock_Follow": "follow the tempo of MIDI clock from USB instead of sending our own",
            "LED_Feedback": "CC and notes from USB light the toggle buttons that send them",
            "ConfigName": "shown on the display at boot (16 chars)",
            "Exp1_CC": "CC number sent by expression pedal 1 (0-127)",
            "Exp2_CC": "CC number sent by expression pedal 2 (0-127)",
            "Bank_Up_LED_Mode": "LED of the Bank Up button",
            "Bank_Down_LED_Mode": "LED of the Bank Down button",
        }
        for row, (idx, r) in enumerate(self.df_global.iterrows()):
            hint = hints.get(str(r["Label"]))
            if hint:
                ctk.CTkLabel(self.global_scroll, text=hint, text_color="gray").grid(
                    row=row, column=2, padx=10, sticky="w"
                )

    # --- Bank tab -------------------------------------------------------------------
    def populate_banks(self):
        for w in self.bank_scroll.winfo_children():
            w.destroy()
        self.bank_widgets = {}

        ctk.CTkLabel(self.bank_scroll, text="Bank").grid(row=0, column=0)
        ctk.CTkLabel(self.bank_scroll, text="Name (large, 4 chars)").grid(row=0, column=1)
        ctk.CTkLabel(self.bank_scroll, text="Info (small, 8 chars)").grid(row=0, column=2)

        for row, (idx, r) in enumerate(self.df_banks.iterrows(), start=1):
            ctk.CTkLabel(self.bank_scroll, text=clean(r["Bank_Number"])).grid(
                row=row, column=0, padx=5, pady=2
            )
            large = TextEntry(self.bank_scroll, 4, r["Bank_Name_Large"], width=100)
            large.grid(row=row, column=1, padx=5, pady=2)
            small = TextEntry(self.bank_scroll, 8, r["Bank_Info_Small"], width=150)
            small.grid(row=row, column=2, padx=5, pady=2)
            self.bank_widgets[idx] = (large, small)

    # --- Button tab -------------------------------------------------------------
    def on_bank_change(self, bank_val):
        self.apply_button_changes(silent=True)
        for w in self.button_matrix.winfo_children():
            w.destroy()

        rows = self.df_buttons[
            self.df_buttons["Bank_Number"].map(clean) == clean(bank_val)
        ]
        for idx, row_data in rows.iterrows():
            btn_id = clean(row_data["Button_Identifier"])
            label = clean(row_data.get("Label"))
            ctk.CTkButton(
                self.button_matrix,
                text=f"{btn_id}   {label}" if label else f"Button {btn_id}",
                width=110,
                command=lambda rid=idx, bid=btn_id: self.load_button_commands(rid, bid),
            ).pack(pady=5, padx=8)

    # --- Copy and paste a whole bank -------------------------------------------------
    def copy_bank(self):
        if self.df_buttons is None:
            return
        # Take whatever is still in the editors along with it
        self.apply_button_changes(silent=True)
        self.apply_bank_enter_changes()
        bank = self.bank_selector.get()
        self.bank_clipboard = bank_clipboard.copy_bank(self.df_buttons, self.df_long, self.df_enter, bank)
        self.paste_bank_button.configure(state="normal", text=f"Paste bank {clean(bank)} here")

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
            "Labels, LED modes, short and long press commands and the commands sent on "
            "entering the bank are all replaced. The bank name is kept.",
        ):
            return
        self.apply_button_changes(silent=True)
        self.apply_bank_enter_changes()
        self.df_buttons, self.df_long, self.df_enter = bank_clipboard.paste_bank(
            self.df_buttons, self.df_long, self.df_enter, self.bank_clipboard, target
        )
        # The open editors point at rows that were just replaced: drop them
        # before refreshing, or they would write the old values back.
        self.editing_row = None
        self.editing_button = None
        self.slot_editors = []
        for w in self.cmd_editor.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.cmd_editor, text="Select a button to edit", font=("Arial", 16)).pack(pady=10)
        self.enter_editors = []
        self.on_bank_change(target)
        if self.enter_bank_selector.get():
            self._on_enter_bank_change(self.enter_bank_selector.get())

    def _long_row_index(self, row_index):
        """Index in df_long of the button at df_buttons row_index (created if missing)."""
        short = self.df_buttons.loc[row_index]
        bank, btn = clean(short["Bank_Number"]), clean(short["Button_Identifier"]).upper()
        match = self.df_long[
            (self.df_long["Bank_Number"].map(clean) == bank)
            & (self.df_long["Button_Identifier"].map(clean).str.upper() == btn)
        ]
        if len(match):
            return match.index[0]
        new_row = {c: float("nan") for c in self.df_long.columns}
        new_row["Bank_Number"], new_row["Button_Identifier"] = bank, btn
        self.df_long = pd.concat([self.df_long, pd.DataFrame([new_row])], ignore_index=True)
        return self.df_long.index[-1]

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
        self.label_entry = None
        self.light_mode = None
        long_mode = self.press_mode == "Long press"

        ctk.CTkLabel(
            self.cmd_editor,
            text=f"Bank {self.bank_selector.get()} - Button {btn_id}",
            font=("Arial", 16, "bold"),
        ).pack(anchor="w", padx=10, pady=(5, 5))

        current = self.df_buttons.loc[row_index]

        if not long_mode:
            light_frame = ctk.CTkFrame(self.cmd_editor, fg_color="transparent")
            light_frame.pack(anchor="w", padx=10, pady=(0, 8))
            ctk.CTkLabel(light_frame, text="Display label:", font=BOLD).pack(side="left")
            self.label_entry = TextEntry(light_frame, 4, current.get("Label"), width=70)
            self.label_entry.pack(side="left", padx=(8, 20))
            ctk.CTkLabel(light_frame, text="LED light mode:", font=BOLD).pack(side="left")
            self.light_mode = Option(light_frame, LED_MODES, current.get("Light_Mode"), width=110)
            self.light_mode.pack(side="left", padx=8)

        mode_frame = ctk.CTkFrame(self.cmd_editor, fg_color="transparent")
        mode_frame.pack(anchor="w", padx=10, pady=(0, 4))
        self.mode_switch = ctk.CTkSegmentedButton(
            mode_frame, values=["Short press", "Long press"], command=self._set_press_mode
        )
        self.mode_switch.set(self.press_mode)
        self.mode_switch.pack(side="left")
        ctk.CTkLabel(
            mode_frame,
            text=(
                "commands sent in order A to J when the button is held past Long_Press_ms"
                if long_mode
                else "commands sent in order A to J when the button is pressed"
            ),
            text_color="gray",
        ).pack(side="left", padx=10)

        if long_mode:
            current = self.df_long.loc[self._long_row_index(row_index)]

        table = ctk.CTkFrame(self.cmd_editor)
        table.pack(fill="x", padx=10, pady=(0, 5))
        for slot in SLOTS:
            initial = {f: current.get(f"{slot}_{f}") for f in CMD_FIELDS}
            self.slot_editors.append(SlotEditor(table, slot, initial))

        ctk.CTkLabel(
            self.cmd_editor,
            text=(
                "Dur = duration in 10 ms steps (0-127).  Bend = -8192..8191.  "
                "BankSel = MIDI Bank Select sent before a PC (0..16383).  "
                "Hold = key (or media key) stays pressed until the next press."
            ),
            text_color="gray",
            justify="left",
            wraplength=720,
        ).pack(anchor="w", padx=10)

        ctk.CTkButton(
            self.cmd_editor,
            text="Apply Changes to Memory",
            command=self.apply_button_changes,
            fg_color="green",
            hover_color="darkgreen",
        ).pack(anchor="w", padx=10, pady=12)

    def apply_button_changes(self, silent=False):
        """Copy the editor widgets back into df_buttons."""
        if self.editing_row is None or not self.slot_editors:
            return
        if self.press_mode == "Long press":
            df, idx = self.df_long, self._long_row_index(self.editing_row)
        else:
            df, idx = self.df_buttons, self.editing_row
        for editor in self.slot_editors:
            for field, val in editor.values().items():
                df.at[idx, f"{editor.slot}_{field}"] = val if val != "" else float("nan")
        if self.light_mode is not None:
            self.df_buttons.at[idx, "Light_Mode"] = self.light_mode.value()
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

        ctk.CTkLabel(
            self.exp_frame,
            text="Calibration: connect the pedal, press Calibrate, move the pedal slowly "
            "from heel to toe and back a couple of times, then press Done.",
            text_color="gray",
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(0, 6))

        top = ctk.CTkFrame(self.exp_frame, fg_color="transparent")
        top.pack(anchor="w", pady=(0, 8))
        self.btn_live = ctk.CTkButton(top, text="Connect live view", width=150, command=self._live_toggle)
        self.btn_live.pack(side="left")
        self.lbl_live = ctk.CTkLabel(top, text="not connected", text_color="gray")
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
            w["cal"] = ctk.CTkButton(head, text="Calibrate", width=90, state="disabled",
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

            self.exp_widgets[i] = w

        ctk.CTkLabel(
            self.exp_frame,
            text="Curve: Linear = proportional, Log = fast at the start, Exp = slow at the start. "
            "Channel Global = MIDI_Channel from Global Settings. CC numbers are Exp1_CC / Exp2_CC.\n"
            "As a switch, reaching the toe or returning to the heel taps a button of the current "
            "bank, sending whatever that button is configured to send. Each direction re-arms only "
            "after the pedal moves back past the level, so resting on the edge does not retrigger.",
            text_color="gray",
            wraplength=760,
            justify="left",
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
        self.lbl_live.configure(text=f"connected, firmware {version}")
        self.btn_live.configure(text="Disconnect")
        for w in self.exp_widgets.values():
            w["cal"].configure(state="normal")
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
            for w in self.exp_widgets.values():
                w["cal"].configure(state="disabled", text="Calibrate")

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
        self.after(60, self._live_poll)

    def _calibrate_toggle(self, i):
        w = self.exp_widgets[i]
        if i not in self.calibrating:
            self.calibrating[i] = [4095, 0]
            w["cal"].configure(text="Done", fg_color="darkorange")
            return
        lo, hi = self.calibrating.pop(i)
        w["cal"].configure(text="Calibrate", fg_color=["#3B8ED0", "#1F6AA5"])
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
        self._live_disconnect()
        self.destroy()

    # --- Bank Enter tab -----------------------------------------------------------
    def _setup_bank_enter_tab(self):
        tab = self.tabview.tab("Bank Enter")
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(
            top,
            text="Commands sent once when a bank is entered, from any source: bank buttons, "
            "a Bank command or an incoming MIDI message. Typically a Program Change that "
            "selects the patch for the bank. No release is sent, and Bank commands are ignored.",
            text_color="gray",
            wraplength=780,
            justify="left",
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
            self.enter_editors.append(SlotEditor(table, slot, initial))

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
        ctk.CTkLabel(
            top,
            text="Commands sent by the Bank Down and Bank Up switches themselves, the same "
            "in every bank. Bank_Switch_Mode in Global Settings decides whether they also "
            "change bank (Bank+MIDI), change bank silently (Bank) or stop changing bank "
            "altogether (MIDI only), which turns the pedal into a ten switch controller. "
            "Each list fires as a tap, press then release, so toggles flip once. Bank "
            "commands are ignored here.",
            text_color="gray",
            wraplength=780,
            justify="left",
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
        ctk.CTkLabel(
            tab,
            text="The order Bank Up and Bank Down follow when Setlist_Mode is on in Global "
            "Settings, instead of stepping through the bank numbers. Relative Bank commands "
            "follow it too; GoTo still jumps to an exact bank. From a bank that is not in the "
            "list, Up enters at the first entry and Down at the last. Up to 32 entries; the "
            "list ends at the first empty row.",
            text_color="gray",
            wraplength=780,
            justify="left",
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

    # --- SysEx tab -----------------------------------------------------------------
    def _setup_sysex_tab(self):
        tab = self.tabview.tab("SysEx")
        ctk.CTkLabel(
            tab,
            text="Stored SysEx messages a SysEx command can send. Write the bytes in "
            "hexadecimal as the device manual shows them; a leading F0 and trailing F7 "
            "are optional and added when sending. Up to 23 data bytes, each 00-7F. "
            "A line that cannot be parsed is stored empty and nothing is sent.",
            text_color="gray",
            wraplength=780,
            justify="left",
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
            status = ctk.CTkLabel(line, text="", text_color="gray", width=160, anchor="w")
            status.pack(side="left")
            self.sysex_widgets[i] = (entry, status)
            entry.bind("<KeyRelease>", lambda _e, n=i: self._sysex_status(n))
            self._sysex_status(i)

    def _sysex_status(self, i):
        entry, status = self.sysex_widgets[i]
        text = entry.value().strip()
        if not text:
            status.configure(text="", text_color="gray")
            return
        data = parse_sysex_bytes(text)
        if data:
            status.configure(text=f"{len(data)} bytes", text_color="gray")
        else:
            status.configure(text="cannot be parsed", text_color="orange")

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
        self.apply_sysex_changes()
        for idx, w in self.global_widgets.items():
            self.df_global.at[idx, "Value"] = w.value()
        for idx, (large, small) in self.bank_widgets.items():
            self.df_banks.at[idx, "Bank_Name_Large"] = large.value()
            self.df_banks.at[idx, "Bank_Info_Small"] = small.value()
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

    def save_csv(self):
        if not self.current_csv_path:
            save_path = filedialog.asksaveasfilename(defaultextension=".csv")
            if not save_path:
                return
            self.current_csv_path = save_path

        self._collect()
        try:
            write_config_csv(
                self.current_csv_path,
                self.df_global,
                self.df_banks,
                self.df_buttons,
                df_long_press=self.df_long,
                df_expression=self.df_exp,
                df_bank_enter=self.df_enter,
                df_sysex=self.df_sysex,
                df_bank_switch=self.df_bank_switch,
                df_setlist=self.df_setlist,
            )
            messagebox.showinfo("Success", "CSV Saved Successfully!")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Could not save CSV: {e}")

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

    def flash_device(self):
        if not self.current_csv_path:
            messagebox.showwarning("Warning", "Please save or load a CSV file first.")
            return
        if not messagebox.askyesno(
            "Flash Device",
            "Save the current settings and flash them? Ensure the Midi Commander "
            "is connected via USB.\n(This will take a few seconds)",
        ):
            return

        self._collect()
        try:
            write_config_csv(
                self.current_csv_path,
                self.df_global,
                self.df_banks,
                self.df_buttons,
                df_long_press=self.df_long,
                df_expression=self.df_exp,
                df_bank_enter=self.df_enter,
                df_sysex=self.df_sysex,
                df_bank_switch=self.df_bank_switch,
                df_setlist=self.df_setlist,
            )
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Could not save CSV before flashing: {e}")
            return

        try:
            p = self._run_tool("CSV_to_Flash.py", self.current_csv_path, "--yes", *self._slot_args())
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to run flash script: {e}")
            return

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
