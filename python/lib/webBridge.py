"""The web configurator's way into the tools' own code.

The page (web/) runs this module in the browser with Pyodide, so a CSV is
read, checked and packed there exactly as CSV_to_Flash.py does it. What
crosses to JavaScript is plain JSON text and bytes: sections as
{name: {"columns": [...], "rows": [[text, ...], ...]}}, with "" for an empty cell.
"""

import json
import os
import tempfile
from math import ceil

import pandas as pd

import lib.binaryUnpacker as unpacker
from lib.configCsv import SECTION_ARGS, read_config_csv, write_config_csv
from lib.configDiff import config_sections, diff, image_sections
from lib.configPacker import pack_config, pack_flash_image, sysex_problem
from lib.configSchema import schema
from lib.cheatSheet import cheat_sheet as _cheat_sheet
import lib.deviceDictionary as devices
import lib.rigWizard as rig
import lib.songFile as songs
from lib.displayText import display_text
# The sizes the page needs to read a slot come from here too
from lib.flashLayout import (  # noqa: F401
    CONFIG_SIZE, DOUBLE_PRESS_OFFSET, DOUBLE_PRESS_SIZE, EXT2_OFFSET, EXT2_SIZE, FLASH_PAGE_SIZE, SLOT_PAGES,
)


def _bytes(data) -> bytes:
    """Bytes from Python, or from a JavaScript Uint8Array in the page."""
    return data.to_bytes() if hasattr(data, "to_bytes") else bytes(data)


def _cell(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _to_json(sections: dict) -> str:
    return json.dumps({
        name: {"columns": list(df.columns), "rows": [[_cell(v) for v in row] for row in df.itertuples(index=False)]}
        for name, df in sections.items()
    })


def _from_json(text: str) -> dict:
    """Sections as read_config_csv gives them: strings, NaN for an empty cell."""
    out = {}
    for name, sec in json.loads(text).items():
        rows = [[v if v != "" else float("nan") for v in row] for row in sec["rows"]]
        out[name] = pd.DataFrame(rows, columns=sec["columns"], dtype=object)
    return out


def shown(text: str, width: int) -> str:
    """What the pedal's display makes of text, cut to width characters."""
    return display_text(text)[:width]


def schema_json() -> str:
    return json.dumps(schema())


def _devices_json(found) -> str:
    return json.dumps([
        {"name": d["name"], "maker": d["maker"], "model": d.get("model", d["name"]),
         "setup": d.get("setup", ""), "community": d.get("community", False),
         "commands": [{"name": e["name"], "fields": devices.fields(e)} for e in d["commands"]]}
        for d in found
    ])


def devices_json() -> str:
    """The device dictionary, each command with the CSV fields it fills."""
    return _devices_json(devices.DEVICES)


def community_json() -> str:
    """The community devices, as devices_json gives them; the page puts
    lib/openmidi.json in place first, when they are asked for."""
    return _devices_json(devices.community())


def device_guess(text: str, chosen: str = "{}") -> str:
    """{channel: device} for sections JSON; `chosen`, {channel: device} picked."""
    found = devices.guess(devices.config_commands(_from_json(text)), json.loads(chosen))
    return json.dumps({str(ch): name for ch, name in found.items()})


def device_name(device: str, cmd_type: str, number: str, on: str, toggle: str) -> str:
    """The dictionary's name for a command on `device`, or ""."""
    return devices.entry_name(device, cmd_type, number, on, toggle) or ""


def cheat_sheet(text: str, chosen: str = "{}") -> str:
    """The configuration as a page to print, lib/cheatSheet.py."""
    return _cheat_sheet(_from_json(text), json.loads(chosen))


def _read_csv(data) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(_bytes(data))
        path = f.name
    try:
        return read_config_csv(path)
    finally:
        os.unlink(path)


def csv_to_sections(data: bytes) -> str:
    """A configuration CSV's bytes, as sections JSON."""
    sections = _read_csv(data)
    missing = [n for n, _ in SECTION_ARGS[:3] if n not in sections]
    if missing:
        raise ValueError(f"this is not a Midi Commander configuration: it has no {', '.join(missing)} section{'s' if len(missing) > 1 else ''}")
    return _to_json(sections)


def sections_to_csv(text: str, note: str = "Written by the web configurator") -> str:
    sections = _from_json(text)
    missing = [n for n, _ in SECTION_ARGS[:3] if n not in sections]
    if missing:
        raise ValueError(f"the configuration has no {', '.join(missing)}")
    kwargs = {arg: sections.get(name) for name, arg in SECTION_ARGS}
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        path = f.name
    try:
        write_config_csv(path, note=note, **kwargs)
        with open(path, encoding="utf-8") as f:
            return f.read()
    finally:
        os.unlink(path)


def pack(text: str):
    """(configuration, flash image) for sections JSON, as CSV_to_Flash.py packs
    them. Raises ValueError saying where, for anything the pedal would not take."""
    sections = _from_json(text)
    missing = [n for n, _ in SECTION_ARGS[:3] if n not in sections]
    if missing:
        raise ValueError(f"the configuration has no {', '.join(missing)}")
    sysex = sections.get("SysEx_Strings")
    if sysex is not None and "Bytes" in sysex.columns:
        index = sysex["Index"] if "Index" in sysex.columns else range(len(sysex))
        for i, text in zip(index, sysex["Bytes"]):
            problem = sysex_problem(text)
            if problem:
                raise ValueError(f"SysEx string {i}: {problem}")
    config = pack_config(sections)
    image = pack_flash_image(sections)
    pages = ceil(len(config) / FLASH_PAGE_SIZE)
    if pages > SLOT_PAGES:
        raise ValueError(f"the configuration needs {pages} flash pages, more than the {SLOT_PAGES} a slot has")
    return config, image


def check(text: str) -> str:
    """"" when the sections pack, otherwise what is wrong."""
    try:
        pack(text)
    except (ValueError, KeyError) as e:
        return str(e) or type(e).__name__
    return ""


def image_to_sections(data: bytes, image: bytes) -> str:
    """Sections JSON for a slot read from the pedal: its configuration, and the
    same followed by the extension areas it has (see slotIO.read_image)."""
    data, image = _bytes(data), _bytes(image)
    sections = unpacker.unpack_sections(data, image)
    # Through a CSV and back, so the cells are the text a CSV file holds
    csv = sections_to_csv(_to_json({k: v for k, v in sections.items() if v is not None}))
    return csv_to_sections(csv.encode("utf-8"))



def changes(data: bytes, image: bytes, text: str) -> str:
    """What writing sections JSON over a slot read from the pedal changes, as
    a JSON list of lines; [] when the slot already holds it."""
    pack(text)   # says what is wrong, where, as a write would
    return json.dumps(diff(image_sections(_bytes(data), _bytes(image)), config_sections(_from_json(text))))


def save_song(text: str, bank: int) -> str:
    """{"name", "text"}: a bank of sections JSON as a song file (lib/songFile.py)."""
    sections = _from_json(text)
    return json.dumps({"name": songs.file_name(sections, bank), "text": songs.save_song(sections, bank)})


def load_song(text: str, data: bytes, bank: int) -> str:
    """{"sections", "notes"}: sections JSON with a song file's bytes loaded into bank."""
    sections, notes = songs.load_song(_from_json(text), _read_csv(data), bank)
    # Through a CSV and back, as the page keeps them
    csv = sections_to_csv(_to_json({k: v for k, v in sections.items() if v is not None}))
    return json.dumps({"sections": json.loads(csv_to_sections(csv.encode("utf-8"))), "notes": notes})


def rig_titles(names: str) -> str:
    """{template: the device's name} for a JSON list of template names."""
    return json.dumps({n: rig.title(n) for n in json.loads(names)})


def build_rig(parts: str) -> str:
    """{"sections", "notes"}: a configuration for the devices of a JSON list of
    {"template", "csv" (its text), "channel", "follow"} (lib/rigWizard.py)."""
    devices = [{**p, "sections": _read_csv(p["csv"].encode("utf-8"))} for p in json.loads(parts)]
    sections, notes = rig.build_rig(devices)
    # Through a CSV and back, as the page keeps them
    csv = sections_to_csv(_to_json({k: v for k, v in sections.items() if v is not None}))
    return json.dumps({"sections": json.loads(csv_to_sections(csv.encode("utf-8"))), "notes": notes})
