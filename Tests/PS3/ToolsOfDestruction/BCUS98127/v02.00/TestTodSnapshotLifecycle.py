"""Exact snapshot staging and deferred restore admission; no native execution."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'Ratchet And Clank Save Editor.sln').is_file())
TOOL = runpy.run_path(str(ROOT / 'Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSnapshotLifecycle.py'))
ELF = SAVE = None


class SnapshotLifecycleChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest('Pass --elf for exact native evidence')
        return TOOL['inspect'](ELF)

    def test_map_reproduction(self):
        report = self.native()
        mapping = json.loads((ROOT / 'docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json').read_text(encoding='utf-8'))
        self.assertEqual(report, mapping['snapshot_lifecycle'])

    def test_native_guards_and_virtual_dispatch(self):
        report = self.native()
        elf = TOOL['BINDINGS'].Elf(ELF)
        for guard in report['instruction_guards']:
            self.assertEqual(elf.read(int(guard['va'], 0), len(bytes.fromhex(guard['bytes']))), bytes.fromhex(guard['bytes']))
        table = elf.u32(0x8A1904)
        self.assertEqual(elf.u32(elf.u32(table+0x10)), 0x35E710)
        self.assertEqual(elf.u32(elf.u32(table+0x14)), 0x35E508)
        # Independently decode launcher slot loads, bctrl and later import branches.
        for start, slot_load, dispatch, spawn in ((0x6952D8,0x6952F8,0x69530C,0x695334),
                                                  (0x695350,0x695370,0x695384,0x6953AC)):
            self.assertEqual(elf.u32(slot_load)&0xFFFF, 0x10)
            self.assertEqual(elf.u32(dispatch), 0x4E800421)
            self.assertEqual(TOOL['BINDINGS'].branch_target(elf.u32(spawn),spawn),0x83968C)
            self.assertLess(start,slot_load)
            self.assertLess(dispatch,spawn)
        self.assertEqual(len(report['threads']),5)

    def test_local_worker_publication_all_gate_combinations(self):
        for slot in (-1,0,1,-2,(1<<31)-1,-(1<<31)):
            for status in (0,1,0xFFFFFFFF,0x80000000):
                result = TOOL['load_worker_preview'](slot,status)
                passed = slot != -1 and status == 0
                self.assertEqual(result['phase_after'],5 if passed else 0)
                self.assertEqual(result['manager_event_after'],3 if passed else None)
                self.assertFalse(result['apply_called_here'])
                auto = TOOL['load_worker_preview'](slot,status,auto=True)
                self.assertEqual(auto['phase_after'],result['phase_after'])
                self.assertEqual(auto['manager_event_after'],4 if passed else None)

    def test_poll_handle_status_and_phase_are_independent(self):
        for handle in (0,1,0xFFFFFFFF,0xFFFFFFFFFFFFFFFF,0x100000001):
            for status in (0,0x80010005,0x80010004,0xFFFFFFFF):
                for phase in (0,1,3,4,5,255,0xFFFFFFFF):
                    result = TOOL['apply_poll_preview'](handle,status,phase)
                    completed = handle != 0xFFFFFFFF and status == 0x80010005
                    applies = completed and phase == 5
                    self.assertEqual(result['apply_dispatch'],applies)
                    self.assertEqual(result['handle_after'],0xFFFFFFFF if completed else handle)
                    self.assertEqual(result['phase_after'],0 if applies else phase)
                    self.assertEqual(result['ordering'],['apply callback','invalidate handle','clear phase'] if applies else ['invalidate handle'] if completed else [])
        # Native sentinel is zero-extendedFFFFFFFF, not the all-ones64 value.
        self.assertTrue(TOOL['apply_poll_preview'](0xFFFFFFFFFFFFFFFF,0x80010005,5)['apply_dispatch'])

    def test_first_matching_file_size_and_duplicate_rejection(self):
        preview = TOOL['metadata_admission_preview']
        size = 0x906F0
        self.assertTrue(preview([(False,0),(True,size)])['accepted'])
        self.assertEqual(preview([(False,size),(True,size)])['first_matching_index'],1)
        for wrong in (0,size-1,size+1,size+(1<<32),(1<<64)-1):
            result = preview([(True,wrong),(True,size)])
            self.assertFalse(result['accepted'])
            self.assertEqual(result['first_matching_index'],0)
            self.assertEqual(result['callback_result'],0xFFFFFFFD)
        self.assertFalse(preview([])['accepted'])
        self.assertFalse(preview([(False,size)])['accepted'])

    def test_detached_staging_retains_snapshot_after_live_mutations(self):
        live = bytearray(0x906F0)
        live[0x484:0x488] = b'ABCD'
        live[0x906E4:0x906E8] = b'TAIL'
        staged = TOOL['staged_copy_preview'](live)
        live[0x484:0x488] = b'EFGH'
        live[-1] = 255
        self.assertEqual(staged[0x484:0x488],b'ABCD')
        self.assertEqual(staged[0x906E4:0x906E8],b'TAIL')
        self.assertEqual(staged[-1],0)
        self.assertNotEqual(staged,live)
        self.assertIsInstance(staged,bytes)

    def test_restore_side_effect_order_and_probe_separation(self):
        report = self.native()
        steps = report['restore_effect_order']['steps']
        self.assertEqual([int(s['call_va'],0) for s in steps],[0x35E534,0x35E550,0x35E560,0x35E570,0x35E584])
        self.assertEqual([s['audio_bus'] for s in steps[1:4]],[1,12,6])
        self.assertEqual([int(s['save_offset'],0) for s in steps[1:4]],[0x114C8,0x114CC,0x114C4])
        elf = TOOL['BINDINGS'].Elf(ELF)
        self.assertEqual(elf.u32(0x6C7784)&0xFFFF,0x100)
        self.assertEqual(elf.u32(0x6C7788)&0xFFFF,0xFC)
        self.assertIn('rather than publishing phase5',report['check_probe']['rule'])
        self.assertIn('not proof',report['check_probe']['rule'])
        self.assertIn('ACTUAL auto-load',report['load_worker']['auto_rule'])
        self.assertIn('overlapping',report['snapshot_launch']['limits'])

    def test_rejects_implicit_or_out_of_bounds_preview_inputs(self):
        for value in (True,1.0,None,-1,1<<64):
            with self.assertRaises(ValueError):
                TOOL['apply_poll_preview'](value,0,0)
        for value in (True,-1,1<<32,1.0,None):
            with self.assertRaises(ValueError):
                TOOL['apply_poll_preview'](1,value,5)
            with self.assertRaises(ValueError):
                TOOL['apply_poll_preview'](1,0,value)
            with self.assertRaises(ValueError):
                TOOL['load_worker_preview'](0,value)
        for value in (True,None,1.0,1<<31,-(1<<31)-1):
            with self.assertRaises(ValueError):
                TOOL['load_worker_preview'](value,0)
        with self.assertRaises(ValueError):
            TOOL['load_worker_preview'](0,0,auto=1)
        for entries in (None,[(1,3)],[(True,-1)],[(True,1<<64)],[(False,3,4)],[(True,0)]*1025):
            with self.assertRaises(ValueError):
                TOOL['metadata_admission_preview'](entries)
        for data in (0x906F0,None,b'',bytes(0x906F1)):
            with self.assertRaises(ValueError):
                TOOL['staged_copy_preview'](data)

    def test_snapshot_observation_preserves_raw_bits_and_rejects_bad_layout(self):
        self.native()
        data = bytearray(0x906F0)
        for identifier in range(32):
            struct.pack_into('>I',data,identifier*20,identifier)
        for offset,bits in ((0x114C8,0x7FC12345),(0x114CC,0xFF800000),(0x114C4,0x80000000),(0x906E8,0xFFFFFFFF)):
            struct.pack_into('>I',data,offset,bits)
        with tempfile.TemporaryDirectory(prefix='tod-snapshot-lifecycle-') as directory:
            path = Path(directory)/'fixture.bin'
            path.write_bytes(data)
            observation = TOOL['inspect'](ELF,path)['save_observation']
            self.assertEqual([a['raw'] for a in observation['audio_float_bits']],['7FC12345','FF800000','80000000'])
            self.assertEqual(observation['saved_destination_raw'],'FFFFFFFF')
            self.assertEqual(path.read_bytes(),data)
            data[0] = 255
            path.write_bytes(data)
            with self.assertRaises(ValueError):
                TOOL['inspect'](ELF,path)
            path.write_bytes(b'bad')
            with self.assertRaises(ValueError):
                TOOL['inspect'](ELF,path)

    def test_actual_input_hashes_unchanged_and_no_runtime_state_inference(self):
        self.native()
        if SAVE is None:
            self.skipTest('Pass --save for actual detached snapshot')
        paths = (Path(ELF),Path(SAVE))
        hashes = [hashlib.sha256(p.read_bytes()).digest() for p in paths]
        observation = TOOL['inspect'](ELF,SAVE)['save_observation']
        self.assertEqual(observation['size'],'0x906f0')
        self.assertIn('no thread handle',observation['scope'])
        self.assertEqual(hashes,[hashlib.sha256(p.read_bytes()).digest() for p in paths])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf",type=Path)
    parser.add_argument("--save",type=Path)
    args,remaining = parser.parse_known_args()
    ELF,SAVE = args.elf,args.save
    unittest.main(argv=[__file__]+remaining)
