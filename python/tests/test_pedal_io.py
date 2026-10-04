"""Talking to the pedal: ports, state, text, the editor, slots, backups and firmware updates."""

import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# roundtrip_support also puts python/ on the path, for lib
from roundtrip_support import DEMO_CSV, FakePedal, HERE  # noqa: E402
import lib.binaryUnpacker as unpacker  # noqa: E402
import lib.cmdBinaryPacker as cbp  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
import lib.configPacker as packer  # noqa: E402
import lib.flashLayout as layout  # noqa: E402


class HostTextTest(unittest.TestCase):
    """SysEx SET_TEXT: the host writes on the display (firmware 0.46)."""

    @classmethod
    def setUpClass(cls):
        import re

        root = os.path.join(os.path.dirname(__file__), "..", "..", "firmware")
        text = ""
        for rel in (("Core", "Inc", "midi_defines.h"), ("Core", "Inc", "display.h"), ("Core", "Src", "display.c")):
            with open(os.path.join(root, *rel)) as handle:
                text += handle.read() + "\n"
        cls.firmware = text
        cls.macros = {k: int(v) for k, v in re.findall(r"^#define\s+(\w+)\s+\((\d+)\)", text, re.M)}

    def test_codes_match_firmware(self):
        from lib import midiDevice as md

        self.assertEqual(self.macros["SYSEX_CMD_SET_TEXT"], md.SYSEX_CMD_SET_TEXT)
        self.assertEqual(self.macros["SYSEX_RSP_SET_TEXT"], md.SYSEX_RSP_SET_TEXT)
        places = {"info": "DISPLAY_TEXT_INFO", "name": "DISPLAY_TEXT_NAME",
                  "line": "DISPLAY_TEXT_LINE_LARGE", "small": "DISPLAY_TEXT_LINE_SMALL"}
        for name, macro in places.items():
            self.assertEqual(self.macros[macro], md.TEXT_PLACES[name], name)
        keeps = {"bank": "TEXT_KEEP_BANK", "always": "TEXT_KEEP_ALWAYS", "moment": "TEXT_KEEP_MOMENT"}
        for name, macro in keeps.items():
            self.assertEqual(self.macros[macro], md.TEXT_KEEP[name], name)

    def test_lengths_match_firmware(self):
        import re

        from lib import midiDevice as md

        self.assertEqual(self.macros["DISPLAY_TEXT_MAX"], md.TEXT_MAX)

        def px(name):
            return int(re.search(rf"#define {name}\s+\((\d+)\)", self.firmware).group(1))

        # What fits without scrolling: the room of each place over its font
        shown, name_w, info_x = px("SCREEN_SHOWN_W"), px("NAME_W"), px("INFO_X")
        rooms = {"info": (shown - info_x) // 7, "name": name_w // 11,
                 "line": shown // 11, "small": shown // 7}
        self.assertEqual(rooms, md.TEXT_FITS)

    def test_message(self):
        from lib.midiDevice import text_sysex

        self.assertEqual(text_sysex("Intro"), [0xF0, 0x7D, 72, 2, 0] + list(b"Intro") + [0xF7])
        self.assertEqual(text_sysex("Clean", "info", "moment")[3:5], [0, 2])
        self.assertEqual(text_sysex("SONG", " Name ", "Always")[3:5], [1, 1])
        self.assertEqual(text_sysex("", "line"), [0xF0, 0x7D, 72, 2, 0, 0xF7])

    def test_cut_to_fit_and_seven_bit(self):
        from lib.midiDevice import text_sysex

        self.assertEqual(bytes(text_sysex("Sweet Child O Mine")[5:-1]), b"Sweet Child O Mine")
        self.assertEqual(len(text_sysex("x" * 40, "name")[5:-1]), 32)
        self.assertEqual(bytes(text_sysex("Canción", "small")[5:-1]), b"Cancion")
        self.assertTrue(all(b < 0x80 for b in text_sysex("\u00f1\u00e9\u20ac\x7f", "small")[1:-1]))

    def test_fits_the_receive_buffer(self):
        """The longest message must fit the firmware's SysEx buffer, with room to spare."""
        from lib.midiDevice import text_sysex

        self.assertLessEqual(len(text_sysex("x" * 100, "small")), 64)

    def test_bad_place_or_keep(self):
        from lib.midiDevice import text_sysex

        with self.assertRaises(ValueError):
            text_sysex("x", "middle")
        with self.assertRaises(ValueError):
            text_sysex("x", "line", "forever")

class VirtualPedalTest(unittest.TestCase):
    """SysEx PRESS_BUTTON and GET_STATE, as the configurator's virtual pedal uses them."""

    def test_sysex_codes_match_firmware(self):
        import re
        from lib import midiDevice as md

        path = os.path.join(os.path.dirname(HERE), "..", "firmware", "Core", "Inc", "midi_defines.h")
        with open(path) as f:
            text = f.read()
        for name in ("SYSEX_CMD_PRESS_BUTTON", "SYSEX_RSP_PRESS_BUTTON",
                     "SYSEX_CMD_GET_STATE", "SYSEX_RSP_GET_STATE",
                     "SYSEX_CMD_GET_SCREEN", "SYSEX_RSP_GET_SCREEN",
                     "SYSEX_CMD_SET_PEDAL", "SYSEX_RSP_SET_PEDAL"):
            m = re.search(r"#define\s+" + name + r"\s+\((\d+)\)", text)
            self.assertIsNotNone(m, name)
            self.assertEqual(int(m.group(1)), getattr(md, name), name)

    def test_set_pedal(self):
        from lib import midiDevice as md

        sent = []

        class Fake(md.MidiCommander):
            def __init__(self):
                pass

            def send(self, data):
                sent.append(list(data))

            def wait_for_sysex(self, rsp, timeout):
                return [0, 1]

        dev = Fake()
        dev.set_pedal(0, 0.5)
        dev.set_pedal(1, 1.0)
        dev.set_pedal(1, -0.2)
        dev.set_pedal(0, None)
        self.assertEqual(sent, [[md.SYSEX_CMD_SET_PEDAL, 0, 1, 64, 0],
                                [md.SYSEX_CMD_SET_PEDAL, 1, 1, 127, 127],
                                [md.SYSEX_CMD_SET_PEDAL, 1, 1, 0, 0],
                                [md.SYSEX_CMD_SET_PEDAL, 0, 0, 0, 0]])

    def test_switch_ids(self):
        from lib.midiDevice import switch_id

        self.assertEqual([switch_id(n) for n in ("1", "4", "a", "D", "down", "UP")], [0, 3, 4, 7, 8, 9])
        self.assertEqual(switch_id(9), 9)
        for bad in ("E", 10, -1, "5"):
            with self.assertRaises(ValueError):
                switch_id(bad)

    def test_parse_state(self):
        from lib.midiDevice import parse_state

        data = [2, 1, 0b0010101, 1]                      # bank 2, slot 2, toggles 1,3,5 and D
        data += list(b"FX  ")
        for label in ("NORM", "REVS", "ALWY", "MOMT", "DIM ", "BLNK", "HALF", "NOFF"):
            data += list(label.encode())
        data += [16, 0, 4, 0, 16, 16, 0, 0, 0, 20]       # LED levels, one out of range
        state = parse_state(data)
        self.assertEqual(state["bank"], 2)
        self.assertEqual(state["slot"], 1)
        self.assertEqual(state["toggles"], [True, False, True, False, True, False, False, True])
        self.assertEqual(state["bank_name"], "FX")
        self.assertEqual(state["labels"][4], "DIM")
        self.assertEqual(state["leds"], [16, 0, 4, 0, 16, 16, 0, 0, 0, 16])
        with self.assertRaises(ValueError):
            parse_state(data[:20])

    def test_state_fits_the_sysex_buffer(self):
        """Firmware answer: F0 7D code + 63 data bytes + F7 must fit its 80 byte buffer."""
        size = 3 + 4 + 4 + 8 * 4 + 10 + 3 + 8 + 1 + 1 + 1
        self.assertEqual(size, 67)
        root = os.path.join(os.path.dirname(__file__), "..", "..")
        with open(os.path.join(root, "firmware", "USB_DEVICE", "App", "usbd_midi_if.c")) as handle:
            source = handle.read()
        buffer = int(source.split("#define SYSEX_MAX_LENGTH", 1)[1].split()[0])
        self.assertLessEqual(size, buffer)

    def test_state_safe_mode(self):
        from lib.midiDevice import parse_state

        self.assertFalse(parse_state([0] * 61)["safe_mode"])     # before firmware 0.60
        self.assertFalse(parse_state([0] * 62)["safe_mode"])
        self.assertTrue(parse_state([0] * 61 + [1])["safe_mode"])

    def test_state_health(self):
        from lib.midiDevice import parse_state

        old = parse_state([0] * 63)                               # before firmware 1.05
        self.assertIsNone(old["uptime"])
        self.assertIsNone(old["stack_free"])
        self.assertIsNone(old["watchdog"])
        up, stack = 3 * 86400 + 5, 40676
        data = [0] * 63 + [1] + [up >> (7 * k) & 0x7F for k in range(4)] + [stack >> (7 * k) & 0x7F for k in range(3)]
        state = parse_state(data)
        self.assertTrue(state["watchdog"])
        self.assertEqual(state["uptime"], up)
        self.assertEqual(state["stack_free"], stack)

    def test_state_frame_and_sleep(self):
        from lib.midiDevice import parse_state

        data = [0] * 50 + [0x7F, 0x03, 1]
        state = parse_state(data)
        self.assertEqual(state["frame"], 0x7F | (3 << 7))
        self.assertTrue(state["asleep"])
        self.assertIsNone(parse_state([0] * 50)["frame"])

    @staticmethod
    def pack7(raw):
        """The firmware's packing, sysex_get_screen in usbd_midi_if.c."""
        out = []
        for i in range(0, len(raw), 7):
            chunk = raw[i:i + 7]
            out.append(sum(1 << k for k, b in enumerate(chunk) if b & 0x80))
            out += [b & 0x7F for b in chunk]
        return out

    def test_unpack7_round_trip(self):
        import random
        from lib.midiDevice import SCREEN_PART_BYTES, unpack7

        rng = random.Random(7)
        for raw in (bytes(range(256))[:SCREEN_PART_BYTES], bytes([0xFF] * SCREEN_PART_BYTES),
                    bytes(rng.randrange(256) for _ in range(SCREEN_PART_BYTES))):
            packed = self.pack7(raw)
            self.assertTrue(all(b < 0x80 for b in packed))
            self.assertEqual(unpack7(packed), raw)
        # 65 bytes: 9 groups of 7 and one of 2 -> 75 bytes, an 80 byte answer
        self.assertEqual(len(self.pack7(bytes(SCREEN_PART_BYTES))), 75)

    def test_screen_rows(self):
        from lib.midiDevice import SCREEN_HEIGHT, SCREEN_VISIBLE_WIDTH, SCREEN_WIDTH, screen_rows

        buffer = bytearray(SCREEN_WIDTH * SCREEN_HEIGHT // 8)
        buffer[0] = 0x01                       # x 0, y 0
        buffer[127 + 7 * SCREEN_WIDTH] = 0x80  # x 127, y 63
        buffer[129] = 0xFF                     # column 129: outside the drawn area
        rows = screen_rows(bytes(buffer))
        self.assertEqual((len(rows), len(rows[0])), (SCREEN_HEIGHT, SCREEN_VISIBLE_WIDTH))
        self.assertTrue(rows[0][0] and rows[63][127])
        self.assertEqual(sum(sum(r) for r in rows), 2)

class PedalEditorTest(unittest.TestCase):
    """Editing on the pedal (firmware 0.53)."""

    FIRMWARE = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core")

    def firmware(self, name):
        with open(os.path.join(self.FIRMWARE, name)) as handle:
            return handle.read()

    @staticmethod
    def pack_lock(value):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        g.loc[g["Label"] == "Edit_Lock", "Value"] = value
        return packer.pack_config(sections)

    def test_lock_byte_matches_firmware(self):
        """The setting the firmware reads before opening the editor."""
        import re

        text = self.firmware(os.path.join("Inc", "midi_defines.h"))
        byte = re.search(r"^#define\s+GLOBAL_SETTINGS_EDIT_LOCK\s+\((\d+)\)", text, re.M)
        self.assertEqual(int(byte.group(1)), 42)
        self.assertLess(42, layout.GLOBAL_SIZE)   # still inside the global settings

    def test_lock_round_trip(self):
        for text, byte in (("N", 0), ("Y", 1)):
            packed = self.pack_lock(text)
            self.assertEqual(packed[42], byte, text)
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual(back["Edit_Lock"], text, text)

    def test_lock_defaults_to_open(self):
        """A configuration written before 0.53 leaves that byte erased."""
        image = bytearray(self.pack_lock("Y"))
        image[42] = 0xFF
        back = unpacker.unpack_config(bytes(image))[0].set_index("Label")["Value"]
        self.assertEqual(back["Edit_Lock"], "N")
        sections = read_config_csv(DEMO_CSV)
        sections["Global_Settings"] = sections["Global_Settings"][
            sections["Global_Settings"]["Label"] != "Edit_Lock"]
        self.assertEqual(packer.pack_config(sections)[42], 0)

    def test_editor_settings_exist(self):
        """Every setting the editor offers is a real global settings byte."""
        import re

        editor = self.firmware(os.path.join("Src", "editor.c"))
        defines = self.firmware(os.path.join("Inc", "midi_defines.h"))
        known = dict(re.findall(r"^#define\s+(GLOBAL_SETTINGS_\w+)\s+\((\d+)\)", defines, re.M))
        used = re.findall(r"\{\"[^\"]+\",\s*(GLOBAL_SETTINGS_\w+)", editor)
        self.assertGreaterEqual(len(used), 10)
        # none of them twice, but for the bits of one byte (S_FLAG)
        flags = re.findall(r"\{\"[^\"]+\",\s*(GLOBAL_SETTINGS_\w+),\s*S_FLAG", editor)
        whole = [n for n in used if n not in flags]
        self.assertEqual(len(whole), len(set(whole)))
        self.assertFalse(set(whole) & set(flags))
        for name in used:
            self.assertIn(name, known, name)
            self.assertLess(int(known[name]), layout.GLOBAL_SIZE, name)

    def test_editor_types_are_the_tools_names(self):
        """What the editor calls a command is what the configurator calls it."""
        import re

        editor = self.firmware(os.path.join("Src", "editor.c"))
        block = re.search(r"type_names\[T_COUNT\]\s*=\s*\{([^}]*)\}", editor, re.S)
        names = re.findall(r'"([^"]+)"', block.group(1))
        self.assertEqual(names[0], "---")               # the empty command
        for name in names[1:]:
            self.assertIn(name, cbp.cmd_route_table, name)

    def test_editor_writes_one_page_at_a_time(self):
        """A command never straddles two pages, which the patch refuses."""
        page = 2048
        for base in (layout.COMMANDS_OFFSET, layout.LONG_PRESS_OFFSET):
            for at in range(base, base + layout.NUM_BANKS * 8 * layout.BUTTON_STRIDE, 4):
                self.assertEqual(at // page, (at + 3) // page, at)

class BackupSlotsTest(unittest.TestCase):
    """Backup_Slots.py: every slot out to a folder, and back, byte for byte."""

    @classmethod
    def setUpClass(cls):
        import Backup_Slots
        from lib.slotIO import pack_sections, select_slot, write_image
        cls.tool = Backup_Slots
        cls.pack_sections = staticmethod(pack_sections)
        cls.select_slot = staticmethod(select_slot)
        cls.write_image = staticmethod(write_image)

    def setUp(self):
        # The pause between chunks paces a real pedal; the fake one needs none,
        # and with it these tests spent a hundred seconds asleep
        from unittest import mock
        import lib.slotIO as slot_io
        patcher = mock.patch.object(slot_io, "time", mock.Mock(sleep=lambda s: None))
        patcher.start()
        self.addCleanup(patcher.stop)

    def sections(self, name):
        s = read_config_csv(DEMO_CSV)
        g = s["Global_Settings"]
        g.loc[g["Label"] == "ConfigName", "Value"] = name
        return s

    def pedal_with(self, names):
        """A pedal whose slots hold the demo under the given names, {slot: name}."""
        pedal = FakePedal()
        for slot, name in names.items():
            self.select_slot(pedal, slot)
            self.write_image(pedal, *self.pack_sections(self.sections(name)))
        self.select_slot(pedal, None)
        return pedal

    def run_tool(self, pedal, *argv):
        import argparse
        import contextlib
        import io
        from unittest import mock
        args = argparse.Namespace(folder=argv[1], yes=True)
        with mock.patch.object(self.tool, "MidiCommander", lambda: pedal), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = self.tool.backup(args) if argv[0] == "backup" else self.tool.restore(args)
        return code, out.getvalue()

    def test_backup_then_restore_is_byte_exact(self):
        import tempfile
        source = self.pedal_with({0: "DEMO ONE", 2: "DEMO THREE"})
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "bk")
            self.assertEqual(self.run_tool(source, "backup", folder)[0], 0)
            self.assertEqual(sorted(os.listdir(folder)), ["backup.txt", "slot1.csv", "slot3.csv"])
            with open(os.path.join(folder, "backup.txt"), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("Slot 1: 'DEMO ONE", text)
            self.assertIn("Slot 2: empty", text)

            target = FakePedal()
            code, _ = self.run_tool(target, "restore", folder)
            self.assertEqual(code, 0)
            for slot in range(4):
                self.assertEqual(bytes(target.flash[slot]), bytes(source.flash[slot]), f"slot {slot + 1}")
            self.assertEqual(target.resets, 1)   # one restart for the whole restore

    def test_restore_leaves_other_slots_alone(self):
        import tempfile
        source = self.pedal_with({0: "DEMO ONE"})
        target = self.pedal_with({0: "OLD ONE", 1: "KEEP ME"})
        keep = bytes(target.flash[1])
        with tempfile.TemporaryDirectory() as tmp:
            self.run_tool(source, "backup", tmp)
            code, out = self.run_tool(target, "restore", tmp)
        self.assertEqual(code, 0)
        self.assertEqual(bytes(target.flash[1]), keep)
        self.assertEqual(bytes(target.flash[0]), bytes(source.flash[0]))
        self.assertIn("Left as they are: slot 2, 3, 4", out)

    def test_bad_file_writes_nothing(self):
        import tempfile
        source = self.pedal_with({0: "DEMO ONE", 1: "DEMO TWO"})
        target = self.pedal_with({0: "OLD ONE"})
        before = {s: bytes(f) for s, f in target.flash.items()}
        with tempfile.TemporaryDirectory() as tmp:
            self.run_tool(source, "backup", tmp)
            with open(os.path.join(tmp, "slot2.csv"), "w", encoding="utf-8") as f:
                f.write("* Global_Settings\nnot,a,configuration\n")
            code, out = self.run_tool(target, "restore", tmp)
        self.assertEqual(code, 1)
        self.assertIn("slot2.csv", out)
        self.assertEqual({s: bytes(f) for s, f in target.flash.items()}, before)
        self.assertEqual(target.resets, 0)

    def test_slot_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("slot1.csv", "Slot4.CSV", "slot5.csv", "slot1.csv.bak", "notes.csv"):
                open(os.path.join(tmp, name), "w").close()
            self.assertEqual(sorted(self.tool.slot_files(tmp)), [0, 3])

    def test_empty_pedal(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_tool(FakePedal(), "backup", os.path.join(tmp, "x"))
        self.assertEqual(code, 4)

class BannerTextTest(unittest.TestCase):
    """The banner's own text, kept by the pedal outside the slots (0.63)."""

    FIRMWARE = os.path.join(os.path.dirname(__file__), "..", "..", "firmware")

    def source(self, *name):
        with open(os.path.join(self.FIRMWARE, *name)) as handle:
            return handle.read()

    def define(self, name, *path):
        import re

        m = re.search(rf"#define\s+{name}\s+\((\d+)\)", self.source(*path))
        self.assertIsNotNone(m, name)
        return int(m.group(1))

    def test_numbers_match_firmware(self):
        from lib import midiDevice as md

        self.assertEqual(self.define("SYSEX_CMD_BANNER", "Core", "Inc", "midi_defines.h"), md.SYSEX_CMD_BANNER)
        self.assertEqual(self.define("SYSEX_RSP_BANNER", "Core", "Inc", "midi_defines.h"), md.SYSEX_RSP_BANNER)
        self.assertEqual(self.define("BANNER_TEXT_MAX", "Core", "Inc", "banner_store.h"), md.BANNER_TEXT_MAX)

    def test_message_fits_the_pedal_buffer(self):
        from lib import midiDevice as md

        import re

        m = re.search(r"#define\s+SYSEX_MAX_LENGTH\s+(\d+)", self.source("USB_DEVICE", "App", "usbd_midi_if.c"))
        msg = md.banner_sysex("x" * md.BANNER_TEXT_MAX)
        self.assertLessEqual(len(msg), int(m.group(1)))
        self.assertEqual(msg[:4], [0xF0, md.MIDI_MANUF_ID, md.SYSEX_CMD_BANNER, 1])
        self.assertEqual(msg[-1], 0xF7)

    def test_text_is_cleaned(self):
        from lib import midiDevice as md

        self.assertEqual(md.banner_sysex("Añil  \t"), [0xF0, md.MIDI_MANUF_ID, md.SYSEX_CMD_BANNER, 1,
                                                          ord("A"), ord("n"), ord("i"), ord("l"), 0xF7])
        self.assertEqual(md.banner_sysex(""), [0xF0, md.MIDI_MANUF_ID, md.SYSEX_CMD_BANNER, 1, 0xF7])

    def test_too_long_is_refused(self):
        from lib import midiDevice as md

        with self.assertRaises(ValueError):
            md.banner_sysex("x" * (md.BANNER_TEXT_MAX + 1))
        md.banner_sysex("x" * md.BANNER_TEXT_MAX + "   ")   # trailing spaces do not count

    def test_page_is_outside_everything_else(self):
        # 0x0803A000: past slot 3 and below 256 kB, never written by the tools
        header = self.source("Core", "Inc", "flash_midi_settings.h")
        self.assertIn("#define FLASH_BANNER_ADDR		(FLASH_SLOTN_ADDR(CONFIG_SLOTS))", header)
        page, slot = 0x800, 12 * 0x800
        slot0, journal = 0x08020000, 4 * 0x800
        banner = slot0 + slot + journal + 3 * slot
        self.assertEqual(banner, 0x0803A000)
        self.assertLessEqual(banner + page, 0x08000000 + 256 * 1024)

class LatencyTest(unittest.TestCase):
    """The pedal times its own presses (0.65): the SysEx that reads them."""

    def source(self, *path):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "firmware")
        with open(os.path.join(root, *path)) as f:
            return f.read()

    def define(self, name, *path):
        import re

        m = re.search(rf"#define\s+{name}\s+\((\d+)\)", self.source(*path))
        self.assertIsNotNone(m, name)
        return int(m.group(1))

    def test_numbers_match_firmware(self):
        from lib import midiDevice as md

        self.assertEqual(self.define("SYSEX_CMD_GET_LATENCY", "Core", "Inc", "midi_defines.h"), md.SYSEX_CMD_GET_LATENCY)
        self.assertEqual(self.define("SYSEX_RSP_GET_LATENCY", "Core", "Inc", "midi_defines.h"), md.SYSEX_RSP_GET_LATENCY)

    def test_answer_fits_the_pedal_buffer(self):
        import re

        samples = self.define("LATENCY_SAMPLES", "Core", "Inc", "latency.h")
        m = re.search(r"#define\s+SYSEX_MAX_LENGTH\s+(\d+)", self.source("USB_DEVICE", "App", "usbd_midi_if.c"))
        # F0 7D 79, count (2), slowest (3), the samples (3 each), F7
        self.assertLessEqual(3 + 2 + 3 + 3 * samples + 1, int(m.group(1)))

    def test_parse(self):
        from lib import midiDevice as md

        def us(v):
            return [(v >> 14) & 0x7F, (v >> 7) & 0x7F, v & 0x7F]

        got = md.parse_latency([1, 2] + us(4500) + us(250) + us(123456))
        self.assertEqual(got["count"], 130)
        self.assertEqual(got["max"], 4.5)
        self.assertEqual(got["samples"], [0.25, 123.456])
        self.assertEqual(md.parse_latency([0, 0, 0, 0, 0]), {"count": 0, "max": 0.0, "samples": []})

class FirmwareUpdateTest(unittest.TestCase):
    """Entering DFU mode from software, and the files it will flash (0.58)."""

    ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

    def source(self, *name):
        with open(os.path.join(self.ROOT, *name)) as handle:
            return handle.read()

    def image(self, payload=None, address=None, **kw):
        sys.path.insert(0, os.path.join(self.ROOT, "tools"))
        import bin_to_dfuse

        from lib import firmwareUpdate as fu

        if payload is None:
            # A stack pointer at the top of RAM, then a reset vector
            payload = struct.pack("<II", 0x20010000, 0x08003135) + bytes(1000)
        fields = dict(alt_setting=0, target_name="ST...", vendor=0x0483, product=0xDF11,
                      device=0, dfu_version=0x011A)
        fields.update(kw)
        return bin_to_dfuse.generate_dfuse(
            payload, load_address=fu.APP_ADDRESS if address is None else address, **fields)

    def check(self, data):
        import tempfile

        from lib import firmwareUpdate as fu

        with tempfile.NamedTemporaryFile(suffix=".dfu", delete=False) as handle:
            handle.write(data)
        try:
            return fu.check_image(handle.name)
        finally:
            os.unlink(handle.name)

    def test_constants_match_firmware(self):
        import re

        from lib import midiDevice as md

        defines = self.source("firmware", "Core", "Inc", "midi_defines.h")
        for name in ("SYSEX_CMD_ENTER_DFU", "SYSEX_RSP_ENTER_DFU"):
            value = re.search(rf"^#define\s+{name}\s+\((\d+)\)", defines, re.M)
            self.assertIsNotNone(value, name)
            self.assertEqual(int(value.group(1)), getattr(md, name), name)
        # The check bytes the firmware wants are the ones the tool sends
        handler = self.source("firmware", "USB_DEVICE", "App", "usbd_midi_if.c")
        check = re.search(r"data_packet_start\[0\] != (0x[0-9A-F]+) \|\| data_packet_start\[1\] != "
                          r"(0x[0-9A-F]+)\)\{\n\t\treturn;\n\t\}\n\n\tbool possible", handler)
        self.assertIsNotNone(check)
        self.assertEqual((int(check.group(1), 16), int(check.group(2), 16)), md.ENTER_DFU_CHECK)

    def test_addresses_match_the_linker(self):
        import re

        from lib import firmwareUpdate as fu

        # Where the firmware zeroes the word is where it is linked, and the
        # biggest image the tool accepts is the room the linker gives it
        entry = self.source("firmware", "Core", "Src", "dfu_entry.c")
        self.assertIn("#define APP_START\t\t(FLASH_BASE + 0x3000U)", entry)
        ld = self.source("firmware", "STM32F103RETX_FLASH_DFU.ld")
        m = re.search(r"FLASH\s+\(rx\)\s+:\s+ORIGIN = \(0x8000000 \+ (0x[0-9A-F]+)\),\s+"
                      r"LENGTH = \((\d+)K - (0x[0-9A-F]+)\)", ld)
        self.assertIsNotNone(m)
        self.assertEqual(0x08000000 + int(m.group(1), 16), fu.APP_ADDRESS)
        self.assertEqual(int(m.group(2)) * 1024 - int(m.group(3), 16), fu.APP_MAX_SIZE)
        # Only a build that runs behind the bootloader may do it
        self.assertIn("return (uint32_t)g_pfnVectors == APP_START;", entry)

    def test_the_bootloaders_own_test(self):
        from lib import firmwareUpdate as fu

        # The stack pointer test the stock bootloader makes before starting the
        # firmware: zero is what the firmware writes to stay in DFU
        self.assertTrue(fu._stack_pointer_ok(0x20010000))
        self.assertTrue(fu._stack_pointer_ok(0x20005000))
        self.assertFalse(fu._stack_pointer_ok(0x00000000))
        self.assertFalse(fu._stack_pointer_ok(0xFFFFFFFF))   # erased flash
        self.assertFalse(fu._stack_pointer_ok(0x08003135))

    def test_a_good_image_passes(self):
        self.assertEqual(self.check(self.image()), 1008)
        # And the one the build makes, when it has been built
        latest = os.path.join(self.ROOT, "artifacts", "dfu", "platformio-latest.dfu")
        if os.path.exists(latest):
            with open(latest, "rb") as handle:
                self.assertGreater(self.check(handle.read()), 40000)

    def test_images_that_would_not_start_are_refused(self):
        from lib import firmwareUpdate as fu

        good = self.image()
        bad = {
            "not a dfu file": b"\x00" * 400,
            "a raw binary": struct.pack("<II", 0x20010000, 0x08003135) + bytes(1000),
            "linked at the start of flash": self.image(address=0x08000000),
            "no stack pointer": self.image(payload=bytes(1008)),
            "too big": self.image(payload=struct.pack("<II", 0x20010000, 0x08003135)
                                  + bytes(fu.APP_MAX_SIZE)),
            "cut short": good[:-100],
            "damaged": good[:400] + bytes([good[400] ^ 0xFF]) + good[401:],
            "another device": self.image(product=0x1234),
        }
        for why, data in bad.items():
            with self.assertRaises(fu.UpdateError, msg=why):
                self.check(data)

    def test_dfu_listing(self):
        from lib import firmwareUpdate as fu

        # What dfu-util --list printed for the pedal in DFU mode
        listing = (
            'Found DFU: [0483:df11] ver=0200, devnum=1, cfg=1, intf=0, path="0-1", alt=2, '
            'name="@NOR Flash : M29W128F/0x64000000/0256*64Kg", serial="48EB874D3938"\n'
            'Found DFU: [0483:df11] ver=0200, devnum=1, cfg=1, intf=0, path="0-1", alt=0, '
            'name="@Internal Flash  /0x08000000/06*002Ka,250*002Kg", serial="48EB874D3938"\n')
        self.assertTrue(fu.dfu_listed(listing))
        self.assertFalse(fu.dfu_listed("dfu-util 0.11\n\nCopyright 2005-2009 Weston Schmidt\n"))
        self.assertFalse(fu.dfu_listed(
            'Found DFU: [1234:5678] ver=0100, alt=0, name="@Internal Flash  /0x08000000/64*002Kg"\n'))

class AnswerWaitTest(unittest.TestCase):
    """Answers for an earlier request are skipped, but only for the timeout."""

    def test_stale_answers_end_in_a_timeout(self):
        import time

        import mido

        from lib import midiDevice as md

        class Port:
            def poll(self):
                # Always the answer for another chunk
                return mido.Message("sysex", data=[md.MIDI_MANUF_ID, md.SYSEX_RSP_READ_FLASH, 0x7F, 0x7F] + [0] * 32)

        dev = md.MidiCommander()
        dev.inport = Port()
        dev.send = lambda data: None
        started = time.monotonic()
        with self.assertRaises(md.DeviceTimeout):
            dev.read_chunk(0, timeout=0.2)
        self.assertLess(time.monotonic() - started, 1.0)


class FlashWriteErrorTest(unittest.TestCase):
    """0.71 answers a write it could not do with 01, and the tools stop and say so."""

    def setUp(self):
        from unittest import mock
        import lib.slotIO as slot_io
        patcher = mock.patch.object(slot_io, "time", mock.Mock(sleep=lambda s: None))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_write_image_raises(self):
        from lib.slotIO import FlashWriteError, pack_sections, write_image
        pedal = FakePedal(fail_write_at=160)
        with self.assertRaises(FlashWriteError) as ctx:
            write_image(pedal, *pack_sections(read_config_csv(DEMO_CSV)))
        self.assertIn("at byte 160", str(ctx.exception))
        # nothing written after the chunk that failed
        self.assertEqual(bytes(pedal.flash[0][176:192]), b"\xff" * 16)

    def test_a_lost_answer_is_not_a_failure(self):
        """#147: the block was written, only its answer went astray: read back,
        found, not sent again."""
        from lib.slotIO import pack_sections, write_image
        config, image = pack_sections(read_config_csv(DEMO_CSV))
        pedal = FakePedal(version="0.90", lose_answer_at={160, 4096})
        write_image(pedal, config, image)
        self.assertEqual(bytes(pedal.flash[0][:len(image)]), image)
        self.assertEqual((pedal.writes[160], pedal.writes[4096]), (1, 1))

    def test_a_lost_write_is_sent_again(self):
        """#147: the message itself went astray: the block reads erased and goes again."""
        from lib.slotIO import pack_sections, write_image
        config, image = pack_sections(read_config_csv(DEMO_CSV))
        pedal = FakePedal(version="0.90", lose_write_at={160, 4096})
        write_image(pedal, config, image)
        self.assertEqual(bytes(pedal.flash[0][:len(image)]), image)
        self.assertEqual((pedal.writes[160], pedal.writes[4096]), (2, 2))

    def test_a_pedal_that_never_answers_stops_it(self):
        from lib.midiDevice import DeviceTimeout
        from lib.slotIO import WRITE_TRIES, pack_sections, write_image

        class Deaf(FakePedal):
            def send(self, data):
                super().send(data)
                from lib import midiDevice as md
                if data[0] == md.SYSEX_CMD_WRITE_FLASH and ((data[1] << 7) | data[2]) * 16 == 160:
                    self.flash[self.target][160:176] = b"\xff" * 16
                    self.answer = None

        pedal = Deaf()
        with self.assertRaises(DeviceTimeout) as ctx:
            write_image(pedal, *pack_sections(read_config_csv(DEMO_CSV)))
        self.assertIn("byte 160", str(ctx.exception))
        self.assertEqual(pedal.writes[160], WRITE_TRIES)

    def test_csv_to_flash_reports_it(self):
        import argparse
        import contextlib
        import io
        from unittest import mock
        import CSV_to_Flash as tool
        pedal = FakePedal(fail_write_at=160)
        args = argparse.Namespace(csv_file=DEMO_CSV, slot=None, yes=True)
        with mock.patch.object(tool, "MidiCommander", lambda: pedal), \
                mock.patch.object(tool, "select_slot", lambda dev, slot: (0, 0, [0])), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = tool.main(args)
        self.assertEqual(code, 4)
        self.assertIn("could not write its flash", out.getvalue())
        self.assertEqual(pedal.resets, 0)


if __name__ == "__main__":
    unittest.main()
