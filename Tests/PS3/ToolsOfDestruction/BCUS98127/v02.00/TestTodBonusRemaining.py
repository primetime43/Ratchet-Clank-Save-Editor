"""Remaining bonus menu evidence, language provenance and immutable snapshots."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("bonus_remaining", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodBonusRemaining.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE, ARCHIVE = None, None, None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32): struct.pack_into(">I", data, i*0x14, i)
    return data


class BonusRemainingChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None: self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(TOOL.inspect(ELF), mapping["bonus_remaining"])

    def test_native_language_pointer_literals_full_guards_and_qualified_names(self):
        report = TOOL.inspect(ELF)
        self.assertEqual(report["runtime_language"]["va"], "0x100d6478")
        self.assertEqual(report["runtime_language"]["elf_initial_value"], 1)
        self.assertEqual(report["runtime_language"]["unmatched_parser_value"], 1)
        self.assertEqual([(r["selector"], [t["token"] for t in r["tokens"]])
                         for r in report["runtime_language"]["literal_token_catalog"]],
            [(10, ["chinese", "cn"]), (14, ["danish", "dk"]), (12, ["finnish", "fi"]),
             (2, ["french", "fr"]), (4, ["german", "de"]), (5, ["italian", "it"]),
             (0, ["japanese", "jp"]), (9, ["korean", "kp"]), (6, ["dutch", "nl"]),
             (15, ["norwegian", "no"]), (7, ["portuguese", "pt"]), (3, ["spanish", "es"]),
             (13, ["swedish", "se"])])
        self.assertIn("not guessed", report["runtime_language"]["scope"])
        self.assertEqual(len(report["recommended_annotations"]), 4)
        elf = TOOL.BINDINGS.Elf(ELF)
        self.assertGreaterEqual(len(report["instruction_guards"]), 180)
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)

    def test_native_numeric_language_alias_unknowns_and_menu_definition_remapping(self):
        self.assertEqual(TOOL.numeric_language_setter(11), 10)
        for value in (0, 1, 10, 12, 15, 16, 0xFFFFFFFF):
            self.assertEqual(TOOL.numeric_language_setter(value), value)
        for language in (0, 2, 10, 11, 0xFFFFFFFF):
            self.assertEqual([TOOL.availability_indices(i, language)["threshold_definition_index"] for i in range(13)],
                             [0, 1, 2, 3, 4, 6, 6, 8, 9, 10, 10, 12, 13])
        for i in range(14):
            self.assertEqual(TOOL.availability_indices(i, 1),
                             {"physical_index_after_first_remap": i, "threshold_definition_index": i})
        self.assertEqual(TOOL.availability_indices(13, 0),
                         {"physical_index_after_first_remap": 14, "threshold_definition_index": 13})
        for value in (-1, True, 1.0, 0x100000000):
            with self.assertRaises(ValueError): TOOL.numeric_language_setter(value)
        for args in ((-1, 1), (14, 1), (True, 1), (1, -1), (1, True), (1, 0x100000000)):
            with self.assertRaises(ValueError): TOOL.availability_indices(*args)

    def test_remaining_names_physical_thresholds_are_not_state_effects(self):
        report = TOOL.inspect(ELF)
        self.assertEqual([r["id"] for r in report["effects"]], [0, 2, 4, 6, 8, 10, 12, 13])
        self.assertEqual([r["physical_definition_score_requirement"] for r in report["effects"]],
                         [25, 75, 150, 250, 350, 450, 600, 750])
        for row in report["effects"]:
            self.assertFalse(row["saved_byte_effect_confirmed"])
            self.assertEqual(row["physical_definition_state_count"], 1)
            self.assertIn("not get_cheat_state", row["scope"])
            self.assertIn("language-adjusted", row["scope"])
        self.assertIn("named enum constants", report["availability_context"]["warning"])
        self.assertIn("111 call's return code", report["recommended_annotations"][3]["comment"])

    def test_raw_unknown_states_unsigned_scores_are_preserved_and_not_activity(self):
        states = [0, 1, 8, 9, 128, 255, 254, 7]
        with tempfile.TemporaryDirectory(prefix="tod-bonus-remaining-") as folder:
            path = Path(folder) / "snapshot.bin"
            for score in (0, 24, 25, 749, 750, 0xFFFFFFFF):
                data = fixture()
                for cheat_id, state in zip(TOOL.ENUMS, states): data[0x86F8+cheat_id] = state
                data[0x8706:0x8708] = bytes.fromhex("BEEF")
                struct.pack_into(">I", data, 0x8708, score)
                path.write_bytes(data)
                observation = TOOL.inspect(ELF, path)["save_observation"]
                self.assertEqual(observation["weighted_score"], score)
                self.assertEqual([e["raw_state"] for e in observation["states"]], states)
                self.assertEqual([e["physical_definition_threshold_satisfied"] for e in observation["states"]],
                                 [score >= threshold for threshold in (25, 75, 150, 250, 350, 450, 600, 750)])
                self.assertTrue(all("active" not in e and "unlocked" not in e for e in observation["states"]))
                self.assertEqual(path.read_bytes(), data)
                json.dumps(observation, allow_nan=False)

    def test_input_preflight_size_and_all32_inventory_ids(self):
        with tempfile.TemporaryDirectory(prefix="tod-bonus-remaining-invalid-") as folder:
            path = Path(folder) / "snapshot.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"): TOOL.inspect(ELF, path)
            for index in (0, 1, 15, 31):
                data = fixture(); struct.pack_into(">I", data, index*0x14, index+1)
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext inventory"): TOOL.inspect(ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"): TOOL.inspect(path)
        with self.assertRaisesRegex(ValueError, "exact USA"): TOOL.inspect_asset_bytes(b"invalid")

    def test_actual_snapshot_immutable(self):
        if SAVE is None: self.skipTest("Pass --save for supplied snapshot")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observation = TOOL.inspect(ELF, SAVE)["save_observation"]
        self.assertEqual(observation["weighted_score"], 750)
        self.assertEqual([s["raw_state"] for s in observation["states"]], [0]*8)
        self.assertTrue(all(s["physical_definition_threshold_satisfied"] for s in observation["states"]))
        self.assertEqual(observation["sha256"], "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])

    def test_shipped_asset_literal_descriptors_gates_and_playback(self):
        if ARCHIVE is None: self.skipTest("Pass --archive for shipped pause-asset verification")
        observation = TOOL.inspect(ELF, archive_path=ARCHIVE)["asset_observation"]
        self.assertEqual([(r["id"], r["art_index_min"], r["art_index_max"]) for r in observation["concept_descriptors"]],
                         [(2, 1, 66), (6, 67, 112), (10, 113, 131), (13, 132, 141)])
        self.assertEqual([(r["id"], r["row_index"]) for r in observation["cinematic_descriptors"]],
                         [(0, 17), (4, 18), (8, 19), (12, 20), (12, 21), (12, 22)])
        self.assertTrue(all(not r["initial_enabled_literal"] for r in observation["cinematic_descriptors"]))
        self.assertEqual(len(observation["bytecode_digests"]), 5)
        self.assertEqual(observation["cinematic_descriptors"][0]["native_play_movie_argument"], "rcf_e3_2007_fmv")
        archive = TOOL.ASSETS.PSARC.Psarc(ARCHIVE)
        raw = archive.read_entry(archive.names.index(TOOL.ASSETS.ASSET), TOOL.ASSETS.ASSET_SIZE)
        for offset in (0xE1EA5, 0xE3C45, 0x10B5A0, 0x10BA7C):
            bad = bytearray(raw); bad[offset] ^= 1
            with self.assertRaisesRegex(ValueError, "exact USA"): TOOL.inspect_asset_bytes(bad)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE, ARCHIVE = args.elf, args.save, args.archive
    unittest.main(argv=[__file__] + remaining)
