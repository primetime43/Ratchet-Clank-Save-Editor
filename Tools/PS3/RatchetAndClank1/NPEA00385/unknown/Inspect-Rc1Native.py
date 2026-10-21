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
}
ITEM_NAMES = {10: "Bomb Glove", 11: "Devastator", 13: "Visibomb Gun", 15: "Blaster",
              16: "Pyrocitor", 17: "Mine Glove", 19: "Tesla Claw", 20: "Glove of Doom",
              23: "R.Y.N.O.", 24: "Drone Device", 25: "Decoy Glove"}


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
    return dict(collection_id='BCES01503', save_id='NPEA00385', executable_version='unknown',
                binary=dict(file='RC1.ppu.elf', size=ELF_SIZE, sha256=ELF_SHA256),
                functions=guards, player_records=records, ammo=ammo,
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
