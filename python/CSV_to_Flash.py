#! env python3
# -*- coding: utf-8 -*-
"""Load a configuration CSV onto the Midi Commander over USB MIDI SysEx."""
import argparse
import sys

from lib.configCsv import read_config_csv
from lib.midiDevice import (
    SYSEX_CMD_RESET,
    CONFIG_SLOTS,
    DeviceNotFound,
    DeviceTimeout,
    MidiCommander,
)
from lib.slotIO import FlashWriteError, SlotError, pack_sections, select_slot, write_image


def main(args: argparse.Namespace) -> int:
    try:
        sections = read_config_csv(args.csv_file)
        config, flash_contents = pack_sections(sections)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"Error parsing {args.csv_file}: {e}")
        return 1

    content_size = len(flash_contents)
    print(f"Flash content is {content_size} bytes = {content_size / 1024} kB")

    if not args.yes:
        ans = input("Continue? (y/N) ").lower().strip()
        if ans != "y":
            return 1

    def progress(done, total):
        print(f"Writing Flash Chunk: {done}/{total}")

    try:
        with MidiCommander() as dev:
            try:
                target, active, _ = select_slot(dev, None if args.slot is None else args.slot - 1)
            except SlotError as e:
                print(f"ERROR: {e}")
                return 1
            print(f"Writing configuration slot {target + 1} "
                  f"(the pedal is running slot {active + 1})")

            write_image(dev, config, flash_contents, log=print, progress=progress)

            print("Finished, resetting device...")
            dev.send([SYSEX_CMD_RESET])
    except DeviceNotFound as e:
        print(f"No matching MIDI device found: {e}")
        return 1
    except DeviceTimeout as e:
        print(f"Device stopped responding: {e}")
        return 3
    except FlashWriteError as e:
        print(f"ERROR: {e}. The slot is incomplete: flash it again.")
        return 4

    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="This is a tool to load a CSV configuration to the Midi Commander device. "
        "First, plug the Midi Commander to the USB port and turn it on. Then, run this tool "
        "by giving it as input the CSV file downloaded from the Google Spreadsheet configuration.",
    )
    p.add_argument(
        "csv_file",
        help="Path to a CSV file downloaded from the Google Spreadsheet configuration",
    )
    p.add_argument(
        "--slot",
        type=int,
        choices=range(1, CONFIG_SLOTS + 1),
        help="Configuration slot to write, 1-4. Defaults to the one the pedal is running.",
    )
    p.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    sys.exit(main(p.parse_args()))
