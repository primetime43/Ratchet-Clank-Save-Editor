"""Read-only exact-build runtime pool prerequisites for saved object-bit identity.

Runtime pool pointers/header/handles are NOT additional GAME.SAV fields. Neither
native callbacks nor allocators are executed; pure previews are bounded tooling.
"""
import argparse
import json
from pathlib import Path
import runpy
import struct

BASE = Path(__file__).resolve().parent
BINDINGS = runpy.run_path(str(BASE / "Inspect-TodWeaponBindings.py"))
DEFINITIONS = runpy.run_path(str(BASE / "Inspect-TodObjectDefinitions.py"))


def setup_capacity(definition_count, extra_slots):
    """Native32-bit add/round expression only; no accepted-input guarantee."""
    if any(type(v) is not int or not 0 <= v <= 0xFFFFFFFF for v in (definition_count, extra_slots)):
        raise ValueError("Capacity expression inputs must be unsigned32")
    return (definition_count + extra_slots + 7) & 0xFFFFFFF8


def initial_bitmap(capacity):
    """Model normal setup's logical bitmap, not heap allocation or native calls.

    Native setup zeroes the logical scan span then marks padding up to the next
    128-bit boundary occupied. The 65536 limit is this tool's bound, not a proven
    native input validator or a claim that saves contain that many object bits.
    """
    if type(capacity) is not int or not 0 <= capacity <= 65536:
        raise ValueError("Supply a bounded unsigned capacity")
    words = [0] * (4 * ((capacity + 127) // 128))
    for slot in range(capacity, len(words) * 32):
        words[slot // 32] |= 1 << (slot % 32)
    return words


def cleared_bitmap_preview(words, pending_slots, capacity):
    """Only the queue drain's occupancy-bit effect on valid bounded inputs.

    Does not emulate callback side effects, sentinel handles, counts, resource
    teardown, reentrancy, or the native routine's missing local slot validation.
    Duplicates are retained: native iteration is not established as deduplicated.
    """
    initial_bitmap(capacity)  # Shape bound only; caller's raw words are retained.
    if type(words) not in (list, tuple) or len(words) != 4 * ((capacity + 127) // 128):
        raise ValueError("Bitmap must contain complete128-bit scan blocks")
    if any(type(v) is not int or not 0 <= v <= 0xFFFFFFFF for v in words):
        raise ValueError("Bitmap words must be unsigned32")
    if type(pending_slots) not in (list, tuple) or len(pending_slots) > 65536:
        raise ValueError("Supply a bounded pending-slot list")
    if any(type(v) is not int or not 0 <= v < min(capacity, 65536) for v in pending_slots):
        raise ValueError("Pending slots must be unsigned16 and inside supplied capacity")
    result = list(words)
    for slot in pending_slots:
        result[slot // 32] &= ~(1 << (slot % 32)) & 0xFFFFFFFF
    return result


def runtime_header(raw):
    """Decode exactly32 supplied bytes without following any runtime pointer."""
    if len(raw) != 0x20:
        raise ValueError("Runtime pool header must be exactly32 bytes; not GAME.SAV")
    values = struct.unpack(">8I", raw)
    return {"raw_hex": bytes(raw).hex().upper(),
            "entry_base_pointer": f"0x{values[0]:08X}",
            "occupancy_pointer": f"0x{values[1]:08X}", "capacity": values[2],
            "live_count": values[3], "high_water_raw": f"0x{values[4]:08X}",
            "high_water_signed": BINDINGS["signed"](values[4], 32),
            "generation_counter_raw": values[5], "pending_release_count": values[6],
            "pending_slot_array_pointer": f"0x{values[7]:08X}",
            "warning": "Runtime bytes supplied by caller only; no save offset or live process lookup inferred."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    checks = {0x8A7610: 0x1064FC80,
              0x51F6A4: 0x90090010, 0x51F6AC: 0x91690000,
              0x51F6B0: 0x9169001C, 0x51F6B4: 0x91690004, 0x51F6B8: 0x91690008,
              0x51FD80: 0x38A00020, 0x51FDA0: 0x907D0010, 0x51FDA4: 0x913D0014,
              0x523B2C: 0x546B3830, 0x523B34: 0x5469482C,
              0x523B90: 0x913F0000, 0x523BDC: 0x913F001C, 0x523C34: 0x913F0004,
              0x523C4C: 0x57BC067E, 0x523C84: 0x7D035830, 0x523C94: 0x90C70000,
              0x523CAC: 0x939F0010, 0x523CB0: 0x911F0014, 0x523CB4: 0x915F0018,
              0x523CB8: 0x93BF0008, 0x523CBC: 0x915F000C,
              0x523CEC: 0x6504FFFE, 0x523CFC: 0xB0CC0050, 0x523D0C: 0x90E9009C,
              0x523D18: 0x394A0180, 0x523D20: 0x90830064,
              0x51FBAC: 0x4E800421, 0x51FBBC: 0xB15F0050, 0x51FBDC: 0xB3A50000,
              0x51FBE0: 0x907E0018,
              0x52193C: 0x83BC0018, 0x521964: 0xA3C60000, 0x521998: 0x4E800421,
              0x5219D8: 0x90E50000, 0x5219DC: 0x909D0064, 0x521A08: 0x93DA000C,
              0x521A54: 0xA3650064, 0x521ACC: 0x92DC0018,
              0x51F6E8: 0x90090000, 0x51F67C: 0x90690600, 0x51F68C: 0x90690604,
              0x3839DC: 0x481A047D,
              0x84DF38: 0x87E708, 0x87E708: 0x68FD60,
              0x68FE7C: 0x807F0044, 0x68FE80: 0x39230007,
              0x68FE88: 0x7F384A14, 0x68FE94: 0x57230038,
              0x68FEB0: 0x82D8003C, 0x68FEC4: 0x4E800421}
    for va, value in checks.items():
        if elf.u32(va) != value:
            raise ValueError(f"Pool lifecycle evidence changed at {va:#x}")
    guards = {va: elf.read(va, 4) for va in checks}
    calls = ((0x51FD90, 0x252938), (0x523C38, 0x252938), (0x523C50, 0x252938),
             (0x3839DC, 0x523E58), (0x68F1E0, 0x68EFC8),
             (0x68FE98, 0x59E020), (0x59E02C, 0x523B00),
             (0x398E60, 0x521840), (0x398EA4, 0x521840))
    for va, target in calls:
        if BINDINGS["branch_target"](elf.u32(va), va) != target:
            raise ValueError(f"Pool lifecycle branch changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    functions = (0x51F698, 0x51FD70, 0x523B00, 0x51FB08, 0x521840,
                 0x51F6C0, 0x51F678, 0x51F688, 0x383960)
    for va in functions:
        if elf.descriptors[va] != 0x89FF20:
            raise ValueError("Pool lifecycle descriptor TOC changed")
        end = elf.functions[elf.functions.index(va) + 1]
        guards[va] = elf.read(va, end - va)
    if elf.descriptors[0x68F190] != 0x8AFE5C:
        raise ValueError("Base definition loader TOC changed")
    guards[0x68F190] = elf.read(0x68F190, 0x80)
    if elf.descriptors[0x68FD60] != 0x8AFE5C:
        raise ValueError("Setup-before-loader TOC changed")
    guards[0x68FD60] = elf.read(0x68FD60, 0x1A8)
    guards[0x59E020] = elf.read(0x59E020, 16)
    fields = [(0, "entry_base", "Runtime entry storage pointer; stride180."),
              (4, "occupancy_bitmap", "Runtime occupancy pointer; low bit first in each BE32 word."),
              (8, "capacity", "Runtime slot capacity, supplied to523B00; not saved world bit count."),
              (12, "live_count", "Incremented by successful creation, decremented during queued release; reservations are not live objects."),
              (16, "high_water_raw", "Signed high-water slot withFFFFFFFF empty sentinel."),
              (20, "generation_counter", "Allocation generation counter; handle high16 uses prior low16."),
              (24, "pending_release_count", "Queued release count; drain reloads it during iteration."),
              (28, "pending_slot_array", "Runtime pointer to ushort physical slot queue; generation discarded.")]
    report = {"confidence": "code-backed",
              "warning": "Exact BCUS98127 v02.00 runtime evidence. This32-byte header is not additional GAME.SAV data. Static definitions and saved bits still do not identify a current named object; native allocation/callback effects are not executed.",
              "runtime_header": {"root_va": "0x1064fc80", "size": "0x20",
                                 "fields": [{"offset": hex(o), "size": 4, "name": n, "meaning": m} for o, n, m in fields]},
              "normal_setup": "523B00 receives runtime capacity; carves aligned entry storage(capacity*180), ushort release queue(rounded capacity*2) and scan bitmap(ceil(capacity/128)*16 logical bytes). It zeroes entry/bitmap spans, then marks padding slots through next128 boundary occupied. Sets capacity8/liveC=0/highwater10=FFFFFFFF/generation14=1/pending18=0; every valid entry class50=FFFF, member9C=0, handle64=FFFE0000|slot. Heap bounds, runtime input validity and allocation success are not inferred.",
              "padding_refinement": "The raw51FC88 reservation has no separate index<capacity predicate, and523E58 marks before its admission check; however normal523B00 setup preoccupies padding. A correctly initialized unchanged bitmap cannot return those padding slots. This is not evidence of a normal-game padding-allocation bug.",
              "setup_before_loader": "68FD60 obtains selected root through651428, computes capacity=(definition count+caller extra+7)&FFFFFFF8 using32-bit arithmetic, then59E020 adjusts TOC to89FF20 and calls523B00. Immediately afterward it dispatches virtual+3C with the same selected root and context; verified vtable84DF28+3C selects2F8690. No intervening direct call occurs between setup return and loader dispatch. Earlier class/setup calls occur before the fresh bitmap initialization. Nested callback/creation effects inside setup or loading, malformed arithmetic overflow and alternative runtime vtables are not ruled out.",
              "reset_distinction": "51FD70 zeroes first20hex bytes then highwater10=FFFFFFFF/generation14=1.51F698 instead clears base0/bitmap4/capacity8/liveC/pending-array1C and highwater10, but does not write generation14 or pending-count18. Neither routine locally frees backing storage or clears saved world bit bands.",
              "deferred_release": "51FB08 resolves physical low16 against highwater and stored full handle, invokes optional root600 callback before class50=FFFF, clears member9C, appends input handle LOW16 to ushort queue(root1C) and increments root18. It does not locally clear the occupancy bit or decrement live count. Malformed-handle null dereference/queue capacity/reentrant safety are not asserted.",
              "queue_drain": "521840 reads queued ushort physical slot, invokes optional root604 callback BEFORE occupancy clear, then clears corresponding bitmap bit and writes handle64=FFFE0000|slot. It decrements rootC, trims highwater using the BE generation halfword at entry64 equalFFFE, performs resource cleanup and reloads pending count at loop bottom; clears root18 on exit. Callback-appended queue entries may extend iteration, so no fixed snapshot, deduplication, atomicity or recursion guarantee is claimed.",
              "identity_limit": "The verified setup-before-virtual-loader path establishes fresh bitmap initialization and matching selected root at that static call boundary. Physical index=asset ordinal still requires valid capacity arithmetic, exactly one successful allocation/reservation per definition and no nested allocation/free during setup or loading. These runtime prerequisites are not established by this save.383960 allocates another object of input object's class and stores input full handle at new entry58; deferred release makes physical slots reusable. Class ID, definition ordinal, runtime generation handle and saved bit index remain distinct.",
              "base_loader": "68F190 directly creates every selected-root definition at stride48, whereas filtered2F8690 tests eligibility and reserves rejected definitions. This is an alternate virtual implementation, not proof which loader a live saved world used.",
              "recommended_annotations": [
                  {"va": "0x68fd60", "kind": "function", "name": "TOD_object_pool_setup_then_selected_root_load_verified", "comment": "Selectedroot651428 count44 +callerextra+7 rounded8 via32bitexpression ->59E020/523B00 freshpoolsetup, immediatelyvirtual3C same root/context (84DF28 selects2F8690). Nested creation/free, arithmeticoverflow, runtimevtable and savedbit identity remain conditional."},
                  {"va": "0x523b00", "kind": "function", "name": "TOD_object_pool_storage_and_padding_initialize_verified", "comment": "Runtime capacity carve: entry stride180, ushortreleasequeue, bitmapceil128. Clearsbitmap then marks paddingoccupied; sets highwaterFFFFFFFF/generation1/live0/pending0; entryclassFFFF/handleFFFE0000|slot. Not GAME.SAV header or runtimeordinalproof."},
                  {"va": "0x51fd70", "kind": "function", "name": "TOD_object_pool_root_header_construct_verified", "comment": "Zeros first20hex runtime rootbytes, then highwater10=FFFFFFFF andgeneration14=1. Does not locally allocate/free backing storage or clear saved worldbits."},
                  {"va": "0x51f698", "kind": "function", "name": "TOD_object_pool_detach_storage_header_verified", "comment": "Clears base0/bitmap4/capacity8/liveC/pendingarray1C, highwater10=FFFFFFFF. Does NOT locally write generation14 orpendingcount18, free backingmemory or mutate GAME.SAV."},
                  {"va": "0x51fb08", "kind": "function", "name": "TOD_object_pool_deferred_release_enqueue_verified", "comment": "Fullhandle match->optional root600 callback BEFOREclassFFFF; append low16 physicalslot to ushortqueue, incrementpending18. No immediate bitmapclear/livecountdecrement. Invalidhandle/reentrant/queuebounds safety unproven."},
                  {"va": "0x521840", "kind": "function", "name": "TOD_object_pool_pending_release_drain_verified", "comment": "Queueushortslot->optional root604 callback BEFOREbitmapclear; handleFFFE0000|slot, liveC--, highwatertrim by BEgenerationhalfFFFE. Reloads pendingcount eachiteration, thenzeroes18; slots reusable, no fixedsnapshot/atomicity guarantee."},
                  {"va": "0x51f6c0", "kind": "function", "name": "TOD_object_pool_occupancy_slot_clear_verified", "comment": "Clearone runtimeoccupancybit, wordbyteoffset(slot>>5)*4, lowbit(slot&31). No localcapacitycheck or savedworldbitwrite."},
                  {"va": "0x51f678", "kind": "function", "name": "TOD_object_pool_release_enqueue_callback_set_verified", "comment": "Stores supplied callbackdescriptor at runtimepoolroot+600; invoked by51FB08 before classclear/queueappend."},
                  {"va": "0x51f688", "kind": "function", "name": "TOD_object_pool_release_drain_callback_set_verified", "comment": "Stores supplied callbackdescriptor at runtimepoolroot+604; invoked by521840 before occupancyclear."}],
              "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())]}
    if save_path is not None:
        observation = DEFINITIONS["inspect"](elf_path, save_path)["save_observation"]
        report["save_observation"] = {**observation,
                                      "warning": "Actual saved world bands only. Runtime root/pointers/capacity/queue/handles are not reconstructed from these bits. Their absence here is not proof all game serialization paths exclude every related datum."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.elf, args.save), indent=2))
    except (ValueError, OSError) as error:
        parser.exit(2, f"Pool lifecycle inspection failed: {error}\n")
