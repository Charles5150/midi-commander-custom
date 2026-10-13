# Tempo, clock, LFO and sequencer

**English** · [Español](../es/07-tempo.md)

The pedal keeps a tempo of its own: tapped with your foot, set by a bank as you enter it, or followed from the host's MIDI clock. Everything that keeps time runs from it:

- the MIDI clock the pedal sends, so a delay or looper behind it follows your foot;
- the tap LED, flashing on every beat;
- the bar and beat on the display, and a count-in before a press goes;
- recorded runs of presses, played back on their beats;
- LFOs, which swing a CC up and down in time;
- step sequences, which play a CC or a note a step at a time.

Tempo commands are `Tap` commands, with an **Action** in the configurator (`KeyMode` in the CSV) saying which: `Tap`, `Clock`, `Set`, `Up`, `Down`, `Up Repeat` or `Down Repeat`, `Record`, `Playback` or `Erase` for [recorded presses](#recording-a-run-of-presses), `Out` to [tap a device's tempo](#tapping-a-devices-tempo), or `Save` to [keep the tempo you tapped](#keeping-the-tempo-you-tapped).

## Tap tempo

The button every delay player wants: tap it in time and the pedal picks up the tempo.

Give a button a `Tap` command with **Action** `Tap`. The pedal measures the tempo from the interval between presses, averaging the last four and ignoring anything outside 30–300 BPM. The new tempo shows on the display for a moment.

The tempo is not saved: it starts at 120 BPM each time the pedal is switched on, unless a bank's [`Set`](#setting-the-tempo) on entry puts it elsewhere, and a [`Save`](#keeping-the-tempo-you-tapped) keeps a tapped tempo in that `Set`. A restart after a lock-up keeps the tempo it had.

## MIDI clock

A `Tap` command with **Action** `Clock` starts or stops the pedal's MIDI clock: MIDI Start or Stop, and then 24 clock bytes per quarter note to USB and DIN while it runs. The tempo shows on the display for a moment, with a leading `*` while the clock is running.

The DIN output sends about one message a millisecond, so a bank sending many commands on entry keeps it busy for a while: 80 messages take about 77 ms. The clock does not wait behind them. Each clock byte goes out ahead of whatever is queued, within a millisecond, as MIDI allows a clock byte between any two bytes. Start, Continue and Stop keep their place in the queue, so a `Song` select sent before a Start still arrives first, and the clocks wait behind a Start that is still queued.

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

### Keeping the tempo you tapped

A tempo tapped at rehearsal can stay with the song. A `Tap` command with **Action** `Save` writes the tempo the pedal is at into the bank's commands on entry, so the next time you step on that bank, or on that song of a setlist, it starts there: nothing to type into the configurator afterwards.

- It changes the first `Set` among the bank's commands on entry. If there is none, the first empty command among them becomes one, so put a `Set` where you want it, or leave a slot free.
- Only the commands above a `Leave` count, the ones sent on entering.
- The display says `SAVED`, with the tempo. When there is neither a `Set` nor an empty command, it says `NOT SAVED` and nothing changes.
- It is written to the flash of the configuration slot, as a [Scene Save](05-buttons.md#scenes) is, and kept after a power cycle. Reading the configuration back into a configurator shows it.

A long press of the tap button is the natural place. In the demo, holding TAP in bank 6 saves the tempo; TAP has **Press at once** ticked, so the tap still goes out as the switch goes down.

*Firmware 1.26 or later.*

<details><summary>Under the hood</summary>

Stored as low nibble 9 of the `Tap` command, the other bytes 0. It writes `72 00 <BPM low 7 bits> <BPM high bits>` over the `Set` or the empty command, in the active slot's flash. Firmware before 1.26 takes it as a plain tap.

</details>

## Tapping a device's tempo

Plenty of gear takes its tempo from a tap CC and not from MIDI clock, or is set to ignore the clock: a Kemper (CC 30), an HX Stomp (CC 64), a Quad Cortex (CC 44), a Strymon (CC 93). `Tap Out` taps it for you, at the pedal's tempo.

Put a `Tap` command with **Action** `Out` right above the device's tap CC, its tap number with its on value, and that CC becomes the device's tap:

- It goes out on the next **Taps** beats, 4 when empty (`OnValue`), from the next beat on, so the first two are a whole beat apart and the device reads the tempo right.
- And again after every change of tempo while you stay in the bank: a `Set`, `Up` or `Down`, or your taps on the pedal's own `Tap` button. A tap on the pedal is a beat, so the device is tapped with your foot, then for as many beats more.
- With **Taps** at 0 it goes out on every beat, until the bank changes.
- Leaving the bank stops it, and so do a [Panic](06-commands.md#panic) and a switch to another configuration; a bank's second page does not. On a button it starts as the button fires; with a toggling CC, switching the button off stops it.
- The beats are the ones the [tap LED](#tap-led) flashes on: the pedal's tempo, its running clock, or the host's clock with `Clock_Follow` on. The tap goes to USB and DIN, as a CC does.

In a bank's [commands on entry](04-banks.md#commands-on-entering-and-leaving-a-bank), below a `Set`, every song puts the device on its tempo as you step on it. Don't give the pedal's own `Tap` button the device's CC as well: `Tap Out` passes your taps on already.

The demo's bank 6 taps CC 64 on channel 3 four times on entering, and again after TAP, BPM+, BPM- or holding SYNC.

*Firmware 1.25 or later.*

<details><summary>Under the hood</summary>

Low nibble 8 of the `Tap` command, with the number of taps in byte 2, and it works on the CC command right below it, like a `Ramp` or an `LFO`; firmware before 1.25 takes it as a plain tap. Up to four devices can be tapped at once. A beat less than half a beat after the last tap sent is passed over, so a tap on the pedal right on the beat reaches the device once.

</details>

## Following the host's clock

When a DAW or a sequencer runs the show, the pedal can take its tempo from the host instead. Tick **Follow the host's clock** in the **Global** tab, `Clock_Follow` in the CSV.

- The pedal measures MIDI clock arriving over USB, over two beats, and adopts its tempo. The display shows it as `EXT` and a tempo for 1.5 seconds when the clock is picked up, or when its tempo changes by two BPM or more.
- While that clock keeps arriving the pedal sends no clock of its own. With `RealTime_Passthrough` on, the host's clock already reaches the DIN output; with it off, the pedal re-clocks the DIN output at the host's tempo.
- Half a second without a clock counts as stopped, and the pedal's own clock, if running, carries on at the adopted tempo, so a looper behind it keeps time.

See [`Clock_Follow`](12-configuration-file.md#global_settings) in the settings. A [`Wait` on the beat](06-commands.md#on-the-beat) counts its bars from the host's Start, or from its Song Position on a Continue.

## Bar and beat on the display

On stage with a looper or a DAW, you want to know where the one is without looking at a screen off stage. Choose how many beats a bar has in **Bar and beat on the display** in the **Global** tab (`Beat_Counter` in the CSV, 1 to 15, `Off` to leave it out), and while a clock runs the bank's info line gives way to the bar, the beat and the tempo: `12.3 120` is the third beat of bar 12, at 120 BPM.

- It shows while the pedal's own clock runs, counted from its Start, and while the host's clock plays with `Clock_Follow` on, from the host's Start, or from its Song Position on a Continue, so the bar numbers are the song's. Between the host's Stop and its next Start or Continue it is gone, even if the host keeps its clock running.
- With no clock running there is no bar to count, and the bank's own info shows.
- A text the computer sends to the info line, or a readout such as the tempo, shows over it as usual.
- A [count-in](06-commands.md#on-the-beat) (`Wait` `Count`) counts its beats down in large type where the bank's name was, `IN 4` to `IN 1`, whether `Beat_Counter` is on or not.

In the demo it is on, in bars of 4: in bank 6, press CLK to start the clock and watch it count; hold CLK for a count-in before CC 21.

*Firmware 0.88 or later.*

<details><summary>Under the hood</summary>

`Beat_Counter` is the top four bits of global byte 35, beside `LED_Feedback`, `Link_Toggles` and the two pedals' `Send_On_Bank` in the bottom four. Older firmware ignores them.

</details>

## Recording a run of presses

A song whose changes come on the same bars every night: the drive on at bar 9, the delay off at bar 25, the looper on the one of the chorus. Play it once with the clock running and the pedal keeps on which beat each switch went down; from then on, whenever the clock runs in that bank, it presses them itself on those beats, and your feet are free for the rest.

- **Record** (`Tap` with **Action** `Record`) arms the bank it is pressed in: `REC WAIT` on the display. The recording begins on the clock's first beat, or at once with the clock running already, `REC`. Every press of the bank's eight buttons is kept with the beat nearest to where it went down, how long it was held, and whether it was a long or a double press.
- It ends, and is kept, when the clock stops, when you press **Record** again, or when you leave the bank or the configuration: `SAVED` and the number of presses. A press still held then, such as the one that ended it, is left out. With nothing pressed, `REC NONE`, and the bank keeps the recording it had.
- **Playback.** Whenever the clock runs in a bank with a recording, from its Start, or from wherever the host's Continue picks up, the pedal presses each button on its beat, as a foot would: its commands, LED, toggle and display cell follow, a long press is held past the threshold and a double press tapped twice, whatever the tempo, and a held one is let go after as many beats as it was held. Leaving the bank, or the clock stopping, stops it, and nothing plays back while the on-pedal editor is open. Your feet still work as ever on top of it.
- A **Playback** button (`Playback`) switches playing back off, `PLAY OFF`, and on again, `PLAY ON`, for every bank. It starts on whenever the pedal is switched on.
- An **Erase** button (`Erase`) drops the recording of the bank it is pressed in: `ERASED`, or `NO REC` with none.
- A bank keeps one recording, made over again by recording it again. Each configuration slot has its own, by bank number, and they stay when the slot is written again, until erased.
- The clock is the pedal's own, or the host's with `Clock_Follow` on, counted as the [bar and beat on the display](#bar-and-beat-on-the-display) are, from its Start. A Record button's LED flashes on the beat while it records or waits to.
- Up to 128 presses a recording, and about 300 in all, in a page of flash of their own: `REC FULL` when a recording takes no more, `NO ROOM` when there is no room left for it. Making room rewrites the page, which holds the pedal up for a moment, so with the clock running that waits until it stops.

In the demo, every song bank of the setlist records: hold TAP for **Record**, hold UNDO for **Erase** and STOP for **Playback**. Run the clock from the computer, or from bank 6's CLK.

*Firmware 1.24 or later.*

<details><summary>Under the hood</summary>

`Record`, `Playback` and `Erase` are low nibbles 5, 6 and 7 of the `Tap` command, with the other bytes 0; firmware before 1.24 takes them as a plain tap. The recordings are a log in the flash page at `0x0803F800`, which nothing else writes, the tools and a firmware update included: per entry its number of presses, bank, slot and a marker written last, then six bytes a press, its beat, how long it was held in clocks, and the button, double press and kind of hold. The latest entry of a slot and bank is its recording, one of no presses an erased one. A press is played back through the same virtual switches the configurator presses.

</details>

## Tap LED

The tap button's LED flashes on every beat, so you can see the tempo from the floor.

- Every button of the current bank with a `Tap` command in `Tap` mode, in any of its lists, flashes its LED at the start of each beat, for a quarter of a beat and at most 100 ms, at the `LED_Brightness` level.
- A `Clock` button flashes the same way, but only while the clock is running, so its LED also tells you the clock is on. A `Record` button flashes while it records or waits to.
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
- An expression pedal can set the speed with your foot instead: see [Speed of the LFOs and sequences](08-expression.md#speed-of-the-lfos-and-sequences).
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
- An expression pedal on Speed sets how long a step lasts, as it does an LFO's cycle: see [Speed of the LFOs and sequences](08-expression.md#speed-of-the-lfos-and-sequences).
- Four sequences can run at once. They keep running when the bank changes, and the toggled ones start again after switching the pedal off and on.
- A `Ramp` or an `LFO` on the same channel and CC gives way to a sequence. `Panic` and a configuration switch stop them all.

Held, the demo's STRT in bank 6 plays a four note arpeggio.

*Firmware 0.52 or later.*

<details><summary>Under the hood</summary>

`Seq` is marked by the low nibble of the empty command type, 10, with the division in byte 1 and the two steps in bytes 2 and 3, `0xFF` where the sequence ends, so the layout is unchanged. Firmware before 0.52 ignores the `Seq` commands and sends the command below them as usual.

</details>

---

[← Commands](06-commands.md) · [Contents](README.md) · [Expression pedals →](08-expression.md)
