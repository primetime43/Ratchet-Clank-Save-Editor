"""Read-only exact-build arena source-index/native-ID/display-row relationships.

Optional archive inspection parses fingerprinted shipped Lua metadata; it never
executes Lua, reconstructs the unresolved runtime challenge table, or edits saves.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import runpy
import struct
import sys

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
TOOLS = Path(__file__).resolve().parents[4]
ASSET = "/built/anark/arenachallenge/built.dat"
ASSET_SIZE = 103692
ASSET_HASH = "3DFD3B6231D06B1C7EE106BD521D263FC4D2B167B3D755280D70E635C38E1BF3"
CHUNK_OFFSET = 0x12A7A
FUNCTIONS = {
    "onInitialize": (0x134FC, 185, "67C35B5C40BB7471CCAC7625917C85AB9B9AE716A5BF179CD1CCE43BF83AEB09"),
    "onActivate": (0x13AB2, 56, "89431FD49157F82B37BCE22113E33E9D206D7F93E70C6636F059210EA7FA6E90"),
    "handleSelect": (0x13FD3, 35, "B9C4984A977732B4AB9F29028154BCD6314423D2B3931CF2A52D8E2EF8B3EBE3"),
    "getNumListItems": (0x14BC0, 14, "20D7740BAB95A7A14D4A3801898C1282965EC2251BCBD6FFAE6CF588E7487828"),
}
NATIVE_RANGES = [
    (0x275268, 0xD8, "ABFC23A4F1F2AC983ADB4E2AA657237A0A71C99AE4F7FEAAB92E4DC01333083F"),
    (0x275438, 0x170, "648E3D2E8DED94A47EAC67E6C276AC3A0AE0E8499BB137955D56F5B70450817B"),
    (0x2756F8, 0x150, "A2AAA14BC6BD3969C188BEE55855A4A49155C1921AACDB7CDC3D492A7F8D002C"),
    (0x279B8, 0x40, "E976891A0F734038A078071FD316936BDDE565F41C904ADF4A9E0BB69F7FC629"),
    (0x26298, 0x28, "3C25A28BD6C9F7AA2FA9046C00D4193FB1DF4ED2E2BD917F253995F4A453D450"),
    (0x26048, 0x40, "F6E6BF2861C531DDD583BB8B1F1A3546FEBBB253ED1AF5A81BB918547E777141"),
    (0x13B80, 0x10, "EBCC8F178FCB2F8FF86656BBC15B61A4F6D667C5E5C41C53951A562515D762CB"),
    (0x110B0, 0x10, "7C10191AC0B6765602712E62AB54F1260E89F727AE564F9A3515CD5C496A0A4F"),
    (0x11100, 0x10, "1522953BFF48EF66D82CFA278E5DC180A332F297FA9847FFD343791214A53971"),
    (0x315A8, 0x110, "7571A00BF13A32B0ECF26AB412C514360B8DF2B8E0ED81EF646F2CCAD1992FA3"),
    (0x31EF8, 0xE0, "2324C8F143A4C1806E187F6805518B57803C1875AC67591F438B81403F884A70"),
    (0x31408, 0xE0, "B04A89BB217FC368B22D9FB2AAF601E9472BC181570F5134723E72FD1FA446C7"),
]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def inspect_asset_bytes(raw):
    if len(raw) != ASSET_SIZE or hashlib.sha256(raw).hexdigest().upper() != ASSET_HASH:
        raise ValueError("Arena menu requires the exact USA v02.00 arena UI asset")
    lua = module("tod_arena_menu_lua", "Inspect-Lua50.py")
    reader = lua.Reader(raw, CHUNK_OFFSET)
    root = reader.function()
    if root["source"] != "ListUpdater" or reader.pos != 0x15B5C:
        raise ValueError("Unexpected arena ListUpdater boundaries")
    selected, digests = {}, []
    for name, (offset, count, digest) in FUNCTIONS.items():
        matches = [f for f in root["children"] if f.get("assigned_name") == name]
        if len(matches) != 1:
            raise ValueError("Ambiguous arena UI function")
        function = matches[0]
        if int(function["code_offset"], 0) != offset or len(function["instructions"]) != count or \
                hashlib.sha256(raw[offset:offset + count * 4]).hexdigest().upper() != digest:
            raise ValueError("Arena UI bytecode changed")
        selected[name] = function
        digests.append({"function": name, "offset": hex(offset), "instruction_count": count, "sha256": digest})

    def guard(name, pc, word):
        instruction = selected[name]["instructions"][pc]
        if instruction["word"] != word:
            raise ValueError("Arena UI relationship byteguard mismatch")
        offset = int(instruction["offset"], 0)
        return {"function": name, "pc": pc, "offset": hex(offset), "decoded_word": word,
                "bytes": raw[offset:offset + 4].hex().upper()}

    guards = [guard(name, pc, word) for name, pc, word in [
        ("onInitialize", 74, "020009C5"), ("onInitialize", 104, "05000D45"),
        ("onInitialize", 106, "05010099"), ("onInitialize", 116, "049A0049"),
        ("onInitialize", 118, "009A8156"), ("onInitialize", 122, "060047C6"),
        ("onInitialize", 128, "06004786"), ("onInitialize", 131, "017FF29C"),
        ("onInitialize", 137, "03004786"), ("onInitialize", 148, "017FFE1C"),
        ("onInitialize", 152, "030047C6"), ("onInitialize", 163, "017FFE1C"),
        ("onActivate", 29, "04024286"), ("onActivate", 48, "04024286"),
        ("handleSelect", 4, "0100BF46"), ("handleSelect", 5, "01008018"),
        ("handleSelect", 27, "02014046"), ("handleSelect", 28, "01010059"),
        ("getNumListItems", 10, "01000105"), ("getNumListItems", 11, "0100801A"),
    ]]
    return {
        "confidence": "asset-backed",
        "asset": {"archive_entry": ASSET, "size": ASSET_SIZE, "sha256": ASSET_HASH,
                  "chunk_offset": hex(CHUNK_OFFSET), "chunk_end_exclusive": hex(reader.pos),
                  "source": root["source"], "bytecode_endianness": "little"},
        "initializer": {
            "source_indices": "Enumerate integer source indices1 through get_num_challenges(), inclusive.",
            "preserved_index_field": "chalNum",
            "completion_test": "get_times_challenge_completed(source_index) > 0",
            "display_order": "Stable partition: non-positive signed completion counts first, positive counts second; source order is preserved within each partition.",
            "inactive_rows": "isActive is recorded but does not filter either partition.",
            "negative_count_caveat": "A negative signed count joins the non-positive partition; this is not proof that an unsigned saved counter is zero.",
        },
        "selection": {
            "select": "handleSelect indexes challengeArray by current display row, requires its isActive field, then calls select_challenge(row.chalNum).",
            "default": "onActivate finds the display row whose chalNum equals get_default_challenge(), then selects that display row.",
            "image": "onActivate calls get_challenge_image(row.chalNum), not get_challenge_image(display_row).",
            "list_count": "getNumListItems returns get_num_challenges(); it does not count native counter slots.",
        },
        "warning": "Static shipped bytecode evidence only; no Lua execution or reconstruction of the current runtime challenge table/menu.",
        "bytecode_digests": digests, "asset_byte_guards": guards,
    }


def inspect_archive(archive_path):
    psarc = module("tod_arena_menu_psarc", "Inspect-Psarc.py")
    archive = psarc.Psarc(archive_path)
    matches = [i for i, name in enumerate(archive.names) if name == ASSET]
    if len(matches) != 1:
        raise ValueError("Exact arena menu asset is missing or ambiguous")
    return inspect_asset_bytes(archive.read_entry(matches[0], ASSET_SIZE))


def inspect(elf_path, archive_path=None, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    for address, size, digest in NATIVE_RANGES:
        if hashlib.sha256(elf.read(address, size)).hexdigest().upper() != digest:
            raise ValueError(f"Arena native guard changed at {address:#x}")
        keep(address, size)
    bindings = []
    for slot, name, wrapper in [(0x8893FC, "get_num_challenges", 0x31EF8),
                                (0x88944C, "get_times_challenge_completed", 0x315A8),
                                (0x88945C, "get_default_challenge", 0x31408)]:
        pointer, descriptor = struct.unpack(">II", elf.read(slot, 8))
        if elf.string(pointer) != name or elf.u32(descriptor) != wrapper:
            raise ValueError("Arena named binding changed")
        keep(slot, 8)
        keep(descriptor, 8)
        keep(pointer, len(name) + 1)
        bindings.append({"name": name, "registration_slot_va": hex(slot),
                         "name_va": hex(pointer), "wrapper_va": hex(wrapper)})
    keys = []
    for slot, value in [(0x898EC0, "ARENA_CHALLENGE_DATA"), (0x898EC4, "num"),
                        (0x898ECC, "id")]:
        pointer = elf.u32(slot)
        if elf.string(pointer) != value:
            raise ValueError("Arena table key changed")
        keep(slot, 4)
        keep(pointer, len(value) + 1)
        keys.append({"key": value, "pointer_slot_va": hex(slot), "string_va": hex(pointer)})
    for slot, pointer in [(0x888624, 0x101EFB20), (0x888628, 0x101AEFF8),
                          (0x898EB8, 0x101E8190), (0x898EBC, 0x101E8198)]:
        if elf.u32(slot) != pointer:
            raise ValueError("Arena state pointer changed")
        keep(slot, 4)
    report = {
        "confidence": "native-confirmed",
        "binary_sha256": hashlib.sha256(elf.raw).hexdigest().upper(),
        "index_spaces": [
            {"name": "source_index", "meaning": "One-based Lua ARENA_CHALLENGE_DATA integer key; passed to menu APIs and stored as shipped UI row.chalNum."},
            {"name": "native_id", "meaning": "Integer .id resolved from the source table row; exported IFF IDs and direct-ID saved counters use this space."},
            {"name": "display_row", "meaning": "One-based current position in the shipped UI challengeArray; completion-count partition can change it."},
        ],
        "count_getter": {"wrapper_va": "0x31ef8", "chain": ["0x31ef8", "0x26298", "0x13b80", "0x275268"],
                         "function_va": "0x275268", "table_key": "num",
                         "meaning": "Returns ARENA_CHALLENGE_DATA.num converted to signed32 by fctiwz (truncation toward zero). Neither a literal23 nor a raw Lua table length."},
        "id_resolver": {"function_va": "0x2756f8", "lua_context_owner_pointer_slot_va": "0x898eb8",
                        "lua_state_owner_offset": "0x4", "lookup": "ARENA_CHALLENGE_DATA[source_index].id",
                        "missing_row_result": 0,
                        "conversion": "Table .id is converted with fctidz; the subsequent subfic/srawi/and/add expression caps ordinary nonnegative IDs at23. There is no lower-bound/source-index validity check.",
                        "counter_consumer_va": "0x279b8", "counter_formula": "saved56D8 + 4*native_id",
                        "count_signedness": "lwz followed by extsw: returned completion count is signed32.",
                        "bounds_warning": "The save has23 counter slots (IDs0..22). ID23 addresses5734, the next independently mapped reset-category word. Do not treat the resolver's cap as a safe counter bound; extreme conversion values are not validated here."},
        "default_selection": {"chain": ["0x31408", "0x26048", "0x11100", "0x275438"],
                              "runtime_object_pointer_slot_va": "0x888628", "runtime_native_id_offset": "0xd8",
                              "inverse_lookup_va": "0x275438",
                              "meaning": "Scan contiguous Lua source rows from1; compare each truncated .id with runtime object+D8. Return the first matching source index; stop at the first non-table and return-1. Caller26048 maps a negative result to0.",
                              "warning": "Runtime object+D8 is not assigned a saved-file offset here. The inverse scan does not use table.num as its bound."},
        "bindings": bindings, "table_keys": keys,
        "recommended_annotations": [
            {"va": "0x275268", "name": "ArenaMenu_GetSourceCountFromLuaNum"},
            {"va": "0x275438", "name": "ArenaMenu_FindSourceIndexByNativeId"},
            {"va": "0x2756f8", "name": "ArenaMenu_ResolveSourceIndexToNativeId"},
        ],
        "unresolved": [
            "The current runtime ARENA_CHALLENGE_DATA initialization, source-index-to-ID values, num and labels are not recovered.",
            "Exported IDs1..22 do not prove source indices1..22 have the same order or that every exported ID is a current menu row.",
            "A saved counter snapshot alone cannot reconstruct menu display order without the runtime source-index-to-ID table.",
            "No in-game acceptance or new safe-edit claim follows from this read-only inspection.",
        ],
        "instruction_guards": [{"va": hex(address), "bytes": raw.hex().upper()} for address, raw in sorted(guards.items())],
    }
    if archive_path is not None:
        report["asset_observation"] = inspect_archive(archive_path)
    if save_path is not None:
        if Path(save_path).stat().st_size != 0x906F0:
            raise ValueError("Expected the exact-length Tools of Destruction plaintext save")
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Expected plaintext inventory IDs0..31, not an encrypted or incompatible save")
        report["snapshot"] = {
            "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest().upper(),
            "counter_start": "0x56d8", "counter_end_exclusive": "0x5734",
            "signed_counts_by_native_id": list(struct.unpack(">23i", raw[0x56D8:0x5734])),
            "adjacent_reset_category0_raw": raw[0x5734:0x5738].hex().upper(),
            "warning": "Native-ID observations only; no current source-index or display-row assignment.",
        }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.archive, args.save), indent=2))
