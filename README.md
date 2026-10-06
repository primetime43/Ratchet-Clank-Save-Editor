# Ratchet & Clank Save Editor

A Windows desktop editor for PS3 Ratchet & Clank saves. Edit bolts and, where supported, raritanium; inspect save metadata; export artwork; and back up the original save.

## Run and build

Requires Windows and the .NET 10 SDK to build. A framework-dependent build requires the .NET 10 Desktop Runtime to run.

```powershell
dotnet build "Ratchet And Clank Save Editor.sln" -c Release
dotnet run --project "Ratchet & Clank Save Editor/Ratchet & Clank Save Editor.csproj"
```

The executable is generated in `Ratchet & Clank Save Editor/bin/Release/net10.0-windows/`.

For a standalone Windows x64 folder that includes the runtime:

```powershell
dotnet publish "Ratchet & Clank Save Editor/Ratchet & Clank Save Editor.csproj" -c Release -r win-x64 --self-contained true -o artifacts/publish
```

## Edit a save

1. Copy the complete PS3 save folder to your PC, including `PARAM.SFO`, `PARAM.PFD`, and the game data file.
2. Choose **File → Open Folder** (`Ctrl+O`). The editor decrypts a temporary copy; opening or closing a save does not alter the original.
3. Edit currency in **Game Save Editing**. **Game Save Information** shows the region, account ID, secure file key, and optional artwork.
4. Choose **File → Save All** (`Ctrl+S`). The editor encrypts the edited copy, verifies its integrity, creates a backup of every file directly in the original PS3 save folder, and replaces the game data and metadata. The window stays open for further edits.
5. Copy the complete saved folder back to your PS3 using your usual save transfer workflow.

Automatic and manual backups use unique directories under `%LOCALAPPDATA%\RatchetClankSaveEditor\Backups\`. Use **Back Up Save** for a manual backup and **Open Backups** after a backup or save to locate it. To restore, close the editor and copy every file from the chosen backup into the original save folder.

**Update integrity** updates the working copy's integrity database; it does not change the account ID. **Remove copy protection** applies the bundled patcher's copy-protection patch. Both actions remain pending until **File → Save All**. Account resigning is not provided by this editor.

Opening an unsupported, incomplete, or truncated save reports an error. If another application changes the original folder while it is open, reopen the save before saving. Failed encryption leaves the original untouched. Failed replacement attempts restore any files already replaced, and the full backup remains available for manual recovery. Replacing multiple files is not a single atomic transaction; keep the backup if the PC shuts down during saving.

## Supported games

| Game | Game data | Editable values | Regions |
| --- | --- | --- | --- |
| Ratchet & Clank: Nexus | `GAME.SAV` | Bolts, raritanium | NPUA80908, NPEA00457, BCUS99245, BCES01908, BCES01949, BCJS30092, NPJA00101 |
| Quest for Booty | `GAME.SAV` | Bolts | BCUS98187, BLES00301, NPUA80145, NPEA00088 |
| Tools of Destruction | `GAME.SAV` | Bolts, raritanium | BCUS98127, BCES00052, BCKS10016, BCJS30014, BCJS70012, BCKS10054, BCAS20045, BCJS70004, NPUA98153, NPEA90017, NPJA90035, NPHA20002 |
| Ratchet & Clank | `USR-DATA` | Bolts | NPUA80643 |

Support retains the original editor's regions and currency offsets. Additional games and regions require verified save samples.

## Verification

```powershell
dotnet run --project Tests/SaveEditor.RegressionTests.csproj -c Release
```

This dependency-free regression runner checks binary reads, metadata parsing, all four game profiles, backup preservation, repeated saves, failed encryption, replacement rollback, external changes, pending metadata actions, and the compact UI layout and scaling. It also invokes the bundled `pfdtool` against an invalid fixture to verify that silent failures are rejected. Rendered UI previews are saved in `artifacts/`.

Successful PS3 encryption and console acceptance still require testing with real save samples; synthetic regression fixtures use a substitute for successful tool operations.

## Credits

Original editor by primetime43, with help from Red_EyeX32. Bundled `pfdtool` and `sfopatcher` by flatz. See [LICENSE](LICENSE).

## Project history

Originally released in 2013 by primetime43, then revisited to improve the program.

### Original v1.0.0 screenshots

![image](https://github.com/primetime43/Ratchet-Clank-Save-Editor/assets/12754111/67a44823-69b7-48c5-b250-a9612d77b698)
![image](https://github.com/primetime43/Ratchet-Clank-Save-Editor/assets/12754111/09c98af7-4aba-4fff-93b3-a867563370d0)

## Historical save-format research

The following notes are preserved from the original README. Supported editing features and game regions are listed above.

```
//Ratchet & Clank 1 (original)
0x24 - Number of bolts (4 bytes)
0x15b - Ammo for Blaster (Max value 200)(C (If you go above C8, the max, the game will reset to new game) 
(All ammo is one byte) //That goes for all the ammo
0x153 - Visibomb Ammo  (Max value 20) (14)
0x14b - Devastator Ammo (Max value 20) (14)
0x16f - Gold Glove of Doom Ammo (Max value 10) (0A)
0x17b - R.Y.N.O Ammo (Max value 50) (32)
0x17f - Drone Ammo (Max value 10) (0A)
0x147 - Bomb Glove Ammo (Max value 40) (2
0x15f - Pyrociter Ammo (Max value 240) (F0)
0x163 - Mine Glove Ammo (Max value 50) (32)
0x16B - Telsa Claw Ammo (Max value 240) (F0)
0x183 - Decoy Glove Ammo (Max value 20) (14)

//Ratchet & Clank 2: Going Commando
0x24 - Number of bolts (4 bytes)
0x28 - Number of Raritanium (4 bytes)

//Ratchet & Clank: Up Your Arsenal
0x24 - Number of bolts (4 bytes)

//Ratchet & Clank Quest For Booty
0x274 - Number of bolts (4 bytes)
```

Some files contained in the PS3 game save: (https://www.psdevwiki.com/ps3/PS3_Savedata)
- GAME.SAV
- PARAM.PFD (https://www.psdevwiki.com/ps3/PARAM.PFD)
- PARAM.SFO (https://www.psdevwiki.com/ps3/PARAM.SFO)
