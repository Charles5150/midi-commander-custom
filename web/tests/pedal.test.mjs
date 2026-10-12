// pedal.js's choice of slot, against a make believe pedal that answers
// SELECT_SLOT as a given firmware would. The same rules as select_slot in
// python/lib/slotIO.py. Run from the repository root: node --test web/tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import { Pedal, Timeout, parseState } from "../pedal.js";

// answer(slot) gives [target, active, valid mask] for a SELECT_SLOT of slot
// (0x7f to only ask), or null for no answer
function fakePedal(answer) {
  const pedal = Object.create(Pedal.prototype);
  pedal.asked = [];
  pedal.ask = async (data) => {
    pedal.asked.push(data[1]);
    const a = answer(data[1]);
    if (!a) throw new Timeout("no answer");
    return a;
  };
  return pedal;
}

const current = (active, valid) => {
  let target = active;
  return (s) => { if (s !== 0x7f) target = s; return [target, active, valid]; };
};

test("a slot is asked for by number and taken as the pedal answers it", async () => {
  const pedal = fakePedal(current(1, 0b0111));
  assert.deepEqual(await pedal.useSlot(2), { target: 2, active: 1, valid: [0, 1, 2] });
  assert.deepEqual(await pedal.useSlot(null), { target: 1, active: 1, valid: [0, 1, 2] });
  assert.deepEqual(pedal.asked, [0x7f, 2, 0x7f, 1], "the active slot asked for, never assumed");
});

test("a slot the pedal did not take is refused", async () => {
  const pedal = fakePedal((s) => [0, 0, 0b0011]);
  await assert.rejects(pedal.useSlot(1), /did not accept slot 2/);
});

test("firmware before 0.24 has slot 1 only", async () => {
  const pedal = fakePedal(() => null);
  assert.deepEqual(await pedal.useSlot(null), { target: 0, active: 0, valid: [0], single: true });
  assert.deepEqual(await pedal.useSlot(0), { target: 0, active: 0, valid: [0], single: true });
  await assert.rejects(pedal.useSlot(2), /single configuration; slots need 0.24/);
});

test("an error other than no answer is not taken for old firmware", async () => {
  const pedal = Object.create(Pedal.prototype);
  pedal.ask = async () => { throw new Error("port gone"); };
  await assert.rejects(pedal.useSlot(0), /port gone/);
});

test("the bank Bank Up and Down are previewing is read from the state, none as 7F", () => {
  const state = (preview) => [3, 0, 1, 0, ..."SONG".split("").map((c) => c.charCodeAt(0)), ...Array(32).fill(0x20),
    ...Array(10).fill(0), 0, 0, 0, ...Array(8).fill(0), 0, preview, ...Array(8).fill(0)];
  assert.equal(parseState(state(5)).preview, 5);
  assert.equal(parseState(state(0x7f)).preview, null);
  assert.equal(parseState(state(5).slice(0, 62)).preview, null, "older firmware sends none");
  assert.equal(parseState(state(5)).bankName, "SONG");
  assert.deepEqual(parseState(state(5)).toggles.slice(0, 2), [true, false]);
});

// The MIDIAccess of the iOS Web MIDI browsers (Web MIDI Browser's polyfill):
// port maps whose values() is not iterable, one listener list shared by every
// port, called with this = the port that received, thenables for Promises
function iosAccess(names) {
  const listeners = [];
  const port = (name, type) => ({
    name, type, id: `${type}-${name}`,
    addEventListener: (t, f) => listeners.push(f),
    removeEventListener: (t, f) => listeners.splice(listeners.indexOf(f), 1),
    open() { return { then: (ok) => setTimeout(() => ok(this), 0) }; },
    receive(data) { listeners.forEach((f) => f.call(this, { data })); },
  });
  const map = (list) => ({ size: list.length, forEach: (cb) => list.forEach((p) => cb(p)), values: () => ({ next: () => ({ done: true }) }) });
  const inputs = names.map((n) => port(n, "input"));
  return { inputs: map(inputs), outputs: map(names.map((n) => port(n, "output"))), addEventListener() {}, removeEventListener() {}, list: inputs };
}

test("the pedal is found and heard through the iOS browsers' Web MIDI, other inputs not", async () => {
  const access = iosAccess(["Keys", "MIDI Commander Custom"]);
  const pedal = await Pedal.open(access);
  assert.equal(pedal.input.name, "MIDI Commander Custom");
  const heard = [];
  pedal.onMessage = (m) => heard.push(m);
  access.list[0].receive([0x90, 60, 100]);
  access.list[1].receive([0xb0, 7, 64]);
  assert.deepEqual(heard, [[0xb0, 7, 64]]);
});

test("MIDI without SysEx is refused, saying so", async () => {
  const access = iosAccess(["MIDI Commander Custom"]);
  access.sysexEnabled = false;
  await assert.rejects(Pedal.open(access), /without SysEx/);
});
