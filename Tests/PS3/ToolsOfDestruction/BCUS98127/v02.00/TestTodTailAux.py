"""Exact saved aggregate/countdown evidence, raw value preservation and immutable inputs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("tail_aux", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodTailAux.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i*0x14, i)
    return data


class TailAuxChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(TOOL.inspect(ELF), mapping["tail_aux_fields"])

    def test_saved_pointer_float_fields_and_exact_guards(self):
        report = TOOL.inspect(ELF)
        self.assertEqual(report["saved_subobject"]["save_offset"], "0x8744")
        self.assertEqual(report["saved_subobject"]["pointer"], "0x101f8264")
        self.assertEqual([(f["offset"], f["type"], f["initializer"]) for f in report["fields"]],
                         [("0x8744", "f32 BE", 0.0), ("0x8748", "f32 BE", 0.0),
                          ("0x874c", "f32 BE", None), ("0x8750", "f32 BE", None)])
        self.assertEqual(report["segment_finalization"]["threshold_ratio"], struct.unpack(">f", bytes.fromhex("3DCCCCCD"))[0])
        self.assertIn("not a runtime-only", report["saved_subobject"]["proof"])
        elf = TOOL.BINDINGS.Elf(ELF)
        self.assertGreaterEqual(len(report["instruction_guards"]), 30)
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)

    def test_countdown_equality_scope_and_initializer_limits(self):
        report = TOOL.inspect(ELF)
        countdown = report["countdown_update"]
        self.assertEqual(countdown["helper_va"], "0x69b810")
        self.assertEqual(countdown["context_pointer"], "0x10731da0")
        self.assertIn("equality yields0 with return0", countdown["rule"])
        self.assertIn("outside906F0", countdown["context_scope"])
        self.assertIn("8750>0 and874C>0", countdown["elapsed_gate"])
        self.assertIn("does not explicitly write874C/8750", report["initializer"]["rule"])
        self.assertEqual(report["segment_finalization"]["log_copies"],
                         [{"record_offset": "0x90", "save_source_offset": "0x8744"},
                          {"record_offset": "0x94", "save_source_offset": "0x8748"}])
        self.assertIn("still has no confirmed", report["unresolved"][0])

    def test_nonfinite_negative_unknown_and_signed_zero_are_not_normalized(self):
        data = fixture()
        bits = [0x7FC12345, 0xFF800000, 0xBF800000, 0x80000000]
        struct.pack_into(">4I", data, 0x8744, *bits)
        struct.pack_into(">I", data, 0x906E4, 0xDEADBEEF)
        with tempfile.TemporaryDirectory(prefix="tod-tail-aux-") as folder:
            path = Path(folder) / "snapshot.bin"
            path.write_bytes(data)
            fields = TOOL.inspect(ELF, path)["save_observation"]["fields"]
            self.assertEqual([f["unsigned_bits"] for f in fields], bits)
            self.assertEqual([f["value"] for f in fields], ["nan", "-inf", -1.0, -0.0])
            self.assertEqual([f["raw_hex"] for f in fields], [f"{b:08X}" for b in bits])
            json.dumps(fields, allow_nan=False)
            self.assertEqual(path.read_bytes(), data)

    def test_rejects_bad_inputs(self):
        with tempfile.TemporaryDirectory(prefix="tod-tail-aux-invalid-") as folder:
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
        self.assertEqual([f["value"] for f in observation["fields"]], [0.0, 0.0, 10.0, 300.0])
        self.assertEqual([f["raw_hex"] for f in observation["fields"]], ["00000000", "00000000", "41200000", "43960000"])
        self.assertEqual(observation["sha256"], "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
