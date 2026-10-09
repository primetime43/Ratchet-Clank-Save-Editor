"""Read-only exact-build hero XP, special-bolt and skin research; stdout only."""
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
    elf = PROGRESSION.BINDINGS.Elf(elf_path)  # full reference hash, before pointer reads
    levels = PROGRESSION.exports(elf, 0x28440, "LEVEL_", 0x12990)
    skins = PROGRESSION.exports(elf, 0x28440, "SKIN_", 0x12990)
    if [v["id"] for v in levels] != list(range(20)) or levels[-1]["enum"] != "LEVEL_COUNT":
        raise ValueError("Unexpected level enum catalog")
    if [v["id"] for v in skins] != list(range(10)) or skins[-1]["enum"] != "SKIN_TYPE_COUNT":
        raise ValueError("Unexpected skin enum catalog")

    # Assembly-verified instruction shapes; displacements are decoded, not inferred
    # from nearby sample values. r2-changing thunks are included in byte evidence.
    checks = {0x25D10: 0x547D502A, 0x25D18: 0x546C1838,
        0x25D24: 0x390A0488, 0x35DDD8: 0x812303EC,
        0x35DEB0: 0x2B84001F, 0x35DEE8: 0x912303EC,
        0x25DDC: 0x80890424, 0x25DE0: 0x7C641850,
        0x23E0F4: 0x91690418, 0x26FEC: 0x93E90480,
        0x24B14: 0x38A60450, 0x24B20: 0x8003000C,
        0x888624: 0x101EFB20, 0x89F158: 0x10062E4C, 0x895854: 0x00840B00}
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Instruction/pointer shape changed at {address:#x}")
    stride = (1 << (elf.u32(0x25D10) >> 11 & 31)) + (1 << (elf.u32(0x25D18) >> 11 & 31))
    base = elf.u32(0x25D24) & 65535
    mask_member = elf.u32(0x35DDD8) & 65535
    mask_offset = base + mask_member
    totals_va, costs_va = elf.u32(0x89F158), elf.u32(0x895854)
    totals = list(struct.unpack(">19I", elf.read(totals_va, 19 * 4)))
    compact = lambda v: {key: v[key] for key in ("id", "enum", "name_va", "export_call_va")}
    catalog = [{**compact(v), "total": totals[v["id"]], "mask_offset": hex(mask_offset + v["id"] * stride)} for v in levels[:-1]]
    skin_catalog = [{**compact(v), "cost": elf.u32(costs_va + v["id"] * 16), "definition_va": hex(costs_va + v["id"] * 16)} for v in skins[:-1]]

    # Complete bounded code ranges preserve both control flow and TOC restores.
    ranges = [(0x25CF0, 0xFC), (0x35DDD8, 0x28), (0x35DE08, 0x28),
        (0x35DEB0, 0xBC), (0x119B0, 16), (0x10D70, 16), (0x2D0898, 16),
        (0x24B08, 0x30), (0x24B38, 0x38), (0x26FC0, 0x48),
        (0x27AA0, 0xA0), (0x1F0D60, 16), (0x28A9B0, 0x140),
        (0x252C78, 16), (0x23E090, 0xA0), (0x23E73C, 0x34),
        (0x2BAFB8, 0x14), (0x2A2E9C, 16),
        (totals_va, 19 * 4), (costs_va, 9 * 16)]
    guards = {address: elf.read(address, length) for address, length in ranges}
    for function in (0x25CF0, 0x25DB8, 0x35DDD8, 0x35DE08, 0x35DEB0,
            0x2D0898, 0x24B08, 0x24B38, 0x26FC0, 0x27AA0, 0x1F0D60,
            0x28A9B0, 0x23E090):
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    for address in checks:
        guards.setdefault(address, elf.read(address, 4))
    for item in levels + skins:
        for key in ("name_slot_va", "name_load_va", "value_slot_va", "value_load_va", "value_move_va", "export_call_va"):
            address = int(item[key], 0)
            guards[address] = elf.read(address, 4)
        address = int(item["name_va"], 0)
        guards[address] = elf.read(address, len(item["enum"]) + 1)
    bindings = [(0x8894A4, "get_special_bolts_collected", 0x30AE8),
        (0x8894AC, "get_special_bolts_total", 0x309D8),
        (0x8894B4, "get_special_bolts_owned", 0x308F8),
        (0x8894EC, "purchase_skin", 0x30330), (0x8894F4, "is_skin_available", 0x30258),
        (0x8894FC, "is_skin_owned", 0x30180), (0x889504, "select_skin", 0x300A8),
        (0x88950C, "get_skin_cost", 0x2FF98), (0x89DEE0, "hero_set_xp", 0x2BAED0)]
    named = []
    for slot, name, wrapper in bindings:
        name_va, descriptor = struct.unpack(">II", elf.read(slot, 8))
        if elf.string(name_va) != name or elf.u32(descriptor) != wrapper:
            raise ValueError("Named script binding changed")
        guards[slot] = elf.read(slot, 8)
        guards[descriptor] = elf.read(descriptor, 8)
        guards[name_va] = elf.read(name_va, len(name) + 1)
        # Include the wrapper in full, not just its prologue.
        end = elf.functions[elf.functions.index(wrapper) + 1]
        guards[wrapper] = elf.read(wrapper, end - wrapper)
        named.append({"name": name, "name_va": hex(name_va), "registration_slot_va": hex(slot), "wrapper_va": hex(wrapper)})

    report = {"confidence": "code-backed", "warning": "Exact USA v02.00 static code and save observations; no new editing permissions or in-game acceptance claim.",
        "hero_xp": {"offset": hex(elf.u32(0x23E0F4) & 65535), "type": "uint32 BE",
            "named_chain": ["0x2baed0", "0x28a9b0", "0x252c78", "0x23e090"],
            "warning": "Serialized integer XP, not current health. Runtime fractional accumulator and calculated level are outside this field; no maximum or safe edit bounds inferred."},
        "special_bolts": {"record_base": hex(base), "record_stride": hex(stride), "initialized_records": 20,
            "level_count": 19, "mask_member": hex(mask_member), "mask_offset": hex(mask_offset), "mask_type": "uint32 BE",
            "bit_order": "Local collectible ID i is BE32 integer bit i (0..31), file byte maskOffset+3-i//8 and mask1<<(i%8). Count helper counts all set bits, including unexpected ones.",
            "count_va": "0x35ddd8", "predicate_va": "0x35de08", "setter_va": "0x35deb0",
            "total_table_va": hex(totals_va), "total_getter_va": "0x2d0898", "shipped_total": sum(totals),
            "collected_getter_va": "0x25cf0", "owned_getter_va": "0x25db8", "spent_offset": hex(elf.u32(0x25DDC) & 65535),
            "balance_formula": "sum(popcount(mask) for native levels0..18) minus saved spent word424, with native signed-32 subtraction; never clamp or repair.",
            "all_collected_award": "Setter awards skill ID46 SKILLPOINT_GOLDEN when every native per-level count is >= its shipped total.",
            "warning": "Initialized slot19 is not a level: LEVEL_COUNT19 requests a sum over0..18. Bits do not identify physical pickup positions. Menu remaps level3 to18 under a native condition.", "catalog": catalog},
        "skins": {"count": 9, "ownership_offset": "0x45c", "ownership_stride": 4,
            "ownership_predicate_va": "0x24b08", "selected_offset": "0x480", "select_va": "0x26fc0",
            "purchase_va": "0x27aa0", "availability_va": "0x24b38", "cost_getter_va": "0x1f0d60",
            "definition_table_va": hex(costs_va), "definition_stride": 16, "catalog": skin_catalog,
            "warning": "Ownership is nonzero, not ==1. Native availability returns true for all except ID7, which requires ownership. Selecting requires ownership; purchasing spends special bolts and notifies runtime systems. Cost0 does not prove unlock eligibility."},
        "named_bindings": named,
        "instruction_guards": [{"va": hex(address), "bytes": value.hex().upper()} for address, value in sorted(guards.items())]}
    if save_path is not None:
        if Path(save_path).stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save layout")
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        masks = [struct.unpack_from(">I", data, mask_offset + i * stride)[0] for i in range(19)]
        spent = struct.unpack_from(">I", data, 0x424)[0]
        balance = (sum(mask.bit_count() for mask in masks) - spent) & 0xFFFFFFFF
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "hero_xp": struct.unpack_from(">I", data, 0x418)[0], "collected": sum(mask.bit_count() for mask in masks),
            "spent": spent, "native_signed_balance": balance if balance < 0x80000000 else balance - 0x100000000,
            "masks": [f"{mask:08X}" for mask in masks], "counts": [mask.bit_count() for mask in masks],
            "uninterpreted_slot19_mask": f"{struct.unpack_from('>I', data, mask_offset + 19 * stride)[0]:08X}",
            "skin_ownership": list(struct.unpack_from(">9I", data, 0x45C)), "selected_skin": struct.unpack_from(">I", data, 0x480)[0]}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path, help="Plaintext working copy only; originals are never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2))
