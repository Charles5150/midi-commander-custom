"""Update the pedal's firmware from a .dfu file, with no switches to hold.

Firmware 0.58 and later restart in the stock bootloader's DFU mode when asked
over SysEx, so the whole update is one step from the computer: ask, wait for
the DFU device, flash the file with dfu-util, wait for the pedal to come back.
A pedal already in DFU mode is simply flashed, which is also the way in for
older firmware and for a pedal that has been left in DFU.
"""

import os
import shutil
import struct
import subprocess
import tempfile
import time
import zlib
from pathlib import Path

from lib.midiDevice import DeviceNotFound, DeviceTimeout, MidiCommander, find_port_names

APP_ADDRESS = 0x08003000        # where the stock bootloader looks for the firmware
APP_MAX_SIZE = 76 * 1024        # the linker scripts' limit: the double press areas follow
DFU_VENDOR = 0x0483
DFU_PRODUCT = 0xDF11
DFU_ID = f"{DFU_VENDOR:04x}:{DFU_PRODUCT:04x}"
FIRST_DFU_VERSION = (0, 58)     # the first firmware that restarts in DFU by itself
FLASH_TIMEOUT = 120             # seconds; writing takes about ten


class UpdateError(Exception):
    pass


def _stack_pointer_ok(word: int) -> bool:
    # The bootloader's own test: an image that fails it would leave the
    # pedal starting in DFU for good
    return (word & 0x2FFE0000) == 0x20000000


def read_dfuse(data: bytes):
    """(load address, payload) of a DfuSe file holding one image, checked
    from its signature to its CRC. Raises UpdateError on anything else."""
    if len(data) < 11 + 274 + 8 + 16 or data[:5] != b"DfuSe":
        raise UpdateError("not a DfuSe .dfu file")
    body, suffix = data[:-16], data[-16:]
    if suffix[8:11] != b"UFD" or suffix[11] != 16:
        raise UpdateError("the .dfu file has no DFU suffix")
    crc = struct.unpack("<I", suffix[12:16])[0]
    if crc != (~zlib.crc32(body + suffix[:12]) & 0xFFFFFFFF):
        raise UpdateError("the .dfu file is damaged: its CRC does not match")
    product, vendor = struct.unpack("<HH", suffix[2:6])
    if (vendor, product) not in ((DFU_VENDOR, DFU_PRODUCT), (0xFFFF, 0xFFFF)):
        raise UpdateError(f"the .dfu file is for another device ({vendor:04x}:{product:04x})")

    version, size, targets = data[5], struct.unpack("<I", data[6:10])[0], data[10]
    if version != 1 or size != len(body):
        raise UpdateError("the .dfu file's header does not match its length")
    if targets != 1:
        raise UpdateError(f"the .dfu file holds {targets} images, not one")

    t = body[11:]
    if t[:6] != b"Target":
        raise UpdateError("the .dfu file has no image in it")
    alt = t[6]
    elements = struct.unpack("<I", t[270:274])[0]
    if alt != 0 or elements != 1:
        raise UpdateError("the .dfu file is not a single image for the internal flash")
    address, length = struct.unpack("<II", t[274:282])
    payload = t[282:282 + length]
    if len(payload) != length:
        raise UpdateError("the .dfu file is cut short")
    return address, payload


def check_image(path) -> int:
    """Refuse a file that would not start on the pedal; the image's size if fine."""
    return len(load_image(path))


def load_image(path) -> bytes:
    """The firmware image in a .dfu file, refused if it would not start on the pedal."""
    try:
        data = Path(path).read_bytes()
    except OSError as e:
        raise UpdateError(f"cannot read {path}: {e}") from e
    address, payload = read_dfuse(data)
    if address != APP_ADDRESS:
        raise UpdateError(
            f"the image goes at 0x{address:08X}, not 0x{APP_ADDRESS:08X} behind the "
            "bootloader; build it with the midi_dfu environment")
    if not 8 <= len(payload) <= APP_MAX_SIZE:
        raise UpdateError(f"the image is {len(payload)} bytes, more than the {APP_MAX_SIZE} there is room for")
    if not _stack_pointer_ok(struct.unpack("<I", payload[:4])[0]):
        raise UpdateError("the image does not start with a stack pointer, so the pedal would not run it")
    return payload


def find_dfu_util():
    """dfu-util on the PATH, or the copy PlatformIO keeps; None if neither."""
    found = shutil.which("dfu-util")
    if found:
        return found
    exe = "dfu-util.exe" if os.name == "nt" else "dfu-util"
    bundled = Path.home() / ".platformio" / "packages" / "tool-dfuutil" / "bin" / exe
    return str(bundled) if bundled.exists() else None


def in_dfu(dfu_util) -> bool:
    """A pedal is waiting in the stock bootloader's DFU mode."""
    try:
        p = subprocess.run([dfu_util, "--list"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return dfu_listed(p.stdout + p.stderr)


def dfu_listed(listing: str) -> bool:
    """The pedal's bootloader is in a `dfu-util --list` listing."""
    return any(f"[{DFU_ID}]" in line.lower() and "internal flash" in line.lower()
               for line in listing.splitlines())


def _text(data) -> str:
    if data is None:
        return ""
    return data.decode(errors="replace") if isinstance(data, bytes) else data


def _dfu_util(dfu_util, *args):
    """Run dfu-util on the pedal: (it went well, what it printed)."""
    try:
        p = subprocess.run([dfu_util, "-d", DFU_ID, "-a", "0", *args],
                           capture_output=True, text=True, timeout=FLASH_TIMEOUT)
        return p.returncode == 0, p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        return False, _text(e.stdout) + _text(e.stderr) + "\ndfu-util did not finish"


def _wait(pred, timeout, step=0.25) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(step)
    return pred()


def _pedal_version():
    try:
        with MidiCommander() as dev:
            return dev.get_version().strip()
    except (DeviceNotFound, DeviceTimeout, OSError):
        return None


def ask_for_dfu(log=print):
    """Ask the pedal to restart in DFU mode; the version it was running."""
    try:
        with MidiCommander() as dev:
            try:
                old = dev.get_version().strip()
            except DeviceTimeout:
                old = "unknown"
            try:
                on_its_way = dev.enter_dfu()
            except DeviceTimeout:
                raise UpdateError(
                    f"The firmware on the pedal ({old}) cannot restart in DFU mode by itself; "
                    f"{FIRST_DFU_VERSION[0]}.{FIRST_DFU_VERSION[1]} and later can. Switch the pedal "
                    "off, hold Bank Down and D while switching it on, and run this again.") from None
    except DeviceNotFound:
        raise UpdateError(
            "No pedal found, neither as a MIDI device nor in DFU mode. Check the USB "
            "cable, and close any other program using the pedal.") from None
    if not on_its_way:
        raise UpdateError(
            "The firmware on the pedal is not running behind the stock bootloader, so "
            "there is no DFU mode to restart in. Nothing was changed.")
    log(f"The pedal was running firmware {old} and is restarting in DFU mode.")
    return old


def update(path, log=print, dfu_util=None, dfu_timeout=15.0, back_timeout=20.0):
    """Flash a .dfu file, asking the pedal to go to DFU first if it is not
    there already. The version it comes back with, or None when it did not
    come back as a MIDI device (which only needs the cable plugged in again)."""
    payload = load_image(path)
    dfu_util = dfu_util or find_dfu_util()
    if not dfu_util:
        raise UpdateError(
            "dfu-util not found. Install it (macOS: brew install dfu-util; Linux: your "
            "package manager; Windows: dfu-util.sourceforge.net) and try again.")

    if in_dfu(dfu_util):
        log("The pedal is already in DFU mode.")
    else:
        ask_for_dfu(log)
        if not _wait(lambda: in_dfu(dfu_util), dfu_timeout, step=0.5):
            raise UpdateError(
                "The pedal restarted but did not show up in DFU mode. Unplug the USB cable "
                "and plug it in again: it will start in DFU mode, and this can be run again.")

    log(f"Flashing {Path(path).name} ({len(payload)} bytes)...")
    ok, out = _dfu_util(dfu_util, "-D", str(path))
    if not ok:
        raise UpdateError("dfu-util failed. The pedal stays in DFU mode, so this can be "
                          "run again.\n" + "\n".join(out.strip().splitlines()[-5:]))

    # Left alone the bootloader stays in DFU mode after a download, until the
    # pedal is switched off. dfu-util only asks it to leave after a raw
    # transfer, and after a download that request (with or without
    # "will-reset") went wrong on the pedal, while after reading it works. So
    # the start of the image is read back, which also shows it was written,
    # and the leave goes with that.
    with tempfile.TemporaryDirectory() as tmp:
        head = Path(tmp) / "head.bin"
        ok, out = _dfu_util(dfu_util, "-s", f"0x{APP_ADDRESS:08X}:8:leave", "-U", str(head))
        written = head.read_bytes() if head.exists() else b""
    if written[:8] != payload[:8]:
        raise UpdateError("The image was sent but does not read back as written. The pedal "
                          "stays in DFU mode, so this can be run again.\n"
                          + "\n".join(out.strip().splitlines()[-5:]))

    log("Flashed. Waiting for the pedal to start...")
    if not _wait(lambda: all(find_port_names()), back_timeout, step=0.5):
        return None
    time.sleep(0.5)
    return _pedal_version()
