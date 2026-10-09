"""Read-only exact-build reward cache and per-world diminishing-return ladders."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("tod_segments", Path(__file__).with_name("Inspect-TodGameplaySegments.py"))
SEGMENTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SEGMENTS)


def inspect(elf_path, save_path=None):
    elf = SEGMENTS.WORLD.PROGRESSION.BINDINGS.Elf(elf_path)
    gameplay = SEGMENTS.inspect(elf_path)
    checks = {0x2CF02C: 0x818B03F0, 0x2CF08C: 0xC3E303F8,
        0x2CF0D0: 0xD04303F8, 0x2CF0D4: 0x914303F0,
        0x2CF0C0: 0x23840004, 0x2CEC70: 0x818B03F4,
        0x2CECC4: 0xC0A303FC, 0x2CEF24: 0xD10303FC,
        0x2CEF28: 0x90A303F4, 0x2CEF14: 0x212A0004,
        0x35E03C: 0x911F03F0, 0x35E040: 0x911F03F4,
        0x35E044: 0x93BF03F8, 0x35E030: 0x93BF03FC,
        0x35E000: 0x93BF03E0, 0x35E004: 0x93BF03E4,
        0x35E008: 0x93BF03E8, 0x35E034: 0x991F0403,
        0x2CEA44: 0xC002F1A8, 0x2CEA5C: 0xC022F1AC,
        0x89F0C8: 0x3F400000, 0x89F0CC: 0x3F000000,
        0x89F0D0: 0x10026194, 0x89F0D4: 0x101EFB20}
    for address, word in checks.items():
        if elf.u32(address) != word:
            raise ValueError(f"Reward instruction/pointer shape changed at {address:#x}")
    multiplier_va = elf.u32(0x89F0D0)
    multipliers = list(struct.unpack(">5f", elf.read(multiplier_va, 20)))
    if multipliers != [1.0, 0.75, 0.5, 0.25, 0.0]:
        raise ValueError("Diminishing-return multiplier table changed")
    guards = {a: elf.read(a, 4) for a in checks}
    guards[multiplier_va] = elf.read(multiplier_va, 20)
    functions = (0x2CEA00, 0x2CEBC0, 0x2CEF70, 0x2CF218, 0x2CF4C8,
        0x2CFAB8, 0x35DFA8, 0x3842B8, 0x369AA8, 0x36A458,
        0xBA108, 0xBD0A8, 0x46BB60, 0x46AAB0, 0x4661E0, 0x4660A8)
    for address in functions:
        end = elf.functions[elf.functions.index(address) + 1]
        guards[address] = elf.read(address, end - address)
    for address in (0x12710, 0x14230):
        guards[address] = elf.read(address, 16)
    world_base = int(gameplay["segments"]["record_base"], 0)
    world_stride = int(gameplay["segments"]["world_stride"], 0)
    fields = [(0x3E0, "cached_experience_reward_total", "f32"),
        (0x3E4, "cached_bolts_reward_total", "f32"),
        (0x3E8, "cached_raritanium_reward_total", "f32"),
        (0x3F0, "bolts_reward_ladder_index", "u32"),
        (0x3F4, "raritanium_reward_ladder_index", "u32"),
        (0x3F8, "bolts_reward_ladder_remainder", "f32"),
        (0x3FC, "raritanium_reward_ladder_remainder", "f32"),
        (0x403, "reward_cache_ready", "u8")]
    report = {"confidence": "code-backed",
        "warning": "Exact USA v02.00 static evidence. Reward caches and ladder remainders are not wallet/XP balances, completion percentages or safe editable values. Experience rewards have a confirmed weapon-XP consumer; serialized heroXP418 linkage is not claimed.",
        "world_storage": {"record_base": hex(world_base), "record_stride": hex(world_stride),
            "physical_world_slots": gameplay["segments"]["initialized_world_slots"],
            "named_levels": gameplay["segments"]["native_level_count"],
            "fields": [{"offset": hex(o), "name": n, "type": t} for o, n, t in fields],
            "other_mapped_members": {"0x3ec": "Independent BE32 special-bolt collected mask; see collectibles, not a reward cache."},
            "unknown_tail_bytes": "0x404..0x407",
            "initialization": "35DFA8 clears all three cache totals, both ladder indices, both remainder float bits and cache-ready byte. Other words/bytes are not renamed."},
        "channels": [
            {"name": "experience", "runtime_attribute_id": "0xb3",
                "attribute_value_member": "0x4", "segment_accumulator_member": "0x10",
                "segment_cached_total_member": "0x1c", "world_cached_unassigned_total_member": "0x3e0",
                "evidence": "2CF218/2CFAB8 consume attribute+4 and accumulate segment+10; 2CF4C8 sums the same attribute+4 into segment+1C or unassigned world+3E0. BA108/BD0A8 send12710 result in message6A/6B float+90. 46BB60 drains both message types and passes+90 to46AAB0 ->4661E0 ->4660A8, adding to inventory-record XP+4. This confirms weapon experience rewards, not heroXP418 or a save-specific level balance."},
            {"name": "bolts", "runtime_attribute_id": "0xb3", "attribute_value_member": "0xc",
                "segment_accumulator_member": "0x14", "segment_cached_total_member": "0x20",
                "world_cached_unassigned_total_member": "0x3e4", "world_ladder_index_member": "0x3f0",
                "world_ladder_remainder_member": "0x3f8", "runtime_budget_member": "0x324",
                "evidence": "2CEF70 reads attribute+C; 2CF4C8 sums that same field into segment+20 or world+3E4. 3842B8 forwards 2CEF70 result to 369AA8, whose hero saved-block store is41C."},
            {"name": "raritanium", "runtime_attribute_id": "0xb3", "attribute_value_member": "0x10",
                "segment_accumulator_member": "0x18", "segment_cached_total_member": "0x24",
                "world_cached_unassigned_total_member": "0x3e8", "world_ladder_index_member": "0x3f4",
                "world_ladder_remainder_member": "0x3fc", "runtime_budget_member": "0x328",
                "evidence": "2CEBC0 reads attribute+10; 2CF4C8 sums that same field into segment+24 or world+3E8. 3842B8 forwards 2CEBC0 result to 36A458, whose hero saved-block store is420."}],
        "cache_lifecycle": "2CF4C8 requires loaded level_transitions configuration. With world+403 zero, it scans eligible runtime object entries, excludes per-channel absolute-value flags1/2/4 from sums, separates ten segment slots from unassigned world totals, then writes403=1. Nonzero403 reloads these saved totals, not the current object table.",
        "ladder": {"runtime_attribute_flag": "0x200", "maximum_written_index": 4,
            "multiplier_table_va": hex(multiplier_va), "multipliers": multipliers,
            "bolts_return_rule": "attribute+C * runtime config+338 * multiplier[index], then lower-bounded at1 by2CF044..2CF050; the returned amount may therefore differ from a zero multiplier.",
            "raritanium_return_rule": "attribute+10 * runtime config+33C * multiplier[index]; no corresponding minimum1 clamp in this branch.",
            "commit_rule": "Only non-preview calls add returned amount to the world remainder. If remainder >= runtime unsigned budget * current multiplier, subtract that one threshold and write min(index+1,4). One threshold per call, not a while loop; at index4 the zero threshold can retain the remainder.",
            "qualification": "The indices are read before any clamp; the observed maximum written4 is not a native malformed-save read bound. Runtime budgets/configuration are not in this save. Do not simulate current payouts or normalize unusual bits."},
        "ordinary_segment_scaling": {"function_va": "0x2cea00",
            "restart_gate": "Saved906EC nonzero via2D1860 bypasses ordinary segment scaling, returning the incoming amount.",
            "threshold_ratios": [1.0, 1.75, 2.25], "multipliers": multipliers[:4],
            "rule": "For finite nonnegative configured budget B and accumulated A, bands are A<B, B<=A<1.75B, 1.75B<=A<2.25B, A>=2.25B. Chooses multipliers1/.75/.5/.25. No player-facing difficulty name inferred."},
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        worlds = []
        for level in range(report["world_storage"]["physical_world_slots"]):
            base = world_base + level * world_stride
            values = {}
            for offset, name, kind in fields:
                size = 1 if kind == "u8" else 4
                bits = data[base+offset:base+offset+size]
                value = bits[0] if kind == "u8" else struct.unpack(">f" if kind == "f32" else ">I", bits)[0]
                values[name] = {"bits": bits.hex().upper(), "value": str(value)}
            worlds.append({"level_id": level, "offset": hex(base), "values": values,
                "indices_outside_verified_table": any(struct.unpack_from(">I", data, base+o)[0] > 4 for o in (0x3F0, 0x3F4)),
                "special_bolt_mask_raw": data[base+0x3EC:base+0x3F0].hex().upper(),
                "unknown_tail": data[base+0x404:base+0x408].hex().upper()})
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "worlds": worlds, "restart_counter": struct.unpack_from(">I", data, 0x906EC)[0]}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path, help="Plaintext working copy only; never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2, allow_nan=False))
