"""Exact weapon record binding and local ammo branch boundaries, without execution."""
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
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWeaponAmmoDebit.py"))
ELF = SAVE = None


def bits(value):
    return struct.unpack(">I", struct.pack(">f", value))[0]


class WeaponAmmoDebitChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def admit(self, request, ammo, global_word=0, present=True, flags=0):
        return TOOL["availability_plan"](global_word, present, flags, request, ammo)["passes_local_predicate"]

    def test_embedded_reproduction_and_guards(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["weapon_ammo_debit"])
        self.assertNotIn("save_observation", report)
        self.assertEqual(len(report["instruction_guards"]), 87)
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)

    def test_borrowed_record_and_canonical_owner_bridge(self):
        report = self.native()
        for evidence in ("canonical101EFB20", "hero+1A68", "12080->466D38", "inventory+4 +20*",
                         "SAME borrowed record", "weapon+2C", "definition at weapon+30", "saved ammo is20*i+8"):
            self.assertIn(evidence, report["record_binding"])
        self.assertIn("No copy", report["record_binding"])
        self.assertIn("not GAME.SAV offsets", report["record_binding"])

    def test_positive_request_equality_and_adjacent_binary32_values(self):
        for request in (bits(0.25), bits(1), bits(100)):
            self.assertFalse(self.admit(request, request-1))
            self.assertTrue(self.admit(request, request))
            self.assertTrue(self.admit(request, request+1))
        self.assertFalse(self.admit(bits(1), bits(0.25)))
        self.assertTrue(self.admit(0, bits(0.25)))

    def test_zero_negative_and_unordered_requests_require_strict_positive_ammo(self):
        for request in (0, 0x80000000, bits(-1), 0xFF800000, 0x7FC12345, 0x7F800001, 0xFFC12345):
            for ammo in (0, 0x80000000, bits(-1), 0xFF800000, 0x7FC12345, 0x7F800001):
                self.assertFalse(self.admit(request, ammo))
            for ammo in (1, bits(0.25), bits(1), 0x7F800000):
                self.assertTrue(self.admit(request, ammo))

    def test_positive_infinite_request_and_unordered_ammo(self):
        self.assertTrue(self.admit(0x7F800000, 0x7F800000))
        self.assertFalse(self.admit(0x7F800000, bits(1)))
        for request in (0, bits(1), 0x7F800000):
            for ammo in (0x7FC12345, 0x7F800001, 0xFFC12345):
                self.assertFalse(self.admit(request, ammo))

    def test_anonymous_global_recordless_and_exact_flag_bypasses(self):
        for global_word in (1, 2, 0x80000000, 0xFFFFFFFF):
            self.assertTrue(self.admit(bits(100), 0x7FC12345, global_word=global_word))
        self.assertTrue(self.admit(bits(100), 0, present=False))
        for flags in (0x10, 0x11, 0xFFFFFFFF):
            self.assertTrue(self.admit(bits(100), 0x7FC12345, flags=flags))
        for flags in (0, 1, 2, 8, 0x20, 0xFFFFFFEF):
            self.assertFalse(self.admit(bits(100), 0, flags=flags))
        self.assertIn("meaning remains unknown", self.native()["availability_rule"])

    def test_negated_debit_request_is_not_resulting_delta(self):
        for sample in (bits(1), bits(-1), bits(0.25), 1, 0x80000001, 0x7F7FFFFF):
            plan = TOOL["debit_request_plan"](True, sample)
            self.assertEqual(plan["operation"], "clamped add")
            self.assertEqual(plan["delta_request_bits"], f"{sample ^ 0x80000000:08X}")
            self.assertIn("no exact saved delta", plan["qualification"])

    def test_signed_zero_negation_and_null_before_nonfinite(self):
        self.assertEqual(TOOL["debit_request_plan"](True, 0)["delta_request_bits"], "80000000")
        self.assertEqual(TOOL["debit_request_plan"](True, 0x80000000)["delta_request_bits"], "00000000")
        for sample in (0, bits(1), 0x7F800000, 0x7FC12345, 0x7F800001):
            plan = TOOL["debit_request_plan"](False, sample)
            self.assertEqual(plan["operation"], "none")
            self.assertIsNone(plan["delta_request_bits"])

    def test_nonfinite_debit_execution_preview_refused(self):
        for sample in (0x7F800000, 0xFF800000, 0x7FC12345, 0x7F800001, 0xFFC12345):
            with self.assertRaises(ValueError):
                TOOL["debit_request_plan"](True, sample)

    def test_check_and_update_remain_separate_with_intervening_callback(self):
        report = self.native()
        self.assertIn("external46C158", report["caller_boundary"])
        self.assertIn("request0 predicate is not an ammo>=1 check", report["caller_boundary"])
        self.assertIn("not an atomic", report["caller_boundary"])
        self.assertIn("not4661F8", report["debit_rule"])
        self.assertIn("no local sign/ownership check", report["debit_rule"].lower())
        self.assertIn("arbitrary native binary64", report["runtime_limit"])

    def test_invalid_words_and_presence_refused(self):
        for bad in (-1, 1 << 32, True, 1.0, "0", None):
            for slot in (0, 2, 3, 4):
                args = [0, True, 0, 0, 0]
                args[slot] = bad
                with self.assertRaises(ValueError):
                    TOOL["availability_plan"](*args)
            with self.assertRaises(ValueError):
                TOOL["debit_request_plan"](True, bad)
        for bad in (0, 1, None, "yes"):
            with self.assertRaises(ValueError):
                TOOL["availability_plan"](0, bad, 0, 0, 0)
            with self.assertRaises(ValueError):
                TOOL["debit_request_plan"](bad, 0)

    def test_binding_branch_constant_call_and_toc_tampering_refused(self):
        self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        original = elf.u32
        for address in (0x1F5DFC, 0x466D38, 0x463B80, 0x463B84, 0x46AD9C,
                        0x46A458, 0x46A494, 0x46A444, 0x8A5FCC, 0x8A5F40,
                        0x469060, 0x4690E0, 0x46ADA0, 0x1208C):
            with patch.object(elf, "u32", side_effect=lambda va, target=address: original(va) ^ (4 if va == target else 0)):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)
        for function in (0x1F5DB8, 0x466D38, 0x463AD0, 0x46A420, 0x46AD80):
            with patch.dict(elf.descriptors, {function: 0}):
                with patch.dict(TOOL["BINDINGS"], {"Elf": lambda _: elf}):
                    with self.assertRaises(ValueError):
                        TOOL["inspect"](ELF)

    def test_actual_save_snapshot_and_hashes_unchanged(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        report = TOOL["inspect"](ELF, SAVE)
        records = report["save_observation"]["records"]
        self.assertEqual(len(records), 32)
        self.assertEqual(records[27]["ammo_offset"], "0x224")
        self.assertEqual(records[27]["ammo_bits"], "00000000")
        self.assertEqual(records[1]["ammo_bits"], bits(100).to_bytes(4, "big").hex().upper())
        self.assertNotIn("eligibility", records[1])
        self.assertIn("no runtime eligibility", report["save_observation"]["qualification"])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])

    def test_synthetic_raw_values_and_malformed_layout(self):
        self.native()
        raw = bytearray([0xA5]) * 0x906F0
        for i in range(32):
            struct.pack_into(">I", raw, i*20, i)
        struct.pack_into(">I", raw, 28, 0x7F800001)
        raw[36:40] = bytes.fromhex("FEFFABCD")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(raw)
            row = TOOL["inspect"](ELF, path)["save_observation"]["records"][1]
            self.assertEqual((row["ammo_bits"], row["ownership"], row["stored_level"], row["opaque_tail"]),
                             ("7F800001", 254, 255, "ABCD"))
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
