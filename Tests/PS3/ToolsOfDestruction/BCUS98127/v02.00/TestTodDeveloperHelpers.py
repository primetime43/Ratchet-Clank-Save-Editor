"""Small portable safety checks; no game execution or private inputs required."""
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
NS = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Create-TodDebugLibraryElf.py"))


class DeveloperHelperChecks(unittest.TestCase):
    def test_patch_enables_only_debug_bit_in_same_instruction(self):
        self.assertEqual(int.from_bytes(NS["BEFORE"], "big") ^ int.from_bytes(NS["AFTER"], "big"), 0x20)
        self.assertEqual(NS["PATCH_VA"], 0x72EB24)

    def test_unknown_and_modified_binaries_are_refused(self):
        for raw in (b"", b"EBOOT", b"\0" * 32):
            with self.assertRaisesRegex(ValueError, "exact unmodified"):
                NS["prepare"](raw)

    def test_original_and_existing_outputs_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "original.elf"
            output = Path(directory) / "existing.elf"
            source.write_bytes(b"original")
            output.write_bytes(b"existing")
            for target in (source, output):
                with self.assertRaisesRegex(ValueError, "new file"):
                    NS["create_copy"](source, target)
            self.assertEqual(source.read_bytes(), b"original")
            self.assertEqual(output.read_bytes(), b"existing")

    def test_copy_and_dry_run_leave_original_untouched(self):
        # Mock native proof/bytes only here; the real CLI requires exact identity.
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "original.elf"
            target = Path(directory) / "new.elf"
            source.write_bytes(b"original")
            globals_ = NS["create_copy"].__globals__
            with patch.dict(NS["RESEARCH"], {"inspect": lambda path: None}), patch.dict(globals_, {"prepare": lambda raw: (b"patched", {})}):
                self.assertFalse(NS["create_copy"](source, target, True)["written"])
                self.assertFalse(target.exists())
                self.assertTrue(NS["create_copy"](source, target)["written"])
                self.assertEqual(target.read_bytes(), b"patched")
                with self.assertRaises(ValueError):
                    NS["create_copy"](source, target)
            self.assertEqual(source.read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
