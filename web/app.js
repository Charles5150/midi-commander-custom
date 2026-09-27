// The web configurator: edit a configuration, read and write the pedal's
// slots, watch and play the pedal, and update its firmware. The editors are
// built from python/lib/configSchema.py, packing is python/lib (see py.js).

import { Tools } from "./py.js";
import { Pedal, SWITCHES, LED_LEVELS, SCREEN_WIDTH, SCREEN_HEIGHT, versionAtLeast } from "./pedal.js";
import { loadImage, flash, Dfu, DFU_FILTER, UpdateError } from "./dfu.js";
import { Simulator } from "./sim.js";

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
};

// --- Messages -----------------------------------------------------------------
function toast(text, kind = "info") {
  const el = h("div", { class: `toast ${kind}` }, text);
  $("#toasts").append(el);
  setTimeout(() => el.remove(), kind === "error" ? 9000 : 4500);
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
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = h("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
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
      const lsel = h("select", {}, spec.lists.map((o) => h("option", { value: o }, o)));
      const asel = h("select", {}, spec.actions.map((o) => h("option", { value: o }, o)));
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
  const draw = () => {
    wrap.replaceChildren();
    let last = slots.length - 1;
    while (last > 0 && !cell(sec, row, `${slots[last]}_CommandType`)) last--;
    const shownCount = Math.min(slots.length, Math.max(last + 2, 3));
    slots.slice(0, shownCount).forEach((slot) => wrap.append(commandRow(sec, row, slot, types, draw)));
    if (shownCount < slots.length) wrap.append(h("div", { class: "hint" }, `${slots.length - shownCount} more below, as the ones above fill`));
  };
  draw();
  return wrap;
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

  const typeSel = h("select", { class: "type" }, (types.includes(type) ? types : [...types, type]).map((t) => h("option", { value: t }, t)));
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

  const params = h("div", { class: "params" });
  for (const f of spec.fields) {
    if (!visible(f)) continue;
    const ctl = fieldControl(f, () => get(f.col), (v) => {
      store(type, { [f.col]: v });
      if (spec.fields.some((x) => x.when && f.col in x.when) || spec.hint_by === f.col) redraw();
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
  return h("div", { class: `command${type === noCommand ? " empty" : ""}` }, h("span", { class: "slot" }, slot), typeSel, params);
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
  ["sysex", "SysEx"], ["setlist", "Setlist"], ["combos", "Combos"], ["live", "Live pedal"], ["firmware", "Firmware"],
];

function renderToolbar() {
  const conn = $("#connection");
  conn.replaceChildren();
  if (state.pedal) {
    const slot = state.slots ? ` · running slot ${state.slots.active + 1}` : "";
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
  $("#btn-write").disabled = !state.config || !state.pedal || state.busy;
  $("#btn-read").disabled = !state.pedal || state.busy || !state.tools;
  $("#btn-backup").disabled = !state.pedal || state.busy || !state.tools;
  $("#btn-open").disabled = !state.tools || state.busy;
  $("#btn-demo").disabled = !state.tools || state.busy;
}

function render() {
  renderToolbar();
  const nav = $("#tabs");
  nav.replaceChildren(...TABS.map(([id, label]) => h("button", {
    class: state.tab === id ? "tab active" : "tab",
    onclick: () => { state.tab = id; render(); },
  }, label)));
  const main = $("#main");
  main.replaceChildren();
  const needsConfig = !["live", "firmware"].includes(state.tab);
  if (needsConfig && !state.config) {
    main.append(welcome());
    return;
  }
  ({
    banks: renderBanks, global: renderGlobal, expression: renderExpression, bankswitch: renderBankSwitch,
    sysex: renderSysex, setlist: renderSetlist, combos: renderCombos, live: renderLive, firmware: renderFirmware,
  })[state.tab](main);
  if (state.tab !== "live") stopLive();
}

function welcome() {
  return h("section", { class: "welcome" },
    h("h2", {}, "Configure your Midi Commander in the browser"),
    h("p", {}, "Nothing to install. Connect the pedal to read its configuration, open a CSV file made with the configurator, or start from the demo."),
    state.tools ? null : h("p", { class: "hint" }, "Loading the configurator’s Python… the first time takes a few seconds."),
    h("div", { class: "buttons" },
      h("button", { class: "primary", disabled: !state.pedal || !state.tools, onclick: readFromPedal }, "Read from the pedal"),
      h("button", { disabled: !state.tools, onclick: openFile }, "Open a CSV file"),
      h("button", { disabled: !state.tools, onclick: openDemo }, "Open the demo")),
    h("p", { class: "hint" }, "No pedal at hand? Try without a pedal: the pedal’s own firmware runs in the page, with the demo in it, and everything here works on it as on the real one."),
    h("p", { class: "hint" }, "Chrome, Edge or Opera on a computer: they have Web MIDI and WebUSB. The page asks to use MIDI devices with SysEx when you connect."));
}

// --- Banks -------------------------------------------------------------------
function bankName(b) {
  const r = rowOf("Bank_Naming", { Bank_Number: b }, false);
  return r ? cell(r.sec, r.row, "Bank_Name_Large").trim() : "";
}

function renderBanks(main) {
  const { numBanks, buttonIds, shortCommandTypes, commandTypes, enterCommandTypes, buttonFields } = state.schema;
  const list = h("nav", { class: "bank-list" }, [...Array(numBanks)].map((_, b) => h("button", {
    class: b === state.bank ? "active" : "",
    onclick: () => { state.bank = b; render(); },
  }, h("span", { class: "num" }, b), bankName(b) || "—")));

  const naming = rowOf("Bank_Naming", { Bank_Number: state.bank });
  const head = h("div", { class: "bank-head" },
    h("h2", {}, `Bank ${state.bank}`),
    labelled("Name", fieldControl({ kind: "text", max: 4, display: true }, () => cell(naming.sec, naming.row, "Bank_Name_Large"),
      (v) => { setCell(naming.sec, naming.row, "Bank_Name_Large", v); $(".bank-list .active").lastChild.textContent = v || "—"; })),
    labelled("Info line", fieldControl({ kind: "text", max: 8, display: true }, () => cell(naming.sec, naming.row, "Bank_Info_Small"),
      (v) => setCell(naming.sec, naming.row, "Bank_Info_Small", v))));

  // The eight buttons as on the pedal: 1-4 on top, A-D underneath
  const btnSec = section("Button_Settings");
  const pedal = h("div", { class: "pedal-grid" }, buttonIds.map((id) => {
    const r = rowOf("Button_Settings", { Bank_Number: state.bank, Button_Identifier: id }, false);
    const label = r ? cell(r.sec, r.row, "Label") : "";
    return h("button", {
      class: `pedal-button${id === state.button ? " active" : ""}`,
      onclick: () => { state.button = id; render(); },
    }, h("span", { class: "id" }, id), h("span", { class: "label" }, label || " "), h("span", { class: "sum" }, summary(btnSec, r && r.row)));
  }));

  const presses = [["Short", "Press", "Button_Settings", shortCommandTypes], ["Long", "Long press", "LongPress_Settings", commandTypes], ["Double", "Double press", "DoublePress_Settings", commandTypes]];
  const pressTabs = h("div", { class: "subtabs" }, presses.map(([id, label]) => h("button", {
    class: state.press === id ? "active" : "", onclick: () => { state.press = id; render(); },
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
  editor.append(commandList(r.sec, r.row, types));

  const enter = rowOf("BankEnter_Settings", { Bank_Number: state.bank });
  const enterCard = h("details", { class: "card" }, h("summary", {}, "On entering this bank"),
    h("p", { class: "hint" }, "Sent every time the bank is entered; after a Leave, on leaving it."),
    commandList(enter.sec, enter.row, enterCommandTypes));

  const expCard = h("details", { class: "card" }, h("summary", {}, "Expression pedals in this bank"));
  const exp = rowOf("BankExpression_Settings", { Bank_Number: state.bank }, false);
  if (exp) {
    expCard.append(h("p", { class: "hint" }, "Empty: as set in the Expression tab. CC: a number, Off, or Speed."),
      h("div", { class: "fields" }, state.schema.sectionColumns.BankExpression_Settings.map((f) =>
        labelled(f.label, fieldControl(f, () => cell(exp.sec, exp.row, f.col), (v) => setCell(exp.sec, exp.row, f.col, v))))));
  }

  main.append(h("div", { class: "banks" }, list, h("div", { class: "bank-main" }, head, pedal, editor, enterCard, exp ? expCard : null)));
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
      return h("div", { class: "setting" }, h("span", { class: "setting-name" }, name), ctl, h("span", { class: "hint" }, hint));
    })))));
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
  main.append(h("p", { class: "hint" }, "What Bank Down and Bank Up send when Bank switches (Global) is Bank+MIDI or MIDI only."));
  for (const [sw, press] of [["Down", "Short"], ["Down", "Long"], ["Up", "Short"], ["Up", "Long"]]) {
    const r = rowOf("BankSwitch_Settings", { Switch: sw, Press: press });
    main.append(h("section", { class: "card" }, h("h3", {}, `Bank ${sw}, ${press.toLowerCase()} press`), commandList(r.sec, r.row, state.schema.commandTypes)));
  }
}

// --- Simple tables ---------------------------------------------------------------
function table(sec, keyCol, keyLabel, fields) {
  return h("table", { class: "grid" },
    h("thead", {}, h("tr", {}, h("th", {}, keyLabel), fields.map((f) => h("th", {}, f.label)))),
    h("tbody", {}, sec.rows.map((row) => h("tr", {}, h("td", { class: "key" }, cell(sec, row, keyCol)),
      fields.map((f) => h("td", {}, fieldControl(f, () => cell(sec, row, f.col), (v) => setCell(sec, row, f.col, v))))))));
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
  main.append(h("p", { class: "hint" }, "Up to 23 bytes each, in hex without F0 and F7, for example 41 10 42 12. A SysEx command sends one by its number."),
    table(sec, "Index", "#", state.schema.sectionColumns.SysEx_Strings));
}

function renderSetlist(main) {
  const sec = ensureRows("Setlist", "Position", state.schema.setlistMax, { Bank_Number: "" });
  main.append(h("p", { class: "hint" }, "The order Bank Up and Bank Down follow when Follow the setlist (Global) is on. Empty positions end it."),
    table(sec, "Position", "Position", state.schema.sectionColumns.Setlist));
}

function renderCombos(main) {
  const sec = section("Combo_Settings") || (state.config.Combo_Settings = { columns: [...state.schema.comboColumns], rows: [] });
  const fields = state.schema.sectionColumns.Combo_Settings;
  main.append(h("p", { class: "hint" }, "Two switches pressed together run another button's list. Switches: two of 1-4, A-D, e.g. 3+4. In bank: a number or All."),
    sec.rows.length ? table(sec, "Switches", "", fields.slice(0)) : h("p", {}, "No combos yet."),
    h("button", {
      disabled: sec.rows.length >= state.schema.comboCount,
      onclick: () => { sec.rows.push(sec.columns.map((c) => ({ Switches: "1+2", Bank: "All", Run_Bank: "0", Run_Button: "1", Run_List: "Short" }[c] ?? ""))); changed(); render(); },
    }, "Add a combo"),
    sec.rows.length ? h("button", { onclick: () => { sec.rows.pop(); changed(); render(); } }, "Remove the last") : null);
}

// --- Files -----------------------------------------------------------------
async function openFile() {
  if (!(await confirmDiscard())) return;
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
  if (!(await confirmDiscard())) return;
  setConfig(state.tools.csvToSections(await state.tools.fetchFile("demo-all-features.csv")), "demo-all-features.csv");
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

// --- The pedal -----------------------------------------------------------------
async function connect() {
  try {
    if (!navigator.requestMIDIAccess) throw new Error("this browser has no Web MIDI: use Chrome, Edge or Opera");
    if (!state.midiAccess) {
      state.midiAccess = await navigator.requestMIDIAccess({ sysex: true });
      state.midiAccess.addEventListener("statechange", () => { if (!state.pedal && !state.busy && !state.simulated) setTimeout(() => attach(true), 800); });
    }
    await attach(false);
  } catch (e) {
    toast(e.message || String(e), "error");
  }
}

async function attach(quiet) {
  if (state.pedal) return;
  try {
    const simulated = state.simulated;
    const pedal = await Pedal.open(simulated ? state.sim.access : state.midiAccess);
    if (simulated) pedal.pause = 0;
    else pedal.onMessage = (msg) => logMessage("USB", msg);
    state.version = await pedal.version();
    try { state.slots = await pedal.selectSlot(null); } catch (e) { state.slots = null; }
    pedal.onGone = () => { pedal.close(); if (state.pedal === pedal) { state.pedal = null; state.slots = null; render(); } };
    if (simulated !== state.simulated) { pedal.close(); return; }
    state.pedal = pedal;
    if (!quiet) toast(simulated ? `Simulated pedal on: firmware ${state.version}` : `Connected: firmware ${state.version}`);
    render();
  } catch (e) {
    if (!quiet) toast(e.message || String(e), "error");
  }
}

// --- The simulated pedal ----------------------------------------------------------
async function simulate() {
  try {
    setBusy("Starting the simulated pedal");
    if (!state.sim) {
      const sim = await Simulator.load();
      sim.access.addEventListener("statechange", (e) => {
        if (e.port.state === "connected" && state.simulated && !state.pedal) setTimeout(() => attach(true), 50);
      });
      sim.onOutput = (port, msg) => logMessage(port, msg);
      state.sim = sim;
    }
    state.simulated = true;
    state.sim.start();
    await attach(false);
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
    await waitFor(() => state.tools, 120000, 300);
    if (!state.tools) return;
  }
  const packed = state.tools.pack(state.tools.csvToSections(await state.tools.fetchFile("demo-all-features.csv")));
  setBusy("Writing the demo to the simulated pedal");
  const pedal = state.pedal;
  await pedal.selectSlot(0);
  await pedal.writeImage(state.version, packed.config, packed.image, () => {}, (d, t) => setBusy("Writing the demo to the simulated pedal", d, t));
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
  await pedal.selectSlot(slot);
  const head = await pedal.readSettings(32);
  return String.fromCharCode(...head.slice(16, 32).map((b) => (b >= 32 && b < 127 ? b : 32))).trim();
}

function slotChooser(label, withEmpty) {
  const valid = state.slots ? state.slots.valid : [0];
  const sel = h("select", {}, [0, 1, 2, 3].filter((s) => withEmpty || valid.includes(s)).map((s) =>
    h("option", { value: s }, `Slot ${s + 1}${state.slots && s === state.slots.active ? " (running)" : ""}${valid.includes(s) ? "" : " (empty)"}`)));
  sel.value = state.slots ? state.slots.active : 0;
  return { sel, el: labelled(label, sel) };
}

async function readFromPedal() {
  if (!(await confirmDiscard())) return;
  const pick = slotChooser("Read", false);
  if (!(await confirmDialog("Read a configuration from the pedal", [pick.el], "Read"))) return;
  const slot = Number(pick.sel.value);
  const pedal = state.pedal;
  try {
    setBusy(`Reading slot ${slot + 1}`);
    await pedal.selectSlot(slot);
    const { data, image } = await pedal.readImage(state.version, state.tools.sizes, (d, t) => setBusy(`Reading slot ${slot + 1}`, d, t));
    setConfig(state.tools.imageToSections(data, image), "");
    toast(`Read slot ${slot + 1}: ${configName()}`);
  } catch (e) {
    toast(`Reading failed: ${e.message}`, "error");
  } finally {
    setBusy(null);
  }
}

async function backupSlots() {
  const pedal = state.pedal;
  const valid = state.slots ? state.slots.valid : [0];
  try {
    for (const slot of valid) {
      setBusy(`Backing up slot ${slot + 1}`);
      await pedal.selectSlot(slot);
      const { data, image } = await pedal.readImage(state.version, state.tools.sizes, (d, t) => setBusy(`Backing up slot ${slot + 1}`, d, t));
      const sections = state.tools.imageToSections(data, image);
      const name = (sections.Global_Settings.rows.find((r) => r[0] === "ConfigName") || [, ""])[1].trim() || "configuration";
      download(`slot${slot + 1}-${name.replace(/[^\w-]+/g, "_")}.csv`, "﻿" + state.tools.sectionsToCsv(sections));
    }
    toast(`Backed up ${valid.length} slot${valid.length === 1 ? "" : "s"} as CSV files`);
  } catch (e) {
    toast(`Backup failed: ${e.message}`, "error");
  } finally {
    setBusy(null);
  }
}

async function writeToPedal() {
  const problem = checkConfig();
  if (problem) { toast("Fix the configuration first: " + problem, "error"); return; }
  let packed;
  try { packed = state.tools.pack(state.config); } catch (e) { toast(e.message, "error"); return; }
  const pedal = state.pedal;
  const pick = slotChooser("Write to", true);
  const note = h("p", { class: "hint" }, "");
  const showNow = async () => {
    const s = Number(pick.sel.value);
    note.textContent = state.slots && !state.slots.valid.includes(s) ? "The slot is empty." : "Looking at what the slot holds…";
    if (state.slots && state.slots.valid.includes(s)) {
      try { note.textContent = `It holds “${await slotName(pedal, s)}”, which this replaces.`; } catch (e) { note.textContent = ""; }
    }
  };
  pick.sel.addEventListener("change", showNow);
  showNow();
  const ok = await confirmDialog(`Write “${configName()}” to the pedal`,
    [pick.el, note, h("p", {}, `${packed.image.length} bytes. The pedal restarts when it is written.`)], "Write");
  if (!ok) return;
  const slot = Number(pick.sel.value);
  try {
    setBusy(`Writing slot ${slot + 1}`);
    await pedal.selectSlot(slot);
    await pedal.writeImage(state.version, packed.config, packed.image, (m) => console.log(m), (d, t) => setBusy(`Writing slot ${slot + 1}`, d, t));
    setBusy("Restarting the pedal");
    state.dirty = false;
    pedal.reset();
    toast(`Written to slot ${slot + 1}; the pedal restarts`);
  } catch (e) {
    toast(`Writing failed: ${e.message}. The slot is incomplete: write it again.`, "error");
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
  const canvas = h("canvas", { width: 128, height: 64, class: "screen" });
  const switchEl = (sw) => {
    const led = h("span", { class: "led", "data-sw": sw });
    const btn = h("button", { class: "footswitch" }, sw === "UP" ? "BANK ▲" : sw === "DOWN" ? "BANK ▼" : sw);
    const down = (e) => { e.preventDefault(); btn.classList.add("down"); state.pedal && state.pedal.press(sw, true).catch(() => {}); };
    const up = () => { if (!btn.classList.contains("down")) return; btn.classList.remove("down"); state.pedal && state.pedal.press(sw, false).catch(() => {}); };
    btn.addEventListener("pointerdown", down);
    btn.addEventListener("pointerup", up);
    btn.addEventListener("pointerleave", up);
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
    monitorView()));
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
  const pedalEl = (i) => {
    const slider = h("input", { type: "range", min: 0, max: 16383, value: 0, "aria-label": `Expression pedal ${i + 1}` });
    const letGo = h("button", { disabled: true }, "Let go");
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
    slider.addEventListener("input", () => { want = Number(slider.value); letGo.disabled = false; send(); });
    letGo.addEventListener("click", async () => {
      want = null;
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
    usb ? null : h("p", { class: "problem" }, "This browser has no WebUSB: use Chrome, Edge or Opera on a computer."),
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
    dlg.addEventListener("close", () => dlg.remove());
    dlg.showModal();
  });
}

async function updateFirmware() {
  const payload = state.dfuPayload;
  const ok = await confirmDialog("Update the firmware", `Write ${state.dfuName} (${payload.length} bytes) to the pedal? Keep the USB cable in until it has started again.`, "Update");
  if (!ok) return;
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
    await flash(device, payload, {
      log: (m) => setBusy(m),
      progress: (d, t, what) => setBusy({ erase: "Erasing", write: "Writing", verify: "Checking" }[what], d, t),
    });
    setBusy("Waiting for the pedal to start");
    if (state.midiAccess) {
      await waitFor(async () => { await attach(true); return state.pedal; }, 20000, 800);
    }
    toast(state.pedal ? `Updated: the pedal runs ${state.version}` : "Updated. Connect the pedal again to see its version.");
  } catch (e) {
    toast(`Update failed: ${e.message}`, "error");
  } finally {
    setBusy(null);
    render();
  }
}

// --- Start -------------------------------------------------------------------------
window.addEventListener("beforeunload", (e) => { if (state.dirty) { e.preventDefault(); e.returnValue = ""; } });

document.addEventListener("DOMContentLoaded", async () => {
  $("#btn-open").addEventListener("click", openFile);
  $("#btn-demo").addEventListener("click", openDemo);
  $("#btn-read").addEventListener("click", readFromPedal);
  $("#btn-save").addEventListener("click", saveCsv);
  $("#btn-write").addEventListener("click", writeToPedal);
  $("#btn-backup").addEventListener("click", backupSlots);
  render();
  try {
    state.tools = await Tools.load((s) => { $("#py-status").textContent = s + "…"; });
    state.schema = state.tools.schema;
    $("#py-status").textContent = "";
  } catch (e) {
    $("#py-status").textContent = "The configurator could not load: " + e.message;
    return;
  }
  render();
});

// For the tests (web/tests): the page's state and its steps
window.mc = { state, setConfig, connect, simulate, stopSimulation, checkConfig, render };
