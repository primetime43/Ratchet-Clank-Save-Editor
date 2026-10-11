"""Read-only exact-build class registry and class-to-actor resource evidence.

Class indices, saved physical slots, generated handles and resource identifiers
are distinct. This tool does not execute allocators, actors or script payloads.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BASE = Path(__file__).resolve().parent
BINDINGS = runpy.run_path(str(BASE / "Inspect-TodWeaponBindings.py"))
DEFINITIONS = runpy.run_path(str(BASE / "Inspect-TodObjectDefinitions.py"))


def flag_packet(raw):
    """Bounded source record: BE64 flags, byte length, then opaque bytes.

    The observed payload is copied to class runtime storage, not decoded as
    text. This is a diagnostic record model, not a complete resource parser.
    """
    if len(raw) < 9 or len(raw) != 9 + raw[8]:
        raise ValueError("Expected eight flag bytes, one length byte and exact opaque payload")
    return {"flags_hex": raw[:8].hex().upper(), "payload_length": raw[8],
            "payload_hex": raw[9:].hex().upper(), "raw_hex": raw.hex().upper()}


def actor_lookup_inputs(explicit_primary, class_primary, secondary=0x66):
    """Bounded model of callback argument fallback, not native lookup/execution."""
    if any(type(v) is not int or not 0 <= v <= 0xFFFFFFFF
           for v in (explicit_primary, class_primary, secondary)):
        raise ValueError("Resource argument values must be unsigned32")
    return {"primary": class_primary if explicit_primary == 0xFFFFFFFF else explicit_primary,
            "secondary": secondary,
            "uses_class_default": explicit_primary == 0xFFFFFFFF,
            "warning": "Arguments only; neither identifier is a saved pool slot, class ID or proven object name."}


def main_classes(raw):
    """Bounded IGHW D100 -> class+78 -> sourceheader+38 packet provenance.

    Asset pointers are file-relative relocation values, never process pointers.
    Uninterpreted fields remain opaque; class ordinals are reference IDs only.
    """
    if len(raw) < 48 or len(raw) > 128 * 1024 * 1024 or raw[:8] != bytes.fromhex("4947485700010001"):
        raise ValueError("Expected bounded IGHW reference main.dat")
    count, header_end, total, reloc_count = struct.unpack_from(">4I", raw, 8)
    if not 1 <= count <= 256 or header_end != 32 + count * 16 or not header_end <= total <= len(raw) or total + reloc_count * 4 != len(raw):
        raise ValueError("Invalid main.dat directory/relocation bounds")
    if reloc_count > (total - header_end) // 4:
        raise ValueError("Relocation count exceeds possible unique aligned body locations")
    sections = {}
    spans = []
    for i in range(count):
        kind, offset, encoded, stride = struct.unpack_from(">4I", raw, 32 + i * 16)
        n = encoded & 0x0FFFFFFF
        end = offset + n * stride
        if kind in sections or not n or not stride or not header_end <= offset < end <= total or any(offset < oe and os < end for os, oe in spans):
            raise ValueError("Invalid duplicate/overlapping main.dat section")
        sections[kind] = (offset, n, stride)
        spans.append((offset, end))
    if 0xD100 not in sections or 0x10200 not in sections:
        raise ValueError("Missing class/source-header section")
    classes, nclass, stride = sections[0xD100]
    source, nsource, source_stride = sections[0x10200]
    source_end = source + nsource * source_stride
    if stride != 0xC0 or nclass > 4096 or nsource != 1:
        raise ValueError("Unexpected class/source-header layout")
    relocations = set(struct.unpack_from(f">{reloc_count}I", raw, total))
    if len(relocations) != reloc_count or any(v % 4 or not header_end <= v <= total - 4 for v in relocations):
        raise ValueError("Invalid duplicate/unaligned main.dat relocation")
    result = []
    for class_id in range(nclass):
        record = classes + class_id * stride
        header = struct.unpack_from(">I", raw, record + 0x78)[0]
        if record + 0x78 not in relocations or header % 4 or not source <= header <= source_end - 0x40:
            raise ValueError("Class source-header pointer outside relocated source section")
        packet = struct.unpack_from(">I", raw, header + 0x38)[0]
        if header + 0x38 not in relocations or not source <= packet <= source_end - 9:
            raise ValueError("Class flag-packet pointer outside relocated source section")
        length = raw[packet + 8]
        if packet + 9 + length > source_end:
            raise ValueError("Class opaque payload outside source section")
        result.append({"class_id": class_id, "asset_offset": hex(record),
                       "source_header_offset": hex(header), "flag_packet_offset": hex(packet),
                       "default_primary_actor_identifier": f"0x{struct.unpack_from('>I', raw, record + 0x64)[0]:08X}",
                       "raw_class_flags_10": f"0x{struct.unpack_from('>I', raw, record + 0x10)[0]:08X}",
                       "source_header_raw_hex": raw[header:header + 0x40].hex().upper(),
                       "class_record_raw_hex": raw[record:record + stride].hex().upper(),
                       "flag_packet": flag_packet(raw[packet:packet + 9 + length])})
    return {"main_dat_sha256": hashlib.sha256(raw).hexdigest().upper(), "size": len(raw),
            "class_section_offset": hex(classes), "class_count": nclass, "classes": result,
            "warning": "Reference class ordinals and opaque source data, not current saved-bit identities, live class pointers or named objects. Original runtime preparation can subsequently mutate these records."}


def inspect(elf_path, archive_path=None):
    elf = BINDINGS["Elf"](elf_path)
    words = {0x8AA350: 0x1064FD00, 0x8AA34C: 0x1064FD3C,
             0x8A6CE8: 0x1064FD3C, 0x8A6CFC: 0x1064FD00,
             0x4AA094: 0x80A26DDC, 0x4AA0CC: 0xF8A100B8,
             0x4AA0E8: 0x816A0000, 0x4AA0EC: 0x818A0004,
             0x4AA0F4: 0x7F686214, 0x4AA870: 0x2F84D100,
             0x4AA878: 0x82CA0008, 0x4AA880: 0x56CB013E,
             0x4AA888: 0x916C0010, 0x4AA898: 0x81626DC8,
             0x4AA8B4: 0x93690000, 0x4AA8B8: 0x3B7B00C0,
             0x8A7610: 0x1064FC80, 0x8AA320: 0x1064FC80,
             0x5212BC: 0x387D0080, 0x5212B8: 0x38A00580,
             0x5212D0: 0x387D00BC, 0x5212D8: 0x38A00500,
             0x5213A8: 0xB39F0050, 0x5213BC: 0x800900BC,
             0x5213D0: 0x901F0054, 0x68F6A8: 0x80FE0054,
             0x68F6AC: 0x81870064, 0x68F634: 0x39000066,
             0x68F658: 0x419E0050, 0x68F664: 0x80630004,
             0x68F82C: 0xA1240016, 0x68FAFC: 0x83F80078,
             0x68FB00: 0x829F0004, 0x68FB0C: 0x809F0038,
             0x68FB14: 0xEB970000, 0x68FB18: 0xFB980070,
             0x68FB1C: 0x89770008, 0x68FB20: 0x91780068,
             0x68FB70: 0x9078006C, 0x68FCBC: 0x3BC40009,
             0x68FCB4: 0x90780044,
             0x68FD98: 0x83B90010, 0x68FDDC: 0x80890000,
             0x68FE30: 0xA10C0000, 0x68FE44: 0x83C9003C,
             0x68FE48: 0x83BE0044, 0x68FE58: 0x8809000D}
    guards = {}
    for va, expected in words.items():
        if elf.u32(va) != expected:
            raise ValueError(f"Object class evidence changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    calls = {0x5212C0: 0x252938, 0x5212EC: 0x252938,
             0x68F668: 0x59DD70, 0x59DD7C: 0x5014F8,
             0x68FDE0: 0x68F7F0, 0x68FCAC: 0x5CF128,
             0x68FCCC: 0x81A9A8}
    for va, target in calls.items():
        if BINDINGS["branch_target"](elf.u32(va), va) != target:
            raise ValueError(f"Object class call changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    functions = {0x4A9FA0: 0x89FF20, 0x5212A0: 0x89FF20, 0x521308: 0x89FF20,
                 0x68F5F0: 0x8AFE5C, 0x68F7F0: 0x8AFE5C,
                 0x68FCD8: 0x8AFE5C, 0x68FD60: 0x8AFE5C,
                 0x5014F8: 0x89FF20, 0x501270: 0x89FF20}
    for va, toc in functions.items():
        if elf.descriptors[va] != toc:
            raise ValueError("Object class descriptor TOC changed")
        end = elf.functions[elf.functions.index(va) + 1]
        guards[va] = elf.read(va, end - va)
    guards[0x4AA870] = elf.read(0x4AA870, 0x58)
    guards[0x4AA080] = elf.read(0x4AA080, 0x34)
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA BCUS98127 v02.00 runtime/reference evidence. No current live instance, localized object name or saved-bit identity inferred; no edit enabled.",
        "registry": {"pool_root_va": "0x1064fc80", "class_subobject_va": "0x1064fd00",
                     "class_pointer_array_va": "0x1064fd3c",
                     "class_count_member_from_subobject": "0x10",
                     "indexed_lookup_member_from_subobject": "0x3c",
                     "reset": "5212A0 clears pool+80 length580, sets subobject+0 to0 and+4/+8/+C to1, and separately clears inline pointer arrayBC length500(320 pointer cells). This reset span is not a native class-ID bound check or a recovered named catalog.",
                     "pointer_aliases": "8AA350 points to pool+80, not an independent resource root.8AA34C points to pool+BC, the same table consumed by521308 via class*4.68FD60/68FCD8 iterate pointed class records from this array using subobject+10 count.",
                     "producer": "4A9FA0 recognizes IGHW sectionD100, takes low28-bit element count into classsubobject+10, populates pointer array1064FD3C with consecutive C0-byte resource records. Thus class ID indexes the reference D100 record ordinal for that loaded resource, not the physical saved pool slot. Assetdirectory stride and relocated+78/header+38 source links are checked independently.",
                     "unresolved": "Class/source records and actor lookup IDs are not localized names. Live class-table contents cannot be read from on-disk ELF BSS; later runtime allocation and chosen resource/world are not serialized as a class table in GAME.SAV."},
        "actor_resource_lookup": {"callback_va": "0x68f5f0", "factory_va": "0x5014f8",
                                  "class_primary_member": "0x64", "secondary_argument": "0x66",
                                  "chain": "Object definition class ushort+3C is stored at runtime+50 and resolves class config at runtime+54. Actor callback uses explicit primary argument unless it equalsFFFFFFFF; only then config+64 supplies primary identifier. Calls59DD70->5014F8 with primary r7 and secondary r8=66; these are lookup arguments, not class ID or named save objects.",
                                  "factory_limits": "5014F8 returns zero when allocator r3 or secondary r8 equalsFFFFFFFF. It can try supplied resource pointers first, then primary lookup when notFFFFFFFF, then secondary lookup; failed primary is not evidence of a class or saved-bit name.",
                                  "resource_kind": "501270 requires resource section25200 before copying/relocating actor data and invoking runtime factory callbacks. No actor/resource payload is executed by this inspector."},
        "class_preparation": {"function_va": "0x68f7f0",
                              "record_members": [
                                  {"offset": "0x16", "meaning": "Unsigned source count; drives runtime32-byte records at class+40, source pointer array+24, source records+80 stride30."},
                                  {"offset": "0x44", "meaning": "Prepared auxiliary resource pointer returned by5CF128 when class+78 header+4 is nonzero;68FD60 counts its byte+D per selected definition."},
                                  {"offset": "0x48", "meaning": "Optional resource; cleared when its nested+74 header ushort+2 is zero, otherwise nested resource byte+78 gains10."},
                                  {"offset": "0x4c", "meaning": "Optional resource; nonzero nested byte+78 gains10."},
                                  {"offset": "0x68", "meaning": "Opaque payload byte length widened to32, sourced from class+78 -> header+38 -> byte+8."},
                                  {"offset": "0x6c", "meaning": "Allocated destination of source packet bytes+9; length class+68, storage16-byte rounded. Not labeled as a string."},
                                  {"offset": "0x70", "meaning": "BE64 flags copied from source packet+0; later ORed into initialized runtime object+118. Not save bitsets."},
                                  {"offset": "0x78", "meaning": "Relocated pointer from D100 class record to source header in main.dat section10200."}],
                              "payload_boundary": "Header+38 points to8 flag bytes, one unsigned length byte and that many opaque payload bytes at+9. ASCII-looking bytes would not prove an object name; no NUL/text decoding assumption.",
                              "scope": "Preparation mutates runtime class records before pool/object load. These class records and pointers are not GAME.SAV fields."},
        "recommended_annotations": [
            {"va": "0x5212a0", "kind": "function", "name": "TOD_object_class_registry_reset_verified",
             "comment": "Clears runtime pool+80 state and inline class-pointer array pool+BC span500hex=320pointercells. Not class-table producer, ID bound predicate or named saved-object mapping."},
            {"va": "0x68f7f0", "kind": "function", "name": "TOD_object_class_resource_prepare_verified",
             "comment": "Prepares runtime D100 class record. Class+78 sourceheader+38 packet(section10200): copiesBE64flags to+70; byte8length to+68; opaque bytes9 onward toallocated+6C. No text/name assumption or saved-bit identity."},
            {"va": "0x68fcd8", "kind": "function", "name": "TOD_object_class_array_prepare_verified",
             "comment": "Iterates class-pointer array1064FD3C, count1064FD00+10, calls68F7F0 with eachpointedrecord. Samepoolroot+BC inlineclassarray, not separate resource root or saved instance identity."},
            {"va": "0x4a9fa0", "kind": "function", "name": "TOD_resource_sections_register_including_object_classes_verified",
             "comment": "Native resource branch registers sectionD100 low28 count and pointerarray1064FD3C at consecutive C0-byte records. Numeric class IDs are per-loaded-resource ordinals, not saved physical slots or names."}],
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())]}
    if archive_path is not None:
        catalog = DEFINITIONS["inspect"](elf_path, archive_path=archive_path)["asset_observation"]
        by_class = {}
        for level in catalog["levels"]:
            for root in level["roots"]:
                for row in root["classes"]:
                    record = by_class.setdefault(row["class_id"], {"class_id": row["class_id"], "reference_definition_count": 0, "world_folders": []})
                    record["reference_definition_count"] += row["definition_count"]
                    if level["folder"] not in record["world_folders"]:
                        record["world_folders"].append(level["folder"])
        psarc = DEFINITIONS["SEGMENTS"]["BINDINGS"].module("tod_object_class_psarc", BINDINGS["ROOT"] / "Tools/Inspect-Psarc.py")
        levels = []
        for level in catalog["levels"]:
            folder = level["folder"]
            archive = psarc.Psarc(Path(archive_path).parent.parent / "levels" / folder / "level_cached.psarc")
            name = f"/built/levels/{folder}/main.dat"
            indexes = [i for i, n in enumerate(archive.names) if n == name]
            if len(indexes) != 1:
                raise ValueError("Class main.dat missing or ambiguous")
            record = main_classes(archive.read_entry(indexes[0], 64 * 1024 * 1024))
            if any(c["class_id"] >= record["class_count"] for group in level["roots"] for c in group["classes"]):
                raise ValueError("Reference definition class ID outside same-world class directory")
            compact_classes = []
            for source_record in record["classes"]:
                packet = source_record["flag_packet"]
                compact_classes.append({key: source_record[key] for key in
                                        ("class_id", "asset_offset", "source_header_offset", "flag_packet_offset",
                                         "default_primary_actor_identifier", "raw_class_flags_10")})
                compact_classes[-1]["flag_packet"] = {"flags_hex": packet["flags_hex"],
                                                     "payload_length": packet["payload_length"],
                                                     "payload_sha256": hashlib.sha256(bytes.fromhex(packet["payload_hex"])).hexdigest().upper()}
            levels.append({"folder": folder, "level_id": level["level_id"],
                           **{k: v for k, v in record.items() if k != "classes"}, "classes": compact_classes})
        report["asset_observation"] = {"classes": [by_class[k] for k in sorted(by_class)],
                                       "levels": levels,
                                       "reference_class_record_count": sum(level["class_count"] for level in levels),
                                       "named_world_count": catalog["named_world_count"],
                                       "definition_count": catalog["definition_count"],
                                       "warning": "Numeric classes counted from bounded reference object definitions across all root groups, not loaded-world selection, class-name bindings or current saved pool allocation."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.elf, args.archive), indent=2))
    except (ValueError, OSError) as error:
        parser.exit(2, f"Object class inspection failed: {error}\n")
