"""Inventory lifecycle evidence, detached slot models and immutable snapshot checks."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("inventory_aux", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodInventoryAux.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i*0x14, i)
    struct.pack_into(">32i", data, 0x284, *([-1]*32))
    return data


class InventoryAuxChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")
        return TOOL.inspect(ELF)

    def test_reproduces_map(self):
        report = self.native()
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["inventory_aux"])

    def test_copy_order_mask_and_restore_assignments(self):
        report = self.native()
        restart = report["restart_lifecycle"]
        self.assertEqual(restart["first_copy_size"], "0x484")
        self.assertEqual(restart["object_arrays"]["preserve_mask"], "0xbff")
        self.assertEqual(restart["object_arrays"]["preserved_ids"], list(range(10))+[11])
        self.assertEqual(restart["object_arrays"]["cleared_ids"], [10]+list(range(12,23)))
        self.assertEqual(restart["quick_select"]["scan_words"], 32)
        self.assertEqual(restart["quick_select"]["reset_item_ids"], [24,26,27,28,29,30,31])
        self.assertEqual([a["id"] for a in report["hero_restore_assignments"]["assignments"]], [0,1,2,3,4,9])
        self.assertIn("leaves positive additions unchanged", report["hero_restore_assignments"]["rule"])
        elf = TOOL.PROGRESSION.BINDINGS.Elf(ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"],0),len(raw)),raw)

    def test_quick_select_duplicate_removal_replacement_and_no_compaction(self):
        words = [-1]*32
        words[0],words[7],words[24],words[31] = 5,6,6,6
        before = list(words)
        automatic = TOOL.quick_select_preview(words,6)
        self.assertEqual(automatic["operation"],"already-present")
        self.assertEqual(automatic["words"],words)
        explicit = TOOL.quick_select_preview(words,6,0)
        self.assertEqual(explicit["selected_slot"],0)
        self.assertEqual(explicit["removed_slots"],[7,24,31])
        self.assertEqual(explicit["displaced_item"],5)
        self.assertEqual([i for i,v in enumerate(explicit["words"]) if v==6],[0])
        self.assertEqual(words,before)
        self.assertEqual(explicit["words"][7],-1)
        self.assertEqual(explicit["words"][24],-1)

    def test_quick_select_capacity_slot_fallback_and_definition_filter(self):
        full = list(range(24))+[-1]*8
        self.assertEqual(TOOL.quick_select_preview(full,31)["operation"],"first24-full")
        # Physical tail membership prevents automatic insertion into an empty front.
        tail = [-1]*32
        tail[31] = 12
        self.assertEqual(TOOL.quick_select_preview(tail,12,24)["operation"],"already-present")
        fallback = TOOL.quick_select_preview([-1]*32,12,31)
        self.assertEqual(fallback["selected_slot"],0)
        for mask in (0x40,0x1000,0x1040):
            self.assertEqual(TOOL.quick_select_preview([-1]*32,12,0,mask)["operation"],"definition-filtered")
        for words,item,slot,flags in [([-1]*31,1,-1,0),([-1]*32,-2,-1,0),([-1]*32,32,-1,0),([-1]*32,1,2**31,0),([-1]*32,1,-1,-1)]:
            with self.assertRaises(ValueError):
                TOOL.quick_select_preview(words,item,slot,flags)

    def test_souls_signed_condition_and_independent_award_state(self):
        report = self.native()
        award = report["souls_award_consumer"]
        self.assertEqual((award["skill_id"],award["skill_enum"]),(52,"SKILLPOINT_SOULS"))
        self.assertEqual(award["additions_getter_va"],"0x23d920")
        self.assertFalse(TOOL.souls_condition_preview(0,25))
        self.assertTrue(TOOL.souls_condition_preview(0,26))
        self.assertFalse(TOOL.souls_condition_preview(1,26))
        self.assertFalse(TOOL.souls_condition_preview(0,0xFFFFFFFF))
        self.assertFalse(TOOL.souls_condition_preview(0,0x80000000))
        with self.assertRaises(ValueError):
            TOOL.souls_condition_preview(-1,26)

    def test_snapshot_raw_unknown_words_and_no_automatic_fixups(self):
        self.native()
        data = fixture()
        struct.pack_into(">i",data,0x284+31*4,-2)
        struct.pack_into(">I",data,0x344,0xFFFFFFFF)
        struct.pack_into(">I",data,0x3A0,0x80000000)
        struct.pack_into(">I",data,0x3FC,0xFFFFFFFF)
        struct.pack_into(">Q",data,0x8710,1<<52)
        with tempfile.TemporaryDirectory(prefix="tod-inventory-aux-") as folder:
            path=Path(folder)/"snapshot.bin"
            path.write_bytes(data)
            observed=TOOL.inspect(ELF,path)["save_observation"]
            self.assertEqual(observed["quick_select"][31],-2)
            row=observed["object_counters"][16]
            self.assertEqual((row["current"],row["peak"],row["positive_additions_raw"]),(-1,0x80000000,0xFFFFFFFF))
            self.assertEqual(observed["souls"]["signed_additions"],-1)
            self.assertFalse(observed["souls"]["saved_comparisons_satisfied"])
            self.assertTrue(observed["souls"]["skill52_already_set"])
            self.assertEqual(path.read_bytes(),data)

    def test_rejects_bad_inputs(self):
        self.native()
        with tempfile.TemporaryDirectory(prefix="tod-inventory-aux-invalid-") as folder:
            path=Path(folder)/"snapshot.bin"
            for data in (b"invalid",bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError,"plaintext"):
                    TOOL.inspect(ELF,path)
            with self.assertRaisesRegex(ValueError,"size mismatch"):
                TOOL.inspect(path)

    def test_actual_snapshot_and_originals_unchanged(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save for actual snapshot")
        before=[hashlib.sha256(p.read_bytes()).digest() for p in (ELF,SAVE)]
        observed=TOOL.inspect(ELF,SAVE)["save_observation"]
        self.assertEqual(observed["quick_select"],[-1]*32)
        for i in (0,1,2,3,4,9):
            row=observed["object_counters"][i]
            self.assertEqual((row["current"],row["peak"],row["positive_additions_raw"]),(1,1,0))
        self.assertEqual(observed["souls"]["current_raw_hex"],"00000000")
        self.assertEqual(observed["souls"]["additions_raw_hex"],"00000000")
        self.assertFalse(observed["souls"]["saved_comparisons_satisfied"])
        self.assertTrue(observed["souls"]["skill52_already_set"])
        self.assertEqual(before,[hashlib.sha256(p.read_bytes()).digest() for p in (ELF,SAVE)])


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf",type=Path)
    parser.add_argument("--save",type=Path)
    args,remaining=parser.parse_known_args()
    ELF,SAVE=args.elf,args.save
    unittest.main(argv=[__file__]+remaining)
