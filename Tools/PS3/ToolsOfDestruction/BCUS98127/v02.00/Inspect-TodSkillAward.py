"""Read-only exact-build skill award producer gates and publication ordering."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct

PROGRESSION = runpy.run_path(str(Path(__file__).with_name("Inspect-TodProgression.py")))
BINDINGS = PROGRESSION["BINDINGS"]


def uint(value, bits=32):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 1 << bits:
        raise ValueError(f"Expected unsigned raw{bits}-bit integer")
    return value


def skill_preview(score, bits, identifier, points):
    """Immutable, callback-free normal-ID storage model, not a native award invocation.

    Real notifications run before the completion scan and could affect runtime
    state. This model deliberately assumes no notification/reentrant mutation.
    """
    uint(score)
    uint(bits, 64)
    uint(identifier)
    if identifier >= 60 or not isinstance(points, (list, tuple)) or len(points) != 60:
        raise ValueError("Preview requires named skill ID0..59 and60 definition points")
    for value in points:
        uint(value)
    awarded, events = [], []
    while not bits & (1 << identifier):
        bits |= 1 << identifier
        events.append(f"bit:{identifier}")
        score = (score + points[identifier]) & 0xFFFFFFFF
        events.extend((f"score:{identifier}", f"notification-omitted:{identifier}"))
        awarded.append(identifier)
        if identifier == 59 or bits & ((1 << 59)-1) != (1 << 59)-1:
            break
        identifier = 59
    return {"score": score, "bits": bits, "awarded_ids": awarded, "events": events,
            "scope": "No callbacks or runtime/reentrant effects are simulated; not a save edit."}


def collectible_preview(masks, totals, world, local_id):
    """Native leaf's OR/scan on bounded physical worlds; no wrapper admission claim."""
    if not isinstance(masks, (list, tuple)) or not isinstance(totals, (list, tuple)) or len(masks) != 19 or len(totals) != 19:
        raise ValueError("Expected19 physical-world masks and shipped totals")
    for value in tuple(masks)+tuple(totals):
        uint(value)
    uint(world)
    uint(local_id)
    if world >= 19:
        raise ValueError("Preview requires world0..18, not the count sentinel/slot19")
    result = list(masks)
    if local_id <= 31:
        result[world] |= 1 << local_id
    counts = [mask.bit_count() for mask in result]
    return {"masks": result, "counts": counts, "mask_changed": result != list(masks),
            "completion_scan_ran": True,
            "skill46_call_requested": all(count >= total for count, total in zip(counts, totals)),
            "scope": "Leaf-only bounded model. A call request is not a new award; skill setter deduplicates independently."}


def ammo_award_gate_preview(item_id, original_request, hero_present, cost_bits, bolts_bits,
                            ownership_byte, definition_flags):
    """Only producer branch admission; cost must already be the native converted word.

    Does not calculate missing ammo, float32 multiplication/fctiwz, mutation,
    pricing, deduction, callbacks or runtime availability. Original request is
    the incoming double, not the clamped quantity or current saved ammo.
    """
    for value in (item_id, cost_bits, bolts_bits, definition_flags):
        uint(value)
    uint(ownership_byte, 8)
    if item_id >= 32 or not isinstance(hero_present, bool):
        raise ValueError("Normal item ID0..31 and explicit hero-present boolean required")
    if isinstance(original_request, bool) or not isinstance(original_request, (int, float)):
        raise ValueError("Expected original numeric request")
    signed = lambda value: BINDINGS.signed(value, 32)
    admitted = hero_present and signed(cost_bits) <= signed(bolts_bits) and ownership_byte != 0 and definition_flags & 3 == 0
    return {"producer_admitted": admitted,
            "skill47_call_requested": admitted and item_id == 1 and original_request <= 1.0,
            "signed_cost": signed(cost_bits), "signed_bolts": signed(bolts_bits),
            "request_ordered_at_most_one": original_request <= 1.0}


def quantity_selection_preview(original_request, missing_quantity):
    """Synthetic finite mathematical selection; supplied missing-helper result only.

    No native float32 rounding, signed-zero/fsel edges or helper evaluation is
    simulated. The original request is retained separately by the award gate.
    """
    uint(missing_quantity)
    if isinstance(original_request, bool) or not isinstance(original_request, (int, float)) or not math.isfinite(original_request):
        raise ValueError("Finite numeric request required; no nonfinite fsel emulation")
    return min(float(original_request), float(missing_quantity)) if original_request > 0 else float(missing_quantity)


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}
    def keep(address, size):
        guards[address] = elf.read(address, size)
    def function(address):
        end = elf.functions[elf.functions.index(address)+1]
        keep(address, end-address)
    checks = {0x35D628: 0x409E00C0, 0x35D63C: 0xF8E90008,
              0x35D640: 0x480014C1, 0x35D64C: 0x90DB31E0,
              0x35D650: 0x4BEF3CC9, 0x35D660: 0x480014D1,
              0x35D670: 0x4BEF3D69, 0x35D6E4: 0x4086FF20,
              0x35DED4: 0x419D0018, 0x35DEE8: 0x912303EC,
              0x35DF30: 0x7C1C1840, 0x35DF78: 0x4BFFF659,
              0x2D2BE4: 0xC042F2B0, 0x2D2C40: 0xECBF01B2,
              0x2D2C44: 0xFC80281E, 0x2D2C58: 0x7C84F800,
              0x2D2CAC: 0x88E30010, 0x2D2CCC: 0x4819314D,
              0x2D2CE0: 0x4BF7CFD9, 0x2D2D14: 0xC102F2B8,
              0x2D2D1C: 0x4C401382, 0x2D2D28: 0x3880002F,
              0x2D2D2C: 0x4808A8A5, 0x2D2040: 0x816906AC,
              0x89F1D0: 0, 0x89F1D8: 0x3F800000,
              0x89F1E4: 0x101F5048, 0x89FF20+0x1A34: 0x101EFB20}
    for address, word in checks.items():
        if elf.u32(address) != word:
            raise ValueError(f"Award instruction/pointer changed at {address:#x}")
        keep(address, 4)
    for address in (0x35D5D0, 0x35DEB0, 0x35EB00, 0x35EB30,
                    0x2D2B90, 0x2D2000, 0x2D22E8):
        function(address)
    keep(0x11D60, 16)
    skills = PROGRESSION["exports"](elf, 0x294E90, "SKILLPOINT_", 0x252EB8)
    named = [skills[i] for i in (46,47,59)]
    if [v["enum"] for v in named] != ["SKILLPOINT_GOLDEN", "SKILLPOINT_CHEAPSKATE", "SKILLPOINT_HARDCORE"]:
        raise ValueError("Award enum exports changed")
    for item in named:
        for key in ("name_slot_va", "name_load_va", "value_slot_va", "value_load_va", "export_call_va"):
            keep(int(item[key],0),4)
        keep(int(item["name_va"],0),len(item["enum"])+1)
    definitions = elf.u32(0x89FF20+0x1A6C)
    keep(0x89FF20+0x1A6C,4)
    keep(definitions,60*16)
    points = [elf.u32(definitions+i*16) for i in range(60)]
    totals_va = elf.u32(0x89F158)
    keep(0x89F158,4)
    keep(totals_va,19*4)
    totals = list(struct.unpack(">19I",elf.read(totals_va,19*4)))
    report = {"confidence": "code-backed",
        "warning": "Exact USA BCUS98127 v02.00 static producer branches and detached observations. No callbacks/native code execute; not a safe-edit contract or in-game validation. Basic bit roles, duplicate prevention and automatic awards were already mapped; this pass sharpens producer gates and order.",
        "skill_publication": {"setter_va": "0x35d5d0", "score_offset": "0x8708", "bits_offset": "0x8710",
            "normal_ids": [0,59], "points": points,
            "order": ["read existing bit; return if set", "capture old saved score", "publish selected bit", "read definition points35EB00", "publish old score + points modulo2^32", "get runtime notification recipient251318", "read name tag35EB30", "notify2513D8", "unless ID59, scan bits0..58 and loop to59 if all set"],
            "retention": "Already-set ID returns before score updates, notifications and the completion scan. Calling a duplicate does not repair a mismatched score or missing ID59. Unknown bits60..63 remain retained in normal-ID operations.",
            "notification_scope": "Name getter35EB30 reads definition+4. This is a tag, not recovered localized text. Static publication is ordered, not atomic; runtime/reentrant notification effects are not modelled."},
        "golden_producer": {"setter_va": "0x35deb0", "physical_worlds": [0,18], "world_stride": "0x408",
            "first_mask_offset": "0x874", "shipped_totals": totals, "skill_id": 46,
            "order": "Unsigned local-ID<=31 permits mask OR/write, then every invocation scans all19 world popcounts with unsigned count>=shippedtotal and optionally calls skill46 setter.",
            "sharper_rules": ["A duplicate collectible still performs the completion scan.", "Native local-ID>31 skips the mask write but does not skip the completion scan; wrapper admission is not established by this leaf.", "Population count includes unexpected bits and completion uses >=, not identity of physical pickups or exact equality.", "Zero-total worlds satisfy their comparison. Slot19 is excluded. Saved skill46 is independently retained and cannot be inferred false from incomplete current masks."],
            "scope": "Bounded world0..18 model only. No invalid world-pointer indexing or named script-wrapper input acceptance is simulated."},
        "cheapskate_producer": {"function_va": "0x2d2b90", "entry_thunk_va": "0x11d60", "skill_id": 47, "item_id": 1,
            "original_request_zero_va": "0x89f1d0", "original_request_award_threshold_va": "0x89f1d8",
            "award_threshold": 1.0, "missing_quantity_helper_va": "0x2d22e8", "unit_price_helper_va": "0x2d2000",
            "unit_price_source": "Definition data+6AC unsignedword; getter returns zero for missing config/data or low definition flags&3 !=0. This is not a gameplay-safe pricing contract.",
            "quantity_selection": "Finite mathematical branch: original request>0 selects min(original request, supplied missing quantity); request<=0 leaves the missing quantity. Synthetic preview does not emulate float32 rounding or signed-zero/fsel edges. Incoming original request is retained separately for the award test.",
            "producer_admission": "Hero lookup24FB88 must be nonzero; selected-quantity * unsigned unitprice is rounded as a float32 product then converted with fctiwz; resulting signed32 cost must be <= signed32 savedbolts+41C; ownership byte(item*0x14+0x10) must be nonzero; definition flags&3 must be zero.",
            "success_order": ["add selected ammo465E18", "deduct converted cost through24FCB8", "if item1 and ordered original request<=1.0, call skill47 setter", "merge checkpoint bank35D358", "runtime notification250FA8(type4)", "return1"],
            "sharper_rules": ["Award checks original request, not clamped quantity or saved ammo. A request>1 clamped to one or zero still fails this award comparison.", "Zero/negative original requests select missing quantity yet meet the native <=1 comparison after producer admission. No named-wrapper acceptance or gameplay exploit claim.", "NaN fails the ordered award comparison; full nonfinite quantity/cost conversion behavior remains outside the preview.", "No explicit positive converted-cost or positive selected-quantity test exists in this producer. Duplicate skill47 calls do not add points or repair other state."],
            "scope": "No runtime config/missing-ammo computation, float conversion overflow, callback execution, current purchase eligibility or localized Cheapskate description inferred."},
        "named_awards": named,
        "recommended_annotations": [
            {"va": "0x002D2B90", "name": "TOD_purchase_ammo_cheapskate_producer", "kind": "function", "comment": "On admitted ammo purchase, ammo addition and bolt deduction precede skill47. Award requires item1 and ordered ORIGINAL request<=1, not clipped selected quantity. Signed converted-cost<=signed savedbolts, nonzero ownership and definition flags&3 zero gate success. Request<=0 retains missing quantity; wrapper admission unresolved."},
            {"va": "0x002D2000", "name": "TOD_get_ammo_unit_price", "kind": "function", "comment": "Returns unsigned configdata+6AC word when config/data exists and lowflags&3 zero; otherwise0. Native ammo purchase uses unsignedprice converted to float32 then fctiwz product; eligibility compares signed convertedcost to signed savedbolts."}],
        "instruction_guards": [{"va":hex(a),"bytes":raw.hex().upper()} for a,raw in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Expected verified plaintext906F0 layout")
        data = path.read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I",data,i*20)[0] != i for i in range(32)):
            raise ValueError("Expected verified plaintext inventory IDs")
        bits = struct.unpack_from(">Q",data,0x8710)[0]
        masks = [struct.unpack_from(">I",data,0x874+i*0x408)[0] for i in range(19)]
        bolts = struct.unpack_from(">I",data,0x41C)[0]
        report["save_observation"] = {"plaintext_sha256":hashlib.sha256(data).hexdigest().upper(),
            "score_raw":struct.unpack_from(">I",data,0x8708)[0], "bits_hex":f"{bits:016X}",
            "skills46_47_59":{str(i):bool(bits & 1<<i) for i in (46,47,59)},
            "all_bits0_58_set":bits & ((1<<59)-1) == (1<<59)-1,
            "world_masks_hex":[f"{mask:08X}" for mask in masks], "world_popcounts":[mask.bit_count() for mask in masks],
            "saved_masks_meet_golden_count_comparisons":all(mask.bit_count()>=total for mask,total in zip(masks,totals)),
            "bolts_hex":f"{bolts:08X}", "bolts_signed_for_purchase_comparison":BINDINGS.signed(bolts,32),
            "combuster_ownership_raw":data[0x24], "combuster_ammo_bits_hex":data[0x1C:0x20].hex().upper(),
            "scope":"Stored snapshot only; no original request, runtime hero/config, current purchase or award prediction."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf",required=True,type=Path)
    parser.add_argument("--save",type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf,args.save),indent=2))
