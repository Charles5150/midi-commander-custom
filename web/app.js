// The web configurator: edit a configuration, read and write the pedal's
// slots, watch and play the pedal, and update its firmware. The editors are
// built from python/lib/configSchema.py, packing is python/lib (see py.js).

import { Tools } from "./py.js";
import { Pedal, Timeout, SWITCHES, LED_LEVELS, SCREEN_WIDTH, SCREEN_HEIGHT, versionAtLeast, isIOS, noWebMidi, SelfTestTally, selfTestLeds } from "./pedal.js";
import { loadImage, flash, Dfu, DFU_FILTER, UpdateError } from "./dfu.js";
import { Simulator } from "./sim.js";
import { shareLink, linkedCsv } from "./share.js";

const $ = (sel, root = document) => root.querySelector(sel);

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else if (k === "value") el.value = v;
    else if (k === "checked") el.checked = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) el.append(c.nodeType ? c : String(c));
  return el;
}

const state = {
  tools: null,
  schema: null,
  config: null,        // sections: {name: {columns, rows}}
  fileName: "",
  dirty: false,
  edits: 0,            // counts the changes, so a write knows if more came while it ran
  bank: 0,
  button: "1",
  press: "Short",
  tab: "banks",
  pedal: null,
  version: "",
  slots: null,         // {target, active, valid}
  midiAccess: null,
  sim: null,           // the simulated pedal (sim.js), once started
  simulated: false,    // state.pedal is the simulated one
  monitor: [],         // what the pedal sent, newest last: {port, msg}
  showClock: false,
  dfuPayload: null,
  dfuName: "",
  busy: false,
  deviceChosen: {},    // {channel: device} picked from the dictionary in this session
  communityUsed: [],   // the community devices picked in this session, for the menus
  toolsError: "",      // why the configurator's Python did not load
  expHeld: [null, null],   // what Live holds each expression pedal at, null: let go
  expPedal: null,      // the pedal expHeld is about
  updateStuck: false,  // the last update failed with the pedal in its update mode
  stageList: 0,        // the setlist the Stage view follows, 0: as the pedal goes
};

// --- Messages -----------------------------------------------------------------
// An error stays until closed, read or not; the rest go after a few seconds
function toast(text, kind = "info") {
  const error = kind === "error";
  const el = h("div", { class: `toast ${kind}`, role: error ? "alert" : null }, h("span", {}, text),
    error ? h("button", { class: "close", "aria-label": "Close", onclick: () => el.remove() }, "×") : null);
  $("#toasts").append(el);
  if (!error) setTimeout(() => el.remove(), 4500);
}

// What went wrong and what to do about it, there until closed: for the
// messages too long to read in a toast
function notice(title, ...body) {
  const box = $("#notice");
  box.replaceChildren(h("strong", {}, title), ...body.map((b) => (typeof b === "string" ? h("p", {}, b) : b)),
    h("button", { class: "close", "aria-label": "Close", onclick: () => { box.hidden = true; } }, "×"));
  box.hidden = false;
}

function setBusy(text, done = null, total = null) {
  const bar = $("#busy");
  if (text === null) {
    bar.hidden = true;
    state.busy = false;
    renderToolbar();
    return;
  }
  state.busy = true;
  bar.hidden = false;
  $("#busy-text").textContent = text;
  const p = $("#busy-progress");
  if (total) { p.max = total; p.value = done; p.hidden = false; } else p.hidden = true;
  renderToolbar();
}

function download(name, text, type = "text/csv") {
  // On iOS a download may go nowhere in an app's browser: the share sheet saves to Files
  if (isIOS() && navigator.share && navigator.canShare) {
    const file = new File([text], name, { type });
    if (navigator.canShare({ files: [file] })) {
      navigator.share({ files: [file] }).catch(() => {});
      return;
    }
  }
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = h("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Where the focus is, as the child positions down from body, so it can go back
// to the same place once that part of the page is drawn again
function focusPath() {
  const path = [];
  for (let el = document.activeElement; el && el !== document.body; el = el.parentElement) {
    if (!el.parentElement) return null;
    path.unshift([...el.parentElement.children].indexOf(el));
  }
  return path.length ? path : null;
}

function keepingFocus(draw) {
  const path = focusPath();
  draw();
  if (!path || (document.activeElement && document.activeElement !== document.body)) return;
  let el = document.body;
  for (const i of path) { if (!el.children[i]) break; el = el.children[i]; }
  const focusable = "button, input, select, textarea, summary, a[href]";
  const target = el.matches(focusable) ? el : el.querySelector(focusable);
  if (target) target.focus();
}

// A name for a field's control where no label holds it
function named(ctl, name) {
  const el = ctl.matches("input, select") ? ctl : ctl.querySelector(":scope > input, :scope > select");
  if (el) el.setAttribute("aria-label", name);
  return ctl;
}

function confirmDialog(title, body, ok = "Continue") {
  return new Promise((resolve) => {
    const dlg = h("dialog", { class: "dialog" },
      h("h3", {}, title),
      ...(Array.isArray(body) ? body : [body]).map((p) => (p.nodeType ? p : h("p", {}, p))),
      h("div", { class: "dialog-buttons" },
        h("button", { onclick: () => { dlg.close(); resolve(false); } }, "Cancel"),
        h("button", { class: "primary", onclick: () => { dlg.close(); resolve(true); } }, ok)));
    dlg.addEventListener("close", () => { dlg.remove(); resolve(false); });
    document.body.append(dlg);
    dlg.showModal();
  });
}

// --- The configuration ----------------------------------------------------------
const section = (name) => state.config && state.config[name];
const int = (v) => { const n = parseInt(String(v).trim(), 10); return Number.isNaN(n) ? null : n; };
const yes = (v) => /^y/i.test(String(v || "").trim());

function col(sec, name) {
  let i = sec.columns.indexOf(name);
  if (i < 0) {
    sec.columns.push(name);
    sec.rows.forEach((r) => r.push(""));
    i = sec.columns.length - 1;
  }
  return i;
}

function cell(sec, row, name) {
  const i = sec.columns.indexOf(name);
  return i < 0 || !row ? "" : row[i] ?? "";
}

function setCell(sec, row, name, value) {
  const i = col(sec, name);
  if (row[i] !== value) {
    row[i] = value;
    changed();
  }
}

function commandColumns() {
  return state.schema.slots.flatMap((s) => state.schema.cmdFields.map((f) => `${s}_${f}`));
}

// The row of a section whose key columns hold keys, made when missing
function rowOf(name, keys, make = true) {
  let sec = section(name);
  if (!sec) {
    if (!make) return null;
    sec = state.config[name] = { columns: [...Object.keys(keys), ...commandColumns()], rows: [] };
  }
  const idx = Object.keys(keys).map((k) => sec.columns.indexOf(k));
  const same = (a, b) => (int(a) !== null && int(b) !== null ? int(a) === int(b) : String(a).trim().toUpperCase() === String(b).trim().toUpperCase());
  let row = sec.rows.find((r) => idx.every((i, n) => i >= 0 && same(r[i], Object.values(keys)[n])));
  if (!row && make) {
    row = sec.columns.map(() => "");
    Object.entries(keys).forEach(([k, v]) => { row[col(sec, k)] = String(v); });
    sec.rows.push(row);
  }
  return row ? { sec, row } : null;
}

function globalValue(label) {
  const sec = section("Global_Settings");
  const row = sec && sec.rows.find((r) => r[0] === label);
  return row ? row[1] : "";
}

function configName() {
  return globalValue("ConfigName").trim() || "configuration";
}

let checkTimer = null;
function changed() {
  state.dirty = true;
  state.edits++;
  renderToolbar();
  clearTimeout(checkTimer);
  checkTimer = setTimeout(checkConfig, 350);
}

function checkConfig() {
  if (!state.config) return "";
  const problem = state.tools.check(state.config);
  const box = $("#problem");
  box.hidden = !problem;
  box.textContent = problem ? `Needs fixing before it can be saved or written: ${problem}` : "";
  return problem;
}

function setConfig(sections, fileName) {
  state.config = sections;
  state.fileName = fileName;
  state.dirty = false;
  state.bank = 0;
  state.button = "1";
  state.press = "Short";
  state.deviceChosen = {};
  if (state.tab === "welcome") state.tab = "banks";
  render();
  checkConfig();
}

async function confirmDiscard() {
  if (!state.dirty) return true;
  return confirmDialog("Discard the changes?", "The configuration open has changes that were not saved or written to the pedal.", "Discard");
}

// --- Fields ------------------------------------------------------------------
// One editor for a field spec (see configSchema.py). get() gives the stored
// text, set(text) stores one.
function fieldControl(spec, get, set) {
  const v = get();
  switch (spec.kind) {
    case "int": {
      const input = h("input", { type: "number", min: spec.lo, max: spec.hi, value: v, class: "num" });
      input.addEventListener("change", () => {
        let t = input.value.trim();
        if (t !== "") {
          const n = Math.max(spec.lo, Math.min(spec.hi, parseInt(t, 10)));
          t = Number.isNaN(n) ? "" : String(n);
          input.value = t;
        }
        set(t);
      });
      return input;
    }
    case "choice": {
      const shown = spec.options.includes(v) ? v : (v === "" && spec.blank !== undefined ? spec.blank : spec.options.find((o) => o.toLowerCase() === String(v).toLowerCase()) ?? spec.options[0]);
      const sel = h("select", {}, spec.options.map((o) => h("option", { value: o }, o === "" ? "—" : o)));
      sel.value = shown;
      sel.addEventListener("change", () => set(sel.value === spec.blank ? "" : sel.value));
      return sel;
    }
    case "check": {
      const box = h("input", { type: "checkbox", checked: yes(v) });
      box.addEventListener("change", () => set(box.checked ? "Y" : (spec.off !== undefined ? spec.off : "N")));
      return box;
    }
    case "combo": {
      const id = `list-${Math.random().toString(36).slice(2)}`;
      const input = h("input", { list: id, value: v, class: "short" });
      input.addEventListener("change", () => set(input.value.trim()));
      return h("span", {}, input, h("datalist", { id }, spec.options.map((o) => h("option", { value: o }))));
    }
    case "modifiers": {
      const mask = int(v) || 0;
      return h("span", { class: "inline" }, spec.options.map(([name, bit]) => {
        const box = h("input", { type: "checkbox", checked: Boolean(mask & bit) });
        box.addEventListener("change", () => {
          const m = int(get()) || 0;
          set(String(box.checked ? m | bit : m & ~bit));
        });
        return h("label", { class: "check" }, box, name);
      }));
    }
    case "scene": {
      const text = String(v);
      const names = { "+": "On", "-": "Off" };
      const code = { On: "+", Off: "-" };
      return h("span", { class: "inline" }, spec.options.map((b, i) => {
        const sel = h("select", {}, ["-", "On", "Off"].map((o) => h("option", { value: o }, o)));
        sel.value = names[text[i]] || "-";
        sel.addEventListener("change", () => {
          const cur = String(get()).padEnd(8, ".").split("");
          cur[i] = code[sel.value] || ".";
          set(cur.join(""));
        });
        return h("label", { class: "scene" }, b, sel);
      }));
    }
    case "button_mode": {
      // Button's KeyMode: an action, then the list when not the short one
      const words = String(v).trim().split(/\s+/).filter(Boolean);
      let list = spec.lists[0];
      if (words.length && spec.lists.slice(1).includes(words[words.length - 1])) list = words.pop();
      const action = spec.actions.includes(words.join(" ")) ? words.join(" ") : spec.actions[0];
      const lsel = h("select", { "aria-label": `${spec.label || "Mode"}: list` }, spec.lists.map((o) => h("option", { value: o }, o)));
      const asel = h("select", { "aria-label": `${spec.label || "Mode"}: action` }, spec.actions.map((o) => h("option", { value: o }, o)));
      lsel.value = list;
      asel.value = action;
      const store = () => {
        const mode = asel.value + (lsel.value === spec.lists[0] ? "" : ` ${lsel.value}`);
        set(mode === spec.actions[0] ? "" : mode);
      };
      lsel.addEventListener("change", store);
      asel.addEventListener("change", store);
      return h("span", { class: "inline" }, lsel, asel);
    }
    default: {
      const input = h("input", { value: v, maxlength: spec.max || 64, class: spec.max && spec.max <= 8 ? "short" : "" });
      input.addEventListener("change", () => {
        const t = spec.display ? state.tools.shown(input.value, spec.max || 64) : input.value;
        input.value = t;
        set(t);
      });
      return input;
    }
  }
}

function labelled(label, control, hint) {
  return h("label", { class: "field" }, h("span", { class: "field-label" }, label), control, hint ? h("span", { class: "hint" }, hint) : null);
}

// --- Command lists -----------------------------------------------------------
// The ten commands A-J of a row, each its type and the fields that type shows
function commandList(sec, row, types) {
  const { slots, cmdFields, commandSpecs, noCommand } = state.schema;
  const wrap = h("div", { class: "commands" });
  const draw = () => keepingFocus(() => {
    wrap.replaceChildren();
    let last = slots.length - 1;
    while (last > 0 && !cell(sec, row, `${slots[last]}_CommandType`)) last--;
    const shownCount = Math.min(slots.length, Math.max(last + 2, 3));
    slots.slice(0, shownCount).forEach((slot) => wrap.append(commandRow(sec, row, slot, types, draw)));
    if (shownCount < slots.length) wrap.append(h("div", { class: "hint" }, `${slots.length - shownCount} more below, as the ones above fill`));
  });
  draw();
  return wrap;
}

// --- Device dictionary -----------------------------------------------------------
// Which device is on each channel: what the commands point to, or what was
// picked; worked out again after a change
let deviceCache = { edits: -1, config: null, map: {} };
function deviceMap() {
  if (deviceCache.edits !== state.edits || deviceCache.config !== state.config) {
    let map = {};
    try {
      map = state.tools.deviceGuess(state.config, state.deviceChosen);
    } catch (e) { /* a configuration that does not read yet names nothing */ }
    deviceCache = { edits: state.edits, config: state.config, map };
  }
  return deviceCache.map;
}

// The channel a command goes out on: the Global channel, when set, carries them all
function sentChannel(text) {
  return int(globalValue("Global_Channel")) || int(text) || 1;
}

const NAMED_TYPES = ["CC", "PC", "Note"];

// "HX Stomp: FS4" for a command, or ""
function deviceText(type, get) {
  if (!NAMED_TYPES.includes(type)) return "";
  const device = deviceMap()[sentChannel(get("Channel_(PC/CC/Note/PB)"))];
  const name = device ? state.tools.deviceName(device, type, get("Number_(PC/CC/Note)"), get("OnValue_(CC/PB)"), get("Toggle_(CC/PB/Note)")) : "";
  return name ? `${device}: ${name}` : "";
}

// A menu of every device's commands; filled when opened, the device on this
// channel first. The community devices are too many for it: "More devices…"
// finds one by name, and the ones picked join the menu
function devicePicker(types, channel, pick, label) {
  const sel = h("select", { class: "device", title: "Fill this command from a device's MIDI map", "aria-label": label }, h("option", { value: "" }, "Device…"));
  let shown = [];
  const fill = () => {
    if (sel.options.length > 1) return;
    const devices = state.tools.devices().concat(state.communityUsed);
    const here = deviceMap()[channel()];
    shown = devices.slice().sort((a, b) => (b.name === here) - (a.name === here));
    shown.forEach((d, di) => {
      const opts = d.commands.map((e, ci) => [e, ci]).filter(([e]) => types.includes(e.fields.CommandType));
      if (opts.length) sel.append(h("optgroup", { label: d.community ? `${d.name} (OpenMIDI)` : `${d.maker} ${d.name}` }, opts.map(([e, ci]) => h("option", { value: `${di}:${ci}` }, e.name))));
    });
    sel.append(h("option", { value: "more" }, "More devices…"));
  };
  sel.addEventListener("focus", fill);
  sel.addEventListener("mousedown", fill);
  sel.addEventListener("change", async () => {
    const value = sel.value;
    sel.value = "";
    if (!value) return;
    if (value === "more") {
      const found = await findCommunityCommand(types);
      if (!found) return;
      if (!state.communityUsed.includes(found.device)) state.communityUsed.push(found.device);
      sel.replaceChildren(h("option", { value: "" }, "Device…"));
      pick(found.device, found.command);
      return;
    }
    const [di, ci] = value.split(":").map(Number);
    pick(shown[di], shown[di].commands[ci]);
  });
  return sel;
}

// The community devices (OpenMIDI): a search by maker and model, then the
// device's commands; {device, command} or null
async function findCommunityCommand(types) {
  let devices;
  try {
    devices = await state.tools.communityDevices();
  } catch (e) {
    toast(`Cannot load the community devices: ${e.message}. Check the internet connection and try again.`, "error");
    return null;
  }
  const search = h("input", { type: "search", placeholder: "Maker or model", "aria-label": "Search devices" });
  const list = h("select", { size: 10, class: "community-devices", "aria-label": "Devices" });
  const commands = h("select", { "aria-label": "Command" });
  let matches = [];
  const showCommands = () => {
    const d = matches[list.selectedIndex];
    const opts = d ? d.commands.map((e, ci) => [e, ci]).filter(([e]) => types.includes(e.fields.CommandType)) : [];
    commands.replaceChildren(...opts.map(([e, ci]) => h("option", { value: ci }, e.name)));
  };
  const filter = () => {
    const words = search.value.toLowerCase().split(/\s+/).filter(Boolean);
    matches = devices.filter((d) => words.every((w) => d.name.toLowerCase().includes(w)));
    list.replaceChildren(...matches.map((d) => h("option", {}, d.name)));
    if (matches.length) list.selectedIndex = 0;
    showCommands();
  };
  search.addEventListener("input", filter);
  list.addEventListener("change", showCommands);
  filter();
  const body = [labelled("Search", search), list, labelled("Command", commands),
    h("p", { class: "hint" }, `${devices.length} devices from OpenMIDI, written down by its community and not checked here: check the numbers and values against the device's manual.`)];
  if (!(await confirmDialog("More devices", body, "Fill"))) return null;
  const device = matches[list.selectedIndex];
  if (!device || commands.value === "") return null;
  return { device, command: device.commands[Number(commands.value)] };
}

function commandRow(sec, row, slot, types, redraw) {
  const { cmdFields, commandSpecs, noCommand } = state.schema;
  const get = (f) => cell(sec, row, `${slot}_${f}`);
  let type = get("CommandType").trim();
  const known = types.find((t) => t.toLowerCase() === type.toLowerCase());
  type = type ? known || type : noCommand;
  const spec = commandSpecs[type] || { fields: [] };
  const visible = (f) => !f.when || Object.entries(f.when).every(([c, vals]) => {
    const cur = get(c);
    const fs = spec.fields.find((x) => x.col === c);
    const shown = fs && fs.kind === "choice" ? (fs.options.includes(cur) ? cur : (cur === "" && fs.blank !== undefined ? fs.blank : fs.options[0])) : cur;
    return vals.includes(shown);
  });

  // What the desktop editor writes: the fields shown, empty for the rest
  const store = (newType, values) => {
    const s = commandSpecs[newType] || { fields: [] };
    const out = Object.fromEntries(cmdFields.map((f) => [f, ""]));
    out["Toggle_(CC/PB/Note)"] = "N";
    out.CommandType = newType === noCommand ? "" : newType;
    const cur = (c) => (c in values ? values[c] : get(c));
    for (const f of s.fields) {
      const whenOk = !f.when || Object.entries(f.when).every(([c, vals]) => {
        const fs = s.fields.find((x) => x.col === c);
        let v = cur(c);
        if (fs && fs.kind === "choice") v = fs.options.includes(v) ? v : (v === "" && fs.blank !== undefined ? fs.blank : fs.options[0]);
        return vals.includes(v);
      });
      if (!whenOk) continue;
      let v = cur(f.col);
      if (f.kind === "choice" && !(v === "" && f.blank !== undefined) && !f.options.includes(v)) {
        v = f.options.find((o) => o.toLowerCase() === String(v).toLowerCase()) ?? (f.default ?? f.options[0]);
        if (v === f.blank) v = "";
      }
      if (v === "" && f.default !== undefined && f.kind !== "choice") v = f.default;
      out[f.col] = v;
    }
    for (const f of cmdFields) setCell(sec, row, `${slot}_${f}`, out[f]);
  };

  const typeSel = h("select", { class: "type", "aria-label": `Command ${slot}: type` }, (types.includes(type) ? types : [...types, type]).map((t) => h("option", { value: t }, t)));
  typeSel.value = type;
  typeSel.addEventListener("change", () => {
    const t = typeSel.value;
    const s = commandSpecs[t] || { fields: [] };
    const fresh = {};
    for (const f of s.fields) {
      if (f.kind === "choice") fresh[f.col] = f.default ?? (f.blank !== undefined ? "" : f.options[0]);
      else fresh[f.col] = f.default ?? (f.kind === "check" ? "N" : "");
      if (t === type && get(f.col) !== "") delete fresh[f.col];
    }
    store(t, fresh);
    redraw();
  });

  // From the dictionary: the type, number and values; the channel stays, or
  // on a new command is the one the device is already on
  const picker = types.some((t) => NAMED_TYPES.includes(t)) ? devicePicker(types, () => sentChannel(get("Channel_(PC/CC/Note/PB)")), (d, e) => {
    const values = { ...e.fields };
    if (!NAMED_TYPES.includes(type)) {
      const known = Object.entries(deviceMap()).find(([, name]) => name === d.name);
      values["Channel_(PC/CC/Note/PB)"] = known ? known[0] : get("Channel_(PC/CC/Note/PB)") || "1";
    }
    if (values.CommandType === "PC" && type !== "PC") values["Number_(PC/CC/Note)"] = "0";
    const ch = sentChannel(values["Channel_(PC/CC/Note/PB)"] ?? get("Channel_(PC/CC/Note/PB)"));
    state.deviceChosen[ch] = d.name;
    deviceCache.edits = -1;
    store(values.CommandType, values);
    redraw();
  }, `Command ${slot}: fill from a device`) : null;

  const nameHint = h("span", { class: "hint device-name" });
  const showName = () => { nameHint.textContent = deviceText(type, get); };
  const params = h("div", { class: "params" });
  for (const f of spec.fields) {
    if (!visible(f)) continue;
    const ctl = fieldControl(f, () => get(f.col), (v) => {
      store(type, { [f.col]: v });
      if (spec.fields.some((x) => x.when && f.col in x.when) || spec.hint_by === f.col) redraw();
      else showName();
    });
    params.append(f.kind === "check" ? h("label", { class: "check" }, ctl, f.label) : labelled(f.label, ctl));
  }
  let hint = spec.hint || "";
  if (spec.hint_by) {
    const f = spec.fields.find((x) => x.col === spec.hint_by);
    let v = get(spec.hint_by);
    if (f && f.kind === "choice") v = f.options.includes(v) ? v : (v === "" && f.blank !== undefined ? f.blank : f.options[0]);
    hint = (spec.hints || {})[v] ?? hint;
  }
  if (hint) params.append(h("span", { class: "hint" }, hint));
  showName();
  params.append(nameHint);
  return h("div", { class: `command${type === noCommand ? " empty" : ""}` }, h("span", { class: "slot" }, slot), typeSel, picker, params);
}

function summary(sec, row) {
  if (!row) return "";
  const t = cell(sec, row, "A_CommandType");
  if (!t) return "";
  const n = cell(sec, row, "A_Number_(PC/CC/Note)");
  const on = cell(sec, row, "A_OnValue_(CC/PB)");
  const mode = cell(sec, row, "A_KeyMode_(Key)");
  const more = state.schema.slots.slice(1).filter((s) => cell(sec, row, `${s}_CommandType`)).length;
  const main = { PC: n, CC: n, Note: n, CCInc: n, Listen: n, Bank: `${mode} ${on}`.trim(), Tap: mode, Key: on, Media: on, Wait: mode, MMC: mode }[t] ?? "";
  return `${t} ${main}`.trim() + (more ? ` +${more}` : "");
}

// --- Toolbar and tabs -------------------------------------------------------
const TABS = [
  ["banks", "Banks"], ["global", "Global"], ["expression", "Expression"], ["bankswitch", "Bank switches"],
  ["sysex", "SysEx"], ["setlist", "Setlist"], ["combos", "Combos"], ["midimap", "MIDI map"], ["presets", "Preset names"],
  ["live", "Live pedal"], ["stage", "Stage"],
  ["firmware", "Firmware"],
];

function renderToolbar() {
  keepingFocus(drawToolbar);
}

function drawToolbar() {
  const conn = $("#connection");
  conn.replaceChildren();
  if (state.pedal) {
    const slot = state.slots && !state.slots.single ? ` · running slot ${state.slots.active + 1}` : "";
    conn.append(h("span", { class: state.simulated ? "pill ok sim" : "pill ok" },
      `${state.simulated ? "Simulated pedal" : "Midi Commander"} ${state.version}${slot}`));
    if (state.simulated) conn.append(h("button", { disabled: state.busy, onclick: stopSimulation, title: "Stop the simulated pedal; what was written to it stays for next time" }, "Stop"));
  } else if (state.simulated) {
    conn.append(h("span", { class: "pill sim" }, "Simulated pedal restarting…"));
  } else {
    conn.append(h("button", { class: "primary", disabled: state.busy, onclick: connect }, "Connect the pedal"));
    conn.append(h("button", { disabled: state.busy, onclick: simulate, title: "The pedal's own firmware, running in this page" }, "Try without a pedal"));
  }
  const name = $("#config-name");
  name.textContent = state.config ? configName() + (state.dirty ? " • changed" : "") : "No configuration open";
  $("#btn-save").disabled = !state.config || state.busy;
  $("#btn-print").disabled = !state.config || state.busy;
  $("#btn-share").disabled = !state.config || state.busy;
  $("#btn-write").disabled = !state.config || !state.pedal || state.busy;
  $("#btn-read").disabled = !state.pedal || state.busy || !state.tools;
  $("#btn-backup").disabled = !state.pedal || state.busy || !state.tools;
  $("#btn-open").disabled = !state.tools || state.busy;
  $("#btn-demo").disabled = !state.tools || state.busy;
  $("#btn-template").disabled = !state.tools || state.busy;
  // The start page's own buttons, as the toolbar's
  const start = { "start-read": $("#btn-read").disabled, "start-open": $("#btn-open").disabled, "start-demo": $("#btn-demo").disabled, "start-template": $("#btn-template").disabled };
  for (const [id, off] of Object.entries(start)) { const b = document.getElementById(id); if (b) b.disabled = off; }
}

function render() {
  keepingFocus(draw);
}

function draw() {
  drawToolbar();
  const nav = $("#tabs");
  nav.replaceChildren(...TABS.map(([id, label]) => h("button", {
    class: state.tab === id ? "tab active" : "tab",
    "aria-current": state.tab === id ? "page" : null,
    onclick: () => { state.tab = id; render(); },
  }, label)));
  const main = $("#main");
  main.replaceChildren();
  const needsConfig = !["live", "stage", "firmware"].includes(state.tab);
  if (needsConfig && !state.config) {
    main.append(welcome());
    return;
  }
  ({
    banks: renderBanks, global: renderGlobal, expression: renderExpression, bankswitch: renderBankSwitch,
    sysex: renderSysex, setlist: renderSetlist, combos: renderCombos, midimap: renderMidiMap, presets: renderPresetNames, live: renderLive,
    stage: renderStage, firmware: renderFirmware,
  })[state.tab](main);
  if (!["live", "stage"].includes(state.tab)) stopLive();
}

function welcome() {
  return h("section", { class: "welcome" },
    h("h2", {}, "Configure your Midi Commander in the browser"),
    h("p", {}, "Nothing to install. Connect the pedal to read its configuration, open a CSV file made with the configurator, or start from the demo or from the devices on your board."),
    state.toolsError ? toolsFailed() : state.tools ? null : h("p", { class: "hint" }, "Loading the configurator’s Python… the first time takes a few seconds."),
    h("div", { class: "buttons" },
      h("button", { id: "start-read", class: "primary", disabled: !state.pedal || !state.tools || state.busy, onclick: readFromPedal }, "Read from the pedal"),
      h("button", { id: "start-open", disabled: !state.tools || state.busy, onclick: openFile }, "Open a CSV file"),
      h("button", { id: "start-demo", disabled: !state.tools || state.busy, onclick: openDemo }, "Open the demo"),
      h("button", { id: "start-template", disabled: !state.tools || state.busy, onclick: openTemplate }, "Start from your devices")),
    h("p", { class: "hint" }, "No pedal at hand? Try without a pedal: the pedal’s own firmware runs in the page, with the demo in it, and everything here works on it as on the real one."),
    h("p", { class: "hint" }, "Chrome, Edge or Opera on a computer: they have Web MIDI and WebUSB. Firefox has Web MIDI, through a site permission add-on it offers when you connect, but no WebUSB, so no firmware update. The page asks to use MIDI devices with SysEx when you connect."));
}

function toolsFailed() {
  return h("div", { class: "problem card" },
    h("strong", {}, "The configurator’s Python could not load"),
    h("p", {}, `${state.toolsError}. It comes from cdn.jsdelivr.net: check the internet connection, or whether a blocker or a company network stops that site, then reload the page. Without it a configuration cannot be opened, read or written; Live pedal and Firmware still work.`),
    h("button", { onclick: () => location.reload() }, "Reload the page"));
}

// --- Banks -------------------------------------------------------------------
function bankName(b) {
  const r = rowOf("Bank_Naming", { Bank_Number: b }, false);
  return r ? cell(r.sec, r.row, "Bank_Name_Large").trim() : "";
}

// A bank's note for the Stage view: in the CSV only, never on the pedal, one
// line there, with \n for a line break and \\ for a backslash
function bankNote(b) {
  const r = rowOf("Bank_Naming", { Bank_Number: b }, false);
  const text = r ? cell(r.sec, r.row, "Notes") : "";
  return text.replace(/\\(n|\\)/g, (_, c) => (c === "n" ? "\n" : "\\"));
}

function setBankNote(b, text) {
  const r = rowOf("Bank_Naming", { Bank_Number: b });
  const stored = text.replace(/\r\n?/g, "\n").trimEnd().replace(/\\/g, "\\\\").replace(/\n/g, "\\n");
  if (stored || cell(r.sec, r.row, "Notes")) setCell(r.sec, r.row, "Notes", stored);
}

function renderBanks(main) {
  const { numBanks, buttonIds, shortCommandTypes, commandTypes, enterCommandTypes, buttonFields } = state.schema;
  const list = h("nav", { class: "bank-list" }, [...Array(numBanks)].map((_, b) => h("button", {
    class: b === state.bank ? "active" : "",
    "aria-current": b === state.bank ? "true" : null,
    onclick: () => { state.bank = b; render(); },
  }, h("span", { class: "num" }, b), bankName(b) || "—")));

  const naming = rowOf("Bank_Naming", { Bank_Number: state.bank });
  const head = h("div", { class: "bank-head" },
    h("h2", {}, `Bank ${state.bank}`),
    labelled("Name", fieldControl({ kind: "text", max: 4, display: true }, () => cell(naming.sec, naming.row, "Bank_Name_Large"),
      (v) => { setCell(naming.sec, naming.row, "Bank_Name_Large", v); $(".bank-list .active").lastChild.textContent = v || "—"; })),
    labelled("Info line", fieldControl({ kind: "text", max: 8, display: true }, () => cell(naming.sec, naming.row, "Bank_Info_Small"),
      (v) => setCell(naming.sec, naming.row, "Bank_Info_Small", v))),
    h("div", { class: "song-buttons" },
      h("button", { onclick: saveSong, title: "This bank and what it runs, as a file to load into a bank of any configuration" }, "Save song"),
      h("button", { onclick: loadSong, title: "Replace this bank with a song file" }, "Load song")));

  // The eight buttons as on the pedal: 1-4 on top, A-D underneath
  const btnSec = section("Button_Settings");
  const pedal = h("div", { class: "pedal-grid" }, buttonIds.map((id) => {
    const r = rowOf("Button_Settings", { Bank_Number: state.bank, Button_Identifier: id }, false);
    // On the Long press tab the labels a Reveal button shows
    const lr = state.press === "Long" ? rowOf("LongPress_Settings", { Bank_Number: state.bank, Button_Identifier: id }, false) : null;
    const label = state.press === "Long" ? (lr ? cell(lr.sec, lr.row, "Long_Label") : "") : r ? cell(r.sec, r.row, "Label") : "";
    return h("button", {
      class: `pedal-button${id === state.button ? " active" : ""}`,
      "aria-current": id === state.button ? "true" : null,
      onclick: () => { state.button = id; render(); },
    }, h("span", { class: "id" }, id), h("span", { class: "label" }, label || " "), h("span", { class: "sum" }, state.press === "Long" ? summary(lr && lr.sec, lr && lr.row) : summary(btnSec, r && r.row)));
  }));

  const presses = [["Short", "Press", "Button_Settings", shortCommandTypes], ["Long", "Long press", "LongPress_Settings", commandTypes], ["Double", "Double press", "DoublePress_Settings", commandTypes]];
  const pressTabs = h("div", { class: "subtabs" }, presses.map(([id, label]) => h("button", {
    class: state.press === id ? "active" : "", "aria-pressed": state.press === id ? "true" : "false", onclick: () => { state.press = id; render(); },
  }, label)));
  const [, , secName, types] = presses.find((p) => p[0] === state.press);
  const r = rowOf(secName, { Bank_Number: state.bank, Button_Identifier: state.button });
  const editor = h("section", { class: "card" }, h("h3", {}, `Button ${state.button}`), pressTabs);
  if (state.press === "Short") {
    const own = rowOf("Button_Settings", { Bank_Number: state.bank, Button_Identifier: state.button });
    editor.append(h("div", { class: "fields" }, buttonFields.map((f) => {
      const ctl = fieldControl(f, () => cell(own.sec, own.row, f.col), (v) => { setCell(own.sec, own.row, f.col, v); if (f.col === "Label") $(".pedal-button.active .label").textContent = v || " "; });
      return f.kind === "check" ? h("label", { class: "check" }, ctl, f.label) : labelled(f.label, ctl);
    })));
  }
  if (state.press === "Long") {
    editor.append(h("div", { class: "fields" }, labelled("Label", fieldControl({ kind: "text", max: 4, display: true }, () => cell(r.sec, r.row, "Long_Label"),
      (v) => { setCell(r.sec, r.row, "Long_Label", v); $(".pedal-button.active .label").textContent = v || " "; }))),
      h("p", { class: "hint" }, "Shown in place of the button's own label while a Bank command set to Reveal is held."));
  }
  editor.append(commandList(r.sec, r.row, types));

  const enter = rowOf("BankEnter_Settings", { Bank_Number: state.bank });
  const enterCard = h("details", { class: "card" }, h("summary", {}, "On entering this bank"),
    h("p", { class: "hint" }, "Sent every time the bank is entered; after a Leave, on leaving it."),
    commandList(enter.sec, enter.row, enterCommandTypes));

  const expCard = h("details", { class: "card" }, h("summary", {}, "Expression pedals in this bank"));
  const exp = rowOf("BankExpression_Settings", { Bank_Number: state.bank }, false);
  if (exp) {
    expCard.append(h("p", { class: "hint" }, "Empty: as set in the Expression tab. CC: a number, Off, Speed, Wheel or Arrows."),
      h("div", { class: "fields" }, state.schema.sectionColumns.BankExpression_Settings.map((f) =>
        labelled(f.label, fieldControl(f, () => cell(exp.sec, exp.row, f.col), (v) => setCell(exp.sec, exp.row, f.col, v))))));
  }

  const note = h("textarea", { rows: 4, "aria-label": `Notes for bank ${state.bank}`, placeholder: "Key, capo, cues, lyrics…" });
  note.value = bankNote(state.bank);
  note.addEventListener("change", () => setBankNote(state.bank, note.value));
  const noteCard = h("details", { class: "card", open: Boolean(note.value) }, h("summary", {}, "Notes for the Stage view"),
    h("p", { class: "hint" }, "Shown large in the Stage tab while the pedal is on this bank. Kept in the CSV file, and in a song file saved from this bank; the pedal never holds them, so reading from the pedal brings none."),
    note);

  main.append(h("div", { class: "banks" }, list, h("div", { class: "bank-main" }, head, pedal, editor, noteCard, enterCard, exp ? expCard : null)));
}

// --- Global --------------------------------------------------------------------
function renderGlobal(main) {
  const sec = section("Global_Settings");
  const { globalGroups, globalFields } = state.schema;
  const known = new Set(globalGroups.flatMap(([, items]) => items.map(([l]) => l)));
  const rowFor = (label) => {
    let row = sec.rows.find((r) => r[0] === label);
    if (!row) { row = [label, ""]; sec.rows.push(row); }
    return row;
  };
  const present = new Set(sec.rows.map((r) => r[0]));
  const others = [...present].filter((l) => !known.has(l));
  const groups = [...globalGroups, ...(others.length ? [["Other", others.map((l) => [l, l, ""])]] : [])];
  main.append(h("div", { class: "global" }, groups.map(([group, items]) => h("section", { class: "card" },
    h("h3", {}, group),
    items.filter(([label]) => present.has(label) || group !== "Other").map(([label, name, hint]) => {
      const spec = globalFields[label] || { kind: "text", max: 64 };
      const row = present.has(label) ? rowFor(label) : null;
      const ctl = fieldControl(spec, () => (row ? row[1] : ""), (v) => { const r = rowFor(label); if (r[1] !== v) { r[1] = v; changed(); } });
      return h("div", { class: "setting" }, h("span", { class: "setting-name" }, name), named(ctl, name), h("span", { class: "hint" }, hint));
    }))), channelPortsCard()));
}

// The output each channel goes to; only the channels not on both are rows
function channelPortsCard() {
  const sec = section("Channel_Ports") || (state.config.Channel_Ports = { columns: [...state.schema.channelPortColumns], rows: [] });
  const rowFor = (ch) => sec.rows.find((row) => int(cell(sec, row, "Channel")) === ch);
  const set = (ch, v) => {
    const row = rowFor(ch);
    if (!v || v === "Both") {
      if (row) { sec.rows.splice(sec.rows.indexOf(row), 1); changed(); }
      return;
    }
    if (row) { setCell(sec, row, "Port", v); return; }
    const fresh = sec.columns.map(() => "");
    fresh[col(sec, "Channel")] = String(ch);
    fresh[col(sec, "Port")] = v;
    sec.rows.push(fresh);
    sec.rows.sort((a, b) => int(cell(sec, a, "Channel")) - int(cell(sec, b, "Channel")));
    changed();
  };
  const spec = { kind: "choice", options: state.schema.channelPorts, blank: "Both" };
  return h("section", { class: "card" },
    h("h3", {}, "Output by channel"),
    h("p", { class: "hint" }, "Where each channel's commands go when the configuration is written to the pedal: say once that channel 3 is the amp on DIN and channel 10 the computer on USB. Every PC, CC, note, bend, pressure, CCInc and PCInc on that channel gets a Chan above it with that output, unless it has a Chan of its own. The expression pedals, the MIDI map and the clock are not changed. Needs firmware 0.84."),
    h("div", { class: "presets" }, Array.from({ length: 16 }, (_, i) =>
      labelled(`Channel ${i + 1}`, fieldControl(spec, () => cell(sec, rowFor(i + 1), "Port"), (v) => set(i + 1, v))))));
}

// --- Expression ----------------------------------------------------------------
function renderExpression(main) {
  const sec = section("Expression_Settings");
  if (!sec) {
    main.append(h("p", {}, "This configuration has no expression pedal settings: the pedal uses its defaults."));
    return;
  }
  main.append(h("div", { class: "global" }, sec.rows.map((row) => h("section", { class: "card" },
    h("h3", {}, `Pedal ${cell(sec, row, "Pedal")}`),
    h("div", { class: "fields" }, state.schema.expressionFields.map((f) => {
      const ctl = fieldControl(f, () => cell(sec, row, f.col), (v) => setCell(sec, row, f.col, v));
      return f.kind === "check" ? h("label", { class: "check" }, ctl, f.label) : labelled(f.label, ctl);
    }))))));
}

// --- Bank switches -------------------------------------------------------------
function renderBankSwitch(main) {
  main.append(h("p", { class: "hint" }, "What Bank Down and Bank Up send when Bank switches (Global) is Bank+MIDI or MIDI only. With MIDI only, a label on the short press puts the switch on the screen, five cells to a row."));
  for (const [sw, press] of [["Down", "Short"], ["Down", "Long"], ["Up", "Short"], ["Up", "Long"]]) {
    const r = rowOf("BankSwitch_Settings", { Switch: sw, Press: press });
    const label = press === "Short"
      ? h("div", { class: "fields" }, labelled("Label", fieldControl({ kind: "text", max: 4, display: true },
        () => cell(r.sec, r.row, "Label"), (v) => setCell(r.sec, r.row, "Label", v))))
      : null;
    main.append(h("section", { class: "card" }, h("h3", {}, `Bank ${sw}, ${press.toLowerCase()} press`), label, commandList(r.sec, r.row, state.schema.commandTypes)));
  }
}

// --- Simple tables ---------------------------------------------------------------
function table(sec, keyCol, keyLabel, fields) {
  return h("table", { class: "grid" },
    h("thead", {}, h("tr", {}, h("th", {}, keyLabel), fields.map((f) => h("th", {}, f.label)))),
    h("tbody", {}, sec.rows.map((row) => h("tr", {}, h("td", { class: "key" }, cell(sec, row, keyCol)),
      fields.map((f) => h("td", {}, named(fieldControl(f, () => cell(sec, row, f.col), (v) => setCell(sec, row, f.col, v)), `${f.label}, ${keyLabel} ${cell(sec, row, keyCol)}`)))))));
}

function ensureRows(name, keyCol, count, extra = {}) {
  let sec = section(name);
  if (!sec) sec = state.config[name] = { columns: [keyCol, ...Object.keys(extra)], rows: [] };
  for (let i = sec.rows.length; i < count; i++) {
    const row = sec.columns.map(() => "");
    row[col(sec, keyCol)] = String(i + (keyCol === "Position" ? 1 : 0));
    sec.rows.push(row);
  }
  return sec;
}

function renderSysex(main) {
  const sec = ensureRows("SysEx_Strings", "Index", 16, { Bytes: "" });
  main.append(h("p", { class: "hint" }, "Up to 23 bytes each, in hex without F0 and F7, for example 41 10 42 12. VV is where a value goes, and CS, last, a Roland checksum. A SysEx command sends one by its number."),
    table(sec, "Index", "#", state.schema.sectionColumns.SysEx_Strings));
}

// The setlists of the Setlist section, {1..4: {name, banks}}: banks by
// position, "" where there is none. A row's List is 1 when empty.
function setlistsOf(sec) {
  const lists = {};
  for (let n = 1; n <= state.schema.setlistCount; n++) lists[n] = { name: "", banks: Array(state.schema.setlistMax).fill("") };
  for (const row of sec ? sec.rows : []) {
    const list = lists[Number(cell(sec, row, "List") || 1)];
    if (!list) continue;
    if (cell(sec, row, "Name")) list.name = cell(sec, row, "Name");
    const pos = Number(cell(sec, row, "Position")), bank = cell(sec, row, "Bank_Number");
    if (bank !== "" && pos >= 1 && pos <= state.schema.setlistMax) list.banks[pos - 1] = bank;
  }
  return lists;
}

// Back into the section, with List and Name only when they are used, as the
// tools write it
function writeSetlists(lists) {
  const used = Object.entries(lists);
  const several = used.some(([n, l]) => n !== "1" && l.banks.some((b) => b !== ""));
  const named = used.some(([, l]) => l.name);
  const columns = ["Position", "Bank_Number", ...(several || named ? ["List"] : []), ...(named ? ["Name"] : [])];
  const rows = [];
  for (const [n, l] of used) {
    const songs = l.banks.map((b, i) => [String(i + 1), b]).filter(([, b]) => b !== "");
    if (l.name && !songs.length) songs.push(["", ""]);
    songs.forEach(([pos, bank], i) => rows.push(columns.map((c) => ({ Position: pos, Bank_Number: bank, List: n, Name: i ? "" : l.name }[c]))));
  }
  state.config.Setlist = { columns, rows };
  changed();
}

function renderSetlist(main) {
  const lists = setlistsOf(section("Setlist"));
  const n = state.setlist || 1, list = lists[n];
  const spec = state.schema.sectionColumns.Setlist[0];
  const picks = h("div", { class: "subtabs" }, Object.keys(lists).map((k) => h("button", {
    class: String(n) === k ? "active" : "", "aria-pressed": String(n) === k ? "true" : "false",
    onclick: () => { state.setlist = Number(k); render(); },
  }, `Setlist ${k}`)));
  const name = h("input", { type: "text", maxlength: state.schema.setlistNameLen, value: list.name, "aria-label": `Name of setlist ${n}`, placeholder: "no name" });
  name.addEventListener("change", () => { list.name = name.value.trim(); writeSetlists(lists); });
  main.append(h("p", { class: "hint" }, "The order Bank Up and Bank Down follow when Follow the setlist (Global) is on. Up to four, one for each show: the pedal follows the first until a Bank command with the action Setlist picks another, and shows its name as it does."),
    picks, h("label", { class: "field" }, "Name ", name),
    h("table", { class: "grid" },
      h("thead", {}, h("tr", {}, h("th", {}, "Position"), h("th", {}, spec.label))),
      h("tbody", {}, list.banks.map((b, i) => h("tr", {}, h("td", { class: "key" }, String(i + 1)),
        h("td", {}, named(fieldControl(spec, () => list.banks[i], (v) => { list.banks[i] = v; writeSetlists(lists); }), `${spec.label}, setlist ${n} position ${i + 1}`)))))));
}

function renderCombos(main) {
  const sec = section("Combo_Settings") || (state.config.Combo_Settings = { columns: [...state.schema.comboColumns], rows: [] });
  const fields = state.schema.sectionColumns.Combo_Settings;
  main.append(h("p", { class: "hint" }, "Two switches pressed together run another button's list. Switches: two of 1-4, A-D, e.g. 3+4. In bank: a number or All."),
    sec.rows.length ? h("table", { class: "grid" },
      h("thead", {}, h("tr", {}, h("th", {}, "#"), fields.map((f) => h("th", {}, f.label)), h("th", {}))),
      h("tbody", {}, sec.rows.map((row, i) => h("tr", {}, h("td", { class: "key" }, String(i + 1)),
        fields.map((f) => h("td", {}, named(fieldControl(f, () => cell(sec, row, f.col), (v) => setCell(sec, row, f.col, v)), `${f.label}, combo ${i + 1}`))),
        h("td", {}, h("button", { "aria-label": `Remove combo ${i + 1}`, onclick: () => { sec.rows.splice(i, 1); changed(); render(); } }, "Remove")))))) : h("p", {}, "No combos yet."),
    h("button", {
      disabled: sec.rows.length >= state.schema.comboCount,
      onclick: () => { sec.rows.push(sec.columns.map((c) => ({ Switches: "1+2", Bank: "All", Run_Bank: "0", Run_Button: "1", Run_List: "Short" }[c] ?? ""))); changed(); render(); },
    }, "Add a combo"));
}

// One card per entry: what it matches, then what it becomes. The fields shown
// follow the types, so a change of type draws the card again.
function renderMidiMap(main) {
  const sec = section("MidiMap_Settings") || (state.config.MidiMap_Settings = { columns: [...state.schema.midiMapColumns], rows: [] });
  const fields = state.schema.sectionColumns.MidiMap_Settings;
  const shown = (f, row) => !f.when || Object.entries(f.when).every(([c, vals]) => vals.includes(cell(sec, row, c)));
  const control = (f, row) => {
    const ctl = fieldControl(f, () => cell(sec, row, f.col), (v) => {
      setCell(sec, row, f.col, v);
      if (f.col.endsWith("_Type")) render();
    });
    return f.kind === "check" ? h("label", { class: "check" }, ctl, f.label) : labelled(f.label, ctl);
  };
  const part = (row, prefix, title) => h("div", { class: "fields" }, h("strong", { class: "map-part" }, title),
    fields.filter((f) => prefix.some((p) => f.col.startsWith(p)) && shown(f, row)).map((f) => control(f, row)));
  main.append(
    h("p", { class: "hint" }, "What a computer sends over USB, turned into what the device on the DIN output wants: another type, channel, number or value range (from 127 to 0 turns it round, one value alone always sends it), or a button's list, run as a Macro runs it. Every entry that matches acts. Empty number: any, or the same. Needs firmware 0.90."),
    ...sec.rows.map((row, i) => h("section", { class: "card" },
      h("h3", {}, `Entry ${i + 1} `, h("button", { "aria-label": `Remove entry ${i + 1}`, onclick: () => { sec.rows.splice(i, 1); changed(); render(); } }, "Remove")),
      part(row, ["In_"], "When"),
      part(row, ["Out_", "Run_", "Keep"], "Becomes"))),
    ...(sec.rows.length ? [] : [h("p", {}, "No entries yet.")]),
    h("button", {
      disabled: sec.rows.length >= state.schema.midiMapCount,
      onclick: () => {
        const fresh = { In_Type: "PC", Out_Type: "CC", Out_Number: "0", Run_Bank: "0", Run_Button: "1", Run_List: "Short", Keep: "N" };
        sec.rows.push(sec.columns.map((c) => fresh[c] ?? ""));
        changed();
        render();
      },
    }, "Add an entry"));
}

// Every program 0-127 with a box for its name; only the named ones are rows
function renderPresetNames(main) {
  const sec = section("Preset_Names") || (state.config.Preset_Names = { columns: [...state.schema.presetNameColumns], rows: [] });
  const rowFor = (p) => sec.rows.find((row) => int(cell(sec, row, "Program")) === p);
  const set = (p, v) => {
    const row = rowFor(p);
    if (!v) {
      if (row) { sec.rows.splice(sec.rows.indexOf(row), 1); changed(); }
      return;
    }
    if (row) { setCell(sec, row, "Name", v); return; }
    const fresh = sec.columns.map(() => "");
    fresh[col(sec, "Program")] = String(p);
    fresh[col(sec, "Name")] = v;
    sec.rows.push(fresh);
    sec.rows.sort((a, b) => int(cell(sec, a, "Program")) - int(cell(sec, b, "Program")));
    changed();
  };
  const spec = { kind: "text", max: state.schema.presetNameLength, display: true };
  main.append(
    h("p", { class: "hint" }, "A name for each program of your device, up to 8 characters. A label, a bank name or an info line with $N shows the name of the program it stands for instead of its number: put $N on a PCInc button and it shows the preset you are on. Needs firmware 1.20."),
    h("div", { class: "presets" }, Array.from({ length: state.schema.presetNameCount }, (_, p) =>
      labelled(String(p), fieldControl(spec, () => cell(sec, rowFor(p), "Name"), (v) => set(p, v))))));
}

// --- Files -----------------------------------------------------------------
async function openFile() {
  if (state.busy || !(await confirmDiscard())) return;
  const input = h("input", { type: "file", accept: ".csv,text/csv" });
  input.addEventListener("change", async () => {
    const file = input.files[0];
    if (!file) return;
    try {
      setConfig(state.tools.csvToSections(new Uint8Array(await file.arrayBuffer())), file.name);
      toast(`Opened ${file.name}`);
    } catch (e) {
      toast(`Cannot open ${file.name}: ${e.message}`, "error");
    }
  });
  input.click();
}

async function openDemo() {
  if (state.busy || !(await confirmDiscard())) return;
  try {
    setConfig(state.tools.csvToSections(await state.tools.fetchFile("demo-all-features.csv")), "demo-all-features.csv");
  } catch (e) {
    toast(`Cannot open the demo: ${e.message}. Check the internet connection and try again.`, "error");
  }
}

// The templates that come with the tools (python/templates), one per device:
// templates/index.json lists them, since a web server lists no folder. Up to
// four devices, each on its channel, make one configuration (lib/rigWizard.py)
async function openTemplate() {
  if (state.busy || !(await confirmDiscard())) return;
  let names, titles;
  try {
    names = JSON.parse(new TextDecoder().decode(await state.tools.fetchFile("templates/index.json"))).map((n) => n.replace(/\.csv$/, ""));
    titles = state.tools.rigTitles(names);
  } catch (e) {
    toast(`Cannot list the templates: ${e.message}. Check the internet connection and try again.`, "error");
    return;
  }
  const order = [...names].sort((a, b) => titles[a].localeCompare(titles[b]));
  const channels = () => h("select", {}, Array.from({ length: 16 }, (_, i) => h("option", { value: String(i + 1) }, String(i + 1))));
  const rows = [0, 1, 2, 3].map((i) => {
    const device = h("select", {}, [...(i ? [h("option", { value: "" }, "—")] : []), ...order.map((n) => h("option", { value: n }, titles[n]))]);
    const channel = channels();
    channel.value = String(i + 1);
    const follow = h("input", { type: "checkbox", checked: true });
    return { device, channel, follow, el: h("div", { class: "rig-row" },
      named(device, i ? `Device ${i + 1}` : "Main device"), named(channel, `Channel of device ${i + 1}`),
      i ? h("label", { class: "check" }, follow, " changes preset with the banks") : null) };
  });
  if (!(await confirmDialog("Start from your devices", [
    h("p", { class: "hint" }, "The main device first, then up to three more, each on the MIDI channel it is set to. The main device’s template makes the configuration; each of the others brings its footswitches or looper in a bank of its own."),
    h("div", { class: "rig" }, h("div", { class: "rig-row rig-head" }, h("span", {}, "Device"), h("span", {}, "Channel")), ...rows.map((r) => r.el)),
    h("p", { class: "hint" }, "Everything goes out of both USB and DIN, so each device needs a channel of its own. Change it all as you like afterwards, and save it under your own name.")], "Make it"))) return;
  const picked = rows.filter((r) => r.device.value);
  try {
    const parts = await Promise.all(picked.map(async (r) => ({
      template: r.device.value, channel: r.channel.value, follow: r.follow.checked,
      csv: new TextDecoder().decode(await state.tools.fetchFile(`templates/${r.device.value}.csv`)),
    })));
    const rig = state.tools.buildRig(parts);
    setConfig(rig.sections, "");
    state.dirty = parts.length > 1 || parts[0].channel !== "1";
    renderToolbar();
    await confirmDialog(parts.length > 1 ? "Your rig" : `The ${titles[parts[0].template]} template`, [
      h("p", {}, "Set up on the devices:"),
      h("ul", {}, rig.notes.map((n) => h("li", {}, n[0].toUpperCase() + n.slice(1) + ".")))], "OK");
  } catch (e) {
    toast(`Cannot make that configuration: ${e.message}`, "error");
  }
}

function saveCsv() {
  const problem = checkConfig();
  if (problem) { toast("Fix the configuration first: " + problem, "error"); return; }
  const name = state.fileName && !/^demo-all-features/.test(state.fileName) ? state.fileName : `${configName().replace(/[^\w-]+/g, "_")}.csv`;
  download(name, "﻿" + state.tools.sectionsToCsv(state.config));
  state.fileName = name;
  state.dirty = false;
  renderToolbar();
}

// The configuration in a link (share.js): opening it loads the configuration
async function shareConfig() {
  const problem = checkConfig();
  if (problem) { toast("Fix the configuration first: " + problem, "error"); return; }
  let link;
  try {
    link = await shareLink(location.href, state.tools.sectionsToCsv(state.config));
  } catch (e) {
    toast(`Cannot make the link: ${e.message}`, "error");
    return;
  }
  const field = h("textarea", { class: "share-link", readonly: true, rows: 4, onfocus: (e) => e.target.select() }, link);
  const copy = h("button", { class: "primary", onclick: async () => {
    try {
      await navigator.clipboard.writeText(link);
      copy.textContent = "Copied";
    } catch {
      field.focus();
      toast("Copy the selected link by hand", "error");
    }
  } }, "Copy the link");
  const share = navigator.share
    ? h("button", { onclick: () => navigator.share({ title: configName(), url: link }).catch(() => {}) }, "Share…")
    : null;
  const kb = (link.length / 1024).toFixed(1);
  const dlg = h("dialog", { class: "dialog" },
    h("h3", {}, `Share “${configName()}”`),
    h("p", {}, "Whoever opens this link gets the configuration open in the configurator, to look at, change, save or write to their pedal. It is all in the link, bank notes and setlists too: nothing is uploaded anywhere."),
    field,
    h("p", { class: "hint" }, `${kb} KB long.${link.length > 8000 ? " Some chats and forums cut links this long: if it arrives cut short, send the CSV file instead." : ""}`),
    h("div", { class: "dialog-buttons" },
      h("button", { onclick: () => dlg.close() }, "Close"), share, copy));
  dlg.addEventListener("close", () => dlg.remove());
  document.body.append(dlg);
  dlg.showModal();
}

// A configuration in the page's address, from a shared link
async function openLinked() {
  let csv;
  try {
    csv = await linkedCsv(location.hash);
  } catch (e) {
    toast(`Cannot open the shared configuration: ${e.message}. Ask for the link again, or for the CSV file.`, "error");
    return;
  }
  if (!csv || state.busy || !(await confirmDiscard())) return;
  try {
    setConfig(state.tools.csvToSections(csv), "");
    toast(`Opened the shared configuration “${configName()}”`);
  } catch (e) {
    toast(`Cannot open the shared configuration: ${e.message}`, "error");
    return;
  }
  // The address back to the plain page: a reload then keeps no stale copy
  history.replaceState(null, "", location.pathname + location.search);
}

// A bank as a song file, to load into a bank of any configuration (lib/songFile.py)
function saveSong() {
  const problem = checkConfig();
  if (problem) { toast("Fix the configuration first: " + problem, "error"); return; }
  try {
    const { name, text } = state.tools.saveSong(state.config, state.bank);
    download(name, "\ufeff" + text);
  } catch (e) {
    toast(`Bank ${state.bank} cannot be saved as a song: ${e.message}`, "error");
  }
}

function loadSong() {
  const bank = state.bank;
  const input = h("input", { type: "file", accept: ".csv,text/csv" });
  input.addEventListener("change", async () => {
    const file = input.files[0];
    if (!file) return;
    let loaded;
    try {
      loaded = state.tools.loadSong(state.config, new Uint8Array(await file.arrayBuffer()), bank);
    } catch (e) {
      toast(`${file.name} does not go into bank ${bank}: ${e.message}`, "error");
      return;
    }
    const notes = loaded.notes.map((n) => n[0].toUpperCase() + n.slice(1) + ".");
    if (!(await confirmDialog("Load song", [`Replace everything in bank ${bank}, its name included, with ${file.name}?`,
      ...(notes.length ? [h("ul", {}, notes.map((n) => h("li", {}, n)))] : [])], "Load"))) return;
    state.config = loaded.sections;
    state.bank = bank;
    changed();
    render();
    toast(`${file.name} is in bank ${bank}`);
  });
  input.click();
}

// The configuration as a page to print, in a tab of its own
function cheatSheet() {
  const problem = checkConfig();
  if (problem) { toast("Fix the configuration first: " + problem, "error"); return; }
  const page = state.tools.cheatSheet(state.config, state.deviceChosen);
  const url = URL.createObjectURL(new Blob([page], { type: "text/html" }));
  if (!window.open(url, "_blank")) download(`${configName().replace(/[^\w-]+/g, "_")}.html`, page);
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

// --- The pedal -----------------------------------------------------------------
async function connect() {
  try {
    if (!navigator.requestMIDIAccess) throw new Error(noWebMidi());
    if (!state.midiAccess) {
      state.midiAccess = await navigator.requestMIDIAccess({ sysex: true });
      state.midiAccess.addEventListener("statechange", () => { if (!state.pedal && !state.busy && !state.simulated) setTimeout(() => attach(true), 800); });
    }
    await attach(false);
  } catch (e) {
    if (e.name === "SecurityError" || e.name === "NotAllowedError") {
      notice("The browser did not allow MIDI for this page",
        "The configurator needs MIDI devices with SysEx to talk to the pedal, and the browser remembers a refusal. To allow it: click the icon left of the address bar, open the site settings, set “MIDI devices” (in Chrome “Control and reprogram your MIDI devices”) to Allow, then reload the page.");
    } else {
      toast(e.message || (e.code ? "the browser could not start MIDI" : String(e)), "error");
    }
  }
}

async function attach(quiet) {
  if (state.pedal) return;
  let pedal = null;
  try {
    const simulated = state.simulated;
    pedal = await Pedal.open(simulated ? state.sim.access : state.midiAccess);
    if (simulated) pedal.pause = 0;
    else pedal.onMessage = (msg) => logMessage("USB", msg);
    state.version = await pedal.version();
    try { state.slots = await pedal.useSlot(null); } catch (e) { state.slots = null; }
    pedal.onGone = () => { pedal.close(); if (state.pedal === pedal) { state.pedal = null; state.slots = null; render(); } };
    if (simulated !== state.simulated) { pedal.close(); return; }
    state.pedal = pedal;
    $("#notice").hidden = true;     // whatever stood in the way, it is past
    if (!quiet) toast(simulated ? `Simulated pedal on: firmware ${state.version}` : `Connected: firmware ${state.version}`);
    render();
  } catch (e) {
    if (pedal && state.pedal !== pedal) pedal.close();     // its ports and listeners, or they pile up at every try
    if (quiet) return;
    if (e instanceof Timeout && !state.simulated) {
      notice("The Midi Commander does not answer the configurator",
        "It is there, but it runs another firmware, most likely MeloAudio’s own: this configurator needs this project’s firmware. Install it in the Firmware tab: unplug the pedal, hold Bank Down and D while plugging it in, and it starts in its update mode.",
        "If it runs this project’s firmware already, unplug it and plug it in again.");
      state.tab = "firmware";
      render();
    } else {
      toast(e.message || String(e), "error");
    }
  }
}

// --- The simulated pedal ----------------------------------------------------------
async function simulate() {
  try {
    setBusy("Starting the simulated pedal");
    if (!state.sim) {
      const sim = await Simulator.load();
      sim.access.addEventListener("statechange", (e) => {
        if (e.port.type === "input" && e.port.state === "connected" && state.simulated && !state.pedal) setTimeout(() => attach(true), 50);
      });
      sim.onOutput = (port, msg) => logMessage(port, msg);
      state.sim = sim;
    }
    state.simulated = true;
    state.sim.start();
    // Its ports show up once it has booted, as a pedal's do, and the
    // statechange above attaches it
    if (!await waitFor(() => state.pedal, 10000, 50)) throw new Error("it did not answer");
    toast(`Simulated pedal on: firmware ${state.version}`);
    if (state.pedal && state.slots && !state.slots.valid.length) await demoIntoSimulation();
  } catch (e) {
    toast(`The simulated pedal could not start: ${e.message}`, "error");
    stopSimulation();
  } finally {
    setBusy(null);
    render();
  }
}

// A simulated pedal starts empty: the demo goes in slot 1, as a first look
async function demoIntoSimulation() {
  if (!state.tools) {
    setBusy("Loading the configurator’s Python");
    await waitFor(() => state.tools || state.toolsError, 120000, 300);
    if (!state.tools) {
      notice("The simulated pedal is on, but empty", "The demo is written to it with the configurator’s Python, which " +
        (state.toolsError ? "could not load. Reload the page to try again." : "has not loaded yet. Stop it and try again in a moment."));
      return;
    }
  }
  const packed = state.tools.pack(state.tools.csvToSections(await state.tools.fetchFile("demo-all-features.csv")));
  setBusy("Writing the demo to the simulated pedal");
  const pedal = state.pedal;
  await pedal.useSlot(0);
  await pedal.writeImage(state.version, packed.config, packed.image, () => {}, (d, t) => setBusy("Writing the demo to the simulated pedal", d, t), state.tools.sizes.ext2Offset);
  pedal.reset();
  toast("The simulated pedal holds the demo in slot 1. Write any configuration to it as to the pedal.");
}

function stopSimulation() {
  state.simulated = false;
  const pedal = state.pedal;
  state.pedal = null;
  state.slots = null;
  if (pedal) pedal.close();
  if (state.sim) state.sim.stop();
  render();
}

async function slotName(pedal, slot) {
  await pedal.useSlot(slot);
  const head = await pedal.readSettings(32);
  return String.fromCharCode(...head.slice(16, 32).map((b) => (b >= 32 && b < 127 ? b : 32))).trim();
}

function slotChooser(label, withEmpty) {
  const valid = state.slots ? state.slots.valid : [0];
  const slots = state.slots && !state.slots.single ? [0, 1, 2, 3] : [0];
  const sel = h("select", {}, slots.filter((s) => withEmpty || valid.includes(s)).map((s) =>
    h("option", { value: s }, `Slot ${s + 1}${slots.length > 1 && s === state.slots.active ? " (running)" : ""}${valid.includes(s) ? "" : " (empty)"}`)));
  sel.value = state.slots ? state.slots.active : 0;
  return { sel, el: labelled(label, sel) };
}

async function readFromPedal() {
  if (state.busy || !state.pedal || !(await confirmDiscard())) return;
  const pick = slotChooser("Read", false);
  if (!(await confirmDialog("Read a configuration from the pedal", [pick.el], "Read"))) return;
  const slot = Number(pick.sel.value);
  const pedal = state.pedal;
  try {
    setBusy(`Reading slot ${slot + 1}`);
    await pedal.useSlot(slot);
    const { data, image } = await pedal.readImage(state.version, state.tools.sizes, (d, t) => setBusy(`Reading slot ${slot + 1}`, d, t));
    setConfig(state.tools.imageToSections(data, image), "");
    toast(`Read slot ${slot + 1}: ${configName()}`);
  } catch (e) {
    toast(`Reading failed: ${e.message}`, "error");
  } finally {
    setBusy(null);
  }
}

// Every slot read first, then saved from a click in a dialog: files downloaded
// after a wait, with no click just before, the browser asks about or blocks
async function backupSlots() {
  if (state.busy || !state.pedal) return;
  const pedal = state.pedal;
  const valid = state.slots ? state.slots.valid : [0];
  if (!valid.length) { toast("No slot holds a configuration: there is nothing to back up."); return; }
  const files = [];
  try {
    for (const slot of valid) {
      setBusy(`Backing up slot ${slot + 1}`);
      await pedal.useSlot(slot);
      const { data, image } = await pedal.readImage(state.version, state.tools.sizes, (d, t) => setBusy(`Backing up slot ${slot + 1}`, d, t));
      const sections = state.tools.imageToSections(data, image);
      const name = (sections.Global_Settings.rows.find((r) => r[0] === "ConfigName") || [, ""])[1].trim() || "configuration";
      files.push([`slot${slot + 1}-${name.replace(/[^\w-]+/g, "_")}.csv`, "﻿" + state.tools.sectionsToCsv(sections)]);
    }
  } catch (e) {
    toast(`Backup failed: ${e.message}`, "error");
    return;
  } finally {
    setBusy(null);
  }
  const links = h("ul", {}, files.map(([name, text]) => h("li", {}, h("a", { href: "#", onclick: (e) => { e.preventDefault(); download(name, text); } }, name))));
  const many = files.length > 1;
  if (await confirmDialog(`Back up ${files.length} slot${many ? "s" : ""}`, [links,
    h("p", { class: "hint" }, many ? "Save them all, or one at a time from the list. The browser may ask once whether the page may download several files." : "Save it as a CSV file.")], many ? "Save all" : "Save")) {
    files.forEach(([name, text]) => download(name, text));
  }
}

async function writeToPedal() {
  const problem = checkConfig();
  if (problem) { toast("Fix the configuration first: " + problem, "error"); return; }
  const edits = state.edits;
  let packed;
  try { packed = state.tools.pack(state.config); } catch (e) { toast(e.message, "error"); return; }
  const pedal = state.pedal;
  const pick = slotChooser("Write to", true);
  const note = h("p", { class: "hint" }, "");
  const changes = h("ul", { class: "changes" });
  // One look at a time, and over before the write: each selects a slot. A
  // look is the whole slot read and compared, so a newer one stops it
  let looking = Promise.resolve();
  let lookId = 0;
  const look = async (id) => {
    const s = Number(pick.sel.value);
    changes.replaceChildren();
    if (state.slots && !state.slots.valid.includes(s)) { note.textContent = "The slot is empty: all of it goes in."; return; }
    const reading = (d, t) => {
      if (id !== lookId) throw new Error("stale");
      note.textContent = `Reading slot ${s + 1} to say what changes… ${Math.round((100 * d) / t)}%`;
    };
    try {
      reading(0, 1);
      await pedal.useSlot(s);
      const { data, image } = await pedal.readImage(state.version, state.tools.sizes, reading);
      const lines = state.tools.changes(data, image, state.config);
      const name = String.fromCharCode(...data.slice(16, 32).map((b) => (b >= 32 && b < 127 ? b : 32))).trim();
      note.textContent = lines.length ? `It holds “${name}”. Writing changes ${lines.length === 1 ? "this" : `these ${lines.length} things`}:` : `It holds “${name}”, already exactly this configuration.`;
      changes.replaceChildren(...lines.map((l) => h("li", {}, l)));
    } catch (e) {
      if (id === lookId) note.textContent = `Could not read the slot to say what changes: ${e.message}`;
    }
  };
  const showNow = () => { const id = ++lookId; looking = looking.then(() => look(id)); };
  pick.sel.addEventListener("change", showNow);
  showNow();
  const ok = await confirmDialog(`Write “${configName()}” to the pedal`,
    [pick.el, note, changes, h("p", {}, `${packed.image.length} bytes. The pedal restarts when it is written.`)], "Write");
  if (!ok) { lookId++; return; }
  lookId++;     // a look still reading stops: the write goes on at once
  const slot = Number(pick.sel.value);
  let erased = false;     // from the erase on, the slot is no longer what it was
  try {
    setBusy(`Writing slot ${slot + 1}`);
    await looking;
    await pedal.useSlot(slot);
    let warning = "";
    const log = (m) => { console.log(m); if (m === "Erasing the slot") erased = true; if (m.startsWith("WARNING: ")) warning = m.slice(9); };
    await pedal.writeImage(state.version, packed.config, packed.image, log, (d, t) => setBusy(`Writing slot ${slot + 1}`, d, t), state.tools.sizes.ext2Offset);
    setBusy("Restarting the pedal");
    state.dirty = state.edits !== edits || warning !== "";     // what changed during the write, or was left out, is not on the pedal
    pedal.reset();
    toast(warning ? `Written to slot ${slot + 1}, but ${warning}` : `Written to slot ${slot + 1}; the pedal restarts`, warning ? "error" : undefined);
  } catch (e) {
    toast(erased ? `Writing failed: ${e.message}. The slot is incomplete: write it again.` : `Writing failed: ${e.message}. Nothing was changed.`, "error");
  } finally {
    setBusy(null);
  }
}

// --- Live pedal ------------------------------------------------------------------
let live = null;

function stopLive() {
  if (live) { live.stop = true; live = null; }
}

function ledColor(level) {
  const t = level / LED_LEVELS;
  const mix = (a, b) => Math.round(a + (b - a) * t);
  return `rgb(${mix(0x2c, 0xff)}, ${mix(0x2c, 0x45)}, ${mix(0x2e, 0x3a)})`;
}

function renderLive(main) {
  if (!state.pedal) {
    main.append(h("p", {}, "Connect the pedal, or try without one, to see its display and LEDs, press its switches from here and see what it sends."));
    return;
  }
  if (!versionAtLeast(state.version, 0, 27)) {
    main.append(h("p", {}, `The live view needs firmware 0.27 or later; the pedal runs ${state.version}. Update it in the Firmware tab.`));
    return;
  }
  const canvas = h("canvas", { width: 128, height: 64, class: "screen" });
  const switchEl = (sw) => {
    const led = h("span", { class: "led", "data-sw": sw });
    const btn = h("button", { class: "footswitch", "aria-label": sw === "UP" ? "Bank up" : sw === "DOWN" ? "Bank down" : `Switch ${sw}` }, sw === "UP" ? "BANK ▲" : sw === "DOWN" ? "BANK ▼" : sw);
    const down = (e) => { e.preventDefault(); if (btn.classList.contains("down")) return; btn.classList.add("down"); state.pedal && state.pedal.press(sw, true).catch(() => {}); };
    const up = () => { if (!btn.classList.contains("down")) return; btn.classList.remove("down"); state.pedal && state.pedal.press(sw, false).catch(() => {}); };
    btn.addEventListener("pointerdown", down);
    btn.addEventListener("pointerup", up);
    btn.addEventListener("pointerleave", up);
    btn.addEventListener("pointercancel", up);
    // From the keyboard, Space or Enter held is the foot held
    const key = (e) => e.key === " " || e.key === "Enter";
    btn.addEventListener("keydown", (e) => { if (key(e)) down(e); });
    btn.addEventListener("keyup", (e) => { if (key(e)) { e.preventDefault(); up(); } });
    btn.addEventListener("blur", up);
    return h("div", { class: "sw" }, btn, led);
  };
  const info = h("p", { class: "hint live-info" }, "");
  main.append(h("div", { class: "live" },
    h("div", { class: "pedal-body" },
      h("div", { class: "row top" }, ["1", "2", "3", "4", "UP"].map(switchEl)),
      canvas,
      h("div", { class: "row bottom" }, ["A", "B", "C", "D", "DOWN"].map(switchEl))),
    info,
    expressionControls(),
    monitorView(),
    selfTestView()));
  stopLive();
  const me = (live = { stop: false });
  const ctx = canvas.getContext("2d");
  const img = ctx.createImageData(128, 64);
  let frame = -1;
  (async () => {
    while (!me.stop && state.pedal) {
      try {
        const s = await state.pedal.getState();
        s.leds.forEach((lv, i) => { const el = $(`.led[data-sw="${SWITCHES[i]}"]`, main); if (el) el.style.background = ledColor(lv); });
        info.textContent = `Bank ${s.bank}${s.bankName ? " " + s.bankName : ""} · slot ${s.slot + 1}${s.asleep ? " · asleep" : ""}${s.safeMode ? " · safe mode" : ""}`;
        if (s.frame !== frame || s.frame === null) {
          frame = s.frame;
          const buf = await state.pedal.getScreen();
          for (let y = 0; y < SCREEN_HEIGHT; y++) {
            for (let x = 0; x < 128; x++) {
              const on = (buf[x + (y >> 3) * SCREEN_WIDTH] >> (y & 7)) & 1;
              const o = (y * 128 + x) * 4;
              img.data.set(on ? [0xee, 0xf6, 0xff, 255] : [4, 5, 6, 255], o);
            }
          }
          ctx.putImageData(img, 0, 0);
        }
      } catch (e) { /* busy or gone: try again */ }
      await new Promise((r) => setTimeout(r, 120));
    }
  })();
}

// The expression pedals moved from here, through the pedal's SET_PEDAL (0.70)
function expressionControls() {
  if (!versionAtLeast(state.version, 0, 70)) return null;
  if (state.expPedal !== state.pedal) { state.expPedal = state.pedal; state.expHeld = [null, null]; }
  const pedalEl = (i) => {
    // What the pedal holds survives leaving the tab: the slider comes back where it was
    const slider = h("input", { type: "range", min: 0, max: 16383, value: state.expHeld[i] ?? 0, "aria-label": `Expression pedal ${i + 1}` });
    const letGo = h("button", { disabled: state.expHeld[i] === null }, "Let go");
    let sending = false, want = null;
    const send = async () => {
      if (sending) return;
      sending = true;
      while (want !== null && state.pedal) {
        const v = want;
        want = null;
        try { await state.pedal.setPedal(i, true, v); } catch (e) { /* gone */ }
      }
      sending = false;
    };
    slider.addEventListener("input", () => { want = state.expHeld[i] = Number(slider.value); letGo.disabled = false; send(); });
    letGo.addEventListener("click", async () => {
      want = state.expHeld[i] = null;
      letGo.disabled = true;
      try { await state.pedal.setPedal(i, false); } catch (e) { /* gone */ }
    });
    return h("label", { class: "exp" }, h("span", {}, `Expression ${i + 1}`), h("span", { class: "hint" }, "heel"), slider, h("span", { class: "hint" }, "toe"), letGo);
  };
  return h("section", { class: "card exp-controls" },
    h("h3", {}, "Expression pedals"),
    h("p", { class: "hint" }, state.simulated
      ? "The simulated pedal has nothing in its jacks: move a pedal here."
      : "Moving one here holds it there, over what is in its jack, until you let go."),
    pedalEl(0), pedalEl(1));
}

// The hardware self-test (1.40): the switches only count, the LEDs light in
// turn, the jacks are read raw; then what was found, in words (lib/selfTest.py)
function selfTestView() {
  if (!versionAtLeast(state.version, 1, 40)) return null;
  const NAMES = { DOWN: "Bank Down", UP: "Bank Up" };
  // Laid out as on the pedal: 1-4 and Bank Up, then A-D and Bank Down
  const cells = SWITCHES.map((sw) => h("li", { "data-sw": sw }, NAMES[sw] || sw));
  const shown = ["1", "2", "3", "4", "UP", "A", "B", "C", "D", "DOWN"].map((sw) => cells[SWITCHES.indexOf(sw)]);
  const jacks = h("p", { class: "hint selftest-jacks" }, "");
  const found = h("ul", { class: "selftest-found" });
  const go = h("button", { class: "primary" }, "Start the self-test");
  let run = null;
  const show = (t) => cells.forEach((li, i) => {
    li.textContent = `${NAMES[SWITCHES[i]] || SWITCHES[i]}: ${t.presses[i]}` + (t.bounces[i] ? ` · ${t.bounces[i]} bounce${t.bounces[i] > 1 ? "s" : ""}` : "");
    li.classList.toggle("down", t.down[i]);
    li.classList.toggle("bad", t.bounces[i] > 0);
    li.classList.toggle("done", t.presses[i] > 0);
  });
  go.addEventListener("click", async () => {
    if (run) { run.stop = true; return; }
    const me = (run = { stop: false });
    const owner = live, start = performance.now(), tally = new SelfTestTally();
    go.textContent = "Stop and check";
    found.replaceChildren();
    while (!me.stop && !(owner && owner.stop) && state.pedal) {
      try {
        tally.add(await state.pedal.selfTest(true, selfTestLeds(performance.now() - start)));
        const p = await state.pedal.getPedals();
        tally.addPedals(p);
        show(tally);
        jacks.textContent = `Expression jacks, raw 0-4095: ${p[0][0]} · ${p[1][0]}`;
      } catch (e) { /* busy or gone: try again */ }
      await new Promise((r) => setTimeout(r, 60));
    }
    try { await state.pedal.selfTest(false); } catch (e) { /* it ends by itself in 3 s */ }
    run = null;
    go.textContent = "Start the self-test";
    found.replaceChildren(...tally.report().map((t) => h("li", {}, t)));
  });
  return h("section", { class: "card selftest" },
    h("h3", {}, "Hardware self-test"),
    h("p", { class: "hint" }, "Before a gig: while it runs the switches only count, nothing is sent and no toggle changes. " +
      "Press each switch a few times as on stage, watch every LED light in turn, and sweep each expression pedal slowly, stopping here and there. " +
      "A switch that bounces, one stuck down or a pot that jumps is named when you stop."),
    go, h("ul", { class: "selftest-switches" }, shown), jacks, found);
}

// --- Stage -------------------------------------------------------------------------
// The tempo, bar and beat, from the clock the pedal sends over USB
const clock = { times: [], ticks: -1, running: false, last: 0 };

function clockMessage(msg) {
  const now = performance.now();
  switch (msg[0]) {
    case 0xf8:
      if (now - clock.last > 500) clock.times = [];
      clock.times.push(now);
      if (clock.times.length > 49) clock.times.shift();
      clock.last = now;
      if (clock.running) clock.ticks++;
      break;
    case 0xfa: clock.running = true; clock.ticks = -1; break;
    case 0xfb: clock.running = true; break;
    case 0xfc: clock.running = false; break;
    case 0xf2: clock.ticks = ((msg[2] << 7) | msg[1]) * 6 - 1; break;   // sixteenths
  }
}

// "120 BPM", with "bar 3 · 2" while the clock runs, or "" with no clock
function clockText() {
  const t = clock.times;
  if (t.length < 25 || performance.now() - clock.last > 500) return "";
  const bpm = 60000 / (((t[t.length - 1] - t[0]) / (t.length - 1)) * 24);
  let text = `${Math.round(bpm)} BPM`;
  if (clock.running && clock.ticks >= 0) {
    const beats = Number(globalValue("Beat_Counter")) || 4, beat = Math.floor(clock.ticks / 24);
    text += ` · bar ${Math.floor(beat / beats) + 1} · ${(beat % beats) + 1}`;
  }
  return text;
}

// Where the bank is in a setlist: {list, pos, songs}, songs its banks in order
// and pos the index of this one there, or null. The setlist chosen in the
// view, or else the one it was last found in, or the first that has it. A
// bank in a setlist twice is the place after the last one, when it is that.
function setlistPlace(bank, last) {
  if (!state.config) return null;
  const lists = setlistsOf(section("Setlist"));
  const order = state.stageList ? [state.stageList] : [last && last.list, ...Object.keys(lists).map(Number)].filter(Boolean);
  for (const n of order) {
    const songs = lists[n].banks.filter((b) => b !== "").map(Number);
    const at = songs.flatMap((b, i) => (b === bank ? [i] : []));
    if (!at.length) continue;
    const before = last && last.list === n ? last.pos : -2;
    const pos = at.includes(before + 1) ? before + 1 : at.includes(before) ? before : at[0];
    return { list: n, name: lists[n].name, pos, songs };
  }
  return null;
}

function bankTitle(b) {
  const r = rowOf("Bank_Naming", { Bank_Number: b }, false);
  const info = r ? cell(r.sec, r.row, "Bank_Info_Small").trim() : "";
  return [bankName(b) || `Bank ${b}`, info].filter(Boolean).join(" · ");
}

async function keepAwake(me) {
  try { if (navigator.wakeLock && document.visibilityState === "visible" && !me.stop) me.lock = await navigator.wakeLock.request("screen"); } catch (e) { /* not allowed: the screen may sleep */ }
}

function renderStage(main) {
  if (!state.pedal) {
    main.append(h("p", {}, "Connect the pedal, or try without one: this view follows it, the song large, its place in the setlist, the tempo, the buttons and your notes, for a tablet or a laptop on a stand."));
    return;
  }
  if (!versionAtLeast(state.version, 0, 27)) {
    main.append(h("p", {}, `The Stage view needs firmware 0.27 or later; the pedal runs ${state.version}. Update it in the Firmware tab.`));
    return;
  }
  const lists = state.config ? setlistsOf(section("Setlist")) : {};
  const used = Object.entries(lists).filter(([, l]) => l.banks.some((b) => b !== ""));
  const pick = used.length ? h("select", { "aria-label": "Setlist" },
    h("option", { value: "" }, "Setlist: as the pedal goes"),
    used.map(([n, l]) => h("option", { value: n, selected: state.stageList === Number(n) }, `Setlist ${n}${l.name ? " " + l.name : ""}`))) : null;
  if (pick) pick.addEventListener("change", () => { state.stageList = Number(pick.value) || 0; });
  const view = h("div", { class: "stage" });
  // Without the Fullscreen API (iPhone, the iOS Web MIDI browsers) the view
  // covers the page instead, with a button to give it back
  const cover = () => view.classList.add("covering");
  const full = h("button", { onclick: () => {
    if (document.fullscreenElement || document.webkitFullscreenElement) return (document.exitFullscreen || document.webkitExitFullscreen).call(document);
    const enter = view.requestFullscreen || view.webkitRequestFullscreen;
    if (!enter) return cover();
    try { Promise.resolve(enter.call(view)).catch(cover); } catch (e) { cover(); }
  } }, "Full screen");
  main.append(h("div", { class: "stage-bar" }, full, pick,
    h("span", { class: "hint" }, state.config
      ? "Notes are written in the Banks tab. The tempo shows while the pedal sends MIDI clock."
      : "Open the configuration the pedal runs to see its setlist and your notes here.")), view);

  const place = h("div", { class: "stage-place" }), tempo = h("div", { class: "stage-tempo" });
  const name = h("div", { class: "stage-name" }), info = h("div", { class: "stage-info" });
  const preview = h("div", { class: "stage-preview" }), note = h("div", { class: "stage-note" });
  const next = h("div", { class: "stage-next" });
  const tiles = ["1", "2", "3", "4", "A", "B", "C", "D"].map((id) => h("div", { class: "tile" }, h("span", { class: "id" }, id), h("span", { class: "label" })));
  view.append(h("button", { class: "stage-close", "aria-label": "Leave full screen", onclick: () => view.classList.remove("covering") }, "×"),
    h("div", { class: "stage-top" }, place, tempo), name, info, preview, note, next, h("div", { class: "stage-tiles" }, tiles));

  stopLive();
  const me = (live = { stop: false, lock: null });
  keepAwake(me);
  const visible = () => { if (document.visibilityState === "visible") keepAwake(me); };
  document.addEventListener("visibilitychange", visible);
  let shown = "", where = null;
  (async () => {
    while (!me.stop && state.pedal) {
      try {
        const s = await state.pedal.getState();
        // The configuration open here, if it is the one on the pedal
        const ours = state.config && bankName(s.bank).toUpperCase() === s.bankName.trim().toUpperCase();
        where = ours ? setlistPlace(s.bank, where) : null;
        const key = JSON.stringify([s, ours, where, state.stageList, state.edits]);
        if (key !== shown) {
          shown = key;
          name.textContent = s.bankName || `Bank ${s.bank}`;
          const r = ours && rowOf("Bank_Naming", { Bank_Number: s.bank }, false);
          info.textContent = r ? cell(r.sec, r.row, "Bank_Info_Small").trim() : "";
          note.textContent = ours ? bankNote(s.bank) : "";
          preview.textContent = s.preview !== null ? `▲▼ ${ours ? bankTitle(s.preview) : `Bank ${s.preview}`}` : "";
          place.textContent = where ? `${where.name || `Setlist ${where.list}`} · ${where.pos + 1} of ${where.songs.length}` : `Bank ${s.bank}`;
          next.textContent = !where ? "" : where.pos + 1 < where.songs.length ? `Next: ${bankTitle(where.songs[where.pos + 1])}` : "Last song";
          tiles.forEach((t, i) => {
            t.lastChild.textContent = s.labels[i];
            t.classList.toggle("on", s.toggles[i]);
            t.classList.toggle("empty", !s.labels[i]);
          });
          view.classList.toggle("asleep", s.asleep);
        }
        tempo.textContent = clockText();
      } catch (e) { /* busy or gone: try again */ }
      await new Promise((r) => setTimeout(r, 150));
    }
    document.removeEventListener("visibilitychange", visible);
    if (me.lock) me.lock.release().catch(() => {});
  })();
}

// --- What the pedal sends ---------------------------------------------------------
const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const hex = (b) => b.toString(16).toUpperCase().padStart(2, "0");

function describeMidi(port, m) {
  if (port === "keys") {
    if (m[0] === 1) {
      const keys = m.slice(3).filter(Boolean);
      if (!keys.length && !m[1]) return "all keys up";
      return [m[1] ? `modifiers ${hex(m[1])}` : "", keys.length ? `key${keys.length > 1 ? "s" : ""} ${keys.map(hex).join(" ")}` : ""].filter(Boolean).join(", ");
    }
    const usage = m[1] | (m[2] << 8);
    return usage ? `media key ${hex(usage >> 8)}${hex(usage & 0xff)}` : "media key up";
  }
  const s = m[0], ch = `ch ${(s & 15) + 1}`;
  const note = (n) => `${NOTE_NAMES[n % 12]}${Math.floor(n / 12) - 1} (${n})`;
  switch (s >> 4) {
    case 0x8: return `Note off ${note(m[1])} · ${ch}`;
    case 0x9: return m[2] ? `Note on ${note(m[1])} vel ${m[2]} · ${ch}` : `Note off ${note(m[1])} · ${ch}`;
    case 0xa: return `Poly pressure ${note(m[1])} = ${m[2]} · ${ch}`;
    case 0xb: return `CC ${m[1]} = ${m[2]} · ${ch}`;
    case 0xc: return `PC ${m[1]} · ${ch}`;
    case 0xd: return `Channel pressure ${m[1]} · ${ch}`;
    case 0xe: return `Pitch bend ${((m[2] << 7) | m[1]) - 8192} · ${ch}`;
  }
  const names = { 0xf8: "Clock", 0xfa: "Start", 0xfb: "Continue", 0xfc: "Stop", 0xfe: "Active sensing", 0xff: "Reset" };
  if (names[s]) return names[s];
  if (s === 0xf2) return `Song position ${(m[2] << 7) | m[1]}`;
  if (s === 0xf0) return `SysEx ${m.length} bytes: ${m.slice(0, 12).map(hex).join(" ")}${m.length > 12 ? " …" : ""}`;
  return m.map(hex).join(" ");
}

function logMessage(port, msg) {
  if (port === "USB") clockMessage(msg);
  if (msg[0] === 0xf8 && !state.showClock) return;
  state.monitor.push({ port, text: describeMidi(port, Array.from(msg)) });
  if (state.monitor.length > 200) state.monitor.splice(0, state.monitor.length - 200);
  const list = $("#monitor-list");
  if (list) {
    list.append(monitorLine(state.monitor[state.monitor.length - 1]));
    while (list.childElementCount > 200) list.firstChild.remove();
    list.scrollTop = list.scrollHeight;
  }
}

function monitorLine(e) {
  return h("li", {}, h("span", { class: `port ${e.port.toLowerCase()}` }, e.port === "keys" ? "Keys" : e.port), e.text);
}

function monitorView() {
  const list = h("ol", { id: "monitor-list", class: "monitor" }, state.monitor.map(monitorLine));
  const clock = h("input", { type: "checkbox", checked: state.showClock });
  clock.addEventListener("change", () => { state.showClock = clock.checked; });
  setTimeout(() => { list.scrollTop = list.scrollHeight; });
  return h("section", { class: "card monitor-card" },
    h("div", { class: "monitor-head" },
      h("h3", {}, "What the pedal sends"),
      h("label", { class: "hint" }, clock, " clock"),
      h("button", { onclick: () => { state.monitor = []; list.replaceChildren(); } }, "Clear")),
    h("p", { class: "hint" }, state.simulated
      ? "Over USB, on the DIN output and as computer keys: the simulated pedal sends nowhere else."
      : "What comes in over USB. The DIN output and the computer keys are not seen from here: try the simulated pedal for those."),
    list);
}

// --- Firmware ----------------------------------------------------------------------
function renderFirmware(main) {
  const file = h("input", { type: "file", accept: ".dfu" });
  const info = h("p", {}, state.dfuPayload ? `${state.dfuName}: ${state.dfuPayload.length} bytes, ready.` : "No file chosen.");
  file.addEventListener("change", async () => {
    const f = file.files[0];
    if (!f) return;
    try {
      state.dfuPayload = loadImage(new Uint8Array(await f.arrayBuffer()));
      state.dfuName = f.name;
    } catch (e) {
      state.dfuPayload = null;
      toast(`${f.name}: ${e.message}`, "error");
    }
    render();
  });
  if (state.simulated) {
    main.append(h("section", { class: "card firmware" },
      h("h3", {}, "Update the firmware"),
      h("p", {}, `The simulated pedal runs the firmware this page came with, ${state.version}, and has nothing to update. Connect the pedal to update it.`)));
    return;
  }
  const usb = Boolean(navigator.usb);
  main.append(h("section", { class: "card firmware" },
    h("h3", {}, "Update the firmware"),
    h("p", {}, "Choose a .dfu file from the project’s releases. The pedal restarts in its update mode by itself (firmware 0.58 or later), the file is written and read back, and the pedal starts again. About 15 seconds; your configurations stay."),
    usb ? null : h("p", { class: "problem" }, isIOS()
      ? "An iPad or iPhone cannot update the pedal: no browser there has WebUSB. Use Chrome, Edge or Opera on a computer."
      : "This browser has no WebUSB: use Chrome, Edge or Opera on a computer."),
    state.updateStuck ? h("p", { class: "problem" }, "The last update did not finish. The pedal waits in its update mode, with its screen dark: press Update again, with the same file. It does not need to be connected first.") : null,
    file, info,
    h("div", { class: "buttons" },
      h("button", { class: "primary", disabled: !state.dfuPayload || !usb || state.busy, onclick: updateFirmware }, "Update"),
      h("span", { class: "hint" }, state.pedal ? `The pedal runs ${state.version}.` : "Connect the pedal first, or put it in update mode by hand: hold Bank Down and D while plugging it in.")),
    h("p", { class: "hint" }, "The first time, the browser asks which device to use: choose “STM32 BOOTLOADER” or “DFU in FS Mode”. On Windows the bootloader needs the WinUSB driver (Zadig), as for dfu-util.")));
}

async function waitFor(pred, ms, step = 250) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    const v = await pred();
    if (v) return v;
    await new Promise((r) => setTimeout(r, step));
  }
  return null;
}

async function askForBootloader() {
  // A device the page may use already, or the browser's chooser (it needs a click)
  const found = await Dfu.find(navigator.usb);
  if (found) return found;
  return new Promise((resolve) => {
    const dlg = h("dialog", { class: "dialog" },
      h("h3", {}, "Allow the pedal’s update mode"),
      h("p", {}, "The browser needs your permission to write to the pedal. Press Choose and pick the bootloader in the list."),
      h("div", { class: "dialog-buttons" },
        h("button", { onclick: () => { dlg.close(); resolve(null); } }, "Cancel"),
        h("button", { class: "primary", onclick: async () => {
          try { const d = await navigator.usb.requestDevice({ filters: [DFU_FILTER] }); dlg.close(); resolve(d); } catch (e) { /* chose nothing */ }
        } }, "Choose")));
    document.body.append(dlg);
    dlg.addEventListener("close", () => { dlg.remove(); resolve(null); });   // Escape too
    dlg.showModal();
  });
}

async function updateFirmware() {
  const payload = state.dfuPayload;
  const ok = await confirmDialog("Update the firmware", `Write ${state.dfuName} (${payload.length} bytes) to the pedal? Keep the USB cable in until it has started again.`, "Update");
  if (!ok) return;
  let inUpdateMode = false;     // from here on, a failure leaves the pedal waiting there
  try {
    let device = await Dfu.find(navigator.usb);
    let sent = false;     // the pedal was asked to go to update mode, and went
    if (state.pedal) {
      setBusy("Asking the pedal to restart in update mode");
      let onItsWay;
      try { onItsWay = await state.pedal.enterDfu(); } catch (e) {
        throw new UpdateError(`the firmware on the pedal (${state.version}) cannot restart in update mode by itself. Unplug it, hold Bank Down and D while plugging it in, and try again.`);
      }
      if (!onItsWay) throw new UpdateError("the firmware on the pedal is not running behind the stock bootloader: nothing was changed.");
      sent = true;
      const p = state.pedal;
      state.pedal = null;
      p.close();
      renderToolbar();
      device = await waitFor(() => Dfu.find(navigator.usb), 8000, 400);
    }
    setBusy("Waiting for the update mode");
    if (!device) device = await askForBootloader();
    if (!device) {
      throw new UpdateError(sent
        ? "no bootloader chosen. The pedal waits in update mode: press Update again and choose it."
        : "no pedal in update mode. Unplug the USB cable and plug it in again: it starts in update mode, and you can try again.");
    }
    inUpdateMode = true;
    await flash(device, payload, {
      log: (m) => setBusy(m),
      progress: (d, t, what) => setBusy({ erase: "Erasing", write: "Writing", verify: "Checking" }[what], d, t),
    });
    setBusy("Waiting for the pedal to start");
    if (state.midiAccess) {
      await waitFor(async () => { await attach(true); return state.pedal; }, 20000, 800);
    }
    state.updateStuck = false;
    toast(state.pedal ? `Updated: the pedal runs ${state.version}` : "Updated. Connect the pedal again to see its version.");
  } catch (e) {
    state.updateStuck = inUpdateMode;
    toast(`Update failed: ${e.message}`, "error");
  } finally {
    setBusy(null);
    render();
  }
}

// --- Start -------------------------------------------------------------------------
window.addEventListener("beforeunload", (e) => { if (state.dirty || state.busy) { e.preventDefault(); e.returnValue = ""; } });

document.addEventListener("DOMContentLoaded", async () => {
  $("#btn-open").addEventListener("click", openFile);
  $("#btn-demo").addEventListener("click", openDemo);
  $("#btn-template").addEventListener("click", openTemplate);
  $("#btn-read").addEventListener("click", readFromPedal);
  $("#btn-print").addEventListener("click", cheatSheet);
  $("#btn-save").addEventListener("click", saveCsv);
  $("#btn-share").addEventListener("click", shareConfig);
  $("#btn-write").addEventListener("click", writeToPedal);
  $("#btn-backup").addEventListener("click", backupSlots);
  render();
  try {
    state.tools = await Tools.load((s) => { $("#py-status").textContent = s + "…"; });
    state.schema = state.tools.schema;
    $("#py-status").textContent = "";
  } catch (e) {
    state.toolsError = e.message || String(e);
    $("#py-status").textContent = "";
    render();
    return;
  }
  render();
  await openLinked();
  window.addEventListener("hashchange", openLinked);
});

// For the tests (web/tests): the page's state and its steps
window.mc = { state, setConfig, shareConfig, openLinked, connect, simulate, stopSimulation, checkConfig, render };
