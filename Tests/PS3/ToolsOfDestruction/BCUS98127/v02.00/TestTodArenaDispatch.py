"""Reproduce bounded runtime routing and arena script writers without Lua execution."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodArenaDispatch.py"))
ELF = ARCHIVE = SAVE = None


class ArenaDispatchNativeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ELF is None:
            raise unittest.SkipTest("Pass --elf for exact native reproduction")
        cls.elf = TOOL["BINDINGS"].Elf(ELF)
        cls.report = TOOL["inspect"](ELF)

    def test_native_guards_and_runtime_request_not_saved_record(self):
        self.assertEqual(len(self.report["instruction_guards"]), 110)
        for guard in self.report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(self.elf.read(int(guard["va"], 0), len(raw)), raw)
        request = self.report["request_constructor"]
        self.assertEqual([row["offset"] for row in request["members"]],
                         ["0x8", "0x10", "0x14", "0x18", "0x1c", "0x20", "0x24"])
        self.assertIn("not serialized", request["warning"])

    def test_operation_routes_concrete_loader_and_alias_gap(self):
        dispatch = self.report["operation_dispatch"]
        self.assertEqual([int(row["target_va"], 0) for row in dispatch["routes"]],
                         [0x24734, 0x248D8, 0x24880, 0x249A8, 0x24974, 0x24940, 0x2490C, 0x248D8])
        self.assertEqual(dispatch["arena_operation"], 5)
        self.assertEqual(dispatch["loader"]["function_va"], "0x62d2e8")
        self.assertEqual(dispatch["loader"]["toc_va"], "0x8afe5c")
        self.assertIn("not installation or aliasing", dispatch["alias_gap"])
        self.assertIn("current-display-row", dispatch["alias_gap"])
        annotation = next(row for row in self.report["recommended_annotations"] if row["va"] == "0x24714")
        self.assertEqual(annotation["kind"], "data")
        self.assertEqual(annotation["size"], 8 * 4)

    def test_named_setters_independent_serialized_fields(self):
        chains = self.report["serialized_writer_chains"]
        self.assertEqual([(row["name"], row["wrapper_va"], row["native_va"]) for row in chains["named_bindings"]],
                         [("set_challenge_success", "0x2c9ca8", "0x27a9c8"),
                          ("set_flag", "0x34698", "0x24a80"), ("set_flag", "0x2cb080", "0x27bb10")])
        self.assertEqual(chains["success_counter"]["increment_store_vas"], ["0x27aad0", "0x27ab50"])
        self.assertEqual(chains["global_flag"]["store_vas"], ["0x24aa8", "0x27bb38"])
        self.assertEqual([row["id"] for row in chains["milestone_flags"]], [74, 75, 85, 88, 89])
        self.assertEqual([row["word_bit"] for row in chains["milestone_flags"]], [10, 11, 21, 24, 25])
        self.assertTrue(all(row["word_offset"] == "0x5530" for row in chains["milestone_flags"]))
        self.assertEqual([row["native_id"] for row in chains["challenges"]], [1, 4, 6, 12])

    def test_synthetic_flags_and_raw_signed_counters_remain_independent(self):
        raw = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", raw, i * 20, i)
        with tempfile.TemporaryDirectory(prefix="tod-arena-dispatch-synthetic-") as directory:
            path = Path(directory) / "synthetic-plaintext.bin"
            for word in [0, (1 << 10) | (1 << 25), sum(1 << i for i in [10, 11, 21, 24, 25])]:
                struct.pack_into(">Q", raw, 0x5530, word)
                for identifier, value in zip([1, 4, 6, 12], [0, 1, 0x80000000, 0xFFFFFFFF]):
                    struct.pack_into(">I", raw, 0x56D8 + identifier * 4, value)
                path.write_bytes(raw)
                observation = TOOL["inspect"](ELF, save_path=path)["save_observation"]
                self.assertEqual([row["set"] for row in observation["milestone_flags"]],
                                 [bool(word & (1 << bit)) for bit in [10, 11, 21, 24, 25]])
                self.assertEqual([row["signed_value"] for row in observation["counters"]], [0, 1, -2147483648, -1])
                self.assertIn("no current operation/script/menu", observation["warning"])

    def test_size_preflight_before_read_and_encrypted_layout_rejected(self):
        with tempfile.TemporaryDirectory(prefix="tod-arena-dispatch-invalid-") as directory:
            path = Path(directory) / "invalid.bin"
            path.write_bytes(b"short")
            original_read = Path.read_bytes
            def reject_short_save_read(candidate):
                if candidate == path:
                    raise AssertionError("Short save must not be read")
                return original_read(candidate)
            with patch.object(Path, "read_bytes", reject_short_save_read):
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, save_path=path)
            path.write_bytes(bytes(0x906F0))
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF, save_path=path)
            with self.assertRaises(ValueError):
                TOOL["inspect"](path)

    def test_original_snapshot_is_read_only(self):
        if SAVE is None:
            self.skipTest("Pass --save for supplied plaintext observation")
        before = hashlib.sha256(Path(SAVE).read_bytes()).digest()
        observation = TOOL["inspect"](ELF, save_path=SAVE)["save_observation"]
        raw = Path(SAVE).read_bytes()
        self.assertEqual(observation["plaintext_sha256"], before.hex().upper())
        self.assertEqual(hashlib.sha256(raw).digest(), before)
        for row in observation["milestone_flags"]:
            word = struct.unpack_from(">Q", raw, int(row["word_offset"], 0))[0]
            self.assertEqual(row["set"], bool(word & (1 << row["word_bit"])))
        for row in observation["counters"]:
            self.assertEqual(row["signed_value"], struct.unpack_from(">i", raw, int(row["offset"], 0))[0])

    def test_embedded_native_and_asset_reports(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        if "arena_dispatch" not in mapping:
            self.skipTest("Parent has not integrated isolated arena_dispatch yet")
        self.assertEqual(self.report, mapping["arena_dispatch"])
        if ARCHIVE is not None:
            self.assertEqual(TOOL["inspect_assets"](ARCHIVE), mapping["arena_dispatch_assets"])


class ArenaDispatchAssetChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ARCHIVE is None:
            raise unittest.SkipTest("Pass --archive for original source/compiled evidence")
        psarc = TOOL["MENU"]["module"]("test_arena_dispatch_psarc", "Inspect-Psarc.py")
        archive = psarc.Psarc(ARCHIVE)
        cls.payloads = {}
        for script, definitions in TOOL["ASSETS"].items():
            for extension, prefix in [("lua", TOOL["PREFIX"]), ("lc", TOOL["BUILT"])]:
                name = prefix + script + "." + extension
                cls.payloads[name] = archive.read_entry(archive.names.index(name), definitions[extension][0])
        cls.before = {name: hashlib.sha256(raw).digest() for name, raw in cls.payloads.items()}
        cls.report = TOOL["inspect_asset_bytes"](cls.payloads)

    def test_fingerprinted_source_and_compiled_ranges(self):
        self.assertEqual(len(self.report["assets"]), 8)
        self.assertEqual(len(self.report["compiled_root_digests"]), 4)
        self.assertEqual(len(self.report["asset_byte_guards"]), 14)
        for guard in self.report["asset_byte_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            offset = int(guard["offset"], 0)
            self.assertEqual(self.payloads[guard["archive_entry"]][offset:offset + len(raw)], raw)

    def test_three_counter_before_flag_writers_and_inverse_timeout_case(self):
        writers = self.report["saved_milestone_writers"]
        self.assertEqual([row["native_id"] for row in writers], [1, 4, 6, 12])
        self.assertEqual([row["milestone_flag_id"] for row in writers], [74, 75, 88, 89])
        self.assertEqual([[action["call_pc"] for action in row["ordered_actions"]] for row in writers],
                         [[626, 638], [230, 309, 325], [710, 721], [231, 290, 306]])
        self.assertEqual([row["ordered_actions"][0]["api"] for row in writers],
                         ["set_challenge_success", "set_challenge_success", "set_flag", "set_challenge_success"])
        self.assertIn("timer_timeup is false", writers[2]["milestone_condition"])
        self.assertTrue(all("flag is clear" in writers[i]["milestone_condition"] for i in [0, 1, 3]))

    def test_literal_wait_index_distinction_and_separate_dependencies(self):
        ordering = self.report["flag_before_counter_case"]
        self.assertEqual((ordering["flag_call_pc"], ordering["wait_call_pc"], ordering["counter_call_pc"]), (710, 718, 721))
        self.assertEqual(ordering["wait_literal"], 6.0)
        self.assertIn("not reconstructed engine timing", ordering["warning"])
        self.assertIn("not an atomic transaction", self.report["separate_state_warning"])
        self.assertIn("challenge10", self.report["index_warning"])
        self.assertIn("no menu-row equality", self.report["index_warning"])

    def test_all_source_and_compiled_mutations_and_missing_assets_rejected(self):
        for name in self.payloads:
            changed = copy.copy(self.payloads)
            raw = bytearray(changed[name]); raw[-1] ^= 1; changed[name] = raw
            with self.assertRaises(ValueError):
                TOOL["inspect_asset_bytes"](changed)
        with self.assertRaises(ValueError):
            TOOL["inspect_asset_bytes"]({})
        self.assertEqual({name: hashlib.sha256(raw).digest() for name, raw in self.payloads.items()}, self.before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, ARCHIVE, SAVE = args.elf, args.archive, args.save
    unittest.main(argv=[__file__] + remaining)
