"""The Kemper Profiler's own System Exclusive dialect.

The Profiler answers questions, and reports what is changed on it, in messages
shaped like this::

    F0 00 20 33 02 7F <function> <instance> <page> <parameter> ... F7

The pedal's Kemper_Mode uses a small corner of it: the beacon that asks the amp
to keep reporting itself, the rig name, and the on/off state of the effect
modules. The same numbers are in ``firmware/Core/Src/kemper.c``, and a test
checks the two lists against each other.
"""

SYSEX_START = 0xF0
SYSEX_END = 0xF7

MANUFACTURER = (0x00, 0x20, 0x33)
PRODUCT = 0x02          # Profiler, whichever model
DEVICE = 0x7F           # whoever is listening
HEADER = (SYSEX_START,) + MANUFACTURER + (PRODUCT, DEVICE)
# What the amp answers with: it puts zeroes where the question carried the
# product and the device, so neither side may be filtered on.
RESPONSE_HEADER = (SYSEX_START,) + MANUFACTURER + (0x00, 0x00)

FN_PARAM = 0x01         # one parameter, value in two bytes
FN_STRING = 0x03        # one parameter that is text
FN_REQ_PARAM = 0x41     # ask for one parameter
FN_REQ_STRING = 0x43    # ask for one that is text
FN_BEACON = 0x7E        # ask to be told of changes from now on

PAGE_RIG = 0x00
PARAM_RIG_NAME = 0x01
PARAM_ON_OFF = 0x03     # in an effect module's page

# Every effect module: the page it answers on and the Control Change that
# switches it, which is the one a button of the configuration sends.
MODULES = [
    ("Stomp A", 0x32, 17, 0),
    ("Stomp B", 0x33, 18, 0),
    ("Stomp C", 0x34, 19, 0),
    ("Stomp D", 0x35, 20, 0),
    ("Stomp X", 0x38, 22, 0),
    ("Mod", 0x3A, 24, 25),
    ("Delay", 0x3C, 26, 27),
    ("Reverb", 0x3D, 28, 29),
]
MODULE_PAGES = {name: page for name, page, _, _ in MODULES}
MODULE_CCS = {name: cc for name, _, cc, _ in MODULES}
MODULE_TAIL_CCS = {name: tails for name, _, _, tails in MODULES if tails}

# The beacon: 7E 00 40 <parameter set> <flags> <time lease in units of two
# seconds>. Bit 0 of the flags says it is the first one, bit 1 that the answers
# should come back as System Exclusive and bit 5 that the tuner is only worth
# reporting while the tuner is up. It is sent again every half lease.
FN_BEACON_MODE = 0x40
BEACON_SET = 0x02
BEACON_FIRST = 0x23
BEACON_AGAIN = 0x22
BEACON_LEASE = 0x05

# The amp reports these by itself once the beacon is up; the delay and the
# reverb are not among them, so those two have to be asked for.
PUSHED = ["Stomp A", "Stomp B", "Stomp C", "Stomp D", "Stomp X", "Mod"]
ASKED = ["Delay", "Reverb"]


def beacon(flags: int = BEACON_AGAIN, lease: int = BEACON_LEASE) -> list:
    return list(HEADER) + [FN_BEACON, 0x00, FN_BEACON_MODE, BEACON_SET, flags, lease, SYSEX_END]


def parameter(page: int, number: int, value: int) -> list:
    """The amp reporting one parameter, value in two seven bit bytes."""
    return list(RESPONSE_HEADER) + [FN_PARAM, 0x00, page & 0x7F, number & 0x7F,
                           (value >> 7) & 0x7F, value & 0x7F, SYSEX_END]


def module_state(name: str, on: bool) -> list:
    """The amp reporting that one of its effect modules is running, or not."""
    return parameter(MODULE_PAGES[name], PARAM_ON_OFF, 1 if on else 0)


def string_parameter(page: int, number: int, text: str) -> list:
    """The amp reporting a parameter that is text, the rig name among them."""
    body = [b & 0x7F for b in text.encode("ascii", "replace")]
    return list(RESPONSE_HEADER) + [FN_STRING, 0x00, page & 0x7F, number & 0x7F] + body + [0x00, SYSEX_END]


def rig_name(text: str) -> list:
    return string_parameter(PAGE_RIG, PARAM_RIG_NAME, text)


def is_kemper(msg) -> bool:
    """Only the maker's three bytes count: the two after them vary."""
    data = list(msg)
    if data and data[0] != SYSEX_START:
        data = [SYSEX_START] + data         # mido hands over the body alone
    return len(data) > len(HEADER) and tuple(data[1:4]) == MANUFACTURER


def function(msg):
    """The function byte of a Kemper message, or None if it is not one."""
    data = list(msg)
    if data and data[0] != SYSEX_START:
        data = [SYSEX_START] + data
    if not is_kemper(data):
        return None
    return data[len(HEADER)]


def request(msg):
    """(function, page, parameter) of a question asked of the amp, or None."""
    data = list(msg)
    if data and data[0] != SYSEX_START:
        data = [SYSEX_START] + data
    fn = function(data)
    if fn not in (FN_REQ_PARAM, FN_REQ_STRING):
        return None
    body = data[len(HEADER):]
    if len(body) < 4:
        return None
    return fn, body[2], body[3]
