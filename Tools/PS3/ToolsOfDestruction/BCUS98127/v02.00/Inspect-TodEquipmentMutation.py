"""Read-only pack/boot publication and selective-restart equipment suffix evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("bindings", Path(__file__).with_name("Inspect-TodWeaponBindings.py"))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)
RESET_IDS = (24, 26, 27, 28, 29, 30, 31)


def unsigned(value, bits):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < 1 << bits:
        raise ValueError(f"Expected an unsigned {bits}-bit integer")
    return value


def words(values, count):
    if not isinstance(values, (list, tuple)) or len(values) != count:
        raise ValueError(f"Expected {count} raw unsigned words")
    return tuple(unsigned(value, 32) for value in values)


def native_pack_preview(argument):
    """Native argument bit-pattern only; no Lua conversion or game execution."""
    value = unsigned(argument, 64)
    return {"pack_word": value & 0xFFFFFFFF, "selector_word": int(value != 0),
            "notification_type": 4, "equip_success": None}


def lua_integer_payload_preview(converted_integer):
    """Already-valid fctiwz int32 result, not floating conversion/admission."""
    if (not isinstance(converted_integer, int) or isinstance(converted_integer, bool) or
            not -(1 << 31) <= converted_integer < 1 << 31):
        raise ValueError("Expected an already-converted signed int32")
    # stfiwx stores the word, then lwz zero-extends it into the native64 argument.
    return native_pack_preview(converted_integer & 0xFFFFFFFF)


def boot_publication_preview(current_words, native_argument):
    """Detached native leaf suffix; stores boot0 even if it was already0."""
    selector, pack, _ = words(current_words, 3)
    unsigned(native_argument, 64)
    return {"words": [selector, pack, 0], "notification_type": 4, "equip_success": None}


def selective_suffix_preview(quick_select, history, pack_boot):
    """Only copied-prefix suffix selection. Not an executable/full reset model."""
    quick = words(quick_select, 32)
    recent = words(history, 3)
    selector, pack, boot = words(pack_boot, 3)
    # Inputs are exactly the lwz-zero-extended saved words, unlike arbitrary64
    # direct calls to the predicate. Unknown words and FFFFFFFF remain raw.
    filtered = lambda values: [0xFFFFFFFF if value in RESET_IDS else value for value in values]
    return {"quick_select": filtered(quick), "history": filtered(recent),
            "pack_boot": [selector, 0 if pack == 3 else pack, boot],
            "inventory_record_ids_reinitialized": list(RESET_IDS),
            "selector_equals_one_after": selector == 1,
            "equip_success": None}


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    def function(address):
        end = elf.functions[elf.functions.index(address) + 1]
        keep(address, end - address)

    checks = {
        0x888624: 0x101EFB20, 0x8A3BAC: 0x101EFB20,
        0x27A34: 0x2FA30000, 0x27A44: 0x9069043C, 0x27A54: 0x90690438,
        0x27A60: 0x4BFEA481, 0x27A78: 0x90690438, 0x27A88: 0x4BFEA459,
        0x26F78: 0x38800004, 0x26F80: 0x90AB0440, 0x26F84: 0x4BFEAF5D,
        0x2FB88: 0xFC20081E, 0x2FB8C: 0x7C204FAE, 0x2FB90: 0x80610080,
        0x2FB94: 0x4BFF7E9D, 0x2FAD0: 0xFC20081E, 0x2FAD4: 0x7C204FAE,
        0x2FAD8: 0x80610080, 0x2FADC: 0x4BFF7485,
        0x3CED80: 0x4BF8F391, 0x3CEDBC: 0x38A00484, 0x3CEDD0: 0x4BE83659,
        0x3CEE2C: 0x3BBE0284, 0x3CEE44: 0x809C0000,
        0x3CEE50: 0x2CA30000, 0x3CEE5C: 0x933C0000,
        0x3CEE6C: 0x809F042C, 0x3CEE80: 0x933F042C,
        0x3CEE88: 0x809F0430, 0x3CEE9C: 0x939F0430,
        0x3CEEA4: 0x809F0434, 0x3CEEB8: 0x93DF0434,
        0x3CEEBC: 0x813F043C, 0x3CEEC0: 0x2C890003,
        0x3CEEC4: 0x418602E4, 0x3CF1AC: 0x901F043C,
        0x3CF1B0: 0x4BFFFD18, 0x3CF158: 0x4BE832D1,
        0x3CECA4: 0x2B84001F, 0x3CECA8: 0x64A4FD00,
    }
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Equipment publication evidence changed at {address:#x}")
        keep(address, 4)
    for address in (0x27A30, 0x26F60, 0x2FAE8, 0x2FA30, 0x3CEC98, 0x3CED40, 0x35E110, 0x35DC80):
        function(address)
    if (elf.string(0x10002B10) != "PACK_WING" or elf.u32(0x8891C0) != 0x10002B10 or
            elf.u32(0x8886B8) != 0x40400000):
        raise ValueError("Native PACK_WING enum evidence changed")
    keep(0x2A4AC, 0x1AC)
    keep(0x10002B10, 10)
    keep(0x8891C0, 4)
    keep(0x8886B8, 4)
    report = {
        "confidence": "code-backed-detached-mutation-boundaries",
        "warning": "Exact USA v02.00 static assembly and optional plaintext observations only. Detached suffix previews neither execute native/Lua code nor change a save. No runtime equipment availability, successful equip, safe edit or gameplay-tested reset is inferred.",
        "pack_publication": {
            "native_va": "0x27a30", "store_order": ["0x43c", "0x438", "notification_type4"],
            "rule": "Native27A30 stores low32 into43C, then writes selector438 from its original64-bit zero test, then calls11EE0 with type4. Both zero/nonzero paths notify even if saved values already equal the requested result. No previous-state, ownership or enum-bound predicate appears in this leaf; this is not proof of accepted wrapper inputs or completed runtime equip.",
            "lua_wrapper_va": "0x2fae8",
            "lua_payload": "After the wrapper's earlier argument checks and13080 extraction, fctiwz at2FB88 writes an int32 payload with stfiwx; lwz2FB90 zero-extends that word into native r3. The already-valid converted payload therefore cannot carry arbitrary high32 bits. A native64 input0000000100000000 can yield pack0/selector1, but that mismatch is not produced by this Lua payload path. NaN, overflow, floating admission and error behavior are not emulated.",
            "scope": "The direct native64 preview describes bit-pattern arithmetic, not which script/gameplay callers can supply it or a player-facing movement name."},
        "boot_publication": {
            "native_va": "0x26f60", "lua_wrapper_va": "0x2fa30",
            "rule": "The boot wrapper also fctiwz/stfiwx/lwz-converts an admitted numeric value, but native26F60 ignores it, stores boot440=0, then calls11EE0(type4), including repeated zero stores. It does not write selector438, pack43C, history or quick-select in this leaf.",
            "scope": "No generic BOOT_GRIND/GRAV/CHARGE setter behavior or successful runtime boot change is inferred from the binding name."},
        "selective_restart_suffix": {
            "consumer_va": "0x3ced40", "predicate_va": "0x3cec98", "copied_prefix_size": "0x484",
            "quick_select": {"offset": "0x284", "count": 32, "type": "u32 BE raw item words"},
            "history_offsets": ["0x42c", "0x430", "0x434"], "reset_item_ids": list(RESET_IDS),
            "initializer_order": "3CED80 first calls35E110, whose35DC80 initializes pack/boot/history. The later252428 call3CEDD0 copies all484 live prefix bytes over that initialized prefix, before the item/history/pack filters. No later27A30/26F60 selector repair occurs in3CED40; the full-bank copy3CF158 publishes the resulting raw suffix.",
            "rule": "After live prefix0..484 is copied to the private bank, IDs24,26,27,28,29,30,31 have inventory records reinitialized. All32 quick-select words and each of42C/430/434 are tested separately through3CEC98; matching IDs becomeFFFFFFFF in place. There is no compaction, reordering, duplicate removal or refill of holes here. Item25 remains, as do raw unknown/sentinel words rejected by the unsigned<=31 predicate.",
            "wing_enum_anchor": {"name": "PACK_WING", "id": 3, "name_va": "0x10002b10", "value_va": "0x8886b8", "export_call_va": "0x2a640"},
            "pack_rule": "The copied pack43C is cleared only when exactly3 (PACK_WING); selector438 and boot440 remain copied raw words. This is not a call to27A30/26F60 and does not apply their notification/selector rules. In particular, selector1/type3 becomes selector1/type0, not selector0/type0. Other pack words, including TYPE_COUNT4 and unknown IDs, are retained without repair.",
            "publication": "The resulting private bank is later fully copied back with252428 at3CF158 before2D16A0(0,0,1). This field-specific suffix omits many other reset operations and does not model allocation, runtime aliases, restore requests or equip success.",
            "history_relationship": "Saved history records historical inventory callbacks, not pack/boot ownership or live equip. Pack/boot setters do not directly write history; selective restart transforms those words independently. Existing hero restore request selection can subsequently choose fallbacks, but no completed equip is implied."},
        "recommended_annotations": [
            {"va": "0x3ced40", "name": "TOD_selective_restart_private_bank_verified", "comment": "Initializes then overwrites live prefix484; independently filters selected item IDs from quick-select/history in place, clears PACK_WING3 but retains raw selector438/boot440. Full private-bank publication precedes level request; not a complete safe reset/equip contract."},
            {"va": "0x27a30", "name": "TOD_set_pack_type_native", "comment": "Stores low32 pack43C, original64-zero selector438, then notification type4 even unchanged. Named Lua wrapper fctiwz/stfiwx/lwz zero-extends an admitted int32 payload, so arbitrary high32/low32 mismatch is native-only arithmetic evidence."},
            {"va": "0x26f60", "name": "TOD_set_boot_type_native", "comment": "Ignores native argument, stores boot440=0 then notifies type4 even already0; leaves pack selector/history untouched. Named wrapper converts an admitted numeric payload but cannot turn this leaf into a general boot-type setter."}],
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save size")
        data = path.read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        quick = list(struct.unpack_from(">32I", data, 0x284))
        history = list(struct.unpack_from(">3I", data, 0x42C))
        equipment = list(struct.unpack_from(">3I", data, 0x438))
        report["save_observation"] = {
            "plaintext_sha256": hashlib.sha256(data).hexdigest().upper(), "size": len(data),
            "quick_select_raw_words": quick, "history_raw_words": history,
            "pack_boot_raw_words": equipment,
            "selective_suffix_only_preview": selective_suffix_preview(quick, history, equipment),
            "scope": "These raw words do not establish that a reset occurred, when history was published, current runtime equipment or private-bank identity. Sources stay unchanged."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2, allow_nan=False))
