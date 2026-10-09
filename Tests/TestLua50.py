"""Synthetic bounded Lua 5.0 decoder tests; no VM execution."""
import argparse
import hashlib
from pathlib import Path
import runpy
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
LUA = runpy.run_path(str(ROOT / "Tools/Inspect-Lua50.py"))
ASSET = None


def fixture(endian="<", number_size=4, code=None, constant="hello"):
    pack = lambda value: struct.pack(endian + "I", value)
    string = lambda value: pack(len(value) + 1) + value + b"\0"
    header = b"\x1bLua\x50" + bytes([endian == "<", 4, 4, 4, 6, 8, 9, 9, number_size])
    header += struct.pack(endian + ("f" if number_size == 4 else "d"), 31415926.535897932)
    # Source, definition line, prototype fields, empty lines/locals/upvalues.
    function = string(b"fixture") + pack(0) + bytes([0, 0, 0, 2]) + pack(0) * 3
    function += pack(1) + b"\4" + string(constant.encode()) + pack(0)
    code = code if code is not None else [1, 0x0000801B]  # LOADK R0 K0; RETURN no values
    return header + function + pack(len(code)) + b"".join(pack(word) for word in code)


class LuaChecks(unittest.TestCase):
    def test_endian_and_number_layouts(self):
        for endian in ("<", ">"):
            for size in (4, 8):
                with self.subTest(endian=endian, size=size):
                    raw = fixture(endian, size)
                    reader = LUA["Reader"](raw)
                    result = reader.function()
                    self.assertEqual(result["source"], "fixture")
                    self.assertEqual(result["constants"], ["hello"])
                    self.assertEqual(reader.pos, len(raw))

    def test_opcode_positions_and_rk_250(self):
        instruction = LUA["decode"](0x03003E86, 0, ["upgrdData"], 0)
        self.assertEqual((instruction["op"], instruction["a"], instruction["b"], instruction["c"]), ("GETTABLE", 3, 0, 250))
        self.assertEqual(instruction["c_constant"], "upgrdData")
        jump = LUA["decode"](0x00800D54, 9, [], 0)
        self.assertEqual(jump["jump_pc"], 64)

    def test_bad_headers_and_truncation(self):
        raw = fixture()
        for offset, value in ((4, 0x51), (5, 2), (6, 8), (13, 2)):
            broken = bytearray(raw)
            broken[offset] = value
            with self.assertRaises(ValueError):
                LUA["Reader"](broken)
        for cut in (1, 14, len(raw) - 1):
            with self.assertRaises(ValueError):
                LUA["Reader"](raw[:cut]).function()

    def test_bad_constants_opcodes_and_count_limits(self):
        for code in ([63], [1 | (1 << 6)], [6 | (251 << 6) | (1 << 15)]):
            with self.assertRaises(ValueError):
                LUA["Reader"](fixture(code=code, constant="x")).function()
        with self.assertRaises(ValueError):
            LUA["Reader"](fixture()).take(1000000)
        reader = LUA["Reader"](fixture())
        reader.raw = reader.raw[:reader.pos] + struct.pack("<I", 100001)
        with self.assertRaises(ValueError):
            reader.count()

    def test_vendor_layout_requires_reference_fingerprint(self):
        with self.assertRaises(ValueError):
            LUA["vendor_layout"]({"file_sha256": "wrong", "chunk_offset": "0x54f85"})

    def test_reference_vendor_chunk_and_grids(self):
        if ASSET is None:
            self.skipTest("Pass --asset for the extracted original vendor built.dat")
        before = hashlib.sha256(ASSET.read_bytes()).digest()
        report = LUA["inspect"](ASSET, 0x54F85)
        self.assertEqual(report["chunk_end_exclusive"], "0x5e78a")
        self.assertEqual(report["number_bytes"], 4)
        self.assertEqual(report["root"]["source"], "weaponUpgradeHandler")
        functions = {f["assigned_name"]: f for f in report["root"]["children"]}
        self.assertEqual(functions["canBePurchased"]["code_offset"], "0x56a8a")
        self.assertEqual(len(functions["canBePurchased"]["instructions"]), 79)
        self.assertEqual(sum(i.get("c_constant") == "specialCheck" for i in functions["is_valid_movement"]["instructions"]), 4)
        grids = LUA["vendor_layout"](report)["grids"]
        self.assertEqual(len(grids), 15)
        self.assertEqual(sum(len(g["nodes"]) for g in grids.values()), 204)
        self.assertEqual(grids["WPN_COMBUSTER"]["grid"], [[-1, -1, 4, 11, 3, -1, -2], [0, 2, 7, -1, 13, -1, -2], [-2, -1, 8, -1, 12, 5, -1], [-2, -1, 6, 9, 1, 10, -1]])
        self.assertEqual(grids["WPN_RYNO"]["special_node"], -3)
        for grid in grids.values():
            nodes = {n["index"]: n for n in grid["nodes"]}
            for node, record in nodes.items():
                for neighbor in record["orthogonal_neighbors"]:
                    self.assertIn(node, nodes[neighbor]["orthogonal_neighbors"])
        self.assertEqual(hashlib.sha256(ASSET.read_bytes()).digest(), before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", type=Path)
    args, remaining = parser.parse_known_args()
    ASSET = args.asset
    unittest.main(argv=[sys.argv[0]] + remaining)
