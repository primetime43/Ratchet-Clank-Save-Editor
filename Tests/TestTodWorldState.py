"""Exact-ELF and plaintext-snapshot checks for world progress and quick select."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("world_state", ROOT / "Tools/Inspect-TodWorldState.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


class WorldStateChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_bundled_map(self):
        mapping = json.loads((ROOT / "docs/maps/ToolsOfDestruction.BCUS98127.v02.00.json").read_text())
        self.assertEqual(TOOL.inspect(ELF), mapping["world_state"])

    def test_catalog_layouts_and_asymmetric_slot_bounds(self):
        report = TOOL.inspect(ELF)
        self.assertEqual(report["worlds"]["record_stride"], "0x408")
        self.assertEqual([v["id"] for v in report["worlds"]["catalog"]], list(range(19)))
        self.assertEqual(report["missions"]["record_stride"], "0x7c")
        self.assertEqual(report["missions"]["completed_offset"], "0x10b70")
        self.assertEqual(report["quick_select"]["word_count"], 32)
        self.assertEqual(report["quick_select"]["automatic_insert_slots"], 24)
        self.assertEqual(report["quick_select"]["offset"], "0x284")

    def test_nonboolean_flags_unsigned_counter_unknown_signed_ids(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 0x14, i)
            struct.pack_into(">i", data, 0x284 + i * 4, -1)
        data[0xC90:0xC93] = bytes([2, 3, 4])
        struct.pack_into(">I", data, 0x10BEC, 0xFFFFFFFF)
        struct.pack_into(">i", data, 0x284, -2)
        struct.pack_into(">i", data, 0x300, 99)
        with tempfile.TemporaryDirectory(prefix="tod-world-test-") as temporary:
            path = Path(temporary) / "GAME.SAV"
            path.write_bytes(data)
            observation = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual(observation["worlds"][1], {"id": 1, "unlocked_byte": 2, "visited_byte": 3, "menu_exclusion_byte": 4, "missions_completed": 0xFFFFFFFF})
            self.assertEqual(observation["quick_select"][0], -2)
            self.assertEqual(observation["quick_select"][31], 99)
            self.assertEqual(path.read_bytes(), data)

    def test_refuses_wrong_size_and_nonplaintext(self):
        with tempfile.TemporaryDirectory(prefix="tod-world-test-") as temporary:
            path = Path(temporary) / "GAME.SAV"
            for data in (b"not a save", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)

    def test_refuses_wrong_elf(self):
        with tempfile.TemporaryDirectory(prefix="tod-world-test-") as temporary:
            path = Path(temporary) / "EBOOT.ELF"
            path.write_bytes(b"wrong executable")
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_inputs_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual plaintext observations")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observation = TOOL.inspect(ELF, SAVE)["save_observation"]
        data = SAVE.read_bytes()
        for i, world in enumerate(observation["worlds"]):
            self.assertEqual(world["unlocked_byte"], data[0x888 + i * 0x408])
            self.assertEqual(world["visited_byte"], data[0x889 + i * 0x408])
            self.assertEqual(world["missions_completed"], struct.unpack_from(">I", data, 0x10B70 + i * 0x7C)[0])
        self.assertEqual(observation["quick_select"], list(struct.unpack_from(">32i", data, 0x284)))
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
