#! env python3
# -*- coding: utf-8 -*-
"""Update the Midi Commander's firmware from a .dfu file.

    Update_Firmware.py midi-commander-custom-0.58.dfu
    Update_Firmware.py --yes ../artifacts/dfu/platformio-latest.dfu

With firmware 0.58 or later on the pedal nothing has to be held: the pedal is
asked to restart in DFU mode, flashed with dfu-util and waited for. Older
firmware has to be put in DFU mode by hand first (Bank Down and D held while
switching on); a pedal already in DFU mode is flashed straight away.

The configuration in the pedal is left as it is.
"""
import argparse
import sys

from lib.firmwareUpdate import UpdateError, check_image, update


def main() -> int:
    parser = argparse.ArgumentParser(description="Update the Midi Commander's firmware from a .dfu file.")
    parser.add_argument("dfu", help="the .dfu file, from a release or from the midi_dfu build")
    parser.add_argument("--yes", action="store_true", help="do not ask before flashing")
    args = parser.parse_args()

    try:
        size = check_image(args.dfu)
    except UpdateError as e:
        print(f"Not flashing {args.dfu}: {e}")
        return 1

    if not args.yes:
        answer = input(f"Flash {args.dfu} ({size} bytes) to the pedal? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Nothing done.")
            return 0

    try:
        version = update(args.dfu, log=lambda m: print(m, flush=True))
    except UpdateError as e:
        print(e)
        return 2

    if version is None:
        print("Flashed, but the pedal did not come back as a MIDI device. Unplug the USB "
              "cable and plug it in again.")
    else:
        print(f"Done: the pedal is running firmware {version}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
