"""Read-only exact-build consumable-ammo catalog and conservative saved-state gates.

This is an editor allowlist, not a purchase, firing or ownership-grant simulator.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
CONFIGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponConfigs.py")))
FLAGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodQuickSelectEligibility.py")))
ALLOWLIST = {
    16: ("Zurkon", 4, 0x802), 17: ("ConfusionGas", 2, 0x80A),
    18: ("Slinkonator", 3, 0x802), 20: ("MiniLeech", 2, 0x802),
    21: ("MaxiLeech", 1, 0x802), 22: ("Morph", 3, 0x802),
    23: ("Copter", 3, 0x802),
}


def saved_observation(data, identifier, maximum):
    """Check a normal record; never normalize or write its raw float/flag bits."""
    if type(identifier) is not int or identifier not in ALLOWLIST:
        raise ValueError("Only the seven explicit consumable IDs are admitted")
    if maximum != ALLOWLIST[identifier][1]:
        raise ValueError("Unexpected shipped consumable capacity")
    if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, item * 20)[0] != item for item in range(32)):
        raise ValueError("Not the verified plaintext inventory layout")
    offset = identifier * 20
    xp, ammo, mask = struct.unpack_from(">ffI", data, offset + 4)
    owned, level = data[offset + 16:offset + 18]
    reasons = []
    if not owned:
        reasons.append("not owned")
    if level != 0:
        reasons.append("nonzero stored level")
    if not math.isfinite(xp) or xp != 0:
        reasons.append("XP is not finite zero")
    if mask != 0:
        reasons.append("nonzero modifier mask")
    if not math.isfinite(ammo) or not 0 <= ammo <= maximum:
        reasons.append("ammo is nonfinite or outside shipped capacity")
    return {"id": identifier, "ammo_offset": hex(offset + 8),
            "ammo_bits": data[offset + 8:offset + 12].hex().upper(),
            "xp_bits": data[offset + 4:offset + 8].hex().upper(),
            "ammo": ammo if math.isfinite(ammo) else None,
            "ownership_byte": owned, "stored_level": level,
            "modifier_mask": f"0x{mask:08X}",
            "tail_bits": data[offset + 18:offset + 20].hex().upper(),
            "passes_editor_gates": not reasons, "excluded_reasons": reasons}


def inspect(elf_path, save_path=None, assets_path=None):
    elf = BINDINGS["Elf"](elf_path)
    mapping = elf.mapping
    guards = {}
    # Reuse exact-build, complete native-body guards, not reconstructed runtime values.
    for section in ("ammo_capacity", "weapon_ammo_debit"):
        for guard in mapping[section]["instruction_guards"]:
            address, raw = int(guard["va"], 0), bytes.fromhex(guard["bytes"])
            if elf.read(address, len(raw)) != raw:
                raise ValueError(f"Consumable ammo native evidence changed at {address:#x}")
            guards[address] = raw
    configs = json.loads((BINDINGS["MAP_PATH"].parent / "WeaponConfigs.json").read_text(encoding="utf-8"))
    if not configs["reference_assets_match"] or any(
            configs["assets"][name]["sha256"] != digest
            for name, digest in CONFIGS["REFERENCE_HASHES"].items()):
        raise ValueError("Bundled consumable configuration hashes are not the reference build")
    if assets_path is not None:
        actual = CONFIGS["inspect"](assets_path)
        if not actual["reference_assets_match"]:
            raise ValueError("Extracted assets are not the reference build")
        for name, _, _ in ALLOWLIST.values():
            if actual["weapons"][name] != configs["weapons"][name]:
                raise ValueError("Extracted and bundled consumable configurations differ")
    # Bind names to the previously guarded native config pointer/getter catalog.
    for guard in mapping["weapon_configuration"]["catalog_instruction_guards"]:
        address, raw = int(guard["va"], 0), bytes.fromhex(guard["bytes"])
        if elf.read(address, len(raw)) != raw:
            raise ValueError(f"Item/config catalog evidence changed at {address:#x}")
        guards[address] = raw
    catalog = []
    rows = {row["id"]: row for row in mapping["quick_select_eligibility"]["catalog"]}
    for identifier, (name, capacity, expected_flags) in ALLOWLIST.items():
        row = rows[identifier]
        if row["config_name"] != name:
            raise ValueError("Consumable ID/config binding changed")
        constructor, call = int(row["constructor_va"], 0), int(row["call_va"], 0)
        store = int(row["flags_argument_store_va"], 0)
        instruction = elf.u32(store)
        if instruction >> 26 != 62 or (instruction >> 16) & 31 != 1 or instruction & 65535 != 0x70:
            raise ValueError("Consumable flags argument store changed")
        flags, literal = FLAGS["literal_argument"](elf, constructor, store, instruction >> 21 & 31)
        if flags != expected_flags or literal != int(row["flags_literal_va"], 0):
            raise ValueError("Consumable initial flags changed")
        if BINDINGS["branch_target"](elf.u32(call), call) != 0x466798 or not elf.u32(call) & 1:
            raise ValueError("Consumable definition initializer call changed")
        end = elf.functions[elf.functions.index(constructor) + 1]
        guards[constructor] = elf.read(constructor, end - constructor)
        config = configs["weapons"][name]
        if config["num_levels"] != 0 or config["modifiers"] or config["variables"]["MaxAmmo"] != [capacity]:
            raise ValueError("Consumable capacity/level/modifier definitions changed")
        catalog.append({"id": identifier, "config_name": name,
                        "ammo_offset": hex(identifier * 20 + 8), "maximum": capacity,
                        "stored_level_required": 0, "modifier_mask_required": "0x00000000",
                        "xp_required": "finite zero", "ownership_required": "nonzero byte",
                        "initial_flags": f"0x{flags:08X}",
                        "constructor_va": hex(constructor), "initializer_call_va": hex(call)})
    report = {
        "confidence": "exact-build-native-layout-and-shipped-consumable-capacity",
        "catalog": catalog,
        "asset_hashes": CONFIGS["REFERENCE_HASHES"],
        "assets_verified_from_files": assets_path is not None,
        "native_rule": "Saved ammo is f32 record+8.463DE0 selects definition MaxAmmo[level] and saved mask;466500 reads data+280+4*level.466258 applies MOD_AMMO records, absent from these seven configurations.465E18 adds/clamps through the same maximum;46AD80 negates a supplied debit request. No generic integer-count assumption, ownership grant or per-use charge is inferred.",
        "editor_policy": "Only owned explicit IDs16,17,18,20,21,22,23 with level0, finite zero XP, mask0 and finite ammo within shipped MaxAmmo[0]. Writes may change record+8 only; preserve XP, level, mask, ownership, tail, acquisition count, unlocks and all other saved bytes. Existing fractional ammo remains valid under this f32 path; a capacity is not a firing count.",
        "excluded": [
            {"ids": [19], "reason": "Groovitron purchase2D2D38 additionally queries object11 through24F7B8. Object11 is Golden Groovitron at saved330, separately tracked by global flag286 at5548 bit30. Linked activation/capacity overrides are not resolved; ordinary cap3 does not license a Golden Groovitron edit."},
            {"ids": list(range(24, 32)), "reason": "Traversal/script gadgets include no-ammo bypass flags, missing/zero capacities and the separate Gelanator fill/drain transition. Neither acquisition nor general record layout establishes safe consumable edits."},
        ],
        "warning": "USA BCUS98127 v02.00 only. Conservative editor policy based on exact static native/asset evidence, not in-game acceptance or live definition reconstruction. Runtime overrides, use callbacks and cross-build behavior remain unverified; originals are never written.",
        "shared_guard_sections": ["ammo_capacity", "weapon_ammo_debit", "weapon_configuration.catalog_instruction_guards"],
        "instruction_guards": [{"va": hex(address), "bytes": guards[address].hex().upper()}
                               for address in sorted(int(rows[identifier]["constructor_va"], 0) for identifier in ALLOWLIST)],
    }
    if save_path is not None:
        data = Path(save_path).read_bytes()
        report["save_observation"] = {
            "sha256": hashlib.sha256(data).hexdigest().upper(),
            "records": [saved_observation(data, row["id"], row["maximum"]) for row in catalog],
            "golden_groovitron_object11_bits": data[0x330:0x334].hex().upper(),
            "golden_groovitron_global286_set": bool(struct.unpack_from(">Q", data, 0x5548)[0] & (1 << 30)),
            "qualification": "Detached saved snapshot only; gate pass is an editor allowlist decision, not runtime firing/activation eligibility or proof of gameplay acceptance."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--assets", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save, args.assets), indent=2, allow_nan=False))
