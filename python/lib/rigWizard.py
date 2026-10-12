"""The rig wizard: what is on your board, each device on its channel, made
into a starting configuration from the device templates.

The first device is the main one, and the configuration is its template: its
presets in the banks, its looper and footswitches. Each of the others brings
the bank of its template that controls it, its footswitches or its looper,
loaded into a bank of the configuration as a song would be (lib/songFile.py):
into a free bank, or else in place of the main device's last preset. And it
can change preset with the main one: entering a bank that loads the main
device's program n loads its program n as well.

The templates all send on channel 1; here each device's commands go on its own
channel. Everything goes out of both the USB and the DIN output, so the
channel is what tells the devices apart.
"""

import copy
import os
import tempfile

import lib.deviceDictionary as dd
import lib.songFile as sf
from lib.configCsv import read_config_csv
from lib.flashLayout import NUM_BANKS, SETLIST_MAX

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(os.path.dirname(HERE), "templates")

MAX_DEVICES = 4
TEMPLATE_CHANNEL = "1"          # what every template sends on
CHANNEL = "Channel_(PC/CC/Note/PB)"
ENTER = "BankEnter_Settings"
# The bank of a template that controls the device; 31 for the others
CONTROL_BANKS = {"Ableton_Live": 1, "Kemper_Player": 10}
# The templates of programs on the computer, which take MIDI over USB
HOSTS = {"Ableton_Live": "Ableton Live", "Cantabile": "Cantabile", "Gig_Performer": "Gig Performer",
         "MainStage": "MainStage"}


def templates(folder=TEMPLATES_DIR) -> list:
    """The template names, as the files are named, without .csv."""
    return sorted(f[:-4] for f in os.listdir(folder) if f.endswith(".csv"))


def load_template(name, folder=TEMPLATES_DIR) -> dict:
    return read_config_csv(os.path.join(folder, f"{name}.csv"))


def device(template):
    """The device dictionary's entry for a template, or None."""
    return next((d for d in dd.DEVICES if d.get("template") == template), None)


def title(template) -> str:
    d = device(template)
    return d["name"] if d else HOSTS.get(template, template.replace("_", " "))


def _channel(text) -> str:
    try:
        n = int(str(text).strip())
    except ValueError:
        n = 0
    if not 1 <= n <= 16:
        raise ValueError(f"channel {text}: channels are 1-16")
    return str(n)


def _rechannel(sections: dict, channel: str) -> dict:
    """A template's sections with what it sends on channel 1 sent on `channel`."""
    out = {}
    for name, df in sections.items():
        if df is not None and any(c.endswith(CHANNEL) for c in df.columns):
            df = df.copy().astype(object)
            for c in [c for c in df.columns if c.endswith(CHANNEL)]:
                df[c] = [channel if sf._cell(v) == TEMPLATE_CHANNEL else v for v in df[c]]
        out[name] = df
    return out


def _set_global(sections, label, value):
    df = sections["Global_Settings"].copy().astype(object)
    hit = df["Label"].astype(str).str.strip() == label
    if hit.any():
        df.loc[hit, "Value"] = value
    else:
        df.loc[len(df)] = {"Label": label, "Value": value}
    sections["Global_Settings"] = df


def _read_text(text) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return read_config_csv(path)
    finally:
        os.unlink(path)


def _enter_programs(sections) -> dict:
    """{bank: program}: the banks that load a program of the main device on
    entering, and that program."""
    df = sections.get(ENTER)
    out = {}
    if df is None:
        return out
    prefixes = sf._prefixes(df)
    for row in df.to_dict("records"):
        for _, kind, number, _, _ in sf._commands(row, prefixes):
            if kind == "PC" and number:
                out[sf._bank(row.get(sf.BANK))] = number
                break
    return out


def _control_song(sections, template) -> dict:
    """The bank of a template that controls the device, as a song: without the
    program a preset bank loads on entering, then named after the device, and
    with the device's name on its info line."""
    bank = CONTROL_BANKS.get(template, NUM_BANKS - 1)
    song = _read_text(sf.save_song(sections, bank))
    naming = song[sf.NAMING].copy().astype(object)
    if _enter_programs(song):
        song.pop(ENTER, None)
        naming["Bank_Name_Large"] = title(template).replace(" ", "")[:4].upper()
    naming["Bank_Info_Small"] = title(template)[:8]
    song[sf.NAMING] = naming
    return song


def _in_setlist(sections, bank):
    """Put `bank` at the end of a setlist the configuration follows, so Bank
    Up / Down reach it; whether it went in."""
    df = sections.get("Setlist")
    on = sections["Global_Settings"]
    on = on[on["Label"].astype(str).str.strip() == "Setlist_Mode"]["Value"].astype(str).str.upper()
    if df is None or not len(df) or not (on == "Y").any():
        return False
    rows = [r for r in df.to_dict("records") if sf._cell(r.get(sf.BANK))]
    if len(rows) >= SETLIST_MAX:
        return False
    df = df.copy().astype(object)
    df.loc[len(df)] = {"Position": str(len(rows) + 1), sf.BANK: bank}
    sections["Setlist"] = df
    return True


def _place(sections, taken) -> tuple:
    """(bank, what was there): a free bank for a device's controls, the lowest,
    or else the main device's last preset bank nothing else names."""
    free = [b for b in reversed(sf._unused_banks(sections, taken))]
    if free:
        return free[0], ""
    named = sf._named_banks(sections)
    for b in sorted(_enter_programs(sections), key=int, reverse=True):
        if b not in taken and int(b) not in named:
            row = sf._rows(sections.get(sf.NAMING), b)
            name = sf._cell(row[0].get("Bank_Name_Large")) if row else ""
            return b, name or f"bank {b}"
    raise ValueError("no bank is left for another device: take a device out")


def _follow(sections, banks: dict, channel: str) -> int:
    """Add a Program Change on `channel` to each bank of `banks`, {bank:
    program}, among what it sends on entering; how many banks took it."""
    df = sections[ENTER].copy().astype(object)
    prefixes = sf._prefixes(df)
    done = 0
    for idx in df.index:
        program = banks.get(sf._bank(df.at[idx, sf.BANK]))
        if program is None:
            continue
        free = next((p for p in prefixes if not sf._cell(df.at[idx, f"{p}_CommandType"])), None)
        if free is None:
            continue
        df.at[idx, f"{free}_CommandType"] = "PC"
        df.at[idx, f"{free}_{CHANNEL}"] = channel
        df.at[idx, f"{free}_{sf.NUM}"] = program
        done += 1
    sections[ENTER] = df
    return done


def setup_note(template, channel) -> str:
    """What to set on the device itself."""
    name = title(template)
    if template in HOSTS:
        return f"{name}, on the computer: it takes the pedal's MIDI over USB, on channel {channel}"
    d = device(template)
    setup = d.get("setup", "") if d else ""
    return f"{name} on channel {channel}" + (f": {setup}" if setup else "")


def build_rig(parts) -> tuple:
    """(sections, notes) for a rig. `parts` are dicts of the devices, the main
    one first: "template" (its name), "sections" (the template read),
    "channel" (1-16) and, for the others, "follow" (change preset with the
    main device). ValueError when the rig does not fit."""
    if not parts:
        raise ValueError("pick a device first")
    if len(parts) > MAX_DEVICES:
        raise ValueError(f"at most {MAX_DEVICES} devices")
    channels = [_channel(p["channel"]) for p in parts]
    for i, c in enumerate(channels):
        if c in channels[:i]:
            other = parts[channels.index(c)]["template"]
            raise ValueError(f"{title(parts[i]['template'])} and {title(other)} are both on channel {c}: "
                             f"give each device a channel of its own")

    main, ch = parts[0], channels[0]
    out = _rechannel(copy.deepcopy(main["sections"]), ch)
    _set_global(out, "MIDI_Channel", ch)
    if len(parts) > 1:
        _set_global(out, "ConfigName", f"{title(main['template'])} rig"[:16])
    programs = _enter_programs(out)
    notes = [setup_note(main["template"], ch)]
    taken = set()

    for part, c in zip(parts[1:], channels[1:]):
        name = title(part["template"])
        song = _control_song(_rechannel(part["sections"], c), part["template"])
        bank, was = _place(out, taken)
        taken.add(bank)
        out, said = sf.load_song(out, song, bank)
        programs.pop(bank, None)
        label = sf._cell(song[sf.NAMING]["Bank_Name_Large"].iat[0])
        notes.append(setup_note(part["template"], c))
        if not label or label == name.replace(" ", "")[:4].upper():
            label = "controls"
        notes.append(f"bank {bank} holds the {name}'s {label}"
                     + (f", in place of the {title(main['template'])}'s {was}" if was else "")
                     + (", at the end of the setlist" if _in_setlist(out, bank) else ""))
        notes.extend(f"{name}: {n}" for n in said if "goes to other banks" not in n)
        if part.get("follow"):
            if _follow(out, programs, c):
                notes.append(f"the {name} changes preset with the {title(main['template'])}: entering a bank that "
                             f"loads its program n loads the {name}'s program n")
            else:
                notes.append(f"the {name} does not change preset with the banks: the "
                             f"{title(main['template'])}'s banks load no program on entering")

    on_din = [p["template"] for p in parts if p["template"] not in HOSTS]
    if len(on_din) > 1:
        notes.append("the pedal has one DIN output: chain the devices, its MIDI OUT to the first one's MIDI IN, "
                     "and that one's MIDI THRU to the next one's MIDI IN")
        for p, c in zip(parts, channels):
            setup = (device(p["template"]) or {}).get("setup", "")
            if "every channel" in setup or "Omni" in setup:
                notes.append(f"the {title(p['template'])} listens on every channel out of the box: set it to "
                             f"channel {c}, or it takes the other devices' messages too")
    return out, notes
