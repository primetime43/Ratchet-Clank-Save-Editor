"""Read-only saved option lifecycle: entry latch and qualified camera exit cleanup.

Numeric runtime modes are not option names. The bounded Python preview selects
records only; native callbacks, game input and save-edit acceptance are not run.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BASE = Path(__file__).resolve().parent
BINDINGS = runpy.run_path(str(BASE / "Inspect-TodWeaponBindings.py"))
TAIL = runpy.run_path(str(BASE / "Inspect-TodFinalTail.py"))


def latched_cleanup_mode(runtime_byte):
    """Exit consumes the entry-derived byte, not a fresh saved-word read."""
    if type(runtime_byte) is not int or not 0 <= runtime_byte <= 255:
        raise ValueError("Runtime latch must be an unsigned byte")
    return 0x0F if runtime_byte else 0x10


def cleanup_selection(mode, selector, pending_mode, pending_selector, records):
    """Bounded pre-callback selection model, not execution or post-state prediction.

    Each of the exactly16 pairs is (record+64 mode, record+6C selector).
    Callback mutation can change future records during native execution, so
    these indices describe an immutable supplied snapshot only.
    """
    if len(records) != 16 or any(not isinstance(pair, (tuple, list)) or len(pair) != 2 for pair in records):
        raise ValueError("Expected exactly16 runtime record mode/selector pairs")
    values = [mode, selector, pending_mode, pending_selector] + [v for pair in records for v in pair]
    if any(type(v) is not int or not 0 <= v <= 0xFFFFFFFF for v in values):
        raise ValueError("Camera mode/selector values must be unsigned32")
    return {"pending_mode_clear": pending_mode == mode and (selector == 0 or pending_selector == selector),
            "matching_indices": [i for i, (record_mode, record_selector) in enumerate(records)
                                 if record_mode == mode and (selector == 0 or record_selector == selector)],
            "warning": "Pre-callback snapshot selection only. No native code executes, no records are mutated, and callback effects can change later runtime matches or final state."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}
    expected = {
        0x89679C: 0x101EFB20, 0x896858: 0x101EFB20,
        0x20F3FC: 0x83A26864, 0x20F400: 0x38000000,
        0x20F408: 0x3D7D0001, 0x20F414: 0x98030024,
        0x20F420: 0x812B14C0, 0x20F424: 0x2F890000, 0x20F428: 0x409E000C,
        0x20F430: 0x987F0024, 0x2108E0: 0x80826920, 0x2108E4: 0x38000000,
        0x2108F0: 0x3D240001, 0x210900: 0x981F003F,
        0x210904: 0x816914C0, 0x210910: 0x2F8B0000, 0x210918: 0x409E000C,
        0x210920: 0x98DF003F,
        0x20F218: 0x81630014, 0x20F224: 0x800314C0, 0x20F228: 0x2F8005C9,
        0x20F22C: 0x419E0104, 0x20F240: 0x83BC2114, 0x20F274: 0x80BD0064,
        0x20F27C: 0x41820114, 0x20F280: 0x887F0024, 0x20F288: 0x419A00D8,
        0x20F290: 0x3880000F, 0x20F2A0: 0x419E0018, 0x20F2AC: 0x38A00000,
        0x20F338: 0x99691DF1, 0x20F364: 0x38800010, 0x20F374: 0x4182FF44,
        0x20F380: 0x38A00000, 0x20F394: 0x38A0000F, 0x20F3B0: 0x41860018,
        0x20F3C0: 0x4BFFFEF8, 0x20F3D0: 0x38A00010, 0x20F3E4: 0x419AFE9C,
        0x2112F8: 0x81630014, 0x211304: 0x800314C0, 0x211308: 0x2F800063,
        0x21130C: 0x419E0104, 0x211320: 0x83BC2114, 0x211354: 0x80BD0064,
        0x21135C: 0x41820114, 0x211360: 0x887F003F, 0x211368: 0x419A00D8,
        0x211370: 0x3880000F, 0x211380: 0x419E0018, 0x21138C: 0x38A00000,
        0x211418: 0x99691DF1, 0x211444: 0x38800010, 0x211454: 0x4182FF44,
        0x211460: 0x38A00000, 0x211474: 0x38A0000F, 0x211490: 0x41860018,
        0x2114A0: 0x4BFFFEF8, 0x2114B0: 0x38A00010, 0x2114C4: 0x419AFE9C,
        0x10390: 0xF8410028, 0x10394: 0x3C420002, 0x10398: 0x3842FF24,
        0x1039C: 0x4862A3AC,
        0x63A78C: 0x800320C0, 0x63A790: 0x7F802000, 0x63A794: 0x419E0104,
        0x63A7A0: 0x2E190000, 0x63A7A4: 0x3B800000, 0x63A7AC: 0x3AE00001,
        0x63A7B0: 0x3BDA00C0, 0x63A7B8: 0x2C1C000F, 0x63A7C8: 0x3BDE0200,
        0x63A7CC: 0x80FF0064, 0x63A7D0: 0x7F07D800, 0x63A7E0: 0x41920010,
        0x63A7E4: 0x811F006C, 0x63A7F4: 0x92FF0064, 0x63A7F8: 0x80A70014,
        0x63A80C: 0x4E800421, 0x63A814: 0x80DA2128, 0x63A820: 0x83BF0068,
        0x63A824: 0x80BF006C, 0x63A828: 0x38800001, 0x63A830: 0x816C0008,
        0x63A844: 0x4E800421, 0x63A854: 0x93BF0068, 0x63A858: 0x4082FF6C,
        0x63A898: 0x2C050000, 0x63A89C: 0x40820010, 0x63A8A0: 0x3880FFFF,
        0x63A8A4: 0x909A20C0, 0x63A8AC: 0x806320C4, 0x63A8B0: 0x7C832800,
        0x35EE48: 0x39200001, 0x35EE74: 0x91230018,
    }
    for address, value in expected.items():
        if elf.u32(address) != value:
            raise ValueError(f"Option exit/producer evidence changed at {address:#x}")
        guards[address] = elf.read(address, 4)
    calls = {0x20F294: 0x683F0, 0x20F368: 0x683F0, 0x211374: 0x683F0,
             0x211448: 0x683F0, 0x20F2B0: 0x10390, 0x20F384: 0x10390,
             0x211390: 0x10390, 0x211464: 0x10390, 0x20F3A0: 0x11060,
             0x20F3D4: 0x11060, 0x20F3B8: 0x12770, 0x211480: 0x11060,
             0x2114B4: 0x11060, 0x211498: 0x12770}
    for address, target in calls.items():
        word = elf.u32(address)
        if not word & 1 or BINDINGS["branch_target"](word, address) != target:
            raise ValueError("Option exit call target changed")
        guards[address] = elf.read(address, 4)
    if BINDINGS["branch_target"](elf.u32(0x1039C), 0x1039C) != 0x63A748:
        raise ValueError("Camera cleanup thunk target changed")
    for address in (0x20F1F8, 0x2112D8, 0x63A748, 0x35EE40):
        end = elf.functions[elf.functions.index(address) + 1]
        guards[address] = elf.read(address, end - address)
    for descriptor, code, toc in ((0x8674B0, 0x20F1F8, 0x88FF38),
                                  (0x867540, 0x2112D8, 0x88FF38),
                                  (0x87C3C8, 0x63A748, 0x8AFE5C)):
        if struct.unpack(">II", elf.read(descriptor, 8)) != (code, toc):
            raise ValueError("Option exit/cleanup function descriptor changed")
        guards[descriptor] = elf.read(descriptor, 8)
    paths = []
    for table, entry, update, exit_va, flag, exclusion in (
            (0x84AF18, 0x20F3F0, 0x20F598, 0x20F1F8, 0x24, 0x5C9),
            (0x84AF48, 0x2108D8, 0x210B80, 0x2112D8, 0x3F, 0x63)):
        for displacement, target in ((12, entry), (16, update), (32, exit_va)):
            descriptor = elf.u32(table + displacement)
            if struct.unpack(">II", elf.read(descriptor, 8)) != (target, 0x88FF38):
                raise ValueError("Entry/update/exit method-table linkage changed")
            guards[descriptor] = elf.read(descriptor, 8)
        guards[table] = elf.read(table, 0x24)
        paths.append({"method_table_va": hex(table), "entry_va": hex(entry),
                      "update_va": hex(update), "exit_va": hex(exit_va),
                      "exit_table_offset": "0x20", "runtime_latch_member": hex(flag),
                      "runtime_actor_state_exclusion": hex(exclusion)})
    report = {
        "confidence": "code-backed entry-latched exit cleanup; option producer/name remains unresolved",
        "warning": "Exact USA v02.00 static evidence and detached observations, not native execution, safe edit permission, a current camera verdict or another build's offsets.",
        "field": {"save_offset": "0x114c0", "physical_type": "u32 BE", "semantic_name": None,
                  "entry_basis": "Entry reads the entire saved word once: zero produces runtime latch1, nonzero latch0. The exit methods consume that runtime byte; they do not reread the saved word in their guarded bodies.",
                  "producer_boundary": "Known leaf default35EE40 stores1 at settings member18. No additional direct setter, named script binding or original player-facing option label was confirmed in this bounded follow-up; this is not an exhaustive absence proof."},
        "exit_paths": paths,
        "exit_rule": {"nonzero_runtime_latch_mode": "0x0f", "zero_runtime_latch_mode": "0x10",
                      "lookup_va": "0x683f0", "cleanup_thunk_va": "0x10390", "cleanup_native_va": "0x63a748",
                      "selector_argument": 0,
                      "qualification": "Runtime actor-state exclusion bypasses this camera branch. Otherwise, nested container+2114 subsystem+64 nonzero reaches latch selection; if zero, either mode0F/10 check through11060 returning a nonzero low byte calls12770 and bypasses latch cleanup. Only when both fail does that path reach latch selection. A null683F0 lookup skips63A748. These callbacks and runtime state are not saved option meanings.",
                      "separate_runtime_offset": "The preliminary incoming-object+14 actor+14C0 comparisons are runtime actor state, not saved-root+114C0 despite the same low displacement.",
                      "scope": "No direct saved114C0/tail store or latch-byte store occurs in the guarded exit bodies. Called callbacks are not exhaustively proven free of save side effects; changing a save after entry does not itself demonstrate changing the runtime latch."},
        "cleanup": {"va": "0x63a748", "record_start_member": "0xc0", "record_stride": "0x200", "record_count": 16,
                    "mode_member": "0x64", "selector_member": "0x6c", "preserved_member": "0x68",
                    "pending_mode_member": "0x20c0", "pending_selector_member": "0x20c4",
                    "pending_rule": "If pending20C0 matches requested mode, and selector argument iszero or pending20C4 matches it, writesFFFFFFFF to20C0. It does not clear20C4 in this body.",
                    "matching_rule": "Scans all16 records, matching record+64 and optional record+6C selector. Selector0 is a wildcard. Unlike683F0's first-match lookup, this cleanup loop continues across matching records, subject to callback mutations.",
                    "callback_sequence": "For each encountered match, stores1 to record+64 before invoking record virtual slot14 with(record,container). Then snapshots record+68, calls container+2128 mode-table entry requested_mode*12+8 with(record,1,record+6C), and restores that snapshot to+68. Snapshot occurs after the first callback, not before it.",
                    "post_state_boundary": "Mode1 is a pre-callback store, not a guarantee of final mode1 or camera inactivity. The callbacks may mutate records, container and future match candidates. No save field is directly addressed by this cleanup body; callback side effects and runtime acceptance remain unproved."},
        "opaque_tail": {"save_offsets": ["0x114d6", "0x114d7"], "semantic_names": [None, None],
                        "leaf_unwritten_members": TAIL["settings_footprint"](elf)["unwritten_members"],
                        "scope": "Existing leaf initializer coverage still excludes these bytes. This follow-up found no qualified name/producer for them and does not establish padding, unused storage or defaultzero."},
        "limitations": ["Saved114C0 has no confirmed original name or input activation/release proof for hold/toggle.",
                        "The bounded root-affine lead scan and selected same-displacement readers do not exclude computed, indirect, dynamically registered or later producers.",
                        "Neither runtime camera mode nor its callbacks is a newly editable saved field.",
                        "Opaque114D6/114D7 values remain arbitrary raw bytes; snapshot zeros would not prove a role."],
        "recommended_annotations": [
            {"va": "0x20f1f8", "kind": "function", "name": "TOD_first_person_exit_latched24_cleanup_verified",
             "comment": "Methodtable84AF18+20. Uses runtime entry latch24 to choose0F/nonzero or10/zero; conditional683F0 lookup then10390→63A748(selector0). Actorstate5C9 and nested2114 subsystem checks can bypass; not savedwordsetter or hold/toggle proof."},
            {"va": "0x2112d8", "kind": "function", "name": "TOD_first_person_exit_latched3f_cleanup_verified",
             "comment": "Methodtable84AF48+20. Uses entry latch3F, conditional mode0F/10 cleanup via10390→63A748(selector0). Actorstate63 and nestedsubsystem checks can bypass. No original optionname or savedtail identity."},
            {"va": "0x63a748", "kind": "function", "name": "TOD_camera_matching_records_cleanup_verified",
             "comment": "Clears matching pending20C0 toFFFFFFFF; scans16 C0+200stride records bymode64 and optionalselector6C(0wildcard). Storesmode1 before virtual14 callback; snapshots68 afterfirstcallback, invokesmode-table callback2128+mode*12+8, restores68. Callback-qualified, not finalstate or savewrite guarantee."}],
        "instruction_guards": [{"va": hex(a), "bytes": raw.hex().upper()} for a, raw in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save size")
        data = path.read_bytes()
        if any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        word = struct.unpack_from(">I", data, 0x114C0)[0]
        latch = int(word == 0)
        report["save_observation"] = {"sha256": hashlib.sha256(data).hexdigest().upper(),
            "word_raw_hex": data[0x114C0:0x114C4].hex().upper(), "word": word,
            "hypothetical_entry_latch": latch, "qualified_exit_mode_if_latch_unchanged": hex(latched_cleanup_mode(latch)),
            "opaque_tail_raw_hex": data[0x114D6:0x114D8].hex().upper(),
            "warning": "Current saved bits only, not the actual runtime latch, guaranteed exit cleanup or final camera state. Raw unknown bytes are not normalized."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path)
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2, allow_nan=False))
