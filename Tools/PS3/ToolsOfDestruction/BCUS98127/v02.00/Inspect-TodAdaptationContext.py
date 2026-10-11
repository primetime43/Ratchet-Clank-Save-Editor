"""Read-only Decryptor outcome context and saved spark-speed multiplier bindings."""
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

    def function(address):
        end = elf.functions[elf.functions.index(address)+1]
        keep(address, end-address)
        return end

    expected_words = {
        0x8A364C: 0x3B8C74, 0x8A3554: 0x101EFB20,
        0x8A365C: 0x10027170, 0x8A3664: 0x10027190, 0x8A3668: 0x100271B0,
        0x3B8C44: 0x2B800006, 0x3B8C58: 0x8162372C,
        0x3B8C60: 0x7CC9582E, 0x3B8C64: 0x7CC507B4, 0x3B8C68: 0x7C655A14,
        0x3B9978: 0x4BFFC141, 0x3B997C: 0x881A5381, 0x3B9984: 0x419A0258,
        0x3B99AC: 0x3880038A, 0x3B9C2C: 0x3880038B,
        0x3B9590: 0xC0D58760, 0x3B9594: 0xC0FA51DC,
        0x3B9598: 0xECA601F2, 0x3B959C: 0xD0BA51D8,
        0x3B9CB0: 0x394C0001, 0x3B9CB4: 0x995A5383,
        0x3B9E90: 0x39690001, 0x3B9E94: 0x9ABA5381, 0x3B9E98: 0x997A5383,
        0x3B9ECC: 0x9BDA5381,
        0x89E688: 0x1001B670, 0x89E68C: 0x86B688,
        0x86B688: 0x2A7A28, 0x86B68C: 0x89FF20,
        0x2A7B1C: 0x4BFE6B5D, 0x28E708: 0xD3E651DC,
    }
    for address, value in expected_words.items():
        if elf.u32(address) != value:
            raise ValueError(f"Decryptor context evidence changed at {address:#x}")
        keep(address, 4)
    if elf.descriptors[0x3B8BF0] != 0x89FF20:
        raise ValueError("Unexpected Decryptor caller TOC")
    caller_end = function(0x3B8BF0)
    if caller_end != 0x3BA168:
        raise ValueError("Unexpected bounded caller extent")
    table = elf.u32(0x8A364C)
    targets = [table+d for d in struct.unpack(">7i", elf.read(table, 28))]
    expected_targets = [0x3B8DFC, 0x3B9694, 0x3B93A8, 0x3B9190, 0x3B9144, 0x3B8F68, 0x3B8E6C]
    if targets != expected_targets or any(not 0x3B8BF0 <= t < caller_end or table <= t < table+28 for t in targets):
        raise ValueError("Invalid native seven-state jump table")
    keep(table, 28)
    function(0x2A7A28)
    function(0x28E678)
    function(0x3B5AB8)
    function(0x3B6860)
    helpers = []
    for slot, address, text in [
            (0x8A365C, 0x10027170, "decryptor basics(with sixaxis)"),
            (0x8A3664, 0x10027190, "decryptor basics(with sticks)"),
            (0x8A3668, 0x100271B0, "decryptor [holding X stabalizes ball]")]:
        if elf.string(address) != text:
            raise ValueError("Decryptor native help identifier changed")
        keep(address, len(text)+1)
        helpers.append({"slot_va": hex(slot), "name_va": hex(address), "native_text": text})
    if elf.string(0x1001B670) != "dc_set_spark_speed":
        raise ValueError("Named spark-speed API changed")
    keep(0x1001B670, len("dc_set_spark_speed")+1)
    tags = []
    for name, name_va, slot, number, load in [
            ("GEN_TXT_GPLAY_DECRYPTSTART", 0x1000D440, 0x88D058, 0x389, 0x85774),
            ("GEN_TXT_GPLAY_DECRYPTWIN", 0x1000D460, 0x88D060, 0x38A, 0x85788),
            ("GEN_TXT_GPLAY_DECRYPTLOSE", 0x1000D480, 0x88D068, 0x38B, 0x8579C),
            ("GEN_TXT_GPLAY_DECRYPTTKO", 0x1000D4A0, 0x88D070, 0x38C, 0x857B0)]:
        name_load, float_load, call = struct.unpack(">III", elf.read(load, 12))
        if (elf.string(name_va) != name or elf.u32(slot) != name_va or
                struct.unpack(">f", elf.read(slot+4, 4))[0] != number or
                name_load != 0x80820000 | ((slot-0x88FF38)&0xFFFF) or
                float_load != 0xC0220000 | ((slot+4-0x88FF38)&0xFFFF) or
                BINDINGS.branch_target(call, load+8) != 0x12990):
            raise ValueError("Native named Decryptor tag export changed")
        keep(slot, 8)
        keep(load, 12)
        keep(name_va, len(name)+1)
        tags.append({"name": name, "id": number, "id_hex": hex(number), "name_va": hex(name_va),
                     "export_slot_va": hex(slot), "export_load_va": hex(load), "export_call_va": hex(load+8)})
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA v02.00 native Decryptor context. Labels describe the traced save-update path, not universal lifetime statistics, gameplay-tested edits, or global combat difficulty. Runtime members are not saved fields.",
        "named_context": {"name": "Decryptor minigame", "caller_va": "0x3b8bf0", "caller_end_exclusive": "0x3ba168",
                          "proof": "Three native help strings identify Decryptor; independently exported START/WIN/LOSE tags identify outcome branches after the saved-word updater.",
                          "help_strings": helpers, "named_tags": tags},
        "seven_state_dispatch": {"runtime_member": "0x20", "entry_latch_member": "0x28", "table_pointer_slot_va": "0x8a364c",
                                 "table_va": hex(table), "count": 7, "entry_type": "signed32 relative to table base",
                                 "states": [{"index": i, "case_va": hex(t)} for i, t in enumerate(targets)],
                                 "rule": "Unsigned state>6 exits; state0..6 loads signed32 table[state] and branches to table+displacement. Indices are runtime-only, not save status or named state enums.",
                                 "analysis_caveat": "Ghidra's original function body omits orphaned switch cases. Bounded raw table/case bytes are authoritative; disposable-session disassembly expansion was discarded without changing the original ELF or persistent project."},
        "runtime_outcomes": {"success_flag_member": "0x5381", "retry_byte_member": "0x5383", "updater_call_va": "0x3b9978",
                             "flag_branch_va": "0x3b9984", "win_tag_load_va": "0x3b99ac", "lose_tag_load_va": "0x3b9c2c",
                             "rule": "After3B5AB8, runtime5381 nonzero selects named DECRYPTWIN; zero selects DECRYPTLOSE branch. This establishes Decryptor success/loss context for the independently mapped save arithmetic.",
                             "writes": "Result helper3B7CD8 return1 leads3B9ECC storing1 in5381. Return2 leads3B9CAC clearing5381 and incrementing5383. Another failure path3B9E94 clears5381 and increments5383. Byte stores wrap modulo256; these are runtime observations, not another saved counter.",
                             "scope": "Cancel/give-up and other result-helper outcomes exist. The retry byte's full lifecycle is not claimed as a universal attempt total."},
        "saved_fields": [
            {"offset": "0x8758", "type": "u32 BE", "display_name": "Decryptor wins (native)",
             "rule": "Incremented by the traced success branch, wrapping32; the same outcome flag selects DECRYPTWIN. This labels the retained native counter, not a guarantee of all-time wins across resets or every gameplay path."},
            {"offset": "0x875c", "type": "u32 BE", "display_name": "Decryptor SIXAXIS losses (native)",
             "rule": "The traced loss branch increments only when saved sixaxis_enabled114D3 is nonzero; success clears it. It is a gated since-success loss counter, not a generic death count or all Decryptor attempts."},
            {"offset": "0x8760", "type": "f32 BE", "display_name": "Decryptor spark-speed multiplier",
             "rule": "3B9590..959C multiplies this saved float by runtime51DC, stores runtime51D8. Named dc_set_spark_speed sets runtime51DC, proving specific spark-speed scaling rather than a general combat-difficulty modifier. Existing save_aux_fields documents native finite0.6..1 clamp and success reset1.0; raw snapshots are not normalized."}],
        "spark_speed_binding": {"script_name": "dc_set_spark_speed", "registration_va": "0x89e688", "name_va": "0x1001b670",
                                "wrapper_descriptor_va": "0x86b688", "wrapper_va": "0x2a7a28", "callee_va": "0x28e678",
                                "wrapper_call_va": "0x2a7b1c", "base_store_va": "0x28e708", "base_runtime_member": "0x51dc",
                                "scaled_runtime_member": "0x51d8", "saved_multiplier_load_va": "0x3b9590", "multiply_va": "0x3b9598",
                                "scaled_store_va": "0x3b959c", "scope": "Script-controlled base speed is a runtime member, not an additional save float; physical units and every downstream motion effect remain unverified."},
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save size")
        data = path.read_bytes()
        if any(struct.unpack_from(">I", data, i*0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        fields = []
        for f in report["saved_fields"]:
            offset = int(f["offset"], 0)
            value = struct.unpack_from(">f" if f["type"] == "f32 BE" else ">I", data, offset)[0]
            fields.append({"offset": f["offset"], "display_name": f["display_name"], "raw_hex": data[offset:offset+4].hex().upper(),
                           "value": value if not isinstance(value, float) or math.isfinite(value) else str(value)})
        report["save_observation"] = {"sha256": hashlib.sha256(data).hexdigest().upper(), "size": len(data), "fields": fields,
                                      "sixaxis_raw_hex": data[0x114D3:0x114D4].hex().upper(),
                                      "interpretation_limit": "This snapshot exposes retained native words only; zero counters do not prove the minigame was never played or map runtime flags."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
