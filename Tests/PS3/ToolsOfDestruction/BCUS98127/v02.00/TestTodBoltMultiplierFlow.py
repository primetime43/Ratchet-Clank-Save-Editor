"""Exact multiplier flow, bounded float32 previews and read-only snapshot checks."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodBoltMultiplierFlow.py"))
ELF = SAVE = None


class BoltMultiplierChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_disabled_getter_preserves_every_value(self):
        result = TOOL["getter_preview"](0, 25, 10, 1, -4)
        self.assertEqual((result["saved_multiplier"], result["cached_health"], result["accumulator"], result["reset"]), (25, 10, -4, False))

    def test_disabled_update_does_not_call_getter(self):
        result = TOOL["update_preview"](0, -10, 10, 1, -4)
        self.assertEqual((result["saved_multiplier"], result["cached_health"], result["accumulator"]), (-10, 10, -4))
        self.assertFalse(result["getter_called"])
        self.assertFalse(result["advanced_once"])

    def test_any_nonzero_raw_replay_enables_health_reset(self):
        for replay in (1, 3, 0x80000000, 0xFFFFFFFF):
            result = TOOL["getter_preview"](replay, 15, 10, 9, 8)
            self.assertEqual((result["saved_multiplier"], result["accumulator"], result["cached_health"]), (1, 1, 9))
            self.assertTrue(result["reset"])

    def test_equality_and_healing_refresh_cache_without_clamp(self):
        for current, multiplier in ((10, -8), (11, 25)):
            result = TOOL["getter_preview"](1, multiplier, 10, current, 4)
            self.assertEqual((result["cached_health"], result["saved_multiplier"], result["accumulator"]), (current, multiplier, 4))
            self.assertFalse(result["reset"])

    def test_half_step_is_stored_without_multiplier_increment(self):
        result = TOOL["update_preview"](3, 4, 10, 10, 1)
        self.assertEqual((result["saved_multiplier"], result["accumulator"]), (4, 0.5))
        self.assertFalse(result["advanced_once"])

    def test_float32_rounding_at_threshold(self):
        # Float32 0.51 minus 0.5 is below float32 0.01, despite decimal equality.
        below = TOOL["update_preview"](1, 4, 10, 10, 0.51)
        bits = struct.unpack(">I", struct.pack(">f", 0.51))[0]
        next_above = struct.unpack(">f", struct.pack(">I", bits + 1))[0]
        above = TOOL["update_preview"](1, 4, 10, 10, next_above)
        self.assertTrue(below["advanced_once"])
        self.assertEqual(below["saved_multiplier"], 5)
        self.assertFalse(above["advanced_once"])
        self.assertGreaterEqual(above["accumulator"], TOOL["EPSILON"])

    def test_single_step_even_for_large_negative_accumulator(self):
        result = TOOL["update_preview"](1, 4, 10, 10, -10000)
        self.assertEqual((result["saved_multiplier"], result["accumulator"]), (5, 5))
        self.assertTrue(result["advanced_once"])

    def test_finite_selection_caps_and_reseeds_at_twenty(self):
        for multiplier in (20, 25):
            result = TOOL["update_preview"](1, multiplier, 10, 10, 0.5)
            self.assertEqual((result["saved_multiplier"], result["accumulator"]), (20, 20))
        low = TOOL["update_preview"](1, -10, 10, 10, 0)
        self.assertEqual((low["saved_multiplier"], low["accumulator"]), (1, 1))

    def test_health_reset_happens_before_subtraction(self):
        result = TOOL["update_preview"](1, 15, 10, 9, -100)
        self.assertTrue(result["reset"])
        self.assertFalse(result["advanced_once"])
        self.assertEqual((result["saved_multiplier"], result["accumulator"]), (1, 0.5))

    def test_outer_gate_and_getter_gate_are_independent_samples(self):
        result = TOOL["update_preview"](1, 4, 10, 9, 0.5, getter_replay=0)
        self.assertFalse(result["reset"])
        self.assertEqual((result["saved_multiplier"], result["cached_health"], result["accumulator"]), (5, 10, 5))
        blocked = TOOL["update_preview"](0, 4, 10, 9, 0.5, getter_replay=1)
        self.assertFalse(blocked["getter_called"])

    def test_preview_rejects_nonfinite_boolean_huge_and_bad_words(self):
        for value in (float("nan"), float("inf"), float("-inf"), True, "1", 1e21, 10 ** 1000):
            for index in range(4):
                values = [4, 10, 10, 1]
                values[index] = value
                with self.assertRaises(ValueError):
                    TOOL["update_preview"](1, *values)
        for replay in (-1, 0x100000000, True, "1"):
            with self.assertRaises(ValueError):
                TOOL["update_preview"](replay, 4, 10, 10, 1)
            with self.assertRaises(ValueError):
                TOOL["update_preview"](1, 4, 10, 10, 1, getter_replay=replay)

    def test_exact_guard_replay_and_literals(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        self.assertEqual(len(report["instruction_guards"]), 90)
        self.assertEqual(report["update"]["threshold"], {"raw_hex": "3C23D70A", "value": TOOL["EPSILON"]})
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)

    def test_changed_instruction_call_or_constant_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0x1E259C, 0x1E264C, 0x895520, 0x1E5E08, 0x1E5E0C, 0x23E35C, 0x13B3C):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (4 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_toc_mismatch_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for function in (0x2D1860, 0x1E2568, 0x1E25F0):
            with patch.dict(elf.descriptors, {function: 0}):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_event_addition_order_and_runtime_not_saved_qualification(self):
        report = self.native()
        self.assertIn("reread", report["event_pairing"]["rule"])
        self.assertIn("unordered", report["event_pairing"]["rule"])
        self.assertIn("XP/level/callback effects happen before", report["event_pairing"]["xp_addition"])
        self.assertIn("not stored at save offsets", report["restore_seed"])
        self.assertIn("not a direct damage-event", report["getter"]["rule"])

    def test_actual_save_values_without_runtime_guesses_and_unchanged_hashes(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)]
        sample = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual((sample["multiplier_hex"], sample["multiplier"], sample["replay_word"], sample["hero_xp"]), ("3F800000", 1, 3, 2315144))
        self.assertIsNone(sample["cached_health"])
        self.assertIsNone(sample["accumulator"])
        self.assertEqual(before, [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)])

    def test_synthetic_raw_nonfinite_preserved_and_bad_layout_refused(self):
        self.native()
        raw = bytearray(0x906F0)
        for identifier in range(32):
            struct.pack_into(">I", raw, identifier * 20, identifier)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            for bits in (0x7FC12345, 0xFF800000, 0xC1200000, 0x41C80000):
                struct.pack_into(">I", raw, 0x428, bits)
                path.write_bytes(raw)
                sample = TOOL["inspect"](ELF, path)["save_observation"]
                self.assertEqual(sample["multiplier_hex"], f"{bits:08X}")
                self.assertEqual(sample["nonfinite"], bits in (0x7FC12345, 0xFF800000))
                json.dumps(sample, allow_nan=False)
                self.assertEqual(path.read_bytes(), raw)
            for bad in (bytes(0x906F0), raw[:-1]):
                path.write_bytes(bad)
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)

    def test_embedded_map_reproduction_without_private_snapshot(self):
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(self.native(), mapping["bolt_multiplier_flow"])
        self.assertNotIn("save_observation", mapping["bolt_multiplier_flow"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
