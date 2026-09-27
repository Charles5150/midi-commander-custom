// Firmware updates from the browser: the checks of python/lib/firmwareUpdate.py
// on the .dfu file, and the DfuSe download dfu-util does, over WebUSB.
// Works with the browser's navigator.usb or, for tests, node-usb's WebUSB.

export const APP_ADDRESS = 0x08003000;     // where the stock bootloader looks for the firmware
export const APP_MAX_SIZE = 76 * 1024;     // the linker scripts' limit: the double press areas follow
export const DFU_VENDOR = 0x0483;
export const DFU_PRODUCT = 0xdf11;
export const DFU_FILTER = { vendorId: DFU_VENDOR, productId: DFU_PRODUCT };

export class UpdateError extends Error {}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let CRC_TABLE = null;
function crc32(bytes) {
  if (!CRC_TABLE) {
    CRC_TABLE = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      CRC_TABLE[n] = c >>> 0;
    }
  }
  let c = 0xffffffff;
  for (const b of bytes) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

const u32 = (b, i) => (b[i] | (b[i + 1] << 8) | (b[i + 2] << 16) | (b[i + 3] << 24)) >>> 0;
const u16 = (b, i) => b[i] | (b[i + 1] << 8);
const ascii = (b) => String.fromCharCode(...b);

// {address, payload} of a DfuSe file holding one image, checked from its
// signature to its CRC, as firmwareUpdate.read_dfuse
export function readDfuse(data) {
  if (data.length < 11 + 274 + 8 + 16 || ascii(data.slice(0, 5)) !== "DfuSe") throw new UpdateError("not a DfuSe .dfu file");
  const body = data.slice(0, -16), suffix = data.slice(-16);
  if (ascii(suffix.slice(8, 11)) !== "UFD" || suffix[11] !== 16) throw new UpdateError("the .dfu file has no DFU suffix");
  // The suffix stores the CRC complemented: ~crc32 of everything before it
  const expected = (~crc32(data.slice(0, -4))) >>> 0;
  if (u32(suffix, 12) !== expected) throw new UpdateError("the .dfu file is damaged: its CRC does not match");
  const product = u16(suffix, 2), vendor = u16(suffix, 4);
  const ok = (vendor === DFU_VENDOR && product === DFU_PRODUCT) || (vendor === 0xffff && product === 0xffff);
  if (!ok) throw new UpdateError(`the .dfu file is for another device (${vendor.toString(16).padStart(4, "0")}:${product.toString(16).padStart(4, "0")})`);
  if (data[5] !== 1 || u32(data, 6) !== body.length) throw new UpdateError("the .dfu file's header does not match its length");
  if (data[10] !== 1) throw new UpdateError(`the .dfu file holds ${data[10]} images, not one`);
  const t = body.slice(11);
  if (ascii(t.slice(0, 6)) !== "Target") throw new UpdateError("the .dfu file has no image in it");
  if (t[6] !== 0 || u32(t, 270) !== 1) throw new UpdateError("the .dfu file is not a single image for the internal flash");
  const address = u32(t, 274), length = u32(t, 278);
  const payload = t.slice(282, 282 + length);
  if (payload.length !== length) throw new UpdateError("the .dfu file is cut short");
  return { address, payload };
}

// The firmware image in a .dfu file, refused if it would not start on the pedal
export function loadImage(data) {
  const { address, payload } = readDfuse(data);
  if (address !== APP_ADDRESS) {
    throw new UpdateError(`the image goes at 0x${address.toString(16).toUpperCase()}, not 0x08003000 behind the bootloader; build it with the midi_dfu environment`);
  }
  if (payload.length < 8 || payload.length > APP_MAX_SIZE) {
    throw new UpdateError(`the image is ${payload.length} bytes, more than the ${APP_MAX_SIZE} there is room for`);
  }
  // The bootloader's own test: an image that fails it would leave the pedal starting in DFU for good
  if ((u32(payload, 0) & 0x2ffe0000) !== 0x20000000) {
    throw new UpdateError("the image does not start with a stack pointer, so the pedal would not run it");
  }
  return payload;
}

// "@Internal Flash  /0x08000000/064*0002Kg" -> [{start, pageSize, pages, erasable, writable}]
export function parseMemoryMap(name) {
  const m = /\/0x([0-9a-f]+)\/(.*)$/i.exec(name || "");
  if (!m) return null;
  let address = parseInt(m[1], 16);
  const segments = [];
  for (const part of m[2].split(",")) {
    const s = /(\d+)\*(\d+)\s*([KMB ]?)([a-g])/i.exec(part.trim());
    if (!s) continue;
    const mult = { K: 1024, M: 1024 * 1024 }[s[3].toUpperCase()] || 1;
    const pages = Number(s[1]), pageSize = Number(s[2]) * mult;
    const type = s[4].toLowerCase().charCodeAt(0) - 0x60;     // a=1 .. g=7: read 1, erase 2, write 4
    segments.push({ start: address, pageSize, pages, erasable: Boolean(type & 2), writable: Boolean(type & 4) });
    address += pages * pageSize;
  }
  return segments;
}

// DFU requests and states
const DNLOAD = 1, UPLOAD = 2, GETSTATUS = 3, CLRSTATUS = 4, ABORT = 6;
const S = { IDLE: 2, DNLOAD_SYNC: 3, DNBUSY: 4, DNLOAD_IDLE: 5, MANIFEST_SYNC: 6, MANIFEST: 7, UPLOAD_IDLE: 9, ERROR: 10 };

export class Dfu {
  constructor(device, log = () => {}) {
    this.device = device;
    this.log = log;
  }

  // A pedal already in DFU mode that this page may use, or null
  static async find(usb) {
    const devices = await usb.getDevices();
    return devices.find((d) => d.vendorId === DFU_VENDOR && d.productId === DFU_PRODUCT) || null;
  }

  async open() {
    const d = this.device;
    await d.open();
    if (d.configuration === null) await d.selectConfiguration(1);
    const raw = await this._configDescriptor();
    const alts = raw.alts.filter((a) => a.cls === 0xfe && a.subclass === 1);
    if (!alts.length) throw new UpdateError("the device in DFU mode has no DFU interface");
    this.transferSize = raw.transferSize || 1024;
    // The internal flash, by its name; its memory map says the page size
    let chosen = null;
    for (const a of alts) {
      a.name = await this._string(a.iInterface);
      if (/internal flash/i.test(a.name)) { chosen = a; break; }
    }
    if (!chosen) throw new UpdateError("the bootloader shows no internal flash");
    this.iface = chosen.number;
    this.map = parseMemoryMap(chosen.name);
    if (!this.map || !this.map.length) throw new UpdateError(`cannot read the bootloader's memory map: ${chosen.name}`);
    await d.claimInterface(this.iface);
    await d.selectAlternateInterface(this.iface, chosen.alt);
    this.log(`Bootloader: ${chosen.name.trim()}, ${this.transferSize} bytes a transfer`);
  }

  async close() {
    try { await this.device.close(); } catch (e) { /* gone already */ }
  }

  async _configDescriptor() {
    const r = await this.device.controlTransferIn(
      { requestType: "standard", recipient: "device", request: 6, value: 0x0200, index: 0 }, 1024);
    const b = new Uint8Array(r.data.buffer, r.data.byteOffset, r.data.byteLength);
    const out = { alts: [], transferSize: 0 };
    for (let i = 0; i + 1 < b.length && b[i] > 0; i += b[i]) {
      if (b[i + 1] === 4) {
        out.alts.push({ number: b[i + 2], alt: b[i + 3], cls: b[i + 5], subclass: b[i + 6], iInterface: b[i + 8] });
      } else if (b[i + 1] === 0x21) {
        out.transferSize = u16(b, i + 5);
      }
    }
    return out;
  }

  async _string(index) {
    if (!index) return "";
    const r = await this.device.controlTransferIn(
      { requestType: "standard", recipient: "device", request: 6, value: 0x0300 | index, index: 0x0409 }, 255);
    const b = new Uint8Array(r.data.buffer, r.data.byteOffset, r.data.byteLength);
    let s = "";
    for (let i = 2; i + 1 < b[0] && i + 1 < b.length; i += 2) s += String.fromCharCode(u16(b, i));
    return s;
  }

  _out(request, value, data) {
    return this.device.controlTransferOut(
      { requestType: "class", recipient: "interface", request, value, index: this.iface }, data || new Uint8Array(0));
  }

  async _in(request, value, length) {
    const r = await this.device.controlTransferIn(
      { requestType: "class", recipient: "interface", request, value, index: this.iface }, length);
    if (r.status !== "ok") throw new UpdateError(`the bootloader refused request ${request} (${r.status})`);
    return new Uint8Array(r.data.buffer, r.data.byteOffset, r.data.byteLength);
  }

  async status() {
    const b = await this._in(GETSTATUS, 0, 6);
    return { status: b[0], poll: b[1] | (b[2] << 8) | (b[3] << 16), state: b[4] };
  }

  async toIdle() {
    let s = await this.status();
    if (s.state === S.ERROR) { await this._out(CLRSTATUS, 0); s = await this.status(); }
    if (s.state !== S.IDLE) { await this._out(ABORT, 0); s = await this.status(); }
    if (s.state !== S.IDLE) throw new UpdateError(`the bootloader will not get ready (state ${s.state})`);
  }

  // After a download request: wait while it is busy, and check it went well
  async _settle(what) {
    for (;;) {
      const s = await this.status();
      if (s.status !== 0) throw new UpdateError(`${what} failed (DFU status ${s.status})`);
      if (s.state !== S.DNBUSY) return s;
      await sleep(s.poll);
    }
  }

  async _special(code, address, what) {
    const b = new Uint8Array([code, address & 0xff, (address >> 8) & 0xff, (address >> 16) & 0xff, (address >>> 24) & 0xff]);
    await this._out(DNLOAD, 0, b);
    const s = await this._settle(what);
    if (s.state !== S.DNLOAD_IDLE) throw new UpdateError(`${what}: unexpected state ${s.state}`);
  }

  // The flash pages an image at address covers, from the memory map
  pagesFor(address, length) {
    const pages = [];
    for (const seg of this.map) {
      for (let p = 0; p < seg.pages; p++) {
        const start = seg.start + p * seg.pageSize;
        if (start + seg.pageSize > address && start < address + length) {
          if (!seg.erasable || !seg.writable) throw new UpdateError(`the flash at 0x${start.toString(16)} cannot be written`);
          pages.push(start);
        }
      }
    }
    return pages;
  }

  async download(address, payload, progress) {
    await this.toIdle();
    const pages = this.pagesFor(address, payload.length);
    const blocks = Math.ceil(payload.length / this.transferSize);
    const total = pages.length + blocks;
    let done = 0;
    this.log(`Erasing ${pages.length} pages`);
    for (const page of pages) {
      await this._special(0x41, page, `erasing 0x${page.toString(16)}`);
      if (progress) progress(++done, total, "erase");
    }
    this.log(`Writing ${payload.length} bytes`);
    for (let n = 0; n < blocks; n++) {
      const at = address + n * this.transferSize;
      await this._special(0x21, at, "setting the address");
      await this._out(DNLOAD, 2, payload.slice(n * this.transferSize, (n + 1) * this.transferSize));
      await this._settle(`writing 0x${at.toString(16)}`);
      if (progress) progress(++done, total, "write");
    }
  }

  async upload(address, length, progress) {
    await this.toIdle();
    await this._special(0x21, address, "setting the address");
    await this.toIdle();
    const out = new Uint8Array(length);
    const blocks = Math.ceil(length / this.transferSize);
    for (let n = 0; n < blocks; n++) {
      const b = await this._in(UPLOAD, 2 + n, this.transferSize);
      out.set(b.slice(0, Math.min(b.length, length - n * this.transferSize)), n * this.transferSize);
      if (progress) progress(n + 1, blocks, "verify");
    }
    return out;
  }

  // Start the firmware: a DfuSe leave, a zero length download then a status
  // request, the way dfu-util's ":leave" does it after reading. The pedal
  // goes off the bus, so an error here is the expected end.
  async leave(address) {
    try {
      await this.toIdle();
      await this._special(0x21, address, "setting the address");
      await this._out(DNLOAD, 2, new Uint8Array(0));
      await this.status();
    } catch (e) {
      /* the device reset */
    }
  }
}

// Flash payload on a device in DFU mode: erase, write, read it all back, leave.
export async function flash(device, payload, { log = () => {}, progress } = {}) {
  const dfu = new Dfu(device, log);
  await dfu.open();
  try {
    await dfu.download(APP_ADDRESS, payload, progress);
    log("Reading it back");
    const back = await dfu.upload(APP_ADDRESS, payload.length, progress);
    const bad = back.findIndex((b, i) => b !== payload[i]);
    if (bad >= 0) {
      throw new UpdateError(`the image does not read back as written (byte ${bad}). The pedal stays in DFU mode, so this can be run again.`);
    }
    log("Written and checked; starting the pedal");
    await dfu.leave(APP_ADDRESS);
  } finally {
    await dfu.close();
  }
}
