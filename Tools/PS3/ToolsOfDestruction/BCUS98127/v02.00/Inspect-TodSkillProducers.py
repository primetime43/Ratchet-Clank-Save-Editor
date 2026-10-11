"""Exact-build skill definition filtering and additional native producer gates.

Read-only static evidence and bounded immutable supplied-state previews only.
Runtime object fields are not inferred from GAME.SAV, and callbacks are not run.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

PROGRESSION = runpy.run_path(str(Path(__file__).with_name("Inspect-TodProgression.py")))
BINDINGS = PROGRESSION["BINDINGS"]


def uint(value, bits=32):
    if type(value) is not int or not 0 <= value < 1 << bits:
        raise ValueError(f"Expected raw unsigned{bits} integer")
    return value


def filter_preview(groups, group, ordinal, saved_bits):
    """Exactly60 raw definition group words; ordinal is one-based, not skill ID."""
    if not isinstance(groups, (list, tuple)) or len(groups) != 60:
        raise ValueError("Expected exactly60 definition group words")
    for word in groups:
        uint(word)
    uint(group); uint(ordinal); uint(saved_bits, 64)
    matching = [i for i, word in enumerate(groups) if word == group]
    selected = matching[ordinal - 1] if 1 <= ordinal <= len(matching) else None
    return {"matching_ids": matching, "matching_count": len(matching), "selected_id": selected,
            "native_completion_result": int(selected is not None and bool(saved_bits & 1 << selected)),
            "qualification": "Selected global ID follows ascending0..59 order. A zero result can mean no matching ordinal or an unset saved bit; the group is not an award prerequisite."}


def ratio_gate_preview(numerator, denominator):
    """Finite supplied u32 nearest-even float32 sample, not a native callback.

    This helper assumes IEEE nearest-even rounding; current native FPSCR mode
    is not reconstructed. No claim about in-game eligibility is made.
    """
    uint(numerator); uint(denominator)
    if denominator == 0:
        return {"denominator_nonzero": False, "ratio_f32_hex": None, "ordered_at_least_0_75": False}
    f32 = lambda value: struct.unpack(">f", struct.pack(">f", value))[0]
    converted_numerator, converted_denominator = f32(numerator), f32(denominator)
    quotient = f32(converted_numerator / converted_denominator)
    return {"denominator_nonzero": True,
            "numerator_f32_hex": struct.pack(">f", converted_numerator).hex().upper(),
            "denominator_f32_hex": struct.pack(">f", converted_denominator).hex().upper(),
            "ratio_f32_hex": struct.pack(">f", quotient).hex().upper(),
            "ordered_at_least_0_75": quotient >= 0.75}


def iris_gate_preview(gate_byte, level_id, entries):
    """Bounded supplied pool-summary snapshot; not runtime reconstruction.

    Entry tuples are (occupied, is_input_entry, has_config, tag695_result_byte,
    config_word2c). No native helper, mutation or pool enumeration is executed.
    """
    uint(gate_byte, 8); uint(level_id)
    if not isinstance(entries, (list, tuple)) or len(entries) > 65536:
        raise ValueError("Expected at most65536 supplied entry summaries")
    blockers = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, (list, tuple)) or len(entry) != 5:
            raise ValueError("Expected five-member entry summary")
        occupied, is_input, has_config, tag_byte, word2c = entry
        if any(type(v) is not bool for v in (occupied, is_input, has_config)):
            raise ValueError("Entry ownership facts must be explicit booleans")
        uint(tag_byte, 8); uint(word2c)
        if occupied and not is_input and has_config and tag_byte != 0 and word2c == 0:
            blockers.append(index)
    return {"blocking_indices": blockers, "sampled_gate_matches": gate_byte != 0 and level_id == 11 and not blockers,
            "qualification": "Supplied immutable snapshot only. Empty summaries satisfy the no-blocker comparison, not proof that all physical enemies were handled. Runtime tag-helper effects and native callbacks are not simulated."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}
    def keep(va, size):
        guards[va] = elf.read(va, size)
    checks = {
        0x8A198C: 0x10026654, 0x35EB18: 0x54652036,
        0x35EB1C: 0x80021A6C, 0x35EB28: 0x8063000C,
        0x27288: 0x836286EC, 0x888624: 0x101EFB20,
        0x272C0: 0x3BBD0001, 0x272C4: 0x7C1DE000,
        0x272F0: 0xE8850010,
        0x89F188: 0x101EFB20, 0x2D1490: 0x8062F268,
        0x2D1494: 0x3D230009, 0x2D1498: 0x806906E8,
        0x89F94C: 0x10063028, 0x89F954: 0x1064FC80,
        0x89F958: 0x101F5048, 0x8A1AC0: 0x101F5048,
        0x8A1AF0: 0x3F400000,
        0x2EBBD4: 0x93BB002C, 0x2EBBD8: 0x8BDF0000,
        0x2EBC10: 0x2F03000B, 0x2EBC1C: 0x811D0010,
        0x2EBC24: 0x419C0058, 0x2EBC40: 0xA0EB0050,
        0x2EBC80: 0x38800018, 0x2EBCA0: 0x7C0A3000,
        0x2EBCA4: 0x41820040, 0x2EBCBC: 0x38800695,
        0x2EBCC8: 0x5466063E, 0x2EBCD8: 0x8009002C,
        0x2EBCE0: 0x419EFF04,
        0x363F20: 0x9123014C, 0x363F38: 0x2C030004,
        0x363F40: 0x2F830008, 0x363F48: 0x801F0114,
        0x363F54: 0x88BF00F9, 0x363F60: 0x8B3F00FA,
        0x363FC0: 0xFD606818, 0x363FC4: 0xFD400018,
        0x363FC8: 0xED2A5824, 0x363FCC: 0xFC894000,
        0x363FD0: 0x4CC53382,
        0x364188: 0x807F0100, 0x364198: 0x2B1E0009,
        0x3641DC: 0x801F010C, 0x3641E8: 0x895F00F8,
        0x3641F4: 0x817F0138, 0x3641F8: 0x2B8B012C,
        0x364258: 0xFD803018, 0x36425C: 0xFC602018,
        0x364260: 0xEC436024, 0x364264: 0xFC826800,
        0x364268: 0x4CC53382,
        0x364170: 0x4E800421, 0x364194: 0x83DF0104,
        0x364224: 0x8B3F00FA,
    }
    for va, expected in checks.items():
        if elf.u32(va) != expected:
            raise ValueError(f"Skill filter/producer instruction changed at {va:#x}")
        keep(va, 4)
    for function in (0x35EB18, 0x255B8, 0x25638, 0x256F8, 0x257B8, 0x27268,
                     0x2EB9B8, 0x363EE8, 0x2D1490):
        keep(function, elf.functions[elf.functions.index(function) + 1] - function)
    calls = {0x1112C: 0x35EB18, 0x1378C: 0x35EB00, 0x1054C: 0x35ECD8,
             0x11F6C: 0x35EB70, 0x255E4: 0x11120, 0x25670: 0x11120,
             0x25730: 0x11120, 0x257F0: 0x11120, 0x272AC: 0x11120,
             0x256C8: 0x13780, 0x25788: 0x10540, 0x25848: 0x11F60,
             0x2EBC08: 0x2D1490, 0x2EBCC0: 0x24F208, 0x2EBC84: 0x35D5D0,
             0x363F30: 0x2D1490, 0x364178: 0x2D1490}
    award_calls = {35: (0x3642E8, 0x3642EC), 36: (0x3641A4, 0x3641A8),
                   38: (0x364274, 0x364278), 39: (0x364288, 0x36428C),
                   40: (0x364204, 0x364208), 41: (0x363FDC, 0x363FE0),
                   42: (0x364218, 0x36421C), 43: (0x363FF0, 0x363FF4)}
    for identifier, (load, call) in award_calls.items():
        if elf.u32(load) != 0x38800000 | identifier:
            raise ValueError("Skill award ID argument changed")
        keep(load, 4)
        calls[call] = 0x35D5D0
    for va, target in calls.items():
        if BINDINGS.branch_target(elf.u32(va), va) != target:
            raise ValueError(f"Skill producer/filter target changed at {va:#x}")
        keep(va, 4)
    for va in (0x11120, 0x13780, 0x10540, 0x11F60):
        keep(va, 16)
    table = elf.u32(0x8A198C)
    keep(table, 60 * 16)
    exports = PROGRESSION["exports"](elf, 0x294E90, "SKILLPOINT_", 0x252EB8)
    if [v["id"] for v in exports] != list(range(61)) or exports[-1]["enum"] != "SKILLPOINT_COUNT":
        raise ValueError("Skill export catalog changed")
    catalog = []
    for item in exports[:-1]:
        raw = elf.read(table + item["id"] * 16, 16)
        points, name, description, group = struct.unpack(">4I", raw)
        catalog.append({"id": item["id"], "enum": item["enum"], "points": points,
                        "definition_va": hex(table + item["id"] * 16),
                        "filter_group_word": group, "name_tag": name, "description_tag": description})
    named_ids = [24] + list(award_calls)
    for identifier in named_ids:
        item = exports[identifier]
        for key in ("name_slot_va", "name_load_va", "value_slot_va", "value_load_va", "value_move_va", "export_call_va"):
            keep(int(item[key], 0), 4)
        keep(int(item["name_va"], 0), len(item["enum"]) + 1)
    report = {
        "confidence": "code-backed definition filter and nine additional named producer requests",
        "warning": "Exact USA v02.00 static paths only. Runtime predicates/callbacks are not reconstructed from saved bits; no native or Lua execution, edits, event-history names or safe-edit contract.",
        "storage": {"bits_offset": "0x8710", "score_offset": "0x8708", "normal_ids": [0, 59],
                    "retained_unknown_bits": [60, 63]},
        "level_selector_source": {"getter_va": "0x2d1490", "saved_offset": "0x906e8",
            "saved_root_pointer_slot_va": "0x89f188", "saved_root_va": "0x101efb20",
            "qualification": "Native currentlevel shorthand below denotes the saved906E8 destination/level selector read by2D1490, not proof of the currently loaded runtime world. It can differ from loaded assets during selection/loading; numeric branches are qualified by this source."},
        "definition_filter": {"table_va": hex(table), "stride": 16, "group_member": "0xc",
            "physical_type": "u32 BE", "confirmed_role": "equality filter/group selector",
            "getter_va": "0x35eb18", "thunk_va": "0x11120", "count_va": "0x255b8",
            "points_nth_va": "0x25638", "description_nth_va": "0x256f8", "name_nth_va": "0x257b8",
            "completion_nth_va": "0x27268",
            "rule": "Count and nth consumers scan all60 definitions in ascending globalID. The nth argument is one-based within the equal-group matches, not a global skillID; ordinal0/out-of-range gives a fallback.27268 then tests the selectedglobalID in saved8710 and returns0 for either no match or an unset bit.",
            "fallbacks": "25638 returns0 points when no match;256F8/257B8 return their existing fallback text pointer, not a saved title. Each nth getter calls the appropriate points/description/name thunk after selecting the globalID.",
            "group19": "Definitions44..59 all have group19 (16 entries). Numeric19 also equals the separately known LEVEL_COUNT sentinel; it is not proof of a twentieth native world or an award prerequisite. Actual equality filtering is confirmed; arbitrary caller labeling/world ownership is not.",
            "scope": "Definition metadata, not an additional save field. Legacy unknown_definition_0c keys can remain for compatibility, qualified by this confirmed narrow role.",
            "catalog": catalog},
        "iris_wrench_producer": {"function_va": "0x2eb9b8", "skill_id": 24, "enum": catalog[24]["enum"],
            "runtime_gate_pointer_slot_va": "0x89f94c", "runtime_gate_byte_va": "0x10063028",
            "pool_pointer_slot_va": "0x89f954", "pool_root_va": "0x1064fc80",
            "saved_award_argument_slot_va": "0x89f958", "saved_substructure_va": "0x101f5048",
            "level_source": "2D1490 reads saved906E8 selector after preceding calls/effects; selector11 is not independently confirmed as the loaded runtime world.",
            "rule": "After preceding effects and input+2C=1, requires nonzero runtime gate byte and currentlevel11. Iterates occupied180-byte runtimepool entries through root highwater+10, excluding input+14. Another nonnull config+40 with nonzero low-byte24F208(tag695) result AND config+2C==0 aborts the producer. Otherwise requests skill24 through35D5D0.",
            "boundary": "A negative highwater or no qualifying other entry permits the request. This is not evidence that all physical enemies were destroyed or that input/config2C is savedworld/segment completion. Pool classes/handles and tag-helper side effects are runtime; the global gate name and config2C gameplay meaning are unresolved. A request can be deduplicated by the already-mapped award setter."},
        "space_context_producer": {"function_va": "0x363ee8", "runtime_owner": "incoming object, not savedroot",
            "level_source": "Both branches call2D1490 for saved906E8 destination/level selector, not an independently observed loaded world. Nonzero+FC reaches the selector read after formatting/notification callbacks; zero+FC has an earlier read without that work.",
            "prelude": "Stores1 at input+14C and a native float at+150. Nonzero input+FC reaches formatting/notification callbacks before currentlevel is reread; zero+FC skips that work. These are runtime owner fields, not inferred save offsets.",
            "ratio_threshold_va": "0x8a1af0", "ratio_threshold_bits": "3F400000", "ratio_threshold": 0.75,
            "ratio_rule": "Requires denominator unsignedword nonzero; each u32 is converted tofloat32 before fdivs rounds the ratio tofloat32. fcmpu plusGT|EQ admits ordered ratio>=0.75. Exact rational percentage shortcuts can differ at float32 rounding boundaries. Python samples assume nearest-even rounding; current native FPSCR mode is not reconstructed.",
            "predicates": [
                {"skill_id": 35, "enum": catalog[35]["enum"], "call_va": "0x3642ec", "level_branch": "currentlevel4", "condition": "runtime word+100==0"},
                {"skill_id": 36, "enum": catalog[36]["enum"], "call_va": "0x3641a8", "level_branch": "currentlevel4", "condition": "runtime unsignedword+104>9"},
                {"skill_id": 38, "enum": catalog[38]["enum"], "call_va": "0x364278", "level_branch": "currentlevel8", "condition": "runtime unsignedword+10C nonzero and float32(+110)/float32(+10C)>=0.75"},
                {"skill_id": 39, "enum": catalog[39]["enum"], "call_va": "0x36428c", "level_branch": "currentlevel8", "condition": "runtime byte+F8==0"},
                {"skill_id": 40, "enum": catalog[40]["enum"], "call_va": "0x364208", "level_branch": "currentlevel8", "condition": "runtime unsignedword+138<=300; no time unit established"},
                {"skill_id": 41, "enum": catalog[41]["enum"], "call_va": "0x363fe0", "level_branch": "else:currentlevel neither4 nor8", "condition": "runtime unsignedword+114 nonzero and float32(+118)/float32(+114)>=0.75"},
                {"skill_id": 42, "enum": catalog[42]["enum"], "call_va": "0x36421c", "level_branch": "else:currentlevel neither4 nor8", "condition": "runtime byte+F9==0"},
                {"skill_id": 43, "enum": catalog[43]["enum"], "call_va": "0x363ff4", "level_branch": "else:currentlevel neither4 nor8", "condition": "runtime byte+FA==0"}],
            "scope": "The SC3 enums are not proof this guarded function restricts the else branch tolevel13; it does not. Prior callbacks and earlier award notifications may change later runtime fields. Predicate rows are encountered native call sites, not simultaneous snapshot guarantees, savedhistory, actor identities or player-facing condition descriptions."},
        "callback_order": [
            "Nonzero input+FC path:2511B8 formatting at364128, virtual notification at364170, then2D1490 saved selector reread364178. Zero+FC instead calls2D1490 at363F30.",
            "Selector4:word100 is read at364188; a requested skill35 at3642EC returns to364194, which freshly reads word104 before testing skill36. Notifications can alter that later value.",
            "Selector8:skill38 request364278 returns to3641E8, freshly reading byteF8 for skill39; skill39 request36428C returns to3641F4, freshly reading word138 for skill40.",
            "Else:skill41 request363FE0 returns to363F54, freshly reading byteF9 for skill42. After skill42 request36421C, byteFA is freshly read364224 for skill43; the no42 path instead readsFA at363F60.",
            "Each award request invokes the existing35D5D0 setter, whose runtime notifications may be reentrant. No simultaneous eligibility list or callback-free post-state is inferred."],
        "recommended_annotations": [
            {"va": "0x35eb18", "name": "TOD_skill_definition_filter_group_word", "kind": "function", "comment": "Returns definition[id*10+0C]. Five equality-filter consumers scan IDs0..59; nth selection is one-based within the group. Metadata selector, not saved field or confirmed award prerequisite."},
            {"va": "0x27268", "name": "TOD_skill_filter_group_nth_saved_bit", "kind": "function", "comment": "Equality-filters definition0C, selects one-based nth matching globalID in ascending0..59 order, then tests saved8710 bit. No match and unset bit both return0."},
            {"va": "0x2eb9b8", "name": "TOD_iris_wrench_runtime_other_entry_scan_award_request", "kind": "function", "comment": "Runtime gate10063028 and saved906E8 selector11 via2D1490 required after prior effects, not loadedworldproof. Occupiedpool scan excludes inputentry; another config/tag695 and config2C==0 aborts. Otherwise requests skill24. Not all-physical-enemies or serialized2C proof."},
            {"va": "0x363ee8", "name": "TOD_space_context_numeric_skill_award_requests", "kind": "function", "comment": "Runtime owner gates for IDs35/36 atsaved906E8 selector4,38/39/40 at8,41/42/43 in else(neither4nor8), not loadedworldproof. Float32 ratio>=.75 and rawfield predicates only; rereadsaftercallbacks matter. No timeunits, SC3 level13 restriction, savedruntime fields or callback-free guarantee."}],
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())],
    }
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Expected detached plaintext save size")
        raw = path.read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Expected plaintext inventory IDs0..31")
        bits = struct.unpack_from(">Q", raw, 0x8710)[0]
        groups = sorted({v["filter_group_word"] for v in catalog})
        report["save_observation"] = {"sha256": hashlib.sha256(raw).hexdigest().upper(),
            "bits_hex": f"{bits:016X}", "score_raw": struct.unpack_from(">I", raw, 0x8708)[0],
            "saved_level_selector_raw": struct.unpack_from(">I", raw, 0x906E8)[0],
            "unknown_bits60_63_hex": f"{bits & (0xF << 60):016X}",
            "named_producer_bits": [{"id": i, "enum": catalog[i]["enum"], "set": bool(bits & 1 << i)} for i in named_ids],
            "groups": [{"group_word": g, "matching_ids": [v["id"] for v in catalog if v["filter_group_word"] == g],
                        "completed_ids": [v["id"] for v in catalog if v["filter_group_word"] == g and bits & 1 << v["id"]]} for g in groups],
            "qualification": "Stored bits only. A set bit does not establish which producer fired, its runtime prerequisites, currentlevel, input fields or reconstructed event history."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path, help="Detached plaintext copy only; never modified")
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
