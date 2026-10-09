"""Read-only PSARC v1.2/v1.4 listing and bounded single-entry extraction.

Only plaintext TOCs, 30-byte records, 64 KiB zlib blocks are supported.
Never executes payloads or rebuilds archives. --out is an explicit new file,
not a destination derived from potentially unsafe archive paths.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import zlib


@dataclass(frozen=True)
class Entry:
    index: int
    digest: bytes
    first_block: int
    length: int
    offset: int


class Psarc:
    def __init__(self, path):
        self.path = Path(path)
        self.size = self.path.stat().st_size
        with self.path.open("rb") as source:
            header = source.read(32)
            if len(header) != 32:
                raise ValueError("Truncated PSARC header")
            magic, self.version, compression, toc_end, stride, count, self.block_size, self.flags = struct.unpack(">4sI4sIIIII", header)
            if magic != b"PSAR" or self.version not in (0x10002, 0x10004):
                raise ValueError("Unsupported PSARC magic/version")
            if compression != b"zlib" or stride != 30 or self.block_size != 65536 or self.flags & ~3:
                raise ValueError("Only plaintext 30-byte/64 KiB/zlib PSARC archives are supported")
            table_end = 32 + count * stride
            if not 1 <= count <= 1_000_000 or not table_end <= toc_end <= min(self.size, 64 * 1024 * 1024):
                raise ValueError("Invalid PSARC TOC bounds")
            if (toc_end - table_end) % 2:
                raise ValueError("Incomplete PSARC block-size table")
            table = source.read(toc_end - 32)
            if len(table) != toc_end - 32:
                raise ValueError("Truncated PSARC TOC")
        self.entries = []
        self.toc_end = toc_end
        self.blocks = [int.from_bytes(table[i:i + 2], "big") for i in range(count * stride, len(table), 2)]
        for index in range(count):
            record = table[index * stride:(index + 1) * stride]
            entry = Entry(index, record[:16], int.from_bytes(record[16:20], "big"),
                          int.from_bytes(record[20:25], "big"), int.from_bytes(record[25:30], "big"))
            num_blocks = (entry.length + self.block_size - 1) // self.block_size
            if entry.first_block + num_blocks > len(self.blocks) or not toc_end <= entry.offset <= self.size:
                raise ValueError(f"Entry {index}: invalid block index/data offset")
            packed_length = sum(size or min(self.block_size, entry.length - block * self.block_size)
                                for block, size in enumerate(self.blocks[entry.first_block:entry.first_block + num_blocks]))
            if entry.offset + packed_length > self.size:
                raise ValueError(f"Entry {index}: data exceeds archive")
            self.entries.append(entry)
        manifest = self.read_entry(0, 16 * 1024 * 1024).decode("utf-8", errors="strict")
        names = manifest.splitlines()
        if len(names) != count - 1 or any(not name or "\x00" in name for name in names):
            raise ValueError("Manifest filename count/contents do not match TOC")
        self.names = [None] + names
        # ToD's flags=3 archives hash ASCII-uppercase paths, including the leading
        # slash. Detect the observed convention rather than asserting flag meaning
        # or applying Unicode case expansions to arbitrary archive names.
        ascii_upper = str.maketrans("abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        exact = [hashlib.md5(name.encode("utf-8")).digest() == entry.digest
                 for name, entry in zip(names, self.entries[1:])]
        upper = [hashlib.md5(name.translate(ascii_upper).encode("utf-8")).digest() == entry.digest
                 for name, entry in zip(names, self.entries[1:])]
        use_upper = bool(upper) and all(upper) and not all(exact)
        self.filename_hash_mode = "ascii-uppercase" if use_upper else "exact-utf8"
        self.name_hashes_match = upper if use_upper else exact

    def read_entry(self, index, max_bytes=64 * 1024 * 1024):
        if not 0 <= index < len(self.entries):
            raise ValueError("Entry index out of range")
        entry = self.entries[index]
        if entry.length > max_bytes:
            raise ValueError(f"Entry {index}: exceeds extraction limit of {max_bytes} bytes")
        output = bytearray()
        with self.path.open("rb") as source:
            source.seek(entry.offset)
            block = entry.first_block
            while len(output) < entry.length:
                expected = min(self.block_size, entry.length - len(output))
                stored_size = self.blocks[block]
                raw = source.read(stored_size or expected)
                if len(raw) != (stored_size or expected):
                    raise ValueError(f"Entry {index}: truncated block")
                if stored_size == 0 or stored_size == expected:
                    decoded = raw
                else:
                    decoder = zlib.decompressobj()
                    decoded = decoder.decompress(raw, expected + 1)
                    if not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
                        raise ValueError(f"Entry {index}: incomplete/oversized/trailing zlib data")
                if len(decoded) != expected:
                    raise ValueError(f"Entry {index}: decompressed block length mismatch")
                output.extend(decoded)
                block += 1
        return bytes(output)

    def report(self):
        return {
            "archive": self.path.name, "size": self.size, "version": f"0x{self.version:08X}",
            "flags": self.flags, "toc_end": self.toc_end, "block_size": self.block_size,
            "entry_count": len(self.entries), "filename_hash_match_count": sum(self.name_hashes_match),
            "filename_hash_mode": self.filename_hash_mode,
            "entries": [{"index": e.index, "name": self.names[e.index], "length": e.length,
                         "offset": e.offset, "first_block": e.first_block, "name_md5": e.digest.hex().upper(),
                         "name_hash_matches": self.name_hashes_match[e.index - 1] if e.index else None}
                        for e in self.entries],
            "warning": "Filename hashes do not validate payload integrity. Payloads are never executed."
        }


def extract(archive, index, destination, max_bytes=64 * 1024 * 1024):
    destination = Path(destination).resolve()
    if destination.is_relative_to(archive.path.resolve().parent):
        raise ValueError("Extraction must be outside the original archive directory")
    if destination.exists():
        raise ValueError("Output already exists; extraction never overwrites")
    payload = archive.read_entry(index, max_bytes)
    with destination.open("xb") as output:
        output.write(payload)
    return {"entry": index, "name": archive.names[index], "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest().upper()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--entry", type=int)
    selection.add_argument("--name")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--max-bytes", type=int, default=64 * 1024 * 1024)
    args = parser.parse_args()
    if args.max_bytes < 1:
        parser.error("--max-bytes must be positive")
    if bool(args.out) != (args.entry is not None or args.name is not None):
        parser.error("Single-entry extraction requires both --entry/--name and --out")
    try:
        archive = Psarc(args.archive)
        if args.out:
            index = args.entry
            if args.name is not None:
                matching = [i for i, name in enumerate(archive.names) if name == args.name]
                if len(matching) != 1:
                    raise ValueError("Requested filename is missing or ambiguous")
                index = matching[0]
            print(json.dumps(extract(archive, index, args.out, args.max_bytes), indent=2))
        else:
            print(json.dumps(archive.report(), indent=2))
    except (ValueError, OSError, zlib.error) as error:
        parser.exit(2, f"PSARC inspection failed: {error}\n")


if __name__ == "__main__":
    main()
