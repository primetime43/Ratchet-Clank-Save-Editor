"""Exact-build read-only saved-setting publication versus runtime application."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))


def unsigned(value, width=32):
    if type(value) is not int or not 0 <= value < 1 << width:
        raise ValueError(f"Expected explicit unsigned{width} bits")
    return value


def scheme_plan(argument):
    value = unsigned(argument)
    return {"saved_word": f"{value:08X}", "runtime_selector": value if value in (1, 2) else 0,
            "qualification": "Saved index is published first without local range normalization. Selector only, not named scheme, current runtime table, accepted Lua conversion or applied hardware state."}


def rumble_plan(argument):
    value = unsigned(argument, 64)
    enabled = value != 0
    return {"saved_byte": f"{value & 255:02X}", "runtime_flag_request": int(enabled),
            "actuator_clear_port_requests": [] if enabled else list(range(8)),
            "qualification": "Raw native argument: low8 stored, full64 zero test selects helper. Named Lua wrapper normalizes to0/1. Port requests are not attached devices, successful actuator changes or runtime state recovered from the saved byte."}


def surround_plan(argument, capability_word=None):
    value = unsigned(argument, 64)
    if capability_word is not None:
        capability_word = unsigned(capability_word)
    queried = value & 0xFFFFFFFF != 0
    if queried and capability_word is None:
        raise ValueError("Enabled surround requires an explicit runtime capability result")
    mode = (4 if capability_word == 6 else 5 if capability_word == 8 else 3) if queried else 1
    return {"saved_byte": f"{value & 255:02X}", "capability_query_selected": queried, "runtime_mode_request": mode,
            "qualification": "Raw native argument, low8 store before low32 helper test. Named Lua wrapper supplies0/1. Mode numbers are not speaker-layout names; deeper engine gates, callbacks, return codes and hardware success are not emulated."}


def bus_store_plan(engine_flags, bus_id):
    engine_flags, bus_id = unsigned(engine_flags), unsigned(bus_id)
    selected = bool(engine_flags & 0x10000) and bus_id <= 63
    return {"local_runtime_store_selected": selected, "runtime_record_offset": hex(bus_id * 0xB0) if selected else None,
            "qualification": "Local call-free5ADEF0 admission only. Runtime engine flag/table pointer validity is explicit, not saved. No native floating store, payload conversion, playback, loudness or saved-setting mutation modeled."}


def control_copies(elf, guards):
    expected_sources = {
        0: [0x1C006, 0x1C002, 0x1C004, 0x1C008, 0x1C018, 0x1C00E, 0x1C010, 0x1C014, 0x1C01C, 0x1C00C, 0x1C00A],
        1: [0x1C006, 0x1C016, 0x1C004, 0x1C008, 0x1C018, 0x1C010, 0x40, 0x1C014, 0x1C01C, 0x1C00C, 0x1C00A],
        2: [0x1C006, 0x1C002, 0x1C004, 0x1C008, 0x1C018, 0x1C00E, 0x40, 0x1C014, 0x1C01C, 0x1C00C, 0x1C00A],
    }
    catalogs = []
    for selector, start, end in ((0, 0x6966B8, 0x696994), (1, 0x696994, 0x696C94), (2, 0x696C94, 0x696F94)):
        pairs = {}
        for address in range(start, end, 4):
            raw = elf.u32(address)
            if raw >> 26 != 40:  # lhz
                continue
            previous, store = elf.u32(address-4), elf.u32(address+4)
            immediate = BINDINGS["signed"](raw & 65535, 16)
            data_reg, base_reg = raw >> 21 & 31, raw >> 16 & 31
            if (previous >> 26 != 15 or previous & 65535 != 2 or store >> 26 != 44 or
                    store >> 21 & 31 != data_reg or store >> 16 & 31 != previous >> 21 & 31 or
                    base_reg != (previous >> (21 if immediate < 0 else 16) & 31)):
                raise ValueError("Control halfword copy shape changed")
            source = immediate + (0x20000 if immediate < 0 else 0)
            destination = 0x20000 + BINDINGS["signed"](store & 65535, 16)
            if destination in pairs and pairs[destination]["source_offset"] != hex(source):
                raise ValueError("Conflicting repeated control copy")
            pairs.setdefault(destination, {"source_offset": hex(source), "destination_offset": hex(destination), "store_sites": []})["store_sites"].append(hex(address+4))
            for va in (address-4, address, address+4):
                guards[va] = elf.read(va, 4)
        ordered = list(pairs.values())
        if [int(p["source_offset"], 0) for p in ordered] != expected_sources[selector] or list(pairs) != list(range(0x1C206, 0x1C21C, 2)):
            raise ValueError("Control copy mapping changed")
        if sum(len(p["store_sites"]) for p in ordered) != (11 if selector == 0 else 12):
            raise ValueError("Control duplicated final-loop tail changed")
        catalogs.append({"selector": selector, "pairs": ordered})
    return catalogs


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}
    expected = {
        0x888624: 0x101EFB20, 0x88B224: 0x101EFB20,
        0x8A90C8: 0x1071F458, 0x8AA4D0: 0x10731648,
        0x8A80D8: 0x1067BF3C, 0x8A8174: 0x1067BF3C, 0x8A80C8: 0x1067BE9C,
        0x88865C: 0, 0x888644: 0x3F800000,
        0x271C4: 0x2F8B0001, 0x271D0: 0x2F0B0002, 0x271D4: 0x916914BC,
        0x271CC: 0x38600001, 0x271DC: 0x38600000, 0x27200: 0x38600002,
        0x26CE8: 0x988914D5, 0x26D1C: 0x2FA30000, 0x26D30: 0x986914D4,
        0x60B7D4: 0x38000001, 0x60B7D8: 0x90090004, 0x60C598: 0x93890004,
        0x696128: 0x2F830000, 0x696138: 0x38000001,
        0x696178: 0x38000004, 0x69617C: 0x2C030006,
        0x696180: 0x2F030008, 0x696188: 0x38000003, 0x696190: 0x38000005,
        0x6966B8: 0x2F830001, 0x6966BC: 0x419E02D8,
        0x6966C0: 0x2C030002, 0x6966C4: 0x418205D0,
        0x6966D4: 0x88AA0012, 0x6966DC: 0x4D9E0020,
        0x7FCB0: 0x38600001, 0x7FCB4: 0xC03D14C8,
        0x7FCC0: 0x38600006, 0x7FCC4: 0xC03D14C4,
        0x7FCD0: 0x3860000C, 0x7FCD4: 0xC03D14CC,
        0x5ADEF4: 0x2B03003F, 0x5ADF00: 0x548003DE,
        0x5ADF08: 0x419E0024, 0x5ADF0C: 0x41990020,
        0x5ADF18: 0x1CA300B0, 0x5ADF28: 0xD02B0000,
        0x5B51DC: 0x546003DE, 0x5B51E4: 0x409E001C,
        0x5B5220: 0x4182FFC8, 0x5B5228: 0x81660030, 0x5B523C: 0x4E800421,
        0x2C660: 0x78630FE2, 0x2C868: 0x78630FE2,
        0x24EBC: 0xD1A914C8, 0x276FC: 0xD1A914C4,
        0x27744: 0xD1A914CC, 0x276C8: 0xD1A914B0,
    }
    for va, value in expected.items():
        if elf.u32(va) != value:
            raise ValueError(f"Settings-apply evidence changed at {va:#x}")
        guards[va] = elf.read(va, 4)
    calls = {0x271E4: 0x128B0, 0x27204: 0x128B0, 0x26CEC: 0x103D0,
             0x26D38: 0x12020, 0x26D50: 0x11C20, 0x276FC+4: 0x7FC98,
             0x24EC0: 0x7FC98, 0x27748: 0x7FC98,
             0x7FCB8: 0x114A0, 0x7FCC8: 0x114A0, 0x7FCD8: 0x114A0,
             0x696144: 0x5B51B8, 0x696170: 0x5B4988,
             0x5B4994: 0x6141E0, 0x5B5204: 0x5B3EB8,
             0x2C664: 0x26CD0, 0x2C86C: 0x26D18}
    for va, target in calls.items():
        raw = elf.u32(va)
        if raw >> 26 != 18 or not raw & 1 or BINDINGS["branch_target"](raw, va) != target:
            raise ValueError("Settings apply call changed")
        guards[va] = elf.read(va, 4)
    for thunk, target in ((0x128B0, 0x6966B8), (0x103D0, 0x696128),
                           (0x12020, 0x60B7D0), (0x11C20, 0x60C568), (0x114A0, 0x5ADEF0)):
        if [elf.u32(thunk+i) for i in (0, 4, 8)] != [0xF8410028, 0x3C420002, 0x3842FF24]:
            raise ValueError("Settings apply cross-TOC adjustment changed")
        raw = elf.u32(thunk+12)
        if raw & 1 or BINDINGS["branch_target"](raw, thunk+12) != target:
            raise ValueError("Settings apply thunk target changed")
        guards[thunk] = elf.read(thunk, 16)
    apis = []
    for slot, name, native in ((0x889644, "set_control_scheme", 0x271B0),
                              (0x889724, "set_surround_on", 0x26CD0),
                              (0x88970C, "set_rumble_on", 0x26D18),
                              (0x8896CC, "set_voice_vol", 0x276D0),
                              (0x8896AC, "set_sound_vol", 0x24E90),
                              (0x8896BC, "set_music_vol", 0x27718),
                              (0x889764, "set_camera_speed", 0x276A8)):
        pointer, descriptor = elf.u32(slot), elf.u32(slot+4)
        wrapper = elf.u32(descriptor)
        end = elf.functions[elf.functions.index(wrapper)+1]
        if elf.string(pointer) != name or elf.descriptors[wrapper] != 0x88FF38 or not any(
                w >> 26 == 18 and w & 1 and BINDINGS["branch_target"](w, a) == native
                for a, w in elf.instructions(wrapper, end)):
            raise ValueError("Named setting setter changed")
        for va, size in ((slot, 8), (pointer, len(name)+1), (descriptor, 8), (wrapper, end-wrapper)):
            guards[va] = elf.read(va, size)
        apis.append({"name": name, "native_va": hex(native), "wrapper_va": hex(wrapper), "slot_va": hex(slot)})
    for function, toc in [(x, 0x88FF38) for x in (0x271B0, 0x26CD0, 0x26D18, 0x276A8, 0x276D0, 0x24E90, 0x27718, 0x7FC98)] + [
            (x, 0x8AFE5C) for x in (0x60B7D0, 0x60C568, 0x696128, 0x6966B8, 0x5ADEF0, 0x5B51B8, 0x5B4988)]:
        if elf.descriptors[function] != toc:
            raise ValueError("Settings apply function TOC changed")
        guards[function] = elf.read(function, elf.functions[elf.functions.index(function)+1]-function)
    port_sites = []
    for port in range(8):
        site = 0x60C5B4 + port * 0x2C
        if BINDINGS["branch_target"](elf.u32(site), site) != 0x839A2C or not elf.u32(site) & 1:
            raise ValueError("Rumble direct-actuator import request changed")
        # The final unrolled request uses the same port literal but reverses the two byte stores.
        literal_va = site-12
        if elf.u32(literal_va) != 0x38600000 | port:
            raise ValueError("Rumble port literal changed")
        for va in (site, literal_va, site-8, site-4):
            guards[va] = elf.read(va, 4)
        port_sites.append({"port": port, "call_va": hex(site)})
    guards[0x839A2C] = elf.read(0x839A2C, 8)  # Already independently NID-mapped cellPadSetActDirect stub.
    copies = control_copies(elf, guards)
    report = {
        "confidence": "exact-build-saved-publication-and-runtime-apply-boundaries",
        "warning": "USA BCUS98127 v02.00 static read-only evidence. No native settings apply, hardware probing, SDK calls, Lua execution or new editing permission.",
        "named_setters": apis,
        "control_scheme": {
            "saved_offset": "0x114bc", "rule": "271B0 stores the supplied low32 index at saved114BC BEFORE runtime128B0->6966B8. Exactly1 requests selector1; exactly2 selector2; ALL other indices selector0 while the original saved word remains unnormalized. Named get_num_control_schemes returns2, not proof setter2 or raw unknown indices are rejected.",
            "runtime_rule": "Call-free6966B8 resolves8AA4D0=10731648, then its pointed runtime table, byte+12 count and pointer entries stride8. Count0 skips its halfword stores, after the caller already published the saved index. Each selected route copies eleven halfword source members to runtime object1C206..1C21A; repeated final-loop tail sites in selectors1/2 have the same last pair. The source/destination members are runtime, NOT GAME.SAV offsets, button names, a device-count guarantee or stored control mappings. Valid pointers and stable observed counts/records remain required; no runtime table inferred from a save.",
            "copies": copies},
        "rumble": {"saved_offset": "0x114d4", "rule": "26D18 stores low8 at saved114D4 BEFORE a FULL64 zero test's selected helper. Nonzero calls12020->60B7D0, whose complete body only sets runtime1071F458+4 to1. Zero calls11C20->60C568: first clears that runtime flag, then issues eight cellPadSetActDirect requests for ports0..7 with both first actuator bytes zero. External return codes are not checked; all eight requests remain explicit even if an earlier one fails. No attached-port count, successful stop, hardware availability or save rollback is proven.",
            "wrapper_limit": "Named set_rumble_on wrapper2C7C0 validates its argument and normalizes boolean conversion to0/1 before26D18. Raw direct-native256 would store byte0 but select enable, and high64-only nonzero also selects enable; these are instruction boundaries, not accepted named-Lua calls or saved-byte history.",
            "port_requests": port_sites},
        "surround": {"saved_offset": "0x114d5", "rule": "26CD0 stores low8 at saved114D5 BEFORE103D0->696128. That helper tests LOW32 argument: zero selects mode1 without the capability query; nonzero calls5B4988->6141E0, then selects mode4 for result6, mode5 for result8, mode3 otherwise. All delegate5B51B8. Mode numbers are not proven speaker-layout names; selected requests are not hardware success.",
            "apply_boundary": "5B51B8 requires runtime engine1067BF3C+14 flag0x10000, then a nonnull5B3EB8 lookup. Either failure returns0 locally; admitted lookup calls virtual+30 with the selected mode.696128 normalizes the low32 helper result to nonzero/zero, but26CD0 ignores that result and does not locally undo saved114D5. Named set_surround_on wrapper2C5B8 supplies normalized0/1. Raw native256 stores byte0 while selecting enabled query; high64-only nonzero has low32 zero and selects mode1. No inferred layout, supported hardware or full callback final-state model."},
        "audio_volumes": {"saved_offsets": ["0x114c4", "0x114c8", "0x114cc"],
            "rule": "Voice276D0, effects24E90 and music27718 first store their respective ordinary-finite0..1-clamped value, then ALL call7FC98. That routine reapplies effects to bus1, voice to bus6, music to bus12 IN THAT ORDER. Each saved float is loaded immediately before its own114A0->5ADEF0 call, not captured as one atomic triple; later samples can differ. Original remaining values are not clamped again by this leaf.",
            "runtime_boundary": "Complete call-free5ADEF0 writes supplied float at runtime table base+busID*B0 only if engine1067BF3C+14 flag0x10000 is set AND unsigned busID<=63. Otherwise it returns0 without this store.7FC98 does not test those return values; saved publication is not rolled back locally. This is runtime storage, not extra saved floats or proof of measured volume/playback. Valid runtime pointers, FPR conversion/FPSCR and nonfinite payload behavior remain qualified.",
            "camera_contrast": "Camera-speed276A8 stores its ordinary-finite0..1-clamped value at saved114B0 and returns with no calls, unlike the three audio setters. No guessed sensitivity unit, runtime camera effect or safe edit range."},
        "snapshot_limit": "Saved scheme/rumble/surround/volume values survive failed or skipped local apply paths. GAME.SAV does not reveal engine gates, attached ports, active runtime halfwords, capability query results, callback outcomes or whether these setters ever executed. Viewing preserves raw values and opaque bytes; does not normalize or apply them.",
        "recommended_annotations": [
            {"va": "0x271d4", "kind": "comment", "name": "TOD_control_scheme_saved_publish_before_runtime_selector", "comment": "Stores original low32 to saved114BC before128B0->6966B8: exactly1/2 request selector1/2, all other raw indices selector0 without rewriting saved word. Runtime table/count may skip apply; not scheme names or accepted edit range."},
            {"va": "0x6966b8", "name": "TOD_control_scheme_runtime_halfword_copy_routes", "comment": "Call-free runtime table10731648, count byte12, pointer-entry stride8. Three routes copy eleven halfwords to object1C206..1C21A, count0 skips; exact source pairs in settings_apply. Not saved mappings, button names or hardware success."},
            {"va": "0x60c568", "name": "TOD_rumble_disable_runtime_flag_then_eight_port_requests", "comment": "Clears runtime1071F458+4 then unrolled cellPadSetActDirect ports0..7 with first actuator bytes zero. External returns ignored, no attached-port count, confirmed stop or rollback. Saved114D4 caller publishes first."},
            {"va": "0x696128", "name": "TOD_surround_runtime_probe_select_and_apply_mode", "comment": "Low32 zero->mode1, otherwise capability query result6->4/8->5/other->3.5B51B8 engine flag10000/non-null lookup gates and virtual30. Caller already stores saved114D5 and ignores normalized return; numeric modes not layout names."},
            {"va": "0x5adef0", "name": "TOD_audio_bus_runtime_float_store_if_engine_ready", "comment": "Call-free engine1067BF3C+14 flag10000 and unsigned bus<=63 select runtime base+bus*B0 float store; otherwise0/no store. Saved-volume setters publish before7FC98 replays effects1/voice6/music12 and ignores these returns. Not playback or extra saved state."},
        ],
        "instruction_guards": [{"va": hex(a), "bytes": raw.hex().upper()} for a, raw in sorted(guards.items())],
    }
    if save_path is not None:
        raw = Path(save_path).read_bytes()
        if len(raw) != 0x906F0 or any(struct.unpack_from(">I", raw, i*20)[0] != i for i in range(32)):
            raise ValueError("Not verified plaintext inventory layout")
        report["save_observation"] = {"sha256": hashlib.sha256(raw).hexdigest().upper(),
            "scheme_bits": raw[0x114BC:0x114C0].hex().upper(),
            "rumble_byte": f"{raw[0x114D4]:02X}", "surround_byte": f"{raw[0x114D5]:02X}",
            "volume_bits": {hex(a): raw[a:a+4].hex().upper() for a in (0x114C4, 0x114C8, 0x114CC)},
            "opaque_tail": raw[0x114D6:0x114D8].hex().upper(), "qualification": report["snapshot_limit"]}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2, allow_nan=False))
