#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The names of a MainStage concert's patches, as the pedal's preset names.

    python3 MainStage_Names.py "My Concert.concert"                  list the patches
    python3 MainStage_Names.py "My Concert.concert" --csv my.csv     put their names in my.csv
    python3 MainStage_Names.py "My Concert.concert" --csv templates/MainStage.csv -o my.csv

Each patch's name goes in Preset_Names under its Program Change number, so
a `$N` in a label or a bank's info line shows the patch the pedal selected,
or the one MainStage says it is on. Names of other programs already in the
CSV are kept; --replace drops them. The concert is only read.

Exit status: 0 when done, 2 when the concert or the CSV cannot be read.
"""
import argparse
import sys

from lib.configCsv import read_config_csv, write_sections
from lib.mainstageConcert import concert_patches, preset_names, shown, with_names


def main(args: argparse.Namespace) -> int:
    try:
        patches = concert_patches(args.concert)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    names, notes = preset_names(patches)
    for p in patches:
        if p.program in names and names[p.program] == p.name:
            where = f"{p.set} / " if p.set else ""
            print(f"PC {p.program:3}  {shown(p.name):8}  {where}{p.name}")
    for note in notes:
        print(f"note: {note}")
    if not names:
        print("no patch has a Program Change: Edit > Reset Program Change Numbers in MainStage gives them one")
    if not args.csv:
        return 0
    try:
        sections = read_config_csv(args.csv)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    sections["Preset_Names"] = with_names(sections.get("Preset_Names"), names, args.replace)
    out = args.output or args.csv
    write_sections(out, sections, f"Preset names from {args.concert}")
    print(f"{len(names)} names written to {out}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A MainStage concert's patch names, as the pedal's preset names.")
    parser.add_argument("concert", help="the .concert folder")
    parser.add_argument("--csv", help="the configuration CSV to put the names in")
    parser.add_argument("-o", "--output", help="write to this CSV instead of changing --csv")
    parser.add_argument("--replace", action="store_true", help="drop the names of other programs")
    sys.exit(main(parser.parse_args()))
