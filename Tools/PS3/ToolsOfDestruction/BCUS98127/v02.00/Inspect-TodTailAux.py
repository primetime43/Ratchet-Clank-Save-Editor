"""Read-only exact-build saved segment aggregates and countdown gates; stdout only."""
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
    checks = {
        0x89F07C: 0x101F8264, 0x89F080: 0x101B9EE8,
        0x89F078: 0x101E8D70, 0x89F088: 0x3F800000,
        0x89F090: 0, 0x89F0AC: 0x3DCCCCCD,
        0x89F0B0: 0x10731DA0, 0x89F0B4: 0x10731D00,
        0x2CDBF8: 0x8062F15C, 0x2CDBFC: 0x4E800020,
        0x35E11C: 0x787D0020, 0x35E124: 0x7C7E1B78,
        0x35E198: 0x381E5528, 0x35E1AC: 0x4BFFF7F5,
        0x35D9BC: 0x7C7F1B78, 0x35DB64: 0x393F321C,
        0x35DB70: 0x79280020, 0x35DB84: 0x39400000,
        0x35DBB0: 0x91480004,
        0x35DBB4: 0x91480000,
        0x2CDC18: 0xC0090FD0, 0x2CDC1C: 0xD003000C,
        0x2CDC48: 0xC0090FCC, 0x2CDC4C: 0xD0030008,
        0x2CE450: 0xC082F18C, 0x2CE478: 0xD17B0000,
        0x2CE484: 0xD15B0004, 0x2CE49C: 0xD09C0090,
        0x2CE4A4: 0xD07C0094,
        0x3C04D0: 0x4BF0D729, 0x3C04DC: 0x9083000C,
        0x3C04E0: 0x90830008,
    }
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Saved aggregate/countdown evidence changed at {address:#x}")
        guards[address] = elf.read(address, 4)
    for function in (0x2CDBF8, 0x2CDC00, 0x2CDC30, 0x2CDC78,
                     0x2CDFB0, 0x2CE328, 0x2CE620, 0x69B810):
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    guards[0x24ECB8] = elf.read(0x24ECB8, 16)
    guards[0x3C04D0] = elf.read(0x3C04D0, 0x14)
    if elf.descriptors[0x2CDBF8] != 0x89FF20:
        raise ValueError("Unexpected saved subobject getter TOC")
    pointer = elf.u32(0x89F07C)
    if pointer - 0x101EFB20 != 0x8744:
        raise ValueError("Saved aggregate subobject is outside expected state")
    ratio = struct.unpack(">f", elf.read(0x89F0AC, 4))[0]
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA v02.00 static evidence and detached save observations only. No gameplay-tested edits, native execution, inferred seconds, or localized difficulty/event names.",
        "saved_subobject": {"getter_va": "0x2cdbf8", "getter_toc": "0x89ff20",
            "pointer_slot_va": "0x89f07c", "pointer": "0x101f8264", "save_offset": "0x8744",
            "proof": "Getter loads r2+signed(F15C); descriptor TOC89FF20 resolves89F07C=101F8264, exactly save101EFB20+8744. This is saved state, not a runtime-only aggregate."},
        "fields": [
            {"offset": "0x8744", "type": "f32 BE", "display_name": "Accumulated adjusted segment scalar (native)", "initializer": 0.0,
             "rule": "Finalizer2CE328 adds segment+00 adjusted elapsed when it is at least configured reference+20 timesfloat32(0.1), otherwise adds that reference. Native fsel behavior is retained; the shortcut is only for ordered finite values."},
            {"offset": "0x8748", "type": "f32 BE", "display_name": "Accumulated segment reference scalar (native)", "initializer": 0.0,
             "rule": "The same finalizer adds the current segment configuration+20 to this saved float. Neither aggregate is a segment count or inferred number of seconds."},
            {"offset": "0x874c", "type": "f32 BE", "display_name": "Segment timing gate A remaining (native)", "initializer": None,
             "rule": "Reset callback2CDC30 stores runtime configuration+10FCC here. Update2CE620 advances this saved float through69B810; active segment elapsed updates require this gate and8750 both strictly greater than0 after the helper. Event cause and time unit remain unnamed."},
            {"offset": "0x8750", "type": "f32 BE", "display_name": "Segment timing gate B remaining (native)", "initializer": None,
             "rule": "Reset callback2CDC00 stores runtime configuration+10FD0 here; the same scaled-step countdown and strict-positive elapsed-update gate applies. It is not proof of a death/health/checkpoint field."}],
        "initializer": {"parent_va": "0x35e110", "subobject_va": "0x35d9a0",
            "rule": "35E110 passes save+5528; inner+321C resolves8744. Stores35DBB0/35DBB4 clear8748/8744. The initializer does not explicitly write874C/8750; their current nonzero values are not initialization defaults."},
        "segment_finalization": {"va": "0x2ce328", "threshold_ratio_slot_va": "0x89f0ac", "threshold_ratio": ratio,
            "source": "Existing saved segment+00 adjusted elapsed and runtime segment configuration+20 reference; only a valid, unfinished segment and normal non-reset path reach these stores.",
            "log_copies": [{"record_offset": "0x90", "save_source_offset": "0x8744"},
                           {"record_offset": "0x94", "save_source_offset": "0x8748"}],
            "correction": "Log90/94 were previously described as runtime accumulated values because the helper pointer was unresolved. Their immediate sources are confirmed saved floats8744/8748, copied after accumulation; retained log values need not equal current aggregates."},
        "aggregate_consumer": {"caller_va": "0x2cdfb0", "calculator_va": "0x2cdc78",
            "runtime_pointer_slot_va": "0x89f078", "runtime_pointer": "0x101e8d70",
            "rule": "2CDFB0 loads saved8744/8748, calls2CDC78 and writes its returned scalar to separate runtime101E8D70+00. Calculator uses their difference and a reference/total ratio with runtime configuration bounds. Runtime result is not written back into either saved aggregate and has no confirmed localized difficulty label."},
        "countdown_update": {"va": "0x2ce620", "thunk_va": "0x24ecb8", "helper_va": "0x69b810",
            "context_pointer_slot_va": "0x89f0b0", "context_pointer": "0x10731da0",
            "context_scope": "Context10731DA0 is outside906F0 saved state; its float+4 supplies the scaled step. This is not another newly discovered save field.",
            "rule": "Helper step=float32(scale*context+4), scale1.0 at these call sites. Ordered finite remaining<step: writepositive0 and return1. Otherwise writefloat32(remaining-step) and return0; equality yields0 with return0, not an expiration event return1. Native unordered comparison also follows subtraction, so inspection does not sanitize NaN.",
            "elapsed_gate": "After advancing both gates,2CE620 requires8750>0 and874C>0 before adding runtime delta to segment+00/+04; native pause/reset/validity/completion conditions independently apply.",
            "explicit_clear": {"call_instruction_va": "0x3c04d0", "stores": ["0x3c04dc", "0x3c04e0"],
                "rule": "A runtime state-machine branch calls the saved subobject getter and stores0 at both gates. Its gameplay event/state names are not recovered; no unreachable-case conclusion is taken from Ghidra's omitted switch."}},
        "unresolved": ["Tail906E4 still has no confirmed semantic name.",
            "Countdown reset causes, runtime configuration field names, units and localized player-facing adaptation meaning remain unresolved.",
            "No guarantee that every possible lifecycle preserves accumulated values or gates, and no new editing permission."],
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
            value = struct.unpack_from(">f", data, offset)[0]
            fields.append({"offset": field["offset"], "type": field["type"],
                "raw_hex": data[offset:offset+4].hex().upper(),
                "unsigned_bits": struct.unpack_from(">I", data, offset)[0],
                "value": value if math.isfinite(value) else str(value)})
        report["save_observation"] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest().upper(), "fields": fields,
            "warning": "10.0/300.0 gate observations in the supplied save are snapshots, not defaults or seconds. Retained log entries are not evidence that current zero aggregates are corrupt."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
