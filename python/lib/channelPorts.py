"""The output each MIDI channel goes to by default, USB or DIN.

A rig says it once: channel 3 is the amp on the DIN cable, channel 10 the
computer. The pedal knows nothing of it. On the way to the pedal the tools put
a Chan command naming only that output above every command on such a channel,
the same Chan a hand would write, so any firmware since 0.84 follows it.

A command that already has a Chan above it keeps it, so one command can still
go its own way. A command driven by a Ramp, LFO, Seq, Tap, Exp, NRPN or a
SysEx taking its value has that command where the Chan would go, and goes out
on both, as it would if the Chan were written by hand.
"""

import collections

import pandas as pd

from lib.cmdBinaryPacker import MIDI_NUM_COMMANDS_PER_SWITCH, cell_text, command_type, safe_int

SECTION = "Channel_Ports"
COLUMNS = ["Channel", "Port"]
PORTS = ["Both", "USB", "DIN"]
# The command lists, by section, and how each row is named in an error
LIST_SECTIONS = {
    "Button_Settings": ("Bank_Number", "Button_Identifier"),
    "LongPress_Settings": ("Bank_Number", "Button_Identifier"),
    "DoublePress_Settings": ("Bank_Number", "Button_Identifier"),
    "BankEnter_Settings": ("Bank_Number",),
    "BankSwitch_Settings": ("Switch", "Press"),
}
# The commands that go out on a channel
ON_A_CHANNEL = {"PC", "CC", "Note", "PB", "Pressure", "CCInc", "PCInc"}
# The commands that work on the one right below them, in the place a Chan takes
DRIVERS = {"Chan", "Ramp", "LFO", "Seq", "Tap", "Exp", "NRPN"}
CHANNEL_COLUMN = "Channel_(PC/CC/Note/PB)"
FIELDS = ["CommandType", CHANNEL_COLUMN, "Number_(PC/CC/Note)", "OnValue_(CC/PB)", "OffValue_(CC)",
          "BankSelect_(PC)", "BankSelectHighByte_(PC)", "Toggle_(CC/PB/Note)", "Velocity_(Note)",
          "Duration_(Note/PB)", "KeyMode_(Key)"]


def port_name(text) -> str:
    """The port a cell names, as PORTS spells it; "Both" for an empty one."""
    value = cell_text(text)
    if value.lower() in ("", "nan"):
        return "Both"
    names = {p.lower(): p for p in PORTS}
    if value.lower() not in names:
        raise ValueError(f"{SECTION}: the port must be Both, USB or DIN, not {value!r}")
    return names[value.lower()]


def channel_ports(df) -> dict:
    """{channel 1-16: "USB" or "DIN"} from a Channel_Ports section; channels
    going to both are left out."""
    ports = {}
    if df is None:
        return ports
    for _, row in df.iterrows():
        text = cell_text(row.get("Channel"))
        if text.lower() in ("", "nan"):
            continue
        channel = safe_int(text, 0)
        if not 1 <= channel <= 16:
            raise ValueError(f"{SECTION}: the channel must be 1-16, not {text!r}")
        if channel in ports:
            raise ValueError(f"{SECTION}: channel {channel} is there twice")
        port = port_name(row.get("Port"))
        if port != "Both":
            ports[channel] = port
    return ports


def global_channel(df) -> int:
    """The Global_Channel the configuration sets, 0 when it is off."""
    if df is None or "Label" not in df.columns:
        return 0
    rows = df[df["Label"].astype(str).str.strip() == "Global_Channel"]
    if rows.empty:
        return 0
    value = safe_int(cell_text(rows.iloc[0].get("Value")), 0)
    return value if 1 <= value <= 16 else 0


def _commands(fields: dict) -> list:
    """A row's command list, one dict of fields per command, A first."""
    out = []
    for i in range(MIDI_NUM_COMMANDS_PER_SWITCH):
        prefix = f"{chr(ord('A') + i)}_"
        out.append(collections.defaultdict(str, {c[len(prefix):]: v for c, v in fields.items()
                                                 if isinstance(c, str) and c.startswith(prefix)}))
    return out


def _port_for(cmd, ports: dict, forced: int):
    """The port the command goes to by default, or None."""
    if command_type(cmd.get("CommandType")) not in ON_A_CHANNEL:
        return None
    channel = forced or safe_int(cell_text(cmd.get(CHANNEL_COLUMN)), 1) or 1
    return ports.get(channel)


def _needs_chan(commands: list, i: int, ports: dict, forced: int):
    """The port command i needs a Chan for, or None when it needs none."""
    port = _port_for(commands[i], ports, forced)
    if port is None or i == 0:
        return port
    above = commands[i - 1]
    kind = command_type(above.get("CommandType"))
    if kind in DRIVERS:
        return None
    if kind == "SysEx" and cell_text(above.get("KeyMode_(Key)")).lower() == "value":
        return None
    return port


def with_ports(commands: list, ports: dict, forced: int = 0) -> list:
    """The command list with a Chan above every command that needs one. Raises
    ValueError when the list then has more commands than a list holds."""
    out = []
    added = 0
    for i, cmd in enumerate(commands):
        port = _needs_chan(commands, i, ports, forced)
        if port is not None:
            added += 1
            out.append(collections.defaultdict(str, {"CommandType": "Chan", "KeyMode_(Key)": port,
                                                     "Toggle_(CC/PB/Note)": "N"}))
        out.append(cmd)
    # Empty commands at the end are no commands
    while len(out) > MIDI_NUM_COMMANDS_PER_SWITCH and command_type(out[-1].get("CommandType")) == "":
        out.pop()
    if len(out) > MIDI_NUM_COMMANDS_PER_SWITCH:
        raise ValueError(f"the default ports of {SECTION} put a Chan above {added} "
                         f"of its commands, and {len(out)} commands are more than the "
                         f"{MIDI_NUM_COMMANDS_PER_SWITCH} a list holds: give one of them a Chan "
                         "of its own, or make room")
    return out


def apply(sections: dict) -> dict:
    """The sections with the Chan commands the default ports call for. The
    sections themselves are left as they are; without a default port they come
    back unchanged."""
    ports = channel_ports(sections.get(SECTION))
    if not ports:
        return sections
    forced = global_channel(sections.get("Global_Settings"))
    out = dict(sections)
    for name, keys in LIST_SECTIONS.items():
        df = sections.get(name)
        if df is None:
            continue
        rows = []
        changed = False
        for _, row in df.iterrows():
            fields = row.to_dict()
            commands = _commands(fields)
            try:
                placed = with_ports(commands, ports, forced)
            except ValueError as e:
                where = " ".join(str(fields.get(k, "")) for k in keys)
                raise ValueError(f"{name} {where}: {e}") from None
            if len(placed) != len(commands) or any(a is not b for a, b in zip(placed, commands)):
                changed = True
                fields = {c: v for c, v in fields.items()
                          if not (isinstance(c, str) and len(c) > 2 and c[1] == "_" and "A" <= c[0] <= "J")}
                for i, cmd in enumerate(placed):
                    for f, v in cmd.items():
                        fields[f"{chr(ord('A') + i)}_{f}"] = v
            rows.append(fields)
        if changed:
            out[name] = pd.DataFrame(rows).reindex(columns=_columns(df, rows))
    return out


def _columns(df, rows) -> list:
    """The section's columns, with any a Chan added after them."""
    columns = list(df.columns)
    for row in rows:
        for c in row:
            if c not in columns:
                columns.append(c)
    return columns
