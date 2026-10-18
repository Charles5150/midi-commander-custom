"""MIDI Commander Custom: the song you are on, on the pedal's display, from Ableton Live.

A Remote Script. The song is the last locator before the playhead, across the
pedal's top line until the next one; in a set without locators it is the
scene selected in Session view, for a set played scene by scene. Optionally,
play, record, the loop and the metronome go out as CCs, 127 when on and 0 when
off, so a toggle button sending the same CC lights with them (LED_Feedback on
in the pedal's configuration).

Put this folder in User Library/Remote Scripts, restart Live, and in Settings >
Link, Tempo & MIDI pick MIDI_Commander as a Control Surface with the pedal,
MIDI Commander Custom, as its Output. Its Input can stay None. Tried on Live 12
Lite. Needs the pedal's firmware 0.46 or later (0.61 for a name longer than
its place to scroll).

https://github.com/Charles5150/midi-commander-custom
"""

# Settings ---------------------------------------------------------------

# Where the song goes: "line" (11 large letters), "small" (18 small ones),
# "name" (4 large, in place of the bank name) or "info" (11 small, beside it)
SONG_PLACE = "line"
# "locators", "scenes", or "auto": locators when the set has any, else scenes
SONG_FROM = "auto"
# The CCs for the transport, None for none; channel 1-16
CC_CHANNEL = 16
CC_PLAY = None
CC_RECORD = None
CC_LOOP = None
CC_METRONOME = None

# ------------------------------------------------------------------------

try:
    import unicodedata
except ImportError:  # pragma: no cover - a Live without it: accents become "?"
    unicodedata = None

PLACES = {"info": 0, "name": 1, "line": 2, "small": 3}
KEEP_ALWAYS = 1
TEXT_MAX = 32
# Live calls update_display ten times a second; the song goes out again every
# five seconds, which the pedal takes without a flicker, so a pedal plugged in
# or restarted catches up
RESEND_TICKS = 50

# Characters that do not come apart into a plain letter and a mark, as the
# tools spell them (python/lib/displayText.py)
SPELLED = {
    "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ø": "o",
    "Ø": "O", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L", "ı": "i",
    "þ": "th", "Þ": "Th", "‘": "'", "’": "'", "‚": ",", "“": '"',
    "”": '"', "„": '"', "«": '"', "»": '"', "–": "-", "—": "-",
    "−": "-", "…": "...", "·": ".", "×": "x", "÷": "/", "¡": "!",
    "¿": "?", "º": "o", "ª": "a", "°": "o", " ": " ", "\t": " ",
}


def display_text(value):
    """The text as the display can draw it: printable ASCII."""
    text = "" if value is None else str(value)
    if unicodedata is not None:
        text = unicodedata.normalize("NFC", text)
    out = []
    for c in text:
        if unicodedata is not None and unicodedata.combining(c):
            continue
        c = SPELLED.get(c, c)
        if len(c) == 1 and not 0x20 <= ord(c) <= 0x7E and unicodedata is not None:
            c = "".join(p for p in unicodedata.normalize("NFKD", c) if not unicodedata.combining(p))
        out.append("".join(p if 0x20 <= ord(p) <= 0x7E else "?" for p in c) or "?")
    return "".join(out)


def text_sysex(text, place):
    """F0 7D 48 place keep text F7: the text on the display until the host changes it."""
    body = [ord(c) for c in display_text(text)[:TEXT_MAX]]
    return tuple([0xF0, 0x7D, 0x48, PLACES[place], KEEP_ALWAYS] + body + [0xF7])


def song_name(song):
    """The song's name as the settings take it, "" for none."""
    locators = list(song.cue_points)
    if SONG_FROM == "locators" or (SONG_FROM == "auto" and locators):
        now = song.current_song_time
        name = ""
        for cue in sorted(locators, key=lambda c: c.time):
            if cue.time <= now + 1e-6:
                name = cue.name
        return name
    scene = song.view.selected_scene
    return scene.name if scene is not None else ""


def transport(song):
    """(CC, value) for each transport CC set."""
    out = []
    for cc, on in ((CC_PLAY, song.is_playing), (CC_RECORD, song.record_mode),
                   (CC_LOOP, song.loop), (CC_METRONOME, song.metronome)):
        if cc is not None:
            out.append((cc, 127 if on else 0))
    return out


class MIDICommander(object):
    def __init__(self, c_instance):
        self._c = c_instance
        self._ticks = 0
        self._song = None
        self._cc = {}
        self._c.log_message("MIDI Commander: started")

    # What Live calls ------------------------------------------------------

    def update_display(self):
        self._ticks += 1
        if self._ticks >= RESEND_TICKS:
            self._ticks = 0
            self._song = None
            self._cc = {}
        self._step()

    def refresh_state(self):
        self._song = None
        self._cc = {}
        self._step()

    def disconnect(self):
        self._send(text_sysex("", SONG_PLACE))

    def build_midi_map(self, midi_map_handle):
        pass

    def receive_midi(self, midi_bytes):
        pass

    def connect_script_instances(self, instanciated_scripts):
        pass

    def can_lock_to_devices(self):
        return False

    def suggest_input_port(self):
        return ""

    def suggest_output_port(self):
        return "MIDI Commander Custom"

    def suggest_map_mode(self, cc_no, channel):
        return -1

    def toggle_lock(self):
        pass

    def lock_to_device(self, device):
        pass

    def unlock_from_device(self, device):
        pass

    def set_appointed_device(self, device):
        pass

    def restore_bank(self, bank):
        pass

    def show_message(self, message):
        self._c.show_message(message)

    def application(self):
        return self._c.application()

    def song(self):
        return self._c.song()

    # ----------------------------------------------------------------------

    def _send(self, message):
        self._c.send_midi(message)

    def _step(self):
        song = self._c.song()
        name = song_name(song)
        if name != self._song:
            self._send(text_sysex(name, SONG_PLACE))
            self._song = name
        for cc, value in transport(song):
            if self._cc.get(cc) != value:
                self._send((0xB0 + CC_CHANNEL - 1, cc, value))
                self._cc[cc] = value


def create_instance(c_instance):
    return MIDICommander(c_instance)
