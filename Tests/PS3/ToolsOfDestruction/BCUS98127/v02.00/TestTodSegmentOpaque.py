"""Regression checks for bounded opaque-word owner audit and raw-bit fidelity."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSegmentOpaque.py"))
ELF = SAVE = None


def fixture():
    data = bytearray(TOOL["SAVE_SIZE"])
    for slot in range(32):
        struct.pack_into(">I", data, slot * 20, slot)
    return data


class SegmentOpaqueChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        return TOOL["inspect"](ELF)

    def test_selected_guard_ranges_reproduce(self):
        report = self.native()
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        self.assertEqual(len(report["instruction_guards"]), 30)
        for guard in report["instruction_guards"]:
            self.assertEqual(elf.read(int(guard["va"], 0), len(guard["bytes"]) // 2).hex().upper(), guard["bytes"])
        self.assertEqual(len(report["reviewed_candidates"]), 3)
        self.assertEqual(report["reviewed_candidates"][1]["copy_source_offset"], "0x14")

    def test_no_new_semantic_or_global_absence_claim(self):
        report = self.native()
        self.assertIn("not a global", report["warning"])
        self.assertIn("No new semantic", report["unresolved"])
        self.assertIn("prior byte-footprint", report["prior_evidence_boundary"])
        self.assertTrue(all(v["type"] == "opaque bytes" for k, v in report["storage"].items() if isinstance(v, dict)))
        self.assertIn("not the owner", report["reviewed_candidates"][2]["conclusion"])
        self.assertEqual(len(report["recommended_annotations"]), 3)
        self.assertEqual(len({v["name"] for v in report["recommended_annotations"]}), 3)
        self.assertTrue(all(v["kind"] == "comment" for v in report["recommended_annotations"]))

    def test_nonzero_nan_and_signed_raw_patterns_stay_opaque(self):
        data = fixture()
        first = 0x488
        final = first + 19 * 0x408 + 9 * 0x30
        data[first + 0x28:first + 0x2C] = bytes.fromhex("7FC01234")
        data[final + 0x28:final + 0x2C] = bytes.fromhex("FFFFFFFF")
        data[final + 0x2D:final + 0x30] = bytes.fromhex("0180FF")
        data[first + 19 * 0x408 + 0x404:first + 20 * 0x408] = bytes.fromhex("DEADBEEF")
        before = bytes(data)
        result = TOOL["opaque_observation"](data)
        self.assertEqual(result["worlds"][0]["segments"][0]["word28_hex"], "7FC01234")
        self.assertEqual(result["worlds"][19]["segments"][9]["word28_hex"], "FFFFFFFF")
        self.assertEqual(result["worlds"][19]["segments"][9]["tail2d_2f_hex"], "0180FF")
        self.assertEqual(result["worlds"][19]["tail404_407_hex"], "DEADBEEF")
        self.assertEqual([result[k] for k in ("nonzero_segment_word28_count", "nonzero_segment_tail_count", "nonzero_world_tail_count")], [2, 1, 1])
        self.assertEqual(bytes(data), before)
        json.dumps(result, allow_nan=False)

    def test_adjacent_bytes_never_blend_into_opaque_ranges(self):
        data = fixture()
        data[0x488 + 0x2C] = 0xAA
        data[0x488 + 0x403] = 0xBB
        data[0x488 + 0x408] = 0xCC
        result = TOOL["opaque_observation"](data)
        self.assertEqual(result["nonzero_segment_word28_count"], 0)
        self.assertEqual(result["nonzero_segment_tail_count"], 0)
        self.assertEqual(result["nonzero_world_tail_count"], 0)
        self.assertEqual(len(result["worlds"]), 20)
        self.assertTrue(all(len(w["segments"]) == 10 for w in result["worlds"]))

    def test_malformed_layout_and_input_type_rejected(self):
        for data in (bytes(0), bytes(TOOL["SAVE_SIZE"] - 1), bytes(TOOL["SAVE_SIZE"] + 1),
                     memoryview(fixture()), None, "x"):
            with self.assertRaises(ValueError):
                TOOL["opaque_observation"](data)
        data = fixture()
        data[20:24] = b"\0\0\0\0"
        with self.assertRaises(ValueError):
            TOOL["opaque_observation"](data)

    def test_exact_inputs_unchanged_and_zero_is_observation_only(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save")
        before = [hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in (ELF, SAVE)]
        report = TOOL["inspect"](ELF, SAVE)
        observed = report["save_observation"]
        self.assertEqual(observed["sha256"], "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
        self.assertTrue(all(observed[k] == 0 for k in ("nonzero_segment_word28_count", "nonzero_segment_tail_count", "nonzero_world_tail_count")))
        self.assertIn("do not prove", observed["qualification"])
        self.assertEqual([hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in (ELF, SAVE)], before)

    def test_embedded_report_reproduces(self):
        report = self.native()
        mapping = json.loads(TOOL["BINDINGS"]["MAP_PATH"].read_text())
        if "segment_opaque" not in mapping:
            self.skipTest("Parent integration pending")
        self.assertEqual(report, mapping["segment_opaque"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
