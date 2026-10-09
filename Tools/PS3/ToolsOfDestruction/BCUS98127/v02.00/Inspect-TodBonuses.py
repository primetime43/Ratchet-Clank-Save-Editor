"""Read-only exact-build blueprint and cheat/bonus research; stdout only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("progression", Path(__file__).with_name("Inspect-TodProgression.py"))
PROGRESSION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROGRESSION)


def inspect(elf_path, save_path=None):
    elf = PROGRESSION.BINDINGS.Elf(elf_path)
    checks = {0x27378: 0x3C860001, 0x27384: 0x800486F4,
        0x27AFA8: 0x900B86F4, 0x27AFBC: 0x64830007, 0x27AFC0: 0x6060DEE4,
        0x35D450: 0x812331CC, 0x270D0: 0x392986F0, 0x270E4: 0x88640008,
        0x35D480: 0x3880000E, 0x35D488: 0x392331D0,
        0x35D494: 0x900331E0, 0x35D484: 0x38000348,
        0x35CA20: 0x54653032, 0x35CA28: 0x54662036,
        0x35CA38: 0x80690008, 0x35CA58: 0x8069000C,
        0x888624: 0x101EFB20, 0x898F50: 0x101EFB20,
        0x888680: 0x101F5048, 0x898FF4: 0x101F5048,
        0x35CA24: 0x800219EC, 0x8A190C: 0x10026384}
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Instruction/pointer shape changed at {address:#x}")
    signed = PROGRESSION.BINDINGS.signed
    state_base = elf.u32(0x888624)
    subobject_base = elf.u32(0x888680)
    mask_offset = 0x10000 + signed(elf.u32(0x27384) & 65535, 16)
    if subobject_base + (elf.u32(0x35D450) & 65535) != state_base + mask_offset:
        raise ValueError("Blueprint count and ownership storage disagree")
    all_mask = ((elf.u32(0x27AFBC) & 65535) << 16) | (elf.u32(0x27AFC0) & 65535)
    states_base = 0x10000 + signed(elf.u32(0x270D0) & 65535, 16) + (elf.u32(0x270E4) & 65535)
    count = elf.u32(0x35D480) & 65535
    score_offset = subobject_base - state_base + (elf.u32(0x35D494) & 65535)
    table_slot = elf.descriptors[0x35CA20] + signed(elf.u32(0x35CA24) & 65535, 16)
    table = elf.u32(table_slot)
    stride = (1 << (elf.u32(0x35CA20) >> 11 & 31)) - (1 << (elf.u32(0x35CA28) >> 11 & 31))
    enums = PROGRESSION.exports(elf, 0x28440, "CHEAT_", 0x12990)
    if [e["id"] for e in enums] != list(range(count + 1)) or enums[-1]["enum"] != "CHEAT_COUNT":
        raise ValueError("Incomplete cheat enum catalog")
    catalog = []
    for item in enums[:-1]:
        address = table + item["id"] * stride
        words = struct.unpack(">12I", elf.read(address, stride))
        if words[3] > 8:
            raise ValueError("Cheat state-name array exceeds physical capacity")
        catalog.append({"id": item["id"], "enum": item["enum"], "name_va": item["name_va"],
            "state_offset": hex(states_base + item["id"]), "definition_va": hex(address),
            "title_lookup_id": words[0], "description_lookup_id": words[1],
            "score_requirement": words[2], "state_count": words[3], "state_name_lookup_ids": list(words[4:])})
    functions = [0x27370, 0x273A0, 0x37580, 0x27A5D8, 0x27A608, 0x27AF90,
        0x27AFB0, 0x35D450, 0x35D480, 0x27A638, 0x27A648, 0x27A678,
        0x27008, 0x27098, 0x27108, 0x24ED8, 0x24F18, 0x25020,
        0x35CA20, 0x35CA40, 0x35CA88, 0x35CD68, 0x35CBF0,
        0x24F80, 0x25110, 0x25088, 0x5BFE08]
    guards = {a: elf.read(a, 4) for a in checks}
    for function in functions:
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    for thunk in (0x12D50, 0x10E10, 0x11C50, 0x13E20, 0x11900, 0x13520, 0x13890):
        guards[thunk] = elf.read(thunk, 16)
    guards[table] = elf.read(table, count * stride)
    for item in enums:
        for key in ("name_slot_va", "name_load_va", "value_slot_va", "value_load_va", "value_move_va", "export_call_va"):
            address = int(item[key], 0)
            guards[address] = elf.read(address, 4)
        address = int(item["name_va"], 0)
        guards[address] = elf.read(address, len(item["enum"]) + 1)
    bindings = [(0x88957C, "get_num_blueprints", 0x2F408), (0x889584, "has_blueprint", 0x2F330),
        (0x889D78, "has_blueprint", 0x38140), (0x89DF18, "hero_get_blueprints", 0x2BA668),
        (0x89DF20, "hero_has_blueprint", 0x2BA520), (0x89DF28, "hero_give_blueprint", 0x2BA3F8),
        (0x89DF30, "hero_give_all_blueprints", 0x2BA318), (0x88965C, "get_num_cheats", 0x2D930),
        (0x889664, "is_cheat_unlocked", 0x2D858), (0x88966C, "get_cheat_name", 0x2D780),
        (0x889674, "get_cheat_desc", 0x2D6A8), (0x88969C, "get_cheat_state_name", 0x2D130),
        (0x88967C, "get_cheat_value", 0x2D598),
        (0x889684, "get_num_cheat_states", 0x2D488), (0x88968C, "get_cheat_state", 0x2D378),
        (0x889694, "set_cheat_state", 0x2D260), (0x89DE80, "enable_all_cheats", 0x2BBC90),
        (0x89DE88, "set_cheat_state", 0x2BBB78), (0x89DE90, "set_cheat_points", 0x2BBAB8)]
    named = []
    for slot, name, wrapper in bindings:
        name_va, descriptor = struct.unpack(">II", elf.read(slot, 8))
        if elf.string(name_va) != name or elf.u32(descriptor) != wrapper:
            raise ValueError("Named script binding changed")
        guards[slot], guards[descriptor] = elf.read(slot, 8), elf.read(descriptor, 8)
        guards[name_va] = elf.read(name_va, len(name) + 1)
        end = elf.functions[elf.functions.index(wrapper) + 1]
        guards[wrapper] = elf.read(wrapper, end - wrapper)
        named.append({"name": name, "registration_slot_va": hex(slot), "wrapper_va": hex(wrapper)})
    report = {"confidence": "code-backed", "warning": "Static exact USA build and save observations; no new editing permissions or in-game acceptance claim.",
        "blueprints": {"mask_offset": hex(mask_offset), "type": "uint32 BE", "all_grant_mask": f"0x{all_mask:08X}",
            "all_grant_ids": [i for i in range(32) if all_mask & (1 << i)],
            "predicate_va": "0x27370", "hero_predicate_va": "0x27a5d8", "grant_va": "0x27af90", "grant_all_va": "0x27afb0", "count_va": "0x35d450",
            "semantics": "ID i tests integer bit i. Native slw uses six low shift bits: 32..63 yield zero, 64 aliases0; this is not bounds validation. Individual grant ORs a bit; grant-all ORs its fixed mask and preserves all other bits. Count popcounts all32 bits, not just the grant-all mask.",
            "warning": "Thirteen IDs are present in the native grant-all mask. Their physical pickup locations and association with LEVEL IDs are not established; do not label bits as planets or normalize unknown bits."},
        "cheats": {"state_base": hex(states_base), "count": count, "type": "uint8", "score_offset": hex(score_offset),
            "definition_table_va": hex(table), "definition_stride": hex(stride), "catalog": catalog,
            "getter_va": "0x27098", "setter_va": "0x27008", "raw_setter_va": "0x27a648", "unlock_va": "0x27108", "enable_all_va": "0x35d480",
            "semantics": "Physical states are14 bytes86F8..8705. Menu APIs conditionally remap IDs>4 toID+1 when runtime5BFE08()!=1; the enum IDs and saved slots are not interchangeable with every menu index. Setter stores0 or states1..8 (menu truncates input tolow8 first); this global bound is not each definition's state count. Availability compares saved weighted score8708 unsigned against a mode-adjusted definition threshold, NOT against the state byte.",
            "enable_all": {"score_written": elf.u32(0x35D484) & 65535,
                "semantics": "Writes score840 at8708, then replaces zero state bytes with1; nonzero bytes and skill-point mask8710 are not changed. It does NOT award all skill points or prove each bonus active."},
            "warning": "Runtime mode meaning, localized names/state labels and gameplay behavior are not recovered. State0 alone does not mean locked. Score thresholds are direct native definition entries, not an asserted current menu availability."},
        "named_bindings": named, "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        if Path(save_path).stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save layout")
        data = Path(save_path).read_bytes()
        if any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        mask = struct.unpack_from(">I", data, mask_offset)[0]
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "blueprint_mask": f"0x{mask:08X}", "native_blueprint_count": mask.bit_count(),
            "all_grant_bits_present": mask & all_mask == all_mask, "outside_grant_mask": f"0x{mask & ~all_mask:08X}",
            "states": list(data[states_base:states_base + count]), "score": struct.unpack_from(">I", data, score_offset)[0],
            "uninterpreted_8706_8707": data[states_base + count:score_offset].hex().upper()}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path, help="Plaintext working copy only; originals are never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2))
