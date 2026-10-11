"""Saved setting publication, runtime-only mapping and apply-failure boundaries."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSettingsApply.py"))
ELF = SAVE = None


class SettingsApplyChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_embedded_reproduction_and_guards(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["settings_apply"])
        self.assertNotIn("save_observation", report)
        self.assertEqual(len(report["instruction_guards"]), 258)
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)

    def test_seven_named_setters_and_saved_pointer_provenance(self):
        report = self.native()
        self.assertEqual({a["name"] for a in report["named_setters"]},
                         {"set_control_scheme", "set_surround_on", "set_rumble_on", "set_voice_vol", "set_sound_vol", "set_music_vol", "set_camera_speed"})
        self.assertEqual(report["control_scheme"]["saved_offset"], "0x114bc")
        self.assertEqual(report["rumble"]["saved_offset"], "0x114d4")
        self.assertEqual(report["surround"]["saved_offset"], "0x114d5")

    def test_every_small_and_high_scheme_preserves_saved_word(self):
        for value in (*range(256), 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF):
            plan = TOOL["scheme_plan"](value)
            self.assertEqual(plan["saved_word"], f"{value:08X}")
            self.assertEqual(plan["runtime_selector"], value if value in (1, 2) else 0)
        self.assertIn("Count0 skips", self.native()["control_scheme"]["runtime_rule"])

    def test_eleven_runtime_halfword_pairs_each_route_and_two_distinctions(self):
        copies = self.native()["control_scheme"]["copies"]
        self.assertEqual([c["selector"] for c in copies], [0, 1, 2])
        pairs = [{int(p["destination_offset"], 0): int(p["source_offset"], 0) for p in c["pairs"]} for c in copies]
        for table in pairs:
            self.assertEqual(list(table), list(range(0x1C206, 0x1C21C, 2)))
        self.assertEqual([p[0x1C208] for p in pairs], [0x1C002, 0x1C016, 0x1C002])
        self.assertEqual([p[0x1C210] for p in pairs], [0x1C00E, 0x1C010, 0x1C00E])
        self.assertEqual([p[0x1C212] for p in pairs], [0x1C010, 0x40, 0x40])
        self.assertIn("NOT GAME.SAV", self.native()["control_scheme"]["runtime_rule"])

    def test_duplicate_final_loop_tails_do_not_invent_extra_members(self):
        copies = self.native()["control_scheme"]["copies"]
        self.assertEqual([sum(len(p["store_sites"]) for p in c["pairs"]) for c in copies], [11, 12, 12])
        for c in copies[1:]:
            self.assertEqual(len(c["pairs"]), 11)
            self.assertEqual(len(c["pairs"][-1]["store_sites"]), 2)

    def test_rumble_byte_store_and_full64_zero_branch_are_distinct(self):
        for value in range(256):
            plan = TOOL["rumble_plan"](value)
            self.assertEqual(plan["saved_byte"], f"{value:02X}")
            self.assertEqual(plan["runtime_flag_request"], int(value != 0))
        for value in (256, 0x100000000, 0xFFFFFFFFFFFFFFFF):
            plan = TOOL["rumble_plan"](value)
            self.assertEqual(plan["saved_byte"], f"{value & 255:02X}")
            self.assertEqual(plan["runtime_flag_request"], 1)
            self.assertEqual(plan["actuator_clear_port_requests"], [])
        self.assertIn("normalizes boolean conversion to0/1", self.native()["rumble"]["wrapper_limit"])

    def test_rumble_disable_requests_all_eight_ports_without_success_verdict(self):
        self.assertEqual(TOOL["rumble_plan"](0)["actuator_clear_port_requests"], list(range(8)))
        report = self.native()["rumble"]
        self.assertEqual([p["port"] for p in report["port_requests"]], list(range(8)))
        self.assertIn("External return codes are not checked", report["rule"])
        self.assertIn("first clears", report["rule"])

    def test_surround_low32_test_capability_result_and_saved_byte_distinction(self):
        for capability, expected in ((0, 3), (1, 3), (5, 3), (6, 4), (7, 3), (8, 5), (0xFFFFFFFF, 3)):
            for argument in (1, 2, 255, 256, 0x100000001):
                plan = TOOL["surround_plan"](argument, capability)
                self.assertEqual(plan["runtime_mode_request"], expected)
                self.assertTrue(plan["capability_query_selected"])
                self.assertEqual(plan["saved_byte"], f"{argument & 255:02X}")
        for argument in (0, 0x100000000):
            plan = TOOL["surround_plan"](argument)
            self.assertEqual(plan["runtime_mode_request"], 1)
            self.assertFalse(plan["capability_query_selected"])
        with self.assertRaises(ValueError):
            TOOL["surround_plan"](1)

    def test_surround_saved_publication_does_not_prove_hardware_apply(self):
        report = self.native()["surround"]
        self.assertIn("Either failure returns0", report["apply_boundary"])
        self.assertIn("ignores that result", report["apply_boundary"])
        self.assertIn("does not locally undo saved114D5", report["apply_boundary"])
        self.assertIn("not proven speaker-layout names", report["rule"])

    def test_all_bus_indices_and_engine_flags_use_exact_local_gate(self):
        for flags in (0, 1, 0x8000, 0x20000, 0xFFFF, 0x10000, 0x10001, 0xFFFFFFFF):
            for bus in (*range(65), 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF):
                plan = TOOL["bus_store_plan"](flags, bus)
                selected = bool(flags & 0x10000) and bus <= 63
                self.assertEqual(plan["local_runtime_store_selected"], selected)
                self.assertEqual(plan["runtime_record_offset"], hex(bus*0xB0) if selected else None)

    def test_volume_setter_reapplies_three_separate_samples_and_camera_does_not(self):
        report = self.native()["audio_volumes"]
        self.assertIn("effects to bus1, voice to bus6, music to bus12 IN THAT ORDER", report["rule"])
        self.assertIn("not captured as one atomic triple", report["rule"])
        self.assertIn("does not test those return values", report["runtime_boundary"])
        self.assertIn("returns with no calls", report["camera_contrast"])

    def test_invalid_raw_argument_and_runtime_inputs_refused(self):
        for bad in (-1, 1 << 64, True, 0.0, "0", None):
            for name in ("rumble_plan", "surround_plan"):
                with self.assertRaises(ValueError):
                    TOOL[name](bad)
        for bad in (-1, 1 << 32, True, 0.0, "0", None):
            with self.assertRaises(ValueError):
                TOOL["scheme_plan"](bad)
            for args in ((bad, 0), (0, bad)):
                with self.assertRaises(ValueError):
                    TOOL["bus_store_plan"](*args)
            if bad is not None:
                with self.assertRaises(ValueError):
                    TOOL["surround_plan"](1, bad)

    def test_pointer_branch_copy_named_api_call_and_toc_tampering_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0x888624, 0x8A90C8, 0x8AA4D0, 0x8A80D8, 0x271D4,
                        0x26D1C, 0x69617C, 0x5ADF18, 0x5ADF00, 0x271E4, 0x128BC,
                        0x60C5A8, 0x60C5B4, 0x696B4C, 0x696D10, 0x889644):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (4 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)
        for function in (0x271B0, 0x6966B8, 0x696128, 0x5ADEF0, 0x60C568):
            with patch.dict(elf.descriptors, {function: 0}):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_actual_save_snapshot_is_not_runtime_state_and_hashes_unchanged(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observed = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(observed["scheme_bits"], "00000000")
        self.assertEqual((observed["rumble_byte"], observed["surround_byte"]), ("01", "01"))
        self.assertEqual(set(observed["volume_bits"].values()), {"3F666666"})
        self.assertNotIn("runtime_selector", observed)
        self.assertNotIn("attached_ports", observed)
        self.assertIn("does not reveal engine gates", observed["qualification"])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])

    def test_synthetic_nonfinite_unknown_indices_flags_and_opaque_tail_preserved(self):
        self.native()
        raw = bytearray([0xA5]) * 0x906F0
        for i in range(32):
            struct.pack_into(">I", raw, i*20, i)
        struct.pack_into(">I", raw, 0x114BC, 0xFFFFFFFF)
        struct.pack_into(">III", raw, 0x114C4, 0x7F800001, 0xFF800000, 0x80000000)
        raw[0x114D4:0x114D8] = bytes.fromhex("FEFFABCD")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(raw)
            observed = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(observed["scheme_bits"], "FFFFFFFF")
            self.assertEqual(list(observed["volume_bits"].values()), ["7F800001", "FF800000", "80000000"])
            self.assertEqual((observed["rumble_byte"], observed["surround_byte"], observed["opaque_tail"]), ("FE", "FF", "ABCD"))
            self.assertEqual(path.read_bytes(), raw)
            for bad in (raw[:-1], bytes(0x906F0)):
                path.write_bytes(bad)
                with self.assertRaises(ValueError):
                    TOOL["inspect"](ELF, path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
