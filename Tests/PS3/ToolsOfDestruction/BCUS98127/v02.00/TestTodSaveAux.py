"""Exact saved adaptation evidence, unknown/nonfinite retention and immutable inputs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("save_aux", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSaveAux.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i*0x14, i)
    return data


class SaveAuxChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(TOOL.inspect(ELF), mapping["save_aux_fields"])

    def test_typed_fields_initializer_branch_rules_and_exact_guards(self):
        report = TOOL.inspect(ELF)
        self.assertEqual([(f["offset"], f["type"], f["initializer"]) for f in report["fields"]],
                         [("0x8758", "u32 BE", 0), ("0x875c", "u32 BE", 0), ("0x8760", "f32 BE", 1.0)])
        self.assertEqual(report["update"]["saved_pointer"], "0x101efb20")
        self.assertEqual(report["update"]["constants"]["lower"], struct.unpack(">f", bytes.fromhex("3F19999A"))[0])
        self.assertIn("min(max(", report["update"]["finite_clamp"])
        self.assertIn("sixaxis_enabled", report["fields"][1]["rule"])
        self.assertIn("final8760 is forced1.0", report["update"]["branches"][0])
        self.assertIn("Extremely large", report["update"]["threshold"])
        elf = TOOL.BINDINGS.Elf(ELF)
        self.assertEqual(len(report["instruction_guards"]), 20)
        for guard in report["instruction_guards"]:
            expected = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"], 0), len(expected)), expected)

    def test_unsigned_nonfinite_and_out_of_bounds_values_are_not_normalized(self):
        for bits, expected in [(0x7FC12345, "nan"), (0xFF800000, "-inf"), (0x3F000000, 0.5), (0x40000000, 2.0)]:
            data = fixture()
            struct.pack_into(">III", data, 0x8758, 0xFFFFFFFF, 0x80000000, bits)
            with tempfile.TemporaryDirectory(prefix="tod-save-aux-") as folder:
                path = Path(folder) / "snapshot.bin"
                path.write_bytes(data)
                fields = TOOL.inspect(ELF, path)["save_observation"]["fields"]
                self.assertEqual([f["value"] for f in fields], [0xFFFFFFFF, 0x80000000, expected])
                self.assertEqual(fields[2]["raw_hex"], f"{bits:08X}")
                json.dumps(fields, allow_nan=False)
                self.assertEqual(path.read_bytes(), data)

    def test_rejects_bad_inputs(self):
        with tempfile.TemporaryDirectory(prefix="tod-save-aux-invalid-") as folder:
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
        self.assertEqual([f["value"] for f in observation["fields"]], [0, 0, 1.0])
        self.assertEqual([f["raw_hex"] for f in observation["fields"]], ["00000000", "00000000", "3F800000"])
        self.assertEqual(observation["sha256"], "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    args, remaining = parser.parse_known_args()
    ELF, SAVE = args.elf, args.save
    unittest.main(argv=[__file__] + remaining)
