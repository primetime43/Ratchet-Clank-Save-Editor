"""Exact-build weapon purchase routing and saved level-five admission.

Read-only static evidence. Previews use explicit immutable supplied inputs;
they do not resolve definitions, execute callbacks or certify safe edits.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))


def uint(value, maximum=0xFFFFFFFF):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("Expected bounded raw unsigned integer")
    return value


def level_five_gate_preview(ownership, stored_level, replay_word, definition_flags, num_levels):
    """The gate only, assuming resolved native definitions and matching record ID."""
    uint(ownership, 255); uint(stored_level, 255)
    for value in (replay_word, definition_flags, num_levels):
        uint(value)
    conditions = [("nonzero ownership", ownership != 0),
                  ("stored level above3", stored_level > 3),
                  ("stored level not above4", stored_level <= 4),
                  ("low definition flag bits clear", definition_flags & 3 == 0),
                  ("nonzero saved replay word", replay_word != 0),
                  ("definition num_levels above5", num_levels > 5)]
    return {"gate": all(ok for _, ok in conditions),
            "failed_conditions": [name for name, ok in conditions if not ok],
            "qualification": "Supplied snapshot gate only. Definition/ID/pointer validity, current caller samples, price, funds, callbacks and gameplay acceptance are not inferred."}


def route_preview(first_gate_byte, transaction_gate_byte):
    """Two independent low-byte samples; assumes a hero reaches the second gate."""
    uint(first_gate_byte, 255); uint(transaction_gate_byte, 255)
    extended = first_gate_byte != 0
    return {"selected_path": "level-five" if extended else "normal acquisition",
            "second_gate_evaluated": extended,
            "level_five_gate_admitted": extended and transaction_gate_byte != 0,
            "fallback_after_second_gate_failure": False,
            "qualification": "Routing/recheck only, not purchase success. Normal ID19 gating, funds and definition/hero safety remain separate."}


def signed_funds_preview(wallet_bits, cost_bits):
    uint(wallet_bits); uint(cost_bits)
    wallet = BINDINGS["signed"](wallet_bits, 32)
    cost = BINDINGS["signed"](cost_bits, 32)
    return {"signed_wallet": wallet, "signed_cost": cost,
            "funds_comparison_admits": wallet >= cost,
            "negated_cost_low32": (-cost_bits) & 0xFFFFFFFF,
            "qualification": "Comparison and captured-cost negation only, not an executed debit, valid shipped price or purchase permission."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}
    def keep(va, size=4):
        guards[va] = elf.read(va, size)
    words = {
        0x89F1B8: 0x101EFB20, 0x89F188: 0x101EFB20,
        0x2D20CC: 0x8162F298, 0x2D20FC: 0x881F0010,
        0x2D2104: 0x409E0024, 0x2D213C: 0x4182FFCC,
        0x2D2158: 0x4086FFB0, 0x2D216C: 0x419AFF9C,
        0x2D2184: 0x419EFF84, 0x2D2190: 0x28030005,
        0x2D2198: 0x4081FF74,
        0x465CC0: 0x88030011, 0x465CC8: 0x2B800003,
        0x465CE0: 0x88030011, 0x465CE8: 0x2B800004,
        0x463280: 0x80830018, 0x463288: 0x548007BE,
        0x463218: 0x80690460, 0x2D186C: 0x800906EC,
        0x2D1870: 0x2F800000, 0x2D1874: 0x419E0008,
        0x26654: 0x5460063E, 0x26660: 0x419E0028,
        0x265F4: 0x419E001C, 0x2D21EC: 0x5463063E,
        0x2D21F4: 0x40820034, 0x2D223C: 0x8003041C,
        0x2D2240: 0x7F00E000, 0x2D2244: 0x4198FFB4,
        0x2D2264: 0x7CBC00D0, 0x2D22B8: 0x38600001,
        0x2D1FE8: 0x816906B0, 0x2D2090: 0x2C840000,
        0x2D2098: 0x800B06A8, 0x2D20B8: 0x800B06AC,
        0x465EAC: 0x80090460, 0x465EB0: 0x2B800004,
        0x465ED4: 0x98DF0011, 0x465ED8: 0xC0090244,
        0x465EDC: 0xD01F0004,
        0x2D2D70: 0x2C1D0013, 0x2D2DA4: 0x7F80E000,
        0x2D2DE0: 0x38A00001, 0x2D2E04: 0x7CDC00D0,
        0x2D2E74: 0x3880000B, 0x2D2E88: 0x4186FEF0,
        0x466C28: 0x4BFFF161, 0x466C38: 0x409AFFB4,
        0x466C4C: 0x995F0010, 0x466CF8: 0x93BC0280,
        0x465DA8: 0xD03D0008, 0xB4A54: 0x80A90008,
        0x33880: 0xFC20081E, 0x338A8: 0x38600001,
    }
    for va, expected in words.items():
        if elf.u32(va) != expected:
            raise ValueError(f"Weapon purchase evidence changed at {va:#x}")
        keep(va)
    calls = {
        0x13EBC: 0x2D20C8, 0x1134C: 0x2D21A8,
        0x1201C: 0x2D2D38, 0x119EC: 0x2D24C0,
        0x2664C: 0x13EB0, 0x26664: 0x11340, 0x2668C: 0x12010,
        0x265DC: 0x119E0, 0x26610: 0x13EB0,
        0x33890: 0x26638, 0x338A0: 0x106A0, 0x33F20: 0x265C8,
        0x2D2128: 0x465CC0, 0x2D2140: 0x465CE0,
        0x2D215C: 0x463270, 0x2D2170: 0x2D1860, 0x2D2188: 0x4631F8,
        0x2D21CC: 0x24FB88, 0x2D21E8: 0x2D20C8,
        0x2D2230: 0x2D1FA8, 0x2D225C: 0x465E78,
        0x2D2270: 0x24FCB8, 0x2D22B0: 0x250FA8,
        0x465EE0: 0x463DE0, 0x465F00: 0x465E18,
        0x2D2D94: 0x2D2058, 0x2D2DE8: 0x466B70,
        0x2D2DFC: 0x252B08, 0x2D2E10: 0x24FCB8,
        0x2D2E28: 0x35D358, 0x2D2E3C: 0x250FA8,
        0x2D2E78: 0x24F7B8, 0x466C50: 0x4660A8,
    }
    for va, target in calls.items():
        if BINDINGS["branch_target"](elf.u32(va), va) != target:
            raise ValueError(f"Weapon purchase target changed at {va:#x}")
        keep(va)
    for function in (0x337D8, 0x33E68, 0x265C8, 0x26638, 0x2D20C8,
                     0x2D21A8, 0x2D1FA8, 0x2D2058, 0x2D24C0, 0x2D2D38,
                     0x465CC0, 0x465CE0, 0x463270, 0x4631F8, 0x2D1860,
                     0x465E78, 0x465D88, 0x465E18, 0x466B70, 0xB4A10):
        keep(function, elf.functions[elf.functions.index(function) + 1] - function)
    for thunk in (0x13EB0, 0x11340, 0x12010, 0x119E0):
        keep(thunk, 16)
    bindings = []
    for slot, name, wrapper in ((0x889334, "purchase_weapon", 0x337D8),
                                (0x8892FC, "is_weapon_available", 0x33E68)):
        name_va, descriptor = struct.unpack(">II", elf.read(slot, 8))
        if elf.string(name_va) != name or elf.u32(descriptor) != wrapper:
            raise ValueError("Named weapon purchase binding changed")
        keep(slot, 8); keep(name_va, len(name) + 1); keep(descriptor, 8)
        bindings.append({"name": name, "slot_va": hex(slot), "wrapper_va": hex(wrapper)})
    report = {
        "confidence": "code-backed purchase routing, saved-state admission and publication order",
        "warning": "Exact USA BCUS98127 v02.00 static evidence only. No native/Lua execution, runtime definition reconstruction, pointer/index safety, purchase simulation or newly editable field.",
        "saved_fields": {"ownership_member": "0x10", "stored_level_member": "0x11", "xp_member": "0x4", "ammo_member": "0x8",
                         "record_stride": "0x14", "bolts_offset": "0x41c", "replay_offset": "0x906ec", "acquisition_counter_offset": "0x280"},
        "level_five_gate": {"va": "0x2d20c8", "global_saved_root_slot_va": "0x89f1b8", "global_saved_root_va": "0x101efb20",
            "ordered_checks": ["record ownership byte nonzero", "465CC0: stored level>3", "465CE0: stored level must NOT be>4", "463270: definition flags&3==0", "2D1860: saved replay906EC!=0", "4631F8: definition num_levels unsigned>5"],
            "rule": "The two level tests together require exactly stored level4, not any level>=4 or5. Nonzero replay accepts any raw32 word, including high-bit values; it is not a new challenge-mode boolean or a local counter bound. Definitions/pointers and matching record-ID assumptions remain necessary.",
            "contrast": "The bridge helper465E78 alone admits definition num_levels>4. The purchase gate requires>5; num_levels5 would satisfy the leaf bridge condition but fail this purchase gate."},
        "routing": {"purchase_dispatch_va": "0x26638", "availability_dispatch_va": "0x265c8",
            "purchase_rule": "26638 samples the low byte of2D20C8 first. Nonzero selects2D21A8; zero selects normal2D2D38, not automatic rejection.2D21A8 requires a hero then samples2D20C8 again. If the second gate fails it returns0 without falling back to normal purchase. Samples need not agree; caller routing is not atomic admission.",
            "availability_rule": "Named is_weapon_available goes through265C8: normal2D24C0 is checked first, returning1 when nonzero; only otherwise is2D20C8 evaluated. This union is distinct from the purchase dispatch order and is not itself a wallet or full vendor eligibility check.",
            "lua_boundary": "Named purchase_weapon converts admitted numeric argument1 with fctiwz/low32 signed extension, calls26638, pushes its low-byte boolean via106A0 and returns1 as Lua RESULT COUNT. Invalid-ID/conversion and validation-helper internals are not emulated."},
        "level_five_transaction": {"va": "0x2d21a8", "price_va": "0x2d1fa8", "price_field": "Vendor.MegaPrice, definition data+6B0",
            "price_rule": "2D1FA8 returns raw unsigned data+6B0 when config/data exists and flags&3==0, otherwise0 locally. The previously mapped vendor schema names this MegaPrice; no localized Omega name or safe zero-price validity contract is inferred.",
            "order": ["hero lookup", "repeat level-five gate", "capture MegaPrice", "signed32 saved bolts>=signed32 captured cost", "465E78 stores level5 then XP from threshold5(+244), then adds new maximum ammo through465E18", "negate captured cost low32 and update bolts24FCB8", "qualified hero subsystem virtual+1C callback", "runtime request4 via250FA8, ignore its return, return1"],
            "local_write_scope": "Bridge writes level/XP/ammo, not local ownership, unlock, modifier mask or acquisition-counter stores. Later helpers/callbacks remain qualified; this is not a promise that all other fields remain unchanged through the full runtime transaction. There is no local rollback/atomicity guarantee.",
            "funds_rule": "Both purchase branches use signed32 comparisons. High-bit wallets/costs are not large legitimate unsigned funds. Captured-cost negation and hero wallet mutation are not a universal subtract-with-lower-clamp contract."},
        "normal_transaction": {"va": "0x2d2d38", "price_va": "0x2d2058",
            "price_rule": "Definition flag2 chooses AmmoPrice(+6AC); otherwise BasePrice(+6A8). Missing config/data yields0 locally, not a safe invalid-definition API contract.",
            "admission": "Requires hero. Item19 additionally must have low-byte24F7B8(hero,11)==0. Then signed saved bolts must be>=signed captured price. The leaf does not invoke normal availability/unlock or independently reject an already-owned item.",
            "order": ["capture definition/price and compare signed funds", "466B70 acquire with refill1", "252B08 hero inventory integration(item,-1)", "24FCB8 captured-cost debit", "qualified virtual callback for low definition flags clear", "35D358 checkpoint ammo merge", "250FA8 runtime request4; return1"],
            "repeat_scope": "Repeated normal calls can charge an already-owned record. Acquisition can refill before its ownership test; already-owned records skip the local ownership/XP initialization and acquisition-counter increment. This does not establish gameplay exploitability, universal refill or preservation across later callbacks.",
            "special_id19": "The additional numeric11 predicate is explicitly recorded without naming its unresolved runtime meaning. It is not an invented saved availability byte."},
        "named_bindings": bindings,
        "recommended_annotations": [
            {"va": "0x2d20c8", "name": "TOD_level_five_purchase_gate_verified", "kind": "function", "comment": "Global save ownership nonzero, stored level exactly4 (separate>3 and NOT>4 tests), definition flags&3 clear, saved906EC nonzero, num_levels unsigned>5. Not funds/full vendor eligibility; raw replay nonzero is not a new mode-bound contract."},
            {"va": "0x26638", "name": "TOD_purchase_weapon_dispatch_and_recheck_boundary_verified", "kind": "function", "comment": "Low-byte2D20C8 true selects2D21A8; false selects normal2D2D38, not rejection. Extended transaction separately requires hero and rechecks gate; failure there returns0 without normal fallback. Definition/callback samples not proven atomic."},
            {"va": "0x2d21a8", "name": "TOD_purchase_weapon_level_five_publication_before_payment_verified", "kind": "function", "comment": "Hero+repeat2D20C8 gate, captureMegaPrice, signed32 bolt admission.465E78 stores level5/threshold5 XP then additive ammo path before captured-cost debit. Qualified virtual callback and request4 afterward; no atomicity/rollback or new safe-edit claim."},
            {"va": "0x265c8", "name": "TOD_weapon_availability_normal_or_level_five_verified", "kind": "function", "comment": "Checks normal2D24C0 first; nonzero returns1, else samples2D20C8 low byte. Named availability is OR of two predicates, distinct from purchase routing and absent local wallet test."}],
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())],
    }
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Expected detached plaintext save size")
        raw = path.read_bytes()
        if any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Expected plaintext record IDs0..31")
        replay, bolts, acquisition = (struct.unpack_from(">I", raw, o)[0] for o in (0x906EC, 0x41C, 0x280))
        report["save_observation"] = {"sha256": hashlib.sha256(raw).hexdigest().upper(), "replay_word": replay,
            "bolts_bits": f"{bolts:08X}", "acquisition_counter": acquisition,
            "records": [{"id": i, "ownership_byte": raw[i * 20 + 16], "stored_level": raw[i * 20 + 17],
                         "stored_necessary_gate_passes": raw[i * 20 + 16] != 0 and raw[i * 20 + 17] == 4 and replay != 0,
                         "xp_hex": raw[i * 20 + 4:i * 20 + 8].hex().upper(), "ammo_hex": raw[i * 20 + 8:i * 20 + 12].hex().upper()} for i in range(32)],
            "qualification": "Stored necessary conditions only. Runtime definition flags/count/prices and independent caller samples are not reconstructed. No purchase is executed or editing range inferred."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2))
