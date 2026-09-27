"""The web configurator's bridge (lib/webBridge.py) and its schema.

The page packs and unpacks through the bridge, so whatever goes through it
must come out as the command line tools make it.
"""
import glob
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from lib import webBridge as wb  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
from lib.configPacker import pack_config, pack_flash_image  # noqa: E402
from lib.configSchema import COMMAND_SPECS, ENTER_COMMAND_TYPES, SHORT_COMMAND_TYPES, schema  # noqa: E402

CSVS = [os.path.join(ROOT, "demo-all-features.csv")] + sorted(glob.glob(os.path.join(ROOT, "templates", "*.csv")))
WEB = os.path.join(os.path.dirname(ROOT), "web")


def read(path):
    with open(path, "rb") as f:
        return f.read()


class BridgeTest(unittest.TestCase):
    def test_csv_packs_the_same_through_json(self):
        for path in CSVS:
            with self.subTest(os.path.basename(path)):
                sections = read_config_csv(path)
                config, image = wb.pack(wb.csv_to_sections(read(path)))
                self.assertEqual(config, pack_config(sections))
                self.assertEqual(image, pack_flash_image(sections))

    def test_csv_written_back_packs_the_same(self):
        for path in CSVS:
            with self.subTest(os.path.basename(path)):
                text = wb.sections_to_csv(wb.csv_to_sections(read(path)))
                again = wb.csv_to_sections(text.encode("utf-8"))
                self.assertEqual(wb.pack(again), wb.pack(wb.csv_to_sections(read(path))))

    def test_slot_read_back_packs_the_same(self):
        for path in CSVS:
            with self.subTest(os.path.basename(path)):
                config, image = wb.pack(wb.csv_to_sections(read(path)))
                back = wb.image_to_sections(config, image)
                self.assertEqual(wb.pack(back), (config, image))

    def test_empty_cells_are_empty_text(self):
        sections = json.loads(wb.csv_to_sections(read(CSVS[0])))
        cells = [c for row in sections["Button_Settings"]["rows"] for c in row]
        self.assertIn("", cells)
        self.assertNotIn("nan", [c.lower() for c in cells])

    def test_check_says_where(self):
        sections = json.loads(wb.csv_to_sections(read(CSVS[0])))
        self.assertEqual(wb.check(json.dumps(sections)), "")
        btn = sections["Button_Settings"]
        btn["rows"][0][btn["columns"].index("A_CommandType")] = "Nonsense"
        problem = wb.check(json.dumps(sections))
        self.assertIn("Nonsense", problem)

    def test_sizes_match_the_unpacker(self):
        import lib.binaryUnpacker as unpacker
        self.assertEqual(wb.CONFIG_SIZE, unpacker.CONFIG_SIZE)
        self.assertEqual(wb.DOUBLE_PRESS_OFFSET, 12 * 2048)


class SchemaTest(unittest.TestCase):
    def test_json(self):
        self.assertEqual(json.loads(wb.schema_json())["numBanks"], 32)

    def test_every_type_has_its_fields(self):
        no_fields = {"(none)", "Start", "Stop", "Panic"}
        for t in set(SHORT_COMMAND_TYPES) | set(ENTER_COMMAND_TYPES):
            with self.subTest(t):
                self.assertTrue(t in COMMAND_SPECS or t in no_fields)

    def test_fields_name_real_columns(self):
        cols = set(schema()["cmdFields"])
        for t, spec in COMMAND_SPECS.items():
            for f in spec["fields"]:
                with self.subTest(t, col=f["col"]):
                    self.assertIn(f["col"], cols)
                    for col in f.get("when", {}):
                        self.assertIn(col, cols)

    def test_global_fields_cover_the_demo(self):
        labels = {label for _, items in schema()["globalGroups"] for label, _, _ in items}
        demo = set(read_config_csv(CSVS[0])["Global_Settings"]["Label"])
        self.assertEqual(demo - labels, set())

    def test_the_page_loads_every_module_it_needs(self):
        """web/app.js lists the Python files it copies into Pyodide."""
        with open(os.path.join(WEB, "py.js"), encoding="utf-8") as f:
            listed = set(re.findall(r'"(\w+\.py)"', f.read()))
        needed, todo = set(), ["webBridge.py"]
        while todo:
            name = todo.pop()
            if name in needed:
                continue
            needed.add(name)
            with open(os.path.join(ROOT, "lib", name), encoding="utf-8") as f:
                todo += [m + ".py" for m in re.findall(r"^\s*(?:from|import) lib\.(\w+)", f.read(), re.M)]
        self.assertEqual(needed - listed, set())
        self.assertNotIn("midiDevice.py", needed)  # mido does not run in the browser


if __name__ == "__main__":
    unittest.main()
