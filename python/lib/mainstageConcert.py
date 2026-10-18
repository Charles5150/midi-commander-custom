"""The patches of an Apple MainStage concert, for the pedal's preset names.

A concert is a folder, ``Name.concert``, holding ``Concert.patch``. Each
``.patch`` folder in it has a ``data.plist``: a set lists its patches under
``nodes``, in the order of the Patch List, and a patch has its name and its
Program Change number under ``patch > engineNode``. Only reading: the concert
is left as it is.
"""

import os
import plistlib
from collections import namedtuple

import pandas as pd

from lib.configPacker import PRESET_NAME_COLUMNS, PRESET_NAME_COUNT, PRESET_NAME_LEN
from lib.displayText import display_text

Patch = namedtuple("Patch", "name program bank set")


def _load(folder: str) -> dict:
    with open(os.path.join(folder, "data.plist"), "rb") as f:
        return plistlib.load(f)


def _engine(data: dict) -> dict:
    return (data.get("patch") or {}).get("engineNode") or {}


def _stem(folder: str) -> str:
    return os.path.splitext(os.path.basename(folder.rstrip(os.sep)))[0]


def concert_patches(concert: str) -> list:
    """Every patch of the concert in Patch List order: its name, its Program
    Change (None without one), its Bank Select (None without one) and the
    name of the set it is in (None at the top)."""
    root = os.path.join(concert, "Concert.patch")
    if not os.path.isfile(os.path.join(root, "data.plist")):
        raise ValueError(f"{concert}: not a MainStage concert (no Concert.patch/data.plist in it)")
    out = []
    _walk(root, _load(root), None, out)
    return out


def _walk(folder: str, data: dict, set_name, out: list) -> None:
    for node in data.get("nodes") or []:
        sub = os.path.join(folder, str(node))
        if not os.path.isfile(os.path.join(sub, "data.plist")):
            continue
        child = _load(sub)
        engine = _engine(child)
        name = str(engine.get("name") or _stem(sub))
        if child.get("nodes"):
            _walk(sub, child, name, out)
            continue
        program = engine.get("patchChangeNum") if engine.get("hasProgramChange") else None
        bank = engine.get("bankSelectNumber") if engine.get("hasBankSelect") else None
        out.append(Patch(name, None if program is None else int(program),
                         None if bank is None else int(bank), set_name))


def preset_names(patches: list) -> tuple:
    """({program: name} for the pedal, [notes on the patches left out])."""
    names, notes = {}, []
    for p in patches:
        if p.program is None:
            notes.append(f"{p.name}: no Program Change, left out")
        elif p.bank:
            notes.append(f"{p.name}: on Bank Select {p.bank}, left out; the names are for bank 0")
        elif not 0 <= p.program < PRESET_NAME_COUNT:
            notes.append(f"{p.name}: Program Change {p.program} is not 0-{PRESET_NAME_COUNT - 1}, left out")
        elif p.program in names:
            notes.append(f"{p.name}: Program Change {p.program} is {names[p.program]}'s too, left out")
        else:
            names[p.program] = p.name
    return names, notes


def shown(name: str) -> str:
    """The name as the pedal shows it."""
    return display_text(name)[:PRESET_NAME_LEN].rstrip()


def with_names(df, names: dict, replace: bool = False):
    """A Preset_Names frame with the names put in, those of other programs
    kept unless replace."""
    rows = {}
    if df is not None and not replace:
        for _, row in df.iterrows():
            try:
                program = int(float(str(row.get("Program")).strip()))
            except ValueError:
                continue
            rows[program] = str(row.get("Name") if pd.notna(row.get("Name")) else "")
    for program, name in names.items():
        rows[program] = shown(name)
    return pd.DataFrame([[str(p), rows[p]] for p in sorted(rows) if rows[p]], columns=PRESET_NAME_COLUMNS)
