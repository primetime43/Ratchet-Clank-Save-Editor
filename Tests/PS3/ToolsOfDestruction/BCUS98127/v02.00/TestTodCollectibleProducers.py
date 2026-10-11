"""Collector provenance, immutable mask leaves and unchanged snapshot checks."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodCollectibleProducers.py"))
ELF = SAVE = None


class CollectibleProducerChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_all_shift_cases_and_high_raw_indices(self):
        for index in (*range(128), 0x80000000, 0xFFFFFFFE, 0xFFFFFFFF):
            result = TOOL["publication_preview"](0, 0xFFFFFFFF, index)
            effective = index & 63
            bit = 1 << effective if effective < 32 else 0
            self.assertEqual(result["effective_bit"], bit)
            self.assertEqual(result["saved_progress_after_store"], bit)
            self.assertEqual(result["runtime_pending_after_store"], 0xFFFFFFFF ^ bit)

    def test_publication_idempotent_and_preserves_unrelated_bits(self):
        for index in (0, 2, 31, 32, 64):
            first = TOOL["publication_preview"](0x12345678, 0x87654321, index)
            second = TOOL["publication_preview"](first["saved_progress_after_store"], first["runtime_pending_after_store"], index)
            self.assertEqual(first, second)
            self.assertEqual(first["saved_progress_after_store"] & 0x12345678, 0x12345678)

    def test_dispatch_skips_only_exact_sentinel(self):
        self.assertFalse(TOOL["dispatch_preview"](0xFFFFFFFF))
        for index in (0, 31, 32, 64, 0x80000000, 0xFFFFFFFE):
            self.assertTrue(TOOL["dispatch_preview"](index))

    def test_partial_sets_message_latch_without_grant(self):
        result = TOOL["reward_gate_preview"](1, 1 << 63, 0)
        self.assertFalse(result["grant_requested"])
        self.assertEqual(result["message_lookup_id"], 0x648)
        self.assertEqual(result["flag_word_after_local_store"], (1 << 63) | (1 << 22))

    def test_partial_latch_suppresses_repeat_request(self):
        flags = (1 << 22) | 7
        result = TOOL["reward_gate_preview"](0x80000000, flags, 0)
        self.assertEqual(result, {"grant_requested": False, "message_lookup_id": None, "flag_word_after_local_store": flags})

    def test_complete_tests_local_zero_not_other_bits_or_message_latch(self):
        for flags in (0, 1 << 22, 0xFFFFFFFFFFFFFFFF):
            result = TOOL["reward_gate_preview"](0, flags, 0xFFFFFFFE)
            self.assertTrue(result["grant_requested"])
            self.assertEqual(result["message_lookup_id"], 0x348)
            self.assertEqual(result["flag_word_after_local_store"], flags)

    def test_complete_existing_local_zero_skips_grant_and_request(self):
        for mask in (1, 0x80000001, 0xFFFFFFFF):
            result = TOOL["reward_gate_preview"](0, 0, mask)
            self.assertFalse(result["grant_requested"])
            self.assertIsNone(result["message_lookup_id"])

    def test_post_lookup_pending_sample_not_derived_from_publication(self):
        before = TOOL["publication_preview"](0, 1, 0)
        self.assertEqual(before["runtime_pending_after_store"], 0)
        after_lookup = TOOL["reward_gate_preview"](8, 0, 0)
        self.assertFalse(after_lookup["grant_requested"])
        self.assertEqual(after_lookup["message_lookup_id"], 0x648)
        self.assertIn("reread", before["qualification"])

    def test_malformed_words_booleans_and_out_of_range_inputs_refused(self):
        for bad in (-1, 0x100000000, True, 1.0, "1", None, 10 ** 1000):
            for index in range(3):
                args = [0, 0, 0]
                args[index] = bad
                with self.assertRaises(ValueError):
                    TOOL["publication_preview"](*args)
            with self.assertRaises(ValueError):
                TOOL["dispatch_preview"](bad)
        for bad in (-1, 1 << 64, True, "0"):
            with self.assertRaises(ValueError):
                TOOL["reward_gate_preview"](0, bad, 0)

    def test_exact_native_guards_and_saved_runtime_separation(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        self.assertEqual(len(report["instruction_guards"]), 107)
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)
        self.assertEqual(report["saved_progress"]["offset"], "0x8728")
        self.assertEqual(report["partial"]["flag_id"], 278)
        self.assertEqual(report["partial"]["enum"], "SC_PLAYED_BONUS_TARGET_MSG")

    def test_changed_publication_gate_pointer_enum_or_link_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0x8A1AC4, 0x364354, 0x364360, 0x3644D4, 0x375C10, 0x3644E0, 0x304D34, 0x889104):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (4 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_changed_collector_toc_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        with patch.dict(elf.descriptors, {0x364300: 0x88FF38}):
            with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF)

    def test_reset_boundary_is_saved_zeroing_without_neighbor_names(self):
        report = self.native()
        self.assertEqual(report["reset"]["cleared_offsets"], ["0x8730", "0x8728", "0x872c"])
        self.assertIn("before465DC0", report["reset"]["rule"])
        self.assertIn("semantically unnamed", report["reset"]["rule"])
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0x8A6890, 0x489FF0, 0x489FF4, 0x489FF8, 0x489FE0, 0x489FFC):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (4 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_callback_order_destination_and_unknown_identity_caveats(self):
        report = self.native()
        self.assertIn("rereads", report["after_lookup"])
        self.assertIn("does not test saved8728", report["complete"]["rule"])
        self.assertIn("No explicit duplicate-bit precheck", report["direct_local_collector"]["rule"])
        self.assertIn("before the eventual saved-destination read", report["direct_local_collector"]["rule"])
        self.assertIn("not a target-completion", report["partial"]["rule"])

    def test_actual_save_values_and_hashes_remain_unchanged(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)]
        observed = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual((observed["progress_hex"], observed["set_bits"], observed["message_latch"], observed["saved_destination"]), ("00000000", [], False, 0))
        self.assertIsNone(observed["runtime_pending"])
        self.assertIsNone(observed["target_count"])
        self.assertEqual(before, [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)])

    def test_synthetic_high_bits_unknown_destination_and_layout(self):
        self.native()
        raw = bytearray(0x906F0)
        for identifier in range(32):
            struct.pack_into(">I", raw, identifier * 20, identifier)
        struct.pack_into(">I", raw, 0x8728, 0x80000001)
        struct.pack_into(">I", raw, 0x906E8, 0xFFFFFFFF)
        struct.pack_into(">Q", raw, 0x5548, 1 << 22)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(raw)
            observed = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(observed["set_bits"], [0, 31])
            self.assertTrue(observed["message_latch"])
            self.assertIsNone(observed["selected_world_local_zero"])
            self.assertEqual(path.read_bytes(), raw)
            for bad in (bytes(0x906F0), raw[:-1]):
                path.write_bytes(bad)
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)

    def test_embedded_map_reproduction_without_private_save(self):
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(self.native(), mapping["collectible_producers"])
        self.assertNotIn("save_observation", mapping["collectible_producers"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
