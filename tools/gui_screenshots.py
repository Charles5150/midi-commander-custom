#! env python3
"""Retake the configurator's screenshots in docs/images, on macOS.

    .venv/bin/python tools/gui_screenshots.py            # all of them
    .venv/bin/python tools/gui_screenshots.py monitor    # only some

Opens the configurator on the demo configuration and captures its window
with screencapture. The Virtual Pedal and Monitor shots need the pedal on
USB with the demo configuration active: the monitor one taps a few switches
over SysEx, each toggle twice so every toggle ends as it was, and Bank Up,
then puts the pedal back on the bank it was on.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "docs" / "images"
sys.path.insert(0, str(ROOT / "python"))
os.chdir(ROOT / "python")

import gui_configurator as g  # noqa: E402

SIZE = "1400x820"
BANK_CHANGE_CC = 32     # the demo's Bank_Change_CC


def pump(app, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.update()
        time.sleep(0.01)


def capture(app, name):
    app.lift()
    app.attributes("-topmost", True)
    pump(app, 0.8)
    x, y, w, h = app.winfo_rootx(), app.winfo_rooty(), app.winfo_width(), app.winfo_height()
    subprocess.run(["screencapture", "-x", f"-R{x},{y},{w},{h}", str(IMAGES / f"{name}.png")], check=True)
    print(f"{name}.png")


def select_button(app, bank, button):
    app.tabview.set("Buttons")
    app.bank_selector.set(str(bank))
    app.on_bank_change(str(bank))
    app.button_widgets[button].invoke()
    pump(app, 0.3)


def shot_workflow(app):
    app.tabview.set("Global")
    capture(app, "gui_workflow")


def shot_button_config(app):
    select_button(app, 1, "1")
    editor = app.slot_editors[0]
    editor.learn_button.invoke()             # learning: orange, reads Stop
    pump(app, 0.3)
    capture(app, "gui_button_config")
    g.LearnSession.stop()


def shot_bank_switch(app):
    app.tabview.set("Bank Switch")
    app.bank_switch_selector.set("Up / Long")
    app._on_bank_switch_change("Up / Long")
    capture(app, "gui_bank_switch")


def shot_virtual_pedal(app):
    app.tabview.set("Virtual Pedal")
    app._live_toggle()
    pump(app, 2)
    x, y = app.pedal_canvas.winfo_rootx(), app.pedal_canvas.winfo_rooty()
    w, h = app.pedal_canvas.winfo_width(), app.pedal_canvas.winfo_height()
    app.attributes("-topmost", True)
    pump(app, 0.8)
    subprocess.run(["screencapture", "-x", f"-R{x},{y},{w},{h}",
                    str(IMAGES / "gui_virtual_pedal.png")], check=True)
    print("gui_virtual_pedal.png")
    app._live_disconnect()


def shot_monitor(app):
    import mido
    from lib.midiDevice import MidiCommander, SYSEX_CMD_PRESS_BUTTON, MIDI_MANUF_ID, switch_id
    app.tabview.set("Monitor")
    app._monitor_toggle()
    pump(app, 0.3)
    with MidiCommander() as dev:
        def press(b, hold=0.08):
            for down in (1, 0):
                dev.outport.send(mido.Message("sysex", data=[MIDI_MANUF_ID, SYSEX_CMD_PRESS_BUTTON, switch_id(b), down]))
                pump(app, hold if down else 0.6)
        bank = dev.get_state()["bank"]
        for b in ["1", "2", "A", "1", "2", "A", "UP"]:
            press(b)
        # Back where it was: Up and Down follow the demo's setlist, which
        # would not undo each other, so by the demo's Bank_Change_CC
        dev.outport.send(mido.Message("control_change", channel=0, control=BANK_CHANGE_CC, value=bank))
    pump(app, 1)
    # Only the pedal: its DIN output may be plugged into an interface, whose
    # copy of every message would double the list
    pedal = [p for p in app.monitor_port.cget("values") if "MIDI Commander" in p]
    if pedal:
        app.monitor_port.set(pedal[0])
        app._monitor_filter_changed()
    capture(app, "gui_monitor")
    app._monitor_stop()


SHOTS = {
    "workflow": shot_workflow,
    "button_config": shot_button_config,
    "bank_switch": shot_bank_switch,
    "virtual_pedal": shot_virtual_pedal,
    "monitor": shot_monitor,
}


def main():
    if sys.platform != "darwin":
        sys.exit("macOS only: it uses screencapture")
    names = sys.argv[1:] or list(SHOTS)
    app = g.MidiCommanderGUI()
    app.geometry(SIZE)
    app.load_csv(str(ROOT / "python" / "demo-all-features.csv"))
    pump(app, 1)
    for name in names:
        SHOTS[name](app)
    app._on_close()


if __name__ == "__main__":
    main()
