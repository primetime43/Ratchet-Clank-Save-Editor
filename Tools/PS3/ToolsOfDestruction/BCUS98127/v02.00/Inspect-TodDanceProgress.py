"""Read-only exact-build saved Dance progress bank and five native producers."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
MASK = (1 << 28) - 1


def progress_preview(bank, runtime_index):
    """Reached suffix only; raw index is sampled AFTER earlier runtime callbacks."""
    for value, width in ((bank, 64), (runtime_index, 32)):
        if type(value) is not int or not 0 <= value < 1 << width:
            raise ValueError("Expected bounded unsigned raw bank/index")
    admitted = runtime_index < 0x80000000
    shift = runtime_index & 127
    operand = (1 << shift) if admitted and shift < 64 else 0
    after = bank | operand
    return {"store_reached": admitted, "or_operand": operand, "bank_after_local_store": after,
            "skill48_request": after == MASK,
            "scope": "Reached native suffix only. Negative signed-low32 indices skip the OR/store but still test equality. A request is not a new award; existing skill48 deduplicates separately. No earlier callback, runtime admission, notification or final state simulated."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}
    checks = {
        0x890898: 0x101EFB20, 0x89089C: 0x101F5048,
        0x8914F0: 0x101EFB20, 0x8914F4: 0x101F5048,
        0x891CE0: 0x101EFB20, 0x891CE4: 0x101F5048,
        0x892094: 0x101EFB20, 0x892098: 0x101F5048,
        0x8923D8: 0x101EFB20, 0x8923DC: 0x101F5048,
        0x122E0: 0xF8410028, 0x122E4: 0x3C420001, 0x122E8: 0x3842FFE8,
        0x135498: 0x38000001, 0x1354B4: 0x81230010, 0x1354B8: 0x81690028,
        0x1354BC: 0x2F8B0000, 0x1354C0: 0x7C0A5836, 0x1354C4: 0x419C0054,
        0x1354C8: 0x8162215C, 0x1354CC: 0x3C6B0001,
        0x1354D0: 0xE8A38720, 0x1354D4: 0x7CA45378, 0x1354D8: 0xF8838720,
        0x1354E0: 0x3940FFFF, 0x1354E4: 0x38800030, 0x1354E8: 0x79460120,
        0x1354EC: 0xE8E88720, 0x1354F0: 0x7C273000, 0x1354F4: 0x40820010,
        0x1354F8: 0x80622160, 0x135518: 0x8162215C,
        0x10DBD0: 0x38000001, 0x10DBDC: 0x81690028, 0x10DBE0: 0x2F8B0000,
        0x10DBE4: 0x7C0A5836, 0x10DBE8: 0x419C0050, 0x10DBEC: 0x816215B8,
        0x10DBF4: 0xE8038720, 0x10DBF8: 0x7C0C5378, 0x10DBFC: 0xF9838720,
        0x10DC04: 0x38A0FFFF, 0x10DC08: 0x38800030, 0x10DC0C: 0x78AA0120,
        0x10DC10: 0xE92B8720, 0x10DC14: 0x7C295000, 0x10DC18: 0x40820010,
        0x10DC1C: 0x806215BC, 0x10DC38: 0x816215B8,
        0xDDA64: 0x806B0028, 0xDDA68: 0x2C830000, 0xDDA6C: 0x418401CC,
        0xDDA70: 0x81420960, 0xDDA74: 0x3B400001, 0xDDA7C: 0x7F491836,
        0xDDA80: 0xEBD98720, 0xDDA84: 0x7FDC4B78, 0xDDA88: 0xFB998720,
        0xDDA90: 0x38E0FFFF, 0xDDA94: 0x78FF0120, 0xDDA98: 0xE8DD8720,
        0xDDA9C: 0x7F26F800, 0xDDAA0: 0x409A0014, 0xDDAA4: 0x80620964,
        0xDDAA8: 0x38800030, 0xDDC38: 0x81420960,
        0x126A84: 0x807D0028, 0x126A88: 0x2C030000, 0x126A8C: 0x418001CC,
        0x126A90: 0x81421DA8, 0x126A94: 0x39600001, 0x126A9C: 0x7D681836,
        0x126AA0: 0xE8F98720, 0x126AA4: 0x7CE34378, 0x126AA8: 0xF8798720,
        0x126AB0: 0x38A0FFFF, 0x126AB4: 0x78AA0120, 0x126AB8: 0xE9848720,
        0x126ABC: 0x7CAC5000, 0x126AC0: 0x40860014, 0x126AC4: 0x80621DAC,
        0x126AC8: 0x38800030, 0x126C58: 0x81421DA8,
        0x13FD20: 0x807D0028, 0x13FD24: 0x2C830000, 0x13FD28: 0x41840320,
        0x13FD2C: 0x814224A0, 0x13FD30: 0x3B600001, 0x13FD38: 0x7F6C1836,
        0x13FD3C: 0xE9198720, 0x13FD40: 0x7D036378, 0x13FD44: 0xF8798720,
        0x13FD4C: 0x3880FFFF, 0x13FD50: 0x788A0120, 0x13FD54: 0xE92B8720,
        0x13FD58: 0x7FA95000, 0x13FD5C: 0x409E0014, 0x13FD60: 0x806224A4,
        0x13FD64: 0x38800030, 0x140048: 0x814224A0,
        0x8998C0: 0x42400000, 0x89D6C0: 0x1001F240, 0x2A14C0: 0x8082D7A0,
        0x2A14C4: 0xC02299A0,
        0x10026954: 40, 0x10026958: 1293, 0x1002695C: 1364, 0x10026960: 19,
        0x35E198: 0x381E5528, 0x35D9BC: 0x7C7F1B78,
        0x35DB7C: 0x3BA00000, 0x35DB9C: 0xFBBF31F8,
    }
    for va, expected in checks.items():
        if elf.u32(va) != expected:
            raise ValueError(f"Dance progress evidence changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    name = elf.string(0x1001F240)
    if name != "SKILLPOINT_DANCE":
        raise ValueError("Dance skill name changed")
    guards[0x1001F240] = elf.read(0x1001F240, len(name) + 1)
    for va, target, linked in ((0x122EC, 0x35D5D0, False),
                              (0x1354FC, 0x122E0, True), (0x10DC20, 0x122E0, True),
                              (0xDDAAC, 0x122E0, True), (0x126ACC, 0x122E0, True),
                              (0x13FD68, 0x122E0, True), (0x35E1AC, 0x35D9A0, True),
                              (0x2A14C8, 0x252EB8, True),
                              (0x13551C, 0x1354DC, False), (0x10DC3C, 0x10DC00, False),
                              (0xDDC3C, 0xDDA8C, False), (0x126C5C, 0x126AAC, False),
                              (0x14004C, 0x13FD48, False)):
        raw = elf.u32(va)
        if BINDINGS["branch_target"](raw, va) != target or bool(raw & 1) != linked:
            raise ValueError("Dance progress branch linkage changed")
        guards[va] = elf.read(va, 4)
    producers = (0xDD858, 0x10DBA0, 0x1268A0, 0x135468, 0x13F9A0)
    for function in (*producers, 0x35D5D0, 0x35D9A0, 0x35E110):
        expected_toc = 0x88FF38 if function in producers else 0x89FF20
        if elf.descriptors[function] != expected_toc:
            raise ValueError("Dance progress descriptor TOC changed")
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    guards[0x122E0] = elf.read(0x122E0, 16)
    report = {
        "confidence": "exact-build-native-flow",
        "warning": "USA BCUS98127 v02.00 only. Read-only static evidence, no native execution or gameplay-tested edits. This producer-only report does not assign target names or runtime index origins; the separate dance_targets report supplies qualified actor/config associations. Localized skill text and current eligibility remain unresolved.",
        "bank": {"offset": "0x8720", "type": "u64 BE", "display_name": "Dance skill progress bank",
                 "completion_pattern": "0x000000000FFFFFFF",
                 "rule": "Five selected native suffixes sample runtime source+28 after following context+10. Signed-low32 negative skips OR/store but still tests the existing bank. Nonnegative performs saved8720 |= PPC sld(1,index): count uses low7 bits, counts64..127 yield0,128 aliases0. No explicit upper range clamp exists in these suffixes. Reread all64 saved bits and compare EXACTLY to low28 all-ones; extra bits28..63 prevent the request, even if every low28 bit is set. Not popcount>=28 or a masked equality."},
        "award": {"id": 48, "enum": name, "points": 40, "name_tag": 1293, "description_tag": 1364,
                  "earned_bits_offset": "0x8710", "earned_mask": "0x0001000000000000",
                  "linkage": "Each reached equality branch passes101F5048 (=canonical save101EFB20+5528) and ID30hex to122E0. Thunk saves r2, changes TOC88FF38 to89FF20 (+10000-18), and tail-branches35D5D0, the verified skill setter. Named export and definition independently identify decimal48 SKILLPOINT_DANCE,40 points. It is not trophy ID48 or a second earned-skill bank.",
                  "retention": "No new-bit requirement or one-shot request latch exists between these OR stores and calls: duplicates and negative/zero-shift indices can request on an already-exact bank. Skill setter deduplicates existing bit48 independently and returns before score/notification updates. Bank8720 is not earned bit48; a zero bank can coexist with a retained award. No score, notification or actual target history inferred."},
        "producers": [{"function_va": hex(a), "toc": "0x88ff38"} for a in producers],
        "initialization": "35E110 passes base+5528 to35D9A0; zero r29 stored by std+31F8 at35DB9C resolves saved8720..8727. Separate saved8710/8718 stores do not merge their meanings. Initialization does not prove every load clears progress or that zero means never danced.",
        "identity_limits": "The low28 pattern alone proves the selected completion test, not names for28 enemies or allocation of index0..27. Separate dance_targets evidence now links selected actor assignments to internal configurations; not localized labels or exhaustive variants. Runtime source+28 is not a raw save index field, saved object UID or world slot. Earlier callbacks and gates of the five bodies are not replayed. No success histories, current eligibility, total gameplay coverage or edits certified.",
        "recommended_annotations": [
            {"va": hex(a), "kind": "comment", "name": f"TOD_dance_progress_bank_store_{a:x}",
             "comment": "Saved BE64 bank8720 OR-publishes sld(1,runtime source+28) after signed nonnegative gate; index has no upper clamp. Re-read exact000000000FFFFFFF requests named SKILLPOINT_DANCE(48) via122E0->35D5D0. Extra high bits block request; target identities/runtime gates unresolved."}
            for a in (0xDDA88, 0x10DBFC, 0x126AA8, 0x1354D8, 0x13FD44)
        ] + [{"va": "0x1354f0", "kind": "comment", "name": "TOD_dance_progress_exact_completion",
              "comment": "All64 saved8720 bits compared EXACTLY to000000000FFFFFFF, not masked/popcount. Signed negative index skips store but reaches this comparison; duplicates may request48 again. Setter deduplicates independently via earned8710 bit48; no history/playback proof."}],
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())],
    }
    if save_path is not None:
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not verified plaintext save layout")
        bank = struct.unpack_from(">Q", raw, 0x8720)[0]
        earned = struct.unpack_from(">Q", raw, 0x8710)[0]
        report["save_observation"] = {
            "plaintext_sha256": hashlib.sha256(raw).hexdigest().upper(), "bank_hex": f"{bank:016X}",
            "low28_set_indices": [i for i in range(28) if bank & (1 << i)],
            "high_bits_hex": f"{bank & ~MASK:016X}", "exact_completion_pattern": bank == MASK,
            "skill48_earned": bool(earned & (1 << 48)),
            "qualification": "Independent raw snapshots, not target names, lifetime progress or proof of current runtime award eligibility."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
