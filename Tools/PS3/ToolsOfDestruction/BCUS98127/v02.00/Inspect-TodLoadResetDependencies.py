"""Read-only exact-build Gelanator ammo reset and deferred saved timing-gate refresh."""
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


def finite_zero_ammo_preview(maximum_bits):
    """Fixed +0 request through the guarded fsel pair, finite supplied maximum only."""
    maximum_bits = word(maximum_bits)
    maximum = struct.unpack(">f", maximum_bits.to_bytes(4, "big"))[0]
    if not math.isfinite(maximum):
        raise ValueError("Preview requires a finite explicit binary32 maximum")
    # First fsel selects request +0; second selects maximum when +0-maximum>=0.
    return {"result_bits": maximum_bits if maximum <= 0 else 0,
            "qualification": "Synthetic finite maximum only, not current definitions, helper effects, a verbatim zero write or edit safety. Negative maximum can produce negative ammo; -0 maximum can preserve signed zero."}


def gate_refresh_plan(replay_word, runtime_latch):
    """Selected 2CE0D0 branch plan only; never resolves config or executes callbacks."""
    replay_word, runtime_latch = word(replay_word), word(runtime_latch)
    refresh = replay_word == 0 and runtime_latch != 0
    return {"branch": "replay bypass" if replay_word else "refresh" if refresh else "no refresh",
            "saved_gate_offsets": ["0x874C", "0x8750"] if refresh else [],
            "explicit_latch_after": 0 if refresh else runtime_latch,
            "qualification": "Explicit gate-reset calls/latch store only. Runtime latch and live configuration are absent from GAME.SAV; no copied float bits, complete helper effects, final runtime state or timing inferred."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    expected = {
        0x8A689C: 0x101EFD3C, 0x8A68A0: 0,
        0x489FE8: 0x8062697C, 0x489FEC: 0xC0226980,
        0x465DE8: 0xC1A25FD4, 0x8A5EF4: 0,
        0x465DEC: 0xFC7F6828, 0x465DF0: 0xFC036FEE,
        0x465DF4: 0xFC400828, 0x465DF8: 0xFD82006E, 0x465DFC: 0xD19D0008,
        0x89F078: 0x101E8D70, 0x89F07C: 0x101F8264,
        0x89F080: 0x101B9EE8, 0x89F188: 0x101EFB20,
        0x2CDBB0: 0x8122F158, 0x2CDBB4: 0x38000001, 0x2CDBB8: 0x90090054,
        0x2CE0FC: 0x409E0150, 0x2CE104: 0x80BC0054, 0x2CE10C: 0x40820178,
        0x2CE28C: 0x93FC0054,
        0x2CDC18: 0xC0090FD0, 0x2CDC1C: 0xD003000C,
        0x2CDC48: 0xC0090FCC, 0x2CDC4C: 0xD0030008,
        0x2D186C: 0x800906EC, 0x2D1874: 0x419E0008,
        0x88B3C0: 0x100002D0, 0x88B3C4: 0x41D80000,
    }
    guards = {}
    for address, raw in expected.items():
        if elf.u32(address) != raw:
            raise ValueError(f"Load reset dependency evidence changed at {address:#x}")
        guards[address] = elf.read(address, 4)
    for address, target in ((0x489FE0, 0x2CDBB0), (0x489FFC, 0x465DC0),
                            (0x465DE0, 0x463DE0), (0x2CE0EC, 0x2D1860),
                            (0x2CE284, 0x2CDC30), (0x2CE288, 0x2CDC00),
                            (0x2CDC3C, 0x2CDBF8), (0x2CDC0C, 0x2CDBF8),
                            (0x80D1C, 0x12990)):
        raw = elf.u32(address)
        if not raw & 1 or BINDINGS["branch_target"](raw, address) != target:
            raise ValueError("Load reset dependency call changed")
        guards[address] = elf.read(address, 4)
    for function in (0x489F68, 0x465DC0, 0x463DE0, 0x2CDBB0,
                     0x2CE0D0, 0x2CDC30, 0x2CDC00, 0x2CDBF8, 0x2D1860):
        if elf.descriptors[function] != 0x89FF20:
            raise ValueError("Load reset dependency TOC changed")
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    guards[0x80D14] = elf.read(0x80D14, 12)
    guards[0x100002D0] = elf.read(0x100002D0, len("WPN_GELANATOR") + 1)
    exports = [row for row in BINDINGS["enum_exports"](elf) if row["id"] == 27]
    if len(exports) != 1 or exports[0]["enum"] != "WPN_GELANATOR":
        raise ValueError("Native item27 name changed")
    record_offset = elf.u32(0x8A689C) - 0x101EFB20
    if record_offset != 27 * 20:
        raise ValueError("Reset ammo record ownership changed")
    report = {
        "confidence": "exact-build-native-flow",
        "warning": "USA BCUS98127 v02.00 static evidence only. Native code is never executed. Runtime latch/configuration, accepted loads, final helper effects and full reset coverage remain unknown; no new editing permission.",
        "ammo_reset": {
            "item_id": 27, "enum": "WPN_GELANATOR", "record_offset": "0x21C", "ammo_offset": "0x224",
            "record_pointer_slot": "0x8A689C", "record_pointer": "0x101EFD3C", "request_bits": "00000000",
            "rule": "After saved8730/8728/872C clears,489F68 loads record pointer8A689C=101EFD3C and f32 +0 from8A68A0, then calls absolute ammo setter465DC0 at489FFC. Relative to save101EFB20 this is record21C=27*14, and setter+8 writes saved224. Native export80D1C independently names ID27 WPN_GELANATOR. The setter does not read old ammo or locally test ownership before its store; this is one specific load/resource reset path, not all ammo writers or a per-shot cost.",
            "clamp_limit": "465DC0 first calls463DE0, which resolves the record ID and passes stored level+11/modifier mask+0C to the maximum resolver. It then applies two fsub/fsel comparisons before stfs+8. With supplied finite strictly positive maximum, +0 request writes +0; maximum+0/-0 can supply its own zero sign, and a finite negative maximum can produce negative ammo. Nonfinite maximum, helper mutation, exact runtime definitions and NaN payloads are not modeled. This is not an unconditional raw00000000 assignment, inventory/XP/ownership reset or safe maximum claim."},
        "deferred_gate_refresh": {
            "latch_va": "0x101E8DC4", "arm": "0x2CDBB0", "consumer": "0x2CE0D0",
            "gate_offsets": ["0x874C", "0x8750"],
            "arm_rule": "Call-free2CDBB0 writes BE32 value1 to runtime101E8D70+54=101E8DC4. It does not directly reset either saved countdown, clear aggregates or write a saved latch. This replaces the earlier unknown-helper boundary at489FE0 specifically.",
            "consume_rule": "2CE0D0 first calls saved replay/restart predicate2D1860 (906EC nonzero). Nonzero selects2CE24C before the latch test, skipping both gate-reset calls and explicit latch consumption on this path. Zero reaches a u32 runtime+54 test: zero skips refresh; ANY nonzero reaches2CE284->2CDC30 (saved874C from config101B9EE8+10FCC), then2CE288->2CDC00 (saved8750 from config+10FD0), then2CE28C clears runtime latch+54 using preserved zero r31. Gate values are loaded/stored as floats, not a promised raw-bit copy. Neither store clears saved8744/8748; larger setup/helper effects are not modeled.",
            "order_limit": "This is a deferred setup refresh, not an immediate effect of arming2CDBB0. Calls may be separated and depend on runtime state. Native setup has subsequent segment/config work, and replay bypass tail-calls2CDDD8; skipping the selected calls is not a universal final-state preservation proof. The latch is outside GAME.SAV and cannot be inferred as armed/clear from the saved gates.",
            "snapshot_limit": "The supplied replay word3 takes the bypass branch if passed unchanged to this setup predicate. Gate observations10/300 do not prove defaults, seconds, latch status or invocation history. A later setup with replay0 and a nonzero runtime latch can take the refresh branch; no actual transition is executed here."},
        "recommended_annotations": [
            {"va": "0x489fe8", "kind": "comment", "name": "TOD_load_reset_Gelanator_ammo_zero_request", "comment": "Loads8A689C=101EFD3C, canonical saved record21C for native ID27 WPN_GELANATOR. Next f32 argument is+0 from8A68A0;489FFC calls465DC0, whose+8 store targets saved224. Definition/level/mask maximum clamp still applies; not raw-zero guarantee or ownership/XP reset."},
            {"va": "0x2cdbb8", "kind": "comment", "name": "TOD_arm_deferred_saved_timing_gate_refresh", "comment": "Call-free leaf stores1 to runtime101E8D70+54=101E8DC4, outside GAME.SAV. No immediate874C/8750 reset. Setup2CE0D0 consumes ANY nonzero latch only when saved replay906EC is zero, invoking two configured gate resets before latch clear."},
            {"va": "0x2ce284", "kind": "comment", "name": "TOD_consume_latch_reset_two_saved_timing_gates", "comment": "Reached only after2D1860 returns0 (saved906EC zero) and runtime latch+54 nonzero. Calls2CDC30 to reset874C fromconfig+10FCC, then2CDC00 to reset8750 from+10FD0;2CE28C clears latch. Deferred setup, not immediate arm effect, fixed seconds or complete callback-state proof."},
            {"va": "0x2ce28c", "kind": "comment", "name": "TOD_timing_refresh_latch_consumption_after_gate_stores", "comment": "Store preserved zero r31 to runtime101E8D70+54 AFTER both gate-reset calls. Replay-nonzero branch skips this consumption and those calls. Latch absent from GAME.SAV; gate values cannot establish latch state or past setup execution."},
        ],
        "instruction_guards": [{"va": hex(a), "bytes": raw.hex().upper()} for a, raw in sorted(guards.items())]}
    if save_path is not None:
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not verified plaintext save layout")
        report["save_observation"] = {
            "sha256": hashlib.sha256(raw).hexdigest().upper(),
            "ammo_bits": raw[0x224:0x228].hex().upper(), "ownership": raw[0x22C],
            "level": raw[0x22D], "xp_bits": raw[0x220:0x224].hex().upper(),
            "gate_bits": [raw[o:o + 4].hex().upper() for o in (0x874C, 0x8750)],
            "replay_word": struct.unpack_from(">I", raw, 0x906EC)[0],
            "qualification": "Raw snapshot only; no current maximum, reset invocation, runtime latch, active item, true time unit or final callback result inferred."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
