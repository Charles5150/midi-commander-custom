"""The device dictionary, lib/devices.json: it agrees with the device
templates, every entry packs, and a configuration's device is found."""
import glob
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import lib.deviceDictionary as dd  # noqa: E402
import lib.webBridge as bridge  # noqa: E402
from lib.cmdBinaryPacker import CC_NO_OFF, cmd_cc, cmd_pc  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
from lib.configSchema import CMD_FIELDS  # noqa: E402

TEMPLATES = os.path.join(ROOT, "templates")
# Templates for software, whose CCs are the user's to learn: no device there
SOFTWARE = {"Ableton_Live", "Cantabile", "Gig_Performer", "MainStage"}


def template_sections(name):
    return read_config_csv(os.path.join(TEMPLATES, f"{name}.csv"))


class DictionaryTest(unittest.TestCase):
    def test_every_hardware_template_has_its_device(self):
        names = {os.path.basename(p)[:-4] for p in glob.glob(os.path.join(TEMPLATES, "*.csv"))}
        self.assertEqual(names - SOFTWARE, {d["template"] for d in dd.DEVICES})

    def test_entries_are_well_formed(self):
        for d in dd.DEVICES:
            with self.subTest(d["name"]):
                self.assertTrue(d["maker"] and d["setup"])
                names = [e["name"] for e in d["commands"]]
                self.assertEqual(len(names), len(set(names)), "a name twice")
                for e in d["commands"]:
                    self.assertIn(e["type"], ("CC", "PC"))
                    if e["type"] == "CC":
                        self.assertTrue(0 <= e["number"] <= 127)
                        if not e.get("exp"):
                            self.assertTrue(0 <= e["on"] <= 127)
                            self.assertTrue(0 <= e.get("off", 0) <= 127)

    def test_every_entry_packs(self):
        for d in dd.DEVICES:
            for e in d["commands"]:
                with self.subTest(f"{d['name']}: {e['name']}"):
                    cmd = {f: "" for f in CMD_FIELDS}
                    cmd["Channel_(PC/CC/Note/PB)"] = "3"
                    cmd.update(dd.fields(e))
                    packed = cmd_cc(cmd) if e["type"] == "CC" else cmd_pc(cmd)
                    self.assertEqual(packed[0] & 0x0F, 2)
                    if e["type"] == "CC":
                        self.assertEqual(packed[1] & 0x7F, e["number"])
                        no_off = 0 if e.get("exp") else CC_NO_OFF     # a pedal's CC: toe, then heel
                        self.assertEqual(packed[3], e.get("off", no_off))

    def test_each_entry_is_named_back(self):
        """What a pick writes, the dictionary names as that pick."""
        for d in dd.DEVICES:
            for e in d["commands"]:
                with self.subTest(f"{d['name']}: {e['name']}"):
                    f = dd.fields(e)
                    name = dd.entry_name(d["name"], f["CommandType"], f.get("Number_(PC/CC/Note)"),
                                         f.get("OnValue_(CC/PB)"), f.get("Toggle_(CC/PB/Note)"))
                    if e["type"] == "PC" or not e.get("exp"):
                        self.assertEqual(name, e["name"])
                    else:
                        self.assertIsNotNone(name)

    def test_the_templates_commands_are_named(self):
        """Every CC a device template sends is in its device's map."""
        for d in dd.DEVICES:
            with self.subTest(d["name"]):
                commands = dd.config_commands(template_sections(d["template"]))
                self.assertTrue(commands)
                unnamed = {(c[1], c[2], c[3]) for c in commands
                           if not dd.entry_name(d["name"], c[1], c[2], c[3], c[4])}
                self.assertEqual(unnamed, set())


class GuessTest(unittest.TestCase):
    def test_each_template_is_its_device(self):
        for d in dd.DEVICES:
            with self.subTest(d["name"]):
                found = dd.guess(dd.config_commands(template_sections(d["template"])))
                self.assertEqual(found, {1: d["name"]})

    def test_software_templates_are_no_device(self):
        for name in sorted(SOFTWARE):
            with self.subTest(name):
                self.assertEqual(dd.guess(dd.config_commands(template_sections(name))), {})

    def test_a_pick_wins(self):
        commands = dd.config_commands(template_sections("HX_Stomp"))
        self.assertEqual(dd.guess(commands, {"1": "Volante", "5": "H90", "6": "nothing"}),
                         {1: "Volante", 5: "H90"})

    def test_a_few_ccs_are_no_device(self):
        """Two CCs say too little: tap and bypass are in many maps."""
        self.assertEqual(dd.guess([("1", "CC", "93", "127", "N"), ("1", "CC", "102", "0", "Y")]), {})

    def test_the_global_channel_carries_them(self):
        sections = template_sections("HX_Stomp")
        g = sections["Global_Settings"]
        g.loc[len(g)] = ["Global_Channel", "7"] + [None] * (len(g.columns) - 2)
        self.assertEqual(dd.guess(dd.config_commands(sections)), {7: "HX Stomp"})

    def test_one_number_several_meanings(self):
        self.assertEqual(dd.describe({1: "HX Stomp"}, "1", "CC", "69", "2", "N"), "HX Stomp: Snapshot 3")
        self.assertEqual(dd.describe({1: "HX Stomp"}, "", "CC", "69", "8", "N"), "HX Stomp: Snapshot next")
        self.assertEqual(dd.describe({1: "HX Stomp"}, "1", "CC", "69", "5", "N"), "")
        self.assertEqual(dd.describe({1: "BigSky"}, "1", "CC", "97", "127", "Y"), "BigSky: Infinite hold, latched")
        self.assertEqual(dd.describe({1: "BigSky"}, "1", "CC", "97", "127", "N"), "BigSky: Infinite hold, while held")
        self.assertEqual(dd.describe({1: "HX Stomp"}, "1", "PC", "12"), "HX Stomp: Preset")
        self.assertEqual(dd.describe({1: "HX Stomp"}, "2", "CC", "49"), "")


class BridgeTest(unittest.TestCase):
    def test_the_page_gets_the_dictionary(self):
        devices = json.loads(bridge.devices_json())
        self.assertEqual([d["name"] for d in devices], [d["name"] for d in dd.DEVICES])
        fs1 = next(e for e in devices[0]["commands"] if e["name"] == "FS1")
        self.assertEqual(fs1["fields"], {"CommandType": "CC", "Number_(PC/CC/Note)": "49", "OnValue_(CC/PB)": "127",
                                         "OffValue_(CC)": "0", "Toggle_(CC/PB/Note)": "Y"})

    def test_the_page_gets_the_guess(self):
        with open(os.path.join(TEMPLATES, "Quad_Cortex.csv"), "rb") as f:
            text = bridge.csv_to_sections(f.read())
        self.assertEqual(json.loads(bridge.device_guess(text)), {"1": "Quad Cortex"})
        self.assertEqual(json.loads(bridge.device_guess(text, '{"2": "H90"}')), {"1": "Quad Cortex", "2": "H90"})
        self.assertEqual(bridge.device_name("Quad Cortex", "CC", "43", "4", "Y"), "Scene E")
        self.assertEqual(bridge.device_name("Quad Cortex", "CC", "99", "4", "Y"), "")


if __name__ == "__main__":
    unittest.main()
