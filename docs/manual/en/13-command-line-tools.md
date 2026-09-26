# Command line tools

`CSV_to_Flash.py` and `Flash_to_CSV.py` take `--slot 1` to `--slot 4` to choose a configuration slot, and use the slot the pedal is running when it is left out. Reading an empty slot is reported rather than producing a CSV. Firmware older than 0.24 has a single configuration, and the tools refuse any slot but 1 on it.

Everything the GUI does is available from the terminal, from the repository root:

```bash
# Flash a configuration to the pedal (normal mode, connected over USB)
.venv/bin/python python/CSV_to_Flash.py my-config.csv

# Read the configuration stored on the pedal into a CSV
.venv/bin/python python/Flash_to_CSV.py current-config.csv

# Back up all four slots at once, and put them back
.venv/bin/python python/Backup_Slots.py backup my-backup
.venv/bin/python python/Backup_Slots.py restore my-backup

# Write on the pedal's display (see Text from the computer)
.venv/bin/python python/Send_Text.py "Sweet Child"

# Answer the pedal as a Kemper would, to try Kemper_Mode without an amp
.venv/bin/python python/Kemper_Sim.py

# Update the firmware, with nothing held on 0.58 or later
.venv/bin/python python/Update_Firmware.py midi-commander-custom-<version>.dfu

# Work the pedal hard for a minute and check it is still sound (demo configuration)
.venv/bin/python python/Stress_Test.py

# How long a press takes to leave as MIDI, quiet and under load (demo configuration)
.venv/bin/python python/Latency_Test.py
```

## Backups

`Backup_Slots.py backup` reads every slot that holds a configuration into a folder, `slot1.csv` to `slot4.csv`, plus a `backup.txt` with the date, the firmware and the name in each slot; with no folder given it makes one named after the date and time. Each CSV is an ordinary configuration, so any of them can be opened in the configurator or flashed on its own. `restore` checks every file before touching the pedal, lists what it will overwrite and asks first (`--yes` skips the question), writes each file to its slot and restarts the pedal once at the end; slots with no file in the folder are left as they are. A backup restored onto the pedal gives the same bytes it was read from, except that settings a configuration from older firmware never had are written with the value the pedal was already using for them.

The tools find the pedal by its USB MIDI name (`MIDI Commander Custom`), check the firmware version, and exchange the configuration as SysEx messages under manufacturer ID `0x7D`: erase (52), write 16-byte chunk (54), read chunk (56), version (58), reset (60), pedal readings (62), select a slot (64), press a switch (66), the pedal's state (68) and screen (70), put text on the display (72), restart in DFU mode (74, with the check bytes `44 46`), the banner's own text (76) and the latency of the last presses (78). The read-back commands need firmware 0.2 or later; the tools tell you if the pedal is older.

To watch what the pedal sends, use any MIDI monitor (MIDI Monitor on macOS, MIDI-OX on Windows, `aseqdump -p 'MIDI Commander Custom'` on Linux).

---

[← The configuration file](12-configuration-file.md) · [Contents](README.md)
