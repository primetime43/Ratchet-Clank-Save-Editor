"""Exact-build blueprint selector producer and named compiled-script consumer.

Read-only: does not invoke actors, callbacks or Lua. A saved level/destination
selector is not necessarily the currently loaded planet during transitions.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BASE = Path(__file__).resolve().parent
BINDINGS = runpy.run_path(str(BASE / "Inspect-TodWeaponBindings.py"))
PROGRESSION = runpy.run_path(str(BASE / "Inspect-TodProgression.py"))
ROOT = BINDINGS["ROOT"]
CONSUMER = "/built/levels/stratus city/scripts/traversal.lc"
CONSUMER_SHA = "ECEED55B969A5D33D8FBD4A84646BCB51A801123B0250374604D6270D598F368"
APIS = ("hero_get_blueprints", "hero_has_blueprint", "hero_give_blueprint",
        "hero_give_all_blueprints", "get_num_blueprints", "has_blueprint")


def uint(value):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("Expected unsigned32-bit raw word")
    return value


def selector_bit_preview(mask, saved_selector):
    """Independent raw slw/OR/check model, not execution or pickup validation."""
    mask, saved_selector = uint(mask), uint(saved_selector)
    shift = saved_selector & 63
    bit = 1 << shift if shift < 32 else 0
    return {"saved_selector": saved_selector, "effective_shift": shift,
            "effective_bit": f"0x{bit:08X}", "already_present": bool(mask & bit),
            "after_reached_grant": f"0x{mask | bit:08X}",
            "scope": "Raw sampled operands only; no callback invocation, placement or collection history inferred."}


def prototypes(root):
    yield root
    for child in root["children"]:
        yield from prototypes(child)


def consumer_guard(raw, root):
    """Validate exact bytes and independently decoded named argument/call/gate."""
    if len(raw) != 4515 or hashlib.sha256(raw).hexdigest().upper() != CONSUMER_SHA:
        raise ValueError("Selected blueprint consumer asset changed")
    rows = root["instructions"]
    expected = [
        (13, "GETGLOBAL", 0, "hero_has_blueprint", "00000185"),
        (14, "GETGLOBAL", 1, "Ratchet1", "010001C5"),
        (15, "GETGLOBAL", 2, "LEVEL_STRATUS_CITY", "02000205"),
        (16, "CALL", 0, None, "00018099"),
        (17, "TEST", 0, None, "00000018"),
        (18, "JMP", 0, None, "00800494"),
    ]
    if root["path"] != "root" or int(root["code_offset"], 0) != 0xA57 or len(rows) <= 18:
        raise ValueError("Selected blueprint consumer prototype changed")
    for pc, op, a, constant, word in expected:
        row = rows[pc]
        offset = 0xA57 + pc * 4
        if (row["pc"], row["op"], row["a"], row.get("constant"), row["word"],
                int(row["offset"], 0)) != (pc, op, a, constant, word, offset):
            raise ValueError("Selected blueprint consumer instruction changed")
        # Compiled Lua instruction words are stored little-endian in this build.
        if int.from_bytes(raw[offset:offset + 4], "little") != int(word, 16):
            raise ValueError("Selected blueprint consumer raw instruction changed")
    if (rows[16]["b"], rows[16]["c"], rows[17]["b"], rows[17]["c"],
            rows[18]["jump_pc"]) != (3, 2, 0, 0, 38):
        raise ValueError("Selected blueprint consumer argument/test/branch changed")
    return {"asset": CONSUMER, "prototype": "root", "getglobal_pc": 13,
            "argument_pc": 15, "call_pc": 16, "test_pc": 17,
            "branch_pc": 18, "branch_target_pc": 38,
            "argument": "LEVEL_STRATUS_CITY", "level_id": 2,
            "guard": {"offset": "0xa8b", "bytes": raw[0xA8B:0xAA3].hex().upper()},
            "semantics": "Reached adjacent bytecode calls hero_has_blueprint(Ratchet1, LEVEL_STRATUS_CITY), then TEST/JMP gates the following block. The global argument is native enum 2, hence saved blueprint bit 2. This is a consumer, not proof this script grants or places a pickup.",
            "confidence_limit": "Syntactic operands and selected branch are confirmed; enclosing thread execution, actor validity and in-game history are not observed."}


def inspect_assets(archive_path):
    psarc = runpy.run_path(str(ROOT / "Tools/Inspect-Psarc.py"))["Psarc"]
    reader_class = runpy.run_path(str(ROOT / "Tools/Inspect-Lua50.py"))["Reader"]
    archive = psarc(Path(archive_path))
    source_rows, hits, selected = [], [], None
    scripts = [(i, n) for i, n in enumerate(archive.names) if n and n.endswith(".lc")]
    if len(scripts) > 1024 or len(archive.entries) > 10000:
        raise ValueError("Blueprint compiled-asset survey exceeds bounded catalog")
    for index, name in scripts:
        raw = archive.read_entry(index, 1024 * 1024)
        digest = hashlib.sha256(raw).hexdigest().upper()
        source_rows.append({"asset": name, "size": len(raw), "sha256": digest})
        if not any(api.encode("ascii") in raw for api in APIS):
            continue
        reader = reader_class(raw)
        root = reader.function()
        if reader.pos != len(raw):
            raise ValueError("Unconsumed blueprint compiled-script bytes")
        for node in prototypes(root):
            for row in node["instructions"]:
                if row["op"] == "GETGLOBAL" and row.get("constant") in APIS:
                    hits.append({"asset": name, "prototype": node["path"], "pc": row["pc"],
                                 "api": row["constant"], "word": row["word"]})
        if name == CONSUMER:
            if selected is not None:
                raise ValueError("Selected blueprint consumer asset is ambiguous")
            selected = consumer_guard(raw, root)
    if selected is None:
        raise ValueError("Selected blueprint consumer asset missing")
    used = {hit["asset"] for hit in hits}
    return {"archive_entry_count": len(archive.entries), "compiled_script_count": len(scripts),
            "source_catalog_sha256": hashlib.sha256(json.dumps(source_rows, sort_keys=True,
                separators=(",", ":")).encode("utf-8")).hexdigest().upper(),
            "api_getglobal_count": len(hits), "api_getglobals": hits,
            "source_fingerprints": [row for row in source_rows if row["asset"] in used],
            "selected_consumer": selected,
            "survey_limit": "Bounded direct GETGLOBAL operands in global_cached .lc only. Zero direct grant GETGLOBAL occurrences do not exclude aliases, indirect calls, native callbacks or other archives. No script executed; no placement identity inferred from an object symbol."}


def inspect(elf_path, save_path=None, archive_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}

    def keep(va, n):
        guards[va] = elf.read(va, n)

    words = {
        0x303234: 0x80C20104, 0x303238: 0x38A00001,
        0x30323C: 0x3D660001, 0x303240: 0x7CA91830,
        0x303244: 0x808B86F4, 0x303248: 0x7C834B78,
        0x30324C: 0x906B86F4, 0x3032D4: 0x80C20104,
        0x3032D8: 0x3CA60001, 0x3032DC: 0x38800001,
        0x3032E0: 0x7C801830, 0x3032E8: 0x812586F4,
        0x3032EC: 0x7C0B4838, 0x3032F0: 0x2C0B0000,
        0x3032F4: 0x40820094, 0x2D1490: 0x8062F268,
        0x2D1494: 0x3D230009, 0x2D1498: 0x806906E8,
        0x8A0024: 0x101EFB20, 0x89F188: 0x101EFB20,
        0x27AFBC: 0x64830007, 0x27AFC0: 0x6060DEE4,
        0x84E3C8: 0x86DEC8, 0x84E40C: 0x86DEC0,
        0x86DEC0: 0x303220, 0x86DEC4: 0x89FF20,
        0x86DEC8: 0x303260, 0x86DECC: 0x89FF20,
        0x2BA4C0: 0x38800002, 0x2BA4E8: 0xFC20081E,
        0x2BA4F8: 0x80810080, 0x2BA5F0: 0x38800002,
        0x2BA618: 0xFC20081E, 0x2BA628: 0x80810080,
    }
    for va, expected in words.items():
        if elf.u32(va) != expected:
            raise ValueError(f"Blueprint producer evidence changed at {va:#x}")
        keep(va, 4)
    for va, target in {0x30322C: 0x2D1490, 0x3032CC: 0x2D1490,
            0x303368: 0x24F4F8, 0x30338C: 0x24F6D8,
            0x2BA4E0: 0x251C78, 0x2BA4FC: 0x27AF90,
            0x2BA610: 0x251C78, 0x2BA62C: 0x27A5D8}.items():
        if BINDINGS["branch_target"](elf.u32(va), va) != target or not elf.u32(va) & 1:
            raise ValueError(f"Blueprint producer call changed at {va:#x}")
        keep(va, 4)
    for function in (0x303220, 0x303260, 0x2D1490, 0x27AF90,
                     0x27AFB0, 0x27A5D8, 0x2BA3F8, 0x2BA520):
        if elf.descriptors[function] != 0x89FF20:
            raise ValueError("Blueprint producer descriptor TOC changed")
        keep(function, elf.functions[elf.functions.index(function) + 1] - function)
    enums = PROGRESSION["exports"](elf, 0x28440, "LEVEL_", 0x12990)
    if [row["id"] for row in enums] != list(range(20)) or enums[-1]["enum"] != "LEVEL_COUNT":
        raise ValueError("Native blueprint selector enum family changed")
    for row in enums:
        for key in ("name_slot_va", "name_load_va", "value_slot_va", "value_load_va", "value_move_va", "export_call_va"):
            keep(int(row[key], 0), 4)
        keep(int(row["name_va"], 0), len(row["enum"]) + 1)
    for slot, name, wrapper in ((0x89DF20, "hero_has_blueprint", 0x2BA520),
                               (0x89DF28, "hero_give_blueprint", 0x2BA3F8)):
        name_va, descriptor = struct.unpack(">II", elf.read(slot, 8))
        if elf.string(name_va) != name or elf.u32(descriptor) != wrapper:
            raise ValueError("Native named blueprint wrapper binding changed")
        keep(slot, 8)
        keep(descriptor, 8)
        keep(name_va, len(name) + 1)
    all_mask = ((elf.u32(0x27AFBC) & 65535) << 16) | (elf.u32(0x27AFC0) & 65535)
    rows = [{"bit_id": row["id"], "level_enum": row["enum"],
             "level_name_va": row["name_va"], "export_call_va": row["export_call_va"],
             "byte_offset": hex(0x86F4 + 3 - row["id"] // 8),
             "byte_mask": f"0x{1 << (row['id'] % 8):02X}"}
            for row in enums[:-1] if all_mask & (1 << row["id"])]
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA BCUS98127 v02.00 static evidence only. No actor execution, pickup coordinates/history, runtime planet equality, edit or in-game acceptance claim.",
        "selector_grant": {"grant_va": "0x303220", "selector_getter_va": "0x2d1490",
            "selector_save_offset": "0x906e8", "mask_save_offset": "0x86f4",
            "state_base_va": "0x101efb20", "grant_call_va": "0x30322c", "write_va": "0x30324c",
            "rule": "Reached 303220 obtains the saved level/destination selector through 2D1490 and ORs 1<<selector into 86F4. No other saved field is written by this leaf. Saved selector is not guaranteed to equal the currently loaded runtime planet during deferred transitions.",
            "dispatch_limit": "Descriptors 86DEC0/86DEC8 are stored in native table 84E40C/84E3C8. No direct branch caller of 303220 was recovered; table membership alone does not establish the event that dispatches this grant."},
        "paired_initializer": {"function_va": "0x303260", "selector_call_va": "0x3032cc",
            "mask_read_va": "0x3032e8", "test_branch_va": "0x3032f4",
            "rule": "After earlier initialization helpers, rereads the saved selector and tests the same selector-indexed bit. Present takes 303388 to 24F6D8(actor+14,0); absent can copy entry+30/+38 and call 24F4F8(actor+14,0) only after native generated-handle validation. Neither branch writes the saved blueprint mask.",
            "limits": "Alternate callback meanings, object name/class, dispatch trigger and physical location remain unresolved. Do not describe all actor initialization as collection."},
        "named_wrapper_argument": {"grant_wrapper_va": "0x2ba3f8", "predicate_wrapper_va": "0x2ba520",
            "grant_native_call_va": "0x2ba4fc", "predicate_native_call_va": "0x2ba62c",
            "rule": "On admitted wrapper arguments and a non-null handle, numeric script argument 2 is read via 251C78, converted with fctiwz and passed as r4 to individual grant/predicate. The grant wrapper does not substitute 2D1490 or require argument==saved selector. No general floating conversion model is supplied."},
        "level_index_associations": {"native_grant_all_mask": f"0x{all_mask:08X}", "count": len(rows),
            "rows": rows,
            "rule": "The inline producer demonstrably indexes by the saved LEVEL/destination selector; these 13 bit IDs are also native LEVEL enum values and native grant-all bits. This is a qualified selector/bit association, not thirteen recovered physical pickup coordinates or proof each world asset dispatches the grant.",
            "unknowns": "Which actor/table event invokes 303220, exact source-instance/UID/position bindings, collection chronology and whether all thirteen levels use this same producer are unresolved."},
        "recommended_annotations": [
            {"va": "0x303220", "kind": "function", "name": "TOD_blueprint_grant_saved_level_selector_bit_verified",
             "comment": "Reached leaf reads 2D1490 saved 906E8 level/destination selector; ORs the corresponding slw bit into 86F4. Saved selector need not equal the currently loaded planet; descriptor dispatch trigger and physical pickup remain unresolved."},
            {"va": "0x303260", "kind": "function", "name": "TOD_blueprint_actor_init_saved_selector_gate_verified",
             "comment": "After initialization helpers, rereads 2D1490 saved 906E8; an existing 86F4 bit takes 24F6D8(actor+14,0), absence can restore entry+30/+38 and call 24F4F8 after handle validation. No saved mask write; class, dispatch trigger and pickup location remain unresolved."}],
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())],
    }
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        mask, selector = (struct.unpack_from(">I", data, offset)[0] for offset in (0x86F4, 0x906E8))
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "blueprint_mask": f"0x{mask:08X}", "saved_level_destination_selector": selector,
            "native_popcount_all32": mask.bit_count(), "outside_grant_all_mask": f"0x{mask & ~all_mask:08X}",
            "level_bits": [{**row, "present": bool(mask & (1 << row["bit_id"]))} for row in rows],
            "sampled_selector_preview": selector_bit_preview(mask, selector),
            "limit": "Snapshot bytes only: no grant execution, actor identity, coordinate or acquisition history inferred."}
    if archive_path is not None:
        report["asset_observation"] = inspect_assets(archive_path)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save, args.archive), indent=2))
