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
2. Choose **File → Open Folder** (`Ctrl+O`) for encrypted PS3 saves. Use **Open Decrypted Folder (RPCS3)** (`Ctrl+Shift+O`) for manually decrypted saves. RPCS3's `RPCS3_BLIST` metadata is also recognized automatically. Opening or closing a save does not alter the original.
3. Edit currency in **Game Save Editing**. **Game Save Information** shows the region, account ID, secure file key, and optional artwork.
4. Choose **File → Save All** (`Ctrl+S`). The editor preserves the input format, verifies encrypted saves by decrypting another temporary copy and comparing every game-data byte, creates a full backup, and replaces the game data and metadata. The window stays open for further edits.
5. Copy the complete saved folder back to your PS3 using your usual save transfer workflow.

A backup is created automatically when you open a supported save, before decryption or editing, and another is created before each save. If the opening backup fails, the save is not opened and the original files are left untouched. Automatic and manual backups use unique directories inside a `Backups` folder beside the running executable, so earlier backups are never overwritten. This location does not depend on the working directory; run the editor from a writable folder. **Open Backups** is available as soon as a save is opened; **Back Up Save** can still create an extra manual backup. To restore, close the editor and copy every file from the chosen backup into the original save folder.

For decrypted/RPCS3 saves, `PARAM.PFD` is optional, encryption is never applied, and an existing PFD is left unchanged. Manually decrypted console saves must be re-encrypted using their original PS3 save-management workflow before console transfer. Do not mix decrypted game data with an encrypted PS3 folder.

**Update integrity** updates the working copy's integrity database while retaining its metadata bindings; it is unavailable for decrypted saves. **Remove copy protection** is available for decrypted saves only. Changing encrypted metadata requires the original console/disc signing keys, which the editor does not have: it refuses that operation instead of replacing valid hashes with fallback hashes. Account resigning is not provided. Metadata actions remain pending until **File → Save All**.

Opening an unsupported, incomplete, or truncated save reports an error. If another application changes the original folder while it is open, reopen the save before saving. Failed encryption leaves the original untouched. Failed replacement attempts restore any files already replaced, and the full backup remains available for manual recovery. Replacing multiple files is not a single atomic transaction; keep the backup if the PC shuts down during saving.

## Supported games

| Game | Game data | Editable values | Regions |
| --- | --- | --- | --- |
| Ratchet & Clank: Nexus | `GAME.SAV` | Bolts, raritanium | NPUA80908, NPEA00457, BCUS99245, BCES01908, BCES01949, BCJS30092, NPJA00101 |
| Quest for Booty | `GAME.SAV` | Bolts | BCUS98187, BLES00301, NPUA80145, NPEA00088 |
| Tools of Destruction | `GAME.SAV` | Bolts, raritanium | BCUS98127, BCES00052, BCKS10016, BCJS30014, BCJS70012, BCKS10054, BCAS20045, BCJS70004, NPUA98153, NPEA90017, NPJA90035, NPHA20002 |
| Ratchet & Clank | `USR-DATA` | Bolts | NPUA80643, NPEA00385, NPJA40001 |
| Going Commando / Locked and Loaded | `USR-DATA` | Bolts, raritanium | NPUA80644, NPEA00386, NPJA40002 |
| Up Your Arsenal / Ratchet & Clank 3 | `USR-DATA` | Bolts | NPUA80645, NPEA00387, NPJA40003 |
| Deadlocked / Gladiator | `USR-DATA` | Bolts | NPUA80646, NPEA00388, NPEA00423, NPJA40004 |
| A Crack in Time | `GAME.SAV` | Bolts | BCUS98124, BCES00142, BCES00511, BCES00748, BCES00726, BCJS30038, BCKS10087, BCAS20098, NPEA00453, NPUA80966 |
| All 4 One | `GAME.SAV` | Bolts for Ratchet, Clank, Qwark and Nefarious | BCUS98175, BCES01142, BCES01141, BCAS20200, BCJS30081, NPEA00356, NPUA80695, NPEA90105, NPUA70181 |
| Full Frontal Assault / QForce | `GAME.SAV` | Bolts (save on a planet first) | BCUS98380, NPUA80642, BCES01594, NPEA00378, XCES00001 |

Quest for Booty also recognizes BCES00301. Tools of Destruction also recognizes the digital NPEA00452 and NPUA80965 releases. Disc trilogy collections are identified using the individual game's save-directory ID, not the enclosing collection disc ID.

This covers the ten native PS3 games, **currency editing**, and the explicitly listed regions, not every save field or PS2 Classics/PSP/Vita formats. Unknown regions remain rejected rather than guessed. The window retains the original compact layout; only All 4 One shows an additional character selector. QForce/Full Frontal Assault uses a named floating-point record and caps edits at 16,777,216 to prevent integer precision loss. Saves without that record, such as some hub saves, cannot be edited.

The HD remasters use big-endian player blocks. The edited block's checksum is marked with the PS3 disabled-checksum sentinel (`FFFFFFFF`), following the established PS3 editing workflow; unedited planet blocks and unused reserved space remain unchanged. This is not the PS2 checksum algorithm.

Encrypted PFD v3/v4 transforms preserve all four original `PARAM.SFO` hashes, including the console, disc and authentication bindings, and independently re-sign the changed PFD tables. Data, metadata-file and table signatures are verified with the bundled native tool. Private-key binding hashes cannot be independently validated here; they are retained byte-for-byte, not recalculated with the bundled sample console or fallback disc key.

## Verification

```powershell
dotnet run --project Tests/SaveEditor.RegressionTests.csproj -c Release
```

This dependency-free runner checks every listed region, binary reads, relocated metadata, remaster player blocks, independent character edits, named float records, backups, repeated saves, failed encryption, rollback, external changes and the compact UI. It also uses the **actual bundled encryption tool** with synthetic PFD v3 and v4 fixtures for all ten games, checks original metadata-binding preservation, and rejects tampered ciphertext and invalid databases. Rendered UI previews are saved in `artifacts/`.

Optional real-save integration tests:

```powershell
./Tests/FetchCompatibilitySamples.ps1
dotnet run --project Tests/SaveEditor.RegressionTests.csproj -c Release -- --samples artifacts/compatibility
```

The download script verifies pinned archive hashes and stores public samples only under ignored `artifacts/`. Tests copy them to temporary folders before editing. Real encrypted R&C 1 (NPUA80643), R&C 2 (NPEA00386) and R&C 3 (NPEA00387) samples passed decrypt/edit/encrypt/reopen comparisons with original bindings intact. A real RPCS3 A Crack in Time (BCES00511) sample passed read/edit/reopen comparisons. **In-game acceptance on PS3/RPCS3 and every regional release have not been tested.** This implements the formats involved in [issue #2](https://github.com/primetime43/Ratchet-Clank-Save-Editor/issues/2); it does not claim that the reporter's specific saves have been reproduced without their files.

### Format references

- [Tools of Destruction save map](docs/ToolsOfDestructionSaveFormat.md): read-only analysis of BCES00052_SAVE_1, wrapper headers, gameplay names and unknown regions, plus code-backed snapshot linkage and weapon XP/ammo/level/modifier fields from the USA v02.00 ELF. Includes repeatable inspection and Ghidra tracing tools; new fields are not enabled for editing pending in-game validation.
- [Tools of Destruction ELF map](docs/ToolsOfDestructionElfMap.md): USA v02.00 executable research, including PS3 imports, scripting/physics, rendering/SPU, audio, memory and save I/O. Includes a shared address map and IDA/Ghidra annotation importers.
- [RatchetModding's save backends](https://github.com/RatchetModding/slimseditor/blob/master/slimseditor/backends.py): PS3 byte order, remaster player blocks and file names. Its [game definitions](https://github.com/RatchetModding/slimseditor/tree/master/slimseditor/game) document trilogy currency offsets.
- [Apollo's PS3 save-patch database](https://github.com/bucanero/apollo-patches/tree/main/PS3): A Crack in Time (`0x588`), All 4 One's character counters, and Full Frontal Assault's `player_bolts` record. Keys are retained from the bundled game-key database; the native configuration is generated from the application's catalog to avoid mismatches.
- [flatz's PFD format definitions](https://github.com/bucanero/pfd_sfo_tools/blob/master/pfdtool/src/pfd_internal.h) and [integrity routines](https://github.com/bucanero/pfd_sfo_tools/blob/master/pfdtool/src/pfd.c): factual v3/v4 layout and signature algorithms; `PfdBinding.cs` is an independent implementation.
- [racman's game/region catalog](https://github.com/MichaelRelaxen/racman), [RatchetHax's digital Tools of Destruction support](https://github.com/ParadoxEpoch/RatchetHax), and [RPCS3 digital Future-series reports](https://github.com/RPCS3/rpcs3/issues/16270): additional regional aliases.
- [Public Apollo trilogy saves](https://github.com/bucanero/apollo-saves/tree/master/PS3) and [RPCS3's public A Crack in Time sample](https://github.com/RPCS3/rpcs3/issues/8944): optional integration fixtures, not bundled with the application.

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
