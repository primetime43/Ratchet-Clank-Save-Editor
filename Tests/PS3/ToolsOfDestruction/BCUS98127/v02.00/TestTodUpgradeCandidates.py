"""Focused upgrade candidate topology and exact reference observations only."""
import argparse
import copy
import json
from pathlib import Path
import runpy
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodUpgradeCandidates.py"))
MAP = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text())
CONFIG = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/WeaponConfigs.json").read_text())
ELF = ASSETS = VENDOR = SAVE = None


def nodes(name="Combuster"):
    item = next(i for i in MAP["weapon_configuration"]["inventory_catalog"] if i["config_name"] == name)
    grid = MAP["weapon_configuration"]["vendor_upgrade_layout"]["grids"][item["enum"]]
    return TOOL["catalog"]({"grid": grid["rows"], "special_node": grid["special_node"]}, CONFIG["weapons"][name]["modifiers"])


class CandidateChecks(unittest.TestCase):
    def test_start_is_implicit_never_a_candidate_and_ownership_required(self):
        self.assertEqual(TOOL["frontier"](nodes(), 0, 1), [2])
        self.assertEqual(TOOL["frontier"](nodes(), 1, 255), [2])
        self.assertEqual(TOOL["frontier"](nodes(), 0, 0), [])

    def test_ordinary_requires_an_installed_neighbor_and_no_duplicate(self):
        self.assertEqual(TOOL["frontier"](nodes(), 1 << 2, 1), [7])
        self.assertNotIn(2, TOOL["frontier"](nodes(), 1 << 2, 1))
        self.assertEqual(TOOL["frontier"](nodes(), 1 << 1, 1), [])  # Disconnected baseline.

    def test_special_requires_every_positive_neighbor(self):
        complete = (1 << len(nodes())) - 2
        missing_special = complete & ~(1 << 12)
        self.assertIn(12, TOOL["frontier"](nodes(), missing_special, 1))
        self.assertNotIn(12, TOOL["frontier"](nodes(), missing_special & ~(1 << 5), 1))

    def test_missing_special_values_are_not_guessed(self):
        for name, index in (("BuzzBlade",6),("Predator",8),("AlphaNova",10),("FlameThrower",9),
                            ("Reaper",13),("Rocket",5),("RoboHive",9)):
            catalog = nodes(name)
            self.assertFalse(catalog[index]["definition_qualified"])
            self.assertIsNone(catalog[index]["runtime_value"])
            self.assertNotIn(index, TOOL["frontier"](catalog, ((1 << len(catalog)) - 2) & ~(1 << index), 1))

    def test_all_15_shipped_graphs_and_counts(self):
        totals = [0] * 5
        for item in MAP["weapon_configuration"]["inventory_catalog"]:
            if item["enum"] not in MAP["weapon_configuration"]["vendor_upgrade_layout"]["grids"]:
                continue
            catalog = nodes(item["config_name"])
            self.assertFalse(TOOL["reachable_order"](catalog, (1 << len(catalog)) - 2)["unreachable_nodes"])
            totals[0] += 1
            totals[1] += len(catalog)
            totals[2] += sum(n["definition_qualified"] for n in catalog)
            totals[3] += sum(n["is_special"] for n in catalog)
            totals[4] += sum(n["type"] == "MOD_AMMO" for n in catalog)
        self.assertEqual(totals, [15, 204, 182, 14, 38])

    def test_undefined_mask_noninteger_ownership_and_mismatched_grid_rejected(self):
        for mask in (-1, True, 1 << 31):
            with self.assertRaises(ValueError): TOOL["frontier"](nodes(), mask, 1)
        for ownership in (-1, True, 256):
            with self.assertRaises(ValueError): TOOL["frontier"](nodes(), 0, ownership)
        grid = MAP["weapon_configuration"]["vendor_upgrade_layout"]["grids"]["WPN_COMBUSTER"]
        with self.assertRaises(ValueError):
            TOOL["catalog"]({"grid": grid["rows"], "special_node": grid["special_node"]}, CONFIG["weapons"]["Combuster"]["modifiers"][:-1])

    def test_inputs_preserved_and_ryno_has_no_positive_special(self):
        catalog = nodes("Ryno")
        original = copy.deepcopy(catalog)
        self.assertFalse(any(n["is_special"] for n in catalog))
        TOOL["frontier"](catalog, 0, 1)
        self.assertEqual(catalog, original)

    def test_exact_fingerprints_guards_and_reference_has_no_purchase_transition(self):
        if any(p is None for p in (ELF, ASSETS, VENDOR, SAVE)):
            self.skipTest("Pass --elf --assets --vendor-asset --save for bounded exact audit")
        report = TOOL["inspect"](ELF, ASSETS, VENDOR, SAVE)
        self.assertEqual(report["counts"]["definition_qualified_positive"], 182)
        self.assertEqual(report["native_guard_count"], 117)
        self.assertEqual(report["native_guard_section"], "upgrade_purchase")
        self.assertEqual(len(report["vendor_asset_observation"]["methods"]), 5)
        self.assertTrue(report["save_observation"]["all_positive_nodes_already_installed"])
        self.assertEqual(report["save_observation"]["sha256"], "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
        self.assertTrue(all(not r["candidate_frontier"] for r in report["save_observation"]["records"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--vendor-asset", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, ASSETS, VENDOR, SAVE = args.elf, args.assets, args.vendor_asset, args.save
    unittest.main(argv=[__file__] + remaining)
