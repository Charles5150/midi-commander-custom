"""MIDI learn: fill a command from the first message that arrives.

Press Learn in the configurator, move a knob or press a button on a device
the computer hears (a USB MIDI device, a DAW's virtual port, the pedal
itself), and the first Program Change, Control Change, Note On or Pitch Bend
that arrives sets the command's type, channel and number. Clock, SysEx and
the other system messages are passed over, as is a Note On at velocity 0,
which is a Note Off.

Nothing here touches the configuration's bytes: learned_fields gives the
same CSV fields the editor would, and the editor puts them in its widgets.
"""

import time

import mido

LEARNABLE = ("program_change", "control_change", "note_on", "pitchwheel")

# The command type a message becomes, and the ones that keep their type
# when they are already chosen: a CC learned on a CCInc sets its CC number
COMMAND_OF = {"program_change": "PC", "control_change": "CC", "note_on": "Note", "pitchwheel": "PB"}
KEEPS = {"control_change": ("CC", "CCInc"), "program_change": ("PC", "PCInc")}

CHANNEL = "Channel_(PC/CC/Note/PB)"
NUMBER = "Number_(PC/CC/Note)"
ON = "OnValue_(CC/PB)"
OFF = "OffValue_(CC)"
VELOCITY = "Velocity_(Note)"


def learnable(msg) -> bool:
    """A message that can fill a command."""
    if msg.type not in LEARNABLE:
        return False
    return not (msg.type == "note_on" and msg.velocity == 0)


def describe(msg, channel: bool = True) -> str:
    """A plain reading of a learnable message, channels counted from 1."""
    if msg.type == "program_change":
        text = f"PC {msg.program}"
    elif msg.type == "control_change":
        text = f"CC {msg.control} = {msg.value}"
    elif msg.type == "note_on":
        text = f"Note {msg.note} velocity {msg.velocity}"
    elif msg.type == "pitchwheel":
        text = f"Pitch Bend {msg.pitch}"
    else:
        return str(msg)
    return f"{text} on channel {msg.channel + 1}" if channel else text


def _empty(value) -> bool:
    s = "" if value is None else str(value).strip()
    return s == "" or s.lower() == "nan"


def learned_fields(msg, current: dict) -> dict:
    """The command's CSV fields after learning `msg`.

    `current` holds the fields as the editor has them, with CommandType. The
    type, channel and number come from the message; the values a command
    already has (On, Off, Velocity) stay, and only an empty one takes the
    value that arrived, so a button learned from a device sending 127 sends
    127 while a knob learned halfway does not set half a value on a filled
    command.
    """
    out = dict(current)
    kind = msg.type
    if (current.get("CommandType") or "") not in KEEPS.get(kind, ()):
        out["CommandType"] = COMMAND_OF[kind]
    cmd_type = out["CommandType"]
    out[CHANNEL] = str(msg.channel + 1)

    if kind == "program_change":
        if cmd_type == "PC":
            out[NUMBER] = str(msg.program)
    elif kind == "control_change":
        out[NUMBER] = str(msg.control)
        if cmd_type == "CC":
            if _empty(current.get(ON)):
                out[ON] = str(msg.value or 127)
            if _empty(current.get(OFF)):
                out[OFF] = "0"
    elif kind == "note_on":
        out[NUMBER] = str(msg.note)
        if _empty(current.get(VELOCITY)):
            out[VELOCITY] = str(msg.velocity)
    elif kind == "pitchwheel":
        if _empty(current.get(ON)):
            out[ON] = str(msg.pitch)
    return out


class Listener:
    """Every MIDI input the computer has, open until close().

    The ports are read from the GUI's own thread by poll(), and closed with
    close_input().
    """

    def __init__(self, names=None):
        self.ports = []
        for name in mido.get_input_names() if names is None else names:
            try:
                self.ports.append(mido.open_input(name))
            except Exception:
                # Held by another program on systems that do not share ports
                continue

    @property
    def names(self):
        return [p.name for p in self.ports]

    def poll(self):
        """(port name, message) for the first learnable message waiting, or None.

        What arrived before it, on every port, is read and dropped.
        """
        for port in self.ports:
            for msg in port.iter_pending():
                if learnable(msg):
                    return port.name, msg
        return None

    def close(self):
        for p in self.ports:
            close_input(p)
        self.ports = []


def close_input(port):
    """Close a mido input without locking up on a message arriving.

    mido's rtmidi ports always hand what arrives to a Python callback, and
    close() puts that callback back before closing. CoreMIDI then waits for a
    message on its way to the callback, which waits for the interpreter the
    close is holding, and both wait for ever. So take the callback away,
    give one already running a moment to finish, and close the port itself.
    """
    rt = getattr(port, "_rt", None)
    if rt is None:
        port.close()
        return
    try:
        rt.cancel_callback()
        time.sleep(0.02)
        rt.close_port()
        rt.delete()
    except Exception:
        pass
    port.closed = True
