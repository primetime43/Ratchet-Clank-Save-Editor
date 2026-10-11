"""Direct assignment and warning state, with static provenance and immutable previews."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodQuickSelectWarning.py"))
ELF = SAVE = None


class QuickSelectWarningChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_ordinary_counter_advances_to_five(self):
        self.assertEqual([TOOL["counter_preview"](n) for n in range(9)], [1, 2, 3, 4, 5, 5, 5, 5, 5])

    def test_signed_difference_high_words_not_unsigned_min(self):
        for old, expected in ((0x7FFFFFFF, 5), (0x80000000, 5), (0x80000004, 5),
                              (0x80000005, 0x80000006), (0xFFFFFFFE, 0xFFFFFFFF), (0xFFFFFFFF, 0)):
            self.assertEqual(TOOL["counter_preview"](old), expected)

    def test_direct_assignment_admits_all_thirty_two_slots(self):
        for slot in range(32):
            result = TOOL["assignment_preview"](slot, 1, True, 0)
            self.assertTrue(result["store"])
            self.assertEqual(result["value"], 1)
        for slot in (32, 0x80000000, 0xFFFFFFFF):
            self.assertFalse(TOOL["assignment_preview"](slot, 1, True, 0)["store"])

    def test_any_unsigned_invalid_item_clears_not_only_sentinel(self):
        for item in (32, 99, 0x80000000, 0xFFFFFFFE, 0xFFFFFFFF):
            result = TOOL["assignment_preview"](31, item, False, 0xFFFFFFFF)
            self.assertTrue(result["store"])
            self.assertEqual(result["value"], 0xFFFFFFFF)

    def test_null_definition_and_rejected_flags_do_not_store(self):
        self.assertFalse(TOOL["assignment_preview"](0, 1, False, 0)["store"])
        for flags in (0x40, 0x1000, 0x1040, 0xFFFFFFFF):
            self.assertFalse(TOOL["assignment_preview"](0, 1, True, flags)["store"])
        self.assertTrue(TOOL["assignment_preview"](0, 1, True, 0x80000001)["store"])

    def test_invalid_words_bytes_and_truthy_nonbooleans_refused(self):
        for bad in (-1, 1 << 32, True, 1.0, "0", None):
            with self.assertRaises(ValueError):
                TOOL["counter_preview"](bad)
            with self.assertRaises(ValueError):
                TOOL["warning_preview"](bad, 0)
            for slot in (0, 1, 3):
                args = [0, 0, True, 0]
                args[slot] = bad
                with self.assertRaises(ValueError):
                    TOOL["assignment_preview"](*args)
        for bad in (-1, 256, True, "1", None):
            with self.assertRaises(ValueError):
                TOOL["warning_preview"](0, bad)
        for bad in (0, 1, "yes", None):
            with self.assertRaises(ValueError):
                TOOL["assignment_preview"](0, 0, bad, 0)

    def test_warning_truth_table_all_raw_latches_and_unsigned_boundaries(self):
        for latch in range(256):
            for counter in (0, 1, 2, 3, 4, 5, 0x80000000, 0xFFFFFFFF):
                result = TOOL["warning_preview"](counter, latch)
                suppressed = latch != 0 and counter > 3
                self.assertEqual(result["message_request_id"], None if suppressed else 0x126)
                self.assertEqual(result["latch_after_local_store"], latch if suppressed else 1)

    def test_gate_preview_does_not_claim_callback_or_playback_success(self):
        self.assertIn("request runs before", TOOL["warning_preview"](5, 0)["qualification"])
        self.assertIn("no callback effects", TOOL["warning_preview"](0, 255)["qualification"])

    def test_named_binding_failed_assignment_and_duplicate_scope(self):
        report = self.native()
        self.assertEqual(report["named_assignment"]["name"], "set_qs_weapon_in_slot")
        self.assertIn("no duplicate-removal", report["named_assignment"]["rule"].lower())
        self.assertIn("wrapper-rejected", report["named_assignment"]["rule"])
        self.assertIn("despite prior counter update", report["named_assignment"]["rule"])
        self.assertIn("without testing a success result", report["latch"]["rule"])

    def test_exact_native_guards_and_different_word_byte_types(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        self.assertEqual(len(report["instruction_guards"]), 87)
        self.assertEqual((report["counter"]["offset"], report["counter"]["type"], report["latch"]["offset"], report["latch"]["type"]), ("0x8734", "u32 BE", "0x8738", "u8"))
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)

    def test_pointer_binding_counter_gate_initializer_or_call_tampering_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0x888624, 0x889598, 0x26E58, 0x26E68, 0x26E80, 0x1E2838, 0x1E286C, 0x1E2874, 0x35DBF4, 0x3CF00C):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (4 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_changed_assignment_toc_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        with patch.dict(elf.descriptors, {0x26E20: 0x89FF20}):
            with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF)

    def test_initialization_and_restart_keep_opaque_neighbors_distinct(self):
        report = self.native()
        self.assertIn("seven-byte loop", report["initialization"])
        self.assertIn("semantically opaque, not proven padding", report["initialization"])
        self.assertIn("not latch8738", report["restart"])
        self.assertIn("final post-callback state", report["restart"])

    def test_actual_save_five_clear_latch_and_unchanged_hashes(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)]
        observation = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual((observation["counter"], observation["latch_byte"], observation["opaque_neighbors_hex"]), (5, 0, "00000000000000"))
        self.assertIn("not assignment history", observation["qualification"])
        self.assertEqual(before, [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)])

    def test_synthetic_extreme_counter_byte_and_opaque_neighbors_preserved(self):
        self.native()
        raw = bytearray(0x906F0)
        for identifier in range(32):
            struct.pack_into(">I", raw, identifier * 20, identifier)
        struct.pack_into(">I", raw, 0x8734, 0xFFFFFFFF)
        raw[0x8738:0x8740] = bytes.fromhex("FF11223344556677")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(raw)
            observed = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual((observed["counter"], observed["latch_byte"], observed["opaque_neighbors_hex"]), (0xFFFFFFFF, 255, "11223344556677"))
            self.assertEqual(path.read_bytes(), raw)
            for bad in (raw[:-1], bytes(0x906F0)):
                path.write_bytes(bad)
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)

    def test_embedded_report_reproduction_without_private_save(self):
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(self.native(), mapping["quick_select_warning"])
        self.assertNotIn("save_observation", mapping["quick_select_warning"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
