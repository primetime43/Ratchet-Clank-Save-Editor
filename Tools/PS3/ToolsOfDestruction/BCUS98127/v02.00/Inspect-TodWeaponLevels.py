"""Exact-build weapon XP property bindings and within-tier level edit policy.

Reads reference ELF/assets and detached plaintext only; never executes native
code/Lua or changes inputs. A file-edit policy is not gameplay validation.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct

BASE = Path(__file__).resolve().parent
BINDINGS = runpy.run_path(str(BASE / "Inspect-TodWeaponBindings.py"))
CONFIGS = runpy.run_path(str(BASE / "Inspect-TodWeaponConfigs.py"))
FLAGS = runpy.run_path(str(BASE / "Inspect-TodQuickSelectEligibility.py"))
PROGRESSION = runpy.run_path(str(BASE / "Inspect-TodWeaponProgression.py"))
CAPACITY = runpy.run_path(str(BASE / "Inspect-TodAmmoCapacity.py"))


def choices(ownership, level, xp_bits, ammo_bits, mask, flags, config):
    """Conservative policy over explicit saved fields and reference definitions."""
    if type(ownership) is not int or not 0 <= ownership <= 255 or type(level) is not int or not 0 <= level <= 255:
        raise ValueError("Expected raw unsigned saved bytes")
    for value in (xp_bits, ammo_bits, mask, flags):
        CAPACITY["word"](value)
    xp, ammo = (struct.unpack(">f", bits.to_bytes(4, "big"))[0] for bits in (xp_bits, ammo_bits))
    if ownership == 0 or level > 9 or flags & 3 or not math.isfinite(xp) or xp < 0 or not math.isfinite(ammo) or ammo < 0:
        return []
    variables = config["variables"]
    thresholds, amounts = variables.get("XP", []), variables.get("MaxAmmo", [])
    if config["num_levels"] != 9 or len(thresholds) != 10 or len(amounts) != 10 or thresholds[0] != 0:
        return []
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in thresholds + amounts):
        return []
    thresholds = [CAPACITY["rounded"](v) for v in thresholds]
    if any(a >= b for a, b in zip(thresholds, thresholds[1:])):
        return []
    if PROGRESSION["finite_level_preview"](level, xp, thresholds, flags)["recomputed_level"] != level:
        return []
    nodes = config["modifiers"]
    if len(nodes) > 24 or mask & ~((1 << len(nodes)) - 1):
        return []
    maximum, factor = CAPACITY["rounded"](amounts[level]), 1.0
    for index, node in enumerate(nodes):
        if node["index"] != index:
            return []
        if not mask & (1 << index) or node["type"] != "MOD_AMMO":
            continue
        value = node["runtime_value"]
        if type(value) not in (int, float) or not math.isfinite(value):
            return []
        value = CAPACITY["rounded"](value)
        if node["is_percent"]:
            factor = CAPACITY["rounded"](factor + value)
        else:
            maximum = CAPACITY["rounded"](maximum + value)
    maximum = CAPACITY["rounded"](maximum * factor)
    if not 0 < maximum <= 1_000_000 or ammo > maximum:
        return []
    first = 5 if level > 4 else 0
    if any(CAPACITY["rounded"](amounts[candidate]) != CAPACITY["rounded"](amounts[level]) for candidate in range(first, first + 5)):
        return []
    return list(range(first, first + 5))


def inspect(elf_path, assets_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    assets = CONFIGS["inspect"](assets_path)
    if not assets["reference_assets_match"]:
        raise ValueError("Weapon levels require all six exact reference assets")
    initial = FLAGS["inspect"](elf_path)
    guards = {}
    checks = {
        0x8903C: 0x83C2E7BC, 0x892C8: 0x83A2B3A8,
        0x892D0: 0x7FA5EB78, 0x892DC: 0x7FA4EB78, 0x892E8: 0x7FA4EB78,
        0x893A4: 0x80A2E90C, 0x893A8: 0x7FC4F378, 0x893AC: 0x80C2E910,
        0xB89F8: 0x281D0013, 0xB8A24: 0x38E30230, 0xB8A34: 0x7C2B352E,
        0xB8B10: 0x281D0013, 0xB8B2C: 0x38E80230, 0xB8B38: 0x7C2B342E,
        0xA751C: 0x90A90460, 0x4660E4: 0x8B9F0011, 0x4660F8: 0xD3FF0004,
        0x46610C: 0x989F0011, 0x46616C: 0x88FF0011, 0x466170: 0x7C07F040,
        0x466174: 0x40810044, 0x465F7C: 0x38000009, 0x465FCC: 0x38000004,
    }
    for va, word in checks.items():
        if elf.u32(va) != word:
            raise ValueError(f"Weapon level evidence changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    for va, target in ((0x892E0, 0x12A00), (0x892F0, 0x10FC0), (0x893B0, 0x12C80), (0x4660F0, 0x465F08), (0x46617C, 0x463DE0), (0x466188, 0x465E18)):
        if BINDINGS["branch_target"](elf.u32(va), va) != target:
            raise ValueError("Weapon level call changed")
        guards[va] = elf.read(va, 4)
    for slot, function in ((0x88E844, 0xB8A68), (0x88E848, 0xB8950), (0x88E898, 0xB4940), (0x88E89C, 0xA7478)):
        descriptor = elf.u32(slot)
        if struct.unpack(">II", elf.read(descriptor, 8)) != (function, 0x88FF38):
            raise ValueError("Weapon property descriptor changed")
        guards[slot], guards[descriptor] = elf.read(slot, 4), elf.read(descriptor, 8)
    for slot, text in ((0x88E6F4, "XP"), (0x88B2E0, "WeaponConfig"), (0x88E894, "NumLevels")):
        address = elf.u32(slot)
        if elf.string(address) != text:
            raise ValueError("Weapon property name changed")
        guards[slot], guards[address] = elf.read(slot, 4), elf.read(address, len(text) + 1)
    for start in (0xB8A68, 0xB8950, 0xB4940, 0xA7478, 0x465F08, 0x4660A8):
        guards[start] = elf.read(start, elf.functions[elf.functions.index(start) + 1] - start)
    catalog = []
    for item in initial["catalog"]:
        if not 1 <= item["id"] <= 15:
            continue
        config = assets["weapons"][item["config_name"]]
        flags = int(item["initial_flags"], 0)
        if flags & 3 or config["num_levels"] != 9:
            raise ValueError("Reference combat definition no longer supports tier policy")
        thresholds, amounts = (config["variables"][key] for key in ("XP", "MaxAmmo"))
        if len(thresholds) != 10 or len(amounts) != 10 or any(v is None for v in thresholds + amounts):
            raise ValueError("Incomplete combat level tables")
        if thresholds[0] != 0 or any(a >= b for a, b in zip(thresholds, thresholds[1:])):
            raise ValueError("Unexpected threshold order")
        tiers = []
        for first in (0, 5):
            if len(set(amounts[first:first + 5])) != 1:
                raise ValueError("Reference within-tier base ammo changes")
            tiers.append({"first_stored_level": first, "last_stored_level": first + 4, "base_max_ammo": amounts[first]})
        catalog.append({"id": item["id"], "config_name": item["config_name"], "initial_flags_bits": flags,
                        "xp_offset": hex(item["id"] * 20 + 4), "level_offset": hex(item["id"] * 20 + 17),
                        "num_levels_highest_index": 9, "xp_thresholds": thresholds, "tiers": tiers})
    annotations = [
        (0xB8A68, "function", "TOD_weapon_config_XP_indexed_get", "WeaponConfig indexed XP getter uses lfsx data+230+4*index; unsigned index>19 calls error helper, then can continue if it returns. This is not the scalar same-name XP property at+14 or HeroConfig's100-entry u32 XP bank."),
        (0xB8950, "function", "TOD_weapon_config_XP_indexed_set", "WeaponConfig indexed XP setter uses stfsx data+230+4*index after numeric conversion.20 physical float slots; out-of-range diagnostic is not a proven terminal bound. Threshold arrays are runtime definitions, not saved XP+4."),
        (0xB4940, "function", "TOD_weapon_config_NumLevels_get", "Reads unsigned definition-data+460 then converts to float for Lua. Shipped weapon.lua publishes highest populated zero-based index, not a count; combat references return9 for ten rows."),
        (0xA7478, "function", "TOD_weapon_config_NumLevels_set", "Numeric input goes through fctidz then low32 stw to definition-data+460. No local playable-level clamp or array-population validation; this is a runtime definition, not saved level+11."),
        (0x893B0, "comment", "TOD_weapon_config_scoped_XP_indexed_registration", "WeaponConfig scope uses shared XP name in nonvolatile r30, loaded8903C from88E6F4; indexed registration callbacks are88E844->B8A68 /88E848->B8950. Shared scalar XP name earlier registered with unrelated+14 callbacks; resolve class and array registration, not the string alone."),
    ]
    report = {
        "confidence": "scoped-native-XP-bindings-and-reference-within-tier-edit-policy",
        "report_tool": "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWeaponLevels.py",
        "xp_property": {"getter_va": "0xb8a68", "setter_va": "0xb8950", "data_offset": "0x230", "physical_count": 20,
                        "registration_call_va": "0x893b0", "num_levels_offset": "0x460",
                        "scope": "WeaponConfig float XP array. Same-name scalar+14 and HeroConfig u32 array are different registrations. Public out-of-range diagnostics do not cap raw native saved-level indexing."},
        "assets": assets["assets"], "catalog": catalog,
        "edit_policy": "Only owned combat IDs1..15 with flags&3==0, finite nonnegative XP/ammo, XP consistent with current level under pre-update cap, known modifier bits, valid reference ammo and complete ten-row tables. Restrict choices to the EXISTING stored0..4 or5..9 tier and require equal reference base capacity throughout that tier. Changed level sets saved XP to that float32 threshold; increase refills reference capacity, decrease retains ammo. Explicit ammo edits override a refill regardless of dictionary order. Same-level requests preserve all bytes. No tier bridge, ownership/modifier/payment/hero-XP/story changes or callback simulation.",
        "native_dependency": "4660A8 samples old level and derives cap through465F08 BEFORE storing XP or resetting level. Equal thresholds promote inclusively; cap uses4 or9 selected by old level>4, with definition flags/NumLevels. Only a strictly increased level calls maximum463DE0 then adds that maximum through465E18. With finite nonnegative old ammo this reaches maximum. Within-tier constant base and unchanged modifiers preserve capacity on decreases; this condition is an editor policy, not a native rejection gate.",
        "warning": "Exact USA v02.00 reference only; live definition overrides, FPSCR, callbacks and in-game acceptance remain unverified. This is a coupled file edit, not native execution or a weapon purchase. Raw XP remains inspection-only; no arbitrary XP or1..10 ownership/tier grant is offered.",
        "recommended_annotations": [{"va": hex(va), "kind": kind, "name": name, "confidence": "code-backed",
                                     "bytes": elf.read(va, 8 if kind == "function" else 4).hex().upper(), "comment": comment}
                                    for va, kind, name, comment in annotations],
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())],
    }
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
            raise ValueError("Expected verified plaintext layout")
        records = []
        for item in catalog:
            offset = item["id"] * 20
            xp_bits, ammo_bits, mask = struct.unpack_from(">III", data, offset + 4)
            selected = choices(data[offset + 16], data[offset + 17], xp_bits, ammo_bits, mask,
                               item["initial_flags_bits"], assets["weapons"][item["config_name"]])
            records.append({"id": item["id"], "stored_level": data[offset + 17], "xp_bits": f"{xp_bits:08X}",
                            "eligible_stored_levels": selected})
        report["save_observation"] = {"sha256": hashlib.sha256(data).hexdigest().upper(), "records": records}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.assets, args.save), indent=2, allow_nan=False))
