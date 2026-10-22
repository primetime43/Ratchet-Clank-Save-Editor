# European trilogy RC1 native save and inventory map

[Reference identity](README.md) · [Save format](../../SaveFormat.md) · [Extracted map](maps/NativeMap.json)

## Executable identity

The collection disc is `BCES01503`; its RC1 save ID is `NPEA00385`. These findings use `USRDIR/RC1.ppu.self`, decrypted locally with PkgLens CLI 1.1.0 `unself`. No executable version has been independently identified. Use the exact ELF fingerprint rather than assuming that every European release shares its addresses.

| Binary | Bytes | SHA-256 |
| --- | --- | --- |
| Original SELF | 9,439,648 | `5ECEF33D70471C448CA9D9CAFC5B1B4E702963B9FB6B40CD51D5043E5CFEF16B` |
| Decrypted ELF | 9,437,216 | `CCE4E741C395518DC4374CF87A7A81E6975F573F99CAD8AC2B6B3EAAFA4BAE9A` |

ELF is big-endian PowerPC64 with PS3 32-bit addresses. Function descriptors occupy `0x703548..0x71A327`, with TOC `0x722328`. There are 11,192 distinct aligned code entries in the descriptor range. File-backed load segments start at VA `0x10000` / file offset `0`, and VA `0x700000` / file offset `0x6F0000`. Native addresses below are virtual addresses, not save offsets.

## Native serialization

| Address | Recovered role |
| --- | --- |
| `0xE7984` | Whole-save writer: writes two block strides, then the player block and 20 repeated world blocks |
| `0xE784C` | Block writer: emits ID/length, copies each descriptor's payload, aligns to four bytes, emits `FFFFFFFF / 0`, initializes the block checksum to zero |
| `0xE6FE4` | Whole-save loader: checks both block strides against the reference descriptor tables before reading blocks |
| `0xE6CD8` | Block loader: searches descriptors by ID, copies bounded payloads, records missing/length-mismatched records |

The player descriptor table at `0x726690` has 48 entries of 16 bytes, followed by a zero entry. Each entry stores runtime address, byte length, record ID and a mutable load-status word. The table reproduces every player record ID, length, order and payload offset in the supplied save. Record IDs are not a sorted or contiguous enumeration.

The world descriptor table starts at `0x7269A0`. The writer's first prefix word is the complete player block stride `0x153C`; its second is the repeated world block stride `0x82A4`. The player payload begins at save offset `0x10` and ends at `0x1544`; the first complete player block begins at `0x8`. Player-only edits preserve all following world data. Gold-bolt collection has its own stricter world-record validation below.

| Player record | Runtime root | Save payload | Meaning established here |
| --- | --- | --- | --- |
| 5, 128 bytes | `0x96BFF0` | `0x58` | Mixed player flags; bytes4/5 are Premium/Ultra Nanotech |
| 9, 148 bytes | `0x96C0AC` | `0x11C` | 37 ammo words, indexed by item ID |
| 10, 37 bytes | `0x96C140` | `0x1B8` | Item ownership/unlock bytes |
| 11, 37 bytes | `0x96C165` | `0x1E8` | Per-item flag set by ordinary grants; not a gold-upgrade flag |
| 12, 12 bytes | `0x71FB2C` | `0x218` | Acquisition list: six-bit item IDs with high flags; `FF` is empty |
| 13, 32 bytes | `0x96C1DC` | `0x22C` | Eight stored quick-select IDs; zero is empty |
| 19, 4 bytes | `0x71FB28` | `0x254` | Saved health capacity: 4, 5 or 8 for canonical nanotech tiers |
| 30, 40 bytes | `0x969CA8` | `0x11D8` | Per-item gold-upgrade flags; ten combat items are supported |

The writer copies the descriptor payloads without normalizing neighboring records or alignment bytes. The reader accepts differing lengths with a bounded copy and a status result; the editor deliberately requires the exact observed table shape for new mapped edits.

## Ammo consumers and limits

| Address | Recovered behavior |
| --- | --- |
| `0x8E0F4` | Ammo query: reads `ammo[item_id]` when the item's capacity is nonzero; capacity-zero items use a special availability result |
| `0xAA258` | Spend ammo: compares the signed ammo word against requested consumption, subtracts on success, and updates a separate spent-ammo counter bank |
| `0xAA2E8` | Add ammo: adds to the word, clamps against the unsigned 16-bit capacity and returns the excess |
| `0xEB0F4` | Ownership query: tests `unlocks[item_id] != 0` |

The item definition table starts at `0x737D30`, with 24 bytes per ID. Capacity is the BE16 at `table + id * 24 + 14`. `0xAA2E8` supplies the capacity consumer; the entire native function and the query/spend/ownership functions have pinned fingerprints in the map.

| Item ID | Reference label | Capacity |
| --- | --- | --- |
| 10 | Bomb Glove | 40 |
| 11 | Devastator | 20 |
| 13 | Visibomb Gun | 20 |
| 15 | Blaster | 200 |
| 16 | Pyrocitor | 240 |
| 17 | Mine Glove | 50 |
| 19 | Tesla Claw | 240 |
| 20 | Glove of Doom | 10 |
| 23 | R.Y.N.O. | 50 |
| 24 | Drone Device | 10 |
| 25 | Decoy Glove | 20 |

Names retain the existing [external RC1 reference](https://github.com/RatchetModding/slimseditor/blob/master/slimseditor/game/rac.json). Native code independently establishes the indexed storage and capacities. The table is a shipped reference, not a live runtime query; no dynamic capacity modifications are simulated.

## Implemented edit boundary

The editor exposes these 11 potential ammo fields only for the matching `NPEA00385` layout, and only when the individual ownership byte is exactly `1` and existing ammo lies in `0..reference capacity`. Native ownership accepts other nonzero bytes, but unusual saved flags remain read-only in this implementation. US and Japanese IDs retain currency editing and inspection without these new ammo writes.

Each requested ammo change writes one BE32 at `0x11C + item_id * 4`. The refill action stages the same allowed ammo edits for eligible owned weapons. Ammo-only changes do not grant weapons, change quick select, alter record 11 or synthesize ammo-consumption statistics. Unknown keys, fractional/negative/excessive values and malformed layouts reject the complete batch before source writes.

Save All uses the existing backup, isolated-candidate and encryption verification workflow, then refreshes the session baseline. Subsequent currency-only saves retain earlier ammo edits. As with existing bolt writes, the player checksum word is set to `FFFFFFFF`. The supplied plaintext sample passed exact software byte comparisons and reopen checks on a disposable copy; gameplay reload acceptance remains unverified.

## Weapon grants

The native grant helper is `0x112E18`, called by the successful weapon purchase branch in `0x16CC50`. The surrounding vendor code charges bolts; the editor offers an explicit grant action and does not simulate that purchase. The persistent writes recovered from the helper are:

1. Set `record11[item_id]` and, for a newly owned item, `record10[item_id]` to `1`.
2. For ammo-using items, raise current ammo to at least the BE16 starting amount at `0x737D30 + item_id * 24 + 18`. Existing larger, in-range ammo is retained.
3. If the ID occurs in the 20-word list at `0x737BF0`, add it to the acquisition list as `item_id | 0x40`. The editor bounds this to the physical 12-byte record and refuses overflow or conflicting retained entries.
4. For combat items (native type zero at `0x721008 + item_id * 76`), insert the ID in the first zero quick-select slot when one exists. The editor preserves occupied slots and avoids adding a second copy of an already retained ID.

Runtime equipment selectors, notification buffers and trophy callbacks are outside these saved writes and are not simulated.

### Notification-path boundary

The helper selects a message from a two-bank table at `0x729380`, depending on saved ownership. It compares that message ID with `-1` at `0x112E9C`; opcode `41820090` at `0x112EA0` branches to `0x112F30` when no notification is required. Ghidra's selected language still stops at the Cell `lvlx` instructions, but a separate bounded audit now decodes the memory/control-flow effects of every instruction in the 35-instruction notification block (`0x112EA4..0x112F2F`).

The Cell operations were checked against [RPCS3's opcode decoder](https://github.com/RPCS3/rpcs3/blob/master/rpcs3/Emu/Cell/PPUOpcodes.h) and [interpreter](https://github.com/RPCS3/rpcs3/blob/master/rpcs3/Emu/Cell/PPUInterpreter.cpp). `lvlx` reads an aligned 16-byte region into a vector register; `stvewx` writes one aligned word. The vector splats, arithmetic, conversions and comparison/select operations do not write memory. The audit classifies their effects without executing the game or simulating display timing.

| Instruction / call | Verified effect |
| --- | --- |
| `0x112EC8`, `0x112ECC`, `0x112ED4` | Three `lvlx` reads, effectively at `0x112E10`, `0x71F410`, `0x112E14` |
| `0x112F04 → 0x7B740` | Read-only localized-text lookup; decompiled helper only searches the loaded text table |
| `0x112F14 → 0x5CC8D8` | NUL-terminated string copy to fixed runtime destination `0xA15C8C` |
| `0x112F28` | Reload ownership at `0x96C140 + item_id` for the shared grant tail |
| `0x112F2C` | One-word `stvewx` to runtime control/timer word `0xA15C80` |

Both call targets have pinned function hashes in the map. Neither fixed notification destination belongs to the 48 player payloads or any of the 20 repeated world payloads. The runtime text's length is not inferred from a save, and notification strings/timer values are not fabricated by the editor. Unknown instructions, calls, store destinations or overlap with serialized ranges fail the audit. Ghidra's incomplete pseudocode is not used as proof that the omitted block has no effects.

The former notification-based exclusion is therefore removed. All **15 combat grants** use the same confirmed saved-state tail, including Suck Cannon (ID9), Morph-o-Ray (ID21) and R.Y.N.O. (ID23). Gadget and equipment ownership grants are documented separately below.

| Newly supported ID | Ownership-dependent notification IDs (owned / unowned) | Initial ammo | Acquisition-list entry |
| --- | --- | --- | --- |
| 9, Suck Cannon | 4007 / 21471 | No ammo initialization | None |
| 21, Morph-o-Ray | 14002 / 14002 | No ammo initialization | None |
| 23, R.Y.N.O. | 5014 / 21474 | 25, reference capacity 50 | None |

The three IDs do not occur in the acquisition-membership table at `0x737BF0`. They can therefore be granted even when the separate acquisition list is full. A full quick-select bank is still preserved. As with every grant, the editor requires canonical unowned flags and in-range stored ammo; Suck Cannon and Morph-o-Ray have no manual ammo editor.

| Grant ID | Weapon | Starting ammo |
| --- | --- | --- |
| 9 | Suck Cannon | 0 (no ammo field initialized) |
| 10 | Bomb Glove | 10 |
| 11 | Devastator | 10 |
| 13 | Visibomb Gun | 10 |
| 14 | Taunter | 0 (no ammo field initialized) |
| 15 | Blaster | 100 |
| 16 | Pyrocitor | 120 |
| 17 | Mine Glove | 25 |
| 18 | Walloper | 0 (no ammo field initialized) |
| 19 | Tesla Claw | 120 |
| 20 | Glove of Doom | 3 |
| 21 | Morph-o-Ray | 0 (no ammo field initialized) |
| 23 | R.Y.N.O. | 25 |
| 24 | Drone Device | 3 |
| 25 | Decoy Glove | 10 |

New grants require ownership and record-11 flags to be zero, and a nonnegative in-range ammo word. Acquisition-list items also require a free byte and no conflicting retained entry for the same ID. Existing owned weapons are shown as owned; repeated grants are byte-preserving no-ops and cannot remove ownership or refill ammo.

Combined grants run in ascending native ID order, so dictionary insertion order cannot change their placement. Explicit quick-select edits run first. New ammo/slot choices become available after saving the grant and loading the refreshed baseline. Weapon grants preserve gold-upgrade state and do not spend bolts, synthesize world pickups or award trophies.

## Gold upgrades

Record 30 is **40 bytes at save offset `0x11D8`**, serialized from runtime `0x969CA8` by the descriptor at `0x726860`. A weapon's byte is indexed by its existing item ID. This bank is separate from ownership (record 10) and the ordinary grant flag (record 11).

| Native address | Evidence |
| --- | --- |
| `0x339B70` | Gold vendor state handler: after confirmed dialogue, writes `1` to `0x969CA8 + item_id`, subtracts the item's BE16 ordinary-bolt price from `0x737D44 + id * 24`, then starts an acquisition presentation |
| `0x811CB0` | Ten BE32 vendor IDs: `19, 10, 11, 16, 17, 15, 21, 20, 25, 9` |
| `0x721008 + id * 76 + 54` | BE16 upgrade limit: `1` for those ten combat weapons, `0` for the other five |
| `0x14B214` | Owned weapon inventory builder: a nonzero upgrade byte selects icon variant 4 and the alternate name at item definition offset 58 instead of 56 |
| `0x11B124` | Counts nonzero item bytes over 37 IDs, clamped to ten gold upgrades |
| `0x11B2C4` | Counts collected gold-bolt flags at runtime `0xA0CA34`, clamps collection to 40, subtracts four per counted upgrade and clamps the result to `0..40` |

The purchase instructions at `0x339CC4` form the flag-bank address, `0x339CC8` loads `1`, and `0x339CE4` stores that byte with `stbx`. The separate bank and weapon-ID table were checked against the complete native serialization map. The four purchase/count/balance/icon functions have pinned hashes in the native inspector; both the vendor table and each combat item's upgrade limit must agree before map generation succeeds. The extra item-definition entry at ID36 is outside the combat allowlist and is never exposed.

Supported upgrades are **Suck Cannon, Bomb Glove, Devastator, Blaster, Pyrocitor, Mine Glove, Tesla Claw, Glove of Doom, Morph-o-Ray and Decoy Glove**. The editor exposes canonical owned (`1`) weapons whose upgrade byte is `0` or `1`. Requests are add-only; existing upgrades are disabled in the UI and repeated requests preserve bytes. Unsupported IDs, noncanonical flags, fractions, removals and unowned weapons reject the entire detached batch. A weapon grant must be saved before its gold upgrade becomes available.

This implements the persistent upgrade flag without simulating vendor payment, its presentation calls, equipped-weapon changes or trophy callbacks. Only requested gold bytes change; ordinary bolts, ammo, ownership, acquisition records, quick-select slots, collectibles and all other bytes are preserved unless separately edited. **The game's available gold-bolt balance can still decrease**, because it derives spending from the upgrade flags; this is not an independently stored balance. Upgrades do not require sufficient currency in the editor. Collection flags and progression are not fabricated to fund them.

Tests cover all ten independent byte offsets, mixed batches and rejection without source changes, hidden invalid ammo, staging/cancellation, installed-state refresh, backups and later currency saves retaining upgrades. A disposable copy of the supplied save also receives Gold Bomb Glove with exact-byte comparison and reopening. Gameplay reload and gold weapon behavior remain untested.

## Gadget grants

The same `0x112E18` grant routine covers the following nine item IDs. All use the already-audited notification block, then write ownership at `0x96C140 + id` and the independent grant flag at `0x96C165 + id`. Their ammo-price, capacity and initial-ammo entries in the 24-byte item table are zero, so the native ammo initializer is skipped. None occurs in the acquisition-membership table at `0x737BF0`, so none consumes a byte in record 12.

| ID | Label | Native item type | Auto quick select | Ownership / grant save offset |
| --- | --- | --- | --- | --- |
| 12 | Swingshot | 0 | Yes | `0x1C4` / `0x1F4` |
| 22 | Hydrodisplacer | 0 | Yes | `0x1CE` / `0x1FE` |
| 26 | Trespasser | 0 | Yes | `0x1D2` / `0x202` |
| 27 | Metal Detector | 0 | Yes | `0x1D3` / `0x203` |
| 31 | Hologuise | 0 | Yes | `0x1D7` / `0x207` |
| 32 | Gadgetron PDA | 0 | Yes | `0x1D8` / `0x208` |
| 33 | Map-o-matic | 4 | No | `0x1D9` / `0x209` |
| 34 | Bolt Grabber | 4 | No | `0x1DA` / `0x20A` |
| 35 | Persuader | 5 | No | `0x1DB` / `0x20B` |

The native type lookup uses `0x721008 + id * 76`. Its final type-zero check appends only the six handheld gadgets to the first free quick-select word. Types 4 and 5 bypass quick select. The optional equip branch updates runtime selection roots for types 0, 2 or 3; types 4 and 5 retain the previous roots. The editor preserves all equipped-item state for every gadget rather than reproducing an immediate equip request.

Additional pinned consumers confirm individual flags: `0x80910` gates Metal Detector updates on ID27, `0xEB22C` queries Hologuise ownership, `0xE22F4` chooses map variants using Map-o-matic ownership, and `0x87A88` selects pickup-radius parameters using Bolt Grabber ownership. The previously pinned vendor purchase routine `0x16CC50` selects the ordinary or alternate item-price entry according to Persuader ownership. Names retain the existing RC1 reference labels; none of these functions proves that every quest or world interaction is satisfied.

**Gadget unlocks** exposes these nine add-only grants. New grants require both flags to be zero; canonical owned items (`1`) are retained without repairing flags, adding slots or otherwise changing bytes. Unknown flags and unsupported IDs reject the detached batch. Unused ammo words are preserved even when nonzero because the native gadget path does not touch them. Full acquisition lists cannot block gadget grants, and full quick-select banks are retained.

Combined batches apply explicit slot assignments first, combat grants in ascending ID order second, and gadget grants in ascending ID order third. Handheld gadgets use only the remaining empty slots and do not duplicate a retained matching slot. Passive items are never offered as new quick-select choices. Save a new grant before assigning a specific slot. Currency, world pickups, mission completion, movement equipment, gold-upgrade bytes, statistics and trophy state are preserved unless separately edited. Equipment ownership has its own category below. This implements the inventory state without claiming story completion or gameplay acceptance.

Tests cover all nine flag pairs, six handheld slot paths, preserved unused ammo and acquisition data, no-ops, full wheels, retained slots, mixed combat/ammo/gold/slot batches, rejection guards, UI staging/cancellation, hidden invalid inputs, backup/reopen and failed encryption. A disposable copy of the supplied save also receives all nine grants with exact-byte comparison and source preservation. Gameplay reload remains untested.

## Equipment grants

The nine equipment entries below follow the pinned generic grant routine `0x112E18`. The recovered item types are all nonzero, so they bypass its quick-select append. Their ammo-price, capacity and initial-ammo words are zero; none belongs to the acquisition table at `0x737BF0`. The editor implements the ownership/grant-flag writes without requesting an immediate equip. All use the previously audited runtime notification path.

| ID | Equipment | Native type | Ownership / grant save offset |
| --- | --- | --- | --- |
| 2 | Heli-Pack | 3 | `0x1BA` / `0x1EA` |
| 3 | Thruster-Pack | 3 | `0x1BB` / `0x1EB` |
| 4 | Hydro-Pack | 3 | `0x1BC` / `0x1EC` |
| 5 | Sonic Summoner | 2 | `0x1BD` / `0x1ED` |
| 6 | O2 Mask | 2 | `0x1BE` / `0x1EE` |
| 7 | Pilot's Helmet | 2 | `0x1BF` / `0x1EF` |
| 28 | Magneboots | 1 | `0x1D4` / `0x204` |
| 29 | Grindboots | 1 | `0x1D5` / `0x205` |
| 30 | Hoverboard | 1 | `0x1D6` / `0x206` |

Additional pinned native consumers distinguish possession from selection and gameplay state:

| Native function | Observation |
| --- | --- |
| `0x85B30` | Equipment switching maintains a saved selection bank at runtime `0x969C7C` (record 32, 28 bytes at `0x1214`) and a separate Thruster-Pack selection indicator at `0x969C9C` (record 23, four bytes at `0x1184`). Contextual O2 Mask, Hydro-Pack and boot choices also check ownership and live movement state. |
| `0xA2750` | O2 Mask ownership gates underwater oxygen depletion; Hydro-Pack ownership gates the swimming input path. The editor does not refill oxygen or change movement state. |
| `0x8B690` | Magneboots ownership participates in a movement-state decision alongside live surface/state checks. |
| `0x950E8` | Grindboots update exits when ID29 is unowned and also applies world/location/state restrictions. |
| `0x3D8CA0` | Sonic Summoner ownership is checked with the live selected-equipment value before its consumer runs. |
| `0x23E140` | The Pilot's Helmet pickup checks ownership and additionally changes world/pickup state and runtime headgear selection. Those pickup side effects are not simulated. |

**Equipment unlocks** is add-only and requires both ownership and ordinary grant flag to be zero for a new grant. Existing ownership byte `1` is retained without repairing the other flag. Unsupported IDs, uncertain flags, removals and non-Boolean requests reject the entire detached batch. The native-map extractor requires the expected type for every entry, no ammo initialization/acquisition-list path, and the expected retained selection-record roots and lengths.

Only the two requested flag bytes per new item change. Both saved selection records, unused ammo words, quick-select words, acquisition entries, currency, health, statistics and all world data are preserved unless independently edited. Packs are not automatically selected; select them in-game after saving/reloading. Equipment grants do not complete quests, award race results, spawn pickups or replace story prerequisites. IDs1, 8 and 36 remain excluded. Inventory round trips do not establish gameplay acceptance.

Tests independently compare every byte for each equipment grant and a combined nine-item batch, retaining opaque ammo, full acquisition/quick-select banks and unusual saved selection values. Mixed ammo/weapon/gadget/gold/slot batches, no-op preservation, invalid ownership/flags, UI staging/cancellation, hidden invalid input, original backups, later currency saves and failed encryption are covered. The reference-save check edits only a disposable copy, reopens it and verifies the source folder stays unchanged.

## Gold-bolt collection

Gold bolts live in world record **3003**, not the player block. The native descriptor at `0x7269C0` maps four bytes per world from runtime `0xA0CA34 + world * 4`. All twenty world blocks begin at `0x1544 + world * 0x82A4`; record 3003's payload is at block-relative `0x8024`. Its absolute byte offset is therefore `0x1544 + world * 0x82A4 + 0x8024 + slot`.

The new world map extracts all eleven descriptors from `0x7269A0`, reproducing the complete stride and exact record framing. The application checks every world header, all eleven record IDs/lengths and every terminator before offering collectible writes. A failed check disables only gold-bolt editing; existing player-only editing retains its prior scope. Alignment bytes and unrelated world payloads remain opaque and preserved.

| Function / table | Confirmed role |
| --- | --- |
| `0x1D9D48` | Gold-bolt actor checks the collection flag when initializing; already-collected actors are removed. |
| `0x1DA110..0x1DA138` | Eleven-instruction straight-line store loads the actor's slot, forms `0xA0CA34 + world * 4 + slot`, and stores literal byte `1`. The inspector checks every instruction word in this block. |
| `0x1DA838` | Spawn helper accepts only slot IDs below four and requires an uncollected flag. |
| `0x147044` | Planet menu counts nonzero flags across the four slots and reads the world's displayed total from `0x738608 + world * 4`. |
| `0x11B1B4` | Counts nonzero flags across all 80 reserved bytes and clamps total collection to 40. |
| `0x11B2C4` | Computes available gold bolts from clamped collection minus four per counted gold weapon upgrade, clamped to `0..40`. |

There are **19 count-table entries**, not twenty: the following word belongs to different data. Counts for world IDs0–18 are `0,3,4,3,1,2,2,2,2,2,2,1,2,1,4,2,2,2,3`, totaling forty. World0 and reserved world19 have no exposed collection requests. Unused slots within other worlds are also never written.

The [asset verifier](../../../../../Tools/PS3/RatchetAndClank1/NPEA00385/unknown/Inspect-Rc1GoldPickups.py) independently reads all nineteen supplied `levelN/gameplay_pal` assets from the original RC1 LZMA PSARC. It locates gold-bolt actors (class1134), follows their bounded PVAR descriptors and reads the stored slot IDs. Each world's actual slot set matches `0..count-1`, confirming all forty permitted flags. Archive size is **422,267,854 bytes**, SHA-256 `45375F8EF6150FDECE8680102D2E2A6B6CC5C289F24630AD9F812389A811616C`. Per-asset hashes and slot lists are reproducible without executing or modifying assets.

Gameplay structure offsets were checked against Replanetizer's [gameplay header](https://github.com/RatchetModding/Replanetizer/blob/master/LibReplanetizer/Headers/GameplayHeader.cs), [RC1 actor layout](https://github.com/RatchetModding/Replanetizer/blob/master/LibReplanetizer/Level%20Objects/Gameplay/Moby.cs) and [gold-bolt PVAR declaration](https://github.com/RatchetModding/Replanetizer/blob/master/Replanetizer/PvarConfigs/moby1134.h). Planet labels use the independent [PAL randomizer ID reference](https://github.com/bordplate/rac1-randomizer/blob/main/table_id.lua); native counts, save offsets and actual pickup indices come from the supplied executable/assets. Bolt numbers identify saved slots rather than described physical locations.

**Gold bolts** provides planet filtering, add-only individual flags and **Collect all supported gold bolts**. Canonical flags0/1 are editable; collected flags are disabled in the UI and cannot be removed. Unknown flag values are preserved and excluded from bulk requests. The balance preview follows the native nonzero-count semantics, including retained unknown/unused bytes, and updates for both staged collection and staged gold upgrades. Bulk collection retains edits from every other category and is blocked by invalid numeric text.

Changed world blocks receive the existing remaster disabled-checksum sentinel (`FFFFFFFF`) at block-relative offset4; untouched blocks and no-ops preserve their checksum words. Save All also retains the existing player-checksum behavior. The pinned `0xE8CA0 → 0xE6FE4 → 0xE6CD8` load path consumes world lengths/records without reading those checksum words; the native writer initializes them to zero. No PS2 checksum calculation is introduced.

Only requested collection flags and affected checksum words change. Gold upgrades, ordinary currency, inventory, world visits, mission/race state and the reserved tail remain unchanged unless separately edited. Runtime pickup animations, notifications and trophy calls are not simulated. The actor decompilation still truncates at Cell instructions; the explicitly verified flag-store block, counts and spawn tests establish the persisted field, without treating incomplete pseudocode as a full side-effect audit. Gameplay acceptance and trophy behavior remain untested.

Tests cover every valid flag, unused/world bounds, malformed framing in early/late worlds, unknown flags, exact-byte preservation, checksum no-ops, mixed-category batches, balance clamping, hidden invalid input, filtering, bulk collection, backup/reopen and failed commits. The supplied save is edited only on disposable copies and compared byte-for-byte with independently expected changes.

## Quick-select editing

`0x143C30` copies the eight saved words to the menu's working bank. `0x143CBC` copies all eight working words back unchanged. `0x143980` handles an owned item's assignment, clearing its prior occurrence before putting it in the chosen slot; it also maintains separate UI-use statistics that the editor leaves untouched.

The editor offers the 15 recognized combat IDs and six supported handheld gadget IDs with canonical saved ownership byte `1`, plus Empty (`0`). Unknown current IDs and other noncombat assignments can be retained unchanged or cleared, but are not offered as new assignments in other slots. Stored indices are not claimed to be wheel positions.

Complete batches support moves and swaps. A new nonzero assignment is rejected if it would duplicate an ID in the final eight-word bank; existing duplicates remain untouched until explicitly changed. UI users clear the old slot before assigning a weapon elsewhere. Grants use only remaining empty slots and never overwrite a full bank.

## Validation added for grants and slots

The RC1 runner verifies each grant's exact changed bytes, all 15 supported IDs, starting ammo, acquisition-list bounds, canonical flag guards, no-op preservation, deterministic batches, atomic slot moves/swaps, preserved unknown IDs, hidden invalid input, staging/cancellation, game reloads and failed-encryption preservation. The supplied save was tested on disposable copies with a Blaster/slot edit and with all three notification-path grants; independently expected bytes matched exactly, reopening retained ownership and R.Y.N.O. ammo, and the source folder remained unchanged. Native tests also reject untraced stores/calls and serialized-address overlap. This remains software validation rather than gameplay acceptance.

## Nanotech upgrades

The native nanotech vendor at `0x24A600` establishes two ownership flags inside player record5 and a linked health-capacity word in record19:

| State | Premium byte `0x5C` | Ultra byte `0x5D` | BE32 capacity `0x254` |
| --- | --- | --- | --- |
| Standard | 0 | 0 | 4 |
| Premium Nanotech | 1 | 0 | 5 |
| Ultra Nanotech | 1 | 1 | 8 |

Record5 is rooted at runtime `0x96BFF0`, with Premium at `+4` and Ultra at `+5`. Record19 serializes runtime `0x71FB28`. These offsets come from the native player descriptor table, independently of inventory item IDs; nanotech flags do not use the weapon/gadget ownership bank.

| Native address | Evidence |
| --- | --- |
| `0xE7154` | Initial save state sets capacity4 and clears the mixed player flag bank |
| `0x24A8C0..0x24A8C8` | Premium flag test branches to the Ultra path only when Premium is already installed |
| `0x24A91C`, `0x24A934..0x24A944` | Premium purchase stores flag1, capacity5 and runtime health5; the separate payment subtracts4,000 ordinary bolts |
| `0x24A96C`, `0x24A9D8`, `0x24AA04..0x24AA14` | Ultra tests its flag, stores flag1 and sets capacity/runtime health8; payment subtracts30,000 bolts |
| `0x7F018`, especially `0x7F2E0..0x7F2E8` | Player initialization copies saved capacity into runtime current health at `0x96BF88` |
| `0x13E634`, especially `0x13E940..0x13E970` | New Game Plus retains both upgrade flags and restores capacity5/8 accordingly |

Current runtime health at `0x96BF88` is outside the serialized record ranges. The editor promotes the persistent tier and relies on normal save loading to initialize health. It does not expose an arbitrary current-health number.

The extractor adds four complete function fingerprints and checks the key instruction words for prerequisite branching, ownership stores, capacity values and initializer/New Game Plus consumers. Ghidra truncates the vendor's later presentation path at Cell instructions (`0x24AA8C`/`0x24AAAC`); both upgrade flag/capacity stores precede those instructions. Vendor payment, presentation and `0x112DC0` trophy calls are not simulated by the editor.

**Nanotech** uses one staged tier selection, with only the current tier and higher tiers offered. Direct Standard→Ultra installs Premium too. Returning to the original tier cancels the pending change; committed upgrades cannot be removed. Only canonical flag/capacity tuples above enable the selector. Unknown flags, Ultra without Premium, mismatched capacity, unsupported keys, fractional/out-of-range tiers and downgrades reject the detached batch. An unavailable selector does not disable other mapped fields.

Writes affect only the two nanotech bytes and saved capacity, plus the existing player checksum sentinel during Save All. Currency, ammo, inventory, selection, world blocks, progression and trophy state are preserved unless separately edited. Regression checks cover every permitted promotion, exact byte preservation, repeated no-ops, mixed-category composition, invalid states, UI staging/cancellation, hidden invalid ammo, backups, reopening and subsequent currency saves. A disposable copy of the supplied RPCS3 save successfully round-tripped Ultra with an independently expected byte comparison. In-game acceptance remains untested.

## Reproduction

The [native inspector](../../../../../Tools/PS3/RatchetAndClank1/NPEA00385/unknown/Inspect-Rc1Native.py) extracts the map directly from the original ELF and rejects mismatched binaries. The [native tests](../../../../../Tests/PS3/RatchetAndClank1/NPEA00385/unknown/TestRc1Native.py) compare it to the bundled JSON and check corrupted-input rejection. The [Ghidra trace script](../../../../../Tools/PS3/RatchetAndClank1/NPEA00385/unknown/Ghidra/TraceRc1Ammo.java) reproduces the selected decompilations with the correct TOC and hash guard.

```powershell
python -B Tools/PS3/RatchetAndClank1/NPEA00385/unknown/Inspect-Rc1Native.py --elf "path/to/RC1.ppu.elf"
python -B Tests/PS3/RatchetAndClank1/NPEA00385/unknown/TestRc1Native.py --elf "path/to/RC1.ppu.elf" -v
dotnet run --project Tests/SaveEditor.RegressionTests.csproj -c Release -- --rc1-save "path/to/RPCS3-save-folder"
```
