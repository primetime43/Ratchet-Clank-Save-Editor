"""Read-only exact-build object definitions and pool allocation provenance.

Shipped definition ordinals are NOT automatically saved physical pool slots.
No native allocator, script payload, callback or runtime pointer is executed.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import runpy
import struct

BASE = Path(__file__).resolve().parent
BINDINGS = runpy.run_path(str(BASE / "Inspect-TodWeaponBindings.py"))
SEGMENTS = runpy.run_path(str(BASE / "Inspect-TodSegmentConfig.py"))


def definition(raw):
    """One bounded 72-byte asset record, retaining uninterpreted words/bytes."""
    if len(raw) != 0x48:
        raise ValueError("Object definition must be exactly72 bytes")
    return {"class_id": struct.unpack_from(">H", raw, 0x3C)[0],
            "load_mode": struct.unpack_from(">H", raw, 0x42)[0],
            "segment_name_index": struct.unpack_from(">H", raw, 0x44)[0],
            "before_complete_gate_byte": raw[0x40], "after_complete_gate_byte": raw[0x41],
            "copied_runtime_byte_170": raw[0x3F], "scaled_runtime_byte_46": raw[0x46],
            "raw_words_00_38": [f"{v:08X}" for v in struct.unpack_from(">15I", raw)],
            "opaque_byte_3e": f"{raw[0x3E]:02X}", "opaque_byte_47": f"{raw[0x47]:02X}",
            "raw_hex": raw.hex().upper()}


def gameplay_definitions(raw):
    """Validate IGHW directory, relocation chain and root-owned definition spans.

    The directory count's upper nibble is retained by the underlying format;
    only its observed low28 element count is used. Bounds are tooling limits,
    not evidence that the game validates malformed assets or save bit indices.
    """
    names_catalog = SEGMENTS["gameplay_catalog"](raw)
    count, header_end, total, reloc_count = struct.unpack_from(">4I", raw, 8)
    sections = {}
    spans = []
    for i in range(count):
        kind, offset, encoded, stride = struct.unpack_from(">4I", raw, 32 + i * 16)
        n = encoded & 0x0FFFFFFF
        end = offset + n * stride
        if any(offset < old_end and old_start < end for old_start, old_end in spans):
            raise ValueError("Overlapping gameplay sections")
        spans.append((offset, end))
        sections[kind] = (offset, n, stride)
    if any(k not in sections for k in (0x25100, 0x7340)):
        raise ValueError("Missing object root/definition section")
    meta, nmeta, smeta = sections[0x25000]
    roots, nroot, sroot = sections[0x25100]
    defs, ndef, sdef = sections[0x7340]
    if (nmeta, smeta, sroot, sdef) != (1, 44, 0x80, 0x48) or nroot > 256 or ndef > 65536:
        raise ValueError("Unexpected object root/definition layout")
    if struct.unpack_from(">2I", raw, meta) != (roots, nroot):
        raise ValueError("Metadata and root directory disagree")
    relocations = set(struct.unpack_from(f">{reloc_count}I", raw, total))
    if len(relocations) != reloc_count or any(v % 4 or not header_end <= v <= total - 4 for v in relocations):
        raise ValueError("Invalid/duplicate relocation location")
    if meta not in relocations:
        raise ValueError("Metadata root pointer is not relocated")
    names, nname, _ = sections[0x250C0]
    pool, _, pool_size = sections[0x79C0]
    loaded_names = []
    for i in range(nname):
        pointer = struct.unpack_from(">I", raw, names + 4 * i)[0]
        end = raw.find(b"\0", pointer, min(pool + pool_size, pointer + 256))
        loaded_names.append(raw[pointer:end].decode("ascii", errors="strict"))
    result = []
    for i in range(nroot):
        root = roots + i * sroot
        name_fields = []
        for member in (0, 9):
            end = raw.find(b"\0", root + member, root + member + 9)
            if end < 0:
                raise ValueError("Unterminated object-root selector name")
            name_fields.append(raw[root + member:end].decode("ascii", errors="strict"))
        pointer, n = struct.unpack_from(">2I", raw, root + 0x40)
        if not defs <= pointer <= defs + ndef * sdef or (pointer - defs) % sdef or pointer + n * sdef > defs + ndef * sdef:
            raise ValueError("Object root definition span outside directory section")
        if root + 0x40 not in relocations:
            raise ValueError("Root definition pointer is not relocated")
        records = [definition(raw[pointer + j * sdef:pointer + (j + 1) * sdef]) for j in range(n)]
        class_counts = Counter(r["class_id"] for r in records)
        mode_counts = Counter(r["load_mode"] for r in records)
        zone_counts = Counter(r["segment_name_index"] for r in records)
        examples = []
        for j, record in enumerate(records[:4]):
            examples.append({"definition_ordinal": j, "asset_offset": hex(pointer + j * sdef), **record})
        result.append({"root_ordinal": i, "root_offset": hex(root), "selector_names": name_fields,
                       "definition_offset": hex(pointer), "definition_count": n,
                       "directory_first_ordinal": (pointer - defs) // sdef,
                       "classes": [{"class_id": k, "definition_count": v} for k, v in sorted(class_counts.items())],
                       "load_modes": [{"mode": k, "definition_count": v} for k, v in sorted(mode_counts.items())],
                       "segment_references": [{"loaded_name_index": k, "reference_name": loaded_names[k] if k < nname else None,
                                               "definition_count": v} for k, v in sorted(zone_counts.items())],
                       "examples": examples})
    return {"gameplay_dat_sha256": hashlib.sha256(raw).hexdigest().upper(), "size": len(raw),
            "directory_definition_count": ndef, "metadata_offset": hex(meta), "roots": result,
            "warning": "Reference asset records only, not saved object names or a current live allocation map. Selector names select root groups, not individual object names. Class IDs are numeric native class-table indices, not localized names. Segment names describe reference associations, not current saved presence/completion."}


def first_free_preview(words, capacity):
    """Bounded model of common scan order, not execution of native allocation.

    A supplied bitmap starts at bit0 in word0. Tooling requires a whole128-bit
    bitmap block per native scan block and rejects negative/malformed capacity.
    Reservation marks a padding bit even if it is >=capacity; creation marks
    that same bit but then rejects it before object initialization.
    """
    if type(capacity) is not int or not 0 <= capacity <= 65536:
        raise ValueError("Supply a bounded unsigned capacity")
    if type(words) not in (list, tuple) or len(words) != 4 * ((capacity + 127) // 128):
        raise ValueError("Bitmap must contain complete128-bit scan blocks")
    if any(type(w) is not int or not 0 <= w <= 0xFFFFFFFF for w in words):
        raise ValueError("Bitmap words must be unsigned32")
    for i, word in enumerate(words):
        for bit in range(32):
            if not word & (1 << bit):
                slot = i * 32 + bit
                updated = list(words)
                updated[i] |= 1 << bit
                return {"reserved_index": slot, "creation_admitted": slot < capacity, "bitmap_words": updated}
    return {"reserved_index": None, "creation_admitted": False, "bitmap_words": list(words)}


def inspect(elf_path, save_path=None, archive_path=None):
    elf = BINDINGS["Elf"](elf_path)
    checks = {0x89FC5C: 0x84DF28, 0x89FC74: 0x1064FC80, 0x8A7610: 0x1064FC80,
              0x8AA320: 0x1064FC80, 0x8A9B68: 0x10724B18,
              0x84DF50: 0x87E6C0, 0x84DF54: 0x87E6E0, 0x84DF64: 0x86D9B0,
              0x87E6C0: 0x68F328, 0x87E6E0: 0x68F5F0,
              0x68F034: 0xA09C003C, 0x68F03C: 0x83A90028, 0x68F0B8: 0x812B002C,
              0x68F0B0: 0x80DC0000, 0x68F0B4: 0x80FC0038, 0x68F084: 0x38A0FFFF,
              0x68F0D8: 0x677A0001, 0x68F0E4: 0x935D0068,
              0x521364: 0x93BF0064, 0x5213A8: 0xB39F0050, 0x5213BC: 0x800900BC,
              0x5213D0: 0x901F0054, 0x523F20: 0x908C0000, 0x523F80: 0x4085FFAC,
              0x523FD4: 0x54A5801E, 0x68F654: 0x91490000,
              0x68F684: 0x901F0040, 0x68F688: 0x93C90014,
              0x2F86B4: 0x80040044, 0x2F86F4: 0x80DE0040, 0x2F86E8: 0x3B9C0048,
              0x2F8738: 0x913A0014, 0x51FD30: 0x90C40000,
              0x651428: 0x81229D0C, 0x65142C: 0x80690004,
              0x651440: 0x90090004, 0x651444: 0x90690000,
              0x6515BC: 0x3BFF0080, 0x6515D8: 0x38BF0009,
              0x6515F0: 0x93FA0004, 0x651630: 0x80DB0000, 0x651634: 0x90DA0004,
              0x3D2238: 0xA01F0016, 0x3D223C: 0x83C30040}
    for va, value in checks.items():
        if elf.u32(va) != value:
            raise ValueError(f"Object definition evidence changed at {va:#x}: {elf.u32(va):08X}")
    calls = ((0x252054, 0x68EFC8), (0x59E70C, 0x523E58), (0x2506B4, 0x651428),
             (0x251464, 0x651438), (0x2515C4, 0x651540), (0x523FF0, 0x521308),
             (0x2F86D8, 0x252048), (0x2F870C, 0x2F79E0), (0x2F8724, 0x51FC88),
             (0x68F340, 0x59E700), (0x68F668, 0x59DD70), (0x3D2260, 0x252048))
    guards = {va: elf.read(va, 4) for va in checks}
    for va, target in calls:
        if BINDINGS["branch_target"](elf.u32(va), va) != target:
            raise ValueError(f"Object definition branch changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    functions = {0x68EFC8: 0x8AFE5C, 0x68F328: 0x8AFE5C, 0x68F5F0: 0x8AFE5C,
                 0x523E58: 0x89FF20, 0x521308: 0x89FF20, 0x51FC88: 0x89FF20,
                 0x2F8690: 0x89FF20, 0x651428: 0x8AFE5C, 0x651438: 0x8AFE5C,
                 0x651540: 0x8AFE5C, 0x3D2170: 0x89FF20,
                 0x2F79E0: 0x89FF20, 0x2D18B0: 0x89FF20}
    for va, toc in functions.items():
        if elf.descriptors[va] != toc:
            raise ValueError("Object definition descriptor TOC changed")
        end = elf.functions[elf.functions.index(va) + 1]
        guards[va] = elf.read(va, end - va)
    guards[0x39A4D8] = elf.read(0x39A4D8, 0x50)
    report = {"confidence": "code-backed",
              "warning": "Exact USA BCUS98127 v02.00 static evidence. Definition ordinal, class ID, physical saved pool slot and generation-bearing handle are distinct. No object name, current instance, unconditional ordinal-to-bit binding or in-game edit safety inferred.",
              "asset_layout": {"metadata_section": "0x25000", "metadata_root_pointer_member": "0x0", "metadata_root_count_member": "0x4",
                               "root_section": "0x25100", "root_stride": "0x80", "root_definition_pointer_member": "0x40", "root_definition_count_member": "0x44",
                               "definition_section": "0x7340", "definition_stride": "0x48"},
              "root_selection": "39A328 obtains25000 metadata and registers it through251458->651438.2515B8->651540 clears selected root, walks metadata+0/count+4 at stride80, compares requested name with root+0 and+9, uses first match or first-root fallback.651428 returns selected root, not metadata or a saved pointer. Supplied native assets are independently validated through directory and relocation chain.",
              "definition_fields": [
                  {"offset": "0x0", "size": 4, "meaning": "Raw32 argument forwarded to virtual+2C actor creation; not a UID or object name."},
                  {"offset": "0x4", "size": 4, "meaning": "Opaque word; preserved without a semantic label."},
                  {"offset": "0x8", "size": 4, "meaning": "Float override for runtime+110 when nonnegative by native fsel; default retained for negative finite values. Nonfinite behavior not modeled."},
                  {"offset": "0xc", "size": 4, "meaning": "Float override for runtime+60 under same fsel rule; not assigned a gameplay stat name."},
                  {"offset": "0x10", "size": 8, "meaning": "Two32-bit masks shifted left1 (high input bit discarded), combined with runtime BE64+118: ((word14<<1)|1) & ((word10<<1)|old118). Not saved event bits."},
                  {"offset": "0x18", "size": 12, "meaning": "Three float inputs copied to runtime+30/+34/+38 and third repeated at+3C; positional vector, axis labels unverified."},
                  {"offset": "0x24", "size": 12, "meaning": "Three float inputs passed to transform builder5A4B58; output vectors copied to runtime+0/+10/+20. Angle units/order not established."},
                  {"offset": "0x30", "size": 4, "meaning": "Float copied to runtime+D0; not named as a gameplay stat."},
                  {"offset": "0x34", "size": 4, "meaning": "Opaque word."},
                  {"offset": "0x38", "size": 4, "meaning": "Raw32 second actor-creation argument, independent of definition+0."},
                  {"offset": "0x3c", "size": 2, "meaning": "Unsigned native class ID: virtual+28 allocation, stored runtime+50, indexes pool-root+BC pointer table into runtime+54. Not generation UID."},
                  {"offset": "0x3e", "size": 1, "meaning": "Opaque byte."},
                  {"offset": "0x3f", "size": 1, "meaning": "Copied to runtime+170, meaning unnamed."},
                  {"offset": "0x40", "size": 2, "meaning": "Separate bytes40/41 used by mode2 before/after segment-complete gate; not a BE16 flag."},
                  {"offset": "0x42", "size": 2, "meaning": "Load mode: mode1 checks saved suppression using loader ordinal; mode2 uses checkpoint/segment gates; other modes admit through this predicate only."},
                  {"offset": "0x44", "size": 2, "meaning": "Loaded segment-name index passed to2D18B0; not saved segment slot or class ID."},
                  {"offset": "0x46", "size": 1, "meaning": "Unsigned byte converted/scaled for runtime+130 with native float selection; stat name unverified."},
                  {"offset": "0x47", "size": 1, "meaning": "Opaque byte."}],
              "allocation": {"root_va": "0x1064fc80", "runtime_entry_stride": "0x180",
                             "order": "523E58 and51FC88 scan the same bitmap(root+4), low bits first, four words per128-bit block. Rejected filtered definitions reserve a bit through51FC88 instead of creating/compacting an object; loader then increments root+14 even without checking reservation result.",
                             "handle": "Successful523E58 creates pointer=base+slot*180 and handle=slot | ((old generation low16)<<16), increments generation with low16>FFFD reset to1.521308 stores handle at+64 and class ID at+50.68F5F0 copies handle into the separate8-byte actor-record table and links pool+40 to actor / actor+14 back to pool.",
                             "bounds": "Creation marks first free bitmap bit BEFORE signed index/capacity validation. Reservation does not perform the same index<capacity check; padding bits and failed reservations are not emulated as safe allocations.",
                             "ordinal_binding_limit": "Empty bitmap, enough capacity, exactly one uninterrupted reservation/allocation per definition and no nested allocation/free would yield ordinal=physical slot. These runtime prerequisites are not reconstructed from GAME.SAV.3D2170 later selects a definition using runtime ushort+16 and calls the same creation path; class ID and definition ordinal cannot be used as universal saved bit labels."},
              "recommended_annotations": [
                  {"va": "0x68efc8", "kind": "function", "name": "TOD_object_create_from_asset_definition_verified", "comment": "Reads72-byte asset definition; ushort3C class ID to virtual+28, two raw actor args+0/+38 to virtual+2C. Copies transform/qualified overrides; sets runtime68 flag10000. Not a saved UID or unconditional bit identity."},
                  {"va": "0x68f328", "kind": "function", "name": "TOD_object_class_allocation_callback_verified", "comment": "Vtable84DF28+28 descriptor87E6C0. Calls59E700->523E58 with class ID and1, then runtime initialization. Does not map names or guarantee allocation success."},
                  {"va": "0x523e58", "kind": "function", "name": "TOD_object_first_free_pool_allocate_verified", "comment": "Firstfree bitmap root1064FC80; marks bit before signed/capacity checks; stride180. Generation-bearing handle initialized through521308. Not ordinal identity unless runtime allocation prerequisites hold."},
                  {"va": "0x521308", "kind": "function", "name": "TOD_object_initialize_class_and_generation_handle_verified", "comment": "Clears180-byte runtime entry, stores generated handle+64, class ushort+50, class table(root+BC+4*class) pointer+54. Class index/handle/poolslot distinct; no saved object-name proof."},
                  {"va": "0x68f5f0", "kind": "function", "name": "TOD_object_actor_record_handle_link_verified", "comment": "Physical pool slot selects8-byte runtime actor-record table; writes handle+64, creates actor, links pool+40 and actor+14 when result nonzero. Uses inputpool pointer, not decompiler's undefined-register artifact."},
                  {"va": "0x3d2170", "kind": "function", "name": "TOD_object_runtime_spawn_from_definition_verified", "comment": "After runtime virtual gates, ushort+16 selects definition in selected root+40 at stride48, then calls252048->68EFC8. Later creation disproves unconditional class/ordinal-as-saved-slot labels; native effects not simulated."}],
              "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())]}
    if archive_path is not None:
        segments = SEGMENTS["inspect"](elf_path)
        psarc = SEGMENTS["BINDINGS"].module("tod_object_definition_psarc", BINDINGS["ROOT"] / "Tools/Inspect-Psarc.py")
        levels = []
        for row in segments["level_folders"]:
            folder = row["folder"]
            if not folder or any(c in folder for c in "/\\:\0") or folder in (".", ".."):
                raise ValueError("Unsafe native level folder")
            archive = psarc.Psarc(Path(archive_path).parent.parent / "levels" / folder / "level_cached.psarc")
            indexes = [i for i, n in enumerate(archive.names) if n == f"/built/levels/{folder}/gameplay.dat"]
            if len(indexes) != 1:
                raise ValueError("Gameplay asset absent or ambiguous")
            levels.append({**row, **gameplay_definitions(archive.read_entry(indexes[0], 32 * 1024 * 1024))})
        report["asset_observation"] = {"levels": levels, "named_world_count": len(levels),
                                       "definition_count": sum(v["directory_definition_count"] for v in levels),
                                       "warning": "Shipped reference catalogs, not private save contents. No object-level names or current runtime allocation reconstructed."}
    if save_path is not None:
        save = Path(save_path)
        if save.stat().st_size != 0x906F0:
            raise ValueError("Expected verified plaintext save size")
        raw = save.read_bytes()
        if len(raw) != 0x906F0 or [struct.unpack_from(">I", raw, i * 20)[0] for i in range(32)] != list(range(32)):
            raise ValueError("Expected verified plaintext inventory header")
        report["save_observation"] = {"sha256": hashlib.sha256(raw).hexdigest().upper(),
                                      "worlds": [{"physical_world_slot": i,
                                                  "recorded_set_count": sum(v.bit_count() for v in raw[0x668 + i * 0x408:0x668 + i * 0x408 + 256]),
                                                  "suppression_set_count": sum(v.bit_count() for v in raw[0x768 + i * 0x408:0x768 + i * 0x408 + 256])} for i in range(20)],
                                      "warning": "Stored bits contain no definition class IDs, selector names or generated runtime handles; reference catalogs do not make every bit identifiable."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.elf, args.save, args.archive), indent=2))
    except (ValueError, OSError) as error:
        parser.exit(2, f"Object definition inspection failed: {error}\n")
