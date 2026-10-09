"""Exact-build mission-list checks, including hostile counts and unknown flags."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("missions", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodMissions.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


class MissionChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_bundled_map_and_boundaries(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text())
        report = TOOL.inspect(ELF)
        self.assertEqual(report, mapping["mission_lists"])
        self.assertEqual(report["active_base"], "0x10148")
        self.assertEqual(report["completed_base"], "0x10af8")
        self.assertEqual(report["capacity_per_list"], 10)
        self.assertEqual(report["entry_stride"], "0xc")
        self.assertEqual(report["list_stride"], "0x7c")
        self.assertEqual(len(report["catalog"]), 19)

    def test_hostile_counts_bound_reads_without_normalizing_flags(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 0x14, i)
        struct.pack_into(">I", data, 0x101C0, 0xFFFFFFFF)
        struct.pack_into(">3I", data, 0x10148, 1234, 5678, 0x80000003)
        struct.pack_into(">I", data, 0x10B70, 1)
        struct.pack_into(">3I", data, 0x10AF8, 98, 99, 0x80000000)
        with tempfile.TemporaryDirectory(prefix="tod-mission-test-") as temporary:
            path = Path(temporary) / "GAME.SAV"
            path.write_bytes(data)
            level = TOOL.inspect(ELF, path)["save_observation"]["levels"][0]
            active, completed = level["active"], level["completed"]
            self.assertEqual(active["saved_count"], 0xFFFFFFFF)
            self.assertTrue(active["exceeds_capacity"])
            self.assertEqual(len(active["entries"]), 10)
            entry = active["entries"][0]
            self.assertEqual(entry["title_lookup_id"], 1234)
            self.assertEqual(entry["description_lookup_id"], 5678)
            self.assertTrue(entry["optional"] and entry["complete"])
            self.assertFalse(entry["available"])
            self.assertEqual(entry["unknown_flags"], "0x80000000")
            self.assertTrue(completed["entries"][0]["available"])
            self.assertFalse(completed["entries"][0]["complete"])
            self.assertEqual(path.read_bytes(), data)

    def test_refuses_wrong_size_nonplaintext_and_wrong_elf(self):
        with tempfile.TemporaryDirectory(prefix="tod-mission-test-") as temporary:
            path = Path(temporary) / "GAME.SAV"
            for data in (b"not a save", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_inputs_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual plaintext observations")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observation = TOOL.inspect(ELF, SAVE)["save_observation"]
        data = SAVE.read_bytes()
        for i, level in enumerate(observation["levels"]):
            for group, base in (("active", 0x10148), ("completed", 0x10AF8)):
                count = struct.unpack_from(">I", data, base + i * 0x7C + 0x78)[0]
                self.assertEqual(level[group]["saved_count"], count)
                self.assertEqual(len(level[group]["entries"]), min(count, 10))
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
