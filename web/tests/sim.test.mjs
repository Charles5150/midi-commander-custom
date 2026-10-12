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
  // then the second extension area with the MIDI map, the long press labels,
  // the bank switches' labels, the preset names and the setlists
  const sizes = { config: demo.config.length, double: 10240, doubleOffset: 12 * 2048, ext2Offset: 17 * 2048, ext2: 16 + 32 * 12 + 32 * 8 * 4 + 16 + 128 * 8 + 3 * 32 + 4 * 8 };
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

test("instant press: the short list goes out as the button goes down, the long and double lists after (before 1.17, it waited)", async () => {
  const sim = simWithDemo(await flashWith(packDemo([
    "b = d['Button_Settings']",
    "b.loc[(b.Bank_Number == '1') & (b.Button_Identifier == '4'), 'Instant_Press'] = 'Y'",
    "c = d['Combo_Settings']",
    "d['Combo_Settings'] = c.iloc[0:0]",     // 3+4 would wait for its partner first
  ].join("\n"))));
  tap(sim, 0);                              // the index to LOOP
  const seen = watch(sim);
  const usb = () => seen.splice(0).filter((m) => m.startsWith("USB b0 0"));

  // REC, with a double press that stops, marked in the demo
  sim.footswitch(0, true);
  sim.run(5);
  assert.deepEqual(usb(), ["USB b0 01 7f"], "REC at once, not after the double press window");
  sim.footswitch(0, false);
  sim.run(600);
  assert.deepEqual(usb(), [], "nothing more once the window has gone by");
  sim.footswitch(0, true);
  sim.run(5);
  sim.footswitch(0, false);
  sim.run(80);
  sim.footswitch(0, true);
  sim.run(5);
  assert.deepEqual(usb(), ["USB b0 01 00", "USB b0 03 7f"], "a double tap: the first tap at once, the second the double list");
  sim.footswitch(0, false);
  sim.run(600);
  usb();

  // UNDO, with a long press that clears, marked here
  sim.footswitch(3, true);
  sim.run(5);
  assert.deepEqual(usb(), ["USB b0 04 7f"], "UNDO at once, not on release");
  sim.run(700);
  assert.deepEqual(usb(), ["USB b0 05 7f"], "held, the long list as well");
  sim.footswitch(3, false);
  sim.run(50);
  assert.deepEqual(usb(), ["USB b0 05 00", "USB b0 04 00"], "both let go");
  sim.footswitch(3, true);
  sim.run(100);
  sim.footswitch(3, false);
  sim.run(600);
  assert.deepEqual(usb(), ["USB b0 04 7f", "USB b0 04 00"], "a tap: the short list only");

  // A switch of a combination still waits for its partner first
  const combo = simWithDemo(await flashWith(packDemo(
    "b = d['Button_Settings']\nb.loc[(b.Bank_Number == '1') & (b.Button_Identifier == '4'), 'Instant_Press'] = 'Y'")));
  tap(combo, 0);
  const paired = watch(combo);
  combo.footswitch(3, true);
  combo.run(5);
  assert.deepEqual(paired, [], "UNDO is half of 3+4");
  combo.run(100);
  assert.deepEqual(paired.filter((m) => m.startsWith("USB")), ["USB b0 04 7f"], "no partner: at once after the wait, not on release");
  combo.footswitch(3, false);
  combo.run(600);

  // Without the mark, as before: STOP has neither list, so the demo's own UNDO
  const plain = simWithDemo();
  tap(plain, 0);
  const was = watch(plain);
  plain.footswitch(3, true);
  plain.run(100);
  assert.deepEqual(was.filter((m) => m.startsWith("USB")), [], "unmarked, nothing until it is let go");
  plain.footswitch(3, false);
  plain.run(50);
  assert.deepEqual(was.filter((m) => m.startsWith("USB b0 0")), ["USB b0 04 7f", "USB b0 04 00"]);
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

test("a tap waiting for its double press goes out in its own bank when the bank changes", async () => {
  const flash = await flashWith(packDemo([
    "p = d['DoublePress_Settings']",        // STOP on LOOP gets a double press
    "m = (p.Bank_Number == '1') & (p.Button_Identifier == '3')",
    "p.loc[m, ['A_CommandType', 'A_Channel_(PC/CC/Note/PB)', 'A_Number_(PC/CC/Note)', 'A_OnValue_(CC/PB)']] = ['CC', '1', '30', '127']",
  ].join("\n")));
  for (const again of [false, true]) {
    const sim = simWithDemo(flash);
    const pedal = await Pedal.open(sim.access);
    const quick = (id) => { sim.footswitch(id, true); sim.run(40); sim.footswitch(id, false); sim.run(40); };
    tap(sim, 0);                            // to LOOP
    const seen = watch(sim);
    quick(2);                               // STOP, then Bank Up inside the double press time
    quick(9);
    if (again) quick(2);                    // and switch 3 again: a press in the new bank
    sim.run(600);
    const usb = seen.filter((m) => m.startsWith("USB"));
    assert.deepEqual(usb.slice(0, 2), ["USB b0 03 7f", "USB b0 03 00"], "STOP, from LOOP");
    assert.ok(!usb.some((m) => m.startsWith("USB b0 1e")), "and no double press");
    assert.equal((await pedal.getState()).bankName, again ? "PTCH" : "HOME", "switch 3 on HOME goes to PTCH");
  }
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
  // A SysEx cut short by a status byte is lost; a clock inside one is not
  got.length = 0;
  p.push([0xf0, 1, 0xf8, 2, 0xb0, 7, 64, 0xf0, 3, 0xf7]);
  assert.deepEqual(got, [[0xf8], [0xb0, 7, 64], [0xf0, 3, 0xf7]]);
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

test("USB on to DIN keeps its order: a transport after what came before it, a SysEx whole, a full packet of mapped CCs (before 1.19, not)", () => {
  const sim = simWithDemo();
  const seen = watch(sim);
  const take = () => seen.splice(0);
  const din = () => take().filter((m) => m.startsWith("DIN"));
  // What the pedal's own press sends, on DIN as on USB
  const asDin = (out) => out.filter((m) => m.startsWith("USB")).map((m) => m.replace("USB", "DIN"));
  // A Song Position then a Continue, in one packet: the device must move first
  sim.usbIn([0xf2, 0x00, 0x10, 0xfb]);
  sim.run(20);
  assert.deepEqual(din(), ["DIN f2 00 10", "DIN fb"]);
  sim.usbIn([0xfc]);
  sim.run(20);
  tap(sim, 1);
  take();
  // A foreign SysEx in two packets, a press of the pedal's own between them:
  // USB has the press at once, DIN after the F7
  const dump = [0xf0, 0x41, 0x10, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0xf7];
  const whole = `DIN ${dump.map((b) => b.toString(16).padStart(2, "0")).join(" ")}`;
  const events = toUsbEvents(dump);
  sim.usbEvents(events.slice(0, 8));
  sim.run(20);
  tap(sim, 1);
  const pressed = take();
  assert.ok(asDin(pressed).length, "the press sends something");
  assert.deepEqual(pressed.filter((m) => m.startsWith("DIN")), []);
  sim.usbEvents(events.slice(8));
  sim.run(20);
  assert.deepEqual(din(), [whole, ...asDin(pressed)]);
  // One the host leaves open lets the press go after a second
  sim.usbEvents(events.slice(0, 8));
  sim.run(20);
  tap(sim, 2);
  const late = take();
  assert.deepEqual(late.filter((m) => m.startsWith("DIN")), []);
  sim.run(400);
  assert.deepEqual(din(), asDin(late));
  // Sixteen mod wheel moves in one packet, each mapped to CC 11 and kept:
  // 32 messages, more than the packet brought in
  sim.usbIn(Array.from({ length: 16 }, (_, i) => [0xbd, 1, i]).flat());
  sim.run(200);
  const cc = din();
  assert.equal(cc.length, 32);
  assert.equal(cc[31], "DIN bd 01 0f");
});

test("a note's release through the MIDI map is a Note Off of the note it played (before 1.12, a Note On)", async () => {
  // Note 60 on channel 14 split by velocity onto notes 72 (always 100) and 74,
  // and note 61 as a PC
  const tweak = [
    "import pandas as pd",
    "m = d['MidiMap_Settings']",
    "rows = [['Note', '14', '60', '1', '63', 'Note', '2', '72', '100', '100', '', '', '', 'N'],",
    "        ['Note', '14', '60', '64', '127', 'Note', '2', '74', '', '', '', '', '', 'N'],",
    "        ['Note', '14', '61', '', '', 'PC', '2', '5', '', '', '', '', '', 'N']]",
    "d['MidiMap_Settings'] = pd.concat([m, pd.DataFrame(rows, columns=m.columns)], ignore_index=True)",
  ].join("\n");
  const sim = simWithDemo(await flashWith(packDemo(tweak)));
  const seen = watch(sim);
  const send = (bytes) => { sim.usbIn(bytes); sim.run(20); return seen.splice(0); };
  assert.deepEqual(send([0x9d, 60, 30]), ["DIN 91 48 64"]);
  assert.deepEqual(send([0x8d, 60, 64]), ["DIN 81 48 40", "DIN 81 4a 40"]);
  assert.deepEqual(send([0x9d, 60, 90]), ["DIN 91 4a 5a"]);
  assert.deepEqual(send([0x9d, 60, 0]), ["DIN 81 48 40", "DIN 81 4a 40"]);
  assert.deepEqual(send([0x9d, 61, 90]), ["DIN c1 05"]);
  assert.deepEqual(send([0x8d, 61, 0]), []);
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

// Whether the screen holds this text in the 7x10 font with its top left at x, y
function textAt(sim, x, y, text, inverted = false) {
  for (let i = 0; i < text.length; i++) {
    for (let row = 0; row < 10; row++) {
      for (let c = 0; c < 7; c++) {
        const want = Boolean((font7x10[(text.charCodeAt(i) - 32) * 10 + row] << c) & 0x8000) !== inverted;
        if (lit(sim, x + i * 7 + c, y + row) !== want) return false;
      }
    }
  }
  return true;
}

// The setlist in slot 1's flash, up to its end
const setlistAt = 0x20000 + 24048;
function setlistOf(sim) {
  const list = [];
  for (const b of sim.flashNow().subarray(setlistAt, setlistAt + 32)) {
    if (b >= 32) break;
    list.push(b);
  }
  return list;
}

// Bank Down and Bank Up held together, which opens the editor and closes it
function holdBoth(sim) {
  sim.footswitch(8, true);
  sim.footswitch(9, true);
  sim.run(2200);
  sim.footswitch(8, false);
  sim.footswitch(9, false);
  sim.run(600);
}

test("the editor's setlist screen moves, takes out and puts in songs (before 1.23, it had none)", async () => {
  const sim = simWithDemo();
  sim.run(10000);                           // the power on banner goes by first
  assert.deepEqual(setlistOf(sim), [0, 12, 15, 13, 14, 18, 16, 17, 19, 20]);
  tap(sim, 0);                              // the index to LOOP, bank 2
  holdBoth(sim);
  tap(sim, 7);
  tap(sim, 7);                              // D twice: the commands, the settings, the setlist
  assert.ok(textAt(sim, 0, 0, "EDIT SETLIST"), "the setlist screen");
  assert.ok(textAt(sim, 0, 12, "SONG 1   1  HOME", true), "the cursor on the first song, its bank's number and name");

  tap(sim, 1);                              // to song 2, bank 13 (12 counted from 0)
  tap(sim, 5);                              // B: one place later
  tap(sim, 1);                              // leaving the line writes it
  assert.deepEqual(setlistOf(sim), [0, 15, 12, 13, 14, 18, 16, 17, 19, 20]);

  for (let i = 0; i < 14; i++) tap(sim, 2);   // song 4 from bank 14 down past bank 1, to ---
  for (let i = 0; i < 3; i++) tap(sim, 2);    // where it stays
  tap(sim, 0);                              // back to song 3, the song taken out
  assert.deepEqual(setlistOf(sim), [0, 15, 12, 14, 18, 16, 17, 19, 20]);

  tap(sim, 6);                              // C: the bank the pedal is on, LOOP, in before song 3
  tap(sim, 4);                              // and A one place earlier
  assert.ok(textAt(sim, 0, 22, "SONG 2   2  LOOP", true));
  holdBoth(sim);                            // closing writes it
  assert.deepEqual(setlistOf(sim), [0, 1, 15, 12, 14, 18, 16, 17, 19, 20]);

  const pedal = await Pedal.open(sim.access);
  tap(sim, 9);                              // Bank Up follows the new order
  assert.equal((await running(sim, () => pedal.getState())).bank, 15);
});

test("an empty setlist is started on the pedal from its END line, and a full one takes no more", async () => {
  const sim = simWithDemo(await flashWith(packDemo("d['Setlist'] = d['Setlist'].iloc[0:0]")));
  sim.run(10000);
  assert.deepEqual(setlistOf(sim), []);
  tap(sim, 1);                              // the index to FX, bank 3
  holdBoth(sim);
  tap(sim, 7);
  tap(sim, 7);
  assert.ok(textAt(sim, 0, 12, "END", true), "only the END line");
  tap(sim, 3);                              // 4 on END changes nothing
  tap(sim, 6);                              // C puts FX in
  tap(sim, 3);                              // and 4 makes it bank 4
  tap(sim, 1);
  assert.deepEqual(setlistOf(sim), [3]);
  for (let i = 0; i < 35; i++) tap(sim, 6); // C again and again: 32 songs at most
  holdBoth(sim);
  assert.deepEqual(setlistOf(sim), [3, ...Array(31).fill(2)]);
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

test("a box's switch holds as long as it is down; a press from the page lets go after 10 s (before 1.15, both did)", async () => {
  const sim = simWithDemo(await flashWith(packDemo([
    "e = d['Expression_Settings']",
    "e.loc[e.Pedal == '2', ['Output', 'Min_ADC', 'Max_ADC', 'Invert', 'Box_2']] = ['Switches', '0', '4095', 'N', '1']",
    "b = d['Button_Settings']",
    "b.loc[(b.Bank_Number == '1') & (b.Button_Identifier == '1'), 'Momentary_Hold'] = 'Y'",
  ].join("\n"))));
  tap(sim, 0);                              // the index to LOOP, where switch 1 is CC 1, momentary when held
  const seen = watch(sim);
  const cc1 = () => seen.splice(0).filter((m) => m.startsWith("USB b0 01 "));
  sim.pedal(1, 2048);                       // box switch 2 holds switch 1
  sim.run(16000);
  assert.deepEqual(cc1(), ["USB b0 01 7f"], "held 16 s, still down");
  sim.pedal(1, 0);
  sim.run(600);
  assert.deepEqual(cc1(), ["USB b0 01 00"], "let go with the box");

  const pedal = await Pedal.open(sim.access);
  await running(sim, () => pedal.press("1", true));
  sim.run(16000);
  assert.deepEqual(cc1(), ["USB b0 01 7f", "USB b0 01 00"], "a press from the page left down lets go by itself");
});

function smallTextAt(sim, x, y, text, inverted = false) {
  for (let i = 0; i < text.length; i++) {
    for (let row = 0; row < 8; row++) {
      for (let c = 0; c < 6; c++) {
        const want = Boolean((font6x8[(text.charCodeAt(i) - 32) * 8 + row] << c) & 0x80) !== inverted;
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
  // and the computer can write on them too (1.34), four characters there
  const pedal = await Pedal.open(ten.access);
  await running(ten, () => pedal.ask([82, 9, 0, ...Array.from("Tempo", (c) => c.charCodeAt(0))], 83, 1000));
  ten.run(200);
  assert.ok(smallTextAt(ten, 102, 26, "Temp"), "Bank Up's label from the computer");
  assert.ok(smallTextAt(ten, 102, 48, "PREV"));

  // One label is enough; the other switch shows its name
  const one = await demoWith("MIDI only", "", "NEXT");
  assert.ok(smallTextAt(one, 102, 26, "NEXT"));
  assert.ok(smallTextAt(one, 108, 48, "DN"));

  // Changing bank, or with no label at all, the eight cells as before
  const plain = cellRows(await demoWith("Bank+MIDI", "", ""));
  assert.equal(cellRows(await demoWith("Bank+MIDI", "PREV", "NEXT")), plain, "the switches change bank: no labels for them");
  assert.equal(cellRows(await demoWith("MIDI only", "", "")), plain, "no labels: the screen as it always was");
});

test("a line the display does not take is sent again, and the screen catches up (before 1.14, it froze)", async () => {
  const sim = simWithDemo();
  sim.run(10000);                           // the demo's power on banner goes by first
  const panel = () => sim.memory.slice(sim.e.sim_panel(), sim.e.sim_panel() + 130 * 8);
  const shows = () => Buffer.compare(panel(), sim.screen()) === 0;
  assert.ok(shows(), "the panel shows the screen");

  // The first line of the next update fails before its DMA starts, as on a
  // NACK of the address: the pedal goes to bank 7 and the panel follows
  const home = panel();
  sim.e.sim_i2c_fail(1);
  sim.usbIn([0xb0, 32, 7]);                 // the demo's Bank_Change_CC
  sim.run(500);
  const pedal = await Pedal.open(sim.access);
  assert.equal((await running(sim, () => pedal.getState())).bank, 7);
  assert.ok(shows(), "the panel caught up with the screen");
  assert.notEqual(Buffer.compare(panel(), home), 0);

  // A display that answers nothing for a while: the pedal carries on, and
  // the screen comes back with it
  sim.e.sim_i2c_fail(1000000);
  sim.usbIn([0xb0, 32, 3]);
  sim.run(1000);
  assert.equal((await running(sim, () => pedal.getState())).bank, 3);
  assert.ok(!shows(), "nothing reached the panel");
  sim.e.sim_i2c_fail(0);
  sim.run(500);
  assert.ok(shows(), "the screen is back, bank 3 on it");
});

test("takeover: back on a CC it left at another value, the pedal catches up with it or scales from it (before 1.18, it jumped)", async () => {
  // Pedal 1 on its own CC 11, but on CC 1 in FX; a plain sweep, nothing else
  const withTakeover = async (mode) => simWithDemo(await flashWith(packDemo([
    "e = d['Expression_Settings']",
    "e.loc[e.Pedal == '1', ['Min_ADC', 'Max_ADC', 'Toe_Button', 'Auto_Button', 'Takeover']] = ['0', '4000', '', '', '" + mode + "']",
  ].join("\n"))));
  const cc11 = (seen) => seen.splice(0).filter((m) => m.startsWith("USB b0 0b ")).map((m) => parseInt(m.slice(-2), 16));
  const move = (sim, value) => { sim.pedal(0, value); sim.run(400); };

  // CC 11 left at about 32 in HOME, then FX takes the pedal to CC 1, and the
  // foot towards the toe; Bank Down back to HOME gives it CC 11 again
  async function leave(mode) {
    const sim = await withTakeover(mode);
    const pedal = await Pedal.open(sim.access);
    const seen = watch(sim);
    move(sim, 0);
    move(sim, 2048);
    move(sim, 1024);
    const left = cc11(seen).at(-1);
    assert.ok(Math.abs(left - 32) <= 1, `CC 11 left at ${left}`);
    tap(sim, 1);
    assert.equal((await running(sim, () => pedal.getState())).bankName, "FX");
    move(sim, 3600);
    assert.deepEqual(cc11(seen), [], "in FX the pedal is on CC 1");
    tap(sim, 9);
    assert.equal((await running(sim, () => pedal.getState())).bankName, "HOME");
    assert.deepEqual(cc11(seen), [], "nothing sent on the way back");
    return { sim, seen, left };
  }

  const jump = await leave("Jump");
  move(jump.sim, 3000);
  assert.ok(cc11(jump.seen).at(-1) > 85, "Jump: to where the foot is");

  const catchUp = await leave("CatchUp");
  move(catchUp.sim, 3000);
  move(catchUp.sim, 2000);
  assert.deepEqual(cc11(catchUp.seen), [], "Catch-up: nothing above the value it was left at");
  move(catchUp.sim, 900);
  let sent = cc11(catchUp.seen);
  assert.ok(sent.length > 0 && sent.at(-1) <= catchUp.left, `crossing it, the foot's own: ${sent}`);
  move(catchUp.sim, 2048);
  assert.ok(Math.abs(cc11(catchUp.seen).at(-1) - 64) <= 1, "and follows it from there");

  const scaled = await leave("Scaled");
  move(scaled.sim, 3850);
  sent = cc11(scaled.seen);
  assert.ok(sent.length > 0 && sent.every((v) => v > scaled.left && v < 110), `Scaled: from the value up, not to the foot: ${sent}`);
  move(scaled.sim, 4095);
  assert.equal(cc11(scaled.seen).at(-1), 127, "at the toe with the foot");
  move(scaled.sim, 2048);
  assert.ok(Math.abs(cc11(scaled.seen).at(-1) - 64) <= 1, "the foot's own from there");
});

// Text in the 7x10 font with its top left corner at x, y
function bigTextAt(sim, x, y, text) {
  for (let i = 0; i < text.length; i++) {
    for (let row = 0; row < 10; row++) {
      for (let c = 0; c < 7; c++) {
        const want = Boolean((font7x10[(text.charCodeAt(i) - 32) * 10 + row] << c) & 0x8000);
        if (lit(sim, x + i * 7 + c, y + row) !== want) return false;
      }
    }
  }
  return true;
}

test("live values: $N shows the preset you are on by its name, $V a button's value, as they change (before 1.20, the text as it was)", async () => {
  const sim = simWithDemo();
  sim.run(10000);                           // the demo's power on banner goes by first
  tap(sim, 2);                              // PTCH, whose enter list sends PC 0
  assert.ok(infoLineIs(sim, "CLEAN"), "the info line's $N: program 0 on MIDI_Channel");
  tap(sim, 7);                              // NEXT
  assert.ok(infoLineIs(sim, "CRUNCH"), "for a moment, the program it sent by its name (before 1.20, PC 1)");
  sim.run(1600);
  assert.ok(infoLineIs(sim, "CRUNCH"), "and then the bank's info line, the same");
  for (let i = 0; i < 4; i++) tap(sim, 7);
  assert.ok(infoLineIs(sim, "PC 5"), "with no name, its number");
  sim.run(1600);
  assert.ok(infoLineIs(sim, "5"));
  sim.usbIn([0xc0, 12]);                    // the computer selects one
  sim.run(200);
  assert.ok(infoLineIs(sim, "SOLO"), "whoever selects it");

  const tweak = [
    "b = d['Button_Settings']",
    "b.loc[(b.Bank_Number == '7') & (b.Button_Identifier == '1'), 'Label'] = 'V$V'",
    "b.loc[(b.Bank_Number == '7') & (b.Button_Identifier == '2'), 'Label'] = 'VL$V'",
    "b.loc[(b.Bank_Number == '7') & (b.Button_Identifier == 'A'), 'Label'] = 'W:$V'",
  ].join("\n");
  const knob = simWithDemo(await flashWith(packDemo(tweak)));
  knob.run(10000);
  tap(knob, 6);                             // KNOB: VOL+ and VOL- start from 64
  assert.ok(bigTextAt(knob, 5, 25, "V64"), "the value a CCInc starts from");
  assert.ok(bigTextAt(knob, 34, 25, "VL64"));
  tap(knob, 0);
  assert.ok(bigTextAt(knob, 5, 25, "V66"), "pressed, the value it sent");
  tap(knob, 1);
  assert.ok(bigTextAt(knob, 34, 25, "VL62"), "each CCInc its own value");
  for (let i = 0; i < 7; i++) tap(knob, 4);  // WRP+, by 16, a toggle drawn the other way round
  assert.ok(smallTextAt(knob, 2, 48, "W:112", true), "one character more than a label fits, in the small letters");
});

// Two switches pressed together, as a foot does: the second a little after
function pair(sim, a, b) {
  sim.footswitch(a, true);
  sim.run(20);
  sim.footswitch(b, true);
  sim.run(100);
  sim.footswitch(a, false);
  sim.footswitch(b, false);
  sim.run(600);
}

test("B+C locks the demo's switches, LOCKED in the info line, and unlocks them (before 1.21, nothing did)", async () => {
  const sim = simWithDemo();
  sim.run(10000);                           // the power on banner goes by first
  tap(sim, 0);                              // the index to LOOP
  const pedal = await Pedal.open(sim.access);
  const seen = watch(sim);
  pair(sim, 5, 6);
  sim.run(3000);                            // past the LOCKED readout
  assert.ok(infoLineIs(sim, "LOCKED"), "the info line says so");
  assert.deepEqual(seen.splice(0), [], "the lock itself sends nothing");

  tap(sim, 0);                              // REC
  tap(sim, 5);                              // B alone
  tap(sim, 9);                              // Bank Up
  sim.footswitch(3, true);                  // half of 3+4, held long
  sim.run(1500);
  sim.footswitch(3, false);
  sim.run(600);
  assert.deepEqual(seen.splice(0), [], "nothing goes out");
  assert.equal((await running(sim, () => pedal.getState())).bankName, "LOOP", "nor does the bank change");

  pair(sim, 6, 5);                          // the other way round
  sim.run(3000);
  assert.ok(infoLineIs(sim, "looper"), "the bank's own info again");
  tap(sim, 0);
  assert.deepEqual(seen.splice(0), ["USB b0 01 7f", "DIN b0 01 7f"], "REC answers again");
});

test("asleep, a bank change from the computer leaves the LEDs dark until a press wakes the pedal (before 1.22, it lit them)", async () => {
  const sim = simWithDemo(await flashWith(packDemo("d['Global_Settings'].loc[d['Global_Settings']['Label'] == 'Sleep_After_Min', 'Value'] = '1'")));
  sim.run(61000);
  assert.ok(!sim.e.sim_screen_on(), "asleep after a minute");
  assert.deepEqual(sim.leds(), Array(10).fill(0), "with the LEDs out");
  sim.usbIn([0xb0, 32, 2]);                 // the demo's Bank_Change_CC: to bank 3
  sim.run(100);
  assert.ok(!sim.e.sim_screen_on(), "the screen stays off");
  assert.deepEqual(sim.leds(), Array(10).fill(0), "and so do the LEDs");
  tap(sim, 9);
  assert.ok(sim.e.sim_screen_on(), "a press wakes it");
});

test("a SysEx left unfinished is dropped at the next F0, not run with the next message (before 1.22, a press)", async () => {
  const sim = simWithDemo();
  sim.run(10000);
  const pedal = await Pedal.open(sim.access);
  const before = (await running(sim, () => pedal.getState())).bankName;
  const seen = watch(sim);
  sim.usbEvents([0x04, 0xf0, 0x7d, 0x42, 0x04, 0x03, 0x01, 0x00]);  // PRESS_BUTTON 4 down, no F7
  const state = await running(sim, () => pedal.getState());
  sim.run(1000);
  assert.equal(state.bankName, before, "GET_STATE answers, and no switch was pressed");
  assert.deepEqual(seen, [], "nothing goes out");
});

test("RESET from the tools keeps a bank chosen just before it (before 1.22, the restart lost it)", async () => {
  const sim = simWithDemo();
  sim.run(10000);
  sim.footswitch(0, true);                  // the index to LOOP, and at once
  sim.run(100);
  sim.footswitch(0, false);
  sim.run(100);
  const pedal = await Pedal.open(sim.access);
  pedal.reset();
  await null;
  sim.run(1);
  const again = await Pedal.open(sim.access);
  assert.equal((await running(sim, () => again.getState())).bankName, "LOOP");
});

test("a power cut in the middle of erasing the saved state does not bring an old bank back later (before 1.22, it did)", async () => {
  const STATE = 0x26000, ENTRY = 100, ENTRIES = 81;
  const sim = simWithDemo();
  sim.run(10000);
  tap(sim, 0);                              // the index to LOOP
  sim.run(3000);
  const flash = sim.flashNow();
  assert.equal(flash[STATE + 98], 0xa9, "saved in the first entry");
  // Cut after the first of the four pages was erased: the old entries are still in the others
  const cut = flash.slice();
  cut.fill(0xff, STATE, STATE + 4 * 2048);
  for (let i = 21; i < ENTRIES; i++) cut.set(flash.slice(STATE, STATE + ENTRY), STATE + i * ENTRY);
  const boot = (f) => {
    const s = new Simulator(module, { persist: false });
    s.flash = f;
    s.start();
    clearInterval(s.timer);
    clearInterval(s.saveTimer);
    s.run(1300);
    return s;
  };
  const again = boot(cut);
  again.run(10000);
  for (let i = 0; i < 24; i++) {            // more saves than the first page holds
    tap(again, i % 2 ? 8 : 9);
    again.run(2500);
  }
  const want = (await running(again, async () => (await Pedal.open(again.access)).getState())).bankName;
  assert.notEqual(want, "LOOP");
  const third = boot(again.flashNow());
  assert.equal((await running(third, async () => (await Pedal.open(third.access)).getState())).bankName, want);
});

test("a tap let go while the main loop is held up by a flash erase is still a press (before 1.22, it was lost)", async () => {
  const sim = simWithDemo();
  sim.run(10000);
  const pedal = await Pedal.open(sim.access);
  sim.footswitch(0, true);
  sim.e.sim_systick();                      // the scan sees the press, then the loop stalls
  sim.footswitch(0, false);                 // the foot is off before the loop is back
  sim.e.sim_systick();
  sim.run(700);
  assert.equal((await running(sim, () => pedal.getState())).bankName, "LOOP", "the index went to LOOP");
});

test("the first tap after power on starts the measurement, not timed from the boot (before 1.22, 30-50 BPM)", async () => {
  const sim = new Simulator(module, { persist: false });
  sim.flash = Uint8Array.from(demoFlash);
  sim.start();
  clearInterval(sim.timer);
  clearInterval(sim.saveTimer);
  while (!sim.e.sim_ready()) sim.run(1);
  sim.usbIn([0xb0, 32, 6]);                 // to the tempo bank at once
  sim.run(10);
  assert.ok(sim.e.sim_tick() < 1950, "under 2 s after power on");
  for (let i = 0; i < 2; i++) {             // TAP twice, 500 ms apart
    sim.footswitch(0, true);
    sim.run(100);
    sim.footswitch(0, false);
    sim.run(400);
  }
  assert.ok(infoLineIs(sim, "120 BPM"), "two taps half a second apart are 120 BPM");
});

// The host's clock at 120 BPM, a clock byte every 21 ms, with what the foot
// does at given clocks: {clock: [switch, down]}
function hostClock(sim, clocks, at = {}) {
  for (let n = 0; n < clocks; n++) {
    for (const [id, down] of at[n] ?? []) sim.footswitch(id, down);
    sim.usbIn([0xf8]);
    sim.run(21);
  }
}

test("a recorded run of presses plays back on its beats whenever the clock runs in that bank, after a restart too (before 1.24, nothing did)", async () => {
  const sim = simWithDemo();
  sim.run(10000);
  sim.usbIn([0xb0, 32, 13]);                // song 2: REC, PLAY, STOP... and TAP, REC when held
  sim.run(50);
  sim.footswitch(7, true);                  // hold TAP: armed, waiting for the clock
  sim.run(700);
  sim.footswitch(7, false);
  sim.run(50);
  assert.ok(infoLineIs(sim, "REC WAIT"));
  sim.usbIn([0xfa]);                        // Start
  // REC a clock before beat 2, a tap; STOP a clock after beat 4, held 20
  // clocks, short of a long press
  hostClock(sim, 160, { 47: [[0, true]], 50: [[0, false]], 97: [[2, true]], 117: [[2, false]] });
  sim.usbIn([0xfc]);                        // Stop: kept
  sim.run(30);
  assert.ok(infoLineIs(sim, "SAVED 2"));

  const replay = (s) => {
    const seen = watch(s);
    let clock = 0;
    s.onOutput = (port, msg) => seen.push(`${port} ${msg.map((b) => b.toString(16).padStart(2, "0")).join(" ")} @${clock}`);
    s.usbIn([0xfa]);
    for (; clock < 160; clock++) { s.usbIn([0xf8]); s.run(21); }
    s.usbIn([0xfc]);
    s.run(30);
    return seen.filter((m) => m.startsWith("USB b0 0")).map((m) => m.slice(4));
  };
  // No foot now: REC on beat 2 (its first clock is clock 48), STOP on beat 4,
  // held as long as it was; STOP is half of a combination, so it goes out
  // after the combination's wait, as under a foot. REC was left on, so its
  // press puts it off.
  assert.deepEqual(replay(sim), ["b0 01 00 @48", "b0 03 7f @99", "b0 03 00 @116"]);

  const again = simWithDemo(sim.flashNow()); // kept in flash
  again.run(10000);
  again.usbIn([0xb0, 32, 13]);
  again.run(50);
  const back = replay(again);               // REC's toggle as the pedal kept it
  assert.match(back[0], /^b0 01 (00|7f) @48$/);
  assert.deepEqual(back.slice(1), ["b0 03 7f @99", "b0 03 00 @116"]);

  again.usbIn([0xb0, 32, 14]);              // song 3 has nothing recorded
  again.run(50);
  assert.deepEqual(replay(again), []);
});

test("a long press plays back long and a double press double, at any tempo; Playback stops it and Erase drops it", async () => {
  const row = (section, btn) => `${section}.loc[(${section}.Bank_Number.astype(str) == '13') & (${section}.Button_Identifier.astype(str) == '${btn}')`;
  const cc = (section, number) => `${row(section, "2")}, ['A_CommandType', 'A_Channel_(PC/CC/Note/PB)', 'A_Number_(PC/CC/Note)', 'A_OnValue_(CC/PB)', 'A_OffValue_(CC)', 'A_Toggle_(CC/PB/Note)']] = ['CC', '1', '${number}', '127', '0', 'N']`;
  const tapMode = (btn, mode) => `${row("b", btn)}, ['A_CommandType', 'A_KeyMode_(Key)']] = ['Tap', '${mode}']`;
  const sim = simWithDemo(await flashWith(packDemo([
    "l = d['LongPress_Settings']", "dp = d['DoublePress_Settings']", "b = d['Button_Settings']",
    cc("l", 9), cc("dp", 8),                // PLAY: held CC 9, twice CC 8
    tapMode("4", "Playback"), tapMode("B", "Erase"),
  ].join("\n"))));
  sim.run(10000);
  sim.usbIn([0xb0, 32, 13]);
  sim.run(50);
  sim.footswitch(7, true);                  // hold TAP: Record
  sim.run(700);
  sim.footswitch(7, false);
  sim.usbIn([0xfa]);
  // PLAY held 40 clocks from beat 1, then twice quickly on beat 4
  hostClock(sim, 130, { 23: [[1, true]], 63: [[1, false]], 95: [[1, true]], 97: [[1, false]], 99: [[1, true]], 101: [[1, false]] });
  sim.usbIn([0xfc]);
  sim.run(30);
  assert.ok(infoLineIs(sim, "SAVED 2"));

  // Played back at 300 BPM, 8 ms a clock: 40 clocks would be too short for a
  // long press, but it is held past the threshold all the same
  const replay = () => {
    const seen = watch(sim);
    sim.usbIn([0xfa]);
    for (let n = 0; n < 160; n++) { sim.usbIn([0xf8]); sim.run(8); }
    sim.usbIn([0xfc]);
    sim.run(600);
    return seen.filter((m) => m.startsWith("USB b0 0")).map((m) => m.slice(4));
  };
  assert.deepEqual(replay(), ["b0 09 7f", "b0 09 00", "b0 08 7f", "b0 08 00"]);

  tap(sim, 3);                              // Playback off
  assert.ok(infoLineIs(sim, "PLAY OFF"));
  assert.deepEqual(replay(), []);
  tap(sim, 3);
  assert.ok(infoLineIs(sim, "PLAY ON"));
  assert.equal(replay().length, 4);
  tap(sim, 5);                              // Erase
  assert.ok(infoLineIs(sim, "ERASED"));
  assert.deepEqual(replay(), []);
});

test("with the recordings' page full, the next one rewrites it with the latest of each bank (before 1.24, there were none)", async () => {
  const sim = simWithDemo();
  sim.run(10000);
  const clock = (clocks, at = {}) => {
    for (let n = 0; n < clocks; n++) {
      for (const [id, down] of at[n] ?? []) sim.footswitch(id, down);
      sim.usbIn([0xf8]);
      sim.run(8);                           // 300 BPM
    }
  };
  // UNDO pressed on each of the first `beats` beats
  const record = (bank, beats) => {
    sim.usbIn([0xb0, 32, bank]);
    sim.run(50);
    sim.footswitch(7, true);
    sim.run(700);
    sim.footswitch(7, false);
    sim.usbIn([0xfa]);
    const at = {};
    for (let b = 1; b <= beats; b++) { at[b * 24 - 1] = [[3, true]]; at[b * 24 + 2] = [[3, false]]; }
    clock(beats * 24 + 30, at);
    sim.usbIn([0xfc]);
    sim.run(30);
    assert.ok(infoLineIs(sim, `SAVED ${beats}`), `bank ${bank}`);
  };
  const played = (bank) => {
    sim.usbIn([0xb0, 32, bank]);
    sim.run(50);
    const seen = watch(sim);
    sim.usbIn([0xfa]);
    clock(70 * 24);
    sim.usbIn([0xfc]);
    sim.run(30);
    return seen.filter((m) => m === "USB b0 04 7f").length;
  };
  for (const bank of [13, 14, 15, 16, 17]) record(bank, 60);   // 364 bytes each
  record(13, 30);                           // no room left: the page is rewritten
  assert.equal(played(13), 30, "the new one");
  for (const bank of [14, 15, 16, 17]) assert.equal(played(bank), 60, `bank ${bank} kept`);
});

test("Tap Out sends a device's tap CC on four beats after entering the bank and after each change of tempo, until the bank changes (before 1.25, nothing did)", async () => {
  const sim = simWithDemo();
  sim.run(10000);
  const run = (ms) => { for (let t = 0; t < ms; t += 5) sim.run(5); };
  const seen = [];
  sim.onOutput = (port, msg) => {
    if (port === "USB" && msg[0] === 0xb2 && msg[1] === 64) seen.push(sim.e.sim_tick());
  };
  sim.usbIn([0xb0, 32, 6]);                 // the tempo bank, at 120 BPM
  run(3000);
  assert.equal(seen.length, 4, "four taps on entering");
  const gaps = seen.slice(1).map((t, i) => t - seen[i]);
  assert.ok(gaps.every((g) => Math.abs(g - 500) <= 2), `a beat apart: ${gaps}`);

  seen.length = 0;
  sim.footswitch(6, true);                  // BPM+: 121, four taps more
  run(100);
  sim.footswitch(6, false);
  run(3000);
  assert.equal(seen.length, 4, "four taps after the new tempo");
  assert.ok(Math.abs(seen[3] - seen[2] - 496) <= 2, "at 121 BPM");

  seen.length = 0;
  for (let i = 0; i < 3; i++) {             // TAP three times, 600 ms apart: 100 BPM
    sim.footswitch(0, true);
    run(50);
    sim.footswitch(0, false);
    run(550);
  }
  run(3000);
  // the second and third taps set the tempo, so they go out as they are
  // tapped, and the third starts a run of four
  assert.equal(seen.length, 5, `the taps relayed and three more: ${seen.length}`);
  assert.ok(seen.slice(1).every((t, i) => Math.abs(t - seen[i] - 600) <= 2), "at 100 BPM");

  seen.length = 0;
  for (let i = 0; i < 3; i++) {             // the same tempo tapped again still taps the device
    sim.footswitch(0, true);
    run(50);
    sim.footswitch(0, false);
    run(550);
  }
  run(3000);
  assert.equal(seen.length, 5);
  assert.ok(seen.slice(1).every((t, i) => t - seen[i] > 300), "never two taps a moment apart");

  seen.length = 0;
  sim.usbIn([0xb0, 32, 7]);                 // another bank: no more taps
  sim.footswitch(6, true);
  run(100);
  sim.footswitch(6, false);
  run(3000);
  assert.deepEqual(seen, []);
});

test("Tap Save keeps the tapped tempo in the bank's enter list, set again on entering it and after a restart (before 1.26, it was lost)", async () => {
  const sim = simWithDemo();
  sim.run(10000);
  const run = (s, ms) => { for (let t = 0; t < ms; t += 5) s.run(5); };
  // Bank 6 taps CC 64 on channel 3 on four beats as it is entered: how far
  // apart they are is the tempo it starts at
  const tapsOnEntering = (s) => {
    const seen = [];
    s.onOutput = (port, msg) => {
      if (port === "USB" && msg[0] === 0xb2 && msg[1] === 64) seen.push(s.e.sim_tick());
    };
    s.usbIn([0xb0, 32, 7]);
    run(s, 200);
    s.usbIn([0xb0, 32, 6]);
    run(s, 3000);
    s.onOutput = null;
    return seen.slice(1).map((t, i) => t - seen[i]);
  };
  assert.ok(tapsOnEntering(sim).every((g) => Math.abs(g - 500) <= 2), "120 BPM before anything is saved");

  for (let i = 0; i < 3; i++) {             // TAP three times, 600 ms apart: 100 BPM
    sim.footswitch(0, true);
    run(sim, 50);
    sim.footswitch(0, false);
    run(sim, 550);
  }
  run(sim, 3000);
  sim.footswitch(0, true);                  // held: Save
  run(sim, 1200);
  sim.footswitch(0, false);
  run(sim, 600);
  sim.footswitch(6, true);                  // BPM+: 101, which is not kept
  run(sim, 100);
  sim.footswitch(6, false);
  run(sim, 600);

  const gaps = tapsOnEntering(sim);
  assert.equal(gaps.length, 3);
  assert.ok(gaps.every((g) => Math.abs(g - 600) <= 2), `back at 100 BPM on entering: ${gaps}`);

  // In flash: a pedal started from it is at 120 until bank 6 sets the 100 kept
  const again = new Simulator(module, { persist: false });
  again.flash = sim.flashNow();
  again.start();
  clearInterval(again.timer);
  clearInterval(again.saveTimer);
  again.run(10000);
  const after = tapsOnEntering(again);
  assert.ok(after.length === 3 && after.every((g) => Math.abs(g - 600) <= 2), `100 BPM after a restart: ${after}`);
});

test("Skip_Same_PC drops a PC the channel is already on, bank included, and Force sends it all the same (before 1.27, every one went out)", async () => {
  const sim = simWithDemo();
  sim.run(10000);
  const run = (ms) => { for (let t = 0; t < ms; t += 5) sim.run(5); };
  // What goes out on USB channel 1 meanwhile: PCs, and the Bank Select LSB
  const sent = (work) => {
    const seen = [];
    sim.onOutput = (port, msg) => {
      if (port === "USB" && (msg[0] === 0xc0 || (msg[0] === 0xb0 && msg[1] === 32))) seen.push(msg.slice(0, msg[0] === 0xc0 ? 2 : 3).join(" "));
    };
    work();
    sim.onOutput = null;
    return seen;
  };
  const enter = (bank) => { sim.usbIn([0xb0, 32, bank]); run(300); };
  const press = (sw) => { sim.footswitch(sw, true); run(60); sim.footswitch(sw, false); run(200); };

  assert.deepEqual(sent(() => enter(3)), ["192 0"], "bank 3 selects program 0 as it is entered");
  assert.deepEqual(sent(() => { enter(4); enter(3); }), [], "and not again: the channel is still on it");
  assert.deepEqual(sent(() => press(1)), ["192 1"], "P 1");
  assert.deepEqual(sent(() => press(1)), [], "P 1 again");
  assert.deepEqual(sent(() => { press(0); press(0); }), ["192 0", "192 0"], "P 0 has Force");
  assert.deepEqual(sent(() => { press(4); press(4); }), ["176 32 3", "192 3"], "BS 3, with its Bank Select");
  sim.usbIn([0xc0, 1]);                      // the host moved the device to program 1
  run(100);
  assert.deepEqual(sent(() => { press(1); press(4); }), ["176 32 3", "192 3"], "P 1 is where the host left it, BS 3 is not");
});

test("reload when lit: the lit button of a group sends its list again and stays on, its PC past Skip_Same_PC (before 1.28, it switched off)", async () => {
  // TRK1 also selects program 5, as a preset button would
  const withPc = [
    "b = d['Button_Settings']",
    "i = (b.Bank_Number == '1') & (b.Button_Identifier == 'A')",
    "b.loc[i, 'B_CommandType'] = 'PC'",
    "b.loc[i, 'B_Channel_(PC/CC/Note/PB)'] = '1'",
    "b.loc[i, 'B_Number_(PC/CC/Note)'] = '5'",
  ];
  const run = (sim, ms) => { for (let t = 0; t < ms; t += 5) sim.run(5); };
  // The PCs and the track CCs 6 and 7 out on USB meanwhile
  const sent = (sim, work) => {
    const seen = [];
    sim.onOutput = (port, msg) => {
      if (port === "USB" && (msg[0] === 0xc0 || (msg[0] === 0xb0 && (msg[1] === 6 || msg[1] === 7)))) {
        seen.push(msg.slice(0, msg[0] === 0xc0 ? 2 : 3).join(" "));
      }
    };
    work();
    sim.onOutput = null;
    return seen;
  };
  const press = (sim, sw) => { sim.footswitch(sw, true); run(sim, 60); sim.footswitch(sw, false); run(sim, 200); };
  const start = async (tweak) => {
    const sim = simWithDemo(await flashWith(packDemo(tweak.join("\n"))));
    sim.run(10000);
    sim.usbIn([0xb0, 32, 1]);                  // to LOOP
    run(sim, 300);
    return sim;
  };

  const sim = await start(withPc);
  assert.deepEqual(sent(sim, () => press(sim, 4)), ["176 6 127", "192 5"], "TRK1 on");
  assert.deepEqual(sent(sim, () => press(sim, 4)), ["176 6 127", "192 5"], "pressed lit: again, PC 5 included");
  assert.equal(sim.leds()[4] > 0, true, "and still lit");
  assert.deepEqual(sent(sim, () => press(sim, 5)), ["176 6 0", "176 7 127"], "TRK2 switches it off as before");
  assert.equal(sim.leds()[4], 0, "TRK1 dark");
  assert.deepEqual(sent(sim, () => press(sim, 5)), ["176 7 127"], "TRK2 again");

  // Unmarked, as before: the lit button switches off, and PC 5 stays dropped
  const plain = await start([...withPc, "b['Reload_When_Lit'] = ''"]);
  assert.deepEqual(sent(plain, () => press(plain, 4)), ["176 6 127", "192 5"]);
  const off = sent(plain, () => press(plain, 4));
  assert.deepEqual(off.filter((m) => m.startsWith("176")), ["176 6 0"], "switched off");
  assert.deepEqual(off.filter((m) => m.startsWith("192")), [], "the channel is on program 5 already");
});

test("an expression pedal shows its value on the display while it moves, as a bar or a number (before 1.29, nothing)", async () => {
  const withDisplay = async (one, two) => simWithDemo(await flashWith(packDemo([
    "e = d['Expression_Settings']",
    "cols = ['Min_ADC', 'Max_ADC', 'Curve', 'Invert', 'Output', 'Toe_Button', 'Heel_Button', 'Auto_Button', 'Display']",
    "e.loc[e.Pedal == '1', cols] = ['0', '4000', 'Linear', 'N', 'CC', '', '', '', '" + one + "']",
    "e.loc[e.Pedal == '2', cols] = ['0', '4000', 'Linear', 'N', 'CC', '', '', '', '" + two + "']",
  ].join("\n"))));
  const move = (sim, i, value) => { sim.pedal(i, value); sim.run(300); };

  const sim = await withDisplay("Bar", "Number");
  sim.run(10000);                           // the demo's power on banner goes by first
  move(sim, 0, 0);
  move(sim, 1, 0);
  sim.run(2000);
  assert.ok(infoLineIs(sim, "1/10>S01"), "at rest, the bank's own info");

  move(sim, 0, 2048);                       // about half way: 65 of 127
  assert.ok(textAt(sim, 50, 6, "1"), "pedal 1's number");
  assert.ok(lit(sim, 60, 11) && lit(sim, 127, 11), "the bar's frame, to the edge");
  assert.ok(lit(sim, 80, 11) && !lit(sim, 110, 11), "filled half way");
  sim.run(2000);
  assert.ok(infoLineIs(sim, "1/10>S01"), "gone after a moment");

  move(sim, 1, 4095);
  assert.ok(infoLineIs(sim, "EXP2 127"), "pedal 2 as a number");
  move(sim, 1, 1000);
  assert.ok(infoLineIs(sim, "EXP2 32"), "following the foot");

  const off = await withDisplay("Off", "Off");
  off.run(10000);
  move(off, 0, 0);
  move(off, 0, 2048);
  assert.ok(infoLineIs(off, "1/10>S01"), "Off: the info line as before");
});

test("a value inside a stored SysEx, with its Roland checksum, from a press, a toggle, a CCInc and a pedal (1.30)", async () => {
  // On DIN: the simulator keeps USB SysEx for the pedal's own answers
  // The demo's string 3, a Boss style write: 41 00 00 00 00 33 12, address 60 00 06 39, VV, CS
  const katana = (value) => {
    const body = [0x60, 0x00, 0x06, 0x39, value];
    const sum = body.reduce((a, b) => a + b, 0);
    return ["f0", "41", "00", "00", "00", "00", "33", "12", ...[...body, (128 - (sum % 128)) % 128].map((b) => b.toString(16).padStart(2, "0")), "f7"].join(" ");
  };
  const sim = simWithDemo(await flashWith(packDemo([
    "e = d['Expression_Settings']",
    "e.loc[e.Pedal == '1', ['Min_ADC', 'Max_ADC', 'Output', 'Toe_Button', 'Heel_Button', 'Auto_Button']] = ['0', '4000', 'SysEx 3', '', '', '']",
  ].join("\n"))));
  sim.run(10000);
  sim.usbIn([0xb0, 32, 8]);                 // the SYX bank
  sim.run(300);
  const hold = (sw) => {
    const seen = watch(sim);
    sim.footswitch(sw, true);
    sim.run(1200);
    sim.footswitch(sw, false);
    sim.run(300);
    sim.onOutput = null;
    return seen.filter((m) => m.startsWith("DIN ")).map((m) => m.slice(4));
  };
  assert.deepEqual(hold(0), [katana(64)], "SX64: its own value");
  assert.equal(katana(64), "f0 41 00 00 00 00 33 12 60 00 06 39 40 21 f7");
  assert.deepEqual(hold(1), [katana(127)], "SX/T on: the CC's On value, and no CC");
  assert.deepEqual(hold(1), [katana(0)], "SX/T off: its Off value");
  assert.deepEqual(hold(2), [katana(16)], "SX+: a step up");
  assert.deepEqual(hold(2), [katana(32)], "and another");

  const seen = watch(sim);
  sim.pedal(0, 0);
  sim.run(300);
  sim.pedal(0, 4095);
  sim.run(300);
  sim.onOutput = null;
  const sent = seen.filter((m) => m.startsWith("DIN ")).map((m) => m.slice(4));
  assert.ok(sent.length > 0 && sent.every((m) => m.startsWith("f0 41 ")), sent.join(", "));
  assert.equal(sent.at(-1), katana(127), "pedal 1 at the toe");
});

test("an expression pedal cut into zones taps a switch as the foot enters each, and again on entering a bank (before 1.31, only toe and heel)", async () => {
  // HOME's switches 1-4 send CC 20-23; pedal 1 in four zones, the third tapping nothing
  const zoned = async (sendOnBank) => simWithDemo(await flashWith(packDemo([
    "b = d['Button_Settings']",
    "for k, sw in enumerate('1234'):",
    "    r = (b.Bank_Number.astype(str) == '0') & (b.Button_Identifier.astype(str) == sw)",
    "    b.loc[r, ['A_CommandType', 'A_Channel_(PC/CC/Note/PB)', 'A_Number_(PC/CC/Note)', 'A_OnValue_(CC/PB)']] = ['CC', '1', str(20 + k), '127']",
    "e = d['Expression_Settings']",
    "e.loc[e.Pedal == '1', ['Min_ADC', 'Max_ADC', 'Output', 'Zones', 'Send_On_Bank']] = ['0', '4095', 'Zones', '1 2 None 4', '" + sendOnBank + "']",
  ].join("\n"))));
  const sim = await zoned("N");
  const seen = watch(sim);
  const sent = () => seen.splice(0).filter((m) => m.startsWith("USB ")).map((m) => m.slice(4));
  const move = (value, ms = 300) => { sim.pedal(0, value); sim.run(ms); };

  move(0);
  assert.deepEqual(sent(), [], "where the pedal is at first taps nothing");
  move(1500);
  assert.deepEqual(sent(), ["b0 15 7f"], "into zone 2: switch 2");
  move(1600);
  assert.deepEqual(sent(), [], "moving inside it: nothing more");
  move(2090);
  assert.deepEqual(sent(), [], "just over the edge of zone 3 is not in it yet");
  move(1990);
  assert.deepEqual(sent(), [], "nor back");
  move(2600);
  assert.deepEqual(sent(), [], "zone 3 taps nothing");
  move(4095);
  assert.deepEqual(sent(), ["b0 17 7f"], "zone 4: switch 4");
  move(1500, 20);                           // a quick sweep down through zone 2
  move(0);
  assert.deepEqual(sent(), ["b0 14 7f"], "only the zone it stops in");
  assert.deepEqual(seen.filter((m) => / b0 0b /.test(m)), [], "and no CC of a pedal");

  const again = await zoned("Y");
  const pedal = await Pedal.open(again.access);
  const seen2 = watch(again);
  again.pedal(0, 4095);
  again.run(300);
  again.usbIn([0xb0, 32, 2]);               // to FX, whose switch 4 sends CC 13
  again.run(600);
  assert.equal((await running(again, () => pedal.getState())).bankName, "FX");
  again.usbIn([0xb0, 32, 0]);               // and back
  again.run(600);
  assert.equal((await running(again, () => pedal.getState())).bankName, "HOME");
  assert.deepEqual(seen2.filter((m) => /^USB b0 (0d|17)/.test(m)).map((m) => m.slice(4)),
    ["b0 17 7f", "b0 0d 7f", "b0 0d 00", "b0 17 7f"], "with Send on entering a bank, each bank entered taps the zone the pedal is in");
});

// The 11x18 font of the firmware, as font7x10: 18 rows a character from ' ' on
const font11x18 = (() => {
  const src = fs.readFileSync(path.join(root, "firmware/Middlewares/stm32-ssd1306-master/ssd1306/fonts/11x18.txt"), "utf8");
  return src.split("\n").filter((line) => /^[#.]{11}$/.test(line))
    .map((line) => parseInt(line.replace(/#/g, "1").replace(/\./g, "0").padEnd(16, "0"), 2));
})();

// Whether the band of rows y..y+18*scale holds just this text in the large
// font, each pixel a square of scale, in the middle of the screen; the font
// has capitals only, and draws a small letter as its capital
function gigLineIs(sim, y, text, scale = 1) {
  text = text.toUpperCase();
  const w = 11 * scale, x0 = Math.floor((128 - text.length * w) / 2);
  for (let x = 0; x < 128; x++) {
    for (let row = 0; row < 18 * scale; row++) {
      const i = Math.floor((x - x0) / w), ch = text.charCodeAt(i);
      const want = x >= x0 && i < text.length
        && Boolean((font11x18[(ch - 32) * 18 + Math.floor(row / scale)] << Math.floor(((x - x0) % w) / scale)) & 0x8000);
      if (lit(sim, x, y + row) !== want) return false;
    }
  }
  return true;
}

const gigView = (sim, name, info) => gigLineIs(sim, 2, name, 2) && gigLineIs(sim, 44, info);

test("3+C turns the demo's gig view on: the song's name and info line large, the labels back for a moment on a press (before 1.32, no gig view)", async () => {
  const sim = simWithDemo();
  sim.run(10000);                           // the power on banner goes by first
  const seen = watch(sim);
  pair(sim, 2, 6);
  assert.ok(gigView(sim, "HOME", "1/10>S01"), "the bank's name twice the large font, its info line under it");
  assert.deepEqual(seen.splice(0), [], "the gig view itself sends nothing");

  tap(sim, 0);                              // LOOP: entering a bank keeps the gig view
  assert.ok(gigView(sim, "LOOP", "looper"), "the new bank's name at once");
  tap(sim, 1);                              // PLAY
  assert.deepEqual(seen.splice(0), ["USB b0 02 7f", "DIN b0 02 7f"], "the press does what it does");
  assert.ok(infoLineIs(sim, "looper"), "and the labels come back");
  sim.run(2000);
  assert.ok(infoLineIs(sim, "looper"), "for a moment");
  sim.run(1000);
  assert.ok(gigView(sim, "LOOP", "looper"), "then the gig view again");

  pair(sim, 2, 6);
  assert.ok(infoLineIs(sim, "looper"), "3+C again: the labels for good");
  sim.run(4000);
  assert.ok(infoLineIs(sim, "looper"));

  const host = simWithDemo();
  host.run(10000);
  pair(host, 2, 6);
  host.usbIn([0xf0, 0x7d, 0x48, 2, 1, ..."HEROES".split("").map((c) => c.charCodeAt(0)), 0xf7]);
  host.run(200);
  assert.ok(gigLineIs(host, 11, "HEROES") && gigLineIs(host, 44, "1/10>S01"),
    "the computer's song name, in the large font when twice its size does not fit");
});

test("Gig_View has the gig view on from power on", async () => {
  const sim = simWithDemo(await flashWith(packDemo([
    "g = d['Global_Settings']",
    "g.loc[g.Label == 'Gig_View', 'Value'] = 'Y'",
  ].join("\n"))));
  sim.run(10000);
  assert.ok(gigView(sim, "HOME", "1/10>S01"));
});

// Text in the 11x18 font with its top left corner at x, y
function largeTextAt(sim, x, y, text) {
  for (let i = 0; i < text.length; i++) {
    for (let row = 0; row < 18; row++) {
      for (let c = 0; c < 11; c++) {
        const want = Boolean((font11x18[(text.charCodeAt(i) - 32) * 18 + row] << c) & 0x8000);
        if (lit(sim, x + i * 11 + c, y + row) !== want) return false;
      }
    }
  }
  return true;
}

test("A+B goes on to the demo's second setlist, named, from its first song, and the pedal keeps it through a restart (before 1.33, one setlist)", async () => {
  const sim = simWithDemo();
  sim.run(10000);                           // the power on banner goes by first
  const pedal = await Pedal.open(sim.access);
  assert.ok(infoLineIs(sim, "1/10>S01"), "the first setlist");
  pair(sim, 4, 5);
  assert.ok(largeTextAt(sim, 0, 8, "SETLIST 2") && largeTextAt(sim, 0, 38, "ACOUSTIC"), "its number and its name");
  assert.equal((await running(sim, () => pedal.getState())).bank, 12, "its first song");
  sim.run(1500);
  assert.ok(infoLineIs(sim, "1/4>S02"), "its place in it, and the next song");
  tap(sim, 9);
  assert.ok(infoLineIs(sim, "2/4>S06"), "Bank Up follows it");
  assert.equal((await running(sim, () => pedal.getState())).bank, 13);

  holdBoth(sim);                            // the editor's setlist screen edits it
  tap(sim, 7);
  tap(sim, 7);
  assert.ok(textAt(sim, 0, 0, "EDIT SETLIST2"));
  holdBoth(sim);

  sim.run(3000);                            // saved
  const again = simWithDemo(sim.flashNow());
  again.run(10000);
  assert.ok(infoLineIs(again, "2/4>S06"), "back on the second setlist, where it was");
  const other = await Pedal.open(again.access);
  tap(again, 9);
  tap(again, 9);
  tap(again, 9);
  assert.equal((await running(again, () => other.getState())).bank, 12, "round the second setlist");

  pair(again, 4, 5);                        // no third: round to the first
  assert.ok(largeTextAt(again, 0, 8, "SETLIST 1") && largeTextAt(again, 0, 38, "FULL SET"));
  assert.equal((await running(again, () => other.getState())).bank, 0);
});

test("a Bank Setlist command to a setlist with no songs says so and leaves the pedal where it is", async () => {
  const sim = simWithDemo(await flashWith(packDemo([
    "b = d['Button_Settings']",
    "b.loc[(b.Bank_Number == '30') & (b.Button_Identifier == '1'), 'A_OnValue_(CC/PB)'] = '3'",
  ].join("\n"))));
  sim.run(10000);
  const pedal = await Pedal.open(sim.access);
  tap(sim, 9);
  pair(sim, 4, 5);
  assert.ok(infoLineIs(sim, "NO SONGS"));
  assert.equal((await running(sim, () => pedal.getState())).bank, 12);
  sim.run(2000);
  assert.ok(infoLineIs(sim, "2/10>S04"), "still on the first setlist");
});

test("the computer writes a button's label, until the bank changes or until it changes it (before 1.34, it could not)", async () => {
  const sim = simWithDemo();
  sim.run(10000);                           // the demo's power on banner goes by first
  const pedal = await Pedal.open(sim.access);
  const seen = watch(sim);
  // SET_LABEL: the pedal's answer echoes the button and how
  const label = async (button, how, text) => {
    const answer = await running(sim, () => pedal.ask([82, button, how, ...Array.from(text, (c) => c.charCodeAt(0))], 83, 300)
      .catch(() => null));
    sim.run(200);
    return answer;
  };
  assert.deepEqual(await label(4, 0, "DLY"), [4, 0], "the pedal answers");
  assert.ok(bigTextAt(sim, 5, 47, "DLY"), "in button A's cell");
  await label(0, 1, "Delay");
  assert.ok(smallTextAt(sim, 2, 26, "Delay"), "five characters, in the small letters");
  tap(sim, 9);                              // Bank Up
  tap(sim, 8);                              // and back
  assert.ok(!bigTextAt(sim, 5, 47, "DLY"), "a label for the bank goes with it");
  assert.ok(smallTextAt(sim, 2, 26, "Delay"), "one kept stays");
  tap(sim, 0);                              // to the looper bank
  assert.ok(smallTextAt(sim, 2, 26, "Delay"), "in any bank");
  seen.splice(0);
  tap(sim, 0);
  tap(sim, 0);
  assert.deepEqual(seen.filter((m) => m.startsWith("USB")), ["USB b0 01 7f", "USB b0 01 00"],
    "while the button sends what the configuration says");
  await label(0x7f, 0, "");
  const fresh = simWithDemo();
  fresh.run(10000);
  tap(fresh, 0);
  const own = cellRows(fresh);
  assert.equal(cellRows(sim), own, "an empty label gives every button back its own");
  assert.equal(await label(10, 0, "X"), null, "a button it does not know: no answer");
  assert.equal(await label(0, 2, "X"), null, "nor a how");
  assert.equal(cellRows(sim), own);
});
