"""Exact-build weapon purchase checks; supplied previews never execute purchases."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWeaponPurchase.py"))
ELF = SAVE = None


class WeaponPurchaseChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_gate_requires_exactly_level_four(self):
        for level in range(256):
            result = TOOL["level_five_gate_preview"](1, level, 3, 0, 9)
            self.assertEqual(result["gate"], level == 4)

    def test_ownership_is_nonzero_not_one(self):
        for ownership in range(256):
            self.assertEqual(TOOL["level_five_gate_preview"](ownership, 4, 1, 0, 9)["gate"], ownership != 0)

    def test_replay_is_raw_nonzero_not_a_counter_bound(self):
        for word in (0, 1, 3, 4, 0x80000000, 0xFFFFFFFF):
            self.assertEqual(TOOL["level_five_gate_preview"](2, 4, word, 0, 9)["gate"], word != 0)

    def test_flags_and_num_levels_are_separate_from_bridge(self):
        for flags in (0, 1, 2, 3, 4, 0x80000000, 0xFFFFFFFF):
            for levels in (0, 4, 5, 6, 9, 20, 0xFFFFFFFF):
                result = TOOL["level_five_gate_preview"](1, 4, 1, flags, levels)
                self.assertEqual(result["gate"], flags & 3 == 0 and levels > 5)
        self.assertFalse(TOOL["level_five_gate_preview"](1, 4, 1, 0, 5)["gate"])

    def test_dispatch_false_selects_normal_not_rejection(self):
        for second in (0, 1, 255):
            result = TOOL["route_preview"](0, second)
            self.assertEqual(result["selected_path"], "normal acquisition")
            self.assertFalse(result["second_gate_evaluated"])

    def test_repeat_gate_failure_has_no_normal_fallback(self):
        for first in (1, 2, 255):
            result = TOOL["route_preview"](first, 0)
            self.assertEqual(result["selected_path"], "level-five")
            self.assertTrue(result["second_gate_evaluated"])
            self.assertFalse(result["level_five_gate_admitted"])
            self.assertFalse(result["fallback_after_second_gate_failure"])
            self.assertTrue(TOOL["route_preview"](first, 255)["level_five_gate_admitted"])

    def test_funds_comparison_and_negation_are_signed_low32(self):
        for wallet, cost, admits in ((10, 10, True), (9, 10, False),
                                     (0x80000000, 0, False), (0, 0xFFFFFFFF, True),
                                     (0xFFFFFFFF, 0xFFFFFFFF, True), (0xFFFFFFFF, 1, False)):
            result = TOOL["signed_funds_preview"](wallet, cost)
            self.assertEqual(result["funds_comparison_admits"], admits)
            self.assertEqual(result["negated_cost_low32"], (-cost) & 0xFFFFFFFF)

    def test_preview_types_and_bounds_rejected(self):
        for bad in (-1, True, 1.0, "1", 0x100000000):
            with self.assertRaises(ValueError):
                TOOL["signed_funds_preview"](bad, 1)
            with self.assertRaises(ValueError):
                TOOL["level_five_gate_preview"](1, 4, bad, 0, 9)
        for bad in (-1, True, 1.0, 256):
            with self.assertRaises(ValueError):
                TOOL["route_preview"](bad, 0)
            with self.assertRaises(ValueError):
                TOOL["level_five_gate_preview"](1, bad, 1, 0, 9)

    def test_guard_ranges_replay_exact_bytes(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        self.assertEqual(len(report["instruction_guards"]), 115)
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)

    def test_native_report_retains_order_and_limits(self):
        report = self.native()
        self.assertIn("exactly stored level4", report["level_five_gate"]["rule"])
        self.assertIn("requires>5", report["level_five_gate"]["contrast"])
        self.assertIn("without falling back", report["routing"]["purchase_rule"])
        order = report["level_five_transaction"]["order"]
        self.assertIn("stores level5", order[4])
        self.assertIn("update bolts", order[5])
        self.assertIn("already-owned", report["normal_transaction"]["repeat_scope"])
        self.assertIn("low-byte24F7B8(hero,11)==0", report["normal_transaction"]["admission"])

    def test_changed_instruction_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0x2D2190, 0x2D2240, 0x26660, 0x465ED4):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (1 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_synthetic_snapshot_preserves_opaque_float_bits(self):
        self.native()
        raw = bytearray(0x906F0)
        for identifier in range(32):
            struct.pack_into(">I", raw, identifier * 20, identifier)
        raw[0x24] = 255; raw[0x25] = 4; raw[0x26:0x28] = bytes.fromhex("ABCD")
        raw[0x18:0x1C] = bytes.fromhex("7FC12345")
        raw[0x1C:0x20] = bytes.fromhex("FF800000")
        struct.pack_into(">I", raw, 0x906EC, 0xFFFFFFFF)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(raw)
            report = TOOL["inspect"](ELF, path)["save_observation"]
            record = report["records"][1]
            self.assertEqual((record["xp_hex"], record["ammo_hex"]), ("7FC12345", "FF800000"))
            self.assertTrue(record["stored_necessary_gate_passes"])
            self.assertEqual(path.read_bytes(), raw)
            path.write_bytes(bytes(0x906F0))
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF, path)

    def test_actual_inputs_unchanged_and_no_full_eligibility_claim(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)]
        sample = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(sample["replay_word"], 3)
        self.assertEqual(sample["acquisition_counter"], 46)
        self.assertEqual(sum(r["stored_necessary_gate_passes"] for r in sample["records"]), 0)
        self.assertTrue(all(r["stored_level"] == 9 for r in sample["records"][1:16]))
        self.assertIn("Runtime definition", sample["qualification"])
        self.assertEqual(before, [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)])

    def test_reproduces_embedded_map(self):
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(self.native(), mapping["weapon_purchase"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
