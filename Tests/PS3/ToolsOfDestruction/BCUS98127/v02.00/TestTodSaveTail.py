"""Exact-build tail lifecycle, retained median provenance and immutable snapshots."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("tail", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSaveTail.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i * 0x14, i)
    return data


class SaveTailChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build verification")

    def test_reproduces_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(TOOL.inspect(ELF), mapping["save_tail"])

    def test_native_replay_does_not_claim_deaths_or_player_facing_mode(self):
        report = TOOL.inspect(ELF)
        self.assertEqual(report["tail_words"]["cli_option"], "-replay")
        self.assertEqual(report["tail_words"]["restart_offset"], "0x906ec")
        self.assertIn("not a localized Challenge Mode", report["warning"])
        self.assertIn("does not name906E4", report["tail_words"]["initializer_rule"])
        self.assertEqual(report["restart_lifecycle"]["reset_inventory_ids"], [24, 26, 27, 28, 29, 30, 31])
        self.assertEqual(int(report["restart_lifecycle"]["grid_blocks_preserved"]["end_exclusive"], 0), 0x114D8 + 21 * 0x60DC)

    def test_unsigned_increment_wrap_and_cap(self):
        for before, after in ((0, 1), (3, 4), (999, 1000), (1000, 1000),
                              (0x80000000, 1000), (0xFFFFFFFE, 1000), (0xFFFFFFFF, 0)):
            self.assertEqual(TOOL.restart_increment_preview(before), after)
        for invalid in (-1, 0x100000000, True, 3.0):
            with self.assertRaises(ValueError):
                TOOL.restart_increment_preview(invalid)

    def test_raw_words_nonfinite_historical_value_and_last_segment_boundary(self):
        data = fixture()
        struct.pack_into(">3I", data, 0x906E4, 0xDEADBEEF, 0xFFFFFFFF, 0xFFFFFFFF)
        struct.pack_into(">I", data, 0x8754, 0x7FC12345)
        struct.pack_into(">f", data, 0x494 + 19 * 0x408 + 9 * 0x30, 2.0)
        with tempfile.TemporaryDirectory(prefix="tod-tail-fixture-") as folder:
            path = Path(folder) / "GAME.bin"
            path.write_bytes(data)
            observation = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual([w["value"] for w in observation["tail_words"]], [0xDEADBEEF, 0xFFFFFFFF, 0xFFFFFFFF])
            self.assertEqual(observation["restart_increment_arithmetic_preview"], 0)
            self.assertTrue(observation["engine_replay_predicate"])
            self.assertEqual(observation["first_restart_time_median_raw_hex"], "7FC12345")
            self.assertEqual(observation["first_restart_time_median"], "nan")
            self.assertEqual(observation["currently_positive_completion_times"], 1)
            self.assertEqual(path.read_bytes(), data)

    def test_empty_median_is_not_recomputed_or_defaulted(self):
        data = fixture()
        struct.pack_into(">f", data, 0x8754, 12.5)
        with tempfile.TemporaryDirectory(prefix="tod-tail-empty-") as folder:
            path = Path(folder) / "GAME.bin"
            path.write_bytes(data)
            report = TOOL.inspect(ELF, path)
            self.assertEqual(report["save_observation"]["currently_positive_completion_times"], 0)
            self.assertEqual(report["save_observation"]["first_restart_time_median"], 12.5)
            self.assertIn("No native empty-count guard", report["first_restart_time_median"]["empty_input_caveat"])
            self.assertEqual(path.read_bytes(), data)

    def test_rejects_invalid_inputs(self):
        with tempfile.TemporaryDirectory(prefix="tod-tail-invalid-") as folder:
            path = Path(folder) / "invalid.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_save_historical_aggregate_and_inputs_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual snapshot verification")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observation = TOOL.inspect(ELF, SAVE)["save_observation"]
        self.assertEqual([w["value"] for w in observation["tail_words"]], [0, 0, 3])
        self.assertEqual(observation["first_restart_time_median_raw_hex"], "408F17AB")
        self.assertAlmostEqual(observation["first_restart_time_median"], 4.471639156341553)
        self.assertEqual(observation["currently_positive_completion_times"], 0)
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
