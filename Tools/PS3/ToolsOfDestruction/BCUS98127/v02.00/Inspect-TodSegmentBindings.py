"""Exact-build mission lookup IDs and literal shipped-script calls, read-only.

Runtime segment name-to-slot tables are deliberately not guessed from log order.
The compiled Lua reader only decodes bytes; it never runs a script or game code.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    # Dataclass-based archive module needs its module present during loading.
    import sys
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


MISSIONS = module("tod_binding_missions", Path(__file__).with_name("Inspect-TodMissions.py"))
ROOT = MISSIONS.PROGRESSION.BINDINGS.ROOT
PATTERN = re.compile(r"L\d+_(LABEL|DESC)_MISSION_\w+")


def exports(elf, function, target):
    """Only contiguous lwz r4 / lfs f1 / bl registration triplets."""
    end = elf.functions[elf.functions.index(function) + 1]
    toc = elf.descriptors[function]
    result = {}
    for address in range(function, end - 8, 4):
        name_load, value_load, call = struct.unpack(">3I", elf.read(address, 12))
        if name_load >> 16 != 0x8082 or value_load >> 16 != 0xC022:
            continue
        if MISSIONS.PROGRESSION.BINDINGS.branch_target(call, address + 8) != target or not call & 1:
            continue
        name_slot = toc + MISSIONS.PROGRESSION.BINDINGS.signed(name_load & 65535, 16)
        value_slot = toc + MISSIONS.PROGRESSION.BINDINGS.signed(value_load & 65535, 16)
        name_va = elf.u32(name_slot)
        name = elf.string(name_va)
        if not PATTERN.fullmatch(name):
            continue
        value = struct.unpack(">f", elf.read(value_slot, 4))[0]
        if not value.is_integer() or not 0 <= value <= 0xFFFFFF or name in result:
            raise ValueError("Unexpected mission numeric export")
        result[name] = {"id": int(value), "load_va": hex(address),
            "name_slot_va": hex(name_slot), "value_slot_va": hex(value_slot),
            "name_va": hex(name_va)}
    return result


def literal_calls(function):
    """Recognize only local straight-line GETGLOB/LOADBOOL/LOADK argument runs.

    A control-flow target inside the run rejects it. No symbolic VM execution,
    source-comment interpretation, condition evaluation or dynamic calls.
    """
    instructions = function["instructions"]
    targets = {i["jump_pc"] for i in instructions if "jump_pc" in i}
    result = []
    for index, call in enumerate(instructions):
        if call["op"] != "CALL" or call["b"] not in (3, 5) or call["c"] != 1:
            continue
        count, base = call["b"], call["a"]
        if index < count:
            continue
        run = instructions[index-count:index]
        if any(i["pc"] in targets for i in run[1:]) or call["pc"] in targets:
            continue
        if any(i["a"] != base + n for n, i in enumerate(run)):
            continue
        if run[0]["op"] != "GETGLOBAL" or run[0].get("constant") not in ("add_mission", "complete_mission"):
            continue
        if (run[0]["constant"] == "add_mission") != (count == 5):
            continue
        if any(i["op"] != "GETGLOBAL" for i in run[1:4 if count == 5 else 3]):
            continue
        if count == 5 and (run[-1]["op"] != "LOADBOOL" or run[-1]["c"] != 0):
            continue
        row = {"api": run[0]["constant"], "level_enum": run[1]["constant"],
            "title_enum": run[2]["constant"], "lua_function": function["path"],
            "call_offset": call["offset"]}
        if count == 5:
            row.update(description_enum=run[3]["constant"], optional=bool(run[4]["b"]))
        result.append(row)
    for child in function["children"]:
        result.extend(literal_calls(child))
    return result


def inspect(elf_path, save_path=None, archive_path=None):
    elf = MISSIONS.PROGRESSION.BINDINGS.Elf(elf_path)
    primary = exports(elf, 0x294E90, 0x252EB8)
    secondary = exports(elf, 0x80848, 0x12990)
    if len(primary) != 162 or {n: v["id"] for n, v in primary.items()} != {n: v["id"] for n, v in secondary.items()}:
        raise ValueError("Independent mission registration catalogs disagree")
    if len({v["id"] for v in primary.values()}) != len(primary):
        raise ValueError("Unexpected duplicate mission numeric ID")
    guards = {}
    for catalog in (primary, secondary):
        for item in catalog.values():
            for key, size in (("load_va", 12), ("name_slot_va", 4), ("value_slot_va", 4)):
                address = int(item[key], 0)
                guards[address] = elf.read(address, size)
    for function in (0x2D18C8, 0x2D1928, 0x2D1A08, 0x2A7680, 0x2776D8, 0x6A7CC0):
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    for thunk in (0x12990, 0x252EB8):
        if MISSIONS.PROGRESSION.BINDINGS.branch_target(elf.u32(thunk + 12), thunk + 12) != 0x6A7CC0:
            raise ValueError("Numeric global export thunk changed")
        guards[thunk] = elf.read(thunk, 16)
    # Coalesce tiny neighboring checks, retaining every checked byte plus the
    # short intervening instruction/table bytes. Never bridge unmapped segments.
    ranges = []
    for address, raw in sorted(guards.items()):
        end = address + len(raw)
        if ranges and address <= ranges[-1][1] + 16:
            ranges[-1][1] = max(ranges[-1][1], end)
        else:
            ranges.append([address, end])
    guards = {start: elf.read(start, end - start) for start, end in ranges}
    pairs = []
    for name, title in primary.items():
        if "_LABEL_" not in name:
            continue
        desc_name = name.replace("_LABEL_", "_DESC_")
        if desc_name not in primary:
            raise ValueError("Unpaired native mission lookup export")
        pairs.append({"title_lookup_id": title["id"], "description_lookup_id": primary[desc_name]["id"],
            "title_enum": name, "description_enum": desc_name,
            "primary_title_load_va": title["load_va"],
            "secondary_title_load_va": secondary[name]["load_va"]})
    report = {"confidence": "code-backed", "warning": "Exact USA v02.00 native numeric exports, not localized titles, a fixed mission slot order, a completion percentage or in-game edit validation.",
        "native_mission_lookup_pairs": sorted(pairs, key=lambda p: p["title_lookup_id"]),
        "lookup_provenance": "294E90 exports numeric globals through252EB8; independent80848 exports identical162 symbols/values through12990. add_mission wrapper2A7680 passes Lua arguments2/3 through2776D8 to the saved title/description list fields mapped in mission_lists.",
        "segment_slot_limit": "2D18C8 hashes a string modulo49;2D1928 reads a loaded runtime hash table memberC8;2D1A08 resolves a loaded index through runtime name pointers. None establishes names for all ten saved slots. Retained statistics-log order is not a slot catalog.",
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        observed = MISSIONS.inspect(elf_path, save_path)["save_observation"]
        titles = {p["title_lookup_id"]: p for p in pairs}
        for level in observed["levels"]:
            for kind in ("active", "completed"):
                for entry in level[kind]["entries"]:
                    pair = titles.get(entry["title_lookup_id"])
                    entry["title_enum"] = pair["title_enum"] if pair else None
                    entry["description_enum"] = next((p["description_enum"] for p in pairs if p["description_lookup_id"] == entry["description_lookup_id"]), None)
                    entry["export_pair_matches"] = bool(pair and pair["description_lookup_id"] == entry["description_lookup_id"])
        report["save_observation"] = observed
    if archive_path is not None:
        psarc = module("tod_binding_psarc", ROOT / "Tools/Inspect-Psarc.py").Psarc(archive_path)
        lua = module("tod_binding_lua", ROOT / "Tools/Inspect-Lua50.py")
        names = {p["title_enum"]: p for p in pairs}
        levels = {v["enum"]: v["id"] for v in MISSIONS.PROGRESSION.exports(elf, 0x28440, "LEVEL_", 0x12990)}
        assets = []
        for index, name in enumerate(psarc.names):
            if not name or not name.endswith("/scripts/missions.lc"):
                continue
            raw = psarc.read_entry(index, 1024 * 1024)
            reader = lua.Reader(raw)
            function = reader.function()
            if reader.pos != len(raw):
                raise ValueError("Trailing compiled mission script bytes")
            calls = literal_calls(function)
            for call in calls:
                pair = names.get(call["title_enum"])
                call["level_id"] = levels.get(call["level_enum"])
                call["title_lookup_id"] = pair["title_lookup_id"] if pair else None
                if call["api"] == "add_mission":
                    call["description_lookup_id"] = primary.get(call["description_enum"], {}).get("id")
                    call["export_pair_matches"] = bool(pair and pair["description_enum"] == call["description_enum"])
            assets.append({"entry_index": index, "path": name, "size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest().upper(), "literal_calls": calls})
        report["asset_observation"] = {"warning": "Selected compiled missions.lc scripts only; literal call sites establish argument relationships, not execution or a complete mission list. Unrecognized globals remain unresolved rather than guessed.", "assets": assets}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path, help="Read-only original global_cached.psarc")
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save, args.archive), indent=2))
