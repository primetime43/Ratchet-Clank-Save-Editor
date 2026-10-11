"""Bonus consumer evidence, unsigned/state branches and immutable supplied observations."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("bonus_effects", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodBonusEffects.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i*0x14, i)
    return data


class BonusEffectChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(TOOL.inspect(ELF), mapping["bonus_effects"])

    def test_native_ids_score_thresholds_pointer_guards_and_annotations(self):
        report = TOOL.inspect(ELF)
        self.assertEqual([(e["id"], e["state_offset"], e["weighted_score_requirement"]) for e in report["effects"]],
                         [(1, "0x86f9", 50), (3, "0x86fb", 100), (5, "0x86fd", 200),
                          (7, "0x86ff", None), (9, "0x8701", None), (11, "0x8703", 500)])
        self.assertEqual(report["weighted_score_offset"], "0x8708")
        self.assertEqual(len(report["recommended_annotations"]), 7)
        self.assertEqual([e["id"] for e in report["enum_evidence"]], [1, 3, 5, 7, 9, 11])
        elf = TOOL.BINDINGS.Elf(ELF)
        self.assertGreaterEqual(len(report["instruction_guards"]), 80)
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)

    def test_head_branch_factors_unsigned_threshold_and_unknown_states(self):
        for state, factor in [(1, 2.0), (2, 4.0), (3, 0.5), (4, 1.0), (255, 1.0)]:
            self.assertEqual(TOOL.head_basis_preview(1, state, 50), factor)
            self.assertIsNone(TOOL.head_basis_preview(1, state, 49))
            self.assertEqual(TOOL.head_basis_preview(1, state, 0xFFFFFFFF), factor)
        for state, factor in [(1, 2.5), (2, 0.5), (3, 2.5), (255, 2.5)]:
            self.assertEqual(TOOL.head_basis_preview(3, state, 100), factor)
            self.assertIsNone(TOOL.head_basis_preview(3, state, 99))
        for cheat_id in (1, 3):
            self.assertIsNone(TOOL.head_basis_preview(cheat_id, 0, 0xFFFFFFFF))
        for arguments in ((1, -1, 50), (1, 256, 50), (1, True, 50), (1, 1, -1),
                          (1, 1, True), (1, 1, 0x100000000), (7, 1, 500), (1.0, 1, 50)):
            with self.assertRaises(ValueError):
                TOOL.head_basis_preview(*arguments)

    def test_runtime_dependencies_and_no_local_bounds_or_availability_claim(self):
        report = TOOL.inspect(ELF)
        effects = {e["id"]: e for e in report["effects"]}
        self.assertIn("return exactly1", effects[5]["rule"])
        self.assertIn("modulo8", effects[7]["rule"])
        self.assertIn("Neither local block checks", effects[7]["rule"])
        self.assertIn("state255 remains an index", effects[7]["scope"])
        self.assertIn("nonzero OR", effects[9]["rule"])
        self.assertIn("outside saved state", effects[9]["scope"])
        self.assertIn("while other flag bits remain", effects[11]["rule"])
        self.assertIn("not modified", effects[11]["rule"])
        self.assertIn("not additional save offsets", effects[11]["scope"])
        self.assertIn("8734 and warning latch8738 are different", report["score_scope"])

    def test_arbitrary_raw_states_unsigned_scores_and_neighbors_preserved(self):
        data = fixture()
        states = [1, 2, 3, 255, 128, 255]
        for cheat_id, state in zip((1, 3, 5, 7, 9, 11), states):
            data[0x86F8 + cheat_id] = state
        data[0x8706:0x8708] = bytes.fromhex("BEEF")
        struct.pack_into(">I", data, 0x8708, 0xFFFFFFFF)
        with tempfile.TemporaryDirectory(prefix="tod-bonus-effects-") as folder:
            path = Path(folder) / "snapshot.bin"
            path.write_bytes(data)
            observation = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual(observation["weighted_score"], 0xFFFFFFFF)
            self.assertEqual([e["raw_state"] for e in observation["effects"]], states)
            self.assertEqual([e["raw_hex"] for e in observation["effects"]], [f"{s:02X}" for s in states])
            self.assertEqual([e["saved_branch_basis_factor"] for e in observation["effects"][:2]], [2.0, 0.5])
            self.assertTrue(all("active" not in e for e in observation["effects"]))
            json.dumps(observation, allow_nan=False)
            self.assertEqual(path.read_bytes(), data)

    def test_rejects_bad_inputs(self):
        with tempfile.TemporaryDirectory(prefix="tod-bonus-effects-invalid-") as folder:
            path = Path(folder) / "snapshot.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_snapshot_and_inputs_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for supplied snapshot")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observation = TOOL.inspect(ELF, SAVE)["save_observation"]
        self.assertEqual(observation["weighted_score"], 750)
        self.assertEqual([e["raw_state"] for e in observation["effects"]], [0]*6)
        self.assertEqual([e["weighted_score_requirement_satisfied"] for e in observation["effects"]],
                         [True, True, True, None, None, True])
        self.assertEqual([e["saved_branch_basis_factor"] for e in observation["effects"][:2]], [None, None])
        self.assertEqual(observation["sha256"], "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
