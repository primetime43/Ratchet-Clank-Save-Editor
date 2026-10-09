"""Synthetic PSARC safety checks; optional read-only reference-archive check."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("psarc_reader", ROOT / "Tools/Inspect-Psarc.py")
READER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = READER
SPEC.loader.exec_module(READER)
ARCHIVE = None


def fixture(files, compressed=False, uppercase=False):
    names = list(files)
    payloads = [("\n".join(names) + "\n").encode()] + list(files.values())
    blocks, streams, records = [], [], []
    for i, payload in enumerate(payloads):
        first = len(blocks)
        stream = bytearray()
        for start in range(0, len(payload), 65536):
            raw = payload[start:start + 65536]
            packed = zlib.compress(raw) if compressed else raw
            if len(packed) >= len(raw):
                packed = raw
            blocks.append(len(packed) if len(packed) < 65536 else 0)
            stream.extend(packed)
        name = names[i - 1].upper() if uppercase and i else names[i - 1] if i else None
        records.append((hashlib.md5(name.encode()).digest() if i else bytes(16), first, len(payload)))
        streams.append(stream)
    toc_end = 32 + 30 * len(records) + 2 * len(blocks)
    result = bytearray(struct.pack(">4sI4sIIIII", b"PSAR", 0x10002, b"zlib", toc_end, 30, len(records), 65536, 3 if uppercase else 0))
    offset = toc_end
    for (digest, first, length), stream in zip(records, streams):
        result.extend(digest + first.to_bytes(4, "big") + length.to_bytes(5, "big") + offset.to_bytes(5, "big"))
        offset += len(stream)
    result.extend(b"".join(b.to_bytes(2, "big") for b in blocks))
    result.extend(b"".join(streams))
    return result


class PsarcChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "original").mkdir()
        self.path = self.root / "original/input.psarc"

    def tearDown(self):
        self.temp.cleanup()

    def open_fixture(self, data):
        self.path.write_bytes(data)
        return READER.Psarc(self.path)

    def test_raw_compressed_multiblock_and_empty(self):
        files = {"/data/raw": bytes(range(256)) * 300, "/data/short": b"a" * 257, "/data/empty": b""}
        for compressed in (False, True):
            with self.subTest(compressed=compressed):
                archive = self.open_fixture(fixture(files, compressed))
                before = self.path.read_bytes()
                for i, payload in enumerate(files.values(), 1):
                    self.assertEqual(archive.read_entry(i), payload)
                self.assertEqual(archive.report()["filename_hash_match_count"], 3)
                self.assertEqual(self.path.read_bytes(), before)

    def test_ascii_uppercase_filename_hashes(self):
        archive = self.open_fixture(fixture({"/data/weapon.csv": b"abc"}, uppercase=True))
        self.assertEqual(archive.filename_hash_mode, "ascii-uppercase")
        self.assertEqual(archive.name_hashes_match, [True])

    def test_bounds_and_unsupported_headers(self):
        original = fixture({"/a": b"data"})
        bad_headers = [(0, b"FAIL"), (4, (0x10003).to_bytes(4, "big")), (8, b"lzma"),
                       (12, (31).to_bytes(4, "big")), (16, (31).to_bytes(4, "big")),
                       (20, bytes(4)), (24, (1024).to_bytes(4, "big")), (28, (4).to_bytes(4, "big"))]
        for offset, value in bad_headers:
            with self.subTest(offset=offset):
                broken = bytearray(original)
                broken[offset:offset + len(value)] = value
                with self.assertRaises(ValueError):
                    self.open_fixture(broken)
        with self.assertRaises(ValueError):
            self.open_fixture(original[:20])
        with self.assertRaises(ValueError):
            self.open_fixture(original[:-1])

    def test_entry_bounds(self):
        original = fixture({"/a": b"data"})
        for offset, value in ((62 + 16, (999).to_bytes(4, "big")),
                              (62 + 25, (1).to_bytes(5, "big")),
                              (62 + 20, (65537).to_bytes(5, "big"))):
            with self.subTest(offset=offset):
                broken = bytearray(original)
                broken[offset:offset + len(value)] = value
                with self.assertRaises(ValueError):
                    self.open_fixture(broken)

    def test_extraction_limits_and_invalid_indices(self):
        archive = self.open_fixture(fixture({"/a": b"data"}))
        for index in (-1, 2):
            with self.assertRaises(ValueError):
                archive.read_entry(index)
        with self.assertRaises(ValueError):
            archive.read_entry(1, 3)

    def test_zlib_output_and_trailing_data_rejected(self):
        data = fixture({"/a": b"a" * 10000}, compressed=True)
        data[62 + 20:62 + 25] = (1).to_bytes(5, "big")
        archive = self.open_fixture(data)
        with self.assertRaises(ValueError):
            archive.read_entry(1)
        data = fixture({"/a": b"a" * 10000}, compressed=True)
        data.extend(b"x")
        block_offset = 32 + 60 + 2
        data[block_offset:block_offset + 2] = (int.from_bytes(data[block_offset:block_offset + 2], "big") + 1).to_bytes(2, "big")
        archive = self.open_fixture(data)
        with self.assertRaises(ValueError):
            archive.read_entry(1)

    def test_output_guards_and_untrusted_names(self):
        archive = self.open_fixture(fixture({"../../evil.lua": b"never execute"}))
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            READER.extract(archive, 1, self.path.parent / "output")
        target = self.root / "safe-output.bin"
        self.assertEqual(READER.extract(archive, 1, target)["bytes"], 13)
        self.assertEqual(target.read_bytes(), b"never execute")
        with self.assertRaises(ValueError):
            READER.extract(archive, 1, target)
        self.assertFalse((self.root / "evil.lua").exists())
        self.assertEqual(self.path.read_bytes(), before)

    def test_manifest_nul_rejected(self):
        with self.assertRaises(ValueError):
            self.open_fixture(fixture({"/bad\x00path": b"abc"}))

    def test_reference_archive(self):
        if ARCHIVE is None:
            self.skipTest("Pass --archive for the original BCUS98127 global_cached.psarc")
        before = hashlib.sha256(ARCHIVE.read_bytes()).digest()
        archive = READER.Psarc(ARCHIVE)
        self.assertEqual(archive.version, 0x10002)
        self.assertEqual(len(archive.entries), 3297)
        self.assertEqual(archive.filename_hash_mode, "ascii-uppercase")
        self.assertTrue(all(archive.name_hashes_match))
        expected = {"weapon.csv": "2E9D75D6509F35E75B27626D1D777F4D5414FCBAA1AC553D36AE9D9F4A728F7A",
                    "mods.csv": "0A01163D76189C7AB532345C22B5355290E3D1170E76672F0309F888EC5A68EE"}
        for name, digest in expected.items():
            payload = archive.read_entry(archive.names.index("/data/configs/" + name))
            self.assertEqual(hashlib.sha256(payload).hexdigest().upper(), digest)
        self.assertEqual(hashlib.sha256(ARCHIVE.read_bytes()).digest(), before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path)
    args, remaining = parser.parse_known_args()
    ARCHIVE = args.archive
    unittest.main(argv=[sys.argv[0]] + remaining)
