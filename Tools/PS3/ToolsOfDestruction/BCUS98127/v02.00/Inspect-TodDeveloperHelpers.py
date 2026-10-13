"""Read-only exact-build developer helpers and disabled Lua debug registration."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

BASE = Path(__file__).resolve().parent
BINDINGS = runpy.run_path(str(BASE / "Inspect-TodWeaponBindings.py"))
RUNTIME_PROBE_CAPTURE = {
    "date": "2026-10-12", "emulator": "RPCS3 0.0.43-20284-2ba2f75b",
    "elf_sha256": "0B29763574A42760E8432DA1E2920F1176EB0C1EE862A79798DF5A7E5E10552C",
    "marker": "TOD_DEV_PROBE\ttable\tfunction", "marker_count": 2,
    "log_elapsed_times": ["0:19:37.188433", "0:19:38.569219"],
    "user_confirmed_movement": True, "fatal_or_access_violation_lines": 0,
    "scope": "Recorded isolated gameplay run, not repeated by this inspector. Confirms Lua execution and debug.debug availability at the factory hook; not console input, later persistence or an on-screen menu."
}
RUNTIME_MEMORY_CAPTURE = {
    "date": "2026-10-12", "emulator": "RPCS3 0.0.43-20284",
    "elf_sha256": "CBEED9FB9A9F3BFA2535F892B8CAFE0FFE5A890F5896CB9706219AF6897962E0",
    "automatic_controller_and_save_selection": True,
    "transport": "Localhost PINE; verified isolated process owner and harness guards",
    "mailbox_va": "0xc10000", "input_call_patch_va": "0x810760",
    "command": 'print("TOD_MEMORY_COMMAND_OK")',
    "command_marker_time": "0:03:50.098601", "console_enter_count": 2,
    "command_marker_count": 1, "console_exit_count": 2,
    "fatal_or_access_violation_lines": 0, "native_channel0_read_warnings": 0,
    "restored_controller_and_save_imports": True,
    "runner_lifecycle_verified": True, "runner_restored_ipc_settings": True,
    "runner_stopped_owned_emulator": True,
    "visible_installed_repeat": {
        "date": "2026-10-12", "renderer": "Vulkan", "headless": False,
        "executable": "Installed RPCS3; isolated config, caches and saves via RPCS3_CONFIG_DIR",
        "executable_sha256": "4638A268DF9B0BFE19171BABD5F508F2D3ABD93F5434D81C9729FF6926E41A27",
        "command_marker_time": "0:03:55.951778", "console_enter_count": 1,
        "command_marker_count": 1, "console_exit_count": 1,
        "fatal_or_access_violation_lines": 0, "native_channel0_read_warnings": 0,
        "ipc_restored_and_owned_emulator_stopped": True,
        "original_elf_hash_unchanged": True, "visual_gameplay_confirmation": False
    },
    "manual_gameplay_repeat": {
        "date": "2026-10-12", "renderer": "Vulkan",
        "command_marker_time": "0:04:04.936791", "command_marker_count": 1,
        "console_enter_count": 2, "console_exit_count": 2, "mailbox_command_state": 3,
        "user_confirmed_movement": True, "synthetic_controller_or_save_selector_used": False,
        "fatal_or_access_violation_lines": 0, "native_channel0_read_warnings": 0,
        "emulator_left_running_for_manual_testing": True,
        "scope": "User loaded the test save and confirmed movement after the prequeued command ran at initialization; not a command invoked from active gameplay."
    },
    "rule": "Queued command, cont, then EOF; no native stdin call. Empty input terminates instead of spinning.",
    "scope": "Recorded fully unattended test at the game Lua factory hook. One-time harness ELF plus memory-driven controls; not a stock-ELF memory-only unlock, persistent console or on-screen developer menu."
}
GAMEPLAY_CAPTURE = {
    "date": "2026-10-12", "emulator": "RPCS3 0.0.43-20284", "renderer": "Vulkan",
    "elf_sha256": "DC48E373003D4416A3FA7282C6B6366273F483D520ED8FEA181CF8A677917955",
    "command_marker_times": ["0:04:57.214776", "0:06:56.779634"], "command_marker_count": 2,
    "reported_types": {"debug": "table", "debug.debug": "function", "hero_give_all_ammo": "function", "ally_debug": "function"},
    "request_state_after_each": 3, "lua_status_after_each": 0,
    "stack_height_before_each": 3, "stack_height_after_each": 3,
    "command_caller_return_va": "0x293ddc", "caller_function_va": "0x293c70",
    "requests_armed_after_user_confirmed_gameplay": True, "repeat_without_reload": True,
    "user_confirmed_normal_movement_after_first_request": True,
    "fatal_or_access_violation_lines": 0, "native_channel0_read_warnings": 0,
    "controller_or_save_bindings_changed": False, "original_elf_hash_unchanged": True,
    "emulator_left_running_for_manual_testing": True,
    "scope": "Two explicit fixed availability prints executed at a live game-script protected-call return. No native grants, ally diagnostics or debug.debug invocation; not an on-screen menu or general console frontend."
}
FUNCTION_GUARDS = [
  {"va": "0x6696c8", "size": "0x120", "sha256": "AAF239CD2D5C5A6EFBA3F326CF9C279B2845ED5D9E15485FF279C8B358DD6273"},
  {"va": "0x668680", "size": "0x18", "sha256": "B7B8A673A0BF53597683CF1A407A7C1397E41BF5C7968C9EB88F546AC3F335CD"},
  {"va": "0x668698", "size": "0x68", "sha256": "1BEB67A5E5E4FEEACB194A26904ADD8D276E25F3E2538C0A8385E1E0082371F7"},
  {"va": "0x66b930", "size": "0x28", "sha256": "6669FB85803B138EC877FC7E83117AB981A9520ACF7132091B3197F0EC651807"},
  {"va": "0x668d58", "size": "0xa0", "sha256": "AF012FEB9F3A1D2DCD9DAB9DC1E3F4730349BA8100404CE58CAF545633721285"},
  {
    "va": "0x666e00",
    "size": "0xb8",
    "sha256": "C6FA611298AE96EA024C09D39F378FA44FBEC5DA997B575E7207FA5867591E5B"
  },
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
    for code in (0x6696C8, 0x668680, 0x668698, 0x66B930, 0x668D58):
        if elf.descriptors[code] != 0x8AFE5C:
            raise ValueError("Lua ABI helper TOC differs")
    if (elf.u32(0x8A9E44) != 0x87DD28 or elf.u32(0x87DD28) != 0x66B930 or
            elf.u32(0x87DD2C) != 0x8AFE5C):
        raise ValueError("Lua fixed-buffer reader descriptor differs")
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
        (0x8106C8, "TOD_lua_debug_interactive_loop", "function", "Registered debug.debug callback: prints lua_debug>, reads up to250 bytes through814E00, exits on input end or cont newline, executes66C520, clears stack. Raw RPCS3 stdin test spun on channel0. Separate bounded memory reader at call810760 executed one queued command and exited in an unattended test; not an on-screen menu."),
        (0x72EB24, "TOD_game_lua_library_mask_excludes_debug", "comment", "Secondary context72E9B0 supplies li r5,1F before743AC8. Experimental3F adds bit20 only here; it does not cover the separate factory666E00 or open the blocking console."),
        (0x666E00, "TOD_lua_context_factory_four_libraries", "function", "Creates Lua state via67EB10 at context+4; on success opens66E3A8/677818/6849E0/67F2F8, pops four library entries via668698(L,-5), then calls context vtable+1C. No debug opener810650. Probe hook666E7C precedes virtual registration; bounded startup console execution and subsequent playable gameplay were confirmed. A gameplay console and on-screen menu remain unconfirmed."),
        (0x6696C8, "TOD_lua_protected_call_entry", "function", "Arguments L/nargs/nresults/errfunc. First instruction cmpwi cr7,r6,0; delegates protected execution to671F10 and returns status. Game TOC thunk252BA8 tail-jumps here after switching to8AFE5C. Experimental adapter delegates entry+4 and filters mapped game L/nesting. Two fixed gameplay probes completed with status0 at caller return293DDC; no menu or native grants tested."),
        (0x668680, "TOD_lua_gettop_eight_byte_values", "function", "Returns (L.top at+8 minus L.base at+C)/8. Stack elements are8 bytes in this exact build. Setter668698 uses matching stride. Both live fixed gameplay probes recorded stack height3 before and after restoration.")
    ):
        annotations.append({"va": f"0x{va:08X}", "name": name, "kind": kind, "confidence": "confirmed",
                            "bytes": elf.read(va, 4).hex().upper(), "comment": comment,
                            "evidence": "Exact ELF function hashes and descriptor/table guards in developer_helpers; targeted read-only Ghidra assembly/decompilation."})
    return {
        "scope": "BCUS98127 supplied disc revision02.00, APP_VER01.00; static native checks with a separately recorded gameplay probe",
        "research_status": "Runtime patch builders, memory clients and isolated emulator artifacts retired and removed. Captures below describe past tests, not a currently running emulator. Original ELF evidence and annotations retained.",
        "function_guards": FUNCTION_GUARDS,
        "recorded_runtime_probe": RUNTIME_PROBE_CAPTURE,
        "recorded_memory_console": RUNTIME_MEMORY_CAPTURE,
        "gameplay_mailbox_candidate": {
            "protected_call_va": "0x6696c8", "displaced_entry_word": "2F860000", "delegate_va": "0x6696cc",
            "game_context_owner_slot_va": "0x898eb8", "owner_lua_state_offset": "0x4",
            "lua_top_offset": "0x8", "lua_base_offset": "0xc", "lua_value_stride": 8,
            "native_nesting_counter_offset": "0x2e", "protected_state_restorer_va": "0x671f10",
            "gettop_va": "0x668680", "settop_va": "0x668698", "load_va": "0x668d58",
            "string_reader": {"slot_va": "0x8a9e44", "descriptor_va": "0x87dd28", "function_va": "0x66b930", "toc": "0x8afe5c", "userdata": "Two words: buffer pointer and byte length; reader clears length after its first chunk."},
            "adapter_va": "0xc20800", "request_va": "0xc10500", "fixed_script_va": "0xc20c00",
            "generated_elf_sha256": "DC48E373003D4416A3FA7282C6B6366273F483D520ED8FEA181CF8A677917955",
            "request_states": {"0": "Idle", "1": "One fixed availability print pending", "2": "Busy; recursive claims blocked", "3": "Attempt finished; inspect Lua status and balanced stack", "5": "Stack balance check failed"},
            "eligibility": "Original protected call returned success; current L matches owner898EB8+4; native nesting counter is zero. No extra Lua API calls when no request is pending.",
            "execution": "Load the fixed availability script and protected-call it with no results; record API status, restore original stack height and preserve original return/registers. Does not invoke _ALERT, debug.debug, native grants or fabricated handles.",
            "portable_adapter_checks": 8, "runtime_validation_pending": False,
            "recorded_runtime": GAMEPLAY_CAPTURE,
            "live_original_harness_observation": "Mapped game L was readable during user-confirmed gameplay; top/base matched (zero API stack elements) and the native nesting count was zero. No live code patches were made.",
            "scope": "Exact-build experimental test ELF. A repeatable gameplay boundary and two fixed availability prints are recorded, not a recovered on-screen menu, arbitrary command frontend or tested native grants. Annotations refer only to original ELF functions."
        },
        "debug_library": {"open_va": "0x810650", "methods": methods, "registration_va": "0x8415c0",
                          "constructor_va": "0x743ac8", "reinitializer_va": "0x743c5c", "required_flag": "0x20",
                          "observed_caller_va": "0x72e9b0", "mask_instruction_va": "0x72eb24", "original_mask": "0x1f",
                          "context_scope": "Secondary context; not the separate game-connected factory at666E00.",
                          "experimental_mask": "0x3f", "warning": "Adds debug registration at this initial call only. Later sandboxing, globals removal and reinitialization may still remove it. Does not inject Lua or connect console input."},
        "game_lua_factory": {"function_va": "0x666e00", "state_create_va": "0x67eb10", "state_context_offset": "0x4",
                             "library_open_vas": ["0x66e3a8", "0x677818", "0x6849e0", "0x67f2f8"],
                             "stack_pop_va": "0x666e74", "stack_settop_va": "0x668698", "stack_settop_argument": -5,
                             "registrar_vtable_offset": "0x1c", "probe_hook_va": "0x666e7c", "probe_hook_bytes": "813F0000",
                             "debug_open_present": False,
                             "warning": "Separate Lua state creation path, not enabled by the72EB24 mask change. Factory debug registration and a bounded memory-fed console command are recorded; later persistence and an on-screen menu are not established."},
        "console": {"function_va": "0x8106c8", "registered_name": "debug.debug", "prompt": "lua_debug> ",
                    "input_limit": 250, "exit_token": "cont\n", "execute_va": "0x66c520",
                    "rule": "Command-reading loop with compile/protected-call helper and subsequent stack clear; no local save flag or controller activation found.",
                    "warning": "Native streams10143DC8/10143E98 reached RPCS3 channel0 and spun on empty input; GUI All channels feeds3..15. Do not use the raw-stdin patch. The separate harness replaces only the console input call with a bounded memory reader."},
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
