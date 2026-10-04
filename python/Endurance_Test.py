#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Leave the pedal playing by itself for an hour and check it never drifts.

Meant for before a gig, and after a firmware change that touches timing,
USB or flash, next to Stress_Test.py: that one works the pedal as hard as it
can for a minute, this one at a gig's pace for as long as asked, to catch
hangs and slow leaks a minute cannot. The pedal on USB with the demo
configuration (demo-all-features.csv) active, and firmware 1.05 or later.

    python3 python/Endurance_Test.py              # an hour
    python3 python/Endurance_Test.py --minutes 180

It goes in rounds of about two minutes, under the traffic a computer sends
on a gig: a clock at 125 BPM, CCs and notes no button uses, a text on the
screen now and then and the pedal's state read every second, as the
configurator does. Each round:

- plays Stress_Test's sequence of presses, long and double presses, combos
  and bank changes, some from the computer's remote CCs: the pedal must send
  exactly what it sent the first time, in the same order, and end on the
  same banks and toggles (nothing missed, nothing doubled);
- sweeps expression pedal 1 heel to toe and back twice in bank 2: the CC
  must go all the way up and down, and what its toe switch and auto-engage
  press must be what they pressed in the first round;
- sets 120 BPM on the pedal's own clock and counts its clock for 10 s: the
  tempo must be 120 within 0.5 %;
- rests, clock and traffic only, then checks the pedal answers, has been on
  since the round before (no restart by the watchdog, which would otherwise
  go unnoticed: the pedal comes back as it was), is not asleep and has
  stack to spare, and that every SysEx sent was answered.

A line per round, and a summary at the end with how the stack held up.
"""
import argparse
import os
import random
import sys
import time

import mido

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.midiDevice import (  # noqa: E402
    SYSEX_CMD_GET_STATE,
    SYSEX_CMD_GET_VERSION,
    SYSEX_CMD_SET_PEDAL,
    SYSEX_CMD_SET_TEXT,
    SYSEX_RSP_GET_VERSION,
    DeviceNotFound,
    MidiCommander,
    text_sysex,
    version_at_least,
)
from Stress_Test import (  # noqa: E402
    FLOOD_CCS,
    FLOOD_NOTES,
    REMOTE_CHANNEL,
    TEXTS,
    Flood,
    Link,
    diff,
    is_demo,
    left_on,
    play,
    reset,
)

SWEEP_BANK = 2              # pedal 1 is CC 1 here, 20 at the heel to 100 at the toe
SWEEP_CC, SWEEP_MIN, SWEEP_MAX = 1, 20, 100
TEMPO_BANK = 6              # CLK starts the pedal's clock, holding SYNC sets 120 BPM
TEMPO_BPM = 120
TEMPO_SECONDS = 10
TEMPO_TOLERANCE = 0.005
STACK_MIN = 2048            # bytes of stack the pedal must always have had left

rounds = []                 # per round: the names of its checks that failed
checks = []


def check(name, ok, detail=""):
    checks.append(bool(ok))
    if not ok:
        rounds[-1].append(name)
        print(f"      FAIL  {name}" + (f"  {detail}" if detail != "" else ""), flush=True)


class GigTraffic(Flood):
    """What a computer sends the pedal on a gig, at a gig's pace; the clock
    can be stopped while the pedal's own tempo is measured."""

    clock = True

    def tick(self, now):
        link, rng = self.link, self.rng
        if self.clock and self.due("clock", now, 0.020):
            link.out(mido.Message("clock"))
        if self.due("feedback cc", now, 0.250):
            link.cc(1, rng.choice(FLOOD_CCS), rng.randrange(128))
        if self.due("feedback note", now, 0.500):
            n = rng.choice(FLOOD_NOTES)
            if n in self.notes_on:
                link.out(mido.Message("note_off", channel=0, note=n))
                self.notes_on.discard(n)
            else:
                link.out(mido.Message("note_on", channel=0, note=n, velocity=rng.randrange(1, 128)))
                self.notes_on.add(n)
        if self.due("thru", now, 0.300):
            link.cc(REMOTE_CHANNEL, rng.choice(FLOOD_CCS), rng.randrange(128))
        if self.due("text", now, 8.0):
            text = TEXTS[self.text % len(TEXTS)]
            self.text += 1
            link.sysex(SYSEX_CMD_SET_TEXT, raw=text_sysex(text, "info", "moment")[1:-1])
        if self.due("state", now, 1.0):
            link.sysex(SYSEX_CMD_GET_STATE)


def press(link, button, hold, traffic, after=0.3):
    link.press(button, True)
    link.wait(hold, traffic)
    link.press(button, False)
    link.wait(after, traffic)


def pedal(link, position):
    v = max(0, min(16383, round(position * 16383)))
    link.sysex(SYSEX_CMD_SET_PEDAL, 0, 1, v >> 7, v & 0x7F)


def sweep(link, traffic):
    """Pedal 1 heel to toe and back, twice, so its toe switch
    presses its button twice and leaves it as it was. Returns the CC 1
    values sent and everything else sent, in order."""
    link.midi = []
    for _ in range(2):
        for step in list(range(0, 41)) + list(range(40, -1, -1)):
            pedal(link, step / 40)
            link.wait(0.04, traffic)
        link.wait(1.2, traffic)          # at the heel: the filter settles, auto-engage lets go
    sent, link.midi = list(link.midi), []
    values = [k[3] for k in sent if k[0] == "control_change" and k[2] == SWEEP_CC]
    rest = [k for k in sent if not (k[0] == "control_change" and k[2] == SWEEP_CC)]
    return values, rest


def own_tempo(link, traffic):
    """The pedal's own clock at the 120 BPM SYNC sets, measured over 10 s
    with the computer's clock stopped. Returns the BPM, None if no clock."""
    traffic.clock = False
    link.bank(TEMPO_BANK)
    link.wait(1.0, traffic)              # it stops following the computer's clock
    press(link, "B", 0.9, traffic)       # hold SYNC: 120 BPM
    press(link, "2", 0.08, traffic, after=1.0)   # CLK: the clock on
    link.clocks = 0
    start = time.monotonic()
    link.wait(TEMPO_SECONDS, traffic)
    count, seconds = link.clocks, time.monotonic() - start
    press(link, "2", 0.08, traffic)      # CLK off
    link.midi = []
    traffic.clock = True
    return count / seconds * 60 / 24 if count else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--minutes", type=float, default=60, help="how long to run (default 60)")
    parser.add_argument("--rest", type=float, default=60, help="seconds of rest in each round (default 60)")
    parser.add_argument("--seed", type=int, default=None, help="seed for the traffic, to repeat a run")
    args = parser.parse_args()
    seed = args.seed if args.seed is not None else random.randrange(1 << 16)
    rng = random.Random(seed)
    print(f"seed {seed}")

    try:
        dev = MidiCommander().__enter__()
    except DeviceNotFound as e:
        sys.exit(f"The pedal is not on USB: {e}")
    started = time.monotonic()
    stack = []
    try:
        version = dev.get_version()
        if not version_at_least(version, 1, 5):
            sys.exit(f"Firmware {version}: this test needs 1.05 or later")
        for p in (0, 1):
            dev.set_pedal(p, 0.0)
        link = Link(dev)
        first = link.ask_state()
        if not is_demo(link):
            link.bank(first["bank"])
            sys.exit("This test runs on the demo configuration: load python/demo-all-features.csv first")
        print(f"firmware {version}, demo configuration, on for {first['uptime']} s, "
              f"{first['stack_free']} bytes of stack never used")

        traffic = GigTraffic(link, rng)
        reference = sweep_reference = None
        last_state, last_time = first, time.monotonic()
        link.sent_sysex.clear()
        link.answers.clear()
        end = started + args.minutes * 60
        while time.monotonic() < end or not rounds:
            rounds.append([])
            number = len(rounds)

            # The sequence; the first round is the reference for the rest
            sent, states = play(link, traffic)
            if reference is None:
                reference = (sent, states)
                check("the sequence leaves nothing on", not left_on(sent), left_on(sent))
            else:
                check("the sequence sends what it sent the first time", sent == reference[0], diff(reference[0], sent))
                check("the sequence leaves the same banks and toggles", states == reference[1], (reference[1], states))

            # Expression pedal 1
            link.bank(SWEEP_BANK)
            reset(link)
            link.wait(0.4, traffic)
            before = link.ask_state()
            values, rest = sweep(link, traffic)
            after = link.ask_state()
            ends = [values[i] for i in range(1, len(values) - 1) if values[i - 1] < values[i] > values[i + 1]]
            check("the pedal's CC goes all the way up and back, twice",
                  len(values) > 20 and len(ends) == 2 and min(ends) >= SWEEP_MAX - 2 and values[-1] <= SWEEP_MIN + 1,
                  f"{len(values)} values, tops {ends}, last {values[-1:]}")
            if sweep_reference is None:
                sweep_reference = rest
            check("its toe switch and auto-engage press what they pressed the first time",
                  rest == sweep_reference, diff(sweep_reference, rest))
            check("two sweeps leave the bank's toggles as they were",
                  before and after and before["toggles"] == after["toggles"], before and after and (before["toggles"], after["toggles"]))
            link.bank(SWEEP_BANK)
            reset(link)

            # The pedal's own tempo
            bpm = own_tempo(link, traffic)
            check(f"its own clock keeps {TEMPO_BPM} BPM", bpm and abs(bpm / TEMPO_BPM - 1) <= TEMPO_TOLERANCE,
                  f"{bpm:.2f}" if bpm else "no clock")

            # Rest, then how it is holding up
            link.bank(first["bank"])
            link.wait(args.rest, traffic)
            traffic.finish()
            link.wait(1.0)
            link.sysex(SYSEX_CMD_GET_VERSION)
            link.wait(0.3)
            st = link.ask_state()
            now = time.monotonic()
            check("still answers", link.answers[SYSEX_RSP_GET_VERSION] >= number and st is not None)
            if st:
                gap = (st["uptime"] - last_state["uptime"]) - (now - last_time)
                check("on all along: not restarted", not st["watchdog"] and abs(gap) <= 2,
                      f"watchdog {st['watchdog']}, uptime {last_state['uptime']} -> {st['uptime']} s in {now - last_time:.0f} s")
                check("not asleep, not in safe mode", not st["asleep"] and not st["safe_mode"], (st["asleep"], st["safe_mode"]))
                check(f"at least {STACK_MIN} bytes of stack left", st["stack_free"] >= STACK_MIN, st["stack_free"])
                stack.append(st["stack_free"])
                last_state, last_time = st, now
            unanswered = {c: (n, link.answers[c + 1]) for c, n in link.sent_sysex.items() if c and link.answers[c + 1] != n}
            check("every SysEx was answered", not unanswered, unanswered)

            minutes = (time.monotonic() - started) / 60
            print(f"round {number:3d}  {minutes:5.1f} min  {'FAIL' if rounds[-1] else 'OK  '}  {len(sent)} messages, "
                  f"tempo {bpm or 0:.2f}, stack {stack[-1] if stack else '?'}", flush=True)
        reset(link)
        link.bank(first["bank"])
        link.wait(0.4)
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        for p in (0, 1):
            dev.set_pedal(p, None)
        dev.__exit__(None, None, None)

    failed = [n for n, r in enumerate(rounds, 1) if r]
    print(f"\n{len(rounds) - len(failed)}/{len(rounds)} rounds OK, {sum(checks)}/{len(checks)} checks, "
          f"{(time.monotonic() - started) / 60:.0f} min (seed {seed})")
    if stack:
        print(f"stack never used: {first['stack_free']} bytes at the start, {stack[-1]} at the end")
    if failed:
        print("rounds that failed: " + ", ".join(map(str, failed)))
    sys.exit(0 if rounds and not failed else 1)


if __name__ == "__main__":
    main()
