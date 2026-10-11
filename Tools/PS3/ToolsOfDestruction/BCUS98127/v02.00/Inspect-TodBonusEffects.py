"""Read-only exact-build saved bonus-byte consumers and qualified runtime effects."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("progression", Path(__file__).with_name("Inspect-TodProgression.py"))
PROGRESSION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROGRESSION)
BINDINGS = PROGRESSION.BINDINGS


def head_basis_preview(cheat_id, raw_state, raw_score):
    """Only the saved comparisons/branch multiplier, never a bone/runtime mutation."""
    if not isinstance(cheat_id, int) or isinstance(cheat_id, bool) or cheat_id not in (1, 3):
        raise ValueError("Expected hero/enemy head bonus ID1 or3")
    if not isinstance(raw_state, int) or isinstance(raw_state, bool) or not 0 <= raw_state <= 255:
        raise ValueError("Expected raw unsigned state byte")
    if not isinstance(raw_score, int) or isinstance(raw_score, bool) or not 0 <= raw_score <= 0xFFFFFFFF:
        raise ValueError("Expected raw unsigned weighted score")
    requirement = 50 if cheat_id == 1 else 100
    if raw_state == 0 or raw_score < requirement:
        return None
    return ({1: 2.0, 2: 4.0, 3: 0.5}.get(raw_state, 1.0)
            if cheat_id == 1 else 0.5 if raw_state == 2 else 2.5)


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    def function(address):
        end = elf.functions[elf.functions.index(address) + 1]
        keep(address, end - address)

    checks = {
        0x890168: 0x101EFB20, 0x897B38: 0x101EFB20,
        0x8A18D8: 0x101EFB20, 0x8A18CC: 0x101EFB08,
        0x8A3694: 0x101EFB20, 0x8A6748: 0x101EFB20,
        0x8A6A60: 0x101FFB20, 0x8A6A50: 0x10724C10,
        0x897AFC: 0x3F800000, 0x897B58: 0x40000000,
        0x897B5C: 0x40800000, 0x897B54: 0x3F000000,
        0x89016C: 0x3F000000, 0x890170: 0x40200000,
        0x23EE8C: 0x881D86F9, 0x23EE90: 0x7F9C1840,
        0x23F104: 0xC3E27C20, 0x23F114: 0xC3E27C24,
        0x23F120: 0xC3E27C1C,
        0xBE578: 0x881D86FB, 0xBE57C: 0x7F9C1840,
        0xBE7E0: 0xC3E20234,
        0x3BAA60: 0x8B9E86FD, 0x3BAB20: 0x7C1D1840,
        0x483908: 0x896386FF, 0x48394C: 0x890A0000,
        0x483958: 0xF8670118, 0x483FCC: 0x88BE86FF,
        0x484010: 0x881E0000, 0x48401C: 0xF95A0118,
        0x35BDF4: 0x88648701,
        0x48CBD4: 0x88148703, 0x48CBD8: 0x7F181840,
        0x48CBF0: 0x99520000, 0x48CDC4: 0x98B20000,
        0x48CC0C: 0x98660045, 0x48CDE0: 0x9A920045,
    }
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Bonus effect evidence changed at {address:#x}")
        keep(address, 4)
    for address in (0xBE530, 0x23EE40, 0x35BC40, 0x3BAA38,
                    0x4838B8, 0x483D78, 0x48C768, 0x35CA20):
        function(address)
    for thunk in (0x11C50, 0x14250, 0x12820, 0x13F70, 0x13D60, 0x251E08, 0x24FEF8):
        keep(thunk, 16)
    enums = PROGRESSION.exports(elf, 0x28440, "CHEAT_", 0x12990)
    expected_enums = {1: "CHEAT_HERO_BIGHEAD", 3: "CHEAT_ENEMY_BIGHEAD",
                      5: "CHEAT_DEV_COMMENTS", 7: "CHEAT_WRENCH_REPLACE",
                      9: "CHEAT_JAMES_ZURKON", 11: "CHEAT_MIRROR_LEVEL"}
    selected = [x for x in enums if x["id"] in expected_enums]
    if {x["id"]: x["enum"] for x in selected} != expected_enums:
        raise ValueError("Native bonus effect identifiers changed")
    for item in selected:
        for key in ("name_slot_va", "name_load_va", "value_slot_va", "value_load_va", "value_move_va", "export_call_va"):
            keep(int(item[key], 0), 4)
        keep(int(item["name_va"], 0), len(item["enum"]) + 1)
    requirements = {}
    for cheat_id, expected in ((1, 50), (3, 100), (5, 200), (11, 500)):
        address = 0x10026384 + cheat_id*0x30 + 8
        if elf.u32(address) != expected:
            raise ValueError("Native bonus effect requirement changed")
        keep(address, 4)
        requirements[cheat_id] = expected
    descriptions = [
        (1, [0x23EE40], "Hero head transform basis (native)",
         "Unsigned score8708>=50 and rawstate86F9 nonzero permit the native transform path. State1/2/3 choose basis multipliers2.0/4.0/0.5; other nonzero bytes choose1.0. The nine basis components are multiplied and the resulting matrix is passed through12820/13F70 to13D60. State0 or insufficient score returns without this modification, not an explicit restoration to1.0.",
         "The caller-supplied bone index and runtime model/transform must be valid. Native fallback branches do not establish a general safe malformed-model contract; no current bone or visual gameplay result is inferred."),
        (3, [0xBE530], "Enemy head transform basis (native)",
         "Unsigned score8708>=100 and rawstate86FB nonzero permit this transform path. State2 chooses0.5; every other nonzero byte chooses2.5. The caller also checks a nonnegative bone-index argument. Basis components are multiplied before the native matrix/bone update calls; raw state values are not Boolean-normalized.",
         "Runtime actor/model/bone validity and call timing independently apply. A saved state does not establish that every enemy is changed, and state0 does not explicitly restore a previous matrix here."),
        (5, [0x3BAA38], "Developer-commentary runtime dispatch (native)",
         "The native qualifier called through251E08 must return exactly1, unsigned score8708 must be>=200 and state86FD must be nonzero. The reached path changes runtime object activation via24EC28 and dispatches runtime member+6C states0/1/2 to3BA658/3BA720/3BA5B8; the other branch uses24F4F8 and clears runtime low-nibble flags.",
         "CHEAT_DEV_COMMENTS is an exported identifier, not a recovered localized menu/voice label. Qualifier meaning, runtime state names, exact commentary clip and every audio dependency are unconfirmed."),
        (7, [0x4838B8, 0x483D78], "Wrench replacement runtime asset mask (native)",
         "Raw saved byte86FF indexes the byte table reached through runtime model+54->+6C. The resulting byte selects a64-bit shift that is ORed into runtime object+118 after clearing the model-defined selection bits. One consumer runs this during initialization; another repeats it on its own modulo8 update gate. Neither local block checks score8708 or clamps the raw state index.",
         "The asset table's current capacity/content and resulting replacement name are not recoverable from this save. Unknown state255 remains an index, not a safe effect option. No global absence of eligibility checks or always-active result is claimed."),
        (9, [0x35BC40], "James Zurkon native factory selection",
         "If runtime word101EFB08+8 is nonzero OR raw saved state8701 is nonzero, factory call250BF8 receives native pairC3/657; otherwise it receives4B/311. Reached objects then receive309848 setup and51F9E0 finalization. This function does not locally test score8708.",
         "The separate runtime qualifier lies outside saved state. The pair IDs are native factory arguments, not recovered localized object names, and state0 alone cannot select the default pair without that qualifier."),
        (11, [0x48C768], "Mirror-level runtime flags (native)",
         "Unsigned score8708>=500 and raw saved state8703 nonzero set runtime byte10724C10 to1 and OR bit0 into byte+45 of the runtime context reached through24FEF8(0)->+10. Otherwise the byte is0 and that bit is cleared while other flag bits remain. The saved state byte and score are not modified by this block.",
         "The runtime pointers are not additional save offsets. CHEAT_MIRROR_LEVEL is exported, but exact geometric axis, rendering/input consequences and current runtime applicability are not proved by these stores alone."),
    ]
    effects = [{"id": cheat_id, "enum": expected_enums[cheat_id],
                "state_offset": hex(0x86F8 + cheat_id), "state_type": "u8",
                "display_name": name, "consumer_vas": [hex(f) for f in consumers],
                "weighted_score_requirement": requirements.get(cheat_id),
                "rule": rule, "scope": scope}
               for cheat_id, consumers, name, rule, scope in descriptions]
    annotations = [(0x23EE40, "TOD_bonus_hero_head_basis_consumer", effects[0]["rule"]),
                   (0xBE530, "TOD_bonus_enemy_head_basis_consumer", effects[1]["rule"]),
                   (0x3BAA38, "TOD_bonus_dev_comments_consumer", effects[2]["rule"]),
                   (0x4838B8, "TOD_bonus_wrench_asset_mask_init", effects[3]["rule"]),
                   (0x483D78, "TOD_bonus_wrench_asset_mask_update", effects[3]["rule"]),
                   (0x35BC40, "TOD_bonus_james_zurkon_factory_choice", effects[4]["rule"]),
                   (0x48C768, "TOD_update_including_mirror_bonus_flags", effects[5]["rule"])]
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA v02.00 static consumer effects only. Names are native exports, not localized labels. Saved comparisons are not current runtime availability or gameplay-tested edits; no native/Lua execution or original-save mutation.",
        "saved_state_base": "0x86f8", "weighted_score_offset": "0x8708",
        "score_scope": "These four consumer gates load weighted bonus score8708 with unsigned comparison;8734 and warning latch8738 are different previously mapped fields and are not substituted for this score.",
        "effects": effects, "enum_evidence": selected,
        "head_basis_factors": {"hero": {"1": 2.0, "2": 4.0, "3": 0.5, "other_nonzero": 1.0},
                               "enemy": {"2": 0.5, "other_nonzero": 2.5}},
        "runtime_only_fields": [
            {"va": "0x10724c10", "type": "u8", "rule": "Mirror-level qualified active flag; outside the saved-state span."},
            {"va": "0x101efb10", "type": "u32", "rule": "Separate factory-choice override;16 bytes before saved-state base, not saved bonus storage."},
            {"offset": "0x118", "base": "runtime object", "type": "u64", "rule": "Wrench replacement asset selection mask, not saved state+118."}],
        "recommended_annotations": [{"va": hex(a), "name": name, "kind": "function", "confidence": "code-backed",
                                     "bytes": elf.read(a, 8).hex().upper(), "comment": comment}
                                    for a, name, comment in annotations],
        "limitations": ["Only six native bonus IDs have newly traced consumers here; this is not a complete effect catalog.",
            "Runtime/menu ID remapping does not apply to these direct physical-byte reads. No current runtime mode value is inferred from the save.",
            "Local missing score checks in two consumers do not prove all callers or other effect dependencies ignore availability.",
            "Arbitrary states and raw unsigned scores are exposed without normalization; no safe edit range or console acceptance is claimed."],
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save size")
        data = path.read_bytes()
        if any(struct.unpack_from(">I", data, i*0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        score = struct.unpack_from(">I", data, 0x8708)[0]
        observations = []
        for effect in effects:
            state = data[int(effect["state_offset"], 0)]
            requirement = effect["weighted_score_requirement"]
            row = {"id": effect["id"], "enum": effect["enum"], "offset": effect["state_offset"],
                   "raw_state": state, "raw_hex": f"{state:02X}",
                   "weighted_score_requirement_satisfied": None if requirement is None else score >= requirement}
            if effect["id"] in (1, 3):
                row["saved_branch_basis_factor"] = head_basis_preview(effect["id"], state, score)
            observations.append(row)
        report["save_observation"] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest().upper(),
            "weighted_score": score, "weighted_score_raw_hex": data[0x8708:0x870C].hex().upper(),
            "effects": observations,
            "warning": "Only saved prerequisites/branch factors are observed. Separate runtime factory override, model tables, actor state and commentary qualifier remain unknown; no active-effect verdict is produced."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2))
