"""Read-only exact-build hero XP publication, fractional carry and restore flow.

Previews are bounded arithmetic/control-flow demonstrations, not game emulation.
They assume round-to-nearest-even for float32 operations; live FPSCR is unknown.
"""
import argparse
import hashlib
import math
from pathlib import Path
import runpy
import struct
import json

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))


def u32(value):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("Expected an unsigned32 integer")
    return value


def finite(value, maximum):
    if type(value) not in (int, float) or not 0 <= value <= maximum or not math.isfinite(value):
        raise ValueError("Outside the finite nonnegative preview domain")
    return float(value)


def f32(value):
    return struct.unpack(">f", struct.pack(">f", value))[0]


def publication_preview(incoming, remainder=0.0):
    """Leaf23E090 only; incoming FPR is not unconditionally narrowed at entry."""
    incoming = finite(incoming, 0x100000000)
    remainder = finite(remainder, 0x100000000)
    remainder = f32(remainder)
    stored = math.trunc(incoming) & 0xFFFFFFFF
    residual = f32(incoming - f32(stored))
    if residual > 0:
        remainder = f32(remainder + residual)
    carried = remainder > 1.0
    if carried:
        remainder = f32(remainder - 1.0)
        stored = (stored + 1) & 0xFFFFFFFF
    return {"saved_xp": stored, "remainder": remainder, "residual": residual,
            "carried_once": carried, "threshold_input": incoming,
            "assumption": "Finite bounded leaf inputs; float32 nearest-even; not native nonfinite/FPSCR emulation."}


def restore_preview(saved):
    saved = u32(saved)
    incoming = f32(saved)
    result = publication_preview(incoming)
    return {"input_saved_xp": saved, "float32_input": incoming,
            "integer_exactly_representable": incoming == saved, **result}


def script_set_preview(incoming, remainder=0.0):
    """Admitted28A9B0 numeric conversion, not handle/type validation emulation."""
    incoming = finite(incoming, 0xFFFFFFFF)
    low32 = math.trunc(incoming) & 0xFFFFFFFF
    return {"script_low32": low32, **publication_preview(f32(low32), remainder)}


def advancement_preview(incoming, old_level, thresholds):
    """Injected synthetic100-word table; never substitutes for runtime BSS."""
    incoming = finite(incoming, 0x100000000)
    if type(old_level) is not int or not 0 <= old_level <= 255:
        raise ValueError("Expected a runtime level byte")
    if type(thresholds) not in (list, tuple) or len(thresholds) != 100:
        raise ValueError("Expected100 supplied unsigned thresholds")
    thresholds = [u32(value) for value in thresholds]
    level = old_level
    while level < 99:
        threshold = f32(thresholds[level + 1])
        if threshold <= 0 or incoming < threshold:
            break
        level += 1
    return {"level_before_callbacks": level, "changed": level != old_level,
            "assumption": "Supplied synthetic table only; no callback, health or runtime table emulation."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}
    # Assembly, not decompiler expressions: frsp also affects the integer back-conversion.
    checks = {
        0x23E090: 0xFC800890, 0x23E098: 0xC1827BBC,
        0x23E0B4: 0xFC60265E, 0x23E0B8: 0xD8610110,
        0x23E0BC: 0xE9610110, 0x23E0C0: 0x79600020,
        0x23E0C4: 0xF8010110, 0x23E0C8: 0xC8410110,
        0x23E0CC: 0xFDA0169C, 0x23E0D0: 0xFC006818,
        0x23E0D4: 0xEDA10028, 0x23E0D8: 0xFF8D6000,
        0x23E0DC: 0x409D0010, 0x23E0E0: 0xC0C31B68,
        0x23E0E4: 0xECAD302A, 0x23E0E8: 0xD0A31B68,
        0x23E0EC: 0x813F1A68, 0x23E0F0: 0xC1627BC4,
        0x23E0F4: 0x91690418, 0x23E0F8: 0xC01F1B68,
        0x23E0FC: 0xFC005800, 0x23E100: 0x4081001C,
        0x23E104: 0xECE05828, 0x23E108: 0x817F1A68,
        0x23E10C: 0xD0FF1B68, 0x23E110: 0x80AB0418,
        0x23E114: 0x38650001, 0x23E118: 0x906B0418,
        0x23E11C: 0x897F1B61, 0x23E120: 0x5568063E,
        0x23E124: 0x28880062, 0x23E128: 0x41850174,
        0x23E130: 0x83A27BC8, 0x23E134: 0x394C0004,
        0x23E13C: 0x7CDD382E, 0x23E148: 0xFD004E9C,
        0x23E14C: 0xFC004018, 0x23E150: 0xFF010000,
        0x23E154: 0x4F59D382, 0x23E158: 0x409A0144,
        0x23E15C: 0xFF806000, 0x23E160: 0x409D013C,
        0x23E164: 0xFDA06090, 0x23E168: 0x48000030,
        0x23E170: 0x7C7D482E, 0x23E17C: 0xFD80569C,
        0x23E180: 0xFC006018, 0x23E184: 0xFC810000,
        0x23E188: 0x4CC53382, 0x23E18C: 0x4086012C,
        0x23E190: 0xFF006800, 0x23E194: 0x40990124,
        0x23E198: 0x380B0001, 0x23E1A8: 0x2C0A0063,
        0x23E1B0: 0x981F1B61, 0x23E1B8: 0x4082FFB8,
        0x23E230: 0x881F1B61, 0x23E23C: 0x39440190,
        0x23E244: 0x7D7D3C2E, 0x23E248: 0xD17F1788,
        0x23E24C: 0xD17F1784, 0x23E2B8: 0x7F885000,
        0x23E2BC: 0x419EFFE0, 0x23E2FC: 0x4BFFFF34,
        0x23E334: 0x4BFFFEFC,
        0x23E67C: 0x3BA00000, 0x23E73C: 0x81227C00,
        0x23E740: 0x38600000, 0x23E744: 0x913F1A68,
        0x23E748: 0x907F1B68, 0x23E74C: 0x9BBF1B61,
        0x23E754: 0x80890418, 0x23E75C: 0xF88100C0,
        0x23E760: 0xC82100C0, 0x23E764: 0xFC000E9C,
        0x23E768: 0xFC200018,
        0x28A9C4: 0xFFE00890, 0x28AA94: 0xFC60F890,
        0x28AA9C: 0xFC401E5E, 0x28AAA0: 0xD8410070,
        0x28AAA4: 0xE9610070, 0x28AAA8: 0x796A0020,
        0x28AAAC: 0xF9410070, 0x28AAB0: 0xC8210070,
        0x28AAB4: 0xFC000E9C, 0x28AAB8: 0xFC200018,
        0x252C7C: 0x3C42FFFF, 0x252C80: 0x38420018,
        0x897AF4: 0, 0x897AFC: 0x3F800000,
        0x897B00: 0x101B9EE8, 0x897B38: 0x101EFB20,
    }
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Hero XP evidence changed at {address:#x}")
        guards[address] = elf.read(address, 4)
    for address, target, linked in ((0x23E76C, 0x23E090, True),
                                   (0x28AABC, 0x252C78, True),
                                   (0x252C84, 0x23E090, False),
                                   (0x23E228, 0x1E06C8, True),
                                   (0x23E2F4, 0x1E06C8, True),
                                   (0x23E32C, 0x1E06C8, True)):
        word = elf.u32(address)
        if BINDINGS["branch_target"](word, address) != target or bool(word & 1) != linked:
            raise ValueError("Hero XP call/thunk target changed")
        guards[address] = elf.read(address, 4)
    if elf.descriptors[0x23E090] != 0x88FF38 or elf.descriptors[0x23E650] != 0x88FF38:
        raise ValueError("Hero XP TOC provenance changed")
    for function in (0x23E090, 0x23E650, 0x28A9B0):
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    report = {
        "confidence": "native-code-backed-exact-build",
        "warning": "USA BCUS98127 v02.00 only. Static flow and detached snapshot, not safe edit bounds, gameplay acceptance or cross-build compatibility. Runtime remainder/level/health are not saved offsets.",
        "publication": {
            "leaf_va": "0x23e090", "saved_xp_offset": "0x418", "saved_type": "u32 BE",
            "saved_pointer_runtime_offset": "0x1a68", "remainder_runtime_offset": "0x1b68",
            "conversion": "fctidz truncates incoming FPR toward zero to signed64; stw publishes its low32. The leaf does not unconditionally narrow incoming f1 on entry.",
            "residual": "fsubs(incoming, frsp(fcfid(zero-extended truncated low32))); only a positive residual is added with fadds to runtime remainder1B68.",
            "carry": "Strict remainder>1, not>=1. Subtract1 once with fsubs and increment saved418 once modulo32. No carry loop; exactly1 remains pending. Integer incoming can still carry a pre-existing runtime remainder>1.",
            "constants": {"zero_slot_va": "0x897af4", "one_slot_va": "0x897afc", "toc": "0x88ff38"},
        },
        "advancement": {
            "runtime_level_offset": "0x1b61", "threshold_table_va": "0x101b9ee8",
            "input": "Threshold comparisons use original incoming f1, not saved418 after the carry increment.",
            "rule": "Only advances from old runtime level while unsigned table[level+1], converted through frsp, is positive and<=incoming. Positive thresholds need not be strictly increasing. Stops at99; old level>=99 skips progression after XP publication. No downward level store in this leaf.",
            "restore_difference": "Binding23E650 clears runtime level and remainder before restoring saved418; lowering XP in a running hero is therefore not equivalent to rebinding from a save.",
            "health": "Changed-level paths call1E06C8 before rereading runtime level at23E230 and loading float table+190+4*level into1788/1784. Callback mutations are not emulated; numerical level/capacity cannot be inferred from this ELF BSS table or save alone.",
        },
        "entry_paths": {
            "restore": "23E650: saved pointer1A68, clears1B68/1B61, lwz saved418, fcfid then frsp, call23E090. This restores through float32 and republishes XP, not a guaranteed bit-exact u32 copy.",
            "script_set": "Admitted hero_set_xp native28A9B0 truncates its numeric input with fctidz, takes low32, converts through fcfid/frsp, then thunk252C78 tail-branches23E090. Ordinary positive script fractions are discarded before the leaf; handle/type validation remains separate.",
            "precision": "All nonnegative integers through2^24 are float32-exact; above that, some but not all are exact. Near-u32-maximum values can round to2^32 under nearest-even, so low32 wrap and residual/carry matter. No inferred safe editing range.",
            "preview_scope": "Synthetic previews assume nearest-even float32 with finite bounded inputs. Runtime FPSCR, nonfinite inputs, conversion exceptions, callers/callbacks and actual threshold values are not reconstructed.",
        },
        "recommended_annotations": [
            {"va": "0x23e100", "name": "TOD_hero_xp_strict_single_carry", "kind": "comment", "comment": "Hero XP leaf: remainder<=1 skips carry; otherwise subtract1 and increment saved418 once. No carry loop or >=1 boundary. Runtime1B68 is not serialized XP."},
            {"va": "0x23e150", "name": "TOD_hero_xp_original_input_threshold", "kind": "comment", "comment": "Threshold comparison uses original incoming f1, not saved418 after carry. Positive threshold and old level<99 required; loop only advances runtime1B61."},
            {"va": "0x23e768", "name": "TOD_hero_xp_restore_float32_conversion", "kind": "comment", "comment": "Saved unsigned XP418 is converted through fcfid/frsp after runtime level/remainder reset, then23E090 republishes low32 and checks carry. Not universally bit-exact above2^24; live FPSCR unknown."},
            {"va": "0x28aab8", "name": "TOD_hero_xp_script_integer_float32_conversion", "kind": "comment", "comment": "Admitted hero_set_xp truncates numeric input to signed64, takes low32 and converts through frsp before252C78→23E090. Ordinary script fractions do not reach leaf accumulator. No handle/type safety or edit range inferred."},
        ],
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())],
    }
    if save_path is not None:
        path = Path(save_path)
        data = path.read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        saved = struct.unpack_from(">I", data, 0x418)[0]
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "saved_xp": saved, "raw_hex": data[0x418:0x41C].hex().upper(),
            "nearest_even_restore_preview": restore_preview(saved),
            "runtime_remainder": None, "runtime_level": None, "current_health": None,
            "qualification": "XP is an actual saved observation; arithmetic preview is not a gameplay reload test. Runtime remainder, thresholds, level and health cannot be recovered from this snapshot."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path, help="Detached plaintext only; read-only")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2, allow_nan=False))
