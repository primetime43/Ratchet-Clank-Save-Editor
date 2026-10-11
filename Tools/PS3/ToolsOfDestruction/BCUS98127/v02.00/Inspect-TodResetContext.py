"""Read-only reset-request admission and independent serialized counter dependencies.

Exact BCUS98127 v02.00 native evidence; never executes native callbacks. Runtime
request latches and actor virtual tables are not serialized save fields.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("tod_reset_categories", Path(__file__).with_name("Inspect-TodResetCategories.py"))
CATEGORIES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CATEGORIES)
BINDINGS = CATEGORIES.BINDINGS


def _word(value, name):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(name + " must be an unsigned 32-bit integer")
    return value


def request_preview(category, latch, blocking_predicate, replay_counter, category_words, segment_count=None):
    """Bounded arithmetic preview only; external calls, floats and reentry omitted.

    The native predicate is masked to its low byte. The native writer has no
    category bound; this inspector deliberately refuses indices outside 0..7.
    A supplied segment count represents an already resolved valid segment.
    """
    for name, value in (("category", category), ("latch", latch),
                        ("blocking_predicate", blocking_predicate), ("replay_counter", replay_counter)):
        _word(value, name)
    if category >= 8:
        raise ValueError("category is outside the eight physically mapped words")
    if not isinstance(category_words, (list, tuple)) or len(category_words) != 8:
        raise ValueError("category_words must contain exactly eight words")
    words = [_word(value, "category word") for value in category_words]
    if segment_count is not None:
        _word(segment_count, "segment_count")
    admitted = blocking_predicate & 255 == 0 and latch == 0
    if admitted:
        if category != 0:
            words[category] = (words[category] + 1) & 0xFFFFFFFF
        if replay_counter == 0 and segment_count is not None:
            segment_count = (segment_count + 1) & 0xFFFFFFFF
    return {"admitted": admitted, "category_words": words, "segment_count": segment_count,
            "post_callback_latch_if_calls_return": 1 if admitted else latch}


def blocking_preview(context_word_58, state_word, secondary_predicate, secondary_mode):
    """Exact numeric branches only; no runtime subsystem names inferred."""
    for name, value in (("context_word_58", context_word_58), ("state_word", state_word),
                        ("secondary_predicate", secondary_predicate), ("secondary_mode", secondary_mode)):
        _word(value, name)
    return int(context_word_58 != 0 or 7 <= state_word <= 9 or
               secondary_predicate & 255 != 0 and secondary_mode in (7, 9))


def latch_service_preview(latch, readiness_bits):
    """Post-callback latch if callback returns; raw IEEE754 bits preserve NaN."""
    _word(latch, "latch")
    _word(readiness_bits, "readiness_bits")
    value = struct.unpack(">f", struct.pack(">I", readiness_bits))[0]
    return 0 if latch == 1 and value >= 1.0 else latch


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    # Independent native checks supplement the prior counter-storage report.
    checks = {
        0x8954D4: 0x101D5C30, 0x8954F4: 0x3F800000,
        0x89F078: 0x101E8D70, 0x89F098: 0x101EFB20,
        0x1E1E64: 0x83E2559C, 0x1E1E6C: 0x801F0068,
        0x1E1E70: 0x2F800001, 0x1E1EB0: 0x38800000, 0x1E1EB4: 0x909F0068,
        0x1E1E98: 0xC00255BC, 0x1E1E9C: 0xFC010000, 0x1E1EA0: 0x4C411382,
        0x1E1EF8: 0x5463063E, 0x1E1EFC: 0x2F830000,
        0x1E1F04: 0x83E2559C, 0x1E1F08: 0x809F0068,
        0x1E1F0C: 0x2C040000, 0x1E1F50: 0x38A00001, 0x1E1F58: 0x90BF0068,
        0x2CE528: 0x800B0048, 0x2CE530: 0x2F800000,
        0x2CE54C: 0x38C70001, 0x2CE550: 0x90C50014,
        0x2CE560: 0x2C0A0000, 0x2CE584: 0x2C830000,
        0x2CE5A4: 0x38040001, 0x2CE5B0: 0x90030008,
        0x2D186C: 0x800906EC, 0x2D1870: 0x2F800000,
        0x3BFB0: 0x38600005, 0x43578: 0x38600002,
        0x4BB04: 0x38600004, 0x55094: 0x38600006,
        0x18F4AC: 0x38600007, 0x18F4E0: 0x38600003,
    }
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Reset context instruction/pointer changed at {address:#x}")
    calls = ((0x1E1EE0, 0x7B358), (0x1E1EEC, 0x7EB48),
             (0x1E1F30, 0x13680), (0x1368C, 0x2CE518),
             (0x1E1F40, 0x244760), (0x1E1F48, 0x11050),
             (0x1E1E90, 0x244658), (0x1E1EA8, 0x11920),
             (0x2CE554, 0x2D1860), (0x2CE580, 0x2CDF40),
             (0x7EB54, 0x7B350), (0x7EB98, 0x13490), (0x1349C, 0x48B4A8),
             (0x1192C, 0x38E3B0), (0x1105C, 0x60C7E8), (0x252264, 0x1E1E58))
    for call, target in calls:
        if BINDINGS.branch_target(elf.u32(call), call) != target:
            raise ValueError(f"Reset context call changed at {call:#x}")
    if elf.descriptors[0x1E1ED0] != 0x88FF38 or elf.descriptors[0x1E1E58] != 0x88FF38:
        raise ValueError("Reset context owner TOC changed")
    contexts = [(5, 0x842128, 0x85AE20, 0x3BFA0),
                (2, 0x842178, 0x85B048, 0x433B0),
                (4, 0x8421F8, 0x85B218, 0x4B9E8),
                (6, 0x842260, 0x85B3D8, 0x54FB0),
                ([3, 7], 0x8482E0, 0x864478, 0x18F480)]
    catalog = []
    for categories, table, descriptor, function in contexts:
        if elf.u32(table + 0x10) != descriptor or struct.unpack(">II", elf.read(descriptor, 8)) != (function, 0x88FF38):
            raise ValueError("Category selector virtual-dispatch context changed")
        catalog.append({"categories": categories if isinstance(categories, list) else [categories],
                        "vtable_va": hex(table), "method_offset": "0x10",
                        "descriptor_va": hex(descriptor), "function_va": hex(function),
                        "scope": "Category selection is in this virtual callback. Actor type, event name and invocation frequency remain unconfirmed."})
    ranges = [(0x1E1E58, 0x78), (0x1E1ED0, 0xA4), (0x13680, 0x10),
              (0x2CE518, 0xB4), (0x2D1860, 0x24), (0x7B350, 8), (0x7B358, 12),
              (0x7EB48, 0xA4), (0x244658, 0x14), (0x13490, 0x10),
              (0x11920, 0x10), (0x11050, 0x10), (0x252258, 0x10),
              (0x88B0EC, 4), (0x88B200, 8), (0x897CC0, 4)]
    guards = {address: elf.read(address, 4) for address in checks}
    guards.update({address: elf.read(address, size) for address, size in ranges})
    guards.update({call: elf.read(call, 4) for call, _ in calls})
    for _, table, descriptor, _ in contexts:
        guards[table + 0x10] = elf.read(table + 0x10, 4)
        guards[descriptor] = elf.read(descriptor, 8)
    report = {
        "confidence": "code-backed",
        "admission": {
            "function_va": "0x1e1ed0", "owner_pointer_slot_va": "0x8954d4",
            "runtime_owner_va": "0x101d5c30", "runtime_latch_offset": "0x68",
            "predicate_calls": ["0x7b358", "0x7eb48"],
            "rule": "Admits only when low byte of 7EB48(7B358()) is zero and runtime word +68 is zero. Other cases return0 without the counter writer.",
            "ordered_calls": ["0x13680 -> 0x2ce518", "0x244760", "0x11050"],
            "publication_store_va": "0x1e1f58",
            "publication": "Only after those calls return does this wrapper store latch1 and return1. The latch is not set before recording. No atomicity or callback reentry safety is proven.",
            "not_serialized": "Runtime owner101D5C30 and category owner101E8D70 are below serialized state101EFB20; neither latch nor current category is a saved byte."},
        "blocking_context": {
            "function_va": "0x7eb48", "context_getter_va": "0x7b350",
            "context_pointer_slot_va": "0x88b0ec", "context_va": hex(elf.u32(0x88B0EC)),
            "context_word_offset": "0x58", "state_word_pointer_slot_va": "0x88b200",
            "state_word_va": hex(elf.u32(0x88B200)),
            "secondary_owner_pointer_slot_va": "0x88b204", "secondary_owner_va": hex(elf.u32(0x88B204)),
            "secondary_mode_offset": "0x20", "secondary_predicate_chain": "0x13490 -> 0x48b4a8",
            "rule": "Returns1 when runtime context+58 is nonzero, or unsigned runtime state word is7..9. Otherwise returns0 if low byte of48B4A8 is0; if nonzero, returns1 only for secondary context+20 equal7 or9.",
            "scope": "7EB48 does not consume the passed7B358 +170 subobject in this native body; it calls7B350 to fetch the separate context. Numeric states are not named pause, death, failure or game-mode enums."},
        "latch_service": {
            "function_va": "0x1e1e58", "clear_store_va": "0x1e1eb4",
            "caller_thunk_va": "0x252258", "readiness_getter_va": "0x244658",
            "runtime_singleton_pointer_slot_va": "0x897cc0", "runtime_readiness_offset": "0x5b62c",
            "threshold_va": "0x8954f4", "threshold": 1.0,
            "clear_callback_chain": "0x11920 -> 0x38e3b0",
            "rule": "Services only latch==1. Runtime singleton float+5B62C must compare ordered >=1.0; NaN does not qualify. Qualified branch calls11920→38E3B0 then stores latch0. Other nonzero latch values block admission but are not serviced by this function.",
            "scope": "The predicate's gameplay meaning, timer units, external-call side effects and reentry are not inferred."},
        "counter_dependencies": {
            "writer_va": "0x2ce518", "category_offset": "0x5734", "category_count": 8,
            "category_rule": "Admitted wrapper calls writer. Nonzero runtime category increments one BE32 word modulo32 before the saved replay/restart gate. Category0 skips its word.",
            "segment_rule": "Segment+08 increments modulo32 only if saved906EC is zero and2CDF40 resolves a nonnull segment. The same branch zeroes segment+04 and adds old segment+04 * runtime config10FC8 to segment+00.",
            "scope": "Arithmetic preview accepts only physical IDs0..7; native writer has no such bound. No death count, challenge-failure name, count equality or current actor is reconstructed."},
        "virtual_selector_contexts": catalog,
        "unresolved": ["Category1 selection and all player-facing category names remain unresolved.",
                       "Virtual callback presence does not establish actor class names or current actor selection.",
                       "External callbacks and runtime predicates are not executed or simulated."],
        "recommended_annotations": [
            {"va": "0x1e1ed0", "name": "AdmitResetRequest_RecordBeforeLatchPublication", "kind": "function",
             "comment": "Low-byte blocking predicate must be0 and runtime101D5C30+68 must be0. Calls13680→2CE518 then244760 and11050 before publishing latch1; callback reentry/atomicity unproved. Latch is not serialized."},
            {"va": "0x1e1e58", "name": "ServiceResetRequestLatch_ExactOneOnly", "kind": "function",
             "comment": "Only runtime101D5C30+68==1 reaches244658 reading singletonfloat+5B62C. Ordered >=1.0 calls11920→38E3B0 before clearing latch0. NaN and other nonzero latch values do not clear here; gameplay predicate meaning unconfirmed."}],
        "instruction_guards": [{"va": hex(address), "bytes": raw.hex().upper()} for address, raw in sorted(guards.items())],
    }
    if save_path is not None:
        if Path(save_path).stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save layout")
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        words = [struct.unpack_from(">I", data, 0x5734 + i * 4)[0] for i in range(8)]
        replay = struct.unpack_from(">I", data, 0x906EC)[0]
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "category_words": words, "saved_replay_restart_counter": replay,
            "scope": "Snapshot supplies saved counts/gate only. Admission predicate, latch, category and resolved current segment are runtime-only and cannot be observed from this save."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path, help="Detached plaintext save; never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2))
