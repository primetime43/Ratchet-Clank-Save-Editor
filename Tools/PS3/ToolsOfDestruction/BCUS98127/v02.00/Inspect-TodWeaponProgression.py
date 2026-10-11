"""Read-only exact-build weapon cap, XP transition and ammo arithmetic evidence.

Native code is never executed. Previews require explicit synthetic finite inputs;
they do not validate a game definition, modify a save or certify editable ranges.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))


def cap_preview(old_level, definition_flags, num_levels):
    """Bounded detached integer model of465F08 for an already resolved definition."""
    for value, maximum in ((old_level, 255), (definition_flags, 0xFFFFFFFF), (num_levels, 0xFFFFFFFF)):
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError("Expected bounded unsigned native input")
    return 0 if definition_flags & 3 else min(num_levels, 9 if old_level > 4 else 4)


def finite_level_preview(old_level, xp, thresholds, definition_flags=0):
    """Synthetic finite threshold loop only; no ownership/definition/ammo simulation."""
    if not isinstance(thresholds, (list, tuple)) or not 1 <= len(thresholds) <= 20:
        raise ValueError("Expected1..20 explicit synthetic threshold values")
    if type(xp) not in (int, float) or not math.isfinite(xp):
        raise ValueError("Preview requires finite XP")
    if any(type(t) not in (int, float) or not math.isfinite(t) for t in thresholds):
        raise ValueError("Preview requires finite thresholds")
    if any(a > b for a, b in zip(thresholds, thresholds[1:])):
        raise ValueError("Preview requires nondecreasing synthetic thresholds")
    cap = cap_preview(old_level, definition_flags, len(thresholds) - 1)
    level = 0
    while level < cap and xp >= thresholds[level + 1]:
        level += 1
    return {"pre_update_cap": cap, "recomputed_level": level,
            "increase_path": level > old_level,
            "warning": "Synthetic finite threshold comparison only; no native rounding, runtime definition resolution, ammo update or save edit is performed."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}

    def require(va, word):
        if elf.u32(va) != word:
            raise ValueError(f"Weapon progression evidence changed at {va:#x}")
        guards[va] = elf.read(va, 4)

    checks = {
        0x465CE0: 0x88030011, 0x465CE8: 0x2B800004,
        0x465F38: 0x807E0018, 0x465F3C: 0x546907BC, 0x465F40: 0x546007FE,
        0x465F7C: 0x38000009, 0x465F8C: 0x83FE0048, 0x465F90: 0x819F0460,
        0x465F94: 0x7D606050, 0x465F98: 0x7D68FE76, 0x465F9C: 0x7D075838,
        0x465FA0: 0x7CCA3A14, 0x465FA4: 0x54CB063E,
        0x465FCC: 0x38000004, 0x465FD4: 0x819F0460,
        0x4660E4: 0x8B9F0011, 0x4660F8: 0xD3FF0004,
        0x4660FC: 0x419E006C, 0x46610C: 0x989F0011,
        0x466110: 0x418200A8, 0x466118: 0xC0030234,
        0x46611C: 0xFC9F0000, 0x466120: 0x4CC53382, 0x466124: 0x40860094,
        0x466130: 0x7DA34C2E, 0x466134: 0xC03F0004, 0x466138: 0xFF816800,
        0x46613C: 0x4FDDF382, 0x466140: 0x409E0028,
        0x466144: 0x38CA0001, 0x466154: 0x7F085800, 0x466158: 0x39250234,
        0x46615C: 0x98DF0011, 0x466164: 0x409AFFCC,
        0x46616C: 0x88FF0011, 0x466170: 0x7C07F040, 0x466174: 0x40810044,
        0x466190: 0x810A00D0, 0x466194: 0x2888003C, 0x466198: 0x40850020,
        0x465E44: 0xC09D0008, 0x465E48: 0xEFFF202A, 0x465E5C: 0xD1BD0008,
        0x466224: 0xC09D0008, 0x466228: 0xED84F828, 0x46623C: 0xD1BD0008,
        0x4661E8: 0xC0090004, 0x4661EC: 0xEC21002A,
        0x465FF0 + 0x30: 0x897F0011, 0x46603C: 0x7FFC4C2E,
        0x466068: 0x7DBCEC2E, 0x46606C: 0xFF9F6800, 0x466070: 0x419E0014,
        0x466074: 0xC03F0004, 0x466078: 0xEDADF828, 0x46607C: 0xEC01F828,
        0x466080: 0xEC206824, 0x465ED4: 0x98DF0011, 0x465ED8: 0xC0090244,
        0x465EDC: 0xD01F0004, 0x465EAC: 0x80090460, 0x465EB0: 0x2B800004,
    }
    for va, word in checks.items():
        require(va, word)
    calls = ((0x4660F0, 0x465F08), (0x46617C, 0x463DE0), (0x466188, 0x465E18),
             (0x465F78, 0x465CE0), (0x466040, 0x465F08), (0x4661F0, 0x4660A8),
             (0x465E38, 0x463DE0), (0x466218, 0x463DE0),
             (0x465EE0, 0x463DE0), (0x465F00, 0x465E18))
    for va, target in calls:
        if BINDINGS["branch_target"](elf.u32(va), va) != target:
            raise ValueError("Weapon progression call changed")
        guards[va] = elf.read(va, 4)
    functions = (0x463190, 0x4632B0, 0x463DE0, 0x465CE0, 0x465DC0, 0x465E18,
                 0x465E78, 0x465F08, 0x465FF0, 0x4660A8, 0x4661E0, 0x4661F8)
    for start in functions:
        end = elf.functions[elf.functions.index(start) + 1]
        guards[start] = elf.read(start, end - start)
    zero_va = elf.descriptors[0x465E18] + BINDINGS["signed"](elf.u32(0x465E40) & 0xFFFF, 16)
    require(zero_va, 0)
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA v02.00 static native evidence. No native execution, gameplay validation, current runtime definition reconstruction or new edit-safety claim. Saved float bits remain raw, including nonfinite/extreme values.",
        "level_cap": {
            "function_va": "0x465f08", "saved_level_offset": "0x11",
            "definition_flags_offset": "0x18", "definition_data_pointer_offset": "0x48",
            "num_levels_offset": "0x460", "pre_update_level_predicate_va": "0x465ce0",
            "rule": "If either low definition-flag bit is set, cap is0. Otherwise the PRE-UPDATE saved level selects boundary4 when <=4 or boundary9 when >4; cap is min(definition num_levels,boundary). The return is narrowed to a byte.",
            "dependency": "4660A8 reads old level and calls465F08 before storing supplied XP or resetting the level. Recomputing a level<=4 therefore cannot cross into stored5 through this setter alone even with very large XP. A previous level>4 permits a larger cap for that invocation; after a decrease to<=4 the next invocation uses boundary4.",
            "scope": "This is a stored-byte predicate, not a replay flag, challenge-mode check or proof of a current runtime weapon state. Definition lookup is required; no general null/invalid-ID safety is proven.",
        },
        "xp_transition": {
            "setter_va": "0x4660a8", "add_va": "0x4661e0", "xp_offset": "0x4",
            "xp_store_va": "0x4660f8", "threshold_base_offset": "0x230",
            "first_threshold_offset": "0x234", "threshold_stride": 4,
            "rule": "The supplied float is stored at record+4 without a local XP lower/upper clamp. With a resolved weapon-data pointer, level is first set0; ordered XP>=threshold[level+1] promotes inclusively one level at a time until the previously computed cap. Equal threshold promotes. Level may decrease; same/lower level does not run the increase-only ammo path.",
            "nonfinite_scope": "fcmpu promotion requires greater-or-equal, not unordered: an unordered first comparison leaves recomputed level0. This is not a promise of NaN payload preservation through floating-point execution; read-only inspection preserves original raw bits and does not normalize them.",
            "missing_data_scope": "The post-cap null weapon-data branch preserves the existing level after the XP store, but preceding lookup/cap paths have their own dereferences. It is not a safe invalid-ID API contract.",
            "add_rule": "4661E0 loads old XP, performs single-precision fadds with the supplied delta, then tail-calls4660A8. A negative delta is not locally rejected; XP accumulation is not a saved hero-XP418 write.",
            "increase_ammo": "Only new unsigned level>old level calls463DE0 for the new maximum and passes that maximum as an ADD delta to465E18. This is not an absolute ammo assignment: for finite ordinary nonnegative old ammo it reaches the maximum; negative old ammo can leave less than maximum after the addition/clamp.",
            "notification_gate": "After the ammo operation, runtime owner+D0 must be unsigned>60 before488688 is called with item ID and old/new levels. This gate does not block the prior XP, level or ammo stores; the callback's gameplay meaning remains unresolved.",
        },
        "ammo_arithmetic": {
            "absolute_setter_va": "0x465dc0", "add_va": "0x465e18", "subtract_va": "0x4661f8",
            "ammo_offset": "0x8", "maximum_helper_va": "0x463de0", "zero_constant_va": hex(zero_va),
            "rule": "Absolute/set, add and subtract each resolve the current level/modifier-dependent maximum. Add/subtract use fadds/fsubs against existing ammo before two fsub/fsel comparisons and stfs to record+8. For ordered finite inputs and nonnegative finite maximum this clips to[0,maximum]; it is not an unqualified NaN/infinity or negative-maximum normalization contract.",
            "scope": "The subtract leaf has a native caller in43A6C0, but these arithmetic guards alone do not prove exactly one decrement per shot, ammo cost, fire rate or a complete list of ammunition writers.",
        },
        "progress_display": {
            "function_va": "0x465ff0", "rule": "Loads low threshold using the RAW stored level before cap calculation, then high threshold at min(level+1,cap). If thresholds compare equal it returns the0 constant; otherwise returns(XP-low)/(high-low) with single-precision subtraction/division and no local0..1 clamp.",
            "scope": "The initial threshold lookup is not guarded by a local level-range clamp, and this helper does not repair inconsistent saved XP/level. A cap-level zero result is not a completion verdict; malformed/out-of-range levels are retained raw, not simulated against guessed data.",
        },
        "level_five_bridge": {
            "function_va": "0x465e78", "rule": "If weapon-data num_levels is unsigned>4, explicitly writes stored level5 and XP from threshold5 at data+244, then adds the newly resolved ammo maximum through465E18. Otherwise leaves this record unchanged. This separate bridge, not ordinary threshold XP alone, can cross the stored4/5 boundary.",
            "scope": "A known caller is2D21A8; the present report does not equate this boundary with a named gameplay mode or prove all possible callers and transition events.",
        },
        "recommended_annotations": [
            {"va": "0x465e18", "kind": "function", "name": "TOD_add_weapon_ammo_clamped", "comment": "Adds supplied float delta to saved inventory-record ammo+8 using fadds, then clamps ordered finite values with zero/current level+modifier maximum through fsel. XP increase passes the maximum as delta, not an absolute assignment. Nonfinite/negative-maximum behavior is not a generic normalization contract."},
            {"va": "0x4661f8", "kind": "function", "name": "TOD_subtract_weapon_ammo_clamped", "comment": "Subtracts supplied float delta from saved ammo+8 using fsubs, then the same zero/maximum comparison-select clipping. Native caller43A6C0 exists; no universal shot count/cost claim."},
        ],
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())],
    }
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Expected verified plaintext save size")
        data = path.read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
            raise ValueError("Expected verified plaintext inventory IDs0..31")
        records = []
        for i in range(32):
            offset = i * 20
            records.append({"id": i, "offset": hex(offset), "ownership_byte": data[offset + 16],
                "stored_level": data[offset + 17], "xp_bits": f"0x{struct.unpack_from('>I', data, offset + 4)[0]:08X}",
                "ammo_bits": f"0x{struct.unpack_from('>I', data, offset + 8)[0]:08X}",
                "selected_cap_boundary": 9 if data[offset + 17] > 4 else 4})
        report["save_observation"] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest().upper(),
            "records": records, "warning": "Boundary selection from the raw saved byte only, before definition flags/num_levels. No effective runtime cap, active weapon, valid XP/level invariant, current menu fraction or safe editing bound is inferred."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2))
