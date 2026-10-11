"""What a calibration sweep says about the expression pedal in the jack.

The configurator reads the jack's raw value (0-4095) every 60 ms or so while
the pedal is swept; check() looks at those readings for the classic faults and
says, in plain words, what to change.
"""

FULL = 4095
NOISE = 12          # a smaller step is a pedal at rest
STUCK = 200         # a sweep that moves less than this did not reach the jack
LOW_END = 150       # a jack reading below this has nothing at the other end
TOP_END = FULL - 150
NARROW = FULL * 35 // 100
JUMP = 40           # a gap this wide in % of the travel, never landed in, is a jump
MIN_MOVING = 30     # readings in motion needed to judge the pot's taper
TAPER = 2.5         # how much one end may crowd the other on a linear pot


def _moving(samples):
    """The readings taken while the pedal was moving."""
    return [b for a, b in zip(samples, samples[1:]) if abs(b - a) > NOISE]


def _gap(samples, lo, hi):
    """The widest stretch between lo and hi no reading landed in, crossed at
    least twice: (bottom, top, crossings), or None."""
    seen = sorted(set(samples))
    best = None
    for a, b in zip(seen, seen[1:]):
        if best is None or b - a > best[1] - best[0]:
            best = (a, b)
    if best is None or 100 * (best[1] - best[0]) < JUMP * (hi - lo):
        return None
    a, b = best
    crossings = sum(1 for x, y in zip(samples, samples[1:]) if min(x, y) <= a and max(x, y) >= b)
    return (a, b, crossings) if crossings >= 2 else None


def check(samples):
    """Plain-word warnings about a sweep's readings, the worst first; empty
    when the pedal looks right."""
    if not samples:
        return ["No reading came from the pedal: connect it and try again."]
    lo, hi = min(samples), max(samples)
    span = hi - lo
    if span < STUCK:
        if hi < LOW_END:
            return [
                "The jack reads nothing. Check that the pedal is plugged in with a stereo (TRS) cable: "
                "a guitar (TS) cable, or a pedal wired with tip and ring the other way round, reads as an empty jack."
            ]
        if lo > TOP_END:
            return [
                "The jack stays at the top whatever the pedal does. Its wiring does not match: "
                "set the pedal's polarity switch the other way, if it has one, or check the cable is stereo (TRS)."
            ]
        return [f"The pedal only moved {span} counts. Move it over its full range and try again."]

    warnings = []
    gap = _gap(samples, lo, hi)
    if gap:
        a, b, _ = gap
        warnings.append(
            f"The pedal jumps from {100 * (a - lo) // span} % to {100 * (b - lo) // span} % of its travel "
            "without passing in between. If you swept it slowly, its wiring does not match the jack: "
            "set the pedal's polarity switch the other way (TRS / tip-ring), if it has one. "
            "A sweep that is too quick does the same: try again, slower."
        )
    if span < NARROW:
        warnings.append(
            f"The pedal uses only {100 * span // FULL} % of the jack's range. It works after calibrating, "
            "in coarser steps; if it has a minimum knob or a polarity switch, check how they are set."
        )
    if not gap:
        moving = _moving(samples)
        if len(moving) >= MIN_MOVING:
            low = sum(1 for v in moving if v < lo + span / 4)
            high = sum(1 for v in moving if v > hi - span / 4)
            if low >= TAPER * max(high, 1):
                warnings.append(
                    "Most of the travel sends low values: the pedal's pot looks logarithmic (audio taper). "
                    "Set Curve to Log to even it out."
                )
            elif high >= TAPER * max(low, 1):
                warnings.append(
                    "Most of the travel sends high values: the pedal's pot looks reverse logarithmic. "
                    "Set Curve to Exp to even it out."
                )
    return warnings
