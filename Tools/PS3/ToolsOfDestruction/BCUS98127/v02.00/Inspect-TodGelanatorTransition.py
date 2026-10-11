"""Read-only exact-build Gelanator paired ammo debit/refund and runtime gates.

Branch plans accept explicit detached runtime samples, never infer them from saves.
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


def byte(value):
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError("Expected raw runtime byte")
    return value


def entry_route(entry_latch, record_present, ammo_bits, actor_latch):
    """Selected local early branch, after state2 admission and record resolution."""
    entry_latch, actor_latch, ammo_bits = byte(entry_latch), byte(actor_latch), word(ammo_bits)
    if type(record_present) is not bool:
        raise ValueError("Expected explicit record-presence boolean")
    zero = ammo_bits & 0x7FFFFFFF == 0
    wait = entry_latch != 0 and record_present and zero == (actor_latch == 0)
    return {"explicit_entry_latch_after": 0,
            "route": "early state3 wait" if wait else "continue toward phase gate",
            "qualification": "Selected local branch only, after post-base-update state2 and qualified record selection. Unordered ammo is not equal to zero. Later callbacks may change state/samples; no full invocation or native nonfinite exception emulation."}


def phase_gate(actor_latch, phase_bits):
    actor_latch, phase_bits = byte(actor_latch), word(phase_bits)
    threshold = 31.0 if actor_latch == 0 else 30.0
    unordered = phase_bits & 0x7F800000 == 0x7F800000 and phase_bits & 0x7FFFFF != 0
    value = struct.unpack(">f", phase_bits.to_bytes(4, "big"))[0]
    return {"threshold": int(threshold), "passes_ordered_branch": not unordered and value >= threshold,
            "qualification": "Predicate from explicit runtime sample only. No frames/seconds, source validity, FPSCR/NaN exceptions, callback execution or later latch sample inferred."}


def transition_plan(record_present, actor_latch):
    """Transaction selection only after the separate ordered phase gate passed."""
    actor_latch = byte(actor_latch)
    if type(record_present) is not bool:
        raise ValueError("Expected explicit record-presence boolean")
    return {"ammo_operation": ("subtract" if actor_latch == 0 else "add") if record_present else "none",
            "request_bits": "3F800000" if record_present else None,
            "explicit_actor_latch_after": (1 if actor_latch == 0 else 0) if record_present else actor_latch,
            "qualification": "Qualified initialized item27 record only, post-phase admission. Request1.0 still passes the definition-dependent ammo clamp; no exact delta, round-trip conservation, per-shot rule, helper final state or save mutation predicted."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    expected = {
        0x250C78: 0xF8410028, 0x250C7C: 0x3C420001,
        0x250C80: 0x3842FF3C, 0x250C84: 0x4843F2E4,
        0x43A500: 0x3800001B, 0x43A508: 0x901D0044,
        0x43A708: 0x813E0000, 0x43A70C: 0x2F890002, 0x43A710: 0x419E0030,
        0x43A7AC: 0x889E0008, 0x43A7B8: 0x993E0008, 0x43A7BC: 0x418200A8,
        0x43A7D0: 0xC1AA0008, 0x43A7D4: 0xFF0D0000, 0x43A7D8: 0x419A01BC,
        0x43A7DC: 0x881F0050, 0x43A7E4: 0x409E01BC,
        0x43A864: 0x8B5F0050, 0x43A86C: 0x409A00CC,
        0x43A870: 0xC3E2543C, 0x43A938: 0xC3E25440,
        0x43A880: 0xFF9F0800, 0x43A884: 0x4FDCF382, 0x43A888: 0x409EFE8C,
        0x43A89C: 0x90FE0000, 0x43A8A0: 0x9BBE0008, 0x43A8A8: 0xD05E0004,
        0x43A8AC: 0x41820048, 0x43A8B0: 0x8BDF0050, 0x43A8B8: 0x41860108,
        0x43A8C0: 0xC0225420, 0x43A8D0: 0x9B9F0050,
        0x43A970: 0x806A1A68, 0x43A978: 0x419EFE30, 0x43A97C: 0x83BF0044,
        0x43A980: 0x57BC2036, 0x43A984: 0x57A7103A, 0x43A98C: 0x7F836214,
        0x43A994: 0x897F0050, 0x43A99C: 0x40820048,
        0x43A9C4: 0xC0225420, 0x43A9D0: 0x9BBF0050,
        0x43A398: 0x99630050, 0x43A448: 0x98030050,
        0x465E48: 0xEFFF202A, 0x465E5C: 0xD1BD0008,
        0x466228: 0xED84F828, 0x46623C: 0xD1BD0008,
        0x8A5340: 0x3F800000, 0x8A535C: 0x41F80000,
        0x8A5360: 0x41F00000, 0x8A5364: 0,
        0x853A30: 0x8734A8, 0x8734A8: 0x43A4D0, 0x8734AC: 0x89FF20,
        0x853A38: 0x8734B8, 0x8734B8: 0x43A6C0, 0x8734BC: 0x89FF20,
        0x4933D0: 0xC0226BE4, 0x8A6B04: 0xBF800000,
        0x897B38: 0x101EFB20, 0x23E744: 0x913F1A68,
        0x88B3C0: 0x100002D0, 0x88B3C4: 0x41D80000,
    }
    guards = {}
    for address, raw in expected.items():
        if elf.u32(address) != raw:
            raise ValueError(f"Gelanator transition evidence changed at {address:#x}")
        guards[address] = elf.read(address, 4)
    for address, target in ((0x43A9C8, 0x4661F8), (0x43A8C8, 0x465E18),
                            (0x43A878, 0x493388), (0x43A8F0, 0x43A548),
                            (0x43A6F8, 0x250C78), (0x465E38, 0x463DE0),
                            (0x466218, 0x463DE0), (0x493398, 0x496690),
                            (0x4933AC, 0x491CD8), (0x80D1C, 0x12990)):
        raw = elf.u32(address)
        if not raw & 1 or BINDINGS["branch_target"](raw, address) != target:
            raise ValueError("Gelanator transition call changed")
        guards[address] = elf.read(address, 4)
    for function, toc in ((0x43A6C0, 0x89FF20), (0x43A4D0, 0x89FF20),
                          (0x43A378, 0x89FF20), (0x43A428, 0x89FF20),
                          (0x4661F8, 0x89FF20), (0x465E18, 0x89FF20),
                          (0x493388, 0x89FF20), (0x68FF68, 0x8AFE5C),
                          (0x23E650, 0x88FF38)):
        if elf.descriptors[function] != toc:
            raise ValueError("Gelanator transition TOC changed")
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    guards[0x80D14] = elf.read(0x80D14, 12)
    guards[0x100002D0] = elf.read(0x100002D0, len("WPN_GELANATOR") + 1)
    if [r["enum"] for r in BINDINGS["enum_exports"](elf) if r["id"] == 27] != ["WPN_GELANATOR"]:
        raise ValueError("Item27 native identity changed")
    report = {
        "confidence": "exact-build-native-paired-transition",
        "warning": "USA BCUS98127 v02.00 only. No native execution, active-mode reconstruction, gameplay naming, firing cost or new editing permission.",
        "record_selection": "Associated table853A30->8734A8->43A4D0 publishes literal27 to actor+44. Native export80D1C independently names27 WPN_GELANATOR. Update853A38->8734B8->43A6C0 selects hero+1A68 +20*actor44 after qualified pool handle, actor40, type/message211 and nonnull saved-pointer checks. Hero bind23E650 installs canonical101EFB20 at+1A68. For the initialized27 selection, record21C/ammo+8 is saved224. No local item-ID range/ownership gate is established; valid hero/handle and unchanged initialized selection are required, not inferred from a save snapshot.",
        "entry_boundary": "Base call250C78->68FF68 sets runtime parent+68 flag20 before actor state+20 is tested for exactly2. For admitted state2, old entry latch+28 is sampled then cleared at43A7B8. Only if that sample is nonzero and the record exists, saved ammo equality to0 and actor latch+50 can select an early state3 wait: zero ammo/latch0 OR nonzero-or-unordered ammo/latch-nonzero. Entry-latch0 skips this local ammo check entirely. Signed zero compares equal; unordered is not a native payload/exception contract. Helper work and recordless paths can still reach the separate phase gate; this is not universal zero-ammo rejection.",
        "phase_gate": "43A864 samples runtime actor+50: zero loads threshold31 from8A535C; ANY nonzero loads30 from8A5360. Call493388 resolves parent+94 through496690; nonnull delegates491CD8, null returns-1 from8A6B04. fcmpu compares threshold against returned value, and cror LT|EQ then bne rejects less-than-threshold and unordered values. Equality admits. Units, active animation, deeper helper effects and sampling cadence remain unverified; the sample cannot be read from GAME.SAV.",
        "paired_ammo": "After the ordered phase gate, state3/entry latch1/configured runtime+24 are published before record presence and a NEW actor+50 sample. Record present/latch0 calls4661F8 with1.0 from8A5340 at43A9C8, then stores actor+50=1. Record present/ANY nonzero calls465E18 with the SAME1.0 at43A8C8, then stores actor+50=0. Recordless skips both operations and these explicit actor-latch stores. Both setters resolve maximum through463DE0 and clamp before their saved+8 store. Thus request1 is not guaranteed actual delta1 or conserved refund, especially at capacity, malformed maxima or nonfinite inputs. Subsequent43A548 and runtime handle cleanup are outside a full final-state model; no per-shot claim.",
        "runtime_limit": "Actor+20/+24/+28/+44/+50, parent phase and resource handles are runtime members, not offsets into GAME.SAV. Phase-gate and transaction latch reads are separate samples around a helper, not one guaranteed immutable byte. Siblings43A378/43A428 explicitly write actor+50=0/1 without directly calling the two saved ammo setters; their animation/helper effects remain qualified. Saved224 and ownership22C do not establish a reservation, active mode, toggle count or runtime latch. The previously mapped load reset also requests Gelanator ammo0 through the absolute setter, independently of this pair.",
        "recommended_annotations": [
            {"va": "0x43a508", "kind": "comment", "name": "TOD_Gelanator_transition_select_native_item27", "comment": "Publishes literal27 at actor+44; native WPN_GELANATOR export independently confirms identity. Qualified hero+1A68 +20*ID later selects saved record21C/ammo224. Not all actor instances or raw ID safety."},
            {"va": "0x43a9c8", "kind": "comment", "name": "TOD_Gelanator_transition_ammo_debit_then_runtime_latch", "comment": "After ordered phase gate, record present and NEW actor+50 sample zero: subtract request1.0 through4661F8, then actor+50=1. Maximum clamp applies; not exactly1 actual delta or per-shot cost."},
            {"va": "0x43a8c8", "kind": "comment", "name": "TOD_Gelanator_transition_ammo_refund_then_runtime_latch", "comment": "Record present/NEW actor+50 sample ANY nonzero: add request1.0 through465E18, then actor+50=0. Clamped request, not conserved refund or complete final callback state."},
            {"va": "0x43a888", "kind": "comment", "name": "TOD_Gelanator_transition_ordered_runtime_threshold_gate", "comment": "FCMPU threshold<=returned phase via LT|EQ admits equality, rejects unordered. Latch0 selects31, any nonzero30. Units/source runtime state absent from GAME.SAV; transaction rereads latch after helper."},
            {"va": "0x43a7b8", "kind": "comment", "name": "TOD_Gelanator_entry_latch_clear_before_qualified_ammo_gate", "comment": "Clears runtime actor+28 after sampling it. Sample0 skips local ammo-equality test. Sample-nonzero/record present can choose early state3 wait; not universal zero-ammo rejection or saved latch."},
        ],
        "instruction_guards": [{"va": hex(a), "bytes": raw.hex().upper()} for a, raw in sorted(guards.items())],
    }
    if save_path is not None:
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not verified plaintext inventory layout")
        report["save_observation"] = {"sha256": hashlib.sha256(raw).hexdigest().upper(),
            "id": 27, "ammo_bits": raw[0x224:0x228].hex().upper(), "mask_bits": raw[0x228:0x22C].hex().upper(),
            "ownership": raw[0x22C], "stored_level": raw[0x22D],
            "qualification": "Snapshot only; no phase, runtime latch, admitted record, active mode, exact debit/refund or invocation history inferred."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
