"""Exact load-selection provenance and safe detached branch previews."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'Ratchet And Clank Save Editor.sln').is_file())
TOOL = runpy.run_path(str(ROOT / 'Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodLoadSelection.py'))
ELF = SAVE = None


class LoadSelectionChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest('Pass --elf for native evidence')
        return TOOL['inspect'](ELF)

    def test_map_reproduction(self):
        report = self.native()
        mapping = json.loads((ROOT / 'docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json').read_text(encoding='utf-8'))
        if 'load_selection' not in mapping:
            self.skipTest('Parent integration pending')
        self.assertEqual(report, mapping['load_selection'])

    def test_native_guards_and_store_order(self):
        report = self.native()
        elf = TOOL['BINDINGS'].Elf(ELF)
        for guard in report['instruction_guards']:
            expected = bytes.fromhex(guard['bytes'])
            self.assertEqual(elf.read(int(guard['va'], 0), len(expected)), expected)
        self.assertEqual(TOOL['BINDINGS'].branch_target(elf.u32(0x2D172C-16),0x2D172C-16), 0x48B490)
        self.assertEqual(elf.u32(0x2D1834), 0x90A906E8)
        self.assertEqual(elf.u32(0x2D1844), 0x909F0000)
        self.assertIn('finally clears', report['pending_consumer']['rule'])
        self.assertEqual(len(report['lookup']['catalog']), 19)
        self.assertIn('WITHOUT', report['lookup']['rule'])
        self.assertIn('does not establish sentinel', report['pending_consumer']['limits'])

    def test_early_return_precedes_every_runtime_gate(self):
        for mode in (0,4,-1,2**31-1):
            for qualifier in (False,True):
                result = TOOL['transition_preview'](3,3,runtime_mode=mode,qualifier=qualifier)
                self.assertEqual(result['branch'],'same-destination early return')
                self.assertEqual(result['saved_id_after'],3)
                self.assertFalse(result['request_dispatched'])
                self.assertIsNone(result['queued_id'])

    def test_deferred_request_is_not_saved_next_level(self):
        for saved_id in range(19):
            requested = (saved_id+1)%19
            result = TOOL['transition_preview'](saved_id,requested,runtime_mode=4)
            self.assertEqual(result['saved_id_after'],saved_id)
            self.assertEqual(result['queued_id'],requested)
            self.assertFalse(result['request_dispatched'])
        result = TOOL['transition_preview'](0,0,force=True,runtime_mode=4)
        self.assertEqual(result['branch'],'deferred runtime request')
        # Force bypasses equality, not the deferral gate.
        self.assertEqual(result['queued_id'],0)

    def test_qualifier_and_explicit_bypass_choose_request_not_success(self):
        for qualifier,bypass,branch in ((True,False,'qualified request'),(False,True,'ordinary request')):
            result = TOOL['transition_preview'](0,18,runtime_mode=4,qualifier=qualifier,bypass_defer=bypass)
            self.assertEqual(result['branch'],branch)
            self.assertEqual(result['saved_id_after'],18)
            self.assertTrue(result['request_dispatched'])
            self.assertIsNone(result['queued_id'])

    def test_preview_rejects_unknown_ids_and_implicit_gate_values(self):
        for value in (-1,19,0xFFFFFFFF,True,1.0,None):
            with self.assertRaises(ValueError):
                TOOL['transition_preview'](value,0)
            with self.assertRaises(ValueError):
                TOOL['transition_preview'](0,value)
        for name,value in (('force',1),('bypass_defer',None),('qualifier',255),('runtime_mode',True),('runtime_mode',1<<31)):
            with self.assertRaises(ValueError):
                TOOL['transition_preview'](0,1,**{name:value})

    def test_extreme_saved_words_are_observed_without_preview_or_mutation(self):
        self.native()
        data = bytearray(0x906F0)
        for identifier in range(32):
            struct.pack_into('>I',data,identifier*20,identifier)
        struct.pack_into('>I',data,0x906E8,0x80000000)
        struct.pack_into('>I',data,0x8740,0xFFFFFFFF)
        with tempfile.TemporaryDirectory(prefix='tod-load-selection-') as directory:
            path = Path(directory)/'fixture.bin'
            path.write_bytes(data)
            report = TOOL['inspect'](ELF,path)['save_observation']
            self.assertEqual(report['load_destination_raw'],'80000000')
            self.assertEqual(report['next_level_selection_raw'],'FFFFFFFF')
            self.assertEqual(path.read_bytes(),data)
            path.write_bytes(bytes(20))
            with self.assertRaises(ValueError):
                TOOL['inspect'](ELF,path)

    def test_actual_inputs_unchanged_and_runtime_not_inferred(self):
        self.native()
        if SAVE is None:
            self.skipTest('Pass --save for detached actual snapshot')
        before = {p:hashlib.sha256(p.read_bytes()).digest() for p in (ELF,SAVE)}
        observation = TOOL['inspect'](ELF,SAVE)['save_observation']
        self.assertEqual(observation['load_destination_raw'],'00000000')
        self.assertEqual(observation['next_level_selection_raw'],'FFFFFFFF')
        self.assertIn('no pending queue',observation['scope'])
        for path,digest in before.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),digest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf",type=Path)
    parser.add_argument("--save",type=Path)
    args,remaining = parser.parse_known_args()
    ELF,SAVE = args.elf,args.save
    unittest.main(argv=[__file__,*remaining])
