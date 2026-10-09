# Tools of Destruction executable map

Research notes for the supplied USA **BCUS98127 v02.00** `EBOOT.ELF`. This map covers startup, PS3 imports, scripting, physics bindings, rendering/SPU diagnostics, audio/middleware anchors and save I/O. It is a starting point, not a complete reconstruction of the game.

## Files to use in IDA or Ghidra

- [Shared address map](maps/ToolsOfDestruction.BCUS98127.v02.00.json): 238 annotations, 118 imports, evidence, byte signatures and six structure definitions.
- [Ghidra importer](../Tools/Ghidra/ImportTodMap.java): applies labels, plate comments and data types.
- [IDA importer](../Tools/IDA/import_tod_map.py): IDAPython script for labels, repeatable comments and local types; no IDC needed.
- [Save-format notes](ToolsOfDestructionSaveFormat.md): file-relative offsets, inventory records and wrapper headers.

The importers modify the **analysis database only**, not the executable or saves. They check the input SHA-256 and all supplied byte signatures before applying annotations. Existing custom names, comments and types are preserved; repeated imports do not duplicate identical notes. Types are added to the type manager but are **not automatically applied** to ELF globals or save bytes. The imported names are descriptive research labels, not recovered original symbols.

Confidence is per annotation: **confirmed** means directly established by bytes, descriptor/pointer tracing, an identifying error path or a matching SDK import ID; **observed** describes behavior without claiming a complete original name or purpose; **candidate** is a hypothesis. A confirmed diagnostic string does not confirm the address or full behavior of the function named inside it.

## Exact executable

| Property | Value |
| --- | --- |
| File | Decrypted `EBOOT.ELF`, 10,923,400 bytes |
| SHA-256 | `0EE9A8414C8FC182BC19FA2A523E6D050D0BE76138B3733AE515798D77D2468C` |
| ELF | ELF64, big-endian, PPC64 machine `0x15`, PS3 OS ABI `0x66` |
| Ghidra language | `PowerPC:BE:64:64-32addr`, compiler `default` |
| ELF entry | Descriptor VA `0x859418`, containing code VA `0x14360` and TOC `0x88FF38` |
| Section headers | 34 entries at file offset `0xA6A508`, stride `0x40` |
| Section-name table | File offset `0xA6A3B2`, size `0x150`; all bytes zero |

Addresses below are **ELF virtual addresses**, not ELF file offsets, save offsets or RPCS3 host-process RAM addresses. Import the ELF at its original addresses; the annotation scripts do not guess rebase deltas. Blank section names do not imply missing section boundaries or recoverable original function symbols.

### Main load segments

Ranges have exclusive ends. File-backed data in a segment maps as `VA = segment VA + file offset - segment file offset`.

| File offset | VA | File bytes | Memory bytes | Observed role |
| --- | --- | --- | --- | --- |
| `0x000000` | `0x00010000` | `0x82C648` | `0x82C648` | Executable code and PS3 import metadata |
| `0x830000` | `0x00840000` | `0x6D4E8` | `0x6D4E8` | Data, function descriptors and TOC slots |
| `0x8A0000` | `0x10000000` | `0x56B80` | `0x56B80` | Strings and other read-only data |
| `0x900000` | `0x10060000` | `0x14EF00` | `0x82C570` | Initialized writable data and zero-initialized memory |

The large final segment's zero-initialized portion starts at `0x101AEF00` and ends at `0x1088C570`. It occupies runtime memory but has no corresponding initialized file bytes. A zero-sized load segment and TLS-related program headers also exist; the table is not a list of every program header.

## PS3 function descriptors and three TOCs

Section 22 contains **23,910 eight-byte records** at `0x859408–0x887F38`: BE uint32 code VA followed by BE uint32 r2/TOC base. Do not treat these as 24-byte desktop PPC64 descriptors or disassemble their contents as instructions.

| TOC base | Descriptor count |
| --- | ---: |
| `0x88FF38` | 8,186 |
| `0x89FF20` | 7,519 |
| `0x8AFE5C` | 8,205 |

`0x8AFE5C` is a **reference base outside the mapped data section**, not a missing data buffer. Its valid accesses use negative displacements. Importers retain this value in the JSON and skip its standalone label when unmapped; they do not create artificial memory there.

Cross-TOC calls can use local thunks. Verified example, called from `0x35E45C`:

```text
0x24F908  std   r2,0x28(r1)
0x24F90C  addis r2,r2,1
0x24F910  subi  r2,r2,0xC4
0x24F914  b     0x694D28
```

This changes TOC `0x89FF20` to `0x8AFE5C`; the caller restores r2 after returning. Using a single global TOC produced misleading or missing references in the initial analysis. `PrepareTod.java` now seeds all descriptors with their own TOCs. Default PowerPC decompilation can still lose r2 across stack restores; assembly and descriptor-backed pointer tracing take precedence over invented decompiler stack variables.

## PS3 library imports

Nine import records occupy `0x83C46C–0x83C5F8`, stride `0x2C`. They identify 118 imported functions, with no variable/TLS imports in these records. The record fields match [RPCS3's PS3 import loader](https://github.com/RPCS3/rpcs3/blob/master/rpcs3/Emu/Cell/PPUModule.cpp).

| Library | Record VA | Functions | Names resolved | Research use |
| --- | --- | ---: | ---: | --- |
| sysPrxForUser | `0x83C46C` | 19 | 4 | Process/runtime services |
| sys_fs | `0x83C498` | 14 | 14 | File and directory operations |
| sys_io | `0x83C4C4` | 9 | 9 | Controller input, pressure/sensor modes, vibration |
| cellGcmSys | `0x83C4F0` | 15 | 15 | Graphics setup, buffers, flips, tiles and address mapping |
| cellAudio | `0x83C51C` | 7 | 7 | Audio initialization and port lifecycle |
| cellSysutil | `0x83C548` | 19 | 15 | System callbacks, video, game data and save data |
| cellSysmodule | `0x83C574` | 3 | 3 | Module initialization/loading/unloading |
| cellSpurs | `0x83C5A0` | 31 | 31 | SPU tasksets, workloads, events and queues |
| cellSync | `0x83C5CC` | 1 | 1 | Lock-free queue direction query |

The JSON stores every NID, local stub VA and address-slot VA. **99 names** match public RPCS3 `REG_FUNC` registrations, checked on 2026-10-08; each resolved import cites its source file. The other **19 remain numeric**, not guessed. Matching uses the [RPCS3 NID algorithm](https://github.com/RPCS3/rpcs3/blob/master/rpcs3/Emu/Cell/PPUModule.cpp): SHA-1 of the symbol name plus suffix `6759659904250490566427499489741A`, then the first four digest bytes interpreted little-endian. A local import stub is not the SDK implementation.

Useful resolved anchors include `cellFsOpen/Read/Write`, `cellPadGetData`, `cellGcmSetFlip`, `cellAudioPortOpen`, `cellSpursCreateTask`, and the save list/auto-load/auto-save imports. Their exact individual addresses are in `library_imports` and the imported `TOD_import_...` labels.

## Non-save findings

### Lua and gameplay/physics bindings

The version text `Lua 5.0.2` is at `0x1002AC50`. Function `0x6687E0` returns it using `lwz r3,-0x6040(r2); blr`, with TOC `0x8AFE5C` and pointer slot `0x8A9E1C`. This establishes the embedded version marker and its getter, not that all bundled Lua code is unmodified upstream code.

Generated Lua configuration and gameplay source-path strings survive at `0x10019668` and `0x100260B0`. A tolua++ mapping-source path survives at `0x1002C2E0`. These are build-time provenance strings, not source files available on this machine.

| Function VA | Established behavior | Evidence |
| --- | --- | --- |
| `0x2C4770` | Lua `physics_on` wrapper | Validates handle/arguments; error load `0x2C47C4` resolves to `0x10025310`; calls target `0x27F558` at `0x2C483C` |
| `0x2C4930` | Lua `physics_off` wrapper | Matching error load `0x2C4984` resolves to `0x10025338`; calls target `0x27E2A0` |
| `0x6687E0` | Embedded Lua version getter | Two instructions and pointer chain above |

The wrappers do not establish the complete physics engine, native object layouts or safe gameplay patch points. Weapon and currency scripting anchors have now been traced separately to the saved-state block below.

### Rendering and SPU work

| String VA | Anchor | Interpretation/limit |
| --- | --- | --- |
| `0x10027C18` | `MobyShaderConstsUpdate` | Passed by `0x51FDC0`, whose inspected body waits on another operation; full shader update not mapped |
| `0x100278E8` | Draw-sort SPU timeout | Named rendering diagnostic, not a recovered function entry |
| `0x10028D60` / `0x10028D90` | Dynamic/static DB query SPU timeouts | Leads for query and synchronization code; data structures unknown |
| `0x10028F08` | Geometry cull/clip SPU timeout | Geometry-work diagnostic |
| `0x10029820` | Render DB wait timeout | Synchronization diagnostic |
| `0x10027728` / `0x10027818` | `igCollBroadSpu.elf` / `igcollspu.elf` build paths | Separate SPU collision-program names; existence/location in the installed game not established |

These markers and the 31 SPURS imports provide entry points for future SPU/graphics research. The PPU ELF is not itself a disassembly of those separate SPU programs.

### Audio, middleware and memory

The SCREAM audio allocator diagnostic at `0x1002CB88` is referenced by `0x6DBDC4` and `0x6DBDF0`. Both call a diagnostic helper; the former returns zero. These are useful fallback/error-path leads, **not confirmed original allocator function names**. No SCREAM version is established. The seven resolved `cellAudio` imports identify the platform audio-port interface separately.

Anark-support pool-allocator source text at `0x10029DA0` has references in `0x6AB800`, including instructions `0x6AB868`, `0x6AB898`, `0x6AB910` and `0x6AB974`. Its inspected body initializes linked structures and allocates nodes. This establishes an allocator-related client, not the full allocator implementation or an original class name. Other embedded Anark framework paths reinforce the component lead, but those sources were not recovered.

StageCore game-data and cache-mount thread markers occur at `0x10026C58` and `0x10026C78`; the game-data-check thread marker is at `0x100275E8`. Strings alone do not establish their thread entry addresses. Save/load thread-name anchors are included separately in the JSON.

## Save I/O findings from the executable

At `0x35E2C8`, setup code copies `GAME.SAV` from string VA `0x10026648` through TOC slot `0x8A1974` (`r2 + 0x1A54`, TOC `0x89FF20`). The filename load is at `0x35E3FC`.

The same routine initializes these **runtime object fields**, not save-header fields:

| Object offset | Initialized value | Evidence |
| --- | --- | --- |
| `+0xC0` / `+0xC4` | Buffer at object `+0x108`, size `0x800` | Stores at `0x35E394–0x35E398` |
| `+0xC8` / `+0xCC` | Directory/file list maxima, each `0x20` | Stores at `0x35E3E0` / `0x35E3A8`; SDK list-buffer setup |
| `+0xD0` / `+0xD4` | ICON0 buffer at object `+0x908`, capacity `0x1F400` | Stores at `0x35E3AC` / `0x35E39C`; file callback reads these fields |
| `+0xD8` / `+0xDC` | Game buffer at object `+0x1FD08`, size **`0x906F0`** | Pointer calculation `0x35E2E8/0x35E2FC`; size construction `0x35E2CC/0x35E304`; stores `0x35E3A0/0x35E3A4` |

`0x906F0` matches the European sample's exact `GAME.SAV` length. This independently supports the buffer length, **not** every serialized field or cross-region acceptance. The setup routine then calls runtime initialization at `0x694D28` through the cross-TOC thunk described above.

Lua wrapper `0x39D588` names `save_game_exists` on its error path and calls predicate `0x39B700`. The predicate reaches an object through pointer slot `0x8A2ACC` and returns true only when both words at object `+0x100` and `+0xFC` are nonzero. Their exact purposes remain unknown; this is not a verified on-disk header parser.

### Verified snapshot and weapon state

The serialization boundary is now established: a contiguous **`0x906F0`-byte game-state block at RAM VA `0x101EFB20`** is copied to/from the save-manager buffer. This is a runtime/BSS address, not initialized ELF data or an emulator host-process address.

```text
RAM game state 0x101EFB20, length 0x906F0
  -> 0x35E710 snapshot via 0x252428 -> 0x81A9A8 byte copy
save manager +0x1FD08 (pointer at +0xD8, length at +0xDC)
  -> 0x695BF8 file callback, state 5
PS3 secure GAME.SAV write

load restore: manager buffer -> 0x35E508 -> same RAM block
```

Evidence is independently reproducible:

| Location | Established behavior |
| --- | --- |
| TOC slot `0x888624` | BE pointer `0x101EFB20`; used by inventory getters with TOC `0x88FF38` |
| TOC slot `0x8A1984` | Same pointer; used by snapshot/restore with TOC `0x89FF20` |
| `0x35E72C–0x35E744` | Loads state source, computes manager `+0x1FD08`, constructs length `0x906F0`, calls byte copy |
| `0x35E50C–0x35E534` | Reverses source/destination with the same length |
| `0x87EC68` | Callback descriptor: code `0x695BF8`, TOC `0x8AFE5C`; pointer slot `0x8AA484` |
| `0x695D78–0x695DD4` | File operation WRITE (1), type SECUREFILE (0), filename manager `+0x70`, buffer from `+0xD8`, both lengths from `+0xDC`, 16-byte secure ID copied from `+0x60` |
| `0x2D1C00` | Reads bolts at state `+0x41C`, using pointer slot `0x89F1B8 = 0x101EFB20` |

Callback field names follow [RPCS3's CellSaveData structures](https://raw.githubusercontent.com/RPCS3/rpcs3/master/rpcs3/Emu/Cell/Modules/cellSaveData.h). The game callback does not explicitly assign `fileOffset`; [RPCS3 clears FileSet before each callback and writes from its resulting offset](https://raw.githubusercontent.com/RPCS3/rpcs3/master/rpcs3/Emu/Cell/Modules/cellSaveData.cpp), giving offset zero there. That emulator behavior is not a separately verified implementation of console firmware. The copy contains no field transform; secure-file handling/PFD integrity is outside this copy, and a complete internal checksum/validation scheme remains unestablished.

Before snapshot, `0x35E710` calls thunk `0x250758 → 0x24EAC8`, which calls `0x24DAB8` on another object's `+0x1AF84` area. That helper conditionally delegates through `0x12670`. Its complete synchronization semantics are not mapped; do not claim the snapshot call is the only pre-save operation. Restore also applies float state from save offsets `0x114C8`, `0x114CC`, `0x114C4` and delegates state `0x906E8`; exact meanings remain unknown.

The inventory base is this same RAM block. Native getters calculate `base + ID*0x14`, not an unrelated RAM structure:

| Script/native chain | Verified record use |
| --- | --- |
| `get_weapon_ammo`: `0x33C80 → 0x258C0` | `lfs` at `0x25964` reads float `+0x08`; subsequent conversion integerizes the script result |
| `get_weapon_level`: `0x33A98 → 0x27608` | `lbz` at `0x27688` reads byte `+0x11`; `0x27690` adds one |
| `get_weapon_progress`: `0x339C0 → 0x27568 → 0x11940 → 0x465FF0` | XP float `+0x04`, level byte `+0x11`, weapon-data thresholds `+0x230 + 4*level` |
| `get_weapon_max_ammo`: `0x33BA8 → 0x27760 → 0x10CB0 → 0x466500` | Level byte `+0x11` and modifier word `+0x0C`; per-level definition values and attribute-9 modifiers |

Ammo, level and progress paths gate access with byte `+0x10` and item-definition flags at definition `+0x18`. The ownership chain is now fully resolved: `is_weapon_owned` wrapper `0x33F40 → 0x25AF0 → thunk 0x12950 → 0x2D1C10`. The leaf tests byte `state + ID*0x14 + 0x10` for **any nonzero value**. This establishes script ownership, not that every flagged slot describes a usable weapon. The existing type member name `eligibility_state` is retained for import compatibility; its refined meaning is this ownership byte.

XP setter `0x4660A8` writes float `+0x04`, recomputes stored level from weapon-data thresholds and cap helper `0x465F08`, and updates ammo on level increase. Helper `0x465E78` explicitly pairs stored level 5 with its XP threshold. Changing the byte alone can therefore leave inconsistent XP/level state. The default decompiler sometimes drops floating-point returns or represents float loads as integer casts; the raw `lfs/stfs/fsubs/fdivs` instructions establish the types.

Modifier helper `0x465D00` ORs a selected bit into record `+0x0C` and refills ammo if maximum changes. Calculation `0x466258` walks weapon-data entries at `+0x464`, stride `0x18`, count at `+0x6A4`; enabled bits select entries matching an attribute ID. Kind zero adds a float, other kinds accumulate a multiplier. Maximum ammo chooses attribute 9 and a base value at weapon-data `+0x280 + 4*level`. The packed assets now provide node indices, label tags, costs and XP/ammo tables, and native bindings confirm the field names below. **Prerequisites, save-ID/name linkage, safe masks and gameplay-validated bounds remain unresolved.** This helper alone does not describe a complete upgrade purchase.

The JSON `serialization` section records the state/copy chain, field offsets and exact instruction guards. The new `TOD_SaveInventoryRecord_verified` type supersedes candidate field names without overwriting an existing analyst's `TOD_SaveInventoryRecord_observed` type. Both remain available because importers preserve existing types. The remaining gameplay/health/armor structures are not verified. No editor fields were enabled by this research, and the USA ELF/European sample match is not a cross-region load test.

### Ownership unlocks and acquisition

| Function or field | Established behavior |
| --- | --- |
| `0x466A60` | Initializes exactly **32** records, IDs 0–31, stride `0x14`, then clears word `+0x280`. The count is now code-backed, not merely an observed sample pattern. |
| `0x466B70` | Acquisition helper: can refill ammo according to item-definition flags; on a previously unowned item, sets record `+0x10` to 1, delegates XP/level initialization, increments word `+0x280`, and can set an additional item-class bit in state `+0x5528`. |
| `0x466AE8` | For an owned record, delegates XP/ammo resets, clears `+0x10` and decrements word `+0x280`. |
| `0x465DC0` | Absolute ammo setter, clamped using the maximum from `0x463DE0` and a zero constant; stores float `+0x08`. |
| `0x2BB778 → 0x28B4E8` | Named `hero_give_weapon` binding. Native code checks ID 0–31 and hero context, calls acquisition with refill enabled, delegates inventory integration, optionally sets XP and ammo, and can notify another system. |
| `0x2A4EC0 → 0x27A5B8` | Named `unlock_weapon` binding. Sets byte `state + 0x5754 + ID` to 1, using pointer slot `0x898F50 = 0x101EFB20`. This is **separate from possession** at record `+0x10`. |
| `0x2D24C0` | Availability predicate uses the unlock byte, definition flag 2 and ownership. An unlocked item is not automatically already owned or purchasable. |
| `0x2D1EF8` | Modifier index must be below definition entry count at `+0x6A4`, item must be owned, and mask bit must be unset. Price, adjacency and all other purchase prerequisites are not established by this predicate. |
| `0x2D2430` | Reads saved word `+0x420`, independently corroborating the existing raritanium offset. |

Word `0x280` is updated as an acquisition/removal counter, but it is **not asserted equal to the number of nonzero ownership bytes**. The reference sample has counter 46 and 32 nonzero record flags. This may reflect other writers, prior edits or another invariant; these routines alone do not settle it. Do not automatically normalize the counter to 32.

The total unlock-array length is not established. The comparison tool decodes only the 32 IDs whose inventory records are mapped; the larger byte region still contains unknown state. Named `purchase_weapon` wrapper `0x337D8 → 0x26638` branches through thunks to `0x2D21A8` or `0x2D2D38`. The latter is now traced: it requires a hero, applies an extra condition for ID `0x13`, obtains price via `0x2D2058`, checks inventory bolts at `+0x41C`, calls acquisition/refill `0x466B70`, delegates hero inventory integration through `0x252B08`, and deducts the price through `0x24FCB8`. It also conditionally dispatches through a virtual method and sends further notifications. This leaf does not establish every vendor prerequisite or the complete semantics of those downstream calls. A one-byte edit is not a complete purchase.

The auxiliary initializer `0x35DC80` clears currency and initializes a 32-word sentinel list at `0x284`, three 23-word arrays at `0x304/0x360/0x3BC`, and other state. Their complete meanings remain unknown. The restart-style routine `0x3CED40` copies and selectively resets state, including some records, then increments/clamps word `0x906EC`; **challenge-mode interpretation is a candidate**, not a confirmed editable field. These are additional leads, not imported original function names.

### Packed weapon configuration and native field bindings

The supplied game's `packed/game/global_cached.psarc` contains plaintext `weapon.csv`, `mods.csv`, `vendor.csv` and their Lua loaders under `/data/configs/`. Selective extracts remain under ignored `artifacts/tod-assets-v02.00/`; no archive, Lua source, compiled code or game binary is tracked. The six SHA-256 fingerprints are recorded in the JSON map's `weapon_configuration.assets` section and the report tool.

This particular archive has 3,297 entries, version `0x00010002`, `zlib` compression, 30-byte TOC records and 64 KiB blocks. All 3,296 filename hashes match **ASCII-uppercase full manifest paths**, including their leading slash. Filename MD5s are not payload-integrity hashes. The independent [archive inspector](../Tools/Inspect-Psarc.py) follows the field/block layout corroborated by this [primary PSARC extractor implementation](https://raw.githubusercontent.com/rscustom/rocksmith-custom-song-toolkit/master/RocksmithToolkitCLI/generalscripts/psarc-extract.rb); uppercase normalization is an observation from these ToD bytes, not assumed for every PSARC variant.

The [configuration report](../Tools/Inspect-TodWeaponConfigs.py) parses numeric literals without executing Lua or expressions. It reports all 28 named weapon/gadget configurations, all per-level variables, 204 modifier entries across 15 weapon groups, vendor weapon/armor records, node masks, costs and localization tags. The 204 entries include 15 `MOD_START` entries: they are not 204 purchasable upgrades. These are shipped **asset definitions**, not independently captured runtime configuration or safe editor limits.

Loader rules established by reading the source:

- `weapon.lua` maps Lua column 4 to level index 0, column 5 to index 1, and so on. `NumLevels` stores the largest populated zero-based index, not a count. Blank cells are unspecified; the report does not fill them from previous levels.
- `mods.lua` maps the CSV node index directly to `Mods[index]`; `NumMods = index + 1`. `PERCENT` values are multiplied by `0.01`, while absolute values are left unchanged. Some `MOD_SPECIAL` rows deliberately omit numeric values, and negative percentage values exist. Neither blank nor negative automatically means corrupt data.
- `vendor.lua` assigns named fields under `config.<weapon>.Vendor`; it also populates armor vendor configuration. Its unlock strings are level identifiers, not save offsets or inventory possession flags.

The ELF independently binds several names to the previously traced native offsets. Registration routine `0x80848` passes named strings and getter/setter descriptors into Lua property registration. Confirmed descriptor TOC is `0x88FF38`; raw instructions and float stores resolve decompiler ambiguities.

| Named property | Native accessors | Runtime field |
| --- | --- | --- |
| `MaxAmmo[index]` | Get `0xB8840`, set `0xB8728` | Weapon config `+0x280 + index*4`, float32; index check allows **0–19** |
| `NumMods` | Get `0xB4870`, set `0xA73A0` | Weapon config `+0x6A4`, word |
| `Vendor` | Get `0x99B20` | Subobject at weapon config `+0x6A8` |
| `Vendor.BasePrice` | Get `0xB4BB0` | Vendor `+0`, hence weapon config `+0x6A8` |
| `Vendor.AmmoPrice` | Get `0xB4AE0` | Vendor `+4`, hence weapon config `+0x6AC` |
| `Vendor.MegaPrice` | Get `0xB4A10` | Vendor `+8`, hence weapon config `+0x6B0` |
| `config.Combuster` | Get `0x971E0` | Parent configuration `+0x1CFC`, **not** a save offset |
| `config.Grenade` | Get `0x96FD0` | Parent configuration `+0x3178`, **not** a save offset |

The maximum-ammo array has **20 native slots**, but the supplied CSV defines ten levels for each of the 15 upgradeable weapons. Capacity does not establish 20 playable levels. The registration also exports `MOD_AMMO = 9`: float constant `9.0` at `0x88B334` is passed with the `MOD_AMMO` string, matching attribute 9 used by `0x466500`. Price selector `0x2D2058` chooses `AmmoPrice` for definition flag 2, otherwise `BasePrice`; the promotion path uses `MegaPrice`.

The table below summarizes the assets using **internal configuration names**, not confirmed save IDs or player-visible weapon names. “Ammo +mods” is the arithmetic result of enabling every listed `MOD_AMMO` node; it does not claim that every mask is attainable or accepted. All listed ammo modifiers in these assets are absolute additions.

| Config name | Base ammo | Ammo +mods | Nodes incl. start | XP for level 5 | XP for level 10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Combuster | 100 | 100 | 14 | 5,368 | 83,336 |
| Grenade | 8 | 10 | 11 | 5,368 | 83,336 |
| GoopMine | 8 | 10 | 13 | 3,221 | 46,760 |
| Tornado | 5 | 5 | 12 | 5,368 | 46,760 |
| Predator | 25 | 30 | 16 | 8,052 | 88,083 |
| Ravager | 30 | 36 | 14 | 4,294 | 48,760 |
| Reaper | 30 | 40 | 14 | 10,736 | 131,780 |
| BuzzBlade | 200 | 260 | 14 | 13,420 | 137,280 |
| EnergyClaws | 30 | 50 | 12 | 26,840 | 120,520 |
| AlphaNova | 4 | 5 | 11 | 18,788 | 62,760 |
| RoboHive | 4 | 6 | 15 | 8,052 | 91,520 |
| Rocket | 12 | 15 | 12 | 32,208 | 161,280 |
| FlameThrower | 30 | 40 | 15 | 21,472 | 113,520 |
| MagNet | 12 | 16 | 16 | 16,104 | 72,760 |
| Ryno | 300 / 750 at indices 5–9 | 450 / 900 | 15 | 80,520 | 242,040 |

Combuster's full XP threshold array is `[0, 1000, 2200, 3640, 5368, 5500, 20000, 37400, 58280, 83336]`. Its node 12 is `MOD_DURATION`, absolute `4`, cost `300`, with localization tags identifying the special burn-patch upgrade. Its complete CSV node catalog spans 0–13, whereas the reference save's modifier word `0x3FFE` enables bits 1–13. That is compatible with this catalog **if** record 1's name linkage is established; it is not an independent proof of that ID mapping or of prerequisites.

Other configurations are Wrench, Groovitron, MiniLeech, ConfusionGas, Zurkon, MaxiLeech, Copter, Morph, Slinkonator, SwingShot, Inflatopod, Gelanator and Decryptor. The first group has only index-0 values; the last four have two populated XP columns but only one populated ammo column. Do not invent missing gadget levels/ammo values. CSV order differs between weapon and vendor tables and must not be used to label the 32 save records.

Reproduce without modifying the game:

```powershell
# Create a separate, ignored output folder first. Each --out must be a new file.
python -B Tools/Inspect-Psarc.py "path/to/global_cached.psarc"
python -B Tools/Inspect-Psarc.py "path/to/global_cached.psarc" `
  --name /data/configs/weapon.csv --out artifacts/tod-assets-v02.00/weapon.csv
# Repeat explicitly for weapon.lua, mods.csv/.lua, and vendor.csv/.lua.
python -B Tools/Inspect-TodWeaponConfigs.py artifacts/tod-assets-v02.00
python -B Tests/TestPsarc.py --archive "path/to/global_cached.psarc" -v
python -B Tests/TestTodWeaponConfigs.py --assets artifacts/tod-assets-v02.00 -v
```

The archive tool refuses existing outputs and extraction into the original archive directory. Bounds, decompression size, malformed manifests, untrusted names and overwrite protection are fixture-tested. Reference tests verify matching extracted hashes and unchanged original archive/assets. Remaining work: link every configuration to its inventory ID, establish node adjacency/prerequisites and runtime overrides, and validate edited copies in-game. No new editor fields are enabled by these findings.

### External editor references

The user-supplied [rac-savegame-editor definitions](https://github.com/maikelwever/rac-savegame-editor/blob/master/RACSaveGameEditor/GameItems.cs) independently list ToD bolts `0x41C` and raritanium `0x420`; its ToD section contains no weapon fields. Its [save-container implementation](https://github.com/maikelwever/rac-savegame-editor/blob/master/RACSaveGameEditor/SaveGameContainer.cs) is a lead for format detection, but its fixed SFO seek is not a replacement for parsing the metadata table.

The project's README points to [Slim's Editor](https://github.com/RatchetModding/slimseditor), now under RatchetModding. At commit `e4cd47d2bb65566dca66799669f2672fd7a5f395`, its [ToD JSON](https://github.com/RatchetModding/slimseditor/blob/e4cd47d2bb65566dca66799669f2672fd7a5f395/slimseditor/game/tod.json) also contains only the two currency definitions. Neither source supplies the missing ToD XP thresholds, upgrade-node catalog or in-game validation. These are corroborating references; no third-party implementation code was copied or executed.

## Import and reproduce

### Ghidra

Import the matching ELF using `PowerPC:BE:64:64-32addr`. Add `Tools/Ghidra` to Script Manager's script directories, run `ImportTodMap.java`, and choose the JSON map. Look for `TOD_` labels and the `/RatchetClank/ToolsOfDestruction` data-type category. The unmapped third TOC base remains in JSON and is skipped as a standalone label.

The live Ghidra checks cover mapped annotations, six structure layouts, repeat-import idempotence and preservation of custom labels/comments. The portable suite verifies the original ELF hash, annotation bytes, 28 serialization instruction guards and ownership/acquisition relationships. The reference-save inspector verifies unchanged hashes for every original file. Comparison-tool checks use generated fixtures, **not in-game captures**.

For a fresh headless research project, run descriptor preparation **before** analysis, then import annotations. Do not use this fixed-build preparation script on a different ELF:

```powershell
# Set these paths for your installation; the project directory must exist.
& "$GhidraRoot/support/analyzeHeadless.bat" $ProjectDirectory TodResearch `
  -import $ElfPath -processor PowerPC:BE:64:64-32addr -cspec default `
  -scriptPath "$RepoRoot/Tools/Ghidra" -preScript PrepareTod.java `
  -postScript ImportTodMap.java "$RepoRoot/docs/maps/ToolsOfDestruction.BCUS98127.v02.00.json"
```

`SurveyTod.java <output-directory> [function-VA ...]` exports string references, descriptor-based TOC-load leads, assembly and selected decompilations. Its direct TOC-load scan assumes the descriptor TOC for that instruction; confirm r2-changing thunks and restore paths in assembly before treating every lead as resolved. Local project/copy/reports are under ignored `artifacts/ghidra/BCUS98127-02.00/`; no game binary is included in the tracked research files.

`TraceTodSave.java <fresh-output-directory> <queries...>` provides a targeted, read-only survey with original instruction bytes. Queries are `f:<VA>` (function), `r:<VA>` (references and TOC leads), `d:<VA>:<hex-size>` (data), `n:<VA>:<decimal-count>` (nearby functions) and `i:<hex-immediate>` (instruction scan). It checks the reference ELF hash, refuses an existing output directory, and marks uninitialized/BSS bytes instead of inventing values. It does not add labels or change types. Example after preparing the project:

```powershell
& "$GhidraRoot/support/analyzeHeadless.bat" $ProjectDirectory TodResearch `
  -process EBOOT.ELF -noanalysis -scriptPath "$RepoRoot/Tools/Ghidra" `
  -postScript TraceTodSave.java "$RepoRoot/artifacts/tod-weapon-trace" `
  f:0035e710 f:0035e508 f:00695bf8 f:000258c0 f:00027608 `
  f:00465ff0 f:004660a8 f:00465d00 f:00466258
```

### IDA

Load the same ELF with its original virtual addresses as big-endian PowerPC. Choose **File → Script file**, run `Tools/IDA/import_tod_map.py`, then select the JSON. The script targets the IDA 9 [IDAPython interfaces](https://python.docs.hex-rays.com/namespaceida__typeinf.html). IDA was not available for a live import test: syntax, map validation and mocked database-safety tests passed, but runtime compatibility is not yet verified. It does not configure PS3 TOCs or correct function prototypes automatically.

### Checks

```powershell
python -B Tests/TestTodElfMap.py --elf "path/to/EBOOT.ELF" -v
```

Checks cover map bounds/types, duplicates, complete sample-region coverage, original ELF SHA-256/signatures, descriptor enumeration, and IDA importer preflight/preservation behavior. ELF/save originals remained read-only. Neither static analysis nor these checks substitutes for controlled in-game testing.
