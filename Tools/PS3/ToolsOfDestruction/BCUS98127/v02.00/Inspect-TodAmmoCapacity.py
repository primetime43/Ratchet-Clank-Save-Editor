"""Read-only exact-build saved level/mask to weapon maximum-ammo calculation.

Previews use explicit synthetic finite definitions, never current runtime data.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))


def word(value):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("Expected raw unsigned32 word")
    return value


def level_address_plan(level):
    if type(level) is not int or not 0 <= level <= 255:
        raise ValueError("Expected raw saved level byte")
    return {"data_offset": 0x280 + 4 * level, "within_declared_20_slots": level < 20,
            "qualification": "Address arithmetic only; native helper has no local level clamp. No pointer dereference, populated definition, playable level or edit safety inferred."}


def finite_bits(bits):
    value = struct.unpack(">f", word(bits).to_bytes(4, "big"))[0]
    if not math.isfinite(value):
        raise ValueError("Synthetic preview requires finite binary32 inputs")
    return value


def rounded(value):
    try:
        result = struct.unpack(">f", struct.pack(">f", value))[0]
    except (OverflowError, struct.error) as error:
        raise ValueError("Synthetic intermediate exceeds finite binary32") from error
    if not math.isfinite(result):
        raise ValueError("Synthetic intermediate exceeds finite binary32")
    return result


def modifier_preview(base_bits, mask, attribute, nodes):
    """Finite nearest-even walker over <=24 explicit native-layout nodes only."""
    base, mask, attribute = finite_bits(base_bits), word(mask), word(attribute)
    if not isinstance(nodes, (list, tuple)) or len(nodes) > 24:
        raise ValueError("Expected0..24 explicit synthetic modifier records")
    decoded = []
    for node in nodes:
        if not isinstance(node, dict) or set(node) != {"attribute", "kind", "value_bits"}:
            raise ValueError("Expected explicit attribute/kind/value_bits node")
        decoded.append((word(node["attribute"]), word(node["kind"]), finite_bits(node["value_bits"])))
    factor = 1.0
    absolute, percentage = [], []
    for index, (node_attribute, kind, value) in enumerate(decoded):
        if mask & (1 << index) and node_attribute == attribute:
            if kind == 0:
                base = rounded(base + value)
                absolute.append(index)
            else:
                factor = rounded(factor + value)
                percentage.append(index)
    result = rounded(base * factor)
    return {"result_bits": struct.unpack(">I", struct.pack(">f", result))[0],
            "absolute_indices": absolute, "percentage_indices": percentage,
            "qualification": "Explicit synthetic finite nodes only, binary32 nearest-even with gradual underflow. Live FPSCR, NaN/Inf behavior, current definitions, mask attainability and saved-ammo mutation are not modeled; not a runtime maximum or safe edit range."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    expected = {
        0x463DF4: 0x80630000, 0x463E04: 0x80BD000C, 0x463E08: 0x889D0011,
        0x466504: 0x5483103A, 0x466508: 0x7CA62B78, 0x46650C: 0x38030280,
        0x466510: 0x38A00009, 0x466518: 0x812B0048, 0x466520: 0x7C29242E,
        0x466258: 0x81630048, 0x466260: 0x812906A4, 0x466268: 0x419E008C,
        0x466270: 0xC1A25FE0, 0x8A5F00: 0x3F800000,
        0x466274: 0x396B0464, 0x466284: 0x39000001, 0x466294: 0x396B0018,
        0x46629C: 0x7D0C5030, 0x4662A4: 0x7D873038, 0x4662AC: 0x4182FFE4,
        0x4662B0: 0x80090000, 0x4662B8: 0x4086FFD8, 0x4662BC: 0x80690004,
        0x4662C4: 0x419A0024, 0x4662C8: 0xC0090008, 0x4662D0: 0xEDAD002A,
        0x4662E0: 0xEC210372, 0x4662EC: 0xEC21102A,
        0x4662F4: 0xC1A25FE0, 0x4662F8: 0xEC210372,
    }
    guards = {}
    for address, raw in expected.items():
        if elf.u32(address) != raw:
            raise ValueError(f"Ammo capacity evidence changed at {address:#x}")
        guards[address] = elf.read(address, 4)
    for address, target, linked in ((0x463DFC, 0x463190, True), (0x463E0C, 0x466500, True),
                                     (0x466524, 0x466258, False)):
        instruction = elf.u32(address)
        if BINDINGS["branch_target"](instruction, address) != target or bool(instruction & 1) != linked:
            raise ValueError("Ammo capacity call/tail branch changed")
        guards[address] = elf.read(address, 4)
    for function in (0x463DE0, 0x466500, 0x466258):
        if elf.descriptors[function] != 0x89FF20:
            raise ValueError("Ammo capacity TOC changed")
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    report = {
        "confidence": "exact-build-native-arithmetic",
        "warning": "USA BCUS98127 v02.00 static evidence only; no native execution, current runtime definition resolution or new editing permission.",
        "saved_inputs": {
            "rule": "463DE0 resolves record ID+0 through463190, then loads raw ownership-independent level byte+11 and modifier word+0C.466500 loads definition-data pointer+48 and base f32 at data+280+4*level, selects attribute9 (MOD_AMMO), and tail-branches466258. Saved ammo+8 and XP+4 are not inputs to these selected arithmetic bodies.",
            "index_limit": "The raw saved level byte is not capped here by465F08, NumLevels or the declared20-slot MaxAmmo property. Level19 addresses2CC;20 addresses2D0;255 addresses67C. Values outside0..19 leave that declared array. Address arithmetic is not a valid dereference, playable level or safe editing range; the public indexed-property check does not protect this native saved-byte path."},
        "modifier_order": {
            "rule": "466258 walks NumMods at data+6A4 in ascending physical index, entries at464 with stride18. A record contributes only when its indexed saved mask bit is enabled AND entry attribute+0 equals requested9. Kind+4 exactly0 adds value f32+8 to the base using fadds. ANY nonzero kind adds value to a separate factor initially1.0 from8A5F00. After the loop, one fmuls multiplies the adjusted base by that factor: (base + absolute additions) * (1 + percentage additions), with single-precision rounding after each operation, not successive percentage compounding.",
            "limits": "NumMods is not locally capped at24 or32; native slw is not a general arbitrarily wide bitset. The bounded preview refuses more than24 explicit records and nonfinite/overflow values. Node0 has no special skip: it is ignored only when disabled or its attribute mismatches. Cost+0C, name/description tags, ownership, purchase eligibility and native level cap are not read by this walker. It does not clamp its result positive, mutate saved ammo or repair out-of-table mask bits; full lookup/helper effects and runtime overrides remain unresolved.",
            "empty_rule": "NumMods0 takes a separate load of1.0 and still performs fmuls before returning. It is not an unconditional raw-bit return for arbitrary nonfinite/signed-zero input."},
        "recommended_annotations": [
            {"va": "0x463e08", "kind": "comment", "name": "TOD_ammo_capacity_raw_saved_level_no_local_clamp", "comment": "Loads raw record+11 level byte; following466500 indexes data+280+4*level without local20-slot/NumLevels clamp. Separate XP cap does not protect this path; level255 offset67C is not proven valid."},
            {"va": "0x466520", "kind": "comment", "name": "TOD_ammo_capacity_base_from_unclamped_saved_level", "comment": "Reads f32 MaxAmmo base using raw caller level; then tail branch to466258 with saved mask and attribute9. No ownership/XP/current-ammo input or safe out-of-range lookup contract."},
            {"va": "0x4662ec", "kind": "comment", "name": "TOD_modifier_absolute_add_before_final_factor", "comment": "Kind exactly0: add f32 value+8 to base, physical index order. All nonzero kinds instead add to factor initialized1.0. Saved mask and exact attribute select records; cost/tags/ownership ignored by this arithmetic body."},
            {"va": "0x4662e0", "kind": "comment", "name": "TOD_modifier_single_final_multiply_not_compounding", "comment": "One final fmuls: adjusted base times accumulated factor. Formula(base+absolute additions)*(1+percentage additions), with per-operation binary32 rounding; not per-node percentage compounding or result positivity clamp."},
        ],
        "instruction_guards": [{"va": hex(a), "bytes": raw.hex().upper()} for a, raw in sorted(guards.items())],
    }
    if save_path is not None:
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not verified plaintext inventory layout")
        report["save_observation"] = {
            "sha256": hashlib.sha256(raw).hexdigest().upper(),
            "records": [{"id": i, "stored_level": raw[i * 20 + 17],
                         "mask_bits": raw[i * 20 + 12:i * 20 + 16].hex().upper(),
                         "ammo_bits": raw[i * 20 + 8:i * 20 + 12].hex().upper(),
                         "address_plan": level_address_plan(raw[i * 20 + 17])} for i in range(32)],
            "qualification": "Snapshot/address plans only. No live definitions, numeric runtime maximum, valid mask, ownership or event history inferred; all original bits preserved."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
