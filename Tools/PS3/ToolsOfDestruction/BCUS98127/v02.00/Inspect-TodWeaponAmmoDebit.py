"""Read-only exact-build borrowed inventory binding, ammo admission and debit.

Reference predicates take explicit runtime samples; saved ammo is not eligibility.
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


def presence(value):
    if type(value) is not bool:
        raise ValueError("Expected explicit record-presence boolean")
    return value


def unordered(bits):
    return bits & 0x7F800000 == 0x7F800000 and bits & 0x7FFFFF != 0


def availability_plan(global_word, record_present, definition_flags, request_bits, ammo_bits):
    """Local CR predicate for explicitly supplied binary32-representable FPR samples."""
    global_word, definition_flags = word(global_word), word(definition_flags)
    request_bits, ammo_bits = word(request_bits), word(ammo_bits)
    record_present = presence(record_present)
    if global_word:
        route, passes = "anonymous runtime-word bypass", True
    elif not record_present:
        route, passes = "absent-record bypass", True
    elif definition_flags & 0x10:
        route, passes = "definition-flag10 bypass", True
    else:
        request = None if unordered(request_bits) else struct.unpack(">f", request_bits.to_bytes(4, "big"))[0]
        ammo = None if unordered(ammo_bits) else struct.unpack(">f", ammo_bits.to_bytes(4, "big"))[0]
        if request is not None and request > 0:
            route, passes = "ordered ammo >= positive request", ammo is not None and ammo >= request
        else:
            route, passes = "ordered ammo > zero", ammo is not None and ammo > 0
    return {"route": route, "passes_local_predicate": passes,
            "qualification": "Explicit supplied samples only, including binary32-representable FPR requests. Not a live eligibility verdict, arbitrary binary64 FPR model, FPSCR/NaN exception contract or execution of later callbacks/debit."}


def debit_request_plan(record_present, request_bits):
    """Finite binary32-representable argument selection, not a resulting ammo preview."""
    record_present, request_bits = presence(record_present), word(request_bits)
    if record_present and request_bits & 0x7F800000 == 0x7F800000:
        raise ValueError("Nonfinite debit execution preview is not supported")
    return {"operation": "clamped add" if record_present else "none",
            "delta_request_bits": f"{request_bits ^ 0x80000000:08X}" if record_present else None,
            "qualification": "Null record skips before FNEG. Nonnull negates the supplied finite binary32-representable amount then calls465E18; no exact saved delta, active maximum, binary64 rounding, FPSCR or firing-cost prediction."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    expected = {
        0x1F5DFC: 0x809D1A68, 0x466D38: 0x90830004, 0x466D3C: 0x4E800020,
        0x4675D8: 0x80630140, 0x467620: 0x811C0004,
        0x467624: 0x5466103A, 0x46762C: 0x547D2036,
        0x467634: 0x7D86EA14, 0x46763C: 0x7CAC4214,
        0x467648: 0x78BB0020, 0x4676B8: 0x7F63DB78,
        0x463AF4: 0x7C7A1B78, 0x463AF8: 0x80630000,
        0x463B7C: 0x81690040, 0x463B80: 0x934B002C, 0x463B84: 0x936B0030,
        0x46AD8C: 0x8003002C, 0x46AD90: 0x2F800000,
        0x46AD94: 0x78030020, 0x46AD98: 0x419E0010, 0x46AD9C: 0xFC200850,
        0x46AFC8: 0x913D002C, 0x46AFCC: 0x913D0030,
        0x46A420: 0x812260AC, 0x46A424: 0x80090000,
        0x46A428: 0x2F800000, 0x46A42C: 0x409E004C,
        0x46A430: 0x8163002C, 0x46A434: 0x2C0B0000, 0x46A438: 0x41820040,
        0x46A43C: 0x80A30030, 0x46A440: 0x80850018,
        0x46A444: 0x548306F6, 0x46A448: 0x2C830000, 0x46A44C: 0x4086002C,
        0x46A450: 0xC1A260B0, 0x46A454: 0xFF016800, 0x46A458: 0x4099002C,
        0x46A464: 0xC0060008, 0x46A468: 0xFF800800,
        0x46A46C: 0x4FDDF382, 0x46A470: 0x409E000C,
        0x46A478: 0x38600001, 0x46A48C: 0xC0270008,
        0x46A490: 0xFC016800, 0x46A494: 0x4081FFE8,
        0x8A5FCC: 0x103698E0, 0x8A5FD0: 0, 0x8A5F6C: 0, 0x8A5F40: 0x3F800000,
        0x469024: 0xC3E2604C, 0x469028: 0xFC20F890,
        0x469078: 0x409E0038, 0x4690C0: 0x809B0068, 0x4690C8: 0x40820058,
        0x4690D0: 0xC3C26020, 0x4690D4: 0x90BB00F4, 0x4690D8: 0xFC20F090,
        0x897B38: 0x101EFB20, 0x23E744: 0x913F1A68,
        0x12080: 0xF8410028, 0x12084: 0x3C420001, 0x12088: 0x3842FFE8,
        0x108E0: 0xF8410028, 0x108E4: 0x3C420001, 0x108E8: 0x3842FFE8,
    }
    guards = {}
    for address, raw in expected.items():
        if elf.u32(address) != raw:
            raise ValueError(f"Weapon ammo debit evidence changed at {address:#x}")
        guards[address] = elf.read(address, 4)
    for address, target in ((0x1F5E00, 0x12080), (0x1208C, 0x466D38),
                            (0x1F5B74, 0x108E0), (0x108EC, 0x4675A0),
                            (0x4676BC, 0x463AD0), (0x463B08, 0x463190),
                            (0x463B6C, 0x250528), (0x46ADA0, 0x465E18),
                            (0x465E38, 0x463DE0), (0x469060, 0x46A420),
                            (0x4690B8, 0x46C158), (0x4690E0, 0x46AD80)):
        raw = elf.u32(address)
        if BINDINGS["branch_target"](raw, address) != target or bool(raw & 1) != (address not in (0x1208C, 0x108EC)):
            raise ValueError("Weapon ammo call/thunk changed")
        guards[address] = elf.read(address, 4)
    for function, toc in ((0x1F5DB8, 0x88FF38), (0x1F5B68, 0x88FF38),
                          (0x23E650, 0x88FF38), (0x466D38, 0x89FF20),
                          (0x4675A0, 0x89FF20), (0x463AD0, 0x89FF20),
                          (0x46A420, 0x89FF20), (0x46AD80, 0x89FF20),
                          (0x46AF58, 0x89FF20),
                          (0x465E18, 0x89FF20), (0x469018, 0x89FF20)):
        if elf.descriptors[function] != toc:
            raise ValueError("Weapon ammo function TOC changed")
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    report = {
        "confidence": "exact-build-native-borrowed-record-and-ammo-branches",
        "warning": "USA BCUS98127 v02.00 only. Read-only static evidence; no gameplay acceptance, per-shot pricing or new editing permission.",
        "record_binding": "Hero23E650 installs canonical101EFB20 at+1A68. Owner setup1F5DB8 supplies hero+1A68 through12080->466D38, whose complete body stores that pointer at inventory+4. Callback1F5B68->108E0->4675A0 selects inventory+4 +20*runtime selected index+140; on the creation branch4676BC passes this record to463AD0. Binder463AD0 resolves the definition from record+0 ID, creates a runtime object through250528, then explicitly installs the SAME borrowed record at object40->weapon+2C and definition at weapon+30. No copy, universal item-index bounds, ownership admission, null creation safety, all runtime instances or callback immutability are proven. For valid canonical ID/index i, saved ammo is20*i+8; these runtime pointer members are not GAME.SAV offsets.",
        "debit_rule": "Complete46AD80 skips null weapon+2C. Otherwise FNEG negates incoming FPR amount and calls465E18, the clamped ADD leaf, not4661F8's subtraction leaf. Positive amount requests a negative delta; negative amount requests an addition. The leaf resolves maximum through463DE0, adds and clamps before its saved record+8 store. No local sign/ownership check or call to46A420 exists in46AD80; no exact delta, universal per-shot cost, meaningful success return, active maximum or native nonfinite execution model inferred.",
        "availability_rule": "Complete call-free46A420 returns1 for ANY nonzero anonymous runtime word103698E0, absent weapon+2C record, or definition+18 flag0x10. Otherwise ordered positive FPR request requires ordered saved ammo>=request (equality passes). A zero/negative OR UNORDERED request takes the GT-clear branch and requires ordered saved ammo>0. Signed zero thus requires positive ammo; unordered ammo rejects both tested routes. An unordered request can pass with positive ammo, but this is only CR branch behavior, not valid gameplay input or FPSCR exception/payload emulation. Ownership, stored level and maximum are not read here. Definition pointer validity is assumed after the bypass gates; anonymous global meaning remains unknown, not an infinite-ammo cheat label.",
        "caller_boundary": "Representative469018 loads request+0 from8A5F6C and calls46A420 at469060. Failure returns before its later explicit debit. Success calls external46C158, then samples weapon+68; only the null branch explicitly publishes weapon+F4=1 and calls46AD80 with1.0 from8A5F40 at4690E0. Thus this caller's request0 predicate is not an ammo>=1 check; positive fractional ammo can pass that local predicate. Callback effects, record/definition/global changes, nonnull+68 route, weapon identity and overall firing outcome remain unmodeled. The check and debit are separate, not an atomic acceptance/charge contract.",
        "runtime_limit": "Viewing shows saved ammo bits only. Runtime global, active record binding, definition flags/capacity, selected index, weapon+68 and intervening callbacks cannot be reconstructed from GAME.SAV. The shared path does not imply every gadget invokes it. The binder stores pointer/definition after object creation; initialization clears weapon+2C/+30 earlier, so pointer lifetime and rebinds remain qualified. Reference plans accept explicit supplied binary32-representable request samples, not arbitrary native binary64 FPR arguments. No eligibility, exact debit, refill, repair or runtime mutation executes.",
        "recommended_annotations": [
            {"va": "0x463ad0", "name": "TOD_weapon_create_and_bind_borrowed_inventory_record", "comment": "Resolves definition from supplied record ID; after250528 creation installs same record at object+40->weapon+2C and definition+30. Canonical owner path1F5DB8/466D38/4675A0 established. Qualified creation/index/instance lifetime, not copied save or ownership admission."},
            {"va": "0x46ad80", "name": "TOD_weapon_ammo_negated_request_to_clamped_add", "comment": "Null borrowed record+2C skips. Otherwise FNEG supplied FPR then465E18 clamped ADD to saved+8; no local availability/sign/ownership check. Negative request adds; not universal per-shot cost or exact delta."},
            {"va": "0x46a420", "name": "TOD_weapon_ammo_local_admission_predicate", "comment": "Runtime global nonzero/recordless/definition flag10 bypass. Ordered positive request requires ammo>=request; zero/negative/unordered request requires ordered ammo>0. No ownership/max/mutation; not full firing eligibility or native exception model."},
            {"va": "0x4690e0", "kind": "comment", "name": "TOD_weapon_zero_request_check_then_one_debit_branch", "comment": "469018 earlier checks request+0 via46A420, then external46C158. Null runtime+68 branch requests1.0 via46AD80; predicate and later debit differ, fractional ammo may pass check. No stable samples, weapon identity or per-shot outcome inferred."},
        ],
        "instruction_guards": [{"va": hex(a), "bytes": raw.hex().upper()} for a, raw in sorted(guards.items())],
    }
    if save_path is not None:
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not verified plaintext inventory layout")
        report["save_observation"] = {"sha256": hashlib.sha256(raw).hexdigest().upper(),
            "records": [{"id": i, "ammo_offset": hex(i * 20 + 8), "ammo_bits": raw[i*20+8:i*20+12].hex().upper(),
                         "ownership": raw[i*20+16], "stored_level": raw[i*20+17],
                         "opaque_tail": raw[i*20+18:i*20+20].hex().upper()} for i in range(32)],
            "qualification": "Raw saved snapshot only; no runtime eligibility, anonymous global, binding presence, current maximum, firing count or actual debit inferred."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
