# Tools of Destruction: USA v02.00 findings

[Build overview](README.md) · [Save offsets](../../SaveFormat.md) · [Tools and imports](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/README.md)

These findings apply to the supplied PS3 `BCUS98127 v02.00` executable. This page summarizes the useful behavior; [NativeMap.json](maps/NativeMap.json) holds the complete address catalog, instruction guards, structures and path-specific evidence. [WeaponConfigs.json](maps/WeaponConfigs.json) contains the shipped weapon/modifier definitions.

Code-backed means the behavior was traced in this binary. It does not mean a proposed edit has been tested in-game. Observations from one save are not universal defaults or invariants.

## Contents

- [Executable identity](#executable-identity)
- [Save lifecycle](#save-lifecycle)
- [Weapon definitions](#weapon-definitions)
- [Inventory and purchases](#inventory-and-purchases)
- [Quick select](#quick-select)
- [Object grants](#object-grants)
- [Progression and equipment](#progression-and-equipment)
- [Worlds, missions and events](#worlds-missions-and-events)
- [Maps and settings](#maps-and-settings)
- [Non-save findings](#non-save-findings)
- [Evidence index](#evidence-index)
- [Open questions](#open-questions)

## Executable identity

| Property | Value |
| --- | --- |
| Input | Decrypted `EBOOT.ELF`, 10,923,400 bytes |
| SHA-256 | `0EE9A8414C8FC182BC19FA2A523E6D050D0BE76138B3733AE515798D77D2468C` |
| Format | ELF64, big-endian PPC64, PS3 ABI `0x66` |
| Ghidra language | `PowerPC:BE:64:64-32addr`, compiler `default` |
| Entry | Descriptor `0x859418` → code `0x14360`, TOC `0x88FF38` |
| Saved-state RAM block | `0x101EFB20–0x10280210` |

All addresses on this page are **ELF virtual addresses**. File offsets, save offsets and host-process addresses are different.

### Load segments

| File offset | Virtual address | File bytes | Memory bytes |
| --- | --- | --- | --- |
| `0x000000` | `0x00010000` | `0x82C648` | `0x82C648` |
| `0x830000` | `0x00840000` | `0x6D4E8` | `0x6D4E8` |
| `0x8A0000` | `0x10000000` | `0x56B80` | `0x56B80` |
| `0x900000` | `0x10060000` | `0x14EF00` | `0x82C570` |

File-backed bytes map as `VA = segment VA + file offset − segment file offset`. The final segment's uninitialized memory starts at `0x101AEF00`; it has no initialized file bytes.

### Descriptors and TOCs

There are 23,910 eight-byte function descriptors at `0x859408–0x887F38`: a BE32 code address followed by a BE32 TOC address. They are not instructions or desktop 24-byte PPC64 descriptors.

| TOC | Descriptor count |
| --- | ---: |
| `0x88FF38` | 8,186 |
| `0x89FF20` | 7,519 |
| `0x8AFE5C` | 8,205 |

The third TOC is an unmapped reference base used with negative displacements. Do not create artificial memory there. Cross-TOC thunks change r2; a single global TOC gives incorrect references. Descriptor-backed assembly takes precedence when the decompiler loses r2 across calls/restores.

## Save lifecycle

| Function | Role |
| --- | --- |
| `0x35E2C8` | Save-manager setup: GAME.SAV buffer at manager `+0x1FD08`, length `0x906F0` |
| `0x35E710` | Copies saved state into the manager buffer |
| `0x35E508` | Copies the same bytes back during restore |
| `0x695BF8` | Supplies that buffer as secure GAME.SAV data to the PS3 save API |
| `0x252428 → 0x81A9A8` | Byte-copy thunk/implementation |

This establishes `save offset = saved-state VA − 0x101EFB20` **inside this block only**. Runtime hero objects, checkpoint structures and save-manager members are not automatically serialized fields.

Save staging snapshots state before the worker runs. Load admission, worker completion and later application are separate steps. The existence predicate checks runtime manager words, not a game-data magic header.

Selective restart uses a private capture bank and preservation ranges, not a fresh full copy of every old field. Mission groups are cleared by nested initializers; settings and equipment have distinct preservation rules. Unknown tail word `0x906E4` is copied on full snapshot/restore but zeroed at the selective-restart staging boundary.

## Weapon definitions

Native enum exports and constructor/getter links identify **all 32 inventory records**. CSV row order is not the ID map. The shipped catalog contains 28 weapon/gadget configurations, 204 modifier entries including starts, and 15 vendor grids.

The full ID list is `weapon_configuration.inventory_catalog`; definitions and XP/ammo arrays are in [WeaponConfigs.json](maps/WeaponConfigs.json). Internal names are not necessarily the names displayed in-game.

Important definition limits:

- Native ammo arrays have 20 slots and modifier arrays 24; capacity is not proof of playable levels.
- The WeaponConfig XP array is 20 floats at `+0x230`, with indexed getter/setter `0xB8A68 / 0xB8950`. The same “XP” string also names an unrelated scalar at `+0x14` and HeroConfig's u32 array. Resolve the class and registration, not the name alone.
- `NumLevels` at `+0x460` is the highest populated zero-based index, not a row count. Getter `0xB4940` exposes the unsigned word through float conversion; setter `0xA7478` truncates and stores low 32 bits without a playable-level clamp.
- Maximum ammo uses the **raw stored level** and modifier mask, with no local level-array bound established on this path.
- Matching absolute modifiers are added first, then one summed percentage factor is applied.
- `CrateAmmo[0]` is a separate property from `MaxAmmo[level]`. Combuster's shipped crate amount is 15; actual gained ammo also depends on runtime factors and remaining capacity.
- Vendor node 0 is a start, not an ordinary purchased bit. Adjacency, special-node movement and native purchase admission are separate checks.

## Inventory and purchases

| Routine | Established behavior |
| --- | --- |
| `0x2D1C10` | Ownership query: any nonzero saved ownership byte |
| `0x258C0` | Definition-gated ammo getter; floors bounded ordinary finite values |
| `0x27608` | Same visibility gate; returns stored level +1 |
| `0x4660A8` | XP setter, level recalculation and level-up ammo effects |
| `0x465D00` | Sets a modifier bit and can replace ammo with its new maximum |
| `0x466500` | Level/modifier-dependent maximum-ammo calculation |
| `0x466B70` | Acquisition, ownership publication and counter update |
| `0x466AE8` | Removal leaf; gameplay caller not recovered |

Ammo/level visibility is `(owned != 0 OR definition flags & 0x2) AND !(definition flags & 0x1)`. Ownership alone does not imply visible attributes or a usable weapon.

The removal leaf requests XP/ammo setters **before** clearing ownership and rereading/decrementing the acquisition counter. That decrement wraps; it is not a whole-record reset. A static caller/descriptor-reference survey found no references, which does not prove the leaf is unused.

Runtime weapons borrow the canonical inventory record. Local ammo admission and debit are different routines; some runtime flags bypass admission. A checked request of zero before a later debit of one is not proof of universal per-shot cost. Gelanator has qualified paired debit/refund requests around a runtime latch, not a saved reservation ledger.

Seven consumable records now have a bounded ammo policy: IDs 16/17/18/20/21/22/23, reference capacities 4/2/3/2/1/3/3. Require ownership, stored level 0, finite zero XP, no modifiers and finite ammo within capacity. Only ammo at record `+8` changes. Fractional values are native float storage, not a proved use count. Groovitron (19) remains excluded because Golden Groovitron object 11 and event flag 286 are separate linked state; IDs 24–31 remain excluded.

Golden Groovitron's object query reads only current count at `0x330`, not event 286. The sample has object counts 1/1/1 with that event clear. In `0x475710`, the object query selects runtime float components later copied to a spawned instance; the separate spawn-attempt path debits 1.0 ammo even when creation returns zero. This does not establish successful firing or the complete unlimited-ammo mechanism. No linked-state repair or edit is enabled.

### Purchases and ordering

Upgrade purchase publishes the modifier, conditionally refills ammo, then debits raritanium and notifies runtime systems. Signed wallet admission differs from vendor adjacency/duplicate checks; the transaction itself can charge for an already-set bit.

The topology audit covers 204 nodes: 15 starts, 175 ordinary and 14 special. Of the 189 positive nodes, 182 have complete numeric definitions. Seven specials have unspecified numeric values; that is not proof of a zero effect.

The editor offers 38 ordinary ammo-capacity nodes: positive integer additions of 1/2/4/5/20/30, none percentages or specials. Require a consistent owned weapon, valid XP/level/ammo, an attainable existing mask and an installed adjacent node (start0 implicit). Bits are add-only. Capacity is recomputed in native float32 order and refilled; explicit ammo overrides the refill up to the new limit. Wallet, ownership and callbacks are untouched. Ten capacity nodes are reachable from an empty mask.

Another 132 ordinary nodes are editable for damage, range, blast radius, speed, duration, bolt/raritanium bonuses and spawn count. They use the same baseline and adjacency gates, but preserve ammo because the native capacity walker selects `MOD_AMMO` only. Labels retain signed shipped values; they are not measured final stats. Five `MOD_MISC` nodes and all 14 designated specials stay read-only. Additions cannot supply prerequisites for other unavailable nodes within the same save batch.

The supplied save already has every positive node, so it cannot confirm an addition transition. Synthetic checks do not establish in-game acceptance.

Special query `0x466630` returns true for any enabled declared node of type `MOD_SPECIAL` (16); numeric value, price and ownership are not inputs. Actor wrapper `0x46B328` supplies the borrowed saved mask. Predator consumer `0x478AA8` allows one prior matching target token with special enabled, but rejects two or more; an earlier runtime component check can also reject. This is local target admission, not a projectile-count guarantee. All seven blank-value special bits are set in the sample, but their edits remain read-only pending weapon-specific dependency checks.

The level-five weapon purchase path requires ownership, exactly stored level 4, replay state and definition prerequisites. Dispatch and later recheck sample those conditions separately. Level/XP/ammo publication precedes bolt payment. Repeated normal acquisition can charge an already-owned record.

### Within-tier level edits

The editor now offers the 15 combat weapons' levels only within their existing stored 0–4 or 5–9 tier (shown as levels 1–5 or 6–10). It requires ownership, consistent finite XP, valid ammo and known modifier bits. The reference base capacity is constant within each tier; Ryno's two tiers differ, so that boundary is not crossed.

A changed level also writes its reference float XP threshold. Increases refill the exact reference maximum; decreases preserve ammo. An explicit ammo edit overrides a refill regardless of edit order. Same-level requests preserve the original XP and ammo bits. Ownership, modifiers, unlock bytes, counters and payment fields are untouched. This is a coupled file-edit policy, not a purchase or execution of native callbacks; live definitions and in-game acceptance remain unverified.

Armor purchase, deferred equip, skin purchase and history publication also have separate steps. A direct field edit does not reproduce their callbacks or payment rules.

## Quick select

All 32 item initializers now have a decoded definition-flags argument. Caller stack `+0x70` supplies the low32 word loaded at callee `+0x114` and stored to definition `+0x18` by `0x466804`. Registry publication uses `0x103697B8 + 0x20 + 4*ID`; the bounded resolver reads that same table. These flags are runtime definition fields, **not saved ownership or unlock bytes**.

Native assignment rejects `flags & 0x1040`. Initial flags exclude Wrench (0), CuttingLaser (26), RoboWings (28), MagCycle (29) and Decryptor (31). The [full catalog](maps/NativeMap.json) is under `quick_select_eligibility`; [the inspector](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodQuickSelectEligibility.py) reproduces it with 76 guards.

The named setter admits all 32 slots and updates warning count before validation. Hero insertion uses only the first 24 and removes duplicates across all 32. Neither establishes physical wheel order. Initial flag literals follow verified early-return branches and compiled nonvolatile-register preservation across known initializer helpers; dynamic definition changes remain unverified.

The editor offers slots 0–23, Empty, and owned items passing the initial flag filter. It rejects new duplicates across the whole bank; explicit batch moves/swaps are allowed. Existing unknown values, slots 24–31, ownership and warning state are preserved. This is a conservative file-edit policy, not execution of either native assignment API. In-game acceptance remains untested.

## Object grants

Object IDs are separate from weapon IDs. All three fixed producers request +1 through `0x252F78 → 0x23D870` after receiver/type admission.

| Object | Decimal ID | Producer | Saved current / peak / additions |
| --- | ---: | --- | --- |
| Charge Boots | 5 | `0x3046E8` | `0x318 / 0x374 / 0x3D0` |
| Statues | 15 | `0x308070` | `0x340 / 0x39C / 0x3F8` |
| Souls | 16 | `0x3075B8` | `0x344 / 0x3A0 / 0x3FC` |

The common leaf stores wrapping current first, positive additions second, then raises peak using unsigned comparison. Repeated reached calls can add again. Current `FFFFFFFF` +1 wraps to zero even though additions increase.

Souls adds **before** later linked-handle validation/type dispatch; subsequent local rejection does not explicitly roll back that update. Statues first touches runtime scratch, which is not the saved count.

Configured producer `0x302A10` ORs an actor-selected global flag into saved `0x5528` before rereading the selected object ID and adding it. It does not locally reject an already-set flag or already-present object. Its Ship Parts branch clears runtime scratch, not a saved object. Native ID bounds, configuration and larger dispatch remain unresolved.

These counters are not unique pickup totals. A grant alone also does not establish the separate Souls skill award.

## Progression and equipment

Hero XP is saved as u32 at `0x418`, but native publication/reload goes through float32 and runtime fractional/level state. Carry happens once only when remainder is strictly greater than 1; thresholds use the original input and the routine does not lower an existing runtime level. Large integers can change through reload conversion.

The shipped Hero asset has 98 XP/HP rows; native configuration banks have 100 entries. Those are reference thresholds, not current health or a saved hero level. Runtime health is hero `+0x1784`, upper bound `+0x1788`; checkpoint `0x10330610` is outside the saved block.

Skill score, earned bits and bonus states are independent. Awards use weighted definition values. All 60 shipped values sum to 750; completing IDs 0–58 requests HARDCORE (59). Menu group selectors are not award prerequisites.

The shipped `cheatHandler.changeCheatState` checks availability, then cycles zero-based states with left/right. **Definition state count includes Off**: hero head states 0–3, enemy head 0–2, mirror 0–1. Hero states 1/2/3 multiply the head basis by 2/4/0.5; enemy states 1/2 use 2.5/0.5. These are native factors, not recovered localized labels. The generic setter accepts a wider 1–8 range and does not enforce each definition's count.

The editor changes physical bytes `0x86F9`, `0x86FB`, `0x86FD`, `0x8701` and `0x8703`, with recognized states and existing scores of at least 50/100/200/400/500. Commentary at `0x86FD` is a saved request only: dispatch additionally requires runtime language ID1, not known from the save. No localized language name or playback is asserted. James Zurkon at `0x8701` also tests runtime override `0x101EFB10` and has no local score gate. Off cannot force the default when that override is set. Its alternate/default factory branches pass `0xC3/0x657` with float 0.75 and `0x4B/0x311` with float 1.5; the float's meaning is unknown. Menu APIs remap IDs by runtime language and must not be used as save offsets. Head Off does not explicitly restore the traced transform; mirror's axis remains unknown. In-game acceptance remains untested.

Special-bolt collection uses per-world masks; balance subtracts spent bolts. Skin purchase changes ownership, selection and spent count. Armor availability, ownership and selected armor are likewise separate.

Equipment history records qualified state-entry callbacks, not merely queued requests. Restart filters, restore selection and menu fallbacks can produce different values. Multiplier reset depends on replay and a sampled health decrease; its update accumulator is runtime-only, not a saved timer.

Multiplier edits are limited to saved `0x428`, finite 1–20, with an existing nonzero replay word. This uses the finite native increment range, not a universal native clamp: malformed baselines stay read-only. Loading seeds the accumulator; health loss can reset the selected value. The editor does not grant replay mode, freeze the multiplier or change XP/balances.

## Worlds, missions and events

The save has 20 world records but 19 named levels. Ten segments per record contain timing/reward accumulators and completion bytes. Assets provide 56 segment-name associations and 81 mission lookup pairs; those keys are not localized text.

Mission completion keeps destination flags and ORs completion bit `0x2`; it does not copy all source flags. Compaction leaves inactive bytes. The native code trusts some counts before capacity checks, while inspection reads only physical entries.

Recorded-object and spawn-suppression bands each hold 2,048 pool-slot bits per world. Object-specific callbacks, load modes and allocation generations affect their use. The 18,214 shipped definitions across 19 worlds are an external catalog, **not a stable bit-to-pickup map**.

Global flags have 292 names and 320 physical bits. Set/clear/consume behavior is mapped for selected scripts; a flag is not always a permanent completion record. Arena story flags are independent of the 23 win counters. The eight following words are reset-event categories, not challenge failures; their player-facing names remain unknown.

Gameplay log count is separate from retained contents. The supplied save has 27 named records with count 0. Timing units and event names are not inferred from those strings. Bonus-target progress is separate from runtime pending; one save cannot identify remaining targets.

Decryptor words track a win path, Sixaxis-enabled losses since success, and spark-speed scaling—not generic lifetime wins/deaths or global difficulty.

## Maps and settings

The 21 RLE blocks decode to 512 × 512 grids. Their copied definitions contain historical pointers/handles, rectangles and seven group flags. Logical slot, browse order, level label and image ID are different mappings.

The accumulator is not a checksum or completion percentage. Group visibility can depend on Treasure Mapper. Geometry, state conversion and a qualified 14 × 14 brush are mapped, but complete pixel meanings remain unknown.

Fifteen settings are named. Stores precede runtime requests: invalid scheme values can remain saved despite fallback routing, surround application has capability gates, and volume changes reapply all three buses. Saved preferences do not prove hardware success. Word `0x114C0` participates in camera-mode behavior but remains unnamed.

Saved destination `0x906E8`, next-level `0x8740` and pending runtime load requests are separate. None alone proves the current planet or successful loading.

## Non-save findings

### Developer helpers and Lua debug

These findings apply to the supplied BCUS98127 ELF: disc `VERSION=02.00`, `APP_VER=01.00`. RPCS3's displayed `01.00` does not identify a different binary; use the ELF hash in the map.

- **Lua console:** embedded Lua 5.0.2 retains `debug.debug`, registered at `0x8415C0`, opened by `0x810650`, with its text-console loop at `0x8106C8`. Secondary caller `0x72EB24` passes library mask `0x1F`, excluding debug flag `0x20`. The separate game-state factory `0x666E00` also omits the debug opener; changing the mask alone does not cover both paths.
- **Live test:** isolated, patched ELF tests on 2026-10-12 restored the console with bounded input. Two probes during playable gameplay confirmed `debug.debug`, `hero_give_all_ammo` and `ally_debug` were registered. Both returned Lua status 0 with stack height preserved at 3; the user confirmed normal movement after the first. The gameplay boundary was `0x6696C8`, with caller return `0x293DDC`. These were availability checks, not item grants or a recovered menu.
- **Input limitation:** the raw console reads RPCS3 channel 0, while GUI “All channels” queues channels 3–15. Empty input caused repeated prompts. Redirecting input to a one-command reader followed by `cont` and EOF avoided this. An always-on console was not implemented.
- **Native helpers:** `hero_give_all_ammo` at `0x2BAFE8` calls `0x28AB00`, which refills qualifying owned records through `0x465D88` when definition flags satisfy `flags & 0x13 == 0`. It requires a valid in-game moby handle and is not equivalent to the editor's ammo allowlist. `ally_debug` at `0x2A82C0` calls `0x28F378` to print component diagnostics; no ally-AI cheat was confirmed.
- **Debug assets:** `packed/game/debug.psarc` is a 780-byte index containing `packed/game/debug.toc` (1,856 bytes), which references the loose global and level `debug.dat` files. The inspected global file (310,389 bytes) contains IGHW class/enum/resource names, including `GUI_Menu_CLASS`, `DebugWad_CLASS` and `LevelDebugWad_CLASS`. Metropolis' file (609,708 bytes) contains object, camera and lighting names. Neither inspected DAT contained embedded Lua bytecode or an identifiable developer-menu interface.

No original on-screen dev menu, god mode or noclip was confirmed. Original game files and normal saves were not changed. The experimental patch builders, memory clients, isolated emulator and generated exports have been removed; original ELF annotations, function guards and recorded test evidence remain in `developer_helpers` in [NativeMap.json](maps/NativeMap.json).

The editor's blueprint and bonus actions reproduce confirmed saved writes rather than executing runtime helpers. They remain available; see [Usage](../../../../../docs/Usage.md).

| Area | Useful anchors | What is established |
| --- | --- | --- |
| Lua | `0x6687E0`, version string `0x1002AC50` | Embedded Lua 5.0.2 marker and getter |
| Physics | `0x2C4770 / 0x2C4930` | Named Lua physics_on/off wrappers and their native targets |
| Rendering/SPU | `0x10027C18`, `0x10028F08` | Shader-work and geometry cull/clip diagnostics, not recovered full implementations |
| Collision SPU | `0x10027728 / 0x10027818` | igCollBroadSpu.elf / igcollspu.elf build-path markers |
| Audio | `0x1002CB88`, references `0x6DBDC4 / 0x6DBDF0` | SCREAM allocator/error-path leads; version unknown |
| Memory | `0x6AB800`, source marker `0x10029DA0` | Anark allocator-related client and linked-node setup |
| Platform | Nine import records, 118 functions | 99 names resolved; 19 retained as numeric NIDs |

Resolved libraries include file I/O, controllers, graphics, audio, system utilities and SPURS. Their exact stubs/NIDs are in `library_imports`. An import stub is not the SDK implementation; a diagnostic/build string is not proof of an original function name or complete subsystem.

## Evidence index

Search these top-level keys in [NativeMap.json](maps/NativeMap.json), or use the corresponding Research topic in the app.

| Topic | Map sections |
| --- | --- |
| Save/load/restart | `serialization`, `snapshot_lifecycle`, `restart_execution`, `save_tail`, `load_selection` |
| Weapons, XP and ammo | `weapon_configuration`, `weapon_progression`, `weapon_level_editing`, `gadget_ammo_editing`, `groovitron_linked_state`, `inventory_queries`, `inventory_reset`, `ammo_capacity`, `ammo_crate`, `weapon_ammo_debit`, `gelanator_transition` |
| Purchases | `weapon_purchase`, `upgrade_purchase`, `upgrade_edit_candidates`, `ammo_upgrade_editing`, `ordinary_upgrade_editing`, `special_modifier_effects`, `armor_consumer`, `currency_mutation` |
| Equipment and objects | `objects`, `object_grant_producers`, `inventory_aux`, `equipment_lifecycle`, `equipment_mutation`, `hero_aux_fields`, `quick_select_warning`, `quick_select_eligibility` |
| XP, health and awards | `progression`, `hero_xp_flow`, `hero_config_assets`, `health_persistence`, `skill_award`, `skill_producers`, `bolt_multiplier_flow`, `reward_multiplier_editing` |
| Collectibles and bonuses | `collectibles`, `collectible_producers`, `blueprint_producers`, `bonuses`, `bonus_effects`, `bonus_remaining`, `bonus_selection`, `bonus_selection_assets` |
| Worlds and missions | `world_state`, `gameplay_segments`, `world_consumers`, `reward_channels`, `mission_lists`, `mission_mutation`, `segment_bindings`, `segment_configuration_assets` |
| Object identity/lifecycle | `world_object_flags`, `object_flag_mutation`, `object_definitions_assets`, `object_classes`, `pool_lifecycle` |
| Events and arena | `global_flags`, `global_flag_mutation`, `saved_event_counters`, `reset_categories`, `reset_context`, `arena_challenges`, `arena_table`, `arena_menu`, `arena_dispatch` |
| Dance and space stats | `dance_progress`, `dance_targets`, `space_stat_boundary` |
| Grids | `state_storage`, `persistent_grid`, `grid_routing`, `grid_geometry`, `grid_lifecycle`, `grid_aux_fields` |
| Settings and Decryptor | `settings`, `settings_menu`, `settings_apply`, `first_person_option`, `adaptation_context`, `tail_aux_fields` |
| Unknown-byte ownership | `world_aux_fields`, `segment_opaque`, `final_tail_fields` |
| Address/types/imports | `annotations`, `structures`, `save_regions`, `library_imports` |
| Developer controls | `developer_helpers`, plus the native save grants in `bonuses` |

## Open questions

The main gaps are field meanings and runtime relationships, not just addresses:

- Unknown bytes/words, including save tail `0x906E4`, settings name `0x114C0`, and copied grid tails.
- Stable world-object identities, target counts and all script-defined producer/configuration links.
- Live arena-table installation, indirect callbacks and removal-leaf reachability.
- Timer units, unnamed reset/event categories and every lifecycle dependency.
- In-game tests of new edits, persisted health/checkpoint behavior and other regions/builds.

Earlier map revisions passed Ghidra import/preservation checks; the latest annotations have byte checks but have not been re-imported live. IDA has mocked safety tests, not a live import test. Neither establishes complete gameplay coverage. See the [tools guide](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/README.md) for reproducible checks.
