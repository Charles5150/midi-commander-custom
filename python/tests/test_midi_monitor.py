"""The MIDI monitor in lib/midiMonitor.py: kinds, readings, filters and rows.

Run from the repository root:

    python -m unittest python/tests/test_midi_monitor.py
"""

import os
import sys
import unittest

import mido

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lib.midiMonitor as mm  # noqa: E402
from lib import midiDevice  # noqa: E402

M = mido.Message


def entry(msg, t=0.0, port="Midi Commander"):
    return mm.Entry(t, port, msg)


class ReadingTest(unittest.TestCase):
    def test_channel_messages(self):
        self.assertEqual(mm.describe(M("control_change", control=7, value=100)), "CC 7 Volume = 100")
        self.assertEqual(mm.describe(M("control_change", control=74, value=3)), "CC 74 = 3")
        self.assertEqual(mm.describe(M("program_change", program=12)), "PC 12")
        self.assertEqual(mm.describe(M("note_on", note=60, velocity=90)), "Note On 60 (C4) velocity 90")
        self.assertEqual(mm.describe(M("pitchwheel", pitch=-200)), "Pitch Bend -200")
        self.assertEqual(mm.describe(M("pitchwheel", pitch=0)), "Pitch Bend centre")

    def test_a_note_on_at_velocity_zero_is_a_note_off(self):
        self.assertEqual(mm.describe(M("note_on", note=36, velocity=0)), "Note Off 36 (C2)")

    def test_channels_count_from_one(self):
        self.assertEqual(mm.channel(M("control_change", channel=15)), 16)
        self.assertIsNone(mm.channel(M("clock")))

    def test_mmc_and_song(self):
        self.assertEqual(mm.describe(M("sysex", data=[0x7F, 0x7F, 0x06, 0x02])), "MMC Play")
        self.assertEqual(mm.describe(M("song_select", song=3)), "Song Select 3")
        self.assertEqual(mm.describe(M("songpos", pos=16)), "Song Position 16")

    def test_the_pedal_and_the_kemper_are_named(self):
        state = M("sysex", data=[midiDevice.MIDI_MANUF_ID, midiDevice.SYSEX_RSP_GET_STATE, 1, 2])
        self.assertEqual(mm.describe(state), "Midi Commander: get state reply")
        beacon = M("sysex", data=[0x00, 0x20, 0x33, 0x02, 0x7F, 0x7E, 0x00, 0x40, 0x02, 0x00, 0x05])
        self.assertEqual(mm.describe(beacon), "Kemper")

    def test_raw_bytes(self):
        self.assertEqual(mm.raw(M("control_change", channel=2, control=74, value=100)), "B2 4A 64")
        long = mm.raw(M("sysex", data=[1] * 40))
        self.assertTrue(long.endswith("(42 bytes)"))
        self.assertEqual(long.count(" 01"), 23)


class KindTest(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(mm.kind(M("note_off")), "Notes")
        self.assertEqual(mm.kind(M("aftertouch")), "Bend & pressure")
        self.assertEqual(mm.kind(M("clock")), "Clock")
        self.assertEqual(mm.kind(M("start")), "System")
        self.assertEqual(mm.kind(M("sysex", data=[0x7F, 0x7F, 0x06, 0x01])), "SysEx")
        self.assertEqual(mm.kind(M("sysex", data=[midiDevice.MIDI_MANUF_ID, 69])), "Pedal replies")

    def test_every_kind_has_a_name_in_the_list(self):
        for msg in (M("note_on"), M("control_change"), M("program_change"), M("pitchwheel"),
                    M("sysex", data=[1]), M("stop"), M("clock"), M("sysex", data=[0x7D, 69])):
            self.assertIn(mm.kind(msg), mm.KINDS)


class FilterTest(unittest.TestCase):
    def test_clock_and_pedal_replies_start_hidden(self):
        f = mm.Filter()
        self.assertFalse(f.passes(entry(M("clock"))))
        self.assertFalse(f.passes(entry(M("sysex", data=[0x7D, 69, 0]))))
        self.assertTrue(f.passes(entry(M("control_change"))))
        self.assertTrue(f.passes(entry(M("sysex", data=[0x7F, 0x7F, 0x06, 0x02]))))

    def test_a_channel_leaves_out_other_channels_and_system_messages(self):
        f = mm.Filter(channel=3)
        self.assertTrue(f.passes(entry(M("control_change", channel=2))))
        self.assertFalse(f.passes(entry(M("control_change", channel=0))))
        self.assertFalse(f.passes(entry(M("start"))))

    def test_a_port(self):
        f = mm.Filter(port="DAW")
        self.assertTrue(f.passes(entry(M("program_change"), port="DAW")))
        self.assertFalse(f.passes(entry(M("program_change"))))


class LineTest(unittest.TestCase):
    def test_a_row(self):
        a = entry(M("control_change", channel=2, control=74, value=100), t=1.5)
        b = entry(M("program_change", program=4), t=1.75)
        row = mm.line(b, a)
        self.assertTrue(row.lstrip().startswith("1.750"))
        self.assertIn("+0.250", row)
        self.assertIn("ch 1", row)
        self.assertIn("PC 4", row)
        self.assertTrue(row.endswith("C0 04"))
        self.assertNotIn("+", mm.line(a))

    def test_a_long_port_name_is_cut(self):
        row = mm.line(entry(M("clock"), port="A very long port name, longer still"))
        self.assertIn("A very long port name…", row)


class MonitorTest(unittest.TestCase):
    def test_stamps_on_arrival(self):
        virt = mido.open_output("Monitor Test", virtual=True)
        try:
            ticks = iter([10.0, 10.5, 11.25])
            mon = mm.Monitor(names=["Monitor Test"], clock=lambda: next(ticks))
            self.assertEqual(mon.names, ["Monitor Test"])
            virt.send(M("control_change", control=1, value=2))
            virt.send(M("note_on", note=60, velocity=1))
            import time
            deadline = time.monotonic() + 2
            got = []
            while len(got) < 2 and time.monotonic() < deadline:
                got += mon.drain()
                time.sleep(0.01)
            mon.close()
        finally:
            virt.close()
        self.assertEqual([e.time for e in got], [0.5, 1.25])
        self.assertEqual([e.msg.type for e in got], ["control_change", "note_on"])
        self.assertEqual(mon.ports, [])


if __name__ == "__main__":
    unittest.main()
