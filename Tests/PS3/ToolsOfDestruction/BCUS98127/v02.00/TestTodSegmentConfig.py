"""Native ordered gameplay names; hash collision, bounds and source preservation."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("segment_config", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSegmentConfig.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF = SAVE = ARCHIVE = None


def fixture(names):
    header_end = 80
    table = 128
    pool = table + 4 * len(names)
    encoded = [name.encode("ascii") + b"\0" for name in names]
    metadata = pool + sum(map(len, encoded))
    total = metadata + 44
    relocations = [table + i * 4 for i in range(len(names))] + [metadata + 0x24]
    raw = bytearray(total + len(relocations) * 4)
    struct.pack_into(">8I", raw, 0, 0x49474857, 0x10001, 3, header_end, total, len(relocations), 0xDEADDEAD, 0xDEADDEAD)
    for i, row in enumerate(((0x250C0, table, 0x10000000 + len(names), 4), (0x79C0, pool, 1, metadata - pool), (0x25000, metadata, 1, 44))):
        struct.pack_into(">4I", raw, 32 + 16 * i, *row)
    pointer = pool
    for i, value in enumerate(encoded):
        struct.pack_into(">I", raw, table + i * 4, pointer)
        raw[pointer:pointer + len(value)] = value
        pointer += len(value)
    struct.pack_into(">2I", raw, metadata + 0x24, table, len(names))
    struct.pack_into(f">{len(relocations)}I", raw, total, *relocations)
    return raw


class SegmentConfigChecks(unittest.TestCase):
    def test_hash_signed_bytes_empty_and_wrap(self):
        self.assertEqual(TOOL.segment_hash(b""), 40)
        self.assertEqual(TOOL.segment_hash(b"gameplay_enemy"), 13)
        value = 5381
        for byte in b"\xff" * 100:
            value = (value * 33 - 1) & 0xFFFFFFFF
        self.assertEqual(TOOL.segment_hash(b"\xff" * 100), value % 49)
        with self.assertRaises(ValueError):
            TOOL.segment_hash(b"bad\0name")

    def test_order_prefix_and_collision_last_wins(self):
        names = ["ambient", "gameplay_b", "other", "GAMEPLAY_C", "gameplay_a"]
        rows = TOOL.gameplay_catalog(fixture(names))["segments"]
        self.assertEqual([(r["slot"], r["loaded_name_index"], r["name"]) for r in rows], [(1, 1, names[1]), (2, 3, names[3]), (3, 4, names[4])])
        # Build a deliberate collision independently, not guessing shipped data.
        seen = {}
        for i in range(200):
            name = f"gameplay_{i}"
            bucket = TOOL.segment_hash(name)
            if bucket in seen:
                pair = [seen[bucket], name]
                break
            seen[bucket] = name
        rows = TOOL.gameplay_catalog(fixture(pair))["segments"]
        self.assertEqual(rows[0]["resolved_lookup_slot"], 2)
        self.assertTrue(rows[0]["hash_collision_shadowed"])
        self.assertFalse(rows[1]["hash_collision_shadowed"])

    def test_rejects_bad_descriptors_names_relocations_and_overflow(self):
        raw = fixture(["gameplay_one"])
        mutations = []
        for offset, value in ((8, 0xFFFFFFFF), (12, 81), (16, len(raw)), (36, 0), (128, 0), (len(raw) - 4, 0)):
            copy = bytearray(raw)
            struct.pack_into(">I", copy, offset, value)
            mutations.append(copy)
        mutations += [raw[:-1], b"bad", fixture([f"gameplay_{i}" for i in range(10)])]
        for value in mutations:
            with self.assertRaises(ValueError):
                TOOL.gameplay_catalog(value)

    def test_exact_native_guards_and_indexed_level_folders(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        result = TOOL.inspect(ELF)
        self.assertEqual(len(result["level_folders"]), 19)
        self.assertEqual(result["level_folders"][17], {"level_id": 17, "level_enum": "LEVEL_MERIDIAN_CITY", "folder": "meridian city"})
        self.assertEqual(result["level_folders"][18]["folder"], "fastoon_return")
        elf = TOOL.BINDINGS.MISSIONS.PROGRESSION.BINDINGS.Elf(ELF)
        for guard in result["instruction_guards"]:
            self.assertEqual(elf.read(int(guard["va"], 0), len(guard["bytes"]) // 2).hex().upper(), guard["bytes"])

    def test_reproduces_embedded_native_and_optional_asset_catalogs(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text())
        self.assertEqual(TOOL.inspect(ELF), mapping["segment_configuration"])
        if ARCHIVE is not None:
            self.assertEqual(TOOL.inspect(ELF, archive_path=ARCHIVE)["asset_observation"], mapping["segment_configuration_assets"])

    def test_actual_snapshot_record_bounds_and_unchanged_inputs(self):
        if ELF is None or SAVE is None:
            self.skipTest("Pass --elf --save")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observation = TOOL.inspect(ELF, SAVE)["save_observation"]
        self.assertEqual(len(observation["named_world_records"]), 19)
        self.assertTrue(all(not r["nonzero_segment_records"] for r in observation["named_world_records"]))
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])
        with tempfile.TemporaryDirectory(prefix="tod-segment-config-") as temporary:
            path = Path(temporary) / "bad.bin"
            for raw in (b"bad", bytes(0x906F0)):
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    TOOL.inspect(ELF, path)

    def test_all_shipped_level_names_and_meridian_catalog(self):
        if ELF is None or ARCHIVE is None:
            self.skipTest("Pass --elf --archive")
        report = TOOL.inspect(ELF, archive_path=ARCHIVE)["asset_observation"]
        self.assertEqual(len(report["levels"]), 19)
        self.assertEqual(report["named_segment_count"], 56)
        self.assertFalse(any(s["hash_collision_shadowed"] for a in report["levels"] for s in a["segments"]))
        city = report["levels"][17]
        self.assertEqual(city["metadata_offset"], "0x134680")
        self.assertEqual(city["name_table_offset"], "0x2100")
        self.assertEqual([s["name"] for s in city["segments"]], ["gameplay_enemy", "gameplay_magcycle", "gameplay_robowings"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE, ARCHIVE = options.elf, options.save, options.archive
    unittest.main(argv=[__file__] + remaining)
