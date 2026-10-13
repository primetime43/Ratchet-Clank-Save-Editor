"""Small portable parser checks; optional exact-archive report reproduction."""
import argparse
import json
from pathlib import Path
import runpy
import struct
import unittest
from unittest.mock import patch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodHudIcons.py"))
ARCHIVE = None


def node(name="combuster", bank=56, unknown=False):
    raw = name.encode("ascii") + b"\0"
    raw += b"\0" * (-len(raw) % 4)
    return struct.pack(">III", 0xDB84D25B, 1, 2) + struct.pack(">III", 0xAE1EAD2B, 11, len(name) + 1) + raw + \
        struct.pack(">III", 0x84471A83, 0x88 if unknown else 5, bank)


class HudIconChecks(unittest.TestCase):
    def test_named_image_nodes_require_known_complete_properties(self):
        self.assertEqual(TOOL["image_nodes"](node()), {"combuster": [{"node_offset": "0x0", "image_bank": 56}]})
        for raw in (node(bank=285), node(unknown=True), node()[:-1], b"combuster\0" + struct.pack(">I", 56)):
            self.assertEqual(TOOL["image_nodes"](raw), {})

    def test_lua_assignments_require_table_and_register_links(self):
        instructions = [
            {"op": "GETTABLE", "a": 1, "c_constant": "icon"},
            {"op": "GETGLOBAL", "a": 2, "constant": "WPN_COMBUSTER"},
            {"op": "SETTABLE", "a": 1, "b": 2, "c_constant": "combuster", "offset": "0x100"},
        ]
        function = {"instructions": instructions, "children": []}
        with patch.dict(TOOL["LUA"]):
            reader = unittest.mock.Mock()
            reader.function.return_value = function
            TOOL["LUA"]["Reader"] = unittest.mock.Mock(return_value=reader)
            self.assertEqual(TOOL["icon_assignments"](b"\x1bLua\x50")["WPN_COMBUSTER"]["name"], "combuster")
            instructions[2]["b"] = 3
            self.assertEqual(TOOL["icon_assignments"](b"\x1bLua\x50"), {})
            instructions[2]["b"] = 2
            instructions[0]["c_constant"] = "movie"
            self.assertEqual(TOOL["icon_assignments"](b"\x1bLua\x50"), {})

    def test_bc3_payload_bounds_and_format(self):
        header = bytearray(160); header[:4] = b"IGHW"; header[0x86] = 0x88
        struct.pack_into(">HH", header, 0x98, 4, 4)
        data = b"IGHW" + bytes(124) + bytes(range(16))
        self.assertEqual(TOOL["bc3_payload"](data, header), (4, 4, bytes(range(16))))
        with self.assertRaises(ValueError): TOOL["bc3_payload"](data[:-1], header)
        header[0x86] = 0xA6
        with self.assertRaises(ValueError): TOOL["bc3_payload"](data, header)

    def test_bundled_map_covers_all_nonwrench_records_without_visual_guesses(self):
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/HudIcons.json").read_text(encoding="utf-8"))
        self.assertEqual([entry["id"] for entry in mapping["items"]], list(range(1, 32)))
        self.assertEqual([entry["id"] for entry in mapping["unmapped"]], [0])
        for entry in mapping["items"]:
            self.assertTrue(entry["assignment_offsets"] and entry["image_nodes"])
            self.assertTrue(all(entry["texture_id"] in node["hud_texture_ids"] for node in entry["image_nodes"]))

    def test_exact_archive_reproduces_bundled_map(self):
        if ARCHIVE is None:
            self.skipTest("Pass --archive for the original game assets")
        expected = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/HudIcons.json").read_text(encoding="utf-8"))
        self.assertEqual(TOOL["inspect"](ARCHIVE), expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    args, rest = parser.parse_known_args()
    ARCHIVE = args.archive
    unittest.main(argv=[__file__, *rest])
