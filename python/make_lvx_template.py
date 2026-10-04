#! env python3
# -*- coding: utf-8 -*-
"""Generate the Meris LVX template, python/templates/LVX.csv.

The LVX has a fixed MIDI map, "MIDI CC TABLE" and "MIDI PC TABLE" in
its manual, so nothing has to be assigned on it: only its MIDI CHANNEL, in
its Globals. What the Meris X templates share is in lib/merisTemplate.py.

    python3 python/make_lvx_template.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib.merisTemplate import write  # noqa: E402

OUT = os.path.join(HERE, "templates", "LVX.csv")

CC_MIX = "1"           # Mix, CC 1, on expression pedal 2


def main() -> int:
    return write(OUT, "LVX", CC_MIX, os.path.basename(__file__), looper=True)


if __name__ == "__main__":
    sys.exit(main())
