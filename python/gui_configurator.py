import customtkinter as ctk
import pandas as pd
import os
import io
import sys
import subprocess
from tkinter import filedialog, messagebox

# Ensure we can import local modules
sys.path.append("python")

# Set theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class MidiCommanderGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MIDI Commander Configurator")
        self.geometry("1100x700")

        # Data placeholders
        self.df_global = None
        self.df_banks = None
        self.df_buttons = None
        self.current_csv_path = None

        # --- Layout ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="Midi Commander\nConfigurator",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.btn_load = ctk.CTkButton(
            self.sidebar_frame, text="Load CSV", command=self.load_csv
        )
        self.btn_load.grid(row=1, column=0, padx=20, pady=10)

        self.btn_save = ctk.CTkButton(
            self.sidebar_frame, text="Save CSV", command=self.save_csv
        )
        self.btn_save.grid(row=2, column=0, padx=20, pady=10)

        self.btn_flash = ctk.CTkButton(
            self.sidebar_frame,
            text="FLASH TO DEVICE",
            fg_color="red",
            hover_color="darkred",
            command=self.flash_device,
        )
        self.btn_flash.grid(row=3, column=0, padx=20, pady=20)

        # Tabs
        self.tabview = ctk.CTkTabview(self, width=850)
        self.tabview.grid(row=0, column=1, padx=(20, 0), pady=(20, 0), sticky="nsew")
        self.tabview.add("Global Settings")
        self.tabview.add("Button Config")
        self.tabview.add("Bank Names")

        # --- Global Settings Tab ---
        self.setup_global_tab()

        # --- Button Config Tab ---
        self.setup_button_tab()

        # --- Bank Names Tab ---
        self.setup_bank_tab()

        # Load default if exists
        default_csv = "python/MeloConfig_10_Cmds - RC-600.csv"
        if os.path.exists(default_csv):
            self.load_csv(default_csv)

    def setup_global_tab(self):
        self.global_frame = self.tabview.tab("Global Settings")
        self.global_entries = {}

        # Labels and Entries will be created dynamically on load
        self.global_scroll = ctk.CTkScrollableFrame(self.global_frame)
        self.global_scroll.pack(fill="both", expand=True)

    def setup_bank_tab(self):
        self.bank_frame = self.tabview.tab("Bank Names")
        self.bank_scroll = ctk.CTkScrollableFrame(self.bank_frame)
        self.bank_scroll.pack(fill="both", expand=True)
        self.bank_entries = {}

    def setup_button_tab(self):
        self.btn_cfg_frame = self.tabview.tab("Button Config")
        self.btn_cfg_frame.grid_columnconfigure(1, weight=1)
        self.btn_cfg_frame.grid_rowconfigure(1, weight=1)

        # Top: Bank Selector
        self.top_bar = ctk.CTkFrame(self.btn_cfg_frame, height=40)
        self.top_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

        self.lbl_bank = ctk.CTkLabel(self.top_bar, text="Select Bank:")
        self.lbl_bank.pack(side="left", padx=10)

        self.bank_selector = ctk.CTkOptionMenu(
            self.top_bar, command=self.on_bank_change
        )
        self.bank_selector.pack(side="left", padx=10)

        # Left: Button Matrix (10 buttons)
        self.button_matrix_frame = ctk.CTkFrame(self.btn_cfg_frame, width=300)
        self.button_matrix_frame.grid(row=1, column=0, sticky="ns", padx=5, pady=5)

        self.ui_buttons = []
        # Layout: 1-4, A-D, Up/Down?
        # Based on CSV: IDs are 1, 2, 3, 4, A, B, C, D, UP, DOWN (represented as 0A, 0B for bank change?)
        # Let's check CSV data. IDs are 1,2,3,4,A,B,C,D often.
        # I'll create a list of buttons dynamically.

        # Right: Command Editor (Scrollable)
        self.cmd_editor_frame = ctk.CTkScrollableFrame(self.btn_cfg_frame)
        self.cmd_editor_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        self.lbl_editing = ctk.CTkLabel(
            self.cmd_editor_frame, text="Select a button to edit", font=("Arial", 16)
        )
        self.lbl_editing.pack(pady=10)

        self.cmd_widgets = []

    def parse_csv_sections(self, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            raw_content = f.readlines()

        no_comments = [l for l in raw_content if "#" not in l]

        title_lines = []
        for i, l in enumerate(no_comments):
            if "*" in l:
                title_lines.append((l.replace(",", " ").strip(" *"), i))

        df_dic = {}
        for i, tline in enumerate(title_lines):
            start_line = tline[1] + 1
            if i == len(title_lines) - 1:
                end_line = len(no_comments)
            else:
                end_line = title_lines[i + 1][1]
            frame_lines = no_comments[start_line:end_line]

            # Clean up trailing commas which confuse pandas if column count mismatches
            cleaned_lines = []
            for ln in frame_lines:
                # Remove trailing commas/whitespace
                # But keep enough commas to match header? No, pandas is smart if we just remove empty trailing fields.
                # Actually, simpler to just let pandas handle it with on_bad_lines='skip' or use python engine?
                # Better: Trim trailing commas from the string itself.
                cleaned_lines.append(ln.rstrip().rstrip(","))

            csv_data = "\n".join(cleaned_lines)
            if not csv_data.strip():
                continue

            try:
                # Use python engine for more lenient parsing, and treat everything as string to avoid type errors on edit
                df = pd.read_csv(
                    io.StringIO(csv_data),
                    delimiter=",",
                    header=0,
                    engine="python",
                    dtype=str,
                ).dropna(how="all")
                # Remove unnamed columns
                df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
                df_dic[tline[0].strip()] = df
            except Exception as e:
                print(f"Error parsing section {tline[0]}: {e}")

        return df_dic

    def load_csv(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
            if not path:
                return

        self.current_csv_path = path
        try:
            data = self.parse_csv_sections(path)
            if "Global_Settings" in data:
                self.df_global = data["Global_Settings"].astype(object)
                # Clean up whitespace in Label
                self.df_global["Label"] = (
                    self.df_global["Label"].astype(str).str.strip()
                )

                # Check for Bank LED modes
                labels = self.df_global["Label"].tolist()
                new_rows = []
                if "Bank_Up_LED_Mode" not in labels:
                    new_rows.append({"Label": "Bank_Up_LED_Mode", "Value": "Normal"})
                if "Bank_Down_LED_Mode" not in labels:
                    new_rows.append({"Label": "Bank_Down_LED_Mode", "Value": "Normal"})

                if new_rows:
                    self.df_global = pd.concat(
                        [self.df_global, pd.DataFrame(new_rows)], ignore_index=True
                    )

                self.populate_global()

            if "Bank_Naming" in data:
                self.df_banks = data["Bank_Naming"].astype(object)
                self.populate_banks()

            if "Button_Settings" in data:
                self.df_buttons = data["Button_Settings"].astype(object)
                # Ensure columns are stripped
                self.df_buttons.columns = self.df_buttons.columns.str.strip()

                # Ensure Light_Mode column exists
                if "Light_Mode" not in self.df_buttons.columns:
                    self.df_buttons["Light_Mode"] = "Normal"
                else:
                    # Fill NaNs with Normal
                    self.df_buttons["Light_Mode"] = self.df_buttons[
                        "Light_Mode"
                    ].fillna("Normal")

                # Update bank selector
                banks = self.df_buttons["Bank_Number"].unique()
                self.bank_selector.configure(values=[str(b) for b in banks])
                self.bank_selector.set(str(banks[0]))
                self.on_bank_change(str(banks[0]))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV: {e}")
            print(e)  # Debug

    def populate_global(self):
        # Clear existing
        for w in self.global_scroll.winfo_children():
            w.destroy()
        self.global_entries = {}

        row = 0
        for index, r in self.df_global.iterrows():
            label_text = str(r["Label"])
            lbl = ctk.CTkLabel(self.global_scroll, text=label_text)
            lbl.grid(row=row, column=0, padx=10, pady=5, sticky="e")

            val = r["Value"]

            if label_text in ["Bank_Up_LED_Mode", "Bank_Down_LED_Mode"]:
                ent = ctk.CTkComboBox(
                    self.global_scroll, values=["Normal", "Reverse", "AlwaysOn"]
                )
                ent.set(str(val))
            else:
                ent = ctk.CTkEntry(self.global_scroll)
                ent.insert(0, str(val))

            ent.grid(row=row, column=1, padx=10, pady=5, sticky="w")

            self.global_entries[index] = ent
            row += 1

    def populate_banks(self):
        for w in self.bank_scroll.winfo_children():
            w.destroy()
        self.bank_entries = {}

        row = 0
        ctk.CTkLabel(self.bank_scroll, text="Bank Number").grid(row=0, column=0)
        ctk.CTkLabel(self.bank_scroll, text="Name (Large)").grid(row=0, column=1)
        ctk.CTkLabel(self.bank_scroll, text="Info (Small)").grid(row=0, column=2)
        row += 1

        for index, r in self.df_banks.iterrows():
            lbl_num = ctk.CTkLabel(self.bank_scroll, text=str(r["Bank_Number"]))
            lbl_num.grid(row=row, column=0, padx=5, pady=2)

            ent_name = ctk.CTkEntry(self.bank_scroll, width=150)
            if pd.notna(r["Bank_Name_Large"]):
                ent_name.insert(0, str(r["Bank_Name_Large"]))
            ent_name.grid(row=row, column=1, padx=5, pady=2)

            ent_info = ctk.CTkEntry(self.bank_scroll, width=150)
            if pd.notna(r["Bank_Info_Small"]):
                ent_info.insert(0, str(r["Bank_Info_Small"]))
            ent_info.grid(row=row, column=2, padx=5, pady=2)

            self.bank_entries[index] = (ent_name, ent_info)
            row += 1

    def on_bank_change(self, bank_val):
        # Populate buttons for this bank
        for w in self.button_matrix_frame.winfo_children():
            w.destroy()

        # Filter buttons (DataFrame is all strings now)
        # Handle potential float-like strings if reloaded
        # Safest is to convert column to string for comparison
        rows = self.df_buttons[
            self.df_buttons["Bank_Number"].astype(str) == str(bank_val)
        ]

        # We assume buttons are 1,2,3,4,A,B,C,D... etc.
        # Create a grid of buttons
        r = 0
        for i, row_data in rows.iterrows():
            btn_id = str(row_data["Button_Identifier"])
            btn = ctk.CTkButton(
                self.button_matrix_frame,
                text=f"Button {btn_id}",
                command=lambda rid=i, bid=btn_id: self.load_button_commands(rid, bid),
            )
            btn.pack(pady=5, padx=10, fill="x")

    def load_button_commands(self, row_index, btn_id):
        # Clear right panel
        for w in self.cmd_editor_frame.winfo_children():
            w.destroy()

        # Title
        # Recreate the label fresh
        self.lbl_editing = ctk.CTkLabel(
            self.cmd_editor_frame,
            text=f"Editing: Bank {self.bank_selector.get()} - Button {btn_id}",
            font=("Arial", 16, "bold"),
        )
        self.lbl_editing.pack(pady=(10, 20))

        current_row = self.df_buttons.loc[row_index]
        self.cmd_widgets = []  # Store widgets to save back later

        # Grid Container for Table
        table_frame = ctk.CTkFrame(self.cmd_editor_frame, fg_color="transparent")
        table_frame.pack(fill="x", padx=10)

        # --- Headers ---
        headers = [
            "Slot",
            "Type",
            "Channel",
            "Number",
            "On Value",
            "Off Value",
            "Delay/Dur",
            "Toggle",
            "Key Mode",
        ]
        widths = [40, 80, 60, 60, 70, 70, 60, 60, 80]

        for col, header in enumerate(headers):
            lbl = ctk.CTkLabel(table_frame, text=header, font=("Arial", 12, "bold"))
            lbl.grid(row=0, column=col, padx=5, pady=(0, 5))

        # --- Rows (Slots A-J) ---
        slots = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

        for i, slot in enumerate(slots):
            row = i + 1

            # Slot Label
            ctk.CTkLabel(table_frame, text=slot, width=widths[0]).grid(
                row=row, column=0, padx=5, pady=5
            )

            # Type
            type_val = current_row.get(f"{slot}_CommandType", "")
            if pd.isna(type_val):
                type_val = ""
            combo_type = ctk.CTkComboBox(
                table_frame,
                values=["", "CC", "PC", "Note", "PB", "Key"],
                width=widths[1],
            )
            combo_type.set(str(type_val).strip())
            combo_type.grid(row=row, column=1, padx=5, pady=5)

            # Channel
            ch_val = current_row.get(f"{slot}_Channel_(PC/CC/Note/PB)", "")
            ent_ch = ctk.CTkEntry(table_frame, width=widths[2])
            if pd.notna(ch_val):
                ent_ch.insert(0, str(ch_val).replace(".0", ""))  # Simple cleanup
            ent_ch.grid(row=row, column=2, padx=5, pady=5)

            # Number
            num_val = current_row.get(f"{slot}_Number_(PC/CC/Note)", "")
            ent_num = ctk.CTkEntry(table_frame, width=widths[3])
            if pd.notna(num_val):
                ent_num.insert(0, str(num_val).replace(".0", ""))
            ent_num.grid(row=row, column=3, padx=5, pady=5)

            # On Value
            on_val = current_row.get(f"{slot}_OnValue_(CC/PB)", "")
            ent_on = ctk.CTkEntry(table_frame, width=widths[4])
            if pd.notna(on_val):
                ent_on.insert(0, str(on_val).replace(".0", ""))
            ent_on.grid(row=row, column=4, padx=5, pady=5)

            # Off Value
            off_val = current_row.get(f"{slot}_OffValue_(CC)", "")
            ent_off = ctk.CTkEntry(table_frame, width=widths[5])
            if pd.notna(off_val):
                ent_off.insert(0, str(off_val).replace(".0", ""))
            ent_off.grid(row=row, column=5, padx=5, pady=5)

            # Duration (Labelled Delay/Dur in header)
            dur_val = current_row.get(f"{slot}_Duration_(Note/PB)", "")
            ent_dur = ctk.CTkEntry(table_frame, width=widths[6])
            if pd.notna(dur_val):
                ent_dur.insert(0, str(dur_val).replace(".0", ""))
            ent_dur.grid(row=row, column=6, padx=5, pady=5)

            # Toggle
            tog_val = current_row.get(f"{slot}_Toggle_(CC/PB/Note)", "")
            chk_tog = ctk.CTkCheckBox(table_frame, text="", width=20)
            if str(tog_val).strip().upper() == "Y":
                chk_tog.select()
            chk_tog.grid(row=row, column=7, padx=5, pady=5)

            # Key Mode (New)
            km_val = current_row.get(f"{slot}_KeyMode_(Key)", "")
            combo_km = ctk.CTkComboBox(
                table_frame,
                values=["Normal", "Down", "Up"],
                width=widths[8],
            )
            # Default to Normal if empty?
            if not km_val or pd.isna(km_val):
                combo_km.set("Normal")
            else:
                combo_km.set(str(km_val).strip())

            combo_km.grid(row=row, column=8, padx=5, pady=5)

            # Save ref
            self.cmd_widgets.append(
                {
                    "row_index": row_index,
                    "slot": slot,
                    "type": combo_type,
                    "ch": ent_ch,
                    "num": ent_num,
                    "on": ent_on,
                    "off": ent_off,
                    "dur": ent_dur,
                    "tog": chk_tog,
                    "keymode": combo_km,
                }
            )

        # --- Light Mode Setting ---
        light_frame = ctk.CTkFrame(self.cmd_editor_frame, fg_color="transparent")
        light_frame.pack(pady=10)

        ctk.CTkLabel(
            light_frame, text="LED Light Mode:", font=("Arial", 12, "bold")
        ).pack(side="left", padx=5)

        current_light = "Normal"
        if "Light_Mode" in current_row:
            val = current_row["Light_Mode"]
            if pd.notna(val) and str(val).strip() != "":
                current_light = str(val).strip()

        self.combo_light_mode = ctk.CTkComboBox(
            light_frame, values=["Normal", "Reverse", "AlwaysOn"], width=120
        )
        self.combo_light_mode.set(current_light)
        self.combo_light_mode.pack(side="left", padx=5)

        btn_apply = ctk.CTkButton(
            self.cmd_editor_frame,
            text="Apply Changes to Memory",
            command=self.apply_button_changes,
            fg_color="green",
            hover_color="darkgreen",
        )
        btn_apply.pack(pady=20)

    def apply_button_changes(self):
        def safe_val(val, dtype_hint=None):
            # Try to keep as number if it looks like one
            if not val:
                return float("nan")  # Empty string -> NaN
            if str(val).isdigit():
                return int(val)
            try:
                return float(val)
            except ValueError:
                return str(val)

        for w in self.cmd_widgets:
            idx = w["row_index"]
            s = w["slot"]

            # Helper to set value with type awareness
            # Since the dataframe might have mixed types or floats (with NaNs), we need to be careful.
            # Best approach: explicitely cast based on what we expect or force column to object type.
            # For simplicity, we try to cast to what pandas likely inferred.

            self.df_buttons.at[idx, f"{s}_CommandType"] = w["type"].get()
            self.df_buttons.at[idx, f"{s}_Channel_(PC/CC/Note/PB)"] = safe_val(
                w["ch"].get()
            )
            self.df_buttons.at[idx, f"{s}_Number_(PC/CC/Note)"] = safe_val(
                w["num"].get()
            )
            self.df_buttons.at[idx, f"{s}_OnValue_(CC/PB)"] = safe_val(w["on"].get())
            self.df_buttons.at[idx, f"{s}_OffValue_(CC)"] = safe_val(w["off"].get())
            self.df_buttons.at[idx, f"{s}_Duration_(Note/PB)"] = safe_val(
                w["dur"].get()
            )
            self.df_buttons.at[idx, f"{s}_Toggle_(CC/PB/Note)"] = (
                "Y" if w["tog"].get() == 1 else "N"
            )
            # Save Key Mode
            self.df_buttons.at[idx, f"{s}_KeyMode_(Key)"] = w["keymode"].get()

        # Save Light Mode
        if hasattr(self, "combo_light_mode") and self.cmd_widgets:
            idx = self.cmd_widgets[0]["row_index"]
            # Ensure column exists
            if "Light_Mode" not in self.df_buttons.columns:
                self.df_buttons["Light_Mode"] = "Normal"

            self.df_buttons.at[idx, "Light_Mode"] = self.combo_light_mode.get()

        print("Updated button memory.")
        messagebox.showinfo(
            "Info", "Changes applied to memory (Don't forget to Save CSV!)"
        )

    def save_csv(self):
        if not self.current_csv_path:
            save_path = filedialog.asksaveasfilename(defaultextension=".csv")
            if not save_path:
                return
            self.current_csv_path = save_path

        # Save updates from Global and Bank tabs back to DF
        for idx, ent in self.global_entries.items():
            self.df_global.at[idx, "Value"] = ent.get()

        for idx, (ename, einfo) in self.bank_entries.items():
            self.df_banks.at[idx, "Bank_Name_Large"] = ename.get()
            self.df_banks.at[idx, "Bank_Info_Small"] = einfo.get()

        # Write to file manualy to preserve structure
        try:
            with open(self.current_csv_path, "w", newline="", encoding="utf-8") as f:
                # Header
                f.write("# Notes" + "," * 50 + "\n")
                f.write("# Generated by GUI" + "," * 50 + "\n")
                f.write("#" + "," * 50 + "\n")

                # Global
                f.write("* Global_Settings" + "," * 50 + "\n")
                self.df_global.to_csv(f, index=False)
                f.write("," * 50 + "\n")

                # Bank
                f.write("* Bank_Naming" + "," * 50 + "\n")
                self.df_banks.to_csv(f, index=False)
                f.write("," * 50 + "\n")

                # Button
                f.write("* Button_Settings" + "," * 50 + "\n")
                # Important comments for parser????? Parser just skips #
                self.df_buttons.to_csv(f, index=False)

            messagebox.showinfo("Success", "CSV Saved Successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"Could not save CSV: {e}")

    def flash_device(self):
        if not self.current_csv_path:
            messagebox.showwarning("Warning", "Please save or load a CSV file first.")
            return

        # Ensure user saved
        ans = messagebox.askyesno(
            "Flash Device",
            "Are you ready to flash? Ensure the Midi Commander is connected via USB.\n(This will take a few seconds)",
        )
        if not ans:
            return

        # Use subprocess to isolate execution and prevent app crashes
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "CSV_to_Flash.py"
        )

        try:
            # Run with --yes to skip prompt
            cmd = [sys.executable, script_path, self.current_csv_path, "--yes"]

            # Hide console window on Windows? (optional, but keep it simple for now)
            # Create NO_WINDOW flag if needed, but let's just capture output.
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            p = subprocess.run(
                cmd, capture_output=True, text=True, startupinfo=startupinfo
            )

            if p.returncode == 0:
                # Success - simplify message
                # Maybe extract byte count if present in stdout?
                msg = "Flash Complete!\nSettings have been written to the device."
                messagebox.showinfo("Flash Success", msg)
            else:
                # Log error for debugging
                err_msg = f"Output:\n{p.stdout}\n\nError:\n{p.stderr}"
                with open("flash_error.log", "w", encoding="utf-8") as f:
                    f.write(err_msg)

                # Analyze error
                user_msg = ""

                # Known specific errors
                if (
                    "no input found" in p.stdout.lower()
                    or "no outputs found" in p.stdout.lower()
                ):
                    user_msg = "Midi Commander not found or disconnected.\nPlease check the USB connection."
                else:
                    # Default error assumption: Device is busy
                    user_msg = "Failed to access MIDI device.\n\nMost likely, the device is being used by another application (DAW, Chrome, etc)."
                    user_msg += (
                        "\n\nPlease close other MIDI applications and try again."
                    )

                # Append technical info slightly separated
                user_msg += f"\n\n(Technical details: Exit Code {p.returncode})"
                if p.stderr.strip():
                    user_msg += (
                        f"\nError: {p.stderr.strip()[:100]}..."  # Truncate if too long
                    )

                messagebox.showerror("Flash Error", user_msg)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to run flash script: {e}")


if __name__ == "__main__":
    app = MidiCommanderGUI()
    app.mainloop()
