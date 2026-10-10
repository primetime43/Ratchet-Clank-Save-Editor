"""Read-only exact-build hero health regeneration and checkpoint ammo lifecycle."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("bindings", Path(__file__).with_name("Inspect-TodWeaponBindings.py"))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    checks = {
        0x8955A0: 0x84BE30, 0x84BE54: 0x868D78,
        0x868D78: 0x23E368, 0x868D7C: 0x88FF38,
        0x84A41C: 0x8660E0, 0x8660E0: 0x1E3380, 0x8660E4: 0x88FF38,
        0x23E3C8: 0x2C84006C, 0x23E3CC: 0x38691780,
        0x23E744: 0x913F1A68, 0x23E74C: 0x9BBF1B61,
        0x23E754: 0x80890418, 0x23E0F4: 0x91690418,
        0x23E1B0: 0x981F1B61, 0x23E23C: 0x39440190,
        0x23E244: 0x7D7D3C2E, 0x23E248: 0xD17F1788,
        0x23E24C: 0xD17F1784, 0x897B00: 0x101B9EE8,
        0x897B38: 0x101EFB20, 0x897B3C: 0x10330610,
        0x8A1928: 0x10330610, 0x8A1934: 0x101EFB20,
        0x35D100: 0x3BA00020, 0x35D160: 0x1F7D0484,
        0x35D168: 0x39450008, 0x35D178: 0x394A0014,
        0x35D150: 0x38E80050, 0x35D17C: 0x39080004,
        0x35D3B8: 0x39000020, 0x35D3CC: 0x1C860484,
        0x35D3D0: 0x39650050, 0x35D3DC: 0x39490008,
        0x35D3EC: 0x394A0014, 0x35D3F8: 0xFC206028,
        0x35D3FC: 0xFDA1602E, 0x35D400: 0xD1AC0000,
        0x241010: 0xC1831784, 0x241020: 0xC01F1788,
        0x24102C: 0xFDA2082E, 0x241038: 0xD1BF1784,
        0x465DFC: 0xD19D0008,
        0x8A5EF4: 0, 0x2893C0: 0x3880006C, 0x2893E0: 0xC0290004,
        0x23E788: 0x881C00EF,
    }
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Health/checkpoint native evidence changed at {address:#x}")
        keep(address, 4)
    for function in (0x1E3380, 0x23E368, 0x23E090, 0x23E650,
                     0x289358, 0x35CF40, 0x35D358, 0x465DC0, 0x240FF8):
        end = elf.functions[elf.functions.index(function) + 1]
        keep(function, end - function)
    for address, target in ((0x1E33A4, 0x23E368), (0x23E76C, 0x23E090)):
        word = elf.u32(address)
        if not word & 1 or BINDINGS.branch_target(word, address) != target:
            raise ValueError("Health dispatcher/XP restore call changed")
        keep(address, 4)
    # These are the three successful vendor-operation paths, not every ammo writer.
    callers = []
    for function in (0x2D2990, 0x2D2B90, 0x2D2D38):
        end = elf.functions[elf.functions.index(function) + 1]
        calls = [address for address, word in elf.instructions(function, end)
                 if word & 1 and BINDINGS.branch_target(word, address) == 0x35D358]
        if len(calls) != 1:
            raise ValueError("Checkpoint ammo vendor merge call changed")
        keep(function, end - function)
        callers.append({"function_va": hex(function), "merge_call_va": hex(calls[0])})
    keep(0x13DD0, 16)
    if BINDINGS.branch_target(elf.u32(0x13DDC), 0x13DDC) != 0x465DC0:
        raise ValueError("Checkpoint ammo restore thunk changed")
    report = {
        "confidence": "native-code-backed-exact-build",
        "warning": "Exact USA v02.00 static paths and detached save observations only. No safe-edit permission, complete load specification, gameplay acceptance, or cross-build guarantee. Runtime health/checkpoint fields are not GAME.SAV offsets.",
        "health": {
            "named_accessor_va": "0x289358", "float_attribute_id": "0x6c",
            "base_hero_vtable_va": "0x84be30", "float_callback_va": "0x23e368",
            "subclass_callback_va": "0x1e3380", "attribute_runtime_offset": "0x1780",
            "current_health_runtime_offset": "0x1784", "capacity_runtime_offset": "0x1788",
            "rule": "Named hero_get_health reaches float attribute6C. Base callback23E368 returns hero+1780 for6C; subclass1E3380 delegates to it except attribute503. Getter reads attribute+4, hence runtime hero+1784. These are runtime hero members, not offsets into serialized state.",
            "capacity_rule": "Native240FF8 adds incoming float to current health1784, then fsub/fsel clamps the result against1788 before storing1784. For finite values this proves1788 is the health upper bound; this path does not add a zero lower clamp or normalize nonfinite inputs.",
        },
        "xp_restore": {
            "saved_xp_offset": "0x418", "saved_xp_type": "u32 BE",
            "bind_restore_va": "0x23e650", "progression_va": "0x23e090",
            "runtime_level_offset": "0x1b61", "runtime_fractional_xp_offset": "0x1b68",
            "threshold_table_va": "0x101b9ee8", "threshold_table_slot_va": "0x897b00",
            "threshold_index_rule": "u32 table[old_level+1], levels0..99; next threshold must be positive and not exceed incoming float XP. Progression can advance multiple levels; it does not unconditionally reset every runtime health value.",
            "health_entry_rule": "On changed-level path, loads float at table+190+4*new_level and writes both runtime1788 and1784. Binding23E650 first clears runtime level1B61 and fractionalXP1B68, consumes saved418 then invokes23E090.",
            "boundary": "This proves an XP-driven health refresh on the qualifying changed-level setup/progression path, not a dedicated serialized current-health word or unconditional healing for XPzero/disabledthresholds. The table is runtime BSS in this ELF; no numerical level or capacity is inferred from the supplied save alone.",
        },
        "checkpoint": {
            "runtime_base_va": "0x10330610", "state_base_va": "0x101efb20",
            "save_size": "0x906f0", "relative_to_state_base": "0x140af0",
            "valid_byte_offset": "0xef", "capture_va": "0x35cf40",
            "ammo_bank_offset": "0x50", "ammo_bank_stride": "0x80", "weapon_count": 32,
            "inventory_bank_stride": "0x484", "inventory_record_stride": "0x14", "ammo_member_offset": "0x8",
            "capture_rule": "For each iterated hero/player index at object+20, capture copies32 saved inventory ammo floats: state+player*484+weapon*14+8 into runtime checkpoint+50+player*80+weapon*4. Capture also writes position/orientation/flags, but does not copy current health1784 into this ammo bank.",
            "merge_va": "0x35d358", "merge_rule": "For each iterated player and32 weapons, fsub/fsel selects current saved ammo when current-checkpoint is nonnegative, otherwise the checkpoint value. For finite values this is max(current saved ammo, checkpoint ammo). Native NaN/signed-zero behavior is not sanitized or replaced by a Python max emulator.",
            "vendor_merge_callers": callers,
            "vendor_scope": "The three traced vendor functions call the merge after their qualifying successful acquisition/refill/payment path. This is not a complete list of ammo modifications or a guarantee every refill is checkpoint-retained.",
            "restore_rule": "Hero bind23E650 checks runtime checkpoint validbyteEF, then loops32 ammo floats from checkpoint+50+hero_index*80 through thunk13DD0 to465DC0 using the hero's saved inventory record base. This setter clamps through the definition/level/modifier-dependent maximum463DE0 and native zero fallback, not a verbatim bit copy. Therefore checkpoint setup can overwrite previously saved ammo; runtime checkpoint data is not serialized by the906F0 state copy.",
            "boundary": "Bank0 observations concern the first32 inventory records in the supplied plaintext. Runtime iteration/player indices, checkpoint validity and opaque flags are not present in this file; no active checkpoint or respawn state is inferred.",
        },
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())],
    }
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save size")
        data = path.read_bytes()
        if any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        ammo = []
        for i in range(32):
            offset = i * 0x14 + 8
            value = struct.unpack_from(">f", data, offset)[0]
            ammo.append({"id": i, "offset": hex(offset), "raw_hex": data[offset:offset + 4].hex().upper(),
                         "value": value if math.isfinite(value) else None,
                         "nonfinite": not math.isfinite(value)})
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "saved_hero_xp": struct.unpack_from(">I", data, 0x418)[0], "inventory_bank0_ammo": ammo,
            "current_health": None, "runtime_level": None, "capacity": None, "active_checkpoint": None,
            "warning": "Actual serialized XP/ammo only; no current-health/level/capacity/checkpoint inference. Unknown and nonfinite ammo bits are preserved without normalization."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path, help="Plaintext working copy; read-only")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2, allow_nan=False))
