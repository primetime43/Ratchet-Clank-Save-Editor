"""Read-only operation5 routing and compiled arena saved milestone writers.

Exact ELF/asset guards only. No Lua/game execution, table-alias reconstruction,
save editing, private binary extraction or reconstructed engine timing.
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
    "challenge1": {"lua": (8610, "AD15AA65CB5FC5BDE11A3ABDC7E279B48DD940C6002667E23D6DFEF5F38294A3"),
                   "lc": (4848, "F93872D904D8CFFDA179DEAFE8198C292B058F4DA4B79F03A06D70DE5AD79818"),
                   "code": (0x868, 674, "5523F6ECF0A3757B1F3563057A0F4BDA098E5F8FCE6C19A7653D6CB8D8ABA820")},
    "challenge4": {"lua": (6795, "541802BC503650E97A9DE0752AE72128E53C46F9DA98D3FFF6287FD37EC912C3"),
                   "lc": (4053, "11454F1E03C683479BBC29D6A8AEB5E4DEC2BC276A44F0DFDD203608E2F56F3D"),
                   "code": (0x9D9, 383, "939FF7813E14F6A45D49985ED6E5CEE7923660847D3BEFE6EAFA2BA8348EE662")},
    "challenge6": {"lua": (11110, "493CB01EDA629A3B539CBDB20BC99A7DAAA0ED5BB0C84821A0506A1B7953B472"),
                   "lc": (6257, "7BB15D4D9F5DB186E0AD86FCE2BD9FA929C61C2AA8A3F40B795FCFE3AE1A5465"),
                   "code": (0xB2D, 849, "D1CEED0BD3218096949587071B5CCE1C589204994FD7ECB36022C86CFE833547")},
    "challenge10": {"lua": (6025, "4CC82EE1A3605AC11341A4222741035323ECE2238753A57125AB59063D7C4547"),
                    "lc": (3593, "161976BE346F2B4A01C53918B04B8D69514F09EE60FC3461606A3073A2E5B07D"),
                    "code": (0x871, 358, "CC8FF2B4BCC90E6F37C8DE18A8578A50D78A5B06FD06DBC60630E9C363CA82A8")},
}
RANGES = [
    (0x23AD0, 0xF0, "CE866811C2D37229446F98C8EDE575C25C235DA422F89CB4D9333E6AD9E456CD"),
    (0x24650, 0x390, "2FEDACE52D91146EC935944EA057D9325320D72129A5A266861D98853FA0A928"),
    (0x62D080, 0xD0, "E443387569E44DB863DAF129B5954AA0EF879E4FE5D4D749004F4DB647FF2662"),
    (0x62D2E8, 0x510, "96DF4DBC7825EEC0C829204442328F04AD1478B72BDDA2A8E7490456D30EF1A8"),
    (0x27A9C8, 0x1B0, "955E7249478B94AB4DF0B8D787BB62133276D2701D8A031DB9BB58B1B956D240"),
    (0x24A80, 0x30, "E7C377596E703703889AE5FF67B0E47F0B31E18848F683E470AD75536EE6C143"),
    (0x27BB10, 0x30, "BC14AD55B3ADF4E5A66E5ED37BE364C1662A9217D52D7F248198C48FDF9E75E6"),
    (0x2C9CA8, 0xB8, "8503A9B15AA9A00ECF2DB643FA10F5B4CA6695667116214734C523156504F6F2"),
    (0x34698, 0xB8, "1FDEA7D6CC799C8C41AF258292C012106CC28CCE8A48178F9EBE4DA61767688D"),
    (0x2CB080, 0xB8, "BB920533AE63CECAC4FFBF6D6EE835FAC4A527008027E80BB8FF0069F902ACCD"),
]
FLAGS = {"LVL_IFF_CHALLENGE_1_DONE": 74, "LVL_IFF_CHALLENGE_2_DONE": 75,
         "LVL_IFF_CKPT_IN_ARENA": 85, "LVL_IFF_RETURN_CHALLENGE_9_DONE": 88,
         "LVL_IFF_RETURN_CHALLENGE_10_DONE": 89}
CHALLENGES = {"IFF_A_1": 1, "IFF_A_4": 4, "IFF_A_6": 6, "IFF_B_10": 12}


def inspect_asset_bytes(payloads):
    expected = {prefix + script + "." + extension for script in ASSETS
                for extension, prefix in [("lua", PREFIX), ("lc", BUILT)]}
    if set(payloads) != expected:
        raise ValueError("Expected all eight exact source/compiled writer assets")
    lua = MENU["module"]("tod_arena_dispatch_lua", "Inspect-Lua50.py")
    roots, metadata, digests = {}, [], []
    for script, definitions in ASSETS.items():
        for extension, prefix in [("lua", PREFIX), ("lc", BUILT)]:
            name = prefix + script + "." + extension
            raw = payloads[name]
            size, digest = definitions[extension]
            if len(raw) != size or hashlib.sha256(raw).hexdigest().upper() != digest:
                raise ValueError("Arena writer asset fingerprint mismatch")
            metadata.append({"archive_entry": name, "size": size, "sha256": digest})
        raw = payloads[BUILT + script + ".lc"]
        reader = lua.Reader(raw, 0)
        root = reader.function()
        offset, count, digest = definitions["code"]
        if reader.pos != len(raw) or int(root["code_offset"], 0) != offset or \
                len(root["instructions"]) != count or \
                hashlib.sha256(raw[offset:offset + count * 4]).hexdigest().upper() != digest:
            raise ValueError("Compiled arena writer root changed")
        roots[script] = root
        digests.append({"asset": BUILT + script + ".lc", "code_offset": hex(offset),
                        "instruction_count": count, "sha256": digest})
    guards = []

    def guard(script, first_pc, end_pc, meaning):
        offset = ASSETS[script]["code"][0] + first_pc * 4
        raw = payloads[BUILT + script + ".lc"]
        guards.append({"archive_entry": BUILT + script + ".lc", "first_pc": first_pc,
                       "end_pc_exclusive": end_pc, "offset": hex(offset),
                       "bytes": raw[offset:offset + (end_pc - first_pc) * 4].hex().upper(), "meaning": meaning})

    def literal_call(script, pc, function, argument):
        q = roots[script]["instructions"][pc:pc + 3]
        if [i["op"] for i in q] != ["GETGLOBAL", "GETGLOBAL", "CALL"] or \
                q[0].get("constant") != function or q[1].get("constant") != argument or \
                q[1]["a"] != q[0]["a"] + 1 or q[2]["a"] != q[0]["a"] or (q[2]["b"], q[2]["c"]) != (2, 1):
            raise ValueError("Unexpected compiled native writer call")
        guard(script, pc, pc + 3, function + "(" + argument + ")")
        return {"pc": pc, "call_pc": pc + 2, "api": function, "argument_enum": argument}

    def clear_flag_branch(script, pc, flag, jump_target):
        q = roots[script]["instructions"][pc:pc + 5]
        if [i["op"] for i in q] != ["GETGLOBAL", "GETGLOBAL", "CALL", "TEST", "JMP"] or \
                q[0].get("constant") != "check_flag" or q[1].get("constant") != flag or \
                q[2]["b"] != 2 or q[2]["c"] != 2 or q[3]["c"] != 1 or q[4].get("jump_pc") != jump_target:
            raise ValueError("Unexpected compiled first-milestone branch")
        guard(script, pc, pc + 5, "Set flag path runs only while milestone flag is clear.")

    writers = []
    specs = [
        ("challenge1", "IFF_A_1", 624, "LVL_IFF_CHALLENGE_1_DONE", 636, 631, 655, None),
        ("challenge4", "IFF_A_4", 228, "LVL_IFF_CHALLENGE_2_DONE", 307, 231, 358, 323),
        ("challenge6", "IFF_A_6", 719, "LVL_IFF_RETURN_CHALLENGE_9_DONE", 708, None, None, None),
        ("challenge10", "IFF_B_10", 229, "LVL_IFF_RETURN_CHALLENGE_10_DONE", 288, 232, 333, 304),
    ]
    for script, challenge, success_pc, flag, flag_pc, check_pc, jump, checkpoint_pc in specs:
        success = literal_call(script, success_pc, "set_challenge_success", challenge)
        milestone = literal_call(script, flag_pc, "set_flag", flag)
        actions = sorted([success, milestone], key=lambda row: row["pc"])
        if check_pc is not None:
            clear_flag_branch(script, check_pc, flag, jump)
        if checkpoint_pc is not None:
            actions.append(literal_call(script, checkpoint_pc, "set_flag", "LVL_IFF_CKPT_IN_ARENA"))
        writers.append({"script": script, "native_id": CHALLENGES[challenge],
                        "save_counter_offset": hex(0x56D8 + CHALLENGES[challenge] * 4),
                        "milestone_enum": flag, "milestone_flag_id": FLAGS[flag], "ordered_actions": actions,
                        "milestone_condition": "Milestone flag is clear on reaching this block" if check_pc is not None else "challenge_6_timer_timeup is false on reaching this block"})
    q = roots["challenge6"]["instructions"]
    if [i["op"] for i in q[693:696]] != ["GETGLOBAL", "TEST", "JMP"] or \
            q[693].get("constant") != "challenge_6_timer_timeup" or q[694]["c"] != 1 or q[695].get("jump_pc") != 748:
        raise ValueError("Unexpected timeout guard around challenge6 milestone")
    if [i["op"] for i in q[716:719]] != ["GETGLOBAL", "LOADK", "CALL"] or \
            q[716].get("constant") != "wait" or q[717].get("constant") != 6.0 or \
            (q[718]["b"], q[718]["c"]) != (2, 1):
        raise ValueError("Unexpected wait literal between flag and counter callback")
    guard("challenge6", 693, 722, "Timeout false branch sets flag88, then wait literal6, then native counter success callback.")
    return {"confidence": "asset-backed", "assets": metadata, "compiled_root_digests": digests,
            "saved_milestone_writers": writers,
            "flag_before_counter_case": {"script": "challenge6", "flag_call_pc": 710,
                                         "wait_call_pc": 718, "wait_literal": 6.0, "counter_call_pc": 721,
                                         "warning": "Source wait literal only, not reconstructed engine timing or an asserted duration of an observable save window."},
            "separate_state_warning": "Story milestone flags, arena checkpoint flag and success counters are separate serialized dependencies and separate script calls. Editing a counter does not perform the script's flag/cinematic/checkpoint/inventory actions; their relationship is not an atomic transaction.",
            "scope_warning": "Static reached-block relationships only; no Lua execution, current script proof, complete failure-path reconstruction or in-game edit acceptance.",
            "index_warning": "Script filename numbers, source selector indices, exported native challenge IDs and current display rows are distinct. challenge10 uses exported IFF_B_10/native ID12; no menu-row equality is established.",
            "asset_byte_guards": guards}


def inspect_assets(archive_path):
    psarc = MENU["module"]("tod_arena_dispatch_psarc", "Inspect-Psarc.py")
    archive = psarc.Psarc(archive_path)
    payloads = {}
    for script, definitions in ASSETS.items():
        for extension, prefix in [("lua", PREFIX), ("lc", BUILT)]:
            name = prefix + script + "." + extension
            matches = [i for i, value in enumerate(archive.names) if value == name]
            if len(matches) != 1:
                raise ValueError("Exact arena writer asset missing or ambiguous")
            payloads[name] = archive.read_entry(matches[0], definitions[extension][0])
    return inspect_asset_bytes(payloads)


def inspect(elf_path, archive_path=None, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    for address, size, digest in RANGES:
        if hashlib.sha256(elf.read(address, size)).hexdigest().upper() != digest:
            raise ValueError("Arena dispatcher native guard mismatch")
        keep(address, size)
    for slot, expected in [(0x8885B4, 0x101AEF80), (0x888610, 0x24714), (0x8A9514, 0x8564C8),
                           (0x8564D0, 0x87BD40), (0x87BD40, 0x62D2E8), (0x87BD44, 0x8AFE5C),
                           (0x888624, 0x101EFB20), (0x898F50, 0x101EFB20)]:
        if elf.u32(slot) != expected:
            raise ValueError("Arena dispatcher pointer/vtable changed")
        keep(slot, 4)
    table = elf.u32(0x888610)
    routes = [(table + struct.unpack(">i", elf.read(table + 4 * i, 4))[0]) & 0xFFFFFFFF for i in range(8)]
    if routes != [0x24734, 0x248D8, 0x24880, 0x249A8, 0x24974, 0x24940, 0x2490C, 0x248D8]:
        raise ValueError("Operation routing changed")
    keep(table, 32)
    bindings = []
    for slot, name, wrapper, native in [(0x89D8E4, "set_challenge_success", 0x2C9CA8, 0x27A9C8),
                                        (0x8892B4, "set_flag", 0x34698, 0x24A80),
                                        (0x89D85C, "set_flag", 0x2CB080, 0x27BB10)]:
        pointer, descriptor = struct.unpack(">II", elf.read(slot, 8))
        if elf.string(pointer) != name or elf.u32(descriptor) != wrapper:
            raise ValueError("Named saved writer binding changed")
        end = elf.functions[elf.functions.index(wrapper) + 1]
        if not any(word >> 26 == 18 and word & 1 and BINDINGS.branch_target(word, va) == native
                   for va, word in elf.instructions(wrapper, end)):
            raise ValueError("Named saved writer no longer calls native")
        keep(slot, 8); keep(descriptor, 8); keep(pointer, len(name) + 1)
        bindings.append({"name": name, "registration_slot_va": hex(slot), "wrapper_va": hex(wrapper), "native_va": hex(native)})
    flags = []
    for name, identifier in FLAGS.items():
        registrations = []
        for start, target in [(0x28440, 0x12990), (0x294E90, 0x252EB8)]:
            matches = [e for e in PROGRESSION["exports"](elf, start, "LVL_IFF_", target) if e["enum"] == name]
            if len(matches) != 1 or matches[0]["id"] != identifier:
                raise ValueError("Arena milestone flag exports disagree")
            registrations.extend(matches)
        for item in registrations:
            keep(int(item["name_va"], 0), len(name) + 1)
            for key in ("name_slot_va", "name_load_va", "value_slot_va", "value_load_va", "value_move_va", "export_call_va"):
                keep(int(item[key], 0), 4)
        flags.append({"enum": name, "id": identifier, "word_offset": hex(0x5528 + identifier // 64 * 8), "word_bit": identifier % 64})
    challenge_exports = PROGRESSION["exports"](elf, 0x294E90, "IFF_", 0x252EB8)
    for name, identifier in CHALLENGES.items():
        match = [e for e in challenge_exports if e["enum"] == name]
        if len(match) != 1 or match[0]["id"] != identifier:
            raise ValueError("Arena milestone challenge enum changed")
        item = match[0]
        keep(int(item["name_va"], 0), len(name) + 1)
        for key in ("name_slot_va", "name_load_va", "value_slot_va", "value_load_va", "value_move_va", "export_call_va"):
            keep(int(item[key], 0), 4)
    report = {
        "confidence": "native-confirmed", "binary_sha256": hashlib.sha256(elf.raw).hexdigest().upper(),
        "request_constructor": {"function_va": "0x23ad0", "runtime_owner_pointer_slot_va": "0x8885b4",
                                "members": [{"offset": "0x8", "type": "u64", "meaning": "Supplied runtime thread token"},
                                            {"offset": "0x10", "type": "u32", "meaning": "Request argument r6"},
                                            {"offset": "0x14", "type": "u32", "meaning": "Auxiliary runtime token resolved through 1E1C00 then 12DF0"},
                                            {"offset": "0x18", "type": "u32", "meaning": "Requested operation r4; arena bridge supplies 5"},
                                            {"offset": "0x1c", "type": "u32", "meaning": "Request argument r5"},
                                            {"offset": "0x20", "type": "u32", "meaning": "Cleared to 0"},
                                            {"offset": "0x24", "type": "u8", "meaning": "Cleared to 0"}],
                                "warning": "Runtime controller members, not serialized save offsets."},
        "operation_dispatch": {"function_va": "0x24650", "relative_table_pointer_slot_va": "0x888610", "relative_table_va": "0x24714",
                               "routes": [{"operation": i, "target_va": hex(target)} for i, target in enumerate(routes)],
                               "arena_case_va": "0x24940", "arena_operation": 5,
                               "loader": {"constructor_va": "0x62d080", "vtable_va": "0x8564c8", "method_offset": "0x8",
                                          "descriptor_va": "0x87bd40", "function_va": "0x62d2e8", "toc_va": "0x8afe5c"},
                               "case_arguments": "Case5 supplies runtime resource-owner+108 members: descriptor+758, word+858, shared owner+108+2C, and descriptor+768 to the constructed UI object's virtual loader.",
                               "alias_gap": "This proves operation5 selects a concrete UI loader/descriptor path, not installation or aliasing of the supplied challenge list as ARENA_CHALLENGE_DATA. No recovered source-index/native-ID/current-display-row equivalence."},
        "serialized_writer_chains": {"named_bindings": bindings,
                                     "success_counter": {"native_va": "0x27a9c8", "formula": "saved56D8 + native_id*4", "increment_store_vas": ["0x27aad0", "0x27ab50"],
                                                         "meaning": "Native success transaction increments the BE32 counter modulo32 bits; it does not set these script milestone flags."},
                                     "global_flag": {"native_vas": ["0x24a80", "0x27bb10"], "formula": "BE64 word5528 + (flag_id//64)*8, integer bit(flag_id%64)",
                                                     "store_vas": ["0x24aa8", "0x27bb38"], "meaning": "OR the named global event bit; separate from arena counter increment."},
                                     "milestone_flags": flags,
                                     "challenges": [{"enum": name, "native_id": identifier, "save_counter_offset": hex(0x56D8 + identifier * 4)} for name, identifier in CHALLENGES.items()]},
        "recommended_annotations": [
            {"va": "0x23ad0", "name": "TOD_ui_construct_runtime_operation_request", "kind": "function", "comment": "Stores runtime thread token/arguments and requested operation; arena bridge supplies operation 5. Not a saved record or recovered Lua list alias."},
            {"va": "0x24650", "name": "TOD_ui_dispatch_runtime_operation_loader", "kind": "function", "comment": "Guarded 8-entry relative switch: operation 5 → 24940 → constructed UI virtual loader 62D2E8. Table installation/ARENA_CHALLENGE_DATA alias remains unresolved."},
            {"va": "0x24714", "name": "TOD_ui_runtime_operation_switch", "kind": "data", "size": 32, "comment": "Eight signed BE32 offsets relative to 24714; entry 5 targets 24940. Runtime UI routing, not challenge IDs or source indices."},
        ],
        "unresolved": ["The requested script list's installation/alias as ARENA_CHALLENGE_DATA remains unresolved beyond the concrete UI loader.",
                       "Runtime request fields cannot be reconstructed from serialized milestone flags/counters.",
                       "Current trip/script/list/menu and callback acceptance cannot be inferred solely from saved predicate values.",
                       "Milestone call ordering is static source/bytecode evidence, not an atomic save snapshot or reconstructed engine wait timing."],
        "instruction_guards": [{"va": hex(address), "bytes": raw.hex().upper()} for address, raw in sorted(guards.items())],
    }
    if archive_path is not None:
        report["asset_observation"] = inspect_assets(archive_path)
    if save_path is not None:
        if Path(save_path).stat().st_size != 0x906F0:
            raise ValueError("Expected exact-length Tools of Destruction plaintext")
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Expected plaintext inventory IDs0..31")
        report["save_observation"] = {"size": len(raw), "plaintext_sha256": hashlib.sha256(raw).hexdigest().upper(),
                                      "milestone_flags": [{**flag, "set": bool(int.from_bytes(raw[int(flag["word_offset"], 0):int(flag["word_offset"], 0) + 8], "big") & (1 << flag["word_bit"]))} for flag in flags],
                                      "counters": [{"native_id": identifier, "offset": hex(0x56D8 + identifier * 4),
                                                    "raw_hex": raw[0x56D8 + identifier * 4:0x56DC + identifier * 4].hex().upper(),
                                                    "signed_value": struct.unpack_from(">i", raw, 0x56D8 + identifier * 4)[0]} for identifier in CHALLENGES.values()],
                                      "warning": "Independent saved bit/counter observations only; no current operation/script/menu or atomic transaction inferred."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.archive, args.save), indent=2))
