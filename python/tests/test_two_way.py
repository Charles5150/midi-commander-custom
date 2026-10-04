"""Two way with a Kemper or a GT-1000, against the simulators."""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# roundtrip_support also puts python/ on the path, for lib
from roundtrip_support import DEMO_CSV, KEMPER_PLAYER_CSV  # noqa: E402
import lib.binaryUnpacker as unpacker  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
import lib.configPacker as packer  # noqa: E402
import lib.gt1000Protocol as gp  # noqa: E402
import lib.kemperProtocol as kp  # noqa: E402
import lib.settingsBinaryPacker as sbp  # noqa: E402
import GT1000_Sim as gt1000_sim  # noqa: E402
import Kemper_Sim as kemper_sim  # noqa: E402


class KemperModeTest(unittest.TestCase):
    """Two way talk with a Kemper Profiler (firmware 0.55)."""

    FIRMWARE = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core")

    def firmware(self, name):
        with open(os.path.join(self.FIRMWARE, name)) as handle:
            return handle.read()

    def kemper_c(self):
        return self.firmware(os.path.join("Src", "kemper.c"))

    def define(self, text, name):
        import re

        found = re.search(r"^#define\s+" + name + r"\s+\((0x[0-9A-Fa-f]+|\d+)\)", text, re.M)
        self.assertIsNotNone(found, name)
        return int(found.group(1), 0)

    def test_dialect_matches_firmware(self):
        """The tools and the pedal speak the amp's numbers the same way."""
        text = self.kemper_c()
        self.assertEqual((self.define(text, "KEMPER_MANUF_1"),
                          self.define(text, "KEMPER_MANUF_2"),
                          self.define(text, "KEMPER_MANUF_3")), kp.MANUFACTURER)
        self.assertEqual(self.define(text, "KEMPER_PRODUCT"), kp.PRODUCT)
        self.assertEqual(self.define(text, "KEMPER_DEVICE"), kp.DEVICE)
        self.assertEqual(self.define(text, "KEMPER_FN_PARAM"), kp.FN_PARAM)
        self.assertEqual(self.define(text, "KEMPER_FN_STRING"), kp.FN_STRING)
        self.assertEqual(self.define(text, "KEMPER_FN_REQ_PARAM"), kp.FN_REQ_PARAM)
        self.assertEqual(self.define(text, "KEMPER_FN_REQ_STRING"), kp.FN_REQ_STRING)
        self.assertEqual(self.define(text, "KEMPER_FN_BEACON"), kp.FN_BEACON)
        self.assertEqual(self.define(text, "KEMPER_PAGE_RIG"), kp.PAGE_RIG)
        self.assertEqual(self.define(text, "KEMPER_PARAM_RIG_NAME"), kp.PARAM_RIG_NAME)
        self.assertEqual(self.define(text, "KEMPER_PARAM_ON_OFF"), kp.PARAM_ON_OFF)
        self.assertEqual(self.define(text, "KEMPER_BEACON_SET"), kp.BEACON_SET)
        self.assertEqual(self.define(text, "KEMPER_BEACON_FIRST"), kp.BEACON_FIRST)
        self.assertEqual(self.define(text, "KEMPER_BEACON_AGAIN"), kp.BEACON_AGAIN)
        self.assertEqual(self.define(text, "KEMPER_BEACON_LEASE"), kp.BEACON_LEASE)

    def test_tuner_matches_firmware(self):
        """The tuner's parameters, and the CC the template's tuner button sends (1.07)."""
        text = self.kemper_c()
        for name in ("PAGE_MODE", "PARAM_MODE", "MODE_TUNER", "PAGE_NOTE", "PARAM_NOTE",
                     "PAGE_DEVIANCE", "PARAM_DEVIANCE", "CC_TUNER"):
            self.assertEqual(self.define(text, "KEMPER_" + name), getattr(kp, name), name)
        # the Kemper Player template's TUNR button, lit and dark with the amp
        buttons = read_config_csv(KEMPER_PLAYER_CSV)["Button_Settings"]
        tuner = buttons[buttons["Label"].astype(str).str.strip() == "TUNR"].iloc[0]
        self.assertEqual(int(float(tuner["A_Number_(PC/CC/Note)"])), kp.CC_TUNER)
        self.assertEqual(str(tuner["A_Toggle_(CC/PB/Note)"]).strip().upper(), "Y")
        display = self.firmware(os.path.join("Src", "display.c"))
        names = display.split("note_names[12] = {", 1)[1].split("};", 1)[0]
        self.assertEqual(re.findall(r'"([^"]+)"', names), kp.NOTE_NAMES)

    def test_tuner_messages(self):
        """Byte for byte, as the amp reports its tuner."""
        self.assertEqual(kp.tuner_mode(True), [0xF0, 0x00, 0x20, 0x33, 0x00, 0x00,
                                               0x01, 0x00, 0x7F, 0x7E, 0x00, 0x01, 0xF7])
        self.assertEqual(kp.tuner_note(57)[8:12], [0x7D, 0x54, 0x00, 57])
        self.assertEqual(kp.tuner_deviance(8192)[8:12], [0x7C, 0x0F, 0x40, 0x00])
        self.assertEqual(kp.tuner_deviance(-5)[10:12], [0, 0])          # kept in range
        self.assertEqual(kp.tuner_deviance(20000)[10:12], [0x7F, 0x7F])

    def test_modules_match_firmware(self):
        """The same eight modules, each with its page and its Control Change."""
        import re

        table = self.kemper_c().split("modules[] = {", 1)[1].split("};", 1)[0]
        rows = [tuple(int(v, 0) for v in row)
                for row in re.findall(r"\{\s*(0x[0-9A-Fa-f]+),\s*(\d+),\s*(\d+)\s*\}", table)]
        self.assertEqual(rows, [(page, cc, tails) for _, page, cc, tails in kp.MODULES])

    def test_the_two_asked_for_are_the_last_two(self):
        """The amp reports six by itself; the delay and the reverb it does not."""
        text = self.kemper_c()
        first = self.define(text, "KEMPER_FIRST_ASKED")
        self.assertEqual([name for name, _, _, _ in kp.MODULES][first:], kp.ASKED)
        self.assertEqual([name for name, _, _, _ in kp.MODULES][:first], kp.PUSHED)

    def test_beacon_is_the_message_the_amp_expects(self):
        """Byte for byte, the frame the Profiler answers to."""
        self.assertEqual(kp.beacon(kp.BEACON_FIRST),
                         [0xF0, 0x00, 0x20, 0x33, 0x02, 0x7F,
                          0x7E, 0x00, 0x40, 0x02, 0x23, 0x05, 0xF7])
        self.assertEqual(kp.beacon()[10], kp.BEACON_AGAIN)   # the ones that keep it alive

    def test_the_amp_answers_with_zeroes(self):
        """It puts zeroes where the question carried the product and the device."""
        answer = kp.rig_name("AC30")
        self.assertEqual(answer[4:6], [0x00, 0x00])
        self.assertTrue(kp.is_kemper(answer))
        self.assertEqual(kp.function(answer), kp.FN_STRING)
        # and the firmware knows a message of the amp's by the maker's three
        # bytes alone, never by the two that follow
        source = self.kemper_c()
        reading = source.split("void kemper_sysex_chunk", 1)[1]
        self.assertIn("rx[1] == KEMPER_MANUF_1", reading)
        self.assertNotIn("KEMPER_PRODUCT", reading)
        self.assertNotIn("KEMPER_DEVICE", reading)

    def test_module_ccs_are_the_template_buttons(self):
        """Bank 10 of the Kemper template sends exactly the module CCs."""
        sections = read_config_csv(KEMPER_PLAYER_CSV)
        buttons = sections["Button_Settings"]
        bank = buttons[buttons["Bank_Number"].astype(str).str.strip() == "10"]
        numbers = [int(float(v)) for v in bank["A_Number_(PC/CC/Note)"][:4]]
        self.assertEqual(numbers, [kp.MODULE_CCS[name]
                                   for name in ("Stomp A", "Stomp B", "Delay", "Reverb")])
        toggles = [str(v).strip().upper() for v in bank["A_Toggle_(CC/PB/Note)"][:4]]
        self.assertEqual(toggles, ["Y"] * 4)    # or their LEDs could not follow

    def test_setting_round_trip(self):
        for text, byte in (("N", 0), ("Y", 1)):
            sections = read_config_csv(DEMO_CSV)
            g = sections["Global_Settings"]
            g.loc[g["Label"] == "Kemper_Mode", "Value"] = text
            packed = packer.pack_config(sections)
            self.assertEqual(packed[43], byte, text)
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual(back["Kemper_Mode"], text, text)

    def test_setting_defaults_to_off(self):
        """A configuration written before 0.55 says nothing, and stays quiet."""
        sections = read_config_csv(DEMO_CSV)
        sections["Global_Settings"] = sections["Global_Settings"][
            sections["Global_Settings"]["Label"] != "Kemper_Mode"]
        self.assertEqual(packer.pack_config(sections)[43], 0)
        image = bytearray(packer.pack_config(read_config_csv(DEMO_CSV)))
        image[43] = 0xFF        # an erased byte is not a yes either
        back = unpacker.unpack_config(bytes(image))[0].set_index("Label")["Value"]
        self.assertEqual(back["Kemper_Mode"], "N")

    def test_the_template_asks_for_it(self):
        """The Player answers over the same USB link, so the template says yes."""
        globals_ = read_config_csv(KEMPER_PLAYER_CSV)["Global_Settings"].set_index("Label")
        self.assertEqual(str(globals_.loc["Kemper_Mode", "Value"]).strip(), "Y")

    def test_the_make_believe_amp_answers_what_is_asked(self):
        """Kemper_Sim, without a pedal or a port in sight."""
        import mido

        class Port:
            def __init__(self, queue=None):
                self.queue = list(queue or [])
                self.sent = []

            def poll(self):
                return self.queue.pop(0) if self.queue else None

            def send(self, message):
                self.sent.append(message)

        asked = [mido.Message("sysex", data=kp.beacon()[1:-1]),
                 mido.Message("sysex", data=(list(kp.HEADER) + [kp.FN_REQ_STRING, 0x00,
                                             kp.PAGE_RIG, kp.PARAM_RIG_NAME])[1:]),
                 mido.Message("sysex", data=(list(kp.HEADER) + [kp.FN_REQ_PARAM, 0x00,
                                             kp.MODULE_PAGES["Delay"], kp.PARAM_ON_OFF])[1:])]
        inport, outport = Port(asked), Port()
        amp = kemper_sim.FakeKemper(inport, outport)
        amp.set_module("Delay", True)
        self.assertEqual(amp.poll(), ["beacon", "rig name", "Delay"])
        self.assertEqual(amp.beacons, 1)
        answers = [[0xF0] + list(m.data) + [0xF7] for m in outport.sent]
        self.assertIn(kp.rig_name(amp.rig), answers)
        self.assertIn(kp.module_state("Delay", True), answers)
        self.assertTrue(all(kp.is_kemper(a) for a in answers))

    def test_the_make_believe_amp_has_a_tuner(self):
        """CC 31 opens it, and a note sent opens it too."""
        import mido

        class Port:
            def __init__(self, queue=None):
                self.queue = list(queue or [])
                self.sent = []

            def poll(self):
                return self.queue.pop(0) if self.queue else None

            def send(self, message):
                self.sent.append([0xF0] + list(message.data) + [0xF7])

        inport, outport = Port([mido.Message("control_change", control=31, value=127)]), Port()
        amp = kemper_sim.FakeKemper(inport, outport)
        self.assertEqual(amp.poll(), ["tuner on"])
        self.assertEqual(outport.sent, [kp.tuner_mode(True)])
        amp.set_tuner(False)
        outport.sent.clear()
        amp.tune("A", -100)
        self.assertEqual(outport.sent, [kp.tuner_mode(True), kp.tuner_note(57), kp.tuner_deviance(8092)])

class GT1000ModeTest(unittest.TestCase):
    """Two way talk with a Boss GT-1000 (firmware 1.09)."""

    FIRMWARE = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core")

    def gt1000_c(self):
        with open(os.path.join(self.FIRMWARE, "Src", "gt1000.c")) as handle:
            return handle.read()

    def define(self, text, name):
        found = re.search(r"^#define\s+" + name + r"\s+\((0x[0-9A-Fa-f]+|\d+)(?:UL)?\)", text, re.M)
        self.assertIsNotNone(found, name)
        return int(found.group(1), 0)

    def test_dialect_matches_firmware(self):
        """The tools and the pedal speak the unit's numbers the same way."""
        text = self.gt1000_c()
        self.assertEqual(self.define(text, "GT_MANUF"), gp.MANUFACTURER)
        self.assertEqual(self.define(text, "GT_DEVICE"), gp.DEVICE)
        self.assertEqual(tuple(self.define(text, f"GT_MODEL_{i}") for i in range(1, 5)), gp.MODEL)
        for name in ("CMD_RQ1", "CMD_DT1", "HEAD_LEN", "ADDR_NOTIFY", "ADDR_PATCH_NUMBER",
                     "PATCH_NUMBER_SIZE", "ADDR_PATCH_NAME", "PATCH_NAME_SIZE", "ADDR_ASSIGN",
                     "ASSIGN_STRIDE", "ASSIGN_COUNT", "ASSIGN_SIZE", "ASSIGN_READ",
                     "SOURCE_CC1", "SOURCE_CC31", "SOURCE_CC64", "SOURCE_CC95"):
            self.assertEqual(self.define(text, "GT_" + name), getattr(gp, name), name)

    def test_effects_match_firmware(self):
        table = self.gt1000_c().split("effects[] = {", 1)[1].split("};", 1)[0]
        rows = [(int(t), int(a, 16)) for t, a in re.findall(r"\{\s*(\d+),\s*0x([0-9A-Fa-f]+)UL\s*\}", table)]
        self.assertEqual(rows, [(target, address) for _, target, address in gp.EFFECTS])

    def test_sources_cover_the_two_ranges_of_cc(self):
        self.assertEqual(gp.source_for_cc(1), gp.SOURCE_CC1)
        self.assertEqual(gp.source_for_cc(31), gp.SOURCE_CC31)
        self.assertEqual(gp.source_for_cc(64), gp.SOURCE_CC64)
        self.assertEqual(gp.source_for_cc(95), gp.SOURCE_CC95)
        for cc in (0, 32, 63, 96):
            with self.assertRaises(ValueError):
                gp.source_for_cc(cc)

    def test_messages_byte_for_byte(self):
        """As Roland's MIDI Implementation writes them, sums and all."""
        self.assertEqual(gp.notify(), [0xF0, 0x41, 0x7F, 0x00, 0x00, 0x00, 0x4F, 0x12,
                                       0x7F, 0x00, 0x00, 0x01, 0x01, 0x7F, 0xF7])
        self.assertEqual(gp.rq1(gp.ADDR_PATCH_NAME, 16), [0xF0, 0x41, 0x7F, 0x00, 0x00, 0x00, 0x4F, 0x11,
                                                         0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x10,
                                                         0x60, 0xF7])
        # the sixteenth ASSIGN, 0x40 on from the fifteenth in seven bit bytes
        self.assertEqual(gp.assign_address(1), 0x10000340)
        self.assertEqual(gp.assign_address(15), 0x10000A40)
        answer = gp.dt1(0x10001D00, [1])
        self.assertEqual(gp.parse(answer), (gp.CMD_DT1, gp.linear(0x10001D00), [1]))
        answer[-2] ^= 1
        self.assertIsNone(gp.parse(answer), "a wrong sum is not read")

    def test_setting_round_trip(self):
        for kemper, gt, byte in (("N", "N", 0), ("Y", "N", 1), ("N", "Y", 2)):
            sections = read_config_csv(DEMO_CSV)
            g = sections["Global_Settings"]
            g.loc[g["Label"] == "Kemper_Mode", "Value"] = kemper
            g.loc[g["Label"] == "GT1000_Mode", "Value"] = gt
            packed = packer.pack_config(sections)
            self.assertEqual(packed[43], byte)
            back = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual((back["Kemper_Mode"], back["GT1000_Mode"]), (kemper, gt))

    def test_one_unit_at_a_time(self):
        sections = read_config_csv(DEMO_CSV)
        g = sections["Global_Settings"]
        g.loc[g["Label"] == "Kemper_Mode", "Value"] = "Y"
        g.loc[g["Label"] == "GT1000_Mode", "Value"] = "Y"
        with self.assertRaisesRegex(ValueError, "GT1000_Mode"):
            packer.pack_config(sections)

    def test_setting_defaults_to_off(self):
        """A configuration written before 1.09 says nothing, and stays quiet."""
        sections = read_config_csv(DEMO_CSV)
        sections["Global_Settings"] = sections["Global_Settings"][
            sections["Global_Settings"]["Label"] != "GT1000_Mode"]
        self.assertEqual(packer.pack_config(sections)[43], 0)

    def test_the_firmware_tells_the_two_apart(self):
        with open(os.path.join(self.FIRMWARE, "Inc", "midi_defines.h")) as handle:
            defines = handle.read()
        self.assertEqual(self.define(defines, "TWO_WAY_KEMPER"), sbp.TWO_WAY_KEMPER)
        self.assertEqual(self.define(defines, "TWO_WAY_GT1000"), sbp.TWO_WAY_GT1000)
        self.assertIn("== TWO_WAY_GT1000", self.gt1000_c())
        with open(os.path.join(self.FIRMWARE, "Src", "kemper.c")) as handle:
            self.assertIn("== TWO_WAY_KEMPER", handle.read())

    def test_the_make_believe_unit_answers_what_is_asked(self):
        """GT1000_Sim, without a pedal or a port in sight."""
        import mido

        class Port:
            def __init__(self, queue=None):
                self.queue = list(queue or [])
                self.sent = []

            def poll(self):
                return self.queue.pop(0) if self.queue else None

            def send(self, message):
                self.sent.append([0xF0] + list(message.data) + [0xF7])

        ask = lambda m: mido.Message("sysex", data=m[1:-1])    # noqa: E731
        inport = Port([ask(gp.notify()), ask(gp.rq1(gp.ADDR_PATCH_NAME, 16)),
                       ask(gp.rq1(gp.assign_address(1), gp.ASSIGN_READ)),
                       mido.Message("control_change", control=81, value=127)])
        outport = Port()
        unit = gt1000_sim.FakeGT1000(inport, outport)
        unit.name = "Lead Boost"
        self.assertEqual(unit.poll(), ["notify", "10000000/16", "10000340/14", "DELAY 1 on"])
        self.assertTrue(unit.notify)
        self.assertEqual(outport.sent[0], gp.dt1(gp.ADDR_PATCH_NAME, list(b"Lead Boost      ")))
        self.assertEqual(outport.sent[1], gp.dt1(gp.assign_address(1), gp.assign_data(
            True, gp.EFFECT_TARGETS["DELAY 1"], gp.source_for_cc(81))))
        # the CC switched the effect, and with reports on the unit says so
        self.assertEqual(outport.sent[2], gp.dt1(gp.EFFECT_ADDRESSES["DELAY 1"], [1]))


if __name__ == "__main__":
    unittest.main()
