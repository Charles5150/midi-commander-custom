# The configuration file

**English** · [Español](../es/12-configuration-file.md)

A configuration is a CSV with several sections, each introduced by a line starting with `*` and the section name. Lines containing `#` are comments. The configurator reads and writes this format, and you can also edit it in a spreadsheet.

| Section | What it holds | Described in |
|---|---|---|
| `Global_Settings` | The settings of the whole pedal | [below](#global_settings) |
| `Bank_Naming` | Each bank's name and info line | [Banks](04-banks.md#bank_naming) |
| `Button_Settings` | Each button's label, light, options and short press commands | [Buttons](05-buttons.md#button_settings), [Commands](06-commands.md) |
| `LongPress_Settings`, `DoublePress_Settings` | The long and double press commands | [Buttons](05-buttons.md#longpress_settings) |
| `Combo_Settings` | Two switches pressed together | [Buttons](05-buttons.md#combo_settings) |
| `SysEx_Strings` | Sixteen stored SysEx messages | [Commands](06-commands.md#sysex_strings) |
| `BankEnter_Settings` | What each bank sends on entry and leaving | [Banks](04-banks.md#bankenter_settings) |
| `BankSwitch_Settings` | What Bank Up and Bank Down send | [Banks](04-banks.md#bankswitch_settings) |
| `Setlist` | The order Bank Up / Down follow | [Banks](04-banks.md#setlist) |
| `Expression_Settings`, `BankExpression_Settings` | The two expression pedals, and per bank | [Expression pedals](08-expression.md) |

## The demo configuration

**`python/demo-all-features.csv`** is the reference: a configuration that uses every feature, with one bank per feature and button labels that say what each one does. Load it in the configurator to see how anything is set up, or flash it to try the whole firmware on the pedal.

| Bank | What it shows |
|---|---|
| 0 | An index of `Bank` commands jumping to the other banks |
| 1 | A looper layout: CC toggles, the four track buttons as an exclusive group, and a long press on one button |
| 2 | The three LED modes side by side, and momentary versus toggle |
| 3 | Program Changes, with and without Bank Select, and a patch selected on entry |
| 4 | Keyboard keys: plain, with modifiers, held, and a Down/Up combination |
| 5 | Media keys; held, the same buttons drive a recorder instead, as MMC, Song Select and Song Position |
| 6 | Tap tempo, clock start/stop, transport, BPM up/down (hold SYNC for 120 BPM), TREM, a tremolo on CC 14 that follows the tempo, and a four note arpeggio held on STRT |
| 7 | Relative CC, up and down, with and without wrapping, VOL+ and VOL- repeating while held, and two CC ramps: a toggle swell and a momentary rise |
| 8 | Stored SysEx messages, including an empty entry that sends nothing, a WAH on D that pedal 1 switches on and off by itself, VOL on C, which turns pedal 1 into a volume pedal (CC 7) while it is on, and P2 X on B, which silences pedal 2 while it is on |
| 9 | Notes and pitch bend, with durations and toggles |
| 10 | Bank navigation from buttons, absolute and relative; B, PREV, goes back to the bank you came from |
| 11 | Several commands chained on one button, short versus long press, and a cycle button stepping through four amp channels (D), and a boost that latches on a tap and is momentary when held (4). Entering the bank sends CC 59 127 and leaving it CC 59 0; holding A mutes channels 1, 2 and 3 with one CC |
| 12–29 | A setlist: each bank selects its patch on entry and has looper controls. On song 1 (bank 12), D is PG 2, which shows bank 31 as its second page; on the other songs D is a global button, the tap from bank 30 |
| 30 | The bank set aside for the global buttons (`Global_Bank`): the tap on D, a mute toggle on C and HOME on A. Also the lists the two combinations run: a tuner toggle on B (CC 68) and the looper's clear on 4 (CC 5) |
| 31 | Song 1's second page: seven toggles, FX1 to FX7 on CC 60–66, and BACK on D. Entering the page sends CC 70 127 and going back CC 70 0 |

Both expression pedals are configured, one linear and one logarithmic and inverted, with the toe and heel acting as switches. Pedal 1 auto-engages button D, the WAH in bank 8 (and TRK4 in bank 1), switching it off after 600 ms at the heel. Pedal 2 sends a 14-bit CC pair, CC 4 and 36. CC 102–111 on channel 16 press the ten switches from the computer. Switches 3 and 4 pressed together toggle the tuner in every bank, except on song 1, where the same pair clears the looper. Bank 2 turns pedal 1 into a modulation wheel held between 20 and 100, and bank 7 silences it and makes pedal 2 a volume on channel 2 that never drops below 40, CC 7 and 39. Regenerate the file with `python3 python/make_demo_config.py` after adding a feature, so it keeps covering everything.

(`python/MeloConfig_10_Cmds - RC-600.csv` is a real-world configuration for a Boss RC-600. The original project's Google Sheets template is no longer online, and it predated several columns anyway; start from one of the CSVs instead.)

## Global_Settings

The settings of the whole pedal, as `Label,Value` rows. In the configurator they are the **Global** tab, in the same groups as below: each setting is shown there by the name in the second column, with its CSV label in small print underneath.

### Configuration

| Label | In the configurator | Values | What it does |
|---|---|---|---|
| `ConfigName` | Configuration name | up to 16 chars | Shown on the display at boot. |
| `Boot_Banner` | Banner at power on | Off / Slow / Normal / Fast | At power on, the `ConfigName`, or the pedal's [own text](09-the-display.md#the-banners-own-text) when it has one, and the firmware version cross the display once in large letters, right to left, in place of the name under the boot animation: about 37, 74 or 110 pixels a second, some four seconds for a full name at Normal. The pedal works all along: any switch, or a press from the computer, ends it at once and does what it always does, and the bank screen comes back underneath with whatever changed meanwhile. Safe mode shows over it. Default Off. Needs firmware 0.62 (global byte 46); older firmware shows the name as before. |
| `MIDI_Channel` | MIDI channel | 1–16 | Channel used by the expression pedals (unless a pedal sets its own). Buttons use the channel of each command. |
| `Global_Channel` | Global channel | Off / 1–16 | Move the whole configuration to one channel: every message goes out on it instead of the channel stored in each command, pedals included. Off leaves each command on its own. A `Chan` command names its channels on purpose, so it is left alone. Default Off. |
| `Exp1_CC`, `Exp2_CC` | Expression pedal 1 CC, Expression pedal 2 CC | 0–127 | CC number sent by each expression pedal. Defaults 11 and 4. |

### Presses

| Label | In the configurator | Values | What it does |
|---|---|---|---|
| `Long_Press_ms` | Long press after | 100–2500 | Hold time that turns a press into a long press, on the command buttons and on Bank Up / Down. Default 500. |
| `Double_Press_ms` | Double press within | 100–1000 | Time the second press of a double press may take. A button with double press commands in the current bank waits this long after a tap before sending its short press. Default 300. |
| `Combo_ms` | Two switches together within | 20–250 | How long a switch of a [combination](05-buttons.md#combo_settings) waits for the other one. Only switches that belong to a combination in the current bank wait, and only this long, before doing what they do alone. Default 80, which one foot on two switches comfortably makes. |
| `Remember_State` | Remember state | Y / N | Power up in the last bank with all toggles as they were. |
| `Edit_Lock` | Lock on-pedal editing | Y / N | Stop the two bank switches held together opening the [on-pedal editor](10-editing-on-the-pedal.md), for a pedal that must not change under anybody's foot. It can only be unlocked from here, or for one session by starting in [safe mode](10-editing-on-the-pedal.md#safe-mode). Default N. |

### LEDs

| Label | In the configurator | Values | What it does |
|---|---|---|---|
| `LED_Brightness` | Brightness | 1–100 | Brightness of a lit LED, in percent. Default 100. Configurations written before 0.9 read as 100. |
| `LED_Rest_Brightness` | Brightness at rest | 1–100 | Brightness of LEDs lit at rest by the Reverse and AlwaysOn modes. Default 100; set it lower to tell an active button from an idle one. |
| `Bank_Up_LED_Mode`, `Bank_Down_LED_Mode` | Bank Up LED, Bank Down LED | Normal / Reverse / AlwaysOn | LED behaviour of the bank buttons (see [LED modes](05-buttons.md#led-modes)). |
| `LED_Feedback` | Follow the computer | Y / N | A Control Change, Note On or Note Off arriving over USB puts every toggle button whose `CC` or `Note` command has the same channel and number into the state it describes: its LED, its display cell and what its next press sends follow. Every bank is updated, and the long press list too. A CC counts as on when its value is nearer the command's `OnValue` than its `OffValue`; a command without an `OffValue` only reacts to its `OnValue`. A Note On with a velocity is on, a Note Off or velocity 0 is off. Only the state changes: nothing is sent, so a host that echoes the pedal's messages back causes no loop. While asleep the state is kept and the LEDs come back right on waking. A list with a [`Listen`](06-commands.md#listening-on-another-cc) command follows that instead, on or off. Default N. |

### Banks

| Label | In the configurator | Values | What it does |
|---|---|---|---|
| `Bank_Switch_Mode` | Bank switches | Bank / Bank+MIDI / MIDI only | What the Bank Up / Down switches do. `Bank` is the original behaviour, they only change bank. `Bank+MIDI` also sends their commands from `BankSwitch_Settings`. `MIDI only` stops them changing bank, leaving a ten switch controller. Default `Bank`. |
| `Bank_Jump_Step` | Long press jumps | 1–31 | Banks skipped by a long press on Bank Up / Down. Default 8. |
| `Bank_Preview` | Preview banks | 0–60 | Bank Up / Down only preview the bank. A press, or a long press, moves a candidate as it would move the bank, setlist included, and the display shows that bank's name inverted, white with black letters, over its button labels; nothing is sent, neither the bank's commands nor the bank switch's own. The first of the eight buttons to go down confirms it: the pedal goes there, the bank left sending its leave list and the bank entered its enter list, and that press does nothing else, nor does its release. The bank switches' own commands from `BankSwitch_Settings` are not sent with a preview on. Stepping back to the bank you are in drops the preview, and so does leaving it this many seconds without a button, the bank you are in coming back on the display. A bank change from MIDI, or the editor opening, drops it too. Tempo readouts and texts from the computer wait until it is over. With `Bank_Switch_Mode` at MIDI only the bank switches do not change bank, so there is nothing to preview. 0 is off, the default. Needs firmware 0.66 (global byte 47). |
| `Setlist_Mode` | Follow the setlist | Y / N | Bank Up / Down, and relative `Bank` commands, follow the order in the `Setlist` section instead of the bank numbers. From a bank that is not in the list, Up enters at its first entry and Down at its last. `GoTo` and bank selection from incoming MIDI still go to the exact bank. Default N. |
| `Bank_Change_Mode` | Change bank from MIDI | Off / PC / CC | Let an incoming Program Change, or Control Change, select a bank. |
| `Bank_Change_Channel` | … listening on channel | Any / 1–16 | Channel the pedal listens on for those messages. |
| `Bank_Change_CC` | … with CC number | 0–127 | CC number that selects a bank, when the mode is CC. Its value is the bank. |
| `Global_Bank` | Global buttons bank | Off / 0–31 | The bank set aside for the global buttons: a button marked `Global` in any other bank takes its command lists, its label, its light and its state from the same button of this one. See [Global buttons](05-buttons.md#global-buttons). Default Off, nothing redirected. |

### USB MIDI

| Label | In the configurator | Values | What it does |
|---|---|---|---|
| `USB_MIDI_Thru` | USB to DIN thru | Y / N | Forward every other MIDI message received over USB (notes, CC, PC, pitch bend, system common, other devices' SysEx) to the DIN output. |
| `RealTime_Passthrough` | Clock and transport thru | Y / N | Forward MIDI Clock, Start, Continue and Stop received over USB to the DIN output. |
| `Clock_Follow` | Follow the host's clock | Y / N | Measure MIDI clock arriving over USB, over two beats, and adopt its tempo; the display shows it as `EXT` and a tempo for 1.5 seconds when the clock is picked up or its tempo changes by two BPM or more. While that clock keeps arriving the pedal sends no clock of its own: with `RealTime_Passthrough` on the host's clock already reaches the DIN output, and with it off the pedal re-clocks the DIN output at the host's tempo. Half a second without a clock counts as stopped, and the pedal's own clock, if running, continues at the adopted tempo. Default N. |
| `Remote_Mode` | Press from the computer | Off / CC / Note | Let the computer press the switches. Ten numbers in a row from `Remote_First` stand for 1, 2, 3, 4, A, B, C, D, Bank Down and Bank Up. A CC of 64 or more, or a Note On, holds the switch down; a CC below 64, a Note Off or a Note On with velocity 0 lets it go. The press goes through the same path as a foot, so a hold becomes a long press, two quick taps a double press, and Bank Up / Down follow `Bank_Switch_Mode` and the setlist. A host that only sends the press, never the release, leaves the switch down until it lets go by itself after 10 seconds, so send both. Messages used this way go no further: not to the DIN output, nor to `LED_Feedback` or bank selection. Default Off. |
| `Remote_Channel` | … listening on channel | Any / 1–16 | Channel the pedal listens on for those messages. Keep it apart from the channels the buttons send on if `LED_Feedback` is on. |
| `Remote_First` | … from number | 0–118 | CC or note number for switch 1; the other nine follow. Default 102, so CC 102–111, numbers no device uses by convention. |
| `Kemper_Mode` | Talk to a Kemper | Y / N | Talk to a Kemper Profiler both ways: the pedal asks the amp to report itself and follows what comes back, the rig you are on written beside the bank name and the effect modules lighting the buttons that switch them. See [Two way with a Kemper](11-devices.md#two-way-with-a-kemper). Default N, on in the Kemper Player template. |

### Power

| Label | In the configurator | Values | What it does |
|---|---|---|---|
| `Sleep_After_Min` | Sleep after | 0–60 | Minutes of inactivity before the display and LEDs go out. 0 turns it off. A press or a moved expression pedal wakes it and still does what it was asked to. |

---

[← Templates and devices](11-devices.md) · [Contents](README.md) · [Command line tools →](13-command-line-tools.md)
