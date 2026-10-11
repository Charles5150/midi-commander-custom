#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Say what changes between two configurations, or what writing one to the
pedal would change in its slot.

Exit status, as diff's: 0 when nothing changes, 1 when something does, 2 when
a configuration has a mistake, 3 when the pedal could not be read.
"""
import argparse
import os
import sys

from lib.configCsv import read_config_csv
from lib.configDiff import config_sections, diff, image_sections
from lib.midiDevice import CONFIG_SLOTS, DeviceNotFound, DeviceTimeout, MidiCommander
from lib.slotIO import SlotError, read_image, select_slot


def _config(path):
    return config_sections(read_config_csv(path))


def _read_slot(slot):
    """(slot number shown, sections or None when the slot is empty)."""
    # Left open: closing the input now and then hangs in CoreMIDI, so the
    # process ends with os._exit and the system closes the ports
    dev = MidiCommander().__enter__()
    version = dev.get_version()
    target, _, valid = select_slot(dev, None if slot is None else slot - 1)
    if target not in valid:
        return target + 1, None
    data, image = read_image(dev, version)
    return target + 1, image_sections(data, image)


def report(lines, empty_text):
    for line in lines:
        print(line)
    print(f"{len(lines)} change{'s' if len(lines) != 1 else ''}" if lines else empty_text)
    return 1 if lines else 0


def main(args: argparse.Namespace) -> int:
    try:
        new = _config(args.new if args.new else args.old)
        old = _config(args.old) if args.new else None
    except (ValueError, KeyError) as e:
        print(f"ERROR: {e}")
        return 2
    if args.new:
        return report(diff(old, new), "Nothing changes: both give the pedal the same configuration.")

    try:
        slot, old = _read_slot(args.slot)
    except DeviceNotFound as e:
        print(f"No matching MIDI device found: {e}")
        return 3
    except (DeviceTimeout, SlotError) as e:
        print(f"Could not read the pedal: {e}")
        return 3
    if old is None:
        print(f"Slot {slot} holds no configuration: writing puts all of it there.")
        return 1
    name = next((r["Value"] for r in old["Global_Settings"] if r["Label"] == "ConfigName"), "")
    lines = diff(old, new)
    if not lines:
        print(f"Slot {slot} holds \"{name}\", already exactly this configuration: writing changes nothing.")
        return 0
    print(f"Slot {slot} holds \"{name}\". Writing {args.old} to it changes:")
    return report(lines, "")


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Say what changes from one configuration CSV to another, in plain words. "
        "Given one CSV, compare it with a slot of the pedal: what writing it would change.",
    )
    p.add_argument("old", help="the configuration CSV to compare from, or the one to write")
    p.add_argument("new", nargs="?", help="the configuration CSV to compare with")
    p.add_argument(
        "--slot",
        type=int,
        choices=range(1, CONFIG_SLOTS + 1),
        help="With one CSV: the slot to compare with, 1-4. Defaults to the one the pedal is running.",
    )
    code = main(p.parse_args())
    sys.stdout.flush()
    os._exit(code)
