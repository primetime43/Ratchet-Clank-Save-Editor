"""Exact-build copied grid definition runtime handle and unresolved auxiliary bytes."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("bindings", Path(__file__).with_name("Inspect-TodWeaponBindings.py"))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)
ROOT = BINDINGS.ROOT


def inspect(elf_path, save_path=None, archive_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}
    functions = (0x64D828, 0x64D9E0, 0x64DAB0, 0x64DB68, 0x64DC50, 0x64DCF0, 0x35E070)
    for function in functions:
        guards[function] = elf.read(function, elf.functions[elf.functions.index(function)+1]-function)
    expected = {0x64D9A4: 0x39990001, 0x64D9AC: 0xB1830840,
        0x64D9C0: 0x939D0004, 0x64D9C8: 0x577A801E,
        0x64D9CC: 0x7FF9D378, 0x64D9D0: 0x933D0008,
        0x64DA78: 0xB0CA0840, 0x64DA8C: 0xF86B0000,
        0x64DB00: 0x93BF0008, 0x64DB04: 0x939F0004,
        0x64DB0C: 0x907F0000, 0x64DD68: 0x83BF0008,
        0x64DD7C: 0x93BF0008, 0x64DD80: 0x939F0004,
        0x64DD88: 0x90BF0000, 0x64DC68: 0x57E313BA,
        0x64DCC8: 0x80C30008, 0x64DCCC: 0x7C86F800,
        0x24E07C: 0x38A000C8, 0x24E09C: 0x4BDC4B15,
        0x35E070: 0x38800007, 0x35E09C: 0x994560D4}
    for address, word in expected.items():
        if elf.u32(address) != word:
            raise ValueError(f"Grid auxiliary guard changed at {address:#x}")
        guards.setdefault(address, elf.read(address, 4))
    guards[0x24E074] = elf.read(0x24E074, 0x30)
    for address in (0x8A9B04, 0x8A9B08, 0x8A9B0C, 0x8A9B14):
        guards[address] = elf.read(address, 4)
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA v02.00. Copied runtime handle bits are historical metadata, not portable stable IDs or proof of current pool validity. Never resolve a saved handle against runtime memory.",
        "runtime_header": {"size": "0xc", "geometry_pointer_member": "0x0", "class_member": "0x4", "handle_member": "0x8",
            "handle_type": "BE uint32: high16 generation, low16 pool slot",
            "pool_slots": 512, "generation_bits": 16, "slot_bits": 16,
            "allocator_va": "0x64d828", "loader_va": "0x64dcf0", "single_loader_va": "0x64dab0",
            "resolver_va": "0x64dc50", "release_va": "0x64d9e0", "pool_reset_va": "0x64db68",
            "allocation": "64D828 selects an unused slot below512, increments its16-bit generation at runtime owner+840+2*slot, sets its used bit, stores class at definition+04 and (generation<<16)|slot at definition+08. Generation arithmetic wraps16 bits; generation1 is not a permanent invariant.",
            "loading": "64DCF0 iterates16-byte descriptors from resource+58/count+5C.64DAB0 loads one descriptor. Both allocate using descriptor+0C class, preserve allocated definition+08 across copying descriptor+04 payload for descriptor+08 bytes, restore class at definition+04 and assign descriptor+00 geometry pointer at definition+00. These first12bytes are runtime-generated/refilled rather than portable baked payload identity.",
            "resolution": "64DC50 indexes the runtime slot table using low16 input bits, rejects the pool sentinel, resolves the allocator's separate handle and returns the definition only if its+08 equals the entire requested generation/slot word. No input slot bounds or null-resolution safety are claimed. This code is inspected, never executed.",
            "release": "64D9E0 reads low16 at definition+0A, releases the allocator handle, resets the slot entry, increments the generation again and clears the used bit.64DB68 resets512 slot/generation entries and occupancy words.",
            "save_link": "24E074..24E0A0 copies exactlyC8bytes from the selected runtime class535 definition into the unready saved block. Hence save block+08 contains copied runtime generation/slot bits, not a game-wide object UID or stable planet identifier."},
        "opaque_fields": [
            {"member": "0xd", "bytes": 3, "meaning": "Unresolved copied source bytes; not asserted padding/reserved."},
            {"member": "0x1d", "bytes": 3, "meaning": "Unresolved copied source bytes; not asserted padding/reserved."},
            {"member": "0x60db", "bytes": 1, "meaning": "Unresolved final physical block byte.35E070 clears only seven flags60D4..60DA, readinessCC and encoded length60D0; it does not assign60DB. Lack of an initializer write is not proof of padding or permanent zero."}],
        "instruction_guards": [{"va": hex(a), "bytes": raw.hex().upper()} for a, raw in sorted(guards.items())]}
    data = None
    if save_path is not None:
        if Path(save_path).stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save layout")
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i*20)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        blocks = []
        for slot in range(21):
            offset = 0x114D8+slot*0x60DC
            bits = struct.unpack_from(">I", data, offset+8)[0]
            blocks.append({"slot": slot, "ready_byte": data[offset+0xCC], "handle_bits": hex(bits),
                "generation": bits>>16, "runtime_slot": bits&65535, "slot_within_native_pool": (bits&65535)<512,
                "unknown_0d_to_0f": data[offset+13:offset+16].hex().upper(),
                "unknown_1d_to_1f": data[offset+29:offset+32].hex().upper(),
                "unknown_60db": data[offset+0x60DB]})
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(), "blocks": blocks,
            "note": "Ready and unready raw bytes are preserved. Bounds are observations, not a runtime-validity test; no handle is followed."}
    if archive_path is not None:
        path = Path(archive_path)
        if path.name != "global_cached.psarc" or not path.is_file():
            raise ValueError("Pass original packed/game/global_cached.psarc to locate sibling level archives")
        levels = path.parent.parent/"levels"
        if not levels.is_dir():
            raise ValueError("Sibling packed/levels directory not found")
        spec = importlib.util.spec_from_file_location("psarc", ROOT/"Tools/Inspect-Psarc.py")
        psarc = importlib.util.module_from_spec(spec)
        import sys
        sys.modules[spec.name] = psarc
        spec.loader.exec_module(psarc)
        candidates = []
        for archive in sorted(levels.glob("*/level_cached.psarc")):
            reader = psarc.Psarc(archive)
            for index, name in enumerate(reader.names):
                if name is None or not name.endswith("/gameplay.dat"):
                    continue
                raw = reader.read_entry(index, 4*1024*1024)
                for cursor in range(12, len(raw)-4, 4):
                    if raw[cursor:cursor+4] != b"\0\0\x05\x35":
                        continue
                    geometry, payload, size, class_id = struct.unpack_from(">4I", raw, cursor-12)
                    if size != 200 or payload+size>len(raw):
                        continue
                    header = raw[payload:payload+size]
                    slot = struct.unpack_from(">I", header, 16)[0]
                    if slot >= 21:
                        continue
                    item = {"level_archive": archive.parent.name, "resource": name, "resource_sha256": hashlib.sha256(raw).hexdigest().upper(),
                        "descriptor_offset": hex(cursor-12), "payload_offset": hex(payload), "size": size,
                        "stored_slot": slot, "source_first12_hex": header[:12].hex().upper(),
                        "source_body_sha256": hashlib.sha256(header[12:]).hexdigest().upper(),
                        "source_unknown_0d_to_0f": header[13:16].hex().upper(), "source_unknown_1d_to_1f": header[29:32].hex().upper()}
                    if data is not None:
                        offset = 0x114D8+slot*0x60DC
                        item["actual_save_body_matches"] = header[12:]==data[offset+12:offset+200]
                        item["actual_save_ready_byte"] = data[offset+0xCC]
                    candidates.append(item)
        report["asset_observation"] = {"definition_candidates": candidates,
            "scope": "Bounded in-memory scan of original sibling level_cached.psarc gameplay.dat resources for class535/strideC8 descriptors. Reports first referenced payload per matching descriptor, not a complete resource schema or count of every volume instance. Exact body matches are separate actual-save observations. Shipped opaque-byte zeros do not establish padding."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path, help="Plaintext working copy, never modified")
    parser.add_argument("--archive", type=Path, help="Original packed/game/global_cached.psarc; locate sibling levels and read resources in-memory")
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save, args.archive), indent=2))
