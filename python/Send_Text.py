#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write on the Midi Commander's display from the computer (firmware 0.46).

    Send_Text.py "Sweet Child"                  whole top line, large, until the bank changes
    Send_Text.py --place info "Clean"           the small line right of the bank name
    Send_Text.py --place name --keep always SONG
    Send_Text.py --keep moment "Next: Intro"    for a moment only
    Send_Text.py --place line ""                back to what the bank shows
    Send_Text.py --hex "Sweet Child"            only print the SysEx message

    Send_Text.py --button A DLY                 button A's label, until the bank changes (1.34)
    Send_Text.py --button A --keep always DLY   until the computer changes it
    Send_Text.py --button A ""                  back to its own label
    Send_Text.py --button all ""                every button back to its own

    Send_Text.py --banner "The Band  612 345 678"   store the power on banner's own text (0.63)
    Send_Text.py --banner ""                    clear it: the banner shows the configuration's name
    Send_Text.py --banner                       print the text the pedal holds

--hex prints the message for a DAW or MainStage to send on its own; nothing
is sent to the pedal then.

The banner's text belongs to the pedal, not to a configuration: it stays
whatever configuration is loaded and through firmware updates, and shows
when Boot_Banner is on.
"""
import argparse
import sys

from lib.midiDevice import (BANNER_TEXT_MAX, LABEL_KEEP, LABEL_MAX, TEXT_FITS, TEXT_KEEP, TEXT_MAX, TEXT_PLACES,
                            DeviceNotFound, DeviceTimeout, MidiCommander, banner_sysex, label_sysex, text_sysex)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write on the Midi Commander's display.")
    parser.add_argument("text", nargs="?", help="the text; empty gives the place back to the bank")
    parser.add_argument("--place", default="line", choices=list(TEXT_PLACES),
                        help="info (11 small chars), name (4 large), line (11 large, the default) "
                             "or small (18 small, the whole line); up to 32 go anywhere, and "
                             "what does not fit scrolls across")
    parser.add_argument("--keep", default="bank", choices=list(TEXT_KEEP),
                        help="bank: until the bank changes (the default); always: until "
                             "replaced; moment: a second and a half")
    parser.add_argument("--button", metavar="BUTTON",
                        help=f"put the text on a button's label instead, up to {LABEL_MAX} characters: "
                             "1-4, A-D, Down, Up or all; --keep bank or always (firmware 1.34)")
    parser.add_argument("--hex", action="store_true", help="print the SysEx message instead of sending it")
    parser.add_argument("--banner", action="store_true",
                        help=f"store the text as the power on banner's own, up to {BANNER_TEXT_MAX} "
                             "characters (empty clears it); without a text print the one stored")
    args = parser.parse_args()

    if args.banner:
        return banner(args)
    if args.text is None:
        parser.error("the text is missing")
    if args.button is not None:
        return label(args)

    msg = text_sysex(args.text, args.place, args.keep)
    if len(args.text) > TEXT_MAX:
        print(f"Only the first {TEXT_MAX} characters are kept", file=sys.stderr)
    elif len(args.text) > TEXT_FITS[args.place]:
        print(f"{TEXT_FITS[args.place]} characters fit there: the text scrolls across once "
              "(firmware 0.61)", file=sys.stderr)
    if args.hex:
        print(" ".join(f"{b:02X}" for b in msg))
        return 0

    try:
        with MidiCommander() as dev:
            dev.set_text(args.text, args.place, args.keep)
    except DeviceNotFound as e:
        print(e)
        return 1
    except DeviceTimeout:
        print("The pedal did not answer. Writing on the display needs firmware 0.46.")
        return 2
    return 0


def label(args) -> int:
    try:
        msg = label_sysex(args.button, args.text, args.keep)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 3
    if len(args.text) > LABEL_MAX:
        print(f"A label shows up to {LABEL_MAX} characters, 4 in the ten cell layout", file=sys.stderr)
    if args.hex:
        print(" ".join(f"{b:02X}" for b in msg))
        return 0
    try:
        with MidiCommander() as dev:
            dev.set_label(args.button, args.text, args.keep)
    except DeviceNotFound as e:
        print(e)
        return 1
    except DeviceTimeout:
        print("The pedal did not answer. A button's label from the computer needs firmware 1.34.")
        return 2
    return 0


def banner(args) -> int:
    if args.text is not None:
        try:
            msg = banner_sysex(args.text)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 3
        if args.hex:
            print(" ".join(f"{b:02X}" for b in msg))
            return 0
    try:
        with MidiCommander() as dev:
            text = dev.get_banner() if args.text is None else dev.set_banner(args.text)
    except DeviceNotFound as e:
        print(e)
        return 1
    except DeviceTimeout:
        print("The pedal did not answer. The banner's own text needs firmware 0.63.")
        return 2
    except ValueError as e:
        print(e)
        return 3
    print(text if text else "(no text: the banner shows the configuration's name)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
