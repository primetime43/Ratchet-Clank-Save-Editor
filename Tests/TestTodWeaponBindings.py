"""Native decoder checks, with optional original-ELF and extracted-asset validation."""
import argparse
import hashlib
from pathlib import Path
import runpy
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DECODER = runpy.run_path(str(ROOT / "Tools/Inspect-TodWeaponBindings.py"))
ELF = ASSETS = None


class BindingChecks(unittest.TestCase):
    def test_signed_and_branch_decode(self):
        self.assertEqual(DECODER["signed"](0xFFFF, 16), -1)
        self.assertEqual(DECODER["branch_target"](0x4BFF22DD, 0x4744BC), 0x466798)
        self.assertEqual(DECODER["branch_target"](0x4BE4025D, 0x1D0FB4), 0x11210)
        self.assertIsNone(DECODER["branch_target"](0x38800001, 0))

    def test_small_and_large_parent_offset_patterns(self):
        class FakeElf:
            def __init__(self, code): self.code = code
            def instructions(self, _start, _end): return enumerate(self.code, 0)
        class AlignedFake(FakeElf):
            def instructions(self, _start, _end): return ((i * 4, word) for i, word in enumerate(self.code))
        small = [0x38DE1CFC, 0x480104CD]  # branch from 4 to 0x104D0
        large = [0x3CFE0001, 0x38C78368, 0x480104C9]  # branch from 8
        self.assertEqual(DECODER["subobject_offset"](AlignedFake(small), 0), 0x1CFC)
        self.assertEqual(DECODER["subobject_offset"](AlignedFake(large), 0), 0x8368)
        with self.assertRaises(ValueError):
            DECODER["subobject_offset"](AlignedFake([0x480104D1]), 0)

    def test_wrong_binary_rejected_before_pointer_following(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-an-elf"
            path.write_bytes(b"wrong")
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                DECODER["inspect"](path)

    def test_reference_catalog_and_unchanged_input(self):
        if ELF is None:
            self.skipTest("Pass --elf for the reference BCUS98127 v02.00 executable")
        before = hashlib.sha256(ELF.read_bytes()).digest()
        report = DECODER["inspect"](ELF)
        self.assertEqual(report["config_root_va"], "0x101b9ee8")
        self.assertEqual(len(report["enum_exports"]), 34)
        self.assertEqual(len(report["config_properties"]), 32)
        catalog = {c["id"]: c for c in report["constructor_calls"]}
        self.assertEqual(set(catalog), set(range(32)))
        self.assertEqual(catalog[1]["config_name"], "Combuster")
        self.assertEqual(catalog[1]["config_va"], "0x101bbbe4")
        self.assertEqual(catalog[2]["config_name"], "Grenade")
        self.assertEqual(catalog[29]["config_name"], "MagCycle")
        self.assertEqual(catalog[30]["config_name"], "PirateGadget")
        self.assertEqual(catalog[31]["save_record_offset"], "0x26c")
        self.assertEqual(hashlib.sha256(ELF.read_bytes()).digest(), before)

    def test_config_csv_links(self):
        if ELF is None or ASSETS is None:
            self.skipTest("Pass --elf and --assets to cross-check independent native/CSV catalogs")
        native = DECODER["inspect"](ELF)
        csv = runpy.run_path(str(ROOT / "Tools/Inspect-TodWeaponConfigs.py"))["inspect"](ASSETS)
        names = {c["config_name"] for c in native["constructor_calls"]}
        self.assertTrue(set(csv["weapons"]) <= names)
        self.assertEqual(names - set(csv["weapons"]), {"CuttingLaser", "RoboWings", "MagCycle", "PirateGadget"})
        lua = runpy.run_path(str(ROOT / "Tools/Inspect-Lua50.py"))
        grids = lua["vendor_layout"](lua["inspect"](ASSETS / "weapon-vendor-built.dat", 0x54F85))["grids"]
        by_enum = {c["enum"]: c["config_name"] for c in native["constructor_calls"]}
        for enum, grid in grids.items():
            mods = csv["weapons"][by_enum[enum]]["modifiers"]
            self.assertEqual({n["index"] for n in grid["nodes"]}, {n["index"] for n in mods}, enum)
            self.assertLessEqual(len(mods), 24)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--assets", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, ASSETS = args.elf, args.assets
    unittest.main(argv=[sys.argv[0]] + remaining)
