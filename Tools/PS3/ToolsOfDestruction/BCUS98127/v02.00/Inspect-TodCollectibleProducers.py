"""Read-only exact-build collectible callers and bonus-target mask publication."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
MESSAGE_BIT = 1 << 22


def word(value, bits=32):
    if type(value) is not int or not 0 <= value < 1 << bits:
        raise ValueError("Expected bounded raw unsigned word")
    return value


def publication_preview(progress, pending, index):
    """Immutable slw/OR/ANDC leaf only; no lookup or post-callback prediction."""
    progress, pending, index = map(word, (progress, pending, index))
    effective = index & 63
    bit = 1 << effective if effective < 32 else 0
    return {"effective_bit": bit, "saved_progress_after_store": progress | bit,
            "runtime_pending_after_store": pending & (~bit & 0xFFFFFFFF),
            "qualification": "Pre-lookup stores only. Runtime pending is reread after the native lookup; no final state or target identity inferred."}


def reward_gate_preview(pending_after_lookup, flag_word_after_lookup, local_mask_at_test):
    """Separate supplied observations, not a callback-free full collector simulator."""
    pending = word(pending_after_lookup)
    flags = word(flag_word_after_lookup, 64)
    local = word(local_mask_at_test)
    if pending:
        requested = not bool(flags & MESSAGE_BIT)
        return {"grant_requested": False, "message_lookup_id": 0x648 if requested else None,
                "flag_word_after_local_store": flags | MESSAGE_BIT if requested else flags}
    requested = not bool(local & 1)
    return {"grant_requested": requested, "message_lookup_id": 0x348 if requested else None,
            "flag_word_after_local_store": flags}


def dispatch_preview(index):
    """375BD8 skips collection only for raw FFFFFFFF; no scene/API admission verdict."""
    return word(index) != 0xFFFFFFFF


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}
    expected = {
        0x8A011C: 0x101EFB20, 0x8A1AC4: 0x101EFB20, 0x89F1B8: 0x101EFB20,
        0x304C80: 0x900300AC, 0x304C88: 0x80640040,
        0x304C9C: 0x38800416, 0x304CA8: 0x5463063E, 0x304CB0: 0x40820030,
        0x304D00: 0x2C8302F4, 0x304D04: 0x41860060,
        0x304D10: 0x812201FC, 0x304D14: 0x809E00C4,
        0x304D18: 0x5460502A, 0x304D1C: 0x54631838,
        0x304D20: 0x7C8407B4, 0x304D2C: 0x3B7E0488,
        0x304DA4: 0x4BF4D4F5, 0x304E18: 0x4E800421, 0x304E20: 0x4BFFFEE8,
        0x304A8C: 0x801E00C4, 0x304A90: 0x2F800000, 0x304A94: 0x419C00AC,
        0x304AAC: 0x836201FC, 0x304AB0: 0x813E00C4,
        0x304AC8: 0x3B5C0488, 0x304AE0: 0x40860048,
        0x304AEC: 0x919E00AC, 0x304AF0: 0x919E00B0,
        0x364328: 0x80640324, 0x364330: 0x83E21BA4,
        0x364334: 0x7F6B1830, 0x364338: 0x80DD00FC,
        0x36433C: 0x3D5F0001, 0x364344: 0x7CC95878,
        0x364348: 0x913D00FC, 0x36434C: 0x80AA8728,
        0x364350: 0x7CA45B78, 0x364354: 0x908A8728,
        0x364360: 0x801D00FC, 0x36436C: 0x419E012C,
        0x364370: 0xE93F5548, 0x364374: 0x55260252,
        0x36437C: 0x419E002C, 0x3643A8: 0x653A0040,
        0x3643B0: 0xFB5F5548, 0x3643E8: 0x38800648,
        0x3644A0: 0x83E21BA4, 0x3644A4: 0x5460502A,
        0x3644A8: 0x547D1838, 0x3644AC: 0x38800000,
        0x3644B8: 0x399A0488, 0x3644CC: 0x5468063E,
        0x3644D4: 0x4082FEAC, 0x3644D8: 0x38800000,
        0x364520: 0x38800348, 0x364548: 0x4BFFFEC8,
        0x375C04: 0x801F0324, 0x375C08: 0x2F80FFFF, 0x375C10: 0x419E0014,
        0x2D1490: 0x8062F268, 0x2D1494: 0x3D230009, 0x2D1498: 0x806906E8,
        0x35DE08: 0x2B84001F, 0x35DE1C: 0x419D0018,
        0x35DE20: 0x808303EC, 0x35DEE8: 0x912303EC,
        0x252E1C: 0x3C42FFFF, 0x252E20: 0x38420018,
        0x251CBC: 0x3C420001, 0x251CC0: 0x3842FF3C,
        0x61B718: 0x80630008,
        0x2A384: 0xC02291CC, 0x297B8C: 0xC022A438,
        0x889104: 0x438B0000, 0x89A358: 0x438B0000,
        0x8A6890: 0x101EFB20, 0x489F90: 0x83A26970,
        0x489F80: 0x3B800000, 0x489FC4: 0x3FBD0001,
        0x489FF0: 0x939D8730, 0x489FF4: 0x939D8728, 0x489FF8: 0x939D872C,
    }
    for address, value in expected.items():
        if elf.u32(address) != value:
            raise ValueError(f"Collector evidence changed at {address:#x}")
        guards[address] = elf.read(address, 4)
    calls = ((0x304CA0, 0x24F208, True), (0x304CF8, 0x251CB8, True),
             (0x304D08, 0x2D1490, True), (0x304D34, 0x35DEB0, True),
             (0x304AA4, 0x2D1490, True), (0x304AD0, 0x35DE08, True),
             (0x364358, 0x252E18, True), (0x364498, 0x2D1490, True),
             (0x3644C4, 0x35DE08, True), (0x3644E0, 0x35DEB0, True),
             (0x3643F0, 0x252298, True), (0x364528, 0x252298, True),
             (0x375C1C, 0x364300, True), (0x252E24, 0x1E1298, False),
             (0x251CC4, 0x61B718, False),
             (0x489FE0, 0x2CDBB0, True), (0x489FFC, 0x465DC0, True))
    for address, target, linked in calls:
        raw = elf.u32(address)
        if BINDINGS["branch_target"](raw, address) != target or bool(raw & 1) != linked:
            raise ValueError("Collector linkage changed")
        guards[address] = elf.read(address, 4)
    for function in (0x304A40, 0x304C58, 0x364300, 0x375BD8, 0x2D1490, 0x35DE08, 0x489F68):
        if elf.descriptors[function] != 0x89FF20:
            raise ValueError("Collector saved-pointer TOC changed")
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    name = elf.string(0x10002858)
    if name != "SC_PLAYED_BONUS_TARGET_MSG":
        raise ValueError("Collector message-latch enum changed")
    guards[0x10002858] = elf.read(0x10002858, len(name) + 1)
    for address in (0x889100, 0x89A354):
        if elf.u32(address) != 0x10002858:
            raise ValueError("Collector enum name link changed")
        guards[address] = elf.read(address, 4)
    report = {
        "confidence": "exact-build-native-flow",
        "warning": "Static USA v02.00 evidence only. No target/pickup locations, universal acquisition rule, current runtime pending set, callback effects, message playback success, native execution or edit-safety verdict. Original raw bits are preserved.",
        "saved_progress": {"offset": "0x8728", "type": "u32 BE", "label": "Bonus-target progress mask",
                           "producer_va": "0x364300", "rule": "Index from runtime object+324 selects a PPC slw bit; clear that bit from runtime owner+FC, then OR it into saved8728. The saved word and pending word are separate. Shift uses low six bits: counts32..63 yield zero; counts64..95 alias0..31. No local target-index range guard, count or identities are recovered."},
        "dispatch": "375BD8 tests object+324 against raw FFFFFFFF after its preceding helper. Only that sentinel skips364300; it is not a signed nonnegative-index check. Another helper follows the dispatch. Reached native stores are not proof every supplied index is a real target.",
        "reset": {"va": "0x489f68", "cleared_offsets": ["0x8730", "0x8728", "0x872c"],
                  "rule": "Canonical saved pointer8A6890 is held across2CDBB0. Instructions489FF0..489FF8 store literal zero to saved8730,8728,872C before465DC0. This is a reached native reset boundary, not a lifetime history bank, default proof or full function simulation. The two neighboring words remain semantically unnamed; preceding/following callbacks and reset invocation causes are outside this leaf claim."},
        "after_lookup": "After publishing both masks,364358 calls252E18 (TOC89FF20→88FF38, target1E1298), then rereads runtime owner+FC at364360. A preview of the pre-lookup ANDC result cannot predict the post-lookup branch. Active pending set and lookup/callback effects are not serialized at8728.",
        "partial": {"flag_id": 278, "enum": name, "word_offset": "0x5548", "bit": 22, "message_lookup_id": "0x648",
                    "rule": "If reread pending is nonzero, test saved BE64 bit22 at5548. If already set, return; otherwise store it before runtime lookup/virtual message request. This is a message latch, not a target-completion or gold-bolt ownership bit. Literal648 is a native lookup ID, not recovered text or proof playback succeeded."},
        "complete": {"local_id": 0, "message_lookup_id": "0x348",
                     "rule": "If reread pending is zero, call2D1490 to read saved destination906E8 and form world record488+selector*408. Test local gold-bolt bit0 through35DE08; if present, return without the explicit grant/message request. Otherwise call35DEB0 with localID0 before the later348 lookup/virtual request. The leaf can separately request skill46. This caller does not test saved8728 for an all-bits mask and does not establish a total target count. Saved destination is not a guaranteed current planet; no native local world bounds clamp is present."},
        "direct_local_collector": {"producer_va": "0x304c58", "initializer_va": "0x304a40",
            "rule": "304C58 first clears runtime+AC even when admission later fails. It requires a nonnull context+40 and a nonzero low-byte type predicate for numeric416. A numeric state2F4 triggers a runtime virtual request before the eventual saved-destination read; other states reach the grant directly. Then read localID from runtime collector+C4, sign-extend it and call35DEB0 on488+saved906E8*408. No explicit duplicate-bit precheck exists in this full caller; leaf OR remains idempotent, but its all-world skill scan may still run. Type416/state2F4/local indices are not localized names or physical positions.",
            "restore_rule": "304A40 checks the saved-destination local bit and calls24F6D8(actor,0) if present before clearing runtime+AC/+B0. Negative initial+C4 follows a separate runtime enumeration path, which can assign indices. That setup does not guarantee final index validity or prove a saved object-identity catalog."},
        "recommended_annotations": [
            {"va": "0x489ff4", "kind": "comment", "name": "TOD_bonus_target_progress_reset", "comment": "Reached reset489F68 clears saved8730,8728,872C after2CDBB0 and before465DC0, using canonical block pointer8A6890. Neighbors remain unnamed. Zero progress is not proof no past targets or lifetime retention."},
            {"va": "0x364354", "kind": "comment", "name": "TOD_bonus_target_progress_publication", "comment": "Store saved BE32 mask8728 OR slw(1,object+324), after clearing the same bit from runtime owner+FC. Lookup252E18 follows; pending is reread afterward. Saved progress is not the runtime remaining-target set."},
            {"va": "0x3643b0", "kind": "comment", "name": "TOD_bonus_target_message_latch", "comment": "Nonzero post-lookup pending: set saved global flag278 SC_PLAYED_BONUS_TARGET_MSG before native648 lookup/virtual request. Existing latch returns without request; not proof message played or target completion."},
            {"va": "0x3644e0", "kind": "comment", "name": "TOD_bonus_target_local_zero_reward", "comment": "Zero post-lookup pending and absent local bit0: grant local gold bolt0 in world chosen by saved906E8. Precheck35DE08 suppresses duplicate grant/message; later348 request follows. Not saved8728 all-bits completion."},
            {"va": "0x304d34", "kind": "comment", "name": "TOD_local_collectible_saved_destination_grant", "comment": "After numeric416 type admission and optional state2F4 virtual request, grant runtime+C4 local ID in world selected by saved906E8. No local duplicate precheck; runtime identity/index and current planet not inferred."},
        ],
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())],
    }
    if save_path is not None:
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        masks = [struct.unpack_from(">I", raw, 0x874 + i * 0x408)[0] for i in range(19)]
        progress = struct.unpack_from(">I", raw, 0x8728)[0]
        destination = struct.unpack_from(">I", raw, 0x906E8)[0]
        flags = struct.unpack_from(">Q", raw, 0x5548)[0]
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(raw).hexdigest().upper(),
            "progress_hex": f"{progress:08X}", "set_bits": [i for i in range(32) if progress & (1 << i)],
            "message_latch": bool(flags & MESSAGE_BIT), "saved_destination": destination,
            "selected_world_local_zero": bool(masks[destination] & 1) if destination < 19 else None,
            "runtime_pending": None, "target_count": None,
            "qualification": "Snapshot only: no current scene, pending targets, pickup positions, message history or reward eligibility inferred."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
