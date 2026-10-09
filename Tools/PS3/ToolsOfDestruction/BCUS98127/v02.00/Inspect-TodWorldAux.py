"""Read-only exact-build world initialization footprint and opaque-byte ownership."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("bindings", Path(__file__).with_name("Inspect-TodWeaponBindings.py"))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)


def runs(offsets):
    """Coalesce a byte ownership set into half-open ranges."""
    result = []
    for offset in sorted(offsets):
        if result and result[-1][1] == offset:
            result[-1][1] += 1
        else:
            result.append([offset, offset + 1])
    return [{"start": hex(a), "end_exclusive": hex(b), "size": b-a} for a, b in result]


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}
    def keep(address, size):
        guards[address] = elf.read(address, size)
    def require(address, expected):
        if elf.u32(address) != expected:
            raise ValueError(f"World initialization shape changed at {address:#x}")
        keep(address, 4)

    # Decode the complete leaf initializer, rejecting unrecognized writes.
    zeros, segment_writes, word28 = set(), [], None
    end = elf.functions[elf.functions.index(0x35DD98)+1]
    keep(0x35DD98, end-0x35DD98)
    for va, word in elf.instructions(0x35DD98, end):
        op, reg, base = word >> 26, word >> 21 & 31, word >> 16 & 31
        if op == 14 and base == 0 and word & 65535 == 0:
            zeros.add(reg)
        elif op in (36, 38) and base == 3 and reg in zeros:
            offset, size = word & 65535, 4 if op == 36 else 1
            segment_writes.append({"offset": hex(offset), "size": size, "value": 0, "write_va": hex(va)})
            if offset == 0x28:
                word28 = va
        elif word not in (0x4E800020, 0x60000000):
            raise ValueError(f"Unexpected segment initializer instruction at {va:#x}")
    segment_bytes = {b for w in segment_writes for b in range(int(w["offset"], 0), int(w["offset"], 0)+w["size"])}
    if segment_bytes != set(range(0x2D)) or word28 != 0x35DDA0:
        raise ValueError("Segment write boundary changed")

    # Guard the observed world loop and both fill-call argument sequences.
    for va, word in {
        0x35DFC8: 0x57A62036, 0x35DFCC: 0x57A53032,
        0x35DFE0: 0x4BFFFDB9, 0x35DFE4: 0x2FBD000A,
        0x35DFEC: 0x395F01E0, 0x35DFF0: 0x3BA00000,
        0x35DFF4: 0x79430020, 0x35DFF8: 0x38800000,
        0x35DFFC: 0x38A00100, 0x35E00C: 0x4BEF492D,
        0x35E014: 0x393F02E0, 0x35E018: 0x38800000,
        0x35E01C: 0x79230020, 0x35E020: 0x38A00100,
        0x35E024: 0x4BEF4915, 0x35E02C: 0x39000000,
        0x35E140: 0x57E61838, 0x35E144: 0x57E7502A,
        0x35E154: 0x38640488, 0x35E15C: 0x4BFFFE4D,
        0x35E164: 0x2FBF0014,
        0x35E50C: 0x80621A64, 0x35E510: 0x3CA00009,
        0x35E518: 0x3886FD08, 0x35E51C: 0x60A506F0,
        0x35E534: 0x4BEF3EF5, 0x35E72C: 0x80821A64,
        0x35E734: 0x3CA00009, 0x35E738: 0x3BA3FD08,
        0x35E73C: 0x60A506F0, 0x35E744: 0x4BEF3CE5,
        0x8A1984: 0x101EFB20}.items():
        require(va, word)
    world_end = elf.functions[elf.functions.index(0x35DFA8)+1]
    keep(0x35DFA8, world_end-0x35DFA8)
    zero_registers, world_writes = set(), []
    for va, word in elf.instructions(0x35DFA8, world_end):
        op, reg, base = word >> 26, word >> 21 & 31, word >> 16 & 31
        if op == 14 and base == 0 and word & 65535 == 0:
            zero_registers.add(reg)
        elif op == 14:
            zero_registers.discard(reg)
        if op in (36, 38) and base == 31:
            if reg not in zero_registers:
                raise ValueError("World initializer has a nonzero/unknown store")
            world_writes.append({"offset": hex(word & 65535), "size": 4 if op == 36 else 1, "value": 0, "write_va": hex(va)})
    slots = elf.u32(0x35DFE4) & 65535
    segment_stride = (1 << (elf.u32(0x35DFCC) >> 11 & 31)) - (1 << (elf.u32(0x35DFC8) >> 11 & 31))
    fill_ranges = [{"start": hex(elf.u32(a) & 65535), "size": elf.u32(b) & 65535, "fill_value": 0,
                    "call_va": hex(c)} for a, b, c in ((0x35DFEC, 0x35DFFC, 0x35E00C), (0x35E014, 0x35E020, 0x35E024))]
    world_bytes = {slot*segment_stride+b for slot in range(slots) for b in segment_bytes}
    for entry in fill_ranges + world_writes:
        start = int(entry.get("start", entry.get("offset")), 0)
        world_bytes.update(range(start, start+entry["size"]))
    world_stride = (1 << (elf.u32(0x35E144) >> 11 & 31)) + (1 << (elf.u32(0x35E140) >> 11 & 31))
    untouched = set(range(world_stride))-world_bytes
    expected_holes = {slot*0x30+b for slot in range(10) for b in range(0x2D, 0x30)} | set(range(0x404, 0x408))
    if world_stride != 0x408 or untouched != expected_holes:
        raise ValueError("World opaque-byte footprint changed")
    base, count = elf.u32(0x35E154) & 65535, elf.u32(0x35E164) & 65535
    report = {"confidence": "code-backed",
        "warning": "Byte ownership and specific initializer/copy boundaries only. Untouched bytes are not proven padding, unused, or preserved by every game lifecycle. No new editable fields or new semantic name for segment28.",
        "storage": {"world_base": hex(base), "world_stride": hex(world_stride), "physical_world_slots": count,
            "named_world_slots": 19, "segments_per_world": slots, "segment_stride": hex(segment_stride)},
        "segment_initializer": {"function_va": "0x35dd98", "zero_stores": segment_writes,
            "written_ranges": runs(segment_bytes), "untouched_range": "0x2d..0x2f",
            "word28": {"offset": "0x28", "write_va": hex(word28), "write_type": "BE32 zero store",
                "meaning": "Unresolved four-byte word. A zero integer-width store does not establish a logical integer, float or flag meaning."}},
        "world_initializer": {"function_va": "0x35dfa8", "array_caller_va": "0x35e110",
            "fill_ranges": fill_ranges, "zero_stores": world_writes,
            "written_bytes_per_world": len(world_bytes), "untouched_ranges": runs(untouched),
            "untouched_bytes_per_world": len(untouched), "untouched_bytes_all_worlds": len(untouched)*count,
            "ownership_correction": "World3C0..3DF belongs to the final32 bytes of the existing spawn-suppression bitset2E0..3DF, not separate scalar words. World3EC is the already-confirmed special-bolt mask, not an unknown reward word.",
            "scope": "Calling35DFA8 on an existing record leaves each segment2D..2F and world404..407 untouched. A staging allocation may have prior unspecified bytes; this is not a claim that restart retains the previous live-save values."},
        "full_copy": {"snapshot_va": "0x35e710", "restore_va": "0x35e508", "size": "0x906f0",
            "manager_buffer_offset": "0x1fd08", "state_pointer_slot_va": "0x8a1984",
            "rule": "Snapshot and initial restore full-size copies include word28 and all680 opaque tail bytes, without interpreting them. Restore has subsequent side effects; full-copy coverage is not proof every later path leaves bytes untouched."},
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i*0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        worlds = []
        for level in range(count):
            offset = base+level*world_stride
            segments = []
            for slot in range(slots):
                p = offset+slot*segment_stride
                raw = data[p+0x28:p+0x2C]
                segments.append({"slot": slot, "offset": hex(p), "word28_hex": raw.hex().upper(),
                    "word28_unsigned_interpretation": struct.unpack(">I", raw)[0],
                    "word28_float_interpretation": str(struct.unpack(">f", raw)[0]),
                    "tail_hex": data[p+0x2D:p+0x30].hex().upper()})
            worlds.append({"level_id": level, "offset": hex(offset), "segments": segments,
                "world_tail_hex": data[offset+0x404:offset+0x408].hex().upper()})
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(), "worlds": worlds,
            "warning": "Alternative numeric interpretations preserve raw bits and do not rename word28. These bytes are observations, not inferred active progress."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path, help="Plaintext working copy; never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2, allow_nan=False))
