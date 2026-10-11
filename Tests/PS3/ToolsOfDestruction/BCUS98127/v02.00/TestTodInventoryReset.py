"""Inventory reset footprint, opaque-byte preservation and immutable inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodInventoryReset.py"))
ELF = SAVE = None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i * 20, i)
    return data


class InventoryResetChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact native evidence")
        return TOOL["inspect"](ELF)

    def test_map_reproduction(self):
        report = self.native()
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["inventory_reset"])

    def test_native_write_widths_and_guard_reproduction(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        writes = report["record_reset"]["writes"]
        touched = {b for w in writes for b in range(int(w["offset"], 0), int(w["offset"], 0) + w["size"])}
        self.assertEqual(touched, set(range(18)))
        self.assertEqual(report["record_reset"]["record_size"], 20)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)

    def test_bulk_initialization_and_prefix_copy_boundaries_are_distinct(self):
        report = self.native()
        self.assertEqual(int(report["bulk_initializer"]["zero_fill_size"], 0), 32 * 20)
        self.assertEqual(report["selective_restart"]["prefix_copy_size"], "0x484")
        self.assertEqual(report["prefix_gap"]["start"], "0x484")
        self.assertEqual(report["prefix_gap"]["end_exclusive"], "0x488")
        self.assertIn("not derived as zero", report["prefix_gap"]["rule"])
        self.assertIn("Later callbacks", report["selective_restart"]["rule"])

    def test_record_preview_keeps_opaque_bytes_for_every_normal_id(self):
        for i in range(32):
            original = bytearray([0xA5] * 20)
            original[18:] = bytes([i, 255 - i])
            before = bytes(original)
            result = TOOL["reset_record_preview"](original, i)
            self.assertEqual(result, struct.pack(">I", i) + bytes(14) + before[18:])
            self.assertEqual(bytes(original), before)

    def test_preview_rejects_invalid_shapes_and_ids(self):
        for record, item_id in [(bytes(19), 1), (bytes(21), 1), ([], 1),
                                (bytes(20), -1), (bytes(20), 32), (bytes(20), True), (bytes(20), 1.0)]:
            with self.assertRaises(ValueError):
                TOOL["reset_record_preview"](record, item_id)

    def test_unknown_snapshot_bytes_remain_raw(self):
        self.native()
        data = fixture()
        data[18:20] = bytes.fromhex("ABCD")
        data[0x484:0x488] = bytes.fromhex("FE123456")
        with tempfile.TemporaryDirectory(prefix="tod-inventory-opaque-") as directory:
            path = Path(directory) / "snapshot.bin"
            path.write_bytes(data)
            observed = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(observed["record_opaque_tails"][0]["hex"], "ABCD")
            self.assertEqual(observed["prefix_gap_hex"], "FE123456")
            self.assertEqual(path.read_bytes(), data)

    def test_bad_snapshot_preflight(self):
        self.native()
        with tempfile.TemporaryDirectory(prefix="tod-inventory-invalid-") as directory:
            path = Path(directory) / "snapshot.bin"
            for data in [b"invalid", bytes(0x906F0)]:
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL["inspect"](ELF, path)

    def test_actual_snapshot_and_inputs_unchanged(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save for detached actual snapshot")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observed = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(len(observed["record_opaque_tails"]), 32)
        self.assertEqual({r["hex"] for r in observed["record_opaque_tails"]}, {"0000"})
        self.assertEqual(observed["prefix_gap_hex"], "00000000")
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, rest = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + rest)
