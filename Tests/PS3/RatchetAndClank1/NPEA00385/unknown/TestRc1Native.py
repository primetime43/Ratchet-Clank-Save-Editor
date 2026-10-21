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
ARCHIVE = None


class NativeChecks(unittest.TestCase):
    def test_world_gold_bolt_map_and_exact_pickup_store(self):
        gold = native.inspect(ELF)['gold_bolts']
        self.assertEqual((0x1544, 0x82A4, 20, 3003, 0x8024),
                         (gold['world_start'], gold['world_stride'], gold['world_count'], gold['record_id'], gold['flag_offset']))
        self.assertEqual(11, len(gold['world_records']))
        self.assertEqual(40, len(gold['fields']))
        self.assertEqual(40, sum(gold['counts']))
        for field in gold['fields']:
            self.assertIn(field['world'], range(1, 19))
            self.assertLess(field['slot'], gold['counts'][field['world']])
            self.assertEqual(0x1544 + field['world'] * 0x82A4 + 0x8024 + field['slot'], field['offset'])
        self.assertEqual(11, gold['pickup_store']['instruction_count'])
        raw = ELF.read_bytes()
        for address in (0x73860C, 0x1DA138, 0x7269C4):
            def changed(current, length):
                result = bytearray(raw[current - 0x10000:current - 0x10000 + length])
                if current <= address < current + length:
                    result[address - current] ^= 1
                return bytes(result)
            with self.subTest(address=hex(address)), self.assertRaises(ValueError):
                native.extract_gold_bolts(changed)

    def test_gold_pickup_asset_reader_rejects_bad_pvars_and_slot_ids(self):
        import struct
        tool = TOOL.with_name('Inspect-Rc1GoldPickups.py')
        spec = importlib.util.spec_from_file_location('gold_assets_test', tool)
        assets = importlib.util.module_from_spec(spec); spec.loader.exec_module(assets)
        data = bytearray(0x400)
        for offset, value in ((0x44, 0x100), (0x54, 0x200), (0x58, 0x220), (0x100, 1),
                              (0x128, 1134), (0x168, 0), (0x200, 0), (0x204, 0x80), (0x220, 3)):
            struct.pack_into('>I', data, offset, value)
        self.assertEqual([3], assets.slots(data))
        for offset, value in ((0x220, 4), (0x168, 0xFFFFFFFF), (0x204, 4), (0x100, 0xFFFFFF)):
            broken = bytearray(data); struct.pack_into('>I', broken, offset, value)
            with self.subTest(offset=hex(offset)), self.assertRaises(ValueError): assets.slots(broken)

    def test_reference_gold_pickups_match_all_native_slots(self):
        if ARCHIVE is None:
            self.skipTest('Pass --archive to verify all nineteen local PAL gameplay assets')
        tool = TOOL.with_name('Inspect-Rc1GoldPickups.py')
        spec = importlib.util.spec_from_file_location('gold_assets_reference', tool)
        assets = importlib.util.module_from_spec(spec); spec.loader.exec_module(assets)
        report = assets.inspect(ARCHIVE, ELF)
        self.assertEqual(40, report['total'])
        self.assertEqual(19, len(report['worlds']))
        self.assertEqual('45375F8EF6150FDECE8680102D2E2A6B6CC5C289F24630AD9F812389A811616C', report['archive']['sha256'])

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
        self.assertEqual({9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 23, 24, 25},
                         {key for key, value in weapons.items() if value['grant_supported']})
        self.assertEqual({9: 0, 10: 10, 11: 10, 13: 10, 14: 0, 15: 100, 16: 120,
                          17: 25, 18: 0, 19: 120, 20: 3, 21: 0, 23: 25, 24: 3, 25: 10},
                         {key: value['initial_ammo'] for key, value in weapons.items() if value['grant_supported']})
        for weapon in weapons.values():
            self.assertEqual(0, weapon['item_type'])
            self.assertEqual(0x1B8 + weapon['id'], weapon['ownership_offset'])
            self.assertEqual(0x1E8 + weapon['id'], weapon['acquisition_flag_offset'])
        self.assertEqual(0x218, report['grant_layout']['acquisition_offset'])
        self.assertEqual(0x22C, report['grant_layout']['quick_offset'])
        self.assertEqual(8, report['grant_layout']['quick_slots'])

    def test_notification_memory_effects(self):
        report = native.inspect(ELF)
        audit = report['notification']
        self.assertEqual(35, audit['instruction_count'])
        self.assertEqual(14, audit['vector_register_operations'])
        self.assertEqual(['0x112e10', '0x71f410', '0x112e14'],
                         [load['effective_address'] for load in audit['vector_loads']])
        self.assertEqual(['0x7b740', '0x5cc8d8'], [call['target'] for call in audit['calls']])
        self.assertEqual('0xa15c8c', audit['calls'][1]['destination'])
        self.assertEqual([dict(address='0x112f2c', destination='0xa15c80', bytes=4)], audit['direct_stores'])
        self.assertFalse(audit['serialized_destination_overlap'])
        weapons = {weapon['id']: weapon for weapon in report['weapons']}
        self.assertEqual({9: [4007, 21471], 21: [14002, 14002], 23: [5014, 21474]},
                         {item_id: weapons[item_id]['notification_ids'] for item_id in (9, 21, 23)})
        self.assertTrue(all(not weapons[item_id]['acquisition_list'] for item_id in (9, 21, 23)))

    def test_gold_upgrade_vendor_limits_and_serialization(self):
        report = native.inspect(ELF)
        gold = report['gold_upgrades']
        self.assertEqual((30, '0x969ca8', 0x11D8, 40),
                         (gold['record_id'], gold['runtime_address'], gold['offset'], gold['bytes']))
        self.assertEqual([19, 10, 11, 16, 17, 15, 21, 20, 25, 9], gold['vendor_ids'])
        self.assertEqual({9, 10, 11, 15, 16, 17, 19, 20, 21, 25}, {item['id'] for item in gold['weapons']})
        for item in gold['weapons']:
            self.assertEqual(0x11D8 + item['id'], item['offset'])
            self.assertEqual(0x1B8 + item['id'], item['ownership_offset'])
            self.assertEqual(1, item['maximum'])

    def test_gold_extractor_rejects_disagreeing_vendor_or_limit_tables(self):
        report = native.inspect(ELF)
        raw = ELF.read_bytes()
        records = {item['id']: item for item in report['player_records']}
        for address in (0x811CB0, 0x721008 + 10 * 76 + 54):
            def modified(current, length):
                result = bytearray(raw[current - 0x10000:current - 0x10000 + length])
                if current <= address < current + length:
                    result[address - current] ^= 1
                return bytes(result)
            with self.subTest(address=hex(address)), self.assertRaises(ValueError):
                native.extract_gold_upgrades(modified, records, report['weapons'])

    def test_notification_audit_rejects_untraced_effects_and_saved_overlap(self):
        raw = ELF.read_bytes()
        def read(address, length):
            return raw[address - 0x10000:address - 0x10000 + length]
        native.audit_notification(read, [])
        for address, word in ((0x112EA8, 0x98000000),  # unexpected byte store
                              (0x112F04, 0x48000005),  # different call target
                              (0x112ED8, 0x3C800096)):  # changed string destination
            def modified(current, length):
                data = bytearray(read(current, length))
                if current <= address < current + length:
                    data[address - current:address - current + 4] = word.to_bytes(4, 'big')
                return bytes(data)
            with self.subTest(address=hex(address)), self.assertRaises(ValueError):
                native.audit_notification(modified, [])
        for destination in (0xA15C80, 0xA15C8C):
            with self.subTest(saved_overlap=hex(destination)), self.assertRaises(ValueError):
                native.audit_notification(read, [(destination, 4)])

    def test_gadget_paths_and_flags(self):
        gadgets = {item['id']: item for item in native.inspect(ELF)['gadgets']}
        self.assertEqual({12, 22, 26, 27, 31, 32, 33, 34, 35}, set(gadgets))
        self.assertEqual({12, 22, 26, 27, 31, 32}, {key for key, value in gadgets.items() if value['quick_select']})
        for key, item in gadgets.items():
            self.assertEqual(0x1B8 + key, item['ownership_offset'])
            self.assertEqual(0x1E8 + key, item['acquisition_flag_offset'])
            self.assertEqual(4 if key in (33, 34) else 5 if key == 35 else 0, item['item_type'])
            self.assertFalse(item['acquisition_list'])
            self.assertFalse(item['initializes_ammo'])
        self.assertEqual([14003, 21469], gadgets[32]['notification_ids'])
        self.assertEqual([16005, 21468], gadgets[33]['notification_ids'])

    def test_gadget_extractor_rejects_unknown_grant_paths(self):
        report, raw = native.inspect(ELF), ELF.read_bytes()
        records = {item['id']: item for item in report['player_records']}
        for address, changed in ((0x721008 + 12 * 76, (2).to_bytes(4, 'big')),
                                 (0x737D30 + 12 * 24 + 8, b'\x00\x01'),
                                 (0x737D30 + 33 * 24 + 14, b'\x00\x01'),
                                 (0x737D30 + 35 * 24 + 18, b'\x00\x01'),
                                 (0x737BF0, (12).to_bytes(4, 'big'))):
            def modified(current, length):
                result = bytearray(raw[current - 0x10000:current - 0x10000 + length])
                for index in range(length):
                    if address <= current + index < address + len(changed):
                        result[index] = changed[current + index - address]
                return bytes(result)
            with self.subTest(address=hex(address)), self.assertRaises(ValueError):
                native.extract_gadgets(modified, records)

    def test_equipment_paths_and_flags_preserve_selection(self):
        report = native.inspect(ELF)
        equipment = {item['id']: item for item in report['equipment']}
        self.assertEqual({2, 3, 4, 5, 6, 7, 28, 29, 30}, set(equipment))
        for key, item in equipment.items():
            self.assertEqual(0x1B8 + key, item['ownership_offset'])
            self.assertEqual(0x1E8 + key, item['acquisition_flag_offset'])
            self.assertEqual(3 if key in (2, 3, 4) else 2 if key in (5, 6, 7) else 1, item['item_type'])
            for field in ('quick_select', 'acquisition_list', 'initializes_ammo', 'editor_requests_equip'):
                self.assertFalse(item[field])
        records = {item['id']: item for item in report['player_records']}
        self.assertEqual((0x1214, 28), (records[32]['offset'], records[32]['length']))
        self.assertEqual((0x1184, 4), (records[23]['offset'], records[23]['length']))

    def test_equipment_extractor_rejects_changed_native_paths(self):
        report, raw = native.inspect(ELF), ELF.read_bytes()
        records = {item['id']: item for item in report['player_records']}
        for address, changed in ((0x721008 + 2 * 76, (0).to_bytes(4, 'big')),
                                 (0x737D30 + 6 * 24 + 8, b'\x00\x01'),
                                 (0x737D30 + 28 * 24 + 14, b'\x00\x01'),
                                 (0x737D30 + 30 * 24 + 18, b'\x00\x01'),
                                 (0x737BF0, (29).to_bytes(4, 'big'))):
            def modified(current, length):
                result = bytearray(raw[current - 0x10000:current - 0x10000 + length])
                for index in range(length):
                    if address <= current + index < address + len(changed):
                        result[index] = changed[current + index - address]
                return bytes(result)
            with self.subTest(address=hex(address)), self.assertRaises(ValueError):
                native.extract_equipment(modified, records)
        changed_records = {key: dict(value) for key, value in records.items()}
        changed_records[32]['length'] = 24
        with self.assertRaises(ValueError):
            native.extract_equipment(lambda address, length: raw[address - 0x10000:address - 0x10000 + length], changed_records)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', required=True, type=Path)
    parser.add_argument('--archive', type=Path)
    args, remaining = parser.parse_known_args()
    ELF = args.elf
    ARCHIVE = args.archive
    unittest.main(argv=[__file__, *remaining])
