#! env python3
# -*- coding: utf-8 -*-
"""Read the configuration currently stored on the Midi Commander into a CSV.

The CSV uses the same layout as the GUI configurator and CSV_to_Flash.py, so
it can be edited and flashed back unchanged.

Requires firmware 0.2 or later (SysEx READ_FLASH support).
"""
import argparse
import sys

import lib.binaryUnpacker as unpacker
from lib.configCsv import write_config_csv
from lib.midiDevice import CONFIG_SLOTS, DeviceNotFound, DeviceTimeout, MidiCommander


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
                target, active, valid = dev.select_slot(
                    None if args.slot is None else args.slot - 1)
                if args.slot is not None and target != args.slot - 1:
                    print(f"ERROR: the device did not accept slot {args.slot}")
                    return 1
                if target not in valid:
                    print(f"Configuration slot {target + 1} holds no configuration")
                    return 4
                print(f"Reading configuration slot {target + 1} "
                      f"(the pedal is running slot {active + 1})")
            except DeviceTimeout:
                if args.slot not in (None, 1):
                    print("ERROR: this firmware has a single configuration; "
                          "slots need 0.24 or later")
                    return 1

            data = dev.read_settings(unpacker.CONFIG_SIZE, progress)
    except DeviceNotFound as e:
        print(f"No matching MIDI device found: {e}")
        return 1
    except DeviceTimeout as e:
        print(f"Device stopped responding: {e}")
        return 3

    (df_global, df_banks, df_buttons, df_long, df_exp,
     df_enter, df_sysex, df_bank_switch, df_setlist) = unpacker.unpack_config(data)
    write_config_csv(
        args.output,
        df_global,
        df_banks,
        df_buttons,
        note="Read from device",
        df_long_press=df_long,
        df_expression=df_exp,
        df_bank_enter=df_enter,
        df_sysex=df_sysex,
        df_bank_switch=df_bank_switch,
        df_setlist=df_setlist,
    )

    name = df_global.loc[df_global["Label"] == "ConfigName", "Value"].iloc[0]
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
