"""Read-only exact-build pack/boot saved words and named native Lua bindings."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("bindings", Path(__file__).with_name("Inspect-TodWeaponBindings.py"))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)


def enum_exports(elf):
    """Bounded straight-line native export sequence; never execute Lua/game code."""
    floating, name, result = {}, None, {"pack": [], "boot": []}
    for address, word in elf.instructions(0x2A4AC, 0x2A658):
        opcode, target, base = word >> 26, word >> 21 & 31, word >> 16 & 31
        if opcode == 48 and base == 2:
            slot = 0x88FF38 + BINDINGS.signed(word & 65535, 16)
            floating[target] = (struct.unpack(">f", elf.read(slot, 4))[0], slot)
        elif opcode == 63 and (word >> 1 & 1023) == 72:
            floating[target] = floating[word >> 11 & 31]
        elif opcode == 32 and target == 4 and base == 2:
            slot = 0x88FF38 + BINDINGS.signed(word & 65535, 16)
            pointer = elf.u32(slot)
            name = (elf.string(pointer), pointer, slot)
        elif opcode == 18:
            if BINDINGS.branch_target(word, address) != 0x12990 or not word & 1:
                raise ValueError("Unexpected native enum export call")
            if name is None or 1 not in floating:
                raise ValueError("Unresolved enum export arguments")
            kind = "boot" if name[0].startswith("BOOT_") else "pack" if name[0].startswith("PACK_") else None
            if kind:
                value, value_slot = floating[1]
                if not value.is_integer():
                    raise ValueError("Noninteger pack/boot enum")
                result[kind].append({"enum": name[0], "id": int(value), "name_va": hex(name[1]),
                                     "name_slot_va": hex(name[2]), "value_slot_va": hex(value_slot),
                                     "call_va": hex(address)})
            name = None
            floating = {r: v for r, v in floating.items() if r >= 14}
    expected = {"boot": ["BOOT_NORMAL", "BOOT_GRIND", "BOOT_GRAV", "BOOT_CHARGE", "BOOT_TYPE_COUNT"],
                "pack": ["PACK_HELI", "PACK_THRUSTER", "PACK_HYDRO", "PACK_WING", "PACK_TYPE_COUNT"]}
    for kind, names in expected.items():
        if [(x["enum"], x["id"]) for x in result[kind]] != list(zip(names, range(5))):
            raise ValueError("Pack/boot enum catalog changed")
    return result


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    for address, expected in {
            0x888624: 0x101EFB20, 0x8958C8: 0x101EFB20,
            0x27A44: 0x9069043C, 0x27A54: 0x90690438, 0x27A78: 0x90690438,
            0x26F80: 0x90AB0440, 0x26FA4: 0x80690440, 0x26FB4: 0x8069043C,
            0x1E228C: 0x8069043C, 0x1E229C: 0x80690440,
            0x1F1DB0: 0x80C90438, 0x1F1DB4: 0x2C860001,
            0x1F2D4C: 0x83A30438, 0x1F2D50: 0x2F9D0001,
            0x3CF1AC: 0x901F043C}.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Hero auxiliary evidence changed at {address:#x}")
        keep(address, 4)
    api_records = []
    for registration, expected, wrapper, target in (
            (0x88952C, "get_pack_type", 0x2FC58, 0x26FB0),
            (0x889534, "get_boot_type", 0x2FBA0, 0x26FA0),
            (0x88953C, "set_pack_type", 0x2FAE8, 0x27A30),
            (0x889544, "set_boot_type", 0x2FA30, 0x26F60)):
        pointer, descriptor = struct.unpack(">II", elf.read(registration, 8))
        if elf.string(pointer) != expected or struct.unpack(">II", elf.read(descriptor, 8)) != (wrapper, 0x88FF38):
            raise ValueError("Named pack/boot Lua registration changed")
        end = elf.functions[elf.functions.index(wrapper) + 1]
        if not any(BINDINGS.branch_target(w, a) == target and w & 1 for a, w in elf.instructions(wrapper, end)):
            raise ValueError("Pack/boot wrapper target changed")
        for a, size in ((registration, 8), (pointer, len(expected) + 1), (descriptor, 8), (wrapper, end - wrapper)):
            keep(a, size)
        api_records.append({"name": expected, "registration_va": hex(registration), "name_va": hex(pointer),
                            "descriptor_va": hex(descriptor), "wrapper_va": hex(wrapper), "native_va": hex(target)})
    for address in (0x26F60, 0x26FA0, 0x26FB0, 0x27A30, 0x1E2288, 0x1E2298, 0x35DC80):
        end = elf.functions[elf.functions.index(address) + 1]
        keep(address, end - address)
    keep(0x1F1D58, 0xD8)
    keep(0x1F2C50, 0x148)
    keep(0x2A4AC, 0x1AC)
    catalogs = enum_exports(elf)
    for entries in catalogs.values():
        for entry in entries:
            keep(int(entry["name_va"], 0), len(entry["enum"]) + 1)
            keep(int(entry["name_slot_va"], 0), 4)
            keep(int(entry["value_slot_va"], 0), 4)
    report = {
        "confidence": "named-native-API-and-code-backed",
        "warning": "Exact USA v02.00 pack/boot API names and static saved-state access, not proof of safe edits, gameplay-tested equipment effects, player-facing names, or applicability to another build. TYPE_COUNT is an enum sentinel, not equipment.",
        "fields": [
            {"offset": "0x438", "name": "pack_dispatch_selector", "type": "u32 BE",
             "rule": "Native27A30 sets0 if its incoming64-bit argument is0, otherwise1. Known consumers1F1D58/1F2C50 use an exact saved-word==1 test, not arbitrary-nonzero truthiness. Raw inconsistent/nonboolean values are preserved."},
            {"offset": "0x43c", "name": "pack_type", "type": "u32 BE", "getter_va": "0x26fb0",
             "hero_getter_va": "0x1e2288", "rule": "Named get_pack_type exposes the saved unsigned word. Native set_pack_type27A30 stores low32 bits of its input and updates438 from the original64-bit argument's zero test."},
            {"offset": "0x440", "name": "boot_type", "type": "u32 BE", "getter_va": "0x26fa0",
             "hero_getter_va": "0x1e2298", "rule": "Named get_boot_type exposes the saved unsigned word. Native set_boot_type26F60 ignores its incoming argument and always stores0; this exact build does not support inferring a general boot-type setter from its name."}],
        "enum_catalogs": catalogs,
        "lua_bindings": api_records,
        "setter_conversion": "Both Lua setters accept a checked numeric argument and use fctiwz to obtain an integer before calling the native accessor. No unverified out-of-range/NaN conversion is emulated and no game code is executed.",
        "dispatch_consumers": [
            {"function_va": "0x1f1d58", "saved_read_va": "0x1f1db0", "when_exactly_one_message": "0x58d", "otherwise_message": "0x58e"},
            {"function_va": "0x1f2c50", "saved_read_va": "0x1f2d4c", "when_exactly_one_message": "0x58c", "otherwise_message": "0x58b"}],
        "dispatch_caveat": "Consumer dispatch is additionally gated by runtime state. Message numbers are numeric native dispatch IDs, not resolved animation names or confirmation of which movement occurs.",
        "initializer_va": "0x35dc80", "initializer_rule": "35DC80 initializes all three saved words to0. Restart path3CF1AC also explicitly clears saved43C; this local store is not a complete restart specification.",
        "excluded_lookalike": "3D5354 stores at438/43C/440/484 in a different monolithic-config object, not these saved fields; matching displacement alone is not save evidence.",
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        if Path(save_path).stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save size")
        data = Path(save_path).read_bytes()
        if any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        words = []
        for field in report["fields"]:
            offset = int(field["offset"], 0)
            value = struct.unpack_from(">I", data, offset)[0]
            kind = "pack" if field["name"] == "pack_type" else "boot" if field["name"] == "boot_type" else None
            label = next((x["enum"] for x in catalogs[kind] if x["id"] == value and not x["enum"].endswith("TYPE_COUNT")), None) if kind else None
            words.append({"name": field["name"], "offset": field["offset"], "raw_hex": data[offset:offset + 4].hex().upper(), "value": value, "native_enum": label})
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(), "words": words,
                                      "selector_equals_one": words[0]["value"] == 1,
                                      "warning": "Saved raw values are shown independently; inspection does not repair selector/type mismatches or execute the setters."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path, help="Plaintext working copy; read-only")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2, allow_nan=False))
