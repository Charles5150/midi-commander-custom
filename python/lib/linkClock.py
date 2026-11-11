"""From an Ableton Link session to MIDI clock (Link_Clock.py, #198).

Link has a beat timeline shared by every app in the session, and a play state
when its start/stop sync is on. The pedal follows a host's clock: 24 clocks a
beat, Start, Continue, Stop, and a Song Position before a Continue to say where
in the bar it picks up (Clock_Follow, firmware tempo.c).

ClockBridge turns the session's ticks (a 24th of a beat, numbered from the
session's beat 0) into those bytes. It knows no time and no port, so a test
can drive it tick by tick:

- the first clock goes out on a sixteenth, after a Song Position that puts the
  pedal's bar where the session's is (the quantum is the bar's length), and a
  Continue if the session is playing;
- the session's Start goes out on its next bar, where Link apps start;
- its Stop goes out at once;
- clocks a late wake skipped are sent, up to a beat; a bigger jump, or the
  timeline going back (joining a session moves it), lines the bar up again on
  the next sixteenth, rather than leave the pedal without a clock for up to a
  beat: past half a second it takes the clock for stopped.
"""

CLOCKS_PER_BEAT = 24
CLOCKS_PER_SIXTEENTH = CLOCKS_PER_BEAT // 4
SPP_MAX = 0x3FFF                # the most sixteenths a Song Position holds
BACK_SLACK = 2                  # ticks the timeline may step back and be waited out

CLOCK, START, CONTINUE, STOP = [0xF8], [0xFA], [0xFB], [0xFC]


def song_position(sixteenths: int) -> list:
    sixteenths = max(0, min(SPP_MAX, sixteenths))
    return [0xF2, sixteenths & 0x7F, sixteenths >> 7]


class ClockBridge:
    def __init__(self, quantum: int = 4, transport: bool = True):
        if quantum < 1:
            raise ValueError("a bar has at least one beat")
        self.bar = quantum * CLOCKS_PER_BEAT
        self.transport = transport
        self.last = None            # the last tick a clock went out for
        self.aligned = False
        self.playing = False        # what the pedal was told

    def step(self, tick: int, playing: bool = False) -> list:
        """The messages for the session's tick, in order: lists of bytes."""
        playing = playing and self.transport
        if self.last is not None:
            gap = tick - self.last
            if -BACK_SLACK <= gap <= 0:
                return []           # woke twice for one tick, or a hair back
            if gap > CLOCKS_PER_BEAT or gap < -BACK_SLACK:
                self.aligned = False
                self.last = None

        out = []
        if not self.aligned:
            if tick % CLOCKS_PER_SIXTEENTH:
                return []
            out.append(song_position(tick % self.bar // CLOCKS_PER_SIXTEENTH))
            if playing:
                out.append(CONTINUE)
            self.playing = playing
            self.aligned = True
        elif playing != self.playing:
            if not playing:
                out.append(STOP)
                self.playing = False
            elif tick % self.bar == 0:
                out.append(START)
                self.playing = True

        if self.last is not None:
            out.extend([CLOCK] * (tick - self.last - 1))
        out.append(CLOCK)
        self.last = tick
        return out

    def stop(self) -> list:
        """What to send on the way out: a Stop if the pedal is playing."""
        if self.playing:
            self.playing = False
            return [STOP]
        return []


class Jitter:
    """How far apart the clocks went out, against the session's tempo."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.prev = None
        self.errors = []

    def sent(self, when: float, tempo: float, clocks: int = 1):
        """A clock went out at `when` (seconds), the `clocks`-th since the last."""
        if self.prev is not None and tempo > 0:
            ideal = clocks * 60.0 / (tempo * CLOCKS_PER_BEAT)
            self.errors.append(when - self.prev - ideal)
        self.prev = when

    def summary(self) -> dict:
        """Milliseconds: the mean and worst early or late, and the 99th percentile."""
        if not self.errors:
            return {"clocks": 0, "mean_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0}
        size = sorted(abs(e) * 1000 for e in self.errors)
        return {
            "clocks": len(size),
            "mean_ms": sum(size) / len(size),
            "p99_ms": size[min(len(size) - 1, int(len(size) * 0.99))],
            "max_ms": size[-1],
        }
