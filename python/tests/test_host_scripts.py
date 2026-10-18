"""The scripts for programs on the computer, under hosts/: what they send the pedal.

The REAPER script runs here in Lua (lupa) against a REAPER made of Python; the
Ableton Live one, in Python, against a Live made of Python.
"""

import importlib.util
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
LIVE_SCRIPT = os.path.join(ROOT, "hosts", "ableton", "MIDI_Commander", "__init__.py")


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


class Obj:
    def __init__(self, **fields):
        self.__dict__.update(fields)


class FakeLive:
    """What a Remote Script gets: c_instance, with a song of locators and scenes."""

    def __init__(self):
        self.sent = []
        self.logged = []
        self.scene = Obj(name="")
        self.view = Obj(selected_scene=self.scene)
        self.the_song = Obj(cue_points=[], current_song_time=0.0, view=self.view, is_playing=False,
                            record_mode=False, loop=False, metronome=False)

    def song(self):
        return self.the_song

    def send_midi(self, message):
        self.assertIsTuple(message)
        self.sent.append(message)

    @staticmethod
    def assertIsTuple(message):
        assert isinstance(message, tuple) and all(isinstance(b, int) and 0 <= b <= 255 for b in message), message

    def log_message(self, text):
        self.logged.append(text)


class LiveScriptTest(unittest.TestCase):
    def load(self, **settings):
        spec = importlib.util.spec_from_file_location("midi_commander_live", LIVE_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name, value in settings.items():
            self.assertTrue(hasattr(module, name), name)
            setattr(module, name, value)
        self.live = FakeLive()
        self.module = module
        return module.create_instance(self.live)

    def texts(self):
        out = []
        for msg in self.live.sent:
            if msg[0] == 0xF0:
                self.assertEqual(msg[:3] + msg[-1:], (0xF0, 0x7D, 0x48, 0xF7))
                out.append((msg[3], msg[4], bytes(msg[5:-1]).decode("ascii")))
            else:
                out.append(msg)
        self.live.sent.clear()
        return out

    def test_the_text_as_the_tools_spell_it(self):
        self.load()
        samples = ["Canci\u00f3n", "\u00d1u", "Stra\u00dfe", "\u201cLive\u201d \u2013 2026\u2026", "\u65e5\u672c",
                   "e\u0301", "\x7f", "Tab\there"] + [chr(c) for c in range(0xA0, 0x250)] + list(SPELLED)
        for text in samples:
            self.assertEqual(self.module.display_text(text), display_text(text), repr(text))

    def test_the_message_is_the_tools(self):
        self.load()
        text = "A song with a name longer than thirty-two letters"
        for place in ("info", "name", "line", "small"):
            self.assertEqual(bytes(self.module.text_sysex(text, place)), bytes(text_sysex(text, place, "always")))

    def test_the_locator_before_the_playhead(self):
        script = self.load()
        song = self.live.the_song
        song.cue_points = [Obj(time=32.0, name="Canci\u00f3n"), Obj(time=0.0, name="Sweet Child")]
        script.update_display()
        self.assertEqual(self.texts(), [(2, 1, "Sweet Child")])
        script.update_display()
        self.assertEqual(self.texts(), [])
        song.current_song_time = 32.0
        script.update_display()
        self.assertEqual(self.texts(), [(2, 1, "Cancion")])
        # Before the first locator: no song, the line back to the bank
        song.cue_points[1].time = 4.0
        song.current_song_time = 1.0
        script.update_display()
        self.assertEqual(self.texts(), [(2, 1, "")])

    def test_the_scene_without_locators(self):
        script = self.load(SONG_PLACE="small")
        self.live.scene.name = "Intro jam"
        script.update_display()
        self.assertEqual(self.texts(), [(3, 1, "Intro jam")])
        self.live.view.selected_scene = Obj(name="Outro")
        script.update_display()
        self.assertEqual(self.texts(), [(3, 1, "Outro")])
        # Scenes asked for: locators are left aside
        script = self.load(SONG_FROM="scenes")
        self.live.the_song.cue_points = [Obj(time=0.0, name="Locator")]
        self.live.scene.name = "Verse"
        script.update_display()
        self.assertEqual(self.texts(), [(2, 1, "Verse")])

    def test_sent_again_now_and_then(self):
        script = self.load()
        for _ in range(49):
            script.update_display()
        self.assertEqual(self.texts(), [(2, 1, "")])
        script.update_display()
        self.assertEqual(self.texts(), [(2, 1, "")])
        script.refresh_state()
        self.assertEqual(self.texts(), [(2, 1, "")])

    def test_the_transport_as_ccs(self):
        script = self.load(CC_PLAY=20, CC_RECORD=21, CC_METRONOME=23, CC_CHANNEL=3)
        song = self.live.the_song
        script.update_display()
        self.assertEqual(self.texts()[1:], [(0xB2, 20, 0), (0xB2, 21, 0), (0xB2, 23, 0)])
        song.is_playing, song.metronome = True, True
        script.update_display()
        self.assertEqual(self.texts(), [(0xB2, 20, 127), (0xB2, 23, 127)])

    def test_disconnect_gives_the_line_back(self):
        script = self.load()
        script.disconnect()
        self.assertEqual(self.texts(), [(2, 1, "")])
        self.assertEqual(script.suggest_output_port(), "MIDI Commander Custom")


if __name__ == "__main__":
    unittest.main()
