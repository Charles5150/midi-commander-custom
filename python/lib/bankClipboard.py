"""Copy everything that belongs to one bank and paste it over another.

A bank's content lives in three frames: Button_Settings (labels, LED modes and
the short press commands), LongPress_Settings and BankEnter_Settings. The bank
name, in Bank_Naming, is deliberately left out: copying a bank is how you start
a variant of it, and the variant wants its own name.

Pasting makes the target bank identical to the copied one. Rows the target had
and the source did not, a long press on some button for instance, are removed
rather than kept, so what you see after pasting is exactly the source.
"""

import pandas as pd

BANK = "Bank_Number"
BUTTON = "Button_Identifier"


def _bank(value) -> str:
    s = str(value).strip()
    try:
        return str(int(float(s)))
    except ValueError:
        return s


def _button(value) -> str:
    return str(value).strip().upper()


def _snapshot(df, bank, keyed_by_button):
    if df is None:
        return []
    rows = []
    for _, row in df.iterrows():
        if _bank(row.get(BANK)) != bank:
            continue
        rows.append(row.to_dict())
    if keyed_by_button:
        rows.sort(key=lambda r: _button(r.get(BUTTON)))
    return rows


def copy_bank(df_buttons, df_long, df_enter, bank, df_double=None, df_bank_exp=None):
    """Snapshot of one bank, independent of later edits to the frames."""
    b = _bank(bank)
    return {
        "bank": b,
        "buttons": _snapshot(df_buttons, b, True),
        "long": _snapshot(df_long, b, True),
        "enter": _snapshot(df_enter, b, False),
        "double": _snapshot(df_double, b, True),
        "bank_exp": _snapshot(df_bank_exp, b, False),
    }


def _replace(df, rows, bank):
    """df with every row of `bank` replaced by `rows`, kept where the old ones were."""
    if df is None:
        return None
    new_rows = []
    for r in rows:
        r = dict(r)
        r[BANK] = bank
        new_rows.append(r)

    out, inserted = [], False
    for _, row in df.iterrows():
        if _bank(row.get(BANK)) == bank:
            if not inserted:
                out.extend(new_rows)
                inserted = True
            continue
        out.append(row.to_dict())
    if not inserted:
        out.extend(new_rows)
    return pd.DataFrame(out, columns=df.columns).astype(object).reset_index(drop=True)


def paste_bank(df_buttons, df_long, df_enter, clip, bank):
    """Return (df_buttons, df_long, df_enter) with `bank` replaced by the clip."""
    b = _bank(bank)
    if clip is None or clip.get("bank") == b:
        return df_buttons, df_long, df_enter
    return (
        _replace(df_buttons, clip["buttons"], b),
        _replace(df_long, clip["long"], b),
        _replace(df_enter, clip["enter"], b),
    )


def paste_double(df_double, clip, bank):
    """df_double with `bank` replaced by the clip's double press rows."""
    b = _bank(bank)
    if clip is None or clip.get("bank") == b:
        return df_double
    return _replace(df_double, clip.get("double", []), b)


def paste_bank_expression(df_bank_exp, clip, bank):
    """df_bank_exp with `bank` taking the clip's expression pedal settings."""
    b = _bank(bank)
    if clip is None or clip.get("bank") == b or not clip.get("bank_exp"):
        return df_bank_exp
    return _replace(df_bank_exp, clip["bank_exp"], b)
