# Tools of Destruction research tools — PS3 / USA / v02.00

These tools correspond to the exact `BCUS98127` executable and assets documented in the [build index](../../../../../docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/README.md). Native inspectors check the executable identity/byte evidence and inspect optional plaintext working copies read-only.

- `Inspect-TodWeaponBindings.py` and `Inspect-TodWeaponConfigs.py`: native bindings and packed configuration definitions.
- `Inspect-TodProgression.py`, `Inspect-TodCollectibles.py`, `Inspect-TodWorldState.py`, `Inspect-TodObjects.py`, `Inspect-TodMissions.py`, `Inspect-TodBonuses.py`, `Inspect-TodStateStorage.py`, `Inspect-TodSettings.py`: mapped state and sample checks.
- [Ghidra importer](Ghidra/ImportTodMap.java) and [IDA importer](IDA/import_tod_map.py): annotations for an analysis database, not binary edits.

See the [executable notes](../../../../../docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/ElfMap.md) for commands. Shared save inspection/comparison scripts live [at the game level](../../); generic PSARC and Lua readers remain at the `Tools/` root.
