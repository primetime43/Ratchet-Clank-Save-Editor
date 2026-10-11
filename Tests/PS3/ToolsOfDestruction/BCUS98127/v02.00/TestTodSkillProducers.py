"""Exact-build skill filter/producers; immutable previews and source checks."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSkillProducers.py"))
ELF = SAVE = None


def fixture():
    raw = bytearray(0x906F0)
    for identifier in range(32):
        struct.pack_into(">I", raw, identifier * 20, identifier)
    return raw


class SkillProducerChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_filter_ordinal_is_one_based_not_global_id(self):
        groups = [19] * 60
        groups[2] = groups[8] = groups[24] = 11
        before = list(groups)
        bits = 1 << 8 | 0xA << 60
        for ordinal, selected, complete in ((0, None, 0), (1, 2, 0), (2, 8, 1),
                                             (3, 24, 0), (4, None, 0), (0xFFFFFFFF, None, 0)):
            result = TOOL["filter_preview"](groups, 11, ordinal, bits)
            self.assertEqual(result["matching_ids"], [2, 8, 24])
            self.assertEqual(result["matching_count"], 3)
            self.assertEqual((result["selected_id"], result["native_completion_result"]), (selected, complete))
        self.assertEqual(groups, before)
        self.assertEqual(TOOL["filter_preview"](groups, 3, 1, bits)["matching_count"], 0)

    def test_arbitrary_group_words_are_not_normalized_into_worlds(self):
        groups = [0xFFFFFFFF] * 60
        result = TOOL["filter_preview"](groups, 0xFFFFFFFF, 60, 1 << 59)
        self.assertEqual(result["selected_id"], 59)
        self.assertEqual(result["native_completion_result"], 1)
        self.assertEqual(groups, [0xFFFFFFFF] * 60)

    def test_filter_input_bounds_reject_types_and_unbounded_words(self):
        for groups in (None, bytes(60), [1] * 59, [1] * 61, [True] * 60):
            with self.assertRaises(ValueError):
                TOOL["filter_preview"](groups, 1, 1, 0)
        for value in (-1, True, 1.0, 0x100000000):
            with self.assertRaises(ValueError):
                TOOL["filter_preview"]([1] * 60, value, 1, 0)
            with self.assertRaises(ValueError):
                TOOL["filter_preview"]([1] * 60, 1, value, 0)
        for bits in (-1, True, 1.0, 1 << 64):
            with self.assertRaises(ValueError):
                TOOL["filter_preview"]([1] * 60, 1, 1, bits)

    def test_iris_only_other_occupied_matching_config_zero_blocks(self):
        entries = [(False, False, True, 1, 0), (True, True, True, 1, 0),
                   (True, False, False, 1, 0), (True, False, True, 0, 0),
                   (True, False, True, 128, 0xFFFFFFFF)]
        before = list(entries)
        self.assertTrue(TOOL["iris_gate_preview"](128, 11, entries)["sampled_gate_matches"])
        self.assertEqual(entries, before)
        entries.append((True, False, True, 255, 0))
        result = TOOL["iris_gate_preview"](1, 11, entries)
        self.assertEqual(result["blocking_indices"], [5])
        self.assertFalse(result["sampled_gate_matches"])
        self.assertTrue(TOOL["iris_gate_preview"](1, 11, [])["sampled_gate_matches"])
        self.assertFalse(TOOL["iris_gate_preview"](0, 11, [])["sampled_gate_matches"])
        self.assertFalse(TOOL["iris_gate_preview"](1, 10, [])["sampled_gate_matches"])

    def test_iris_invalid_summary_cannot_imply_native_pool(self):
        for entries in (None, [(1, False, True, 1, 0)], [(True, False, True, True, 0)],
                        [(True, False, True, 256, 0)], [(True, False, True, 1, -1)],
                        [(True, False)], [(False, False, False, 0, 0)] * 65537):
            with self.assertRaises(ValueError):
                TOOL["iris_gate_preview"](1, 11, entries)
        for gate in (-1, 256, True):
            with self.assertRaises(ValueError):
                TOOL["iris_gate_preview"](gate, 11, [])

    def test_ratio_zero_threshold_and_nearest_even_rounding_boundary(self):
        preview = TOOL["ratio_gate_preview"]
        self.assertFalse(preview(0xFFFFFFFF, 0)["ordered_at_least_0_75"])
        self.assertIsNone(preview(0xFFFFFFFF, 0)["ratio_f32_hex"])
        self.assertFalse(preview(2, 3)["ordered_at_least_0_75"])
        self.assertTrue(preview(3, 4)["ordered_at_least_0_75"])
        self.assertEqual(preview(3, 4)["ratio_f32_hex"], "3F400000")
        # Exact integer ratio lies below.75, but both converted operands round
        # upward to50331648/67108864 in this explicit nearest-even sample.
        numerator, denominator = 50331647, 67108863
        self.assertLess(4 * numerator, 3 * denominator)
        self.assertTrue(preview(numerator, denominator)["ordered_at_least_0_75"])
        self.assertTrue(preview(0xFFFFFFFF, 0xFFFFFFFF)["ordered_at_least_0_75"])
        for value in (-1, True, 1.0, 0x100000000):
            with self.assertRaises(ValueError):
                preview(value, 1)
            with self.assertRaises(ValueError):
                preview(1, value)

    def test_guarded_group_getter_and_nine_named_producers(self):
        report = self.native()
        elf = TOOL["BINDINGS"].Elf(ELF)
        self.assertEqual(len(report["instruction_guards"]), 155)
        for guard in report["instruction_guards"]:
            self.assertEqual(elf.read(int(guard["va"], 0), len(guard["bytes"]) // 2).hex().upper(), guard["bytes"])
        self.assertEqual(report["definition_filter"]["confirmed_role"], "equality filter/group selector")
        catalog = report["definition_filter"]["catalog"]
        self.assertEqual([v["id"] for v in catalog if v["filter_group_word"] == 19], list(range(44, 60)))
        self.assertEqual(report["iris_wrench_producer"]["enum"], "SKILLPOINT_IRIS_WRENCH")
        self.assertEqual([v["skill_id"] for v in report["space_context_producer"]["predicates"]], [35, 36, 38, 39, 40, 41, 42, 43])

    def test_else_branch_and_runtime_numeric_limits_explicit(self):
        report = self.native()
        space = report["space_context_producer"]
        self.assertTrue(all(v["level_branch"] == "else:currentlevel neither4 nor8" for v in space["predicates"][-3:]))
        self.assertIn("it does not", space["scope"])
        self.assertIn("native FPSCR", space["ratio_rule"])
        self.assertIn("no time unit", space["predicates"][4]["condition"])
        self.assertIn("negative highwater", report["iris_wrench_producer"]["boundary"])
        self.assertIn("not an additional save field", report["definition_filter"]["scope"])
        self.assertEqual(len(report["recommended_annotations"]), 4)

    def test_saved_selector_source_and_callback_reread_order(self):
        report = self.native()
        elf = TOOL["BINDINGS"].Elf(ELF)
        source = report["level_selector_source"]
        self.assertEqual(source["saved_offset"], "0x906e8")
        self.assertIn("not proof", source["qualification"])
        self.assertIn("saved906E8", report["iris_wrench_producer"]["level_source"])
        self.assertIn("after formatting/notification", report["space_context_producer"]["level_source"])
        self.assertEqual(elf.u32(0x364170), 0x4E800421)
        self.assertEqual(TOOL["BINDINGS"].branch_target(elf.u32(0x364178), 0x364178), 0x2D1490)
        for address, word in ((0x364194, 0x83DF0104), (0x3641E8, 0x895F00F8),
                              (0x3641F4, 0x817F0138), (0x363F54, 0x88BF00F9),
                              (0x364224, 0x8B3F00FA)):
            self.assertEqual(elf.u32(address), word)
        self.assertEqual(len(report["callback_order"]), 5)
        self.assertIn("No simultaneous eligibility", report["callback_order"][-1])

    def test_exact_shape_tamper_refused(self):
        self.native()
        cls = TOOL["BINDINGS"].Elf
        original = cls.u32
        for address in (0x35EB28, 0x2EBC10, 0x3641F8, 0x8A1AF0):
            def changed(elf, va, address=address):
                return original(elf, va) ^ (1 if va == address else 0)
            with patch.object(cls, "u32", changed):
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF)

    def test_raw_score_unknown_bits_preserved_without_history_prediction(self):
        self.native()
        raw = fixture()
        struct.pack_into(">Q", raw, 0x8710, 0xA << 60 | 1 << 24 | 1 << 43)
        struct.pack_into(">I", raw, 0x8708, 0xFFFFFFFF)
        with tempfile.TemporaryDirectory(prefix="tod-skill-producers-test-") as folder:
            path = Path(folder) / "save.bin"
            path.write_bytes(raw)
            observation = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(observation["unknown_bits60_63_hex"], "A000000000000000")
            self.assertEqual(observation["score_raw"], 0xFFFFFFFF)
            self.assertEqual([v["id"] for v in observation["named_producer_bits"] if v["set"]], [24, 43])
            self.assertIn("does not establish which producer", observation["qualification"])
            self.assertEqual(path.read_bytes(), raw)

    def test_original_working_inputs_unchanged_and_actual_bits_read(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in (ELF, SAVE)]
        observation = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(observation["sha256"], "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
        self.assertEqual(observation["bits_hex"], SAVE.read_bytes()[0x8710:0x8718].hex().upper())
        self.assertEqual([hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in (ELF, SAVE)], before)

    def test_invalid_save_layout_refused(self):
        self.native()
        with tempfile.TemporaryDirectory(prefix="tod-skill-invalid-") as folder:
            path = Path(folder) / "save.bin"
            for raw in (bytes(17), bytes(0x906F0)):
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)

    def test_embedded_report_reproduces(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"].MAP_PATH.read_text())
        self.assertEqual(report, mapping["skill_producers"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
