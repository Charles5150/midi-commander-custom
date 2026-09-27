# Templates and devices

**English** · [Español](../es/11-devices.md)

The pedal talks to a computer over USB and to the rest of your gear through its MIDI OUT socket. Everything a button sends goes out of both; what arrives over USB can change bank, light LEDs, press switches, set the tempo or go on to the DIN output.

![Where MIDI goes in and out](../images/midi-routes-en.svg)

Four ready-made configurations under `python/templates/` put a device's main controls under your feet with nothing, or next to nothing, to set up on the device. To use one, open it with **Load CSV** in the configurator and press **Flash to Device**, or from a terminal:

```bash
.venv/bin/python python/CSV_to_Flash.py python/templates/FM3.csv
```

Each is built by a script from the device's own MIDI map, so a different channel or CC is a constant to change and the script to run again, as each section says. Or change the buttons in the configurator like any other configuration.

## Fractal Audio FM3 template

**`python/templates/FM3.csv`** is ready to flash for a Fractal Audio FM3 driven over the DIN output, and should suit an Axe-Fx III or FM9 too, which are set up the same way. Connect the pedal's MIDI OUT to the FM3's MIDI IN and power the pedal over USB.

| Banks | Buttons |
|---|---|
| 0–29, `P000`–`P029` | Entering the bank loads the FM3 preset with the same number. 1 2 3 4 A B are scenes 1–6, C latches the tuner, D taps the tempo |
| 30, `LOOP` | Looper: Record, Play/Stop, Undo, Once, Reverse, Half Speed, then tuner and tap |
| 31, `FX` | Engages and bypasses Drive 1, Compressor 1, Phaser 1, Chorus 1, Delay 1, Reverb 1, Wah 1 and Pitch 1 |

Bank Up / Down step through the presets, and a long press jumps ten. The scene buttons are an exclusive group, so the LED and the display show the scene last picked; pressing the lit one again darkens it without sending anything. The expression pedals are External 1 and 2, to attach to any parameter as a modifier.

The FM3 comes with no MIDI CC assigned, so on the FM3, under **SETUP > MIDI/Remote**, set its MIDI channel to 1 and assign:

| Page | Function | CC |
|---|---|---|
| Other | Tempo Tap | 14 |
| Other | Tuner | 15 |
| Other | Scene Select | 34 |
| External | External 1, External 2 | 16, 17 |
| Looper | Record, Play, Undo, Once, Reverse, Half Speed | 20–25 |
| Bypass | Drive 1, Compressor 1, Phaser 1, Chorus 1, Delay 1, Reverb 1, Wah 1, Pitch 1 | 40–47 |

To use other numbers, or another channel, change the constants at the top of `python/make_fm3_template.py` and run it again, or edit the buttons in the configurator. Presets above 29, or in the FM3's banks B to D, take a Program Change with `BankSelect_(PC)` set to 128 times the FM3 bank and `BankSelectHighByte_(PC)` to `Y`, so that CC#0 carries the bank.

## Line 6 HX Stomp template

**`python/templates/HX_Stomp.csv`** is ready to flash for a Line 6 HX Stomp driven over the DIN output. Connect the pedal's MIDI OUT to the HX Stomp's MIDI IN and power the pedal over USB.

| Banks | Buttons |
|---|---|
| 0–29, `01A`–`10C` | Entering the bank loads the HX Stomp preset with the same name, 01A to 10C. 1 2 3 are snapshots 1–3, 4 opens and closes the tuner, A B C press FS1–FS3 and D taps the tempo |
| 30, `LOOP` | Looper: Record, Overdub, Play/Stop, Half Speed, Play Once, Undo, Reverse, then tap |
| 31, `FS` | FS1–FS5, previous and next snapshot, and the tuner |

Bank Up / Down step through the presets, and a long press jumps ten. The snapshot buttons are an exclusive group, so the LED and the display show the snapshot last picked; pressing the lit one again darkens it without sending anything. FS1–FS5 act as if you stepped on the HX Stomp's footswitch in Stomp mode, so they switch whatever is assigned to it, and the expression pedals move the HX Stomp's EXP 1 and EXP 2 controllers.

The HX Stomp has a fixed MIDI map, so it needs no assignments: under **Global Settings > MIDI/Tempo**, set the MIDI Base Channel to 1 and turn MIDI PC Receive on. The template sends:

| Function | CC | Values |
|---|---|---|
| EXP 1, EXP 2 | 1, 2 | the pedals |
| FS1–FS5 | 49–53 | 127 and 0, each one a press |
| Looper Record / Overdub | 60 | 127 records, 0 overdubs |
| Looper Play / Stop, Play Once, Undo | 61, 62, 63 | |
| Tap Tempo | 64 | 127, on the press only |
| Looper Reverse, Half Speed | 65, 66 | |
| Tuner | 68 | |
| Snapshot | 69 | 0–2 snapshots 1–3, 8 next, 9 previous |

To use another channel, change `CHANNEL` at the top of `python/make_hx_stomp_template.py` and run it again, or edit the buttons in the configurator. Presets above 10C take a Program Change with the preset number, 0 to 125.

## Neural DSP Quad Cortex template

**`python/templates/Quad_Cortex.csv`** is ready to flash for a Neural DSP Quad Cortex driven over the DIN output. Connect the pedal's MIDI OUT to the Quad Cortex's MIDI IN and power the pedal over USB.

| Banks | Buttons |
|---|---|
| 0–29, `P000`–`P029` | Entering the bank loads the preset with the same number from the My Presets setlist. 1 2 3 4 A B are scenes A–F, C opens and closes the tuner, D taps the tempo |
| 30, `LOOP` | Looper X: Record / Overdub, Play / Stop, Undo / Redo, the Looper X view, One Shot, Half Speed, Reverse, then tap |
| 31, `FS` | Footswitches A–H, as laid out on the Quad Cortex: A–D on the bottom row, E–H on the top one |

Bank Up / Down step through the presets, and a long press jumps ten. The scene buttons are an exclusive group, so the LED and the display show the scene last picked; pressing the lit one again darkens it without sending anything. The footswitch buttons act as if you stepped on the Quad Cortex's own, so they switch whatever is assigned to it in the mode it is in, and the expression pedals move its Expression Pedal 1 and 2. Button 4 of the looper bank opens the Looper X view on one press and closes it on the next; One Shot, Half Speed and Reverse light while they are on, counted from when the looper was opened.

The Quad Cortex has a fixed MIDI map, so it needs no assignments: under **Settings > Device > MIDI**, set its MIDI Channel to 1, or OMNI. The template sends, from the Quad Cortex manual (CorOS 4.1.1):

| Function | CC | Values |
|---|---|---|
| Bank Select before each preset | 0, 32 | 0 and 1: presets 0–127 of My Presets |
| Expression Pedal 1, 2 | 1, 2 | the pedals |
| Footswitches A–H | 35–42 | 127 and 0, each one a press |
| Scene | 43 | 0–5, scenes A–F |
| Tap Tempo | 44 | 127, on the press only |
| Tuner | 45 | 127 opens, 0 closes |
| Looper X view | 48 | 0 opens, 127 closes |
| Looper X One Shot, Half Speed, Reverse | 50, 51, 55 | 127, each one a switch |
| Looper X Record / Overdub, Play / Stop, Undo / Redo | 53, 54, 56 | 127, on the press only |

To use another channel, or another setlist, change `CHANNEL` or `SETLIST` at the top of `python/make_quad_cortex_template.py` and run it again: `SETLIST` is the Bank Select LSB, 0 for Factory Presets, 1 for My Presets and 2 to 12 for the user setlists. Scenes G and H are CC 43 with 6 and 7, for any button in the configurator.

## Kemper Profiler Player template

**`python/templates/Kemper_Player.csv`** is ready to flash for a Kemper Profiler Player. The Player has no DIN sockets: plug the pedal's USB into the Player's USB A socket, where the Player acts as host and powers it. That is the link whose Active Sensing, a byte every 300 ms, stalls the stock firmware; this one reads and drains everything that arrives, so the link never backs up.

| Banks | Buttons |
|---|---|
| 0–9, `BK01`–`BK10` | The Player's ten banks of five rigs. Entering the bank preselects it, 1 2 3 4 A load rigs 1–5 of it, B and C press the Player's effect buttons I and II, and D taps the tempo |
| 10, `FX` | Modules A, B, DLY and REV, then the four effect buttons I to IIII |
| 11, `TOOL` | Tuner, rotary speed, delay infinity, freeze, all effects at once, delay and reverb again but keeping their tails, and tap |

Only those twelve banks are in use, so the template turns `Setlist_Mode` on and Bank Up / Down walk them and skip the empty ones; a long press jumps five. The rig buttons are an exclusive group, so the LED and the display show the rig last picked and pressing the lit one again sends nothing. Entering a bank only preselects it on the Player: the rig changes when you press one of the five, which is what keeps the sound from jumping about while you walk the banks with your foot.

The Player has a fixed MIDI map, so it needs no assignments: it listens on all sixteen channels unless **System Settings > MIDI In Channel** says otherwise. The template sends:

| Function | CC | Values |
|---|---|---|
| Wah pedal, Volume pedal | 1, 7 | the two expression pedals |
| All modules at once | 16 | 127 inverts every module |
| Module A, module B | 17, 18 | 127 and 0 |
| Delay, reverb | 26, 28 | 127 and 0, tails cut |
| Delay, reverb keeping the tails | 27, 29 | 127 and 0 |
| Tap Tempo | 30 | 127, on the press only |
| Tuner | 31 | 127 opens it, 0 closes it |
| Rotary speed, delay infinity, freeze | 33, 34, 35 | 127, and each press flips it |
| Bank preselect | 47 | 0–9, sent when you enter one of the ten rig banks |
| Rigs 1–5 of the bank | 50–54 | 1, which is what loads the rig |
| Effect buttons I–IIII | 75–78 | 127 and 0 |

To use another channel, change `CHANNEL` at the top of `python/make_kemper_player_template.py` and run it again, or edit the buttons in the configurator. The fifty rigs also answer to a plain Program Change: the Player's manual numbers them 1 to 50, which is `Number` 0 to 49 here.

## Two way with a Kemper

Everything above sends one way: the pedal tells the amp what to do and hopes it listened. A Kemper Profiler can also be asked about itself, and then the pedal shows what the amp is really doing, however it got there.

**To turn it on**, tick **Talk to a Kemper** in the configurator's **Global** tab (`Kemper_Mode` `Y` in the CSV), or start from the [Kemper Player template](#kemper-profiler-player-template), which has it on. The on-pedal editor offers it as `KEMPER`.

Two things come back and are worth seeing from the floor:

- **The rig you are on**, in the small line beside the bank name, and there it stays, bank after bank, until the rig changes. Eleven characters fit; a longer name, up to 32, [scrolls across once](09-the-display.md#text-from-the-computer) when the rig changes and whenever a bank is entered. The pedal asks for it every second, so it is right even when the rig was changed on the amp itself.
- **Which effect modules are running.** A module switching on or off is turned into the Control Change that switches that module — 17 and 18 for stomps A and B, 19, 20, 22 and 24 for C, D, X and MOD, 26 and 28 for delay and reverb, and 27 and 29 which keep their tails — and handed to the same machinery as [`LED_Feedback`](12-configuration-file.md#global_settings). Any toggle button that sends one of those ends up lit or dark like the amp, in every bank, whether the module was switched with your foot, on the amp's own buttons or from a third place. Nothing is sent back because of it, so the two cannot chase each other, and the channel does not have to match: the amp's answers carry none.

**Which Kempers.** The answers come in over USB. On a **Profiler Player** that is the very socket the pedal is already plugged into: the Player is the host, powers the pedal and speaks MIDI over it, so nothing else is needed. A Profiler head or Stage would have to reach the pedal's own MIDI input, which the hardware does not have, so there the pedal keeps talking one way as before.

<details><summary>Under the hood</summary>

The pedal sends the amp the message that asks it to report what it is doing from now on, and repeats it every five seconds, which is what tells the amp somebody is still on the other end. Six of the eight modules the amp reports by itself; the delay and the reverb it does not, so the pedal asks for those two every second, and for the rig name every second too. It asks for all eight when it starts and again whenever the rig changes. Safe mode keeps `Kemper_Mode` off, so no beacon and no questions go out.

</details>

*Firmware 0.55 or later.*

### Tried without an amp

The conversation was tested against `python/Kemper_Sim.py`, a Kemper of make believe that answers over the same USB link a Player would use: it replies to what the pedal asks and lets you change the rig or switch a module to watch the pedal follow.

```bash
.venv/bin/python python/Kemper_Sim.py
kemper> rig Brit Crunch DLX
kemper> dly
```

It has not been tried against a real Kemper yet. The numbers it speaks — the maker's `00 20 33`, the functions, the module pages and the beacon — are the ones the Profiler's MIDI documentation and the open controllers that talk to one use, and a test checks the firmware's list against the tools', so if an amp ever disagrees the fix will be in that table of numbers and nowhere else.


## Three USB ports

With `USB_Ports` at 3 the pedal shows up on the computer as three USB MIDI ports instead of one:

| Port | Name on macOS | What it is |
|---|---|---|
| 1 | `MIDI Commander Custom Pedal` | The pedal, as with one port. |
| 2 | `MIDI Commander Custom DIN` | Straight to the MIDI OUT socket. |
| 3 | `MIDI Commander Custom Config` | The pedal again, for a second program. |

**Port 2** makes the pedal a USB MIDI interface for the gear on its DIN output. Whatever a program sends there goes out of the MIDI OUT socket as it came, clock and SysEx included, and the pedal itself never sees it: it does not change bank, press switches or follow that clock, and `USB_MIDI_Thru`, `RealTime_Passthrough` and the MIDI map do not apply. So a DAW can play the synth behind the pedal on port 2 and talk to the pedal on port 1, each on its own. Nothing comes back on port 2, as the pedal has no MIDI IN socket.

**Port 3** is the same pedal as port 1: what the pedal sends goes out on both, and it listens to both alike. A configurator gets its answers on the port it asked on. It is there for a second program: on Windows only one program at a time can open a port, so while a DAW holds port 1 the configurator, the [browser page](14-in-the-browser.md) or the [command line tools](13-command-line-tools.md) use port 3. The tools choose it by themselves when it is there, and never port 2. Leave port 3 off in the DAW, or it hears everything twice.

The ports change the next time the pedal starts; flashing a configuration restarts it. A DAW set up with one port needs its port choosing again, as the names change, which is why one port stays the default. With three ports the pedal also gives a USB serial number of its own, so macOS and Windows set it up as a new device instead of keeping the one port they remember; the one port entry stays in Audio MIDI Setup, offline, for when you go back. Switching configuration on the pedal (`NextConfig`) keeps the ports it started with.

Windows numbers the ports instead of naming them, `MIDIOUT2 (MIDI Commander Custom)` and so on, and older Linux kernels call them `MIDI 1` to `MIDI 3`; the tools know those names too, but three ports have only been tried on macOS so far.

Needs firmware 1.04 (bit 1 of global byte 6, beside `USB_MIDI_Thru` in bit 0).


## Translating what comes in

A DAW, a sequencer or a keyboard on USB rarely speaks the language of the old pedal on the DIN cable: the DAW changes scene with a Program Change, the delay wants two CCs; the keyboard's mod wheel is CC 1, the amp's volume CC 11 and the other way round. The **MIDI map** puts the pedal in the middle and translates.

Each entry says **when**, a message arriving over USB, and what it **becomes**:

- **When**: its type, `Note`, `CC`, `PC`, `Pressure` (Channel Pressure) or `PitchBend`; its channel or any; its number (the note, the CC, the program) or any; and a range of values, 0 to 127 unless narrowed. A `Note Off` counts as a note of velocity 0, a PC's value is its program, and a pitch bend's is its upper seven bits.
- **Becomes** another message on the DIN output: another type, channel or number, empty for the same, and the value range scaled onto another. From 127 to 0 turns it round, one value alone sends that value every time, and nothing keeps the value as it came. A PC made with no number takes the value as its program, so `CC 20` becomes `PC` of its value.
- Or it **runs a button's list**, named by bank, button and short, long or double press, as a [`Macro`](06-commands.md#macros) does. The list runs as a press would, with its commands on USB and DIN; a `Note Off`, a velocity 0 or a value below 64 runs it with its toggles off, so a pad held down holds a toggle on.
- Or **Nothing**, which only stops the message.

Every entry that matches acts, so one message can make several: two entries on the same PC send two CCs. A message some entry matched goes no further as it came, unless one of them has **also as it came** ticked; what the entries make goes out whether `USB_MIDI_Thru` is on or not, and a message no entry matches goes on through the thru as ever. Up to 32 entries per configuration.

The map works alongside everything else the pedal listens for. [`Remote_Mode`](12-configuration-file.md#usb-midi) comes first, and a message pressing a switch goes no further; bank selection by PC or CC, `LED_Feedback` and following the host's programs still see a message the map translated.

**In the configurator** it is the **MIDI Map** tab, each entry with its **When** and **Becomes**; the web configurator has it too.

**In the demo**, a PC on channel 15 becomes CC 20 = 127 and CC 21 = the program on channel 2, the mod wheel on channel 14 becomes CC 11 on channel 1 turned round and also goes on as it came, note 36 on channel 14 holds the global bank's tuner on while it is down, and the pitch bend on channel 14 becomes CC 4.

### MidiMap_Settings

A row per entry. Empty cells take the default shown.

| Column | Values | Meaning |
|---|---|---|
| `In_Type` | `Note`, `CC`, `PC`, `Pressure`, `PitchBend` | The message it matches. A row without one is left out. |
| `In_Channel` | `Any`, 1–16 | Default any. |
| `In_Number` | `Any`, 0–127 | The note, CC or program. `Pressure` and `PitchBend` have none: leave it empty. |
| `In_Min`, `In_Max` | 0–127 | The values it matches. Default 0 and 127. |
| `Out_Type` | `Note`, `CC`, `PC`, `Pressure`, `PitchBend`, `Run`, `Nothing` | What it becomes. Default the same type. |
| `Out_Channel` | `Same`, 1–16 | Default the same. |
| `Out_Number` | `Same`, 0–127 | Default the same; a `Note` or `CC` made from a `Pressure` or `PitchBend` needs one. |
| `Out_Min`, `Out_Max` | 0–127 | `In_Min`..`In_Max` scaled onto these. Both empty: the value as it came; one alone: always that value. |
| `Run_Bank`, `Run_Button`, `Run_List` | 0–31, `1`–`D`, `Short` / `Long` / `Double` | The list an `Out_Type` of `Run` runs. |
| `Keep` | Y / N | Also as it came. |

<details><summary>Under the hood</summary>

The pages of a slot were full, so the map lives in a second extension area, two flash pages per slot above the power on banner's page, which the tools see as the configuration going on after the double press area. It starts with the marker `EXT2` and counts only when that is there. An entry is 12 bytes, described in `flash_midi_settings.h`. The map is looked up in the USB interrupt, as the thru is; a list to run is queued there, eight at most, and run by the main loop.

</details>

*Firmware 0.90 or later; older firmware gets everything else and the tools say the map was left out.*

---

[← Editing on the pedal](10-editing-on-the-pedal.md) · [Contents](README.md) · [The configuration file →](12-configuration-file.md)
