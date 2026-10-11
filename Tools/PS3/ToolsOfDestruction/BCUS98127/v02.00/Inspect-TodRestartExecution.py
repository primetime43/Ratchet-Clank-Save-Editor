"""Exact-build private restart-bank capture, selection and retained-byte ownership.

Read-only static evidence and bounded detached previews. No native/Lua execution,
allocation, restart action, save repair or claim of gameplay acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
SAVE_SIZE = 0x906F0
RETAINED = (("segment_log_bytes", 0x8764, 0x10144),)
MISSION_CLEARS = (("active_mission_lists", 0x10148, 0x10AF8),
                  ("completed_mission_lists", 0x10AF8, 0x114A8))


def u32(value):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("Expected an unsigned32-bit integer")
    return value


def detached(value):
    if not isinstance(value, (bytes, bytearray)) or len(value) != SAVE_SIZE:
        raise ValueError("Expected exactly906F0 detached bytes")
    return bytes(value)


def constructor_gate_preview(phase, qualifier):
    phase, qualifier = u32(phase), u32(qualifier)
    return "initialize both banks" if (phase, qualifier) == (1, 0xFFFF) else (
        "manager-side teardown only" if (phase, qualifier) == (0, 0xFFFF) else "no operation")


def phase_one_capture_preview(live, private_bank, entry_latch):
    """Only phase1's byte-copy branch; all handle/UI helpers are deliberately omitted."""
    live, private_bank = detached(live), detached(private_bank)
    entry_latch = u32(entry_latch)
    if entry_latch > 255:
        raise ValueError("Entry latch must fit the observed byte")
    return {"private_bank": live if entry_latch != 0 else private_bank,
            "entry_latch_after": 0, "copied": entry_latch != 0,
            "scope": "Conditional byte copy only, assumes native handle-resolution path reached its copy; no allocation or UI execution."}


def selection_preview(phase, entry_latch, selector_result):
    """Phase4 entry-latch-zero suffix, after native UI helper returns raw low32."""
    phase, entry_latch, selector_result = map(u32, (phase, entry_latch, selector_result))
    if phase != 4 or entry_latch != 0:
        raise ValueError("Preview only covers phase4 with consumed entry latch; earlier UI setup is not emulated")
    action = "selective restart" if selector_result == 0 else "full private-bank restore" if selector_result == 1 else None
    return {"action": action, "action_va": "0x3ced40" if selector_result == 0 else "0x3cf1b8" if selector_result == 1 else None,
            "phase_after": 5 if action else 4, "entry_latch_after": 1 if action else 0,
            "ordering": ["helper250ED8", action, "publish phase5 and entry latch1"] if action else [],
            "request_arguments": [0, 0, 1] if selector_result == 0 else [18, 1, 1] if selector_result == 1 else None}


def arena_bank_preview(base, capacity, front_used, back_used, reverse):
    """Safe normal-domain arithmetic only; rejects underflow/overlap native code does not check."""
    base, capacity, front_used, back_used = map(u32, (base, capacity, front_used, back_used))
    if type(reverse) is not bool or base + capacity > 0xFFFFFFFF or front_used + back_used > capacity:
        raise ValueError("Invalid bounded arena inputs")
    if reverse:
        pointer = (base + capacity - back_used - SAVE_SIZE) & ~15
        if pointer < base + front_used:
            raise ValueError("Insufficient arena space; unsafe native arithmetic is not emulated")
        return {"pointer": pointer, "front_used": front_used, "back_used": base + capacity - pointer}
    aligned_offset = (front_used + 15) & ~15
    if aligned_offset + SAVE_SIZE > capacity - back_used:
        raise ValueError("Insufficient arena space; unsafe native arithmetic is not emulated")
    return {"pointer": base + aligned_offset, "front_used": aligned_offset + SAVE_SIZE, "back_used": back_used}


def retained_region_preview(private_bank):
    """Only untouched ranges at selective restart's final copy boundary, NOT its full output."""
    bank = detached(private_bank)
    return {name: bank[start:end] for name, start, end in RETAINED}


def initializer_region_preview(private_bank):
    """Only nested35D9A0's proven log/mission/Decryptor byte ownership; not full restart."""
    bank = detached(private_bank)
    return {"segment_log_bytes": bank[0x8764:0x10144],
            "log_count": bytes(4), "decryptor_words": bytes.fromhex("00000000000000003F800000"),
            **{name: bytes(end - start) for name, start, end in MISSION_CLEARS}}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}

    def keep(va, size):
        guards[va] = elf.read(va, size)

    expected = {
        0x8A3BAC: 0x101EFB20, 0x8A3BD0: 0x1064FC80, 0x8A3BD4: 0x10690580,
        0x8A3BE8: 0x3CF3DC, 0x8524B0: 0x8726D0,
        0x8726B8: 0x3CED40, 0x8726BC: 0x89FF20,
        0x8726C0: 0x3CF1B8, 0x8726C4: 0x89FF20,
        0x8726D0: 0x3CF228, 0x8726D4: 0x89FF20,
        0x8726E0: 0x3CF378, 0x8726E4: 0x89FF20,
        0x3CF2C8: 0x3809F910, 0x3CF2CC: 0x54090036,
        0x3CF2F0: 0x913F0080, 0x3CF358: 0x3809000F,
        0x3CF35C: 0x540C0036, 0x3CF36C: 0x90A70008,
        0x3CF3B8: 0x2B800004, 0x3CF3D8: 0x4E800420,
        0x3CF5B4: 0x88DE0008, 0x3CF5C0: 0x997E0008,
        0x3CF5C4: 0x419A0044, 0x3CF5E8: 0x807D0080,
        0x3CF5F4: 0x80823C8C, 0x3CF600: 0x4BE82E29,
        0x3CF610: 0x4BE81B79, 0x3CF618: 0x547D063E,
        0x3CF61C: 0x2C1D0000, 0x3CF620: 0x4182FE28,
        0x3CF628: 0x38000002, 0x3CF524: 0x7F83E378,
        0x3CF528: 0x4BE94891, 0x3CF530: 0x2C830000,
        0x3CF538: 0x418600F8, 0x3CF53C: 0x2F030001,
        0x3CF540: 0x409AFF08, 0x3CF550: 0x4BFFFC69,
        0x3CF558: 0x38800005, 0x3CF55C: 0x9BFE0008,
        0x3CF560: 0x909E0000, 0x3CF63C: 0x4BFFF705,
        0x3CF644: 0x38000005, 0x3CF64C: 0x901E0000,
        0x3CF650: 0x9B5E0008, 0x3CF1C8: 0x80830080,
        0x3CF1D4: 0x4BE83255, 0x3CF1E8: 0x4BF024B9,
        0x35C760: 0x2F830001, 0x35C788: 0x6C9DFFFF,
        0x35C78C: 0x2F1DFFFF, 0x35C7B0: 0x6C83FFFF,
        0x35C7B4: 0x2C03FFFF, 0x35C8C4: 0x4800184D,
        0x35C990: 0x48001781, 0x35C9DC: 0x4BEF478D,
        0x3CED80: 0x4BF8F391, 0x3CF158: 0x4BE832D1,
        0x35DBB8: 0x93ACAC1C,
        0x35E198: 0x381E5528, 0x35E1AC: 0x4BFFF7F5,
        0x35DB64: 0x393F321C, 0x35DB68: 0xC0021A24,
        0x35DB7C: 0x3BA00000, 0x35DB80: 0x387CAC20,
        0x35DB8C: 0x38800000, 0x35DB90: 0x38A009B0,
        0x35DBA4: 0x93A80014, 0x35DBA8: 0x93A80018,
        0x35DBAC: 0xD008001C, 0x35DBBC: 0x4BEF4D7D,
        0x35DBC4: 0x38FCB5D0, 0x35DBC8: 0x38800000,
        0x35DBD0: 0x38A009B0, 0x35DBD4: 0x4BEF4D65,
        0x8A1944: 0x3F800000,
        0x2CE3C4: 0x806A0144, 0x2CE3CC: 0x1C83009C,
        0x2CE3D8: 0x38C88750, 0x2CE3E8: 0x3B9D0014,
    }
    for va, word in expected.items():
        if elf.u32(va) != word:
            raise ValueError(f"Restart execution evidence changed at {va:#x}")
        keep(va, 4)
    # Includes disjoint inline case bodies that Ghidra's old function body omitted.
    for start, end in ((0x3CF228, 0x3CF378), (0x3CF378, 0x3CFA50),
                       (0x3CED40, 0x3CF1B8), (0x3CF1B8, 0x3CF200),
                       (0x35C760, 0x35CA20), (0x35E110, 0x35E240),
                       (0x35D9A0, 0x35DC80)):
        keep(start, end - start)
    keep(0x3CF3DC, 20)
    relative = struct.unpack(">5i", elf.read(0x3CF3DC, 20))
    targets = [0x3CF3DC + displacement for displacement in relative]
    if targets != [0x3CF47C, 0x3CF5B4, 0x3CF3F0, 0x3CF570, 0x3CF4EC]:
        raise ValueError("Restart phase switch destinations changed")
    calls = {va: BINDINGS["branch_target"](elf.u32(va), va) for va in
             (0x3CF600, 0x3CF610, 0x3CF528, 0x3CF544, 0x3CF550, 0x3CF630, 0x3CF63C)}
    if list(calls.values()) != [0x252428, 0x251188, 0x263DB8, 0x250ED8, 0x3CF1B8, 0x250ED8, 0x3CED40]:
        raise ValueError("Capture/action helper call chain changed")
    signed = BINDINGS["signed"]
    log_base = 0x10000 + signed(elf.u32(0x2CE3D8) & 65535, 16) + (elf.u32(0x2CE3E8) & 65535)
    log_end = 0x10000 + (elf.u32(0x2CE3C4) & 65535)
    log_stride = elf.u32(0x2CE3CC) & 65535
    inner_base = elf.u32(0x35E198) & 65535
    mission_starts = [inner_base + 0x10000 + signed(elf.u32(va) & 65535, 16) for va in (0x35DB80, 0x35DBC4)]
    mission_sizes = [elf.u32(va) & 65535 for va in (0x35DB90, 0x35DBD0)]
    memset_targets = [BINDINGS["branch_target"](elf.u32(va), va) for va in (0x35DBBC, 0x35DBD4)]
    if (log_base, log_end, log_stride) != (0x8764, 0x10144, 0x9C) or log_end - log_base != 200 * log_stride:
        raise ValueError("Independent segment-log boundary evidence changed")
    if mission_starts != [0x10148, 0x10AF8] or mission_sizes != [0x9B0, 0x9B0] or memset_targets != [0x252938, 0x252938]:
        raise ValueError("Nested mission zero-fill destinations changed")
    report = {
        "confidence": "code-backed",
        "warning": "Static exact USA v02.00 engine paths, not an editor restart API. Private captured bytes and current live bytes can differ. No menu-label, safe-edit, allocation-safety or in-game acceptance claim.",
        "private_bank_allocation": {
            "function_va": "0x3cf228", "object_pointer_member": "0x80",
            "arena_va": "0x10690580", "arena_members": {"base": 0, "capacity": 4, "front_used": 8, "back_used": 12, "reverse_byte": 16},
            "size": "0x906f0",
            "rule": "Forward branch rounds used OFFSET up to16 then adds arena base; resulting address alignment additionally depends on base. Reverse branch rounds the absolute candidate address down to16 and updates back-used. Both publish object+80. No zero-fill, null/capacity guard or pointer equality to standard save-manager staging is visible here.",
            "limits": "Allocation helper assumes runtime arena state; bounded preview refuses overlap, wrap and underflow rather than emulating unsafe native accesses."},
        "phase_dispatch": {"function_va": "0x3cf378", "phase_member": "0x60", "entry_latch_member": "0x68",
            "table_va": "0x3cf3dc", "table_encoding": "five signed BE32 relative offsets from table base",
            "cases": [{"phase": i, "target_va": hex(target)} for i, target in enumerate(targets)],
            "rule": "Unsigned phase>4 exits without selecting a case; phase5 is outside this dispatcher, not a confirmed completed-gameplay outcome."},
        "phase_one_capture": {"case_va": "0x3cf5b4", "copy_call_va": "0x3cf600", "continuation_call_va": "0x3cf610",
            "rule": "Consumes entry latch to0. On nonzero entry latch and reaching the resolved-handle path, copies all906F0 current live bytes to object+80 BEFORE helper251188. Later phase1 polls with latch0 skip the copy. Helper low-byte0 leaves phase1; nonzero publishes phase2/entry latch1 via common suffix3CF434.",
            "limits": "Handle resolution dereferences runtime state; no safe handle validity or successful UI/gameplay transition inferred. Capture is not an atomic operation or disk backup."},
        "phase_four_selection": {"case_va": "0x3cf4ec", "selector_va": "0x263db8", "selector_call_va": "0x3cf528",
            "rule": "In the entry-latch-zero suffix, raw low32 selector result0 invokes helper250ED8 then selective restart3CED40; exact result1 invokes helper250ED8 then full private-bank restore3CF1B8. Other results leave phase4. Each selected action returns BEFORE phase5 and entry latch1 are published. No named menu choice is inferred from result numbers.",
            "selective_request": [0, 0, 1], "full_restore_request": [18, 1, 1],
            "limits": "Entry-latch-nonzero menu construction has additional runtime dependencies deliberately not simulated. A callback returning does not establish load acceptance."},
        "retained_private_regions": [{"name": name, "start": hex(start), "end_exclusive": hex(end)} for name, start, end in RETAINED],
        "retention_rule": "At selective restart3CED40's final copy boundary, segment log bytes8764..10144 come from the PRIOR PRIVATE BANK. Nested35D9A0 clears count10144 but not this log buffer. Other explicit selective-copy/reset writes do not overlap it. Prior phase1 capture can supply the log bytes, but no current-live equality, preceding phase1 invocation or globally zero initialization is presumed. Mission groups are NOT retained: nested zero-fill explicitly clears both.",
        "nested_initializer_ownership": {
            "chain": ["0x3ced80", "0x35e110", "0x35e1ac", "0x35d9a0"],
            "inner_save_base": hex(inner_base),
            "mission_zero_fills": [{"start": hex(start), "size": hex(size), "end_exclusive": hex(start + size), "call_va": hex(va)}
                for start, size, va in zip(mission_starts, mission_sizes, (0x35DBBC, 0x35DBD4))],
            "decryptor_reset_words": [{"offset": "0x8758", "bits": "00000000"}, {"offset": "0x875c", "bits": "00000000"}, {"offset": "0x8760", "bits": "3F800000"}],
            "log": {"start": hex(log_base), "end_exclusive": hex(log_end), "stride": hex(log_stride), "physical_slots": 200},
            "rule": "35E110's direct loops omit mission lists, BUT nested35D9A0 makes two9B0-byte zero-fill calls to252938. This clears all mission entry bytes, flags and counts in BOTH groups. Preceding8758/875C/8760 Decryptor words reset0/0/float1.0 and are not log bytes. Inspecting only the35C760 loops misses the later zero-fill."},
        "constructor_scope": {"function_va": "0x35c760", "initialize_arguments_low32": [1, 65535], "teardown_arguments_low32": [0, 65535],
            "rule": "Qualified initialization separately initializes standard manager bank at live+B03F8 (1029FF18) and live bank. Each group's mission loops temporarily leave flags untouched while writing title/descriptionFFFFFFFF and count0, BUT their later35E110→35D9A0 calls zero-fill both entire mission groups. Loop-boundary retention is not final constructor retention. This does not prove the object+80 private arena bank is that standard manager bank. Qualified phase0 performs visible manager-side teardown; other arguments return without these loops."},
        "recommended_annotations": [
            {"va": "0x3cf228", "name": "TOD_restart_private_bank_arena_setup", "kind": "function", "comment": "Publishes object+80 private906F0-byte arena bank; no zero-fill/capacity guard or standard manager staging pointer equality proven."},
            {"va": "0x3cf378", "name": "TOD_restart_phase_dispatch_capture_selection", "kind": "function", "comment": "Phase1 entry copies live to private bank before continuation; phase4 selector0/1 invokes selective/full restore before phase5 publication. Inline case bodies extend beyond old Ghidra recovered body."},
            {"va": "0x3cf3dc", "name": "TOD_restart_phase_relative_cases", "kind": "data", "size": 20, "comment": "Five signedBE32 displacements relative to3CF3DC: phases0..4; unsignedphase>4 exits."}],
        "limitations": ["Original inputs unchanged; native/UI code is never executed.", "Retained bytes are private-bank bytes, not automatically current live save data.", "Private arena pointer, dispatch phase, entry latch and UI result are runtime-only, absent from supplied GAME.SAV.", "No reconstructed UI choice label or editable restart operation."],
        "instruction_guards": [{"va": hex(va), "bytes": data.hex().upper()} for va, data in sorted(guards.items())],
    }
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != SAVE_SIZE:
            raise ValueError("Detached save must contain exactly906F0 bytes")
        data = detached(path.read_bytes())
        if any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
            raise ValueError("Detached save inventory identity does not match verified layout")
        report["save_observation"] = {"sha256": hashlib.sha256(data).hexdigest().upper(),
            "restart_word_raw": data[0x906EC:0x906F0].hex().upper(), "log_count_raw": data[0x10144:0x10148].hex().upper(),
            "mission_counts_raw": [{"world": i, "active": data[0x101C0 + i * 0x7C:0x101C4 + i * 0x7C].hex().upper(),
                "completed": data[0x10B70 + i * 0x7C:0x10B74 + i * 0x7C].hex().upper()} for i in range(20)],
            "scope": "Current saved bits only; no private runtime bank contents, phase1 capture history or UI choice reconstructed."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2))
