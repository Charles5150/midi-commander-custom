// Retake the web configurator's screenshots in docs/images, with headless Chrome.
//
//     node tools/web_screenshots.mjs            # all of them
//     node tools/web_screenshots.mjs stage      # only some
//
// Serves web/ from the repository on a local port and drives the page on the
// simulated pedal, so no pedal is needed; web/pedal-sim.wasm must be built
// first (sh firmware/sim/build.sh). CHROME names the browser if it is not
// Google Chrome in /Applications.
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const IMAGES = path.join(ROOT, "docs", "images");
const CHROME = process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const PORT = 8790, DEBUG = 9340;
const WIDTH = 1100, HEIGHT = 720;
const BANK_CHANGE_CC = 32;     // the demo's Bank_Change_CC

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// A Chrome left on the port by a run that was cut short would be driven in
// place of a fresh one, its simulated pedal still holding what that run left
const busy = await fetch(`http://127.0.0.1:${DEBUG}/json/version`).then(() => true, () => false);
if (busy) {
  console.error(`Port ${DEBUG} is taken, most likely by a Chrome left from an earlier run: pkill -f remote-debugging-port=${DEBUG}`);
  process.exit(1);
}
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "mc-shots-"));
const server = spawn("python3", ["-m", "http.server", String(PORT), "--bind", "127.0.0.1"], { cwd: ROOT, stdio: "ignore" });
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${DEBUG}`, `--user-data-dir=${profile}`,
  `--window-size=${WIDTH},${HEIGHT}`, "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
for (const signal of ["SIGINT", "SIGTERM", "SIGALRM"]) {
  process.on(signal, () => { chrome.kill(); server.kill(); process.exit(1); });
}

let ws, id = 0;
const pending = new Map();
for (let i = 0; i < 50 && !ws; i++) {
  try {
    const page = (await (await fetch(`http://127.0.0.1:${DEBUG}/json`)).json()).find((t) => t.type === "page");
    if (page) ws = new WebSocket(page.webSocketDebuggerUrl);
  } catch {}
  await sleep(200);
}
if (ws.readyState !== WebSocket.OPEN) await new Promise((r) => ws.addEventListener("open", r));
ws.addEventListener("message", (m) => {
  const d = JSON.parse(m.data);
  if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); }
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
async function ev(expr) {
  const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true, userGesture: true });
  if (r.error || r.result.exceptionDetails) throw new Error(JSON.stringify(r.error || r.result.exceptionDetails) + " in " + expr.slice(0, 80));
  return r.result.result.value;
}
async function until(expr, ms = 90000) {
  for (const end = Date.now() + ms; Date.now() < end; await sleep(300)) if (await ev(`Boolean(${expr})`)) return;
  throw new Error("timed out waiting for " + expr);
}
const button = (text) => `[...document.querySelectorAll("button")].find((b) => b.textContent === ${JSON.stringify(text)})`;
const click = (text) => ev(`${button(text)}.click(), 0`);
async function size(width, height) {
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
  await sleep(400);
}
const wanted = process.argv.slice(2);
let current = "";
async function capture(name) {
  if (wanted.length && !wanted.includes(current)) return;
  await sleep(600);
  const r = await send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(path.join(IMAGES, `${name}.png`), Buffer.from(r.result.data, "base64"));
  console.log("wrote", `docs/images/${name}.png`);
}
async function tap(sw) {
  await ev(`mc.state.pedal.press(${JSON.stringify(sw)}, true).then(() => 0)`);
  await sleep(120);
  await ev(`mc.state.pedal.press(${JSON.stringify(sw)}, false).then(() => 0)`);
  await sleep(600);
}

// The first song, by the demo's bank change CC, as if from the computer
async function home() {
  await ev(`mc.state.sim.usbIn([0xb0, ${BANK_CHANGE_CC}, 0]), 0`);
  await until(`mc.state.pedal.getState().then((s) => s.bank === 0)`, 5000);
}

// Each shot starts where the one before it left the page, so all of them
// run; only those asked for are written
const PAGE = "https://charles5150.github.io/midi-commander-custom/";
const SHOTS = {
  async start() {
    await capture("web_start");
  },
  async banks() {
    await ev(`document.querySelector("#btn-demo").click(), 0`);
    await until(`!!mc.state.config`);
    await click("Banks");
    await ev(`document.querySelectorAll(".bank-list button")[1].click(), 0`);
    await ev(`document.querySelectorAll(".pedal-grid .pedal-button")[4].click(), 0`);
    await capture("web_banks");
  },
  async share() {
    await ev(`document.querySelector("#btn-share").click(), 0`);
    await until(`document.querySelector(".share-link")`);
    // The link as from the published page, not this local one
    await ev(`(() => { const t = document.querySelector(".share-link"); t.value = t.value.replace(/^[^#]*/, ${JSON.stringify(PAGE)}); })(), 0`);
    await capture("web_share");
    await click("Close");
  },
  async live() {
    // A note on the first song, for the Stage shot
    await ev(`document.querySelectorAll(".bank-list button")[0].click(), 0`);
    await ev(`(() => { const t = document.querySelector("textarea"); t.value = "Capo 2, key of A minor\\nIntro: 4 bars, then the riff twice"; t.dispatchEvent(new Event("change")); })(), 0`);
    await ev(`mc.simulate(), 0`);
    await until(`!!mc.state.pedal && !mc.state.busy`);
    await sleep(1500);
    await ev(`mc.state.dirty = false, 0`);
    await click("Live pedal");
    // Hold both pedals halfway, and start from the first song
    await ev(`document.querySelectorAll('input[type="range"]').forEach((s, i) => { s.value = [6500, 9800][i]; s.dispatchEvent(new Event("input")); }), 0`);
    await sleep(800);
    await home();
    await tap("1");      // HOME's 1 goes to LOOP
    await tap("A");      // and lights TRK1
    await ev(`document.querySelector("#toasts").replaceChildren(), 0`);
    await size(WIDTH, 1180);
    await sleep(1500);
    await capture("web_live");
    await size(WIDTH, HEIGHT);
    await tap("A");
  },
  async stage() {
    await size(1024, 768);
    await home();
    await click("Stage");
    await click("Full screen");
    await ev(`document.querySelector("#toasts").replaceChildren(), 0`);
    await capture("web_stage");
    await ev(`document.querySelector(".stage-close").click(), 0`);
    await size(WIDTH, HEIGHT);
  },
};

let failed = false;
try {
  await send("Page.enable");
  await send("Runtime.enable");
  await size(WIDTH, HEIGHT);
  await send("Page.navigate", { url: `http://127.0.0.1:${PORT}/web/index.html` });
  await until(`window.mc && mc.state.tools`);
  await sleep(500);
  for (const [name, shoot] of Object.entries(SHOTS)) {
    current = name;
    await shoot();
  }
} catch (e) {
  console.error(e.message);
  failed = true;
}
const closed = new Promise((r) => chrome.on("exit", r));
chrome.kill();
await closed;
server.kill();
fs.rmSync(profile, { recursive: true, force: true });
process.exit(failed ? 1 : 0);
