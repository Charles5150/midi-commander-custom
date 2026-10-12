# In the browser

**English** · [Español](../es/14-in-the-browser.md)

The web configurator does in a browser page what the desktop configurator and the command line tools do: edit a configuration, read and write the pedal's slots, back them up, play the pedal from the screen, show the song you are on large for the stage, and update its firmware. Nothing to install, no Python, no `dfu-util`. And with no pedal at all, it runs the pedal's own firmware in the page: see [Without a pedal](#without-a-pedal).

**https://charles5150.github.io/midi-commander-custom/**

It needs a browser with Web MIDI and WebUSB: **Chrome**, **Edge** or **Opera**, on a computer. Safari has neither. Firefox has Web MIDI, through a site permission add-on it offers when the page first asks, but not WebUSB, so the firmware update needs Chrome, Edge or Opera. The page runs the tools' own Python code inside the browser, with [Pyodide](https://pyodide.org), so a configuration is checked and packed exactly as the configurator packs it, and the CSV files are the same: a file saved in one opens in the other. The first visit loads about 20 MB, Python and pandas, which the browser then keeps; after that it opens in a few seconds.

## Connecting

Click **Connect the pedal**. The browser asks once whether the page may use MIDI devices, with SysEx: allow it. The header then shows the firmware and the slot the pedal is running. The page finds the pedal again by itself after it restarts.

Close the desktop configurator and any other program using the pedal first: on Windows a MIDI port can only be open in one program at a time. Or give the pedal [three USB ports](11-devices.md#three-usb-ports): the page then uses the third, and a DAW can keep the first.

## Without a pedal

**Try without a pedal**, beside **Connect the pedal**, starts a simulated pedal: the firmware itself, the same code the pedal runs, built for the browser. Everything on the page works on it as on the real one: reading and writing its four slots, backing them up, the live view, pressing its switches. It is the way to try a configuration before writing it to the pedal, or to try the firmware before buying one.

- The first time it holds nothing, so the page writes the demo to its slot 1. What you write to it afterwards is kept in the browser, and is there on the next visit.
- The header says **Simulated pedal**, with the firmware it runs. **Stop** turns it off; what was written to it stays.
- Under the live view, **What the pedal sends** lists every message it sends, and says where: over USB, on the DIN output, or as a key of the computer keyboard (**Keys**). **Expression pedals** move its two pedals from heel to toe; its jacks have nothing in them otherwise.
- The **Firmware** tab has nothing to update: the simulated pedal runs the firmware the page came with, which is the newest, sometimes newer than the latest release.

It keeps time as the pedal does, a millisecond at a time, but the browser runs it: a tab in the background slows it down. Nothing outside the page reaches it and nothing answers it: no Kemper, no clock or LED feedback from a computer, no other MIDI program. There is no bootloader to update either.

## Opening a configuration

- **Read from pedal** reads a slot, the running one or another.
- **Open CSV** opens a configuration file, from the configurator or the command line tools.
- **Demo** opens the demo configuration, which uses every feature.
- **Your rig** opens one of the templates that come with the tools, made for a device or a program: a Quad Cortex, a BigSky, Ableton Live and the rest of [the templates](11-devices.md). Up to three more devices, each on its channel, add their footswitches or looper to it in banks of their own, as [Your rig](11-devices.md#your-rig-several-devices-at-once) explains, and a list then says what to set on each device. It opens with no file name, so **Save CSV** names it after the configuration.

The start page has the same four, and none of them can be pressed while the pedal is being read or written.

The name of the configuration is at the top, with **changed** after it until it is saved or written; a change made while the pedal is being written stays marked, since it is not on the pedal. Leaving the page with changes not saved, or while the pedal is being written or updated, asks first.

## Editing

The tabs follow the desktop configurator's:

- **Banks**: the 32 banks on the left; a bank's name and info line; its eight buttons laid out as on the pedal, 1 to 4 on top and A to D below, each with its label and first command. Click a button to edit it: **Press**, **Long press** and **Double press** each hold ten commands, A to J, and **Press** also the label, the LED mode, the exclusive group and the button's flags. Each command shows the fields its type needs, as in the configurator, with a line saying what it does. **Device…** beside the type fills a command from a device's MIDI map, and a CC or Program Change shows the device's name for it, as [in the configurator](03-the-configurator.md#from-a-devices-midi-map); its last entry, **More devices…**, finds one of the 571 community devices by maker or model, and loads them, about 170 kB, only then. Below the buttons, **On entering this bank** and **Expression pedals in this bank**. **Save song** and **Load song**, beside the bank's name, save the bank as a [song file](04-banks.md#songs-a-bank-in-a-file-of-its-own) and load one into it. **Notes for the Stage view** holds the bank's note for [Stage](#stage).
- **Global**: every global setting, in the configurator's groups, with the same choices and ranges.
- **Expression**, **Bank switches**, **SysEx**, **Setlist**, **Combos**, **MIDI map** and **Preset names**, as in the configurator.

Every change is checked as it is made. When the configuration could not be packed, a red line under the toolbar says what is wrong and where, and it can be neither saved nor written until that is fixed.

The whole page works from the keyboard and with a screen reader: every field has a name, the tab, bank, button and press being edited are marked as the current one, and after a click or a change the focus stays where it was. Messages are read out as they appear.

## Saving and writing

- **Save CSV** downloads the configuration as a CSV file.
- **Cheat sheet** opens the configuration in a new tab as a page to print, with a **Print** button: each bank's switches as on the pedal and what they send in words, the setlist with its tempos, the pedals and the combinations, as [Cheat_Sheet](13-command-line-tools.md#cheat_sheet-a-page-to-print) makes it. A browser that blocks the tab downloads the page instead.
- **Write to pedal** asks which slot to write, reads it, which takes a few seconds, and lists what writing will change in it, as [Diff_Config](13-command-line-tools.md#diff_config-what-changes) does: the wrong slot or an old file shows before anything is written. Choosing another slot reads that one. **Write** does not wait for the list. Then it writes the slot and restarts the pedal: about 12 seconds. As with the configurator, writing the slot the pedal is running pauses the pedal until the restart. If the pedal does not take the slot asked for, nothing is written; if a write fails after the slot was erased, the page says so, and the slot needs writing again. Firmware before 0.24 has a single configuration, so the page offers slot 1 only.
- **Back up all slots** reads every slot that holds a configuration, then lists them, one CSV file each: **Save all** downloads them together, or click one to download it alone. The browser may ask once whether the page may download several files. With no slot holding a configuration it says so.

## Live pedal

The pedal's display, its LEDs and its ten switches, as they are on the pedal, a few times a second. It needs firmware 0.27 or later; with older firmware the tab says so. Press a switch on the screen, with the mouse or a finger, to press it on the pedal: it goes down while held, so long presses work too. From the keyboard, Tab to a switch and hold Space or Enter.

## Stage

The song you are on, readable from a few steps away, for a tablet or a laptop on a mic stand. **Full screen** fills the screen with it, and the page keeps the screen from sleeping while the tab is open. It follows the pedal a few times a second, from firmware 0.27:

- the bank's name, large, and its info line;
- where it is in the setlist, `FULL SET · 3 of 10`, and the next song, `Next: S04 · song 4`, or `Last song`;
- the tempo, `120 BPM`, while the pedal sends MIDI clock over USB, and the bar and beat, `bar 5 · 3`, while the clock runs after a Start; the beats in a bar are those of **Bar and beat on the display**, 4 unless set;
- the bank **Bank Up** or **Bank Down** is showing before it is confirmed, with `Bank_Preview` on;
- the bank's note, from **Notes for the Stage view** in the Banks tab: the key, a capo, cues, lyrics;
- the eight buttons as large tiles, 1 to 4 above and A to D below, with their labels as the pedal shows them, a lit toggle in colour.

The setlist, the info line and the notes come from the configuration open in the page, so open the one the pedal runs, or read it from the pedal and then open the CSV with the notes. When the bank's name there is not the pedal's, the view takes it for another configuration and shows the pedal's bank and buttons only. A bank in several setlists is placed in the first that has it, and stays in that one while the next banks are in it too; **Setlist** picks one by hand.

The notes are kept in the CSV, in a `Notes` column of `Bank_Naming`, and in a song file saved from the bank; the pedal never holds them, so writing them changes nothing on it, and reading a configuration from the pedal brings none. The desktop configurator keeps them when it saves. On an iPad, Safari has no Web MIDI: the page needs a browser that adds it.

## Firmware

Choose a `.dfu` file from the [releases](https://github.com/Charles5150/midi-commander-custom/releases) and click **Update**. The page checks the file first, as `Update_Firmware.py` does, and refuses one that is not an image for this pedal. Then:

1. It asks the pedal to restart in its update mode (firmware 0.58 or later).
2. The first time, the browser asks which device the page may use: choose the one called **STM32 BOOTLOADER** or **DFU in FS Mode**.
3. It erases the firmware's pages, writes the file, reads it all back to check it, and starts the pedal again. About 15 seconds.

The bootloader and the configurations are never touched. A pedal with older firmware, or with the stock firmware, is put in update mode by hand: hold **Bank Down** and **D** while plugging it in, then click **Update** and choose it. This way the very first flash needs nothing installed either.

On Windows the bootloader needs the WinUSB driver, as it does for `dfu-util`: install it once with [Zadig](https://zadig.akeo.ie) for the device `STM32 BOOTLOADER`. On Linux the browser needs the udev rule of [Getting started](02-getting-started.md#1-flash-the-firmware) to reach it.

## When something goes wrong

- **The configurator's Python could not load.** The page reads, checks and packs configurations with the tools' own Python, which the browser fetches from cdn.jsdelivr.net the first time. Offline, or with that site blocked by an extension or a company network, the start page says so in red, with **Reload the page**. Live pedal and Firmware work without it; opening, reading and writing a configuration do not, and a simulated pedal starts empty.
- **A file that is not a configuration** is refused with what it lacks, and the configuration open stays open.
- **The demo or a template does not download**, offline for example: the page says so, and the configuration open stays open.
- **Part of a configuration left out.** Firmware before 0.90 takes no MIDI map and no long press labels, and before 0.26 no double press: **Write to pedal** writes the rest, says what it left out, and keeps the configuration marked **changed**, since the pedal does not hold all of it.
- **A SysEx string the pedal would not send as written**, a byte that is not hexadecimal, one over `7F`, or more than 23 bytes, is named in the red line under the toolbar, and the configuration can be neither saved nor written until it is fixed.
- **The browser did not allow MIDI.** Chrome remembers a refusal. The page says how to allow it again: the icon left of the address bar, the site settings, **MIDI devices** (in Chrome "Control and reprogram your MIDI devices") to Allow, then reload.
- **The pedal does not answer.** A Midi Commander found but silent most likely runs MeloAudio's own firmware: the page says so and opens the Firmware tab, where it is updated with the pedal put in update mode by hand.
- **An update failed** after the pedal had gone into its update mode: it stays there, with its screen dark, and the Firmware tab says so. Press **Update** again with the same file; the pedal does not need to be connected first.

A message that needs reading stays under the toolbar until it is closed with ×, or until the pedal connects. An error in the corner also stays until closed with ×; the other messages there go after a few seconds.

## Running it from the repository

The page is `web/index.html`, and it loads the Python files from `python/lib`. The simulated pedal is `web/pedal-sim.wasm`, built from the firmware's sources with `firmware/sim/build.sh` (see [its README](../../../firmware/sim/README.md)). To try a change, serve the repository root and open the page there:

```bash
python3 -m http.server 8000
```

then `http://localhost:8000/web/`. Web MIDI and WebUSB work on `localhost` without HTTPS.

---

[← Command line tools](13-command-line-tools.md) · [Contents](README.md)
