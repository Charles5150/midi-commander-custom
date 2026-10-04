#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Set up the Python tools on first use, then open the configurator.

What the double click launchers in the repository's folder run (Start
Configurator.command on macOS, Start Configurator.bat on Windows,
start-configurator.sh on Linux); it works the same from a terminal:

    python3 python/launch.py            # the configurator
    python3 python/launch.py --check    # set up and check, without opening it

The first time it makes the environment in .venv next to the python folder
and installs requirements.txt into it; again only when requirements.txt
changes. When something is missing it says what to install on this system.
"""
import hashlib
import os
import platform
import subprocess
import sys
import venv
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VENV = ROOT / ".venv"
REQUIREMENTS = HERE / "requirements.txt"
STAMP = VENV / "requirements.installed"
# python-rtmidi comes ready built for these; newer ones compile it
READY_BUILT = ((3, 10), (3, 12))
MODULES = ("mido", "rtmidi", "pandas", "customtkinter", "tkinter")


def venv_python():
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def say(text=""):
    print(text, flush=True)


def help_for_system(problem):
    """What to install for a missing piece, on the system this runs on."""
    system = platform.system()
    version = f"{sys.version_info[0]}.{sys.version_info[1]}"
    if problem == "tk":
        if system == "Darwin":
            return (f"This Python has no Tk, which the configurator's window needs. With Homebrew: "
                    f"brew install python-tk@{version}. Or install Python from python.org, which has it.")
        if system == "Linux":
            return "This Python has no Tk. On Debian or Ubuntu: sudo apt install python3-tk"
        return "This Python has no Tk. Install Python from python.org and tick tcl/tk in the installer."
    if problem == "venv":
        if system == "Linux":
            return f"On Debian or Ubuntu: sudo apt install python{version}-venv  (or python3-venv)"
        return "Install Python from python.org and run this again."
    # problem == "pip": nearly always python-rtmidi having to compile
    lines = []
    if not READY_BUILT[0] <= sys.version_info[:2] <= READY_BUILT[1]:
        lines.append(f"This is Python {version}, and python-rtmidi, which talks MIDI, only comes ready built for "
                     f"Python {READY_BUILT[0][0]}.{READY_BUILT[0][1]} to {READY_BUILT[1][0]}.{READY_BUILT[1][1]}. "
                     f"The simplest fix: install Python 3.12 from python.org, delete the .venv folder and run this again.")
    if system == "Windows":
        lines.append("Compiling it on Windows needs Microsoft's C++ Build Tools.")
    elif system == "Darwin":
        lines.append("Compiling it on macOS needs the command line tools: xcode-select --install")
    else:
        lines.append("Compiling it on Linux needs, on Debian or Ubuntu: "
                     "sudo apt install build-essential libasound2-dev libjack-jackd2-dev")
    return "\n".join(lines)


def fail(text):
    say()
    say(text)
    sys.exit(1)


def make_venv():
    if venv_python().exists():
        return
    say(f"Making the Python environment in {VENV} (once) ...")
    try:
        venv.create(VENV, with_pip=True)
    except Exception as e:           # Debian's python3 without ensurepip, a folder we cannot write
        fail(f"Could not make it: {e}\n{help_for_system('venv')}")
    if not venv_python().exists():
        fail(help_for_system("venv"))


def install():
    digest = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    if STAMP.exists() and STAMP.read_text().strip() == digest:
        return
    say("Installing what the tools need (once, a minute or two) ...")
    cmd = [str(venv_python()), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQUIREMENTS)]
    if subprocess.call(cmd) != 0:
        fail("Installing failed; the messages above say what.\n" + help_for_system("pip"))
    STAMP.write_text(digest + "\n")


def check():
    """Every module the tools use imports in the environment."""
    code = ("import importlib, sys\n"
            "bad = []\n"
            f"for m in {MODULES!r}:\n"
            "    try:\n"
            "        importlib.import_module(m)\n"
            "    except Exception as e:\n"
            "        bad.append(f'{m}: {e}')\n"
            "print('\\n'.join(bad))\n"
            "sys.exit(1 if bad else 0)\n")
    p = subprocess.run([str(venv_python()), "-c", code], capture_output=True, text=True)
    if p.returncode != 0:
        missing = p.stdout.strip() or p.stderr.strip()
        if "tkinter" in missing:
            fail(f"{missing}\n{help_for_system('tk')}")
        STAMP.unlink(missing_ok=True)    # install again next time
        fail(f"{missing}\nSomething did not install; run this again, or delete the .venv folder and run it again.")


def main():
    args = sys.argv[1:]
    only_check = "--check" in args
    args = [a for a in args if a != "--check"]
    if sys.version_info < READY_BUILT[0]:
        fail(f"This is Python {platform.python_version()}; the tools need 3.10 or later. "
             "Install Python 3.12 from python.org.")
    make_venv()
    install()
    check()
    if only_check:
        say(f"Ready: {venv_python()}")
        return
    gui = HERE / "gui_configurator.py"
    sys.exit(subprocess.call([str(venv_python()), str(gui), *args], cwd=str(ROOT)))


if __name__ == "__main__":
    main()
