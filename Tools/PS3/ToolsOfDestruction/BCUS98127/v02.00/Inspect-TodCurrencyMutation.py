"""Read-only exact-build currency mutation routes, raw arithmetic and ordering."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
CAP = 999999999
MASK = 0xFFFFFFFF


def uint(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MASK:
        raise ValueError("Expected unsigned raw32-bit integer")
    return value


def hero_wallet_preview(wallet_bits, delta_bits):
    """Exact low32 leaf arithmetic only; no caller admission or save mutation.

    The sign of the wrapped difference is important: this is not a universal
    unsigned minimum, signed minimum, saturating add or lower bound at zero.
    """
    uint(wallet_bits)
    uint(delta_bits)
    total = (wallet_bits + delta_bits) & MASK
    difference = (CAP - total) & MASK
    selected = CAP if difference & 0x80000000 else total
    return {"wallet_bits": selected, "sum_bits": total,
            "difference_bits": difference,
            "selected_cap": bool(difference & 0x80000000),
            "scope": "Callback-free leaf low32 arithmetic; caller eligibility and execution are not simulated."}


def reward_wallet_preview(wallet_bits, runtime_counter_bits, delta_bits):
    """Exact two-store low32 reward leaf model; supplied runtime word, not a save total."""
    for value in (wallet_bits, runtime_counter_bits, delta_bits):
        uint(value)
    return {"runtime_counter_bits": (runtime_counter_bits + delta_bits) & MASK,
            "wallet_bits": (wallet_bits + delta_bits) & MASK,
            "store_order": ["runtime counter", "saved wallet"],
            "scope": "No upper/lower cap at this leaf. Runtime counter is not read from the save. No pointer, callback or reward-calculator simulation."}


def reward_word_preview(result_f32_bits):
    """Finite/in-range fctidz + low32 nonzero gate, on an already-calculated f32.

    Does not calculate or authorize a reward, emulate nonfinite/out-of-range
    PPC conversions, or imply that a negative result is admitted by producers.
    """
    uint(result_f32_bits)
    value = struct.unpack(">f", struct.pack(">I", result_f32_bits))[0]
    if not math.isfinite(value) or not -(1 << 63) <= value < 1 << 63:
        raise ValueError("Finite signed64-convertible native result required")
    converted = math.trunc(value)
    word = converted & MASK
    return {"converted_signed64": converted, "delta_bits": word,
            "leaf_call_requested": word != 0,
            "scope": "Consumer low32 gate only, not current payout or native producer admission."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}
    def keep(address, length):
        guards[address] = elf.read(address, length)
    def function(address):
        keep(address, elf.functions[elf.functions.index(address)+1]-address)
    checks = {
        0x23D810: 0x81631A68, 0x23D814: 0x3D003B9A, 0x23D818: 0x6106C9FF,
        0x23D81C: 0x80EB041C, 0x23D820: 0x7C643A14, 0x23D824: 0x7CA33050,
        0x23D828: 0x7CA9FE70, 0x23D82C: 0x7CA04838, 0x23D834: 0x908B041C,
        0x23D840: 0x81631A68, 0x23D84C: 0x80EB0420, 0x23D858: 0x7CA9FE70,
        0x23D864: 0x908B0420,
        0x24FCC4: 0x4BFEDB4C, 0x24F754: 0x4BFEE0EC,
        0x369AAC: 0x80CB0124, 0x369AB4: 0x90AB0124,
        0x369AB8: 0x81230030, 0x369AC4: 0x9089041C,
        0x36A45C: 0x80CB0128, 0x36A464: 0x90AB0128, 0x36A474: 0x90890420,
        0x3842F8: 0xFC00165E, 0x38430C: 0xFC200E5E,
        0x38431C: 0x2F800000, 0x3843AC: 0x2C1D0000,
        0x3843B4: 0x7FA407B4, 0x3843C0: 0x2C9F0000,
        0x3843D0: 0x4BFE6089, 0x3843E0: 0x4BFE56C9,
        0x3764B4: 0xFC00165E, 0x3764C8: 0xFC200E5E,
        0x376514: 0x7FA407B4, 0x376530: 0x4BFF3F29, 0x376558: 0x4BFF3551,
        0x304034: 0x38800416, 0x30404C: 0x5463063E,
        0x304090: 0x7D0407B4, 0x304094: 0x4BF4BC25,
        0x3040B0: 0x7C9D482E, 0x3040BC: 0xFD80169C,
        0x3040C0: 0xFC006018, 0x3040C4: 0xEDA10028, 0x3040C8: 0xD1AB000C,
        0x306370: 0x38800416, 0x306384: 0x5464063E,
        0x3063B0: 0x7D4407B4, 0x3063B4: 0x4BF49395,
        0x3063C4: 0x7D8007B4, 0x30642C: 0xFC401E9C,
        0x306434: 0xFDA01018, 0x306438: 0xEC016828,
        0x28A8F8: 0x38800211, 0x28A964: 0x7FA407B4, 0x28A96C: 0x4BFC534D,
        0x28A698: 0x38800211, 0x28A704: 0x7FA407B4, 0x28A70C: 0x4BFC503D,
        0x8A1C24: 0x10330740, 0x8A0048: 0x101EF8E0,
        0x8A0054: 0x10063108, 0x8A01C8: 0x101EF920,
    }
    for address, word in checks.items():
        if elf.u32(address) != word:
            raise ValueError(f"Currency instruction/pointer changed at {address:#x}")
        keep(address, 4)
    for address in (0x23D810, 0x23D840, 0x369AA8, 0x36A458,
                    0x3842B8, 0x376428, 0x304010, 0x306338, 0x28A880, 0x28A620):
        function(address)
    keep(0x24FCB8, 16)
    keep(0x24F748, 16)
    report = {"confidence": "code-backed",
        "warning": "Exact USA BCUS98127 v02.00 native currency routes and detached observations. No game/native code executes. Wallet offsets were already mapped; this pass separates arithmetic, runtime counters and producer ordering. No safe edit bounds, high-water/collected total, current payout or in-game validation claimed.",
        "hero_wallet_mutation": {
            "bolts_leaf_va": "0x23d810", "raritanium_leaf_va": "0x23d840",
            "bolts_thunk_va": "0x24fcb8", "raritanium_thunk_va": "0x24f748",
            "hero_state_pointer_member": "0x1a68", "bolts_save_offset": "0x41c", "raritanium_save_offset": "0x420",
            "cap_constant": CAP, "cap_hex": "0x3b9ac9ff",
            "raw_rule": "sum=(old+delta) modulo2^32; difference=(999999999-sum) modulo2^32; result=cap if difference bit31 is set, else sum. add/subf/srawi31/and/add/stw, not a universal unsigned/signed minimum.",
            "normal_domain": "For ordinary nonnegative sums in signed32 range, this selects min(sum,999999999). There is NO lower clamp, underflow rejection, direct-leaf hero/type gate or callback.",
            "edge_scope": "Wrapping or high-bit raw state can differ from intuitive saturation. Negative ordinary sums can remain negative; some signed-overflow differences select cap. No malformed-input gameplay acceptance inferred.",
            "runtime_effect": "These two leaves store only their respective wallet. They do not update the reward path's runtime+124/+128 counters or saved reward caches.",
            "thunk_scope": "16-byte TOC-change thunks reduce caller r2 by10000 then add18 before the branch. Save offsets, hero members, runtime roots and ELF VAs remain distinct."},
        "reward_wallet_mutation": {
            "bolts_leaf_va": "0x369aa8", "raritanium_leaf_va": "0x36a458",
            "hero_state_pointer_member": "0x30", "runtime_root_slot_va": "0x8a1c24", "runtime_root_va": "0x10330740",
            "runtime_bolts_member": "0x124", "runtime_raritanium_member": "0x128",
            "order": ["read/add/store runtime counter+124 or+128", "read hero+30 state pointer", "read/add/store saved wallet41C or420"],
            "raw_rule": "Both stores retain low32(old+delta), with no upper cap, lower clamp, native sign/zero gate or callback at these leaves.",
            "counter_scope": "The initialized pointer points outside the serialized interval101EFB20..10280210. Its runtime words are NOT serialized collected totals, high-water marks, wallet aliases or inferable from a detached save.",
            "producer_scope": "Negative raw deltas and wrapping are leaf arithmetic facts, not proof that an ordinary pickup producer admits those inputs. Unlike24FCB8/24F748 these leaves do not use the999999999 selection."},
        "reward_conversion_consumers": {
            "consumer_vas": ["0x3842b8", "0x376428"],
            "order": ["calculate bolts2CEF70 and convert through fctidz", "calculate raritanium2CEBC0 and convert through fctidz", "if either LOW32 result is nonzero, resolve runtime hero", "nonzero low32 bolts sign-extended then369AA8", "nonzero low32 raritanium sign-extended then36A458"],
            "conversion": "fctidz truncates toward zero to signed64; cmpwi examines low32 and extsw forwards signed low32. Thus a finite positive converted multiple of2^32 can skip a leaf even though the full converted64 value is nonzero. Negative converted low32 is not filtered by an explicit positivity gate here.",
            "scope": "Preview accepts already-calculated float32 bit patterns only, rejects NaN/infinity/signed64-overflow, and does not emulate runtime reward calculations or producer admission. Consumer3842B8 subsequently sends type31 runtime message and virtual cleanup even when neither wallet leaf is called;376428 has other runtime bookkeeping before calculation."},
        "pickup_runtime_debit": {
            "bolts_function_va": "0x304010", "raritanium_function_va": "0x306338",
            "gate": "Actor pointer at argument+40 must be nonzero and24F208(actor,0x416) low byte nonzero. Native leaves do not independently verify positive quantity or lower wallet bound.",
            "bolts_order": "Read definition word at10063108+16*object+9C, pass signed-low32 delta through24FCB8 first, then reread definition word as unsigned32, convert fcfid/frsp, and subtract float32 from runtime101EF8E0+0C.",
            "raritanium_order": "Perform253048(object+9C,0) before actor gate. After admission, pass signed object+A0 through24F748 first, then reread/sign-extend object+A0, convert fcfid/frsp and subtract float32 from runtime101EF920+0C. Signed32 input fits the direct conversion branch; unrelated wide-integer fallback code is retained, not exercised by the bounded model.",
            "sharper_rule": "Runtime cache debit uses the FULL reread requested definition/object word, not the actual difference between old and capped wallet. A wallet capped near999999999 need not receive the same amount debited from that runtime float cache. No current cache values, callback atomicity or collection-completion verdict inferred.",
            "scope": "Runtime float cache pointers are outside serialized state. These routines are static currency-consumer anchors, not recovered named pickup classes or executed gameplay transactions."},
        "actor_mutation_routes": {
            "bolts_function_va": "0x28a880", "raritanium_function_va": "0x28a620",
            "gate": "Resolve actor handle276D48; missing handle or failed lowbyte actor-typeB9 goes through diagnostic24F9D8. Subsequent resolved actor+40 nonzero and type211 lowbyte nonzero route signed-low32 delta to24FCB8 or24F748; failed211 returns without currency write.",
            "scope": "Diagnostic continuation/termination and invalid-handle safety are not emulated. No script-export name, named-wrapper numeric conversion or accepted malformed input claimed."},
        "recommended_annotations": [
            {"va": "0x0023D810", "name": "TOD_hero_bolts_add_upper_selection", "kind": "function", "comment": "hero+1A68 wallet41C: low32 sum(old+delta); select999999999 only when low32(cap-sum) bit31 set. Ordinary nonnegative signed32 sum gets upper selection, NOT universal saturation or lower clamp. No runtime reward counter update/callback here."},
            {"va": "0x0023D840", "name": "TOD_hero_raritanium_add_upper_selection", "kind": "function", "comment": "hero+1A68 wallet420: same wrapped-difference-sign upper selection999999999 as23D810. No lower bound or runtime124/128 update. Purchase deduction thunk24F748 branches here after TOC change."},
            {"va": "0x00369AA8", "name": "TOD_hero_bolts_reward_add", "kind": "function", "comment": "Low32 adds delta to runtime10330740+124 FIRST, then hero+30 savedwallet41C. No upper/lower cap or native sign/zero gate. Runtime counter is outside serialized state, not a saved collected/high-water total. Distinct from capped-difference-sign hero route23D810."},
            {"va": "0x0036A458", "name": "TOD_hero_raritanium_reward_add", "kind": "function", "comment": "Low32 adds delta to runtime10330740+128 FIRST, then hero+30 savedwallet420. No upper/lower cap or native sign/zero gate. Runtime counter not persisted in save. Distinct from hero route23D840 upper selection999999999."},
            {"va": "0x00304010", "name": "TOD_bolts_currency_consumer_cache_debit", "kind": "function", "comment": "Resolved actor+40/type416 lowbyte gate. Definition word delta goes via24FCB8 wallet first; reread unsigned word ->fcfid/frsp then full float32 debit runtime101EF8E0+0C. Cache debit is requested amount, not observed capped-wallet delta; runtime-only."},
            {"va": "0x00306338", "name": "TOD_raritanium_currency_consumer_cache_debit", "kind": "function", "comment": "253048(object+9C,0) BEFORE actor/type416 gate; signed object+A0 via24F748 wallet first; reread signed word ->float32 then full debit runtime101EF920+0C. Cache debit not capped-wallet delta; runtime-only."},
        ],
        "instruction_guards": [{"va": hex(address), "bytes": raw.hex().upper()} for address, raw in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Expected plaintext906F0 layout")
        data = path.read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i*20)[0] != i for i in range(32)):
            raise ValueError("Expected verified plaintext inventory IDs")
        values = {name: struct.unpack_from(">I", data, offset)[0] for name, offset in (("bolts",0x41C),("raritanium",0x420))}
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "wallets": {name: {"bits_hex": f"{value:08X}", "unsigned32": value,
                                "signed32": BINDINGS["signed"](value,32)} for name,value in values.items()},
            "scope": "Stored wallet snapshot only. No runtime counters/cache values, mutation route/history, total collected, current payout or eligibility can be inferred."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2))
