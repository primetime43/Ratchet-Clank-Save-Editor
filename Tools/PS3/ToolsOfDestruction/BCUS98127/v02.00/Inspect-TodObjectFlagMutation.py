"""Exact-build object lifecycle publication and restore gates, read-only.

Runtime latches, callbacks and UID records are not reconstructed from save bits.
No native callback, handle resolver or malformed pointer arithmetic is executed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))


def _unsigned(value, bits, name):
    if type(value) is not int or not 0 <= value < 1 << bits:
        raise ValueError(f"{name} must be an unsigned {bits}-bit integer")
    return value


def event_gate_preview(latch_byte, argument_word, object_uid, runtime_record_uids):
    """Local gate/order only, assuming callback returns and supplied lookup data.

    Supplied UID words model already-resolved runtime records. They are not
    object pool indices. No callback mutation, reentrancy or handle resolution
    is simulated. The bounded sequence is a tooling limit, not a native gate.
    """
    _unsigned(latch_byte, 8, "latch_byte")
    _unsigned(argument_word, 32, "argument_word")
    _unsigned(object_uid, 32, "object_uid")
    if type(runtime_record_uids) not in (list, tuple) or len(runtime_record_uids) > 2048:
        raise ValueError("Supply at most 2048 resolved runtime record UID words")
    for uid in runtime_record_uids:
        _unsigned(uid, 32, "runtime record UID")
    admitted = latch_byte == 0
    match = next((i for i, uid in enumerate(runtime_record_uids) if uid == object_uid), None) if admitted else None
    return {"callback_admitted": admitted, "callback_argument_low_byte": argument_word & 255 if admitted else None,
            "saved_bit_set_after_callback_returns": admitted, "first_matching_runtime_record": match,
            "matching_record_byte_c_result": 0 if match is not None else None, "event_latch_result": 1,
            "warning": "Runtime inputs supplied explicitly. Callback may have side effects; no atomicity, unique UID match, current saved-world identity or handle safety inferred."}


def restore_gate_preview(pending_byte, saved_bit_set, event_latch_byte):
    """One-shot pending latch and saved-bit gate; does not execute event leaf."""
    _unsigned(pending_byte, 8, "pending_byte")
    _unsigned(event_latch_byte, 8, "event_latch_byte")
    if type(saved_bit_set) is not bool:
        raise ValueError("saved_bit_set must be explicitly boolean")
    query = pending_byte != 0
    call = query and saved_bit_set
    return {"pending_result": 0 if query else pending_byte, "saved_bit_queried": query,
            "event_leaf_called": call, "event_argument": 0 if call else None,
            "virtual_callback_admitted": call and event_latch_byte == 0,
            "event_latch_result": 1 if call else event_latch_byte}


def suppression_gate_preview(object_flags_word, saved_word, bit):
    """Native flag predicate and one bounded BE64 OR; no downstream call."""
    _unsigned(object_flags_word, 32, "object_flags_word")
    _unsigned(saved_word, 64, "saved_word")
    _unsigned(bit, 6, "bit")
    admitted = bool(object_flags_word & 0x10000)
    return {"saved_write_admitted": admitted, "result_word": saved_word | (1 << bit) if admitted else saved_word,
            "downstream_helper_called": True}


def record_request_preview(handle_word, table_count, stored_handle_word, entry_nonzero):
    """27C358 route after its unchecked record resolver has returned valid data.

    Does not reproduce pointer arithmetic or check the actor pointer read from
    the matching pool entry. The zero record-byte store precedes this route.
    """
    for name, value in (("handle_word", handle_word), ("table_count", table_count), ("stored_handle_word", stored_handle_word)):
        _unsigned(value, 32, name)
    if type(entry_nonzero) is not bool:
        raise ValueError("entry_nonzero must be explicitly boolean")
    return {"resolved_record_byte_c_result": 0,
            "reaches_actor_pointer_read": (handle_word & 65535) <= table_count and handle_word == stored_handle_word and entry_nonzero}


def auxiliary_consumer_preview(handle_valid, actor_state_word, saved_bit_set):
    """2FE0E8 branch after earlier work; supplied actor state is post-helper."""
    if type(handle_valid) is not bool or type(saved_bit_set) is not bool:
        raise ValueError("handle_valid and saved_bit_set must be explicitly boolean")
    _unsigned(actor_state_word, 32, "actor_state_word")
    return {"runtime_helper_24f4f8_called": handle_valid,
            "saved_bit_queried": handle_valid and actor_state_word != 9,
            "runtime_byte_643_result": int(handle_valid and (actor_state_word == 9 or saved_bit_set))}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    checks = {
        0x2DD5A4: 0x8803001D, 0x2DD5AC: 0x2F800000, 0x2DD5B0: 0x419E0030,
        0x2DD5B4: 0x3BC00001, 0x2DD5B8: 0x9BDD001D,
        0x2DD5E4: 0x78840620, 0x2DD5EC: 0x812B0048, 0x2DD600: 0x4E800421,
        0x2DD608: 0x807D0014, 0x2DD614: 0x8382F54C, 0x2DD624: 0x83C2F548,
        0x2DD638: 0x4099FF7C, 0x2DD658: 0x80E30020, 0x2DD65C: 0x80880064,
        0x2DD664: 0x4086FFCC, 0x2DD670: 0x9983000C, 0x2DD674: 0x9BDD001D,
        0x2DD6A8: 0x8803001E, 0x2DD6B4: 0x409E001C, 0x2DD6D8: 0x98DF001E,
        0x2DD6E4: 0x38800000, 0x2DD6E8: 0x5465063E, 0x2DD6F4: 0x4182FFC4,
        0x2F7950: 0x546003DE, 0x2F795C: 0x419E0060,
        0x2F79B0: 0x7D26282A, 0x2F79B8: 0x7CE6292A,
        0x3BF8D8: 0x2C080000, 0x3BF8EC: 0x41820190,
        0x3BFA7C: 0x807E0014, 0x3BFA8C: 0x993E0248,
        0x3C01A0: 0x88030248, 0x3C01D0: 0x88A60000, 0x3C01D8: 0x41820348,
        0x3C0520: 0x807F0014, 0x3C053C: 0x93080000, 0x3C0540: 0x98E80008,
        0x3C054C: 0x98FF0248, 0x8A37E0: 0x100637C0,
        0x89F46C: 0x101D67A0, 0x89F468: 0x101D67A4,
        0x27C37C: 0x81030020, 0x27C380: 0x9883000C, 0x27C38C: 0x7F8B4840,
        0x27C39C: 0x419C0044, 0x27C3B0: 0x80690064, 0x27C3D0: 0x41820010,
        0x27C3D4: 0x80690040, 0x898F3C: 0x1064FC80,
        0x2FE120: 0x9BBF0643, 0x2FE150: 0x9BBF0642, 0x2FE154: 0x9BBF0640,
        0x2FE164: 0x7F8B0040, 0x2FE170: 0x419C0038, 0x2FE1D4: 0x2C840009,
        0x2FE1D8: 0x40860024, 0x2FE1E0: 0x991F0643, 0x2FE210: 0x419AFF98,
        0x89FE5C: 0x1064FC80,
    }
    for va, expected in checks.items():
        if elf.u32(va) != expected:
            raise ValueError(f"Object mutation evidence changed at {va:#x}")
    calls = ((0x2DD60C, 0x2F77A8), (0x2DD64C, 0x250848), (0x2DD6DC, 0x2F7830),
             (0x2DD708, 0x2DD588), (0x2F7974, 0x2D1490), (0x2F79C0, 0x2501C8),
             (0x3BF8C8, 0x3BE900), (0x3BFA80, 0x2F77A8), (0x3C0528, 0x2F77A8),
             (0x27C36C, 0x2788B8), (0x27C3D8, 0x2DD588), (0x2FE104, 0x2FBAB8),
             (0x2FE140, 0x494348), (0x2FE1C8, 0x24F4F8), (0x2FE200, 0x2F7830))
    guards = {va: elf.read(va, 4) for va in checks}
    for va, target in calls:
        if BINDINGS["branch_target"](elf.u32(va), va) != target:
            raise ValueError(f"Object mutation branch changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    functions = (0x2DD588, 0x2DD698, 0x2F7720, 0x2F77A8, 0x2F7930, 0x3BF5A8, 0x3C0160, 0x27C358, 0x2FE0E8)
    for va in functions:
        if elf.descriptors[va] != 0x89FF20:
            raise ValueError("Object mutation TOC changed")
        end = elf.functions[elf.functions.index(va) + 1]
        guards[va] = elf.read(va, end - va)
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA BCUS98127 v02.00 static paths only. Saved pool-slot bits are not object UID records, universal killed flags, named boss identities or current runtime latches. No callback, native execution, editable bounds or in-game acceptance inferred.",
        "storage": {"world_base": "0x488", "world_stride": "0x408", "world_slots": 20,
                    "recorded_member": "0x1e0", "suppression_member": "0x2e0", "bitset_bytes": 256},
        "event_leaf": {
            "function_va": "0x2dd588", "runtime_event_latch_member": "0x1d",
            "admission": "Zero byte1D admits the virtual callback. Any nonzero initial byte skips callback, saved bit setter and runtime record scan, but still stores1 to1D. This normalizes a raw noncanonical nonzero latch rather than preserving its byte.",
            "publication_order": ["2DD600: virtual descriptor at object vtable+48, argument low8", "2DD608/2DD60C: reload object+14 and call saved recorded-state setter2F77A8", "Resolve runtime records250848 and compare record+20 to pool entry+64 UID", "First UID match: record+C byte=0", "Runtime object+1D byte=1"],
            "scan": "Runtime owner count and four-byte handle sequence come from TOC slots89F46C/89F468. First matching UID returns immediately; no unique-match invariant is established. No matched record is required to publish1D. This path dereferences resolver result without an independently visible null gate; tooling does not emulate malformed handles.",
            "scope": "Callback executes BEFORE saved-bit publication and BEFORE1D is set. Setter2F77A8 obtains current world through2D1490 after callback returns; entry-time world identity cannot be assumed if callback changes runtime state. Callback reentrancy/effects and notification meaning are not simulated; stores are not an atomic transaction.",
        },
        "restore_gate": {
            "function_va": "0x2dd698", "runtime_pending_member": "0x1e",
            "order": "Pending1E zero returns without querying the bit. Nonzero stores0 to1E BEFORE invoking recorded-bit checker2F7830 on object+14. Only a nonzero low byte result tail-calls2DD588 with argument0. Pending is consumed even when the saved bit is clear; already-nonzero1D independently suppresses the inner virtual callback.",
            "scope": "A set save bit does not independently schedule restoration, prove a pending runtime request, or force a callback. Pending/latch bytes belong to a runtime object, not GAME.SAV fields.",
        },
        "record_request": {
            "function_va": "0x27c358", "resolver_va": "0x2788b8", "pool_pointer_slot_va": "0x898f3c",
            "order": "Resolver2788B8 supplies a runtime record whose UID/handle+20 is loaded, then record+C byte clears BEFORE object-pool validation. Low16 index must be <= unsigned table count; full entry+64 handle must match; nonzero entry then supplies actor pointer+40 to2DD588 with0. Rejected index/handle skips event but does not undo record+C=0.",
            "scope": "No visible resolver-null or actor-pointer-null gate is established in this complete function. Preview assumes a valid resolved record and only reports the bounded routing decision, not native pointer dereferences or a safe script/UI entry point. Exported semantic name remains unresolved.",
        },
        "auxiliary_consumer": {
            "function_va": "0x2fe0e8", "pool_pointer_slot_va": "0x89fe5c",
            "order": "Following2FBAB8 and494348, clears runtime bytes643/642/640, validates related handle at63C (low16<=unsigned table count, full handle equality, nonzero pool entry). Valid route calls24F4F8(actor+14,0) BEFORE testing related actor state+24. State9 writes consumer byte643=1 WITHOUT querying saved bit; other states query2F7830 and write1 only if low byte is nonzero.",
            "scope": "Saved bit is one alternative, not a necessary condition for this runtime result. Actor state is inspected after24F4F8, whose effects are not simulated. Invalid handle leaves643 zero on this path. Object kind/byte meaning and downstream use remain unnamed; runtime byte643 is not a serialized completion flag.",
        },
        "suppression_publication": {
            "function_va": "0x2f7930", "downstream_helper_va": "0x2501c8",
            "order": "Object+68 flag10000 gates ONLY the saved spawn-suppression OR. Both branches then invoke2501C8 on the original object pointer. The qualifying bit store precedes that helper; an unqualified object can still reach the helper without a saved suppression write.",
            "store_shape": "The read uses ldarx2F79B0 but writes with plain stdx2F79B8, not store-conditional/retry. This pair alone is not proof of atomic OR or concurrency safety.",
            "clear_scope": "Recorded-state clear leaf2F7720 affects the distinct1E0 bitset, not suppression2E0. No new direct call site or gameplay reset cause is inferred for this clear leaf.",
        },
        "opaque_producers": [
            {"function_va": "0x3bf5a8", "rule": "After preceding runtime work, queries3BE900 for at most indices0,1,2. First null result branches to saved recorded-state setter3BFA80, then runtime byte248=1. These three query results and prior side effects are runtime inputs, not decoded save entries.", "warning": "Object kind and query meaning remain unresolved; no boss or collectible name assigned."},
            {"function_va": "0x3c0160", "rule": "Runtime byte read through pointer slot8A37E0 (100637C0) zero takes3C0520: saved recorded-state setter3C0528, then runtime state+24=9, byte+2C=1, time+28 from runtime singleton+B4, byte248=1. Preexisting248 also changes the runtime state to9 earlier but does not itself establish a new saved-bit write.", "warning": "Only guarded entry/force path is interpreted; decompiler omits inline switch cases. Runtime global byte and object kind are intentionally unnamed."},
        ],
        "recommended_annotations": [
            {"va": "0x2dd588", "kind": "function", "name": "TOD_object_event_callback_then_saved_bit_verified", "comment": "Zero runtime1D admits virtual+48 callback BEFORE current-world saved-bit publication. First matching runtime UID record byteC clears;1D=1 last. Repeated nonzero1D normalizes1, skips callback/bit/scan. No object-kind or atomicity claim."},
            {"va": "0x2dd698", "kind": "function", "name": "TOD_object_restore_pending_consumed_before_bit_verified", "comment": "Consumes runtime pending1E before saved recorded-bit query; nonzero result tail-calls2DD588 with0. Pending consumed even if bitclear; inner1D latch can independently suppress callback."},
            {"va": "0x27c358", "kind": "function", "name": "TOD_object_record_clear_before_event_route_verified", "comment": "Resolved runtime record byteC=0 BEFORE low16/count/full-handle object-pool routing. Valid route actor+40 to2DD588(0); rejected handle does not undo prior record-byte write. Resolver/actor null gate not established."},
            {"va": "0x2fe0e8", "kind": "function", "name": "TOD_related_object_state_or_saved_bit_consumer_verified", "comment": "Valid related handle calls24F4F8 then tests actor state24. State9 sets runtime643 without bit query; otherwise saved recorded-bit2F7830 determines runtime643. Not a serialized flag or named object-kind verdict."},
        ],
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())],
    }
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Expected verified plaintext save size")
        data = path.read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
            raise ValueError("Expected verified plaintext inventory IDs0..31")
        rows = []
        for world in range(20):
            entry = {"physical_world_slot": world, "named_world": world < 19}
            for label, member in (("recorded", 0x1E0), ("suppression", 0x2E0)):
                offset = 0x488 + world * 0x408 + member
                words = struct.unpack_from(">32Q", data, offset)
                entry[label + "_offset"] = hex(offset)
                entry[label + "_set_count"] = sum(w.bit_count() for w in words)
                entry[label + "_raw_words"] = [f"{w:016X}" for w in words]
            rows.append(entry)
        report["save_observation"] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest().upper(), "worlds": rows,
            "warning": "Raw bit observations only; no runtime1D/1E/248 latch, UID record, object name, callback history, producer path or current world inferred."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
