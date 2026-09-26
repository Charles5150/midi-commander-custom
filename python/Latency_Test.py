#! env python3
# -*- coding: utf-8 -*-
"""How long the pedal takes from a switch going down to its first MIDI message.

The pedal times it itself (firmware 0.65): from the moment it sees a switch
change, or a press sent by the computer arrives, to the moment the first
message of that press is handed to USB. The computer cannot time that on its
own: its USB and MIDI stack add several milliseconds, on a Mac in steps of
about five, far more than the pedal's part. That round trip is shown too,
for comparison.

Run it with the pedal on USB and the demo configuration (demo-all-features.csv)
active, like the stress test:

    python3 python/Latency_Test.py [--presses 60]

Presses are sent over SysEx, so no foot is needed. The same presses are timed
with the line quiet and then under load: a running clock, an LFO and a step
sequencer sending, and a flood of incoming MIDI, texts and screen reads that
keep the display redrawing. Two kinds are timed: a toggle button (BLNK in
bank 2, CC 15) and Bank Up from bank 2, which draws the next bank of the
demo's setlist and sends the bank switch's own CC and that bank's program
change. The pedal is left on the bank it was on.
"""
import argparse
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Stress_Test as st  # noqa: E402
from lib.midiDevice import (  # noqa: E402
    SYSEX_CMD_GET_VERSION,
    SYSEX_RSP_GET_VERSION,
    DeviceNotFound,
    MidiCommander,
    version_at_least,
)

LIMIT_MS = st.PRESS_LIMIT_MS


def round_trip(link, count):
    """The computer's own share: a SysEx there and its answer back."""
    times = []
    for i in range(count):
        link.poll()
        before = link.answers[SYSEX_RSP_GET_VERSION]
        t0 = time.monotonic()
        link.sysex(SYSEX_CMD_GET_VERSION)
        while link.answers[SYSEX_RSP_GET_VERSION] == before and time.monotonic() - t0 < 1:
            link.poll()
        times.append((time.monotonic() - t0) * 1000)
        link.wait(0.02 + (i % 7) * 0.003)
    return times


def presses(link, count, flood=None):
    """count taps of BLNK in bank 2 and count Bank Ups from it, as the pedal timed them."""
    button, bank = [], []
    link.ask_latency()
    for i in range(count):
        jitter = (i % 7) * 0.004
        link.press("B", True)
        link.wait(0.06 + jitter, flood)
        link.press("B", False)
        link.wait(0.06, flood)
        got = link.ask_latency()
        button += got["samples"] if got else []
        link.press("UP", True)
        link.wait(0.05, flood)
        link.press("UP", False)
        link.wait(0.12 + jitter, flood)
        got = link.ask_latency()
        bank += got["samples"] if got else []
        link.bank(2)                   # back by MIDI, which is not a press
        link.wait(0.15, flood)
    return button, bank, {"button": count, "bank": count}


def describe(times):
    if not times:
        return "nothing measured"
    s = sorted(times)
    return (f"median {statistics.median(s):.2f} ms, 95% {s[int(len(s) * 0.95)]:.2f}, "
            f"max {s[-1]:.2f}  ({len(s)} presses)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--presses", type=int, default=40, help="presses of each kind in each run (default 40)")
    parser.add_argument("--seed", type=int, help="seed for the incoming flood (default random)")
    args = parser.parse_args()
    seed = args.seed if args.seed is not None else random.randrange(1 << 30)

    try:
        dev = MidiCommander()
        dev.__enter__()
    except DeviceNotFound as e:
        print(e)
        return 2
    try:
        version = dev.get_version()
        print(f"Firmware {version}, seed {seed}")
        if not version_at_least(version, 0, 65):
            print("The pedal times presses from firmware 0.65 on")
            return 2
        link = st.Link(dev)
        start = link.ask_state()
        if not st.is_demo(link):
            link.bank(start["bank"])
            print("This test runs on the demo configuration: load python/demo-all-features.csv first")
            return 2

        trip = round_trip(link, args.presses)
        print(f"The computer's round trip, for comparison: {describe(trip)}")

        link.bank(2)
        link.wait(0.4)
        st.reset(link)
        link.wait(0.5)                 # its redraws over before the quiet run
        button, bank, expected = presses(link, args.presses)
        print(f"Quiet   button: {describe(button)}")
        print(f"Quiet   bank:   {describe(bank)}")
        st.check("every quiet press timed", len(button) == expected["button"] and len(bank) == expected["bank"],
                 f"{len(button)}/{expected['button']} {len(bank)}/{expected['bank']}")
        st.check(f"quiet presses under {LIMIT_MS} ms", max(button + bank, default=99) < LIMIT_MS,
                 f"{max(button + bank, default=0):.2f}")

        st.own_streams(link, True)
        flood = st.Flood(link, random.Random(seed))
        lbutton, lbank, lexpected = presses(link, args.presses, flood)
        flood.finish()
        link.wait(0.3)
        st.own_streams(link, False)
        print(f"Loaded  button: {describe(lbutton)}")
        print(f"Loaded  bank:   {describe(lbank)}")
        st.check("every loaded press timed",
                 len(lbutton) == lexpected["button"] and len(lbank) == lexpected["bank"],
                 f"{len(lbutton)}/{lexpected['button']} {len(lbank)}/{lexpected['bank']}")
        st.check(f"loaded presses under {LIMIT_MS} ms", max(lbutton + lbank, default=99) < LIMIT_MS,
                 f"{max(lbutton + lbank, default=0):.2f}")

        st.reset(link)
        if start:
            link.bank(start["bank"])
            link.wait(0.4)
    finally:
        dev.__exit__(None, None, None)

    passed = sum(st.results)
    print(f"\n{passed}/{len(st.results)} OK")
    return 0 if passed == len(st.results) else 1


if __name__ == "__main__":
    sys.exit(main())
