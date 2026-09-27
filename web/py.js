// The configurator's Python (python/lib) running in the page with Pyodide, so
// a configuration is checked and packed exactly as the command line tools do.

const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";

// Everything webBridge.py imports; tests/test_web_bridge.py keeps this complete
const FILES = [
  "webBridge.py", "binaryUnpacker.py", "cmdBinaryPacker.py", "configCsv.py", "configPacker.py",
  "configSchema.py", "displayText.py", "settingsBinaryPacker.py",
];

// Published, the tools' files sit next to the page; in the repository, in python/
export async function toolsBase() {
  const bases = location.pathname.includes("/web/") ? ["../python/", "./"] : ["./", "../python/"];
  for (const base of bases) {
    try {
      const r = await fetch(new URL(base + "lib/webBridge.py", import.meta.url), { method: "HEAD" });
      if (r.ok) return new URL(base, import.meta.url);
    } catch (e) { /* try the next */ }
  }
  throw new Error("cannot find the configurator's Python files");
}

function pyError(e) {
  // Only the last line of a Python traceback says what is wrong
  const lines = String(e.message || e).trim().split("\n");
  const last = lines[lines.length - 1];
  return new Error(last.replace(/^\w+(Error|Exception): /, ""));
}

export class Tools {
  static async load(status = () => {}) {
    status("Loading Python");
    const { loadPyodide } = await import(PYODIDE + "pyodide.mjs");
    const py = await loadPyodide({ indexURL: PYODIDE });
    status("Loading pandas");
    await py.loadPackage("pandas");
    const base = await toolsBase();
    py.FS.mkdirTree("/tools/lib");
    await Promise.all(FILES.map(async (name) => {
      const r = await fetch(new URL("lib/" + name, base));
      if (!r.ok) throw new Error(`cannot load ${name}`);
      py.FS.writeFile("/tools/lib/" + name, new Uint8Array(await r.arrayBuffer()));
    }));
    py.runPython("import sys; sys.path.insert(0, '/tools'); import lib.webBridge");
    return new Tools(py, base);
  }

  constructor(py, base) {
    this.py = py;
    this.base = base;
    this.bridge = py.pyimport("lib.webBridge");
    this.schema = JSON.parse(this.bridge.schema_json());
    this.sizes = {
      config: this.bridge.CONFIG_SIZE,
      doubleOffset: this.bridge.DOUBLE_PRESS_OFFSET,
      double: this.bridge.DOUBLE_PRESS_SIZE,
      ext2Offset: this.bridge.EXT2_OFFSET,
      ext2: this.bridge.EXT2_SIZE,
    };
  }

  _call(fn, ...args) {
    try {
      return fn(...args);
    } catch (e) {
      throw pyError(e);
    }
  }

  csvToSections(bytes) {
    return JSON.parse(this._call(this.bridge.csv_to_sections, bytes));
  }

  sectionsToCsv(sections) {
    return this._call(this.bridge.sections_to_csv, JSON.stringify(sections));
  }

  // "" when the configuration packs, otherwise what is wrong and where
  check(sections) {
    return this._call(this.bridge.check, JSON.stringify(sections));
  }

  pack(sections) {
    const r = this._call(this.bridge.pack, JSON.stringify(sections));
    const [config, image] = r.toJs();
    r.destroy();
    return { config: Uint8Array.from(config), image: Uint8Array.from(image) };
  }

  imageToSections(data, image) {
    return JSON.parse(this._call(this.bridge.image_to_sections, data, image));
  }

  shown(text, width) {
    return this.bridge.shown(text, width);
  }

  // A file the tools come with: the demo, a template
  async fetchFile(path) {
    const r = await fetch(new URL(path, this.base));
    if (!r.ok) throw new Error(`cannot load ${path}`);
    return new Uint8Array(await r.arrayBuffer());
  }
}
