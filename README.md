# Midi Commander Custom Firmware 2.0 (with GUI & LED Control)

Custom firmware for the MeloAudio Midi Commander.
This project is a fork of the original custom firmware, adding a GUI configuration tool for improved usability and advanced LED control features.

## New Features

### 1. GUI Configurator
No need to edit CSV files manually anymore. You can now use a Python-based GUI tool to intuitively change settings.

- **Button Configuration**: Assign up to 10 MIDI commands (PC, CC, Note, PB) per button.
- **LED Mode Settings**: Configure LED behavior individually for each button.
- **Auto Flash**: Transfer settings to the device with a single click.

### 2. Advanced LED Control Modes (LED Light Mode)
You can choose the LED behavior for each button (including Bank Up/Down buttons) from the following three modes:

| Mode | Behavior (Momentary) | Behavior (Toggle) | Use Case |
| :--- | :--- | :--- | :--- |
| **Normal** | Lit while **Pressed** | Lit when **ON** | Standard indicator behavior |
| **Reverse** | Lit while **Released** | Lit when **OFF** | Always lit, turns off when active |
| **AlwaysOn** | Always **Lit**, **Blinks** when Pressed | Always **Lit**, **Blinks** when ON | Improved visibility on dark stages + Status indication |

*Note: The LED mode for Bank Up/Down buttons can be changed from the "Global Settings" tab.*

### 3. Expression Pedal Improvements
Major improvements to expression pedal behavior:
- **Dual Input Support**: Both EXP1 and EXP2 can be used simultaneously.
- **Crosstalk Prevention**: Unused pins are pulled down to preventing noise accumulation.
- **High Impedance Support**: Ensures full range (0-127) even with high impedance consumer pedals using a long recovery time logic.
- **Adaptive Filter**: Balances stability when static and low latency when moving.

---

## Installation & Setup

### Requirements
- Python 3.x
- `dfu-util` (for flashing firmware)

### 1. Preparation
Clone the repository and install the required Python libraries.

```bash
git clone https://github.com/YOUR_USERNAME/midi-commander-custom2.git
cd midi-commander-custom2
pip install -r python/requirements.txt
```

### 2. Flashing the Firmware
First, you need to install the custom firmware that supports these extended features.

1.  **Enter DFU Mode**: Turn on the power while holding down the `Bank Down` + `D` buttons (Screen remains blank, LED 3 lights up).
2.  **Flash**:
    ```bash
    dfu-util --alt 0 --download artifacts/dfu/platformio-latest.dfu
    ```
    *Note: Driver setup may be required on Windows.*

### 3. Launching the Configurator
Connect the Midi Commander to your PC via USB (in Normal Mode) and run the following command:

```bash
python python/gui_configurator.py
```

### 4. Configuration Workflow
1.  **Load CSV**: Load an existing configuration file (Loaded automatically on startup).
2.  **Edit**: Select a button to change commands or LED modes. Click "Apply Changes to Memory".
3.  **Global Settings**: Set modes for Bank Up/Down LEDs here.
4.  **Save CSV**: Save your configuration as a CSV file (**Required**).
5.  **FLASH TO DEVICE**: Transfer settings to the device. The device will automatically restart with the new settings applied.

---

## Credits & Original README

This project is a fork based on the amazing work by the original authors.
For core features and original documentation, please refer to the original repository or the sections below.

# midi-commander-custom (Original)
Custom Firmware for the MeloAudio Midi Commander

There's no intention of this replacing the default firmware functions. I'm creating this purely for custom requirements that the original firmware will never fulfill.

This project provides the following components that work together:

1. A custom firmware to be loaded onto the Midi Commander (e.g. using DFU tool)

2. A publicly available configuration template spreadsheet on Google Sheets that you can customize to your needs

3. The `python/CSV_to_Flash.py` tool that can load a configuration spreadsheet to the Midi Commander through a simple USB connection

# Build status

There is the current build under `artifacts/dfu/generated_xxx.dfu`. See the instructions in the [development environment section](#basic-instructions-for-setting-up-development-environment) for building the firmware locally and/or loading it to the device.