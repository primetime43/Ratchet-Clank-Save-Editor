"""Read-only arena queue API boundary and UI runtime resource ownership.

This pass does not recover ARENA_CHALLENGE_DATA installation or execute native
code/Lua. Runtime pointers are explicitly not serialized save offsets.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
RANGES = [
    (0x2CA1D8, 0x120, "65F7F2F894666F8BDD9D2E2991195E239DBBCF6CFF6903014627761C57EE10AC"),
    (0x282AF8, 0xD0, "287525153C30C3A3541C655B2044DF9CFFF0803C59734574C2CCA618FE3FB07E"),
    (0x62D2E8, 0x448, "65B94864F4D4A2A1845813624CD1C2631E7B2A7CF80DD9ABA44A7FF434C802F1"),
    (0x632710, 0x10, "2DFEE9197B7C6C0932EECF773D8DBA9396C3B9D23807881462133C7878155C05"),
    (0x632720, 0x18, "E7D447523D42E49370D81300148AD8F872930A8EEBAA13C44E2E9299174112BE"),
    (0x6329D0, 0x28, "FF301EEE6CEA3D5859E92809E9755D0016338FE6ACE988EAEAB4A31E85EC1469"),
    (0x636EF0, 0x20, "EA335F23B3FFFF179A5152B18C3D8E09CFB9CF781DA5294DC552AD0CE52125AC"),
    (0x252288, 0x10, "F303E07E839B2D9BEFF32964CA04B64A1AD7AABBC41F7C8233F0AD91CAEBEDD9"),
    (0x24FAB8, 0x10, "AE57205FCA03C791ECE2C3077891507153F860BEF8AFF2CFC35A9CF6013F498D"),
    (0x252BE8, 0x10, "07656F7F3DC9707EAE11D6EE375A3C7C5F381588538FD0C3D76CF1AA88DF4321"),
    (0x6A5C68, 0xF0, "F1174C13CD275231F81F3A91F2AC17087833ECA3EBF6F1D8D8EA28E44668E42B"),
    (0x6A9E78, 0x78, "F86468C70184DA558FF59CEB3A9A57841AE4CB4EABFEB4EE7B44123B5C17D75F"),
    (0x6A5FC8, 0x58, "71B9DB43F5D3C9F6F476CD2CF73A62F636C60A746C6E4013B13BFC7E6D8129B4"),
]


def observe_save_bytes(raw):
    """Observe existing arena counters only; never infer runtime resource fields."""
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != 0x906F0 or \
            any(struct.unpack_from(">I", raw, i * 20)[0] != i for i in range(32)):
        raise ValueError("Expected exact-length plaintext with inventory IDs0..31")
    return {"size": len(raw), "plaintext_sha256": hashlib.sha256(raw).hexdigest().upper(),
            "counters": [{"native_id": i, "offset": hex(0x56D8 + i * 4),
                          "raw_hex": raw[0x56D8 + i * 4:0x56DC + i * 4].hex().upper(),
                          "signed_value": struct.unpack_from(">i", raw, 0x56D8 + i * 4)[0]}
                         for i in range(23)],
            "warning": "Existing counter bank only. No saved queue string, resource owner, current Lua table or menu rows are reconstructed."}


def inspect(elf_path, save_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}
    def keep(address, size):
        guards[address] = elf.read(address, size)
    for address, size, digest in RANGES:
        if hashlib.sha256(elf.read(address, size)).hexdigest().upper() != digest:
            raise ValueError("Arena queue API boundary fingerprint mismatch")
        keep(address, size)
    for slot, expected in [(0x89D8AC, 0x1001F4C0), (0x89D8B0, 0x86C530),
                           (0x86C530, 0x2CA1D8), (0x86C534, 0x89FF20),
                           (0x8991E0, 0x1001A7D8),
                           (0x8A9578, 0x107225CC), (0x8A957C, 0x10731E64),
                           (0x8A9898, 0x107225D8), (0x8AA5FC, 0x1002C6D8),
                           (0x8AA60C, 0x1002C090)]:
        if elf.u32(slot) != expected:
            raise ValueError("Arena API/resource pointer changed")
        keep(slot, 4)
    for slot, text in [(0x89D8AC, "queue_arena_challenge_screen"),
                       (0x8991E0, "select_arena_challenge"), (0x8AA5FC, "string"),
                       (0x8AA60C, "[no object]"), (0x899660, "moby_handle")]:
        pointer = elf.u32(slot)
        if elf.string(pointer) != text:
            raise ValueError("Arena API identifier changed")
        keep(pointer, len(text) + 1)
        keep(slot, 4)
    for thunk, target in [(0x252288, 0x6A5C68), (0x24FAB8, 0x6A9E78), (0x252BE8, 0x6A5FC8)]:
        word = elf.u32(thunk + 12)
        if BINDINGS["branch_target"](word, thunk + 12) != target or word & 1:
            raise ValueError("Arena API thunk changed")
    report = {
        "confidence": "native-confirmed", "binary_sha256": hashlib.sha256(elf.raw).hexdigest().upper(),
        "queue_binding": {
            "registration_slot_va": "0x89d8ac", "name": "queue_arena_challenge_screen",
            "descriptor_va": "0x86c530", "wrapper_va": "0x2ca1d8", "native_va": "0x282af8",
            "diagnostic_identifier": "select_arena_challenge", "diagnostic_pointer_slot_va": "0x8991e0",
            "distinction": "The registered native queue API and its diagnostic identifier are different. A diagnostic select_arena_challenge string does not establish a named native binding for the table-taking shipped Lua call.",
            "arguments": [
                {"position": 1, "meaning": "Required moby_handle checked via250338; userdata lookup2518C8 must return nonzero before dereferencing the handle word."},
                {"position": 2, "meaning": "Required string-compatible argument checked via252288→6A5C68, using diagnostic type string;24FAB8→6A9E78 returns its pointer through66B078."}],
            "arity": "252BE8→6A5FC8 with index3 rejects a present third argument; ordinary path requires two arguments. String-compatible means the native Lua predicate's accepted domain, not an asserted strict Python string type.",
            "native_argument_boundary": "Wrapper places handle inr3 and extracted string pointer inr4 before282AF8. The guarded complete282AF8 body does not preserve/read incomingr4 before overwriting it; the operation request uses actor thread token, operation5,0,0. No string/table payload is carried by this observed request path.",
            "validation_scope": "Failure paths call the engine Lua diagnostic helper; no assertion that errors are recoverable or that invalid handles safely continue."},
        "loader_resource_ownership": {
            "loader_va": "0x62d2e8", "resource_setter_va": "0x632710",
            "resource_pointer_slot_va": "0x8a9578", "runtime_resource_owner_va": "0x107225cc",
            "source": "Operation5's UI loader receives owner+108+2C as its incomingr6;62D320 retains it inr24,62D55C movesr24 tor3,62D560 calls632710.",
            "resource_store": "632710 stores its supplied word to runtime owner+0 via8A9578. This is a resource word, not a recovered Lua-state pointer or saved challenge ID.",
            "companion_setter_va": "0x632720",
            "companion_store": "632720 independently stores a supplied word to runtime owner+4 and clears owner+8. The later loader call632710 does not perform those companion writes.",
            "context_setup": "6329D0→636EF0 stores two supplied runtime words at separate owner107225D8+14/+18; no ARENA_CHALLENGE_DATA assignment is present in these setter bodies.",
            "warning": "All owner members and pointer slots are runtime virtual addresses, not GAME.SAV offsets. This extends the loader resource boundary but does not install or alias the script challenge list."},
        "unresolved": [
            "Shipped select_arena_challenge(actor, challenge_list) is not connected to a recovered table-installing wrapper; queue_arena_challenge_screen is the observed registered native endpoint.",
            "The Lua ARENA_CHALLENGE_DATA table's current identity/list installation remains unresolved; selector input, native ID and display row cannot be equated.",
            "No new serialized save field, live queue state or in-game edit acceptance is claimed."],
        "recommended_annotations": [
            {"va": "0x2ca1d8", "name": "TOD_lua_queue_arena_challenge_screen", "kind": "function",
             "comment": "Named native queue_arena_challenge_screen registration89D8AC. Requires moby_handle/string-compatible arg2, rejects ordinary third arg. Extracted string is passed to282AF8 but not consumed by that native body. Diagnostic select_arena_challenge string is not a proven table-taking API binding."},
            {"va": "0x632710", "name": "TOD_ui_store_runtime_resource_word", "kind": "function",
             "comment": "Stores supplied word to runtime107225CC+0 through TOC slot8A9578. Arena loader62D2E8 passes incomingr6 here; not a saved field or recovered ARENA_CHALLENGE_DATA installer."},
            {"va": "0x632720", "name": "TOD_ui_store_companion_resource_clear_aux_word", "kind": "function",
             "comment": "Stores supplied runtime word to107225CC+4 and clears107225CC+8. Separate from632710 owner+0 store; no serialized save offset or confirmed Lua table binding."},
            {"va": "0x636ef0", "name": "TOD_ui_store_runtime_context_pair", "kind": "function",
             "comment": "Stores supplied words at runtime owner107225D8+14/+18 through8A9898; called by6329D0. No challenge list alias or GAME.SAV member inferred."}],
        "instruction_guards": [{"va": hex(address), "bytes": raw.hex().upper()} for address, raw in sorted(guards.items())]}
    if save_path is not None:
        if Path(save_path).stat().st_size != 0x906F0:
            raise ValueError("Expected exact-length Tools of Destruction plaintext")
        report["save_observation"] = observe_save_bytes(Path(save_path).read_bytes())
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--save", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save), indent=2))
