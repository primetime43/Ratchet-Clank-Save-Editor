"""Mission mutation: stale flags, residual bytes, ordering and safe bounds."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodMissionMutation.py"))
ELF = SAVE = None


def mission_list(entries=(), stale_flags=0):
    data = bytearray(0x7C)
    for i in range(10):
        struct.pack_into(">3I", data, i * 12, 0xFFFFFFFF, 0xFFFFFFFF, stale_flags)
    for i, entry in enumerate(entries):
        struct.pack_into(">3I", data, i * 12, *entry)
    struct.pack_into(">I", data, 0x78, len(entries))
    return data


class MissionMutationChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact native evidence")
        return TOOL["inspect"](ELF)

    def test_map_reproduction(self):
        report = self.native()
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["mission_mutation"])

    def test_native_compaction_initialization_and_guard_reproduction(self):
        report = self.native()
        self.assertEqual(sorted(s["entry_offset"] for s in report["compaction"]["byte_stores"]), list(range(12)))
        self.assertEqual([s["entry_offset"] for s in report["initialization"]["entry_stores"]], [4, 0, 4, 0])
        self.assertEqual(report["layout"]["capacity"] * report["layout"]["entry_stride"], 0x78)
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)

    def test_constructor_loop_preview_retains_flags_not_final_nested_initializer(self):
        original = mission_list([(562, 641, 1)], 0xABCD1235)
        struct.pack_into(">I", original, 0x78, 0xFFFFFFFF)
        before = bytes(original)
        result = TOOL["initialize_list_preview"](original)
        self.assertEqual(struct.unpack_from(">I", result, 0x78)[0], 0)
        for i in range(10):
            self.assertEqual(result[i * 12:i * 12 + 8], bytes.fromhex("FFFFFFFFFFFFFFFF"))
            self.assertEqual(result[i * 12 + 8:i * 12 + 12], before[i * 12 + 8:i * 12 + 12])
        self.assertEqual(bytes(original), before)

    def test_completion_uses_destination_unknown_and_optional_bits_not_source(self):
        for source_flags, destination_flags in [(0xFFFFFFFD, 0), (0, 0xABCD1235)]:
            a = mission_list([(562, 641, source_flags)])
            c = mission_list(stale_flags=destination_flags)
            before = bytes(a), bytes(c)
            result = TOOL["complete_preview"](a, c, 562)
            self.assertTrue(result["changed"])
            self.assertEqual(struct.unpack_from(">3I", result["completed"], 0), (562, 641, destination_flags | 2))
            self.assertEqual(result["active"][:12], before[0][:12])
            self.assertEqual(struct.unpack_from(">I", result["active"], 0x78)[0], 0)
            self.assertEqual((bytes(a), bytes(c)), before)

    def test_compaction_keeps_survivor_order_all_flags_and_residual_last_entry(self):
        entries = [(10, 110, 0x80000001), (20, 120, 0x12345678), (30, 130, 0xABCD5678)]
        a, c = mission_list(entries), mission_list()
        result = TOOL["complete_preview"](a, c, 20)
        self.assertEqual(struct.unpack_from(">3I", result["active"], 0), entries[0])
        self.assertEqual(struct.unpack_from(">3I", result["active"], 12), entries[2])
        self.assertEqual(struct.unpack_from(">3I", result["active"], 24), entries[2])
        self.assertEqual(struct.unpack_from(">I", result["active"], 0x78)[0], 2)
        self.assertEqual(struct.unpack_from(">3I", result["completed"], 0), (20, 120, 2))

    def test_add_overwrites_all_entry_bytes_with_low_eight_flags(self):
        a = mission_list(stale_flags=0xFFFFFFFF)
        c = mission_list()
        result = TOOL["add_preview"](a, c, 562, 641, 0x123456AB)
        self.assertEqual(struct.unpack_from(">3I", result["active"], 0), (562, 641, 0xAB))
        self.assertEqual(result["active"][12:0x78], a[12:0x78])
        self.assertEqual(result["completed"], c)
        self.assertEqual(struct.unpack_from(">I", result["active"], 0x78)[0], 1)

    def test_duplicate_title_only_across_lists_is_noop_even_if_description_differs(self):
        for a, c in [(mission_list([(562, 1, 0)]), mission_list()),
                     (mission_list(), mission_list([(562, 2, 0)]))]:
            before = bytes(a), bytes(c)
            result = TOOL["add_preview"](a, c, 562, 641, 1)
            self.assertFalse(result["changed"])
            self.assertEqual((result["active"], result["completed"]), before)
        a, c = mission_list([(562, 641, 1)]), mission_list([(562, 999, 2)])
        result = TOOL["complete_preview"](a, c, 562)
        self.assertFalse(result["changed"])
        self.assertEqual((result["active"], result["completed"]), (a, c))

    def test_inactive_title_residuals_are_not_duplicate_or_completable(self):
        a, c = mission_list(), mission_list()
        struct.pack_into(">3I", a, 0, 562, 641, 0xABCD1235)
        self.assertFalse(TOOL["complete_preview"](a, c, 562)["changed"])
        result = TOOL["add_preview"](a, c, 562, 641, 0)
        self.assertTrue(result["changed"])
        self.assertEqual(struct.unpack_from(">3I", result["active"], 0), (562, 641, 0))

    def test_full_lists_and_corrupt_counts_never_emulate_unsafe_memory(self):
        full = mission_list([(i, 100 + i, 0) for i in range(10)])
        empty = mission_list()
        self.assertFalse(TOOL["add_preview"](full, empty, 99, 199, 0)["changed"])
        with self.assertRaisesRegex(ValueError, "count word"):
            TOOL["complete_preview"](mission_list([(99, 199, 1)]), full, 99)
        for count in (11, 0x80000000, 0xFFFFFFFF):
            corrupt = mission_list()
            struct.pack_into(">I", corrupt, 0x78, count)
            for a, c in ((corrupt, empty), (empty, corrupt)):
                with self.assertRaisesRegex(ValueError, "physical"):
                    TOOL["add_preview"](a, c, 99, 199, 0)
                with self.assertRaisesRegex(ValueError, "physical"):
                    TOOL["complete_preview"](a, c, 99)

    def test_invalid_preview_shapes_and_numbers(self):
        for invalid in ([], bytes(123), bytes(125), None):
            with self.assertRaises(ValueError):
                TOOL["initialize_list_preview"](invalid)
        for value in (-1, 0x100000000, True, 1.0, None):
            with self.assertRaises(ValueError):
                TOOL["add_preview"](mission_list(), mission_list(), value, 1, 0)
            with self.assertRaises(ValueError):
                TOOL["add_preview"](mission_list(), mission_list(), 1, value, 0)
            with self.assertRaises(ValueError):
                TOOL["add_preview"](mission_list(), mission_list(), 1, 1, value)
            with self.assertRaises(ValueError):
                TOOL["complete_preview"](mission_list(), mission_list(), value)

    def test_raw_snapshot_counts_and_inactive_flags_remain_visible(self):
        self.native()
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 20, i)
        struct.pack_into(">I", data, 0x10148 + 8, 0xABCD1235)
        struct.pack_into(">I", data, 0x10AF8 + 0x78, 0xFFFFFFFF)
        with tempfile.TemporaryDirectory(prefix="tod-mission-raw-") as directory:
            path = Path(directory) / "snapshot.bin"
            path.write_bytes(data)
            observed = TOOL["inspect"](ELF, path)["save_observation"]["lists"]
            self.assertEqual(observed[0]["inactive_flags"][0], "0xabcd1235")
            self.assertEqual(observed[20]["saved_count"], 0xFFFFFFFF)
            self.assertTrue(observed[20]["exceeds_capacity"])
            self.assertEqual(len(observed[20]["physical_flags"]), 10)
            self.assertEqual(observed[20]["inactive_flags"], [])
            self.assertFalse(observed[19]["named_level"])
            self.assertEqual(path.read_bytes(), data)

    def test_bad_snapshot_preflight(self):
        self.native()
        with tempfile.TemporaryDirectory(prefix="tod-mission-invalid-") as directory:
            path = Path(directory) / "snapshot.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL["inspect"](ELF, path)

    def test_actual_snapshot_unchanged_and_no_occupied_example_claimed(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save for actual detached snapshot")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observed = TOOL["inspect"](ELF, SAVE)["save_observation"]
        self.assertEqual(len(observed["lists"]), 40)
        self.assertEqual({r["saved_count"] for r in observed["lists"]}, {0})
        self.assertEqual({f for r in observed["lists"] for f in r["physical_flags"]}, {"0x00000000"})
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, rest = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + rest)
