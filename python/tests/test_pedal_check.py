"""The expression pedal checker run on a calibration sweep."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import roundtrip_support  # noqa: E402,F401  (puts python/ on the path)
from lib.pedalCheck import check  # noqa: E402


def sweep(taper=lambda n: n, lo=100, hi=3950, steps=40, sweeps=2, rest=8):
    """Readings every 60 ms of a pedal swept at an even speed heel to toe and
    back, resting a little at each end, with a few counts of noise."""
    out = []
    for _ in range(sweeps):
        path = [i / steps for i in range(steps + 1)]
        for n in [0.0] * rest + path + [1.0] * rest + path[::-1]:
            out.append(round(lo + (hi - lo) * taper(n)) + (len(out) * 7) % 5 - 2)
    return out


class PedalCheckTest(unittest.TestCase):
    def test_a_good_pedal_has_nothing_to_say(self):
        self.assertEqual(check(sweep()), [])

    def test_a_pedal_using_half_the_range_is_still_fine(self):
        # Carlos's own pedal: its heel reads about 1990
        self.assertEqual(check(sweep(lo=1990, hi=4060)), [])

    def test_no_readings(self):
        self.assertIn("No reading", check([])[0])

    def test_an_empty_jack_or_a_guitar_cable(self):
        (w,) = check(sweep(lo=0, hi=3))
        self.assertIn("TRS", w)
        self.assertIn("reads nothing", w)

    def test_stuck_at_the_top(self):
        (w,) = check(sweep(lo=4080, hi=4093))
        self.assertIn("stays at the top", w)
        self.assertIn("polarity", w)

    def test_too_little_movement(self):
        (w,) = check(sweep(lo=1500, hi=1600))
        self.assertIn("only moved", w)

    def test_a_jump_from_nothing_to_most_of_the_way(self):
        # The polarity switch the wrong way: 0 for most of the travel, then 85 % on
        jumpy = sweep(taper=lambda n: 0.0 if n < 0.6 else 0.85 + 0.15 * (n - 0.6) / 0.4, lo=0, hi=4000)
        warnings = check(jumpy)
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("jumps from 0 % to 8", warnings[0])
        self.assertIn("polarity switch", warnings[0])

    def test_a_narrow_range(self):
        warnings = check(sweep(lo=1000, hi=2000))
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("only 24 %", warnings[0])

    def test_an_audio_taper_pot(self):
        warnings = check(sweep(taper=lambda n: n**3))
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("logarithmic", warnings[0])
        self.assertIn("Curve to Log", warnings[0])

    def test_a_reverse_taper_pot(self):
        warnings = check(sweep(taper=lambda n: 1 - (1 - n) ** 3))
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("Curve to Exp", warnings[0])

    def test_a_short_sweep_says_nothing_of_the_taper(self):
        self.assertEqual(check(sweep(taper=lambda n: n**3, steps=10, sweeps=1)), [])


if __name__ == "__main__":
    unittest.main()
