"""Exact-build read-only object grant producers and flag-before-counter ordering."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
OBJECTS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodObjects.py")))


def unsigned(value, width=32):
    if type(value) is not int or not 0 <= value < 1 << width:
        raise ValueError(f"Expected explicit unsigned{width} bits")
    return value


def grant_one_preview(current_bits, peak_bits, additions_bits):
    """Stable valid canonical samples only; detached arithmetic, never file writes."""
    current_bits, peak_bits, additions_bits = [unsigned(v) for v in (current_bits, peak_bits, additions_bits)]
    current = (current_bits+1) & 0xFFFFFFFF
    return {"current_bits": f"{current:08X}", "positive_additions_bits": f"{(additions_bits+1) & 0xFFFFFFFF:08X}",
            "peak_store_selected": current > peak_bits, "peak_bits": f"{max(current, peak_bits):08X}",
            "nonzero_current_after": current != 0,
            "qualification": "Explicit stable non-aliasing current/peak/additions samples for requested signed delta+1 only. Native current store precedes additions then unsigned peak comparison. Not unique pickups, ownership events, completed callback state or save mutation."}


def flag_grant_plan(object_id, flag_id, flag_words, current_bits, peak_bits, additions_bits, receiver_admitted):
    if type(object_id) is not int or not 0 <= object_id < 23:
        raise ValueError("Reference plan requires physical object ID0..22")
    if type(flag_id) is not int or not 0 <= flag_id < 320:
        raise ValueError("Reference plan requires physical global flag ID0..319")
    if not isinstance(flag_words, (list, tuple)) or len(flag_words) != 5:
        raise ValueError("Expected five explicit BE64 flag words")
    words = [unsigned(v, 64) for v in flag_words]
    if type(receiver_admitted) is not bool:
        raise ValueError("Expected explicit post-helper receiver admission")
    grant = grant_one_preview(current_bits, peak_bits, additions_bits)
    if receiver_admitted:
        words[flag_id//64] |= 1 << (flag_id % 64)
    return {"flag_words_after": [f"{v:016X}" for v in words],
            "saved_store_order": (["global flag OR", "current+1", "positive additions+1"] +
                                   (["unsigned peak update"] if grant["peak_store_selected"] else [])) if receiver_admitted else [],
            "selected_object_id": object_id if receiver_admitted else None,
            "counter_projection": grant if receiver_admitted else None,
            "qualification": "302A10 saved-store suffix from supplied post-helper admission, stable selected IDs and canonical samples only. Existing flag does not reject the add. Native ID bounds, runtime scratch/helpers, callbacks, flag names and full gameplay eligibility not emulated."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    expected = {
        0x897B38: 0x101EFB20, 0x23E744: 0x913F1A68,
        0x89FFF4: 0x101EFB20, 0x8A0278: 0x1064FC80,
        0x304708: 0x38800211, 0x304730: 0x38800005, 0x304738: 0x38A00001,
        0x3075E4: 0x38800211, 0x30761C: 0x38800010, 0x307620: 0x38A00001,
        0x307630: 0x807E009C, 0x307640: 0x4184FFBC,
        0x30765C: 0x81090064, 0x307678: 0x419AFF84,
        0x307688: 0x419EFF74, 0x307690: 0x38800307, 0x3076B4: 0x388002D4,
        0x3080A0: 0x38800211, 0x3080B4: 0x3880000F, 0x3080BC: 0x38A00001,
        0x302A40: 0x801F00B4, 0x302A44: 0x2F800011, 0x302A48: 0x419E00B8,
        0x302B04: 0x909F00B8, 0x302A54: 0x38800416,
        0x302A80: 0x38A00001, 0x302AA8: 0x813F00AC,
        0x302AB0: 0x814200D4, 0x302AB4: 0x5527E8F8,
        0x302AB8: 0x552606BE, 0x302ABC: 0x38875520,
        0x302AC0: 0x7C0C3036, 0x302ACC: 0xE9690008,
        0x302AD0: 0x7D885B78, 0x302AD4: 0xF9090008, 0x302ADC: 0x809F00B4,
        0x23D874: 0x80E31A68, 0x23D878: 0x2F850000,
        0x23D8A0: 0x90090004, 0x23D8A4: 0x409D0018,
        0x23D8B8: 0x900C000C, 0x23D8CC: 0x7C054840,
        0x23D8D0: 0x4C800020, 0x23D8D4: 0x7D23212E,
        0x252F78: 0xF8410028, 0x252F7C: 0x3C42FFFF, 0x252F80: 0x38420018,
    }
    guards = {}
    for va, value in expected.items():
        if elf.u32(va) != value:
            raise ValueError(f"Object grant evidence changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    for va, target in ((0x30475C, 0x252F78), (0x307624, 0x252F78),
                        (0x3080E4, 0x252F78), (0x302AE0, 0x252F78),
                        (0x3046FC, 0x24FB88), (0x302A4C, 0x24FB88),
                        (0x3076E0, 0x2503C8), (0x3076FC, 0x24FB78),
                        (0x302A38, 0x253048), (0x308090, 0x253048)):
        raw = elf.u32(va)
        if raw >> 26 != 18 or not raw & 1 or BINDINGS["branch_target"](raw, va) != target:
            raise ValueError("Object grant call changed")
        guards[va] = elf.read(va, 4)
    if BINDINGS["branch_target"](elf.u32(0x252F84), 0x252F84) != 0x23D870 or elf.u32(0x252F84) & 1:
        raise ValueError("Object grant thunk tail changed")
    guards[0x252F84] = elf.read(0x252F84, 4)
    functions = [(0x302A10, 0x89FF20), (0x3046E8, 0x89FF20),
                 (0x3075B8, 0x89FF20), (0x308070, 0x89FF20),
                 (0x23D870, 0x88FF38), (0x23E650, 0x88FF38)]
    for function, toc in functions:
        if elf.descriptors[function] != toc:
            raise ValueError("Object grant function TOC changed")
        guards[function] = elf.read(function, elf.functions[elf.functions.index(function)+1]-function)
    dispatch = []
    for slot, descriptor, function in ((0x84E39C, 0x86DE60, 0x302A10),
                                       (0x84E4EC, 0x86DF90, 0x3046E8),
                                       (0x84E78C, 0x86E198, 0x3075B8),
                                       (0x84E86C, 0x86E218, 0x308070)):
        if elf.u32(slot) != descriptor or elf.u32(descriptor) != function or elf.u32(descriptor+4) != 0x89FF20:
            raise ValueError("Object grant dispatch link changed")
        guards[slot], guards[descriptor] = elf.read(slot, 4), elf.read(descriptor, 8)
        dispatch.append({"slot_va": hex(slot), "descriptor_va": hex(descriptor), "function_va": hex(function)})
    enums = OBJECTS["PROGRESSION"].exports(elf, 0x28440, "OBJ_", 0x12990)
    ids = {5: "OBJ_CHARGE_BOOTS", 15: "OBJ_STATUES", 16: "OBJ_SOULS", 17: "OBJ_SHIP_PARTS"}
    for identifier, name in ids.items():
        item = next(e for e in enums if e["id"] == identifier)
        if item["enum"] != name:
            raise ValueError("Object grant native ID changed")
        for key, size in (("name_va", len(name)+1), ("name_slot_va", 4), ("value_slot_va", 4), ("export_call_va", 4)):
            va = int(item[key], 0)
            guards[va] = elf.read(va, size)
    report = {
        "confidence": "exact-build-native-object-grants-and-flag-before-counter",
        "warning": "USA BCUS98127 v02.00 only. Static producer paths, not pickup placement/uniqueness, accepted gameplay transitions, timer units, callback outcomes or new editing permission.",
        "dispatch_links": dispatch,
        "fixed_grants": [
            {"id": 5, "enum": ids[5], "function_va": "0x3046e8", "current_offset": "0x318", "peak_offset": "0x374", "additions_offset": "0x3d0",
             "rule": "3046E8 samples24FB88: nonnull replaces supplied context with returned+14, null keeps supplied context. Reached context+40/type211 admission requests object5,+1 through252F78. No local current-count/already-present rejection; global lookup/valid receiver and larger runtime dispatch remain qualified."},
            {"id": 16, "enum": ids[16], "function_va": "0x3075b8", "current_offset": "0x344", "peak_offset": "0x3a0", "additions_offset": "0x3fc",
             "rule": "3075B8 requires supplied context+40/type211 admission, then requests object16,+1 through252F78 BEFORE inspecting actor+9C linked runtime handle. Invalid index/generation, null linked actor or failed later type tests return only AFTER the saved counter operation. Qualified linked type307 requests24FB78; alternative type2D4 requests2503C8. No verified handler outcomes, target identity or counter rollback; no local duplicate/current-count rejection."},
            {"id": 15, "enum": ids[15], "function_va": "0x308070", "current_offset": "0x340", "peak_offset": "0x39c", "additions_offset": "0x3f8",
             "rule": "308070 first calls253048 on actor+9C runtime scratch, then requires supplied context+40/type211 admission and requests object15,+1 through252F78. That scratch member is NOT saved current340. No local duplicate/current-count rejection; earlier helper and larger dispatch effects remain qualified."}],
        "counter_order": "252F78 adjusts TOC89FF20 to88FF38 and tail-branches23D870. Valid canonical receiver+1A68 resolves save101EFB20. For these signed+1 requests, the call-free leaf stores wrapping current at304+4*ID FIRST, then wrapping positive additions at3BC+4*ID, then raises peak360+4*ID only by unsigned comparison. The peak sample and saved-pointer reloads occur later, not an atomic three-word publication. Repeated reached calls add again. CurrentFFFFFFFF wraps to0 and still increments additions; high-bit peaks can remain unchanged. Counts are not unique or lifetime pickup totals, attached actors, or an accepted edit range.",
        "flag_then_object": {"function_va": "0x302a10",
            "rule": "302A10 first calls253048 on actor+B0. If the then-sampled actor+B4 is17 OBJ_SHIP_PARTS it explicitly clears runtime actor+B8 before receiver admission.24FB88 nonnull chooses returned+14; null retains supplied context. Reached context+40/type416 admission selects actor+AC global flag ID, ORs its bit into canonical saved5528+(ID>>6)*8, THEN rereads actor+B4 and requests that object ID,+1 through252F78. Flag publication precedes current/additions/peak work, not an atomic flag/counter pair.",
            "repeat_limit": "The complete body does not reject an already-set flag or already-present object before the add. Repeated reached calls can keep the same bit set while increasing the object counters. No local flag0..319/object0..22 bounds are established; plans enforce physical limits only for safe detached reference arithmetic. Actor-selected IDs are separate samples around helpers; stable configuration, matching canonical receiver and valid pointers are required, not inferred from the save.",
            "runtime_limit": "Actor+B0/+B4/+B8/+AC, context, lookup result and linked handles are runtime members, not new save fields. The17 branch's scratch clear is not saved object removal. No flag-name/object association catalog, every timer producer, spawn suppression, unique collection or complete callback effects are recovered."},
        "snapshot_limit": "Saved object counts and global bits do not reconstruct admitted contexts, number of producer invocations, linked actors, unique pickups or award history. The separately mapped Souls award reads signed additions>25/current0 under other gates; a grant alone is not that award. Viewing never dispatches a grant, changes flags/counters, deduplicates counts or repairs invariants.",
        "recommended_annotations": [
            {"va": "0x3046e8", "name": "TOD_charge_boots_object_grant_after_receiver_admission", "comment": "24FB88 lookup can replace supplied context; type211 path requests OBJ_CHARGE_BOOTS5,+1 via252F78->23D870. Saved318/374/3D0 wrap current/additions and unsigned peak; no local duplicate check or unique pickup proof."},
            {"va": "0x307624", "kind": "comment", "name": "TOD_souls_saved_object_add_before_linked_handle_checks", "comment": "Qualified supplied receiver requests OBJ_SOULS16,+1 before actor9C linked-handle validation/type307 or2D4 follow-up helpers. Invalid linked handle does not locally undo prior saved344/3A0/3FC update. Not handler outcomes or unique targets."},
            {"va": "0x308070", "name": "TOD_statues_object_grant_after_runtime_scratch_and_receiver_gate", "comment": "253048 actor9C scratch first, then supplied receiver type211 requests OBJ_STATUES15,+1. Saved340/39C/3F8 counters; scratch is runtime, no local duplicate gate or unique statue placement proof."},
            {"va": "0x302ad4", "kind": "comment", "name": "TOD_configured_object_flag_publish_before_saved_counter_add", "comment": "Type416 receiver path ORs actorAC flag into canonical5528 bank BEFORE reread actorB4/+1 via252F78. No existing-flag rejection or local ID bounds. Repeat can add counters with unchanged flag; not atomic or fixed flag/object identity."},
        ],
        "instruction_guards": [{"va": hex(a), "bytes": raw.hex().upper()} for a, raw in sorted(guards.items())],
    }
    if save_path is not None:
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i*20)[0] != i for i in range(32)):
            raise ValueError("Not verified plaintext inventory layout")
        report["save_observation"] = {"sha256": hashlib.sha256(raw).hexdigest().upper(),
            "fixed_objects": [{"id": identifier, "enum": ids[identifier],
                               "current_bits": raw[0x304+4*identifier:0x308+4*identifier].hex().upper(),
                               "peak_bits": raw[0x360+4*identifier:0x364+4*identifier].hex().upper(),
                               "additions_bits": raw[0x3BC+4*identifier:0x3C0+4*identifier].hex().upper()} for identifier in (5, 15, 16)],
            "global_flag_words": [raw[0x5528+8*i:0x5530+8*i].hex().upper() for i in range(5)],
            "qualification": report["snapshot_limit"]}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
