"""Exact ammo-capacity provenance, synthetic arithmetic and qualified asset/save checks."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodAmmoCapacity.py"))
ELF = SAVE = ASSETS = None


def bits(value):
    return struct.unpack(">I", struct.pack(">f", value))[0]


def node(value, attribute=9, kind=0):
    return {"attribute": attribute, "kind": kind, "value_bits": bits(value)}


class AmmoCapacityChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_report_reproduction_and_complete_native_guards(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["ammo_capacity"])
        self.assertNotIn("save_observation", mapping["ammo_capacity"])
        self.assertEqual(len(report["instruction_guards"]), 35)
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)

    def test_all_saved_level_bytes_have_unclamped_address_plans(self):
        for level in range(256):
            plan = TOOL["level_address_plan"](level)
            self.assertEqual(plan["data_offset"], 0x280 + 4 * level)
            self.assertEqual(plan["within_declared_20_slots"], level < 20)
        self.assertEqual(TOOL["level_address_plan"](255)["data_offset"], 0x67C)
        self.assertIn("public indexed-property check does not protect", self.native()["saved_inputs"]["index_limit"])

    def test_absolute_additions_are_scaled_by_sum_of_percentages_not_compounded(self):
        result = TOOL["modifier_preview"](bits(10), 7, 9, [node(.25, kind=1), node(2), node(.25, kind=2)])
        self.assertEqual(result["result_bits"], bits(18))
        self.assertNotEqual(result["result_bits"], bits(18.75))
        self.assertEqual(result["absolute_indices"], [1])
        self.assertEqual(result["percentage_indices"], [0, 2])

    def test_exact_attribute_and_mask_selection_including_node_zero(self):
        result = TOOL["modifier_preview"](bits(10), 0b1101, 9,
                                           [node(2), node(999), node(999, attribute=8), node(.5, kind=0xFFFFFFFF)])
        self.assertEqual(result["result_bits"], bits(18))
        self.assertEqual(result["absolute_indices"], [0])
        self.assertEqual(result["percentage_indices"], [3])

    def test_single_precision_rounding_occurs_after_each_add(self):
        result = TOOL["modifier_preview"](bits(2 ** 24), 3, 9, [node(1), node(1)])
        self.assertEqual(result["result_bits"], bits(2 ** 24))
        self.assertNotEqual(result["result_bits"], bits(2 ** 24 + 2))
        result = TOOL["modifier_preview"](bits(1), 3, 9, [node(2 ** -24, kind=1), node(2 ** -24, kind=1)])
        self.assertEqual(result["result_bits"], bits(1))

    def test_negative_factor_and_absolute_values_are_not_clamped(self):
        self.assertEqual(TOOL["modifier_preview"](bits(10), 1, 9, [node(-2, kind=1)])["result_bits"], bits(-10))
        self.assertEqual(TOOL["modifier_preview"](bits(10), 1, 9, [node(-12)])["result_bits"], bits(-2))

    def test_empty_and_high_mask_bits_do_not_become_repairs(self):
        self.assertEqual(TOOL["modifier_preview"](0x80000000, 0xFFFFFFFF, 9, [])["result_bits"], 0x80000000)
        nodes = [node(2)] * 24
        self.assertEqual(TOOL["modifier_preview"](bits(10), 1 << 31, 9, nodes)["result_bits"], bits(10))
        self.assertEqual(TOOL["modifier_preview"](bits(10), 1 << 23, 9, nodes)["absolute_indices"], [23])
        self.assertIn("still performs fmuls", self.native()["modifier_order"]["empty_rule"])

    def test_strict_inputs_and_nonfinite_or_overflow_values_are_refused(self):
        for bad in (-1, 256, True, "9", 1.0, None):
            with self.assertRaises(ValueError):
                TOOL["level_address_plan"](bad)
        for bad in (-1, 1 << 32, True, 1.0, "0", None):
            for argument in range(3):
                args = [bits(1), 0, 9, []]
                args[argument] = bad
                with self.assertRaises(ValueError):
                    TOOL["modifier_preview"](*args)
        for bad in (None, {}, [node(1)] * 25, [{"attribute": 9}], [node(1) | {"extra": 0}]):
            with self.assertRaises(ValueError):
                TOOL["modifier_preview"](bits(1), 0, 9, bad)
        for bad in (0x7FC12345, 0x7F800000, 0xFF800000, 0x7F800001):
            with self.assertRaises(ValueError):
                TOOL["modifier_preview"](bad, 0, 9, [])
            with self.assertRaises(ValueError):
                TOOL["modifier_preview"](bits(1), 1, 9, [{"attribute": 9, "kind": 0, "value_bits": bad}])
        with self.assertRaises(ValueError):
            TOOL["modifier_preview"](0x7F7FFFFF, 1, 9, [{"attribute": 9, "kind": 0, "value_bits": 0x7F7FFFFF}])

    def test_call_tail_branch_constant_field_and_toc_tampering_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0x463E08, 0x463E04, 0x466510, 0x466520, 0x466260, 0x4662C4,
                        0x4662D0, 0x4662E0, 0x8A5F00, 0x463DFC, 0x463E0C, 0x466524):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (1 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)
        for function in (0x463DE0, 0x466500, 0x466258):
            with patch.dict(elf.descriptors, {function: 0x88FF38}):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_qualified_original_assets_and_save_comparison(self):
        self.native()
        if ASSETS is None or SAVE is None:
            self.skipTest("Pass --assets and --save")
        parser = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWeaponConfigs.py"))
        configs = parser["inspect"](ASSETS)
        self.assertTrue(configs["reference_assets_match"])
        raw = SAVE.read_bytes()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        matches = []
        for entry in mapping["weapon_configuration"]["inventory_catalog"]:
            identifier = entry["id"]
            if not 1 <= identifier <= 15:
                continue
            config = configs["weapons"][entry["config_name"]]
            level = raw[identifier * 20 + 17]
            self.assertEqual(level, 9)
            nodes = [node(n["runtime_value"] or 0, 9 if n["type"] == "MOD_AMMO" else 0, int(n["is_percent"]))
                     for n in config["modifiers"]]
            mask = struct.unpack_from(">I", raw, identifier * 20 + 12)[0]
            result = TOOL["modifier_preview"](bits(config["variables"]["MaxAmmo"][level]), mask, 9, nodes)
            observed = struct.unpack_from(">I", raw, identifier * 20 + 8)[0]
            if observed == result["result_bits"]:
                matches.append(identifier)
            else:
                self.assertEqual(identifier, 15)
                self.assertEqual(result["result_bits"], bits(900))
                self.assertLess(TOOL["finite_bits"](observed), 900)
            self.assertIn("not a runtime maximum", result["qualification"])
        self.assertEqual(matches, list(range(1, 15)))

    def test_original_snapshot_has_only_raw_inputs_and_unchanged_hashes(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observed = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(len(observed["records"]), 32)
        self.assertEqual(observed["records"][2]["mask_bits"], "000007FE")
        self.assertEqual(observed["records"][2]["ammo_bits"], "41200000")
        self.assertNotIn("maximum", observed["records"][2])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])

    def test_unusual_level_mask_and_nan_ammo_are_preserved_not_resolved(self):
        self.native()
        raw = bytearray([0xA5]) * 0x906F0
        for identifier in range(32):
            struct.pack_into(">I", raw, identifier * 20, identifier)
        raw[17] = 255
        struct.pack_into(">2I", raw, 8, 0x7FC12345, 0xFFFFFFFF)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(raw)
            record = TOOL["inspect"](ELF, path)["save_observation"]["records"][0]
            self.assertEqual(record["ammo_bits"], "7FC12345")
            self.assertEqual(record["mask_bits"], "FFFFFFFF")
            self.assertEqual(record["address_plan"]["data_offset"], 0x67C)
            self.assertFalse(record["address_plan"]["within_declared_20_slots"])
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
