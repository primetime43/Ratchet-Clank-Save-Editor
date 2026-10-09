"""Read-only exact-build world flags, mission counters and quick-select research."""
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
    checks = {0x279F8: 0x5468502A, 0x27A00: 0x54671838,
        0x27A0C: 0x38A60880, 0x27A18: 0x88030009,
        0x24AE4: 0x38A60880, 0x24AF0: 0x88030008,
        0x36A44: 0x38C70488, 0x36A7C: 0x88690402,
        0x2D0DF0: 0x54663830, 0x2D0DF8: 0x5467103A,
        0x2D0E00: 0x3C850001, 0x2D0E08: 0x39230AF8,
        0x2D0F04: 0x80630078, 0x1E2774: 0x1CC70484,
        0x1E27F0: 0x39400018, 0x1E27F4: 0x397A0284,
        0x1E2730: 0x2C850017,
        0x888624: 0x101EFB20, 0x889AF4: 0x101EFB20,
        0x89550C: 0x101EFB20, 0x89F16C: 0x101EFB20}
    # Fixed-build shape guards precede displacement decoding; no guessed layouts.
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Instruction/pointer shape changed at {address:#x}")
    shift = lambda address: elf.u32(address) >> 11 & 31
    stride = (1 << shift(0x279F8)) + (1 << shift(0x27A00))
    flags_base = elf.u32(0x27A0C) & 65535
    visited = flags_base + (elf.u32(0x27A18) & 65535)
    unlocked = (elf.u32(0x24AE4) & 65535) + (elf.u32(0x24AF0) & 65535)
    world_base = elf.u32(0x36A44) & 65535
    excluded = world_base + (elf.u32(0x36A7C) & 65535)
    mission_stride = (1 << shift(0x2D0DF0)) - (1 << shift(0x2D0DF8))
    mission_base = ((elf.u32(0x2D0E00) & 65535) << 16) + (elf.u32(0x2D0E08) & 65535)
    completed_member = elf.u32(0x2D0F04) & 65535
    quick_base = elf.u32(0x1E27F4) & 65535
    automatic_slots = elf.u32(0x1E27F0) & 65535
    # Membership/removal both iterate 32 words; retain all, not just insertable24.
    loop_counts = [word & 65535 for _, word in elf.instructions(0x1E22A8, 0x1E22F8)
        if word >> 26 == 14 and word >> 16 & 31 == 0 and word & 65535 == 32]
    if len(loop_counts) != 1:
        raise ValueError("Unexpected quick-select removal bound")
    catalog = [{"id": v["id"], "enum": v["enum"],
        "unlocked_offset": hex(unlocked + stride * v["id"]),
        "visited_offset": hex(visited + stride * v["id"]),
        "menu_exclusion_offset": hex(excluded + stride * v["id"]),
        "missions_completed_offset": hex(mission_base + completed_member + mission_stride * v["id"])} for v in levels[:-1]]
    guards = {a: elf.read(a, 4) for a in checks}
    functions = (0x279F8, 0x24AD0, 0x36A10, 0x36AC8, 0x37460, 0x36FC0,
        0x2D0EF0, 0x2D0DF0, 0x1E26F0, 0x1E22A8, 0x1E22F8,
        0x288988, 0x288888)
    for function in functions:
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    for thunk in (0x12470, 0x252B08, 0x252ED8):
        guards[thunk] = elf.read(thunk, 16)
    named = []
    bindings = [(0x8894C4, "is_level_unlocked", 0x30768),
        (0x8894CC, "is_level_visited", 0x30690),
        (0x889C90, "is_level_visitable", 0x39BA0),
        (0x889C98, "is_level_visible", 0x39AC8),
        (0x889CA0, "is_level_seen", 0x399F0),
        (0x889CC8, "get_level_missions_completed", 0x395A0),
        (0x89DFCC, "hero_add_quick_select", 0x2B8780),
        (0x89DFD4, "hero_remove_quick_select", 0x2B8650)]
    for slot, name, wrapper in bindings:
        name_va, descriptor = struct.unpack(">II", elf.read(slot, 8))
        if elf.string(name_va) != name or elf.u32(descriptor) != wrapper:
            raise ValueError("Named binding changed")
        for address, length in ((slot, 8), (descriptor, 8), (name_va, len(name) + 1),
                (wrapper, elf.functions[elf.functions.index(wrapper) + 1] - wrapper)):
            guards[address] = elf.read(address, length)
        named.append({"name": name, "registration_slot_va": hex(slot), "wrapper_va": hex(wrapper)})
    for v in levels:
        for key in ("name_slot_va", "name_load_va", "value_slot_va", "value_load_va", "value_move_va", "export_call_va"):
            address = int(v[key], 0)
            guards[address] = elf.read(address, 4)
        address = int(v["name_va"], 0)
        guards[address] = elf.read(address, len(v["enum"]) + 1)
    report = {"confidence": "code-backed", "warning": "Exact USA v02.00 static code; storage values are not an in-game completion or travel-eligibility verdict. No editing permissions inferred.",
        "worlds": {"record_base": hex(world_base), "record_stride": hex(stride), "native_level_count": 19,
            "unlocked_offset": hex(unlocked), "visited_offset": hex(visited), "menu_exclusion_offset": hex(excluded),
            "flag_type": "uint8, nonzero predicate",
            "menu_rule": "36A10 requires a nonzero level ID, unlocked byte nonzero and exclusion byte zero. Level3 is suppressed when recursive level18 eligibility is true; visible36AC8 delegates to this rule. Seen37460 reads the same saved byte as visited279F8.",
            "warning": "Byte402 has a proven exclusion role, not a recovered gameplay name. Byte403 and other record members remain unknown. Initialized slot19 is not a native level.", "catalog": catalog},
        "missions": {"record_base": hex(mission_base), "record_stride": hex(mission_stride), "completed_member": hex(completed_member),
            "completed_offset": hex(mission_base + completed_member), "type": "uint32 BE",
            "named_chain": ["0x395a0", "0x36fc0", "0x12470", "0x2d0ef0", "0x2d0df0"],
            "warning": "Menu getter remaps level3 to18 when native level18 visibility is true. Rows expose unremapped storage for IDs0..18. Entry fields are documented separately in mission_lists; this count alone does not resolve runtime titles or a trustworthy completion percentage."},
        "quick_select": {"offset": hex(quick_base), "word_count": loop_counts[0], "word_stride": 4,
            "type": "int32 BE item IDs; -1 is empty", "automatic_insert_slots": automatic_slots,
            "player_state_stride": hex(elf.u32(0x1E2774) & 65535),
            "add_chain": ["0x2b8780", "0x288988", "0x252b08", "0x1e26f0"],
            "remove_chain": ["0x2b8650", "0x288888", "0x252ed8", "0x1e22a8"],
            "warning": "Membership/removal search all32 words, while insertion accepts/searches slots0..23 and filters item config flags0x1040. These are stored slot indices, not a proven UI wheel order. Player0 block only; additional player-index validity not inferred."},
        "named_bindings": named,
        "instruction_guards": [{"va": hex(a), "bytes": value.hex().upper()} for a, value in sorted(guards.items())]}
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "worlds": [{"id": v["id"], "unlocked_byte": data[int(v["unlocked_offset"], 0)],
                "visited_byte": data[int(v["visited_offset"], 0)], "menu_exclusion_byte": data[int(v["menu_exclusion_offset"], 0)],
                "missions_completed": struct.unpack_from(">I", data, int(v["missions_completed_offset"], 0))[0]} for v in catalog],
            "quick_select": list(struct.unpack_from(f">{loop_counts[0]}i", data, quick_base))}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path, help="Plaintext working copy only; originals are never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2))
