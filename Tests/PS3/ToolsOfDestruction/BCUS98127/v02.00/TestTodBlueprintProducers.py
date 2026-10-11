"""Raw blueprint selector/consumer checks; no actors or Lua execution."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodBlueprintProducers.py"))
ELF = SAVE = ARCHIVE = None


class RawSelectorTests(unittest.TestCase):
    def test_all_shift_cases_independent_of_grant_mask(self):
        for selector in range(128):
            effective = selector % 64
            bit = 1 << effective if effective < 32 else 0
            row = TOOL["selector_bit_preview"](0, selector)
            self.assertEqual(int(row["effective_bit"], 0), bit)
            self.assertEqual(row["already_present"], False)
            self.assertEqual(int(row["after_reached_grant"], 0), bit)
        # The native leaf admits selector0 though bit0 is outside grant-all.
        row = TOOL["selector_bit_preview"](0x7DEE4, 0)
        self.assertEqual(row["after_reached_grant"], "0x0007DEE5")

    def test_or_is_idempotent_and_preserves_unrelated_bits(self):
        for mask in (0, 1, 0x7DEE4, 0x80000000, 0xFFFFFFFF):
            for selector in (0, 2, 18, 31, 32, 63, 64, 0xFFFFFFFF):
                first = TOOL["selector_bit_preview"](mask, selector)
                second = TOOL["selector_bit_preview"](int(first["after_reached_grant"], 0), selector)
                self.assertEqual(first["after_reached_grant"], second["after_reached_grant"])
                self.assertEqual(int(first["after_reached_grant"], 0) & mask, mask)

    def test_predicate_and_shift_alias_boundaries(self):
        cases = [(0x80000000, 31, True), (0xFFFFFFFF, 32, False),
                 (0xFFFFFFFF, 63, False), (1, 64, True), (1, 65, False)]
        for mask, selector, expected in cases:
            self.assertEqual(TOOL["selector_bit_preview"](mask, selector)["already_present"], expected)

    def test_invalid_raw_inputs_refused(self):
        for invalid in (-1, 0x100000000, True, 1.0, "2", None):
            for args in ((invalid, 2), (0, invalid)):
                with self.assertRaises(ValueError):
                    TOOL["selector_bit_preview"](*args)


class NativeBlueprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ELF is None:
            raise unittest.SkipTest("Pass --elf for exact native reproduction")
        cls.elf = TOOL["BINDINGS"]["Elf"](ELF)
        cls.report = TOOL["inspect"](ELF)

    def test_exact_guards_and_selector_pointer_alias(self):
        self.assertEqual(len(self.report["instruction_guards"]), 193)
        for row in self.report["instruction_guards"]:
            raw = bytes.fromhex(row["bytes"])
            self.assertEqual(self.elf.read(int(row["va"], 0), len(raw)), raw)
        self.assertEqual(self.elf.u32(0x8A0024), self.elf.u32(0x89F188))
        self.assertEqual(self.elf.u32(0x89F188), 0x101EFB20)
        self.assertEqual(struct.unpack(">4I", self.elf.read(0x2D1490, 16)),
            (0x8062F268, 0x3D230009, 0x806906E8, 0x4E800020))
        self.assertIn("not guaranteed", self.report["selector_grant"]["rule"])
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(mapping["blueprint_producers"], self.report)

    def test_inline_grant_read_shift_or_store_not_only_predicate(self):
        self.assertEqual(struct.unpack(">7I", self.elf.read(0x303234, 28)),
            (0x80C20104, 0x38A00001, 0x3D660001, 0x7CA91830,
             0x808B86F4, 0x7C834B78, 0x906B86F4))
        self.assertEqual(TOOL["BINDINGS"]["branch_target"](self.elf.u32(0x30322C), 0x30322C), 0x2D1490)
        self.assertEqual(self.report["selector_grant"]["write_va"], "0x30324c")

    def test_initializer_test_edge_and_validated_entry_restore(self):
        word = self.elf.u32(0x3032F4)
        self.assertEqual(word, 0x40820094)
        self.assertEqual(0x3032F4 + (word & 0xFFFC), 0x303388)
        for va, target in ((0x303368, 0x24F4F8), (0x30338C, 0x24F6D8)):
            self.assertEqual(TOOL["BINDINGS"]["branch_target"](self.elf.u32(va), va), target)
        self.assertEqual(self.elf.u32(0x30332C), 0x80090064)
        self.assertEqual(self.elf.u32(0x30334C), 0x41860024)
        self.assertIn("after native generated-handle validation", self.report["paired_initializer"]["rule"])
        self.assertIn("Neither branch writes", self.report["paired_initializer"]["rule"])

    def test_native_level_registration_byte_masks_and_unknowns(self):
        catalog = self.report["level_index_associations"]
        ids = [2, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 17, 18]
        self.assertEqual([r["bit_id"] for r in catalog["rows"]], ids)
        self.assertEqual(catalog["count"], 13)
        combined = 0
        for row in catalog["rows"]:
            self.assertEqual(self.elf.string(int(row["level_name_va"], 0)), row["level_enum"])
            ordinal = row["bit_id"]
            self.assertEqual(int(row["byte_offset"], 0), 0x86F7 - ordinal // 8)
            self.assertEqual(int(row["byte_mask"], 0), 1 << (ordinal % 8))
            combined |= 1 << ordinal
        self.assertEqual(combined, int(catalog["native_grant_all_mask"], 0))
        self.assertIn("whether all thirteen levels use this same producer", catalog["unknowns"])
        self.assertIn("not thirteen recovered physical pickup", catalog["rule"])

    def test_wrapper_argument2_not_implicit_saved_selector(self):
        for va, target in ((0x2BA4E0, 0x251C78), (0x2BA610, 0x251C78),
                           (0x2BA4FC, 0x27AF90), (0x2BA62C, 0x27A5D8)):
            self.assertEqual(TOOL["BINDINGS"]["branch_target"](self.elf.u32(va), va), target)
        self.assertEqual(self.elf.u32(0x2BA4E8), 0xFC20081E)
        self.assertEqual(self.elf.u32(0x2BA618), 0xFC20081E)
        self.assertIn("does not substitute 2D1490", self.report["named_wrapper_argument"]["rule"])
        self.assertIn("non-null handle", self.report["named_wrapper_argument"]["rule"])

    def test_descriptor_table_is_not_proven_dispatch_trigger(self):
        self.assertEqual(self.elf.u32(0x84E40C), 0x86DEC0)
        self.assertEqual(self.elf.u32(0x84E3C8), 0x86DEC8)
        self.assertEqual(self.elf.u32(0x86DEC0), 0x303220)
        self.assertIn("does not establish the event", self.report["selector_grant"]["dispatch_limit"])
        self.assertEqual(len(self.report["recommended_annotations"]), 2)

    def test_guard_tamper_refused_after_reference_hash_constructor(self):
        elf_class = TOOL["BINDINGS"]["Elf"]
        original = elf_class.u32
        for changed in (0x303240, 0x30324C, 0x2D1498, 0x8A0024, 0x3032F4,
                        0x30322C, 0x2BA4FC, 0x86DEC0):
            def altered(instance, va):
                value = original(instance, va)
                return value ^ 4 if va == changed else value
            with patch.object(elf_class, "u32", altered), self.assertRaises(ValueError):
                TOOL["inspect"](ELF)

    def test_captured_save_snapshot_not_collection_history(self):
        if SAVE is None:
            self.skipTest("Pass --save for detached plaintext comparison")
        before = hashlib.sha256(Path(SAVE).read_bytes()).hexdigest()
        report = TOOL["inspect"](ELF, SAVE)
        observation = report["save_observation"]
        self.assertEqual(observation["blueprint_mask"], "0x0007DEE4")
        self.assertEqual(observation["saved_level_destination_selector"], 0)
        self.assertTrue(all(row["present"] for row in observation["level_bits"]))
        self.assertEqual(observation["native_popcount_all32"], 13)
        self.assertFalse(observation["sampled_selector_preview"]["already_present"])
        self.assertIn("no grant execution", observation["limit"])
        self.assertEqual(hashlib.sha256(Path(SAVE).read_bytes()).hexdigest(), before)
        with tempfile.TemporaryDirectory() as temp:
            invalid = Path(temp) / "invalid.bin"
            invalid.write_bytes(bytes(0x906F0))
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF, invalid)


class AssetBlueprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ARCHIVE is None:
            raise unittest.SkipTest("Pass --archive for original bounded compiled scripts")
        cls.report = TOOL["inspect_assets"](ARCHIVE)
        psarc = runpy.run_path(str(ROOT / "Tools/Inspect-Psarc.py"))["Psarc"]
        reader = runpy.run_path(str(ROOT / "Tools/Inspect-Lua50.py"))["Reader"]
        archive = psarc(Path(ARCHIVE))
        indexes = [i for i, n in enumerate(archive.names) if n == TOOL["CONSUMER"]]
        cls.raw = archive.read_entry(indexes[0], 1024 * 1024)
        cls.root = reader(cls.raw).function()

    def test_bounded_survey_and_qualified_negative_grant_scan(self):
        self.assertEqual(self.report["archive_entry_count"], 3297)
        self.assertEqual(self.report["compiled_script_count"], 524)
        self.assertEqual(self.report["api_getglobal_count"], 39)
        self.assertEqual(len(self.report["source_fingerprints"]), 6)
        self.assertEqual(self.report["source_catalog_sha256"],
            "9E66E9BF10DF565AB94F70965CCF50BAD5196D0FF88994412A795F64E7656DD4")
        names = [r["api"] for r in self.report["api_getglobals"]]
        self.assertEqual(names.count("hero_get_blueprints"), 38)
        self.assertEqual(names.count("hero_has_blueprint"), 1)
        self.assertNotIn("hero_give_blueprint", names)
        self.assertIn("aliases, indirect calls, native callbacks or other archives", self.report["survey_limit"])
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(mapping["blueprint_producers_assets"], self.report)

    def test_named_consumer_exact_operand_registers_call_and_branch(self):
        consumer = self.report["selected_consumer"]
        self.assertEqual(consumer["argument"], "LEVEL_STRATUS_CITY")
        self.assertEqual(consumer["level_id"], 2)
        self.assertEqual(consumer["branch_target_pc"], 38)
        guard = consumer["guard"]
        self.assertEqual(self.raw[int(guard["offset"], 0):int(guard["offset"], 0) + 24], bytes.fromhex(guard["bytes"]))
        self.assertIn("consumer, not proof", consumer["semantics"])

    def test_raw_and_decoded_selected_instruction_tamper_refused(self):
        changed_raw = bytearray(self.raw)
        changed_raw[0xA8B] ^= 1
        with self.assertRaises(ValueError):
            TOOL["consumer_guard"](bytes(changed_raw), self.root)
        changes = [(13, "constant", "hero_give_blueprint"), (14, "a", 2),
                   (15, "constant", "LEVEL_METROPOLIS"), (16, "b", 2),
                   (16, "c", 1), (17, "c", 1), (18, "jump_pc", 39),
                   (18, "word", "008004D4"), (13, "offset", "0xa8f")]
        for pc, key, value in changes:
            altered = copy.deepcopy(self.root)
            altered["instructions"][pc][key] = value
            with self.assertRaises(ValueError):
                TOOL["consumer_guard"](self.raw, altered)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path)
    options, rest = parser.parse_known_args()
    ELF, SAVE, ARCHIVE = options.elf, options.save, options.archive
    unittest.main(argv=[__file__] + rest)
