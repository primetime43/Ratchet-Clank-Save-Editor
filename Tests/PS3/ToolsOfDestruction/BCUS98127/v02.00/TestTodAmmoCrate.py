"""CrateAmmo producer, separate admission, finite request and immutable observations."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodAmmoCrate.py"))
ELF = SAVE = ASSETS = None


def bits(value):
    return struct.unpack(">I", struct.pack(">f", value))[0]


class AmmoCrateChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def preview(self, maximum, ammo, crate, factor, item=1):
        return TOOL["request_preview"](*(bits(v) for v in (maximum, ammo, crate, factor)), item)

    def test_native_reproduction_guards_and_no_private_observation(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["ammo_crate"])
        self.assertNotIn("save_observation", report)
        self.assertEqual(len(report["instruction_guards"]), 88)
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)

    def test_distinct_named_crate_array_and_canonical_record_selection(self):
        report = self.native()
        self.assertIn("CrateAmmo", report["crate_property"])
        self.assertIn("data+2D0+4*index", report["crate_property"])
        self.assertIn("supplies index0, not the saved level", report["crate_property"])
        self.assertIn("distinct from MaxAmmo", report["crate_property"])
        self.assertIn("canonical101EFB20", report["record_selection"])
        self.assertIn("saved20*i+8", report["record_selection"])

    def test_request_missing_capacity_zero_and_negative_scaled_values(self):
        for ammo, crate, factor, expected in ((80, 15, 1, 15), (98, 15, 1, 2), (100, 15, 1, 0),
                                              (80, -15, 1, 0), (80, 15, -1, 0), (80, 0, 1, 0)):
            self.assertEqual(self.preview(100, ammo, crate, factor)["add_request_bits"], f"{bits(expected):08X}")

    def test_fractional_request_is_not_floored_to_one_and_ceiling_is_later(self):
        plan = self.preview(100, 99.75, 15, 1)
        self.assertEqual(plan["add_request_bits"], f"{bits(0.25):08X}")
        self.assertEqual(plan["post_add_local_value"], 1)
        self.assertIn("AFTER465E18", plan["qualification"])
        self.assertEqual(self.preview(100, 80, 0.25, 1)["add_request_bits"], f"{bits(0.25):08X}")

    def test_over_capacity_direct_invocation_can_request_negative_addition(self):
        plan = self.preview(100, 100.25, 15, 1)
        self.assertEqual(plan["add_request_bits"], f"{bits(-0.25):08X}")
        self.assertEqual(plan["post_add_local_value"], 0)
        self.assertIn("no local floor1", self.native()["request_rule"].lower())

    def test_binary32_product_and_subtraction_round_before_selection(self):
        plan = self.preview(100, 50, 15, 0.1)
        expected = TOOL["CAPACITY"]["rounded"](15 * TOOL["CAPACITY"]["finite_bits"](bits(0.1)))
        self.assertEqual(plan["scaled_crate_bits"], f"{bits(expected):08X}")
        self.assertEqual(plan["missing_bits"], f"{bits(50):08X}")
        self.assertEqual(plan["post_add_local_value"], 2)

    def test_ravager_exception_and_other_ids_ceiling_positive_and_negative(self):
        for amount in (-1.25, -0.25, 0, 0.25, 1.25, 2):
            for item in range(32):
                # A negative missing selects the negative request; positive missing permits a positive crate request.
                plan = self.preview(10, 10-amount, max(amount, 0), 1, item)
                expected = amount if item == 3 else math.ceil(amount)
                self.assertEqual(plan["post_add_local_value"], expected)
        self.assertIn("WPN_RAVAGER", self.native()["post_add_rounding"])

    def test_below_capacity_ordered_predicate_equality_and_unordered(self):
        for ammo, maximum, expected in ((bits(1)-1, bits(1), True), (bits(1), bits(1), False),
                                       (bits(1)+1, bits(1), False), (0x7FC12345, bits(1), False),
                                       (bits(1), 0x7F800001, False), (bits(1), 0x7F800000, True),
                                       (0xFF800000, bits(1), True), (0, 0x80000000, False)):
            self.assertEqual(TOOL["below_capacity_predicate"](ammo, maximum)["passes_ordered_below_capacity"], expected)
        self.assertIn("does not read ownership or invoke2FF6C0", self.native()["below_capacity"])

    def test_flag2_acquisition_and_later_ui_gate_are_after_ammo(self):
        rule = self.native()["later_publication"]
        self.assertIn("refill0", rule)
        self.assertIn("even after an earlier request0", rule)
        self.assertIn("AFTER the ammo/acquisition work", rule)
        self.assertIn("not an ammo rollback", rule)

    def test_nonfinite_overflow_large_rounding_and_invalid_raw_inputs_refused(self):
        for bad in (-1, 1 << 32, True, "0", None, 0x7F800000, 0x7F800001, 0xFF800000):
            for slot in range(4):
                args = [bits(100), bits(0), bits(15), bits(1), 1]
                args[slot] = bad
                with self.assertRaises(ValueError):
                    TOOL["request_preview"](*args)
        for bad in (-1, 32, True, "1", 1.0, None):
            with self.assertRaises(ValueError):
                TOOL["request_preview"](bits(100), 0, bits(15), bits(1), bad)
        with self.assertRaises(ValueError):
            self.preview(3e38, -3e38, 1, 1)
        with self.assertRaises(ValueError):
            self.preview(100, 0, 1e38, 1e38)
        with self.assertRaises(ValueError):
            self.preview(1e20, 0, 1e20, 1)

    def test_native_call_identity_branch_pointer_and_toc_tampering_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0x2FF774, 0x2FF7C4, 0x2FF7DC, 0x2FF7F0, 0x2FF7FC,
                        0x2FF80C, 0x2FFAAc, 0x466530, 0xB86DC, 0x89FF00,
                        0x84E24C, 0x88E858, 0x2FF694):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (4 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)
        for function in (0x2FF6C0, 0x2FF5F0, 0x466528, 0xB8618):
            with patch.dict(elf.descriptors, {function: 0}):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_reference_crate_values_native_ids_and_missing_values_are_not_defaults(self):
        self.native()
        if ASSETS is None:
            self.skipTest("Pass --assets")
        observed = TOOL["inspect"](ELF, assets_path=ASSETS)["asset_observation"]
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(observed, mapping["ammo_crate_assets"])
        catalog = observed["catalog"]
        self.assertEqual([row["id"] for row in catalog], list(range(32)))
        self.assertEqual((catalog[1]["config"], catalog[1]["crate_ammo_level0"]), ("Combuster", 15))
        self.assertIsNone(catalog[31]["crate_ammo_level0"])
        with patch.dict(TOOL["CONFIGS"]["REFERENCE_HASHES"], {"weapon.csv": "0" * 64}):
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF, assets_path=ASSETS)

    def test_actual_save_records_hashes_and_no_runtime_history_inferred(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observed = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(len(observed["records"]), 32)
        self.assertEqual(observed["records"][1]["ammo_bits"], f"{bits(100):08X}")
        self.assertNotIn("runtime_factor", observed)
        self.assertNotIn("pickup_count", observed)
        self.assertIn("invocation history", observed["qualification"])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])

    def test_synthetic_raw_nonfinite_ammo_high_level_mask_and_tail_preserved(self):
        self.native()
        raw = bytearray([0xA5]) * 0x906F0
        for i in range(32):
            struct.pack_into(">I", raw, i*20, i)
        struct.pack_into(">II", raw, 28, 0x7F800001, 0xFFFFFFFF)
        raw[36:40] = bytes.fromhex("FEFFABCD")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(raw)
            row = TOOL["inspect"](ELF, path)["save_observation"]["records"][1]
            self.assertEqual((row["ammo_bits"], row["mask_bits"], row["ownership"], row["stored_level"], row["opaque_tail"]),
                             ("7F800001", "FFFFFFFF", 254, 255, "ABCD"))
            self.assertEqual(path.read_bytes(), raw)
            for bad in (raw[:-1], bytes(0x906F0)):
                path.write_bytes(bad)
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--assets", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE, ASSETS = args.elf, args.save, args.assets
    unittest.main(argv=[__file__] + remaining)
