"""Read-only exact-build equipment history and bounded saved RLE block research."""
import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("bindings", Path(__file__).with_name("Inspect-TodWeaponBindings.py"))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)


def decode_stream(encoded):
    """Safe native-format decoder: never overread declared input or exceed256KiB."""
    if len(encoded) > 0x5FFF:
        raise ValueError("Declared length exceeds native encoder cap")
    position, accumulator, clipped, tokens = 0, 0, 0, 0
    output = bytearray()
    while position < len(encoded) and len(output) < 0x40000:
        value = encoded[position]
        # Native decoder stops considering pairs in its final four output bytes.
        if len(output) <= 0x3FFFB and position + 1 < len(encoded) and encoded[position + 1] == value:
            if position + 4 > len(encoded):
                raise ValueError("Truncated repeated-byte token")
            extra = int.from_bytes(encoded[position + 2:position + 4], "big")
            count = extra + 2
            accumulator += extra if value == 0 else 0
            position += 4
        else:
            count = 1
            accumulator += value == 0
            position += 1
        take = min(count, 0x40000 - len(output))
        clipped += count - take
        output.extend(bytes([value]) * take)
        tokens += 1
    return bytes(output), {"consumed": position, "trailing_encoded_bytes": len(encoded) - position,
        "decoded_size": len(output), "complete": len(output) == 0x40000,
        "clipped_run_bytes": clipped, "encoder_accumulator": accumulator, "token_count": tokens,
        "decoded_sha256": hashlib.sha256(output).hexdigest().upper(),
        "value_histogram": {str(k): v for k, v in sorted(collections.Counter(output).items())}}


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    checks = {0x1F5588: 0x80AB0188, 0x1F558C: 0x83A51A68,
        0x1F5598: 0x909D0434, 0x1F559C: 0x913D0430, 0x1F55A8: 0x907D042C,
        0x1F55A0: 0x4BE1C271, 0x1181C: 0x484556A4,
        0x1F5DD8: 0x909C0188, 0x23E744: 0x913F1A68, 0x897B38: 0x101EFB20,
        0x35E170: 0x1D7F60DC, 0x35E180: 0x390914D8, 0x35E190: 0x2C3F0015,
        0x35C490: 0x386614D8, 0x35C498: 0x810360D0,
        0x35C4B0: 0x392500C0, 0x35C4D4: 0x894C000D,
        0x35C56C: 0x392A0002, 0x35C558: 0x3D800004, 0x35C620: 0x2B035FFF,
        0x35C744: 0x93E40010, 0x35C748: 0x98640014, 0x35C728: 0x3BA91590,
        0x35E088: 0x980300CC, 0x35E08C: 0x912360D0, 0x8A1900: 0x101EFB20}
    for address, word in checks.items():
        if elf.u32(address) != word:
            raise ValueError(f"Instruction/pointer shape changed at {address:#x}")
    stride = elf.u32(0x35E170) & 65535
    base = 0x10000 + (elf.u32(0x35E180) & 65535)
    count = elf.u32(0x35E190) & 65535
    payload = (elf.u32(0x35C4B0) & 65535) + (elf.u32(0x35C4D4) & 65535)
    length_member = elf.u32(0x35C498) & 65535
    accumulator = 0x10000 + (elf.u32(0x35C728) & 65535) + (elf.u32(0x35C744) & 65535) - base
    ready = elf.u32(0x35E088) & 65535
    guards = {address: elf.read(address, 4) for address in checks}
    for function in (0x1F5570, 0x1F5DB8, 0x466EC0, 0x466E88, 0x466E28,
            0x288060, 0x2B7F70, 0x26CE30, 0x1E33C8, 0x35C460, 0x35C5B8,
            0x35E110, 0x35E070, 0x24EAC8, 0x24DAB8, 0x35E710):
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    for thunk in (0x11810, 0x10660, 0x12670, 0x250758):
        guards[thunk] = elf.read(thunk, 16)
    slot = 0x89E004
    name, descriptor = struct.unpack(">II", elf.read(slot, 8))
    if elf.string(name) != "hero_get_equipped" or elf.u32(descriptor) != 0x2B7F70:
        raise ValueError("Named equipped-item binding changed")
    for address, size in ((slot, 8), (descriptor, 8), (name, len("hero_get_equipped") + 1), (0x84A4E0, 4)):
        guards[address] = elf.read(address, size)
    report = {"confidence": "code-backed", "warning": "Exact USA build. RLE byte meanings and gameplay edit acceptance remain unknown; no original files are modified.",
        "equipment_history": {"offsets": [hex(elf.u32(a) & 65535) for a in (0x1F55A8, 0x1F559C, 0x1F5598)],
            "type": "int32 BE item IDs; raw bits retained", "update_va": "0x1f5570", "owner_initializer_va": "0x1f5db8",
            "named_getter_chain": ["0x2b7f70", "0x288060", "0x466ec0"],
            "semantics": "Update shifts old430 to434, old42C to430, then records native equipped getter11810 ->466EC0 into42C. Inventory+188 is initialized to hero; hero+1A68 points to serialized state. History updater descriptor8666D8 is referenced at84A4E0 for indirect dispatch. IDs are historical snapshots, not dual-wield primary/secondary slots.",
            "warning": "Initializer storesFFFFFFFF in all three words. Restore consumes42C/430 with fallback logic; menu26CE30 also consults434. Callback timing, duplicates, reset policy and safe history edits are not gameplay-validated. Current in-memory equipment can differ from these saved values."},
        "rle_blocks": {"base": hex(base), "stride": hex(stride), "count": count,
            "end_exclusive": hex(base + stride * count), "ready_member": hex(ready), "accumulator_member": hex(accumulator),
            "payload_member": hex(payload), "encoded_size_member": hex(length_member),
            "native_encoded_limit": (elf.u32(0x35C620) & 65535), "decoded_limit": (elf.u32(0x35C558) & 65535) << 16,
            "encoder_va": "0x35c5b8", "decoder_va": "0x35c460", "initializer_va": "0x35e070",
            "presnapshot_chain": ["0x35e710", "0x250758", "0x24eac8", "0x24dab8", "0x12670", "0x35c5b8"],
            "encoding": "An unequal byte is literal. Two equal bytes start four-byte token value,value,BE16 additional-repeat count; run length=count+2. Native decoder caps output at40000 and stops pair checks after output offset3FFFB. Safe research decoder additionally bounds token reads by declared input; it never imitates native out-of-range reads.",
            "accumulator": "Encoder memberC8 adds1 for a zero literal or BE16 additional-repeat count for a zero run; initial two repeated bytes are excluded. It is NOT exact zero-byte count, completion count or checksum.",
            "warning": "21 physical slots, not a confirmed planet index catalog. Ready byte nonzero marks encoder-produced storage, not visit/completion status. Header prefixes, per-byte logical meanings, tail60D4..60DB and synchronization/reset dependencies remain unresolved. Final runs can extend beyond decoded output and are clipped by native restore; preserve original encoded bytes."},
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        if Path(save_path).stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save layout")
        data = Path(save_path).read_bytes()
        if any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        blocks = []
        for index in range(count):
            start = base + stride * index
            length = struct.unpack_from(">I", data, start + length_member)[0]
            stored = struct.unpack_from(">I", data, start + accumulator)[0]
            block = {"index": index, "offset": hex(start), "ready_byte": data[start + ready],
                "encoded_size": length, "saved_accumulator": stored, "opaque_tail": data[start + 0x60D4:start + stride].hex().upper()}
            if block["ready_byte"] == 0:
                block["status"] = "No encoded state marked ready; payload not interpreted"
            elif length > report["rle_blocks"]["native_encoded_limit"]:
                block["status"] = "Declared length exceeds native encoder cap; payload not interpreted"
            else:
                try:
                    _, decoded = decode_stream(data[start + payload:start + payload + length])
                    block.update(decoded)
                    block["accumulator_matches"] = stored == decoded["encoder_accumulator"]
                    block["status"] = "Decoded to native output cap" if decoded["complete"] else "Short decoded output; no padding or repair"
                except ValueError as error:
                    block["status"] = str(error)
            blocks.append(block)
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "equipment_history_ids": list(struct.unpack_from(">3i", data, 0x42C)), "blocks": blocks}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path, help="Plaintext working copy only; no bytes are written")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2))
