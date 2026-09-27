"""launch.py: what it tells a user who is missing something."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import launch  # noqa: E402


class HelpForSystem(unittest.TestCase):
    def test_python_too_new_for_rtmidi(self):
        with mock.patch.object(launch.sys, "version_info", (3, 14, 0)), \
             mock.patch.object(launch.platform, "system", return_value="Windows"):
            text = launch.help_for_system("pip")
        self.assertIn("Python 3.12 from python.org", text)
        self.assertIn("C++ Build Tools", text)

    def test_ready_built_python_only_names_the_compiler(self):
        with mock.patch.object(launch.sys, "version_info", (3, 12, 7)), \
             mock.patch.object(launch.platform, "system", return_value="Linux"):
            text = launch.help_for_system("pip")
        self.assertNotIn("python.org", text)
        self.assertIn("libasound2-dev", text)

    def test_tk_on_each_system(self):
        for system, needle in (("Darwin", "brew install python-tk@"), ("Linux", "python3-tk"),
                               ("Windows", "tcl/tk")):
            with mock.patch.object(launch.platform, "system", return_value=system):
                self.assertIn(needle, launch.help_for_system("tk"))

    def test_venv_path_per_system(self):
        with mock.patch.object(launch.os, "name", "nt"):
            self.assertEqual(launch.venv_python().parts[-2:], ("Scripts", "python.exe"))
        with mock.patch.object(launch.os, "name", "posix"):
            self.assertEqual(launch.venv_python().parts[-2:], ("bin", "python"))


if __name__ == "__main__":
    unittest.main()
