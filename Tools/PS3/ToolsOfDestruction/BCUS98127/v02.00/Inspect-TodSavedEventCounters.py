"""Exact-build saved event counters, bounded consumers and bonus-target restoration.

Read-only static evidence. Counter event names and in-game acceptance remain unknown.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))


def word(value):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("Expected raw unsigned32 word")
    return value


def increment_preview(total, qualified, handle_admitted):
    """Reached suffix only; admission supplied, not derived from a private save."""
    total, qualified = word(total), word(qualified)
    if type(handle_admitted) is not bool:
        raise ValueError("Expected explicit boolean handle admission")
    return ((total + 1) & 0xFFFFFFFF,
            (qualified + int(handle_admitted)) & 0xFFFFFFFF)


def scaling_preview(count, offset):
    """Finite nearest-even fmadds reference, not live FPSCR/config reconstruction."""
    count = word(count)
    if type(offset) is not int or offset not in (0x872C, 0x8730):
        raise ValueError("Unknown saved counter")
    cap, bits = (5, 0x3E19999A) if offset == 0x872C else (3, 0xBDCCCCCD)
    step = 0 if count <= 2 else min(count - 2, cap)
    slope = struct.unpack(">f", struct.pack(">I", bits))[0]
    # Small integer steps times this binary32 literal plus1 are exact in binary64;
    # one final binary32 rounding corresponds to the guarded finite fused operation.
    factor = struct.unpack(">f", struct.pack(">f", 1.0 + step * slope))[0]
    return {"step": step, "factor": factor,
            "qualification": "Nearest-even finite reference only. Not current runtime parameters, global difficulty, event identity or edit safety."}


def registration_preview(progress, pending, next_index):
    """362C20 leaf only. Runtime indices wrap; PPC slw uses low six count bits."""
    progress, pending, index = map(word, (progress, pending, next_index))
    effective = index & 63
    bit = 1 << effective if effective < 32 else 0
    admitted = not bool(progress & bit)
    return {"assigned_index": index, "next_index": (index + 1) & 0xFFFFFFFF,
            "effective_bit": bit, "admitted": admitted,
            "pending_after_store": pending | bit if admitted else pending,
            "saved_progress": progress,
            "qualification": "Runtime registration leaf only; no saved target identity or total recovered. Zero shift bit still returns true. Caller375C48 replaces a rejected assigned index with FFFFFFFF."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    expected = {
        0x8A1AC4: 0x101EFB20, 0x8A1C70: 0x101EFB20,
        0x8A1C40: 0x10027BE0, 0x8A1C44: 0x10027BC0, 0x8A1C48: 0x1064FC80,
        0x8A1C80: 0x3E19999A, 0x8A1C28: 0x3F800000, 0x8A1C58: 0,
        0x8A1FE4: 0x101EFB20, 0x8A2038: 0x101EFB20, 0x8A2128: 0x101EFB20,
        0x8A1FE8: 0xBDCCCCCD, 0x8A206C: 0xBDCCCCCD, 0x8A212C: 0xBDCCCCCD,
        0x8A1F48: 0x3F800000, 0x8A2020: 0x3F800000, 0x8A20BC: 0x3F800000,
        0x362C28: 0x80A3011C, 0x362C2C: 0x3D670001, 0x362C30: 0x39450001,
        0x362C34: 0x7CC82830, 0x362C38: 0x9143011C, 0x362C3C: 0x90A40324,
        0x362C40: 0x800B8728, 0x362C48: 0x7D090038, 0x362C50: 0x40820014,
        0x362C54: 0x818300FC, 0x362C5C: 0x7D046378, 0x362C60: 0x908300FC,
        0x375C64: 0x3BC0FFFF, 0x375C70: 0x93DF0324, 0x375C90: 0x5469063E,
        0x375C98: 0x2F890000, 0x375CA4: 0x409E0024, 0x375CA8: 0x93DF0324,
        0x36C650: 0x80C21D50, 0x36C658: 0x3CE60001, 0x36C668: 0x8087872C,
        0x36C670: 0x3BA40001, 0x36C674: 0x80660010, 0x36C678: 0x93A7872C,
        0x36C67C: 0xE93F03B0, 0x36C680: 0x7D204038, 0x36C684: 0x7C082C36,
        0x36C688: 0x551F043E, 0x36C68C: 0x7C03F840, 0x36C690: 0x57FE482C,
        0x36C694: 0x57EC3830, 0x36C698: 0x7C0CF050, 0x36C69C: 0x4180003C,
        0x36C6AC: 0x808A0064, 0x36C6B0: 0x7FA44050, 0x36C6B4: 0x7D282050,
        0x36C6B8: 0x7D20EB78, 0x36C6BC: 0x7C1FFE70, 0x36C6C0: 0x7CBEF878,
        0x36C6C4: 0x2C9E0000, 0x36C6C8: 0x41860010, 0x36C6CC: 0x80C78730,
        0x36C6D0: 0x39060001, 0x36C6D4: 0x91078730,
        0x36F8BC: 0xC3DB02C4, 0x36F8C0: 0xC0221D38, 0x36F8C4: 0xFC9E0800,
        0x36F8C8: 0x4CC43382, 0x36F8CC: 0x4186040C,
        0x36ABEC: 0x8177872C, 0x36ABF0: 0x2B8B0002, 0x36ABF4: 0x409D0308,
        0x36AC00: 0x23670004, 0x36AC10: 0x39630001, 0x36AC50: 0xEDA2E8FA,
        0x379FC0: 0x81698730, 0x379FC4: 0x2B8B0002, 0x379FC8: 0x419D0730,
        0x37CDF0: 0x83A220F4, 0x37CDDC: 0x81698730, 0x37CDE0: 0x2B8B0002,
        0x37CDE4: 0x419D06EC, 0x37D4D8: 0x23BE0002, 0x37D54C: 0xED8DE83A,
        0x380FB8: 0x81698730, 0x380FBC: 0x2B8B0002, 0x380FC0: 0x419D0718,
        0x3816E0: 0x239D0002, 0x381754: 0xED8DE83A,
        0x489FF0: 0x939D8730, 0x489FF4: 0x939D8728, 0x489FF8: 0x939D872C,
    }
    guards = {}
    for address, value in expected.items():
        if elf.u32(address) != value:
            raise ValueError(f"Saved event evidence changed at {address:#x}")
        guards[address] = elf.read(address, 4)
    for address, target in ((0x375C84, 0x362C20), (0x36FCEC, 0x36C578),
                            (0x36C648, 0x24F4F8)):
        raw = elf.u32(address)
        if BINDINGS["branch_target"](raw, address) != target or not raw & 1:
            raise ValueError("Saved event call changed")
        guards[address] = elf.read(address, 4)
    for function in (0x362C20, 0x375C48, 0x36A908, 0x36C578, 0x36F6A0,
                     0x379F60, 0x37CD88, 0x380F60, 0x489F68):
        if elf.descriptors[function] != 0x89FF20:
            raise ValueError("Saved event TOC changed")
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    report = {
        "confidence": "exact-build-native-flow",
        "warning": "USA BCUS98127 v02.00 only. Event identities are unresolved: not proven deaths, kills, attempts, global difficulty or lifetime statistics. Native code is not executed; no edit safety or current runtime state inferred.",
        "fields": [
            {"offset": "0x872C", "type": "u32 BE", "display_name": "Saved event counter",
             "rule": "Reached suffix36C578 increments saved872C once with low32 wrapping before resolving runtime actor+3B0 handle. Earlier native helpers/callbacks run first. This counter does not require the later handle admission; it is not a bitmask."},
            {"offset": "0x8730", "type": "u32 BE", "display_name": "Handle-qualified event counter",
             "rule": "The same reached suffix increments saved8730 once with low32 wrapping only when the extracted runtime handle admits a nonzero pool record under the native slot/identity test. Not a bitmask or proof of a named gameplay event. Neither counter is guaranteed less than the other after wrapping/reset."},
        ],
        "handle_gate": "TOC8A1C40/44 point to runtime mask/shift banks10027BE0/10027BC0;8A1C48 points to runtime pool1064FC80. Mask and srd extract from actor+3B0. Slot is low16; unsigned limit at pool+10 admits slot<=limit, NOT slot<limit. Record address is pool base+slot*180, truncated for the identity read at+64. The native signed-low32 difference/OR selects only a low32 identity match, then requires nonzero low32 selected pointer. Actual banks, handle, pool bounds and identity are not serialized in these counters. No speculative pool memory reads or broad edit admission are simulated.",
        "caller_gate": "Selected caller36F6A0 compares runtime+2C4 with literal zero; ordered <= takes36FCD8, calls361F60(owner,0), then36C578. Earlier runtime gates/callbacks remain significant. Unordered does not take this <= branch. Scalar role and gameplay cause remain unnamed; this is not a universal death/kill counter proof.",
        "scaling": {
            "0x872C": {"consumer": "0x36A908", "slope_bits": "3E19999A", "step_cap": 5,
                       "rule": "Unsigned count<=2 selects1.0; otherwise step=min(count-2,5), factor=fmadds(float(step),float32(0.15),1). This scales a runtime config-derived parameter via252748; not a saved multiplier or global difficulty setting."},
            "0x8730": {"consumers": ["0x379F60", "0x37CD88", "0x380F60"], "slope_bits": "BDCCCCCD", "step_cap": 3,
                       "rule": "Unsigned count<=2 selects1.0; otherwise step=min(count-2,3), factor=fmadds(float(step),float32(-0.1),1). Three selected setup bodies multiply config-derived runtime fields by this factor. Current definitions, final callback results and a universal combat-difficulty meaning are not inferred."},
            "preview_limit": "Finite small-step nearest-even arithmetic only; live FPSCR rounding and current runtime parameters are unknown."},
        "registration": "Native362C20 always consumes old owner+11C index, stores incremented low32 back and assigns old index to target+324. It tests slw(1,index) against saved8728. If set, return0 without pending OR; otherwise OR into runtime owner+FC and return1. Saved progress is not modified. Counts32..63 select zero and still return1;64 aliases0. These are raw instruction cases, not known legitimate target indices or counts.",
        "restoration_caller": "375C48 starts with target+324=FFFFFFFF, runs384758, then calls362C20. A zero low-byte result replaces the assigned index withFFFFFFFF and returns before the explicit type5 request. Nonzero retains the assigned index and follows that request. No saved identity, physical target location or successful request outcome is recovered.",
        "reset": "Previously confirmed489F68 clears8730,8728,872C after2CDBB0 and before465DC0. Counter event names, all reset causes and surrounding callback effects remain unverified. Snapshot zero is not absence of past events.",
        "recommended_annotations": [
            {"va": "0x362c40", "kind": "comment", "name": "TOD_bonus_target_restore_saved_bit_test", "comment": "362C20 consumes runtime index+11C and assigns target+324 before testing saved8728. Set bit returns0 without pending OR; clear/zero bit returns1 and ORs runtime+FC. Saved progress unchanged; no target identity/count."},
            {"va": "0x375ca8", "kind": "comment", "name": "TOD_bonus_target_restore_rejected_sentinel", "comment": "Zero low-byte result from362C20 restores raw FFFFFFFF to target+324 and returns before explicit type5 request. Previously recorded bit prevents pending registration; not proof request/gameplay success."},
            {"va": "0x36c678", "kind": "comment", "name": "TOD_saved_event_counter_wrapping_increment", "comment": "Reached36C578 suffix stores old saved872C+1 low32 before runtime handle resolution. Earlier helpers/callbacks precede this. BE32 counter, not mask; event identity/death/kill meaning unconfirmed."},
            {"va": "0x36c6d4", "kind": "comment", "name": "TOD_saved_handle_qualified_counter_increment", "comment": "Store saved8730+1 low32 only after runtime handle slot<=limit, low32 record identity match and nonzero selected pointer. Counter wraps; runtime handle/pool not saved here. Event identity unknown."},
            {"va": "0x36ac50", "kind": "comment", "name": "TOD_saved_event_counter_bounded_scaling", "comment": "Saved872C unsigned count<=2 factor1; otherwise min(count-2,5)*float32(0.15)+1 via fmadds. Runtime parameter scaling only; not global difficulty or edit safety."},
            {"va": "0x37d54c", "kind": "comment", "name": "TOD_saved_qualified_counter_bounded_scaling", "comment": "Saved8730 unsigned count<=2 factor1; otherwise min(count-2,3)*float32(-0.1)+1 via fmadds. Shared selected setup behavior in379F60/37CD88/380F60; not a named gameplay event or global difficulty."},
        ],
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())],
    }
    if save_path is not None:
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not verified plaintext save layout")
        report["save_observation"] = {
            "plaintext_sha256": hashlib.sha256(raw).hexdigest().upper(),
            "raw_words": {hex(o): struct.unpack_from(">I", raw, o)[0] for o in (0x8728, 0x872C, 0x8730)},
            "qualification": "Raw snapshot only. No prior event totals, live handle admission, active pending set or current scaling inferred."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
