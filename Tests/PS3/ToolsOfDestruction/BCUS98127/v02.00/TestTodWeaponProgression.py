"""Exact weapon progression, synthetic boundaries and raw float-bit retention."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWeaponProgression.py"))
ELF = SAVE = None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i * 20, i)
    return data


class WeaponProgressionChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact native evidence")
        return TOOL["inspect"](ELF)

    def test_map_reproduction(self):
        report = self.native()
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["weapon_progression"])

    def test_native_guards_and_xp_before_refill_order(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)
        self.assertLess(0x4660F0, int(report["xp_transition"]["xp_store_va"], 0))
        self.assertLess(int(report["xp_transition"]["xp_store_va"], 0), 0x466188)
        self.assertEqual(elf.u32(0x4660F0), 0x4BFFFE19)
        self.assertEqual(elf.u32(0x466188), 0x4BFFFC91)
        self.assertEqual(elf.u32(int(report["ammo_arithmetic"]["zero_constant_va"], 0)), 0)

    def test_cap_exhaustive_old_bytes_flags_and_definition_limits(self):
        preview = TOOL["cap_preview"]
        for level in range(256):
            for flags in (0, 1, 2, 3, 4, 0x80000000, 0xFFFFFFFF):
                for count in (0, 1, 3, 4, 5, 9, 10, 255, 0xFFFFFFFF):
                    expected = 0 if flags & 3 else min(count, 4 if level <= 4 else 9)
                    self.assertEqual(preview(level, flags, count), expected)

    def test_cap_uses_pre_update_byte_not_new_xp(self):
        thresholds = tuple(i * 10.0 for i in range(11))
        preview = TOOL["finite_level_preview"]
        normal = preview(4, 1e30, thresholds)
        larger = preview(5, 1e30, thresholds)
        self.assertEqual((normal["pre_update_cap"], normal["recomputed_level"]), (4, 4))
        self.assertEqual((larger["pre_update_cap"], larger["recomputed_level"]), (9, 9))
        lowered = preview(9, 0, thresholds)
        self.assertEqual(lowered["recomputed_level"], 0)
        self.assertFalse(lowered["increase_path"])
        second = preview(lowered["recomputed_level"], 1e30, thresholds)
        self.assertEqual(second["recomputed_level"], 4)

    def test_thresholds_promote_inclusively_and_no_xp_clipping_preview(self):
        preview = TOOL["finite_level_preview"]
        thresholds = (0., 10., 20., 30., 40., 50.)
        for xp, expected in ((-1e30, 0), (9.999, 0), (10., 1), (20., 2), (40., 4), (1e30, 4)):
            self.assertEqual(preview(0, xp, thresholds)["recomputed_level"], expected)
        self.assertEqual(preview(5, 50., thresholds)["recomputed_level"], 5)
        self.assertEqual(preview(5, 50., thresholds, 1)["recomputed_level"], 0)

    def test_preview_rejects_nonfinite_or_unbounded_inputs(self):
        for values in ((True, 0, 9), (-1, 0, 9), (256, 0, 9), (0, -1, 9),
                       (0, 0, -1), (0, 0, 2**32), (0, 0, 9.0)):
            with self.assertRaises(ValueError):
                TOOL["cap_preview"](*values)
        for xp, thresholds in ((float("nan"), [0, 1]), (float("inf"), [0, 1]),
                               (0, [0, float("inf")]), (0, [1, 0]), (0, []),
                               (0, [0] * 21), (True, [0, 1])):
            with self.assertRaises(ValueError):
                TOOL["finite_level_preview"](0, xp, thresholds)

    def test_ammo_add_not_absolute_and_progress_not_clamped(self):
        report = self.native()
        self.assertIn("ADD delta", report["xp_transition"]["increase_ammo"])
        self.assertIn("negative old ammo", report["xp_transition"]["increase_ammo"])
        self.assertIn("no local0..1 clamp", report["progress_display"]["rule"])
        self.assertIn("RAW stored level", report["progress_display"]["rule"])
        self.assertIn("does not repair", report["progress_display"]["scope"])
        self.assertIn("not an unqualified", report["ammo_arithmetic"]["rule"])

    def test_nonfinite_extreme_xp_ammo_and_level_bits_retained(self):
        self.native()
        data = fixture()
        patterns = (0x7FC12345, 0x7F812345, 0x7F800000, 0xFF800000, 0x7F7FFFFF,
                    0xFF7FFFFF, 0x80000000, 0x00000001)
        for i, bits in enumerate(patterns):
            struct.pack_into(">II", data, i * 20 + 4, bits, patterns[-i - 1])
            data[i * 20 + 17] = 255 - i
        with tempfile.TemporaryDirectory(prefix="tod-weapon-raw-") as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(data)
            observed = TOOL["inspect"](ELF, path)["save_observation"]
            for i, bits in enumerate(patterns):
                row = observed["records"][i]
                self.assertEqual(row["xp_bits"], f"0x{bits:08X}")
                self.assertEqual(row["ammo_bits"], f"0x{patterns[-i - 1]:08X}")
                self.assertEqual(row["stored_level"], 255 - i)
                self.assertEqual(row["selected_cap_boundary"], 9)
            self.assertEqual(path.read_bytes(), data)

    def test_bad_snapshot_preflight(self):
        self.native()
        with tempfile.TemporaryDirectory(prefix="tod-weapon-bad-") as directory:
            path = Path(directory) / "fixture.bin"
            for data in (b"bad", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL["inspect"](ELF, path)

    def test_actual_save_and_elf_unchanged(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save for actual detached save")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        report = TOOL["inspect"](ELF, SAVE)
        rows = report["save_observation"]["records"]
        self.assertEqual(len(rows), 32)
        self.assertEqual([row["id"] for row in rows if row["stored_level"] > 4], list(range(1, 16)))
        self.assertEqual(rows[1]["stored_level"], 9)
        self.assertEqual(rows[1]["ammo_bits"], "0x42C80000")
        self.assertIn("No effective runtime cap", report["save_observation"]["warning"])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, rest = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + rest)
