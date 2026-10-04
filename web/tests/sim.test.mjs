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
import { Pedal, portKind } from "../pedal.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const module = new WebAssembly.Module(fs.readFileSync(path.join(root, "web/pedal-sim.wasm")));
const firmwareVersion = /FIRMWARE_VERSION\s+"([^"]+)"/.exec(fs.readFileSync(path.join(root, "firmware/Core/Inc/main.h"), "utf8"))[1];

// The demo packed by the Python tools: {config, image}. `tweak`, Python run
// on its sections `d` before packing, changes it for one test
function packDemo(tweak = "") {
  const script = [
    "import sys, json",
    "from lib.configCsv import read_config_csv",
    "from lib.slotIO import pack_sections",
    "d = read_config_csv('demo-all-features.csv')",
    tweak,
    "c, i = pack_sections(d)",
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

// The flash of a simulator with a configuration written in slot 1
async function flashWith(packed) {
  const sim = newSim();
  const pedal = await Pedal.open(sim.access);
  pedal.pause = 0;
  await running(sim, async () => {
    await pedal.selectSlot(0);
    await pedal.writeImage(firmwareVersion, packed.config, packed.image);
  });
  pedal.reset();
  await null;
  sim.run(10);
  return sim.flash;
}

before(async () => {
  demo = packDemo();
  demoFlash = await flashWith(demo);
});

function simWithDemo(flash = demoFlash) {
  const sim = new Simulator(module, { persist: false });
  sim.flash = Uint8Array.from(flash);
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
  // then the second extension area with the MIDI map, the long press labels
  // and the bank switches' labels
  const sizes = { config: demo.config.length, double: 10240, doubleOffset: 12 * 2048, ext2Offset: 17 * 2048, ext2: 16 + 32 * 12 + 32 * 8 * 4 + 16 };
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

test("a bank's enter list of 80 messages reaches USB and DIN whole (before 1.03, 32 did)", async () => {
  // Bank 7 of the demo, empty on entering, gets five CCs on all sixteen channels
  const tweak = [
    "e = d['BankEnter_Settings']",
    "r = e.index[e.Bank_Number.astype(str) == '7'][0]",
    "for k, letter in enumerate('ABCDEFGHIJ'):",
    "    if k % 2 == 0:",
    "        e.loc[r, letter + '_CommandType'] = 'Chan'",
    "        e.loc[r, letter + '_Channel_(PC/CC/Note/PB)'] = '1-16'",
    "    else:",
    "        e.loc[r, letter + '_CommandType'] = 'CC'",
    "        e.loc[r, letter + '_Channel_(PC/CC/Note/PB)'] = '1'",
    "        e.loc[r, letter + '_Number_(PC/CC/Note)'] = str(40 + k // 2)",
    "        e.loc[r, letter + '_OnValue_(CC/PB)'] = '1'",
    "        e.loc[r, letter + '_Toggle_(CC/PB/Note)'] = 'N'",
  ].join("\n");
  const sim = simWithDemo(await flashWith(packDemo(tweak)));
  const pedal = await Pedal.open(sim.access);
  const seen = watch(sim);
  const want = [];
  for (let cc = 40; cc < 45; cc++) {
    for (let ch = 0; ch < 16; ch++) want.push(`b${ch.toString(16)} ${cc.toString(16)} 01`);
  }
  sim.usbIn([0xb0, 32, 7]);                // the demo's Bank_Change_CC: to bank 7
  sim.run(300);
  const list = (port) => seen.filter((m) => m.startsWith(port) && /^.{4}b. 2[89a-c] 01$/.test(m)).map((m) => m.slice(4));
  assert.equal((await pedal.getState()).bank, 7);
  assert.deepEqual(list("USB"), want);
  assert.deepEqual(list("DIN"), want);
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

test("a page the pedal was rewriting when the power went is finished from its copy at the next start", async () => {
  const sim = simWithDemo();
  let pedal = await Pedal.open(sim.access);
  const hold = (s, id) => { s.footswitch(id, true); s.run(1200); s.footswitch(id, false); s.run(600); };
  const toBank2 = (s) => { hold(s, 2); tap(s, 0); tap(s, 2); };
  toBank2(sim);
  tap(sim, 1);
  tap(sim, 5);
  for (let i = 0; i < 2; i++) {             // Scene Save: a page patch
    sim.footswitch(4, true); sim.run(60); sim.footswitch(4, false); sim.run(60);
  }
  sim.run(800);
  tap(sim, 1);
  tap(sim, 5);
  // The copy page, then the log with its last note: [page address][sum][0 when done]
  const COPY = 0x3E800, LOG = 0x3F000, BASE = 0x10000;
  const flash = sim.flashNow();
  const view = new DataView(flash.buffer, flash.byteOffset);
  let last = -1;
  for (let i = 0; i < 256; i++) if (view.getUint32(LOG + 8 * i, true) !== 0xFFFFFFFF) last = i;
  assert.ok(last >= 0, "the patch left a note");
  const note = LOG + 8 * last;
  assert.equal(view.getUint16(note + 6, true), 0, "marked done");
  const page = view.getUint32(note, true) - BASE;
  assert.ok(flash.slice(COPY, COPY + 2048).every((b) => b === 0xFF), "the copy erased for the next one");
  // Cut after the erase: the copy written, the page blank, the note not done
  const cut = flash.slice();
  cut.set(flash.slice(page, page + 2048), COPY);
  cut.fill(0xFF, page, page + 2048);
  cut[note + 6] = 0xFF; cut[note + 7] = 0xFF;
  const again = new Simulator(module, { persist: false });
  again.flash = cut;
  again.start();
  clearInterval(again.timer);
  clearInterval(again.saveTimer);
  again.run(1300);
  const after = again.flashNow();
  assert.deepEqual(after.slice(page, page + 2048), flash.slice(page, page + 2048), "the page is back");
  assert.equal(after[note + 6] | after[note + 7], 0, "and the note done");
  assert.ok(after.slice(COPY, COPY + 2048).every((b) => b === 0xFF), "and the copy erased");
  pedal = await Pedal.open(again.access);
  toBank2(again);
  hold(again, 4);                           // the scene saved before the cut
  const state = await pedal.getState();
  assert.deepEqual(state.toggles.slice(0, 6), [false, true, false, false, false, true]);
  // A note cut before its address was written is left alone: the page was not touched yet
  const early = flash.slice();
  early.fill(0x00, page, page + 16);
  early[note + 2] = 0xFF; early[note + 3] = 0xFF; early[note + 6] = 0xFF; early[note + 7] = 0xFF;
  const third = new Simulator(module, { persist: false });
  third.flash = early;
  third.start();
  clearInterval(third.timer);
  clearInterval(third.saveTimer);
  third.run(1300);
  assert.deepEqual(third.flashNow().slice(page, page + 16), new Uint8Array(16));
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

test("with USB_Ports at 3, cable 1 goes straight to DIN and the pedal answers on the cable asked", async () => {
  const flash = await flashWith(packDemo("g = d['Global_Settings']\ng.loc[g.Label == 'USB_Ports', 'Value'] = '3'"));
  const sim = simWithDemo(flash);
  const pedal = await Pedal.open(sim.access);
  const seen = watch(sim);
  const events = [];
  sim.onUsbEvents = (data) => { for (let i = 0; i < data.length; i += 4) events.push(data.slice(i, i + 4)); };
  const bank = (await pedal.getState()).bank;
  events.length = 0;

  // On cable 1 the demo's Bank_Change_CC, a remote press and a SysEx for the
  // device behind: all on DIN as they came, none of it seen by the pedal
  sim.usbEvents([0x1b, 0xb0, 32, 7, 0x1b, 0xbf, 102, 127, 0x14, 0xf0, 0x00, 0x20, 0x17, 0x33, 0x01, 0xf7, 0x1b, 0xbf, 102, 0]);
  sim.run(300);
  assert.deepEqual(seen.filter((m) => m.startsWith("DIN")), ["DIN b0 20 07", "DIN bf 66 7f", "DIN f0 00 20 33 01 f7", "DIN bf 66 00"]);
  assert.deepEqual(events, [], "nothing back on USB");
  assert.equal((await pedal.getState()).bank, bank);
  events.length = 0;

  // GET_VERSION on cables 2 and 0 at once, their halves interleaved
  sim.usbEvents([0x24, 0xf0, 0x7d, 0x3a, 0x04, 0xf0, 0x7d, 0x3a, 0x25, 0xf7, 0, 0, 0x05, 0xf7, 0, 0]);
  sim.run(10);
  await null;
  const answers = events.filter((e) => e[1] === 0xf0 && e[3] === 0x3b).map((e) => e[0] >> 4);
  assert.deepEqual(answers, [2, 0]);
  events.length = 0;

  // What the pedal sends goes out on cables 0 and 2 alike
  sim.usbIn([0xb0, 32, 12]);               // bank 12 sends its enter list
  sim.run(300);
  await null;
  const on = (cable) => events.filter((e) => e[0] >> 4 === cable).map((e) => [e[0] & 15, ...e.slice(1)]);
  assert.ok(on(0).length > 0);
  assert.deepEqual(on(2), on(0));
  assert.deepEqual(on(1), []);
});

test("the tools know the three ports by name on macOS, Windows and Linux", () => {
  const kinds = (names) => names.map(portKind);
  assert.deepEqual(kinds(["MIDI Commander Custom", "MIDI Commander Custom Pedal", "MIDI Commander Custom DIN", "MIDI Commander Custom Config"]),
    ["pedal", "pedal", "din", "config"]);
  assert.deepEqual(kinds(["MIDI Commander Custom", "MIDIOUT2 (MIDI Commander Custom)", "MIDIIN3 (MIDI Commander Custom)"]),
    ["pedal", "din", "config"]);
  assert.deepEqual(kinds(["MIDI Commander Custom:MIDI Commander Custom MIDI 1 20:0", "MIDI Commander Custom:MIDI Commander Custom MIDI 2 20:1",
    "MIDI Commander Custom:MIDI Commander Custom MIDI 3 20:2"]), ["pedal", "din", "config"]);
});

// The Kemper reporting one parameter, as it answers the beacon
const kemperParam = (page, param, value) => [0xf0, 0x00, 0x20, 0x33, 0x00, 0x00, 0x01, 0x00, page, param, (value >> 7) & 0x7f, value & 0x7f, 0xf7];
const lit = (sim, x, y) => Boolean(sim.screen()[(y >> 3) * 130 + x] & (1 << (y & 7)));

test("with Kemper_Mode, the amp's tuner takes the screen while it is up", async () => {
  const sim = simWithDemo(await flashWith(packDemo("g = d['Global_Settings']\ng.loc[g.Label == 'Kemper_Mode', 'Value'] = 'Y'")));
  sim.run(10000);                           // the demo's power on banner goes by first
  const kemper = (page, param, value) => { sim.usbIn(kemperParam(page, param, value)); sim.run(60); };
  assert.ok(infoLineIs(sim, "1/10>S01"));

  kemper(0x7f, 0x7e, 1);                    // the tuner opens: no note yet
  assert.ok(!infoLineIs(sim, "1/10>S01"), "the tuner has the screen");
  assert.ok(lit(sim, 64, 40) && lit(sim, 64, 52), "the scale's middle mark");
  assert.ok(!lit(sim, 64, 56), "and no needle");

  kemper(0x7d, 0x54, 57);                   // an A
  kemper(0x7c, 0x0f, 8192 + 100);           // in tune: the note boxed in, the needle solid
  assert.ok(lit(sim, 48, 1) && lit(sim, 80, 1), "the box");
  assert.ok(lit(sim, 65, 56), "the needle, filled in");

  kemper(0x7c, 0x0f, 8192 + 3400);          // sharp: the needle at the right end
  assert.ok(!lit(sim, 48, 1) && !lit(sim, 80, 1), "no box");
  assert.ok(lit(sim, 122, 50) && lit(sim, 122, 60) && !lit(sim, 124, 56), "the needle's outline");
  assert.ok(!lit(sim, 65, 56));

  kemper(0x7f, 0x7e, 0);                    // closed on the amp: the bank is back
  sim.run(100);
  assert.ok(infoLineIs(sim, "1/10>S01"));

  kemper(0x7d, 0x54, 64);                   // a note opens it too, then the amp goes quiet
  assert.ok(!infoLineIs(sim, "1/10>S01"));
  sim.run(3500);
  assert.ok(infoLineIs(sim, "1/10>S01"), "an amp that stops answering takes its tuner away");
});

// The GT-1000 answering a question: DT1 with the address as four 7 bit bytes
function gtData(address, data) {
  const body = [(address >> 24) & 0x7f, (address >> 16) & 0x7f, (address >> 8) & 0x7f, address & 0x7f, ...data];
  const sum = (128 - (body.reduce((a, b) => a + b, 0) & 0x7f)) & 0x7f;
  return [0xf0, 0x41, 0x10, 0x00, 0x00, 0x00, 0x4f, 0x12, ...body, sum, 0xf7];
}
const hex = (bytes) => bytes.map((b) => b.toString(16).padStart(2, "0")).join(" ");
const gtAsk = (a, size) => {
  const body = [(a >> 24) & 0x7f, (a >> 16) & 0x7f, (a >> 8) & 0x7f, a & 0x7f, 0, 0, 0, size];
  const sum = (128 - (body.reduce((x, y) => x + y, 0) & 0x7f)) & 0x7f;
  return "DIN " + hex([0xf0, 0x41, 0x7f, 0x00, 0x00, 0x00, 0x4f, 0x11, ...body, sum, 0xf7]);
};

test("with GT1000_Mode, the patch name is on the display and the ASSIGNs light the buttons", async () => {
  const sim = simWithDemo(await flashWith(packDemo("g = d['Global_Settings']\ng.loc[g.Label == 'GT1000_Mode', 'Value'] = 'Y'")));
  const seen = watch(sim);
  sim.run(10000);                           // the demo's power on banner goes by first
  assert.ok(seen.includes("DIN f0 41 7f 00 00 00 4f 12 7f 00 00 01 01 7f f7"), "asked to report changes");
  assert.ok(seen.includes(gtAsk(0x00000000, 4)), "and asked for the patch number every second");
  assert.ok(!seen.some((m) => m.includes(" 4f 11 10 00 ")), "nothing of a patch not heard of yet");
  tap(sim, 1);                              // the FX bank: switch 1 sends CC 10, a toggle
  seen.length = 0;

  const unit = (address, data) => { sim.usbIn(gtData(address, data)); sim.run(60); };
  unit(0x00000000, [0, 0, 0, 12]);          // patch 12: the pedal asks for the rest of it
  assert.ok(seen.includes(gtAsk(0x10000000, 16)), "the name");
  assert.ok(seen.includes(gtAsk(0x10000300, 14)) && seen.includes(gtAsk(0x10000a40, 14)), "the sixteen ASSIGNs");

  unit(0x10000000, [..."Lead Boost      "].map((c) => c.charCodeAt(0)));
  sim.run(200);
  assert.ok(infoLineIs(sim, "Lead Boost"), "the patch name in the info line");

  // ASSIGN 1: on, target 158 (DELAY 1 ON OFF), min 0, max 1, source 31 (CC 10)
  seen.length = 0;
  unit(0x10000300, [1, 0, 0, 9, 14, 0, 0, 0, 0, 0, 0, 0, 1, 31]);
  assert.ok(seen.includes(gtAsk(0x10001d00, 1)), "the switch of the effect it switches");
  const pedal = await Pedal.open(sim.access);
  assert.equal((await running(sim, () => pedal.getState())).toggles[0], false);

  unit(0x10001d00, [1]);                    // DELAY 1 on: the button sending CC 10 lights
  sim.run(100);
  assert.equal((await running(sim, () => pedal.getState())).toggles[0], true);
  unit(0x10001d00, [0]);                    // and off again, switched on the unit
  sim.run(100);
  assert.equal((await running(sim, () => pedal.getState())).toggles[0], false);

  unit(0x10001c00, [1]);                    // an effect no ASSIGN switches changes nothing
  sim.run(100);
  assert.equal((await running(sim, () => pedal.getState())).toggles[0], false);
  const garbled = gtData(0x10001d00, [1]);
  garbled[garbled.length - 2] ^= 1;         // nor does a message with the wrong sum
  sim.usbIn(garbled);
  sim.run(100);
  assert.equal((await running(sim, () => pedal.getState())).toggles[0], false);
});

// The 6x8 font as its picture draws it, a row of 8 bits per line, the leftmost pixel in bit 7
const font6x8 = fs.readFileSync(path.join(root, "firmware/Middlewares/stm32-ssd1306-master/ssd1306/fonts/6x8.txt"), "utf8")
  .split("\n").filter((line) => /^[#.]{6}$/.test(line))
  .map((line) => parseInt(line.replace(/#/g, "1").replace(/\./g, "0").padEnd(8, "0"), 2));

// Whether the screen holds this text in the 6x8 font with its top left at x, y
test("a box of switches on an expression jack holds down the pedal's switches", async () => {
  const sim = simWithDemo(await flashWith(packDemo([
    "e = d['Expression_Settings']",
    "e.loc[e.Pedal == '2', ['Output', 'Min_ADC', 'Max_ADC', 'Invert', 'Box_2', 'Box_3']] = ['Switches', '0', '4095', 'N', '2', 'Up']",
  ].join("\n"))));
  const pedal = await Pedal.open(sim.access);
  const bank = async () => (await running(sim, () => pedal.getState())).bankName;
  const box = (value) => { sim.pedal(1, value); sim.run(300); };
  const seen = watch(sim);
  box(0);
  assert.equal(await bank(), "HOME");

  box(1024);                                // switch 1 holds nothing down
  box(0);
  assert.equal(await bank(), "HOME");
  box(2048);                                // switch 2 is switch 2: the index goes to FX
  box(0);
  sim.run(600);
  assert.equal(await bank(), "FX");
  box(3072);                                // switch 3 is Bank Up
  box(0);
  sim.run(600);
  assert.notEqual(await bank(), "FX");
  box(4095);                                // past the last level, a pedal at the toe: nothing
  box(0);
  assert.deepEqual(seen.filter((m) => /^(USB|DIN) b[0-9a-f] 0b /.test(m)), [], "and no CC of a pedal");
});

function smallTextAt(sim, x, y, text) {
  for (let i = 0; i < text.length; i++) {
    for (let row = 0; row < 8; row++) {
      for (let c = 0; c < 6; c++) {
        const want = Boolean((font6x8[(text.charCodeAt(i) - 32) * 8 + row] << c) & 0x80);
        if (lit(sim, x + i * 6 + c, y + row) !== want) return false;
      }
    }
  }
  return true;
}

const cellRows = (sim) => Array.from({ length: 44 }, (_, y) => Array.from({ length: 128 }, (_, x) => lit(sim, x, y + 20)).join()).join();

test("with the bank switches at MIDI only and labelled, the screen shows ten cells", async () => {
  const demoWith = async (mode, down, up) => {
    const tweak = [
      "g = d['Global_Settings']",
      `g.loc[g.Label == 'Bank_Switch_Mode', 'Value'] = '${mode}'`,
      "s = d['BankSwitch_Settings']",
      "s['Label'] = ''",
      `s.loc[(s.Switch == 'Down') & (s.Press == 'Short'), 'Label'] = '${down}'`,
      `s.loc[(s.Switch == 'Up') & (s.Press == 'Short'), 'Label'] = '${up}'`,
    ].join("\n");
    const sim = simWithDemo(await flashWith(packDemo(tweak)));
    sim.run(10000);                         // the demo's power on banner goes by first
    return sim;
  };
  // Five to a row, Bank Up on top and Bank Down below, in the 6x8 font
  const ten = await demoWith("MIDI only", "PREV", "NEXT");
  assert.ok(smallTextAt(ten, 102, 26, "NEXT"), "Bank Up's label, top right");
  assert.ok(smallTextAt(ten, 102, 48, "PREV"), "Bank Down's label, bottom right");

  // One label is enough; the other switch shows its name
  const one = await demoWith("MIDI only", "", "NEXT");
  assert.ok(smallTextAt(one, 102, 26, "NEXT"));
  assert.ok(smallTextAt(one, 108, 48, "DN"));

  // Changing bank, or with no label at all, the eight cells as before
  const plain = cellRows(await demoWith("Bank+MIDI", "", ""));
  assert.equal(cellRows(await demoWith("Bank+MIDI", "PREV", "NEXT")), plain, "the switches change bank: no labels for them");
  assert.equal(cellRows(await demoWith("MIDI only", "", "")), plain, "no labels: the screen as it always was");
});
