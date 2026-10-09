# Tools of Destruction save format

Offset map checked against the PS3 `BCES00052_SAVE_1` plaintext sample and the supplied `BCUS98127_SAVE_1` encrypted USA save. Decrypted `GAME.SAV` contains big-endian game state; `PARAM.SFO` is a little-endian metadata container, and `PARAM.PFD` is a separate big-endian integrity database. The game data begins with repeating inventory records, not an identified magic/version/length header. Do not apply the HD trilogy's `USR-DATA` block header to this file.

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

The table above describes the European sample only. The supplied USA save has an encrypted `GAME.SAV` of the same `0x906F0` length. Its ciphertext SHA-256 is `FA16668A09319AF0193F53674C7ED0DE7434189EA488E3FAB5AF4782D2D10D48`; the working-copy plaintext SHA-256 is `F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463`. The editor's normal `SaveSession` / `Encryption` path decrypted a private copy after a full backup; all five original hashes remained unchanged. Plaintext, save images, account IDs and PFD bindings are not tracked or embedded.

## Game data overview

These ranges cover the entire sample, including unknown areas. The whole-buffer copy is now verified in the USA executable; most internal subranges remain an observed partition rather than a fully understood schema.

| Range | Size | Contents | Evidence |
| --- | ---: | --- | --- |
| `0x00000–0x00280` | `0x280` | 32 item/weapon records with IDs 0–31, stride `0x14` | Count, stride and several fields code-backed |
| `0x00280–0x00284` | 4 | Acquisition/removal counter, sample 46 | Code-backed updates; not equated to flagged-record count |
| `0x00284–0x0041C` | `0x198` | Integer lists and flags; hero XP word at `0x418` | XP code-backed; other meanings unknown |
| `0x0041C–0x00420` | 4 | Bolts, uint32 BE | Documented |
| `0x00420–0x00424` | 4 | Raritanium, uint32 BE | Documented |
| `0x00424–0x00428` | 4 | Special bolts spent; both samples 32 | Code-backed balance getter and skin purchase |
| `0x00428–0x0042C` | 4 | Bolt multiplier; EU 8.0, USA 1.0 | Code-backed getter and update |
| `0x0042C–0x08764` | `0x8338` | Armor, skins, per-level collectible records, skill points and other state | Partially mapped; preserve unknown portions |
| `0x08764–0x097D8` | `0x1074` | 27 named gameplay records, stride `0x9C` | Observed |
| `0x097D8–0x10148` | `0x6970` | Further world/binary state | Partly opaque; not proven padding |
| `0x10148–0x10AF8` | `0x9B0` | Twenty active mission lists, stride `0x7C` | Code-backed structure |
| `0x10AF8–0x114A8` | `0x9B0` | Twenty completed mission lists, stride `0x7C` | Code-backed structure |
| `0x114A8–0x114D8` | `0x30` | Fifteen named options, one unknown word, two unknown bytes | Code-backed settings APIs |
| `0x114D8–0x906E4` | `0x7F20C` | 21 native RLE blocks, stride `0x60DC` | Encoding/storage confirmed, logical payload meanings unknown |
| `0x906E4–0x906E8` | 4 | Unresolved tail word | Unknown |
| `0x906E8–0x906EC` | 4 | Saved load-level ID | Code-backed, not necessarily current runtime planet |
| `0x906EC–0x906F0` | 4 | Restart/playthrough-related word | Exact gameplay terminology remains candidate |

The documented currency offsets are implemented in `SaveProfile.cs`. The multiplier at `0x428` is now established by the supplied executable's saved-state pointer, getter and update path; see the progression map below. **RAM addresses are not automatically save offsets**: the executable snapshot linkage establishes the conversion only for the identified saved-state block in the supplied build.

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

The exact USA v02.00 ELF uses RAM block `0x101EFB20`, length `0x906F0`, as its saved state. Snapshot function `0x35E710` copies it byte-for-byte to the save-manager buffer at object `+0x1FD08`; restore function `0x35E508` copies the same bytes back. Both call byte-copy implementation `0x81A9A8` through thunk `0x252428`. File callback `0x695BF8` hands that buffer and length to the PS3 save API as secure `GAME.SAV` data. Thus `save offset = game-state VA − 0x101EFB20` for this snapshot layout, not for arbitrary game RAM. Details and exact instruction guards are in the [ELF map](BCUS98127/v02.00/ElfMap.md#verified-snapshot-and-weapon-state).

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

The `hero_give_weapon` binding reaches `0x28B4E8`, which validates the hero and ID, acquires through `0x466B70`, delegates inventory integration, optionally sets XP/ammo and can notify another system. See the [ELF ownership and acquisition map](BCUS98127/v02.00/ElfMap.md#ownership-unlocks-and-acquisition) for exact labels and dependencies. Script helpers are not proof that arbitrary file edits safely reproduce those runtime operations.

### Currency and nearby values

| Offset | Bytes | Interpretation | Evidence |
| --- | --- | --- | --- |
| `0x418` | `0022FC63` | uint32 2,292,835 hero XP | Code-backed named `hero_set_xp` chain |
| `0x41C` | `153814E4` | 355,996,900 bolts | Documented offset; observed value |
| `0x420` | `0092B08E` | 9,613,454 raritanium | Documented offset; observed value |
| `0x424` | `00000020` | uint32 32 special bolts spent | Code-backed balance getter and skin purchase |
| `0x428` | `41000000` | float32 8.0 | Code-backed multiplier; EU sample value |
| `0x42C` | `00000018` | Last recorded equipped item ID 24 | USA native history updater; EU observation |
| `0x430` | `0000000F` | Previously recorded equipped item ID 15 | USA native history updater; EU observation |

### Code-backed progression and armor

These meanings were traced in the exact USA v02.00 ELF and checked against the supplied USA plaintext working copy. The shared JSON `progression` section records native functions, all 60 skill definitions, all five armor enums and 478 byte guards. [Inspect-TodProgression.py](../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodProgression.py) independently reproduces that section from the original ELF; its optional save argument reads plaintext only and refuses other sizes or non-sequential inventory IDs.

| Save offset | Stored type | Code-backed meaning | USA observation |
| --- | --- | --- | --- |
| `0x428` | float32 BE | Bolt multiplier | 1.0 |
| `0x444 + 4*i`, `i=0..4` | uint32 BE | Armor ownership; nonzero predicate | All five words 1 |
| `0x458` | uint32 BE | Equipped armor ID | 4, `ARMOR_QUANTONIUM` |
| `0x5774 + i`, `i=0..4` | uint8 | Independent armor unlock bytes | All five bytes 1 |
| `0x8708` | uint32 BE | Weighted skill-point total | 750 |
| `0x8710–0x8718` | uint64 BE | Skill completion bitset; IDs 0..59 | `0FFFFFFFFFFFFFFF`, all 60 complete |

For skill ID `i`, test integer bit `i` of the BE64 word. The equivalent file-byte expression is `0x8710 + 7 - floor(i/8)`, mask `1 << (i % 8)`: ID0 is byte `0x8717` bit0; ID59 is byte `0x8710` bit3. The high four bits and bytes `0x870C–0x8710` remain uninterpreted. The native setter adds each newly earned definition's **point value**, not one; all 60 shipped values sum to 750 and exactly match this save's stored total. It also awards ID59 `SKILLPOINT_HARDCORE` when IDs0..58 become complete. The inspector preserves unknown bits and score mismatches, never repairs them.

Armor IDs are 0 `ARMOR_NONE`, 1 `ARMOR_DURAFIBER`, 2 `ARMOR_HYPERPLATE`, 3 `ARMOR_TETRAMESH`, 4 `ARMOR_QUANTONIUM`. Unlock availability, ownership and equipped ID are separate. The native availability getter can itself set unlock byte `0x5778` when word `0x906EC` is nonzero. Equipping also marks ownership and changes a runtime armor attribute; a purchase additionally deducts bolts and sends notifications. A direct file-word edit does not reproduce these transactions.

The multiplier getter can reset the saved float to 1 depending on runtime state; its update path adds 1 and clamps to 1..20. This is observed **code behavior**, not permission to expose arbitrary multiplier edits. No new editable fields were added: the program's **Skill points**, **Armor**, **Counters & nearby fields** and **Research** views are read-only.

The USA value at `0x418` is 2,315,144 hero XP, now confirmed by the named setter chain below. The saved integer is not current health, maximum health, or a directly stored hero level. Word `0x906EC` is 3; its nonzero predicate gates multiplier updates and final-armor availability, and the restart routine increments/clamps it. Its exact challenge-mode/playthrough interpretation remains a candidate. Health fields, general world flags and named gameplay-record tails remain unresolved.

Reproduce from a working-copy plaintext capture:

```powershell
python Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodProgression.py --elf $ElfPath --save $PlaintextSavePath
python Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodProgression.py --elf $ElfPath --save $PlaintextSavePath
```

### Confirmed hero XP and collectibles

The shared map's `collectibles` section is reproduced by [Inspect-TodCollectibles.py](../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodCollectibles.py) from the hash-guarded USA ELF. It contains 19 native level IDs, nine skin IDs, static prices, per-level totals and 267 byte guards. These are static meanings checked against an actual plaintext working copy, not in-game edit/load tests. Original ELF and save files remain unchanged.

| Save offset | Type | Meaning | USA save |
| --- | --- | --- | --- |
| `0x418` | uint32 BE | Serialized integer hero XP | 2,315,144 |
| `0x424` | uint32 BE | Special bolts spent | 32 |
| `0x45C + 4*i`, `i=0..8` | uint32 BE | Skin ownership, nonzero predicate | Eight owned, ID7 not owned |
| `0x480` | uint32 BE | Selected skin ID | 0, `SKIN_NONE` |
| `0x874 + 0x408*i`, `i=0..18` | uint32 BE | Per-native-level special-bolt mask | Counts match all shipped totals, sum 32 |

Named `hero_set_xp` registration resolves to `0x2BAED0 → 0x28A9B0 → 0x252C78 → 0x23E090`. The thunk restores the appropriate TOC; the leaf writes the saved integer at `+0x418`. A separate runtime fractional accumulator and calculated level byte participate in XP updates. No safe editor bounds or serialized health fields follow from this chain. Legacy JSON observation keys containing `unknown_progression_418` are retained for compatibility; the field meaning is now established.

Per-level records begin at `0x488 + 0x408*i`. Initializer `0x35E110` initializes **20 slots**, ending at `0x5528`; only IDs0..18 are native levels. The mask is record member `+0x3EC`, giving save offset `0x874 + 0x408*i`. Count helper `0x35DDD8` counts all 32 set bits; test `0x35DE08` and setter `0x35DEB0` use local collectible IDs0..31 as BE32 integer bit indices. File byte is `maskOffset + 3 - floor(id/8)`, byte mask `1 << (id % 8)`. Physical pickup locations and the other record contents are not mapped.

Native `get_special_bolts_collected` reaches `0x25CF0`; argument19 (`LEVEL_COUNT`) requests a sum over levels0..18, **not a read of slot19**. That initialized slot's mask at `0x550C` remains uninterpreted. Native totals table `0x10062E4C` contains `(0,1,2,0,1,4,1,3,1,2,4,1,2,1,2,2,2,2,1)`, indexed by the decoded level catalog. The USA masks' popcounts match that vector exactly. The setter awards skill ID46 `SKILLPOINT_GOLDEN` when every count meets or exceeds its respective total. The menu has a conditional level3→18 remap; inspector rows show unremapped storage.

`get_special_bolts_owned` reaches `0x25DB8` and returns **collected minus spent** using native signed-32 subtraction. The USA observation is `32 - 32 = 0`. Extra mask bits, excessive counts, negative balances, and unfamiliar IDs are preserved and displayed, never repaired.

### Confirmed skins

Skin ownership words and selected ID are independent. `is_skin_owned` reaches `0x24B08` and tests any nonzero word; `select_skin` reaches `0x26FC0`, requires ownership, and writes `0x480`. `purchase_skin` reaches `0x27AA0`, checks special-bolt balance against definition cost, marks ownership, selects the skin, increments spent word `0x424`, and notifies runtime systems. Repeated purchases and malformed IDs are not established as safe operations. Availability `0x24B38` returns true except ID7, which requires ownership; a zero price is not proof of unlock eligibility.

| ID | Native identifier | Shipped special-bolt cost | USA owned |
| ---: | --- | ---: | --- |
| 0 | `SKIN_NONE` | 0 | Yes, selected |
| 1 | `SKIN_DAN` | 6 | Yes |
| 2 | `SKIN_SNOWMAN` | 3 | Yes |
| 3 | `SKIN_CRAGMITE` | 6 | Yes |
| 4 | `SKIN_PETE` | 6 | Yes |
| 5 | `SKIN_CRONK` | 4 | Yes |
| 6 | `SKIN_ZEPHYR` | 4 | Yes |
| 7 | `SKIN_JAILBIRD` | 0 | No |
| 8 | `SKIN_FURIOSO` | 3 | Yes |

Cost getter `0x1F0D60` reads the first uint32 of nine 16-byte definitions at `0x840B00`. Remaining definition words are preserved without guessed tag meanings. Owned-skin costs sum to32 in this save and match its spent word; that observation is **not a universal invariant to enforce**, since the purchase routine is a transaction with its own behavior.

The editor's **Hero XP** and **Special bolts spent** summary rows, **Special bolts**, **Skins**, and bundled **Research** topics are read-only. Reproduce the research and input-preservation checks with:

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodCollectibles.py --elf $ElfPath --save $PlaintextSavePath
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodCollectibles.py --elf $ElfPath --save $PlaintextSavePath -v
```

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
./Tools/PS3/ToolsOfDestruction/Inspect-TodSave.ps1 `
  -SourceFolder "C:\Users\primetime43\Downloads\Ratchet & Clank Save Editor\PS3\SAVEDATA\BCES00052_SAVE_1" `
  -OutputFile artifacts/save-mapping/BCES00052_SAVE_1-survey.json
```

Omit `-OutputFile` to return JSON without writing anything. The report includes all SFO fields, PFD table bounds, every inventory/gameplay record, every four-byte word in the first `0x1000` game bytes, printable strings, zero spans, 4 KiB page occupancy and PNG chunks. It refuses unfamiliar/encrypted game prefixes instead of guessing or decrypting them. This initial survey is limited to the observed BCES00052/BCUS98127 ToD layout.

Run the reference-specific checks with `./Tests/PS3/ToolsOfDestruction/TestTodSaveInspector.ps1 -SourceFolder <save-folder>`. They verify the observed tables, privacy redaction, output safeguards, malformed-input rejection and unchanged source hashes. These checks do not replace controlled in-game tests of candidate fields.

## Compare plaintext snapshots

[Compare-TodSaves.ps1](../../../Tools/PS3/ToolsOfDestruction/Compare-TodSaves.ps1) compares two `GAME.SAV` files without editing them. It requires the exact `0x906F0` size and plaintext sequential record IDs, emits JSON to stdout only, and reads no SFO/PFD or account-binding data. Unknown regions are reported as byte-range/count changes without dumping their contents.

```powershell
./Tools/PS3/ToolsOfDestruction/Compare-TodSaves.ps1 -BeforeFile "before/GAME.SAV" -AfterFile "after/GAME.SAV"
```

Reports include hashes, exact changed ranges, region totals, XP/ammo/level/ownership/modifier changes, added/cleared modifier-bit indices, currency deltas, unlock bytes for IDs 0–31 and acquisition-counter changes. Float changes retain raw bytes, including nonfinite values. `-MaxRanges 200` limits displayed ranges, not total changed-byte/range counts. Differing bytes show correlation, not the cause of a gameplay event; the script does not infer a valid XP/level combination or validate console acceptance.

Run `./Tests/PS3/ToolsOfDestruction/TestTodSaveComparison.ps1 -SourceFile <reference-GAME.SAV>` for 11 checks against this exact sample. Tests generate and modify temporary copies to verify decoding, bounds, masks, unknown ranges and input preservation. **These are generated fixtures, not before/after game captures.** Only one supplied save is available; runtime paired-save and edited-load validation remain outstanding.

## Confirmed world progress and quick-select storage

The exact USA v02.00 ELF independently confirms these fields. [Inspect-TodWorldState.py](../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWorldState.py) checks the reference hash, named Lua bindings, full native routines and TOC-changing thunks before decoding. Its 205 original-byte guards and 19-level catalog are bundled under `world_state` in the shared map. All inspector views are read-only; regional behavior and edited-load acceptance remain unverified.

| Save offset | Storage | Code-backed meaning |
| --- | --- | --- |
| `0x284 + 4*s`, `s=0..31` | signed BE32 item ID | Quick-select stored slot; `-1` means empty |
| `0x888 + 0x408*l`, `l=0..18` | byte, nonzero | Level unlocked |
| `0x889 + 0x408*l` | byte, nonzero | Level visited; menu's “seen” reads the same byte |
| `0x88A + 0x408*l` | byte | Nonzero excludes this level from native menu eligibility; actual gameplay name unknown |
| `0x10B70 + 0x7C*l` | BE32 integer | Saved missions-completed counter for the native level |

Quick-select membership and removal search all 32 words. Insertion accepts slots 0–23, and automatic insertion searches only those first 24; it also checks item configuration flags `0x1040`. Slots 24–31 are retained and displayed, not discarded. These indices do **not** establish the physical wheel layout. Only the player0 block is decoded; the routine's `0x484` player stride is not proof that additional player blocks are valid here.

The menu's visitable/visible predicate requires a nonzero level ID, an unlocked byte and a clear exclusion byte. Level3 is suppressed when level18 passes its recursive eligibility check; its displayed mission count then uses level18 storage. The inspector shows unremapped native rows and does not emulate runtime eligibility or claim a completion percentage. Twenty world records are initialized, but the native catalog has only 19 levels; the extra slot is not assigned a planet name.

Mission-counter records start at `0x10AF8`, stride `0x7C`; the getter reads member `+0x78`. The preceding 120 bytes are now mapped as ten entries in the mission-list section below. A counter alone does not resolve mission titles, and the other world-record members remain unmapped.

Actual USA snapshot (`F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463`): all 32 quick-select words are `-1`; all 19 unlocked/exclusion bytes and mission counters are zero; only native level0 has visited byte1. These are exact observations, **not** a claim that the player has no game progress. They coexist with the mapped populated inventory and collectibles, so zero counters are not converted into “0% complete” or silently repaired. The original encrypted save is never changed.

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWorldState.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin"
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodWorldState.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin" -v
```

The program exposes simple **World progress** and **Quick select** views. Technical retains exact offsets, IDs and exclusion bytes; row details explain the asymmetrical bounds, aliases and limitations. Unknown values, unusual nonzero bytes and out-of-catalog IDs are preserved.

## Confirmed object counters and equipment

The three previously opaque 23-word arrays are now independently linked to named object APIs and two matching native enum registrations. They are a separate catalog from the 32 weapon IDs. [Inspect-TodObjects.py](../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodObjects.py) reproduces the shared map's `objects` section with 205 exact-byte guards; `TOD_SaveObjectCounters_verified` maps the three arrays without claiming valid edit ranges.

| Save storage, object ID `i=0..22` | Code-backed role |
| --- | --- |
| `0x304 + 4*i` | Current object count; getter returns signed BE32; possession tests nonzero, including negative values |
| `0x360 + 4*i` | High-water counter, updated using **unsigned** comparison |
| `0x3BC + 4*i` | Accumulated positive additions; signed-positive add deltas only, modulo 32 bits |

`hero_set_num_objects` sets current and raises the high-water value without touching positive additions. `hero_add_object` adds its signed delta to current modulo 32 bits; only a positive delta also increments the additions counter, then it raises the peak using an unsigned comparison. Thus these arrays need not be equal, a direct set is not a pickup, and a negative current value can yield a very large unsigned peak. No normalization is performed. The last additions word ends at `0x418`, immediately before hero XP.

Native IDs in order: 0 Heli Pack; 1 Thruster Pack; 2 Hydro Pack; 3 Grind Boots; 4 Gravity Boots; 5 Charge Boots; 6 Treasure Mapper; 7 Box Basher; 8 Armor Magnetizer; 9 O2 Mask; 10 Qwark Info Bot; 11 Golden Groovitron; 12 Verdigris Upgrade; 13 Praxus Upgrade; 14 Hexagonal Washer; 15 Statues; 16 Souls; 17 Ship Parts; 18 Turrets; 19 Timer; 20 Timer Detonator; 21 Timer Clock; 22 Arena Count. `OBJ_TYPE_COUNT=23` is a bound, not another object. These readable labels format native identifiers; timer/arena names do not prove units or conversion rules.

Actual USA snapshot: current and peak are both `[1,1,1,1,1,1,3,1,1,1,0,1,0,0,0,0,0,0,0,0,0,0,0]`; positive additions are `[0,0,0,0,0,1,3,1,1,0,0,1,0,0,0,0,0,0,0,0,0,0,0]`. In particular, initialized/equipped packs have current1 but additions0, reinforcing that additions must not be called “all items acquired.” The save alone does not prove how each value appears in live gameplay.

The new **Objects & equipment** inspector shows only object and current count by default. Exact high-water/addition counters, offsets, raw current bits and limitations remain available in Technical and row details. Tests cover signed negatives, independent unsigned words, full catalog bounds, actual observations and unchanged input hashes.

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodObjects.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin"
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodObjects.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin" -v
```

## Confirmed active and completed mission lists

[Inspect-TodMissions.py](../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodMissions.py) independently reproduces the `mission_lists` section from exact named bindings, address arithmetic and complete native routines. Each group occupies twenty `0x7C` physical list slots; only native levels0..18 are named. Active lists begin at `0x10148`; completed lists begin at `0x10AF8`. Each list contains ten `0x0C` entries followed by a saved BE32 count at `+0x78`.

| Entry member | Proven meaning |
| --- | --- |
| `+0x0`, BE32 | Title lookup ID, also the native duplicate/search key |
| `+0x4`, BE32 | Description lookup ID |
| `+0x8`, BE32 | Flags: bit0 optional, bit1 complete; all higher bits unknown |

`is_mission_available` returns the inverse of completion bit1; there is **no separate available bit** established by this getter. Script indices are one-based. The combined accessor subtracts1, selects the active list first using its count, then the completed list. Title and description getters feed the stored IDs to native text lookup; numeric IDs are not recovered localized strings.

`add_mission` searches both lists by title ID, skips duplicates and appends to active only when count<10. It stores title/description and the low eight incoming flag bits. `complete_mission` searches active by title ID, copies title/description into the completed destination, ORs completion bit2 into that destination's existing flag word, increments completed count, decrements active count and compacts active entries. The observed path does not visibly copy all original flags or independently check completed capacity; these are code observations, not a justification to reproduce the transaction in an editor or repair game state.

The USA snapshot has zero counts in all19 active and completed lists. Unused entries are not assigned mission names or interpreted as current missions. World progress row details show saved counts and bounded entries when present; Technical/research retains the lookup IDs, unknown flag bits, precise native indices and limitations. If a count exceeds10, inspection reads only the ten physical entries and reports the unchanged original count. No cross-list reads or silent normalization occurs.

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodMissions.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin"
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodMissions.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin" -v
```

## Confirmed blueprint and bonus state

The exact USA ELF's named blueprint and cheat APIs establish `0x86F4` as a BE32 blueprint bitmask and `0x86F8–0x8705` as fourteen native bonus-state bytes. `0x8706–0x8707` remains unknown; `0x8708` is the shared weighted skill-point score used for bonus availability, not a count of earned bits. Full call chains, definition/state catalogs and runtime-index caveats are in the [ELF research](BCUS98127/v02.00/ElfMap.md#blueprints-and-bonuscheat-states).

The supplied USA plaintext has blueprint mask `0x0007DEE4`: all thirteen bits in the native grant-all mask and no additional bits. All fourteen bonus-state bytes are zero and score is 750. State zero does not prove locked. Menu indices can be remapped by a runtime mode that is not inferred from the save; shipped definition thresholds are not a current-availability verdict. The native enable-all routine writes score840 and changes only zero states to1, without awarding earned skill bits. Unknown bytes and unexpected bit/state values must remain unchanged.

Reproduce without modifying either input:

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodBonuses.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin"
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodBonuses.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin" -v
```

The program exposes this as simple read-only Blueprints and Bonuses & cheats views. Physical pickup/planet names and localized bonus/state labels have not been recovered; no new editable fields or gameplay-compatibility claim is introduced.

## Confirmed equipment history and compressed blocks

Saved BE32 words `0x42C`, `0x430`, `0x434` are last/previous/older recorded equipped item IDs. Native updater `1F5570` shifts the history and records the same getter used by named `hero_get_equipped`; they are not dual-wield slots. The USA save contains IDs15/25/0 (Ryno/SwingShot/Wrench). Current runtime state, callback timing, fallback/reset behavior and safe history edits remain unverified.

The twenty-one blocks at `0x114D8`, stride `0x60DC`, contain native RLE storage. Per block: `+C8` encoder accumulator, `+CC` readiness byte, `+CD` compressed payload, `+60D0` declared encoded length, and opaque prefix/tail. Two equal bytes introduce a BE16 additional-repeat count; other bytes are literals. Output is capped at `0x40000` bytes; preserve original compressed tokens, including clipped final runs. The accumulator excludes the first two zero bytes of each zero run; it is neither exact zero count nor checksum.

Nineteen blocks in the USA save are ready and all decode to262144 bytes with matching accumulators; slots3/4 are not ready. Each populated final run is clipped by four bytes. Logical meanings of decoded indices/values and slot-to-planet mapping remain unknown. The [full ELF notes](BCUS98127/v02.00/ElfMap.md#saved-equipment-history-and-compressed-state-blocks) describe proof, layouts and cross-decoder hashes. Stored state blocks and player summary show these facts read-only; no bytes are rewritten or normalized.

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodStateStorage.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin"
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodStateStorage.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin" -v
```

## Saved options and load selections

The exact USA code identifies the **48-byte options block at `0x114A8–0x114D8`**. Its fifteen named fields are listed with native getter/setter addresses in the [settings evidence table](BCUS98127/v02.00/ElfMap.md#saved-settings-and-load-destinations): camera/look inversion words, camera-speed float, control-scheme index, voice/effects/music floats, and help/subtitle/quick-select/Sixaxis/rumble/surround bytes. [Inspect-TodSettings.py](../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSettings.py) derives their offsets from native load instructions and named bindings rather than searching the save for plausible values.

USA observations: camera speed1.0; all inversions and scheme index0; all three volumes `3F666666` (approximately0.9, shown as90%); help text0; subtitles, quick-select pause, Sixaxis, rumble and surround1. Native initializer defaults differ for help text (1) and subtitles (0). Unnamed BE32 word `114C0` is1 and bytes `114D6/114D7` are`0000`, but their meanings remain unknown. The bytes are not normalized or treated as padding. Stub button-layout/rumble-connected APIs do not identify additional saved settings.

Saved load destination is **BE32 at `0x906E8`**; next-level selection is **BE32 at `0x8740`**, not tail word `906E4`. Nineteen native load-name strings form the catalog. The USA snapshot has saved-load ID0 (`metropolis`) and next-level ID`FFFFFFFF`, retained as unmapped without assigning a sentinel meaning. Neither field is necessarily the current runtime planet or the SFO subtitle. The app exposes both in read-only Player summary and options in read-only Game settings; Technical mode retains exact and unknown data.

Runtime checkpoint object `10330610` lies outside the serialized block. Captured position/orientation and valid byte`+EF` are **not** assigned guessed save offsets. Named runtime health accessor resolves object float attribute`6C`; no dedicated saved health field is proven. See the [checkpoint and health findings](BCUS98127/v02.00/ElfMap.md#runtime-checkpoints-and-health-no-saved-offsets-inferred).

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSettings.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin"
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodSettings.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin" -v
```

## Runtime validation and remaining fields

### Arena challenge counters

Exact USA ELF evidence establishes **23 BE32 words at `0x56D8–0x5734` (end exclusive)**, indexed by direct native ID. ID0 is INVALID; IDs1..22 are the named `IFF_` challenges. Getter sign-extension and wrapping increments are preserved; unusual negative values are not normalized. The following **eight words `0x5734–0x5754` are a separate unknown array**, not a24th challenge or proven failure counts. All31 words are zero in the supplied USA snapshot.

The [arena executable mapping](BCUS98127/v02.00/ElfMap.md#arena-challenges-direct-ids-saved-wins-and-shipped-definitions) joins all22 IDs to shipped config descriptions, restrictions and base rewards; CSV order is not native ID order. Runtime ArenaConfig records are not save records, and the runtime menu table/index order remains unresolved. Success additionally changes currency and potentially inventory/quick-select state. No challenge editing controls or live payout guarantee are enabled; the app provides a read-only **Arena challenges** view.

Executable research is recorded separately in the [Tools of Destruction ELF map](BCUS98127/v02.00/ElfMap.md), with a shared JSON address map and IDA/Ghidra importers. Inventory structure and snapshot linkage are code-backed; paired saves are still needed to test behavior and editing dependencies. Other fields below remain candidates.

Packed-asset research supplies [weapon XP/ammo tables and upgrade-node catalogs](BCUS98127/v02.00/ElfMap.md#packed-weapon-configuration-and-native-field-bindings). The [native ID catalog](BCUS98127/v02.00/ElfMap.md#native-inventory-id-catalog) now independently links all 32 save records to enum/config names through exports, constructors and named getters; CSV order is **not** the ID map. The read-only asset report covers 28 internal configurations and 204 entries including start nodes. All 15 [vendor upgrade grids and their UI checks](BCUS98127/v02.00/ElfMap.md#vendor-upgrade-grids-and-purchasing) are mapped separately from the native purchasing transaction. The native ammo array has 20 slots and the modifier array 24; neither array capacity nor a 32-bit mask establishes playable levels or valid arbitrary upgrades. Asset values, node masks and calculated capacities remain research facts, not gameplay-validated edit limits.

Collect paired saves with exactly one intentional change, using copies rather than the only original. Autosave time and unrelated engine state can still change, so repeated pairs are needed.

| Controlled change | Candidate offsets or region | Question |
| --- | --- | --- |
| Fire one Combuster shot | `0x01C` | Does the float decrease by exactly one? |
| Earn XP with one weapon | `i * 0x14 + 4` | Verify XP delta and threshold behavior against gameplay |
| Level up one weapon | `i * 0x14 + 0x11` | Verify level/XP/ammo changes together |
| Buy one raritanium upgrade | `i * 0x14 + 0x0C` | Which bit corresponds to the purchased node? |
| Change only bolt multiplier | `0x428` | Does this float track the displayed multiplier? |
| Acquire or unlock one mapped item | `i*0x14+0x10`, `0x280`, `0x5754+i` and other inventory state | Verify acquisition versus availability and counter/list updates |
| Buy or equip armor | `0x444–0x45C`, `0x5774–0x5779` | Verify ownership, equipped ID, currency and unlock changes together |
| Earn one skill point | `0x8708`, `0x8710–0x8718` | Verify weighted score, bit order and automatic HARDCORE award |
| Change health | Unmapped state; `0x418` is confirmed XP | Locate current/max health without conflating them with progression XP |
| Complete one scenario | `0x8764–0x97D8` and later state | Distinguish statistics from actual progression |
| Change only one option | `0x114A8–0x114D8` | Verify persisted options and reset/restore timing; retain unknown word/tail |
| Win one named arena challenge | `0x56D8+4*nativeId`, `0x41C`, inventory/quick-select state | Verify the direct counter and currency/weapon transaction together; runtime menu order is not native ID order |
| Move, save, reload | `0x906E8`, `0x8740` and unmapped persisted state | Verify load-selection updates; find any persisted checkpoint/position linkage separately from runtime object |

Do not expose speculative fields in the editor until their meaning, bounds, dependencies and in-game load behavior are verified. No internal game checksum algorithm has been established for this sample.
