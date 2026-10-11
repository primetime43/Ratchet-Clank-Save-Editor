"""Saved counter provenance, wrapping, bounded consumers and target initialization/restoration."""
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
        self.assertEqual(len(report["instruction_guards"]), 166)
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)
        self.assertEqual([(f["offset"], f["type"]) for f in report["fields"]], [("0x872C", "u32 BE"), ("0x8730", "u32 BE")])

    def test_pointer_gate_slope_store_and_call_tampering_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0x8A1C70, 0x8A1C48, 0x8A1C80, 0x8A206C, 0x36C678, 0x36C69C, 0x36C6D4, 0x375C84, 0x362C50, 0x36FCEC,
                        0x8A19B8, 0x8A1C24, 0x362108, 0x3621CC, 0x3621D0, 0x35F49C, 0x3620B4, 0x35F4A4, 0x36A964,
                        0x3645E4, 0x3620B8, 0x8A688C, 0x8A6890, 0x489FBC, 0x489FCC, 0x489F88, 0x39A35C, 0x398808, 0x39B594):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (4 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_changed_toc_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for function in (0x36C578, 0x3620D0, 0x35F490, 0x362098, 0x3645E0, 0x2D08D8, 0x39A328, 0x3987B8, 0x39B2E8):
            with patch.dict(elf.descriptors, {function: 0x88FF38}):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_zero_admission_reaches_explicit_initialization_stores(self):
        result = TOOL["initialization_store_preview"](0, 0xFFFFFFFF, 0x80000001)
        self.assertTrue(result["reaches_initialization"])
        self.assertEqual((result["admission_byte"], result["next_index"], result["pending"]), (1, 0, 0))
        self.assertIn("not complete callback effects", result["qualification"])

    def test_every_nonzero_admission_returns_without_initialization(self):
        for value in range(1, 256):
            result = TOOL["initialization_store_preview"](value, 0xFFFFFFFF, 0x80000001)
            self.assertFalse(result["reaches_initialization"])
            self.assertEqual((result["admission_byte"], result["next_index"], result["pending"]), (value, 0xFFFFFFFF, 0x80000001))

    def test_initialization_projection_invalid_inputs_refused(self):
        for bad in (-1, 256, True, 1.0, "0", None):
            with self.assertRaises(ValueError):
                TOOL["initialization_store_preview"](bad, 0, 0)
        for slot in (1, 2):
            for bad in (-1, 1 << 32, True, 1.0, None):
                args = [0, 0, 0]
                args[slot] = bad
                with self.assertRaises(ValueError):
                    TOOL["initialization_store_preview"](*args)

    def test_rejected_registration_still_consumes_zero_based_index(self):
        initialized = TOOL["initialization_store_preview"](0, 99, 0xFFFF)
        first = TOOL["registration_preview"](1, initialized["pending"], initialized["next_index"])
        second = TOOL["registration_preview"](1, first["pending_after_store"], first["next_index"])
        self.assertEqual((first["assigned_index"], first["admitted"], first["next_index"]), (0, False, 1))
        self.assertEqual((second["assigned_index"], second["admitted"], second["pending_after_store"]), (1, True, 2))
        self.assertEqual((first["saved_progress"], second["saved_progress"]), (1, 1))

    def test_distinct_pointer_bases_resolve_same_runtime_admission_owner(self):
        report = self.native()["registration_initialization"]
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        self.assertEqual(elf.u32(0x8A19B8) + 0x10, elf.u32(0x8A1C24))
        self.assertEqual(int(report["owner"], 0) + 0xF4, int(report["admission_byte_va"], 0))
        self.assertEqual(int(report["owner"], 0) + 0x11C, int(report["next_index_va"], 0))
        self.assertEqual(int(report["owner"], 0) + 0xFC, int(report["pending_mask_va"], 0))
        self.assertIn("intervening write", report["reinitialization_admission"])
        self.assertIn("not a fixed named target catalog", report["index_identity_limit"])
        self.assertIn("not proof that every called helper preserves", report["save_boundary"])

    def test_bounded_saved_store_plan_order_and_one_byte_visited(self):
        for identifier in range(19):
            plan = TOOL["load_reset_store_plan"](identifier)
            self.assertEqual([(int(s["offset"], 0), s["size"], s["value"]) for s in plan["stores"]],
                [(0x906E8, 4, identifier), (0x889 + 0x408 * identifier, 1, 1),
                 (0x8730, 4, 0), (0x8728, 4, 0), (0x872C, 4, 0)])
            self.assertIn("not an atomic transaction", plan["qualification"])

    def test_store_plan_refuses_arbitrary_saved_ids_and_noninteger_values(self):
        for bad in (-1, 19, 0xFFFFFFFF, True, 0.0, "0", None):
            with self.assertRaises(ValueError):
                TOOL["load_reset_store_plan"](bad)

    def test_detached_store_plan_preserves_unlocked_exclusion_and_opaque_bytes(self):
        # Generated fixture, not a native/gameplay execution or captured save transition.
        for identifier in range(19):
            before = bytes([0xA5]) * 0x906F0
            after = bytearray(before)
            touched = set()
            for store in TOOL["load_reset_store_plan"](identifier)["stores"]:
                offset, size = int(store["offset"], 0), store["size"]
                after[offset:offset + size] = store["value"].to_bytes(size, "big")
                touched.update(range(offset, offset + size))
            visited = 0x889 + 0x408 * identifier
            self.assertEqual(after[visited - 1:visited + 2], bytes([0xA5, 1, 0xA5]))
            self.assertEqual([index for index, (a, b) in enumerate(zip(before, after)) if a != b], sorted(touched))
            self.assertEqual(before[0x8728:0x8734], bytes([0xA5]) * 12)

    def test_native_reset_catalog_name_source_and_no_match_fallback_qualification(self):
        report = self.native()["reset_publication"]
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        self.assertEqual(elf.u32(0x8A688C), int(report["name_cell"], 0))
        self.assertEqual(len(report["catalog"]), 19)
        for row in report["catalog"]:
            self.assertEqual(row["internal_name"], elf.string(elf.u32(0x10062F7C + 4 * row["id"])))
            self.assertEqual(int(row["visited_offset"], 0), 0x488 + 0x401 + 0x408 * row["id"])
        self.assertIn("or0 if none matches", report["lookup_limit"])
        self.assertIn("not proof that the name matched", report["lookup_limit"])
        self.assertIn("do not prove they ran on this save", report["snapshot_limit"])

    def test_closed_reinitialization_leaf_only_clears_separate_runtime_word(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        self.assertEqual(elf.read(0x3645E0, 12).hex().upper(), "38000000900300304E800020")
        self.assertEqual(elf.u32(0x8A19B8) + 0x10 + 0x10 + 0x30, 0x10330780)
        self.assertIn("neither clears next index/pending", report["reinitialization_closed_leaf"])
        self.assertIn("no remaining callees", report["reinitialization_closed_leaf"])

    def test_selected_reset_entry_precedes_asset_gates_not_universal_event_proof(self):
        report = self.native()["reset_publication"]
        self.assertIn("before its later asset/pointer branches", report["rule"])
        self.assertIn("no local old-destination equality", report["rule"])
        self.assertIn("ONE byte1", report["rule"])
        self.assertIn("universal death/retry", report["caller_limit"])
        self.assertIn("other branches do not establish", report["caller_limit"])

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
        self.assertEqual(observed["saved_destination"], 0)
        self.assertEqual(observed["visited_bytes"], [1] + [0] * 18)
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
