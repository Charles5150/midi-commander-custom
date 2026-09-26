# Expression pedals

Two expression pedals plug into the pedal's 1/4" jacks. Each sends a CC on its own channel, with calibrated end points and a response curve; each can also be a pair of extra footswitches, switch a wah on and off by itself, and send something different in every bank.

## Connecting and calibrating

Everything about the pedals is in the configurator's **Expression** tab, one panel per pedal.

1. Connect the pedal over USB and press **Connect live view**. It shows the pedal's position and the CC being sent, read from the pedal in real time.
2. Press **Calibrate**, sweep the pedal slowly from heel to toe and back a couple of times, and press **Done**.
3. The end points are filled in with a small margin, so 0 and 127 are always reached.

**If a pedal produces no CC**, open the Expression tab and press **Connect live view**:

- if the raw value does not follow the pedal, the problem is the cable or the jack;
- if it does but no CC reaches your MIDI monitor, check the channel and CC number, and the bank's own settings (see [A different target in each bank](#a-different-target-in-each-bank)).

*Calibration: firmware 0.8 or later.*

<details><summary>Under the hood</summary>

The two jacks are read through the ADC one after the other. Between readings each pin is pulled down, to prevent crosstalk between the two inputs and so an empty jack reads as zero; a reading is taken 12 ms after its pin is let go, while the rest of the pedal carries on. Readings are smoothed with an adaptive filter and a small hysteresis, so a resting pedal does not chatter. A CC is sent only when its 7-bit value changes.

</details>

## What each pedal sends

| Setting | In the CSV | What it does |
|---|---|---|
| **Expression pedal 1 CC**, **2 CC** (Global tab) | `Exp1_CC`, `Exp2_CC` | The CC each pedal sends. Defaults 11 and 4. |
| Channel | `Channel` | 1–16, or Global to use **MIDI channel** (`MIDI_Channel`) from the Global tab. |
| Curve | `Curve` | Linear, Log or Exp. Log is fast at the start of the travel, Exp is slow at the start. |
| Invert | `Invert` | Swap heel and toe. |

## Output range

A pedal can send only part of the range: 40 to 127 for a volume pedal that never goes silent, for instance, or 127 to 0 to turn it round without touching Invert.

Set the **output range** in the Expression tab (`Out_Min` and `Out_Max`, defaults 0 and 127).

- The pedal's travel, after the curve and Invert, is spread between `Out_Min` at the heel and `Out_Max` at the toe.
- The ends are always reached exactly.
- `Toe_Level` and `Heel_Level` still refer to the pedal's position, 0 to 127, whatever it sends.
- A bank can override either end; see [A different target in each bank](#a-different-target-in-each-bank).

*Firmware 0.33 or later; older firmware ignores the range.*

<details><summary>Under the hood</summary>

Stored in two bytes that were reserved in each pedal's record, bytes 11 and 12, where older tools wrote zeros: firmware 0.33 reads 0 and 0 as the full range, so older configurations are unchanged.

</details>

## Pitch Bend and 14-bit CC

A pedal can send Pitch Bend, for a whammy, or a 14-bit CC pair, with 16384 steps instead of 128, for sweeps without zipper noise on synths and plugins that read them.

Choose what it sends with **Output** in the Expression tab (`Output`: `CC`, `PitchBend` or `CC14`; default CC).

- **PitchBend** sends Pitch Bend on the pedal's channel instead of its CC.
- **CC14** sends a 14-bit CC pair: the high 7 bits on its CC and the low 7 bits on that CC plus 32, as the MIDI standard pairs them. So CC 4 goes out as CC 4 and CC 36, the high byte first.
- Both have 16384 steps instead of 128, and the pedal sends every finer step it can measure: its dead band against noise is four times narrower in these modes, and a pedal at rest still sends nothing.
- `Out_Min` and `Out_Max` keep counting from 0 to 127, and each is taken as its top 7 bits, so 64 is the middle of the bend: 64 to 127 bends up only, from the heel at rest, and 127 is the very top.
- Curve, Invert and the toe and heel levels work as before.
- A bank or an `Exp` command that sends the pedal to another CC sends that CC: as a pair when `Output` is `CC14` and the CC is below 32, which a 14-bit CC needs, and with 7 bits otherwise. So a Pitch Bend pedal can still be a volume pedal in another bank. A 14-bit CC above 31 goes out with 7 bits too.

The demo's pedal 2 sends a 14-bit CC pair, CC 4 and 36.

*Firmware 0.44 or later; older firmware ignores the setting and sends the CC.*

<details><summary>Under the hood</summary>

Stored in byte 15 of each pedal's record, 0 for CC, 1 for Pitch Bend and 2 for 14-bit CC, where older tools wrote a zero.

</details>

## Toe and heel switches

A pedal can give you two more footswitches while it keeps sending its CC: reaching the toe taps one button, returning to the heel taps another.

In the Expression tab, name a **toe** button and the level the pedal must reach for it (`Toe_Button`, `Toe_Level`, default 120), and a **heel** button and the level it must fall to (`Heel_Button`, `Heel_Level`, default 7).

- The pedal taps a button of the **current bank**, sending whatever that button is configured to send, including its toggle state and LED.
- Each direction re-arms only after the pedal moves back past its level by a margin, so resting on the edge does not retrigger.
- The levels refer to the pedal's position, whatever its output range.
- A pedal silenced in a bank still acts as a switch: its toe and heel buttons keep working.

*Firmware 0.15 or later.*

## Auto-engage

A wah that switches itself on and off, as on Fractal and Line 6 units: no stomping on the wah before using it.

Put the wah's on and off commands on a toggle button and name that button under **Auto-engage** in the Expression tab (`Auto_Button`), with how long the pedal must rest at the heel before it goes off (`Auto_Off_ms`, 10 to 2540, default 500).

- Moving the pedal up past `Heel_Level` switches the button on, just before the pedal's first value is sent.
- Resting at or below `Heel_Level` for `Auto_Off_ms` switches it off.
- The button is pressed as if by foot, so its commands, LED and display cell follow.
- It can still be pressed by hand: both directions act only on the moment the pedal leaves the heel or has rested there long enough, so a wah switched off by hand with the pedal up, or on by hand at the heel, stays as it was left.
- The button is the same in every bank, and nothing happens in a bank where it is not a toggle, so put the wah on the same button in the banks that need it.
- It works when a bank silences the pedal too.
- While an `Exp` command has the pedal somewhere else, auto-engage leaves its button alone.

In the demo, pedal 1 auto-engages button D, the WAH in bank 8 (and TRK4 in bank 1), switching it off after 600 ms at the heel.

*Firmware 0.41 or later.*

<details><summary>Under the hood</summary>

Stored in bytes 13 and 14 of each pedal's record, the button plus one and the delay in 10 ms steps, where older tools wrote zeros, which mean no auto-engage.

</details>

## A different target in each bank

The same pedal can be a wah in one bank and a volume in another, or be silent where it is not needed.

In the configurator's **Banks** tab each bank has, per pedal, a CC and a channel, each `Default` to keep the pedal's own, or `Off` for the CC to silence the pedal in that bank, and the lowest and highest value it sends there, left empty to keep the pedal's own range.

- An empty cell keeps the pedal's own setting; each end of the range is taken on its own.
- A silenced pedal still acts as a switch: its toe and heel buttons keep working.
- After a bank change the pedal is not sent to its new CC, channel or range at the position it happens to rest in; it follows the next movement.
- An [`Exp` command](06-commands.md#changing-an-expression-pedals-target) on a button can change the target again until the next bank change.

In the demo, bank 2 turns pedal 1 into a modulation wheel held between 20 and 100, and bank 7 silences it and makes pedal 2 a volume on channel 2 that never drops below 40, CC 7 and 39.

*Firmware 0.28 or later; the per bank range needs 0.33.*

<details><summary>Under the hood</summary>

Configurations written before 0.28 have nothing stored here and behave as if every cell were empty, and those written before 0.33 have no range here. The CC and channel are four bytes per bank after the setlist, erased flash (`0xFF`) keeping the pedal's own and `0x80` silencing it; the range is a table of its own after them, four bytes per bank, so their layout is unchanged.

</details>

## In the CSV

### Expression_Settings

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

### BankExpression_Settings

Optional; one row per `Bank_Number` (0–31), rows may be missing or in any order.

| Column | Values | Meaning |
|---|---|---|
| `Exp1_CC`, `Exp2_CC` | empty, 0–127 or Off | CC the pedal sends while this bank is selected. Empty keeps `Exp1_CC` / `Exp2_CC` from `Global_Settings`; Off silences the pedal in this bank. |
| `Exp1_Channel`, `Exp2_Channel` | empty or 1–16 | Channel for that pedal in this bank. Empty keeps the pedal's `Channel` from `Expression_Settings`. |
| `Exp1_Min`, `Exp1_Max`, `Exp2_Min`, `Exp2_Max` | empty or 0–127 | Values the pedal sends at the heel and at the toe in this bank. Empty keeps its `Out_Min` / `Out_Max` from `Expression_Settings`; each end is taken on its own. Firmware 0.33 or later. |

---

[← Tempo, clock, LFO and sequencer](07-tempo.md) · [Contents](README.md) · [The display →](09-the-display.md)
