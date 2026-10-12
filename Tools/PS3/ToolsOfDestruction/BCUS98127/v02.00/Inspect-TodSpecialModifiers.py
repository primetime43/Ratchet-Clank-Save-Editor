"""Read-only MOD_SPECIAL predicate and Predator duplicate-target evidence.

Exact USA v02.00 code only. This does not qualify upgrades for editing or
emulate projectile activation. Blank definition values remain unspecified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
CATALOG = ((5, "BuzzBlade", 6), (6, "Predator", 8), (7, "AlphaNova", 10),
           (8, "FlameThrower", 9), (10, "Reaper", 13), (11, "Rocket", 5),
           (12, "RoboHive", 9))
GUARDS = {
    0x466630: "8163004879690020812906A42F890000419E004C38A9FFFF396B046478A300203940000038030001390000017C0903A67D065030796900207CC72038396B00182C070000394A000141820010818900002C8C0010418600144200FFD8386000007C6307B44E800020386000017C6307B44E800020",
    0x46B328: "F821FF917C8802A6F88100808123002C806300308089000C4BFFB2F160000000E8010080786306207C0803A6382100704E800020",
    0x80C28: "C3C2B434", 0x88B36C: "41800000",
    0x80EC8: "FC20F0908082B4F87FA3EB784BF91ABD", 0x88B430: "10000428",
    0x478BC4: "7BE300204BFF276160000000547F063E2C9F0000418600602B1E00013860000040990074",
    0x478C38: "E881009038600000EBC100707C6307B4",
    0x478C58: "E881009038600001EBC100707C6307B4", 0x8A63E0: "40000000",
}


def special_preview(mask, types):
    """Bounded synthetic type/mask predicate; no pointer or value assumptions."""
    if type(mask) is not int or not 0 <= mask <= 0xFFFFFFFF:
        raise ValueError("Expected unsigned32 mask")
    if not isinstance(types, (list, tuple)) or len(types) > 24:
        raise ValueError("Expected at most 24 declared modifier types")
    if any(type(value) is not int or not 0 <= value <= 0xFFFFFFFF for value in types):
        raise ValueError("Expected unsigned32 modifier types")
    return any(mask & (1 << index) and kind == 16 for index, kind in enumerate(types))


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    for address, expected in GUARDS.items():
        if elf.read(address, len(expected) // 2).hex().upper() != expected:
            raise ValueError(f"Special modifier evidence changed at {address:#x}")
    if elf.string(0x10000428) != "MOD_SPECIAL":
        raise ValueError("MOD_SPECIAL enum name changed")
    for function in (0x466630, 0x46B328, 0x478AA8):
        if elf.descriptors[function] != 0x89FF20:
            raise ValueError("Unexpected consumer TOC")
    consumer_hash = hashlib.sha256(elf.read(0x478AA8, 0x21C)).hexdigest().upper()
    if consumer_hash != "5F2CB76E8ADE61E2E96992BB8848302C0968A15535932BB85EFF0CC2ED1CC8DD":
        raise ValueError("Predator duplicate-target consumer changed")
    configs = json.loads((BINDINGS["MAP_PATH"].parent / "WeaponConfigs.json").read_text(encoding="utf-8"))
    if not configs["reference_assets_match"]:
        raise ValueError("Expected exact reference config catalog")
    catalog = []
    for item_id, name, index in CATALOG:
        modifier = configs["weapons"][name]["modifiers"][index]
        if modifier["index"] != index or modifier["type"] != "MOD_SPECIAL" or modifier["runtime_value"] is not None:
            raise ValueError("Expected blank-value special definition")
        catalog.append({"id": item_id, "config_name": name, "node": index,
                        "save_mask_offset": hex(item_id * 20 + 12), "mask_bit": hex(1 << index),
                        "type_id": 16, "value": None, "cost": modifier["cost"]})
    report = {
        "reference_build": "BCUS98127 v02.00", "elf_sha256": elf.mapping["binary"]["sha256"],
        "report_tool": "Inspect-TodSpecialModifiers.py", "catalog": catalog,
        "enum": {"id": 16, "name": "MOD_SPECIAL", "name_va": "0x10000428",
                 "value_load_va": "0x80c28", "value_slot_va": "0x88b36c", "export_call_va": "0x80ed4"},
        "predicate": {"va": "0x466630", "definition_pointer_member": "0x48", "count_offset": "0x6a4",
                      "array_offset": "0x464", "stride": "0x18",
                      "rule": "Returns true when any enabled mask index below declared NumMods has type16. Zero count returns false. Reads type+0 only: kind+4, value+8, price+0C and labels are not inputs. No ownership, topology, wallet or playable-level gate.",
                      "boundary": "Native count is not locally clamped to24; synthetic preview and bundled configs are bounded. Valid definition pointers are assumed by native code."},
        "actor_wrapper": {"va": "0x46b328", "record_pointer_member": "0x2c", "definition_pointer_member": "0x30",
                          "rule": "Loads saved modifier mask from borrowed record+0C and queries definition+30 through466630. Does not check record null or ownership; returns the low result byte."},
        "predator_consumer": {"va": "0x478aa8", "bytes": 0x21C, "sha256": consumer_hash,
                              "query_call_va": "0x478bc8", "runtime_list_offset": "0x320", "count_offset": "0x3c0", "entry_stride": "0x10",
                              "rule": "Counts exact12-byte target-token matches in the runtime list. A first match-free target returns1 without special query. For repeated targets, a runtime component6C whose float+8 is ordered below2.0 rejects before querying the modifier. Otherwise no MOD_SPECIAL rejects; MOD_SPECIAL admits exactly one previous match and rejects two or more. Every path publishes the request in a32-entry runtime ring first.",
                              "boundary": "This proves a local duplicate-target admission effect, not a final projectile count, complete target eligibility or whole weapon behavior. Runtime lists/components/ring are not saved fields."},
        "edit_policy": "Keep these seven nodes read-only for now. A blank numeric value is not itself a predicate blocker: the native special query does not read it. Weapon-specific effects and activation dependencies require separate qualification; do not replace unspecified values with zero.",
        "instruction_guards": [{"va": hex(address), "bytes": expected} for address, expected in GUARDS.items()],
        "recommended_annotations": [
            {"va": "0x00466630", "name": "TOD_any_enabled_special_modifier", "kind": "function", "confidence": "confirmed", "bytes": GUARDS[0x466630][:8], "comment": "Any enabled declared node of type16 (MOD_SPECIAL). Does not read numeric value/kind/cost or ownership; pointer/count safety is not checked locally."},
            {"va": "0x0046B328", "name": "TOD_actor_special_modifier_from_saved_mask", "kind": "function", "confidence": "confirmed", "bytes": GUARDS[0x46B328][:8], "comment": "Actor+2C borrowed inventory record supplies saved mask+0C; actor+30 definition passed to466630. No null/ownership check. Result reduced to low byte."},
            {"va": "0x00478AA8", "name": "TOD_predator_duplicate_target_local_admission", "kind": "function", "confidence": "confirmed", "bytes": "F821FF81", "comment": "Counts exact12-byte token matches at runtime+320. Repeat targets require special predicate and fewer than2 previous matches after component6C float+8 below2.0 rejection. Writes request ring even on rejection. Not complete target or projectile eligibility."},
        ],
    }
    for annotation in report["recommended_annotations"]:
        annotation["evidence"] = "SpecialModifiers exact-build instruction guards; enum16 export; actor wrapper; full Predator consumer body SHA-256."
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or [int.from_bytes(data[i * 20:i * 20 + 4], "big") for i in range(32)] != list(range(32)):
            raise ValueError("Expected USA plaintext save layout")
        observed = []
        for entry in catalog:
            offset = int(entry["save_mask_offset"], 0)
            mask = int.from_bytes(data[offset:offset + 4], "big")
            observed.append({"id": entry["id"], "raw_mask": hex(mask), "special_bit_set": bool(mask & int(entry["mask_bit"], 0))})
        report["save_observation"] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest().upper(), "records": observed,
                                      "warning": "A snapshot confirms stored bit values, not a before/after activation or native acceptance test."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True)
    parser.add_argument("--save")
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2))
