"""Read-only exact-build CrateAmmo refill requests, admission and post-store rounding."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
CAPACITY = runpy.run_path(str(Path(__file__).with_name("Inspect-TodAmmoCapacity.py")))
CONFIGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponConfigs.py")))


def request_preview(maximum_bits, ammo_bits, crate_bits, factor_bits, item_id):
    """Explicit finite binary32 nearest-even arithmetic, not a resulting save preview."""
    if type(item_id) is not int or not 0 <= item_id < 32:
        raise ValueError("Preview requires an explicit valid inventory ID0..31")
    maximum, ammo, crate, factor = [CAPACITY["finite_bits"](v) for v in (maximum_bits, ammo_bits, crate_bits, factor_bits)]
    missing = CAPACITY["rounded"](maximum-ammo)
    scaled = CAPACITY["rounded"](factor*crate)
    request = min(max(scaled, 0.0), missing)
    if abs(request) > 0x7FFFFFFF:
        raise ValueError("Reference rounding projection limited to finite signed31 magnitude")
    request_bits = struct.unpack(">I", struct.pack(">f", request))[0]
    return {"missing_bits": f"{struct.unpack('>I', struct.pack('>f', missing))[0]:08X}",
            "scaled_crate_bits": f"{struct.unpack('>I', struct.pack('>f', scaled))[0]:08X}",
            "add_request_bits": f"{request_bits:08X}",
            "post_add_local_value": request if item_id == 3 else math.ceil(request),
            "qualification": "Explicit synthetic finite inputs only; binary32 nearest-even/gradual-underflow reference with signed-zero result identity unmodeled. Later value rounding is AFTER465E18, not actual delta. No live definitions, FPSCR, nonfinite conversion, eligibility, acquisition or saved result inferred."}


def below_capacity_predicate(ammo_bits, maximum_bits):
    ammo_bits, maximum_bits = CAPACITY["word"](ammo_bits), CAPACITY["word"](maximum_bits)
    def nan(bits):
        return bits & 0x7F800000 == 0x7F800000 and bits & 0x7FFFFF != 0
    result = False if nan(ammo_bits) or nan(maximum_bits) else (
        struct.unpack(">f", ammo_bits.to_bytes(4, "big"))[0] <
        struct.unpack(">f", maximum_bits.to_bytes(4, "big"))[0])
    return {"passes_ordered_below_capacity": result,
            "qualification": "Local comparison from explicit samples after separate hero/type gates. No ownership test, coupling to refill invocation, FPSCR/NaN exception model or full pickup eligibility."}


def inspect(elf_path, save_path=None, assets_path=None):
    elf = BINDINGS["Elf"](elf_path)
    expected = {
        0x2FF700: 0x80640040, 0x2FF710: 0x38800211,
        0x2FF724: 0x40820044, 0x2FF76C: 0x80FE009C,
        0x2FF774: 0x83BF1A68, 0x2FF788: 0x54C92036,
        0x2FF78C: 0x54C5103A, 0x2FF794: 0x7C7D2214,
        0x2FF7AC: 0x80BB000C, 0x2FF7B0: 0x889B0011,
        0x2FF7BC: 0x8102FFE0, 0x2FF7C0: 0xC05B0008,
        0x2FF7C4: 0x38800000, 0x2FF7C8: 0xEFC11028,
        0x2FF7D0: 0xC3E80014, 0x2FF7DC: 0xEFFF0072,
        0x2FF7E0: 0xC1A2FFDC, 0x2FF7E4: 0xFC3F6828,
        0x2FF7E8: 0xFC016FEE, 0x2FF7EC: 0xFD80F028,
        0x2FF7F0: 0xFFEC07AE, 0x2FF808: 0x2F040003,
        0x2FF80C: 0x419A0028, 0x2FF810: 0xFCA0FE5E,
        0x2FF814: 0xFCA02E9C, 0x2FF818: 0xC0E2FFE4,
        0x2FF81C: 0xFC65F828, 0x2FF820: 0xFCC5382A,
        0x2FF824: 0xFC9F29AE, 0x2FF828: 0xFFE327EE,
        0x2FF82C: 0xFC601850, 0x2FF830: 0xFFE327EE,
        0x2FF834: 0x81790018, 0x2FF838: 0x556A07BC,
        0x2FF840: 0x409E0260, 0x2FFAA8: 0x38A00000,
        0x2FFAC0: 0x38A0FFFF, 0x2FF85C: 0x801A0034,
        0x2FF864: 0x41820014, 0x2FF86C: 0x4186000C,
        0x2FF874: 0x409AFEB4,
        0x2FF670: 0x80EA1A68, 0x2FF684: 0xC3E90008,
        0x2FF694: 0xFC9F0800, 0x2FF698: 0x7C740026, 0x2FF69C: 0x54632FFE,
        0x466528: 0x5485103A, 0x46652C: 0x81230048,
        0x466530: 0x380502D0, 0x466538: 0x7C29242E,
        0xB86DC: 0x38E802D0, 0xB86E8: 0x7C2B342E,
        0x89FF00: 0x101E8D70, 0x89FEFC: 0, 0x89FF04: 0x3F800000,
        0x897B38: 0x101EFB20, 0x23E744: 0x913F1A68,
        0x84E24C: 0x86DD30, 0x86DD30: 0x2FF6C0, 0x86DD34: 0x89FF20,
        0x84E254: 0x86DD20, 0x86DD20: 0x2FF5F0, 0x86DD24: 0x89FF20,
        0x88E858: 0x10012D08, 0x88E85C: 0x85E980,
        0x85E980: 0xB8618, 0x85E984: 0x88FF38,
    }
    guards = {}
    for address, raw in expected.items():
        if elf.u32(address) != raw:
            raise ValueError(f"Ammo crate evidence changed at {address:#x}")
        guards[address] = elf.read(address, 4)
    if elf.string(0x10012D08) != "CrateAmmo":
        raise ValueError("CrateAmmo property identity changed")
    guards[0x10012D08] = elf.read(0x10012D08, 10)
    identity = next(e for e in BINDINGS["enum_exports"](elf) if e["id"] == 3)
    if identity["enum"] != "WPN_RAVAGER":
        raise ValueError("Crate rounding exception identity changed")
    for key, size in (("name_va", len(identity["enum"])+1), ("name_slot_va", 4), ("value_slot_va", 4), ("call_va", 4)):
        address = int(identity[key], 0)
        guards[address] = elf.read(address, size)
    for va, target in ((0x2FF714, 0x24F208), (0x2FF778, 0x463190),
                       (0x2FF7B4, 0x466500), (0x2FF7D4, 0x466528),
                       (0x2FF7FC, 0x465E18), (0x2FFAAc, 0x466B70),
                       (0x2FFAC4, 0x252B08), (0x2FF688, 0x463DE0),
                       (0x465E38, 0x463DE0)):
        raw = elf.u32(va)
        if raw >> 26 != 18 or not raw & 1 or BINDINGS["branch_target"](raw, va) != target:
            raise ValueError("Ammo crate call changed")
        guards[va] = elf.read(va, 4)
    for function, toc in ((0x2FF6C0, 0x89FF20), (0x2FF5F0, 0x89FF20),
                          (0x466528, 0x89FF20), (0x466500, 0x89FF20),
                          (0x465E18, 0x89FF20), (0x466B70, 0x89FF20),
                          (0xB8618, 0x88FF38), (0x23E650, 0x88FF38)):
        if elf.descriptors[function] != toc:
            raise ValueError("Ammo crate TOC changed")
        guards[function] = elf.read(function, elf.functions[elf.functions.index(function)+1]-function)
    report = {
        "confidence": "exact-build-native-crate-refill-request-and-separate-admission",
        "warning": "USA BCUS98127 v02.00 only. Static read-only evidence, not a pickup-placement catalog, full gameplay simulation, safe edit recipe or new writable field.",
        "record_selection": "Table84E24C->86DD30->2FF6C0 and adjacent84E254->86DD20->2FF5F0 establish two separate dispatch methods. Both require context+40 nonnull and low-byte24F208(context40,211) nonzero, then select hero+1A68 +20*actor+9C. Hero23E650 installs canonical101EFB20. For valid matching ID/index i, ammo is saved20*i+8. No universal item-ID bounds, ownership gate, complete pool/context safety or guarantee that the two methods are invoked together is proven.",
        "below_capacity": "2FF5F0 loads saved ammo before calling463DE0 maximum resolution, then extracts the ordered LT bit from FCMPU. Equality and unordered reject; strictly lower ordered ammo admits this local predicate. It does not read ownership or invoke2FF6C0. Helpers can change samples/definitions; saved ammo alone is not full pickup eligibility or active capacity.",
        "crate_property": "Native property registration88E858 names CrateAmmo at10012D08; getterB8618 reads indexed data+2D0+4*index. Complete466528 reads the same array through definition+48.2FF6C0 explicitly supplies index0, not the saved level. CrateAmmo is distinct from MaxAmmo at data+280 and is not a level-zero maximum-ammo calculation. No pickup-size default is guessed for absent configuration values.",
        "request_rule": "2FF6C0 first resolves maximum through466500 with raw saved level+11 and mask+C, then computes binary32 missing=max-ammo. It loads runtime101E8D70+14 factor and multiplies it by CrateAmmo[0], rounded by FMULS. For ordinary finite inputs it selects min(max(scaled CrateAmmo,0),missing), then calls465E18 clamped ADD BEFORE subsequent request rounding. There is no local floor1, ownership gate or call to2FF5F0. Negative missing can therefore select a negative addition request on a direct over-capacity invocation.465E18 resolves its own maximum from record ID/level/mask again; exact actual delta/new saved ammo, stable definitions and native nonfinite/FPSCR behavior are not inferred.",
        "post_add_rounding": "Only AFTER465E18 returns, selected ID3 skips local rounding; native enum independently names3 WPN_RAVAGER. All other selected IDs use FCTIDZ/FCFID and FSEL around constant1.0 to produce mathematical ceiling for bounded ordinary finite requests. This later local value is retained for downstream integer/helper/message work; it is not rounded ammo written by465E18, actual gained ammo, a conserved quantity or guaranteed displayed text. Nonfinite and out-of-range integer conversions remain unmodeled.",
        "later_publication": "After ammo and local rounding, definition+18 flag2 selects466B70(hero saved base,selected ID,refill0), followed by252B08(hero,ID,-1). These helpers can perform acquisition/progression work even after an earlier request0; no ownership/result final-state prediction. Later runtime UI-member+34 gate admits0/3/4 and otherwise returns AFTER the ammo/acquisition work, not before it. Subsequent messages, handles and callbacks are outside a complete consumer model; presentation rejection is not an ammo rollback.",
        "snapshot_limit": "CrateAmmo definition, runtime factor, valid context/selected ID, active maximum and invocation history are absent from the saved ammo snapshot. Viewing preserves all raw ammo, levels, masks, ownership and opaque record bytes; does not run the predicate, refill, acquire, normalize or infer pickup counts.",
        "recommended_annotations": [
            {"va": "0x2ff5f0", "name": "TOD_ammo_crate_ordered_below_capacity_predicate", "comment": "Qualified hero/type context selects saved20*actor9C+8 and extracts ordered LT against463DE0 max. Equal/unordered false, no ownership read or local refill call; not full pickup eligibility."},
            {"va": "0x2ff7fc", "kind": "comment", "name": "TOD_ammo_crate_unrounded_request_before_later_rounding", "comment": "Calls465E18 ADD with finite min(max(runtime factor*CrateAmmo[0],0), max-ammo), FMULS/FSUBS rounding. No floor1, local ownership/below-capacity gate, exact delta or stable definition assumption. Rounding below is AFTER this store path."},
            {"va": "0x2ff810", "kind": "comment", "name": "TOD_ammo_crate_post_add_request_ceiling_except_id3", "comment": "After465E18 returned, ID3 WPN_RAVAGER bypasses; other IDs FCTIDZ/FCFID/FSEL select ceil for bounded finite request. Later local/helper value, not rounded saved ammo or exact acquired amount. Native nonfinite conversion unmodeled."},
            {"va": "0x2ffaac", "kind": "comment", "name": "TOD_ammo_crate_flag2_acquisition_after_ammo_request", "comment": "Definition flag2 selects466B70(base,ID,refill0) after ammo request and local rounding, then252B08 integration. Later UI gate can return only after these operations; no ownership/final-state or rollback claim."},
        ],
        "instruction_guards": [{"va": hex(a), "bytes": raw.hex().upper()} for a, raw in sorted(guards.items())],
    }
    if assets_path is not None:
        raw = (Path(assets_path) / "weapon.csv").read_bytes()
        digest = hashlib.sha256(raw).hexdigest().upper()
        if digest != CONFIGS["REFERENCE_HASHES"]["weapon.csv"]:
            raise ValueError("Not fingerprinted reference weapon.csv")
        weapons = CONFIGS["parse_weapons"](raw)
        # Reuse the existing exact constructor/property relationship, never CSV order.
        root = elf.u32(0x88FAFC)
        names = {root + p["parent_offset"]: p["name"] for p in BINDINGS["config_properties"](elf)}
        catalog = []
        for call in BINDINGS["constructor_calls"](elf):
            name = names.get(int(call["config_va"], 0))
            if name is None:
                raise ValueError("Unresolved native constructor configuration")
            values = weapons.get(name, {}).get("variables", {}).get("CrateAmmo", [])
            catalog.append({"id": call["id"], "config": name, "crate_ammo_level0": values[0] if values else None})
        if len(catalog) != 32 or {c["id"] for c in catalog} != set(range(32)):
            raise ValueError("Incomplete constructor-based CrateAmmo catalog")
        catalog.sort(key=lambda c: c["id"])
        report["asset_observation"] = {"weapon_csv_sha256": digest, "catalog": catalog,
            "qualification": "Fingerprint-verified declared CrateAmmo[0] only; missing values stay unknown. Constructor-based IDs, not CSV order. No live runtime overrides/factor, pickup amount, capacity or event history inferred."}
    if save_path is not None:
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i*20)[0] != i for i in range(32)):
            raise ValueError("Not verified plaintext inventory layout")
        report["save_observation"] = {"sha256": hashlib.sha256(raw).hexdigest().upper(),
            "records": [{"id": i, "ammo_bits": raw[i*20+8:i*20+12].hex().upper(),
                         "mask_bits": raw[i*20+12:i*20+16].hex().upper(), "ownership": raw[i*20+16],
                         "stored_level": raw[i*20+17], "opaque_tail": raw[i*20+18:i*20+20].hex().upper()} for i in range(32)],
            "qualification": report["snapshot_limit"]}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--assets", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save, args.assets), indent=2, allow_nan=False))
