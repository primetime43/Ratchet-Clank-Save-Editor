"""Read-only exact-build Groovitron ammo, Golden object and event relationships."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
FUNCTIONS = (
    (0x475710, 0x2C8, "A8FB632BD29E920AC04200B7E277848AE31FA4EB9A7E29A5B467E1464554BB0D"),
    (0x475358, 0x148, "158BA859D847A04AD931BF28A9D1019E17E058B03AF11E5769009AA7F0217410"),
    (0x23D940, 0x30, "78BA1A1F4EFF54A68EFECB41A4E8EFAE33A88DC58230873797F250B5AAF5646E"),
)
WORDS = {
    0x24F7B8: 0xF8410028, 0x24F7BC: 0x3C42FFFF,
    0x24F7C0: 0x38420018, 0x24F7C4: 0x4BFEE17C,
    0x4753D4: 0x3800080A, 0x4753F0: 0xF8010070,
    0x475408: 0x38800013, 0x475470: 0x4BFF1329,
    0x475788: 0x419900C8, 0x47578C: 0xC3E26348,
    0x475794: 0xFC20F890, 0x475798: 0x4BFF4C89,
    0x475850: 0xC3E26354, 0x4758E4: 0x419A005C,
    0x47591C: 0x80BF0014, 0x475920: 0x80830014,
    0x475924: 0xE9250140, 0x475928: 0xE8050148,
    0x47592C: 0xF9240140, 0x475930: 0xF8040148,
    0x475940: 0xFC20F890, 0x475954: 0x4BFF542D,
    0x47595C: 0x4BFFFE30, 0x475960: 0x3880000B,
    0x475968: 0x4BDD9E51, 0x475974: 0x2C840000,
    0x475978: 0x4186FE00, 0x47597C: 0x80DF0014,
    0x475980: 0xC0026354, 0x475984: 0x38A60140,
    0x475988: 0xC1A26358, 0x475990: 0xD009000C,
    0x475994: 0xD1A90008, 0x475998: 0xD0090000,
    0x47599C: 0xD0090004, 0x4759A0: 0x4BFFFDD8,
    0x8A6268: 0x00000000, 0x8A6274: 0x3F800000,
    0x8A6278: 0x3E808081,
}


def saved_observation(data):
    if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
        raise ValueError("Expected the verified detached inventory layout")
    xp, ammo, mask = struct.unpack_from(">ffI", data, 0x180)
    current, peak, additions = (struct.unpack_from(">I", data, o)[0] for o in (0x330, 0x38C, 0x3E8))
    flag = bool(struct.unpack_from(">Q", data, 0x5548)[0] & (1 << 30))
    return {
        "groovitron": {"id": 19, "record_offset": "0x17c", "ammo_offset": "0x184",
                       "ammo_bits": data[0x184:0x188].hex().upper(),
                       "ammo": ammo if math.isfinite(ammo) else None,
                       "xp": xp if math.isfinite(xp) else None, "modifier_mask": f"0x{mask:08X}",
                       "owned": data[0x18C], "stored_level": data[0x18D]},
        "golden_object": {"id": 11, "current": current, "peak": peak, "positive_additions": additions,
                          "current_nonzero_query": current != 0},
        "golden_event286_set": flag,
        "object_query_and_event_agree_in_snapshot": (current != 0) == flag,
        "qualification": "The object query and named event are separate storage, not a synchronized invariant. No disagreement repair, Golden grant or ammo edit is licensed.",
    }


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    for address, expected in WORDS.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Groovitron evidence changed at {address:#x}")
    for address, size, digest in FUNCTIONS:
        if hashlib.sha256(elf.read(address, size)).hexdigest().upper() != digest:
            raise ValueError(f"Groovitron function evidence changed at {address:#x}")
    for section in ("ammo_capacity", "weapon_ammo_debit"):
        for guard in elf.mapping[section]["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            if elf.read(int(guard["va"], 0), len(raw)) != raw:
                raise ValueError(f"Shared {section} evidence changed")
    row = next(row for row in elf.mapping["quick_select_eligibility"]["catalog"] if row["id"] == 19)
    if row["config_name"] != "Groovitron" or int(row["initial_flags"], 0) != 0x80A:
        raise ValueError("Groovitron constructor binding changed")
    configs = json.loads((BINDINGS["MAP_PATH"].parent / "WeaponConfigs.json").read_text(encoding="utf-8"))
    config = configs["weapons"]["Groovitron"]
    if not configs["reference_assets_match"] or config["num_levels"] != 0 or config["modifiers"] or config["variables"]["MaxAmmo"] != [3]:
        raise ValueError("Shipped ordinary Groovitron capacity changed")
    flag = next(row for row in elf.mapping["global_flags"]["catalog"] if row["id"] == 286)
    if (flag["enum"], flag["word_offset"], flag["word_bit"]) != ("GOLDENGROOVITRON_ACQUIRED", "0x5548", 30):
        raise ValueError("Golden event binding changed")
    report = {
        "confidence": "exact-build-native-branch-and-detached-save-evidence",
        "saved_fields": {"ordinary_ammo": "0x184", "golden_current": "0x330", "golden_peak": "0x38c",
                         "golden_positive_additions": "0x3e8", "golden_event": {"id": 286, "word_offset": "0x5548", "bit": 30}},
        "ordinary_definition": {"weapon_id": 19, "config_name": "Groovitron", "initial_flags": "0x0000080A", "shipped_capacity": 3},
        "object_query": {"thunk_va": "0x24f7b8", "leaf_va": "0x23d940",
                         "rule": "Returns current object word at hero inventory+304+4*ID !=0. For ID11 this is saved330; neither peak, additions nor event286 is read by this leaf."},
        "activation_branch": {"va": "0x475710", "golden_query_call_va": "0x475968",
            "golden_branch": "When the earlier runtime predicate routes here, query object11. Nonzero writes four float components 1,1,0.250980407,1 at weapon instance+14 pointer+140; zero skips those stores. The spawn-initialization path47591C..475930 copies those16 bytes to the spawned instance+14 pointer+140. These are runtime appearance-like components, not saved ammo or capacity; a property name is not proved.",
            "ammo_path": "Spawn-attempt branch loads1.0 into f31 at475850, passes it to46AD80 at475954, then returns to47578C which loads0.0 for gate46A420. The debit is not locally conditioned on object11 or event286. A zero spawn result at4758E4 skips instance initialization but still reaches475940/debit; this is not proof of successful firing.",
            "scope": "The observed branch does not establish the complete Golden unlimited-ammo mechanism or rule out runtime definition overrides and other callbacks. No Golden-to-capacity contract is inferred."},
        "editor_policy": "Keep Groovitron ammo and Golden grant/event edits read-only. Shipped MaxAmmo3 and a local one-unit debit do not by themselves validate Golden linked-state editing or a global ownership/capacity policy.",
        "shared_guard_sections": ["ammo_capacity", "weapon_ammo_debit", "quick_select_eligibility", "global_flags"],
        "function_guards": [{"va": hex(a), "size": hex(n), "sha256": h} for a, n, h in FUNCTIONS],
        "instruction_guards": [{"va": hex(a), "bytes": f"{w:08X}"} for a, w in sorted(WORDS.items())],
        "recommended_annotations": [{
            "va": "0x475710", "name": "TOD_golden_object11_components_and_ammo_attempt_verified",
            "kind": "function", "confidence": "confirmed", "bytes": elf.read(0x475710, 16).hex().upper(),
            "comment": "Object11 query24F7B8 at475968 uses saved current330 only. A nonzero result writes runtime float components1,1,0.250980407,1, later copied to a spawned instance; no saved capacity/event store here. The spawn-attempt branch independently passes1.0 to46AD80 at475954, even if spawn returned0. Not proof of firing success or the complete Golden unlimited-ammo mechanism.",
            "evidence": "Exact-build full-body hash; GroovitronState instruction guards; objects.catalog ID11; shared weapon_ammo_debit and ammo_capacity guards.",
        }],
        "warning": "USA v02.00 static evidence only. Runtime predicates, use acceptance, linked mutations and gameplay behavior are not executed or certified.",
    }
    if save_path is not None:
        data = Path(save_path).read_bytes()
        report["save_observation"] = {"sha256": hashlib.sha256(data).hexdigest().upper(), **saved_observation(data)}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
