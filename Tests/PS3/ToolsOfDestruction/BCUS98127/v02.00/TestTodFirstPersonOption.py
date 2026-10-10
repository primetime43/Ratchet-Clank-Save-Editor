"""Saved first-person option branches, camera coupling and immutable raw bits."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("first_person", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodFirstPersonOption.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i * 0x14, i)
    return data


class FirstPersonOptionChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build verification")

    def test_reproduces_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(TOOL.inspect(ELF), mapping["first_person_option"])

    def test_two_method_tables_and_conditional_calls(self):
        report = TOOL.inspect(ELF)
        self.assertEqual([(p["method_table_va"], p["entry_va"], p["update_va"], p["runtime_flag_offset"]) for p in report["state_paths"]],
                         [("0x84af18", "0x20f3f0", "0x20f598", "0x24"),
                          ("0x84af48", "0x2108d8", "0x210b80", "0x3f")])
        self.assertEqual(report["mode_selection"]["zero_word_request"], "0x0f")
        self.assertEqual(report["mode_selection"]["nonzero_word_request"], "0x10")
        self.assertEqual(report["update_coupling"]["orientation_adjust_va"], "0x778c8")
        guards = {int(g["va"], 0): bytes.fromhex(g["bytes"]) for g in report["instruction_guards"]}
        for address, word in ((0x20F81C, 0x418600EC), (0x2110E0, 0x4086FC20)):
            self.assertEqual(guards[address], word.to_bytes(4, "big"))
        self.assertIn("scans16", report["update_coupling"]["lookup_rule"])

    def test_not_named_hold_toggle_or_runtime_acceptance(self):
        report = TOOL.inspect(ELF)
        self.assertIsNone(report["field"]["semantic_name"])
        self.assertIn("not the saved word again", report["field"]["scope"])
        self.assertIn("reject", report["mode_selection"]["qualification"])
        self.assertIn("does not guarantee execution", report["update_coupling"]["nonzero_word"])
        self.assertIn("not a direct save-field write", report["update_coupling"]["orientation_rule"])
        self.assertIn("No guarded input activation/release", report["update_coupling"]["unresolved"])

    def test_full_word_zero_test_and_unknown_tail_preservation(self):
        with tempfile.TemporaryDirectory(prefix="tod-first-person-flags-") as folder:
            path = Path(folder) / "GAME.bin"
            for value in (0, 1, 2, 0x100, 0x80000000, 0xFFFFFFFF):
                data = fixture()
                struct.pack_into(">I", data, 0x114C0, value)
                data[0x114D6:0x114D8] = b"\xab\xcd"
                path.write_bytes(data)
                observation = TOOL.inspect(ELF, path)["save_observation"]
                self.assertEqual(observation["word"], value)
                self.assertEqual(observation["raw_hex"], f"{value:08X}")
                self.assertEqual(observation["entry_runtime_flag"], int(value == 0))
                self.assertEqual(observation["orientation_path_permitted"], value != 0)
                self.assertEqual(observation["qualified_mode_request"], "0x0f" if value == 0 else "0x10")
                self.assertEqual(observation["unknown_tail_raw"], "ABCD")
                self.assertEqual(path.read_bytes(), data)

    def test_rejects_invalid_inputs(self):
        with tempfile.TemporaryDirectory(prefix="tod-first-person-invalid-") as folder:
            path = Path(folder) / "invalid.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_snapshot_and_inputs_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual snapshot verification")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observation = TOOL.inspect(ELF, SAVE)["save_observation"]
        self.assertEqual(observation["word"], 1)
        self.assertEqual(observation["entry_runtime_flag"], 0)
        self.assertEqual(observation["qualified_mode_request"], "0x10")
        self.assertTrue(observation["orientation_path_permitted"])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
