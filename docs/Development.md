# Build and test

[Main README](../README.md)

Requires Windows and the .NET 10 SDK.

The bundled `pfdtool.exe` and `sfopatcher.exe` also require the **Visual C++ 2010 SP1 Redistributable (x86)** (`MSVCR100.dll`), including on 64-bit Windows. Install `vcredist_x86.exe` from [Microsoft](https://www.microsoft.com/en-us/download/details.aspx?id=26999) before running native encryption regressions. Both Windows workflows run `Tools/Install-NativeDependencies.ps1` to install this prerequisite when absent, using Microsoft's installer with a pinned SHA-256 checksum.

## Source organization

Game-specific application code lives under `Ratchet & Clank Save Editor/Games/<GameName>/`. `Games/ToolsOfDestruction/` contains its editors, inventory previews, research helpers and inspection UI. `Games/RatchetAndClank1/` contains RC1 inspection, ammo/grant/quick-select editing and the bundled native-map reader. Shared save sessions, profiles, encryption, metadata, numeric controls, theming and the main window remain at the application root.

Game-specific C# regression checks mirror that layout under `Tests/Games/<GameName>/`; shared UI and validation checks remain at the test root. The native research checks, tools and documentation retain their existing game/region/version folders under `Tests/PS3/`, `Tools/PS3/` and `docs/PS3/`.

## Build

```powershell
dotnet build "Ratchet And Clank Save Editor.sln" -c Release
```

Output: `Ratchet & Clank Save Editor/bin/Release/net10.0-windows/`. Framework-dependent builds require the .NET 10 Desktop Runtime.

The current version is **1.1.0**. Set `<Version>` in the application project to bump the default version. That one value supplies assembly/file metadata, **File → About**, the window title, and the executable name (`Ratchet & Clank Save Editor v1.1.0.exe`). A build can override it with `-p:Version=1.2.3` or a prerelease such as `-p:Version=1.2.3-rc.1`.

## Standalone Windows x64 build

```powershell
dotnet publish "Ratchet & Clank Save Editor/Ratchet & Clank Save Editor.csproj" -c Release -r win-x64 --self-contained true -o artifacts/publish
```

This output includes the runtime.

## Manual GitHub releases

After `.github/workflows/release.yml` is pushed to the default branch, open **Actions → Create release (manual) → Run workflow**. Choose the branch to build and enter a new tag such as `v1.2.3`. Optionally select **prerelease** or **draft**; tags with a suffix such as `v1.2.3-rc.1` are automatically prereleases.

The workflow passes the tag's version to the build and publish commands, builds and runs the application regressions, checks bundled research/documentation, and publishes a standalone Windows x64 ZIP with the .NET 10 Desktop Runtime, license and usage instructions. The executable name, window title and About dialog include the complete version, including any prerelease suffix. It attaches the ZIP to a GitHub release with generated release notes. The tag points to the exact commit used by that workflow run. Existing tags are rejected; source version files are unchanged.

Only the release job receives `contents: write`, using GitHub's automatic token; no personal access token is required. Packaging runs on Actions. The existing manual regression workflow remains available separately.

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

Use `-- --rc1` for RC1 inspection, ammo, all 15 combat grants and quick-select checks, or `-- --rc1-save "path/to/save-folder"` to also test a plaintext RPCS3 RC1 save. The latter edits only disposable copies and verifies byte preservation and the untouched source, including the Suck Cannon/Morph-o-Ray/R.Y.N.O. batch. UI previews are written to ignored `artifacts/rc1-inspector.png`, `artifacts/rc1-ammo-editor.png`, `artifacts/rc1-grants.png`, `artifacts/rc1-quick-select.png` and `artifacts/rc1-all-weapons.png`. See the [RC1 format notes](PS3/RatchetAndClank1/SaveFormat.md) and [native research tools](../Tools/PS3/RatchetAndClank1/NPEA00385/unknown/README.md).

Optional public integration samples:

```powershell
./Tests/FetchCompatibilitySamples.ps1
dotnet run --project Tests/SaveEditor.RegressionTests.csproj -c Release -- --samples artifacts/compatibility
```

Downloads use pinned hashes and stay under ignored `artifacts/`. These are software round-trip tests, not in-game acceptance tests.

Native reverse-engineering checks are covered in the [research tools guide](../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/README.md).
