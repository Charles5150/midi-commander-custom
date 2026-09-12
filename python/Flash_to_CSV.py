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
from lib.midiDevice import DeviceNotFound, DeviceTimeout, MidiCommander


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

            data = dev.read_settings(unpacker.CONFIG_SIZE, progress)
    except DeviceNotFound as e:
        print(f"No matching MIDI device found: {e}")
        return 1
    except DeviceTimeout as e:
        print(f"Device stopped responding: {e}")
        return 3

    df_global, df_banks, df_buttons, df_long = unpacker.unpack_config(data)
    write_config_csv(
        args.output,
        df_global,
        df_banks,
        df_buttons,
        note="Read from device",
        df_long_press=df_long,
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
    sys.exit(main(p.parse_args()))
