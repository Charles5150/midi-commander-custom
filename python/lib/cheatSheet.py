"""A configuration as a page to print: for the floor, the band or the tech.

One block per bank in use, its eight switches laid out as on the pedal, 1 2 3
4 above and A B C D below, each with its label and what its short, long and
double presses send, in words; a command a known device answers to is named
as the device names it ("HX Stomp: FS4"). Then the setlist in its order with
each song's tempo, the expression pedals, the bank switches and the
combinations.

The configuration is packed and read back first, as diff does, so the page
shows what the pedal would hold. Plain HTML with its own style, light, for
paper: Cheat_Sheet.py writes it to a file, the configurators open it in the
browser, whose Print makes the PDF.
"""

from html import escape

import lib.deviceDictionary as devices
from lib.configDiff import command_text, config_sections
from lib.configPacker import setlists
from lib.configSchema import CMD_FIELDS, MODIFIERS, NO_COMMAND, SLOTS
from lib.flashLayout import BUTTON_IDS

ROWS = (BUTTON_IDS[:4], BUTTON_IDS[4:])     # the pedal's top row, then the bottom one
PRESSES = (("Button_Settings", "Press"), ("LongPress_Settings", "Long"), ("DoublePress_Settings", "Double"))

STYLE = """
@page { size: A4; margin: 12mm; }
* { box-sizing: border-box; }
body { margin: 16px; background: #fff; color: #111; font: 10pt/1.3 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
h1 { font-size: 16pt; margin: 0 0 2px; }
h2 { font-size: 12pt; margin: 18px 0 6px; border-bottom: 1px solid #999; }
h3 { font-size: 11pt; margin: 0 0 4px; }
.sub { color: #555; margin: 0 0 10px; }
.print { float: right; font: inherit; padding: 4px 12px; }
.bank { break-inside: avoid; margin: 0 0 12px; }
.bank h3 small { font-weight: normal; color: #555; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; }
.sw { border: 1px solid #888; border-radius: 4px; padding: 3px 5px; min-height: 3.2em; overflow-wrap: anywhere; }
.sw b { font-family: Menlo, Consolas, monospace; font-size: 11pt; }
.sw .id { float: right; color: #888; font-size: 8pt; }
.sw p { margin: 1px 0; font-size: 8.5pt; }
.sw p i { color: #555; font-style: normal; }
.sw.empty { border-style: dashed; color: #aaa; }
.note { font-size: 8.5pt; margin: 3px 0 0; }
table { border-collapse: collapse; width: 100%; font-size: 9pt; }
th, td { text-align: left; padding: 2px 6px; border-bottom: 1px solid #ddd; vertical-align: top; }
th { font-weight: 600; }
@media print { body { margin: 0; } .print { display: none; } }
"""


def _yes(text) -> bool:
    return str(text or "").upper().startswith("Y")


class _Sheet:
    def __init__(self, sections: dict, chosen=None):
        self.s = config_sections(sections)
        self.devices = devices.guess(devices.config_commands(sections), chosen)
        self.settings = {r["Label"]: r.get("Value", "") for r in self.s.get("Global_Settings", [])}
        self.names = {r["Bank_Number"]: (r.get("Bank_Name_Large", ""), r.get("Bank_Info_Small", ""))
                      for r in self.s.get("Bank_Naming", [])}
        self.presets = {r["Program"]: r.get("Name", "") for r in self.s.get("Preset_Names", []) if r.get("Name")}
        self.rows = {name: {(r["Bank_Number"], r["Button_Identifier"]): r for r in self.s.get(name, [])}
                     for name, _ in PRESSES}
        self.enter = {r["Bank_Number"]: r for r in self.s.get("BankEnter_Settings", [])}

    def bank_name(self, number: str) -> str:
        name, info = self.names.get(str(number), ("", ""))
        return " ".join(t for t in (str(number), name, info and f"({info})") if t)

    # --- commands in words -------------------------------------------------------
    def words(self, cmd: dict) -> str:
        kind = cmd.get("CommandType", "")
        channel = self.settings.get("Global_Channel", "")
        channel = channel if channel.isdigit() else cmd.get("Channel_(PC/CC/Note/PB)", "")
        named = devices.describe(self.devices, channel, kind, cmd.get("Number_(PC/CC/Note)"),
                                 cmd.get("OnValue_(CC/PB)"), cmd.get("Toggle_(CC/PB/Note)"))
        number, on, mode = cmd.get("Number_(PC/CC/Note)", ""), cmd.get("OnValue_(CC/PB)", ""), cmd.get("KeyMode_(Key)", "")
        if kind == "PC":
            preset = self.presets.get(number)
            text = f"Program {number}" + (f" {preset}" if preset else "") + (f", ch {channel}" if channel else "")
            return f"{named} ({text})" if named else text
        if named:
            return named
        if kind == "Bank" and mode in ("GoTo", "Page"):
            return f"Bank {'go to' if mode == 'GoTo' else 'page'} {self.bank_name(on)}"
        if kind == "Bank" and mode in ("Up", "Down"):
            return f"Bank {mode.lower()} {on or 1}"
        if kind == "Bank":
            return f"Bank {mode}"
        if kind == "Key":
            bits = int(number) if number.isdigit() else 0
            keys = [n for n, b in MODIFIERS if bits & b] + [on]
            held = " (held)" if _yes(cmd.get("Toggle_(CC/PB/Note)")) else ""
            return f"Key {'+'.join(keys)}" + ("" if mode in ("", "Normal") else f" {mode.lower()}") + held
        if kind == "Media":
            return f"Media {on.replace('_', ' ')}" + (" (held)" if _yes(cmd.get("Toggle_(CC/PB/Note)")) else "")
        if kind == "Tap" and mode == "Set":
            return f"Tempo {on} BPM"
        if kind == "Tap" and mode in ("", "Tap"):
            return "Tap tempo"
        return command_text(cmd)

    def commands(self, row: dict, split: str = "") -> list:
        """The words of a row's commands A-J; a Cycle or Leave in the list
        starts a new part, as "then LABEL:" or "on leaving:"."""
        out = []
        for slot in SLOTS:
            cmd = {f: (row or {}).get(f"{slot}_{f}", "") for f in CMD_FIELDS}
            kind = cmd["CommandType"]
            if not kind or kind == NO_COMMAND:
                continue
            if kind == "Cycle":
                out.append(f"then {cmd['OnValue_(CC/PB)'] or (row or {}).get('Label', '')}:")
            elif kind == "Leave":
                out.append("on leaving:")
            else:
                out.append(self.words(cmd))
        text = "; ".join(out).replace(":; ", ": ")
        return [text] if text else []

    def tempo(self, bank: str) -> str:
        """The tempo a bank sets on entering, from its Tap Set."""
        row = self.enter.get(bank, {})
        for slot in SLOTS:
            if row.get(f"{slot}_CommandType") == "Leave":
                break
            if row.get(f"{slot}_CommandType") == "Tap" and row.get(f"{slot}_KeyMode_(Key)") == "Set":
                return row.get(f"{slot}_OnValue_(CC/PB)", "")
        return ""

    # --- the page ------------------------------------------------------------------
    def switch(self, bank: str, button: str) -> str:
        short = self.rows["Button_Settings"].get((bank, button), {})
        label = short.get("Label", "")
        long_label = self.rows["LongPress_Settings"].get((bank, button), {}).get("Long_Label", "")
        lines = []
        for name, press in PRESSES:
            for text in self.commands(self.rows[name].get((bank, button))):
                lines.append(f"<p><i>{press}:</i> {escape(text)}</p>")
        flags = [t for col, t in (("Global", "global"), ("Momentary_Hold", "momentary when held"))
                 if _yes(short.get(col))]
        if short.get("Group", "") not in ("", "None", "0"):
            flags.append(f"group {short['Group']}")
        if flags:
            lines.append(f"<p><i>{escape(', '.join(flags))}</i></p>")
        title = escape(label) + (f" / {escape(long_label)}" if long_label else "")
        empty = "" if label or lines else " empty"
        return (f'<div class="sw{empty}"><span class="id">{button}</span><b>{title or "&nbsp;"}</b>'
                + "".join(lines) + "</div>")

    def used(self, bank: str) -> bool:
        if self.commands(self.enter.get(bank)):
            return True
        return any(self.rows["Button_Settings"].get((bank, b), {}).get("Label") or
                   any(self.commands(self.rows[name].get((bank, b))) for name, _ in PRESSES)
                   for b in BUTTON_IDS)

    def bank(self, bank: str) -> str:
        name, info = self.names.get(bank, ("", ""))
        out = [f'<section class="bank"><h3>Bank {bank} {escape(name)} <small>{escape(info)}</small></h3>',
               '<div class="grid">']
        out += [self.switch(bank, b) for row in ROWS for b in row]
        out.append("</div>")
        for text in self.commands(self.enter.get(bank)):
            out.append(f'<p class="note"><i>On entering:</i> {escape(text)}</p>')
        pedals = self.bank_pedals(bank)
        if pedals:
            out.append(f'<p class="note"><i>Pedals here:</i> {escape(pedals)}</p>')
        out.append("</section>")
        return "\n".join(out)

    def bank_pedals(self, bank: str) -> str:
        row = next((r for r in self.s.get("BankExpression_Settings", []) if r["Bank_Number"] == bank), {})
        parts = []
        for p in ("1", "2"):
            cc = row.get(f"Exp{p}_CC", "")
            if not cc:
                continue
            text = f"pedal {p} " + (f"CC {cc}" if cc.isdigit() else cc.lower())
            if row.get(f"Exp{p}_Channel"):
                text += f" ch {row[f'Exp{p}_Channel']}"
            low, high = row.get(f"Exp{p}_Min", ""), row.get(f"Exp{p}_Max", "")
            if low or high:
                text += f", {low or 'min'} to {high or 'max'}"
            parts.append(text)
        return "; ".join(parts)

    def setlist(self) -> str:
        lists = {n: v for n, v in setlists(self.s.get("Setlist", [])).items() if v[1]}
        out = []
        for n, (title, banks) in lists.items():
            rows = []
            for i, bank in enumerate(map(str, banks), 1):
                name, info = self.names.get(bank, ("", ""))
                tempo = self.tempo(bank)
                rows.append(f"<tr><td>{i}</td><td>{escape(name)}</td><td>{escape(info)}</td><td>{bank}</td>"
                            f"<td>{tempo and tempo + ' BPM'}</td></tr>")
            head = "Setlist" if list(lists) == [1] else f"Setlist {n}"
            out.append(f"<h2>{head}{escape(': ' + title) if title else ''}</h2><table><tr><th>#</th><th>Song</th>"
                       "<th>Info</th><th>Bank</th><th>Tempo</th></tr>" + "".join(rows) + "</table>")
        return "".join(out)

    def pedals(self) -> str:
        rows = []
        for r in self.s.get("Expression_Settings", []):
            p = r["Pedal"]
            output = r.get("Output", "CC") or "CC"
            channel = r.get("Channel", "")
            channel = self.settings.get("MIDI_Channel", "") if channel in ("", "Global") else channel
            if output in ("CC", "CC14"):
                cc = self.settings.get(f"Exp{p}_CC", "")
                what = f"{output} {cc}, ch {channel}"
                named = devices.describe(self.devices, channel, "CC", cc)
                if named:
                    what = f"{named} ({what})"
            else:
                what = output
            if output == "Zones":
                zones = (r.get("Zones", "") or "").replace(",", " ").replace("/", " ").split()
                what = f"{len(zones)} zones, heel first"
                taps = [f"zone {k} presses {sw}" for k, sw in enumerate(zones, 1) if sw.upper() != "NONE"]
                rows.append(f"<tr><td>Pedal {p}</td><td>{escape(what)}</td><td>{escape(', '.join(taps))}</td></tr>")
                continue
            what += f", {r.get('Out_Min', '0') or '0'} to {r.get('Out_Max', '127') or '127'}"
            taps = [f"{where} taps press {r[col]}" for col, where in (("Toe_Button", "toe"), ("Heel_Button", "heel"))
                    if r.get(col, "") not in ("", "None")]
            if r.get("Auto_Button", "") not in ("", "None"):
                taps.append(f"moving it presses {r['Auto_Button']}")
            rows.append(f"<tr><td>Pedal {p}</td><td>{escape(what)}</td><td>{escape(', '.join(taps))}</td></tr>")
        return "<h2>Expression pedals</h2><table>" + "".join(rows) + "</table>" if rows else ""

    def others(self) -> str:
        rows = []
        mode = self.settings.get("Bank_Switch_Mode", "Bank")
        for r in self.s.get("BankSwitch_Settings", []):
            text = " ".join(self.commands(r))
            if text and mode != "Bank":
                label = f" {r['Label']}" if r.get("Label") else ""
                rows.append((f"Bank {r['Switch'].lower()}, {r['Press'].lower()} press{label}", text))
        for r in self.s.get("Combo_Settings", []):
            where = "every bank" if r.get("Bank", "") in ("", "All") else f"bank {r['Bank']}"
            run = (r.get("Run_Bank", ""), r.get("Run_Button", ""))
            label = self.rows["Button_Settings"].get(run, {}).get("Label", "")
            press = r.get("Run_List", "") or "Short"
            rows.append((f"{r['Switches']} together, in {where}",
                         f"bank {run[0]} button {run[1]}" + (f" {label}" if label else "")
                         + ("" if press == "Short" else f", its {press.lower()} press")))
        if not rows:
            return ""
        return ("<h2>Bank switches and combinations</h2><table>"
                + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in rows) + "</table>")

    def page(self) -> str:
        name = self.settings.get("ConfigName", "") or "Configuration"
        facts = [f"MIDI channel {self.settings.get('MIDI_Channel', '1')}"]
        if self.settings.get("Global_Channel", "").isdigit():
            facts.append(f"everything on channel {self.settings['Global_Channel']}")
        facts.append(f"long press {self.settings.get('Long_Press_ms', '500')} ms")
        if self.devices:
            facts.append(", ".join(f"{d} on channel {ch}" for ch, d in sorted(self.devices.items())))
        banks = [str(b) for b in range(len(self.names))]
        body = [f'<button class="print" onclick="print()">Print</button><h1>{escape(name)}</h1>',
                f'<p class="sub">{escape("; ".join(facts))}</p>',
                self.setlist(), self.pedals(), self.others(), "<h2>Banks</h2>"]
        body += [self.bank(b) for b in banks if self.used(b)]
        return ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                f"<title>{escape(name)} cheat sheet</title><style>{STYLE}</style></head>\n<body>\n"
                + "\n".join(b for b in body if b) + "\n</body></html>\n")


def cheat_sheet(sections: dict, chosen=None) -> str:
    """The page for a configuration's sections, as read_config_csv gives them;
    chosen: {channel: device} picked in a configurator, as guess takes it.
    Raises ValueError for one the pedal would not take."""
    return _Sheet(sections, chosen).page()
