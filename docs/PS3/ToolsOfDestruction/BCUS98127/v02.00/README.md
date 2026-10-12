# Tools of Destruction — USA v02.00

PS3 · USA · `BCUS98127` · supplied executable v02.00.

## Pages

| Page | Use |
| --- | --- |
| [Save format](../../SaveFormat.md) | File layout, offsets, field types and unknowns |
| [Executable findings](ElfMap.md) | Native behavior, transaction ordering and non-save anchors |
| [Tools guide](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/README.md) | Inspect saves, compare captures and import into Ghidra/IDA |

## Data and evidence

- [NativeMap.json](maps/NativeMap.json): addresses, byte guards, catalogs and structures.
- [WeaponConfigs.json](maps/WeaponConfigs.json): shipped weapon/gadget definitions and modifiers.
- [Tests](../../../../../Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00): independent native/report and input-preservation checks.

The map contains 1,493 annotations, 45 structure definitions and 118 imports. These are inventory counts, not a completion percentage.

ELF SHA-256: `0EE9A8414C8FC182BC19FA2A523E6D050D0BE76138B3733AE515798D77D2468C`.

Addresses and byte guards apply to that binary only. Save behavior has been traced and tested in software; new edits have not been validated in-game. The [European sample](../../BCES00052/unknown/README.md) is separate evidence.
