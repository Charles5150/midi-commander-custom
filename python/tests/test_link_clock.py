"""Link_Clock (#198): an Ableton Link session's ticks as the MIDI clock the pedal follows."""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import Link_Clock  # noqa: E402
from lib.linkClock import CLOCK, CONTINUE, START, STOP, ClockBridge, Jitter, song_position  # noqa: E402

BAR = 96    # 4 beats of 24 clocks


def run_ticks(bridge, ticks, playing=False):
    out = []
    for t in ticks:
        out.extend(bridge.step(t, playing(t) if callable(playing) else playing))
    return out


class TestBridge(unittest.TestCase):
    def test_the_first_clock_waits_for_a_sixteenth_and_says_where_in_the_bar_it_is(self):
        b = ClockBridge(4)
        # Session beat 6.5 (tick 156) is bar 2, beat 3 and a half: 10 sixteenths in
        self.assertEqual(b.step(153), [])
        self.assertEqual(b.step(155), [])
        self.assertEqual(b.step(156), [song_position(10), CLOCK])
        self.assertEqual(b.step(157), [CLOCK])

    def test_joining_a_playing_session_continues_from_there(self):
        b = ClockBridge(4)
        self.assertEqual(b.step(BAR * 7 + 24, True), [song_position(4), CONTINUE, CLOCK])

    def test_play_starts_on_the_next_bar_and_stop_stops_at_once(self):
        b = ClockBridge(4)
        out = run_ticks(b, range(0, BAR * 2 + 2), lambda t: t >= 30)
        self.assertEqual(out[:2], [song_position(0), CLOCK])
        self.assertEqual(out.count(START), 1)
        # The Start goes before the bar's first clock: clocks 0..95 came first
        self.assertEqual(out.index(START), 1 + BAR)
        self.assertEqual(b.step(BAR * 2 + 2, False), [STOP, CLOCK])
        self.assertEqual(b.stop(), [])

    def test_a_late_wake_sends_the_clocks_it_missed(self):
        b = ClockBridge(4)
        b.step(0)
        self.assertEqual(b.step(4), [CLOCK] * 4)
        self.assertEqual(b.step(4), [], "woke twice for one tick")
        self.assertEqual(b.step(2), [], "a hair back")
        self.assertEqual(b.step(5), [CLOCK])
        self.assertEqual(b.step(-6), [song_position(15), CLOCK], "further back: the bar again")

    def test_a_jump_lines_the_bar_up_again(self):
        b = ClockBridge(4)
        b.step(0, True)
        out = b.step(BAR * 50 + 49, True)     # not on a sixteenth: wait
        self.assertEqual(out, [])
        self.assertEqual(b.step(BAR * 50 + 54, True), [song_position(9), CONTINUE, CLOCK])
        self.assertEqual(b.step(-BAR + 48, True), [song_position(8), CONTINUE, CLOCK], "the timeline went back")

    def test_quantum_three_and_no_transport(self):
        b = ClockBridge(3, transport=False)
        self.assertEqual(b.step(72 + 30, True), [song_position(5), CLOCK])
        out = run_ticks(b, range(103, 300), True)
        self.assertEqual(set(map(tuple, out)), {tuple(CLOCK)})
        self.assertEqual(b.stop(), [])

    def test_leaving_stops_a_playing_pedal(self):
        b = ClockBridge(4)
        b.step(0, True)
        self.assertEqual(b.stop(), [STOP])
        self.assertEqual(b.stop(), [])

    def test_song_position_bytes(self):
        self.assertEqual(song_position(200), [0xF2, 200 & 0x7F, 1])
        self.assertEqual(song_position(-3), [0xF2, 0, 0])
        with self.assertRaises(ValueError):
            ClockBridge(0)


class TestJitter(unittest.TestCase):
    def test_how_far_off_the_clocks_are(self):
        j = Jitter()
        self.assertEqual(j.summary()["clocks"], 0)
        step = 60 / (125 * 24)                  # 20 ms at 125 BPM
        for i, off in enumerate([0, 0.001, -0.001, 0, 0.003]):
            j.sent(i * step + off, 125)
        s = j.summary()
        self.assertEqual(s["clocks"], 4)
        self.assertAlmostEqual(s["max_ms"], 3.0, places=6)
        self.assertAlmostEqual(s["mean_ms"], (1 + 2 + 1 + 3) / 4, places=6)
        j.sent(5 * step + 2 * step, 125, clocks=2)  # two at once, a late wake
        self.assertEqual(j.summary()["clocks"], 5)


class FakeLink:
    """A session at a tempo, from a beat, playing from a given beat on."""

    def __init__(self, tempo, beat, play_from=None, peers=1):
        self.tempo, self.beat, self.play_from, self.num_peers = tempo, beat, play_from, peers
        self.playing = False
        self.now = 0.0

    async def sync(self, fraction):
        self.beat = (int(self.beat / fraction + 1e-9) + 1) * fraction
        self.now += fraction * 60 / self.tempo
        self.playing = self.play_from is not None and self.beat >= self.play_from
        return self.beat


class TestRun(unittest.TestCase):
    def test_the_loop_clocks_the_session_and_says_what_changes(self):
        link = FakeLink(100, 6.4, play_from=8)
        sent, said = [], []
        asyncio.run(Link_Clock.run(link, sent.append, ClockBridge(4), Jitter(), stats=1.0,
                                   say=said.append, ticks=24 * 6, clock=lambda: link.now))
        self.assertEqual(sent[0], song_position(10))
        self.assertIn(START, sent)
        self.assertEqual(sent.index(START), sent.index(CLOCK) + 36, "on beat 8, 36 clocks after beat 6.5")
        self.assertEqual(said[0], "100.0 BPM, stopped, 1 peer")
        self.assertIn("100.0 BPM, playing, 1 peer", said)
        self.assertTrue(any("0.00 ms off on average" in s for s in said), said)

    def test_the_pedal_port_and_a_chosen_one(self):
        names = ["IAC Driver Bus 1", "MIDI Commander Custom DIN", "MIDI Commander Custom Config",
                 "MIDI Commander Custom"]
        self.assertEqual(Link_Clock.pedal_output(names), "MIDI Commander Custom")
        self.assertEqual(Link_Clock.pedal_output(names[:3]), "MIDI Commander Custom Config")
        self.assertEqual(Link_Clock.pedal_output(names, "iac"), "IAC Driver Bus 1")
        self.assertIsNone(Link_Clock.pedal_output(names[:1]))


if __name__ == "__main__":
    unittest.main()
