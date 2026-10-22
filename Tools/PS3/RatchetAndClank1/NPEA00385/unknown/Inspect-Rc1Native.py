"""Inspect the supplied European trilogy RC1 ELF without executing game code.

Checks exact binary identity and bounded native function fingerprints, extracts
record/item definitions and audits notification memory effects. JSON goes to stdout.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

ELF_SHA256 = "CCE4E741C395518DC4374CF87A7A81E6975F573F99CAD8AC2B6B3EAAFA4BAE9A"
ELF_SIZE = 9437216
FUNCTIONS = {
    "load_block": (0xE6CD8, 0x30C, "CAFFBD339D1B49E440578B01A0F732D5E3B1EEFDE64B3E7A895A22E951281715"),
    "load_save": (0xE6FE4, 0x170, "F4CB31B962D01F429E78D94106F7C509DE065F92476B8A37B8F75148433C3511"),
    "write_block": (0xE784C, 0x138, "94E6EF41E04B1624ADED0C6F1FDAC4DACADE5E0EB29E74075DB3572CDDB08A21"),
    "write_save": (0xE7984, 0x134, "2316686251A900E645619CA465A88D7FDB226B4F96E363A12D85AD8F32102580"),
    "read_ammo": (0x8E0F4, 0x7C, "888203AF45378B141BB5A6A01E49DADC3041A162FA206D9DC465244A58E1FD68"),
    "spend_ammo": (0xAA258, 0x90, "2E6B91C89D52A6BCA99E27BD53B2248CC0C736AC08D99253A3CB11E6A9AC3458"),
    "add_ammo": (0xAA2E8, 0x80, "322BB4720233042AC29968D976B77A1BC8B637CCC58D9DB35E12C373209B9F30"),
    "has_item": (0xEB0F4, 0x24, "A8B5398F4CFA5CDC350BB0FB2048DCD8A0F61714AB4F982B0B924DD0960FDCC1"),
    "grant_item": (0x112E18, 0x390, "77E44E39B9BE1200193822E81454626F2A7A61D5D4E825F4CE3F4EEA3B99EF22"),
    "vendor_purchase": (0x16CC50, 0xE38, "E3B544F3D6134838A000BC21E38A1016023C5B0403EAA9F75ABFB3001996051F"),
    "assign_quick_select": (0x143980, 0x2B0, "F5102C83624F7FEB021752811C446C412CBF0DDC54047DBFB1D31B904C227B08"),
    "load_quick_select": (0x143C30, 0x8C, "B6F5C3069DB87AA29FFCFF4E6956E50E8C1FA73BD5A01FAA5FCE18A52E420432"),
    "store_quick_select": (0x143CBC, 0x40, "E7FE7EDA407550382F9A5AC6966DF64A47093D33E40EB89ED8C9DAD91A010D6D"),
    "notification_text_lookup": (0x7B740, 0x98, "89E8D93A3EA42FAC22010C6D94E5FA18849292DC5914139D9E20CD2982019204"),
    "notification_text_copy": (0x5CC8D8, 0xEC, "23752406F48D66B6340793A5E7E880F1E0C6DDDAC958F42F9F66CAF2FD6A5258"),
    "gold_vendor_purchase": (0x339B70, 0x244, "EA95CCCC67869BC8A2491C9543A2E0341091E176099B5C3ACA47796CCEE42C11"),
    "count_gold_upgrades": (0x11B124, 0x90, "F30D20B411342EE68BCDE1405AA4990CB93D3D81A8AA184727C37C6FD459DD91"),
    "available_gold_bolts": (0x11B2C4, 0x1D0, "4B2964778705D724CEB0C9B8E96765C1C59D8ACA3AD8A02D3CC1985EEB33EDF2"),
    "gold_inventory_icons": (0x14B214, 0x118, "5AF4BDA9881284C8942A72535847CC8A181CF9D0447BF9389D303772E546DCD2"),
    "metal_detector_update": (0x80910, 0xF8, "B64A2EE671F4FBFC15744D610444669589FF0535E4A0878B50718ABD0F5F4E85"),
    "has_hologuise": (0xEB22C, 0x24, "0807452DB6593E9CDF605A55AAF514116249D459944F23D317D8E274880A4E34"),
    "map_variant_selection": (0xE22F4, 0x1B8, "092CE3F2BEDF3A472F971C78ACFE93A3881F084632113D3111313C045DF6CBF4"),
    "bolt_pickup_radius": (0x87A88, 0x780, "E700A9CA83358AD519CDBBAC8989710EBD4FD44F840D35959BB4B977EC4ED308"),
    "equipment_switch": (0x85B30, 0xCE4, "40D382DD755EE166C232E9D7718046263866B0F8FD4D79FF4774CED7B5843522"),
    "magneboots_state": (0x8B690, 0xE8, "46F6F767DC28733E5934B717C13A4DDAD773848F53C874493FED55DC4695B294"),
    "grindboots_update": (0x950E8, 0x3E0, "8C02ABB599065F8A269D8147F8722283467540ABC7413CE39893D0D3049EAAE9"),
    "swimming_equipment": (0xA2750, 0x2B8, "66C7E9C438D7F2F98D6D1412DCF8F45EDE675389E3ED89EBE4EFF5A96B4F9512"),
    "sonic_summoner_consumer": (0x3D8CA0, 0x4FC, "AC81E936D6419B5F36FAC76A3F268B2D96BE133DED79F0D1F6C1BCAEC441DA69"),
    "pilots_helmet_pickup": (0x23E140, 0x370, "35054985E0BD942759167C3C08A4996C5C1F4BE591AAF3969EF58A64CA9A4659"),
    "count_gold_bolts": (0x11B1B4, 0x110, "3CA16FD9823A5C618EBC4F1A492C84EB5665EAF1A33BC60FA51D7D5AF029F212"),
    "gold_bolt_pickup": (0x1D9D48, 0xAF0, "D41770E2C45F5787680B623ED92203E20C6CFDFBD71E3894CE7CD5EF7E1278FA"),
    "gold_bolt_spawn": (0x1DA838, 0x1A8, "B2434603CFE2599B5D79F7E0C288FD966418F0A8800A584A6773D06D48187AE6"),
    "gold_bolt_world_menu": (0x147044, 0x2AC, "2CBC59D4DE4B512D39AC99F82C5A84EE949EB1DDC3624791A49D0D8A40BA5348"),
    "save_load_callback": (0xE8CA0, 0x280, "FB8FB3252E14EB33DA1F68D50EEEAC1467D1F645D4AD7F05088BDBAA85DB0E6A"),
    "nanotech_vendor": (0x24A600, 0x514, "E716A3D6334D2804DCFFCAD34ABB1C1CD61E56B905C77FB4C7424A6B311FE28D"),
    "initialize_player_health": (0x7F018, 0x364, "02F7658F28285E7DCE29E78A718F08362AB0D6E42E2F18BD586C2B41C87DD0A7"),
    "new_game_plus": (0x13E634, 0x414, "CE405C620FDA5DC05CAAF3E90672A9EC4DB3E8C2DFD05D14AA398DC92E33CB74"),
    "initialize_save_state": (0xE7154, 0x4E4, "840388262AF5BB6DECBBA01109A07B0C4880D2E24DCE002DDE485555413EF325"),
}
ITEM_NAMES = {10: "Bomb Glove", 11: "Devastator", 13: "Visibomb Gun", 15: "Blaster",
              16: "Pyrocitor", 17: "Mine Glove", 19: "Tesla Claw", 20: "Glove of Doom",
              23: "R.Y.N.O.", 24: "Drone Device", 25: "Decoy Glove"}
WEAPON_NAMES = {**ITEM_NAMES, 9: 'Suck Cannon', 14: 'Taunter', 18: 'Walloper', 21: 'Morph-o-Ray'}
GADGET_NAMES = {12: 'Swingshot', 22: 'Hydrodisplacer', 26: 'Trespasser', 27: 'Metal Detector',
                31: 'Hologuise', 32: 'Gadgetron PDA', 33: 'Map-o-matic', 34: 'Bolt Grabber', 35: 'Persuader'}
EQUIPMENT_NAMES = {2: 'Heli-Pack', 3: 'Thruster-Pack', 4: 'Hydro-Pack', 5: 'Sonic Summoner',
                   6: 'O2 Mask', 7: "Pilot's Helmet", 28: 'Magneboots', 29: 'Grindboots', 30: 'Hoverboard'}
WORLD_NAMES = ['Veldin (opening)', 'Novalis', 'Aridia', 'Kerwan', 'Eudora', 'Rilgar', 'Nebula G34',
               'Umbris', 'Batalia', 'Gaspar', 'Orxon', 'Pokitaru', 'Hoven', 'Gemlik Base', 'Oltanis',
               'Quartu', 'Kalebo III', "Drek's Fleet", 'Veldin (finale)']


def audit_notification(read, saved_ranges):
    """Bounded straight-line memory/control-flow audit, not a PPC emulator.

    Vector loads/arithmetic are decoded for their memory effects; timer values
    and localized text are not evaluated. Call effects follow the two pinned,
    separately traced helpers. Refuse any additional instruction or call.
    """
    def signed(value, bits=16):
        return value - (1 << bits) if value & (1 << (bits - 1)) else value

    registers = {3: 'message_id', 28: 0x96C140, 31: 'item_id'}
    loads, calls, stores = [], [], []
    vector_count = 0
    for address in range(0x112EA4, 0x112F30, 4):
        word = struct.unpack('>I', read(address, 4))[0]
        op, rt, ra, rb = word >> 26, word >> 21 & 31, word >> 16 & 31, word >> 11 & 31
        immediate = signed(word & 65535)
        if op in (12, 14, 15):
            base = 0 if ra == 0 else registers.get(ra)
            if not isinstance(base, int):
                raise ValueError('Unknown notification address base')
            registers[rt] = (base + immediate * (65536 if op == 15 else 1)) & 0xFFFFFFFF
        elif op == 24:  # ori, including register copies and nop
            if rt == ra == 0 and word & 65535 == 0:
                continue
            source = registers.get(rt)
            if word & 65535 == 0:
                registers[ra] = source
            elif isinstance(source, int):
                registers[ra] = source | (word & 65535)
            else:
                raise ValueError('Unknown notification OR source')
        elif op == 4:
            # VX forms: splats, shift, conversion and comparison. VA forms:
            # vmaddfp and vsel. None writes GPRs or memory.
            if word & 2047 not in (0x38C, 0x184, 0x28C, 0x3CA, 0x086) and word & 63 not in (0x2E, 0x2A):
                raise ValueError(f'Unknown notification vector instruction at 0x{address:X}')
            vector_count += 1
        elif op == 31:
            xo = word >> 1 & 1023
            if xo == 986:  # extsw
                if registers.get(rt) != 'message_id':
                    raise ValueError('Unexpected notification sign extension')
                registers[ra] = 'message_id'
            elif xo == 519:  # Cell lvlx: aligned read + register shift only
                base = 0 if ra == 0 else registers.get(ra)
                index = registers.get(rb)
                if not isinstance(base, int) or not isinstance(index, int):
                    raise ValueError('Unknown Cell load address')
                effective = (base + index) & 0xFFFFFFFF
                loads.append(dict(address=hex(address), mnemonic='lvlx', effective_address=hex(effective),
                                  aligned_read=hex(effective & ~15), bytes=16))
            elif xo == 87:  # lbzx: reload saved ownership for the following path
                if (registers.get(ra), registers.get(rb)) != (0x96C140, 'item_id'):
                    raise ValueError('Unexpected notification ownership reload')
                registers[rt] = 'ownership_byte'
            elif xo == 199:  # stvewx: one aligned BE32 at a fixed runtime address
                base = 0 if ra == 0 else registers.get(ra)
                index = registers.get(rb)
                if not isinstance(base, int) or not isinstance(index, int):
                    raise ValueError('Unknown notification store address')
                stores.append(dict(address=hex(address), destination=hex(((base + index) & 0xFFFFFFFF) & ~3), bytes=4))
            else:
                raise ValueError(f'Unexpected notification X-form instruction at 0x{address:X}')
        elif op == 18 and word & 1:
            displacement = signed(word & 0x3FFFFFC, 26)
            target = (displacement if word & 2 else address + displacement) & 0xFFFFFFFF
            if target == 0x7B740 and registers.get(3) == 'message_id':
                calls.append(dict(address=hex(address), target=hex(target), role='localized text lookup; no writes'))
                result = 'localized_text_pointer'
            elif target == 0x5CC8D8 and registers.get(3) == 0xA15C8C and registers.get(4) == 'localized_text_pointer':
                calls.append(dict(address=hex(address), target=hex(target), role='NUL-terminated string copy', destination='0xa15c8c'))
                result = 0xA15C8C
            else:
                raise ValueError('Unexpected notification call or arguments')
            for register in (0, *range(3, 13)):
                registers.pop(register, None)
            registers[3] = result
        else:
            raise ValueError(f'Unexpected notification control flow or instruction at 0x{address:X}')

    if [load['effective_address'] for load in loads] != ['0x112e10', '0x71f410', '0x112e14'] or len(calls) != 2:
        raise ValueError('Notification load/call sequence mismatch')
    if stores != [dict(address='0x112f2c', destination='0xa15c80', bytes=4)] or registers.get(4) != 'ownership_byte':
        raise ValueError('Notification store/exit mismatch')
    for destination, length in ((0xA15C80, 4), (0xA15C8C, 1)):
        if any(destination < start + size and start < destination + length for start, size in saved_ranges):
            raise ValueError('Notification destination overlaps serialized state')
    return dict(start='0x112ea4', end_exclusive='0x112f30', instruction_count=35,
                sha256=hashlib.sha256(read(0x112EA4, 0x8C)).hexdigest().upper(),
                vector_register_operations=vector_count, vector_loads=loads, calls=calls, direct_stores=stores,
                serialized_destination_overlap=False,
                text_extent='Runtime NUL-terminated localized string; length is not inferred from a save.',
                rule='Notification text/timer remain runtime-only; the shared grant tail supplies the saved writes.')


def inspect(path):
    raw = Path(path).read_bytes()
    if len(raw) != ELF_SIZE or hashlib.sha256(raw).hexdigest().upper() != ELF_SHA256:
        raise ValueError("RC1 reference ELF size/SHA-256 mismatch")
    if raw[:6] != b"\x7fELF\x02\x02" or struct.unpack_from(">H", raw, 18)[0] != 21:
        raise ValueError("Expected a big-endian PowerPC64 ELF")
    header = struct.unpack_from(">HHIQQQIHHHHHH", raw, 16)
    segments = []
    for index in range(header[9]):
        ptype, flags, offset, address, _, size, _, _ = struct.unpack_from(">IIQQQQQQ", raw, header[4] + index * header[8])
        if ptype == 1 and size:
            if offset + size > len(raw):
                raise ValueError("Truncated ELF segment")
            segments.append((address, offset, size))

    def read(address, size):
        for start, offset, length in segments:
            if start <= address and address + size <= start + length:
                return raw[offset + address - start:offset + address - start + size]
        raise ValueError(f"Unmapped file-backed address 0x{address:X}+0x{size:X}")

    guards = {}
    for name, (address, size, expected) in FUNCTIONS.items():
        actual = hashlib.sha256(read(address, size)).hexdigest().upper()
        if actual != expected:
            raise ValueError("Native function changed: " + name)
        guards[name] = dict(address=hex(address), size=size, sha256=actual)

    records, offset = [], 16
    for index in range(49):
        slot = 0x726690 + 16 * index
        address, size, record_id, state = struct.unpack(">IIII", read(slot, 16))
        if address == 0:
            break
        if size == 0 or size > 0x10000 or state != 0:
            raise ValueError("Unexpected player record descriptor")
        records.append(dict(id=record_id, length=size, offset=offset + 8,
                            table_address=hex(slot), runtime_address=hex(address)))
        offset += 8 + ((size + 3) & ~3)
    if len(records) != 48 or len({record['id'] for record in records}) != 48 or offset + 8 != 0x1544:
        raise ValueError("Unexpected RC1 player table shape")
    by_id = {record['id']: record for record in records}
    if (by_id[9]['runtime_address'], by_id[10]['runtime_address']) != ('0x96c0ac', '0x96c140'):
        raise ValueError("Unexpected inventory serialization roots")
    saved_ranges = [(int(record['runtime_address'], 0), record['length']) for record in records]
    # Include all twenty repeated world payloads, not only player records.
    for index in range(12):
        address, size, _, _ = struct.unpack('>IIII', read(0x7269A0 + index * 16, 16))
        if not address:
            break
        saved_ranges.extend((address + world * size, size) for world in range(20))
    notification = audit_notification(read, saved_ranges)
    ammo = []
    for item_id, name in ITEM_NAMES.items():
        slot = 0x737D30 + item_id * 24 + 14
        maximum = struct.unpack(">H", read(slot, 2))[0]
        if not 0 < maximum <= 1000:
            raise ValueError("Unexpected reference ammo capacity")
        ammo.append(dict(id=item_id, name=name, maximum=maximum,
                         offset=by_id[9]['offset'] + 4 * item_id,
                         ownership_offset=by_id[10]['offset'] + item_id,
                         capacity_address=hex(slot)))
    pickup_ids = struct.unpack('>20I', read(0x737BF0, 80))
    weapons = []
    for item_id, name in sorted(WEAPON_NAMES.items()):
        item = 0x737D30 + item_id * 24
        capacity = struct.unpack('>H', read(item + 14, 2))[0]
        initial = struct.unpack('>H', read(item + 18, 2))[0]
        price = struct.unpack('>H', read(item + 8, 2))[0]
        kind = struct.unpack('>I', read(0x721008 + item_id * 76, 4))[0]
        messages = [struct.unpack('>i', read(0x729380 + (item_id + bank * 37) * 4, 4))[0] for bank in (0, 1)]
        # The previously excluded Cell path is now audited separately. Its
        # notification buffer/timer are outside the serialized record ranges.
        grant = kind == 0
        if initial > capacity or kind != 0:
            raise ValueError('Unexpected combat weapon definition')
        weapons.append(dict(id=item_id, name=name, maximum=capacity, initial_ammo=initial if price else 0,
                            grant_supported=grant, acquisition_list=item_id in pickup_ids,
                            ownership_offset=by_id[10]['offset'] + item_id,
                            acquisition_flag_offset=by_id[11]['offset'] + item_id,
                            ammo_offset=by_id[9]['offset'] + 4 * item_id,
                            item_type=kind, notification_ids=messages))
    if sum(item['grant_supported'] for item in weapons) != 15:
        raise ValueError('Unexpected safe grant allowlist')
    if struct.unpack('>II', read(0x112E9C, 8)) != (0x2C03FFFF, 0x41820090):
        raise ValueError('Grant notification bypass branch changed')
    gold = extract_gold_upgrades(read, by_id, weapons)
    gadgets = extract_gadgets(read, by_id)
    equipment = extract_equipment(read, by_id)
    gold_bolts = extract_gold_bolts(read)
    return dict(collection_id='BCES01503', save_id='NPEA00385', executable_version='unknown',
                binary=dict(file='RC1.ppu.elf', size=ELF_SIZE, sha256=ELF_SHA256),
                functions=guards, player_records=records, ammo=ammo, weapons=weapons, notification=notification,
                gold_upgrades=gold, gadgets=gadgets, equipment=equipment, gold_bolts=gold_bolts,
                nanotech=extract_nanotech(read, by_id),
                grant_layout=dict(flag_record=11, acquisition_record=12, acquisition_offset=by_id[12]['offset'],
                                  acquisition_bytes=12, acquisition_empty=255, acquisition_flag=64,
                                  quick_record=13, quick_offset=by_id[13]['offset'], quick_slots=8, quick_empty=0,
                                  notification_bypass=dict(compare_address='0x112e9c', branch_address='0x112ea0',
                                                           target_address='0x112f30')),
                notes=["Names follow the existing external RC1 reference; native evidence binds IDs, storage and capacities.",
                       "Capacities are shipped reference limits, not a live runtime query.",
                       "Record 11 and ownership bytes are not changed by ammo edits.",
                       "Software round trips do not establish gameplay acceptance."])


def extract_nanotech(read, records):
    flags, health = records[5], records[19]
    if (flags['runtime_address'], flags['length']) != ('0x96bff0', 128) or (
            health['runtime_address'], health['length']) != ('0x71fb28', 4):
        raise ValueError('Unexpected nanotech serialization roots')
    # Independently bind key instructions to the separately fingerprinted traces.
    # The vendor's later Cell presentation block is not part of these stores.
    expected = {0x24A8B8: 0x3F800097, 0x24A8BC: 0x339CBFF0,
                0x24A8C0: 0x887C0004, 0x24A8C8: 0x408200A4,
                0x24A910: 0x3BA00001, 0x24A91C: 0x9BBC0004,
                0x24A930: 0x3CA00072, 0x24A934: 0x38C00005, 0x24A940: 0x90C5FB28,
                0x24A96C: 0x887C0005, 0x24A9C8: 0x38800001, 0x24A9D8: 0x989C0005,
                0x24AA00: 0x3CA00072, 0x24AA04: 0x38C00008, 0x24AA10: 0x90C5FB28,
                0xE7164: 0x3C600072, 0xE716C: 0x3A000004, 0xE7190: 0x9203FB28,
                0x7F2E0: 0x8063FB28, 0x7F2E8: 0x907F22A8,
                0x13E948: 0x38A00005, 0x13E94C: 0x987F0004, 0x13E950: 0x90A4FB28,
                0x13E968: 0x38A00008, 0x13E96C: 0x987F0005, 0x13E970: 0x90A4FB28}
    if any(struct.unpack('>I', read(address, 4))[0] != word for address, word in expected.items()):
        raise ValueError('Nanotech ownership, prerequisite or capacity instructions changed')
    return dict(flag_record=5, premium_offset=flags['offset'] + 4, ultra_offset=flags['offset'] + 5,
                capacity_record=19, capacity_offset=health['offset'],
                tiers=[dict(level=0, name='Standard', capacity=4),
                       dict(level=1, name='Premium Nanotech', capacity=5),
                       dict(level=2, name='Ultra Nanotech', capacity=8)],
                runtime_health='0x96bf88', runtime_health_serialized=False,
                rule='Add-only canonical tiers; Ultra includes Premium. Preserve currency, progression and trophy state.')


def extract_gold_bolts(read):
    records, offset = [], 8
    for index in range(12):
        address, size, record_id, state = struct.unpack('>IIII', read(0x7269A0 + index * 16, 16))
        if not address:
            break
        if not 0 < size <= 0x8000 or state != 0:
            raise ValueError('Unexpected world descriptor')
        records.append(dict(id=record_id, length=size, offset=offset + 8, runtime_address=hex(address)))
        offset += 8 + ((size + 3) & ~3)
    if len(records) != 11 or len({item['id'] for item in records}) != 11 or offset + 8 != 0x82A4:
        raise ValueError('Unexpected world table shape')
    gold = next(item for item in records if item['id'] == 3003)
    if (gold['runtime_address'], gold['offset'], gold['length']) != ('0xa0ca34', 0x8024, 4):
        raise ValueError('Unexpected world gold-bolt record')
    counts = struct.unpack('>19I', read(0x738608, 76))
    if counts != (0, 3, 4, 3, 1, 2, 2, 2, 2, 2, 2, 1, 2, 1, 4, 2, 2, 2, 3):
        raise ValueError('Unexpected world gold-bolt totals')
    # Straight-line flag store: load slot from actor PVARs, load current world,
    # form 0xA0CA34 + slot + world*4 and stbx literal 1. No calls in this block.
    words = (0x3C600097, 0x80BE0000, 0x3C8000A1, 0x38C00001, 0x3084CA34, 0x80639C70,
             0x7C852014, 0x5463103A, 0x78840020, 0x7C6307B4, 0x7CC419AE)
    if read(0x1DA110, 44) != struct.pack('>11I', *words):
        raise ValueError('Gold-bolt pickup flag store changed')
    fields = [dict(world=world, planet=WORLD_NAMES[world], slot=slot,
                   offset=0x1544 + world * 0x82A4 + gold['offset'] + slot)
              for world, count in enumerate(counts) for slot in range(count)]
    return dict(world_start=0x1544, world_stride=0x82A4, world_count=20, world_records=records,
                record_id=3003, flag_offset=gold['offset'], counts_address='0x738608', counts=list(counts), fields=fields,
                pickup_store=dict(start='0x1da110', instruction_count=11, value=1,
                                  address_rule='0xA0CA34 + world * 4 + slot'),
                name_reference='https://github.com/bordplate/rac1-randomizer/blob/main/table_id.lua',
                slot_verification_tool='Tools/PS3/RatchetAndClank1/NPEA00385/unknown/Inspect-Rc1GoldPickups.py')


def extract_equipment(read, records):
    if (records[32]['runtime_address'], records[32]['length']) != ('0x969c7c', 28) or (
            records[23]['runtime_address'], records[23]['length']) != ('0x969c9c', 4):
        raise ValueError('Unexpected retained equipment selection records')
    pickup_ids = struct.unpack('>20I', read(0x737BF0, 80))
    result = []
    for item_id, name in EQUIPMENT_NAMES.items():
        kind = struct.unpack('>I', read(0x721008 + item_id * 76, 4))[0]
        expected_kind = 3 if item_id in (2, 3, 4) else 2 if item_id in (5, 6, 7) else 1
        ammo = [struct.unpack('>H', read(0x737D30 + item_id * 24 + offset, 2))[0] for offset in (8, 14, 18)]
        if kind != expected_kind or any(ammo) or item_id in pickup_ids:
            raise ValueError('Unexpected equipment grant path, ammo initialization or acquisition membership')
        messages = [struct.unpack('>i', read(0x729380 + (item_id + bank * 37) * 4, 4))[0] for bank in (0, 1)]
        result.append(dict(id=item_id, name=name, item_type=kind, quick_select=False,
                           ownership_offset=records[10]['offset'] + item_id,
                           acquisition_flag_offset=records[11]['offset'] + item_id,
                           notification_ids=messages, acquisition_list=False, initializes_ammo=False,
                           editor_requests_equip=False))
    return result


def extract_gadgets(read, records):
    pickup_ids = struct.unpack('>20I', read(0x737BF0, 80))
    result = []
    for item_id, name in GADGET_NAMES.items():
        kind = struct.unpack('>I', read(0x721008 + item_id * 76, 4))[0]
        expected_kind = 4 if item_id in (33, 34) else 5 if item_id == 35 else 0
        ammo = [struct.unpack('>H', read(0x737D30 + item_id * 24 + offset, 2))[0] for offset in (8, 14, 18)]
        if kind != expected_kind or any(ammo) or item_id in pickup_ids:
            raise ValueError('Unexpected gadget grant path, ammo initialization or acquisition membership')
        messages = [struct.unpack('>i', read(0x729380 + (item_id + bank * 37) * 4, 4))[0] for bank in (0, 1)]
        result.append(dict(id=item_id, name=name, item_type=kind, quick_select=kind == 0,
                           ownership_offset=records[10]['offset'] + item_id,
                           acquisition_flag_offset=records[11]['offset'] + item_id,
                           notification_ids=messages, acquisition_list=False, initializes_ammo=False))
    return result


def extract_gold_upgrades(read, records, weapons):
    record = records[30]
    if (record['runtime_address'], record['offset'], record['length']) != ('0x969ca8', 0x11D8, 40):
        raise ValueError('Unexpected gold-upgrade serialization root')
    vendor_ids = struct.unpack('>10I', read(0x811CB0, 40))
    expected = {9, 10, 11, 15, 16, 17, 19, 20, 21, 25}
    if len(set(vendor_ids)) != 10 or set(vendor_ids) != expected:
        raise ValueError('Unexpected gold vendor item table')
    result = []
    for weapon in weapons:
        address = 0x721008 + weapon['id'] * 76 + 54
        maximum = struct.unpack('>H', read(address, 2))[0]
        if maximum != int(weapon['id'] in expected):
            raise ValueError('Gold vendor and item upgrade limits disagree')
        if maximum:
            result.append(dict(id=weapon['id'], name=weapon['name'], offset=record['offset'] + weapon['id'],
                               ownership_offset=weapon['ownership_offset'], maximum=maximum,
                               limit_address=hex(address)))
    return dict(record_id=30, runtime_address='0x969ca8', offset=record['offset'], bytes=40,
                vendor_table_address='0x811cb0', vendor_ids=list(vendor_ids), weapons=result,
                rule='Add-only flags for already-owned weapons. No purchase, currency, collectible, equipment or trophy writes.',
                balance_rule='The game clamps collected gold bolts minus four per counted upgrade to 0..40; flags affect this derived balance.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', required=True, type=Path)
    options = parser.parse_args()
    try:
        print(json.dumps(inspect(options.elf), indent=2))
    except (OSError, ValueError, struct.error) as error:
        parser.exit(1, str(error) + '\n')
