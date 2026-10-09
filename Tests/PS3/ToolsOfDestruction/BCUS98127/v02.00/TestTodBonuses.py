"""Exact-build blueprint/bonus checks; fixtures are not gameplay captures."""
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
SPEC = importlib.util.spec_from_file_location("bonuses", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodBonuses.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


class BonusChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_bundled_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text())
        report = TOOL.inspect(ELF)
        self.assertEqual(report, mapping["bonuses"])
        self.assertEqual(report["blueprints"]["mask_offset"], "0x86f4")
        self.assertEqual(report["blueprints"]["all_grant_mask"], "0x0007DEE4")
        self.assertEqual(len(report["blueprints"]["all_grant_ids"]), 13)
        self.assertEqual(report["cheats"]["state_base"], "0x86f8")
        self.assertEqual(report["cheats"]["score_offset"], "0x8708")
        self.assertEqual(report["cheats"]["enable_all"]["score_written"], 840)

    def test_definition_ids_counts_and_thresholds(self):
        report = TOOL.inspect(ELF)
        catalog = report["cheats"]["catalog"]
        self.assertEqual([c["id"] for c in catalog], list(range(14)))
        self.assertEqual([c["score_requirement"] for c in catalog], [25, 50, 75, 100, 150, 200, 250, 300, 350, 400, 450, 500, 600, 750])
        self.assertEqual([c["state_count"] for c in catalog], [1, 4, 1, 3, 1, 2, 1, 5, 1, 2, 1, 2, 1, 1])
        for c in catalog:
            self.assertEqual(len(c["state_name_lookup_ids"]), 8)
            self.assertEqual(int(c["state_offset"], 0), 0x86F8 + c["id"])

    def fixture(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 0x14, i)
        return data

    def test_unknown_bits_unusual_states_and_score_remain_unchanged(self):
        data = self.fixture()
        struct.pack_into(">I", data, 0x86F4, 0x8007DEE4)
        data[0x86F8:0x8706] = bytes([255] * 14)
        data[0x8706:0x8708] = b"\xAB\xCD"
        struct.pack_into(">I", data, 0x8708, 0xFFFFFFFF)
        with tempfile.TemporaryDirectory(prefix="tod-bonus-test-") as temporary:
            path = Path(temporary) / "GAME.SAV"
            path.write_bytes(data)
            actual = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual(actual["blueprint_mask"], "0x8007DEE4")
            self.assertEqual(actual["native_blueprint_count"], 14)
            self.assertEqual(actual["outside_grant_mask"], "0x80000000")
            self.assertTrue(actual["all_grant_bits_present"])
            self.assertEqual(actual["states"], [255] * 14)
            self.assertEqual(actual["score"], 0xFFFFFFFF)
            self.assertEqual(actual["uninterpreted_8706_8707"], "ABCD")
            self.assertEqual(path.read_bytes(), data)

    def test_missing_blueprint_bits_not_repaired(self):
        data = self.fixture()
        struct.pack_into(">I", data, 0x86F4, 1 << 2)
        with tempfile.TemporaryDirectory(prefix="tod-bonus-test-") as temporary:
            path = Path(temporary) / "GAME.SAV"
            path.write_bytes(data)
            actual = TOOL.inspect(ELF, path)["save_observation"]
            self.assertFalse(actual["all_grant_bits_present"])
            self.assertEqual(actual["native_blueprint_count"], 1)
            self.assertEqual(path.read_bytes(), data)

    def test_refuses_wrong_size_nonplaintext_and_modified_elf(self):
        with tempfile.TemporaryDirectory(prefix="tod-bonus-test-") as temporary:
            path = Path(temporary) / "bad.bin"
            for data in (b"not a save", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)
            data = bytearray(ELF.read_bytes())
            data[0x17384] ^= 1
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                TOOL.inspect(path)

    def test_actual_inputs_unchanged_and_observations_match_bytes(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual observations")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        actual = TOOL.inspect(ELF, SAVE)["save_observation"]
        data = SAVE.read_bytes()
        mask = struct.unpack_from(">I", data, 0x86F4)[0]
        self.assertEqual(actual["native_blueprint_count"], mask.bit_count())
        self.assertEqual(actual["states"], list(data[0x86F8:0x8706]))
        self.assertEqual(actual["score"], struct.unpack_from(">I", data, 0x8708)[0])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
