#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import the OpenMIDI database into python/lib/openmidi.json.

OpenMIDI (https://github.com/Morningstar-Engineering/openmidi, Apache-2.0)
is a community record of the MIDI CCs of hundreds of devices, one YAML per
device and data/all.json with them all. This turns that file into the
device dictionary's community part, which the configurators offer below the
hand-checked devices of lib/devices.json. The devices that dictionary
already has are left out: its maps are checked against the manuals.

    git clone --depth 1 https://github.com/Morningstar-Engineering/openmidi
    python3 python/import_openmidi.py openmidi
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "lib", "openmidi.json")
SOURCE = "https://github.com/Morningstar-Engineering/openmidi"

# OpenMIDI's devices that lib/devices.json has, checked: {OpenMIDI id: ours}
REPLACED = {
    "ikmultimedia/tonex": "TONEX Pedal",
    "kemper/profiler_player": "Kemper Player",
    "line6/helix": "Helix",
    "line6/helixfloor": "Helix",
    "line6/helixlt": "Helix",
    "line6/helixstadium": "Helix Stadium",
    "line6/hxstomp": "HX Stomp",
    "line6/podgo": "POD Go",
    "meris/enzox": "Enzo X",
    "meris/lvx": "LVX",
    "meris/mercuryx": "MercuryX",
    "neuraldsp/nanocortex": "Nano Cortex",
    "neuraldsp/quadcortex": "Quad Cortex",
    "strymon/bigsky": "BigSky",
    "strymon/iridium": "Iridium",
    "strymon/timeline": "TimeLine",
    "strymon/volante": "Volante",
    "valeton/gp200": "GP-200",
}


def _int(value):
    """A whole number from OpenMIDI's text or number, or None: some say
    "User-defined" or "0-127" instead."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def command(cc: dict):
    """A dictionary entry for one of OpenMIDI's CCs, or None.

    One value, min = max, is a press that sends it, and so is a range in
    the upper half, 64-127, where any value does the same; any other range
    is a switch between its ends, max on and min off, as for an on / off or
    a pedal.
    """
    number = _int(cc.get("value"))
    name = _text(cc.get("name"))
    if number is None or not 0 <= number <= 127 or not name:
        return None
    low, high = _int(cc.get("min")), _int(cc.get("max"))
    low = 0 if low is None or not 0 <= low <= 127 else low
    high = 127 if high is None or not 0 <= high <= 127 else high
    low, high = min(low, high), max(low, high)
    if low == high or low >= 64:
        return {"name": name, "type": "CC", "number": number, "on": high}
    return {"name": name, "type": "CC", "number": number, "on": high, "off": low, "toggle": True}


def device(maker: str, model: str, data: dict) -> dict:
    commands = [{"name": "Program", "type": "PC"}]
    seen = set()
    for cc in data.get("cc") or []:
        e = command(cc)
        if e is None or json.dumps(e, sort_keys=True) in seen:
            continue
        seen.add(json.dumps(e, sort_keys=True))
        # One name a command: a name used twice says which CC it is
        names = {c["name"] for c in commands}
        if e["name"] in names:
            e["name"] = f"{e['name']} (CC{e['number']})"
            n = 2
            while e["name"] in names:
                e["name"] = f"{e['name'].rsplit(' #', 1)[0]} #{n}"
                n += 1
        commands.append(e)
    return {"name": f"{maker} {model}", "maker": maker, "model": model, "commands": commands}


def convert(all_devices: dict, mapping: dict) -> list:
    """The community devices, by maker and model, from OpenMIDI's all.json
    and the names its mapping.json gives them."""
    out = []
    for brand in mapping["brands"]:
        maker = _text(brand["name"])
        for m in brand["models"]:
            key = f"{brand['value']}/{m['value']}"
            data = all_devices.get(brand["value"], {}).get(m["value"])
            if key in REPLACED or data is None:
                continue
            d = device(maker, _text(m["name"]), data)
            if len(d["commands"]) > 1:
                out.append(d)
    out.sort(key=lambda d: (d["maker"].lower(), d["model"].lower()))
    names = [d["name"] for d in out]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        raise SystemExit(f"two devices with one name: {sorted(dup)}")
    return out


def dump(devices: list, commit: str) -> str:
    """openmidi.json, one device a line, so an update shows as a diff of the
    devices that changed."""
    head = {"source": SOURCE, "commit": commit, "licence": "Apache-2.0, lib/openmidi-LICENSE.txt"}
    lines = [json.dumps(d, ensure_ascii=False, separators=(",", ":")) for d in devices]
    return ("{" + json.dumps(head)[1:-1] + ',\n"devices":[\n' + ",\n".join(lines) + "\n]}\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("openmidi", help="a clone of the OpenMIDI repository")
    args = ap.parse_args()
    data = os.path.join(args.openmidi, "data")
    with open(os.path.join(data, "all.json"), encoding="utf-8") as f:
        all_devices = json.load(f)
    with open(os.path.join(data, "mapping.json"), encoding="utf-8") as f:
        mapping = json.load(f)
    try:
        commit = subprocess.run(["git", "-C", args.openmidi, "rev-parse", "HEAD"], capture_output=True,
                                text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = ""
    devices = convert(all_devices, mapping)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(dump(devices, commit))
    print(f"{len(devices)} devices, {sum(len(d['commands']) for d in devices)} commands -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
