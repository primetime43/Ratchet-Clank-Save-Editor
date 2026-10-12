"""Small detached-byte checks; no native execution, game assets or crypto subprocess."""
from pathlib import Path
import runpy
import struct
import unittest

ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "Ratchet And Clank Save Editor.sln").is_file())
RESEARCH = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGroovitronState.py"))


def snapshot():
    data = bytearray(0x906F0)
    for item in range(32):
        struct.pack_into(">I", data, item * 20, item)
    return data


class GroovitronStateChecks(unittest.TestCase):
    def test_separate_object_and_event_states(self):
        data = snapshot()
        struct.pack_into(">I", data, 0x330, 1)
        result = RESEARCH["saved_observation"](data)
        self.assertTrue(result["golden_object"]["current_nonzero_query"])
        self.assertFalse(result["golden_event286_set"])
        self.assertFalse(result["object_query_and_event_agree_in_snapshot"])
        struct.pack_into(">Q", data, 0x5548, 1 << 30)
        self.assertTrue(RESEARCH["saved_observation"](data)["golden_event286_set"])

    def test_query_uses_current_not_history(self):
        data = snapshot()
        struct.pack_into(">I", data, 0x38C, 1)
        struct.pack_into(">I", data, 0x3E8, 7)
        result = RESEARCH["saved_observation"](data)
        self.assertFalse(result["golden_object"]["current_nonzero_query"])
        self.assertEqual(result["golden_object"]["positive_additions"], 7)
        struct.pack_into(">I", data, 0x330, 0x80000000)
        self.assertTrue(RESEARCH["saved_observation"](data)["golden_object"]["current_nonzero_query"])

    def test_ammo_float_is_observed_not_normalized(self):
        data = snapshot()
        struct.pack_into(">f", data, 0x184, 2.5)
        before = bytes(data)
        self.assertEqual(RESEARCH["saved_observation"](data)["groovitron"]["ammo"], 2.5)
        self.assertEqual(bytes(data), before)
        struct.pack_into(">I", data, 0x184, 0x7FC00001)
        result = RESEARCH["saved_observation"](data)["groovitron"]
        self.assertIsNone(result["ammo"])
        self.assertEqual(result["ammo_bits"], "7FC00001")

    def test_layout_rejection(self):
        for data in (bytearray(16), bytearray(0x906F0)):
            with self.assertRaises(ValueError):
                RESEARCH["saved_observation"](data)


if __name__ == "__main__":
    unittest.main()
