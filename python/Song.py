#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Save one bank of a configuration as a song file, and load a song file into
a bank of any configuration (lib/songFile.py says what goes with it).

    python3 Song.py save my-config.csv 12                      # writes bank 12 as <name>.song.csv
    python3 Song.py load my-config.csv HEROES.song.csv 5 -o new.csv

Exit status: 0 when written, 2 when the bank, the song or the configuration
has a mistake, or the song does not fit.
"""
import argparse
import os
import sys

from lib.configCsv import read_config_csv, write_sections
import lib.songFile as songs


def save(args) -> int:
    sections = read_config_csv(args.config)
    text = songs.save_song(sections, args.bank)
    out = args.output or songs.file_name(sections, args.bank)
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"Written {out}: bank {args.bank} as a song.")
    return 0


def load(args) -> int:
    sections = read_config_csv(args.config)
    loaded, notes = songs.load_song(sections, read_config_csv(args.song), args.bank)
    write_sections(args.output, loaded, f"Bank {args.bank} loaded from {os.path.basename(args.song)}")
    print(f"Written {args.output}: {os.path.basename(args.song)} in bank {args.bank}.")
    for n in notes:
        print(f"  - {n[0].upper()}{n[1:]}.")
    return 0


def main(args: argparse.Namespace) -> int:
    try:
        return args.run(args)
    except (OSError, ValueError, KeyError) as e:
        print(f"ERROR: {e}")
        return 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Save a bank as a song file, or load one into a bank.")
    sub = p.add_subparsers(required=True)
    s = sub.add_parser("save", help="save a bank of a configuration as a song file")
    s.add_argument("config", help="the configuration CSV")
    s.add_argument("bank", type=int, help="the bank, 0-31")
    s.add_argument("-o", "--output", help="the song file; defaults to the bank's name with .song.csv")
    s.set_defaults(run=save)
    l = sub.add_parser("load", help="load a song file into a bank of a configuration")
    l.add_argument("config", help="the configuration CSV")
    l.add_argument("song", help="the song file")
    l.add_argument("bank", type=int, help="the bank it replaces, 0-31")
    l.add_argument("-o", "--output", required=True, help="the configuration CSV to write")
    l.set_defaults(run=load)
    sys.exit(main(p.parse_args()))
