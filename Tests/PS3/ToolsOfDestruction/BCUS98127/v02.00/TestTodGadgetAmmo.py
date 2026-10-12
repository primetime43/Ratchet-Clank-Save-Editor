"""Small consumable-ammo allowlist checks; optional one-shot native report validation."""
import argparse
import json
from pathlib import Path
import runpy
import struct
import unittest

ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGadgetAmmo.py"))
ELF = SAVE = ASSETS = None


def sample():
    data = bytearray(0x906F0)
    for identifier in range(32):
        struct.pack_into(">I", data, identifier * 20, identifier)
    data[16 * 20 + 16] = 1
    struct.pack_into(">f", data, 16 * 20 + 8, 4)
    return data


class GadgetAmmoChecks(unittest.TestCase):
    def test_exact_allowlist_excludes_linked_and_traversal_states(self):
        self.assertEqual(list(TOOL["ALLOWLIST"]), [16, 17, 18, 20, 21, 22, 23])
        self.assertEqual([row[1] for row in TOOL["ALLOWLIST"].values()], [4, 2, 3, 2, 1, 3, 3])
        for identifier in [0, 15, 19, 24, 27, 31, 32, True]:
            with self.assertRaises(ValueError):
                TOOL["saved_observation"](sample(), identifier, 4)

    def test_owned_zero_level_xp_and_mask_are_independent_gates(self):
        baseline = sample()
        self.assertTrue(TOOL["saved_observation"](baseline, 16, 4)["passes_editor_gates"])
        for offset, raw in [(16 * 20 + 16, b"\0"), (16 * 20 + 17, b"\1"),
                            (16 * 20 + 4, struct.pack(">f", 1)),
                            (16 * 20 + 4, bytes.fromhex("7FC12345")),
                            (16 * 20 + 12, struct.pack(">I", 1))]:
            data = bytearray(baseline)
            data[offset:offset + len(raw)] = raw
            self.assertFalse(TOOL["saved_observation"](data, 16, 4)["passes_editor_gates"])
        self.assertEqual(baseline, sample())

    def test_ammo_bounds_and_nonfinite_are_not_clamped_or_repaired(self):
        for value, accepted in [(0, True), (.5, True), (4, True), (-.1, False),
                                (4.1, False), (float("inf"), False), (float("nan"), False)]:
            data = sample()
            struct.pack_into(">f", data, 16 * 20 + 8, value)
            before = bytes(data)
            result = TOOL["saved_observation"](data, 16, 4)
            self.assertEqual(result["passes_editor_gates"], accepted)
            json.dumps(result, allow_nan=False)
            self.assertEqual(bytes(data), before)

    def test_malformed_layout_and_wrong_reference_capacity_are_refused(self):
        for data in (sample()[:-1], bytearray(0x906F0)):
            with self.assertRaises(ValueError):
                TOOL["saved_observation"](data, 16, 4)
        with self.assertRaises(ValueError):
            TOOL["saved_observation"](sample(), 16, 5)

    def test_optional_native_assets_and_actual_saved_observation_once(self):
        if ELF is None:
            self.skipTest("Pass --elf for one bounded proof")
        report = TOOL["inspect"](ELF, SAVE, ASSETS)
        self.assertEqual([row["id"] for row in report["catalog"]], list(TOOL["ALLOWLIST"]))
        self.assertTrue(report["instruction_guards"])
        if ASSETS is not None:
            self.assertTrue(report["assets_verified_from_files"])
        if SAVE is not None:
            observations = report["save_observation"]["records"]
            self.assertEqual([row["id"] for row in observations], list(TOOL["ALLOWLIST"]))
            self.assertTrue(all(row["passes_editor_gates"] for row in observations))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--assets", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE, ASSETS = args.elf, args.save, args.assets
    unittest.main(argv=[__file__] + remaining)
