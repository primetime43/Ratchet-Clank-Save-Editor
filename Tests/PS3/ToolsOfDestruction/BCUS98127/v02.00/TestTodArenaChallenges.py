"""Exact-build arena checks. Synthetic fixtures are not gameplay captures."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodArenaChallenges.py"))
ELF, ASSETS, SAVE = None, None, None


class ArenaChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None or ASSETS is None:
            self.skipTest("Pass --elf and --assets for exact-build validation")

    def test_reproduces_map_and_direct_id_boundaries(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        report = TOOL["inspect"](ELF, ASSETS)
        self.assertEqual(report, mapping["arena_challenges"])
        self.assertEqual([e["id"] for e in report["catalog"]], list(range(1, 23)))
        self.assertEqual(report["catalog"][-1]["save_offset"], "0x5730")
        self.assertEqual(report["storage"]["count"], 23)
        self.assertEqual(report["storage"]["end_exclusive"], "0x5734")
        self.assertEqual(report["storage"]["following_category_counts"]["words"], 8)
        self.assertIn("not proof of24", report["menu_resolver"]["warning"])

    def test_csv_order_is_not_native_id_order_and_blanks_stay_unknown(self):
        report = TOOL["inspect"](ELF, ASSETS)
        catalog = {e["enum"]: e for e in report["catalog"]}
        self.assertEqual(catalog["IFF_A_2"]["id"], 2)
        self.assertEqual(catalog["IFF_A_2"]["shipped"]["time_seconds"], 120)
        self.assertEqual(catalog["IFF_A_8"]["shipped"]["time_seconds"], 60)
        self.assertEqual(catalog["IFF_A_4"]["shipped"]["weapon_reward_id"], 24)
        self.assertEqual(catalog["IFF_B_10"]["shipped"]["weapon_reward_id"], 30)
        self.assertEqual(catalog["IFF_A_7"]["shipped"]["weapon_restriction_id"], 3)
        self.assertIsNone(catalog["IFF_A_1"]["shipped"]["weapon_reward_id"])
        self.assertIsNone(catalog["IFF_A_1"]["shipped"]["time_seconds"])
        self.assertEqual([p["offset"] for p in report["configuration"]["properties"]], ["0x0", "0x4", "0x8", "0xc", "0x10", "0x14"])
        self.assertIn("Runtime configuration, not saved", report["configuration"]["warning"])
        self.assertIn("not a write", report["transactions"]["failure"])

    def test_signed_values_and_adjacent_unknown_words_preserved(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 20, i)
        for i, value in ((0, 0xDEADBEEF), (7, 0x80000000), (22, 0xFFFFFFFF)):
            struct.pack_into(">I", data, 0x56D8 + 4 * i, value)
        data[0x5734:0x5754] = bytes(range(32))
        with tempfile.TemporaryDirectory(prefix="tod-arena-check-") as temporary:
            path = Path(temporary) / "GAME.bin"
            path.write_bytes(data)
            actual = TOOL["inspect"](ELF, ASSETS, path)["save_observation"]
            self.assertEqual(len(actual["counters"]), 23)
            self.assertEqual(actual["counters"][7]["signed_value"], -2147483648)
            self.assertEqual(actual["counters"][22]["signed_value"], -1)
            self.assertEqual(actual["counters"][0]["raw_hex"], "DEADBEEF")
            self.assertEqual(actual["following_category_raw"], bytes(range(32)).hex().upper())
            self.assertEqual(path.read_bytes(), data)

    def test_rejects_bad_assets_elf_and_nonplaintext(self):
        with tempfile.TemporaryDirectory(prefix="tod-arena-check-") as temporary:
            folder = Path(temporary)
            for name in TOOL["ASSETS"]:
                (folder / name).write_bytes((ASSETS / name).read_bytes())
            (folder / "arena.csv").write_bytes(b"not a verified config")
            with self.assertRaisesRegex(ValueError, "Asset SHA-256 mismatch"):
                TOOL["inspect"](ELF, folder)
            path = folder / "bad.bin"
            for data in (b"not a save", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL["inspect"](ELF, ASSETS, path)
            data = bytearray(ELF.read_bytes())
            data[0x16E08] ^= 1
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                TOOL["inspect"](path, ASSETS)

    def test_actual_inputs_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual observations")
        paths = [ELF, SAVE] + [ASSETS / name for name in TOOL["ASSETS"]]
        before = [hashlib.sha256(p.read_bytes()).digest() for p in paths]
        actual = TOOL["inspect"](ELF, ASSETS, SAVE)["save_observation"]
        if actual["plaintext_sha256"] == "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463":
            self.assertEqual([c["signed_value"] for c in actual["counters"]], [0] * 23)
            self.assertEqual(actual["following_category_raw"], "00" * 32)
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in paths])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, ASSETS, SAVE = options.elf, options.assets, options.save
    unittest.main(argv=[__file__] + remaining)
