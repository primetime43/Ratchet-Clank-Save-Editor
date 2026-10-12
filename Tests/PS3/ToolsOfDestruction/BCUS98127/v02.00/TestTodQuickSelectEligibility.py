"""Initial native definition flags and conservative detached slot-edit plans."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodQuickSelectEligibility.py"))
ELF = SAVE = None


class QuickSelectChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_report_reproduces_public_map_and_76_native_guards(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["quick_select_eligibility"])
        self.assertEqual(len(report["instruction_guards"]), 76)
        self.assertNotIn("save_observation", report)
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(raw, elf.read(int(guard["va"], 0), len(raw)))

    def test_all32_ids_and_five_rejected_initial_flag_values(self):
        catalog = self.native()["catalog"]
        self.assertEqual([row["id"] for row in catalog], list(range(32)))
        self.assertEqual([row["id"] for row in catalog if not row["quick_select_initially_allowed"]], [0, 26, 28, 29, 31])
        self.assertEqual(catalog[0]["initial_flags"], "0x00001014")
        self.assertEqual(catalog[1]["initial_flags"], "0x00000004")
        self.assertEqual(catalog[25]["initial_flags"], "0x00002815")
        self.assertEqual(catalog[31]["initial_flags"], "0x00001011")
        for row in catalog:
            self.assertEqual(row["quick_select_initially_allowed"], int(row["initial_flags"], 0) & 0x1040 == 0)

    def test_literal_stack_sources_redecode_independently(self):
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for row in self.native()["catalog"]:
            store = int(row["flags_argument_store_va"], 0)
            literal = int(row["flags_literal_va"], 0)
            word = elf.u32(store)
            self.assertEqual(word >> 26, 62)
            self.assertEqual(word & 65535, 0x70)
            decoded, address = TOOL["literal_argument"](elf, int(row["constructor_va"], 0), store, (word >> 21) & 31)
            self.assertEqual((decoded, address), (int(row["initial_flags"], 0), literal))
            self.assertEqual((elf.u32(literal) >> 16) & 31, 0)

    def test_registry_and_save_fields_remain_separate(self):
        report = self.native()
        self.assertIn("callee+114", report["definition_linkage"])
        self.assertIn("definition+18", report["definition_linkage"])
        self.assertIn("103697B8+20+4*ID", report["definition_linkage"])
        self.assertIn("BEFORE", report["assignment"])
        self.assertIn("not saved eligibility bits", report["warning"])

    def test_clear_and_assign_modify_only_requested_first24_slots(self):
        slots = [-1]*32
        slots[0], slots[31] = 1, -123
        plan = TOOL["edit_plan"](slots, {0: -1, 3: 1}, {1}, {1})
        self.assertEqual(plan["changed_slots"], [0, 3])
        self.assertEqual(plan["slots"][3], 1)
        self.assertEqual(plan["slots"][24:], slots[24:])
        self.assertEqual(slots[0], 1)

    def test_duplicate_refusal_checks_last8_reserved_slots(self):
        slots = [-1]*32
        slots[31] = 1
        with self.assertRaises(ValueError):
            TOOL["edit_plan"](slots, {0: 1}, {1}, {1})
        with self.assertRaises(ValueError):
            TOOL["edit_plan"]([-1]*32, {0: 1, 1: 1}, {1}, {1})

    def test_swap_is_batch_order_independent(self):
        slots = [1, 2]+[-1]*30
        a = TOOL["edit_plan"](slots, {0: 2, 1: 1}, {1, 2}, {1, 2})
        b = TOOL["edit_plan"](slots, {1: 1, 0: 2}, {1, 2}, {1, 2})
        self.assertEqual(a, b)
        self.assertEqual(a["slots"][:2], [2, 1])

    def test_unknown_values_and_existing_duplicates_preserved_on_noop(self):
        slots = [0x7FFFFFFF, -0x80000000, 1, 1]+[-1]*28
        result = TOOL["edit_plan"](slots, {0: 0x7FFFFFFF, 1: -0x80000000, 2: 1}, {1}, {1})
        self.assertEqual(result["slots"], slots)
        self.assertEqual(result["changed_slots"], [])

    def test_unowned_filtered_or_reserved_assignments_refused(self):
        for edits, eligible, owned in (({24: -1}, [], []), ({-1: -1}, [], []),
                                       ({True: 1}, [1], [1]), ({0: True}, [1], [1]),
                                       ({0: 1}, [], [1]), ({0: 1}, [1], []),
                                       ({0: 32}, [1], [1]), ({0: -2}, [1], [1])):
            with self.assertRaises(ValueError):
                TOOL["edit_plan"]([-1]*32, edits, eligible, owned)

    def test_bank_and_catalog_domain_validation(self):
        for bank in ([], [-1]*31, [-1]*33, [True]+[-1]*31, [1 << 31]+[-1]*31):
            with self.assertRaises(ValueError):
                TOOL["edit_plan"](bank, {}, [], [])
        for ids in ([True], [-1], [32], [1.0]):
            with self.assertRaises(ValueError):
                TOOL["edit_plan"]([-1]*32, {}, ids, [])

    def test_pointer_frame_call_and_flags_store_tampering_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0x8A5E84, 0x466798, 0x4667FC, 0x466804, 0x467B0C, 0x467B18,
                        0x26ECC, 0x26EEC, 0x1121C, 0x13B9C, 0x4632F0):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (4 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_actual_save_observation_is_private_and_sources_unchanged(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(path.read_bytes()).digest() for path in (ELF, SAVE)]
        observed = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(len(observed["slots"]), 32)
        self.assertNotIn(0, observed["owned_reference_choices"])
        self.assertNotIn(31, observed["owned_reference_choices"])
        self.assertEqual(before, [hashlib.sha256(path.read_bytes()).digest() for path in (ELF, SAVE)])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"invalid.bin"
            path.write_bytes(bytes(0x906F0))
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF, path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__]+remaining)
