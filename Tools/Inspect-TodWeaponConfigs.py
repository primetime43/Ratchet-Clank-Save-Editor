"""Read-only report of extracted ToD weapon/mod/vendor CSV configuration.

Never executes Lua or CSV expressions. CSV order is NOT a save-record ID map.
Reference hashes identify the inspected BCUS98127 v02.00 assets; other versions
may be inspected but are explicitly marked unverified. No files are written.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re

REFERENCE_HASHES = {
    "weapon.csv": "2E9D75D6509F35E75B27626D1D777F4D5414FCBAA1AC553D36AE9D9F4A728F7A",
    "weapon.lua": "DECDC62DF183E47640E8B05D137E2A3C1F3C6929C55A81CB9C60BDB7694F0F85",
    "mods.csv": "0A01163D76189C7AB532345C22B5355290E3D1170E76672F0309F888EC5A68EE",
    "mods.lua": "5007B0FDDD3F8D46BFE22DCBE9ABB06E679CA6993149F26D9EA75BCE81C464FF",
    "vendor.csv": "E5163C6E8195EBAF761B2B9FD4F96BCFE227A902454AC1323EDE720ED1DB639D",
    "vendor.lua": "E9C1E5500FA6B690EA8FA4C82B373A2C69AE5C192D5381C3BF9EA92679786B20",
}
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9]*\Z")
NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?\Z")


def numeric(value):
    if not NUMBER.fullmatch(value):
        raise ValueError(f"Expected numeric literal, not expression: {value!r}")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Nonfinite configuration value")
    return result


def rows(raw):
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Configuration exceeds 2 MiB limit")
    parsed = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True))
    if len(parsed) > 10000 or any(len(row) > 64 or any(len(cell) > 4096 for cell in row) for row in parsed):
        raise ValueError("Configuration row/cell limits exceeded")
    return [[cell.strip() for cell in row] + [""] * max(0, 13 - len(row)) for row in parsed]


def parse_weapons(raw):
    result, active, in_table = {}, None, False
    for row in rows(raw):
        if row[0] == "Weapon:":
            in_table = True
            continue
        if not in_table:
            continue
        if row[0]:
            if not IDENTIFIER.fullmatch(row[0]) or row[0] in result:
                raise ValueError("Invalid/duplicate weapon configuration name")
            active = {"num_levels": 0, "variables": {}}
            result[row[0]] = active
        elif active is not None and row[1]:
            variable = row[1]
            if not IDENTIFIER.fullmatch(variable) or variable in active["variables"]:
                raise ValueError("Invalid/duplicate weapon variable")
            # weapon.lua: Lua columns 4..num_weapon_levels+3, level=c-4.
            if any(row[23:]):
                raise ValueError("Weapon variable exceeds the native 20-slot research layout")
            values = [numeric(value) if value else None for value in row[3:23]]
            last = max((i for i, value in enumerate(values) if value is not None), default=-1)
            if last >= 0:
                active["variables"][variable] = values[:last + 1]
                active["num_levels"] = max(active["num_levels"], last)
    if not result:
        raise ValueError("Missing weapon configuration table")
    return result


def parse_mods(raw):
    result, active, in_table = {}, None, False
    for row in rows(raw):
        if row[0] == "Weapon:":
            in_table = True
            continue
        if not in_table:
            continue
        if row[0]:
            if not IDENTIFIER.fullmatch(row[0]) or row[0] in result:
                raise ValueError("Invalid/duplicate modifier weapon name")
            active = []
            result[row[0]] = active
        elif active is not None and row[1]:
            if not row[1].isdigit():
                raise ValueError("Invalid modifier index")
            index = int(row[1])
            if index != len(active) or index >= 32 or not re.fullmatch(r"MOD_[A-Z_]+", row[2]):
                raise ValueError(f"Modifier indices must be contiguous 0..31 with symbolic types: {row[:6]!r}")
            if row[3] not in ("", "ABSOLUTE", "PERCENT") or (row[3] == "PERCENT" and not row[4]):
                raise ValueError("Invalid modifier kind/value")
            if row[2] not in ("MOD_START", "MOD_SPECIAL") and (not row[4] or not row[5]):
                raise ValueError("Missing modifier kind/value/cost")
            cost = numeric(row[5]) if row[5] else None
            if cost is not None and (cost < 0 or not cost.is_integer()):
                raise ValueError("Modifier cost must be a nonnegative integer")
            value = numeric(row[4]) if row[4] else None
            active.append({"index": index, "mask": f"0x{1 << index:08X}", "type": row[2],
                           "is_percent": row[3] == "PERCENT", "value": value,
                           "runtime_value": value * 0.01 if value is not None and row[3] == "PERCENT" else value,
                           "cost": int(cost) if cost is not None else None,
                           "name_tag": row[6] or None, "description_tag": row[7] or None})
    if not result:
        raise ValueError("Missing modifier configuration table")
    return result


def parse_vendor(raw):
    weapons, armor, columns, section = {}, {}, None, None
    for row in rows(raw):
        if row[0]:
            section, columns = row[0], row
            continue
        if columns is None or section not in ("Weapon", "Armor") or not row[1]:
            continue
        target = weapons if section == "Weapon" else armor
        if row[1] in target:
            raise ValueError("Duplicate vendor record")
        target[row[1]] = {field: numeric(row[i]) if NUMBER.fullmatch(row[i]) else row[i][:30]
                          for i, field in enumerate(columns)
                          if i > 1 and IDENTIFIER.fullmatch(field) and row[i]}
    if not weapons:
        raise ValueError("Missing vendor configuration table")
    return weapons, armor


def inspect(directory):
    directory = Path(directory)
    assets = {}
    data = {}
    for name, expected in REFERENCE_HASHES.items():
        path = directory / name
        if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError(f"Missing/oversized configuration: {name}")
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest().upper()
        assets[name] = {"bytes": len(raw), "sha256": digest, "reference_matches": digest == expected}
        data[name] = raw
    weapons = parse_weapons(data["weapon.csv"])
    mods = parse_mods(data["mods.csv"])
    vendor, armor = parse_vendor(data["vendor.csv"])
    for name, weapon in weapons.items():
        weapon["modifiers"] = mods.get(name, [])
        weapon["vendor"] = vendor.get(name)
    return {"reference_build": "BCUS98127 v02.00", "reference_assets_match": all(a["reference_matches"] for a in assets.values()),
            "assets": assets, "weapon_count": len(weapons), "modifier_count": sum(len(m) for m in mods.values()),
            "weapons": weapons, "armor_vendor": armor,
            "unmatched_modifier_names": sorted(set(mods) - set(weapons)),
            "unmatched_vendor_names": sorted(set(vendor) - set(weapons)),
            "warnings": ["CSV order is not a save-record ID mapping.",
                         "NumLevels is the highest populated zero-based column, not a count.",
                         "Shipped asset definitions are not proof of runtime values or safe edit bounds.",
                         "Upgrade adjacency/prerequisites and gameplay round-trip validation remain unresolved.",
                         "Lua and all other archive payloads are inspected only; never executed."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Folder containing the six explicitly extracted CSV/Lua assets")
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.directory), indent=2, allow_nan=False))
    except (ValueError, OSError, UnicodeError, csv.Error) as error:
        parser.exit(2, f"Configuration inspection failed: {error}\n")


if __name__ == "__main__":
    main()
