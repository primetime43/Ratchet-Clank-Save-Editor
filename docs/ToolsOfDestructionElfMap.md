# Tools of Destruction executable map

Research notes for the supplied USA **BCUS98127 v02.00** `EBOOT.ELF`. This map covers startup, PS3 imports, scripting, physics bindings, rendering/SPU diagnostics, audio/middleware anchors and save I/O. It is a starting point, not a complete reconstruction of the game.

## Files to use in IDA or Ghidra

- [Shared address map](maps/ToolsOfDestruction.BCUS98127.v02.00.json): 183 annotations, 118 imports, evidence, byte signatures and five structure definitions.
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

The wrappers do not establish the complete physics engine, native object layouts or safe gameplay patch points. Script names such as `get_hero_bolts`, `get_weapon_ammo` and `get_weapon_level` are additional anchors, not confirmed global-variable addresses.

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
| `+0xC8` / `+0xCC` | Two values `0x20`, meanings unknown | Stores at `0x35E3E0` / `0x35E3A8` |
| `+0xD0` / `+0xD4` | Buffer at object `+0x908`, size `0x1F400` | Stores at `0x35E3AC` / `0x35E39C` |
| `+0xD8` / `+0xDC` | Game buffer at object `+0x1FD08`, size **`0x906F0`** | Pointer calculation `0x35E2E8/0x35E2FC`; size construction `0x35E2CC/0x35E304`; stores `0x35E3A0/0x35E3A4` |

`0x906F0` matches the European sample's exact `GAME.SAV` length. This independently supports the buffer length, **not** every serialized field or cross-region acceptance. The setup routine then calls runtime initialization at `0x694D28` through the cross-TOC thunk described above.

Lua wrapper `0x39D588` names `save_game_exists` on its error path and calls predicate `0x39B700`. The predicate reaches an object through pointer slot `0x8A2ACC` and returns true only when both words at object `+0x100` and `+0xFC` are nonzero. Their exact purposes remain unknown; this is not a verified on-disk header parser.

The serializer, inventory-to-file copy, health/armor fields, upgrade-bit semantics and any internal checksum remain unverified. The observed save inventory/gameplay types are included for manual analysis only, with candidate members clearly named. No editor fields were enabled or changed by this research.

## Import and reproduce

### Ghidra

Import the matching ELF using `PowerPC:BE:64:64-32addr`. Add `Tools/Ghidra` to Script Manager's script directories, run `ImportTodMap.java`, and choose the JSON map. Look for `TOD_` labels and the `/RatchetClank/ToolsOfDestruction` data-type category. Ghidra 12.0.3 successfully imported 182 mapped annotations; the unmapped third TOC base remains in JSON.

For a fresh headless research project, run descriptor preparation **before** analysis, then import annotations. Do not use this fixed-build preparation script on a different ELF:

```powershell
# Set these paths for your installation; the project directory must exist.
& "$GhidraRoot/support/analyzeHeadless.bat" $ProjectDirectory TodResearch `
  -import $ElfPath -processor PowerPC:BE:64:64-32addr -cspec default `
  -scriptPath "$RepoRoot/Tools/Ghidra" -preScript PrepareTod.java `
  -postScript ImportTodMap.java "$RepoRoot/docs/maps/ToolsOfDestruction.BCUS98127.v02.00.json"
```

`SurveyTod.java <output-directory> [function-VA ...]` exports string references, descriptor-based TOC-load leads, assembly and selected decompilations. Its direct TOC-load scan assumes the descriptor TOC for that instruction; confirm r2-changing thunks and restore paths in assembly before treating every lead as resolved. Local project/copy/reports are under ignored `artifacts/ghidra/BCUS98127-02.00/`; no game binary is included in the tracked research files.

### IDA

Load the same ELF with its original virtual addresses as big-endian PowerPC. Choose **File → Script file**, run `Tools/IDA/import_tod_map.py`, then select the JSON. The script targets the IDA 9 [IDAPython interfaces](https://python.docs.hex-rays.com/namespaceida__typeinf.html). IDA was not available for a live import test: syntax, map validation and mocked database-safety tests passed, but runtime compatibility is not yet verified. It does not configure PS3 TOCs or correct function prototypes automatically.

### Checks

```powershell
python -B Tests/TestTodElfMap.py --elf "path/to/EBOOT.ELF" -v
```

Checks cover map bounds/types, duplicates, complete sample-region coverage, original ELF SHA-256/signatures, descriptor enumeration, and IDA importer preflight/preservation behavior. ELF/save originals remained read-only. Neither static analysis nor these checks substitutes for controlled in-game testing.
