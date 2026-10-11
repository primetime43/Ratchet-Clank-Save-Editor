"""Read-only arena selector input lists and independent native reward dependencies.

Literal folding of fingerprinted Lua constructors is metadata inspection only:
no calls, branches, Lua VM execution, game execution or original-file writes.
The supplied script list's alias to ARENA_CHALLENGE_DATA remains unproven.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

PROGRESSION = runpy.run_path(str(Path(__file__).with_name("Inspect-TodProgression.py")))
BINDINGS = PROGRESSION["BINDINGS"]
MENU = runpy.run_path(str(Path(__file__).with_name("Inspect-TodArenaMenu.py")))
PREFIX = "/levels/imperial fight fest/scripts/"
BUILT = "/built/levels/imperial fight fest/scripts/"
ASSETS = {
    PREFIX + "main.lua": (16588, "3DEE483B66019465FAA05F228841615068B9F6B8F064B1F95CA05D15C492FA7D"),
    BUILT + "main.lc": (8317, "4C5B1D48B386912611A81CF614F1C182566341C58E430658361BE0FF1300EB30"),
    PREFIX + "arena.lua": (4026, "774C349B4C66E11EF878509079DDDEEB95BA8FABA318264CC45031EFA47C907B"),
    BUILT + "arena.lc": (1769, "0840B449AB5062E94E1AD28841F22BE73C22CE298FB2F5425D42BF9A84F4F47B"),
    PREFIX + "arena_2.lua": (5389, "5E27723DCED186EA87354F792A63DCDC21CA72F54B831A99FC1EF227B4C485F2"),
    BUILT + "arena_2.lc": (2165, "DAAA707D87F371C96DF4951EAD1970BCA6184FF081D621A7EEE4C7F679F71410"),
}
CODE = {
    "main": (0x1681, 639, "AF3EBD9E9C35B9DD25F0C3A5E3D4B1A64833E2F3CD5A0A6FC6F1024DD930DEB2"),
    "arena": (0x3D5, 197, "8F0D75283928E65FA2A11D1BF7B82050A7A610ABAD7F0328A6D6B38E95A750FA"),
    "arena_2": (0x47D, 254, "42A7276DEA33AAFAE32848C72CD1FAF611493718583CEBCC2DBF6E999D653CCB"),
}
RANGES = [
    (0x314E8, 0xC0, "FA2CDF582D91D5037C62F1A74918E6D7D2E0B8EE9E4CCE6A8AEDB7089A8C2DDD"),
    (0x26088, 0x50, "CE7748E9108A79DAF4A8BEAF22F17C7993C176533911B961AC950C88721D918E"),
    (0x275340, 0xF8, "9A99BF56B4B6AB939C1BEE7056EA705660526ED790B3263ECFCA47B744A68D47"),
    (0x239C8, 0x98, "CE2819214103BE62A2FC906D8B25A00E448B7CFED28DBEDC55B80C7BAC40208E"),
    (0x10CC0, 0x10, "EA572512307197EDCDAD59E722125B63D41686C18B267E85A6A9FEF9E0BCEFCA"),
    (0x273D0, 0x90, "EDF88238528B69F554303818AAD1083F298DD62C59A8DF2637D3773051244523"),
    (0x316B8, 0x110, "DFB0A56030443D84789D61385B8B6CE40B0E2FBA8837181AEE8A1F8EF800970B"),
    (0x317C8, 0x110, "C079A52767128C830360D335430C4C6DCCB8C49C462A561E08774C935BEAB11E"),
    (0x261E0, 0x40, "B9EF08819CB9B7A77230CF7BDCA0080DE491522C17EBF0B76659D2B4B4F70D80"),
    (0x12DB0, 0x10, "4F2F799EF5C29440B086F463748D278D71A27D84FB71A975DAE8D6F955490D15"),
    (0x282AF8, 0xD0, "287525153C30C3A3541C655B2044DF9CFFF0803C59734574C2CCA618FE3FB07E"),
    (0x39DEA8, 0x10, "EF6A82C72DB834CFAFF51C4A2512D43EACBBAE829997067065F00DE1E8BAEF1A"),
    (0x24F098, 0x10, "A43AA7594F1FE6211833786ACE99CA94B78CAB7C72D2BBC1C4842FC8F4CF86F0"),
    (0x27948, 0x40, "E3DB7615811EC277F4346549808EE8EA980BC9F43D69D7D3B57A16E764C773E2"),
]
FLAG_IDS = {"LVL_IFF_CHALLENGE_1_DONE": 74, "LVL_IFF_CHALLENGE_2_DONE": 75,
            "LVL_IFF_RETURN_CHALLENGE_9_DONE": 88, "LVL_IFF_RETURN_CHALLENGE_10_DONE": 89}


def preview_weapon_reward(configured_weapon_id, raw_count):
    """Pure synthetic ordinary-domain model; not a runtime config/save lookup."""
    if type(configured_weapon_id) is not int or not -(1 << 31) <= configured_weapon_id < (1 << 31) or \
            type(raw_count) is not int or not 0 <= raw_count < (1 << 32):
        raise ValueError("Expected signed32 configured weapon ID and raw uint32 counter")
    return configured_weapon_id if configured_weapon_id > 0 and raw_count == 0 else -1


def fold_literals(function, first, end):
    """Bounded straight-line constructor fold; GETGLOBAL yields symbols only."""
    registers, globals_out = {}, {}
    constants = function["constants"]

    def operand(value):
        return constants[value - 250] if value >= 250 else registers[value]

    for instruction in function["instructions"][first:end]:
        op, a, b, c = (instruction[k] for k in ("op", "a", "b", "c"))
        if op == "NEWTABLE":
            registers[a] = {}
        elif op == "GETGLOBAL":
            registers[a] = {"global_symbol": instruction["constant"]}
        elif op == "LOADBOOL" and c == 0:
            registers[a] = bool(b)
        elif op == "SETTABLE":
            registers[a][operand(b)] = operand(c)
        elif op == "SETGLOBAL":
            globals_out[instruction["constant"]] = registers[a]
        elif op == "SETLIST" and 0 <= instruction["bx"] < 32:
            for index in range(1, instruction["bx"] + 2):
                registers[a][index] = registers[a + index]
        else:
            raise ValueError(f"Literal metadata fold refuses opcode {op}")
    return registers, globals_out


def inspect_asset_bytes(payloads, challenge_ids):
    if set(payloads) != set(ASSETS):
        raise ValueError("Expected all six exact source/compiled arena script assets")
    roots, metadata = {}, []
    lua = MENU["module"]("tod_arena_table_lua", "Inspect-Lua50.py")
    for name, (size, digest) in ASSETS.items():
        raw = payloads[name]
        if len(raw) != size or hashlib.sha256(raw).hexdigest().upper() != digest:
            raise ValueError("Arena script fingerprint mismatch")
        metadata.append({"archive_entry": name, "size": size, "sha256": digest})
        if name.endswith(".lc"):
            key = Path(name).stem
            reader = lua.Reader(raw, 0)
            root = reader.function()
            offset, count, code_digest = CODE[key]
            if reader.pos != len(raw) or root["source"] != "=(none)" or \
                    int(root["code_offset"], 0) != offset or len(root["instructions"]) != count or \
                    hashlib.sha256(raw[offset:offset + count * 4]).hexdigest().upper() != code_digest:
                raise ValueError("Compiled arena root function changed")
            roots[key] = root
    _, descriptors = fold_literals(roots["main"], 48, 268)
    if len(descriptors) != 20 or any(not key.startswith("arena_challenge_") for key in descriptors):
        raise ValueError("Unexpected compiled master descriptor count")
    records = {}
    for symbol, fields in descriptors.items():
        if set(fields) != {"id", "script", "active", "name", "desc"}:
            raise ValueError("Unexpected master descriptor fields")
        enum = fields["id"]["global_symbol"]
        if enum not in challenge_ids or type(fields["active"]) is not bool:
            raise ValueError("Unknown compiled master descriptor enum")
        identifier = challenge_ids[enum]
        records[symbol] = {"table_symbol": symbol, "id_enum": enum, "native_id": identifier,
                           "save_counter_offset": hex(0x56D8 + identifier * 4), "script": fields["script"],
                           "initial_active": fields["active"], "name_symbol": fields["name"]["global_symbol"],
                           "description_symbol": fields["desc"]["global_symbol"]}
    first, _ = fold_literals(roots["arena"], 0, 22)
    returns, _ = fold_literals(roots["arena_2"], 0, 44)

    def rows(table):
        keys = sorted(k for k in table if type(k) is int)
        if keys != list(range(1, len(keys) + 1)):
            raise ValueError("Non-contiguous selector input literal")
        return [{"selector_input_index": key, **records[table[key]["global_symbol"]]} for key in keys]

    lists = [
        {"name": "first_trip_intro_one", "condition": "LVL_IFF_CHALLENGE_1_DONE is clear", "selector_called": False, "rows": rows(first[0])},
        {"name": "first_trip_intro_two", "condition": "First flag set and LVL_IFF_CHALLENGE_2_DONE clear", "selector_called": False, "rows": rows(first[1])},
        {"name": "first_trip_final", "condition": "Both first-trip flags set", "selector_called": True, "rows": rows(first[2])},
        {"name": "return_trip_bonus_one", "condition": "Reached arena_2 loop after its two opening challenge scripts", "selector_called": True, "rows": rows(returns[0])},
    ]
    if [len(row["rows"]) for row in lists] != [1, 1, 8, 18] or rows(returns[0]) != rows(returns[1]):
        raise ValueError("Unexpected source-list relationship")
    for entry, table in zip(lists, [first[0], first[1], first[2], returns[0]]):
        entry["arena_title_symbol"] = table["arenaname"]["global_symbol"]
    guards, gates = [], []

    def guard_range(key, first_pc, end_pc, meaning):
        root = roots[key]
        raw = payloads[BUILT + key + ".lc"]
        offset = int(root["code_offset"], 0) + first_pc * 4
        guards.append({"archive_entry": BUILT + key + ".lc", "first_pc": first_pc,
                       "end_pc_exclusive": end_pc, "offset": hex(offset),
                       "bytes": raw[offset:offset + (end_pc - first_pc) * 4].hex().upper(), "meaning": meaning})

    guard_range("main", 48, 268, "Twenty literal challenge descriptors; GETGLOBAL operands remain symbols.")
    guard_range("arena", 0, 22, "Three first-trip literal source lists.")
    guard_range("arena_2", 0, 44, "Two identical return literals; only first is reached by selector call.")
    for key, expected_count in [("arena", 4), ("arena_2", 10)]:
        instructions = roots[key]["instructions"]
        found = 0
        for pc, instruction in enumerate(instructions):
            if instruction.get("constant") != "get_challenge_successes":
                continue
            window = instructions[pc - 1:pc + 9]
            if len(window) != 10 or [q["op"] for q in window] != \
                    ["GETGLOBAL", "GETGLOBAL", "GETGLOBAL", "GETTABLE", "CALL", "LT", "JMP", "LOADBOOL", "LOADBOOL", "SETTABLE"] or \
                    window[3].get("c_constant") != "id" or window[5].get("b_constant") != 0 or \
                    window[5]["a"] != 1 or window[9].get("b_constant") != "active":
                raise ValueError("Unexpected compiled signed completion activation pattern")
            target, required = window[0]["constant"], window[2]["constant"]
            gates.append({"script_asset": BUILT + key + ".lc", "target_table": target,
                          "target_native_id": records[target]["native_id"], "requires_table": required,
                          "requires_native_id": records[required]["native_id"],
                          "requires_save_counter_offset": records[required]["save_counter_offset"],
                          "condition": "signed32(get_challenge_successes(required_native_id)) > 0"})
            guard_range(key, pc - 1, pc + 9, "Signed-positive count predicate assigns active; no Lua calls executed.")
            found += 1
        if found != expected_count:
            raise ValueError("Incomplete compiled activation gate census")
    guard_range("arena", 70, 107, "Ordered story-flag branch, selector call only for final list; singleton branches force selection1.")
    guard_range("arena_2", 66, 98, "Return opening scripts gated by independent flags88/89.")
    guard_range("arena_2", 199, 204, "MOVE selects bonus-one register0; selector receives it, not bonus-two register1.")
    return {
        "confidence": "asset-backed", "assets": metadata,
        "compiled_root_digests": [{"asset": BUILT + key + ".lc", "code_offset": hex(offset),
                                   "instruction_count": count, "sha256": digest} for key, (offset, count, digest) in CODE.items()],
        "master_descriptors": list(records.values()), "source_lists": lists, "activation_gates": gates,
        "unreached_literal": {"name": "return_trip_bonus_two", "identical_to": "return_trip_bonus_one",
                              "warning": "Compiled literal exists but is not supplied by the live selector call; not an extra selectable branch."},
        "catalog_exclusions": {"no_compiled_master_descriptor": [name for name in challenge_ids if name not in {r["id_enum"] for r in records.values()}],
                               "master_but_not_reached_return_list": [r["id_enum"] for r in records.values() if r["native_id"] not in {q["native_id"] for q in lists[3]["rows"]}]},
        "execution_relationship": "Positive returned selector_input_index indexes the same supplied list and launches that row's .script. The first-trip singleton branches do not call select_arena_challenge and force index1.",
        "localization_warning": "Names/descriptions and arena title are symbolic localization bindings, not independently decoded English strings.",
        "alias_warning": "These are compiled selector-input indices, not a recovered alias/current snapshot of ARENA_CHALLENGE_DATA indices and not display rows. Native operation bridge is traced; subsequent table installation remains unresolved.",
        "asset_byte_guards": guards,
    }


def inspect_assets(archive_path, challenge_ids):
    psarc = MENU["module"]("tod_arena_table_psarc", "Inspect-Psarc.py")
    archive = psarc.Psarc(archive_path)
    payloads = {}
    for name, (size, _) in ASSETS.items():
        matches = [i for i, value in enumerate(archive.names) if value == name]
        if len(matches) != 1:
            raise ValueError("Exact arena script missing or ambiguous")
        payloads[name] = archive.read_entry(matches[0], size)
    return inspect_asset_bytes(payloads, challenge_ids)


def inspect(elf_path, archive_path=None, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    for address, size, digest in RANGES:
        if hashlib.sha256(elf.read(address, size)).hexdigest().upper() != digest:
            raise ValueError("Arena table native guard mismatch")
        keep(address, size)
    enums = PROGRESSION["exports"](elf, 0x294E90, "IFF_", 0x252EB8)
    if [e["id"] for e in enums] != list(range(1, 23)):
        raise ValueError("Unexpected arena enum catalog")
    ids = {e["enum"]: e["id"] for e in enums}
    primary = PROGRESSION["exports"](elf, 0x28440, "LVL_", 0x12990)
    secondary = PROGRESSION["exports"](elf, 0x294E90, "LVL_", 0x252EB8)
    flags = []
    selected_exports = []
    for name, identifier in FLAG_IDS.items():
        left = [e for e in primary if e["enum"] == name]
        right = [e for e in secondary if e["enum"] == name]
        if len(left) != 1 or len(right) != 1 or left[0]["id"] != identifier or right[0]["id"] != identifier:
            raise ValueError("Independent story-flag exports disagree")
        selected_exports.extend(left + right)
        word = 0x5528 + identifier // 64 * 8
        bit = identifier % 64
        flags.append({"enum": name, "id": identifier, "word_offset": hex(word), "word_bit": bit,
                      "byte_offset": hex(word + 7 - bit // 8), "byte_mask": hex(1 << (bit % 8))})
    for item in enums + selected_exports:
        keep(int(item["name_va"], 0), len(item["enum"]) + 1)
        for key in ("name_slot_va", "name_load_va", "value_slot_va", "value_load_va", "value_move_va", "export_call_va"):
            keep(int(item[key], 0), 4)
    bindings = []
    for slot, name, wrapper in [(0x889454, "select_challenge", 0x314E8),
                                (0x889444, "get_challenge_weapon_reward", 0x316B8),
                                (0x88943C, "get_challenge_bolt_reward", 0x317C8)]:
        pointer, descriptor = struct.unpack(">II", elf.read(slot, 8))
        if elf.string(pointer) != name or elf.u32(descriptor) != wrapper:
            raise ValueError("Named arena selection/reward registration changed")
        keep(slot, 8); keep(descriptor, 8); keep(pointer, len(name) + 1)
        bindings.append({"name": name, "registration_slot_va": hex(slot), "wrapper_va": hex(wrapper)})
    for slot, expected in [(0x888624, 0x101EFB20), (0x888628, 0x101AEFF8),
                           (0x88867C, 0x101B9EE8), (0x8885B4, 0x101AEF80),
                           (0x898EC8, 0x10019CC0), (0x8991E0, 0x1001A7D8)]:
        if elf.u32(slot) != expected:
            raise ValueError("Arena runtime pointer/key changed")
        keep(slot, 4)
    if elf.string(0x10019CC0) != "selection" or elf.string(0x1001A7D8) != "select_arena_challenge":
        raise ValueError("Arena selector key/name changed")
    keep(0x10019CC0, len("selection") + 1)
    keep(0x1001A7D8, len("select_arena_challenge") + 1)
    report = {
        "confidence": "native-confirmed", "binary_sha256": hashlib.sha256(elf.raw).hexdigest().upper(),
        "native_challenge_ids": [{"enum": e["enum"], "id": e["id"]} for e in enums], "story_flags": flags,
        "weapon_reward_getter": {"chain": ["0x316b8", "0x273d0", "0x110b0", "0x2756f8"],
                                 "input_space": "source_index", "configuration": "ArenaConfig[native_id].WpnReward at parent1177C + native_id*34 +10",
                                 "configured_weapon_load_va": "0x27408", "counter_load_va": "0x2741c",
                                 "counter_formula": "saved56D8 + 4*native_id", "predicate": "signed configured weapon ID > 0 AND raw uint32 completion count == 0",
                                 "else_result": -1, "warning": "Any nonzero counter, including high-bit/negative signed values, hides the first-victory weapon reward. This differs from the shipped UI's signed-positive completion partition and activation gates."},
        "bolt_reward_getter": {"chain": ["0x317c8", "0x261e0", "0x110b0", "0x2756f8", "0x12db0", "0x2ceab0"],
                               "meaning": "Resolve menu source index to native ID, invoke the independently mapped direct-ID reward calculator, then fctidz and return signed low32 bits. No live quote without current runtime config."},
        "selection_side_effects": {"chain": ["0x314e8", "0x26088"],
                                   "ordered_actions": ["10CC0→275340 writes the supplied source index to runtime Lua ARENA_CHALLENGE_DATA.selection.",
                                                       "110B0→2756F8 resolves the same source index to native ID;260B4 stores it into runtime object+D8 through pointer888628.",
                                                       "239C8 requests a runtime phase transition: phase3 dispatches event0x57 with payload word0xA and becomes4; other phases become0."],
                                   "warning": "Lua selection, runtime native ID and phase are runtime-only here; no new saved selection field is assigned. Downstream event side effects/in-game acceptance are not established."},
        "selector_bridge": {"function_va": "0x282af8", "identifier_pointer_slot_va": "0x8991e0", "toc_va": "0x89ff20",
                            "meaning": "Validates actor/typeB9, clears a runtime member via39DEA8, and calls24F098(thread+48, opcode5,0,0); thunk24F098 branches to23AD0.",
                            "alias_gap": "This operation bridge does not itself install or alias the supplied list as ARENA_CHALLENGE_DATA; dispatcher/table binder remains unresolved."},
        "bindings": bindings,
        "recommended_annotations": [
            {"va": "0x273d0", "name": "TOD_arena_menu_first_victory_weapon_reward",
             "comment": "Named menu weapon-reward getter resolves source index to native ID; returns configured positive weapon ID only for raw saved count0, else-1. High-bit counts are nonzero, not a signed-positive test."},
            {"va": "0x26088", "name": "TOD_arena_menu_select_source_index",
             "comment": "Writes Lua.selection source index, resolves/stores runtime native ID+D8, and requests runtime phase change. No new saved selection field assigned."},
            {"va": "0x282af8", "name": "TOD_arena_selector_prepare_operation5",
             "comment": "select_arena_challenge identifier consumer validates actor typeB9 and requests thread operation5. Does not itself prove supplied-list alias/installation as ARENA_CHALLENGE_DATA."},
        ],
        "unresolved": ["Selector input index, native ID and display row remain distinct; source lists are not a current runtime menu snapshot.",
                       "The dispatcher that aliases the supplied script list to ARENA_CHALLENGE_DATA remains unrecovered.",
                       "Source flags and counters do not alone prove which script, list, trip, replay state or UI is currently running.",
                       "No safe-edit/in-game acceptance contract follows from these static dependencies."],
        "instruction_guards": [{"va": hex(address), "bytes": raw.hex().upper()} for address, raw in sorted(guards.items())],
    }
    if archive_path is not None:
        report["asset_observation"] = inspect_assets(archive_path, ids)
    if save_path is not None:
        if Path(save_path).stat().st_size != 0x906F0:
            raise ValueError("Expected exact-length Tools of Destruction plaintext")
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Expected plaintext inventory IDs0..31")
        values = [{**flag, "set": bool(int.from_bytes(raw[int(flag["word_offset"], 0):int(flag["word_offset"], 0) + 8], "big") & (1 << flag["word_bit"]))} for flag in flags]
        report["save_observation"] = {"size": len(raw), "plaintext_sha256": hashlib.sha256(raw).hexdigest().upper(),
                                      "story_flags": values, "signed_counts_by_native_id": list(struct.unpack_from(">23i", raw, 0x56D8)),
                                      "first_trip_gate_if_script_loop_reached": "first_trip_intro_one" if not values[0]["set"] else "first_trip_intro_two" if not values[1]["set"] else "first_trip_final",
                                      "warning": "Saved predicate observations only, not proof that any corresponding script/list/current menu is active."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.archive, args.save), indent=2))
