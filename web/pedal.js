// The pedal over Web MIDI: the SysEx protocol of python/lib/midiDevice.py and
// the slot reading and writing of python/lib/slotIO.py, for the browser.

export const MANUF_ID = 0x7d;
export const CMD = {
  ERASE_FLASH: 52, RSP_ERASE_FLASH: 53,
  WRITE_FLASH: 54, RSP_WRITE_FLASH: 55,
  READ_FLASH: 56, RSP_READ_FLASH: 57,
  GET_VERSION: 58, RSP_GET_VERSION: 59,
  RESET: 60,
  SELECT_SLOT: 64, RSP_SELECT_SLOT: 65,
  PRESS_BUTTON: 66, RSP_PRESS_BUTTON: 67,
  GET_STATE: 68, RSP_GET_STATE: 69,
  GET_SCREEN: 70, RSP_GET_SCREEN: 71,
  ENTER_DFU: 74, RSP_ENTER_DFU: 75,
  BANNER: 76, RSP_BANNER: 77,
};
const ENTER_DFU_CHECK = [0x44, 0x46];
export const SWITCHES = ["1", "2", "3", "4", "A", "B", "C", "D", "DOWN", "UP"];
export const LED_LEVELS = 16;
export const SCREEN_WIDTH = 130;         // columns in the pedal's buffer, 128 shown
export const SCREEN_HEIGHT = 64;
const SCREEN_PARTS = (SCREEN_HEIGHT / 8) * 2;
const SCREEN_PART_BYTES = SCREEN_WIDTH / 2;
const WRITE_TRIES = 4;                    // see slotIO._write_chunk (#147)

export class Timeout extends Error {}
export class NotFound extends Error {}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const matches = (port) => /STM|MIDI Commander/.test(port.name || "");

export function versionAtLeast(version, major, minor) {
  const parts = String(version).trim().split(".").slice(0, 2).map(Number);
  if (parts.some(Number.isNaN)) return false;
  while (parts.length < 2) parts.push(0);
  return parts[0] > major || (parts[0] === major && parts[1] >= minor);
}

export function unpack7(data) {
  const out = [];
  for (let i = 0; i < data.length; i += 8) {
    const high = data[i];
    data.slice(i + 1, i + 8).forEach((low, k) => out.push((low & 0x7f) | ((high >> k) & 1 ? 0x80 : 0)));
  }
  return out;
}

export function parseState(d) {
  const text = (a) => String.fromCharCode(...a.map((b) => (b >= 0x20 && b <= 0x7e ? b : 0x20))).trimEnd();
  const toggles = d[2] | (d[3] << 7);
  return {
    bank: d[0],
    slot: d[1],
    toggles: [...Array(8)].map((_, i) => Boolean((toggles >> i) & 1)),
    bankName: text(d.slice(4, 8)),
    labels: [...Array(8)].map((_, i) => text(d.slice(8 + 4 * i, 12 + 4 * i))),
    leds: d.slice(40, 50).map((v) => Math.min(v, LED_LEVELS)),
    frame: d.length >= 53 ? d[50] | (d[51] << 7) : null,
    asleep: d.length >= 53 ? Boolean(d[52]) : false,
    safeMode: d.length >= 62 ? Boolean(d[61]) : false,
  };
}

export class Pedal {
  constructor(access, input, output) {
    this.access = access;
    this.input = input;
    this.output = output;
    this.queue = [];          // SysEx answers, data after F0 7D
    this.waiters = [];
    this.onMessage = null;    // everything else the pedal sends, for a monitor
    this.onGone = null;
    this._listen = (e) => this._receive(Array.from(e.data));
    input.addEventListener("midimessage", this._listen);
    this._state = (e) => {
      if (e.port.id === input.id && e.port.state === "disconnected" && this.onGone) this.onGone();
    };
    access.addEventListener("statechange", this._state);
  }

  // Open the pedal's ports, asking for Web MIDI with SysEx unless given it
  static async open(access = null) {
    if (!access) {
      if (!navigator.requestMIDIAccess) throw new NotFound("this browser has no Web MIDI: use Chrome, Edge or Opera");
      access = await navigator.requestMIDIAccess({ sysex: true });
    }
    const input = [...access.inputs.values()].find(matches);
    const output = [...access.outputs.values()].find(matches);
    if (!input || !output) throw new NotFound("no Midi Commander found: check the USB cable, and close other programs using it");
    await input.open();
    await output.open();
    return new Pedal(access, input, output);
  }

  close() {
    this.input.removeEventListener("midimessage", this._listen);
    this.access.removeEventListener("statechange", this._state);
    this.waiters.forEach((w) => w.reject(new Timeout("closed")));
    this.waiters = [];
  }

  _receive(data) {
    if (data[0] !== 0xf0) {
      if (this.onMessage) this.onMessage(data);
      return;
    }
    if (data[1] !== MANUF_ID) return;
    const msg = data.slice(1, data[data.length - 1] === 0xf7 ? -1 : undefined);
    for (let i = 0; i < this.waiters.length; i++) {
      const w = this.waiters[i];
      if (msg[1] === w.rsp && (!w.accept || w.accept(msg.slice(2)))) {
        this.waiters.splice(i, 1);
        clearTimeout(w.timer);
        w.resolve(msg.slice(2));
        return;
      }
    }
    this.queue.push(msg);
    if (this.queue.length > 64) this.queue.shift();
  }

  flush() {
    this.queue = [];
  }

  send(data) {
    this.output.send([0xf0, MANUF_ID, ...data, 0xf7]);
  }

  // The data after the answer code rsp; accept can pass over stale answers
  waitFor(rsp, timeout = 2000, accept = null) {
    const i = this.queue.findIndex((m) => m[1] === rsp && (!accept || accept(m.slice(2))));
    if (i >= 0) return Promise.resolve(this.queue.splice(i, 1)[0].slice(2));
    return new Promise((resolve, reject) => {
      const w = { rsp, accept, resolve, reject };
      w.timer = setTimeout(() => {
        this.waiters.splice(this.waiters.indexOf(w), 1);
        reject(new Timeout(`no answer ${rsp} from the pedal`));
      }, timeout);
      this.waiters.push(w);
    });
  }

  async ask(data, rsp, timeout, accept) {
    const answer = this.waitFor(rsp, timeout, accept);
    this.send(data);
    return answer;
  }

  async version() {
    const d = await this.ask([CMD.GET_VERSION], CMD.RSP_GET_VERSION, 1000);
    return String.fromCharCode(...d).trim();
  }

  // Point the next read or write at slot 0-3, or with null only ask.
  // {target, active, valid: [slots holding a configuration]}
  async selectSlot(slot = null) {
    const d = await this.ask([CMD.SELECT_SLOT, slot === null ? 0x7f : slot], CMD.RSP_SELECT_SLOT, 1000);
    return { target: d[0], active: d[1], valid: [0, 1, 2, 3].filter((s) => d[2] & (1 << s)) };
  }

  async readChunk(index, timeout = 1000) {
    const hi = (index >> 7) & 0x7f, lo = index & 0x7f;
    const d = await this.ask([CMD.READ_FLASH, hi, lo], CMD.RSP_READ_FLASH, timeout,
      (a) => a.length >= 34 && a[0] === hi && a[1] === lo);
    const out = new Uint8Array(16);
    for (let i = 0; i < 16; i++) out[i] = (d[2 + 2 * i] << 4) | (d[3 + 2 * i] & 0x0f);
    return out;
  }

  // numBytes of the selected slot from byte start, a multiple of 16
  async readSettings(numBytes, progress, start = 0) {
    const chunks = Math.ceil(numBytes / 16);
    const out = new Uint8Array(chunks * 16);
    for (let i = 0; i < chunks; i++) {
      out.set(await this.readChunk(start / 16 + i), i * 16);
      if (progress) progress(i + 1, chunks);
    }
    return out.slice(0, numBytes);
  }

  // The selected slot, as slotIO.read_image: {data, image}
  async readImage(version, sizes, progress) {
    const data = await this.readSettings(sizes.config, progress);
    if (versionAtLeast(version, 0, 26) && data[37] === 1) {
      const ext = await this.readSettings(sizes.double, progress, sizes.doubleOffset);
      const image = new Uint8Array(sizes.doubleOffset + ext.length).fill(0xff);
      image.set(data);
      image.set(ext, sizes.doubleOffset);
      return { data, image };
    }
    return { data, image: data };
  }

  async _writeChunk(x, chunk, log) {
    const data = [CMD.WRITE_FLASH, (x >> 7) & 0x7f, x & 0x7f];
    for (const b of chunk) data.push(b >> 4, b & 0x0f);
    for (let attempt = 0; attempt < WRITE_TRIES; attempt++) {
      let answer;
      try {
        answer = await this.ask(data, CMD.RSP_WRITE_FLASH, 2000);
      } catch (e) {
        if (!(e instanceof Timeout)) throw e;
        this.flush();   // a late answer must not pass for the next block's
        let back;
        try {
          back = await this.readChunk(x);
        } catch (e2) {
          if (e2 instanceof Timeout) continue;
          throw e2;
        }
        if (back.every((b, i) => b === chunk[i])) {
          log(`No answer for byte ${x * 16}, but it was written`);
          return;
        }
        log(`No answer for byte ${x * 16}: sending it again`);
        continue;
      }
      if (answer.length && answer[0]) throw new Error(`the pedal could not write its flash at byte ${x * 16}`);
      return;
    }
    throw new Timeout(`no answer from the pedal for byte ${x * 16}, ${WRITE_TRIES} times`);
  }

  // Erase the selected slot and write image into it (slotIO.write_image)
  async writeImage(version, config, image, log = () => {}, progress) {
    if (image.length > config.length && !versionAtLeast(version, 0, 26)) {
      log("WARNING: double press needs firmware 0.26 or later; writing everything else");
      image = Uint8Array.from(config);
      image[37] = 0;
    }
    log("Erasing the slot");
    const erased = await this.ask([CMD.ERASE_FLASH, 0x42, 0x24], CMD.RSP_ERASE_FLASH, 5000);
    if (erased.length && erased[0]) throw new Error("the pedal could not erase its flash");
    const chunks = Math.ceil(image.length / 16);
    for (let x = 0; x < chunks; x++) {
      if (progress) progress(x + 1, chunks);
      const chunk = new Uint8Array(16).fill(0xff);
      chunk.set(image.slice(x * 16, x * 16 + 16));
      if (chunk.every((b) => b === 0xff)) continue;
      await this._writeChunk(x, chunk, log);
      await sleep(5);
    }
  }

  reset() {
    this.send([CMD.RESET]);
  }

  async getState() {
    return parseState(await this.ask([CMD.GET_STATE], CMD.RSP_GET_STATE, 1000));
  }

  // The whole screen buffer, SCREEN_WIDTH x SCREEN_HEIGHT / 8 bytes
  async getScreen() {
    const buffer = [];
    for (let part = 0; part < SCREEN_PARTS; part++) {
      const d = await this.ask([CMD.GET_SCREEN, part], CMD.RSP_GET_SCREEN, 1000, (a) => a[0] === part);
      const chunk = unpack7(d.slice(1));
      if (chunk.length !== SCREEN_PART_BYTES) throw new Error(`screen part ${part} has ${chunk.length} bytes`);
      buffer.push(...chunk);
    }
    return buffer;
  }

  async press(sw, down) {
    await this.ask([CMD.PRESS_BUTTON, SWITCHES.indexOf(sw), down ? 1 : 0], CMD.RSP_PRESS_BUTTON, 1000);
  }

  // Restart in the stock bootloader's DFU mode (firmware 0.58): true when on its way
  async enterDfu() {
    const d = await this.ask([CMD.ENTER_DFU, ...ENTER_DFU_CHECK], CMD.RSP_ENTER_DFU, 1000);
    return d.length > 0 && d[0] === 0;
  }
}
