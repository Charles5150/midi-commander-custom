"""A value inside a stored SysEx string, and the Roland checksum (firmware 1.30)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from roundtrip_support import DEMO_CSV  # noqa: E402  (also puts python/ on the path)
import lib.binaryUnpacker as unpacker  # noqa: E402
import lib.cmdBinaryPacker as cbp  # noqa: E402
import lib.configPacker as packer  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
from lib.flashLayout import EXP_OFFSET, SYSEX_OFFSET  # noqa: E402

KATANA = "F0 41 00 00 00 00 33 12 60 00 06 39 VV CS F7"


class StringTest(unittest.TestCase):
    def test_value_and_checksum_are_stored_as_marks(self):
        stored = packer.parse_sysex_bytes(KATANA)
        # The checksum sums from the address on, the 8th byte after F0
        self.assertEqual(stored, bytes([0x41, 0, 0, 0, 0, 0x33, 0x12, 0x60, 0, 6, 0x39, 0x80, 0x80 | 7]))
        self.assertEqual(packer.sysex_problem(KATANA), "")
        self.assertEqual(packer.sysex_text(stored), "41 00 00 00 00 33 12 60 00 06 39 VV CS")

    def test_lower_case_and_a_read_request(self):
        stored = packer.parse_sysex_bytes("41 10 00 00 00 5c 11 10 00 00 00 00 00 00 01 cs")
        self.assertEqual(stored[-1], 0x80 | 7)

    def test_what_is_wrong(self):
        for text, problem in [
            ("41 10 42 CS 12 40", "must be the last"),
            ("7E 7F 06 01 CS", "Roland checksum"),
            ("41 10 42 40 00 7F CS", "Roland checksum"),
            ("41 80 12", "80 is over 7F"),
            ("41 10 VW", "not a byte"),
        ]:
            with self.subTest(text):
                self.assertIn(problem, packer.sysex_problem(text))
                self.assertEqual(packer.parse_sysex_bytes(text), b"")

    def test_too_long_is_cut_unless_it_ends_in_a_checksum(self):
        self.assertEqual(len(packer.parse_sysex_bytes(" ".join(["01"] * 24))), 23)
        self.assertEqual(packer.parse_sysex_bytes("41 10 12" + " 01" * 20 + " CS"), b"")

    def test_strings_read_back_as_written(self):
        df = packer.empty_sysex_strings()
        df.loc[3, "Bytes"] = KATANA
        back = unpacker.unpack_sysex_strings(bytes(SYSEX_OFFSET) + packer.pack_sysex_strings(df))
        self.assertEqual(back.loc[3, "Bytes"], "41 00 00 00 00 33 12 60 00 06 39 VV CS")


class CommandTest(unittest.TestCase):
    def cmd(self, **fields):
        base = {"CommandType": "SysEx", "Number_(PC/CC/Note)": "3"}
        return cbp.cmd_sysex(dict(base, **fields))

    def test_send_puts_its_value_in_byte_2(self):
        self.assertEqual(self.cmd(**{"OnValue_(CC/PB)": "64"}), [0x60, 3, 64, 0])
        self.assertEqual(self.cmd(), [0x60, 3, 0, 0], "as before 1.30")

    def test_value_is_a_mode(self):
        self.assertEqual(self.cmd(**{"KeyMode_(Key)": "Value"}), [0x61, 3, 0, 0])
        with self.assertRaises(ValueError):
            self.cmd(**{"KeyMode_(Key)": "Sweep"})

    def test_demo_reads_back(self):
        sections = read_config_csv(DEMO_CSV)
        long = sections["LongPress_Settings"]
        row = long[(long.Bank_Number.astype(str) == "8") & (long.Button_Identifier.astype(str) == "2")].iloc[0]
        self.assertEqual((row["A_CommandType"], row["A_KeyMode_(Key)"]), ("SysEx", "Value"))
        for b0, b2, mode, value in [(0x60, 64, "", "64"), (0x60, 0, "", ""), (0x61, 0, "Value", "")]:
            cmd = unpacker.unpack_command(bytes([b0, 3, b2, 0]))
            self.assertEqual((cmd["CommandType"], cmd["Number_(PC/CC/Note)"]), ("SysEx", "3"))
            self.assertEqual(cmd.get("KeyMode_(Key)", ""), mode)
            self.assertEqual(cmd.get("OnValue_(CC/PB)", ""), value)


class PedalTest(unittest.TestCase):
    def test_the_output_names_the_string(self):
        df = packer.empty_expression_settings()
        df.loc[df.Pedal.astype(str) == "1", "Output"] = "SysEx 3"
        df.loc[df.Pedal.astype(str) == "2", "Output"] = "sysex 15"
        packed = packer.pack_expression_settings(df)
        stride = len(packed) // 2
        self.assertEqual((packed[15], packed[stride + 15]), (0x13, 0x1F))
        back = unpacker.unpack_expression_settings(bytes(EXP_OFFSET) + packed)
        self.assertEqual(list(back.Output), ["SysEx 3", "SysEx 15"])
        with self.assertRaises(ValueError):
            df.loc[df.Pedal.astype(str) == "1", "Output"] = "SysEx 16"
            packer.pack_expression_settings(df)
