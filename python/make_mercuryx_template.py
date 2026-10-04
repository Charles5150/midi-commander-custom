#! env python3
# -*- coding: utf-8 -*-
"""Generate the Meris MercuryX template, python/templates/MercuryX.csv.

The MercuryX has a fixed MIDI map, "MIDI CC TABLE" and "MIDI PC TABLE" in
its manual, so nothing has to be assigned on it: only its MIDI CHANNEL, in
its Globals. What the Meris X templates share is in lib/merisTemplate.py.

    python3 python/make_mercuryx_template.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib.merisTemplate import write  # noqa: E402

OUT = os.path.join(HERE, "templates", "MercuryX.csv")

CC_MIX = "1"           # Mix, CC 1, on expression pedal 2


def main() -> int:
    return write(OUT, "MercuryX", CC_MIX, os.path.basename(__file__), tap=False)


if __name__ == "__main__":
    sys.exit(main())
