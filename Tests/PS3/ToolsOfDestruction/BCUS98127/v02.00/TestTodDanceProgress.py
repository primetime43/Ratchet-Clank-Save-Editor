"""Dance progress exact equality, native shift rules and independent earned state."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodDanceProgress.py"))
ELF = SAVE = None
MASK = (1 << 28) - 1


class DanceProgressChecks(unittest.TestCase):
    def native(self, save=None):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF, save)

    def test_each_expected_low_bit_publishes(self):
        for index in range(28):
            result = TOOL["progress_preview"](0, index)
            self.assertTrue(result["store_reached"])
            self.assertEqual(result["bank_after_local_store"], 1 << index)
            self.assertFalse(result["skill48_request"])

    def test_missing_bit_completion_and_duplicate_request(self):
        for index in range(28):
            self.assertTrue(TOOL["progress_preview"](MASK ^ (1 << index), index)["skill48_request"])
            self.assertTrue(TOOL["progress_preview"](MASK, index)["skill48_request"])

    def test_all64_equality_extra_high_bits_block(self):
        for index in range(28, 64):
            result = TOOL["progress_preview"](MASK | (1 << index), 0)
            self.assertFalse(result["skill48_request"])
            self.assertEqual(result["bank_after_local_store"], MASK | (1 << index))

    def test_no_popcount_completion(self):
        self.assertFalse(TOOL["progress_preview"](MASK << 1, 1)["skill48_request"])
        self.assertFalse(TOOL["progress_preview"]((1 << 64) - 1, 1)["skill48_request"])

    def test_sld_counts64_through127_store_unchanged_but_test(self):
        for index in range(64, 128):
            result = TOOL["progress_preview"](MASK, index)
            self.assertTrue(result["store_reached"])
            self.assertEqual(result["or_operand"], 0)
            self.assertTrue(result["skill48_request"])

    def test_sld_aliases128_and_large_nonnegative_values(self):
        for index in (128, 256, 0x7FFFFF80):
            self.assertEqual(TOOL["progress_preview"](0, index)["bank_after_local_store"], 1)
        self.assertEqual(TOOL["progress_preview"](0, 191)["or_operand"], 1 << 63)
        self.assertEqual(TOOL["progress_preview"](0, 0x7FFFFFFF)["or_operand"], 0)

    def test_signed_negative_skips_store_not_equality(self):
        for index in (0x80000000, 0x80000001, 0xFFFFFFFF):
            result = TOOL["progress_preview"](MASK, index)
            self.assertFalse(result["store_reached"])
            self.assertTrue(result["skill48_request"])
            self.assertEqual(result["bank_after_local_store"], MASK)
            self.assertFalse(TOOL["progress_preview"](0, index)["skill48_request"])

    def test_raw_input_validation(self):
        for slot, width in ((0, 64), (1, 32)):
            for invalid in (-1, 1 << width, True, None, "0", 1.0):
                args = [0, 0]
                args[slot] = invalid
                with self.assertRaises(ValueError):
                    TOOL["progress_preview"](*args)

    def test_request_is_not_runtime_execution_or_new_award(self):
        scope = TOOL["progress_preview"](MASK, 0)["scope"]
        self.assertIn("not a new award", scope)
        self.assertIn("AFTER", TOOL["progress_preview"].__doc__)
        self.assertIn("No earlier callback", scope)

    def test_five_producers_exact_named_award_and_guards(self):
        report = self.native()
        self.assertEqual(len(report["producers"]), 5)
        self.assertEqual(len(report["instruction_guards"]), 134)
        self.assertEqual((report["bank"]["offset"], report["bank"]["type"]), ("0x8720", "u64 BE"))
        self.assertEqual((report["award"]["id"], report["award"]["enum"], report["award"]["points"]), (48, "SKILLPOINT_DANCE", 40))
        self.assertIn("not trophy", report["award"]["linkage"])
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)

    def test_pointer_opcode_definition_and_negative_branch_tamper_refused(self):
        self.native()
        cls = TOOL["BINDINGS"]["Elf"]
        original = cls.u32
        for target in (0x892094, 0x892098, 0x1354C4, 0x1354D8, 0x1354F0, 0x122EC, 0x10026954, 0x8998C0, 0x14004C):
            def changed(instance, address):
                return original(instance, address) ^ (4 if address == target else 0)
            with patch.object(cls, "u32", changed), self.assertRaises(ValueError):
                TOOL["inspect"](ELF)

    def test_initialization_and_target_identity_limits(self):
        report = self.native()
        self.assertIn("+31F8", report["initialization"])
        self.assertIn("producer-only report does not assign target names", report["warning"])
        self.assertIn("not names for28 enemies", report["identity_limits"])
        self.assertNotIn("save_observation", report)

    def test_actual_snapshot_keeps_earned_award_independent_and_hash_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save")
        before = hashlib.sha256(SAVE.read_bytes()).hexdigest()
        observation = self.native(SAVE)["save_observation"]
        self.assertEqual(observation["bank_hex"], "0000000000000000")
        self.assertTrue(observation["skill48_earned"])
        self.assertFalse(observation["exact_completion_pattern"])
        self.assertEqual(before, hashlib.sha256(SAVE.read_bytes()).hexdigest())

    def test_synthetic_high_bits_neighbors_and_independent_award_retained(self):
        self.native()
        raw = bytearray(0x906F0)
        for index in range(32):
            struct.pack_into(">I", raw, index * 20, index)
        struct.pack_into(">Q", raw, 0x8720, MASK | (1 << 63))
        raw[0x8718:0x8720] = bytes.fromhex("1122334455667788")
        raw[0x8728:0x8730] = bytes.fromhex("8877665544332211")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "fixture.bin"
            path.write_bytes(raw)
            observation = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(observation["bank_hex"], "800000000FFFFFFF")
            self.assertEqual(observation["high_bits_hex"], "8000000000000000")
            self.assertEqual(observation["low28_set_indices"], list(range(28)))
            self.assertFalse(observation["skill48_earned"])
            self.assertFalse(observation["exact_completion_pattern"])
            self.assertEqual(path.read_bytes(), raw)
            path.write_bytes(raw[:-1])
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF, path)

    def test_embedded_report_reproduces_without_private_snapshot(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(mapping["dance_progress"], report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
