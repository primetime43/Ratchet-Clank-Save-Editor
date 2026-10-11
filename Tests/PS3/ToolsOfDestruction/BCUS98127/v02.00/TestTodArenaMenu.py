"""Static arena menu relationships; optional original inputs are always read-only."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodArenaMenu.py"))
ELF = ARCHIVE = SAVE = None


class ArenaNativeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ELF is None:
            raise unittest.SkipTest("Pass --elf for exact native validation")
        cls.elf = TOOL["BINDINGS"]["Elf"](ELF)
        cls.before = hashlib.sha256(cls.elf.raw).digest()
        cls.report = TOOL["inspect"](ELF)

    def test_native_instruction_guards_and_named_bindings(self):
        self.assertEqual(len(self.report["instruction_guards"]), 31)
        for guard in self.report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(self.elf.read(int(guard["va"], 0), len(expected)), expected)
        self.assertEqual([row["name"] for row in self.report["bindings"]],
                         ["get_num_challenges", "get_times_challenge_completed", "get_default_challenge"])
        self.assertEqual(hashlib.sha256(self.elf.raw).digest(), self.before)

    def test_three_index_spaces_and_metadata_count(self):
        self.assertEqual([row["name"] for row in self.report["index_spaces"]],
                         ["source_index", "native_id", "display_row"])
        count = self.report["count_getter"]
        self.assertEqual(count["table_key"], "num")
        self.assertEqual(count["chain"], ["0x31ef8", "0x26298", "0x13b80", "0x275268"])
        self.assertIn("Neither a literal23", count["meaning"])

    def test_native_id_bounds_do_not_claim_safe_counter_bounds(self):
        resolver = self.report["id_resolver"]
        self.assertEqual(resolver["missing_row_result"], 0)
        self.assertIn("no lower-bound", resolver["conversion"])
        self.assertIn("ID23 addresses5734", resolver["bounds_warning"])
        self.assertIn("signed32", resolver["count_signedness"])
        self.assertEqual(resolver["counter_formula"], "saved56D8 + 4*native_id")

    def test_default_is_inverse_lookup_not_direct_display_index(self):
        default = self.report["default_selection"]
        self.assertEqual(default["runtime_native_id_offset"], "0xd8")
        self.assertEqual(default["inverse_lookup_va"], "0x275438")
        self.assertIn("first non-table", default["meaning"])
        self.assertIn("negative result to0", default["meaning"])
        self.assertIn("does not use table.num", default["warning"])

    def test_unresolved_table_is_not_assumed_identity_order(self):
        limits = " ".join(self.report["unresolved"])
        self.assertIn("same order", limits)
        self.assertIn("snapshot alone cannot reconstruct", limits)
        self.assertNotIn("snapshot", self.report)
        self.assertNotIn("asset_observation", self.report)

    def test_wrong_elf_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="tod-arena-menu-test-") as directory:
            path = Path(directory) / "not-game.elf"
            path.write_bytes(b"not the exact reference ELF")
            with self.assertRaises(ValueError):
                TOOL["inspect"](path)

    def test_reproduces_embedded_map_if_integrated(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        if "arena_menu" not in mapping:
            self.skipTest("Parent has not integrated the isolated arena_menu report yet")
        self.assertEqual(json.loads(json.dumps(self.report)), mapping["arena_menu"])
        if ARCHIVE is not None:
            self.assertEqual(TOOL["inspect_archive"](ARCHIVE), mapping["arena_menu_assets"])

    def test_wrong_length_and_same_length_nonplaintext_saves_rejected(self):
        with tempfile.TemporaryDirectory(prefix="tod-arena-save-test-") as directory:
            path = Path(directory) / "not-save.bin"
            path.write_bytes(b"too short")
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF, save_path=path)
            path.write_bytes(bytes(0x906F0))
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF, save_path=path)

    def test_optional_actual_snapshot_remains_native_id_only(self):
        if SAVE is None:
            self.skipTest("Pass --save for plaintext snapshot checks")
        raw = Path(SAVE).read_bytes()
        before = hashlib.sha256(raw).digest()
        snapshot = TOOL["inspect"](ELF, save_path=SAVE)["snapshot"]
        self.assertEqual(snapshot["signed_counts_by_native_id"], list(struct.unpack(">23i", raw[0x56D8:0x5734])))
        self.assertEqual(snapshot["sha256"], before.hex().upper())
        self.assertIn("no current source-index", snapshot["warning"])
        self.assertEqual(hashlib.sha256(Path(SAVE).read_bytes()).digest(), before)


class ArenaAssetChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ARCHIVE is None:
            raise unittest.SkipTest("Pass --archive for exact shipped arena UI validation")
        psarc = TOOL["module"]("test_tod_arena_psarc", "Inspect-Psarc.py")
        archive = psarc.Psarc(ARCHIVE)
        cls.raw = archive.read_entry(archive.names.index(TOOL["ASSET"]), TOOL["ASSET_SIZE"])
        cls.before = hashlib.sha256(cls.raw).digest()
        cls.report = TOOL["inspect_asset_bytes"](cls.raw)

    def test_exact_asset_function_and_instruction_guards(self):
        self.assertEqual(self.report["asset"]["sha256"], TOOL["ASSET_HASH"])
        self.assertEqual(self.report["asset"]["source"], "ListUpdater")
        self.assertEqual(len(self.report["bytecode_digests"]), 4)
        self.assertEqual(len(self.report["asset_byte_guards"]), 20)
        for guard in self.report["asset_byte_guards"]:
            offset = int(guard["offset"], 0)
            self.assertEqual(self.raw[offset:offset + 4].hex().upper(), guard["bytes"])
            self.assertEqual(int.from_bytes(self.raw[offset:offset + 4], "little"), int(guard["decoded_word"], 16))

    def test_partition_is_non_positive_then_positive_not_zero_only(self):
        init = self.report["initializer"]
        self.assertIn("> 0", init["completion_test"])
        self.assertIn("non-positive", init["display_order"])
        self.assertIn("preserved within each partition", init["display_order"])
        self.assertIn("negative signed count", init["negative_count_caveat"])
        self.assertIn("does not filter", init["inactive_rows"])
        self.assertEqual(init["preserved_index_field"], "chalNum")

    def test_selection_requires_active_and_uses_preserved_source_index(self):
        selection = self.report["selection"]
        self.assertIn("requires its isActive", selection["select"])
        self.assertIn("select_challenge(row.chalNum)", selection["select"])
        self.assertIn("chalNum equals get_default_challenge()", selection["default"])
        self.assertIn("not get_challenge_image(display_row)", selection["image"])
        self.assertIn("does not count native counter slots", selection["list_count"])
        self.assertIn("no Lua execution", self.report["warning"])

    def test_asset_archive_and_bytes_reports_agree(self):
        self.assertEqual(self.report, TOOL["inspect_archive"](ARCHIVE))
        self.assertEqual(hashlib.sha256(self.raw).digest(), self.before)

    def test_changed_and_truncated_original_asset_rejected(self):
        with self.assertRaises(ValueError):
            TOOL["inspect_asset_bytes"](self.raw[:-1])
        changed = bytearray(self.raw)
        changed[0x134FC + 118 * 4] ^= 1
        with self.assertRaises(ValueError):
            TOOL["inspect_asset_bytes"](changed)
        self.assertEqual(hashlib.sha256(self.raw).digest(), self.before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, ARCHIVE, SAVE = args.elf, args.archive, args.save
    unittest.main(argv=[__file__] + remaining)
