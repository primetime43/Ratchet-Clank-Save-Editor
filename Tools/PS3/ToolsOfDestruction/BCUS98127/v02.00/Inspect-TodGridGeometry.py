"""Exact-build copied grid rectangles, world projection and clearing brush; read-only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("bindings", Path(__file__).with_name("Inspect-TodWeaponBindings.py"))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}
    for function in (0x24D570, 0x24D6E8, 0x24D788, 0x24D9C0, 0x24DEA8, 0x25BF68):
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    if elf.descriptors[0x24D570] != 0x88FF38 or elf.descriptors[0x25BF68] != 0x89FF20:
        raise ValueError("Projection/display TOCs changed")
    expected = {0x897EA8: 0x3A800000, 0x897EAC: 0x44000000,
        0x897EB0: 0x448AE000, 0x897EB4: 0x44800000,
        0x897EB8: 0x3F000000, 0x897EBC: 0,
        0x897EC8: 0x10060DE8, 0x898310: 0x3F800000,
        0x89835C: 0x43C80000, 0x898360: 0x43480000,
        0x898364: 0x3F480000, 0x898368: 0x3EC80000,
        0x89836C: 0x44480000, 0x898328: 0,
        0x25C0BC: 0x8009000C, 0x25C0C0: 0x81690004,
        0x25C0C4: 0x80690008, 0x25C16C: 0x7C07202E,
        0x24D978: 0x7F005038, 0x24D97C: 0x7F803800,
        0x24D9B4: 0x98C80000}
    for address, value in expected.items():
        if elf.u32(address) != value:
            raise ValueError(f"Grid geometry guard changed at {address:#x}")
        guards[address] = elf.read(address, 4)
    brush = elf.read(0x10060DE8, 14*14)
    if set(brush) != {0, 255} or brush.count(255) != 129:
        raise ValueError("Grid clearing brush changed")
    guards[0x10060DE8] = brush
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA v02.00 only. Read-only mathematical/display semantics, not edited-save acceptance or complete terrain/fog semantics.",
        "groups": {"base": "0x20", "count": 7, "stride": "0x18",
            "coordinate_1_member": "0x4", "coordinate_2_member": "0x8",
            "extent_1_member": "0xc", "extent_2_member": "0x10",
            "storage_type": "BE unsigned32 words",
            "consumer_va": "0x25bf68",
            "semantics": "25BF68 consumes group+04/+08 as rectangle origins and+0C/+10 as extents, transforms them to map-display rectangle endpoints, clips endpoints and adjusts texture UVs. Group+0C is therefore horizontal extent, not merely a boolean activation word; it also gates containment flag recording and image visibility when nonzero. Axes are map-display coordinates, not raw world coordinates.",
            "display_constants": {"coordinate_1_factor": "400/512", "coordinate_2_factor": "200/512", "clip_axis_1": 800, "clip_axis_2": 400},
            "unknown_members": "Header+08,+0D..0F,+1D..1F and saved tail+60DB remain unresolved. No completion meaning inferred."},
        "projection": {"consumer_va": "0x24d570", "caller_va": "0x24d9c0",
            "geometry_pointer_member": "0x0", "sign_member": "0x1c",
            "normalizer": "sqrt(geometry[0]^2 + geometry[1]^2 + geometry[2]^2)",
            "translation_offsets": ["0x30", "0x38"],
            "sign": "header+1C zero -> -1; nonzero -> +1",
            "formula": "For each input component p and corresponding geometry translation c: t=512 + sign*(p-c)*512/normalizer; output=truncate_toward_zero((t>=0 ? 1024-t : 1111)*0.5). At finite nonzero normalizer and translation center the coordinate is256. Negative t gives555, an out-of-grid result, not an edge clamp.",
            "buffer_order": "24DEA8 passes hero transform+30/+38 pairs to24D9C0;24D9C0 forwards the +38-derived coordinate first and +30-derived coordinate second to24D788, which uses first*512+second.",
            "limits": "Geometry is a copied runtime pointer and cannot be reconstructed or dereferenced from save bytes. Formula follows PPC single-precision/FMA/conversion operations; simplified algebra is not a bit-exact floating-point emulator. World-axis naming/orientation beyond transform offsets and pathological NaN/zero-normalizer behavior remain unverified."},
        "brush": {"consumer_va": "0x24d788", "pointer_slot_va": "0x897ec8",
            "data_va": "0x10060de8", "width": 14, "height": 14,
            "mask_hex": brush.hex().upper(), "nonzero_cells": brush.count(255),
            "range": "Nominal first/second coordinate ranges [center-7,center+7), mask index=first_loop_index+14*second_loop_index. Native unsigned coordinate checks require each coordinate<512. Near minimum edge a negative starting coordinate causes the corresponding loop to skip; maximum-edge loops stop at512. Do not replace this with a symmetric clamped brush.",
            "predicate": "Center image byte and each candidate image byte are converted with24D6E8. Clear persistent grid cell to0 exactly when (center_class & brush_byte)==candidate_class. This is not candidate_class&mask==candidate_class: center_class is preserved in r24 at24D8D0, whereas candidate_class is loaded in r7 at24D958.",
            "zero_mask": "Zero mask entries can still satisfy the predicate for candidate class0; they are not an unconditional skip."},
        "instruction_guards": [{"va": hex(a), "bytes": raw.hex().upper()} for a, raw in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save layout")
        data = path.read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i*20)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        observations = []
        for slot in range(21):
            offset = 0x114D8 + slot*0x60DC
            ready = data[offset+0xCC]
            groups = []
            for group in range(7):
                words = struct.unpack_from(">6I", data, offset+0x20+group*24)
                x, y, width, height = words[1:5]
                groups.append({"group": group, "coordinate_1": x, "coordinate_2": y,
                    "extent_1": width, "extent_2": height,
                    "nonzero_extent_1": width != 0,
                    "within_512": x+width <= 512 and y+height <= 512,
                    "saved_flag": data[offset+0x60D4+group]})
            observations.append({"slot": slot, "ready_byte": ready, "groups": groups,
                "unknown_header_08_bits": hex(struct.unpack_from(">I", data, offset+8)[0]),
                "unknown_header_0d_to_0f": data[offset+13:offset+16].hex().upper(),
                "unknown_header_1d_to_1f": data[offset+29:offset+32].hex().upper(),
                "unknown_tail_60db": data[offset+0x60DB]})
        active = [group for block in observations if block["ready_byte"] for group in block["groups"] if group["nonzero_extent_1"]]
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "blocks": observations, "ready_nonzero_extent_groups": len(active),
            "all_active_rectangles_within_512": all(group["within_512"] for group in active),
            "note": "Observed bounds are not a validator for all possible game resources; malformed/retained/not-ready bytes are never normalized."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path, help="Plaintext working copy; never modified")
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2))
