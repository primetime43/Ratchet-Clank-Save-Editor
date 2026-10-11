"""Equipment request/menu fallback previews, native guards and unchanged snapshots."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("equipment_lifecycle", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodEquipmentLifecycle.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


def fixture(words):
    data = bytearray(0x906F0)
    for index in range(32):
        struct.pack_into(">I", data, index*0x14, index)
    struct.pack_into(">3i", data, 0x42C, *words)
    return data


class EquipmentLifecycleChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf for native evidence")
        return TOOL.inspect(ELF)

    def test_reproduces_map(self):
        report = self.native()
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["equipment_lifecycle"])

    def test_native_evidence(self):
        report = self.native()
        elf = TOOL.BINDINGS.Elf(ELF)
        self.assertEqual(report["storage"]["history_offsets"], ["0x42c", "0x430", "0x434"])
        self.assertEqual(report["storage"]["runtime_pending_item_member"], "0x140")
        self.assertEqual(report["storage"]["runtime_active_handle_member"], "0x144")
        self.assertNotIn("runtime_active_id_member", report["storage"])
        self.assertIn("runtime pending ID140=-1", report["restore_requests"]["reset"])
        self.assertEqual(report["restore_requests"]["queue_seed_va"], "0x466fd8")
        dispatch = report["history_dispatch"]
        self.assertEqual(dispatch["history_slot_offset"], "0x28")
        self.assertEqual(dispatch["runtime_state_member"], "0x110")
        self.assertEqual(dispatch["entry_latch_member"], "0x118")
        self.assertEqual(dispatch["call_va"], "0x4674c0")
        self.assertIn("precedes", dispatch["ordering"])
        self.assertIn("never directly stores saved", report["equipment_request"]["rule"])
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)

    def test_restore_requests_and_seed_are_distinct(self):
        cases = [((15,25,0),15,15), ((-1,25,7),0,1), ((0,25,7),0,25),
                 ((0,-1,7),0,1), ((30,25,7),0,30), ((31,25,7),31,31), ((0,0,7),0,0)]
        for words, request, seed in cases:
            self.assertEqual(TOOL.restore_requests_preview(words),
                {"equip_request": request, "runtime_history_seed_if_empty": seed})

    def test_menu_fallback_and_duplicate_preservation(self):
        cases = [((15,25,0),15,25), ((15,15,15),15,15), ((0,25,7),25,7),
                 ((-1,25,7),25,7), ((15,0,7),15,7), ((15,-1,7),15,7),
                 ((0,0,0),-1,-1), ((-1,-1,31),-1,31)]
        for words, primary, secondary in cases:
            self.assertEqual(TOOL.menu_history_preview(words),
                {"runtime_5034": primary, "runtime_5030": secondary})

    def test_invalid_preview_inputs_and_no_mutation(self):
        for words in ([-1]*2, [-1]*4, [-2,0,0], [32,0,0], [True,0,0], [1.0,0,0]):
            for operation in (TOOL.restore_requests_preview, TOOL.menu_history_preview):
                with self.assertRaises(ValueError):
                    operation(words)
        words = [15,25,0]
        TOOL.restore_requests_preview(words)
        TOOL.menu_history_preview(words)
        self.assertEqual(words, [15,25,0])

    def test_unknown_snapshot_words_remain_raw(self):
        self.native()
        data = fixture((-2,0x7FFFFFFF,-0x80000000))
        with tempfile.TemporaryDirectory(prefix="tod-equipment-lifecycle-") as folder:
            path = Path(folder)/"snapshot.bin"
            path.write_bytes(data)
            observed = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual(observed["raw_history_words"], [-2,0x7FFFFFFF,-0x80000000])
            self.assertFalse(observed["normal_catalog_domain"])
            self.assertIsNone(observed["restore_request_selection_only"])
            self.assertIsNone(observed["menu_selection_only"])
            self.assertEqual(path.read_bytes(), data)

    def test_bad_snapshot_shape_and_identity(self):
        self.native()
        with tempfile.TemporaryDirectory(prefix="tod-equipment-invalid-") as folder:
            path = Path(folder)/"snapshot.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_snapshot_and_originals_unchanged(self):
        self.native()
        if SAVE is None:
            self.skipTest("Pass --save for actual snapshot")
        before = [hashlib.sha256(path.read_bytes()).digest() for path in (ELF,SAVE)]
        observed = TOOL.inspect(ELF, SAVE)["save_observation"]
        self.assertEqual(observed["raw_history_words"], [15,25,0])
        self.assertEqual(observed["restore_request_selection_only"],
                         {"equip_request": 15, "runtime_history_seed_if_empty": 15})
        self.assertEqual(observed["menu_selection_only"], {"runtime_5034": 15, "runtime_5030": 25})
        self.assertEqual(before, [hashlib.sha256(path.read_bytes()).digest() for path in (ELF,SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__]+remaining)
