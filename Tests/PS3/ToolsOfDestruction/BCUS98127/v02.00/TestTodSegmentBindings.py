"""Independent numeric mission lookup exports, bounded save reads and Lua literals."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("segment_bindings", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSegmentBindings.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF = SAVE = ARCHIVE = None


class SegmentBindingChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build checks")

    def test_dual_catalog_and_reference_keys(self):
        elf = TOOL.MISSIONS.PROGRESSION.BINDINGS.Elf(ELF)
        first = TOOL.exports(elf, 0x294E90, 0x252EB8)
        second = TOOL.exports(elf, 0x80848, 0x12990)
        self.assertEqual(len(first), 162)
        self.assertEqual({n: v["id"] for n, v in first.items()}, {n: v["id"] for n, v in second.items()})
        report = TOOL.inspect(ELF)
        self.assertEqual(len(report["native_mission_lookup_pairs"]), 81)
        self.assertEqual(report["native_mission_lookup_pairs"][0]["title_lookup_id"], 562)
        self.assertEqual(report["native_mission_lookup_pairs"][0]["description_lookup_id"], 641)
        self.assertIn("not a slot catalog", report["segment_slot_limit"])
        for guard in report["instruction_guards"]:
            self.assertEqual(elf.read(int(guard["va"], 0), len(guard["bytes"]) // 2).hex().upper(), guard["bytes"])

    def test_reproduces_embedded_catalog(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text())
        self.assertEqual(TOOL.inspect(ELF), mapping["segment_bindings"])

    def test_bounded_lookup_preserves_unknowns_and_pair_mismatch(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 0x14, i)
        struct.pack_into(">I", data, 0x101C0, 0xFFFFFFFF)
        struct.pack_into(">3I", data, 0x10148, 562, 641, 0x80000003)
        struct.pack_into(">3I", data, 0x10154, 562, 0xFFFFFFFF, 0)
        struct.pack_into(">3I", data, 0x10160, 0xFFFFFFFF, 641, 0)
        with tempfile.TemporaryDirectory(prefix="tod-binding-test-") as temporary:
            path = Path(temporary) / "GAME.SAV"
            path.write_bytes(data)
            level = TOOL.inspect(ELF, path)["save_observation"]["levels"][0]["active"]
            self.assertTrue(level["exceeds_capacity"])
            self.assertEqual(len(level["entries"]), 10)
            first, mismatch, unknown = level["entries"][:3]
            self.assertEqual(first["title_enum"], "L01_LABEL_MISSION_DEFENSECENTER")
            self.assertTrue(first["export_pair_matches"])
            self.assertEqual(first["unknown_flags"], "0x80000000")
            self.assertIsNone(mismatch["description_enum"])
            self.assertFalse(mismatch["export_pair_matches"])
            self.assertIsNone(unknown["title_enum"])
            self.assertFalse(unknown["export_pair_matches"])
            self.assertEqual(path.read_bytes(), data)

    def test_refuses_wrong_inputs(self):
        with tempfile.TemporaryDirectory(prefix="tod-binding-test-") as temporary:
            path = Path(temporary) / "BAD.SAV"
            for data in (b"bad", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_lists_remain_empty_and_inputs_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual snapshot")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observation = TOOL.inspect(ELF, SAVE)["save_observation"]
        self.assertEqual(len(observation["levels"]), 19)
        for level in observation["levels"]:
            for kind in ("active", "completed"):
                self.assertEqual(level[kind]["saved_count"], 0)
                self.assertEqual(level[kind]["entries"], [])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])

    def test_compiled_literal_calls_optional_asset(self):
        if ARCHIVE is None:
            self.skipTest("Pass --archive for original shipped scripts")
        assets = TOOL.inspect(ELF, archive_path=ARCHIVE)["asset_observation"]["assets"]
        self.assertEqual(len(assets), 11)
        self.assertEqual(sum(len(a["literal_calls"]) for a in assets), 32)
        metropolis = next(a for a in assets if "/metropolis/" in a["path"])
        self.assertEqual(metropolis["sha256"], "7AA1EDAABCE682FACB1D9DFD0159D094EC25F927F5BEAACED0F5952A5513B92A")
        call = metropolis["literal_calls"][0]
        self.assertEqual((call["level_id"], call["title_lookup_id"], call["description_lookup_id"]), (0, 562, 641))
        self.assertFalse(call["optional"])
        self.assertTrue(call["export_pair_matches"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE, ARCHIVE = options.elf, options.save, options.archive
    unittest.main(argv=[__file__] + remaining)
