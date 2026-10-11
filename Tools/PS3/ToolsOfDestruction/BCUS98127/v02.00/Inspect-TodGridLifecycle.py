"""Read-only saved-grid publication, menu-buffer synchronization and image-only mode evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("storage", Path(__file__).with_name("Inspect-TodStateStorage.py"))
STORAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STORAGE)
BINDINGS = STORAGE.BINDINGS


def image_byte_preview(logical_byte, image_byte, mode="active-overlay"):
    """One detached image-byte branch only; never a saved-grid conversion or palette claim."""
    if any(not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 255 for v in (logical_byte, image_byte)):
        raise ValueError("Expected raw unsigned byte values")
    if mode == "other-slot-mask":
        return 127 if logical_byte != 0 else 0
    if mode != "active-overlay":
        raise ValueError("Unknown qualified image operation")
    masked = image_byte if logical_byte != 0 else 0
    if masked == 0:
        return 0
    return (masked + 110 if masked < 128 else masked - 17) & 255


def restore_buffer_preview(encoded, initial_buffer):
    """Safe prefix overlay on an explicit detached initial buffer; no invented zero tail."""
    if not isinstance(encoded, (bytes, bytearray)) or not isinstance(initial_buffer, (bytes, bytearray)):
        raise ValueError("Encoded input and initial buffer must be bytes or bytearray")
    if len(initial_buffer) != 0x40000:
        raise ValueError("Explicit initial logical buffer must contain 0x40000 bytes")
    decoded, summary = STORAGE.decode_stream(encoded)
    result = bytearray(initial_buffer)
    result[:len(decoded)] = decoded
    return bytes(result), summary


def selection_update_enabled(display_latch):
    """Detached exact-equality gate only, not overall runtime/resource eligibility."""
    if not isinstance(display_latch, int) or isinstance(display_latch, bool) or not 0 <= display_latch <= 255:
        raise ValueError("Expected a raw unsigned display-latch byte")
    return display_latch != 1


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    def function(address):
        end = elf.functions[elf.functions.index(address)+1]
        keep(address, end-address)

    expected = {
        0x897EE4: 0x101EFB20, 0x897F10: 0x101EFB20, 0x8A1900: 0x101EFB20,
        0x24DEDC: 0x88090024, 0x24DEE4: 0x2F800001, 0x24DEE8: 0x419E0238,
        0x24E004: 0x7F89F000, 0x24E008: 0x419E01C0,
        0x24E024: 0x4BDC464D, 0x24E034: 0x93DB0020,
        0x24E050: 0x8BBF0014, 0x24E058: 0x40860144,
        0x24E070: 0x4BFFFC31, 0x24E07C: 0x38A000C8,
        0x24E09C: 0x4BDC4B15, 0x24E118: 0x48000789,
        0x24E1A8: 0x4BDC24B9, 0x24E1C0: 0x4BFFF941,
        0x24DDF8: 0x98090024, 0x24DE34: 0x880B0000,
        0x24DE44: 0x896A0000, 0x24DE5C: 0x380CFF81,
        0x24DE60: 0x388BFF80, 0x24DE74: 0x3960006E,
        0x24DE90: 0x988A0000, 0x24D670: 0x98090024,
        0x24D6CC: 0x99440000, 0x24DB48: 0x98A90024,
        0x25BD74: 0x4BFF5A45, 0x25BD80: 0x4BFF54F9,
        0x25D314: 0x4BFF4C65, 0x25D324: 0x7F9ED000,
        0x25D330: 0x4BFF54E9, 0x25D618: 0x4BFF4331,
        0x25D624: 0x4BFF3C55, 0x25B970: 0x4BFF6609,
        0x25B9B4: 0x38A00000, 0x25B9B8: 0x4BFF5F91,
        0x35C73C: 0x90650008, 0x35C744: 0x93E40010,
        0x35C748: 0x98640014, 0x35C6C8: 0x89690000,
        0x35C6BC: 0x42400018, 0x35C620: 0x2B035FFF,
        0x35C498: 0x810360D0, 0x35C49C: 0x7F054040,
        0x35C4A0: 0x40980088, 0x35C4A8: 0x419D0080,
        0x35E070: 0x38800007, 0x35E088: 0x980300CC,
        0x35E08C: 0x912360D0, 0x35E09C: 0x994560D4,
        0x24E978: 0x88C9000C, 0x24E980: 0x408600F8,
        0x24EA68: 0x9AA5000C, 0x24EA7C: 0x2F3B0007,
        0x897CC0: 0x101E72B8, 0x897CF8: 0x84C0B0,
        0x84C0E8: 0x869238, 0x84C0F0: 0x869240,
        0x869238: 0x247E78, 0x86923C: 0x88FF38,
        0x869240: 0x248798, 0x869244: 0x88FF38,
        0x244510: 0x81227D88, 0x244514: 0x80690000, 0x244518: 0x4E800020,
        0x244E4C: 0x82227D88, 0x244E50: 0x82910000,
        0x244E58: 0x3B340070, 0x244E60: 0x7F35CB78,
        0x244EC0: 0x82427DC0, 0x244F28: 0x7B3E0020, 0x244F44: 0x925E0000,
        0x247F04: 0x3C9C0002, 0x247F08: 0x3864AF14, 0x247F10: 0x48005F99,
        0x24EADC: 0x3C830002, 0x24EAE0: 0x3864AF84,
    }
    for address, word in expected.items():
        if elf.u32(address) != word:
            raise ValueError(f"Grid lifecycle evidence changed at {address:#x}")
        keep(address, 4)
    functions = (0x24DEA8, 0x24DDE8, 0x24D660, 0x24DB00, 0x24DCA0,
                 0x24DAB8, 0x24DA88, 0x24E8A0, 0x24EAC8, 0x25BBF0,
                 0x25B918, 0x25D1D0, 0x35C460, 0x35C5B8, 0x35E070)
    for address in functions:
        function(address)
    # Compact constructor/frame slices preserve register provenance without bundling the entire owner chain.
    for address, size in ((0x244E4C, 0xFC), (0x247E78, 0x9C)):
        keep(address, size)
    thunks = {0x251948: 0x24DB00, 0x251278: 0x24DDE8, 0x251F78: 0x24DA88,
              0x2517B8: 0x24DAB8, 0x252818: 0x24D660,
              0x10660: 0x35C460, 0x12670: 0x35C5B8}
    for thunk, target in thunks.items():
        if BINDINGS.branch_target(elf.u32(thunk+12), thunk+12) != target:
            raise ValueError("Grid synchronization thunk changed")
        keep(thunk, 16)
    report = {
        "confidence": "code-backed",
        "warning": "Exact USA v02.00 static lifecycle, detached byte models and snapshot observations. Display bytes are not saved logical values; readiness is not a checksum, visit or completion verdict. No native/Lua execution or original file modification.",
        "layout": {"base": "0x114d8", "stride": "0x60dc", "count": 21,
                   "copied_header_size": "0xc8", "accumulator_member": "0xc8", "ready_member": "0xcc",
                   "payload_member": "0xcd", "encoded_length_member": "0x60d0",
                   "group_flags_member": "0x60d4", "group_flag_count": 7, "opaque_tail_member": "0x60db",
                   "runtime_definition_member": "0x20", "runtime_logical_buffer_member": "0x24",
                   "runtime_display_latch_member": "0x40024", "runtime_image_pointer_member": "0x40028"},
        "owner_provenance": {"getter_va": "0x244510", "constructor_va": "0x244dd8",
                             "context_vtable_va": "0x84c0b0", "context_offset": "0x70",
                             "frame_method_va": "0x247e78", "frame_grid_offset": "0x1af14",
                             "presnapshot_grid_offset": "0x1af84",
                             "rule": "244510 returns the allocation base through TOC897CC0 -> singleton101E72B8 without adjustment. Constructor244DD8 computes allocation+70 and installs vtable84C0B0 there; its +38 descriptor869238 identifies frame247E78. That frame passes receiver+1AF14 to selector24DEA8. Therefore the first context's grid address is allocation+70+1AF14=allocation+1AF84, exactly the getter-based pre-snapshot24EAC8 grid address.",
                             "limits": "This proves the constructor's first context/subobject relationship, not equality for every alternate context, every runtime instance or pointers retained in a detached save."},
        "selection_lifecycle": {"selector_va": "0x24dea8", "rule": "The selector exits only when runtime display latch40024 equals1, not on every nonzero byte. It compares selected definition POINTER to current runtime20; the same pointer skips flush/reload/header copy and continues position/group processing. A different pointer first encodes the prior logical buffer into the prior definition's saved slot, then stores the new pointer and checks that slot's ready byte.",
                                "header_refresh": "Ready nonzero restores only encoded logical data, then refreshes the image from the selected runtime definition's baked layer; it does NOT recopy the saved C8-byte header. Ready zero initializes logical/image data from the baked layer and copies exactlyC8 header bytes. Saved header runtime pointer/handle bits can therefore remain historical even when current runtime definition metadata changed; no equality or current-handle validity is established.",
                                "groups": "Both selected paths can reach24E8A0. Its flag checks/stores have no ready-byte test: a selected unready block can receive group flags before its logical grid is encoded and readiness published. Previously nonzero flag bytes are retained; zero can become1 under the existing volume/extent checks.",
                                "scope": "Definition identity, not just saved-slot equality, controls switching. All actual resource loading, hero containment and runtime validity requirements still apply. No field edit safety or universal transition cause inferred."},
        "menu_synchronization": {"activation_va": "0x25bbf0", "browse_va": "0x25d1d0", "exit_va": "0x25b918",
                                 "rule": "Activation calls2517B8->24DAB8 to encode the active logical buffer BEFORE251278->24DDE8 modifies the image and sets latch40024=1. Browsing loads the selected ready saved stream into the logical buffer through251F78->24DA88. Selecting the active definition's slot refreshes its baked image then overlays it; another slot uses24D660's binary image instead. The runtime definition pointer20 is not replaced by this browse restore.",
                                 "exit": "25B918 reads active definition20 and, if present, restores THAT definition's saved slot into the logical buffer through251F78 before calling251948->24DB00(-1,0). The refresh clears latch40024 and rebuilds the baked image, even though it does not encode a newly browsed buffer on exit. This provides a concrete buffer-restoration dependency, not proof of every menu exit path.",
                                 "limits": "Map activation, browse and exit are identified by the native method relationships and opposite runtime/menu setup; no recovered localized menu label, current UI state, thread synchronization or gameplay acceptance assumed."},
        "image_only_consumers": {"active_overlay_va": "0x24dde8", "other_slot_mask_va": "0x24d660",
                                 "active_overlay": "For each of512x512 logical bytes, logical0 suppresses image input to0; any nonzero logical byte retains that input. Image input0 yields0, input1..127 yields(input+110) modulo256, input128..255 yieldsinput-17. Only the separate image buffer is written. The colors/alpha meaning and palette remain unknown.",
                                 "other_slot_mask": "24D660 writes image0 for logical0, image127 for ANY nonzero logical byte, and raises display latch40024=1. It does not rewrite logical1/2 to127 or make those stored state classes globally interchangeable.",
                                 "latch": "Both image-only helpers set40024=1.24DB00 assigns its third argument to that byte before resource lookup; refresh can clear the latch even if the baked resource later fails.24DEA8's exact equality1 gate suppresses its selection/cell-clearing/group-recording work while in this display mode.",
                                 "preview_scope": "image_byte_preview evaluates a single detached unsigned-byte branch, not a reconstructed actual image, saved byte replacement or native call."},
        "publication_and_restore": {"encoder_va": "0x35c5b8", "decoder_va": "0x35c460", "initializer_va": "0x35e070",
                                    "encoder_order": "The encoder writes payload incrementally, then stores encoded length60D0, accumulatorC8 and readyCC=1 in that order. It does NOT clear an already-nonzero ready byte at entry. This is ordered metadata publication, not a proven atomic transaction or runtime concurrency lock.",
                                    "decoder_trust": "35C460 uses declared encoded length60D0 and output cap40000. It neither reads/checks accumulatorC8 nor tests readyCC or validates header fields/group flags. Readiness is an outer selector/menu gate. A short stream returns without filling the untouched output tail; no automatic zero initialization or accumulator-based repair occurs in this decoder.",
                                    "safe_preview": "restore_buffer_preview requires an explicit full initial buffer and overlays only safely decoded prefix bytes. It rejects truncated/oversized declared input through the existing bounded decoder and never emulates native out-of-range reads.",
                                    "initializer_footprint": ["0xcc", "0x60d0..0x60d3", "0x60d4..0x60da"],
                                    "initializer_limits": "35E070 clears readyCC, encoded length60D0 and seven flags60D4..60DA only. It does not clear accumulatorC8, copied header, encoded payload or final60DB. A retained accumulator does not validate unready bytes; no zero/padding/default claim is made for untouched storage.",
                                    "source_boundary": "Flush passes source runtime+24; its40000-byte logical end is therefore runtime40024, the separate display latch. The encoder's repeated-byte lookahead is limited by a65535-extra-run counter, not remaining logical source length, and can reach beyond that end before its post-run total-size test. Adjacent runtime bytes can affect an overlong final token; source/runtime latch state is not recoverable from a detached save. Safe inspectors clip declared output without recreating or normalizing that native overread."},
        "opaque_members": {"copied_header_bytes": ["0xd..0xf", "0x1d..0x1f"], "final_byte": "0x60db",
                           "rule": "These remain semantically unresolved. Selected header copies preserve the source bytes; the checked initializer and compression/image/group routines do not establish a named role for the final byte. Whole-save copies can retain it. Absence of a known assignment is not evidence of padding or an unused byte."},
        "recommended_annotations": [
            {"va": "0x24dde8", "kind": "function", "name": "TOD_grid_active_image_overlay_verified", "comment": "Image-only mask/remapping from logical bytes; sets runtime display latch40024=1; no saved logical-grid normalization."},
            {"va": "0x24d660", "kind": "function", "name": "TOD_grid_other_slot_binary_image_verified", "comment": "Maps logical0/nonzero to separate image0/127; raises display latch. Stored logical state classes remain unchanged."},
            {"va": "0x25b918", "kind": "function", "name": "TOD_map_exit_restore_active_grid_verified", "comment": "Reached exit path restores active definition's saved slot after browsing, then refreshes image/clears display latch; no browse-buffer flush."},
            {"va": "0x24da88", "kind": "function", "name": "TOD_grid_restore_selected_stream_to_runtime_verified", "comment": "Forwards explicit slot to decoder with runtime+24 destination; leaves runtime definition20 unchanged."}],
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save size")
        data = path.read_bytes()
        if any(struct.unpack_from(">I", data, index*0x14)[0] != index for index in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        observations = []
        for slot in range(21):
            offset = 0x114D8+slot*0x60DC
            ready = data[offset+0xCC]
            length = struct.unpack_from(">I", data, offset+0x60D0)[0]
            accumulator = struct.unpack_from(">I", data, offset+0xC8)[0]
            row = {"slot": slot, "ready_byte": ready, "encoded_length": length,
                   "saved_accumulator": accumulator, "raw_group_flags": list(data[offset+0x60D4:offset+0x60DB]),
                   "opaque_0d_to_0f": data[offset+13:offset+16].hex().upper(),
                   "opaque_1d_to_1f": data[offset+29:offset+32].hex().upper(), "opaque_60db": data[offset+0x60DB],
                   "decoded": None, "accumulator_matches_research_decode": None}
            if ready == 0:
                row["status"] = "Not marked ready; retained bytes not decoded or normalized"
            else:
                try:
                    if length > 0x5FFF:
                        raise ValueError("Declared encoded length exceeds native encoder cap")
                    _, summary = STORAGE.decode_stream(data[offset+0xCD:offset+0xCD+length])
                    row["decoded"] = summary
                    row["accumulator_matches_research_decode"] = accumulator == summary["encoder_accumulator"]
                    row["status"] = "Full decoded logical span" if summary["complete"] else "Short stream; native decoder would leave a preexisting output tail untouched"
                except ValueError as error:
                    row["status"] = str(error)
            observations.append(row)
        report["save_observation"] = {"sha256": hashlib.sha256(data).hexdigest().upper(), "size": len(data), "blocks": observations,
            "scope": "Accumulator agreement is a research comparison, not a native restore check. No actual display image, owner pointer, active slot, latch state or timing is inferred from these bytes."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2, allow_nan=False))
