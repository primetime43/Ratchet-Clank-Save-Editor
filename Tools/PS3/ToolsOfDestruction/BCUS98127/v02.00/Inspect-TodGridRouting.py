"""Exact-build read-only grid browse order, image routing and accumulator predicate."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("grid", Path(__file__).with_name("Inspect-TodPersistentGrid.py"))
GRID = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GRID)
BINDINGS = GRID.STORAGE.BINDINGS


def decode_switch(elf, function, load, count, register, shared_return, guards):
    if elf.u32(function) != 0x2B830014 or elf.u32(load) & 0xFFFF0000 != 0x81620000:
        raise ValueError("Grid switch bounds or TOC load changed")
    slot = elf.descriptors[function] + BINDINGS.signed(elf.u32(load) & 65535, 16)
    table = elf.u32(slot)
    guards[slot] = elf.read(slot, 4)
    guards[table] = elf.read(table, count * 4)
    values = []
    for index in range(count):
        case = table + BINDINGS.signed(elf.u32(table + index * 4), 32)
        word = elf.u32(case)
        if (word & 0xFFFF0000) != (0x38000000 | register << 21):
            raise ValueError("Grid switch case no longer loads a literal")
        if case + 4 != shared_return and BINDINGS.branch_target(elf.u32(case + 4), case + 4) != shared_return:
            raise ValueError("Grid switch shared return changed")
        guards[case] = elf.read(case, 8)
        values.append(word & 65535)
    return {"function_va": hex(function), "table_va": hex(table), "table_slot_va": hex(slot), "values": values}


def observe(data, report):
    if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
        raise ValueError("Not the verified plaintext save layout")
    blocks, predicate = report["blocks"], report["accumulator_predicate"]
    base, stride = int(blocks["base"], 0), int(blocks["stride"], 0)
    qualifying, rows = [], []
    for slot in range(blocks["count"]):
        offset = base + slot * stride
        accumulator = struct.unpack_from(">I", data, offset + 0xC8)[0]
        ready = data[offset + 0xCC]
        qualifies = accumulator >= predicate["threshold"]
        if qualifies:
            qualifying.append(slot)
        rows.append({"slot": slot, "ready_byte": ready,
            "browse_ordinal": report["slot_to_browse"]["values"][slot],
            "image_index": report["slot_to_image"]["values"][slot],
            "saved_accumulator": accumulator, "qualifies_accumulator_predicate": qualifies})
    browse = report["browse_to_slot"]["values"]
    ready_by_slot = {row["slot"]: row["ready_byte"] for row in rows}
    return {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(), "slots": rows,
        "ready_slots_in_browse_order": [slot for slot in browse if ready_by_slot[slot] != 0],
        "qualifying_slots": qualifying, "qualifying_count": len(qualifying),
        "predicate_result": len(qualifying) > predicate["count_must_exceed"],
        "warning": "Snapshot evaluation only. The predicate reads all accumulator words without a readiness gate, not exact cleared-cell counts. No trophy/completion caller or in-game edit acceptance established."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    checks = {0x35E170: 0x1D7F60DC, 0x35E180: 0x390914D8, 0x35E190: 0x2C3F0015,
        0x24E7E8: 0x81027FD0, 0x24E7F0: 0x81427FCC, 0x24E7FC: 0x394A60DC,
        0x24E808: 0x80AB0000, 0x24E80C: 0x3C85FFFD, 0x24E810: 0x3864999A,
        0x24E814: 0x78690FE0, 0x24E818: 0x7D290050, 0x24E820: 0x2809000F,
        0x24E3A0: 0x419D0078, 0x24E4C8: 0x419D0078, 0x24E5EC: 0x419D0074,
        0x24E39C: 0x38000015, 0x24E4C4: 0x3800FFFF, 0x24E660: 0x38600015,
        0x25D21C: 0x4BFF4EAD, 0x25D288: 0x4BFF4031, 0x25D2E4: 0x4BFF2DF5,
        0x25BD14: 0x4BFF43C5, 0x25D4CC: 0x89680014, 0x25D5AC: 0x88090014,
        0x25D4C0: 0x39991590, 0x25D5A0: 0x38A41590, 0x25D290: 0x814283CC}
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Grid routing instruction changed at {address:#x}")
    guards = {a: elf.read(a, 4) for a in checks}
    for function in (0x24E398, 0x24E4C0, 0x24E5E8, 0x24E7E8, 0x25D1D0, 0x25BBF0):
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    for thunk, target in ((0x2520C8, 0x24E398), (0x2512B8, 0x24E4C0), (0x2500D8, 0x24E5E8)):
        guards[thunk] = elf.read(thunk, 16)
        if BINDINGS.branch_target(elf.u32(thunk + 12), thunk + 12) != target:
            raise ValueError("Grid menu TOC thunk changed")
    count = elf.u32(0x35E190) & 65535
    base = 0x10000 + (elf.u32(0x35E180) & 65535)
    stride = elf.u32(0x35E170) & 65535
    slot_browse = decode_switch(elf, 0x24E398, 0x24E3A4, count, 0, 0x24E418, guards)
    browse_slot = decode_switch(elf, 0x24E4C0, 0x24E4CC, count, 0, 0x24E540, guards)
    slot_image = decode_switch(elf, 0x24E5E8, 0x24E5F0, count, 3, 0x24E664, guards)
    if sorted(slot_browse["values"]) != list(range(count)) or any(
            browse_slot["values"][slot_browse["values"][slot]] != slot for slot in range(count)):
        raise ValueError("Grid browse switches are not inverse permutations")
    toc = elf.descriptors[0x24E7E8]
    first_slot = toc + BINDINGS.signed(elf.u32(0x24E7F0) & 65535, 16)
    end_slot = toc + BINDINGS.signed(elf.u32(0x24E7E8) & 65535, 16)
    first, end = elf.u32(first_slot), elf.u32(end_slot)
    state_slot = elf.descriptors[0x25D1D0] + BINDINGS.signed(elf.u32(0x25D290) & 65535, 16)
    state = elf.u32(state_slot)
    for slot in (first_slot, end_slot, state_slot):
        guards[slot] = elf.read(slot, 4)
    guards[0x869388] = elf.read(0x869388, 8)
    if elf.u32(0x869388) != 0x24E7E8 or elf.u32(0x86938C) != toc:
        raise ValueError("Grid predicate descriptor changed")
    if first != state + base + 0xC8 or end != first + stride * count:
        raise ValueError("Grid accumulator pointer range changed")
    if first - state + (count - 1) * stride + 4 > 0x906F0:
        raise ValueError("Grid predicate reads outside serialized state")
    threshold = -(BINDINGS.signed(elf.u32(0x24E80C) & 65535, 16) * 65536
        + BINDINGS.signed(elf.u32(0x24E810) & 65535, 16))
    slot_browse["out_of_range_result"] = elf.u32(0x24E39C) & 65535
    browse_slot["out_of_range_result"] = BINDINGS.signed(elf.u32(0x24E4C4) & 65535, 16) & 0xFFFFFFFF
    slot_image["out_of_range_result"] = elf.u32(0x24E660) & 65535
    report = {"confidence": "code-backed",
        "warning": "Exact USA v02.00 only. Browse ordinal, saved physical slot, map-label level and resource image index are different namespaces. Native aggregate predicate has no confirmed gameplay caller; do not label it trophy/completion progress.",
        "blocks": {"base": hex(base), "stride": hex(stride), "count": count},
        "slot_to_browse": slot_browse, "browse_to_slot": browse_slot, "slot_to_image": slot_image,
        "menu_provenance": {"consumer_va": "0x25d1d0", "initial_consumer_va": "0x25bbf0",
            "selection_runtime_member": "0xad0", "selected_saved_block_pointer_member": "0xb08",
            "ready_save_member": "0xcc", "state_pointer_slot_va": hex(state_slot),
            "semantics": "25D1D0 converts selected slot to browse ordinal via2520C8->24E398, wraps directional searches over21 ordinals, converts back via2512B8->24E4C0 and skips saved ready byte0 at block+CC. Nonzero flags are accepted without normalization. It stores runtime selection+AD0 and block pointer+B08; these are not new save fields.",
            "image_semantics": "25BBF0 and25D1D0 call2500D8->24E5E8, feeding its image index to251898 with512 extent and20000 flags; a separate call uses physical slot with80000 flags. Shared image indices do not merge their distinct saved grid slots. Image file names/palette are not proven."},
        "accumulator_predicate": {"function_va": "0x24e7e8", "first_pointer_slot_va": hex(first_slot),
            "end_pointer_slot_va": hex(end_slot), "first_runtime_va": hex(first), "end_pointer_va": hex(end),
            "first_save_offset": hex(first - state), "stride": hex(stride), "count": count,
            "threshold": threshold, "comparison": "unsigned saved accumulator >= threshold",
            "count_must_exceed": elf.u32(0x24E820) & 65535, "ready_gate": False,
            "semantics": "Reads21 BE32 encoder accumulators at block+C8, counts each word >=0x36666, returns1 iff count>15. The end pointer is a stride sentinel beyond the serialized end; it is never dereferenced. No decoding or ready-byte test is performed. Accumulator is not exact zero-cell count or checksum.",
            "caller_evidence": "Only function descriptor869388 references code24E7E8 in the native scan; no descriptor-pointer references or direct callers found. Gameplay invocation/purpose remains unresolved."},
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save layout")
        report["save_observation"] = observe(path.read_bytes(), report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path, help="Plaintext working copy; never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2))
