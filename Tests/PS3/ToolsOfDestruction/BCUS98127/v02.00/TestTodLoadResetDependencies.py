"""Exact load-reset ammo identity, deferred gates, raw snapshots and synthetic boundaries."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodLoadResetDependencies.py"))
ELF = SAVE = None


class LoadResetDependencyChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_embedded_report_and_all_exact_native_guards(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["load_reset_dependencies"])
        self.assertNotIn("save_observation", mapping["load_reset_dependencies"])
        self.assertEqual(len(report["instruction_guards"]), 49)
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)

    def test_item27_pointer_enum_and_exact_ammo_field(self):
        report = self.native()["ammo_reset"]
        self.assertEqual((report["item_id"], report["enum"], report["request_bits"]), (27, "WPN_GELANATOR", "00000000"))
        self.assertEqual(int(report["record_pointer"], 0) - 0x101EFB20, 27 * 20)
        self.assertEqual(int(report["ammo_offset"], 0), 27 * 20 + 8)
        self.assertIn("does not read old ammo", report["rule"])
        self.assertIn("not an unconditional raw00000000", report["clamp_limit"])

    def test_gate_plan_replay_precedes_any_nonzero_latch_and_no_saved_latch(self):
        for replay in (0, 1, 3, 0x80000000, 0xFFFFFFFF):
            for latch in (0, 1, 2, 0x80000000, 0xFFFFFFFF):
                plan = TOOL["gate_refresh_plan"](replay, latch)
                refresh = replay == 0 and latch != 0
                self.assertEqual(plan["saved_gate_offsets"], ["0x874C", "0x8750"] if refresh else [])
                self.assertEqual(plan["explicit_latch_after"], 0 if refresh else latch)
                self.assertEqual(plan["branch"], "replay bypass" if replay else "refresh" if refresh else "no refresh")
                self.assertIn("absent from GAME.SAV", plan["qualification"])

    def test_finite_zero_request_retains_negative_maximum_and_signed_zero_cases(self):
        for maximum in (0, 0x80000000, 0x3F800000, 0xBF800000, 1, 0x80000001, 0x7F7FFFFF, 0xFF7FFFFF):
            result = TOOL["finite_zero_ammo_preview"](maximum)
            expected = maximum if maximum in (0, 0x80000000, 0xBF800000, 0x80000001, 0xFF7FFFFF) else 0
            self.assertEqual(result["result_bits"], expected)
            self.assertIn("not current definitions", result["qualification"])

    def test_invalid_words_and_nonfinite_maximum_are_not_simulated(self):
        for bad in (-1, 1 << 32, True, 1.0, "0", None):
            with self.assertRaises(ValueError):
                TOOL["finite_zero_ammo_preview"](bad)
            for slot in (0, 1):
                args = [0, 0]
                args[slot] = bad
                with self.assertRaises(ValueError):
                    TOOL["gate_refresh_plan"](*args)
        for bits in (0x7FC12345, 0x7F800000, 0xFF800000, 0x7F800001):
            with self.assertRaises(ValueError):
                TOOL["finite_zero_ammo_preview"](bits)

    def test_pointer_call_store_constant_and_toc_tampering_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0x8A689C, 0x8A68A0, 0x89F078, 0x89F07C, 0x2CDBB8, 0x2CE0FC,
                        0x2CE28C, 0x2CE284, 0x2CE288, 0x489FFC, 0x465DFC, 0x88B3C4):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (4 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)
        for function in (0x489F68, 0x465DC0, 0x463DE0, 0x2CDBB0, 0x2CE0D0, 0x2CDC00, 0x2CDC30, 0x2D1860):
            with patch.dict(elf.descriptors, {function: 0x88FF38}):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_gate_provenance_order_and_snapshot_do_not_invent_latch_units_or_defaults(self):
        report = self.native()["deferred_gate_refresh"]
        self.assertEqual(int(report["latch_va"], 0), 0x101E8D70 + 0x54)
        self.assertIn("does not directly reset", report["arm_rule"])
        self.assertIn("ANY nonzero", report["consume_rule"])
        self.assertIn("then2CE28C clears", report["consume_rule"])
        self.assertIn("not a promised raw-bit copy", report["consume_rule"])
        self.assertIn("cannot be inferred", report["order_limit"])
        self.assertIn("do not prove defaults, seconds", report["snapshot_limit"])

    def test_actual_save_snapshot_and_unchanged_input_hashes(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)]
        observed = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual((observed["ammo_bits"], observed["ownership"], observed["level"], observed["xp_bits"]), ("00000000", 0, 0, "00000000"))
        self.assertEqual(observed["gate_bits"], ["41200000", "43960000"])
        self.assertEqual(observed["replay_word"], 3)
        self.assertIn("no current maximum", observed["qualification"])
        self.assertEqual(before, [hashlib.sha256(Path(p).read_bytes()).digest() for p in (ELF, SAVE)])

    def test_synthetic_raw_nonfinite_fields_and_opaque_neighbors_preserved(self):
        self.native()
        raw = bytearray([0xA5]) * 0x906F0
        for identifier in range(32):
            struct.pack_into(">I", raw, identifier * 20, identifier)
        struct.pack_into(">I", raw, 0x224, 0x7FC12345)
        struct.pack_into(">2I", raw, 0x874C, 0x80000000, 0xFF800000)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(raw)
            report = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(report["ammo_bits"], "7FC12345")
            self.assertEqual(report["gate_bits"], ["80000000", "FF800000"])
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
