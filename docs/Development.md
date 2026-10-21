# Build and test

[Main README](../README.md)

Requires Windows and the .NET 10 SDK.

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

The .NET runner covers save formats, backups, encryption, rollback, metadata bindings and the UI. The Python check validates documentation links and embedded resource paths.

To include an actual Tools of Destruction save, append `-- --tod-save "path/to/save-folder"` to the .NET command. Source files are read-only; edit/reopen tests use disposable copies.

Optional public integration samples:

```powershell
./Tests/FetchCompatibilitySamples.ps1
dotnet run --project Tests/SaveEditor.RegressionTests.csproj -c Release -- --samples artifacts/compatibility
```

Downloads use pinned hashes and stay under ignored `artifacts/`. These are software round-trip tests, not in-game acceptance tests.

Native reverse-engineering checks are covered in the [research tools guide](../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/README.md).
