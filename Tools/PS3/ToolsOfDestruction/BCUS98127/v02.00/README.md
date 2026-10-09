# Tools of Destruction research tools — PS3 / USA / v02.00

These tools correspond to the exact `BCUS98127` executable and assets documented in the [build index](../../../../../docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/README.md). Native inspectors check the executable identity/byte evidence and inspect optional plaintext working copies read-only.

- `Inspect-TodWeaponBindings.py` and `Inspect-TodWeaponConfigs.py`: native bindings and packed configuration definitions.
- [Inspect-TodGameplaySegments.py](Inspect-TodGameplaySegments.py): ten saved gameplay segments per world, named completion flag, timers, integer reset-event count, reward accumulators and the200-slot retained statistics log. Distinguishes saved count from stale buffer contents; never edits sources.
- [Inspect-TodWorldObjectFlags.py](Inspect-TodWorldObjectFlags.py): two2048-bit per-world object bitsets, exact BE64 slot ordering, object-state restore paths and mode-qualified spawn suppression. Runtime object names/UID mapping remain unresolved; snapshots are read-only.
- [Inspect-TodResetCategories.py](Inspect-TodResetCategories.py): eight reset-event category counters, native selectors2–7 and temporary runtime countdown/strict expiration. Player-facing names and time units remain unknown; no inferred death total or save writes.
- `Inspect-TodProgression.py`, `Inspect-TodCollectibles.py`, `Inspect-TodWorldState.py`, `Inspect-TodObjects.py`, `Inspect-TodMissions.py`, `Inspect-TodBonuses.py`, `Inspect-TodStateStorage.py`, `Inspect-TodSettings.py`: mapped state and sample checks.
- [Ghidra importer](Ghidra/ImportTodMap.java) and [IDA importer](IDA/import_tod_map.py): annotations for an analysis database, not binary edits.
- [Inspect-TodArenaChallenges.py](Inspect-TodArenaChallenges.py): direct native challenge IDs, saved win counters, shipped descriptions/restrictions/rewards and guarded runtime ArenaConfig properties. Requires the exact ELF and extracted `arena.csv`, `arena.lua`, `arena.lc`; scripts are never executed.
- [Inspect-TodGlobalFlags.py](Inspect-TodGlobalFlags.py):292 global event IDs independently exported twice, five saved BE64 words,28 unnamed physical tail bits and the HERO_HAS_TWO_ITEMS acquisition dependency. Reports are read-only; Set/Clear is not a story-completion verdict.

See the [executable notes](../../../../../docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/ElfMap.md) for commands. Shared save inspection/comparison scripts live [at the game level](../../); generic PSARC and Lua readers remain at the `Tools/` root.
