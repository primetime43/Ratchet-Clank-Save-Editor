"""Read-only exact-build combat-weapon acquisition and saved grant policy.

Checks eleven function fingerprints, named/default constants and all combat
initializer flags. Does not execute game code, grant items or write files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
ELIGIBILITY = runpy.run_path(str(Path(__file__).with_name("Inspect-TodQuickSelectEligibility.py")))


def inspect(elf_path):
    elf = BINDINGS["Elf"](elf_path)
    report = elf.mapping["weapon_grants"]
    for guard in report["function_guards"]:
        va, size = int(guard["va"], 0), guard["size"]
        if elf.functions[elf.functions.index(va) + 1] - va != size:
            raise ValueError(f"Function boundary changed at {va:#x}")
        if hashlib.sha256(elf.read(va, size)).hexdigest().upper() != guard["sha256"]:
            raise ValueError(f"Function fingerprint changed at {va:#x}")
    for constant in report["constants"].values():
        va = int(constant["va"], 0)
        if elf.read(va, 4).hex().upper() != constant["bits"]:
            raise ValueError(f"Grant constant changed at {va:#x}")
        if "name" in constant and elf.string(elf.u32(va)) != constant["name"]:
            raise ValueError("Named hero grant changed")
    expected_calls = {0x466C28: 0x465D88, 0x466C50: 0x4660A8, 0x28B61C: 0x466B70,
                      0x28B630: 0x252B08, 0x252B14: 0x1E26F0,
                      0x1E2788: 0x1E22A8, 0x1E27E0: 0x1E22F8}
    for va, target in expected_calls.items():
        if BINDINGS["branch_target"](elf.u32(va), va) != target:
            raise ValueError(f"Grant call target changed at {va:#x}")
    flags = ELIGIBILITY["inspect"](elf_path)["catalog"]
    configs = json.loads(Path(BINDINGS["MAP_PATH"]).with_name("WeaponConfigs.json").read_text(encoding="utf-8"))
    catalog = []
    for row in flags:
        id_ = row["id"]
        if not 1 <= id_ <= 15:
            continue
        config = configs["weapons"][row["config_name"]]
        variables = config["variables"]
        if (int(row["initial_flags"], 0) & (0x203 | 0x1040) or
                not row["quick_select_initially_allowed"] or config["num_levels"] != 9 or
                variables["XP"][0] != 0 or variables["XP"][1] <= 0 or
                variables["MaxAmmo"][0] != report["starting_ammo_by_id_1_to_15"][id_ - 1]):
            raise ValueError(f"Combat starting reference changed for ID{id_}")
        catalog.append({"id": id_, "enum": row["enum"], "config_name": row["config_name"],
                        "record_offset": hex(id_ * 20), "initial_flags": row["initial_flags"],
                        "initial_level_index": 0, "initial_xp": 0, "initial_ammo": variables["MaxAmmo"][0]})
    if [row["id"] for row in catalog] != list(range(1, 16)):
        raise ValueError("Incomplete combat grant catalog")
    return {**report, "catalog": catalog, "verified_functions": len(report["function_guards"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf), indent=2))
