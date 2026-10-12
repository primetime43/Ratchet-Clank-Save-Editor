# Ratchet & Clank: Tools of Destruction

PS3 save-format and executable research.

## Read the wiki

- [Save format](SaveFormat.md): file layout, field tables and known gaps.
- [USA v02.00 findings](BCUS98127/v02.00/ElfMap.md): how the game reads, changes and restores those fields.
- [Tools guide](../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/README.md): save inspection, comparisons, Ghidra and IDA.

The map covers inventory, currency, equipment, collectibles, missions, event flags, arena counters, settings and compressed map grids. Some field meanings and runtime relationships remain unknown. The editor's research views are read-only.

## Regions and builds

| Region | Title ID | Executable | Evidence |
| --- | --- | --- | --- |
| USA | `BCUS98127` | v02.00 | [ELF, matching assets and encrypted save](BCUS98127/v02.00/README.md) |
| Europe | `BCES00052` | Unknown | [Plaintext save sample](BCES00052/unknown/README.md) |

A build folder identifies the supplied executable, not a save-header or editor version. Findings are not automatically portable to other regions.

## Verification

[Native tests](../../../Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00) reproduce map evidence from the matching ELF. [Organization checks](../../../Tests/TestResearchOrganization.py) check wiki links and embedded resource paths.

The [PowerShell survey](../../../Tools/PS3/ToolsOfDestruction/Inspect-TodSave.ps1) and [comparison](../../../Tools/PS3/ToolsOfDestruction/Compare-TodSaves.ps1) have [survey tests](../../../Tests/PS3/ToolsOfDestruction/TestTodSaveInspector.ps1) and [comparison tests](../../../Tests/PS3/ToolsOfDestruction/TestTodSaveComparison.ps1) tied to the European reference sample. Those expected values are sample-specific.

Software round-trip tests use disposable copies. Controlled in-game captures and acceptance tests are still needed for new editable fields.
