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
  // As the page takes them from the tools (py.js): the double press area,
  // then the second extension area with the MIDI map and the long press labels
  const sizes = { config: demo.config.length, double: 10240, doubleOffset: 12 * 2048, ext2Offset: 17 * 2048, ext2: 16 + 32 * 12 + 32 * 8 * 4 };
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

test("the demo's MIDI map turns what comes in over USB into what goes out on DIN", async () => {
  const sim = simWithDemo();
  const seen = watch(sim);
  const send = (bytes) => { sim.usbIn(bytes); sim.run(20); return seen.splice(0); };
  // A scene change from the DAW on channel 15 becomes two CCs on channel 2,
  // the second carrying the program; the PC itself stays behind
  assert.deepEqual(send([0xce, 5]), ["DIN b1 14 7f", "DIN b1 15 05"]);
  // The mod wheel on channel 14 turns round into CC 11 on channel 1, and goes
  // on as it came too, through the USB thru
  assert.deepEqual(send([0xbd, 1, 100]), ["DIN b0 0b 1b", "DIN bd 01 64"]);
  // The pitch bend's upper seven bits as CC 4
  assert.deepEqual(send([0xed, 0x11, 0x50]), ["DIN b0 04 50"]);
  // Nothing in the map for this one: the thru passes it untouched
  assert.deepEqual(send([0xb2, 7, 99]), ["DIN b2 07 63"]);
  // A pad (note 36) runs the global bank's tuner button: on while it is down,
  // off when it comes up, on both outputs like a press
  assert.deepEqual(send([0x9d, 36, 90]), ["USB b0 44 7f", "DIN b0 44 7f"]);
  assert.deepEqual(send([0x8d, 36, 0]), ["USB b0 44 00", "DIN b0 44 00"]);
});

test("held, a Bank Reveal button shows the long press labels", async () => {
  const sim = simWithDemo();
  tap(sim, 4);                              // MEDI: the media keys bank
  const pedal = await Pedal.open(sim.access);
  const own = await pedal.getState();
  assert.equal(own.bankName, "MEDI");
  const before = Array.from(sim.screen());
  sim.footswitch(6, true);                  // hold C past the long press
  sim.run(1200);
  const held = await pedal.getState();
  assert.deepEqual(held.labels, ["MPLY", "SNG2", "TOP0", "MSTP", "LOC0", "1:02", "HELD", "MREC"]);
  sim.run(50);
  assert.notDeepEqual(Array.from(sim.screen()), before, "the display shows them");
  sim.footswitch(6, false);
  sim.run(200);
  assert.deepEqual((await pedal.getState()).labels, own.labels, "let go, the buttons' own labels are back");
});

test("held, a Bank Direct button chooses any bank with two presses", async () => {
  const sim = simWithDemo();
  const pedal = await Pedal.open(sim.access);
  assert.equal((await pedal.getState()).bank, 0);
  sim.footswitch(2, true);                  // hold 3 on HOME past the long press
  sim.run(1200);
  sim.footswitch(2, false);
  sim.run(200);
  let state = await pedal.getState();
  assert.equal(state.bank, 0, "nothing changes yet");
  assert.deepEqual(state.labels, ["0+", "8+", "16+", "24+", "-", "-", "-", "-"]);
  const seen = watch(sim);
  tap(sim, 2);                              // the group 16-23
  state = await pedal.getState();
  assert.deepEqual(state.labels, ["S05", "S06", "S07", "S08", "S09", "S10", "S11", "S12"]);
  assert.deepEqual(seen, [], "choosing sends nothing");
  tap(sim, 5);                              // B: bank 21
  state = await pedal.getState();
  assert.equal(state.bank, 21);
  assert.equal(state.bankName, "S10");
  assert.notEqual(state.labels[0], "16+", "the bank's own labels");
});

test("A-D, or ten seconds without a press, drop the Bank Direct chooser", async () => {
  const sim = simWithDemo();
  const pedal = await Pedal.open(sim.access);
  const home = (await pedal.getState()).labels;
  const open = () => { sim.footswitch(2, true); sim.run(1200); sim.footswitch(2, false); sim.run(200); };
  open();
  const seen = watch(sim);
  tap(sim, 4);                              // A: no group there
  let state = await pedal.getState();
  assert.equal(state.bank, 0);
  assert.deepEqual(state.labels, home);
  assert.deepEqual(seen, [], "and the press of A does nothing else");
  open();
  sim.run(9000);
  assert.equal((await pedal.getState()).labels[0], "0+", "still waiting");
  sim.run(1500);
  state = await pedal.getState();
  assert.equal(state.bank, 0);
  assert.deepEqual(state.labels, home);
});

test("a Scene Save stores the bank's toggles into a scene, kept after a restart", async () => {
  const sim = simWithDemo();
  let pedal = await Pedal.open(sim.access);
  const hold = (id) => { sim.footswitch(id, true); sim.run(1200); sim.footswitch(id, false); sim.run(600); };
  hold(2);                                  // Bank Direct on HOME: group 0+, then bank 2
  tap(sim, 0);
  tap(sim, 2);
  let state = await pedal.getState();
  assert.equal(state.bank, 2);
  assert.deepEqual(state.toggles.slice(0, 3), [false, false, false]);
  tap(sim, 1);                              // REVS and BLNK on: not the demo's mix (1 and 3)
  tap(sim, 5);
  for (let i = 0; i < 2; i++) {             // a double press of A saves into A's held scene
    sim.footswitch(4, true); sim.run(60); sim.footswitch(4, false); sim.run(60);
  }
  sim.run(800);
  state = await pedal.getState();
  assert.deepEqual(state.toggles.slice(0, 6), [false, true, false, false, false, true], "saving presses nothing");
  tap(sim, 1);                              // both off again, then held A brings them back
  tap(sim, 5);
  hold(4);
  state = await pedal.getState();
  assert.deepEqual(state.toggles.slice(0, 6), [false, true, false, false, false, true]);
  // In flash: a pedal started from it recalls the saved scene
  tap(sim, 1);
  tap(sim, 5);
  const again = new Simulator(module, { persist: false });
  again.flash = sim.flashNow();
  again.start();
  clearInterval(again.timer);
  clearInterval(again.saveTimer);
  again.run(1300);
  pedal = await Pedal.open(again.access);
  const holdAgain = (id) => { again.footswitch(id, true); again.run(1200); again.footswitch(id, false); again.run(600); };
  holdAgain(2);
  tap(again, 0);
  tap(again, 2);
  assert.equal((await pedal.getState()).bank, 2);
  holdAgain(4);
  state = await pedal.getState();
  assert.deepEqual(state.toggles.slice(0, 6), [false, true, false, false, false, true]);
});

// The 7x10 font of the firmware as its picture draws it, rows of 16 bits
// from ' ' on, the leftmost pixel in bit 15
const font7x10 = (() => {
  const src = fs.readFileSync(path.join(root, "firmware/Middlewares/stm32-ssd1306-master/ssd1306/fonts/7x10.txt"), "utf8");
  return src.split("\n").filter((line) => /^[#.]{7}$/.test(line))
    .map((line) => parseInt(line.replace(/#/g, "1").replace(/\./g, "0").padEnd(16, "0"), 2));
})();

// Whether the info line (x 50-127, y 6-15) holds just this text
function infoLineIs(sim, text) {
  const screen = sim.screen();
  for (let x = 50; x < 128; x++) {
    for (let y = 6; y < 16; y++) {
      const i = Math.floor((x - 50) / 7), ch = text.charCodeAt(i);
      const want = i < text.length && ch > 32
        && Boolean((font7x10[(ch - 32) * 10 + y - 6] << ((x - 50) % 7)) & 0x8000);
      const lit = Boolean(screen[(y >> 3) * 130 + x] & (1 << (y & 7)));
      if (lit !== want) return false;
    }
  }
  return true;
}

test("with Setlist_Display, the info line shows the place in the setlist and the next song", () => {
  const sim = simWithDemo();
  sim.run(10000);                           // the demo's power on banner goes by first
  assert.ok(infoLineIs(sim, "1/10>S01"), "HOME opens the setlist");
  tap(sim, 9);                              // Bank Up: the next song
  assert.ok(infoLineIs(sim, "2/10>S04"), "the second song, bank 12, and the one after it");
  tap(sim, 8);
  tap(sim, 8);                              // Bank Down from HOME: the last song
  assert.ok(infoLineIs(sim, "10/10 END"));
  tap(sim, 9);                              // round to HOME, then to a bank not in the list
  tap(sim, 0);
  assert.ok(infoLineIs(sim, "looper"), "a bank off the setlist keeps its own info");
});
