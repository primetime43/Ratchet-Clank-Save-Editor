"""Reproduce native global flag latches and bounded compiled-script evidence."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGlobalFlagMutation.py"))
ELF = SAVE = ARCHIVE = None


def chunk(api="clear_flag", enum="HERO_USED_MAP", register=2, call_register=2, results=1, argument_register=3):
    """Independent minimal Lua50 container; data only, never executed."""
    def integer(value):
        return struct.pack("<I", value)
    def string(value):
        raw = value.encode("ascii") + b"\0"
        return integer(len(raw)) + raw
    header = b"\x1bLua\x50" + bytes([1, 4, 4, 4, 6, 8, 9, 9, 4]) + struct.pack("<f", 31415926)
    function = integer(0) + integer(0) + bytes([0, 0, 0, 8])
    function += integer(0) * 3 + integer(2) + b"\x04" + string(api) + b"\x04" + string(enum)
    words = [register << 24 | 5, argument_register << 24 | 1 << 6 | 5,
             call_register << 24 | 2 << 15 | results << 6 | 25]
    return header + function + integer(0) + integer(3) + struct.pack("<3I", *words)


class DetachedFlagChecks(unittest.TestCase):
    def test_single_bit_preview_immutable_and_tail_preserved(self):
        raw = bytearray([0xA5] * 40)
        before = bytes(raw)
        for identifier in (0, 3, 63, 64, 127, 128, 191, 192, 255, 256, 291):
            set_ = TOOL["flag_preview"](raw, identifier, "set_flag")
            clear = TOOL["flag_preview"](set_["bytes"], identifier, "clear_flag")
            location = identifier // 64 * 8 + 7 - identifier % 64 // 8
            mask = 1 << (identifier % 8)
            for index in range(40):
                self.assertEqual(set_["bytes"][index], before[index] | mask if index == location else before[index])
                self.assertEqual(clear["bytes"][index], before[index] & ~mask if index == location else before[index])
            self.assertTrue(set_["set_after"])
            self.assertFalse(clear["set_after"])
        self.assertEqual(bytes(raw), before)

    def test_check_preview_no_change_and_idempotent_set_clear(self):
        raw = bytes(40)
        for identifier in range(292):
            first = TOOL["flag_preview"](raw, identifier, "set_flag")
            second = TOOL["flag_preview"](first["bytes"], identifier, "set_flag")
            check = TOOL["flag_preview"](second["bytes"], identifier, "check_flag")
            self.assertEqual(first["bytes"], second["bytes"])
            self.assertEqual(second["bytes"], check["bytes"])
            self.assertTrue(check["was_set"])
            clear = TOOL["flag_preview"](check["bytes"], identifier, "clear_flag")
            self.assertEqual(clear["bytes"], raw)
            self.assertEqual(TOOL["flag_preview"](clear["bytes"], identifier, "clear_flag")["bytes"], raw)

    def test_bad_ids_sentinel_unknown_tail_and_operations_rejected(self):
        for identifier in (-1, 292, 319, 320, 0xFFFFFFFF, True, 1.0, "3", None):
            with self.assertRaises(ValueError):
                TOOL["flag_preview"](bytes(40), identifier, "set_flag")
        for value in (bytes(39), bytes(41), [0] * 40, None):
            with self.assertRaises(ValueError):
                TOOL["flag_preview"](value, 3, "clear_flag")
        with self.assertRaises(ValueError):
            TOOL["flag_preview"](bytes(40), 3, "toggle_flag")

    def test_strict_adjacent_literal_call_decoder(self):
        for api, results in (("check_flag", 2), ("set_flag", 1), ("clear_flag", 1)):
            raw = chunk(api=api, results=results)
            root, calls = TOOL["literal_calls"](raw)
            self.assertEqual(len(calls), 1)
            self.assertEqual((calls[0]["api"], calls[0]["argument_enum"], calls[0]["prototype_path"], calls[0]["pc"]),
                             (api, "HERO_USED_MAP", "root", 0))
            offset = int(root["code_offset"], 0)
            self.assertEqual(bytes.fromhex(calls[0]["bytes"]), raw[offset:offset + 12])

    def test_nonliteral_register_or_result_mismatch_not_claimed(self):
        for raw in (chunk(argument_register=4), chunk(call_register=3), chunk(results=2), chunk(api="not_a_flag_api")):
            self.assertEqual(TOOL["literal_calls"](raw)[1], [])

    def test_lua_truncation_header_and_trailing_bytes_refused(self):
        for raw in (chunk()[:-1], chunk() + b"trailing", b"bad Lua header", bytes(14)):
            with self.assertRaises(ValueError):
                TOOL["literal_calls"](raw)


class NativeFlagMutationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ELF is None:
            raise unittest.SkipTest("Pass --elf for exact reference ELF")
        cls.elf = TOOL["BINDINGS"].Elf(ELF)
        cls.report = TOOL["inspect"](ELF)

    def test_native_guards_and_dual_clear_leaf_words(self):
        self.assertEqual(len(self.report["instruction_guards"]), 510)
        for guard in self.report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(self.elf.read(int(guard["va"], 0), len(raw)), raw)
        for address in (0x279AC, 0x27BB04):
            self.assertEqual(self.elf.u32(address), 0x7C0B2078)

    def test_selected_enums_event_offsets_and_no_atomicity_claim(self):
        self.assertEqual([r["id"] for r in self.report["selected_flags"]], [3, 7, 12, 13, 15, 16, 17, 219])
        self.assertEqual(self.report["selected_flags"][-1]["word_offset"], "0x5540")
        self.assertEqual(self.report["storage"]["unknown_tail_ids"], {"first": 292, "last": 319})
        self.assertIn("not reservation", self.report["native_mutation"]["atomicity"])
        self.assertIn("not a monotonic achievement", self.report["warning"])

    def test_supplied_snapshot_read_only_and_raw_events_not_history(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual detached reference snapshot")
        raw = Path(SAVE).read_bytes()
        before = hashlib.sha256(raw).digest()
        observation = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(observation["plaintext_sha256"], before.hex().upper())
        self.assertEqual(hashlib.sha256(Path(SAVE).read_bytes()).digest(), before)
        for row in observation["selected_events"]:
            word = struct.unpack_from(">Q", raw, int(row["word_offset"], 0))[0]
            self.assertEqual(row["set"], bool(word & 1 << row["word_bit"]))
        self.assertIn("not evidence a script consumed", observation["warning"])

    def test_invalid_save_size_preflight_and_layout_rejected(self):
        with tempfile.TemporaryDirectory(prefix="tod-global-latch-test-") as directory:
            path = Path(directory) / "invalid.bin"
            path.write_bytes(b"short")
            read_bytes = Path.read_bytes
            def checked_read(candidate):
                if candidate == path:
                    raise AssertionError("Short save must not be read")
                return read_bytes(candidate)
            with patch.object(Path, "read_bytes", checked_read):
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)
            path.write_bytes(bytes(0x906F0))
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF, path)

    def test_report_reproduction_after_parent_integration(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        if "global_flag_mutation" not in mapping:
            self.skipTest("Isolated report not yet integrated by parent")
        self.assertEqual(self.report, mapping["global_flag_mutation"])
        if ARCHIVE is not None:
            catalog = {q["enum"]: q["id"] for q in TOOL["FLAGS"]["inspect"](ELF)["catalog"]}
            self.assertEqual(TOOL["inspect_assets"](ARCHIVE, catalog), mapping["global_flag_mutation_assets"])


class AssetFlagMutationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ARCHIVE is None or ELF is None:
            raise unittest.SkipTest("Pass --archive and --elf for original bytecode replay")
        cls.archive = TOOL["PSARC"].Psarc(ARCHIVE)
        cls.payloads = {name: cls.archive.read_entry(cls.archive.names.index(name), size)
                        for name, (size, _) in TOOL["SELECTED"].items()}
        cls.catalog = {q["enum"]: q["id"] for q in TOOL["FLAGS"]["inspect"](ELF)["catalog"]}
        cls.report = TOOL["inspect_assets"](ARCHIVE, cls.catalog)

    def test_exact_bounded_survey_and_three_example_limit(self):
        survey = self.report["survey"]
        self.assertEqual((survey["compiled_entries_scanned"], survey["api_string_candidates"], survey["literal_calls"]), (524, 181, 880))
        self.assertEqual((survey["assets_with_strict_literal_calls"], survey["native_mapped_operand_names"], survey["operand_names"]), (180, 214, 215))
        self.assertEqual(survey["asset_metadata_sha256"], TOOL["ASSET_SET_SHA256"])
        self.assertTrue(all(1 <= len(r["example_sites"]) <= 3 for r in self.report["catalog"]))

    def test_missing_export_remains_unresolved_without_fabricated_alias(self):
        unresolved = self.report["unresolved_operands"]
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0]["argument_enum"], "LVL_IFF_RETURN_CHALLENGE_7_DONE")
        self.assertEqual((unresolved[0]["pc"], unresolved[0]["call_pc"]), (293, 295))
        self.assertNotIn("id", unresolved[0])
        self.assertNotIn("word_offset", unresolved[0])

    def test_selected_raw_guards_and_consumable_latch_relationships(self):
        selected = self.report["selected_consumers"]
        self.assertEqual(selected["consumable_event_ids"], [3, 7, 12, 13, 15, 16, 17])
        self.assertEqual(len(selected["asset_byte_guards"]), 6)
        for guard in selected["asset_byte_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            start = int(guard["offset"], 0)
            self.assertEqual(raw, self.payloads[guard["archive_entry"]][start:start + len(raw)])
        self.assertIn("not evidence", selected["meaning"])
        self.assertIn("no serialized save location", selected["shield_counter"])
        self.assertIn("not a proven atomic", selected["mission_order"])

    def test_selected_asset_mutation_and_missing_payload_refused(self):
        before = {name: hashlib.sha256(raw).digest() for name, raw in self.payloads.items()}
        for name in self.payloads:
            changed = dict(self.payloads)
            data = bytearray(changed[name]); data[-1] ^= 1; changed[name] = data
            with self.assertRaises(ValueError):
                TOOL["inspect_selected"](changed)
        with self.assertRaises(ValueError):
            TOOL["inspect_selected"]({})
        # Exact asset SHA checks remain active. Alter only parser output to prove
        # the selected assertions themselves independently constrain conditions,
        # rather than relying on fingerprints to hide a decoder regression.
        original = TOOL["literal_calls"]
        globals_ = TOOL["inspect_selected"].__globals__
        global_name, meridian, metro, _, _ = TOOL["SELECTED"]
        for name, pc, field, value in (
                (global_name, 156, "b", 2), (global_name, 157, "b", 0),
                (global_name, 158, "c", 2),
                (metro, 32, "constant", "DifferentHero"), (metro, 34, "b", 2),
                (metro, 35, "c", 1),
                (meridian, 0, "b", 1), (meridian, 15, "b", 1),
                (meridian, 16, "c", 0), (meridian, 17, "jump_pc", 25),
                (meridian, 18, "b", 0)):
            def changed_decode(raw, target=self.payloads[name], pc=pc, field=field, value=value):
                root, calls = original(raw)
                if raw == target:
                    root = copy.deepcopy(root)
                    root["instructions"][pc][field] = value
                return root, calls
            with patch.dict(globals_, {"literal_calls": changed_decode}):
                with self.assertRaises(ValueError):
                    TOOL["inspect_selected"](self.payloads)
        self.assertEqual({name: hashlib.sha256(raw).digest() for name, raw in self.payloads.items()}, before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE, ARCHIVE = args.elf, args.save, args.archive
    unittest.main(argv=[__file__] + remaining)
