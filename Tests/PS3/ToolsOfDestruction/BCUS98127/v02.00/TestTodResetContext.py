"""Exact native reset admission, latch publication, and independent counter gates."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("reset_context", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodResetContext.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


class ResetContextChecks(unittest.TestCase):
    def test_admission_requires_zero_latch_and_zero_predicate_low_byte(self):
        initial = [7] * 8
        for latch in (0, 1, 2, 0x80000000, 0xFFFFFFFF):
            for predicate in (0, 1, 255, 256, 257, 0xFFFFFF00, 0xFFFFFFFF):
                result = TOOL.request_preview(2, latch, predicate, 0, initial, 41)
                admitted = latch == 0 and predicate & 255 == 0
                self.assertEqual(result["admitted"], admitted)
                self.assertEqual(result["category_words"][2], 8 if admitted else 7)
                self.assertEqual(result["segment_count"], 42 if admitted else 41)
                self.assertEqual(result["post_callback_latch_if_calls_return"], 1 if admitted else latch)
                self.assertEqual(initial, [7] * 8)

    def test_category_zero_and_saved_restart_gate_are_independent(self):
        for category in range(8):
            for replay in (0, 1, 3, 0x80000000, 0xFFFFFFFF):
                result = TOOL.request_preview(category, 0, 0, replay, [0] * 8, 9)
                self.assertEqual(sum(result["category_words"]), int(category != 0))
                self.assertEqual(result["segment_count"], 10 if replay == 0 else 9)
        self.assertIsNone(TOOL.request_preview(3, 0, 0, 0, [0] * 8)["segment_count"])

    def test_count_wrap_preserves_other_words(self):
        words = [0, 1, 2, 0xFFFFFFFF, 4, 5, 6, 0x80000000]
        result = TOOL.request_preview(3, 0, 0, 0, words, 0xFFFFFFFF)
        self.assertEqual(result["category_words"], [0, 1, 2, 0, 4, 5, 6, 0x80000000])
        self.assertEqual(result["segment_count"], 0)
        self.assertEqual(words[3], 0xFFFFFFFF)

    def test_blocking_predicate_unsigned_range_and_secondary_modes(self):
        for state in (0, 6, 7, 8, 9, 10, 0x80000000, 0xFFFFFFFF):
            for predicate in (0, 1, 256, 257, 0xFFFFFFFF):
                for mode in (0, 7, 8, 9, 0x80000009, 0xFFFFFFFF):
                    expected = 7 <= state <= 9 or predicate & 255 != 0 and mode in (7, 9)
                    self.assertEqual(TOOL.blocking_preview(0, state, predicate, mode), int(expected))
                    self.assertEqual(TOOL.blocking_preview(0xFFFFFFFF, state, predicate, mode), 1)

    def test_latch_service_only_exact_one_and_ordered_float_threshold(self):
        for bits in (0, 0x80000000, 0x3F7FFFFF, 0x3F800000, 0x3F800001,
                     0x7F800000, 0xFF800000, 0x7FC00000, 0x7F800001, 0xFFC00000):
            value = struct.unpack(">f", struct.pack(">I", bits))[0]
            for latch in (0, 1, 2, 0xFFFFFFFF):
                self.assertEqual(TOOL.latch_service_preview(latch, bits), 0 if latch == 1 and value >= 1.0 else latch)

    def test_preview_refuses_unbounded_or_nonword_inputs(self):
        for category in (-1, 8, 0xFFFFFFFF, True, "1"):
            with self.assertRaises(ValueError):
                TOOL.request_preview(category, 0, 0, 0, [0] * 8)
        for words in (None, [0] * 7, [0] * 9, [0] * 7 + [-1], [0] * 7 + [True]):
            with self.assertRaises(ValueError):
                TOOL.request_preview(2, 0, 0, 0, words)
        with self.assertRaises(ValueError):
            TOOL.blocking_preview(0, -1, 0, 0)
        with self.assertRaises(ValueError):
            TOOL.latch_service_preview(1, 0x100000000)

    def test_reproduces_map_and_all_native_guards(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")
        report = TOOL.inspect(ELF)
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["reset_context"])
        elf = TOOL.BINDINGS.Elf(ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(raw, elf.read(int(guard["va"], 0), len(raw)))
        self.assertNotIn("save_observation", report)

    def test_context_publication_and_unresolved_names(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")
        report = TOOL.inspect(ELF)
        self.assertEqual(report["admission"]["ordered_calls"], ["0x13680 -> 0x2ce518", "0x244760", "0x11050"])
        self.assertEqual(report["latch_service"]["threshold"], 1.0)
        self.assertIn("not set before", report["admission"]["publication"])
        self.assertIn("does not consume", report["blocking_context"]["scope"])
        self.assertEqual([e["categories"] for e in report["virtual_selector_contexts"]], [[5], [2], [4], [6], [3, 7]])
        self.assertIn("Category1 selection", report["unresolved"][0])

    def test_bad_save_layout_rejected_before_observation(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")
        with tempfile.TemporaryDirectory(prefix="tod-reset-context-invalid-") as folder:
            path = Path(folder) / "GAME.bin"
            for data in (b"wrong", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)

    def test_actual_snapshot_counts_gate_and_unchanged_inputs(self):
        if ELF is None or SAVE is None:
            self.skipTest("Pass --elf and --save for actual snapshot validation")
        before = [hashlib.sha256(path.read_bytes()).digest() for path in (ELF, SAVE)]
        observation = TOOL.inspect(ELF, SAVE)["save_observation"]
        self.assertEqual(observation["category_words"], [0] * 8)
        self.assertEqual(observation["saved_replay_restart_counter"], 3)
        self.assertIn("runtime-only", observation["scope"])
        self.assertEqual(before, [hashlib.sha256(path.read_bytes()).digest() for path in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
