"""Read-only arena research: exact ELF, fingerprinted shipped definitions, plaintext observations."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import runpy
import struct

PROGRESSION = runpy.run_path(str(Path(__file__).with_name("Inspect-TodProgression.py")))
BINDINGS = PROGRESSION["BINDINGS"]
ASSETS = {
    "arena.csv": "EB806E8146747AD448EEE69F11B71E83A511102A0558E583E3AAA56797C3C002",
    "arena.lua": "4E41A9B5C0A97B7BE70500EF82487030807919E81F5B37EC89996F8919539054",
    "arena.lc": "65F93FF2771F2EE9CEAF06CB418911E35FA34FC9B3C8641B02529B4CA2E903D3",
}
PROPERTIES = [
    ("IsBoss", 0x00, "u8", 0xB6AE0, 0xB6A00),
    ("Time", 0x04, "f32", 0xA8BA0, 0x9A148),
    ("Weapon", 0x08, "i32", 0xA8AE8, 0x9A078),
    ("BoltReward", 0x0C, "u32", 0xA8A18, 0x99FA0),
    ("WpnReward", 0x10, "i32", 0xA8960, 0x99ED0),
    ("ImageName", 0x14, "bytes32", 0xB6800, 0xB64C8),
]


def inspect(elf_path, assets_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)  # Refuse any other build before reading addresses.
    guards, bindings = {}, []

    def keep(address, size):
        guards[address] = elf.read(address, size)

    def function(address):
        end = elf.functions[elf.functions.index(address) + 1]
        keep(address, end - address)
        return list(elf.instructions(address, end))

    def expect(address, word):
        if elf.u32(address) != word:
            raise ValueError(f"Arena instruction/pointer changed at {address:#x}")
        keep(address, 4)

    # Direct-ID getter, success stores and initializer independently establish bounds.
    for address, word in {
        0x27A958: 0x2B830016, 0x27A994: 0x57EA103A,
        0x27A998: 0x80E29030, 0x27A9A0: 0x390A56D0,
        0x27A9B8: 0x80650008, 0x27A9BC: 0x7C6307B4,
        0x898F50: 0x101EFB20, 0x35D9AC: 0x39200017,
        0x35D9F4: 0x914301B0, 0x35D9FC: 0x38C00008,
        0x35DA1C: 0x9007020C, 0xB706C: 0x1D5D0034,
        0xB7070: 0x3D0A0001, 0xB7078: 0x38C7177C,
        0x899074: 0x101B9EE8, 0x89F0D4: 0x101EFB20,
        0x89F0BC: 0x101B9EE8,
        0xB6B24: 0x88890000, 0xA8BE4: 0xC0290004,
        0xA8B2C: 0x80E80008, 0xA8A5C: 0x80A9000C,
        0xA89A4: 0x80E80010, 0xB683C: 0x38BE0014,
        0xB6558: 0x38A0001F, 0xB6560: 0x387E0014,
    }.items():
        expect(address, word)
    base = (elf.u32(0x27A9A0) & 65535) + (elf.u32(0x27A9B8) & 65535)
    count = (elf.u32(0x27A958) & 65535) + 1
    if base != 0x56D8 or count != (elf.u32(0x35D9AC) & 65535):
        raise ValueError("Arena initializer/getter disagree")

    for slot, native in ((0x89D8DC, 0x278DB0), (0x89D8E4, 0x27A9C8),
                         (0x89D8EC, 0x278D48), (0x89D8F4, 0x27A958)):
        pointer, descriptor = struct.unpack(">II", elf.read(slot, 8))
        name, wrapper = elf.string(pointer), elf.u32(descriptor)
        instructions = function(wrapper)
        if not any(word >> 26 == 18 and word & 1 and
                   BINDINGS.branch_target(word, address) == native for address, word in instructions):
            raise ValueError("Named arena wrapper no longer calls native")
        keep(slot, 8)
        keep(descriptor, 8)
        keep(pointer, len(name) + 1)
        function(native)
        bindings.append({"name": name, "name_va": hex(pointer), "registration_slot_va": hex(slot),
                         "wrapper_va": hex(wrapper), "native_va": hex(native)})

    enums = PROGRESSION["exports"](elf, 0x294E90, "IFF_", 0x252EB8)
    sentinels = PROGRESSION["exports"](elf, 0x294E90, "ARENA_CHALLENGE_", 0x252EB8)
    if [e["id"] for e in enums] != list(range(1, count)) or [e["id"] for e in sentinels] != [0, 23]:
        raise ValueError("Incomplete arena enum catalog")
    for item in enums + sentinels:
        keep(int(item["name_va"], 0), len(item["enum"]) + 1)
        for key in ("name_slot_va", "name_load_va", "value_slot_va", "value_load_va", "value_move_va", "export_call_va"):
            keep(int(item[key], 0), 4)

    assets = {}
    for name, digest in ASSETS.items():
        raw = (Path(assets_path) / name).read_bytes()
        if hashlib.sha256(raw).hexdigest().upper() != digest:
            raise ValueError(f"Asset SHA-256 mismatch: {name}")
        assets[name] = raw
    # Parse data only. Never execute shipped Lua or CSV expressions.
    records, header = {}, False
    weapons = {e["enum"]: e["id"] for e in BINDINGS.enum_exports(elf)}
    for cells in csv.reader(io.StringIO(assets["arena.csv"].decode("ascii"))):
        cells = [c.strip() for c in cells]
        if cells[:8] == ["ID", "Comment", "IsBoss", "Time", "Weapon", "BoltReward", "WpnReward", "ImageName"]:
            header = True
            continue
        if not header or not cells or not cells[0]:
            continue
        if len(cells) < 8 or cells[0] in records or cells[2] not in ("TRUE", "FALSE"):
            raise ValueError("Unexpected arena CSV row")
        for i in (3, 5):
            if cells[i] and not cells[i].isdigit():
                raise ValueError("Not a numeric arena literal")
        for i in (4, 6):
            if cells[i] and cells[i] not in weapons:
                raise ValueError("Unknown native weapon enum")
        records[cells[0]] = {"comment": cells[1], "is_boss": cells[2] == "TRUE",
            "time_seconds": int(cells[3]) if cells[3] else None,
            "weapon_restriction": cells[4] or None, "weapon_restriction_id": weapons.get(cells[4]),
            "base_bolts": int(cells[5]) if cells[5] else None,
            "weapon_reward": cells[6] or None, "weapon_reward_id": weapons.get(cells[6]), "image_name": cells[7]}
    if set(records) != {e["enum"] for e in enums}:
        raise ValueError("CSV and native challenge catalog disagree")

    properties = []
    for index, (name, offset, kind, getter, setter) in enumerate(PROPERTIES):
        slot = 0x88FA5C + index * 12
        pointer, get_descriptor, set_descriptor = struct.unpack(">III", elf.read(slot, 12))
        if elf.string(pointer) != name or elf.u32(get_descriptor) != getter or elf.u32(set_descriptor) != setter:
            raise ValueError("Arena native property registration changed")
        keep(slot, 12)
        keep(pointer, len(name) + 1)
        keep(get_descriptor, 8)
        keep(set_descriptor, 8)
        function(getter)
        function(setter)
        properties.append({"name": name, "offset": hex(offset), "type": kind,
            "registration_va": hex(slot), "name_va": hex(pointer), "getter_va": hex(getter), "setter_va": hex(setter)})
    for address in (0x35D9A0, 0x2CEAB0, 0x2D1860, 0xB6FA8, 0x2756F8, 0x279B8, 0x315A8):
        function(address)
    keep(0x8BD98, 0xCC)  # ArenaConfig registration portion, not unrelated class registrations.
    for slot in (0x898FE4, 0x898FE8, 0x898EC0, 0x898ECC):
        keep(slot, 4)
    keep(0x10019CA0, len("ARENA_CHALLENGE_DATA") + 1)
    keep(0x10019CD0, 3)
    constants = []
    for slot, expected in ((0x89F0D8, 0x3EA8F5C3), (0x89F0DC, 0x41C80000),
                           (0x89F0E0, 0x42480000), (0x89F0E4, 0x3DCCCCCD)):
        expect(slot, expected)
        constants.append({"va": hex(slot), "bits": f"{expected:08X}", "float": struct.unpack(">f", elf.read(slot, 4))[0]})
    report = {"confidence": "code-backed", "warning": "Exact USA v02.00 static code and shipped definitions; not gameplay-tested editing permissions or localized titles.",
        "storage": {"base": hex(base), "stride": 4, "count": count, "end_exclusive": hex(base + count * 4),
            "getter_va": "0x27a958", "initializer_va": "0x35d9a0", "semantics": "BE32 counters; direct getter sign-extends. Success increments modulo32 bits. ID0 is INVALID, not a playable challenge. No cap or repair inferred.",
            "following_category_counts": {"base": "0x5734", "words": 8, "end_exclusive": "0x5754", "meaning": "Separate reset-event category counters; reset_categories guards the runtime selectors and increment path. Not a24th challenge or per-challenge failure array."}},
        "catalog": [{**e, "save_offset": hex(base + 4 * e["id"]), "shipped": records[e["enum"]]} for e in enums],
        "sentinels": sentinels, "assets": [{"name": name, "sha256": digest, "size": len(assets[name])} for name, digest in ASSETS.items()],
        "configuration": {"class": "ArenaConfig", "parent_offset": "0x1177c", "stride": "0x34", "native_indexer_va": "0xb6fa8", "properties": properties,
            "warning": "Runtime configuration, not saved records. CSV Comment is not parsed by arena.lua. Blank fields remain unspecified, not guessed defaults. ImageName has32-byte storage and a31-byte copy bound; termination and bytes1..3 remain unconfirmed."},
        "transactions": {"start_va": "0x278db0", "failure_va": "0x278d48", "success_va": "0x27a9c8", "reward_va": "0x2ceab0",
            "runtime_id_vas": ["0x101af0d0", "0x101aeff8"],
            "success": "Cleans runtime challenge state, adds calculated bolts, conditionally grants configured weapon/quick-select state, then increments the direct saved counter once. Counter-only edits do not reproduce this transaction.",
            "failure": "Runtime cleanup and ID bookkeeping, not a write to a saved failure-counter array.",
            "reward": "Read raw BE32 count; subtract1 modulo32 bits when unsigned32(rewardWeapon+1)>1, then compare the adjusted low32 bits as signed32. Negative adjusted count yields0; zero yields base bolts; one uses float32 scale0.33; larger counts use0.1. Repeat reward is truncate((fusedFloat32(base*scale+25))/50)*50. Nonzero predicate2D1860 multiplies by100 with32-bit arithmetic; return converts unsigned32 to float32. Runtime config/rounding are not captured; no live quote is computed.", "float_constants": constants},
        "menu_resolver": {"va": "0x2756f8", "table": "ARENA_CHALLENGE_DATA", "field": "id", "upper_cap": 23,
            "warning": "get_times_challenge_completed resolves a runtime Lua table index, unlike direct get_challenge_successes. Runtime table/order and lower-bound safety are unresolved. Cap23 can alias the following unknown array; not proof of24 valid counters."},
        "named_bindings": bindings,
        "instruction_guards": [{"va": hex(address), "bytes": raw.hex().upper()} for address, raw in sorted(guards.items())]}
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "counters": [{"id": i, "offset": hex(base + 4 * i), "signed_value": struct.unpack_from(">i", data, base + 4 * i)[0],
                          "raw_hex": data[base + 4 * i:base + 4 * i + 4].hex().upper()} for i in range(count)],
            "following_category_raw": data[0x5734:0x5754].hex().upper()}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--assets", required=True, type=Path, help="Extracted arena.csv/lua/lc; never executed")
    parser.add_argument("--save", type=Path, help="Plaintext working copy, never overwritten")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.assets, options.save), indent=2, allow_nan=False))
