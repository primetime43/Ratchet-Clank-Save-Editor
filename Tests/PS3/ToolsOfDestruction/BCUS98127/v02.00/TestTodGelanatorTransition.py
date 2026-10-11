"""Exact Gelanator paired debit/refund, separate runtime samples and raw save checks."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGelanatorTransition.py"))
ELF = SAVE = None


def bits(value):
    return struct.unpack(">I", struct.pack(">f", value))[0]


class GelanatorTransitionChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_embedded_reproduction_and_original_guards(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["gelanator_transition"])
        self.assertNotIn("save_observation", mapping["gelanator_transition"])
        self.assertEqual(len(report["instruction_guards"]), 85)
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)

    def test_item_identity_and_borrowed_saved_record_provenance(self):
        report = self.native()
        self.assertIn("literal27", report["record_selection"])
        self.assertIn("WPN_GELANATOR", report["record_selection"])
        self.assertIn("canonical101EFB20", report["record_selection"])
        self.assertIn("saved224", report["record_selection"])
        self.assertIn("unchanged initialized selection", report["record_selection"])

    def test_every_actor_latch_byte_selects_debit_or_refund_without_exact_delta(self):
        for latch in range(256):
            plan = TOOL["transition_plan"](True, latch)
            self.assertEqual(plan["ammo_operation"], "subtract" if latch == 0 else "add")
            self.assertEqual(plan["explicit_actor_latch_after"], 1 if latch == 0 else 0)
            self.assertEqual(plan["request_bits"], "3F800000")
            self.assertIn("no exact delta", plan["qualification"])

    def test_recordless_skips_ammo_and_explicit_actor_latch_store(self):
        for latch in (0, 1, 2, 128, 255):
            plan = TOOL["transition_plan"](False, latch)
            self.assertEqual(plan["ammo_operation"], "none")
            self.assertIsNone(plan["request_bits"])
            self.assertEqual(plan["explicit_actor_latch_after"], latch)

    def test_threshold_equality_and_adjacent_binary32_values(self):
        for latch, threshold in ((0, 31), (1, 30), (2, 30), (255, 30)):
            for sample, passes in ((bits(threshold) - 1, False), (bits(threshold), True), (bits(threshold) + 1, True)):
                plan = TOOL["phase_gate"](latch, sample)
                self.assertEqual(plan["threshold"], threshold)
                self.assertEqual(plan["passes_ordered_branch"], passes)
                self.assertIn("No frames/seconds", plan["qualification"])

    def test_unordered_infinite_zero_and_negative_phase_predicates(self):
        for latch in (0, 255):
            for sample in (0x7FC12345, 0x7F800001, 0xFFC12345, 0xFF800000, 0, 0x80000000, bits(-1)):
                self.assertFalse(TOOL["phase_gate"](latch, sample)["passes_ordered_branch"])
            self.assertTrue(TOOL["phase_gate"](latch, 0x7F800000)["passes_ordered_branch"])
        self.assertIn("null returns-1", self.native()["phase_gate"])

    def test_entry_latch_zero_or_recordless_skips_local_ammo_gate(self):
        for ammo in (0, 0x80000000, bits(1), bits(-1), 0x7FC12345):
            for actor in (0, 1, 255):
                self.assertEqual(TOOL["entry_route"](0, True, ammo, actor)["route"], "continue toward phase gate")
                self.assertEqual(TOOL["entry_route"](255, False, ammo, actor)["route"], "continue toward phase gate")

    def test_entry_gate_signed_zero_unordered_and_every_nonzero_latch(self):
        for entry in (1, 2, 255):
            for ammo in (0, 0x80000000, bits(1), bits(-1), 0x7FC12345, 0x7F800001):
                for actor in (0, 1, 255):
                    result = TOOL["entry_route"](entry, True, ammo, actor)
                    wait = (ammo & 0x7FFFFFFF == 0) == (actor == 0)
                    self.assertEqual(result["route"], "early state3 wait" if wait else "continue toward phase gate")
                    self.assertEqual(result["explicit_entry_latch_after"], 0)

    def test_separate_samples_and_sibling_latch_updates_prevent_snapshot_inference(self):
        self.assertTrue(TOOL["phase_gate"](0, bits(31))["passes_ordered_branch"])
        self.assertEqual(TOOL["transition_plan"](True, 255)["ammo_operation"], "add")
        report = self.native()
        self.assertIn("separate samples", report["runtime_limit"])
        self.assertIn("without directly calling", report["runtime_limit"])
        self.assertIn("not universal zero-ammo rejection", report["entry_boundary"])
        self.assertIn("not guaranteed actual delta1", report["paired_ammo"])
        self.assertIn("state3/entry latch1", report["paired_ammo"])

    def test_invalid_runtime_bytes_words_and_record_presence_are_refused(self):
        for bad in (-1, 256, True, "0", 1.0, None):
            with self.assertRaises(ValueError):
                TOOL["phase_gate"](bad, 0)
            with self.assertRaises(ValueError):
                TOOL["transition_plan"](True, bad)
            for slot in (0, 3):
                args = [0, True, 0, 0]
                args[slot] = bad
                with self.assertRaises(ValueError):
                    TOOL["entry_route"](*args)
        for bad in (-1, 1 << 32, True, "0", 1.0, None):
            with self.assertRaises(ValueError):
                TOOL["phase_gate"](0, bad)
            with self.assertRaises(ValueError):
                TOOL["entry_route"](0, True, bad, 0)
        for bad in (0, 1, None, "yes"):
            with self.assertRaises(ValueError):
                TOOL["transition_plan"](bad, 0)
            with self.assertRaises(ValueError):
                TOOL["entry_route"](0, bad, 0, 0)

    def test_constant_identity_branch_call_pointer_and_toc_tampering_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0x43A500, 0x43A508, 0x8A5340, 0x8A535C, 0x8A5360, 0x853A30,
                        0x897B38, 0x43A9D0, 0x43A888, 0x43A9C8, 0x43A8C8, 0x250C84):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (4 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)
        for function in (0x43A6C0, 0x43A4D0, 0x4661F8, 0x68FF68, 0x23E650):
            with patch.dict(elf.descriptors, {function: 0x88FF38 if function != 0x23E650 else 0x89FF20}):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_actual_save_snapshot_does_not_reconstruct_runtime_state(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observed = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual((observed["id"], observed["ammo_bits"], observed["ownership"], observed["stored_level"]),
                         (27, "00000000", 0, 0))
        self.assertNotIn("actor_latch", observed)
        self.assertNotIn("phase", observed)
        self.assertIn("no phase, runtime latch", observed["qualification"])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])

    def test_synthetic_nan_ammo_unknown_mask_level_and_opaque_tails_remain_raw(self):
        self.native()
        raw = bytearray([0xA5]) * 0x906F0
        for identifier in range(32):
            struct.pack_into(">I", raw, identifier * 20, identifier)
        struct.pack_into(">2I", raw, 0x224, 0x7FC12345, 0xFFFFFFFF)
        raw[0x22D] = 255
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(raw)
            observed = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(observed["ammo_bits"], "7FC12345")
            self.assertEqual(observed["mask_bits"], "FFFFFFFF")
            self.assertEqual(observed["stored_level"], 255)
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
