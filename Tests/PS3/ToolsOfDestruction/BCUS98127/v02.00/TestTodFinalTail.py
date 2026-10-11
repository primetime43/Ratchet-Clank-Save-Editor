"""Opaque-tail copy-boundary evidence, settings footprint and immutable byte observations."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("final_tail", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodFinalTail.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i*0x14, i)
    return data


class FinalTailChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(TOOL.inspect(ELF), mapping["final_tail_fields"])

    def test_exact_native_guards_and_tail_pointer(self):
        report = TOOL.inspect(ELF)
        self.assertEqual(report["opaque_word"]["offset"], "0x906e4")
        self.assertEqual(report["opaque_word"]["va"], "0x10280204")
        self.assertIsNone(report["opaque_word"]["semantic_name"])
        elf = TOOL.BINDINGS.Elf(ELF)
        self.assertGreaterEqual(len(report["instruction_guards"]), 30)
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)

    def test_leaf_initializer_coverage_is_exactly46_bytes_not_padding_verdict(self):
        footprint = TOOL.inspect(ELF)["settings_initializer_footprint"]
        self.assertEqual(footprint["covered_byte_count"], 46)
        self.assertEqual(len(footprint["stores"]), 16)
        self.assertEqual(footprint["unwritten_members"], ["0x2e", "0x2f"])
        self.assertEqual(footprint["unwritten_save_offsets"], ["0x114d6", "0x114d7"])
        covered = set()
        for store in footprint["stores"]:
            offset = int(store["member_offset"], 0)
            covered.update(range(offset, offset + store["size"]))
        self.assertEqual(covered, set(range(46)))
        self.assertIn("or prove padding", footprint["rule"])

    def test_restart_excludes_word_but_preserves_both_opaque_options(self):
        restart = TOOL.inspect(ELF)["selective_restart"]
        self.assertEqual(restart["opaque_word_at_copy_boundary"], 0)
        self.assertEqual(len(restart["grid_preservation_ranges"]), 21)
        self.assertEqual(len(restart["special_bolt_mask_preservation_ranges"]), 20)
        self.assertEqual(restart["grid_preservation_ranges"][-1]["end_exclusive"], "0x906e4")
        ranges = (restart["fixed_preservation_ranges"] + restart["grid_preservation_ranges"]
                  + restart["special_bolt_mask_preservation_ranges"])
        for region in ranges:
            start, end = int(region["offset"], 0), int(region["end_exclusive"], 0)
            self.assertEqual(end - start, int(region["size"], 0))
            self.assertFalse(start <= 0x906E4 < end)
        settings = next(r for r in ranges if r["offset"] == "0x114a8")
        self.assertEqual(settings["end_exclusive"], "0x114d8")
        self.assertIn("copy boundary only", restart["scope"])

    def test_whole_copy_boundaries_and_pointer_census_do_not_claim_semantic_usage(self):
        report = TOOL.inspect(ELF)
        copies = report["whole_state_copy_boundaries"]
        self.assertEqual([c["function_va"] for c in copies], ["0x35e710", "0x35e508", "0x3cf1b8"])
        for copy in copies:
            self.assertEqual(copy["size"], "0x906f0")
            for offset, length in ((0x906E4, 4), (0x114D6, 2)):
                self.assertLessEqual(offset + length, int(copy["size"], 0))
        census = report["aligned_pointer_census"]
        self.assertEqual(census["matches"], [])
        self.assertEqual(census["settings_pointer_matches"], ["0x8a3bbc"])
        self.assertIn("not proof of no computed", census["rule"])
        self.assertIn("not proven padding", report["limitations"][1])

    def test_arbitrary_opaque_values_and_neighbor_bytes_are_preserved(self):
        data = fixture()
        data[0x114D4:0x114D8] = bytes.fromhex("01027FFF")
        data[0x906E0:0x906F0] = bytes.fromhex("01234567DEADBEEF89ABCDEFFEDCBA98")
        with tempfile.TemporaryDirectory(prefix="tod-final-tail-") as folder:
            path = Path(folder) / "snapshot.bin"
            path.write_bytes(data)
            observation = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual(observation["opaque_word"]["unsigned_bits"], 0xDEADBEEF)
            self.assertEqual(observation["opaque_word"]["raw_hex"], "DEADBEEF")
            self.assertEqual([v["value"] for v in observation["opaque_options"]], [0x7F, 0xFF])
            self.assertEqual([v["raw_hex"] for v in observation["opaque_options"]], ["7F", "FF"])
            json.dumps(observation, allow_nan=False)
            self.assertEqual(path.read_bytes(), data)

    def test_rejects_bad_inputs(self):
        with tempfile.TemporaryDirectory(prefix="tod-final-tail-invalid-") as folder:
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
        self.assertEqual(observation["opaque_word"]["unsigned_bits"], 0)
        self.assertEqual([v["value"] for v in observation["opaque_options"]], [0, 0])
        self.assertEqual(observation["sha256"], "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
