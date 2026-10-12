// A configuration in a link (web/share.js)
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { shareLink, linkedCsv, PREFIX } from "../share.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const demo = fs.readFileSync(path.join(root, "python/demo-all-features.csv"), "utf8");
const page = "https://charles5150.github.io/midi-commander-custom/";

test("a configuration comes back whole from its link, and the link is short", async () => {
  const link = await shareLink(page + "#old", demo);
  assert.ok(link.startsWith(page + PREFIX));
  assert.match(link.slice(page.length + PREFIX.length), /^[\w-]+$/);
  assert.ok(link.length < demo.length / 5);
  const back = await linkedCsv(new URL(link).hash);
  assert.equal(new TextDecoder().decode(back), demo);
});

test("an address with no configuration in it holds none", async () => {
  assert.equal(await linkedCsv(""), null);
  assert.equal(await linkedCsv("#stage"), null);
});

test("a link cut short or changed is refused, saying so", async () => {
  const hash = new URL(await shareLink(page, demo)).hash;
  await assert.rejects(linkedCsv(hash.slice(0, hash.length / 2)), /cut short or changed/);
  await assert.rejects(linkedCsv(PREFIX + "abc$%"), /cut short or changed/);
});
