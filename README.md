# Midi Commander Custom Firmware

Custom firmware and configuration tools for the **MeloAudio Midi Commander** foot controller, sold in Europe as the **Harley Benton MP-100**: 32 banks of eight buttons, up to ten MIDI commands per press plus ten more on a long press and ten on a double press, two switches pressed together, tap tempo and MIDI clock, USB keyboard and media keys, two calibrated expression pedals, button labels on the display, USB-to-DIN MIDI thru, and a desktop configurator that talks to the pedal over USB.

This repository is a fork of [arasan95/midi-commander-custom](https://github.com/arasan95/midi-commander-custom), which in turn builds on the original project by [harvie256](https://github.com/harvie256/midi-commander-custom). None of this would exist without their work and that of the other contributors listed in the [Acknowledgements](#acknowledgements). Thank you all.

The firmware replaces the stock MeloAudio one but never touches its bootloader, so you can always flash the vendor image back. Its configuration lives in the microcontroller's own flash, so the stock configuration stored in the external EEPROM is left untouched.

---

## Contents

1. [Features](#features)
2. [Getting started](#getting-started)
3. [The configurator](#the-configurator)
4. [Configuration reference](#configuration-reference)
5. [The display](#the-display)
6. [Editing on the pedal](#editing-on-the-pedal)
7. [Command line tools](#command-line-tools)
8. [Building and flashing from source](#building-and-flashing-from-source)
9. [Changelog](#changelog)
10. [Still to come](#still-to-come)
11. [Acknowledgements](#acknowledgements)

---

## Features

- **32 banks × 8 buttons.** A short press on Bank Up / Bank Down steps one bank, a long press jumps a configurable number of banks, and both wrap around. A `Bank` command can also jump straight to a given bank, so one bank can act as a setlist index. Each bank has a name shown on the display.
- **The Bank Up / Down switches send MIDI too.** Each has its own command list for a short and a long press, the same in every bank. `Bank_Switch_Mode` chooses whether they also change bank, or stop changing bank altogether, which turns the pedal into a plain ten switch controller.
- **Up to 10 commands per button press**, sent in order. Any mix of Program Change (with optional Bank Select), Control Change, Note, Pitch Bend, Start, Stop, USB keyboard keys and media keys, each MIDI command on its own channel.
- **Long press.** A second set of up to 10 commands fires when a button is held past a configurable time (default 500 ms). Buttons without long press commands react instantly, as before.
- **Pauses between commands.** A `Wait` command spaces out the commands of a button, for the device that drops a Control Change arriving right behind a Program Change. The pedal keeps reading switches and pedals while it waits.
- **CC ramps.** A `Ramp` command makes the Control Change below it walk to its value over a time, up to about 11 minutes, instead of jumping: a volume swell or a slow filter sweep from a single press, and back again on the release or when a toggle is switched off.
- **Tempo-synced LFO.** An `LFO` command makes the Control Change below it swing up and down by itself, one cycle per note division of the tempo (from a sixteenth triplet to four bars) in a sine, triangle, saw, square or random shape: tremolo, filter sweeps and auto-pan that follow your tap or the host's clock.
- **Values and conditions.** The pedal keeps eight values of its own, and a `Value` command sets one, adds to it or takes away, round and round within a top you choose. An `If` command above a command holds it back unless the test holds: a button's toggle on or off, one of those values against a number, or the bank you are on. One button can then do different things depending on another — a shift layer — and a counter on a long press can walk a set of patches one press at a time.
- **Step sequencer.** A run of `Seq` commands turns the Control Change or note below it into a sequence: a value a step, an eighth note or whatever division you choose, round and round while the button is held or its toggle is on. Rests included, so it is a rhythm as much as a melody: a stuttered filter, an arpeggio, a pattern of amp switches, all in time with the tap tempo or the host's clock.
- **One channel for everything, or several at once.** A global channel setting moves a whole configuration to another channel, and a `Chan` command sends the command below it to as many channels as you like.
- **Recorder and sequencer control.** `MMC` commands work the transport of a DAW or a recorder — play, stop, record, rewind, locate to a time — and `Song` commands pick the song of a drum machine or a sequencer and where in it to start.
- **Macros.** A command list stored once and called from many buttons: the ten commands that set up the band's whole rig live on one button and every bank that wants them spends a single command. Macros call macros, pauses inside them are kept, and it is the one feature that gives configuration room back instead of taking it.
- **Global buttons.** One bank set aside holds the buttons that should be the same wherever you are — the tuner, panic, the tap — and any button of any other bank marked global takes everything from it: its commands, its label, its light and whether it is on. Written once, changed once, and on all night under the same foot.
- **Cycle buttons.** One button steps through several states, each with its own commands and its own label on the display: the four channels of an amp on a single switch, say, one press each, round and round.
- **Momentary or toggle** behaviour per command, and timed auto-release (up to 1.27 s) for Notes, Pitch Bend and keys.
- **Second page in a bank.** A button shows another bank's eight buttons and labels in place of the current ones, and back again, like a shift key, doubling what a song holds. It is still the same bank: Bank Up / Down, the expression pedals and the text from the computer carry on as they were.
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
- **Expression target from a button.** A command changes what an expression pedal sends, its CC and channel, or silences it, so one pedal can be the wah, then the volume, then a parameter, within the same bank; as a toggle, switching it off gives the pedal back.
- **Auto-engage wah.** Moving an expression pedal up from the heel switches a button on, and resting at the heel for a moment switches it off again, like the auto-engage wahs of Fractal and Line 6: no stomping on the wah before using it.
- **Expression output range.** A pedal can send only part of the range, 40 to 127 for a volume that never drops to silence for instance, or run backwards; per pedal, and per bank on top of that.
- **Pitch Bend and 14-bit CC from a pedal.** An expression pedal can send Pitch Bend, for a whammy, or a 14-bit CC pair, with 16384 steps instead of 128, for sweeps without zipper noise on synths and plugins that read them.
- **Virtual pedal.** The configurator draws the pedal as it is built, and lets you press its switches with the mouse, tap, hold or double click, while its screen, pixel for pixel, and its LEDs are read back from the pedal, so a configuration can be tried without standing on it.
- **Double press.** A third command list per button, fired by two quick presses, alongside the short and the long press.
- **Two switches together.** Pressing a pair of switches at once, 3 and 4 with one foot for instance, runs a list of its own instead of what either switch does alone, the way Boss and Morningstar controllers reach the tuner or the looper. Up to twelve pairs, in every bank or in one, and only the switches of a pair wait to see whether the other one follows.
- **Safe mode.** Hold any of the eight command switches while the pedal powers on and it starts without sending a thing: no bank enter commands, no saved bank or toggles brought back, no Kemper beacon, no expression pedal position. It still changes bank, answers its buttons and opens the on-pedal editor, so a configuration that mutes the amp or upsets the rig at start-up can be put right with no computer at hand. See [Safe mode](#safe-mode).
- **LEDs that follow the computer.** With `LED_Feedback` on, a CC or a note arriving over USB lights or darkens the toggle buttons that send it, so the pedal shows what is really on when an effect is changed from a DAW or an amp editor.
- **Pressed from the computer.** With `Remote_Mode` on, ten CCs or notes arriving over USB press the ten switches, held for as long as the host holds them, so a DAW, MainStage or a script can drive the pedal's own logic: toggles, long and double presses, bank changes, LEDs and display.
- **A banner at power on.** The configuration's name and the firmware version can cross the display in large letters as the pedal starts, so you see at a glance which configuration came up. Or a text of your own, up to 60 characters, that the pedal keeps whatever configuration is loaded: a band, a show, a phone number in case it gets lost. Any switch cuts it short, and the pedal answers from the first press. Turn it on with `Boot_Banner`; see [The banner's own text](#the-banners-own-text).
- **Written on by the computer.** A DAW, MainStage or a script can put the patch or song name on the display over SysEx: in place of the bank name, of its info, or across the whole top line in large or small letters, until the bank changes, for good, or for a moment. A name longer than its place scrolls across it once, when it arrives and whenever a bank is entered, and then shows its beginning. `Send_Text.py` sends it from a terminal, or prints the bytes for a host to send.
- **Follows the host's clock.** With `Clock_Follow` on, the pedal measures MIDI clock arriving over USB, adopts that tempo and flashes it on the display for 1.5 seconds, and keeps its own clock out of the way while the host's is running. If the host's clock stops, the pedal's carries on at the same tempo.
- **Preview a bank before going there.** With `Bank_Preview` on, Bank Up / Down only show the bank they would go to, its name inverted on the display, and send nothing; one of the eight buttons confirms it. Brushing a bank switch in the middle of a song cannot change the patch, and a bank left unconfirmed goes back by itself.
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
- **Ready for the Line 6 HX Stomp.** A template with a preset per bank, snapshots, footswitches FS1–FS5, tuner, tap tempo and the looper, using the HX Stomp's own MIDI map so there is nothing to assign; see [the HX Stomp template](#line-6-hx-stomp-template).
- **Ready for the Kemper Profiler Player.** A template with the Player's ten banks of five rigs, its effect modules and effect buttons, tuner and tap tempo, again with nothing to assign on the Player; see [the Kemper Player template](#kemper-profiler-player-template).
- **Two way with a Kemper.** With `Kemper_Mode` on, the pedal asks the amp about itself and follows the answers: the rig you are on written beside the bank name and the effect modules lighting the buttons that switch them, whether the module was switched with your foot, on the amp or from anywhere else; see [Two way with a Kemper](#two-way-with-a-kemper).
- **Editing on the pedal.** Bank Down and Bank Up held together open an editor on the pedal's own screen: the commands of any button of any bank, short and long press, their labels, and the settings that are a number or a choice, all changed with your foot and written straight to flash. For the wrong Program Change found at soundcheck, with no laptop in sight.
- **Configuration over USB.** Flash a configuration to the pedal and read it back, from the GUI or the command line, over ordinary USB MIDI SysEx. No special driver.
- **Backups.** Copy all four configuration slots to a folder in one go, one editable CSV each, and put them all back just as easily.
- **Firmware updates with nothing held.** From firmware 0.58 the pedal restarts in DFU mode when the computer asks, so `Update_Firmware.py` or **Update Firmware…** in the configurator does the whole update in about fifteen seconds: no switches held at power on, no power cycle, and the configuration left as it is. The stock bootloader is never written.

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

5. Power cycle the pedal: after a plain `dfu-util` download the bootloader stays in DFU mode until then. The firmware version shows on the display for a moment, then the first bank. (Steps 3 to 5 can also be `Update_Firmware.py` below, which flashes a pedal already in DFU mode and starts it again by itself.)

**From then on, nothing has to be held.** With firmware 0.58 or later on the pedal, connect it as usual and run

```bash
.venv/bin/python python/Update_Firmware.py midi-commander-custom-<version>.dfu
```

or use **Update Firmware…** in the PEDAL section of the configurator. It checks the file first, and refuses one that is not an image for this pedal. Then it asks the pedal to restart in DFU mode, flashes it and starts it again, and says which version it came back with. A pedal already in DFU mode, put there by hand or by an update that did not finish, is flashed straight away.

How it works: the stock bootloader is ST's DFU demo, which starts the firmware only when Bank Down and D are up **and** the firmware's first word, its initial stack pointer, looks valid. Asked over SysEx, the firmware writes zero over that word and restarts, so the bootloader stays in DFU mode, and the new image brings a good word back. While the pedal waits in DFU mode its display says **FIRMWARE UPDATE**. If nothing is flashed it keeps starting in DFU mode, as though the switches were held, until something is.

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
- **Pedal: Slot** chooses which of the four configuration slots the two buttons below it use. `Active` means the one the pedal is running; flashing one slot never touches the others. **Read from Device** pulls that configuration from the connected pedal into a CSV you choose, and loads it. **Flash to Device**, the one red button, saves the CSV, transfers it to the pedal and reboots it. **Back Up All Slots** reads every slot that holds a configuration into a new dated folder, one CSV per slot, and **Restore Backup** writes such a folder back, each file to its own slot, after showing which ones it will replace. **Update Firmware** flashes a `.dfu` file, with nothing held on firmware 0.58 or later (see [Getting started](#1-flash-the-firmware)).

The tabs follow the order a configuration is usually built in. Each starts with a one line summary; the **?** next to it opens the details.

**Buttons** — pick a bank, then a button from the eight laid out as on the pedal, 1 to 4 on top and A to D below; the one being edited is highlighted. At the top you set its **display label**, **LED light mode** and **exclusive group**, and tick **Momentary when held**, **Flash at the tempo** or **Global**; below, ten command slots A–J. Choose a slot's command type and only the fields that type uses appear. **Short press / Long press / Double press** switches the slots between the three command sets of the button. Edits are kept in memory automatically when you switch button, bank or tab. **Copy bank** and **Paste bank** duplicate a whole bank onto another: labels, LED modes, groups, short, long and double press commands and the commands sent on entering the bank. The target becomes identical to the source, so anything it had that the source does not is removed, and its name is kept, since a copy is usually the start of a variant. Pasting asks for confirmation first.

<img src="docs/images/gui_button_config.png" width="500">

**Banks** — the 4 character name and 8 character info line of each bank, and where the expression pedals send while it is selected: a CC and a channel per pedal, each `Default` to keep the pedal's own, or `Off` for the CC to silence the pedal in that bank, and the lowest and highest value it sends there, left empty to keep the pedal's own range.

**Bank Enter** — the commands each bank sends when you switch to it, and, below a `Leave` command, when you leave it.

**Bank Switch** — the command lists of the Bank Down and Bank Up switches, one per switch and press length. Combine it with **Bank switches** (`Bank_Switch_Mode`) in the Global tab.

<img src="docs/images/gui_bank_switch.png" width="500">

**Combos** — the two switch combinations, one row each: the two switches, the bank it counts in or all banks, and the list it runs, named by bank, button and short, long or double press. How long a switch waits for the other one is **Two switches together within** in the Global tab.

**Setlist** — the order Bank Up / Down follow when **Follow the setlist** (`Setlist_Mode`) is on, one drop-down per position listing every bank by number and name. The list ends at the first empty row.

**Expression** — per pedal: end points, response curve, invert, channel, the toe and heel switches, the output range, what it sends (CC, Pitch Bend or 14-bit CC) and auto-engage. **Connect live view** shows the pedal position and the CC being sent, read from the pedal in real time. To calibrate: press **Calibrate**, sweep the pedal slowly from heel to toe and back a couple of times, press **Done**; the end points are filled in with a small margin so 0 and 127 are always reached.

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
| 5 | Media keys; held, the same buttons drive a recorder instead, as MMC, Song Select and Song Position |
| 6 | Tap tempo, clock start/stop, transport, BPM up/down (hold SYNC for 120 BPM), TREM, a tremolo on CC 14 that follows the tempo, and a four note arpeggio held on STRT |
| 7 | Relative CC, up and down, with and without wrapping, VOL+ and VOL- repeating while held, and two CC ramps: a toggle swell and a momentary rise |
| 8 | Stored SysEx messages, including an empty entry that sends nothing, a WAH on D that pedal 1 switches on and off by itself, VOL on C, which turns pedal 1 into a volume pedal (CC 7) while it is on, and P2 X on B, which silences pedal 2 while it is on |
| 9 | Notes and pitch bend, with durations and toggles |
| 10 | Bank navigation from buttons, absolute and relative; B, PREV, goes back to the bank you came from |
| 11 | Several commands chained on one button, short versus long press, and a cycle button stepping through four amp channels (D), and a boost that latches on a tap and is momentary when held (4). Entering the bank sends CC 59 127 and leaving it CC 59 0; holding A mutes channels 1, 2 and 3 with one CC |
| 12–29 | A setlist: each bank selects its patch on entry and has looper controls. On song 1 (bank 12), D is PG 2, which shows bank 31 as its second page; on the other songs D is a global button, the tap from bank 30 |
| 30 | The bank set aside for the global buttons (`Global_Bank`): the tap on D, a mute toggle on C and HOME on A. Also the lists the two combinations run: a tuner toggle on B (CC 68) and the looper's clear on 4 (CC 5) |
| 31 | Song 1's second page: seven toggles, FX1 to FX7 on CC 60–66, and BACK on D. Entering the page sends CC 70 127 and going back CC 70 0 |

Both expression pedals are configured, one linear and one logarithmic and inverted, with the toe and heel acting as switches. Pedal 1 auto-engages button D, the WAH in bank 8 (and TRK4 in bank 1), switching it off after 600 ms at the heel. Pedal 2 sends a 14-bit CC pair, CC 4 and 36. CC 102–111 on channel 16 press the ten switches from the computer. Switches 3 and 4 pressed together toggle the tuner in every bank, except on song 1, where the same pair clears the looper. Bank 2 turns pedal 1 into a modulation wheel held between 20 and 100, and bank 7 silences it and makes pedal 2 a volume on channel 2 that never drops below 40, CC 7 and 39. Regenerate the file with `python3 python/make_demo_config.py` after adding a feature, so it keeps covering everything.

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

### Line 6 HX Stomp template

**`python/templates/HX_Stomp.csv`** is ready to flash for a Line 6 HX Stomp driven over the DIN output. Connect the pedal's MIDI OUT to the HX Stomp's MIDI IN and power the pedal over USB.

| Banks | Buttons |
|---|---|
| 0–29, `01A`–`10C` | Entering the bank loads the HX Stomp preset with the same name, 01A to 10C. 1 2 3 are snapshots 1–3, 4 opens and closes the tuner, A B C press FS1–FS3 and D taps the tempo |
| 30, `LOOP` | Looper: Record, Overdub, Play/Stop, Half Speed, Play Once, Undo, Reverse, then tap |
| 31, `FS` | FS1–FS5, previous and next snapshot, and the tuner |

Bank Up / Down step through the presets, and a long press jumps ten. The snapshot buttons are an exclusive group, so the LED and the display show the snapshot last picked; pressing the lit one again darkens it without sending anything. FS1–FS5 act as if you stepped on the HX Stomp's footswitch in Stomp mode, so they switch whatever is assigned to it, and the expression pedals move the HX Stomp's EXP 1 and EXP 2 controllers.

The HX Stomp has a fixed MIDI map, so it needs no assignments: under **Global Settings > MIDI/Tempo**, set the MIDI Base Channel to 1 and turn MIDI PC Receive on. The template sends:

| Function | CC | Values |
|---|---|---|
| EXP 1, EXP 2 | 1, 2 | the pedals |
| FS1–FS5 | 49–53 | 127 and 0, each one a press |
| Looper Record / Overdub | 60 | 127 records, 0 overdubs |
| Looper Play / Stop, Play Once, Undo | 61, 62, 63 | |
| Tap Tempo | 64 | 127, on the press only |
| Looper Reverse, Half Speed | 65, 66 | |
| Tuner | 68 | |
| Snapshot | 69 | 0–2 snapshots 1–3, 8 next, 9 previous |

To use another channel, change `CHANNEL` at the top of `python/make_hx_stomp_template.py` and run it again, or edit the buttons in the configurator. Presets above 10C take a Program Change with the preset number, 0 to 125.

### Kemper Profiler Player template

**`python/templates/Kemper_Player.csv`** is ready to flash for a Kemper Profiler Player. The Player has no DIN sockets: plug the pedal's USB into the Player's USB A socket, where the Player acts as host and powers it. That is the link whose Active Sensing stalls the stock firmware, which this one drains, as described above.

| Banks | Buttons |
|---|---|
| 0–9, `BK01`–`BK10` | The Player's ten banks of five rigs. Entering the bank preselects it, 1 2 3 4 A load rigs 1–5 of it, B and C press the Player's effect buttons I and II, and D taps the tempo |
| 10, `FX` | Modules A, B, DLY and REV, then the four effect buttons I to IIII |
| 11, `TOOL` | Tuner, rotary speed, delay infinity, freeze, all effects at once, delay and reverb again but keeping their tails, and tap |

Only those twelve banks are in use, so the template turns `Setlist_Mode` on and Bank Up / Down walk them and skip the empty ones; a long press jumps five. The rig buttons are an exclusive group, so the LED and the display show the rig last picked and pressing the lit one again sends nothing. Entering a bank only preselects it on the Player: the rig changes when you press one of the five, which is what keeps the sound from jumping about while you walk the banks with your foot.

The Player has a fixed MIDI map, so it needs no assignments: it listens on all sixteen channels unless **System Settings > MIDI In Channel** says otherwise. The template sends:

| Function | CC | Values |
|---|---|---|
| Wah pedal, Volume pedal | 1, 7 | the two expression pedals |
| All modules at once | 16 | 127 inverts every module |
| Module A, module B | 17, 18 | 127 and 0 |
| Delay, reverb | 26, 28 | 127 and 0, tails cut |
| Delay, reverb keeping the tails | 27, 29 | 127 and 0 |
| Tap Tempo | 30 | 127, on the press only |
| Tuner | 31 | 127 opens it, 0 closes it |
| Rotary speed, delay infinity, freeze | 33, 34, 35 | 127, and each press flips it |
| Bank preselect | 47 | 0–9, sent when you enter one of the ten rig banks |
| Rigs 1–5 of the bank | 50–54 | 1, which is what loads the rig |
| Effect buttons I–IIII | 75–78 | 127 and 0 |

To use another channel, change `CHANNEL` at the top of `python/make_kemper_player_template.py` and run it again, or edit the buttons in the configurator. The fifty rigs also answer to a plain Program Change: the Player's manual numbers them 1 to 50, which is `Number` 0 to 49 here.

### Two way with a Kemper

Everything above sends one way: the pedal tells the amp what to do and hopes it listened. A Kemper Profiler can also be asked about itself, and `Kemper_Mode` in `Global_Settings` turns that on. The pedal then sends the amp the message that asks it to report what it is doing from now on, and repeats it every five seconds, which is what tells the amp somebody is still on the other end. Two things come back and are worth seeing from the floor:

- **The rig you are on**, in the small line beside the bank name, and there it stays, bank after bank, until the rig changes. Eleven characters fit; a longer name, up to 32, [scrolls across once](#text-from-the-computer) when the rig changes and whenever a bank is entered. The pedal asks for it every second, so it is right even when the rig was changed on the amp itself.
- **Which effect modules are running.** A module switching on or off is turned into the Control Change that switches that module — 17 and 18 for stomps A and B, 19, 20, 22 and 24 for C, D, X and MOD, 26 and 28 for delay and reverb, and 27 and 29 which keep their tails — and handed to the same machinery as [`LED_Feedback`](#global_settings). Any toggle button that sends one of those ends up lit or dark like the amp, in every bank, whether the module was switched with your foot, on the amp's own buttons or from a third place. Nothing is sent back because of it, so the two cannot chase each other, and the channel does not have to match: the amp's answers carry none.

Six of the eight modules the amp reports by itself; the delay and the reverb it does not, so the pedal asks for those two every second. It asks for all eight when it starts and again whenever the rig changes.

The answers come in over USB. On a **Profiler Player** that is the very socket the pedal is already plugged into: the Player is the host, powers the pedal and speaks MIDI over it, so nothing else is needed and the [Kemper Player template](#kemper-profiler-player-template) has `Kemper_Mode` on. A Profiler head or Stage would have to reach the pedal's own MIDI input, which the hardware does not have, so there the pedal keeps talking one way as before.

**Tried without an amp.** The conversation was tested against `python/Kemper_Sim.py`, a Kemper of make believe that answers over the same USB link a Player would use: it replies to what the pedal asks and lets you change the rig or switch a module to watch the pedal follow.

```bash
.venv/bin/python python/Kemper_Sim.py
kemper> rig Brit Crunch DLX
kemper> dly
```

The numbers it speaks — the maker's `00 20 33`, the functions, the module pages and the beacon — are the ones the Profiler's MIDI documentation and the open controllers that talk to one use, and a test checks the firmware's list against the tools'. It has not been tried against a real Kemper, so if an amp ever disagrees the fix will be in that table of numbers and nowhere else.

### Global_Settings

`Label,Value` rows.

| Label | Values | Meaning |
|---|---|---|
| `MIDI_Channel` | 1–16 | Channel used by the expression pedals (unless a pedal sets its own). Buttons use the channel of each command. |
| `Global_Channel` | Off / 1–16 | Move the whole configuration to one channel: every message goes out on it instead of the channel stored in each command, pedals included. Off leaves each command on its own. A `Chan` command names its channels on purpose, so it is left alone. Default Off. |
| `RealTime_Passthrough` | Y / N | Forward MIDI Clock, Start, Continue and Stop received over USB to the DIN output. |
| `USB_MIDI_Thru` | Y / N | Forward every other MIDI message received over USB (notes, CC, PC, pitch bend, system common, other devices' SysEx) to the DIN output. |
| `ConfigName` | up to 16 chars | Shown on the display at boot. |
| `Boot_Banner` | Off / Slow / Normal / Fast | At power on, the `ConfigName`, or the pedal's [own text](#the-banners-own-text) when it has one, and the firmware version cross the display once in large letters, right to left, in place of the name under the boot animation: about 37, 74 or 110 pixels a second, some four seconds for a full name at Normal. The pedal works all along: any switch, or a press from the computer, ends it at once and does what it always does, and the bank screen comes back underneath with whatever changed meanwhile. Safe mode shows over it. Default Off. Needs firmware 0.62 (global byte 46); older firmware shows the name as before. |
| `Exp1_CC`, `Exp2_CC` | 1–127 | CC number sent by each expression pedal. Defaults 11 and 4. |
| `Bank_Up_LED_Mode`, `Bank_Down_LED_Mode` | Normal / Reverse / AlwaysOn | LED behaviour of the bank buttons (see [LED modes](#led-modes)). |
| `Remember_State` | Y / N | Power up in the last bank with all toggles as they were. |
| `Double_Press_ms` | 100–1000 | Time the second press of a double press may take. A button with double press commands in the current bank waits this long after a tap before sending its short press. Default 300. |
| `Combo_ms` | 20–250 | How long a switch of a [combination](#combo_settings) waits for the other one. Only switches that belong to a combination in the current bank wait, and only this long, before doing what they do alone. Default 80, which one foot on two switches comfortably makes. |
| `Long_Press_ms` | 100–2500 | Hold time that turns a press into a long press, on the command buttons and on Bank Up / Down. Default 500. |
| `LED_Brightness` | 1–100 | Brightness of a lit LED, in percent. Default 100. Configurations written before 0.9 read as 100. |
| `LED_Rest_Brightness` | 1–100 | Brightness of LEDs lit at rest by the Reverse and AlwaysOn modes. Default 100; set it lower to tell an active button from an idle one. |
| `Bank_Jump_Step` | 1–31 | Banks skipped by a long press on Bank Up / Down. Default 8. |
| `Bank_Preview` | 0–60 | Bank Up / Down only preview the bank. A press, or a long press, moves a candidate as it would move the bank, setlist included, and the display shows that bank's name inverted, white with black letters, over its button labels; nothing is sent, neither the bank's commands nor the bank switch's own. The first of the eight buttons to go down confirms it: the pedal goes there as Bank Up / Down would have, leave and enter lists included, and that press does nothing else, nor does its release. Stepping back to the bank you are in drops the preview, and so does leaving it this many seconds without a button, the bank you are in coming back on the display. A bank change from MIDI, or the editor opening, drops it too. Tempo readouts and texts from the computer wait until it is over. With `Bank_Switch_Mode` at MIDI only the bank switches do not change bank, so there is nothing to preview. 0 is off, the default. Needs firmware 0.66 (global byte 47). |
| `Bank_Change_Mode` | Off / PC / CC | Let an incoming Program Change, or Control Change, select a bank. |
| `Bank_Change_Channel` | Any / 1–16 | Channel the pedal listens on for those messages. |
| `Bank_Change_CC` | 0–127 | CC number that selects a bank, when the mode is CC. Its value is the bank. |
| `LED_Feedback` | Y / N | A Control Change, Note On or Note Off arriving over USB puts every toggle button whose `CC` or `Note` command has the same channel and number into the state it describes: its LED, its display cell and what its next press sends follow. Every bank is updated, and the long press list too. A CC counts as on when its value is nearer the command's `OnValue` than its `OffValue`; a command without an `OffValue` only reacts to its `OnValue`. A Note On with a velocity is on, a Note Off or velocity 0 is off. Only the state changes: nothing is sent, so a host that echoes the pedal's messages back causes no loop. While asleep the state is kept and the LEDs come back right on waking. Default N. |
| `Remote_Mode` | Off / CC / Note | Let the computer press the switches. Ten numbers in a row from `Remote_First` stand for 1, 2, 3, 4, A, B, C, D, Bank Down and Bank Up. A CC of 64 or more, or a Note On, holds the switch down; a CC below 64, a Note Off or a Note On with velocity 0 lets it go. The press goes through the same path as a foot, so a hold becomes a long press, two quick taps a double press, and Bank Up / Down follow `Bank_Switch_Mode` and the setlist. A host that only sends the press, never the release, leaves the switch down until it lets go by itself after 10 seconds, so send both. Messages used this way go no further: not to the DIN output, nor to `LED_Feedback` or bank selection. Default Off. |
| `Remote_Channel` | Any / 1–16 | Channel the pedal listens on for those messages. Keep it apart from the channels the buttons send on if `LED_Feedback` is on. |
| `Remote_First` | 0–118 | CC or note number for switch 1; the other nine follow. Default 102, so CC 102–111, numbers no device uses by convention. |
| `Clock_Follow` | Y / N | Measure MIDI clock arriving over USB, over two beats, and adopt its tempo; the display shows it as `EXT` and a tempo for 1.5 seconds when the clock is picked up or its tempo changes by two BPM or more. While that clock keeps arriving the pedal sends no clock of its own: with `RealTime_Passthrough` on the host's clock already reaches the DIN output, and with it off the pedal re-clocks the DIN output at the host's tempo. Half a second without a clock counts as stopped, and the pedal's own clock, if running, continues at the adopted tempo. Default N. |
| `Setlist_Mode` | Y / N | Bank Up / Down, and relative `Bank` commands, follow the order in the `Setlist` section instead of the bank numbers. From a bank that is not in the list, Up enters at its first entry and Down at its last. `GoTo` and bank selection from incoming MIDI still go to the exact bank. Default N. |
| `Sleep_After_Min` | 0–60 | Minutes of inactivity before the display and LEDs go out. 0 turns it off. A press or a moved expression pedal wakes it and still does what it was asked to. |
| `Bank_Switch_Mode` | Bank / Bank+MIDI / MIDI only | What the Bank Up / Down switches do. `Bank` is the original behaviour, they only change bank. `Bank+MIDI` also sends their commands from `BankSwitch_Settings`. `MIDI only` stops them changing bank, leaving a ten switch controller. Default `Bank`. |
| `Edit_Lock` | Y / N | Stop the two bank switches held together opening the [on-pedal editor](#editing-on-the-pedal), for a pedal that must not change under anybody's foot. It can only be unlocked from here, or for one session by starting in [safe mode](#safe-mode). Default N. |
| `Global_Bank` | Off / 0–31 | The bank set aside for the global buttons: a button marked `Global` in any other bank takes its command lists, its label, its light and its state from the same button of this one. See [Global buttons](#global-buttons-the-same-button-in-every-bank). Default Off, nothing redirected. |
| `Kemper_Mode` | Y / N | Talk to a Kemper Profiler both ways: the pedal asks the amp to report itself and follows what comes back, the rig you are on written beside the bank name and the effect modules lighting the buttons that switch them. See [Two way with a Kemper](#two-way-with-a-kemper). Default N, on in the Kemper Player template. |

### Bank_Naming

One row per bank, `Bank_Number` 0–31: `Bank_Name_Large` (4 characters, big font) and `Bank_Info_Small` (8 characters, small font).

### Button_Settings

One row per button, 256 rows in bank order and, within a bank, in the order `1, 2, 3, 4, A, B, C, D` (top row of the pedal, then bottom row). Columns:

- `Bank_Number`, `Button_Identifier`
- `Label` — up to 4 characters shown on the display. Empty shows the button identifier.
- `Light_Mode` — Normal / Reverse / AlwaysOn.
- `Group` — empty, or an exclusive group 1–4 (see **Exclusive groups** below).
- `Momentary_Hold` — `Y` for a toggle button that is momentary when held (see **Latch or momentary** below); empty or `N` otherwise.
- `Tempo_Flash` — `Y` for a button whose LED flashes with the beat (see **Tap LED** below); empty or `N` otherwise.
- `Global` — `Y` for a button that takes everything from the same button of `Global_Bank` (see **Global buttons** below); empty or `N` otherwise.
- Ten command slots, prefixed `A_` to `J_`, each with the fields below.

#### Command fields

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

`Start` and `Stop` take no parameters; they send MIDI Start (0xFA) / Stop (0xFC) over USB and DIN.

**When the "off" is sent**

- `Toggle = N`, `Duration = 0`: on when pressed, off when released (momentary).
- `Toggle = N`, `Duration > 0`: on when pressed, off automatically after the duration, even if still held. Notes, pitch bend and keys only; CC ignores the duration.
- `Toggle = Y`: the first press sends on, the next sends off, and so on. Toggle state is kept per button and per bank, and drives the LED.

**Keyboard keys.** `Number` is the sum of the modifiers: 1 Ctrl, 2 Shift, 4 Alt, 8 Cmd/Win (3 = Ctrl+Shift). `OnValue` is a single character (`a`, `7`) or one of `enter`, `esc`, `tab`, `space`, `backspace`, `minus`, `equal`, `leftbr`, `rightbr`, `backslash`, `semicolon`, `quote`, `grave`, `comma`, `dot`, `slash`, `f1`–`f12`. `KeyMode`: **Normal** taps the key (held for `Duration` if set); **Down** presses and leaves it pressed, **Up** releases it, both after a `Duration` delay, so one button can build combinations across several slots. `Toggle` holds the key until the next press.

**Relative CC.** `CommandType` `CCInc` sends a CC whose value moves on every press instead of being fixed. `Number` is the CC, `OnValue` the value it starts from at power on, `OffValue` the step, `KeyMode` the direction (`Up` or `Down`, or `Up Repeat` or `Down Repeat` to repeat while held, below) and `Toggle` enables wrapping past the ends instead of sticking at 0 and 127. The running value lives in memory, one per command slot, and resets to the start value when the pedal is switched off.

**Next and previous preset.** `CommandType` `PCInc` sends a Program Change one step up or down from the program last selected on its channel. That is whatever was sent last on the channel, by any PC command, by the commands of a bank being entered, or by the computer over USB, so the button always moves on from where the device really is; before anything has been sent it counts as program 0. The state is shared, so a Next and a Previous button work as a pair, and it is not kept across a power cycle. `Channel` is the channel, `KeyMode` the direction (`Up` or `Down`), `OffValue` the step (1 when empty), `Number` the last program of the range, 0 to 127 (127 when empty; a Line 6 HX Stomp, for instance, has 0 to 125), and `Toggle` makes it wrap round at the ends instead of stopping there. No Bank Select is sent. The new number shows on the display for a moment, as `PC 6`. Stored as a PC whose Bank Select MSB byte, where 0x80 and above already meant none, holds 0x81 for up or 0x82 for down; the step is in byte 1 and the last program in byte 3, with its top bit for wrapping. The demo puts PREV and NEXT on C and D of the program change bank, which sends PC 0 when entered.

**Repeat while held.** With `KeyMode` `Up Repeat` or `Down Repeat`, a `CCInc` or `PCInc` command, or a `Tap` stepping the tempo, keeps firing while its button is held, like a key on a computer keyboard: once on the press, again after half a second, then every 200 ms, each gap a quarter shorter than the one before, down to one every 50 ms. A CC value can thus cross its whole range in about three seconds with a step of 2, while a tap still moves it a single step. Only the repeating commands of the list fire again, and they skip any `Wait`. A repeat that has hit an end and cannot move any further sends nothing, so a held button does not keep resending 127. Holding a button that has long press commands makes a long press, so its short list cannot repeat; its long press list can, and so can a double press list while the second press is held. Stored as the top bit of the step byte for `CCInc`, and as the markers 0x83 for up and 0x84 for down, in place of 0x81 and 0x82, for `PCInc`. Needs firmware 0.35; older firmware ignores the repeat on `CCInc` but sends a repeating `PCInc` as an ordinary, wrong, Program Change, so update the firmware first.

**One channel, or several.** Two settings cover a rig that does not live on the channel the configuration was written for. `Global_Channel` moves everything: while it is set to a channel, every message the pedal sends goes out on it, whatever each command stores, the expression pedals included, so a configuration written for channel 1 drives a device listening on channel 9 without touching a single command. And `CommandType` `Chan` goes the other way, for one command: it names the channels in `Channel`, as `1 2 3` or `1-3`, and the command right below it is sent once on each of them, so one press mutes three devices or three amps change patch together. Naming channels is on purpose, so a `Chan` also beats the global channel: a `Chan 3` above a command keeps it on channel 3 while the rest of the configuration moves. Like a `Ramp`, a `Chan` only reaches the command directly below it, and it counts for the release too, so a momentary CC goes off on every channel it went on. Stored by the low nibble of the empty command type, 9, with the sixteen channels as a bit each: byte 2 for channels 1–7, byte 3 for 8–14 and the two low bits of byte 1 for 15 and 16. The global channel is byte 41 of the global settings, 0 meaning off. Both need firmware 0.51; older firmware ignores a `Chan` and the setting. In the demo, holding A in bank 11 mutes channels 1, 2 and 3 with one CC.

**Driving a recorder or a sequencer.** `CommandType` `MMC` sends a MIDI Machine Control message to every device on the wire, over USB and DIN: the transport of a DAW, a hard disk recorder or a drum machine, from the pedal. `KeyMode` is the action: `Play`, `Stop`, `Record` (a record strobe, the punch in), `RecordExit` (the punch out), `Pause`, `FastForward`, `Rewind`, `DeferredPlay`, `Chase`, `Eject`, `Reset`, and `Locate`, which also takes `OnValue`, where to go in seconds from the start, up to 16383 (4h33m). A `Locate` goes out as a timecode of hours, minutes and seconds with the frames at zero, so `3725` is 1:02:05. Nothing is sent back: MMC is one way here, and the pedal does not follow a recorder's position. Stored like a `Wait`, by the low nibble of the empty command type, 7, with the MMC command byte in byte 1 and the seconds in bytes 2 and 3.

**Song Select and Song Position.** `CommandType` `Song` with `KeyMode` `Select` sends a Song Select (0xF3) with the song number in `OnValue`, 0–127: the song, pattern or sequence a drum machine or a hardware sequencer should play. With `KeyMode` `Position` it sends a Song Position Pointer (0xF2) instead, `OnValue` being where in the song to start, counted in sixteenth notes, so 16 to a 4/4 bar and 0 for the top; a device usually waits there for the next Start or Continue. Neither message belongs to a MIDI channel, so there is no `Channel` to set, and both go out over USB and DIN. Put a `Select` in a bank's commands on entry and the recorder follows your setlist. Stored by the low nibble of the empty command type, 8: byte 1 says which message, bytes 2 and 3 the value. Both need firmware 0.50; older firmware ignores them, as it does an `MMC`.

**Tap tempo.** `CommandType` `Tap` with `KeyMode` `Tap` measures the tempo from the interval between presses, averaging the last four and ignoring anything outside 30–300 BPM. With `KeyMode` `Clock` the button starts or stops the clock instead, sending MIDI Start or Stop and then 24 clock bytes per quarter note to USB and DIN while it runs. Either action shows the tempo on the display for a moment, with a leading `*` while the clock is running. The tempo is not saved; it starts at 120 BPM each time the pedal is switched on.

**Setting the tempo.** With `KeyMode` `Set`, a `Tap` command sets the tempo to `OnValue` BPM, 30–300 (120 when empty). Put it in a bank's commands on entry and each bank, or each song of a setlist, starts at its own tempo. With `KeyMode` `Up` or `Down` it moves the tempo by `OffValue` BPM (1 when empty), stopping at 30 and 300, and with `Up Repeat` or `Down Repeat` it keeps moving while the button is held, faster and faster, as described under **Repeat while held** above. All of them show the new tempo on the display, and a running clock and the tap LED follow it at once. While `Clock_Follow` is following the host's clock, the host's tempo wins. These buttons do not flash with the beat. Stored in the low nibble of the `Tap` command, 2 for `Set` with the BPM in bytes 2 (low 7 bits) and 3 (the rest), 3 for `Up` and 4 for `Down` with the step in byte 2 and its top bit set to repeat. Needs firmware 0.37; older firmware takes all three as a plain tap, so update the firmware first.

**Tap LED.** Every button of the current bank with a `Tap` command in `Tap` mode, in any of its lists, flashes its LED at the `LED_Brightness` level at the start of each beat, for a quarter of a beat and at most 100 ms. A `Clock` button flashes the same way, but only while the clock is running, so its LED also tells you the clock is on. With the clock stopped the beat runs freely at the tempo and every tap re-phases it, so the flash lands with your foot; with the clock running the flash is the first of every 24 clock bytes, starting from Start; and while `Clock_Follow` is following the host's clock, it is the host's beat, counted from its Start. The flash sits on top of whatever the LED shows, so a Reverse or AlwaysOn LED lit at rest as bright as `LED_Brightness` shows no flash; set `LED_Rest_Brightness` lower to see it. It stops while the pedal sleeps. Any other button can flash with the beat too, whatever its commands are: set `Tempo_Flash` to `Y` on it, bit 2 of its LED mode byte, which configurations have always left at zero, or tick "Flash at the tempo" in the configurator's button editor. It flashes at all times, like a `Tap` button, since it is your choice rather than the clock's. Needs firmware 0.48; older firmware ignores it. The demo's bank 6 button B, SYNC, a plain CC toggle, uses it.

**Double press.** `DoublePress_Settings` gives each button a third command list, in the same format as `LongPress_Settings` and with its own toggle state; in the configurator it is the **Double press** mode of the button editor, and Copy / Paste bank carries it. Two presses within `Double_Press_ms` send it. Only buttons that have double press commands in the current bank change behaviour: a single tap on them waits for that window before sending its short press, and holding them still gives the long press, or the short press when there is none. Buttons without double press commands respond exactly as before. Needs firmware 0.26; `CSV_to_Flash.py` leaves the double press commands out, with a warning, when the pedal runs anything older.

**Configuration slots.** Two more `Bank` command modes switch configuration instead of bank. `Config` switches to the slot in `OnValue`, 1 to 4, and `NextConfig` moves to the next slot that holds a configuration, wrapping round. The switch waits until every switch is released, sends any timed release still pending so nothing is left hanging, and starts the new configuration from bank 0 with every toggle off, showing its number and name full screen. Asking for an empty slot, or for the next one when no other holds a configuration, shows a short notice instead. The active slot is remembered across power cycles whatever `Remember_State` says; the bank and toggles are only restored when the configuration being started asks for them. A slot holds a configuration when its `ConfigName` is sixteen printable characters, which the tools always write.

**Scenes.** `CommandType` `Scene` sets the toggle buttons of the current bank to a chosen state. `OnValue` holds eight characters, one per button in the order `1234ABCD`: `+` to switch it on, `-` to switch it off, and `.` or anything else to leave it alone, so `+-+..-..` turns 1 and 3 on and 2 and B off. Each affected button that is not already in the wanted state is pressed as if by foot, so its own commands, LED and display cell follow; buttons already there are not touched, so recalling the same scene twice sends nothing the second time. Buttons without a toggle command have no state and are skipped. A scene cannot trigger another scene. The configurator shows it as eight drop-downs, and the demo puts three on the long presses of the LED modes bank.

**Exclusive groups.** A button's `Group`, 1 to 4, ties it to the other buttons of its bank in the same group: switching one on switches off every other one of the group that is on, as if pressed by foot, so their off commands go out and their LEDs and display cells follow. They are switched off before the pressed button sends anything, so when the whole group drives one parameter, an amp channel CC for instance, the device ends up where the pressed button says. Pressing the lit button switches it off like any toggle, leaving the group all off. Only buttons with a toggle command take part, and only their short press; groups are per bank, so group 1 in one bank has nothing to do with group 1 in another. A scene can switch on two buttons of a group, and the last one wins. The group lives in the top bits of the button's LED mode byte, which configurations have always left at zero, so the layout is unchanged. Needs firmware 0.32; firmware before it reads a button with a group as `Normal` LED mode. The demo groups the four track buttons of the looper bank.

**Panic.** `CommandType` `Panic` sends All Sound Off (CC 120) and All Notes Off (CC 123) on all sixteen channels, to both USB and the DIN output. It takes no parameters. The 32 messages go out packed into two USB packets and two serial buffers, so a panic cannot itself run out of transmit buffers. It does not reset toggle states or controllers. A long press is a good place for it, where it cannot be hit by accident; the demo puts it on a long press of STOP in the tempo bank.

**Pauses.** `CommandType` `Wait` sends nothing: it pauses the commands that follow it in the list. `Duration` is the pause in milliseconds, in steps of 10 and up to 2550. It is what a device that drops a Control Change arriving right behind a Program Change needs, and it also spaces out a chain the other end cannot swallow at once. The pedal does not stop to count: the rest of the list is picked up once the time is up, so other buttons, the expression pedals and the display keep working meanwhile. A button released while its list is still waiting has its release, the note off or the momentary off, held back until the list finishes, so nothing is switched off before it has been sent; pressing the same button again first sends whatever was left, without its pauses. Pauses work in every list: short, long and double press, bank enter and the bank switches. Four lists can be waiting at once, which is more than a foot can start; beyond that the pauses are skipped rather than queued. Needs firmware 0.30; older firmware sends the rest of the list without pausing.

**CC ramps.** `CommandType` `Ramp` sends nothing itself: it turns the `CC` command right below it into a ramp. Instead of jumping to its value, that CC walks there over `Duration` milliseconds, in steps of 10 and up to 655350 (almost 11 minutes). On the press it walks to `OnValue`; on the release, or on the press that switches a toggle off, it walks back to `OffValue`. A ramp starts from the command's other end, `OffValue` on the way up and `OnValue` on the way down, so a swell sounds the same every time; a command whose `OffValue` is above 127, and so has no off value, starts from 0 and stays where it got to on the release. Starting a ramp on a channel and CC that is still ramping picks up from where that one got to, so pressing a toggle again halfway turns it round without a jump. The pedal does not stop while a ramp runs: switches, expression pedals and other ramps keep working, and a `Wait` below the CC can hold the rest of the list back until the ramp has finished. A ramp sends a message at most every 5 ms and only when the value changes, and always ends on the exact value. Eight ramps can run at once; beyond that a CC goes straight to its value. `Panic` stops every ramp. A `Ramp` above anything but a CC is ignored. Needs firmware 0.34; older firmware ignores the `Ramp` and sends the CC as usual.

**Tempo-synced LFO.** `CommandType` `LFO` also sends nothing itself: it turns the `CC` command right below it into an LFO. While the button is held, or while a toggle is on, the CC swings between its `OffValue` and `OnValue` by itself, one cycle every `OnValue` of the `LFO`, a note division: `1/16T`, `1/16`, `1/8T`, `1/8`, `1/4T`, `1/8.`, `1/4`, `1/2T`, `1/4.`, `1/2`, `1/2.`, `1/1`, `2/1` or `4/1`, where `.` is dotted and `T` a triplet. `KeyMode` is the shape: `Sine`, `Triangle` and `SawUp` start at the bottom, `SawDown` and `Square` at the top, and `Random` jumps to a new value on every cycle. On the release, or the press that switches the toggle off, the LFO stops and the CC gets its `OffValue` as usual. A CC with no off value swings from 0. The LFO is locked to the beat the tap LED flashes, the host's clock while it is followed ([Clock_Follow](#global_settings)): cycles start on a beat, counted from the beat of the press, and a new tap, tempo or clock is followed straight away, so a `1/8` tremolo on a toggle is always in time with the delay. Setting `OnValue` below `OffValue` turns the shape upside down. It sends a message at most every 5 ms and only when the value changes; eight LFOs can run at once. An LFO keeps running when the bank changes, like any CC a button leaves on, and the toggled ones start again after switching the pedal off and on. A `Ramp` on the same channel and CC takes over from an LFO and the other way round; `Panic` and a configuration switch stop them all. Like `Wait`, an `LFO` is marked by the low nibble of the empty command type, 6, with the division's index in byte 2 and the shape's in byte 3. Needs firmware 0.43; older firmware ignores the `LFO` and sends the CC as usual.

**Step sequencer.** `CommandType` `Seq` is the same idea a step at a time: a run of them above a `CC` or `Note` command plays that command one step at a time while the button is held, or while a toggle is on, round and round until it is let go. Each `Seq` command holds two steps in `OnValue`, `100 -`, so a longer sequence is several of them one after the other, up to nine above the command they play, eighteen steps in all. A step is a value 0–127 or `-`, a step that sends nothing: under a `CC` the value is what the controller gets, under a `Note` it is the note played, with the command's `Velocity`, and each step lets the note before it go. `KeyMode` of the first command of the run is how long a step lasts, the same note divisions as the `LFO`, `1/8` when empty. Like the LFO it is locked to the beat the tap LED flashes, the host's clock while it is followed: the first step falls on the beat of the press, and a new tap or tempo is followed straight away. On the release, or the press that switches the toggle off, the sequence stops, a CC gets its `OffValue` as usual and a sounding note is let go. Four sequences can run at once, they keep running when the bank changes, and the toggled ones start again after switching the pedal off and on. A `Ramp` or an `LFO` on the same channel and CC gives way to a sequence; `Panic` and a configuration switch stop them all. `Seq` is marked by the low nibble of the empty command type, 10, with the division in byte 1 and the two steps in bytes 2 and 3, `0xFF` where the sequence ends, so the layout is unchanged. Needs firmware 0.52; older firmware ignores the `Seq` commands and sends the command below them as usual.

**Changing an expression pedal's target.** `CommandType` `Exp` changes what an expression pedal sends, so one pedal can drive the wah, then the volume, then a parameter. `OnValue` is the pedal, 1 or 2, and `KeyMode` says where it goes: `CC` sends it to the CC in `Number`, on `Channel` or, left empty, on the pedal's own channel; `Off` silences it; `Own` gives it back what it sends in this bank. It lasts until another `Exp` for the same pedal or a bank change, and it wins over the bank's `BankExpression_Settings`, even over a bank that silences the pedal, while the output range stays the bank's. With `Toggle` Y the command does it while the button is on, and switching the button off gives the pedal back its own target, so a button with `Exp 1 CC 7` as a toggle turns the wah pedal into a volume pedal and back, with the LED showing which. The pedal switches over on its next movement, like on a bank change, so the volume does not jump to where the wah was left. On entering a bank the pedals start from that bank's own targets, and then any toggling `Exp` on a button of the bank that is on takes effect again, so the pedals always match the LEDs, also after switching the pedal off and on. While an `Exp` has a pedal somewhere else, its auto-engage leaves its button alone. Like `Wait`, an `Exp` is marked by the low nibble of the empty command type, 5; byte 1 is the pedal with the toggle bit, byte 2 the CC, 0x80 for Off or 0x81 for Own, and byte 3 the channel, 0 for the pedal's own. Needs firmware 0.42; older firmware ignores it.

**Values and conditions.** The pedal keeps eight values of its own, 0 to 127 each, all zero when it is switched on. `CommandType` `Value` changes one: `Number` says which, 1 to 8, `KeyMode` what to do with it — `Set` it to `OnValue`, `Add` that much or `Sub`tract it — and `OffValue` the highest it goes, 127 when empty, adding past it starting again at zero and taking away past zero starting again at it. So `Add 1` with a top of 2 counts 0, 1, 2, 0, 1… on successive presses. The values are not part of the configuration and are not saved: they are what a button remembers within a gig, and the tools report them with the rest of the pedal's state.

`CommandType` `If` sends nothing either: it holds back the command right below it unless its test holds. `KeyMode` is the test: `Button on` and `Button off` ask about the toggle state of a button of the current bank, named in `Number` as `1`–`4` or `A`–`D`; `Value =`, `Value <>`, `Value <` and `Value >=` compare the value in `Number`, 1 to 8, with `OnValue`; and `Bank is` and `Bank is not` ask which bank the pedal is on, `OnValue` being the bank number. An `If` reaches only the command right below it, with whatever `Chan`, `Ramp`, `LFO` or `Seq` commands belong to that one, and an `If` under another asks for both, so two tests can be required at once. Two `If` commands with opposite tests, each above a command of its own, are a one button either-or: hold the pedal's BOST toggle on and a button sends one CC, off and it sends another, which is a shift layer without a second bank. A button's toggle state is its own: it still turns over on every press, and its LED with it, whether or not the `If` above its command let anything out. The test is made again when the button is let go, so a momentary command that was held back is not sent its off value either, and a test a configuration made true while the button was down does not leave a device switched on for ever. The two commands are marked by the low nibble of the empty command type, 11 for `Value` and 12 for `If`, so the layout is unchanged. Both need firmware 0.54; older firmware ignores a `Value` and, more to the point, ignores an `If` and sends the command below it anyway. The demo's bank 11 has both: held, NUDG asks about BOST, and held, ALL5 counts round three program changes.

**Macros: one list called from many buttons.** `CommandType` `Macro` sends nothing of its own: it runs another button's command list in place, where it stands. `OnValue` is the bank that button is in, 0 to 31, `Number` the button, `1`–`4` or `A`–`D`, and `KeyMode` which of that button's lists to run, `Short`, `Long` or `Double`. So the ten commands that put the whole band's rig where it belongs are stored once, on a button of a bank set aside for them, and every bank that wants them spends one command instead of ten. It is the one thing here that gives configuration room back rather than taking it: four bytes wherever it is used instead of forty, which matters, the configuration block being all but full.

The called list runs as if its commands were written where the `Macro` stands: with the toggle state of the button that called it, on the release as well as on the press, so a momentary command inside a macro is still sent its off value when you let go. A `Wait` inside it pauses the whole thing and the caller carries on where it left off once the pause is over. An `If` above a `Macro` holds back the whole of it, which is how one button runs one stored list or another. What is above it otherwise — `Chan`, `Ramp`, `LFO`, `Seq` — belongs to the command right below it and does not reach inside a macro. A macro calls a macro, up to four lists deep counting the button's own, and a list already running is never called again, so a macro that names itself, or two that name each other, sends what it can and stops rather than going round for ever; the call that would have been the fifth, or the one that would have gone round, is simply passed over and the rest of the list carries on. Macros work in a button's short, long and double press lists, in a bank's commands on entering and leaving it, and in the Bank switches' lists.

Two things look only at the button's own list and do not follow a macro into another: `LED_Feedback` and the Kemper's answers, which light a button by matching the commands written on it, and the auto-repeat of a held `CCInc` or `PCInc`. Put those on the button itself rather than in a macro. `Macro` is marked by the low nibble of the empty command type, 13, with the bank in byte 1 and the button and list in byte 2, so the layout is unchanged. Needs firmware 0.56; older firmware ignores it and sends nothing in its place. In the demo, holding 2 on HOME runs the list stored on bank 11's WAIT button, pause and all.

**Global buttons: the same button in every bank.** A tuner, a panic, a tap tempo — the things that should be under the same foot all night — used to mean the same commands copied into all 32 banks, and a change meant changing it 32 times. Instead, set one bank aside for them in `Global_Settings` with `Global_Bank`, write those buttons there once, and in every other bank tick `Global` on the buttons that should follow it. A global button takes everything from the same button of that bank: its short, long and double press lists, its label on the display, its light mode, its exclusive group and whether it is on, so the tuner is lit in every bank at once and switching it off in one switches it off in all of them. What is written on the button in its own bank is left alone and never sent, which is worth remembering: a button cannot be global and be something of its own as well.

The bank set aside is an ordinary bank otherwise — you can stand on it, its own buttons work as they always did, and it is where the global buttons are edited, on the pedal or in the configurator. Its own buttons never follow anything, so nothing can go round in circles. `Global_Bank` set to `Off`, which is what every configuration written before this holds, redirects nothing and every button is its own again. Like the macros it gives configuration room back rather than taking it: the flag is a bit of the button's LED mode byte, bit 3, which configurations have always left at zero, so the layout is unchanged; what it saves is the copies. Needs firmware 0.57; older firmware ignores the bit and sends whatever is written on the button itself. In the configurator it is the "Global" box beside the exclusive group, and on the pedal the setting is `GLOBBANK`, the bank number as the editor shows it or 0 for none. In the demo, bank 30 is set aside and holds the tap, and every song bank but the first takes its D from there — the first keeps its own, which is the way to its second page.

**Latch or momentary.** A button with `Momentary_Hold` set to `Y` and a toggle command in its short press list latches on a tap and is momentary when held. It toggles as soon as it is pressed, as always; held past `Long_Press_ms` (500 ms unless set), it presses itself once more when released, so it goes back to where it was: on only while held if it was off, off only while held if it was on. A tap shorter than that latches as usual. The hold belongs to the long press list when the button has one, so the option does nothing on such a button, nor on a cycle button. In an exclusive group, holding a button switches the others off and they stay off. The option is bit 7 of the button's LED mode byte, which configurations have always left at zero, so the layout is unchanged. Needs firmware 0.39; older firmware ignores it and the button simply toggles. In the configurator it is the "Momentary when held" box beside the exclusive group. The demo's bank 11 button 4, BOST, uses it.

**Cycle buttons.** `CommandType` `Cycle` splits a button's short press commands into states. The commands above the first `Cycle` are state 1, those between it and the next `Cycle` state 2, and so on. The `Cycle` commands take command slots too, so the ten slots hold five states of one command each. Each press sends the next state's commands, back to state 1 after the last one, and the display cell shows the label of the state just sent: the `Cycle` command's `OnValue`, up to 4 characters, or the button's own `Label` for state 1 and for a `Cycle` left without one. A button starts before its first state, so its first press sends state 1. For an amp with four channels on Program Changes 0 to 3, the button's commands are `PC 0`, `Cycle "CH B"`, `PC 1`, `Cycle "CH C"`, `PC 2`, `Cycle "CH D"`, `PC 3`, with `CH A` as its label. A state may hold several commands, pauses, ramps and repeating commands, which then repeat only while that state's press is held. Every cycle button of every bank keeps its place while the pedal is on, whatever banks you visit in between; a change of configuration, or switching the pedal off, starts them all from the beginning again. `Cycle` belongs in the short press list only: the tools refuse it in a long or double press, a bank's commands on entry or the Bank switches' lists. The labels are kept in a table of 48 at the end of the configuration, each different label stored once however many buttons use it, and the tools refuse a configuration with more. Like `Wait`, a `Cycle` is marked by the low nibble of the empty command type, 3, with byte 1 holding the label's place in the table, or 0x7F for none. Needs firmware 0.38; older firmware ignores the `Cycle` commands and sends every state at once.

**Custom SysEx.** `CommandType` `SysEx` sends one of the messages stored in the `SysEx_Strings` section; `Number` selects which, 0 to 15. Nothing else in the command is used. The message goes to both USB and the DIN output.

**Bank changes.** `CommandType` `Bank` switches bank. `KeyMode` selects the action: `GoTo` jumps to the bank number in `OnValue` (0–31), `Up` and `Down` move by the number of banks in `OnValue`, wrapping around. The change is applied after the button's remaining commands have been sent, so a button can send MIDI and then move to another bank. Nothing else in the command is used.

**Back to the bank you came from.** `KeyMode` `Back` returns to the bank the last bank change left, whoever asked for it: a button, a `Bank` command, the setlist, Bank Up / Down or the computer. It takes no value. A utility bank — a tuner, a set of solo boosts — is then one button away and one button back, wherever you were, and since going back records the bank you left, a `Back` button in each of two banks flips between them. Showing a second page is not a bank change, so `Back` on a page returns to the bank the page's bank was reached from, not to the page's own bank; leaving a bank from its page counts as leaving the bank. The pedal forgets it when the configuration changes, and after a power cycle, so a `Back` pressed before any bank change does nothing. Stored as low nibble 6 of the `Bank` command. Needs firmware 0.49; older firmware takes it as `GoTo` bank 0. The demo's bank 10 button B, PREV, is one.

**Second page.** `KeyMode` `Page` shows the bank in `OnValue` in place of the current one, as its second page: its eight buttons, labels, names, LED modes and press types take over the switches, like a shift key. Pressing a `Page` button again, on the page, goes back; the page's own `Page` button usually sits on the same switch, with the first bank in its `OnValue`, and stays lit while the page is shown. The page is a bank like any other and could be used on its own, but reached this way it belongs to the bank it came from:

- Nothing of the bank is sent again on coming back: its enter commands went out when you entered it.
- The page's enter commands go out when it is shown, and its leave commands when you go back, so a page can switch something on the device and off again. Leave them empty for a page that only changes the switches.
- Bank Up / Down, relative `Bank` commands and the setlist move on from the bank, not the page, and leave the page on the way.
- The expression pedals keep the bank's `BankExpression_Settings` and whatever `Exp` commands set. Their toe, heel and auto-engage buttons press the button of the page shown.
- Text the computer wrote until the bank changes stays on the display.
- After a power cycle with `Remember_State`, the pedal comes back on the bank, not on its page. Each page keeps its own toggle states, like any bank.
- `GoTo`, a bank change from incoming MIDI or a configuration switch leave the page too, sending its leave commands and then the bank's.

**Media keys.** `CommandType` `Media` sends a USB consumer-control key to the computer, the same ones a keyboard's media buttons send, so they work in any player or DAW without MIDI mapping. `OnValue` is one of `play_pause`, `play`, `pause`, `stop`, `next`, `prev`, `record`, `fast_forward`, `rewind`, `eject`, `mute`, `vol_up`, `vol_down`, or a raw usage number (`0xE9`). The key is tapped on press and released on release, held for `Duration` if set, or held until the next press with `Toggle`. `Number` and `Channel` are unused.

#### LED modes

- **Normal**: lit while the button is active, off otherwise.
- **Reverse**: lit at rest, off while active.
- **AlwaysOn**: lit at rest, blinking while active.

"Active" means physically pressed for a momentary button, or toggled on when any of the button's commands is a toggle. A lit LED uses `LED_Brightness`; "lit at rest" uses `LED_Rest_Brightness`. LEDs are dimmed by software PWM at 500 Hz, so there is no visible flicker.

### LongPress_Settings

Optional. `Bank_Number`, `Button_Identifier` and the ten command slots: the columns of `Button_Settings` without the label and the light, group and hold ones, which belong to the button. Rows may be missing or in any order; a button without a row has no long press commands and reacts instantly on press. Long press commands have their own toggle state.

Rows are optional in `Button_Settings` and `Bank_Naming` too: a configuration that only defines the first few banks, including one written for the 8 bank firmware, flashes unchanged and leaves the rest empty. The configurator always shows all 32 banks and writes them all when you save.

### DoublePress_Settings

Optional, and laid out exactly like `LongPress_Settings`: the third command list of each button, fired by two quick presses (see **Double press** above). Its own toggle state.

### Combo_Settings

Optional; one row per combination, up to twelve, in any order. Pressing the two switches together runs a list of their own instead of what either does alone.

| Column | Values | Meaning |
|---|---|---|
| `Switches` | two of 1–4, A–D, such as `3+4` | The pair. The order does not matter. |
| `Bank` | All / 0–31 | The bank it counts in, or `All` for every bank. A combination of the bank showing wins over an `All` one for the same pair, which is how one bank gives a pair another job. |
| `Run_Bank`, `Run_Button`, `Run_List` | 0–31, 1–4 or A–D, Short / Long / Double | The list it runs, any button's, as a [`Macro`](#button_settings) names it. |

A combination costs four bytes rather than ten commands: there was no room left for a list of its own, so its commands live on a button of a bank you keep spare, the global bank for instance, and can be tried from there. The list runs with a toggle state of the combination's own, on the press, and its release pass, the momentary offs, goes out when the first of the two switches lets go. `Wait`, `If`, `Macro` and the rest work in it as anywhere else.

A switch that belongs to a combination in the current bank does not fire at once: it waits `Combo_ms`, 80 ms unless changed, for the other one. If that comes in time the pair runs the combination and neither switch sends its own. If it does not, the press carries on as it would have, into a short, long or double press, the wait counted in, and a tap let go inside the window is still a tap. Switches in no combination, and every switch in a bank without any, answer at once as before. Two presses of the same switch are still a double press, not a combination, and the two bank switches keep their own gesture, the on-pedal editor. Needs firmware 0.59, which reads the table from the last 48 bytes of the slot; older firmware ignores it and the two switches do what they do alone. Edit it in the configurator's **Combos** tab.

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
| `Output` | CC, PitchBend or CC14 | What the pedal sends: its CC with 7 bits, Pitch Bend, or a 14-bit CC pair. Default CC. |

**Output range.** The pedal's travel, after the curve and `Invert`, is spread between `Out_Min` at the heel and `Out_Max` at the toe, so 40 and 127 make a volume pedal that never goes silent, and 127 and 0 turn it round without touching `Invert`. The ends are always reached exactly. `Toe_Level` and `Heel_Level` still refer to the pedal's position, 0 to 127, whatever it sends. A bank can override either end in `BankExpression_Settings`. Stored in two bytes that were reserved in each pedal's record, where older tools wrote zeros: firmware 0.33 reads 0 and 0 as the full range, so older configurations are unchanged. Firmware before 0.33 ignores the range.

**Pitch Bend and 14-bit CC.** With `Output` set to `PitchBend` the pedal sends Pitch Bend on its channel instead of its CC, and with `CC14` it sends a 14-bit CC pair: the high 7 bits on its CC and the low 7 bits on that CC plus 32, as the MIDI standard pairs them, so CC 4 goes out as CC 4 and CC 36, the high byte first. Both have 16384 steps instead of 128, and the pedal sends every finer step it can measure: its dead band against noise is four times narrower in these modes, and a pedal at rest still sends nothing. `Out_Min` and `Out_Max` keep counting from 0 to 127, and each is taken as its top 7 bits, so 64 is the middle of the bend: 64 to 127 bends up only, from the heel at rest, and 127 is the very top. Curve, `Invert` and the toe and heel levels work as before. A bank or an `Exp` command that sends the pedal to another CC sends that CC: as a pair when `Output` is `CC14` and the CC is below 32, which a 14-bit CC needs, and with 7 bits otherwise, so a Pitch Bend pedal can still be a volume pedal in another bank. A 14-bit CC above 31 goes out with 7 bits too. Stored in byte 15 of each pedal's record, 0 for CC, 1 for Pitch Bend and 2 for 14-bit CC, where older tools wrote a zero. Firmware before 0.44 ignores it and sends the CC.

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

An `Exp` command on a button can change these again until the next bank change, see [Button_Settings](#button_settings). A silenced pedal still acts as a switch: its `Toe_Button` and `Heel_Button` keep working. After a bank change the pedal is not sent to its new CC, channel or range at the position it happens to rest in; it follows the next movement. Configurations written before 0.28 have nothing stored here and behave as if every cell were empty, and those written before 0.33 have no range here. The range is a table of its own after the CC and channel one, four bytes per bank, so their layout is unchanged. Edit it in the configurator's **Banks** tab.

---

## The display

The 128×64 OLED shows, on the top line, the bank's large 4 character name and its 8 character info. Below it, a 2×4 grid laid out like the pedal: buttons **1 2 3 4** on the top row, **A B C D** on the bottom. Each cell shows the button's label, or its identifier when it has none, and cells of toggle buttons are drawn inverted while the toggle is on, so the state of the whole bank is visible at a glance.

### Text from the computer

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

**Longer than fits.** A text wider than its place scrolls across it once (firmware 0.61), so the whole song name gets read: still for a moment, then along at about 40 pixels a second until its end shows, still again, and back to its beginning, where it stays. It scrolls when it arrives and again whenever a bank is entered; the same text sent again leaves it where it is, so a host that repeats itself does not keep it moving. Only its own place moves: a long info line scrolls beside a still bank name. A long text for a moment stays up until it has reached its end, however long that takes past the 1.5 seconds. Scrolling never holds a press up, since the pedal draws a step only once the previous screen has gone out. Firmware before 0.61 keeps only what fits. An empty text gives the place back to what the bank shows. A whole line text hides the bank name and info while it is there, and the large and small whole lines replace each other. A text shown for a moment goes back to what was there before, and one in the bank name or info shows even over a whole line text. Text also wakes the display if the pedal was asleep. The pedal answers `F0 7D 49 place how F7`, and ignores a place or `how` it does not know.

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

### The banner's own text

The [banner at power on](#global_settings) shows the configuration's name, unless the pedal holds a text of its own (firmware 0.63): up to 60 characters of plain ASCII, such as a band, a show or a phone number in case the pedal gets lost. It belongs to the pedal, not to a configuration, so it stays whichever of the four is loaded, when a configuration is flashed and through firmware updates. It shows only while `Boot_Banner` is on, at its speed, followed by the version as the name is.

In the configurator, **Banner Text…** under PEDAL reads the text from the pedal and stores, clears or keeps it. From a terminal:

```bash
.venv/bin/python python/Send_Text.py --banner "The Band  612 345 678"   # store it
.venv/bin/python python/Send_Text.py --banner                           # print what the pedal holds
.venv/bin/python python/Send_Text.py --banner ""                        # clear it: the name again
```

Over SysEx, `F0 7D 4C 01 text... F7` stores it, with no text clears it, and `F0 7D 4C 00 F7` only asks. The pedal answers `F0 7D 4D result text... F7`, with `result` 0, or 1 when it refused a text longer than 60 characters or with a byte outside `20`–`7E` and kept the one it had, and then the text it holds. The text sits in a flash page of its own at `0x0803A000`, past the fourth configuration slot, which nothing else writes; a blank or damaged page reads as no text.

---

## Editing on the pedal

Everything is easier from the configurator, but the configurator is not always there. Hold **Bank Down and Bank Up together for two seconds** and the pedal opens an editor on the configuration it is running; the same two switches held again leave it. All ten LEDs light while it is open, and none of the switches sends anything, so nothing can go out by mistake.

The screen is a list of named fields with the cursor on one of them, and the switches are:

| Switch | What it does |
| --- | --- |
| **1** / **2** | move the cursor up and down the list |
| **3** / **4** | change the value under the cursor; held, they repeat and speed up |
| **A** / **B** | step to the previous or next command of the button's list |
| **C** | send the command as it stands, so it can be heard |
| **D** | swap the commands for the settings |
| **Bank Down** / **Bank Up** | step to the previous or next bank |

On the commands screen the first fields say what is being edited — bank, button, short or long press, and which of the ten commands — then the command's type and the fields that type has: channel, CC or note number, on and off values, whether it toggles, and so on. Below them come the four characters of the button's label, one field each. The types the editor writes are `---` (no command), `PC`, `CC`, `Note`, `Bank`, `Tap`, `Start`, `Stop`, `Panic` and `Wait`; a command of any other type is shown by name and left exactly as it is until the type field is changed, which replaces it. The double press lists are not offered: they live in an area the tools write as a block.

The settings screen holds the global settings that are a number or a choice: the long press, double press and combination (`COMBO`) times, the two LED brightnesses, how far a long press on Bank Up / Down jumps, the sleep timeout, the bank preview time (`PREVIEW`), the global channel, the bank set aside for the global buttons, what the bank switches do, the setlist, remember state, clock follow, LED feedback, the two thru switches, Kemper mode and the expression pedal CC numbers. The rest, the ones that need text or a list, stay with the configurator.

What you change is written to flash as soon as the cursor leaves the command, the label or the setting, so walking away loses nothing; a star in the title line says there is something not written yet. A write takes about a tenth of a second, during which the pedal is busy: change what you need between songs, not in the middle of one. Afterwards the pedal reads the configuration again, so the new command is live at once, and reading the configuration back with `Flash_to_CSV.py` gives you a CSV with the change in it.

`Edit_Lock` in the Global tab stops the two bank switches opening the editor at all, for a pedal that must not change under anybody's foot. It can only be turned off again from the configurator, or for one session from [safe mode](#safe-mode).

### Safe mode

Hold **any one of the eight command switches** (1–4, A–D) while the pedal powers on, and let go once the display says **SAFE MODE**. The pedal then starts without sending anything, and stays that way until it is switched off:

- no bank enter or leave list runs, neither at start-up nor when the bank changes;
- the saved bank and toggle states are not brought back, even with `Remember_State` on: it starts on bank 0 with everything off;
- `Kemper_Mode` stays off, so no beacon and no questions go to the amp;
- the expression pedals keep their position to themselves until they are moved;
- the switch held at power on is not a press, and letting go of it does nothing.

Everything else works: the buttons send their commands, the bank switches change bank, a configuration can be flashed from the computer, and the [editor](#editing-on-the-pedal) opens even with `Edit_Lock` on, so a wrong Bank Enter command can be found and changed from the pedal itself. Switch it off and on again with nothing held to leave safe mode. A bank changed in safe mode is remembered as usual, so with `Remember_State` on the pedal comes back there.

Bank Down and D held together at power on is still the bootloader's DFU mode, as on the stock pedal. `GET_STATE` reports safe mode in its last byte (firmware 0.60).

---

## Command line tools

`CSV_to_Flash.py` and `Flash_to_CSV.py` take `--slot 1` to `--slot 4` to choose a configuration slot, and use the slot the pedal is running when it is left out. Reading an empty slot is reported rather than producing a CSV. Firmware older than 0.24 has a single configuration, and the tools refuse any slot but 1 on it.

Everything the GUI does is available from the terminal, from the repository root:

```bash
# Flash a configuration to the pedal (normal mode, connected over USB)
.venv/bin/python python/CSV_to_Flash.py my-config.csv

# Read the configuration stored on the pedal into a CSV
.venv/bin/python python/Flash_to_CSV.py current-config.csv

# Back up all four slots at once, and put them back
.venv/bin/python python/Backup_Slots.py backup my-backup
.venv/bin/python python/Backup_Slots.py restore my-backup

# Write on the pedal's display (see Text from the computer)
.venv/bin/python python/Send_Text.py "Sweet Child"

# Answer the pedal as a Kemper would, to try Kemper_Mode without an amp
.venv/bin/python python/Kemper_Sim.py

# Update the firmware, with nothing held on 0.58 or later
.venv/bin/python python/Update_Firmware.py midi-commander-custom-<version>.dfu

# Work the pedal hard for a minute and check it is still sound (demo configuration)
.venv/bin/python python/Stress_Test.py

# How long a press takes to leave as MIDI, quiet and under load (demo configuration)
.venv/bin/python python/Latency_Test.py
```

**Backups.** `Backup_Slots.py backup` reads every slot that holds a configuration into a folder, `slot1.csv` to `slot4.csv`, plus a `backup.txt` with the date, the firmware and the name in each slot; with no folder given it makes one named after the date and time. Each CSV is an ordinary configuration, so any of them can be opened in the configurator or flashed on its own. `restore` checks every file before touching the pedal, lists what it will overwrite and asks first (`--yes` skips the question), writes each file to its slot and restarts the pedal once at the end; slots with no file in the folder are left as they are. A backup restored onto the pedal gives the same bytes it was read from, except that settings a configuration from older firmware never had are written with the value the pedal was already using for them.

The tools find the pedal by its USB MIDI name (`MIDI Commander Custom`), check the firmware version, and exchange the configuration as SysEx messages under manufacturer ID `0x7D`: erase (52), write 16-byte chunk (54), read chunk (56), version (58), reset (60), pedal readings (62), select a slot (64), press a switch (66), the pedal's state (68) and screen (70), put text on the display (72), restart in DFU mode (74, with the check bytes `44 46`), the banner's own text (76) and the latency of the last presses (78). The read-back commands need firmware 0.2 or later; the tools tell you if the pedal is older.

To watch what the pedal sends, use any MIDI monitor (MIDI Monitor on macOS, MIDI-OX on Windows, `aseqdump -p 'MIDI Commander Custom'` on Linux).

---

## Building and flashing from source

The firmware is built with [PlatformIO](https://platformio.org/) (`pip install platformio`, `pipx install platformio` or the VS Code extension). All sources live under `firmware/`; the first build downloads the ARM toolchain.

```bash
platformio run -e midi_dfu      # DFU image, linked at 0x08003000 behind the stock bootloader
platformio run -e midi_debug    # ST-Link image at 0x08000000 (for SWD debugging, replaces the bootloader)
```

`midi_dfu` also packages the binary as a DfuSe container through `scripts/post_build_dfuse.py` and `tools/bin_to_dfuse.py`, writing `artifacts/dfu/platformio-<timestamp>.dfu` and a stable `artifacts/dfu/platformio-latest.dfu`. Flash it as in [Getting started](#1-flash-the-firmware), or let PlatformIO do it:

```bash
platformio run -e midi_dfu -t upload
```

With the Python environment in `.venv` the upload goes through `Update_Firmware.py`, so a pedal on 0.58 or later needs nothing held and starts the new build by itself. Without it, `dfu-util` is run on its own and the pedal has to be in DFU mode already.

The raw binary can also be flashed directly: `dfu-util --alt 0 -s 0x08003000 --download .pio/build/midi_dfu/firmware.bin`.

The Python tools have tests: round trips through the configuration packers, and checks that the numbers the tools and the firmware share still agree:

```bash
.venv/bin/python -m unittest discover -s python/tests
```

**Before a release**, with the pedal on USB and the demo configuration (`python/demo-all-features.csv`) active, run the stress test as well. It needs nothing else, no foot and no DIN device, and takes about a minute:

```bash
.venv/bin/python python/Stress_Test.py
```

It plays the same sequence of presses and bank changes twice, over SysEx and through `Remote_Mode`: short, long and double presses, two switches together, scenes, a note held while the bank changes. The first time the line is quiet; the second time the pedal also gets MIDI clock, CCs and notes for `LED_Feedback` to look up, messages for the DIN output, texts over SysEx and a stream of state and screen reads, a few hundred messages a second. Both runs must send the same messages in the same order and leave the same banks and toggles, with no note or momentary CC left on and every SysEx answered. Then `LED_Feedback` gets a snapshot of 125 CCs in one go, and 150 bank changes arrive in bursts, some of them spaced to land as the previous screen finishes going out: every bank entered must be left again with its Bank Enter and Leave commands, and the pedal must end on the last bank asked for, with that bank's screen. Changes that arrive before the pedal has handled the one before are merged, the last one winning, as they always have been. The screen is checked in the pedal's buffer, so look at the panel itself when it finishes; the pedal is put back on the bank it started on. Last, the pedal's own MIDI clock, an LFO and a step sequence are started in bank 6 and the presses and bank changes go on for 15 seconds under the same flood, the pedal now sending on its own as well: it must keep answering, and from firmware 0.65 no press may take more than 5 ms from the switch to its first MIDI message. It exits with 1 when a check fails, and `--seed` repeats a run's random parts. Firmware 0.60 or later.

**Latency.** From 0.65 the pedal times its own presses: from the moment it sees a switch change, or a press from the computer arrives, to the moment the first MIDI message of that press is handed to USB, with the processor's cycle counter. SysEx `GET_LATENCY` (78) returns how many presses it timed, the slowest and the last 16, in microseconds. A press that waits on purpose, one with a long or double press list, is not timed, and a bank switch is timed from its release, which is when it acts. `Latency_Test.py` presses a toggle button and Bank Up forty times each over SysEx, first with the line quiet and then under the stress test's load with the pedal's clock, LFO and sequence running, and prints what the pedal measured next to the computer's own round trip for comparison; on a Mac that round trip alone is about 6 ms, in steps of about 5 ms, which is why the computer cannot time the pedal's part itself. On 0.65 a press takes about 0.25 ms and a bank change about 0.4 ms; the slowest are a press that lands while a screen is being drawn, about 2 ms more. Firmware 0.65 or later.

GitHub Actions builds both firmware images and runs these tests on every push and pull request. See `CONTRIBUTING.md` for the repository layout and what to keep in sync when changing the configuration format.

Hardware notes (MCU, pinout, I²C addresses) are in `HardwareNotes.txt`; `backup/` holds a dump of the original firmware and EEPROM.

---

## Changelog

Firmware versions are shown on the display at boot and reported by the tools.

- **0.66 — Preview a bank before going there.** New `Bank_Preview` setting, global byte 47, the last one free: 1 to 60 seconds, 0 or erased flash off. With it on, Bank Up / Down move a candidate bank, from the one previewed or else from the bank you are in, and the display shows it with its own name inverted over its labels; nothing is sent. The first of the eight buttons to go down confirms it through the same bank change as before, and that press and its release are taken by the preview; a button already down when the preview began finishes its press as usual. Stepping back to the bank you are in, the time running out, any other bank change, a configuration switch or the editor opening drop it. Readouts over the bank screen are skipped while it shows, and texts from the computer wait under it. From the switch to the first message a confirming press takes about 0.13 ms. `GET_STATE` grows one byte: the bank previewed, 127 for none. **Preview banks** in the configurator's Global tab, `PREVIEW` in the pedal's own editor; the demo leaves it off, since the stress and latency tests time Bank Up.
- **0.65 — The pedal times its presses.** New SysEx `GET_LATENCY` (78) and `python/Latency_Test.py`: the pedal measures, with the processor's cycle counter, the time from a switch changing to the first MIDI message of that press being handed to USB (see [Building and flashing from source](#building-and-flashing-from-source)). What it found, fixed here. **A bank change no longer waits for its screen.** Every bank change drew the whole bank screen before sending anything, Bank Enter commands and bank switch commands included, and the display driver drew it a pixel at a time, 11 ms; when the previous screen was still going out over I²C it also waited for that, up to 25 ms more. The driver now draws characters and filled rectangles straight into the buffer a row or a byte at a time, so a whole bank screen takes 2.1 ms, pixel for pixel the same; sending a screen never waits, the next one being sent when the last is out; and a bank change sends its MIDI first, the screen being drawn on the same pass of the main loop, with a readout such as the tempo that its commands show drawn over the new bank. From the switch to the first message a bank change went from 10.8 ms to 0.4 ms, and a press is about 0.25 ms. **A hang with the DIN output busy.** Sending to the DIN output spun until the UART took the message. When the pedal was sending on its own (a clock, an LFO, a sequence) and MIDI from the computer to be passed through to DIN arrived in the middle of one of those sends, the USB interrupt spun for ever on the lock the main loop held, and the pedal stopped answering until it was unplugged; before that it froze for up to a second at a time. A transfer is now started with interrupts off and never waited for: a busy UART starts the next message itself when it finishes. The stress test gains a part with the pedal's own clock, LFO and sequence running, which is how it was found. No configuration bytes.
- **0.64 — A stress test, and what it found.** New `python/Stress_Test.py`, to run before each release (see [Building and flashing from source](#building-and-flashing-from-source)). Its first runs found three things, fixed here. **A release now sends the up list of the bank the press fired in.** A note or a momentary CC held while the bank changed was never let go: the release sent whatever the new bank had on the same switch, a stray message of its own. The same went for the press that changes the bank, whose release went to the new bank's button. **The expression pedals no longer hold up everything else.** Before each reading the pin is left to recover from its pull-down; that wait was a busy loop of 11.7 ms per pedal, on every pass of the main loop, which therefore ran 43 times a second, and every press waited behind it. The pin now settles while the loop carries on, for the same 12 ms, so the pedals read as before. From a press over SysEx to its CC arriving on the computer, the median went from 19.3 ms to 11.4 ms and the slowest of 60 from 31 ms to 22 ms. **`LED_Feedback` keeps up with a DAW.** Its queue held 32 messages, so a burst such as a mixer snapshot lost everything past the 31st, and each message was checked against every command of every bank, about a millisecond each. The queue now holds 160, a message whose number no toggle button carries is passed over at once, and the commands are compared number first. No configuration bytes.
- **0.63 — The banner's own text.** New SysEx `BANNER` (76) stores up to 60 characters for the power on banner, which then shows them in place of the configuration's name, followed by the version. The pedal keeps them in their own flash page, at `0x0803A000`: the comment that gave the slots' addresses was wrong, and slots 2 to 4 end at `0x0803A000`, not at 256 kB, so 24 kB below 256 kB were unused. The page holds a length, a check byte and a marker written last, so a torn write or a damaged page reads as no text. Neither a configuration flash nor a firmware update touches it. `Send_Text.py --banner` and **Banner Text…** in the configurator read, store and clear it. No configuration bytes. See [The banner's own text](#the-banners-own-text).
- **0.62 — A banner at power on.** New `Boot_Banner` setting, global byte 46: 0 or erased flash is off, 1 to 3 the speed. The configuration's name, padding left out, and `v` with the firmware version cross the display once in large letters, starting during the boot's waits and carrying on in the main loop. Only the four display pages the letters sit on are sent, so a step takes about half a whole screen's time: one every 27 ms, measured. The switch scan, and a press from the computer, end it; the bank screen and any host text sent meanwhile wait underneath and show once it is over, and a short readout meanwhile is skipped. The configuration switch notice, safe mode and the on-pedal editor take the screen from it. **Banner at power on** in the configurator's Global tab; the demo has it at Normal. See [`Boot_Banner`](#global_settings).
- **0.61 — Long names scroll.** A host text or Kemper rig name wider than its place on the top line scrolls across it once, when it arrives and whenever a bank is entered, then shows its beginning: still for 0.8 s, 2 pixels every 50 ms, still 0.8 s at its end. Every place now keeps up to 32 characters, where it kept only what fit, and the same text sent again leaves the scroll alone. A long text for a moment stays up until it has reached its end. The display's main loop task no longer waits for the previous screen to go out: it comes back on the next pass, so a scroll step never holds a press up. `Send_Text.py` sends up to 32 and says when a text will scroll. No configuration bytes. See [Text from the computer](#text-from-the-computer).
- **0.60 — Safe mode.** Any of the eight command switches held at power on starts the pedal in safe mode until it is switched off. Bank enter and leave lists do not run, the saved state is not restored, `Kemper_Mode` counts as off, the expression pedals take their first reading as already sent, and `Edit_Lock` is ignored. SAFE MODE shows on the display for three seconds. The switch held is not taken as a press: the switch scan starts from the switches as they are. `GET_STATE` grows one byte, 1 in safe mode. No configuration bytes. See [Safe mode](#safe-mode). Also two display fixes: the large `S` was drawn a column narrower at the top than at the bottom, and a screen update that began just as the previous one sent its last line wrote over that line while the DMA was still reading it, which could leave the bottom of the screen scrambled until the next redraw; single display commands were also sent from a byte on the stack that could be gone before the DMA read it.
- **0.59 — Two switches together.** New `Combo_Settings` section and `Combo_ms` setting (global byte 45, in 10 ms steps, 80 ms when unset): two command switches pressed together run a list of their own. A combination is four bytes — the pair, the bank it counts in plus one (0 for every bank), and the bank, button and list it runs, named as a `Macro` names one — so twelve of them fill exactly the 48 bytes the slot had left, 24528 to 24576; older configurations have erased flash there, which is no combination. Two new press states: a switch of a combination waits for its partner, and the pair that fired waits for release. A switch that is in no combination of the bank showing takes the same path as before, with no delay. **Combos** tab and **Two switches together within** in the configurator, `COMBO` in the pedal's own editor. In the demo, 3+4 toggles a tuner in every bank and clears the looper on song 1.
- **0.58 — Firmware updates with nothing held.** New SysEx `ENTER_DFU` (74, check bytes `44 46`): the firmware answers, and a moment later shows FIRMWARE UPDATE, writes zero over its own initial stack pointer at 0x08003000 and restarts. The stock bootloader is ST's DFU demo, read back from the pedal to confirm it: it starts the firmware only when that word looks like a RAM address, so it stays in DFU mode until a new image is flashed. The F1 lets a programmed halfword be written to zero without erasing its page, and the bootloader pages are never touched. A build linked at the start of flash answers that it cannot and does nothing. New `Update_Firmware.py` and **Update Firmware…** in the configurator. They check the .dfu file, down to the bootloader's own stack pointer test, ask for DFU mode, flash, and start the pedal again by reading back the start of the image with DfuSe's leave request. A plain `dfu-util` download leaves the bootloader in DFU mode until the pedal is switched off. `platformio run -e midi_dfu -t upload` goes through it too.
- **0.57 — Global buttons.** New global setting `Global_Bank` (byte 44, the bank plus one so a zero means none) names a bank set aside for the buttons that should be the same everywhere, and a new bit 3 of each button's LED mode byte marks a button as following it. A marked button takes everything from the same button of that bank: its three command lists, its label, its light mode and group, its cycle position and its on and off state, which is therefore shared between all the banks that follow it. The redirect sits in the three `get_*_rom_pointer` functions and in what reads the LED mode byte, the label and the toggle bit, so a press, the LED feedback, a `Macro` and the table built at load all follow it without knowing about it; a button of the bank set aside is never redirected. `Global` in the configurator beside the exclusive group and `GLOBBANK` in the pedal's own editor. In the demo, bank 30 holds the tap and the song banks take it from there.
- **0.56 — Macros.** New `Macro` command type, marked by the low nibble of the empty command type, 13: it runs another button's list in place, named by its bank, its button and which of its lists, so a sequence wanted in many banks is stored once and called with four bytes instead of being copied. A list being run is now a stack of frames rather than a single list, `MACRO_DEPTH` of them, which is what lets a `Wait` inside a macro pause the whole thing and the caller carry on afterwards; the release pass follows macros too, so a momentary command inside one is still let go. An `If` above a `Macro` holds back the whole of it, a list already running is never called again and four lists is as deep as they go, so a macro cannot go round for ever. `Macro` in the configurator's command lists and in the pedal's own editor, which names it and leaves it alone. Held, the demo's 2 on HOME runs bank 11's WAIT list, its 200 ms pause included.
- **0.55 — Two way with a Kemper.** New global setting `Kemper_Mode` (byte 43). With it on the pedal sends a Kemper Profiler the beacon that asks it to report itself, again every five seconds, and asks for the rig name every second and for the two modules the amp does not report by itself, the delay and the reverb; all eight are asked for at the start and whenever the rig changes. What comes back the new `kemper.c` turns into the two things worth seeing from the floor: the rig name in the info line beside the bank name, and a module switching on or off turned into the Control Change that switches it and handed to the `LED_Feedback` machinery, which grew a way of matching a command whatever channel it carries, since the amp's answers carry none. Nothing is sent back because of what the amp reports, so they cannot chase each other. The Kemper Player template has it on, and the on-pedal editor offers it as `KEMPER`. New `python/Kemper_Sim.py`, a Kemper of make believe that answers over the same USB link a Player uses, which is what this was tried against: there was no Kemper here. See [Two way with a Kemper](#two-way-with-a-kemper).
- **0.54 — Values and conditions.** New `Value` and `If` command types, marked by the low nibble of the empty command type, 11 and 12. The pedal keeps eight values of its own, 0–127 and all zero at power on; a `Value` command sets one, adds to it or takes away, wrapping round within a top of its own. An `If` command holds back the command right below it, with the `Chan`, `Ramp`, `LFO` or `Seq` commands belonging to it, unless its test holds: a button's toggle on or off, one of the values compared with a number, or the bank the pedal is on. Ifs stack, so two tests can be asked at once, and the test is made again on the release, so a command held back sends no off value either. The `GET_STATE` answer now carries the eight values, and the tools report them. `Value` and `If` in the configurator's command lists. Held, the demo's NUDG in bank 11 sends one CC or another depending on the BOST toggle, and ALL5 counts round three program changes.
- **0.53 — Editing on the pedal.** Bank Down and Bank Up held together for two seconds open an editor on the running configuration, and held again leave it: any command of any button of any bank, short or long press, with the fields of its type, the four characters of the button's label, and the global settings that are a number or a choice. Switches 1 and 2 walk the field list, 3 and 4 change the value under the cursor and repeat while held, A and B step through the ten commands of the list, C sends the command so it can be heard, D swaps commands for settings, and the bank switches change bank. The types it writes are `PC`, `CC`, `Note`, `Bank`, `Tap`, `Start`, `Stop`, `Panic`, `Wait` and no command; anything else is shown by name and left alone until the type is changed. A change is written as soon as the cursor leaves it, by rewriting the 2 kB flash page it lives in (`flash_settings_patch`), after which everything derived from the configuration is built again. New global setting `Edit_Lock` (byte 42) stops the editor opening at all. See [Editing on the pedal](#editing-on-the-pedal).
- **0.52 — Step sequencer.** New `Seq` command type, marked by the low nibble of the empty command type, 10: a run of them above a `CC` or `Note` command plays it one step at a time, locked to the tempo, while the button is held or its toggle is on. Each command holds two steps in `OnValue`, a value 0–127 or `-` for a silent step, up to eighteen in the nine commands above the one they play, and `KeyMode` of the first is how long a step lasts, the same note divisions as the `LFO`. Under a `Note` each step is the note played, with the command's velocity, so a sequence is an arpeggio; the note before it is let go at every step, and on the release. Four can run at once, they survive a bank change and the toggled ones start again at power up; `Panic` and a configuration switch stop them. `Seq` in the configurator's command lists, with the steps and the division. Held, the demo's STRT in bank 6 plays a four note arpeggio.
- **0.51 — Global channel and several channels at once.** New global setting `Global_Channel` (byte 41, 0 = off), which sends every message on one channel instead of the one each command carries, expression pedals included, so a whole configuration moves with one number. New `Chan` command type, marked by the low nibble of the empty command type, 9: it names channels in `Channel` and the command right below it goes out once on each, on the press and on the release, and on purpose, so it beats the global channel. LED feedback matches the channel a command really sends on. Both in the configurator, as a setting and a command with a channel list. The demo mutes three channels with one CC, holding A in bank 11.
- **0.50 — MMC and Song Select.** New `MMC` command type, a MIDI Machine Control message to every device: `Play`, `Stop`, `Record`, `Pause`, `FastForward`, `Rewind`, `Locate` to a time in seconds, and the rest. New `Song` command type: Song Select with a song number, or Song Position Pointer with a place in the song in sixteenth notes, neither on a channel. Both are marked by the low nibble of the empty command type, 7 and 8, so the layout is unchanged. A long press or double press list holding only such a command now counts as present, which it did not before for any command of that type, `Exp` and `Wait` included. `MMC` and `Song` in the configurator's command lists, with an action menu and the value to match. Held, the demo's media buttons in bank 5 send the same transport as MMC, plus Song Select 2 and Song Position 0.
- **0.49 — Back to the bank you came from.** New `Bank` command mode `Back`, low nibble 6: it returns to the bank the last bank change left, whoever asked for it, so a detour to a utility bank costs one button there and one back, and two `Back` buttons flip between two banks. It takes no value. The bank is recorded by the one place every bank change goes through, and forgotten on a configuration switch and at power on. "Back" in the configurator's `Bank` action list. The demo's bank 10 button B is one.
- **0.48 — Tempo flash on any button.** New `Tempo_Flash` column in `Button_Settings`: the button's LED flashes on every beat as a `Tap` button's does, whatever the button sends. Stored in bit 2 of the button's LED mode byte, which the LED mode itself never reached, so the layout is unchanged and a CSV without the column packs exactly as before. "Flash at the tempo" box in the configurator's button editor. The demo's bank 6 button B, SYNC, flashes with the beat.
- **Templates.** Ready to flash configurations for the Fractal Audio FM3, the Line 6 HX Stomp and the Kemper Profiler Player, each built by a script from the device's own MIDI map; see [the templates](#fractal-audio-fm3-template). No firmware change.
- **0.47 — Second page in a bank.** New `Bank` command mode `Page`, low nibble 5, with the page's bank in byte 1: shows that bank in place of the current one and back, without the bank's enter commands, while the pedals, relative bank moves, the setlist, the host's text and the remembered bank stay with the bank. The page's enter commands go out when it is shown and its leave commands when it is left. A button holding `Page` stays lit while the page is shown. `Page` in the configurator's Bank actions. The demo's song 1 has PG 2 on D, showing bank 31, which is no longer a song.
- **0.46 — The computer writes on the display.** New SysEx `SET_TEXT` (72): the host puts up to 18 characters in the bank name, the info line or across the whole top line, large or small, until the bank changes, until it changes them, or for 1.5 seconds; an empty text gives the place back to the bank. It is stored from the USB interrupt and drawn from the main loop, and wakes the display. The bank screen now clears its refresh flag before drawing, so a refresh asked for while it draws is no longer lost. New `Send_Text.py`, which sends the text or prints the bytes for a host.
- **0.45 — Press a button from the computer.** New global settings `Remote_Mode` (Off, CC or Note), `Remote_Channel` and `Remote_First`, in bytes 38–40, which older tools left at zero, meaning off. Ten CCs or notes over USB press and release the ten switches through the virtual pedal, so every press type works; a press and its release arriving in the same USB packet are now taken one pass apart, so the press is never lost. The messages used are not forwarded. Three new fields in the configurator's USB MIDI group. The demo listens on CC 102–111, channel 16.
- **0.44 — Pitch Bend and 14-bit CC from an expression pedal.** New `Output` column in `Expression_Settings`, `CC`, `PitchBend` or `CC14`, stored in byte 15 of each pedal's record, which older tools left at zero, meaning CC. A 14-bit CC goes out as the CC and CC + 32, high byte first, both in one packet; CCs above 31, and any CC a bank or an `Exp` command sends the pedal to in Pitch Bend mode, stay 7-bit. The output range still counts 0–127, 64 being the middle of the bend. A narrower dead band in these modes gives the finer steps; a pedal at rest stays quiet. `Output` choice in the configurator's Expression tab. The demo's pedal 2 sends a 14-bit CC.
- **0.43 — Tempo-synced LFO.** New `LFO` command type: the `CC` command right below it swings between its `OffValue` and `OnValue` while the button is held or the toggle is on, one cycle per note division of the tempo, from `1/16T` to `4/1`, in a `Sine`, `Triangle`, `SawUp`, `SawDown`, `Square` or `Random` shape. Locked to the beat of the tap LED or the followed clock, so taps and tempo changes are followed at once. Keeps running across bank changes; toggled ones restart at power up. Marked by the low nibble of the empty command type, 6, so the layout is unchanged. `LFO` in the configurator's command lists. The demo's bank 6 swaps TAP2 on A for TREM, a 1/8 sine tremolo on CC 14.
- **0.42 — Expression target from a button.** New `Exp` command type: sends an expression pedal to another CC and channel, silences it (`Off`) or gives it back its own target (`Own`), until another `Exp` or a bank change; as a toggle, switching it off gives the pedal back. Toggling `Exp` commands that are on take effect again on entering their bank and at power up. Auto-engage pauses while the pedal is elsewhere. Marked by the low nibble of the empty command type, 5, so the layout is unchanged. `Exp` in the configurator's command lists. The demo's bank 8 has VOL on C, pedal 1 as a volume pedal, and P2 X on B, pedal 2 silenced.
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
