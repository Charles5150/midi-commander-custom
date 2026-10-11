// pedal.js's choice of slot, against a make believe pedal that answers
// SELECT_SLOT as a given firmware would. The same rules as select_slot in
// python/lib/slotIO.py. Run from the repository root: node --test web/tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import { Pedal, Timeout } from "../pedal.js";

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
