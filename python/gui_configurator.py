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

from lib.cmdBinaryPacker import HID_SPECIAL_KEYS  # noqa: E402
from lib.configCsv import read_config_csv, write_config_csv  # noqa: E402

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

DEFAULT_CSV = os.path.join(HERE, "MeloConfig_10_Cmds - RC-600.csv")

# --- Value sets -------------------------------------------------------------
LED_MODES = ["Normal", "Reverse", "AlwaysOn"]
CHANNELS = [str(i) for i in range(1, 17)]
NO_COMMAND = "(none)"
COMMAND_TYPES = [NO_COMMAND, "PC", "CC", "Note", "PB", "Key", "Start", "Stop"]
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
            self._int("bank", "Bank", "BankSelect_(PC)", 0, 16383, width=65)
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
        # Start, Stop and (none) have no parameters

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
        self.current_csv_path = None

        self.global_widgets = {}  # df index -> widget with .value()
        self.bank_widgets = {}  # df index -> (large, small)
        self.slot_editors = []
        self.editing_row = None
        self.light_mode = None

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

        # Tabs
        self.tabview = ctk.CTkTabview(self, width=900)
        self.tabview.grid(row=0, column=1, padx=(20, 0), pady=(20, 0), sticky="nsew")
        self.tabview.add("Global Settings")
        self.tabview.add("Button Config")
        self.tabview.add("Bank Names")

        self.global_scroll = ctk.CTkScrollableFrame(self.tabview.tab("Global Settings"))
        self.global_scroll.pack(fill="both", expand=True)

        self.bank_scroll = ctk.CTkScrollableFrame(self.tabview.tab("Bank Names"))
        self.bank_scroll.pack(fill="both", expand=True)

        self._setup_button_tab()

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
            ]
            missing = [{"Label": l, "Value": v} for l, v in defaults if l not in labels]
            if missing:
                self.df_global = pd.concat(
                    [self.df_global, pd.DataFrame(missing)], ignore_index=True
                )
            self.populate_global()

        if "Bank_Naming" in data:
            self.df_banks = data["Bank_Naming"].astype(object).reset_index(drop=True)
            self.populate_banks()

        if "Button_Settings" in data:
            self.df_buttons = data["Button_Settings"].astype(object).reset_index(drop=True)
            if "Light_Mode" not in self.df_buttons.columns:
                self.df_buttons["Light_Mode"] = "Normal"
            else:
                self.df_buttons["Light_Mode"] = self.df_buttons["Light_Mode"].fillna("Normal")
            for slot in SLOTS:
                for field in CMD_FIELDS:
                    col = f"{slot}_{field}"
                    if col not in self.df_buttons.columns:
                        self.df_buttons[col] = float("nan")

            banks = [clean(b) for b in self.df_buttons["Bank_Number"].unique()]
            self.bank_selector.configure(values=banks)
            self.bank_selector.set(banks[0])
            self.on_bank_change(banks[0])

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
            elif label in ("RealTime_Passthrough", "USB_MIDI_Thru"):
                w = Check(self.global_scroll, text="", checked=is_yes(value))
            elif label in ("Bank_Up_LED_Mode", "Bank_Down_LED_Mode"):
                w = Option(self.global_scroll, LED_MODES, value, width=110)
            elif label in ("Exp1_CC", "Exp2_CC"):
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
            ctk.CTkButton(
                self.button_matrix,
                text=f"Button {btn_id}",
                width=110,
                command=lambda rid=idx, bid=btn_id: self.load_button_commands(rid, bid),
            ).pack(pady=5, padx=8)

    def load_button_commands(self, row_index, btn_id):
        self.apply_button_changes(silent=True)

        for w in self.cmd_editor.winfo_children():
            w.destroy()
        self.slot_editors = []
        self.editing_row = row_index

        ctk.CTkLabel(
            self.cmd_editor,
            text=f"Bank {self.bank_selector.get()} - Button {btn_id}",
            font=("Arial", 16, "bold"),
        ).pack(anchor="w", padx=10, pady=(5, 5))

        current = self.df_buttons.loc[row_index]

        light_frame = ctk.CTkFrame(self.cmd_editor, fg_color="transparent")
        light_frame.pack(anchor="w", padx=10, pady=(0, 8))
        ctk.CTkLabel(light_frame, text="LED light mode:", font=BOLD).pack(side="left")
        self.light_mode = Option(light_frame, LED_MODES, current.get("Light_Mode"), width=110)
        self.light_mode.pack(side="left", padx=8)

        ctk.CTkLabel(
            self.cmd_editor,
            text="Commands, sent in order A to J when the button is pressed:",
            font=BOLD,
        ).pack(anchor="w", padx=10, pady=(0, 2))

        table = ctk.CTkFrame(self.cmd_editor)
        table.pack(fill="x", padx=10, pady=(0, 5))
        for slot in SLOTS:
            initial = {f: current.get(f"{slot}_{f}") for f in CMD_FIELDS}
            self.slot_editors.append(SlotEditor(table, slot, initial))

        ctk.CTkLabel(
            self.cmd_editor,
            text=(
                "Dur = duration in 10 ms steps (0-127).  Bend = -8192..8191.  "
                "Bank = 0..16383.  Hold = key stays pressed until the next press."
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
        idx = self.editing_row
        for editor in self.slot_editors:
            for field, val in editor.values().items():
                self.df_buttons.at[idx, f"{editor.slot}_{field}"] = (
                    val if val != "" else float("nan")
                )
        if self.light_mode is not None:
            self.df_buttons.at[idx, "Light_Mode"] = self.light_mode.value()

        if not silent:
            messagebox.showinfo(
                "Info", "Changes applied to memory (Don't forget to Save CSV!)"
            )

    # --- Saving / device -----------------------------------------------------------
    def _collect(self):
        """Pull every tab's widgets into the DataFrames."""
        self.apply_button_changes(silent=True)
        for idx, w in self.global_widgets.items():
            self.df_global.at[idx, "Value"] = w.value()
        for idx, (large, small) in self.bank_widgets.items():
            self.df_banks.at[idx, "Bank_Name_Large"] = large.value()
            self.df_banks.at[idx, "Bank_Info_Small"] = small.value()

    def save_csv(self):
        if not self.current_csv_path:
            save_path = filedialog.asksaveasfilename(defaultextension=".csv")
            if not save_path:
                return
            self.current_csv_path = save_path

        self._collect()
        try:
            write_config_csv(
                self.current_csv_path, self.df_global, self.df_banks, self.df_buttons
            )
            messagebox.showinfo("Success", "CSV Saved Successfully!")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Could not save CSV: {e}")

    def _run_tool(self, script, *args):
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
            p = self._run_tool("Flash_to_CSV.py", save_path)
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
                self.current_csv_path, self.df_global, self.df_banks, self.df_buttons
            )
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"Could not save CSV before flashing: {e}")
            return

        try:
            p = self._run_tool("CSV_to_Flash.py", self.current_csv_path, "--yes")
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
