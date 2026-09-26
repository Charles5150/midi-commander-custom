"""Helpers to talk to the Midi Commander over USB MIDI SysEx."""

import time

import mido

MIDI_MANUF_ID = 0x7D

SYSEX_CMD_ERASE_FLASH = 52
SYSEX_RSP_ERASE_FLASH = 53
SYSEX_CMD_WRITE_FLASH = 54
SYSEX_RSP_WRITE_FLASH = 55
SYSEX_CMD_READ_FLASH = 56
SYSEX_RSP_READ_FLASH = 57
SYSEX_CMD_GET_VERSION = 58
SYSEX_RSP_GET_VERSION = 59
SYSEX_CMD_RESET = 60
SYSEX_CMD_GET_PEDALS = 62
SYSEX_RSP_GET_PEDALS = 63
SYSEX_CMD_SELECT_SLOT = 64
SYSEX_RSP_SELECT_SLOT = 65
SYSEX_CMD_PRESS_BUTTON = 66
SYSEX_RSP_PRESS_BUTTON = 67
SYSEX_CMD_GET_STATE = 68
SYSEX_RSP_GET_STATE = 69
SYSEX_CMD_GET_SCREEN = 70
SYSEX_RSP_GET_SCREEN = 71
SYSEX_CMD_SET_TEXT = 72
SYSEX_RSP_SET_TEXT = 73
SYSEX_CMD_ENTER_DFU = 74
SYSEX_RSP_ENTER_DFU = 75
SYSEX_CMD_BANNER = 76
SYSEX_RSP_BANNER = 77
SYSEX_CMD_GET_LATENCY = 78
SYSEX_RSP_GET_LATENCY = 79
# Two check bytes ("DF") so a stray message cannot restart the pedal in DFU
ENTER_DFU_CHECK = (0x44, 0x46)

# Where host text goes on the display (firmware 0.46), and what fits there
TEXT_PLACES = {"info": 0, "name": 1, "line": 2, "small": 3}
TEXT_FITS = {"info": 11, "name": 4, "line": 11, "small": 18}
# The most the pedal keeps in any place; a longer text than fits scrolls
# across it (firmware 0.61), where older firmware keeps only what fits
TEXT_MAX = 32
# How long it stays
TEXT_KEEP = {"bank": 0, "always": 1, "moment": 2}

# The power on banner's own text (firmware 0.63), kept by the pedal outside
# the configurations
BANNER_TEXT_MAX = 60

# The pedal's screen buffer: one byte per column for every 8 rows
SCREEN_WIDTH = 130      # columns in the buffer; the firmware draws in 0..127
SCREEN_VISIBLE_WIDTH = 128
SCREEN_HEIGHT = 64
SCREEN_PARTS = (SCREEN_HEIGHT // 8) * 2
SCREEN_PART_BYTES = SCREEN_WIDTH // 2

# Virtual pedal switch ids, in the firmware's order
VIRTUAL_SWITCHES = ["1", "2", "3", "4", "A", "B", "C", "D", "DOWN", "UP"]
LED_LEVELS = 16
CONFIG_SLOTS = 4


class DeviceNotFound(Exception):
    pass


class DeviceTimeout(Exception):
    pass


def switch_id(button) -> int:
    """A virtual switch id from 0-9 or a name: 1-4, A-D, DOWN, UP."""
    if isinstance(button, int):
        if 0 <= button < len(VIRTUAL_SWITCHES):
            return button
        raise ValueError(f"switch id out of range: {button}")
    name = str(button).strip().upper()
    if name not in VIRTUAL_SWITCHES:
        raise ValueError(f"unknown switch: {button}")
    return VIRTUAL_SWITCHES.index(name)


def text_sysex(text: str, place: str = "line", keep: str = "bank") -> list:
    """The whole SysEx message, F0 to F7, that puts text on the display.

    place is one of TEXT_PLACES, keep one of TEXT_KEEP. Characters the display
    cannot draw become spaces; an empty text gives the place back to the bank.
    """
    place = place.strip().lower()
    keep = keep.strip().lower()
    if place not in TEXT_PLACES:
        raise ValueError(f"unknown place: {place} (use {', '.join(TEXT_PLACES)})")
    if keep not in TEXT_KEEP:
        raise ValueError(f"unknown keep: {keep} (use {', '.join(TEXT_KEEP)})")
    body = [ord(c) if 0x20 <= ord(c) <= 0x7E else 0x20 for c in text[:TEXT_MAX]]
    return [0xF0, MIDI_MANUF_ID, SYSEX_CMD_SET_TEXT, TEXT_PLACES[place], TEXT_KEEP[keep]] + body + [0xF7]


def banner_sysex(text: str) -> list:
    """The whole SysEx message, F0 to F7, that stores the banner's own text.

    Characters the display cannot draw become spaces and trailing spaces go;
    an empty text clears it. Raises ValueError for more than BANNER_TEXT_MAX.
    """
    body = "".join(c if 0x20 <= ord(c) <= 0x7E else " " for c in text).rstrip()
    if len(body) > BANNER_TEXT_MAX:
        raise ValueError(f"the banner text is {len(body)} characters, at most {BANNER_TEXT_MAX} fit")
    return [0xF0, MIDI_MANUF_ID, SYSEX_CMD_BANNER, 1] + [ord(c) for c in body] + [0xF7]


def parse_latency(data) -> dict:
    """A GET_LATENCY answer: presses timed, the slowest and the last ones, in ms."""
    def us(i):
        return (data[i] << 14) | (data[i + 1] << 7) | data[i + 2]
    count = (data[0] << 7) | data[1]
    samples = [us(i) / 1000 for i in range(5, len(data) - 2, 3)]
    return {"count": count, "max": us(2) / 1000, "samples": samples}


def unpack7(data) -> bytes:
    """Undo the firmware's 7 in 8 packing: a byte of high bits, then up to 7 low parts."""
    data = list(data)
    out = bytearray()
    for i in range(0, len(data), 8):
        high = data[i]
        for k, low in enumerate(data[i + 1 : i + 8]):
            out.append((low & 0x7F) | (0x80 if (high >> k) & 1 else 0))
    return bytes(out)


def screen_rows(buffer: bytes):
    """The visible screen as SCREEN_HEIGHT rows of booleans, lit pixels True."""
    return [
        [bool(buffer[x + (y // 8) * SCREEN_WIDTH] >> (y % 8) & 1) for x in range(SCREEN_VISIBLE_WIDTH)]
        for y in range(SCREEN_HEIGHT)
    ]


def parse_state(data) -> dict:
    """Decode a GET_STATE answer (the bytes after the response code)."""
    data = list(data)
    if len(data) < 50:
        raise ValueError(f"state answer too short: {len(data)} bytes")

    def text(chunk):
        return "".join(chr(b) if 0x20 <= b <= 0x7E else " " for b in chunk).rstrip()

    toggles = data[2] | (data[3] << 7)
    return {
        "bank": data[0],
        "slot": data[1],
        "toggles": [bool(toggles >> i & 1) for i in range(8)],
        "bank_name": text(data[4:8]),
        "labels": [text(data[8 + 4 * i : 12 + 4 * i]) for i in range(8)],
        "leds": [min(v, LED_LEVELS) for v in data[40:50]],
        # Changes whenever the pedal redraws its screen; None before firmware 0.27's final form
        "frame": (data[50] | (data[51] << 7)) if len(data) >= 53 else None,
        "asleep": bool(data[52]) if len(data) >= 53 else False,
        # The eight stored values a Var command changes; None before firmware 0.54
        "values": data[53:61] if len(data) >= 61 else None,
        # Started with a footswitch held: nothing sent (firmware 0.60)
        "safe_mode": bool(data[61]) if len(data) >= 62 else False,
    }


def version_at_least(version: str, major: int, minor: int) -> bool:
    """Compare a "0.26" style version string; anything unparsable is old."""
    try:
        parts = [int(p) for p in str(version).strip().split(".")[:2]]
    except ValueError:
        return False
    while len(parts) < 2:
        parts.append(0)
    return tuple(parts) >= (major, minor)


def _matches(name: str) -> bool:
    return "STM" in name or "MIDI Commander" in name


def find_port_names():
    inputs = [n for n in mido.get_input_names() if _matches(n)]
    outputs = [n for n in mido.get_output_names() if _matches(n)]
    return inputs, outputs


class MidiCommander:
    """Context manager wrapping the input/output port pair."""

    def __init__(self):
        self.inport = None
        self.outport = None

    def __enter__(self):
        inputs, outputs = find_port_names()
        if not inputs:
            raise DeviceNotFound("No MIDI Input Found")
        if not outputs:
            raise DeviceNotFound("No MIDI Output Found")

        errors = []
        for name in inputs:
            try:
                self.inport = mido.open_input(name)
                break
            except Exception as e:  # noqa: BLE001
                errors.append(f"{name}: {e}")
        if self.inport is None:
            raise DeviceNotFound("Could not open MIDI input: " + "; ".join(errors))

        for name in outputs:
            try:
                self.outport = mido.open_output(name)
                break
            except Exception as e:  # noqa: BLE001
                errors.append(f"{name}: {e}")
        if self.outport is None:
            self.inport.close()
            raise DeviceNotFound("Could not open MIDI output: " + "; ".join(errors))

        self.flush_input()
        return self

    def __exit__(self, *exc):
        if self.inport:
            self.inport.close()
        if self.outport:
            self.outport.close()
        return False

    def flush_input(self):
        while self.inport.poll():
            pass

    def send(self, data):
        self.outport.send(mido.Message("sysex", data=[MIDI_MANUF_ID] + list(data)))

    def wait_for_sysex(self, expected_rsp, timeout=2.0):
        """Return the data bytes after the response code, or raise DeviceTimeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            msg = self.inport.poll()
            if msg is None:
                time.sleep(0.002)
                continue
            if msg.type != "sysex":
                continue  # clock, active sensing, etc.
            data = list(msg.data)
            if len(data) >= 2 and data[0] == MIDI_MANUF_ID and data[1] == expected_rsp:
                return data[2:]
        raise DeviceTimeout(f"No response {expected_rsp} from device")

    def firmware_at_least(self, major: int, minor: int, timeout=1.0) -> bool:
        """True when the firmware reports a version of at least major.minor."""
        return version_at_least(self.get_version(timeout), major, minor)

    def get_version(self, timeout=1.0) -> str:
        self.send([SYSEX_CMD_GET_VERSION])
        data = self.wait_for_sysex(SYSEX_RSP_GET_VERSION, timeout)
        return bytes(data).decode("ascii", errors="replace")

    def get_latency(self, clear=False, timeout=1.0) -> dict:
        """What the pedal measured from a press to its first MIDI message (0.65).

        count presses timed since the last clear, max the slowest and samples
        the last ones, oldest first, both in milliseconds.
        """
        self.send([SYSEX_CMD_GET_LATENCY, 1 if clear else 0])
        return parse_latency(self.wait_for_sysex(SYSEX_RSP_GET_LATENCY, timeout))

    def get_pedals(self, timeout=0.5):
        """Return [(raw_adc, cc_value), (raw_adc, cc_value)] for the two pedals."""
        self.send([SYSEX_CMD_GET_PEDALS])
        data = self.wait_for_sysex(SYSEX_RSP_GET_PEDALS, timeout)
        out = []
        for i in range(2):
            hi, lo, cc = data[3 * i : 3 * i + 3]
            out.append(((hi << 7) | lo, cc))
        return out

    def select_slot(self, slot=None, timeout=1.0):
        """Choose the configuration slot (0-3) the next erase, write and read
        act on, or with None only ask. Returns (target, active, valid_slots).

        Raises DeviceTimeout on firmware older than 0.24, which has no slots.
        """
        code = 0x7F if slot is None else int(slot)
        self.send([SYSEX_CMD_SELECT_SLOT, code & 0x7F])
        data = self.wait_for_sysex(SYSEX_RSP_SELECT_SLOT, timeout)
        target, active, mask = data[0], data[1], data[2]
        valid = [s for s in range(CONFIG_SLOTS) if mask & (1 << s)]
        return target, active, valid

    def press_button(self, button, down: bool, timeout=1.0):
        """Press (down=True) or release a switch as if by foot (firmware 0.27)."""
        sid = switch_id(button)
        self.send([SYSEX_CMD_PRESS_BUTTON, sid, 1 if down else 0])
        self.wait_for_sysex(SYSEX_RSP_PRESS_BUTTON, timeout)

    def set_text(self, text: str, place: str = "line", keep: str = "bank", timeout=1.0):
        """Put text on the display (firmware 0.46); see text_sysex."""
        self.outport.send(mido.Message("sysex", data=text_sysex(text, place, keep)[1:-1]))
        self.wait_for_sysex(SYSEX_RSP_SET_TEXT, timeout)

    def get_banner(self, timeout=1.0) -> str:
        """The banner's own text the pedal holds, "" for none (firmware 0.63)."""
        self.send([SYSEX_CMD_BANNER, 0])
        data = self.wait_for_sysex(SYSEX_RSP_BANNER, timeout)
        return bytes(data[1:]).decode("ascii", errors="replace")

    def set_banner(self, text: str, timeout=2.0) -> str:
        """Store the banner's own text, "" to clear it (firmware 0.63); see
        banner_sysex. Returns the text the pedal now holds."""
        self.outport.send(mido.Message("sysex", data=banner_sysex(text)[1:-1]))
        data = self.wait_for_sysex(SYSEX_RSP_BANNER, timeout)
        if data and data[0]:
            raise ValueError("the pedal refused the banner text")
        return bytes(data[1:]).decode("ascii", errors="replace")

    def enter_dfu(self, timeout=1.0) -> bool:
        """Restart the pedal in the stock bootloader's DFU mode (firmware 0.58).

        True when it is on its way; False when the firmware is not running
        behind the bootloader, and nothing was done. Raises DeviceTimeout on
        older firmware, which does not know the command.
        """
        self.send([SYSEX_CMD_ENTER_DFU, *ENTER_DFU_CHECK])
        data = self.wait_for_sysex(SYSEX_RSP_ENTER_DFU, timeout)
        return bool(data) and data[0] == 0

    def get_state(self, timeout=1.0) -> dict:
        """Bank, slot, toggles, bank name, labels and LED levels (firmware 0.27)."""
        self.send([SYSEX_CMD_GET_STATE])
        return parse_state(self.wait_for_sysex(SYSEX_RSP_GET_STATE, timeout))

    def get_screen(self, timeout=1.0) -> bytes:
        """The pedal's whole screen buffer, SCREEN_WIDTH x SCREEN_HEIGHT / 8 bytes."""
        buffer = bytearray()
        for part in range(SCREEN_PARTS):
            self.send([SYSEX_CMD_GET_SCREEN, part])
            while True:
                data = self.wait_for_sysex(SYSEX_RSP_GET_SCREEN, timeout)
                if data and data[0] == part:
                    break
            chunk = unpack7(data[1:])
            if len(chunk) != SCREEN_PART_BYTES:
                raise ValueError(f"screen part {part} has {len(chunk)} bytes")
            buffer += chunk
        return bytes(buffer)

    def flash_report(self, timeout=1.0):
        """(flash size in kB the chip reports, double press storable), from the
        SELECT_SLOT answer of firmware 0.26 or later; None on older firmware."""
        self.send([SYSEX_CMD_SELECT_SLOT, 0x7F])
        data = self.wait_for_sysex(SYSEX_RSP_SELECT_SLOT, timeout)
        if len(data) < 6:
            return None
        return (data[3] << 7) | data[4], bool(data[5] & 1)

    def read_chunk(self, chunk_index: int, timeout=1.0) -> bytes:
        hi = (chunk_index >> 7) & 0x7F
        lo = chunk_index & 0x7F
        self.send([SYSEX_CMD_READ_FLASH, hi, lo])
        while True:
            data = self.wait_for_sysex(SYSEX_RSP_READ_FLASH, timeout)
            if len(data) >= 34 and data[0] == hi and data[1] == lo:
                nibbles = data[2:34]
                return bytes(
                    (nibbles[2 * i] << 4) | (nibbles[2 * i + 1] & 0x0F)
                    for i in range(16)
                )
            # A stale response for another chunk, keep waiting

    def read_settings(self, num_bytes: int, progress=None, start: int = 0) -> bytes:
        """num_bytes of the target slot's image from byte `start` (a multiple of 16)."""
        first = start // 16
        chunks = (num_bytes + 15) // 16
        out = bytearray()
        for i in range(chunks):
            out += self.read_chunk(first + i)
            if progress:
                progress(i + 1, chunks)
        return bytes(out[:num_bytes])
