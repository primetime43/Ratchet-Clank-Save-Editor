"""Exact-build event flag checks; generated bit fixtures are not gameplay captures."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGlobalFlags.py"))
ELF, SAVE = None, None


class GlobalFlagChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_complete_catalog_and_independent_registrations(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        report = TOOL["inspect"](ELF)
        self.assertEqual(report, mapping["global_flags"])
        self.assertEqual([e["id"] for e in report["catalog"]], list(range(292)))
        for entry in report["catalog"]:
            a, b = entry["exports"]
            self.assertEqual((a["id"], a["enum"], a["name_va"]), (b["id"], b["enum"], b["name_va"]))
            self.assertNotEqual(a["name_load_va"], b["name_load_va"])
        self.assertEqual([e["id"] for e in report["count_exports"]], [292, 292])
        self.assertEqual(len(report["named_bindings"]), 6)

    def test_be64_byte_order_and_named_bounds(self):
        report = TOOL["inspect"](ELF)
        for e in report["catalog"]:
            i = e["id"]
            self.assertEqual(int(e["word_offset"], 0), 0x5528 + i // 64 * 8)
            self.assertEqual(int(e["byte_offset"], 0), 0x5528 + i // 64 * 8 + 7 - i % 64 // 8)
            self.assertEqual(int(e["byte_mask"], 0), 1 << (i % 8))
        self.assertEqual(report["catalog"][0]["byte_offset"], "0x552f")
        self.assertEqual(report["catalog"][63]["byte_offset"], "0x5528")
        self.assertEqual(report["catalog"][64]["byte_offset"], "0x5537")
        self.assertEqual(report["storage"]["physical_bits"], 320)
        self.assertEqual(report["storage"]["end_exclusive"], "0x5550")
        self.assertIn("sentinel", report["storage"]["bounds_warning"])
        self.assertEqual(report["acquisition_dependency"]["enum"], "HERO_HAS_TWO_ITEMS")
        self.assertEqual(report["catalog"][10]["enum"], "HERO_HAS_TWO_ITEMS")

    def test_boundary_bits_and_unknown_tail_are_preserved(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 20, i)
        identifiers = [0, 7, 8, 10, 63, 64, 127, 128, 191, 192, 255, 256, 291, 292, 319]
        for i in identifiers:
            offset = 0x5528 + i // 64 * 8
            word = struct.unpack_from(">Q", data, offset)[0] | 1 << (i % 64)
            struct.pack_into(">Q", data, offset, word)
        data[0x5550:0x5558] = b"\xFF" * 8
        with tempfile.TemporaryDirectory(prefix="tod-global-flags-") as temporary:
            path = Path(temporary) / "GAME.bin"
            path.write_bytes(data)
            actual = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(actual["set_named_ids"], identifiers[:-2])
            self.assertEqual(actual["set_unmapped_ids"], [292, 319])
            self.assertEqual(len(actual["raw_words"]), 5)
            self.assertEqual(actual["raw_words"][4], "8000001800000001")
            self.assertEqual(path.read_bytes(), data)

    def test_refuses_bad_layout_and_modified_elf(self):
        with tempfile.TemporaryDirectory(prefix="tod-global-flags-") as temporary:
            path = Path(temporary) / "bad.bin"
            for data in (b"not a save", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL["inspect"](ELF, path)
            data = bytearray(ELF.read_bytes())
            data[0x16E08] ^= 1
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                TOOL["inspect"](path)

    def test_actual_save_and_elf_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual observations")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        actual = TOOL["inspect"](ELF, SAVE)["save_observation"]
        if actual["plaintext_sha256"] == "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463":
            self.assertEqual(actual["raw_words"], ["0" * 16] * 5)
            self.assertEqual(actual["set_named_ids"], [])
            self.assertEqual(actual["set_unmapped_ids"], [])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
