"""Read-only shipped upgrade topology and definition-qualified add-only candidates.

This is a research allowlist, not a purchase simulator or editable-save verdict.
No native/Lua code is executed and no input files are rewritten.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct

BASE = Path(__file__).resolve().parent
PURCHASE = runpy.run_path(str(BASE / "Inspect-TodUpgradePurchase.py"))
CONFIGS = runpy.run_path(str(BASE / "Inspect-TodWeaponConfigs.py"))


def catalog(grid, modifiers):
    """Cross-check literal grid indices against contiguous shipped definitions."""
    rows, special = grid["grid"], grid["special_node"]
    PURCHASE["vendor_predicate_preview"](rows, 0, 0, special)
    positions = {n for row in rows for n in row if n >= 0}
    if not 1 <= len(modifiers) <= 24 or positions != set(range(len(modifiers))):
        raise ValueError("Grid and modifier indices must match exactly")
    if modifiers[0]["type"] != "MOD_START" or special not in positions | {-3}:
        raise ValueError("Unexpected start or special marker")
    result = []
    for index, definition in enumerate(modifiers):
        if definition["index"] != index:
            raise ValueError("Modifier indices must be contiguous")
        predicate = PURCHASE["vendor_predicate_preview"](rows, index, 0, special)
        value, cost = definition["runtime_value"], definition["cost"]
        numeric_value = type(value) in (int, float) and math.isfinite(value)
        integral_cost = (type(cost) in (int, float) and math.isfinite(cost)
                         and cost > 0 and int(cost) == cost)
        qualified = index > 0 and numeric_value and integral_cost
        result.append({"index": index, "type": definition["type"],
                       "is_special": index == special, "is_start": index == 0,
                       "orthogonal_neighbors": predicate["orthogonal_neighbors"],
                       "definition_qualified": qualified,
                       "runtime_value": value, "cost": cost,
                       "is_percent": definition["is_percent"]})
    return result


def reachable_order(nodes, desired_mask):
    """Deterministic geometric admission order; ignores definition qualification."""
    PURCHASE["uint"](desired_mask)
    if desired_mask & ~((1 << len(nodes)) - 1):
        raise ValueError("Mask contains undefined nodes")
    reached, order = {0}, []
    remaining = {n["index"] for n in nodes if n["index"] > 0 and desired_mask & (1 << n["index"])}
    while remaining:
        candidates = []
        for n in nodes:
            if n["index"] not in remaining:
                continue
            neighbors = n["orthogonal_neighbors"]
            admitted = (all(i in reached for i in neighbors if i > 0) if n["is_special"]
                        else any(i in reached for i in neighbors))
            if admitted:
                candidates.append(n["index"])
        if not candidates:
            break
        for index in sorted(candidates):
            reached.add(index)
            remaining.remove(index)
            order.append(index)
    return {"order": order, "unreachable_nodes": sorted(remaining)}


def frontier(nodes, mask, ownership):
    """Owned, absent, qualified immediate additions; no wallet/max-ammo verdict."""
    PURCHASE["uint"](ownership, 255)
    state = reachable_order(nodes, mask)
    if not ownership or state["unreachable_nodes"]:
        return []
    installed = lambda i: i == 0 or bool(mask & (1 << i))
    return [n["index"] for n in nodes if n["definition_qualified"] and not installed(n["index"])
            and (all(installed(i) for i in n["orthogonal_neighbors"] if i > 0)
                 if n["is_special"] else any(installed(i) for i in n["orthogonal_neighbors"]))]


def inspect(elf_path, assets_path, vendor_path, save_path=None):
    definitions = CONFIGS["inspect"](assets_path)
    if not definitions["reference_assets_match"]:
        raise ValueError("Requires six exact reference configuration assets")
    native = PURCHASE["inspect"](elf_path, vendor_asset_path=vendor_path)
    decoded = PURCHASE["LUA"]["inspect"](vendor_path, 0x54F85)
    grids = PURCHASE["LUA"]["vendor_layout"](decoded)["grids"]
    mapping = json.loads(PURCHASE["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
    entries = []
    for item in mapping["weapon_configuration"]["inventory_catalog"]:
        if item["enum"] not in grids:
            continue
        nodes = catalog(grids[item["enum"]], definitions["weapons"][item["config_name"]]["modifiers"])
        all_mask = (1 << len(nodes)) - 2
        order = reachable_order(nodes, all_mask)
        if order["unreachable_nodes"]:
            raise ValueError("Shipped graph has unreachable positive nodes")
        entries.append({"id": item["id"], "config_name": item["config_name"],
                        "enum": item["enum"], "special_node": grids[item["enum"]]["special_node"],
                        "nodes": nodes, "synthetic_complete_admission_order": order["order"],
                        "synthetic_mask_zero_frontier": frontier(nodes, 0, 1)})
    all_nodes = [n for item in entries for n in item["nodes"]]
    report = {
        "confidence": "exact-build native guards and shipped literal topology audit",
        "warning": "Research candidates only. No new save-edit authorization or gameplay validation. Shipped values are not captured runtime overrides.",
        "catalog": entries,
        "counts": {"weapons": len(entries), "nodes": len(all_nodes),
                   "starts": sum(n["is_start"] for n in all_nodes),
                   "ordinary_positive": sum(not n["is_start"] and not n["is_special"] for n in all_nodes),
                   "special_positive": sum(n["is_special"] for n in all_nodes),
                   "definition_qualified_positive": sum(n["definition_qualified"] for n in all_nodes),
                   "ammo_nodes": sum(n["type"] == "MOD_AMMO" for n in all_nodes)},
        "candidate_policy": {
            "ordinary": "Absent positive node with finite value and positive integral cost; any installed orthogonal neighbor, with start0 implicit.",
            "special": "Same definition requirements, plus every positive orthogonal neighbor installed. Seven blank-value MOD_SPECIAL nodes are excluded, not assigned a guessed zero.",
            "baseline": "Require owned record, mask within shipped indices, and positive installed nodes geometrically attainable from implicit start0. Preserve start bit, existing nodes and unknown bytes; no removals or ownership grants.",
            "ammo": "465D00 recomputes maximum before/after OR. Unequal maxima refill ammo absolutely to NEW maximum; equal maxima preserve ammo. A writer must separately qualify finite level/base/MOD_AMMO inputs and account for simultaneous level/ammo edits.",
            "limits": "Frontier is not affordability or a runtime purchase verdict. Raritanium debit, callbacks/request4 and in-game acceptance are not simulated. Synthetic full order includes excluded nodes only to audit topology, not editing permission."},
        "assets": definitions["assets"],
        "vendor_asset_observation": native["asset_observation"],
        "native_guard_section": "upgrade_purchase",
        "native_guard_count": len(native["instruction_guards"]),
        "recommended_annotations": [],
    }
    if save_path is not None:
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Expected verified plaintext inventory layout")
        observations = []
        for entry in entries:
            offset = entry["id"] * 20
            mask = struct.unpack_from(">I", raw, offset + 12)[0]
            observations.append({"id": entry["id"], "config_name": entry["config_name"],
                                 "mask_raw_hex": f"{mask:08X}", "ownership_byte": raw[offset + 16],
                                 "missing_positive_nodes": [n["index"] for n in entry["nodes"] if n["index"] > 0 and not mask & (1 << n["index"])],
                                 "candidate_frontier": frontier(entry["nodes"], mask, raw[offset + 16])})
        complete = all(not e["missing_positive_nodes"] for e in observations)
        report["save_observation"] = {"sha256": hashlib.sha256(raw).hexdigest().upper(), "records": observations,
            "all_positive_nodes_already_installed": complete,
            "warning": ("This snapshot contains no missing positive nodes on any weapon and cannot independently validate an add/purchase transition."
                        if complete else "Missing nodes and candidate frontiers are observed; they do not establish purchase history or gameplay acceptance.")}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--vendor-asset", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.assets, args.vendor_asset, args.save), indent=2, allow_nan=False))
