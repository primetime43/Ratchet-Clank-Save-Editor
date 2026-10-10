"""Health attribute identity, conditional XP refresh and checkpoint ammo boundaries."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("health", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodHealthPersistence.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i * 0x14, i)
    return data


class HealthPersistenceChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build verification")

    def test_reproduces_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(TOOL.inspect(ELF), mapping["health_persistence"])

    def test_runtime_health_is_attribute_not_a_save_offset(self):
        report = TOOL.inspect(ELF)
        self.assertEqual(report["health"]["float_attribute_id"], "0x6c")
        self.assertEqual(report["health"]["attribute_runtime_offset"], "0x1780")
        self.assertEqual(report["health"]["current_health_runtime_offset"], "0x1784")
        self.assertEqual(report["health"]["capacity_runtime_offset"], "0x1788")
        self.assertIn("zero lower clamp", report["health"]["capacity_rule"])
        self.assertNotIn("save_offset", report["health"])

    def test_xp_restore_conditional_and_table_not_available(self):
        report = TOOL.inspect(ELF)["xp_restore"]
        self.assertEqual(report["saved_xp_offset"], "0x418")
        self.assertIn("On changed-level", report["health_entry_rule"])
        self.assertIn("XPzero", report["boundary"])
        self.assertIn("runtime BSS", report["boundary"])
        self.assertEqual(report["threshold_table_va"], "0x101b9ee8")

    def test_checkpoint_captures_and_merges_ammo_not_health_or_xp(self):
        report = TOOL.inspect(ELF)["checkpoint"]
        self.assertGreater(int(report["relative_to_state_base"], 0), int(report["save_size"], 0))
        self.assertEqual(report["ammo_member_offset"], "0x8")
        self.assertEqual(report["weapon_count"], 32)
        self.assertEqual(report["ammo_bank_stride"], "0x80")
        self.assertEqual([x["function_va"] for x in report["vendor_merge_callers"]], ["0x2d2990", "0x2d2b90", "0x2d2d38"])
        self.assertIn("finite values", report["merge_rule"])
        self.assertIn("not a verbatim bit copy", report["restore_rule"])

    def test_nonfinite_and_unknown_ammo_bits_immutable(self):
        data = fixture()
        values = [0x7FC12345, 0x7F800000, 0xFF800000, 0x80000000, 0xBF800000, 0x44240000]
        for i, value in enumerate(values):
            struct.pack_into(">I", data, i * 0x14 + 8, value)
        struct.pack_into(">I", data, 0x418, 0xFFFFFFFF)
        with tempfile.TemporaryDirectory(prefix="tod-health-") as folder:
            path = Path(folder) / "GAME.bin"
            path.write_bytes(data)
            observation = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual(observation["saved_hero_xp"], 0xFFFFFFFF)
            self.assertEqual([x["raw_hex"] for x in observation["inventory_bank0_ammo"][:6]], [f"{x:08X}" for x in values])
            self.assertEqual([x["nonfinite"] for x in observation["inventory_bank0_ammo"][:6]], [True, True, True, False, False, False])
            self.assertIsNone(observation["current_health"])
            self.assertIsNone(observation["runtime_level"])
            self.assertIsNone(observation["capacity"])
            self.assertIsNone(observation["active_checkpoint"])
            json.dumps(observation, allow_nan=False)
            self.assertEqual(path.read_bytes(), data)

    def test_invalid_plaintext_rejected(self):
        with tempfile.TemporaryDirectory(prefix="tod-health-invalid-") as folder:
            path = Path(folder) / "GAME.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)

    def test_actual_save_and_elf_unchanged_no_runtime_claims(self):
        if SAVE is None:
            self.skipTest("Pass --save for supplied-save observations")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        report = TOOL.inspect(ELF, SAVE)
        observation = report["save_observation"]
        self.assertEqual(observation["saved_hero_xp"], 2315144)
        self.assertEqual(len(observation["inventory_bank0_ammo"]), 32)
        self.assertEqual(observation["inventory_bank0_ammo"][1]["value"], 100.0)
        self.assertIsNone(observation["current_health"])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__, *remaining])
