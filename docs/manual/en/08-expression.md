# Expression pedals

## Expression_Settings

Optional; two rows, `Pedal` 1 and 2.

| Column | Values | Meaning |
|---|---|---|
| `Min_ADC`, `Max_ADC` | 0–4095 | Calibrated heel and toe readings. Defaults 80 and 3900. |
| `Curve` | Linear / Log / Exp | Log is fast at the start of the travel, Exp is slow at the start. |
| `Invert` | Y / N | Swap heel and toe. |
| `Channel` | Global or 1–16 | Global uses `MIDI_Channel`. |
| `Toe_Button` | None or 1–4, A–D | Button tapped when the pedal reaches the toe. |
| `Toe_Level` | 1–127 | Value the pedal must reach for that. Default 120. |
| `Heel_Button` | None or 1–4, A–D | Button tapped when the pedal returns to the heel. |
| `Heel_Level` | 0–127 | Value it must fall to for that. Default 7. |
| `Out_Min`, `Out_Max` | 0–127 | Values sent at the heel and at the toe. Defaults 0 and 127. |
| `Auto_Button` | None or 1–4, A–D | Button switched on as the pedal leaves the heel and off after resting there (auto-engage). |
| `Auto_Off_ms` | 10–2540 | How long the pedal must rest at the heel before that button goes off. Default 500. |
| `Output` | CC, PitchBend or CC14 | What the pedal sends: its CC with 7 bits, Pitch Bend, or a 14-bit CC pair. Default CC. |

### Output range

The pedal's travel, after the curve and `Invert`, is spread between `Out_Min` at the heel and `Out_Max` at the toe, so 40 and 127 make a volume pedal that never goes silent, and 127 and 0 turn it round without touching `Invert`. The ends are always reached exactly. `Toe_Level` and `Heel_Level` still refer to the pedal's position, 0 to 127, whatever it sends. A bank can override either end in `BankExpression_Settings`. Stored in two bytes that were reserved in each pedal's record, where older tools wrote zeros: firmware 0.33 reads 0 and 0 as the full range, so older configurations are unchanged. Firmware before 0.33 ignores the range.

### Pitch Bend and 14-bit CC

With `Output` set to `PitchBend` the pedal sends Pitch Bend on its channel instead of its CC, and with `CC14` it sends a 14-bit CC pair: the high 7 bits on its CC and the low 7 bits on that CC plus 32, as the MIDI standard pairs them, so CC 4 goes out as CC 4 and CC 36, the high byte first. Both have 16384 steps instead of 128, and the pedal sends every finer step it can measure: its dead band against noise is four times narrower in these modes, and a pedal at rest still sends nothing. `Out_Min` and `Out_Max` keep counting from 0 to 127, and each is taken as its top 7 bits, so 64 is the middle of the bend: 64 to 127 bends up only, from the heel at rest, and 127 is the very top. Curve, `Invert` and the toe and heel levels work as before. A bank or an `Exp` command that sends the pedal to another CC sends that CC: as a pair when `Output` is `CC14` and the CC is below 32, which a 14-bit CC needs, and with 7 bits otherwise, so a Pitch Bend pedal can still be a volume pedal in another bank. A 14-bit CC above 31 goes out with 7 bits too. Stored in byte 15 of each pedal's record, 0 for CC, 1 for Pitch Bend and 2 for 14-bit CC, where older tools wrote a zero. Firmware before 0.44 ignores it and sends the CC.

### Auto-engage

For a wah that switches itself on and off, as on Fractal and Line 6 units: put the wah's on and off commands on a toggle button and name that button in `Auto_Button`. Moving the pedal up past `Heel_Level` switches the button on, just before the pedal's first value is sent, and resting at or below `Heel_Level` for `Auto_Off_ms` switches it off. The button is pressed as if by foot, so its commands, LED and display cell follow, and it can still be pressed by hand: both directions act only on the moment the pedal leaves the heel or has rested there long enough, so a wah switched off by hand with the pedal up, or on by hand at the heel, stays as it was left. The button is the same in every bank, and nothing happens in a bank where it is not a toggle, so put the wah on the same button in the banks that need it. It works when a bank silences the pedal too. Stored in bytes 13 and 14 of each pedal's record, the button plus one and the delay in 10 ms steps, where older tools wrote zeros, which mean no auto-engage. Firmware before 0.41 ignores it.

Used as a switch, the pedal taps a button of the **current bank**, sending whatever that button is configured to send, including its toggle state and LED. Each direction re-arms only after the pedal moves back past its level by a margin, so resting on the edge does not retrigger.

Both 1/4" jacks are read through the ADC every millisecond, with the pin pulled down between readings to prevent crosstalk between the two inputs, smoothed with an adaptive filter and a small hysteresis so a resting pedal does not chatter. A CC is sent only when the 7-bit value changes.

If a pedal produces no CC, open the Expression tab and press **Connect live view**: if the raw value does not follow the pedal, the problem is the cable or jack; if it does but no CC reaches your MIDI monitor, check the channel and CC number, and the bank's own settings in `BankExpression_Settings`.

## BankExpression_Settings

Optional; one row per `Bank_Number` (0–31), rows may be missing or in any order.

| Column | Values | Meaning |
|---|---|---|
| `Exp1_CC`, `Exp2_CC` | empty, 0–127 or Off | CC the pedal sends while this bank is selected. Empty keeps `Exp1_CC` / `Exp2_CC` from `Global_Settings`; Off silences the pedal in this bank. |
| `Exp1_Channel`, `Exp2_Channel` | empty or 1–16 | Channel for that pedal in this bank. Empty keeps the pedal's `Channel` from `Expression_Settings`. |
| `Exp1_Min`, `Exp1_Max`, `Exp2_Min`, `Exp2_Max` | empty or 0–127 | Values the pedal sends at the heel and at the toe in this bank. Empty keeps its `Out_Min` / `Out_Max` from `Expression_Settings`; each end is taken on its own. Needs firmware 0.33. |

An `Exp` command on a button can change these again until the next bank change, see [Button_Settings](05-buttons.md#button_settings). A silenced pedal still acts as a switch: its `Toe_Button` and `Heel_Button` keep working. After a bank change the pedal is not sent to its new CC, channel or range at the position it happens to rest in; it follows the next movement. Configurations written before 0.28 have nothing stored here and behave as if every cell were empty, and those written before 0.33 have no range here. The range is a table of its own after the CC and channel one, four bytes per bank, so their layout is unchanged. Edit it in the configurator's **Banks** tab.

---

[← Tempo, clock, LFO and sequencer](07-tempo.md) · [Contents](README.md) · [The display →](09-the-display.md)
