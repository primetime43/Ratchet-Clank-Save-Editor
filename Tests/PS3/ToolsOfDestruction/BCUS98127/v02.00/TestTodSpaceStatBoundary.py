"""Named runtime space statistics must not be synthesized from saved progress."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSpaceStatBoundary.py"))
ELF = SAVE = None


def runtime():
    return {offset: 0 for offset in (0xFC, 0x120, 0x124, 0x128, 0x130, 0x134, 0x138, 0x13C)}


class SpaceStatBoundaryChecks(unittest.TestCase):
    def native(self, save=None):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF, save)

    def test_direct_words_and_signed_public_result(self):
        for identifier, offset in ((0, 0x120), (1, 0x124), (2, 0x128), (5, 0x138), (6, 0x13C)):
            for raw in (0, 123, 0x80000000, 0xFFFFFFFF):
                observed = runtime(); observed[offset] = raw
                result = TOOL["stat_preview"](identifier, observed)
                self.assertEqual(result["native_raw32"], raw)
                self.assertEqual(result["lua_signed_result"], raw if raw < 0x80000000 else raw - (1 << 32))

    def test_pending_count_includes_high_bits(self):
        for mask in (0, 1, 0x80000000, 0xFFFFFFFF, 0xAABBCCDD):
            observed = runtime(); observed[0xFC] = mask
            self.assertEqual(TOOL["stat_preview"](3, observed)["native_raw32"], mask.bit_count())

    def test_pending_empty_predicate_is_not_saved_completion(self):
        for mask in (0, 1, 0x80000000, 0xFFFFFFFF):
            observed = runtime(); observed[0xFC] = mask
            self.assertEqual(TOOL["stat_preview"](7, observed)["native_raw32"], int(mask == 0))

    def test_ratio_zero_denominator_and_no_hundred_cap(self):
        observed = runtime(); observed[0x134] = 0xFFFFFFFF
        self.assertEqual(TOOL["stat_preview"](4, observed)["native_raw32"], 0)
        for numerator, denominator, expected in ((1, 2, 50), (3, 4, 75), (2, 1, 200), (100, 1, 10000)):
            observed[0x134], observed[0x130] = numerator, denominator
            self.assertEqual(TOOL["stat_preview"](4, observed)["native_raw32"], expected)

    def test_ratio_float32_rounding_and_low32_return(self):
        observed = runtime(); observed[0x134] = 0xFFFFFFFF; observed[0x130] = 1
        self.assertEqual(TOOL["stat_preview"](4, observed)["native_raw32"], 0)
        observed[0x130] = 0x7FFFFFFF
        self.assertEqual(TOOL["stat_preview"](4, observed)["native_raw32"], 200)

    def test_unsigned_invalid_native_selectors_return_zero(self):
        for identifier in (8, 100, 0x80000000, 0xFFFFFFFF):
            self.assertEqual(TOOL["stat_preview"](identifier, runtime())["native_raw32"], 0)

    def test_explicit_runtime_observations_and_raw_types_required(self):
        for invalid in (-1, 1 << 32, True, 1.0, None, "0"):
            with self.assertRaises(ValueError): TOOL["stat_preview"](invalid, runtime())
            observed = runtime(); observed[0xFC] = invalid
            with self.assertRaises(ValueError): TOOL["stat_preview"](3, observed)
        for invalid in (None, {}, {0x8728: 0}, [0] * 8):
            with self.assertRaises(ValueError): TOOL["stat_preview"](3, invalid)

    def test_preview_keeps_input_immutable_and_disclaims_saved_stats(self):
        observed = runtime(); observed[0xFC] = 0xFFFFFFFF; before = observed.copy()
        result = TOOL["stat_preview"](3, observed)
        self.assertEqual(observed, before)
        self.assertIn("not saved data", result["scope"])
        self.assertIn("not live FPSCR", result["scope"])

    def test_named_apis_dispatch_guards_and_outside_save_root(self):
        report = self.native()
        self.assertEqual(len(report["instruction_guards"]), 89)
        self.assertEqual(report["named_getter"]["name"], "get_space_stat")
        self.assertEqual(report["named_reset"]["name"], "space_combat_reset")
        self.assertGreater(int(report["named_getter"]["runtime_root"], 0), 0x101EFB20 + 0x906F0)
        self.assertEqual(len(report["numeric_stat_catalog"]), 8)
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)

    def test_reset_footprint_and_saved_increment_order_are_qualified(self):
        report = self.native()
        self.assertEqual(report["named_reset"]["explicit_zero_word_offsets"], [hex(a) for a in range(0x120, 0x14C, 4)])
        self.assertIn("not proof of final preservation", report["named_reset"]["rule"])
        self.assertIn("first calls", report["saved_boundary"]["rule"])
        self.assertIn("No deaths/kills/retries", report["saved_boundary"]["rule"])

    def test_pointer_relative_table_reset_and_call_tamper_refused(self):
        self.native(); cls = TOOL["BINDINGS"]["Elf"]; original = cls.u32
        for target in (0x888658, 0x898F5C, 0x8A1C70, 0x3619E4, 0x361FB0, 0x36FCE0, 0x36FCEC, 0x8A1A58):
            def changed(instance, address):
                return original(instance, address) ^ (4 if address == target else 0)
            with patch.object(cls, "u32", changed), self.assertRaises(ValueError): TOOL["inspect"](ELF)

    def test_actual_zero_save_does_not_synthesize_runtime_zero(self):
        if SAVE is None: self.skipTest("Pass --save")
        before = hashlib.sha256(SAVE.read_bytes()).hexdigest()
        observation = self.native(SAVE)["save_observation"]
        self.assertEqual(set(observation["saved_words"].values()), {"00000000"})
        self.assertIsNone(observation["runtime_statistics"])
        self.assertIsNone(observation["runtime_pending"])
        self.assertEqual(hashlib.sha256(SAVE.read_bytes()).hexdigest(), before)

    def test_synthetic_saved_high_words_and_opaque_neighbors_preserved(self):
        self.native(); raw = bytearray(0x906F0)
        for i in range(32): struct.pack_into(">I", raw, i * 20, i)
        for offset in (0x8728, 0x872C, 0x8730): struct.pack_into(">I", raw, offset, 0xFFFFFFFF)
        raw[0x8718:0x8720] = bytes.fromhex("1122334455667788")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "fixture.bin"; path.write_bytes(raw)
            observation = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(set(observation["saved_words"].values()), {"FFFFFFFF"})
            self.assertIsNone(observation["runtime_statistics"])
            self.assertEqual(path.read_bytes(), raw)
            path.write_bytes(raw[:-1])
            with self.assertRaises(ValueError): TOOL["inspect"](ELF, path)

    def test_embedded_report_reproduces_without_private_snapshot(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(mapping["space_stat_boundary"], report)
        self.assertNotIn("save_observation", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
