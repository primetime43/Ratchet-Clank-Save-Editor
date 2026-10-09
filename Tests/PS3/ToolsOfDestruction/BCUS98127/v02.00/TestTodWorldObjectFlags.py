"""Exact native map, independent BE64 slot-order and immutable snapshot checks."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("world_objects", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWorldObjectFlags.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


class WorldObjectFlagChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_native_map_boundaries_and_mode_qualifications(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        report = TOOL.inspect(ELF)
        self.assertEqual(report, mapping["world_object_flags"])
        self.assertEqual(report["world_stride"], "0x408")
        self.assertEqual(report["word_count"], 32)
        self.assertEqual(report["physical_bits_per_bitset"], 2048)
        self.assertEqual([v["offset"] for v in report["bitsets"]], ["0x668", "0x768"])
        self.assertEqual(report["segment_update_gate"]["counter_offset"], "0x906ec")
        self.assertIn("clear", report["load_modes"]["mode1"])
        self.assertIn("not universally", report["bitsets"][0]["meaning"].lower())
        self.assertIn("Other modes", report["bitsets"][1]["meaning"])
        record = next(t for t in mapping["structures"] if t["name"] == "TOD_SaveWorldObjectFlags_verified")
        self.assertEqual(record["size"], "0x408")
        self.assertEqual([f["count"] for f in record["fields"][1:3]], [256, 256])

    def test_explicit_bit_order_and_invalid_physical_indices(self):
        expected = {0: (0x66F, 1), 7: (0x66F, 128), 8: (0x66E, 1),
            63: (0x668, 128), 64: (0x677, 1), 2047: (0x760, 128)}
        for slot, (offset, mask) in expected.items():
            location = TOOL.bit_location(0x668, slot)
            self.assertEqual(int(location["byte_offset"], 0), offset)
            self.assertEqual(location["byte_mask"], mask)
            self.assertEqual(location["word_bit"], slot % 64)
        for slot in (-1, 2048, 65535, True, 1.0, "1"):
            with self.assertRaisesRegex(ValueError, "physical"):
                TOOL.bit_location(0x668, slot)

    def test_distinct_bands_all_word_boundaries_and_last_physical_world(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 0x14, i)
        selected = [0, 7, 8, 63, 64, 127, 1023, 1024, 2047]
        # Independent BE64 packing, not the byte-location helper under test.
        for slot in selected:
            offset = 0x668 + slot // 64 * 8
            bits = struct.unpack_from(">Q", data, offset)[0] | (1 << (slot % 64))
            struct.pack_into(">Q", data, offset, bits)
        struct.pack_into(">Q", data, 0x768, 1 << 2)
        last = 0x768 + 19 * 0x408 + 31 * 8
        struct.pack_into(">Q", data, last, 1 << 63)
        data[0x5500:0x5504] = bytes.fromhex("AABBCCDD")  # Adjacent reward tail, never included.
        with tempfile.TemporaryDirectory(prefix="tod-object-bits-") as folder:
            path = Path(folder) / "GAME.bin"
            path.write_bytes(data)
            observed = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual(len(observed["bitsets"]), 40)
            self.assertEqual(observed["bitsets"][0]["set_slots"], selected)
            self.assertEqual(observed["bitsets"][1]["set_slots"], [2])
            self.assertEqual(observed["bitsets"][-1]["set_slots"], [2047])
            self.assertEqual(observed["bitsets"][-1]["raw_be64_words"][-1], "8000000000000000")
            self.assertEqual(path.read_bytes(), data)

    def test_rejects_wrong_elf_size_and_nonplaintext(self):
        with tempfile.TemporaryDirectory(prefix="tod-object-invalid-") as folder:
            path = Path(folder) / "input.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_all40_bands_and_inputs_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual snapshot observations")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observed = TOOL.inspect(ELF, SAVE)["save_observation"]
        data = SAVE.read_bytes()
        for band in observed["bitsets"]:
            offset = int(band["offset"], 0)
            words = struct.unpack_from(">32Q", data, offset)
            self.assertEqual(band["raw_be64_words"], [f"{v:016X}" for v in words])
            self.assertEqual(band["set_count"], sum(v.bit_count() for v in words))
        if observed["plaintext_sha256"] == "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463":
            self.assertEqual(observed["saved_restart_counter"], 3)
            self.assertTrue(all(b["set_count"] == 0 for b in observed["bitsets"]))
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
