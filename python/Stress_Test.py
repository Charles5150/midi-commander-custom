#! env python3
# -*- coding: utf-8 -*-
"""Work the pedal hard for about a minute and check it is still sound.

Meant to run before each release, next to the unit tests, with the pedal on
USB and the demo configuration (demo-all-features.csv) active. Nothing else is
needed: no foot, no DIN device.

    python3 python/Stress_Test.py

The same sequence of presses and bank changes is played twice: once with the
line quiet, as the reference, and once under a flood of incoming MIDI (clock,
CCs and notes the LED_Feedback has to look up, messages for the DIN output),
texts over SysEx and state and screen reads. Both runs must send exactly the
same messages, in the same order, and leave the same banks and toggles; no
note or momentary CC may be left on and every SysEx must get its answer.
A snapshot of 125 CCs must reach LED_Feedback whole. Then bursts of bank
changes, some spaced to land on the end of the previous screen update, must
end on the right bank with the right screen, every bank entered being left
again with its Bank Enter and Leave commands. Last, the pedal's own clock,
LFO and step sequence are started and the presses go on under the flood with
the pedal sending on its own too: it must keep answering and, from firmware
0.65, which times its presses itself, no press may take more than 5 ms from
the switch to its first MIDI message.

The screen is checked in the pedal's buffer, which is what GET_SCREEN reads;
the panel itself is only seen by eye, so look at it when the script ends.
"""
import argparse
import os
import random
import sys
import time
from collections import Counter

import mido

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.midiDevice import (  # noqa: E402
    MIDI_MANUF_ID,
    SCREEN_PARTS,
    SCREEN_PART_BYTES,
    SYSEX_CMD_GET_LATENCY,
    SYSEX_CMD_GET_SCREEN,
    SYSEX_CMD_GET_STATE,
    SYSEX_CMD_GET_VERSION,
    SYSEX_CMD_PRESS_BUTTON,
    SYSEX_CMD_SET_TEXT,
    SYSEX_RSP_GET_LATENCY,
    SYSEX_RSP_GET_SCREEN,
    SYSEX_RSP_GET_STATE,
    SYSEX_RSP_GET_VERSION,
    DeviceNotFound,
    MidiCommander,
    parse_latency,
    parse_state,
    switch_id,
    text_sysex,
    unpack7,
    version_at_least,
)

# What the demo configuration answers to (see make_demo_config.py)
BANK_CC = 32                 # Bank_Change_CC, any channel: the value is the bank
REMOTE_CHANNEL = 16          # Remote_Mode CC on channel 16 ...
REMOTE_FIRST = 102           # ... from CC 102: 1 2 3 4 A B C D Down Up
REMOTE_ORDER = ["1", "2", "3", "4", "A", "B", "C", "D", "DOWN", "UP"]
DEMO_LABELS = {              # a few banks' labels, to know the demo is loaded
    1: ["REC", "PLAY", "STOP", "UNDO", "TRK1", "TRK2", "TRK3", "TRK4"],
    2: ["NORM", "REVS", "ALWY", "MOMT", "DIM", "BLNK", "HALF", "NOFF"],
    9: ["C3", "E3", "G3", "HOLD", "1SEC", "UP", "DOWN", "BLIP"],
}
# Toggles the sequence changes, CCs and notes on channel 1: an off sent to
# LED_Feedback puts each back to off without anything being sent
FEEDBACK_CCS = [1, 2, 6, 7, 8, 9, 10, 11, 12, 14, 15, 18, 68]
FEEDBACK_NOTES = [72]
# Buttons that must not be left on: momentary CCs, back at their off value
MOMENTARY_CCS = {(0, 3): 0, (0, 4): 0, (0, 13): 0, (0, 16): 0}
# Banks the bursts go through: what entering and leaving each one sends
BURST_BANKS = [0, 1, 3, 5, 10, 11]
ENTER_SENDS = {3: [("program_change", 0, 0)], 11: [("control_change", 0, 59, 127)]}
LEAVE_SENDS = {11: [("control_change", 0, 59, 0)]}
# Incoming traffic for the loaded run: numbers no button of the demo uses
FLOOD_CCS = range(90, 100)
FLOOD_NOTES = range(100, 111)
# The most a press may take from the switch to its first MIDI message, as the
# pedal times it (firmware 0.65): the pass of the main loop it lands in, whose
# longest step is drawing a whole screen, about 2 ms
PRESS_LIMIT_MS = 5.0
TEXTS = ["STRESS", "LOAD 1234", "A LONGER TEXT THAT HAS TO SCROLL", "X", "MIDI FLOOD"]

results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("OK    " if ok else "FAIL  ") + name + (f"  {detail}" if detail != "" else ""), flush=True)


def key(msg):
    """A sent message as a comparable tuple; None for what is not compared."""
    if msg.type == "note_on" and msg.velocity == 0:
        return ("note_off", msg.channel, msg.note)
    if msg.type == "note_on":
        return ("note_on", msg.channel, msg.note, msg.velocity)
    if msg.type == "note_off":
        return ("note_off", msg.channel, msg.note)
    if msg.type == "control_change":
        return ("control_change", msg.channel, msg.control, msg.value)
    if msg.type == "program_change":
        return ("program_change", msg.channel, msg.program)
    if msg.type == "pitchwheel":
        return ("pitchwheel", msg.channel, msg.pitch)
    if msg.type == "sysex" and msg.data and msg.data[0] != MIDI_MANUF_ID:
        return ("sysex",) + tuple(msg.data)
    return None


class Link:
    """The pedal's ports, sending without waiting and keeping all that comes back."""

    def __init__(self, dev):
        self.dev = dev
        self.sent_sysex = Counter()
        self.answers = Counter()
        self.midi = []            # what the pedal sent, as key() tuples
        self.states = []          # GET_STATE answers, parsed
        self.screen = {}          # GET_SCREEN part -> bytes
        self.latency = None       # the last GET_LATENCY answer, parsed

    def out(self, msg):
        self.dev.outport.send(msg)

    def sysex(self, cmd, *data, raw=None):
        body = raw if raw is not None else [MIDI_MANUF_ID, cmd, *data]
        self.out(mido.Message("sysex", data=body))
        self.sent_sysex[cmd] += 1

    def cc(self, channel, number, value):
        self.out(mido.Message("control_change", channel=channel - 1, control=number, value=value))

    def bank(self, number):
        self.cc(1, BANK_CC, number)

    def press(self, button, down, remote=False):
        if remote:
            self.cc(REMOTE_CHANNEL, REMOTE_FIRST + REMOTE_ORDER.index(button), 127 if down else 0)
        else:
            self.sysex(SYSEX_CMD_PRESS_BUTTON, switch_id(button), 1 if down else 0)

    def poll(self):
        while True:
            msg = self.dev.inport.poll()
            if msg is None:
                return
            k = key(msg)
            if k is not None:
                self.midi.append(k)
                continue
            if msg.type != "sysex" or len(msg.data) < 2:
                continue
            rsp, data = msg.data[1], list(msg.data[2:])
            self.answers[rsp] += 1
            if rsp == SYSEX_RSP_GET_STATE:
                self.states.append(parse_state(data))
            elif rsp == SYSEX_RSP_GET_SCREEN and data:
                self.screen[data[0]] = unpack7(data[1:])
            elif rsp == SYSEX_RSP_GET_LATENCY:
                self.latency = parse_latency(data)

    def wait(self, seconds, flood=None):
        end = time.monotonic() + seconds
        while True:
            now = time.monotonic()
            if now >= end:
                break
            if flood:
                flood.tick(now)
            self.poll()
            time.sleep(0.001)
        self.poll()

    def ask_state(self, timeout=1.0):
        before = len(self.states)
        self.sysex(SYSEX_CMD_GET_STATE)
        end = time.monotonic() + timeout
        while len(self.states) == before and time.monotonic() < end:
            self.poll()
            time.sleep(0.002)
        return self.states[-1] if len(self.states) > before else None

    def ask_latency(self, clear=True, timeout=1.0):
        """What the pedal timed since the last clear (firmware 0.65), None if no answer."""
        self.latency = None
        self.sysex(SYSEX_CMD_GET_LATENCY, 1 if clear else 0)
        end = time.monotonic() + timeout
        while self.latency is None and time.monotonic() < end:
            self.poll()
            time.sleep(0.002)
        return self.latency

    def ask_screen(self, timeout=1.0):
        self.screen = {}
        for part in range(SCREEN_PARTS):
            self.sysex(SYSEX_CMD_GET_SCREEN, part)
            end = time.monotonic() + timeout
            while part not in self.screen and time.monotonic() < end:
                self.poll()
                time.sleep(0.002)
        if len(self.screen) != SCREEN_PARTS or any(len(v) != SCREEN_PART_BYTES for v in self.screen.values()):
            return None
        return b"".join(self.screen[p] for p in range(SCREEN_PARTS))


class Flood:
    """Incoming traffic at fixed rates, sent from the same loop as the sequence."""

    def __init__(self, link, rng):
        self.link = link
        self.rng = rng
        self.next = {}
        self.part = 0
        self.text = 0
        self.notes_on = set()
        self.sent = Counter()

    def due(self, name, now, every):
        if now < self.next.get(name, 0):
            return False
        self.next[name] = now + every
        self.sent[name] += 1
        return True

    def tick(self, now):
        link, rng = self.link, self.rng
        if self.due("clock", now, 0.020):              # 125 BPM, followed by Clock_Follow
            link.out(mido.Message("clock"))
        if self.due("feedback cc", now, 0.007):
            link.cc(1, rng.choice(FLOOD_CCS), rng.randrange(128))
        if self.due("feedback note", now, 0.011):
            n = rng.choice(FLOOD_NOTES)
            if n in self.notes_on:
                link.out(mido.Message("note_off", channel=0, note=n))
                self.notes_on.discard(n)
            else:
                link.out(mido.Message("note_on", channel=0, note=n, velocity=rng.randrange(1, 128)))
                self.notes_on.add(n)
        if self.due("thru", now, 0.015):               # not the remote CCs: only to DIN
            link.cc(REMOTE_CHANNEL, rng.choice(FLOOD_CCS), rng.randrange(128))
        if self.due("program", now, 0.050):
            link.out(mido.Message("program_change", channel=2, program=rng.randrange(128)))
        if self.due("text", now, 0.150):
            text = TEXTS[self.text % len(TEXTS)]
            self.text += 1
            link.sysex(SYSEX_CMD_SET_TEXT, raw=text_sysex(text, rng.choice(["info", "line", "small"]), "moment")[1:-1])
        if self.due("state", now, 0.040):
            link.sysex(SYSEX_CMD_GET_STATE)
        if self.due("screen", now, 0.025):
            link.sysex(SYSEX_CMD_GET_SCREEN, self.part)
            self.part = (self.part + 1) % SCREEN_PARTS

    def finish(self):
        for n in sorted(self.notes_on):
            self.link.out(mido.Message("note_off", channel=0, note=n))
        self.notes_on.clear()


# --- the sequence: (what, argument, seconds to wait afterwards)
def tap(button, hold=0.10, after=0.25, remote=False):
    return [("down", button, hold, remote), ("up", button, after, remote)]


def sequence():
    s = [("bank", 2, 0.35), ("reset", None, 0.3)]
    for b in ["1", "2", "3", "A", "B"]:              # toggles, one press each
        s += tap(b, after=0.20)
    s += tap("4", hold=0.20, after=0.45)             # momentary, waits out the double press
    s += tap("C", hold=0.20) + tap("D")              # momentary at 64, on without an off
    s += tap("1", hold=0.90, after=0.30)             # long press: scene, all on
    s += tap("4", hold=0.90, after=0.30)             # long press: scene, all off
    s += tap("4", hold=0.06, after=0.08) + tap("4", hold=0.06, after=0.45)   # double press: CC 18
    s += [("combo", ("3", "4"), 0.15, False), ("uncombo", ("3", "4"), 0.30, False)]   # tuner on
    s += tap("A", after=0.20, remote=True) + tap("B", after=0.20, remote=True)
    s += tap("2", hold=0.90, after=0.30, remote=True)  # a long press from the computer
    s += [("combo", ("3", "4"), 0.15, False), ("uncombo", ("3", "4"), 0.30, False)]   # tuner off
    s += tap("A", hold=0.90, after=0.30)             # scene: a mix
    s += [("bank", 9, 0.35)]
    s += tap("1", hold=0.20) + tap("2", hold=0.20, remote=True)
    s += tap("4") + tap("4") + tap("4")              # a toggled note, left on
    s += tap("B", hold=0.30) + tap("C", hold=0.30)   # pitch bend and back
    s += [("down", "3", 0.20, False), ("bank", 1, 0.30), ("up", "3", 0.30, False)]   # note held over a bank change
    for b in ["1", "2", "A", "B"]:
        s += tap(b, after=0.20)
    s += tap("C", after=0.20, remote=True) + tap("D", after=0.20, remote=True)
    s += tap("3", hold=0.15) + tap("4", hold=0.15, after=0.30)   # momentaries
    s += tap("4", hold=0.90, after=0.30)             # long press: CC 5
    s += tap("UP", after=0.45) + tap("DOWN", after=0.45, remote=True)   # Bank+MIDI, setlist
    s += [("bank", 2, 0.35)]
    s += tap("1") + tap("3") + tap("B", remote=True)
    s += tap("4", hold=0.06, after=0.08) + tap("4", hold=0.06, after=0.45)
    return s


def reset(link):
    """Every toggle the sequence touches off, through LED_Feedback: nothing is sent."""
    for n in FEEDBACK_CCS:
        link.cc(1, n, 0)
    for n in FEEDBACK_NOTES:
        link.out(mido.Message("note_off", channel=0, note=n))


def play(link, flood=None):
    """Play the sequence; returns what the pedal sent and the states it ended in."""
    link.midi = []
    for what, arg, after, *rest in sequence():
        remote = rest[0] if rest else False
        if what == "bank":
            link.bank(arg)
        elif what == "reset":
            reset(link)
        elif what in ("down", "up"):
            link.press(arg, what == "down", remote)
        elif what in ("combo", "uncombo"):
            link.press(arg[0], what == "combo")
            link.wait(0.010, flood)
            link.press(arg[1], what == "combo")
        link.wait(after, flood)
    if flood:
        flood.finish()
    link.wait(0.6)                                  # the pedal stops following the clock
    sent = list(link.midi)
    states = {}
    for bank in (1, 2, 9):
        link.bank(bank)
        link.wait(0.3)
        st = link.ask_state()
        states[bank] = st and (st["bank"], st["toggles"])
    link.midi = []
    return sent, states


def left_on(sent):
    """Notes still sounding and momentary CCs not back at rest at the end."""
    sounding = set()
    last = {}
    for k in sent:
        if k[0] == "note_on":
            sounding.add((k[1], k[2]))
        elif k[0] == "note_off":
            sounding.discard((k[1], k[2]))
        elif k[0] == "control_change":
            last[(k[1], k[2])] = k[3]
    stuck = [f"CC {c + 1}/{n}={v}" for (c, n), v in last.items() if MOMENTARY_CCS.get((c, n), v) != v]
    toggled = {(0, 72)}                              # the HOLD note toggles, and is left on on purpose
    stuck += [f"note {c + 1}/{n}" for c, n in sorted(sounding - toggled)]
    return stuck


def diff(a, b, limit=6):
    """Where two message lists first differ, for the report."""
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f"message {i}: {x} / {y}; {len(a)} vs {len(b)}"
    if len(a) != len(b):
        longer = a if len(a) > len(b) else b
        return f"{len(a)} vs {len(b)}, extra {longer[min(len(a), len(b)):][:limit]}"
    return ""


def snapshot(link):
    """A DAW recalling a mixer snapshot: 120 CCs in a row, then bank 2's
    toggles; each must end as the last message about it said."""
    link.bank(2)
    link.wait(0.4)
    got = []
    for want in (127, 0):
        for i in range(120):
            link.cc(1, FLOOD_CCS[i % len(FLOOD_CCS)], i)
        for n in (10, 11, 12, 14, 15):
            link.cc(1, n, want)
        link.wait(0.4)
        st = link.ask_state()
        got.append(st and [st["toggles"][i] for i in (0, 1, 2, 4, 5)])
    return got == [[True] * 5, [False] * 5], got


def bursts(link, rng, count):
    """Bank changes in quick succession; returns (name, ok, detail) per check.

    Changes that arrive before the pedal has handled the one before are
    merged, the last one winning, so not every bank asked for is entered:
    what is checked is that every bank entered is left again, with its Bank
    Enter and Leave commands, and that nothing else is sent.
    """
    # Each bank's settled screen, drawn with the line quiet
    reference = {}
    for bank in BURST_BANKS:
        link.bank(bank)
        link.wait(0.4)
        reference[bank] = link.ask_screen()
    link.midi = []
    current = BURST_BANKS[-1]
    asked = []
    spacings = [0.003, 0.010, 0.020] + [0.040 + i * 0.002 for i in range(15)]   # 40-68 ms: a screen takes ~50
    for _ in range(count):
        current = rng.choice([b for b in BURST_BANKS if b != current])
        asked.append(current)
        link.bank(current)
        link.wait(rng.choice(spacings))
    link.wait(0.5)
    sent = list(link.midi)
    known = {k for v in list(ENTER_SENDS.values()) + list(LEAVE_SENDS.values()) for k in v}
    stray = [k for k in sent if k not in known]
    # Bank 11 sends CC 59 on entering and leaving: on and off in turn, and
    # on at the end only when the bursts end on it; it started there, so the
    # first is an off
    cc59 = [k[3] for k in sent if k[:3] == ("control_change", 0, 59)]
    wanted = [0 if n % 2 == 0 else 127 for n in range(len(cc59))]
    paired = cc59 == wanted and (cc59[-1:] == [127]) == (current == 11) if cc59 else current != 11
    entered = sum(1 for b in asked if b == 3)
    pcs = sum(1 for k in sent if k[0] == "program_change")
    st = link.ask_state()
    # Three reads: a read can catch a frame half drawn, but only one
    screens = [link.ask_screen() for _ in range(3)]
    same = sum(s == reference[current] for s in screens)
    return [
        ("bursts: every bank entered is left, with its commands", paired and not stray and 0 < pcs <= entered,
         f"CC 59 {len(cc59)}x, PC 0 {pcs}x for bank 3 asked {entered}x" + (f", stray {stray[:5]}" if stray else "")),
        ("bursts: ends on the bank asked for", st and st["bank"] == current, st and (st["bank"], current)),
        ("bursts: the screen is the bank's, nothing left over", same >= 2, f"{same}/3 reads match the reference"),
    ]


def own_streams(link, on):
    """Start or stop, in bank 6, the pedal's own clock, the LFO under TREM and
    the arpeggio under STRT, which keep sending from the pedal whatever the
    bank. Ends on bank 2."""
    link.bank(6)
    link.wait(0.3)
    order = [("2", 0.08), ("A", 0.08), ("3", 1.2)]    # STRT held: the sequence
    for name, hold in (order if on else order[::-1]):
        link.press(name, True)
        link.wait(hold)
        link.press(name, False)
        link.wait(0.2)
    link.bank(2)
    link.wait(0.4)


def streams(link, rng, seconds, timed):
    """Presses and bank changes while the pedal sends on its own and the flood
    comes in: sending to the DIN output from both the main loop and the USB
    interrupt hung the pedal before 0.65. Yields (name, ok, detail)."""
    reset(link)
    own_streams(link, True)
    if timed:
        link.ask_latency()
    flood = Flood(link, rng)
    presses = 0
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        for name in ("B", "UP"):
            link.press(name, True)
            link.wait(0.06, flood)
            link.press(name, False)
            link.wait(0.1, flood)
            presses += 1
        link.bank(2)
        link.wait(0.12, flood)
    flood.finish()
    link.wait(0.3)
    got = link.ask_latency() if timed else None
    yield ("with its own clock, LFO and sequence running it still answers",
           got is not None if timed else link.ask_state() is not None, f"{presses} presses")
    if timed and got:
        yield (f"no press took more than {PRESS_LIMIT_MS:g} ms to send", 0 < got["count"] and got["max"] < PRESS_LIMIT_MS,
               f"slowest {got['max']:.2f} ms of {got['count']}")
    own_streams(link, False)
    reset(link)


def is_demo(link):
    """Whether the demo configuration is the one active, by a few banks' labels."""
    for bank, labels in DEMO_LABELS.items():
        link.bank(bank)
        link.wait(0.3)
        st = link.ask_state()
        if not st or st["labels"] != labels:
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--bursts", type=int, default=150, help="bank changes in the bursts (default 150)")
    parser.add_argument("--streams", type=float, default=15, help="seconds of presses with the pedal's own streams (default 15)")
    parser.add_argument("--seed", type=int, default=None, help="seed for the random parts, to repeat a run")
    args = parser.parse_args()
    seed = args.seed if args.seed is not None else random.randrange(1 << 16)
    rng = random.Random(seed)
    print(f"seed {seed}")
    started = time.monotonic()

    try:
        dev = MidiCommander().__enter__()
    except DeviceNotFound as e:
        sys.exit(f"The pedal is not on USB: {e}")
    try:
        version = dev.get_version()
        if not version_at_least(version, 0, 60):
            sys.exit(f"Firmware {version}: this test needs 0.60 or later")
        link = Link(dev)
        start = link.ask_state()
        if not is_demo(link):
            link.bank(start["bank"])
            sys.exit("This test runs on the demo configuration: load python/demo-all-features.csv first")
        print(f"firmware {version}, demo configuration, starting from bank {start['bank']}")
        link.midi = []
        link.sent_sysex.clear()
        link.answers.clear()

        # --- 1. the reference, then the same under load
        calm, calm_states = play(link)
        print(f"quiet: {len(calm)} MIDI messages out")
        flood = Flood(link, rng)
        t0 = time.monotonic()
        loaded, loaded_states = play(link, flood)
        print(f"loaded: {len(loaded)} MIDI messages out in {time.monotonic() - t0:.0f} s, with "
              + ", ".join(f"{v} {k}" for k, v in flood.sent.items()) + " coming in")
        check("under load it sends what it sends when quiet, in the same order", loaded == calm, diff(calm, loaded))
        check("under load it leaves the same banks and toggles", loaded_states == calm_states,
              "" if loaded_states == calm_states else (calm_states, loaded_states))
        check("quiet: nothing left on", not left_on(calm), left_on(calm))
        check("loaded: nothing left on", not left_on(loaded), left_on(loaded))
        link.wait(1.0)
        ok = all(link.answers[c + 1] == n for c, n in link.sent_sysex.items() if c)
        check("every SysEx was answered", ok,
              {c: (n, link.answers[c + 1]) for c, n in link.sent_sysex.items() if c and link.answers[c + 1] != n})

        ok, got = snapshot(link)
        check("LED_Feedback keeps up with a snapshot of 125 CCs", ok, got)

        # --- 2. bank changes in bursts
        for name, ok, detail in bursts(link, rng, args.bursts):
            check(name, ok, detail)

        # --- 3. the pedal sending on its own as well
        for name, ok, detail in streams(link, rng, args.streams, version_at_least(version, 0, 65)):
            check(name, ok, detail)

        # --- 4. still sound
        link.sysex(SYSEX_CMD_GET_VERSION)
        link.wait(0.3)
        check("still answers", link.answers[SYSEX_RSP_GET_VERSION] >= 1)
        st = link.ask_state()
        check("not asleep, not in safe mode", st and not st["asleep"] and not st["safe_mode"],
              st and (st["asleep"], st["safe_mode"]))

        # Back where it was, toggles of the banks played with off
        reset(link)
        link.bank(start["bank"])
        link.wait(0.4)
    finally:
        dev.__exit__(None, None, None)

    print(f"\n{sum(results)}/{len(results)} OK in {time.monotonic() - started:.0f} s (seed {seed})")
    print(f"The pedal is back on bank {start['bank']}: check its screen looks clean.")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
