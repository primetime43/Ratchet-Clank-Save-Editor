"""Exact-build read-only ownership, script-visible ammo/level and removal-leaf boundaries."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
CAPACITY = runpy.run_path(str(Path(__file__).with_name("Inspect-TodAmmoCapacity.py")))


def byte(value):
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError("Expected explicit unsigned saved byte")
    return value


def query_preview(ownership, definition_flags, stored_level, ammo_bits):
    """Explicit detached fields/definition flags only; not a current script invocation."""
    ownership, stored_level = byte(ownership), byte(stored_level)
    definition_flags, ammo_bits = CAPACITY["word"](definition_flags), CAPACITY["word"](ammo_bits)
    visible = (ownership != 0 or bool(definition_flags & 2)) and not definition_flags & 1
    if visible:
        ammo = CAPACITY["finite_bits"](ammo_bits)
        if abs(ammo) > 0x7FFFFFFF:
            raise ValueError("Finite getter projection limited to magnitude<=7FFFFFFF")
        returned_ammo = math.floor(ammo)
    else:
        returned_ammo = 0
    return {"ownership_predicate": ownership != 0, "ammo_level_visible": bool(visible),
            "script_ammo_reference": returned_ammo, "script_level_reference": stored_level+1 if visible else 0,
            "qualification": "Explicit supplied valid-record fields and definition flags only. Bounded finite FLOOR reference, signed-zero identity/FPSCR/nonfinite conversion unmodeled. No live definition, Lua conversion, current eligibility, capacity check or mutation inferred."}


def removal_request_plan(ownership, post_helper_counter_bits):
    """Selected local requests/stores; counter sample is AFTER both setter calls."""
    ownership, post_helper_counter_bits = byte(ownership), CAPACITY["word"](post_helper_counter_bits)
    selected = ownership != 0
    return {"setter_requests": ["XP+0", "absolute ammo+0"] if selected else [],
            "explicit_ownership_store": 0 if selected else None,
            "explicit_counter_store_bits": f"{(post_helper_counter_bits-1) & 0xFFFFFFFF:08X}" if selected else None,
            "qualification": "Leaf466AE8 only, valid supplied inventory-shaped base/index. Counter is an explicit post-helper sample, not the saved snapshot's guaranteed next value. No established caller, exact final XP/level/ammo, callback effects, ownership history or editor-safe removal."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    expected = {
        0x888624: 0x101EFB20, 0x89F1B8: 0x101EFB20,
        0x897B38: 0x101EFB20, 0x23E744: 0x913F1A68,
        0x88865C: 0, 0x888644: 0x3F800000, 0x8A5F0C: 0,
        0x2D1C24: 0x38850010, 0x2D1C2C: 0x7C0918AE,
        0x2D1C30: 0x2F800000, 0x2D1C34: 0x419E0008, 0x2D1C38: 0x39600001,
        0x258F8: 0x881D0010, 0x25908: 0x546807BC,
        0x25910: 0x40820044, 0x25954: 0x546A07FE,
        0x2595C: 0x4086FFB8, 0x25964: 0xC17D0008,
        0x25978: 0xFC205E5E, 0x2597C: 0xFC200E9C,
        0x25980: 0xFDA15828, 0x25984: 0xFD811028,
        0x25988: 0xFC0B606E, 0x2598C: 0xFC2D02EE,
        0x25990: 0xFDA06850, 0x25994: 0xFC2D006E,
        0x27640: 0x881D0010, 0x27650: 0x546807BC,
        0x27658: 0x40820024, 0x2767C: 0x546A07FE,
        0x27684: 0x4086FFD8, 0x27688: 0x897D0011, 0x27690: 0x386B0001,
        0x28B184: 0x419D014C, 0x28B194: 0x4BFEBBB5,
        0x28B1B8: 0x388000B9, 0x28B1E8: 0x38800211,
        0x28B254: 0x81651A68, 0x28B25C: 0x4186FFA8,
        0x28B27C: 0x7D0B50AE, 0x28B280: 0x2F080000,
        0x28B28C: 0x38600001, 0x28B2F0: 0x4BFFFE98,
        0x466AF4: 0xC0225FEC, 0x466B1C: 0x881F0010,
        0x466B24: 0x419E0030, 0x466B34: 0xC0225FEC,
        0x466B44: 0x995F0010, 0x466B48: 0x811E0280,
        0x466B4C: 0x3928FFFF, 0x466B50: 0x913E0280,
        0x874B00: 0x466AE8, 0x874B04: 0x89FF20,
    }
    guards = {}
    for va, raw in expected.items():
        if elf.u32(va) != raw:
            raise ValueError(f"Inventory query evidence changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    calls = {0x33FF8: 0x25AF0, 0x25AFC: 0x12950,
             0x258D8: 0x13B90, 0x27620: 0x13B90,
             0x2BB5C0: 0x28B160, 0x466B28: 0x4660A8, 0x466B38: 0x465DC0,
             0x28B2E8: 0x24F9D8, 0x28B2C0: 0x24F9D8}
    for va, target in calls.items():
        raw = elf.u32(va)
        if raw >> 26 != 18 or not raw & 1 or BINDINGS["branch_target"](raw, va) != target:
            raise ValueError("Inventory query call changed")
        guards[va] = elf.read(va, 4)
    for thunk, target in ((0x12950, 0x2D1C10), (0x13B90, 0x463190)):
        if [elf.u32(thunk+i) for i in (0, 4, 8)] != [0xF8410028, 0x3C420001, 0x3842FFE8]:
            raise ValueError("Inventory query TOC adjustment changed")
        raw = elf.u32(thunk+12)
        if raw & 1 or BINDINGS["branch_target"](raw, thunk+12) != target:
            raise ValueError("Inventory query thunk changed")
        guards[thunk] = elf.read(thunk, 16)
    named = []
    for slot, name, wrapper in ((0x8892F4, "is_weapon_owned", 0x33F40),
                                (0x88930C, "get_weapon_ammo", 0x33C80),
                                (0x88931C, "get_weapon_level", 0x33A98),
                                (0x89DEB8, "hero_has_weapon", 0x2BB4B0)):
        pointer, descriptor = elf.u32(slot), elf.u32(slot+4)
        if elf.string(pointer) != name or elf.u32(descriptor) != wrapper or elf.u32(descriptor+4) != elf.descriptors[wrapper]:
            raise ValueError("Named inventory registration changed")
        for va, size in ((slot, 8), (pointer, len(name)+1), (descriptor, 8)):
            guards[va] = elf.read(va, size)
        named.append({"name": name, "slot_va": hex(slot), "wrapper_va": hex(wrapper)})
    for function, toc in [(f, 0x88FF38) for f in (0x33F40, 0x33C80, 0x33A98, 0x25AF0, 0x258C0, 0x27608, 0x23E650)] + [
            (f, 0x89FF20) for f in (0x2D1C10, 0x2BB4B0, 0x28B160, 0x466AE8, 0x4660A8, 0x465DC0)]:
        if elf.descriptors[function] != toc:
            raise ValueError("Inventory query function TOC changed")
        guards[function] = elf.read(function, elf.functions[elf.functions.index(function)+1]-function)
    # A static census is a boundary, not proof that native code is dead or unreachable.
    descriptor_refs, branch_sites = [], []
    for start, offset, size in elf.segments:
        for index, (raw,) in enumerate(struct.iter_unpack(">I", elf.raw[offset:offset+size//4*4])):
            va = start+4*index
            if raw == 0x874B00:
                descriptor_refs.append(hex(va))
            if start == 0x10000 and va >= 0x10200 and raw >> 26 == 18 and BINDINGS["branch_target"](raw, va) == 0x466AE8:
                branch_sites.append(hex(va))
    report = {
        "confidence": "exact-build-named-queries-and-qualified-removal-leaf",
        "warning": "USA BCUS98127 v02.00 only. Static read-only reference, not full inventory usability, native execution, removal reachability or new editing permission.",
        "named_apis": named,
        "ownership": "Named is_weapon_owned33F40->25AF0->12950->2D1C10 reads canonical saved20*ID+10 through89F1B8=101EFB20 and returns normalized0/1 for zero/ANY nonzero byte. It does not resolve definitions, inspect flags, ammo, level or capacity. No local ID bound is established. Wrapper returns1 as Lua RESULT COUNT after pushing the predicate, not always true ownership.",
        "visible_attributes": "Named get_weapon_ammo33C80->258C0 and get_weapon_level33A98->27608 resolve definition through13B90->463190. They expose attributes only if (saved ownership nonzero OR definition flag2) AND definition flag1 clear; otherwise both return0 locally. Thus owned can be true while visible attributes are0, or owned false while flag2 exposes them. No capacity, stored-level range or playable-weapon validation is performed by these gates. Valid record/definition pointers, matching ID and current definition flags remain necessary; viewing does not infer them from a save.",
        "ammo_rounding": "258C0 exposes FLOOR(saved ammo) for bounded ordinary finite inputs through FCTIDZ/FCFID and FSEL around1.0. It is not nearest rounding, ceiling, clamping to0/capacity or a store back to the record. Negative fractional ammo floors farther negative; positive fractional ammo remains raw in GAME.SAV even when the named numeric getter returns a lower integer. Nonfinite/out-of-range conversion and FPSCR/signed-zero identity remain unmodeled. This differs from2FF6C0's later CEILING local request after the crate add.",
        "level_numbering": "27608 returns raw unsigned stored-level byte+1 only after the visibility gate. Stored0 becomes script1; stored9 becomes10; raw255 becomes256 in this arithmetic, not a valid level or accepted edit. The inspector retains the original zero-based byte and does not replace it with this getter result.",
        "handle_ownership": "Named hero_has_weapon2BB4B0->28B160, on a valid resolved handle/type211/non-null hero+1A68 path, normalizes the selected saved ownership byte without applying the ammo/level definition gates. The native method resolves the handle repeatedly rather than caching one stable object. Its unsigned ID>31, missing handle and initial typeB9 diagnostic branches call24F9D8 then CONTINUE; they are not independently proven safe rejection or terminal assertions. Later type211/nonnull-save gates do return0. Wrapper validation/conversion, diagnostics, helper mutations and full invalid-handle behavior remain unmodeled; Lua1 is result count after pushing its predicate.",
        "removal_leaf": {"va": "0x466ae8", "ordered_rule": "For a valid supplied inventory-shaped base/index, complete466AE8 samples record+10: zero skips both setter calls and its explicit stores. ANY nonzero calls4660A8 with XP+0, then465DC0 with absolute ammo+0, then explicitly stores ownership0. Only AFTER both helpers and that byte store does it load base+280 and publish wrapping low32(counter-1). No local underflow clamp; post-helper sample0 becomesFFFFFFFF. Setter calls can alter XP/level/ammo and other callback state; requests are not a raw first18-byte reset or guaranteed final level/ammo0.",
            "scope": "Only direct leaf stores target ownership+10 and counter+280. No direct modifier-mask, unlock, quick-select or opaque-tail store occurs here; called helpers' complete effects are not thereby ruled out. Descriptor874B00 exists but this survey found no aligned file-backed references to it and no direct executable branch to466AE8. No caller or gameplay invocation is established; this does not prove unused/dead code or authorize removal. Counter arithmetic must use a supplied post-helper sample, not promise the snapshot's next value.",
            "static_descriptor_references": descriptor_refs, "static_direct_branch_sites": branch_sites},
        "snapshot_limit": "Raw ownership, ammo and stored level are separate saved facts. Current definition flags, active handles, native query results and removal history are not recovered. Acquisition counter is not repaired to the number of owned records; the qualified leaf can decrement it if invoked, but its gameplay use is unresolved. Inspection never floors ammo in storage, renumbers levels, clears ownership or changes counters.",
        "recommended_annotations": [
            {"va": "0x25978", "kind": "comment", "name": "TOD_weapon_ammo_visible_finite_floor_not_saved_mutation", "comment": "Visible attribute gate (ownership!=0 OR flags2) AND !flags1. FCTIDZ/FCFID/FSEL select FLOOR for bounded finite saved ammo, not ceiling, lower/max clamp or raw ammo store. Nonfinite/FPSCR unmodeled."},
            {"va": "0x27690", "kind": "comment", "name": "TOD_weapon_level_script_one_based_after_visibility_gate", "comment": "Returns saved unsigned byte+1 only after (ownership!=0 OR flags2) AND !flags1; raw255 arithmetic256, not level validity or save normalization. Hidden branch0."},
            {"va": "0x2d1c10", "name": "TOD_weapon_saved_ownership_nonzero_predicate", "comment": "Named is_weapon_owned leaf: canonical saved20*ID+10 through89F1B8; normalizes ANY nonzero byte to1 without definition/ammo/level/capacity checks. No local ID bound."},
            {"va": "0x466ae8", "name": "TOD_inventory_removal_leaf_requests_then_owner_clear_counter_decrement", "comment": "Owned nonzero: XP+0 setter, absolute ammo+0 setter, owner0 store, THEN reread base280 and wrap decrement. Owner0 skips. No observed static caller/descriptor reference; not established gameplay removal or exact helper final state."},
        ],
        "instruction_guards": [{"va": hex(a), "bytes": raw.hex().upper()} for a, raw in sorted(guards.items())],
    }
    if save_path is not None:
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i*20)[0] != i for i in range(32)):
            raise ValueError("Not verified plaintext inventory layout")
        report["save_observation"] = {"sha256": hashlib.sha256(raw).hexdigest().upper(),
            "raw_acquisition_counter_bits": raw[0x280:0x284].hex().upper(),
            "nonzero_ownership_records": sum(raw[i*20+16] != 0 for i in range(32)),
            "records": [{"id": i, "ownership": raw[i*20+16], "stored_level": raw[i*20+17],
                         "ammo_bits": raw[i*20+8:i*20+12].hex().upper(), "opaque_tail": raw[i*20+18:i*20+20].hex().upper()} for i in range(32)],
            "qualification": report["snapshot_limit"]}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
