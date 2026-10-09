"""Read-only exact-build active/completed mission lists; never resolves guessed titles."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("tod_progression", Path(__file__).with_name("Inspect-TodProgression.py"))
PROGRESSION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROGRESSION)


def inspect(elf_path, save_path=None):
    elf = PROGRESSION.BINDINGS.Elf(elf_path)
    levels = PROGRESSION.exports(elf, 0x28440, "LEVEL_", 0x12990)
    if [v["id"] for v in levels] != list(range(20)) or levels[-1]["enum"] != "LEVEL_COUNT":
        raise ValueError("Unexpected native level catalog")
    checks = {0x2D0D60: 0x54663830, 0x2D0D68: 0x5467103A,
        0x2D0D70: 0x3C850001, 0x2D0D78: 0x39230148,
        0x2D0E00: 0x3C850001, 0x2D0E08: 0x39230AF8,
        0x2D0DDC: 0x80630078, 0x2D0E40: 0x57E9103A,
        0x2D0E44: 0x57E42036, 0x2D1220: 0x2B850009,
        0x25E18: 0x80A30008, 0x25E1C: 0x68A30002,
        0x25E60: 0x80A30008, 0x25E64: 0x54A007FE,
        0x89F16C: 0x101EFB20}
    for address, value in checks.items():
        if elf.u32(address) != value:
            raise ValueError(f"Instruction/pointer shape changed at {address:#x}")
    shift = lambda address: elf.u32(address) >> 11 & 31
    list_stride = (1 << shift(0x2D0D60)) - (1 << shift(0x2D0D68))
    active = ((elf.u32(0x2D0D70) & 65535) << 16) + (elf.u32(0x2D0D78) & 65535)
    completed = ((elf.u32(0x2D0E00) & 65535) << 16) + (elf.u32(0x2D0E08) & 65535)
    count_member = elf.u32(0x2D0DDC) & 65535
    entry_stride = (1 << shift(0x2D0E44)) - (1 << shift(0x2D0E40))
    capacity = (elf.u32(0x2D1220) & 65535) + 1
    if capacity * entry_stride != count_member or completed - active != 20 * list_stride:
        raise ValueError("Unexpected mission list boundary")
    guards = {a: elf.read(a, 4) for a in checks}
    functions = (0x2D0D60, 0x2D0D88, 0x2D0DC8, 0x2D0DF0, 0x2D0EB0,
        0x2D0EF0, 0x2D0E18, 0x2D0F18, 0x2D0F78, 0x2D1168,
        0x25DF0, 0x25E38, 0x25E80, 0x25EC8, 0x27CA8, 0x27B40,
        0x2776B0, 0x2776D8)
    for function in functions:
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    for thunk in (0x11D30, 0x137C0, 0x12470):
        guards[thunk] = elf.read(thunk, 16)
    bindings = [(0x889474, "get_num_missions", 0x311C0),
        (0x88947C, "is_mission_complete", 0x31098),
        (0x889484, "is_mission_optional", 0x30F70),
        (0x88948C, "is_mission_available", 0x30E48),
        (0x889494, "get_mission_name", 0x30D20),
        (0x88949C, "get_mission_desc", 0x30BF8),
        (0x89E6A0, "add_mission", 0x2A7680),
        (0x89E6A8, "complete_mission", 0x2A7568)]
    named = []
    for slot, name, wrapper in bindings:
        name_va, descriptor = struct.unpack(">II", elf.read(slot, 8))
        if elf.string(name_va) != name or elf.u32(descriptor) != wrapper:
            raise ValueError("Named mission binding changed")
        for address, length in ((slot, 8), (descriptor, 8), (name_va, len(name) + 1),
                (wrapper, elf.functions[elf.functions.index(wrapper) + 1] - wrapper)):
            guards[address] = elf.read(address, length)
        named.append({"name": name, "registration_slot_va": hex(slot), "wrapper_va": hex(wrapper)})
    report = {"confidence": "code-backed", "warning": "Exact USA v02.00; saved list storage and native API meanings, not an in-game completion percentage. No new edit permissions; runtime titles not recovered.",
        "active_base": hex(active), "completed_base": hex(completed), "list_stride": hex(list_stride),
        "physical_lists_per_group": 20, "native_levels": 19, "capacity_per_list": capacity,
        "count_member": hex(count_member), "entry_stride": hex(entry_stride),
        "entry_fields": {"0x0": "Title lookup ID and native search key", "0x4": "Description lookup ID", "0x8": "Flags word uint32 BE"},
        "flags": {"optional_mask": 1, "complete_mask": 2, "available_rule": "inverse of complete bit", "unknown_mask": "0xfffffffc"},
        "indexing": "Script mission indices are one-based. Native combined getter subtracts1, selects active entries first by saved active count, then completed entries. The inspector bounds reads to the physical10 entries per list, never executes unsafe native indexing, and excludes unnamed physical slot19.",
        "transactions": "Add rejects duplicate title IDs across both lists, requires active count<10, appends title/description/low8 flag bits. Complete copies title/description from active to completed, ORs completed bit2 into destination flags, increments completed count, decrements active count and compacts active entries. This path does not visibly copy all source flags or independently guard completed capacity; no repair inferred.",
        "catalog": [{"id": v["id"], "enum": v["enum"], "active_offset": hex(active + list_stride * v["id"]),
            "completed_offset": hex(completed + list_stride * v["id"])} for v in levels[:-1]],
        "named_bindings": named,
        "instruction_guards": [{"va": hex(a), "bytes": value.hex().upper()} for a, value in sorted(guards.items())]}
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        def decode(base):
            count = struct.unpack_from(">I", data, base + count_member)[0]
            entries = []
            for slot in range(min(count, capacity)):
                title, desc, flags = struct.unpack_from(">3I", data, base + entry_stride * slot)
                entries.append({"slot": slot, "title_lookup_id": title, "description_lookup_id": desc,
                    "flags": f"0x{flags:08x}", "optional": bool(flags & 1), "complete": bool(flags & 2),
                    "available": not bool(flags & 2), "unknown_flags": f"0x{flags & ~3:08x}"})
            return {"saved_count": count, "exceeds_capacity": count > capacity, "entries": entries}
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "levels": [{"id": v["id"], "active": decode(int(v["active_offset"], 0)),
                "completed": decode(int(v["completed_offset"], 0))} for v in report["catalog"]]}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path, help="Plaintext working copy only; originals are never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2))
