"""Configuration parser fixtures; optional fingerprinted original-asset checks."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys
import unittest

ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "Ratchet And Clank Save Editor.sln").is_file())
PARSER = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWeaponConfigs.py"))
ASSETS = None


class ConfigChecks(unittest.TestCase):
    def test_levels_and_missing_values(self):
        parsed = PARSER["parse_weapons"](b'Weapon:,Variable:,Comments:\nCombuster,,\n,XP,,0,1000\n,MaxAmmo,,100,,120\n')
        self.assertEqual(parsed["Combuster"]["num_levels"], 2)
        self.assertEqual(parsed["Combuster"]["variables"]["MaxAmmo"], [100, None, 120])

    def test_percentage_special_and_negative_nodes(self):
        parsed = PARSER["parse_mods"](b'Weapon:,Mod#:\nTest,,\n,0,MOD_START\n,1,MOD_ALT_DAMAGE,PERCENT,-25,100\n,2,MOD_SPECIAL,,,500\n')
        self.assertEqual(parsed["Test"][1]["runtime_value"], -0.25)
        self.assertEqual(parsed["Test"][2]["mask"], "0x00000004")
        self.assertIsNone(parsed["Test"][2]["runtime_value"])

    def test_bad_values_rejected_without_execution(self):
        for value in ("nan", "inf", "1e999", "1+1", "os.execute('bad')"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                PARSER["parse_weapons"](f'Weapon:,Variable:\nTest,,\n,XP,,{value}\n'.encode())

    def test_duplicate_names_variables_and_sparse_nodes(self):
        for raw in (b'Weapon:,Variable:\nTest,,\nTest,,\n',
                    b'Weapon:,Variable:\nTest,,\n,XP,,0\n,XP,,1\n'):
            with self.assertRaises(ValueError):
                PARSER["parse_weapons"](raw)
        for index in ("32", "1", "-1"):
            with self.assertRaises(ValueError):
                PARSER["parse_mods"](f'Weapon:,Mod#:\nTest,,\n,{index},MOD_START\n'.encode())

    def test_vendor_sections(self):
        weapons, armor = PARSER["parse_vendor"](b'Weapon,WeaponID,BasePrice,AmmoPrice,MegaPrice,UnlockLevel\n,Combuster,69,1,5500000,\nArmor,ArmorID,BasePrice,,,UnlockLevel\n,ARMOR_NONE,0,,,test\n')
        self.assertEqual(weapons["Combuster"]["MegaPrice"], 5500000)
        self.assertEqual(armor["ARMOR_NONE"]["UnlockLevel"], "test")

    def test_reference_hash_lengths(self):
        for digest in PARSER["REFERENCE_HASHES"].values():
            self.assertEqual(len(bytes.fromhex(digest)), 32)

    def test_reference_assets(self):
        if ASSETS is None:
            self.skipTest("Pass --assets for explicitly extracted original configurations")
        before = {p.name: hashlib.sha256(p.read_bytes()).digest() for p in ASSETS.iterdir() if p.is_file()}
        report = PARSER["inspect"](ASSETS)
        bundled = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/WeaponConfigs.json").read_text(encoding="utf-8"))
        for key in ("assets", "weapons", "armor_vendor", "weapon_count", "modifier_count"):
            self.assertEqual(bundled[key], report[key], "Bundled research drift: " + key)
        self.assertTrue(report["reference_assets_match"])
        self.assertEqual(report["weapon_count"], 28)
        self.assertEqual(report["modifier_count"], 204)
        combuster = report["weapons"]["Combuster"]
        self.assertEqual(combuster["variables"]["XP"], [0, 1000, 2200, 3640, 5368, 5500, 20000, 37400, 58280, 83336])
        self.assertEqual(combuster["num_levels"], 9)
        self.assertEqual(combuster["modifiers"][12]["cost"], 300)
        self.assertEqual(report["weapons"]["Ryno"]["variables"]["MaxAmmo"], [300] * 5 + [750] * 5)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).digest() for p in ASSETS.iterdir() if p.is_file()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path)
    args, remaining = parser.parse_known_args()
    ASSETS = args.assets
    unittest.main(argv=[sys.argv[0]] + remaining)
