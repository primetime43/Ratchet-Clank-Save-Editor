"""Named pack/boot fields, exact-one selector semantics and immutable observations."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
SPEC = importlib.util.spec_from_file_location("hero_aux", ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodHeroAux.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for i in range(32):
        struct.pack_into(">I", data, i * 0x14, i)
    return data


class HeroAuxChecks(unittest.TestCase):
    def setUp(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build verification")

    def test_reproduces_map(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(TOOL.inspect(ELF), mapping["hero_aux_fields"])

    def test_named_getter_setter_chains_and_distinct_boot_quirk(self):
        report = TOOL.inspect(ELF)
        self.assertEqual([(x["name"], x["native_va"]) for x in report["lua_bindings"]],
                         [("get_pack_type", "0x26fb0"), ("get_boot_type", "0x26fa0"),
                          ("set_pack_type", "0x27a30"), ("set_boot_type", "0x26f60")])
        self.assertEqual([x["offset"] for x in report["fields"]], ["0x438", "0x43c", "0x440"])
        self.assertIn("ignores its incoming argument and always stores0", report["fields"][2]["rule"])
        self.assertIn("fctiwz", report["setter_conversion"])
        self.assertIn("different monolithic-config", report["excluded_lookalike"])
        self.assertIn("original64-bit", report["fields"][1]["rule"])

    def test_native_enums_are_not_ownership_or_sentinel_equipment(self):
        report = TOOL.inspect(ELF)
        self.assertEqual([(x["enum"], x["id"]) for x in report["enum_catalogs"]["pack"]],
                         list(zip(["PACK_HELI", "PACK_THRUSTER", "PACK_HYDRO", "PACK_WING", "PACK_TYPE_COUNT"], range(5))))
        self.assertEqual([(x["enum"], x["id"]) for x in report["enum_catalogs"]["boot"]],
                         list(zip(["BOOT_NORMAL", "BOOT_GRIND", "BOOT_GRAV", "BOOT_CHARGE", "BOOT_TYPE_COUNT"], range(5))))
        self.assertIn("not equipment", report["warning"])
        self.assertEqual([(x["when_exactly_one_message"], x["otherwise_message"]) for x in report["dispatch_consumers"]],
                         [("0x58d", "0x58e"), ("0x58c", "0x58b")])

    def test_selector_is_exact_one_and_inconsistent_words_not_repaired(self):
        with tempfile.TemporaryDirectory(prefix="tod-hero-aux-selector-") as folder:
            path = Path(folder) / "GAME.bin"
            for selector in (0, 1, 2, 0xAB, 0xFFFFFFFF):
                data = fixture()
                struct.pack_into(">III", data, 0x438, selector, 3, 2)
                path.write_bytes(data)
                observation = TOOL.inspect(ELF, path)["save_observation"]
                self.assertEqual(observation["selector_equals_one"], selector == 1)
                self.assertEqual([w["value"] for w in observation["words"]], [selector, 3, 2])
                self.assertEqual([w["native_enum"] for w in observation["words"]], [None, "PACK_WING", "BOOT_GRAV"])
                self.assertEqual(path.read_bytes(), data)

    def test_unknown_and_type_count_values_preserve_raw_without_label(self):
        with tempfile.TemporaryDirectory(prefix="tod-hero-aux-unknown-") as folder:
            path = Path(folder) / "GAME.bin"
            for pack, boot in ((4, 4), (0xFFFFFFFF, 0x80000000), (0xDEADBEEF, 17)):
                data = fixture()
                struct.pack_into(">III", data, 0x438, 0xAB, pack, boot)
                path.write_bytes(data)
                observation = TOOL.inspect(ELF, path)["save_observation"]
                words = observation["words"]
                self.assertEqual([x["value"] for x in words], [0xAB, pack, boot])
                self.assertEqual([x["raw_hex"] for x in words], [f"{n:08X}" for n in (0xAB, pack, boot)])
                self.assertTrue(all(w["native_enum"] is None for w in words))
                self.assertFalse(observation["selector_equals_one"])
                self.assertEqual(path.read_bytes(), data)

    def test_rejects_invalid_inputs(self):
        with tempfile.TemporaryDirectory(prefix="tod-hero-aux-invalid-") as folder:
            path = Path(folder) / "invalid.bin"
            for data in (b"invalid", bytes(0x906F0)):
                path.write_bytes(data)
                with self.assertRaisesRegex(ValueError, "plaintext"):
                    TOOL.inspect(ELF, path)
            with self.assertRaisesRegex(ValueError, "size mismatch"):
                TOOL.inspect(path)

    def test_actual_snapshot_and_inputs_unchanged(self):
        if SAVE is None:
            self.skipTest("Pass --save for actual snapshot verification")
        before = [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)]
        observation = TOOL.inspect(ELF, SAVE)["save_observation"]
        self.assertEqual([w["value"] for w in observation["words"]], [0, 0, 0])
        self.assertEqual([w["native_enum"] for w in observation["words"]], [None, "PACK_HELI", "BOOT_NORMAL"])
        self.assertFalse(observation["selector_equals_one"])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).digest() for p in (ELF, SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--save", type=Path)
    options, remaining = parser.parse_known_args()
    ELF, SAVE = options.elf, options.save
    unittest.main(argv=[__file__] + remaining)
