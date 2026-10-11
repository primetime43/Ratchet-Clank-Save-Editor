"""Exact reset-category producer boundaries without native/state VM execution."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodResetProducers.py"))
ELF = SAVE = None


class SelectorSampleChecks(unittest.TestCase):
    def test_signed_selection_and_unsigned_dispatch_are_distinct(self):
        for state, category, index in ((0, 2, 0), (28, 2, 28), (29, None, 29),
                (32, None, 32), (33, None, None), (0x7FFFFFFF, None, None),
                (0x80000000, 2, None), (0xFFFFFFFF, 2, None)):
            preview = TOOL["selector_preview"]("word_430", state)
            self.assertEqual((preview["selected_category"], preview["dispatch_index"]), (category, index))

    def test_category4_intervening_helpers_allow_distinct_samples(self):
        cases = [(2, 2, None, 2), (2, 0, None, 0), (0, 2, 4, 2),
                 (103, 0, 4, 0), (0, 103, 4, None), (0xFFFFFFFF, 0xFFFFFFFF, 4, None)]
        for state, later, category, index in cases:
            result = TOOL["selector_preview"]("word_4a4", state, dispatch_state=later)
            self.assertEqual((result["selected_category"], result["dispatch_index"]), (category, index))

    def test_category6_selects_before_table_limit(self):
        for state in range(256):
            result = TOOL["selector_preview"]("byte_762", state)
            self.assertEqual(result["selected_category"], 6 if state else None)
            self.assertEqual(result["dispatch_index"], state if 1 <= state <= 19 else None)
        for mode in (1, 2, 3, 255):
            result = TOOL["selector_preview"]("byte_762", 1, mode=mode)
            self.assertIsNone(result["selected_category"])
            self.assertIsNone(result["dispatch_index"])

    def test_flags_and_unconditional_contexts_not_counter_increment(self):
        for flags, expected in ((0, None), (0x1000, None), (0x800, 3), (0x1800, 7), (0xFFFFFFFF, 7)):
            result = TOOL["selector_preview"]("flags_8b0", flags)
            self.assertEqual(result["selected_category"], expected)
            self.assertIsNone(result["dispatch_index"])
            self.assertIn("not a native invocation or counter increment", result["scope"])
        self.assertEqual(TOOL["selector_preview"]("unconditional_5", 0)["selected_category"], 5)

    def test_invalid_words_bytes_and_contexts_refused(self):
        for state in (-1, 0x100000000, True, 1.0, "1", None):
            with self.assertRaises(ValueError):
                TOOL["selector_preview"]("word_430", state)
        for kwargs in ({"state": 256}, {"state": 1, "mode": 256}, {"state": 1, "dispatch_state": 256}):
            with self.assertRaises(ValueError):
                TOOL["selector_preview"]("byte_762", **kwargs)
        with self.assertRaises(ValueError):
            TOOL["selector_preview"]("death", 0)


class ResetProducerNativeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ELF is None:
            raise unittest.SkipTest("Pass --elf for exact native reproduction")
        cls.elf = TOOL["BINDINGS"]["Elf"](ELF)
        cls.report = TOOL["inspect"](ELF)

    def test_exact_native_guards_and_runtime_flag_mark(self):
        self.assertEqual(len(self.report["instruction_guards"]), 79)
        for guard in self.report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(self.elf.read(int(guard["va"], 0), len(raw)), raw)
        self.assertEqual(struct.unpack(">5I", self.elf.read(0x68FF68, 20)),
                         (0x81230014, 0x80690068, 0x60600020, 0x90090068, 0x4E800020))
        self.assertIn("not a saved bit", self.report["common_preselector"]["rule"])

    def test_dispatch_tables_signed_relative_and_duplicates_retained(self):
        tables = self.report["dispatch_tables"]
        self.assertEqual([r["physical_entries"] for r in tables], [33, 103, 20])
        self.assertEqual([r["unique_target_count"] for r in tables], [22, 28, 15])
        for row in tables:
            address, count = int(row["table_va"], 0), row["physical_entries"]
            displacements = struct.unpack(">" + str(count) + "i", self.elf.read(address, count * 4))
            self.assertEqual([int(r["target_va"], 0) for r in row["entries"]],
                             [(address + d) & 0xFFFFFFFF for d in displacements])
            self.assertEqual([r["state"] for r in row["entries"]], list(range(count)))
        self.assertEqual(tables[0]["entries"][0]["target_va"], "0x43530")
        self.assertEqual(tables[2]["entries"][0]["target_va"], "0x55060")

    def test_virtual_contexts_unknown_actor_labels_and_readonly_names(self):
        contexts = self.report["virtual_contexts"]
        self.assertEqual([r["categories"] for r in contexts], [[5], [2], [4], [6], [3, 7]])
        self.assertTrue(all(r["actor_name"] == "Unresolved" for r in contexts))
        self.assertIn("event cause/name", self.report["warning"])
        self.assertEqual([r["size"] for r in self.report["recommended_annotations"] if r["kind"] == "data"], [132, 412, 80])

    def test_preselector_state_request_and_reached_store_sites(self):
        producers = self.report["producer_boundaries"]
        self.assertIn("3EFB8(actor,23)", producers[0]["preselector_state_request"])
        self.assertIn("53490(actor,1)", producers[2]["preselector_state_request"])
        self.assertEqual(self.elf.u32(0x3F0C0), 0x915C0430)
        self.assertEqual(self.elf.u32(0x53680), 0x9BFE0762)
        self.assertIn("reached", producers[2]["preselector_state_request"])
        self.assertIn("separated by helper calls", producers[1]["boundary"])
        self.assertIn("does not gate the earlier", producers[3]["boundary"])

    def test_window_publication_not_saved_reset_or_float_vm(self):
        selection = self.report["selection_vs_recording"]
        self.assertEqual(selection["window_literal"], 0.25)
        self.assertIn("no saved-counter increment", selection["rule"])
        self.assertIn("last supplied category", selection["rule"])
        self.assertIn("unordered", self.report["float_gate_caution"])
        self.assertIn("raw CR bits only", self.report["float_gate_caution"])
        for init_va, branch_va, true_va in ((0x40544, 0x4054C, 0x40550), (0x54EE4, 0x54EEC, 0x54EF0)):
            self.assertEqual(self.elf.u32(init_va), 0x39200000)  # li r9,0
            self.assertEqual(self.elf.u32(true_va), 0x39200001)  # li r9,1
            word = self.elf.u32(branch_va)
            self.assertEqual((word >> 26, word >> 21 & 31, word >> 16 & 31, word & 0xFFFF), (16, 4, 29, 8))
            for cr7_bits, taken, predicate in ((8, True, 0), (4, False, 1), (2, True, 0), (1, True, 0)):
                result = TOOL["float_gt_gate_preview"](cr7_bits, word)
                self.assertEqual((result["branch_taken"], result["local_predicate"]), (taken, predicate))
            for invalid_word in (word ^ (1 << 21), word ^ (1 << 16), word | 1, word ^ 4):
                with self.assertRaises(ValueError):
                    TOOL["float_gt_gate_preview"](4, invalid_word)
        for invalid_cr in (16, -1, True, 1.0):
            with self.assertRaises(ValueError):
                TOOL["float_gt_gate_preview"](invalid_cr)

    def test_native_guard_tampering_refused_after_hash_constructor(self):
        original = self.elf.__class__.u32
        for address in (0x68FF70, 0x4340C, 0x4054C, 0x53680):
            def changed(elf, va, address=address):
                return original(elf, va) ^ (1 if va == address else 0)
            with patch.object(self.elf.__class__, "u32", changed):
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF)

    def test_supplied_save_raw_counters_and_unchanged_hash(self):
        if SAVE is None:
            self.skipTest("Pass --save for reference snapshot")
        before = Path(SAVE).read_bytes()
        digest = hashlib.sha256(before).digest()
        observation = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(observation["category_words"], list(struct.unpack_from(">8I", before, 0x5734)))
        self.assertEqual(observation["plaintext_sha256"], digest.hex().upper())
        self.assertEqual(hashlib.sha256(Path(SAVE).read_bytes()).digest(), digest)
        self.assertIn("not serialized here", observation["scope"])

    def test_invalid_save_preflight_and_untrusted_layout_rejected(self):
        with tempfile.TemporaryDirectory(prefix="tod-reset-producers-test-") as directory:
            path = Path(directory) / "invalid.bin"
            path.write_bytes(b"short")
            original_read = Path.read_bytes
            def checked_read(candidate):
                if candidate == path:
                    raise AssertionError("Short save should not be read")
                return original_read(candidate)
            with patch.object(Path, "read_bytes", checked_read):
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)
            path.write_bytes(bytes(0x906F0))
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF, path)

    def test_embedded_report_reproduction_after_parent_merge(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        if "reset_producers" not in mapping:
            self.skipTest("Isolated report not integrated yet")
        self.assertEqual(self.report, mapping["reset_producers"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
