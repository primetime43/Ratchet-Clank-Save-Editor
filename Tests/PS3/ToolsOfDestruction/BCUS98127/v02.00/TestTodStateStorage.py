"""Bounded native RLE/equipment checks. Fixtures are not gameplay captures."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("storage", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodStateStorage.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


class StorageChecks(unittest.TestCase):
    def test_literal_and_zero_run_accumulator(self):
        data, result = TOOL.decode_stream(b"\x01\x00\x00\x00\x03\x02")
        self.assertEqual(data, b"\x01" + b"\0" * 5 + b"\x02")
        self.assertEqual(result["encoder_accumulator"], 3)
        self.assertEqual(result["value_histogram"], {"0": 5, "1": 1, "2": 1})
        self.assertFalse(result["complete"])

    def test_output_cap_run_clipping_and_trailing_bytes(self):
        data, result = TOOL.decode_stream(b"\0\0\xff\xff" * 4 + b"\x05")
        self.assertEqual(len(data), 0x40000)
        self.assertEqual(result["clipped_run_bytes"], 4)
        self.assertEqual(result["consumed"], 16)
        self.assertEqual(result["trailing_encoded_bytes"], 1)
        self.assertEqual(result["encoder_accumulator"], 4 * 65535)
        self.assertTrue(result["complete"])

    def test_truncated_tokens_and_last_output_pair_boundary(self):
        with self.assertRaisesRegex(ValueError, "cap"):
            TOOL.decode_stream(bytes(0x6000))
        for encoded in (b"\0\0", b"\0\0\x05"):
            with self.assertRaisesRegex(ValueError, "Truncated"):
                TOOL.decode_stream(encoded)
        encoded = b"\x01\x01\xff\xff" * 3 + b"\x02\x02\xff\xf8" + b"\x03\x03\x03"
        data, result = TOOL.decode_stream(encoded)
        self.assertEqual(len(data), 0x40000)
        self.assertEqual(data[-3:], b"\x03\x03\x03")
        self.assertEqual(result["clipped_run_bytes"], 0)

    def require_elf(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_map_and_layout(self):
        self.require_elf()
        report = TOOL.inspect(ELF)
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text())
        self.assertEqual(report, mapping["state_storage"])
        self.assertEqual(report["equipment_history"]["offsets"], ["0x42c", "0x430", "0x434"])
        self.assertEqual(report["rle_blocks"]["count"], 21)
        self.assertEqual(report["rle_blocks"]["end_exclusive"], "0x906e4")
        self.assertEqual(report["rle_blocks"]["payload_member"], "0xcd")

    def test_hostile_lengths_readiness_and_history_not_normalized(self):
        self.require_elf()
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 0x14, i)
        struct.pack_into(">3i", data, 0x42C, -1, 999, -123)
        base = 0x114D8
        struct.pack_into(">I", data, base + 0x60D0, 0xFFFFFFFF)
        data[base + 0xCC] = 255
        struct.pack_into(">I", data, base + 0x60DC + 0x60D0, 0xFFFFFFFF)
        with tempfile.TemporaryDirectory(prefix="tod-storage-test-") as temporary:
            path = Path(temporary) / "GAME.SAV"
            path.write_bytes(data)
            actual = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual(actual["equipment_history_ids"], [-1, 999, -123])
            self.assertIn("exceeds native", actual["blocks"][0]["status"])
            self.assertEqual(actual["blocks"][0]["ready_byte"], 255)
            self.assertIn("not interpreted", actual["blocks"][1]["status"])
            self.assertEqual(path.read_bytes(), data)

    def test_actual_blocks_and_inputs_unchanged(self):
        self.require_elf()
        if SAVE is None:
            self.skipTest("Pass --save for actual observations")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        actual = TOOL.inspect(ELF, SAVE)["save_observation"]
        self.assertEqual(len(actual["blocks"]), 21)
        if actual["plaintext_sha256"] == "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463":
            self.assertEqual(actual["equipment_history_ids"], [15, 25, 0])
            ready = [b for b in actual["blocks"] if b["ready_byte"]]
            self.assertEqual(len(ready), 19)
            self.assertTrue(all(b["complete"] and b["accumulator_matches"] for b in ready))
            self.assertTrue(all(b["clipped_run_bytes"] == 4 and b["trailing_encoded_bytes"] == 0 for b in ready))
            self.assertEqual(actual["blocks"][0]["decoded_sha256"], "2CE4BB0E543C205E2524A6AA309B008F6824695EEAC68040847393F598EF9CD8")
            self.assertEqual(actual["blocks"][11]["value_histogram"]["2"], 297)
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
