"""Exact-build reset-category producer ordering and bounded state dispatch.

Numeric actor predicates and reached publication sites only. No actor/death
labels, native callbacks, original writes or full state-switch simulation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
TABLES = (
    (2, 0x433B0, 0x889FE8, 0x43438, 33, "AA5A064E431AC63F28186D0A4B6254390BF8399E253CC3296116B0DF639A838A"),
    (4, 0x4B9E8, 0x88A120, 0x4BBBC, 103, "154C02ED86CD340582B4E0DC560385969EF41495C0549ADA94645C3040DC9294"),
    (6, 0x54FB0, 0x88A280, 0x550C8, 20, "3A529568A0DCC778D19655839DBC5E4EEA022430DA130CB22DA4B65D3475F2EA"),
)


def uint(value):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("Expected unsigned32-bit raw word")
    return value


def float_gt_gate_preview(cr7_bits, branch_word=0x409D0008):
    """Raw four-bit CR7 branch outcome only; no floating-point/native execution.

    CR field bits are LT8, GT4, EQ2, UN1. BO4 tests BI29 (CR7.GT) for zero
    without using CTR; the +8 taken edge skips li1, preserving initial zero.
    """
    cr7_bits, branch_word = uint(cr7_bits), uint(branch_word)
    if cr7_bits > 15 or branch_word >> 26 != 16 or \
            branch_word >> 21 & 31 != 4 or branch_word >> 16 & 31 != 29 or \
            branch_word & 0xFFFF != 8:
        raise ValueError("Expected CR7 nibble and exact non-linking BO4/BI29/+8 branch")
    tested_mask = 1 << (3 - ((branch_word >> 16 & 31) % 4))
    taken = cr7_bits & tested_mask == 0
    return {"branch_taken": taken, "local_predicate": 0 if taken else 1}


def selector_preview(selector, state, dispatch_state=None, mode=0):
    """Bounded sampled predicates only; helpers/callbacks/timing not emulated.

    Category4 caller has intervening helpers; its later dispatcher state can be
    supplied separately. The category2/6 leaves also reread after publication.
    """
    state, mode = uint(state), uint(mode)
    later = state if dispatch_state is None else uint(dispatch_state)
    if selector == "word_430":
        selected = 2 if BINDINGS["signed"](state, 32) <= 28 else None
        index = later if later <= 32 else None
    elif selector == "word_4a4":
        selected = 4 if state != 2 else None
        index = later if later <= 102 else None
    elif selector == "byte_762":
        if state > 255 or later > 255 or mode > 255:
            raise ValueError("Expected raw byte state/mode")
        selected = 6 if mode == 0 and state != 0 else None
        index = later if selected is not None and later <= 19 else None
    elif selector == "flags_8b0":
        selected = (7 if state & 0x1000 else 3) if state & 0x800 else None
        index = None
    elif selector == "unconditional_5":
        selected, index = 5, None
    else:
        raise ValueError("Unknown bounded selector context")
    return {"selected_category": selected, "dispatch_index": index,
            "scope": "Independent sampled selector/dispatch conditions, not a native invocation or counter increment."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}

    def keep(va, size):
        guards[va] = elf.read(va, size)

    def require(va, expected):
        if elf.u32(va) != expected:
            raise ValueError(f"Reset producer instruction changed at {va:#x}")
        keep(va, 4)

    for va, word in {
        0x68FF68: 0x81230014, 0x68FF6C: 0x80690068,
        0x68FF70: 0x60600020, 0x68FF74: 0x90090068,
        0x43408: 0x815F0430, 0x4340C: 0x2F8A001C,
        0x43410: 0x409D0168, 0x43414: 0x280A0020,
        0x43418: 0x41810118, 0x43584: 0x815F0430,
        0x4BAF4: 0x800804A4, 0x4BAFC: 0x2F800002,
        0x55088: 0x88BF0762, 0x5508C: 0x2F850000,
        0x550A0: 0x881F0762, 0x550A4: 0x28000013,
        0x550A8: 0x4181FFB8,
        0x405E4: 0x38800017, 0x3F0C0: 0x915C0430,
        0x3F0C4: 0x93BC0434,
        0x54F94: 0x3880000E, 0x54FA4: 0x38800001,
        0x53680: 0x9BFE0762, 0x53688: 0x93FE0754,
        0x40548: 0xFF8D0000, 0x4054C: 0x409D0008,
        0x54EE8: 0xFF8D0000, 0x54EEC: 0x409D0008,
        0x2CDC68: 0xD009004C, 0x2CDC6C: 0x90690048,
        0x89F078: 0x101E8D70, 0x89F084: 0x3E800000,
        0x89F098: 0x101EFB20,
    }.items():
        require(va, word)
    # Descriptor-backed whole bodies include exact branch/callback operands.
    for function in (0x433B0, 0x4B9E8, 0x54FB0, 0x18F480, 0x3BFA0,
                     0x40518, 0x54EB8, 0x3EFB8, 0x53490, 0xBF178,
                     0x68FF68, 0x2CDC60):
        end = elf.functions[elf.functions.index(function) + 1]
        keep(function, end - function)
    calls = ((0x433F8, 0x11370), (0x43404, 0x40518), (0x4357C, 0x132D0),
             (0x4BAE4, 0x11370), (0x4BB08, 0x132D0),
             (0x54FD4, 0x11370), (0x54FE0, 0x54EB8), (0x54FE8, 0x4DAA8),
             (0x55098, 0x132D0), (0x18F4B4, 0x132D0), (0x18F4C0, 0xBF178),
             (0x3BFBC, 0x132D0), (0x1137C, 0x68FF68), (0x132DC, 0x2CDC60),
             (0x405E8, 0x3EFB8), (0x54F98, 0x53490), (0x54FA8, 0x53490))
    for va, target in calls:
        if BINDINGS["branch_target"](elf.u32(va), va) != target:
            raise ValueError("Reset producer call chain changed")
        keep(va, 4)
    keep(0x11370, 16); keep(0x132D0, 16)
    dispatch_tables = []
    for category, function, slot, expected_table, count, digest in TABLES:
        table = elf.u32(slot)
        if table != expected_table:
            raise ValueError("Reset producer dispatch table pointer changed")
        raw = elf.read(table, count * 4)
        if hashlib.sha256(raw).hexdigest().upper() != digest:
            raise ValueError("Reset producer dispatch table changed")
        targets = [(table + displacement) & 0xFFFFFFFF for displacement in struct.unpack(">" + str(count) + "i", raw)]
        if any(t % 4 or not 0x10200 <= t < 0x83A50C for t in targets):
            raise ValueError("Invalid state dispatch target")
        keep(slot, 4); keep(table, len(raw))
        dispatch_tables.append({"category": category, "function_va": hex(function),
            "table_pointer_slot_va": hex(slot), "table_va": hex(table), "physical_entries": count,
            "unique_target_count": len(set(targets)),
            "encoding": "Signed BE32 displacement relative to the table VA; repeated targets are retained, not distinct state names.",
            "entries": [{"state": i, "target_va": hex(target)} for i, target in enumerate(targets)]})
    # Follow the same exact virtual context families; neither table addresses nor
    # runtime member numbers supply an actor name.
    contexts = []
    for categories, table, descriptor, function in (
            ([5], 0x842128, 0x85AE20, 0x3BFA0), ([2], 0x842178, 0x85B048, 0x433B0),
            ([4], 0x8421F8, 0x85B218, 0x4B9E8), ([6], 0x842260, 0x85B3D8, 0x54FB0),
            ([3, 7], 0x8482E0, 0x864478, 0x18F480)):
        if elf.u32(table + 0x10) != descriptor or struct.unpack(">II", elf.read(descriptor, 8)) != (function, 0x88FF38):
            raise ValueError("Reset producer virtual context changed")
        keep(table + 0x10, 4); keep(descriptor, 8)
        contexts.append({"categories": categories, "vtable_va": hex(table), "method_offset": "0x10",
                         "descriptor_va": hex(descriptor), "function_va": hex(function), "actor_name": "Unresolved"})
    report = {"confidence": "code-backed numeric producer/dispatch boundaries",
        "storage": {"counter_base": "0x5734", "counter_count": 8,
            "runtime_owner_va": "0x101e8d70", "runtime_category_member": "0x48", "runtime_window_member": "0x4c"},
        "selection_vs_recording": {
            "selector_thunk_va": "0x132d0", "selector_va": "0x2cdc60", "window_literal": 0.25,
            "rule": "Selector overwrites the runtime window+4C with0.25, then runtime category+48 with the supplied ID. It contains no saved-counter increment, reset-request admission call or actor-state write. Repeated qualified callbacks refresh the window; the last supplied category replaces the previous one if these calls return sequentially. Runtime interleaving/atomicity and time units are not established.",
            "recording_boundary": "Only a separate admitted reset request reaches the saved counter writer2CE518. Selecting a category does not itself record a reset, and category names remain unresolved."},
        "common_preselector": {"thunk_va": "0x11370", "function_va": "0x68ff68",
            "rule": "Callbacks for categories2,4,6 first reach68FF68: actor member+14 supplies a runtime entry pointer; its entry+68 flags are ORed with0x20. This is a runtime flag update, not a saved bit or direct reset admission.",
            "scope": "The gameplay meaning of entry flag0x20 and virtual callback frequency are not recovered."},
        "producer_boundaries": [
            {"categories": [2], "function_va": "0x433b0", "selected_member": "0x430",
             "selection": "After11370 and40518, signed actor word430<=28 selects2. The dispatcher then rereads430 and uses an unsigned<=32 bound for its33-entry table.",
             "boundary": "States29..32 bypass selection but remain in the table domain. Raw80000000..FFFFFFFF satisfy the signed selection and then fail the unsigned dispatch bound. Selection is therefore not proof of a recognized state handler or named failure cause.",
             "preselector_state_request": "40518 can request3EFB8(actor,23) before category selection. On the reached setter publication path3F0C0/3F0C4, it stores requested actor430 and zeroes actor434. Caller predicates use actor334, a native float threshold and flags454 bit1000; complete old-state transition effects are not simulated."},
            {"categories": [4], "function_va": "0x4b9e8", "selected_member": "0x4a4",
             "selection": "After11370, initial actor word4A4!=2 selects4. Five following helpers45B28/48520/4AC10/4AA38/4A250 run before the later dispatcher rereads4A4, which is bounded unsigned<=102 for103 entries.",
             "boundary": "The selected state sample and later dispatch sample are separated by helper calls; their equality is not assumed. Out-of-range initial states can select4. No actor/death label or reset-request occurrence follows from this callback alone."},
            {"categories": [6], "function_va": "0x54fb0", "selected_member": "0x762", "mode_member": "0x764",
             "selection": "After11370/54EB8/4DAA8, modebyte764==0 and statebyte762!=0 select6. Only afterward does reloaded762 receive the unsigned<=19 bound for20 dispatch entries.",
             "boundary": "Statebytes20..255 still select6 but bypass the table. State0 and nonzero764 bypass category6 selection. No valid-state, death or failure verdict is inferred.",
             "preselector_state_request": "54EB8 can request53490(actor,1) for prior byte762 in8..11, otherwise14, under its float/flag gates. On reached publication53680/53688 the setter stores low8 requested state to762 and zeroes754; unrelated state-specific callbacks and the full transition machine are not reconstructed."},
            {"categories": [3, 7], "function_va": "0x18f480", "selected_member": "0x8b0",
             "selection": "Flags8B0 bit800 chooses whether to select. If set, bit1000 chooses7 when set, otherwise3. The selector call returns before the commonBF178 call.",
             "boundary": "BF178 itself requires actorbyte5BD==0 for its following runtime virtual callbacks/C59C0. That later gate does not gate the earlier category selection. No cleanup, death or actor-name label is assigned."},
            {"categories": [5], "function_va": "0x3bfa0", "selected_member": None,
             "selection": "Category5 is selected before10550(actor+24) and the resolved object's virtual method+14.",
             "boundary": "Following virtual callback acceptance/side effects and invocation frequency remain unresolved."}],
        "float_gate_caution": "40518/54EB8 initialize their local predicate0, then use fcmpu followed by BO4/BI29/+8: branch when CR7.GT is0, skipping li1. Only ordered greater-than sets predicate1; less/equal/unordered (including NaN) retain0. The bounded helper previews raw CR bits only, not floating-point/native execution, timer units or the full transition gate.",
        "virtual_contexts": contexts, "dispatch_tables": dispatch_tables,
        "unresolved": ["All player-facing category names and actor classes remain unresolved.",
                       "Category1 has physical storage but no newly confirmed selector here.",
                       "Actual invocation frequency/order, runtime state transitions, callback acceptance and current selected context are not derivable from the supplied save."],
        "recommended_annotations": [
            {"va": "0x68ff68", "kind": "function", "name": "TOD_actor_mark_runtime_entry_flag20_before_category_context",
             "comment": "Actor+14 is runtime entry pointer; ORs entry+68 flags with20, used via11370 before category2/4/6 callbacks. No saved-bit write, reset admission or gameplay flag name established."},
            {"va": "0x43438", "kind": "data", "size": 132, "name": "TOD_reset_context2_state_relative_dispatch",
             "comment": "33 signed BE32 offsets relative to43438, states0..32. Signed430<=28 selection precedes unsigned dispatch bound; negative raw states can select2 but reject dispatch. Targets are not gameplay state names."},
            {"va": "0x4bbbc", "kind": "data", "size": 412, "name": "TOD_reset_context4_state_relative_dispatch",
             "comment": "103 signed BE32 offsets relative to4BBBC; dispatcher rereads4A4 after intervening helpers, separately from initial!=2 category4 selection. Repeated targets retained; no actor/death names."},
            {"va": "0x550c8", "kind": "data", "size": 80, "name": "TOD_reset_context6_byte_state_relative_dispatch",
             "comment": "20 signed BE32 offsets relative to550C8. Mode764==0/nonzero762 selection happens before<=19 table bound;20..255select6 but reject table. Runtime actor states, not saved category names."}],
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())],
        "warning": "Producer context is not an event cause/name or a death total. Numeric boundaries are confirmed for USA v02.00 only. No full switch execution, callback invocation, saved edits or gameplay validation."}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Expected verified plaintext size")
        raw = path.read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Expected plaintext inventory IDs0..31")
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(raw).hexdigest().upper(),
            "category_words": list(struct.unpack_from(">8I", raw, 0x5734)),
            "scope": "Saved counters only. Actor predicate words/flags and current runtime category/window are not serialized here; no cause or actor identity is reconstructed."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2))
