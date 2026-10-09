"""Read-only, exact-build ToD progression research. Never executes game code."""
import argparse
import bisect
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("tod_bindings", Path(__file__).with_name("Inspect-TodWeaponBindings.py"))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)


def exports(elf, start, prefix, target):
    """Observed lfs/fmr/name-load/export sequences, not a general disassembler."""
    toc = elf.descriptors[start]
    end = elf.functions[bisect.bisect_right(elf.functions, start)]
    floating, name, result = {}, None, []
    for address, word in elf.instructions(start, end):
        opcode, register, base = word >> 26, word >> 21 & 31, word >> 16 & 31
        if opcode == 48 and base == 2:
            slot = toc + BINDINGS.signed(word & 65535, 16)
            floating[register] = (struct.unpack(">f", elf.read(slot, 4))[0], slot, address, address)
        elif opcode == 63 and (word >> 1 & 1023) == 72:
            source = word >> 11 & 31
            if source in floating:
                value, slot, load, _ = floating[source]
                floating[register] = (value, slot, load, address)
            else:
                floating.pop(register, None)
        elif opcode == 32 and register == 4 and base == 2:
            slot = toc + BINDINGS.signed(word & 65535, 16)
            pointer = elf.u32(slot)
            try:
                name = (elf.string(pointer), pointer, slot, address)
            except (ValueError, UnicodeError):
                name = None
        elif opcode == 18 and word & 1:
            if BINDINGS.branch_target(word, address) == target and name and name[0].startswith(prefix):
                if 1 not in floating or not floating[1][0].is_integer():
                    raise ValueError("Unresolved enum value")
                value, slot, load, move = floating[1]
                result.append({"id": int(value), "enum": name[0], "name_va": hex(name[1]),
                    "name_slot_va": hex(name[2]), "name_load_va": hex(name[3]),
                    "value_slot_va": hex(slot), "value_load_va": hex(load),
                    "value_move_va": hex(move), "export_call_va": hex(address)})
            floating = {r: v for r, v in floating.items() if r >= 14}
            name = None
    return result


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    skills = exports(elf, 0x294E90, "SKILLPOINT_", 0x252EB8)
    armor = exports(elf, 0x28440, "ARMOR_", 0x12990)
    if len(skills) != 61 or [s["id"] for s in skills] != list(range(61)) or skills[-1]["enum"] != "SKILLPOINT_COUNT":
        raise ValueError("Incomplete skill-point enum catalog")
    if len(armor) != 6 or [a["id"] for a in armor] != list(range(6)) or armor[-1]["enum"] != "ARMOR_TYPE_COUNT":
        raise ValueError("Incomplete armor enum catalog")
    table = elf.u32(0x89FF20 + 0x1A6C)
    if table != 0x10026654:
        raise ValueError("Skill definition table moved")
    catalog = []
    for item in skills[:-1]:
        address = table + item["id"] * 16
        points, name_tag, description_tag, unknown = struct.unpack(">IIII", elf.read(address, 16))
        catalog.append({**item, "definition_va": hex(address), "points": points,
            "name_tag": name_tag, "description_tag": description_tag, "unknown_definition_0c": unknown})
    guard_addresses = [0x897B38, 0x23E73C, 0x23E744, 0x898FF4, 0x27A6DC,
        0x27A6E4, 0x898F50, 0x27A700, 0x27A73C, 0x27A748, 0x27A750,
        0x27A754, 0x27A764, 0x35D61C, 0x35D63C, 0x35D640, 0x35D64C,
        0x35D678, 0x35D680, 0x35EB04, 0x35EB0C, 0x27360,
        0x89F1B8, 0x2D240C, 0x2D2418, 0x1E2144, 0x1E2170, 0x1E2190,
        0x2D2440, 0x2D247C, 0x2D2490, 0x89F1DC, 0x2D2684,
        0x1E25B8, 0x1E25C8, 0x1E2630, 0x1E2658, 0x1E2670,
        0x895518, 0x89551C, 0x895520, 0x895524,
        0x251524, 0x2D073C, 0x2D0744, 0x2D02F8,
        0x2D186C, 0x23E754, 0x23E76C, 0x23E0F4,
        0x2B1D8, 0x2B1EC, 0x2E7D8, 0x2E6B0, 0x11F6C, 0x1054C, 0x35EBA4, 0x35ED0C]
    guards = {a: elf.read(a, 4) for a in guard_addresses}
    for item in skills + armor:
        for key in ("name_slot_va", "name_load_va", "value_slot_va", "value_load_va", "value_move_va", "export_call_va"):
            a = int(item[key], 0)
            guards[a] = elf.read(a, 4)
        a = int(item["name_va"], 0)
        guards[a] = elf.read(a, len(item["enum"]) + 1)
    guards[table] = elf.read(table, 60 * 16)
    report = {"confidence": "code-backed",
        "warning": "Exact USA v02.00 ELF. Static meanings and observed save values are not gameplay-tested edit permissions. Preserve opaque bits and independent state.",
        "hero_state_pointer": {"initializer_va": "0x0023E650", "hero_member_offset": "0x1A68", "pointer_slot_va": "0x00897B38", "state_va": "0x101EFB20"},
        "skill_points": {"count": 60, "score_offset": "0x8708", "bits_offset": "0x8710", "bits_size": 8,
            "bit_order": "Big-endian uint64; native ID i is integer bit i, NOT byte i/8 from the start. IDs60..63 are uninterpreted.",
            "setter_va": "0x0035D5D0", "predicate_va": "0x0027A700", "score_getter_va": "0x00027358",
            "definitions_va": hex(table), "definition_stride": 16, "definition_value_getter_va": "0x0035EB00",
            "total_definition_points": sum(s["points"] for s in catalog), "catalog": catalog,
            "name_ui_getter_va": "0x0035EB70", "description_ui_getter_va": "0x0035ECD8",
            "automatic_completion": "After a newly earned ID other than59, the setter tests IDs0..58 and awards ID59 SKILLPOINT_HARDCORE when all are set. Already-set IDs return without adding points."},
        "armor": {"count": 5, "ownership_offset": "0x444", "ownership_stride": 4, "ownership_type": "uint32 BE, nonzero predicate",
            "equipped_offset": "0x458", "unlock_offset": "0x5774", "unlock_stride": 1,
            "ownership_predicate_va": "0x002D2400", "availability_va": "0x002D2440", "equipped_getter_va": "0x001E2140",
            "equipped_setter_va": "0x001E2150", "purchase_va": "0x002D26D0", "unlock_update_va": "0x002D2588",
            "catalog": armor[:-1], "warning": "Availability getter can set ID4 unlock byte when word906EC is nonzero. Equipping also marks ownership and updates a runtime armor attribute. Do not equate unlock, ownership and equipped ID."},
        "bolt_multiplier": {"offset": "0x428", "type": "float32 BE", "getter_va": "0x001E2568", "update_va": "0x001E25F0",
            "observed_update_min": 1, "observed_update_max": 20, "step": 1,
            "warning": "Update path clamps to1..20 and getter can reset to1 based on runtime state. This is not a validated editable-save range.",
            "consumer_va": "0x002D0058", "consumer_call_va": "0x002D073C", "consumer_multiply_va": "0x002D02F8"},
        "additional_leads": {"offset_418": "Named hero_set_xp binding confirms serialized integer hero XP; full chain and byte evidence are in collectibles.hero_xp. Runtime health and level are distinct.",
            "offset_906ec": "Nonzero predicate2D1860 gates multiplier updates and final-armor availability; restart3CED40 increments/clamps it. Named challenge/playthrough count remains a candidate."},
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        if Path(save_path).stat().st_size != 0x906F0:
            raise ValueError("Unrecognized plaintext save size")
        data = Path(save_path).read_bytes()
        if any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        bits = int.from_bytes(data[0x8710:0x8718], "big")
        completed = [s["id"] for s in catalog if bits & (1 << s["id"])]
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(), "size": len(data),
            "skill_score": struct.unpack_from(">I", data, 0x8708)[0], "skill_bits_hex": f"{bits:016X}",
            "completed_ids": completed, "completed_count": len(completed),
            "score_from_definitions": sum(catalog[i]["points"] for i in completed),
            "unknown_skill_bits_hex": f"{bits & ~((1 << 60) - 1):016X}",
            "armor_ownership": list(struct.unpack_from(">5I", data, 0x444)),
            "equipped_armor": struct.unpack_from(">I", data, 0x458)[0],
            "armor_unlock_bytes": list(data[0x5774:0x5779]),
            "bolt_multiplier": struct.unpack_from(">f", data, 0x428)[0],
            "unknown_progression_418": struct.unpack_from(">I", data, 0x418)[0],
            "restart_counter_candidate": struct.unpack_from(">I", data, 0x906EC)[0]}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path, help="Plaintext GAME.SAV only; inputs are never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2))
