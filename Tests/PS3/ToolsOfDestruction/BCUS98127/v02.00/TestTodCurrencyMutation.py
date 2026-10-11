"""Exact currency mutation evidence and immutable bounded arithmetic checks."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
TOOL = runpy.run_path(str(ROOT / "Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodCurrencyMutation.py"))
ELF, SAVE = None, None


def fixture():
    data = bytearray(0x906F0)
    for index in range(32):
        struct.pack_into(">I", data, index*20, index)
    return data


class CurrencyMutationChecks(unittest.TestCase):
    def native(self):
        if ELF is None:
            self.skipTest("Pass --elf for exact-build verification")
        return TOOL["inspect"](ELF)

    def test_reproduces_map(self):
        report = self.native()
        mapping = json.loads((ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json").read_text(encoding="utf-8"))
        self.assertEqual(report, mapping["currency_mutation"])

    def test_exact_guarded_cap_routes_and_runtime_pointers(self):
        report = self.native()
        self.assertEqual(report["hero_wallet_mutation"]["cap_constant"], 999999999)
        self.assertEqual(report["reward_wallet_mutation"]["runtime_root_va"], "0x10330740")
        self.assertIn("NOT serialized", report["reward_wallet_mutation"]["counter_scope"])
        elf = TOOL["BINDINGS"]["Elf"](ELF)
        for guard in report["instruction_guards"]:
            raw = bytes.fromhex(guard["bytes"])
            self.assertEqual(elf.read(int(guard["va"],0), len(raw)), raw)

    def test_ordinary_upper_selection_and_equality(self):
        preview, cap = TOOL["hero_wallet_preview"], TOOL["CAP"]
        self.assertEqual(preview(100,50)["wallet_bits"],150)
        self.assertEqual(preview(cap-1,1)["wallet_bits"],cap)
        self.assertFalse(preview(cap-1,1)["selected_cap"])
        self.assertTrue(preview(cap-1,2)["selected_cap"])
        self.assertEqual(preview(cap-1,2)["wallet_bits"],cap)

    def test_deduction_has_no_lower_clamp_and_retains_high_bits(self):
        preview = TOOL["hero_wallet_preview"]
        self.assertEqual(preview(100,(-50)&0xFFFFFFFF)["wallet_bits"],50)
        self.assertEqual(preview(0,0xFFFFFFFF)["wallet_bits"],0xFFFFFFFF)
        self.assertEqual(preview(0xFFFFFFFF,0)["wallet_bits"],0xFFFFFFFF)
        self.assertEqual(preview(0xFFFFFFFF,1)["wallet_bits"],0)

    def test_wrapped_difference_sign_is_not_universal_saturation(self):
        preview, cap = TOOL["hero_wallet_preview"], TOOL["CAP"]
        self.assertEqual(preview(0,0x80000000)["wallet_bits"],cap)
        self.assertEqual(preview(cap,0x7FFFFFFF)["wallet_bits"],cap)
        self.assertEqual(preview(cap,0x80000000)["wallet_bits"],cap)
        raw = (cap+0x80000001)&0xFFFFFFFF
        self.assertEqual(preview(cap,0x80000001)["wallet_bits"],raw)
        self.assertFalse(preview(cap,0x80000001)["selected_cap"])

    def test_reward_and_hero_routes_differ_and_reward_counters_independent(self):
        hero, reward, cap = TOOL["hero_wallet_preview"], TOOL["reward_wallet_preview"], TOOL["CAP"]
        self.assertEqual(hero(cap,1)["wallet_bits"],cap)
        result = reward(cap,100,1)
        self.assertEqual(result["wallet_bits"],cap+1)
        self.assertEqual(result["runtime_counter_bits"],101)
        self.assertEqual(result["store_order"],["runtime counter","saved wallet"])
        self.assertEqual(reward(0,0xFFFFFFFF,1)["runtime_counter_bits"],0)
        self.assertEqual(reward(0xFFFFFFFF,5,1)["wallet_bits"],0)
        self.assertEqual(reward(0,5,0xFFFFFFFF)["wallet_bits"],0xFFFFFFFF)

    def test_finite_reward_conversion_truncates_toward_zero(self):
        preview = TOOL["reward_word_preview"]
        for bits, expected in ((0x3FE00000,1),(0xBFE00000,-1),(0x3F400000,0),(0xBF400000,0),(0x80000000,0)):
            result = preview(bits)
            self.assertEqual(result["converted_signed64"],expected)
            self.assertEqual(result["delta_bits"],expected&0xFFFFFFFF)
            self.assertEqual(result["leaf_call_requested"],expected != 0)

    def test_low32_nonzero_gate_not_full64_or_positivity(self):
        preview = TOOL["reward_word_preview"]
        result = preview(0x4F800000)  # float32 2^32
        self.assertEqual(result["converted_signed64"],1<<32)
        self.assertEqual(result["delta_bits"],0)
        self.assertFalse(result["leaf_call_requested"])
        self.assertEqual(preview(0x4F800001)["delta_bits"],512)
        result = preview(0xCF800001)
        self.assertEqual(result["delta_bits"],(-512)&0xFFFFFFFF)
        self.assertTrue(result["leaf_call_requested"])

    def test_nonfinite_overflow_and_invalid_raw_inputs_rejected(self):
        for value in (True,-1,1<<32,1.0,None):
            for name,args in (("hero_wallet_preview",(value,0)),("reward_wallet_preview",(0,value,0)),("reward_word_preview",(value,))):
                with self.assertRaises(ValueError):
                    TOOL[name](*args)
        for value in (0x7F800000,0xFF800000,0x7FC00001,0x5F000000,0xDF000001):
            with self.assertRaises(ValueError):
                TOOL["reward_word_preview"](value)
        self.assertEqual(TOOL["reward_word_preview"](0xDF000000)["converted_signed64"],-(1<<63))

    def test_cache_debit_full_amount_and_unsigned_vs_signed_sources(self):
        report = self.native()["pickup_runtime_debit"]
        self.assertIn("FULL reread",report["sharper_rule"])
        self.assertIn("not the actual difference",report["sharper_rule"])
        self.assertIn("unsigned32",report["bolts_order"])
        self.assertIn("sign-extend",report["raritanium_order"])
        self.assertIn("before actor gate",report["raritanium_order"])
        self.assertEqual(TOOL["hero_wallet_preview"](TOOL["CAP"]-1,100)["wallet_bits"],TOOL["CAP"])

    def test_detached_observation_preserves_unusual_wallet_bits(self):
        if ELF is None:
            self.skipTest("Pass --elf")
        data = fixture()
        struct.pack_into(">II",data,0x41C,0xFFFFFFFF,0x80000000)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"synthetic.bin"
            path.write_bytes(data)
            before = path.read_bytes()
            observation = TOOL["inspect"](ELF,path)["save_observation"]
            self.assertEqual(observation["wallets"]["bolts"]["unsigned32"],0xFFFFFFFF)
            self.assertEqual(observation["wallets"]["bolts"]["signed32"],-1)
            self.assertEqual(observation["wallets"]["raritanium"]["signed32"],-(1<<31))
            self.assertEqual(path.read_bytes(),before)
            path.write_bytes(data[:-1])
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF,path)
            data[0:4] = b"BAD!"
            path.write_bytes(data)
            with self.assertRaises(ValueError):
                TOOL["inspect"](ELF,path)

    def test_actual_snapshot_and_original_inputs_remain_unchanged(self):
        if ELF is None or SAVE is None:
            self.skipTest("Pass --elf and --save for detached actual snapshot")
        before = [hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in (ELF,SAVE)]
        observation = TOOL["inspect"](ELF,SAVE)["save_observation"]
        self.assertEqual(observation["plaintext_sha256"],"F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
        self.assertEqual(observation["wallets"]["bolts"]["bits_hex"],"0FD5CCF5")
        self.assertEqual(observation["wallets"]["raritanium"]["bits_hex"],"00A721E3")
        self.assertIn("No runtime",observation["scope"])
        self.assertEqual(before,[hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in (ELF,SAVE)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf",type=Path)
    parser.add_argument("--save",type=Path)
    args, remaining = parser.parse_known_args()
    ELF,SAVE = args.elf,args.save
    unittest.main(argv=[__file__]+remaining)
