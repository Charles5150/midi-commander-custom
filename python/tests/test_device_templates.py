"""The FM3, HX Stomp, Quad Cortex and Kemper Player templates."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# roundtrip_support also puts python/ on the path, for lib
from roundtrip_support import FM3_CSV, HX_STOMP_CSV, KEMPER_PLAYER_CSV, QUAD_CORTEX_CSV, norm  # noqa: E402
import lib.binaryUnpacker as unpacker  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
import lib.configPacker as packer  # noqa: E402


class Fm3TemplateTest(unittest.TestCase):
    """The FM3 template packs and reads back as the template describes."""

    @classmethod
    def setUpClass(cls):
        packed = packer.pack_config(read_config_csv(FM3_CSV))
        tables = unpacker.unpack_config(packed)
        cls.banks, cls.buttons, cls.enter = tables[1], tables[2], tables[5]

    def button(self, bank, btn):
        b = self.buttons
        return b[(b["Bank_Number"].astype(str) == str(bank)) & (b["Button_Identifier"] == btn)].iloc[0]

    def test_preset_banks_load_their_preset(self):
        for bank in (0, 7, 29):
            row = self.enter[self.enter["Bank_Number"].astype(str) == str(bank)].iloc[0]
            self.assertEqual(row["A_CommandType"], "PC")
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), str(bank))

    def test_scene_buttons(self):
        for btn, value in (("1", 0), ("4", 3), ("A", 4), ("B", 5)):
            row = self.button(3, btn)
            self.assertEqual(row["A_CommandType"], "CC")
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), "34")
            self.assertEqual(norm(row["A_OnValue_(CC/PB)"]), str(value))
            self.assertEqual(norm(row["A_OffValue_(CC)"]), "")   # sends nothing
            self.assertEqual(row["A_Toggle_(CC/PB/Note)"], "Y")
            self.assertEqual(norm(row["Group"]), "1")

    def test_tap_sends_only_on_the_press(self):
        row = self.button(0, "D")
        self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), "14")
        self.assertEqual(norm(row["A_OffValue_(CC)"]), "")
        self.assertEqual(row["A_Toggle_(CC/PB/Note)"], "N")

    def test_looper_and_fx_banks(self):
        names = self.banks.set_index(self.banks["Bank_Number"].astype(str))["Bank_Name_Large"]
        self.assertEqual(names["30"], "LOOP")
        self.assertEqual(names["31"], "FX")
        self.assertEqual(norm(self.button(30, "1")["A_Number_(PC/CC/Note)"]), "20")
        self.assertEqual(self.button(31, "A")["A_Toggle_(CC/PB/Note)"], "Y")

class HxStompTemplateTest(unittest.TestCase):
    """The HX Stomp template packs and reads back as the template describes."""

    @classmethod
    def setUpClass(cls):
        packed = packer.pack_config(read_config_csv(HX_STOMP_CSV))
        tables = unpacker.unpack_config(packed)
        cls.globals, cls.banks, cls.buttons, cls.enter = tables[0], tables[1], tables[2], tables[5]

    def button(self, bank, btn):
        b = self.buttons
        return b[(b["Bank_Number"].astype(str) == str(bank)) & (b["Button_Identifier"] == btn)].iloc[0]

    def test_preset_banks_load_their_preset(self):
        names = self.banks.set_index(self.banks["Bank_Number"].astype(str))["Bank_Name_Large"]
        for bank, name in ((0, "01A"), (4, "02B"), (29, "10C")):
            row = self.enter[self.enter["Bank_Number"].astype(str) == str(bank)].iloc[0]
            self.assertEqual(row["A_CommandType"], "PC")
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), str(bank))
            self.assertEqual(names[str(bank)], name)

    def test_snapshot_buttons(self):
        for btn, value in (("1", 0), ("2", 1), ("3", 2)):
            row = self.button(5, btn)
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), "69")
            self.assertEqual(norm(row["A_OnValue_(CC/PB)"]), str(value))
            self.assertEqual(norm(row["A_OffValue_(CC)"]), "")   # sends nothing
            self.assertEqual(norm(row["Group"]), "1")

    def test_footswitches_tuner_and_tap(self):
        for btn, number in (("A", "49"), ("B", "50"), ("C", "51"), ("4", "68")):
            row = self.button(0, btn)
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), number)
            self.assertEqual(row["A_Toggle_(CC/PB/Note)"], "Y")
        tap = self.button(0, "D")
        self.assertEqual(norm(tap["A_Number_(PC/CC/Note)"]), "64")
        self.assertEqual(norm(tap["A_OffValue_(CC)"]), "")

    def test_looper_and_stomp_banks(self):
        self.assertEqual(norm(self.button(30, "1")["A_Number_(PC/CC/Note)"]), "60")
        self.assertEqual(norm(self.button(30, "2")["A_OnValue_(CC/PB)"]), "0")    # overdub
        self.assertEqual(norm(self.button(31, "B")["A_Number_(PC/CC/Note)"]), "53")  # FS5
        self.assertEqual(norm(self.button(31, "4")["A_OnValue_(CC/PB)"]), "8")    # next snapshot

    def test_expression_pedals_are_exp1_and_exp2(self):
        values = self.globals.set_index("Label")["Value"]
        self.assertEqual((norm(values["Exp1_CC"]), norm(values["Exp2_CC"])), ("1", "2"))

class QuadCortexTemplateTest(unittest.TestCase):
    """The Quad Cortex template packs and reads back as the template describes."""

    @classmethod
    def setUpClass(cls):
        packed = packer.pack_config(read_config_csv(QUAD_CORTEX_CSV))
        tables = unpacker.unpack_config(packed)
        cls.globals, cls.banks, cls.buttons, cls.enter = tables[0], tables[1], tables[2], tables[5]

    def button(self, bank, btn):
        b = self.buttons
        return b[(b["Bank_Number"].astype(str) == str(bank)) & (b["Button_Identifier"] == btn)].iloc[0]

    def test_preset_banks_load_their_preset_from_my_presets(self):
        for bank in (0, 7, 29):
            row = self.enter[self.enter["Bank_Number"].astype(str) == str(bank)].iloc[0]
            self.assertEqual(row["A_CommandType"], "PC")
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), str(bank))
            self.assertEqual(norm(row["A_BankSelect_(PC)"]), "1")       # CC#32 1, My Presets
            self.assertEqual(row["A_BankSelectHighByte_(PC)"], "Y")      # CC#0 0, presets 0-127

    def test_scene_buttons(self):
        for btn, value in (("1", 0), ("4", 3), ("A", 4), ("B", 5)):
            row = self.button(5, btn)
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), "43")
            self.assertEqual(norm(row["A_OnValue_(CC/PB)"]), str(value))
            self.assertEqual(norm(row["A_OffValue_(CC)"]), "")   # sends nothing
            self.assertEqual(norm(row["Group"]), "1")

    def test_tuner_and_tap(self):
        tuner = self.button(0, "C")
        self.assertEqual(norm(tuner["A_Number_(PC/CC/Note)"]), "45")
        self.assertEqual(tuner["A_Toggle_(CC/PB/Note)"], "Y")
        tap = self.button(0, "D")
        self.assertEqual(norm(tap["A_Number_(PC/CC/Note)"]), "44")
        self.assertEqual(norm(tap["A_OffValue_(CC)"]), "")

    def test_looper_bank(self):
        self.assertEqual(norm(self.button(30, "1")["A_Number_(PC/CC/Note)"]), "53")
        view = self.button(30, "4")                  # 0-63 opens the view, 64-127 closes it
        self.assertEqual((norm(view["A_OnValue_(CC/PB)"]), norm(view["A_OffValue_(CC)"])), ("0", "127"))
        rev = self.button(30, "C")                   # each 64-127 toggles reverse
        self.assertEqual((norm(rev["A_Number_(PC/CC/Note)"]), norm(rev["A_OffValue_(CC)"])), ("55", "127"))

    def test_footswitch_bank(self):
        for btn, number in (("A", "35"), ("D", "38"), ("1", "39"), ("4", "42")):
            self.assertEqual(norm(self.button(31, btn)["A_Number_(PC/CC/Note)"]), number)

    def test_expression_pedals(self):
        values = self.globals.set_index("Label")["Value"]
        self.assertEqual((norm(values["Exp1_CC"]), norm(values["Exp2_CC"])), ("1", "2"))

class KemperPlayerTemplateTest(unittest.TestCase):
    """The Kemper Player template packs and reads back as the template describes."""

    @classmethod
    def setUpClass(cls):
        packed = packer.pack_config(read_config_csv(KEMPER_PLAYER_CSV))
        tables = unpacker.unpack_config(packed)
        cls.globals, cls.banks, cls.buttons = tables[0], tables[1], tables[2]
        cls.enter, cls.setlist = tables[5], tables[8]

    def button(self, bank, btn):
        b = self.buttons
        return b[(b["Bank_Number"].astype(str) == str(bank)) & (b["Button_Identifier"] == btn)].iloc[0]

    def test_rig_banks_preselect_their_bank(self):
        names = self.banks.set_index(self.banks["Bank_Number"].astype(str))
        for bank, name, rigs in ((0, "BK01", "1 to 5"), (3, "BK04", "16 to 20"), (9, "BK10", "46 to 50")):
            row = self.enter[self.enter["Bank_Number"].astype(str) == str(bank)].iloc[0]
            self.assertEqual(row["A_CommandType"], "CC")
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), "47")
            self.assertEqual(norm(row["A_OnValue_(CC/PB)"]), str(bank))
            self.assertEqual(names.loc[str(bank), "Bank_Name_Large"], name)
            self.assertEqual(names.loc[str(bank), "Bank_Info_Small"], rigs)

    def test_slot_buttons(self):
        for btn, number in (("1", "50"), ("2", "51"), ("3", "52"), ("4", "53"), ("A", "54")):
            row = self.button(7, btn)
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), number)
            self.assertEqual(norm(row["A_OnValue_(CC/PB)"]), "1")
            self.assertEqual(norm(row["A_OffValue_(CC)"]), "")   # sends nothing
            self.assertEqual(row["A_Toggle_(CC/PB/Note)"], "Y")
            self.assertEqual(norm(row["Group"]), "1")

    def test_effect_buttons_and_tap(self):
        for btn, number in (("B", "75"), ("C", "76")):
            row = self.button(0, btn)
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), number)
            self.assertEqual(row["A_Toggle_(CC/PB/Note)"], "Y")
        tap = self.button(0, "D")
        self.assertEqual(norm(tap["A_Number_(PC/CC/Note)"]), "30")
        self.assertEqual(norm(tap["A_OffValue_(CC)"]), "")

    def test_fx_and_tool_banks(self):
        names = self.banks.set_index(self.banks["Bank_Number"].astype(str))["Bank_Name_Large"]
        self.assertEqual((names["10"], names["11"]), ("FX", "TOOL"))
        for btn, number in (("1", "17"), ("2", "18"), ("3", "26"), ("4", "28"), ("D", "78")):
            self.assertEqual(norm(self.button(10, btn)["A_Number_(PC/CC/Note)"]), number)
        # The tuner latches: 127 to open it and 0 to close it
        self.assertEqual(norm(self.button(11, "1")["A_Number_(PC/CC/Note)"]), "31")
        self.assertEqual(norm(self.button(11, "1")["A_OffValue_(CC)"]), "0")
        # What flips on any value sends 127 on both halves of the toggle
        for btn, number in (("2", "33"), ("3", "34"), ("4", "35")):
            row = self.button(11, btn)
            self.assertEqual(norm(row["A_Number_(PC/CC/Note)"]), number)
            self.assertEqual(norm(row["A_OnValue_(CC/PB)"]), "127")
            self.assertEqual(norm(row["A_OffValue_(CC)"]), "127")

    def test_only_the_twelve_used_banks_are_in_the_setlist(self):
        values = self.globals.set_index("Label")["Value"]
        self.assertEqual(values["Setlist_Mode"], "Y")
        self.assertEqual([norm(b) for b in self.setlist["Bank_Number"]], [str(b) for b in range(12)])

    def test_expression_pedals_are_wah_and_volume(self):
        values = self.globals.set_index("Label")["Value"]
        self.assertEqual((norm(values["Exp1_CC"]), norm(values["Exp2_CC"])), ("1", "7"))


if __name__ == "__main__":
    unittest.main()
