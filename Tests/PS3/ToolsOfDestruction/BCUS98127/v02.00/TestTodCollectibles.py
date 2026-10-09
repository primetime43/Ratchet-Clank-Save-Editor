"""Exact-ELF/save checks for the hero XP, special-bolt and skin map."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("collectibles", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodCollectibles.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


class CollectibleChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_bundled_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text())
        self.assertEqual(TOOL.inspect(ELF), mapping["collectibles"])

    def test_native_catalogs_totals_and_types(self):
        report = TOOL.inspect(ELF)
        self.assertEqual(report["hero_xp"]["offset"], "0x418")
        self.assertEqual(report["hero_xp"]["type"], "uint32 BE")
        levels = report["special_bolts"]["catalog"]
        self.assertEqual([v["id"] for v in levels], list(range(19)))
        self.assertEqual(sum(v["total"] for v in levels), 32)
        self.assertEqual([int(v["mask_offset"], 0) for v in levels], [0x874 + i * 0x408 for i in range(19)])
        self.assertEqual([v["cost"] for v in report["skins"]["catalog"]], [0, 6, 3, 6, 6, 4, 4, 0, 3])
        self.assertEqual(report["skins"]["catalog"][7]["enum"], "SKIN_JAILBIRD")

    def test_unknown_bits_nonboolean_ownership_and_signed_balance(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 0x14, i)
        struct.pack_into(">I", data, 0xC7C, 0x80000001)
        struct.pack_into(">I", data, 0x550C, 0xFFFFFFFF)
        struct.pack_into(">I", data, 0x424, 5)
        struct.pack_into(">I", data, 0x460, 2)
        struct.pack_into(">I", data, 0x480, 99)
        with tempfile.TemporaryDirectory(prefix="tod-collectibles-test-") as temporary:
            path = Path(temporary) / "GAME.SAV"
            path.write_bytes(data)
            observation = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual(observation["collected"], 2)
            self.assertEqual(observation["native_signed_balance"], -3)
            self.assertEqual(observation["uninterpreted_slot19_mask"], "FFFFFFFF")
            self.assertEqual(observation["skin_ownership"][1], 2)
            self.assertEqual(observation["selected_skin"], 99)
            self.assertEqual(path.read_bytes(), data)

    def test_refuses_wrong_size_and_nonplaintext(self):
        with tempfile.TemporaryDirectory(prefix="tod-collectibles-test-") as temporary:
            path = Path(temporary) / "GAME.SAV"
            for data in (b"not a save", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)

    def test_refuses_wrong_elf(self):
        with tempfile.TemporaryDirectory(prefix="tod-collectibles-test-") as temporary:
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
        self.assertEqual(observation["hero_xp"], struct.unpack_from(">I", data, 0x418)[0])
        self.assertEqual(observation["spent"], struct.unpack_from(">I", data, 0x424)[0])
        self.assertEqual(observation["collected"], sum(struct.unpack_from(">I", data, 0x874 + i * 0x408)[0].bit_count() for i in range(19)))
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
