"""Check physical bonus choices, zero-based menu cycling and immutable inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodBonusSelection.py"))
MAP = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
ELF, SAVE, ARCHIVE = None, None, None


def fixture(score=750):
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i * 20, i)
    struct.pack_into(">I", data, 0x8708, score)
    return data


class BonusSelectionChecks(unittest.TestCase):
    def test_menu_cycles_include_off_and_wrap_both_directions(self):
        for count in (4, 3, 2):
            for state in range(count):
                self.assertEqual(TOOL["cycle_preview"](state, count, 1, True), (state + 1) % count)
                self.assertEqual(TOOL["cycle_preview"](state, count, -1, True), (state - 1) % count)
                for delta in (-1, 1):
                    self.assertEqual(TOOL["cycle_preview"](state, count, delta, False), state)

    def test_unknown_state_branch_is_not_modulo_arithmetic(self):
        for count in (4, 3, 2):
            for state in (8, 255):
                self.assertEqual(TOOL["cycle_preview"](state, count, 1, True), 0)
                self.assertEqual(TOOL["cycle_preview"](state, count, -1, True), 0)
                self.assertEqual(TOOL["cycle_preview"](state, count, 1, False), state)
        self.assertEqual(TOOL["cycle_preview"](4, 4, -1, True), 3)
        for args in ((-1, 4, 1, True), (256, 4, 1, True), (True, 4, 1, True),
                     (0, 0, 1, True), (0, 9, 1, True), (0, 4, 0, True),
                     (0, 4, True, True), (0, 4, 1, 1)):
            with self.assertRaises(ValueError):
                TOOL["cycle_preview"](*args)

    def test_native_catalog_reproduces_map_and_consumers(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build evidence")
        report = TOOL["inspect"](ELF)
        self.assertEqual(report, MAP["bonus_selection"])
        self.assertEqual([(r["id"], r["state_offset"], r["score_requirement"], r["state_count_including_off"]) for r in report["catalog"]],
                         [(1, "0x86f9", 50, 4), (3, "0x86fb", 100, 3), (5, "0x86fd", 200, 2), (9, "0x8701", 400, 2), (11, "0x8703", 500, 2)])
        for row in report["catalog"]:
            self.assertEqual([o["value"] for o in row["options"]], list(range(row["state_count_including_off"])))
            effect = next(e for e in MAP["bonus_effects"]["effects"] if e["id"] == row["id"])
            self.assertEqual(row["consumer_vas"], effect["consumer_vas"])
            if row["id"] == 9:
                self.assertIsNone(effect["weighted_score_requirement"])
            else:
                self.assertEqual(row["score_requirement"], effect["weighted_score_requirement"])
        elf = TOOL["EFFECTS"]["BINDINGS"].Elf(ELF)
        self.assertEqual(len(report["instruction_guards"]), 37)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)

    def test_policy_keeps_menu_indices_and_physical_offsets_separate(self):
        report = MAP["bonus_selection"]
        self.assertIn("language-remapped", report["edit_policy"])
        self.assertIn("score", report["setter_scope"])
        self.assertIn("raw byte", report["edit_policy"])
        self.assertIn("not an explicit head-transform restoration", report["warning"])
        self.assertIn("geometry/input axis", report["warning"])
        self.assertIn("in-game acceptance", report["warning"])

    def test_commentary_request_does_not_infer_or_edit_runtime_language(self):
        report = MAP["bonus_selection"]["commentary_request"]
        self.assertEqual(report["state_offset"], "0x86fd")
        self.assertEqual(report["score_requirement"], 200)
        self.assertEqual(report["state_count_including_off"], 2)
        self.assertEqual(report["required_runtime_language_id"], 1)
        self.assertEqual(report["native_guard_section"], "bonus_effects")
        self.assertIn("not inferred or changed", MAP["bonus_selection"]["edit_policy"])
        self.assertIn("does not guarantee", report["scope"])

    def test_zurkon_request_keeps_runtime_override_and_arguments_distinct(self):
        report = MAP["bonus_selection"]["zurkon_factory_choice"]
        self.assertEqual(report["state_offset"], "0x8701")
        self.assertEqual(report["definition_score_requirement"], 400)
        self.assertEqual(report["state_count_including_off"], 2)
        self.assertFalse(report["local_consumer_score_gate"])
        self.assertEqual(report["runtime_override_va"], "0x101efb10")
        self.assertEqual(report["alternate"]["factory_arguments"], [0xC3, 0x657])
        self.assertEqual(report["default"]["factory_arguments"], [0x4B, 0x311])
        self.assertEqual(report["alternate"]["float_argument"], 0.75)
        self.assertEqual(report["default"]["float_argument"], 1.5)
        self.assertIn("meaning", report["scope"])
        self.assertIn("cannot override", report["scope"])

    def test_score_boundaries_and_unknown_states_are_observed_without_changes(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build evidence")
        with tempfile.TemporaryDirectory(prefix="tod-bonus-selection-") as directory:
            path = Path(directory) / "snapshot.bin"
            for score in (0, 49, 50, 99, 100, 199, 200, 399, 400, 499, 500, 750, 0xFFFFFFFF):
                data = fixture(score)
                for states in ((0, 0, 0, 0, 0), (3, 2, 1, 1, 1), (4, 3, 2, 2, 2), (255, 255, 255, 255, 255)):
                    for offset, state in zip((0x86F9, 0x86FB, 0x86FD, 0x8701, 0x8703), states):
                        data[offset] = state
                    data[0x8706:0x8708] = b"\xBE\xEF"
                    path.write_bytes(data)
                    report = TOOL["inspect"](ELF, path)["save_observation"]
                    self.assertEqual(report["weighted_score"], score)
                    self.assertEqual([r["raw_state"] for r in report["selections"]], list(states))
                    self.assertEqual([r["editor_eligible"] for r in report["selections"]],
                                     [score >= threshold and state < count for state, threshold, count in zip(states, (50, 100, 200, 400, 500), (4, 3, 2, 2, 2))])
                    self.assertEqual(path.read_bytes(), data)

    def test_shipped_menu_reproduces_asset_map_and_cycling_guards(self):
        if ELF is None or ARCHIVE is None:
            self.skipTest("Pass --elf and --archive for native/asset evidence")
        report = TOOL["inspect"](ELF, archive_path=ARCHIVE)["asset_observation"]
        self.assertEqual(report, MAP["bonus_selection_assets"])
        self.assertEqual(len(report["bytecode_digests"]), 5)
        self.assertEqual(len(report["asset_byte_guards"]), 14)
        self.assertIn("INCLUDES off/index0", report["cycling"])
        self.assertIn("one-based", report["selection"])
        self.assertIn("failure bypasses all state writes", report["selection"])
        archive = TOOL["MENU"]["PSARC"].Psarc(ARCHIVE)
        raw = archive.read_entry(archive.names.index(TOOL["MENU"]["ASSET"]), TOOL["MENU"]["ASSET_SIZE"])
        for guard in report["asset_byte_guards"]:
            offset = int(guard["offset"], 0)
            self.assertEqual(raw[offset:offset + 4], bytes.fromhex(guard["bytes"]))
        for offset in (0x110F26, 0x110F62, 0x111120, 0x111350):
            changed = bytearray(raw)
            changed[offset] ^= 1
            with self.assertRaisesRegex(ValueError, "exact USA"):
                TOOL["inspect_asset_bytes"](changed)

    def test_rejects_unfamiliar_inputs(self):
        with self.assertRaisesRegex(ValueError, "exact USA"):
            TOOL["inspect_asset_bytes"](b"invalid")
        if ELF is None:
            self.skipTest("Pass --elf for native input validation")
        with tempfile.TemporaryDirectory(prefix="tod-bonus-selection-invalid-") as directory:
            path = Path(directory) / "snapshot.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL["inspect"](ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL["inspect"](path)

    def test_reference_snapshot_and_native_inputs_unchanged(self):
        if ELF is None or SAVE is None:
            self.skipTest("Pass --elf and --save for reference observations")
        inputs = [ELF, SAVE] + ([ARCHIVE] if ARCHIVE is not None else [])
        def digest(path):
            with path.open("rb") as stream:
                return hashlib.file_digest(stream, "sha256").digest()
        before = [digest(path) for path in inputs]
        report = TOOL["inspect"](ELF, SAVE, ARCHIVE)["save_observation"]
        self.assertEqual(report["sha256"], "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
        self.assertEqual(report["weighted_score"], 750)
        self.assertTrue(all(r["editor_eligible"] for r in report["selections"]))
        self.assertEqual(before, [digest(path) for path in inputs])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE, ARCHIVE = args.elf, args.save, args.archive
    unittest.main(argv=[__file__] + remaining)
