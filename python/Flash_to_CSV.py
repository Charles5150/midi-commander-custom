#! env python3
# -*- coding: utf-8 -*-
"""Read the configuration currently stored on the Midi Commander into a CSV.

The CSV uses the same layout as the GUI configurator and CSV_to_Flash.py, so
it can be edited and flashed back unchanged.

Requires firmware 0.2 or later (SysEx READ_FLASH support).
"""
import argparse
import sys

from lib.midiDevice import CONFIG_SLOTS, DeviceNotFound, DeviceTimeout, MidiCommander
from lib.slotIO import SlotError, read_image, save_csv, select_slot


def main(args: argparse.Namespace) -> int:
    try:
        with MidiCommander() as dev:
            try:
                version = dev.get_version()
            except DeviceTimeout:
                print(
                    "The device did not answer the version query. Its firmware "
                    "predates configuration read-back; flash "
                    "artifacts/dfu/platformio-latest.dfu (0.2 or later) first."
                )
                return 2
            print(f"Device firmware: {version}")

            def progress(done, total):
                if done == total or done % 20 == 0:
                    print(f"Reading chunk {done}/{total}")

            try:
                target, active, valid = select_slot(dev, None if args.slot is None else args.slot - 1)
            except SlotError as e:
                print(f"ERROR: {e}")
                return 1
            if target not in valid:
                print(f"Configuration slot {target + 1} holds no configuration")
                return 4
            print(f"Reading configuration slot {target + 1} "
                  f"(the pedal is running slot {active + 1})")

            data, image = read_image(dev, version, progress)
    except DeviceNotFound as e:
        print(f"No matching MIDI device found: {e}")
        return 1
    except DeviceTimeout as e:
        print(f"Device stopped responding: {e}")
        return 3

    name = save_csv(args.output, data, image)
    print(f"Saved configuration '{name}' ({len(data)} bytes) to {args.output}")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Read the configuration stored on the Midi Commander and save "
        "it as a CSV file. Plug the Midi Commander in, turn it on in normal mode "
        "and run this tool with the path of the CSV file to create."
    )
    p.add_argument("output", help="Path of the CSV file to write")
    p.add_argument(
        "--slot",
        type=int,
        choices=range(1, CONFIG_SLOTS + 1),
        help="Configuration slot to read, 1-4. Defaults to the one the pedal is running.",
    )
    sys.exit(main(p.parse_args()))
