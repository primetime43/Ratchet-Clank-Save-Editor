# Tools of Destruction save format

[Game overview](README.md) · [USA v02.00 findings](BCUS98127/v02.00/ElfMap.md) · [Research tools](../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/README.md)

This reference covers the supplied PS3 saves: USA `BCUS98127` and Europe `BCES00052`. Field meanings come from the **USA v02.00 executable** unless marked as sample observations. The European layout matches the inspected ranges, but no European executable has been checked.

`GAME.SAV` is `0x906F0` bytes (591,600). Its integers and floats are big-endian. It starts with inventory records, not a known magic/version header. Offsets below refer to **decrypted** game data; range ends are exclusive. IDs and counts are decimal unless prefixed with `0x`.

Research and Save inspector remain read-only. The editing tab supports selected USA settings, owned-weapon ammo and within-tier levels, appearance, quick select and cosmetic bonuses; see [mapped-field edits](../../Usage.md#mapped-field-edits). Unknown bytes must be preserved; matching a layout does not establish that a new edit is safe to load in-game.

## Contents

- [File layout](#game-data-overview)
- [Inventory and equipment](#inventory-and-equipment)
- [Player state](#player-state)
- [Worlds and gameplay segments](#worlds-and-gameplay-segments)
- [Flags and counters](#flags-and-counters)
- [Gameplay log and missions](#gameplay-log-and-missions)
- [Settings](#settings)
- [Compressed map grids](#compressed-map-grids)
- [PS3 container files](#ps3-container-files)
- [Reference samples](#reference-files)
- [Known gaps](#known-gaps)

## Game data overview

These boundaries cover the whole file, including fields whose purpose is still unknown.

| Range | Contents |
| --- | --- |
| `0x00000–0x00280` | 32 inventory records, `0x14` bytes each |
| `0x00280–0x00284` | Acquisition/removal counter |
| `0x00284–0x00304` | 32 quick-select IDs |
| `0x00304–0x00418` | Three banks of 23 object counters |
| `0x00418–0x00488` | XP, currency, equipment, armor, skins and four unknown bytes |
| `0x00488–0x05528` | 20 world records, `0x408` bytes each |
| `0x05528–0x05550` | Five global-event flag words |
| `0x05550–0x056D8` | Partially understood state; see native map |
| `0x056D8–0x05734` | 23 arena win counters |
| `0x05734–0x05754` | Eight reset-event category counters |
| `0x05754–0x086F4` | Unlock arrays and partially understood state |
| `0x086F4–0x08764` | Blueprint, bonus, skill and auxiliary state |
| `0x08764–0x10144` | 200 gameplay log records, `0x9C` bytes each |
| `0x10144–0x10148` | Saved gameplay log count |
| `0x10148–0x10AF8` | 20 active mission lists |
| `0x10AF8–0x114A8` | 20 completed mission lists |
| `0x114A8–0x114D8` | Settings |
| `0x114D8–0x906E4` | 21 compressed map-grid blocks, stride `0x60DC` |
| `0x906E4–0x906E8` | Unknown word |
| `0x906E8–0x906EC` | Saved load-level ID |
| `0x906EC–0x906F0` | Engine replay/restart word |

## Inventory and equipment

### Inventory records

Record `i` starts at `i × 0x14`, for IDs 0–31.

| Member | Type | Meaning |
| --- | --- | --- |
| `+0x00` | u32 | Native item ID |
| `+0x04` | f32 | Weapon XP |
| `+0x08` | f32 | Ammo |
| `+0x0C` | u32 | Purchased modifier bitmask |
| `+0x10` | byte | Ownership; any nonzero value passes the ownership query |
| `+0x11` | byte | Stored zero-based level |
| `+0x12` | 2 bytes | Unknown |

Ownership is separate from availability at `0x5754 + ID`. Ammo and level getters also consult runtime definition flags. The eligible ammo getter floors ordinary finite values; the level getter returns stored level +1. Neither changes the save.

XP, level, ammo and modifiers are related. Native XP updates can recalculate level and refill ammo; modifier updates can change capacity. Editing one raw field does not reproduce those operations. The [definition catalogs](BCUS98127/v02.00/ElfMap.md#weapon-definitions) include all 32 IDs, 28 shipped configurations and 15 upgrade grids.

Word `0x280` changes during acquisition/removal. It is **not the number of nonzero ownership bytes**. The USA sample has value 46 and 25 nonzero ownership records. A mapped removal leaf exists, but its gameplay caller is unresolved.

### Quick select and equipment

| Offset | Type | Meaning |
| --- | --- | --- |
| `0x284 + 4*s`, s=0–31 | s32 | Quick-select item ID; `-1` is empty |
| `0x42C / 0x430 / 0x434` | u32 | Last, previous and older recorded equipped item IDs |
| `0x438` | u32 | Pack dispatch selector; known consumers test exactly 1 |
| `0x43C` | u32 | Pack type: Heli, Thruster, Hydro, Wing (IDs 0–3) |
| `0x440` | u32 | Boot type: Normal, Grind, Gravity, Charge (IDs 0–3) |

The direct quick-select API addresses all 32 slots. Hero insertion uses only the first 24 and removes duplicates through a separate path. [Initial definition flags](BCUS98127/v02.00/ElfMap.md#quick-select) now supply the editor's owned-item eligibility filter for slots 0–23; the last eight remain read-only. Stored indices are not wheel positions. Equipment history is not a set of simultaneous equipped slots. The native boot setter ignores its supplied type and writes zero.

### Object counters

Objects use a **different ID catalog** from weapons. For object ID `i=0–22`:

| Offset | Type | Meaning |
| --- | --- | --- |
| `0x304 + 4*i` | s32 getter | Current count; possession tests nonzero |
| `0x360 + 4*i` | u32 | Peak, raised using unsigned comparison |
| `0x3BC + 4*i` | u32 | Positive additions |

A direct set changes current and may raise peak, but does not change additions. Add wraps current to 32 bits; a signed-positive delta also increases additions, then may raise peak. Reset/restore paths can replace these banks. They are not unique or lifetime pickup totals.

IDs in order: 0 Heli Pack, 1 Thruster Pack, 2 Hydro Pack, 3 Grind Boots, 4 Gravity Boots, 5 Charge Boots, 6 Treasure Mapper, 7 Box Basher, 8 Armor Magnetizer, 9 O2 Mask, 10 Qwark Info Bot, 11 Golden Groovitron, 12 Verdigris Upgrade, 13 Praxus Upgrade, 14 Hexagonal Washer, 15 Statues, 16 Souls, 17 Ship Parts, 18 Turrets, 19 Timer, 20 Timer Detonator, 21 Timer Clock, 22 Arena Count. Timer names do not establish units.

Golden Groovitron's current/peak/positive-addition words are at `0x330/0x38C/0x3E8`. They are separate from event 286 (`0x5548`, bit 30 of the big-endian u64): the USA sample has all three words set to 1 while the event is clear. The native object query reads only current. Do not treat these as mirrored flags or repair their disagreement.

Fixed +1 producers are confirmed for Charge Boots, Statues and Souls. Souls updates its counters **before** later linked-handle checks. A configured producer sets a global flag before adding its selected object, without locally rejecting an already-set flag. See [object grants](BCUS98127/v02.00/ElfMap.md#object-grants).

## Player state

| Offset | Type | Meaning |
| --- | --- | --- |
| `0x418` | u32 | Hero XP, not current health or a stored level |
| `0x41C` | u32 | Bolts |
| `0x420` | u32 | Raritanium |
| `0x424` | u32 | Special bolts spent |
| `0x428` | f32 | Bolt multiplier |
| `0x444 + 4*i`, i=0–4 | u32 | Armor ownership; nonzero predicate |
| `0x458` | u32 | Selected armor ID |
| `0x45C + 4*i`, i=0–8 | u32 | Skin ownership; nonzero predicate |
| `0x480` | u32 | Selected skin ID |
| `0x484–0x488` | 4 bytes | Unknown |
| `0x5774 + i`, i=0–4 | byte | Separate armor availability |
| `0x86F4` | u32 | Blueprint mask |
| `0x86F8–0x8706` | 14 bytes | Bonus/cheat states; zero is not necessarily locked |
| `0x8706–0x8708` | 2 bytes | Unknown |
| `0x8708` | u32 | Weighted skill-point total |
| `0x870C–0x8710` | 4 bytes | Uninterpreted |
| `0x8710–0x8718` | u64 | Earned skill bits, IDs 0–59; high four bits unknown |

Armor IDs: 0 None, 1 Durafiber, 2 Hyperplate, 3 Tetramesh, 4 Quantonium. Ownership, availability and selection are independent.

Skin IDs and shipped special-bolt costs: 0 None (0), 1 Dan (6), 2 Snowman (3), 3 Cragmite (6), 4 Pete (6), 5 Cronk (4), 6 Zephyr (4), 7 Jailbird (0), 8 Furioso (3). Jailbird availability requires ownership. A zero price is not an unlock rule.

Special-bolt balance is collected count minus `0x424`, using signed-32 subtraction. The 19 shipped level totals sum to 32. Extra bits and negative balances are retained, not repaired.

The 60 skill definitions total 750 points. Awards add each definition's value, not one point per bit. Completing IDs 0–58 triggers ID 59, HARDCORE. Blueprint grants, weighted score, earned skill bits and bonus states are separate fields.

The editor offers add-only skill awards: preserve the existing score, add each newly granted definition's weight, and award HARDCORE only when a new award completes IDs0–58. High bits60–63 and producer-progress fields are untouched; existing inconsistencies are not repaired. Score overflow and combining this action with the score-replacing unlock-bonuses helper are rejected. No runtime notifications or in-game acceptance are implied.

Bonus requests: `0x86F9` hero head (0 Off, 1 2x, 2 4x, 3 0.5x), `0x86FB` enemy head (0 Off, 1 2.5x, 2 0.5x), `0x86FD` commentary (0 Off, 1 On), `0x8701` James Zurkon (0 Off, 1 On), `0x8703` mirror (0 Off, 1 On). Counts include state 0. Editing requires existing score `0x8708` of at least 50/100/200/400/500 respectively. Commentary dispatch additionally requires runtime language ID1, not stored here; no localized language name or playback is inferred. Zurkon has no local consumer score check and a separate runtime override can still select its alternate when Off. Unknown states, score and earned bits are preserved. Other bonus slots remain read-only.

Multiplier editing writes only `0x428`, bounded to finite 1–20, with an existing nonzero replay/restart word at `0x906EC`. Loading seeds its runtime accumulator; a sampled health decrease can reset the multiplier to 1. Runtime cache/countdown fields are not serialized and must not be written to same-numbered file offsets.

Developer actions reproduce two native writes: grant-all ORs `0x0007DEE4` into blueprint mask `0x86F4`; enable-all sets score `0x8708` to 840 and changes only zero bytes in `0x86F8–0x8705` to 1. Nonzero states, earned bits and unknown blueprint bits are retained. This does not award all skills or prove every bonus is active.

Hero XP passes through runtime float32 conversion and a fractional accumulator. Reload can lose precision for large integers; the native routine does not simply assign a saved level. Current health and checkpoint position are runtime state with **no confirmed dedicated save offset**.

## Worlds and gameplay segments

World `l` starts at `W = 0x488 + l × 0x408`. There are 20 physical records, but only 19 named native levels. Slot 19 remains unnamed. Internal names are in `settings.level_selection.catalog` in the [native map](BCUS98127/v02.00/maps/NativeMap.json).

### World record

| Member | Type | Meaning |
| --- | --- | --- |
| `+0x000–0x1E0` | 10 × `0x30` | Gameplay segments |
| `+0x1E0–0x2E0` | 32 × u64 | Recorded object lifecycle bits |
| `+0x2E0–0x3E0` | 32 × u64 | Spawn-suppression bits |
| `+0x3E0 / +0x3E4 / +0x3E8` | f32 | Cached experience, bolts and raritanium rewards |
| `+0x3EC` | u32 | Collected special-bolt mask |
| `+0x3F0 / +0x3F4` | u32 | Bolts/raritanium diminishing-reward ladder indices |
| `+0x3F8 / +0x3FC` | f32 | Corresponding remainders |
| `+0x400` | byte | Level unlocked |
| `+0x401` | byte | Level visited |
| `+0x402` | byte | Nonzero excludes the level from native menu eligibility; exact name unknown |
| `+0x403` | byte | Reuse cached reward totals |
| `+0x404–0x408` | 4 bytes | Unknown |

Each object band has 2,048 physical slot bits. They are runtime pool indices, not named pickups or inventory IDs. Recorded state is not universally a killed flag; spawn suppression is confirmed for load mode 1, not every mode.

### Gameplay segment

Segment `s` starts at `W + s × 0x30`, for s=0–9.

| Member | Type | Meaning |
| --- | --- | --- |
| `+0x00` | f32 | Adjusted elapsed accumulator |
| `+0x04` | f32 | Unmodified elapsed accumulator |
| `+0x08` | u32 | Reset-event count |
| `+0x0C` | f32 | Finalized timing scalar |
| `+0x10 / +0x14 / +0x18` | f32 | Experience, bolts and raritanium accumulators |
| `+0x1C / +0x20 / +0x24` | f32 | Cached reward totals |
| `+0x28` | u32 | Initializer writes zero; meaning unknown |
| `+0x2C` | byte | Completion flag; nonzero predicate |
| `+0x2D–0x30` | 3 bytes | Unknown; untouched by the world initializer |

The experience reward channel has a confirmed **weapon-XP** consumer. These are not wallet balances or current payouts. Timing units remain unknown. Completion does not guarantee logging or every reward/reset path.

The USA assets provide 56 reference segment-name associations across 19 worlds. Physical slot 0 is reserved in the name catalog; a retained gameplay-log string is not a substitute for this mapping.

## Flags and counters

| Offset | Type | Meaning |
| --- | --- | --- |
| `0x5528–0x5550` | 5 × u64 | Global event flags: 292 named IDs, 320 physical bits |
| `0x56D8 + 4*i`, i=0–22 | s32 getter | Arena wins; ID 0 INVALID, IDs 1–22 named challenges |
| `0x5734 + 4*i`, i=0–7 | u32 | Reset-event category counts; not arena failure counters |
| `0x8720` | u64 | Dance producer progress, separate from earned skill bit 48 |
| `0x8728` | u32 | Bonus-target progress mask |
| `0x872C / 0x8730` | u32 | Wrapping event counts; gameplay names unresolved |
| `0x8734` | u32 | Quick-select warning counter; updated before rejection branches |
| `0x8738` | byte | Full-list message-request latch |
| `0x8739–0x8740` | 7 bytes | Unknown; explicitly zeroed by initializer |
| `0x8740` | u32 | Next-level selection |
| `0x8744 / 0x8748` | f32 | Accumulated adjusted/reference timing scalars |
| `0x874C / 0x8750` | f32 | Countdown gates; units unknown |
| `0x8754` | f32 | First-restart median of positive finalized segment scalars |
| `0x8758` | u32 | Decryptor win-path count |
| `0x875C` | u32 | Sixaxis-enabled Decryptor losses since success |
| `0x8760` | f32 | Decryptor spark-speed multiplier |
| `0x906E8` | u32 | Saved load-level ID, not necessarily current planet |
| `0x906EC` | u32 | Engine replay/restart state |

For a u64 bit bank, ID `i` selects word `i // 64`, integer bit `i % 64`. Since words are big-endian, logical bit 0 is in the last byte of its word. Global bits 292–319 are unnamed; native operations have no local enum-count bound.

Flags can be set, cleared or consumed. A clear bit does not universally mean unfinished. Arena native IDs, Lua source indices and displayed rows are different index spaces; the installed runtime arena table remains unresolved.

Dance compares all 64 progress bits to `0x000000000FFFFFFF`; high bits prevent that award request. Bonus-target progress does not contain the runtime pending set or identify the remaining targets.

CLI `-replay` writes 1 to `0x906EC`. Selective restart writes `min(wrapping_u32(old + 1), 1000)`. This proves engine replay context, not a completed-playthrough count. Saved load ID, next-level selection and the SFO subtitle need not agree.

## Gameplay log and missions

### Gameplay log

There are 200 physical records at `0x8764 + j × 0x9C`. Count is stored at `0x10144`.

| Member | Type | Meaning |
| --- | --- | --- |
| `+0x00 / +0x40` | 64-byte strings | Location and segment names |
| `+0x80 / +0x84` | f32 | Runtime baseline and post-reset timing modifier |
| `+0x88 / +0x8C` | f32 | Adjusted elapsed and configured reference |
| `+0x90 / +0x94` | f32 | Accumulated scalars from saved `0x8744 / 0x8748` |
| `+0x98` | u32 | Reset-event count, not a float |

Initialization clears the count without erasing old records. The USA sample contains 27 named records but count 0: those names are **retained history**, not active entries.

### Mission lists

Active lists start at `0x10148`; completed lists at `0x10AF8`. Each bank has 20 lists of `0x7C` bytes. A list holds ten `0x0C` entries followed by a u32 count at `+0x78`.

Entry members: title lookup ID at `+0`, description lookup ID at `+4`, flags at `+8`. Flag bit 0 is optional; bit 1 is complete. Higher bits are unknown. There is no separate available bit established by the getter. Script indices are one-based.

Completion copies the lookup IDs, ORs `0x2` into the destination's existing flags and compacts the active list. It does not simply copy the source flags. Native searches trust counts; the viewer bounds reads to ten entries. Completed-list count also supplies the missions-completed getter.

The native map contains 81 title/description lookup pairs. These are keys, not recovered localized mission text.

## Settings

The settings block is `0x114A8–0x114D8`. Boolean fields use nonzero predicates; the viewer keeps their original values.

| Offset | Type | Setting |
| --- | --- | --- |
| `0x114A8 / 0x114AC` | u32 | Camera X/Y inversion |
| `0x114B0` | f32 | Camera speed |
| `0x114B4 / 0x114B8` | u32 | Look X/Y inversion |
| `0x114BC` | u32 | Control-scheme index |
| `0x114C0` | u32 | Unnamed camera-mode-related option |
| `0x114C4 / 0x114C8 / 0x114CC` | f32 | Voice, effects and music volumes |
| `0x114D0` | byte | Help text |
| `0x114D1` | byte | Subtitles |
| `0x114D2` | byte | Quick select pauses |
| `0x114D3` | byte | Sixaxis |
| `0x114D4` | byte | Rumble |
| `0x114D5` | byte | Surround |
| `0x114D6–0x114D8` | 2 bytes | Unknown |

Float setters clamp ordinary finite inputs to 0–1; raw getters can still expose unusual values. Scheme 0 uses camera inversion APIs, while scheme 1 uses look inversion APIs in the shipped menu. `0x114C0` has camera-mode consumers, but its original option name and hold/toggle behavior are unknown.

Settings stores precede runtime application. A stored surround or rumble value does not prove hardware activation; changing one volume requests application of all three audio buses.

## Compressed map grids

There are 21 blocks at `0x114D8 + slot × 0x60DC`. Each represents a native 512 × 512 grid, not a planet completion percentage.

| Member | Contents |
| --- | --- |
| `+0x00–0xC8` | Copied 200-byte volume definition |
| `+0xC8` | u32 encoder accumulator |
| `+0xCC` | Readiness byte |
| `+0xCD` | Compressed payload start |
| `+0x60D0` | Declared encoded length |
| `+0x60D4–0x60DB` | Seven group flags |
| `+0x60DB` | Unknown final byte |

Two equal bytes introduce a BE16 additional-repeat count; otherwise bytes are literals. Decoded output is capped at `0x40000` bytes. The accumulator is **not** a checksum or exact zero-pixel count. Preserve compressed tokens, including final runs clipped by the output cap.

The copied definition includes pointer bits, class 535, a generation/slot handle, indices and seven rectangle/image groups. Pointer and handle values are historical runtime data; the inspector never follows them. Physical slot, browse position, level label and image ID are distinct.

Native baked values map 0→state 0, 1–7→state 1, 8–15→state 2. Geometry and a qualified 14 × 14 clearing brush are mapped, but complete pixel meanings and world-axis names are not. The USA sample has 19 ready blocks; slots 3 and 4 are unready.

## PS3 container files

### PARAM SFO

`PARAM.SFO` uses little-endian integers. Magic is `00 50 53 46`; the header contains format version (`+0x04`), key-table offset (`+0x08`), value-table offset (`+0x0C`) and entry count (`+0x10`). The entry table begins at `0x14`.

Each 16-byte entry contains u16 key-relative offset, u16 type, u32 used length, u32 capacity and u32 value-relative offset. Used length and capacity are different. Types include binary `0x0004`, text `0x0204` and integer `0x0404`.

Useful keys: `TITLE`, `SUB_TITLE`, `SAVEDATA_DIRECTORY`, `ATTRIBUTE` and `ACCOUNT_ID`. `PARAMS`/`PARAMS2` contain binary metadata; account bindings are redacted in research reports. Subtitle text is not a reliable current-planet field.

### PARAM PFD

`PARAM.PFD` is a separate big-endian integrity database. The European sample is version 3 and `0x8000` bytes.

| Offset | Contents |
| --- | --- |
| `0x00` | u64 magic `0x50464442` |
| `0x08` | u64 version |
| `0x10–0x20` | IV/header key |
| `0x20–0x60` | Encrypted signature block |
| `0x60 / 0x68 / 0x70` | u64 bucket capacity, reserved entry count, used entry count |
| `0x78` onward | Bucket indices, file entries and bucket signatures |

The sample has 57 buckets, 114 entry slots of `0x110` bytes and two used entries: `PARAM.SFO` and `GAME.SAV`. File-entry layout and signature fields are retained in the container inspector. Parsing a PFD does not verify its signatures or prove console acceptance. Its presence alone does not prove game data is encrypted.

### Artwork

`ICON0.PNG` and `PIC1.PNG` are ordinary PNG files. The European sample uses 320 × 176 and 1000 × 560 RGBA images. They are not game-state records.

## Reference files

| Sample | Game data | Evidence |
| --- | --- | --- |
| Europe `BCES00052_SAVE_1` | Plaintext, `0x906F0` bytes | Save observations only; executable version unknown |
| USA `BCUS98127_SAVE_1` | Encrypted, `0x906F0` bytes | Inspected through a detached plaintext copy; exact v02.00 ELF available |

SHA-256 identities:

| Input | SHA-256 |
| --- | --- |
| European plaintext | `BEB457F9F5C750C46F2AD27E9DEFB15090785311696EAE7D5178904205DD949C` |
| USA encrypted GAME.SAV | `FA16668A09319AF0193F53674C7ED0DE7434189EA488E3FAB5AF4782D2D10D48` |
| USA detached plaintext | `F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463` |

The European sample has a PFD but readable game data; use **Open Decrypted Folder** for that sample. Source saves, artwork and account bindings are not bundled. Inspection/tests use copies and check that original files remain unchanged.

## Known gaps

- Unknown inventory tails, prefix gap, segment/world tails, grid-header bytes, `0x906E4` and unnamed settings fields.
- Exact timer units, event-counter names and every reset/restore dependency.
- Per-world object-slot identities, remaining bonus-target identities and live arena-table installation.
- Persisted health/checkpoint dependencies, if any; the known runtime structures are not saved fields.
- Controlled before/after captures, in-game acceptance of new edits and other executable builds.

Full addresses, byte guards, catalogs and per-path qualifications remain in [NativeMap.json](BCUS98127/v02.00/maps/NativeMap.json). The [tools guide](../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/README.md) explains how to inspect and compare copies.
