"""Reproduce the arena queue API boundary without native/Lua execution."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodArenaBinding.py"))
ELF = SAVE = None


class ArenaBindingChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ELF is None:
            raise unittest.SkipTest("Pass --elf for exact native reproduction")
        cls.elf = TOOL["BINDINGS"]["Elf"](ELF)
        cls.report = TOOL["inspect"](ELF)

    def test_guards_and_api_registration_are_exact(self):
        self.assertEqual(len(self.report["instruction_guards"]), 29)
        for guard in self.report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(self.elf.read(int(guard["va"], 0), len(raw)), raw)
        binding = self.report["queue_binding"]
        self.assertEqual(binding["name"], "queue_arena_challenge_screen")
        self.assertEqual(binding["registration_slot_va"], "0x89d8ac")
        self.assertEqual(binding["wrapper_va"], "0x2ca1d8")
        self.assertEqual(binding["diagnostic_identifier"], "select_arena_challenge")
        self.assertIn("does not establish", binding["distinction"])

    def test_argument_domain_arity_and_native_boundary(self):
        binding = self.report["queue_binding"]
        self.assertEqual([row["position"] for row in binding["arguments"]], [1, 2])
        self.assertIn("moby_handle", binding["arguments"][0]["meaning"])
        self.assertIn("string-compatible", binding["arguments"][1]["meaning"])
        self.assertIn("rejects a present third", binding["arity"])
        self.assertIn("not an asserted strict", binding["arity"])
        self.assertIn("does not preserve/read incomingr4", binding["native_argument_boundary"])
        self.assertEqual(self.elf.u32(0x282B30), 0x388000B9)  # first body use of r4 is overwrite
        self.assertEqual(self.elf.u32(0x282B80), 0x38800005)
        self.assertEqual(self.elf.u32(0x282B88), 0x38A00000)
        self.assertEqual(self.elf.u32(0x282B8C), 0x38C00000)
        self.assertIn("no assertion", binding["validation_scope"])

    def test_toc_changing_thunks_target_guarded_validators(self):
        for thunk, target in [(0x252288, 0x6A5C68), (0x24FAB8, 0x6A9E78), (0x252BE8, 0x6A5FC8)]:
            word = self.elf.u32(thunk + 12)
            self.assertEqual(TOOL["BINDINGS"]["branch_target"](word, thunk + 12), target)
            self.assertFalse(word & 1)

    def test_runtime_setters_write_distinct_words_not_saved_fields(self):
        resource = self.report["loader_resource_ownership"]
        self.assertEqual(resource["runtime_resource_owner_va"], "0x107225cc")
        self.assertEqual(self.elf.u32(0x632714), 0x90690000)  # stw r3,0(r9)
        self.assertIn("owner+4", resource["companion_store"])
        self.assertIn("clears owner+8", resource["companion_store"])
        self.assertIn("does not perform", resource["companion_store"])
        self.assertIn("107225D8+14/+18", resource["context_setup"])
        self.assertIn("not GAME.SAV offsets", resource["warning"])
        self.assertEqual(len(self.report["recommended_annotations"]), 4)
        self.assertTrue(all(row["kind"] == "function" for row in self.report["recommended_annotations"]))
        self.assertTrue(any("No new serialized save field" in text for text in self.report["unresolved"]))

    def test_embedded_report_reproduces(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        if "arena_binding" not in mapping:
            self.skipTest("Parent has not integrated isolated arena_binding yet")
        self.assertEqual(self.report, mapping["arena_binding"])

    def test_actual_snapshot_remains_read_only(self):
        if SAVE is None:
            self.skipTest("Pass --save for supplied plaintext observation")
        before = Path(SAVE).read_bytes()
        report = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(Path(SAVE).read_bytes(), before)
        self.assertEqual(report["plaintext_sha256"], hashlib.sha256(before).hexdigest().upper())
        self.assertEqual(len(report["counters"]), 23)
        for row in report["counters"]:
            self.assertEqual(row["signed_value"], struct.unpack_from(">i", before, int(row["offset"], 0))[0])
        self.assertIn("No saved queue string", report["warning"])

    def test_synthetic_raw_signed_counter_boundaries_no_runtime_reconstruction(self):
        raw = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", raw, i * 20, i)
        for i, value in enumerate([0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF]):
            struct.pack_into(">I", raw, 0x56D8 + i * 4, value)
        struct.pack_into(">I", raw, 0x5734, 0xFE123456)
        before = bytes(raw)
        observation = TOOL["observe_save_bytes"](raw)
        self.assertEqual([row["signed_value"] for row in observation["counters"][:5]], [0, 1, 2147483647, -2147483648, -1])
        self.assertEqual(observation["counters"][-1]["native_id"], 22)
        self.assertEqual(observation["counters"][-1]["offset"], "0x5730")
        self.assertNotIn("runtime_resource_owner", observation)
        self.assertEqual(bytes(raw), before)

    def test_invalid_layout_size_preflight_and_mutated_native_rejected(self):
        for value in [None, {}, [], "text", b"short", bytes(0x906F0)]:
            with self.assertRaises(ValueError):
                TOOL["observe_save_bytes"](value)
        with tempfile.TemporaryDirectory(prefix="tod-arena-binding-invalid-") as directory:
            path = Path(directory) / "short.bin"
            path.write_bytes(b"short")
            original_read = Path.read_bytes
            def reject_save_read(candidate):
                if candidate == path:
                    raise AssertionError("Short save must fail before read")
                return original_read(candidate)
            with patch.object(Path, "read_bytes", reject_save_read):
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)
            with self.assertRaises(ValueError):
                TOOL["inspect"](path)
        OriginalElf = TOOL["BINDINGS"]["Elf"]
        class ChangedElf(OriginalElf):
            def read(self, address, size):
                raw = super().read(address, size)
                if address == 0x2CA1D8 and size == 0x120:
                    raw = bytes([raw[0] ^ 1]) + raw[1:]
                return raw
        with patch.dict(TOOL["BINDINGS"], {"Elf": ChangedElf}):
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
