#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write a configuration as a page to print: each bank's switches laid out as
on the pedal, with their labels and what each press sends, the setlist with
its tempos, the expression pedals and the combinations.

    python3 Cheat_Sheet.py my-config.csv            # writes my-config.html
    python3 Cheat_Sheet.py my-config.csv --open     # and opens it, to print

Exit status: 0 when written, 2 when the configuration has a mistake.
"""
import argparse
import os
import sys
import webbrowser

from lib.cheatSheet import cheat_sheet
from lib.configCsv import read_config_csv


def device(text: str):
    channel, sep, name = text.partition("=")
    if not sep or not channel.strip().isdigit() or not name.strip():
        raise argparse.ArgumentTypeError("as CHANNEL=NAME, e.g. 2=\"Fender Tone Master Pro\"")
    return channel.strip(), name.strip()


def main(args: argparse.Namespace) -> int:
    try:
        page = cheat_sheet(read_config_csv(args.config), dict(args.device or []))
    except (OSError, ValueError, KeyError) as e:
        print(f"ERROR: {e}")
        return 2
    out = args.output or os.path.splitext(args.config)[0] + ".html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Written {out}: open it in a browser and print it.")
    if args.open:
        webbrowser.open("file://" + os.path.abspath(out))
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Write a configuration CSV as a cheat sheet to print, in HTML.")
    p.add_argument("config", help="the configuration CSV")
    p.add_argument("-o", "--output", help="the page to write; defaults to the CSV's name with .html")
    p.add_argument("--device", action="append", type=device, metavar="CHANNEL=NAME",
                   help="the device on a channel, from the configurators' Device menu, when the configuration "
                        "does not say it by itself; can be given more than once")
    p.add_argument("--open", action="store_true", help="open the page in the browser")
    sys.exit(main(p.parse_args()))
