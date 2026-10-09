"""Exact-build category selection, physical boundaries, unsigned counters and immutable reads."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("categories", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodResetCategories.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


class ResetCategoryChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_map_and_physical_type(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        report = TOOL.inspect(ELF)
        self.assertEqual(report, mapping["reset_categories"])
        self.assertEqual(report["storage"]["offset"], "0x5734")
        self.assertEqual(report["storage"]["end_exclusive"], mapping["serialization"]["inventory"]["unlock_bytes_offset"])
        self.assertEqual(report["storage"]["count"], 8)
        t = next(t for t in mapping["structures"] if t["name"] == "TOD_SaveResetCategoryCounters_verified")
        self.assertEqual(int(t["size"], 0), 8 * 4)
        self.assertEqual(t["fields"][0]["type"], "u32")
        self.assertEqual(t["fields"][0]["count"], 8)

    def test_selection_and_runtime_are_not_saved_or_named_failure_counts(self):
        report = TOOL.inspect(ELF)
        self.assertEqual([e["id"] for e in report["catalog"] if e["selection_sources"]], list(range(2, 8)))
        self.assertEqual(report["catalog"][0]["evidence"], "Increment skipped for ID0")
        self.assertEqual(report["catalog"][1]["selection_sources"], [])
        self.assertEqual(report["catalog"][3]["selection_sources"][0]["call_va"], report["catalog"][7]["selection_sources"][0]["call_va"])
        self.assertLess(int(report["runtime"]["state_va"], 0), 0x101EFB20)
        self.assertEqual(report["runtime"]["initial_countdown"], 0.25)
        self.assertIn("Equality reaches zero without clearing", report["runtime"]["clear_rule"])
        self.assertIn("before2D1860", report["storage"]["gate"])
        self.assertIn("not arena", report["warning"])

    def test_unsigned_extremes_and_adjacent_unlock_are_not_normalized(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 0x14, i)
        values = [0xFFFFFFFF, 0x80000000, 2, 3, 4, 5, 6, 0x7FFFFFFF]
        for i, value in enumerate(values):
            struct.pack_into(">I", data, 0x5734 + 4 * i, value)
        data[0x5754] = 0xAB
        with tempfile.TemporaryDirectory(prefix="tod-category-test-") as folder:
            path = Path(folder) / "GAME.bin"
            path.write_bytes(data)
            report = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual([e["value"] for e in report["counters"]], values)
            self.assertEqual(report["counters"][-1]["offset"], "0x5750")
            self.assertEqual(report["counters"][0]["raw_bits"], "FFFFFFFF")
            self.assertEqual(path.read_bytes(), data)

    def test_rejects_bad_inputs(self):
        with tempfile.TemporaryDirectory(prefix="tod-category-invalid-") as folder:
            path = Path(folder) / "input.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_snapshot_zero_counters_restart_three_and_unchanged_inputs(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual snapshot validation")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        report = TOOL.inspect(ELF, SAVE)["save_observation"]
        self.assertEqual([e["value"] for e in report["counters"]], [0] * 8)
        self.assertEqual(report["saved_restart_counter"], 3)
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
