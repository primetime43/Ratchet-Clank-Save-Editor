"""Read-only exact-build eight-word reset-event category storage and runtime selection."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("tod_bindings", Path(__file__).with_name("Inspect-TodWeaponBindings.py"))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    checks = {0x35E198: 0x381E5528, 0x35DA1C: 0x9007020C,
        0x35D9FC: 0x38C00008, 0x35DA14: 0x396B0004,
        0x2CE534: 0x39235720, 0x2CE548: 0x80E50014,
        0x2CE550: 0x90C50014, 0x2CDC6C: 0x90690048,
        0x2CE608: 0x909F0048, 0x2CE604: 0x38800000,
        0x3BFB0: 0x38600005, 0x43578: 0x38600002,
        0x4BB04: 0x38600004, 0x55094: 0x38600006,
        0x18F4AC: 0x38600007, 0x18F4E0: 0x38600003,
        0x89F078: 0x101E8D70, 0x89F098: 0x101EFB20,
        0x89F084: 0x3E800000, 0x89F088: 0x3F800000,
        0x89F0B0: 0x10731DA0}
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Reset category instruction/pointer changed at {address:#x}")
    base = (elf.u32(0x35E198) & 65535) + (elf.u32(0x35DA1C) & 65535)
    count = elf.u32(0x35D9FC) & 65535
    stride = elf.u32(0x35DA14) & 65535
    writer_base = (elf.u32(0x2CE534) & 65535) + (elf.u32(0x2CE548) & 65535)
    if base != writer_base or base + count * stride != 0x5754:
        raise ValueError("Reset category storage boundaries disagree")
    if elf.descriptors[0x2CDC60] != 0x89FF20 or elf.descriptors[0x69B810] != 0x8AFE5C:
        raise ValueError("Reset category TOC identity changed")
    calls = [(2, 0x433B0, 0x4357C, "Signed runtime state +430 <29."),
        (3, 0x18F480, 0x18F4B4, "Runtime flags +8B0: bit800 set, bit1000 clear."),
        (4, 0x4B9E8, 0x4BB08, "Runtime state +4A4 !=2."),
        (5, 0x3BFA0, 0x3BFBC, "Unconditional selection in this virtual callback."),
        (6, 0x54FB0, 0x55098, "Runtime byte +764 zero and byte +762 nonzero."),
        (7, 0x18F480, 0x18F4B4, "Runtime flags +8B0: bits800 and1000 both set.")]
    for _, _, call, _ in calls:
        if BINDINGS.branch_target(elf.u32(call), call) != 0x132D0:
            raise ValueError("Category selection thunk call changed")
    for call, target in ((0x132DC, 0x2CDC60), (0x24ECC4, 0x69B810),
            (0x35E1AC, 0x35D9A0), (0x2CE554, 0x2D1860),
            (0x2CE63C, 0x2CE5D0), (0x2CE640, 0x2D1860)):
        if BINDINGS.branch_target(elf.u32(call), call) != target:
            raise ValueError(f"Reset category call changed at {call:#x}")
    ranges = [(0x132D0, 16), (0x24ECB8, 16), (0x2CDC60, 20),
        (0x2CE518, 0xB4), (0x2CE5D0, 0x50), (0x2CE620, 0x38),
        (0x69B810, 0x3C), (0x35D9FC, 0x28), (0x35E198, 0x20),
        (0x3BFA0, 0x6C), (0x43408, 0xC), (0x43578, 0x10),
        (0x4BAF4, 0x1C), (0x5503C, 0x18), (0x55088, 0x20),
        (0x18F480, 0x68)]
    guards = {a: elf.read(a, 4) for a in checks}
    guards.update({a: elf.read(a, size) for a, size in ranges})
    catalog = []
    for category in range(count):
        sources = [{"function_va": hex(fn), "call_va": hex(call), "condition": condition}
            for value, fn, call, condition in calls if value == category]
        catalog.append({"id": category, "label": f"Category {category} (name unknown)",
            "offset": hex(base + category * stride),
            "evidence": "Increment skipped for ID0" if category == 0 else
                "Native selection confirmed" if sources else "Storage confirmed; selection not recovered",
            "selection_sources": sources})
    report = {"confidence": "code-backed",
        "warning": "Exact USA v02.00 static evidence. Category labels, death/failure terminology, runtime time units and safe edits are unverified. These are not arena challenge success or per-challenge failure counters.",
        "storage": {"offset": hex(base), "end_exclusive": hex(base + count * stride),
            "count": count, "stride": hex(stride), "type": "u32",
            "initializer_va": "0x35d9a0", "writer_va": "0x2ce518",
            "formula": "state +5734 +4*runtime_category; ID0 skips increment; addi/stw wraps modulo32.",
            "bounds_warning": "Eight initialized words establish physical storage, not a native writer bounds check. Selector accepts its argument without range validation. Inspector reads only eight slots.",
            "gate": "Increment occurs before2D1860 restart-counter906EC gate, unlike segment+8 reset-event increment. Do not infer category sums equal segment counts or deaths."},
        "runtime": {"state_va": "0x101e8d70", "category_offset": "0x48", "countdown_offset": "0x4c",
            "setter_va": "0x2cdc60", "setter_thunk_va": "0x132d0",
            "initial_countdown": struct.unpack(">f", elf.read(0x89F084, 4))[0],
            "clear_va": "0x2ce5d0", "countdown_helper_va": "0x69b810",
            "countdown_delta_pointer_va": hex(elf.u32(0x89F0B0)), "countdown_delta_member": "0x4",
            "clear_rule": "Helper multiplies rate1 by runtime delta+4. If delta > countdown, stores zero and returns true; otherwise subtracts delta and returns false. Equality reaches zero without clearing category until a later call.2CE620 runs this before the restart gate. Units unverified.",
            "not_serialized": "101E8D70 lies outside serialized101EFB20..10280210; runtime category/countdown are not save offsets."},
        "catalog": catalog,
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "counters": [{"id": e["id"], "offset": e["offset"],
                "raw_bits": data[base+e["id"]*stride:base+(e["id"]+1)*stride].hex().upper(),
                "value": struct.unpack_from(">I", data, base+e["id"]*stride)[0]} for e in catalog],
            "saved_restart_counter": struct.unpack_from(">I", data, 0x906EC)[0]}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path, help="Plaintext working copy; never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2))
