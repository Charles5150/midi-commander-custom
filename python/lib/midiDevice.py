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


class DeviceNotFound(Exception):
    pass


class DeviceTimeout(Exception):
    pass


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

    def read_settings(self, num_bytes: int, progress=None) -> bytes:
        chunks = (num_bytes + 15) // 16
        out = bytearray()
        for i in range(chunks):
            out += self.read_chunk(i)
            if progress:
                progress(i + 1, chunks)
        return bytes(out[:num_bytes])
