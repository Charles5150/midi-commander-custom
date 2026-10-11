// dfu.js's checks on a .dfu file, the same as firmwareUpdate.check_image in
// python/lib, on files made by tools/bin_to_dfuse.py. Run from the
// repository root: node --test web/tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { loadImage, APP_ADDRESS, APP_MAX_SIZE } from "../dfu.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

// A .dfu file holding payloadLength bytes, a stack pointer and a reset vector first
function dfu(payloadLength) {
  const script = [
    "import struct, sys",
    "sys.path.insert(0, 'tools')",
    "import bin_to_dfuse",
    "n = int(sys.argv[1])",
    "payload = (struct.pack('<II', 0x20010000, 0x08003135) + bytes(max(0, n - 8)))[:n]",
    "sys.stdout.buffer.write(bin_to_dfuse.generate_dfuse(payload, load_address=int(sys.argv[2]), alt_setting=0,",
    "    target_name='ST...', vendor=0x0483, product=0xDF11, device=0, dfu_version=0x011A))",
  ].join("\n");
  return new Uint8Array(execFileSync(process.env.PYTHON || "python3", ["-c", script, String(payloadLength), String(APP_ADDRESS)], { cwd: root }));
}

test("a firmware image is taken whole", () => {
  assert.equal(loadImage(dfu(1008)).length, 1008);
});

test("an image too short or too big says which (before, too short was called too big)", () => {
  assert.throws(() => loadImage(dfu(4)), /4 bytes, too short to be a firmware/);
  assert.throws(() => loadImage(dfu(APP_MAX_SIZE + 8)), new RegExp(`more than the ${APP_MAX_SIZE} there is room for`));
});
