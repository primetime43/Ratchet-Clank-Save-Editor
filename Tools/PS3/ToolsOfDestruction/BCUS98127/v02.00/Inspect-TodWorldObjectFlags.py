"""Read-only exact-build per-world object-state and spawn-suppression bitsets."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("tod_world", Path(__file__).with_name("Inspect-TodWorldState.py"))
WORLD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WORLD)


def bit_location(offset, slot):
    """Physical BE64 storage mapping; never treats a runtime UID as an index."""
    if type(slot) is not int or not 0 <= slot < 2048:
        raise ValueError("Object slot outside physical2048-bit capacity")
    word = offset + slot // 64 * 8
    return {"word_offset": hex(word), "word_bit": slot % 64,
        "byte_offset": hex(word + 7 - slot % 64 // 8), "byte_mask": 1 << (slot % 8)}


def inspect(elf_path, save_path=None):
    elf = WORLD.PROGRESSION.BINDINGS.Elf(elf_path)
    world = WORLD.inspect(elf_path)["worlds"]
    checks = {0x35DFEC: 0x395F01E0, 0x35DFFC: 0x38A00100,
        0x35E014: 0x393F02E0, 0x35E020: 0x38A00100,
        0x35E164: 0x2FBF0014, 0x2F77D0: 0x5469502A,
        0x2F77D4: 0x54671838, 0x2F77D8: 0x616CAAAB,
        0x2F77EC: 0x7CAA3E70, 0x2F77F0: 0x39030668,
        0x2F7800: 0x54EBE8F8, 0x2F7804: 0x54FD06BE,
        0x2F7810: 0x7CA44B78, 0x2F7788: 0x7D242878,
        0x2F7894: 0xE8A90008, 0x2F7898: 0x7CA4EC36,
        0x2F7950: 0x546003DE, 0x2F7990: 0x380B0100,
        0x2F799C: 0x39830668, 0x2F79B4: 0x7D074B78,
        0x2F7A3C: 0xA01D0042, 0x2F7A64: 0x2F800001,
        0x2F7A7C: 0x2F000002, 0x2F7A88: 0x896B0014,
        0x2F7AC0: 0xEBA70008, 0x2F7AD4: 0x68630001,
        0x89FC64: 0x1064FC80, 0x89FC68: 0x101EFB20,
        0x89FC74: 0x1064FC80, 0x89FC78: 0x101EFB20,
        0x89FC7C: 0x10330610,
        0x2D1868: 0x3D240009, 0x2D186C: 0x800906EC}
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Object-bitset instruction/pointer shape changed at {address:#x}")
    shift = lambda address: elf.u32(address) >> 11 & 31
    world_stride = (1 << shift(0x2F77D0)) + (1 << shift(0x2F77D4))
    member_a = elf.u32(0x35DFEC) & 65535
    member_b = elf.u32(0x35E014) & 65535
    size = elf.u32(0x35DFFC) & 65535
    base = int(world["record_base"], 0)
    offset_a = elf.u32(0x2F77F0) & 65535
    offset_b = (elf.u32(0x2F799C) & 65535) + (elf.u32(0x2F7990) & 65535)
    if world_stride != int(world["record_stride"], 0) or offset_a != base + member_a or offset_b != base + member_b or size != (elf.u32(0x35E020) & 65535):
        raise ValueError("Inconsistent object-bitset initialization/access boundaries")
    words = size // 8
    restart_offset = (elf.u32(0x2D1868) & 65535) * 65536 + (elf.u32(0x2D186C) & 65535)
    functions = (0x2F7720, 0x2F77A8, 0x2F7830, 0x2F7930, 0x2F79E0,
        0x2F8690, 0x2DD588, 0x2DD698, 0x3BEB78, 0x35DFA8, 0x2D1860)
    guards = {a: elf.read(a, 4) for a in checks}
    for f in functions:
        end = elf.functions[elf.functions.index(f) + 1]
        guards[f] = elf.read(f, end - f)
    bands = [{"id": "recorded_object_state", "label": "Recorded object state", "member": hex(member_a), "offset": hex(offset_a),
        "clear_va": "0x2f7720", "set_va": "0x2f77a8", "check_va": "0x2f7830",
        "meaning": "Saved per-object lifecycle state. Restore2DD698 checks the bit before invoking2DD588; object initialization3BEB78 selects alternate state when set. Not universally a dead/killed flag; object-specific meaning and runtime names unresolved."},
        {"id": "spawn_suppression", "label": "Spawn suppression (mode1)", "member": hex(member_b), "offset": hex(offset_b),
        "set_va": "0x2f7930", "load_predicate_va": "0x2f79e0",
        "meaning": "Writer sets the object-slot bit only when runtime object+68 flag10000 is set. Native load-definition mode1 admits the object only when its saved bit is clear. Other modes follow different rules; not an unconditional present/absent verdict."}]
    report = {"confidence": "code-backed", "warning": "Exact USA v02.00 static evidence, not gameplay-validated edits. Physical slots are runtime pool indices, not object UIDs, inventory IDs, collectible names or a completion percentage. No new editing controls.",
        "record_base": hex(base), "world_stride": hex(world_stride), "native_level_count": world["native_level_count"],
        "initialized_world_slots": elf.u32(0x35E164) & 65535, "bitset_size": hex(size),
        "word_count": words, "bits_per_word": 64, "physical_bits_per_bitset": size * 8,
        "byte_mapping": "word=offset+8*(slot//64); byte=word+7-(slot%64)//8; mask=1<<(slot%8)",
        "bitsets": bands,
        "runtime_index": {"object_pool_pointer_slot_va": "0x89fc64", "object_pool_va": "0x1064fc80",
            "entry_stride": "0x180", "calculation": "For an aligned runtime object-entry pointer, (pointer - *object_pool)/0x180. Assembly uses signed shift7 then low32 multiplyAAAAAAAB, dividing the remaining factor3.",
            "warning": "Only aligned valid runtime entries justify division. Native leaves do not establish the2048-slot bounds check. Do not compute indices from arbitrary pointers or stored UID values."},
        "load_modes": {"mode_member": "0x42", "mode1": "Return saved spawn-suppression bit clear; loader2F8690 skips records when predicate is false.",
            "mode2": "Runtime checkpoint mask44 blocks a segment; otherwise use load-definition byte40 before saved segment completion, byte41 after completion. Segment complete byte is world+slot*30+2C. Runtime checkpoint is not serialized.",
            "other_modes": "Predicate returns true; this is not the whole loader's acceptance/availability logic."},
        "segment_update_gate": {"counter_offset": hex(restart_offset), "predicate_va": "0x2d1860",
            "rule": "Saved restart-counter nonzero predicate gates segment tick/reset/log finalization. Nonzero skips those updates. Named game-mode terminology remains unverified; do not equate this predicate to a separately confirmed replay flag."},
        "instruction_guards": [{"va": hex(a), "bytes": value.hex().upper()} for a, value in sorted(guards.items())]}
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        rows = []
        for level in range(report["initialized_world_slots"]):
            for band in bands:
                offset = int(band["offset"], 0) + level * world_stride
                raw = list(struct.unpack_from(f">{words}Q", data, offset))
                slots = [slot for slot in range(size * 8) if raw[slot // 64] & (1 << (slot % 64))]
                rows.append({"level_id": level, "bitset": band["id"], "offset": hex(offset),
                    "set_slots": slots, "set_count": len(slots), "raw_be64_words": [f"{v:016X}" for v in raw]})
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "saved_restart_counter": struct.unpack_from(">I", data, restart_offset)[0], "bitsets": rows}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path, help="Plaintext working copy only; never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2))
