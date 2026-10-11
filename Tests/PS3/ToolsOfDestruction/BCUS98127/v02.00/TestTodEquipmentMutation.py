"""Detached equipment suffix checks, exact native ordering and unchanged inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodEquipmentMutation.py"))
ELF = SAVE = None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i * 20, i)
    return data


class EquipmentMutationChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact native evidence")
        return TOOL["inspect"](ELF)

    def test_map_reproduction(self):
        report = self.native()
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["equipment_mutation"])

    def test_exact_guards_and_initializer_before_prefix_copy(self):
        report = self.native()
        elf = TOOL["BINDINGS"].Elf(ELF)
        guards = {int(g["va"], 0): bytes.fromhex(g["bytes"]) for g in report["instruction_guards"]}
        for address, raw in guards.items():
            self.assertEqual(elf.read(address, len(raw)), raw)
        for address in (0x27A30, 0x26F60, 0x2FAE8, 0x2FA30, 0x3CED40, 0x35E110, 0x35DC80):
            self.assertEqual(len(guards[address]), elf.functions[elf.functions.index(address) + 1] - address)
        self.assertIn("later252428 call3CEDD0", report["selective_restart_suffix"]["initializer_order"])
        self.assertEqual(report["selective_restart_suffix"]["wing_enum_anchor"]["id"], 3)
        self.assertEqual(report["pack_publication"]["store_order"], ["0x43c", "0x438", "notification_type4"])

    def test_native64_argument_and_low32_selector_mismatch(self):
        preview = TOOL["native_pack_preview"]
        self.assertEqual(preview(0)["selector_word"], 0)
        for argument in (1, 3, 4, 0xFFFFFFFF, 0x100000000, 0xFFFFFFFFFFFFFFFF):
            result = preview(argument)
            self.assertEqual(result["pack_word"], argument & 0xFFFFFFFF)
            self.assertEqual(result["selector_word"], 1)
            self.assertIsNone(result["equip_success"])
        self.assertEqual(preview(0x100000000)["pack_word"], 0)

    def test_lua_already_converted_payload_is_zero_extended_not_native64(self):
        preview = TOOL["lua_integer_payload_preview"]
        for integer in (-(1 << 31), -1, 0, 1, 3, (1 << 31) - 1):
            result = preview(integer)
            self.assertEqual(result["pack_word"], integer & 0xFFFFFFFF)
            self.assertEqual(result["selector_word"], int(integer != 0))
        self.assertEqual(preview(-1)["pack_word"], 0xFFFFFFFF)
        self.assertEqual(preview(0)["selector_word"], 0)

    def test_boot_leaf_ignores_argument_preserves_other_words_and_always_notifies(self):
        preview = TOOL["boot_publication_preview"]
        for argument in (0, 3, 0xFFFFFFFFFFFFFFFF):
            result = preview([0xDEADBEEF, 4, 0x80000000], argument)
            self.assertEqual(result["words"], [0xDEADBEEF, 4, 0])
            self.assertEqual(result["notification_type"], 4)
            self.assertIsNone(result["equip_success"])
        self.assertEqual(preview([1, 3, 0], 2)["notification_type"], 4)

    def test_selective_filter_exact_ids_in_place_not_compaction(self):
        quick = list(range(32))
        result = TOOL["selective_suffix_preview"](quick, [24, 25, 31], [0, 0, 0])
        self.assertEqual([i for i, value in enumerate(result["quick_select"]) if value == 0xFFFFFFFF], [24, 26, 27, 28, 29, 30, 31])
        self.assertEqual(result["history"], [0xFFFFFFFF, 25, 0xFFFFFFFF])
        self.assertEqual(result["quick_select"][25], 25)
        self.assertEqual(quick, list(range(32)))

    def test_selective_wing_clear_retains_selector_and_boot_without_repair(self):
        preview = TOOL["selective_suffix_preview"]
        for selector in (0, 1, 2, 0xFFFFFFFF):
            for boot in (0, 3, 4, 0xDEADBEEF):
                result = preview([0] * 32, [0, 0, 0], [selector, 3, boot])
                self.assertEqual(result["pack_boot"], [selector, 0, boot])
                self.assertEqual(result["selector_equals_one_after"], selector == 1)
                self.assertIsNone(result["equip_success"])
        for pack in (0, 1, 2, 4, 0x80000000, 0xFFFFFFFF):
            self.assertEqual(preview([0] * 32, [0, 0, 0], [1, pack, 2])["pack_boot"], [1, pack, 2])

    def test_raw_unknown_and_duplicate_history_words_not_repaired(self):
        quick = [0xDEADBEEF, 0xFFFFFFFF, 25, 25] * 8
        history = [0xFFFFFFFF, 25, 25]
        result = TOOL["selective_suffix_preview"](quick, history, [2, 4, 4])
        self.assertEqual(result["quick_select"], quick)
        self.assertEqual(result["history"], history)
        self.assertEqual(result["pack_boot"], [2, 4, 4])

    def test_previews_reject_invalid_types_shapes_and_ranges(self):
        for argument in (None, True, -1, 1 << 64, 3.0):
            with self.assertRaises(ValueError):
                TOOL["native_pack_preview"](argument)
        for value in (True, -(1 << 31) - 1, 1 << 31, 1.0, float("nan")):
            with self.assertRaises(ValueError):
                TOOL["lua_integer_payload_preview"](value)
        for bad in (None, "abc", [0], [0] * 4, [True, 0, 0], [-1, 0, 0], [1 << 32, 0, 0]):
            with self.assertRaises(ValueError):
                TOOL["boot_publication_preview"](bad, 0)
        for args in ((None, [0] * 3, [0] * 3), ([0] * 31, [0] * 3, [0] * 3),
                     ([0] * 32, [0] * 2, [0] * 3), ([0] * 32, [0] * 3, [0] * 4)):
            with self.assertRaises(ValueError):
                TOOL["selective_suffix_preview"](*args)

    def test_snapshot_retains_raw_fields_and_detached_preview_only(self):
        self.native()
        data = fixture()
        struct.pack_into(">32I", data, 0x284, *range(32))
        struct.pack_into(">6I", data, 0x42C, 24, 25, 0xDEADBEEF, 1, 3, 0x80000000)
        with tempfile.TemporaryDirectory(prefix="tod-equipment-mutation-") as folder:
            path = Path(folder) / "GAME.bin"
            path.write_bytes(data)
            observation = TOOL["inspect"](ELF, path)["save_observation"]
            self.assertEqual(observation["history_raw_words"], [24, 25, 0xDEADBEEF])
            self.assertEqual(observation["pack_boot_raw_words"], [1, 3, 0x80000000])
            self.assertEqual(observation["selective_suffix_only_preview"]["pack_boot"], [1, 0, 0x80000000])
            self.assertEqual(path.read_bytes(), data)

    def test_invalid_elf_and_plaintext_inputs_rejected(self):
        self.native()
        with tempfile.TemporaryDirectory(prefix="tod-equipment-mutation-invalid-") as folder:
            path = Path(folder) / "invalid.bin"
            for data in (b"wrong", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL["inspect"](ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL["inspect"](path)

    def test_actual_save_and_inputs_unchanged(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save for actual plaintext observation")
        before = [hashlib.sha256(path.read_bytes()).digest() for path in (ELF, SAVE)]
        observation = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(observation["size"], 0x906F0)
        self.assertEqual(observation["plaintext_sha256"], "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
        self.assertEqual(observation["pack_boot_raw_words"], [0, 0, 0])
        self.assertEqual(observation["history_raw_words"], [15, 25, 0])
        self.assertEqual(observation["quick_select_raw_words"], [0xFFFFFFFF] * 32)
        self.assertEqual(observation["selective_suffix_only_preview"]["history"], [15, 25, 0])
        self.assertEqual(before, [hashlib.sha256(path.read_bytes()).digest() for path in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
