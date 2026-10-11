"""Read-only exact-build actor index assignments behind saved Dance progress.

Internal configuration names are reference associations, not localized labels,
saved object IDs, current actors or a replay of the five progress callbacks.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
# Index, actor method, selected config-binding method, literal actor+28 stores,
# named MonolithicConfig property registration. Index19 uses another method of
# the SAME guarded actor vtable; its index setter has no direct config load.
TARGETS = (
    (0, 0x17A890, 0x17A890, (0x17A984, 0x17AA10), 0x88EC24, "EnemyAntaraCentipede"),
    (1, 0x17D4B8, 0x17D4B8, (0x17D518,), 0x88EB04, "EnemyAntaraSwarmer"),
    (2, 0x1809D0, 0x1809D0, (0x180AC0,), 0x88EBD0, "EnemyBladeMaster"),
    (3, 0x181C40, 0x181C40, (0x181D58,), 0x88EC3C, "EnemyBombBot"),
    (4, 0x182500, 0x182500, (0x182598,), 0x88EB28, "EnemyBurrowerBeetle"),
    (5, 0x184A60, 0x184A60, (0x184AF0,), 0x88EAD4, "EnemyCaveBat"),
    (6, 0x186D60, 0x186D60, (0x186DCC,), 0x88ECE4, "EnemyConsumerBot"),
    (7, 0x1895B8, 0x1895B8, (0x189608,), 0x88EC84, "EnemyCragmiteMature"),
    (8, 0x18C618, 0x18C618, (0x18C668,), 0x88EC78, "EnemyCragmiteYoung"),
    (9, 0x18B2D8, 0x18B2D8, (0x18B33C,), 0x88EC6C, "EnemyCragmiteSwarmer"),
    (10, 0x18E420, 0x18E420, (0x18E5A4,), 0x88EC90, "EnemyDrophyd"),
    (11, 0x193DD0, 0x193DD0, (0x193E54,), 0x88EBA0, "EnemyGelChomper"),
    (12, 0x194C90, 0x194C90, (0x194DC8,), 0x88EAC8, "EnemyHunchbackPirate"),
    (13, 0x198CD8, 0x198CD8, (0x198DC8,), 0x88EBB8, "EnemyHunter"),
    (14, 0x199800, 0x199800, (0x199A8C,), 0x88EAF8, "EnemyKerchuuFlameThrower"),
    (15, 0x19B6A8, 0x19B6A8, (0x19B7CC,), 0x88EAEC, "EnemyKerchuuRoller"),
    (16, 0x1A2240, 0x1A2240, (0x1A2340,), 0x88ECD8, "EnemyPenguin"),
    (17, 0x1A72A0, 0x1A72A0, (0x1A7400, 0x1A74AC), 0x88EB1C, "EnemySargassoWasp"),
    (18, 0x1AD730, 0x1AD730, (0x1AD840,), 0x88EB34, "EnemySecurityBot"),
    (19, 0x1AED30, 0x1AE8C0, (0x1AF04C,), 0x88EABC, "EnemyShinglePirate"),
    (20, 0x1B3658, 0x1B3658, (0x1B3718,), 0x88EBAC, "EnemyShockBot"),
    (21, 0x1B5E88, 0x1B5E88, (0x1B5FB0,), 0x88EA8C, "EnemySkinnyPirateMelee"),
    (22, 0x1B9250, 0x1B9250, (0x1B92F4,), 0x88EAA4, "EnemySkinnyPirateShooter"),
    (23, 0x1BE910, 0x1BE910, (0x1BE9B4,), 0x88EBC4, "EnemyStalker"),
    (24, 0x1C3FA8, 0x1C3FA8, (0x1C4144,), 0x88EB58, "EnemyTachyonTrooperMelee"),
    (25, 0x1C7AD8, 0x1C7AD8, (0x1C7C68,), 0x88EB70, "EnemyTachyonTrooperShooter"),
    (26, 0x1CCDC8, 0x1CCDC8, (0x1CD0E4,), 0x88EB40, "EnemyTachyonTurret"),
    (27, 0x1CE928, 0x1CE928, (0x1CED48,), 0x88EB88, "EnemyTachyonWalker"),
)
MASK = (1 << 28) - 1


def observation(data):
    if not isinstance(data, (bytes, bytearray)) or len(data) != 0x906F0 or any(
            struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
        raise ValueError("Expected verified detached plaintext layout")
    bank = struct.unpack_from(">Q", data, 0x8720)[0]
    return {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "bank_hex": f"{bank:016X}", "high_bits_hex": f"{bank & ~MASK:016X}",
            "exact_completion_pattern": bank == MASK,
            "skill48_earned": bool(struct.unpack_from(">Q", data, 0x8710)[0] & (1 << 48)),
            "targets": [{"index": i, "config_name": name, "recorded_bit": bool(bank & (1 << i))}
                        for i, _, _, _, _, name in TARGETS],
            "scope": "Recorded bits only, not lifetime dance history, live actors or current award eligibility. Clear does not prove never danced; earned skill48 is independent."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}
    def keep(va, size=4):
        guards[va] = elf.read(va, size)
    checks = {0x88FAFC: 0x101B9EE8, 0xBFEC8: 0x3800FFFF, 0xBFED4: 0x90180028,
              0xC2574: 0x807D0040, 0xC2578: 0x907C0010,
              0x85ED48: 0xC2548, 0x85ED4C: 0x88FF38,
              0x845A68: 0x85ED48, 0x8466A8: 0x85ED48,
              0x848CF8: 0x864F30, 0x864F30: 0x1AED30, 0x864F34: 0x88FF38,
              0x848D38: 0x864F18, 0x864F18: 0x1AE8C0, 0x864F1C: 0x88FF38,
              0x1354B4: 0x81230010, 0x1354B8: 0x81690028,
              0x8914F0: 0x101EFB20, 0x892094: 0x101EFB20,
              0x1354D8: 0xF8838720, 0x1354F0: 0x7C273000}
    for va, expected in checks.items():
        if elf.u32(va) != expected:
            raise ValueError(f"Dance actor ownership changed at {va:#x}")
        keep(va)
    root = elf.u32(0x88FAFC)
    catalog = []
    full_functions = {0xBFE70, 0xC2548, 0x94400, 0x135468, 0x10DBA0}
    for index, function, binding_function, stores, registration, expected_name in TARGETS:
        name_va, descriptor, setter = struct.unpack(">III", elf.read(registration, 12))
        name = elf.string(name_va)
        getter, toc = struct.unpack(">II", elf.read(descriptor, 8))
        if name != expected_name or toc != 0x88FF38:
            raise ValueError("Dance target named property changed")
        offset = BINDINGS["subobject_offset"](elf, getter)
        pointer = root + offset
        keep(registration, 12); keep(descriptor, 8); keep(name_va, len(name) + 1)
        full_functions.update((function, binding_function, getter))
        end = elf.functions[elf.functions.index(binding_function) + 1]
        links = []
        for va, word in elf.instructions(binding_function, end):
            if word >> 26 == 32 and word >> 21 & 31 == 4 and word >> 16 & 31 == 2:
                slot = toc + BINDINGS["signed"](word & 65535, 16)
                if elf.u32(slot) == pointer:
                    links.append((va, slot))
        if len(links) != 1:
            raise ValueError("Missing/ambiguous Dance actor configuration load")
        load, slot = links[0]
        keep(load); keep(slot)
        publications = []
        for store in stores:
            word = elf.u32(store)
            if word >> 26 != 36 or word & 65535 != 0x28 or word >> 16 & 31 in (1, 2):
                raise ValueError("Dance index store opcode/owner changed")
            source = word >> 21 & 31
            literal = 0x38000000 | (source << 21) | index
            literals = [va for va, candidate in elf.instructions(max(function, store - 96), store)
                        if candidate == literal]
            if len(literals) != 1:
                raise ValueError("Dance actor index literal changed")
            keep(store); keep(literals[0])
            publications.append({"literal_va": hex(literals[0]), "store_va": hex(store),
                                 "owner_register": f"r{word >> 16 & 31}"})
        catalog.append({"index": index, "config_name": name,
            "display_label": re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name.removeprefix("Enemy")),
            "index_method_va": hex(function), "binding_method_va": hex(binding_function),
            "config_registration_va": hex(registration), "config_getter_va": hex(getter),
            "config_root_offset": hex(offset), "config_pointer_va": hex(pointer),
            "config_load_va": hex(load), "config_pointer_slot_va": hex(slot),
            "publications": publications,
            "association": "Same actor vtable848CF0: index method at+8, config-binding method at+48; not a direct load inside the index method or a proven execution sequence." if index == 19 else
                           "Selected actor method both passes this named config pointer to virtual+4C and explicitly stores this literal at the original actor+28. Other runtime variants/overrides are not exhaustively cataloged."})
    for function in sorted(full_functions):
        if elf.descriptors[function] != 0x88FF38:
            raise ValueError("Dance actor/getter descriptor TOC changed")
        keep(function, elf.functions[elf.functions.index(function) + 1] - function)
    report = {
        "confidence": "exact-build-native-index-and-config-association",
        "warning": "USA BCUS98127 v02.00 only; read-only static reference associations. Formatted internal names, not localized titles. No native/Lua execution, live actor reconstruction, complete variant catalog, in-game acceptance or safe edits claimed.",
        "saved_bank": {"offset": "0x8720", "type": "u64 BE", "pattern": "0x000000000FFFFFFF",
                       "earned_skill_offset": "0x8710", "earned_skill_id": 48},
        "owner_chain": "State initializerC2548 (shared by vtables845A50/846690 at+18) first calls14090 then copies registration payload+40 into state+10. Selected Dance producers follow state+10 and read actor+28, then OR saved8720. Runtime actor+28 is not a saved object UID, world slot, class-table ordinal or configuration member+28. Common actor initializerBFE70 explicitly sets its original actor+28 toFFFFFFFF; selected actor methods subsequently publish literals0..27. This is selected static ownership evidence, not simulation of all dispatch/callback paths.",
        "catalog": catalog,
        "index19_boundary": "Vtable848CF0 slot+8 descriptor864F30 targets1AED30, which sets original actor+28 to19. Its slot+48 descriptor864F18 targets1AE8C0, which passes named EnemyShinglePirate config to virtual+4C. Same class-method table links the association; no direct Shingle config load or guaranteed relative execution order inside1AED30 is claimed.",
        "variant_boundary": "28 index associations are not28 uniquely identified physical enemies. A class can have multiple instances and methods can have qualified branches/overrides; default named configs do not exclude shielded/advanced variants. Five already mapped progress producers do not prove every cataloged actor reaches the same dance path in every state. Callback admission, later actor+28 changes and current actor availability remain unresolved.",
        "save_interpretation": "All64 saved bits are retained. Show each low28 bit as Recorded/Not recorded. Clear does not prove never danced, killed or mission-complete. Extra bits28..63 still block exact completion; earned skill48 remains separate. A zero bank and an earned award can coexist. Names explain the selected code-backed index association, not target locations, histories or current eligibility.",
        "recommended_annotations": [{"va": hex(store), "kind": "comment",
            "name": f"TOD_dance_actor_index_{index}_{store:x}",
            "comment": f"Original runtime actor+28 receives Dance progress index{index}; named reference config association {name}. Selected state+10 consumers OR saved BE64 bank8720. Not an object UID/world slot, localized label, live actor or complete variant/eligibility proof."}
            for index, _, _, stores, _, name in TARGETS for store in stores] + [
            {"va": "0xbfed4", "kind": "comment", "name": "TOD_dance_actor_index_default_negative",
             "comment": "Common actor initializerBFE70 explicitly sets original actor+28 toFFFFFFFF. Dance progress suffixes treat signed-negative index as skip-store but still compare saved8720. Selected actor methods assign0..27 later; callbacks/final state not emulated."},
            {"va": "0xc2578", "kind": "comment", "name": "TOD_dance_state_actor_owner_publication",
             "comment": "Shared state initializer copies input registration payload+40 into state+10 after14090. Dance producers follow this pointer to actor+28, not config+28 or a saved world/object index."}],
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())],
    }
    if save_path is not None:
        report["save_observation"] = observation(Path(save_path).read_bytes())
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
