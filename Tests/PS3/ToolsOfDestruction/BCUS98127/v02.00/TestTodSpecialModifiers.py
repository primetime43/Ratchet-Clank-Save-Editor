"""Small portable synthetic checks; the inspector verifies native/private inputs."""
from pathlib import Path
import runpy
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
NS = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSpecialModifiers.py"))


class SpecialModifierChecks(unittest.TestCase):
    def test_no_enabled_special(self):
        self.assertFalse(NS["special_preview"](0xFFFFFFFF, []))
        self.assertFalse(NS["special_preview"](1, [9, 16]))

    def test_special_requires_enabled_declared_type(self):
        self.assertTrue(NS["special_preview"](2, [9, 16]))
        self.assertFalse(NS["special_preview"](4, [9, 16]))
        self.assertFalse(NS["special_preview"](2, [16, 9]))

    def test_last_bounded_index(self):
        self.assertTrue(NS["special_preview"](1 << 23, [9] * 23 + [16]))
        self.assertFalse(NS["special_preview"](1 << 31, [16] * 24))

    def test_invalid_inputs(self):
        for mask, types in ((-1, []), (1 << 32, []), (True, []), (0, [16] * 25), (0, [True]), (0, [-1])):
            with self.assertRaises(ValueError):
                NS["special_preview"](mask, types)

    def test_seven_unique_positive_special_nodes(self):
        self.assertEqual(len(NS["CATALOG"]), 7)
        self.assertEqual(len({item[0] for item in NS["CATALOG"]}), 7)
        self.assertTrue(all(0 < item[2] < 24 for item in NS["CATALOG"]))


if __name__ == "__main__":
    unittest.main()
