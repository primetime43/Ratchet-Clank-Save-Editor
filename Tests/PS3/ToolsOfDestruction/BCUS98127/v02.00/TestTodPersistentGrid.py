"""Exact-native grid slot catalog, copied headers, physical bounds and immutable snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodPersistentGrid.py"))
ELF, SAVE = None, None
LEVELS = [14,14,10,10,10,6,6,1,16,3,18,5,11,11,17,0,7,9,15,2,12]


class PersistentGridChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def fixture(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i*20, i)
        return data

    def test_reproduces_map_and_types(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        report = TOOL["inspect"](ELF)
        self.assertEqual(report, mapping["persistent_grid"])
        self.assertEqual(report["blocks"]["header_size"], "0xc8")
        self.assertEqual(report["blocks"]["count"], 21)
        self.assertEqual(report["grid"]["width"]*report["grid"]["height"], 0x40000)
        h = next(t for t in mapping["structures"] if t["name"]=="TOD_SaveGridVolumeHeader_verified")
        g = next(t for t in mapping["structures"] if t["name"]=="TOD_SaveGridGroup_verified")
        self.assertEqual(int(h["size"],0), 0xC8)
        self.assertEqual(int(g["size"],0)*7, h["fields"][-1]["count"])

    def test_all_slot_labels_are_native_not_physical_level_order(self):
        report = TOOL["inspect"](ELF)
        self.assertEqual([e["label_level_id"] for e in report["slot_catalog"]], LEVELS)
        self.assertEqual(report["slot_catalog"][15]["internal_level_name"], "metropolis")
        self.assertEqual(report["slot_catalog"][3]["internal_level_name"], "sargasso")
        self.assertIn("not current planet", report["label_provenance"])
        self.assertIn("not a portable pointer", report["blocks"]["header_provenance"])

    def test_nonboolean_flags_unsigned_header_and_last_group_preserved(self):
        data = self.fixture()
        offset = 0x114D8+20*0x60DC
        for relative,value in ((0,0xDEADBEEF),(4,0x535),(0x10,20),(0x14,0xFFFFFFFF),(0x18,0xFFFFFFFF),
            (0x20+6*24,0x80000000),(0x2C+6*24,7),(0x34+6*24,0xFFFFFFFF)):
            struct.pack_into(">I",data,offset+relative,value)
        data[offset+0x1C]=255
        data[offset+0x60DA]=0xAB
        data[offset+0x60DB]=0xCD
        with tempfile.TemporaryDirectory(prefix="tod-grid-fixture-") as folder:
            path=Path(folder)/"GAME.bin";path.write_bytes(data)
            observed=TOOL["inspect"](ELF,path)["save_observation"]["blocks"][-1]
            self.assertTrue(observed["header_matches_selection"])
            self.assertEqual(observed["runtime_geometry_pointer_bits"],"0xdeadbeef")
            self.assertEqual(observed["coordinate_sign_byte"],255)
            self.assertEqual(observed["groups"][-1]["saved_flag"],0xAB)
            self.assertEqual(observed["groups"][-1]["extent_1"],7)
            self.assertEqual(observed["unknown_last_byte"],0xCD)
            self.assertIsNone(observed["decoded"])
            self.assertEqual(path.read_bytes(),data)

    def test_grid_value_two_is_not_normalized_to_boolean(self):
        data=self.fixture();offset=0x114D8
        encoded=b"\x02\x02\xFF\xFF"*4
        data[offset+0xCC]=7
        struct.pack_into(">I",data,offset+0x60D0,len(encoded))
        data[offset+0xCD:offset+0xCD+len(encoded)]=encoded
        with tempfile.TemporaryDirectory(prefix="tod-grid-value-") as folder:
            path=Path(folder)/"GAME.bin";path.write_bytes(data)
            observed=TOOL["inspect"](ELF,path)["save_observation"]["blocks"][0]
            self.assertFalse(observed["header_matches_selection"])
            self.assertEqual(observed["ready_byte"],7)
            self.assertEqual(observed["decoded"]["value_histogram"],{"2":0x40000})
            self.assertEqual(observed["decoded"]["clipped_run_bytes"],4)
            self.assertEqual(path.read_bytes(),data)

    def test_malformed_lengths_are_bounded_without_repair(self):
        data=self.fixture();offset=0x114D8
        data[offset+0xCC]=1
        with tempfile.TemporaryDirectory(prefix="tod-grid-length-") as folder:
            path=Path(folder)/"GAME.bin"
            for length in (0x6000,0xFFFFFFFF):
                struct.pack_into(">I",data,offset+0x60D0,length);path.write_bytes(data)
                observed=TOOL["inspect"](ELF,path)["save_observation"]["blocks"][0]
                self.assertIsNone(observed["decoded"])
                self.assertIn("cap",observed["status"])
                self.assertEqual(path.read_bytes(),data)

    def test_invalid_inputs_rejected(self):
        with tempfile.TemporaryDirectory(prefix="tod-grid-invalid-") as folder:
            path=Path(folder)/"input.bin"
            for data in (b"invalid",bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError,"plaintext"):
                    TOOL["inspect"](ELF,path)
            with self.assertRaisesRegex(ValueError,"size mismatch"):
                TOOL["inspect"](path)

    def test_actual_save_header_grid_and_flags_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual snapshot validation")
        before=[hashlib.sha256(p.read_bytes()).digest() for p in (ELF,SAVE)]
        blocks=TOOL["inspect"](ELF,SAVE)["save_observation"]["blocks"]
        self.assertEqual([b["slot"] for b in blocks if not b["ready_byte"]],[3,4])
        self.assertTrue(all(b["header_matches_selection"] for b in blocks if b["ready_byte"]))
        self.assertTrue(all(b["decoded"]["decoded_size"]==0x40000 for b in blocks if b["ready_byte"]))
        self.assertEqual(blocks[11]["decoded"]["value_histogram"]["2"],297)
        data=SAVE.read_bytes()
        for b in blocks:
            o=0x114D8+b["slot"]*0x60DC
            self.assertEqual([g["saved_flag"] for g in b["groups"]],list(data[o+0x60D4:o+0x60DB]))
        self.assertEqual(before,[hashlib.sha256(p.read_bytes()).digest() for p in (ELF,SAVE)])


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf",type=Path)
    parser.add_argument("--save",type=Path)
    options,remaining=parser.parse_known_args();ELF,SAVE=options.elf,options.save
    unittest.main(argv=[__file__]+remaining)
