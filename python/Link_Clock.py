#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ableton Link to MIDI clock: the pedal in time with the band's Link session.

    Link_Clock.py                     join the session, clock the pedal
    Link_Clock.py --quantum 3         bars of 3 beats, as the session's quantum
    Link_Clock.py --no-transport      clock only: no Start, Stop or Continue
    Link_Clock.py --port "IAC"        to another MIDI output (--list shows them)
    Link_Clock.py --stats 10          how steady the clock is, every 10 seconds

Joins the Link session on the network (Ableton Live, Bitwig, Loopy Pro, AUM
and the rest) and sends the pedal 24 clocks a beat at the session's tempo,
whatever app changes it. With Link's Start Stop Sync on in the apps, their
play and stop start and stop the pedal's bar counting, quantized presses and
recorded runs on the session's bar. Turn on Follow the host's clock
(Clock_Follow) on the pedal. Ctrl+C stops it.

Needs aalink, Ableton Link for Python, installed apart (GPL-3.0):
    .venv/bin/pip install aalink
"""
import argparse
import asyncio
import functools
import signal
import sys
import time

import mido

from lib.linkClock import CLOCK, CLOCKS_PER_BEAT, ClockBridge, Jitter
from lib.midiDevice import PRODUCT_NAME, port_kind


def pedal_output(names, wanted=None):
    """The output to clock: one whose name holds `wanted`, or the pedal's own
    port (not its DIN one, nor the tools' one)."""
    if wanted:
        found = [n for n in names if wanted.lower() in n.lower()]
    else:
        found = sorted((n for n in names if PRODUCT_NAME in n and port_kind(n) != "din"),
                       key=lambda n: port_kind(n) != "pedal")
    return found[0] if found else None


def describe(link) -> str:
    peers = link.num_peers
    who = "alone" if not peers else f"{peers} peer" + ("s" if peers != 1 else "")
    state = "playing" if link.playing else "stopped"
    return f"{link.tempo:.1f} BPM, {state}, {who}"


async def run(link, send, bridge, jitter=None, stats=0.0, say=print, ticks=None, clock=time.perf_counter):
    """Clock the session's ticks out through `send` (bytes); `ticks` many, or forever."""
    shown = None
    last_stats = clock()
    while ticks is None or ticks > 0:
        beat = await link.sync(1 / CLOCKS_PER_BEAT)
        msgs = bridge.step(round(beat * CLOCKS_PER_BEAT), bool(link.playing))
        now = clock()
        for m in msgs:
            send(m)
        clocks = sum(m == CLOCK for m in msgs)
        if clocks and jitter is not None:
            jitter.sent(now, link.tempo, clocks)
        if ticks is not None:
            ticks -= 1

        state = describe(link)
        if state != shown:
            say(state)
            shown = state
        if stats and jitter is not None and now - last_stats >= stats:
            s = jitter.summary()
            say(f"{s['clocks']} clocks: {s['mean_ms']:.2f} ms off on average, "
                f"99% within {s['p99_ms']:.2f} ms, at worst {s['max_ms']:.2f} ms")
            jitter.reset()
            last_stats = now


def _interrupt(*_):
    raise KeyboardInterrupt


def main() -> int:
    parser = argparse.ArgumentParser(description="Clock the pedal from an Ableton Link session.")
    parser.add_argument("--port", help="a MIDI output whose name holds this (default: the pedal)")
    parser.add_argument("--list", action="store_true", help="list the MIDI outputs and exit")
    parser.add_argument("--quantum", type=int, default=4,
                        help="beats in a bar, as the session's quantum (default 4)")
    parser.add_argument("--tempo", type=float, default=120.0,
                        help="the tempo to start a session at when no one else is in it (default 120)")
    parser.add_argument("--no-transport", action="store_true",
                        help="only the clock: no Start, Stop or Continue from the session's play state")
    parser.add_argument("--stats", type=float, default=0.0, metavar="SECONDS",
                        help="every so many seconds, how far the clocks are from where they should be")
    args = parser.parse_args()

    names = mido.get_output_names()
    if args.list:
        for n in names:
            print(n)
        return 0
    if args.quantum < 1:
        parser.error("--quantum is at least 1")
    if not 20 <= args.tempo <= 999:
        parser.error("--tempo is 20 to 999, as Link's")

    try:
        import aalink
    except ImportError:
        print("Link_Clock needs aalink, Ableton Link for Python (GPL-3.0), installed apart:\n"
              "    .venv/bin/pip install aalink")
        return 1

    name = pedal_output(names, args.port)
    if name is None:
        print(f"No MIDI output named {args.port!r}" if args.port else "The pedal is not connected")
        return 1

    bridge = ClockBridge(args.quantum, transport=not args.no_transport)
    with mido.open_output(name) as out:
        def send(data):
            out.send(mido.Message.from_bytes(data))

        async def session():
            link = aalink.Link(args.tempo)
            link.quantum = args.quantum
            link.start_stop_sync_enabled = not args.no_transport
            link.enabled = True
            say = functools.partial(print, flush=True)
            say(f"Clocking {name} from Link, bars of {args.quantum}. Ctrl+C stops.")
            await run(link, send, bridge, Jitter(), args.stats, say)

        signal.signal(signal.SIGTERM, _interrupt)   # killed: still the Stop on the way out
        try:
            asyncio.run(session())
        except KeyboardInterrupt:
            pass
        finally:
            for m in bridge.stop():
                send(m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
