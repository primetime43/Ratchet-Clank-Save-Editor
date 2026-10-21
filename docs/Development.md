# Build and test

[Main README](../README.md)

Requires Windows and the .NET 10 SDK.

## Source organization

Game-specific application code lives under `Ratchet & Clank Save Editor/Games/<GameName>/`. `Games/ToolsOfDestruction/` contains its editors, inventory previews, research helpers and inspection UI. Shared save sessions, profiles, encryption, metadata, numeric controls, theming and the main window remain at the application root.

Game-specific C# regression checks mirror that layout under `Tests/Games/<GameName>/`; shared UI and validation checks remain at the test root. The native research checks, tools and documentation retain their existing game/region/version folders under `Tests/PS3/`, `Tools/PS3/` and `docs/PS3/`.

## Build

```powershell
dotnet build "Ratchet And Clank Save Editor.sln" -c Release
```

Output: `Ratchet & Clank Save Editor/bin/Release/net10.0-windows/`. Framework-dependent builds require the .NET 10 Desktop Runtime.

## Standalone Windows x64 build

```powershell
dotnet publish "Ratchet & Clank Save Editor/Ratchet & Clank Save Editor.csproj" -c Release -r win-x64 --self-contained true -o artifacts/publish
```

This output includes the runtime.

## Tests

```powershell
dotnet run --project Tests/SaveEditor.RegressionTests.csproj -c Release
python -B Tests/TestResearchOrganization.py
```

On Windows 11, append `-- --dark-mode` to the .NET command to run the same checks and capture UI previews using the native dark theme.
Use `-- --theme-ui` (optionally followed by `--dark-mode`) for just numeric validation and UI rendering checks.
Use `-- --omega-promotions` for the promotion prerequisites, byte-preservation, ammo/upgrade composition, UI staging and backup/save/reopen checks; these also run in the full suite.
Use `-- --hero-xp-edits` for XP validation, reference HP and threshold previews, and progression-panel rendering; these also run in the full suite.

The .NET runner covers save formats, backups, encryption, rollback, metadata bindings and the UI. The Python check validates documentation links and embedded resource paths.

To include an actual Tools of Destruction save, append `-- --tod-save "path/to/save-folder"` to the .NET command. Source files are read-only; edit/reopen tests use disposable copies.

Optional public integration samples:

```powershell
./Tests/FetchCompatibilitySamples.ps1
dotnet run --project Tests/SaveEditor.RegressionTests.csproj -c Release -- --samples artifacts/compatibility
```

Downloads use pinned hashes and stay under ignored `artifacts/`. These are software round-trip tests, not in-game acceptance tests.

Native reverse-engineering checks are covered in the [research tools guide](../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/README.md).
