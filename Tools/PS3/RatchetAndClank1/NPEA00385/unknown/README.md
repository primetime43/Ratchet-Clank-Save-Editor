# European RC1 native research tools

[Native findings](../../../../../docs/PS3/RatchetAndClank1/NPEA00385/unknown/ElfMap.md) · [Save format](../../../../../docs/PS3/RatchetAndClank1/SaveFormat.md)

Commands run from the repository root. Requires Python 3; no third-party Python packages are needed. Executable and save inputs are read-only. Original game binaries are not bundled. Store local binaries, Ghidra projects and generated reports under ignored `artifacts/`.

```powershell
python -B Tools/PS3/RatchetAndClank1/NPEA00385/unknown/Inspect-Rc1Native.py --elf "path/to/RC1.ppu.elf"
python -B Tests/PS3/RatchetAndClank1/NPEA00385/unknown/TestRc1Native.py --elf "path/to/RC1.ppu.elf" -v
python -B Tools/PS3/RatchetAndClank1/NPEA00385/unknown/Inspect-Rc1GoldPickups.py --elf "path/to/RC1.ppu.elf" --archive "path/to/rc1/ps3data/PS3arc.psarc"
```

The inspector validates the complete ELF SHA-256 and 34 native function fingerprints, then extracts player/world descriptors, ammo capacities, starting ammo, acquisition membership, item types, notification selectors, gadget/equipment paths, forty gold-bolt slots and the gold-upgrade vendor table/limits. It audits all 35 notification-path instructions and their two helper calls, distinguishing Cell vector reads from runtime writes outside serialized records. It also checks all eleven instruction words of the pickup flag-store block. Its JSON matches the [bundled map](../../../../../docs/PS3/RatchetAndClank1/NPEA00385/unknown/maps/NativeMap.json). Tests reject truncated/altered ELF inputs, unexpected stores/calls, saved-address overlap, changed world/count tables and unknown inventory paths.

[Inspect-Rc1GoldPickups.py](Inspect-Rc1GoldPickups.py) independently verifies actual slot IDs in all nineteen PAL level assets against the native count map. It uses the shared [PSARC reader](../../../../Inspect-Psarc.py), now supporting bounded LZMA-alone blocks as well as zlib. The tool reads only bounded gameplay payloads into memory, follows checked actor/PVAR offsets, rejects duplicate/out-of-range slots and reports archive/per-asset SHA-256. No extraction to the game directory or binary modification occurs. Add `--archive "path/to/PS3arc.psarc"` to the native test command to run the optional actual-asset check; synthetic asset-parser checks always run.

For Ghidra, import the ELF with language `PowerPC:BE:64:64-32addr` and compiler `default`. Run [TraceRc1Ammo.java](Ghidra/TraceRc1Ammo.java) with a report output path. It validates the executable, sets TOC `0x722328` and decompiles selected save, inventory, collectible and notification routines. Ghidra still truncates the grant and pickup actors at Cell vector loads; the Python audits verify the separately documented blocks without patching instructions or executing game code. The script writes only an analysis database and the requested report. Use Ghidra's `-noanalysis` and `-postScript` options to reproduce the selected trace without waiting for whole-program analysis.
