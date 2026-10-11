"""Reproduce bounded arena source-list/reward evidence without executing Lua."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodArenaTable.py"))
ELF = ARCHIVE = SAVE = None


class ArenaPureChecks(unittest.TestCase):
    def test_weapon_reward_zero_test_is_not_signed_positive_test(self):
        preview = TOOL["preview_weapon_reward"]
        for weapon in [-1, 0, 1, 24, 30]:
            for raw in [0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF]:
                self.assertEqual(preview(weapon, raw), weapon if weapon > 0 and raw == 0 else -1)
        for args in [(1, -1), (1, 1 << 32), (1 << 31, 0), (True, 0), (1, True)]:
            with self.assertRaises(ValueError):
                preview(*args)

    def test_literal_fold_rejects_calls_and_control_flow(self):
        for op in ["CALL", "JMP", "TAILCALL", "CLOSURE"]:
            function = {"constants": [], "instructions": [{"op": op, "a": 0, "b": 0, "c": 0}]}
            with self.assertRaises(ValueError):
                TOOL["fold_literals"](function, 0, 1)


class ArenaNativeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ELF is None:
            raise unittest.SkipTest("Pass --elf for exact native reproduction")
        cls.elf = TOOL["BINDINGS"].Elf(ELF)
        cls.report = TOOL["inspect"](ELF)

    def test_native_guards_and_named_counter_dependency(self):
        self.assertEqual(len(self.report["instruction_guards"]), 223)
        for guard in self.report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(self.elf.read(int(guard["va"], 0), len(raw)), raw)
        rule = self.report["weapon_reward_getter"]
        self.assertIn("raw uint32 completion count == 0", rule["predicate"])
        self.assertIn("Any nonzero counter", rule["warning"])
        self.assertEqual(rule["counter_load_va"], "0x2741c")
        self.assertEqual(rule["else_result"], -1)

    def test_runtime_selection_and_alias_gap_not_saved_field(self):
        selection = self.report["selection_side_effects"]
        self.assertIn("runtime-only", selection["warning"])
        self.assertIn("source index", selection["ordered_actions"][0])
        self.assertIn("native ID", selection["ordered_actions"][1])
        self.assertIn("does not itself install", self.report["selector_bridge"]["alias_gap"])
        self.assertIn("unrecovered", " ".join(self.report["unresolved"]))

    def test_story_gate_storage_is_independent_flags_not_counters(self):
        flags = self.report["story_flags"]
        self.assertEqual([r["id"] for r in flags], [74, 75, 88, 89])
        self.assertEqual([r["word_offset"] for r in flags], ["0x5530"] * 4)
        self.assertEqual([r["word_bit"] for r in flags], [10, 11, 24, 25])
        self.assertEqual([r["byte_mask"] for r in flags], ["0x4", "0x8", "0x1", "0x2"])

    def test_synthetic_flag_branches_do_not_identify_current_ui(self):
        raw = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", raw, i * 20, i)
        with tempfile.TemporaryDirectory(prefix="tod-arena-table-flags-") as directory:
            path = Path(directory) / "synthetic-plaintext.bin"
            for bits, name in [(0, "first_trip_intro_one"), (1 << 10, "first_trip_intro_two"),
                               ((1 << 10) | (1 << 11), "first_trip_final"), (1 << 11, "first_trip_intro_one")]:
                struct.pack_into(">Q", raw, 0x5530, bits)
                path.write_bytes(raw)
                observation = TOOL["inspect"](ELF, save_path=path)["save_observation"]
                self.assertEqual(observation["first_trip_gate_if_script_loop_reached"], name)
                self.assertIn("not proof", observation["warning"])

    def test_malformed_or_encrypted_layout_rejected(self):
        with tempfile.TemporaryDirectory(prefix="tod-arena-table-invalid-") as directory:
            path = Path(directory) / "invalid.bin"
            for data in [b"short", bytes(0x906F0)]:
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, save_path=path)
            with self.assertRaises(ValueError):
                TOOL["inspect"](path)

    def test_actual_snapshot_read_only(self):
        if SAVE is None:
            self.skipTest("Pass --save for original plaintext observation")
        before = hashlib.sha256(Path(SAVE).read_bytes()).digest()
        observation = TOOL["inspect"](ELF, save_path=SAVE)["save_observation"]
        self.assertEqual(observation["plaintext_sha256"], before.hex().upper())
        raw = Path(SAVE).read_bytes()
        self.assertEqual(observation["signed_counts_by_native_id"], list(struct.unpack_from(">23i", raw, 0x56D8)))
        self.assertEqual(hashlib.sha256(raw).digest(), before)

    def test_embedded_native_and_asset_reproduction(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        if "arena_table" not in mapping:
            self.skipTest("Parent has not integrated isolated arena_table yet")
        self.assertEqual(self.report, mapping["arena_table"])
        if ARCHIVE is not None:
            ids = {r["enum"]: r["id"] for r in self.report["native_challenge_ids"]}
            self.assertEqual(TOOL["inspect_assets"](ARCHIVE, ids), mapping["arena_table_assets"])


class ArenaAssetChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ELF is None or ARCHIVE is None:
            raise unittest.SkipTest("Pass --elf and --archive for compiled source relationships")
        native = TOOL["inspect"](ELF)
        cls.ids = {r["enum"]: r["id"] for r in native["native_challenge_ids"]}
        psarc = TOOL["MENU"]["module"]("test_arena_table_psarc", "Inspect-Psarc.py")
        archive = psarc.Psarc(ARCHIVE)
        cls.payloads = {name: archive.read_entry(archive.names.index(name), size) for name, (size, _) in TOOL["ASSETS"].items()}
        cls.before = {name: hashlib.sha256(raw).digest() for name, raw in cls.payloads.items()}
        cls.report = TOOL["inspect_asset_bytes"](cls.payloads, cls.ids)

    def test_compiled_master_and_reached_source_list_native_id_order(self):
        self.assertEqual(len(self.report["master_descriptors"]), 20)
        lists = self.report["source_lists"]
        self.assertEqual([[r["native_id"] for r in row["rows"]] for row in lists],
                         [[1], [4], [1, 4, 2, 3, 7, 5, 8, 10],
                          [1, 4, 2, 3, 7, 5, 8, 10, 6, 12, 13, 14, 17, 18, 9, 11, 20, 22]])
        self.assertEqual([row["selector_called"] for row in lists], [False, False, True, True])
        self.assertEqual(lists[2]["arena_title_symbol"], "L06_TXT_GPLAY_ROGARTOURN")
        self.assertEqual(lists[3]["arena_title_symbol"], "L06_TXT_GPLAY_MAGNETOURN")

    def test_compiled_gates_signed_positive_and_unused_catalog_rows(self):
        gates = self.report["activation_gates"]
        self.assertEqual(len(gates), 14)
        self.assertTrue(all("signed32" in row["condition"] and "> 0" in row["condition"] for row in gates))
        first = gates[:4]
        self.assertEqual([(row["target_native_id"], row["requires_native_id"]) for row in first],
                         [(7, 2), (5, 3), (8, 7), (10, 5)])
        self.assertEqual(self.report["catalog_exclusions"]["no_compiled_master_descriptor"], ["IFF_B_13", "IFF_B_19"])
        self.assertEqual(self.report["catalog_exclusions"]["master_but_not_reached_return_list"], ["IFF_B_14", "IFF_B_17"])
        self.assertIn("not an extra selectable branch", self.report["unreached_literal"]["warning"])

    def test_original_asset_fingerprints_guards_and_alias_limit(self):
        self.assertEqual(len(self.report["assets"]), 6)
        self.assertEqual(len(self.report["compiled_root_digests"]), 3)
        self.assertEqual(len(self.report["asset_byte_guards"]), 20)
        for guard in self.report["asset_byte_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            offset = int(guard["offset"], 0)
            self.assertEqual(self.payloads[guard["archive_entry"]][offset:offset + len(raw)], raw)
        self.assertIn("not a recovered alias", self.report["alias_warning"])
        self.assertIn("not independently decoded English", self.report["localization_warning"])

    def test_modified_source_compiled_bytes_and_missing_assets_rejected(self):
        for name in [TOOL["PREFIX"] + "arena.lua", TOOL["BUILT"] + "main.lc"]:
            changed = copy.copy(self.payloads)
            raw = bytearray(changed[name]); raw[-1] ^= 1; changed[name] = raw
            with self.assertRaises(ValueError):
                TOOL["inspect_asset_bytes"](changed, self.ids)
        with self.assertRaises(ValueError):
            TOOL["inspect_asset_bytes"]({}, self.ids)
        self.assertEqual({name: hashlib.sha256(raw).digest() for name, raw in self.payloads.items()}, self.before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, ARCHIVE, SAVE = args.elf, args.archive, args.save
    unittest.main(argv=[__file__] + remaining)
