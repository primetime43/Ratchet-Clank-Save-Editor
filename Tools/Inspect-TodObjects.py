"""Read-only exact-build native object catalog and three saved counter arrays."""
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
    objects = PROGRESSION.exports(elf, 0x28440, "OBJ_", 0x12990)
    other = PROGRESSION.exports(elf, 0x294E90, "OBJ_", 0x252EB8)
    if [v["id"] for v in objects] != list(range(24)) or objects[-1]["enum"] != "OBJ_TYPE_COUNT":
        raise ValueError("Unexpected native object catalog")
    if [(v["id"], v["enum"]) for v in objects] != [(v["id"], v["enum"]) for v in other]:
        raise ValueError("Object enum export registrations disagree")
    checks = {0x23D8E4: 0x80031A68, 0x23D8E8: 0x38A60300,
        0x23D8F4: 0x80690004, 0x23D8F8: 0x7C6307B4,
        0x23D884: 0x388A0360, 0x23D880: 0x396A03B0,
        0x23D8B0: 0x80CC000C, 0x23D8CC: 0x7C054840,
        0x23D8D0: 0x4C800020, 0x23D95C: 0x2F800000,
        0x23D960: 0x419E0008, 0x23E73C: 0x81227C00,
        0x23E744: 0x913F1A68, 0x897B38: 0x101EFB20}
    for address, value in checks.items():
        if elf.u32(address) != value:
            raise ValueError(f"Instruction/pointer shape changed at {address:#x}")
    current = (elf.u32(0x23D8E8) & 65535) + (elf.u32(0x23D8F4) & 65535)
    peak = elf.u32(0x23D884) & 65535
    additions = (elf.u32(0x23D880) & 65535) + (elf.u32(0x23D8B0) & 65535)
    guards = {a: elf.read(a, 4) for a in checks}
    for function in (0x23D870, 0x23D8E0, 0x23D900, 0x23D940, 0x23D970,
            0x288A98, 0x288B80, 0x288C58, 0x288D40):
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    for thunk in (0x2509B8, 0x24FC88, 0x252F78, 0x24F7B8):
        guards[thunk] = elf.read(thunk, 16)
    bindings = [(0x89DFAC, "hero_has_object", 0x2B8D60),
        (0x89DFB4, "hero_add_object", 0x2B8BE8),
        (0x89DFBC, "hero_get_num_objects", 0x2B8A70),
        (0x89DFC4, "hero_set_num_objects", 0x2B88F8)]
    named = []
    for slot, name, wrapper in bindings:
        name_va, descriptor = struct.unpack(">II", elf.read(slot, 8))
        if elf.string(name_va) != name or elf.u32(descriptor) != wrapper:
            raise ValueError("Named object binding changed")
        for address, length in ((slot, 8), (descriptor, 8), (name_va, len(name) + 1),
                (wrapper, elf.functions[elf.functions.index(wrapper) + 1] - wrapper)):
            guards[address] = elf.read(address, length)
        named.append({"name": name, "registration_slot_va": hex(slot), "wrapper_va": hex(wrapper)})
    for obj in objects:
        for key in ("name_slot_va", "name_load_va", "value_slot_va", "value_load_va", "value_move_va", "export_call_va"):
            address = int(obj[key], 0)
            guards[address] = elf.read(address, 4)
        address = int(obj["name_va"], 0)
        guards[address] = elf.read(address, len(obj["enum"]) + 1)
    report = {"confidence": "code-backed", "warning": "Exact USA v02.00 static native object APIs; not proof of gameplay usability, units, safe bounds or edited-load acceptance.",
        "count": len(objects) - 1, "word_stride": 4,
        "current_offset": hex(current), "peak_offset": hex(peak), "positive_additions_offset": hex(additions),
        "current_type": "signed int32 BE returned by native getter; raw bits retained",
        "peak_type": "uint32 BE, unsigned high-water comparison",
        "positive_additions_type": "32-bit integer bits, increments only for signed delta >0",
        "get_chain": ["0x2b8a70", "0x288b80", "0x24fc88", "0x23d8e0"],
        "has_chain": ["0x2b8d60", "0x288d40", "0x24f7b8", "0x23d940"],
        "set_chain": ["0x2b88f8", "0x288a98", "0x2509b8", "0x23d970"],
        "add_chain": ["0x2b8be8", "0x288c58", "0x252f78", "0x23d870"],
        "semantics": "Set writes current and raises peak only by unsigned comparison, without changing positive additions. Add wraps current32 bits, adds signed-positive deltas to additions32 bits, then raises peak by unsigned comparison. Has tests nonzero, including negative current values. These are not unique pickup totals; timer/arena enum names do not establish units or conversion rules.",
        "catalog": [{"id": v["id"], "enum": v["enum"], "name_va": v["name_va"], "export_call_va": v["export_call_va"],
            "current_offset": hex(current + 4 * v["id"]), "peak_offset": hex(peak + 4 * v["id"]),
            "positive_additions_offset": hex(additions + 4 * v["id"])} for v in objects[:-1]],
        "named_bindings": named,
        "instruction_guards": [{"va": hex(a), "bytes": value.hex().upper()} for a, value in sorted(guards.items())]}
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "current": list(struct.unpack_from(">23i", data, current)),
            "peak": list(struct.unpack_from(">23I", data, peak)),
            "positive_additions": list(struct.unpack_from(">23I", data, additions))}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path, help="Plaintext working copy only; originals are never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2))
