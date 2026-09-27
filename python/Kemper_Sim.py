"""A Kemper Profiler of make believe, to try the pedal's Kemper_Mode without one.

The pedal, with Kemper_Mode on, sends the amp a beacon every five seconds and
asks it for the rig name and for the state of its eight effect modules. This
answers those questions, in the amp's own System Exclusive dialect, and lets
you change the rig or switch a module on and off to see the pedal follow: the
rig name on its display, the modules on the LEDs of the buttons that send them,
and its tuner full screen while the amp's is up.

    python3 Kemper_Sim.py

Then, at the prompt:

    rig Crunch DLX      name the rig the pedal shows
    a / b / c / d       switch Stomp A, B, C or D on or off
    x / mod / dly / rev the same for the others
    tuner               open or close the tuner, as CC 31 from the pedal does
    tune A -1500        the note the tuner hears and how far off, -8192 to
                        8191 (0 in tune, the needle's end at about 3400)
    sweep E             a string brought up to pitch, from flat to in tune
    show                what the amp is supposed to be doing
    quit

The real link is the same one this uses: on a Profiler Player the pedal plugs
into the Player's USB A socket, and the Player, being the host, asks and
answers exactly as a computer does here.
"""
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])

import mido

from lib import kemperProtocol as kp
from lib.midiDevice import MidiCommander


class FakeKemper:
    """The amp's side of the conversation, over an already open port pair."""

    def __init__(self, inport, outport, verbose=True):
        self.inport = inport
        self.outport = outport
        self.verbose = verbose
        self.rig = "Empty Rig"
        self.modules = {name: False for name, _, _, _ in kp.MODULES}
        self.beacons = 0
        self.last_beacon = []
        self.name_requests = 0
        self.module_requests = 0
        self.tuner = False

    # --- the amp speaking ---------------------------------------------------
    def _send(self, message):
        self.outport.send(mido.Message("sysex", data=message[1:-1]))

    def say_rig(self):
        self._send(kp.rig_name(self.rig))

    def say_module(self, name):
        self._send(kp.module_state(name, self.modules[name]))

    def set_rig(self, name):
        self.rig = name[:20]
        self.say_rig()

    def set_module(self, name, on):
        self.modules[name] = on
        self.say_module(name)

    def module_for_cc(self, cc):
        """The module a Control Change switches, tails and all, or None."""
        for name, _, own, tails in kp.MODULES:
            if cc in (own, tails):
                return name
        return None

    def set_tuner(self, on):
        self.tuner = on
        self._send(kp.tuner_mode(on))

    def tune(self, note, offset):
        """The tuner hearing a note (a name or a MIDI number), offset from in tune."""
        if isinstance(note, str):
            note = 48 + kp.NOTE_NAMES.index(note.upper())
        if not self.tuner:
            self.set_tuner(True)
        self._send(kp.tuner_note(note))
        self._send(kp.tuner_deviance(kp.DEVIANCE_IN_TUNE + offset))

    # --- and listening ------------------------------------------------------
    def poll(self, seconds=0.0):
        """Answer whatever the pedal has asked. Returns what it asked for."""
        asked = []
        until = time.time() + seconds
        while True:
            msg = self.inport.poll()
            if msg is None:
                if time.time() >= until:
                    return asked
                time.sleep(0.005)
                continue

            if msg.type == "control_change" and msg.control == kp.CC_TUNER:
                asked.append("tuner " + ("on" if msg.value >= 64 else "off"))
                self.set_tuner(msg.value >= 64)
                continue
            if msg.type == "control_change":
                # A real amp switches the module and says so
                name = self.module_for_cc(msg.control)
                if name is not None:
                    asked.append(name + (" on" if msg.value >= 64 else " off"))
                    self.set_module(name, msg.value >= 64)
                continue
            if msg.type != "sysex" or not kp.is_kemper(msg.data):
                continue

            function = kp.function(msg.data)
            if function == kp.FN_BEACON:
                self.beacons += 1
                self.last_beacon = [kp.SYSEX_START] + list(msg.data) + [kp.SYSEX_END]
                asked.append("beacon")
                continue

            request = kp.request(msg.data)
            if request is None:
                continue
            function, page, number = request
            if function == kp.FN_REQ_STRING and page == kp.PAGE_RIG \
                    and number == kp.PARAM_RIG_NAME:
                self.name_requests += 1
                asked.append("rig name")
                self.say_rig()
            elif function == kp.FN_REQ_PARAM and number == kp.PARAM_ON_OFF:
                for name, module_page, _, _ in kp.MODULES:
                    if module_page == page:
                        self.module_requests += 1
                        asked.append(name)
                        self.say_module(name)
                        break


SHORTCUTS = {
    "a": "Stomp A", "b": "Stomp B", "c": "Stomp C", "d": "Stomp D",
    "x": "Stomp X", "mod": "Mod", "dly": "Delay", "rev": "Reverb",
}


def main() -> int:
    with MidiCommander() as dev:
        amp = FakeKemper(dev.inport, dev.outport)
        print("Kemper of make believe. The pedal needs Kemper_Mode on.")
        print("Waiting for it to ask something…  (Ctrl-C to leave)")
        while True:
            try:
                asked = amp.poll(0.5)
            except KeyboardInterrupt:
                return 0
            if asked:
                print("  asked for: " + ", ".join(asked))
                break

        while True:
            try:
                line = input("kemper> ").strip()
            except (EOFError, KeyboardInterrupt):
                return 0
            amp.poll(0.05)

            if not line:
                continue
            word, _, rest = line.partition(" ")
            word = word.lower()
            if word in ("quit", "exit", "q"):
                return 0
            if word == "rig":
                amp.set_rig(rest or "Empty Rig")
                print(f"  rig: {amp.rig}")
            elif word in SHORTCUTS:
                name = SHORTCUTS[word]
                amp.set_module(name, not amp.modules[name])
                print(f"  {name}: {'on' if amp.modules[name] else 'off'}")
            elif word == "tuner":
                amp.set_tuner(not amp.tuner)
                print(f"  tuner: {'on' if amp.tuner else 'off'}")
            elif word == "tune":
                parts = rest.split()
                try:
                    note = parts[0] if parts else "A"
                    note = int(note) if note.isdigit() else note
                    amp.tune(note, int(parts[1]) if len(parts) > 1 else 0)
                except (ValueError, IndexError):
                    print("  tune <C..B or a note number> [offset]")
            elif word == "sweep":
                note = (rest or "E").strip().upper()
                if note not in kp.NOTE_NAMES:
                    print("  sweep <C..B>")
                    continue
                for offset in range(-4000, 1, 100):
                    amp.tune(note, offset)
                    amp.poll(0.04)
            elif word == "show":
                print(f"  rig: {amp.rig}, tuner {'on' if amp.tuner else 'off'}")
                for name, _, cc, _ in kp.MODULES:
                    print(f"  {name:8} {'on ' if amp.modules[name] else 'off'}  (CC {cc})")
                print(f"  beacons {amp.beacons}, rig name asked {amp.name_requests} times,"
                      f" modules {amp.module_requests}")
            else:
                print("  rig <name> | a b c d x mod dly rev | tuner | tune <note> [offset]"
                      " | sweep <note> | show | quit")
            amp.poll(0.05)


if __name__ == "__main__":
    raise SystemExit(main())
