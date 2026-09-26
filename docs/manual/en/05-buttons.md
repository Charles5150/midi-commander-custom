# Buttons

Every button has three command lists, a short, a long and a double press, a label on the display, a light and a few options that change how it behaves.

## Button_Settings

One row per button, 256 rows in bank order and, within a bank, in the order `1, 2, 3, 4, A, B, C, D` (top row of the pedal, then bottom row). Columns:

- `Bank_Number`, `Button_Identifier`
- `Label` — up to 4 characters shown on the display. Empty shows the button identifier.
- `Light_Mode` — Normal / Reverse / AlwaysOn.
- `Group` — empty, or an exclusive group 1–4 (see [Exclusive groups](#exclusive-groups)).
- `Momentary_Hold` — `Y` for a toggle button that is momentary when held (see [Latch or momentary](#latch-or-momentary)); empty or `N` otherwise.
- `Tempo_Flash` — `Y` for a button whose LED flashes with the beat (see [Tap LED](07-tempo.md#tap-led)); empty or `N` otherwise.
- `Global` — `Y` for a button that takes everything from the same button of `Global_Bank` (see [Global buttons](#global-buttons)); empty or `N` otherwise.
- Ten command slots, prefixed `A_` to `J_`, each with the fields below.

## LED modes

- **Normal**: lit while the button is active, off otherwise.
- **Reverse**: lit at rest, off while active.
- **AlwaysOn**: lit at rest, blinking while active.

"Active" means physically pressed for a momentary button, or toggled on when any of the button's commands is a toggle. A lit LED uses `LED_Brightness`; "lit at rest" uses `LED_Rest_Brightness`. LEDs are dimmed by software PWM at 500 Hz, so there is no visible flicker.

**When the "off" is sent**

- `Toggle = N`, `Duration = 0`: on when pressed, off when released (momentary).
- `Toggle = N`, `Duration > 0`: on when pressed, off automatically after the duration, even if still held. Notes, pitch bend and keys only; CC ignores the duration.
- `Toggle = Y`: the first press sends on, the next sends off, and so on. Toggle state is kept per button and per bank, and drives the LED.

## Double press

`DoublePress_Settings` gives each button a third command list, in the same format as `LongPress_Settings` and with its own toggle state; in the configurator it is the **Double press** mode of the button editor, and Copy / Paste bank carries it. Two presses within `Double_Press_ms` send it. Only buttons that have double press commands in the current bank change behaviour: a single tap on them waits for that window before sending its short press, and holding them still gives the long press, or the short press when there is none. Buttons without double press commands respond exactly as before. Needs firmware 0.26; `CSV_to_Flash.py` leaves the double press commands out, with a warning, when the pedal runs anything older.

## LongPress_Settings

Optional. `Bank_Number`, `Button_Identifier` and the ten command slots: the columns of `Button_Settings` without the label and the light, group and hold ones, which belong to the button. Rows may be missing or in any order; a button without a row has no long press commands and reacts instantly on press. Long press commands have their own toggle state.

Rows are optional in `Button_Settings` and `Bank_Naming` too: a configuration that only defines the first few banks, including one written for the 8 bank firmware, flashes unchanged and leaves the rest empty. The configurator always shows all 32 banks and writes them all when you save.

## DoublePress_Settings

Optional, and laid out exactly like `LongPress_Settings`: the third command list of each button, fired by two quick presses (see [Double press](#double-press)). Its own toggle state.

## Latch or momentary

A button with `Momentary_Hold` set to `Y` and a toggle command in its short press list latches on a tap and is momentary when held. It toggles as soon as it is pressed, as always; held past `Long_Press_ms` (500 ms unless set), it presses itself once more when released, so it goes back to where it was: on only while held if it was off, off only while held if it was on. A tap shorter than that latches as usual. The hold belongs to the long press list when the button has one, so the option does nothing on such a button, nor on a cycle button. In an exclusive group, holding a button switches the others off and they stay off. The option is bit 7 of the button's LED mode byte, which configurations have always left at zero, so the layout is unchanged. Needs firmware 0.39; older firmware ignores it and the button simply toggles. In the configurator it is the "Momentary when held" box beside the exclusive group. The demo's bank 11 button 4, BOST, uses it.

## Exclusive groups

A button's `Group`, 1 to 4, ties it to the other buttons of its bank in the same group: switching one on switches off every other one of the group that is on, as if pressed by foot, so their off commands go out and their LEDs and display cells follow. They are switched off before the pressed button sends anything, so when the whole group drives one parameter, an amp channel CC for instance, the device ends up where the pressed button says. Pressing the lit button switches it off like any toggle, leaving the group all off. Only buttons with a toggle command take part, and only their short press; groups are per bank, so group 1 in one bank has nothing to do with group 1 in another. A scene can switch on two buttons of a group, and the last one wins. The group lives in the top bits of the button's LED mode byte, which configurations have always left at zero, so the layout is unchanged. Needs firmware 0.32; firmware before it reads a button with a group as `Normal` LED mode. The demo groups the four track buttons of the looper bank.

## Scenes

`CommandType` `Scene` sets the toggle buttons of the current bank to a chosen state. `OnValue` holds eight characters, one per button in the order `1234ABCD`: `+` to switch it on, `-` to switch it off, and `.` or anything else to leave it alone, so `+-+..-..` turns 1 and 3 on and 2 and B off. Each affected button that is not already in the wanted state is pressed as if by foot, so its own commands, LED and display cell follow; buttons already there are not touched, so recalling the same scene twice sends nothing the second time. Buttons without a toggle command have no state and are skipped. A scene cannot trigger another scene. The configurator shows it as eight drop-downs, and the demo puts three on the long presses of the LED modes bank.

## Cycle buttons

`CommandType` `Cycle` splits a button's short press commands into states. The commands above the first `Cycle` are state 1, those between it and the next `Cycle` state 2, and so on. The `Cycle` commands take command slots too, so the ten slots hold five states of one command each. Each press sends the next state's commands, back to state 1 after the last one, and the display cell shows the label of the state just sent: the `Cycle` command's `OnValue`, up to 4 characters, or the button's own `Label` for state 1 and for a `Cycle` left without one. A button starts before its first state, so its first press sends state 1. For an amp with four channels on Program Changes 0 to 3, the button's commands are `PC 0`, `Cycle "CH B"`, `PC 1`, `Cycle "CH C"`, `PC 2`, `Cycle "CH D"`, `PC 3`, with `CH A` as its label. A state may hold several commands, pauses, ramps and repeating commands, which then repeat only while that state's press is held. Every cycle button of every bank keeps its place while the pedal is on, whatever banks you visit in between; a change of configuration, or switching the pedal off, starts them all from the beginning again. `Cycle` belongs in the short press list only: the tools refuse it in a long or double press, a bank's commands on entry or the Bank switches' lists. The labels are kept in a table of 48 at the end of the configuration, each different label stored once however many buttons use it, and the tools refuse a configuration with more. Like `Wait`, a `Cycle` is marked by the low nibble of the empty command type, 3, with byte 1 holding the label's place in the table, or 0x7F for none. Needs firmware 0.38; older firmware ignores the `Cycle` commands and sends every state at once.

## Global buttons

A tuner, a panic, a tap tempo — the things that should be under the same foot all night — used to mean the same commands copied into all 32 banks, and a change meant changing it 32 times. Instead, set one bank aside for them in `Global_Settings` with `Global_Bank`, write those buttons there once, and in every other bank tick `Global` on the buttons that should follow it. A global button takes everything from the same button of that bank: its short, long and double press lists, its label on the display, its light mode, its exclusive group and whether it is on, so the tuner is lit in every bank at once and switching it off in one switches it off in all of them. What is written on the button in its own bank is left alone and never sent, which is worth remembering: a button cannot be global and be something of its own as well.

The bank set aside is an ordinary bank otherwise — you can stand on it, its own buttons work as they always did, and it is where the global buttons are edited, on the pedal or in the configurator. Its own buttons never follow anything, so nothing can go round in circles. `Global_Bank` set to `Off`, which is what every configuration written before this holds, redirects nothing and every button is its own again. Like the macros it gives configuration room back rather than taking it: the flag is a bit of the button's LED mode byte, bit 3, which configurations have always left at zero, so the layout is unchanged; what it saves is the copies. Needs firmware 0.57; older firmware ignores the bit and sends whatever is written on the button itself. In the configurator it is the "Global" box beside the exclusive group, and on the pedal the setting is `GLOBBANK`, the bank number as the editor shows it or 0 for none. In the demo, bank 30 is set aside and holds the tap, and every song bank but the first takes its D from there — the first keeps its own, which is the way to its second page.

## Combo_Settings

Optional; one row per combination, up to twelve, in any order. Pressing the two switches together runs a list of their own instead of what either does alone.

| Column | Values | Meaning |
|---|---|---|
| `Switches` | two of 1–4, A–D, such as `3+4` | The pair. The order does not matter. |
| `Bank` | All / 0–31 | The bank it counts in, or `All` for every bank. A combination of the bank showing wins over an `All` one for the same pair, which is how one bank gives a pair another job. |
| `Run_Bank`, `Run_Button`, `Run_List` | 0–31, 1–4 or A–D, Short / Long / Double | The list it runs, any button's, as a [`Macro`](#button_settings) names it. |

A combination costs four bytes rather than ten commands: there was no room left for a list of its own, so its commands live on a button of a bank you keep spare, the global bank for instance, and can be tried from there. The list runs with a toggle state of the combination's own, on the press, and its release pass, the momentary offs, goes out when the first of the two switches lets go. `Wait`, `If`, `Macro` and the rest work in it as anywhere else.

A switch that belongs to a combination in the current bank does not fire at once: it waits `Combo_ms`, 80 ms unless changed, for the other one. If that comes in time the pair runs the combination and neither switch sends its own. If it does not, the press carries on as it would have, into a short, long or double press, the wait counted in, and a tap let go inside the window is still a tap. Switches in no combination, and every switch in a bank without any, answer at once as before. Two presses of the same switch are still a double press, not a combination, and the two bank switches keep their own gesture, the on-pedal editor. Needs firmware 0.59, which reads the table from the last 48 bytes of the slot; older firmware ignores it and the two switches do what they do alone. Edit it in the configurator's **Combos** tab.

---

[← Banks](04-banks.md) · [Contents](README.md) · [Commands →](06-commands.md)
