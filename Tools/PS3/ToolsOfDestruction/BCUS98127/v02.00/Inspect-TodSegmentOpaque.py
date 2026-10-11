"""Read-only bounded owner audit for unresolved saved segment/world words.

An immediate displacement is not a save offset. This exact-build audit records
three newly reviewed candidate paths and one prior constructor counterexample;
it does not enumerate or prove the absence of other readers/writers.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
SAVE_SIZE = 0x906F0
WORLD_BASE, WORLD_STRIDE, WORLD_COUNT = 0x488, 0x408, 20
SEGMENT_STRIDE, SEGMENT_COUNT = 0x30, 10


def opaque_observation(data):
    """Bounded immutable raw-byte observation; no integer/float/type inference."""
    if not isinstance(data, (bytes, bytearray)) or len(data) != SAVE_SIZE:
        raise ValueError("Expected one detached plaintext save layout")
    if any(struct.unpack_from(">I", data, slot * 20)[0] != slot for slot in range(32)):
        raise ValueError("Plaintext weapon record layout changed")
    worlds = []
    for world in range(WORLD_COUNT):
        start = WORLD_BASE + world * WORLD_STRIDE
        segments = []
        for slot in range(SEGMENT_COUNT):
            record = start + slot * SEGMENT_STRIDE
            segments.append({"slot": slot, "record_offset": hex(record),
                             "word28_hex": data[record + 0x28:record + 0x2C].hex().upper(),
                             "tail2d_2f_hex": data[record + 0x2D:record + 0x30].hex().upper()})
        worlds.append({"world_id": world, "record_offset": hex(start), "segments": segments,
                       "tail404_407_hex": data[start + 0x404:start + 0x408].hex().upper()})
    return {"sha256": hashlib.sha256(data).hexdigest().upper(), "worlds": worlds,
            "nonzero_segment_word28_count": sum(v["word28_hex"] != "00000000" for w in worlds for v in w["segments"]),
            "nonzero_segment_tail_count": sum(v["tail2d_2f_hex"] != "000000" for w in worlds for v in w["segments"]),
            "nonzero_world_tail_count": sum(w["tail404_407_hex"] != "00000000" for w in worlds),
            "qualification": "Raw bits only. Zero values in one snapshot do not prove padding, unused storage, logical type or invariant; nonzero synthetic fixtures are retained without renaming."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    checks = {
        # Prior constructor example: its independently initialized pointer is
        # not the live saved-state root, despite all three matching immediates.
        0x7EE04: 0x8122B2D0, 0x7EED0: 0x90690404,
        0x7EF7C: 0xD02904B0, 0x7F358: 0xD029088C,
        0x88B208: 0x101B9EE8, 0x89F188: 0x101EFB20,
        # Destination from first11F20 return, copied to nonvolatile r30.
        0x921BC: 0x4BF7FD65, 0x921C8: 0x7C7E1B78,
        0x92224: 0x4BF7FCFD, 0x9222C: 0x7BCB0020,
        0x92230: 0x78690020, 0x92238: 0x80E90000,
        0x92248: 0x90EB088C,
        0x9383C: 0x4BF7E6E5, 0x93848: 0x7C7E1B78,
        0x938A4: 0x4BF7E67D, 0x938AC: 0x7BCB0020,
        0x938B0: 0x78690020, 0x938D8: 0x83A90014,
        0x938E8: 0x93AB04B0,
        # Input argument retained in r25; selected path stages three adjacent
        # float fields from that owner into a stack message, not a save getter.
        0x18282C: 0x7C791B78, 0x183414: 0xC0790884,
        0x183424: 0xC0590888, 0x183434: 0xC039088C,
        0x183438: 0xD02100A4, 0x18343C: 0x4BE909A5,
    }
    for va, expected in checks.items():
        if elf.u32(va) != expected:
            raise ValueError(f"Opaque-owner audit instruction/pointer changed at {va:#x}")
    for va in (0x7EDF0, 0x92198, 0x93818, 0x1827D8):
        if elf.descriptors[va] != 0x88FF38:
            raise ValueError("Opaque-owner candidate descriptor TOC changed")
    if 0x88FF38 + BINDINGS["signed"](elf.u32(0x7EE04) & 65535, 16) != 0x88B208:
        raise ValueError("Constructor candidate pointer ownership changed")
    for va in (0x921BC, 0x92224, 0x9383C, 0x938A4):
        if BINDINGS["branch_target"](elf.u32(va), va) != 0x11F20:
            raise ValueError("Candidate argument conversion target changed")
    # Keep selected bounded owner/load/copy spans, not a global census. The
    # exact ELF hash also protects reviewed control flow outside these spans.
    ranges = ((0x92198, 0x92270), (0x93818, 0x93928),
              (0x1827D8, 0x182844), (0x183404, 0x183440))
    guards = {va: elf.read(va, 4) for va in checks}
    for start, end in ranges:
        guards[start] = elf.read(start, end - start)
    report = {
        "confidence": "bounded code-backed ownership audit",
        "warning": "No new saved field semantic, editable field or completion percentage. No native execution. This selected-candidate audit is not a global no-reader/no-writer proof.",
        "storage": {"world_base": hex(WORLD_BASE), "world_stride": hex(WORLD_STRIDE),
                    "physical_world_slots": WORLD_COUNT, "segments_per_world": SEGMENT_COUNT,
                    "segment_stride": hex(SEGMENT_STRIDE),
                    "segment_word28": {"offset": "0x28", "size": 4, "type": "opaque bytes"},
                    "segment_tail": {"offset": "0x2d", "size": 3, "type": "opaque bytes"},
                    "world_tail": {"offset": "0x404", "size": 4, "type": "opaque bytes"}},
        "reviewed_candidates": [
            {"function_va": "0x92198", "access_va": "0x92248", "immediate": "0x88c",
             "copy_source_offset": "0x0", "access_kind": "32-bit raw copy",
             "owner": "First11F20 result from input argument1 retained in r30 and narrowed to r11; source is second11F20 result for argument2 narrowed to r9.",
             "conclusion": "Immediate88C alone does not bind this write to save488+world0+404. Destination comes from argument conversion11F20, not the saved-world address calculation; aliasing through arbitrary callers is not ruled out."},
            {"function_va": "0x93818", "access_va": "0x938e8", "immediate": "0x4b0",
             "copy_source_offset": "0x14", "access_kind": "32-bit raw copy",
             "owner": "First11F20 result from input argument1 retained in r30 and narrowed to r11; word at source+14 loaded into r29 from the second11F20 result for argument2.",
             "conclusion": "This copy cannot assign meaning/type to saved segment28 merely because4B0 equals488+28. No saved-record getter or world/segment indexing is used in this reviewed leaf; arbitrary caller aliasing is not excluded."},
            {"function_va": "0x1827d8", "access_va": "0x183434", "immediate": "0x88c",
             "access_kind": "float load into stack message",
             "owner": "Selected path retains the original input owner in nonvolatile r25; reads adjacent input+884/+888/+88C and stages them at stack+9C/+A0/+A4 before13DE0 with code2F6 and input+68.",
             "conclusion": "The neighboring input+14→+54 traversal is configuration traversal, not the owner of this88C float load. This is an input-owner float field, not evidence that savedworld404 is float; caller aliasing remains outside this audit."},
        ],
        "prior_counterexample": {"function_va": "0x7edf0", "pointer_slot_va": "0x88b208",
            "initialized_pointer_va": "0x101b9ee8", "saved_pointer_slot_va": "0x89f188",
            "initialized_saved_pointer_va": "0x101efb20",
            "rule": "Constructor immediate404/4B0/88C stores use r9 loaded from88B208. Distinct initialized pointer owners, not a new direct saved-field consumer; pointer slots are not treated as immutable runtime alias proofs."},
        "prior_evidence_boundary": "WorldAux already confirms segment28 BE32-zero initialization, segment2D..2F/world404..407 omitted by that initializer, and full906F0 snapshot/initial-restore coverage. These are prior byte-footprint facts, not new semantics or a universal preservation claim.",
        "unresolved": "No new semantic consumer/producer established for segment28 or world404..407. Existing configuration28 float readers have a different owner. Keep opaque bytes and do not expose an inferred edit.",
        "recommended_annotations": [
            {"va": "0x92248", "name": "TOD_argument_owner_88c_copy_not_save_tail", "kind": "comment", "comment": "Argument-converted owner+88C receives source+0 raw bits. Do not equate literal88C with live savedworld0 tail404."},
            {"va": "0x938e8", "name": "TOD_argument_owner_4b0_copy_not_save_segment", "kind": "comment", "comment": "Argument-converted owner+4B0 receives source+14 raw bits. Not a confirmed savedsegment28 semantic/type."},
            {"va": "0x183434", "name": "TOD_input_owner_88c_message_not_save_tail", "kind": "comment", "comment": "Original input owner+88C float copied into stack message with adjacent884/888. Input+14→+54 traversal elsewhere is not this load's owner; no savedworld404 type confirmation."},
        ],
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())],
    }
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != SAVE_SIZE:
            raise ValueError("Expected one detached plaintext save layout")
        report["save_observation"] = opaque_observation(path.read_bytes())
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path, help="Detached plaintext working copy only; never modified")
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
