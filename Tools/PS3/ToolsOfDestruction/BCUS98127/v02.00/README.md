# Tools of Destruction research tools

[Wiki](../../../../../docs/PS3/ToolsOfDestruction/README.md) · [Save offsets](../../../../../docs/PS3/ToolsOfDestruction/SaveFormat.md) · [USA v02.00 findings](../../../../../docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/ElfMap.md)

Run commands from the repository root. Native inspectors require the exact `BCUS98127 v02.00 EBOOT.ELF`; save arguments refer to a **decrypted copy**, not the encrypted original. Reports are read-only unless an output or database import is explicitly requested. Keep generated reports under ignored `artifacts/`.

## Inspect or compare a save

The game-level PowerShell tools require PowerShell 7.2 or later.

```powershell
./Tools/PS3/ToolsOfDestruction/Inspect-TodSave.ps1 -SourceFolder "path/to/plaintext-save-folder"
./Tools/PS3/ToolsOfDestruction/Compare-TodSaves.ps1 -BeforeFile "before/GAME.SAV" -AfterFile "after/GAME.SAV"
```

[Inspect-TodSave.ps1](../../Inspect-TodSave.ps1) reports game records, metadata headers, artwork headers and unknown ranges. It refuses unfamiliar/encrypted game prefixes; it does not decrypt them. Optional `-OutputFile` must name a new file outside the source folder.

[Compare-TodSaves.ps1](../../Compare-TodSaves.ps1) writes JSON to stdout. It reports field/range changes without editing either input or reading account metadata. Both saves must have the verified plaintext layout. Differences establish correlation, not the cause of a gameplay event.

## Inspect native evidence

Most Python inspectors accept `--elf` and optional `--save`. WeaponBindings takes a positional ELF path; WeaponConfigs takes an extracted asset-directory path. Use `--help` for each tool's asset/archive requirements.

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodObjects.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-GAME.SAV"
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodObjects.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-GAME.SAV" -v
```

Each inspector checks binary identity and native evidence. Neighboring `TestTod*.py` files cover report reproduction, bounds and raw-value preservation. Detached arithmetic previews do not execute native code, Lua or callbacks.

### Where to start

| Subject | Inspectors |
| --- | --- |
| Inventory/definitions | [WeaponBindings](Inspect-TodWeaponBindings.py), [WeaponConfigs](Inspect-TodWeaponConfigs.py), [InventoryQueries](Inspect-TodInventoryQueries.py) |
| Ammo/XP/upgrades | [WeaponProgression](Inspect-TodWeaponProgression.py), [WeaponLevels](Inspect-TodWeaponLevels.py), [GadgetAmmo](Inspect-TodGadgetAmmo.py), [AmmoCapacity](Inspect-TodAmmoCapacity.py), [AmmoCrate](Inspect-TodAmmoCrate.py), [UpgradeCandidates](Inspect-TodUpgradeCandidates.py), [UpgradePurchase](Inspect-TodUpgradePurchase.py). `--assets` uses the six extracted reference files; UpgradeCandidates also needs `--vendor-asset`. |
| Equipment and objects | [Objects](Inspect-TodObjects.py), [ObjectGrantProducers](Inspect-TodObjectGrantProducers.py), [InventoryAux](Inspect-TodInventoryAux.py), [EquipmentLifecycle](Inspect-TodEquipmentLifecycle.py) |
| Linked consumables/specials | [GroovitronState](Inspect-TodGroovitronState.py): separate object/event and activation evidence; [SpecialModifiers](Inspect-TodSpecialModifiers.py): type/mask query and Predator repeat-target gate |
| Quick-select eligibility | [QuickSelectEligibility](Inspect-TodQuickSelectEligibility.py): all32 initializer flags, registry linkage and detached first24 edit plans |
| Player progression | [Progression](Inspect-TodProgression.py), [HeroXpFlow](Inspect-TodHeroXpFlow.py), [HeroConfig](Inspect-TodHeroConfig.py), [HealthPersistence](Inspect-TodHealthPersistence.py) |
| Collectibles/bonuses | [Collectibles](Inspect-TodCollectibles.py), [CollectibleProducers](Inspect-TodCollectibleProducers.py), [Bonuses](Inspect-TodBonuses.py), [BonusSelection](Inspect-TodBonusSelection.py): physical choices; `--archive` verifies shipped menu cycling |
| Worlds/missions | [WorldState](Inspect-TodWorldState.py), [GameplaySegments](Inspect-TodGameplaySegments.py), [Missions](Inspect-TodMissions.py), [SegmentConfig](Inspect-TodSegmentConfig.py) |
| Events/arena | [GlobalFlags](Inspect-TodGlobalFlags.py), [ResetCategories](Inspect-TodResetCategories.py), [ArenaChallenges](Inspect-TodArenaChallenges.py), [ArenaTable](Inspect-TodArenaTable.py) |
| Maps | [StateStorage](Inspect-TodStateStorage.py), [PersistentGrid](Inspect-TodPersistentGrid.py), [GridGeometry](Inspect-TodGridGeometry.py) |
| Settings | [Settings](Inspect-TodSettings.py), [SettingsApply](Inspect-TodSettingsApply.py), [SettingsMenu](Inspect-TodSettingsMenu.py) |
| Item artwork | [HudIcons](Inspect-TodHudIcons.py): `--archive` checks compiled pause-menu icon assignments, named image references and identical HUD BC3 payloads; metadata only, no game execution or extraction. |
| Save/reset/unknowns | [SnapshotLifecycle](Inspect-TodSnapshotLifecycle.py), [SaveTail](Inspect-TodSaveTail.py), [WorldAux](Inspect-TodWorldAux.py), [FinalTail](Inspect-TodFinalTail.py) |

The [full directory](.) contains the more specialized inspectors. [The evidence index](../../../../../docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/ElfMap.md#evidence-index) lists their map sections. Generic [PSARC inspection](../../../../../Tools/Inspect-Psarc.py) and [Lua inspection](../../../../../Tools/Inspect-Lua50.py) tools stay at the Tools root.

## Developer research

[Inspect-TodDeveloperHelpers.py](Inspect-TodDeveloperHelpers.py) checks sixteen bounded native function hashes, Lua registration and grant guards in the original ELF. Original-address annotations remain available for IDA and Ghidra.

The [findings](../../../../../docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/ElfMap.md#developer-helpers-and-lua-debug) cover the working Lua console, live helper availability and debug-asset contents. No original on-screen developer menu was recovered.

Experimental ELF builders, memory clients and the isolated RPCS3 test profile have been removed. Save-side blueprint and bonus actions remain in the editor; see [Usage](../../../../../docs/Usage.md).

## Ghidra

Use `PowerPC:BE:64:64-32addr`, compiler `default`, and original ELF addresses. Add this directory's `Ghidra/` folder to Script Manager.

For a **new project**, [PrepareTod.java](Ghidra/PrepareTod.java) must run before analysis: it seeds descriptor functions and their three TOCs. Then run [ImportTodMap.java](Ghidra/ImportTodMap.java) with [NativeMap.json](../../../../../docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json).

```powershell
# Set these variables to your local paths; create the project directory first.
& "$GhidraRoot/support/analyzeHeadless.bat" $ProjectDirectory TodResearch `
  -import $ElfPath -processor PowerPC:BE:64:64-32addr -cspec default `
  -scriptPath "$RepoRoot/Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Ghidra" `
  -preScript PrepareTod.java `
  -postScript ImportTodMap.java "$RepoRoot/docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json"
```

Imports add `TOD_` labels, comments and types to the analysis database. They validate hashes/signatures, preserve custom work and do not patch executable bytes. Types are added under `/RatchetClank/ToolsOfDestruction`, not automatically applied to every global. The unmapped third TOC base is retained in JSON but skipped as a label.

### Trace or validate an existing project

Use `-readOnly -noanalysis` for checks that should not save database changes. Never run two headless jobs against the same project at once.

```powershell
& "$GhidraRoot/support/analyzeHeadless.bat" $ProjectDirectory TodResearch `
  -process EBOOT.ELF -readOnly -noanalysis `
  -scriptPath "$RepoRoot/Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Ghidra" `
  -postScript TraceTodSave.java "$RepoRoot/artifacts/tod-trace-new" f:0x35E710 r:0x35E710
```

[TraceTodSave.java](Ghidra/TraceTodSave.java) requires a fresh output directory and supports:

| Query | Result |
| --- | --- |
| `f:<VA>` | Function assembly/decompilation |
| `r:<VA>` | References and TOC leads |
| `d:<VA>:<hex-size>` | Data bytes |
| `n:<VA>:<decimal-count>` | Nearby functions; count is functions, not instructions |
| `i:<hex-immediate>` | Instruction-immediate scan |

[SurveyTod.java](Ghidra/SurveyTod.java) exports broader string/descriptor leads. Confirm TOC-changing thunks in assembly before treating a lead as resolved.

To validate imports, replace the postScript with `TestTodMap.java "<path/to/NativeMap.json>"`. [TestTodMap.java](Ghidra/TestTodMap.java) checks mapped annotations, structures, repeat-import behavior and custom-name/comment preservation.

## IDA

Load the matching ELF as big-endian PowerPC at its original addresses. Choose **File → Script file**, run [import_tod_map.py](IDA/import_tod_map.py), then select NativeMap.json.

The importer adds names, repeatable comments and local types without changing binary bytes. It targets IDA 9, does not configure PS3 TOCs automatically and has **not been tested in live IDA**; current checks cover mocked database safety and map validation.

## Verification

The [manual regression workflow](../../../../../.github/workflows/regression.yml) runs the Windows app fixtures and portable research checks on GitHub. Use **Actions → Regression checks (manual) → Run workflow** after pushing it. Original ELF, asset and private-save checks are not included; they need the local research corpus. Nothing runs automatically on pushes.

```powershell
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodElfMap.py --elf "path/to/EBOOT.ELF" -v
python -B Tests/TestResearchOrganization.py
dotnet run --project Tests/SaveEditor.RegressionTests.csproj -c Release
```

Optional actual-save checks: append `-- --tod-save "path/to/save-folder"` to the .NET command. They load the source read-only and use disposable copies for edit/encrypt/reopen tests.

Asset-specific checks require the original archive or extracted matching assets. Pass those only where the tool's help requests them. No game binaries, private saves or raw assets are tracked. Software tests are not a substitute for controlled in-game before/after captures.
