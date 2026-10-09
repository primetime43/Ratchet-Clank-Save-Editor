"""Exact-build read-only persistent grid, copied volume header and seven group flags."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("storage", Path(__file__).with_name("Inspect-TodStateStorage.py"))
STORAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STORAGE)


def inspect(elf_path, save_path=None):
    elf = STORAGE.BINDINGS.Elf(elf_path)
    checks = {0x35E170: 0x1D7F60DC, 0x35E180: 0x390914D8, 0x35E190: 0x2C3F0015,
        0x24DFB0: 0x2F070535, 0x24E07C: 0x38A000C8, 0x24E094: 0x386A14D8,
        0x24E97C: 0x2C860000, 0x24EA7C: 0x2F3B0007,
        0x24EA40: 0x8019000C, 0x24EA68: 0x9AA5000C,
        0x897EE4: 0x101EFB20, 0x897F10: 0x101EFB20,
        0x897EC0: 0x42FE0000, 0x897EC4: 0x3F800000,
        0x24E6E8: 0x2B830014, 0x24E6F0: 0x81627FC8,
        0x25D33C: 0x4BFF40ED, 0x25D3CC: 0x480735BD, 0x25D3E0: 0x48073839,
        0x20F518: 0xE91D5528, 0x20F51C: 0x61060040, 0x20F520: 0xF8DD5528}
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Persistent grid instruction/pointer changed at {address:#x}")
    base = 0x10000 + (elf.u32(0x35E180) & 65535)
    stride, count = elf.u32(0x35E170) & 65535, elf.u32(0x35E190) & 65535
    prefix_size, groups = elf.u32(0x24E07C) & 65535, elf.u32(0x24EA7C) & 65535
    guards = {a: elf.read(a, 4) for a in checks}
    functions = (0x24D570, 0x24D6E8, 0x24D788, 0x24DCA0, 0x24DEA8,
        0x24E1D0, 0x24E6E8, 0x24E8A0, 0x25AE08, 0x25D1D0, 0x2D0988, 0x2D0C18,
        0x20F3F0, 0x2108D8, 0x639400, 0x639548)
    for f in functions:
        end = elf.functions[elf.functions.index(f) + 1]
        guards[f] = elf.read(f, end - f)
    guards[0x12BB0] = elf.read(0x12BB0, 16)
    if STORAGE.BINDINGS.branch_target(elf.u32(0x12BBC), 0x12BBC) != 0x81A9A8:
        raise ValueError("Prefix copy thunk changed")
    for thunk, target in ((0x251428, 0x24E6E8), (0x10420, 0x639400), (0x13D50, 0x639548)):
        guards[thunk] = elf.read(thunk, 16)
        if STORAGE.BINDINGS.branch_target(elf.u32(thunk+12), thunk+12) != target:
            raise ValueError("Grid label/camera context thunk changed")
    for function, displacement in ((0x20F3F0, 0x6864), (0x2108D8, 0x6920)):
        address = elf.descriptors[function] + displacement
        guards[address] = elf.read(address, 4)
        if elf.u32(address) != 0x101EFB20:
            raise ValueError("Camera context no longer uses the saved state")
    # Case blocks omitted by Ghidra's unresolved switch decompilation: decode the
    # guarded relative jump table, then require each exact li/return sequence.
    table_slot = elf.descriptors[0x24E6E8] + STORAGE.BINDINGS.signed(elf.u32(0x24E6F0) & 65535, 16)
    table = elf.u32(table_slot)
    guards[table_slot] = elf.read(table_slot, 4)
    guards[table] = elf.read(table, count * 4)
    levels = [{"internal_name": elf.string(elf.u32(0x10062F7C+i*4)),
        "name_va": hex(elf.u32(0x10062F7C+i*4))} for i in range(19)]
    catalog = []
    for slot in range(count):
        case = table + STORAGE.BINDINGS.signed(elf.u32(table + slot * 4), 32)
        word = elf.u32(case)
        if word & 0xFFFF0000 != 0x38600000:
            raise ValueError("Grid level case no longer loads literal r3")
        level = word & 65535
        if not 0 <= level < len(levels):
            raise ValueError("Unmapped grid label level ID")
        second = elf.u32(case + 4)
        if second == 0x78630020:
            if elf.u32(case + 8) != 0x4E800020:
                raise ValueError("Grid level return changed")
        elif STORAGE.BINDINGS.branch_target(second, case+4) != 0x24E768:
            raise ValueError("Grid level shared return changed")
        guards[case] = elf.read(case, 12)
        catalog.append({"slot": slot, "offset": hex(base + slot * stride), "label_level_id": level,
            "internal_level_name": levels[level]["internal_name"], "case_va": hex(case)})
    for address in (0x897ECC, 0x897ED0, 0x897EDC, 0x897EF4, 0x89F158):
        guards[address] = elf.read(address, 4)
    guards[0x10062F7C] = elf.read(0x10062F7C, 19 * 4)
    for level in levels:
        address = int(level["name_va"], 0)
        guards[address] = elf.read(address, len(level["internal_name"]) + 1)
    report = {"confidence": "code-backed",
        "warning": "Exact USA v02.00. Persistent 512x512 grid and map-label associations, not a per-planet completion checklist, editable fog map or runtime acceptance proof. Unknown scalar meanings remain preserved.",
        "blocks": {"base": hex(base), "stride": hex(stride), "count": count, "header_size": hex(prefix_size),
            "copy_va": "0x24e09c", "copy_thunk_va": "0x12bb0", "copy_leaf_va": "0x81a9a8",
            "selection_class": "0x535", "selection_class_member": "0x4", "selection_enabled_member": "0xc",
            "saved_slot_member": "0x10", "baked_layer_member": "0x14", "optional_volume_reference_member": "0x18",
            "coordinate_sign_member": "0x1c",
            "header_provenance": "24DEA8 selects enabled class535 definitions containing the hero, uses definition+10 for block slot, saves prior grid, then copies exactly200 bytes into an unready block prefix. Header+0 is copied runtime geometry pointer, not a portable pointer or stable UID. Other common header bytes remain unresolved.",
            "groups": {"base": "0x20", "count": groups, "stride": "0x18", "reference_member": "0x0",
                "activation_member": "0xc", "image_index_member": "0x14", "flag_base": "0x60d4", "unknown_last_byte": "0x60db",
                "semantics": "24E8A0 tests referenced volume-list entries against hero position; if group+0C nonzero and containment succeeds, stores1 in its saved flag. Nonzero saved flags skip further checks.25AE08 reads those flags and group+0C to choose/show group image index+14+25; treasure-mapper object count at save31C can bypass flag display requirement. No localized group names or completion meanings inferred."}},
        "grid": {"width": 512, "height": 512, "bytes": "0x40000", "runtime_buffer_member": "0x24",
            "runtime_image_pointer_member": "0x40028", "offset_formula": "first_coordinate*512 + second_coordinate",
            "initialization": "24DCA0 reads resource250D0, layer definition+14; each BE32 contributes eight high-to-low nibbles. Nested512 loops store persistent bytes at runtime+24 and converted image bytes via+40028.",
            "conversion": "24D6E8: zero input yields image0/state0; otherwise image=min((input&15)*17,254), state=min(ceil(image/127),2). Thus nibble1..7->state1,8..15->state2.",
            "updates": "24D570 maps world coordinates using runtime geometry pointer and sign byte1C;24D788 checks coordinates<512, processes a bounded neighboring region and clears qualifying saved-grid cells to0. Zero is a cleared cell, not a mission-completion bit.1/2 encode native state classes, not boolean equivalents.",
            "limits": "Coordinate orientation/scale, pixel-specific terrain labels, runtime image palette and visual/edited-save acceptance remain unverified. Native logical grid is distinct from encoded physical bytes."},
        "slot_catalog": catalog,
        "label_provenance": "24E6E8 maps physical slot to native level ID;25D1D0 calls it via251428 and passes the result to named-table lookups2D0988/2D0C18. This is a map-label relationship, not current planet or identity of every gameplay subsystem.",
        "settings_followup": "20F3F0's saved114C0 consumer sets independently named HERO_FIRST_PERSON bit6; native mode requests0F/10 via13D50->639548, getter10420->639400. This strengthens first-person camera context, but no menu-option name, toggle/hold polarity or trailing-byte meanings are confirmed.",
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i*0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        observations = []
        for entry in catalog:
            o = int(entry["offset"], 0)
            u32 = lambda relative: struct.unpack_from(">I", data, o+relative)[0]
            ready, length = data[o+0xCC], u32(0x60D0)
            decoded, status = None, "Not marked ready; grid not decoded"
            if ready:
                try:
                    if length > 0x5FFF:
                        raise ValueError("Length exceeds native encoder cap")
                    _, decoded = STORAGE.decode_stream(data[o+0xCD:o+0xCD+length])
                    status = "Decoded" if decoded["complete"] else "Short grid; not padded"
                except ValueError as error:
                    status = str(error)
            observations.append({"slot": entry["slot"], "ready_byte": ready, "class": u32(4),
                "stored_slot": u32(0x10), "header_matches_selection": u32(4)==0x535 and u32(0x10)==entry["slot"],
                "runtime_geometry_pointer_bits": hex(u32(0)), "baked_layer": u32(0x14),
                "optional_volume_reference_bits": hex(u32(0x18)), "coordinate_sign_byte": data[o+0x1C],
                "header_hex": data[o:o+prefix_size].hex().upper(),
                "groups": [{"group": g, "reference_bits": hex(u32(0x20+g*24)), "activation_word": u32(0x2C+g*24),
                    "image_index_bits": hex(u32(0x34+g*24)), "saved_flag": data[o+0x60D4+g]} for g in range(groups)],
                "unknown_last_byte": data[o+0x60DB], "status": status, "decoded": decoded})
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(), "blocks": observations}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path, help="Plaintext working copy; never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2))
