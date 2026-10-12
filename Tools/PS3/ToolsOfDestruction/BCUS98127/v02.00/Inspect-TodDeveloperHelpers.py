"""Read-only exact-build developer helpers and disabled Lua debug registration."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BASE = Path(__file__).resolve().parent
BINDINGS = runpy.run_path(str(BASE / "Inspect-TodWeaponBindings.py"))
FUNCTION_GUARDS = [
  {
    "va": "0x810650",
    "size": "0x78",
    "sha256": "5B58BCEA1150C7E1E4114BD588F9538F732D24BF05217094ACF257D46DB568CD"
  },
  {
    "va": "0x8106c8",
    "size": "0xd8",
    "sha256": "B7D74E9EDF021B7EA6703ADAA48EF7320CE699D5CE4EA38B05C3CF8F490F6B19"
  },
  {
    "va": "0x743ac8",
    "size": "0x194",
    "sha256": "BEA2BE645018A22D68BBD54616FF101FFABA9301493E2D089380BA7CD83C1E59"
  },
  {
    "va": "0x743c5c",
    "size": "0x194",
    "sha256": "CDCA78296D6D8BEBCD6D17D04A0CB07F51CC2A2A2DE6EC51B3181B2FFDEB3A8B"
  },
  {
    "va": "0x72e9b0",
    "size": "0x374",
    "sha256": "3D724DB34A84CA2BFE93D0B713C91CEB5B4DF6328A12B18B6BD9D62BBF9D40A2"
  },
  {
    "va": "0x2bafe8",
    "size": "0xe0",
    "sha256": "1F48BDA1A461E309BDB21004A1FF9597C85189BE4C3B5CB7B284F4D9F5391263"
  },
  {
    "va": "0x28ab00",
    "size": "0x180",
    "sha256": "7EFF1D28A4A203435B27753E2BDF782CEFAA2B75C7AC79FAFDB07F581DAD9584"
  },
  {
    "va": "0x2a82c0",
    "size": "0xe0",
    "sha256": "01DA743E54BCDFEFCA397829FE8D110B0A5834D7AF08168401141F7EA70B8A0D"
  },
  {
    "va": "0x28f378",
    "size": "0x100",
    "sha256": "56F0C2577066ECA74901DBDB53999EC22F376FCE60DB0583BD9D7169D9373338"
  },
  {
    "va": "0x66c520",
    "size": "0xa0",
    "sha256": "C9FBB02565F60B7AF4954DC83FB34D90C15165C60F13B544049D5895C5EB2CB9"
  }
]


def inspect(elf_path):
    elf = BINDINGS["Elf"](elf_path)
    for guard in elf.mapping["bonuses"]["instruction_guards"]:
        raw = bytes.fromhex(guard["bytes"])
        if elf.read(int(guard["va"], 0), len(raw)) != raw:
            raise ValueError("Shared native bonus/blueprint evidence changed")
    for guard in FUNCTION_GUARDS:
        if hashlib.sha256(elf.read(int(guard["va"], 0), int(guard["size"], 0))).hexdigest().upper() != guard["sha256"]:
            raise ValueError("Developer helper body changed at " + guard["va"])
    for address, expected in ((0x72EB24, 0x38A0001F), (0x72EB28, 0x48014FA1),
                              (0x743B90, 0x57A006B4), (0x743B98, 0x419E0010), (0x743BA0, 0x480CCAB1)):
        if elf.u32(address) != expected:
            raise ValueError("Debug initialization gate changed")
    if elf.read(0x8415C0, 80).hex().upper() != "100487A800886F88100487B800886F98100487C000886F80100487C800886F60100487D800886F70100487E000886F68100487F000886F58100486B800886F481004880000886F900000000000000000":
        raise ValueError("Debug registration table changed")
    methods = []
    for index in range(9):
        name, descriptor = struct.unpack(">II", elf.read(0x8415C0 + 8 * index, 8))
        methods.append({"name": elf.string(name), "descriptor_va": hex(descriptor), "function_va": hex(elf.u32(descriptor))})
    for slot, text in ((0x8ACD98, "debug"), (0x8ACDA8, "lua_debug> "), (0x8ACDB4, "cont\n")):
        if elf.string(elf.u32(slot)) != text:
            raise ValueError("Debug library strings changed")
    helpers = []
    for slot, name, target in ((0x89DED8, "hero_give_all_ammo", 0x2BAFE8), (0x89E658, "ally_debug", 0x2A82C0)):
        string, descriptor = struct.unpack(">II", elf.read(slot, 8))
        if elf.string(string) != name or elf.u32(descriptor) != target:
            raise ValueError("Native helper registration changed")
        helpers.append({"name": name, "registration_va": hex(slot), "wrapper_va": hex(target)})
    annotations = []
    for va, name, kind, comment in (
        (0x810650, "TOD_lua_debug_library_open", "function", "Registers debug table at8415C0. Initialization743AC8/743C5C requires flag20; observed caller72E9B0 supplies1F, excluding it."),
        (0x8106C8, "TOD_lua_debug_interactive_loop", "function", "Registered debug.debug callback: writes lua_debug> prompt, reads up to250 bytes through814E00, exits on input end or cont newline, invokes66C520 to compile/call Lua then clears stack. Host streams and live usability untested."),
        (0x72EB24, "TOD_game_lua_library_mask_excludes_debug", "comment", "li r5,1F before743AC8. Experimental3F adds bit20 for debug-library registration without automatically opening the blocking console.")
    ):
        annotations.append({"va": f"0x{va:08X}", "name": name, "kind": kind, "confidence": "confirmed",
                            "bytes": elf.read(va, 4).hex().upper(), "comment": comment,
                            "evidence": "Exact ELF function hashes and descriptor/table guards in developer_helpers; targeted read-only Ghidra assembly/decompilation."})
    return {
        "scope": "BCUS98127 supplied v02.00; static native evidence, not live emulator validation",
        "function_guards": FUNCTION_GUARDS,
        "debug_library": {"open_va": "0x810650", "methods": methods, "registration_va": "0x8415c0",
                          "constructor_va": "0x743ac8", "reinitializer_va": "0x743c5c", "required_flag": "0x20",
                          "observed_caller_va": "0x72e9b0", "mask_instruction_va": "0x72eb24", "original_mask": "0x1f",
                          "experimental_mask": "0x3f", "warning": "Adds debug registration at this initial call only. Later sandboxing, globals removal and reinitialization may still remove it. Does not inject Lua or connect console input."},
        "console": {"function_va": "0x8106c8", "registered_name": "debug.debug", "prompt": "lua_debug> ",
                    "input_limit": 250, "exit_token": "cont\n", "execute_va": "0x66c520",
                    "rule": "Command-reading loop with compile/protected-call helper and subsequent stack clear; no local save flag or controller activation found.",
                    "warning": "Input/output are native runtime streams at10143DC8/10143E98. They are not confirmed usable from RPCS3; do not auto-invoke the console, which may block."},
        "runtime_helpers": helpers,
        "ammo_helper": {"leaf_va": "0x28ab00", "rule": "Valid hero-component path loops32 inventory records, requiring ownership and definition flags&13==0, then invokes465D88. Not equivalent to the editor's seven gadget-ammo fields. Handle/class diagnostics may continue, so never call with a fabricated handle."},
        "ally_debug": {"leaf_va": "0x28f378", "rule": "Resolved moby/component path checks runtime class461 and emits formatted diagnostic lines for a runtime count. Not a confirmed ally AI cheat or invulnerability toggle."},
        "save_helpers": {"native_guard_section": "bonuses", "native_guard_count": len(elf.mapping["bonuses"]["instruction_guards"]), "blueprints": "ORs0007DEE4 at86F4, preserving other bits; no planet-to-bit names guessed.",
                         "bonuses": "Sets score8708 to840 and replaces zero state bytes86F8..8705 with1. Preserves nonzero states and earned bits8710; not all skill awards or proof every effect is active."},
        "recommended_annotations": annotations
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf), indent=2))
