# Getting started

You need the pedal, a USB cable, Python 3 and, to update the firmware, `dfu-util`.

## 1. Flash the firmware

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

### From then on, nothing has to be held

With firmware 0.58 or later on the pedal, connect it as usual and run

```bash
.venv/bin/python python/Update_Firmware.py midi-commander-custom-<version>.dfu
```

or use **Update Firmware…** in the PEDAL section of the configurator. It checks the file first, and refuses one that is not an image for this pedal. Then it asks the pedal to restart in DFU mode, flashes it and starts it again, and says which version it came back with. A pedal already in DFU mode, put there by hand or by an update that did not finish, is flashed straight away.

How it works: the stock bootloader is ST's DFU demo, which starts the firmware only when Bank Down and D are up **and** the firmware's first word, its initial stack pointer, looks valid. Asked over SysEx, the firmware writes zero over that word and restarts, so the bootloader stays in DFU mode, and the new image brings a good word back. While the pedal waits in DFU mode its display says **FIRMWARE UPDATE**. If nothing is flashed it keeps starting in DFU mode, as though the switches were held, until something is.

Flashing firmware does not erase your configuration. When a release changes the configuration format the [changelog](../../../CHANGELOG.md) says so; re-flash your configuration with the updated tools in that case.

## 2. Install the Python tools

```bash
git clone https://github.com/Charles5150/midi-commander-custom.git
cd midi-commander-custom
python3 -m venv .venv
.venv/bin/pip install -r python/requirements.txt
```

On macOS with Homebrew Python, the GUI also needs Tk: `brew install python-tk`.

## 3. Configure the pedal

```bash
.venv/bin/python python/gui_configurator.py
```

Connect the pedal in normal mode (not DFU), click **Read from Device** to load what it currently holds, edit, then **Flash to Device**. The next section walks through the configurator.

---

[← What it does](01-what-it-does.md) · [Contents](README.md) · [The configurator →](03-the-configurator.md)
