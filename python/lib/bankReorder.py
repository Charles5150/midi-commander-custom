"""Move a bank to another place in the list, and copy a single button.

Moving bank 5 to place 2 shifts banks 2, 3 and 4 one place down, as dragging a
row in a list would. Everything a bank owns moves with it: its name, its
buttons with their long and double press lists, the commands sent on entering
it and its expression pedal settings. Everything that names a bank by number
follows it too, so a configuration behaves the same after the move:

- the Bank command in GoTo and Page modes (Up, Down and Back are relative);
- the If tests "Bank is" and "Bank is not";
- Macro, which names the bank the called list lives in;
- the setlist, Global_Bank, and the combinations' bank and Run_Bank.

A host changing banks by Bank_Change_CC names banks by number from outside the
configuration, and cannot be followed.
"""

import pandas as pd

from lib.bankClipboard import _bank, _button

BANK = "Bank_Number"
BUTTON = "Button_Identifier"
NUM_BANKS = 32
IF_BANK_TESTS = ("BANK IS", "BANK IS NOT")


def move_map(src: int, dst: int, num_banks: int = NUM_BANKS) -> dict:
    """{old bank: new bank} for moving bank `src` to place `dst`."""
    order = list(range(num_banks))
    order.insert(dst, order.pop(src))
    return {old: new for new, old in enumerate(order)}


def _renumber(value, mapping):
    """The bank in `value` renumbered, or `value` untouched if it is not one."""
    text = _bank(value)
    try:
        bank = int(text)
    except ValueError:
        return value
    if bank not in mapping:
        return value
    return str(mapping[bank])


def _cell(value) -> str:
    s = str(value).strip()
    return "" if s.lower() == "nan" else s


def _command_prefixes(df):
    return [c[: -len("_CommandType")] for c in df.columns if c.endswith("_CommandType")]


def _names_a_bank(cmd_type: str, key_mode: str) -> bool:
    mode = key_mode.upper().replace(" ", "")
    if cmd_type == "Bank":
        return mode in ("", "GOTO") or mode.startswith("PAGE")
    if cmd_type == "If":
        return key_mode.strip().upper() in IF_BANK_TESTS
    return cmd_type == "Macro"


def remap_commands(df, mapping):
    """Command lists with every bank named by a command renumbered."""
    if df is None:
        return None
    df = df.copy().astype(object)
    for p in _command_prefixes(df):
        value_col, mode_col = f"{p}_OnValue_(CC/PB)", f"{p}_KeyMode_(Key)"
        if value_col not in df.columns:
            continue
        for idx in df.index:
            cmd_type = _cell(df.at[idx, f"{p}_CommandType"])
            key_mode = _cell(df.at[idx, mode_col]) if mode_col in df.columns else ""
            if _names_a_bank(cmd_type, key_mode):
                df.at[idx, value_col] = _renumber(df.at[idx, value_col], mapping)
    return df


def _move_rows(df, mapping):
    """A per bank frame with its rows renumbered and put back in bank order."""
    if df is None or BANK not in df.columns:
        return df
    df = df.copy().astype(object)
    df[BANK] = [_renumber(v, mapping) for v in df[BANK]]

    def order(value):
        try:
            return int(_bank(value))
        except ValueError:
            return NUM_BANKS
    rows = sorted(range(len(df)), key=lambda i: order(df[BANK].iat[i]))
    return df.iloc[rows].reset_index(drop=True)


def move_bank(frames: dict, src: int, dst: int) -> dict:
    """The configuration's frames with bank `src` moved to place `dst`.

    `frames` holds the GUI's DataFrames by name (buttons, long, double, enter,
    banks, bank_exp, bank_switch, setlist, combos, global); missing or None
    ones are passed through.
    """
    if src == dst:
        return dict(frames)
    mapping = move_map(src, dst)
    out = dict(frames)
    for name in ("buttons", "long", "double", "enter"):
        out[name] = remap_commands(_move_rows(frames.get(name), mapping), mapping)
    for name in ("banks", "bank_exp"):
        out[name] = _move_rows(frames.get(name), mapping)
    out["bank_switch"] = remap_commands(frames.get("bank_switch"), mapping)

    setlist = frames.get("setlist")
    if setlist is not None:
        setlist = setlist.copy().astype(object)
        setlist[BANK] = [_renumber(v, mapping) for v in setlist[BANK]]
        out["setlist"] = setlist

    combos = frames.get("combos")
    if combos is not None:
        combos = combos.copy().astype(object)
        for col in ("Bank", "Run_Bank"):
            if col in combos.columns:
                combos[col] = [_renumber(v, mapping) for v in combos[col]]
        out["combos"] = combos

    glob = frames.get("global")
    if glob is not None:
        glob = glob.copy().astype(object)
        for idx in glob.index:
            if str(glob.at[idx, "Label"]).strip() == "Global_Bank":
                glob.at[idx, "Value"] = _renumber(glob.at[idx, "Value"], mapping)
        out["global"] = glob
    return out


# --- One button ---------------------------------------------------------------

def _row(df, bank, button):
    if df is None:
        return None
    for _, row in df.iterrows():
        if _bank(row.get(BANK)) == bank and _button(row.get(BUTTON)) == button:
            return row.to_dict()
    return None


def copy_button(df_buttons, df_long, df_double, bank, button) -> dict:
    """Snapshot of one button: label, LED and flags, and its three lists."""
    b, btn = _bank(bank), _button(button)
    return {
        "bank": b,
        "button": btn,
        "short": _row(df_buttons, b, btn),
        "long": _row(df_long, b, btn),
        "double": _row(df_double, b, btn),
    }


def _put(df, row, bank, button):
    """df with the row of (bank, button) replaced by `row`, or removed if None."""
    if df is None:
        return None
    out, placed = [], False
    for _, r in df.iterrows():
        if _bank(r.get(BANK)) == bank and _button(r.get(BUTTON)) == button:
            if row is not None and not placed:
                out.append({**row, BANK: bank, BUTTON: button})
                placed = True
            continue
        out.append(r.to_dict())
    if row is not None and not placed:
        out.append({**row, BANK: bank, BUTTON: button})
    return pd.DataFrame(out, columns=df.columns).astype(object).reset_index(drop=True)


def paste_button(df_buttons, df_long, df_double, clip, bank, button):
    """(df_buttons, df_long, df_double) with (bank, button) made a copy of the clip."""
    b, btn = _bank(bank), _button(button)
    if clip is None or (clip["bank"], clip["button"]) == (b, btn) or clip["short"] is None:
        return df_buttons, df_long, df_double
    return (
        _put(df_buttons, clip["short"], b, btn),
        _put(df_long, clip["long"], b, btn),
        _put(df_double, clip["double"], b, btn),
    )
