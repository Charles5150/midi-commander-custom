"""What changes between two configurations, in plain words.

Both are packed and read back first, as the pedal would hold them, so only
what reaches the pedal counts: not the order of a CSV's columns, a comment, or
a field the command does not use. Each change is one line, as

    Bank 4 PRE2, button B, long press: A CC: CC# 20 -> 21
    Global: Follow the host's clock: off -> on

Used by Diff_Config.py and by both configurators before they write a slot.
"""

import math

from lib.binaryUnpacker import unpack_sections
from lib.configPacker import pack_config, pack_flash_image
from lib.configSchema import (
    BUTTON_FIELDS, CMD_FIELDS, COMMAND_SPECS, EXPRESSION_FIELDS, GLOBAL_FIELDS, GLOBAL_GROUPS, NO_COMMAND,
    SECTION_COLUMNS, SLOTS,
)

GLOBAL_NAMES = {label: name for _, items in GLOBAL_GROUPS for label, name, _ in items}
CHECK_COLUMNS = ({label for label, spec in GLOBAL_FIELDS.items() if spec["kind"] == "check"}
                 | {f["col"] for f in BUTTON_FIELDS + EXPRESSION_FIELDS if f["kind"] == "check"}
                 | {f["col"] for cols in SECTION_COLUMNS.values() for f in cols if f["kind"] == "check"})
LISTS = {"Button_Settings": "", "LongPress_Settings": "long press", "DoublePress_Settings": "double press"}


def _text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _rows(df) -> list:
    """A section as a list of {column: text}."""
    if df is None:
        return []
    return [{c: _text(v) for c, v in zip(df.columns, row)} for row in df.itertuples(index=False)]


def image_sections(data: bytes, image: bytes) -> dict:
    """{section: [{column: text}]} for a slot read with slotIO.read_image."""
    return {name: _rows(df) for name, df in unpack_sections(data, image).items()}


def config_sections(sections: dict) -> dict:
    """The same for a configuration's sections, as read_config_csv gives them.
    Raises ValueError for one the pedal would not take."""
    return image_sections(pack_config(sections), pack_flash_image(sections))


def _value(text: str, check: bool) -> str:
    if check:
        return "on" if text.upper().startswith("Y") else "off"
    return text if text else "(empty)"


def _change(name: str, old: str, new: str, check=False) -> str:
    return f"{name}: {_value(old, check)} -> {_value(new, check)}"


def _fields(kind: str, cmd: dict) -> list:
    """(label, text, is a check box) of the fields a command of this type shows."""
    out = []
    for f in COMMAND_SPECS.get(kind, {}).get("fields", []):
        when = f.get("when")
        if when and not all(cmd.get(c, "") in values or (cmd.get(c, "") == "" and f.get("blank") in values)
                            for c, values in when.items()):
            continue
        out.append((f["label"], cmd.get(f["col"], ""), f["kind"] == "check"))
    return out


def command_text(cmd: dict) -> str:
    """One command in a few words: "CC Ch 1, CC# 20, On 127, Off 0, Toggle"."""
    kind = cmd.get("CommandType", "")
    if not kind or kind == NO_COMMAND:
        return NO_COMMAND
    parts = [label if check else f"{label} {text}"
             for label, text, check in _fields(kind, cmd)
             if text and (not check or text.upper().startswith("Y"))]
    return kind + (" " + ", ".join(parts) if parts else "")


def _command(row: dict, slot: str) -> dict:
    return {f: row.get(f"{slot}_{f}", "") for f in CMD_FIELDS}


def _command_changes(old: dict, new: dict) -> list:
    """What changed in a list of commands A to J."""
    out = []
    for slot in SLOTS:
        a, b = _command(old, slot), _command(new, slot)
        ta, tb = command_text(a), command_text(b)
        if ta == tb:
            continue
        if a["CommandType"] == b["CommandType"]:
            fa = {label: (text, check) for label, text, check in _fields(a["CommandType"], a)}
            fb = {label: (text, check) for label, text, check in _fields(b["CommandType"], b)}
            fields = [_change(label, fa.get(label, ("", False))[0], fb.get(label, ("", False))[0],
                              (fa.get(label) or fb.get(label))[1])
                      for label in dict.fromkeys(list(fa) + list(fb))
                      if fa.get(label, ("", False))[0] != fb.get(label, ("", False))[0]]
            out.append(f"{slot} {b['CommandType']}: " + ", ".join(fields))
        elif tb == NO_COMMAND:
            out.append(f"{slot}: {ta} removed")
        elif ta == NO_COMMAND:
            out.append(f"{slot}: {tb} added")
        else:
            out.append(f"{slot}: {ta} -> {tb}")
    return out


def _other_changes(old: dict, new: dict, skip, labels: dict) -> list:
    """Changed columns that are not commands, named as the editors name them."""
    commands = {f"{s}_" for s in SLOTS}
    return [_change(labels.get(c, c), old.get(c, ""), new.get(c, ""), c in CHECK_COLUMNS)
            for c in dict.fromkeys(list(old) + list(new))
            if c not in skip and c[:2] not in commands and old.get(c, "") != new.get(c, "")]


def _keyed(rows: list, key) -> dict:
    return {tuple(r.get(k, "") for k in key): r for r in rows}


def diff(old: dict, new: dict) -> list:
    """Lines saying what changes from `old` to `new`, both as config_sections
    or image_sections give them; [] when the pedal would hold the same."""
    lines = []
    banks = {r["Bank_Number"]: r.get("Bank_Name_Large", "") for r in old.get("Bank_Naming", [])}
    banks.update({r["Bank_Number"]: r.get("Bank_Name_Large", "") for r in new.get("Bank_Naming", [])})

    def bank(number: str) -> str:
        name = banks.get(number, "")
        return f"Bank {number} {name}".rstrip()

    def pairs(section, key):
        a, b = _keyed(old.get(section, []), key), _keyed(new.get(section, []), key)
        for k in dict.fromkeys(list(a) + list(b)):
            if a.get(k, {}) != b.get(k, {}):
                yield k, a.get(k, {}), b.get(k, {})

    for (label,), a, b in pairs("Global_Settings", ["Label"]):
        lines.append("Global: " + _change(GLOBAL_NAMES.get(label, label), a.get("Value", ""), b.get("Value", ""),
                                          label in CHECK_COLUMNS))

    for (number,), a, b in pairs("Bank_Naming", ["Bank_Number"]):
        for col, name in (("Bank_Name_Large", "name"), ("Bank_Info_Small", "info")):
            if a.get(col, "") != b.get(col, ""):
                lines.append(f"Bank {number}: " + _change(name, a.get(col, ""), b.get(col, "")))

    button_labels = {f["col"]: f["label"] for f in BUTTON_FIELDS}
    button_labels["Long_Label"] = "Long press label"
    for section, press in LISTS.items():
        for (number, button), a, b in pairs(section, ["Bank_Number", "Button_Identifier"]):
            where = f"{bank(number)}, button {button}" + (f", {press}" if press else "")
            for change in (_other_changes(a, b, {"Bank_Number", "Button_Identifier"}, button_labels)
                           + _command_changes(a, b)):
                lines.append(f"{where}: {change}")

    for (number,), a, b in pairs("BankEnter_Settings", ["Bank_Number"]):
        for change in _command_changes(a, b):
            lines.append(f"{bank(number)}, on entering: {change}")

    for (switch, press), a, b in pairs("BankSwitch_Settings", ["Switch", "Press"]):
        where = f"Bank {switch} switch, {press.lower()} press"
        for change in _other_changes(a, b, {"Switch", "Press"}, {}) + _command_changes(a, b):
            lines.append(f"{where}: {change}")

    expression_labels = {f["col"]: f["label"] for f in EXPRESSION_FIELDS}
    for (pedal,), a, b in pairs("Expression_Settings", ["Pedal"]):
        for change in _other_changes(a, b, {"Pedal"}, expression_labels):
            lines.append(f"Expression pedal {pedal}: {change}")

    bank_exp_labels = {f["col"]: f["label"] for f in SECTION_COLUMNS["BankExpression_Settings"]}
    for (number,), a, b in pairs("BankExpression_Settings", ["Bank_Number"]):
        for change in _other_changes(a, b, {"Bank_Number"}, bank_exp_labels):
            lines.append(f"{bank(number)}, expression: {change}")

    for (index,), a, b in pairs("SysEx_Strings", ["Index"]):
        lines.append(f"SysEx string {index}: " + _change("bytes", a.get("Bytes", ""), b.get("Bytes", "")))

    for (program,), a, b in pairs("Preset_Names", ["Program"]):
        lines.append(f"Preset name {program}: " + _change("name", a.get("Name", ""), b.get("Name", "")))

    def order(section):
        return [r.get("Bank_Number", "") for r in section if r.get("Bank_Number", "")]
    setlist_a, setlist_b = order(old.get("Setlist", [])), order(new.get("Setlist", []))
    if setlist_a != setlist_b:
        lines.append("Setlist: " + _change("banks", " ".join(setlist_a), " ".join(setlist_b)))

    for section, name in (("Combo_Settings", "Combination"), ("MidiMap_Settings", "MIDI map row")):
        a, b = old.get(section, []), new.get(section, [])
        for i in range(max(len(a), len(b))):
            ra, rb = (a[i] if i < len(a) else {}), (b[i] if i < len(b) else {})
            if not ra or not rb:
                text = ", ".join(f"{c} {v}" for c, v in (ra or rb).items() if v)
                lines.append(f"{name} {i + 1}: {text} {'added' if rb else 'removed'}")
            elif ra != rb:
                lines.append(f"{name} {i + 1}: " + ", ".join(_other_changes(ra, rb, (), {})))
    return lines
