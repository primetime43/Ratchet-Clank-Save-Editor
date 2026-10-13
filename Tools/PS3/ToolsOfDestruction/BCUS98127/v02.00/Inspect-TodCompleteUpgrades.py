"""Read-only audit of all189 positive upgrade nodes and complete-grid edit policy.

Requires the original ELF and six reference config assets plus vendor DAT.
Reproduces purchase-write guards, literal topology and special type/mask query;
does not execute game code, edit files or infer final weapon effects.
"""
import argparse
import json
from pathlib import Path
import runpy

BASE = Path(__file__).resolve().parent
CANDIDATES = runpy.run_path(str(BASE / "Inspect-TodUpgradeCandidates.py"))
SPECIAL = runpy.run_path(str(BASE / "Inspect-TodSpecialModifiers.py"))


def inspect(elf_path, assets_path, vendor_path):
    audited = CANDIDATES["inspect"](elf_path, assets_path, vendor_path)
    special = SPECIAL["inspect"](elf_path)
    verified_flags = {(row["id"], row["node"]) for row in special["catalog"]}
    numeric_types = {"MOD_AMMO", "MOD_DAMAGE", "MOD_RANGE", "MOD_AOE", "MOD_SPEED", "MOD_DURATION",
                     "MOD_BOLTS", "MOD_MINERALS", "MOD_SPAWNCOUNT", "MOD_KNOCKBACK", "MOD_ALT_DAMAGE", "MOD_MISC"}
    report = []
    for weapon in audited["catalog"]:
        nodes = weapon["nodes"]
        for node in nodes[1:]:
            if node["type"] == "MOD_SPECIAL":
                if ((weapon["id"], node["index"]) not in verified_flags or not node["is_special"] or
                        node["runtime_value"] is not None or not isinstance(node["cost"], (int, float)) or
                        node["cost"] <= 0 or int(node["cost"]) != node["cost"]):
                    raise ValueError("Unverified value-free special node")
            elif (not node["definition_qualified"] or node["type"] not in numeric_types or
                  node["runtime_value"] == 0 or node["is_percent"] and node["runtime_value"] <= -1):
                raise ValueError("Unverified numeric modifier")
        order = CANDIDATES["reachable_order"](nodes, (1 << len(nodes)) - 2)
        if order["unreachable_nodes"] or len(order["order"]) != len(nodes) - 1:
            raise ValueError("Complete graph cannot satisfy its prerequisites")
        report.append({"id": weapon["id"], "config_name": weapon["config_name"], "positive_nodes": len(nodes) - 1,
                       "special_node": weapon["special_node"], "complete_mask_without_start": hex((1 << len(nodes)) - 2),
                       "admission_order": order["order"]})
    if len(report) != 15 or sum(row["positive_nodes"] for row in report) != 189:
        raise ValueError("Incomplete weapon upgrade catalog")
    mapping = json.loads(CANDIDATES["PURCHASE"]["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
    return {**mapping["complete_upgrade_editing"], "catalog": report,
            "native_purchase_guards": audited["native_guard_count"], "verified_value_free_special_nodes": len(verified_flags)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--vendor-asset", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.assets, args.vendor_asset), indent=2))
