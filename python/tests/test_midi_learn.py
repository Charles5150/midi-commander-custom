"""MIDI learn in lib/midiLearn.py: what a message that arrives fills in.

Run from the repository root:

    python -m unittest python/tests/test_midi_learn.py
"""

import os
import sys
import unittest

import mido

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lib.midiLearn as ml  # noqa: E402

EMPTY = {"CommandType": "", ml.CHANNEL: "", ml.NUMBER: "", ml.ON: "", ml.OFF: "", ml.VELOCITY: ""}


class LearnedFieldsTest(unittest.TestCase):
    def test_a_cc_on_an_empty_slot(self):
        out = ml.learned_fields(mido.Message("control_change", channel=2, control=74, value=127), EMPTY)
        self.assertEqual(
            (out["CommandType"], out[ml.CHANNEL], out[ml.NUMBER], out[ml.ON], out[ml.OFF]),
            ("CC", "3", "74", "127", "0"),
        )

    def test_a_cc_keeps_the_values_already_set(self):
        current = dict(EMPTY, CommandType="CC", **{ml.ON: "100", ml.OFF: "20", ml.NUMBER: "1"})
        out = ml.learned_fields(mido.Message("control_change", channel=0, control=11, value=63), current)
        self.assertEqual((out[ml.NUMBER], out[ml.ON], out[ml.OFF]), ("11", "100", "20"))

    def test_a_cc_at_zero_sends_127(self):
        out = ml.learned_fields(mido.Message("control_change", control=80, value=0), EMPTY)
        self.assertEqual(out[ml.ON], "127")

    def test_a_cc_on_a_ccinc_keeps_the_ccinc(self):
        current = dict(EMPTY, CommandType="CCInc", **{ml.ON: "0", ml.OFF: "1"})
        out = ml.learned_fields(mido.Message("control_change", channel=4, control=20, value=90), current)
        self.assertEqual((out["CommandType"], out[ml.CHANNEL], out[ml.NUMBER]), ("CCInc", "5", "20"))
        self.assertEqual((out[ml.ON], out[ml.OFF]), ("0", "1"))

    def test_a_pc_replaces_another_type(self):
        current = dict(EMPTY, CommandType="Note", **{ml.NUMBER: "60"})
        out = ml.learned_fields(mido.Message("program_change", channel=15, program=12), current)
        self.assertEqual((out["CommandType"], out[ml.CHANNEL], out[ml.NUMBER]), ("PC", "16", "12"))

    def test_a_pc_on_a_pcinc_sets_the_channel_only(self):
        current = dict(EMPTY, CommandType="PCInc", **{ml.NUMBER: "127"})
        out = ml.learned_fields(mido.Message("program_change", channel=1, program=5), current)
        self.assertEqual((out["CommandType"], out[ml.CHANNEL], out[ml.NUMBER]), ("PCInc", "2", "127"))

    def test_a_note(self):
        out = ml.learned_fields(mido.Message("note_on", channel=9, note=36, velocity=90), EMPTY)
        self.assertEqual((out["CommandType"], out[ml.CHANNEL], out[ml.NUMBER], out[ml.VELOCITY]),
                         ("Note", "10", "36", "90"))

    def test_a_pitch_bend(self):
        out = ml.learned_fields(mido.Message("pitchwheel", channel=0, pitch=-4096), EMPTY)
        self.assertEqual((out["CommandType"], out[ml.CHANNEL], out[ml.ON]), ("PB", "1", "-4096"))

    def test_a_cc_on_a_listen_sets_what_it_listens_for(self):
        current = dict(EMPTY, CommandType="Listen")
        out = ml.learned_fields(mido.Message("control_change", channel=0, control=22, value=1), current)
        self.assertEqual((out["CommandType"], out[ml.NUMBER], out[ml.ON], out[ml.OFF]),
                         ("Listen", "22", "1", "0"))

    def test_other_fields_are_kept(self):
        current = dict(EMPTY, CommandType="CC", **{"Toggle_(CC/PB/Note)": "Y"})
        out = ml.learned_fields(mido.Message("control_change", control=1, value=1), current)
        self.assertEqual(out["Toggle_(CC/PB/Note)"], "Y")


class LearnableTest(unittest.TestCase):
    def test_what_can_fill_a_command(self):
        self.assertTrue(ml.learnable(mido.Message("control_change")))
        self.assertTrue(ml.learnable(mido.Message("note_on", velocity=1)))
        self.assertFalse(ml.learnable(mido.Message("note_on", velocity=0)))
        self.assertFalse(ml.learnable(mido.Message("note_off")))
        self.assertFalse(ml.learnable(mido.Message("clock")))
        self.assertFalse(ml.learnable(mido.Message("sysex", data=[0x7D, 1])))
        self.assertFalse(ml.learnable(mido.Message("aftertouch")))

    def test_poll_skips_what_cannot(self):
        class Port:
            name = "Port"

            def __init__(self, messages):
                self.messages = list(messages)

            def iter_pending(self):
                while self.messages:
                    yield self.messages.pop(0)

        listener = ml.Listener(names=[])
        listener.ports = [Port([mido.Message("clock")]),
                          Port([mido.Message("note_on", velocity=0),
                                mido.Message("control_change", control=7, value=5)])]
        name, msg = listener.poll()
        self.assertEqual((name, msg.type, msg.control), ("Port", "control_change", 7))
        self.assertIsNone(listener.poll())

    def test_describe(self):
        self.assertEqual(ml.describe(mido.Message("control_change", channel=0, control=74, value=5)),
                         "CC 74 = 5 on channel 1")
        self.assertEqual(ml.describe(mido.Message("program_change", channel=3, program=9)),
                         "PC 9 on channel 4")


if __name__ == "__main__":
    unittest.main()
