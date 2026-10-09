"""Exact-build reward cache, typed ladder state and immutable snapshot checks."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("rewards", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodRewardChannels.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i * 0x14, i)
    return data


class RewardChannelChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(TOOL.inspect(ELF), mapping["reward_channels"])

    def test_channels_cache_members_and_native_multipliers(self):
        report = TOOL.inspect(ELF)
        self.assertEqual([c["name"] for c in report["channels"]], ["experience", "bolts", "raritanium"])
        self.assertEqual([c["segment_cached_total_member"] for c in report["channels"]], ["0x1c", "0x20", "0x24"])
        self.assertIn("weapon", report["channels"][0]["evidence"])
        self.assertIn("not heroXP418", report["channels"][0]["evidence"])
        self.assertEqual(report["ladder"]["multipliers"], [1.0, 0.75, 0.5, 0.25, 0.0])
        self.assertEqual(report["ladder"]["maximum_written_index"], 4)
        self.assertEqual(report["ordinary_segment_scaling"]["threshold_ratios"], [1.0, 1.75, 2.25])
        self.assertIn("minimum1", report["ladder"]["raritanium_return_rule"])
        self.assertIn("One threshold per call", report["ladder"]["commit_rule"])

    def test_unsigned_indices_nonfinite_float_bits_unknown_bytes_last_world(self):
        data = fixture()
        base = 0x488 + 19 * 0x408
        struct.pack_into(">I", data, base+0x3F0, 0xFFFFFFFF)
        struct.pack_into(">I", data, base+0x3F4, 7)
        struct.pack_into(">I", data, base+0x3F8, 0x7FC12345)
        struct.pack_into(">I", data, base+0x3FC, 0xFF800000)
        data[base+0x403] = 0xAB
        data[base+0x3EC:base+0x3F0] = bytes.fromhex("DEADBEEF")
        data[base+0x404:base+0x408] = bytes.fromhex("11223344")
        with tempfile.TemporaryDirectory(prefix="tod-reward-test-") as folder:
            path = Path(folder) / "GAME.bin"
            path.write_bytes(data)
            observed = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual(len(observed["worlds"]), 20)
            world = observed["worlds"][-1]
            self.assertEqual(world["offset"], hex(base))
            self.assertTrue(world["indices_outside_verified_table"])
            values = world["values"]
            self.assertEqual(values["bolts_reward_ladder_index"]["value"], "4294967295")
            self.assertEqual(values["bolts_reward_ladder_remainder"]["bits"], "7FC12345")
            self.assertEqual(values["raritanium_reward_ladder_remainder"]["bits"], "FF800000")
            self.assertEqual(values["reward_cache_ready"]["value"], "171")
            self.assertEqual(world["unknown_word_3ec"], "DEADBEEF")
            self.assertEqual(world["unknown_tail"], "11223344")
            json.dumps(observed, allow_nan=False)
            self.assertEqual(path.read_bytes(), data)

    def test_cache_ready_does_not_normalize_cache_or_wallet(self):
        data = fixture()
        struct.pack_into(">f", data, 0x488+0x3E4, 123.5)
        struct.pack_into(">I", data, 0x41C, 999)
        with tempfile.TemporaryDirectory(prefix="tod-reward-cache-") as folder:
            path = Path(folder) / "GAME.bin"
            for ready in (0, 1, 255):
                data[0x488+0x403] = ready
                path.write_bytes(data)
                values = TOOL.inspect(ELF, path)["save_observation"]["worlds"][0]["values"]
                self.assertEqual(values["cached_bolts_reward_total"]["value"], "123.5")
                self.assertEqual(values["reward_cache_ready"]["value"], str(ready))
                self.assertEqual(path.read_bytes(), data)

    def test_rejects_bad_inputs(self):
        with tempfile.TemporaryDirectory(prefix="tod-reward-invalid-") as folder:
            path = Path(folder) / "input.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_snapshot_matches_bytes_and_sources_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual snapshot validation")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observed = TOOL.inspect(ELF, SAVE)["save_observation"]
        data = SAVE.read_bytes()
        for world in observed["worlds"]:
            base = int(world["offset"], 0)
            for offset, name in ((0x3F0, "bolts_reward_ladder_index"), (0x3F4, "raritanium_reward_ladder_index")):
                self.assertEqual(world["values"][name]["value"], str(struct.unpack_from(">I", data, base+offset)[0]))
                self.assertEqual(world["values"][name]["value"], "0")
            for offset, name in ((0x3E0, "cached_experience_reward_total"), (0x3E4, "cached_bolts_reward_total"), (0x3E8, "cached_raritanium_reward_total"), (0x3F8, "bolts_reward_ladder_remainder"), (0x3FC, "raritanium_reward_ladder_remainder")):
                self.assertEqual(world["values"][name]["bits"], data[base+offset:base+offset+4].hex().upper())
                self.assertEqual(world["values"][name]["bits"], "00000000")
        self.assertEqual(observed["restart_counter"], 3)
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
