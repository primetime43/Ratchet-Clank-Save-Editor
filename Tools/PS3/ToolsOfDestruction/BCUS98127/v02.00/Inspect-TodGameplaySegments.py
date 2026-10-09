"""Read-only exact-build gameplay segment storage and retained statistics log."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("tod_world", Path(__file__).with_name("Inspect-TodWorldState.py"))
WORLD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WORLD)


def inspect(elf_path, save_path=None):
    elf = WORLD.PROGRESSION.BINDINGS.Elf(elf_path)
    worlds = WORLD.inspect(elf_path)["worlds"]
    checks = {0x2D14E8: 0x54683032, 0x2D14EC: 0x546A2036,
        0x2D1520: 0x3BA30488, 0x35DFE4: 0x2FBD000A,
        0x35E164: 0x2FBF0014, 0x2D154C: 0x8863002C,
        0x2D1658: 0x9B9F002C, 0x2CE5A0: 0x80830008,
        0x2CE5B0: 0x90030008, 0x2CE5B4: 0x91230004,
        0x2CE730: 0xD1BF0004, 0x2CE734: 0xD05F0000,
        0x2CE3C4: 0x806A0144, 0x2CE3CC: 0x1C83009C,
        0x2CE3D4: 0x918A0144, 0x2CE3D8: 0x38C88750,
        0x2CE3E8: 0x3B9D0014, 0x2CE424: 0x38FD0054,
        0x2CE4AC: 0x90BC0098, 0x35DBB8: 0x93ACAC1C,
        0x2CF5C0: 0x887C0403, 0x2CF8E4: 0x9BBC0403,
        0x2CF1D4: 0xD0690014, 0x369ABC: 0x8009041C,
        0x369AC4: 0x9089041C, 0x36A46C: 0x80090420,
        0x36A474: 0x90890420, 0x89F098: 0x101EFB20,
        0x89F188: 0x101EFB20, 0x89F190: 0x10330610}
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Gameplay instruction/pointer shape changed at {address:#x}")
    shift = lambda a: elf.u32(a) >> 11 & 31
    stride = (1 << shift(0x2D14E8)) - (1 << shift(0x2D14EC))
    base = elf.u32(0x2D1520) & 65535
    slots = elf.u32(0x35DFE4) & 65535
    physical_worlds = elf.u32(0x35E164) & 65535
    log_stride = elf.u32(0x2CE3CC) & 65535
    signed = lambda a: WORLD.PROGRESSION.BINDINGS.signed(elf.u32(a) & 65535, 16)
    log_base = 0x10000 + signed(0x2CE3D8) + (elf.u32(0x2CE3E8) & 65535)
    count_offset = 0x10000 + (elf.u32(0x2CE3C4) & 65535)
    capacity, remainder = divmod(count_offset - log_base, log_stride)
    if remainder or capacity != 200 or base != int(worlds["record_base"], 0) or stride * slots != 0x1E0:
        raise ValueError("Unexpected gameplay record boundaries")
    functions = (0x35DD98, 0x35DFA8, 0x35D9A0, 0x35E110, 0x2D14E0,
        0x2D1538, 0x2D15C8, 0x2CDF40, 0x2CDEC0, 0x2CE328, 0x2CE518,
        0x2CE620, 0x2CF4C8, 0x2CEF70, 0x2CEBC0, 0x369AA8, 0x36A458,
        0x3842B8, 0x2782B0, 0x2782E8, 0x2C8950, 0x2C8A18)
    guards = {a: elf.read(a, 4) for a in checks}
    for f in functions:
        end = elf.functions[elf.functions.index(f) + 1]
        guards[f] = elf.read(f, end - f)
    bindings = []
    for slot, name, wrapper in ((0x89D960, "complete_segment", 0x2C8A18),
            (0x89D968, "is_segment_complete", 0x2C8950)):
        name_va, descriptor = struct.unpack(">II", elf.read(slot, 8))
        if elf.string(name_va) != name or elf.u32(descriptor) != wrapper:
            raise ValueError("Gameplay named binding changed")
        for address, size in ((slot, 8), (name_va, len(name) + 1), (descriptor, 8)):
            guards[address] = elf.read(address, size)
        bindings.append({"name": name, "registration_slot_va": hex(slot), "wrapper_va": hex(wrapper)})
    fields = [(0, "adjusted_elapsed", "f32", "Tick adds runtime delta; reset event adds current_attempt * config10FC8; finalization copies to log88 then clears."),
        (4, "current_attempt_elapsed", "f32", "Same tick delta as adjusted_elapsed; reset and finalization clear it. Time units not independently confirmed."),
        (8, "reset_events", "u32", "2CE518 increments with lwz/addi/stw, modulo32; finalization copies bits to log98. Not float despite decompiler output."),
        (12, "finalized_runtime_score", "f32", "Finalizer stores max(0, runtime baseline + runtime modifier). Not a completion percentage."),
        (16, "reward_channel_a_accumulated", "f32", "2CF218/2CFAB8 reward scaling; player-facing channel name unresolved."),
        (20, "bolts_reward_accumulated", "f32", "2CEF70 accumulates at14; consumer3842B8 calls369AA8, whose hero state store is41C (bolts). Not wallet balance."),
        (24, "raritanium_reward_accumulated", "f32", "2CEBC0 accumulates at18; consumer3842B8 calls36A458, whose hero state store is420 (raritanium). Not wallet balance."),
        (28, "cached_reward_total_a", "f32", "2CF4C8 computes and reloads this per-segment reward total."),
        (32, "cached_reward_total_b", "f32", "2CF4C8 computes and reloads this per-segment reward total."),
        (36, "cached_reward_total_c", "f32", "2CF4C8 computes and reloads this per-segment reward total."),
        (40, "unknown_28", "u32", "Initializer zeroes this word; gameplay meaning unresolved.")]
    log_fields = [(0x80, "runtime_baseline", "f32", "2CE328 copies runtime101E8D70+0 after recalculation."),
        (0x84, "post_reset_timing_modifier", "f32", "2CDD20 result using zeroed elapsed time and configuration24/28/2C."),
        (0x88, "adjusted_elapsed", "f32", "Copies segment+0 before reset; no time-unit conversion applied."),
        (0x8C, "configured_reference_time", "f32", "Copies runtime segment configuration+20, not save data."),
        (0x90, "runtime_accumulated_time", "f32", "Runtime2CDBF8+0 after adding this segment's threshold-adjusted time."),
        (0x94, "runtime_accumulated_reference", "f32", "Runtime2CDBF8+4 after adding configuration+20."),
        (0x98, "reset_events", "u32", "Raw copy of segment+8 via lwz/stw; integer counter, not seventh float.")]
    encode = lambda entries: [{"offset": hex(o), "name": n, "type": t, "comment": c} for o, n, t, c in entries]
    report = {"confidence": "code-backed", "warning": "Exact USA v02.00 static evidence; no new editable fields or runtime compatibility claims. Segment names/slot association require loaded configuration; slot order is not a planet mission list.",
        "segments": {"record_base": hex(base), "world_stride": worlds["record_stride"],
            "native_level_count": worlds["native_level_count"], "initialized_world_slots": physical_worlds,
            "slots_per_world": slots, "record_stride": hex(stride), "fields": encode(fields),
            "complete_offset": hex(elf.u32(0x2D154C) & 65535),
            "complete_chain": ["0x2c8a18", "0x2782e8", "0x2d15c8", "0x2ce328"],
            "check_chain": ["0x2c8950", "0x2782b0", "0x2d1538", "0x2d14e0"],
            "unknown_tail": "Bytes2D..2F are preserved, not proven padding; word28 remains unknown. Twenty physical worlds initialized, only19 named native levels.",
            "replay_rule": "Tick/reset/finalizer paths skip segment updates when2D1860 is true. complete_segment still writes2C after calling finalizer; flag alone does not prove a log append.",
            "world_reward_cache_ready_member": hex(elf.u32(0x2CF5C0) & 65535),
            "opaque_arrays": [{"offset": "0x1e0", "size": "0x100"}, {"offset": "0x2e0", "size": "0x100"}]},
        "log": {"offset": hex(log_base), "record_stride": hex(log_stride), "count_offset": hex(count_offset),
            "bounded_physical_slots": capacity, "fields": encode(log_fields),
            "warning": "200 slots are the structural span up to saved count, not an established writer bounds check. Native finalizer increments count before writing. Initialization resets count but does not clear log entries: retained bytes beyond count are not active progress. Malformed counts clipped for reading only."},
        "named_bindings": bindings,
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        def values(offset, entries):
            return {n: {"bits": data[offset+o:offset+o+4].hex().upper(),
                "value": str(struct.unpack_from(">f" if t == "f32" else ">I", data, offset+o)[0])}
                for o, n, t, _ in entries}
        count = struct.unpack_from(">I", data, count_offset)[0]
        segments = []
        for level in range(physical_worlds):
            for slot in range(slots):
                offset = base + level * int(worlds["record_stride"], 0) + slot * stride
                segments.append({"level_id": level, "slot": slot, "offset": hex(offset),
                    "complete_byte": data[offset+0x2C], "unknown_tail": data[offset+0x2D:offset+stride].hex().upper(),
                    "values": values(offset, fields)})
        logs = []
        for slot in range(capacity):
            offset = log_base + slot * log_stride
            nonzero = any(data[offset:offset+log_stride])
            logs.append({"slot": slot, "offset": hex(offset), "within_saved_count": slot < count,
                "nonzero": nonzero, "location": data[offset:offset+64].split(b"\0")[0].decode("ascii", "replace"),
                "segment": data[offset+64:offset+128].split(b"\0")[0].decode("ascii", "replace"), "values": values(offset, log_fields)})
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "saved_log_count": count, "count_exceeds_physical_span": count > capacity,
            "nonzero_retained_entries": sum(e["nonzero"] and not e["within_saved_count"] for e in logs),
            "segments": segments, "log_entries": logs}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path, help="Plaintext working copy; never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2, allow_nan=False))
