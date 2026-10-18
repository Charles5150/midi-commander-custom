#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Try the pedal's switches, LEDs and expression jacks, before a gig.

    python3 python/Self_Test.py [--seconds 60]

While it runs (firmware 1.40 or later) the switches only count: press each
of the ten a few times, as on stage, and nothing is sent and no toggle
changes. The LEDs light one after the other and then all together; watch for
one that stays dark. Sweep each expression pedal slowly heel to toe and back.
Ctrl+C, or the seconds running out, ends it and says what it found: a switch
that bounces (fires twice from one press), one that is stuck down, a pot
that jumps. The pedal goes back to normal by itself a few seconds after the
test stops asking, even if the computer goes away.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.midiDevice import DeviceNotFound, DeviceTimeout, MidiCommander  # noqa: E402
from lib.selfTest import Tally, led_mask  # noqa: E402

POLL_S = 0.06


def run(dev, seconds, out=print):
    tally = Tally()
    start = time.monotonic()
    try:
        while seconds is None or time.monotonic() - start < seconds:
            answer = dev.self_test(True, led_mask(time.monotonic() - start))
            for i in tally.add(answer):
                out(tally.line(i))
            tally.add_pedals(dev.get_pedals())
            time.sleep(POLL_S)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            dev.self_test(False)
        except DeviceTimeout:
            pass                    # it ends by itself in a few seconds
    return tally


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seconds", type=float, default=None, help="end after this long (default: Ctrl+C)")
    args = parser.parse_args()
    try:
        with MidiCommander() as dev:
            if not dev.firmware_at_least(1, 40):
                print("The self-test needs firmware 1.40 or later: update it with Update_Firmware.py.")
                return 2
            print("Press each switch a few times, sweep the expression pedals slowly, watch the LEDs. "
                  "Ctrl+C when done.")
            tally = run(dev, args.seconds)
    except DeviceNotFound as e:
        print(e)
        return 1
    except DeviceTimeout:
        print("The pedal stopped answering.")
        return 2
    print()
    for line in tally.report():
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
