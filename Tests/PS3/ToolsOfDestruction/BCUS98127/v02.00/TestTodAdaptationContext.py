"""Exact Decryptor context, named outcome exports and safe snapshot observations."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("adaptation_context", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodAdaptationContext.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i*0x14, i)
    return data


class AdaptationContextChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(TOOL.inspect(ELF), mapping["adaptation_context"])

    def test_named_context_outcome_exports_and_speed_binding(self):
        report = TOOL.inspect(ELF)
        self.assertEqual(report["named_context"]["name"], "Decryptor minigame")
        self.assertEqual([(t["name"], t["id"]) for t in report["named_context"]["named_tags"]],
                         [("GEN_TXT_GPLAY_DECRYPTSTART", 0x389), ("GEN_TXT_GPLAY_DECRYPTWIN", 0x38A),
                          ("GEN_TXT_GPLAY_DECRYPTLOSE", 0x38B), ("GEN_TXT_GPLAY_DECRYPTTKO", 0x38C)])
        self.assertEqual(report["spark_speed_binding"]["script_name"], "dc_set_spark_speed")
        self.assertEqual(report["spark_speed_binding"]["registration_va"], "0x89e688")
        self.assertEqual(report["spark_speed_binding"]["base_runtime_member"], "0x51dc")
        self.assertEqual(report["spark_speed_binding"]["scaled_runtime_member"], "0x51d8")
        self.assertEqual([f["display_name"] for f in report["saved_fields"]],
                         ["Decryptor wins (native)", "Decryptor SIXAXIS losses (native)", "Decryptor spark-speed multiplier"])
        self.assertIn("not universal lifetime statistics", report["warning"])

    def test_bounded_signed_relative_jump_table_and_exact_guards(self):
        report = TOOL.inspect(ELF)
        elf = TOOL.BINDINGS.Elf(ELF)
        dispatch = report["seven_state_dispatch"]
        self.assertEqual(dispatch["count"], 7)
        self.assertEqual(dispatch["runtime_member"], "0x20")
        table = int(dispatch["table_va"], 0)
        targets = [table+d for d in struct.unpack(">7i", elf.read(table, 28))]
        self.assertEqual(targets, [int(s["case_va"], 0) for s in dispatch["states"]])
        self.assertEqual(targets, [0x3B8DFC, 0x3B9694, 0x3B93A8, 0x3B9190, 0x3B9144, 0x3B8F68, 0x3B8E6C])
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(raw)), raw)
        caller = next(g for g in report["instruction_guards"] if g["va"] == "0x3b8bf0")
        self.assertEqual(len(bytes.fromhex(caller["bytes"])), 0x3BA168-0x3B8BF0)
        self.assertIn("runtime-only", dispatch["rule"])

    def test_preserves_large_counters_nonfinite_float_and_sixaxis_raw_byte(self):
        data = fixture()
        struct.pack_into(">III", data, 0x8758, 0xFFFFFFFF, 0x80000000, 0x7FC12345)
        data[0x114D3] = 0xAB
        with tempfile.TemporaryDirectory(prefix="tod-adaptation-context-") as folder:
            path = Path(folder) / "snapshot.bin"
            path.write_bytes(data)
            observed = TOOL.inspect(ELF, path)["save_observation"]
            self.assertEqual([f["value"] for f in observed["fields"]], [0xFFFFFFFF, 0x80000000, "nan"])
            self.assertEqual([f["raw_hex"] for f in observed["fields"]], ["FFFFFFFF", "80000000", "7FC12345"])
            self.assertEqual(observed["sixaxis_raw_hex"], "AB")
            json.dumps(observed, allow_nan=False)
            self.assertEqual(path.read_bytes(), data)

    def test_rejects_bad_inputs(self):
        with tempfile.TemporaryDirectory(prefix="tod-adaptation-context-invalid-") as folder:
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
        observed = TOOL.inspect(ELF, SAVE)["save_observation"]
        self.assertEqual([f["value"] for f in observed["fields"]], [0, 0, 1.0])
        self.assertEqual([f["raw_hex"] for f in observed["fields"]], ["00000000", "00000000", "3F800000"])
        self.assertEqual(observed["sixaxis_raw_hex"], "01")
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
