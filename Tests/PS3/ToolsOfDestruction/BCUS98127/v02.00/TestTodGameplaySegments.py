"""Exact-ELF, scalar-type, buffer-boundary and immutable segment/log checks."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("segments", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGameplaySegments.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


class GameplaySegmentChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_map_and_types(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        report = TOOL.inspect(ELF)
        self.assertEqual(report, mapping["gameplay_segments"])
        segment = next(t for t in mapping["structures"] if t["name"] == "TOD_SaveGameplaySegment_verified")
        log = next(t for t in mapping["structures"] if t["name"] == "TOD_SaveGameplayLog_verified")
        self.assertEqual(segment["fields"][:11], report["segments"]["fields"])
        self.assertEqual(log["fields"][2:], report["log"]["fields"])
        self.assertEqual(report["segments"]["slots_per_world"], 10)
        self.assertEqual(report["segments"]["initialized_world_slots"], 20)
        self.assertEqual(report["log"]["bounded_physical_slots"], 200)
        self.assertEqual(report["log"]["count_offset"], "0x10144")
        self.assertEqual(report["log"]["fields"][-1]["type"], "u32")

    def test_nonboolean_flag_integer_events_nonfinite_bits_and_last_slots(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 0x14, i)
        last = 0x488 + 19 * 0x408 + 9 * 0x30
        struct.pack_into(">I", data, last, 0x7FC12345)
        struct.pack_into(">I", data, last+8, 0xFFFFFFFF)
        data[last+0x2C:last+0x30] = bytes([7, 0xAB, 0xCD, 0xEF])
        log = 0x8764 + 199 * 0x9C
        struct.pack_into(">I", data, log+0x98, 2)
        with tempfile.TemporaryDirectory(prefix="tod-segment-test-") as folder:
            path = Path(folder) / "GAME.bin"
            path.write_bytes(data)
            observation = TOOL.inspect(ELF, path)["save_observation"]
            s = observation["segments"][-1]
            self.assertEqual(s["offset"], hex(last))
            self.assertEqual(s["complete_byte"], 7)
            self.assertEqual(s["unknown_tail"], "ABCDEF")
            self.assertEqual(s["values"]["adjusted_elapsed"]["bits"], "7FC12345")
            self.assertEqual(s["values"]["reset_events"]["value"], "4294967295")
            self.assertEqual(observation["log_entries"][-1]["values"]["reset_events"]["value"], "2")
            self.assertEqual(observation["nonzero_retained_entries"], 1)
            json.dumps(observation, allow_nan=False)
            self.assertEqual(path.read_bytes(), data)

    def test_count_is_not_inferred_from_retained_names_and_reads_are_bounded(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i*0x14, i)
        data[0x8764:0x8764+10] = b"metropolis"
        with tempfile.TemporaryDirectory(prefix="tod-log-test-") as folder:
            path = Path(folder) / "GAME.bin"
            for count in (0, 1, 200, 201, 0xFFFFFFFF):
                struct.pack_into(">I", data, 0x10144, count)
                path.write_bytes(data)
                observed = TOOL.inspect(ELF, path)["save_observation"]
                self.assertEqual(observed["saved_log_count"], count)
                self.assertEqual(len(observed["log_entries"]), 200)
                self.assertEqual(sum(e["within_saved_count"] for e in observed["log_entries"]), min(count, 200))
                self.assertEqual(observed["nonzero_retained_entries"], int(count == 0))
                self.assertEqual(observed["count_exceeds_physical_span"], count > 200)
                self.assertEqual(path.read_bytes(), data)

    def test_rejects_bad_plaintext_and_elf(self):
        with tempfile.TemporaryDirectory(prefix="tod-invalid-test-") as folder:
            path = Path(folder) / "input.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_snapshot_agrees_and_inputs_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual snapshot observations")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observed = TOOL.inspect(ELF, SAVE)["save_observation"]
        data = SAVE.read_bytes()
        for s in observed["segments"]:
            offset = int(s["offset"], 0)
            self.assertEqual(s["values"]["reset_events"]["value"], str(struct.unpack_from(">I", data, offset+8)[0]))
            self.assertEqual(s["complete_byte"], data[offset+0x2C])
        self.assertEqual(observed["saved_log_count"], struct.unpack_from(">I", data, 0x10144)[0])
        for entry in observed["log_entries"]:
            offset = int(entry["offset"], 0)
            self.assertEqual(entry["values"]["reset_events"]["value"], str(struct.unpack_from(">I", data, offset+0x98)[0]))
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
