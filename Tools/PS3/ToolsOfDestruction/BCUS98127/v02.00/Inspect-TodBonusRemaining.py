"""Exact-build read-only bonus menu consumers and runtime language provenance."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("bonus_remaining_base", Path(__file__).with_name("Inspect-TodBonusEffects.py"))
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)
BINDINGS = BASE.BINDINGS
SPEC = importlib.util.spec_from_file_location("bonus_remaining_asset", Path(__file__).with_name("Inspect-TodSettingsMenu.py"))
ASSETS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASSETS)

ENUMS = {0: "CHEAT_E3TRAILER", 2: "CHEAT_CONCEPT_CHAR", 4: "CHEAT_TRAILER01",
         6: "CHEAT_CONCEPT_ENV", 8: "CHEAT_HOW_TO_DRAW", 10: "CHEAT_CONCEPT_WEAP",
         12: "CHEAT_SCRIPTSCREEN", 13: "CHEAT_CONCEPT_PAINT"}
ART = [(2, 1, 28, 1, 66), (6, 2, 29, 67, 112), (10, 3, 30, 113, 131), (13, 4, 31, 132, 141)]
MOVIES = [(0, 17, "PRE_RCF_E3_2007_FMV"), (4, 18, "PRE_RCF_FLYBY_FMV"),
          (8, 19, "PRE_RCF_SKETCH_FMV"), (12, 20, "PRE_RCF_SCRIPT_2D_FMV"),
          (12, 21, "PRE_RCF_SCRIPT_3D_01_FMV"), (12, 22, "PRE_RCF_SCRIPT_3D_02_FMV")]
LANGUAGES = [
    (10, "chinese", "cn", 0x5BFF78, 0x5BFFC4, 0x5BFFA0),
    (14, "danish", "dk", 0x5BFFDC, 0x5BFFFC, 0x5BFFF0),
    (12, "finnish", "fi", 0x5C0014, 0x5C0034, 0x5C0028),
    (2, "french", "fr", 0x5C004C, 0x5C006C, 0x5C0060),
    (4, "german", "de", 0x5C0084, 0x5C00A4, 0x5C0098),
    (5, "italian", "it", 0x5C00BC, 0x5C00DC, 0x5C00D0),
    (0, "japanese", "jp", 0x5C00F4, 0x5C0114, 0x5C0108),
    (9, "korean", "kp", 0x5C012C, 0x5C014C, 0x5C0140),
    (6, "dutch", "nl", 0x5C0164, 0x5C0184, 0x5C0178),
    (15, "norwegian", "no", 0x5C019C, 0x5C01BC, 0x5C01B0),
    (7, "portuguese", "pt", 0x5C01D4, 0x5C01F4, 0x5C01E8),
    (3, "spanish", "es", 0x5C020C, 0x5C022C, 0x5C0220),
    (13, "swedish", "se", 0x5C0244, 0x5C0264, 0x5C0258),
]
ASSET_FUNCTIONS = {
    "conceptHandler": (0xE167D, 0xE42FE, {
        "onInitialize": (0xE1E41, 110, "FBCD7B7CF325B80EE046147E995C60EBCF8993E1C7481A1DC605BEEBC2F533B7"),
        "onHintToggle": (0xE3BF5, 57, "9587C7E33475E8479C01B20AB85D116B2BB92648AFFD89BAFCFB74ABD44B0D6B"),
        "goToArt": (0xE2589, 45, "CD5E49D2AF71AFD2C825AD6DAE58C07033EC64FEF2A052AE9EB57B0F05A87DC2"),
    }),
    "cineListUpdater": (0x10A6B8, 0x10C27A, {
        "onInitialize": (0x10B214, 269, "326296FDC3EBCDDEE39570E03BF27BE549D61BA072019D3E6068E2888F8440C5"),
        "handleSelect": (0x10BA30, 23, "BB97B6F2979C444733F6B8E6AFCA8CA6C89CB2EA0D54A8BBE30BBC31FEC5F9DA"),
    }),
}


def availability_indices(menu_id, language):
    """Bounded ID0..13 native arithmetic only; no availability/runtime verdict."""
    for value, limit in ((menu_id, 13), (language, 0xFFFFFFFF)):
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= limit:
            raise ValueError("Expected bounded unsigned menu ID/language")
    physical = menu_id + (language != 1 and menu_id > 4)
    definition = physical - (language != 1 and physical in (7, 11, 14))
    return {"physical_index_after_first_remap": physical, "threshold_definition_index": definition}


def numeric_language_setter(value):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("Expected raw unsigned32 language input")
    return 10 if value == 11 else value


def fold_literals(function, start, end):
    """Fold descriptor literals, preserving one availability call as a symbol."""
    registers = {0: {}}
    constants = function["constants"]
    def operand(value):
        return constants[value - 250] if value >= 250 else registers[value]
    for instruction in function["instructions"][start:end]:
        op, a, b, c = (instruction[k] for k in ("op", "a", "b", "c"))
        if op == "NEWTABLE": registers[a] = {}
        elif op in ("GETGLOBAL", "LOADK"): registers[a] = instruction["constant"]
        elif op == "GETTABLE": registers[a] = registers[b][operand(c)]
        elif op == "SETTABLE": registers[a][operand(b)] = operand(c)
        elif op == "LOADBOOL" and c == 0: registers[a] = bool(b)
        elif op == "CALL" and (a, b, c) == (3, 2, 2) and registers[3] == "is_cheat_unlocked":
            registers[3] = {"api": "is_cheat_unlocked", "enum": registers[4]}
        else: raise ValueError(f"Unsupported descriptor literal operation: {op}")
    return registers[0]


def inspect_asset_bytes(raw):
    if len(raw) != ASSETS.ASSET_SIZE or hashlib.sha256(raw).hexdigest().upper() != ASSETS.ASSET_HASH:
        raise ValueError("Bonus menu requires the exact USA v02.00 pause asset")
    selected, digests = {}, []
    for source, (offset, end, functions) in ASSET_FUNCTIONS.items():
        reader = ASSETS.LUA.Reader(raw, offset)
        root = reader.function()
        if root["source"] != source or reader.pos != end:
            raise ValueError("Bonus menu chunk boundaries changed")
        selected[source] = {}
        for name, (code, count, digest) in functions.items():
            matches = [f for f in root["children"] if f.get("assigned_name") == name]
            if len(matches) != 1:
                raise ValueError("Ambiguous bonus menu function")
            function = matches[0]
            if int(function["code_offset"], 0) != code or len(function["instructions"]) != count or \
                    hashlib.sha256(raw[code:code+count*4]).hexdigest().upper() != digest:
                raise ValueError("Bonus menu bytecode changed")
            selected[source][name] = function
            digests.append({"source": source, "function": name, "offset": hex(code), "instruction_count": count, "sha256": digest})
    art = fold_literals(selected["conceptHandler"]["onInitialize"], 23, 65)["concept_pack"]
    cine = fold_literals(selected["cineListUpdater"]["onInitialize"], 32, 188)["cineArray"]
    for cheat_id, index, tag, _, _ in ART:
        if art[index] != {"enum": ENUMS[cheat_id], "name": float(tag),
                          "available": {"api": "is_cheat_unlocked", "enum": ENUMS[cheat_id]}}:
            raise ValueError("Concept menu symbolic availability descriptor changed")
    if len(cine) != 22 or any(cine[index]["movie"] != movie or cine[index]["enabled"] is not False
                             for _, index, movie in MOVIES):
        raise ValueError("Bonus cinematic descriptors changed")
    functions = [f for group in selected.values() for f in group.values()]
    if any(i.get("constant") == "get_cheat_state" for f in functions for i in f["instructions"]):
        raise ValueError("Unexpected saved-state getter dependency")
    return {"confidence": "asset-backed", "archive_entry": ASSETS.ASSET,
        "size": len(raw), "sha256": ASSETS.ASSET_HASH,
        "concept_descriptors": [{"id": cheat_id, "enum": ENUMS[cheat_id], "pack_index": index,
            "label_tag": tag, "art_index_min": lo, "art_index_max": hi,
            "availability_call": art[index]["available"]} for cheat_id, index, tag, lo, hi in ART],
        "cinematic_descriptors": [{"id": cheat_id, "enum": ENUMS[cheat_id], "row_index": index,
            "movie_literal": cine[index]["movie"], "native_play_movie_argument": movie[4:].lower(),
            "initial_enabled_literal": cine[index]["enabled"]} for cheat_id, index, movie in MOVIES],
        "bytecode_digests": digests,
        "warning": "Static literal/branch inspection only. Availability calls remain symbolic; no Lua/native execution, art/video contents, current menu visibility or saved-state-driven effect is inferred."}


def inspect(elf_path, save_path=None, archive_path=None):
    elf, guards = BINDINGS.Elf(elf_path), {}
    def keep(address, size): guards[address] = elf.read(address, size)
    def check(address, word):
        if elf.u32(address) != word: raise ValueError(f"Bonus language evidence changed at {address:#x}")
        keep(address, 4)
    for address, word in {0x8A83A0: 0x100D6478, 0x100D6478: 1,
        0x5BFE08: 0x81228544, 0x5BFE0C: 0x80690000,
        0x5BFE18: 0x2F83000B, 0x5BFE34: 0x3860000A,
        0x5BFFA8: 0x90090000, 0x5C0270: 0x38000001,
        0x48A908: 0x4BDC7941, 0x252254: 0x4836DD24,
        0x5C028C: 0x38600122, 0x5C02B8: 0x38600111,
        0x5C0308: 0x3800000A, 0x2717C: 0x7C9D1840}.items(): check(address, word)
    for function in (0x5BFE08, 0x5BFE18, 0x5BFF78, 0x5A7358, 0x5C0280,
                     0x24ED8, 0x27008, 0x27098, 0x27108, 0x25088):
        keep(function, elf.functions[elf.functions.index(function)+1]-function)
    for address in (0x10E10, 0x251E08, 0x252248): keep(address, 16)
    keep(0x48A8C4, 0x50)
    language_rows = []
    for value, full, short, full_load, short_load, select in LANGUAGES:
        check(select, 0x38000000 | value)
        tokens = []
        for load, expected in ((full_load, full), (short_load, short)):
            word = elf.u32(load)
            if word & 0xFFFF0000 != 0x80820000:
                raise ValueError("Language token is not a TOC string load")
            slot = 0x8AFE5C + BINDINGS.signed(word & 0xFFFF, 16)
            string_va = elf.u32(slot)
            if elf.string(string_va) != expected: raise ValueError("Language literal changed")
            keep(load, 4); keep(slot, 4); keep(string_va, len(expected)+1)
            tokens.append({"token": expected, "load_va": hex(load), "slot_va": hex(slot), "string_va": hex(string_va)})
        language_rows.append({"selector": value, "tokens": tokens, "select_va": hex(select)})
    for slot, token in ((0x8A6980, "-language"), (0x8A6984, "-lang")):
        string_va = elf.u32(slot)
        if elf.string(string_va) != token: raise ValueError("Native language CLI token changed")
        keep(slot, 4); keep(string_va, len(token)+1)
    enums = [e for e in BASE.PROGRESSION.exports(elf, 0x28440, "CHEAT_", 0x12990) if e["id"] in ENUMS]
    if {e["id"]: e["enum"] for e in enums} != ENUMS: raise ValueError("Remaining bonus identifiers changed")
    for item in enums:
        for key in ("name_slot_va", "name_load_va", "value_slot_va", "value_load_va", "value_move_va", "export_call_va"):
            keep(int(item[key], 0), 4)
        keep(int(item["name_va"], 0), len(item["enum"])+1)
    effects = []
    for cheat_id, name in ENUMS.items():
        address = 0x10026384 + cheat_id*0x30
        keep(address, 0x30)
        if elf.u32(address+12) != 1: raise ValueError("Unexpected remaining bonus state count")
        art_row = next((r for r in ART if r[0] == cheat_id), None)
        movie_rows = [(i, m) for cid, i, m in MOVIES if cid == cheat_id]
        rule = (f"Shipped conceptHandler initializes pack{art_row[1]} availability with is_cheat_unlocked({name}); onHintToggle checks that availability before selecting art indexes{art_row[3]}..{art_row[4]} and entering browsing."
                if art_row else f"Shipped cineListUpdater checks is_cheat_unlocked({name}) to enable cinematic rows{','.join(str(i) for i, _ in movie_rows)}. Previously-played movie status also enables rows; replay bypass applies only to rows1..16. handleSelect passes the lower-cased movie literal with PRE_ removed to play_movie.")
        effects.append({"id": cheat_id, "enum": name, "state_offset": hex(0x86F8+cheat_id),
            "state_type": "u8", "physical_definition_score_requirement": elf.u32(address+8),
            "physical_definition_state_count": 1, "consumer_kind": "shipped pause-menu unlock query",
            "rule": rule, "saved_byte_effect_confirmed": False,
            "scope": "These consumers query native availability, not get_cheat_state. The native API uses language-adjusted threshold indexing; a raw saved byte or physical threshold alone does not establish that this menu entry is unlocked, visible or playing."})
    annotations = [
        (0x5BFE08, "TOD_runtime_language_selector_get", "Returns runtime u32 at100D6478, not a save field. Meaning established by native full/short language literals in5BFF78. Bonus menu count/remap and developer-commentary qualifier compare this getter to1."),
        (0x5BFE18, "TOD_runtime_language_selector_set", "Writes runtime100D6478; numeric11 becomes10, other low32 values are stored without a general valid-language range check."),
        (0x5BFF78, "TOD_runtime_language_selector_parse", "Native language tokens select runtime100D6478: jp/japanese0,fr/french2,es/spanish3,de/german4,it/italian5,nl/dutch6,pt/portuguese7,kp/korean9,cn/chinese10,fi/finnish12,se/swedish13,dk/danish14,no/norwegian15. Unmatched input stores1; do not invent a literal label for1."),
        (0x5C0280, "TOD_runtime_language_and_context_system_init", "Calls cellSysutilGetSystemParamInt identifiers122 and111. On successful122 query stores adjacent runtime word+4;111 result stores language word with11->10. Native code does not test the111 call's return code before reading its stack output; no successful/failure default is inferred."),
    ]
    report = {"confidence": "code-and-asset-backed", "saved_state_base": "0x86f8", "weighted_score_offset": "0x8708",
        "effects": effects, "enum_evidence": enums,
        "runtime_language": {"va": "0x100d6478", "type": "u32", "toc_pointer_slot": "0x8a83a0",
            "getter_va": "0x5bfe08", "numeric_setter_va": "0x5bfe18", "parser_va": "0x5bff78",
            "elf_initial_value": 1, "unmatched_parser_value": 1, "literal_token_catalog": language_rows,
            "comparison_helper_va": "0x5a7358", "comparison_scope": "Helper maps each byte through81F638 before comparing; current character-classification table and arbitrary non-ASCII behavior are not reconstructed here.",
            "cli": {"consumer_va": "0x48a908", "thunk_va": "0x252248", "tokens": ["-language", "-lang"]},
            "system_initializer_va": "0x5c0280", "numeric_alias": {"11": 10},
            "scope": "Runtime-only state, not a property recoverable from the saved bonuses or save-folder region. Selector1 is native default/fallback; an explicit English literal is absent from this parser and is not guessed."},
        "availability_context": {"function_va": "0x27108", "rule": "Language1 exposes14 menu entries; other language values expose13 and skip physical developer-commentary slot5. Native availability first maps menu ID>4 toID+1 for language!=1; then subtracts1 for resulting IDs7/11/14. Saved score8708 is compared unsigned against this adjusted definition threshold, independently of saved state bytes.",
            "language_1_indices": [availability_indices(i, 1) for i in range(14)],
            "other_language_indices": [availability_indices(i, 0) for i in range(13)],
            "warning": "Shipped concept/movie handlers pass named enum constants to this menu-oriented API. Preserve the actual native remapping rather than silently correcting enum IDs; the runtime language and current availability are not present in a save snapshot."},
        "asset_provenance": {"archive_entry": ASSETS.ASSET, "size": ASSETS.ASSET_SIZE, "sha256": ASSETS.ASSET_HASH,
            "verification": "Pass archive_path to independently revalidate the shipped consumers and bytecode digests; expected relationships are documented statically without executing Lua."},
        "recommended_annotations": [{"va": hex(a), "name": n, "kind": "function", "confidence": "code-backed", "bytes": elf.read(a, 8).hex().upper(), "comment": c} for a,n,c in annotations],
        "limitations": ["All eight remaining IDs have menu unlock-query consumers, not new confirmed direct saved-byte effects.",
            "Localized labels, individual art/image/video contents and in-game playback remain unconfirmed.",
            "Runtime language, replay flag and already-played movie status are separate dependencies. Neither arbitrary saved states nor score-only tests are active-effect verdicts.",
            "The native parser's unmatched value1 is not a proven universal valid-language fallback for system-query failure."],
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a,b in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0: raise ValueError("Not the verified plaintext save size")
        data = path.read_bytes()
        if any(struct.unpack_from(">I", data, i*0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        score = struct.unpack_from(">I", data, 0x8708)[0]
        report["save_observation"] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest().upper(),
            "weighted_score": score, "states": [{"id": e["id"], "enum": e["enum"], "raw_state": data[0x86F8+e["id"]],
                "physical_definition_threshold_satisfied": score >= e["physical_definition_score_requirement"]} for e in effects],
            "warning": "Physical thresholds only, not language-adjusted API availability. Unknown state bytes are preserved; runtime language/movie/replay state and menu activity are not inferred."}
    if archive_path is not None:
        archive = ASSETS.PSARC.Psarc(archive_path)
        matches = [i for i,n in enumerate(archive.names) if n == ASSETS.ASSET]
        if len(matches) != 1: raise ValueError("Exact pause bonus asset missing or ambiguous")
        report["asset_observation"] = inspect_asset_bytes(archive.read_entry(matches[0], ASSETS.ASSET_SIZE))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save, args.archive), indent=2, allow_nan=False))
