"""Read-only exact-build pause controls metadata; never executes embedded Lua."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[4]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    result = importlib.util.module_from_spec(spec)
    # dataclass resolves the module through sys.modules when reading Psarc.
    import sys
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


PSARC = module("tod_settings_psarc", "Inspect-Psarc.py")
LUA = module("tod_settings_lua", "Inspect-Lua50.py")
ASSET = "/built/anark/pause/built.dat"
ASSET_SIZE = 1152780
ASSET_HASH = "26FC24DD3564FDF94F0F6278FC0F0BC5578FE73C6813D3F39CD113FD22CF761B"
CHUNK_OFFSET = 0xF38FC
FUNCTIONS = {
    "onInitialize": (0xF482C, 372, "BC63CF700C94B19FBF693046DEE10FF4C03E012EEE7E6F27456161598A1BBFA9"),
    "onActivate": (0xF52E2, 126, "DED16A860B2482C53D042CB0E4080803BD98C1A585722D7A6B29B42E691EABB1"),
    "updateItemData": (0xF5F59, 122, "4F14FCAA27BBA7B1BAB8F37B318D27BD1D6D95D7024ABC3966958B55BE673051"),
    "adjustOption": (0xF649B, 122, "DDD22420B52D56AF3332F3A5CEE5E19A527CF0479E3977C621747C93BB7F55A0"),
}


def fold_tables(function):
    """Fold only literal table construction, PCs49..252; no VM or calls."""
    registers = {0: {}}
    constants = function["constants"]

    def operand(value):
        return constants[value - 250] if value >= 250 else registers[value]

    for instruction in function["instructions"][49:253]:
        op, a, b, c = (instruction[k] for k in ("op", "a", "b", "c"))
        if op == "NEWTABLE":
            registers[a] = {}
        elif op == "GETGLOBAL":
            registers[a] = instruction["constant"]  # Symbol only; never call.
        elif op == "GETTABLE":
            registers[a] = registers[b][operand(c)]
        elif op == "SETTABLE":
            registers[a][operand(b)] = operand(c)
        elif op == "LOADBOOL":
            if c != 0:
                raise ValueError("Literal fold does not permit branch/skip instructions")
            registers[a] = bool(b)
        else:
            raise ValueError(f"Unsupported literal table instruction: {op}")
    return registers[0]


def inspect_bytes(raw):
    if len(raw) != ASSET_SIZE or hashlib.sha256(raw).hexdigest().upper() != ASSET_HASH:
        raise ValueError("Settings menu requires the exact USA v02.00 pause asset")
    reader = LUA.Reader(raw, CHUNK_OFFSET)
    root = reader.function()
    if root["source"] != "controlHandler" or reader.pos != 0xF715E:
        raise ValueError("Unexpected controlHandler metadata boundaries")
    selected = {}
    digests = []
    for name, (offset, count, digest) in FUNCTIONS.items():
        matches = [f for f in root["children"] if f.get("assigned_name") == name]
        if len(matches) != 1:
            raise ValueError("Ambiguous controlHandler function")
        function = matches[0]
        end = offset + count * 4
        if int(function["code_offset"], 0) != offset or len(function["instructions"]) != count or \
                hashlib.sha256(raw[offset:end]).hexdigest().upper() != digest:
            raise ValueError("Settings menu bytecode changed")
        selected[name] = function
        digests.append({"function": name, "offset": hex(offset), "instruction_count": count, "sha256": digest})
    tables = fold_tables(selected["onInitialize"])
    if set(tables["optArray"]) != set(range(1, 13)):
        raise ValueError("Unexpected options descriptor count")
    rows = []
    for index, row in sorted(tables["optArray"].items()):
        # Descriptions are summarized, not copied from shipped assets.
        rows.append({"descriptor_index": int(index), "label_tag_or_literal": row["optName"],
            "type": row["type"], "enabled_literal": row["enabled"],
            "getter": row["get"], "setter": row["set"]})
    def guard(function, pc, word):
        instruction = selected[function]["instructions"][pc]
        if instruction["word"] != word:
            raise ValueError("Settings menu relationship byteguard mismatch")
        offset = int(instruction["offset"], 0)
        return {"function": function, "pc": pc, "offset": instruction["offset"],
            "decoded_word": word, "bytes": raw[offset:offset + 4].hex().upper()}
    guards = [guard(name, pc, word) for name, pc, word in [
        ("onInitialize", 48, "0083C2C9"), ("onInitialize", 173, "01830089"),
        ("onInitialize", 178, "01A18089"), ("onInitialize", 209, "01830089"),
        ("onInitialize", 214, "01A18089"), ("onInitialize", 250, "01A8D589"),
        ("onInitialize", 252, "01A9D5C9"), ("onActivate", 18, "040240C6"),
        ("onActivate", 26, "04018059"), ("onActivate", 122, "01000945"),
        ("updateItemData", 99, "0C000745"), ("updateItemData", 101, "0B058306"),
        ("adjustOption", 66, "0100C24F"), ("adjustOption", 94, "03008099"),
        ("adjustOption", 95, "020100C6"), ("adjustOption", 106, "03000002"),
        ("adjustOption", 116, "03008002")]]
    return {"confidence": "asset-backed",
        "warning": "Exact shipped USA v02.00 pause-menu metadata, not runtime execution, in-game edit acceptance or a name for saved114C0.",
        "asset": {"archive_entry": ASSET, "size": ASSET_SIZE, "sha256": ASSET_HASH,
            "chunk_offset": hex(CHUNK_OFFSET), "chunk_end_exclusive": hex(reader.pos), "source": root["source"],
            "bytecode_endianness": "little" if reader.endian == "<" else "big"},
        "descriptors": rows,
        "visible_descriptor_indices": [r["descriptor_index"] for r in rows if r["enabled_literal"]],
        "axis_dispatch": {"scheme_0": {"x_getter": tables["optArray"][10]["get"][0],
            "y_getter": tables["optArray"][11]["get"][0], "meaning": "normal camera inversion APIs"},
            "scheme_1": {"x_getter": tables["optArray"][10]["get"][1],
            "y_getter": tables["optArray"][11]["get"][1], "meaning": "look/first-person inversion APIs"},
            "read_and_write": "Both value display and axis adjustment index the descriptor API table by get_cur_control_scheme(). This is API selection, not reversal of a saved flag's polarity.",
            "space_combat": "Initializer displays control scheme2 for a space-combat level; the axis tables have entries0/1 only. Do not infer valid scheme2 axis dispatch from this initializer."},
        "value_display_tags": {"boolean": tables["localizeKey"], "axis": tables["localizeAxisKey"],
            "warning": "These are local text tag IDs, not native enum IDs or proven English label strings. Native getters expose boolean results; raw saved bytes remain unchanged."},
        "actions": {"boolean_and_axis": "Read the chosen native API boolean and pass its logical opposite to the corresponding setter.",
            "percentage": "Adjustment delta is divided by10 before adding to native getter value and invoking setter; signed delta1/-1 therefore requests steps0.1/-0.1. Existing native setters clamp ordinary finite input0..1.",
            "activation_filter": "onActivate inserts only enabled descriptors into its option list. Literal disabled descriptors are not evidence of current menu visibility.",
            "global_event": "onActivate checks and, if clear, sets independently named HERO_SAW_CONTROL_MENU."},
        "unresolved": ["No menu binding establishes the name or polarity of saved114C0.",
            "Saved114D6/114D7 and906E4 still lack semantic confirmation.",
            "Do not assign NORMAL/INVERTED text to tag95/96 without resolving the separate localization-tag lookup.",
            "Control scheme display names and runtime input behavior remain independent of these descriptor tables."],
        "bytecode_digests": digests, "asset_byte_guards": guards}


def inspect(archive_path):
    archive = PSARC.Psarc(archive_path)
    matches = [i for i, name in enumerate(archive.names) if name == ASSET]
    if len(matches) != 1:
        raise ValueError("Exact pause asset is missing or ambiguous")
    return inspect_bytes(archive.read_entry(matches[0], ASSET_SIZE))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Exact-build global_cached.psarc; read only")
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.archive), indent=2, allow_nan=False))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f"Settings menu inspection failed: {error}\n")


if __name__ == "__main__":
    main()
