"""Bounded, read-only Lua 5.0 chunk inspection, including chunks embedded in assets.

No VM, execution, decompilation or file output. Layout/opcode references:
https://www.lua.org/source/5.0/lundump.c.html
https://www.lua.org/source/5.0/lopcodes.h.html
Only 32-bit int/size_t/instructions and float32/float64 numbers are supported.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

OPS = "MOVE LOADK LOADBOOL LOADNIL GETUPVAL GETGLOBAL GETTABLE SETGLOBAL SETUPVAL SETTABLE NEWTABLE SELF ADD SUB MUL DIV POW UNM NOT CONCAT JMP EQ LT LE TEST CALL TAILCALL RETURN FORLOOP TFORLOOP TFORPREP SETLIST SETLISTO CLOSE CLOSURE".split()
VENDOR_HASH = "294BA05A607BC5C4C59B60E85C57515DBBD8CDEECC9CB6BF570AE4AE937627D5"


class Reader:
    def __init__(self, raw, offset=0):
        if len(raw) > 16 * 1024 * 1024 or not 0 <= offset < len(raw):
            raise ValueError("Invalid input size/offset")
        self.raw, self.pos, self.nodes = raw, offset, 0
        header = self.take(14)
        if header[:5] != b"\x1bLua\x50" or header[5] not in (0, 1) or header[6:13] != bytes([4, 4, 4, 6, 8, 9, 9]) or header[13] not in (4, 8):
            raise ValueError("Unsupported Lua 5.0 header/layout")
        self.endian = "<" if header[5] else ">"
        self.number_size = header[13]
        if int(self.number()) != 31415926:
            raise ValueError("Unknown Lua number format")

    def take(self, size):
        if size < 0 or self.pos + size > len(self.raw):
            raise ValueError("Truncated Lua chunk")
        result = self.raw[self.pos:self.pos + size]
        self.pos += size
        return result

    def uint(self):
        return struct.unpack(self.endian + "I", self.take(4))[0]

    def count(self):
        value = self.uint()
        if value > 100000:
            raise ValueError("Lua collection/count limit exceeded")
        return value

    def string(self):
        size = self.uint()
        if size == 0:
            return None
        if size > 1024 * 1024:
            raise ValueError("Lua string limit exceeded")
        value = self.take(size)
        if value[-1:] != b"\0":
            raise ValueError("Lua string is not NUL-terminated")
        return value[:-1].decode("utf-8", errors="backslashreplace")

    def number(self):
        value = struct.unpack(self.endian + ("f" if self.number_size == 4 else "d"), self.take(self.number_size))[0]
        if not math.isfinite(value):
            raise ValueError("Nonfinite Lua constant")
        return value

    def function(self, parent_source=None, depth=0, path="root"):
        self.nodes += 1
        if depth > 32 or self.nodes > 4096:
            raise ValueError("Lua prototype depth/count limit exceeded")
        start = self.pos
        source = self.string() or parent_source
        line = self.uint()
        nups, parameters, vararg, stack = self.take(4)
        lines = [self.uint() for _ in range(self.count())]
        locals_ = [{"name": self.string(), "start_pc": self.uint(), "end_pc": self.uint()} for _ in range(self.count())]
        up_count = self.count()
        if up_count not in (0, nups):
            raise ValueError("Lua upvalue count mismatch")
        upvalues = [self.string() for _ in range(up_count)]
        constants = []
        for _ in range(self.count()):
            kind = self.take(1)[0]
            if kind not in (0, 3, 4):
                raise ValueError("Unsupported Lua constant kind")
            constants.append(None if kind == 0 else self.number() if kind == 3 else self.string())
        children = [self.function(source, depth + 1, f"{path}.{i}") for i in range(self.count())]
        count = self.count()
        code_offset = self.pos
        code = [self.uint() for _ in range(count)]
        instructions = [decode(word, pc, constants, code_offset + pc * 4) for pc, word in enumerate(code)]
        if lines and len(lines) != count:
            raise ValueError("Lua line table/code count mismatch")
        names = {}
        # Recover straightforward closure assignments only; not control-flow inference.
        for instruction in instructions:
            op, a, b, c = (instruction[k] for k in ("op", "a", "b", "c"))
            if op == "CLOSURE":
                if instruction["bx"] >= len(children):
                    raise ValueError("Invalid Lua child-prototype index")
                names[a] = instruction["bx"]
            elif op == "SETTABLE" and b >= 250 and c in names and b - 250 < len(constants):
                children[names[c]]["assigned_name"] = constants[b - 250]
            elif op not in ("SETTABLE", "SETGLOBAL", "SETUPVAL", "JMP", "RETURN", "CLOSE"):
                names.pop(a, None)
        return {"path": path, "source": source, "line_defined": line, "offset": hex(start), "code_offset": hex(code_offset),
                "parameters": parameters, "vararg": vararg, "stack": stack, "upvalues": upvalues,
                "locals": locals_, "constants": constants, "instructions": instructions, "children": children}


def decode(word, pc, constants, offset):
    index = word & 63
    if index >= len(OPS):
        raise ValueError("Unknown Lua opcode")
    op, a, b, c = OPS[index], word >> 24, word >> 15 & 511, word >> 6 & 511
    bx = word >> 6 & 262143
    sbx = bx - 131071
    result = {"pc": pc, "offset": hex(offset), "word": f"{word:08X}", "op": op, "a": a, "b": b, "c": c, "bx": bx, "sbx": sbx}
    if op in ("LOADK", "GETGLOBAL", "SETGLOBAL"):
        if bx >= len(constants):
            raise ValueError("Invalid Lua constant index")
        result["constant"] = constants[bx]
    if op in ("GETTABLE", "SELF", "SETTABLE", "ADD", "SUB", "MUL", "DIV", "POW", "EQ", "LT", "LE"):
        for field, value in (("b", b), ("c", c)):
            if op in ("GETTABLE", "SELF") and field == "b":
                continue
            if value >= 250:
                if value - 250 >= len(constants):
                    raise ValueError("Invalid Lua RK constant index")
                result[field + "_constant"] = constants[value - 250]
    if op in ("JMP", "FORLOOP", "TFORPREP"):
        result["jump_pc"] = pc + 1 + sbx
    return result


def inspect(path, offset):
    path = Path(path)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Input exceeds 16 MiB limit")
    raw = path.read_bytes()
    reader = Reader(raw, offset)
    root = reader.function()
    return {"file_sha256": hashlib.sha256(raw).hexdigest().upper(), "chunk_offset": hex(offset),
            "chunk_end_exclusive": hex(reader.pos), "number_bytes": reader.number_size,
            "endianness": "little" if reader.endian == "<" else "big", "root": root,
            "warning": "Static decoding only. No Lua VM execution or complete semantic/bytecode verification."}


def vendor_layout(report):
    """Fold the reference initializer's literal tables only; no calls or branches.

    GETGLOBAL names remain symbolic strings, not fetched values. Stop before
    icon tables: only weapArray, upgrdData and specMod are needed for graph data.
    """
    if report["file_sha256"] != VENDOR_HASH or report["chunk_offset"] != "0x54f85":
        raise ValueError("Vendor layout requires the exact reference asset/chunk")
    function = next(f for f in report["root"]["children"] if f.get("assigned_name") == "initWeaps")
    registers = {0: {}}
    constants = function["constants"]
    def operand(value):
        return constants[value - 250] if value >= 250 else registers[value]
    for instruction in function["instructions"]:
        op, a, b, c = (instruction[k] for k in ("op", "a", "b", "c"))
        if op == "SETTABLE" and a == 0 and instruction.get("b_constant") == "icon":
            break
        if op == "NEWTABLE":
            registers[a] = {}
        elif op == "GETGLOBAL":
            registers[a] = instruction["constant"]
        elif op == "LOADK":
            registers[a] = instruction["constant"]
        elif op == "GETTABLE":
            registers[a] = registers[b][operand(c)]
        elif op == "SETTABLE":
            registers[a][operand(b)] = operand(c)
        elif op == "SETLIST":
            bx = instruction["bx"]
            for i in range(1, bx % 32 + 2):
                registers[a][bx - bx % 32 + i] = registers[a + i]
        else:
            raise ValueError(f"Unsupported nonliteral initializer operation: {op}")
    self_ = registers[0]
    if set(self_) != {"weapArray", "upgrdData", "specMod"} or len(self_["upgrdData"]) != 15:
        raise ValueError("Incomplete reference vendor layout tables")
    result = {}
    for weapon, rows in self_["upgrdData"].items():
        if set(rows) != {1, 2, 3, 4} or any(set(row) != set(range(1, 8)) for row in rows.values()):
            raise ValueError("Unexpected vendor grid dimensions")
        grid = [[int(rows[row][col]) for col in range(1, 8)] for row in range(1, 5)]
        special = int(self_["specMod"][weapon])
        positions = {node: (row + 1, col + 1) for row, values in enumerate(grid) for col, node in enumerate(values) if node >= 0}
        if len(positions) != sum(node >= 0 for row in grid for node in row):
            raise ValueError("Duplicate vendor node position")
        nodes = []
        for node, (row, col) in sorted(positions.items()):
            neighbors = []
            for other_row, other_col in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
                if 1 <= other_row <= 4 and 1 <= other_col <= 7 and grid[other_row - 1][other_col - 1] >= 0:
                    neighbors.append(grid[other_row - 1][other_col - 1])
            nodes.append({"index": node, "row": row, "column": col, "orthogonal_neighbors": sorted(neighbors),
                          "is_special": node == special, "is_start": node == 0})
        result[weapon] = {"grid": grid, "special_node": special, "nodes": nodes}
    return {"asset_sha256": VENDOR_HASH, "chunk_offset": "0x54f85", "initializer_path": function["path"],
            "initializer_code_offset": function["code_offset"], "grids": result,
            "warning": "Literal grid reconstruction and geometric neighbors, not runtime simulation or gameplay validation. Negative cell markers remain uninterpreted."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--offset", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--vendor-layout", action="store_true", help="Reference-only literal upgrade grids, no bytecode execution")
    args = parser.parse_args()
    try:
        report = inspect(args.file, args.offset)
        print(json.dumps(vendor_layout(report) if args.vendor_layout else report, indent=2, allow_nan=False))
    except (ValueError, OSError) as error:
        parser.exit(2, f"Lua inspection failed: {error}\n")


if __name__ == "__main__":
    main()
