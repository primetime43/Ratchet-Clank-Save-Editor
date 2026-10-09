"""Reproduce progression mapping from the original ELF and optional plaintext save."""
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
SPEC = importlib.util.spec_from_file_location("progression", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodProgression.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


class ProgressionChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build decoding")

    def test_reproduces_complete_bundled_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text())
        self.assertEqual(TOOL.inspect(ELF), mapping["progression"])

    def test_ids_definitions_and_localization_tags(self):
        report = TOOL.inspect(ELF)
        skills = report["skill_points"]["catalog"]
        self.assertEqual([s["id"] for s in skills], list(range(60)))
        self.assertEqual(len({s["enum"] for s in skills}), 60)
        self.assertEqual(skills[-1]["enum"], "SKILLPOINT_HARDCORE")
        self.assertEqual(sum(s["points"] for s in skills), 750)
        self.assertEqual([s["enum"] for s in report["armor"]["catalog"]],
            ["ARMOR_NONE", "ARMOR_DURAFIBER", "ARMOR_HYPERPLATE", "ARMOR_TETRAMESH", "ARMOR_QUANTONIUM"])
        elf = TOOL.BINDINGS.Elf(ELF)
        for skill in skills:
            self.assertEqual(struct.unpack(">IIII", elf.read(int(skill["definition_va"], 0), 16)),
                (skill["points"], skill["name_tag"], skill["description_tag"], skill["unknown_definition_0c"]))

    def test_sparse_bits_unknown_high_bits_and_nonboolean_ownership(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 0x14, i)
        struct.pack_into(">Q", data, 0x8710, (1 << 63) | (1 << 59) | 1)
        struct.pack_into(">I", data, 0x448, 2)
        struct.pack_into(">I", data, 0x458, 99)
        with tempfile.TemporaryDirectory(prefix="tod-progression-test-") as temporary:
            path = Path(temporary) / "GAME.SAV"
            path.write_bytes(data)
            result = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual(result["completed_ids"], [0, 59])
            self.assertEqual(result["unknown_skill_bits_hex"], "8000000000000000")
            self.assertEqual(result["armor_ownership"], [0, 2, 0, 0, 0])
            self.assertEqual(result["equipped_armor"], 99)
            self.assertEqual(path.read_bytes(), data)

    def test_rejects_wrong_size_and_nonplaintext_layout(self):
        with tempfile.TemporaryDirectory(prefix="tod-progression-test-") as temporary:
            path = Path(temporary) / "GAME.SAV"
            path.write_bytes(b"not a save")
            with self.assertRaisesRegex(ValueError, "size"):
                TOOL.inspect(ELF, path)
            path.write_bytes(bytes(0x906F0))
            with self.assertRaisesRegex(ValueError, "plaintext"):
                TOOL.inspect(ELF, path)

    def test_hash_guard_rejects_other_elf(self):
        with tempfile.TemporaryDirectory(prefix="tod-progression-test-") as temporary:
            path = Path(temporary) / "wrong.elf"
            path.write_bytes(b"wrong ELF")
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_plaintext_observations_without_writes(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual reference plaintext")
        before = hashlib.sha256(SAVE.read_bytes()).digest()
        data = SAVE.read_bytes()
        observation = TOOL.inspect(ELF, SAVE)["save_observation"]
        bits = int.from_bytes(data[0x8710:0x8718], "big")
        self.assertEqual(observation["completed_count"], (bits & ((1 << 60) - 1)).bit_count())
        self.assertEqual(observation["skill_score"], struct.unpack_from(">I", data, 0x8708)[0])
        self.assertEqual(observation["equipped_armor"], struct.unpack_from(">I", data, 0x458)[0])
        self.assertEqual(hashlib.sha256(SAVE.read_bytes()).digest(), before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
