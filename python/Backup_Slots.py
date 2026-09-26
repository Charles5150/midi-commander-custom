#! env python3
# -*- coding: utf-8 -*-
"""Back up every configuration slot of the Midi Commander at once, or restore them.

    Backup_Slots.py backup [folder]
    Backup_Slots.py restore folder [--yes]

A backup is a folder holding one CSV per slot that holds a configuration,
slot1.csv to slot4.csv, in the same format as Flash_to_CSV.py writes, plus a
backup.txt saying when it was made and what was in each slot. Any of the CSVs
can be opened in the configurator or flashed on its own with CSV_to_Flash.py.

Restoring writes each slotN.csv back to slot N, then restarts the pedal once.
Slots with no file in the backup are left as they are.
"""
import argparse
import datetime
import os
import re
import sys

from lib.configCsv import read_config_csv
from lib.midiDevice import (
    SYSEX_CMD_RESET,
    CONFIG_SLOTS,
    DeviceNotFound,
    DeviceTimeout,
    MidiCommander,
)
from lib.slotIO import FlashWriteError, SlotError, pack_sections, read_image, save_csv, select_slot, write_image

SLOT_FILE = re.compile(r"^slot([1-9])\.csv$", re.IGNORECASE)


def slot_path(folder: str, slot: int) -> str:
    """The file of a slot, 0-3, in a backup folder."""
    return os.path.join(folder, f"slot{slot + 1}.csv")


def slot_files(folder: str) -> dict:
    """{slot (0-3): path} for every slotN.csv of a backup folder."""
    found = {}
    for name in sorted(os.listdir(folder)):
        m = SLOT_FILE.match(name)
        if m and 1 <= int(m.group(1)) <= CONFIG_SLOTS:
            found[int(m.group(1)) - 1] = os.path.join(folder, name)
    return found


def backup(args: argparse.Namespace) -> int:
    folder = args.folder or datetime.datetime.now().strftime("midi-commander-backup-%Y%m%d-%H%M%S")
    try:
        with MidiCommander() as dev:
            try:
                version = dev.get_version()
            except DeviceTimeout:
                print("The device did not answer the version query. Its firmware predates "
                      "configuration read-back; flash artifacts/dfu/platformio-latest.dfu first.")
                return 2
            print(f"Device firmware: {version}")

            _, active, valid = select_slot(dev, None)
            if not valid:
                print("The pedal holds no configuration to back up")
                return 4

            os.makedirs(folder, exist_ok=True)
            saved = []
            for slot in valid:
                select_slot(dev, slot)
                print(f"Reading configuration slot {slot + 1}")
                data, image = read_image(dev, version)
                name = save_csv(slot_path(folder, slot), data, image,
                                note=f"Backup of slot {slot + 1}")
                saved.append((slot, name))
                print(f"  saved '{name}' to {slot_path(folder, slot)}")

            # Leave the pedal pointing at the slot it is running
            select_slot(dev, None)
    except DeviceNotFound as e:
        print(f"No matching MIDI device found: {e}")
        return 1
    except DeviceTimeout as e:
        print(f"Device stopped responding: {e}")
        return 3
    except SlotError as e:
        print(f"ERROR: {e}")
        return 1

    with open(os.path.join(folder, "backup.txt"), "w", encoding="utf-8") as f:
        f.write(f"Midi Commander backup, {datetime.datetime.now():%Y-%m-%d %H:%M}\n")
        f.write(f"Firmware {version}, running slot {active + 1}\n\n")
        names = dict(saved)
        for slot in range(CONFIG_SLOTS):
            f.write(f"Slot {slot + 1}: " + (f"'{names[slot]}'" if slot in names else "empty") + "\n")

    print(f"Backed up {len(saved)} configuration(s) to {folder}")
    return 0


def restore(args: argparse.Namespace) -> int:
    if not os.path.isdir(args.folder):
        print(f"ERROR: {args.folder} is not a folder")
        return 1
    files = slot_files(args.folder)
    if not files:
        print(f"ERROR: {args.folder} holds no slot1.csv to slot{CONFIG_SLOTS}.csv")
        return 1

    # Check every file before touching the pedal, so a bad one cannot leave a
    # restore half done
    packed = {}
    for slot, path in files.items():
        try:
            sections = read_config_csv(path)
            packed[slot] = pack_sections(sections)
        except Exception as e:  # noqa: BLE001
            print(f"ERROR: {path}: {e}")
            return 1
        name = sections["Global_Settings"].set_index("Label")["Value"].get("ConfigName", "")
        print(f"Slot {slot + 1}: '{str(name).strip()}' from {path}")
    untouched = [s + 1 for s in range(CONFIG_SLOTS) if s not in files]
    if untouched:
        print("Left as they are: slot " + ", ".join(str(s) for s in untouched))

    if not args.yes:
        ans = input("Overwrite these slots on the pedal? (y/N) ").lower().strip()
        if ans != "y":
            return 1

    try:
        with MidiCommander() as dev:
            for slot, (config, image) in packed.items():
                target, _, _ = select_slot(dev, slot)
                print(f"Writing configuration slot {target + 1}")
                write_image(dev, config, image, log=lambda m: print(f"  {m}"))
            print("Finished, resetting device...")
            dev.send([SYSEX_CMD_RESET])
    except DeviceNotFound as e:
        print(f"No matching MIDI device found: {e}")
        return 1
    except DeviceTimeout as e:
        print(f"Device stopped responding: {e}")
        return 3
    except SlotError as e:
        print(f"ERROR: {e}")
        return 1
    except FlashWriteError as e:
        print(f"ERROR: {e}. That slot is incomplete: restore it again.")
        return 4

    print(f"Restored {len(packed)} configuration(s)")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Back up all the configuration slots of the Midi Commander into a "
        "folder, one CSV per slot, or write such a folder back to the pedal.")
    sub = p.add_subparsers(dest="command", required=True)
    b = sub.add_parser("backup", help="Read every slot holding a configuration into a folder")
    b.add_argument("folder", nargs="?",
                   help="Folder to create; defaults to midi-commander-backup-<date>-<time>")
    r = sub.add_parser("restore", help="Write the slotN.csv files of a folder back to the pedal")
    r.add_argument("folder", help="Folder made by 'backup'")
    r.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    a = p.parse_args()
    sys.exit(backup(a) if a.command == "backup" else restore(a))
