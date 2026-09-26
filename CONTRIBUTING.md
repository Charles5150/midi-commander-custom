# Contributing

Bug reports, configuration questions and pull requests are welcome. Use the
[issue templates](https://github.com/Charles5150/midi-commander-custom/issues/new/choose)
for bugs and feature requests, and [Discussions](https://github.com/Charles5150/midi-commander-custom/discussions)
for questions.

## Repository layout

| Path | What it is |
|---|---|
| `firmware/` | STM32F103 firmware (HAL, USB MIDI + HID composite device) |
| `python/` | Configuration tools: GUI, `CSV_to_Flash.py`, `Flash_to_CSV.py`, `Backup_Slots.py`, packers and `slotIO.py` (reading and writing a slot) under `lib/` |
| `python/tests/` | Round-trip tests for the CSV packers |
| `docs/manual/` | The user manual, `en/` and `es/` with the same chapters, and the pictures both share |
| `artifacts/` | Built firmware images. Current ones are attached to GitHub releases |
| `tools/`, `scripts/` | DFU packaging helpers used by the PlatformIO build |

## Building the firmware

Install [PlatformIO](https://platformio.org/) (`pip install platformio` or the
VS Code extension), then:

```bash
platformio run -e midi_dfu      # DFU image, also writes artifacts/dfu/platformio-latest.dfu
platformio run -e midi_debug    # ST-Link image at 0x08000000
```

The first build downloads the ARM toolchain. CI builds both environments on
every push and pull request.

`midi_dfu` also packages the binary as a DfuSe container through `scripts/post_build_dfuse.py` and `tools/bin_to_dfuse.py`, writing `artifacts/dfu/platformio-<timestamp>.dfu` and a stable `artifacts/dfu/platformio-latest.dfu`. Flash it as in [Getting started](docs/manual/en/02-getting-started.md#1-flash-the-firmware), or let PlatformIO do it:

```bash
platformio run -e midi_dfu -t upload
```

With the Python environment in `.venv` the upload goes through `Update_Firmware.py`, so a pedal on 0.58 or later needs nothing held and starts the new build by itself. Without it, `dfu-util` is run on its own and the pedal has to be in DFU mode already.

The raw binary can also be flashed directly: `dfu-util --alt 0 -s 0x08003000 --download .pio/build/midi_dfu/firmware.bin`.

Hardware notes (MCU, pinout, I²C addresses) are in `HardwareNotes.txt`; `backup/` holds a dump of the original firmware and EEPROM.

## Flashing

With firmware 0.58 or later already on the pedal, nothing has to be held:

```bash
platformio run -e midi_dfu -t upload     # builds, asks the pedal for DFU mode, flashes, restarts it
.venv/bin/python python/Update_Firmware.py artifacts/dfu/platformio-latest.dfu   # the same, without building
```

`firmware/Core/Src/dfu_entry.c` explains how. Keep its `APP_START` and the DFU
linker script's origin the same; a test checks it. Never write below
0x08003000: without an ST-Link, losing the bootloader is the one way to brick
the pedal.

On older firmware, or by hand:

1. Power the pedal on while holding **Bank Down** and **D**. The display stays
   dark and LED 3 lights up: this is the stock DFU bootloader.
2. `dfu-util -d 0483:df11 --alt 0 --download artifacts/dfu/platformio-latest.dfu`
3. Power cycle. The version shows on the display at boot.

The configuration lives in separate flash pages, so flashing firmware does not
touch it. When a release changes the configuration format the changelog says so;
re-flash the configuration with the updated tools in that case.

## Python tools

```bash
python3 -m venv .venv
.venv/bin/pip install -r python/requirements.txt
.venv/bin/python python/gui_configurator.py            # GUI
.venv/bin/python python/CSV_to_Flash.py config.csv     # flash a configuration
.venv/bin/python python/Flash_to_CSV.py dump.csv       # read it back
.venv/bin/python python/Backup_Slots.py backup my-backup  # every slot at once
.venv/bin/python -m unittest discover -s python/tests  # tests
```

On macOS with Homebrew Python you also need `brew install python-tk`.

## Tests

The Python tools have tests: round trips through the configuration packers, and checks that the numbers the tools and the firmware share still agree:

```bash
.venv/bin/python -m unittest discover -s python/tests
```

GitHub Actions builds both firmware images and runs these tests on every push and pull request.

**Before a release**, with the pedal on USB and the demo configuration (`python/demo-all-features.csv`) active, run the stress test as well. It needs nothing else, no foot and no DIN device, and takes about a minute:

```bash
.venv/bin/python python/Stress_Test.py
```

It plays the same sequence of presses and bank changes twice, over SysEx and through `Remote_Mode`: short, long and double presses, two switches together, scenes, a note held while the bank changes. The first time the line is quiet; the second time the pedal also gets MIDI clock, CCs and notes for `LED_Feedback` to look up, messages for the DIN output, texts over SysEx and a stream of state and screen reads, a few hundred messages a second. Both runs must send the same messages in the same order and leave the same banks and toggles, with no note or momentary CC left on and every SysEx answered. Then `LED_Feedback` gets a snapshot of 125 CCs in one go, and 150 bank changes arrive in bursts, some of them spaced to land as the previous screen finishes going out: every bank entered must be left again with its Bank Enter and Leave commands, and the pedal must end on the last bank asked for, with that bank's screen. Changes that arrive before the pedal has handled the one before are merged, the last one winning, as they always have been. The screen is checked in the pedal's buffer, so look at the panel itself when it finishes; the pedal is put back on the bank it started on. Last, the pedal's own MIDI clock, an LFO and a step sequence are started in bank 6 and the presses and bank changes go on for 15 seconds under the same flood, the pedal now sending on its own as well: it must keep answering, and from firmware 0.65 no press may take more than 5 ms from the switch to its first MIDI message. It exits with 1 when a check fails, and `--seed` repeats a run's random parts. Firmware 0.60 or later.

**Latency.** From 0.65 the pedal times its own presses: from the moment it sees a switch change, or a press from the computer arrives, to the moment the first MIDI message of that press is handed to USB, with the processor's cycle counter. SysEx `GET_LATENCY` (78) returns how many presses it timed, the slowest and the last 16, in microseconds. A press that waits on purpose, one with a long or double press list, is not timed, and a bank switch is timed from its release, which is when it acts. `Latency_Test.py` presses a toggle button and Bank Up forty times each over SysEx, first with the line quiet and then under the stress test's load with the pedal's clock, LFO and sequence running, and prints what the pedal measured next to the computer's own round trip for comparison; on a Mac that round trip alone is about 6 ms, in steps of about 5 ms, which is why the computer cannot time the pedal's part itself. On 0.65 a press takes about 0.25 ms and a bank change about 0.4 ms; the slowest are a press that lands while a screen is being drawn, about 2 ms more. Firmware 0.65 or later.

**Moving an expression pedal from the computer.** From 0.70, SysEx `SET_PEDAL` (80) holds pedal 0 or 1 at a position of its calibrated travel, 0 at the heel to 16383 at the toe in two 7-bit bytes, or gives it back to its jack: `F0 7D 50 <pedal> 1 <high> <low> F7` to hold, `F0 7D 50 <pedal> 0 0 0 F7` to let go. The pedal reads it as a real pedal at that position would, through the filter, the curve and the switches, and answers `SET_PEDAL` reply (81) with the pedal and hold. `MidiCommander.set_pedal(pedal, position)` takes a position from 0.0 to 1.0, or None. It lets a test sweep the pedals without a foot.

## Making changes

- Keep the flash layout in `firmware/Core/Src/flash_midi_settings.c`,
  `python/lib/configPacker.py` and `python/lib/binaryUnpacker.py` in sync, and
  add a round-trip test for any new field.
- Bump `FIRMWARE_VERSION` in `firmware/Core/Inc/main.h` when the SysEx
  protocol or the configuration format changes, and publish the image as a
  GitHub release rather than committing another `artifacts/release-x.y.dfu`.
- Describe user-visible changes in `CHANGELOG.md`, and in the user manual,
  `docs/manual/en/` and `docs/manual/es/`, both languages at once.
- If you can, say in the pull request what you verified on hardware.
