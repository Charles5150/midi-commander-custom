"""The Boss GT-1000's own System Exclusive dialect, Roland's address model.

The unit is read and written as one address space, in messages shaped like::

    F0 41 <device> 00 00 00 4F <command> <address, four bytes> ... <sum> F7

RQ1 (11) asks for a stretch of it, an address and a size; the unit answers
with DT1 (12), the address and the bytes found there. Every byte of an address
or a size carries seven bits, and the sum makes everything after the command a
multiple of 128.

The pedal's GT1000_Mode uses a small corner of it: the patch number, the patch
name, the patch's sixteen ASSIGNs (which CC switches which effect) and the
switches of those effects. The same numbers are in
``firmware/Core/Src/gt1000.c``, and a test checks the two against each other.
"""

SYSEX_START = 0xF0
SYSEX_END = 0xF7

MANUFACTURER = 0x41         # Roland
DEVICE = 0x7F               # whoever is listening
UNIT_DEVICE = 0x10          # what a unit set to device 17, its default, answers with
MODEL = (0x00, 0x00, 0x00, 0x4F)
CMD_RQ1 = 0x11
CMD_DT1 = 0x12
HEAD_LEN = 8

ADDR_NOTIFY = 0x7F000001        # 1: report what changes, as it changes
ADDR_PATCH_NUMBER = 0x00000000  # four bytes of four bits, 0 - 499
PATCH_NUMBER_SIZE = 4
ADDR_PATCH_NAME = 0x10000000
PATCH_NAME_SIZE = 16
ADDR_ASSIGN = 0x10000300
ASSIGN_STRIDE = 0x40
ASSIGN_COUNT = 16
ASSIGN_SIZE = 0x2C
ASSIGN_READ = 0x0E              # SW to SOURCE

# An ASSIGN's SOURCE: CC 1 to 31 and CC 64 to 95
SOURCE_CC1 = 22
SOURCE_CC31 = 52
SOURCE_CC64 = 53
SOURCE_CC95 = 84

# The effects an ASSIGN can switch on and off: the number of the ON OFF target
# in the ASSIGN TARGET TABLE, and the address of the effect's block, whose
# first byte is its switch.
EFFECTS = [
    ("COMP", 0, 0x10001200),
    ("OD/DS 1", 8, 0x10001300),
    ("OD/DS 2", 17, 0x10001400),
    ("PREAMP 1", 26, 0x10001500),
    ("PREAMP 2", 40, 0x10001600),
    ("NS 1", 54, 0x10001700),
    ("NS 2", 58, 0x10001800),
    ("EQ 1", 62, 0x10001900),
    ("EQ 2", 86, 0x10001A00),
    ("EQ 3", 110, 0x10001B00),
    ("EQ 4", 134, 0x10001C00),
    ("DELAY 1", 158, 0x10001D00),
    ("DELAY 2", 164, 0x10001E00),
    ("DELAY 3", 170, 0x10001F00),
    ("DELAY 4", 176, 0x10002000),
    ("MASTER DELAY", 182, 0x10002100),
    ("CHORUS", 213, 0x10002200),
    ("FX1", 237, 0x10002300),
    ("FX2", 449, 0x10003E00),
    ("FX3", 661, 0x10005900),
    ("REVERB", 873, 0x10007400),
    ("PEDAL FX", 915, 0x10007500),
    ("FX4", 1175, 0x10020100),
]
EFFECT_TARGETS = {name: target for name, target, _ in EFFECTS}
EFFECT_ADDRESSES = {name: address for name, _, address in EFFECTS}


def linear(address: int) -> int:
    """An address of four seven bit bytes as one number."""
    return (((address >> 24) & 0x7F) << 21) | (((address >> 16) & 0x7F) << 14) \
        | (((address >> 8) & 0x7F) << 7) | (address & 0x7F)


def address_bytes(lin: int) -> list:
    return [(lin >> 21) & 0x7F, (lin >> 14) & 0x7F, (lin >> 7) & 0x7F, lin & 0x7F]


def checksum(body) -> int:
    return (128 - (sum(body) & 0x7F)) & 0x7F


def message(command: int, lin: int, data, device: int = DEVICE) -> list:
    body = address_bytes(lin) + [b & 0x7F for b in data]
    return [SYSEX_START, MANUFACTURER, device, *MODEL, command] + body + [checksum(body), SYSEX_END]


def rq1(address: int, size: int) -> list:
    """The pedal asking for ``size`` bytes from ``address`` (as Roland writes it)."""
    return message(CMD_RQ1, linear(address), [0, 0, 0, size])


def dt1(address: int, data, device: int = UNIT_DEVICE) -> list:
    """The unit reporting the bytes at ``address``."""
    return message(CMD_DT1, linear(address), data, device)


def notify() -> list:
    """What the pedal writes so the unit reports changes as they happen."""
    return message(CMD_DT1, linear(ADDR_NOTIFY), [1])


def nibbles(value: int) -> list:
    return [(value >> 12) & 0x0F, (value >> 8) & 0x0F, (value >> 4) & 0x0F, value & 0x0F]


def assign_address(i: int) -> int:
    """Where ASSIGN ``i`` (0-15) is, as Roland writes an address."""
    lin = linear(ADDR_ASSIGN) + i * ASSIGN_STRIDE
    a = address_bytes(lin)
    return (a[0] << 24) | (a[1] << 16) | (a[2] << 8) | a[3]


def source_for_cc(cc: int) -> int:
    if 1 <= cc <= 31:
        return SOURCE_CC1 + cc - 1
    if 64 <= cc <= 95:
        return SOURCE_CC64 + cc - 64
    raise ValueError(f"an ASSIGN listens to CC 1-31 or 64-95, not {cc}")


def assign_data(on: bool, target: int, source: int) -> list:
    """The first ASSIGN_READ bytes of an ASSIGN: SW, TARGET, MIN, MAX, SOURCE."""
    return [1 if on else 0] + nibbles(target) + nibbles(0) + nibbles(1) + [source]


def is_gt1000(msg) -> bool:
    data = list(msg)
    if data and data[0] != SYSEX_START:
        data = [SYSEX_START] + data         # mido hands over the body alone
    return len(data) > HEAD_LEN and data[1] == MANUFACTURER and tuple(data[3:7]) == MODEL


def parse(msg):
    """(command, linear address, data) of a GT-1000 message, or None."""
    data = list(msg)
    if data and data[0] != SYSEX_START:
        data = [SYSEX_START] + data
    if data and data[-1] != SYSEX_END:
        data = data + [SYSEX_END]
    if not is_gt1000(data) or len(data) < HEAD_LEN + 4 + 2:
        return None
    body = data[HEAD_LEN:-2]
    if checksum(body) != data[-2]:
        return None
    lin = (body[0] << 21) | (body[1] << 14) | (body[2] << 7) | body[3]
    return data[7], lin, body[4:]
