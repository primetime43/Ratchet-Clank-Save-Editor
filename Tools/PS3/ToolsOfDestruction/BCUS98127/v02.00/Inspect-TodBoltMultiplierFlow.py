"""Read-only exact-build saved bolt multiplier and paired hero-XP event flow."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
EPSILON = struct.unpack(">f", bytes.fromhex("3C23D70A"))[0]


def word(value):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("Expected raw unsigned32 word")
    return value


def f32(value):
    return struct.unpack(">f", struct.pack(">f", value))[0]


def finite(value):
    if type(value) not in (int, float) or not -1e20 <= value <= 1e20 or not math.isfinite(value):
        raise ValueError("Outside the finite bounded preview domain")
    return f32(value)


def getter_preview(replay, multiplier, cached_health, health, accumulator):
    """Finite leaf only, not native exceptions/FPSCR or a game-side getter call."""
    replay = word(replay)
    multiplier, cached_health, health, accumulator = map(finite, (multiplier, cached_health, health, accumulator))
    reset = replay != 0 and cached_health > health
    if replay != 0:
        cached_health = health
        if reset:
            multiplier = accumulator = 1.0
    return {"saved_multiplier": multiplier, "cached_health": cached_health,
            "accumulator": accumulator, "reset": reset,
            "scope": "Finite synthetic values, float32 nearest-even; no save write or native getter execution."}


def update_preview(replay, multiplier, cached_health, health, accumulator, getter_replay=None):
    """The outer gate and inner getter read the replay predicate separately."""
    replay = word(replay)
    inner = replay if getter_replay is None else word(getter_replay)
    # Validate finite inputs even when the outer gate would bypass the native body.
    values = list(map(finite, (multiplier, cached_health, health, accumulator)))
    if replay == 0:
        return {"saved_multiplier": values[0], "cached_health": values[1], "accumulator": values[3],
                "reset": False, "getter_called": False, "advanced_once": False}
    result = getter_preview(inner, *values)
    result["getter_called"] = True
    remaining = f32(result["accumulator"] - 0.5)
    result["advanced_once"] = remaining < EPSILON
    if result["advanced_once"]:
        result["saved_multiplier"] = min(20.0, max(1.0, f32(result["saved_multiplier"] + 1.0)))
        remaining = result["saved_multiplier"]
    result["accumulator"] = remaining
    return result


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}
    checks = {
        0x895518: 0x3F800000, 0x89551C: 0x3F000000,
        0x895520: 0x3C23D70A, 0x895524: 0x41A00000, 0x895500: 0,
        0x89F1B8: 0x101EFB20, 0x897B38: 0x101EFB20, 0x23E744: 0x913F1A68,
        0x13B34: 0x3C420001, 0x13B38: 0x3842FFE8,
        0x2D1860: 0x8082F268, 0x2D1868: 0x3D240009,
        0x2D186C: 0x800906EC, 0x2D1870: 0x2F800000,
        0x2D1874: 0x419E0008, 0x2D1878: 0x38600001,
        0x1E2584: 0x5463063E, 0x1E258C: 0x419E0018,
        0x1E2590: 0xC1BF1784, 0x1E2594: 0xC01F21C4,
        0x1E2598: 0xFC006800, 0x1E259C: 0x41810024,
        0x1E25A0: 0xD1BF21C4, 0x1E25B8: 0xC0250428,
        0x1E25C4: 0xC02255E0, 0x1E25C8: 0xD0290428,
        0x1E25D0: 0xD03F21C8, 0x1E25D4: 0xD1BF21C4,
        0x1E260C: 0x5460063E, 0x1E2618: 0x409E0018,
        0x1E2634: 0xC05F21C8, 0x1E2638: 0xC1A255E4,
        0x1E263C: 0xEC026828, 0x1E2640: 0xC18255E8,
        0x1E2644: 0xFC006000, 0x1E2648: 0xD01F21C8,
        0x1E264C: 0x4080FFD0, 0x1E2654: 0xC16255E0,
        0x1E2658: 0xECE1582A, 0x1E265C: 0xC14255EC,
        0x1E2660: 0xFCC75828, 0x1E2664: 0xFCA659EE,
        0x1E2668: 0xFC855028, 0x1E266C: 0xFC642AAE,
        0x1E2670: 0xD06B0428, 0x1E2678: 0xC0290428, 0x1E267C: 0xD03F21C8,
        0x1E36B0: 0x82FF1A68, 0x1E36B4: 0xC1BF1784,
        0x1E36B8: 0xD1BF21C4, 0x1E36C0: 0xC0770428, 0x1E36C4: 0xD07F21C8,
        0x1E5CAC: 0x787B0020, 0x1E5CB8: 0x3A1A0008,
        0x1E5CC4: 0x7A160020, 0x1E5D90: 0x3880006A,
        0x1E5DA8: 0x780F0020, 0x1E5DAC: 0x7F63DB78,
        0x1E5DB0: 0xC02F0090, 0x1E5DBC: 0x800F0004, 0x1E5DC4: 0x4082FFE4,
        0x1E5DCC: 0x3880006B, 0x1E5DE0: 0xC3E255C8,
        0x1E5DE8: 0x787D0020, 0x1E5DEC: 0x7F63DB78,
        0x1E5DF0: 0xC03D0090, 0x1E5DFC: 0xC19D0090,
        0x1E5E00: 0xFF0CF800, 0x1E5E08: 0x40990008,
        0x1E5E10: 0x82DD0004, 0x1E5E1C: 0x409EFFCC,
        0x23E344: 0x812B1A68, 0x23E348: 0x80090418,
        0x23E354: 0xFDA0169C, 0x23E358: 0xFC206818, 0x23E35C: 0xEC21002A,
    }
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Multiplier flow evidence changed at {address:#x}")
        guards[address] = elf.read(address, 4)
    calls = ((0x13B3C, 0x2D1860, False), (0x1E257C, 0x13B30, True),
             (0x1E2604, 0x13B30, True), (0x1E2630, 0x1E2568, True),
             (0x1E5D94, 0x12960, True), (0x1E5DD0, 0x12960, True),
             (0x1E5DB4, 0x23E338, True), (0x1E5DF4, 0x23E338, True),
             (0x1E5E0C, 0x1E25F0, True), (0x23E360, 0x23E090, False))
    for address, target, linked in calls:
        word_ = elf.u32(address)
        if BINDINGS["branch_target"](word_, address) != target or bool(word_ & 1) != linked:
            raise ValueError("Multiplier/XP call changed")
        guards[address] = elf.read(address, 4)
    if elf.descriptors[0x2D1860] != 0x89FF20 or elf.descriptors[0x1E2568] != 0x88FF38 or elf.descriptors[0x1E25F0] != 0x88FF38:
        raise ValueError("Multiplier TOC provenance changed")
    for function in (0x1E2568, 0x1E25F0, 0x2D1860, 0x23E338):
        end = elf.functions[elf.functions.index(function) + 1]
        guards[function] = elf.read(function, end - function)
    guards[0x13B30] = elf.read(0x13B30, 16)
    report = {
        "confidence": "exact-build-native-flow-and-detached-snapshot",
        "warning": "USA v02.00 static evidence only. Saved428 is a multiplier, not its runtime accumulator or health cache. Finite synthetic previews assume nearest-even; native nonfinite exceptions/FPSCR, event meaning, timing and gameplay acceptance are not emulated. Viewing never calls the mutating getter.",
        "storage": {"saved_offset": "0x428", "saved_type": "f32 BE", "cached_health_runtime_offset": "0x21c4", "accumulator_runtime_offset": "0x21c8", "current_health_runtime_offset": "0x1784"},
        "gate": "Each getter/updater separately calls13B30→2D1860, reading global saved906EC through89F1B8→101EFB20. Any raw nonzero word enables the body; this is not a bounded mode boolean or proven completed-playthrough count. The outer update gate and inner getter gate are independent reads.",
        "getter": {"va": "0x1e2568", "rule": "Gate false returns saved428 unchanged, without updating health cache or accumulator. Gate true compares cached21C4 to current health1784; strict cached>current resets saved428 and accumulator21C8 to1.0 and refreshes cached21C4. Otherwise refreshes the cache and returns saved428 without a range clamp. This is a sampled health decrease, not a direct damage-event listener; equality/healing does not reset.",
                   "nonfinite": "Unordered health comparison does not take bgt; the native path writes current health bits into cache. Previews reject nonfinite values instead of pretending they are ordinary comparisons."},
        "update": {"va": "0x1e25f0", "rule": "After outer admission, calls the getter first, subtracts0.5 with fsubs from runtime21C8, and stores it. Post-subtraction>=float32(0.01) returns without an explicit multiplier store. Otherwise increments returned multiplier by1 with fadds, applies native fsub/fsel1..20 selection for finite values, stores428 and replaces accumulator with that saved multiplier. One step per call, no loop or time delta.",
                   "threshold": {"raw_hex": "3C23D70A", "value": EPSILON},
                   "reset_interaction": "A health-drop reset inside the getter replaces accumulator with1 before this subtraction, so the same finite update leaves0.5 and does not advance. NaN/unordered accumulator comparison does not take bge; nonfinite native arithmetic is not modeled as a Python clamp."},
        "restore_seed": "Hero initialization1E36B0..1E36C4 seeds cached21C4 from runtime current health1784 and accumulator21C8 from saved multiplier428. It does not load serialized cache/countdown fields; they are not stored at save offsets21C4/21C8.",
        "event_pairing": {"consumer_va": "0x1e5c28", "rule": "Within the qualified hero-message path, numeric6A and6B linked nodes each send float payload+90 through23E338 before advancing next pointer+4. Only the6B branch additionally calls1E25F0 after rereading payload and comparing to literal0. For finite payloads it calls only when positive; unordered also falls through native ble. The6A loop has no such explicit updater call. Event source identities, enclosing gates and callbacks remain qualified, not one increment per kill or elapsed second.",
                          "xp_addition": "23E338 zero-extends saved XP418, converts via fcfid/frsp, fadds the supplied payload, and tail-branches23E090. The payload is an addition, unlike hero_set_xp replacement. XP/level/callback effects happen before the6B multiplier test, which rereads node+90."},
        "recommended_annotations": [
            {"va": "0x1e259c", "name": "TOD_multiplier_sampled_health_drop", "kind": "comment", "comment": "Replay-gated strict cached-health21C4>current1784 resets saved multiplier428 and runtime accumulator21C8 to1. Getter can mutate state; not a direct damage callback or universal clamp."},
            {"va": "0x1e264c", "name": "TOD_multiplier_accumulator_threshold", "kind": "comment", "comment": "After mutating getter, subtract0.5 from runtime21C8. bge skips a single increment when result>=float32(0.01); otherwise finite multiplier+1 selection1..20 reseeds accumulator. Not a timer or loop."},
            {"va": "0x1e5e08", "name": "TOD_message_6B_multiplier_gate", "kind": "comment", "comment": "After23E338 adds hero XP, reread6B node float+90; finite<=0 skips multiplier update1E25F0, positive/unordered falls through.6A sibling loop has no explicit updater; source/gameplay cadence unverified."},
            {"va": "0x23e35c", "name": "TOD_hero_xp_float32_addition", "kind": "comment", "comment": "fadds incoming payload to saved unsigned XP418 converted through float32, then tail-branches23E090. Additive event path, unlike script replacement setter; no runtime level/health acceptance inferred."},
        ],
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())],
    }
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext save layout")
        value = struct.unpack_from(">f", data, 0x428)[0]
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "multiplier_hex": data[0x428:0x42C].hex().upper(), "multiplier": value if math.isfinite(value) else None,
            "nonfinite": not math.isfinite(value), "replay_word": struct.unpack_from(">I", data, 0x906EC)[0],
            "hero_xp": struct.unpack_from(">I", data, 0x418)[0], "cached_health": None, "accumulator": None,
            "qualification": "Actual raw saved values only. No number of qualifying events, active cache/countdown, current health, damage history or multiplier reset is inferred or performed."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
