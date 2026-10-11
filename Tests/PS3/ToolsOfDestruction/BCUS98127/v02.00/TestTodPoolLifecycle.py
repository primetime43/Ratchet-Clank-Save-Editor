"""Exact-build pool lifecycle prerequisites, padding and physical-slot reuse."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodPoolLifecycle.py"))
ELF = SAVE = None


class PoolLifecycleChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_exact_instruction_guards(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        self.assertEqual(len(report["instruction_guards"]), 71)
        for guard in report["instruction_guards"]:
            self.assertEqual(elf.read(int(guard["va"], 0), len(guard["bytes"]) // 2).hex().upper(), guard["bytes"])

    def test_normal_setup_blocks_all_padding_slots(self):
        for capacity in (0, 1, 31, 32, 33, 127, 128, 129, 2048, 65535, 65536):
            words = TOOL["initial_bitmap"](capacity)
            self.assertEqual(len(words), 4 * ((capacity + 127) // 128))
            self.assertEqual(sum(w.bit_count() for w in words), len(words) * 32 - capacity)
            for slot in range(len(words) * 32):
                self.assertEqual(bool(words[slot // 32] & 1 << (slot % 32)), slot >= capacity)

    def test_first_free_allocations_do_not_enter_normal_padding(self):
        for capacity in (1, 33, 127, 128, 129):
            words = TOOL["initial_bitmap"](capacity)
            for slot in range(capacity):
                result = TOOL["DEFINITIONS"]["first_free_preview"](words, capacity)
                self.assertEqual(result["reserved_index"], slot)
                self.assertTrue(result["creation_admitted"])
                words = result["bitmap_words"]
            self.assertIsNone(TOOL["DEFINITIONS"]["first_free_preview"](words, capacity)["reserved_index"])

    def test_raw_uninitialized_padding_is_still_distinct(self):
        result = TOOL["DEFINITIONS"]["first_free_preview"]([0xFFFFFFFF, 1, 0, 0], 33)
        self.assertEqual(result["reserved_index"], 33)
        self.assertFalse(result["creation_admitted"])
        self.assertIn("not evidence", self.native()["padding_refinement"])

    def test_setup_capacity_rounding_and_32bit_wrap_are_not_validation(self):
        self.assertEqual(TOOL["setup_capacity"](18214, 0), 18216)
        self.assertEqual(TOOL["setup_capacity"](33, 3), 40)
        self.assertEqual(TOOL["setup_capacity"](0, 0), 0)
        self.assertEqual(TOOL["setup_capacity"](0xFFFFFFFF, 0), 0)
        self.assertEqual(TOOL["setup_capacity"](0xFFFFFFF8, 0), 0xFFFFFFF8)
        for value in (-1, 0x100000000, True, 1.0, "1"):
            with self.assertRaises(ValueError):
                TOOL["setup_capacity"](value, 0)
            with self.assertRaises(ValueError):
                TOOL["setup_capacity"](0, value)

    def test_release_preview_reuses_physical_slot_without_mutation(self):
        words = [0xFFFFFFFF] * 4
        pending = [31, 0, 31, 127]
        result = TOOL["cleared_bitmap_preview"](words, pending, 128)
        self.assertEqual(result, [0x7FFFFFFE, 0xFFFFFFFF, 0xFFFFFFFF, 0x7FFFFFFF])
        self.assertEqual(words, [0xFFFFFFFF] * 4)
        self.assertEqual(pending, [31, 0, 31, 127])
        allocated = TOOL["DEFINITIONS"]["first_free_preview"](result, 128)
        self.assertEqual(allocated["reserved_index"], 0)
        self.assertEqual(allocated["bitmap_words"][0], 0x7FFFFFFF)

    def test_tooling_bounds_do_not_hide_native_uncertainty(self):
        for capacity in (-1, 65537, True, 1.5):
            with self.assertRaises(ValueError):
                TOOL["initial_bitmap"](capacity)
        for words, pending, capacity in (([], [], 1), ([0] * 3, [], 33),
                                         ([True] * 4, [], 128), ([0x100000000] * 4, [], 128),
                                         ([0] * 4, [-1], 128), ([0] * 4, [True], 128),
                                         ([0] * 4, [128], 128), ([0] * 4, [33], 33),
                                         ([0] * 4, "0", 128), ([], [0], 0)):
            with self.assertRaises(ValueError):
                TOOL["cleared_bitmap_preview"](words, pending, capacity)

    def test_runtime_header_unsigned_pointers_and_raw_bytes_preserved(self):
        values = (0xDEADBEEF, 0x80000000, 33, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFF1234, 0xFFFFFFFE, 0xFEEDC0DE)
        raw = bytearray(struct.pack(">8I", *values))
        before = bytes(raw)
        result = TOOL["runtime_header"](raw)
        self.assertEqual(bytes.fromhex(result["raw_hex"]), before)
        self.assertEqual(result["entry_base_pointer"], "0xDEADBEEF")
        self.assertEqual(result["occupancy_pointer"], "0x80000000")
        self.assertEqual(result["high_water_signed"], -1)
        self.assertEqual(result["generation_counter_raw"], 0xFFFF1234)
        self.assertEqual(result["pending_release_count"], 0xFFFFFFFE)
        self.assertEqual(raw, before)
        for length in (0, 31, 33, 72):
            with self.assertRaises(ValueError):
                TOOL["runtime_header"](bytes(length))

    def test_complete_runtime_header_is_not_saved_layout(self):
        report = self.native()
        fields = report["runtime_header"]["fields"]
        self.assertEqual([int(v["offset"], 0) for v in fields], list(range(0, 32, 4)))
        self.assertEqual(sum(v["size"] for v in fields), 32)
        self.assertIn("not additional GAME.SAV", report["warning"])
        self.assertIn("BE generation halfword", report["queue_drain"])

    def test_callback_order_and_dynamic_queue_limits_explicit(self):
        report = self.native()
        self.assertIn("callback before", report["deferred_release"])
        self.assertIn("BEFORE occupancy clear", report["queue_drain"])
        self.assertIn("reloads pending count", report["queue_drain"])
        self.assertIn("deduplication", report["queue_drain"])
        self.assertIn("does not write generation14 or pending-count18", report["reset_distinction"])
        self.assertIn("No intervening direct call", report["setup_before_loader"])
        self.assertIn("runtime prerequisites are not established", report["identity_limit"])

    def test_native_and_save_inputs_unchanged(self):
        report = self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in (ELF, SAVE)]
        observation = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(observation["sha256"], "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
        self.assertTrue(all(v["recorded_set_count"] == v["suppression_set_count"] == 0 for v in observation["worlds"]))
        self.assertEqual([hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in (ELF, SAVE)], before)
        self.assertNotIn("save_observation", report)

    def test_embedded_report_reproduces(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text())
        self.assertEqual(report, mapping["pool_lifecycle"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
