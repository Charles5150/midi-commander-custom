#!/bin/sh
# Opens the configurator, setting up the Python tools the first time.
# Linux: run it from a terminal, or mark it as executable and double click it.
# The work is done by python/launch.py; this only finds a Python to run it.
cd "$(dirname "$0")" || exit 1

if [ -x .venv/bin/python ]; then
    exec .venv/bin/python python/launch.py "$@"
fi

# A Python that has Tk and for which python-rtmidi comes ready built, if there is one
for p in python3.12 python3.11 python3.10 /usr/local/bin/python3.12 /usr/local/bin/python3.11 /usr/local/bin/python3.10 python3; do
    if command -v "$p" >/dev/null 2>&1 &&
       "$p" -c "import sys, tkinter; sys.exit(not (3, 10) <= sys.version_info[:2] <= (3, 12))" >/dev/null 2>&1; then
        exec "$p" python/launch.py "$@"
    fi
done
if command -v python3 >/dev/null 2>&1; then
    exec python3 python/launch.py "$@"
fi
echo "Python 3 is not installed. Install Python 3.12 (python.org, or your package manager) and run this again."
exit 1
