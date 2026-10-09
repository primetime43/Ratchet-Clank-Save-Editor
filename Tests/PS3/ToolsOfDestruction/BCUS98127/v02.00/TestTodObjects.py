"""Exact-ELF and plaintext-snapshot checks for native object counters."""
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
SPEC = importlib.util.spec_from_file_location("objects", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodObjects.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


class ObjectChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_bundled_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text())
        self.assertEqual(TOOL.inspect(ELF), mapping["objects"])

    def test_catalog_and_array_boundaries(self):
        report = TOOL.inspect(ELF)
        self.assertEqual(report["count"], 23)
        self.assertEqual([v["id"] for v in report["catalog"]], list(range(23)))
        self.assertEqual(report["catalog"][0]["enum"], "OBJ_HELI_PACK")
        self.assertEqual(report["catalog"][22]["enum"], "OBJ_ARENA_COUNT")
        self.assertEqual(report["current_offset"], "0x304")
        self.assertEqual(report["peak_offset"], "0x360")
        self.assertEqual(report["positive_additions_offset"], "0x3bc")
        self.assertEqual(report["catalog"][-1]["positive_additions_offset"], "0x414")

    def test_signed_current_independent_unsigned_other_arrays(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 0x14, i)
        struct.pack_into(">i", data, 0x304, -2)
        struct.pack_into(">I", data, 0x360, 0xFFFFFFFF)
        struct.pack_into(">I", data, 0x3BC, 0x80000000)
        with tempfile.TemporaryDirectory(prefix="tod-object-test-") as temporary:
            path = Path(temporary) / "GAME.SAV"
            path.write_bytes(data)
            observation = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual(observation["current"][0], -2)
            self.assertEqual(observation["peak"][0], 0xFFFFFFFF)
            self.assertEqual(observation["positive_additions"][0], 0x80000000)
            self.assertEqual(path.read_bytes(), data)

    def test_refuses_wrong_size_nonplaintext_and_wrong_elf(self):
        with tempfile.TemporaryDirectory(prefix="tod-object-test-") as temporary:
            path = Path(temporary) / "GAME.SAV"
            for data in (b"not a save", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_inputs_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual plaintext observations")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observation = TOOL.inspect(ELF, SAVE)["save_observation"]
        data = SAVE.read_bytes()
        self.assertEqual(observation["current"], list(struct.unpack_from(">23i", data, 0x304)))
        self.assertEqual(observation["peak"], list(struct.unpack_from(">23I", data, 0x360)))
        self.assertEqual(observation["positive_additions"], list(struct.unpack_from(">23I", data, 0x3BC)))
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
