# The display

The 128×64 OLED shows, on the top line, the bank's large 4 character name and its 8 character info. Below it, a 2×4 grid laid out like the pedal: buttons **1 2 3 4** on the top row, **A B C D** on the bottom. Each cell shows the button's label, or its identifier when it has none, and cells of toggle buttons are drawn inverted while the toggle is on, so the state of the whole bank is visible at a glance.

## Text from the computer

A host can write on the top line with one SysEx message (firmware 0.46), for instance the name of the patch or song it has just loaded:

```
F0 7D 48 place how text... F7
```

| `place` | Where | Fits without scrolling |
|---|---|---|
| `00` | the small info line right of the bank name | 11 characters |
| `01` | the large bank name | 4 characters |
| `02` | the whole top line, large | 11 characters |
| `03` | the whole top line, small | 18 characters |

| `how` | How long |
|---|---|
| `00` | until the bank changes |
| `01` | until the host changes it |
| `02` | 1.5 seconds, like the tempo readout |

The text is plain ASCII, one byte per character (`20`–`7E`), and anything else shows as a space. Up to 32 characters are kept in any place, and more are cut off.

### Longer than fits

A text wider than its place scrolls across it once (firmware 0.61), so the whole song name gets read: still for a moment, then along at about 40 pixels a second until its end shows, still again, and back to its beginning, where it stays. It scrolls when it arrives and again whenever a bank is entered; the same text sent again leaves it where it is, so a host that repeats itself does not keep it moving. Only its own place moves: a long info line scrolls beside a still bank name. A long text for a moment stays up until it has reached its end, however long that takes past the 1.5 seconds. Scrolling never holds a press up, since the pedal draws a step only once the previous screen has gone out. Firmware before 0.61 keeps only what fits. An empty text gives the place back to what the bank shows. A whole line text hides the bank name and info while it is there, and the large and small whole lines replace each other. A text shown for a moment goes back to what was there before, and one in the bank name or info shows even over a whole line text. Text also wakes the display if the pedal was asleep. The pedal answers `F0 7D 49 place how F7`, and ignores a place or `how` it does not know.

For example, `F0 7D 48 02 00 53 77 65 65 74 20 43 68 69 6C 64 F7` puts **Sweet Child** across the top line until the bank changes. `Send_Text.py` builds and sends it:

```bash
.venv/bin/python python/Send_Text.py "Sweet Child"                      # whole line, large, until the bank changes
.venv/bin/python python/Send_Text.py --place info --keep always "Clean"  # the info line, for good
.venv/bin/python python/Send_Text.py --keep moment "Next: Intro"        # for a moment
.venv/bin/python python/Send_Text.py "Sweet Child O' Mine"              # too long for the line: scrolls once
.venv/bin/python python/Send_Text.py ""                                 # back to the bank
.venv/bin/python python/Send_Text.py --hex "Sweet Child"                # only print the bytes, for a host to send
```

`--place` is `info`, `name`, `line` (the default) or `small`, and `--keep` is `bank` (the default), `always` or `moment`.

## The banner's own text

The [banner at power on](12-configuration-file.md#global_settings) shows the configuration's name, unless the pedal holds a text of its own (firmware 0.63): up to 60 characters of plain ASCII, such as a band, a show or a phone number in case the pedal gets lost. It belongs to the pedal, not to a configuration, so it stays whichever of the four is loaded, when a configuration is flashed and through firmware updates. It shows only while `Boot_Banner` is on, at its speed, followed by the version as the name is.

In the configurator, **Banner Text…** under PEDAL reads the text from the pedal and stores, clears or keeps it. From a terminal:

```bash
.venv/bin/python python/Send_Text.py --banner "The Band  612 345 678"   # store it
.venv/bin/python python/Send_Text.py --banner                           # print what the pedal holds
.venv/bin/python python/Send_Text.py --banner ""                        # clear it: the name again
```

Over SysEx, `F0 7D 4C 01 text... F7` stores it, with no text clears it, and `F0 7D 4C 00 F7` only asks. The pedal answers `F0 7D 4D result text... F7`, with `result` 0, or 1 when it refused a text longer than 60 characters or with a byte outside `20`–`7E` and kept the one it had, and then the text it holds. The text sits in a flash page of its own at `0x0803A000`, past the fourth configuration slot, which nothing else writes; a blank or damaged page reads as no text.

---

[← Expression pedals](08-expression.md) · [Contents](README.md) · [Editing on the pedal →](10-editing-on-the-pedal.md)
