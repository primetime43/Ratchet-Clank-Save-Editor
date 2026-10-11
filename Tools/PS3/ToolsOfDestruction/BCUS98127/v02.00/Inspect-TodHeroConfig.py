"""Read-only exact-build Hero XP/HP arrays and fingerprinted shipped config."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import runpy
import struct

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "Ratchet And Clank Save Editor.sln").is_file())
BINDINGS = runpy.run_path(str(Path(__file__).with_name("Inspect-TodWeaponBindings.py")))
PSARC = runpy.run_path(str(ROOT / "Tools/Inspect-Psarc.py"))
LUA = runpy.run_path(str(ROOT / "Tools/Inspect-Lua50.py"))
HASHES = {
    "/data/configs/hero.csv": "D40621A34C826C638CD0E5F40731EE42E28CAE25B45FF1EB16394AB0204DBC77",
    "/data/configs/hero.lua": "E6D43D5ED88691DB798026499EA1FEC07CE279760BC58FE971F6A9DE23EC2EEC",
    "/data/configs/hero.lc": "C835CD96E2EAA4F238AAF61E8FA38FF393BA364D9FEA96CA048042D22C6E25FF",
}


def parse_hero(raw):
    if len(raw) > 65536:
        raise ValueError("Hero CSV exceeds the bounded research size")
    parsed = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True))
    if len(parsed) > 1000 or any(len(r) > 64 or any(len(c) > 4096 for c in r) for r in parsed):
        raise ValueError("Hero CSV row/cell limits exceeded")
    active, result = False, []
    for row in parsed:
        if row and row[0] == "Hero":
            if active or row[1:3] != ["XP", "HP"]:
                raise ValueError("Missing/ambiguous Hero XP/HP header")
            active = True
            continue
        if not active or len(row) < 2 or not row[1]:
            continue
        if len(result) >= 100 or len(row) < 3 or not re.fullmatch(r"[0-9]+", row[1]) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", row[2]):
            raise ValueError("Expected at most100 literal Hero XP/HP rows")
        xp, hp = int(row[1]), float(row[2])
        if xp > 0xFFFFFFFF or not math.isfinite(hp) or hp > 0xFFFFFFFF:
            raise ValueError("Hero values outside the finite bounded domain")
        result.append({"index": len(result), "xp": xp, "hp": hp})
    if not result or result[0]["xp"] != 0:
        raise ValueError("Missing Hero table or nonzero initial XP")
    return result


def asset_report(archive_path):
    archive = PSARC["Psarc"](archive_path)
    payloads, fingerprints = {}, []
    for name, expected in HASHES.items():
        if archive.names.count(name) != 1:
            raise ValueError("Missing/ambiguous reference Hero asset")
        index = archive.names.index(name)
        if not archive.name_hashes_match[index - 1]:
            raise ValueError("Hero asset name digest mismatch")
        raw = archive.read_entry(index, 65536)
        digest = hashlib.sha256(raw).hexdigest().upper()
        if digest != expected:
            raise ValueError("Reference Hero asset hash mismatch: " + name)
        payloads[name] = raw
        fingerprints.append({"name": name, "bytes": len(raw), "sha256": digest})
    reader = LUA["Reader"](payloads["/data/configs/hero.lc"])
    function = reader.function()
    if reader.pos != len(reader.raw) or function["children"] or len(function["instructions"]) != 72:
        raise ValueError("Compiled Hero parser shape changed")
    constants = function["constants"]
    if constants != ['col_map', 'row_num', 0.0, 'ipairs', 'CONFIG_TABLE', 1.0, 'Hero', 2.0, None, 'string', 'len', 'variable', 'value', 'execute', 'config.Hero.', '[', '] = ', '; ']:
        raise ValueError("Compiled Hero parser constants changed")
    code_start = int(function["code_offset"], 0)
    code_end = code_start + 4 * len(function["instructions"])
    code_hash = hashlib.sha256(reader.raw[code_start:code_end]).hexdigest().upper()
    if code_hash != "987A1354800AA0BAE8D2C0EBE193ED50CBE26B8EFD6550C4C874591426E41D26":
        raise ValueError("Compiled Hero parser code changed")
    rows = parse_hero(payloads["/data/configs/hero.csv"])
    if len(rows) != 98 or rows[-1] != {"index": 97, "xp": 989000, "hp": 999.0}:
        raise ValueError("Reference Hero table changed")
    return {"confidence": "fingerprinted-reference-assets-with-named-native-array-bindings",
            "assets": fingerprints, "compiled_parser_code_sha256": code_hash,
            "parser_rule": "Header Hero selects XP/HP column names. Nonempty XP rows increment row_num from0; executable assignment string config.Hero.<column>[row_num] receives literal cells. Source and compiled72-instruction parser agree. No Lua or expressions are executed by this inspector.",
            "rows": rows, "populated_rows": 98, "unpopulated_native_indices": [98, 99],
            "qualification": "Shipped reference definitions, not captured runtime values. The old50-row designer note is stale;98 rows are populated. Blank-header designer tags are not parsed properties or pickup/world placements. Later overrides, installation and values of unpopulated indices98/99 are not proven by this table."}


def inspect(elf_path, save_path=None, archive_path=None):
    elf = BINDINGS["Elf"](elf_path)
    guards = {}
    def keep(address, size=4):
        guards[address] = elf.read(address, size)
    checks = {
        0x88FAFC: 0x101B9EE8, 0x897B00: 0x101B9EE8,
        0x88EA78: 0x10012FB0, 0x88EA7C: 0x85D538,
        0x88B2A4: 0x10006680, 0x88E6F4: 0x10012BA0, 0x88E6B8: 0x10012B78,
        0x88E8CC: 0x85E920, 0x88E8D0: 0x85E918,
        0x88E8D4: 0x85E910, 0x88E8D8: 0x85E908,
        0x99AB4: 0x7BC40020,
        0x8903C: 0x83C2E7BC, 0x88FBC: 0x82E2E780,
        0x894C8: 0x81C2B36C, 0x894D0: 0x7DC57378,
        0x894DC: 0x7DC47378, 0x894E8: 0x7DC47378,
        0x894F8: 0x7FC4F378, 0x89500: 0x80A2E994, 0x89504: 0x80C2E998,
        0x89510: 0x7EE4BB78, 0x89514: 0x80A2E99C, 0x89518: 0x80C2E9A0,
        0xB7850: 0x281D0063, 0xB7854: 0x40810010,
        0xB7878: 0x57A3103A, 0xB787C: 0xFC000E5E, 0xB7894: 0x7CEB312E,
        0xB7970: 0x281D0063, 0xB7984: 0x57A8103A,
        0xB7994: 0x7CCB382E, 0xB79A0: 0xFC00169C, 0xB79A4: 0xFC200018,
        0xB7628: 0x281D0063, 0xB762C: 0x40810010,
        0xB7650: 0x57A3103A, 0xB7654: 0x38E30190, 0xB7664: 0x7C2B352E,
        0xB7740: 0x281D0063, 0xB775C: 0x38E80190, 0xB7768: 0x7C2B342E,
        0x23E13C: 0x7CDD382E, 0x23E23C: 0x39440190, 0x23E244: 0x7D7D3C2E,
        0x23DBB0: 0x88031B61, 0x23DBB8: 0x2B800062, 0x23DBC8: 0x419D0050,
        0x23DBDC: 0x80E90418, 0x23DBE0: 0x7CCC5850, 0x23DBE4: 0x7CAC3850,
        0x23DBE8: 0x78C40020, 0x23DBEC: 0x78A30020, 0x23DC10: 0xEC206824,
        0x23DC18: 0xC0227BC4,
    }
    for address, expected in checks.items():
        if elf.u32(address) != expected:
            raise ValueError(f"Hero config evidence changed at {address:#x}")
        keep(address)
    for address, expected in ((0x10012FB0, "Hero"), (0x10006680, "HeroConfig"), (0x10012BA0, "XP"), (0x10012B78, "HP")):
        if elf.string(address) != expected:
            raise ValueError("Hero config identifier changed")
        keep(address, len(expected) + 1)
    bindings = []
    for name, offset, getter, setter, get_slot, set_slot in (
            ("XP", 0, 0xB78C8, 0xB77A8, 0x88E8CC, 0x88E8D0),
            ("HP", 0x190, 0xB7698, 0xB7580, 0x88E8D4, 0x88E8D8)):
        for slot, function in ((get_slot, getter), (set_slot, setter)):
            descriptor = elf.u32(slot)
            if struct.unpack(">II", elf.read(descriptor, 8)) != (function, 0x88FF38):
                raise ValueError("Hero array function descriptor changed")
            keep(descriptor, 8)
            end = elf.functions[elf.functions.index(function) + 1]
            keep(function, end - function)
        bindings.append({"name": name, "offset": hex(offset), "count": 100,
                         "element_type": "u32" if name == "XP" else "f32",
                         "getter_va": hex(getter), "setter_va": hex(setter)})
    for address, target in ((0x894E0, 0x12A00), (0x894F0, 0x10FC0),
                            (0x89508, 0x12C80), (0x89520, 0x12C80), (0x99AB8, 0x104D0)):
        word = elf.u32(address)
        if not word & 1 or BINDINGS["branch_target"](word, address) != target:
            raise ValueError("Hero config registration call changed")
        keep(address)
    if struct.unpack(">II", elf.read(0x85D538, 8)) != (0x99A70, 0x88FF38):
        raise ValueError("Hero subobject getter descriptor changed")
    keep(0x85D538, 8)
    keep(0x99A70, elf.functions[elf.functions.index(0x99A70) + 1] - 0x99A70)
    keep(0x23DBB0, 0x70)
    report = {
        "confidence": "named-native-array-and-consumer-backed-exact-build",
        "warning": "USA v02.00 static bindings/reference definitions only; no safe edits or observed runtime level/current health. Runtime config arrays are not GAME.SAV offsets.",
        "root": {"va": "0x101b9ee8", "root_getter_va": "0x94400", "hero_getter_va": "0x99a70", "hero_offset": "0x0",
                 "rule": "MonolithicConfig.Hero getter passes the same parent pointer as HeroConfig; array registration in HeroConfig scope pairs the XP/HP names with distinct indexed callbacks. Scalar same-name properties in another class are not these arrays."},
        "arrays": bindings,
        "conversion": "Normal indices0..99: XP setter fctidz/stwx publishes truncated low32; XP getter zero-extends lwzx then fcfid/frsp. HP setter/getter stfsx/lfsx use offset190. Unsigned index>99 invokes an error helper; no clamp or safety if that helper returns is inferred.",
        "consumer": "Hero progression23E090 reads XP[level+1] and qualified HP[level] at190+4*level, matching the named arrays. Shipped definitions may supply numbers, but live installation/overrides and callbacks are not captured.",
        "progress_fraction": {"va": "0x23dbb0", "rule": "For runtime level<=98, numerator=(saved418-XP[level]) modulo32 and denominator=(XP[level+1]-XP[level]) modulo32; convert each through frsp and fdivs. No0..1 clamp or zero-denominator repair. Level>=99 returns literal1.0. Runtime level and current table must be supplied; this is not computed from a save alone."},
        "recommended_annotations": [
            {"va": hex(function), "name": "TOD_HeroConfig_" + name + "_array_" + action,
             "comment": name + " indexed HeroConfig " + action + "; normal indices0..99, offset" + hex(offset) + ", stride4. Runtime configuration, not serialized save state. Same-name scalar properties belong to a different class."}
            for name, offset, getter, setter, _, _ in (("XP", 0, 0xB78C8, 0xB77A8, 0, 0), ("HP", 0x190, 0xB7698, 0xB7580, 0, 0))
            for function, action in ((getter, "getter"), (setter, "setter"))],
        "instruction_guards": [{"va": hex(a), "bytes": b.hex().upper()} for a, b in sorted(guards.items())],
    }
    assets = asset_report(archive_path) if archive_path is not None else None
    if assets is not None:
        report["asset_observation"] = assets
    if save_path is not None:
        data = Path(save_path).read_bytes()
        if len(data) != 0x906F0 or any(struct.unpack_from(">I", data, i * 20)[0] != i for i in range(32)):
            raise ValueError("Not the verified plaintext layout")
        xp = struct.unpack_from(">I", data, 0x418)[0]
        passed = [r for r in assets["rows"] if r["xp"] <= xp] if assets is not None else []
        report["save_observation"] = {"saved_xp": xp, "plaintext_sha256": hashlib.sha256(data).hexdigest().upper(),
            "reference_thresholds_met": len(passed) if assets is not None else None,
            "highest_reference_row_met": passed[-1] if passed else None,
            "runtime_level": None, "current_health": None,
            "qualification": "Reference threshold comparison only, not observed runtime level/current health or gameplay reload. Config installation, two unpopulated entries and later overrides remain unknown."}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--save", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.elf, args.save, args.archive), indent=2, allow_nan=False))
