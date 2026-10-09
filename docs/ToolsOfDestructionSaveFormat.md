# Tools of Destruction save format

Initial offset map for the PS3 `BCES00052_SAVE_1` sample. `GAME.SAV` contains readable, big-endian game state; `PARAM.SFO` is a little-endian metadata container, and `PARAM.PFD` is a separate big-endian integrity database. The game data begins with repeating inventory records, not an identified magic/version/length header. Do not apply the HD trilogy's `USR-DATA` block header to this file.

**Status:** the wrapper headers are mapped; game-state structures are partially mapped. A byte pattern is not enough to establish a field's gameplay meaning. No new fields are enabled for editing.

All offsets are hexadecimal and relative to the named file. Ranges use an **exclusive** end. Evidence levels:

- **Documented:** established container format or existing currency offsets.
- **Code-backed:** verified against the exact USA v02.00 ELF; not a substitute for in-game load tests or cross-region validation.
- **Observed:** exact bytes, lengths, names or repeating patterns in this sample.
- **Candidate:** plausible gameplay meaning; needs controlled comparison saves.
- **Unknown:** retained without a guessed meaning.

## Reference files

| File | Bytes | Purpose |
| --- | ---: | --- |
| `GAME.SAV` | 591,600 (`0x906F0`) | Game state, already plaintext in this sample |
| `PARAM.SFO` | 2,736 (`0xAB0`) | Save metadata, title, account binding and subtitle |
| `PARAM.PFD` | 32,768 (`0x8000`) | PS3 integrity database, version 3 |
| `ICON0.PNG` | 108,305 | 320 × 176 RGBA save icon |
| `PIC1.PNG` | 696,304 | 1000 × 560 RGBA background |

The SFO subtitle is `Planet Sargasso `, including a trailing space. Presence of a PFD does **not** establish that `GAME.SAV` is encrypted. This sample has both a PFD and readable game state, but no `RPCS3_BLIST` field. Use **Open Decrypted Folder** if opening this exact sample in the editor. The survey does not validate PFD cryptographic integrity or console acceptance.

Sample `GAME.SAV` SHA-256: `BEB457F9F5C750C46F2AD27E9DEFB15090785311696EAE7D5178904205DD949C`. Original files were read only and their hashes checked again after inspection. Account-binding values and opaque PFD keys are omitted from reports.

## Game data overview

These ranges cover the entire sample, including unknown areas. The whole-buffer copy is now verified in the USA executable; most internal subranges remain an observed partition rather than a fully understood schema.

| Range | Size | Contents | Evidence |
| --- | ---: | --- | --- |
| `0x00000–0x00280` | `0x280` | 32 item/weapon records with IDs 0–31, stride `0x14` | Count, stride and several fields code-backed |
| `0x00280–0x00284` | 4 | Acquisition/removal counter, sample 46 | Code-backed updates; not equated to flagged-record count |
| `0x00284–0x0041C` | `0x198` | Integer lists, `FFFFFFFF` sentinels, repeated small values | Unknown; possible inventory ordering/unlock arrays |
| `0x0041C–0x00420` | 4 | Bolts, uint32 BE | Documented |
| `0x00420–0x00424` | 4 | Raritanium, uint32 BE | Documented |
| `0x00424–0x00428` | 4 | `00000020` (32) | Unknown |
| `0x00428–0x0042C` | 4 | `41000000` (float32 8.0) | Candidate bolt multiplier |
| `0x0042C–0x08764` | `0x8338` | Flags, floats, arrays and sparse binary state | Unknown |
| `0x08764–0x097D8` | `0x1074` | 27 named gameplay records, stride `0x9C` | Observed |
| `0x097D8–0x906F0` | `0x86F18` | Large sparse regions and further binary state | Unknown; not proven padding |

The documented currency offsets are implemented in `SaveProfile.cs`. The multiplier candidate matches both the sample's plausible 8.0 value and the relative bolts/raritanium/multiplier layout in [RatchetHax's ToD memory definitions](https://github.com/ParadoxEpoch/RatchetHax/blob/main/games/rctod_ps3_npua80965.js). **RAM addresses are not automatically save offsets**; the external layout supports the multiplier hypothesis but does not verify that field. The executable snapshot linkage below establishes the conversion only for the identified saved-state block in the supplied build.

### Inventory records

For record ID `i`, the base is `i * 0x14`, for `i = 0..31`. All 32 sample IDs match their array index; initializer `0x466A60` independently establishes the count and stride in code.

| Relative offset | Size | Type | Meaning |
| --- | ---: | --- | --- |
| `+0x00` | 4 | uint32 BE | Item/weapon ID used for definition lookup |
| `+0x04` | 4 | float32 BE | Weapon XP; progress and level recalculation use it |
| `+0x08` | 4 | float32 BE | Ammo; script getter integerizes the float |
| `+0x0C` | 4 | uint32 BE | Modifier mask selecting weapon-definition upgrade entries |
| `+0x10` | 1 | uint8 | Script ownership flag: any nonzero value satisfies `is_weapon_owned`; other getters also check definition flags |
| `+0x11` | 1 | uint8 | Zero-based stored level; eligible script getter returns this plus one |
| `+0x12` | 2 | Opaque bytes | Unknown; preserve |

Do not decode the final four bytes as one meaningful BE integer. IDs 1–15 contain `01 09 00 00`; other records contain `01 00 00 00`. The code confirms that `09` is stored level 9, exposed as level 10 when eligible. All 32 sample records satisfy the script ownership predicate, including empty-looking slots; ownership alone does not prove a usable weapon. The initializer at `0x465C98` does not write the final two bytes; this does not prove they are padding.

The names below come from RatchetHax's ID catalog; the values and offsets are observed in the sample. Weapon names can change with upgrades. Ammo, XP, stored level and the mask's modifier-selection role are now code-backed in the USA build. Specific upgrade-node meanings, prerequisites, prices and valid editing combinations still need verification.

| ID | Base | Catalog name | Ammo float | Modifier mask |
| ---: | --- | --- | ---: | --- |
| 0 | `0x000` | Unknown | 0 | `00000000` |
| 1 | `0x014` | Combuster | 100 | `00003FFE` |
| 2 | `0x028` | Fusion Grenade | 10 | `000007FE` |
| 3 | `0x03C` | Shock Ravager | 36 | `00003FFE` |
| 4 | `0x050` | Tornado Launcher | 5 | `00000FFE` |
| 5 | `0x064` | Buzz Blades | 260 | `00003FFE` |
| 6 | `0x078` | Predator Launcher | 30 | `0000FFFE` |
| 7 | `0x08C` | Alpha Disruptor | 5 | `000007FE` |
| 8 | `0x0A0` | Pyro Blaster | 40 | `00007FFE` |
| 9 | `0x0B4` | Plasma Beasts | 10 | `00001FFE` |
| 10 | `0x0C8` | Shard Reaper | 40 | `00003FFE` |
| 11 | `0x0DC` | Negotiator | 15 | `00000FFE` |
| 12 | `0x0F0` | Nano-Swarmers | 6 | `00007FFE` |
| 13 | `0x104` | Mag-Net Launcher | 16 | `0000FFFE` |
| 14 | `0x118` | Razor Claws | 50 | `00000FFE` |
| 15 | `0x12C` | RYNO IV | 832 | `00007FFE` |
| 16–31 | `0x140–0x280` | Unmapped IDs | See JSON survey | All zero masks |

For example, record 1 has `00000001 47A33965 42C80000 00003FFE 01090000`: ID 1, XP ≈83,570.79, ammo 100, modifier mask `0x3FFE`, ownership byte 1, stored level 9 and two unknown bytes. There is no proven checksum, signature, save version or total-length field in this prefix. `0x00000004` is a record field, **not an established header version**.

### Verified snapshot and inventory dependencies

The exact USA v02.00 ELF uses RAM block `0x101EFB20`, length `0x906F0`, as its saved state. Snapshot function `0x35E710` copies it byte-for-byte to the save-manager buffer at object `+0x1FD08`; restore function `0x35E508` copies the same bytes back. Both call byte-copy implementation `0x81A9A8` through thunk `0x252428`. File callback `0x695BF8` hands that buffer and length to the PS3 save API as secure `GAME.SAV` data. Thus `save offset = game-state VA − 0x101EFB20` for this snapshot layout, not for arbitrary game RAM. Details and exact instruction guards are in the [ELF map](ToolsOfDestructionElfMap.md#verified-snapshot-and-weapon-state).

The named Lua getters connect the record to gameplay: ammo `0x33C80 → 0x258C0`, level `0x33A98 → 0x27608`, and progress `0x339C0 → 0x27568 → thunk 0x11940 → 0x465FF0`. The getters use the same RAM base and `0x14` stride. Ammo and level are gated by byte `+0x10` and definition flags; inactive records must not be interpreted as usable weapons solely because their numeric fields look plausible.

Editing must preserve dependencies:

- `0x4660A8` stores XP at `+0x04` and recalculates level at `+0x11` from weapon-specific thresholds. On level increase, it also updates ammo and can notify another system. Writing XP alone does not reproduce the game operation.
- `0x465FF0` computes progress between thresholds at weapon-data `+0x230 + 4*level`. The next threshold is capped using `0x465F08`; the equal-threshold path returns a fallback constant. The inspected formula does not clamp arbitrary edited XP.
- `0x465D00` enables a bit in `+0x0C`; if maximum ammo changes, it writes the new maximum into `+0x08`. This helper is not a complete purchase transaction.
- `0x466500` derives maximum ammo from weapon-data `+0x280 + 4*level`, then applies mask-selected attribute-9 modifiers through `0x466258`. Modifier entries begin at weapon-data `+0x464`, stride `0x18`, with count at `+0x6A4`. Node ordering and values depend on runtime weapon definitions; they are not a universal upgrade catalog embedded in the save.

This confirms structural meaning, **not safe editable bounds or successful loads**. The ELF is USA; the reference save is European. Matching size/layout does not prove cross-region compatibility. The read-only survey JSON retains its original candidate property names for backward compatibility; the new `TOD_SaveInventoryRecord_verified` analysis type contains the refined semantics. No new editor controls are enabled.

### Ownership and unlock state

The full named ownership chain is `0x33F40 → 0x25AF0 → thunk 0x12950 → 0x2D1C10`; the leaf returns whether record byte `+0x10` is nonzero. Acquisition helper `0x466B70` sets it to 1, initializes XP/level, can refill ammo and increments word `0x280`. Removal helper `0x466AE8` resets XP/ammo, clears the byte and decrements that word. The sample counter is 46 despite 32 flagged records, so **do not normalize it to the ownership-byte count** without finding all writers and validating the intended invariant.

The separately named `unlock_weapon` path `0x2A4EC0 → 0x27A5B8` sets byte `0x5754 + item ID` to 1. Predicate `0x2D24C0` combines that byte with definition flags and ownership; unlocking availability is not the same as acquiring possession. The total byte-array length remains unknown. Only IDs 0–31 are interpreted by the comparison tool.

The `hero_give_weapon` binding reaches `0x28B4E8`, which validates the hero and ID, acquires through `0x466B70`, delegates inventory integration, optionally sets XP/ammo and can notify another system. See the [ELF ownership and acquisition map](ToolsOfDestructionElfMap.md#ownership-unlocks-and-acquisition) for exact labels and dependencies. Script helpers are not proof that arbitrary file edits safely reproduce those runtime operations.

### Currency and nearby values

| Offset | Bytes | Interpretation | Evidence |
| --- | --- | --- | --- |
| `0x418` | `0022FC63` | uint32 2,292,835 | Unknown |
| `0x41C` | `153814E4` | 355,996,900 bolts | Documented offset; observed value |
| `0x420` | `0092B08E` | 9,613,454 raritanium | Documented offset; observed value |
| `0x424` | `00000020` | uint32 32 | Unknown |
| `0x428` | `41000000` | float32 8.0 | Candidate multiplier |
| `0x42C` | `00000018` | uint32 24 | Unknown |
| `0x430` | `0000000F` | uint32 15 | Unknown |

### Named gameplay records

Record `j` begins at `0x8764 + j * 0x9C`, for `j = 0..26`. Each has a 64-byte NUL-terminated location name, a 64-byte NUL-terminated `gameplay_...` name and a 28-byte numeric tail. Names identify locations/scenarios; they do **not** establish completion, unlock or checkpoint flags.

| Relative offset | Size | Observed contents |
| --- | ---: | --- |
| `+0x00` | `0x40` | Location name and zero fill |
| `+0x40` | `0x40` | Scenario name and zero fill |
| `+0x80` | 8 | Numeric bytes; could be float64 or two words |
| `+0x88` | 16 | Four float-like words, semantics unknown |
| `+0x98` | 4 | Small integer, semantics unknown |

| Base | Location | Scenario |
| --- | --- | --- |
| `0x8764` | metropolis | gameplay_enemy |
| `0x8800` | cobalia | gameplay_default |
| `0x889C` | stratus city | gameplay_enemy |
| `0x8938` | stratus city | gameplay_traversal |
| `0x89D4` | fastoon | gameplay_scavenger |
| `0x8A70` | imperial fight fest | gameplay_enemies |
| `0x8B0C` | apogee space station | gameplay_station |
| `0x8BA8` | pirate base | gameplay_enemy1 |
| `0x8C44` | pirate base | gameplay_warehouse |
| `0x8CE0` | pirate base | gameplay_enemy2 |
| `0x8D7C` | rykan v | gameplay_battlefield |
| `0x8E18` | sargasso | gameplay_decryptor |
| `0x8EB4` | sargasso | gameplay_lombax |
| `0x8F50` | iris | gameplay_seg1 |
| `0x8FEC` | iris | gameplay_seg2 |
| `0x9088` | zordoom prison | gameplay_enemies |
| `0x9124` | zordoom prison | gameplay_enemies_2 |
| `0x91C0` | zordoom prison | gameplay_enemies_3 |
| `0x925C` | kerchu city | gameplay_enemy |
| `0x92F8` | kerchu city | gameplay_enemy2 |
| `0x9394` | kerchu city | gameplay_boss |
| `0x9430` | slags_fleet | gameplay_enemy |
| `0x94CC` | slags_fleet | gameplay_boss |
| `0x9568` | cragmite ruins | gameplay_battlefield |
| `0x9604` | cragmite ruins | gameplay_traversal |
| `0x96A0` | meridian city | gameplay_enemy |
| `0x973C` | fastoon_return | gameplay_battleground |

`0x97D8–0x1014A` is an observed all-zero span. Many later regions alternate populated data and long zero spans. **Do not trim them or label them disposable padding:** zero bytes can encode reserved slots or meaningful default state.

## PARAM SFO header and fields

The PSF container uses little-endian integers and 16-byte index entries. The header and index layout follow [RPCS3's PSF loader](https://github.com/RPCS3/rpcs3/blob/master/rpcs3/Loader/PSF.cpp).

| Header offset | Size | Sample value | Meaning |
| --- | ---: | --- | --- |
| `0x00` | 4 | `00 50 53 46` | Magic `\0PSF` |
| `0x04` | 4 | `0x00000101` | Format version |
| `0x08` | 4 | `0xC4` | Key table offset |
| `0x0C` | 4 | `0x140` | Value table offset |
| `0x10` | 4 | 11 | Field count |

Index entries begin at `0x14`: `+0` uint16 key-relative offset, `+2` uint16 type, `+4` uint32 used length, `+8` uint32 capacity, `+0xC` uint32 value-relative offset. Key offsets are relative to `0xC4`; value offsets are relative to `0x140`. Used length and reserved capacity are not interchangeable.

| Field | Index | Data | Type | Used / capacity | Sample value |
| --- | --- | --- | --- | --- | --- |
| ACCOUNT_ID | `0x14` | `0x140` | `0004` binary | 16 / 16 | Redacted |
| ATTRIBUTE | `0x24` | `0x150` | `0404` integer | 4 / 4 | 0 |
| CATEGORY | `0x34` | `0x154` | `0204` text | 3 / 4 | SD |
| DETAIL | `0x44` | `0x158` | `0204` text | 1 / 1024 | Empty |
| PARAMS | `0x54` | `0x558` | `0004` binary | 1024 / 1024 | Ownership-related blob; internal fields not mapped here |
| PARAMS2 | `0x64` | `0x958` | `0004` binary | 12 / 12 | Opaque binary |
| PARENTAL_LEVEL | `0x74` | `0x964` | `0404` integer | 4 / 4 | 3 |
| SAVEDATA_DIRECTORY | `0x84` | `0x968` | `0204` text | 17 / 64 | BCES00052_SAVE_1 |
| SAVEDATA_LIST_PARAM | `0x94` | `0x9A8` | `0204` text | 1 / 8 | Empty |
| SUB_TITLE | `0xA4` | `0x9B0` | `0204` text | 17 / 128 | Planet Sargasso, trailing space |
| TITLE | `0xB4` | `0xA30` | `0204` text | 41 / 128 | Ratchet & Clank: Tools of Destruction™ |

## PARAM PFD header and tables

Layout follows [flatz's PFD structures](https://github.com/bucanero/pfd_sfo_tools/blob/master/pfdtool/src/pfd_internal.h). Multi-byte integers are big-endian. Cryptographic fields remain opaque in this survey.

| Range | Contents |
| --- | --- |
| `0x00–0x08` | uint64 magic `0x50464442` |
| `0x08–0x10` | uint64 version 3 |
| `0x10–0x20` | 16-byte IV/header key |
| `0x20–0x60` | 64-byte encrypted signature block |
| `0x60–0x68` | uint64 hash bucket capacity 57 |
| `0x68–0x70` | uint64 reserved entry count 114 |
| `0x70–0x78` | uint64 used entry count 2 |
| `0x78–0x240` | 57 uint64 bucket indices |
| `0x240–0x7B60` | 114 entry slots, `0x110` bytes each |
| `0x7B60–0x7FD4` | 57 × 20-byte bucket signatures |
| `0x7FD4–0x8000` | 44 trailing bytes |

Each entry: `+0x00` chain index (8), `+0x08` filename (65), `+0x49` padding (7), `+0x50` opaque key (64), `+0x90` four hashes (80), `+0xE0` padding (40), `+0x108` file size (8).

Used entries are `PARAM.SFO` at `0x240`, size `0xAB0`, and `GAME.SAV` at `0x350`, size `0x906F0`. Both chain indices are 114, the out-of-range terminator. Artwork has no used entry here. Parsing these structures does not verify their hashes or prove PS3 acceptance.

## PNG headers and chunks

Both images have the standard eight-byte PNG signature, followed by an IHDR chunk at `0x08`. The IHDR data begins at `0x10`: BE width (4), BE height (4), bit depth (1), color type (1), compression (1), filter (1), interlace (1). Both samples use bit depth 8, color type 6 (RGBA), and zero for the final three bytes. The container layout is defined by the [W3C PNG specification](https://www.w3.org/TR/png-3/#11IHDR).

Chunks proceed through IHDR, gAMA, cHRM, iCCP, pHYs, IDAT data and IEND. The survey lists every chunk offset, length and stored CRC; it does not validate CRCs or decode compressed pixel data. No trailing bytes follow IEND in either image.

## Repeat the survey

Requires PowerShell 7.2 or later. Reports are generated under ignored `artifacts/`; private source saves are not copied into the repository. The output file must not exist and must be outside the source save folder.

```powershell
./Tools/Inspect-TodSave.ps1 `
  -SourceFolder "C:\Users\primetime43\Downloads\Ratchet & Clank Save Editor\PS3\SAVEDATA\BCES00052_SAVE_1" `
  -OutputFile artifacts/save-mapping/BCES00052_SAVE_1-survey.json
```

Omit `-OutputFile` to return JSON without writing anything. The report includes all SFO fields, PFD table bounds, every inventory/gameplay record, every four-byte word in the first `0x1000` game bytes, printable strings, zero spans, 4 KiB page occupancy and PNG chunks. It refuses unfamiliar/encrypted game prefixes instead of guessing or decrypting them. This initial survey is limited to the observed BCES00052/BCUS98127 ToD layout.

Run the reference-specific checks with `./Tests/TestTodSaveInspector.ps1 -SourceFolder <save-folder>`. They verify the observed tables, privacy redaction, output safeguards, malformed-input rejection and unchanged source hashes. These checks do not replace controlled in-game tests of candidate fields.

## Compare plaintext snapshots

[Compare-TodSaves.ps1](../Tools/Compare-TodSaves.ps1) compares two `GAME.SAV` files without editing them. It requires the exact `0x906F0` size and plaintext sequential record IDs, emits JSON to stdout only, and reads no SFO/PFD or account-binding data. Unknown regions are reported as byte-range/count changes without dumping their contents.

```powershell
./Tools/Compare-TodSaves.ps1 -BeforeFile "before/GAME.SAV" -AfterFile "after/GAME.SAV"
```

Reports include hashes, exact changed ranges, region totals, XP/ammo/level/ownership/modifier changes, added/cleared modifier-bit indices, currency deltas, unlock bytes for IDs 0–31 and acquisition-counter changes. Float changes retain raw bytes, including nonfinite values. `-MaxRanges 200` limits displayed ranges, not total changed-byte/range counts. Differing bytes show correlation, not the cause of a gameplay event; the script does not infer a valid XP/level combination or validate console acceptance.

Run `./Tests/TestTodSaveComparison.ps1 -SourceFile <reference-GAME.SAV>` for 11 checks against this exact sample. Tests generate and modify temporary copies to verify decoding, bounds, masks, unknown ranges and input preservation. **These are generated fixtures, not before/after game captures.** Only one supplied save is available; runtime paired-save and edited-load validation remain outstanding.

## Runtime validation and remaining fields

Executable research is recorded separately in the [Tools of Destruction ELF map](ToolsOfDestructionElfMap.md), with a shared JSON address map and IDA/Ghidra importers. Inventory structure and snapshot linkage are code-backed; paired saves are still needed to test behavior and editing dependencies. Other fields below remain candidates.

Collect paired saves with exactly one intentional change, using copies rather than the only original. Autosave time and unrelated engine state can still change, so repeated pairs are needed.

| Controlled change | Candidate offsets or region | Question |
| --- | --- | --- |
| Fire one Combuster shot | `0x01C` | Does the float decrease by exactly one? |
| Earn XP with one weapon | `i * 0x14 + 4` | Verify XP delta and threshold behavior against gameplay |
| Level up one weapon | `i * 0x14 + 0x11` | Verify level/XP/ammo changes together |
| Buy one raritanium upgrade | `i * 0x14 + 0x0C` | Which bit corresponds to the purchased node? |
| Change only bolt multiplier | `0x428` | Does this float track the displayed multiplier? |
| Acquire or unlock one mapped item | `i*0x14+0x10`, `0x280`, `0x5754+i` and other inventory state | Verify acquisition versus availability and counter/list updates |
| Change health/armor | Unmapped state | Separate current health, max health, XP and armor |
| Complete one scenario | `0x8764–0x97D8` and later state | Distinguish statistics from actual progression |
| Move, save, reload | Unmapped state | Locate checkpoint, planet ID and position fields |

Do not expose speculative fields in the editor until their meaning, bounds, dependencies and in-game load behavior are verified. No internal game checksum algorithm has been established for this sample.
