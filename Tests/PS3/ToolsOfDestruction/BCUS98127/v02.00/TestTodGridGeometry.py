"""Exact-native grid projection, copied display rectangles and raw-byte preservation."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGridGeometry.py"))
ELF, SAVE = None, None


class GridGeometryChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def fixture(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i*20, i)
        return data

    def test_reproduces_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(TOOL["inspect"](ELF), mapping["grid_geometry"])

    def test_signed_projection_and_buffer_order_are_qualified(self):
        report = TOOL["inspect"](ELF)
        self.assertIn("zero -> -1; nonzero -> +1", report["projection"]["sign"])
        self.assertIn("Negative t gives555", report["projection"]["formula"])
        self.assertIn("+38-derived coordinate first", report["projection"]["buffer_order"])
        self.assertIn("cannot be reconstructed", report["projection"]["limits"])

    def test_brush_has_native_center_class_predicate(self):
        brush = TOOL["inspect"](ELF)["brush"]
        mask = bytes.fromhex(brush["mask_hex"])
        self.assertEqual(len(mask), 196)
        self.assertEqual(mask.count(255), 129)
        self.assertEqual(mask.count(0), 67)
        self.assertIn("(center_class & brush_byte)==candidate_class", brush["predicate"])
        self.assertIn("causes the corresponding loop to skip", brush["range"])
        self.assertIn("not an unconditional skip", brush["zero_mask"])

    def test_last_slot_group_unsigned_extents_nonboolean_flags_preserved(self):
        data = self.fixture()
        offset = 0x114D8+20*0x60DC
        group_offset = offset+0x20+6*24
        struct.pack_into(">6I", data, group_offset, 0xFFFFFFFF, 0xFFFFFFFF, 0x80000000, 0xFFFFFFFF, 0x80000000, 0xFFFFFFFF)
        data[offset+0xCC] = 7
        data[offset+0x60DA] = 0xAB
        data[offset+0x60DB] = 0xCD
        data[offset+13:offset+16] = b"\x11\x22\x33"
        data[offset+29:offset+32] = b"\x44\x55\x66"
        with tempfile.TemporaryDirectory(prefix="tod-grid-geometry-") as folder:
            path = Path(folder)/"GAME.bin"
            path.write_bytes(data)
            observed = TOOL["inspect"](ELF, path)["save_observation"]["blocks"][-1]
            self.assertEqual(observed["ready_byte"], 7)
            group = observed["groups"][-1]
            self.assertEqual(group["coordinate_1"], 0xFFFFFFFF)
            self.assertEqual(group["coordinate_2"], 0x80000000)
            self.assertEqual(group["extent_1"], 0xFFFFFFFF)
            self.assertEqual(group["extent_2"], 0x80000000)
            self.assertFalse(group["within_512"])
            self.assertEqual(group["saved_flag"], 0xAB)
            self.assertEqual(observed["unknown_tail_60db"], 0xCD)
            self.assertEqual(observed["unknown_header_0d_to_0f"], "112233")
            self.assertEqual(observed["unknown_header_1d_to_1f"], "445566")
            self.assertEqual(path.read_bytes(), data)

    def test_not_ready_fields_are_retained_without_counting_active(self):
        data = self.fixture()
        struct.pack_into(">I", data, 0x114D8+0x2C, 5)
        with tempfile.TemporaryDirectory(prefix="tod-grid-retained-") as folder:
            path = Path(folder)/"GAME.bin"
            path.write_bytes(data)
            observed = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(observed["ready_nonzero_extent_groups"], 0)
            self.assertEqual(observed["blocks"][0]["groups"][0]["extent_1"], 5)
            self.assertEqual(path.read_bytes(), data)

    def test_invalid_inputs_rejected(self):
        with tempfile.TemporaryDirectory(prefix="tod-grid-invalid-") as folder:
            path = Path(folder)/"input.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)

    def test_actual_rectangles_and_original_hash_preserved(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual plaintext validation")
        before = hashlib.sha256(SAVE.read_bytes()).hexdigest().upper()
        observed = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(observed["plaintext_sha256"], before)
        self.assertEqual(observed["ready_nonzero_extent_groups"], 33)
        self.assertTrue(observed["all_active_rectangles_within_512"])
        active = [g for b in observed["blocks"] if b["ready_byte"] for g in b["groups"] if g["nonzero_extent_1"]]
        self.assertEqual(sum(g["saved_flag"] != 0 for g in active), 28)
        self.assertEqual((min(g["coordinate_1"] for g in active), max(g["coordinate_1"] for g in active)), (4,454))
        self.assertEqual((min(g["coordinate_2"] for g in active), max(g["coordinate_2"] for g in active)), (27,439))
        self.assertEqual(hashlib.sha256(SAVE.read_bytes()).hexdigest().upper(), before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__, *remaining])
