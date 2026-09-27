# In the browser

**English** · [Español](../es/14-in-the-browser.md)

The web configurator does in a browser page what the desktop configurator and the command line tools do: edit a configuration, read and write the pedal's slots, back them up, play the pedal from the screen and update its firmware. Nothing to install, no Python, no `dfu-util`.

**https://charles5150.github.io/midi-commander-custom/**

It needs a browser with Web MIDI and WebUSB: **Chrome**, **Edge** or **Opera**, on a computer. Safari and Firefox have neither. The page runs the tools' own Python code inside the browser, with [Pyodide](https://pyodide.org), so a configuration is checked and packed exactly as the configurator packs it, and the CSV files are the same: a file saved in one opens in the other. The first visit loads about 20 MB, Python and pandas, which the browser then keeps; after that it opens in a few seconds.

## Connecting

Click **Connect the pedal**. The browser asks once whether the page may use MIDI devices, with SysEx: allow it. The header then shows the firmware and the slot the pedal is running. The page finds the pedal again by itself after it restarts.

Close the desktop configurator and any other program using the pedal first: on Windows a MIDI port can only be open in one program at a time.

## Opening a configuration

- **Read from pedal** reads a slot, the running one or another.
- **Open CSV** opens a configuration file, from the configurator, the command line tools or a template.
- **Demo** opens the demo configuration, which uses every feature.

The name of the configuration is at the top, with **changed** after it until it is saved or written. Leaving the page with changes not saved asks first.

## Editing

The tabs follow the desktop configurator's:

- **Banks**: the 32 banks on the left; a bank's name and info line; its eight buttons laid out as on the pedal, 1 to 4 on top and A to D below, each with its label and first command. Click a button to edit it: **Press**, **Long press** and **Double press** each hold ten commands, A to J, and **Press** also the label, the LED mode, the exclusive group and the button's flags. Each command shows the fields its type needs, as in the configurator, with a line saying what it does. Below the buttons, **On entering this bank** and **Expression pedals in this bank**.
- **Global**: every global setting, in the configurator's groups, with the same choices and ranges.
- **Expression**, **Bank switches**, **SysEx**, **Setlist** and **Combos**, as in the configurator.

Every change is checked as it is made. When the configuration could not be packed, a red line under the toolbar says what is wrong and where, and it can be neither saved nor written until that is fixed.

## Saving and writing

- **Save CSV** downloads the configuration as a CSV file.
- **Write to pedal** asks which slot to write, says what that slot holds now, writes it and restarts the pedal: about 12 seconds. As with the configurator, writing the slot the pedal is running pauses the pedal until the restart.
- **Back up all slots** downloads every slot that holds a configuration, one CSV file each.

## Live pedal

The pedal's display, its LEDs and its ten switches, as they are on the pedal, a few times a second. Press a switch on the screen, with the mouse or a finger, to press it on the pedal: it goes down while held, so long presses work too.

## Firmware

Choose a `.dfu` file from the [releases](https://github.com/Charles5150/midi-commander-custom/releases) and click **Update**. The page checks the file first, as `Update_Firmware.py` does, and refuses one that is not an image for this pedal. Then:

1. It asks the pedal to restart in its update mode (firmware 0.58 or later).
2. The first time, the browser asks which device the page may use: choose the one called **STM32 BOOTLOADER** or **DFU in FS Mode**.
3. It erases the firmware's pages, writes the file, reads it all back to check it, and starts the pedal again. About 12 seconds.

The bootloader and the configurations are never touched. A pedal with older firmware, or with the stock firmware, is put in update mode by hand: hold **Bank Down** and **D** while plugging it in, then click **Update** and choose it. This way the very first flash needs nothing installed either.

On Windows the bootloader needs the WinUSB driver, as it does for `dfu-util`: install it once with [Zadig](https://zadig.akeo.ie) for the device `STM32 BOOTLOADER`.

## Running it from the repository

The page is `web/index.html`, and it loads the Python files from `python/lib`. To try a change, serve the repository root and open the page there:

```bash
python3 -m http.server 8000
```

then `http://localhost:8000/web/`. Web MIDI and WebUSB work on `localhost` without HTTPS.

---

[← Command line tools](13-command-line-tools.md) · [Contents](README.md)
