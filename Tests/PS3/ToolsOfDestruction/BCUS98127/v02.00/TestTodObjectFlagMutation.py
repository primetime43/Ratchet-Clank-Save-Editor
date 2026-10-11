"""Object event/restore publication checks, bounded previews and raw snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodObjectFlagMutation.py"))
ELF = SAVE = None


class ObjectFlagMutationChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact native evidence")
        return TOOL["inspect"](ELF)

    def test_map_reproduction(self):
        report = self.native()
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["object_flag_mutation"])

    def test_exact_guards_and_full_function_coverage(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        guards = {int(g["va"], 0): bytes.fromhex(g["bytes"]) for g in report["instruction_guards"]}
        self.assertEqual(len(guards), 83)
        for va, raw in guards.items():
            self.assertEqual(elf.read(va, len(raw)), raw)
        for va in (0x2DD588, 0x2DD698, 0x2F7720, 0x2F77A8, 0x2F7930, 0x3BF5A8, 0x3C0160, 0x27C358, 0x2FE0E8):
            end = elf.functions[elf.functions.index(va) + 1]
            self.assertEqual(len(guards[va]), end - va)

    def test_native_order_scope_and_opaque_names(self):
        report = self.native()
        order = report["event_leaf"]["publication_order"]
        self.assertIn("virtual", order[0])
        self.assertIn("2DD60C", order[1])
        self.assertIn("First UID match", order[3])
        self.assertIn("1D", order[4])
        self.assertIn("after callback returns", report["event_leaf"]["scope"])
        self.assertIn("not proof of atomic", report["suppression_publication"]["store_shape"])
        self.assertIn("no boss", report["opaque_producers"][0]["warning"])
        self.assertIn("BEFORE object-pool validation", report["record_request"]["order"])
        self.assertIn("WITHOUT querying saved bit", report["auxiliary_consumer"]["order"])

    def test_event_zero_latch_low_byte_and_first_duplicate_uid_only(self):
        records = [7, 0x80000000, 7, 7]
        original = list(records)
        result = TOOL["event_gate_preview"](0, 0xFFFFFFAB, 7, records)
        self.assertTrue(result["callback_admitted"])
        self.assertEqual(result["callback_argument_low_byte"], 0xAB)
        self.assertTrue(result["saved_bit_set_after_callback_returns"])
        self.assertEqual(result["first_matching_runtime_record"], 0)
        self.assertEqual(result["matching_record_byte_c_result"], 0)
        self.assertEqual(result["event_latch_result"], 1)
        self.assertEqual(records, original)
        self.assertIsNone(TOOL["event_gate_preview"](0, 0, 5, records)["first_matching_runtime_record"])

    def test_event_nonzero_latch_normalizes_without_callback_bit_or_scan(self):
        for latch in (1, 2, 255):
            result = TOOL["event_gate_preview"](latch, 0xFFFFFFFF, 7, [7])
            self.assertFalse(result["callback_admitted"])
            self.assertIsNone(result["callback_argument_low_byte"])
            self.assertFalse(result["saved_bit_set_after_callback_returns"])
            self.assertIsNone(result["first_matching_runtime_record"])
            self.assertEqual(result["event_latch_result"], 1)

    def test_pending_consumed_even_with_clear_saved_bit(self):
        preview = TOOL["restore_gate_preview"]
        for pending in (1, 255):
            result = preview(pending, False, 2)
            self.assertEqual(result["pending_result"], 0)
            self.assertTrue(result["saved_bit_queried"])
            self.assertFalse(result["event_leaf_called"])
            self.assertEqual(result["event_latch_result"], 2)
        result = preview(0, True, 255)
        self.assertFalse(result["saved_bit_queried"])
        self.assertFalse(result["event_leaf_called"])
        self.assertEqual(result["event_latch_result"], 255)

    def test_saved_bit_does_not_bypass_event_latch(self):
        preview = TOOL["restore_gate_preview"]
        for latch in (0, 1, 255):
            result = preview(1, True, latch)
            self.assertTrue(result["event_leaf_called"])
            self.assertEqual(result["event_argument"], 0)
            self.assertEqual(result["virtual_callback_admitted"], latch == 0)
            self.assertEqual(result["event_latch_result"], 1)

    def test_suppression_flag_only_gates_write_not_downstream_call(self):
        preview = TOOL["suppression_gate_preview"]
        for flags in (0, 0xFFFF, 0xFFFEFFFF):
            result = preview(flags, 0x8000000000000000, 0)
            self.assertFalse(result["saved_write_admitted"])
            self.assertEqual(result["result_word"], 0x8000000000000000)
            self.assertTrue(result["downstream_helper_called"])
        self.assertEqual(preview(0x10000, 1, 63)["result_word"], 0x8000000000000001)
        self.assertEqual(preview(0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF, 63)["result_word"], 0xFFFFFFFFFFFFFFFF)

    def test_request_clears_record_before_full_handle_route(self):
        preview = TOOL["record_request_preview"]
        self.assertTrue(preview(0x12340005, 5, 0x12340005, True)["reaches_actor_pointer_read"])
        for args in ((0x12340006, 5, 0x12340006, True), (0x12340005, 5, 0x56780005, True), (5, 5, 5, False)):
            result = preview(*args)
            self.assertFalse(result["reaches_actor_pointer_read"])
            self.assertEqual(result["resolved_record_byte_c_result"], 0)
        self.assertTrue(preview(0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, True)["reaches_actor_pointer_read"])

    def test_auxiliary_state_nine_short_circuits_saved_bit_query(self):
        preview = TOOL["auxiliary_consumer_preview"]
        for bit in (False, True):
            result = preview(True, 9, bit)
            self.assertFalse(result["saved_bit_queried"])
            self.assertEqual(result["runtime_byte_643_result"], 1)
            self.assertTrue(result["runtime_helper_24f4f8_called"])
        for state in (0, 8, 0xFFFFFFFF):
            for bit in (False, True):
                self.assertEqual(preview(True, state, bit)["runtime_byte_643_result"], int(bit))
                self.assertTrue(preview(True, state, bit)["saved_bit_queried"])
        self.assertEqual(preview(False, 9, True), {"runtime_helper_24f4f8_called": False, "saved_bit_queried": False, "runtime_byte_643_result": 0})

    def test_invalid_preview_shapes_rejected(self):
        for value in (-1, 256, True, 1.0, None):
            with self.assertRaises(ValueError):
                TOOL["event_gate_preview"](value, 0, 0, [])
            with self.assertRaises(ValueError):
                TOOL["restore_gate_preview"](0, True, value)
        for value in (-1, 0x100000000, True, 1.0, None):
            with self.assertRaises(ValueError):
                TOOL["event_gate_preview"](0, value, 0, [])
            with self.assertRaises(ValueError):
                TOOL["record_request_preview"](0, value, 0, True)
            with self.assertRaises(ValueError):
                TOOL["auxiliary_consumer_preview"](True, value, False)
        for records in (None, "", {0: 0}, [True], [0] * 2049):
            with self.assertRaises(ValueError):
                TOOL["event_gate_preview"](0, 0, 0, records)
        for bit in (-1, 64, True, None):
            with self.assertRaises(ValueError):
                TOOL["suppression_gate_preview"](0, 0, bit)
        for word in (-1, 1 << 64, True):
            with self.assertRaises(ValueError):
                TOOL["suppression_gate_preview"](0, word, 0)
        with self.assertRaises(ValueError):
            TOOL["restore_gate_preview"](0, 1, 0)
        with self.assertRaises(ValueError):
            TOOL["auxiliary_consumer_preview"](1, 0, False)
        with self.assertRaises(ValueError):
            TOOL["record_request_preview"](0, 0, 0, 1)

    def test_raw_snapshot_world_twenty_and_high_bits_preserved(self):
        self.native()
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 20, i)
        struct.pack_into(">Q", data, 0x668, 0x8000000000000000)
        last = 0x488 + 19 * 0x408 + 0x2E0
        data[last:last + 256] = b"\xFF" * 256
        with tempfile.TemporaryDirectory(prefix="tod-object-raw-") as directory:
            path = Path(directory) / "snapshot.bin"
            path.write_bytes(data)
            observation = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(path.read_bytes(), data)
        self.assertEqual(observation["worlds"][0]["recorded_raw_words"][0], "8000000000000000")
        self.assertEqual(observation["worlds"][0]["recorded_set_count"], 1)
        self.assertEqual(observation["worlds"][0]["suppression_set_count"], 0)
        self.assertFalse(observation["worlds"][19]["named_world"])
        self.assertEqual(observation["worlds"][19]["suppression_set_count"], 2048)
        self.assertEqual(observation["worlds"][19]["recorded_set_count"], 0)

    def test_malformed_snapshots_rejected_without_changes(self):
        self.native()
        with tempfile.TemporaryDirectory(prefix="tod-object-invalid-") as directory:
            path = Path(directory) / "snapshot.bin"
            for data in (b"", b"\0" * 0x906EF, b"\0" * 0x906F1, b"\0" * 0x906F0):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)
                self.assertEqual(path.read_bytes(), data)

    def test_actual_detached_save_and_original_elf_unchanged(self):
        if ELF is None or SAVE is None:
            self.skipTest("Pass --elf and --save for actual snapshot")
        before_elf = hashlib.sha256(ELF.read_bytes()).hexdigest().upper()
        before_save = hashlib.sha256(SAVE.read_bytes()).hexdigest().upper()
        observation = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(observation["sha256"], "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
        self.assertEqual(len(observation["worlds"]), 20)
        self.assertTrue(all(w["recorded_set_count"] == 0 and w["suppression_set_count"] == 0 for w in observation["worlds"]))
        self.assertEqual(hashlib.sha256(ELF.read_bytes()).hexdigest().upper(), before_elf)
        self.assertEqual(hashlib.sha256(SAVE.read_bytes()).hexdigest().upper(), before_save)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
