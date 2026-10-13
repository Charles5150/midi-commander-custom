# What it does

**English** · [Español](../es/01-what-it-does.md)

Everything the firmware and its tools can do, grouped the way the manual is. Each group's chapter tells the whole story.

## Banks and songs

*In detail: [Banks](04-banks.md).*

- **32 banks × 8 buttons.** A short press on Bank Up / Bank Down steps one bank, a long press jumps a configurable number of banks, and both wrap around. A `Bank` command can also jump straight to a given bank, so one bank can act as a setlist index. Each bank has a name shown on the display.
- **Setlist.** Bank Up / Down can follow an order of your choosing instead of the bank numbers, so the night's songs come up one after another whatever banks they live in. Relative Bank commands follow it too; jumping to an exact bank still works as before. Up to four setlists, named, one for each show, picked from the floor.
- **Where you are in the set.** In a bank of the setlist, the info line can show the song's place and the next one, `3/12>INTR`; see [Where you are in it](04-banks.md#where-you-are-in-it).
- **Preview a bank before going there.** With `Bank_Preview` on, Bank Up / Down only show the bank they would go to, its name inverted on the display, and send nothing; one of the eight buttons confirms it. Brushing a bank switch in the middle of a song cannot change the patch, and a bank left unconfirmed goes back by itself.
- **Any bank in two presses.** A `Direct` button turns the eight buttons into a chooser, a group of eight banks and then the bank, so any of the 32 is two presses away; see [Any bank in two presses](04-banks.md#any-bank-in-two-presses).
- **Commands on entering and leaving a bank.** Each bank can send a set of commands when you switch to it, typically a Program Change that selects its patch, so no button is spent on it, and another when you leave it, for instance to switch off what it switched on.
- **Second page in a bank.** A button shows another bank's eight buttons and labels in place of the current ones, and back again, like a shift key, doubling what a song holds. It is still the same bank: Bank Up / Down, the expression pedals and the text from the computer carry on as they were.
- **The Bank Up / Down switches send MIDI too.** Each has its own command list for a short and a long press, the same in every bank. `Bank_Switch_Mode` chooses whether they also change bank, or stop changing bank altogether, which turns the pedal into a plain ten switch controller, all ten labelled on the screen.
- **Four configurations on one pedal.** Keep up to four complete configurations, one per band or venue for instance, and switch between them from a button. The pedal shows the number and name of the one it switched to and comes back on it after a power cycle.
- **Bank changes from incoming MIDI.** A Program Change or a Control Change arriving over USB can select a bank, so a DAW or another pedal can drive this one.
- **Remember state.** Optionally power up in the last bank with every toggle exactly as you left it, journaled across several flash pages so wear is not a concern.

## Buttons

*In detail: [Buttons](05-buttons.md).*

- **Long press.** A second set of up to 10 commands fires when a button is held past a configurable time (default 500 ms). Buttons without long press commands react instantly, as before.
- **Double press.** A third command list per button, fired by two quick presses, alongside the short and the long press.
- **Press at once.** A button with a long or double press list can still send its short press the moment it goes down, for a looper started on the beat; see [Press at once](05-buttons.md#press-at-once).
- **Labels for the long press.** Each long press has a label of its own, and a `Reveal` button shows them all while it is held; see [Labels for the long press](05-buttons.md#labels-for-the-long-press).
- **Two switches together.** Pressing a pair of switches at once, 3 and 4 with one foot for instance, runs a list of its own instead of what either switch does alone, the way Boss and Morningstar controllers reach the tuner or the looper. Up to twelve pairs, in every bank or in one, and only the switches of a pair wait to see whether the other one follows.
- **Locking the switches.** A `Lock` command, best on a pair of switches, locks every switch, so stepping over the pedal or packing up sends nothing, and the same pair unlocks; see [Locking the switches](05-buttons.md#locking-the-switches).
- **Momentary or toggle** behaviour per command, and timed auto-release (up to 1.27 s) for Notes, Pitch Bend and keys.
- **Latch or momentary.** A toggle button can latch on a tap and work as a momentary switch when held, like the boost on a Boss or Morningstar pedal: tap it on for the song, or hold it for a solo and it goes back off when you let go.
- **Reset on bank change.** Per button, a toggle can go back to off each time you leave its bank, so the boost starts off in every song while the noise gate stays as you left it.
- **Exclusive groups.** Put toggle buttons of a bank in a group and switching one on switches the others off, sending their off commands, like the channel buttons of an amp or a choice between delays.
- **Reload when lit.** Pressing a lit button can send its list again and leave it lit, to get back a preset tweaked on the amp as it was stored; see [Reload when lit](05-buttons.md#reload-when-lit).
- **Scenes.** One press puts the toggle buttons of the bank into a chosen combination, delay on and chorus off for instance, pressing for you only the ones that are not already there. A `Scene` `Save` stores the toggles as they are now into a scene, with your feet; see [Saving a scene with your feet](05-buttons.md#saving-a-scene-with-your-feet).
- **Cycle buttons.** One button steps through several states, each with its own commands and its own label on the display: the four channels of an amp on a single switch, say, one press each, round and round.
- **Global buttons.** One bank set aside holds the buttons that should be the same wherever you are — the tuner, panic, the tap — and any button of any other bank marked global takes everything from it: its commands, its label, its light and whether it is on. Written once, changed once, and on all night under the same foot.
- **Linked toggles.** With `Link_Toggles` on, toggle buttons that send the same CC or note share their state across every bank: the delay switched on in one song is lit in the next, whichever switch it sits on there.
- **LED modes** per button: Normal, Reverse (lit when off) or AlwaysOn (blinks while active). The Bank Up / Down LEDs have the same options. Global brightness for lit LEDs and, separately, for LEDs lit at rest, so an active button stands out from an idle one.

## Commands

*In detail: [Commands](06-commands.md).*

- **Up to 10 commands per button press**, sent in order. Any mix of Program Change (with optional Bank Select), Control Change, NRPN and RPN, Note, Pitch Bend, Channel Pressure, Start, Stop, USB keyboard keys and media keys, each MIDI command on its own channel.
- **Pauses between commands.** A `Wait` command spaces out the commands of a button, for the device that drops a Control Change arriving right behind a Program Change. The pedal keeps reading switches and pedals while it waits. It can also wait for the next beat or bar of the clock, so a looper without quantize starts on the downbeat.
- **CC ramps.** A `Ramp` command makes the Control Change below it walk to its value over a time, up to about 11 minutes, instead of jumping: a volume swell or a slow filter sweep from a single press, and back again on the release or when a toggle is switched off.
- **Values and conditions.** The pedal keeps eight values of its own, and a `Value` command sets one, adds to it or takes away, round and round within a top you choose. An `If` command above a command holds it back unless the test holds: a button's toggle on or off, one of those values against a number, or the bank you are on. One button can then do different things depending on another — a shift layer — and a counter on a long press can walk a set of patches one press at a time.
- **Macros.** A command list stored once and called from many buttons: the ten commands that set up the band's whole rig live on one button and every bank that wants them spends a single command. Macros call macros, pauses inside them are kept, and it is the one feature that gives configuration room back instead of taking it.
- **A button that presses others.** A song's intro button switches the delay on and lights it, in this bank or any other; a preset change puts a button back to off without sending a thing. Press, on only if off, off only if on, or just set the state and LED.
- **One channel for everything, or several at once.** A global channel setting moves a whole configuration to another channel, and a `Chan` command sends the command below it to as many channels as you like.
- **Next and previous preset.** A button steps the Program Change up or down from wherever you are, whether you got there with a button, by entering a bank or from the computer, and shows the new number on the display. Stops at the ends or wraps round, within the range your device has.
- **No reload of the preset you are on.** A Program Change the device is already on can be left out, so coming back to a bank does not reload the preset and cut the sound, with a Force for when you want it reloaded; see [Not reloading the preset you are on](06-commands.md#not-reloading-the-preset-you-are-on).
- **Relative CC.** A button can nudge a CC value up or down by a step on each press, optionally wrapping, for setting a parameter with your foot. The value it lands on shows on the display for a moment, so you are not adjusting blind. Held down, it can keep going on its own, faster and faster, and so can a next or previous preset button.
- **Recorder and sequencer control.** `MMC` commands work the transport of a DAW or a recorder — play, stop, record, rewind, locate to a time — and `Song` commands pick the song of a drum machine or a sequencer and where in it to start.
- **Custom SysEx.** Up to sixteen SysEx messages can be stored and sent from a button, for devices that are only controllable that way. A message can carry a value where it has `VV` and end in a Roland checksum; see [A value in the message, and the Roland checksum](06-commands.md#a-value-in-the-message-and-the-roland-checksum).
- **USB keyboard and media keys (HID).** A command can press a key with Ctrl / Shift / Alt / Cmd modifiers, tap it, hold it or release it, or send a media key (play/pause, next, previous, stop, volume, mute, record) to the computer.
- **Panic.** A command that sends All Sound Off and All Notes Off on all sixteen channels, to USB and the DIN output, for the stuck note or runaway sound in the middle of a set.

## Tempo

*In detail: [Tempo](07-tempo.md).*

- **Tap tempo and MIDI clock.** A button sets the tempo by tapping and another starts or stops a 24 PPQN MIDI clock on both USB and the DIN output, so a delay or looper follows your foot. The tempo shows on the display as you tap. The tap button's LED flashes on every beat, whether the tempo is yours or the host's. Each bank or song can also set its own tempo on entry, a tempo tapped at rehearsal can be saved into it with a press, and a pair of buttons can nudge it a BPM at a time. Gear that takes a tap CC and not the clock is tapped on the beat after every change of tempo, your own taps passed on.
- **Follows the host's clock.** With `Clock_Follow` on, the pedal measures MIDI clock arriving over USB, adopts that tempo and flashes it on the display for 1.5 seconds, and keeps its own clock out of the way while the host's is running. If the host's clock stops, the pedal's carries on at the same tempo.
- **Bar and beat on the display, and a count-in.** With `Beat_Counter` on, the display counts bars and beats while a clock runs, the pedal's or the host's, from its Start; and a `Wait` `Count` counts a bar in, `IN 4` to `IN 1` in large type, before the looper starts recording on the one.
- **Recorded runs of presses.** Play a song once with the clock running and the pedal keeps on which beat each switch went down; from then on, whenever the clock runs in that bank, from the pedal or the host, it presses them itself on those beats, long and double presses included.
- **Tempo-synced LFO.** An `LFO` command makes the Control Change below it swing up and down by itself, one cycle per note division of the tempo (from a sixteenth triplet to four bars) in a sine, triangle, saw, square or random shape: tremolo, filter sweeps and auto-pan that follow your tap or the host's clock.
- **Step sequencer.** A run of `Seq` commands turns the Control Change or note below it into a sequence: a value a step, an eighth note or whatever division you choose, round and round while the button is held or its toggle is on. Rests included, so it is a rhythm as much as a melody: a stuttered filter, an arpeggio, a pattern of amp switches, all in time with the tap tempo or the host's clock.

## Expression pedals

*In detail: [Expression pedals](08-expression.md).*

- **Two expression pedals** with per-pedal CC number, MIDI channel, calibrated end points, response curve and direction, calibrated live from the configurator. Each can also act as a switch: reaching the toe, or returning to the heel, taps a button of the current bank.
- **Expression per bank.** Each bank can give each expression pedal its own CC and channel, or silence it, so the same pedal is a wah in one bank and a volume in another.
- **Expression target from a button.** A command changes what an expression pedal sends, its CC and channel, or silences it, so one pedal can be the wah, then the volume, then a parameter, within the same bank; as a toggle, switching it off gives the pedal back.
- **Auto-engage wah.** Moving an expression pedal up from the heel switches a button on, and resting at the heel for a moment switches it off again, like the auto-engage wahs of Fractal and Line 6: no stomping on the wah before using it.
- **A stepped pedal.** An expression pedal's travel can be cut into 2 to 8 zones, each tapping a button as the foot enters it: one of four delay times, a harmony or a scene picked with the foot.
- **Three more switches on a jack.** A small box of up to three footswitches, wired like an expression pedal and plugged into its jack, holds down switches of the pedal, Bank Down and Up included.
- **No volume jump after a preset change.** An expression pedal can send where it is as a bank is entered, so the preset the bank calls up takes the volume from your foot.
- **No jump when a pedal takes over a CC.** With `CatchUp` or `Scaled`, a pedal that comes back to a CC left at another value does not jump it to where the foot is; see [Picking up a CC without a jump](08-expression.md#picking-up-a-cc-without-a-jump).
- **Its value on the display.** While a pedal moves, the display can show what it sends, as a number or a bar; see [Its value on the display](08-expression.md#its-value-on-the-display).
- **Expression output range.** A pedal can send only part of the range, 40 to 127 for a volume that never drops to silence for instance, or run backwards; per pedal, and per bank on top of that.
- **Pitch Bend and 14-bit CC from a pedal.** An expression pedal can send Pitch Bend, for a whammy, or a 14-bit CC pair, with 16384 steps instead of 128, for sweeps without zipper noise on synths and plugins that read them.
- **A SysEx parameter from a pedal.** A pedal can sweep a parameter that a device only takes by SysEx, its position written into a stored message; see [A SysEx parameter](08-expression.md#a-sysex-parameter).
- **An expression pedal as the speed of the LFOs and sequences.** Instead of a CC, a pedal can set how fast every LFO and step sequence goes, heel slow and toe fast, always on a note division of the tempo: a tremolo that speeds up under your foot and stays in time.
- **Scrolling lyrics on the computer.** With `Wheel` or `Arrows`, a pedal scrolls lyrics, a score or a teleprompter, faster the further you press it; see [Scrolling on the computer](08-expression.md#scrolling-on-the-computer).

## The display

*In detail: [The display](09-the-display.md).*

- **Button labels on the display.** Each button has a 4 character label; the screen shows the current bank and a 2×4 grid mirroring the pedal, with toggle buttons drawn inverted while on.
- **Live values.** A label, a bank's name or its info line can show a value as it is now: `$V` the button's value, `$N` the preset by the name given in the **Presets** tab, `$1` to `$8` the pedal's own values, `$T` the tempo; see [Live values](09-the-display.md#live-values).
- **Written on by the computer.** A DAW, MainStage or a script can put the patch or song name on the display over SysEx: in place of the bank name, of its info, or across the whole top line in large or small letters, until the bank changes, for good, or for a moment. A name longer than its place scrolls across it once, when it arrives and whenever a bank is entered, and then shows its beginning. It can write each button's label too, for a script that drives the pedal (1.34). `Send_Text.py` sends both from a terminal, or prints the bytes for a host to send.
- **A banner at power on.** The configuration's name and the firmware version can cross the display in large letters as the pedal starts, so you see at a glance which configuration came up. Or a text of your own, up to 60 characters, that the pedal keeps whatever configuration is loaded: a band, a show, a phone number in case it gets lost. Any switch cuts it short, and the pedal answers from the first press. Turn it on with `Boot_Banner`; see [The banner's own text](09-the-display.md#the-banners-own-text).
- **A gig view.** The song's name and its info line in letters large enough to read standing, in place of the labels. A press brings the labels back for three seconds, entering a bank shows the next song's name, and a pair of switches or `Gig_View` turns it on. See [Gig view](09-the-display.md#gig-view).
- **A MIDI monitor for soundcheck.** A mark in the corner as MIDI comes in over USB, and if you want the last message received or sent, `IN CC7=100 CH3`, for two seconds: whether MIDI gets through, without a laptop. See [MIDI monitor](09-the-display.md#midi-monitor).

## On the pedal, without a computer

*In detail: [Editing on the pedal](10-editing-on-the-pedal.md).*

- **Editing on the pedal.** Bank Down and Bank Up held together open an editor on the pedal's own screen: the commands of any button of any bank, short and long press, their labels, the settings that are a number or a choice, and the order of the setlist, all changed with your foot and written straight to flash. For the wrong Program Change found at soundcheck, with no laptop in sight.
- **Safe mode.** Hold any of the eight command switches while the pedal powers on and it starts without sending a thing: no bank enter commands, no saved bank or toggles brought back, no Kemper beacon or GT-1000 questions, no expression pedal position. It still changes bank, answers its buttons and opens the on-pedal editor, so a configuration that mutes the amp or upsets the rig at start-up can be put right with no computer at hand. See [Safe mode](10-editing-on-the-pedal.md#safe-mode).
- **Works without a computer.** On a USB charger or a power bank the pedal runs normally and drives your gear over the DIN output.
- **Idle sleep.** After a configurable number of minutes with nobody touching it, the display and the LEDs switch off. Any press or expression pedal movement brings them back, and the press that wakes it still does its job, so nothing is lost on stage.
- **Carries on when the computer sleeps.** If the computer it is plugged into goes to sleep and keeps powering the USB port, the pedal keeps working: the display, the LEDs and DIN MIDI as usual, and USB MIDI dropped until a computer is back.
- **Restarts itself if it ever locks up.** A watchdog notices when the firmware stops running and restarts the pedal, back and working about six seconds later, instead of leaving it dead until it is switched off and on. It comes back where it was: on the same bank, with the same toggles on and the same tempo, whatever `Remember_State` says, and shows RESTARTED for a moment. A display that stops answering, from static or a loose flex, no longer freezes the pedal either: it carries on, and the screen is sent again.
- **Keeps time while it saves.** The bank and the toggles are saved in the pedal's flash a couple of seconds after they change, and every eighty saves or so part of it has to be wiped, which stops the pedal for a tenth of a second. That wipe now waits until nothing is keeping time: not while the pedal's clock runs, a clock comes from the computer, or an LFO or a sequence plays, so the clock, the LFOs and the tap tempo carry on through a song without a stumble. What changes meanwhile is still saved, and in the rare case that the room runs out mid-song, the last save goes as soon as the music stops. A scene saved with the feet, or a change made in the on-pedal editor, cannot wait, but the time it takes is given back: the clock sends the clocks it owes at once and keeps its place, and the LFOs theirs.
- **A power cut does not lose the configuration.** A scene saved with the feet or a change made on the pedal rewrites a 2 kB page of the configuration. The new page is written to a spare page first, so should the power go while the page itself is rewritten, the pedal finishes it from there the next time it starts.

## With a computer and other gear

*In detail: [Templates and devices](11-devices.md).*

- **LEDs that follow the computer.** With `LED_Feedback` on, a CC or a note arriving over USB lights or darkens the toggle buttons that send it, so the pedal shows what is really on when an effect is changed from a DAW or an amp editor. A device that reports on another CC than the one it is sent, or with other values, is followed with a `Listen` command on the button, and several on one CC make the LED blink fast, slowly or dim by the value, so a looper's recording, overdubbing and playing can be told apart at a glance.
- **Pressed from the computer.** With `Remote_Mode` on, ten CCs or notes arriving over USB press the ten switches, held for as long as the host holds them, so a DAW, MainStage or a script can drive the pedal's own logic: toggles, long and double presses, bank changes, LEDs and display.
- **Translating what comes in.** The MIDI map turns a message arriving over USB into what the device on the DIN cable wants: a Program Change from the DAW into the two CCs an old pedal needs, the mod wheel turned round onto the amp's volume, a channel moved, or a pad on a keyboard running a button's list; see [Translating what comes in](11-devices.md#translating-what-comes-in).
- **USB-to-DIN MIDI thru.** Optionally forward everything received over USB to the MIDI OUT jack, so the pedal doubles as a USB MIDI interface for the device behind it. Clock / Start / Continue / Stop have their own switch.
- **Three USB ports, if you want them.** One for the pedal, one going straight to the DIN output, and the pedal again for a second program, so the configurator can connect while a DAW holds the first on Windows; see [Three USB ports](11-devices.md#three-usb-ports).
- **Survives Active Sensing.** Some hosts, the Kemper Profiler Player among them, send an Active Sensing byte every 300 ms. A controller that never reads it lets its USB buffer fill until the link stalls, which is what makes the stock firmware drag the host down to a crawl. Here every incoming USB MIDI event is consumed and the endpoint is always re-armed, so the stream cannot back up.
- **Two way with a Kemper.** With `Kemper_Mode` on, the pedal asks the amp about itself and follows the answers: the rig you are on written beside the bank name and the effect modules lighting the buttons that switch them, whether the module was switched with your foot, on the amp or from anywhere else, and the amp's tuner drawn full screen on the pedal while it is up; see [Two way with a Kemper](11-devices.md#two-way-with-a-kemper).
- **Two way with a GT-1000.** With `GT1000_Mode` on, the pedal asks a Boss GT-1000 or GT-1000CORE about itself: the patch you are on written beside the bank name, and the effects the patch's ASSIGNs switch from a CC lighting the buttons that send that CC, however the effect was switched; the two meet on a computer or a USB MIDI host box. See [Two way with a GT-1000](11-devices.md#two-way-with-a-gt-1000).
- **Ready for the Fractal FM3.** A template that loads a preset per bank and puts scenes, tuner, tap tempo, the looper and block bypass under your feet; see [the FM3 template](11-devices.md#fractal-audio-fm3-template).
- **Ready for the Line 6 HX Stomp.** A template with a preset per bank, snapshots, footswitches FS1–FS5, tuner, tap tempo and the looper, using the HX Stomp's own MIDI map so there is nothing to assign; see [the HX Stomp template](11-devices.md#line-6-hx-stomp-template).
- **Ready for the Neural DSP Quad Cortex.** A template with a preset per bank, scenes, footswitches A–H, tuner, tap tempo and Looper X, using the Quad Cortex's own MIDI map so there is nothing to assign; see [the Quad Cortex template](11-devices.md#neural-dsp-quad-cortex-template).
- **Ready for more gear.** Templates for the Eventide H90, the Strymon TimeLine, BigSky, Volante and Iridium, the Meris Enzo X, LVX and MercuryX, the Line 6 Helix, Helix Stadium and POD Go, the Neural DSP Nano Cortex, the IK Multimedia TONEX Pedal and TONEX Board, the Valeton GP-200, the Hotone Ampero II and the Boss RC-600, each on the device's own MIDI map, with a table of what to assign where the device has none; see [Templates and devices](11-devices.md).
- **Your whole board at once.** Pick the devices on your board, up to four, each with its channel, and the configurator puts their templates together: the main device's presets in the banks, the others' footswitches or looper in banks of their own, and the others changing preset with it if you like; then it lists what to set on each device; see [Your rig](11-devices.md#your-rig-several-devices-at-once).
- **Ready for the computer.** Templates for MainStage, Gig Performer, Cantabile and Ableton Live that select patches, rackspaces or songs with a Program Change and drive the rest with each program's own keyboard shortcuts, typed by the pedal as a USB keyboard, so there is little or nothing to learn; see [Templates for programs on the computer](11-devices.md#templates-for-programs-on-the-computer).
- **Ready for the Kemper Profiler Player.** A template with the Player's ten banks of five rigs, its effect modules and effect buttons, tuner and tap tempo, again with nothing to assign on the Player; see [the Kemper Player template](11-devices.md#kemper-profiler-player-template).

## The tools

*In detail: [The configurator](03-the-configurator.md).*

- **In the browser.** The web configurator does the same from a page in Chrome, Edge or Opera, with nothing to install: edit, read, write and back up the configurations, see and play the pedal live, show the song you are on large on a tablet on a stand, with your notes for it, and update its firmware, the very first flash included. With no pedal, it runs the pedal's own firmware in the page, to try a configuration or the pedal itself. **Share link** puts a configuration inside a link for a bandmate, with nothing uploaded. On an iPad or iPhone it works in an app that adds Web MIDI, such as Web MIDI Browser with SysEx turned on in its settings, all but the firmware updates; see [In the browser](14-in-the-browser.md) and [On an iPad or iPhone](14-in-the-browser.md#on-an-ipad-or-iphone).
- **A cheat sheet to print.** Each bank's switches laid out as on the pedal, with what each press sends in words and a known device's own names, the setlist with its tempos, the pedals and the combinations, on a page for the floor, the band or the tech; see [Cheat_Sheet](13-command-line-tools.md#cheat_sheet-a-page-to-print).
- **Virtual pedal.** The configurator draws the pedal as it is built, and lets you press its switches with the mouse, tap, hold or double click, while its screen, pixel for pixel, and its LEDs are read back from the pedal, so a configuration can be tried without standing on it.
- **Configuration over USB.** Flash a configuration to the pedal and read it back, from the GUI or the command line, over ordinary USB MIDI SysEx. No special driver.
- **What changes, before writing.** **Flash to Device** reads the slot first, lists what writing will change and asks; `Diff_Config.py` compares two configurations the same way; see [Diff_Config](13-command-line-tools.md#diff_config-what-changes).
- **Arranging a set.** Move banks up and down the list, or anywhere in one go, and every bank change, setlist entry, macro and combination follows them; copy a bank or a single button onto another.
- **A library of songs.** Save a bank as a song file, with the lists it runs in other banks and its SysEx strings, and load it into a bank of any configuration, to build a set from songs set up once or share one with the band; see [Songs](04-banks.md#songs-a-bank-in-a-file-of-its-own).
- **MIDI learn.** Press Learn on a command and move a knob or press a button on the device: its type, channel and number fill themselves in, from any MIDI input the computer has.
- **Device dictionary.** Pick a command by name, **HX Stomp > FS4** or **H90 > Perform 3**, from the MIDI maps of the twenty-one devices with a template, or of 571 more from the OpenMIDI community, and see the name beside a CC already written.
- **MIDI monitor.** Every message reaching the computer, from the pedal or any other input, timed to the millisecond and read in plain words beside its bytes, with filters by kind, channel and port.
- **Backups.** Copy all four configuration slots to a folder in one go, one editable CSV each, and put them all back just as easily.
- **Firmware updates with nothing held.** From firmware 0.58 the pedal restarts in DFU mode when the computer asks, so `Update_Firmware.py` or **Update Firmware…** in the configurator does the whole update in about fifteen seconds: no switches held at power on, no power cycle, and the configuration left as it is. The stock bootloader is never written.

---

[Contents](README.md) · [Getting started →](02-getting-started.md)
