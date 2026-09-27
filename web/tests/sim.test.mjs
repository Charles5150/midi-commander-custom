// The simulated pedal (firmware/sim, web/sim.js) driven as the page drives
// it, through pedal.js. Needs web/pedal-sim.wasm (firmware/sim/build.sh) and
// Python with python/requirements.txt, which packs the demo as
// CSV_to_Flash.py does. Run from the repository root: node --test web/tests/
import { test, before } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { Simulator, toUsbEvents, MidiParser } from "../sim.js";
import { Pedal } from "../pedal.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const module = new WebAssembly.Module(fs.readFileSync(path.join(root, "web/pedal-sim.wasm")));
const firmwareVersion = /FIRMWARE_VERSION\s+"([^"]+)"/.exec(fs.readFileSync(path.join(root, "firmware/Core/Inc/main.h"), "utf8"))[1];

// The demo packed by the Python tools: {config, image}
function packDemo() {
  const script = [
    "import sys, json",
    "from lib.configCsv import read_config_csv",
    "from lib.slotIO import pack_sections",
    "c, i = pack_sections(read_config_csv('demo-all-features.csv'))",
    "print(json.dumps([bytes(c).hex(), bytes(i).hex()]))",
  ].join("\n");
  const out = execFileSync(process.env.PYTHON || "python3", ["-c", script], { cwd: path.join(root, "python") });
  const [config, image] = JSON.parse(out).map((hex) => Uint8Array.from(Buffer.from(hex, "hex")));
  return { config, image };
}

// A simulator whose time only moves when the test says, or while it waits on
// the pedal, as the page's timer would
function newSim() {
  const sim = new Simulator(module, { persist: false });
  sim.start();
  clearInterval(sim.timer);
  clearInterval(sim.saveTimer);
  sim.run(1300);
  return sim;
}

async function running(sim, work) {
  const clock = setInterval(() => sim.run(5), 1);
  try { return await work(); } finally { clearInterval(clock); }
}

let demo;
let demoFlash;      // the flash of a simulator with the demo written in slot 1

before(async () => {
  demo = packDemo();
  const sim = newSim();
  const pedal = await Pedal.open(sim.access);
  pedal.pause = 0;
  await running(sim, async () => {
    await pedal.selectSlot(0);
    await pedal.writeImage(firmwareVersion, demo.config, demo.image);
  });
  pedal.reset();
  await null;
  sim.run(10);
  demoFlash = sim.flash;
});

function simWithDemo() {
  const sim = new Simulator(module, { persist: false });
  sim.flash = Uint8Array.from(demoFlash);
  sim.start();
  clearInterval(sim.timer);
  clearInterval(sim.saveTimer);
  sim.run(1300);
  return sim;
}

function watch(sim) {
  const seen = [];
  sim.onOutput = (port, msg) => seen.push(`${port} ${msg.map((b) => b.toString(16).padStart(2, "0")).join(" ")}`);
  return seen;
}

test("a blank simulator answers like the pedal, with no configuration", async () => {
  const sim = newSim();
  const pedal = await Pedal.open(sim.access);
  assert.equal(await pedal.version(), firmwareVersion);
  assert.deepEqual(await pedal.selectSlot(null), { target: 0, active: 0, valid: [] });
  assert.equal(await pedal.enterDfu(), false, "there is no bootloader to go to");
});

test("the demo written over SysEx reads back the same", async () => {
  const sim = simWithDemo();
  const pedal = await Pedal.open(sim.access);
  assert.deepEqual((await pedal.selectSlot(null)).valid, [0]);
  const sizes = { config: demo.config.length, double: demo.image.length - 12 * 2048, doubleOffset: 12 * 2048 };
  const back = await running(sim, () => pedal.readImage(firmwareVersion, sizes));
  assert.deepEqual(back.data, demo.config);
  assert.deepEqual(back.image, demo.image);
});

test("writing restarts the simulated pedal, whose ports go and come back", async () => {
  const sim = simWithDemo();
  const states = [];
  sim.access.addEventListener("statechange", (e) => { if (e.port.type === "input") states.push(e.port.state); });
  const pedal = await Pedal.open(sim.access);
  let gone = false;
  pedal.onGone = () => { gone = true; };
  pedal.reset();
  await null;
  sim.run(1);
  assert.ok(gone);
  assert.deepEqual(states, ["disconnected", "connected"]);
  const again = await Pedal.open(sim.access);
  assert.equal((await again.getState()).bankName, "HOME");
});

test("the demo's first bank on the display and in GET_STATE", async () => {
  const sim = simWithDemo();
  const pedal = await Pedal.open(sim.access);
  const s = await pedal.getState();
  assert.equal(s.bank, 0);
  assert.equal(s.bankName, "HOME");
  assert.deepEqual(s.labels, ["LOOP", "FX", "PTCH", "KEYS", "MEDI", "TMPO", "KNOB", "SONG"]);
  const screen = await pedal.getScreen();
  assert.deepEqual(screen, Array.from(sim.screen()), "GET_SCREEN is the display buffer");
  assert.ok(screen.some((b) => b !== 0), "something is drawn");
});

function tap(sim, id) {
  sim.footswitch(id, true);
  sim.run(100);
  sim.footswitch(id, false);
  sim.run(600);
}

test("the demo's index bank: switch 1 goes to the looper bank, where it sends CC 1", async () => {
  const sim = simWithDemo();
  const seen = watch(sim);
  tap(sim, 0);
  assert.deepEqual(seen.splice(0), [], "the index only changes bank");
  const pedal = await Pedal.open(sim.access);
  assert.equal((await pedal.getState()).bankName, "LOOP");
  tap(sim, 0);
  assert.deepEqual(seen.splice(0), ["USB b0 01 7f", "DIN b0 01 7f"], "over USB and on the DIN output");
  let lit = 0;
  for (let i = 0; i < 40; i++) { sim.run(25); lit = Math.max(lit, sim.leds()[0]); }
  assert.equal(lit, 16, "its LED lit");
  tap(sim, 0);
  assert.deepEqual(seen.splice(0), ["USB b0 01 00", "DIN b0 01 00"], "a toggle: off again");
});

test("a press from the page goes through the same logic", async () => {
  const sim = simWithDemo();
  const pedal = await Pedal.open(sim.access);
  await running(sim, async () => {
    await pedal.press("2", true);
    await new Promise((r) => setTimeout(r, 60));
    await pedal.press("2", false);
    await new Promise((r) => setTimeout(r, 700));
  });
  assert.equal((await pedal.getState()).bankName, "FX");
});

test("Bank Up moves on from the index bank", async () => {
  const sim = simWithDemo();
  tap(sim, 9);
  const pedal = await Pedal.open(sim.access);
  const s = await pedal.getState();
  assert.notEqual(s.bank, 0);
  const names = fs.readFileSync(path.join(root, "python/demo-all-features.csv"), "utf8").split(/\r?\n/)
    .map((l) => l.split(",")).filter((c) => /^\d+$/.test(c[0]) && c.length >= 2);
  assert.ok(names.some((c) => Number(c[0]) === s.bank && c[1] === s.bankName), `bank ${s.bank} is ${s.bankName} in the demo`);
});

test("MIDI into the page's port: raw bytes to USB events and back", () => {
  assert.deepEqual(toUsbEvents([0xb0, 10, 127]), [0xb, 0xb0, 10, 127]);
  assert.deepEqual(toUsbEvents([0xc1, 5]), [0xc, 0xc1, 5, 0]);
  assert.deepEqual(toUsbEvents([0xf8]), [0xf, 0xf8, 0, 0]);
  assert.deepEqual(toUsbEvents([0xf0, 0x7d, 58, 0xf7]), [0x4, 0xf0, 0x7d, 58, 0x5, 0xf7, 0, 0]);
  assert.deepEqual(toUsbEvents([0xf0, 0x7d, 0xf7]), [0x7, 0xf0, 0x7d, 0xf7]);
  const got = [];
  const p = new MidiParser((m) => got.push(m));
  p.push([0x90, 60, 100, 62, 0, 0xf8, 0xf0, 1, 2, 0xf7, 0xc0, 3]);
  assert.deepEqual(got, [[0x90, 60, 100], [0x90, 62, 0], [0xf8], [0xf0, 1, 2, 0xf7], [0xc0, 3]]);
});
