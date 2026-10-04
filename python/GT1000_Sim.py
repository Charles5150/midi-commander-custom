"""A Boss GT-1000 of make believe, to try the pedal's GT1000_Mode without one.

The pedal, with GT1000_Mode on, asks the unit for the patch number every
second, and for the name and the ASSIGNs of each patch it lands on. This
answers those questions in Roland's own System Exclusive, and lets you change
the patch or switch an effect to see the pedal follow: the patch name on its
display, and the effects on the LEDs of the buttons that send the CC an ASSIGN
switches them with.

    python3 GT1000_Sim.py

Then, at the prompt:

    patch 12 Lead Boost  go to patch 12, named "Lead Boost"
    assign 1 DELAY 1 81  ASSIGN 1 switches DELAY 1 when CC 81 comes in
    fx DELAY 1           switch that effect on or off
    show                 what the unit is supposed to be doing
    quit

The patch it starts on has ASSIGN 1 to 4 switching OD/DS 1, DELAY 1, REVERB
and CHORUS with CC 80 to 83. The unit's own switches also make a CC it has an
ASSIGN for switch the effect, as a real one would.
"""
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])

import mido

from lib import gt1000Protocol as gp
from lib.midiDevice import MidiCommander

DEFAULT_ASSIGNS = [("OD/DS 1", 80), ("DELAY 1", 81), ("REVERB", 82), ("CHORUS", 83)]


class FakeGT1000:
    """The unit's side of the conversation, over an already open port pair."""

    def __init__(self, inport, outport):
        self.inport = inport
        self.outport = outport
        self.patch = 0
        self.name = "Clean Start"
        self.effects = {name: False for name, _, _ in gp.EFFECTS}
        self.assigns = [None] * gp.ASSIGN_COUNT     # (effect, cc) or None
        for i, (effect, cc) in enumerate(DEFAULT_ASSIGNS):
            self.assigns[i] = (effect, cc)
        self.notify = False
        self.requests = 0

    # --- the unit speaking ---------------------------------------------------
    def _send(self, message):
        self.outport.send(mido.Message("sysex", data=message[1:-1]))

    def memory(self, lin):
        """The byte at a linear address, as far as the pedal asks about."""
        number = gp.linear(gp.ADDR_PATCH_NUMBER)
        if number <= lin < number + 4:
            return gp.nibbles(self.patch)[lin - number]
        name = gp.linear(gp.ADDR_PATCH_NAME)
        if name <= lin < name + gp.PATCH_NAME_SIZE:
            return ord(self.name.ljust(gp.PATCH_NAME_SIZE)[lin - name])
        for i in range(gp.ASSIGN_COUNT):
            at = gp.linear(gp.assign_address(i))
            if at <= lin < at + gp.ASSIGN_SIZE:
                if self.assigns[i] is None:
                    data = gp.assign_data(False, 0, 0)
                else:
                    effect, cc = self.assigns[i]
                    data = gp.assign_data(True, gp.EFFECT_TARGETS[effect], gp.source_for_cc(cc))
                return data[lin - at] if lin - at < len(data) else 0
        for effect, _, address in gp.EFFECTS:
            if lin == gp.linear(address):
                return 1 if self.effects[effect] else 0
        return 0

    def report(self, address, size):
        lin = gp.linear(address)
        self._send(gp.message(gp.CMD_DT1, lin, [self.memory(lin + k) for k in range(size)],
                              gp.UNIT_DEVICE))

    def set_patch(self, number, name=None):
        self.patch = number
        if name is not None:
            self.name = name[:gp.PATCH_NAME_SIZE]
        if self.notify:
            self.report(gp.ADDR_PATCH_NUMBER, gp.PATCH_NUMBER_SIZE)

    def set_effect(self, effect, on):
        self.effects[effect] = on
        if self.notify:
            self.report(gp.EFFECT_ADDRESSES[effect], 1)

    def set_assign(self, i, effect, cc):
        self.assigns[i] = (effect, cc) if effect else None
        if self.notify:
            self.report(gp.assign_address(i), gp.ASSIGN_READ)

    # --- and listening -------------------------------------------------------
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

            if msg.type == "control_change":
                # An ASSIGN in TOGGLE mode: each press flips the effect
                for slot in self.assigns:
                    if slot and slot[1] == msg.control and msg.value >= 64:
                        effect = slot[0]
                        asked.append(f"{effect} {'off' if self.effects[effect] else 'on'}")
                        self.set_effect(effect, not self.effects[effect])
                continue
            if msg.type != "sysex" or not gp.is_gt1000(msg.data):
                continue
            parsed = gp.parse(msg.data)
            if parsed is None:
                continue
            command, lin, data = parsed
            if command == gp.CMD_DT1 and lin == gp.linear(gp.ADDR_NOTIFY):
                self.notify = bool(data and data[0])
                asked.append("notify")
            elif command == gp.CMD_RQ1 and len(data) == 4:
                self.requests += 1
                size = (data[0] << 21) | (data[1] << 14) | (data[2] << 7) | data[3]
                a = gp.address_bytes(lin)
                address = (a[0] << 24) | (a[1] << 16) | (a[2] << 8) | a[3]
                asked.append(f"{address:08X}/{size}")
                self.report(address, size)


def main() -> int:
    with MidiCommander() as dev:
        unit = FakeGT1000(dev.inport, dev.outport)
        print("GT-1000 of make believe. The pedal needs GT1000_Mode on.")
        print("Waiting for it to ask something…  (Ctrl-C to leave)")
        while True:
            try:
                asked = unit.poll(0.5)
            except KeyboardInterrupt:
                return 0
            if asked:
                print("  asked for: " + ", ".join(asked))
                break

        names = {name.upper(): name for name, _, _ in gp.EFFECTS}
        while True:
            try:
                line = input("gt1000> ").strip()
            except (EOFError, KeyboardInterrupt):
                return 0
            unit.poll(0.05)

            if not line:
                continue
            word, _, rest = line.partition(" ")
            word = word.lower()
            if word in ("quit", "exit", "q"):
                return 0
            if word == "patch":
                number, _, name = rest.partition(" ")
                try:
                    unit.set_patch(int(number), name or None)
                    print(f"  patch {unit.patch}: {unit.name}")
                except ValueError:
                    print("  patch <0-499> [name]")
            elif word == "fx" and rest.upper() in names:
                effect = names[rest.upper()]
                unit.set_effect(effect, not unit.effects[effect])
                print(f"  {effect}: {'on' if unit.effects[effect] else 'off'}")
            elif word == "assign":
                parts = rest.split()
                try:
                    i = int(parts[0]) - 1
                    cc = int(parts[-1])
                    effect = names[" ".join(parts[1:-1]).upper()]
                    gp.source_for_cc(cc)
                    unit.set_assign(i, effect, cc)
                    print(f"  ASSIGN {i + 1}: CC {cc} switches {effect}")
                except (ValueError, IndexError, KeyError):
                    print("  assign <1-16> <effect> <CC 1-31 or 64-95>")
            elif word == "show":
                print(f"  patch {unit.patch}: {unit.name}, reports {'on' if unit.notify else 'off'}")
                for i, slot in enumerate(unit.assigns):
                    if slot:
                        effect, cc = slot
                        print(f"  ASSIGN {i + 1:2}: CC {cc:3} -> {effect:12}"
                              f" {'on' if unit.effects[effect] else 'off'}")
                print(f"  questions answered: {unit.requests}")
            else:
                print("  patch <n> [name] | fx <effect> | assign <n> <effect> <cc> | show | quit")
                print("  effects: " + ", ".join(name for name, _, _ in gp.EFFECTS))
            unit.poll(0.05)


if __name__ == "__main__":
    raise SystemExit(main())
