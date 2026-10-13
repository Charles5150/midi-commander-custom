# Building with PlatformIO

The firmware is built with [PlatformIO](https://platformio.org/) straight out of `firmware/`. No STM32CubeIDE project is needed.

## Project layout

- `platformio.ini` builds for `genericSTM32F103RE` (an STM32F103RET6 at 72 MHz) with the `cmsis` framework, and points `src_dir` to `firmware/`. ST's HAL is part of the tree, in `firmware/Drivers/`.
- The startup code and `system_stm32f1xx.c` come from PlatformIO's CMSIS framework, so `build_src_filter` leaves out the copies in `firmware/`. It takes only the firmware's own sources (Core, the HAL, USB and the SSD1306 middleware), so `firmware/sim/`, the simulated pedal's WebAssembly build, stays out, and skips `Debug/` and the README and LICENSE files.
- The include directories (HAL, CMSIS, USB device stack, SSD1306 middleware, local headers) are listed in `build_flags`. Add new middleware paths there.
- The build links with `-flto` and writes a map file, `.pio/build/<env>/firmware.map`.

## Environments

| Environment | Linker script | Upload | Use |
|-------------|---------------|--------|-----|
| `midi_dfu`   | `STM32F103RETX_FLASH_DFU.ld` | `scripts/dfu_upload.py` | The default. Linked at 0x08003000, above the stock MeloAudio DFU bootloader. This is the image the releases ship. |
| `midi_debug` | `STM32F103RETX_FLASH.ld` | ST-Link | Linked at 0x08000000 for debugging over SWD. Flashing it erases the stock DFU bootloader. |

`main.c` points `SCB->VTOR` at `g_pfnVectors`, wherever the linker script put it, so the same code runs in both.

## Build and upload

```bash
pio run -e midi_dfu               # DFU image, also writes artifacts/dfu/platformio-<timestamp>.dfu and platformio-latest.dfu
pio run -e midi_dfu -t upload     # builds, then flashes artifacts/dfu/platformio-latest.dfu
pio run -e midi_debug             # ST-Link image
pio run -e midi_debug -t upload   # flashes it over ST-Link
```

After every `midi_dfu` build, `scripts/post_build_dfuse.py` runs `tools/bin_to_dfuse.py` to package the `.bin` as a DfuSe container.

The `midi_dfu` upload is set by `scripts/dfu_upload.py`. With the Python environment in `.venv` it runs `python/Update_Firmware.py`, so a pedal on firmware 0.58 or later goes into DFU mode by itself, nothing held, and starts the new build afterwards. Without `.venv` it runs `dfu-util` on its own, and the pedal has to be in DFU mode already.

CI (`.github/workflows/build.yml`) builds both environments on every push and pull request. Size limits, the tests and flashing by hand are in [CONTRIBUTING.md](CONTRIBUTING.md).
