"""A song: one bank saved to a file of its own, to load into any bank of any
configuration.

A set is then built from a library of songs, and a song shared with the rest
of the band. The file is a configuration CSV cut down to the bank: its name,
its buttons with their short, long and double press lists, the commands sent
on entering it (its tempo among them) and its expression pedal settings, the
combinations that count only in it, and what all of those point at:

- the button lists its Macros and Buttons run in other banks, which go to the
  same place in the configuration loading the song: that place must be free or
  hold the same, or the song does not load;
- the SysEx strings its commands send, which take the same number where it is
  free or holds the same bytes, and another free one otherwise;
- the names of the programs it sends, added where the configuration has none.

What the bank points at by number and cannot carry, a Bank command going to
another bank or an If asking for one, is kept as it is and said in the notes.
"""

import io
import re

import pandas as pd

import lib.cmdBinaryPacker as cbp
from lib.bankClipboard import _bank, _button, _replace
from lib.bankReorder import _put, remap_commands
from lib.configCsv import PAD
from lib.configPacker import (
    BANK_ENTER_SECTION, BANK_EXPRESSION_SECTION, COMBO_COLUMNS, COMBO_SECTION, DOUBLE_PRESS_SECTION,
    EXPRESSION_SECTION, LONG_PRESS_SECTION, PRESET_NAME_COLUMNS, PRESET_NAMES_SECTION, SYSEX_SECTION,
    pack_config, pack_flash_image,
)
from lib.flashLayout import COMBO_COUNT, NUM_BANKS, SYSEX_STRING_COUNT

BANK = "Bank_Number"
BUTTON = "Button_Identifier"
NAMING = "Bank_Naming"
BUTTONS = "Button_Settings"
# The lists a Macro or Button names, in cbp.MACRO_LISTS order
LISTS = [BUTTONS, LONG_PRESS_SECTION, DOUBLE_PRESS_SECTION]
LABELS = {BUTTONS: "Label", LONG_PRESS_SECTION: "Long_Label", DOUBLE_PRESS_SECTION: "Long_Label"}
# The sections a bank owns a row of, or one per button
BANK_SECTIONS = [NAMING, BUTTONS, LONG_PRESS_SECTION, DOUBLE_PRESS_SECTION, BANK_ENTER_SECTION,
                 BANK_EXPRESSION_SECTION]
# The ones holding command lists
COMMAND_SECTIONS = [BUTTONS, LONG_PRESS_SECTION, DOUBLE_PRESS_SECTION, BANK_ENTER_SECTION]
SONG_SECTIONS = BANK_SECTIONS + [COMBO_SECTION, SYSEX_SECTION, PRESET_NAMES_SECTION]
MARK = "# Song"
NUM = "Number_(PC/CC/Note)"
ON = "OnValue_(CC/PB)"
MODE = "KeyMode_(Key)"


def _cell(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).strip()
    return "" if s.lower() == "nan" else s


def _prefixes(df):
    return [c[: -len("_CommandType")] for c in df.columns if c.endswith("_CommandType")]


def _commands(row, prefixes):
    """(prefix, type, number, on, mode) of each command in a row."""
    for p in prefixes:
        kind = _cell(row.get(f"{p}_CommandType"))
        if kind:
            yield p, kind, _cell(row.get(f"{p}_{NUM}")), _cell(row.get(f"{p}_{ON}")), _cell(row.get(f"{p}_{MODE}"))


def _rows(df, bank):
    if df is None or BANK not in df.columns:
        return []
    return [row for row in df.to_dict("records") if _bank(row.get(BANK)) == bank]


def _row(df, bank, button):
    if df is None or BANK not in df.columns:
        return None
    for row in df.to_dict("records"):
        if _bank(row.get(BANK)) == bank and _button(row.get(BUTTON)) == button:
            return row
    return None


def _int(text, default=-1):
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default


def _list_index(text) -> int:
    names = [m.upper() for m in cbp.MACRO_LISTS]
    return names.index(text.upper()) if text.upper() in names else 0


def _calls(row, prefixes, bank):
    """(list section, bank, button) of each list another bank holds that the
    row's Macros and Buttons run; `bank` is the bank the row is in."""
    for _, kind, number, on, mode in _commands(row, prefixes):
        if kind == "Macro":
            target, which = _bank(on or "0"), _list_index(mode)
        elif kind == "Button":
            if not on or on.upper() == "THIS BANK":
                continue                      # the bank showing, whichever
            try:
                which = cbp.button_mode(mode)[1]
            except ValueError:
                which = 0
            target = _bank(on)
        else:
            continue
        if target != bank:
            yield LISTS[which], target, _button(number or "1")


def _combo_runs(df, bank):
    """The combinations that count only in `bank`."""
    if df is None or "Bank" not in df.columns:
        return []
    return [row.to_dict() for _, row in df.iterrows()
            if _cell(row.get("Switches")) and _bank(_cell(row.get("Bank"))) == bank]


def _section_rows(sections, name, rows):
    """A frame of the section's columns holding `rows`."""
    df = sections.get(name)
    columns = list(df.columns) if df is not None else list(rows[0].keys()) if rows else []
    return pd.DataFrame(rows, columns=columns).astype(object)


def _texts(section_rows):
    """The song's sections as CSV text."""
    out = io.StringIO()
    for name, df in section_rows:
        out.write(f"* {name}{PAD}\n")
        df.to_csv(out, index=False, lineterminator="\n")
        out.write(PAD + "\n")
    return out.getvalue()


def save_song(sections: dict, bank) -> str:
    """The song file for `bank` of a configuration, as text."""
    s = _bank(bank)
    if not 0 <= _int(s) < NUM_BANKS:
        raise ValueError(f"there is no bank {bank}: banks are 0-{NUM_BANKS - 1}")
    picked = {name: _rows(sections.get(name), s) for name in BANK_SECTIONS}
    combos = _combo_runs(sections.get(COMBO_SECTION), s)

    # The lists other banks hold that the song runs, and those they run
    todo = []
    for name in COMMAND_SECTIONS:
        df = sections.get(name)
        if df is not None:
            for row in picked[name]:
                todo.extend(_calls(row, _prefixes(df), s))
    for c in combos:
        run = _bank(_cell(c.get("Run_Bank")))
        if run != s:
            todo.append((LISTS[_list_index(_cell(c.get("Run_List")))], run, _button(_cell(c.get("Run_Button")))))
    carried = set()
    while todo:
        key = todo.pop()
        if key in carried:
            continue
        carried.add(key)
        name, b, btn = key
        row = _row(sections.get(name), b, btn)
        if row is None:
            continue
        picked[name].append(row)
        todo.extend(_calls(row, _prefixes(sections[name]), b))

    # The SysEx strings and program names the commands use
    strings, programs = set(), set()
    for name in COMMAND_SECTIONS:
        df = sections.get(name)
        if df is None:
            continue
        for row in picked[name]:
            for _, kind, number, _, _ in _commands(row, _prefixes(df)):
                if kind == "SysEx":
                    strings.add(_int(number or "0"))
                elif kind == "PC":
                    programs.add(_int(number))
    sysex = sections.get(SYSEX_SECTION)
    sysex_rows = []
    if sysex is not None:
        for i, (_, row) in enumerate(sysex.iterrows()):
            index = _int(_cell(row.get("Index")), i)
            if index in strings:
                sysex_rows.append({"Index": str(index), "Bytes": _cell(row.get("Bytes"))})
    names = sections.get(PRESET_NAMES_SECTION)
    name_rows = []
    if names is not None:
        name_rows = [{"Program": _cell(r.get("Program")), "Name": _cell(r.get("Name"))}
                     for _, r in names.iterrows() if _int(_cell(r.get("Program"))) in programs and _cell(r.get("Name"))]

    out = [(name, _section_rows(sections, name, picked[name])) for name in BANK_SECTIONS if picked[name]]
    if combos:
        out.append((COMBO_SECTION, pd.DataFrame(combos, columns=COMBO_COLUMNS)))
    if sysex_rows:
        out.append((SYSEX_SECTION, pd.DataFrame(sysex_rows, columns=["Index", "Bytes"])))
    if name_rows:
        out.append((PRESET_NAMES_SECTION, pd.DataFrame(name_rows, columns=PRESET_NAME_COLUMNS)))
    title = picked[NAMING][0].get("Bank_Name_Large") if picked[NAMING] else ""
    head = f"{MARK}{PAD}\n# Bank {s} {_cell(title)}, to load into a bank of any configuration{PAD}\n#{PAD}\n"
    return head + _texts(out)


def file_name(sections: dict, bank) -> str:
    """The file a bank is saved as: its name and info line, or its number."""
    rows = _rows(sections.get(NAMING), _bank(bank))
    words = " ".join(_cell(rows[0].get(c)) for c in ("Bank_Name_Large", "Bank_Info_Small")) if rows else ""
    name = re.sub(r"[^\w-]+", "_", words.strip()).strip("_") or f"bank-{_bank(bank)}"
    return f"{name}.song.csv"


def song_bank(song: dict) -> str:
    """The bank the song was saved from, or ValueError if it is no song."""
    if "Global_Settings" in song:
        raise ValueError("this is a whole configuration, not a song: a song is one bank saved with Save song")
    naming = song.get(NAMING)
    if naming is None or len(naming) != 1 or BUTTONS not in song:
        raise ValueError("this is not a song file: it should hold one bank, saved with Save song")
    return _bank(naming[BANK].iat[0])


def _same(a, b, name) -> bool:
    """Whether two rows of a list section do the same."""
    def what(row):
        if row is None:
            row = {}
        labels = []
        packed = cbp.pack_row(row, labels, leave=name == BANK_ENTER_SECTION)
        extras = []
        if name == BUTTONS:
            extras = [cbp.pack_button_led_modes([_cell(row.get("Light_Mode")) or "Normal"],
                                                [_cell(row.get("Group"))], [_cell(row.get("Momentary_Hold"))],
                                                [_cell(row.get("Tempo_Flash"))], [_cell(row.get("Global"))])]
            extras += [cbp._yes_no(_cell(row.get(c)), c) for c in ("Reset_On_Bank", "Instant_Press", "Reload_When_Lit")]
        return packed, labels, _cell(row.get(LABELS.get(name, ""))), extras
    return what(a) == what(b)


def _empty(row, name) -> bool:
    return _same(row, None, name)


def _where(name, bank, button) -> str:
    press = {BUTTONS: "", LONG_PRESS_SECTION: " long press", DOUBLE_PRESS_SECTION: " double press"}[name]
    return f"bank {bank} button {button}{press}"


def _with_columns(df, columns):
    """df with any of `columns` it lacks added, empty."""
    missing = [c for c in columns if c not in df.columns]
    if not missing:
        return df
    df = df.copy()
    for c in missing:
        df[c] = float("nan")
    return df


def _used_strings(sections, skip_bank):
    """(used, only there): the SysEx strings the configuration uses but in
    skip_bank, and those only skip_bank uses."""
    used, there = set(), set()
    for name in COMMAND_SECTIONS + ["BankSwitch_Settings"]:
        df = sections.get(name)
        if df is None:
            continue
        prefixes = _prefixes(df)
        for row in df.to_dict("records"):
            mine = BANK in df.columns and _bank(row.get(BANK)) == skip_bank
            for _, kind, number, _, _ in _commands(row, prefixes):
                if kind == "SysEx":
                    (there if mine else used).add(_int(number or "0"))
    exp = sections.get(EXPRESSION_SECTION)
    if exp is not None and "Output" in exp.columns:
        for value in exp["Output"]:
            text = _cell(value).upper()
            if text.startswith("SYSEX"):
                used.add(_int(text[5:]))
    return used, there - used


def _sysex_table(sections):
    """{index: bytes} of the configuration's 16 strings."""
    table = {i: "" for i in range(SYSEX_STRING_COUNT)}
    df = sections.get(SYSEX_SECTION)
    if df is not None:
        for i, (_, row) in enumerate(df.iterrows()):
            index = _int(_cell(row.get("Index")), i)
            if 0 <= index < SYSEX_STRING_COUNT:
                table[index] = " ".join(_cell(row.get("Bytes")).upper().split())
    return table


def _remap_strings(df, mapping):
    """Command lists with their SysEx strings renumbered."""
    if df is None or not mapping:
        return df
    df = df.copy().astype(object)
    for p in _prefixes(df):
        for idx in df.index:
            if _cell(df.at[idx, f"{p}_CommandType"]) == "SysEx":
                old = _int(_cell(df.at[idx, f"{p}_{NUM}"]) or "0")
                if old in mapping:
                    df.at[idx, f"{p}_{NUM}"] = str(mapping[old])
    return df


def _unused_banks(sections, but):
    """The banks nothing is in and nothing names, highest first, but those in `but`."""
    named = _named_banks(sections)
    return [str(b) for b in reversed(range(NUM_BANKS))
            if str(b) not in but and b not in named and _unused_bank(sections, str(b))]


def _unused_bank(sections, bank) -> bool:
    """Whether nothing is in `bank`."""
    naming = _rows(sections.get(NAMING), bank)
    if any(_cell(r.get("Bank_Name_Large")) or _cell(r.get("Bank_Info_Small")) for r in naming):
        return False
    for name in COMMAND_SECTIONS:
        if any(not _empty(r, name if name in LABELS else BANK_ENTER_SECTION) for r in _rows(sections.get(name), bank)):
            return False
    return True


def _named_banks(sections) -> set:
    """The banks the configuration names by number anywhere."""
    named = set()
    for name in COMMAND_SECTIONS + ["BankSwitch_Settings"]:
        df = sections.get(name)
        if df is None:
            continue
        prefixes = _prefixes(df)
        for row in df.to_dict("records"):
            for _, kind, _, on, mode in _commands(row, prefixes):
                m = mode.upper().replace(" ", "")
                if (kind in ("Macro", "Button") or (kind == "Bank" and (m in ("", "GOTO") or m.startswith("PAGE")))
                        or (kind == "If" and mode.upper() in ("BANK IS", "BANK IS NOT"))):
                    named.add(_int(on))
    for name, cols in ((COMBO_SECTION, ("Bank", "Run_Bank")), ("Setlist", (BANK,)), ("MidiMap_Settings", ("Run_Bank",))):
        df = sections.get(name)
        if df is not None:
            for c in cols:
                if c in df.columns:
                    named.update(_int(_cell(v)) for v in df[c])
    glob = sections.get("Global_Settings")
    if glob is not None:
        named.update(_int(_cell(r.get("Value"))) for _, r in glob.iterrows() if _cell(r.get("Label")) == "Global_Bank")
    return named


def _renumber(df, strings, moves, s, t):
    """Song rows as they go in: their SysEx strings renumbered, the lists they
    run that moved followed, and their own bank made the new one."""
    df = _remap_strings(df, strings)
    if moves:
        df = df.copy().astype(object)
        for p in _prefixes(df):
            for idx in df.index:
                kind = _cell(df.at[idx, f"{p}_CommandType"])
                on = _cell(df.at[idx, f"{p}_{ON}"]) if f"{p}_{ON}" in df.columns else ""
                if kind in ("Macro", "Button") and on and _bank(on) in moves:
                    df.at[idx, f"{p}_{ON}"] = moves[_bank(on)]
    # Moved banks are never s, so this leaves them be
    return remap_commands(df, {_int(s): _int(t)})


def load_song(sections: dict, song: dict, bank):
    """(sections, notes): the configuration with `bank` made the song, and
    what to know about it. ValueError when the song does not fit."""
    t = _bank(bank)
    if not 0 <= _int(t) < NUM_BANKS:
        raise ValueError(f"there is no bank {bank}: banks are 0-{NUM_BANKS - 1}")
    s = song_bank(song)
    out = dict(sections)
    notes = []

    # The lists the song runs in other banks: at the same place here when it
    # is free or holds the same, or else, with the rest of that bank's, in a
    # bank nothing here uses
    units = {}
    for name in LISTS:
        for row in [r for _, r in song[name].iterrows()] if name in song else []:
            b = _bank(row.get(BANK))
            if b != s:
                units.setdefault(b, []).append((name, _button(row.get(BUTTON)), row.to_dict()))
    moves = {}
    spare = None
    carried = []
    for b, rows in sorted(units.items(), key=lambda u: _int(u[0])):
        heres = [_row(sections.get(name), b, btn) for name, btn, _ in rows]
        fits = b != t and all(here is None or _empty(here, name) or _same(here, row, name)
                              for (name, _, row), here in zip(rows, heres))
        if not fits:
            if spare is None:
                spare = _unused_banks(sections, {t, s, *units})
            if not spare:
                name, btn, _ = rows[0]
                raise ValueError(f"the song runs {_where(name, b, btn)}, which holds something else here, "
                                 f"and no bank here is free to take it: free one, or load the song into "
                                 f"another configuration")
            moves[b] = spare.pop(0)
            notes.append(f"what the song runs in bank {b} is in bank {moves[b]} here, which was empty")
        for (name, btn, row), here in zip(rows, heres):
            if b in moves or here is None or _empty(here, name):
                carried.append((name, moves.get(b, b), btn, row))
                if b not in moves:
                    notes.append(f"{_where(name, b, btn)} was empty here and now holds what the song runs there")

    # Its SysEx strings: the same number where it is free or holds the same bytes
    table = _sysex_table(sections)
    used, only_there = _used_strings(sections, t)
    mapping = {}
    if SYSEX_SECTION in song:
        wanted = {_int(_cell(r.get("Index"))): " ".join(_cell(r.get("Bytes")).upper().split())
                  for _, r in song[SYSEX_SECTION].iterrows()}
        taken = set()
        for i, text in sorted(wanted.items()):
            same = [j for j in range(SYSEX_STRING_COUNT) if table[j] == text and j not in taken]
            # Empty ones first, then those only the bank replaced sent
            free = [j for j in range(SYSEX_STRING_COUNT)
                    if table[j] == "" and j not in used and j not in taken]
            free += [j for j in sorted(only_there) if table[j] != "" and j not in taken]
            if i in same or (i in free and not same):
                j = i
            elif same:
                j = same[0]
            elif free:
                j = free[0]
            else:
                raise ValueError(f"the song sends SysEx string {i} ({text or 'empty'}), and all "
                                 f"{SYSEX_STRING_COUNT} strings here are in use")
            taken.add(j)
            table[j] = text
            if j != i:
                mapping[i] = j
                notes.append(f"its SysEx string {i} is string {j} here")
        rows = [{"Index": str(i), "Bytes": table[i]} for i in range(SYSEX_STRING_COUNT)]
        out[SYSEX_SECTION] = pd.DataFrame(rows, columns=["Index", "Bytes"]).astype(object).replace("", float("nan"))

    # The bank itself, its own bank number made the new one
    for name in BANK_SECTIONS:
        rows = _rows(song.get(name), s)
        df = song.get(name)
        if df is not None and name in COMMAND_SECTIONS:
            rows = _rows(_renumber(df, mapping, moves, s, t), s)
        target = out.get(name)
        if target is None:
            if not rows:
                continue
            target = pd.DataFrame(columns=list(rows[0].keys()))
        elif rows:
            target = _with_columns(target, [c for c in rows[0] if _cell(rows[0][c])])
        out[name] = _replace(target, rows, t)

    for name, b, btn, row in carried:
        row = _renumber(pd.DataFrame([row]), mapping, moves, s, t).iloc[0].to_dict()
        target = out.get(name)
        if target is None:
            target = pd.DataFrame(columns=list(row.keys()))
        out[name] = _put(_with_columns(target, list(row.keys())), row, b, btn)

    # The combinations that count only in this bank, where its own were
    combos = out.get(COMBO_SECTION)
    brought = []
    if COMBO_SECTION in song:
        for r in song[COMBO_SECTION].to_dict("records"):
            if _bank(_cell(r.get("Bank"))) != s:
                continue
            run = _bank(_cell(r.get("Run_Bank")))
            brought.append({**r, "Bank": t, "Run_Bank": t if run == s else moves.get(run, run)})
    if brought or combos is not None:
        rows, placed = [], False
        for r in [] if combos is None else combos.to_dict("records"):
            if _cell(r.get("Switches")) and _bank(_cell(r.get("Bank"))) == t:
                if not placed:
                    rows += brought
                    placed = True
                continue
            rows.append(r)
        if not placed:
            rows += brought
        in_use = sum(1 for r in rows if _cell(r.get("Switches")))
        if in_use > COMBO_COUNT:
            raise ValueError(f"the song brings {len(brought)} combinations and this configuration has "
                             f"{in_use - len(brought)} for its other banks: at most {COMBO_COUNT} fit")
        columns = list(combos.columns) if combos is not None else COMBO_COLUMNS
        out[COMBO_SECTION] = pd.DataFrame(rows, columns=columns).astype(object)

    # The names of the programs it sends, where this configuration has none
    if PRESET_NAMES_SECTION in song:
        names = out.get(PRESET_NAMES_SECTION)
        rows = [] if names is None else [r.to_dict() for _, r in names.iterrows()]
        have = {_int(_cell(r.get("Program"))): _cell(r.get("Name")) for r in rows}
        for _, r in song[PRESET_NAMES_SECTION].iterrows():
            p, name = _int(_cell(r.get("Program"))), _cell(r.get("Name"))
            if p not in have or not have[p]:
                rows = [x for x in rows if _int(_cell(x.get("Program"))) != p]
                rows.append({"Program": str(p), "Name": name})
                have[p] = name
            elif have[p] != name:
                notes.append(f"program {p} keeps the name {have[p]} it has here; the song calls it {name}")
        rows.sort(key=lambda x: _int(_cell(x.get("Program"))))
        out[PRESET_NAMES_SECTION] = pd.DataFrame(rows, columns=PRESET_NAME_COLUMNS).astype(object)

    notes += _numbered(song, s)
    glob = sections.get("Global_Settings")
    shares = glob is not None and any(_cell(r.get("Label")) == "Global_Bank" and _cell(r.get("Value")) not in ("", "Off")
                                      for _, r in glob.iterrows())
    marked = [_button(r.get(BUTTON)) for _, r in song[BUTTONS].iterrows()
              if _bank(r.get(BANK)) == s and _cell(r.get("Global")).upper() in ("Y", "YES", "1", "TRUE")]
    if marked and not shares:
        notes.append(f"button{'s' if len(marked) > 1 else ''} {', '.join(marked)} {'are' if len(marked) > 1 else 'is'} "
                     f"marked Global, and this configuration has no global buttons bank")
    try:
        pack_config(out)
        pack_flash_image(out)
    except ValueError as e:
        raise ValueError(f"with the song in bank {t}, the configuration does not pack: {e}") from None
    return out, notes


def _numbered(song, s):
    """What in the song names another bank by number, which it cannot carry."""
    goes, asks = [], []
    for name in COMMAND_SECTIONS:
        df = song.get(name)
        if df is None:
            continue
        prefixes = _prefixes(df)
        for _, row in df.iterrows():
            if _bank(row.get(BANK)) != s:
                continue
            where = f"button {_button(row.get(BUTTON))}" if BUTTON in df.columns else "the enter list"
            if name == LONG_PRESS_SECTION:
                where += " long"
            elif name == DOUBLE_PRESS_SECTION:
                where += " double"
            for _, kind, _, on, mode in _commands(row, prefixes):
                m = mode.upper().replace(" ", "")
                other = _bank(on or "0")
                if other == s:
                    continue
                if kind == "Bank" and (m in ("", "GOTO") or m.startswith("PAGE")):
                    goes.append(f"{where} to {other}")
                elif kind == "If" and mode.upper() in ("BANK IS", "BANK IS NOT"):
                    asks.append(f"{where} for {other}")
    notes = []
    if goes:
        notes.append("it goes to other banks by number, as where it was saved: " + ", ".join(goes))
    if asks:
        notes.append("it asks for other banks by number, as where it was saved: " + ", ".join(asks))
    return notes
