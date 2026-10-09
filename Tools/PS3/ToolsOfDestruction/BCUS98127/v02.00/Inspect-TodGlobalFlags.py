"""Read-only exact-build global event flags; native enum IDs, not guessed story completion."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

PROGRESSION = runpy.run_path(str(Path(__file__).with_name("Inspect-TodProgression.py")))
BINDINGS = PROGRESSION["BINDINGS"]


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    def function(address):
        end = elf.functions[elf.functions.index(address) + 1]
        keep(address, end - address)
        return list(elf.instructions(address, end))

    def expect(address, word):
        if elf.u32(address) != word:
            raise ValueError(f"Flag instruction/pointer changed at {address:#x}")
        keep(address, 4)

    for address, word in {
        0x27948: 0x5468E8F8, 0x2794C: 0x816286EC,
        0x27950: 0x546306BE, 0x27954: 0x38E85520,
        0x27964: 0xE8A90008, 0x27968: 0x7CA41C36,
        0x2796C: 0x548007FE, 0x888624: 0x101EFB20,
        0x2770F4: 0x81629030, 0x898F50: 0x101EFB20,
        0x24AA4: 0x7C8B0378, 0x24AA8: 0xF9690008,
        0x279AC: 0x7C0B2078, 0x279B0: 0xF9690008,
        0x35E198: 0x381E5528, 0x35E1AC: 0x4BFFF7F5,
        0x35D9A8: 0x38000000, 0x35D9D0: 0xF8030020,
        0x35D9D4: 0xF8030000, 0x35D9D8: 0xF8030008,
        0x35D9DC: 0xF8030010, 0x35D9E0: 0xF8030018,
        0x466C58: 0x83425FF4, 0x89550C: 0x101EFB20,
        0x466C5C: 0xE93A5528, 0x466C60: 0x5528056A,
        0x466CE4: 0xEBFA5528, 0x466CE8: 0x63FE0400,
        0x466CEC: 0xFBDA5528,
    }.items():
        expect(address, word)
    base = (elf.u32(0x27954) & 65535) + (elf.u32(0x27964) & 0xFFFC)
    bit_mask = (1 << (32 - (elf.u32(0x27950) >> 6 & 31))) - 1
    if base != 0x5528 or bit_mask != 63:
        raise ValueError("Unexpected global bit addressing")
    # Two separate named Lua registration/TOC families agree on every flag ID.
    registrations = ((0x28440, 0x12990, 0x28DC8, 0x2A4A0),
                     (0x294E90, 0x252EB8, 0x2965D0, 0x297CA8))
    catalogs = []
    for start, target, low, high in registrations:
        items = [e for e in PROGRESSION["exports"](elf, start, "", target)
                 if low <= int(e["name_load_va"], 0) <= high]
        if [e["id"] for e in items] != list(range(293)) or items[-1]["enum"] != "GLOBAL_FLAG_COUNT":
            raise ValueError("Incomplete global flag catalog")
        keep(low, high + 8 - low)
        for e in items:
            keep(int(e["name_va"], 0), len(e["enum"]) + 1)
            for key in ("name_slot_va", "value_slot_va"):
                keep(int(e[key], 0), 4)
        catalogs.append(items)
    if [(e["id"], e["enum"], e["name_va"]) for e in catalogs[0]] != [
            (e["id"], e["enum"], e["name_va"]) for e in catalogs[1]]:
        raise ValueError("Independent flag registrations disagree")
    named = []
    for slot, native in ((0x8892AC, 0x27948), (0x8892B4, 0x24A80), (0x8892BC, 0x27988),
                         (0x89D854, 0x2770F0), (0x89D85C, 0x27BB10), (0x89D864, 0x27BAE0)):
        pointer, descriptor = struct.unpack(">II", elf.read(slot, 8))
        name, wrapper = elf.string(pointer), elf.u32(descriptor)
        instructions = function(wrapper)
        if name not in ("check_flag", "set_flag", "clear_flag") or not any(
                word >> 26 == 18 and word & 1 and BINDINGS.branch_target(word, address) == native
                for address, word in instructions):
            raise ValueError("Named flag binding changed")
        keep(slot, 8)
        keep(descriptor, 8)
        keep(pointer, len(name) + 1)
        function(native)
        named.append({"name": name, "registration_slot_va": hex(slot), "name_va": hex(pointer),
                      "wrapper_va": hex(wrapper), "native_va": hex(native)})
    for native in (0x35D9A0, 0x35E110, 0x466B70):
        function(native)
    acquisition_mask = elf.u32(0x466CE8) & 65535
    acquisition_id = acquisition_mask.bit_length() - 1
    if acquisition_mask != 1 << acquisition_id or catalogs[0][acquisition_id]["enum"] != "HERO_HAS_TWO_ITEMS":
        raise ValueError("Acquisition flag does not match the independent enum catalog")
    catalog = []
    for primary, secondary in zip(catalogs[0][:-1], catalogs[1][:-1]):
        identifier = primary["id"]
        word_offset = base + identifier // 64 * 8
        category = "Level events" if primary["enum"].startswith("LVL_") else \
                   "Hero events" if primary["enum"].startswith("HERO_") else \
                   "Movie flags" if primary["enum"].startswith("MOVIE_") else "Other global flags"
        catalog.append({"id": identifier, "enum": primary["enum"], "name_va": primary["name_va"],
            "category": category, "word_offset": hex(word_offset), "word_bit": identifier % 64,
            "byte_offset": hex(word_offset + 7 - identifier % 64 // 8),
            "byte_mask": hex(1 << (identifier % 8)), "exports": [primary, secondary]})
    # Coalesce adjacent/overlapping evidence so the same bytes are not duplicated.
    intervals = []
    for address, raw in sorted(guards.items()):
        end = address + len(raw)
        if intervals and address <= intervals[-1][1]:
            intervals[-1][1] = max(intervals[-1][1], end)
        else:
            intervals.append([address, end])
    report = {"confidence": "code-backed",
        "warning": "Exact USA v02.00 enum/bit storage, not proof of localized names, current story state, flag polarity or gameplay-safe edits.",
        "storage": {"base": hex(base), "word_count": 5, "word_size": 8, "end_exclusive": "0x5550",
            "named_count": len(catalog), "physical_bits": 320, "unmapped_bits": {"first_id": 292, "last_id": 319},
            "encoding": "Five BE64 words. ID selects word floor(id/64), integer bit id%64; file byte=base+8*floor(id/64)+7-floor((id%64)/8). Set is OR; clear is AND-NOT; check returns boolean.",
            "initializer_va": "0x35d9a0", "owner_initializer_va": "0x35e110",
            "bounds_warning": "Native flag leaves do not enforce GLOBAL_FLAG_COUNT. Inspector bounds reads to the five initialized words. COUNT292 is a sentinel, not a named flag; physical tail bits292..319 are preserved as unknown. No valid arbitrary input or edit range inferred."},
        "catalog": catalog, "count_exports": [c[-1] for c in catalogs], "named_bindings": named,
        "acquisition_dependency": {"id": acquisition_id, "enum": catalogs[0][acquisition_id]["enum"], "native_va": "0x466b70", "mask": hex(acquisition_mask),
            "semantics": "New acquisition tests this global bit and item definition flag2. If bit is clear and the acquired item has flag2, it scans32 owned records and counts those with definition flag2; count>1 sets the bit. This is a recorded event, not a continuously maintained inventory-count predicate; removal does not establish its reset policy."},
        "instruction_guards": [{"va": hex(start), "bytes": elf.read(start, end - start).hex().upper()} for start, end in intervals]}
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        words = struct.unpack_from(">5Q", data, base)
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "raw_words": [f"{word:016X}" for word in words],
            "set_named_ids": [i for i in range(292) if words[i // 64] & 1 << (i % 64)],
            "set_unmapped_ids": [i for i in range(292, 320) if words[i // 64] & 1 << (i % 64)]}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path, help="Plaintext working copy; never modified")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2))
