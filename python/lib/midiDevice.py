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
