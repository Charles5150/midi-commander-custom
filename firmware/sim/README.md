# The simulated pedal

The web configurator's **Try without a pedal** runs the pedal's own firmware in
the browser: the sources in `Core/Src`, `USB_DEVICE/App/usbd_midi_if.c` and the
display library, unchanged, built for WebAssembly. Only what stands for the
chip is here:

- `include/`: ST's HAL and CMSIS headers replaced by the few types, registers
  and calls the sources use, plus the C library headers they include.
- `sim.c`: `main()` and the interrupts as the chip runs them, one millisecond
  at a time, and the functions the page calls. The flash is 256 kB of the
  module's memory at the same offsets as on the chip; the switches are GPIO
  pins, the expression pedals an ADC, the display the SSD1306 buffer, and
  what goes out over USB, the DIN output and as computer keys a queue the page
  reads.
- `sim_libc.c`: `memcpy` and the like; `snprintf` is the firmware's own.

`web/sim.js` loads the module and puts it behind a Web MIDI port of its own,
so the page talks to it with the same SysEx as to the pedal.

## Building

```sh
firmware/sim/build.sh            # writes web/pedal-sim.wasm
```

It needs clang and wasm-ld from LLVM: `brew install lld` on macOS (Apple's
clang has the WebAssembly target), `apt install clang lld` on Debian and
Ubuntu. The workflows build it for the tests and for the site.

## Testing

```sh
node --test web/tests/*.test.mjs
```

from the repository root, with Python and `python/requirements.txt`, which
packs the demo as `CSV_to_Flash.py` does (`PYTHON=` picks the interpreter).

## What is not simulated

The bootloader (no firmware update: `ENTER_DFU` answers that it cannot), the
watchdog (a lock-up would hang the page's timer instead), what is plugged into
the expression jacks (empty until a pedal is moved from the page) and timing
finer than a millisecond: the main loop runs once per millisecond, where the
chip runs it many times.
