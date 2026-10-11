"""Bounded first-person exit evidence, callback qualifications and immutable inputs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("option_producers", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodOptionProducers.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i * 0x14, i)
    return data


class BoundedSelectionChecks(unittest.TestCase):
    def test_latch_full_byte_not_new_saved_word(self):
        self.assertEqual(TOOL.latched_cleanup_mode(0), 0x10)
        for latch in (1, 2, 128, 255):
            self.assertEqual(TOOL.latched_cleanup_mode(latch), 0x0F)
        # There is deliberately no current saved-word argument to this helper.
        self.assertEqual(TOOL.latched_cleanup_mode(runtime_byte=1), 0x0F)

    def test_latch_rejects_non_byte_values(self):
        for value in (-1, 256, 1.0, True, None):
            with self.assertRaisesRegex(ValueError, "unsigned byte"):
                TOOL.latched_cleanup_mode(value)

    def test_wildcard_selects_all_matching_snapshot_records(self):
        pairs = [(1, i) for i in range(16)]
        pairs[0], pairs[4], pairs[15] = (0xF, 9), (0xF, 0), (0xF, 0xFFFFFFFF)
        before = list(pairs)
        result = TOOL.cleanup_selection(0xF, 0, 0xF, 12, pairs)
        self.assertEqual(result["matching_indices"], [0, 4, 15])
        self.assertTrue(result["pending_mode_clear"])
        self.assertEqual(pairs, before)
        self.assertIn("callback effects", result["warning"])

    def test_selector_requires_mode_and_selector_match(self):
        pairs = [(1, 9)] * 16
        pairs[1], pairs[7], pairs[8] = (0x10, 9), (0x10, 8), (0x10, 9)
        result = TOOL.cleanup_selection(0x10, 9, 0x10, 8, pairs)
        self.assertEqual(result["matching_indices"], [1, 8])
        self.assertFalse(result["pending_mode_clear"])
        self.assertTrue(TOOL.cleanup_selection(0x10, 9, 0x10, 9, pairs)["pending_mode_clear"])
        self.assertFalse(TOOL.cleanup_selection(0x10, 0, 0xF, 9, pairs)["pending_mode_clear"])

    def test_bounded_selection_rejects_malformed_inputs(self):
        pairs = [(1, 0)] * 16
        for bad in (pairs[:15], pairs + [(1, 0)], [(1,)] * 16, [(True, 0)] * 16, [(-1, 0)] * 16):
            with self.assertRaises(ValueError):
                TOOL.cleanup_selection(0xF, 0, 0xF, 0, bad)
        for value in (-1, 0x100000000, 1.0, True):
            with self.assertRaisesRegex(ValueError, "unsigned32"):
                TOOL.cleanup_selection(value, 0, 1, 0, pairs)


class ExactOptionProducerChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build verification")

    def test_entry_exit_method_slots_and_cleanup_target(self):
        report = TOOL.inspect(ELF)
        self.assertEqual([(p["method_table_va"], p["exit_va"], p["runtime_latch_member"], p["exit_table_offset"]) for p in report["exit_paths"]],
                         [("0x84af18", "0x20f1f8", "0x24", "0x20"), ("0x84af48", "0x2112d8", "0x3f", "0x20")])
        self.assertEqual(report["exit_rule"]["cleanup_native_va"], "0x63a748")
        self.assertEqual(report["exit_rule"]["selector_argument"], 0)
        self.assertEqual(len(report["recommended_annotations"]), 3)

    def test_cleanup_order_and_callback_boundary(self):
        cleanup = TOOL.inspect(ELF)["cleanup"]
        self.assertEqual(cleanup["record_count"], 16)
        self.assertEqual(cleanup["record_stride"], "0x200")
        self.assertIn("Snapshot occurs after the first callback", cleanup["callback_sequence"])
        self.assertIn("not a guarantee of final mode1", cleanup["post_state_boundary"])
        self.assertIn("continues across matching records", cleanup["matching_rule"])
        self.assertIn("does not clear20C4", cleanup["pending_rule"])

    def test_qualifications_and_opaque_unknowns(self):
        report = TOOL.inspect(ELF)
        self.assertIsNone(report["field"]["semantic_name"])
        self.assertIn("not an exhaustive absence proof", report["field"]["producer_boundary"])
        self.assertIn("null683F0", report["exit_rule"]["qualification"])
        self.assertIn("Runtime actor-state exclusion", report["exit_rule"]["qualification"])
        self.assertIn("not saved-root+114C0", report["exit_rule"]["separate_runtime_offset"])
        self.assertEqual(report["opaque_tail"]["semantic_names"], [None, None])
        self.assertEqual(report["opaque_tail"]["leaf_unwritten_members"], ["0x2e", "0x2f"])
        self.assertIn("not exhaustively proven", report["exit_rule"]["scope"])

    def test_guard_opcodes_and_rejection(self):
        report = TOOL.inspect(ELF)
        guards = {int(g["va"], 0): bytes.fromhex(g["bytes"]) for g in report["instruction_guards"]}
        self.assertEqual(guards[0x1039C], bytes.fromhex("4862A3AC"))
        self.assertEqual(guards[0x63A820], bytes.fromhex("83BF0068"))
        self.assertEqual(guards[0x84AF18][-4:], bytes.fromhex("008674B0"))
        self.assertEqual(guards[0x8674B0], bytes.fromhex("0020F1F80088FF38"))
        original = TOOL.BINDINGS["Elf"]

        class ChangedOpcode(original):
            def u32(self, address):
                value = super().u32(address)
                return value ^ 1 if address == 0x63A820 else value

        with patch.dict(TOOL.BINDINGS, {"Elf": ChangedOpcode}):
            with self.assertRaisesRegex(ValueError, "0x63a820"):
                TOOL.inspect(ELF)

    def test_raw_word_and_tail_preserved_without_runtime_assertion(self):
        with tempfile.TemporaryDirectory(prefix="tod-option-producers-") as folder:
            path = Path(folder) / "GAME.bin"
            for word in (0, 1, 2, 0x100, 0x80000000, 0xFFFFFFFF):
                data = fixture()
                struct.pack_into(">I", data, 0x114C0, word)
                data[0x114D6:0x114D8] = b"\xab\xcd"
                path.write_bytes(data)
                observation = TOOL.inspect(ELF, path)["save_observation"]
                self.assertEqual(observation["word_raw_hex"], f"{word:08X}")
                self.assertEqual(observation["opaque_tail_raw_hex"], "ABCD")
                self.assertEqual(observation["hypothetical_entry_latch"], int(word == 0))
                self.assertEqual(observation["qualified_exit_mode_if_latch_unchanged"], "0xf" if word == 0 else "0x10")
                self.assertIn("not the actual runtime latch", observation["warning"])
                self.assertEqual(path.read_bytes(), data)

    def test_rejects_wrong_plaintext_or_elf(self):
        with tempfile.TemporaryDirectory(prefix="tod-option-invalid-") as folder:
            path = Path(folder) / "invalid.bin"
            for data in (b"bad", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_snapshot_and_inputs_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual detached snapshot")
        before = [hashlib.sha256(path.read_bytes()).digest() for path in (ELF, SAVE)]
        report = TOOL.inspect(ELF, SAVE)
        self.assertEqual(report["save_observation"]["word"], 1)
        raw = SAVE.read_bytes()
        self.assertEqual(report["save_observation"]["opaque_tail_raw_hex"], raw[0x114D6:0x114D8].hex().upper())
        self.assertEqual(before, [hashlib.sha256(path.read_bytes()).digest() for path in (ELF, SAVE)])

    def test_reproduces_embedded_native_map(self):
        mapping = json.loads(TOOL.BINDINGS["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(TOOL.inspect(ELF), mapping["option_producers"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
