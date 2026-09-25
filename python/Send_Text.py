#! env python3
# -*- coding: utf-8 -*-
"""Write on the Midi Commander's display from the computer (firmware 0.46).

    Send_Text.py "Sweet Child"                  whole top line, large, until the bank changes
    Send_Text.py --place info "Clean"           the small line right of the bank name
    Send_Text.py --place name --keep always SONG
    Send_Text.py --keep moment "Next: Intro"    for a moment only
    Send_Text.py --place line ""                back to what the bank shows
    Send_Text.py --hex "Sweet Child"            only print the SysEx message

--hex prints the message for a DAW or MainStage to send on its own; nothing
is sent to the pedal then.
"""
import argparse
import sys

from lib.midiDevice import TEXT_FITS, TEXT_KEEP, TEXT_MAX, TEXT_PLACES, DeviceNotFound, DeviceTimeout, MidiCommander, text_sysex


def main() -> int:
    parser = argparse.ArgumentParser(description="Write on the Midi Commander's display.")
    parser.add_argument("text", help="the text; empty gives the place back to the bank")
    parser.add_argument("--place", default="line", choices=list(TEXT_PLACES),
                        help="info (11 small chars), name (4 large), line (11 large, the default) "
                             "or small (18 small, the whole line); up to 32 go anywhere, and "
                             "what does not fit scrolls across")
    parser.add_argument("--keep", default="bank", choices=list(TEXT_KEEP),
                        help="bank: until the bank changes (the default); always: until "
                             "replaced; moment: a second and a half")
    parser.add_argument("--hex", action="store_true", help="print the SysEx message instead of sending it")
    args = parser.parse_args()

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


if __name__ == "__main__":
    sys.exit(main())
