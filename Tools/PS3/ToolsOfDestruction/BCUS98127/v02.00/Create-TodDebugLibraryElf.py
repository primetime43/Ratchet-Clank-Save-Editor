"""Create a separate experimental ELF copy enabling initial Lua debug registration.

Never installs patches or overwrites an existing output. Does not launch the
blocking console, inject scripts, re-sign EBOOT.BIN or guarantee RPCS3 support.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy

BASE = Path(__file__).resolve().parent
RESEARCH = runpy.run_path(str(BASE / "Inspect-TodDeveloperHelpers.py"))
PATCH_VA = 0x72EB24
BEFORE = bytes.fromhex("38A0001F")
AFTER = bytes.fromhex("38A0003F")


def prepare(raw):
    mapping = json.loads(RESEARCH["BINDINGS"]["MAP_PATH"].read_text(encoding="utf-8"))
    binary = mapping["binary"]
    if len(raw) != binary["size"] or hashlib.sha256(raw).hexdigest().upper() != binary["sha256"]:
        raise ValueError("Requires the exact unmodified BCUS98127 v02.00 ELF")
    segments = [segment for segment in binary["load_segments"] if int(segment["va"], 0) <= PATCH_VA and
                PATCH_VA + 4 <= int(segment["va"], 0) + int(segment["file_size"], 0)]
    if len(segments) != 1:
        raise ValueError("Patch is not uniquely file-backed")
    segment = segments[0]
    offset = int(segment["file_offset"], 0) + PATCH_VA - int(segment["va"], 0)
    if raw[offset:offset + 4] != BEFORE:
        raise ValueError("Original initialization instruction differs")
    patched = bytearray(raw)
    patched[offset:offset + 4] = AFTER
    return bytes(patched), {"patch_va": hex(PATCH_VA), "file_offset": hex(offset),
                           "before": BEFORE.hex().upper(), "after": AFTER.hex().upper(),
                           "original_sha256": binary["sha256"],
                           "patched_sha256": hashlib.sha256(patched).hexdigest().upper(),
                           "changed_bytes": 1, "warning": "Experimental initial debug-library registration only. Console streams, script loading and in-game stability untested."}


def create_copy(source, destination, dry_run=False):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or destination.exists():
        raise ValueError("Output must be a new file distinct from the original ELF")
    RESEARCH["inspect"](source)
    patched, report = prepare(source.read_bytes())
    if not dry_run:
        # Exclusive creation: never replace an original, symlink or existing copy.
        with destination.open("xb") as stream:
            stream.write(patched)
    return {**report, "output": str(destination), "written": not dry_run}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(create_copy(args.elf, args.output, args.dry_run), indent=2))
