"""Read-only equipment history dispatch, restore requests and menu fallback evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("bindings", Path(__file__).with_name("Inspect-TodWeaponBindings.py"))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)


def normal_history(words):
    if len(words) != 3 or any(not isinstance(v, int) or isinstance(v, bool) or not -1 <= v < 32 for v in words):
        raise ValueError("Preview requires three normal item IDs or -1")
    return tuple(words)


def restore_requests_preview(words):
    """Only detached normal-domain request selection; not equip success or callback simulation."""
    latest, previous, _ = normal_history(words)
    selected = 0 if latest in (-1, 30) else latest
    seed = previous if latest == 0 else latest
    seed = 1 if seed == -1 else seed
    return {"equip_request": selected, "runtime_history_seed_if_empty": seed}


def menu_history_preview(words):
    """Detached selection for the two runtime menu fields, without mutating saved history."""
    latest, previous, older = normal_history(words)
    primary = previous if latest in (-1, 0) else latest
    secondary = older if previous in (-1, 0) or previous == primary else previous
    return {"runtime_5034": -1 if primary == 0 else primary,
            "runtime_5030": -1 if secondary == 0 else secondary}


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    def function(address):
        end = elf.functions[elf.functions.index(address)+1]
        keep(address, end-address)

    for address, expected in {
            0x89554C: 0x84A4B8, 0x8A41A8: 0x84A4B8, 0x84A4E0: 0x8666D8,
            0x8666D8: 0x1F5570, 0x8666DC: 0x88FF38,
            0x1F5588: 0x80AB0188, 0x1F558C: 0x83A51A68,
            0x1F5598: 0x909D0434, 0x1F559C: 0x913D0430, 0x1F55A8: 0x907D042C,
            0x1F5CB4: 0x919D0140, 0x1F5CB8: 0x915D0144,
            0x1E3840: 0x8086042C, 0x1E3844: 0x83860430,
            0x1E3838: 0xEB625630, 0x1E3884: 0x2366001E,
            0x1E38A4: 0x48012FE5, 0x1E38D4: 0x4BE30A7D,
            0x1435C: 0x48452C7C, 0x466FD8: 0x8003013C,
            0x466FE8: 0x9083011C, 0x466FEC: 0x90A3013C,
            0x26CE5C: 0x8169042C, 0x26CE60: 0x81490434,
            0x26CE68: 0x81290430, 0x26CE6C: 0x2B800001,
            0x26CE88: 0x7C804800, 0x26CECC: 0x915F5030,
            0x1E33D4: 0x3AA31E00, 0x1E3474: 0x80E25614,
            0x1E34A4: 0x90F40000, 0x1F5DD8: 0x909C0188,
            0x46724C: 0x83BE0000, 0x4672D8: 0x2C9D0002,
            0x467348: 0x3BA00002, 0x46734C: 0x93BE0000,
            0x467344: 0x9BBE0008, 0x467378: 0x2F040000,
            0x467380: 0x409A0124, 0x4674AC: 0x808B0028,
            0x4674C0: 0x4E800421, 0x4674C8: 0x4BFFFEBC,
            0x467A30: 0x38030110, 0x467A50: 0x889F0008,
            0x467A6C: 0x987F0008, 0x467A78: 0x4BFFF7B1,
            0x467A7C: 0x889F0008, 0x467A90: 0x9BBF0008,
            0x467A94: 0x4086FFDC}.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Equipment lifecycle evidence changed at {address:#x}")
        keep(address, 4)
    restore_constant = elf.descriptors[0x1E33C8]+(elf.u32(0x1E3838)&0xFFFF)
    if elf.read(restore_constant, 8) != bytes.fromhex("FFFFFFFF00000001"):
        raise ValueError("Restore fallback arithmetic constant changed")
    keep(restore_constant, 8)
    for address in (0x1F5570, 0x1F5C18, 0x1F5DB8, 0x1F6888, 0x466E28,
                    0x466E88, 0x466EC0, 0x466FD8, 0x26CE30,
                    0x467228, 0x467908, 0x467A30):
        function(address)
    keep(0x1E3468, 0x40)
    keep(0x84A4B8, 0x2C)
    for descriptor, code in ((0x874BC0, 0x467228), (0x874BE8, 0x467908), (0x874BF0, 0x467A30)):
        if elf.u32(descriptor) != code or elf.u32(descriptor+4) != elf.descriptors[code]:
            raise ValueError("Equipment lifecycle descriptor identity changed")
        keep(descriptor, 8)
    keep(0x1E382C, 0xB0)
    keep(0x14350, 0x10)
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA v02.00 static lifecycle plus detached observations. Request selection is not equip success, gameplay validation or an editor write rule. No original bytes are modified.",
        "storage": {"history_offsets": ["0x42c", "0x430", "0x434"],
                    "word_type": "int32 BE item ID snapshots; preserve original bits",
                    "runtime_pending_item_member": "0x140", "runtime_active_handle_member": "0x144",
                    "runtime_recent_ids_member": "0x11c", "runtime_recent_count_member": "0x13c"},
        "restore_requests": {"consumer_va": "0x1e33c8", "selection_block_va": "0x1e382c",
                             "equip_request_va": "0x1e38a4", "equip_wrapper_va": "0x1f6888",
                             "queue_seed_call_va": "0x1e38d4", "queue_seed_va": "0x466fd8",
                             "rule": "The first restore request uses saved42C except -1 or item30 becomes item0. The separate recent-equipment seed uses42C unless42C==0, then430; seed -1 becomes item1. Seed466FD8 only writes runtime11C/count13C when count13C==0. Therefore the two saved words do not represent simultaneous equipped weapons.",
                             "eligibility": "For this request's mode0,1F6888 additionally requires saved inventory ownership byte+10 nonzero. Definition flag2 can impose an ammo comparison, with flag10 bypass; item30 has further runtime gates but is mapped to0 by this restore selection. A request can fail, and its return is not used to assume an accepted equip here.",
                             "reset": "Earlier1F5DB8->1F5C18 resets runtime pending ID140=-1 and active equipment handle144=0, without clearing these saved history words in that function. It reconstructs other inventory runtime state first; the saved requests follow later.",
                             "scope": "The reached hero initialization path has earlier runtime gates. Pure preview accepts only normal IDs -1..31 and models selection, not initialization, callback execution, ownership, ammo or later runtime changes."},
        "menu_fallback": {"consumer_va": "0x26ce30", "runtime_primary_member": "0x5034", "runtime_secondary_member": "0x5030",
                          "rule": "Menu primary uses42C except -1/0 selects430. Secondary uses430 unless it is -1/0 or equal to primary, then uses434. Finally each selected0 becomes -1. The fallback434 is not rechecked for duplication; this is not a general distinct-item filter or saved-history repair.",
                          "scope": "Only the two runtime fields in this consumer; no localized UI label, player selection or equip success inferred."},
        "history_dispatch": {"table_va": "0x84a4b8", "history_slot_offset": "0x28", "slot_va": "0x84a4e0",
                             "descriptor_va": "0x8666d8", "updater_va": "0x1f5570",
                             "owner": "Hero initialization1E33C8 installs table84A4B8 at hero+1E00;1F5DB8 stores hero in this inventory's188. The history callback's188->hero1A68 therefore resolves these serialized words, not an unrelated menu object.",
                             "step_va": "0x467228", "pump_va": "0x467a30", "call_va": "0x4674c0",
                             "runtime_state_member": "0x110", "entry_latch_member": "0x118", "pending_item_member": "0x140",
                             "gate": "The indirect history callback runs in state110==2 only when the step's second argument is nonzero. Pump467A30 converts entry latch118 to a boolean, clears it, calls the step and repeats when the step raised118 again. State1's transition sets state2 and raises118, so its next step can dispatch the history callback within the same pump invocation.",
                             "ordering": "The history callback precedes the state2 active-object lookup and pending140/current-item checks. It is not guarded by those later checks. It snapshots the native active-item getter; it is not an immediate request setter and does not first reject duplicate or -1 history values.",
                             "limits": "Confirmed state-entry/latch dispatch, not every frame, every script call or every successful weapon equip. Physical animation time, all causes of phase transitions and gameplay acceptance remain unvalidated."},
        "equipment_request": {"wrapper_va": "0x1f6888", "native_request_va": "0x467908", "pending_member": "0x140",
                              "rule": "After wrapper eligibility,467908 mode0 requires table+14 predicate, saved inventory ownership and a runtime158 restriction. An already active request can return1 without a pending store. Otherwise it stores itemID into runtime140 and returns1; it never directly stores saved42C/430/434. A successful request return therefore does not prove history changed or equipping finished.",
                              "scope": "Concrete queued-request versus later entry callback separation. Runtime restriction158 and predicate policy are not given player-facing names."},
        "recommended_annotations": [
            {"va": "0x467228", "name": "TOD_inventory_equipment_state_step_verified", "comment": "Equipment state110 step; state2 with entry argument dispatches saved-history callback table+28 before active/pending checks."},
            {"va": "0x467a30", "name": "TOD_inventory_equipment_state_pump_verified", "comment": "Consumes/clears entry latch118; calls467228 and repeats when transition raises latch. Not an unconditional saved-history tick."},
            {"va": "0x467908", "name": "TOD_inventory_request_equipment_verified", "comment": "Guarded mode0 equipment request queues runtime pendingID140 or returns already-active success; does not directly write serialized history."},
            {"va": "0x466fd8", "name": "TOD_inventory_seed_recent_equipment_if_empty_verified", "comment": "Writes runtime recentID11C/count13C=1 only when count was0;1E33C8 supplies saved-history-derived fallback seed."},
            {"va": "0x84a4b8", "kind": "data", "size": 44, "name": "TOD_hero_inventory_dispatch_table_verified", "comment": "11 descriptor pointers installed at hero+1E00. Slot+28 points8666D8->1F5570 history updater; exact owner and gated call established."}],
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save size")
        data = path.read_bytes()
        if any(struct.unpack_from(">I", data, i*0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        words = list(struct.unpack_from(">3i", data, 0x42C))
        known = all(-1 <= value < 32 for value in words)
        report["save_observation"] = {"sha256": hashlib.sha256(data).hexdigest().upper(), "size": len(data),
            "raw_history_words": words, "raw_history_hex": data[0x42C:0x438].hex().upper(),
            "normal_catalog_domain": known,
            "restore_request_selection_only": restore_requests_preview(words) if known else None,
            "menu_selection_only": menu_history_preview(words) if known else None,
            "scope": "Snapshot history does not reveal actual current runtime equipment, accepted restore, event count or callback time. Unknown signed words are retained raw and do not receive a normal-domain preview."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2, allow_nan=False))
