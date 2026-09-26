# Command line tools

**English** · [Español](../es/13-command-line-tools.md)

Everything the configurator does can also be done from a terminal, which is handy for scripts, backups and a quick flash before a gig. Run the tools from the repository root, with the pedal connected over USB in normal mode, not DFU mode.

The tools find the pedal by its USB MIDI name, `MIDI Commander Custom`, and check its firmware version before doing anything.

## Choosing a configuration slot

`CSV_to_Flash.py` and `Flash_to_CSV.py` act on one of the pedal's four [configuration slots](04-banks.md#four-configurations):

- `--slot 1` to `--slot 4` chooses the slot;
- left out, they use the slot the pedal is running.

Reading an empty slot is reported rather than producing a CSV. Firmware older than 0.24 has a single configuration, and the tools refuse any slot but 1 on it.

## CSV_to_Flash: send a configuration to the pedal

```bash
.venv/bin/python python/CSV_to_Flash.py my-config.csv
.venv/bin/python python/CSV_to_Flash.py --slot 2 my-config.csv
```

It checks the CSV, says how big the configuration is and asks `Continue? (y/N)` before writing anything; `--yes` or `-y` skips the question. Then it writes the slot and restarts the pedal.

## Flash_to_CSV: read a configuration back

```bash
.venv/bin/python python/Flash_to_CSV.py current-config.csv
.venv/bin/python python/Flash_to_CSV.py --slot 3 slot3.csv
```

It writes what the pedal holds into a CSV you can open in the configurator, including any change made with the [on-pedal editor](10-editing-on-the-pedal.md).

## Backups

`Backup_Slots.py` copies all four slots to a folder in one go, and puts them back.

```bash
.venv/bin/python python/Backup_Slots.py backup my-backup
.venv/bin/python python/Backup_Slots.py restore my-backup
```

**backup** reads every slot that holds a configuration into the folder:

- `slot1.csv` to `slot4.csv`, each an ordinary configuration that can be opened in the configurator or flashed on its own;
- `backup.txt`, with the date, the firmware and the name in each slot.

With no folder given, it makes one named after the date and time.

**restore** puts a backup folder back:

1. It checks every file before touching the pedal.
2. It lists the slots it will overwrite and asks first; `--yes` or `-y` skips the question.
3. It writes each file to its slot, and restarts the pedal once at the end.

Slots with no file in the folder are left as they are. A restored backup gives the same bytes it was read from, except that settings a configuration from older firmware never had are written with the value the pedal was already using for them.

## Send_Text: write on the display

```bash
.venv/bin/python python/Send_Text.py "Sweet Child"
.venv/bin/python python/Send_Text.py --banner "The Band  612 345 678"
```

Puts a text on the pedal's top line, or prints the SysEx bytes for a host to send with `--hex`; with `--banner` it reads, stores or clears the banner's own text. See [Text from the computer](09-the-display.md#text-from-the-computer) and [The banner's own text](09-the-display.md#the-banners-own-text).

## Kemper_Sim: a Kemper to try Kemper_Mode without one

```bash
.venv/bin/python python/Kemper_Sim.py
kemper> rig Brit Crunch DLX
kemper> dly
```

It answers the pedal as a Kemper Profiler would, over the same USB link a Player uses. At its prompt:

| Command | What it does |
|---|---|
| `rig <name>` | names the rig the pedal shows |
| `a`, `b`, `c`, `d` | switches Stomp A, B, C or D on or off |
| `x`, `mod`, `dly`, `rev` | the same for the other modules |
| `show` | what the amp is supposed to be doing |
| `quit` | ends it |

See [Two way with a Kemper](11-devices.md#two-way-with-a-kemper).

## Update_Firmware: update the firmware

```bash
.venv/bin/python python/Update_Firmware.py midi-commander-custom-<version>.dfu
```

Checks the `.dfu` file, asks before flashing (`--yes` skips the question), puts the pedal in DFU mode, flashes it and starts it again, with nothing held on firmware 0.58 or later. See [Updating the firmware later](02-getting-started.md#updating-the-firmware-later).

## Stress_Test and Latency_Test: check the pedal

```bash
.venv/bin/python python/Stress_Test.py      # work the pedal hard for a minute and check it is still sound
.venv/bin/python python/Latency_Test.py     # how long a press takes to leave as MIDI, quiet and under load
```

Both need the demo configuration, `python/demo-all-features.csv`, on the pedal, and no foot. They are described in [CONTRIBUTING](../../../CONTRIBUTING.md#tests).

## Watching what the pedal sends

Any MIDI monitor shows it: MIDI Monitor on macOS, MIDI-OX on Windows, or `aseqdump -p 'MIDI Commander Custom'` on Linux.

<details><summary>Under the hood</summary>

The tools exchange the configuration as SysEx messages under manufacturer ID `0x7D`:

| Command | Number |
|---|---|
| erase | 52 |
| write a 16-byte chunk | 54 |
| read a chunk | 56 |
| version | 58 |
| reset | 60 |
| pedal readings | 62 |
| select a slot | 64 |
| press a switch | 66 |
| the pedal's state | 68 |
| the pedal's screen | 70 |
| put text on the display | 72 |
| restart in DFU mode, with the check bytes `44 46` | 74 |
| the banner's own text | 76 |
| the latency of the last presses | 78 |

The read-back commands need firmware 0.2 or later; the tools tell you if the pedal is older.

</details>

---

[← The configuration file](12-configuration-file.md) · [Contents](README.md)
