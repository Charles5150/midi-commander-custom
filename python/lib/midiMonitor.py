"""The MIDI monitor: what arrives at the computer, read plainly.

The configurator's Monitor tab opens every MIDI input the computer has (the
pedal, a USB device, a DAW's virtual port) and lists each message with the
time it arrived, the port, its raw bytes and a plain reading. The tab only
draws; what a message is, which filter it passes and how a line reads are
here, so they can be tested without a window or a device.

Each port hands its messages to a callback on rtmidi's own thread, which
stamps the time right away, so the times are those of arrival and not of the
next time the window looked.
"""

import collections
import time
from dataclasses import dataclass

import mido

from lib import kemperProtocol as kemper
from lib import midiDevice
from lib.cmdBinaryPacker import MMC_COMMANDS
from lib.midiLearn import close_input

# The kinds of message, each shown or hidden as a whole. Clock runs at 24 a
# beat and the pedal's replies to the configurator's own questions come many
# times a second while the Virtual Pedal is connected, so both start hidden.
KINDS = ("Notes", "CC", "PC", "Bend & pressure", "SysEx", "System", "Clock", "Pedal replies")
HIDDEN_AT_START = ("Clock", "Pedal replies")

CLOCK = ("clock", "active_sensing")
SYSTEM = ("start", "stop", "continue", "songpos", "song_select", "tune_request", "quarter_frame", "reset")

# How many messages are kept for the filters to go back over
KEEP = 2000

# A few Control Changes known by name the world over
CC_NAMES = {
    0: "Bank Select", 1: "Modulation", 2: "Breath", 4: "Foot", 5: "Portamento Time",
    7: "Volume", 8: "Balance", 10: "Pan", 11: "Expression", 32: "Bank Select LSB",
    64: "Sustain", 65: "Portamento", 66: "Sostenuto", 67: "Soft Pedal",
    120: "All Sound Off", 121: "Reset All Controllers", 123: "All Notes Off",
}

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

MMC_NAMES = {v: k for k, v in MMC_COMMANDS.items()}

# The pedal's own SysEx numbers, by name, for reading its replies
PEDAL_ID = midiDevice.MIDI_MANUF_ID
PEDAL_SYSEX = {
    getattr(midiDevice, n): n[len("SYSEX_CMD_"):].replace("_", " ").lower()
    + (" reply" if n.startswith("SYSEX_RSP_") else "")
    for n in dir(midiDevice) if n.startswith(("SYSEX_CMD_", "SYSEX_RSP_"))
}


def note_name(note: int) -> str:
    """Middle C, note 60, is C4."""
    return f"{NOTE_NAMES[note % 12]}{note // 12 - 1}"


def is_pedal_reply(msg) -> bool:
    """The pedal answering the configurator in its own SysEx."""
    return msg.type == "sysex" and len(msg.data) >= 2 and msg.data[0] == PEDAL_ID


def kind(msg) -> str:
    t = msg.type
    if t in ("note_on", "note_off"):
        return "Notes"
    if t == "control_change":
        return "CC"
    if t == "program_change":
        return "PC"
    if t in ("pitchwheel", "aftertouch", "polytouch"):
        return "Bend & pressure"
    if t == "sysex":
        return "Pedal replies" if is_pedal_reply(msg) else "SysEx"
    if t in CLOCK:
        return "Clock"
    return "System"


def channel(msg):
    """The message's channel counted from 1, or None for a system message."""
    return msg.channel + 1 if hasattr(msg, "channel") else None


def raw(msg, most: int = 24) -> str:
    """The bytes in hex; a long SysEx is cut, saying how long it was."""
    data = msg.bytes()
    text = " ".join(f"{b:02X}" for b in data[:most])
    if len(data) > most:
        text += f" … ({len(data)} bytes)"
    return text


def _sysex(data) -> str:
    data = tuple(data)
    if not data:
        return "SysEx, empty"
    if data[0] == PEDAL_ID:
        what = PEDAL_SYSEX.get(data[1]) if len(data) > 1 else None
        return f"Midi Commander: {what}" if what else "Midi Commander"
    if data[:3] == kemper.MANUFACTURER:
        return "Kemper"
    if data[0] == 0x7F and len(data) >= 4 and data[2] == 0x06:
        name = MMC_NAMES.get(data[3], f"command {data[3]}")
        return f"MMC {name}"
    if data[0] == 0x7F:
        return "Universal real time"
    if data[0] == 0x7E and len(data) >= 4 and data[2:4] == (0x06, 0x01):
        return "Identity request"
    if data[0] == 0x7E and len(data) >= 4 and data[2:4] == (0x06, 0x02):
        return "Identity reply"
    if data[0] == 0x7E:
        return "Universal non real time"
    if data[0] == 0x00 and len(data) >= 3:
        return f"SysEx from maker {data[0]:02X} {data[1]:02X} {data[2]:02X}"
    return f"SysEx from maker {data[0]:02X}"


def describe(msg) -> str:
    """A plain reading of any message, without its channel."""
    t = msg.type
    if t == "note_on" and msg.velocity == 0:
        return f"Note Off {msg.note} ({note_name(msg.note)})"
    if t == "note_on":
        return f"Note On {msg.note} ({note_name(msg.note)}) velocity {msg.velocity}"
    if t == "note_off":
        return f"Note Off {msg.note} ({note_name(msg.note)}) velocity {msg.velocity}"
    if t == "control_change":
        name = CC_NAMES.get(msg.control)
        return f"CC {msg.control}" + (f" {name}" if name else "") + f" = {msg.value}"
    if t == "program_change":
        return f"PC {msg.program}"
    if t == "pitchwheel":
        return f"Pitch Bend {msg.pitch:+d}" if msg.pitch else "Pitch Bend centre"
    if t == "aftertouch":
        return f"Channel Pressure {msg.value}"
    if t == "polytouch":
        return f"Key Pressure {msg.note} ({note_name(msg.note)}) = {msg.value}"
    if t == "sysex":
        return _sysex(msg.data)
    if t == "songpos":
        return f"Song Position {msg.pos}"
    if t == "song_select":
        return f"Song Select {msg.song}"
    if t == "quarter_frame":
        return f"Timecode quarter frame {msg.frame_type}:{msg.frame_value}"
    names = {"clock": "Clock", "active_sensing": "Active Sensing", "start": "Start",
             "stop": "Stop", "continue": "Continue", "tune_request": "Tune Request",
             "reset": "System Reset"}
    return names.get(t, t)


@dataclass
class Entry:
    time: float     # seconds since the monitor started
    port: str
    msg: object


@dataclass
class Filter:
    """What the monitor shows: kinds, a channel (1-16, None for any) and a port."""

    kinds: frozenset = frozenset(k for k in KINDS if k not in HIDDEN_AT_START)
    channel: object = None
    port: object = None

    def passes(self, entry: Entry) -> bool:
        if kind(entry.msg) not in self.kinds:
            return False
        if self.port is not None and entry.port != self.port:
            return False
        # A channel chosen leaves out what has no channel
        if self.channel is not None and channel(entry.msg) != self.channel:
            return False
        return True


def line(entry: Entry, previous=None, port_width: int = 22) -> str:
    """One row: time, time since the row above, port, channel, reading, bytes."""
    since = "" if previous is None else f"+{entry.time - previous.time:.3f}"
    ch = channel(entry.msg)
    port = entry.port if len(entry.port) <= port_width else entry.port[:port_width - 1] + "…"
    return (f"{entry.time:9.3f} {since:>9}  {port:<{port_width}}  "
            f"{'ch ' + str(ch) if ch else '':<5}  {describe(entry.msg):<38}  {raw(entry.msg)}")


class Monitor:
    """Every MIDI input the computer has, stamping what arrives until close()."""

    def __init__(self, names=None, clock=time.monotonic):
        self.clock = clock
        self.start = clock()
        self.queue = collections.deque()
        self.ports = []
        for name in mido.get_input_names() if names is None else names:
            try:
                self.ports.append(mido.open_input(name, callback=self._taker(name)))
            except Exception:
                # Held by another program on systems that do not share ports
                continue

    def _taker(self, name):
        def take(msg):
            # deque.append is safe from another thread
            self.queue.append(Entry(self.clock() - self.start, name, msg))
        return take

    @property
    def names(self):
        return [p.name for p in self.ports]

    def drain(self):
        """What has arrived since the last call, oldest first."""
        out = []
        while self.queue:
            out.append(self.queue.popleft())
        return out

    def close(self):
        for p in self.ports:
            close_input(p)
        self.ports = []
