# Editing on the pedal

**English** · [Español](../es/10-editing-on-the-pedal.md)

Everything is easier from the configurator, but the configurator is not always there: the wrong Program Change turns up at soundcheck, with no laptop in sight. The pedal has an editor of its own, on its own screen, worked with your feet.

## Opening and closing it

Hold **Bank Down and Bank Up together for two seconds** and the pedal opens the editor on the configuration it is running; the same two switches held again leave it.

- All ten LEDs light while it is open.
- None of the switches sends anything while it is open, nor do the pedals' toe, heel and auto-engage buttons, so nothing can go out by mistake.
- If a [bank preview](04-banks.md#bank-preview) is showing, opening the editor drops it.

## The switches

![The editor's two screens and what each switch does](../images/editor-en.svg)

The screen is a list of named fields with the cursor on one of them:

| Switch | What it does |
| --- | --- |
| **1** / **2** | move the cursor up and down the list |
| **3** / **4** | change the value under the cursor; held, they repeat and speed up |
| **A** / **B** | step to the previous or next command of the button's list |
| **C** | send the command as it stands, so it can be heard |
| **D** | swap the commands for the settings |
| **Bank Down** / **Bank Up** | step to the previous or next bank |

## Editing a button's commands

On the commands screen the first fields say what is being edited:

1. the bank;
2. the button;
3. short, long or double press, the last only when the configuration has double press commands;
4. which of the ten commands.

Then come the command's type and the fields that type has — channel, CC or note number, on and off values, whether it toggles, and so on — and below them the four characters of the button's label, one field each.

The editor writes these types:

`---` (no command), `PC`, `CC`, `Note`, `Bank`, `Tap`, `Start`, `Stop`, `Panic` and `Wait` (a pause; one [on the beat](06-commands.md#on-the-beat) is left alone).

A command of any other type is shown by name and left exactly as it is until the type field is changed, which replaces it. The double press lists live in an area the tools write as a block: a configuration with no double press commands at all, or written for firmware older than 0.26, has none, so the editor offers only the short and long lists there.

## Editing the settings

**D** swaps to the settings screen, which holds the global settings that are a number or a choice. The rest, the ones that need text or a list, stay with the configurator.

| On the pedal | In the configurator (CSV) |
|---|---|
| `LONGPRES` | the long press time (`Long_Press_ms`), 100–2500 ms |
| `DBLPRESS` | the double press time (`Double_Press_ms`), 100–1000 ms |
| `COMBO` | the combination time (`Combo_ms`) |
| `BRIGHT`, `RESTBRIG` | the two LED brightnesses (`LED_Brightness`, `LED_Rest_Brightness`), 1–100 % |
| `BANKJUMP` | how far a long press on Bank Up / Down jumps (`Bank_Jump_Step`) |
| `SLEEP` | the sleep timeout (`Sleep_After_Min`) |
| `GLOBCHAN` | the global channel (`Global_Channel`) |
| `GLOBBANK` | the bank set aside for the global buttons (`Global_Bank`), as the editor shows its number, 0 for none |
| `BANK SW` | what the bank switches do (`Bank_Switch_Mode`) |
| `PREVIEW` | the bank preview time (`Bank_Preview`) |
| `SETLIST` | follow the setlist (`Setlist_Mode`): `No`, `Yes`, or `Shown`, which also shows the place in it (`Setlist_Display`) |
| `REMEMBER` | remember state (`Remember_State`) |
| `CLOCKFLW` | clock follow (`Clock_Follow`) |
| `LEDFEEDB` | LED feedback (`LED_Feedback`) |
| `LINKTOGL` | linked toggles (`Link_Toggles`) |
| `USB THRU`, `RT THRU` | the two thru switches (`USB_MIDI_Thru`, `RealTime_Passthrough`) |
| `3 PORTS` | three USB MIDI ports (`USB_Ports`), from the next start |
| `TWO WAY` | which unit to talk to both ways: `Off`, `Kemper` (`Kemper_Mode`) or `GT-1000` (`GT1000_Mode`) |
| `EXP1 CC`, `EXP2 CC` | the expression pedal CC numbers (`Exp1_CC`, `Exp2_CC`), 1–127 |
| `EXP1SEND`, `EXP2SEND` | each pedal sends its position on entering a bank (`Send_On_Bank`) |
| `BARBEATS` | the beats in a bar for the bar and beat on the display, `off` or 1–15 (`Beat_Counter`) |

## When a change is written

What you change is written to flash as soon as the cursor leaves the command, the label or the setting, so walking away loses nothing. A star in the title line says there is something not written yet.

- A write takes about a tenth of a second, during which the pedal is busy: change what you need between songs, not in the middle of one.
- Afterwards the pedal reads the configuration again, so the new command is live at once.
- Reading the configuration back with `Flash_to_CSV.py`, or **Read from Device** in the configurator, gives you a CSV with the change in it.

*Firmware 0.53 or later.*

<details><summary>Under the hood</summary>

A change is written by rewriting the 2 kB flash page it lives in, after which everything derived from the configuration is built again. The new page goes to a spare page first, with a note of where it belongs, so a power cut halfway is finished from there at the next start (firmware 1.06 or later).

</details>

## Locking the editor

For a pedal that must not change under anybody's foot, tick **Lock on-pedal editing** in the configurator's **Global** tab, `Edit_Lock` in the CSV. The two bank switches held together then no longer open the editor at all. It can only be turned off again from the configurator, or for one session from [safe mode](#safe-mode).

## Safe mode

For the configuration that mutes the amp or upsets the rig at start-up, with no computer at hand. Hold **any one of the eight command switches** (1–4, A–D) while the pedal powers on, and let go once the display says **SAFE MODE**. The pedal then starts without sending anything, and stays that way until it is switched off:

- no bank enter or leave list runs, neither at start-up nor when the bank changes;
- the saved bank and toggle states are not brought back, even with `Remember_State` on: it starts on bank 0 with everything off;
- `Kemper_Mode` and `GT1000_Mode` stay off, so no beacon and no questions go to the amp or the GT-1000;
- the expression pedals keep their position to themselves until they are moved;
- the switch held at power on is not a press, and letting go of it does nothing.

Everything else works: the buttons send their commands, the bank switches change bank, a configuration can be flashed from the computer, and the [editor](#editing-on-the-pedal) opens even with `Edit_Lock` on, so a wrong Bank Enter command can be found and changed from the pedal itself.

- Switch the pedal off and on again with nothing held to leave safe mode.
- A bank changed in safe mode is remembered as usual, so with `Remember_State` on the pedal comes back there.
- Bank Down and D held together at power on is still the bootloader's DFU mode, as on the stock pedal: that is not safe mode.

*Firmware 0.60 or later.*

<details><summary>Under the hood</summary>

`GET_STATE` reports safe mode too, in the byte after the eight stored values (firmware 0.60).

</details>

---

[← The display](09-the-display.md) · [Contents](README.md) · [Templates and devices →](11-devices.md)
