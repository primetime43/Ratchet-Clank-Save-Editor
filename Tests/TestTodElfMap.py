"""Portable map/importer checks. Optional: --elf <reference EBOOT.ELF>.

IDA is mocked here; this does not substitute for running the importer in IDA.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "docs/maps/ToolsOfDestruction.BCUS98127.v02.00.json"
SPEC = importlib.util.spec_from_file_location("tod_import", ROOT / "Tools/IDA/import_tod_map.py")
IMPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPORTER)
MAPPING = json.loads(MAP_PATH.read_text(encoding="utf-8"))
ELF_PATH = None


class MapChecks(unittest.TestCase):
    def test_map_and_type_declarations(self):
        IMPORTER.validate_map(MAPPING)
        for record in MAPPING["structures"]:
            text = IMPORTER.declaration(record)
            self.assertIn("typedef struct", text)
            self.assertIn(record["name"], text)
            for field in record["fields"]:
                self.assertIn(field["name"], text)

    def test_descriptor_bounds_and_counts(self):
        binary = MAPPING["binary"]
        table = binary["descriptor_table"]
        self.assertEqual(int(table["end_exclusive"], 0) - int(table["start"], 0), table["count"] * table["stride"])
        self.assertEqual(sum(toc["descriptor_count"] for toc in binary["toc_bases"]), table["count"])

    def test_save_regions_cover_entire_sample(self):
        end = 0
        for region in MAPPING["save_regions"]:
            self.assertEqual(int(region["start"], 0), end)
            end = int(region["end_exclusive"], 0)
        self.assertEqual(end, int(MAPPING["reference_save"]["size"], 0))

    def test_import_counts_and_resolved_name_ids(self):
        libraries = MAPPING["library_imports"]
        metadata = MAPPING["binary"]["import_table"]
        self.assertEqual(len(libraries), metadata["library_count"])
        self.assertEqual(sum(lib["function_count"] for lib in libraries), metadata["function_count"])
        resolved = 0
        suffix = bytes.fromhex("6759659904250490566427499489741A")
        for library in libraries:
            self.assertEqual(library["function_count"], len(library["functions"]))
            for function in library["functions"]:
                if not function["name"]: continue
                digest = hashlib.sha1(function["name"].encode("ascii") + suffix).digest()
                self.assertEqual(int.from_bytes(digest[:4], "little"), int(function["nid"], 0))
                self.assertTrue(function["source"].startswith("https://raw.githubusercontent.com/RPCS3/rpcs3/"))
                resolved += 1
        self.assertEqual(resolved, metadata["resolved_name_count"])

    def test_reject_bad_schema_duplicates_and_overlap(self):
        invalid = copy.deepcopy(MAPPING)
        invalid["schema_version"] = 99
        with self.assertRaises(ValueError): IMPORTER.validate_map(invalid)
        invalid = copy.deepcopy(MAPPING)
        invalid["annotations"].append(invalid["annotations"][0])
        with self.assertRaises(ValueError): IMPORTER.validate_map(invalid)
        invalid = copy.deepcopy(MAPPING)
        invalid["structures"][0]["fields"][1]["offset"] = "0x0"
        with self.assertRaises(ValueError): IMPORTER.validate_map(invalid)

    def test_reference_elf_bytes(self):
        if ELF_PATH is None:
            self.skipTest("Pass --elf to check all guards against the original ELF")
        raw = ELF_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), MAPPING["binary"]["sha256"])
        self.assertEqual(len(raw), MAPPING["binary"]["size"])
        self.assertEqual(raw[:6], b"\x7fELF\x02\x02")
        for entry in MAPPING["annotations"]:
            if "bytes" not in entry: continue
            va = int(entry["va"], 0)
            expected = bytes.fromhex(entry["bytes"])
            segments = [segment for segment in MAPPING["binary"]["load_segments"]
                        if int(segment["va"], 0) <= va and va + len(expected) <= int(segment["va"], 0) + int(segment["file_size"], 0)]
            self.assertEqual(len(segments), 1, entry["name"])
            segment = segments[0]
            offset = va - int(segment["va"], 0) + int(segment["file_offset"], 0)
            self.assertEqual(raw[offset:offset + len(expected)], expected, entry["name"])
        table = MAPPING["binary"]["descriptor_table"]
        counts = {}
        # This table lives in the second PT_LOAD (VA = file offset + 0x10000).
        for va in range(int(table["start"], 0), int(table["end_exclusive"], 0), 8):
            code, toc = struct.unpack_from(">II", raw, va - 0x10000)
            self.assertEqual(code & 3, 0)
            self.assertTrue(0x10200 <= code < 0x83A50C)
            counts[toc] = counts.get(toc, 0) + 1
        self.assertEqual(counts, {int(toc["va"], 0): toc["descriptor_count"] for toc in MAPPING["binary"]["toc_bases"]})
        for library in MAPPING["library_imports"]:
            for index, function in enumerate(library["functions"]):
                nid_offset = int(library["nids_va"], 0) - 0x10000 + index * 4
                slot_offset = int(function["slot_va"], 0) - 0x10000
                self.assertEqual(struct.unpack_from(">I", raw, nid_offset)[0], int(function["nid"], 0))
                self.assertEqual(struct.unpack_from(">I", raw, slot_offset)[0], int(function["stub_va"], 0))


class MockIdaChecks(unittest.TestCase):
    def setUp(self):
        self.writes, self.names, self.comments = [], {}, {}
        self.digest = bytes.fromhex(MAPPING["binary"]["sha256"])
        self.bad_address = None
        owner = self
        class TypeInfo:
            def get_named_type(self, _til, name): return False
        def get_bytes(address, _size):
            if address == owner.bad_address: return b"bad"
            entry = next(e for e in MAPPING["annotations"] if int(e["va"], 0) == address)
            return bytes.fromhex(entry.get("bytes", ""))
        def set_name(address, name, _flags):
            self.writes.append(("name", address))
            self.names[address] = name
            return True
        def set_comment(address, text, _repeatable):
            self.writes.append(("comment", address))
            self.comments[address] = text
            return True
        self.modules = {
            "ida_bytes": SimpleNamespace(is_mapped=lambda _: True, get_bytes=get_bytes,
                get_full_flags=lambda address: address, has_user_name=lambda flags: flags in self.names,
                get_cmt=lambda address, _: self.comments.get(address), set_cmt=set_comment),
            "ida_kernwin": SimpleNamespace(ask_file=lambda *_: str(MAP_PATH)),
            "ida_name": SimpleNamespace(set_name=set_name, SN_CHECK=0, SN_NOWARN=0),
            "ida_nalt": SimpleNamespace(retrieve_input_file_sha256=lambda: self.digest),
            "ida_typeinf": SimpleNamespace(tinfo_t=TypeInfo, PT_SIL=0,
                idc_parse_types=lambda text, _: self.writes.append(("type", text)) or 0),
        }

    def run_import(self):
        with patch.dict(sys.modules, self.modules): IMPORTER.main()

    def test_hash_guard_before_any_write(self):
        self.digest = bytes(32)
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"): self.run_import()
        self.assertEqual(self.writes, [])

    def test_all_byte_guards_before_any_write(self):
        self.bad_address = int(MAPPING["annotations"][-1]["va"], 0)
        with self.assertRaisesRegex(ValueError, "Byte mismatch"): self.run_import()
        self.assertEqual(self.writes, [])

    def test_unmapped_toc_reference_base_is_not_missing_data(self):
        self.modules["ida_bytes"].is_mapped = lambda address: address != 0x8AFE5C
        self.run_import()
        self.assertNotIn(0x8AFE5C, self.names)
        self.assertNotIn(0x8AFE5C, self.comments)

    def test_unmapped_real_annotation_rejected_before_writes(self):
        self.modules["ida_bytes"].is_mapped = lambda address: address != 0x10026648
        with self.assertRaisesRegex(ValueError, "Unmapped VA"): self.run_import()
        self.assertEqual(self.writes, [])

    def test_preserve_custom_name_comment_and_idempotent_notes(self):
        address = int(MAPPING["annotations"][0]["va"], 0)
        self.names[address] = "my_research_label"
        self.comments[address] = "My existing research"
        self.run_import()
        first_comments = dict(self.comments)
        self.run_import()
        self.assertEqual(self.names[address], "my_research_label")
        self.assertTrue(self.comments[address].startswith("My existing research"))
        self.assertEqual(first_comments, self.comments)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--elf", type=Path)
    options, remaining = parser.parse_known_args()
    ELF_PATH = options.elf
    unittest.main(argv=[sys.argv[0]] + remaining)
