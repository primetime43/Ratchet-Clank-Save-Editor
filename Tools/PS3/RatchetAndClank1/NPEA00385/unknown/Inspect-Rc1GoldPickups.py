"""Verify actual gold-bolt slot IDs in all supplied PAL RC1 gameplay assets.

Read-only PSARC extraction into memory; no payloads are executed or rewritten.
The small structure reader uses documented RC1 gameplay/moby/PVAR offsets.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[5]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def slots(payload):
    def word(offset):
        if offset < 0 or offset + 4 > len(payload):
            raise ValueError('Gameplay field outside payload')
        return struct.unpack_from('>I', payload, offset)[0]
    mobys, sizes, pvars = (word(offset) for offset in (0x44, 0x54, 0x58))
    count = word(mobys)
    if not 0 < count <= 100000 or mobys + 16 + count * 0x78 > len(payload) or not 0 < sizes <= pvars < len(payload):
        raise ValueError('Unexpected RC1 gameplay structure')
    found = []
    for index in range(count):
        actor = mobys + 16 + index * 0x78
        if word(actor + 0x18) != 1134:
            continue
        pvar_index = word(actor + 0x58)
        descriptor = sizes + pvar_index * 8
        if descriptor < sizes or descriptor + 8 > pvars:
            raise ValueError('Gold-bolt PVAR descriptor outside table')
        offset, length = word(descriptor), word(descriptor + 4)
        if length != 0x80 or pvars + offset + length > len(payload):
            raise ValueError('Unexpected gold-bolt PVAR payload')
        slot = word(pvars + offset)
        if slot >= 4 or slot in found:
            raise ValueError('Invalid or duplicate gold-bolt slot')
        found.append(slot)
    return sorted(found)


def inspect(archive_path, elf):
    native = module('rc1_gold_native', Path(__file__).with_name('Inspect-Rc1Native.py')).inspect(elf)
    reader = module('rc1_gold_psarc', ROOT / 'Tools/Inspect-Psarc.py')
    archive = reader.Psarc(archive_path)
    if archive.compression != 'lzma' or not all(archive.name_hashes_match):
        raise ValueError('Unexpected RC1 archive compression or filename hashes')
    worlds = []
    for world in range(19):
        name = f'/rc1/ps3data/level{world}/gameplay_pal'
        if archive.names.count(name) != 1:
            raise ValueError('Missing or duplicate PAL gameplay asset')
        payload = archive.read_entry(archive.names.index(name), 16 * 1024 * 1024)
        actual = slots(payload)
        expected = [item['slot'] for item in native['gold_bolts']['fields'] if item['world'] == world]
        if actual != expected:
            raise ValueError(f'Native count / actual pickup slots disagree in world {world}')
        worlds.append(dict(world=world, asset=name, bytes=len(payload), slots=actual,
                           sha256=hashlib.sha256(payload).hexdigest().upper()))
    with Path(archive_path).open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest().upper()
    return dict(archive=dict(bytes=archive.size, sha256=digest), worlds=worlds,
                total=sum(len(world['slots']) for world in worlds),
                structure_reference='https://github.com/RatchetModding/Replanetizer/tree/master/LibReplanetizer')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--elf', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.archive, args.elf), indent=2))
