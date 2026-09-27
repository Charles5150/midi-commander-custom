// The pedal without the pedal: the firmware itself, built for WebAssembly
// (firmware/sim), behind a Web MIDI port of its own. The page talks to it
// with the same SysEx as to the pedal, so reading, writing, the live view and
// everything else work on it unchanged. Its flash is kept in the browser, so
// what is written to it is still there on the next visit.

export const SIM_PORT_NAME = "MIDI Commander (simulated)";
const STORE_KEY = "mc-sim-flash";
const TICK_MS = 10;
const MAX_CATCH_UP_MS = 250;      // a tab in the background moves slower
const PORT = { USB: 0, DIN: 1, KEYS: 2 };

// Bytes of a USB MIDI event after its header, by code index number
const CIN_LENGTH = [0, 0, 2, 3, 3, 1, 2, 3, 3, 3, 3, 3, 2, 2, 3, 1];

// Raw MIDI to USB MIDI events of four bytes, cable 0
export function toUsbEvents(bytes) {
  const out = [];
  let i = 0;
  while (i < bytes.length) {
    const s = bytes[i];
    if (s === 0xf0) {
      let end = bytes.indexOf(0xf7, i);
      if (end < 0) end = bytes.length - 1;
      const msg = bytes.slice(i, end + 1);
      for (let j = 0; j < msg.length; j += 3) {
        const part = msg.slice(j, j + 3);
        const last = j + 3 >= msg.length;
        const cin = !last ? 0x4 : [0, 0x5, 0x6, 0x7][part.length];
        out.push(cin, part[0], part[1] || 0, part[2] || 0);
      }
      i = end + 1;
    } else if (s >= 0xf8) {
      out.push(0xf, s, 0, 0);
      i += 1;
    } else if (s >= 0xf0) {
      const len = s === 0xf2 ? 3 : s === 0xf1 || s === 0xf3 ? 2 : 1;
      const cin = len === 3 ? 0x3 : len === 2 ? 0x2 : 0x5;
      out.push(cin, s, bytes[i + 1] || 0, bytes[i + 2] || 0);
      i += len;
    } else if (s >= 0x80) {
      const len = s >= 0xc0 && s < 0xe0 ? 2 : 3;
      out.push(s >> 4, s, bytes[i + 1] || 0, len === 3 ? bytes[i + 2] || 0 : 0);
      i += len;
    } else {
      i += 1;   // running status is not used by anything that talks to the pedal
    }
  }
  return out;
}

const dataBytes = (s) => (s >= 0xf0 ? (s === 0xf2 ? 2 : s === 0xf1 || s === 0xf3 ? 1 : 0) : s >= 0xc0 && s < 0xe0 ? 1 : 2);

// Splits a raw byte stream, such as the DIN output, into whole messages
export class MidiParser {
  constructor(onMessage) {
    this.onMessage = onMessage;
    this.msg = [];
    this.need = 0;
    this.status = 0;
  }
  push(bytes) {
    for (const b of bytes) {
      if (b >= 0xf8) { this.onMessage([b]); continue; }
      if (b === 0xf0) { this.msg = [b]; this.need = -1; continue; }
      if (this.need === -1) {
        this.msg.push(b);
        if (b === 0xf7) { this.onMessage(this.msg); this.msg = []; this.need = 0; }
        continue;
      }
      if (b >= 0x80) {
        this.status = b;
        this.msg = [b];
        this.need = dataBytes(b);
      } else {
        if (!this.msg.length) {
          if (!this.status || this.status >= 0xf0) continue;   // stray data
          this.msg = [this.status];      // running status
          this.need = dataBytes(this.status);
        }
        this.msg.push(b);
        this.need--;
      }
      if (this.msg.length && this.need === 0) { this.onMessage(this.msg); this.msg = []; }
    }
  }
}

function loadFlash(size) {
  try {
    const text = localStorage.getItem(STORE_KEY);
    if (!text) return null;
    const bytes = Uint8Array.from(atob(text), (c) => c.charCodeAt(0));
    return bytes.length === size ? bytes : null;
  } catch (e) {
    return null;
  }
}

function storeFlash(bytes) {
  try {
    let text = "";
    for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    localStorage.setItem(STORE_KEY, btoa(text));
  } catch (e) {
    // Private windows and full storage: the pedal simply starts blank next time
  }
}

function checksum(bytes) {
  let sum = 0;
  for (let i = 0; i < bytes.length; i += 4) sum = (Math.imul(sum, 31) + (bytes[i] | bytes[i + 1] << 8 | bytes[i + 2] << 16 | bytes[i + 3] << 24)) | 0;
  return sum;
}

class Port extends EventTarget {
  constructor(access, type) {
    super();
    this.access = access;
    this.type = type;
    this.id = `mc-sim-${type}`;
    this.name = SIM_PORT_NAME;
    this.manufacturer = "midi-commander-custom";
    this.state = "connected";
    this.connection = "closed";
  }
  async open() { this.connection = "open"; return this; }
  async close() { this.connection = "closed"; return this; }
  send(data) {
    if (this.type !== "output" || this.state !== "connected") return;
    this.access.sim.usbIn(Array.from(data));
  }
}

// Looks like the MIDIAccess Web MIDI gives, with the simulated pedal's ports
export class SimAccess extends EventTarget {
  constructor(sim) {
    super();
    this.sim = sim;
    this.sysexEnabled = true;
    this.input = new Port(this, "input");
    this.output = new Port(this, "output");
    this.inputs = new Map([[this.input.id, this.input]]);
    this.outputs = new Map([[this.output.id, this.output]]);
  }
  _setState(state) {
    for (const port of [this.input, this.output]) {
      port.state = state;
      const e = new Event("statechange");
      e.port = port;
      this.dispatchEvent(e);
    }
  }
}

export class Simulator {
  // The module, fetched once
  static async load(url = new URL("pedal-sim.wasm", import.meta.url)) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`cannot load the simulator: ${response.status} ${response.statusText}`);
    return new Simulator(await WebAssembly.compile(await response.arrayBuffer()));
  }

  constructor(module, { persist = true } = {}) {
    this.module = module;
    this.persist = persist;
    this.access = new SimAccess(this);
    this.onOutput = null;         // (port "USB" | "DIN" | "keys", bytes) for a monitor
    this.timer = null;
    this.flash = null;
    this.sysex = null;
    this.din = new MidiParser((msg) => this.onOutput && this.onOutput("DIN", msg));
    this.savedSum = 0;
    this.drainQueued = false;
  }

  get e() { return this.instance.exports; }
  get memory() { return new Uint8Array(this.e.memory.buffer); }

  // Power on: a fresh module, with the flash it had
  _boot() {
    this.instance = new WebAssembly.Instance(this.module, {});
    const e = this.e;
    const size = e.sim_flash_size();
    if (!this.flash) this.flash = (this.persist && loadFlash(size)) || new Uint8Array(size).fill(0xff);
    if (e.sim_flash() + size > e.__global_base.value) throw new Error("the simulator's flash overlaps its data");
    this.memory.set(this.flash, e.sim_flash());
    this.savedSum = checksum(this.flash);
    this.sysex = null;
    e.sim_boot(0);
    this.last = performance.now();
  }

  // The flash as it is now, 256 kB from 0x08000000
  flashNow() {
    const e = this.e;
    return this.memory.slice(e.sim_flash(), e.sim_flash() + e.sim_flash_size());
  }

  _save() {
    this.flash = this.flashNow();
    const sum = checksum(this.flash);
    if (this.persist && sum !== this.savedSum) storeFlash(this.flash);
    this.savedSum = sum;
  }

  start() {
    if (this.timer) return;
    this._boot();
    if (this.access.input.state !== "connected") this.access._setState("connected");
    this.timer = setInterval(() => this._tick(), TICK_MS);
    this.saveTimer = setInterval(() => this._save(), 3000);
  }

  stop() {
    if (!this.timer) return;
    this._save();
    clearInterval(this.timer);
    clearInterval(this.saveTimer);
    this.timer = null;
    this.access._setState("disconnected");
  }

  // Time on, as much as has passed since the last call
  _tick() {
    const now = performance.now();
    const ms = Math.min(Math.floor(now - this.last), MAX_CATCH_UP_MS);
    if (ms < 1) return;
    this.last += ms;
    if (now - this.last > MAX_CATCH_UP_MS) this.last = now;
    this.run(ms);
  }

  // ms milliseconds of the pedal, and what it sent meanwhile
  run(ms) {
    this.e.sim_run(ms);
    this._drain();
    if (this.e.sim_restart_asked()) this._restart();
  }

  // The pedal restarts: its ports go away while it boots, as over USB
  _restart() {
    this._save();
    this.access._setState("disconnected");
    this._boot();
    this.run(1300);   // the banner, up to where USB comes up
    this.access._setState("connected");
  }

  usbIn(bytes) {
    this.usbEvents(toUsbEvents(bytes));
  }

  // USB MIDI events as they are, any cable: for tests of the three ports
  usbEvents(events) {
    const e = this.e;
    for (let i = 0; i < events.length; i += 64) {
      const part = events.slice(i, i + 64);
      this.memory.set(part, e.sim_in_buffer());
      e.sim_usb_in(part.length);
    }
    // Answers leave at once, as from the USB interrupt
    if (!this.drainQueued) {
      this.drainQueued = true;
      queueMicrotask(() => { this.drainQueued = false; this._drain(); });
    }
  }

  _drain() {
    const e = this.e;
    const len = e.sim_out_len();
    if (!len) return;
    const q = this.memory.slice(e.sim_out(), e.sim_out() + len);
    e.sim_out_clear();
    for (let i = 0; i + 3 <= q.length;) {
      const port = q[i], size = q[i + 1] | (q[i + 2] << 8);
      const data = q.subarray(i + 3, i + 3 + size);
      i += 3 + size;
      if (port === PORT.USB) this._usbOut(data);
      else if (port === PORT.DIN) this.din.push(data);
      else if (port === PORT.KEYS && this.onOutput) this.onOutput("keys", Array.from(data));
    }
  }

  // USB MIDI events to whole messages, as Web MIDI hands them over
  _usbOut(data) {
    if (this.onUsbEvents) this.onUsbEvents(Array.from(data));
    for (let i = 0; i + 4 <= data.length; i += 4) {
      if (data[i] >> 4) continue;     // the simulated port is the first
      const cin = data[i] & 0x0f;
      const bytes = Array.from(data.subarray(i + 1, i + 1 + CIN_LENGTH[cin]));
      if (cin === 0x4 || (cin >= 0x5 && cin <= 0x7 && (this.sysex || bytes[0] === 0xf0))) {
        this.sysex = (this.sysex || []).concat(bytes);
        if (cin === 0x4) continue;
        const msg = this.sysex;
        this.sysex = null;
        this._deliver(msg);
      } else if (bytes.length) {
        this._deliver(bytes);
      }
    }
  }

  _deliver(msg) {
    if (this.onOutput && msg[0] !== 0xf0) this.onOutput("USB", msg);
    if (this.access.input.state !== "connected") return;
    const ev = new Event("midimessage");
    ev.data = Uint8Array.from(msg);
    this.access.input.dispatchEvent(ev);
  }

  // Straight on the simulated hardware, for tests: a foot on switch 0-9
  // (1 2 3 4 A B C D, Bank Down, Bank Up), a pedal at 0-4095
  footswitch(id, down) { this.e.sim_switch(id, down); }
  pedal(id, value) { this.e.sim_pedal(id, value); }
  screen() { return this.memory.slice(this.e.sim_screen(), this.e.sim_screen() + 130 * 8); }
  leds() { return Array.from(this.memory.slice(this.e.sim_leds(), this.e.sim_leds() + 10)); }

  // Back to a pedal with nothing written: every slot erased
  wipe() {
    this.flash = new Uint8Array(this.e.sim_flash_size()).fill(0xff);
    this.memory.set(this.flash, this.e.sim_flash());
    this._restart();
  }
}
