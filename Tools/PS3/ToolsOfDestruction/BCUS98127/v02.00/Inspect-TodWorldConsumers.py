"""Exact-build segment validity, configuration remapping and lifecycle gates.

Reads only the fingerprinted ELF and an optional detached plaintext snapshot.
Decision previews require explicit caller-supplied runtime validity; that runtime
table is not reconstructed from saved flags or retained log strings.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))


def lifecycle_gate_preview(complete_byte, restart_word, runtime_slot_valid):
    """Predicate-only preview for ordinary physical slots, not game execution."""
    if type(complete_byte) is not int or not 0 <= complete_byte <= 255:
        raise ValueError("Completion must be an unsigned byte")
    if type(restart_word) is not int or not 0 <= restart_word <= 0xFFFFFFFF:
        raise ValueError("Restart value must be an unsigned word")
    if type(runtime_slot_valid) is not bool:
        raise ValueError("Runtime validity must be explicitly boolean")
    normal_valid = restart_word == 0 and runtime_slot_valid
    changed = complete_byte == 0
    return {
        "completion_would_change": changed,
        "completion_result_byte": 1 if changed else complete_byte,
        "finalizer_called_by_completion": changed,
        "finalizer_passes_segment_gates": changed and normal_valid,
        "reset_passes_segment_gates": normal_valid,
        "tick_passes_segment_gates": changed and normal_valid,
        "warning": "Predicate gates only. Tick has additional saved-timer and runtime-context conditions. No timer arithmetic, log append, notification, native code or save write is executed.",
    }


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}
    checks = {
        0x2CDBC0: 0x5465103A, 0x2CDBC4: 0x8162F158,
        0x2CDBC8: 0x38850020, 0x2CDBD0: 0x7C0B482E,
        0x2CDBD4: 0x2F80FFFF, 0x2CDBD8: 0x419E0010,
        0x2CDBDC: 0x78630020, 0x2CDBE8: 0x3860FFFF,
        0x2CDEE4: 0x7FE9182E, 0x2CDEE8: 0x2F9FFFFF,
        0x2CDEEC: 0x419E0038, 0x2CDF20: 0x3966EA24,
        0x2CDF50: 0x4BFFFC71, 0x2CDF58: 0x2F83FFFF,
        0x2CDF60: 0x419E0034, 0x2CDF6C: 0x57E83032,
        0x2CDF78: 0x57EA2036, 0x2CDF90: 0x38090488,
        0x2D14E8: 0x54683032, 0x2D14EC: 0x546A2036,
        0x2D1520: 0x3BA30488, 0x2D1618: 0x881F002C,
        0x2D1620: 0x419E0028, 0x2D1648: 0x4BFFCCE1,
        0x2D1658: 0x9B9F002C, 0x2CE554: 0x4800330D,
        0x2CE580: 0x4BFFF9C1, 0x2CE584: 0x2C830000,
        0x2CE5A0: 0x80830008, 0x2CE5A4: 0x38040001,
        0x2CE5B0: 0x90030008, 0x2CE5B4: 0x91230004,
        0x2CE5B8: 0xD1A30000, 0x2CE640: 0x48003221,
        0x2CE6E8: 0x4BFFF859, 0x2CE708: 0x897F002C,
        0x2CE710: 0x4086FF44, 0x2CE350: 0x48003511,
        0x2CE398: 0x4BFFFBA9, 0x2CE3A8: 0x8863002C,
        0x2CE3B4: 0x4086FFB8, 0x2D186C: 0x800906EC,
        0x89F078: 0x101E8D70, 0x89F098: 0x101EFB20,
        0x89F188: 0x101EFB20, 0x8A1984: 0x101EFB20,
    }
    for va, expected in checks.items():
        if elf.u32(va) != expected:
            raise ValueError(f"Segment consumer shape changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    functions = (0x2CDBC0, 0x2CDEC0, 0x2CDF40, 0x2D14E0, 0x2D15C8,
                 0x2CE518, 0x2CE620, 0x2CE328, 0x2D1490, 0x2D1860)
    for va in functions:
        end = elf.functions[elf.functions.index(va) + 1]
        guards[va] = elf.read(va, end - va)
        if elf.descriptors[va] != 0x89FF20:
            raise ValueError("Segment consumer TOC changed")
    # Validate the reset leaf's complete load/store footprint: there is no saved
    # +2C completion test anywhere in this hash-verified function. This does not
    # make a claim about callers or unrelated game paths.
    if any(w >> 26 == 34 and w & 65535 == 0x2C
           for _, w in elf.instructions(0x2CE518, 0x2CE5CC)):
        raise ValueError("Reset completion-byte footprint changed")
    bindings = []
    for slot, name, wrapper in ((0x89D960, "complete_segment", 0x2C8A18),
                               (0x89D968, "is_segment_complete", 0x2C8950)):
        name_va, descriptor = struct.unpack(">II", elf.read(slot, 8))
        if elf.string(name_va) != name or elf.u32(descriptor) != wrapper:
            raise ValueError("Named segment binding changed")
        for va, size in ((slot, 8), (descriptor, 8), (name_va, len(name) + 1)):
            guards[va] = elf.read(va, size)
        bindings.append({"name": name, "registration_slot_va": hex(slot), "wrapper_va": hex(wrapper)})
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA v02.00 static consumer relationships only. No saved field renamed, safe edit range inferred, native game code executed or runtime slot table reconstructed.",
        "storage": {"world_base": "0x488", "world_stride": "0x408", "physical_world_slots": 20,
                    "segment_stride": "0x30", "segments_per_world": 10, "completion_member": "0x2c",
                    "restart_word_offset": "0x906ec", "log_count_offset": "0x10144"},
        "runtime_mapping": {
            "pointer_slot_va": "0x89f078", "runtime_owner_va": "0x101e8d70",
            "member": "0x20", "word_stride": 4, "absent_word": "0xffffffff",
            "validity_function_va": "0x2cdbc0", "saved_getter_va": "0x2cdf40",
            "raw_saved_getter_va": "0x2d14e0", "config_getter_va": "0x2cdec0",
            "saved_rule": "2CDBC0 tests runtime[20+4*requested_slot] against -1, but returns the requested slot itself, not the table value. 2CDF40 returns null for absent mapping; otherwise saved+488+current_world*408+requested_slot*30. Raw2D14E0 performs the saved address calculation without this runtime mapping gate.",
            "configuration_rule": "2CDEC0 instead uses the runtime table value as a configuration record index: runtime configuration root+EA24+current_world*1E0+mapped_index*30. These runtime records are not saved segment records; a remapped configuration index does not reorder GAME.SAV slots.",
            "bounds_scope": "These guarded leaves do not establish a 0..9 input-range check. Preview and snapshot reads stay inside the 200 physical saved records; no unsafe malformed-index address is reproduced.",
        },
        "lifecycle": {
            "completion": {"function_va": "0x2d15c8", "flag_store_va": "0x2d1658",
                "rule": "Raw requested saved-slot byte2C is tested first. Nonzero returns0 without calling finalizer or replacing the byte. Zero calls2CE328 then writes1 and returns1, even when finalizer skipped because replay word is nonzero or runtime mapping absent. Runtime checkpoint mask+44 updates separately before that byte test.",
                "scope": "A newly set completion flag is not evidence of a log append, timer reset, reward commit or reconstructed active runtime configuration."},
            "finalization": {"function_va": "0x2ce328", "rule": "Requires restart906EC==0, runtime mapping present through2CDF40, and saved byte2C==0 before incrementing log count and storing scalar/timing entries. No completion-byte store is made by this leaf; the caller performs it afterward."},
            "tick": {"function_va": "0x2ce620", "rule": "Saved segment elapsed updates require restart906EC==0, two saved timing gates, runtime mapping present and saved byte2C==0. Additional runtime context matters; completion-byte clearance alone does not predict elapsed changes."},
            "reset": {"function_va": "0x2ce518", "counter_store_va": "0x2ce5b0",
                "rule": "For the selected runtime slot, restart906EC==0 and runtime mapping present suffice for this leaf's saved segment writes. It does not test byte2C: increments BE32+8 modulo32, clears+4, and stores adjusted+0 using current-attempt+4 times runtime config10FC8 plus previous+0. Completed records are therefore not inherently frozen against this reset consumer. Category-bank increment precedes restart gate and is documented separately.",
                "scope": "Does not prove the game actually calls reset after completion or reveal reset cause/time units. Full leaf coverage, not a global no-reader claim."},
            "preview_scope": "Explicit runtime validity is a preview argument, not obtained from GAME.SAV. Tick/finalizer gate success does not execute any log/timer write or promise native side effects.",
        },
        "opaque_members": {"segment_word28": "Unresolved; no new semantic consumer established.",
                           "segment_tail2d_2f": "Unresolved; existing initializer footprint does not prove padding.",
                           "world_tail404_407": "Unresolved. Immediate-address candidates do not by themselves prove this saved-record owner; no absence of all consumers is claimed."},
        "named_bindings": bindings,
        "recommended_annotations": [
            {"va": "0x2cdbc0", "name": "segment_runtime_mapping_validity", "kind": "function",
             "comment": "Tests runtime mapping word20+4*requested_slot against -1, returning requested slot itself or -1. Table value is not returned and no normal-slot bounds check is established."},
            {"va": "0x2cdf40", "name": "segment_saved_pointer_if_runtime_mapped", "kind": "function",
             "comment": "Uses2CDBC0 for runtime mapping validity only; saved offset remains requested_slot*30, current_world*408, plus488. Does not substitute mapped config index."},
            {"va": "0x2cdec0", "name": "segment_runtime_config_from_mapping", "kind": "function",
             "comment": "Uses runtime mapping table value as configuration index; runtime root+EA24+current_world*1E0+mapped_index*30. Distinct from saved-record addressing."},
        ],
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())],
    }
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save layout")
        data = path.read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        restart = struct.unpack_from(">I", data, 0x906EC)[0]
        records = []
        for world in range(20):
            for slot in range(10):
                offset = 0x488 + world * 0x408 + slot * 0x30
                records.append({"world_id": world, "slot": slot, "offset": hex(offset),
                                "complete_byte": data[offset + 0x2C],
                                "reset_events_bits": data[offset + 8:offset + 12].hex().upper(),
                                "opaque_word28_hex": data[offset + 0x28:offset + 0x2C].hex().upper(),
                                "opaque_tail_hex": data[offset + 0x2D:offset + 0x30].hex().upper()})
        report["save_observation"] = {
            "plaintext_sha256": hashlib.sha256(data).hexdigest().upper(), "restart_word": restart,
            "log_count": struct.unpack_from(">I", data, 0x10144)[0], "segments": records,
            "world_tail_hex": [data[0x488+i*0x408+0x404:0x488+(i+1)*0x408].hex().upper() for i in range(20)],
            "qualification": "Runtime validity/mapping table is absent from the snapshot. Nonzero restart makes the proven segment tick/reset/finalizer gates fail, not the raw completion setter. No current call, completion history or timer unit is inferred.",
        }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path, help="Detached plaintext working copy only; never modified")
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
