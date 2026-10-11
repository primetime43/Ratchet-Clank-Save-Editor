"""Exact native award evidence and bounded immutable producer branch models."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSkillAward.py"))
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I",data,i*20,i)
    return data


class SkillAwardChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build verification")
        return TOOL["inspect"](ELF)

    def test_reproduces_map(self):
        report = self.native()
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(report,mapping["skill_award"])

    def test_exact_guards_producer_thresholds_and_enum(self):
        report = self.native()
        self.assertEqual([x["enum"] for x in report["named_awards"]], ["SKILLPOINT_GOLDEN","SKILLPOINT_CHEAPSKATE","SKILLPOINT_HARDCORE"])
        self.assertEqual(report["cheapskate_producer"]["award_threshold"],1.0)
        self.assertIn("signed32 savedbolts",report["cheapskate_producer"]["producer_admission"])
        elf = TOOL["BINDINGS"].Elf(ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"],0),len(raw)),raw)

    def test_duplicate_does_not_fix_score_or_auto_hardcore(self):
        points = [10]*60
        before = (1<<59)-1
        result = TOOL["skill_preview"](123,before,1,points)
        self.assertEqual(result["bits"],before)
        self.assertEqual(result["score"],123)
        self.assertEqual(result["awarded_ids"],[])
        self.assertEqual(result["events"],[])
        self.assertEqual(points,[10]*60)

    def test_publication_order_wrap_unknown_bits_and_auto_hardcore(self):
        points = [1]*60
        points[59] = 10
        before = ((1<<59)-1) ^ (1<<47) | (0xA<<60)
        result = TOOL["skill_preview"](0xFFFFFFFF,before,47,points)
        self.assertEqual(result["score"],10)
        self.assertEqual(result["bits"],(0xA<<60)|(1<<60)-1)
        self.assertEqual(result["awarded_ids"],[47,59])
        self.assertEqual(result["events"],["bit:47","score:47","notification-omitted:47","bit:59","score:59","notification-omitted:59"])

    def test_direct_hardcore_is_not_all_skills_or_score_repair(self):
        result = TOOL["skill_preview"](99,0,59,[2]*60)
        self.assertEqual(result["bits"],1<<59)
        self.assertEqual(result["score"],101)
        self.assertEqual(result["awarded_ids"],[59])

    def test_duplicate_and_invalid_local_collectible_still_scan(self):
        masks,totals = [1]*19,[1]*19
        before = list(masks)
        for identifier in (0,32,0xFFFFFFFF):
            result = TOOL["collectible_preview"](masks,totals,0,identifier)
            self.assertFalse(result["mask_changed"])
            self.assertTrue(result["completion_scan_ran"])
            self.assertTrue(result["skill46_call_requested"])
        self.assertEqual(masks,before)

    def test_collectible_ge_popcount_not_shipped_identity(self):
        result = TOOL["collectible_preview"]([0]*19,[0]*18+[1],18,31)
        self.assertTrue(result["skill46_call_requested"])
        self.assertEqual(result["masks"][18],0x80000000)
        result = TOOL["collectible_preview"]([0xFFFFFFFF]*19,[1]*19,0,31)
        self.assertTrue(result["skill46_call_requested"])
        self.assertEqual(result["counts"],[32]*19)

    def test_original_request_vs_selected_quantity(self):
        quantity = TOOL["quantity_selection_preview"]
        gate = TOOL["ammo_award_gate_preview"]
        self.assertEqual(quantity(2.0,1),1.0)
        self.assertFalse(gate(1,2.0,True,0,0,2,0)["skill47_call_requested"])
        for request in (0.0,-1.0):
            self.assertEqual(quantity(request,100),100.0)
            self.assertTrue(gate(1,request,True,0,0,2,0)["skill47_call_requested"])
        self.assertTrue(gate(1,1.0,True,0,0,2,0)["skill47_call_requested"])
        self.assertFalse(gate(2,1.0,True,0,0,2,0)["skill47_call_requested"])
        self.assertFalse(gate(1,float("nan"),True,0,0,2,0)["skill47_call_requested"])

    def test_signed_currency_ownership_definition_and_hero_gates(self):
        gate = TOOL["ammo_award_gate_preview"]
        self.assertFalse(gate(1,1.0,True,1,0xFFFFFFFF,1,0)["producer_admitted"])
        self.assertTrue(gate(1,1.0,True,0xFFFFFFFF,0,1,0)["producer_admitted"])
        for args in ((1,1.0,False,0,0,1,0),(1,1.0,True,0,0,0,0),(1,1.0,True,0,0,1,1),(1,1.0,True,0,0,1,2)):
            self.assertFalse(gate(*args)["producer_admitted"])
        self.assertTrue(gate(1,1.0,True,0,0,255,4)["skill47_call_requested"])

    def test_rejects_unbounded_inputs(self):
        for invalid in (None, 1, "wrong", {}):
            with self.assertRaises(ValueError):
                TOOL["skill_preview"](0,0,1,invalid)
            with self.assertRaises(ValueError):
                TOOL["collectible_preview"](invalid,[0]*19,0,0)
            with self.assertRaises(ValueError):
                TOOL["collectible_preview"]([0]*19,invalid,0,0)
        for identifier in (-1,60,True):
            with self.assertRaises(ValueError):
                TOOL["skill_preview"](0,0,identifier,[1]*60)
        for world in (-1,19,True):
            with self.assertRaises(ValueError):
                TOOL["collectible_preview"]([0]*19,[0]*19,world,0)
        for request in (float("nan"),float("inf"),True):
            with self.assertRaises(ValueError):
                TOOL["quantity_selection_preview"](request,1)
        with self.assertRaises(ValueError):
            TOOL["ammo_award_gate_preview"](32,1.0,True,0,0,1,0)

    def test_raw_snapshot_mismatch_and_originals_unchanged(self):
        self.native()
        data = fixture()
        struct.pack_into(">I",data,0x8708,0xDEADBEEF)
        struct.pack_into(">Q",data,0x8710,0xF000000000000000)
        struct.pack_into(">I",data,0x41C,0xFFFFFFFF)
        struct.pack_into(">I",data,0x1C,0x7FC01234)
        data[0x24] = 255
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"synthetic.bin"
            path.write_bytes(data)
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            report = TOOL["inspect"](ELF,path)
            observation = report["save_observation"]
            self.assertEqual(observation["score_raw"],0xDEADBEEF)
            self.assertEqual(observation["bits_hex"],"F000000000000000")
            self.assertEqual(observation["bolts_signed_for_purchase_comparison"],-1)
            self.assertEqual(observation["combuster_ammo_bits_hex"],"7FC01234")
            self.assertEqual(observation["combuster_ownership_raw"],255)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
            path.write_bytes(b"too short")
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF,path)

    def test_actual_save_observation_immutable(self):
        if ELF is None or SAVE is None:
            self.skipTest("Pass --elf and --save for detached actual observations")
        elf_hash = hashlib.sha256(ELF.read_bytes()).hexdigest()
        data = SAVE.read_bytes()
        report = TOOL["inspect"](ELF,SAVE)
        actual = report["save_observation"]
        self.assertEqual(actual["plaintext_sha256"],hashlib.sha256(data).hexdigest().upper())
        self.assertEqual(actual["score_raw"],struct.unpack_from(">I",data,0x8708)[0])
        self.assertEqual(SAVE.read_bytes(),data)
        self.assertEqual(hashlib.sha256(ELF.read_bytes()).hexdigest(),elf_hash)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf",type=Path)
    parser.add_argument("--save",type=Path)
    args,remaining = parser.parse_known_args()
    ELF,SAVE = args.elf,args.save
    unittest.main(argv=[__file__]+remaining)
