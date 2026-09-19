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

## Flashing

1. Power the pedal on while holding **Bank Down** and **D**. The display stays
   dark and LED 3 lights up: this is the stock DFU bootloader.
2. `dfu-util -d 0483:df11 --alt 0 --download artifacts/dfu/platformio-latest.dfu`
3. Power cycle. The version shows on the display at boot.

The configuration lives in separate flash pages, so flashing firmware does not
touch it. When a release changes the configuration format the README says so;
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

## Making changes

- Keep the flash layout in `firmware/Core/Src/flash_midi_settings.c`,
  `python/lib/configPacker.py` and `python/lib/binaryUnpacker.py` in sync, and
  add a round-trip test for any new field.
- Bump `FIRMWARE_VERSION` in `firmware/Core/Inc/main.h` when the SysEx
  protocol or the configuration format changes, and publish the image as a
  GitHub release rather than committing another `artifacts/release-x.y.dfu`.
- Describe user-visible changes in the README under "Changelog".
- If you can, say in the pull request what you verified on hardware.
