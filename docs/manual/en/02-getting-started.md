# Getting started

**English** · [Español](../es/02-getting-started.md)

This chapter takes a pedal from the factory firmware to your first configuration: flash the firmware once by hand, install the tools, and load a configuration. After that, updates need nothing held.

**With nothing installed.** In Chrome, Edge or Opera, the [web configurator](14-in-the-browser.md) does all of this chapter from a browser page, the first flash included: put the pedal in update mode by hand as in step 1, open the page's **Firmware** tab and choose the `.dfu` file. The rest of this chapter is the route with the desktop tools.

**What you need**

- the pedal, a MeloAudio Midi Commander or a Harley Benton MP-100;
- a USB cable;
- a computer with macOS, Windows or Linux, and Python 3.12 for the desktop tools;
- `dfu-util`, for the first firmware update.

Flashing firmware does not erase your configuration, and the pedal's bootloader is never written, so the stock firmware can always go back on.

## 1. Flash the firmware

The first time, the pedal has to be put in its update mode by hand. The firmware comes as a ready built `.dfu` file attached to the [latest release](https://github.com/Charles5150/midi-commander-custom/releases/latest). Older images are on the [releases](https://github.com/Charles5150/midi-commander-custom/releases) page, and some are also kept in `artifacts/` for reference. You can build the image yourself instead, as [CONTRIBUTING](../../../CONTRIBUTING.md) explains; both routes end in the same place.

1. Install `dfu-util`:
   - macOS: `brew install dfu-util`;
   - Linux: your package manager, for example `sudo apt install dfu-util`;
   - Windows: download it from [dfu-util.sourceforge.net](https://dfu-util.sourceforge.net/releases/), and put `dfu-util.exe` in a folder on the `PATH`, or in the repository's folder of step 2, where the tools look for it too.

   On Windows the pedal in DFU mode also needs the WinUSB driver, once: with the pedal in DFU mode as in step 2, run [Zadig](https://zadig.akeo.ie), choose **STM32 BOOTLOADER** (under **Options → List All Devices** if it is not listed), **WinUSB** as the driver, and **Install Driver**. On Linux, either run `dfu-util` with `sudo`, or let your user reach the pedal with a udev rule, once:

   ```bash
   echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="0483", ATTR{idProduct}=="df11", TAG+="uaccess"' | sudo tee /etc/udev/rules.d/70-midi-commander.rules
   sudo udevadm control --reload-rules
   ```

2. With the pedal off, hold **Bank Down** and **D**, the two bottom-right switches, and switch it on. The display stays dark and LED 3 lights up: the pedal is in DFU mode.
3. Connect it over USB and check that it is seen:

   ```text
   $ dfu-util --list
   Found DFU: [0483:df11] ... alt=0, name="@Internal Flash  /0x08000000/06*002Ka,250*002Kg", ...
   ```

4. Flash it, using `--alt 0`, the internal flash entry in that list:

   ```bash
   dfu-util -d 0483:df11 --alt 0 --download midi-commander-custom-<version>.dfu
   ```

5. Switch the pedal off and on again. After a plain `dfu-util` download it stays in DFU mode until you do. The firmware version shows on the display for a moment, then the first bank.

Once the tools of step 2 are installed, `Update_Firmware.py` can do steps 3 to 5 instead: it flashes a pedal already in DFU mode and starts it again by itself.

## 2. Install the Python tools

The configurator and the command line tools are Python programs in this repository.

1. **Get the files.** Download [the repository as a ZIP](https://github.com/Charles5150/midi-commander-custom/archive/refs/heads/main.zip) and unzip it where you like, or, with git, `git clone https://github.com/Charles5150/midi-commander-custom.git`.
2. **Install Python 3.12.**
   - macOS and Windows: from [python.org](https://www.python.org/downloads/). Its installer comes with Tk, which the configurator's window needs.
   - Linux: your distribution's Python 3 and, on Debian or Ubuntu, `sudo apt install python3-venv python3-tk`.

   Python 3.10 and 3.11 work as well. With a newer Python, python-rtmidi, the library that talks MIDI, is not ready built and has to be compiled, which needs a compiler: on Windows Microsoft's C++ Build Tools, on macOS `xcode-select --install`, on Linux `build-essential libasound2-dev libjack-jackd2-dev`. Several versions of Python can live side by side, and the launcher picks 3.12 when it is there.
3. **Open the launcher** in the repository's folder:
   - macOS: double click **Start Configurator.command**. The first time, macOS may refuse a file downloaded from the internet: right click it, **Open**, and **Open** again.
   - Windows: double click **Start Configurator.bat**. If Windows SmartScreen stops it, **More info** and **Run anyway**.
   - Linux: `./start-configurator.sh` in a terminal.

   The first time it makes a Python environment in the `.venv` folder and installs what the tools need, a minute or two; after that it opens the configurator straight away. When something is missing it says what to install on your system. `--check` sets up and checks without opening the configurator.

<details><summary>The same by hand, in a terminal</summary>

From the repository's folder, macOS and Linux:

```bash
python3 -m venv .venv
.venv/bin/pip install -r python/requirements.txt
.venv/bin/python python/gui_configurator.py
```

Windows:

```bat
py -3.12 -m venv .venv
.venv\Scripts\pip install -r python\requirements.txt
.venv\Scripts\python python\gui_configurator.py
```

This manual writes the commands the macOS and Linux way, `.venv/bin/python python/...`; on Windows they are `.venv\Scripts\python python\...`.

</details>

## 3. Configure the pedal

The configurator is where a configuration is built and sent to the pedal. The launcher of step 2 opens it; from a terminal it is `.venv/bin/python python/gui_configurator.py`.

1. Connect the pedal in normal mode, not DFU mode.
2. Load a starting point:
   - the configurator opens on `python/demo-all-features.csv`, a configuration that uses every feature, with labels saying what each button does;
   - or one of the ready-made [templates](11-devices.md) for a Fractal FM3, a Line 6 HX Stomp or a Kemper Player, with **Load CSV…**;
   - or **Read from Device**, to start from what the pedal holds now.
3. Edit it.
4. Click **Flash to Device**.

[The configurator](03-the-configurator.md) walks through every tab.

## Updating the firmware later

With firmware 0.58 or later on the pedal, an update needs nothing held and no power cycle, and takes about fifteen seconds. Connect the pedal as usual and run

```bash
.venv/bin/python python/Update_Firmware.py midi-commander-custom-<version>.dfu
```

or use **Update Firmware…** under PEDAL in the configurator.

1. It checks the file first, and refuses one that is not an image for this pedal.
2. It asks before flashing; `--yes` skips the question.
3. It asks the pedal to restart in DFU mode, flashes it and starts it again.
4. It says which version the pedal came back with.

A pedal already in DFU mode, put there by hand or by an update that did not finish, is flashed straight away.

The configuration stays as it was. When a release changes the configuration format the [changelog](../../../CHANGELOG.md) says so; flash your configuration again with the updated tools in that case.

## If something goes wrong

- **The pedal stays on FIRMWARE UPDATE, or starts with a dark display as in step 1.** It is waiting in DFU mode for an image, after an update that did not finish. It keeps starting that way until something is flashed. Run `Update_Firmware.py` or **Update Firmware…** again, or flash it with `dfu-util` as in [step 1](#1-flash-the-firmware).
- **You want the stock firmware back.** The bootloader is never touched, so the vendor image can be flashed the same way as in step 1. The configuration of this firmware lives in the microcontroller's own flash, and the stock configuration in the external EEPROM is left untouched.
- **A configuration upsets the rig at power on.** Start the pedal in [safe mode](10-editing-on-the-pedal.md#safe-mode).
- **The pedal restarted by itself and showed RESTARTED.** Its watchdog found it locked up and restarted it, back on the bank, toggles and tempo it had. Please [open an issue](https://github.com/Charles5150/midi-commander-custom/issues) saying what it was doing: a lock-up is a bug.

<details><summary>Under the hood</summary>

The stock bootloader is ST's DFU demo. It starts the firmware only when Bank Down and D are up **and** the firmware's first word, its initial stack pointer, looks valid. Asked over SysEx, the firmware writes zero over that word and restarts, so the bootloader stays in DFU mode; the new image brings a good word back. While the pedal waits in DFU mode its display says **FIRMWARE UPDATE**. If nothing is flashed, it keeps starting in DFU mode, as though the switches were held, until something is.

</details>

---

[← What it does](01-what-it-does.md) · [Contents](README.md) · [The configurator →](03-the-configurator.md)
