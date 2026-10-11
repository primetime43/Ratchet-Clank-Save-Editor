"""Grid lifecycle native guards, detached image/buffer previews and unchanged snapshots."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("grid_lifecycle", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGridLifecycle.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for index in range(32):
        struct.pack_into(">I", data, index*0x14, index)
    return data


class GridLifecycleChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf for native evidence")
        return TOOL.inspect(ELF)

    def test_reproduces_map(self):
        report = self.native()
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["grid_lifecycle"])

    def test_native_guard_coverage_and_owner(self):
        report = self.native()
        elf = TOOL.BINDINGS.Elf(ELF)
        guards = {int(g["va"], 0): bytes.fromhex(g["bytes"]) for g in report["instruction_guards"]}
        for address, expected in guards.items():
            self.assertEqual(elf.read(address, len(expected)), expected)
        for function in (0x35C5B8, 0x35C460, 0x24DAB8, 0x24DEA8, 0x25B918):
            end = elf.functions[elf.functions.index(function)+1]
            self.assertEqual(len(guards[function]), end-function)
        self.assertGreaterEqual(len(guards[0x244E4C]), 0xFC)
        self.assertEqual(elf.u32(0x897CF8), 0x84C0B0)
        self.assertEqual(elf.u32(elf.u32(0x84C0B0+0x38)), 0x247E78)
        owner = report["owner_provenance"]
        self.assertEqual(int(owner["context_offset"], 0)+int(owner["frame_grid_offset"], 0),
                         int(owner["presnapshot_grid_offset"], 0))
        self.assertIn("first context", owner["limits"])
        self.assertIn("not a proven atomic", report["publication_and_restore"]["encoder_order"])
        self.assertIn("semantically unresolved", report["opaque_members"]["rule"])

    def test_all_image_branch_values(self):
        for logical in (0, 1, 2, 255):
            for image in range(256):
                masked = 0 if logical == 0 else image
                expected = 0 if masked == 0 else ((masked+110) & 255 if masked < 128 else masked-17)
                self.assertEqual(TOOL.image_byte_preview(logical, image), expected)
                self.assertEqual(TOOL.image_byte_preview(logical, image, "other-slot-mask"),
                                 0 if logical == 0 else 127)
        self.assertEqual([TOOL.image_byte_preview(2, x) for x in (0,1,127,128,255)], [0,111,237,111,238])

    def test_exact_display_latch_gate(self):
        self.assertEqual([TOOL.selection_update_enabled(v) for v in (0,1,2,255)], [True,False,True,True])
        for value in (-1,256,True,1.0,None):
            with self.assertRaises(ValueError):
                TOOL.selection_update_enabled(value)

    def test_restore_prefix_keeps_explicit_tail_and_inputs(self):
        initial = bytearray([0xAB])*0x40000
        encoded = bytearray([1,2,3])
        initial_before, encoded_before = bytes(initial), bytes(encoded)
        result, summary = TOOL.restore_buffer_preview(encoded, initial)
        self.assertEqual(result[:3], bytes(encoded))
        self.assertEqual(result[3:], initial_before[3:])
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["decoded_size"], 3)
        self.assertEqual(bytes(initial), initial_before)
        self.assertEqual(bytes(encoded), encoded_before)
        result, summary = TOOL.restore_buffer_preview(b"", initial)
        self.assertEqual(result, initial_before)
        self.assertEqual(summary["decoded_size"], 0)

    def test_preview_input_domain_and_bounds(self):
        for invalid in (None, [], "bytes", 7, memoryview(b"x")):
            with self.assertRaises(ValueError):
                TOOL.restore_buffer_preview(invalid, bytes(0x40000))
            with self.assertRaises(ValueError):
                TOOL.restore_buffer_preview(b"", invalid)
        for encoded, initial in ((b"\0\0\1", bytes(0x40000)), (bytes(0x6000), bytes(0x40000)), (b"", b"")):
            with self.assertRaises(ValueError):
                TOOL.restore_buffer_preview(encoded, initial)
        for logical, image, mode in ((-1,0,"active-overlay"),(0,256,"active-overlay"),
                                     (True,0,"active-overlay"),(0,1.0,"active-overlay"),(0,0,"unknown")):
            with self.assertRaises(ValueError):
                TOOL.image_byte_preview(logical, image, mode)

    def test_ready_nonzero_mismatch_is_observation_not_repair(self):
        self.native()
        data = fixture()
        offset = 0x114D8
        data[offset+0xCC] = 255
        data[offset+0xCD] = 3
        struct.pack_into(">I", data, offset+0x60D0, 1)
        struct.pack_into(">I", data, offset+0xC8, 0xFFFFFFFF)
        data[offset+13:offset+16] = b"\xA1\xB2\xC3"
        data[offset+29:offset+32] = b"\xF1\xE2\xD3"
        data[offset+0x60D4:offset+0x60DC] = bytes([0,255,1,2,3,4,5,0xA5])
        # The second slot is unready but retains unknown bytes and an invalid declared length.
        second = offset+0x60DC
        struct.pack_into(">I", data, second+0x60D0, 0xFFFFFFFF)
        struct.pack_into(">I", data, second+0xC8, 0x12345678)
        with tempfile.TemporaryDirectory(prefix="tod-grid-lifecycle-") as folder:
            path = Path(folder)/"snapshot.bin"
            path.write_bytes(data)
            observation = TOOL.inspect(ELF,path)["save_observation"]
            row, untouched = observation["blocks"][:2]
            self.assertEqual(row["ready_byte"], 255)
            self.assertEqual(row["decoded"]["decoded_size"], 1)
            self.assertFalse(row["accumulator_matches_research_decode"])
            self.assertEqual(row["saved_accumulator"], 0xFFFFFFFF)
            self.assertEqual(row["opaque_0d_to_0f"], "A1B2C3")
            self.assertEqual(row["opaque_1d_to_1f"], "F1E2D3")
            self.assertEqual(row["opaque_60db"], 0xA5)
            self.assertEqual(row["raw_group_flags"], [0,255,1,2,3,4,5])
            self.assertIsNone(untouched["decoded"])
            self.assertIsNone(untouched["accumulator_matches_research_decode"])
            self.assertEqual(untouched["encoded_length"], 0xFFFFFFFF)
            self.assertIn("not a native restore check", observation["scope"])
            self.assertEqual(path.read_bytes(), data)

    def test_invalid_ready_streams_remain_raw(self):
        self.native()
        data = fixture()
        offset = 0x114D8
        data[offset+0xCC] = 1
        with tempfile.TemporaryDirectory(prefix="tod-grid-invalid-") as folder:
            path = Path(folder)/"snapshot.bin"
            for length, payload, error in ((0x6000,b"", "cap"),(3,b"\0\0\1", "Truncated")):
                struct.pack_into(">I",data,offset+0x60D0,length)
                data[offset+0xCD:offset+0xCD+len(payload)] = payload
                path.write_bytes(data)
                row = TOOL.inspect(ELF,path)["save_observation"]["blocks"][0]
                self.assertIn(error,row["status"])
                self.assertIsNone(row["decoded"])
                self.assertEqual(path.read_bytes(),data)

    def test_invalid_snapshot_shape_and_identity(self):
        self.native()
        with tempfile.TemporaryDirectory(prefix="tod-grid-shape-") as folder:
            path = Path(folder)/"snapshot.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError,"plaintext"):
                    TOOL.inspect(ELF,path)

    def test_actual_snapshot_and_originals_unchanged(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save for actual snapshot")
        before = [hashlib.sha256(path.read_bytes()).digest() for path in (ELF,SAVE)]
        observation = TOOL.inspect(ELF,SAVE)["save_observation"]
        ready = [row for row in observation["blocks"] if row["ready_byte"] != 0]
        self.assertEqual(len(ready), 19)
        self.assertEqual([r["slot"] for r in observation["blocks"] if r["ready_byte"] == 0], [3,4])
        self.assertTrue(all(r["decoded"]["complete"] for r in ready))
        self.assertTrue(all(r["decoded"]["clipped_run_bytes"] == 4 for r in ready))
        self.assertTrue(all(r["accumulator_matches_research_decode"] for r in ready))
        self.assertEqual(before,[hashlib.sha256(path.read_bytes()).digest() for path in (ELF,SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf",type=Path)
    parser.add_argument("--save",type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf,args.save
    unittest.main(argv=[__file__]+remaining)
