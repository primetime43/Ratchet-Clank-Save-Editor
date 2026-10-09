# Ratchet & Clank: Tools of Destruction — PS3

## Shared save research

- [Save format and sample evidence](SaveFormat.md): wrapper headers, game-state offsets, confidence levels and remaining unknowns. Each finding identifies its evidence; USA executable findings are not automatically confirmed for Europe.
- [Read-only save inspector](../../../Tools/PS3/ToolsOfDestruction/Inspect-TodSave.ps1)
- [Plaintext save comparison](../../../Tools/PS3/ToolsOfDestruction/Compare-TodSaves.ps1)

## Regions and versions

| Region | Title ID | Version | Research |
| --- | --- | --- | --- |
| USA | `BCUS98127` | `v02.00` | [Executable, assets and save observations](BCUS98127/v02.00/README.md) |
| Europe | `BCES00052` | Unknown | [Plaintext save sample only](BCES00052/unknown/README.md) |

Version folders identify the supplied executable build, not a save header version or the editor's version. Add other regions/builds separately when matching evidence is available.

## Tests

- [Save-inspector checks](../../../Tests/PS3/ToolsOfDestruction/TestTodSaveInspector.ps1) (`-SourceFolder`) and [save-comparison checks](../../../Tests/PS3/ToolsOfDestruction/TestTodSaveComparison.ps1) (`-SourceFile`) use the original European plaintext sample as their reference fixture. Some expected values are sample-specific; these are not tests for arbitrary saves.
- Native executable/configuration checks live under `Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/` and can use the matching USA ELF, plaintext working copy and extracted assets.
- [Organization checks](../../../Tests/TestResearchOrganization.py) verify documentation links, map-tool references and stable embedded resource names: `python -B Tests/TestResearchOrganization.py -v` from the repository root.
