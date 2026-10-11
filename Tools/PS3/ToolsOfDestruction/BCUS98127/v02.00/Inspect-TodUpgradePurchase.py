"""Read-only exact-build upgrade admission, mask/ammo publication and debit order.

Previews require explicit synthetic inputs and resolved maxima/cost. They do not
execute native/Lua code, resolve pointers, mutate saves or certify valid edits.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct

BASE = Path(__file__).resolve().parent
BINDINGS = runpy.run_path(str(BASE / "Inspect-TodWeaponBindings.py"))
CURRENCY = runpy.run_path(str(BASE / "Inspect-TodCurrencyMutation.py"))
LUA = runpy.run_path(str(BINDINGS["ROOT"] / "Tools/Inspect-Lua50.py"))
MASK = 0xFFFFFFFF


def uint(value, maximum=MASK):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("Expected bounded unsigned integer")
    return value


def purchase_admission_preview(hero_present, ownership_byte, wallet_bits, cost_bits):
    """Only the three local transaction gates, assuming valid resolved pointers."""
    if type(hero_present) is not bool:
        raise ValueError("Hero presence must be an explicit boolean")
    uint(ownership_byte, 255)
    uint(wallet_bits)
    uint(cost_bits)
    signed_wallet, signed_cost = BINDINGS["signed"](wallet_bits, 32), BINDINGS["signed"](cost_bits, 32)
    admitted = hero_present and signed_wallet >= signed_cost and ownership_byte != 0
    delta = (-cost_bits) & MASK
    return {"local_admission": admitted, "signed_wallet": signed_wallet, "signed_cost": signed_cost,
            "debit_delta_bits": delta if admitted else None,
            "wallet_leaf_bits": CURRENCY["hero_wallet_preview"](wallet_bits, delta)["wallet_bits"] if admitted else None,
            "warning": "Local gates and callback-free wallet leaf only, with explicit synthetic resolved cost. No node validity, adjacency, duplicate-bit prevention, pointer/hero safety, definition lookup, callbacks or gameplay acceptance is simulated."}


def modifier_publication_preview(mask_bits, node, old_max_bits, new_max_bits):
    """Bit OR and fcmpu non-equality branch for already resolved float32 maxima."""
    uint(mask_bits)
    uint(node, 31)
    uint(old_max_bits)
    uint(new_max_bits)
    old_max = struct.unpack(">f", old_max_bits.to_bytes(4, "big"))[0]
    new_max = struct.unpack(">f", new_max_bits.to_bytes(4, "big"))[0]
    unordered = math.isnan(old_max) or math.isnan(new_max)
    return {"new_mask_bits": mask_bits | (1 << node), "already_set": bool(mask_bits & (1 << node)),
            "ammo_store_branch": unordered or old_max != new_max, "unordered": unordered,
            "warning": "Branch model for synthetic pre/post resolved maxima only. A32-bit OR domain is not a native definition capacity or safe node bound. NaN exception/payload behavior, floating-point maximum evaluation and native execution are not emulated."}


def vendor_predicate_preview(grid, node, mask_bits, special_node):
    """Immutable4x7 literal-grid predicate; not menu execution or a purchase verdict."""
    uint(node, 31)
    uint(mask_bits)
    if type(special_node) is not int or not -3 <= special_node <= 31:
        raise ValueError("Expected bounded special node/marker")
    if not isinstance(grid, (list, tuple)) or len(grid) != 4 or any(not isinstance(r, (list, tuple)) or len(r) != 7 for r in grid):
        raise ValueError("Expected4x7 explicit grid")
    values = [v for row in grid for v in row]
    if any(type(v) is not int or not -3 <= v <= 31 for v in values):
        raise ValueError("Expected bounded literal grid cells")
    nodes = [v for v in values if v >= 0]
    if len(nodes) != len(set(nodes)):
        raise ValueError("Duplicate nonnegative grid node")
    positions = [(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v == node]
    neighbors = []
    if positions:
        r, c = positions[0]
        neighbors = [grid[nr][nc] for nr, nc in ((r-1,c), (r+1,c), (r,c-1), (r,c+1))
                     if 0 <= nr < 4 and 0 <= nc < 7 and grid[nr][nc] >= 0]
    bought = lambda n: n == 0 or bool(mask_bits & (1 << n))
    return {"node_present": bool(positions), "orthogonal_neighbors": sorted(neighbors),
            "can_be_purchased_predicate": bool(positions) and (node == special_node or node == 0 or any(bought(n) for n in neighbors)),
            "positive_neighbor_checks_satisfied": bool(positions) and all(bought(n) for n in neighbors if n > 0),
            "on_select_excludes_start": node == 0,
            "warning": "Static literal predicate only. Special canBePurchased and all-positive-neighbor movement/icon checks are separate. Native availability, wallet, hero, navigation state and transaction result are not simulated."}


def inspect(elf_path, save_path=None, vendor_asset_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}
    expected = {
        0x88938C: 0x10003058, 0x889390: 0x85A8A0, 0x89F1B8: 0x101EFB20,
        0x2ABFC: 0x80829454, 0x2AC00: 0x80A29458,
        0x32C34: 0xFC20081E, 0x32C38: 0xFFE0F81E, 0x32C4C: 0x7C6307B4,
        0x32C50: 0x7C8407B4, 0x32C5C: 0x78640620, 0x32C6C: 0x38600001,
        0x26400: 0x78840020, 0x2641C: 0x78630620,
        0x2D28B0: 0x2F9E0000, 0x2D28BC: 0x419E0034, 0x2D28C0: 0x83BE1A68,
        0x2D28CC: 0x57E92036, 0x2D28D0: 0x57E6103A, 0x2D28D8: 0x7CA64A14,
        0x2D28DC: 0x806B0420, 0x2D28E4: 0x7C03D800, 0x2D28EC: 0x40800034,
        0x2D28F4: 0x38600000, 0x2D2920: 0x88E90010, 0x2D292C: 0x2C870000,
        0x2D2930: 0x4186FFC0, 0x2D293C: 0x7D5B00D0, 0x2D2944: 0x7D4407B4,
        0x2D2950: 0x8102F2B4, 0x2D2954: 0x38800004, 0x2D2958: 0x80680000,
        0x2D296C: 0x38600001,
        0x465D38: 0x809F000C, 0x465D3C: 0x38600001, 0x465D40: 0x7C60E030,
        0x465D48: 0x7C890378, 0x465D4C: 0x913F000C, 0x465D58: 0xFF9F0800,
        0x465D5C: 0x419E0008, 0x465D60: 0xD03F0008,
        0x463DF4: 0x80630000, 0x463E04: 0x80BD000C, 0x463E08: 0x889D0011,
        0x2D1EA8: 0x80830048, 0x2D1EBC: 0x816A06A4, 0x2D1EC4: 0x7C8BF840,
        0x2D1ECC: 0x39230460, 0x2D1ED4: 0x4085000C, 0x2D1EDC: 0x81070010,
        0x2D1F1C: 0x81230048, 0x2D1F24: 0x800906A4, 0x2D1F28: 0x7F80F040,
        0x2D1F2C: 0x419D0024, 0x2D1C2C: 0x7C0918AE, 0x2D1C5C: 0x7CE92030,
        0x2D1C6C: 0x8003000C, 0x2D1C70: 0x7D2B0038,
        0x23D840: 0x81631A68, 0x23D844: 0x3D003B9A, 0x23D848: 0x6106C9FF,
        0x23D84C: 0x80EB0420, 0x23D850: 0x7C643A14, 0x23D854: 0x7CA33050,
        0x23D858: 0x7CA9FE70, 0x23D85C: 0x7CA04838, 0x23D864: 0x908B0420,
        0x694A70: 0x2F840004, 0x694A94: 0x419E00F4, 0x694AA4: 0x813E0000,
        0x694AAC: 0x41860024, 0x694B88: 0x806300E0, 0x694B8C: 0x2C030001,
        0x694B90: 0x4182FF08, 0x694B94: 0x38800001, 0x694B98: 0x909F0104,
        0x8AA43C: 0x694AF4, 0x694B04: 0x120, 0x694C14: 0x80BF00EC,
        0x694C18: 0x2F85FFFF, 0x694C1C: 0x419EFF40, 0x694C2C: 0x90DF0104,
    }
    for va, value in expected.items():
        if elf.u32(va) != value:
            raise ValueError(f"Upgrade purchase evidence changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    calls = {0x2AC04: 0x12EC0, 0x32C54: 0x26400, 0x32C64: 0x106A0,
             0x26410: 0x12A20, 0x12A2C: 0x2D2878, 0x2D28A0: 0x24FB88,
             0x2D28C4: 0x2D1E80, 0x2D2934: 0x465D00, 0x2D2948: 0x24F748,
             0x2D295C: 0x250FA8, 0x465D2C: 0x463DE0, 0x465D50: 0x463DE0,
             0x463DFC: 0x463190, 0x463E0C: 0x466500, 0x2D1E94: 0x463190,
             0x2D1F14: 0x463190, 0x2D1F50: 0x2D1C10, 0x2D1F68: 0x2D1C48,
             0x24F754: 0x23D840, 0x250FB4: 0x694A70, 0x694C30: 0x6952D8}
    for va, target in calls.items():
        if BINDINGS["branch_target"](elf.u32(va), va) != target:
            raise ValueError("Upgrade call/thunk target changed")
        guards[va] = elf.read(va, 4)
    for va in (0x32B48, 0x26400, 0x2D2878, 0x465D00, 0x463DE0,
               0x2D1E80, 0x2D1EF8, 0x2D1C10, 0x2D1C48, 0x23D840):
        guards[va] = elf.read(va, elf.functions[elf.functions.index(va)+1]-va)
    for va in (0x12A20, 0x24F748, 0x250FA8):
        guards[va] = elf.read(va, 16)
    guards[0x694A70] = elf.read(0x694A70, 0x130)
    guards[0x694C14] = elf.read(0x694C14, 0x30)
    for descriptor, code, toc in ((0x85A8A0, 0x32B48, 0x88FF38), (0x85A1A0, 0x26400, 0x88FF38),
                                  (0x86CA48, 0x2D2878, 0x89FF20)):
        if struct.unpack(">II", elf.read(descriptor, 8)) != (code, toc):
            raise ValueError("Purchase API descriptor changed")
        guards[descriptor] = elf.read(descriptor, 8)
    if elf.string(0x10003058) != "purchase_mod" or elf.descriptors[0x28440] != 0x88FF38:
        raise ValueError("Named purchase API registration changed")
    guards[0x10003058] = elf.read(0x10003058, 13)
    report = {"confidence": "code-backed purchase admission and ordered mask/ammo/wallet publication",
        "warning": "Exact USA v02.00 static native/optional shipped script evidence only. No native/Lua execution, runtime configuration capture, newly editable field or gameplay acceptance proof.",
        "api": {"name": "purchase_mod", "registration_call_va": "0x2ac04", "lua_wrapper_va": "0x32b48",
                "scalar_wrapper_va": "0x26400", "transaction_thunk_va": "0x12a20", "transaction_va": "0x2d2878",
                "argument_boundary": "After wrapper argument validation, values1/2 go through13080 then fctiwz, low32 stores and signed extension.26400 narrows the second argument to low32 and forwards. Nonfinite/out-of-range conversion behavior and validation helper internals are not modeled.",
                "result_boundary": "26400 narrows transaction0/1 to a byte.32B48 pushes it via106A0 and returns1 as the Lua RESULT COUNT, not an independent purchase-success flag. The shipped onSelect tests the pushed result."},
        "saved_fields": {"record_stride": "0x14", "modifier_mask_member": "0xc", "ammo_member": "0x8",
                         "ownership_member": "0x10", "stored_level_member": "0x11", "raritanium_offset": "0x420"},
        "admission": {"hero_lookup_va": "0x24fb88", "cost_getter_va": "0x2d1e80",
                      "wallet_comparison_va": "0x2d28e4", "record_ownership_va": "0x2d2920",
                      "rule": "Missing hero returns0. With resolved hero inventory+1A68, cost is obtained first; signed32 wallet420 must be >= signed32 cost, then record ownership byte10 must be nonzero. Equality admits; ownership is nonzero, not strictly1.",
                      "signed_edge": "High-bit raw wallet words compare as negative, not huge balances. High-bit cost words compare as negative; if admitted, low32 negated cost can become a credit rather than an ordinary debit. These synthetic malformed-state implications are not legitimate shipped costs or safe edits.",
                      "missing_checks": "Transaction body does not invoke2D1EF8 availability, test the already-set node bit, reject node0, check grid adjacency, or independently validate node/item bounds. Valid pointers/definition resolution are prerequisites to any preview, not proven by admission.",
                      "cost_boundary": "Cost getter uses an UNSIGNED node<NumMods test at config+6A4, then reads config+470+node*18. Missing definition/config or out-of-count node gives0 locally; zero cost is not a validity/safety certificate."},
        "publication": {"modifier_helper_va": "0x465d00", "maximum_helper_va": "0x463de0",
                        "mask_store_va": "0x465d4c", "ammo_store_va": "0x465d60", "debit_call_va": "0x2d2948",
                        "order": ["resolve OLD maximum ammo from record ID, stored level and OLD mask",
                                  "OR selected node bit and store mask at record+C",
                                  "resolve NEW maximum ammo using the published mask",
                                  "if fcmpu is not equal, store new maximum to ammo+8",
                                  "negate captured cost and call24F748→23D840 wallet mutation",
                                  "send runtime request4 through250FA8→694A70; ignore result; return1"],
                        "ammo_rule": "Equal maxima skip the ammo write, regardless of current ammo. Unequal maxima store the new maximum absolutely, not old ammo plus capacity difference. fcmpu unordered also falls through to the store; NaN exception/payload preservation is not established. Maximum resolution depends on record ID, stored level+11 and mask+C through466500.",
                        "repeat_rule": "A repeated native transaction can pass the same local gates and charge again even when OR does not change the already-set bit. With equal recomputed maxima, ammo remains untouched. Normal vendor availability prevents this at its own boundary, not through native transaction duplicate rejection.",
                        "debit_rule": "Captured cost is negated low32. Wallet leaf computes wrapped sum, selecting999999999 only when wrapped(cap-sum) bit31 is set. No lower clamp or rollback is implemented in this local chain; mask/ammo publication precedes wallet mutation.",
                        "scope": "Order of guarded native operations only; not concurrency/atomicity, crash recovery or proof all callers use vendor constraints."},
        "availability": {"va": "0x2d1ef8", "rule": "Separate predicate requires unsigned node<NumMods, nonzero ownership via2D1C10 and unset mask bit via2D1C48. This predicate is not called by2D2878 itself. It does not check wallet or adjacency; null/invalid definition safety is not independently established."},
        "runtime_request": {"thunk_va": "0x250fa8", "target_va": "0x694a70", "request": 4,
                           "rule": "If runtime context+E0 !=1, request4 stores1 at+104 then returns0. Transaction ignores that return and still returns1. If E0==1 it dispatches case4 through the relative table at694AF4 to694C14: EC==FFFFFFFF skips to common completion; otherwise clears104 then delegates6952D8 and continues. The context pointer comes from an uninitialized runtime pointer holder, not a resolved saved-field address.",
                           "scope": "No original notification/menu name or current runtime context is inferred. Downstream6952D8 and the remainder of the generic state machine are not fully reversed here."},
        "script_boundary": {"asset": "/built/anark/weaponvendor/built.dat", "reference_sha256": LUA["VENDOR_HASH"],
                            "rule": "Shipped onSelect calls is_mod_available, canBePurchased, and excludes node0 before purchase_mod; it tests purchase_mod's result before success UI updates. Ordinary neighbor reachability, start-node convention and special movement/icon checks are separate script layers, not native transaction admission.",
                            "start_rule": "beenPurchased treats node0 as true without saved bit0. Native ownership still belongs to the weapon record, not that script start convention.",
                            "special_boundary": "canBePurchased returns true for the special node directly; all-positive-neighbor specialCheck calls belong to movement/icon gating instead. A synthetic special canBePurchased result is not full menu eligibility.",
                            "scope": "Prior grid evidence is context, not new204-node discovery. Optional asset observation rechecks exact method code/fingerprints without executing scripts."},
        "limitations": ["No new safe editing range, edited-save round trip or gameplay transaction has been validated.",
                        "No current runtime cost, maximum ammo, definition/pointer validity or purchase permission is inferred from a detached save.",
                        "Invalid node/item safety, floating conversion exceptions and complete downstream request effects remain unproved."],
        "recommended_annotations": [
            {"va": "0x465d00", "kind": "function", "name": "TOD_apply_modifier_bit_and_conditional_ammo_refresh_verified",
             "comment": "Resolves old max ammo, OR/stores saved record+C node bit, resolves new max; non-EQ fcmpu (including unordered) writes NEW maximum absolutely to record+8. Equal maxima leave ammo untouched. No local duplicate/index/ownership admission; caller purchase debits afterward."},
            {"va": "0x32b48", "kind": "function", "name": "TOD_Lua_purchase_mod_result_wrapper_verified",
             "comment": "Named export registration2AC04. Validated values1/2 through13080→fctiwz low32 sign extension, call26400→12A20→2D2878, push transaction byte via106A0. Return1 is Lua result count, not separate success verdict."}],
        "instruction_guards": [{"va": hex(a), "bytes": raw.hex().upper()} for a, raw in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Expected verified plaintext save size")
        data = path.read_bytes()
        if any(struct.unpack_from(">I", data, i*20)[0] != i for i in range(32)):
            raise ValueError("Expected verified plaintext inventory IDs")
        report["save_observation"] = {"sha256": hashlib.sha256(data).hexdigest().upper(),
            "raritanium_bits": f"{struct.unpack_from('>I',data,0x420)[0]:08X}",
            "records": [{"id": i, "record_offset": hex(i*20), "mask_raw_hex": data[i*20+12:i*20+16].hex().upper(),
                         "ownership_byte": data[i*20+16], "ammo_raw_hex": data[i*20+8:i*20+12].hex().upper()}
                        for i in range(32)],
            "warning": "Raw detached snapshot only, not runtime resolved cost/maxima or node availability. No fields are rewritten or normalized."}
    if vendor_asset_path is not None:
        report["asset_observation"] = inspect_vendor_asset(vendor_asset_path)
    return report


def inspect_vendor_asset(path):
    path = Path(path)
    if path.stat().st_size != 390796:
        raise ValueError("Reference vendor asset size mismatch")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest().upper() != LUA["VENDOR_HASH"]:
        raise ValueError("Reference vendor asset SHA-256 mismatch")
    decoded = LUA["inspect"](path, 0x54F85)
    expected = {
        "onSelect": (0x5A7F8, 142, "843621500C7E5442031C1D9B0591CECCA188F7B7E0AA6C30F57F0B81342A0E9B"),
        "canBePurchased": (0x56A8A, 79, "DA2B498594AA83B7A8ACE352C4D4164370013C9EDE5115547725E7E0CB2C037F"),
        "beenPurchased": (0x56CFC, 41, "5B9756401AD9A7A4120BD27ED66DDA3646E0E0BA589C1BDCB81152FA1EA4F846"),
        "specialCheck": (0x56ECE, 39, "7AC5B7B412AA7046953CF60B4E2A399E5773EB1E8243686C107F460400F2B143"),
        "is_valid_movement": (0x56781, 72, "8FCDCCEFDADAFCD9A0F6561A183066118145C71D416CF3EE3EB2765A502B9DAA")}
    methods = []
    for name, (offset, count, digest) in expected.items():
        matches = [f for f in decoded["root"]["children"] if f.get("assigned_name") == name]
        if len(matches) != 1 or int(matches[0]["code_offset"], 0) != offset or len(matches[0]["instructions"]) != count:
            raise ValueError("Vendor purchase method identity changed")
        if hashlib.sha256(raw[offset:offset+count*4]).hexdigest().upper() != digest:
            raise ValueError("Vendor purchase method code changed")
        methods.append({"name": name, "code_file_offset": hex(offset), "instruction_count": count, "code_sha256": digest})
    words = {0x5A7F8: 0x01000005, 0x5A824: 0x01018099, 0x5A844: 0x01020099,
             0x5A874: 0x0100C055, 0x5A87C: 0x01000205, 0x5A8A8: 0x01018099,
             0x5A8AC: 0x01008018, 0x5A8B0: 0x008008D4,
             0x56D54: 0x0001BF55, 0x56D5C: 0x03008002, 0x56BB2: 0x03008002}
    for offset, word in words.items():
        if struct.unpack_from("<I", raw, offset)[0] != word:
            raise ValueError("Vendor purchase instruction guard changed")
    layout = LUA["vendor_layout"](decoded)
    combuster = layout["grids"]["WPN_COMBUSTER"]
    examples = [{"node": node, "mask_raw_hex": "00000000",
                 "predicate": vendor_predicate_preview(combuster["grid"], node, 0, combuster["special_node"])}
                for node in (0, 1, 2, 12)]
    return {"asset": "/built/anark/weaponvendor/built.dat", "size": len(raw), "sha256": LUA["VENDOR_HASH"],
            "methods": methods, "grid_count": len(layout["grids"]),
            "combuster_synthetic_examples": examples,
            "asset_guards": [{"file_offset": hex(o), "bytes": raw[o:o+4].hex().upper()} for o in sorted(words)],
            "warning": "Exact shipped static code and synthetic mask0 examples, not runtime menu execution or purchase permission. File offsets are not ELF VAs or save offsets; original full asset payload is not bundled."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--vendor-asset", type=Path)
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save, options.vendor_asset), indent=2, allow_nan=False))
