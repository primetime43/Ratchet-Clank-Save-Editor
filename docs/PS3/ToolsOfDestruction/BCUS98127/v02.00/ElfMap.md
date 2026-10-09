# Tools of Destruction executable map

Research notes for the supplied USA **BCUS98127 v02.00** `EBOOT.ELF`. This map covers startup, PS3 imports, scripting, physics bindings, rendering/SPU diagnostics, audio/middleware anchors and save I/O. It is a starting point, not a complete reconstruction of the game.

## Parallel save research: rewards, replay lifecycle and mission keys

Three independent passes cross-checked native code, the supplied plaintext snapshot and selected shipped scripts. Derived sections `reward_channels`, `save_tail` and `segment_bindings` contain respectively **43, 40 and 15 exact byte guards**. These are static code-backed meanings and bounded observations, not gameplay-tested edits or a complete reverse engineering claim.

### Reward channels and per-world ladders

Runtime attribute `B3` members `+4/+C/+10` are experience/bolts/raritanium. The experience result from `2CF218` reaches `BA108/BD0A8` through TOC thunk `12710`, carried by messages `6A/6B` at float payload `+90`. Consumer `46BB60` drains both and forwards to `46AAB0 → 4661E0 → 4660A8`, adding to **weapon inventory-record XP `+4`**. This does not establish a connection to serialized hero XP `418`. Bolts/raritanium consumers separately reach saved wallet words `41C/420`.

For world record `W = 488 + level*408`, initialized for20 physical slots (19 named levels):

| World member | Type | Meaning |
| --- | --- | --- |
| `+3E0/+3E4/+3E8` | BE float32 | Cached unassigned experience/bolts/raritanium totals |
| `+3F0/+3F4` | BE uint32 | Separate bolts/raritanium diminishing-return ladder indices |
| `+3F8/+3FC` | BE float32 | Corresponding accumulated remainders, not balances |
| `+403` | Byte | Nonzero reloads saved reward caches |

Segment members `+1C/+20/+24` cache the same three channels. `2CF4C8` computes totals only when cache-ready iszero, requires loaded `level_transitions`, and filters per-channel absolute-value flags. World `+3EC` and trailing `+404..407` stay opaque. The added `TOD_SaveWorldRewardState_verified` type leaves those gaps unknown and does not replace prior types or apply itself to globals.

Flag `200` reward branches in `2CEF70`/`2CEBC0` use table `10026194 = [1,.75,.5,.25,0]`. A committed non-preview call adds its result to the corresponding remainder, subtracts **one** current threshold if reached, and writes index capped at4. Reads occur before that cap, so malformed indices are not safely native-clamped. Bolts in this branch has a minimum returned1; raritanium does not. Runtime budgets/configuration are not recovered from the save, so the inspector does not simulate payouts. Ordinary segment scaling `2CEA00` uses budget thresholds `1/1.75/2.25` and multipliers `1/.75/.5/.25`; nonzero saved `906EC` bypasses that scaling.

All20 actual world cache totals, ladder indices and remainders arezero. This checks locations and raw decoding, **not exercised native ladder behavior**. `World progress` row details now show these fields, raw unknowns and invalid-index warnings; the ordinary four-column presentation is unchanged.

### Native replay context and historical segment median

Native CLI string `10027410 = -replay`, addressed through TOC slot `8A6914`, is compared in parser `48A270`. Exact equality writes1 at saved `906EC` with instruction `48A5D4`, using state pointer `8A6918 = 101EFB20`. This confirms **engine replay/restart context**, not a localized Challenge Mode label or actual number of completed playthroughs. Tail `906E4` still has no semantic name.

Selective restart `3CED40` initializes staging state, preserves settings `114A8..114D8` and all21 grid blocks `114D8..906E4`, resets selected inventory IDs24 and26..31 (predicate `3CEC98`, mask `FD000000`), clears `5550..56D8`, then copies the full `906F0` staging state back. Counter arithmetic is `min(wrapping_u32(old+1),1000)`: `FFFFFFFF` wraps tozero, not1000. Destination request `2D16A0(0,0,1)` differs from alternative staging-copy `3CF1B8`, which requests native destination18 `fastoon_return`. This is not a sufficient specification for safely invoking restart as an editor action.

Saved float `8754` is written at `3CEFEC` **only when the old replay/restart word iszero**. Calculator `3CEB10` scans all200 saved segment `+0C` scalars starting `494`, filters values greater thanzero, sorts descending and returns the median (even count: float32 half the middle pair's sum). Existing finalization defines these as `max(0,runtime baseline+modifier)`; no named completion-time API or time unit has been established. The compatibility JSON key `first_restart_time_median` therefore denotes a **finalized segment scalar/time proxy**, not proof of seconds.

For zero inputs, native code has no guard and reads uninitialized stack scratch. Inspection neither emulates that nor invents azero result. Later restarts skip recomputing the scalar in this path; this is a retained staging aggregate, not guaranteed preservation through every lifecycle. Actual saved `8754` is **4.471639156341553**, bits `408F17AB`, while all current segment inputs arezero and `906EC=3`. That observation is compatible with historical data; it cannot reconstruct the original median inputs. The player summary now displays the saved float and raw engine replay word separately.

### Mission lookup catalog and segment naming limits

Independent registrations `294E90 → 252EB8` and `80848 → 12990` agree on **162 numeric exports: 81 mission title/description pairs**. Named `add_mission` wrapper `2A7680` passes numeric arguments through `2776D8` into the already-mapped saved lookup fields. First pair: `562 = L01_LABEL_MISSION_DEFENSECENTER`, `641 = L01_DESC_MISSION_DEFENSECENTER`. These are native lookup keys, **not localized English mission titles or a fixed mission slot order**. The program resolves known saved IDs to these keys and leaves unknown IDs visible; title/description fields are resolved independently.

Optional read-only Lua5.0 decoding finds32 literal mission calls across11 compiled `missions.lc` scripts; no scripts run. Metropolis script SHA-256 is `7AA1EDAABCE682FACB1D9DFD0159D094EC25F927F5BEAACED0F5952A5513B92A`, and its first observed literal add call uses level0, IDs562/641, optionalfalse. Literal call presence does not prove execution or a complete dynamic mission list. All38 named-world active/completed counts in the actual save arezero, so **no active saved mission identity is confirmed by this snapshot**.

Physical segment names remain unresolved: `2D18C8` hashes nonempty names using33×accumulator modulo49 (empty returns40); `2D1928` reads runtime table memberC8, and `2D1A08` resolves loaded name pointers. The lookup itself does not establish a collision-free static dictionary. Retained log order or script symbols cannot name all ten saved physical slots without recovering the configuration loader/table.

Reproduction tools (all read-only; `--save` accepts the detached plaintext working copy):

- [Inspect-TodRewardChannels.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodRewardChannels.py): `--elf <exact ELF> --save <plaintext>`; matching test covers six checks.
- [Inspect-TodSaveTail.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSaveTail.py): same arguments; seven checks including raw nonfinite values, unsigned wrap, empty-input caveat and unchanged originals.
- [Inspect-TodSegmentBindings.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSegmentBindings.py): same arguments, optional `--archive <global_cached.psarc>`; six checks including independent exports, hostile list bounds and literal compiled-script relationships.

## Files to use in IDA or Ghidra

- [Shared address map](maps/NativeMap.json): 1205 annotations, 118 imports, evidence, byte signatures and 32 structure definitions.
- [Ghidra importer](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Ghidra/ImportTodMap.java): applies labels, plate comments and data types.
- [IDA importer](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/IDA/import_tod_map.py): IDAPython script for labels, repeatable comments and local types; no IDC needed.
- [Save-format notes](../../SaveFormat.md): file-relative offsets, inventory records and wrapper headers.

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

Modifier helper `0x465D00` ORs a selected bit into record `+0x0C` and refills ammo if maximum changes. Calculation `0x466258` walks weapon-data entries at `+0x464`, stride `0x18`, count at `+0x6A4`; enabled bits select entries matching an attribute ID. Kind zero adds a float, other kinds accumulate a multiplier. Maximum ammo chooses attribute 9 and a base value at weapon-data `+0x280 + 4*level`. The packed assets provide node indices, label tags, costs and XP/ammo tables. Native bindings now link all 32 inventory IDs to named configurations, and vendor bytecode supplies upgrade grids and UI checks below. **Runtime overrides, safe edited-save masks and gameplay-validated bounds remain unresolved.** This modifier helper alone does not describe a complete upgrade purchase.

The JSON `serialization` section records the state/copy chain, field offsets and exact instruction guards. The `TOD_SaveInventoryRecord_verified` type supersedes candidate field names without overwriting an existing analyst's `TOD_SaveInventoryRecord_observed` type. Both remain available because importers preserve existing types. Armor, skill points and gameplay-record tail provenance are mapped below; saved health remains unresolved. No new editable fields were enabled, and a matching layout is not a cross-region load test.

### Ownership unlocks and acquisition

| Function or field | Established behavior |
| --- | --- |
| `0x466A60` | Initializes exactly **32** records, IDs 0–31, stride `0x14`, then clears word `+0x280`. The count is now code-backed, not merely an observed sample pattern. |
| `0x466B70` | Acquisition helper: can refill ammo according to item-definition flags; on a previously unowned item, sets record `+0x10` to 1, delegates XP/level initialization, increments word `+0x280`, and can set global flag10 `HERO_HAS_TWO_ITEMS` in the BE64 word at `+0x5528`. This event flag is not a continuously maintained item-count predicate. |
| `0x466AE8` | For an owned record, delegates XP/ammo resets, clears `+0x10` and decrements word `+0x280`. |
| `0x465DC0` | Absolute ammo setter, clamped using the maximum from `0x463DE0` and a zero constant; stores float `+0x08`. |
| `0x2BB778 → 0x28B4E8` | Named `hero_give_weapon` binding. Native code checks ID 0–31 and hero context, calls acquisition with refill enabled, delegates inventory integration, optionally sets XP and ammo, and can notify another system. |
| `0x2A4EC0 → 0x27A5B8` | Named `unlock_weapon` binding. Sets byte `state + 0x5754 + ID` to 1, using pointer slot `0x898F50 = 0x101EFB20`. This is **separate from possession** at record `+0x10`. |
| `0x2D24C0` | Availability predicate uses the unlock byte, definition flag 2 and ownership. An unlocked item is not automatically already owned or purchasable. |
| `0x2D1EF8` | Modifier index must be below definition entry count at `+0x6A4`, item must be owned, and mask bit must be unset. Price, adjacency and all other purchase prerequisites are not established by this predicate. |
| `0x2D2430` | Reads saved word `+0x420`, independently corroborating the existing raritanium offset. |

Word `0x280` is updated as an acquisition/removal counter, but it is **not asserted equal to the number of nonzero ownership bytes**. The reference sample has counter 46 and 32 nonzero record flags. This may reflect other writers, prior edits or another invariant; these routines alone do not settle it. Do not automatically normalize the counter to 32.

The total unlock-array length is not established. The comparison tool decodes only the 32 IDs whose inventory records are mapped; the larger byte region still contains unknown state. Named `purchase_weapon` wrapper `0x337D8 → 0x26638` branches through thunks to `0x2D21A8` or `0x2D2D38`. The latter is now traced: it requires a hero, applies an extra condition for ID `0x13`, obtains price via `0x2D2058`, checks inventory bolts at `+0x41C`, calls acquisition/refill `0x466B70`, delegates hero inventory integration through `0x252B08`, and deducts the price through `0x24FCB8`. It also conditionally dispatches through a virtual method and sends further notifications. This leaf does not establish every vendor prerequisite or the complete semantics of those downstream calls. A one-byte edit is not a complete purchase.

The auxiliary initializer `0x35DC80` clears currency and initializes a 32-word sentinel list at `0x284`, three 23-word arrays at `0x304/0x360/0x3BC`, and other state. Their complete meanings remain unknown. The restart-style routine `0x3CED40` copies and selectively resets state, including some records, then increments/clamps word `0x906EC`; **native engine replay terminology is now confirmed by the `-replay` CLI store; localized challenge-mode interpretation remains unverified**, not a confirmed editable field. These are additional leads, not imported original function names.

### Progression, skill points and armor

The supplied encrypted `BCUS98127_SAVE_1` now provides a same-title USA reference alongside the original European plaintext sample. The normal editor decryption path produced a private plaintext snapshot without changing any original files. Its non-private observations are in `usa_reference_save`; see [save-format notes](../../SaveFormat.md#code-backed-progression-and-armor) for hashes and values. An encryption round-trip on a disposable clone is not an in-game load test.

The key pointer proof is initializer `0x23E650`: `0x23E73C` loads TOC slot `0x897B38`, whose word is `0x101EFB20`; `0x23E744` stores it into hero member `+0x1A68`. Hero member accesses therefore refer to the identified serialized block, not an arbitrary runtime object.

| Native function / chain | Verified behavior |
| --- | --- |
| `get_current_skillpoints: 0x2EA30 → 0x27358` | Reads weighted total at state `+0x8708` |
| `is_skillpoint_done: 0x27A700` | Tests BE64 integer bit ID at state `+0x8710`; named IDs0..59 |
| `set_skillpoint_done: 0x27A6A0 → 0x35D5D0` | Slot `0x898FF4` points to state `+0x5528`; subobject `+0x31E0/+0x31E8` are save `0x8708/0x8710` |
| `0x35D5D0` | Returns on already-set bit; otherwise sets bit and adds definition points; tests IDs0..58 to award ID59 |
| `0x35EB00` | Definition points at table `0x10026654 + ID*0x10` |
| `get_skillpoint_name: 0x2E6D0 → 0x257B8 → 0x11F60 → 0x35EB70` | Loads definition `+4` name tag at `0x35EBA4` and localizes it |
| `get_skillpoint_desc: 0x2E5A8 → 0x256F8 → 0x10540 → 0x35ECD8` | Loads definition `+8` description tag at `0x35ED0C` and localizes it |
| `is_armor_owned: 0x32230 → 0x25F70 → 0x10FF0 → 0x2D2400` | Tests nonzero uint32 at save `0x444 + ID*4` |
| `hero_get_armor: 0x28A290 → 0x2510D8 → 0x1E2140` | Reads equipped ID at save `0x458` |
| `hero_set_armor: 0x28A3C0 → 0x252098 → 0x1E2150` | Writes save `0x458`, marks corresponding ownership word, updates runtime attribute |
| `0x2D2440` / `0x2D2588` | Read/update five armor unlock bytes at save `0x5774`; slot `0x89F1DC` is `0x101F5294` |
| `purchase_armor: 0x32080 → 0x25F18 → 0x12FB0 → 0x2D26D0` | Checks bolts/equipped ID, marks ownership, deducts price, delegates equip and notifications |
| `0x1E2568` / `0x1E25F0` | Read/reset/update saved float `0x428`; update clamps 1..20 |
| `0x2D1860` | Returns whether saved word `0x906EC` is nonzero; called by multiplier and armor availability |

Native registration `0x294E90` exports all 60 `SKILLPOINT_*` IDs and count60; registration `0x28440` exports the five `ARMOR_*` IDs and count5. [Inspect-TodProgression.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodProgression.py) decodes their literal float exports and TOC name pointers, not string order or guessed enum numbering. It also reads all 60 definition records: points, name tag, description tag and **unknown** member `+0xC`. Localization tags are numeric IDs, not direct pointers or recovered English descriptions. Runtime localization branches are not fully reconstructed.

The shared `progression` section contains **478** additional original-ELF byte guards and the complete catalogs. The types `TOD_SaveArmorState_verified` (relative to save `0x444`) and `TOD_SaveSkillPointState_verified` (relative to `0x8708`) are added without replacing prior types. Raw BE64 bit order and unknown high bits are explicitly documented. The program embeds the map and displays these findings read-only.

Multiplier use is traced through cross-TOC thunk `0x251518 → 0x1E2568`; `0x2D073C` calls it, `0x2D0744` retains its float result in f31, and `0x2D02F8` multiplies it in the consumer. Do not treat this as a complete reconstruction of that consumer's reward/side-effect logic. Raw PPC instructions remain authoritative: the decompiler can omit TOC-restoration and float semantics.

Save `0x418` is now confirmed as serialized integer hero XP by the named setter chain below, not current health or a directly stored level. The tail word `0x906EC` has confirmed engine replay/restart context from the native `-replay` CLI store, but is not a confirmed count of completed playthroughs. Neither field gained an editable control.

### Packed weapon configuration and native field bindings

The supplied game's `packed/game/global_cached.psarc` contains plaintext `weapon.csv`, `mods.csv`, `vendor.csv` and their Lua loaders under `/data/configs/`. Selective extracts remain under ignored `artifacts/tod-assets-v02.00/`; no archive, Lua source, compiled code or game binary is tracked. The six SHA-256 fingerprints are recorded in the JSON map's `weapon_configuration.assets` section and the report tool.

This particular archive has 3,297 entries, version `0x00010002`, `zlib` compression, 30-byte TOC records and 64 KiB blocks. All 3,296 filename hashes match **ASCII-uppercase full manifest paths**, including their leading slash. Filename MD5s are not payload-integrity hashes. The independent [archive inspector](../../../../../Tools/Inspect-Psarc.py) follows the field/block layout corroborated by this [primary PSARC extractor implementation](https://raw.githubusercontent.com/rscustom/rocksmith-custom-song-toolkit/master/RocksmithToolkitCLI/generalscripts/psarc-extract.rb); uppercase normalization is an observation from these ToD bytes, not assumed for every PSARC variant.

The [configuration report](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWeaponConfigs.py) parses numeric literals without executing Lua or expressions. It reports all 28 named weapon/gadget configurations, all per-level variables, 204 modifier entries across 15 weapon groups, vendor weapon/armor records, node masks, costs and localization tags. The 204 entries include 15 `MOD_START` entries: they are not 204 purchasable upgrades. These are shipped **asset definitions**, not independently captured runtime configuration or safe editor limits.

Loader rules established by reading the source:

- `weapon.lua` maps Lua column 4 to level index 0, column 5 to index 1, and so on. `NumLevels` stores the largest populated zero-based index, not a count. Blank cells are unspecified; the report does not fill them from previous levels.
- `mods.lua` maps the CSV node index directly to `Mods[index]`; `NumMods = index + 1`. `PERCENT` values are multiplied by `0.01`, while absolute values are left unchanged. Some `MOD_SPECIAL` rows deliberately omit numeric values, and negative percentage values exist. Neither blank nor negative automatically means corrupt data.
- `vendor.lua` assigns named fields under `config.<weapon>.Vendor`; it also populates armor vendor configuration. Its unlock strings are level identifiers, not save offsets or inventory possession flags.

The ELF independently binds several names to the previously traced native offsets. Registration routine `0x80848` passes named strings and getter/setter descriptors into Lua property registration. Confirmed descriptor TOC is `0x88FF38`; raw instructions and float stores resolve decompiler ambiguities.

| Named property | Native accessors | Runtime field |
| --- | --- | --- |
| `MaxAmmo[index]` | Get `0xB8840`, set `0xB8728` | Weapon config `+0x280 + index*4`, float32; index check allows **0–19** |
| `NumMods` | Get `0xB4870`, set `0xA73A0` | Weapon config `+0x6A4`, word |
| `Mods[index]` | Get `0xB7B30`, set `0xB79E0` | Weapon config `+0x464 + index*0x18`; index check allows **0–23** |
| Modifier cost | Native `0x2D1E80` | Modifier entry `+0x0C`, word; equivalent config `+0x470 + index*0x18` |
| `Vendor` | Get `0x99B20` | Subobject at weapon config `+0x6A8` |
| `Vendor.BasePrice` | Get `0xB4BB0` | Vendor `+0`, hence weapon config `+0x6A8` |
| `Vendor.AmmoPrice` | Get `0xB4AE0` | Vendor `+4`, hence weapon config `+0x6AC` |
| `Vendor.MegaPrice` | Get `0xB4A10` | Vendor `+8`, hence weapon config `+0x6B0` |
| `config.Combuster` | Get `0x971E0` | Parent configuration `+0x1CFC`, **not** a save offset |
| `config.Grenade` | Get `0x96FD0` | Parent configuration `+0x3178`, **not** a save offset |

The maximum-ammo array has **20 native slots**, but the supplied CSV defines ten levels for each of the 15 upgradeable weapons. Capacity does not establish 20 playable levels. The registration also exports `MOD_AMMO = 9`: float constant `9.0` at `0x88B334` is passed with the `MOD_AMMO` string, matching attribute 9 used by `0x466500`. Price selector `0x2D2058` chooses `AmmoPrice` for definition flag 2, otherwise `BasePrice`; the promotion path uses `MegaPrice`.

The table below summarizes the assets using **internal configuration names**, not player-visible localized weapon names. Their native ID links are listed in the next section. “Ammo +mods” is the arithmetic result of enabling every listed `MOD_AMMO` node; it does not claim that every mask is attainable or accepted. All listed ammo modifiers in these assets are absolute additions.

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

Combuster's full XP threshold array is `[0, 1000, 2200, 3640, 5368, 5500, 20000, 37400, 58280, 83336]`. Its node 12 is `MOD_DURATION`, absolute `4`, cost `300`, with localization tags identifying the special burn-patch upgrade. Its complete CSV node catalog spans 0–13; the reference save's record 1 modifier word `0x3FFE` enables bits 1–13. The ID link is independently confirmed by native constructors and enum exports, not inferred from this mask. The vendor script treats node 0 as the start without requiring ownership bit 0.

Other configurations are Wrench, Groovitron, MiniLeech, ConfusionGas, Zurkon, MaxiLeech, Copter, Morph, Slinkonator, SwingShot, Inflatopod, Gelanator and Decryptor. The first group has only index-0 values; the last four have two populated XP columns but only one populated ammo column. Do not invent missing gadget levels/ammo values. CSV order differs between weapon and vendor tables and must not be used to label the 32 save records.

Reproduce without modifying the game:

```powershell
# Create a separate, ignored output folder first. Each --out must be a new file.
python -B Tools/Inspect-Psarc.py "path/to/global_cached.psarc"
python -B Tools/Inspect-Psarc.py "path/to/global_cached.psarc" `
  --name /data/configs/weapon.csv --out artifacts/tod-assets-v02.00/weapon.csv
# Repeat explicitly for weapon.lua, mods.csv/.lua, and vendor.csv/.lua.
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWeaponConfigs.py artifacts/tod-assets-v02.00
python -B Tests/TestPsarc.py --archive "path/to/global_cached.psarc" -v
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodWeaponConfigs.py --assets artifacts/tod-assets-v02.00 -v
```

The archive tool refuses existing outputs and extraction into the original archive directory. Bounds, decompression size, malformed manifests, untrusted names and overwrite protection are fixture-tested. Reference tests verify matching extracted hashes and unchanged original archive/assets. Native IDs and vendor adjacency are now mapped below; runtime overrides and edited-copy gameplay validation remain open. No new editor fields are enabled by these findings.

### Native inventory ID catalog

All **32** IDs are now linked through three independent native evidence paths: numeric Lua `WPN_*` exports in registration `0x80848`, constructor arguments to common registration `0x466798` (or cross-TOC thunk `0x11210`), and named configuration getters from property table `0x88ED20`. Constructors pass ID in `r4` and the configuration pointer in `r5`; the common constructor stores them at definition `+0` and `+0x48`. CSV row order is not used.

The MonolithicConfig root getter is `0x94400`; pointer slot `0x88FAFC` contains runtime address `0x101B9EE8`. Named weapon subobjects are `0x6D4` bytes apart in a different order from inventory IDs. For example, Combuster getter `0x971E0` returns root `+0x1CFC = 0x101BBBE4`; constructor `0x470378` passes that pointer with ID 1. These are **runtime configuration addresses**, not save offsets or extracted asset bytes.

| ID | Native config name | Save record offset |
| ---: | --- | --- |
| 0 | Wrench | `0x000` |
| 1 | Combuster | `0x014` |
| 2 | Grenade | `0x028` |
| 3 | Ravager | `0x03C` |
| 4 | Tornado | `0x050` |
| 5 | BuzzBlade | `0x064` |
| 6 | Predator | `0x078` |
| 7 | AlphaNova | `0x08C` |
| 8 | FlameThrower | `0x0A0` |
| 9 | GoopMine | `0x0B4` |
| 10 | Reaper | `0x0C8` |
| 11 | Rocket | `0x0DC` |
| 12 | RoboHive | `0x0F0` |
| 13 | MagNet | `0x104` |
| 14 | EnergyClaws | `0x118` |
| 15 | Ryno | `0x12C` |
| 16 | Zurkon | `0x140` |
| 17 | ConfusionGas | `0x154` |
| 18 | Slinkonator | `0x168` |
| 19 | Groovitron | `0x17C` |
| 20 | MiniLeech | `0x190` |
| 21 | MaxiLeech | `0x1A4` |
| 22 | Morph | `0x1B8` |
| 23 | Copter | `0x1CC` |
| 24 | Inflatopod | `0x1E0` |
| 25 | SwingShot | `0x1F4` |
| 26 | CuttingLaser | `0x208` |
| 27 | Gelanator | `0x21C` |
| 28 | RoboWings | `0x230` |
| 29 | MagCycle | `0x244` |
| 30 | PirateGadget | `0x258` |
| 31 | Decryptor | `0x26C` |

The JSON `inventory_catalog` records enum names, instruction addresses, pointer slots, getters and offsets for every row, with **264** separate catalog byte guards. Internal enum/config names need not match: `WPN_VISICOPTER` maps to `Copter`, `WPN_PIRATEGUISE` to `PirateGadget`, and `WPN_MAGCYCLE` to `MagCycle`. CuttingLaser, RoboWings, MagCycle and PirateGadget have native bindings but no rows in the six extracted configuration files; do not invent their asset defaults.

The [native binding inspector](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWeaponBindings.py) verifies the exact ELF size/hash before decoding bounded, observed PPC patterns. It is not a general emulator. Assembly traces independently corroborate the arguments and getter offsets. The acquisition counter at save `0x280` remains unexplained (sample 46); the new catalog does not justify replacing it with the number of owned items.

### Vendor upgrade grids and purchasing

Archive entry `/built/anark/weaponvendor/built.dat` is 390,796 bytes, SHA-256 `294BA05A607BC5C4C59B60E85C57515DBBD8CDEECC9CB6BF570AE4AE937627D5`. Its `weaponUpgradeHandler` chunk spans **file** offsets `0x54F85–0x5E78A` (exclusive end), not ELF VAs. The chunk is Lua 5.0 with little-endian integers and float32 numbers, unlike the big-endian native executable. The bounded [Lua reader](../../../../../Tools/Inspect-Lua50.py) follows the official [chunk field ordering](https://www.lua.org/source/5.0/lundump.c.html) and [5.0 instruction encoding](https://www.lua.org/source/5.0/lopcodes.h.html); it never executes Lua. In particular, Lua 5.0's A field is at bit 24 and its register/constant operand boundary is 250, not the familiar Lua 5.1 layout.

Static literal-table recovery from `initWeaps` yields **15 grids**, each four rows by seven columns. Every nonnegative node index matches its named CSV group, totaling 204 entries including the 15 starts. The JSON stores all grids and selected method offsets. Globals such as `WPN_COMBUSTER` remain symbolic while decoding; no game environment is executed or assumed.

| Script method | Bytecode file offset | Observed behavior |
| --- | --- | --- |
| `initWeaps` | `0x5C6E1` | Builds weapon, grid and special-node tables |
| `canBePurchased` | `0x56A8A` | Normal node: any orthogonal neighbor purchased; special node: returns true directly |
| `beenPurchased` | `0x56CFC` | Missing cell: false; node 0: true without checking bit 0; otherwise calls `is_mod_owned` |
| `specialCheck` | `0x56ECE` | Missing/nonpositive cell: true; positive cell: must be owned |
| `is_valid_movement` | `0x56781` | Special-node selection requires all four neighbor `specialCheck` results |
| `onSelect` | `0x5A7F8` | Checks native `is_mod_available` and `canBePurchased`, excludes node 0, then calls `purchase_mod` |

Special-node icon handling (`showIcon`/`copyIcon`) also checks all four neighbors. Thus special selection/icon gating, the `canBePurchased` predicate and the native purchase transaction are **different checks**. Do not describe the native function as enforcing the entire prerequisite graph.

Combuster grid (rows/columns are one-based in the script):

```text
-1 -1  4 11  3 -1 -2
 0  2  7 -1 13 -1 -2
-2 -1  8 -1 12  5 -1
-2 -1  6  9  1 10 -1
```

Its special node 12 is at row 3, column 5; adjacent positive nodes are **1, 5 and 13**, all required by special navigation/icon checks. Node 2 neighbors start node 0, so it is the first ordinary node eligible without any purchased bits. Negative marker semantics are not fully identified. Ryno's special marker is `-3`, not a positive purchasable node.

Native transaction `0x2D2878` requires a hero, nonzero record ownership at `+0x10`, and sufficient raritanium at inventory `+0x420`. It gets cost through `0x2D1E80`, enables the bit via `0x465D00`, and deducts the cost via `0x24F748`. This leaf does not enforce grid adjacency or an already-owned-bit check. The cost getter returns zero for missing definitions/configurations or indices outside `NumMods`; that does **not** establish an out-of-range node as safe to purchase.

The `Mods` getter/setter allow **24 entries**, stride `0x18`, base `+0x464`; getter compare at `0xB7BD8` allows indices 0–23. This also agrees with `(0x6A4 - 0x464) / 0x18 = 24`. A 32-bit saved mask does not establish 32 native modifier slots. Only cost at entry `+0x0C` is newly named here; other entry member offsets must be confirmed individually before expanding structure definitions.

Reproduce the new read-only reports and checks:

```powershell
# Use a new output file; never overwrite the original archive or assets.
python -B Tools/Inspect-Psarc.py "path/to/global_cached.psarc" `
  --name /built/anark/weaponvendor/built.dat --out artifacts/tod-assets-v02.00/weapon-vendor-built.dat
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWeaponBindings.py "path/to/EBOOT.ELF"
python -B Tools/Inspect-Lua50.py artifacts/tod-assets-v02.00/weapon-vendor-built.dat `
  --offset 0x54F85 --vendor-layout
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodWeaponBindings.py --elf "path/to/EBOOT.ELF" --assets artifacts/tod-assets-v02.00 -v
python -B Tests/TestLua50.py --asset artifacts/tod-assets-v02.00/weapon-vendor-built.dat -v
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodElfMap.py --elf "path/to/EBOOT.ELF" -v
```

Tests cover malformed/bounded chunks, endian/number layouts, operand encoding, literal-grid recovery, native ID/offset links and matching CSV nodes, plus unchanged reference files. Static graph recovery is not proof that edited saves load or that these USA executable findings apply to every region/version. New UI editing remains deferred until runtime validation of disposable copies.

### External editor references

The user-supplied [rac-savegame-editor definitions](https://github.com/maikelwever/rac-savegame-editor/blob/master/RACSaveGameEditor/GameItems.cs) independently list ToD bolts `0x41C` and raritanium `0x420`; its ToD section contains no weapon fields. Its [save-container implementation](https://github.com/maikelwever/rac-savegame-editor/blob/master/RACSaveGameEditor/SaveGameContainer.cs) is a lead for format detection, but its fixed SFO seek is not a replacement for parsing the metadata table.

The project's README points to [Slim's Editor](https://github.com/RatchetModding/slimseditor), now under RatchetModding. At commit `e4cd47d2bb65566dca66799669f2672fd7a5f395`, its [ToD JSON](https://github.com/RatchetModding/slimseditor/blob/e4cd47d2bb65566dca66799669f2672fd7a5f395/slimseditor/game/tod.json) also contains only the two currency definitions. Neither source supplies the missing ToD XP thresholds, upgrade-node catalog or in-game validation. These are corroborating references; no third-party implementation code was copied or executed.

## Hero XP special bolts and skins

The `collectibles` section records 267 original-byte guards, native script registrations, all19 level IDs and all9 skin IDs. [Inspect-TodCollectibles.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodCollectibles.py) independently reproduces it from the exact reference ELF and optionally observes a plaintext save without writing either input. Complete native function bytes and TOC-changing thunks are retained, including the collectible setter's automatic skill-point award.

| Verified chain or routine | Result |
| --- | --- |
| Named `hero_set_xp`, `0x2BAED0 → 0x28A9B0 → 0x252C78 → 0x23E090` | Saved uint32 XP at `0x418`; store at `0x23E0F4`; hero saved-block member `+0x1A68` |
| `get_special_bolts_collected`, `0x30AE8 → 0x25CF0 → 0x119B0 → 0x35DDD8` | Popcount saved BE32 mask `0x874 + level*0x408`; argument19 sums19 levels |
| `get_special_bolts_total`, `0x309D8 → 0x25C60 → 0x10D70 → 0x2D0898` | Definition table `0x10062E4C`, 19 uint32 totals, sum32 |
| `get_special_bolts_owned`, `0x308F8 → 0x25DB8` | Collected sum minus saved spent word `0x424`, signed32 |
| Bit test `0x35DE08`, setter `0x35DEB0` | Local ID0..31 selects integer bitID in record member `+0x3EC`; completing all per-level totals awards skill46 `GOLDEN` |
| `is_skin_owned`, `0x30180 → 0x24B08` | Nonzero saved uint32 `0x45C + ID*4`, nine IDs |
| `select_skin`, `0x300A8 → 0x26FC0` | Ownership gate, then saved selected ID `0x480` |
| `purchase_skin`, `0x30330 → 0x27AA0` | Checks balance/cost; updates ownership, selection and spent word, then sends runtime notification |
| `is_skin_available`, `0x30258 → 0x24B38` | True except ID7 whose ownership determines availability |
| Cost leaf `0x1F0D60` | uint32 at `0x840B00 + ID*0x10`; nine static prices `(0,6,3,6,6,4,4,0,3)` |

State pointer `0x888624` is `0x101EFB20`; collectible getter arithmetic uses shifts10 and3, establishing stride `0x400+8`, then adds `0x488`. Popcount helper loads record member `+0x3EC`, giving saved mask base `0x874`. Twenty records initialized by `0x35E110` cover `0x488–0x5528`; native level exports stop at ID18, with `LEVEL_COUNT=19`. Do not conflate the sum selector with the initialized extra slot. Remaining record contents are not assigned guessed meanings. Added analysis types are `TOD_SaveLevelCollectibleState_verified` and `TOD_SaveSkinState_verified`; types preserve all opaque bytes.

The USA plaintext working copy has XP2,315,144; collected32, spent32, balance0; selected skin0; ownership set for all skins except ID7. Static owned prices sum32 in this sample but are not enforced as a save invariant. Neither the observation nor the mapped transactions proves safe edits or console acceptance. Runtime `hero_get_health` does not identify a saved health word through this research.

The original `TOD_hero_progression_restore_candidate` label is retained at `0x23E090` for existing analysis databases, but its confidence/comment now establish XP via the named binding. No executable or original save bytes were patched.

## World progress mission counters and quick select

The shared `world_state` section and [Inspect-TodWorldState.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWorldState.py) independently reproduce 19 native level rows and 205 original-byte guards from this exact ELF. Newly imported types preserve opaque bytes: `TOD_SaveLevelProgressState_verified` refines the older collectible type without replacing it; `TOD_SaveMissionCounterRecord_verified` maps only its final counter; `TOD_SaveQuickSelectStorage_verified` stores raw ID bits with signed interpretation in its comments.

| Named binding / native path | Proven storage or behavior |
| --- | --- |
| `is_level_unlocked`: `0x30768 → 0x24AD0` | Nonzero byte `save+0x888+0x408*level` |
| `is_level_visited`: `0x30690 → 0x279F8` | Nonzero byte `save+0x889+0x408*level` |
| `is_level_seen`: `0x399F0 → 0x37460` | Same saved byte as visited |
| `is_level_visitable`: `0x39BA0 → 0x36A10` | Nonzero level ID, unlocked and clear record member `+0x402`; suppresses level3 when level18 qualifies |
| `is_level_visible`: `0x39AC8 → 0x36AC8` | Delegates to visitable; not another saved boolean |
| `get_level_missions_completed`: `0x395A0 → 0x36FC0 → 0x12470 → 0x2D0EF0 → 0x2D0DF0` | Save `0x10AF8+0x7C*level`, member `+0x78`; menu remaps level3 to18 under visibility condition |
| `hero_add_quick_select`: `0x2B8780 → 0x288988 → 0x252B08 → 0x1E26F0` | Stored item IDs at `0x284`; automatic insertion searches 24 slots and filters config flags `0x1040` |
| `hero_remove_quick_select`: `0x2B8650 → 0x288888 → 0x252ED8 → 0x1E22A8` | Scans 32 words; replaces matching IDs with `0xFFFFFFFF` |
| Membership helper `0x1E22F8` | Scans all 32 stored quick-select words |

Pointers `0x888624`, `0x889AF4`, `0x89550C` and `0x89F16C` all resolve to serialized base `0x101EFB20`. World stride is derived from shifts10+3; mission stride from shifts7−2. Assembly proves the mission-counter load at `0x2D0F04`, the insertion bound at `0x1E2730`, its automatic-search count at `0x1E27F0`, and removal's 32-word loop. Thunks restore/change TOCs explicitly; decompiler output alone is not used for these displacements.

The USA snapshot has all32 quick-select slots empty, all19 mission counters/unlocked/exclusion bytes zero, and only native level0 visited. This surprising observation is retained without inferring current runtime progress. See the [save-format notes](../../SaveFormat.md#confirmed-world-progress-and-quick-select-storage) for limitations and reproduction checks. No completion percentage, wheel position, mission-ID catalog or safe edit range is established.

### Global event flags: named story, tutorial, movie and equipment bits

[Inspect-TodGlobalFlags.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGlobalFlags.py) independently reproduces the `global_flags` section using two separate enum registrations and six named API wrappers from this exact ELF. Its **509 coalesced byte guards** cover both export ranges, names/value pointers, native readers/writers, initialization and the acquisition consumer. [TestTodGlobalFlags.py](../../../../../Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodGlobalFlags.py) checks agreement, BE64 byte order, word boundaries, unknown high bits, rejected inputs and unchanged actual save/ELF bytes.

The storage is **five BE64 words at save `5528–5550`, end exclusive**. Initializer `35E110` passes `save+5528` to `35D9A0`; stores at `35D9D0..35D9E0` explicitly clear members20/00/08/10/18. This confirms320 physical bits, not320 named or valid script flags. Enum registrations `28440 → 12990` and `294E90 → 252EB8` independently agree on **IDs0..291**; both export `GLOBAL_FLAG_COUNT=292`. The higher28 physical bits292..319 are unresolved. COUNT is not a flag name or proof of a safe native upper bound.

| API | Menu-side wrapper / native | Gameplay-side wrapper / native |
| --- | --- | --- |
| check_flag | 34750 /27948 | 2CB138 /2770F0 |
| set_flag | 34698 /24A80 | 2CB080 /27BB10 |
| clear_flag | 345E0 /27988 | 2CAFC8 /27BAE0 |

Both families resolve saved-state base `101EFB20` through their descriptor-specific TOCs (`888624` /`898F50`). Native getters/writers select **word `floor(id/64)` and integer bit `id%64`**. File byte is `5528+8*floor(id/64)+7-floor((id%64)/8)`, byte mask `1<<(id%8)`. Setting ORs the mask; clearing AND-NOTs it; checking returns a boolean. Native leaves have **no GLOBAL_FLAG_COUNT range check**. The read-only inspector bounds access to these five physical words instead of following arbitrary script IDs.

Examples from the complete292-entry catalog:

| ID / native identifier | File byte / mask | Evidence limit |
| --- | --- | --- |
| 3 / HERO_FIRED_WEAPON | 552F /08 | Native event name, not current ammo or firing eligibility |
| 10 / HERO_HAS_TWO_ITEMS | 552E /04 | Acquisition writer independently confirmed below |
| 32 / RYNO_COMPLETE | 552B /01 | Separate flag, not a replacement for inventory/blueprint state |
| 74 / LVL_IFF_CHALLENGE_1_DONE | 5536 /04 | Story/menu-list gate; not the numeric win counter |
| 75 / LVL_IFF_CHALLENGE_2_DONE | 5536 /08 | Story/menu/training gate; independent of arena counters |
| 183 / MOVIE_METROPOLIS_INTRO | 5539 /80 | Internal movie-event identifier, not recovered movie text |
| 275 / MAGNETIZER_ACQUIRED | 554D /08 | Separate event bit; usable equipment state not established by it alone |
| 276 / MAPOMATIC_ACQUIRED | 554D /10 | Separate event bit |
| 285 / BOXBASHER_ACQUIRED | 554C /20 | Separate event bit |
| 286 / GOLDENGROOVITRON_ACQUIRED | 554C /40 | Separate event bit |
| 287 / TREASURE_MAPPER_ACQUIRED | 554C /80 | Separate event bit |

Acquisition `466B70` tests mask400 in the first BE64 word and the acquired item's definition flag2. If the global bit is clear and that definition flag is set, it scans32 owned records, counts entries whose definitions also have flag2, and sets mask400 when the count exceeds1. Both independent enum catalogs identify bit10 as **HERO_HAS_TWO_ITEMS**. This confirms the named relationship, not a continuously recomputed inventory invariant or its reset policy. Do not repair the global flag merely from an owned-item count.

The exact archive's shipped source offers an additional distinction. In `packed/game/global_cached.psarc`, entry2476 `/levels/imperial fight fest/scripts/arena.lua` (4026 bytes, SHA-256 `774C349B4C66E11EF878509079DDDEEB95BA8FABA318264CC45031EFA47C907B`) selects first-visit challenge lists at lines55–63 using flags74/75. Lines117–131 also use flag75 with the separate training flag and can set the left-after-Crushto flag. Entry2478 `arena_2.lua` (5389 bytes, SHA-256 `5E27723DCED186EA87354F792A63DCDC21CA72F54B831A99FC1EF227B4C485F2`) checks return-challenge flags before running scripts at lines81–94. Both sources separately derive some `.active` values from **numeric `get_challenge_successes(...id)>0`**. These are static source observations; payloads were read only, not executed, and commented-out alternative checks are not treated as live logic. Numeric win counters and global story bits are therefore not interchangeable; exact runtime synchronization remains unverified.

**Actual USA observation:** all five words are zero, so no named or unknown tail bit is set. This surprising snapshot is preserved without inferring that the player has completed no story events. The app's **Global event flags** view shows group, formatted native identifier and Set/Clear; Technical retains all320 bits, exact byte/mask/word offsets and raw BE64 values. Labels are not recovered localized titles; Clear is not universally equivalent to unfinished. No new flag editing controls are enabled.

Portable `TOD_SaveGlobalFlags_verified` represents the five words as five8-byte arrays to preserve exact layout using the shared importer types. It is not automatically applied to globals/save bytes, and older analyst types/names remain intact.

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGlobalFlags.py --elf artifacts/ghidra/BCUS98127-02.00/EBOOT.ELF --save artifacts/tod-research-capture/USA-GAME.plaintext.bin
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodGlobalFlags.py --elf artifacts/ghidra/BCUS98127-02.00/EBOOT.ELF --save artifacts/tod-research-capture/USA-GAME.plaintext.bin
```

### Remaining native leads, not promoted to saved-field names

`get_times_challenge_completed` registration at `0x88944C` reaches wrapper `0x315A8`, native `0x279B8`, then TOC thunk `0x110B0 → 0x2756F8`. This menu resolver reads `ARENA_CHALLENGE_DATA[argument].id`, caps the resolved index at23 and reads `save+0x56D8+4*resolvedIndex`. Its table/order and lower-bound safety remain unresolved. Independent direct-ID API and initializer evidence now establish **23 counters, not24**, as documented below. Index23 would alias the separate unknown array at5734; the menu cap is not a valid-counter count.

`get_current_level` leads to runtime pointer access (`0x30840 → 0x25C30 → 0x109E0`), not a demonstrated saved planet field. `hero_get_equipped` (`0x2B7F70 → 0x288060 → 0x466EC0`) traverses a runtime inventory object; the equipment-history section below establishes its link to saved `0x42C/0x430/0x434`. The three initialized 23-word arrays at `0x304/0x360/0x3BC` are mapped below through named object APIs. A numeric resemblance or initializer alone is insufficient proof.

## Native object counters and equipment

Two enum exporters (`0x28440 → 0x12990` and `0x294E90 → 0x252EB8`) agree on all23 `OBJ_` IDs and the count sentinel23. [Inspect-TodObjects.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodObjects.py) independently reproduces those IDs and the three saved arrays, with 205 exact-byte guards and named registrations. All23 native object-name strings and their accessor/thunk chains are importable; `TOD_SaveObjectCounters_verified` preserves signed-current interpretation as comments on raw BE32 words.

| Named API | Exact native chain |
| --- | --- |
| `hero_set_num_objects` | `0x2B88F8 → 0x288A98 → 0x2509B8 → 0x23D970` |
| `hero_get_num_objects` | `0x2B8A70 → 0x288B80 → 0x24FC88 → 0x23D8E0` |
| `hero_add_object` | `0x2B8BE8 → 0x288C58 → 0x252F78 → 0x23D870` |
| `hero_has_object` | `0x2B8D60 → 0x288D40 → 0x24F7B8 → 0x23D940` |

Native methods access hero member `+0x1A68`, whose pointer linkage to serialized `0x101EFB20` is guarded at `0x23E73C/0x23E744` and TOC slot `0x897B38`. Current getter loads `+0x304+4*i` and sign-extends; high-water getter `0x23D900` loads `+0x360+4*i`. Set/add methods compare high-water as unsigned (`cmplw`), not signed, and add updates `+0x3BC+4*i` only when the signed delta is positive. The presence predicate compares current against zero, not against a positive threshold. Native arithmetic wraps 32 bits; no repaired or clamped data is implied.

Full catalog, actual USA observations, reproduction commands and limitations are in the [save-format notes](../../SaveFormat.md#confirmed-object-counters-and-equipment). Timer units, arena-count usage, reset points and each item's runtime dependencies still require further tracing or controlled captures. Positive additions are not asserted to be unique pickups or lifetime acquisition totals.

## Active and completed mission lists

The `mission_lists` section is independently reproduced by [Inspect-TodMissions.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodMissions.py). Native active address getter `0x2D0D60` resolves `save+0x10148+0x7C*level`; completed getter `0x2D0DF0` resolves `save+0x10AF8+0x7C*level`. Each list has ten12-byte entries and count at member78. Original count values are retained; analysis only bounds reads to the physical capacity. Added types `TOD_SaveMissionEntry_verified` and `TOD_SaveMissionList_verified` refine the old counter-only type without overwriting it.

| Named native chain | Evidence |
| --- | --- |
| `get_num_missions`: `0x311C0 → 0x25EC8` | Sum active count (`0x137C0 → 0x2D0DC8`) and completed count (`0x12470 → 0x2D0EF0`) |
| `is_mission_complete`: `0x31098 → 0x25E80` | Entry flags bit1 |
| `is_mission_optional`: `0x30F70 → 0x25E38` | Entry flags bit0 |
| `is_mission_available`: `0x30E48 → 0x25DF0` | Inverse of bit1, not another saved flag |
| `get_mission_name`: `0x30D20 → 0x27CA8` | Entry word0 passed into native text lookup |
| `get_mission_desc`: `0x30BF8 → 0x27B40` | Entry word4 passed into native text lookup |
| `add_mission`: `0x2A7680 → 0x2776D8 → 0x2D1168` | Duplicate title-ID check, active capacity10, append with low8 flag bits |
| `complete_mission`: `0x2A7568 → 0x2776B0 → 0x2D0F78` | Moves title/description, ORs completion bit, updates both counts and compacts active entries |

All getter paths use `0x11D30 → 0x2D0E18`: one-based script indices become zero-based, active entries precede completed entries. The native getter is not an independently safe bounds checker; inspection never invokes it. Unknown flag bits and malformed counts remain visible. The transaction code does not prove a safe edit sequence, valid arbitrary title IDs, or console acceptance. The supplied save has no occupied mission entries, so controlled gameplay captures are still needed to observe a nonempty example and its reset behavior.

### Blueprints and bonus/cheat states

The named APIs independently establish the next serialized fields. [Inspect-TodBonuses.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodBonuses.py) reproduces the bundled `bonuses` section with 231 byte guards, full original ELF hash verification and bounded plaintext inspection. It reports to stdout only. [TestTodBonuses.py](../../../../../Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodBonuses.py) tests unknown bits, unusual states, malformed inputs, exact catalog reproduction and original-input preservation; generated fixtures are not in-game captures.

| Save offset | Code-backed meaning | Evidence |
| --- | --- | --- |
| `0x86F4`, BE32 | Blueprint ownership mask, integer bit = native ID | Named `has_blueprint`: `2F330 → 27370`; hero predicate `2BA520 → 27A5D8`; menu predicate `38140 → 37580` |
| `0x86F8–0x8705`, 14 bytes | Physical native bonus/cheat selected states | Named `get_cheat_state`: `2D378 → 27098`; named setters `2D260 → 27008` and `2BBB78 → 27A648` |
| `0x8706–0x8707` | Still opaque | Zero in supplied USA save; no semantic claim |
| `0x8708`, BE32 | Shared weighted skill-point score used by bonus availability | `is_cheat_unlocked`: `2D858 → 27108`; `set_cheat_points`: `2BBAB8 → 27A638` |

`hero_give_blueprint` (`2BA3F8 → 27AF90`) ORs one shifted bit into the mask. `hero_give_all_blueprints` (`2BA318 → 27AFB0`) ORs `0x0007DEE4`, preserving every other bit. Its thirteen IDs are **2, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 17, 18**. Their physical locations and correspondence to planet IDs are not established by these functions, so the inspector labels them by blueprint ID, not planet. Native `slw` behavior is not bounds validation: the low six shift bits are used; 32–63 yield zero, 64 aliases zero. Inspection never invokes the game setters.

Both named blueprint count APIs lead to `35D450`: menu `2F408 → 273A0 → 12D50 → 35D450`, hero `2BA668 → 27A608 → 35D450`. Their object pointer is `0x101F5048`; member `0x31CC` is absolute `0x101F8214`, which is serialized base `0x101EFB20 + 0x86F4`. The helper popcounts **all 32 bits**, including bits outside the native all-grant mask. The supplied plaintext contains `0x0007DEE4`, so count 13 and no outside bits; this is a save observation, not proof of obtaining the blueprints normally.

Fourteen `CHEAT_*` identifiers are exported with exact IDs in both registration modules. The native definition table is `0x10026384`, fourteen records of `0x30` bytes. Named value/count/title/description/state-name getters establish words `+0` title lookup ID, `+4` description lookup ID, `+8` unsigned score requirement, `+C` state-name count, and eight physical state-name lookup words at `+10`. Localized names are runtime lookups, not recovered text.

| Physical ID | Native identifier | Shipped score | State-name count |
| --- | --- | --- | --- |
| 0 | E3TRAILER | 25 | 1 |
| 1 | HERO_BIGHEAD | 50 | 4 |
| 2 | CONCEPT_CHAR | 75 | 1 |
| 3 | ENEMY_BIGHEAD | 100 | 3 |
| 4 | TRAILER01 | 150 | 1 |
| 5 | DEV_COMMENTS | 200 | 2 |
| 6 | CONCEPT_ENV | 250 | 1 |
| 7 | WRENCH_REPLACE | 300 | 5 |
| 8 | HOW_TO_DRAW | 350 | 1 |
| 9 | JAMES_ZURKON | 400 | 2 |
| 10 | CONCEPT_WEAP | 450 | 1 |
| 11 | MIRROR_LEVEL | 500 | 2 |
| 12 | SCRIPTSCREEN | 600 | 1 |
| 13 | CONCEPT_PAINT | 750 | 1 |

These are **physical native slots**, not unconditional menu indices. When runtime getter `5BFE08() != 1`, menu count is 13 instead of 14 and IDs greater than 4 are incremented before storage/definition lookup. Availability has additional threshold-index adjustments for resulting IDs 7, 11 and 14. The runtime getter reads a word through a TOC pointer to `0x100D6478`; its gameplay meaning is unresolved and is not taken from this save. No current menu availability is inferred in the inspector. Availability compares the saved score unsigned to the adjusted threshold; it does **not** test the saved state byte.

Menu setter `27008` first takes the low eight state bits, then accepts 1–8 or stores zero; raw setter `27A648` also accepts 1–8 or zero without an observed explicit ID bounds check. This global setter range is not each bonus's valid state-name range. Neither routine supplies safe editing permissions. All fourteen state bytes are zero in the supplied save despite score 750; zero alone does not mean locked, and nonzero is not enough to assert an active/on label.

Named `enable_all_cheats` (`2BBC90 → 27A678 → 35D480`) writes **840** to score `0x8708`, changes only zero state bytes to one, and preserves nonzero states. It does not update earned skill bits `0x8710`; therefore it must not be represented as “award all skill points.” New verified types `TOD_BonusDefinition_verified` and `TOD_SaveBonusState_verified` capture only these proven layouts, retaining opaque padding. Simple read-only Blueprints and Bonuses & cheats inspector views retain all raw evidence under Technical/details; unexpected set blueprint bits remain visible.

### Saved equipment history and compressed state blocks

[Inspect-TodStateStorage.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodStateStorage.py) reproduces the shared `state_storage` section with 50 byte guards, full ELF hash verification, three historical equipment words and a bounded native-format RLE decoder. [TestTodStateStorage.py](../../../../../Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodStateStorage.py) tests token truncation, native output boundaries, run clipping, malicious lengths, map reproduction and unchanged actual inputs. No decoded payload or game binary is embedded in the application; it computes only live read-only summaries from the session snapshot.

#### Equipment history, not dual-wield slots

Native callback `0x1F5570` reads inventory member `+0x188`, then hero member `+0x1A68` to reach serialized state. Initializer `0x1F5DB8` stores the hero argument at inventory `+0x188`; the already mapped hero initializer links `+0x1A68` to `0x101EFB20`. The callback's descriptor `0x8666D8` is referenced at table slot `0x84A4E0` for indirect dispatch; exact callback timing remains unverified.

The callback performs these operations, in order:

1. Copy old saved `0x430` to `0x434`.
2. Copy old saved `0x42C` to `0x430`.
3. Call `0x11810 → 0x466EC0`, the same native equipped-item getter reached by named `hero_get_equipped`, and store its result at `0x42C`.

Therefore these are **last recorded, previously recorded and older recorded equipped item IDs**, not primary/secondary weapon slots. The native getter returns config ID or `-1` when no runtime equipment object exists; initializer `35DC80` stores `FFFFFFFF` in all three words. Restore `1E33C8` consumes `42C/430` with fallback logic. Menu consumer `26CE30` consults all three history words and also applies fallback logic. Duplicate history values, callback frequency, reset rules, currently active runtime equipment and safe edits cannot be inferred from one snapshot.

The supplied USA save contains IDs **15, 25, 0**, corresponding to the independently mapped native item names **Ryno, SwingShot, Wrench**. These labels now appear in the read-only player summary; unknown IDs and `-1` remain visible without repair. `TOD_SaveEquipmentHistory_verified` describes the three raw signed-ID words.

#### Native RLE storage

Initializer `35E110` creates **21 physical blocks** starting at save `0x114D8`, stride `0x60DC`, ending at `0x906E4`. These slots are not a one-block-per-planet catalog; their native map-label associations are documented below. The following block members are proven by encoder `35C5B8`, decoder `35C460` and initializer `35E070`:

| Block member | Meaning |
| --- | --- |
| `+0x00–0xC7` | Copied runtime volume definition; partially refined below, not padding |
| `+0xC8`, BE32 | Native encoder accumulator; formula below, not checksum/completion |
| `+0xCC`, byte | Encoder writes 1; initializer clears it; readiness, not visit/completion |
| `+0xCD–0x60CF` | Physical RLE storage, `0x6003` bytes; writer asserts encoded length no greater than `0x5FFF` |
| `+0x60D0`, BE32 | Declared encoded byte count |
| `+0x60D4–0x60DA` | Seven saved volume-group flags, detailed below; initializer clears them |
| `+0x60DB` | Final byte remains unknown |

RLE grammar is a literal byte when it differs from the next byte, or a four-byte token **value, value, BE16 extra-repeat count** when two bytes match. A run contains `extra + 2` copies. Native restore caps output at **`0x40000` / 262,144 bytes** and stops pair recognition after output offset `0x3FFFB`. Its final run may exceed this output cap and is clipped. The safe Python and C# research decoders additionally refuse truncated tokens and oversized declared input; they do not emulate native out-of-range reads or normalize malformed streams. Empty/not-ready slots are not interpreted as zero-filled logical state.

Encoder accumulator `+C8` adds one for each zero literal or the **extra-repeat count** for each zero run; the first two bytes of each repeated run are excluded. Consequently it is not the exact number of zero bytes, a checksum or a completion count. The native writer's terminal runs may incorporate bytes beyond the intended logical input boundary; the research decoder reports clipping and never rewrites those original tokens.

The supplied USA save has **19 ready blocks**, with slots **3 and 4 not marked ready**. Every ready block consumes exactly its declared encoded size, restores exactly 262,144 bytes, clips four bytes from its final run and reproduces its saved encoder accumulator. Byte values are usually 0/1; slot 11 also contains **297 bytes with value 2**, so they must not be coerced to booleans. Individual logical indices and values remain unnamed.

Independent Python and C# decoders agree on the actual output hashes, including slot 0 `2CE4BB0E543C205E2524A6AA309B008F6824695EEAC68040847393F598EF9CD8` and slot 11 `9CD7A4BF562AB098D75C0FF51BDFD7625D9F68DADECA96BB9CC6A5D85795004E`. Their agreement and accumulator checks confirm encoding/storage interpretation, not gameplay meanings.

The native **pre-snapshot synchronization chain** is `35E710 → 250758 → 24EAC8 → 24DAB8 → 12670 → 35C5B8`. `24DAB8` only invokes encoding when runtime member `+20` is nonnull; it passes runtime `+24` as source and loaded-object member `+10` as block slot. This identifies a synchronization step before the bulk save copy, not every synchronization dependency. `TOD_SaveRleBlock_verified` retains the earlier physical layout; the separate verified header/group types below refine it without replacing existing analysis types. The read-only Stored state blocks view retains unknown bytes, raw readiness, sizes, hashes, value histograms and clipping details. No new editing controls are introduced.

### Persistent grid volume headers, map labels and group flags

[Inspect-TodPersistentGrid.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodPersistentGrid.py) independently derives the bundled `persistent_grid` section from the fingerprinted USA v02.00 ELF. Its **86 byte guards** include complete native consumers, the relative switch table and case blocks, level-name table/strings, TOC identities, copy thunk and label/camera call chains. Seven tests cover map/type reproduction, all21 labels, unsigned pointer/index bits, nonboolean flags, last-group/tail bounds, malformed lengths and unchanged actual inputs.

#### Copied200-byte volume definition

Selector `24DEA8` iterates enabled definitions (`+C` nonzero), requires class `+4 == 0x535` and tests hero containment. Definition `+18` selects an optional runtime volume (`FFFFFFFF` means use direct geometry). Definition `+10` selects the saved physical block. On switching volumes it encodes the previous grid; ready slots restore via `10660 → 35C460`, while unready slots initialize a baked layer then copy exactly `0xC8` bytes at `24E09C → 12BB0 → 81A9A8` into that block's prefix. This is a copied runtime definition, not a freshly constructed pointer-free save header.

| Prefix member | Confirmed interpretation |
| --- | --- |
| `+00`, BE32 | Runtime geometry pointer bits; never follow from the save, not a portable pointer/stable UID |
| `+04`, BE32 | Volume class; selector requires `0x535` |
| `+08`, BE32 | Unnamed common-object word |
| `+0C`, byte | Definition enabled when nonzero; `+0D..0F` unresolved |
| `+10`, BE32 | Physical saved block slot |
| `+14`, BE32 | Baked resource layer index |
| `+18`, BE32 | Optional runtime volume reference; preserve `FFFFFFFF` sentinel bits |
| `+1C`, byte | Coordinate-sign control: zero gives−1, nonzero+1; world-axis naming unverified |
| `+1D..1F` | Unresolved bytes |
| `+20..C7` | Seven24-byte groups |

Each group has reference index `+00`, map rectangle origin words `+04/+08`, extent words `+0C/+10`, and image/resource index `+14`. The formerly named activation word is **first rectangle extent**, whose nonzero value also gates containment/image visibility. `TOD_SaveGridRectangleGroup_verified` refines the original raw `TOD_SaveGridGroup_verified` without replacing existing database types. No save pointer is dereferenced and no unknown field is normalized. Display-consumer evidence is detailed below.

#### Seven containment flags and image visibility

`24E8A0` iterates exactly seven groups. A nonzero saved byte at block `+60D4+group` skips further checks. Otherwise it follows the group's runtime volume-list reference (skipping `FFFFFFFF`), checks hero containment, and writes1 when first extent `+0C` is nonzero. `25AE08` uses those saved bytes and nonzero first extent to display image index `+14+25`. A nonzero independently named `OBJ_TREASURE_MAPPER` count at save `31C` bypasses the saved-flag visibility requirement, not the nonzero-extent requirement. These are qualified containment/visibility flags, **not a mission completion checklist**. Eighth tail byte `+60DB` remains unknown.

#### Native512×512 grid

`24DCA0` reads baked resource `250D0`, selecting layer from definition `+14`. Two512-iteration loops consume eight high-to-low nibbles per BE32 and write persistent state bytes at runtime manager `+24`, separate image bytes through pointer `+40028`. Index is `first_coordinate*512 + second_coordinate`; the persistent grid is exactly `0x40000` bytes.

Conversion `24D6E8` yields image0/state0 for input0. Otherwise image is `min((input & 15)*17,254)` and state is `min(ceil(image/127),2)`, with native constants127 and1 guarded independently. Thus baked nibbles1..7 initialize state1 and8..15 initialize state2. `24D570` projects world coordinates using runtime geometry and the sign byte; `24D788` checks coordinates below512 and clears qualifying cells in a bounded neighboring region to0. State2 is not another spelling of boolean true. Projection formula and brush are now refined below; world-axis naming, runtime geometry, pixel-specific terrain meaning, palette and edited-save acceptance remain unverified. This does not authorize a fog-map editor.

#### All21 physical slot-to-level label associations

`24E6E8` bounds slot0..20 and returns the level literal from relative jump table `24E70C` (TOC slot `897F00`). Unresolved-switch decompilation omits case blocks, so the inspector decodes and guards them directly. Caller `25D1D0` uses thunk `251428` at `25D33C`, then passes that result into native title/description lookups `2D0988` / `2D0C18` at `25D3CC` / `25D3E0`. The independent19-name table at `10062F7C` supplies internal labels.

| Physical slot(s) | Native level ID | Internal map-label level |
| --- | --- | --- |
| 0, 1 | 14 | kerchucity |
| 2, 3, 4 | 10 | sargasso |
| 5, 6 | 6 | apogeespacestation |
| 7 | 1 | cobalia |
| 8 | 16 | cragmitiruins |
| 9 | 3 | fastoon |
| 10 | 18 | fastoon_return |
| 11 | 5 | imperialfightfest |
| 12, 13 | 11 | iris |
| 14 | 17 | meridiancity |
| 15 | 0 | metropolis |
| 16 | 7 | piratebase |
| 17 | 9 | rykanv |
| 18 | 15 | slags_fleet |
| 19 | 2 | stratuscity |
| 20 | 12 | zordoomprison |

This proves a **map-label relationship**, not current planet or the identity of every gameplay subsystem. Multiple slots share a level; physical slot number is not level ID. Other neighboring switches implement browse order and image selection, not interchangeable level catalogs.

All19 ready blocks in the supplied USA plaintext have class535 and stored slot matching physical slot. Slots3/4 are not ready and have zero headers; they are left uninterpreted. All ready streams still decode to512×512, with297 state2 bytes in slot11. The UI adds these map labels to the simple Stored state blocks view; Technical/details retain all21 slots, header bits, seven raw flags, unnamed words and the final unknown byte. Neither grid data nor flags are editable.

#### Settings follow-up without a guessed option name

The `114C0` consumer `20F3F0` sets independently cataloged global bit6 `HERO_FIRST_PERSON` (`ld5528`, `ori40`, `std5528`). Camera getter `10420 → 639400` and priority-qualified request `13D50 → 639548` establish runtime modes0F/10 used by this path and `2108D8`. This supports first-person camera context, **not** a localized menu label or toggle/hold polarity. Runtime camera members do not become new save offsets; `114C0`, `114D6/114D7` and `906E4` retain unknown semantic labels.

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodPersistentGrid.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin"
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodPersistentGrid.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin" -v
```

### Map-menu routing and native accumulator predicate

[Inspect-TodGridRouting.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGridRouting.py) independently reproduces `grid_routing` with **102 native byte guards**. Three unsigned-input switches establish separate namespaces:

| Function | Input → output | Out-of-range result |
| --- | --- | --- |
| `24E398` | Physical saved grid slot → browse ordinal0..20 | 21 |
| `24E4C0` | Browse ordinal → physical saved grid slot | `FFFFFFFF` |
| `24E5E8` | Physical saved grid slot → shared resource image index21..36 | 21 |

The first two are inverse permutations, not native level catalogs. Full browse order by **physical slot** is `[15,7,19,9,11,5,6,16,17,2,3,4,12,13,20,0,1,18,8,14,10]`. Shared image indices by slot are `[32,32,29,29,29,26,26,22,34,24,36,25,30,30,35,21,27,28,33,23,31]`; duplicate image IDs do not merge separately saved grids.

Consumer `25D1D0` calls TOC thunks `2520C8 → 24E398` and `2512B8 → 24E4C0`, wraps directional searches across21 ordinals, and skips blocks with ready byte`+CC==0`. Both paths address save `114D8+slot*60DC`; tests at `25D4CC`/`25D5AC` reach exactly`+CC`. Nonzero readiness is accepted, not normalized. Runtime selection `+AD0` and selected block pointer `+B08` are not additional save fields. `25BBF0` and `25D1D0` call image thunk `2500D8 → 24E5E8`, then resource helper `251898` with extent512 and flag`20000`; a separate physical-slot lookup uses flag`80000`. Image names/palette remain unassigned.

Unreferenced predicate `24E7E8` reads **all21 saved BE32 encoder accumulators** at `115A0+slot*60DC`, counts unsigned words **greater than or equal to`0x36666` /222822**, and returns1 only when count **exceeds15**. It does not check readiness or decode cells. TOC slots `897F04`/`897F08` point to `102010C0` / `102802CC`; the second is a stride sentinel beyond serialized state, **never dereferenced**. The last actual read remains inside the save. The sign-bit arithmetic uses zero-extended loaded words, so values`80000000`/`FFFFFFFF` qualify, not negative counts.

Only descriptor `869388` references predicate code in the native pointer scan; no direct caller or descriptor-pointer reference was found. **No trophy, mission or completion meaning is established.** The accumulator already excludes the first two zero bytes of every repeated run, so this is not an exact cleared-cell count or percentage. The actual USA snapshot qualifies19 words; slots3/4 have0. Its ready menu order is the permutation above with3/4 omitted. Both are snapshot/static-code observations, not runtime acceptance tests.

Seven routing checks cover inverse mappings, namespace/default differences, shared image IDs, threshold equality, strict15/16 count boundary, unsigned extremes, readiness independence, sentinel bounds and unchanged actual inputs. Inspector details show menu position/image ID and explicitly qualified predicate evaluation; the simple four-column grid view stays unchanged.

### Copied map rectangles, world projection and clearing brush

[Inspect-TodGridGeometry.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGridGeometry.py) reproduces `grid_geometry` with **28 native byte guards**, including six complete functions, TOC constants and the196-byte brush. `25BF68` addresses copied group`20+group*18`, converts unsigned BE32 words into display geometry and clips endpoints/adjusts UVs:

| Group member | Confirmed role |
| --- | --- |
| `+00` | Runtime volume-list reference, already verified |
| `+04 / +08` | First/second map rectangle origins |
| `+0C / +10` | First/second map rectangle extents |
| `+14` | Image resource index, already verified |

Loads at `25C0BC/C0/C4` establish first extent and two origins; indexed load `25C16C` from header`30+group*18` establishes second extent. Display constants include400/512 and200/512, clipping axes800/400. These are **map-display coordinates, not raw world coordinates**. In the actual save33 ready groups have nonzero first extent; all33 origin-plus-extent rectangles fit512×512,28have nonzero saved flags and5have0. First origins span4..454; second27..439. These observed bounds are not universal edit limits or a validator for arbitrary resources.

`24D570` projects using copied runtime geometry pointer`+00` and sign byte`+1C`: zero means−1, any nonzero+1. Let `n=sqrt(g[0]^2+g[1]^2+g[2]^2)` and `c` be geometry translation`+30` or`+38`. For corresponding input component`p`, simplified finite arithmetic is:

```text
t = 512 + sign*(p-c)*512/n
coordinate = truncate_toward_zero((t >= 0 ? 1024-t : 1111)*0.5)
```

The translation center gives256; negative`t` gives555, an out-of-grid result, **not an edge clamp**. `24D9C0` sends the hero-transform`+38`-derived coordinate first and`+30`-derived coordinate second to `24D788`, whose index is first*512+second. Guarded constants are1/1024,512,1111,1024,0.5 and0. The formula follows native single-precision/FMA/conversion operations; simplified algebra is not a bit-exact float emulator. Geometry is unavailable from saved pointer bits, so actual-save world-coordinate projection and pathological NaN/zero-normalizer behavior are not validated.

`24D788` uses the **14×14 mask at`10060DE8`**, via TOC`897EC8`:129bytes`FF`,67bytes0. Nominal ranges are `[center-7,center+7)` on both coordinates. Mask index is first-loop index+14*second-loop index. Original assembly preserves converted **center class in r24** (`24D8D0`) and loads candidate class in r7 (`24D958`); clearing condition at`24D978/97C` is **`(center_class & brush_byte)==candidate_class`**, then writes0 at`24D9B4`. It is not a candidate-only mask test. Zero mask bytes can still match class0; they are not unconditional skips. Minimum-edge negative starting coordinates fail unsigned bounds/loop comparisons and skip the loop; maximum-edge loops stop at512. Do not replace this behavior with a symmetric clamped brush.

Seven geometry checks cover unsigned rectangle extremes/last-group boundaries, nonboolean flags, retained unready fields, mask shape, exact class-source distinction, qualified projection/order and unchanged actual input. Original types remain intact; `TOD_SaveGridRectangleGroup_verified` supplies the refined field names. Header`+08`, `+0D..0F`, `+1D..1F` and final tail`+60DB` remain unnamed.

### Shipped pause-menu settings dispatch

[Inspect-TodSettingsMenu.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSettingsMenu.py) independently reproduces `settings_menu` from **shipped asset evidence, not ELF addresses**. Exact `global_cached.psarc` entry `/built/anark/pause/built.dat` is1152780bytes, SHA-256`26FC24DD3564FDF94F0F6278FC0F0BC5578FE73C6813D3F39CD113FD22CF761B`. Embedded Lua5.0 `controlHandler` occupies asset offsets`F38FC..F715E`. Four function-code digests and17raw asset-byte guards check initialization/activation/display/adjustment. Literal table folding allows only construction instructions, never calls or executes Lua. Asset offsets must not be treated as ELF VAs/save offsets.

The12 literal descriptors produce enabled indices`[1,4,7,10,11,12]`. Separate first-person inversion descriptors exist but are disabled; `onActivate` filters disabled descriptors, so a literal row is not proof of runtime visibility. Axis descriptors10/11 have native API tables: **scheme0 → `is_x/y_inverted` / `set_x/y_inverted`**, **scheme1 → `is_look_x/y_inverted` / `set_look_x/y_inverted`**. Both display and adjustment index by `get_cur_control_scheme`; this selects the saved field/API, **not reversal of flag polarity**. An initializer's space-combat display of scheme2 does not prove a scheme2 entry in those0/1 tables.

Boolean/axis adjustment passes the logical opposite of the selected getter result. Percentage adjustment divides input delta by10 before adding to getter value; ±1 requests±0.1, then native setters clamp ordinary finite values0..1. Activation checks/sets independently named `HERO_SAW_CONTROL_MENU`. Display tags93/94 for boolean true/false and95/96 for axis true/false are **local text-tag IDs**, not native enum IDs or proven English NORMAL/INVERTED strings. Six asset tests cover exact hash/guards, descriptor filtering, API dispatch, action math/tag separation, mutation rejection and bundled-report reproduction.

The actual save's control scheme is0, making the scheme0 dispatch applicable to these saved bits as a **static interpretation**, not a claim about current runtime menus. `114C0`, `114D6/114D7` and`906E4` remain semantically unnamed. Read-only settings details explain the dispatch/steps while preserving all native fields, raw flags and unknown bytes; no setters or Lua scripts are run.

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGridRouting.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin"
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGridGeometry.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin"
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSettingsMenu.py "path/to/global_cached.psarc"
```

### Saved settings and load destinations

[Inspect-TodSettings.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSettings.py) independently reproduces the `settings` section from named Lua registrations, guarded native getters/setters and the settings initializer. It checks the full ELF hash first, resolves TOC pointers and derives save offsets from the actual load instructions. The section adds 270 byte guards and the portable `TOD_SaveSettings_verified` structure; [TestTodSettings.py](../../../../../Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodSettings.py) covers map reproduction, initializer defaults, actual save observations, unusual flags, nonfinite floats, unknown IDs/bytes and unchanged inputs.

The options block is **`0x114A8–0x114D8`, size `0x30`**: immediately after the twenty completed mission lists and immediately before the 21 RLE blocks. Fifteen fields are named by native APIs, not inferred from neighboring values:

| Save offset | Storage | Meaning | Getter / setter VA |
| --- | --- | --- | --- |
| `114A8` | BE32, nonzero | Camera X inverted | `26CA8 / 26C98` |
| `114AC` | BE32, nonzero | Camera Y inverted | `26C70 / 26C60` |
| `114B0` | BE float32 | Camera speed, units not asserted | `26C50 / 276A8` |
| `114B4` | BE32, nonzero | Look X inverted | `26C28 / 26C18` |
| `114B8` | BE32, nonzero | Look Y inverted | `26BF0 / 26BE0` |
| `114BC` | BE32 | Current control-scheme index | `27220 / 271B0` |
| `114C0` | BE32 | **Unknown**, initializer writes 1 | No named semantic link |
| `114C4` | BE float32 | Voice volume | `26E00 / 276D0` |
| `114C8` | BE float32 | Sound-effects volume | `26BB0 / 24E90` |
| `114CC` | BE float32 | Music volume | `26E10 / 27718` |
| `114D0` | Byte | Help text enabled | `26DF0 / 26DB8` |
| `114D1` | Byte | Subtitles enabled | `26DA8 / 26D98` |
| `114D2` | Byte | Quick select pauses | `26D88 / 26D78` |
| `114D3` | Byte | Sixaxis controls enabled | `26BC0 / 26BD0` |
| `114D4` | Byte | Rumble enabled | `26D68 / 26D18` |
| `114D5` | Byte | Surround enabled | `26D08 / 26CD0` |
| `114D6–114D7` | Two bytes | **Unknown**, not proven padding | Preserve |

Word-boolean getters explicitly compare with zero. Byte getters return the raw byte and their named Lua wrappers expose a boolean result. Inspector display uses nonzero but preserves atypical raw bytes/words. Float setters use `fsel` against TOC constants `0.0f` and `1.0f`; these bounds describe ordinary finite setter inputs, not a demonstrated safe edit range or NaN normalization rule. The inspector retains all raw float bits.

Initializer `35EE40`, called on the settings subobject by `35D9A0`, writes inversions and scheme index 0, camera speed 1.0, all audio volumes `3F666666` (float32 approximately 0.9), help/pause/sixaxis/rumble/surround 1, subtitles 0, and unnamed word `114C0` = 1. It does not explicitly initialize `114D6/114D7`. **Actual USA save differs:** help text is 0 and subtitles 1; volumes remain `3F666666`. These are observations, not inferred defaults. The app converts volume fractions to percentages for readability without changing bytes or asserting measured loudness.

Two additional assembly-backed consumers show unnamed word `114C0` is used: `20F3F0` resolves state through slot `89679C`, sets runtime flag `+24` when the word is zero, and selects modes `0F/10`; `2108D8` does the same through slot `896858` and runtime flag `+3F`. The option and mode names remain unresolved. This is a confirmed use relationship, not grounds to rename the word. Byte getter wrappers normalize nonzero to a Lua boolean through `106A0 -> 6A8EE0 -> 668770`; inspection preserves the original saved bytes.

Audio apply `7FC98` sends saved effects/voice/music values to buses **1/6/12**. Restore `35E508 → 251CC8 → 5ADEF0` applies the same saved values. This establishes audio settings rather than a health/ammo interpretation. Do not invent extra option fields: `is_rumble_connected → 24C90` returns constant 1; `get_button_layout → 24C98` returns constant 0; `set_button_layout → 24CA0` is a no-op. In particular, these APIs do not identify unnamed word `114C0` as button layout. `get_num_control_schemes → 24C48` returns 2, but the setter also distinguishes index 2; this is not sufficient to assign names or an accepted saved-value range.

Two independent level-selection words are now confirmed:

- **`0x906E8`, saved load destination:** named `set_save_level` wrapper `2C8D38` calls `27BAD0`, which stores at saved-state base + `90000 + 6E8`. Getter `2D1490` reads the same word. Restore `35E508` passes it to level-change routine `2D16A0`; that routine also updates it during transitions. This is not necessarily the current runtime planet or the SFO subtitle.
- **`0x8740`, next-level selection:** named `set_next_level` wrapper `2C8C80` calls `27A818`, which stores at saved-state base + `10000 - 78C0`. Named `get_next_level` wrapper `39938` calls getter `36AF0`. It is **not** the tail word `906E4`.

Table `10062F7C` contains nineteen native level-name pointers; `2D0880` indexes it and inverse lookup `2D08D8` compares nineteen entries. The decoded catalog preserves internal names, not guessed localized planet titles. Actual USA saved load ID is **0 (`metropolis`)**; next-level raw ID is **`FFFFFFFF`**, retained as unmapped rather than assigning an unproved sentinel meaning. A current-level script API instead resolves a separate runtime string. The read-only Player summary displays the two saved words with these limitations.

### Runtime checkpoints and health: no saved offsets inferred

Named checkpoint bindings lead to a separate runtime object at **`0x10330610`**, through TOC pointer slots `898FB0 / 8A1928`. Relative to saved-state base `101EFB20` this is `140AF0`, outside the serialized interval `[101EFB20, 10280210)`. It cannot be assigned a save offset by subtracting the state base.

`checkpoint → 27B258` and `checkpoint_volume → 27B128` reach capture routine `35CF40`. It copies/normalizes three orientation rows at runtime `+00/+10/+20`, copies sixteen position bytes to `+30`, stores saved-load getter `2D1490` at `+40`, and marks byte `+EF` valid. `has_valid_checkpoint → 27B108` tests `+EF`; predicate `27B218` also compares flag byte `+ED`. `is_current_checkpoint → 2788E8` compares positions against a resolved runtime volume. Other members and validity/reset behavior are not fully mapped. These findings belong in the runtime research, **not** as editable saved position fields.

Named `hero_get_health` wrapper `2B93F0` calls `289358`, resolves an object via `276D48`, validates class `B9` via `24F208`, then requests **float attribute ID `6C`** through `251F98` and reads the returned attribute's `+4` float. This confirms a runtime health accessor; no link to a dedicated serialized health word has been proven. Saved hero XP `418` is independently mapped and is not relabeled as health.

### Arena challenges: direct IDs, saved wins and shipped definitions

[Inspect-TodArenaChallenges.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodArenaChallenges.py) independently reproduces `arena_challenges` from the exact ELF and fingerprinted `arena.csv`, `arena.lua`, `arena.lc` extracted from `packed/game/global_cached.psarc`. It parses CSV literals only, never executes scripts, and carries **259 byte guards**. [TestTodArenaChallenges.py](../../../../../Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodArenaChallenges.py) checks catalog reproduction, bounds, signed/raw values, asset identity, invalid inputs and unchanged sources. Both portable structures are available to IDA/Ghidra; neither is automatically applied.

Named slot `89D8F4` (`get_challenge_successes`) reaches wrapper `2C9AE0 → 27A958`. The native getter checks unsigned ID against22, loads state through TOC slot `898F50 → 101EFB20`, indexes `56D0+4*id`, then loads member+8 and sign-extends. This establishes **BE32 at `56D8+4*id`**, independently of the runtime menu resolver. Initializer `35D9A0` clears23 words at subobject `5528+1B0 = 56D8`, ending exclusively at **5734**. A subsequent loop clears **eight separate words at `5528+20C = 5734`**, ending at5754 before weapon unlock bytes. Their meaning is unknown; they are not proven failure counters. Invalid-ID error paths are not a separately proven safe range guard.

Enum exports from `294E90 → 252EB8` establish INVALID0, the22 `IFF_` IDs below, and COUNT23. CSV rows have a different order and are joined by native enum name, not line number. **Descriptions are the CSV Comment column, explicitly not parsed by arena.lua; localized challenge titles have not been recovered.** Blank fields remain unspecified rather than guessed native defaults.

| Native ID / enum | Save offset | Shipped config description | Base bolts |
| --- | --- | --- | --- |
| 1 / IFF_A_1 | 56DC | Rookie Korner | 3000 |
| 2 / IFF_A_2 | 56E0 | Time Is Not On Your Side | 4000 |
| 3 / IFF_A_3 | 56E4 | Breath of Death | 6000 |
| 4 / IFF_A_4 | 56E8 | Introducing Crushto | 5000 |
| 5 / IFF_A_5 | 56EC | Crash The Party | 5000 |
| 6 / IFF_A_6 | 56F0 | Well Done Mustacio | 5000 |
| 7 / IFF_A_7 | 56F4 | Whip It Good | 8000 |
| 8 / IFF_A_8 | 56F8 | Return of Crushto | 10000 |
| 9 / IFF_A_ALT1 | 56FC | Noxious Another Arena Challenge | 12000 |
| 10 / IFF_A_ALT2 | 5700 | Get Your Dang Hands Off | 9000 |
| 11 / IFF_B_9 | 5704 | Heavy Weapons | 5000 |
| 12 / IFF_B_10 | 5708 | Zaptor In Da House | 6000 |
| 13 / IFF_B_11 | 570C | Slaying the Slots | 6000 |
| 14 / IFF_B_12 | 5710 | And The Bots Keep on Coming | 7000 |
| 15 / IFF_B_13 | 5714 | Challenge 13 | 7000 |
| 16 / IFF_B_14 | 5718 | Take To The Skies | 9000 |
| 17 / IFF_B_15 | 571C | Untouchable | 10000 |
| 18 / IFF_B_16 | 5720 | It Takes Two | 11000 |
| 19 / IFF_B_17 | 5724 | Smashing Good Time | 8000 |
| 20 / IFF_B_18 | 5728 | Zaptors Revenge | 13000 |
| 21 / IFF_B_19 | 572C | Bombbot-ocalypse | 14000 |
| 22 / IFF_B_20 | 5730 | The Ultimate Showdown | 15000 |

The USA snapshot has **all23 counter words zero**, including INVALID0 at56D8; the separate eight words are also zero. This is an observation, not evidence that all challenges are available or a calculated completion percentage. The read-only app **Arena challenges** view shows22 descriptions, recorded wins and shipped base bolts; Technical includes the reserved slot, offsets and raw bits. Unexpected negative values are retained, not converted into zero wins.

Native `ArenaConfig` indexer `B6FA8` checks ID0..22 and returns parent+`1177C+34*id`. Six named property triplets at `88FA5C` establish the entire52-byte record layout below (opaque bytes remain unnamed). These records are **runtime configuration, not fields in GAME.SAV**.

| Offset / type | Native property | Getter / setter |
| --- | --- | --- |
| +00 / byte | IsBoss | B6AE0 / B6A00 |
| +01..03 / opaque | Unknown, not asserted padding | — |
| +04 / float32 | Time | A8BA0 / 9A148 |
| +08 / signed32 | Weapon | A8AE8 / 9A078 |
| +0C / unsigned32 | BoltReward | A8A18 / 99FA0 |
| +10 / signed32 | WpnReward | A8960 / 99ED0 |
| +14..33 /32-byte storage | ImageName | B6800 / B64C8 |

ImageName setter passes a31-byte copy bound to12840; unconditional termination is not established. Shipped scripts populate nonblank fields through these properties. Time values are120 seconds for IFF_A_2 and60 for IFF_A_8. Restrictions are WRENCH0 for IFF_A_5, RAVAGER3 for IFF_A_7, ALPHA_NOVA7 for IFF_B_9, and INVALID otherwise. Weapon rewards are INFLATOPOD24 for IFF_A_4 and PIRATEGUISE30 for IFF_B_10; blank reward cells are left unspecified. These enum IDs come from native weapon exports, not CSV order. Asset sizes/hashes are recorded in the JSON section.

Named `start_challenge → 278DB0` starts runtime challenge state. `set_challenge_failure → 278D48` performs runtime cleanup and ID bookkeeping without writing a saved failure-count array. `set_challenge_success → 27A9C8` clears runtime IDs at `101AF0D0 /101AEFF8`, calculates/adds bolts, conditionally grants the configured weapon through466B70 and quick-select integration252B08, and increments the saved win counter once on either branch. Both runtime IDs are outside the serialized interval. A counter-only file edit does not reproduce this transaction; no challenge editing controls are enabled.

Reward routine `2CEAB0` reads the raw BE32 count and subtracts1 modulo32 bits when `unsigned32(WpnReward+1)>1`, then compares the adjusted low32 bits as signed32. Negative adjusted count gives0 bolts; zero gives base bolts; one uses float32 scale `3EA8F5C3` (approximately0.33); higher counts use `3DCCCCCD` (approximately0.1). Repeat payouts use PPC fused single-precision multiply/add with25, division by50, truncation and multiplication by50. Predicate `2D1860` can multiply the result by100 with32-bit arithmetic; the return converts unsigned32 to float32. Runtime config, floating-point rounding and grant timing are not captured in a static save, so the app does not present a computed current payout as confirmed.

To reproduce against plaintext working copies (never point a decoder at encrypted GAME.SAV):

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodArenaChallenges.py --elf artifacts/ghidra/BCUS98127-02.00/EBOOT.ELF --assets artifacts/tod-assets-v02.00 --save artifacts/tod-research-capture/USA-GAME.plaintext.bin
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodArenaChallenges.py --elf artifacts/ghidra/BCUS98127-02.00/EBOOT.ELF --assets artifacts/tod-assets-v02.00 --save artifacts/tod-research-capture/USA-GAME.plaintext.bin
```

## Gameplay segments, timers, reward accumulators and retained log

The `gameplay_segments` section reproduces **58 exact byte guards** using [Inspect-TodGameplaySegments.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGameplaySegments.py). The executable identity is checked before decoding. These are static storage/operation confirmations checked against the actual plaintext snapshot, not in-game validation of arbitrary edits.

### Ten segment records per world

Initializer `35DFA8` calls `35DD98` ten times with stride `(1<<6)-(1<<4) = 0x30`. Save selector `2D14E0` computes **`488 + saved_load_level*408 + physical_segment_slot*30`**. Twenty world slots are initialized (`35E110`); only nineteen have native level names. Each world's first `0x1E0` bytes contain ten records, followed by two256-byte object bitsets at `+1E0` and `+2E0`, mapped below.

| Segment member | Type | Confirmed role |
| --- | --- | --- |
| `+00` | BE float32 | Adjusted elapsed accumulator; tick adds runtime delta; reset event additionally adds `+04 * config10FC8` |
| `+04` | BE float32 | Current-attempt elapsed accumulator; tick adds the same delta, reset/finalization clears it |
| `+08` | BE uint32 | Reset-event counter; `2CE518` uses `lwz/addi/stw`, not float arithmetic |
| `+0C` | BE float32 | Finalizer stores `max(0, runtime baseline + runtime modifier)` |
| `+10` | BE float32 | Experience reward accumulator; confirmed weapon-XP consumer, not hero-XP balance |
| `+14` | BE float32 | Bolt reward accumulator, not bolt wallet balance |
| `+18` | BE float32 | Raritanium reward accumulator, not raritanium wallet balance |
| `+1C/+20/+24` | Three BE float32 | Cached experience/bolts/raritanium totals, respectively; not current payouts |
| `+28` | BE word | Zeroed by initializer, meaning unresolved |
| `+2C` | Byte, nonzero predicate | Named gameplay-segment completion flag |
| `+2D..+2F` | Three opaque bytes | Preserved; initializer does not prove padding |

Registrations **`89D960: complete_segment → 2C8A18 → 2782E8 → 2D15C8`** and **`89D968: is_segment_complete → 2C8950 → 2782B0 → 2D1538`** establish the flag's name. Runtime string lookup resolves segment names to slots; the retained log's name order is not a static slot catalog. These records are separate from the active/completed mission lists at10148/10AF8.

`2D15C8` calls `2CE328` only for a previously clear flag, then stores1 at `+2C`. Finalizer/tick/reset paths skip saved segment operations when **saved restart-counter predicate `2D1860` reads906EC nonzero**; completion still sets the flag after invoking the skipped finalizer. Native `-replay` CLI handling now confirms engine replay context; localized game-mode naming remains unverified. Therefore a set flag alone does not prove a log append. Runtime checkpoint mask at10330610+44 is separate, outside the saved block.

Reward consumers confirm `2CEF70 → 3842B8 → 369AA8` delivers bolts to hero state+41C, while `2CEBC0 → 3842B8 → 36A458` delivers raritanium to+420. Their segment accumulators are+14/+18. No current payout or safe edited balance is calculated. Cache byte **world+403** is read/set by `2CF4C8`, which also stores world reward totals at3E0/3E4/3E8. Its nonzero state reuses cached totals; it is not another mission-completion flag.

### Log count and six floats plus one integer

Finalizer `2CE328` increments saved **BE32 count at10144**, writes a `0x9C` record at **`8764 + old_count*9C`**, and copies level/loaded-segment names into the two64-byte fields. The span8764..10144 contains **200 physical slots**, not27. This is a structural read bound: a safe native writer capacity check has not been established.

| Log member | Type | Native source |
| --- | --- | --- |
| `+80` | BE float32 | Runtime101E8D70+0 baseline after recalculation |
| `+84` | BE float32 | Timing modifier from `2CDD20` with elapsed reset to zero and config24/28/2C |
| `+88` | BE float32 | Segment+00 adjusted elapsed before clearing |
| `+8C` | BE float32 | Loaded segment config+20 reference time |
| `+90` | BE float32 | Runtime `2CDBF8` result+0, accumulated adjusted time |
| `+94` | BE float32 | Runtime `2CDBF8` result+4, accumulated reference time |
| `+98` | BE uint32 | Segment+08 reset-event counter, copied with `lwz/stw` |

**Assembly is essential here:** the decompiler incorrectly represents the counter as a float. Actual log entries contain raw00000001/00000002/00000003, which are integer counts, not tiny denormal time values. Exact time units, difficulty terminology and reset-event cause remain unverified; the inspector applies no time conversion or percentage label.

Initialization `35E110` passes save+5528 to `35D9A0`; its store at `35DBB8` clears relativeAC1C, hence saved10144. It does **not** clear the preceding log buffer. The supplied plaintext SHA-256 `F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463` has count0, all200 segment records zero, and27 retained nonzero log entries. These are **retained beyond saved count**, not active progress or a completion count. For example retained record0 has adjusted elapsed1145.373779296875, configured reference1000 and reset-event count1. The zeroed current segment state and retained log can coexist; no repair is appropriate from this snapshot alone.

The app adds read-only **Gameplay segments** (190 named-world rows by default;200 physical records in Technical). **Saved locations** shows storage status, keeps nonzero retained entries, and bounds Technical reads to200 slots. Details explain all mapped fields and preserve raw bytes/nonfinite values. `TOD_SaveGameplaySegment_verified` and `TOD_SaveGameplayLog_verified` supplement, rather than overwrite, the earlier observed types. No new editing controls are enabled.

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGameplaySegments.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin"
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodGameplaySegments.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin" -v
```

The five native tests cover bundled-map/type reproduction, nonboolean flags, integer/float distinction, unusual/nonfinite bits, unknown bytes, last physical slots, stale entries, malformed count clipping, invalid inputs and unchanged sources. App fixtures independently exercise scalar types, retained-entry presentation and detached snapshots; actual-save checks compare the new views against decrypted working-copy bytes.

## Per-world object state and spawn-suppression bitsets

[Inspect-TodWorldObjectFlags.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWorldObjectFlags.py) reproduces the `world_object_flags` map section using **44 exact byte guards** against the fingerprinted USA executable. The two previously opaque256-byte arrays are **32 BE64 words / 2,048 physical object-slot bits each**. Initializer35DFA8 clears the two arrays independently; twenty physical world records are initialized, nineteen have native level names.

| Saved bitset | World member / world0 save offset | Native operations | Confirmed interpretation |
| --- | --- | --- | --- |
| Recorded object state | `+1E0` / `668` | Clear2F7720, set2F77A8, check2F7830 | Per-object lifecycle state restored by consumers; not universally a dead/killed flag |
| Spawn suppression | `+2E0` / `768` | Mark2F7930, load predicate2F79E0, loader2F8690 | A set bit rejects the corresponding definition in native load mode1 only |

For world `l` and physical object slot `s`, bitset base is `668 + l*408` or `768 + l*408`. Word address is `base + 8*floor(s/64)` and integer bit is `s%64`. **File byte** is `word + 7 - floor((s%64)/8)`, byte mask `1<<(s%8)`. For the first bitset in world0, slot0 is byte66F mask01, slot63 byte668 mask80, slot64 byte677 mask01, and slot2047 byte760 mask80. These are not byte-LSB-first arrays; BE64 word order matters.

### Runtime indices are not object names or UIDs

The accessors receive a runtime object-entry pointer, obtain the entry-array base through object-pool root1064FC80, and derive a slot from aligned entry stride **180**. Assembly subtracts the base, signed-shifts7 and low32-multipliesAAAAAAAB, effectively dividing a valid aligned difference by384. Native set/clear derive world stride as `(1<<10)+(1<<3)=408` and use state pointer101EFB20 from descriptor TOC89FF20. TOC slots89FC64/89FC74 point to the runtime pool;89FC68/89FC78 point to serialized state; mode2 slot89FC7C points to runtime checkpoint10330610.

An arbitrary pointer or stored object UID cannot safely be substituted. The physical2,048-bit capacity does not establish that all slots are valid/populated or that native accessors check bounds. The runtime pool and per-level definition table are not captured by the save; **no named object catalog is inferred from bit numbers**, and indices from different worlds do not necessarily identify the same object. This catalog is separate from the named object counters and inventory IDs mapped earlier.

### Verified consumers and load-mode qualifications

`2DD698` checks recorded object state before calling `2DD588`; that routine invokes an object virtual callback and sets the saved bit. Separate initialization3BEB78 uses the same bit to select alternate runtime state9. These paths establish persistence/restoration of object-specific state, not one universal “killed” interpretation. The first bitset has both set and clear accessors; the second bitset's inspected writer sets a bit only when runtime object+68 flag10000 is present, then forwards through common object-manager dispatch2501C8/68EC38. No original method/class name is asserted from that virtual call.

`2F79E0` reads a16-bit mode at loaded definition+42:

- **Mode1:** return true only when the object's spawn-suppression bit is clear. Loader2F8690 iterates48-byte definitions and skips entries whose predicate is false before forwarding creation. A clear bit alone is not a complete loader-acceptance guarantee.
- **Mode2:** runtime checkpoint mask+44 blocks the associated gameplay segment; otherwise use definition byte40 before saved segment completion and byte41 after completion. The saved segment byte is world+slot*30+2C. Runtime checkpoint state is outside serialized GAME.SAV.
- **Other modes:** this predicate returns true; other loader/runtime conditions are not removed or claimed irrelevant.

No set bit is promoted to a mission/collectible checklist or completion percentage. Reset dependencies, runtime slot/name mapping and controlled in-game before/after behavior remain unresolved. The third reward channel still has no confirmed player-facing label: its traced consumers forward a runtime message value, which is not enough to rename it XP.

### Actual save and inspector

All **40 physical bitsets are zero** in the supplied USA plaintext snapshot. Restart counter906EC is3; the directly observed counter value makes predicate2D1860 true and therefore gates segment tick/reset/log finalization. This does not explain every other zero flag or prove an exact replay/challenge mode. Original encrypted GAME.SAV, metadata/PFD and ELF are unchanged.

The new read-only **World object flags** view shows38 rows for nineteen named levels by default and40 physical rows in Technical. Select a row for all set slot indices,32 exact words and byte-order rules. **Set bits** is a stored-bit count, not a tally of killed enemies, objects present or collectibles completed. `TOD_SaveWorldObjectFlags_verified` refines world record boundaries without overwriting existing observed/progress structures or applying the type automatically to ELF globals.

The five independent native tests check bundled map/type reproduction, explicit byte ordering, invalid indices, word/bit boundaries, both bitsets, last physical world/slot, adjacent-tail exclusion, input rejection and immutable actual snapshots. App fixtures decode independently with BE64 operations and preserve detached snapshots; actual-save UI checks compare every256-byte band and render the view at minimum and expanded sizes.

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWorldObjectFlags.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin"
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodWorldObjectFlags.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin" -v
```

## Reset-event category counters and temporary runtime selection

The formerly unknown eight-word array at **save `0x5734–0x5754` (end exclusive)** is now confirmed as a separate reset-event category counter bank. The evidence establishes storage and update mechanics, **not names for its categories or a total number of deaths**. All eight words remain zero in the supplied USA snapshot.

### Storage and initialization

`35E110` passes `state+5528` to initializer `35D9A0`. Its loop at `35D9FC..35DA20` clears eight words, advancing four bytes and storing at relative `20C`: `5528+20C=5734`. The bank ends exactly where the independent inventory unlock bytes begin at `5754`. `TOD_SaveResetCategoryCounters_verified` describes this 32-byte bank without modifying earlier structures or assigning a type to unrelated runtime globals.

Writer `2CE518` loads a runtime category from `101E8D70+48`. It skips category 0; otherwise it performs a wrapping integer increment at `state+5734+4*category`. Crucially, this happens **before** calling the saved restart-counter predicate `2D1860`. The later per-segment reset count at `segment+8` is gated, so category counts and segment counts need not agree. No writer range check is present in this path: eight initialized words are a physical boundary, not a proven native guard against arbitrary arguments. The inspector never reads beyond those eight words.

### Recovered native selectors

Five native callbacks call TOC-changing thunk `132D0`, which switches `88FF38` to `89FF20` and forwards the argument to setter `2CDC60`. The table records exact native conditions, not guesses about enemy types or gameplay modes.

| Category | Save offset | Native callback / selection condition |
| --- | --- | --- |
| 0 | `5734` | Increment explicitly skipped; no recovered selector |
| 1 | `5738` | Initialized storage; no selection source recovered |
| 2 | `573C` | `433B0`, call `4357C`: signed runtime state at `+430` less than 29 |
| 3 | `5740` | `18F480`, call `18F4B4`: runtime flags `+8B0`, bit `800` set and bit `1000` clear |
| 4 | `5744` | `4B9E8`, call `4BB08`: runtime state `+4A4` not equal to 2 |
| 5 | `5748` | `3BFA0`, call `3BFBC`: unconditional within this callback |
| 6 | `574C` | `54FB0`, call `55098`: runtime byte `+764` zero, byte `+762` nonzero |
| 7 | `5750` | `18F480`, same call as category 3: bits `800` and `1000` both set |

These runtime member offsets belong to the respective callback objects; they are **not offsets in GAME.SAV**. Virtual tables provide callback relationships but do not establish player-facing category names. The named `set_challenge_failure` implementation `278D48` follows a different runtime arena-state path; it does not establish a per-challenge failure interpretation for this bank.

### Countdown and strict expiration boundary

Setter `2CDC60` writes category `+48` and float32 countdown `+4C=0.25`, using the constant at TOC slot `89F084`. The runtime object at `101E8D70` is below the serialized `101EFB20..10280210` snapshot, so neither current category nor countdown is saved here. Time units remain unverified; **0.25 is not labeled seconds**.

`2CE5D0` passes rate `1.0` (slot `89F088`), runtime delta source `10731DA0` (slot `89F0B0`) and countdown pointer to thunk `24ECB8 → 69B810`. Assembly in `69B810` multiplies the rate by delta member `+4`, then uses a strict comparison. If delta is greater than countdown, it zeros the countdown and returns true; otherwise it subtracts delta and returns false. Equality therefore reaches zero **without clearing category on that call**. Caller `2CE5D0` clears category only on true. Tick `2CE620` calls this expiration path before its restart-counter gate, so that gate does not suppress expiration.

Expiration clears temporary runtime selection, **not any saved counter**. No game code is executed to produce these observations.

### Actual save, read-only view and reproduction

The supplied USA working plaintext contains eight zero counters and saved restart counter `906EC=3`. This is a snapshot observation, not proof that no reset/death events occurred or that every category has been exercised. Original encrypted save and ELF remain untouched.

The **Reset-event counters** view keeps all eight physical slots. Default columns show category ID, exact recorded count and evidence; Technical adds offsets and raw bits. Categories retain “name unknown” labeling. Unsigned values including `FFFFFFFF` and `80000000` are preserved exactly; no repair, inferred totals or new editing controls are added. Research includes the full native catalog and provenance.

`Inspect-TodResetCategories.py` independently reproduces the bundled section using exact ELF identity, derived initialization boundaries, branch targets, TOC identities and **34 byte guards**. Five native tests cover map/type reproduction, selector qualifications, runtime/save separation, unsigned extremes, adjacent unlock exclusion, malformed inputs and unchanged actual inputs. Editor checks cover detached snapshots, friendly/technical columns and minimum-window fit.

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodResetCategories.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin"
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodResetCategories.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin" -v
```

### Why this is not 100-percent semantic or gameplay confirmation

Structural maps cover all file bytes, but many are deliberately opaque. Remaining work includes runtime per-world object-slot/name catalogs and object-specific lifecycle meanings, segment runtime name/slot mapping, timer units/reset-event cause, equipment callback/reset dependencies, runtime arena menu table/order, player-facing reset-category names and category1 selection, any persisted checkpoint/health dependencies, additional snapshot synchronization, runtime grid geometry/world-axis naming and pixel-specific meanings, unnamed common copied-header bytes and final tail byte60DB. The5734 bank has confirmed initialization/increment mechanics, selectors2..7 and runtime expiration; this still does not make it named challenge failures or prove in-game counter semantics. Direct arena IDs/counters/configuration, object-bitset addressing and qualified load predicates, segment/log scalar provenance, RLE grammar, equipment history, fifteen options and two saved load-selection words are established above. All21 grid slots now have native map-label associations and partially verified volume headers/group flags, not a fully understood planet/mission completion map. Tail `0x906E4`, settings word `114C0` and settings bytes `114D6/114D7` remain semantically unresolved; first-person context is established without guessing an option label or polarity. The final word has native engine replay/restart context; localized game-mode naming and completed-playthrough semantics remain unverified. Runtime checkpoint positions are distinguished from saved fields rather than used to fill unknown save offsets.

One snapshot and a stripped executable cannot establish every script-defined key, valid value combination, reset dependency or in-game acceptance rule. Static code evidence, observed values, structural boundaries and gameplay verification are distinct. No completion percentage is assigned to this research, and no “100% compatibility” or “100% mapped” claim is made. Controlled before/after captures and an isolated runtime test environment are required for the remaining behavioral verification; original saves must be kept untouched.

## Import and reproduce

### Ghidra

Import the matching ELF using `PowerPC:BE:64:64-32addr`. Add `Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Ghidra` to Script Manager's script directories, run `ImportTodMap.java`, and choose the JSON map. Look for `TOD_` labels and the `/RatchetClank/ToolsOfDestruction` data-type category. The unmapped third TOC base remains in JSON and is skipped as a standalone label.

The live Ghidra checks cover 1204 mapped annotations (the third TOC reference base is unmapped), 32 structure layouts, repeat-import idempotence and preservation of custom labels/comments. The portable suite verifies the original ELF hash, annotation bytes, serialization/configuration/catalog/progression/collectible/world-state/object/mission-list/bonus/state-storage/settings/arena/global-flag/gameplay-segment/world-object-bitset/reset-category/persistent-grid/grid-routing/grid-geometry/save-tail/reward-channel/mission-key instruction guards and ownership/acquisition relationships. Research decoders reproduce their bundled catalogs independently from the original ELF and check the actual USA plaintext snapshot. When research notes change, the importers retain older notes under `Previous ToD map` markers and keep one current note; custom prose is preserved. Shipped pause-menu evidence separately checks asset identity, four Lua function digests and17asset byte guards without executing scripts or treating asset offsets as ELF VAs. The reference-save inspector verifies unchanged hashes for every original file. Comparison-tool checks use generated fixtures, **not in-game captures**.

For a fresh headless research project, run descriptor preparation **before** analysis, then import annotations. Do not use this fixed-build preparation script on a different ELF:

```powershell
# Set these paths for your installation; the project directory must exist.
& "$GhidraRoot/support/analyzeHeadless.bat" $ProjectDirectory TodResearch `
  -import $ElfPath -processor PowerPC:BE:64:64-32addr -cspec default `
  -scriptPath "$RepoRoot/Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Ghidra" -preScript PrepareTod.java `
  -postScript ImportTodMap.java "$RepoRoot/docs/PS3/ToolsOfDestruction/BCUS98127/v02.00/maps/NativeMap.json"
```

`SurveyTod.java <output-directory> [function-VA ...]` exports string references, descriptor-based TOC-load leads, assembly and selected decompilations. Its direct TOC-load scan assumes the descriptor TOC for that instruction; confirm r2-changing thunks and restore paths in assembly before treating every lead as resolved. Local project/copy/reports are under ignored `artifacts/ghidra/BCUS98127-02.00/`; no game binary is included in the tracked research files.

`TraceTodSave.java <fresh-output-directory> <queries...>` provides a targeted, read-only survey with original instruction bytes. Queries are `f:<VA>` (function), `r:<VA>` (references and TOC leads), `d:<VA>:<hex-size>` (data), `n:<VA>:<decimal-count>` (nearby functions) and `i:<hex-immediate>` (instruction scan). It checks the reference ELF hash, refuses an existing output directory, and marks uninitialized/BSS bytes instead of inventing values. It does not add labels or change types. Example after preparing the project:

```powershell
& "$GhidraRoot/support/analyzeHeadless.bat" $ProjectDirectory TodResearch `
  -process EBOOT.ELF -noanalysis -scriptPath "$RepoRoot/Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Ghidra" `
  -postScript TraceTodSave.java "$RepoRoot/artifacts/tod-weapon-trace" `
  f:0035e710 f:0035e508 f:00695bf8 f:000258c0 f:00027608 `
  f:00465ff0 f:004660a8 f:00465d00 f:00466258
```

### IDA

Load the same ELF with its original virtual addresses as big-endian PowerPC. Choose **File → Script file**, run `Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/IDA/import_tod_map.py`, then select the JSON. The script targets the IDA 9 [IDAPython interfaces](https://python.docs.hex-rays.com/namespaceida__typeinf.html). IDA was not available for a live import test: syntax, map validation and mocked database-safety tests passed, but runtime compatibility is not yet verified. It does not configure PS3 TOCs or correct function prototypes automatically.

### Checks

```powershell
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodElfMap.py --elf "path/to/EBOOT.ELF" -v
```

Checks cover map bounds/types, duplicates, complete sample-region coverage, original ELF SHA-256/signatures, descriptor enumeration, and IDA importer preflight/preservation behavior. ELF/save originals remained read-only. Neither static analysis nor these checks substitutes for controlled in-game testing.
