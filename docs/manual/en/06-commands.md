# Commands

**English** · [Español](../es/06-commands.md)

What a button can send. Every list — a button's short, long and double press, a bank's commands on entering and leaving, and the bank switches' — holds up to ten commands, sent in order, top to bottom.

![A command list with a pause, a ramp, a condition and a macro](../images/command-list-en.svg)

In the configurator a list is ten slots, A to J. Choose a slot's command type and only the fields that type uses appear. In the CSV each slot is a group of columns, prefixed `A_` to `J_`; the [Command fields](#command-fields) table at the end of this chapter lists them all. When a command sends its "off" — on release, after a time or on the next press — is explained in [Buttons](05-buttons.md).

## Every command at a glance

| `CommandType` | What it does | Where |
|---|---|---|
| `PC` | Program Change, with an optional Bank Select | [Program Change](#program-change) |
| `CC` | Control Change | [Control Change](#control-change) |
| `Note` | Note On, and Note Off to let it go | [Notes](#notes) |
| `PB` | Pitch Bend | [Pitch Bend](#pitch-bend) |
| `SysEx` | One of sixteen stored SysEx messages | [Custom SysEx](#custom-sysex) |
| `Start`, `Stop` | MIDI Start and Stop | [Start and Stop](#start-and-stop) |
| `MMC` | The transport of a recorder or a DAW | [Driving a recorder or a sequencer](#driving-a-recorder-or-a-sequencer) |
| `Song` | Song Select or Song Position | [Song Select and Song Position](#song-select-and-song-position) |
| `Panic` | All Sound Off and All Notes Off everywhere | [Panic](#panic) |
| `CCInc` | A CC that moves up or down a step on each press | [Relative CC](#relative-cc) |
| `PCInc` | The next or previous preset | [Next and previous preset](#next-and-previous-preset) |
| `Key` | A key of a computer keyboard | [Keyboard keys](#keyboard-keys) |
| `Media` | A media key: play, next, volume… | [Media keys](#media-keys) |
| `Chan` | Sends the command below on several channels | [One channel, or several](#one-channel-or-several) |
| `Wait` | A pause in the list | [Pauses](#pauses) |
| `Ramp` | Turns the CC below into a slow walk to its value | [CC ramps](#cc-ramps) |
| `Exp` | Changes what an expression pedal sends | [Changing an expression pedal's target](#changing-an-expression-pedals-target) |
| `Value` | Sets or counts one of the pedal's eight values | [Values and conditions](#values-and-conditions) |
| `If` | Holds back the command below unless a test holds | [Values and conditions](#values-and-conditions) |
| `Macro` | Runs another button's list in place | [Macros](#macros) |
| `Tap` | Tap tempo, the MIDI clock, setting or nudging the tempo | [Tempo](07-tempo.md#tap-tempo) |
| `LFO` | Makes the CC below swing in time | [Tempo](07-tempo.md#tempo-synced-lfo) |
| `Seq` | Plays the CC or note below as a step sequence | [Tempo](07-tempo.md#step-sequencer) |
| `Bank` | Changes bank, goes back, shows a second page or switches configuration | [Banks](04-banks.md#buttons-that-change-bank) |
| `Scene` | Puts the bank's toggles into a chosen combination | [Buttons](05-buttons.md#scenes) |
| `Cycle` | Splits a short press list into states, one per press (short press only) | [Buttons](05-buttons.md#cycle-buttons) |
| `Leave` | Splits a bank's list into entering and leaving (a bank's enter list only) | [Banks](04-banks.md#commands-on-leaving-a-bank) |
| empty | No command | |

## Sending MIDI

Everything in this group goes out over USB and the DIN output at once.

### Program Change

Selects a patch. `Channel` is the MIDI channel, 1–16, and `Number` the program, 0–127.

For devices with more than 128 patches, `BankSelect` puts a Bank Select in front of the Program Change, 0–16383: it goes out as CC#32, the low byte, before the PC. With `BankSelectHighByte` set to `Y`, CC#0, the high byte, goes out too, so the value is 128 times the high byte plus the low one. The [FM3 template](11-devices.md#fractal-audio-fm3-template) uses it to reach the FM3's banks B to D.

Leave `BankSelect` empty and no Bank Select is sent at all; an explicit `0` sends one.

<details><summary>Under the hood</summary>

Until the tools of firmware 0.17, an empty Bank Select was packed as a 0, so every Program Change sent an unwanted Bank Select LSB of 0, which selects a bank on devices that listen to it. It was a tooling fix: a configuration flashed with older tools has to be flashed again to lose it.

</details>

### Control Change

`Channel` is the channel, `Number` the controller, `OnValue` the value sent on the press, 0–127, and `OffValue` the value sent on the release, or when a toggle is switched off. With `Toggle` set to `Y` the button alternates between the two on successive presses, and its LED shows which. A CC ignores `Duration`. Leave `OffValue` empty for a CC that has no off value and only ever sends `OnValue`.

### Notes

`Channel` is the channel, `Number` the note and `Velocity` its velocity, 0–127. The note is let go with a Note Off on the release, after `Duration` if one is set, in steps of 10 ms up to 1.27 s even if the button is still held, or on the next press with `Toggle`.

### Pitch Bend

`Channel` is the channel and `OnValue` the bend, −8192 to 8191. The bend goes back to the centre on the release, after `Duration` if one is set, or on the next press with `Toggle`, in the same way as a note.

### Start and Stop

`Start` and `Stop` take no fields: they send MIDI Start (0xFA) and Stop (0xFC), to set a drum machine or a sequencer going and stop it again. For the pedal's own MIDI clock, see [Tap tempo](07-tempo.md#tap-tempo).

### Custom SysEx

For a device that is only controllable through SysEx. `CommandType` `SysEx` sends one of the sixteen messages stored in the configuration's [`SysEx_Strings`](#sysex_strings); `Number` says which, 0 to 15, and nothing else in the command is used.

*Firmware 0.13 or later.*

### SysEx_Strings

The messages themselves, edited in the configurator's **SysEx** tab, which shows the byte count, or a warning, as you type.

- In the CSV the section is optional: sixteen rows, each with an `Index`, 0–15, and its `Bytes`.
- Write the bytes in hexadecimal as the device's manual shows them, separated by spaces or commas, with or without a `0x` in front.
- The leading `F0` and trailing `F7` are optional: they are added when sending.
- Up to 23 data bytes, each `00`–`7F`.
- A line that cannot be read is stored empty, and a command that points at it sends nothing, rather than a malformed message.

### Driving a recorder or a sequencer

The transport of a DAW, a hard disk recorder or a drum machine, from your foot. `CommandType` `MMC` sends a MIDI Machine Control message to every device on the wire.

`KeyMode` is the action:

| `KeyMode` | What it does |
|---|---|
| `Play` (or empty), `Stop`, `Pause` | The transport |
| `Record`, `RecordExit` | A record strobe, the punch in, and the punch out |
| `FastForward`, `Rewind` | Wind forward or back |
| `Locate` | Go to the time in `OnValue`, in seconds from the start, up to 16383 (4h33m) |
| `DeferredPlay`, `Chase`, `Eject`, `Reset` | The rest of the MMC set |

A `Locate` goes out as a timecode of hours, minutes and seconds with the frames at zero, so `3725` is 1:02:05. MMC is one way here: nothing comes back, and the pedal does not follow a recorder's position.

<details><summary>Under the hood</summary>

Stored like a `Wait`, by the low nibble of the empty command type, 7, with the MMC command byte in byte 1 and the seconds in bytes 2 and 3. Older firmware ignores it.

</details>

*Firmware 0.50 or later.*

### Song Select and Song Position

To pick what a drum machine or a hardware sequencer plays. `CommandType` `Song`:

- `KeyMode` `Select` sends a Song Select (0xF3) with the song number in `OnValue`, 0–127: the song, pattern or sequence to play.
- `KeyMode` `Position` sends a Song Position Pointer (0xF2) instead, `OnValue` being where in the song to start, counted in sixteenth notes: 16 to a 4/4 bar, 0 for the top. A device usually waits there for the next Start or Continue.

Neither message belongs to a MIDI channel, so there is no `Channel` to set. Put a `Select` in a bank's commands on entry and the recorder follows your setlist.

<details><summary>Under the hood</summary>

Stored by the low nibble of the empty command type, 8: byte 1 says which message, bytes 2 and 3 the value. Older firmware ignores both, as it does an `MMC`.

</details>

*Firmware 0.50 or later.*

### Panic

For the stuck note or runaway sound in the middle of a set. `CommandType` `Panic` takes no fields and sends All Sound Off (CC 120) and All Notes Off (CC 123) on all sixteen channels.

It does not reset toggle states or controllers, but it does stop every [CC ramp](#cc-ramps). A long press is a good place for it, where it cannot be hit by accident; the demo puts it on a long press of STOP in the tempo bank.

<details><summary>Under the hood</summary>

The 32 messages go out packed into two USB packets and two serial buffers, so a panic cannot itself run out of transmit buffers.

</details>

*Firmware 0.21 or later.*

## Stepping values

### Relative CC

For setting a parameter with your foot: a button that nudges a CC up or down a step on each press, instead of sending a fixed value. `CommandType` `CCInc`:

| Field | Meaning |
|---|---|
| `Number` | The CC |
| `OnValue` | The value it starts from at power on |
| `OffValue` | The step |
| `KeyMode` | The direction: `Up` or `Down`, or `Up Repeat` or `Down Repeat` to keep going while held (see [Repeat while held](#repeat-while-held)) |
| `Toggle` | `Y` to wrap round past the ends instead of stopping at 0 and 127 |

The running value lives in memory, one per command slot, and goes back to the start value when the pedal is switched off.

*Firmware 0.13 or later.*

### Next and previous preset

A button that steps the Program Change up or down from wherever the device is. `CommandType` `PCInc` sends a Program Change one step on from the program last selected on its channel: whatever was sent last on the channel, by any PC command, by the commands of a bank being entered, or by the computer over USB. So the button always moves on from where the device really is; before anything has been sent it counts as program 0.

| Field | Meaning |
|---|---|
| `Channel` | The channel |
| `KeyMode` | The direction: `Up` or `Down`, or `Up Repeat` or `Down Repeat` to keep going while held |
| `OffValue` | The step, 1 when empty |
| `Number` | The last program of the range, 0 to 127, 127 when empty; a Line 6 HX Stomp, for instance, has 0 to 125 |
| `Toggle` | `Y` to wrap round at the ends instead of stopping there |

- The last program is shared, so a Next and a Previous button work as a pair.
- It is not kept across a power cycle.
- No Bank Select is sent.
- The new number shows on the display for a moment, as `PC 6`.

The demo puts PREV and NEXT on C and D of the program change bank, which sends PC 0 when entered.

<details><summary>Under the hood</summary>

Stored as a PC whose Bank Select MSB byte, where 0x80 and above already meant none, holds 0x81 for up or 0x82 for down; the step is in byte 1 and the last program in byte 3, with its top bit for wrapping.

</details>

*Firmware 0.31 or later.*

### Repeat while held

Like a key on a computer keyboard: hold the button and it keeps going. With `KeyMode` `Up Repeat` or `Down Repeat`, a `CCInc` or `PCInc` command, or a `Tap` stepping the tempo, fires once on the press, again after half a second, then every 200 ms, each gap a quarter shorter than the one before, down to one every 50 ms. A CC value can cross its whole range in about three seconds with a step of 2, while a tap still moves it a single step.

- Only the repeating commands of the list fire again, and they skip any `Wait`.
- A repeat that has hit an end and cannot move any further sends nothing, so a held button does not keep resending 127.
- Holding a button that has long press commands makes a long press, so its short list cannot repeat. Its long press list can, and so can a double press list while the second press is held.

<details><summary>Under the hood</summary>

Stored as the top bit of the step byte for `CCInc`, and as the markers 0x83 for up and 0x84 for down, in place of 0x81 and 0x82, for `PCInc`. Older firmware ignores the repeat on `CCInc`, but sends a repeating `PCInc` as an ordinary, wrong, Program Change, so update the firmware first.

</details>

*Firmware 0.35 or later.*

## Computer keys

These go to the computer over USB as a keyboard would, not as MIDI, so they work in any program without MIDI mapping.

### Keyboard keys

`CommandType` `Key` presses a key of a computer keyboard: to turn a page in a score, start a recording, or anything a program has a shortcut for.

| Field | Meaning |
|---|---|
| `OnValue` | The key: a single character (`a`, `7`) or one of `enter`, `esc`, `tab`, `space`, `backspace`, `minus`, `equal`, `leftbr`, `rightbr`, `backslash`, `semicolon`, `quote`, `grave`, `comma`, `dot`, `slash`, `f1`–`f12` |
| `Number` | The modifiers, added up: 1 Ctrl, 2 Shift, 4 Alt, 8 Cmd/Win, so 3 is Ctrl+Shift |
| `KeyMode` | `Normal` taps the key, held for `Duration` if set. `Down` presses it and leaves it pressed, `Up` releases it, both after waiting `Duration`, so one button can build a combination across several slots. The wait holds back the commands below it, like a [`Wait`](#pauses), while the rest of the pedal keeps going |
| `Toggle` | `Y` holds the key until the next press |

### Media keys

`CommandType` `Media` sends one of the keys a keyboard's media buttons send, so it works in any player or DAW.

- `OnValue` is one of `play_pause`, `play`, `pause`, `stop`, `next`, `prev`, `record`, `fast_forward`, `rewind`, `eject`, `mute`, `vol_up`, `vol_down`, or a raw usage number (`0xE9`).
- The key is pressed on the press and released on the release; held for `Duration` if one is set; or held until the next press with `Toggle`.
- `Number` and `Channel` are not used.

*Firmware 0.10 or later.*

## Channels

### One channel, or several

Two settings cover a rig that does not live on the channel the configuration was written for.

**Everything on one channel.** `Global_Channel`, in the [global settings](12-configuration-file.md#global_settings), moves everything: while it is set to a channel, every message the pedal sends goes out on it, whatever each command stores, the expression pedals included. A configuration written for channel 1 then drives a device listening on channel 9 without touching a single command.

**One command on several channels.** `CommandType` `Chan` goes the other way, for one command: it names channels in `Channel`, as `1 2 3` or `1-3`, and the command right below it is sent once on each of them. One press mutes three devices, or three amps change patch together.

- Naming channels is on purpose, so a `Chan` beats the global channel: a `Chan 3` above a command keeps it on channel 3 while the rest of the configuration moves.
- Like a `Ramp`, a `Chan` only reaches the command directly below it.
- It counts for the release too, so a momentary CC goes off on every channel it went on.

In the demo, holding A in bank 11 mutes channels 1, 2 and 3 with one CC.

<details><summary>Under the hood</summary>

`Chan` is stored by the low nibble of the empty command type, 9, with the sixteen channels as a bit each: byte 2 for channels 1–7, byte 3 for 8–14 and the two low bits of byte 1 for 15 and 16. The global channel is byte 41 of the global settings, 0 meaning off. Older firmware ignores both a `Chan` and the setting.

</details>

*Firmware 0.51 or later.*

## Shaping a list

These send nothing themselves: they change when, whether or how the commands around them go out.

### Pauses

For the device that drops a Control Change arriving right behind a Program Change, or a chain the other end cannot swallow at once. `CommandType` `Wait` pauses the commands that follow it in the list; `Duration` is the pause in milliseconds, in steps of 10, up to 2550.

- The pedal does not stop to count: the rest of the list is picked up once the time is up, and meanwhile other buttons, the expression pedals and the display keep working.
- A button released while its list is still waiting has its release, the note off or the momentary off, held back until the list finishes, so nothing is switched off before it has been sent.
- Pressing the same button again first sends whatever was left, without its pauses.
- Pauses work in every list: short, long and double press, a bank's commands on entry, and the bank switches.
- Four lists can be waiting at once, which is more than a foot can start; beyond that the pauses are skipped rather than queued.

<details><summary>Under the hood</summary>

Older firmware sends the rest of the list without pausing.

</details>

*Firmware 0.30 or later.*

### CC ramps

A volume swell or a slow filter sweep from a single press. `CommandType` `Ramp` turns the `CC` command right below it into a ramp: instead of jumping to its value, the CC walks there over `Duration` milliseconds, in steps of 10, up to 655350, almost 11 minutes.

- On the press it walks to `OnValue`; on the release, or on the press that switches a toggle off, it walks back to `OffValue`.
- It starts from the command's other end, `OffValue` on the way up and `OnValue` on the way down, so a swell sounds the same every time.
- A CC with no off value starts from 0, and stays where it got to on the release.
- Starting a ramp on a channel and CC that is still ramping picks up from where that one got to, so pressing a toggle again halfway turns it round without a jump.
- The pedal does not stop while a ramp runs: switches, expression pedals and other ramps keep working. A `Wait` below the CC can hold the rest of the list back until the ramp has finished.
- It always ends on the exact value.
- Eight ramps can run at once; beyond that a CC goes straight to its value.
- `Panic` stops every ramp.
- A `Ramp` above anything but a CC is ignored.

<details><summary>Under the hood</summary>

A ramp sends a message at most every 5 ms, and only when the value changes. Older firmware ignores the `Ramp` and sends the CC as usual.

</details>

*Firmware 0.34 or later.*

### Changing an expression pedal's target

One pedal as the wah, then the volume, then a parameter. `CommandType` `Exp` changes what an expression pedal sends.

| Field | Meaning |
|---|---|
| `OnValue` | The pedal, 1 or 2 |
| `KeyMode` | `CC` sends it to the CC in `Number`, on `Channel` or, left empty, on the pedal's own channel. `Off` silences it. `Own` gives it back what it sends in this bank |
| `Toggle` | `Y`: only while the button is on |

- It lasts until another `Exp` for the same pedal, or a bank change.
- It wins over the bank's [`BankExpression_Settings`](08-expression.md#bankexpression_settings), even over a bank that silences the pedal, while the output range stays the bank's.
- As a toggle, switching the button off gives the pedal back its own target: a button with `Exp 1 CC 7` as a toggle turns the wah pedal into a volume pedal and back, with the LED showing which.
- The pedal switches over on its next movement, as on a bank change, so the volume does not jump to where the wah was left.
- On entering a bank the pedals start from that bank's own targets, and then any toggling `Exp` on a button of the bank that is on takes effect again, so the pedals always match the LEDs, also after switching the pedal off and on.
- While an `Exp` has a pedal somewhere else, its [auto-engage](08-expression.md#auto-engage) leaves its button alone.

<details><summary>Under the hood</summary>

Like `Wait`, an `Exp` is marked by the low nibble of the empty command type, 5; byte 1 is the pedal with the toggle bit, byte 2 the CC, 0x80 for Off or 0x81 for Own, and byte 3 the channel, 0 for the pedal's own. Older firmware ignores it.

</details>

*Firmware 0.42 or later.*

### Values and conditions

One button that does different things depending on another — a shift layer without a second bank — or a counter that walks a set of patches one press at a time.

**Values.** The pedal keeps eight values of its own, 0 to 127 each, all zero when it is switched on. `CommandType` `Value` changes one:

| Field | Meaning |
|---|---|
| `Number` | Which value, 1 to 8 |
| `KeyMode` | `Set` it to `OnValue` (also when empty), `Add` that much, or `Sub`tract it |
| `OnValue` | The amount |
| `OffValue` | The highest it goes, 127 when empty. Adding past it starts again at zero; taking away past zero starts again at it |

So `Add 1` with a top of 2 counts 0, 1, 2, 0, 1… on successive presses. The values are not part of the configuration and are not saved: they are what a button remembers within a gig, and the tools report them with the rest of the pedal's state.

**Conditions.** `CommandType` `If` holds back the command right below it unless its test holds. `KeyMode` is the test:

| `KeyMode` | Asks | Compared with |
|---|---|---|
| `Button on`, `Button off` | The toggle state of a button of the current bank | `Number`: the button, `1`–`4` or `A`–`D` |
| `Value =`, `Value <>`, `Value <`, `Value >=` | The value in `Number`, 1 to 8 | `OnValue` |
| `Bank is`, `Bank is not` | Which bank the pedal is on | `OnValue`: the bank number |

- An `If` reaches only the command right below it, with whatever `Chan`, `Ramp`, `LFO` or `Seq` commands belong to that one.
- An `If` under another asks for both, so two tests can be required at once.
- Two `If` commands with opposite tests, each above a command of its own, are a one button either-or: hold the pedal's BOST toggle on and a button sends one CC, off and it sends another.
- A button's toggle state is its own: it still turns over on every press, and its LED with it, whether or not the `If` above its command let anything out.
- The test is made again when the button is let go, so a momentary command that was held back is not sent its off value either, and a test that became true while the button was down does not leave a device switched on for ever.

The demo's bank 11 has both: held, NUDG asks about BOST, and held, ALL5 counts round three program changes.

<details><summary>Under the hood</summary>

The two commands are marked by the low nibble of the empty command type, 11 for `Value` and 12 for `If`, so the layout is unchanged. Older firmware ignores a `Value` and, more to the point, ignores an `If` and sends the command below it anyway.

</details>

*Firmware 0.54 or later.*

### Macros

A command list stored once and called from many buttons. `CommandType` `Macro` runs another button's command list in place, where it stands:

| Field | Meaning |
|---|---|
| `OnValue` | The bank that button is in, 0 to 31 |
| `Number` | The button, `1`–`4` or `A`–`D` |
| `KeyMode` | Which of its lists to run: `Short`, `Long` or `Double` |

So the ten commands that put the whole band's rig where it belongs are stored once, on a button of a bank set aside for them, and every bank that wants them spends one command instead of ten. It is the one feature that gives configuration room back rather than taking it: four bytes wherever it is used instead of forty, which matters, the configuration block being all but full.

How the called list runs:

- As if its commands were written where the `Macro` stands, with the toggle state of the button that called it, on the release as well as on the press, so a momentary command inside a macro is still sent its off value when you let go.
- A `Wait` inside it pauses the whole thing, and the caller carries on where it left off once the pause is over.
- An `If` above a `Macro` holds back the whole of it, which is how one button runs one stored list or another. Anything else above it — `Chan`, `Ramp`, `LFO`, `Seq` — belongs to the command right below it and does not reach inside a macro.
- A macro can call a macro, up to four lists deep counting the button's own, and a list already running is never called again. A macro that names itself, or two that name each other, send what they can and stop rather than going round for ever: the call that would have been the fifth, or the one that would have gone round, is passed over and the rest of the list carries on.
- Macros work in a button's short, long and double press lists, in a bank's commands on entering and leaving it, and in the bank switches' lists.

Two things look only at the button's own list and do not follow a macro into another: `LED_Feedback` and the Kemper's answers, which light a button by matching the commands written on it, and the auto-repeat of a held `CCInc` or `PCInc`. Put those on the button itself rather than in a macro.

In the demo, holding 2 on HOME runs the list stored on bank 11's WAIT button, pause and all.

<details><summary>Under the hood</summary>

`Macro` is marked by the low nibble of the empty command type, 13, with the bank in byte 1 and the button and list in byte 2, so the layout is unchanged. Older firmware ignores it and sends nothing in its place.

</details>

*Firmware 0.56 or later.*

## Command fields

The reference: every column of a command slot in the CSV, and what each command type does with it. A ✓ marks the command types the column is named after.

| Field | PC | CC | Note | PB | Key | Meaning |
|---|---|---|---|---|---|---|
| `CommandType` | | | | | | `PC`, `PCInc`, `CC`, `CCInc`, `Note`, `PB`, `Key`, `Media`, `Bank`, `SysEx`, `Tap`, `Start`, `Stop`, `MMC`, `Song`, `Panic`, `Scene`, `Wait`, `Ramp`, `LFO`, `Seq`, `Exp`, `Chan`, `Value`, `If`, `Macro`, `Cycle` (short press only), `Leave` (a bank's enter list only), or empty for none |
| `Channel_(PC/CC/Note/PB)` | ✓ | ✓ | ✓ | ✓ | | MIDI channel 1–16. Exp: empty for the pedal's own. Chan: the list of channels, `1 2 3` or `1-3` |
| `Number_(PC/CC/Note)` | ✓ | ✓ | ✓ | | ✓ | PC: program 0–127. CC: controller number. Note: note number. Key: modifier mask. Exp: the CC the pedal sends. Value: which of the eight, 1–8. If: the button it looks at, `1`–`4` or `A`–`D`, or the value, 1–8. Macro: the button, `1`–`4` or `A`–`D` |
| `OnValue_(CC/PB)` | | ✓ | | ✓ | ✓ | CC: value on press (0–127). PB: −8192..8191. Key: key name. Media: media key name. Cycle: the state's label, up to 4 characters. Exp: the pedal, 1 or 2. MMC `Locate`: where to go, in seconds. Song: the song number 0–127, or the position in sixteenth notes. LFO: the length of a cycle, `1/16T` `1/16` `1/8T` `1/8` `1/4T` `1/8.` `1/4` `1/2T` `1/4.` `1/2` `1/2.` `1/1` `2/1` `4/1` (empty for `1/4`). Seq: its two steps, a value 0–127 or `-` for a silent one, `100 -`. Value: the amount. If: what the value is compared with, or the bank. Bank: the bank, or how many to move. Macro: the bank the button is in |
| `OffValue_(CC)` | | ✓ | | | | CC: value on release / toggle off (0–127). Value: the highest it goes, 127 when empty |
| `BankSelect_(PC)` | ✓ | | | | | 0–16383, sent as CC#32 (LSB) before the PC |
| `BankSelectHighByte_(PC)` | ✓ | | | | | Y: also send CC#0 (MSB) |
| `Toggle_(CC/PB/Note)` | | ✓ | ✓ | ✓ | ✓ | Y: alternate on / off on successive presses. Key / Media: hold until the next press |
| `Velocity_(Note)` | | | ✓ | | | 0–127 |
| `Duration_(Note/PB)` | | | ✓ | ✓ | ✓ | In 10 ms steps, 0–127 (max 1.27 s). Media: same as Key. Wait: the pause in milliseconds, up to 2550. Ramp: its time in milliseconds, up to 655350 |
| `KeyMode_(Key)` | | | | | ✓ | Normal / Down / Up. CCInc and PCInc: Up / Down / Up Repeat / Down Repeat. Tap: Tap / Clock / Set / Up / Down / Up Repeat / Down Repeat. Exp: CC / Off / Own. LFO: Sine / Triangle / SawUp / SawDown / Square / Random (empty for Sine). Seq: how long a step lasts, the same note divisions as the LFO (empty for `1/8`), read from the first command of the run. MMC: Play / Stop / Record / RecordExit / Pause / FastForward / Rewind / Locate / DeferredPlay / Chase / Eject / Reset (empty for Play). Song: Select / Position. Value: Set / Add / Sub (empty for Set). If: Button on / Button off / Value = / Value <> / Value < / Value >= / Bank is / Bank is not. Bank: GoTo / Up / Down / Back / Page / Config / NextConfig. Macro: Short / Long / Double |

---

[← Buttons](05-buttons.md) · [Contents](README.md) · [Tempo, clock, LFO and sequencer →](07-tempo.md)
