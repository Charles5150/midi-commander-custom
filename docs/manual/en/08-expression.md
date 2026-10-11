# Expression pedals

**English** · [Español](../es/08-expression.md)

Two expression pedals plug into the pedal's 1/4" jacks. Each sends a CC on its own channel, with calibrated end points and a response curve; each can also be a pair of extra footswitches, switch a wah on and off by itself, and send something different in every bank. A jack can also take a [box of up to three switches](#a-box-of-switches-on-the-jack) instead of a pedal.

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
| Channel | `Channel` | 1–16, or Global to use **MIDI channel** (`MIDI_Channel`) from the Global tab. A bank's channel for the pedal, or an `Exp` command's, wins over this one, and `Global_Channel`, when set, over all of them. |
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

## Speed of the LFOs and sequences

A pedal can send no MIDI at all and set instead how fast the pedal's own modulation goes: every running [LFO](07-tempo.md#tempo-synced-lfo) and [step sequence](07-tempo.md#step-sequencer) follows it, a tremolo sweeping from slow to fast under your foot, always in time with the tempo.

Put it there in any of three ways:

- **Output** `Speed` in the Expression tab, for good;
- `Speed` as the pedal's CC in a bank, in the Banks tab (`Exp1_CC` or `Exp2_CC` in [BankExpression_Settings](#bankexpression_settings)), for that bank;
- an [`Exp` command](06-commands.md#changing-an-expression-pedals-target) with `KeyMode` `Speed`, from a button.

How it behaves:

- The heel is the slowest and the toe the fastest, and every position in between is a note division, from four bars to a sixteenth triplet, so the speed is never out of time.
- The output range narrows it: each division takes its share of 0–127, as in the table below, so `Out_Min` 37 and `Out_Max` 118 sweep from a half note at the heel to a sixteenth at the toe.
- Every LFO and sequence goes at the pedal's division, running or started while the pedal is on Speed, whatever division its own command gives. Each carries on from where it is in its cycle, only faster or slower, so the sound does not jump.
- The pedal takes over on its first movement, as on any change of target. Moving it elsewhere, by a bank change or an `Exp`, gives every LFO and sequence its own division back.
- The display shows the division for a moment, `Sp 1/8`.
- Curve, Invert, the toe and heel switches and auto-engage work as before.

| Pedal range | Division |
|---|---|
| 0–9 | `4/1` |
| 10–18 | `2/1` |
| 19–27 | `1/1` |
| 28–36 | `1/2.` |
| 37–45 | `1/2` |
| 46–54 | `1/4.` |
| 55–63 | `1/2T` |
| 64–73 | `1/4` |
| 74–82 | `1/8.` |
| 83–91 | `1/4T` |
| 92–100 | `1/8` |
| 101–109 | `1/8T` |
| 110–118 | `1/16` |
| 119–127 | `1/16T` |

In the demo's bank 6, pedal 1 sets the speed of TREM and of the arpeggio held on STRT, from `1/2` to `1/16`.

*Firmware 0.70 or later; older firmware sends the pedal's own CC instead.*

<details><summary>Under the hood</summary>

Stored in byte 15 of each pedal's record, 0 for CC, 1 for Pitch Bend, 2 for 14-bit CC, 3 for Speed, 4 for Wheel and 5 for Arrows, where older tools wrote a zero.

</details>

## Scrolling on the computer

A pedal can scroll lyrics, a score or a teleprompter on the computer, hands free: the further you press it, the faster the page goes, and back at the heel it stops. No MIDI is sent; the pedal types on the computer as the [keyboard commands](06-commands.md) do.

It scrolls in one of two ways:

- `Arrows` taps the Down arrow key. It goes to the window in front, as a keyboard would. **The one to use on a Mac.**
- `Wheel` turns a mouse wheel. It goes to the window under the mouse pointer, even if another one is in front. Good on Windows. macOS speeds a wheel up by how often it turns, so there it crawls below half way and races past it.

Put it there as Speed is put:

- **Output** `Wheel` or `Arrows` in the Expression tab, for good;
- `Wheel` or `Arrows` as the pedal's CC in a bank, in the Banks tab, for that bank: a bank for each song's lyrics;
- an [`Exp` command](06-commands.md#changing-an-expression-pedals-target) with `KeyMode` `Wheel` or `Arrows`, from a button: a toggle turns scrolling on and off.

How it behaves:

- At the heel nothing moves. From there it speeds up gently, so the first part of the travel crawls: a quarter of the way is about one step a second, half way five, and the toe twenty.
- It keeps going while the pedal stands still: leave it where the song needs it.
- A range whose toe value is below its heel value scrolls up, with the Up arrow or the wheel the other way. `Out_Min` 127 and `Out_Max` 0 scroll up at full speed.
- A smaller range caps the speed: `Out_Min` 0 and `Out_Max` 64 go up to five steps a second at the toe.
- On a Mac with natural scrolling (the default), `Wheel` goes up where it would go down elsewhere; turn the range round.
- Curve, Invert, the toe and heel switches and auto-engage work as before, and scrolling keeps the pedal from falling asleep.

In the demo's bank 5, a double press on PLAY turns pedal 1 to `Arrows`, and another gives it back its CC.

*Firmware 0.95 or later; older firmware sends the pedal's own CC instead.*

<details><summary>Under the hood</summary>

Output 4 is Wheel and 5 Arrows; in a bank or an `Exp` command, 0x84 and 0x85. The wheel is a third report on the pedal's USB keyboard, a mouse with only a wheel (report 3). A step comes every 806450 / d² ms, d being how far the pedal is from its heel value, 0–127, with nothing below 3.

</details>

## Toe and heel switches

A pedal can give you two more footswitches while it keeps sending its CC: reaching the toe taps one button, returning to the heel taps another.

In the Expression tab, name a **toe** button and the level the pedal must reach for it (`Toe_Button`, `Toe_Level`, default 120), and a **heel** button and the level it must fall to (`Heel_Button`, `Heel_Level`, default 7).

- The pedal taps a button of the **current bank**, sending whatever that button is configured to send, including its toggle state and LED.
- Each direction re-arms only after the pedal moves back past its level by a margin, so resting on the edge does not retrigger.
- The levels refer to the pedal's position, whatever its output range.
- A pedal silenced in a bank still acts as a switch: its toe and heel buttons keep working.

*Firmware 0.15 or later.*

## A box of switches on the jack

A jack needs no pedal in it: a small box of up to three footswitches plugged in instead gives the pedal three more switches, with nothing changed inside it. Set the jack's **Sends** to **Switches** (`Output` `Switches`) and say what each of the box's switches holds down: **1**–**4**, **A**–**D**, or Bank **Down** or **Up** (`Box_1`, `Box_2`, `Box_3`).

- A box switch is the pedal's own switch under another foot: held, it holds that switch down, so its short and long press lists, a double press, a momentary hold and a Bank Up held to jump all work as from the pedal itself, in the **current bank**. It stays down as long as the box's switch does: a boost, a freeze or a note held for a whole verse holds (before 1.15 it let go after 10 seconds, as a press from the computer does).
- The jack sends no MIDI of its own, and its toe and heel switches and auto-engage do not apply.
- A switch left at **None** does nothing.

**Building the box.** It is wired as an expression pedal is, so it plugs into the same jack with the same cable:

- four equal resistors, 10 kΩ say, in a chain between the two contacts the ends of a pedal's potentiometer go to;
- each switch between the third contact, the one a pedal's wiper goes to, and a joint of the chain: switch 1 to the joint nearest the heel end, switch 2 to the middle one, switch 3 to the one nearest the toe end;
- and a resistor of 100 kΩ from the wiper contact to the heel end, so that with nothing pressed the jack reads as a pedal at the heel.

Switch 1 then puts the jack a quarter of the way from heel to toe, switch 2 halfway and switch 3 three quarters, and the pedal takes the nearest level. The levels count in the calibrated travel, so **Calibrate** the jack with the box too: nothing pressed for the heel, then switch 3 held for the toe. A reading above three quarters, such as a pedal at the toe, presses nothing.

A level must read the same twice running, some 25 ms apart, before it counts, so a contact bouncing presses nothing; going from one switch to another lets the first go before the second goes down. Pressing two at once is not supported: the jack then reads somewhere in between.

To try the setting with an expression pedal instead, move it quickly to a quarter, a half or three quarters of its travel: moved slowly, it holds down each level it passes on the way.

*Firmware 1.10 or later. Tried with an expression pedal and with the pedal moved from the computer; not yet with a box.*

<details><summary>Under the hood</summary>

The jack is read as for a pedal, every 24 ms or so with both jacks in use, and the average of 16 samples is placed in the calibrated travel, 0 to 1024. The nearest of 0, 256, 512 and 768 is the level, and a reading above 896 is level 0. A level held is a press of the switch through the same queue as the virtual pedal's presses (`sw_virtual_hold`), so the switch scan sees it as a foot; unlike a press from the computer, it has no 10 second limit. Stored in the jack's calibration record: `Output` 6, and bytes 7 to 9, which a pedal uses for its toe and heel switches, hold what the box's switches press, 0–7 for 1–D, 8 for Bank Down, 9 for Bank Up, 0xFF for none.

</details>

## Auto-engage

A wah that switches itself on and off, as on Fractal and Line 6 units: no stomping on the wah before using it.

Put the wah's on and off commands on a toggle button and name that button under **Auto-engage** in the Expression tab (`Auto_Button`), with how long the pedal must rest at the heel before it goes off (`Auto_Off_ms`, 10 to 2540, default 500).

- Moving the pedal up past `Heel_Level` switches the button on, just before the pedal's first value is sent.
- Resting at or below `Heel_Level` for `Auto_Off_ms` switches it off.
- The button is pressed as if by foot, so its commands, LED and display cell follow.
- It can still be pressed by hand: both directions act only on the moment the pedal leaves the heel or has rested there long enough, so a wah switched off by hand with the pedal up, or on by hand at the heel, stays as it was left.
- The button is the same in every bank, and nothing happens in a bank where it is not a toggle, so put the wah on the same button in the banks that need it.
- It works when a bank silences the pedal too.
- While an `Exp` command has the pedal somewhere else, auto-engage leaves its button alone, and so it does while a [page](04-banks.md#second-page) is shown: its buttons are another bank's.

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
- After a bank change the pedal is not sent to its new CC, channel or range at the position it happens to rest in; it follows the next movement, unless it [sends on entering a bank](#sending-the-position-on-entering-a-bank).
- An [`Exp` command](06-commands.md#changing-an-expression-pedals-target) on a button can change the target again until the next bank change.
- An `Exp` in `Add` mode makes a pedal send [several CCs at once](06-commands.md#one-pedal-to-several-ccs), each with its own range and direction.

In the demo, bank 2 turns pedal 1 into a modulation wheel held between 20 and 100, and bank 7 silences it and makes pedal 2 a volume on channel 2 that never drops below 40, CC 7 and 39.

*Firmware 0.28 or later; the per bank range needs 0.33.*

<details><summary>Under the hood</summary>

Configurations written before 0.28 have nothing stored here and behave as if every cell were empty, and those written before 0.33 have no range here. The CC and channel are four bytes per bank after the setlist, erased flash (`0xFF`) keeping the pedal's own and `0x80` silencing it; the range is a table of its own after them, four bytes per bank, so their layout is unchanged.

</details>

## Sending the position on entering a bank

Change preset on the amp and its volume jumps to what the preset saved, while your volume pedal sits somewhere else; the two only agree again once you move the pedal. With **Send on entering a bank** ticked for a pedal in the Expression tab (`Send_On_Bank` `Y`), the pedal sends where it is as soon as a bank is entered, as on Morningstar and Fractal controllers, so the new preset takes the volume from your foot.

- It goes out after the bank's [enter commands](04-banks.md#commands-on-entering-and-leaving-a-bank), so a Program Change sent there reaches the device first.
- It goes to whatever the pedal sends in the new bank: its own CC, the bank's, an `Exp` command's from the enter list, and the CCs an `Exp` in `Add` mode gives it. On `Speed`, the LFOs and sequences take its speed at once.
- It is sent even when the new bank has the same target as the old one.
- Nothing goes out in a bank that silences the pedal, and turning a page sends nothing, as a page keeps its bank's pedals.
- Leave it off for a jack with no pedal in it: the empty jack reads as the heel, and its heel value would go out on every bank change.
- Without it, as before, the pedal follows its next movement.

On the pedal the settings are `EXP1SEND` and `EXP2SEND` in the [editor](10-editing-on-the-pedal.md). The demo leaves both off, as its jacks may be empty.

*Firmware 0.87 or later.*

<details><summary>Under the hood</summary>

The global bytes and the pedals' records being all taken, it is kept in bits 2 and 3 of global byte 35, beside `LED_Feedback` and `Link_Toggles`, for pedals 1 and 2. Older firmware leaves those bits alone and waits for the pedal to move.

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
| `Output` | CC, PitchBend, CC14, Speed, Wheel, Arrows or Switches | What the pedal sends: its CC with 7 bits, Pitch Bend, a 14-bit CC pair, nothing but the [speed of the LFOs and sequences](#speed-of-the-lfos-and-sequences), or [scrolling on the computer](#scrolling-on-the-computer); Switches for a [box of switches](#a-box-of-switches-on-the-jack) in the jack. Default CC. |
| `Send_On_Bank` | Y / N | Send the pedal's position as a bank is entered, after its enter commands. Default N. Firmware 0.87. |
| `Box_1`, `Box_2`, `Box_3` | None, 1–4, A–D, Down or Up | With `Output` Switches, the switch each of the box's switches holds down. Default None. Firmware 1.10. |

### BankExpression_Settings

Optional; one row per `Bank_Number` (0–31), rows may be missing or in any order.

| Column | Values | Meaning |
|---|---|---|
| `Exp1_CC`, `Exp2_CC` | empty, 0–127, Off, Speed, Wheel or Arrows | CC the pedal sends while this bank is selected. Empty keeps `Exp1_CC` / `Exp2_CC` from `Global_Settings`; Off silences the pedal in this bank; Speed makes it set the [speed of the LFOs and sequences](#speed-of-the-lfos-and-sequences), stored as 0x82 (firmware 0.70); Wheel and Arrows make it [scroll on the computer](#scrolling-on-the-computer), 0x84 and 0x85 (firmware 0.95). |
| `Exp1_Channel`, `Exp2_Channel` | empty or 1–16 | Channel for that pedal in this bank. Empty keeps the pedal's `Channel` from `Expression_Settings`. |
| `Exp1_Min`, `Exp1_Max`, `Exp2_Min`, `Exp2_Max` | empty or 0–127 | Values the pedal sends at the heel and at the toe in this bank. Empty keeps its `Out_Min` / `Out_Max` from `Expression_Settings`; each end is taken on its own. Firmware 0.33 or later. |

---

[← Tempo, clock, LFO and sequencer](07-tempo.md) · [Contents](README.md) · [The display →](09-the-display.md)
