"""The scripts for programs on the computer, under hosts/: what they send the pedal.

The REAPER script runs here in Lua (lupa) against a REAPER made of Python.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from lib.displayText import SPELLED, display_text  # noqa: E402
from lib.midiDevice import text_sysex  # noqa: E402

try:
    from lupa import lua54
except ImportError:  # pragma: no cover
    lua54 = None

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
REAPER_SCRIPT = os.path.join(ROOT, "hosts", "reaper", "MIDI_Commander_song_names.lua")


class FakeReaper:
    """A project of regions and markers, a transport and a list of MIDI outputs."""

    def __init__(self):
        self.outputs = ["IAC Driver Bus 1", "MIDI Commander Custom"]
        self.sent = []
        self.time = 0.0
        self.state = 0
        self.play = 0.0
        self.cursor = 0.0
        self.project = "Gig.rpp"
        # (is region, start, end, name)
        self.markers = []
        self.toggles = {}

    def api(self, lua):
        r = self

        def last_marker_and_region(_proj, t):
            marker = region = -1
            for i, (rgn, start, end, _) in enumerate(r.markers):
                if rgn and start <= t < end:
                    region = i
                if not rgn and start <= t:
                    marker = i
            return marker, region

        def enum_markers(_proj, i):
            rgn, start, end, name = r.markers[i]
            return 1, rgn, start, end, name.encode(), i, 0

        def output_name(i, _buf):
            if i < len(r.outputs):
                return True, r.outputs[i].encode()
            return False, b""

        functions = {
            "time_precise": lambda: r.time,
            "GetPlayState": lambda: r.state,
            "GetPlayPosition": lambda: r.play,
            "GetCursorPosition": lambda: r.cursor,
            "GetLastMarkerAndCurRegion": last_marker_and_region,
            "EnumProjectMarkers3": enum_markers,
            "GetProjectName": lambda _proj: r.project.encode(),
            "GetNumMIDIOutputs": lambda: 16,
            "GetMIDIOutputName": output_name,
            "SendMIDIMessageToHardware": lambda dev, msg: r.sent.append((dev, bytes(msg))),
            "GetToggleCommandState": lambda cmd: r.toggles.get(cmd, 0),
        }
        return lua.table_from({name.encode(): f for name, f in functions.items()})


@unittest.skipIf(lua54 is None, "needs lupa (pip install lupa)")
class ReaperScriptTest(unittest.TestCase):
    def load(self, settings=None):
        with open(REAPER_SCRIPT, encoding="utf-8") as f:
            source = f.read()
        for name, value in (settings or {}).items():
            source, n = re.subn(rf"^local {name} = .*$", f"local {name} = {value}", source, count=1, flags=re.M)
            self.assertEqual(n, 1, name)
        lua = lua54.LuaRuntime(unpack_returned_tuples=True, encoding=None)
        self.reaper = FakeReaper()
        lua.globals().reaper = self.reaper.api(lua)
        lua.globals().MCC_TEST = True
        return lua.execute(source.encode())

    def texts(self):
        """What went to the pedal since the last look, as (place, keep, text) or a CC."""
        out = []
        for dev, msg in self.reaper.sent:
            self.assertEqual(dev, 1)
            if msg[0] == 0xF0:
                self.assertEqual(msg[:3] + msg[-1:], bytes([0xF0, 0x7D, 0x48, 0xF7]))
                out.append((msg[3], msg[4], msg[5:-1].decode("ascii")))
            else:
                out.append(tuple(msg))
        self.reaper.sent.clear()
        return out

    def test_the_text_as_the_tools_spell_it(self):
        script = self.load()
        samples = ["Canción", "Ñu", "Straße", "Œuvre", "Café", "“Live” – 2026…", "日本", "Tab\there",
                   "é", "\x7f"]
        samples += [chr(c) for c in range(0xA0, 0x180)] + list(SPELLED)
        for text in samples:
            self.assertEqual(script.display_text(text.encode()).decode(), display_text(text), repr(text))

    def test_the_message_is_the_tools(self):
        script = self.load()
        for place, number in (("info", 0), ("name", 1), ("line", 2), ("small", 3)):
            for keep, how in (("always", 1), ("moment", 2)):
                text = "A song with a name longer than thirty-two letters"
                self.assertEqual(script.text_sysex(text.encode(), place.encode(), how), bytes(text_sysex(text, place, keep)))

    def test_the_region_names_the_song(self):
        script = self.load()
        r = self.reaper
        r.markers = [(True, 0, 100, "Sweet Child"), (True, 100, 200, "Canción")]
        script.step()
        self.assertEqual(self.texts(), [(2, 1, "Sweet Child")])
        r.time, r.cursor = 0.1, 150
        script.step()
        self.assertEqual(self.texts(), [(2, 1, "Cancion")])
        r.time = 0.2
        script.step()
        self.assertEqual(self.texts(), [])
        # Playing, the play cursor counts, not the edit cursor
        r.time, r.state, r.play = 0.3, 1, 10
        script.step()
        self.assertEqual(self.texts(), [(2, 1, "Sweet Child")])

    def test_the_project_when_no_region(self):
        script = self.load()
        script.step()
        self.assertEqual(self.texts(), [(2, 1, "Gig")])
        script = self.load({"PROJECT_NAME_AS_SONG": "false"})
        script.step()
        self.assertEqual(self.texts(), [(2, 1, "")])

    def test_a_marker_reached_playing_shows_for_a_moment(self):
        script = self.load()
        r = self.reaper
        r.markers = [(True, 0, 100, "Song"), (False, 0, 0, "Intro"), (False, 20, 0, "Chorus")]
        script.step()
        self.assertEqual(self.texts(), [(2, 1, "Song")])
        # The cursor put past a marker: nothing
        r.time, r.cursor = 0.1, 30
        script.step()
        self.assertEqual(self.texts(), [])
        r.time, r.state, r.play = 0.2, 1, 5
        script.step()
        self.assertEqual(self.texts(), [(2, 2, "Intro")])
        r.time, r.play = 0.3, 21
        script.step()
        self.assertEqual(self.texts(), [(2, 2, "Chorus")])
        script = self.load({"PART_PLACE": "nil"})
        self.reaper.markers = r.markers
        script.step()
        self.reaper.state, self.reaper.play, self.reaper.time = 1, 25, 0.1
        script.step()
        self.assertEqual(self.texts(), [(2, 1, "Song")])

    def test_sent_again_now_and_then(self):
        script = self.load({"SONG_PLACE": '"small"'})
        r = self.reaper
        script.step()
        r.time = 4.9
        script.step()
        self.assertEqual(self.texts(), [(3, 1, "Gig")])
        r.time = 5.0
        script.step()
        self.assertEqual(self.texts(), [(3, 1, "Gig")])

    def test_no_pedal_nothing_sent(self):
        script = self.load()
        self.reaper.outputs = ["IAC Driver Bus 1"]
        script.step()
        self.assertEqual(self.reaper.sent, [])
        # Plugged in: found at the next resend
        self.reaper.outputs.append("MIDI Commander Custom")
        self.reaper.time = 5
        script.step()
        self.assertEqual(self.texts(), [(2, 1, "Gig")])

    def test_the_transport_as_ccs(self):
        script = self.load({"CC_PLAY": "20", "CC_RECORD": "21", "CC_REPEAT": "22", "CC_CHANNEL": "3"})
        r = self.reaper
        script.step()
        self.assertEqual(self.texts()[1:], [(0xB2, 20, 0), (0xB2, 21, 0), (0xB2, 22, 0)])
        r.time, r.state, r.toggles = 0.1, 5, {1068: 1}
        script.step()
        self.assertEqual(self.texts(), [(0xB2, 20, 127), (0xB2, 21, 127), (0xB2, 22, 127)])
        r.time, r.state = 0.2, 1
        script.step()
        self.assertEqual(self.texts(), [(0xB2, 21, 0)])

    def test_stopping_gives_the_line_back(self):
        script = self.load()
        script.stop()
        self.assertEqual(self.texts(), [(2, 1, "")])


if __name__ == "__main__":
    unittest.main()
