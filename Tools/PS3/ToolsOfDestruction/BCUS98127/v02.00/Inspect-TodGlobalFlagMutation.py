"""Exact-build global event latches and bounded shipped literal flag callsites.

No game/Lua execution, source writes, flag repair or fabricated enum aliases.
Adjacent bytecode operands prove static callsites, not that a script ran.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import runpy
import struct
from types import SimpleNamespace

FLAGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodGlobalFlags.py")))
BINDINGS = FLAGS["BINDINGS"]
LUA = SimpleNamespace(**runpy.run_path(str(BINDINGS.ROOT / "Tools/Inspect-Lua50.py")))
PSARC = SimpleNamespace(**runpy.run_path(str(BINDINGS.ROOT / "Tools/Inspect-Psarc.py")))
BASE, WORD_BYTES, NAMED_COUNT = 0x5528, 40, 292
APIS = ("check_flag", "set_flag", "clear_flag")
ASSET_SET_SHA256 = "3A6A543ABFF18EDDF8174E95F4F61B96295E1AF693FAED254A9FDED56B5EBE05"
SELECTED = {
    "/built/game/scripts/globalhelp.lc": (3221, "C48BD0DA9F5012D387E5F932A2E44374C5DD79ECDB11F5704D8CD2D8CD94A49F"),
    "/built/levels/meridian city/scripts/c2_use_aphelion.lc": (367, "2ED16C0C7F68D287F618D524AB8B44A7C5427414463C00F466C677E4F849E26F"),
    "/built/levels/metropolis/scripts/help.lc": (3864, "966A189BFEA02F79784F3748DD203C9FBF408A281C66A9BA80DFCBD9763FEE1E"),
    "/built/levels/stratus city/scripts/help.lc": (3155, "01E2457803D3F08FFB36B0056E5D32078975C935AB9DE1A7146115A98513A285"),
    "/built/levels/apogee space station/scripts/help.lc": (4596, "CC169C3B763838E78A710718F48C4059CB19C070CE3B5CAB770CFFF5652631CD"),
}
SELECTED_FLAGS = {"HERO_FIRED_WEAPON": 3, "HERO_USED_QUICK_SELECT": 7,
    "HERO_USED_APHELION": 12, "HERO_HIT_SHIELD": 13,
    "HERO_HIT_ELECTRIC_IMMUNE": 15, "HERO_USED_VISICOPTER": 16,
    "HERO_USED_MAP": 17, "LVL_MERIDIAN_ROBOWING_DONE": 219}


def flag_preview(value, identifier, operation):
    """Immutable physical storage preview restricted to named IDs, not edit advice."""
    if not isinstance(value, (bytes, bytearray)) or len(value) != WORD_BYTES:
        raise ValueError("Expected detached five BE64 global-flag words")
    if type(identifier) is not int or not 0 <= identifier < NAMED_COUNT:
        raise ValueError("Expected named flag ID0..291, not COUNT292 or unknown tail bits")
    if operation not in APIS:
        raise ValueError("Expected check_flag, set_flag or clear_flag")
    result = bytearray(value)
    offset, mask = identifier // 64 * 8, 1 << (identifier % 64)
    word = struct.unpack_from(">Q", result, offset)[0]
    was_set = bool(word & mask)
    if operation != "check_flag":
        struct.pack_into(">Q", result, offset, word | mask if operation == "set_flag" else word & ~mask)
    return {"bytes": bytes(result), "was_set": was_set,
            "set_after": bool(struct.unpack_from(">Q", result, offset)[0] & mask)}


def prototypes(root):
    yield root
    for child in root["children"]:
        yield from prototypes(child)


def literal_calls(raw):
    """Strict adjacent GETGLOBAL/API, GETGLOBAL/enum, CALL only; no VM/dataflow."""
    reader = LUA.Reader(raw, 0)
    root = reader.function()
    if reader.pos != len(raw):
        raise ValueError("Trailing bytes after compiled Lua chunk")
    calls = []
    for node in prototypes(root):
        instructions = node["instructions"]
        for pc in range(len(instructions) - 2):
            q = instructions[pc:pc + 3]
            if [x["op"] for x in q] != ["GETGLOBAL", "GETGLOBAL", "CALL"] or \
                    q[0].get("constant") not in APIS or not isinstance(q[1].get("constant"), str) or \
                    q[1]["a"] != q[0]["a"] + 1 or q[2]["a"] != q[0]["a"] or q[2]["b"] != 2:
                continue
            expected_results = 2 if q[0]["constant"] == "check_flag" else 1
            if q[2]["c"] != expected_results:
                continue
            calls.append({"prototype_path": node["path"], "pc": pc, "call_pc": pc + 2,
                          "api": q[0]["constant"], "argument_enum": q[1]["constant"],
                          "offset": q[0]["offset"], "bytes": raw[int(q[0]["offset"], 0):int(q[0]["offset"], 0) + 12].hex().upper()})
    return root, calls


def inspect_selected(payloads):
    if set(payloads) != set(SELECTED):
        raise ValueError("Expected all five exact selected compiled assets")
    roots, guards = {}, []
    for name, (size, digest) in SELECTED.items():
        raw = payloads[name]
        if len(raw) != size or hashlib.sha256(raw).hexdigest().upper() != digest:
            raise ValueError("Selected flag consumer asset fingerprint mismatch")
        roots[name] = literal_calls(raw)[0]

    def instruction(name, pc, op, **fields):
        q = roots[name]["instructions"][pc]
        if q["op"] != op or any(q.get(k) != v for k, v in fields.items()):
            raise ValueError("Selected reached-block instruction changed")

    def call(name, pc, api, argument):
        _, sites = literal_calls(payloads[name])
        if not any(q["prototype_path"] == "root" and q["pc"] == pc and q["api"] == api and
                   q["argument_enum"] == argument for q in sites):
            raise ValueError("Selected literal flag call changed")

    def guard(name, first, end, meaning):
        offset = int(roots[name]["code_offset"], 0) + first * 4
        guards.append({"archive_entry": name, "prototype_path": "root", "first_pc": first,
            "end_pc_exclusive": end, "offset": hex(offset),
            "bytes": payloads[name][offset:offset + (end - first) * 4].hex().upper(), "meaning": meaning})

    global_name, meridian, metro, stratus, apogee = SELECTED
    call(global_name, 134, "check_flag", "HERO_HIT_ELECTRIC_IMMUNE")
    instruction(global_name, 137, "TEST", a=2, b=2, c=0)
    instruction(global_name, 138, "JMP", jump_pc=150)
    instruction(global_name, 139, "GETGLOBAL", constant="help")
    instruction(global_name, 146, "CALL", a=2, b=6, c=1)
    call(global_name, 147, "clear_flag", "HERO_HIT_ELECTRIC_IMMUNE")
    guard(global_name, 134, 150, "Flag15 true reached-block calls help then clears flag15; false branch skips to150.")
    call(global_name, 150, "check_flag", "HERO_USED_VISICOPTER")
    instruction(global_name, 153, "TEST", a=2, b=2, c=0)
    instruction(global_name, 154, "JMP", jump_pc=191)
    instruction(global_name, 155, "GETGLOBAL", constant="is_six_axis_active")
    instruction(global_name, 156, "CALL", a=2, b=1, c=2)
    instruction(global_name, 157, "LOADBOOL", a=3, b=1, c=0)
    instruction(global_name, 158, "EQ", a=0, b=2, c=3)
    instruction(global_name, 159, "JMP", jump_pc=176)
    for help_pc, clear_pc in ((163, 172), (179, 188)):
        instruction(global_name, help_pc, "GETGLOBAL", constant="helptext")
        call(global_name, clear_pc, "clear_flag", "HERO_USED_VISICOPTER")
    guard(global_name, 150, 191, "Flag16 true has two input-mode helptext branches, each followed by a clear. Wait literals do not reconstruct runtime timing.")
    call(stratus, 192, "check_flag", "HERO_HIT_SHIELD")
    instruction(stratus, 195, "TEST", a=0, b=0, c=0)
    instruction(stratus, 196, "JMP", jump_pc=216)
    instruction(stratus, 197, "GETGLOBAL", constant="hero_shield_hits")
    instruction(stratus, 198, "ADD", a=0, b=0, c_constant=1.0)
    instruction(stratus, 199, "SETGLOBAL", constant="hero_shield_hits")
    call(stratus, 200, "clear_flag", "HERO_HIT_SHIELD")
    guard(stratus, 192, 203, "Flag13 true increments the script global hero_shield_hits then clears flag13; this global is not proven serialized.")
    for pc, enum in ((38, "HERO_FIRED_WEAPON"), (41, "HERO_USED_QUICK_SELECT")):
        call(metro, pc, "clear_flag", enum)
    instruction(metro, 31, "GETGLOBAL", a=9, constant="is_in_volume")
    instruction(metro, 32, "GETGLOBAL", a=10, constant="Ratchet1")
    instruction(metro, 33, "GETGLOBAL", a=11, constant="Help_Shoot_Reset_Trigger")
    instruction(metro, 34, "CALL", a=9, b=3, c=2)
    instruction(metro, 35, "TEST", a=9, b=9, c=0)
    instruction(metro, 36, "JMP", jump_pc=44)
    guard(metro, 31, 44, "Reached volume-trigger body clears fired-weapon flag3 before quick-select flag7; not lifetime achievement bits.")
    call(apogee, 26, "clear_flag", "HERO_USED_MAP")
    guard(apogee, 26, 29, "Script has an entry clear of map-use event17, not proof that savedclear means the map was never opened.")
    instruction(meridian, 0, "LOADBOOL", a=0, b=0, c=0)
    call(meridian, 1, "clear_flag", "HERO_USED_APHELION")
    call(meridian, 5, "check_flag", "HERO_USED_APHELION")
    call(meridian, 10, "check_flag", "LVL_MERIDIAN_ROBOWING_DONE")
    instruction(meridian, 8, "TEST", a=1, b=1, c=0)
    instruction(meridian, 9, "JMP", jump_pc=26)
    instruction(meridian, 13, "TEST", a=1, b=1, c=0)
    instruction(meridian, 14, "JMP", jump_pc=26)
    instruction(meridian, 15, "LOADBOOL", a=1, b=0, c=0)
    instruction(meridian, 16, "EQ", a=0, b=0, c=1)
    instruction(meridian, 17, "JMP", jump_pc=26)
    instruction(meridian, 18, "LOADBOOL", a=0, b=1, c=0)
    call(meridian, 19, "clear_flag", "HERO_USED_APHELION")
    instruction(meridian, 22, "GETGLOBAL", constant="complete_mission")
    instruction(meridian, 23, "GETGLOBAL", constant="LEVEL_MERIDIAN_CITY")
    instruction(meridian, 24, "GETGLOBAL", constant="L18_LABEL_MISSION_RETURNTOAPHELION")
    instruction(meridian, 25, "CALL", a=1, b=3, c=1)
    guard(meridian, 0, 26, "Entry clears event12. The reached completion block requires checks12 and219 true plus local first-run guard, clears12 then calls complete_mission; separate state actions.")
    return {"assets": [{"archive_entry": name, "size": size, "sha256": digest} for name, (size, digest) in SELECTED.items()],
        "consumable_event_ids": [3, 7, 12, 13, 15, 16, 17], "asset_byte_guards": guards,
        "meaning": "These named bits have explicit script clear sites. A clear saved event is not evidence the corresponding action never happened. A set bit alone is not proof its help/mission consumer ran or is active.",
        "shield_counter": "hero_shield_hits is a Lua global incremented in the reached flag13 block; no serialized save location is established for that variable.",
        "mission_order": "Meridian reached block clears HERO_USED_APHELION before complete_mission(LEVEL_MERIDIAN_CITY,L18_LABEL_MISSION_RETURNTOAPHELION). Calls are separate, not a proven atomic save transaction.",
        "scope": "Guarded static reached-block relationships only. No script execution, call acceptance, complete control-flow reconstruction, help display timing or gameplay-safe flag edits."}


def inspect_assets(archive_path, catalog):
    archive = PSARC.Psarc(archive_path)
    candidates = [(i, name) for i, name in enumerate(archive.names) if name and name.endswith(".lc")]
    if len(archive.entries) > 4096 or len(candidates) != 524 or len({n for _, n in candidates}) != len(candidates):
        raise ValueError("Expected unique exact reference compiled-script set")
    if sum(archive.entries[i].length for i, _ in candidates) > 8 * 1024 * 1024:
        raise ValueError("Compiled-script aggregate exceeds bounded survey size")
    counts, examples, unresolved, fingerprints, payloads = {}, {}, [], [], {}
    candidate_count, calls_count = 0, 0
    for index, name in candidates:
        raw = archive.read_entry(index, 1024 * 1024)
        if name in SELECTED:
            payloads[name] = raw
        if not any(api.encode("ascii") in raw for api in APIS):
            continue
        candidate_count += 1
        _, calls = literal_calls(raw)
        if not calls:
            continue
        fingerprints.append({"name": name, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest().upper()})
        calls_count += len(calls)
        for call in calls:
            enum = call["argument_enum"]
            location = {"archive_entry": name, **call}
            if enum not in catalog:
                unresolved.append(location)
                continue
            counts.setdefault(enum, Counter())[call["api"]] += 1
            samples = examples.setdefault(enum, [])
            if len(samples) < 3:
                samples.append(location)
    fingerprints.sort(key=lambda row: row["name"])
    fingerprint = hashlib.sha256(json.dumps(fingerprints, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest().upper()
    if fingerprint != ASSET_SET_SHA256 or candidate_count != 181 or calls_count != 880 or len(counts) != 214:
        raise ValueError("Exact compiled global-flag callsite survey changed")
    return {"confidence": "asset-backed static literal operands; not execution or complete semantics",
        "survey": {"compiled_entries_scanned": len(candidates), "api_string_candidates": candidate_count,
                   "assets_with_strict_literal_calls": len(fingerprints), "literal_calls": calls_count,
                   "operand_names": len(counts) + len({q["argument_enum"] for q in unresolved}),
                   "native_mapped_operand_names": len(counts), "asset_metadata_sha256": fingerprint},
        "catalog": [{"enum": enum, "id": catalog[enum],
                     "word_offset": hex(BASE + catalog[enum] // 64 * 8), "word_bit": catalog[enum] % 64,
                     "call_counts": dict(sorted(counts[enum].items())), "example_sites": examples[enum]}
                    for enum in sorted(counts, key=lambda value: catalog[value])],
        "unresolved_operands": unresolved,
        "selected_consumers": inspect_selected(payloads),
        "warning": "880 strict adjacent named-global callsites are a syntactic subset. Variable arguments, alias calls and nonadjacent dataflow are not resolved. GETGLOBAL operands bind native exports statically but runtime globals may be reassigned. Missing-export LVL_IFF_RETURN_CHALLENGE_7_DONE is retained without ID, alias or fabricated save offset. Samples are bounded to three sites per mapped enum, not every callsite or a complete producer/consumer graph."}


def inspect(elf_path, save_path=None, archive_path=None):
    elf = BINDINGS.Elf(elf_path)
    reference = FLAGS["inspect"](elf_path)
    catalog = {q["enum"]: q["id"] for q in reference["catalog"]}
    if any(catalog.get(enum) != identifier for enum, identifier in SELECTED_FLAGS.items()):
        raise ValueError("Selected event enum registrations changed")
    # Full original native/enum guards establish flag name/ID provenance. New
    # leaf guards independently verify both clear implementations, not atomics.
    guards = {int(g["va"], 0): bytes.fromhex(g["bytes"]) for g in reference["instruction_guards"]}
    for va, words in ((0x27988, [0x546AE8F8, 0x80C286EC, 0x546306BE, 0x390A5520,
            0x38E00001, 0x7D0507B4, 0x7CE41836, 0x7D253214, 0xE8090008, 0x7C0B2078, 0xF9690008, 0x4E800020]),
            (0x27BAE0, [0x546AE8F8, 0x80C29030, 0x546306BE, 0x390A5520,
            0x38E00001, 0x7D0507B4, 0x7CE41836, 0x7D253214, 0xE8090008, 0x7C0B2078, 0xF9690008, 0x4E800020])):
        raw = struct.pack(">12I", *words)
        if elf.read(va, len(raw)) != raw:
            raise ValueError("Exact clear-flag leaf changed")
        guards[va] = raw
    report = {"confidence": "code-backed, with optional exact shipped bytecode evidence",
        "storage": {"base": hex(BASE), "bytes": WORD_BYTES, "named_flags": NAMED_COUNT,
                    "physical_bits": 320, "unknown_tail_ids": {"first": 292, "last": 319}},
        "selected_flags": [{"enum": name, "id": identifier, "word_offset": hex(BASE + identifier // 64 * 8),
                            "word_bit": identifier % 64} for name, identifier in SELECTED_FLAGS.items()],
        "native_mutation": {"set_vas": ["0x24a80", "0x27bb10"], "clear_vas": ["0x27988", "0x27bae0"],
            "rule": "Set loads one BE64 word, ORs one selected bit, and stores. Clear loads one BE64 word, AND-NOTs one selected bit, and stores. Other bits in that word are preserved at these native boundaries. No inventory, mission or tutorial-history action is called by these leaf bodies.",
            "atomicity": "Ordinary ld/std read-modify-write leaves, not reservation/conditional-store atomic operations. Callback acceptance, concurrency exclusion and whole save transaction atomicity are not established.",
            "bounds": "Native leaves do not check GLOBAL_FLAG_COUNT. Safe detached previews accept named IDs0..291 only; COUNT292 is a sentinel and physical bits292..319 remain unknown/preserved."},
        "recommended_annotations": [],
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())],
        "warning": "Event state is not a monotonic achievement or story completion verdict. Exact-bit storage and static script references do not authorize editable fields, reconstruct current script context or establish in-game acceptance."}
    if archive_path is not None:
        report["asset_observation"] = inspect_assets(archive_path, catalog)
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Expected exact verified plaintext save size")
        raw = path.read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Expected verified plaintext inventory IDs0..31")
        words = struct.unpack_from(">5Q", raw, BASE)
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(raw).hexdigest().upper(),
            "raw_words": [f"{word:016X}" for word in words],
            "selected_events": [{**row, "set": bool(words[row["id"] // 64] & 1 << row["word_bit"])} for row in report["selected_flags"]],
            "set_unknown_tail_ids": [i for i in range(292, 320) if words[i // 64] & 1 << (i % 64)],
            "warning": "One supplied snapshot of raw event bits, not evidence a script consumed them or that an action never occurred. Neither hero_shield_hits nor script local first-run guards are reconstructed."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save, args.archive), indent=2))
