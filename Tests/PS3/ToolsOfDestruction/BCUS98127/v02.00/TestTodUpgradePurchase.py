"""Upgrade transaction gates/order, static vendor boundary and preserved raw inputs."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("upgrade_purchase", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodUpgradePurchase.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE, VENDOR = None, None, None
GRID = [[-1,-1,4,11,3,-1,-2], [0,2,7,-1,13,-1,-2], [-2,-1,8,-1,12,5,-2], [-2,-1,6,9,1,10,-2]]


def fixture():
    raw = bytearray(0x906F0)
    for item in range(32):
        struct.pack_into(">I", raw, item*20, item)
    return raw


class SyntheticPurchaseChecks(unittest.TestCase):
    def test_local_admission_equality_and_nonboolean_ownership(self):
        for owner in (1, 2, 255):
            result = TOOL.purchase_admission_preview(True, owner, 100, 100)
            self.assertTrue(result["local_admission"])
            self.assertEqual(result["wallet_leaf_bits"], 0)
        for hero, owner, wallet in ((False, 1, 100), (True, 0, 100), (True, 1, 99)):
            result = TOOL.purchase_admission_preview(hero, owner, wallet, 100)
            self.assertFalse(result["local_admission"])
            self.assertIsNone(result["wallet_leaf_bits"])

    def test_signed_wallet_cost_edges_are_not_unsigned_affordability(self):
        result = TOOL.purchase_admission_preview(True, 1, 0x80000000, 1)
        self.assertFalse(result["local_admission"])
        self.assertEqual(result["signed_wallet"], -(1 << 31))
        result = TOOL.purchase_admission_preview(True, 1, 0, 0xFFFFFFFF)
        self.assertTrue(result["local_admission"])
        self.assertEqual(result["signed_cost"], -1)
        self.assertEqual(result["debit_delta_bits"], 1)
        self.assertEqual(result["wallet_leaf_bits"], 1)
        result = TOOL.purchase_admission_preview(True, 1, 0xFFFFFFF0, 0xFFFFFFEF)
        self.assertTrue(result["local_admission"])
        self.assertEqual(result["wallet_leaf_bits"], 1)
        self.assertIn("synthetic resolved cost", result["warning"])

    def test_repeated_native_gate_can_charge_with_unchanged_mask(self):
        first = TOOL.purchase_admission_preview(True, 1, 1000, 100)
        second = TOOL.purchase_admission_preview(True, 1, first["wallet_leaf_bits"], 100)
        bit = TOOL.modifier_publication_preview(1 << 2, 2, 0x42C80000, 0x42C80000)
        self.assertTrue(first["local_admission"] and second["local_admission"])
        self.assertEqual(second["wallet_leaf_bits"], 800)
        self.assertTrue(bit["already_set"])
        self.assertEqual(bit["new_mask_bits"], 1 << 2)
        self.assertFalse(bit["ammo_store_branch"])

    def test_ammo_refresh_is_non_eq_including_unordered_not_bit_inequality(self):
        cases = [(0x00000000,0x80000000,False), (0x7F800000,0x7F800000,False),
                 (0x3F800000,0x40000000,True), (0x40000000,0x3F800000,True),
                 (0x7FC12345,0x3F800000,True), (0x3F800000,0x7FA12345,True)]
        for old, new, expected in cases:
            result = TOOL.modifier_publication_preview(0, 1, old, new)
            self.assertEqual(result["ammo_store_branch"], expected)
            self.assertEqual(result["new_mask_bits"], 2)
            self.assertIn("NaN exception/payload", result["warning"])
        self.assertEqual(TOOL.modifier_publication_preview(0, 31, 0, 0)["new_mask_bits"], 0x80000000)

    def test_models_reject_unsupported_or_noninteger_inputs(self):
        for bad in (-1, 0x100000000, 1.0, True):
            with self.assertRaises(ValueError):
                TOOL.purchase_admission_preview(True, 1, bad, 100)
        for bad in (-1, 256, True):
            with self.assertRaises(ValueError):
                TOOL.purchase_admission_preview(True, bad, 100, 1)
        with self.assertRaises(ValueError):
            TOOL.purchase_admission_preview(1, 1, 100, 1)
        for node in (-1, 32, 1.0, True):
            with self.assertRaises(ValueError):
                TOOL.modifier_publication_preview(0, node, 0, 0)

    def test_vendor_start_and_special_predicates_are_separate(self):
        before = copy.deepcopy(GRID)
        start = TOOL.vendor_predicate_preview(GRID, 0, 0, 12)
        self.assertTrue(start["can_be_purchased_predicate"])
        self.assertTrue(start["on_select_excludes_start"])
        self.assertTrue(TOOL.vendor_predicate_preview(GRID, 2, 0, 12)["can_be_purchased_predicate"])
        self.assertFalse(TOOL.vendor_predicate_preview(GRID, 1, 0, 12)["can_be_purchased_predicate"])
        special = TOOL.vendor_predicate_preview(GRID, 12, 0, 12)
        self.assertTrue(special["can_be_purchased_predicate"])
        self.assertFalse(special["positive_neighbor_checks_satisfied"])
        self.assertEqual(special["orthogonal_neighbors"], [1, 5, 13])
        self.assertTrue(TOOL.vendor_predicate_preview(GRID, 12, (1<<1)|(1<<5)|(1<<13), 12)["positive_neighbor_checks_satisfied"])
        self.assertEqual(GRID, before)

    def test_vendor_bounds_duplicate_and_missing_node(self):
        for grid in (None, GRID[:3], [[0]*7]*4, [[True]*7]*4):
            with self.assertRaises(ValueError):
                TOOL.vendor_predicate_preview(grid, 2, 0, 12)
        self.assertFalse(TOOL.vendor_predicate_preview(GRID, 31, 0xFFFFFFFF, 12)["node_present"])
        self.assertFalse(TOOL.vendor_predicate_preview(GRID, 31, 0xFFFFFFFF, 12)["can_be_purchased_predicate"])


class ExactPurchaseChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build evidence")

    def test_native_gate_and_exact_publication_order(self):
        report = TOOL.inspect(ELF)
        self.assertEqual(report["saved_fields"]["modifier_mask_member"], "0xc")
        self.assertEqual(report["saved_fields"]["ownership_member"], "0x10")
        self.assertIn("signed32 wallet420", report["admission"]["rule"])
        self.assertEqual(report["publication"]["mask_store_va"], "0x465d4c")
        self.assertEqual(report["publication"]["ammo_store_va"], "0x465d60")
        self.assertEqual(report["publication"]["debit_call_va"], "0x2d2948")
        self.assertIn("OLD maximum", report["publication"]["order"][0])
        self.assertIn("OR selected", report["publication"]["order"][1])
        self.assertIn("ammo+8", report["publication"]["order"][3])
        self.assertIn("negate captured cost", report["publication"]["order"][4])
        self.assertIn("not called by2D2878", report["availability"]["rule"])

    def test_named_wrapper_result_count_and_ignored_runtime_request(self):
        report = TOOL.inspect(ELF)
        self.assertEqual(report["api"]["name"], "purchase_mod")
        self.assertIn("Lua RESULT COUNT", report["api"]["result_boundary"])
        self.assertIn("fctiwz", report["api"]["argument_boundary"])
        self.assertIn("ignores that return", report["runtime_request"]["rule"])
        self.assertIn("not a resolved saved-field", report["runtime_request"]["rule"])
        self.assertIn("not fully reversed", report["runtime_request"]["scope"])
        self.assertEqual(len(report["recommended_annotations"]), 2)

    def test_native_guards_reject_changed_admission_instruction(self):
        report = TOOL.inspect(ELF)
        guards = {int(g["va"],0): bytes.fromhex(g["bytes"]) for g in report["instruction_guards"]}
        self.assertEqual(guards[0x2D28E4], bytes.fromhex("7C03D800"))
        self.assertEqual(guards[0x465D5C], bytes.fromhex("419E0008"))
        self.assertEqual(guards[0x85A8A0], bytes.fromhex("00032B480088FF38"))
        original = TOOL.BINDINGS["Elf"]

        class ChangedInstruction(original):
            def u32(self, address):
                word = super().u32(address)
                return word ^ 0x40 if address == 0x2D28E4 else word

        with patch.dict(TOOL.BINDINGS, {"Elf": ChangedInstruction}):
            with self.assertRaisesRegex(ValueError, "0x2d28e4"):
                TOOL.inspect(ELF)

    def test_arbitrary_saved_mask_owner_ammo_remain_raw(self):
        with tempfile.TemporaryDirectory(prefix="tod-upgrade-raw-") as folder:
            path = Path(folder) / "GAME.bin"
            for mask in (0, 1, 0x3FFE, 0x80000000, 0xFFFFFFFF):
                data = fixture()
                struct.pack_into(">I", data, 20+12, mask)
                data[20+16] = 255
                data[20+8:20+12] = bytes.fromhex("7FC12345")
                path.write_bytes(data)
                record = TOOL.inspect(ELF,path)["save_observation"]["records"][1]
                self.assertEqual(record["mask_raw_hex"], f"{mask:08X}")
                self.assertEqual(record["ammo_raw_hex"], "7FC12345")
                self.assertEqual(record["ownership_byte"], 255)
                self.assertEqual(path.read_bytes(), data)

    def test_rejects_unverified_elf_plaintext_and_vendor(self):
        with tempfile.TemporaryDirectory(prefix="tod-upgrade-invalid-") as folder:
            path = Path(folder) / "invalid.bin"
            for raw in (b"bad", bytes(0x906F0)):
                path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF,path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)
            path.write_bytes(bytes(390796))
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                TOOL.inspect_vendor_asset(path)

    def test_reference_asset_methods_guards_and_no_payload_bundle(self):
        if VENDOR is None:
            self.skipTest("Pass --vendor-asset for detached reference asset")
        before = hashlib.sha256(VENDOR.read_bytes()).digest()
        report = TOOL.inspect(ELF,vendor_asset_path=VENDOR)["asset_observation"]
        self.assertEqual(report["grid_count"], 15)
        self.assertEqual(len(report["methods"]), 5)
        self.assertEqual(len(report["asset_guards"]), 11)
        self.assertEqual(sum(len(bytes.fromhex(g["bytes"])) for g in report["asset_guards"]), 44)
        self.assertEqual([f["node"] for f in report["combuster_synthetic_examples"]], [0,1,2,12])
        self.assertEqual(before, hashlib.sha256(VENDOR.read_bytes()).digest())

    def test_actual_elf_snapshot_asset_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for detached snapshot")
        paths = [ELF,SAVE] + ([VENDOR] if VENDOR else [])
        before = [hashlib.sha256(p.read_bytes()).digest() for p in paths]
        report = TOOL.inspect(ELF,SAVE,VENDOR)
        self.assertEqual(report["save_observation"]["records"][1]["mask_raw_hex"], "00003FFE")
        self.assertIn("not runtime resolved", report["save_observation"]["warning"])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in paths])

    def test_reproduces_embedded_map(self):
        mapping = json.loads(TOOL.BINDINGS["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(TOOL.inspect(ELF), mapping["upgrade_purchase"])
        if VENDOR is not None:
            self.assertEqual(TOOL.inspect_vendor_asset(VENDOR), mapping["upgrade_purchase_assets"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--vendor-asset", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE, VENDOR = options.elf, options.save, options.vendor_asset
    unittest.main(argv=[__file__] + remaining)
