# Midi Commander Custom Firmware

Custom firmware and configuration tools for the **MeloAudio Midi Commander** foot controller, sold in Europe as the **Harley Benton MP-100**: 32 banks of eight buttons, up to ten MIDI commands per press plus ten more on a long press, tap tempo and MIDI clock, USB keyboard and media keys, two calibrated expression pedals, button labels on the display, USB-to-DIN MIDI thru, and a desktop configurator that talks to the pedal over USB.

This repository is a fork of [arasan95/midi-commander-custom](https://github.com/arasan95/midi-commander-custom), which in turn builds on the original project by [harvie256](https://github.com/harvie256/midi-commander-custom). None of this would exist without their work and that of the other contributors listed in the [Acknowledgements](#acknowledgements). Thank you all.

The firmware replaces the stock MeloAudio one but never touches its bootloader, so you can always flash the vendor image back. Its configuration lives in the microcontroller's own flash, so the stock configuration stored in the external EEPROM is left untouched.

---

## Contents

1. [Features](#features)
2. [Getting started](#getting-started)
3. [The configurator](#the-configurator)
4. [Configuration reference](#configuration-reference)
5. [The display](#the-display)
6. [Command line tools](#command-line-tools)
7. [Building and flashing from source](#building-and-flashing-from-source)
8. [Changelog](#changelog)
9. [Still to come](#still-to-come)
10. [Acknowledgements](#acknowledgements)

---

## Features

- **32 banks × 8 buttons.** A short press on Bank Up / Bank Down steps one bank, a long press jumps a configurable number of banks, and both wrap around. A `Bank` command can also jump straight to a given bank, so one bank can act as a setlist index. Each bank has a name shown on the display.
- **The Bank Up / Down switches send MIDI too.** Each has its own command list for a short and a long press, the same in every bank. `Bank_Switch_Mode` chooses whether they also change bank, or stop changing bank altogether, which turns the pedal into a plain ten switch controller.
- **Up to 10 commands per button press**, sent in order. Any mix of Program Change (with optional Bank Select), Control Change, Note, Pitch Bend, Start, Stop, USB keyboard keys and media keys, each MIDI command on its own channel.
- **Long press.** A second set of up to 10 commands fires when a button is held past a configurable time (default 500 ms). Buttons without long press commands react instantly, as before.
- **Pauses between commands.** A `Wait` command spaces out the commands of a button, for the device that drops a Control Change arriving right behind a Program Change. The pedal keeps reading switches and pedals while it waits.
- **CC ramps.** A `Ramp` command makes the Control Change below it walk to its value over a time, up to about 11 minutes, instead of jumping: a volume swell or a slow filter sweep from a single press, and back again on the release or when a toggle is switched off.
- **Cycle buttons.** One button steps through several states, each with its own commands and its own label on the display: the four channels of an amp on a single switch, say, one press each, round and round.
- **Momentary or toggle** behaviour per command, and timed auto-release (up to 1.27 s) for Notes, Pitch Bend and keys.
- **Button labels on the display.** Each button has a 4 character label; the screen shows the current bank and a 2×4 grid mirroring the pedal, with toggle buttons drawn inverted while on.
- **LED modes** per button: Normal, Reverse (lit when off) or AlwaysOn (blinks while active). The Bank Up / Down LEDs have the same options. Global brightness for lit LEDs and, separately, for LEDs lit at rest, so an active button stands out from an idle one.
- **Tap tempo and MIDI clock.** A button sets the tempo by tapping and another starts or stops a 24 PPQN MIDI clock on both USB and the DIN output, so a delay or looper follows your foot. The tempo shows on the display as you tap. The tap button's LED flashes on every beat, whether the tempo is yours or the host's. Each bank or song can also set its own tempo on entry, and a pair of buttons can nudge it a BPM at a time.
- **Next and previous preset.** A button steps the Program Change up or down from wherever you are, whether you got there with a button, by entering a bank or from the computer, and shows the new number on the display. Stops at the ends or wraps round, within the range your device has.
- **Relative CC.** A button can nudge a CC value up or down by a step on each press, optionally wrapping, for setting a parameter with your foot. The value it lands on shows on the display for a moment, so you are not adjusting blind. Held down, it can keep going on its own, faster and faster, and so can a next or previous preset button.
- **Four configurations on one pedal.** Keep up to four complete configurations, one per band or venue for instance, and switch between them from a button. The pedal shows the number and name of the one it switched to and comes back on it after a power cycle.
- **Scenes.** One press puts the toggle buttons of the bank into a chosen combination, delay on and chorus off for instance, pressing for you only the ones that are not already there.
- **Latch or momentary.** A toggle button can latch on a tap and work as a momentary switch when held, like the boost on a Boss or Morningstar pedal: tap it on for the song, or hold it for a solo and it goes back off when you let go.
- **Exclusive groups.** Put toggle buttons of a bank in a group and switching one on switches the others off, sending their off commands, like the channel buttons of an amp or a choice between delays.
- **Panic.** A command that sends All Sound Off and All Notes Off on all sixteen channels, to USB and the DIN output, for the stuck note or runaway sound in the middle of a set.
- **Custom SysEx.** Up to sixteen SysEx messages can be stored and sent from a button, for devices that are only controllable that way.
- **USB keyboard and media keys (HID).** A command can press a key with Ctrl / Shift / Alt / Cmd modifiers, tap it, hold it or release it, or send a media key (play/pause, next, previous, stop, volume, mute, record) to the computer.
- **Two expression pedals** with per-pedal CC number, MIDI channel, calibrated end points, response curve and direction, calibrated live from the configurator. Each can also act as a switch: reaching the toe, or returning to the heel, taps a button of the current bank.
- **Expression per bank.** Each bank can give each expression pedal its own CC and channel, or silence it, so the same pedal is a wah in one bank and a volume in another.
- **Auto-engage wah.** Moving an expression pedal up from the heel switches a button on, and resting at the heel for a moment switches it off again, like the auto-engage wahs of Fractal and Line 6: no stomping on the wah before using it.
- **Expression output range.** A pedal can send only part of the range, 40 to 127 for a volume that never drops to silence for instance, or run backwards; per pedal, and per bank on top of that.
- **Virtual pedal.** The configurator draws the pedal as it is built, and lets you press its switches with the mouse, tap, hold or double click, while its screen, pixel for pixel, and its LEDs are read back from the pedal, so a configuration can be tried without standing on it.
- **Double press.** A third command list per button, fired by two quick presses, alongside the short and the long press.
- **LEDs that follow the computer.** With `LED_Feedback` on, a CC or a note arriving over USB lights or darkens the toggle buttons that send it, so the pedal shows what is really on when an effect is changed from a DAW or an amp editor.
- **Follows the host's clock.** With `Clock_Follow` on, the pedal measures MIDI clock arriving over USB, adopts that tempo and flashes it on the display for 1.5 seconds, and keeps its own clock out of the way while the host's is running. If the host's clock stops, the pedal's carries on at the same tempo.
- **Setlist.** Bank Up / Down can follow an order of your choosing instead of the bank numbers, so the night's songs come up one after another whatever banks they live in. Relative Bank commands follow it too; jumping to an exact bank still works as before.
- **Idle sleep.** After a configurable number of minutes with nobody touching it, the display and the LEDs switch off. Any press or expression pedal movement brings them back, and the press that wakes it still does its job, so nothing is lost on stage. It matters on batteries, where there is no host to suspend the USB bus.
- **Survives Active Sensing.** Some hosts, the Kemper Profiler Player among them, send an Active Sensing byte every 300 ms. A controller that never reads it lets its USB buffer fill until the link stalls, which is what makes the stock firmware drag the host down to a crawl. Here every incoming USB MIDI event is consumed and the endpoint is always re-armed, so the stream cannot back up.
- **USB-to-DIN MIDI thru.** Optionally forward everything received over USB to the MIDI OUT jack, so the pedal doubles as a USB MIDI interface for the device behind it. Clock / Start / Continue / Stop have their own switch.
- **Commands on entering and leaving a bank.** Each bank can send a set of commands when you switch to it, typically a Program Change that selects its patch, so no button is spent on it, and another when you leave it, for instance to switch off what it switched on.
- **Bank changes from incoming MIDI.** A Program Change or a Control Change arriving over USB can select a bank, so a DAW or another pedal can drive this one.
- **Remember state.** Optionally power up in the last bank with every toggle exactly as you left it, journaled across several flash pages so wear is not a concern.
- **Works without a computer.** On a USB charger or a power bank the pedal runs normally and drives your gear over the DIN output.
- **Sleep mode.** When the computer the pedal is connected to suspends, LEDs and display switch off; they come back when it wakes.
- **Ready for the Fractal FM3.** A template that loads a preset per bank and puts scenes, tuner, tap tempo, the looper and block bypass under your feet; see [the FM3 template](#fractal-audio-fm3-template).
- **Configuration over USB.** Flash a configuration to the pedal and read it back, from the GUI or the command line, over ordinary USB MIDI SysEx. No special driver.
- **Backups.** Copy all four configuration slots to a folder in one go, one editable CSV each, and put them all back just as easily.
- Firmware updates through the stock DFU bootloader with `dfu-util`.

---

## Getting started

You need the pedal, a USB cable, Python 3 and, to update the firmware, `dfu-util`.

### 1. Flash the firmware

The quickest way in is the [latest release](https://github.com/Charles5150/midi-commander-custom/releases/latest), which carries a ready built `.dfu` image. Build it yourself instead if you prefer; both routes end in the same place.

Released images are attached to the [releases](https://github.com/Charles5150/midi-commander-custom/releases); older ones are also kept in `artifacts/` for reference.

1. Install `dfu-util` (macOS: `brew install dfu-util`; Linux: your package manager; Windows: [dfu-util.sourceforge.net](https://dfu-util.sourceforge.net/)).
2. With the pedal off, hold **Bank Down** and **D** (the two bottom-right buttons) and switch it on. The display stays dark and LED 3 lights up: the pedal is in DFU mode.
3. Connect it over USB and check it is seen:

   ```text
   $ dfu-util --list
   Found DFU: [0483:df11] ... alt=0, name="@Internal Flash  /0x08000000/06*002Ka,250*002Kg", ...
   ```

4. Flash, using `--alt 0` (the internal flash entry above):

   ```bash
   dfu-util -d 0483:df11 --alt 0 --download midi-commander-custom-<version>.dfu
   ```

5. Power cycle the pedal. The firmware version shows on the display for a moment, then the first bank.

Flashing firmware does not erase your configuration. When a release changes the configuration format the [changelog](#changelog) says so; re-flash your configuration with the updated tools in that case.

### 2. Install the Python tools

```bash
git clone https://github.com/Charles5150/midi-commander-custom.git
cd midi-commander-custom
python3 -m venv .venv
.venv/bin/pip install -r python/requirements.txt
```

On macOS with Homebrew Python, the GUI also needs Tk: `brew install python-tk`.

### 3. Configure the pedal

```bash
.venv/bin/python python/gui_configurator.py
```

Connect the pedal in normal mode (not DFU), click **Read from Device** to load what it currently holds, edit, then **Flash to Device**. The next section walks through the configurator.

---

## The configurator

`python/gui_configurator.py` edits a configuration CSV and exchanges it with the pedal over USB MIDI.

<img src="docs/images/gui_workflow.png" width="500">

**Sidebar.** Two groups, the file and the pedal, with the name of the open file at the bottom.

- **File: Load CSV** opens a configuration file. `python/demo-all-features.csv` is loaded at start, so every feature is there to look at straight away. **Save CSV** writes the current settings to the open file.
- **Pedal: Slot** chooses which of the four configuration slots the two buttons below it use. `Active` means the one the pedal is running; flashing one slot never touches the others. **Read from Device** pulls that configuration from the connected pedal into a CSV you choose, and loads it. **Flash to Device**, the one red button, saves the CSV, transfers it to the pedal and reboots it. **Back Up All Slots** reads every slot that holds a configuration into a new dated folder, one CSV per slot, and **Restore Backup** writes such a folder back, each file to its own slot, after showing which ones it will replace.

The tabs follow the order a configuration is usually built in. Each starts with a one line summary; the **?** next to it opens the details.

**Buttons** — pick a bank, then a button from the eight laid out as on the pedal, 1 to 4 on top and A to D below; the one being edited is highlighted. At the top you set its **display label**, **LED light mode** and **exclusive group**; below, ten command slots A–J. Choose a slot's command type and only the fields that type uses appear. **Short press / Long press / Double press** switches the slots between the three command sets of the button. Edits are kept in memory automatically when you switch button, bank or tab. **Copy bank** and **Paste bank** duplicate a whole bank onto another: labels, LED modes, groups, short, long and double press commands and the commands sent on entering the bank. The target becomes identical to the source, so anything it had that the source does not is removed, and its name is kept, since a copy is usually the start of a variant. Pasting asks for confirmation first.

<img src="docs/images/gui_button_config.png" width="500">

**Banks** — the 4 character name and 8 character info line of each bank, and where the expression pedals send while it is selected: a CC and a channel per pedal, each `Default` to keep the pedal's own, or `Off` for the CC to silence the pedal in that bank, and the lowest and highest value it sends there, left empty to keep the pedal's own range.

**Bank Enter** — the commands each bank sends when you switch to it, and, below a `Leave` command, when you leave it.

**Bank Switch** — the command lists of the Bank Down and Bank Up switches, one per switch and press length. Combine it with **Bank switches** (`Bank_Switch_Mode`) in the Global tab.

<img src="docs/images/gui_bank_switch.png" width="500">

**Setlist** — the order Bank Up / Down follow when **Follow the setlist** (`Setlist_Mode`) is on, one drop-down per position listing every bank by number and name. The list ends at the first empty row.

**Expression** — per pedal: end points, response curve, invert, channel, the toe and heel switches, the output range and auto-engage. **Connect live view** shows the pedal position and the CC being sent, read from the pedal in real time. To calibrate: press **Calibrate**, sweep the pedal slowly from heel to toe and back a couple of times, press **Done**; the end points are filled in with a small margin so 0 and 127 are always reached.

**SysEx** — the sixteen stored SysEx messages, with the byte count or a parse warning as you type.

**Global** — the global settings in groups: Configuration, Presses, LEDs, Banks, USB MIDI and Power. Each setting has a plain name, a short hint and, in small print, its label in the CSV, which is the name the [reference](#global_settings) uses. Bounded settings are drop-downs or check boxes; numbers are limited to their valid range.

**Virtual Pedal** — the pedal as it is right now, laid out like its board: five switches a row with Bank Up and Down at the right, each LED at its real brightness, blinking and dimmed ones included, and between the rows the pedal's screen, mirrored pixel for pixel, so overlays and inverted toggle cells show exactly as on the pedal. Click a switch to tap it, hold the mouse button for a long press, click twice quickly for a double press. The press goes through exactly the same path as a foot, so long and double presses, the bank switches and everything they send behave as on the pedal. A switch held here lets go by itself after 10 seconds. Shares the Expression tab's connection; needs firmware 0.27.

<img src="docs/images/gui_virtual_pedal.png" width="500">

---

## Configuration reference

A configuration is a CSV with several sections, each introduced by a line starting with `*` and the section name. Lines containing `#` are comments. The configurator reads and writes this format, and you can also edit it in a spreadsheet.

**`python/demo-all-features.csv`** is the reference: a configuration that uses every feature, with one bank per feature and button labels that say what each one does. Load it in the configurator to see how anything is set up, or flash it to try the whole firmware on the pedal.

| Bank | What it shows |
|---|---|
| 0 | An index of `Bank` commands jumping to the other banks |
| 1 | A looper layout: CC toggles, the four track buttons as an exclusive group, and a long press on one button |
| 2 | The three LED modes side by side, and momentary versus toggle |
| 3 | Program Changes, with and without Bank Select, and a patch selected on entry |
| 4 | Keyboard keys: plain, with modifiers, held, and a Down/Up combination |
| 5 | Media keys |
| 6 | Tap tempo, clock start/stop, transport, and BPM up/down (hold SYNC for 120 BPM) |
| 7 | Relative CC, up and down, with and without wrapping, VOL+ and VOL- repeating while held, and two CC ramps: a toggle swell and a momentary rise |
| 8 | Stored SysEx messages, including an empty entry that sends nothing, and a WAH on D that pedal 1 switches on and off by itself |
| 9 | Notes and pitch bend, with durations and toggles |
| 10 | Bank navigation from buttons, absolute and relative |
| 11 | Several commands chained on one button, short versus long press, and a cycle button stepping through four amp channels (D), and a boost that latches on a tap and is momentary when held (4). Entering the bank sends CC 59 127 and leaving it CC 59 0 |
| 12–31 | A setlist: each bank selects its patch on entry and has looper controls |

Both expression pedals are configured, one linear and one logarithmic and inverted, with the toe and heel acting as switches. Pedal 1 auto-engages button D, the WAH in bank 8 (and TRK4 in bank 1), switching it off after 600 ms at the heel. Bank 2 turns pedal 1 into a modulation wheel held between 20 and 100, and bank 7 silences it and makes pedal 2 a volume on channel 2 that never drops below 40. Regenerate the file with `python3 python/make_demo_config.py` after adding a feature, so it keeps covering everything.

(`python/MeloConfig_10_Cmds - RC-600.csv` is a real-world configuration for a Boss RC-600. The original project's Google Sheets template is no longer online, and it predated several columns anyway; start from one of the CSVs instead.)

### Fractal Audio FM3 template

**`python/templates/FM3.csv`** is ready to flash for a Fractal Audio FM3 driven over the DIN output, and should suit an Axe-Fx III or FM9 too, which are set up the same way. Connect the pedal's MIDI OUT to the FM3's MIDI IN and power the pedal over USB.

| Banks | Buttons |
|---|---|
| 0–29, `P000`–`P029` | Entering the bank loads the FM3 preset with the same number. 1 2 3 4 A B are scenes 1–6, C latches the tuner, D taps the tempo |
| 30, `LOOP` | Looper: Record, Play/Stop, Undo, Once, Reverse, Half Speed, then tuner and tap |
| 31, `FX` | Engages and bypasses Drive 1, Compressor 1, Phaser 1, Chorus 1, Delay 1, Reverb 1, Wah 1 and Pitch 1 |

Bank Up / Down step through the presets, and a long press jumps ten. The scene buttons are an exclusive group, so the LED and the display show the scene last picked; pressing the lit one again darkens it without sending anything. The expression pedals are External 1 and 2, to attach to any parameter as a modifier.

The FM3 comes with no MIDI CC assigned, so on the FM3, under **SETUP > MIDI/Remote**, set its MIDI channel to 1 and assign:

| Page | Function | CC |
|---|---|---|
| Other | Tempo Tap | 14 |
| Other | Tuner | 15 |
| Other | Scene Select | 34 |
| External | External 1, External 2 | 16, 17 |
| Looper | Record, Play, Undo, Once, Reverse, Half Speed | 20–25 |
| Bypass | Drive 1, Compressor 1, Phaser 1, Chorus 1, Delay 1, Reverb 1, Wah 1, Pitch 1 | 40–47 |

To use other numbers, or another channel, change the constants at the top of `python/make_fm3_template.py` and run it again, or edit the buttons in the configurator. Presets above 29, or in the FM3's banks B to D, take a Program Change with `BankSelect_(PC)` set to 128 times the FM3 bank and `BankSelectHighByte_(PC)` to `Y`, so that CC#0 carries the bank.

### Global_Settings

`Label,Value` rows.

| Label | Values | Meaning |
|---|---|---|
| `MIDI_Channel` | 1–16 | Channel used by the expression pedals (unless a pedal sets its own). Buttons use the channel of each command. |
| `RealTime_Passthrough` | Y / N | Forward MIDI Clock, Start, Continue and Stop received over USB to the DIN output. |
| `USB_MIDI_Thru` | Y / N | Forward every other MIDI message received over USB (notes, CC, PC, pitch bend, system common, other devices' SysEx) to the DIN output. |
| `ConfigName` | up to 16 chars | Shown on the display at boot. |
| `Exp1_CC`, `Exp2_CC` | 1–127 | CC number sent by each expression pedal. Defaults 11 and 4. |
| `Bank_Up_LED_Mode`, `Bank_Down_LED_Mode` | Normal / Reverse / AlwaysOn | LED behaviour of the bank buttons (see [LED modes](#led-modes)). |
| `Remember_State` | Y / N | Power up in the last bank with all toggles as they were. |
| `Double_Press_ms` | 100–1000 | Time the second press of a double press may take. A button with double press commands in the current bank waits this long after a tap before sending its short press. Default 300. |
| `Long_Press_ms` | 100–2500 | Hold time that turns a press into a long press, on the command buttons and on Bank Up / Down. Default 500. |
| `LED_Brightness` | 1–100 | Brightness of a lit LED, in percent. Default 100. Configurations written before 0.9 read as 100. |
| `LED_Rest_Brightness` | 1–100 | Brightness of LEDs lit at rest by the Reverse and AlwaysOn modes. Default 100; set it lower to tell an active button from an idle one. |
| `Bank_Jump_Step` | 1–31 | Banks skipped by a long press on Bank Up / Down. Default 8. |
| `Bank_Change_Mode` | Off / PC / CC | Let an incoming Program Change, or Control Change, select a bank. |
| `Bank_Change_Channel` | Any / 1–16 | Channel the pedal listens on for those messages. |
| `Bank_Change_CC` | 0–127 | CC number that selects a bank, when the mode is CC. Its value is the bank. |
| `LED_Feedback` | Y / N | A Control Change, Note On or Note Off arriving over USB puts every toggle button whose `CC` or `Note` command has the same channel and number into the state it describes: its LED, its display cell and what its next press sends follow. Every bank is updated, and the long press list too. A CC counts as on when its value is nearer the command's `OnValue` than its `OffValue`; a command without an `OffValue` only reacts to its `OnValue`. A Note On with a velocity is on, a Note Off or velocity 0 is off. Only the state changes: nothing is sent, so a host that echoes the pedal's messages back causes no loop. While asleep the state is kept and the LEDs come back right on waking. Default N. |
| `Clock_Follow` | Y / N | Measure MIDI clock arriving over USB, over two beats, and adopt its tempo; the display shows it as `EXT` and a tempo for 1.5 seconds when the clock is picked up or its tempo changes by two BPM or more. While that clock keeps arriving the pedal sends no clock of its own: with `RealTime_Passthrough` on the host's clock already reaches the DIN output, and with it off the pedal re-clocks the DIN output at the host's tempo. Half a second without a clock counts as stopped, and the pedal's own clock, if running, continues at the adopted tempo. Default N. |
| `Setlist_Mode` | Y / N | Bank Up / Down, and relative `Bank` commands, follow the order in the `Setlist` section instead of the bank numbers. From a bank that is not in the list, Up enters at its first entry and Down at its last. `GoTo` and bank selection from incoming MIDI still go to the exact bank. Default N. |
| `Sleep_After_Min` | 0–60 | Minutes of inactivity before the display and LEDs go out. 0 turns it off. A press or a moved expression pedal wakes it and still does what it was asked to. |
| `Bank_Switch_Mode` | Bank / Bank+MIDI / MIDI only | What the Bank Up / Down switches do. `Bank` is the original behaviour, they only change bank. `Bank+MIDI` also sends their commands from `BankSwitch_Settings`. `MIDI only` stops them changing bank, leaving a ten switch controller. Default `Bank`. |

### Bank_Naming

One row per bank, `Bank_Number` 0–31: `Bank_Name_Large` (4 characters, big font) and `Bank_Info_Small` (8 characters, small font).

### Button_Settings

One row per button, 256 rows in bank order and, within a bank, in the order `1, 2, 3, 4, A, B, C, D` (top row of the pedal, then bottom row). Columns:

- `Bank_Number`, `Button_Identifier`
- `Label` — up to 4 characters shown on the display. Empty shows the button identifier.
- `Light_Mode` — Normal / Reverse / AlwaysOn.
- `Group` — empty, or an exclusive group 1–4 (see **Exclusive groups** below).
- `Momentary_Hold` — `Y` for a toggle button that is momentary when held (see **Latch or momentary** below); empty or `N` otherwise.
- Ten command slots, prefixed `A_` to `J_`, each with the fields below.

#### Command fields

| Field | PC | CC | Note | PB | Key | Meaning |
|---|---|---|---|---|---|---|
| `CommandType` | | | | | | `PC`, `PCInc`, `CC`, `CCInc`, `Note`, `PB`, `Key`, `Media`, `Bank`, `SysEx`, `Tap`, `Start`, `Stop`, `Panic`, `Scene`, `Wait`, `Ramp`, `Cycle` (short press only), or empty for none |
| `Channel_(PC/CC/Note/PB)` | ✓ | ✓ | ✓ | ✓ | | MIDI channel 1–16 |
| `Number_(PC/CC/Note)` | ✓ | ✓ | ✓ | | ✓ | PC: program 0–127. CC: controller number. Note: note number. Key: modifier mask |
| `OnValue_(CC/PB)` | | ✓ | | ✓ | ✓ | CC: value on press (0–127). PB: −8192..8191. Key: key name. Media: media key name. Cycle: the state's label, up to 4 characters |
| `OffValue_(CC)` | | ✓ | | | | CC: value on release / toggle off (0–127) |
| `BankSelect_(PC)` | ✓ | | | | | 0–16383, sent as CC#32 (LSB) before the PC |
| `BankSelectHighByte_(PC)` | ✓ | | | | | Y: also send CC#0 (MSB) |
| `Toggle_(CC/PB/Note)` | | ✓ | ✓ | ✓ | ✓ | Y: alternate on / off on successive presses. Key / Media: hold until the next press |
| `Velocity_(Note)` | | | ✓ | | | 0–127 |
| `Duration_(Note/PB)` | | | ✓ | ✓ | ✓ | In 10 ms steps, 0–127 (max 1.27 s). Media: same as Key. Wait: the pause in milliseconds, up to 2550. Ramp: its time in milliseconds, up to 655350 |
| `KeyMode_(Key)` | | | | | ✓ | Normal / Down / Up. CCInc and PCInc: Up / Down / Up Repeat / Down Repeat. Tap: Tap / Clock / Set / Up / Down / Up Repeat / Down Repeat |

`Start` and `Stop` take no parameters; they send MIDI Start (0xFA) / Stop (0xFC) over USB and DIN.

**When the "off" is sent**

- `Toggle = N`, `Duration = 0`: on when pressed, off when released (momentary).
- `Toggle = N`, `Duration > 0`: on when pressed, off automatically after the duration, even if still held. Notes, pitch bend and keys only; CC ignores the duration.
- `Toggle = Y`: the first press sends on, the next sends off, and so on. Toggle state is kept per button and per bank, and drives the LED.

**Keyboard keys.** `Number` is the sum of the modifiers: 1 Ctrl, 2 Shift, 4 Alt, 8 Cmd/Win (3 = Ctrl+Shift). `OnValue` is a single character (`a`, `7`) or one of `enter`, `esc`, `tab`, `space`, `backspace`, `minus`, `equal`, `leftbr`, `rightbr`, `backslash`, `semicolon`, `quote`, `grave`, `comma`, `dot`, `slash`, `f1`–`f12`. `KeyMode`: **Normal** taps the key (held for `Duration` if set); **Down** presses and leaves it pressed, **Up** releases it, both after a `Duration` delay, so one button can build combinations across several slots. `Toggle` holds the key until the next press.

**Relative CC.** `CommandType` `CCInc` sends a CC whose value moves on every press instead of being fixed. `Number` is the CC, `OnValue` the value it starts from at power on, `OffValue` the step, `KeyMode` the direction (`Up` or `Down`, or `Up Repeat` or `Down Repeat` to repeat while held, below) and `Toggle` enables wrapping past the ends instead of sticking at 0 and 127. The running value lives in memory, one per command slot, and resets to the start value when the pedal is switched off.

**Next and previous preset.** `CommandType` `PCInc` sends a Program Change one step up or down from the program last selected on its channel. That is whatever was sent last on the channel, by any PC command, by the commands of a bank being entered, or by the computer over USB, so the button always moves on from where the device really is; before anything has been sent it counts as program 0. The state is shared, so a Next and a Previous button work as a pair, and it is not kept across a power cycle. `Channel` is the channel, `KeyMode` the direction (`Up` or `Down`), `OffValue` the step (1 when empty), `Number` the last program of the range, 0 to 127 (127 when empty; a Line 6 HX Stomp, for instance, has 0 to 125), and `Toggle` makes it wrap round at the ends instead of stopping there. No Bank Select is sent. The new number shows on the display for a moment, as `PC 6`. Stored as a PC whose Bank Select MSB byte, where 0x80 and above already meant none, holds 0x81 for up or 0x82 for down; the step is in byte 1 and the last program in byte 3, with its top bit for wrapping. The demo puts PREV and NEXT on C and D of the program change bank, which sends PC 0 when entered.

**Repeat while held.** With `KeyMode` `Up Repeat` or `Down Repeat`, a `CCInc` or `PCInc` command, or a `Tap` stepping the tempo, keeps firing while its button is held, like a key on a computer keyboard: once on the press, again after half a second, then every 200 ms, each gap a quarter shorter than the one before, down to one every 50 ms. A CC value can thus cross its whole range in about three seconds with a step of 2, while a tap still moves it a single step. Only the repeating commands of the list fire again, and they skip any `Wait`. A repeat that has hit an end and cannot move any further sends nothing, so a held button does not keep resending 127. Holding a button that has long press commands makes a long press, so its short list cannot repeat; its long press list can, and so can a double press list while the second press is held. Stored as the top bit of the step byte for `CCInc`, and as the markers 0x83 for up and 0x84 for down, in place of 0x81 and 0x82, for `PCInc`. Needs firmware 0.35; older firmware ignores the repeat on `CCInc` but sends a repeating `PCInc` as an ordinary, wrong, Program Change, so update the firmware first.

**Tap tempo.** `CommandType` `Tap` with `KeyMode` `Tap` measures the tempo from the interval between presses, averaging the last four and ignoring anything outside 30–300 BPM. With `KeyMode` `Clock` the button starts or stops the clock instead, sending MIDI Start or Stop and then 24 clock bytes per quarter note to USB and DIN while it runs. Either action shows the tempo on the display for a moment, with a leading `*` while the clock is running. The tempo is not saved; it starts at 120 BPM each time the pedal is switched on.

**Setting the tempo.** With `KeyMode` `Set`, a `Tap` command sets the tempo to `OnValue` BPM, 30–300 (120 when empty). Put it in a bank's commands on entry and each bank, or each song of a setlist, starts at its own tempo. With `KeyMode` `Up` or `Down` it moves the tempo by `OffValue` BPM (1 when empty), stopping at 30 and 300, and with `Up Repeat` or `Down Repeat` it keeps moving while the button is held, faster and faster, as described under **Repeat while held** above. All of them show the new tempo on the display, and a running clock and the tap LED follow it at once. While `Clock_Follow` is following the host's clock, the host's tempo wins. These buttons do not flash with the beat. Stored in the low nibble of the `Tap` command, 2 for `Set` with the BPM in bytes 2 (low 7 bits) and 3 (the rest), 3 for `Up` and 4 for `Down` with the step in byte 2 and its top bit set to repeat. Needs firmware 0.37; older firmware takes all three as a plain tap, so update the firmware first.

**Tap LED.** Every button of the current bank with a `Tap` command in `Tap` mode, in any of its lists, flashes its LED at the `LED_Brightness` level at the start of each beat, for a quarter of a beat and at most 100 ms. A `Clock` button flashes the same way, but only while the clock is running, so its LED also tells you the clock is on. With the clock stopped the beat runs freely at the tempo and every tap re-phases it, so the flash lands with your foot; with the clock running the flash is the first of every 24 clock bytes, starting from Start; and while `Clock_Follow` is following the host's clock, it is the host's beat, counted from its Start. The flash sits on top of whatever the LED shows, so a Reverse or AlwaysOn LED lit at rest as bright as `LED_Brightness` shows no flash; set `LED_Rest_Brightness` lower to see it. It stops while the pedal sleeps.

**Double press.** `DoublePress_Settings` gives each button a third command list, in the same format as `LongPress_Settings` and with its own toggle state; in the configurator it is the **Double press** mode of the button editor, and Copy / Paste bank carries it. Two presses within `Double_Press_ms` send it. Only buttons that have double press commands in the current bank change behaviour: a single tap on them waits for that window before sending its short press, and holding them still gives the long press, or the short press when there is none. Buttons without double press commands respond exactly as before. Needs firmware 0.26; `CSV_to_Flash.py` leaves the double press commands out, with a warning, when the pedal runs anything older.

**Configuration slots.** Two more `Bank` command modes switch configuration instead of bank. `Config` switches to the slot in `OnValue`, 1 to 4, and `NextConfig` moves to the next slot that holds a configuration, wrapping round. The switch waits until every switch is released, sends any timed release still pending so nothing is left hanging, and starts the new configuration from bank 0 with every toggle off, showing its number and name full screen. Asking for an empty slot, or for the next one when no other holds a configuration, shows a short notice instead. The active slot is remembered across power cycles whatever `Remember_State` says; the bank and toggles are only restored when the configuration being started asks for them. A slot holds a configuration when its `ConfigName` is sixteen printable characters, which the tools always write.

**Scenes.** `CommandType` `Scene` sets the toggle buttons of the current bank to a chosen state. `OnValue` holds eight characters, one per button in the order `1234ABCD`: `+` to switch it on, `-` to switch it off, and `.` or anything else to leave it alone, so `+-+..-..` turns 1 and 3 on and 2 and B off. Each affected button that is not already in the wanted state is pressed as if by foot, so its own commands, LED and display cell follow; buttons already there are not touched, so recalling the same scene twice sends nothing the second time. Buttons without a toggle command have no state and are skipped. A scene cannot trigger another scene. The configurator shows it as eight drop-downs, and the demo puts three on the long presses of the LED modes bank.

**Exclusive groups.** A button's `Group`, 1 to 4, ties it to the other buttons of its bank in the same group: switching one on switches off every other one of the group that is on, as if pressed by foot, so their off commands go out and their LEDs and display cells follow. They are switched off before the pressed button sends anything, so when the whole group drives one parameter, an amp channel CC for instance, the device ends up where the pressed button says. Pressing the lit button switches it off like any toggle, leaving the group all off. Only buttons with a toggle command take part, and only their short press; groups are per bank, so group 1 in one bank has nothing to do with group 1 in another. A scene can switch on two buttons of a group, and the last one wins. The group lives in the top bits of the button's LED mode byte, which configurations have always left at zero, so the layout is unchanged. Needs firmware 0.32; firmware before it reads a button with a group as `Normal` LED mode. The demo groups the four track buttons of the looper bank.

**Panic.** `CommandType` `Panic` sends All Sound Off (CC 120) and All Notes Off (CC 123) on all sixteen channels, to both USB and the DIN output. It takes no parameters. The 32 messages go out packed into two USB packets and two serial buffers, so a panic cannot itself run out of transmit buffers. It does not reset toggle states or controllers. A long press is a good place for it, where it cannot be hit by accident; the demo puts it on a long press of STOP in the tempo bank.

**Pauses.** `CommandType` `Wait` sends nothing: it pauses the commands that follow it in the list. `Duration` is the pause in milliseconds, in steps of 10 and up to 2550. It is what a device that drops a Control Change arriving right behind a Program Change needs, and it also spaces out a chain the other end cannot swallow at once. The pedal does not stop to count: the rest of the list is picked up once the time is up, so other buttons, the expression pedals and the display keep working meanwhile. A button released while its list is still waiting has its release, the note off or the momentary off, held back until the list finishes, so nothing is switched off before it has been sent; pressing the same button again first sends whatever was left, without its pauses. Pauses work in every list: short, long and double press, bank enter and the bank switches. Four lists can be waiting at once, which is more than a foot can start; beyond that the pauses are skipped rather than queued. Needs firmware 0.30; older firmware sends the rest of the list without pausing.

**CC ramps.** `CommandType` `Ramp` sends nothing itself: it turns the `CC` command right below it into a ramp. Instead of jumping to its value, that CC walks there over `Duration` milliseconds, in steps of 10 and up to 655350 (almost 11 minutes). On the press it walks to `OnValue`; on the release, or on the press that switches a toggle off, it walks back to `OffValue`. A ramp starts from the command's other end, `OffValue` on the way up and `OnValue` on the way down, so a swell sounds the same every time; a command whose `OffValue` is above 127, and so has no off value, starts from 0 and stays where it got to on the release. Starting a ramp on a channel and CC that is still ramping picks up from where that one got to, so pressing a toggle again halfway turns it round without a jump. The pedal does not stop while a ramp runs: switches, expression pedals and other ramps keep working, and a `Wait` below the CC can hold the rest of the list back until the ramp has finished. A ramp sends a message at most every 5 ms and only when the value changes, and always ends on the exact value. Eight ramps can run at once; beyond that a CC goes straight to its value. `Panic` stops every ramp. A `Ramp` above anything but a CC is ignored. Needs firmware 0.34; older firmware ignores the `Ramp` and sends the CC as usual.

**Latch or momentary.** A button with `Momentary_Hold` set to `Y` and a toggle command in its short press list latches on a tap and is momentary when held. It toggles as soon as it is pressed, as always; held past `Long_Press_ms` (500 ms unless set), it presses itself once more when released, so it goes back to where it was: on only while held if it was off, off only while held if it was on. A tap shorter than that latches as usual. The hold belongs to the long press list when the button has one, so the option does nothing on such a button, nor on a cycle button. In an exclusive group, holding a button switches the others off and they stay off. The option is bit 7 of the button's LED mode byte, which configurations have always left at zero, so the layout is unchanged. Needs firmware 0.39; older firmware ignores it and the button simply toggles. In the configurator it is the "Momentary when held" box beside the exclusive group. The demo's bank 11 button 4, BOST, uses it.

**Cycle buttons.** `CommandType` `Cycle` splits a button's short press commands into states. The commands above the first `Cycle` are state 1, those between it and the next `Cycle` state 2, and so on. The `Cycle` commands take command slots too, so the ten slots hold five states of one command each. Each press sends the next state's commands, back to state 1 after the last one, and the display cell shows the label of the state just sent: the `Cycle` command's `OnValue`, up to 4 characters, or the button's own `Label` for state 1 and for a `Cycle` left without one. A button starts before its first state, so its first press sends state 1. For an amp with four channels on Program Changes 0 to 3, the button's commands are `PC 0`, `Cycle "CH B"`, `PC 1`, `Cycle "CH C"`, `PC 2`, `Cycle "CH D"`, `PC 3`, with `CH A` as its label. A state may hold several commands, pauses, ramps and repeating commands, which then repeat only while that state's press is held. Every cycle button of every bank keeps its place while the pedal is on, whatever banks you visit in between; a change of configuration, or switching the pedal off, starts them all from the beginning again. `Cycle` belongs in the short press list only: the tools refuse it in a long or double press, a bank's commands on entry or the Bank switches' lists. The labels are kept in a table of 48 at the end of the configuration, each different label stored once however many buttons use it, and the tools refuse a configuration with more. Like `Wait`, a `Cycle` is marked by the low nibble of the empty command type, 3, with byte 1 holding the label's place in the table, or 0x7F for none. Needs firmware 0.38; older firmware ignores the `Cycle` commands and sends every state at once.

**Custom SysEx.** `CommandType` `SysEx` sends one of the messages stored in the `SysEx_Strings` section; `Number` selects which, 0 to 15. Nothing else in the command is used. The message goes to both USB and the DIN output.

**Bank changes.** `CommandType` `Bank` switches bank. `KeyMode` selects the action: `GoTo` jumps to the bank number in `OnValue` (0–31), `Up` and `Down` move by the number of banks in `OnValue`, wrapping around. The change is applied after the button's remaining commands have been sent, so a button can send MIDI and then move to another bank. Nothing else in the command is used.

**Media keys.** `CommandType` `Media` sends a USB consumer-control key to the computer, the same ones a keyboard's media buttons send, so they work in any player or DAW without MIDI mapping. `OnValue` is one of `play_pause`, `play`, `pause`, `stop`, `next`, `prev`, `record`, `fast_forward`, `rewind`, `eject`, `mute`, `vol_up`, `vol_down`, or a raw usage number (`0xE9`). The key is tapped on press and released on release, held for `Duration` if set, or held until the next press with `Toggle`. `Number` and `Channel` are unused.

#### LED modes

- **Normal**: lit while the button is active, off otherwise.
- **Reverse**: lit at rest, off while active.
- **AlwaysOn**: lit at rest, blinking while active.

"Active" means physically pressed for a momentary button, or toggled on when any of the button's commands is a toggle. A lit LED uses `LED_Brightness`; "lit at rest" uses `LED_Rest_Brightness`. LEDs are dimmed by software PWM at 500 Hz, so there is no visible flicker.

### LongPress_Settings

Optional. Same columns as `Button_Settings` minus `Label` and `Light_Mode`. Rows may be missing or in any order; a button without a row has no long press commands and reacts instantly on press. Long press commands have their own toggle state.

Rows are optional in `Button_Settings` and `Bank_Naming` too: a configuration that only defines the first few banks, including one written for the 8 bank firmware, flashes unchanged and leaves the rest empty. The configurator always shows all 32 banks and writes them all when you save.

### SysEx_Strings

Optional; sixteen rows with an `Index` (0–15) and `Bytes`. Write the bytes in hexadecimal as the device manual shows them, separated by spaces or commas, with an optional `0x` prefix. A leading `F0` and trailing `F7` are optional and added when sending. Up to 23 data bytes, each `00`–`7F`. A line that cannot be parsed is stored empty and the command sends nothing, rather than sending a malformed message. Edit it in the configurator's **SysEx** tab, which shows the byte count or a warning as you type.

### BankEnter_Settings

Optional; one row per bank with the same ten command slots as a button, minus the button columns. These commands are sent once when the bank is entered, from any source: the bank switches, a `Bank` command or an incoming MIDI message. No release is sent, and `Bank` commands are ignored so entering a bank cannot chain into another one. Edit it in the configurator's **Bank Enter** tab.

**Commands on leaving a bank.** A `Leave` command, which takes no fields, splits the list in two: the commands above it are sent on entering the bank, those below it on leaving it. A bank that switches a delay on as it is entered, for instance, has `CC 59 127`, `Leave`, `CC 59 0`, and the delay goes off again whichever way you leave. The leaving commands go out just before those of the bank being entered, whatever took you there, a bank switch, a `Bank` command or incoming MIDI, and also when you change configuration, before the new one's first bank is entered. They are sent straight through: a `Wait` among them is skipped, so the two lists never overlap, and a `Wait` at the top of the next bank's list is how to space them out. The ten slots are shared by both parts and the `Leave` takes one of them; the tools refuse a second `Leave`, or one anywhere else than a bank's list. Like `Wait`, a `Leave` is marked by the low nibble of the empty command type, 4, so the layout is unchanged. Needs firmware 0.40; older firmware sends both parts on entering.

### BankSwitch_Settings

Optional; four rows, one per switch and press length: `Switch` `Down` or `Up`, `Press` `Short` or `Long`, then the same ten command slots as a button. Rows may be missing or in any order.

These lists are global, not per bank, because the switches are navigation and should behave the same wherever you are. Each list fires as a tap, press then release, so a `Toggle` command flips once per press and keeps its own state. `Bank` commands are ignored here; where you end up is decided by the switch itself and by `Bank_Switch_Mode`. Nothing is sent while the mode is `Bank`. Edit it in the configurator's **Bank Switch** tab.

### Setlist

Optional; rows of `Position` and `Bank_Number` (0–31). Up to 32 entries, ordered by `Position`, so rows may be in any order and positions may skip numbers; invalid bank numbers are dropped. It only takes effect while `Setlist_Mode` is on, so you can keep a list stored and switch it off. A bank may appear more than once, but stepping from it always continues from its first appearance. Edit it in the configurator's **Setlist** tab.

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

**Output range.** The pedal's travel, after the curve and `Invert`, is spread between `Out_Min` at the heel and `Out_Max` at the toe, so 40 and 127 make a volume pedal that never goes silent, and 127 and 0 turn it round without touching `Invert`. The ends are always reached exactly. `Toe_Level` and `Heel_Level` still refer to the pedal's position, 0 to 127, whatever it sends. A bank can override either end in `BankExpression_Settings`. Stored in two bytes that were reserved in each pedal's record, where older tools wrote zeros: firmware 0.33 reads 0 and 0 as the full range, so older configurations are unchanged. Firmware before 0.33 ignores the range.

**Auto-engage.** For a wah that switches itself on and off, as on Fractal and Line 6 units: put the wah's on and off commands on a toggle button and name that button in `Auto_Button`. Moving the pedal up past `Heel_Level` switches the button on, just before the pedal's first value is sent, and resting at or below `Heel_Level` for `Auto_Off_ms` switches it off. The button is pressed as if by foot, so its commands, LED and display cell follow, and it can still be pressed by hand: both directions act only on the moment the pedal leaves the heel or has rested there long enough, so a wah switched off by hand with the pedal up, or on by hand at the heel, stays as it was left. The button is the same in every bank, and nothing happens in a bank where it is not a toggle, so put the wah on the same button in the banks that need it. It works when a bank silences the pedal too. Stored in bytes 13 and 14 of each pedal's record, the button plus one and the delay in 10 ms steps, where older tools wrote zeros, which mean no auto-engage. Firmware before 0.41 ignores it.

Used as a switch, the pedal taps a button of the **current bank**, sending whatever that button is configured to send, including its toggle state and LED. Each direction re-arms only after the pedal moves back past its level by a margin, so resting on the edge does not retrigger.

Both 1/4" jacks are read through the ADC every millisecond, with the pin pulled down between readings to prevent crosstalk between the two inputs, smoothed with an adaptive filter and a small hysteresis so a resting pedal does not chatter. A CC is sent only when the 7-bit value changes.

If a pedal produces no CC, open the Expression tab and press **Connect live view**: if the raw value does not follow the pedal, the problem is the cable or jack; if it does but no CC reaches your MIDI monitor, check the channel and CC number, and the bank's own settings in `BankExpression_Settings`.

### BankExpression_Settings

Optional; one row per `Bank_Number` (0–31), rows may be missing or in any order.

| Column | Values | Meaning |
|---|---|---|
| `Exp1_CC`, `Exp2_CC` | empty, 0–127 or Off | CC the pedal sends while this bank is selected. Empty keeps `Exp1_CC` / `Exp2_CC` from `Global_Settings`; Off silences the pedal in this bank. |
| `Exp1_Channel`, `Exp2_Channel` | empty or 1–16 | Channel for that pedal in this bank. Empty keeps the pedal's `Channel` from `Expression_Settings`. |
| `Exp1_Min`, `Exp1_Max`, `Exp2_Min`, `Exp2_Max` | empty or 0–127 | Values the pedal sends at the heel and at the toe in this bank. Empty keeps its `Out_Min` / `Out_Max` from `Expression_Settings`; each end is taken on its own. Needs firmware 0.33. |

A silenced pedal still acts as a switch: its `Toe_Button` and `Heel_Button` keep working. After a bank change the pedal is not sent to its new CC, channel or range at the position it happens to rest in; it follows the next movement. Configurations written before 0.28 have nothing stored here and behave as if every cell were empty, and those written before 0.33 have no range here. The range is a table of its own after the CC and channel one, four bytes per bank, so their layout is unchanged. Edit it in the configurator's **Banks** tab.

---

## The display

The 128×64 OLED shows, on the top line, the bank's large 4 character name and its 8 character info. Below it, a 2×4 grid laid out like the pedal: buttons **1 2 3 4** on the top row, **A B C D** on the bottom. Each cell shows the button's label, or its identifier when it has none, and cells of toggle buttons are drawn inverted while the toggle is on, so the state of the whole bank is visible at a glance.

---

## Command line tools

Both tools take `--slot 1` to `--slot 4` to choose a configuration slot, and use the slot the pedal is running when it is left out. Reading an empty slot is reported rather than producing a CSV. Firmware older than 0.24 has a single configuration, and the tools refuse any slot but 1 on it.

Everything the GUI does is available from the terminal, from the repository root:

```bash
# Flash a configuration to the pedal (normal mode, connected over USB)
.venv/bin/python python/CSV_to_Flash.py my-config.csv

# Read the configuration stored on the pedal into a CSV
.venv/bin/python python/Flash_to_CSV.py current-config.csv

# Back up all four slots at once, and put them back
.venv/bin/python python/Backup_Slots.py backup my-backup
.venv/bin/python python/Backup_Slots.py restore my-backup
```

**Backups.** `Backup_Slots.py backup` reads every slot that holds a configuration into a folder, `slot1.csv` to `slot4.csv`, plus a `backup.txt` with the date, the firmware and the name in each slot; with no folder given it makes one named after the date and time. Each CSV is an ordinary configuration, so any of them can be opened in the configurator or flashed on its own. `restore` checks every file before touching the pedal, lists what it will overwrite and asks first (`--yes` skips the question), writes each file to its slot and restarts the pedal once at the end; slots with no file in the folder are left as they are. A backup restored onto the pedal gives the same bytes it was read from, except that settings a configuration from older firmware never had are written with the value the pedal was already using for them.

The tools find the pedal by its USB MIDI name (`MIDI Commander Custom`), check the firmware version, and exchange the configuration as SysEx messages under manufacturer ID `0x7D`: erase (52), write 16-byte chunk (54), read chunk (56), version (58), reset (60), pedal readings (62). The read-back commands need firmware 0.2 or later; the tools tell you if the pedal is older.

To watch what the pedal sends, use any MIDI monitor (MIDI Monitor on macOS, MIDI-OX on Windows, `aseqdump -p 'MIDI Commander Custom'` on Linux).

---

## Building and flashing from source

The firmware is built with [PlatformIO](https://platformio.org/) (`pip install platformio`, `pipx install platformio` or the VS Code extension). All sources live under `firmware/`; the first build downloads the ARM toolchain.

```bash
platformio run -e midi_dfu      # DFU image, linked at 0x08003000 behind the stock bootloader
platformio run -e midi_debug    # ST-Link image at 0x08000000 (for SWD debugging, replaces the bootloader)
```

`midi_dfu` also packages the binary as a DfuSe container through `scripts/post_build_dfuse.py` and `tools/bin_to_dfuse.py`, writing `artifacts/dfu/platformio-<timestamp>.dfu` and a stable `artifacts/dfu/platformio-latest.dfu`. Flash it as in [Getting started](#1-flash-the-firmware), or let PlatformIO drive `dfu-util`:

```bash
platformio run -e midi_dfu -t upload
```

The raw binary can also be flashed directly: `dfu-util --alt 0 -s 0x08003000 --download .pio/build/midi_dfu/firmware.bin`.

The Python tools have round-trip tests for the configuration packers:

```bash
.venv/bin/python -m unittest discover -s python/tests
```

GitHub Actions builds both firmware images and runs these tests on every push and pull request. See `CONTRIBUTING.md` for the repository layout and what to keep in sync when changing the configuration format.

Hardware notes (MCU, pinout, I²C addresses) are in `HardwareNotes.txt`; `backup/` holds a dump of the original firmware and EEPROM.

---

## Changelog

Firmware versions are shown on the display at boot and reported by the tools.

- **0.41 — Auto-engage from the expression pedal.** New `Auto_Button` and `Auto_Off_ms` columns in `Expression_Settings`, stored in bytes 13 and 14 of each pedal's record, which older tools left at zero, meaning none. Leaving the heel switches the toggle button on, resting at the heel for the delay (default 500 ms) switches it off, each only on that edge so the button can still be pressed by hand. The threshold is `Heel_Level`. Auto-engage fields in the configurator's Expression tab. The demo's bank 8 has a WAH on D that pedal 1 drives.
- **0.40 — Commands on leaving a bank.** New `Leave` command type for a bank's enter list: the commands below it are sent on leaving the bank, just before the next bank's, and on changing configuration, straight through without pauses. Marked by the low nibble of the empty command type, 4, so the layout is unchanged. `Leave` in the configurator's Bank Enter command list. The demo's bank 11 switches CC 59 on as it is entered and off as it is left.
- **0.39 — Latch or momentary.** New `Momentary_Hold` column in `Button_Settings`: a toggle button with it set latches on a tap, and held past `Long_Press_ms` goes back to its previous state on release. Stored in bit 7 of the button's LED mode byte, so the layout is unchanged and a CSV without the column packs exactly as before. "Momentary when held" box in the configurator's button editor. The demo's bank 11 button 4 becomes BOST, a boost using it.
- **0.38 — Cycle buttons.** New `Cycle` command type: in a button's short press list, each `Cycle` starts a new state, and every press sends the next state's commands, round and round, with the state's label on the display. The labels live in a new table of 48 four character labels at the end of the configuration, in space the slot already had, so nothing moves; the tools read and write it, and read older dumps without it. The virtual pedal and `GET_STATE` report the label shown. `Cycle` in the configurator's short press command list, with a field for its label. The demo's bank 11 D becomes a cycle button through four amp channels, in place of a second SysEx button.
- **0.37 — Setting the tempo.** The `Tap` command takes the new `KeyMode` values `Set`, to set the tempo to a BPM, for instance on entering a bank, and `Up`, `Down`, `Up Repeat` and `Down Repeat`, to step it by a number of BPM, repeating while held. The configurator's `Tap` menu offers them, with a BPM or step field to match; its `Bank` action menu no longer jumps back to the old action when changed. The demo's bank 6 has BPM+ and BPM- on C and D, in place of a second Start and Stop, and holding SYNC sets 120 BPM. The configuration layout is unchanged.
- **0.36 — Tap LED.** Buttons with a `Tap` command flash on every beat, `Clock` buttons only while the clock runs. The beat follows the host's clock under `Clock_Follow`, the pedal's clock while it runs, and otherwise the tempo running freely from the last tap. The flash is an overlay in the LED interrupt, so the button's own LED state is untouched underneath; the LED levels read over USB include it. Nothing to configure and the configuration layout is unchanged.
- **0.35 — Repeat while held.** `CCInc` and `PCInc` commands take the new `KeyMode` values `Up Repeat` and `Down Repeat`, which fire them again while the button is held: after 500 ms, then from every 200 ms speeding up to every 50 ms, without resending a value that has stopped at an end. It works for whichever list fired, short, long or double press. The flag is the top bit of the step byte for `CCInc`, which never used it; for `PCInc` it is two new Bank Select MSB markers, 0x83 and 0x84, because the top bit of byte 1 already means toggle. The configurator's direction menu offers the new values. The demo's VOL+ and VOL- repeat, with a step of 2 instead of 5. The configuration layout is unchanged.
- **0.34 — CC ramps.** New `Ramp` command type: the `CC` command right below it walks to its value over `Duration` milliseconds instead of jumping, to `OnValue` on the press and back to `OffValue` on the release or when a toggle is switched off, starting from the other end or from wherever a ramp still running on the same channel and CC got to. Like `Wait`, a ramp is marked by the low nibble of the empty command type, low nibble 2, with its time in 10 ms units in bytes 2 and 3; byte 1 stays clear, so it never reads as a toggling command. The steps go out from the main loop, at most one every 5 ms per ramp, eight ramps at once, so nothing else stops meanwhile; `Panic` stops them all. `Ramp` in the configurator's command list. The demo's KNOB bank swaps FINE and JUMP for SWEL, a 2 s toggle swell, and RISE, a half second momentary rise. The configuration layout is unchanged.
- **0.33 — Expression output range.** New `Out_Min` and `Out_Max` columns in `Expression_Settings`, stored in bytes 11 and 12 of each pedal's record, which older tools left at zero and the firmware reads as the full range when both are. New `Exp1_Min`, `Exp1_Max`, `Exp2_Min` and `Exp2_Max` columns in `BankExpression_Settings`, stored in a new table of four bytes per bank after the CC and channel one, erased (`0xFF`) to keep the pedal's own. The ends map exactly and a range can run backwards; toe and heel levels still follow the pedal's position. Output range fields in the configurator's Expression tab and Min / Max columns in its Banks tab. The demo's FX and KNOB banks use it.
- **0.32 — Exclusive groups.** New `Group` column in `Button_Settings`: switching on a toggle button of a group first switches off, by pressing them as if by foot, the other buttons of the group in the bank that are on. Stored in bits 4–6 of the button's LED mode byte, whose low nibble keeps the mode and which older configurations always left at zero, so the layout is unchanged and a CSV without the column packs exactly as before. Exclusive group drop-down beside the LED mode in the configurator's button editor, carried by Copy / Paste bank. The demo's looper bank groups TRK1 to TRK4.
- **Back up all slots.** `Backup_Slots.py` and the configurator's **Back Up All Slots** and **Restore Backup** copy every configuration slot to a folder, one CSV per slot, and write them back, validating every file first and restarting the pedal once. The slot reading and writing that `Flash_to_CSV.py` and `CSV_to_Flash.py` each did on their own now lives in `python/lib/slotIO.py`, shared by all three. Tested against a simulated pedal in the test suite, byte for byte, and on an MP-100. No firmware change.
- **0.31 — Next and previous preset.** New `PCInc` command type: a Program Change one step up or down from the program last selected on the channel, with a step, a last program and optional wrapping, shown on the display as `PC 6`. The firmware remembers, per channel, the last program sent by a PC command or a bank being entered, or received from the host over USB. The command types were all taken, so it is a PC whose Bank Select MSB byte holds 0x81 or 0x82, values that byte could already hold to mean no Bank Select and that the tools never wrote; an ordinary Program Change is unaffected. The configuration layout is unchanged. The demo's program change bank has PREV and NEXT on C and D, and its channel 5 and 16 examples move to 3 and 4.
- **0.30 — Pauses inside a command list.** New `Wait` command type: the commands below it in the list are sent `Duration` milliseconds later, in steps of 10 up to 2550, for the device that drops a Control Change arriving right behind a Program Change. All sixteen command types were taken, so a pause is marked by the low nibble of the empty command type: a command of all zeroes stays an empty command, and the byte holding the pause is not the one whose top bit marks a toggling command, so nothing in an older configuration reads as one. Command lists are no longer sent in a single loop: `run_cmd_list` sends up to the pause and leaves the rest in a table of four pending lists that the main loop drains, so switches, expression pedals and the display keep working while a list waits. A button released mid-list has its release pass held back until the list finishes, a second press first sends whatever was left, and a configuration switch now waits for every list to finish, since their commands live in the configuration being left. Pauses work in the short, long and double press lists, the bank enter list and the bank switch lists. The configuration layout is unchanged.
- **0.29 — Works without a computer.** Powered from a USB charger or a power bank the pedal booted and went dark, ignoring every switch: with no host the USB bus is idle from the start, the core reported a suspend a few milliseconds after boot, and the suspend handler switched the display off and blocked the switches. Suspend is now only honoured when a host had configured the device; otherwise the pedal keeps running, DIN MIDI works and USB MIDI is discarded. A sleeping computer still turns the display and LEDs off. Reported in harvie256/midi-commander-custom#40.
- **0.28 — Expression per bank.** New `BankExpression_Settings` section, four bytes per bank after the setlist: each bank can give each expression pedal its own CC and channel, or silence it (`0x80`); erased flash keeps the pedal's own settings, so older configurations are unchanged. A silenced pedal's toe and heel switches keep working, and after a bank change a pedal follows its next movement rather than jumping to its new target. CC and channel columns per pedal in the configurator's Banks tab, carried by Copy / Paste bank.
- **0.27 — Virtual pedal.** SysEx `PRESS_BUTTON` (66) presses or releases any of the ten switches: the switch is marked as held and the switch scan's change flag is raised, so every press type and the bank switches behave exactly as with a foot; a press left down lets go after 10 seconds. SysEx `GET_STATE` (68) returns the bank, slot, toggles, bank name, button labels, the level of all ten LEDs, a screen frame counter and whether the pedal is asleep; `GET_SCREEN` (70) returns the display buffer in sixteen parts packed 7 in 8, fetched only when the frame counter moves. New Virtual Pedal tab in the configurator, drawn like the pedal.
- **0.26 — Double press.** New `DoublePress_Settings` section and `Double_Press_ms` setting (global byte 36): two presses within the window fire a third command list per button. The slot's 12 pages had 496 bytes free and slot 1 cannot grow without moving the journal and the other slots, so each slot gets five more pages in the gap between the firmware and slot 1, `0x08016000` to `0x08020000`; the linker scripts now cap the firmware at 76 kB so it can never grow into them. To the tools they continue the image from offset 24576: SysEx write and read map there, and erasing a slot erases them too. Global byte 37 marks a slot whose double press area the tools wrote, so leftovers from older firmware are never read as commands; on the test pedal that area held 928 bytes of them. `CSV_to_Flash.py` skips chunks that are already erased. The `SELECT_SLOT` answer also reports the flash size the chip declares: a Harley Benton MP-100 reports 256 kB, not the 512 kB the hardware notes give, so nothing is stored above 256 kB.
- **0.25 — LEDs that follow the computer.** `LED_Feedback` (global byte 35) lets a CC, Note On or Note Off arriving over USB set the toggle buttons that send it, in every bank and in the long press list, without sending anything. A CC is on when nearer the `OnValue` than the `OffValue`. The USB interrupt queues the message and the main loop applies it. The demo turns it on.
- **0.24 — Four configurations.** The pedal keeps four configuration slots. Slot 1 stays at the address the configuration always had, so a pedal using only one behaves exactly as before; slots 2 to 4 follow the state journal and end at 256 kB. New `Bank` command modes `Config` and `NextConfig` switch between them from a button, waiting until every switch is released, flushing timed releases, starting the new configuration from bank 0 and showing its number and name. A new SysEx, `SELECT_SLOT` (64), chooses the slot the next erase, write and read act on and reports which slots hold a configuration; without it the tools act on the active slot, so older tools keep working. Writes are now bounds checked against the slot. `CSV_to_Flash.py` and `Flash_to_CSV.py` take `--slot`, and the configurator has a Slot selector. **The state journal changes format** to record the active slot, so the first boot after updating forgets the remembered bank and toggles once. Two bugs found on the way: expression pedal toe and heel switches started armed as if the pedal were at the heel, so a pedal resting past its toe threshold, such as an inverted pedal at rest, pressed its toe button at initialisation, which on batteries meant at every power on; they are now armed from the first real reading. And the tools reused a slot selected by an earlier run instead of the active one when no slot was given.
- **0.23 — Scenes.** New `Scene` command type: one press sets any of the bank's toggle buttons on or off, pressing only those that are not already in the wanted state, so their commands, LEDs and display follow as if pressed by foot and a repeated scene is silent. Stored in two bytes of the command, written in the CSV as eight characters, `+`, `-` or `.`. A scene cannot recurse into another, and a bank change queued by the scene's own button is held until it finishes. The configuration layout is unchanged.
- **Configurator: copy and paste banks.** Copy bank and Paste bank in the Buttons tab duplicate everything that belongs to a bank onto another one, except its name, after a confirmation. The logic lives in `python/lib/bankClipboard.py` and is covered by tests that pack the result and check the target bank's bytes match the source and nothing outside it moved. No firmware change.
- **0.22 — See relative CC values.** A `CCInc` button used to change a value nobody could see. The CC number and the value just sent now replace the bank's info line for a second and a half, as `CC7=69`, or `C120=127` for three digit CC numbers so it still fits. Firmware only: the configuration is unchanged.
- **0.21 — Panic.** New `Panic` command type: All Sound Off and All Notes Off on all sixteen channels, to USB and DIN, packed into two USB packets and two serial buffers so a single press cannot exhaust the transmit buffers. A command type only, so the configuration layout is unchanged and 0.20 configurations need no re-flash.
- **0.20 — Follow the host's clock.** `Clock_Follow` makes the pedal measure the MIDI clock arriving over USB over two beats and adopt its tempo, shown on the display as `EXT` and a tempo for 1.5 seconds when it is picked up or changes. While the host's clock runs the pedal never adds a second clock to the stream: it stays silent when realtime passthrough already forwards the host's clock to DIN, and re-clocks DIN at the host's tempo when it does not. When the host's clock stops, the pedal's own clock, if running, carries on at the tempo it adopted, so a looper behind it keeps time. A single byte in the global settings area, so nothing moves and configurations from 0.19 need no re-flash.
- **0.19 — Setlist.** `Setlist_Mode` and the new `Setlist` section make Bank Up / Down, and relative `Bank` commands, step through a stored order of banks instead of their numbers, wrapping at both ends, with a Setlist tab in the configurator. Absolute jumps are unchanged. The section is appended after everything else, so nothing moves: a configuration written for 0.18 still reads correctly, with the setlist empty and switched off. The configuration grows by 32 bytes to 24080, within the same 12 flash pages.
- **0.18 — Idle sleep.** `Sleep_After_Min` switches the display and the LEDs off after a set number of minutes without a press or a pedal movement, and anything you do brings them back without losing the press that did it. The firmware already had a sleep path, but only for USB suspend, which never fires on batteries because there is no host. The main loop now waits for an interrupt instead of spinning, so the processor is stopped most of every millisecond even while awake. An expression pedal only counts as activity once it has moved several steps: a connected pedal sitting still was measured drifting one unit either side of its resting value, several times a minute, which was enough to hold off sleep for ever. The CC is still sent on every change, it is only the activity marker that is filtered. **Configuration format change:** the global area was full, 16 bytes of settings and 16 of name, so it grows to 48 and every section after it moves; the configuration goes to 24048 bytes, still within the same 12 flash pages. Re-flash your configuration after updating, or the pedal will read it shifted.
- **0.17 — MIDI from the bank switches, and no more freeze.** The Bank Down and Bank Up switches have their own command lists for a short and a long press (`BankSwitch_Settings`, Bank Switch tab), and `Bank_Switch_Mode` decides whether they also change bank or stop changing bank altogether, which makes the pedal a ten switch controller. A full MIDI transmit buffer no longer calls `Error()`, which disabled interrupts and spun forever: the pedal froze until it was power cycled. The message is dropped instead, and the number of buffers goes from 20 to 32 so it rarely comes to that. These answer two long-standing requests in the original project, [#39](https://github.com/harvie256/midi-commander-custom/issues/39) and [#40](https://github.com/harvie256/midi-commander-custom/issues/40). A new test parses the firmware's own `CFG_*` macros and compares every section offset with the Python tools, so the two can no longer drift apart. A Program Change with an empty Bank Select no longer sends one: the packer wrote a 0 into the byte the firmware reads, so **every** Program Change sent an unwanted Bank Select LSB of 0, which selects a bank on devices that listen to it. An explicit `0` still sends it, and a `Bank_Select` with `BankSelectHighByte` set still sends both bytes. This one is a tooling fix rather than a firmware one, so re-flash the configuration to pick it up. **Configuration format change:** it grows by 160 bytes to 24032, still within the same 12 flash pages; re-flash after updating.
- **Active Sensing, verified.** Not a code change in 0.17, but worth recording: hosts that send Active Sensing every 300 ms, notably the Kemper Profiler Player, stall the stock firmware because it never drains what arrives over USB. The receive path here walks every 4 byte event, handles or discards each one, and re-arms the endpoint unconditionally, so nothing accumulates. Measured on the pedal with 3599 messages, including Active Sensing at the host's own rate, a 2000 message burst and a mixed stream; the pedal answered a SysEx version request after every phase.
- **0.16 — Journal wear.** The saved-state journal now spans four flash pages instead of one, so a fill-and-erase cycle absorbs 124 saves and the journal is good for over a million of them. This replaces the idea of moving it to the external EEPROM: the EEPROM shares the I2C bus with the DMA-driven display and holds only 896 free bytes, so it would have meant coordinating blocking writes with screen updates for no practical gain, while spare flash costs nothing.
- **0.15 — Expression pedals as switches.** Reaching the toe, or returning to the heel, taps a button of the current bank (`Toe_Button`, `Toe_Level`, `Heel_Button`, `Heel_Level`), so a pedal gives you two more footswitches while still sending its CC. Stored in bytes that were already reserved in each pedal's record, so the configuration does not grow.
- **0.14 — Tap tempo and MIDI clock.** New `Tap` command type, in Tap or Clock mode. The clock is generated from the millisecond tick with fractional accumulation, so its average tempo is exact and it does not drift, and the bytes are emitted from the main loop rather than an interrupt. USB MIDI transmission was rewritten around a queue: it used to busy-wait for the previous packet, which made sending from an interrupt impossible and could hang for good if the USB interrupt never ran.
- **0.13 — Relative CC and custom SysEx.** New `CCInc` command type nudges a CC value by a step per press, with optional wrapping and a per-slot running value. New `SysEx` command type sends one of sixteen stored messages from the new `SysEx_Strings` section, to both USB and DIN, with a SysEx tab in the configurator that validates the bytes as you type.
- **0.12 — Bank automation.** Each bank can send commands when entered (`BankEnter_Settings`, Bank Enter tab), typically a Program Change for its patch. An incoming Program Change or Control Change over USB can select a bank (`Bank_Change_Mode`, `Bank_Change_Channel`, `Bank_Change_CC`), so a DAW or another pedal drives this one. **Configuration format change:** it grows to 23 kB over 12 flash pages; re-flash after updating.
- **0.11 — 32 banks and bank navigation.** Banks go from 8 to 32. A short press on Bank Up / Down steps one bank and a long press jumps `Bank_Jump_Step` banks (default 8), both wrapping around. A new `Bank` command type jumps to a given bank or moves relative to it, applied after the button's other commands, so one bank can act as a setlist index. **Configuration format change:** the configuration grows to 22 kB over 11 flash pages and takes about 13 seconds to transfer; re-flash it after updating. Configurations written for 8 banks still flash, leaving the new banks empty. The per-bank toggle bitmasks and the saved-state journal widened accordingly.
- **0.10 — Media keys.** New `Media` command type sends USB consumer-control keys (play/pause, next, previous, stop, volume, mute, record, ...). The HID interface now carries two reports with IDs (keyboard and consumer control) on a 16-byte endpoint, and gets the USB packet-memory allocation it had always been missing.
- **0.9 — LED brightness.** `LED_Brightness` and `LED_Rest_Brightness` (percent) dim the LEDs with a 500 Hz software PWM on TIM2; the rest level lets Reverse/AlwaysOn buttons look different when idle and when active.
- **0.8 — Expression pedal calibration.** `Expression_Settings` section and Expression tab with live view and one-click calibration: per pedal end points, curve, invert and channel. SysEx `GET_PEDALS` (62).
- **0.7 — Long press.** Second command set per button (`LongPress_Settings`), `Long_Press_ms`, separate toggle state, Short/Long switch in the editor.
- **0.6 — Button labels on the display.** `Label` column, 2×4 grid mirroring the pedal, inverted cells for active toggles. Flash page size corrected to the real 2 kB (configuration area is 6 kB).
- **0.5 — Remember state.** `Remember_State` restores the last bank and toggles at power on, journaled in a dedicated flash page. GitHub Actions CI added.
- **0.4 — USB-to-DIN MIDI thru.** `USB_MIDI_Thru` forwards channel, system common and foreign SysEx messages to the DIN output. The USB receive parser was rewritten to walk 4-byte USB MIDI events, fixing a buffer overflow on long SysEx from other devices.
- **0.3 — LED modes moved to their own table.** Previously `Light_Mode` was encoded in bit 7 of two bytes of the button's first command, which corrupted that command depending on its type (a CC with AlwaysOn never sent its off value, a Note got a long duration, a Key became a toggle or sent the wrong key, a PC without Bank Select MSB read as Reverse). **Configuration format change:** re-flash your configuration after updating.
- **GUI rework.** Bounded fields as drop-downs and check boxes, range-checked numbers, type-aware command editor with the previously missing Bank Select, Bank Select MSB, Velocity, Start and Stop fields, automatic apply, save before flash.
- **0.2 — Configuration read-back.** `Flash_to_CSV.py` and **Read from Device**; SysEx `READ_FLASH` (56) and `GET_VERSION` (58).
- **0.1B fixes.** Spurious Note Off after a timed pitch bend (missing `break`); global `MIDI_Channel` was 0-based while every other channel field is 1-based; `customtkinter` added to `requirements.txt`; round-trip tests added.
- **0.1B Sleep and earlier** (arasan95, harvie256 and contributors): GUI configurator, LED modes, HID keyboard, dual expression pedals with pull-down switching, sleep mode, PlatformIO build, DMA display driver, 10 commands per button, flash-based configuration and the SysEx flashing tool.

---

## Still to come

- Battery management has not been considered; battery operation is untested.

Ideas and bug reports are welcome through the [issues](https://github.com/Charles5150/midi-commander-custom/issues/new/choose) and [discussions](https://github.com/Charles5150/midi-commander-custom/discussions).

---

## Acknowledgements

- @harvie256: project founder, original firmware, flash-based configuration and SysEx flashing tool
- @eliericha: expansion to 10 commands per button, Python tooling and macOS documentation
- @redcloud80: DMA and interrupt driven display driver
- @BenjaminJensen: the info on expression pedals
- Ivaylo Milanov: PlatformIO migration, DFU packaging workflow and expression pedal ADC pin map
- @arasan95: GUI configurator, LED light modes, HID keyboard output, dual expression pedal filtering and sleep mode
