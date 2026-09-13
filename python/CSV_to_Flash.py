#! env python3
# -*- coding: utf-8 -*-
"""Load a configuration CSV onto the Midi Commander over USB MIDI SysEx."""
import argparse
import sys
import time
from math import ceil

from lib.configCsv import read_config_csv
from lib.configPacker import pack_config
from lib.midiDevice import (
    SYSEX_CMD_ERASE_FLASH,
    SYSEX_CMD_RESET,
    SYSEX_CMD_WRITE_FLASH,
    SYSEX_RSP_ERASE_FLASH,
    SYSEX_RSP_WRITE_FLASH,
    CONFIG_SLOTS,
    DeviceNotFound,
    DeviceTimeout,
    MidiCommander,
)

# Flash pages are 2 kB on the STM32F103RE (high density)
FLASH_PAGE_SIZE = 2048

# This needs to be in sync with FLASH_SETTINGS_NO_PAGES in
# firmware/Core/Inc/flash_midi_settings.h
ALLOWED_NUM_FLASH_PAGES = 12


def main(args: argparse.Namespace) -> int:
    try:
        sections = read_config_csv(args.csv_file)
        flash_contents = pack_config(sections)
    except Exception as e:  # noqa: BLE001
        print(f"Error parsing {args.csv_file}: {e}")
        return 1

    content_size = len(flash_contents)
    print(f"Flash content is {content_size} bytes = {content_size / 1024} kB")

    actual_num_flash_pages = ceil(content_size / FLASH_PAGE_SIZE)
    if actual_num_flash_pages > ALLOWED_NUM_FLASH_PAGES:
        print(
            f"ERROR: Your configuration requires {actual_num_flash_pages} "
            f"flash pages which is more than the {ALLOWED_NUM_FLASH_PAGES} pages "
            "allowed"
        )
        return 1

    if not args.yes:
        ans = input("Continue? (y/N) ").lower().strip()
        if ans != "y":
            return 1

    try:
        with MidiCommander() as dev:
            try:
                # Always choose explicitly: the target a previous read or write
                # selected stays until the pedal restarts, so "the active slot"
                # must be asked for, not assumed
                _, active, _ = dev.select_slot(None)
                wanted = active if args.slot is None else args.slot - 1
                target, active, _ = dev.select_slot(wanted)
                if args.slot is not None and target != args.slot - 1:
                    print(f"ERROR: the device did not accept slot {args.slot}")
                    return 1
                print(f"Writing configuration slot {target + 1} "
                      f"(the pedal is running slot {active + 1})")
            except DeviceTimeout:
                if args.slot not in (None, 1):
                    print("ERROR: this firmware has a single configuration; "
                          "slots need 0.24 or later")
                    return 1
            print("Erasing Flash Settings")
            dev.send([SYSEX_CMD_ERASE_FLASH, 0x42, 0x24])
            dev.wait_for_sysex(SYSEX_RSP_ERASE_FLASH, timeout=5.0)
            print("Erase Complete")

            no_chunks = ceil(content_size / 16)
            for x in range(no_chunks):
                print(f"Writing Flash Chunk: {x + 1}/{no_chunks}")
                chunk = flash_contents[x * 16 : (x + 1) * 16].ljust(16, b"\xff")
                data = [SYSEX_CMD_WRITE_FLASH, (x >> 7) & 0x7F, x & 0x7F]
                for byte in chunk:
                    data += [byte >> 4, byte & 0x0F]
                dev.send(data)
                dev.wait_for_sysex(SYSEX_RSP_WRITE_FLASH, timeout=2.0)
                time.sleep(0.005)

            print("Finished, resetting device...")
            dev.send([SYSEX_CMD_RESET])
    except DeviceNotFound as e:
        print(f"No matching MIDI device found: {e}")
        return 1
    except DeviceTimeout as e:
        print(f"Device stopped responding: {e}")
        return 3

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
