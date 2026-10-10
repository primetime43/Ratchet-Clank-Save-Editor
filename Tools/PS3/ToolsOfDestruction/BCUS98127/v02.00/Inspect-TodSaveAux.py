"""Read-only exact-build saved adaptation counters and bounded modifier evidence."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("bindings", Path(__file__).with_name("Inspect-TodWeaponBindings.py"))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    for address, expected in {
            0x8A3554: 0x101EFB20, 0x8A1944: 0x3F800000,
            0x8A3540: 0x3F800000, 0x8A3544: 0,
            0x8A3558: 0x3DCCCCCD, 0x8A355C: 0xBD4CCCCD,
            0x8A3560: 0x3F19999A,
            0x35E11C: 0x787D0020, 0x35E124: 0x7C7E1B78,
            0x35E198: 0x381E5528, 0x35E1AC: 0x4BFFF7F5,
            0x35D9BC: 0x7C7F1B78, 0x35DB7C: 0x3BA00000,
            0x35DB64: 0x393F321C, 0x35DB68: 0xC0021A24,
            0x35DBA4: 0x93A80014, 0x35DBA8: 0x93A80018,
            0x35DBAC: 0xD008001C,
            0x3B9978: 0x4BFFC141}.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Saved adaptation evidence changed at {address:#x}")
        keep(address, 4)
    keep(0x3B5AB8, 0x118)
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA v02.00 read-only evidence; behavior-qualified names are not localized option names or gameplay-tested edits. No save writes or native code execution.",
        "initializer": {
            "parent_va": "0x35e110", "subobject_initializer_va": "0x35d9a0",
            "subobject_save_offset": "0x5528", "inner_save_offset": "0x8744",
            "rule": "35E110 passes save+5528 to35D9A0. Inner+321C is save8744; words+14/+18 are cleared and float+1C is initialized from8A1944=1.0."},
        "fields": [
            {"offset": "0x8758", "type": "u32 BE", "display_name": "Adaptation event counter (native)",
             "initializer": 0, "update_va": "0x3b5ab8",
             "rule": "Update routine loads the saved unsigned word and increments it with wrapping32-bit arithmetic when runtime byte5381 is nonzero; the pre-increment count also determines a threshold used against runtime byte5383. Exact event meaning is not yet named."},
            {"offset": "0x875c", "type": "u32 BE", "display_name": "Adaptation gated counter (native)",
             "initializer": 0, "update_va": "0x3b5ab8",
             "rule": "Runtime byte5381 nonzero resets this saved word to0. On the other branch, saved byte114D3 (independently mapped sixaxis_enabled) nonzero permits wrapping32-bit increment; otherwise no increment. This is not proof of a death or playthrough counter."},
            {"offset": "0x8760", "type": "f32 BE", "display_name": "Adaptation modifier (native)",
             "initializer": 1.0, "update_va": "0x3b5ab8",
             "rule": "Native update adds a branch-selected adjustment and uses two fsel operations with0.6 and1.0 bounds. Runtime byte5381 nonzero ultimately stores1.0. Values in snapshots are exposed verbatim, not clamped or normalized."}],
        "update": {
            "va": "0x3b5ab8", "caller_va": "0x3b8bf0", "call_instruction_va": "0x3b9978",
            "saved_pointer_slot_va": "0x8a3554", "saved_pointer": "0x101efb20",
            "runtime_fields": ["0x5381", "0x5383"],
            "runtime_field_scope": "Offsets5381/5383 are relative to the runtime argument, not the save. Their byte-sized observations are distinct from the saved counters.",
            "threshold": "For normal counter values, threshold=4-min(old8758,2). Exact code uses low32-bit arithmetic sign mask: d=wrapping_u32(2-old8758); threshold=wrapping_u32(4-wrapping_u32(old8758+(d if signed32(d)<0 else0))). Extremely large raw counters are not normalized to the normal-domain shortcut.",
            "branches": [
                "Runtime5381 nonzero: increment8758; an intermediate positive adjustment is computed if runtime5383<threshold, but final8760 is forced1.0 and875C is cleared.",
                "Runtime5381 zero and runtime5383>threshold: add float32(-0.05) to8760 and bound the ordered finite result to0.6..1.0.",
                "Runtime5381 zero and runtime5383<=threshold: add0 and bound the ordered finite result to0.6..1.0.",
                "Runtime5381 zero: independently increment875C only if saved sixaxis_enabled114D3 is nonzero."],
            "context_limit": "Caller3B8BF0 dispatches a seven-state runtime machine; Ghidra omits its switch cases. No exact gameplay outcome name for5381/5383 or player-facing difficulty label was established.",
            "constants": {"lower": 0.6000000238418579, "upper": 1.0, "positive_step": 0.10000000149011612, "negative_step": -0.05000000074505806},
            "finite_clamp": "min(max(adjusted_modifier,float32(0.6)),float32(1.0)) for ordered finite input; literal bound representations retained.",
            "nonfinite_scope": "Native fsel is not a general sanitization contract. Inspection preserves rawbits and nonfinite values and does not emulate hardware NaN selection or invent safe edit limits."},
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save size")
        data = path.read_bytes()
        if any(struct.unpack_from(">I", data, i*0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        fields = []
        for field in report["fields"]:
            offset = int(field["offset"], 0)
            bits = struct.unpack_from(">I", data, offset)[0]
            value = struct.unpack_from(">f", data, offset)[0] if field["type"] == "f32 BE" else bits
            fields.append({"offset": field["offset"], "type": field["type"],
                           "raw_hex": data[offset:offset+4].hex().upper(),
                           "unsigned_bits": bits,
                           "value": value if not isinstance(value, float) or math.isfinite(value) else str(value)})
        report["save_observation"] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest().upper(), "fields": fields}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
