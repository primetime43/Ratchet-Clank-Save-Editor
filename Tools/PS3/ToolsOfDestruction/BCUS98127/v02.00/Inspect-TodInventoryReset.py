"""Read-only inventory reset write footprint and opaque prefix-byte ownership.

Pure previews use detached fixtures only; no native code or original save writes.
Initialization, standalone record reset and restart preservation are distinct.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))


def reset_record_preview(record, item_id):
    """Detached ordinary-ID model of465C98; the two opaque bytes survive."""
    if not isinstance(record, (bytes, bytearray)) or len(record) != 0x14:
        raise ValueError("Expected one detached20-byte record")
    if type(item_id) is not int or not 0 <= item_id < 32:
        raise ValueError("Preview requires a normal inventory ID0..31")
    result = bytearray(record)
    struct.pack_into(">I", result, 0, item_id)
    result[4:0x12] = bytes(0xE)
    return bytes(result)


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}

    def keep(va, size):
        guards[va] = elf.read(va, size)

    def require(va, expected):
        if elf.u32(va) != expected:
            raise ValueError(f"Inventory reset evidence changed at {va:#x}")
        keep(va, 4)

    leaf = 0x465C98
    end = elf.functions[elf.functions.index(leaf) + 1]
    keep(leaf, end - leaf)
    zeros, writes = set(), []
    for va, word in elf.instructions(leaf, end):
        op, source, base = word >> 26, word >> 21 & 31, word >> 16 & 31
        if op == 14 and base == 0 and (word & 0xFFFF) == 0:
            zeros.add(source)
        elif op in (36, 38) and base == 3:
            offset, width = word & 0xFFFF, 4 if op == 36 else 1
            value = "item_id_argument" if source == 4 and offset == 0 and width == 4 else 0
            if value == 0 and source not in zeros:
                raise ValueError("Unknown value in record reset")
            writes.append({"offset": hex(offset), "size": width, "value": value, "write_va": hex(va)})
        elif word != 0x4E800020:
            raise ValueError(f"Unexpected reset-leaf instruction at {va:#x}")
    touched = {b for w in writes for b in range(int(w["offset"], 0), int(w["offset"], 0) + w["size"])}
    if touched != set(range(0x12)):
        raise ValueError("Record reset byte footprint changed")
    for va, expected in {
        0x35DC98: 0x48108DC9,
        0x466A78: 0x38800000, 0x466A7C: 0x38A00280,
        0x466A94: 0x4BDEBEA5, 0x466AA8: 0x3BFF0014,
        0x466AAC: 0x4BFFF1ED, 0x466AB4: 0x2F9E001F,
        0x466ABC: 0x409EFFE4, 0x466AC4: 0x90BD0280,
        0x35DD78: 0x901F0480,
        0x35E138: 0x4BFFFB49, 0x35E154: 0x38640488,
        0x3CEDBC: 0x38A00484, 0x3CEDD0: 0x4BE83659,
        0x3CEE1C: 0x48096E7D,
    }.items():
        require(va, expected)
    for va in (0x466A60, 0x35DC80, 0x35E110):
        keep(va, elf.functions[elf.functions.index(va) + 1] - va)
    for va, size in ((0x252938, 16), (0x3CEDA0, 0x40), (0x3CEDD8, 0x54)):
        keep(va, size)
    # Independently read explicit scalar/loop write destinations in35DC80.
    # r31 is the incoming prefix; r5/r8/r9 are bounded loop addresses.
    prefix_stores = []
    for va, word in elf.instructions(0x35DCA0, 0x35DD80):
        op, base = word >> 26, word >> 16 & 31
        if op in (36, 52) and base == 31:
            prefix_stores.append({"va": hex(va), "offset": hex(word & 0xFFFF), "size": 4})
    offsets = {int(w["offset"], 0) for w in prefix_stores}
    if offsets != set(range(0x418, 0x45C, 4)) | {0x45C, 0x480}:
        raise ValueError("Prefix scalar store footprint changed")
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA v02.00 byte ownership only. Opaque bytes have no gameplay name or edit-safety contract. Viewing and synthetic previews do not initialize, reset or modify an original save.",
        "record_reset": {
            "function_va": "0x465c98", "record_size": 20, "writes": writes,
            "written_byte_range": {"start": "0x0", "end_exclusive": "0x12"},
            "untouched_byte_range": {"start": "0x12", "end_exclusive": "0x14"},
            "rule": "Standalone record reset writes the ID argument, clears XP/ammo/modifier words and ownership/level bytes, but leaves record+12/+13 untouched. This is18 written bytes out of20, not a full-record clear.",
        },
        "bulk_initializer": {
            "function_va": "0x466a60", "caller_va": "0x35dc80", "fill_call_va": "0x466a94",
            "fill_target_va": "0x252938", "zero_fill_size": "0x280", "record_count": 32, "record_stride": "0x14",
            "record_reset_call_va": "0x466aac", "counter_store_va": "0x466ac4",
            "rule": "Bulk initialization zero-fills all280 bytes before looping through32 record resets. Consequently both opaque tail bytes are zero at this initializer boundary, unlike standalone465C98. The acquisition counter at280 is separately cleared.",
        },
        "selective_restart": {
            "function_va": "0x3ced40", "prefix_copy_call_va": "0x3cedd0", "prefix_copy_size": "0x484",
            "selected_record_reset_call_va": "0x3cee1c",
            "rule": "Selective restart initializes staging, then copies allfirst484 live bytes before selected record resets. The reset leaf leaves +12/+13 untouched even for selected items, so copied opaque inventory tails survive those observed reset steps. Later callbacks are not included in this claim.",
        },
        "prefix_gap": {
            "start": "0x484", "end_exclusive": "0x488", "size": 4,
            "prefix_initializer_va": "0x35dc80", "next_world_start": "0x488",
            "explicit_scalar_stores": prefix_stores,
            "rule": "The complete prefix initializer reaches480..484 exclusively through its final scalar store, and the world loop starts at488. The four bytes484..487 are not written by these initializer steps and are not included by the first484-byte restart preservation copy. Their value at restart is not derived as zero or copied from the current save; no padding or unused-field claim is made.",
            "scope": "These are exact initializer/first-prefix-copy boundaries, not an exhaustive census of all runtime consumers or every later copy. Full906F0-byte snapshots include the bytes verbatim. Gameplay meaning remains unresolved.",
        },
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())],
    }
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Expected verified plaintext save size")
        data = path.read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
            raise ValueError("Expected verified plaintext inventory IDs0..31")
        report["save_observation"] = {
            "size": len(data), "sha256": hashlib.sha256(data).hexdigest().upper(),
            "record_opaque_tails": [{"id": i, "offset": hex(i * 20 + 0x12), "hex": data[i * 20 + 0x12:i * 20 + 0x14].hex().upper()} for i in range(32)],
            "prefix_gap_hex": data[0x484:0x488].hex().upper(),
            "warning": "Observed zero bytes are not proof of unused storage or a default for other lifecycle paths. No reset/initializer is run.",
        }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2))
