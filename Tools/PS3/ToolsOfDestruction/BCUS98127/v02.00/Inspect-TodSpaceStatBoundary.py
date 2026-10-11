"""Read-only named space-stat/reset APIs versus persistent target/counter banks."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
TARGETS = (0x361A1C, 0x361A80, 0x361A78, 0x361A4C, 0x361A04, 0x361A44, 0x361A3C, 0x361A24)


def u32(value):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("Expected unsigned raw32 observation")
    return value


def stat_preview(identifier, observations):
    """Supplied runtime snapshots only, not a reconstruction from GAME.SAV."""
    identifier = u32(identifier)
    if type(observations) is not dict or set(observations) != {0xFC, 0x120, 0x124, 0x128, 0x130, 0x134, 0x138, 0x13C}:
        raise ValueError("Expected exactly the eight runtime source words")
    raw = {offset: u32(value) for offset, value in observations.items()}
    rounded = lambda value: struct.unpack(">f", struct.pack(">f", value))[0]
    if identifier > 7:
        value = 0
    elif identifier in (0, 1, 2, 5, 6):
        value = raw[{0: 0x120, 1: 0x124, 2: 0x128, 5: 0x138, 6: 0x13C}[identifier]]
    elif identifier == 3:
        value = raw[0xFC].bit_count()
    elif identifier == 7:
        value = int(raw[0xFC] == 0)
    elif raw[0x130] == 0:
        value = 0
    else:
        ratio = rounded(rounded(raw[0x134]) / rounded(raw[0x130]))
        value = math.trunc(rounded(ratio * 100.0)) & 0xFFFFFFFF
    return {"native_raw32": value, "lua_signed_result": BINDINGS["signed"](value, 32),
            "scope": "Separate supplied runtime words, not saved data. Numeric ratio assumes nearest-even float32, not live FPSCR. No menu names, units, callback effects or current gameplay statistics inferred."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}
    checks = {
        0x8897BC: 0x10003B68, 0x8897C0: 0x85A470,
        0x85A470: 0x2B880, 0x85A474: 0x88FF38,
        0x89E14C: 0x1001FDA8, 0x89E150: 0x86BBF8,
        0x86BBF8: 0x2B5150, 0x86BBFC: 0x89FF20,
        0x888658: 0x10330740, 0x898F5C: 0x10330740, 0x8A1C24: 0x10330740,
        0x8A1C70: 0x101EFB20, 0x8A1A54: 0x3619E4, 0x8A1A58: 0x42C80000,
        0x24DDC: 0x78640020, 0x24DE0: 0x80628720,
        0x139A0: 0xF8410028, 0x139A4: 0x3C420001, 0x139A8: 0x3842FFE8,
        0x2B928: 0xFC20081E, 0x2B92C: 0x7C2047AE, 0x2B934: 0x7C6307B4,
        0x24DEC: 0xE8010080, 0x24DF0: 0x7C6307B4,
        0x3619C0: 0x2B840007, 0x3619C4: 0x419D004C,
        0x3619CC: 0x81621B34, 0x3619D4: 0x7CA407B4, 0x3619E0: 0x4E800420,
        0x361A1C: 0x81230120, 0x361A80: 0x81230124, 0x361A78: 0x81230128,
        0x361A44: 0x81230138, 0x361A3C: 0x8123013C,
        0x361A4C: 0x806300FC, 0x361A60: 0x546607FE, 0x361A64: 0x5463F87E,
        0x361A6C: 0x2C830000, 0x361A70: 0x4086FFF0,
        0x361A24: 0x810300FC, 0x361A30: 0x419E009C, 0x361ACC: 0x38600001,
        0x361A04: 0x81230130, 0x361A08: 0x2F090000, 0x361A0C: 0x409A007C,
        0x361A88: 0x80E30134, 0x361AAC: 0xFC603018, 0x361AB0: 0xFDA02018,
        0x361AB4: 0xEC436824, 0x361AB8: 0xEC220332, 0x361ABC: 0xFC000E5E,
        0x277C04: 0x7C641B78, 0x277C08: 0x8062903C,
        0x361F60: 0x2F840000, 0x361F84: 0x409E007C, 0x361F8C: 0x3BA00000,
        0x361FB0: 0x93BF0120, 0x361FB4: 0x93BF0124, 0x361FB8: 0x93BF0128,
        0x361FBC: 0x93BF012C, 0x361FC0: 0x93BF0130, 0x361FC4: 0x93BF0134,
        0x361FC8: 0x93BF0138, 0x361FCC: 0x93BF013C, 0x361FD0: 0x93BF0140,
        0x361FD4: 0x93BF0144, 0x361FD8: 0x93BF0148,
        0x36FCD8: 0x80621D04, 0x36FCDC: 0x38800000,
        0x36C678: 0x93A7872C, 0x36C6D4: 0x91078730,
    }
    for va, value in checks.items():
        if elf.u32(va) != value:
            raise ValueError(f"Space-stat boundary evidence changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    for address, expected in ((0x10003B68, "get_space_stat"), (0x1001FDA8, "space_combat_reset")):
        if elf.string(address) != expected:
            raise ValueError("Space-stat named API changed")
        guards[address] = elf.read(address, len(expected) + 1)
    table = 0x3619E4
    targets = tuple((table + BINDINGS["signed"](elf.u32(table + i * 4), 32)) & 0xFFFFFFFF for i in range(8))
    if targets != TARGETS:
        raise ValueError("Space-stat relative dispatch changed")
    guards[table] = elf.read(table, 32)
    for address, target, linked in ((0x2B938, 0x24DD0, True), (0x24DE4, 0x139A0, True),
                                    (0x139AC, 0x3619C0, False), (0x2B51FC, 0x277BF8, True),
                                    (0x277C0C, 0x361F60, True), (0x361FA8, 0x361948, True),
                                    (0x36FCE0, 0x361F60, True), (0x36FCEC, 0x36C578, True)):
        word = elf.u32(address)
        if BINDINGS["branch_target"](word, address) != target or bool(word & 1) != linked:
            raise ValueError("Space-stat boundary call changed")
        guards[address] = elf.read(address, 4)
    for function in (0x2B880, 0x24DD0, 0x2B5150, 0x277BF8, 0x3619C0, 0x361F60, 0x361948, 0x36C578, 0x36F6A0):
        expected = 0x88FF38 if function in (0x2B880, 0x24DD0) else 0x89FF20
        if elf.descriptors[function] != expected:
            raise ValueError("Space-stat function TOC changed")
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    guards[0x139A0] = elf.read(0x139A0, 16)
    report = {
        "confidence": "exact-build-native-flow",
        "warning": "Read-only USA BCUS98127 v02.00 static evidence. No native execution, runtime BSS reads, saved-stat synthesis or gameplay-tested edits. Exact counter event names, numeric stat menu labels and units remain unresolved.",
        "named_getter": {"name": "get_space_stat", "registration_va": "0x8897bc", "wrapper_va": "0x2b880",
                         "native_chain": ["0x24dd0", "0x139a0", "0x3619c0"],
                         "runtime_root": "0x10330740", "scope": "Root10330740 is outside serialized state101EFB20..10280210. Named wrapper validates/converts its numeric argument with fctiwz; native24DD0 passes low32 selector and root through139A0, which changes TOC88FF38 to89FF20. Native getter accepts unsigned selectors0..7; all others return0. Wrapper sign-extends the returned low32 value for Lua numeric output, not an unsigned total. Caller-rejected/nonfinite conversions are not modeled."},
        "numeric_stat_catalog": [
            {"id": i, "target_va": hex(TARGETS[i]), "rule": rule}
            for i, rule in enumerate(("Read runtime u32+120", "Read runtime u32+124", "Read runtime u32+128",
                                     "Popcount all32 runtime pending bits at+FC, not saved8728",
                                     "If runtime u32+130 is0 return0; otherwise convert u32+134/+130 to float32, divide and multiply100, then fctidz; public wrapper exposes signed low32. No100 cap or named accuracy/unit assertion.",
                                     "Read runtime u32+138", "Read runtime u32+13C",
                                     "Return1 if runtime pending+FC is0, otherwise0; not a saved all-targets verdict"))],
        "named_reset": {"name": "space_combat_reset", "registration_va": "0x89e14c", "wrapper_va": "0x2b5150",
                        "native_chain": ["0x277bf8", "0x361f60"], "root_pointer_slot": "0x898f5c",
                        "explicit_zero_word_offsets": [hex(a) for a in range(0x120, 0x14C, 4)],
                        "rule": "Named Boolean wrapper reaches277BF8 with runtime root10330740. Native361F60 low32 flag nonzero first enumerates runtime objects and invokes their virtual+18 callbacks; zero skips that loop. Both paths call252978, clear runtime+154/F5, call361948, then explicitly zeroF6, eleven words120..148 andF7. Complete361948 rewires23 runtime scratch records and clears24754/24764. Neither complete body explicitly stores root+FC or saved8728/872C/8730. Helpers/virtual callbacks can affect state; absence of direct stores is not proof of final preservation or a safe reset implementation."},
        "saved_boundary": {"offsets": ["0x8728", "0x872c", "0x8730"],
                           "rule": "Existing saved8728 is retained collected-target progress, whereas named stat3/7 read runtime pending+FC. They cannot be reconstructed by popcount/complement of saved8728: target count/index validity, registration and callback state are unknown. Existing producer36C578 increments872C and conditionally8730. In selected caller36F6A0,36FCE0 first calls the shared361F60(root,0), then36FCEC invokes36C578. Thus explicit live-stat reset stores precede the persistent counter updates on this branch; reset does not mean a new save or that persistent counters are directly cleared. Root8A1C24=10330740 and canonical pointer8A1C70=101EFB20 establish the separate domains. No deaths/kills/retries label or current stat value is inferred."},
        "recommended_annotations": [
            {"va": "0x2b938", "kind": "comment", "name": "TOD_get_space_stat_runtime_not_saved", "comment": "Named get_space_stat wrapper reaches24DD0->139A0->3619C0 with runtime10330740, outside GAME.SAV. Signed low32 Lua result; no saved-stat reconstruction."},
            {"va": "0x3619e4", "kind": "data", "size": 32, "name": "TOD_space_stat_relative_dispatch_table", "comment": "Eight signed-relative native3619C0 targets. IDs3/7 query runtime pending+FC, not saved8728. ID4 computes numeric134/130*100 with float32 and fctidz; no cap100/name/unit proof."},
            {"va": "0x361fb0", "kind": "comment", "name": "TOD_space_stat_reset_explicit_word_bank", "comment": "Named space_combat_reset reaches361F60. Explicit stores zero runtime words120..148 after helpers. No direct saved8728/872C/8730 or pending+FC store in selected complete bodies; callback effects/final preservation unmodeled."},
            {"va": "0x36fce0", "kind": "comment", "name": "TOD_runtime_stat_reset_before_saved_counter_event", "comment": "Selected36F6A0 branch calls shared361F60(runtime10330740,0) before36C578 updates saved872C and handle-qualified8730. Named API confirms space-combat context, not event identity, death count or saved-stat reset."},
        ],
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())],
    }
    if save_path is not None:
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not verified plaintext save layout")
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(raw).hexdigest().upper(),
            "saved_words": {hex(a): f"{struct.unpack_from('>I', raw, a)[0]:08X}" for a in (0x8728, 0x872C, 0x8730)},
            "runtime_statistics": None, "runtime_pending": None,
            "scope": "No runtime owner/stat words are serialized here; unavailable data stays unknown, not synthesized as0 from an all-zero saved snapshot."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
