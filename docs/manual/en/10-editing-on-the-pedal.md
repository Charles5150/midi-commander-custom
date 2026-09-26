# Editing on the pedal

Everything is easier from the configurator, but the configurator is not always there. Hold **Bank Down and Bank Up together for two seconds** and the pedal opens an editor on the configuration it is running; the same two switches held again leave it. All ten LEDs light while it is open, and none of the switches sends anything, so nothing can go out by mistake.

The screen is a list of named fields with the cursor on one of them, and the switches are:

| Switch | What it does |
| --- | --- |
| **1** / **2** | move the cursor up and down the list |
| **3** / **4** | change the value under the cursor; held, they repeat and speed up |
| **A** / **B** | step to the previous or next command of the button's list |
| **C** | send the command as it stands, so it can be heard |
| **D** | swap the commands for the settings |
| **Bank Down** / **Bank Up** | step to the previous or next bank |

On the commands screen the first fields say what is being edited — bank, button, short or long press, and which of the ten commands — then the command's type and the fields that type has: channel, CC or note number, on and off values, whether it toggles, and so on. Below them come the four characters of the button's label, one field each. The types the editor writes are `---` (no command), `PC`, `CC`, `Note`, `Bank`, `Tap`, `Start`, `Stop`, `Panic` and `Wait`; a command of any other type is shown by name and left exactly as it is until the type field is changed, which replaces it. The double press lists are not offered: they live in an area the tools write as a block.

The settings screen holds the global settings that are a number or a choice: the long press, double press and combination (`COMBO`) times, the two LED brightnesses, how far a long press on Bank Up / Down jumps, the sleep timeout, the bank preview time (`PREVIEW`), the global channel, the bank set aside for the global buttons, what the bank switches do, the setlist, remember state, clock follow, LED feedback, the two thru switches, Kemper mode and the expression pedal CC numbers. The rest, the ones that need text or a list, stay with the configurator.

What you change is written to flash as soon as the cursor leaves the command, the label or the setting, so walking away loses nothing; a star in the title line says there is something not written yet. A write takes about a tenth of a second, during which the pedal is busy: change what you need between songs, not in the middle of one. Afterwards the pedal reads the configuration again, so the new command is live at once, and reading the configuration back with `Flash_to_CSV.py` gives you a CSV with the change in it.

`Edit_Lock` in the Global tab stops the two bank switches opening the editor at all, for a pedal that must not change under anybody's foot. It can only be turned off again from the configurator, or for one session from [safe mode](#safe-mode).

## Safe mode

Hold **any one of the eight command switches** (1–4, A–D) while the pedal powers on, and let go once the display says **SAFE MODE**. The pedal then starts without sending anything, and stays that way until it is switched off:

- no bank enter or leave list runs, neither at start-up nor when the bank changes;
- the saved bank and toggle states are not brought back, even with `Remember_State` on: it starts on bank 0 with everything off;
- `Kemper_Mode` stays off, so no beacon and no questions go to the amp;
- the expression pedals keep their position to themselves until they are moved;
- the switch held at power on is not a press, and letting go of it does nothing.

Everything else works: the buttons send their commands, the bank switches change bank, a configuration can be flashed from the computer, and the [editor](#editing-on-the-pedal) opens even with `Edit_Lock` on, so a wrong Bank Enter command can be found and changed from the pedal itself. Switch it off and on again with nothing held to leave safe mode. A bank changed in safe mode is remembered as usual, so with `Remember_State` on the pedal comes back there.

Bank Down and D held together at power on is still the bootloader's DFU mode, as on the stock pedal. `GET_STATE` reports safe mode in its last byte (firmware 0.60).

---

[← The display](09-the-display.md) · [Contents](README.md) · [Templates and devices →](11-devices.md)
