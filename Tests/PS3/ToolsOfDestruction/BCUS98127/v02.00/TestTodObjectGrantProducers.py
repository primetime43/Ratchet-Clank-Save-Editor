"""Fixed grants and flag-before-counter plans, without native callbacks or edits."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodObjectGrantProducers.py"))
ELF = SAVE = None


class ObjectGrantChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_native_reproduction_guards_and_no_private_observation(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["object_grant_producers"])
        self.assertEqual(len(report["instruction_guards"]), 88)
        self.assertNotIn("save_observation", report)
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)

    def test_three_fixed_object_ids_and_four_dispatch_links(self):
        report = self.native()
        self.assertEqual([(r["id"], r["enum"]) for r in report["fixed_grants"]],
                         [(5, "OBJ_CHARGE_BOOTS"), (16, "OBJ_SOULS"), (15, "OBJ_STATUES")])
        self.assertEqual(len(report["dispatch_links"]), 4)
        for row in report["fixed_grants"]:
            i = row["id"]
            self.assertEqual(row["current_offset"], hex(0x304+4*i))
            self.assertEqual(row["peak_offset"], hex(0x360+4*i))
            self.assertEqual(row["additions_offset"], hex(0x3BC+4*i))

    def test_grant_current_additions_and_unsigned_peak_projection(self):
        for current, peak, additions, expected in ((0, 0, 0, (1, 1, 1)),
                                                  (5, 10, 20, (6, 10, 21)),
                                                  (5, 5, 20, (6, 6, 21))):
            plan = TOOL["grant_one_preview"](current, peak, additions)
            self.assertEqual(tuple(int(plan[k], 16) for k in ("current_bits", "peak_bits", "positive_additions_bits")), expected)
            self.assertEqual(plan["peak_store_selected"], expected[0] > peak)

    def test_current_and_additions_wrap_independently(self):
        plan = TOOL["grant_one_preview"](0xFFFFFFFF, 10, 0xFFFFFFFF)
        self.assertEqual(plan["current_bits"], "00000000")
        self.assertEqual(plan["positive_additions_bits"], "00000000")
        self.assertEqual(plan["peak_bits"], "0000000A")
        self.assertFalse(plan["nonzero_current_after"])
        self.assertFalse(plan["peak_store_selected"])

    def test_unsigned_peak_not_signed_high_water_and_equality_no_store(self):
        plan = TOOL["grant_one_preview"](0x7FFFFFFF, 0, 0)
        self.assertEqual(plan["peak_bits"], "80000000")
        self.assertTrue(plan["nonzero_current_after"])
        self.assertFalse(TOOL["grant_one_preview"](0, 1, 0)["peak_store_selected"])
        self.assertEqual(TOOL["grant_one_preview"](0, 0xFFFFFFFF, 0)["peak_bits"], "FFFFFFFF")

    def test_all_global_flag_positions_use_be64_word_and_bit_order(self):
        words = [0, 0, 0, 0, 0]
        for flag in range(320):
            plan = TOOL["flag_grant_plan"](5, flag, words, 0, 0, 0, True)
            actual = [int(v, 16) for v in plan["flag_words_after"]]
            expected = words.copy()
            expected[flag//64] = 1 << (flag%64)
            self.assertEqual(actual, expected)
            self.assertEqual(plan["saved_store_order"], ["global flag OR", "current+1", "positive additions+1", "unsigned peak update"])
        self.assertEqual(words, [0]*5)

    def test_already_set_flag_does_not_reject_repeated_counter_grants(self):
        words = [1, 0, 0, 0, 0]
        first = TOOL["flag_grant_plan"](5, 0, words, 1, 1, 1, True)
        self.assertEqual(first["flag_words_after"], [f"{v:016X}" for v in words])
        self.assertEqual(first["counter_projection"]["current_bits"], "00000002")
        second = TOOL["grant_one_preview"](2, 2, 2)
        self.assertEqual(second["current_bits"], "00000003")
        self.assertIn("does not reject an already-set flag", self.native()["flag_then_object"]["repeat_limit"])

    def test_rejected_receiver_skips_saved_suffix_and_preserves_unknown_flag_bits(self):
        words = [0x0123456789ABCDEF, 0xFFFFFFFFFFFFFFFF, 0x8000000000000000, 1, 42]
        plan = TOOL["flag_grant_plan"](16, 319, words, 9, 99, 0xFFFFFFFF, False)
        self.assertEqual(plan["flag_words_after"], [f"{v:016X}" for v in words])
        self.assertEqual(plan["saved_store_order"], [])
        self.assertIsNone(plan["counter_projection"])
        self.assertIsNone(plan["selected_object_id"])

    def test_souls_saved_grant_precedes_invalid_linked_handle_return(self):
        rule = next(r["rule"] for r in self.native()["fixed_grants"] if r["id"] == 16)
        self.assertIn("BEFORE inspecting actor+9C", rule)
        self.assertIn("AFTER the saved counter operation", rule)
        self.assertIn("No verified handler outcomes", rule)

    def test_runtime_scratch_and_ship_parts_clear_do_not_become_saved_removal(self):
        report = self.native()
        statues = next(r["rule"] for r in report["fixed_grants"] if r["id"] == 15)
        self.assertIn("NOT saved current340", statues)
        self.assertIn("clears runtime actor+B8 before receiver admission", report["flag_then_object"]["rule"])
        self.assertIn("not saved object removal", report["flag_then_object"]["runtime_limit"])

    def test_invalid_words_ids_bank_shape_and_admission_refused(self):
        for bad in (-1, 1 << 32, True, "0", 0.0, None):
            for slot in range(3):
                args = [0, 0, 0]
                args[slot] = bad
                with self.assertRaises(ValueError):
                    TOOL["grant_one_preview"](*args)
        for object_id, flag in ((-1, 0), (23, 0), (True, 0), (0, -1), (0, 320), (0, True)):
            with self.assertRaises(ValueError):
                TOOL["flag_grant_plan"](object_id, flag, [0]*5, 0, 0, 0, True)
        for bank in ([], [0]*4, [0]*6, [0, 0, 0, 0, -1], [0, 0, 0, 0, 1 << 64], [False]*5):
            with self.assertRaises(ValueError):
                TOOL["flag_grant_plan"](0, 0, bank, 0, 0, 0, True)
        for admitted in (0, 1, None, "yes"):
            with self.assertRaises(ValueError):
                TOOL["flag_grant_plan"](0, 0, [0]*5, 0, 0, 0, admitted)

    def test_literal_call_pointer_order_and_toc_tampering_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for va in (0x304730, 0x30761C, 0x3080B4, 0x302A54, 0x302AD4, 0x302AE0,
                   0x307624, 0x307678, 0x23D8A0, 0x23D8B8, 0x23D8CC, 0x89FFF4,
                   0x8A0278, 0x84E4EC, 0x252F84):
            with patch.object(elf, "u32", side_effect=lambda address, target=va: original(address) ^ (4 if address == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)
        for function in (0x302A10, 0x3046E8, 0x3075B8, 0x308070, 0x23D870):
            with patch.dict(elf.descriptors, {function: 0}):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_actual_save_three_banks_not_invocation_or_unique_pickup_history(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observation = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual([r["id"] for r in observation["fixed_objects"]], [5, 15, 16])
        self.assertEqual(len(observation["global_flag_words"]), 5)
        self.assertNotIn("invocation_count", observation)
        self.assertNotIn("linked_handle", observation)
        self.assertIn("do not reconstruct", observation["qualification"])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])

    def test_synthetic_high_counters_unknown_flags_and_neighbor_bytes_preserved(self):
        self.native()
        raw = bytearray([0xA5])*0x906F0
        for i in range(32):
            struct.pack_into(">I", raw, i*20, i)
        for base in (0x304, 0x360, 0x3BC):
            struct.pack_into(">I", raw, base+16*4, 0xFFFFFFFF)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"fixture.bin"
            path.write_bytes(raw)
            observation = TOOL["inspect"](ELF, path)["save_observation"]
            row = next(r for r in observation["fixed_objects"] if r["id"] == 16)
            self.assertEqual((row["current_bits"], row["peak_bits"], row["additions_bits"]), ("FFFFFFFF",)*3)
            self.assertEqual(observation["global_flag_words"], ["A5A5A5A5A5A5A5A5"]*5)
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
    unittest.main(argv=[__file__]+remaining)
