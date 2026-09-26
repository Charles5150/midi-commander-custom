# The configurator

`python/gui_configurator.py` edits a configuration CSV and exchanges it with the pedal over USB MIDI.

<img src="../../images/gui_workflow.png" width="500">

**Sidebar.** Two groups, the file and the pedal, with the name of the open file at the bottom.

- **File: Load CSV** opens a configuration file. `python/demo-all-features.csv` is loaded at start, so every feature is there to look at straight away. **Save CSV** writes the current settings to the open file.
- **Pedal: Slot** chooses which of the four configuration slots the two buttons below it use. `Active` means the one the pedal is running; flashing one slot never touches the others. **Read from Device** pulls that configuration from the connected pedal into a CSV you choose, and loads it. **Flash to Device**, the one red button, saves the CSV, transfers it to the pedal and reboots it. **Back Up All Slots** reads every slot that holds a configuration into a new dated folder, one CSV per slot, and **Restore Backup** writes such a folder back, each file to its own slot, after showing which ones it will replace. **Update Firmware** flashes a `.dfu` file, with nothing held on firmware 0.58 or later (see [Getting started](02-getting-started.md#1-flash-the-firmware)).

The tabs follow the order a configuration is usually built in. Each starts with a one line summary; the **?** next to it opens the details.

**Buttons** — pick a bank, then a button from the eight laid out as on the pedal, 1 to 4 on top and A to D below; the one being edited is highlighted. At the top you set its **display label**, **LED light mode** and **exclusive group**, and tick **Momentary when held**, **Flash at the tempo** or **Global**; below, ten command slots A–J. Choose a slot's command type and only the fields that type uses appear. **Short press / Long press / Double press** switches the slots between the three command sets of the button. Edits are kept in memory automatically when you switch button, bank or tab. **Copy bank** and **Paste bank** duplicate a whole bank onto another: labels, LED modes, groups, short, long and double press commands and the commands sent on entering the bank. The target becomes identical to the source, so anything it had that the source does not is removed, and its name is kept, since a copy is usually the start of a variant. Pasting asks for confirmation first.

<img src="../../images/gui_button_config.png" width="500">

**Banks** — the 4 character name and 8 character info line of each bank, and where the expression pedals send while it is selected: a CC and a channel per pedal, each `Default` to keep the pedal's own, or `Off` for the CC to silence the pedal in that bank, and the lowest and highest value it sends there, left empty to keep the pedal's own range.

**Bank Enter** — the commands each bank sends when you switch to it, and, below a `Leave` command, when you leave it.

**Bank Switch** — the command lists of the Bank Down and Bank Up switches, one per switch and press length. Combine it with **Bank switches** (`Bank_Switch_Mode`) in the Global tab.

<img src="../../images/gui_bank_switch.png" width="500">

**Combos** — the two switch combinations, one row each: the two switches, the bank it counts in or all banks, and the list it runs, named by bank, button and short, long or double press. How long a switch waits for the other one is **Two switches together within** in the Global tab.

**Setlist** — the order Bank Up / Down follow when **Follow the setlist** (`Setlist_Mode`) is on, one drop-down per position listing every bank by number and name. The list ends at the first empty row.

**Expression** — per pedal: end points, response curve, invert, channel, the toe and heel switches, the output range, what it sends (CC, Pitch Bend or 14-bit CC) and auto-engage. **Connect live view** shows the pedal position and the CC being sent, read from the pedal in real time. To calibrate: press **Calibrate**, sweep the pedal slowly from heel to toe and back a couple of times, press **Done**; the end points are filled in with a small margin so 0 and 127 are always reached.

**SysEx** — the sixteen stored SysEx messages, with the byte count or a parse warning as you type.

**Global** — the global settings in groups: Configuration, Presses, LEDs, Banks, USB MIDI and Power. Each setting has a plain name, a short hint and, in small print, its label in the CSV, which is the name the [reference](12-configuration-file.md#global_settings) uses. Bounded settings are drop-downs or check boxes; numbers are limited to their valid range.

**Virtual Pedal** — the pedal as it is right now, laid out like its board: five switches a row with Bank Up and Down at the right, each LED at its real brightness, blinking and dimmed ones included, and between the rows the pedal's screen, mirrored pixel for pixel, so overlays and inverted toggle cells show exactly as on the pedal. Click a switch to tap it, hold the mouse button for a long press, click twice quickly for a double press. The press goes through exactly the same path as a foot, so long and double presses, the bank switches and everything they send behave as on the pedal. A switch held here lets go by itself after 10 seconds. Shares the Expression tab's connection; needs firmware 0.27.

<img src="../../images/gui_virtual_pedal.png" width="500">

---

[← Getting started](02-getting-started.md) · [Contents](README.md) · [Banks →](04-banks.md)
