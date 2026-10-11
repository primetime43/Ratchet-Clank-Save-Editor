"""Saved counter provenance, wrapping, bounded consumers and target restoration."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSavedEventCounters.py"))
ELF = SAVE = None


class SavedEventCounterChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_reached_unconditional_and_handle_qualified_counts(self):
        self.assertEqual(TOOL["increment_preview"](8, 3, False), (9, 3))
        self.assertEqual(TOOL["increment_preview"](8, 3, True), (9, 4))

    def test_wrapping_not_saturating_and_no_cross_counter_order(self):
        self.assertEqual(TOOL["increment_preview"](0xFFFFFFFF, 7, True), (0, 8))
        self.assertEqual(TOOL["increment_preview"](0, 0xFFFFFFFF, True), (1, 0))

    def test_unsigned_scaling_thresholds_and_caps(self):
        for offset, cap in ((0x872C, 5), (0x8730, 3)):
            for count in (*range(12), 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF):
                result = TOOL["scaling_preview"](count, offset)
                self.assertEqual(result["step"], 0 if count <= 2 else min(count - 2, cap))

    def test_fused_finite_reference_values(self):
        expected = {0x872C: [1.0, 1.149999976158142, 1.2999999523162842, 1.4500000476837158, 1.600000023841858, 1.75],
                    0x8730: [1.0, 0.8999999761581421, 0.800000011920929, 0.699999988079071]}
        for offset, values in expected.items():
            self.assertEqual([TOOL["scaling_preview"](count, offset)["factor"] for count in range(2, 2 + len(values))], values)
            self.assertIn("Nearest-even", TOOL["scaling_preview"](3, offset)["qualification"])

    def test_registration_restores_recorded_bit_without_pending_store(self):
        result = TOOL["registration_preview"](4, 8, 2)
        self.assertFalse(result["admitted"])
        self.assertEqual((result["assigned_index"], result["next_index"], result["pending_after_store"], result["saved_progress"]), (2, 3, 8, 4))

    def test_new_registration_preserves_progress_and_unrelated_pending(self):
        result = TOOL["registration_preview"](4, 8, 3)
        self.assertTrue(result["admitted"])
        self.assertEqual(result["pending_after_store"], 8)
        self.assertEqual(result["saved_progress"], 4)
        self.assertEqual(TOOL["registration_preview"](4, 8, 0)["pending_after_store"], 9)

    def test_shift_zero_returns_true_and_large_indices_alias(self):
        for index in (*range(128), 0x80000000, 0xFFFFFFFE, 0xFFFFFFFF):
            result = TOOL["registration_preview"](0xFFFFFFFF, 0x12345678, index)
            bit = 1 << (index & 63) if index & 63 < 32 else 0
            self.assertEqual(result["effective_bit"], bit)
            self.assertEqual(result["admitted"], bit == 0)
            self.assertEqual(result["pending_after_store"], 0x12345678)
            self.assertEqual(result["next_index"], (index + 1) & 0xFFFFFFFF)

    def test_invalid_words_and_nonboolean_admission_refused(self):
        for bad in (-1, 1 << 32, True, 1.0, "0", None):
            with self.assertRaises(ValueError):
                TOOL["scaling_preview"](bad, 0x872C)
            for slot in range(3):
                args = [0, 0, 0]
                args[slot] = bad
                with self.assertRaises(ValueError):
                    TOOL["registration_preview"](*args)
            with self.assertRaises(ValueError):
                TOOL["increment_preview"](bad, 0, True)
        for bad in (0, 1, "true", None):
            with self.assertRaises(ValueError):
                TOOL["increment_preview"](0, 0, bad)
        with self.assertRaises(ValueError):
            TOOL["scaling_preview"](0, 0x8728)

    def test_exact_guard_ranges_and_two_integer_fields(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        self.assertEqual(len(report["instruction_guards"]), 101)
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)
        self.assertEqual([(f["offset"], f["type"]) for f in report["fields"]], [("0x872C", "u32 BE"), ("0x8730", "u32 BE")])

    def test_pointer_gate_slope_store_and_call_tampering_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0x8A1C70, 0x8A1C48, 0x8A1C80, 0x8A206C, 0x36C678, 0x36C69C, 0x36C6D4, 0x375C84, 0x362C50, 0x36FCEC):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (4 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_changed_toc_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        with patch.dict(elf.descriptors, {0x36C578: 0x88FF38}):
            with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF)

    def test_runtime_pool_and_event_identity_caveats(self):
        report = self.native()
        self.assertIn("slot<=limit, NOT slot<limit", report["handle_gate"])
        self.assertIn("low32 identity match", report["handle_gate"])
        self.assertIn("not serialized", report["handle_gate"])
        self.assertIn("Unordered does not take", report["caller_gate"])
        self.assertIn("not proven deaths, kills", report["warning"])
        self.assertIn("FFFFFFFF", report["restoration_caller"])

    def test_actual_save_zero_counters_without_history_claim_and_unchanged_hashes(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)]
        observed = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(observed["raw_words"], {"0x8728": 0, "0x872c": 0, "0x8730": 0})
        self.assertIn("No prior event totals", observed["qualification"])
        self.assertEqual(before, [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)])

    def test_synthetic_high_words_preserved_and_malformed_layout_refused(self):
        self.native()
        raw = bytearray(0x906F0)
        for identifier in range(32):
            struct.pack_into(">I", raw, identifier * 20, identifier)
        struct.pack_into(">I", raw, 0x872C, 0xFFFFFFFF)
        struct.pack_into(">I", raw, 0x8730, 0x80000000)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(raw)
            observed = TOOL["inspect"](ELF, path)["save_observation"]["raw_words"]
            self.assertEqual(observed["0x872c"], 0xFFFFFFFF)
            self.assertEqual(observed["0x8730"], 0x80000000)
            self.assertEqual(path.read_bytes(), raw)
            for bad in (raw[:-1], bytes(0x906F0)):
                path.write_bytes(bad)
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)

    def test_embedded_report_reproduction_without_private_save(self):
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(self.native(), mapping["saved_event_counters"])
        self.assertNotIn("save_observation", mapping["saved_event_counters"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
