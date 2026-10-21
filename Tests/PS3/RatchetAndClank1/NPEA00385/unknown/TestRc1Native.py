"""Reproduce the RC1 native map and reject unrelated/corrupt executable inputs."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[5]
TOOL = ROOT / 'Tools/PS3/RatchetAndClank1/NPEA00385/unknown/Inspect-Rc1Native.py'
spec = importlib.util.spec_from_file_location('rc1_native', TOOL)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
ELF = None


class NativeChecks(unittest.TestCase):
    def test_map_reproduces(self):
        expected = json.loads((ROOT / 'docs/PS3/RatchetAndClank1/NPEA00385/unknown/maps/NativeMap.json').read_text(encoding='utf-8'))
        self.assertEqual(expected, native.inspect(ELF))

    def test_native_layout_and_limits(self):
        report = native.inspect(ELF)
        records = {item['id']: item for item in report['player_records']}
        self.assertEqual(48, len(records))
        self.assertEqual((0x24, 4), (records[1]['offset'], records[1]['length']))
        self.assertEqual((0x11C, 148), (records[9]['offset'], records[9]['length']))
        self.assertEqual((0x1B8, 37), (records[10]['offset'], records[10]['length']))
        self.assertEqual((0x1E8, 37), (records[11]['offset'], records[11]['length']))
        self.assertEqual({10: 40, 11: 20, 13: 20, 15: 200, 16: 240, 17: 50,
                          19: 240, 20: 10, 23: 50, 24: 10, 25: 20},
                         {item['id']: item['maximum'] for item in report['ammo']})

    def test_wrong_and_corrupted_binaries_fail(self):
        original = ELF.read_bytes()
        with tempfile.TemporaryDirectory(prefix='rc1-native-check-') as directory:
            target = Path(directory) / 'candidate.elf'
            target.write_bytes(b'\x7fELF')
            with self.assertRaises(ValueError):
                native.inspect(target)
            modified = bytearray(original)
            modified[0xAA2E8 - 0x10000] ^= 1
            target.write_bytes(modified)
            with self.assertRaises(ValueError):
                native.inspect(target)
        self.assertEqual(original, ELF.read_bytes())

    def test_grant_allowlist_and_initial_ammo(self):
        report = native.inspect(ELF)
        weapons = {item['id']: item for item in report['weapons']}
        self.assertEqual({10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 24, 25},
                         {key for key, value in weapons.items() if value['grant_supported']})
        self.assertEqual({10: 10, 11: 10, 13: 10, 14: 0, 15: 100, 16: 120,
                          17: 25, 18: 0, 19: 120, 20: 3, 24: 3, 25: 10},
                         {key: value['initial_ammo'] for key, value in weapons.items() if value['grant_supported']})
        for weapon in weapons.values():
            self.assertEqual(0, weapon['item_type'])
            self.assertEqual(0x1B8 + weapon['id'], weapon['ownership_offset'])
            self.assertEqual(0x1E8 + weapon['id'], weapon['acquisition_flag_offset'])
        self.assertEqual(0x218, report['grant_layout']['acquisition_offset'])
        self.assertEqual(0x22C, report['grant_layout']['quick_offset'])
        self.assertEqual(8, report['grant_layout']['quick_slots'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', required=True, type=Path)
    args, remaining = parser.parse_known_args()
    ELF = args.elf
    unittest.main(argv=[__file__, *remaining])
