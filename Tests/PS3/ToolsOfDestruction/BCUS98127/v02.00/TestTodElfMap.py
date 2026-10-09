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

ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "Ratchet And Clank Save Editor.sln").is_file())
MAP_PATH = ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json"
SPEC = importlib.util.spec_from_file_location("tod_import", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/IDA/import_tod_map.py")
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
                self.assertTrue(field.get("comment"), "Ghidra import requires a field comment")

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

    def test_verified_snapshot_and_inventory_layout(self):
        snapshot = MAPPING["serialization"]
        self.assertEqual(int(snapshot["runtime_state_va"], 0), 0x101EFB20)
        self.assertEqual(int(snapshot["size"], 0), int(MAPPING["reference_save"]["size"], 0))
        names = {entry["va"]: entry for entry in MAPPING["annotations"]}
        for key in ("snapshot_va", "restore_va", "copy_va", "file_callback_va"):
            self.assertEqual(names[snapshot[key]]["confidence"], "confirmed")
        for address in ("0x00888624", "0x008A1984", "0x0089F1B8"):
            self.assertEqual(int(names[address]["bytes"], 16), int(snapshot["runtime_state_va"], 0))
        inventory = snapshot["inventory"]
        record = next(t for t in MAPPING["structures"] if t["name"] == inventory["verified_type"])
        self.assertEqual(int(record["size"], 0), int(inventory["stride"], 0))
        fields = {f["name"]: f for f in record["fields"]}
        for name, key, expected_type in (("weapon_xp", "xp_offset", "f32"),
                ("ammo", "ammo_offset", "f32"), ("modifier_mask", "modifier_mask_offset", "u32"),
                ("eligibility_state", "eligibility_offset", "u8"), ("stored_level", "stored_level_offset", "u8")):
            self.assertEqual(int(fields[name]["offset"], 0), int(inventory[key], 0))
            self.assertEqual(fields[name]["type"], expected_type)
        self.assertEqual(int(fields["unknown_12_13"]["offset"], 0), 0x12)
        self.assertEqual(fields["unknown_12_13"]["count"], 2)
        self.assertEqual(int(inventory["stride"], 0) * inventory["sample_count"], 0x280)

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

    def test_ownership_unlock_and_acquisition_evidence(self):
        inventory = MAPPING["serialization"]["inventory"]
        annotations = {entry["va"]: entry for entry in MAPPING["annotations"]}
        self.assertEqual(inventory["code_count"], inventory["sample_count"])
        self.assertEqual(inventory["code_count"], 32)
        self.assertEqual(inventory["script_ownership_offset"], inventory["eligibility_offset"])
        self.assertEqual(int(inventory["acquisition_counter_offset"], 0), 0x280)
        self.assertEqual(int(inventory["unlock_bytes_offset"], 0), 0x5754)
        self.assertEqual(int(annotations["0x00898F50"]["bytes"], 16), int(MAPPING["serialization"]["runtime_state_va"], 0))
        for key in ("ownership_predicate_va", "array_initializer_va", "acquire_va", "remove_va", "unlock_setter_va"):
            self.assertEqual(annotations[inventory[key]]["confidence"], "confirmed")
        fields = next(t["fields"] for t in MAPPING["structures"] if t["name"] == inventory["verified_type"])
        byte = next(f for f in fields if int(f["offset"], 0) == 0x10)
        self.assertEqual(byte["type"], "u8")
        self.assertIn("nonzero", byte["comment"])
        self.assertIn("Counter", inventory["ownership_warning"])

    def test_weapon_asset_fingerprints_and_native_bindings(self):
        import runpy
        hashes = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWeaponConfigs.py"))["REFERENCE_HASHES"]
        configuration = MAPPING["weapon_configuration"]
        self.assertEqual(configuration["asset_weapon_count"], 28)
        self.assertEqual(configuration["asset_modifier_count_including_start_nodes"], 204)
        self.assertEqual({Path(asset["name"]).name: asset["sha256"] for asset in configuration["assets"]}, hashes)
        fields = configuration["native_fields"]
        self.assertEqual(fields["max_ammo_array_capacity"], 20)
        self.assertEqual(fields["mod_ammo_attribute_id"], 9)
        self.assertEqual(int(fields["vendor_offset"], 0), 0x6A8)
        self.assertEqual(int(fields["num_mods_offset"], 0), 0x6A4)
        self.assertEqual(fields["mods_array_capacity"], 24)
        self.assertEqual(int(fields["mods_offset"], 0), 0x464)
        self.assertEqual(int(fields["mod_stride"], 0), 0x18)
        self.assertEqual(int(fields["mod_cost_offset"], 0), 0xC)
        annotations = {entry["va"]: entry for entry in MAPPING["annotations"]}
        for key, value in fields.items():
            if key.endswith("_va"):
                self.assertEqual(annotations[value]["confidence"], "confirmed", key)
        self.assertIn("CSV order", configuration["warning"])

    def test_inventory_catalog_and_upgrade_grid_evidence(self):
        configuration = MAPPING["weapon_configuration"]
        catalog = configuration["inventory_catalog"]
        self.assertEqual([item["id"] for item in catalog], list(range(32)))
        self.assertEqual(len({item["config_name"] for item in catalog}), 32)
        guards = {int(g["va"], 0): bytes.fromhex(g["bytes"])
                  for g in configuration["catalog_instruction_guards"]}
        annotations = {int(a["va"], 0): a for a in MAPPING["annotations"]}
        root = int(configuration["config_root"]["va"], 0)
        for item in catalog:
            self.assertEqual(int(item["save_record_offset"], 0), item["id"] * 0x14)
            self.assertEqual(int(item["config_va"], 0), root + int(item["parent_config_offset"], 0))
            self.assertEqual(int.from_bytes(guards[int(item["id_load_va"], 0)], "big"), 0x38800000 | item["id"])
            self.assertEqual(struct.unpack(">f", guards[int(item["enum_export"]["value_slot_va"], 0)])[0], item["id"])
            pointer = annotations[int(item["config_pointer_slot_va"], 0)]
            self.assertEqual(int(pointer["bytes"], 16), int(item["config_va"], 0))
            self.assertEqual(annotations[int(item["enum_export"]["name_va"], 0)]["bytes"], (item["enum"].encode("ascii") + b"\0").hex().upper())
            self.assertEqual(annotations[int(item["config_getter_va"], 0)]["confidence"], "confirmed")
        vendor = configuration["vendor_upgrade_layout"]
        self.assertEqual(vendor["number_bytes"], 4)
        self.assertEqual(len(vendor["grids"]), 15)
        total = 0
        for enum, grid in vendor["grids"].items():
            self.assertIn(enum, {item["enum"] for item in catalog})
            rows = grid["rows"]
            self.assertEqual(len(rows), 4)
            self.assertTrue(all(len(row) == 7 for row in rows))
            indices = [node for row in rows for node in row if node >= 0]
            self.assertEqual(sorted(indices), list(range(len(indices))))
            total += len(indices)
        self.assertEqual(total, 204)

    def test_reference_catalog_matches_independent_decoder(self):
        if ELF_PATH is None:
            self.skipTest("Pass --elf to reproduce the native catalog")
        import runpy
        report = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWeaponBindings.py"))["inspect"](ELF_PATH)
        by_id = {item["id"]: item for item in report["constructor_calls"]}
        for item in MAPPING["weapon_configuration"]["inventory_catalog"]:
            decoded = by_id[item["id"]]
            for key in ("enum", "config_name"):
                self.assertEqual(item[key], decoded[key])
            for key in ("constructor_va", "id_load_va", "config_load_va", "config_pointer_slot_va", "config_va", "save_record_offset"):
                self.assertEqual(int(item[key], 0), int(decoded[key], 0))
            self.assertEqual(int(item["constructor_call_va"], 0), int(decoded["call_va"], 0))
            self.assertEqual(int(item["config_getter_va"], 0), int(decoded["config_property"]["getter_va"], 0))
            self.assertEqual(int(item["parent_config_offset"], 0), decoded["config_property"]["parent_offset"])

    def test_reject_bad_schema_duplicates_and_overlap(self):
        invalid = copy.deepcopy(MAPPING)
        invalid["schema_version"] = 99
        with self.assertRaises(ValueError): IMPORTER.validate_map(invalid)
        invalid = copy.deepcopy(MAPPING)
        invalid["annotations"].append(invalid["annotations"][0])
        with self.assertRaises(ValueError): IMPORTER.validate_map(invalid)
        invalid = copy.deepcopy(MAPPING)
        next(s for s in invalid["structures"] if len(s["fields"]) > 1)["fields"][1]["offset"] = "0x0"
        with self.assertRaises(ValueError): IMPORTER.validate_map(invalid)

    def test_reference_elf_bytes(self):
        if ELF_PATH is None:
            self.skipTest("Pass --elf to check all guards against the original ELF")
        raw = ELF_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), MAPPING["binary"]["sha256"])
        self.assertEqual(len(raw), MAPPING["binary"]["size"])
        self.assertEqual(raw[:6], b"\x7fELF\x02\x02")
        for entry in (MAPPING["annotations"] + MAPPING["serialization"]["instruction_guards"]
                + MAPPING["weapon_configuration"]["instruction_guards"]
                + MAPPING["weapon_configuration"]["catalog_instruction_guards"]
                + MAPPING["progression"]["instruction_guards"]
                + MAPPING["collectibles"]["instruction_guards"]
                + MAPPING["world_state"]["instruction_guards"]
                + MAPPING["objects"]["instruction_guards"]
                + MAPPING["mission_lists"]["instruction_guards"]
                + MAPPING["bonuses"]["instruction_guards"]
                + MAPPING["state_storage"]["instruction_guards"]
                + MAPPING["settings"]["instruction_guards"]
                + MAPPING["arena_challenges"]["instruction_guards"]
                + MAPPING["global_flags"]["instruction_guards"]
                + MAPPING["gameplay_segments"]["instruction_guards"]
                + MAPPING["world_object_flags"]["instruction_guards"]
                + MAPPING["reset_categories"]["instruction_guards"]
                + MAPPING["persistent_grid"]["instruction_guards"]
                + MAPPING["grid_routing"]["instruction_guards"]
                + MAPPING["grid_geometry"]["instruction_guards"]
                + MAPPING["save_tail"]["instruction_guards"]
                + MAPPING["reward_channels"]["instruction_guards"]
                + MAPPING["segment_bindings"]["instruction_guards"]):
            if "bytes" not in entry: continue
            va = int(entry["va"], 0)
            expected = bytes.fromhex(entry["bytes"])
            segments = [segment for segment in MAPPING["binary"]["load_segments"]
                        if int(segment["va"], 0) <= va and va + len(expected) <= int(segment["va"], 0) + int(segment["file_size"], 0)]
            self.assertEqual(len(segments), 1, entry.get("name", entry["va"]))
            segment = segments[0]
            offset = va - int(segment["va"], 0) + int(segment["file_offset"], 0)
            self.assertEqual(raw[offset:offset + len(expected)], expected, entry.get("name", entry["va"]))
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

    def test_revised_notes_preserve_history_and_custom_comments(self):
        entry = MAPPING["annotations"][0]
        address = int(entry["va"], 0)
        marker = f"[ToD map: {entry['name']};"
        old_note = marker + " candidate]\nEarlier research\nEvidence: earlier bytes"
        self.comments[address] = "My custom prefix\n\n" + old_note + "\nMy custom suffix"
        self.run_import()
        updated = self.comments[address]
        self.assertEqual(updated.count(marker), 1)
        self.assertIn("[Previous ToD map:", updated)
        self.assertIn("Earlier research\nEvidence: earlier bytes", updated)
        self.assertTrue(updated.startswith("My custom prefix"))
        self.assertIn("\nMy custom suffix", updated)
        self.run_import()
        self.assertEqual(self.comments[address], updated)
        self.comments[address] = old_note + "\n\n" + updated
        self.run_import()
        self.assertEqual(self.comments[address].count(marker), 1)
        repaired = self.comments[address]
        self.run_import()
        self.assertEqual(self.comments[address], repaired)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--elf", type=Path)
    options, remaining = parser.parse_known_args()
    ELF_PATH = options.elf
    unittest.main(argv=[sys.argv[0]] + remaining)
