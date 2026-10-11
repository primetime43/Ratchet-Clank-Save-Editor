"""Exact-build mission mutation byte ownership; immutable bounded previews only.

No original save writes, native execution, unsafe indexing or mission repair.
Preview flags describe storage behavior, not a player-facing completion verdict.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
CAPACITY, STRIDE, COUNT = 10, 12, 0x78
LIST_SIZE = 0x7C
ACTIVE, COMPLETED = 0x10148, 0x10AF8


def uint32(value):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("Expected an unsigned32-bit integer")
    return value


def detached_list(value, require_count=True):
    if not isinstance(value, (bytes, bytearray)) or len(value) != LIST_SIZE:
        raise ValueError("Expected one detached124-byte mission list")
    count = struct.unpack_from(">I", value, COUNT)[0]
    if require_count and count > CAPACITY:
        raise ValueError("Raw count exceeds physical mission-list capacity; unsafe native search is not emulated")
    return bytearray(value), count


def find_title(value, count, title):
    return next((i for i in range(count) if struct.unpack_from(">I", value, i * STRIDE)[0] == title), None)


def initialize_list_preview(value):
    """Only the35C760 mission loop: titles/descriptions cleared, flags retained."""
    result, _ = detached_list(value, require_count=False)
    for slot in range(CAPACITY):
        struct.pack_into(">2I", result, slot * STRIDE, 0xFFFFFFFF, 0xFFFFFFFF)
    struct.pack_into(">I", result, COUNT, 0)
    return bytes(result)


def add_preview(active, completed, title, description, flags):
    """Bounded ordinary storage model of2D1168, not a native API invocation."""
    a, ac = detached_list(active)
    c, cc = detached_list(completed)
    title, description, flags = uint32(title), uint32(description), uint32(flags)
    changed = False
    if find_title(c, cc, title) is None and find_title(a, ac, title) is None and ac < CAPACITY:
        struct.pack_into(">3I", a, ac * STRIDE, title, description, flags & 0xFF)
        struct.pack_into(">I", a, COUNT, ac + 1)
        changed = True
    return {"active": bytes(a), "completed": bytes(c), "changed": changed}


def complete_preview(active, completed, title):
    """Safe physical-domain2D0F78 model; destination flags are NOT source flags."""
    a, ac = detached_list(active)
    c, cc = detached_list(completed)
    title = uint32(title)
    index = find_title(a, ac, title)
    changed = False
    if find_title(c, cc, title) is None and index is not None:
        if cc == CAPACITY:
            raise ValueError("Completion would address the completed count word; native out-of-bounds writes are not emulated")
        start, target = index * STRIDE, cc * STRIDE
        c[target:target + 8] = a[start:start + 8]
        old_flags = struct.unpack_from(">I", c, target + 8)[0]
        struct.pack_into(">I", c, target + 8, old_flags | 2)
        struct.pack_into(">I", c, COUNT, cc + 1)
        struct.pack_into(">I", a, COUNT, ac - 1)
        for slot in range(index, ac - 1):
            a[slot * STRIDE:(slot + 1) * STRIDE] = a[(slot + 1) * STRIDE:(slot + 2) * STRIDE]
        changed = True
    return {"active": bytes(a), "completed": bytes(c), "changed": changed}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}

    def keep(va, size):
        guards[va] = elf.read(va, size)

    def require(va, word):
        if elf.u32(va) != word:
            raise ValueError(f"Mission mutation evidence changed at {va:#x}")
        keep(va, 4)

    for function in (0x2D0D60, 0x2D0DF0, 0x2D0F18, 0x2D0F78,
                     0x2D1168, 0x2776B0, 0x2776D8, 0x35C760, 0x35E110,
                     0x35DC80, 0x466A60, 0x35DFA8, 0x35DD98, 0x35E070, 0x35D9A0):
        keep(function, elf.functions[elf.functions.index(function) + 1] - function)
    for va, word in {
        0x2D0F18: 0x81230078, 0x2D0F40: 0x7D2903A6,
        0x2D1038: 0x7C0C192E, 0x2D103C: 0x813F0078,
        0x2D1054: 0x91040004, 0x2D1058: 0x807F0078,
        0x2D1070: 0x81480008, 0x2D1074: 0x61470002,
        0x2D1078: 0x90E80008, 0x2D1084: 0x907F0078,
        0x2D1094: 0x907E0078, 0x2D1138: 0x4200FF90,
        0x2D1214: 0x5786063E, 0x2D1220: 0x2B850009,
        0x2D1268: 0x90C90008, 0x2D1274: 0x917F0078,
        0x35C760: 0x2F830001, 0x35C7B0: 0x6C83FFFF,
        0x35C7B4: 0x2C03FFFF, 0x35C900: 0x90CC0000,
        0x35C904: 0x397D0148, 0x35C910: 0x91490004,
        0x35C914: 0x91490000, 0x35C924: 0x2FA80014,
        0x35C960: 0x90E50000, 0x35C964: 0x39660AF8,
        0x35C970: 0x93A40004, 0x35C974: 0x93A40000,
        0x35C984: 0x2C2A0014,
    }.items():
        require(va, word)
    # Independently enumerate exactly the12 destination-byte offsets in the
    # compaction loop; this includes unknown flags, not only title/description.
    byte_stores = []
    for va, word in elf.instructions(0x2D10D8, 0x2D1138):
        if word >> 26 == 38 and word >> 16 & 31 == 12:
            byte_stores.append({"va": hex(va), "entry_offset": word & 0xFFFF})
    if sorted(s["entry_offset"] for s in byte_stores) != list(range(12)):
        raise ValueError("Mission compaction byte footprint changed")
    # The inner initialization bodies contain only title/description stores.
    init_stores = []
    for start, end, base in ((0x35C908, 0x35C91C, 9), (0x35C968, 0x35C97C, 4)):
        stores = []
        for va, word in elf.instructions(start, end):
            if word >> 26 == 36 and word >> 16 & 31 == base:
                stores.append({"va": hex(va), "entry_offset": word & 0xFFFF, "size": 4})
        if sorted(s["entry_offset"] for s in stores) != [0, 4]:
            raise ValueError("Mission initialization entry footprint changed")
        init_stores.extend(stores)
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA v02.00 mutation byte ownership, not safe edit permission, a repair recipe or an in-game mission status reconstruction. Previews refuse malformed counts and never reproduce unsafe native memory accesses.",
        "layout": {"active_base": hex(ACTIVE), "completed_base": hex(COMPLETED),
                   "list_stride": hex(LIST_SIZE), "entry_stride": STRIDE,
                   "capacity": CAPACITY, "count_member": hex(COUNT),
                   "physical_lists_per_group": 20, "named_levels": 19},
        "initialization": {
            "function_va": "0x35c760", "loop_vas": ["0x35c8cc", "0x35c92c"],
            "entry_stores": init_stores, "gating": "This initializer branch requires low32 first argument1 and low32 second argument0000FFFF; it is not an unconditional reset call.",
            "rule": "Both20-list groups receive count0 and title/descriptionFFFFFFFF in each of10 physical entries. The mission initialization loops do not write entry flags+8. Unknown and optional bits therefore remain whatever was already in those words at these loop boundaries, not a guaranteed zero default.",
            "scope": "Pure preview covers only the constructor's mission loops. Following35E110 calls35D9A0, whose two nested9B0-byte zero-fills clear BOTH entire mission-list groups, including counts, IDs and flags. The loop's flag retention is not the final initialized-state result. Selective restart also reaches these zero-fills; restart_execution independently guards the call/base/size provenance. No stale startup flags or mission retention through this initializer is asserted.",
        },
        "completion_flags": {
            "function_va": "0x2d0f78", "destination_load_va": "0x2d1070", "destination_store_va": "0x2d1078",
            "rule": "Completion copies source title/description only, then ORs2 into the preexisting destination flags word. It neither copies source optional bit0 nor source unknown flags. Destination optional/unknown bits survive even when their entry was outside the previous completed count; a source optional mission can become nonoptional here if destination bit0 wasclear, and the reverse can occur if it wasalreadyset.",
            "scope": "This is exact storage behavior of this native path, not proof that any supplied actual mission experienced stale flag contamination. Other producers or memory initialization may affect those words.",
        },
        "compaction": {
            "byte_stores": byte_stores,
            "publication_order": ["Completed destination title", "Completed destination description", "Preexisting completed flags OR2", "Completed count increment", "Active count decrement", "Active entries after removed index copied left in order"],
            "rule": "Active compaction copies all12 bytes per surviving entry, preserving their unknown/optional flags and relative order. The old last occupied entry is not cleared after the count decrement; bytes beyond the new count are residual storage, not additional live missions. Appends overwrite all12 destination bytes, with only low8 incoming flag bits retained.",
            "scope": "Stores/count changes are sequential in the native function, not a proven atomic transaction. There is no separate global/world-flag setter call in the complete/add bodies; independently scripted dependencies are not ruled out.",
        },
        "bounds": {
            "search_va": "0x2d0f18", "add_capacity_check_va": "0x2d1220",
            "rule": "Title search uses the raw saved count as its loop limit without a10-entry clamp. Duplicate searches occur before add's unsigned active-count<10 gate. Completion bounds the found active index to0..9, but does not independently bound completed count or active compaction length.",
            "completed_full_boundary": "For completed count10, the first destination title store addresses list+78, the count word itself. Subsequent address calculations reread that word after the title write, so this is not safely modeled as a fixed12-byte spill into the next list. The inspector refuses such a completion and does not emulate memory corruption.",
            "inactive_scope": "A saved count0 hides all10 physical entries from native title search; residual flags/IDs do not make them current missions. Physical group slot19 remains unnamed, not a20th native game level.",
        },
        "recommended_annotations": [
            {"va": "0x2d0f18", "kind": "function", "name": "TOD_find_saved_mission_title_raw_count", "comment": "Searches title word through raw saved count, with no physical10-entry clamp; invoked before add capacity gate. Analysis bounds separately; residual entries outside count are not searched."},
        ],
        "instruction_guards": [{"va": hex(va), "bytes": raw.hex().upper()} for va, raw in sorted(guards.items())],
    }
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Expected verified plaintext save size")
        data = path.read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
            raise ValueError("Expected verified plaintext inventory IDs0..31")
        observations = []
        for group, base in (("active", ACTIVE), ("completed", COMPLETED)):
            for level in range(20):
                offset = base + level * LIST_SIZE
                count = struct.unpack_from(">I", data, offset + COUNT)[0]
                flags = [struct.unpack_from(">I", data, offset + i * STRIDE + 8)[0] for i in range(10)]
                observations.append({"group": group, "physical_level_slot": level, "named_level": level < 19,
                    "offset": hex(offset), "saved_count": count, "exceeds_capacity": count > 10,
                    "physical_flags": [f"0x{f:08x}" for f in flags],
                    "inactive_flags": [f"0x{f:08x}" for f in flags[min(count, 10):]]})
        report["save_observation"] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest().upper(),
            "lists": observations, "warning": "Raw inactive flags remain visible without being labeled current mission state. Supplied counts/flags do not establish how an entry was initialized or completed."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2))
