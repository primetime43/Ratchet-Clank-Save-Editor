"""Read-only exact-build pause-menu item names -> image banks -> HUD BC3 payloads.

Parses bounded literal Lua assignments and observed image-node properties.
No Lua execution, native calls, extraction or image/file writes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
PSARC = runpy.run_path(str(ROOT / "Tools/Inspect-Psarc.py"))
LUA = runpy.run_path(str(ROOT / "Tools/Inspect-Lua50.py"))
PAUSE_NAME = "/built/anark/pause/built.dat"
HASHES = {
    PAUSE_NAME: "26FC24DD3564FDF94F0F6278FC0F0BC5578FE73C6813D3F39CD113FD22CF761B",
    "/processed/texpacks/hud.tp": "FF662581D84107A7F4D77B83DA3B74277C5E36FDFB333C0CB15029A3FD434D16",
    "/processed/texpacks/hud.tph": "A057E6F0B48DD6968BB72DB33D261952D041B43196C8B262F87684F547A5FBA3",
}


def icon_assignments(raw):
    """Require consecutive GETTABLE(self.icon), GETGLOBAL(WPN_*), SETTABLE.

    Register relationships are checked; constants merely appearing together are
    not enough. Child functions are inspected recursively, never executed.
    """
    results = {}

    def visit(function):
        code = function["instructions"]
        for table, key, value in zip(code, code[1:], code[2:]):
            if not (table["op"] == "GETTABLE" and table.get("c_constant") == "icon" and
                    key["op"] == "GETGLOBAL" and str(key.get("constant", "")).startswith("WPN_") and
                    value["op"] == "SETTABLE" and value["a"] == table["a"] and value["b"] == key["a"] and
                    isinstance(value.get("c_constant"), str)):
                continue
            enum, name = key["constant"], value["c_constant"]
            if enum in results and results[enum]["name"] != name:
                raise ValueError("Conflicting pause-menu icon assignments")
            results.setdefault(enum, {"name": name, "assignment_offsets": []})["assignment_offsets"].append(value["offset"])
        for child in function["children"]:
            visit(child)

    for marker in re.finditer(rb"\x1bLua\x50", raw):
        visit(LUA["Reader"](raw, marker.start()).function())
    return results


def image_nodes(raw):
    """Observed image class hash, name property and scalar image-bank property.

    Unknown typed records are skipped, never searched past an uncertain record
    boundary. Only completely parsed records contribute to associations.
    """
    nodes = {}
    for marker in re.finditer(rb"\xdb\x84\xd2\x5b", raw):
        start = marker.start()
        if start + 12 > len(raw):
            continue
        count = struct.unpack_from(">I", raw, start + 8)[0]
        if not 1 <= count <= 64:
            continue
        cursor, props = start + 12, {}
        try:
            for _ in range(count):
                tag, kind = struct.unpack_from(">II", raw, cursor)
                cursor += 8
                if kind == 11:
                    length = struct.unpack_from(">I", raw, cursor)[0]
                    cursor += 4
                    if not 1 <= length <= 4096 or cursor + length > len(raw) or raw[cursor + length - 1] != 0:
                        raise ValueError("Invalid image-node string")
                    value = raw[cursor:cursor + length - 1].decode("ascii")
                    cursor += (length + 3) & ~3
                elif kind in (2, 5, 6, 9, 10):
                    value = struct.unpack_from(">I", raw, cursor)[0]
                    cursor += 4
                elif kind == 0x85:
                    length = struct.unpack_from(">I", raw, cursor)[0]
                    cursor += 4
                    if length > 256 or cursor + 4 * length > len(raw):
                        raise ValueError("Invalid image-node array")
                    value = None
                    cursor += 4 * length
                else:
                    raise ValueError("Unmapped image-node property type")
                if tag in props:
                    raise ValueError("Duplicate image-node property")
                props[tag] = (kind, value)
            name_kind, name = props.get(0xAE1EAD2B, (None, None))
            image_kind, bank = props.get(0x84471A83, (None, None))
            if name_kind == 11 and image_kind == 5 and 0 <= bank < 285:
                nodes.setdefault(name, []).append({"node_offset": hex(start), "image_bank": bank})
        except (ValueError, UnicodeError, struct.error):
            continue
    return nodes


def bc3_payload(data, header, index=0):
    record = 0x80 + index * 32
    if record + 32 > len(header) or data[:4] != b"IGHW" or header[:4] != b"IGHW":
        raise ValueError("Invalid texture container")
    width, height = struct.unpack_from(">HH", header, record + 24)
    offset = 0x80 + struct.unpack_from(">I", header, record)[0]
    size = ((width + 3) // 4) * ((height + 3) // 4) * 16
    if not 1 <= width <= 1024 or not 1 <= height <= 1024 or header[record + 6] & ~0x20 != 0x88 or offset + size > len(data):
        raise ValueError("Unsupported bounded BC3 texture")
    return width, height, data[offset:offset + size]


def inspect(archive_path):
    archive = PSARC["Psarc"](archive_path)
    fingerprints = {}

    def read(name, limit=3 * 1024 * 1024):
        if archive.names.count(name) != 1:
            raise ValueError("Missing/ambiguous asset: " + name)
        index = archive.names.index(name)
        if not archive.name_hashes_match[index - 1]:
            raise ValueError("Asset name digest mismatch")
        raw = archive.read_entry(index, limit)
        digest = hashlib.sha256(raw).hexdigest().upper()
        if name in HASHES and digest != HASHES[name]:
            raise ValueError("Reference asset hash mismatch: " + name)
        fingerprints[name] = {"bytes": len(raw), "sha256": digest}
        return raw

    pause = read(PAUSE_NAME)
    data = read("/processed/texpacks/hud.tp")
    header = read("/processed/texpacks/hud.tph", 8192)
    if len(header) != 0x80 + 208 * 32:
        raise ValueError("HUD descriptor count mismatch")
    hud = {}
    for index in range(208):
        width, height, pixels = bc3_payload(data, header, index)
        hud.setdefault((width, height, pixels), []).append(index)
    names, nodes = icon_assignments(pause), image_nodes(pause)
    mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
    items, unmapped = [], []
    for item in mapping["weapon_configuration"]["inventory_catalog"]:
        entry = names.get(item["enum"])
        candidates = nodes.get(entry["name"], []) if entry else []
        evidence = []
        for node in candidates:
            bank = node["image_bank"]
            bank_data = read(f"/built/anark/pause/texturebank_{bank}.bnk")
            bank_header = read(f"/built/anark/pause/texturebank_{bank}.bnkh", 8192)
            try:
                width, height, pixels = bc3_payload(bank_data, bank_header)
            except ValueError:
                continue
            matches = hud.get((width, height, pixels), [])
            if matches:
                evidence.append({**node, "hud_texture_ids": matches,
                                 "base_bc3_sha256": hashlib.sha256(pixels).hexdigest().upper()})
        texture_ids = {index for match in evidence for index in match["hud_texture_ids"]}
        if texture_ids and all(match["hud_texture_ids"] == evidence[0]["hud_texture_ids"] for match in evidence):
            items.append({"id": item["id"], "enum": item["enum"], "config_name": item["config_name"],
                          "scene_name": entry["name"], "texture_id": min(texture_ids),
                          "assignment_offsets": sorted(set(entry["assignment_offsets"])), "image_nodes": evidence})
        else:
            unmapped.append({"id": item["id"], "config_name": item["config_name"],
                             "reason": "No validated named-image BC3 match"})
    return {"build": "PS3 Tools of Destruction BCUS98127 v02.00", "confidence": "compiled-icon-assignments-and-byte-identical-image-assets",
            "scope": "Pause-menu item artwork mapped to the exact HUD atlas. Not a universal runtime icon getter, upgraded-art selection or cross-build compatibility proof.",
            "assets": fingerprints, "items": items, "unmapped": unmapped}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.archive), indent=2))
