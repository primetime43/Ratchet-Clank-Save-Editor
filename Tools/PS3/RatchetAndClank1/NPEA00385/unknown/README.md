# European RC1 native research tools

[Native findings](../../../../../docs/PS3/RatchetAndClank1/NPEA00385/unknown/ElfMap.md) · [Save format](../../../../../docs/PS3/RatchetAndClank1/SaveFormat.md)

Commands run from the repository root. Requires Python 3; no third-party Python packages are needed. Executable and save inputs are read-only. Original game binaries are not bundled. Store local binaries, Ghidra projects and generated reports under ignored `artifacts/`.

```powershell
python -B Tools/PS3/RatchetAndClank1/NPEA00385/unknown/Inspect-Rc1Native.py --elf "path/to/RC1.ppu.elf"
python -B Tests/PS3/RatchetAndClank1/NPEA00385/unknown/TestRc1Native.py --elf "path/to/RC1.ppu.elf" -v
```

The inspector validates the complete ELF SHA-256 and 23 native function fingerprints, then extracts player descriptors, ammo capacities, starting ammo, acquisition membership, item types, notification selectors, gadget paths and the gold-upgrade vendor table/limits. It also audits all 35 notification-path instructions and their two helper calls, distinguishing Cell vector reads from runtime writes outside serialized records. These establish all 15 combat grants, nine gadget/passive grants, ten gold upgrades and quick-select storage. Its JSON matches the [bundled map](../../../../../docs/PS3/RatchetAndClank1/NPEA00385/unknown/maps/NativeMap.json). Tests reject truncated/altered ELF inputs, unexpected notification stores or call targets, saved-address overlap, disagreeing gold vendor/limit tables and unknown gadget type/ammo/acquisition paths.

For Ghidra, import the ELF with language `PowerPC:BE:64:64-32addr` and compiler `default`. Run [TraceRc1Ammo.java](Ghidra/TraceRc1Ammo.java) with a report output path. It validates the executable, sets TOC `0x722328` and decompiles selected save, ammo, grant, vendor, gadget-consumer, quick-select and notification-callee routines. Ghidra still truncates the grant helper at the Cell vector loads; the separate Python audit accounts for that entire block without patching instructions or executing game code. The script writes only an analysis database and the requested report. Use Ghidra's `-noanalysis` and `-postScript` options to reproduce the selected trace without waiting for whole-program analysis.
