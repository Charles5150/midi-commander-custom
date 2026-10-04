"""What the configuration tests share: the CSVs, packing one, and a pedal in memory."""

import os
import sys
from collections import Counter

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from lib.configCsv import read_config_csv  # noqa: E402
from lib.configPacker import pack_config  # noqa: E402
import lib.flashLayout as layout  # noqa: E402

SAMPLE_CSV = os.path.join(os.path.dirname(HERE), "MeloConfig_10_Cmds - RC-600.csv")
DEMO_CSV = os.path.join(os.path.dirname(HERE), "demo-all-features.csv")
FM3_CSV = os.path.join(os.path.dirname(HERE), "templates", "FM3.csv")
HX_STOMP_CSV = os.path.join(os.path.dirname(HERE), "templates", "HX_Stomp.csv")
KEMPER_PLAYER_CSV = os.path.join(os.path.dirname(HERE), "templates", "Kemper_Player.csv")
QUAD_CORTEX_CSV = os.path.join(os.path.dirname(HERE), "templates", "Quad_Cortex.csv")


def pack_csv(path: str) -> bytes:
    """Pack a CSV exactly like CSV_to_Flash.py does."""
    return pack_config(read_config_csv(path))


def norm(value) -> str:
    """Normalise a CSV cell for comparison: NaN/None -> '', '5.0' -> '5'."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).strip()
    if s.lower() == "nan":
        return ""
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
    except ValueError:
        pass
    return s


FIRMWARE = os.path.join(os.path.dirname(os.path.dirname(HERE)), "firmware")


def firmware_source(*name) -> str:
    """A firmware source file, by its path under firmware/Core."""
    with open(os.path.join(FIRMWARE, "Core", *name)) as handle:
        return handle.read()
FLASH_IMAGE2_SIZE = layout.EXT2_OFFSET + layout.EXT2_PAGES * 2048


class FakePedal:
    """A pedal in memory that answers the SysEx the slot tools use: four slots
    of flash, a target selected with SELECT_SLOT, erase, write and read."""

    def __init__(self, version="0.31", active=0, fail_write_at=None, lose_answer_at=(),
                 lose_write_at=()):
        self.version = version
        self.active = active
        self.target = active
        self.flash = {s: bytearray(b"\xff" * FLASH_IMAGE2_SIZE) for s in range(4)}
        self.resets = 0
        self.fail_write_at = fail_write_at  # a byte offset whose write fails, as 0.71 answers
        # Byte offsets whose answer, or whose write message, goes astray once (#147)
        self.lose_answer_at = set(lose_answer_at)
        self.lose_write_at = set(lose_write_at)
        self.writes = Counter()
        self.answer = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_version(self, timeout=1.0):
        return self.version

    def firmware_at_least(self, major, minor, timeout=1.0):
        from lib.midiDevice import version_at_least
        return version_at_least(self.version, major, minor)

    def valid(self):
        # The firmware's rule: a slot holds a configuration when its name is
        # sixteen printable characters
        return [s for s, f in self.flash.items() if all(0x20 <= b <= 0x7E for b in f[16:32])]

    def select_slot(self, slot=None, timeout=1.0):
        if slot is not None:
            self.target = slot
        return self.target, self.active, self.valid()

    def read_settings(self, num_bytes, progress=None, start=0):
        return bytes(self.flash[self.target][start:start + num_bytes])

    def send(self, data):
        from lib import midiDevice as md
        if data[0] == md.SYSEX_CMD_ERASE_FLASH:
            self.flash[self.target] = bytearray(b"\xff" * FLASH_IMAGE2_SIZE)
        elif data[0] == md.SYSEX_CMD_WRITE_FLASH:
            at = ((data[1] << 7) | data[2]) * 16
            self.writes[at] += 1
            if at in self.lose_write_at:
                self.lose_write_at.discard(at)
                self.answer = None
                return
            nib = data[3:]
            self.flash[self.target][at:at + 16] = bytes(
                (nib[2 * i] << 4) | nib[2 * i + 1] for i in range(16))
            self.answer = [1] if at == self.fail_write_at else []
            if at in self.lose_answer_at:
                self.lose_answer_at.discard(at)
                self.answer = None
        elif data[0] == md.SYSEX_CMD_RESET:
            self.resets += 1

    def wait_for_sysex(self, expected_rsp, timeout=2.0):
        from lib.midiDevice import DeviceTimeout
        answer, self.answer = self.answer, []
        if answer is None:
            raise DeviceTimeout(f"No response {expected_rsp} from device")
        return answer

    def flush_input(self):
        pass

    def read_chunk(self, chunk_index, timeout=1.0):
        return bytes(self.flash[self.target][chunk_index * 16:chunk_index * 16 + 16])
