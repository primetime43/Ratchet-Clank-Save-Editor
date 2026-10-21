"""Inspect the supplied European trilogy RC1 ELF without executing game code.

Checks exact binary identity and bounded native function fingerprints, then
extracts the player record table and ammo capacities. JSON goes to stdout.
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
}
ITEM_NAMES = {10: "Bomb Glove", 11: "Devastator", 13: "Visibomb Gun", 15: "Blaster",
              16: "Pyrocitor", 17: "Mine Glove", 19: "Tesla Claw", 20: "Glove of Doom",
              23: "R.Y.N.O.", 24: "Drone Device", 25: "Decoy Glove"}
WEAPON_NAMES = {**ITEM_NAMES, 9: 'Suck Cannon', 14: 'Taunter', 18: 'Walloper', 21: 'Morph-o-Ray'}


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
        # The Cell-vector notification path is not fully decoded by Ghidra.
        # Permit grants only for items whose two message selectors bypass it.
        grant = messages == [-1, -1] and kind == 0
        if initial > capacity or kind != 0:
            raise ValueError('Unexpected combat weapon definition')
        weapons.append(dict(id=item_id, name=name, maximum=capacity, initial_ammo=initial if price else 0,
                            grant_supported=grant, acquisition_list=item_id in pickup_ids,
                            ownership_offset=by_id[10]['offset'] + item_id,
                            acquisition_flag_offset=by_id[11]['offset'] + item_id,
                            ammo_offset=by_id[9]['offset'] + 4 * item_id,
                            item_type=kind, notification_ids=messages))
    if sum(item['grant_supported'] for item in weapons) != 12:
        raise ValueError('Unexpected safe grant allowlist')
    if struct.unpack('>II', read(0x112E9C, 8)) != (0x2C03FFFF, 0x41820090):
        raise ValueError('Grant notification bypass branch changed')
    return dict(collection_id='BCES01503', save_id='NPEA00385', executable_version='unknown',
                binary=dict(file='RC1.ppu.elf', size=ELF_SIZE, sha256=ELF_SHA256),
                functions=guards, player_records=records, ammo=ammo, weapons=weapons,
                grant_layout=dict(flag_record=11, acquisition_record=12, acquisition_offset=by_id[12]['offset'],
                                  acquisition_bytes=12, acquisition_empty=255, acquisition_flag=64,
                                  quick_record=13, quick_offset=by_id[13]['offset'], quick_slots=8, quick_empty=0,
                                  notification_bypass=dict(compare_address='0x112e9c', branch_address='0x112ea0',
                                                           target_address='0x112f30')),
                notes=["Names follow the existing external RC1 reference; native evidence binds IDs, storage and capacities.",
                       "Capacities are shipped reference limits, not a live runtime query.",
                       "Record 11 and ownership bytes are not changed by ammo edits.",
                       "Software round trips do not establish gameplay acceptance."])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', required=True, type=Path)
    options = parser.parse_args()
    try:
        print(json.dumps(inspect(options.elf), indent=2))
    except (OSError, ValueError, struct.error) as error:
        parser.exit(1, str(error) + '\n')
