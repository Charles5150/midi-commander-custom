"""The output each channel goes to by default: the Chan commands put in on the way to the pedal."""

import os
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from roundtrip_support import DEMO_CSV  # noqa: E402
import lib.binaryUnpacker as unpacker  # noqa: E402
import lib.channelPorts as channelPorts  # noqa: E402
from lib.configCsv import read_config_csv, write_sections  # noqa: E402
from lib.configPacker import pack_config, pack_flash_image  # noqa: E402


def ports(*pairs):
    return pd.DataFrame([list(p) for p in pairs], columns=channelPorts.COLUMNS)


def command(kind, channel="", **more):
    cmd = {"CommandType": kind, "Channel_(PC/CC/Note/PB)": channel}
    cmd.update(more)
    return cmd


def listed(commands):
    """A Button_Settings row of bank 0 button 1 holding the commands."""
    row = {"Bank_Number": "0", "Button_Identifier": "1"}
    for i, cmd in enumerate(commands):
        for field, value in cmd.items():
            row[f"{chr(ord('A') + i)}_{field}"] = value
    return row


def kinds(placed):
    return [(c.get("CommandType"), c.get("KeyMode_(Key)", "")) for c in placed]


class WithPortsTest(unittest.TestCase):
    def test_a_chan_above_each_command_on_the_channel(self):
        placed = channelPorts.with_ports([command("PC", "1", **{"Number_(PC/CC/Note)": "5"}),
                                          command("CC", "2"), command("Note", "")], {1: "DIN"})
        self.assertEqual(kinds(placed), [("Chan", "DIN"), ("PC", ""), ("CC", ""), ("Chan", "DIN"), ("Note", "")])

    def test_a_chan_of_its_own_is_kept(self):
        mine = command("Chan", "", **{"KeyMode_(Key)": "Both"})
        placed = channelPorts.with_ports([mine, command("CC", "1")], {1: "USB"})
        self.assertEqual(kinds(placed), [("Chan", "Both"), ("CC", "")])

    def test_driven_commands_are_left(self):
        for driver in ("Ramp", "LFO", "Seq", "Tap", "Exp", "NRPN"):
            placed = channelPorts.with_ports([command(driver), command("CC", "1")], {1: "DIN"})
            self.assertEqual(len(placed), 2, driver)
        placed = channelPorts.with_ports([command("SysEx", **{"KeyMode_(Key)": "Value"}), command("CC", "1")], {1: "DIN"})
        self.assertEqual(len(placed), 2)
        placed = channelPorts.with_ports([command("SysEx"), command("CC", "1")], {1: "DIN"})
        self.assertEqual(kinds(placed)[1], ("Chan", "DIN"))

    def test_an_if_keeps_its_command_and_the_chan(self):
        placed = channelPorts.with_ports([command("If"), command("CC", "1")], {1: "DIN"})
        self.assertEqual([k for k, _ in kinds(placed)], ["If", "Chan", "CC"])

    def test_commands_without_a_channel_are_left(self):
        placed = channelPorts.with_ports([command("SysEx"), command("Start"), command("Bank")], {1: "DIN"})
        self.assertEqual(len(placed), 3)

    def test_the_global_channel_decides(self):
        placed = channelPorts.with_ports([command("CC", "1")], {9: "DIN"}, forced=9)
        self.assertEqual(kinds(placed)[0], ("Chan", "DIN"))
        self.assertEqual(len(channelPorts.with_ports([command("CC", "9")], {9: "DIN"}, forced=1)), 1)

    def test_empty_commands_make_room(self):
        commands = [command("CC", "1")] + [command("") for _ in range(9)]
        placed = channelPorts.with_ports(commands, {1: "DIN"})
        self.assertEqual(len(placed), 10)
        self.assertEqual(kinds(placed)[:2], [("Chan", "DIN"), ("CC", "")])

    def test_a_full_list_says_so(self):
        with self.assertRaisesRegex(ValueError, "20 commands are more than the 10"):
            channelPorts.with_ports([command("CC", "1")] * 10, {1: "DIN"})


class TableTest(unittest.TestCase):
    def test_both_is_no_entry(self):
        self.assertEqual(channelPorts.channel_ports(ports(("1", "both"), ("3", "din"), ("4", ""))), {3: "DIN"})

    def test_bad_entries(self):
        for pairs, message in [((("17", "DIN"),), "1-16"), ((("1", "MIDI"),), "Both, USB or DIN"),
                               ((("2", "DIN"), ("2", "USB")), "twice")]:
            with self.assertRaisesRegex(ValueError, message):
                channelPorts.channel_ports(ports(*pairs))


class ConfigurationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sections = read_config_csv(DEMO_CSV)

    def test_without_ports_nothing_changes(self):
        self.assertIs(channelPorts.apply(self.sections), self.sections)
        with_both = dict(self.sections, Channel_Ports=ports(("1", "Both")))
        self.assertEqual(pack_flash_image(with_both), pack_flash_image(self.sections))

    def test_the_pedal_gets_the_chan(self):
        sections = dict(self.sections, Button_Settings=pd.DataFrame([listed([command("CC", "5", **{
            "Number_(PC/CC/Note)": "20", "OnValue_(CC/PB)": "127", "OffValue_(CC)": "0", "Toggle_(CC/PB/Note)": "N"})])]),
            Channel_Ports=ports(("5", "DIN")))
        buttons = unpacker.unpack_config(pack_config(sections))[2]
        row = buttons[(buttons["Bank_Number"].astype(str) == "0") & (buttons["Button_Identifier"] == "1")].iloc[0]
        self.assertEqual((row["A_CommandType"], row["A_KeyMode_(Key)"]), ("Chan", "DIN"))
        self.assertEqual((row["B_CommandType"], str(row["B_Number_(PC/CC/Note)"])), ("CC", "20"))
        # The sections themselves are as they were
        self.assertEqual(sections["Button_Settings"].iloc[0]["A_CommandType"], "CC")

    def test_every_list_is_covered(self):
        used = [name for name in channelPorts.LIST_SECTIONS if self._uses(self.sections[name], "1")]
        sections = dict(self.sections, Channel_Ports=ports(("1", "USB")))
        placed = channelPorts.apply(sections)
        self.assertGreater(len(used), 1)
        for name in used:
            self.assertIsNot(placed[name], sections[name], name)

    @staticmethod
    def _uses(df, channel):
        return any(str(v).strip() == channel for c in df.columns if c.endswith("_Channel_(PC/CC/Note/PB)")
                   for v in df[c])

    def test_the_error_says_where(self):
        sections = dict(self.sections, Button_Settings=pd.DataFrame([listed([command("CC", "1")] * 10)]),
                        Channel_Ports=ports(("1", "DIN")))
        with self.assertRaisesRegex(ValueError, "Button_Settings 0 1: the default ports"):
            pack_flash_image(sections)

    def test_the_table_is_kept_in_the_csv(self):
        sections = dict(self.sections, Channel_Ports=ports(("3", "DIN"), ("10", "USB")))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ports.csv")
            write_sections(path, sections, "test")
            back = read_config_csv(path)
        self.assertEqual(channelPorts.channel_ports(back["Channel_Ports"]), {3: "DIN", 10: "USB"})
        self.assertEqual(pack_flash_image(back), pack_flash_image(sections))


if __name__ == "__main__":
    unittest.main()
