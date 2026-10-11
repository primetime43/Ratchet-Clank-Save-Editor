"""Exact native class registry, opaque packet boundaries and resource arguments."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodObjectClasses.py"))
ELF = ARCHIVE = None


def class_fixture():
    raw = bytearray(0x410)
    struct.pack_into(">8I", raw, 0, 0x49474857, 0x10001, 2, 64, 0x400, 4, 0xDEADDEAD, 0xDEADDEAD)
    struct.pack_into(">4I", raw, 32, 0xD100, 0x80, 0x10000002, 0xC0)
    struct.pack_into(">4I", raw, 48, 0x10200, 0x200, 1, 0x200)
    for i in range(2):
        record, header, packet = 0x80 + i * 0xC0, 0x200 + i * 0x40, 0x2C0 + i * 0x10
        struct.pack_into(">I", raw, record + 0x64, 0xFFFFFFFF if i else 0xABCD1234)
        struct.pack_into(">I", raw, record + 0x78, header)
        struct.pack_into(">I", raw, header + 0x38, packet)
        raw[packet:packet + 13] = bytes.fromhex("FEDCBA9876543210") + b"\x04A\0\xFF\x80"
    struct.pack_into(">4I", raw, 0x400, 0xF8, 0x1B8, 0x238, 0x278)
    return raw


class ObjectClassChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_exact_native_guard_bytes_and_alias_identity(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        self.assertEqual(len(report["instruction_guards"]), 64)
        for guard in report["instruction_guards"]:
            self.assertEqual(elf.read(int(guard["va"], 0), len(guard["bytes"]) // 2).hex().upper(), guard["bytes"])
        registry = report["registry"]
        self.assertEqual(int(registry["class_subobject_va"], 0), int(registry["pool_root_va"], 0) + 0x80)
        self.assertEqual(int(registry["class_pointer_array_va"], 0), int(registry["pool_root_va"], 0) + 0xBC)
        self.assertIn("not a native class-ID bound check", registry["reset"])

    def test_d100_class_ordinals_source_relocation_and_raw_unknowns(self):
        raw = class_fixture()
        before = bytes(raw)
        report = TOOL["main_classes"](raw)
        self.assertEqual(report["class_count"], 2)
        self.assertEqual([r["class_id"] for r in report["classes"]], [0, 1])
        self.assertEqual(report["classes"][0]["default_primary_actor_identifier"], "0xABCD1234")
        self.assertEqual(report["classes"][1]["default_primary_actor_identifier"], "0xFFFFFFFF")
        self.assertEqual(bytes.fromhex(report["classes"][0]["class_record_raw_hex"]), raw[0x80:0x140])
        self.assertEqual(report["classes"][0]["flag_packet"]["payload_hex"], "4100FF80")
        self.assertEqual(raw, before)

    def test_d100_invalid_directories_and_unrelocated_links_rejected(self):
        for offset, value in ((8, 0), (12, 63), (16, 0x4000000), (32, 0x10200),
                              (36, 0x201), (40, 4097), (44, 0xBF), (56, 2),
                              (0xF8, 0x1FF), (0xF8, 0x3C4), (0x238, 0x1FF),
                              (0x238, 0x3FF), (0x400, 0xF9), (0x404, 0xF8),
                              (0x408, 0x234), (0x400, 0xF4)):
            raw = class_fixture()
            struct.pack_into(">I", raw, offset, value)
            before = bytes(raw)
            with self.assertRaises(ValueError, msg=hex(offset)):
                TOOL["main_classes"](raw)
            self.assertEqual(raw, before)
        raw = class_fixture()
        excessive_count = (0x400 - 64) // 4 + 1
        raw.extend(b"\0" * (excessive_count * 4 - 16))
        struct.pack_into(">I", raw, 20, excessive_count)
        with self.assertRaisesRegex(ValueError, "possible unique aligned body locations"):
            TOOL["main_classes"](raw)

    def test_d100_packet_end_boundary_and_no_name_assumption(self):
        raw = class_fixture()
        struct.pack_into(">I", raw, 0x238, 0x3F7)
        raw[0x3FF] = 0
        self.assertEqual(TOOL["main_classes"](raw)["classes"][0]["flag_packet"]["payload_length"], 0)
        raw[0x3FF] = 1
        with self.assertRaises(ValueError):
            TOOL["main_classes"](raw)
        for raw in (b"", class_fixture()[:-1]):
            with self.assertRaises(ValueError):
                TOOL["main_classes"](raw)

    def test_opaque_packet_all_bytes_retained(self):
        raw = bytearray(bytes.fromhex("FEDCBA9876543210") + b"\x04\0\xFF\x80A")
        before = bytes(raw)
        result = TOOL["flag_packet"](raw)
        self.assertEqual(result["flags_hex"], "FEDCBA9876543210")
        self.assertEqual(result["payload_length"], 4)
        self.assertEqual(result["payload_hex"], "00FF8041")
        self.assertEqual(bytes.fromhex(result["raw_hex"]), before)
        self.assertEqual(raw, before)

    def test_packet_zero_and_unsigned_max_length(self):
        self.assertEqual(TOOL["flag_packet"](b"\0" * 9)["payload_length"], 0)
        result = TOOL["flag_packet"](b"\xFF" * 9 + bytes(range(255)))
        self.assertEqual(result["payload_length"], 255)
        self.assertEqual(bytes.fromhex(result["payload_hex"]), bytes(range(255)))

    def test_packet_truncated_or_trailing_payload_rejected(self):
        for raw in (b"", b"\0" * 8, b"\0" * 8 + b"\x02A", b"\0" * 9 + b"A"):
            with self.assertRaises(ValueError):
                TOOL["flag_packet"](raw)

    def test_ascii_payload_is_not_assigned_object_name(self):
        result = TOOL["flag_packet"](b"\0" * 8 + b"\x07Ratchet")
        self.assertNotIn("name", result)
        self.assertEqual(result["payload_hex"], b"Ratchet".hex().upper())
        report = self.native()
        self.assertIn("no NUL/text decoding assumption", report["class_preparation"]["payload_boundary"])

    def test_only_all_ones_primary_uses_class_default(self):
        for explicit in (0, 1, 0x80000000, 0xFFFFFFFE):
            result = TOOL["actor_lookup_inputs"](explicit, 0x12345678)
            self.assertEqual(result["primary"], explicit)
            self.assertFalse(result["uses_class_default"])
            self.assertEqual(result["secondary"], 0x66)
        result = TOOL["actor_lookup_inputs"](0xFFFFFFFF, 0x12345678)
        self.assertEqual(result["primary"], 0x12345678)
        self.assertTrue(result["uses_class_default"])

    def test_resource_arguments_unsigned_and_never_executed(self):
        for values in ((True, 0, 0x66), (-1, 0, 0x66), (0, 0x100000000, 0x66), (0, 0, "66")):
            with self.assertRaises(ValueError):
                TOOL["actor_lookup_inputs"](*values)
        result = TOOL["actor_lookup_inputs"](0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF)
        self.assertEqual((result["primary"], result["secondary"]), (0xFFFFFFFF, 0xFFFFFFFF))
        self.assertIn("Arguments only", result["warning"])

    def test_native_report_matches_embedded_map_when_integrated(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text())
        if "object_classes" not in mapping:
            self.skipTest("Parent has not integrated object_classes report yet")
        self.assertEqual(report, mapping["object_classes"])
        if ARCHIVE is not None:
            self.assertEqual(TOOL["inspect"](ELF, ARCHIVE)["asset_observation"], mapping["object_classes_assets"])

    def test_reference_numeric_class_catalog_no_name_claim(self):
        self.native()
        if ARCHIVE is None:
            self.skipTest("Pass --archive")
        report = TOOL["inspect"](ELF, ARCHIVE)["asset_observation"]
        self.assertEqual(report["named_world_count"], 19)
        self.assertEqual(report["definition_count"], 18214)
        self.assertEqual(sum(row["reference_definition_count"] for row in report["classes"]), 18214)
        self.assertEqual([row["class_id"] for row in report["classes"]], sorted({row["class_id"] for row in report["classes"]}))
        self.assertEqual(min(row["class_id"] for row in report["classes"]), 0)
        self.assertEqual(max(row["class_id"] for row in report["classes"]), 118)
        self.assertTrue(all("name" not in row for row in report["classes"]))
        self.assertEqual(len(report["levels"]), 19)
        self.assertEqual(sum(level["class_count"] for level in report["levels"]), report["reference_class_record_count"])
        for level in report["levels"]:
            self.assertEqual(len(level["classes"]), level["class_count"])
            for row in level["classes"]:
                self.assertNotIn("class_record_raw_hex", row)
                self.assertNotIn("source_header_raw_hex", row)
                self.assertNotIn("payload_hex", row["flag_packet"])
                self.assertEqual(len(row["flag_packet"]["payload_sha256"]), 64)

    def test_elf_source_unchanged_and_wrong_hash_rejected(self):
        self.native()
        before = hashlib.sha256(Path(ELF).read_bytes()).digest()
        TOOL["inspect"](ELF)
        self.assertEqual(hashlib.sha256(Path(ELF).read_bytes()).digest(), before)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "wrong.elf"
            raw = bytearray(Path(ELF).read_bytes())
            raw[-1] ^= 1
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                TOOL["inspect"](path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--archive", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, ARCHIVE = args.elf, args.archive
    unittest.main(argv=[__file__] + remaining)
