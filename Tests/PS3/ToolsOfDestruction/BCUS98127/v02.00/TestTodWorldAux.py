"""Exact initializer coverage, opaque tails and immutable save observations."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("world_aux", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWorldAux.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i*0x14, i)
    return data


class WorldAuxChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(TOOL.inspect(ELF), mapping["world_aux_fields"])

    def test_exact_initializer_footprint_and_copy_coverage(self):
        report = TOOL.inspect(ELF)
        storage, initializer = report["storage"], report["world_initializer"]
        self.assertEqual(storage["physical_world_slots"], 20)
        self.assertEqual(storage["named_world_slots"], 19)
        self.assertEqual(report["segment_initializer"]["written_ranges"], [{"start": "0x0", "end_exclusive": "0x2d", "size": 45}])
        self.assertEqual(report["segment_initializer"]["word28"]["write_va"], "0x35dda0")
        self.assertEqual(initializer["written_bytes_per_world"], 998)
        self.assertEqual(initializer["untouched_bytes_per_world"], 34)
        self.assertEqual(initializer["untouched_bytes_all_worlds"], 680)
        holes = {b for r in initializer["untouched_ranges"] for b in range(int(r["start"], 0), int(r["end_exclusive"], 0))}
        expected = {s*0x30+b for s in range(10) for b in (0x2D, 0x2E, 0x2F)} | set(range(0x404, 0x408))
        self.assertEqual(holes, expected)
        # A byte-mask exercise only; no game or save edit is invoked.
        patterned = bytearray(b"\xAB"*0x408)
        for b in set(range(0x408))-holes:
            patterned[b] = 0
        self.assertEqual({i for i, value in enumerate(patterned) if value == 0xAB}, expected)
        for world in range(20):
            for hole in holes:
                self.assertLess(0x488+world*0x408+hole, int(report["full_copy"]["size"], 0))
        self.assertIn("not a claim that restart retains", initializer["scope"])

    def test_first_and_last_slots_unsigned_nonfinite_and_raw_tail_bytes(self):
        data = fixture()
        samples = [(0, 0, 0xFFFFFFFF), (0, 9, 0x7FC12345), (19, 0, 0xFF800000), (19, 9, 0x3F800000)]
        for world, slot, bits in samples:
            base = 0x488+world*0x408+slot*0x30
            struct.pack_into(">I", data, base+0x28, bits)
            data[base+0x2D:base+0x30] = b"\x11\x22\xAB"
        for world in (0, 19):
            base = 0x488+world*0x408
            data[base+0x404:base+0x408] = b"\xDE\xAD\xBE\xEF"
        with tempfile.TemporaryDirectory(prefix="tod-world-aux-") as folder:
            path = Path(folder) / "input.bin"
            path.write_bytes(data)
            observed = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual(len(observed["worlds"]), 20)
            for world, slot, bits in samples:
                entry = observed["worlds"][world]["segments"][slot]
                self.assertEqual(entry["offset"], hex(0x488+world*0x408+slot*0x30))
                self.assertEqual(entry["word28_hex"], f"{bits:08X}")
                self.assertEqual(entry["word28_unsigned_interpretation"], bits)
                self.assertEqual(entry["tail_hex"], "1122AB")
            self.assertEqual(observed["worlds"][0]["segments"][9]["word28_float_interpretation"], "nan")
            self.assertEqual(observed["worlds"][19]["segments"][0]["word28_float_interpretation"], "-inf")
            for world in (0, 19):
                self.assertEqual(observed["worlds"][world]["world_tail_hex"], "DEADBEEF")
            json.dumps(observed, allow_nan=False)
            self.assertEqual(path.read_bytes(), data)

    def test_rejects_bad_inputs(self):
        with tempfile.TemporaryDirectory(prefix="tod-world-aux-invalid-") as folder:
            path = Path(folder) / "input.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_save_bytes_and_original_inputs_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual snapshot validation")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observed = TOOL.inspect(ELF, SAVE)["save_observation"]
        raw = SAVE.read_bytes()
        for world in observed["worlds"]:
            base = int(world["offset"], 0)
            self.assertEqual(world["world_tail_hex"], raw[base+0x404:base+0x408].hex().upper())
            for segment in world["segments"]:
                p = int(segment["offset"], 0)
                self.assertEqual(segment["word28_hex"], raw[p+0x28:p+0x2C].hex().upper())
                self.assertEqual(segment["tail_hex"], raw[p+0x2D:p+0x30].hex().upper())
                self.assertEqual(segment["word28_hex"], "00000000")
                self.assertEqual(segment["tail_hex"], "000000")
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__]+remaining)
