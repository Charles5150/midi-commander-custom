"""Customize the PlatformIO upload step to push the packaged DFU file.

With the repository's Python environment in place the upload goes through
python/Update_Firmware.py, which asks a pedal running firmware 0.58 or later
to restart in DFU mode by itself and starts it again afterwards, so nothing
has to be held. Without it, dfu-util is run on its own as before, and the
pedal has to be in DFU mode already.
"""
from __future__ import annotations

import os
from pathlib import Path

Import("env")  # type: ignore  # Provided by PlatformIO at runtime

project_dir = Path(env["PROJECT_DIR"])  # type: ignore[name-defined]
dfu_latest = project_dir / "artifacts" / "dfu" / "platformio-latest.dfu"
venv_python = project_dir / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
updater = project_dir / "python" / "Update_Firmware.py"

if venv_python.exists() and updater.exists():
    cmd = f'"{venv_python}" "{updater}" --yes "{dfu_latest}"'
else:
    # PlatformIO exposes the dfu-util binary path via $DFUUTIL when using the
    # built-in uploader. Fallback to "dfu-util" if the package is missing.
    dfu_util = env.subst("$DFUUTIL")  # type: ignore[name-defined]
    if not dfu_util or dfu_util == "$DFUUTIL":
        dfu_util = "dfu-util"
    cmd = f'"{dfu_util}" --alt 0 --download "{dfu_latest}"'

env.Replace(UPLOADCMD=cmd)  # type: ignore[name-defined]
