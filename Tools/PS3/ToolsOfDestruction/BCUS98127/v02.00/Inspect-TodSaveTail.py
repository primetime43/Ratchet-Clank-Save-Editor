"""Read-only exact-build replay/restart lifecycle and retained segment-scalar median."""
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


def restart_increment_preview(value):
    """Arithmetic only, never a request to change a save or execute a reset."""
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("Counter must be an unsigned 32-bit integer")
    return min((value + 1) & 0xFFFFFFFF, 1000)


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    def function(address):
        end = elf.functions[elf.functions.index(address) + 1]
        keep(address, end - address)

    # Exact assembly establishes both saved-state bases and meaningful arithmetic.
    for address, expected in {
            0x8A6914: 0x10027410, 0x8A6918: 0x101EFB20,
            0x8A3BAC: 0x101EFB20, 0x8A3BBC: 0x10200FC8,
            0x8A3BA8: 0x3F000000, 0x8A3BB0: 0,
            0x89F188: 0x101EFB20,
            0x48A5B4: 0x808269F4, 0x48A5B8: 0x4BDC5B41,
            0x48A5C4: 0x409E0018, 0x48A5C8: 0x806269F8,
            0x48A5CC: 0x38000001, 0x48A5D0: 0x3C830009,
            0x48A5D4: 0x900406EC,
            0x35E1B4: 0x93FE06EC, 0x35E1B8: 0x93BE06E4,
            0x3CEFD0: 0x80FF06EC, 0x3CEFD4: 0x2C070000,
            0x3CEFD8: 0x40820018, 0x3CEFE8: 0x4BFFFB29,
            0x3CEFEC: 0xD03A8754, 0x3CF0E8: 0x82FF06EC,
            0x3CF0F0: 0x38D70001, 0x3CF100: 0x212403E8,
            0x3CF124: 0x93FE06EC, 0x3CF140: 0x4BE837F9,
            0x3CF158: 0x4BE832D1, 0x3CF16C: 0x4BF02535,
            0x3CECAC: 0x38600001, 0x3CECA8: 0x64A4FD00}.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Save-tail evidence changed at {address:#x}")
        keep(address, 4)
    if elf.string(0x10027410) != "-replay":
        raise ValueError("Native replay option name changed")
    keep(0x10027410, 8)
    for address in (0x35E110, 0x3CED40, 0x3CEB10, 0x3CEC98,
                    0x3CF1B8, 0x2D14D0, 0x2D1860, 0x2D16A0):
        function(address)
    keep(0x48A5B0, 0x2C)
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA v02.00 static lifecycle plus read-only save observations. Native replay terminology is confirmed, not a localized Challenge Mode label, death count, gameplay-tested edit, or proof of completed playthroughs.",
        "tail_words": {
            "unknown_offset": "0x906e4", "saved_load_offset": "0x906e8",
            "restart_offset": "0x906ec", "type": "u32 BE",
            "initializer_va": "0x35e110",
            "initializer_rule": "35E110 clears906E4 and906EC; this alone does not name906E4 or prove padding. It does not directly clear906E8.",
            "counter_getter_va": "0x2d14d0", "nonzero_predicate_va": "0x2d1860",
            "cli_option": "-replay", "cli_option_va": "0x10027410",
            "cli_parser_va": "0x48a270", "cli_store_va": "0x48a5d4",
            "cli_rule": "Exact -replay string equality stores1 at906EC. Nonzero predicate therefore has engine replay context; arbitrary raw counter values are retained."},
        "restart_lifecycle": {
            "reset_va": "0x3ced40", "staging_pointer_member": "0x80",
            "increment": "min(wrapping_u32(old906EC + 1),1000); FFFFFFFF wraps to0 before the cap, so this is not unconditional saturation of all malformed values.",
            "settings_preserved": {"offset": "0x114a8", "size": "0x30"},
            "grid_blocks_preserved": {"offset": "0x114d8", "count": 21, "stride": "0x60dc", "end_exclusive": "0x906e4"},
            "cleared_counter_range": {"offset": "0x5550", "size": "0x188", "end_exclusive": "0x56d8"},
            "reset_inventory_ids": [24, 26, 27, 28, 29, 30, 31],
            "reset_id_predicate_va": "0x3cec98", "reset_id_mask": "0xfd000000",
            "rule": "Initializes staging save; preserves selected ranges from current state; resets selected inventory records/history; increments capped replay/restart word; clears5550..56D8; copies full906F0 staging state back and requests destination0 via2D16A0(0,0,1). This list is not a complete specification for safely invoking a reset.",
            "alternate_copy_va": "0x3cf1b8",
            "alternate_copy_rule": "Copies full staging906F0 state back without the selective-reset/increment sequence, then calls2D16A0(18,1,1). Destination18 is native level fastoon_return, not restart destination0."},
        "first_restart_time_median": {
            "offset": "0x8754", "type": "f32 BE", "calculator_va": "0x3ceb10",
            "write_va": "0x3cefec", "write_gate": "Only if old906EC is0 in3CED40.",
            "source": {"first_offset": "0x494", "world_count": 20, "world_stride": "0x408", "segment_count": 10, "segment_stride": "0x30", "member_offset": "0xc"},
            "calculation": "Collects saved finalized segment scalar/time-proxy floats strictly greater than0, inserts descending, returns middle value for odd count or float32 half the sum of middle pair for even count. Existing segment provenance establishes max(0, baseline + modifier), not a named completion-time API or verified time units; the compatibility key first_restart_time_median is not proof of time semantics.",
            "empty_input_caveat": "No native empty-count guard: even-count path reads stack scratch for zero entries. Inspection does not emulate that undefined observation or invent a0 default.",
            "retention": "Later restarts skip recomputing8754 in this path; this is a retained staging aggregate, not a guarantee that every lifecycle preserves it. Current segment scalars may be zero while8754 remains nonzero."},
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        if Path(save_path).stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save size")
        data = Path(save_path).read_bytes()
        if any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        words = [{"offset": hex(a), "raw_hex": data[a:a + 4].hex().upper(),
                  "value": struct.unpack_from(">I", data, a)[0]} for a in (0x906E4, 0x906E8, 0x906EC)]
        value = struct.unpack_from(">f", data, 0x8754)[0]
        positive = sum(struct.unpack_from(">f", data, 0x494 + w * 0x408 + s * 0x30)[0] > 0
                       for w in range(20) for s in range(10))
        report["save_observation"] = {"plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "tail_words": words, "engine_replay_predicate": words[2]["value"] != 0,
            "restart_increment_arithmetic_preview": restart_increment_preview(words[2]["value"]),
            "first_restart_time_median_raw_hex": data[0x8754:0x8758].hex().upper(),
            "first_restart_time_median": value if math.isfinite(value) else str(value),
            "currently_positive_completion_times": positive,
            "warning": "Preview is arithmetic evidence only; no save bytes or runtime state are changed. Retained8754 is not recomputed from current segment records."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path, help="Plaintext working copy; read-only")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2, allow_nan=False))
