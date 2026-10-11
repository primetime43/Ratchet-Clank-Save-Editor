"""Read-only exact-build opaque-tail lifecycle and settings initialization footprint."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("bindings", Path(__file__).with_name("Inspect-TodWeaponBindings.py"))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)


def settings_footprint(elf):
    """Decode only the observed leaf initializer's direct r3-relative stores."""
    stores = []
    covered = set()
    for address, word in elf.instructions(0x35EE40, 0x35EE94):
        if word == 0x4E800020:
            break
        opcode, base = word >> 26, word >> 16 & 31
        if opcode in (36, 38, 52):
            if base != 3:
                raise ValueError("Unrecognized settings initializer store base")
            offset = BINDINGS.signed(word & 65535, 16)
            size = 1 if opcode == 38 else 4
            if not 0 <= offset < offset + size <= 0x30:
                raise ValueError("Settings initializer store exceeds object")
            covered.update(range(offset, offset + size))
            stores.append({"instruction_va": hex(address), "member_offset": hex(offset),
                           "size": size, "store_kind": {36: "stw", 38: "stb", 52: "stfs"}[opcode]})
        elif opcode not in (14, 48):
            raise ValueError("Unrecognized settings initializer instruction")
    else:
        raise ValueError("Settings initializer did not terminate at verified return")
    if covered != set(range(0x2E)):
        raise ValueError("Unexpected settings initializer coverage")
    return {"va": "0x35ee40", "size": "0x30", "covered_byte_count": len(covered),
            "stores": stores, "unwritten_members": ["0x2e", "0x2f"],
            "unwritten_save_offsets": ["0x114d6", "0x114d7"],
            "rule": "This leaf initializer writes exactly members00..2D (46 of48 bytes), with no calls or writes to2E/2F. It does not establish whole-lifecycle defaults for the two opaque bytes or prove padding."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}
    expected = {
        0x8A1984: 0x101EFB20, 0x8A3BAC: 0x101EFB20,
        0x8A3BBC: 0x10200FC8,
        0x35E19C: 0x3FDD0009, 0x35E1A0: 0x3BE00000,
        0x35E1A4: 0x3BA00000, 0x35E1B8: 0x93BE06E4,
        0x3CED78: 0x80630080, 0x3CED80: 0x4BF8F391,
        0x3CED94: 0x38A00030, 0x3CED98: 0x38C714A8,
        0x3CEDA0: 0x4BE83689,
        0x3CEF4C: 0x38A060DC, 0x3CEF50: 0x1D5F60DC,
        0x3CEF5C: 0x380414D0, 0x3CEF68: 0x39030008,
        0x3CEF78: 0x4BE834B1, 0x3CEF80: 0x2F3F0015,
        0x3CF14C: 0x3F600009, 0x3CF154: 0x636506F0,
        0x3CF158: 0x4BE832D1,
        0x3CF1C0: 0x3CA00009, 0x3CF1CC: 0x60A506F0,
        0x3CF1D4: 0x4BE83255,
        0x35E51C: 0x60A506F0, 0x35E534: 0x4BEF3EF5,
        0x35E73C: 0x60A506F0, 0x35E744: 0x4BEF3CE5,
    }
    for address, value in expected.items():
        if elf.u32(address) != value:
            raise ValueError(f"Opaque tail lifecycle evidence changed at {address:#x}")
        guards[address] = elf.read(address, 4)
    for function in (0x35E110, 0x35EE40, 0x35E508, 0x35E710,
                     0x3CED40, 0x3CF1B8, 0x3CEC98, 0x465C98):
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    guards[0x252428] = elf.read(0x252428, 16)
    footprint = settings_footprint(elf)
    # All explicit current-state preservation destinations before the final whole
    # staging copy. The grid's endpoint is exclusive, not a tail-word inclusion.
    fixed = [(0, 0x484), (0x86F4, 4), (0x114A8, 0x30), (0x8734, 4),
             (0x86F8, 0xE), (0x8708, 4), (0x8710, 0x10), (0x5754, 0x25),
             (0x577C, 0xC00), (0x637E, 0x1000), (0x737E, 0x280), (0x637C, 2)]
    ranges = [{"offset": hex(start), "size": hex(size), "end_exclusive": hex(start + size)}
              for start, size in fixed]
    grids = [{"offset": hex(0x114D8 + i*0x60DC), "size": "0x60dc",
              "end_exclusive": hex(0x114D8 + (i+1)*0x60DC)} for i in range(21)]
    masks = [{"offset": hex(0x874 + i*0x408), "size": "0x4",
              "end_exclusive": hex(0x878 + i*0x408)} for i in range(20)]
    if any(int(r["offset"], 0) <= 0x906E4 < int(r["end_exclusive"], 0)
           for r in ranges + grids + masks):
        raise ValueError("Opaque final word unexpectedly included in restart preservation")
    pointers = {0x10280204: [], 0x10200FC8: []}
    for va, file_offset, size in elf.segments:
        for index, (word,) in enumerate(struct.iter_unpack(">I", elf.raw[file_offset:file_offset + size//4*4])):
            if word in pointers:
                pointers[word].append(hex(va + index*4))
    if pointers[0x10280204] or pointers[0x10200FC8] != ["0x8a3bbc"]:
        raise ValueError("Recorded aligned pointer census changed")
    report = {
        "confidence": "code-backed mechanical evidence; semantic name unresolved",
        "warning": "Exact USA v02.00, detached read-only inspection only. These lifecycle boundaries do not identify906E4 or opaque options as flags, padding, checksum, health, or a version field. No game code or reset is executed.",
        "opaque_word": {"offset": "0x906e4", "va": "0x10280204", "physical_type": "u32 BE",
            "initializer_va": "0x35e110", "zero_store_va": "0x35e1b8",
            "initializer_rule": "Initializer forms input_state+90000 and stores low32-bit zero at+6E4. Previous21 grid slots end exactly at906E4, end exclusive; this store is outside those slots.",
            "semantic_name": None},
        "settings_initializer_footprint": footprint,
        "selective_restart": {"va": "0x3ced40", "staging_pointer_member": "0x80",
            "initialization_call_va": "0x3ced80", "commit_copy_va": "0x3cf158",
            "copy_size": "0x906f0", "opaque_word_at_copy_boundary": 0,
            "fixed_preservation_ranges": ranges, "grid_preservation_ranges": grids,
            "special_bolt_mask_preservation_ranges": masks,
            "rule": "Initializer clears the staging906E4 word. Every explicit current-state preservation destination in this routine excludes906E4; the last grid ends there exclusively. Later explicit stores reset inventory/object banks, help byte114D0, unlock byte5778 and906EC, not906E4. The full staging-to-live copy therefore transfers0 for this word under the observed non-aliasing native staging/current-state arrangement.",
            "opaque_options_rule": "The exact30-byte settings preservation copy includes114D6/114D7 verbatim, even though the leaf settings initializer does not write them. The later help-byte clear at114D0 does not overlap them.",
            "scope": "Claim concerns the bytes at the full-copy boundary only, not every side effect of the subsequent destination request or future loading/runtime callbacks. This is not a complete editor-safe restart implementation."},
        "whole_state_copy_boundaries": [
            {"function_va": "0x35e710", "copy_instruction_va": "0x35e744", "direction": "live saved state to snapshot context+1FD08", "size": "0x906f0"},
            {"function_va": "0x35e508", "copy_instruction_va": "0x35e534", "direction": "snapshot context+1FD08 to live saved state", "size": "0x906f0"},
            {"function_va": "0x3cf1b8", "copy_instruction_va": "0x3cf1d4", "direction": "staging context+80 to live saved state", "size": "0x906f0"}],
        "whole_copy_rule": "All three copies include906E4 and both opaque option bytes verbatim at the copy boundary. They do not parse or validate those bytes, and subsequent callbacks are not claimed to preserve every field indefinitely.",
        "aligned_pointer_census": {"target_va": "0x10280204", "matches": pointers[0x10280204],
            "settings_pointer_va": "0x10200fc8", "settings_pointer_matches": pointers[0x10200FC8],
            "rule": "Scans aligned BE32 words only in the map's exact four file-backed LOAD ranges. No embedded absolute906E4 pointer occurs there. This is not proof of no computed, indirect, dynamic, relocated or executable consumer."},
        "limitations": ["No named binding or player-facing meaning for906E4 was established.",
            "114D6/114D7 remain semantically opaque and are not proven padding or defaultzero.",
            "Actual zero values cannot prove unused storage or safe edits; arbitrary opaque bytes are preserved in inspection.",
            "Initializer and copy mechanics are not gameplay-tested reset/edit acceptance."],
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save size")
        data = path.read_bytes()
        if any(struct.unpack_from(">I", data, i*0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        report["save_observation"] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest().upper(),
            "opaque_word": {"offset": "0x906e4", "raw_hex": data[0x906E4:0x906E8].hex().upper(),
                            "unsigned_bits": struct.unpack_from(">I", data, 0x906E4)[0]},
            "opaque_options": [{"offset": hex(o), "raw_hex": f"{data[o]:02X}", "value": data[o]}
                               for o in (0x114D6, 0x114D7)],
            "warning": "Snapshot observations only; no opaque bytes are overwritten, normalized, removed or treated as padding."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2))
