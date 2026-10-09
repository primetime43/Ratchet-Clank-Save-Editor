"""Grid namespace separation, inverse switches, predicate boundaries and immutable inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGridRouting.py"))
ELF, SAVE = None, None
BROWSE = [15, 7, 19, 9, 11, 5, 6, 16, 17, 2, 3, 4, 12, 13, 20, 0, 1, 18, 8, 14, 10]


class GridRoutingChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ELF is None:
            raise unittest.SkipTest("Pass --elf for exact-build validation")
        cls.report = TOOL["inspect"](ELF)

    def fixture(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 20, i)
        return data

    def test_reproduces_bundled_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(self.report, mapping["grid_routing"])
        self.assertIn("different namespaces", self.report["warning"])
        self.assertIn("no confirmed gameplay caller", self.report["warning"])

    def test_inverse_browse_permutations_and_unsigned_defaults(self):
        self.assertEqual(self.report["browse_to_slot"]["values"], BROWSE)
        for ordinal, slot in enumerate(BROWSE):
            self.assertEqual(self.report["slot_to_browse"]["values"][slot], ordinal)
        self.assertEqual(self.report["slot_to_browse"]["out_of_range_result"], 21)
        self.assertEqual(self.report["browse_to_slot"]["out_of_range_result"], 0xFFFFFFFF)

    def test_shared_images_do_not_merge_distinct_saved_slots(self):
        values = self.report["slot_to_image"]["values"]
        self.assertEqual(values, [32,32,29,29,29,26,26,22,34,24,36,25,30,30,35,21,27,28,33,23,31])
        self.assertEqual(len(set(values)), 16)
        self.assertEqual(self.report["slot_to_image"]["out_of_range_result"], 21)
        self.assertIn("Shared image indices do not merge", self.report["menu_provenance"]["image_semantics"])

    def test_threshold_equality_unsigned_extremes_and_no_ready_gate(self):
        data = self.fixture()
        threshold = self.report["accumulator_predicate"]["threshold"]
        self.assertEqual(threshold, 0x36666)
        self.assertEqual(self.report["accumulator_predicate"]["count_must_exceed"], 15)
        self.assertFalse(self.report["accumulator_predicate"]["ready_gate"])
        for slot in range(15):
            struct.pack_into(">I", data, 0x114D8 + slot * 0x60DC + 0xC8, threshold)
        struct.pack_into(">I", data, 0x114D8 + 15 * 0x60DC + 0xC8, threshold - 1)
        self.assertFalse(TOOL["observe"](data, self.report)["predicate_result"])
        struct.pack_into(">I", data, 0x114D8 + 15 * 0x60DC + 0xC8, threshold)
        result = TOOL["observe"](data, self.report)
        self.assertEqual(result["qualifying_count"], 16)
        self.assertTrue(result["predicate_result"])
        self.assertEqual(result["ready_slots_in_browse_order"], [])
        for value in (0x80000000, 0xFFFFFFFF):
            struct.pack_into(">I", data, 0x114D8 + 20 * 0x60DC + 0xC8, value)
            self.assertIn(20, TOOL["observe"](data, self.report)["qualifying_slots"])

    def test_raw_readiness_and_stride_sentinel_do_not_overread(self):
        data = self.fixture()
        data[0x114D8 + 20 * 0x60DC + 0xCC] = 0xAB
        data[0x114D8 + 15 * 0x60DC + 0xCC] = 7
        before = bytes(data)
        result = TOOL["observe"](data, self.report)
        self.assertEqual(result["ready_slots_in_browse_order"], [15, 20])
        self.assertEqual(result["slots"][20]["ready_byte"], 0xAB)
        p = self.report["accumulator_predicate"]
        first = int(p["first_save_offset"], 0)
        self.assertGreater(first + 21 * 0x60DC, len(data))
        self.assertLessEqual(first + 20 * 0x60DC + 4, len(data))
        self.assertEqual(bytes(data), before)

    def test_invalid_inputs_rejected_without_repair(self):
        for data in (b"bad", bytes(0x906F0)):
            with self.assertRaisesRegex(ValueError, "plaintext"):
                TOOL["observe"](data, self.report)
        with tempfile.TemporaryDirectory(prefix="tod-routing-invalid-") as folder:
            path = Path(folder) / "input.bin"
            path.write_bytes(b"bad")
            with self.assertRaisesRegex(ValueError, "plaintext"):
                TOOL["inspect"](ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL["inspect"](path)

    def test_actual_snapshot_predicate_and_browse_order_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for the actual snapshot")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        result = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(result["qualifying_count"], 19)
        self.assertTrue(result["predicate_result"])
        self.assertEqual(result["qualifying_slots"], [i for i in range(21) if i not in (3, 4)])
        self.assertEqual(result["ready_slots_in_browse_order"], [i for i in BROWSE if i not in (3, 4)])
        self.assertIn("No trophy/completion caller", result["warning"])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
