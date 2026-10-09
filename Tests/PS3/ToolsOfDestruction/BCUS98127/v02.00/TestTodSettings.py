"""Exact-build saved options/load research checks; fixtures are not gameplay captures."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSettings.py"))
ELF, SAVE = None, None


class SettingsChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build validation")

    def test_reproduces_map_and_expected_storage(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text())
        report = TOOL["inspect"](ELF)
        self.assertEqual(report, mapping["settings"])
        fields = report["block"]["fields"]
        self.assertEqual(len(fields), 15)
        self.assertEqual([int(f["offset"], 0) for f in fields],
            [0x114A8, 0x114AC, 0x114B0, 0x114B4, 0x114B8, 0x114BC,
             0x114C4, 0x114C8, 0x114CC, 0x114D0, 0x114D1, 0x114D2, 0x114D3, 0x114D4, 0x114D5])
        selection = report["level_selection"]
        self.assertEqual(selection["saved_load_offset"], "0x906e8")
        self.assertEqual(selection["next_level_offset"], "0x8740")
        self.assertEqual([c["id"] for c in selection["catalog"]], list(range(19)))
        self.assertEqual(selection["catalog"][10]["internal_name"], "sargasso")

    def test_initializer_defaults_not_inferred_from_sample(self):
        defaults = TOOL["inspect"](ELF)["block"]["default_bytes"]
        self.assertEqual(len(defaults), 16)
        self.assertEqual(defaults["0x114d0"], "01")  # sample help byte is0
        self.assertEqual(defaults["0x114d1"], "00")  # sample subtitle byte is1
        self.assertEqual(defaults["0x114c0"], "00000001")
        self.assertEqual(defaults["0x114b0"], "3F800000")
        for key in ("0x114c4", "0x114c8", "0x114cc"):
            self.assertEqual(defaults[key], "3F666666")
        self.assertNotIn("0x114d6", defaults)
        self.assertNotIn("0x114d7", defaults)

    def test_runtime_checkpoint_not_misrepresented_as_saved(self):
        report = TOOL["inspect"](ELF)
        relative = int(report["runtime_only"]["checkpoint_va"], 0) - 0x101EFB20
        self.assertGreater(relative, 0x906F0)
        self.assertIn("no saved health offset", report["runtime_only"]["warning"])
        self.assertIn("no-op", report["block"]["stub_apis"])
        consumers = report["block"]["unknown_word_consumers"]
        self.assertEqual([c["native_va"] for c in consumers], ["0x20f3f0", "0x2108d8"])
        self.assertIn("not what", report["block"]["unknown_word_usage"])
        self.assertIn("668770", report["block"]["lua_boolean_conversion"])

    def fixture(self):
        data = bytearray(0x906F0)
        for i in range(32):
            struct.pack_into(">I", data, i * 0x14, i)
        return data

    def test_nonfinite_unknown_flags_tail_and_level_ids_preserved(self):
        data = self.fixture()
        struct.pack_into(">I", data, 0x114A8, 0x80000000)
        struct.pack_into(">I", data, 0x114C4, 0x7FC12345)
        struct.pack_into(">I", data, 0x114C8, 0xFF800000)
        data[0x114D0] = 255
        data[0x114D6:0x114D8] = b"\xAB\xCD"
        struct.pack_into(">I", data, 0x114C0, 0xDEADBEEF)
        struct.pack_into(">I", data, 0x8740, 0xFFFFFFFF)
        struct.pack_into(">I", data, 0x906E8, 99)
        with tempfile.TemporaryDirectory(prefix="tod-settings-check-") as temporary:
            path = Path(temporary) / "GAME.plaintext.bin"
            path.write_bytes(data)
            actual = TOOL["inspect"](ELF, path)["save_observation"]
            fields = {f["name"]: f for f in actual["fields"]}
            self.assertTrue(fields["camera_x_inverted"]["enabled"])
            self.assertEqual(fields["voice_volume"]["raw_hex"], "7FC12345")
            self.assertEqual(fields["voice_volume"]["value"], "nan")
            self.assertEqual(fields["sound_effects_volume"]["value"], "-inf")
            self.assertEqual(fields["help_text_enabled"]["value"], 255)
            self.assertEqual(actual["unknown_word_raw"], "DEADBEEF")
            self.assertEqual(actual["unknown_tail_raw"], "ABCD")
            self.assertEqual(actual["next_level_id"], 0xFFFFFFFF)
            self.assertEqual(actual["saved_load_id"], 99)
            json.dumps(actual, allow_nan=False)
            self.assertEqual(path.read_bytes(), data)

    def test_refuses_nonplaintext_and_modified_elf(self):
        with tempfile.TemporaryDirectory(prefix="tod-settings-check-") as temporary:
            path = Path(temporary) / "bad.bin"
            for data in (b"not a save", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL["inspect"](ELF, path)
            data = bytearray(ELF.read_bytes())
            data[0x16E08] ^= 1
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                TOOL["inspect"](path)

    def test_actual_inputs_unchanged_and_observations_match_bytes(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual observations")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        actual = TOOL["inspect"](ELF, SAVE)["save_observation"]
        data = SAVE.read_bytes()
        for field in actual["fields"]:
            offset = int(field["offset"], 0)
            self.assertEqual(bytes.fromhex(field["raw_hex"]), data[offset:offset + len(field["raw_hex"]) // 2])
        if actual["plaintext_sha256"] == "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463":
            fields = {f["name"]: f for f in actual["fields"]}
            self.assertFalse(fields["help_text_enabled"]["enabled"])
            self.assertTrue(fields["subtitles_enabled"]["enabled"])
            self.assertEqual(fields["music_volume"]["raw_hex"], "3F666666")
            self.assertEqual(actual["saved_load_id"], 0)
            self.assertEqual(actual["next_level_id"], 0xFFFFFFFF)
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
