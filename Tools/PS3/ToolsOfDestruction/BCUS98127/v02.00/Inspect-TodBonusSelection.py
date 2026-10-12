"""Read-only cosmetic bonus selection evidence for exact USA v02.00 inputs.

Decodes native definitions and shipped pause-menu bytecode; never executes Lua
or game code. Editor eligibility is a conservative policy, not a gameplay test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BASE = Path(__file__).resolve().parent
BONUSES = runpy.run_path(str(BASE / "Inspect-TodBonuses.py"))
EFFECTS = runpy.run_path(str(BASE / "Inspect-TodBonusEffects.py"))
MENU = runpy.run_path(str(BASE / "Inspect-TodSettingsMenu.py"))
FUNCTIONS = {
    "changeCheatState": (0x110F26, 45, "CADF254680A71EB91B49818ABFE055A85A8E0C5A6F550949CB96DF4F418ACD64"),
    "handleSelect": (0x11103A, 4, "C0597D1B1201560E10F1622AF6AC18589B64E709E2235B7AB85D38EFA66904CD"),
    "handleRight": (0x1110AA, 4, "C0597D1B1201560E10F1622AF6AC18589B64E709E2235B7AB85D38EFA66904CD"),
    "handleLeft": (0x11111F, 4, "6B5D4044E51D5CCE7C3D63C8CCC4B7A1BEA7F2F4FAAA1175046672DC56CDDBB6"),
    "setListItemValue": (0x111350, 31, "5FA7794D4E3DA667F3CC119F2E4B31DB079A6967152529E10E0F239AD24D58B6"),
}
LABELS = {
    1: ("bonus_hero_head", "Hero head size", ["Off", "Large (2x)", "Extra large (4x)", "Small (0.5x)"]),
    3: ("bonus_enemy_head", "Enemy head size", ["Off", "Large (2.5x)", "Small (0.5x)"]),
    5: ("bonus_commentary", "Developer commentary request", ["Off", "On (supported language only)"]),
    9: ("bonus_james_zurkon", "James Zurkon bonus", ["Off", "On"]),
    11: ("bonus_mirror", "Mirror mode", ["Off", "On"]),
}


def cycle_preview(state, count, delta, unlocked):
    """Detached menu arithmetic only, including existing unknown byte values."""
    if type(state) is not int or not 0 <= state <= 255 or type(count) is not int or not 1 <= count <= 8:
        raise ValueError("Expected bounded raw state and definition count")
    if type(delta) is not int or delta not in (-1, 1) or type(unlocked) is not bool:
        raise ValueError("Expected left/right delta and explicit availability")
    if not unlocked:
        return state
    value = state + delta
    return 0 if value >= count else count - 1 if value < 0 else value


def inspect_asset_bytes(raw):
    if len(raw) != MENU["ASSET_SIZE"] or hashlib.sha256(raw).hexdigest().upper() != MENU["ASSET_HASH"]:
        raise ValueError("Bonus selection requires the exact USA pause asset")
    reader = MENU["LUA"].Reader(raw, 0x110642)
    root = reader.function()
    if root["source"] != "cheatHandler" or reader.pos != 0x111D15:
        raise ValueError("Unexpected cheatHandler boundaries")
    selected, digests = {}, []
    for name, (offset, count, digest) in FUNCTIONS.items():
        matches = [f for f in root["children"] if f.get("assigned_name") == name]
        if len(matches) != 1:
            raise ValueError("Ambiguous bonus selection function")
        function = matches[0]
        if int(function["code_offset"], 0) != offset or len(function["instructions"]) != count or \
                hashlib.sha256(raw[offset:offset + count * 4]).hexdigest().upper() != digest:
            raise ValueError("Bonus selection bytecode changed")
        selected[name] = function
        digests.append({"function": name, "offset": hex(offset), "instruction_count": count, "sha256": digest})
    guards = []
    for name, pc, word in [
        ("changeCheatState", 0, "02000005"), ("changeCheatState", 2, "0301BF0D"),
        ("changeCheatState", 5, "00800954"), ("changeCheatState", 10, "0201004C"),
        ("changeCheatState", 15, "00018097"), ("changeCheatState", 20, "05000181"),
        ("changeCheatState", 23, "00014016"), ("changeCheatState", 32, "0502BF0D"),
        ("changeCheatState", 39, "03018059"), ("handleSelect", 1, "03000041"),
        ("handleRight", 1, "03000041"), ("handleLeft", 1, "03000081"),
        ("setListItemValue", 15, "040001C5"), ("setListItemValue", 19, "06010019")]:
        instruction = selected[name]["instructions"][pc]
        if instruction["word"] != word:
            raise ValueError("Bonus selection relationship changed")
        offset = int(instruction["offset"], 0)
        guards.append({"function": name, "pc": pc, "offset": hex(offset), "word": word,
                       "bytes": raw[offset:offset + 4].hex().upper()})
    return {
        "confidence": "asset-backed",
        "asset": {"archive_entry": MENU["ASSET"], "size": len(raw), "sha256": MENU["ASSET_HASH"],
                  "source": "cheatHandler", "chunk_offset": "0x110642", "chunk_end_exclusive": "0x111d15"},
        "selection": "Lua row is one-based; every bonus API receives currentlySelected-1. changeCheatState first calls is_cheat_unlocked; failure bypasses all state writes and list-value refresh.",
        "cycling": "Select/right request +1; left requests -1. The candidate is raw getter state+delta. Candidate>=get_num_cheat_states writes0; candidate<0 writes count-1; otherwise it writes the candidate. Thus definition state_count INCLUDES off/index0; it is not the maximum valid state index. This is ordered branching, not modulo arithmetic for malformed states.",
        "display": "setListItemValue passes get_cheat_state(row-1) directly as the zero-based state argument to get_cheat_state_name(row-1,state). Labels remain localization lookup IDs; editor descriptions summarize guarded native effects.",
        "scope": "Menu APIs apply runtime-language remapping. No language value or menu row for physical ID11 is inferred from a save. No Lua execution or in-game effect/acceptance test.",
        "bytecode_digests": digests, "asset_byte_guards": guards,
    }


def inspect(elf_path, save_path=None, archive_path=None):
    native = BONUSES["inspect"](elf_path)
    effects = EFFECTS["inspect"](elf_path)
    elf = EFFECTS["BINDINGS"].Elf(elf_path)
    guards = {}
    for va, expected in {
        0x35CA40: 0x54653032, 0x35CA48: 0x54662036, 0x35CA58: 0x8069000C,
        0x24F34: 0x2F830001, 0x24F38: 0x2F1F0004, 0x24F48: 0x281F000D,
        0x24F78: 0x3BFF0001, 0x2702C: 0x57BD063E, 0x2703C: 0x28800007,
        0x27048: 0x281F000D, 0x2706C: 0x99630008,
        0x27A650: 0x2B800007, 0x27A670: 0x98090008,
        0x35BD1C: 0x80090008, 0x35BD24: 0x2F800000, 0x35BDE8: 0x409E0018,
        0x35BDF4: 0x88648701, 0x35BDF8: 0x2C030000, 0x35BDFC: 0x4182007C,
        0x35BE00: 0x386000C3, 0x35BE08: 0x38800657, 0x35BE14: 0x4BEF4DE5,
        0x35BE78: 0x38800311, 0x35BE88: 0x3860004B, 0x35BE8C: 0x4BEF4D6D,
    }.items():
        if elf.u32(va) != expected:
            raise ValueError(f"Bonus selection native evidence changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    for start in (0x24F18, 0x27008, 0x27A648, 0x35CA40):
        guards[start] = elf.read(start, elf.functions[elf.functions.index(start) + 1] - start)
    toc = elf.descriptors[0x35BC40]
    factory_values = {}
    for displacement, expected in ((0x19AC, 0x101EFB08), (0x19B8, 0x101EFB20),
                                   (0x19BC, 0x3F400000), (0x19C0, 0x3FC00000)):
        address = toc + displacement
        if elf.u32(address) != expected:
            raise ValueError("Zurkon factory pointer/argument evidence changed")
        guards[address] = elf.read(address, 4)
        factory_values[displacement] = address
    catalog = []
    for item in native["cheats"]["catalog"]:
        if item["id"] not in LABELS:
            continue
        key, label, labels = LABELS[item["id"]]
        effect = next(e for e in effects["effects"] if e["id"] == item["id"])
        consumer_requirement = effect["weighted_score_requirement"]
        if item["state_count"] != len(labels) or (consumer_requirement is not None and
                item["score_requirement"] != consumer_requirement):
            raise ValueError("Bonus definition and consumer bounds disagree")
        if item["id"] == 5 and (item["score_requirement"] != 200 or item["state_offset"] != "0x86fd"):
            raise ValueError("Commentary physical definition changed")
        if item["id"] == 9 and (item["score_requirement"] != 400 or item["state_offset"] != "0x8701"):
            raise ValueError("Zurkon physical definition changed")
        address = int(item["definition_va"], 0)
        guards[address] = elf.read(address, 0x30)
        catalog.append({"id": item["id"], "key": key, "label": label, "enum": item["enum"],
                        "state_offset": item["state_offset"], "score_requirement": item["score_requirement"],
                        "state_count_including_off": item["state_count"], "consumer_vas": effect["consumer_vas"],
                        "options": [{"value": value, "label": text} for value, text in enumerate(labels)]})
    report = {
        "confidence": "code-backed-physical-bonus-selection-policy",
        "report_tool": "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodBonusSelection.py",
        "score_offset": "0x8708", "catalog": catalog,
        "commentary_request": {
            "consumer_va": "0x3baa38", "state_offset": "0x86fd", "score_requirement": 200,
            "state_count_including_off": 2, "required_runtime_language_id": 1,
            "language_getter_chain": ["0x251e08", "0x5bfe08"],
            "native_guard_section": "bonus_effects",
            "rule": "Canonical saved Off/On request only, with existing score>=200. Native dispatch additionally requires runtime language ID1; the language getter and dispatch blocks are guarded by bonus_effects. No language field is stored or changed by this edit.",
            "scope": "Runtime language is an applicability gate, not the validity of the physical saved0/1 request. On does not guarantee supported language, active commentary, clip identity or audio playback. ID1 is not assigned a guessed localized language name."},
        "zurkon_factory_choice": {
            "consumer_va": "0x35bc40", "state_offset": "0x8701", "definition_va": "0x10026534",
            "definition_score_requirement": 400, "state_count_including_off": 2,
            "local_consumer_score_gate": False, "runtime_override_va": "0x101efb10",
            "rule": "Nonzero runtime override101EFB10 OR nonzero saved byte8701 selects the alternate factory branch. Both zero select the default branch. The definition/editor requires score>=400, but this consumer has no local score comparison.",
            "alternate": {"factory_arguments": [195, 1623], "float_argument": 0.75,
                          "float_slot_va": hex(factory_values[0x19BC])},
            "default": {"factory_arguments": [75, 785], "float_argument": 1.5,
                        "float_slot_va": hex(factory_values[0x19C0])},
            "factory_call_va": "0x250bf8",
            "scope": "Factory IDs and floating argument meaning are not recovered localized assets or a proved scale. Off clears only the saved request; it cannot override runtime101EFB10. No ammo, ownership, actor or override writes."},
        "setter_scope": "27008 menu setter remaps IDs>4 when language!=1, bounds physical ID<=13 and truncates supplied state to low8; accepts1..8 or stores0. Raw physical leaf27A648 accepts1..8 or0 without a local ID bound. Neither validates per-definition state_count or score. Editor never invokes either setter.",
        "edit_policy": "Offer only physical IDs1,3,5,9,11 when existing unsigned score8708 meets their definition requirement and raw byte is in0..state_count-1. IDs1/3/5/11 also have direct consumer score gates; ID9 does not locally test score. ID5 edits only a saved request; runtime language ID1 is additionally required for dispatch, not inferred or changed here. Write exactly one selected byte; preserve all other bonus states, score, earned skill bits and unknown neighbors. Unrecognized states or insufficient score remain read-only. Never grant points/unlocks or use language-remapped menu IDs as save offsets.",
        "warning": "Exact USA v02.00 reference. Off means no requested bonus, not an explicit head-transform restoration. Zurkon Off clears the saved request but cannot override runtime101EFB10. Mirror geometry/input axis and current runtime applicability are unconfirmed. Labels describe native basis factors or exported bonus identifiers, not recovered localized menu text. File-edit policy and software round trips do not prove in-game acceptance.",
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())],
    }
    if archive_path is not None:
        archive = MENU["PSARC"].Psarc(archive_path)
        matches = [i for i, name in enumerate(archive.names) if name == MENU["ASSET"]]
        if len(matches) != 1:
            raise ValueError("Exact pause asset missing or ambiguous")
        report["asset_observation"] = inspect_asset_bytes(archive.read_entry(matches[0], MENU["ASSET_SIZE"]))
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
            raise ValueError("Expected verified plaintext layout")
        score = struct.unpack_from(">I", data, 0x8708)[0]
        report["save_observation"] = {"sha256": hashlib.sha256(data).hexdigest().upper(), "weighted_score": score,
            "selections": [{"id": item["id"], "raw_state": data[int(item["state_offset"], 0)],
                            "editor_eligible": score >= item["score_requirement"] and
                            data[int(item["state_offset"], 0)] < item["state_count_including_off"]} for item in catalog]}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save, args.archive), indent=2, allow_nan=False))
