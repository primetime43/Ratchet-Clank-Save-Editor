"""Read-only segment consumer mapping and lifecycle gate checks."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWorldConsumers.py"))
ELF = SAVE = None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i * 20, i)
    return data


class WorldConsumerChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact native evidence")
        return TOOL["inspect"](ELF)

    def test_map_reproduction(self):
        report = self.native()
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["world_consumers"])

    def test_native_guards_and_distinct_pointer_formulas(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)
        # Validity reads the mapping but returns r3/requested slot unchanged.
        self.assertEqual(elf.u32(0x2CDBDC), 0x78630020)
        # Configuration uses r31 populated by indexed table load instead.
        self.assertEqual(elf.u32(0x2CDEE4), 0x7FE9182E)
        self.assertEqual(elf.u32(0x2CDEF8), 0x57E93032)
        self.assertEqual(elf.u32(0x2CDF6C), 0x57E83032)
        self.assertIn("does not reorder", report["runtime_mapping"]["configuration_rule"])

    def test_reset_leaf_has_no_completion_byte_load(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        words = [w for _, w in elf.instructions(0x2CE518, 0x2CE5CC)]
        self.assertFalse(any(w >> 26 == 34 and w & 65535 == 0x2C for w in words))
        self.assertEqual(elf.u32(0x2CE5A0) >> 26, 32)
        self.assertEqual(elf.u32(0x2CE5B0) >> 26, 36)
        self.assertIn("does not test byte2C", report["lifecycle"]["reset"]["rule"])

    def test_completed_byte_blocks_tick_finalizer_but_not_reset(self):
        for byte in (1, 2, 255):
            result = TOOL["lifecycle_gate_preview"](byte, 0, True)
            self.assertFalse(result["completion_would_change"])
            self.assertEqual(result["completion_result_byte"], byte)
            self.assertFalse(result["finalizer_called_by_completion"])
            self.assertFalse(result["finalizer_passes_segment_gates"])
            self.assertFalse(result["tick_passes_segment_gates"])
            self.assertTrue(result["reset_passes_segment_gates"])

    def test_raw_completion_can_change_when_runtime_mapping_is_absent(self):
        result = TOOL["lifecycle_gate_preview"](0, 0, False)
        self.assertTrue(result["completion_would_change"])
        self.assertEqual(result["completion_result_byte"], 1)
        self.assertTrue(result["finalizer_called_by_completion"])
        self.assertFalse(result["finalizer_passes_segment_gates"])
        self.assertFalse(result["reset_passes_segment_gates"])
        self.assertFalse(result["tick_passes_segment_gates"])

    def test_nonzero_restart_blocks_segment_consumers_not_raw_completion(self):
        for replay in (1, 3, 0x80000000, 0xFFFFFFFF):
            result = TOOL["lifecycle_gate_preview"](0, replay, True)
            self.assertTrue(result["completion_would_change"])
            self.assertFalse(result["finalizer_passes_segment_gates"])
            self.assertFalse(result["tick_passes_segment_gates"])
            self.assertFalse(result["reset_passes_segment_gates"])

    def test_unfinished_valid_segment_gate_preview_is_not_full_simulation(self):
        result = TOOL["lifecycle_gate_preview"](0, 0, True)
        self.assertTrue(result["finalizer_passes_segment_gates"])
        self.assertTrue(result["reset_passes_segment_gates"])
        self.assertTrue(result["tick_passes_segment_gates"])
        self.assertIn("additional saved-timer", result["warning"])
        self.assertNotIn("log_count", result)

    def test_invalid_preview_arguments(self):
        for args in ((-1, 0, True), (256, 0, True), (True, 0, True),
                     (1.0, 0, True), (0, -1, True), (0, 1 << 32, True),
                     (0, False, True), (0, 0, 1), (0, 0, None)):
            with self.assertRaises(ValueError):
                TOOL["lifecycle_gate_preview"](*args)

    def test_opaque_snapshot_sentinels_retained_in_first_and_last_slots(self):
        self.native()
        data = fixture()
        for world, slot in ((0, 0), (19, 9)):
            offset = 0x488 + world * 0x408 + slot * 0x30
            data[offset + 0x28:offset + 0x2C] = bytes.fromhex("7FC12345")
            data[offset + 0x2C] = 255
            data[offset + 0x2D:offset + 0x30] = bytes.fromhex("ABCDEF")
            data[0x488 + world * 0x408 + 0x404:0x488 + (world + 1) * 0x408] = bytes.fromhex("FE123456")
        with tempfile.TemporaryDirectory(prefix="tod-world-consumers-") as directory:
            path = Path(directory) / "snapshot.bin"
            path.write_bytes(data)
            report = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(len(report["segments"]), 200)
            for index in (0, 199):
                self.assertEqual(report["segments"][index]["opaque_word28_hex"], "7FC12345")
                self.assertEqual(report["segments"][index]["opaque_tail_hex"], "ABCDEF")
                self.assertEqual(report["segments"][index]["complete_byte"], 255)
            self.assertEqual(report["world_tail_hex"][0], "FE123456")
            self.assertEqual(report["world_tail_hex"][19], "FE123456")
            self.assertEqual(path.read_bytes(), data)

    def test_invalid_snapshot_preflight(self):
        self.native()
        with tempfile.TemporaryDirectory(prefix="tod-world-invalid-") as directory:
            path = Path(directory) / "snapshot.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL["inspect"](ELF, path)

    def test_actual_snapshot_and_inputs_unchanged(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save for detached actual snapshot")
        before = [hashlib.sha256(path.read_bytes()).digest() for path in (ELF, SAVE)]
        observed = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(observed["restart_word"], 3)
        self.assertEqual(observed["log_count"], 0)
        self.assertEqual(len(observed["segments"]), 200)
        self.assertEqual({r["complete_byte"] for r in observed["segments"]}, {0})
        self.assertEqual(set(observed["world_tail_hex"]), {"00000000"})
        self.assertEqual(before, [hashlib.sha256(path.read_bytes()).digest() for path in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, rest = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + rest)
