"""Exact-native copied generation handles and unresolved grid auxiliary bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p/"Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT/"Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGridAux.py"))
ELF, SAVE, ARCHIVE = None, None, None


class GridAuxChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def fixture(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i*20, i)
        return data

    def test_report_matches_map(self):
        mapping = json.loads((ROOT/"docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        if "grid_aux_fields" not in mapping:
            self.skipTest("Parent integration has not embedded grid_aux_fields yet")
        self.assertEqual(TOOL["inspect"](ELF), mapping["grid_aux_fields"])

    def test_runtime_handle_consumer_and_loader_are_guarded(self):
        report = TOOL["inspect"](ELF)
        header = report["runtime_header"]
        self.assertEqual(header["handle_member"], "0x8")
        self.assertEqual(header["pool_slots"], 512)
        self.assertIn("entire requested generation/slot", header["resolution"])
        self.assertIn("preserve allocated definition+08", header["loading"])
        self.assertIn("wraps16 bits", header["allocation"])
        self.assertIn("Never resolve", report["warning"])
        guarded = {int(g["va"],0) for g in report["instruction_guards"]}
        self.assertTrue({0x64D828,0x64D9E0,0x64DAB0,0x64DB68,0x64DC50,0x64DCF0,0x35E070}.issubset(guarded))

    def test_shipped_fingerprints_reproduce_map_without_private_save_data(self):
        if ARCHIVE is None:
            self.skipTest("Pass --archive for original shipped-resource checks")
        mapping = json.loads((ROOT/"docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        report = TOOL["inspect"](ELF, archive_path=ARCHIVE)["asset_observation"]
        self.assertEqual(report, mapping["grid_aux_assets"])
        self.assertEqual(len(report["definition_candidates"]), 19)
        self.assertTrue(all("actual_save_body_matches" not in entry and "actual_save_ready_byte" not in entry for entry in report["definition_candidates"]))

    def test_opaque_bytes_not_reclassified_as_padding(self):
        report = TOOL["inspect"](ELF)
        self.assertEqual([(f["member"],f["bytes"]) for f in report["opaque_fields"]], [("0xd",3),("0x1d",3),("0x60db",1)])
        self.assertTrue(all("padding" in f["meaning"] for f in report["opaque_fields"]))
        self.assertIn("does not assign60DB", report["opaque_fields"][-1]["meaning"])

    def test_last_slot_nonboolean_ready_and_unknown_bits_preserved(self):
        data = self.fixture()
        offset = 0x114D8+20*0x60DC
        struct.pack_into(">I", data, offset+8, 0xABCDFFFF)
        data[offset+0xCC] = 7
        data[offset+13:offset+16] = b"\x11\x22\x33"
        data[offset+29:offset+32] = b"\x44\x55\x66"
        data[offset+0x60DB] = 0xCD
        with tempfile.TemporaryDirectory(prefix="tod-grid-aux-") as folder:
            path = Path(folder)/"GAME.bin"
            path.write_bytes(data)
            observed = TOOL["inspect"](ELF,path)["save_observation"]["blocks"][-1]
            self.assertEqual(observed["ready_byte"],7)
            self.assertEqual(observed["handle_bits"],"0xabcdffff")
            self.assertEqual(observed["generation"],0xABCD)
            self.assertEqual(observed["runtime_slot"],0xFFFF)
            self.assertFalse(observed["slot_within_native_pool"])
            self.assertEqual(observed["unknown_0d_to_0f"],"112233")
            self.assertEqual(observed["unknown_1d_to_1f"],"445566")
            self.assertEqual(observed["unknown_60db"],0xCD)
            self.assertEqual(path.read_bytes(),data)

    def test_not_ready_handle_not_repaired_or_resolved(self):
        data = self.fixture()
        struct.pack_into(">I",data,0x114D8+8,0xFFFFFFFF)
        with tempfile.TemporaryDirectory(prefix="tod-grid-aux-retained-") as folder:
            path = Path(folder)/"GAME.bin"
            path.write_bytes(data)
            block = TOOL["inspect"](ELF,path)["save_observation"]["blocks"][0]
            self.assertEqual(block["ready_byte"],0)
            self.assertEqual(block["handle_bits"],"0xffffffff")
            self.assertEqual(path.read_bytes(),data)

    def test_invalid_inputs_rejected(self):
        with tempfile.TemporaryDirectory(prefix="tod-grid-aux-invalid-") as folder:
            path = Path(folder)/"input.bin"
            for data in (b"invalid",bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF,path)
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF,archive_path=path)

    def test_actual_ready_generation_handles_and_snapshot_immutable(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual plaintext checks")
        before = hashlib.sha256(SAVE.read_bytes()).hexdigest().upper()
        observed = TOOL["inspect"](ELF,SAVE)["save_observation"]
        ready = [b for b in observed["blocks"] if b["ready_byte"]]
        self.assertEqual(len(ready),19)
        self.assertTrue(all(b["generation"]==1 and b["slot_within_native_pool"] for b in ready))
        self.assertEqual((min(b["runtime_slot"] for b in ready),max(b["runtime_slot"] for b in ready)),(5,76))
        self.assertLess(len({b["handle_bits"] for b in ready}),19)
        self.assertTrue(all(b["unknown_0d_to_0f"]=="000000" and b["unknown_1d_to_1f"]=="000000" and b["unknown_60db"]==0 for b in observed["blocks"]))
        self.assertEqual(observed["plaintext_sha256"],before)
        self.assertEqual(hashlib.sha256(SAVE.read_bytes()).hexdigest().upper(),before)

    def test_original_shipped_definition_bodies_match_actual_ready_headers(self):
        if SAVE is None or ARCHIVE is None:
            self.skipTest("Pass --save and --archive for bounded original asset comparisons")
        before = hashlib.sha256(SAVE.read_bytes()).hexdigest().upper()
        observed = TOOL["inspect"](ELF,SAVE,ARCHIVE)["asset_observation"]
        entries = observed["definition_candidates"]
        self.assertEqual(len(entries),19)
        self.assertEqual(len({e["stored_slot"] for e in entries}),19)
        self.assertTrue(all(e["source_first12_hex"]=="000000000000000000000000" for e in entries))
        self.assertTrue(all(e["actual_save_body_matches"] and e["actual_save_ready_byte"] for e in entries))
        self.assertTrue(all(e["source_unknown_0d_to_0f"]=="000000" and e["source_unknown_1d_to_1f"]=="000000" for e in entries))
        self.assertIn("not a complete resource schema",observed["scope"])
        self.assertEqual(hashlib.sha256(SAVE.read_bytes()).hexdigest().upper(),before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf",type=Path)
    parser.add_argument("--save",type=Path)
    parser.add_argument("--archive",type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE, ARCHIVE = options.elf, options.save, options.archive
    unittest.main(argv=[__file__,*remaining])
