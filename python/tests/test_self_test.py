"""The hardware self-test: the SELF_TEST answer and what it says (firmware 1.40)."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from lib.midiDevice import parse_self_test  # noqa: E402
from lib.selfTest import Tally, led_mask, scratches  # noqa: E402


def answer(presses=None, bounces=None, down=()):
    presses = presses or [0] * 10
    bounces = bounces or [0] * 10
    mask = sum(1 << i for i in down)
    data = [v for pair in zip(presses, bounces) for v in pair] + [mask & 0x7F, mask >> 7]
    return parse_self_test(data)


class SelfTestTest(unittest.TestCase):
    def test_the_answer(self):
        a = answer([1, 2, 0, 0, 0, 0, 0, 0, 0, 9], [0, 1, 0, 0, 0, 0, 0, 0, 0, 0], down=(1, 9))
        self.assertEqual(a["presses"][:2], [1, 2])
        self.assertEqual(a["presses"][9], 9)
        self.assertEqual(a["bounces"][1], 1)
        self.assertEqual([i for i, d in enumerate(a["down"]) if d], [1, 9])
        with self.assertRaises(ValueError):
            parse_self_test([0] * 21)

    def test_counts_go_on_past_the_seven_bits(self):
        t = Tally()
        t.add(answer([120] + [0] * 9))
        changed = t.add(answer([5] + [0] * 9))
        self.assertEqual(t.presses[0], 133)
        self.assertEqual(changed, [0])
        self.assertEqual(t.add(answer([5] + [0] * 9)), [], "nothing new")

    def test_the_report(self):
        t = Tally()
        t.add(answer([20, 30] + [4] * 8, [0, 2] + [0] * 8, down=(9,)))
        t.add(answer([20, 30] + [4] * 7 + [0], [0, 2] + [0] * 8, down=(9,)))
        said = t.report()
        self.assertIn("Bank Up was down the whole time", said[0])
        self.assertIn("Switch 2 bounced 2 times in 30 presses", said[1])
        self.assertEqual(len(said), 2, "the rest pressed cleanly; a stuck switch is not 'not pressed'")
        quiet = Tally()
        quiet.add(answer())
        self.assertEqual(quiet.report()[-1], "Not pressed: 1, 2, 3, 4, A, B, C, D, Bank Down, Bank Up.")
        clean = Tally()
        clean.add(answer([3] * 10))
        self.assertEqual(clean.report(), ["Every switch pressed cleanly, with no bounce."])

    def test_a_scratchy_pot(self):
        sweep = list(range(0, 4000, 30))
        self.assertEqual(scratches(sweep), 0, "a slow sweep is no scratch")
        self.assertEqual(scratches([0, 4095, 0, 4095, 0, 4095]), 0, "a quick swing is not one either")
        self.assertEqual(scratches([0, 0, 4095, 4095, 4095]), 0, "nor heel to toe")
        self.assertEqual(scratches([2000, 2010, 2600, 2015, 2020, 1400, 2030, 2035]), 2)
        t = Tally()
        t.add(answer([1] * 10))
        for v in (2000, 2003, 2900, 2005, 2008):
            t.add_pedals([(v, 64), (100, 0)])
        self.assertIn("Expression 1 jumped and came straight back 1 time", t.report()[0])

    def test_the_leds_in_turn(self):
        self.assertEqual(led_mask(0), 1)
        self.assertEqual(led_mask(0.45), 2)
        self.assertEqual(led_mask(9 * 0.4 + 0.1), 1 << 9)
        self.assertEqual(led_mask(10 * 0.4 + 0.1), 0x3FF, "then all together")
        self.assertEqual(led_mask(11 * 0.4 + 0.1), 1, "and round again")


if __name__ == "__main__":
    unittest.main()
