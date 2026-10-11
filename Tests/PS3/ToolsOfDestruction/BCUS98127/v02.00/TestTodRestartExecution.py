"""Private restart capture and deferred action selection, without native execution."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodRestartExecution.py"))
ELF = SAVE = None


class RestartExecutionChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact native evidence")
        return TOOL["inspect"](ELF)

    def test_map_reproduction(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(self.native(), mapping["restart_execution"])

    def test_native_guards_and_disjoint_case_table(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)
        self.assertEqual([r["target_va"] for r in report["phase_dispatch"]["cases"]],
                         ["0x3cf47c", "0x3cf5b4", "0x3cf3f0", "0x3cf570", "0x3cf4ec"])
        self.assertIn({"va": "0x3cf3dc", "bytes": "000000A0000001D8000000140000019400000110"}, report["instruction_guards"])
        nested = report["nested_initializer_ownership"]
        self.assertEqual(nested["inner_save_base"], "0x5528")
        self.assertEqual(nested["mission_zero_fills"], [
            {"start": "0x10148", "size": "0x9b0", "end_exclusive": "0x10af8", "call_va": "0x35dbbc"},
            {"start": "0x10af8", "size": "0x9b0", "end_exclusive": "0x114a8", "call_va": "0x35dbd4"}])
        self.assertEqual(nested["log"], {"start": "0x8764", "end_exclusive": "0x10144", "stride": "0x9c", "physical_slots": 200})

    def test_constructor_gate_exact_arguments(self):
        fn = TOOL["constructor_gate_preview"]
        self.assertEqual(fn(1, 65535), "initialize both banks")
        self.assertEqual(fn(0, 65535), "manager-side teardown only")
        for phase, qualifier in ((2, 65535), (1, 0xFFFFFFFF), (0, 0), (0xFFFFFFFF, 65535)):
            self.assertEqual(fn(phase, qualifier), "no operation")

    def test_entry_capture_and_later_live_changes_do_not_recapture(self):
        size = TOOL["SAVE_SIZE"]
        live, private = bytearray(b"A" * size), bytearray(b"B" * size)
        before = bytes(live), bytes(private)
        first = TOOL["phase_one_capture_preview"](live, private, 255)
        self.assertTrue(first["copied"])
        self.assertEqual(first["private_bank"], before[0])
        live[0x10148:0x1014C] = bytes.fromhex("DEADBEEF")
        later = TOOL["phase_one_capture_preview"](live, first["private_bank"], 0)
        self.assertFalse(later["copied"])
        self.assertEqual(later["private_bank"], before[0])
        self.assertEqual(bytes(private), before[1])

    def test_exact_selector_zero_one_and_action_before_publication(self):
        for value, action, va, request in ((0, "selective restart", "0x3ced40", [0, 0, 1]),
                                            (1, "full private-bank restore", "0x3cf1b8", [18, 1, 1])):
            result = TOOL["selection_preview"](4, 0, value)
            self.assertEqual((result["action"], result["action_va"], result["request_arguments"]), (action, va, request))
            self.assertEqual((result["phase_after"], result["entry_latch_after"]), (5, 1))
            self.assertEqual(result["ordering"], ["helper250ED8", action, "publish phase5 and entry latch1"])
        for value in (2, 255, 0xFFFFFFFF, 0x80000000):
            result = TOOL["selection_preview"](4, 0, value)
            self.assertIsNone(result["action"])
            self.assertEqual((result["phase_after"], result["entry_latch_after"]), (4, 0))

    def test_private_retained_log_includes_nonfinite_bits_but_excludes_count(self):
        bank = bytearray(b"\xA5" * TOOL["SAVE_SIZE"])
        struct.pack_into(">I", bank, 0x101C0, 0xFFFFFFFF)
        struct.pack_into(">I", bank, 0x10150, 0xDEADBEEF)
        struct.pack_into(">I", bank, 0x8764, 0x7FC12345)
        before = bytes(bank)
        result = TOOL["retained_region_preview"](bank)
        for name, start, end in TOOL["RETAINED"]:
            self.assertEqual(result[name], before[start:end])
        self.assertEqual(result["segment_log_bytes"][:4], bytes.fromhex("7FC12345"))
        self.assertEqual(len(result["segment_log_bytes"]), 200 * 0x9C)
        self.assertEqual(bytes(bank), before)

    def test_nested_initializer_zeros_every_mission_byte_not_only_count(self):
        bank = bytearray(b"\xA5" * TOOL["SAVE_SIZE"])
        struct.pack_into(">I", bank, 0x8764, 0xDEADBEEF)
        before = bytes(bank)
        result = TOOL["initializer_region_preview"](bank)
        for name, start, end in TOOL["MISSION_CLEARS"]:
            self.assertEqual(result[name], bytes(end - start))
            self.assertEqual(len(result[name]), 0x9B0)
        self.assertEqual(result["decryptor_words"], bytes.fromhex("00000000000000003F800000"))
        self.assertEqual(result["log_count"], bytes(4))
        self.assertEqual(result["segment_log_bytes"][:4], bytes.fromhex("DEADBEEF"))
        self.assertEqual(bytes(bank), before)

    def test_forward_arena_rounds_offset_not_absolute_address(self):
        result = TOOL["arena_bank_preview"](0x100003, 0x200000, 1, 32, False)
        self.assertEqual(result, {"pointer": 0x100013, "front_used": 16 + TOOL["SAVE_SIZE"], "back_used": 32})
        self.assertNotEqual(result["pointer"] & 15, 0)

    def test_reverse_arena_rounds_absolute_address_and_preserves_front(self):
        result = TOOL["arena_bank_preview"](0x100003, 0x200000, 123, 7, True)
        self.assertEqual(result["pointer"] & 15, 0)
        self.assertEqual(result["front_used"], 123)
        self.assertEqual(result["back_used"], 0x300003 - result["pointer"])

    def test_safe_preview_rejects_unsafe_native_domains(self):
        for inputs in ((0, 0x100, 0, 0, False), (0, 0x100, 0, 0, True),
                       (0xFFFFFF00, 0x1000, 0, 0, False), (0, 0x200000, 0x180000, 0x180000, False)):
            with self.assertRaises(ValueError):
                TOOL["arena_bank_preview"](*inputs)
        for inputs in ((5, 0, 0), (4, 1, 0), (4, 0, True), (4, 0, -1)):
            with self.assertRaises(ValueError):
                TOOL["selection_preview"](*inputs)
        with self.assertRaises(ValueError):
            TOOL["retained_region_preview"](bytes(16))

    def test_actual_save_observation_does_not_infer_private_runtime(self):
        if ELF is None or SAVE is None:
            self.skipTest("Pass --elf and --save for actual detached save")
        before = Path(SAVE).read_bytes()
        observation = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(observation["sha256"], hashlib.sha256(before).hexdigest().upper())
        self.assertEqual(observation["restart_word_raw"], "00000003")
        self.assertEqual(observation["log_count_raw"], "00000000")
        self.assertTrue(all(m["active"] == m["completed"] == "00000000" for m in observation["mission_counts_raw"]))
        self.assertEqual(Path(SAVE).read_bytes(), before)

    def test_save_preflight_rejects_wrong_size(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact native evidence")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "short.bin"
            path.write_bytes(b"\0" * 32)
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF, path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remainder = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remainder)
