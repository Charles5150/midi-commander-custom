"""Read and write one configuration slot of the Midi Commander.

Shared by Flash_to_CSV.py, CSV_to_Flash.py and Backup_Slots.py. Nothing here
prints except through the ``log`` callback, and nothing resets the pedal: the
caller decides when, so several slots can be written with a single restart.
"""

import time
from math import ceil

import lib.binaryUnpacker as unpacker
from lib.configCsv import write_config_csv
from lib.configPacker import pack_config, pack_flash_image
from lib.flashLayout import (
    CONFIG_SIZE, DOUBLE_PRESS_OFFSET, DOUBLE_PRESS_SIZE, EXT2_MARKER, EXT2_OFFSET, EXT2_SIZE, FLASH_PAGE_SIZE,
    SLOT_PAGES,
)
from lib.midiDevice import (
    SYSEX_CMD_ERASE_FLASH,
    SYSEX_CMD_WRITE_FLASH,
    SYSEX_RSP_ERASE_FLASH,
    SYSEX_RSP_WRITE_FLASH,
    DeviceTimeout,
    version_at_least,
)
from lib.settingsBinaryPacker import GLOBAL_SETTINGS_DOUBLE_STORED


class SlotError(Exception):
    """The pedal refused the slot, or holds nothing in it."""


class FlashWriteError(Exception):
    """The pedal answered that it could not erase or write its flash (0.71 on)."""


def _quiet(*_args):
    pass


def select_slot(dev, slot=None):
    """Point the next read or write at ``slot`` (0-3), or at the active slot
    when None. Returns (target, active, valid_slots).

    The target a previous read or write selected stays until the pedal
    restarts, so the active slot must be asked for, never assumed. Firmware
    older than 0.24 has a single configuration: then only slot 0 or None works,
    and the answer is (0, 0, [0]).
    """
    try:
        _, active, _ = dev.select_slot(None)
        wanted = active if slot is None else slot
        target, active, valid = dev.select_slot(wanted)
    except DeviceTimeout:
        if slot not in (None, 0):
            raise SlotError("this firmware has a single configuration; slots need 0.24 or later")
        return 0, 0, [0]
    if slot is not None and target != slot:
        raise SlotError(f"the device did not accept slot {slot + 1}")
    return target, active, valid


def read_image(dev, version, progress=None):
    """Read the selected slot. Returns (config, image): the configuration
    proper, and the same followed by the double press area when the slot has
    one (firmware 0.26 and a slot whose tools wrote it), then the second
    extension area when it has that (0.90, and its marker is there)."""
    data = dev.read_settings(CONFIG_SIZE, progress)
    image = data
    if version_at_least(version, 0, 26) and data[GLOBAL_SETTINGS_DOUBLE_STORED] == 1:
        extension = dev.read_settings(
            DOUBLE_PRESS_SIZE, progress, start=DOUBLE_PRESS_OFFSET)
        image = data.ljust(DOUBLE_PRESS_OFFSET, b"\xff") + extension
    if version_at_least(version, 0, 90):
        head = dev.read_settings(16, None, start=EXT2_OFFSET)
        if head.startswith(EXT2_MARKER):
            ext2 = head + dev.read_settings(EXT2_SIZE - 16, progress, start=EXT2_OFFSET + 16)
            image = image.ljust(EXT2_OFFSET, b"\xff") + ext2
    return data, image


def save_csv(path, data, image, note="Read from device"):
    """Write a slot read with read_image as a configuration CSV. Returns its name."""
    (df_global, df_banks, df_buttons, _, df_exp,
     df_enter, df_sysex, _, df_setlist) = unpacker.unpack_config(image)   # Takeover is in the image
    df_bank_switch = unpacker.unpack_bank_switch_settings(image)   # its labels are in the image
    write_config_csv(
        path,
        df_global,
        df_banks,
        df_buttons,
        note=note,
        df_long_press=unpacker.unpack_long_press_settings(image),
        df_double_press=unpacker.unpack_double_press_settings(image),
        df_expression=df_exp,
        df_bank_enter=df_enter,
        df_sysex=df_sysex,
        df_bank_switch=df_bank_switch,
        df_setlist=df_setlist,
        df_bank_expression=unpacker.unpack_bank_expression_settings(data),
        df_combos=unpacker.unpack_combos(data),
        df_midi_map=unpacker.unpack_midi_map(image),
    )
    return df_global.loc[df_global["Label"] == "ConfigName", "Value"].iloc[0]


def pack_sections(sections):
    """Configuration and full flash image for the sections of a CSV, checked
    against the room a slot has. Raises ValueError when it does not fit."""
    config = pack_config(sections)
    image = pack_flash_image(sections)
    pages = ceil(len(config) / FLASH_PAGE_SIZE)
    if pages > SLOT_PAGES:
        raise ValueError(
            f"the configuration needs {pages} flash pages, more than the "
            f"{SLOT_PAGES} a slot has")
    return config, image


# How often a block whose answer did not come is looked at and sent again
WRITE_TRIES = 4


def _write_chunk(dev, x, chunk, log):
    """Write one 16 byte block. An answer that does not come, seen on macOS now
    and then (#147), is not taken as a failure: the block is read back, which
    says unmistakably whether it is there, as the read answer carries its
    address and the write answer does not, and is sent again if it is not. The
    firmware writes a block already holding the same bytes without complaint.
    """
    data = [SYSEX_CMD_WRITE_FLASH, (x >> 7) & 0x7F, x & 0x7F]
    for byte in chunk:
        data += [byte >> 4, byte & 0x0F]
    for attempt in range(WRITE_TRIES):
        dev.send(data)
        try:
            answer = dev.wait_for_sysex(SYSEX_RSP_WRITE_FLASH, timeout=2.0)
        except DeviceTimeout:
            try:
                dev.flush_input()	# a late answer must not pass for the next block's
                back = dev.read_chunk(x)
            except DeviceTimeout:
                continue
            if back == chunk:
                log(f"No answer for byte {x * 16}, but it was written")
                return
            log(f"No answer for byte {x * 16}: sending it again")
            continue
        # Empty when written; firmware 0.71 on answers 01 when it could not be
        if answer:
            raise FlashWriteError(f"the pedal could not write its flash at byte {x * 16}")
        return
    raise DeviceTimeout(f"no answer from the pedal for byte {x * 16}, {WRITE_TRIES} times")


def write_image(dev, config, image, log=_quiet, progress=None):
    """Erase the selected slot and write ``image`` into it.

    Firmware older than 0.26 has no double press area: the configuration is
    then written on its own, marked as having none. Older than 0.90 has no
    second extension area, so no MIDI map.
    """
    if len(image) > EXT2_OFFSET:
        try:
            new_enough = dev.firmware_at_least(0, 90)
        except DeviceTimeout:
            new_enough = False
        if not new_enough:
            log("WARNING: the MIDI map and the long press labels need firmware 0.90 or later; writing everything else")
            image = image[:EXT2_OFFSET] if config[GLOBAL_SETTINGS_DOUBLE_STORED] == 1 else config  # the double press area stays
    if len(image) > len(config):
        try:
            new_enough = dev.firmware_at_least(0, 26)
        except DeviceTimeout:
            new_enough = False
        if not new_enough:
            log("WARNING: double press needs firmware 0.26 or later; writing everything else")
            image = bytearray(config)
            image[GLOBAL_SETTINGS_DOUBLE_STORED] = 0
            image = bytes(image)

    log("Erasing Flash Settings")
    dev.send([SYSEX_CMD_ERASE_FLASH, 0x42, 0x24])
    if dev.wait_for_sysex(SYSEX_RSP_ERASE_FLASH, timeout=5.0):
        raise FlashWriteError("the pedal could not erase its flash")
    log("Erase Complete")

    chunks = ceil(len(image) / 16)
    for x in range(chunks):
        if progress:
            progress(x + 1, chunks)
        chunk = image[x * 16 : (x + 1) * 16].ljust(16, b"\xff")
        if chunk == b"\xff" * 16:
            continue  # already erased
        try:
            _write_chunk(dev, x, bytes(chunk), log)
        except FlashWriteError as e:
            raise FlashWriteError(f"{e} of {len(image)}") from None
        time.sleep(0.005)
