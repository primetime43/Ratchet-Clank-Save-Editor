"""Named query visibility, finite FLOOR, one-based levels and qualified removal requests."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodInventoryQueries.py"))
ELF = SAVE = None


def bits(value):
    return struct.unpack(">I", struct.pack(">f", value))[0]


class InventoryQueryChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_native_reproduction_and_original_guards(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["inventory_queries"])
        self.assertEqual(len(report["instruction_guards"]), 89)
        self.assertNotIn("save_observation", report)
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)

    def test_named_ownership_and_attributes_have_distinct_rules(self):
        report = self.native()
        self.assertEqual({a["name"] for a in report["named_apis"]},
                         {"is_weapon_owned", "get_weapon_ammo", "get_weapon_level", "hero_has_weapon"})
        self.assertIn("normalized0/1", report["ownership"])
        self.assertIn("does not resolve definitions", report["ownership"])
        self.assertIn("owned can be true", report["visible_attributes"])
        self.assertIn("owned false while flag2 exposes", report["visible_attributes"])

    def test_every_ownership_byte_and_low_flag_combination(self):
        for owner in range(256):
            for flags in range(16):
                plan = TOOL["query_preview"](owner, flags, 9, bits(2.75))
                visible = (owner != 0 or bool(flags & 2)) and not flags & 1
                self.assertEqual(plan["ownership_predicate"], owner != 0)
                self.assertEqual(plan["ammo_level_visible"], bool(visible))
                self.assertEqual(plan["script_ammo_reference"], 2 if visible else 0)
                self.assertEqual(plan["script_level_reference"], 10 if visible else 0)
        self.assertTrue(TOOL["query_preview"](0, 0x80000002, 0, bits(1))["ammo_level_visible"])
        self.assertFalse(TOOL["query_preview"](255, 0xFFFFFFFF, 9, bits(1))["ammo_level_visible"])

    def test_positive_and_negative_fractional_ammo_floor_not_ceiling(self):
        for sample, expected in ((0.25, 0), (1.25, 1), (2, 2), (-0.25, -1), (-1.25, -2), (-2, -2), (749.0493, 749)):
            self.assertEqual(TOOL["query_preview"](1, 0, 9, bits(sample))["script_ammo_reference"], expected)
        self.assertEqual(TOOL["query_preview"](1, 0, 0, 0x80000000)["script_ammo_reference"], 0)
        self.assertIn("not nearest rounding, ceiling, clamping", self.native()["ammo_rounding"])

    def test_all_raw_level_bytes_are_one_based_only_when_visible(self):
        for level in range(256):
            self.assertEqual(TOOL["query_preview"](1, 0, level, 0)["script_level_reference"], level+1)
            self.assertEqual(TOOL["query_preview"](0, 2, level, 0)["script_level_reference"], level+1)
            self.assertEqual(TOOL["query_preview"](1, 1, level, 0)["script_level_reference"], 0)
        self.assertIn("raw255 becomes256", self.native()["level_numbering"])

    def test_hidden_nonfinite_ammo_skips_conversion_but_visible_preview_refuses_it(self):
        for sample in (0x7F800001, 0x7FC12345, 0x7F800000, 0xFF800000):
            self.assertEqual(TOOL["query_preview"](0, 0, 9, sample)["script_ammo_reference"], 0)
            self.assertEqual(TOOL["query_preview"](1, 1, 9, sample)["script_ammo_reference"], 0)
            with self.assertRaises(ValueError):
                TOOL["query_preview"](1, 0, 9, sample)
        with self.assertRaises(ValueError):
            TOOL["query_preview"](1, 0, 9, bits(1e20))

    def test_handle_diagnostics_are_not_invented_terminal_rejection(self):
        rule = self.native()["handle_ownership"]
        self.assertIn("call24F9D8 then CONTINUE", rule)
        self.assertIn("resolves the handle repeatedly", rule)
        self.assertIn("Later type211/nonnull-save gates do return0", rule)
        self.assertIn("Lua1 is result count", rule)

    def test_every_owned_byte_selects_requests_and_zero_skips(self):
        for owner in range(256):
            plan = TOOL["removal_request_plan"](owner, 46)
            self.assertEqual(plan["setter_requests"], ["XP+0", "absolute ammo+0"] if owner else [])
            self.assertEqual(plan["explicit_ownership_store"], 0 if owner else None)
            self.assertEqual(plan["explicit_counter_store_bits"], "0000002D" if owner else None)

    def test_decrement_wraps_supplied_post_helper_sample_without_underflow_clamp(self):
        for counter, expected in ((0, "FFFFFFFF"), (1, "00000000"), (0x80000000, "7FFFFFFF"), (0xFFFFFFFF, "FFFFFFFE")):
            plan = TOOL["removal_request_plan"](255, counter)
            self.assertEqual(plan["explicit_counter_store_bits"], expected)
            self.assertIn("post-helper sample", plan["qualification"])
        rule = self.native()["removal_leaf"]["ordered_rule"]
        self.assertIn("Only AFTER both helpers", rule)
        self.assertIn("not a raw first18-byte reset", rule)

    def test_removal_reachability_is_unresolved_and_no_extra_stores_claimed(self):
        leaf = self.native()["removal_leaf"]
        self.assertEqual(leaf["static_descriptor_references"], [])
        self.assertEqual(leaf["static_direct_branch_sites"], [])
        self.assertIn("does not prove unused/dead code", leaf["scope"])
        self.assertIn("No direct modifier-mask, unlock, quick-select or opaque-tail store", leaf["scope"])
        self.assertIn("No caller or gameplay invocation is established", leaf["scope"])

    def test_invalid_raw_inputs_refused_without_mutation(self):
        for bad in (-1, 256, True, "1", 1.0, None):
            for slot in (0, 2):
                args = [1, 0, 9, bits(1)]
                args[slot] = bad
                with self.assertRaises(ValueError):
                    TOOL["query_preview"](*args)
            with self.assertRaises(ValueError):
                TOOL["removal_request_plan"](bad, 0)
        for bad in (-1, 1 << 32, True, "0", 0.0, None):
            for slot in (1, 3):
                args = [1, 0, 9, bits(1)]
                args[slot] = bad
                with self.assertRaises(ValueError):
                    TOOL["query_preview"](*args)
            with self.assertRaises(ValueError):
                TOOL["removal_request_plan"](1, bad)

    def test_pointer_flag_rounding_call_counter_and_toc_tampering_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for va in (0x89F1B8, 0x25908, 0x25954, 0x25978, 0x27690, 0x28B2F0,
                   0x466B24, 0x466B28, 0x466B38, 0x466B48, 0x466B4C, 0x874B00):
            with patch.object(elf, "u32", side_effect=lambda address, target=va: original(address) ^ (4 if address == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)
        for function in (0x258C0, 0x27608, 0x2D1C10, 0x466AE8):
            with patch.dict(elf.descriptors, {function: 0}):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_actual_save_count_and_raw_fraction_are_not_query_or_removal_history(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observed = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(observed["nonzero_ownership_records"], 25)
        self.assertEqual(observed["raw_acquisition_counter_bits"], "0000002E")
        self.assertEqual(observed["records"][1]["stored_level"], 9)
        self.assertNotIn("script_level", observed["records"][1])
        self.assertNotIn("removal_count", observed)
        self.assertIn("removal history are not recovered", observed["qualification"])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])

    def test_synthetic_unknown_owner_level_nonfinite_and_opaque_tail_preserved(self):
        self.native()
        raw = bytearray([0xA5]) * 0x906F0
        for i in range(32):
            struct.pack_into(">I", raw, i*20, i)
        struct.pack_into(">I", raw, 28, 0x7F800001)
        raw[36:40] = bytes.fromhex("FEFFABCD")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(raw)
            row = TOOL["inspect"](ELF, path)["save_observation"]["records"][1]
            self.assertEqual((row["ownership"], row["stored_level"], row["ammo_bits"], row["opaque_tail"]), (254, 255, "7F800001", "ABCD"))
            self.assertEqual(path.read_bytes(), raw)
            for bad in (raw[:-1], bytes(0x906F0)):
                path.write_bytes(bad)
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
