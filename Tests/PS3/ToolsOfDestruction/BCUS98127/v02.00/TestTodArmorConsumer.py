"""Armor effect ordering and bounded detached native-leaf decision checks."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodArmorConsumer.py"))
ELF = SAVE = None


class ArmorConsumerChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact native evidence")
        return TOOL["inspect"](ELF)

    def test_map_reproduction(self):
        report = self.native()
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["armor_consumer"])

    def test_exact_full_functions_guards_calls_and_definition_root(self):
        report = self.native()
        elf = TOOL["BINDINGS"].Elf(ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)
        self.assertEqual(report["definition_dependency"]["runtime_root_va"], "0x101b9ee8")
        self.assertEqual(report["definition_dependency"]["stride"], 40)
        self.assertEqual([c["target_va"] for c in report["skin_purchase_leaf"]["calls"]], ["0x1f0d60", "0x25db8", "0x11ee0"])
        guards = {int(g["va"], 0): g for g in report["instruction_guards"]}
        for address in (0x2D26D0, 0x43FCE8, 0x1F7DC0, 0x1E2150, 0x2D1C88, 0x27AA0):
            end = elf.functions[elf.functions.index(address) + 1]
            self.assertEqual(len(bytes.fromhex(guards[address]["bytes"])), end - address)

    def test_armor_admission_is_higher_id_and_signed_balance_not_ownership(self):
        preview = TOOL["armor_admission_preview"]
        self.assertTrue(preview(4, 3, 100, 100))
        self.assertFalse(preview(4, 3, 99, 100))
        self.assertFalse(preview(4, 4, 100, 100))
        self.assertFalse(preview(2, 3, 100, 0))
        self.assertFalse(preview(4, 3, 0xFFFFFFFF, 0))
        self.assertTrue(preview(1, 0, 0, 0))
        self.assertFalse(preview(1, 0, 100, 0, False))

    def test_effect_queue_requires_all_three_local_gates_low_byte_predicate(self):
        preview = TOOL["effect_route_preview"]
        self.assertEqual(preview(True, 1, 0), "queued")
        self.assertEqual(preview(True, 255, 0xFFFFFF00), "queued")
        for values in ((False, 1, 0), (True, 0, 0), (True, 1, 1), (True, 1, 0x10001)):
            self.assertEqual(preview(*values), "direct")

    def test_delayed_equip_state_two_strict_greater_not_equal(self):
        preview = TOOL["delayed_equip_preview"]
        one, two = 0x3F800000, 0x40000000
        self.assertFalse(preview(2, one, one)["reaches_equip_block"])
        self.assertFalse(preview(2, one, two)["reaches_equip_block"])
        self.assertTrue(preview(2, two, one)["reaches_equip_block"])
        for state in (0, 1, 3, 4, 0xFFFFFFFF):
            self.assertFalse(preview(state, two, one)["reaches_equip_block"])

    def test_unordered_nan_passes_ble_exit_gate_without_float_normalization(self):
        preview = TOOL["delayed_equip_preview"]
        for nan_bits in (0x7FC00001, 0x7F800001, 0xFFC01234):
            for current, deadline in ((nan_bits, 0), (0, nan_bits), (nan_bits, nan_bits)):
                result = preview(2, current, deadline)
                self.assertEqual(result, {"unordered": True, "reaches_equip_block": True})
                self.assertFalse(preview(1, current, deadline)["reaches_equip_block"])
        self.assertFalse(preview(2, 0x80000000, 0)["reaches_equip_block"])
        self.assertTrue(preview(2, 0x7F800000, 0xFF800000)["reaches_equip_block"])
        self.assertFalse(preview(2, 0x7F800000, 0x7F800000)["reaches_equip_block"])

    def test_skin_leaf_signed_balance_only_is_independent_of_owned_and_available(self):
        preview = TOOL["skin_admission_preview"]
        self.assertTrue(preview(5, 5))
        self.assertFalse(preview(5, 4))
        self.assertFalse(preview(0, 0xFFFFFFFF))
        self.assertTrue(preview(0xFFFFFFFF, 0))
        self.assertTrue(preview(0x80000000, 0x80000000))
        report = self.native()
        self.assertIn("ownership24B08", report["skin_purchase_leaf"]["admission"])
        self.assertIn("repeated", report["skin_purchase_leaf"]["consequence"])

    def test_preview_invalid_shapes_and_numbers_rejected(self):
        for value in (-1, 5, 0xFFFFFFFF, True, 1.0, None):
            for requested, equipped in ((value, 0), (1, value)):
                with self.assertRaises(ValueError):
                    TOOL["armor_admission_preview"](requested, equipped, 0, 0)
        for value in (-1, 0x100000000, True, 1.0, None):
            with self.assertRaises(ValueError):
                TOOL["delayed_equip_preview"](2, value, 0)
            with self.assertRaises(ValueError):
                TOOL["skin_admission_preview"](value, 0)
        for value in (-1, 0x80000000, True, 1.0, None):
            with self.assertRaises(ValueError):
                TOOL["armor_admission_preview"](1, 0, 100, value)
        with self.assertRaises(ValueError):
            TOOL["armor_admission_preview"](1, 0, 100, 0, 1)
        with self.assertRaises(ValueError):
            TOOL["effect_route_preview"](1, 1, 0)
        with self.assertRaises(ValueError):
            TOOL["effect_route_preview"](True, 256, 0)

    def test_raw_snapshot_extremes_and_independent_state_preserved(self):
        self.native()
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 20, i)
        struct.pack_into(">I", data, 0x41C, 0x80000000)
        struct.pack_into(">5I", data, 0x444, 0, 2, 0xFFFFFFFF, 0, 0)
        struct.pack_into(">I", data, 0x458, 0xFFFFFFFF)
        struct.pack_into(">I", data, 0x480, 0xFFFFFFFE)
        struct.pack_into(">I", data, 0x424, 0xFFFFFFFF)
        data[0x5774:0x5779] = bytes((2, 3, 4, 5, 255))
        with tempfile.TemporaryDirectory(prefix="tod-armor-raw-") as directory:
            path = Path(directory) / "snapshot.bin"
            path.write_bytes(data)
            observed = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(observed["bolts_word"], 0x80000000)
            self.assertEqual(observed["armor_ownership_words"], [0, 2, 0xFFFFFFFF, 0, 0])
            self.assertEqual(observed["equipped_armor_word"], 0xFFFFFFFF)
            self.assertEqual(observed["selected_skin_word"], 0xFFFFFFFE)
            self.assertEqual(observed["spent_special_bolts_word"], 0xFFFFFFFF)
            self.assertEqual(observed["armor_unlock_bytes"], [2, 3, 4, 5, 255])
            self.assertNotIn("runtime_queue", observed)
            self.assertEqual(path.read_bytes(), data)

    def test_bad_save_preflight(self):
        self.native()
        with tempfile.TemporaryDirectory(prefix="tod-armor-invalid-") as directory:
            path = Path(directory) / "snapshot.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL["inspect"](ELF, path)

    def test_actual_detached_snapshot_and_elf_unchanged(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save for actual detached snapshot")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observed = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(observed["armor_ownership_words"], [1] * 5)
        self.assertEqual(observed["equipped_armor_word"], 4)
        self.assertEqual(observed["selected_skin_word"], 0)
        self.assertEqual(observed["spent_special_bolts_word"], 32)
        self.assertEqual(observed["skin_ownership_words"], [1, 1, 1, 1, 1, 1, 1, 0, 1])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, rest = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + rest)
