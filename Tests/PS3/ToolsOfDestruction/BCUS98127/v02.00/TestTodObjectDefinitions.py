"""Object asset provenance, raw record boundaries and conditional slot identity."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodObjectDefinitions.py"))
ELF = SAVE = ARCHIVE = None


def fixture():
    names = [b"ambient\0", b"gameplay_enemy\0"]
    raw = bytearray(0x400 + 5 * 4)
    struct.pack_into(">8I", raw, 0, 0x49474857, 0x10001, 6, 128, 0x400, 5, 0xDEADDEAD, 0xDEADDEAD)
    sections = [(0x250C0, 0x80, 0x10000002, 4), (0x79C0, 0x90, 1, sum(map(len, names))),
                (0x25100, 0x100, 0x10000001, 0x80), (0x7340, 0x200, 0x10000002, 0x48),
                (0x25000, 0x300, 1, 44), (0x7700, 0x380, 1, 16)]
    for i, row in enumerate(sections):
        struct.pack_into(">4I", raw, 32 + i * 16, *row)
    pointer = 0x90
    for i, name in enumerate(names):
        struct.pack_into(">I", raw, 0x80 + i * 4, pointer)
        raw[pointer:pointer + len(name)] = name
        pointer += len(name)
    raw[0x100:0x108] = b"default\0"
    struct.pack_into(">2I", raw, 0x140, 0x200, 2)
    struct.pack_into(">2I", raw, 0x300, 0x100, 1)
    struct.pack_into(">2I", raw, 0x324, 0x80, 2)
    for i in range(2):
        start = 0x200 + i * 0x48
        struct.pack_into(">I", raw, start + 4, 0xDEADBEEF)
        struct.pack_into(">H", raw, start + 0x3C, 0x8000 + i)
        raw[start + 0x3E:start + 0x42] = bytes([0xAB, 0xCD, 0xFE, 0xFD])
        struct.pack_into(">2H", raw, start + 0x42, i + 1, 1)
        raw[start + 0x46:start + 0x48] = bytes([0xFC, 0xFB])
    struct.pack_into(">5I", raw, 0x400, 0x80, 0x84, 0x140, 0x300, 0x324)
    return raw


class ObjectDefinitionChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_exact_native_guards_and_identity_boundaries(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        self.assertEqual(len(report["instruction_guards"]), 69)
        for guard in report["instruction_guards"]:
            self.assertEqual(elf.read(int(guard["va"], 0), len(guard["bytes"]) // 2).hex().upper(), guard["bytes"])
        self.assertIn("not reconstructed", report["allocation"]["ordinal_binding_limit"])
        self.assertIn("BEFORE", report["allocation"]["bounds"])
        self.assertEqual(sum(f["size"] for f in report["definition_fields"]), 0x48)

    def test_asset_chain_counts_modes_and_reference_names(self):
        source = fixture()
        before = bytes(source)
        catalog = TOOL["gameplay_definitions"](source)
        root = catalog["roots"][0]
        self.assertEqual(root["selector_names"], ["default", ""])
        self.assertEqual(root["definition_count"], 2)
        self.assertEqual(root["classes"], [{"class_id": 0x8000, "definition_count": 1}, {"class_id": 0x8001, "definition_count": 1}])
        self.assertEqual(root["segment_references"], [{"loaded_name_index": 1, "reference_name": "gameplay_enemy", "definition_count": 2}])
        self.assertEqual(root["examples"][1]["definition_ordinal"], 1)
        self.assertEqual(source, before)

    def test_unsigned_fields_and_opaque_bytes_are_retained(self):
        raw = fixture()[0x200:0x248]
        row = TOOL["definition"](raw)
        self.assertEqual(row["class_id"], 0x8000)
        self.assertEqual(row["raw_words_00_38"][1], "DEADBEEF")
        self.assertEqual((row["opaque_byte_3e"], row["opaque_byte_47"]), ("AB", "FB"))
        self.assertEqual((row["before_complete_gate_byte"], row["after_complete_gate_byte"]), (254, 253))
        self.assertEqual(bytes.fromhex(row["raw_hex"]), raw)

    def test_record_length_and_malformed_assets_rejected(self):
        for raw in (b"", b"\0" * 71, b"\0" * 73):
            with self.assertRaises(ValueError):
                TOOL["definition"](raw)
        raw = fixture()
        for offset, value in ((8, 0xFFFFFFFF), (12, 129), (16, len(raw)), (0x300, 0x101),
                              (0x304, 2), (0x140, 0x201), (0x144, 3), (0x408, 0),
                              (32 + 2 * 16 + 12, 0x81), (32 + 3 * 16 + 12, 0x47)):
            copy = bytearray(raw)
            struct.pack_into(">I", copy, offset, value)
            before = bytes(copy)
            with self.assertRaises(ValueError, msg=hex(offset)):
                TOOL["gameplay_definitions"](copy)
            self.assertEqual(copy, before)
        with self.assertRaises(ValueError):
            TOOL["gameplay_definitions"](raw[:-1])

    def test_overlap_duplicate_and_selector_name_rejected(self):
        for mutate in (lambda r: struct.pack_into(">I", r, 32 + 5 * 16 + 4, 0x200),
                       lambda r: struct.pack_into(">I", r, 0x40C, 0x140),
                       lambda r: r.__setitem__(slice(0x100, 0x109), b"abcdefghi")):
            raw = fixture()
            mutate(raw)
            with self.assertRaises(ValueError):
                TOOL["gameplay_definitions"](raw)

    def test_first_free_order_and_no_mutation(self):
        words = [0xFFFFFFFF, 0xFFFFFFFD, 0, 0]
        result = TOOL["first_free_preview"](words, 128)
        self.assertEqual(result["reserved_index"], 33)
        self.assertTrue(result["creation_admitted"])
        self.assertEqual(result["bitmap_words"][1], 0xFFFFFFFF)
        self.assertEqual(words[1], 0xFFFFFFFD)
        self.assertIsNone(TOOL["first_free_preview"]([0xFFFFFFFF] * 4, 128)["reserved_index"])
        self.assertIsNone(TOOL["first_free_preview"]([], 0)["reserved_index"])

    def test_padding_reservation_distinct_from_creation_admission(self):
        result = TOOL["first_free_preview"]([0xFFFFFFFF, 1, 0, 0], 33)
        self.assertEqual(result["reserved_index"], 33)
        self.assertFalse(result["creation_admitted"])
        self.assertEqual(result["bitmap_words"][1], 3)

    def test_preview_rejects_unsafe_shapes(self):
        for words, capacity in (([], 1), ([0] * 4, -1), ([0] * 4, True), ([0] * 4, 65537),
                                ([0] * 3, 33), ([0x100000000] * 4, 128), ([True] * 4, 128)):
            with self.assertRaises(ValueError):
                TOOL["first_free_preview"](words, capacity)

    def test_embedded_native_and_asset_reports_reproduce(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text())
        self.assertEqual(report, mapping["object_definitions"])
        if ARCHIVE is not None:
            self.assertEqual(TOOL["inspect"](ELF, archive_path=ARCHIVE)["asset_observation"], mapping["object_definitions_assets"])

    def test_actual_nineteen_world_assets_and_counts(self):
        self.native()
        if ARCHIVE is None:
            self.skipTest("Pass --archive")
        assets = TOOL["inspect"](ELF, archive_path=ARCHIVE)["asset_observation"]
        self.assertEqual((assets["named_world_count"], assets["definition_count"]), (19, 18214))
        self.assertEqual([v["level_id"] for v in assets["levels"]], list(range(19)))
        for level in assets["levels"]:
            self.assertEqual(len(level["roots"]), 1)
            self.assertEqual(level["roots"][0]["selector_names"], ["default", ""])
            root = level["roots"][0]
            self.assertEqual(root["definition_count"], level["directory_definition_count"])
            for key in ("classes", "load_modes", "segment_references"):
                self.assertEqual(sum(row["definition_count"] for row in root[key]), root["definition_count"])

    def test_raw_save_bits_not_assigned_asset_names(self):
        self.native()
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 20, i)
        data[0x668] = 0x80
        last = 0x768 + 19 * 0x408
        data[last:last + 256] = b"\xFF" * 256
        with tempfile.TemporaryDirectory(prefix="tod-definition-save-") as directory:
            path = Path(directory) / "snapshot.bin"
            path.write_bytes(data)
            observation = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(path.read_bytes(), data)
        self.assertEqual(observation["worlds"][0]["recorded_set_count"], 1)
        self.assertEqual(observation["worlds"][19]["suppression_set_count"], 2048)
        self.assertNotIn("class_id", json.dumps(observation["worlds"]))

    def test_actual_save_and_elf_unchanged(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in (ELF, SAVE)]
        report = TOOL["inspect"](ELF, SAVE)
        self.assertEqual(report["save_observation"]["sha256"], "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
        self.assertTrue(all(v["recorded_set_count"] == v["suppression_set_count"] == 0 for v in report["save_observation"]["worlds"]))
        self.assertEqual([hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in (ELF, SAVE)], before)

    def test_layout_covers_asset_record_without_claiming_saved_uid(self):
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text())
        layout = next(v for v in mapping["structures"] if v["name"] == "TOD_AssetObjectDefinition_verified")
        end = 0
        for field in layout["fields"]:
            self.assertEqual(int(field["offset"], 0), end)
            end += {"u8": 1, "u16": 2, "u32": 4, "f32": 4}[field["type"]] * field.get("count", 1)
        self.assertEqual(end, 0x48)
        self.assertIn("Not GAME.SAV", layout["comment"])
        self.assertNotIn("uid", {f["name"] for f in layout["fields"]})

    def test_malformed_save_inputs_rejected_unchanged(self):
        self.native()
        with tempfile.TemporaryDirectory(prefix="tod-definition-invalid-") as directory:
            path = Path(directory) / "snapshot.bin"
            for raw in (b"", b"\0" * 0x906EF, b"\0" * 0x906F1, b"\0" * 0x906F0):
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)
                self.assertEqual(path.read_bytes(), raw)

    def test_unknown_segment_index_is_preserved_not_named(self):
        raw = fixture()
        struct.pack_into(">H", raw, 0x244, 0xFFFF)
        root = TOOL["gameplay_definitions"](raw)["roots"][0]
        self.assertEqual(root["segment_references"][-1], {"loaded_name_index": 65535, "reference_name": None, "definition_count": 1})
        self.assertEqual(root["examples"][0]["segment_name_index"], 65535)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE, ARCHIVE = args.elf, args.save, args.archive
    unittest.main(argv=[__file__] + remaining)
