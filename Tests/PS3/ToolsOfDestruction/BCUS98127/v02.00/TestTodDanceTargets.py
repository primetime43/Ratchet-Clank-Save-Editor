"""Exact Dance actor index/config associations and immutable saved observations."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import unittest
from unittest.mock import patch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodDanceTargets.py"))
ELF = SAVE = None


def fixture(bank=0, earned=False):
    raw = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", raw, i * 20, i)
    struct.pack_into(">Q", raw, 0x8720, bank)
    struct.pack_into(">Q", raw, 0x8710, (1 << 48) if earned else 0)
    return raw


class DanceTargetChecks(unittest.TestCase):
    def native(self, save=None):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF, save)

    def test_all28_unique_indices_and_names(self):
        rows = self.native()["catalog"]
        self.assertEqual([r["index"] for r in rows], list(range(28)))
        self.assertEqual(len({r["config_name"] for r in rows}), 28)
        self.assertEqual(rows[0]["config_name"], "EnemyAntaraCentipede")
        self.assertEqual(rows[-1]["config_name"], "EnemyTachyonWalker")

    def test_all30_literal_publications_target_runtime28(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        self.assertEqual(sum(len(r["publications"]) for r in report["catalog"]), 30)
        for row in report["catalog"]:
            for publication in row["publications"]:
                literal, store = (elf.u32(int(publication[k], 0)) for k in ("literal_va", "store_va"))
                self.assertEqual(literal & 65535, row["index"])
                self.assertEqual(literal >> 16 & 31, 0)
                self.assertEqual(literal >> 21 & 31, store >> 21 & 31)
                self.assertEqual((store >> 26, store & 65535), (36, 0x28))

    def test_named_property_pointer_associations(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for row in report["catalog"]:
            pointer = int(row["config_pointer_va"], 0)
            self.assertEqual(pointer, 0x101B9EE8 + int(row["config_root_offset"], 0))
            self.assertEqual(elf.u32(int(row["config_pointer_slot_va"], 0)), pointer)
            self.assertEqual(elf.string(elf.u32(int(row["config_registration_va"], 0))), row["config_name"])

    def test_shingle19_uses_shared_vtable_not_direct_initializer_load(self):
        report = self.native()
        row = report["catalog"][19]
        self.assertEqual((row["index_method_va"], row["binding_method_va"]), ("0x1aed30", "0x1ae8c0"))
        self.assertIn("Same actor vtable", row["association"])
        self.assertIn("no direct Shingle", report["index19_boundary"])
        self.assertIn("guaranteed relative execution order", report["index19_boundary"])

    def test_owner_chain_and_variant_limits(self):
        report = self.native()
        self.assertIn("payload+40", report["owner_chain"])
        self.assertIn("FFFFFFFF", report["owner_chain"])
        self.assertIn("not28 uniquely identified physical enemies", report["variant_boundary"])
        self.assertIn("shielded/advanced variants", report["variant_boundary"])
        self.assertIn("not localized titles", report["warning"])

    def test283_guards_and32_annotations_match_elf(self):
        report = self.native()
        self.assertEqual(len(report["instruction_guards"]), 283)
        self.assertEqual(len(report["recommended_annotations"]), 32)
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)

    def test_root_owner_store_literal_config_and_vtable_tamper_refused(self):
        self.native()
        cls = TOOL["BINDINGS"]["Elf"]
        original = cls.u32
        for target in (0x88FAFC, 0xBFED4, 0xC2578, 0x848CF8, 0x848D38,
                       0x17D510, 0x17D518, 0x893258, 0x1354B8):
            def changed(instance, address):
                return original(instance, address) ^ (4 if address == target else 0)
            with patch.object(cls, "u32", changed), self.assertRaises(ValueError):
                TOOL["inspect"](ELF)

    def test_each_single_saved_bit_has_only_one_reference_target(self):
        for index in range(28):
            observed = TOOL["observation"](fixture(1 << index))
            self.assertEqual([r["index"] for r in observed["targets"] if r["recorded_bit"]], [index])
            self.assertFalse(observed["exact_completion_pattern"])

    def test_high_bits_retained_without_inventing_targets_or_completion(self):
        for high in range(28, 64):
            bank = TOOL["MASK"] | (1 << high)
            raw = fixture(bank)
            before = bytes(raw)
            observed = TOOL["observation"](raw)
            self.assertEqual(len(observed["targets"]), 28)
            self.assertTrue(all(r["recorded_bit"] for r in observed["targets"]))
            self.assertFalse(observed["exact_completion_pattern"])
            self.assertEqual(observed["high_bits_hex"], f"{1 << high:016X}")
            self.assertEqual(raw, before)

    def test_award_and_progress_are_independent(self):
        for bank in (0, TOOL["MASK"], 0xFFFFFFFFFFFFFFFF):
            for earned in (False, True):
                result = TOOL["observation"](fixture(bank, earned))
                self.assertEqual(result["skill48_earned"], earned)
                self.assertEqual(result["exact_completion_pattern"], bank == TOOL["MASK"])
                self.assertIn("Clear does not prove never danced", result["scope"])

    def test_opaque_neighbors_unchanged(self):
        raw = fixture(1 << 19, True)
        raw[0x8718:0x8720] = bytes.fromhex("0123456789ABCDEF")
        raw[0x8728:0x8730] = bytes.fromhex("FEDCBA9876543210")
        before = bytes(raw)
        self.assertTrue(TOOL["observation"](raw)["targets"][19]["recorded_bit"])
        self.assertEqual(raw, before)

    def test_malformed_layout_refused(self):
        for data in (None, "0", bytes(0x906F0), fixture()[:-1], fixture() + b"\0"):
            with self.assertRaises(ValueError):
                TOOL["observation"](data)

    def test_actual_save_snapshot_and_hash_preserved(self):
        if SAVE is None:
            self.skipTest("Pass --save")
        before = hashlib.sha256(SAVE.read_bytes()).hexdigest()
        observed = self.native(SAVE)["save_observation"]
        self.assertEqual(observed["bank_hex"], "0000000000000000")
        self.assertTrue(observed["skill48_earned"])
        self.assertFalse(any(r["recorded_bit"] for r in observed["targets"]))
        self.assertEqual(before, hashlib.sha256(SAVE.read_bytes()).hexdigest())

    def test_embedded_report_reproduces_without_private_data(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
        self.assertEqual(mapping["dance_targets"], report)
        self.assertNotIn("save_observation", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
