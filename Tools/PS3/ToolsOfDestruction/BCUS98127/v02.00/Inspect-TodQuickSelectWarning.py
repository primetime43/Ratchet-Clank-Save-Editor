"""Read-only exact-build quick-select assignment counter and message-latch flow."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))


def word(value, bits=32):
    if type(value) is not int or not 0 <= value < 1 << bits:
        raise ValueError("Expected bounded raw unsigned value")
    return value


def counter_preview(old):
    """26E4C..26E68 store only, before slot/item checks; not a complete call."""
    increment = (word(old) + 1) & 0xFFFFFFFF
    difference = (5 - increment) & 0xFFFFFFFF
    return (increment + (difference if difference & 0x80000000 else 0)) & 0xFFFFFFFF


def assignment_preview(slot, item, definition_present, definition_flags):
    """Selected store decision with supplied post-lookup observations, no lookup."""
    slot, item, flags = map(word, (slot, item, definition_flags))
    if type(definition_present) is not bool:
        raise ValueError("Expected explicit definition presence")
    if slot > 31:
        return {"store": False, "value": None, "reason": "Unsigned slot above31; counter was already updated."}
    if item > 31:
        return {"store": True, "value": 0xFFFFFFFF, "reason": "Unsigned item above31 clears slot, not only rawFFFFFFFF."}
    if not definition_present or flags & 0x1040:
        return {"store": False, "value": None, "reason": "Definition absent or flags1040 reject; no slot store."}
    return {"store": True, "value": item, "reason": "Admitted definition. Direct store, no duplicate-removal call or ownership test in this body."}


def warning_preview(counter_at_test, latch_at_test):
    """Reached full-list gate only; no current eligibility or playback prediction."""
    counter, latch = word(counter_at_test), word(latch_at_test, 8)
    suppressed = latch != 0 and counter > 3
    return {"message_request_id": None if suppressed else 0x126,
            "latch_after_local_store": latch if suppressed else 1,
            "qualification": "Separate reached gate observations. The native request runs before the local latch store; no callback effects, successful playback or full insertion outcome simulated."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}
    checks = {
        0x888624: 0x101EFB20, 0x89550C: 0x101EFB20, 0x8A3BAC: 0x101EFB20,
        0x889594: 0x100035A8, 0x889598: 0x85A698,
        0x85A698: 0x2F108, 0x85A69C: 0x88FF38,
        0x26E2C: 0x83C286EC, 0x26E30: 0x2B04001F, 0x26E38: 0x3D5E0001,
        0x26E48: 0x2B83001F, 0x26E4C: 0x80CA8734, 0x26E54: 0x38860001,
        0x26E58: 0x20A40005, 0x26E5C: 0x7CABFE70, 0x26E60: 0x7CA05838,
        0x26E64: 0x7D240214, 0x26E68: 0x912A8734, 0x26E6C: 0x419D0024,
        0x26E70: 0x57EC103A, 0x26E78: 0x390C0280, 0x26E80: 0x40990030,
        0x26E88: 0x3BA0FFFF, 0x26E8C: 0x93A30004,
        0x26EC0: 0x2C030000, 0x26EC4: 0x4182FFCC, 0x26EC8: 0x80030018,
        0x26ECC: 0x38A01040, 0x26ED4: 0x7C042838, 0x26EE8: 0x4086FFA8,
        0x26EEC: 0x93A30004,
        0x2F1F4: 0xFC20081E, 0x2F1F8: 0xFFE0F81E,
        0x2F200: 0x80610080, 0x2F208: 0x80810080,
        0x2F20C: 0x7C6307B4, 0x2F210: 0x7C8407B4,
        0x1E281C: 0x834255D4, 0x1E2820: 0x3FFA0001,
        0x1E2824: 0x897F8738, 0x1E2828: 0x2C0B0000, 0x1E282C: 0x41820010,
        0x1E2830: 0x837F8734, 0x1E2834: 0x289B0003, 0x1E2838: 0x4185FF70,
        0x1E2844: 0x38600126, 0x1E2860: 0x3B800001, 0x1E2874: 0x9B9F8738,
        0x35E198: 0x381E5528, 0x35D9BC: 0x7C7F1B78,
        0x35DB30: 0x38600007, 0x35DB38: 0x39600000, 0x35DB3C: 0x7C6903A6,
        0x35DB40: 0x39400000, 0x35DB50: 0x7C9F5A14, 0x35DB54: 0x396B0001,
        0x35DB5C: 0x99453211, 0x35DB60: 0x4200FFF0,
        0x35DB7C: 0x3BA00000, 0x35DBEC: 0x39600000,
        0x35DBF0: 0x93BF320C, 0x35DBF4: 0x997F3210,
        0x3CEDA8: 0x82E23C8C, 0x3CEFF4: 0x3F970001,
        0x3CEFFC: 0x3D790001, 0x3CF008: 0x80FC8734, 0x3CF00C: 0x90EB8734,
        0x3CF148: 0x809B0080, 0x3CF150: 0x7B030020, 0x3CF154: 0x636506F0,
        0x13B94: 0x3C420001, 0x13B98: 0x3842FFE8,
    }
    for va, value in checks.items():
        if elf.u32(va) != value:
            raise ValueError(f"Quick-select warning evidence changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    name = elf.string(0x100035A8)
    if name != "set_qs_weapon_in_slot":
        raise ValueError("Quick-select assignment binding changed")
    guards[0x100035A8] = elf.read(0x100035A8, len(name) + 1)
    for va, target, linked in ((0x2F214, 0x26E20, True), (0x26EB8, 0x13B90, True),
                              (0x1E286C, 0x1E06C8, True), (0x35E1AC, 0x35D9A0, True),
                              (0x3CED80, 0x35E110, True), (0x3CF158, 0x252428, True),
                              (0x13B9C, 0x463190, False)):
        raw = elf.u32(va)
        if BINDINGS["branch_target"](raw, va) != target or bool(raw & 1) != linked:
            raise ValueError("Quick-select warning call linkage changed")
        guards[va] = elf.read(va, 4)
    for function, toc in ((0x26E20, 0x88FF38), (0x2F108, 0x88FF38),
                          (0x1E26F0, 0x88FF38), (0x35E110, 0x89FF20),
                          (0x35D9A0, 0x89FF20), (0x3CED40, 0x89FF20)):
        if elf.descriptors[function] != toc:
            raise ValueError("Quick-select warning descriptor TOC changed")
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    guards[0x13B90] = elf.read(0x13B90, 16)
    report = {
        "confidence": "exact-build-native-flow",
        "warning": "USA BCUS98127 v02.00 only; read-only static evidence, no native execution. This is not successful assignment count, lifetime history, current menu eligibility, proof message126 played or edit safety. Original raw values are preserved.",
        "counter": {"offset": "0x8734", "type": "u32 BE", "display_name": "Quick-select warning counter",
                    "rule": "Named set_qs_weapon_in_slot wrapper2F108 calls26E20. Reached26E20 increments saved8734 before applying unsigned slot/item rejection branches; comparison instructions precede this store. For ordinary small values it advances toward5 and remains5. Exact leaf: increment=u32(old+1); d=u32(5-increment); result=u32(increment+(d if signed32(d)<0 else0)). High raw words can exceed5 and FFFFFFFF wraps0. No universal unsigned min or repair."},
        "latch": {"offset": "0x8738", "type": "u8", "display_name": "Quick-select full-list message latch",
                  "rule": "Reached no-slot branch1E26F0 reads8738 as one byte. Zero bypasses the counter read and requests126. Nonzero suppresses the request ONLY when unsigned8734>3; at0..3 it requests again. After normal return from1E06C8, store literal1 to8738 without testing a success result. It does not mean message playback succeeded or an insertion occurred."},
        "named_assignment": {"name": name, "registration_va": "0x889594", "wrapper_va": "0x2F108", "native_va": "0x26E20",
                             "rule": "Wrapper validates/converts arguments before reaching native26E20; the native counter does not count wrapper-rejected calls. Converted slot/item are sign-extended low32 values. Native unsigned slot<=31 admits all32 physical slots, unlike hero automatic insertion's first24. For admitted slot, ANY unsigned item>31 storesFFFFFFFF (clears), not only the -1 sentinel. Item0..31 requires nonnull definition and flags+18&1040==0 before storing directly to284+4*slot. No duplicate-removal call or saved ownership check exists in this complete native body; failed admission leaves the slot unchanged despite prior counter update.",
                             "lookup_thunk": "13B90 changes TOC88FF38 to89FF20 and tail-branches463190. Runtime definition lookup and callback effects are not reconstructed from saved IDs."},
        "full_list_context": "The warning leaf is reached only after the earlier item/definition, player-state, membership and first24 empty-slot tests in1E26F0. Occurrence anywhere among32 words suppresses automatic insertion before this branch. Latch/counter samples alone do not prove a full list, current warning eligibility or active player index. Native126 is a request ID, not recovered localized warning text.",
        "initialization": "35E110 passes input+5528 to35D9A0. Literal-zero stw+320C resolves saved8734; stb+3210 resolves8738. A separate seven-byte loop at+3211..3217 explicitly zeros8739..873F. Those seven neighbors remain semantically opaque, not proven padding. Initializer stores are not proof every load resets these fields or that a zero latch means never requested.",
        "restart": "Guarded selective restart3CED40 initializes its private staging bank, then explicitly copies old canonical live8734 into staging8734 at3CF008/00C. The fixed preservation list includes only those four bytes at8734, not latch8738 or neighbors8739..873F. Later3CF158 copies the full906F0-byte staging bank to live state. The explicit init/copy boundaries differ for counter and latch; surrounding helper/callback effects and final post-callback state are not simulated. This does not establish every restart mode's behavior.",
        "recommended_annotations": [
            {"va": "0x26e68", "kind": "comment", "name": "TOD_quick_select_warning_counter_before_validation", "comment": "Named set_qs_weapon_in_slot reaches26E20: store saved8734 update before slot/item validation. Low32 signed-difference cap selects5 only on one arithmetic branch; high words not universal min. Not successful assignments."},
            {"va": "0x26e8c", "kind": "comment", "name": "TOD_quick_select_direct_invalid_item_clear", "comment": "After unsigned slot<=31, any unsigned item>31 writesFFFFFFFF to saved284+4*slot. All32 slots admitted; not hero automatic first24. Counter8734 already updated; not only -1 clear and no duplicate compaction."},
            {"va": "0x1e2838", "kind": "comment", "name": "TOD_quick_select_warning_repeat_gate", "comment": "Full first24/no-membership warning path: nonzero byte8738 AND unsigned8734>3 suppress native126 request. Zero latch skips count read; count<=3 repeats even with set latch. Not current eligibility/playback proof."},
            {"va": "0x1e2874", "kind": "comment", "name": "TOD_quick_select_warning_latch_after_request", "comment": "Store literal1 to saved BYTE8738 after normal return from1E06C8 native126 request, with no success-result test. Does not rescue insertion; bytes8739..873F are distinct opaque storage."},
            {"va": "0x3cf00c", "kind": "comment", "name": "TOD_quick_select_warning_counter_restart_preservation", "comment": "Selective restart explicitly copies old live8734 into initialized private staging bank. This four-byte preserve excludes8738 and opaque8739..873F; initialization explicitly zeros those bytes. No final callback-state or every-mode verdict."},
        ],
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())],
    }
    if save_path is not None:
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not verified plaintext save layout")
        report["save_observation"] = {
            "plaintext_sha256": hashlib.sha256(raw).hexdigest().upper(),
            "counter": struct.unpack_from(">I", raw, 0x8734)[0], "latch_byte": raw[0x8738],
            "opaque_neighbors_hex": raw[0x8739:0x8740].hex().upper(),
            "qualification": "Raw snapshot only, not assignment history, message success, current list admission or initialization defaults."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
