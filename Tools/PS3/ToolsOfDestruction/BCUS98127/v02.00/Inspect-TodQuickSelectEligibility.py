"""Exact-build initial item flags, registry linkage and bounded quick-select edit plans."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))


def returns_without_branch(elf, address):
    for va in range(address, address+0x40, 4):
        word = elf.u32(va)
        if word == 0x4E800020:
            return True
        if word >> 26 in (16, 18, 19):
            return False
    return False


def literal_argument(elf, start, store, register):
    """Observed LI-to-STD suffix; known base calls preserve compiled nonvolatile GPRs."""
    for va in range(store-4, start-4, -4):
        word = elf.u32(va)
        op, target, base = word >> 26, (word >> 21) & 31, (word >> 16) & 31
        if op == 16 and not word & 3:
            destination = va + BINDINGS["signed"](word & 0xFFFC, 16)
            if start <= destination < va and returns_without_branch(elf, destination):
                continue # The taken admission branch exits; only fallthrough reaches the argument.
        if op == 18 and word & 1 and register >= 14 and BINDINGS["branch_target"](word, va) in (0x251398, 0x10D10):
            continue
        if op in (16, 18, 19):
            raise ValueError("Flags source crosses a branch/call")
        if op == 14 and target == register:
            if base != 0:
                raise ValueError("Flags require a direct literal")
            return BINDINGS["signed"](word & 65535, 16) & 0xFFFFFFFF, va
        if op in (14, 15, 32, 58) and target == register:
            raise ValueError("Flags source is not a recognized literal")
        if op in (24, 25, 30, 31) and base == register:
            raise ValueError("Flags source has an unmodeled register write")
        if op not in (14, 15, 24, 25, 31, 32, 36, 48, 52, 58, 62):
            raise ValueError("Unrecognized flags argument suffix")
    raise ValueError("Flags literal not found")


def edit_plan(slots, changes, eligible_ids, owned_ids):
    """Editor policy: first24 only; preserve other words, refuse new duplicates."""
    if not isinstance(slots, (list, tuple)) or len(slots) != 32 or any(
            type(value) is not int or not -0x80000000 <= value <= 0x7FFFFFFF for value in slots):
        raise ValueError("Expected32 explicit signed slot words")
    if not isinstance(changes, dict):
        raise ValueError("Expected explicit slot changes")
    for ids in (eligible_ids, owned_ids):
        if not isinstance(ids, (list, tuple, set)) or any(type(value) is not int or not 0 <= value < 32 for value in ids):
            raise ValueError("Expected normal reference item IDs")
    result = list(slots)
    changed = []
    for slot, value in changes.items():
        if type(slot) is not int or not 0 <= slot < 24 or type(value) is not int:
            raise ValueError("Only physical slots0..23 may change")
        if value == slots[slot]:
            continue
        if value != -1 and (value not in eligible_ids or value not in owned_ids):
            raise ValueError("New assignment requires owned, initially eligible item")
        result[slot] = value
        changed.append(slot)
    for slot in changed:
        if result[slot] >= 0 and result.count(result[slot]) > 1:
            raise ValueError("New assignment duplicates an item in the32-slot bank")
    return {"slots": result, "changed_slots": sorted(changed),
            "qualification": "Detached conservative editor policy, NOT native assignment emulation. Does not increment8734, set8738, change ownership, compact slots or infer wheel positions/runtime eligibility."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    binding = BINDINGS["inspect"](elf_path)
    guards = {}
    expected = {
        0x466798: 0xF821FF61, 0x4667FC: 0x80810114, 0x466804: 0x908B0018,
        0x4667E0: 0x908B0000, 0x8A5E84: 0x103697B8,
        0x4632E8: 0x80625F64, 0x4632EC: 0x38630020,
        0x467B00: 0x80C40000, 0x467B0C: 0x7C83012E, 0x467B10: 0x4E800020,
        0x467B18: 0x2B84001F, 0x467B30: 0x7C69002E, 0x467B38: 0x4E800020,
        0x11210: 0xF8410028, 0x11214: 0x3C420001, 0x11218: 0x3842FFE8,
        0x13B90: 0xF8410028, 0x13B94: 0x3C420001, 0x13B98: 0x3842FFE8,
        0x26E2C: 0x83C286EC, 0x26E30: 0x2B04001F, 0x26E48: 0x2B83001F,
        0x26E68: 0x912A8734, 0x26E8C: 0x93A30004, 0x26EC8: 0x80030018,
        0x26ECC: 0x38A01040, 0x26EE8: 0x4086FFA8, 0x26EEC: 0x93A30004,
        0x888624: 0x101EFB20,
    }
    # The direct setter's TOC is88FF38; -7914 resolves the canonical save.
    for va, word in expected.items():
        if elf.u32(va) != word:
            raise ValueError(f"Quick-select eligibility evidence changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    for va, target, linked in ((0x4668A4, 0x4632D8, True), (0x4632F0, 0x467B00, True),
                               (0x4631A8, 0x467B18, True), (0x1121C, 0x466798, False),
                               (0x13B9C, 0x463190, False), (0x26EB8, 0x13B90, True),
                               (0x2513A4, 0x63BC60, False), (0x10D1C, 0x63BC60, False),
                               (0x63BC70, 0x59E4B0, True)):
        if BINDINGS["branch_target"](elf.u32(va), va) != target or bool(elf.u32(va) & 1) != linked:
            raise ValueError("Quick-select definition call changed")
        guards[va] = elf.read(va, 4)
    for va in (0x466798, 0x4632D8, 0x467B00, 0x467B18, 0x463190, 0x26E20, 0x63BC60):
        position = elf.functions.index(va)
        guards[va] = elf.read(va, elf.functions[position+1]-va)
    for va in (0x251398, 0x10D10, 0x11210, 0x13B90):
        guards[va] = elf.read(va, 16)
    catalog = []
    for item in binding["constructor_calls"]:
        start, call = int(item["constructor_va"], 0), int(item["call_va"], 0)
        stores = [(va, word) for va, word in elf.instructions(start, call)
                  if word >> 26 == 62 and (word >> 16) & 31 == 1 and word & 65535 == 0x70]
        if len(stores) != 1:
            raise ValueError("Expected one flags stack argument store")
        store, instruction = stores[0]
        try:
            flags, literal = literal_argument(elf, start, store, (instruction >> 21) & 31)
        except ValueError as error:
            raise ValueError(f"Constructor ID{item['id']} at{start:#x}, store{store:#x}: {error}") from error
        position = elf.functions.index(start)
        guards[start] = elf.read(start, elf.functions[position+1]-start)
        catalog.append({"id": item["id"], "enum": item["enum"], "config_name": item["config_name"],
                        "constructor_va": hex(start), "call_va": hex(call),
                        "flags_literal_va": hex(literal), "flags_argument_store_va": hex(store),
                        "initial_flags": f"0x{flags:08X}", "quick_select_initially_allowed": flags & 0x1040 == 0})
    catalog.sort(key=lambda row: row["id"])
    if [row["id"] for row in catalog] != list(range(32)):
        raise ValueError("Incomplete initial definition catalog")
    report = {
        "confidence": "exact-build-initial-definition-flags-and-quick-select-reference-filter",
        "catalog": catalog,
        "literal_source_rule": "Bounded LI-to-STD register-flow decoder permits only admission branches to a verified straight-line return, and known base-initializer calls for compiled nonvolatile GPR sources. It rejects volatile call-crossing, unknown calls/writes and general branch merging; this is not a general PPC emulator.",
        "definition_linkage": "466798 allocates stackA0, loads the low32 of caller STD+70 from callee+114, then stores definition+18 at466804. ID goes to definition+0. It calls4632D8, which publishes through call-free467B00 at registry103697B8+20+4*ID. Resolver463190 uses the same registry;467B18 returns a pointer only for unsigned ID<=31. Thunks11210/13B90 adjust88FF38->89FF20 without changing SP, preserving the argument slot. Constructor admission/runtime lifetime and later overrides remain separate.",
        "assignment": "Named26E20 reads definition+18 and rejects flags&1040 before writing saved284+4*slot. It admits all32 physical slots and writes directly without ownership or duplicate-removal checks. Its warning counter8734 is updated BEFORE those gates. Hero insertion uses first24 and removes duplicates across32; the two APIs are not interchangeable.",
        "edit_policy": "Editor exposes slots0..23 only, clear=-1 or owned items with initial flags&1040==0. Batch preflight rejects newly created duplicates across all32 physical slots, but allows clearing or explicitly moving within first24. Last8 slots, unknown current values, ownership, warning state and other bytes are retained. This policy is intentionally stricter than native direct assignment, not a recovered gameplay transaction.",
        "warning": "USA BCUS98127 v02.00 initialization reference only. Literal flow across known base-initializer calls follows the compiled nonvolatile-GPR preservation convention; volatile or unknown-call sources are refused. Flags are runtime definition fields, not saved eligibility bits. Does not prove live definition availability, dynamic overrides, UI wheel layout, current equip/selection, valid other builds or in-game edit acceptance.",
        "recommended_annotations": [
            {"va": "0x466804", "kind": "comment", "name": "TOD_definition_initial_flags_from_caller_stack_argument", "comment": "Callee frameA0 +114 reads caller STD+70 low32 flags; store definition+18 before registry publication.32 initializer literals cataloged; not live eligibility or a saved field."},
            {"va": "0x467b0c", "kind": "comment", "name": "TOD_definition_publish_indexed_pointer_no_local_id_bound", "comment": "Call-free leaf reads definition+0 ID then stores its pointer at supplied registry+4*ID.4632D8 passes103697B8+20. Publication leaf has no local bounds; later467B18 lookup checks unsigned<=31."},
        ],
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())],
    }
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, id*20)[0] != id for id in range(32)):
            raise ValueError("Not verified plaintext layout")
        report["save_observation"] = {"sha256": hashlib.sha256(data).hexdigest().upper(),
            "slots": list(struct.unpack_from(">32i", data, 0x284)),
            "owned_reference_choices": [row["id"] for row in catalog if row["quick_select_initially_allowed"] and data[row["id"]*20+16] != 0],
            "warning": report["warning"]}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
