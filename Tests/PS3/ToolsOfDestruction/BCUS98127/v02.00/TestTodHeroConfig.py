"""Named Hero config arrays, bounded literal parsing and unchanged save checks."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodHeroConfig.py"))
ELF = SAVE = ARCHIVE = None


class HeroConfigChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def assets(self):
        if ARCHIVE is None:
            self.skipTest("Pass --archive")
        return TOOL["asset_report"](ARCHIVE)

    def test_all98_shipped_rows_and_endpoints(self):
        rows = self.assets()["rows"]
        self.assertEqual(len(rows), 98)
        self.assertEqual(rows[0], {"index": 0, "xp": 0, "hp": 10})
        self.assertEqual(rows[-1], {"index": 97, "xp": 989000, "hp": 999})
        self.assertEqual([r["index"] for r in rows], list(range(98)))
        self.assertTrue(all(a["xp"] < b["xp"] for a, b in zip(rows, rows[1:])))

    def test_designer_tags_and_old_notes_not_interpreted_as_properties(self):
        rows = TOOL["parse_hero"](b',50 rows maximum\nHero,XP,HP,,\n,0,10,,Met\n,1000,11,,Cob\n')
        self.assertEqual(rows, [{"index": 0, "xp": 0, "hp": 10}, {"index": 1, "xp": 1000, "hp": 11}])
        self.assertIn("stale", self.assets()["qualification"])

    def test_empty_xp_row_does_not_advance_row_counter(self):
        rows = TOOL["parse_hero"](b'Hero,XP,HP\n,0,10\n,,99\n,1000,11\n')
        self.assertEqual(rows[1]["index"], 1)

    def test_literal_parser_rejects_expressions_nonfinite_and_negative_values(self):
        for xp, hp in (("1+2", "11"), ("1", "execute()"), ("1", "nan"), ("-1", "10"), ("1", "-1"), ("4294967296", "10"), ("1", "4294967296")):
            with self.assertRaises(ValueError):
                TOOL["parse_hero"](f'Hero,XP,HP\n,0,10\n,{xp},{hp}\n'.encode())

    def test_native100_slot_bound_and_csv_size_limits(self):
        raw = b'Hero,XP,HP\n' + b''.join(f',{i},10\n'.encode() for i in range(100))
        self.assertEqual(len(TOOL["parse_hero"](raw)), 100)
        for bad in (raw + b',100,10\n', bytes(65537), b'Hero,XP,HP\n,0,' + b'1' * 4097):
            with self.assertRaises(ValueError):
                TOOL["parse_hero"](bad)

    def test_header_initial_xp_and_duplicate_header_validation(self):
        for bad in (b'', b'Hero,HP,XP\n,0,10\n', b'Hero,XP,HP\n,1,10\n', b'Hero,XP,HP\n,0,10\nHero,XP,HP\n'):
            with self.assertRaises(ValueError):
                TOOL["parse_hero"](bad)

    def test_source_compiled_and_csv_fingerprints_match(self):
        assets = self.assets()
        self.assertEqual({a["name"]: a["sha256"] for a in assets["assets"]}, TOOL["HASHES"])
        self.assertEqual(assets["unpopulated_native_indices"], [98, 99])
        self.assertIn("compiled72", assets["parser_rule"])
        self.assertIn("not captured runtime", assets["qualification"])

    def test_changed_payload_hash_refused(self):
        self.assets()
        archive = TOOL["PSARC"]["Psarc"](ARCHIVE)
        original = archive.read_entry
        index = archive.names.index('/data/configs/hero.lc')
        with patch.object(archive, "read_entry", side_effect=lambda i, n: original(i, n) + (b'x' if i == index else b'')):
            with patch.dict(TOOL["PSARC"], {"Psarc": lambda _: archive}):
                with self.assertRaises(ValueError):
                    TOOL["asset_report"](ARCHIVE)

    def test_duplicate_asset_name_or_bad_name_digest_refused(self):
        self.assets()
        archive = TOOL["PSARC"]["Psarc"](ARCHIVE)
        with patch.dict(TOOL["PSARC"], {"Psarc": lambda _: archive}):
            index = archive.names.index('/data/configs/hero.csv')
            archive.name_hashes_match[index - 1] = False
            with self.assertRaises(ValueError):
                TOOL["asset_report"](ARCHIVE)
            archive.name_hashes_match[index - 1] = True
            archive.names.append('/data/configs/hero.csv')
            with self.assertRaises(ValueError):
                TOOL["asset_report"](ARCHIVE)

    def test_exact_guard_replay(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        self.assertEqual(len(report["instruction_guards"]), 74)
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)

    def test_changed_native_bank_bound_descriptor_or_scope_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0xB7654, 0xB7850, 0x88E8CC, 0x89510, 0x894E0, 0x23DBE4):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (1 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_distinct_array_types_scope_and_unclamped_fraction(self):
        report = self.native()
        self.assertEqual([(r["name"], r["offset"], r["element_type"]) for r in report["arrays"]], [("XP", "0x0", "u32"), ("HP", "0x190", "f32")])
        self.assertIn("Scalar same-name", report["root"]["rule"])
        self.assertIn("modulo32", report["progress_fraction"]["rule"])
        self.assertIn("No0..1 clamp", report["progress_fraction"]["rule"])
        self.assertIn("if that helper returns", report["conversion"])

    def test_actual_save_reference_comparison_without_runtime_guesses(self):
        self.native(); self.assets()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)]
        sample = TOOL["inspect"](ELF, SAVE, ARCHIVE)["save_observation"]
        self.assertEqual((sample["saved_xp"], sample["reference_thresholds_met"]), (2315144, 98))
        self.assertEqual(sample["highest_reference_row_met"], {"index": 97, "xp": 989000, "hp": 999})
        self.assertIsNone(sample["runtime_level"])
        self.assertIsNone(sample["current_health"])
        self.assertEqual(before, [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)])

    def test_synthetic_raw_xp_without_assets_and_bad_layout(self):
        self.native()
        raw = bytearray(0x906F0)
        for identifier in range(32):
            struct.pack_into(">I", raw, identifier * 20, identifier)
        struct.pack_into(">I", raw, 0x418, 0xFFFFFFFF)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(raw)
            sample = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(sample["saved_xp"], 0xFFFFFFFF)
            self.assertIsNone(sample["reference_thresholds_met"])
            self.assertEqual(path.read_bytes(), raw)
            for bad in (bytes(0x906F0), raw[:-1]):
                path.write_bytes(bad)
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)

    def test_embedded_native_and_asset_report_reproduction(self):
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(self.native(), mapping["hero_config"])
        self.assertEqual(self.assets(), mapping["hero_config_assets"])
        self.assertNotIn("save_observation", mapping["hero_config"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE, ARCHIVE = args.elf, args.save, args.archive
    unittest.main(argv=[__file__] + remaining)
