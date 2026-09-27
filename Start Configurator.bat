@echo off
rem Windows: double click to open the configurator; the first time it also
rem sets up the Python tools. The work is done by python\launch.py; this
rem only finds a Python to run it.
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" python\launch.py %*
    goto done
)

rem Python 3.12, 3.11 or 3.10 if installed: python-rtmidi comes ready built for them
for %%v in (3.12 3.11 3.10) do (
    py -%%v -c "" >nul 2>&1 && (
        py -%%v python\launch.py %*
        goto done
    )
)
py -3 -c "" >nul 2>&1 && (
    py -3 python\launch.py %*
    goto done
)
python -c "" >nul 2>&1 && (
    python python\launch.py %*
    goto done
)
echo Python is not installed. Install Python 3.12 from python.org and run this again.
cmd /c exit 1

:done
rem Keep the window open to read what went wrong
if errorlevel 1 if not defined CI pause
