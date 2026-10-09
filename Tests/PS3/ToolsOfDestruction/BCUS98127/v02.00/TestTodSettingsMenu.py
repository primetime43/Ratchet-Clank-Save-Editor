"""Exact shipped menu descriptor dispatch; static inspection, never Lua execution."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSettingsMenu.py"))
ARCHIVE = None


class SettingsMenuChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ARCHIVE is None:
            raise unittest.SkipTest("Pass --archive for exact shipped asset validation")
        archive = TOOL["PSARC"].Psarc(ARCHIVE)
        cls.raw = archive.read_entry(archive.names.index(TOOL["ASSET"]), TOOL["ASSET_SIZE"])
        cls.before = hashlib.sha256(cls.raw).digest()
        cls.report = TOOL["inspect_bytes"](cls.raw)

    def test_exact_asset_and_guarded_functions(self):
        self.assertEqual(self.report["asset"]["sha256"], TOOL["ASSET_HASH"])
        self.assertEqual(len(self.report["bytecode_digests"]), 4)
        for guard in self.report["asset_byte_guards"]:
            offset = int(guard["offset"], 0)
            self.assertEqual(self.raw[offset:offset + 4].hex().upper(), guard["bytes"])
        self.assertEqual(hashlib.sha256(self.raw).digest(), self.before)

    def test_reproduces_embedded_mapping(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads(json.dumps(self.report)), mapping["settings_menu"])

    def test_enabled_descriptors_not_every_literal_row_visible(self):
        rows = self.report["descriptors"]
        self.assertEqual(len(rows), 12)
        self.assertEqual(self.report["visible_descriptor_indices"], [1, 4, 7, 10, 11, 12])
        self.assertFalse(rows[7]["enabled_literal"])
        self.assertFalse(rows[8]["enabled_literal"])
        self.assertEqual(rows[7]["getter"], "is_look_x_inverted")
        self.assertEqual(rows[8]["getter"], "is_look_y_inverted")
        self.assertIn("only enabled descriptors", self.report["actions"]["activation_filter"])

    def test_axis_dispatch_does_not_redefine_saved_flag_polarity(self):
        dispatch = self.report["axis_dispatch"]
        self.assertEqual(dispatch["scheme_0"]["x_getter"], "is_x_inverted")
        self.assertEqual(dispatch["scheme_0"]["y_getter"], "is_y_inverted")
        self.assertEqual(dispatch["scheme_1"]["x_getter"], "is_look_x_inverted")
        self.assertEqual(dispatch["scheme_1"]["y_getter"], "is_look_y_inverted")
        self.assertIn("not reversal", dispatch["read_and_write"])
        self.assertIn("entries0/1 only", dispatch["space_combat"])
        self.assertEqual(self.report["descriptors"][9]["setter"], {1.0: "set_look_x_inverted", 0.0: "set_x_inverted"})

    def test_tag_ids_percentage_steps_and_unknown_options_stay_distinct(self):
        tags = self.report["value_display_tags"]
        self.assertEqual(tags["boolean"], {"true": 93, "false": 94})
        self.assertEqual(tags["axis"], {"true": 95, "false": 96})
        self.assertIn("divided by10", self.report["actions"]["percentage"])
        self.assertIn("logical opposite", self.report["actions"]["boolean_and_axis"])
        self.assertIn("HERO_SAW_CONTROL_MENU", self.report["actions"]["global_event"])
        self.assertTrue(any("114C0" in text for text in self.report["unresolved"]))
        self.assertTrue(any("906E4" in text for text in self.report["unresolved"]))

    def test_rejects_other_asset_or_modified_bytecode(self):
        with self.assertRaises(ValueError):
            TOOL["inspect_bytes"](b"not the verified shipped menu")
        changed = bytearray(self.raw)
        changed[0xF65A3] ^= 1
        with self.assertRaises(ValueError):
            TOOL["inspect_bytes"](changed)
        self.assertEqual(hashlib.sha256(self.raw).digest(), self.before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    args, remaining = parser.parse_known_args()
    ARCHIVE = args.archive
    unittest.main(argv=[__file__] + remaining)
