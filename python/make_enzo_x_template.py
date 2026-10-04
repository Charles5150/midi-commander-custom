#! env python3
# -*- coding: utf-8 -*-
"""Generate the Meris Enzo X template, python/templates/Enzo_X.csv.

The Enzo X has a fixed MIDI map, "MIDI CC TABLE" and "MIDI PC TABLE" in
its manual, so nothing has to be assigned on it: only its MIDI CHANNEL, in
its Globals. What the Meris X templates share is in lib/merisTemplate.py.

    python3 python/make_enzo_x_template.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib.merisTemplate import write  # noqa: E402

OUT = os.path.join(HERE, "templates", "Enzo_X.csv")

CC_MIX = "60"           # Mix, CC 60, on expression pedal 2


def main() -> int:
    return write(OUT, "Enzo X", CC_MIX, os.path.basename(__file__))


if __name__ == "__main__":
    sys.exit(main())
