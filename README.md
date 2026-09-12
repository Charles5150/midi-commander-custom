# Midi Commander Custom Firmware

Custom firmware and configuration tools for the **MeloAudio Midi Commander** foot controller: eight banks of eight buttons, up to ten MIDI commands per press plus ten more on a long press, USB keyboard keys, two calibrated expression pedals, button labels on the display, USB-to-DIN MIDI thru, and a desktop configurator that talks to the pedal over USB.

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

- **8 banks × 8 buttons.** Bank Up / Bank Down switch banks; each bank has a name shown on the display.
- **Up to 10 commands per button press**, sent in order. Any mix of Program Change (with optional Bank Select), Control Change, Note, Pitch Bend, Start, Stop, USB keyboard keys and media keys, each MIDI command on its own channel.
- **Long press.** A second set of up to 10 commands fires when a button is held past a configurable time (default 500 ms). Buttons without long press commands react instantly, as before.
- **Momentary or toggle** behaviour per command, and timed auto-release (up to 1.27 s) for Notes, Pitch Bend and keys.
- **Button labels on the display.** Each button has a 4 character label; the screen shows the current bank and a 2×4 grid mirroring the pedal, with toggle buttons drawn inverted while on.
- **LED modes** per button: Normal, Reverse (lit when off) or AlwaysOn (blinks while active). The Bank Up / Down LEDs have the same options. Global brightness for lit LEDs and, separately, for LEDs lit at rest, so an active button stands out from an idle one.
- **USB keyboard and media keys (HID).** A command can press a key with Ctrl / Shift / Alt / Cmd modifiers, tap it, hold it or release it, or send a media key (play/pause, next, previous, stop, volume, mute, record) to the computer.
- **Two expression pedals** with per-pedal CC number, MIDI channel, calibrated end points, response curve and direction, calibrated live from the configurator.
- **USB-to-DIN MIDI thru.** Optionally forward everything received over USB to the MIDI OUT jack, so the pedal doubles as a USB MIDI interface for the device behind it. Clock / Start / Continue / Stop have their own switch.
- **Remember state.** Optionally power up in the last bank with every toggle exactly as you left it.
- **Sleep mode.** When the computer suspends, LEDs and display switch off; they come back when it wakes.
- **Configuration over USB.** Flash a configuration to the pedal and read it back, from the GUI or the command line, over ordinary USB MIDI SysEx. No special driver.
- Firmware updates through the stock DFU bootloader with `dfu-util`.

---

## Getting started

You need the pedal, a USB cable, Python 3 and, to update the firmware, `dfu-util`.

### 1. Flash the firmware

The current release is **`artifacts/release-0.10.dfu`**. Earlier releases are kept in `artifacts/` for reference.

1. Install `dfu-util` (macOS: `brew install dfu-util`; Linux: your package manager; Windows: [dfu-util.sourceforge.net](https://dfu-util.sourceforge.net/)).
2. With the pedal off, hold **Bank Down** and **D** (the two bottom-right buttons) and switch it on. The display stays dark and LED 3 lights up: the pedal is in DFU mode.
3. Connect it over USB and check it is seen:

   ```text
   $ dfu-util --list
   Found DFU: [0483:df11] ... alt=0, name="@Internal Flash  /0x08000000/06*002Ka,250*002Kg", ...
   ```

4. Flash, using `--alt 0` (the internal flash entry above):

   ```bash
   dfu-util -d 0483:df11 --alt 0 --download artifacts/release-0.10.dfu
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

Connect the pedal in normal mode (not DFU), click **Read from Device** to load what it currently holds, edit, then **FLASH TO DEVICE**. The next section walks through the configurator.

---

## The configurator

`python/gui_configurator.py` edits a configuration CSV and exchanges it with the pedal over USB MIDI.

<img src="docs/images/gui_workflow.png" width="500">

**Sidebar**

- **Load CSV** opens a configuration file. The sample `python/MeloConfig_10_Cmds - RC-600.csv` is loaded at start.
- **Read from Device** pulls the configuration stored on the connected pedal into a CSV you choose, and loads it.
- **Save CSV** writes the current settings to the open file.
- **FLASH TO DEVICE** saves the CSV, transfers it to the pedal and reboots it.

**Global Settings** — MIDI channel, config name, expression pedal CC numbers, bank LED modes, realtime passthrough, USB MIDI thru, remember state and the long press time. Bounded settings are drop-downs or check boxes; numbers are limited to their valid range. See the [reference](#global_settings).

**Button Config** — pick a bank, then a button. At the top you set its **display label** and **LED light mode**; below, ten command slots A–J. Choose a slot's command type and only the fields that type uses appear. **Short press / Long press** switches the slots between the two command sets of the button. Edits are kept in memory automatically when you switch button, bank or tab.

**Bank Names** — the 4 character name and 8 character info line of each bank.

**Expression** — per pedal: end points, response curve, invert, channel. **Connect live view** shows the pedal position and the CC being sent, read from the pedal in real time. To calibrate: press **Calibrate**, sweep the pedal slowly from heel to toe and back a couple of times, press **Done**; the end points are filled in with a small margin so 0 and 127 are always reached.

---

## Configuration reference

A configuration is a CSV with several sections, each introduced by a line starting with `*` and the section name. Lines containing `#` are comments. The configurator reads and writes this format; you can also edit it in a spreadsheet, and the sample file is the reference for the column names. (The original project's [Google Sheets template](https://docs.google.com/spreadsheets/d/1KwKj3sYrNEkEl8ONipW-ZGSLD7r_W1NfWwyGgjnbk08/edit?usp=sharing) predates several columns; start from the sample CSV instead.)

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
| `Long_Press_ms` | 100–2500 | Hold time that turns a press into a long press. Default 500. |
| `LED_Brightness` | 1–100 | Brightness of a lit LED, in percent. Default 100. Configurations written before 0.9 read as 100. |
| `LED_Rest_Brightness` | 1–100 | Brightness of LEDs lit at rest by the Reverse and AlwaysOn modes. Default 100; set it lower to tell an active button from an idle one. |

### Bank_Naming

One row per bank, `Bank_Number` 0–7: `Bank_Name_Large` (4 characters, big font) and `Bank_Info_Small` (8 characters, small font).

### Button_Settings

One row per button, 64 rows in bank order and, within a bank, in the order `1, 2, 3, 4, A, B, C, D` (top row of the pedal, then bottom row). Columns:

- `Bank_Number`, `Button_Identifier`
- `Label` — up to 4 characters shown on the display. Empty shows the button identifier.
- `Light_Mode` — Normal / Reverse / AlwaysOn.
- Ten command slots, prefixed `A_` to `J_`, each with the fields below.

#### Command fields

| Field | PC | CC | Note | PB | Key | Meaning |
|---|---|---|---|---|---|---|
| `CommandType` | | | | | | `PC`, `CC`, `Note`, `PB`, `Key`, `Media`, `Start`, `Stop`, or empty for none |
| `Channel_(PC/CC/Note/PB)` | ✓ | ✓ | ✓ | ✓ | | MIDI channel 1–16 |
| `Number_(PC/CC/Note)` | ✓ | ✓ | ✓ | | ✓ | PC: program 0–127. CC: controller number. Note: note number. Key: modifier mask |
| `OnValue_(CC/PB)` | | ✓ | | ✓ | ✓ | CC: value on press (0–127). PB: −8192..8191. Key: key name. Media: media key name |
| `OffValue_(CC)` | | ✓ | | | | CC: value on release / toggle off (0–127) |
| `BankSelect_(PC)` | ✓ | | | | | 0–16383, sent as CC#32 (LSB) before the PC |
| `BankSelectHighByte_(PC)` | ✓ | | | | | Y: also send CC#0 (MSB) |
| `Toggle_(CC/PB/Note)` | | ✓ | ✓ | ✓ | ✓ | Y: alternate on / off on successive presses. Key / Media: hold until the next press |
| `Velocity_(Note)` | | | ✓ | | | 0–127 |
| `Duration_(Note/PB)` | | | ✓ | ✓ | ✓ | In 10 ms steps, 0–127 (max 1.27 s). Media: same as Key |
| `KeyMode_(Key)` | | | | | ✓ | Normal / Down / Up |

`Start` and `Stop` take no parameters; they send MIDI Start (0xFA) / Stop (0xFC) over USB and DIN.

**When the "off" is sent**

- `Toggle = N`, `Duration = 0`: on when pressed, off when released (momentary).
- `Toggle = N`, `Duration > 0`: on when pressed, off automatically after the duration, even if still held. Notes, pitch bend and keys only; CC ignores the duration.
- `Toggle = Y`: the first press sends on, the next sends off, and so on. Toggle state is kept per button and per bank, and drives the LED.

**Keyboard keys.** `Number` is the sum of the modifiers: 1 Ctrl, 2 Shift, 4 Alt, 8 Cmd/Win (3 = Ctrl+Shift). `OnValue` is a single character (`a`, `7`) or one of `enter`, `esc`, `tab`, `space`, `backspace`, `minus`, `equal`, `leftbr`, `rightbr`, `backslash`, `semicolon`, `quote`, `grave`, `comma`, `dot`, `slash`, `f1`–`f12`. `KeyMode`: **Normal** taps the key (held for `Duration` if set); **Down** presses and leaves it pressed, **Up** releases it, both after a `Duration` delay, so one button can build combinations across several slots. `Toggle` holds the key until the next press.

**Media keys.** `CommandType` `Media` sends a USB consumer-control key to the computer, the same ones a keyboard's media buttons send, so they work in any player or DAW without MIDI mapping. `OnValue` is one of `play_pause`, `play`, `pause`, `stop`, `next`, `prev`, `record`, `fast_forward`, `rewind`, `eject`, `mute`, `vol_up`, `vol_down`, or a raw usage number (`0xE9`). The key is tapped on press and released on release, held for `Duration` if set, or held until the next press with `Toggle`. `Number` and `Channel` are unused.

#### LED modes

- **Normal**: lit while the button is active, off otherwise.
- **Reverse**: lit at rest, off while active.
- **AlwaysOn**: lit at rest, blinking while active.

"Active" means physically pressed for a momentary button, or toggled on when any of the button's commands is a toggle. A lit LED uses `LED_Brightness`; "lit at rest" uses `LED_Rest_Brightness`. LEDs are dimmed by software PWM at 500 Hz, so there is no visible flicker.

### LongPress_Settings

Optional. Same columns as `Button_Settings` minus `Label` and `Light_Mode`. Rows may be missing or in any order; a button without a row has no long press commands and reacts instantly on press. Long press commands have their own toggle state.

### Expression_Settings

Optional; two rows, `Pedal` 1 and 2.

| Column | Values | Meaning |
|---|---|---|
| `Min_ADC`, `Max_ADC` | 0–4095 | Calibrated heel and toe readings. Defaults 80 and 3900. |
| `Curve` | Linear / Log / Exp | Log is fast at the start of the travel, Exp is slow at the start. |
| `Invert` | Y / N | Swap heel and toe. |
| `Channel` | Global or 1–16 | Global uses `MIDI_Channel`. |

Both 1/4" jacks are read through the ADC every millisecond, with the pin pulled down between readings to prevent crosstalk between the two inputs, smoothed with an adaptive filter and a small hysteresis so a resting pedal does not chatter. A CC is sent only when the 7-bit value changes.

If a pedal produces no CC, open the Expression tab and press **Connect live view**: if the raw value does not follow the pedal, the problem is the cable or jack; if it does but no CC reaches your MIDI monitor, check the channel and CC number.

---

## The display

The 128×64 OLED shows, on the top line, the bank's large 4 character name and its 8 character info. Below it, a 2×4 grid laid out like the pedal: buttons **1 2 3 4** on the top row, **A B C D** on the bottom. Each cell shows the button's label, or its identifier when it has none, and cells of toggle buttons are drawn inverted while the toggle is on, so the state of the whole bank is visible at a glance.

---

## Command line tools

Everything the GUI does is available from the terminal, from the repository root:

```bash
# Flash a configuration to the pedal (normal mode, connected over USB)
.venv/bin/python python/CSV_to_Flash.py my-config.csv

# Read the configuration stored on the pedal into a CSV
.venv/bin/python python/Flash_to_CSV.py current-config.csv
```

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
- More than 8 banks; the flash has room for it.

Ideas and bug reports are welcome through the [issues](https://github.com/Charles5150/midi-commander-custom/issues/new/choose) and [discussions](https://github.com/Charles5150/midi-commander-custom/discussions).

---

## Acknowledgements

- @harvie256: project founder, original firmware, flash-based configuration and SysEx flashing tool
- @eliericha: expansion to 10 commands per button, Python tooling and macOS documentation
- @redcloud80: DMA and interrupt driven display driver
- @BenjaminJensen: the info on expression pedals
- Ivaylo Milanov: PlatformIO migration, DFU packaging workflow and expression pedal ADC pin map
- @arasan95: GUI configurator, LED light modes, HID keyboard output, dual expression pedal filtering and sleep mode
