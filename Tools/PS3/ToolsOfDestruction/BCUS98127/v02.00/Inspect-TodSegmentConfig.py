"""Read-only exact-build gameplay-zone loader and bounded shipped slot catalogs.

No script execution, binary extraction or mutation. The optional archive is the
original global_cached.psarc; sibling packed/levels archives are read in place.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct


SPEC = importlib.util.spec_from_file_location("tod_segment_bindings", Path(__file__).with_name("Inspect-TodSegmentBindings.py"))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)


def segment_hash(name):
    """Native signed-byte djb2, uint32 wrapping; empty maps to40."""
    if isinstance(name, str):
        name = name.encode("ascii")
    if b"\0" in name:
        raise ValueError("Embedded NUL segment name")
    if not name:
        return 40
    value = 5381
    for byte in name:
        value = (value * 33 + (byte if byte < 128 else byte - 256)) & 0xFFFFFFFF
    return value % 49


def gameplay_catalog(raw):
    """Decode only validated IGHW descriptors and metadata-referenced names."""
    if not 32 <= len(raw) <= 32 * 1024 * 1024 or raw[:8] != bytes.fromhex("4947485700010001"):
        raise ValueError("Unsupported gameplay header/size")
    count, header_end, total, reloc_count = struct.unpack_from(">4I", raw, 8)
    if not 1 <= count <= 1024 or reloc_count > 1_000_000 or header_end != 32 + count * 16 or total < header_end or total + reloc_count * 4 != len(raw):
        raise ValueError("Invalid gameplay directory bounds")
    sections = {}
    for index in range(count):
        kind, offset, encoded_count, stride = struct.unpack_from(">4I", raw, 32 + index * 16)
        n = encoded_count & 0x0FFFFFFF
        if kind in sections or n == 0 or stride == 0 or offset < header_end or offset + n * stride > total:
            raise ValueError("Invalid/duplicate gameplay section")
        sections[kind] = (offset, n, stride)
    if any(kind not in sections for kind in (0x25000, 0x250C0, 0x79C0)):
        raise ValueError("Missing gameplay name metadata")
    metadata, nmeta, smeta = sections[0x25000]
    names, nname, sname = sections[0x250C0]
    pool, npool, spool = sections[0x79C0]
    if (nmeta, smeta, sname, npool) != (1, 44, 4, 1) or nname > 50:
        raise ValueError("Unexpected gameplay name layout/count")
    if struct.unpack_from(">2I", raw, metadata + 0x24) != (names, nname):
        raise ValueError("Metadata and name section disagree")
    relocations = set(struct.unpack_from(f">{reloc_count}I", raw, total))
    if metadata + 0x24 not in relocations or any(names + i * 4 not in relocations for i in range(nname)):
        raise ValueError("Name pointers absent from relocation table")
    result, all_names, buckets = [], [], {}
    for index in range(nname):
        pointer = struct.unpack_from(">I", raw, names + index * 4)[0]
        if not pool <= pointer < pool + spool:
            raise ValueError("Gameplay name pointer outside string pool")
        end = raw.find(b"\0", pointer, min(pool + spool, pointer + 256))
        if end < 0:
            raise ValueError("Unterminated/oversized gameplay name")
        name = raw[pointer:end].decode("ascii", errors="strict")
        all_names.append(name)
        if not name.lower().startswith("gameplay_"):
            continue
        slot = len(result) + 1
        if slot >= 10:
            raise ValueError("Loaded gameplay names exceed saved segment slots")
        bucket = segment_hash(name)
        row = {"slot": slot, "name": name, "loaded_name_index": index,
            "name_offset": hex(pointer), "hash_bucket": bucket}
        result.append(row)
        buckets[bucket] = slot
    for row in result:
        row["resolved_lookup_slot"] = buckets[row["hash_bucket"]]
        row["hash_collision_shadowed"] = row["resolved_lookup_slot"] != row["slot"]
    return {"metadata_offset": hex(metadata), "name_table_offset": hex(names),
        "name_count": nname, "string_pool_offset": hex(pool), "string_pool_size": spool,
        "gameplay_dat_sha256": hashlib.sha256(raw).hexdigest().upper(), "size": len(raw),
        "relocation_count": reloc_count, "logical_size": total,
        "slot_zero": "Reserved: reverse lookup initialized toFFFFFFFF; invalid_zone fallback, not a named physical segment.",
        "segments": result}


def inspect(elf_path, save_path=None, archive_path=None):
    progression = BINDINGS.MISSIONS.PROGRESSION
    elf = progression.BINDINGS.Elf(elf_path)
    if elf.u32(0x89F154) != 0x10062F7C or elf.u32(0x840B90) != 0x100261D0 or elf.string(0x100261D0) != "gameplay_":
        raise ValueError("Exact-build native name table/prefix changed")
    levels = progression.exports(elf, 0x28440, "LEVEL_", 0x12990)
    if [v["id"] for v in levels] != list(range(20)) or levels[-1]["enum"] != "LEVEL_COUNT":
        raise ValueError("Unexpected native level catalog")
    catalog = [{"level_id": v["id"], "level_enum": v["enum"],
        "folder": elf.string(elf.u32(0x10062F7C + v["id"] * 4))} for v in levels[:-1]]
    guards = {0x89F154: 4, 0x10062F7C: 76, 0x840B90: 4, 0x100261D0: 10,
        0x89F1AC: 8, 0x8A9B68: 4, 0x39A4D8: 0x50,
        0x24FED8: 16, 0x251458: 16, 0x251938: 16, 0x252A48: 16}
    for entry in (0x2D0880, 0x2D18B0, 0x2D18C8, 0x2D1928, 0x2D1960, 0x2D1A08,
                  0x2D1A88, 0x651418, 0x651438, 0x51E260, 0x5A7238, 0x81F638):
        guards[entry] = elf.functions[elf.functions.index(entry) + 1] - entry
    for row in catalog:
        pointer = elf.u32(0x10062F7C + row["level_id"] * 4)
        guards[pointer] = len(row["folder"]) + 1
    report = {"confidence": "code-backed",
        "warning": "Exact USA v02.00 loaded asset provenance, not game-tested edits or a claim that the actual save preserves original runtime asset names. Slot0 and unused slots remain unnamed; no names are guessed from log order.",
        "loader": {"entry_va": "0x2d1a88", "loaded_metadata_registration_va": "0x39a4ec",
            "metadata_section_class": "0x25000", "name_table_section_class": "0x250c0",
            "string_pool_section_class": "0x79c0", "metadata_names_member": "0x24",
            "metadata_count_member": "0x28", "prefix": "gameplay_",
            "filter": "2D1960 uses5A7238 case-folded prefix comparison overstrlen(gameplay_).",
            "assignment": "2D1A88 scans loaded name-array order; passing names receive sequential slots starting1. Reverse slot0 isFFFFFFFF. No native nine-name guard was established; bounded asset decoder rejects overflow instead of emulating memory corruption.",
            "hash": "2D18C8 uses signed inputbytes, wrapping uint32 accumulator5381*33, modulo49; empty40. 2D1A88 writes one slot perbucket, later entries overwrite earlier collisions;2D1928 does no name equality check.",
            "native_level_folder_getter_va": "0x2d0880", "native_level_folder_table_va": "0x10062f7c"},
        "level_folders": catalog,
        "instruction_guards": [{"va": hex(a), "bytes": elf.read(a, size).hex().upper()} for a, size in sorted(guards.items())]}
    if save_path is not None:
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or [struct.unpack_from(">I", raw, i * 0x14)[0] for i in range(32)] != list(range(32)):
            raise ValueError("Unexpected plaintext save size/header")
        report["save_observation"] = {"sha256": hashlib.sha256(raw).hexdigest().upper(),
            "warning": "Physical records alone do not contain the loaded name-array catalog.",
            "named_world_records": [{"level_id": row["level_id"], "world_offset": hex(0x488 + row["level_id"] * 0x408),
                "segment_count": 10, "nonzero_segment_records": [slot for slot in range(10)
                    if any(raw[0x488 + row["level_id"] * 0x408 + slot * 0x30:0x488 + row["level_id"] * 0x408 + (slot + 1) * 0x30])]} for row in catalog]}
    if archive_path is not None:
        archive_path = Path(archive_path)
        psarc = BINDINGS.module("tod_segment_psarc", BINDINGS.ROOT / "Tools/Inspect-Psarc.py")
        # No filename from archive contents is used as an output path. Native
        # folder names are validated before resolving these read-only inputs.
        root = archive_path.parent.parent / "levels"
        assets = []
        for row in catalog:
            folder = row["folder"]
            if not folder or any(c in folder for c in "/\\:\0") or folder in (".", ".."):
                raise ValueError("Unsafe native asset folder")
            path = root / folder / "level_cached.psarc"
            archive = psarc.Psarc(path)
            name = f"/built/levels/{folder}/gameplay.dat"
            indexes = [i for i, value in enumerate(archive.names) if value == name]
            if len(indexes) != 1:
                raise ValueError("Missing/duplicate gameplay asset")
            item = gameplay_catalog(archive.read_entry(indexes[0], 32 * 1024 * 1024))
            item.update(row, asset_path=name, archive=f"packed/levels/{folder}/level_cached.psarc", entry_index=indexes[0])
            for segment in item["segments"]:
                segment["save_offset"] = hex(0x488 + row["level_id"] * 0x408 + segment["slot"] * 0x30)
            assets.append(item)
        report["asset_observation"] = {"warning": "Exact shipped ordered gameplay.dat catalogs from sibling level archives; conditional names for this native build/these asset hashes, not stored save labels or localization.", "levels": assets,
            "named_segment_count": sum(len(a["segments"]) for a in assets)}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path, help="Original global_cached.psarc; sibling packed/levels archives are read-only inputs")
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save, args.archive), indent=2))
