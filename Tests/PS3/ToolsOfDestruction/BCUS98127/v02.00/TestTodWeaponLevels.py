"""Scoped weapon XP bindings, tier policy, reference snapshots and immutable inputs."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWeaponLevels.py"))
MAP = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
CONFIGS = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/WeaponConfigs.json").read_text(encoding="utf-8"))
ELF, ASSETS, SAVE = None, None, None


def bits(value):
    return struct.unpack(">I", struct.pack(">f", value))[0]


class WeaponLevelChecks(unittest.TestCase):
    def test_all_reference_combat_choices_stay_within_existing_tier(self):
        for item in MAP["weapon_level_editing"]["catalog"]:
            config = CONFIGS["weapons"][item["config_name"]]
            for level in range(10):
                xp = config["variables"]["XP"][level]
                first = 5 if level > 4 else 0
                self.assertEqual(TOOL["choices"](1, level, bits(xp), bits(0), 0, item["initial_flags_bits"], config), list(range(first, first + 5)))
                for candidate in range(first, first + 5):
                    selected = TOOL["PROGRESSION"]["finite_level_preview"](level, config["variables"]["XP"][candidate], config["variables"]["XP"], item["initial_flags_bits"])
                    self.assertEqual(selected["recomputed_level"], candidate)

    def test_cap_uses_old_tier_and_xp_boundary_is_inclusive(self):
        config = CONFIGS["weapons"]["Combuster"]
        choices = TOOL["choices"]
        self.assertEqual(choices(7, 4, bits(1000000), bits(0), 0, 4, config), list(range(5)))
        self.assertEqual(choices(1, 9, bits(83336), bits(0), 0, 4, config), list(range(5, 10)))
        self.assertEqual(choices(1, 9, bits(83335), bits(0), 0, 4, config), [])
        self.assertEqual(choices(1, 0, bits(1000), bits(0), 0, 4, config), [])
        self.assertEqual(choices(1, 5, bits(5500), bits(0), 0, 4, config), list(range(5, 10)))
        self.assertEqual(choices(1, 5, bits(20000), bits(0), 0, 4, config), [])

    def test_unknown_records_and_invalid_definitions_stay_read_only(self):
        config = CONFIGS["weapons"]["Combuster"]
        base = [1, 0, bits(0), bits(0), 0, 4, config]
        for index, value in ((0, 0), (1, 255), (2, bits(float("nan"))), (2, bits(float("inf"))),
                             (2, bits(-1)), (3, bits(-1)), (3, bits(101)), (3, bits(float("nan"))),
                             (4, 0x80000000), (5, 1), (5, 2)):
            arguments = base.copy(); arguments[index] = value
            self.assertEqual(TOOL["choices"](*arguments), [])
        for failure in range(6):
            changed = copy.deepcopy(config)
            if failure == 0: changed["num_levels"] = 10
            if failure == 1: changed["variables"]["XP"][3] = None
            if failure == 2: changed["variables"]["XP"][2] = changed["variables"]["XP"][1]
            if failure == 3: changed["variables"]["XP"].pop()
            if failure == 4: changed["variables"]["MaxAmmo"][2] = 90
            if failure == 5: changed["variables"]["MaxAmmo"].pop()
            self.assertEqual(TOOL["choices"](*base[:-1], changed), [])
        for index, value in ((0, True), (1, -1), (2, -1), (4, 0x100000000)):
            arguments = base.copy(); arguments[index] = value
            with self.assertRaises(ValueError): TOOL["choices"](*arguments)

    def test_selected_ammo_modifiers_and_ryno_boundary(self):
        config = CONFIGS["weapons"]["Grenade"]
        selected = next(node for node in config["modifiers"] if node["type"] == "MOD_AMMO")
        limit = config["variables"]["MaxAmmo"][0] + selected["runtime_value"]
        self.assertEqual(TOOL["choices"](1, 0, bits(0), bits(limit), 1 << selected["index"], 0x804, config), list(range(5)))
        self.assertEqual(TOOL["choices"](1, 0, bits(0), bits(limit + 1), 1 << selected["index"], 0x804, config), [])
        ryno = CONFIGS["weapons"]["Ryno"]
        self.assertEqual(TOOL["choices"](1, 4, bits(80520), bits(500), 0, 0x400, ryno), [])
        self.assertEqual(TOOL["choices"](1, 5, bits(81000), bits(500), 0, 0x400, ryno), list(range(5, 10)))

    def test_reproduces_native_and_asset_map(self):
        if ELF is None or ASSETS is None: self.skipTest("Pass --elf and --assets for exact-build reproduction")
        report = TOOL["inspect"](ELF, ASSETS)
        self.assertEqual(report, MAP["weapon_level_editing"])
        self.assertEqual(len(report["catalog"]), 15)
        self.assertEqual(len(report["recommended_annotations"]), 5)
        self.assertEqual(len(report["instruction_guards"]), 49)
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)
        annotations = {int(a["va"], 0): a for a in MAP["annotations"]}
        for annotation in report["recommended_annotations"]:
            self.assertEqual(annotations[int(annotation["va"], 0)]["name"], annotation["name"])

    def test_namespace_scope_and_policy_limits_remain_explicit(self):
        report = MAP["weapon_level_editing"]
        self.assertEqual(report["xp_property"]["data_offset"], "0x230")
        self.assertEqual(report["xp_property"]["physical_count"], 20)
        self.assertIn("scalar+14", report["xp_property"]["scope"])
        self.assertIn("HeroConfig", report["xp_property"]["scope"])
        self.assertIn("BEFORE storing XP", report["native_dependency"])
        self.assertIn("Explicit ammo edits override", report["edit_policy"])
        self.assertIn("Same-level requests preserve all bytes", report["edit_policy"])
        self.assertIn("in-game acceptance", report["warning"])
        self.assertIn("inspection-only", report["warning"])

    def test_wrong_assets_and_layouts_are_rejected(self):
        if ELF is None or ASSETS is None: self.skipTest("Pass --elf and --assets for input checks")
        with tempfile.TemporaryDirectory(prefix="tod-level-evidence-") as directory:
            path = Path(directory)
            for filename in TOOL["CONFIGS"]["REFERENCE_HASHES"]:
                (path / filename).write_bytes((ASSETS / filename).read_bytes())
            (path / "weapon.lua").write_bytes((path / "weapon.lua").read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "six exact reference"): TOOL["inspect"](ELF, path)
            bad = path / "snapshot.bin"
            for data in (b"invalid", bytes(0x906F0)):
                bad.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"): TOOL["inspect"](ELF, ASSETS, bad)

    def test_reference_save_has15_consistent_owned_top_tier_weapons_and_inputs_stay_unchanged(self):
        if ELF is None or ASSETS is None or SAVE is None: self.skipTest("Pass --elf, --assets and --save for reference observations")
        inputs = [ELF, SAVE] + [ASSETS / name for name in TOOL["CONFIGS"]["REFERENCE_HASHES"]]
        before = [hashlib.sha256(path.read_bytes()).digest() for path in inputs]
        report = TOOL["inspect"](ELF, ASSETS, SAVE)["save_observation"]
        self.assertEqual(report["sha256"], "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
        self.assertEqual([r["stored_level"] for r in report["records"]], [9] * 15)
        self.assertEqual([r["eligible_stored_levels"] for r in report["records"]], [list(range(5, 10))] * 15)
        self.assertEqual(before, [hashlib.sha256(path.read_bytes()).digest() for path in inputs])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, ASSETS, SAVE = args.elf, args.assets, args.save
    unittest.main(argv=[__file__] + remaining)
