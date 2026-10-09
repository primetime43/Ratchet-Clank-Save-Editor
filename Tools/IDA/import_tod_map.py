"""IDA 9 IDAPython: File > Script file, then choose the shared ToD map JSON.

Annotates only the matching, unre-based ELF database. Does not patch input bytes,
create guessed functions, replace user names, or apply save types to ELF globals.
"""
import json
import re
from pathlib import Path


def validate_map(mapping):
    """Validate the portable subset without requiring IDA (also used by tests)."""
    if mapping.get("schema_version") != 1:
        raise ValueError("Unsupported map schema")
    if len(bytes.fromhex(mapping["binary"]["sha256"])) != 32:
        raise ValueError("Invalid ELF SHA-256")
    names, addresses = set(), set()
    for entry in mapping["annotations"]:
        address = int(entry["va"], 0)
        if address in addresses or entry["name"] in names:
            raise ValueError("Duplicate annotation name/address")
        names.add(entry["name"])
        addresses.add(address)
        if entry["confidence"] not in ("confirmed", "observed", "candidate"):
            raise ValueError("Invalid confidence")
        if entry.get("bytes"):
            bytes.fromhex(entry["bytes"])
        if not entry["comment"] or not entry["evidence"]:
            raise ValueError("Missing evidence/comment")
    for record in mapping["structures"]:
        end = 0
        for field in record["fields"]:
            offset = int(field["offset"], 0)
            width = {"u32": 4, "u16": 2, "f32": 4, "u8": 1}[field["type"]]
            count = field.get("count", 1)
            if offset < end or count < 1:
                raise ValueError("Overlapping/invalid structure field")
            end = offset + width * count
        if end != int(record["size"], 0):
            raise ValueError("Structure size mismatch")


def declaration(record):
    types = {"u32": "unsigned int", "u16": "unsigned short", "f32": "float", "u8": "unsigned char"}
    lines, end = ["typedef struct {"], 0
    for field in record["fields"]:
        offset = int(field["offset"], 0)
        if offset > end:
            lines.append(f"  unsigned char unknown_{end:x}[{offset - end}];")
        count = field.get("count", 1)
        suffix = f"[{count}]" if count != 1 else ""
        lines.append(f"  {types[field['type']]} {field['name']}{suffix};")
        end = offset + {"u32": 4, "u16": 2, "f32": 4, "u8": 1}[field["type"]] * count
    lines.append("} " + record["name"] + ";")
    return "\n".join(lines)


def main():
    import ida_bytes
    import ida_kernwin
    import ida_name
    import ida_nalt
    import ida_typeinf

    default = Path(__file__).resolve().parents[2] / "docs" / "maps" / "ToolsOfDestruction.BCUS98127.v02.00.json"
    selected = ida_kernwin.ask_file(False, str(default), "Choose the ToD ELF address map JSON")
    if not selected:
        return
    with open(selected, encoding="utf-8") as stream:
        mapping = json.load(stream)
    validate_map(mapping)
    digest = ida_nalt.retrieve_input_file_sha256()
    if isinstance(digest, bytes):
        digest = digest.hex()
    if not digest or digest.lower() != mapping["binary"]["sha256"].lower():
        raise ValueError("ELF SHA-256 mismatch. No annotations applied.")
    # All byte guards must pass before any database mutation. Fixed VAs intentionally
    # reject rebased imports rather than guessing a relocation delta.
    for entry in mapping["annotations"]:
        address = int(entry["va"], 0)
        if entry["kind"] == "reference_base" and not ida_bytes.is_mapped(address):
            continue
        if not ida_bytes.is_mapped(address):
            raise ValueError(f"Unmapped VA {address:#x}. No annotations applied.")
        if entry.get("bytes"):
            expected = bytes.fromhex(entry["bytes"])
            if ida_bytes.get_bytes(address, len(expected)) != expected:
                raise ValueError(f"Byte mismatch at {address:#x}. No annotations applied.")
    for record in mapping["structures"]:
        existing = ida_typeinf.tinfo_t()
        if existing.get_named_type(None, record["name"]):
            print("Keeping existing type", record["name"])
            continue
        errors = ida_typeinf.idc_parse_types(declaration(record), ida_typeinf.PT_SIL)
        if errors:
            raise RuntimeError(f"Could not import type {record['name']}: {errors} parser errors")
    applied = 0
    for entry in mapping["annotations"]:
        address = int(entry["va"], 0)
        if entry["kind"] == "reference_base" and not ida_bytes.is_mapped(address):
            print(f"Unmapped TOC reference base retained in JSON: {address:#x}")
            continue
        flags = ida_bytes.get_full_flags(address)
        if not ida_bytes.has_user_name(flags):
            if not ida_name.set_name(address, entry["name"], ida_name.SN_CHECK | ida_name.SN_NOWARN):
                print(f"Could not name {address:#x}: {entry['name']}; adding comment only")
        note = (f"[ToD map: {entry['name']}; {entry['confidence']}]\n"
                f"{entry['comment']}\nEvidence: {entry['evidence']}")
        old = ida_bytes.get_cmt(address, True) or ""
        marker_pattern = r"(?m)^\[ToD map: " + re.escape(entry["name"]) + r";"
        if note not in old or len(re.findall(marker_pattern, old)) > 1:
            # Retain older research verbatim except its owned marker. Do not
            # infer where a user's appended comments end or delete any text.
            old = re.sub(marker_pattern,
                         "[Previous ToD map: " + entry["name"] + ";", old)
            if not ida_bytes.set_cmt(address, old + ("\n\n" if old else "") + note, True):
                raise RuntimeError(f"Could not add comment at {address:#x}")
        applied += 1
    print(f"Imported {applied} ToD annotations; no executable bytes patched.")


if __name__ == "__main__":
    main()
