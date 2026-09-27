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
from lib.configCsv import read_config_csv, write_config_csv
from lib.configPacker import pack_config, pack_flash_image
from lib.configSchema import schema
from lib.displayText import display_text

FLASH_PAGE_SIZE = 2048
SLOT_PAGES = 12

# The sections in the order a CSV has them, and write_config_csv's name for each
SECTION_ARGS = [
    ("Global_Settings", "df_global"),
    ("Bank_Naming", "df_banks"),
    ("Button_Settings", "df_buttons"),
    ("LongPress_Settings", "df_long_press"),
    ("DoublePress_Settings", "df_double_press"),
    ("Expression_Settings", "df_expression"),
    ("BankEnter_Settings", "df_bank_enter"),
    ("SysEx_Strings", "df_sysex"),
    ("BankSwitch_Settings", "df_bank_switch"),
    ("Setlist", "df_setlist"),
    ("BankExpression_Settings", "df_bank_expression"),
    ("Combo_Settings", "df_combos"),
]


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


def csv_to_sections(data: bytes) -> str:
    """A configuration CSV's bytes, as sections JSON."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        f.write(_bytes(data))
        path = f.name
    try:
        return _to_json(read_config_csv(path))
    finally:
        os.unlink(path)


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
    same followed by the double press area when it has one (see slotIO.read_image)."""
    data, image = _bytes(data), _bytes(image)
    (df_global, df_banks, df_buttons, df_long, df_exp,
     df_enter, df_sysex, df_bank_switch, df_setlist) = unpacker.unpack_config(data)
    sections = {
        "Global_Settings": df_global,
        "Bank_Naming": df_banks,
        "Button_Settings": df_buttons,
        "LongPress_Settings": df_long,
        "DoublePress_Settings": unpacker.unpack_double_press_settings(image),
        "Expression_Settings": df_exp,
        "BankEnter_Settings": df_enter,
        "SysEx_Strings": df_sysex,
        "BankSwitch_Settings": df_bank_switch,
        "Setlist": df_setlist,
        "BankExpression_Settings": unpacker.unpack_bank_expression_settings(data),
        "Combo_Settings": unpacker.unpack_combos(data),
    }
    # Through a CSV and back, so the cells are the text a CSV file holds
    csv = sections_to_csv(_to_json({k: v for k, v in sections.items() if v is not None}))
    return csv_to_sections(csv.encode("utf-8"))


# Sizes the page needs to read a slot, from the same place slotIO takes them
CONFIG_SIZE = unpacker.CONFIG_SIZE
DOUBLE_PRESS_OFFSET = unpacker.DOUBLE_PRESS_OFFSET
DOUBLE_PRESS_SIZE = unpacker.DOUBLE_PRESS_SIZE
