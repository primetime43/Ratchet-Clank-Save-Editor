"""Read-only native item/config bindings for the exact ToD BCUS98127 v02.00 ELF.

Decodes bounded, observed PPC instruction patterns; not a general disassembler.
Requires the reference ELF hash before following any pointers. Reports to stdout
only and never executes game code. File offsets, VAs and save offsets are distinct.
"""
import argparse
from bisect import bisect_right
import hashlib
import json
from pathlib import Path
import struct

ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "Ratchet And Clank Save Editor.sln").is_file())
MAP_PATH = ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json"


def signed(value, bits):
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def branch_target(word, address):
    if word >> 26 != 18:
        return None
    displacement = signed(word & 0x03FFFFFC, 26)
    return (displacement if word & 2 else address + displacement) & 0xFFFFFFFF


class Elf:
    def __init__(self, path):
        self.mapping = json.loads(MAP_PATH.read_text(encoding="utf-8"))
        binary = self.mapping["binary"]
        if Path(path).stat().st_size != binary["size"]:
            raise ValueError("Reference ELF size mismatch")
        self.raw = Path(path).read_bytes()
        if hashlib.sha256(self.raw).hexdigest().upper() != binary["sha256"]:
            raise ValueError("Reference ELF SHA-256 mismatch")
        self.segments = [(int(s["va"], 0), int(s["file_offset"], 0), int(s["file_size"], 0)) for s in binary["load_segments"]]
        self.descriptors = {}
        table = binary["descriptor_table"]
        for address in range(int(table["start"], 0), int(table["end_exclusive"], 0), 8):
            code, toc = struct.unpack(">II", self.read(address, 8))
            if code in self.descriptors and self.descriptors[code] != toc:
                raise ValueError("Ambiguous function TOC")
            self.descriptors[code] = toc
        self.functions = sorted(self.descriptors)

    def read(self, address, size):
        if size < 1:
            raise ValueError("Read length must be positive")
        for start, offset, length in self.segments:
            if start <= address and address + size <= start + length:
                position = offset + address - start
                return self.raw[position:position + size]
        raise ValueError(f"Unmapped/uninitialized range: 0x{address:X}+0x{size:X}")

    def u32(self, address):
        return int.from_bytes(self.read(address, 4), "big")

    def string(self, address):
        result = bytearray()
        for index in range(128):
            value = self.read(address + index, 1)
            if value == b"\0":
                return result.decode("ascii", errors="strict")
            result.extend(value)
        raise ValueError("Unterminated/oversized native identifier")

    def instructions(self, start, end):
        for address in range(start, end, 4):
            yield address, self.u32(address)


def enum_exports(elf):
    """Observed straight-line WPN export range, including INVALID/TYPE_COUNT."""
    toc, floating, name, exports = 0x88FF38, {}, None, []
    for address, word in elf.instructions(0x80A98, 0x80D88):
        opcode, target, base = word >> 26, word >> 21 & 31, word >> 16 & 31
        if opcode == 48 and base == 2:  # lfs fN,disp(r2)
            slot = toc + signed(word & 65535, 16)
            floating[target] = (struct.unpack(">f", elf.read(slot, 4))[0], slot, address)
        elif opcode == 63 and (word >> 1 & 1023) == 72:  # fmr
            source = word >> 11 & 31
            if source not in floating:
                raise ValueError("Unknown FPR value in item enum export")
            floating[target] = floating[source]
        elif opcode == 32 and target == 4 and base == 2:
            slot = toc + signed(word & 65535, 16)
            pointer = elf.u32(slot)
            name = (elf.string(pointer), pointer, slot, address)
        elif opcode == 18:
            if not word & 1 or branch_target(word, address) != 0x12990 or name is None or 1 not in floating:
                raise ValueError("Unexpected call/unknown arguments in item enum export")
            value, value_slot, value_load = floating[1]
            if not value.is_integer() or not name[0].startswith("WPN_"):
                raise ValueError("Invalid item enum name/value")
            exports.append({"enum": name[0], "id": int(value), "call_va": hex(address),
                            "name_va": hex(name[1]), "name_slot_va": hex(name[2]), "name_load_va": hex(name[3]),
                            "value_slot_va": hex(value_slot), "value_load_va": hex(value_load)})
            name = None
            floating = {register: v for register, v in floating.items() if register >= 14}
        elif word != 0xE8410028 and word != 0x7FA3EB78:
            raise ValueError(f"Unexpected enum instruction at 0x{address:X}: 0x{word:08X}")
    if len(exports) != 34 or {e["id"] for e in exports} != set(range(-1, 33)):
        raise ValueError("Incomplete/duplicate reference item enum catalog")
    return exports


def subobject_offset(elf, function):
    """Observed getter r6 = parent r30 + constant, before userdata push."""
    affine = {30: 0}
    for address, word in elf.instructions(function, function + 0xA0):
        opcode, target, base = word >> 26, word >> 21 & 31, word >> 16 & 31
        if opcode in (14, 15) and base in affine:
            immediate = signed(word & 65535, 16) * (65536 if opcode == 15 else 1)
            affine[target] = affine[base] + immediate
        if word >> 26 == 18 and branch_target(word, address) == 0x104D0:
            offset = affine.get(6)
            if offset is None or offset < 0:
                raise ValueError(f"Missing/negative config subobject offset at getter 0x{function:X}")
            return offset
    raise ValueError(f"Unrecognized config subobject getter at 0x{function:X}")


def config_properties(elf):
    # Native property registration triplets (name, getter opd, setter opd).
    # 32 native entries, including four without matching weapon.csv sections.
    result = []
    for slot in range(0x88ED20, 0x88ED20 + 32 * 12, 12):
        name_va, getter_descriptor, setter_descriptor = struct.unpack(">III", elf.read(slot, 12))
        name = elf.string(name_va)
        getter, toc = struct.unpack(">II", elf.read(getter_descriptor, 8))
        if toc != 0x88FF38:
            raise ValueError("Unexpected config getter TOC")
        result.append({"name": name, "registration_slot_va": hex(slot), "name_va": hex(name_va),
                       "getter_va": hex(getter), "getter_descriptor_va": hex(getter_descriptor),
                       "setter_descriptor_va": hex(setter_descriptor), "parent_offset": subobject_offset(elf, getter)})
    if len({p["name"] for p in result}) != len(result):
        raise ValueError("Duplicate named config subobject")
    return result


def constructor_calls(elf):
    result = []
    for address, word in elf.instructions(0x10200, 0x83A50C):
        if not word & 1 or branch_target(word, address) not in (0x466798, 0x11210):
            continue
        position = bisect_right(elf.functions, address) - 1
        function = elf.functions[position]
        toc = elf.descriptors[function]
        item, pointer = None, None
        item_load, pointer_load, pointer_slot = None, None, None
        for load_va, instruction in elf.instructions(max(function, address - 0x180), address):
            opcode, target, base = instruction >> 26, instruction >> 21 & 31, instruction >> 16 & 31
            if opcode == 14 and target == 4 and base == 0:
                item, item_load = signed(instruction & 65535, 16), load_va
            elif opcode == 32 and target == 5 and base == 2:
                pointer_slot = toc + signed(instruction & 65535, 16)
                pointer, pointer_load = elf.u32(pointer_slot), load_va
        if item is None or pointer is None or not 0 <= item < 32:
            raise ValueError(f"Unresolved constructor arguments at 0x{address:X}")
        result.append({"id": item, "constructor_va": hex(function), "call_va": hex(address),
                       "call_target_va": hex(branch_target(word, address)), "toc_va": hex(toc),
                       "id_load_va": hex(item_load), "config_load_va": hex(pointer_load),
                       "config_pointer_slot_va": hex(pointer_slot), "config_va": hex(pointer)})
    return result


def inspect(path):
    elf = Elf(path)
    exports = enum_exports(elf)
    properties = config_properties(elf)
    calls = constructor_calls(elf)
    root = elf.u32(0x88FAFC)  # MonolithicConfig getter 0x94400.
    by_pointer = {root + p["parent_offset"]: p for p in properties}
    enums = {e["id"]: e for e in exports}
    for call in calls:
        call["enum"] = enums[call["id"]]["enum"]
        property_ = by_pointer.get(int(call["config_va"], 0))
        call["config_name"] = property_["name"] if property_ else None
        call["config_property"] = property_
        call["save_record_offset"] = hex(call["id"] * 0x14)
    if len(calls) != 32 or {c["id"] for c in calls} != set(range(32)) or any(c["config_name"] is None for c in calls):
        raise ValueError("Incomplete/ambiguous reference constructor catalog")
    return {"reference_build": "BCUS98127 v02.00", "elf_sha256": elf.mapping["binary"]["sha256"],
            "config_root_va": hex(root), "enum_exports": exports, "config_properties": properties,
            "constructor_calls": calls,
            "warnings": ["Fixed-build observed instruction decoder, not a general PPC emulator.",
                         "Constructor argument patterns must be cross-checked in assembly before promoting mappings.",
                         "Native IDs/asset links are not edited-save gameplay validation.",
                         "No game code or Lua is executed; no file is written."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.elf), indent=2, allow_nan=False))
    except (ValueError, OSError) as error:
        parser.exit(2, f"Native binding inspection failed: {error}\n")


if __name__ == "__main__":
    main()
