"""The rig wizard, lib/rigWizard.py: the devices on a board, each on its
channel, made into a configuration from their templates."""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import lib.rigWizard as rw  # noqa: E402
from lib.configCsv import read_config_csv  # noqa: E402
from lib.slotIO import pack_sections  # noqa: E402

CHANNEL = "Channel_(PC/CC/Note/PB)"


TEMPLATES = {}


def part(template, channel, follow=True):
    if template not in TEMPLATES:
        TEMPLATES[template] = rw.load_template(template)
    return {"template": template, "sections": TEMPLATES[template], "channel": channel, "follow": follow}


def rows(sections, name, bank):
    df = sections[name]
    return [r for r in df.to_dict("records") if str(r["Bank_Number"]) == str(bank)]


def sent(sections, name, bank):
    """(type, channel, number) of every command a bank's rows of a section send."""
    out = []
    for r in rows(sections, name, bank):
        for c in r:
            if c.endswith("_CommandType") and str(r[c]) not in ("", "nan"):
                p = c[: -len("_CommandType")]
                out.append((r[c], str(r.get(f"{p}_{CHANNEL}")), str(r.get(f"{p}_Number_(PC/CC/Note)"))))
    return out


def setting(sections, label):
    df = sections["Global_Settings"]
    return str(df[df["Label"] == label]["Value"].iloc[0])


class RigTest(unittest.TestCase):
    def test_a_stomp_and_a_delay(self):
        s, notes = rw.build_rig([part("HX_Stomp", "3"), part("TimeLine", "2")])
        pack_sections(s)
        self.assertEqual(setting(s, "MIDI_Channel"), "3")
        self.assertEqual(setting(s, "ConfigName"), "HX Stomp rig")
        # The HX Stomp's buttons on its channel
        self.assertEqual({ch for _, ch, _ in sent(s, "Button_Settings", 0)}, {"3"})
        # Bank 29, its last preset, holds the TimeLine's footswitches on channel 2
        naming = rows(s, "Bank_Naming", 29)[0]
        self.assertEqual((naming["Bank_Name_Large"], naming["Bank_Info_Small"]), ("FS", "TimeLine"))
        self.assertEqual({ch for _, ch, _ in sent(s, "Button_Settings", 29)}, {"2"})
        self.assertEqual(sent(s, "BankEnter_Settings", 29), [])
        # Entering bank 5 loads program 5 on both
        self.assertEqual(sent(s, "BankEnter_Settings", 5), [("PC", "3", "5"), ("PC", "2", "5")])
        self.assertIn("bank 29 holds the TimeLine's FS, in place of the HX Stomp's 10C", notes)
        self.assertTrue(any("one DIN output" in n for n in notes))

    def test_not_following(self):
        s, notes = rw.build_rig([part("HX_Stomp", "1"), part("TimeLine", "2", follow=False)])
        self.assertEqual(sent(s, "BankEnter_Settings", 5), [("PC", "1", "5")])
        self.assertFalse(any("changes preset" in n for n in notes))

    def test_free_banks_first_and_the_setlist(self):
        s, notes = rw.build_rig([part("Kemper_Player", "1"), part("BigSky", "3"), part("Ampero_II", "4")])
        pack_sections(s)
        self.assertEqual(rows(s, "Bank_Naming", 12)[0]["Bank_Info_Small"], "BigSky")
        self.assertEqual(rows(s, "Bank_Naming", 13)[0]["Bank_Info_Small"], "Ampero I")
        self.assertEqual(s["Setlist"]["Bank_Number"].tolist()[-2:], ["12", "13"])
        self.assertIn("bank 12 holds the BigSky's FS, at the end of the setlist", notes)
        self.assertIn("the BigSky does not change preset with the banks: the Kemper Player's banks load no "
                      "program on entering", notes)
        self.assertIn("the Ampero II listens on every channel out of the box: set it to channel 4, or it takes "
                      "the other devices' messages too", notes)

    def test_a_preset_bank_for_controls(self):
        # The Iridium's template has presets in every bank: its last loses its program
        s, notes = rw.build_rig([part("MainStage", "1"), part("Iridium", "2")])
        naming = rows(s, "Bank_Naming", 30)[0]
        self.assertEqual((naming["Bank_Name_Large"], naming["Bank_Info_Small"]), ("IRID", "Iridium"))
        self.assertEqual(sent(s, "BankEnter_Settings", 30), [])
        self.assertIn("bank 30 holds the Iridium's controls, in place of the MainStage's P030", notes)
        self.assertEqual(notes[0], "MainStage, on the computer: it takes the pedal's MIDI over USB, on channel 1")

    # Two tests, which run side by side
    def test_every_template_as_the_main_device(self):
        for t in rw.templates():
            with self.subTest(t):
                pack_sections(rw.build_rig([part(t, "1"), part("TimeLine", "2")])[0])

    def test_every_template_as_another_device(self):
        for t in rw.templates():
            with self.subTest(t):
                s, _ = rw.build_rig([part("HX_Stomp", "1"), part(t, "2")])
                pack_sections(s)
                self.assertEqual({ch for _, ch, _ in sent(s, "Button_Settings", 29)} - {"nan"}, {"2"})

    def test_mistakes(self):
        with self.assertRaisesRegex(ValueError, "TimeLine and HX Stomp are both on channel 1"):
            rw.build_rig([part("HX_Stomp", "1"), part("TimeLine", "1")])
        with self.assertRaisesRegex(ValueError, "channel 17: channels are 1-16"):
            rw.build_rig([part("HX_Stomp", "17")])
        with self.assertRaisesRegex(ValueError, "at most 4 devices"):
            rw.build_rig([part("HX_Stomp", str(c)) for c in range(1, 6)])
        with self.assertRaisesRegex(ValueError, "pick a device first"):
            rw.build_rig([])

    def test_the_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "rig.csv")
            r = subprocess.run([sys.executable, "Rig.py", "hx_stomp:1", "TimeLine:2", "--no-follow", "-o", out],
                               cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("Bank 29 holds the TimeLine's FS", r.stdout)
            self.assertEqual(sent(read_config_csv(out), "BankEnter_Settings", 5), [("PC", "1", "5")])
            r = subprocess.run([sys.executable, "Rig.py", "Nothing:1", "-o", out], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn("there is no template Nothing", r.stdout)


if __name__ == "__main__":
    unittest.main()
