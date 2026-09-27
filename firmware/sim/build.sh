#!/bin/sh
# Builds the simulator, the firmware's own sources for WebAssembly, into
# web/pedal-sim.wasm (or the path given). Needs clang and wasm-ld, from LLVM:
# on macOS `brew install lld`, on Debian and Ubuntu `apt install clang lld`.
set -e
here=$(cd "$(dirname "$0")" && pwd)
fw="$here/.."
out=${1:-"$fw/../web/pedal-sim.wasm"}
CC=${CC:-clang}

src="
  $here/sim.c
  $here/sim_libc.c
  $fw/Core/Src/switch_router.c
  $fw/Core/Src/midi_cmds.c
  $fw/Core/Src/display.c
  $fw/Core/Src/tempo.c
  $fw/Core/Src/expression.c
  $fw/Core/Src/editor.c
  $fw/Core/Src/kemper.c
  $fw/Core/Src/leds.c
  $fw/Core/Src/flash_midi_settings.c
  $fw/Core/Src/state_store.c
  $fw/Core/Src/restart_state.c
  $fw/Core/Src/sleep.c
  $fw/Core/Src/tiny_printf.c
  $fw/Core/Src/banner_store.c
  $fw/Core/Src/latency.c
  $fw/USB_DEVICE/App/usbd_midi_if.c
  $fw/Middlewares/stm32-ssd1306-master/ssd1306/ssd1306.c
  $fw/Middlewares/stm32-ssd1306-master/ssd1306/ssd1306_fonts.c
"

# The stack first, below 0x10000; the flash at 0x10000, 256 kB (FLASH_BASE in
# include/stm32f1xx_hal.h); the module's own data above it, from 0x50000
$CC --target=wasm32 -O2 -std=gnu11 -ffreestanding -nostdlib -fno-builtin \
  -Wall -Wno-unused-function -Wno-unused-variable -Wno-unused-but-set-variable \
  -DSTM32F103xE -DSIM \
  -I"$here/include" -I"$fw/Core/Inc" -I"$fw/USB_DEVICE/App" \
  -I"$fw/Middlewares/stm32-ssd1306-master/ssd1306" \
  -Wl,--no-entry -Wl,--stack-first -Wl,--global-base=327680 -Wl,-z,stack-size=65536 \
  -Wl,--export=__heap_base -Wl,--export=__data_end -Wl,--export=__stack_pointer -Wl,--export=__global_base \
  -o "$out" $src
echo "$out: $(wc -c < "$out" | tr -d ' ') bytes"
