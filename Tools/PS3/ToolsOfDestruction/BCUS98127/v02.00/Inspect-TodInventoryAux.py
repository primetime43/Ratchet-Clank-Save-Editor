"""Read-only quick-select and object-counter restore/restart/award lifecycle evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("progression", Path(__file__).with_name("Inspect-TodProgression.py"))
PROGRESSION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROGRESSION)


def signed32(bits):
    return PROGRESSION.BINDINGS.signed(bits, 32)


def quick_select_preview(words, item_id, slot=-1, definition_flags=0):
    """Detached model on normal validated item IDs; never edits a save or invokes native code."""
    if len(words) != 32 or any(not isinstance(v, int) or isinstance(v, bool) or not -0x80000000 <= v <= 0x7FFFFFFF for v in words):
        raise ValueError("Expected32 signed slot words")
    if not isinstance(item_id, int) or isinstance(item_id, bool) or not 0 <= item_id < 32:
        raise ValueError("Preview requires a normal validated item ID")
    if not isinstance(slot, int) or isinstance(slot, bool) or not -0x80000000 <= slot <= 0x7FFFFFFF:
        raise ValueError("Expected signed slot argument")
    if not isinstance(definition_flags, int) or isinstance(definition_flags, bool) or not 0 <= definition_flags <= 0xFFFFFFFF:
        raise ValueError("Expected unsigned definition flags")
    result = list(words)
    if definition_flags & 0x1040:
        return {"operation": "definition-filtered", "words": result, "selected_slot": None, "removed_slots": []}
    if slot > 23:
        slot = -1
    if slot < 0:
        if item_id in result:
            return {"operation": "already-present", "words": result, "selected_slot": None, "removed_slots": []}
        slot = next((i for i in range(24) if result[i] == -1), None)
        if slot is None:
            return {"operation": "first24-full", "words": result, "selected_slot": None, "removed_slots": []}
    removed = [i for i, value in enumerate(result) if value == item_id]
    for i in removed:
        result[i] = -1
    displaced = result[slot]
    result[slot] = item_id
    return {"operation": "inserted", "words": result, "selected_slot": slot, "removed_slots": removed, "displaced_item": displaced}


def souls_condition_preview(current_bits, additions_bits):
    """Only the two saved comparisons, not the guarded runtime award or skill setter."""
    if any(not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 0xFFFFFFFF for v in (current_bits, additions_bits)):
        raise ValueError("Expected unsigned raw32-bit counter words")
    return signed32(additions_bits) > 25 and current_bits == 0


def inspect(elf_path, save_path=None):
    elf = PROGRESSION.BINDINGS.Elf(elf_path)
    guards = {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    def function(address):
        end = elf.functions[elf.functions.index(address)+1]
        keep(address, end-address)

    for address, expected in {
            0x897B38: 0x101EFB20, 0x89550C: 0x101EFB20,
            0x35DD14: 0x91050284, 0x35DD1C: 0x38E00017,
            0x35DD3C: 0x900803BC, 0x35DD40: 0x90080304, 0x35DD44: 0x90080360,
            0x3CEDBC: 0x38A00484, 0x3CEDD0: 0x4BE83659,
            0x3CEE2C: 0x3BBE0284, 0x3CEE4C: 0x2F1F001F,
            0x3CEE5C: 0x933C0000, 0x3CEEC8: 0x3BE00016,
            0x3CEECC: 0x39000001, 0x3CEEE8: 0x38800BFF,
            0x3CEEEC: 0x2B88000B, 0x3CEF24: 0x90C90004,
            0x3CEF2C: 0x7CDE392E, 0x3CEF38: 0x90D9000C,
            0x1E6034: 0x38800010, 0x1E6038: 0x480578E9,
            0x1E6040: 0x2F830019, 0x1E6044: 0x409D001C,
            0x1E6050: 0x48057891, 0x1E6058: 0x2C030000,
            0x1E605C: 0x41820308, 0x1E6368: 0x38800034,
            0x1E636C: 0x4BE2BF75, 0x122EC: 0x4834B2E4,
            0x1E2788: 0x4BFFFB21, 0x1E27A0: 0x93DF0004,
            0x1E27E0: 0x4BFFFB19, 0x1E27F0: 0x39400018,
            0x1E27F4: 0x397A0284, 0x1E2818: 0x4200FFE8,
            0x1E2874: 0x9B9F8738}.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Inventory lifecycle evidence changed at {address:#x}")
        keep(address, 4)
    for address in (0x35DC80, 0x3CED40, 0x3CEC98, 0x1E22A8, 0x1E22F8,
                    0x1E26F0, 0x23D8E0, 0x23D920, 0x23D970):
        function(address)
    keep(0x1E36FC, 0x80)
    keep(0x1E6030, 0x30)
    keep(0x1E6364, 0x14)
    keep(0x122E0, 0x10)
    # Current/peak/additions offsets are independently established by existing
    # named APIs; this pass adds the selected lifecycle consumers, not new arrays.
    objects = PROGRESSION.exports(elf, 0x28440, "OBJ_", 0x12990)
    if [x["id"] for x in objects] != list(range(24)) or objects[-1]["enum"] != "OBJ_TYPE_COUNT":
        raise ValueError("Native object enum changed")
    skills = PROGRESSION.exports(elf, 0x294E90, "SKILLPOINT_", 0x252EB8)
    skill = next(s for s in skills if s["id"] == 52)
    if skill["enum"] != "SKILLPOINT_SOULS":
        raise ValueError("Native Souls award ID changed")
    for item in objects[:-1]+[skill]:
        for key in ("name_slot_va", "name_load_va", "value_slot_va", "value_load_va", "value_move_va", "export_call_va"):
            keep(int(item[key], 0), 4)
        keep(int(item["name_va"], 0), len(item["enum"])+1)
    assignments = []
    for call in (0x1E370C, 0x1E3724, 0x1E3738, 0x1E374C, 0x1E3760, 0x1E3774):
        if PROGRESSION.BINDINGS.branch_target(elf.u32(call), call) != 0x23D970:
            raise ValueError("Hero restore setter changed")
        instructions = list(elf.instructions(call-16, call))
        ids = [w&0xFFFF for _, w in instructions if w&0xFFFF0000 == 0x38800000]
        values = [w&0xFFFF for _, w in instructions if w&0xFFFF0000 == 0x38A00000]
        if len(ids) != 1 or values != [1]:
            raise ValueError("Hero restore object assignment changed")
        assignments.append({"id": ids[0], "value": 1, "call_va": hex(call)})
    reset_mask = elf.u32(0x3CEEE8)&0xFFFF
    preserved = [i for i in range(23) if i == 0 or i <= 11 and reset_mask&(1<<i)]
    cleared = [i for i in range(23) if i not in preserved]
    expected_preserved = list(range(10))+[11]
    if preserved != expected_preserved or [a["id"] for a in assignments] != [0, 1, 2, 3, 4, 9]:
        raise ValueError("Native lifecycle catalog changed")
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA v02.00 static lifecycle plus detached snapshot observations. Existing quick-select/object array roles are not new discoveries; this pass confirms selected restore/restart/award relationships. No source-save edits, reset invocation, award simulation or safe edit ranges.",
        "storage": {"quick_select_offset": "0x284", "quick_select_words": 32, "empty_word": -1,
                    "current_offset": "0x304", "peak_offset": "0x360", "positive_additions_offset": "0x3bc",
                    "object_count": 23, "word_stride": 4, "hero_saved_pointer_member": "0x1a68"},
        "quick_select_mutation": {"add_va": "0x1e26f0", "membership_va": "0x1e22f8", "remove_va": "0x1e22a8",
                                  "rule": "Automatic insertion returns unchanged if the item appears anywhere among all32 words, including slots24..31; otherwise it selects the first -1 only in slots0..23. A full first24 causes no slot store, even if slots24..31 are empty. Explicit normal slot0..23 removes ALL occurrences of the same item across32 words, then overwrites that slot; it can displace a different item without compacting it elsewhere. Explicit slot>23 becomes automatic insertion.",
                                  "eligibility": "Definition lookup must succeed and definition+18 flags&1040 must be zero. This routine does not separately test saved inventory ownership. Item ID checks and definition lookup restrict the native path; the detached preview intentionally accepts only normal validated IDs0..31, never guesses negative-ID behavior.",
                                  "full_list_side_effect": "The no-slot branch may emit message126 and set saved warning latch8738 depending on8734; this does not rescue an insertion. Native UI wheel ordering and every runtime consumer remain unverified.",
                                  "preview_scope": "quick_select_preview is a pure synthetic normal-domain model; no original file is modified and no in-game selection usability is asserted."},
        "restart_lifecycle": {"va": "0x3ced40", "staging_pointer_member": "0x80", "first_copy_size": "0x484", "first_copy_call_va": "0x3cedd0",
                              "ordering": "35E110 initializes staging;3CEDD0 copies current player's first484 bytes, including quick-select and allthree object arrays; then selected inventory/quick-select entries and selected object counters are cleared. This order proves preserved words come from the copied state, not fresh zeros.",
                              "quick_select": {"scan_words": 32, "loop_va": "0x3cee38", "predicate_va": "0x3cec98", "reset_item_ids": [24, 26, 27, 28, 29, 30, 31],
                                               "rule": "Every physical slot whose stored item ID satisfies the selective predicate becomes-1, including slots24..31; retained entries keep their original slots. No compaction or reconstruction is performed by this loop."},
                              "object_arrays": {"loop_ids": "1..22 inclusive", "preserve_mask": hex(reset_mask), "preserved_ids": preserved, "cleared_ids": cleared,
                                                "rule": "Object0 is outside the clearing loop and remains copied. IDs1..11 survive when maskBFF contains their bit; allother loop IDs have current, peak and positive-additions words cleared together. These totals are therefore not unconditional lifetime counts."},
                              "catalog": [{"id": x["id"], "enum": x["enum"], "reset_action": "preserved" if x["id"] in preserved else "clear allthree words"} for x in objects[:-1]],
                              "scope": "Only this guarded selective restart path; no claim of every game mode, cross-build behavior or console acceptance."},
        "hero_restore_assignments": {"va": "0x1e33c8", "setter_va": "0x23d970", "assignments": assignments,
                                     "rule": "Reached restore initialization calls set_num_objects(ID,1) for0,1,2,3,4,9. The setter writes current1, raises peak only under unsigned comparison and leaves positive additions unchanged. Thus1/1/0 can be synthesized by restoration, not evidence of a pickup or runtime ownership event.",
                                     "scope": "Restore routine has earlier runtime gates; this describes the reached assignment block, not an unconditional reset for every loaded save."},
        "souls_award_consumer": {"consumer_va": "0x1e5c28", "object_id": 16, "object_enum": "OBJ_SOULS", "current_offset": "0x344", "positive_additions_offset": "0x3fc",
                                "additions_getter_va": "0x23d920", "additions_call_va": "0x1e6038", "signed_comparison_va": "0x1e6040",
                                "current_call_va": "0x1e6050", "award_call_va": "0x1e636c", "award_thunk_va": "0x122e0", "award_setter_va": "0x35d5d0",
                                "skill_id": 52, "skill_enum": skill["enum"], "skill_enum_evidence": skill,
                                "skill_bits_offset": "0x8710", "skill_bit_index": 52,
                                "condition": "signed32(saved additions[OBJ_SOULS])>25 and saved current[OBJ_SOULS]==0 within a guarded hero-update path. Raw additions remain32-bit storage, but this particular consumer uses cmpwi, not an unsigned threshold; high-bit values do not satisfy it merely because their unsigned value is large.",
                                "scope": "Skill bits are independently retained progression state. Counters alone do not prove an award will execute, remove a previously earned skill or define unique-pickup totals."},
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save size")
        data = path.read_bytes()
        if any(struct.unpack_from(">I", data, i*0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        words = list(struct.unpack_from(">32i", data, 0x284))
        rows = [{"id": x["id"], "enum": x["enum"], "current": struct.unpack_from(">i", data, 0x304+x["id"]*4)[0],
                 "peak": struct.unpack_from(">I", data, 0x360+x["id"]*4)[0],
                 "positive_additions_raw": struct.unpack_from(">I", data, 0x3BC+x["id"]*4)[0]} for x in objects[:-1]]
        current_bits, additions_bits = struct.unpack_from(">I", data, 0x344)[0], struct.unpack_from(">I", data, 0x3FC)[0]
        report["save_observation"] = {"sha256": hashlib.sha256(data).hexdigest().upper(), "size": len(data), "quick_select": words,
                                      "object_counters": rows, "souls": {"current_raw_hex": data[0x344:0x348].hex().upper(),
                                                                            "additions_raw_hex": data[0x3FC:0x400].hex().upper(),
                                                                            "signed_additions": signed32(additions_bits),
                                                                            "saved_comparisons_satisfied": souls_condition_preview(current_bits, additions_bits),
                                                                            "skill52_already_set": bool(struct.unpack_from(">Q", data, 0x8710)[0]&(1<<52))},
                                      "scope": "Observations are not a reset or award preview: separate retained skill bits can remain set even when reset counters no longer satisfy the award's two saved comparisons."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
