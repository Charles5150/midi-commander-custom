# PlatformIO Migration Notes

This repository now contains a [PlatformIO](https://platformio.org/) configuration that builds the firmware directly out of `firmware/`, so no STM32CubeIDE project files are required.

## Project layout

- `platformio.ini` selects `genericSTM32F103RET6` with the STM32Cube framework and points `src_dir` to `firmware/` so the HAL/CMSIS sources live in a neutral directory.
- `build_src_filter` keeps only the firmware sources (Core, Drivers, USB, Middlewares) and skips the `Debug/` artifacts and README/LICENSE files to avoid compiler noise.
- All include directories from the Cube project (HAL, CMSIS, USB device stack, SSD1306 middleware, local headers) are added through `build_flags`. Update this list if you add new middleware paths.

## Environments

Two PlatformIO environments correspond to the original linker scripts:

| Environment | Linker script | Upload method | Typical use |
|-------------|---------------|---------------|-------------|
| `midi_debug` | `STM32F103RETX_FLASH.ld` | `stlink` | RAM-at-0x20000000, flash-at-0x08000000. Matches the "Debug" Cube target for on-board SWD debugging. Flashing it erases the stock DFU bootloader. |
| `midi_dfu`   | `STM32F103RETX_FLASH_DFU.ld` | `dfu-util` | Adds the 0x3000 DFU offset. Use this when you need binaries compatible with the stock Melo DFU loader. The default. |

Switch the default environment by changing `default_envs` in `platformio.ini` or by passing `-e` on the command line.

## Build & upload workflow

```bash
# Build the standard debugger-friendly image
pio run -e midi_debug

# Flash via ST-Link (adjust when using a different probe)
pio run -e midi_debug -t upload

# Build the DFU-offset image (also writes artifacts/dfu/platformio-<timestamp>.dfu)
pio run -e midi_dfu

# Push via dfu-util (device in DFU mode)
pio run -e midi_dfu -t upload
```

The `midi_dfu` upload recipe flashes the freshly generated `artifacts/dfu/platformio-latest.dfu` using PlatformIO's bundled `dfu-util` (see `scripts/post_build_dfuse.py` and `scripts/dfu_upload.py`), so the bootloader offset and metadata always match the DfuSe container you just built. Manual `dfu-util` invocations remain possible when you need extra control.

## Tips & follow-up tasks

1. **Startup/system files** – they are already part of `Core/Startup` and `Core/Src`. If CubeMX regenerates the project, re-run `pio run` to ensure nothing new needs to be whitelisted in `build_src_filter`.
2. **External tooling** – Python utilities (`python/CSV_to_Flash.py`) remain untouched and can be driven separately from firmware builds.
3. **Debug configuration** – PlatformIO will generate an OpenOCD configuration for ST-Link automatically. If you prefer Black Magic Probe or J-Link, override `debug_tool` and `upload_protocol` per-environment.
4. **DFU packaging** – `scripts/post_build_dfuse.py` runs after every `midi_dfu` build and invokes `tools/bin_to_dfuse.py`, so you automatically get a timestamped DfuSe container alongside the raw `.bin`.
5. **Interrupt/vectors** – `main.c` points `SCB->VTOR` at `g_pfnVectors`, wherever the linker script put it: `0x08003000` for `midi_dfu`, `0x08000000` for `midi_debug`.
6. **Continuous integration** – once comfortable with the PIO workflow, wire `pio run -e midi_debug` (and optionally `pio run -e midi_dfu`) into your CI system so firmware builds stay reproducible outside STM32CubeIDE.

With the configuration in place you can iterate entirely inside VS Code + PlatformIO. If you ever regenerate peripherals with CubeMX again, drop the refreshed sources into `firmware/` and re-run `pio run` to ensure the filters stay up to date.
