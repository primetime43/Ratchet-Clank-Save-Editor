"""Exact-build read-only armor purchase/effect ordering and skin leaf admission.

No native callbacks, actor lookup, currency helper or game asset code is executed.
Decision previews are detached and do not grant save editing permissions.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("tod_armor_bindings", Path(__file__).with_name("Inspect-TodWeaponBindings.py"))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)


def _word(value, name):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(name + " must be an unsigned 32-bit integer")
    return value


def _signed(value):
    return value - 0x100000000 if value & 0x80000000 else value


def armor_admission_preview(requested, equipped, bolts_word, price, hero_exists=True):
    """Native leaf admission only; no unlock, ownership or actor callbacks.

    Armor IDs are deliberately limited to the five named normal entries. Native
    code lacks this bound. Price is a supplied nonnegative signed-32 definition
    value, not a guessed price derived from this save.
    """
    for name, value in (("requested", requested), ("equipped", equipped)):
        if type(value) is not int or not 0 <= value < 5:
            raise ValueError(name + " must be a normal armor ID 0..4")
    _word(bolts_word, "bolts_word")
    if type(price) is not int or not 0 <= price <= 0x7FFFFFFF:
        raise ValueError("price must be a nonnegative signed-32 definition value")
    if type(hero_exists) is not bool:
        raise ValueError("hero_exists must be a boolean")
    return hero_exists and _signed(bolts_word) >= price and equipped < requested


def effect_route_preview(handle_valid, hero_byte_1c, predicate_word):
    """Only the 43FCE8 decision; outer actor type and lookup already resolved."""
    if type(handle_valid) is not bool:
        raise ValueError("handle_valid must be a boolean")
    if type(hero_byte_1c) is not int or not 0 <= hero_byte_1c <= 255:
        raise ValueError("hero_byte_1c must be a byte")
    _word(predicate_word, "predicate_word")
    return "queued" if handle_valid and hero_byte_1c != 0 and predicate_word & 255 == 0 else "direct"


def delayed_equip_preview(state, current_bits, deadline_bits):
    """Exact state-2 branch decision, including unordered fcmpu behavior.

    This does not advance the surrounding state machine, resolve an actor,
    execute equip, notify systems or infer actual runtime timing from a save.
    """
    for name, value in (("state", state), ("current_bits", current_bits), ("deadline_bits", deadline_bits)):
        _word(value, name)
    current = struct.unpack(">f", struct.pack(">I", current_bits))[0]
    deadline = struct.unpack(">f", struct.pack(">I", deadline_bits))[0]
    unordered = math.isnan(current) or math.isnan(deadline)
    return {"unordered": unordered, "reaches_equip_block": state == 2 and not current <= deadline}


def skin_admission_preview(price_word, balance_word):
    """Signed leaf comparison only; ownership and availability are not inputs."""
    return _signed(_word(price_word, "price_word")) <= _signed(_word(balance_word, "balance_word"))


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    checks = {
        0x895504: 0x101B9EE8, 0x89F1BC: 0x101B9EE8,
        0x8A54F8: 0x41600000, 0x895A00: 0x10731D00,
        0x2D2728: 0x8069041C, 0x2D272C: 0x7C03E800, 0x2D2730: 0x40800038,
        0x2D2778: 0x7C83F000, 0x2D277C: 0x4084FFB8,
        0x2D27A4: 0x900B0004, 0x2D27B4: 0x5749043E,
        0x2D27BC: 0x7C9F4840, 0x2D27C0: 0x41840088,
        0x2D2810: 0x38800396, 0x2D281C: 0x547A063E, 0x2D2824: 0x41820024,
        0x43FDB8: 0x891F001C, 0x43FDBC: 0x2C880000, 0x43FDC0: 0x4186FFB0,
        0x43FDD4: 0x547F063E, 0x43FDDC: 0x2F1F0000, 0x43FDE0: 0x409AFF90,
        0x43FDEC: 0xD01D01AC, 0x43FDF0: 0x9864000C,
        0x43FDF8: 0x93C40004, 0x43FE00: 0x93640000, 0x43FE04: 0x93840008,
        0x1F7E30: 0x39232170, 0x1F7E90: 0x2F000002,
        0x1F7F3C: 0xC13A001C, 0x1F7F40: 0xC1BC00B4,
        0x1F7F44: 0xFF0D4800, 0x1F7F48: 0x4099FF58,
        0x1F7F4C: 0x80990000, 0x1F7FC0: 0x917A0018,
        0x1E2170: 0x908A0458, 0x1E2190: 0x900A0004,
        0x1E2194: 0xC00B0008, 0x1E2198: 0xD0031798,
        0x2D1CA8: 0x8063000C,
        0x27AD4: 0x7F9F1800, 0x27AE8: 0x419D0038,
        0x27B00: 0x93CB0480, 0x27B04: 0x7D23FA14,
        0x27B08: 0x90AA000C, 0x27B10: 0x912B0424,
    }
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Armor/skin consumer evidence changed at {address:#x}")
    calls = [(0x2D2700, 0x24FB88), (0x2D271C, 0x2D1C88),
             (0x2D2770, 0x2510D8), (0x2D27A8, 0x24FCB8),
             (0x2D2814, 0x24F208), (0x2D2834, 0x43FCE8),
             (0x2D2850, 0x252098), (0x2D2864, 0x250FA8),
             (0x43FD78, 0x252098), (0x43FD8C, 0x250FA8),
             (0x43FDC8, 0x24F038), (0x1F7F58, 0x1E2150),
             (0x1F7F6C, 0x11EE0), (0x27AC0, 0x1F0D60),
             (0x27ACC, 0x25DB8), (0x27B14, 0x11EE0)]
    for address, target in calls:
        if BINDINGS.branch_target(elf.u32(address), address) != target:
            raise ValueError(f"Armor/skin consumer call changed at {address:#x}")
    guards = {address: elf.read(address, 4) for address in checks}
    guards.update({address: elf.read(address, 4) for address, _ in calls})
    functions = (0x2D26D0, 0x43FCE8, 0x1F7DC0, 0x1E2150, 0x2D1C88, 0x27AA0)
    for address in functions:
        end = elf.functions[elf.functions.index(address) + 1]
        guards[address] = elf.read(address, end - address)
    # Full skin leaf call inventory proves absence of native ownership/availability
    # calls, rather than treating a missing nearby instruction as proof.
    skin_calls = [{"call_va": hex(a), "target_va": hex(BINDINGS.branch_target(w, a))}
                  for a, w in elf.instructions(0x27AA0, 0x27B40)
                  if w >> 26 == 18 and w & 1]
    if [int(c["target_va"], 0) for c in skin_calls] != [0x1F0D60, 0x25DB8, 0x11EE0]:
        raise ValueError("Skin purchase leaf call inventory changed")
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA BCUS98127 v02.00 static code plus optional plaintext observations. No actor/native/Lua execution, in-game acceptance, safe edit bounds or current runtime effect inferred.",
        "armor_purchase": {
            "function_va": "0x2d26d0", "price_getter_va": "0x2d1c88",
            "admission": "Requires a resolved hero, signed saved bolts41C >= signed definition price, and signed equipped458 < requested ID. This leaf has no ownership or availability predicate call. The bounded preview accepts only normal armor IDs0..4 and nonnegative signed-32 supplied prices; native code has no corresponding index validation.",
            "commit_order": ["0x2d27a4: ownership444+4*ID =1", "0x2d27a8: currency deduction helper24FCB8", "actor handle/type routing", "direct equip or queued effect"],
            "routing": "A handle with low16 index <= runtime table count, matching stored full handle, nonzero actor pointer and low byte of actor predicate24F208(argument396) nonzero delegates to43FCE8. Otherwise the caller invokes equip252098 then notification250FA8(argument4). The delegated path also returns1 after43FCE8 returns; this is not proof of immediate equip.",
            "currency_scope": "The deduction helper's callbacks/clamps are not simulated here. The code orders ownership and deduction before all actor routing and before the eventual equipped-ID store.",
        },
        "queued_effect": {
            "function_va": "0x43fce8", "consumer_va": "0x1f7dc0",
            "runtime_hero_member": "0x2170", "written_footprint_bytes": 13,
            "members": {"0x0": "requested armor ID", "0x4": "actor handle from actor+1B8", "0x8": "actor companion word from actor+1B4; semantic name unresolved", "0xc": "byte latch written1"},
            "queue_gate": "43FCE8 requires its actor handle lookup valid, hero byte+1C nonzero, and low byte of24F038(hero) zero. If any fails it invokes equip then notification immediately. The hero byte/predicate are not assigned player-facing meanings.",
            "publication": "Queue branch writes actor float+1AC=14, then hero217C latch1, then handle2174, ID2170, companion2178, and returns. Latch-before-payload ordering is not a proven atomic publication. These fields are runtime hero/actor members, not serialized save offsets.",
            "consumer": "1F7DC0 uses its object+14 hero pointer and queued record. The state2 block compares runtime singleton10731D00+B4 to object deadline+1C using fcmpu then ble. Ordered <= exits; > OR unordered reaches the equip block. It loads queued ID2170, calls1E2150, sends notification11EE0(argument4), then writes object state+18=3 after further calls. Other state transitions and callbacks are not simulated.",
            "consequence": "Ownership and currency may have committed while saved equipped458 still contains the prior armor. A purchase return1 or queued latch alone cannot establish equipped armor, finished animation, damage reduction or console load acceptance.",
        },
        "definition_dependency": {
            "root_pointer_slots": ["0x895504", "0x89f1bc"], "runtime_root_va": "0x101b9ee8",
            "record_relative_offset": "0x11c20", "stride": 40,
            "members": {"0x8": "float copied to hero runtime+1798 by1E2150", "0xc": "price word read by2D1C88"},
            "warning": "The runtime definition root is not the saved state. Equipped ID is insufficient to reconstruct the current runtime attribute. The float is not newly named damage reduction: its downstream use is not proven by this report.",
        },
        "skin_purchase_leaf": {
            "function_va": "0x27aa0", "calls": skin_calls,
            "admission": "Only signed price <= signed special-bolt balance is checked in this native leaf. It does not call ownership24B08, availability24B38 or selection26FC0. Already-owned and unavailable IDs are not independently rejected here; normal UI/script callers may impose additional gates.",
            "commit_order": ["0x27b00: selected480 =ID", "0x27b08: ownership45C+4*ID =1", "0x27b10: spent424 = low32(old spent+price)", "0x27b14: notification11EE0(argument4)"],
            "consequence": "An admitted repeated native leaf call can add the price again even when ownership was already nonzero. This is static leaf behavior, not a demonstrated UI action, exploit or editable-save invariant. Full caller eligibility and runtime notification effects remain outside scope.",
        },
        "recommended_annotations": [
            {"va": "0x43fce8", "name": "TOD_armor_effect_queue_or_equip_verified", "comment": "After purchase commit, valid handle/hero1C/predicate gates queue runtime hero2170 record; otherwise equip+notify directly. Latch precedes payload writes."},
            {"va": "0x1f7dc0", "name": "TOD_armor_effect_state_consumer_verified", "comment": "State2 fcmpu/ble deadline branch reaches queued armor equip for > or unordered; equip then notification, later state3. Runtime queue is not serialized."},
            {"va": "0x2d26d0", "name": "TOD_purchase_armor_commit_before_effect_verified", "comment": "Hero/signed bolts/equipped-ID gates; ownership and currency commit before actor routing; return1 does not imply immediate equip."},
            {"va": "0x27aa0", "name": "TOD_purchase_skin_leaf_signed_balance_verified", "comment": "Native leaf only tests signed price<=signed balance. Select/own/spent stores precede notification; no ownership/availability call."},
        ],
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())],
    }
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save size")
        data = path.read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        report["save_observation"] = {
            "sha256": hashlib.sha256(data).hexdigest().upper(), "size": len(data),
            "bolts_word": struct.unpack_from(">I", data, 0x41C)[0],
            "armor_ownership_words": list(struct.unpack_from(">5I", data, 0x444)),
            "equipped_armor_word": struct.unpack_from(">I", data, 0x458)[0],
            "armor_unlock_bytes": list(data[0x5774:0x5779]),
            "skin_ownership_words": list(struct.unpack_from(">9I", data, 0x45C)),
            "selected_skin_word": struct.unpack_from(">I", data, 0x480)[0],
            "spent_special_bolts_word": struct.unpack_from(">I", data, 0x424)[0],
            "scope": "Raw independent saved words only. Snapshot cannot establish a live queued effect, definition price/attribute, repeated purchase history or notification outcome.",
        }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path)
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2, allow_nan=False))
