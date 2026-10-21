# European RC1 native research tools

[Native findings](../../../../../docs/PS3/RatchetAndClank1/NPEA00385/unknown/ElfMap.md) · [Save format](../../../../../docs/PS3/RatchetAndClank1/SaveFormat.md)

Commands run from the repository root. Requires Python 3; no third-party Python packages are needed. Executable and save inputs are read-only. Original game binaries are not bundled. Store local binaries, Ghidra projects and generated reports under ignored `artifacts/`.

```powershell
python -B Tools/PS3/RatchetAndClank1/NPEA00385/unknown/Inspect-Rc1Native.py --elf "path/to/RC1.ppu.elf"
python -B Tests/PS3/RatchetAndClank1/NPEA00385/unknown/TestRc1Native.py --elf "path/to/RC1.ppu.elf" -v
```

The inspector validates the complete ELF SHA-256 and 13 native function fingerprints, then extracts player descriptors, ammo capacities, starting ammo, acquisition membership, item types and notification selectors. These establish the 12-item grant allowlist and quick-select storage. Its JSON matches the [bundled map](../../../../../docs/PS3/RatchetAndClank1/NPEA00385/unknown/maps/NativeMap.json). Tests also reject truncated and altered ELF inputs.

For Ghidra, import the ELF with language `PowerPC:BE:64:64-32addr` and compiler `default`. Run [TraceRc1Ammo.java](Ghidra/TraceRc1Ammo.java) with a report output path. It validates the executable, sets TOC `0x722328` and decompiles selected save, ammo, grant, vendor and quick-select routines. The report explicitly identifies the grant helper's partly decoded Cell-vector notification path; supported grants bypass it. The script writes only an analysis database and the requested report, without patching the executable. Use Ghidra's `-noanalysis` and `-postScript` options to reproduce the selected trace without waiting for whole-program analysis.
