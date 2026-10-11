"""Hero XP exact-build guards and bounded synthetic arithmetic, without writes."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodHeroXpFlow.py"))
ELF = SAVE = None


class HeroXpFlowChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_exactly_one_does_not_carry(self):
        result = TOOL["publication_preview"](100.75, 0.25)
        self.assertEqual((result["saved_xp"], result["remainder"]), (100, 1.0))
        self.assertFalse(result["carried_once"])

    def test_above_one_carries_once(self):
        result = TOOL["publication_preview"](100.75, 0.5)
        self.assertEqual((result["saved_xp"], result["remainder"]), (101, 0.25))
        self.assertTrue(result["carried_once"])

    def test_large_remainder_has_no_loop(self):
        result = TOOL["publication_preview"](100.0, 3.5)
        self.assertEqual((result["saved_xp"], result["remainder"]), (101, 2.5))
        self.assertEqual(TOOL["publication_preview"](0xFFFFFFFF, 1.5)["saved_xp"], 0)

    def test_pending_one_and_integer_input_remains_pending(self):
        result = TOOL["publication_preview"](100.0, 1.0)
        self.assertEqual(result["remainder"], 1.0)
        self.assertFalse(result["carried_once"])

    def test_leaf_input_is_not_always_single_precision(self):
        result = TOOL["publication_preview"](100.0000001)
        self.assertGreater(result["residual"], 0)
        self.assertEqual(result["threshold_input"], 100.0000001)

    def test_negative_residual_is_not_added(self):
        result = TOOL["publication_preview"](16777219, 0.5)
        self.assertEqual(result["residual"], -1.0)
        self.assertEqual((result["saved_xp"], result["remainder"]), (16777219, 0.5))

    def test_original_input_not_carried_saved_xp_selects_level(self):
        result = TOOL["publication_preview"](100.75, 0.5)
        thresholds = [0, 101] + [0] * 98
        self.assertEqual(TOOL["advancement_preview"](result["threshold_input"], 0, thresholds)["level_before_callbacks"], 0)
        self.assertEqual(TOOL["advancement_preview"](result["saved_xp"], 0, thresholds)["level_before_callbacks"], 1)

    def test_lower_xp_does_not_lower_runtime_level(self):
        thresholds = [0] + list(range(100, 10000, 100))
        self.assertEqual(TOOL["advancement_preview"](0, 10, thresholds)["level_before_callbacks"], 10)

    def test_thresholds_need_positive_not_increasing_values(self):
        thresholds = [0, 100, 50, 100] + [0] * 96
        self.assertEqual(TOOL["advancement_preview"](100, 0, thresholds)["level_before_callbacks"], 3)

    def test_zero_threshold_stops_progression(self):
        thresholds = [0, 100, 0, 50] + [0] * 96
        self.assertEqual(TOOL["advancement_preview"](1000, 0, thresholds)["level_before_callbacks"], 1)

    def test_ceiling_and_out_of_range_runtime_byte_do_not_wrap(self):
        thresholds = [0] + [1] * 99
        self.assertEqual(TOOL["advancement_preview"](10, 0, thresholds)["level_before_callbacks"], 99)
        for level in range(99, 256):
            self.assertEqual(TOOL["advancement_preview"](10, level, thresholds)["level_before_callbacks"], level)

    def test_restore_precision_boundary_and_exact_large_integer(self):
        for value, restored in ((16777216, 16777216), (16777217, 16777216),
                                (16777218, 16777218), (16777219, 16777220)):
            result = TOOL["restore_preview"](value)
            self.assertEqual(result["saved_xp"], restored)
            self.assertEqual(result["integer_exactly_representable"], value == restored)

    def test_unsigned_max_restore_has_low32_wrap_and_single_carry(self):
        result = TOOL["restore_preview"](0xFFFFFFFF)
        self.assertEqual(result["float32_input"], 0x100000000)
        self.assertEqual(result["saved_xp"], 1)
        self.assertTrue(result["carried_once"])
        self.assertIn("nearest-even", result["assumption"])

    def test_script_discards_fractions_but_does_not_reset_pending_remainder(self):
        result = TOOL["script_set_preview"](100.75)
        self.assertEqual((result["saved_xp"], result["residual"]), (100, 0))
        self.assertEqual(TOOL["script_set_preview"](100.75, 1.5)["saved_xp"], 101)

    def test_preview_domain_rejects_nonfinite_invalid_types_and_tables(self):
        for value in (True, -1, float("nan"), float("inf"), "1", 0x100000001, 10 ** 1000):
            with self.assertRaises(ValueError):
                TOOL["publication_preview"](value)
            with self.assertRaises(ValueError):
                TOOL["publication_preview"](1, value)
        for value in (True, -1, 1.5, "1", 0x100000000):
            with self.assertRaises(ValueError):
                TOOL["restore_preview"](value)
        for level, table in ((256, [0] * 100), (True, [0] * 100), (0, [0] * 99), (0, [True] * 100)):
            with self.assertRaises(ValueError):
                TOOL["advancement_preview"](1, level, table)

    def test_exact_guard_replay_and_qualification(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        self.assertEqual(len(report["instruction_guards"]), 100)
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)
        self.assertIn("original incoming f1", report["advancement"]["input"])
        self.assertIn("before rereading", report["advancement"]["health"])
        self.assertIn("FPSCR", report["entry_paths"]["preview_scope"])

    def test_changed_carry_restore_script_instruction_or_literal_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0x23E100, 0x23E150, 0x23E768, 0x28AAB8, 0x897AFC, 0x252C84):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (1 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_actual_save_snapshot_without_runtime_guesses_or_writes(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)]
        report = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual((report["saved_xp"], report["raw_hex"]), (2315144, "00235388"))
        self.assertTrue(report["nearest_even_restore_preview"]["integer_exactly_representable"])
        for name in ("runtime_remainder", "runtime_level", "current_health"):
            self.assertIsNone(report[name])
        self.assertEqual(before, [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)])

    def test_synthetic_unusual_xp_preserved_and_bad_layout_refused(self):
        self.native()
        raw = bytearray(0x906F0)
        for identifier in range(32):
            struct.pack_into(">I", raw, identifier * 20, identifier)
        struct.pack_into(">I", raw, 0x418, 0xFFFFFFFF)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(raw)
            report = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(report["saved_xp"], 0xFFFFFFFF)
            self.assertEqual(report["nearest_even_restore_preview"]["saved_xp"], 1)
            self.assertEqual(path.read_bytes(), raw)
            for bad in (bytes(0x906F0), raw[:-1]):
                path.write_bytes(bad)
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)

    def test_embedded_map_reproduction_without_private_snapshot(self):
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(self.native(), mapping["hero_xp_flow"])
        self.assertNotIn("save_observation", mapping["hero_xp_flow"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
