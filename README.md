# Midi Commander Custom Firmware

This is a fork of the custom firmware for MeloAudio Midi Commander.
It introduces a GUI configuration tool and advanced LED control modes.

## New Features

### GUI Configurator
A Python-based GUI (`python/gui_configurator.py`) allows for easy configuration editing and flashing, removing the need to edit CSV files manually.

### LED Light Modes
Three modes are available for button LEDs:
- **Normal**: Standard behavior.
- **Reverse**: Inverted behavior (lit when released/OFF).
- **AlwaysOn**: Always lit, blinks when active (pressed/ON).

### Bank LED Settings
Bank Up/Down LED behaviors can also be customized via Global Settings.

### Usage
Run the configurator:
```bash
python python/gui_configurator.py
```

---

# midi-commander-custom
Custom Firmware for the MeloAudio Midi Commander

There's no intention of this replacing the default firmware functions. I'm creating this purely for custom requirements that the original firmware will never fulfill.

This project provides the following components that work together:

1. A custom firmware to be loaded onto the Midi Commander (e.g. using DFU tool)

2. A publicly available configuration template spreadsheet on Google Sheets that you can customize to your needs

3. The `python/CSV_to_Flash.py` tool that can load a configuration spreadsheet to the Midi Commander through a simple USB connection

# Build status
There is the current build under `artifacts/dfu/generated_xxx.dfu`. See the instructions in the [development environment section](#basic-instructions-for-setting-up-development-environment) for building the firmware locally and/or loading it to the device.

Anything I leave in there has had a bit of testing on my device, and everything appears to be working ok.  These are still Dev builds, so it's likely they'll have bugs.  But it's something you can play with, and you should be able to go back to an meloaudio build.

Uploading the DFU binary is the same as for the meloaudio firmware.  So download the firmware update tools from the meloaudio website (or directly from ST - package STSW-STM32080) and follow the upgrade manual.

I have had a lot of issues under Windows 10, and there are reports from others on the net to this effect. So I'm using a Windows 7 Virtual Machine to test the DFU aspects, which works fine.

# Improvements in this commit
24 Apr 22 - The display driver has been modified to use DMA for all transfers, and interrupts to kick off the transfer of each line.  The result is the processor isn't stalled waiting for the display to update. This will allow the display to be utilised more on individual key presses without resulting in delays.  From an end user perspective, there should be no visable change.

# Current features list
- Completely open source, so feel free to contribute (even just bug reports! or better still user guides)
- "Spreadsheet" based configuration, no scrolling through menus on that tiny screen with huge buttons. Easy Copy/Paste, Fill, etc. Easy sharing.
- Supports Program Change (aka Patch Change), Controller Change, Note, Pitch Bend and Start/Stop messages for any of the buttons.
- The Channel for each message is configured on each individual command.  So it can address seperate pieces of hardware in a midi chain.
- 8 banks of 8 buttons.  Each bank can display message strings for identification.
- 0 to 10 independant chained commands on each switch/bank position.  Enables configuring different devices, or a series of actions of each button push.
- CC, Note and Pitch Bend support momentary, toggle, or an on-duration of up to 2.5 sec in 10ms increments. CC can also send just the start message.
- Program Change messages can include the Bank Select messages prior to the PC message, either just the Lease Signficant Byte or both the LSB & MSB.
- Pass through of Sync/Start/Stop messages from USB to the Serial MIDI connector.
- Dual expression pedal inputs (PA7/PB0 via ADC1 ch7/ch8) emit MIDI CCs (EXP1 → CC#11, EXP2 → CC#4) on the configured global channel.

- Firmware can be loaded through the normal DFU update process.
- Configuration has been moved to the FLASH memory, so this will not affect the standard Melo firmware configuration that is stored in an external EEPROM.

# Still to come
- The battery management has not been considered yet.  Not sure if it even works on batteries with this.
- Plenty of code tidying to be done
- Plenty of testing needed
- Needs documentation.

## Expression pedals

Both 1/4" expression jacks now route to `ADC1` (channels 7 and 8 on PA7/PB0). The firmware samples each pedal every 5 ms, applies a small dead-zone, and transmits MIDI CC messages immediately when the value moves at least two counts. By default:

- EXP1 → CC #11 (Expression 1)
- EXP2 → CC #4 (Foot Control 2)

The channel comes from the “Global Channel” field in the flash configuration, so you can point the pedals at any target rig without code changes. You can tweak CC numbers or the sampling interval in `firmware/Core/Src/expression.c` if you need a different mapping or response curve.

If a connected pedal still produces no CC output (e.g. `amidi -d` remains silent), follow the step-by-step guide in `docs/expression_pedal_troubleshooting.md` to verify firmware, hardware wiring, and MIDI monitoring.


# Configuration
The configuration is done via a spreadsheet. Here is a publicly available template on Google Sheets that you can copy and customize to your needs:

https://docs.google.com/spreadsheets/d/1KwKj3sYrNEkEl8ONipW-ZGSLD7r_W1NfWwyGgjnbk08/edit?usp=sharing

(a copy of this spreasheet is also availble in the repository at `python/MeloConfig_10_Cmds - RC-600.csv`)

Roughly, the spreadsheet allows you to specify for each button press up to 10 independant MIDI commands. For each command the following characteristics can be chosen independently:

- Type: PC/CC/Note/PB (Pitch Bend)/Start/Stop
- Midi Channel
- PC/CC/Note number
- CC/PB button on value
- CC/PB button off value
- PC bank select value
- PC bank select value high byte
- CC/PB/Note toggle mode
  - If disabled, the button on value is sent when the button is held down, and the button off value is sent when the button is released. So each button press results in 2 commands sent.
  - If enabled, the button on value is sent at the first button press, and the button off value is sent at the next button press and so on. So each button press results in 1 command sent. The LED of the button is toggled on and off at each button press.
- Note velocity
- Note/PB duration (up to 2.5 seconds in 10ms increments)

Lines starting with `#` or `*` are simply ignored which allows you to include comments in the configuration file to keep track of your work.

Once you are happy with your configuration, download it from Google Sheets as a CSV file (or use "Save As" if you chose to edit it locally with Excel or similar spreadsheet software).

Then prepare a Python environment as follows:

1. Download and install [Python](https://www.python.org/).
2. Check out this repository with Git or download it as a Zip and extract it somewhere.
3. Open a Terminal (or Windows Command Prompt) and run the following:

   ```
   cd /path/to/midi-commander-custom
   python3 -m pip install -r python/requirements.txt
   python3 python/CSV_to_Flash.py -h
   ```

   If your setup is successful, the last command should display the help message of the tool.

Once your Python environment is operational, you can load your configuration onto the Midi Commander as follows:

1. Turn on the Midi Commander in normal mode (not DFU)
2. Connect it to the USB port of your computer
3. Run the following in a Terminal or in the Windows Command Prompt:

   ```
   cd /path/to/midi-commander-custom
   python3 python/CSV_to_Flash.py /path/to/you/configuration-file.csv
   ```

The tool will convert the CSV file to a binary format and transmit it to the Midi Commander. At the end of the operation the Midi Commander should restart to load the new configuration.

# Basic instructions for setting up development environment
Install the [PlatformIO](https://platformio.org/) CLI (`pipx install platformio` works well) or the PlatformIO VS Code extension. All firmware sources now live under `firmware/`, so `platformio run -e midi_debug` produces the debugger-friendly image and `platformio run -e midi_dfu` outputs the DFU-offset build (and packages it automatically). No STM32CubeIDE metadata remains in the repository.

## PlatformIO workflow (Linux/macOS/Windows)

PlatformIO reproduces both build targets from the command line or the VS Code extension and keeps the sources inside `firmware/`. The firmware is still linked to run at `0x08003000` and the startup code now relocates the vector table automatically, so no extra bootloader tweaks are required.

1. Install the PlatformIO CLI (`pipx install platformio`, `pip install --user platformio`, or use the PlatformIO VS Code extension).
2. Build the DFU-offset firmware:

   ```bash
   platformio run -e midi_dfu
   ```

   On success PlatformIO prints a line from `[post_build_dfuse]` showing the freshly generated DFU file under `artifacts/dfu/platformio-<timestamp>.dfu` and copies it to `artifacts/dfu/platformio-latest.dfu`.
3. Put the pedal in DFU mode and flash the DFU container. You can either let PlatformIO handle both the packaging and upload via the bundled `dfu-util`:

   ```bash
   platformio run -e midi_dfu -t upload
   ```

   The `scripts/post_build_dfuse.py` hook regenerates `artifacts/dfu/platformio-<timestamp>.dfu` and a stable `platformio-latest.dfu`, then `scripts/dfu_upload.py` runs `dfu-util --alt 0 --download artifacts/dfu/platformio-latest.dfu` with the STM32 DFU VID/PID (`0483:df11`).

   Or invoke `dfu-util` yourself (handy when scripting or working on a different machine):

   ```bash
   dfu-util --alt 0 --download artifacts/dfu/platformio-latest.dfu
   ```

   The DFU file already targets `0x08003000`, so you do not need to pass `--dfuse-address` when using the packaged image. If you prefer writing the raw binary directly, use:

   ```bash
   dfu-util --alt 0 -s 0x08003000 --download .pio/build/midi_dfu/firmware.bin
   ```

4. For ST-Link workflows run `platformio run -e midi_debug -t upload`; this mirrors the Cube “Debug” target.

Every build keeps the MeloAudio bootloader intact, so you can always revert to the stock firmware by flashing a vendor DFU image.

### Capturing MIDI traffic for debugging

Once the pedal enumerates as `MIDI Commander Custom`, you can monitor the raw MIDI stream via ALSA tools on Linux:

```bash
# List ALSA raw MIDI ports and note the hw:X,Y,Z number
amidi -l

# Dump incoming bytes until Ctrl+C
amidi -d -p hw:2,0,0

# Record to a file for later inspection
amidi -d -p hw:2,0,0 > midi_dump.bin

# View decoded events instead of raw hex
aseqdump -p 'MIDI Commander Custom'
```

Make sure no other application exclusively owns the ALSA port (close DAWs/PipeWire bridges or use their routing features) before running `amidi`. On macOS/Windows you can use MIDI-OX, MIDI Monitor, or similar tools to achieve the same result.

## Loading the firmware

### macOS

On macOS the firmware can be loaded with [dfu-util](https://dfu-util.sourceforge.net/) which can be installed using [Homebrew](https://brew.sh/) with a simple `brew install dfu-util`.

Then you connect the Midi Commander to the USB port of the computer and start it in DFU mode by holding down the `bank down` and `D` buttons (the two buttons on the bottom-right corner) while pressing the power button. The device should start with nothing on the display, and the LED 3 turned on.

`dfu-util` should now be able to detect the device:

```text
$ dfu-util --list
...
Found DFU: [0483:df11] ver=0200, devnum=12, cfg=1, intf=0, path="4-1", alt=2, name="@NOR Flash : M29W128F/0x64000000/0256*64Kg", serial="5CE867623433"
Found DFU: [0483:df11] ver=0200, devnum=12, cfg=1, intf=0, path="4-1", alt=1, name="@SPI Flash : M25P64/0x00000000/128*64Kg", serial="5CE867623433"
Found DFU: [0483:df11] ver=0200, devnum=12, cfg=1, intf=0, path="4-1", alt=0, name="@Internal Flash  /0x08000000/06*002Ka,250*002Kg", serial="5CE867623433"
```

If you have a DFU file (e.g. from `artifacts/dfu/generated-*.dfu`), you can load it as follows. `--alt 0` should be used because it corresponds to the address range of the internal flash `0x80000000` in the list above.

```bash
dfu-util --alt 0 --download ./artifacts/dfu/generated-*.dfu
```

If you are building the firmware yourself, `platformio run -e midi_dfu` already emits both `.pio/build/midi_dfu/firmware.bin` and the packaged DFU under `artifacts/dfu`. You can also sidestep the DFU wrapper and push the raw binary directly:

```bash
dfu-util --alt 0 -s 0x8003000 --download .pio/build/midi_dfu/firmware.bin
```

Once the firmware is loaded, turn off the device and turn it back on in normal mode. You should see the name and version of the custom firmware on the display briefly, and then the name of the first configured bank. You can now load your own configuration following the instructions in the section [Configuration](#configuration).

### Manually re-running the DFU packer

The post-build hook calls `tools/bin_to_dfuse.py` for you (producing both a timestamped file and `platformio-latest.dfu`), but you can still run it manually to regenerate a DFU with custom metadata or filenames:

```bash
platformio run -e midi_dfu
python tools/bin_to_dfuse.py --bin .pio/build/midi_dfu/firmware.bin
```

This command emits `artifacts/dfu/platformio-<timestamp>.dfu`, refreshes `platformio-latest.dfu`, and keeps everything ready for flashing with ST's DFU utilities. Use `--out` to choose a different filename or `--address`, `--vendor`, `--product`, etc. if you ever need to adjust the metadata. Pass `--overwrite` when reusing the same output path.

## Python development

Python files under `python/` can be edited directly, however it is recommended to use the VS Code workspace at the root of this repository with the recommended extensions. It is configured to use auto-formatting with Black and type checking with MyPy.

The main entry point is `python/CSV_to_Flash.py` and some functionality is offloaded to modules under `python/lib`.

## Acknowledgements
- @harvie256: project founder
- @eliericha: expansion to 10 commands per button
- @BenjaminJensen: the info on expression pedals