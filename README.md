# Midi Commander Custom Firmware (Fork)

This repository is a fork of the custom firmware for MeloAudio Midi Commander.
It adds a GUI-based configuration tool and expanded LED control options.

## Added Features

### 1. GUI Configurator
A Python script (`python/gui_configurator.py`) has been added to edit configurations via a GUI, replacing the manual CSV editing process.
It allows setting MIDI commands, LED modes, and flashing the firmware directly.

### 2. LED Light Modes
Three LED behaviors are now available for each button:

| Mode | Behavior (Momentary) | Behavior (Toggle) |
| :--- | :--- | :--- |
| **Normal** | Lit while Pressed | Lit when ON |
| **Reverse** | Lit while Released | Lit when OFF |
| **AlwaysOn** | Always Lit, Blinks when Pressed | Always Lit, Blinks when ON |

*Bank Up/Down LED modes can be configured in the Global Settings tab.*

### 3. Expression Pedal Adjustments
- Enabled support for both EXP1 and EXP2.
- Added input pull-down to prevent floating signals.
- Adjusted handling for high impedance pedals.
- Implemented adaptive filtering for stability.

---

## Installation

### Requirements
- Python 3.x
- `dfu-util`

### Setup
Clone the repository and install dependencies:

```bash
git clone https://github.com/arasan95/midi-commander-custom.git
cd midi-commander-custom
pip install -r python/requirements.txt
```

### Flashing Firmware
1.  Enter DFU Mode: Power on while holding `Bank Down` + `D`.
2.  Flash the firmware:
    ```bash
    dfu-util --alt 0 --download artifacts/dfu/platformio-latest.dfu
    ```

### Usage
Connect the device via USB and run:

```bash
python python/gui_configurator.py
```

1.  **Edit**: Change button commands and modes.
2.  **Save CSV**: Save the configuration file.
3.  **Flash**: Write settings to the device.

---

## Original Project

This project is based on the original custom firmware.
Please refer to the original repository for core functionalities and details.

# midi-commander-custom (Original README)
Custom Firmware for the MeloAudio Midi Commander

There's no intention of this replacing the default firmware functions. I'm creating this purely for custom requirements that the original firmware will never fulfill.

This project provides the following components that work together:

1. A custom firmware to be loaded onto the Midi Commander (e.g. using DFU tool)

2. A publicly available configuration template spreadsheet on Google Sheets that you can customize to your needs

3. The `python/CSV_to_Flash.py` tool that can load a configuration spreadsheet to the Midi Commander through a simple USB connection

# Build status

There is the current build under `artifacts/dfu/generated_xxx.dfu`. See the instructions in the [development environment section](#basic-instructions-for-setting-up-development-environment) for building the firmware locally and/or loading it to the device.