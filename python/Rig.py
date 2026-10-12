#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Make a starting configuration for what is on your board, from the device
templates: each device as its template's name and the MIDI channel it is set
to, the main one first (lib/rigWizard.py says how they are put together).

    python3 Rig.py HX_Stomp:1 TimeLine:2 -o my-rig.csv
    python3 Rig.py --list                       # the devices it knows

The others change preset with the main one; --no-follow leaves them be.

Exit status: 0 when written, 2 when a device or a channel has a mistake, or
the rig does not fit.
"""
import argparse
import sys

import lib.rigWizard as rig
from lib.configCsv import write_sections


def part(text: str, follow: bool) -> dict:
    name, _, channel = text.rpartition(":")
    if not name:
        raise ValueError(f"{text}: give a device as its template and its channel, as HX_Stomp:1")
    known = {t.lower(): t for t in rig.templates()}
    template = known.get(name.lower())
    if template is None:
        raise ValueError(f"there is no template {name}: python3 Rig.py --list shows them")
    return {"template": template, "sections": rig.load_template(template), "channel": channel, "follow": follow}


def main(args: argparse.Namespace) -> int:
    if args.list:
        for t in rig.templates():
            print(f"{t:16} {rig.title(t)}")
        return 0
    try:
        if not args.devices or not args.output:
            raise ValueError("give the devices and -o, the configuration CSV to write")
        sections, notes = rig.build_rig([part(d, not args.no_follow) for d in args.devices])
        write_sections(args.output, sections, "Made by Rig.py: " + " ".join(args.devices))
    except (OSError, ValueError, KeyError) as e:
        print(f"ERROR: {e}")
        return 2
    print(f"Written {args.output}.")
    for n in notes:
        print(f"  - {n[0].upper()}{n[1:]}.")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Make a starting configuration for the devices on your board.")
    p.add_argument("devices", nargs="*", help="TEMPLATE:CHANNEL, the main device first, up to "
                                              f"{rig.MAX_DEVICES}")
    p.add_argument("-o", "--output", help="the configuration CSV to write")
    p.add_argument("--no-follow", action="store_true", help="the other devices do not change preset with the banks")
    p.add_argument("--list", action="store_true", help="list the devices, as their templates are named")
    sys.exit(main(p.parse_args()))
