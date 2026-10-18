// The page's own scripts parse: app.js runs only in a browser, so no other
// test loads it, and a slip in it leaves the published page blank.
// Run from the repository root: node --test web/tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const web = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

for (const name of fs.readdirSync(web).filter((f) => f.endsWith(".js"))) {
  test(`${name} parses as a module`, () => {
    assert.doesNotThrow(() => execFileSync(process.execPath, ["--input-type=module", "--check"],
      { input: fs.readFileSync(path.join(web, name)), stdio: ["pipe", "pipe", "pipe"] }));
  });
}
