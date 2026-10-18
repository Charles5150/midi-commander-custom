"""The hardware self-test (firmware 1.40): a tired switch or a scratchy pot,
found before the gig.

While the configurator keeps the test going, the pedal's switches only count
their presses: nothing is sent and no toggle changes. A press that comes
within 50 ms of the release before it is a bounce, which a sound switch does
not make and a worn one does more and more. The LEDs light as the
configurator says, one after the other, and the expression jacks are read raw
(GET_PEDALS) to find a pot that jumps as it turns.

Tally adds up the pedal's answers and report() puts them in plain words.
"""

from lib.midiDevice import VIRTUAL_SWITCHES

COUNT_WRAP = 128        # the pedal counts in 7 bits
SPIKE = 150             # a reading this far from both its neighbours, out and back: a scratch
STILL = 40              # neighbours this close: the pedal was not moving there
LED_STEP_S = 0.4        # how long each LED stays lit in turn

NAMES = {"DOWN": "Bank Down", "UP": "Bank Up"}


def switch_name(i: int) -> str:
    """The switch's name as it is printed on the pedal: 1, A, Bank Down."""
    sw = VIRTUAL_SWITCHES[i]
    return NAMES.get(sw, sw)


def switch_title(i: int) -> str:
    """The switch in a sentence: Switch 1, Bank Down."""
    sw = VIRTUAL_SWITCHES[i]
    return NAMES.get(sw, f"Switch {sw}")


def led_mask(elapsed_s: float) -> int:
    """The LED lit elapsed_s into the test: each in turn, then all together
    for one step, and round again."""
    step = int(elapsed_s / LED_STEP_S) % (len(VIRTUAL_SWITCHES) + 1)
    return (1 << len(VIRTUAL_SWITCHES)) - 1 if step == len(VIRTUAL_SWITCHES) else 1 << step


def scratches(samples) -> int:
    """Readings that leap away from a pedal held still, or moved slowly, and
    straight back: the wiper losing the track for a moment. A quick sweep
    there and back is not one, as the pedal was not still either side."""
    return sum(
        1
        for a0, a, b, c, c1 in zip(samples, samples[1:], samples[2:], samples[3:], samples[4:])
        if max(abs(a0 - a), abs(a - c), abs(c - c1)) <= STILL and min(abs(b - a), abs(b - c)) >= SPIKE
    )


class Tally:
    """Presses and bounces since the test began, whatever the 7 bits wrap."""

    def __init__(self):
        n = len(VIRTUAL_SWITCHES)
        self.presses = [0] * n
        self.bounces = [0] * n
        self.down = [False] * n
        self.ever_up = [False] * n
        self._last = {"presses": [0] * n, "bounces": [0] * n}
        self.pedals = [[], []]

    def add(self, answer: dict) -> list:
        """Count one SELF_TEST answer; returns the switches that changed."""
        changed = []
        for i in range(len(self.presses)):
            more = (answer["presses"][i] - self._last["presses"][i]) % COUNT_WRAP
            bounced = (answer["bounces"][i] - self._last["bounces"][i]) % COUNT_WRAP
            self.presses[i] += more
            self.bounces[i] += bounced
            if more or bounced or answer["down"][i] != self.down[i]:
                changed.append(i)
            self.down[i] = answer["down"][i]
            self.ever_up[i] = self.ever_up[i] or not answer["down"][i]
        self._last = {"presses": list(answer["presses"]), "bounces": list(answer["bounces"])}
        return changed

    def add_pedals(self, readings):
        """One GET_PEDALS answer: [(raw, cc), (raw, cc)]."""
        for i, (raw, _) in enumerate(readings[:2]):
            self.pedals[i].append(raw)

    def line(self, i: int) -> str:
        """One switch's count, as the test goes."""
        b = self.bounces[i]
        return (f"{switch_name(i)}: {self.presses[i]} press{'es' if self.presses[i] != 1 else ''}"
                + (f", {b} bounce{'s' if b != 1 else ''}" if b else "")
                + (" (down)" if self.down[i] else ""))

    def report(self) -> list:
        """What the test found, the worst first, in plain words."""
        out = []
        for i in range(len(self.presses)):
            if not self.ever_up[i]:
                out.append(f"{switch_title(i)} was down the whole time: it is stuck, or something is resting on it.")
        for i in range(len(self.presses)):
            if self.bounces[i]:
                out.append(
                    f"{switch_title(i)} bounced {self.bounces[i]} time{'s' if self.bounces[i] != 1 else ''} in "
                    f"{self.presses[i]} press{'es' if self.presses[i] != 1 else ''}: it is wearing out and may "
                    "fire twice on stage. Press it a few dozen times more to see if it keeps doing it; "
                    "if it does, the switch wants replacing.")
        for i, samples in enumerate(self.pedals):
            n = scratches(samples)
            if n:
                out.append(
                    f"Expression {i + 1} jumped and came straight back {n} time{'s' if n != 1 else ''}: "
                    "its pot is scratchy, or the cable or jack is loose. Try another cable first.")
        untried = [switch_name(i) for i in range(len(self.presses)) if not self.presses[i] and self.ever_up[i]]
        if untried:
            out.append("Not pressed: " + ", ".join(untried) + ".")
        if not out:
            out.append("Every switch pressed cleanly, with no bounce.")
        return out
