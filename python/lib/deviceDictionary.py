"""The device dictionary: what a device's CCs and Program Changes do.

devices.json, next to this file, holds the MIDI maps behind the device
templates, so a configurator can offer "HX Stomp > FS4" instead of a type,
a number and values, and name a CC already written. The desktop and the web
configurators both read it through here.

A command is (channel, type, number, on, toggle) as text, the way the CSV
holds them; which device sits on a channel is guessed from the commands the
configuration already sends there, unless the user picked one.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DEVICES_JSON = os.path.join(HERE, "devices.json")

with open(DEVICES_JSON, encoding="utf-8") as f:
    DEVICES = json.load(f)["devices"]

BY_NAME = {d["name"]: d for d in DEVICES}

# How many of a channel's CC numbers a device must know before it is taken
# for the device there, and what share of them
GUESS_MIN = 3
GUESS_SHARE = 0.8


def _int(text):
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def _yes(text) -> bool:
    return str(text or "").strip().upper().startswith("Y")


def fields(entry: dict) -> dict:
    """The CSV fields a dictionary entry fills; the channel is left as it is."""
    out = {"CommandType": entry["type"]}
    if entry["type"] == "PC":
        return out
    out["Number_(PC/CC/Note)"] = str(entry["number"])
    if entry.get("exp"):
        on, off, toggle = 127, 0, True       # a button on a continuous control: toe, then heel
    else:
        on, off, toggle = entry["on"], entry.get("off"), entry.get("toggle", False)
    out["OnValue_(CC/PB)"] = str(on)
    out["OffValue_(CC)"] = "" if off is None else str(off)
    out["Toggle_(CC/PB/Note)"] = "Y" if toggle else "N"
    return out


def entry_name(device: str, cmd_type, number=None, on=None, toggle=None):
    """The dictionary's name for a command on `device`, or None."""
    d = BY_NAME.get(device)
    if d is None:
        return None
    cmd_type = str(cmd_type or "").strip()
    if cmd_type == "PC":
        return next((e["name"] for e in d["commands"] if e["type"] == "PC"), None)
    n = _int(number)
    same = [e for e in d["commands"] if e["type"] == cmd_type and e.get("number") == n]
    if len(same) <= 1:
        return same[0]["name"] if same else None
    # One number, several meanings: the value says which, then the toggle
    v = _int(on)
    by_value = [e for e in same if e.get("on") == v]
    if not by_value:
        return None
    if len(by_value) > 1 and toggle is not None:
        by_toggle = [e for e in by_value if e.get("toggle", False) == _yes(toggle)]
        by_value = by_toggle or by_value
    return by_value[0]["name"]


def guess(commands, chosen=None) -> dict:
    """{channel: device} for the channels whose commands one device explains.

    `commands` are (channel, type, number, on, toggle); `chosen`, {channel:
    device} the user picked, wins over the guess. A channel's CC numbers are
    matched against each device: the one that knows most of them, at least
    GUESS_MIN and GUESS_SHARE of them, is the device there; on a tie, the one
    with the shorter map, the more particular of the two.
    """
    numbers = {}
    for ch, cmd_type, number, _on, _toggle in commands:
        n = _int(number)
        if str(cmd_type).strip() == "CC" and n is not None:
            numbers.setdefault(_int(ch) or 1, set()).add(n)
    out = {}
    for ch, used in numbers.items():
        best = None
        for d in DEVICES:
            known = {e.get("number") for e in d["commands"] if e["type"] == "CC"}
            hits = len(used & known)
            if hits < GUESS_MIN or hits < GUESS_SHARE * len(used):
                continue
            key = (hits, -len(d["commands"]))
            if best is None or key > best[0]:
                best = (key, d["name"])
        if best:
            out[ch] = best[1]
    for ch, name in (chosen or {}).items():
        if name in BY_NAME:
            out[_int(ch) or 1] = name
    return out


def describe(devices: dict, channel, cmd_type, number=None, on=None, toggle=None) -> str:
    """"HX Stomp: FS4" for a command on a channel with a known device, or ""."""
    device = devices.get(_int(channel) or 1)
    name = entry_name(device, cmd_type, number, on, toggle) if device else None
    return f"{device}: {name}" if name else ""


def config_commands(sections: dict) -> list:
    """Every (channel, type, number, on, toggle) of a configuration's command
    lists, sections as read_config_csv gives them, on the channel it goes out
    on: Global_Channel, when set, carries them all."""
    out = []
    g = sections.get("Global_Settings")
    settings = {}
    if g is not None and "Label" in g.columns:
        settings = {str(k): ("" if v != v else str(v)) for k, v in zip(g["Label"], g["Value"])}
    global_channel = _int(settings.get("Global_Channel"))
    # The expression pedals' CCs, on the MIDI channel
    for key in ("Exp1_CC", "Exp2_CC"):
        if _int(settings.get(key)) is not None:
            out.append((global_channel or settings.get("MIDI_Channel", ""), "CC", settings[key], "", ""))
    for df in sections.values():
        for col in df.columns:
            if not col.endswith("_CommandType"):
                continue
            slot = col[: -len("_CommandType")]

            def column(name):
                c = f"{slot}_{name}"
                return ["" if v is None or v != v else str(v) for v in df[c]] if c in df.columns else [""] * len(df)

            rows = zip(column("CommandType"), column("Channel_(PC/CC/Note/PB)"), column("Number_(PC/CC/Note)"),
                       column("OnValue_(CC/PB)"), column("Toggle_(CC/PB/Note)"))
            out += [(global_channel or ch, t.strip(), n, on, tg) for t, ch, n, on, tg in rows
                    if t.strip() in ("CC", "PC", "Note")]
    return out
