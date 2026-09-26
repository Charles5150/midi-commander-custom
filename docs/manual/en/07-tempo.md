# Tempo, clock, LFO and sequencer

The pedal keeps a tempo of its own: tapped with your foot, set by a bank as you enter it, or followed from the host's MIDI clock. Everything that keeps time runs from it:

- the MIDI clock the pedal sends, so a delay or looper behind it follows your foot;
- the tap LED, flashing on every beat;
- LFOs, which swing a CC up and down in time;
- step sequences, which play a CC or a note a step at a time.

Tempo commands are `Tap` commands, with an **Action** in the configurator (`KeyMode` in the CSV) saying which: `Tap`, `Clock`, `Set`, `Up`, `Down`, `Up Repeat` or `Down Repeat`.

## Tap tempo

The button every delay player wants: tap it in time and the pedal picks up the tempo.

Give a button a `Tap` command with **Action** `Tap`. The pedal measures the tempo from the interval between presses, averaging the last four and ignoring anything outside 30–300 BPM. The new tempo shows on the display for a moment.

The tempo is not saved: it starts at 120 BPM each time the pedal is switched on.

## MIDI clock

A `Tap` command with **Action** `Clock` starts or stops the pedal's MIDI clock: MIDI Start or Stop, and then 24 clock bytes per quarter note to USB and DIN while it runs. The tempo shows on the display for a moment, with a leading `*` while the clock is running.

The demo's bank 6 has tap tempo, clock start and stop, and transport buttons side by side.

## Setting the tempo

Each song has its tempo. Put a `Tap` command with **Action** `Set` in a bank's [commands on entry](04-banks.md#commands-on-entering-and-leaving-a-bank) and each bank, or each song of a setlist, starts at its own tempo; on a button, it is a reset to a known tempo.

| Action | What it does | Value |
|---|---|---|
| `Set` | Sets the tempo | **BPM**, 30–300, 120 when empty (`OnValue`) |
| `Up`, `Down` | Moves the tempo, stopping at 30 and 300 | **Step** in BPM, 1 when empty (`OffValue`) |
| `Up Repeat`, `Down Repeat` | The same, and keeps moving while the button is held, faster and faster, as described under [Repeat while held](06-commands.md#repeat-while-held) | **Step**, as above |

- All of them show the new tempo on the display, and a running clock and the tap LED follow it at once.
- While `Clock_Follow` is following the host's clock, the host's tempo wins.
- These buttons do not flash with the beat.

The demo's bank 6 has BPM+ and BPM- on C and D, and holding SYNC sets 120 BPM.

*Firmware 0.37 or later.*

<details><summary>Under the hood</summary>

Stored in the low nibble of the `Tap` command: 2 for `Set`, with the BPM in bytes 2 (low 7 bits) and 3 (the rest); 3 for `Up` and 4 for `Down`, with the step in byte 2 and its top bit set to repeat. Firmware before 0.37 takes all three as a plain tap, so update the firmware first.

</details>

## Following the host's clock

When a DAW or a sequencer runs the show, the pedal can take its tempo from the host instead. Tick **Follow the host's clock** in the **Global** tab, `Clock_Follow` in the CSV.

- The pedal measures MIDI clock arriving over USB, over two beats, and adopts its tempo. The display shows it as `EXT` and a tempo for 1.5 seconds when the clock is picked up, or when its tempo changes by two BPM or more.
- While that clock keeps arriving the pedal sends no clock of its own. With `RealTime_Passthrough` on, the host's clock already reaches the DIN output; with it off, the pedal re-clocks the DIN output at the host's tempo.
- Half a second without a clock counts as stopped, and the pedal's own clock, if running, carries on at the adopted tempo, so a looper behind it keeps time.

See [`Clock_Follow`](12-configuration-file.md#global_settings) in the settings.

## Tap LED

The tap button's LED flashes on every beat, so you can see the tempo from the floor.

- Every button of the current bank with a `Tap` command in `Tap` mode, in any of its lists, flashes its LED at the start of each beat, for a quarter of a beat and at most 100 ms, at the `LED_Brightness` level.
- A `Clock` button flashes the same way, but only while the clock is running, so its LED also tells you the clock is on.
- The beat it flashes depends on where the tempo comes from:
  - with the clock stopped, the beat runs freely at the tempo and every tap re-phases it, so the flash lands with your foot;
  - with the clock running, the flash is the first of every 24 clock bytes, starting from Start;
  - while `Clock_Follow` is following the host's clock, it is the host's beat, counted from its Start.
- The flash sits on top of whatever the LED shows, so a Reverse or AlwaysOn LED lit at rest as bright as `LED_Brightness` shows no flash: set **Brightness at rest** (`LED_Rest_Brightness`) lower to see it.
- It stops while the pedal sleeps.

**Any button can flash with the beat**, whatever its commands are: tick **Flash at the tempo** in the configurator's button editor, or set `Tempo_Flash` to `Y` in the CSV. It flashes at all times, like a `Tap` button, since it is your choice rather than the clock's. The demo's bank 6 button B, SYNC, a plain CC toggle, uses it.

*Firmware 0.36 or later; **Flash at the tempo** 0.48 or later.*

<details><summary>Under the hood</summary>

`Tempo_Flash` is bit 2 of the button's LED mode byte, which configurations have always left at zero. Firmware before 0.48 ignores it.

</details>

## Tempo-synced LFO

A tremolo, a filter sweep or an auto-pan that follows your tap or the host's clock. An `LFO` command sends nothing itself: it turns the `CC` command right below it into an LFO. While the button is held, or while a toggle is on, the CC swings by itself between its `OffValue` and its `OnValue`.

In the configurator, put an `LFO` command above a `CC` and choose:

- **Every**, the length of one cycle (`OnValue` of the `LFO`), a note division: `1/16T`, `1/16`, `1/8T`, `1/8`, `1/4T`, `1/8.`, `1/4`, `1/2T`, `1/4.`, `1/2`, `1/2.`, `1/1`, `2/1` or `4/1`, where `.` is dotted and `T` a triplet. `1/4` when empty.
- **Shape** (`KeyMode`): `Sine`, `Triangle` and `SawUp` start at the bottom, `SawDown` and `Square` at the top, and `Random` jumps to a new value on every cycle. `Sine` when empty.

How it behaves:

- The LFO is locked to the beat the tap LED flashes, the host's clock while it is followed ([Clock_Follow](12-configuration-file.md#global_settings)). Cycles start on a beat, counted from the beat of the press, and a new tap, tempo or clock is followed straight away, so a `1/8` tremolo on a toggle is always in time with the delay.
- On the release, or the press that switches the toggle off, the LFO stops and the CC gets its `OffValue` as usual.
- A CC with no off value swings from 0. Setting `OnValue` below `OffValue` turns the shape upside down.
- It sends a message at most every 5 ms and only when the value changes. Eight LFOs can run at once.
- An LFO keeps running when the bank changes, like any CC a button leaves on, and the toggled ones start again after switching the pedal off and on.
- A `Ramp` on the same channel and CC takes over from an LFO, and the other way round; a step sequence on it takes over too. `Panic` and a configuration switch stop them all.

The demo's bank 6 has TREM on A, a `1/8` sine tremolo on CC 14.

*Firmware 0.43 or later.*

<details><summary>Under the hood</summary>

Like `Wait`, an `LFO` is marked by the low nibble of the empty command type, 6, with the division's index in byte 2 and the shape's in byte 3. Firmware before 0.43 ignores the `LFO` and sends the CC as usual.

</details>

## Step sequencer

The same idea a step at a time: a stuttered filter, an arpeggio, a pattern of amp switches, all in time. A run of `Seq` commands above a `CC` or `Note` command plays that command one step at a time while the button is held, or while a toggle is on, round and round until it is let go.

In the configurator, put the `Seq` commands above the `CC` or `Note` and fill in:

- **Steps** (`OnValue`): two steps per `Seq` command, such as `100 -`. A longer sequence is several `Seq` commands one after the other, up to nine above the command they play, eighteen steps in all. A step is a value 0–127, or `-` for a step that sends nothing, so rests are part of the rhythm.
- **Every** (`KeyMode` of the first command of the run): how long a step lasts, the same note divisions as the LFO, `1/8` when empty.

What a step means depends on the command below:

- under a `CC`, the value is what the controller gets;
- under a `Note`, it is the note played, with the command's `Velocity`, and each step lets the note before it go — an arpeggio.

How it behaves:

- Like the LFO it is locked to the beat the tap LED flashes, the host's clock while it is followed: the first step falls on the beat of the press, and a new tap or tempo is followed straight away.
- On the release, or the press that switches the toggle off, the sequence stops, a CC gets its `OffValue` as usual and a sounding note is let go.
- Four sequences can run at once. They keep running when the bank changes, and the toggled ones start again after switching the pedal off and on.
- A `Ramp` or an `LFO` on the same channel and CC gives way to a sequence. `Panic` and a configuration switch stop them all.

Held, the demo's STRT in bank 6 plays a four note arpeggio.

*Firmware 0.52 or later.*

<details><summary>Under the hood</summary>

`Seq` is marked by the low nibble of the empty command type, 10, with the division in byte 1 and the two steps in bytes 2 and 3, `0xFF` where the sequence ends, so the layout is unchanged. Firmware before 0.52 ignores the `Seq` commands and sends the command below them as usual.

</details>

---

[← Commands](06-commands.md) · [Contents](README.md) · [Expression pedals →](08-expression.md)
