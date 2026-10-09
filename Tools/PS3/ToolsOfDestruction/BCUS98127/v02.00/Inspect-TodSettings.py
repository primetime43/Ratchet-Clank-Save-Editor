"""Read-only exact-build settings/load-destination decoder; stdout only."""
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

# Internal names are backed by the named Lua registrations, not guessed menu labels.
# name, storage type, getter, setter, get registration, set registration
FIELDS = [
    ("camera_x_inverted", "bool32", 0x26CA8, 0x26C98, 0x88973C, 0x889744),
    ("camera_y_inverted", "bool32", 0x26C70, 0x26C60, 0x88974C, 0x889754),
    ("camera_speed", "f32", 0x26C50, 0x276A8, 0x88975C, 0x889764),
    ("look_x_inverted", "bool32", 0x26C28, 0x26C18, 0x88976C, 0x889774),
    ("look_y_inverted", "bool32", 0x26BF0, 0x26BE0, 0x88977C, 0x889784),
    ("control_scheme_index", "u32", 0x27220, 0x271B0, 0x88963C, 0x889644),
    ("voice_volume", "f32", 0x26E00, 0x276D0, 0x8896C4, 0x8896CC),
    ("sound_effects_volume", "f32", 0x26BB0, 0x24E90, 0x8896A4, 0x8896AC),
    ("music_volume", "f32", 0x26E10, 0x27718, 0x8896B4, 0x8896BC),
    ("help_text_enabled", "bool8", 0x26DF0, 0x26DB8, 0x8896D4, 0x8896DC),
    ("subtitles_enabled", "bool8", 0x26DA8, 0x26D98, 0x8896E4, 0x8896EC),
    ("quick_select_pauses", "bool8", 0x26D88, 0x26D78, 0x8896F4, 0x8896FC),
    ("sixaxis_enabled", "bool8", 0x26BC0, 0x26BD0, 0x889794, 0x88978C),
    ("rumble_enabled", "bool8", 0x26D68, 0x26D18, 0x889704, 0x88970C),
    ("surround_enabled", "bool8", 0x26D08, 0x26CD0, 0x88971C, 0x889724),
]


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)  # Exact size/hash verified before any address read.
    guards, named = {}, {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    def function(address):
        end = elf.functions[elf.functions.index(address) + 1]
        keep(address, end - address)
        return list(elf.instructions(address, end))

    def binding(slot, native=None):
        if slot in named:
            return named[slot]
        pointer, descriptor = struct.unpack(">II", elf.read(slot, 8))
        name = elf.string(pointer)
        wrapper = elf.u32(descriptor)
        instructions = function(wrapper)
        if native is not None and not any(word >> 26 == 18 and word & 1 and
                BINDINGS.branch_target(word, address) == native for address, word in instructions):
            raise ValueError(f"Named wrapper {name} no longer calls its expected native function")
        keep(slot, 8)
        keep(descriptor, 8)
        keep(pointer, len(name) + 1)
        item = {"name": name, "name_va": hex(pointer), "registration_slot_va": hex(slot),
                "wrapper_va": hex(wrapper)}
        if native is not None:
            item["native_va"] = hex(native)
        named[slot] = item
        return item

    def storage(getter, opcode):
        instructions = function(getter)
        first = instructions[0][1]
        if first >> 26 != 32 or first >> 16 & 31 != 2:
            raise ValueError("Getter no longer starts with a TOC pointer load")
        slot = elf.descriptors[getter] + BINDINGS.signed(first & 65535, 16)
        if elf.u32(slot) != 0x101EFB20:
            raise ValueError("Getter no longer targets serialized state")
        keep(slot, 4)
        base_register = first >> 21 & 31
        additions = [word for _, word in instructions if word >> 26 == 15 and word >> 16 & 31 == base_register]
        if len(additions) != 1:
            raise ValueError("Ambiguous getter base arithmetic")
        addition = additions[0]
        loads = [word for _, word in instructions if word >> 26 == opcode and word >> 16 & 31 == addition >> 21 & 31]
        if len(loads) != 1:
            raise ValueError("Ambiguous getter field access")
        return (BINDINGS.signed(addition & 65535, 16) << 16) + BINDINGS.signed(loads[0] & 65535, 16)

    fields = []
    for name, kind, getter, setter, get_slot, set_slot in FIELDS:
        offset = storage(getter, 48 if kind == "f32" else 34 if kind == "bool8" else 32)
        function(setter)
        get_api, set_api = binding(get_slot, getter), binding(set_slot, setter)
        fields.append({"name": name, "offset": hex(offset), "type": kind,
            "getter_va": hex(getter), "setter_va": hex(setter),
            "get_api": get_api["name"], "set_api": set_api["name"]})

    # Interpret only the simple verified initializer (li/lfs/stw/stb/stfs/blr).
    registers, floats, defaults = {}, {}, {}
    initializer = 0x35EE40
    for address, word in function(initializer):
        if word == 0x4E800020:
            break  # Following alignment nops are not initializer operations.
        op, rt, ra, immediate = word >> 26, word >> 21 & 31, word >> 16 & 31, BINDINGS.signed(word & 65535, 16)
        if op == 14 and ra == 0:
            registers[rt] = immediate
        elif op == 48 and ra == 2:
            slot = elf.descriptors[initializer] + immediate
            keep(slot, 4)
            floats[rt] = elf.read(slot, 4)
        elif op in (36, 38, 52) and ra == 3:
            defaults[hex(0x114A8 + immediate)] = (floats[rt] if op == 52 else
                registers[rt].to_bytes(1 if op == 38 else 4, "big", signed=False)).hex().upper()
        elif word != 0x4E800020:
            raise ValueError(f"Unsupported initializer instruction at {address:#x}")

    levels = []
    keep(0x10062F7C, 19 * 4)
    for i in range(19):
        pointer = elf.u32(0x10062F7C + i * 4)
        name = elf.string(pointer)
        keep(pointer, len(name) + 1)
        levels.append({"id": i, "internal_name": name, "name_va": hex(pointer)})
    saved_load = storage(0x2D1490, 32)
    next_level = storage(0x36AF0, 32)
    for slot, native in ((0x89D940, 0x27BAD0), (0x89D948, 0x27A818), (0x889CA8, 0x36AF0),
            (0x889714, 0x24C90), (0x88972C, 0x24C98), (0x889734, 0x24CA0),
            (0x889634, 0x24C48), (0x88964C, 0x28010),
            (0x89D980, 0x27B258), (0x89D988, 0x27B128), (0x89D990, 0x27B108),
            (0x89D998, 0x2788E8), (0x89DF7C, 0x289358)):
        binding(slot, native)
        function(native)
    for address in (0x35D9A0, 0x2D16A0, 0x2D08D8, 0x2D0880, 0x35E508,
            0x7FC98, 0x5ADEF0, 0x35CF40, 0x27B218, 0x20F3F0, 0x2108D8,
            0x6A8EE0, 0x668770):
        function(address)
    keep(0x106A0, 16)
    # Two consumers establish use, but not a named gameplay/menu meaning.
    for address, expected in {0x89679C: 0x101EFB20, 0x896858: 0x101EFB20,
            0x20F3FC: 0x83A26864, 0x20F408: 0x3D7D0001, 0x20F420: 0x812B14C0,
            0x20F430: 0x987F0024, 0x2108E0: 0x80826920, 0x2108F0: 0x3D240001,
            0x210904: 0x816914C0, 0x210920: 0x98DF003F}.items():
        if elf.u32(address) != expected:
            raise ValueError("Unnamed option consumer no longer matches saved-state addressing")
        keep(address, 4)
    for address, expected in {0x898FB0: 0x10330610, 0x8A1928: 0x10330610,
            0x88865C: 0, 0x888644: 0x3F800000}.items():
        if elf.u32(address) != expected:
            raise ValueError("Runtime checkpoint or float bounds changed")
        keep(address, 4)
    report = {"confidence": "code-backed", "warning": "Exact USA v02.00 code and read-only plaintext observations; no runtime acceptance or new editing permissions.",
        "block": {"base": "0x114a8", "size": "0x30", "initializer_va": hex(initializer),
            "fields": fields, "default_bytes": defaults,
            "unknown_word_offset": "0x114c0", "unknown_tail_offset": "0x114d6",
            "unknown_word_consumers": [
                {"native_va": "0x20f3f0", "state_pointer_slot_va": "0x89679c", "runtime_flag_offset": "0x24"},
                {"native_va": "0x2108d8", "state_pointer_slot_va": "0x896858", "runtime_flag_offset": "0x3f"}],
            "unknown_word_usage": "Both consumers set their runtime flag when saved114C0 is zero and use it to choose between runtime modes0x0F/0x10. This proves the word is used, not what the modes or option are called; do not infer a named control setting.",
            "lua_boolean_conversion": "Byte getter wrappers call106A0 -> 6A8EE0 -> 668770; the leaf writes normalized0/1 to a Lua stack value by comparing its input with zero. Saved raw flags are not normalized by inspection.",
            "semantics": "Boolean word getters test nonzero; byte getters preserve the byte and named wrappers expose boolean results. Float setters clamp ordinary finite inputs to0..1; getters preserve raw floats. Control scheme is an index, not an asserted valid edit range. Unknown word114C0 defaults to1; bytes114D6/114D7 are not proven padding.",
            "stub_apis": "is_rumble_connected returns1; get_button_layout returns0; set_button_layout is a no-op. These do not establish extra saved flags or a button-layout field."},
        "level_selection": {"saved_load_offset": hex(saved_load), "next_level_offset": hex(next_level),
            "saved_load_getter_va": "0x2d1490", "saved_load_setter_va": "0x27bad0",
            "next_getter_va": "0x36af0", "next_setter_va": "0x27a818", "catalog": levels,
            "warning": "Saved load destination and next-level selection are not necessarily the current runtime planet or SFO subtitle.906E4 remains unresolved. Named runtime current-level API reads a separate runtime string. Unknown IDs are retained."},
        "runtime_only": {"checkpoint_va": "0x10330610", "checkpoint_writer_va": "0x35cf40",
            "checkpoint_valid_byte": "0xef", "checkpoint_saved_level_offset": "0x40",
            "warning": "Checkpoint struct lies outside the906F0 serialized state interval. Position vectors and valid flags are runtime evidence, not mapped save offsets. hero_get_health follows a runtime object float attribute lookup for ID0x6C; no saved health offset is confirmed."},
        "named_bindings": sorted(named.values(), key=lambda item: int(item["registration_slot_va"], 0)),
        "instruction_guards": [{"va": hex(address), "bytes": raw.hex().upper()} for address, raw in sorted(guards.items())]}
    if save_path is not None:
        if Path(save_path).stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save layout")
        data = Path(save_path).read_bytes()
        if any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        values = []
        for field in fields:
            offset = int(field["offset"], 0)
            width = 1 if field["type"] == "bool8" else 4
            raw = data[offset:offset + width]
            value = struct.unpack(">f", raw)[0] if field["type"] == "f32" else int.from_bytes(raw, "big")
            item = {"name": field["name"], "offset": hex(offset), "raw_hex": raw.hex().upper(),
                "value": value if not isinstance(value, float) or math.isfinite(value) else str(value)}
            if field["type"].startswith("bool"):
                item["enabled"] = value != 0
            values.append(item)
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "fields": values, "unknown_word_raw": data[0x114C0:0x114C4].hex().upper(),
            "unknown_tail_raw": data[0x114D6:0x114D8].hex().upper(),
            "saved_load_id": struct.unpack_from(">I", data, saved_load)[0],
            "next_level_id": struct.unpack_from(">I", data, next_level)[0]}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path, help="Plaintext working copy; originals are never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2, allow_nan=False))
