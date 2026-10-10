"""Read-only exact-build saved first-person option camera-coupling evidence."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location("bindings", Path(__file__).with_name("Inspect-TodWeaponBindings.py"))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    # These are saved-state pointer slots, not offsets in arbitrary runtime objects.
    expected_words = {
        0x89679C: 0x101EFB20, 0x896858: 0x101EFB20,
        0x20F3FC: 0x83A26864, 0x20F408: 0x3D7D0001,
        0x20F420: 0x812B14C0, 0x20F424: 0x2F890000,
        0x20F428: 0x409E000C, 0x20F430: 0x987F0024,
        0x2108E0: 0x80826920, 0x2108F0: 0x3D240001,
        0x210904: 0x816914C0, 0x210910: 0x2F8B0000,
        0x210918: 0x409E000C, 0x210920: 0x98DF003F,
        0x20F814: 0x8B9F0024, 0x20F818: 0x2C9C0000,
        0x20F81C: 0x418600EC, 0x20F90C: 0x38800010,
        0x20F910: 0x4BE58AE1, 0x20FC18: 0x4BE67CB1,
        0x2110D8: 0x8BB0003F, 0x2110DC: 0x2C9D0000,
        0x2110E0: 0x4086FC20, 0x2110F0: 0x38800010,
        0x2110F8: 0x4BE572F9, 0x211110: 0x4BE667B9,
        0x7799C: 0xC15F00F4, 0x779B0: 0xD03F00F4,
        0x778EC: 0x38FF00C0, 0x779BC: 0x4BF9B595,
        0x683F0: 0x38000010, 0x683F4: 0x386300C0,
        0x68404: 0x38630200, 0x68408: 0x80A90064,
        0x68410: 0x419E000C, 0x68414: 0x4200FFEC,
        0x68418: 0x39200000,
    }
    for address, expected in expected_words.items():
        if elf.u32(address) != expected:
            raise ValueError(f"First-person camera evidence changed at {address:#x}")
        keep(address, 4)
    if elf.descriptors[0x20F3F0] + 0x6864 != 0x89679C or \
            elf.descriptors[0x2108D8] + 0x6920 != 0x896858:
        raise ValueError("First-person consumer TOC changed")
    for address in (0x20F3F0, 0x2108D8, 0x20F598, 0x210B80, 0x20FD90,
                    0x778C8, 0x683F0, 0x639400, 0x639548):
        end = elf.functions[elf.functions.index(address) + 1]
        keep(address, end - address)
    for address, target in ((0x20F910, 0x683F0), (0x2110F8, 0x683F0),
                            (0x20FC18, 0x778C8), (0x211110, 0x778C8)):
        word = elf.u32(address)
        if word & 1 == 0 or BINDINGS.branch_target(word, address) != target:
            raise ValueError("Camera lookup/orientation call changed")
    paths = []
    for table, entry, update, flag in ((0x84AF18, 0x20F3F0, 0x20F598, 0x24),
                                       (0x84AF48, 0x2108D8, 0x210B80, 0x3F)):
        for displacement, target in ((12, entry), (16, update)):
            descriptor = elf.u32(table + displacement)
            if struct.unpack(">II", elf.read(descriptor, 8)) != (target, 0x88FF38):
                raise ValueError("Native method-table relationship changed")
            keep(descriptor, 8)
        keep(table, 0x24)
        paths.append({"method_table_va": hex(table), "entry_va": hex(entry),
                      "update_va": hex(update), "runtime_flag_offset": hex(flag)})
    report = {
        "confidence": "code-backed-camera-coupling",
        "warning": "Exact USA v02.00 static native relationships and read-only save observations, not runtime acceptance, safe edit permissions, an original option name, hold/toggle polarity or applicability to another build.",
        "field": {"offset": "0x114c0", "type": "u32 BE", "semantic_name": None,
                  "entry_rule": "Both entry methods read saved114C0 once and set their runtime byte to1 only when the entire word iszero. Any nonzero word takes the same branch; values are not normalized in the save.",
                  "scope": "This word affects first-person camera context. The checked update methods read the entry-derived runtime byte, not the saved word again. This is a local latch relationship, not a guarantee that no other lifecycle changes the byte."},
        "state_paths": paths,
        "mode_selection": {"zero_word_request": "0x0f", "nonzero_word_request": "0x10",
                           "request_thunk_va": "0x13d50", "request_native_va": "0x639548",
                           "qualification": "Entry methods do not request a new mode if the current camera is already0F/10; one path also has an unrelated runtime-state exclusion. Request639548 can reject a lower/equal-priority request. These are requests, not proof of the currently active camera."},
        "update_coupling": {
            "zero_word": "Entry-derived runtime flag1 bypasses the mode10 orientation-adjustment paths at20F814/20F81C and2110D8/2110E0.",
            "nonzero_word": "Entry-derived flag0 permits lookup of a mode10 runtime camera and, if additional update conditions pass, forwards a computed runtime vector into778C8. Nonzero permits the path; it does not guarantee execution every frame.",
            "first_call_va": "0x20fc18", "second_call_va": "0x211110",
            "camera_lookup_va": "0x683f0", "orientation_adjust_va": "0x778c8",
            "lookup_rule": "683F0 scans16 runtime records starting at container+C0, stride200, compares record+64 with the requested numeric mode, and returns the first match orzero.",
            "orientation_rule": "778C8 uses runtime vector/basis products and an angular conversion, adds the result to runtime float+F4, stores it back, and updates a runtime basis beginning+C0. It is not a direct save-field write or a simple vector copy.",
            "unresolved": "No guarded input activation/release sequence proves whether saved114C0 means hold/toggle. Modes0F/10 and scalar+F4 remain numeric/descriptive, not asserted original camera-class names or a named world yaw axis."},
        "unknown_tail": {"offset": "0x114d6", "size": 2,
                         "qualification": "114D6/114D7 remain opaque; first-person word evidence does not give those bytes a role or establish padding."},
        "instruction_guards": [{"va": hex(a), "bytes": raw.hex().upper()} for a, raw in sorted(guards.items())]}
    if save_path is not None:
        if Path(save_path).stat().st_size != 0x906F0:
            raise ValueError("Not the verified plaintext save size")
        data = Path(save_path).read_bytes()
        if any(struct.unpack_from(">I", data, i * 0x14)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext inventory layout")
        value = struct.unpack_from(">I", data, 0x114C0)[0]
        report["save_observation"] = {
            "plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "word": value, "raw_hex": data[0x114C0:0x114C4].hex().upper(),
            "entry_runtime_flag": int(value == 0),
            "qualified_mode_request": "0x0f" if value == 0 else "0x10",
            "orientation_path_permitted": value != 0,
            "unknown_tail_raw": data[0x114D6:0x114D8].hex().upper(),
            "warning": "These are static branch interpretations of raw saved bits, not a current camera state or a guarantee of update execution."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path, help="Plaintext working copy; read only")
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2, allow_nan=False))
