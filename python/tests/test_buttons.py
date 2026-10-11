"""What a button is besides its commands: double and long press, groups, holds, globals, combos."""

import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# roundtrip_support also puts python/ on the path, for lib
from roundtrip_support import DEMO_CSV, SAMPLE_CSV, firmware_source, norm, pack_csv  # noqa: E402
import lib.binaryUnpacker as unpacker  # noqa: E402
import lib.cmdBinaryPacker as cbp  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
import lib.configPacker as packer  # noqa: E402
from lib.configPacker import pack_config  # noqa: E402
import lib.flashLayout as layout  # noqa: E402


class DoublePressTest(unittest.TestCase):
    """Double press commands, written after the slot's pages (firmware 0.26)."""

    def setUp(self):
        self.sections = read_config_csv(DEMO_CSV)

    def test_extension_fits_its_pages(self):
        self.assertLessEqual(layout.DOUBLE_PRESS_SIZE, layout.DOUBLE_PRESS_PAGES * layout.FLASH_PAGE_SIZE)
        self.assertGreaterEqual(layout.DOUBLE_PRESS_OFFSET, layout.CONFIG_SIZE)

    def test_demo_image(self):
        image = packer.pack_flash_image(self.sections)
        config = packer.pack_config(self.sections)
        self.assertEqual(len(image), layout.EXT2_OFFSET + layout.EXT2_SIZE)   # the MIDI map follows
        image = image[: layout.DOUBLE_PRESS_OFFSET + layout.DOUBLE_PRESS_SIZE]
        # The configuration itself is untouched, and since 0.59 it fills the
        # slot's pages, so the extension follows it with no gap
        self.assertEqual(image[: len(config)], config)
        self.assertEqual(len(config), layout.DOUBLE_PRESS_OFFSET)
        # Four commands in the demo, everything else erased
        extension = image[layout.DOUBLE_PRESS_OFFSET :]
        self.assertEqual(sum(1 for b in extension if b != 0xFF), 16)
        button = 2 * 8 + 3                     # bank 2, button 4
        off = layout.DOUBLE_PRESS_OFFSET + button * layout.BUTTON_STRIDE
        self.assertEqual(list(image[off : off + 4]), [0xB0, 18 | 0x80, 127, 0])

    def test_demo_round_trip(self):
        image = packer.pack_flash_image(self.sections)
        df = unpacker.unpack_double_press_settings(image)
        row = df[(df["Bank_Number"] == "2") & (df["Button_Identifier"] == "4")].iloc[0]
        self.assertEqual(row["A_CommandType"], "CC")
        self.assertEqual(row["A_Number_(PC/CC/Note)"], "18")
        self.assertEqual(row["A_Toggle_(CC/PB/Note)"], "Y")
        self.assertEqual(row["B_CommandType"], "")
        # and the Scene Save on A, Arrows on 1 in bank 5 and Stop on REC
        self.assertEqual((df["A_CommandType"] != "").sum(), 4)

    def test_commands_of_the_empty_type_are_kept(self):
        """Wait, If, Macro, Button and the rest share the empty command type's
        nibble; only a slot with nothing in it is left erased (0.73)."""
        df = self.sections[packer.DOUBLE_PRESS_SECTION].copy()
        i = df[(df["Bank_Number"].astype(str) == "1") & (df["Button_Identifier"] == "3")].index[0]
        for slot, fields in (("A", {"CommandType": "Wait", "Duration_(Note/PB)": "200"}),
                             ("B", {"CommandType": "Button", "Number_(PC/CC/Note)": "B",
                                    "KeyMode_(Key)": "Set Off"})):
            for field, value in fields.items():
                df.at[i, f"{slot}_{field}"] = value
        image = packer.pack_flash_image({**self.sections, packer.DOUBLE_PRESS_SECTION: df})
        off = layout.DOUBLE_PRESS_OFFSET + (1 * 8 + 2) * layout.BUTTON_STRIDE
        self.assertEqual(list(image[off : off + 12]),
                         [0x01, 0, 20, 0, 0x0D, 0x7F, 0x05, 5] + [0xFF] * 4)
        back = unpacker.unpack_double_press_settings(image)
        row = back[(back["Bank_Number"] == "1") & (back["Button_Identifier"] == "3")].iloc[0]
        self.assertEqual((row["A_CommandType"], row["B_CommandType"]), ("Wait", "Button"))

    def test_without_double_press_image_is_the_config(self):
        sections = {k: v for k, v in self.sections.items()
                    if k not in (packer.DOUBLE_PRESS_SECTION, packer.MIDI_MAP_SECTION)}
        sections[packer.LONG_PRESS_SECTION] = sections[packer.LONG_PRESS_SECTION].assign(Long_Label="")
        sections[packer.BANK_SWITCH_SECTION] = sections[packer.BANK_SWITCH_SECTION].assign(Label="")
        self.assertEqual(packer.pack_flash_image(sections), packer.pack_config(sections))
        self.assertIsNone(packer.pack_double_press(sections))

    def test_stored_flag(self):
        """Byte 37 tells the firmware the double press area belongs to this image."""
        self.assertEqual(packer.pack_config(self.sections)[37], 1)
        sections = {k: v for k, v in self.sections.items() if k != packer.DOUBLE_PRESS_SECTION}
        self.assertEqual(packer.pack_config(sections)[37], 0)
        empty = {**self.sections, packer.DOUBLE_PRESS_SECTION: packer.empty_double_press_settings()}
        self.assertEqual(packer.pack_config(empty)[37], 0)

    def test_dump_from_older_firmware_has_none(self):
        df = unpacker.unpack_double_press_settings(packer.pack_config(self.sections))
        self.assertEqual((df["A_CommandType"] != "").sum(), 0)
        self.assertEqual(len(df), 32 * 8)

    def test_window(self):
        g = self.sections["Global_Settings"]
        for text, byte, back in (("450", 45, "450"), ("50", 10, "100"), ("5000", 100, "1000")):
            g.loc[g["Label"] == "Double_Press_ms", "Value"] = text
            packed = packer.pack_config(self.sections)
            self.assertEqual(packed[36], byte, text)
            decoded = unpacker.unpack_config(packed)[0].set_index("Label")["Value"]
            self.assertEqual(decoded["Double_Press_ms"], back)
        self.sections["Global_Settings"] = g[g["Label"] != "Double_Press_ms"]
        self.assertEqual(packer.pack_config(self.sections)[36], 30)

    def test_erased_window_reads_default(self):
        image = bytearray(packer.pack_config(self.sections))
        for old in (0x00, 0xFF):
            image[36] = old
            decoded = unpacker.unpack_config(bytes(image))[0].set_index("Label")["Value"]
            self.assertEqual(decoded["Double_Press_ms"], "300")

    def test_copy_paste_bank_takes_double_press(self):
        from lib import bankClipboard

        s = self.sections
        double = s[packer.DOUBLE_PRESS_SECTION]
        clip = bankClipboard.copy_bank(s["Button_Settings"], s.get(packer.LONG_PRESS_SECTION),
                                       s.get(packer.BANK_ENTER_SECTION), 2, df_double=double)
        pasted = bankClipboard.paste_double(double, clip, 9)
        image = packer.pack_flash_image({**s, packer.DOUBLE_PRESS_SECTION: pasted})
        df = unpacker.unpack_double_press_settings(image)
        row = df[(df["Bank_Number"] == "9") & (df["Button_Identifier"] == "4")].iloc[0]
        self.assertEqual(row["A_Number_(PC/CC/Note)"], "18")
        self.assertEqual((df["A_CommandType"] != "").sum(), 6)

class BankClipboardTest(unittest.TestCase):
    """Copy one bank over another, as the configurator's Copy/Paste bank does."""

    SRC, DST = 3, 9

    @staticmethod
    def region(packed, start, stride, bank):
        return packed[start + bank * stride:start + (bank + 1) * stride]

    def setUp(self):
        from lib import bankClipboard
        self.clip = bankClipboard
        self.sections = read_config_csv(DEMO_CSV)
        self.before = packer.pack_config(self.sections)

    def paste(self, src, dst):
        s = self.sections
        clip = self.clip.copy_bank(s["Button_Settings"], s.get(packer.LONG_PRESS_SECTION),
                                   s.get(packer.BANK_ENTER_SECTION), src)
        b, l, e = self.clip.paste_bank(s["Button_Settings"], s.get(packer.LONG_PRESS_SECTION),
                                       s.get(packer.BANK_ENTER_SECTION), clip, dst)
        new = dict(s)
        new["Button_Settings"], new[packer.LONG_PRESS_SECTION], new[packer.BANK_ENTER_SECTION] = b, l, e
        return new, packer.pack_config(new)

    def test_target_becomes_identical(self):
        _, after = self.paste(self.SRC, self.DST)
        for name, start, stride in (
            ("commands", layout.COMMANDS_OFFSET, 8 * layout.BUTTON_STRIDE),
            ("led modes", layout.LED_MODES_OFFSET, 8),
            ("labels", layout.LABELS_OFFSET, 32),
            ("long press", layout.LONG_PRESS_OFFSET, 8 * layout.BUTTON_STRIDE),
            ("bank enter", layout.BANK_ENTER_OFFSET, layout.BUTTON_STRIDE),
        ):
            self.assertEqual(self.region(after, start, stride, self.DST),
                             self.region(self.before, start, stride, self.SRC), name)

    def test_nothing_else_changes(self):
        _, after = self.paste(self.SRC, self.DST)
        diffs = [i for i in range(len(after)) if after[i] != self.before[i]]
        allowed = []
        for start, stride in ((layout.COMMANDS_OFFSET, 8 * layout.BUTTON_STRIDE), (layout.LED_MODES_OFFSET, 8),
                              (layout.LABELS_OFFSET, 32), (layout.LONG_PRESS_OFFSET, 8 * layout.BUTTON_STRIDE),
                              (layout.BANK_ENTER_OFFSET, layout.BUTTON_STRIDE)):
            allowed.append(range(start + self.DST * stride, start + (self.DST + 1) * stride))
        stray = [i for i in diffs if not any(i in r for r in allowed)]
        self.assertEqual(stray, [], "bytes outside the target bank changed")
        self.assertTrue(diffs, "the paste changed nothing")

    def test_bank_name_is_kept(self):
        _, after = self.paste(self.SRC, self.DST)
        name = self.region(after, layout.GLOBAL_SIZE, 12, self.DST)
        self.assertEqual(name, self.region(self.before, layout.GLOBAL_SIZE, 12, self.DST))

    def test_rows_keep_their_count(self):
        new, _ = self.paste(self.SRC, self.DST)
        self.assertEqual(len(new["Button_Settings"]), len(self.sections["Button_Settings"]))

    def test_target_extras_are_removed(self):
        """Bank 1 has a long press on button 4; bank 6 only one on button 4 too; bank 2 none."""
        s = self.sections
        long_frame = s[packer.LONG_PRESS_SECTION]
        def long_types(frame, bank):
            rows = frame[frame["Bank_Number"].astype(str).str.replace(".0", "", regex=False) == str(bank)]
            return sorted(str(r["A_CommandType"]) for _, r in rows.iterrows()
                          if str(r["A_CommandType"]) not in ("", "nan"))
        self.assertTrue(long_types(long_frame, 1))
        new, _ = self.paste(2, 1)
        self.assertEqual(long_types(new[packer.LONG_PRESS_SECTION], 1), long_types(long_frame, 2))

    def test_copy_is_a_snapshot(self):
        s = self.sections
        clip = self.clip.copy_bank(s["Button_Settings"], None, None, self.SRC)
        before = [dict(r) for r in clip["buttons"]]
        s["Button_Settings"].loc[:, "Label"] = "XXXX"
        self.assertEqual(clip["buttons"], before)

    def test_paste_onto_itself_is_a_no_op(self):
        _, after = self.paste(self.SRC, self.SRC)
        self.assertEqual(after, self.before)

class ButtonGroupTest(unittest.TestCase):
    """Exclusive groups, stored in the top bits of each button's LED mode byte."""

    def test_packs_in_the_led_byte(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Button_Settings"].copy()
        df["Group"] = ""
        i = df.index[(df["Bank_Number"].astype(str) == "5") & (df["Button_Identifier"] == "B")][0]
        df.at[i, "Light_Mode"] = "AlwaysOn"
        df.at[i, "Group"] = "3"
        base = pack_config({**sections, "Button_Settings": df.assign(Group="")})
        packed = pack_config({**sections, "Button_Settings": df})
        at = layout.LED_MODES_OFFSET + 5 * 8 + layout.BUTTON_IDS.index("B")
        self.assertEqual(packed[at], 0x32)
        # Nothing else moves
        self.assertEqual(packed[:at] + packed[at + 1:], base[:at] + base[at + 1:])

    def test_round_trip(self):
        sections = read_config_csv(DEMO_CSV)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        df = sections["Button_Settings"]
        for bank, btn in (("1", "A"), ("1", "D")):
            row = decoded[(decoded["Bank_Number"] == bank) & (decoded["Button_Identifier"] == btn)]
            self.assertEqual(row["Group"].iloc[0], "1")
        self.assertEqual((decoded["Group"] != "").sum(), (df["Group"].map(norm) != "").sum())

    def test_older_configurations_have_no_group(self):
        """A CSV without the column packs exactly as before, all zero on top."""
        sections = read_config_csv(SAMPLE_CSV)
        self.assertNotIn("Group", sections["Button_Settings"].columns)
        packed = pack_config(sections)
        table = packed[layout.LED_MODES_OFFSET : layout.LABELS_OFFSET]
        self.assertTrue(all(b < 0x10 for b in table))
        _, _, decoded, *_ = unpacker.unpack_config(packed)
        self.assertTrue((decoded["Group"] == "").all())

    def test_erased_flash_has_no_group(self):
        blank = bytes([0xFF]) * layout.CONFIG_SIZE
        _, _, df, *_ = unpacker.unpack_config(blank)
        self.assertTrue((df["Group"] == "").all())
        self.assertTrue((df["Light_Mode"] == "Normal").all())

    def test_values(self):
        for cell, want in (("", 0), (float("nan"), 0), ("None", 0), ("0", 0), ("1", 1), ("4.0", 4)):
            self.assertEqual(cbp.button_group_value(cell), want, cell)
        for cell in ("5", "-1", "x"):
            with self.assertRaises(ValueError):
                cbp.button_group_value(cell)

class MomentaryHoldTest(unittest.TestCase):
    """Momentary hold, bit 7 of each button's LED mode byte."""

    def test_packs_in_the_led_byte(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Button_Settings"].copy()
        df["Momentary_Hold"] = ""
        i = df.index[(df["Bank_Number"].astype(str) == "5") & (df["Button_Identifier"] == "B")][0]
        df.at[i, "Light_Mode"] = "Reverse"
        df.at[i, "Group"] = "2"
        base = pack_config({**sections, "Button_Settings": df})
        df.at[i, "Momentary_Hold"] = "Y"
        packed = pack_config({**sections, "Button_Settings": df})
        at = layout.LED_MODES_OFFSET + 5 * 8 + layout.BUTTON_IDS.index("B")
        self.assertEqual(base[at], 0x21)
        self.assertEqual(packed[at], 0xA1)
        self.assertEqual(packed[:at] + packed[at + 1:], base[:at] + base[at + 1:])

    def test_round_trip(self):
        sections = read_config_csv(DEMO_CSV)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        row = decoded[(decoded["Bank_Number"] == "11") & (decoded["Button_Identifier"] == "4")]
        self.assertEqual(row["Momentary_Hold"].iloc[0], "Y")
        self.assertEqual(row["Light_Mode"].iloc[0], "AlwaysOn")
        self.assertEqual((decoded["Momentary_Hold"] == "Y").sum(), 1)

    def test_older_configurations_have_none(self):
        sections = read_config_csv(SAMPLE_CSV)
        self.assertNotIn("Momentary_Hold", sections["Button_Settings"].columns)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        self.assertTrue((decoded["Momentary_Hold"] == "").all())

    def test_erased_flash_has_none(self):
        blank = bytes([0xFF]) * layout.CONFIG_SIZE
        _, _, df, *_ = unpacker.unpack_config(blank)
        self.assertTrue((df["Momentary_Hold"] == "").all())

    def test_values(self):
        for cell, want in (("", False), (float("nan"), False), ("N", False), ("0", False),
                           ("Y", True), ("yes", True), ("1.0", True)):
            self.assertEqual(cbp.momentary_hold_value(cell), want, cell)
        with self.assertRaises(ValueError):
            cbp.momentary_hold_value("maybe")

    def test_firmware_bit_matches(self):
        import re
        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc",
                            "flash_midi_settings.h")
        with open(path) as handle:
            header = handle.read()
        m = re.search(r"#define\s+BUTTON_MOMENTARY_HOLD\s+\((0x[0-9A-Fa-f]+)\)", header)
        self.assertEqual(int(m.group(1), 16), cbp.BUTTON_MOMENTARY_HOLD)

class ResetOnBankTest(unittest.TestCase):
    """Reset on bank change, bit 7 of the first character of a button's label."""

    def _index(self, df, bank, btn):
        return df.index[(df["Bank_Number"].astype(str) == str(bank))
                        & (df["Button_Identifier"] == btn)][0]

    def test_packs_in_the_label(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Button_Settings"].copy()
        df["Reset_On_Bank"] = ""
        i = self._index(df, 5, "B")
        base = pack_config({**sections, "Button_Settings": df})
        df.at[i, "Reset_On_Bank"] = "Y"
        packed = pack_config({**sections, "Button_Settings": df})
        at = layout.LABELS_OFFSET + (5 * 8 + layout.BUTTON_IDS.index("B")) * layout.LABEL_LEN
        self.assertEqual(packed[at], base[at] | packer.LABEL_RESET_BIT)
        self.assertEqual(packed[:at] + packed[at + 1:], base[:at] + base[at + 1:])

    def test_an_empty_label_keeps_it(self):
        self.assertEqual(packer.pack_label("", reset=True), b"\xa0   ")
        self.assertEqual(packer.pack_label("BOST", reset=True), b"\xc2OST")
        self.assertEqual(packer.pack_label("BOST"), b"BOST")

    def test_round_trip(self):
        sections = read_config_csv(DEMO_CSV)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        row = decoded[(decoded["Bank_Number"] == "11") & (decoded["Button_Identifier"] == "4")]
        self.assertEqual(row["Reset_On_Bank"].iloc[0], "Y")
        self.assertEqual(row["Label"].iloc[0], "BOST")
        self.assertEqual((decoded["Reset_On_Bank"] == "Y").sum(), 1)

    def test_empty_label_round_trip(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Button_Settings"].copy()
        i = self._index(df, 5, "B")
        df.at[i, "Label"] = ""
        df.at[i, "Reset_On_Bank"] = "Y"
        _, _, decoded, *_ = unpacker.unpack_config(pack_config({**sections, "Button_Settings": df}))
        row = decoded[(decoded["Bank_Number"] == "5") & (decoded["Button_Identifier"] == "B")]
        self.assertEqual(norm(row["Label"].iloc[0]), "")
        self.assertEqual(row["Reset_On_Bank"].iloc[0], "Y")

    def test_older_configurations_have_none(self):
        sections = read_config_csv(SAMPLE_CSV)
        self.assertNotIn("Reset_On_Bank", sections["Button_Settings"].columns)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        self.assertTrue((decoded["Reset_On_Bank"] == "").all())

    def test_erased_flash_has_none(self):
        blank = bytes([0xFF]) * layout.CONFIG_SIZE
        _, _, df, *_ = unpacker.unpack_config(blank)
        self.assertTrue((df["Reset_On_Bank"] == "").all())

    def test_values(self):
        for cell, want in (("", False), (float("nan"), False), ("N", False),
                           ("Y", True), ("yes", True), ("1.0", True)):
            self.assertEqual(cbp.reset_on_bank_value(cell), want, cell)
        with self.assertRaises(ValueError):
            cbp.reset_on_bank_value("maybe")

    def test_firmware_bit_matches(self):
        import re
        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc",
                            "flash_midi_settings.h")
        with open(path) as handle:
            header = handle.read()
        m = re.search(r"#define\s+LABEL_RESET_BIT\s+\((0x[0-9A-Fa-f]+)\)", header)
        self.assertEqual(int(m.group(1), 16), packer.LABEL_RESET_BIT)

class InstantPressTest(unittest.TestCase):
    """Instant press, bit 7 of the second character of a button's label (1.17)."""

    def _index(self, df, bank, btn):
        return df.index[(df["Bank_Number"].astype(str) == str(bank))
                        & (df["Button_Identifier"] == btn)][0]

    def test_packs_in_the_label(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Button_Settings"].copy()
        df["Instant_Press"] = ""
        i = self._index(df, 5, "B")
        base = pack_config({**sections, "Button_Settings": df})
        df.at[i, "Instant_Press"] = "Y"
        packed = pack_config({**sections, "Button_Settings": df})
        at = layout.LABELS_OFFSET + (5 * 8 + layout.BUTTON_IDS.index("B")) * layout.LABEL_LEN + 1
        self.assertEqual(packed[at], base[at] | packer.LABEL_INSTANT_BIT)
        self.assertEqual(packed[:at] + packed[at + 1:], base[:at] + base[at + 1:])

    def test_with_the_reset_and_short_labels(self):
        self.assertEqual(packer.pack_label("", instant=True), b" \xa0  ")
        self.assertEqual(packer.pack_label("R", reset=True, instant=True), b"\xd2\xa0  ")
        self.assertEqual(packer.pack_label("REC", instant=True), b"R\xc5C ")

    def test_round_trip(self):
        sections = read_config_csv(DEMO_CSV)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        row = decoded[(decoded["Bank_Number"] == "1") & (decoded["Button_Identifier"] == "1")]
        self.assertEqual(row["Instant_Press"].iloc[0], "Y")
        self.assertEqual(row["Label"].iloc[0], "REC")
        self.assertEqual(row["Reset_On_Bank"].iloc[0], "")
        self.assertEqual((decoded["Instant_Press"] == "Y").sum(), 1)

    def test_both_bits_round_trip(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Button_Settings"].copy()
        i = self._index(df, 11, "4")             # BOST, reset on bank change
        df.at[i, "Instant_Press"] = "Y"
        _, _, decoded, *_ = unpacker.unpack_config(pack_config({**sections, "Button_Settings": df}))
        row = decoded[(decoded["Bank_Number"] == "11") & (decoded["Button_Identifier"] == "4")]
        self.assertEqual(row["Label"].iloc[0], "BOST")
        self.assertEqual(row["Reset_On_Bank"].iloc[0], "Y")
        self.assertEqual(row["Instant_Press"].iloc[0], "Y")

    def test_older_configurations_and_erased_flash_have_none(self):
        sections = read_config_csv(SAMPLE_CSV)
        self.assertNotIn("Instant_Press", sections["Button_Settings"].columns)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        self.assertTrue((decoded["Instant_Press"] == "").all())
        _, _, df, *_ = unpacker.unpack_config(bytes([0xFF]) * layout.CONFIG_SIZE)
        self.assertTrue((df["Instant_Press"] == "").all())

    def test_values(self):
        for cell, want in (("", False), (float("nan"), False), ("N", False),
                           ("Y", True), ("yes", True), ("1.0", True)):
            self.assertEqual(cbp.instant_press_value(cell), want, cell)
        with self.assertRaises(ValueError):
            cbp.instant_press_value("maybe")

    def test_firmware_bit_matches(self):
        import re
        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc",
                            "flash_midi_settings.h")
        with open(path) as handle:
            header = handle.read()
        m = re.search(r"#define\s+LABEL_INSTANT_BIT\s+\((0x[0-9A-Fa-f]+)\)", header)
        self.assertEqual(int(m.group(1), 16), packer.LABEL_INSTANT_BIT)

class TempoFlashTest(unittest.TestCase):
    """Flashing at the tempo, bit 2 of each button's LED mode byte."""

    def test_packs_in_the_led_byte(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Button_Settings"].copy()
        df["Tempo_Flash"] = ""
        i = df.index[(df["Bank_Number"].astype(str) == "5") & (df["Button_Identifier"] == "B")][0]
        df.at[i, "Light_Mode"] = "Reverse"
        df.at[i, "Group"] = "2"
        df.at[i, "Momentary_Hold"] = "Y"
        base = pack_config({**sections, "Button_Settings": df})
        df.at[i, "Tempo_Flash"] = "Y"
        packed = pack_config({**sections, "Button_Settings": df})
        at = layout.LED_MODES_OFFSET + 5 * 8 + layout.BUTTON_IDS.index("B")
        self.assertEqual(base[at], 0xA1)
        self.assertEqual(packed[at], 0xA5)
        self.assertEqual(packed[:at] + packed[at + 1:], base[:at] + base[at + 1:])

    def test_round_trip(self):
        sections = read_config_csv(DEMO_CSV)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        row = decoded[(decoded["Bank_Number"] == "6") & (decoded["Button_Identifier"] == "B")]
        self.assertEqual(row["Tempo_Flash"].iloc[0], "Y")
        # A plain CC toggle, not a Tap button: the flash is the button's own
        self.assertEqual(row["A_CommandType"].iloc[0], "CC")
        self.assertEqual((decoded["Tempo_Flash"] == "Y").sum(), 1)

    def test_older_configurations_have_none(self):
        sections = read_config_csv(SAMPLE_CSV)
        self.assertNotIn("Tempo_Flash", sections["Button_Settings"].columns)
        _, _, decoded, *_ = unpacker.unpack_config(pack_config(sections))
        self.assertTrue((decoded["Tempo_Flash"] == "").all())

    def test_erased_flash_has_none(self):
        blank = bytes([0xFF]) * layout.CONFIG_SIZE
        _, _, df, *_ = unpacker.unpack_config(blank)
        self.assertTrue((df["Tempo_Flash"] == "").all())

    def test_values(self):
        for cell, want in (("", False), (float("nan"), False), ("N", False), ("0", False),
                           ("Y", True), ("yes", True), ("1.0", True)):
            self.assertEqual(cbp.tempo_flash_value(cell), want, cell)
        with self.assertRaises(ValueError):
            cbp.tempo_flash_value("maybe")

    def test_firmware_bits_match(self):
        import re
        path = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core", "Inc",
                            "flash_midi_settings.h")
        with open(path) as handle:
            header = handle.read()
        m = re.search(r"#define\s+BUTTON_TEMPO_FLASH\s+\((0x[0-9A-Fa-f]+)\)", header)
        self.assertEqual(int(m.group(1), 16), cbp.BUTTON_TEMPO_FLASH)
        # The mode itself now stops below the flash bit, so the two never mix
        m = re.search(r"#define\s+LED_MODE_MASK\s+\((0x[0-9A-Fa-f]+)\)", header)
        self.assertEqual(int(m.group(1), 16), 0x03)
        self.assertLess(max(cbp.LED_MODE_VALUES.values()), cbp.BUTTON_TEMPO_FLASH)

class GlobalButtonTest(unittest.TestCase):
    """Global buttons: one bank holds what is the same everywhere (0.57)."""

    FIRMWARE = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core")

    def source(self, *name):
        with open(os.path.join(self.FIRMWARE, *name)) as handle:
            return handle.read()

    def test_constants_match_firmware(self):
        import re

        header = self.source("Inc", "flash_midi_settings.h")
        bit = re.search(r"^#define\s+BUTTON_GLOBAL\s+\((0x[0-9A-Fa-f]+)\)", header, re.M)
        self.assertIsNotNone(bit)
        self.assertEqual(int(bit.group(1), 16), cbp.BUTTON_GLOBAL)
        # It is a bit of its own in the LED mode byte, taken by nothing else
        taken = [int(v, 16) for v in re.findall(
            r"^#define\s+(?:BUTTON_TEMPO_FLASH|BUTTON_MOMENTARY_HOLD)\s+\((0x[0-9A-Fa-f]+)\)",
            header, re.M)]
        group = int(re.search(r"^#define\s+BUTTON_GROUP_MASK\s+\((0x[0-9A-Fa-f]+)\)",
                              header, re.M).group(1), 16)
        shift = int(re.search(r"^#define\s+BUTTON_GROUP_SHIFT\s+\((\d+)\)", header, re.M).group(1))
        taken.append(group << shift)
        taken.append(int(re.search(r"^#define\s+LED_MODE_MASK\s+\((0x[0-9A-Fa-f]+)\)",
                                   header, re.M).group(1), 16))
        for other in taken:
            self.assertEqual(other & cbp.BUTTON_GLOBAL, 0, hex(other))

        defines = self.source("Inc", "midi_defines.h")
        byte = re.search(r"^#define\s+GLOBAL_SETTINGS_GLOBAL_BANK\s+\((\d+)\)", defines, re.M)
        self.assertIsNotNone(byte)
        import lib.settingsBinaryPacker as sbp
        self.assertEqual(int(byte.group(1)), sbp.GLOBAL_SETTINGS_GLOBAL_BANK)

    def test_firmware_redirects_every_list(self):
        """All three command lists of a button go through the same redirect."""
        source = self.source("Src", "switch_router.c")
        self.assertEqual(source.count("\tpage = button_bank(page, sw);"), 3)
        # And the bank set aside never follows itself
        self.assertIn("bank == g", source)

    def test_packs_in_the_led_byte(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Button_Settings"].copy()
        df["Global"] = ""
        i = df.index[(df["Bank_Number"].astype(str) == "5") & (df["Button_Identifier"] == "B")][0]
        df.at[i, "Light_Mode"] = "Reverse"
        df.at[i, "Group"] = "2"
        base = pack_config({**sections, "Button_Settings": df})
        df.at[i, "Global"] = "Y"
        packed = pack_config({**sections, "Button_Settings": df})
        at = layout.LED_MODES_OFFSET + 5 * 8 + layout.BUTTON_IDS.index("B")
        self.assertEqual(base[at], 0x21)
        self.assertEqual(packed[at], 0x29)
        self.assertEqual(packed[:at] + packed[at + 1:], base[:at] + base[at + 1:])

    def test_the_bank_is_held_as_one_more(self):
        """0 means no bank set aside, so an older configuration redirects nothing."""
        sections = read_config_csv(DEMO_CSV)
        df = sections["Global_Settings"].copy()
        where = df.index[df["Label"] == "Global_Bank"][0]
        for value, byte in (("0", 1), ("30", 31), ("31", 32), ("Off", 0), ("", 0)):
            df.at[where, "Value"] = value
            packed = pack_config({**sections, "Global_Settings": df})
            self.assertEqual(packed[44], byte, value)
            back = unpacker.unpack_global_settings(packed)
            row = back[back["Label"] == "Global_Bank"]["Value"].iloc[0]
            self.assertEqual(row, "Off" if byte == 0 else str(byte - 1), value)
        for bad in ("32", "-1", "twelve"):
            df.at[where, "Value"] = bad
            with self.assertRaises(ValueError, msg=bad):
                pack_config({**sections, "Global_Settings": df})

    def test_older_configurations_have_none(self):
        sections = read_config_csv(SAMPLE_CSV)
        self.assertNotIn("Global", sections["Button_Settings"].columns)
        packed = pack_config(sections)
        self.assertEqual(packed[44], 0)
        _, _, decoded, *_ = unpacker.unpack_config(packed)
        self.assertTrue((decoded["Global"] == "").all())

    def test_erased_flash_has_none(self):
        blank = bytes([0xFF]) * layout.CONFIG_SIZE
        _, _, df, *_ = unpacker.unpack_config(blank)
        self.assertTrue((df["Global"] == "").all())
        settings = unpacker.unpack_global_settings(blank)
        self.assertEqual(settings[settings["Label"] == "Global_Bank"]["Value"].iloc[0], "Off")

    def test_values(self):
        for cell, want in (("", False), (float("nan"), False), ("N", False),
                           ("Y", True), ("yes", True), ("1.0", True)):
            self.assertEqual(cbp.button_global_value(cell), want, cell)
        with self.assertRaises(ValueError):
            cbp.button_global_value("maybe")

    def test_demo_stores_the_tap_once(self):
        """The songs' tap is written in the bank set aside and followed."""
        sections = read_config_csv(DEMO_CSV)
        settings = sections["Global_Settings"]
        self.assertEqual(
            str(settings[settings["Label"] == "Global_Bank"]["Value"].iloc[0]), "30")

        buttons = sections["Button_Settings"]

        def row(bank, btn):
            return buttons[(buttons["Bank_Number"].astype(str) == str(bank))
                           & (buttons["Button_Identifier"].astype(str) == btn)].iloc[0]

        stored = row(30, "D")
        self.assertEqual(norm(stored["A_CommandType"]), "Tap")
        self.assertEqual(norm(stored["Label"]), "TAP")
        self.assertEqual(norm(stored["Global"]), "")     # it is the one stored

        # Song 1 keeps its own D, which is the way to its second page
        self.assertEqual(norm(row(12, "D")["Global"]), "")
        followers = [b for b in range(13, 30)]
        for bank in followers:
            here = row(bank, "D")
            self.assertEqual(norm(here["Global"]), "Y", bank)
            # Nothing of its own: the whole button comes from bank 30
            self.assertEqual(norm(here["A_CommandType"]), "", bank)
            self.assertEqual(norm(here["Label"]), "", bank)

        # What it saves: one list instead of one per bank
        self.assertEqual(len(followers) * cbp.MIDI_NUM_COMMANDS_PER_SWITCH * 4, 680)

class ComboTest(unittest.TestCase):
    """Two switches pressed together run a list of their own (0.59)."""

    FIRMWARE = os.path.join(os.path.dirname(__file__), "..", "..", "firmware", "Core")

    def source(self, *name):
        with open(os.path.join(self.FIRMWARE, *name)) as handle:
            return handle.read()

    def combos(self, rows):
        return pd.DataFrame(rows, columns=packer.COMBO_COLUMNS)

    def packed(self, rows, base=None):
        sections = dict(read_config_csv(base or DEMO_CSV))
        sections[packer.COMBO_SECTION] = self.combos(rows)
        return pack_config(sections)

    def table(self, packed):
        return packed[layout.COMBOS_OFFSET : layout.COMBOS_OFFSET + 48]

    def test_constants_agree(self):
        import re

        self.assertEqual(layout.COMBO_COUNT, layout.COMBO_COUNT)
        self.assertEqual(packer.COMBO_COLUMNS, unpacker.COMBO_COLUMNS)
        header = self.source("Inc", "flash_midi_settings.h")
        for name, want in (("COMBO_EVERY_BANK", 0), ("COMBO_UNUSED", 0xFF)):
            m = re.search(rf"^#define\s+{name}\s+\((0x[0-9A-Fa-f]+|\d+)\)", header, re.M)
            self.assertIsNotNone(m, name)
            self.assertEqual(int(m.group(1), 0), want, name)
        # The list is named as a Macro names it
        defines = self.source("Inc", "midi_defines.h")
        for i, name in enumerate(cbp.MACRO_LISTS):
            m = re.search(rf"^#define\s+MACRO_LIST_{name.upper()}\s+\((\d+)\)", defines, re.M)
            self.assertEqual(int(m.group(1)), i, name)
        # They take exactly the room the slot had left
        self.assertEqual(layout.CONFIG_SIZE, 12 * 2048)

    def test_packs_the_table(self):
        packed = self.packed([
            {"Switches": "1+2", "Bank": "All", "Run_Bank": "31", "Run_Button": "A", "Run_List": "Short"},
            {"Switches": "D + a", "Bank": "3", "Run_Bank": "5", "Run_Button": "b", "Run_List": "long"},
            {"Switches": "3 4", "Bank": "", "Run_Bank": "0", "Run_Button": "C", "Run_List": ""},
            {"Switches": "C,2", "Bank": "31", "Run_Bank": "30", "Run_Button": "D", "Run_List": "Double"},
        ])
        table = self.table(packed)
        self.assertEqual(table[:16], bytes([0x10, 0, 31, 0x04,  0x74, 4, 5, 0x15,
                                            0x32, 0, 0, 0x06,   0x61, 32, 30, 0x27]))
        self.assertEqual(table[16:], b"\xff" * 32)
        back = unpacker.unpack_combos(packed)
        self.assertEqual(back.to_dict("records"), [
            {"Switches": "1+2", "Bank": "All", "Run_Bank": "31", "Run_Button": "A", "Run_List": "Short"},
            {"Switches": "A+D", "Bank": "3", "Run_Bank": "5", "Run_Button": "B", "Run_List": "Long"},
            {"Switches": "3+4", "Bank": "All", "Run_Bank": "0", "Run_Button": "C", "Run_List": "Short"},
            {"Switches": "2+C", "Bank": "31", "Run_Bank": "30", "Run_Button": "D", "Run_List": "Double"},
        ])
        # and nothing else moved
        self.assertEqual(packed[: layout.COMBOS_OFFSET], pack_csv(DEMO_CSV)[: layout.COMBOS_OFFSET])

    def test_rows_without_switches_are_left_out(self):
        packed = self.packed([
            {"Switches": "", "Bank": "All", "Run_Bank": "1", "Run_Button": "A", "Run_List": "Short"},
            {"Switches": float("nan"), "Bank": "", "Run_Bank": "", "Run_Button": "", "Run_List": ""},
            {"Switches": "1+2", "Bank": "All", "Run_Bank": "1", "Run_Button": "A", "Run_List": "Short"},
        ])
        self.assertEqual(self.table(packed)[:4], bytes([0x10, 0, 1, 0x04]))
        self.assertEqual(len(unpacker.unpack_combos(packed)), 1)

    def test_refuses_what_it_cannot_store(self):
        good = {"Switches": "1+2", "Bank": "All", "Run_Bank": "1", "Run_Button": "A", "Run_List": "Short"}
        for field, bad in (("Switches", "1+1"), ("Switches", "1+E"), ("Switches", "1"), ("Switches", "1+2+3"),
                           ("Bank", "32"), ("Bank", "-1"), ("Bank", "some"),
                           ("Run_Bank", "32"), ("Run_Bank", ""), ("Run_Button", "E"), ("Run_Button", ""),
                           ("Run_List", "Triple")):
            with self.assertRaises(ValueError, msg=f"{field}={bad}"):
                self.packed([{**good, field: bad}])
        # the same pair twice for the same bank, whichever way round
        with self.assertRaises(ValueError):
            self.packed([good, {**good, "Switches": "2+1", "Run_Bank": "2"}])
        # but for another bank it is how one bank changes what the pair does
        self.packed([good, {**good, "Bank": "4"}])
        pairs = [f"{a}+{b}" for i, a in enumerate(layout.BUTTON_IDS) for b in layout.BUTTON_IDS[i + 1:]]
        self.packed([{**good, "Switches": p} for p in pairs[:layout.COMBO_COUNT]])
        with self.assertRaises(ValueError):
            self.packed([{**good, "Switches": p} for p in pairs[:layout.COMBO_COUNT + 1]])

    def test_older_configurations_have_none(self):
        sections = read_config_csv(SAMPLE_CSV)
        self.assertNotIn(packer.COMBO_SECTION, sections)
        packed = pack_config(sections)
        self.assertEqual(self.table(packed), b"\xff" * 48)
        self.assertEqual(packed[45], 8)   # and the window is the default
        # An older dump stops before the table, and erased flash is none either
        self.assertEqual(len(unpacker.unpack_combos(packed[: layout.COMBOS_OFFSET])), 0)
        self.assertEqual(len(unpacker.unpack_combos(b"\xff" * layout.CONFIG_SIZE)), 0)
        blank = unpacker.unpack_global_settings(b"\xff" * layout.CONFIG_SIZE)
        self.assertEqual(blank[blank["Label"] == "Combo_ms"]["Value"].iloc[0], "80")

    def test_invalid_entries_are_not_read(self):
        """What the firmware passes over the tools do not show either."""
        image = bytearray(pack_csv(SAMPLE_CSV))
        at = layout.COMBOS_OFFSET
        image[at : at + 20] = bytes([0x11, 0, 1, 0,   0x18, 0, 1, 0,   0x10, 33, 1, 0,
                                     0x10, 0, 32, 0,  0x21, 0, 2, 0x13])
        back = unpacker.unpack_combos(bytes(image))
        self.assertEqual(back["Switches"].tolist(), ["2+3"])
        source = self.source("Src", "switch_router.c")
        self.assertIn("a >= MIDI_NUM_SWITCHES || b >= MIDI_NUM_SWITCHES || a == b", source)

    def test_window(self):
        sections = read_config_csv(DEMO_CSV)
        df = sections["Global_Settings"].copy()
        where = df.index[df["Label"] == "Combo_ms"][0]
        for value, byte in (("80", 8), ("20", 2), ("5", 2), ("250", 25), ("400", 25), ("", 8), ("x", 8)):
            df.at[where, "Value"] = value
            packed = pack_config({**sections, "Global_Settings": df})
            self.assertEqual(packed[45], byte, value)
            back = unpacker.unpack_global_settings(packed)
            self.assertEqual(back[back["Label"] == "Combo_ms"]["Value"].iloc[0], str(byte * 10))

    def test_csv_round_trip(self):
        import tempfile

        from lib import slotIO

        sections = dict(read_config_csv(DEMO_CSV))
        sections[packer.COMBO_SECTION] = self.combos([
            {"Switches": "1+2", "Bank": "7", "Run_Bank": "31", "Run_Button": "A", "Run_List": "Long"},
        ])
        image = packer.pack_flash_image(sections)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "back.csv")
            slotIO.save_csv(path, image[: layout.CONFIG_SIZE], image)
            again = read_config_csv(path)
            self.assertIn(packer.COMBO_SECTION, again)
            self.assertEqual(packer.pack_flash_image(again), image)

    def test_demo(self):
        """3+4 is the tuner everywhere, and on the first song the looper's clear."""
        sections = read_config_csv(DEMO_CSV)
        combos = sections[packer.COMBO_SECTION]
        self.assertEqual(combos["Switches"].tolist(), ["3+4", "3+4"])
        self.assertEqual(combos["Bank"].tolist(), ["All", "12"])
        buttons = sections["Button_Settings"]
        for _, c in combos.iterrows():
            row = buttons[(buttons["Bank_Number"].astype(str) == c["Run_Bank"])
                          & (buttons["Button_Identifier"] == c["Run_Button"])].iloc[0]
            self.assertEqual(norm(row["A_CommandType"]), "CC", c.to_dict())
        table = self.table(pack_config(sections))
        self.assertEqual(table[:8], bytes([0x32, 0, 30, 0x05, 0x32, 13, 30, 0x03]))

class LongLabelTest(unittest.TestCase):
    """Labels for the long presses, shown while a Bank Reveal is held (0.91)."""

    def source(self, *name):
        return firmware_source(*name)

    def long_sections(self, labels, with_map=False):
        sections = dict(read_config_csv(SAMPLE_CSV if not with_map else DEMO_CSV))
        df = packer.empty_long_press_settings()
        for (bank, btn), text in labels.items():
            df.loc[(df["Bank_Number"] == str(bank)) & (df["Button_Identifier"] == btn), "Long_Label"] = text
        sections[packer.LONG_PRESS_SECTION] = df
        return sections

    def test_layout_agrees(self):
        header = self.source("Inc", "flash_midi_settings.h")
        self.assertIn("#define EXT2_LONG_LABELS_OFF	(EXT2_MAP_OFF + MIDI_MAP_COUNT * MIDI_MAP_STRIDE)", header)
        self.assertEqual(layout.EXT2_LONG_LABELS_OFFSET, 16 + 32 * 12)
        self.assertEqual(layout.EXT2_BANK_SWITCH_LABELS_OFFSET, layout.EXT2_LONG_LABELS_OFFSET + 32 * 8 * 4)
        self.assertLessEqual(layout.EXT2_SIZE, layout.EXT2_PAGES * 2048)
        defines = self.source("Inc", "midi_defines.h")
        self.assertRegex(defines, r"#define BANK_MODE_REVEAL\s+\(7\)")

    def test_labels_alone_write_the_area(self):
        """No map, but labels: the marker, an empty map and the labels."""
        image = packer.pack_flash_image(self.long_sections({(0, "1"): "PLAY", (31, "D"): "end"}))
        ext = image[layout.EXT2_OFFSET:]
        self.assertEqual(len(ext), layout.EXT2_SIZE)
        self.assertEqual(ext[:4], b"EXT2")
        self.assertEqual(ext[16:layout.EXT2_LONG_LABELS_OFFSET], b"\xff" * (32 * 12))
        labels = ext[layout.EXT2_LONG_LABELS_OFFSET:layout.EXT2_BANK_SWITCH_LABELS_OFFSET]
        self.assertEqual(labels[:4], b"PLAY")
        self.assertEqual(labels[4:8], b"    ")
        self.assertEqual(labels[-4:], b"end ")
        self.assertEqual(len(unpacker.unpack_midi_map(image)), 0)
        back = unpacker.unpack_long_press_settings(image)
        self.assertEqual(back["Long_Label"].tolist()[:2], ["PLAY", ""])
        self.assertEqual(back["Long_Label"].tolist()[-1], "end")

    def test_no_labels_no_area(self):
        sections = self.long_sections({})
        self.assertIsNone(packer.pack_ext2(sections))
        image = packer.pack_flash_image(sections)
        self.assertEqual(set(unpacker.unpack_long_press_settings(image)["Long_Label"]), {""})
        # A map alone keeps the labels erased, which the firmware reads as none
        ext = packer.pack_flash_image(self.long_sections({}, with_map=True))[layout.EXT2_OFFSET:]
        self.assertEqual(ext[:4], b"EXT2")
        self.assertEqual(ext[layout.EXT2_LONG_LABELS_OFFSET:layout.EXT2_BANK_SWITCH_LABELS_OFFSET],
                         b"\xff" * (32 * 8 * 4))

    def test_reveal_command(self):
        self.assertEqual(cbp.cmd_bank({"KeyMode_(Key)": "Reveal"}), [0x47, 0, 0, 0])
        cmd = unpacker.unpack_command(bytes([0x47, 0, 0, 0]))
        self.assertEqual((cmd["CommandType"], cmd["KeyMode_(Key)"], cmd["OnValue_(CC/PB)"]),
                         ("Bank", "Reveal", ""))

    def test_demo(self):
        """Held, MUTE in bank 5 shows what the other buttons do when held."""
        packed = packer.pack_flash_image(read_config_csv(DEMO_CSV))
        long_press = unpacker.unpack_long_press_settings(packed)
        bank5 = long_press[long_press["Bank_Number"] == "5"]
        self.assertEqual(bank5["Long_Label"].tolist(),
                         ["MPLY", "SNG2", "TOP0", "MSTP", "LOC0", "1:02", "HELD", "MREC"])
        c = bank5[bank5["Button_Identifier"] == "C"].iloc[0]
        self.assertEqual((c["A_CommandType"], c["A_KeyMode_(Key)"]), ("Bank", "Reveal"))

    def test_firmware(self):
        router = self.source("Src", "switch_router.c")
        self.assertIn("case BANK_MODE_REVEAL:      set_reveal(true); break;", router)
        self.assertIn("if(*pRom == (CMD_BANK_NIBBLE | BANK_MODE_REVEAL)) set_reveal(false);", router)
        self.assertIn("const uint8_t *all = flash_settings_long_labels();", router)
        flash = self.source("Src", "flash_midi_settings.c")
        self.assertIn("return ext2_part(EXT2_LONG_LABELS_OFF);", flash)


if __name__ == "__main__":
    unittest.main()
