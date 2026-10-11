# Tools of Destruction executable map

Research notes for the supplied USA **BCUS98127 v02.00** `EBOOT.ELF`. This map covers startup, PS3 imports, scripting, physics bindings, rendering/SPU diagnostics, audio/middleware anchors and save I/O. It is a starting point, not a complete reconstruction of the game.

Latest completed pass confirms hero XP publication, strict single carry, original-input threshold checks, one-way runtime progression and distinct script/reload float32 conversions. It adds twenty research tests, one app check and four instruction comments, with100 native guard ranges; no new editable fields. All613 native/asset/organization checks and184 app regression checks pass, including actual-save loading, resizing/DPI behavior and encrypted edit/reopen using disposable copies. Live read-only Ghidra checks pass1380 mapped annotations,45 layouts, repeat-import idempotence and analyst-name/comment preservation;1381 total JSON annotations include one unmapped TOC reference base. Release build has zero warnings/errors. IDA importer validation remains mocked safety testing, not live IDA execution. Original ELF, encrypted save and detached plaintext SHA-256 values remain unchanged. Numerical XP previews assume nearest-even float32 and do not reconstruct live FPSCR, runtime thresholds, callbacks or nonfinite exceptions. These checks validate static evidence/software behavior, not in-game acceptance or full semantic coverage.

## Hero XP publication, fractional carry and reload precision

The saved `u32 BE` at `418` is whole-number hero XP. Native `23E090` receives incoming XP in `f1`, truncates it toward zero with `fctidz` and publishes the low32 through the saved-state pointer at runtime hero+`1A68`. The leaf does **not** unconditionally narrow its input to float32 at entry. Its residual is `fsubs(incoming, frsp(fcfid(zero-extended truncated low32)))`; only a positive residual is added with `fadds` to runtime remainder+`1B68`. The integer back-conversion's `frsp` matters at large values; a decompiler expression that omits that rounding is insufficient evidence.

At `23E100`, remainder **strictly greater than1** triggers one `fsubs` subtraction and one wrapping saved-XP increment. Exactly1 stays pending. There is no carry loop: a synthetic remainder3.5 with integer incoming100 publishes101 and leaves2.5, not103/0.5. A pre-existing remainder>1 can carry even when incoming XP is an integer. These are qualified leaf semantics, not proof of how often gameplay generates those states.

Threshold comparisons at `23E150/23E184` use **original incoming `f1`**, not the saved value after carry. For example, synthetic incoming100.75 plus remainder0.5 publishes101, but a supplied next threshold101 still fails in that invocation. Runtime level+`1B61` only advances from its existing byte, stops at99, and is not reduced when incoming XP is lower. Old levels99..255 skip progression after XP publication. Each unsigned table threshold is converted through `frsp` and must be positive and<=incoming; this is not a strict-increasing-threshold check. The loop can advance across multiple positive entries.

Reload binding `23E650` differs: it sets the canonical saved pointer, clears runtime remainder/level, loads saved418, converts through `fcfid/frsp`, then invokes the same leaf. Consequently rebinding from a save is not equivalent to changing XP in an already initialized hero. Admitted named `hero_set_xp` native `28A9B0` also truncates its numeric input, selects low32 and converts to float32 **before** thunk `252C78 → 23E090`. Ordinary positive script fractions are discarded before the leaf; the script setter does not itself reset the runtime remainder. Handle/type validation is a separate admission path, not emulated by these arithmetic previews.

All nonnegative integers through2^24 are float32-exact; some larger integers remain exact, while others do not. Under the previews' **nearest-even** assumption, saved16,777,217 restores through16,777,216 and16,777,219 through16,777,220. At the extreme, `FFFFFFFF` converts to2^32; the leaf's low32 becomes0 and its positive residual/single carry yields saved1. This is a bounded synthetic conversion result, **not an observed in-game reload or inferred safe edit bound**. The live FPSCR rounding mode, conversion exceptions and nonfinite behavior are not reconstructed.

The actual supplied plaintext holds `00235388` = **2,315,144**, exactly representable as float32; the bounded reload preview republishes that value without carry. The snapshot does not disclose runtime remainder, current level, health or the runtime BSS threshold table at `101B9EE8`. Changed-level paths invoke `1E06C8` before rereading level at `23E230` and loading table+`190+4*level` into runtime capacity/current-health `1788/1784`. Callback changes are outside the preview: it reports only level **before callbacks**, never numerical health.

[Inspect-TodHeroXpFlow.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodHeroXpFlow.py) reproduces100 guard ranges, including complete progression/bind/setter functions, TOC provenance, zero/one literals and linked/tail branch checks. Twenty research tests cover carry boundaries, original-input threshold selection, one-way progression, zero/non-monotonic thresholds, precision/wrap edges, malformed/nonfinite rejection, byte tampering, snapshot preservation and embedded-map reproduction. Four new instruction comments preserve existing function labels. The app includes a read-only research topic and explanatory XP details; no new editable fields or private payload are bundled.

## Weapon purchase routing and saved level-five gate

Named `purchase_weapon` (`337D8 → 26638`) now has a fully qualified two-path dispatch. Its first low-byte `2D20C8` result selects `2D21A8` when nonzero, or normal acquisition `2D2D38` when zero. A false first gate is **not automatic rejection**. The selected level-five transaction performs a hero lookup and then samples the gate again; a failed second sample returns0 with **no normal-purchase fallback**. These are separate observations, not atomic admission.

The `2D20C8` gate reads global saved state through `89F1B8 → 101EFB20`. It requires nonzero record ownership, `465CC0` stored level>3, `465CE0` stored level not>4, definition flags&3 clear, saved replay word `906EC` nonzero, and unsigned definition `num_levels > 5`. The two level tests together mean **exactly stored level4**. Nonzero replay accepts any raw32 word; it is not a newly bounded mode boolean. By contrast, bridge `465E78` alone requires `num_levels > 4`: a supplied definition value5 could satisfy that leaf condition while failing this purchase gate. Neither predicate makes malformed definitions or IDs safe.

`2D21A8` obtains `Vendor.MegaPrice` through `2D1FA8` at definition data+6B0, then compares saved bolts with the captured cost using signed32 `cmpw`. The bridge stores level5, stores XP from threshold5 at data+244, and adds the newly resolved ammo maximum through `465E18`. Only afterward does it negate the captured price and invoke bolt update `24FCB8`. Qualified hero-subsystem virtual+1C and runtime request4 follow; the request result is ignored before returning1. No local rollback or atomicity is proven, and the bridge has no local ownership/unlock/modifier-mask/acquisition-counter stores. Later callbacks remain outside that local preservation claim.

Normal acquisition chooses `AmmoPrice` (+6AC) for definition flag2, otherwise `BasePrice` (+6A8). It requires a hero and signed32 funds; item19 has an extra low-byte `24F7B8(hero,11)==0` gate whose gameplay name remains unresolved. This leaf does not invoke the availability/unlock predicate or reject duplicate ownership. An admitted repeated call can charge again: acquisition can refill before checking ownership, while an already-owned record skips its local ownership/XP initialization and acquisition-counter increment. Hero integration, checkpoint merge and later callbacks still matter; this is not gameplay exploit validation or a universal refill guarantee.

Named `is_weapon_available` uses `265C8` with different ordering: normal availability `2D24C0` first, and the level-five gate only when normal availability is false. This union is neither a wallet check nor the purchase dispatcher. The Lua purchase wrapper converts admitted argument1 through `fctiwz`, pushes the returned boolean, and returns1 as the **Lua result count**, not independent transaction success.

[Inspect-TodWeaponPurchase.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWeaponPurchase.py) reproduces115 exact-build guard ranges. Its fourteen tests cover all256 stored-level/ownership values, raw replay words, separate definition bounds, independent gate samples, signed cost edges, tamper rejection, opaque float-bit preservation and embedded-map reproduction. The supplied save has replay3, acquisition counter46, stored level9 for IDs1..15, and no record satisfying the saved necessary level-five conditions. These are snapshot observations, not reconstructed runtime prices, current menu availability or acquisition history. The app adds a read-only topic and inventory detail explanations; no editable fields or safe ranges are added.

## Blueprint selector grants and qualified level associations

The separate native producer `303220` calls `2D1490`, then ORs `1 << returned_selector` into the saved blueprint mask at `86F4`. The getter reads saved word `906E8`; it is a saved level/destination selector, not proof of the currently loaded runtime world. The paired initializer `303260` tests that same bit before choosing a native restore/helper path. Function-descriptor links establish the callback entries, but the actual collection trigger and physical pickup locations remain unresolved. Existing grant-all mask `0007DEE4` identifies thirteen bits; level enum correlations and compiled checks must not be presented as a complete pickup-placement map.

The shipped Stratus City traversal script supplies `LEVEL_STRATUS_CITY` to `hero_has_blueprint`. This is a named predicate association, not evidence that every grant is executed by that script. A bounded scan for direct named global calls cannot exclude aliases, indirect calls or native callbacks. Actual-save bits are observations, not collection history. The new `blueprint_producers` report preserves these distinctions and exact-build guards; the UI remains read-only.

[Inspect-TodBlueprintProducers.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodBlueprintProducers.py) reproduces193 native ranges and optionally surveys524 compiled scripts using `--archive`. There are39 direct blueprint API global operands across six fingerprinted assets, but no direct named individual/all-grant operands in that bounded survey. The supplied plaintext has mask `0007DEE4` (all thirteen known bits) and saved selector0; a present historical bit is not evidence that its selector is active now.

## Upgrade purchase publication, ammo refill and payment order

Native transaction `2D2878` obtains the hero, looks up a node cost, compares the saved raritanium wallet using **signed32** `cmpw`, and tests the record's script-ownership byte `+10`. It does not locally test adjacency, the starting node, or whether the node bit was already set. Those vendor/menu rules and argument boundaries remain separate from this native leaf.

Helper `465D00` measures old max-ammo, publishes the ORed modifier mask at record `+0C`, recomputes max-ammo, and writes ammo `+08` only when `fcmpu` does not report equality. Unordered comparisons also reach that write; this is not an arbitrary NaN-payload preservation claim. Only afterward does the transaction negate the cost, invoke raritanium update, notify and return success. A repeated admitted native call can charge again without changing the mask; this is not a recommended editor action. Publication is not established as atomic, rollback-safe, or gameplay-validated.

Named `purchase_mod` passes through numeric conversion and boolean-result wrappers. A Lua wrapper's returned result count is not the transaction's purchase-success value. The new `upgrade_purchase` report distinguishes the cost guard, script ownership, conditional ammo side effect and final notification. Viewing does not spend currency, refill ammo or simulate runtime calls.

[Inspect-TodUpgradePurchase.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodUpgradePurchase.py) reproduces117 native ranges. Optional `--vendor-asset` validates eleven instruction guards and five method fingerprints. The vendor's `onSelect` separately excludes node0 and tests availability and purchase result. Special-node `canBePurchased` returns true directly; its all-positive-neighbor checks belong to other movement/icon layers, not a universal native transaction prerequisite. Runtime request4 can return0 while the transaction ignores that return and still returns1; this does not establish completed save I/O or current menu effects.

## Skill definition groups and additional runtime award producers

Definition `+0C`, formerly unnamed, is returned by `35EB18` and consumed by native menu helpers as an equality filter/group selector over the sixty skill IDs. Matching IDs are traversed in ascending global-ID order; nth matching selection is one-based. Group `19` is a grouping value numerically equal to `LEVEL_COUNT`, not a twentieth playable level or an award prerequisite. The saved earned bitset and weighted score remain independent preserved fields.

Producer `363EE8` requests eight more named skill IDs: `35`/`36` in its selector4 branch, `38`/`39`/`40` in selector8, and `41`/`42`/`43` in the final else branch. That else branch is **not explicitly restricted to selector13**. Predicates use runtime words, bytes and rounded ratio comparisons; their units and histories are not reconstructed from saved bits. `2EB9B8` supplies an additional qualified Iris Wrench (`24`) producer through runtime pool occupancy/configuration checks. Absence of another qualifying object is not proof of a complete enemy-kill history. The `skill_producers` report records exact gates, saved/runtime owners and immutable previews; none of these observations enables new edits.

[Inspect-TodSkillProducers.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSkillProducers.py) reproduces155 ranges, including saved-selector getter and callback reload sites. Selector comparisons refer to `2D1490`'s saved906E8, not an independently observed loaded world. Native ratio gates convert each unsigned word to float32 before single-precision division; nearest-even previews can differ from exact rational shortcuts, and current FPSCR is not reconstructed. Callback effects precede later predicate rereads, so report rows are not simultaneous eligibility claims. The supplied save has all sixty known skill bits set and score750, but selector0; neither runtime producer conditions nor acquisition chronology can be recovered from that snapshot.

## Entry-latched option exits and callback-qualified camera cleanup

The saved unnamed word `114C0` still has no recovered original option label or confirmed hold/toggle behavior. This pass links entry/update methods to exit methods `20F1F8` and `2112D8` through method tables `84AF18/84AF48 +0x20`. Their exit logic reads entry-derived runtime bytes `+0x24/+0x3F`, not the saved word again: nonzero latch selects numeric mode `0x0F`, zero selects `0x10`. Runtime actor states `0x5C9/0x63`, a nested subsystem and callback results can bypass this branch. Similar-looking actor `+0x14C0` accesses are not saved-root `+0x114C0` readers.

The qualified exit first checks mode existence with first-match lookup `683F0`, then calls `10390 → 63A748` with selector argument0. Cleanup clears matching pending mode `+20C0` to `FFFFFFFF`, without clearing pending selector `+20C4`, and scans all16 runtime records at `+C0`, stride `+200`. Selector0 is a wildcard, not a request to touch only selector0. Every encountered match stores mode1 before its virtual `+14` callback, then snapshots member `+68`, calls the requested-mode callback table and restores that snapshot. The snapshot is **after the first callback**, so its modifications are not rolled back. Callback effects can change later matches or final mode; cleanup is neither atomic nor proof the camera is inactive.

[Inspect-TodOptionProducers.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodOptionProducers.py) provides exact native guard reproduction and a callback-free, immutable16-record selection preview. It does not simulate exits or predict final runtime state. No new setter/name was confirmed for `114C0`, and opaque settings bytes `114D6/114D7` remain unnamed, not proven padding or defaultzero. The app adds a read-only Research topic and selected-row explanation without enabling edits.

## Reset-category producer contexts and separate dispatch bounds

The reset-category selector `132D0 → 2CDC60` writes runtime window `+4C = 0.25` then category `+48`, outside GAME.SAV. It contains no saved-counter increment or reset-request admission. Separate admitted requests reach writer `2CE518`; selecting a context alone does not prove a reset, death or failure. Repeated sequential selections refresh the window and replace the prior category, with no established interleaving/atomicity or time units.

Newly confirmed caller boundaries distinguish category selection from later actor-state dispatch:

- Category2: signed word `+430 <= 28` selects2, but the later reread dispatches only unsigned states0..32. States29..32 can dispatch without selection; negative raw32 states can select2 yet reject dispatch.
- Category4: initial word `+4A4 != 2` selects4 before helper calls. Later dispatch rereads the word and accepts0..102. The two samples need not agree.
- Category6: byte `+764 == 0` and nonzero `+762` select6 before the later20-case dispatch bound. Bytes20..255 can select6 while bypassing the table.
- Categories3/7: flags `+8B0` choose the category before `BF178`; that helper's later byte `+5BD` gate does not gate the earlier selection.
- Category5: selection precedes a resolved object's virtual callback; acceptance and invocation frequency remain unknown.

The common preselector `11370 → 68FF68` ORs runtime entry flags `+68` with20 for category2/4/6 contexts. It is not a saved flag or direct reset request. State-request helpers can publish actor state23 or1/14 before selection, but complete transition machines and old-state callbacks are not simulated. The checked `fcmpu` followed by `409D0008` tests CR7.GT==0: less/equal/unordered branch past `li1`, retaining predicate0; only greater falls through to predicate1. The branch model is checked using raw condition bits, not decompiler comparison shorthand or a floating-point emulator. [Primary branch-field semantics](https://git.openpowerfoundation.org/cores/a2i/raw/branch/master/rel/doc/A2_BGQ.pdf), section2.9.3, support that decoding. Three relative jump tables have33/103/20 entries, not recovered state names. [Inspect-TodResetProducers.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodResetProducers.py) reproduces their byte evidence and five virtual contexts; immutable sampled previews keep selection/dispatch samples separate. Actor names, player-facing category causes and current runtime context remain unresolved. Actual eight saved counters are zero, not evidence no resets occurred.

## Opaque segment and world fields: bounded ownership audit

No new semantic type/name was established for segment `+28`, its `+2D..2F` tail or world `+404..407`. Three reviewed apparent matches do not establish saved-record ownership: `92198` copies source `+0` into an argument-converted destination `+88C`; `93818` copies source `+14` into destination `+4B0`; selected `1827D8` reads original input-owner `+884/+888/+88C` into a stack message. Its separate `+14 → +54` traversal is not the owner of that float load. A prior constructor's similar immediates use initialized root `101B9EE8`, not saved root `101EFB20`.

[Inspect-TodSegmentOpaque.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSegmentOpaque.py) guards30 selected native ranges and preserves opaque bytes in bounded200-segment/20-world observations. Arbitrary caller aliasing, computed/indirect readers and other producers remain outside this audit; eliminated candidates are not a global no-use proof. Actual zeros cannot establish padding or gameplay meaning. Prior initializer/full-copy facts remain prior evidence, not newly mapped fields or a coverage-percentage increase. Seven tests cover ownership report reproduction, extreme raw patterns, boundaries and unchanged inputs.

## Runtime pool setup, deferred release and reusable physical slots

Normal storage setup `523B00` initializes entries at stride `0x180`, a ushort release queue and a bitmap in 128-slot blocks. It marks unused padding slots occupied. This refines the raw allocator warning below: a correctly initialized, unchanged bitmap cannot return a padding slot. It does not establish safe behavior for malformed capacity arithmetic, pointers or callbacks.

`68FD60` computes `(definition_count + caller_extra + 7) & 0xFFFFFFF8` with 32-bit arithmetic, initializes the selected root's pool through the TOC-adjusting `59E020` thunk, then immediately dispatches the same root/context through virtual `+0x3C`. The verified `84DF28` table selects filtered loader `2F8690`. Fresh initialization is now code-backed at this boundary; ordinal=physical slot still requires valid arithmetic, one successful allocation/reservation per definition and no nested allocation/free. The alternate base loader `68F190` creates every definition without that filter.

Deferred release `51FB08` validates the full generation-bearing handle, calls the enqueue callback before clearing class `+0x50`, then queues the physical low16 slot. It does not immediately clear occupancy or decrement live count. Drain `521840` calls a separate callback before occupancy clear, writes `0xFFFE0000 | slot` as the unused handle, decrements live count and trims the high-water index. It reloads pending count while iterating: callback-appended entries may extend the drain. No fixed snapshot, deduplication, atomicity or recursion safety is inferred. Physical slots are reusable, so saved bits cannot be assigned permanent instance identities.

Constructor `51FD70` zeroes the 32-byte runtime header and sets high-water `-1` and generation `1`. Detach `51F698` clears storage pointers/capacity/live count and high-water, but does not locally reset generation or pending count, free backing storage or clear saved world bands. `TOD_RuntimeObjectPoolHeader_verified` describes these eight raw32 fields; it is not a GAME.SAV header and is not automatically applied to BSS/dynamic memory. [Inspect-TodPoolLifecycle.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodPoolLifecycle.py) reproduces71 native guard ranges;12 tests cover padding, deferred reuse, header distinctions, bounds, actual stored bands and unchanged inputs.

## Global event latches and confirmed script consumers

The reference compiled-script survey scans524 entries, finds181 API-string candidates and strict adjacent literal flag calls in180 assets:880 check/set/clear sites,214 native-bound operand names. This is a bounded static operand survey, not a full control-flow/call graph or proof that every site executes. Runtime global reassignment, aliases, variables and nonadjacent calls remain unresolved. `LVL_IFF_RETURN_CHALLENGE_7_DONE` has no matching native exported enum: its spelling is retained without inventing an ID, alias or save offset.

Selected, whole-asset-fingerprinted reached blocks show reset/consume paths for IDs3 (fired weapon),7 (quick select),12 (Aphelion),13 (hit shield),15 (electric-immune hit),16 (Visicopter) and17 (map). A clear bit does not mean the action never happened; set does not prove help ran or is currently active. These selected bits can act as consumable event latches, not monotonic achievements. This behavior is not generalized to all292 named flags or the28 unnamed physical tail bits.

The Stratus help consumer increments Lua global `hero_shield_hits` before clearing13; that counter has no confirmed save offset. Metropolis's reached reset-volume body clears3 then7. Apogee entry clears17; Meridian entry clears12. Meridian's later return-to-Aphelion completion requires12,219 and a local first-run guard, then clears12 before separately completing the mission. Those actions are not atomic. Global help clears15 after help and clears16 in each input-mode help branch; no engine timing/current help state is reconstructed.

Both native clear leaves use ordinary load/and-complement/store, preserving unrelated bits without establishing atomicity or named bounds. [Inspect-TodGlobalFlagMutation.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGlobalFlagMutation.py) reproduces510 native guards (including existing enum registrations), six selected asset guards across five assets and15 tests. The actual supplied save has the selected event bits and dependency219 clear; this is a snapshot, not reconstructed action history. The app explains these boundaries per row and exposes read-only source evidence. No scripts, native flag mutations or mission completion are executed.

## Class-table source records and actor factory lookup

The inline class-pointer table at runtime `1064FD3C` is the pool root `1064FC80 + 0xBC`. TOC aliases `8AA34C` and `8A6CE8` address that same table; `8AA350`/`8A6CFC` address its containing subobject at pool `+0x80`, not an independent class resource root. Resource loader `4A9FA0` recognizes section `D100`, stores its low28 element count at subobject `+0x10`, then populates the table with consecutive `0xC0`-byte records. Numeric class ID therefore indexes that loaded resource's source-record ordinal. This is not a physical saved slot or a recovered object name. Reset `5212A0` clears320 pointer cells; that span is not a native checked class-ID bound.

`521308` writes the runtime class ushort at object `+0x50`, the table's class pointer at `+0x54`, and a distinct generation-bearing handle at `+0x64`. Actor callback `68F5F0` substitutes class record `+0x64` only when its explicit primary actor identifier is `0xFFFFFFFF`, while independently supplying secondary identifier `0x66` to factory `5014F8`. The factory's lookup/failure paths and resource-kind25200 preparation do not establish a localized name, effective spawn success or saved object identity.

Class preparation `68F7F0` consumes pointed class records, not numeric IDs directly. Class `+0x78` points to a source header whose `+0x38` points to a packet: eight flag bytes, one unsigned length byte and that many opaque bytes at `+9`. It copies the flags to runtime class `+0x70`, widens length into `+0x68` and allocates/copies payload into `+0x6C`; flags are later ORed into runtime object `+0x118`. These pointers/flags are not GAME.SAV fields or saved world bitsets. No NUL termination, text encoding or object-name meaning is assumed for the opaque bytes.

[Inspect-TodObjectClasses.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodObjectClasses.py) independently validates bounded IGHW directories and relocated class `+0x78` → header `+0x38` packet links against the reference level assets, then cross-checks reference definition class IDs against each corresponding class table. It reproduces64 native guard ranges and13 tests. All19 worlds contain2,974 source class records (48–211 per world);18,214 object definitions refer to119 numeric classes0–118. Of the2,974 source packets,622 have nonempty opaque payloads. Compact public catalogs retain source offsets, raw flags, lookup IDs, lengths and fingerprints, not complete source records/headers/payloads. Native/asset provenance is exposed read-only; no actor/resource payload executes. This advances the class-source chain without relabeling saved bits or claiming current live world/class selection.

## Shipped object definitions and conditional pool-slot identity

The exact USA v02.00 assets contain **18,214 object definitions across the 19 named worlds**. Each reference world has one `default` root. Independently validated IGHW descriptors and relocation locations connect metadata class25000 (`+0` pointer / `+4` count) to128-byte roots in25100, then root `+40/+44` to72-byte records in7340. Native registration251458→651438, root selection2515B8→651540 and selected-root getter651428 establish the same pointer chain. The root selector compares its two inline name fields at0/9, returns the first matching root, or falls back to the first root; these are group selector names, **not individual object names**. Bare native member/address numbers below are hexadecimal; byte sizes stated in prose are decimal.

Creation68EFC8 reads class ushort3C through virtual+28, transform inputs18..2C, qualified float overrides8/C, raw actor arguments0/38, runtime-D0 input30, mask inputs10/14 and bytes3F/46. It sets runtime flag10000 used by suppression publication. Other words/bytes remain explicitly opaque. The verified72-byte external asset type is imported into IDA/Ghidra as `TOD_AssetObjectDefinition_verified`; it is not a GAME.SAV record or a runtime384-byte object entry. Transform angle units, axis order and several runtime stat names remain unresolved.

Class callback68F328 reaches523E58 through the TOC-changing59E700 thunk. Allocation and rejected-definition reservation51FC88 scan the **same bitmap**, low bits first in four-word128-bit blocks. The allocator constructs `base+slot*180`, then521308 writes generation-bearing handle at64, class ushort at50 and a class-table pointer at54. Actor creation68F5F0 copies the handle into a separate8-byte table and links pool+40 / actor+14 on a nonzero result. Class ID, asset ordinal, physical pool slot and generated handle are distinct identities; no localized class names or concrete instance UIDs are recovered from the save.

Filtered loader2F8690 advances every definition ordinal. Rejected entries reserve bitmap slots instead of creating/compacting an object, then increment root14 even without checking the reservation result. Creation marks a free bit **before** validating signed index/capacity; reservation lacks that same index-capacity predicate. These native trust boundaries must not become editor-safe allocation behavior.

An initially empty bitmap with sufficient capacity and exactly one uninterrupted allocation/reservation per definition, without nested allocation/free, would produce ordinal=physical slot. That is a conditional inference, not a recovered runtime invariant. Later3D2170 selects a definition through runtime ushort16 and the same creation path. Consequently neither class nor reference ordinal is automatically assigned to a saved bit. The actual save has all40 object bitsets clear and does not capture the live bitmap, class-table pointers, generation or spawn history. This cannot prove that every object is alive/present or make a named save-bit catalog.

[Inspect-TodObjectDefinitions.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodObjectDefinitions.py) reproduces69 native guard ranges and reads matching level archives in place. The embedded reference catalog includes per-world class counts, load-mode counts, segment-name associations, fingerprints and four raw examples per root; it does not bundle complete assets or private save contents. Fifteen tests cover exact guards, relocation/span bounds, overlap/duplicate rejection, unknown IDs/bytes, first-free scan order, padding reservation versus creation, full layout coverage, map reproduction and unchanged inputs. Research topics expose the definitions and reference catalogs; object-bit row details explain why they cannot relabel current bits. No new edit fields or native execution are enabled.

## Object callback publication and one-shot restore gates

Event leaf `2DD588` admits its virtual+48 callback only when runtime byte1D is zero. That callback runs **before** saved recorded-bit setter2F77A8 and before publishing1D=1. The setter obtains the current world after the callback returns; entry-time world identity cannot be assumed if the callback changes it. A runtime handle-record scan clears byteC in the first matching UID record only; no uniqueness invariant or match requirement for latch publication is established. Already-nonzero1D skips callback/bit/scan but still normalizes1D to1. Callback reentrancy/effects are not simulated, and this is not an atomic transaction.

Restore gate `2DD698` returns for pending1E zero. Nonzero pending is consumed to0 **before** checking the saved recorded bit; a nonzero result tail-calls2DD588(0), whose1D latch can still suppress the inner callback. A set save bit alone therefore neither schedules a restore nor forces callback execution. These latches belong to runtime objects, not GAME.SAV offsets.

Record request `27C358` clears resolved runtime record byteC before validating the object-pool handle. Rejected low16/count or full-handle matching does not undo that earlier runtime write. Its complete body does not establish resolver-null or actor-pointer-null safety. Related-object consumer `2FE0E8` calls24F4F8 on the valid handle path, then accepts post-helper actor state9 without querying the bit; other states consult2F7830. Result byte643 is runtime-only, not a saved completion flag. Neither record UID nor actor state is decoded from saved pool-slot bits.

Suppression writer `2F7930` uses object flag10000 to gate only the saved OR; runtime helper2501C8 runs on either branch, after the qualifying store. Its `ldarx` followed by ordinary `stdx` is not proof of atomic OR or concurrency safety. Two additional recorded-bit producers in3BF5A8/3C0160 have qualified runtime branches, but object kinds/query meanings remain unnamed; the latter's guarded entry/force path does not reconstruct omitted inline switch cases. The recorded-state clear leaf affects a distinct bank and is not assigned a gameplay reset cause.

[Inspect-TodObjectFlagMutation.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodObjectFlagMutation.py) reproduces83 native guard ranges, including nine full descriptor functions. Fourteen tests cover callback/latch ordering, first duplicate UID match, pending consumption, separate suppression/helper gates, early record clearing, state9 short-circuit, bounded shapes, all20 physical world slots, map reproduction and unchanged inputs. Actual all40 recorded/suppression bitsets are clear; this does not prove that every object is alive/present or recover callback history. The app adds `object_flag_mutation` and row details without new columns or edits.

## Equipment publication and independent restart filters

Pack leaf `27A30` stores43C, then selector438 from its original64-bit zero test, then notifies type4, even when the saved result is unchanged. It supplies no local ownership/enum-bound predicate. The named Lua wrapper's admitted `fctiwz/stfiwx/lwz` payload is zero-extended int32, so it cannot produce a nonzero64-bit native argument with zero low32. Nonfinite/out-of-range conversion and wrapper error behavior are not emulated. Boot leaf26F60 ignores its argument, stores440=0, then notifies type4 even if already0; pack/selector/history remain independent. Notifications do not prove successful runtime equip.

Selective restart `3CED40` first initializes the private bank through35E110/35DC80, then overwrites its first484 bytes with the live prefix. The later filters therefore operate on copied raw words, not initializer defaults. IDs24,26..31 are reinitialized in inventory and independently replaced byFFFFFFFF in each of32 quick-select slots and three history words42C/430/434. This is in-place filtering, without compaction, duplicate repair or hole filling; ID25 and unknown/sentinel words survive the predicate.

The copied pack word43C is cleared only when exactly3, independently exported as `PACK_WING`. Selector438 and boot440 retain their copied raw values: selector1/type3 becomes **selector1/type0**, not selector0/type0. Other pack words remain unchanged. This suffix does not call the pack/boot setters or apply their notification rules. The later full private-bank copy publishes the result before the level request; subsequent runtime callbacks/acceptance remain outside this boundary.

[Inspect-TodEquipmentMutation.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodEquipmentMutation.py) reproduces52 native guard ranges. Twelve tests cover native64 versus admitted Lua int32 payloads, always-notifying boot publication, exact in-place filters, retained selector/boot/unknown words, detached suffix previews, copy/initializer order, map reproduction and unchanged inputs. Actual quick-select has32FFFFFFFF words, history is15/25/0 and selector/pack/boot0/0/0. These observations do not prove a past restart or current runtime equipment. The app adds `equipment_mutation` and Pack details, preserving raw independent fields without repair or new editing.

## Currency mutation routes and runtime cache debit

Hero-side leaves `23D810/23D840`, reached through TOC-changing thunks `24FCB8/24F748`, update saved wallets41C/420 through hero+1A68. Their exact low32 rule is `sum=old+delta; difference=999999999-sum; result=cap if difference bit31 is set, otherwise sum`, all modulo2^32. Ordinary nonnegative signed32 sums select the upper cap999999999, but arbitrary high-bit/wrapping state is **not** a universal unsigned minimum or saturating addition. There is no lower clamp, local hero/type admission or callback in these leaves. These are native arithmetic boundaries, not editor-safe ranges.

Reward-side leaves `369AA8/36A458` instead update runtime root10330740+124/+128 **before** adding the same delta to saved wallets through hero+30. Both stores wrap low32, with no upper/lower cap or local sign/zero gate. The runtime root is outside the serialized bank and is not a saved collected total, high-water mark or wallet alias. Native reward consumers `3842B8/376428` use `fctidz` signed64 truncation but test/pass the low32 word; a nonzero finite converted multiple of2^32 can skip a wallet call. This does not prove that normal producers admit negative or extreme rewards. Nonfinite/out-of-range PPC conversions and current payout calculation are deliberately not emulated.

Currency consumers `304010/306338` require nonzero actor+40 and type416 predicate low byte. They update the wallet first, then debit separate runtime float caches101EF8E0+0C/101EF920+0C using the **full reread requested word**, not the actual capped-wallet difference. Bolts reread an unsigned definition word and round it to float32; raritanium rereads/sign-extends object+A0. The latter also calls253048(object+9C,0) before the actor gate. Requested amount, actual wallet delta and runtime cache debit must not be equated. No named pickup class, current cache value or atomic transaction is reconstructed.

[Inspect-TodCurrencyMutation.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodCurrencyMutation.py) reproduces72 native guard ranges. Twelve tests cover equality, deduction/underflow, sign-wrap boundaries, independent runtime counters, finite conversion and low32 gates, raw snapshots, preflight, map reproduction and unchanged inputs. Actual saved bolts265669877 (`0FD5CCF5`) and raritanium10953187 (`00A721E3`) do not identify the route/history that produced them. The app adds `currency_mutation` and read-only currency details, without calculating payouts, applying caps or enabling new edits.

## Skill award producers and publication ordering

Previously mapped skill setter `35D5D0` now has its precise order confirmed: return if already set; capture old score; publish bit; read definition points; publish low32 score sum; obtain notification recipient/tag and notify; only then scan bits0..58 for automatic59. Duplicate calls skip that scan too, so they do not repair mismatched score or missing59. Normal-ID operations retain unknown bits60..63. Notifications can have separate runtime/reentrant effects; callback-free fixtures are not atomicity proofs.

Golden collectible setter `35DEB0` performs its all19-world count scan even on duplicate local IDs or unsigned local IDs>31 that skip the mask write. It counts all set bits, including unexpected bits, and compares unsigned popcount>=shippedtotal; zero-total worlds pass and slot19 is excluded. An optional skill46 call request is not a newly earned award, because deduplication is separate. This leaf's invalid-local-ID behavior does not establish script-wrapper admission or physical pickup identity.

Native ammo purchase `2D2B90` supplies **SKILLPOINT_CHEAPSKATE47** for item1 (Combuster) only after ammo addition and bolt deduction, using ordered **original request<=1.0**, not the clipped quantity. For ordinary finite requests, positive input selects the smaller of the request and missing quantity; zero/negative input selects missing quantity but still meets that award comparison after admission. A request>1 clipped to1 or0 does not meet it. Admission separately requires hero, signed32 converted cost<=signed32 savedbolts, nonzero ownership and definition lowflags&3 zero. Price getter `2D2000` reads unsigned data+6AC; float32 multiplication/fctiwz overflow and runtime definitions are not emulated. No gameplay exploit, named-wrapper acceptance or current purchase verdict is claimed.

[Inspect-TodSkillAward.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSkillAward.py) reproduces58 native guard ranges; twelve tests cover wrap, duplicate mismatch retention, automatic-award order, duplicate/invalid-local-ID scans, original-versus-selected request, signed admission, raw snapshots and map reproduction. Actual score750 and all60 bits are set; all19 masks meet shipped count comparisons. These do not recover the original purchase requests or a captured award event. The app adds `skill_award` and selected-row explanations without new columns or editing.

## Armor purchase and deferred equip versus skin leaf charging

Armor purchase `2D26D0` admits a resolved hero when signed savedbolts>=signed definitionprice and signed equippedID<requestedID. Its leaf does not test ownership/availability or bound the requested index. It stores ownership1 and calls currency deduction **before** actor handle/type routing. Invalid/fallback routing equips/notifies directly; qualified actor routing calls `43FCE8`, which can instead queue runtime hero+2170 {requestedID, actorhandle, opaque companion word, latch}. Purchase return1 does not prove immediate equip.

The queue branch writes actor float+1AC=14, then the latch before payload. This is not atomic publication and these are not GAME.SAV offsets. Consumer `1F7DC0` state2 compares runtime singleton+B4 with object deadline+1C via `fcmpu/ble`: ordered<= exits, > or unordered NaN reaches equip. It calls `1E2150`, notifies, then publishes state3 after further calls. Current queue/timing and animation acceptance cannot be inferred from the save. Definition root `101B9EE8` record+11C20 stride28(hex) supplies price+0C and float+08→hero1798; that float's downstream damage meaning is still unproven.

Skin purchase `27AA0` checks signed price<=signed special-bolt balance, then stores selected480, ownership45C+4*ID, and low32 spent424+price before notification. The full native leaf calls no ownership/availability/selection predicate. An admitted repeated leaf call can therefore charge again; normal UI/script callers may impose additional gates. This is not demonstrated gameplay behavior or an editable-save invariant.

[Inspect-TodArmorConsumer.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodArmorConsumer.py) reproduces68 native guard ranges; eleven tests cover signed admission, low-byte queue predicates, exact call inventory, unordered deadline comparisons, independent raw saved words, preflight and immutable inputs. Actual armor ownership/unlocks are all1, equipped4; skin7 ownership0, selected0, spent32. No pending queue, price, runtime attribute or purchase history is inferred. The app exposes `armor_consumer` and Armor/Skins details with unchanged simple columns and no edits.

## Private restart-bank capture and nested initializer ownership

Arena setup `3CF228` publishes a separate save-sized `906F0` bank at runtime object+80. Its forward allocator rounds the used offset to16 before adding the arena base; its reverse allocator rounds the absolute candidate down16. The body supplies no visible zero-fill/capacity/null guard and does not establish equality with normal save-manager staging. Runtime allocation is not emulated or inferred from GAME.SAV.

Dispatcher `3CF378` uses five signed BE32 displacements relative to table `3CF3DC`: phases0..4 target `3CF47C/3CF5B4/3CF3F0/3CF570/3CF4EC`; unsigned phase>4 exits. The guarded inline case bodies extend beyond the old recovered decompiler body. In phase1, a nonzero entry latch is consumed and the qualified handle path copies live state into the private bank **before** continuation helper `251188`. Later polls with latch0 skip capture. That helper's low-byte result0 stays in phase1; nonzero publishes phase2/latch1. This is a conditional earlier snapshot, not continuous synchronization.

In the phase4 entry-latch-zero suffix, selector `263DB8` low32 exact0 calls `250ED8` then selective restart `3CED40`; exact1 calls `250ED8` then full private-bank restore `3CF1B8`. Other results stay in phase4. The selected action returns before phase5/latch1 publication. Reached level-request arguments differ (`0,0,1` versus `18,1,1`); no menu labels, successful gameplay transition or phase5 completion verdict are assigned.

**Correction to the earlier constructor-loop notes:** later initializer `35E110` passes save+5528 to `35D9A0`. The latter calls zero-fill `252938` twice with size9B0, clearing whole mission groups `[10148,10AF8)` and `[10AF8,114A8)`, including IDs, flags and counts. Its innerbase+10000−53E0/4A30 destination arithmetic independently proves these ranges. Constructor loop flag retention is only an intermediate result; both standard-manager/live initialization and selective restart reach the later clears. Neither final startup nor selective restart retains those mission flags.

The initializer also clears log count10144 and resets Decryptor words8758/875C/8760 to0/0/float1. It leaves only the preceding statistics-log bytes `[8764,10144)` (200 records of9C) untouched in this region. At selective restart's final copy boundary, those bytes therefore belong to the **previous private-bank contents**, potentially the earlier phase1 capture, not necessarily the current live bank. Retained bytes beyond cleared count are not active statistics or reconstructed history.

[Inspect-TodRestartExecution.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodRestartExecution.py) reproduces88 native guard ranges. Twelve tests cover relative switch targets, constructor gates, capture-on-entry versus later polls, selector exactness, action/publication order, bounded allocation arithmetic, nested mission clearing, retained log ownership, raw snapshots and map reproduction. Actual restart word3, log count0 and all40 mission counts0 are observations, not evidence of current runtime phase or private-bank identity. The app exposes `restart_execution` and corrected Mission/Counters detail text; no new editing or native execution.

## Save staging and deferred load application

Save launchers `6952D8`/`695350` synchronously call manager virtual slot+10 before creating their worker thread. Installed vtable `84FE18` resolves that slot through `86F760` to `35E710`, performing qualified grid synchronization and the full906F0 byte copy. Live state `101EFB20` and staging `1029FF18` are distinct; setup `35E2C8` binds managerD8/DC to staging/906F0. Later GAME transfer `695BF8` reads those staging members, not live memory. Later live mutations alone do not change captured bytes; other staging writers, overlapping requests, synchronization and durability remain unproven.

Load metadata callback `6C7A78` walks ordered38-byte records. The **first name-equal record** must have full64-bit size equal zero-extended managerDC; a wrong-size match immediately returnsFFFFFFFD rather than finding a later duplicate. Missing/empty lists fail too. Phase3 callback `6C7BC0` requests reading GAME into staging and advances phase4; it does not interpret fields or copy into live state. These name/size checks are not complete payload, PFD or edit-safety validation.

List worker `6C7870` and actual auto-load worker `6C7E00` publish phase5 only when selected-slot!=-1 and platform result0; their runtime manager events are respectively3/4. They do not directly apply ToD state. Poll `6C7640` requires handle!=zero-extendedFFFFFFFF, syscall30 low32 result80010005 and phase5 to dispatch virtual slot+14→`86F750`→`35E508`. Apply occurs before invalidating the handle/clearing phase. A qualifying poll in another phase only invalidates the handle. These raw gates are retained without invented SDK error names or scheduling guarantees.

The **separate Check-thread** worker `6C79C0`, not the actual auto-load worker, performs an existence probe and clears phase0. Stat callback `6C7770` writes runtime managerFC/100 used by `39B700`; these fields are outside GAME.SAV. Restore first copies staging to live906F0 bytes, then applies effects/music/voice settings `114C8/114CC/114C4` and calls `2D16A0(saved906E8,1,0)`. The restore body supplies no local per-field validation/clamp or all-or-nothing rollback; separate callees/platform guarantees remain distinct. Saved destination is still not successful in-game load acceptance.

[Inspect-TodSnapshotLifecycle.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSnapshotLifecycle.py) reproduces76 native guard ranges. Ten tests cover worker/poll gate combinations, exact64-bit file-size comparison, duplicate rejection, separate probe identity, immutable staging fixtures, raw float bits and map reproduction. Actual destination is0 and three audio float words are3F666666, not inferred worker status. The app exposes `snapshot_lifecycle` and Save regions explanations, without additional columns or edit controls.

## Weapon XP boundaries and additive ammo updates

The cap helper `465F08` reads the **pre-update stored level** through `465CE0`: level<=4 selects boundary4; level>4 selects boundary9. Definition flag bits0/1 can force cap0; otherwise the cap is the minimum of that boundary and definition `num_levels`, narrowed to a byte. `4660A8` obtains this cap before storing the incoming XP or recomputing the level. High XP alone therefore cannot cross stored4/5 through this setter; a decrease to<=4 changes the next invocation's boundary. This is a stored-byte predicate, not a named gameplay-mode test or a current effective-cap verdict.

Ordered XP>=the next threshold promotes inclusively; equal thresholds promote. Supplied XP has no local lower/upper clamp, and same/lower recomputed levels skip the increase-only ammo path. On an increase, the new ammo maximum is passed as an **add delta** to `465E18`, not an absolute refill. Ordinary finite nonnegative ammo reaches the maximum; negative old ammo can leave less after addition/clipping. Add/subtract leaves use single-precision arithmetic and comparison-select clipping, not an unrestricted nonfinite/negative-maximum normalization contract.

Progress helper `465FF0` reads the raw stored level's threshold **before** computing the cap, returns0 for equal low/high thresholds, otherwise `(XP-low)/(high-low)` without a local0..1 clamp. It does not repair inconsistent saved levels/XP. Separate `465E78` writes stored level5/threshold5 XP when definition levels>4; its known caller does not establish all transition events. Actual save IDs1..15 have stored level9 and Combuster ammo100; these observations do not prove current runtime definitions or progress fractions.

[Inspect-TodWeaponProgression.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWeaponProgression.py) reproduces84 native guard ranges. Ten tests cover inclusive thresholds, old-level dependencies, finite synthetic previews, raw nonfinite/extreme bytes, actual-save immutability and map reproduction. The app exposes `weapon_progression` and plain read-only weapon details. No new editing or native execution.

## Mission mutation and retained entry flags

The qualified `35C760` constructor loops clear counts and title/description words in both20 physical-list groups, but **do not write entry flags at those loop boundaries**. Their branch requires low32 arguments1/0000FFFF. **Correction from nested-call tracing:** following `35E110 → 35D9A0` performs two9B0-byte zero-fills clearing both entire mission groups, including IDs/counts/flags. Selective restart reaches the same clears. Constructor-loop flag retention is not the final initialization result, and missions are not preserved by this initializer. See [private restart-bank ownership](#private-restart-bank-capture-and-nested-initializer-ownership) for guarded base/size/call provenance.

Completion `2D0F78` copies source title/description only, then ORs completion bit2 into the **destination's preexisting flags**. Source optional/unknown flags are not transferred; retained destination bits survive. Active compaction copies all12 bytes of survivors in order and leaves the old last entry as inactive residual storage. Counts/stores occur sequentially, not as a proven atomic transaction. Add `2D1168` overwrites all12 destination bytes and keeps only low8 incoming flag bits.

Title search `2D0F18` walks the raw saved count before add's count<10 check. Completion lacks an independent completed-count capacity gate. At completed count10, its first title write aliases the count word at list+78; subsequent address calculations reread the overwritten word. This is **not** a safe fixed12-byte spill model. Detached previews reject malformed counts/full destination mutation and never emulate native corruption. Actual40 physical counts and400 flag words are all0, so no occupied mission example or observed stale-flag contamination is claimed.

[Inspect-TodMissionMutation.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodMissionMutation.py) reproduces42 native guard ranges; thirteen tests cover retained flags, stable compaction/residual bytes, duplicate title keys, bounded previews, actual-save observations and immutable inputs. The app exposes `mission_mutation` and World progress details without adding columns, repairing missions or enabling edits.

## Arena queue API boundary and runtime resource ownership

Registration89D8AC contains **`queue_arena_challenge_screen`**, descriptor86C530→wrapper2CA1D8→282AF8. The string `select_arena_challenge` at8991E0 is this native body's **diagnostic identifier**, not proof of a registered native table-taking API. The shipped Lua selector call and its actual table-installing wrapper remain unconnected; neither its input list nor ARENA_CHALLENGE_DATA identity is recovered by this pass.

The registered wrapper checks a required `moby_handle` argument and nonzero userdata resolution, then a required **string-compatible** second argument through252288→6A5C68 and extracts its pointer through24FAB8→6A9E78/66B078. A present ordinary third argument is rejected through252BE8→6A5FC8. This accepted domain is the native Lua predicate's, not an asserted strict Python string type or recoverable-error guarantee. The wrapper passes the extracted pointer inr4, but the complete guarded282AF8 body overwrites incomingr4 without consuming/preserving it. Its operation request remains thread token,5,0,0; this boundary does not carry a recovered challenge-list payload.

Loader62D2E8 retains incomingr6 from runtimeowner+108+2C, then passes it to632710. That leaf writes a runtime word at107225CC+0 through8A9578. Companion setter632720 independently writes+4 and clears+8; those writes are not performed by632710. Context setup6329D0→636EF0 writes separate runtimeowner107225D8+14/+18. These are runtime words, not save offsets, recovered Lua-state/table pointers or saved challenge IDs; their full semantic names remain qualified.

[Inspect-TodArenaBinding.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodArenaBinding.py) reproduces29 native guards, including thirteen function/block SHA-256 fingerprints; eight tests cover registration/diagnostic distinction, type/arity boundaries, payload consumption, resource-store separation, bundled reproduction and unchanged inputs. Actual23 arena counters remain zero. The app exposes `arena_binding` and selected-row caveats without reconstructing a live table, adding save fields or executing native UI/Lua.

## Reset request admission and latch service

The previously mapped category writer `2CE518` has a confirmed caller bridge `13680` from request wrapper `1E1ED0`. It admits only when the low byte of7EB48 is zero **and runtime101D5C30+68 is zero**; rejected paths return0 without recording. The admitted path calls13680→2CE518,244760 and11050, then stores latch1/returns1 only after those calls return. Recording precedes latch publication, so this is not a proven atomic transaction, prepublished lock or callback reentry guarantee.

Predicate `7EB48` ignores the passed7B358+170 subobject and fetches a separate runtime context through7B350. It blocks when context101B88E0+58 is nonzero or unsigned state1036BC0C lies7..9. Otherwise low-byte48B4A8==0 permits; a nonzero result blocks only for secondary context1036BA44+20 equal7/9. These are numeric runtime gates, not recovered pause/death/failure/game-mode names.

Service `1E1E58` handles **latch exactly1**, not every nonzero word. Getter244658 supplies singleton float+5B62C; an ordered comparison≥1.0 calls11920→38E3B0 before clearing latch0. NaN does not qualify; other nonzero latch values block admission but are not serviced here. The threshold is not given timer/progress units, and no current runtime value is inferred from the save.

Within the admitted writer, nonzero category increments its BE32 counter modulo32 before saved906EC is tested. Segment+8 increments only when906EC==0 and the selected segment resolves; category0 skips its word. These counts need not agree and are not promoted to a death/failure total. Five vtables independently associate selector categories2..7 with virtual method+10, but actor names, invocation frequencies and category1 selection remain unresolved.

[Inspect-TodResetContext.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodResetContext.py) reproduces77 native guards and10 tests covering low-byte admission, exact latch values, ordered NaN/Inf float behavior, counter wrap, replay/mapping distinctions, bounds and unchanged inputs. Previews use supplied runtime inputs and refuse categories outside physical0..7 even though native writer lacks that bound. Actual eight counts are zero/replay word3; no current latch, category or blocking predicate is reconstructed. The app bundles `reset_context` and explains the gates in selected-row details without extra columns or editing controls.

## Saved segment slots and runtime configuration mapping

The new consumer pass refines previously mapped segment storage without renaming opaque fields. Runtime table `101E8D70+20+4*requestedSlot` supplies two different relationships. Validity getter `2CDBC0` tests its word against−1 but returns the **requested slot**, not the mapped word. Guarded saved-pointer getter `2CDF40` then uses saved488+currentWorld×408+requestedSlot×30. Raw getter `2D14E0` omits that mapping-validity gate. By contrast, configuration getter `2CDEC0` uses the **table value** as an index in runtimeRoot+EA24+currentWorld×1E0+mappedIndex×30. Configuration remapping therefore does not reorder GAME.SAV segment slots. These native leaves do not establish0..9 input bounds; inspector reads are limited to the200 physical records.

Named completion `2D15C8` tests the requested raw saved byte+2C: nonzero returns0 unchanged; zero calls finalizer `2CE328`, then stores1/returns1 even if finalizer skipped for nonzero replay word906EC or absent runtime mapping. Runtime checkpoint-mask work occurs separately before the byte test. A recorded completion flag is not proof of an appended log, timer finalization or reward commit.

Tick `2CE620` and finalizer require saved byte+2C==0 in addition to replay/mapping gates; reset leaf `2CE518` **does not test completion**. When its replay word is zero and the selected slot resolves, it increments BE32+8 modulo32, clears current-attempt+4 and accumulates old+4×runtime config10FC8 into adjusted+0. Thus a completed record is not intrinsically frozen against this leaf; this does not prove the engine actually calls it after completion. Category increment happens before the replay gate and remains separate from these segment writes. No timer unit, current configuration or safe edit range is assigned.

[Inspect-TodWorldConsumers.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWorldConsumers.py) reproduces61 native guards;11 tests cover complete/invalid-mapping/replay gate combinations, requested-versus-mapped addressing, normal-domain previews, bounds and immutability. Actual snapshot has replay word3, log count0 and all200 completion bytes0; all20 world tails404..407 are zero. Runtime mappings cannot be inferred from these bytes. Segment word28/tail2D..2F and world tail404..407 remain semantically unresolved. `world_consumers` is bundled under Research; selected-row details retain the simple five-column view without edits, remapping or log simulation.

## Saved level requests and runtime deferral

Saved load destination906E8 and next-level selection8740 were already typed/named. The new consumer pass confirms **how load requests can leave these saved fields unchanged**. Direct setters `27BAD0`/`27A818` write their supplied low32 bits without local ID checks; `set_save_level` does not itself request a transition, and `set_next_level` does not write the runtime deferred queue.

Transition `2D16A0` first returns when r4==0 and the requested ID equals saved906E8. Force bypasses that equality only. A runtime byte getter `38E440` selects a special path when nonzero; with zero qualifier, runtime mode `1036BC0C==4` and r5==0, the routine stores the ID in **runtime10063024** and returns without a name request or saved906E8 write. This runtime word lies outside the serialized span and is distinct from saved8740. Other branches pass the name pointer through48B490, then write906E8 before requesting the ordinary transition or setting a special runtime byte+1 latch. A saved assignment is not proof of successful loading; context/phase labels remain unknown.

Pending consumer `2D17C8` skips runtime signed ID−1. Otherwise runtime helpers2518F8/252C68 supply a float gate: ordered result≥1.0 permits name lookup,48B490, saved906E8 write,38E3E0 transition request and finally pending=FFFFFFFF. Below-threshold/unordered results retain the request in this path. Constants0.5/0/1.0 are not given elapsed-time/progress units. This **runtime** skip marker does not establish sentinel meaning for actual saved8740=FFFFFFFF. Full restore `35E508` reaches2D16A0(saved906E8,1,0), bypassing equality but not every later gate.

Forward name lookup `2D0880` scales low32 ID by4, sign-extends that32-bit offset and indexes the nineteen-pointer catalog **without a local bounds check**. Inverse `2D08D8` scans nineteen entries and returns0 on no match, which is not a proved successful name match. The inspector preserves unknown saved IDs and never follows them; pure branch previews accept only IDs0..18 with explicit runtime inputs. Actual saved destination is00000000, next selectionFFFFFFFF; no pending queue, qualifier, current planet or request outcome is inferred from this snapshot.

[Inspect-TodLoadSelection.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodLoadSelection.py) independently reproduces63 native guards and eight tests for branch ordering, forced deferral, direct field separation, native lookup limits, unexpected raw IDs and unchanged actual inputs. The report is bundled as `load_selection`; selected-row details add plain-language qualifications without new simple columns or editing controls.

## Bonus content queries and runtime language selection

The eight remaining named bonus operands have confirmed shipped pause-menu **unlock-query consumers**, not newly proven direct saved-byte effects. Concept-art operands2/6/10/13 select image index ranges1–66,67–112,113–131 and132–141. Cinematic operands0/4/8 enable rows17/18/19; operand12 enables rows20–22. Previously-played movie status can independently enable those rows. The replay bypass applies only to ordinary rows1–16, not the six bonus rows. None of these traced functions calls `get_cheat_state`; this does not prove their raw bytes unused everywhere.

The previously unnamed runtime selector `100D6478`, getter `5BFE08`, is **language**, proven by parser `5BFF78`, CLI `-language`/`-lang` and system initializer `5C0280`. Literal pairs map Japanese0, French2, Spanish3, German4, Italian5, Dutch6, Portuguese7, Korean9, Chinese10, Finnish12, Swedish13, Danish14 and Norwegian15. Setter `5BFE18` aliases11→10; other low32 values are not domain-clamped. Initial/unmatched-parser value1 is a native fallback/default: an explicit English parser literal was not found and is not invented. The system language query return is not tested before its stack output is consumed, so parser fallback behavior is not a proved system-query failure default.

Language1 exposes14 bonus-menu entries; other values expose13, skipping physical developer-commentary slot5. Availability `27108` remaps menu operands>4 by+1 when language!=1, then adjusts threshold indices for resulting7/11/14. Shipped pause handlers pass named enum operands without proved language compensation. Consequently their query targets must not be silently equated with the physical saved slot of the same enum. Saved score is compared unsigned; raw state is not the availability predicate. This also identifies the direct commentary consumer's `251E08` qualifier as language==1, without proving a particular clip or localized language label.

[Inspect-TodBonusRemaining.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodBonusRemaining.py) reproduces183 native guards and optionally verifies the original pause asset plus five compiled function digests. Eight tests cover remapping, content/replay distinctions, unexpected states, exact bundled reports and unchanged input hashes. Supplied score750 satisfies the physical definition thresholds and all eight raw states are zero; **current runtime availability is not inferred**. Reports `bonus_remaining` and `bonus_remaining_assets` are available under Research; simple bonus columns are unchanged.

## Arena operation routing and separate milestone writers

Bridge `282AF8 → 24F098 → 23AD0` constructs a runtime request; dispatcher `24650` uses eight signed BE32 relative offsets at `24714`. Operation5 reaches `24940`, constructor `62D080`, vtable `8564C8` slot+8, descriptor `87BD40` and loader `62D2E8`. These are runtime fields, not save offsets. **The supplied list's installation/alias as `ARENA_CHALLENGE_DATA` is still unresolved**; a concrete UI-loader route does not establish source-index/native-ID/display-row equivalence.

Four original challenge scripts independently link named calls to save writers. `set_challenge_success → 27A9C8` increments a BE32 counter at `56D8 + nativeID*4` modulo32 bits, without setting those milestone flags. Both named `set_flag` wrappers reach OR stores in the BE64 global bank `5528 + (flagID//64)*8`, integer bit `flagID%64`.

| Compiled script | Native counter ID | Reached action order and qualification |
| --- | --- | --- |
| challenge1 | 1 | Success, then conditional milestone74 while clear |
| challenge4 | 4 | Success, then conditional milestone75 and checkpoint85 |
| challenge6 | 6 | Timeout-false branch: milestone88, source `wait(6)` literal, then success |
| challenge10 | 12 | Success, then conditional milestone89 and checkpoint85 |

These are separate calls, not an atomic transaction; source wait6 is not reconstructed engine elapsed timing. Changing a counter does not perform cinematics, inventory or story/checkpoint actions. Script filename10 is not native ID10. The supplied flags74/75/85/88/89 are clear and counters1/4/6/12 zero, which does not prove a current trip or running script. [Inspect-TodArenaDispatch.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodArenaDispatch.py) reproduces110 native guards; optional original archive checks eight source/compiled fingerprints and14 compiled guard ranges. Eleven tests cover native routing, action ordering, flag bit order, table aliases and unchanged inputs. Reports `arena_dispatch` / `arena_dispatch_assets` and selected-row milestone details remain read-only.

## Grid browsing synchronization and restore trust boundaries

Constructor `244DD8` installs the first context subobject at singleton allocation+70. Its vtable frame `247E78` passes receiver+1AF14 to the selector, proving that first context's grid equals allocation+1AF84 used by pre-snapshot `24EAC8`. This resolves the apparent70-byte mismatch for that context only, not all alternate instances.

Selector `24DEA8` is suppressed only when display latch40024 **equals1**, not every nonzero value. It compares runtime definition pointers: the same pointer skips flush/reload/header copy; a different pointer flushes the prior logical grid and selects the new saved slot. Nonzero readiness restores the encoded grid but **does not recopy its C8-byte header**. A zero-ready selection initializes the grid/image and copies the header. Saved handles can therefore be historical. Group updater `24E8A0` has no readiness gate; selected group flags can change before readiness publication.

Map activation `25BBF0` encodes the active grid before image overlay. Browse `25D1D0` restores another ready slot into the logical buffer without replacing the active definition pointer20. Reached exit `25B918` restores that active definition's own saved slot before image refresh/latch clear. Image helpers write a separate display buffer: other-slot rendering maps logical zero/nonzero to image0/127, while active overlay preserves baked input only for nonzero logical cells and transforms image1–127 by+110 modulo256 and128–255 by−17. These display operations do **not** normalize saved classes1/2 or identify colors/alpha.

Encoder `35C5B8` writes payload, then encoded length60D0, accumulatorC8, readyCC=1; it does not clear existing readiness at entry, and atomicity is not established. Decoder `35C460` uses declared length/output cap but does not check accumulator, ready, copied header or group flags. A short stream leaves the prior runtime output tail untouched. Initializer `35E070` clears readiness, length and seven group flags only—not accumulator, header, payload or final60DB. The encoder's final-run lookahead can cross its logical source boundary; detached safe decoders clip output and never emulate those out-of-range reads.

[Inspect-TodGridLifecycle.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGridLifecycle.py) reproduces101 native guards with ten tests for buffer retention, exact latch comparison, image-only branches, constructor provenance, opaque retention and unchanged inputs. All19 ready streams in the supplied snapshot fill the logical grid and have four clipped final-run bytes; slots3/4 remain unready. These observations reveal neither actual runtime adjacent bytes nor display/latch state. Header `D..F`, `1D..1F` and final60DB remain semantically unresolved. The app exposes the report under Research and plain-language selected-row details without extra simple columns, repair or editing controls.

All four new passes inspect the exact ELF and optional detached plaintext read-only. Optional `--archive` validates original assets without Lua/native execution. No private save, game executable or asset payload is bundled. These findings are not in-game edit validation or cross-build compatibility proof.


## Inventory reset footprint and opaque prefix-byte ownership

Record reset `465C98` is **not a full20-byte clear**. Decoding its complete leaf body confirms writes to `+00..11` only: the supplied ID, three zero words (XP, ammo, modifier mask), and zero ownership/level bytes. Opaque record tails `+12/+13` remain untouched. In contrast, bulk initializer `466A60` zero-fills all `280` inventory bytes before its32 reset calls, then clears acquisition counter `280`; both tail bytes are therefore zero at that initializer boundary.

Selective restart `3CED40` first initializes staging, then copies the current state's first `484` bytes at `3CEDD0`, before selected record resets call `465C98` at `3CEE1C`. The copied opaque tails survive those observed reset steps even in records whose interpreted fields are reset. This claim does not cover every subsequent callback or provide a safe arbitrary-value edit range.

The prefix initializer `35DC80` ends its final scalar store at `484` exclusively, while the world loop starts at `488`. Four bytes **`484..487` are outside those initializer writes and the first-prefix restart copy**. Their restart value is not inferred as zero or copied from the live save by those steps. Full snapshot copies include them verbatim; no gameplay name, padding or globally-unused claim is made.

The supplied snapshot has all32 opaque tails and these four gap bytes zero. Sentinel fixtures instead retain `ABCD` and `FE123456` unchanged during inspection. [Inspect-TodInventoryReset.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodInventoryReset.py) independently decodes the leaf write mask and reproduces22 byte guards; eight tests cover all normal IDs, invalid previews, initialization/copy distinctions and unchanged inputs. The inspector explains the inventory-tail distinction in weapon details and keeps the gap under Technical only. No initializer or reset is run.

## Compiled arena selector inputs and independent reward predicates

The original global archive contains separate level scripts under `/levels/imperial fight fest/scripts/`, distinct from the previously mapped arena configuration script. Fingerprinted source plus compiled `main.lc`, `arena.lc` and `arena_2.lc` establish20 literal master descriptors and the following reached script lists. A bounded constructor fold reads literal metadata only: it does not execute calls, branches, Lua or game code.

| Script list | Native challenge IDs in literal input order | Reached-path qualification |
| --- | --- | --- |
| First-trip opening1 | `1` | Story flag74 clear; forces index1 without calling the selector |
| First-trip opening2 | `4` | Flag74 set, flag75 clear; forces index1 without calling the selector |
| First-trip final | `1,4,2,3,7,5,8,10` | Both first-trip flags set; list passed to the selector |
| Return-trip bonus1 | `1,4,2,3,7,5,8,10,6,12,13,14,17,18,9,11,20,22` | Reached return script loop after two flag-qualified opening scripts |

The return script also constructs an identical bonus2 literal, but the compiled selector call takes **bonus1 only**. It is not an additional proven selectable branch. Native catalog entries `IFF_B_13` and `IFF_B_19` lack master descriptors in compiled `main.lc`; `IFF_B_14` and `IFF_B_17` have descriptors but are omitted from the reached return list. Compiled rows must not be counted from commented/source-only text or inferred from the22 native configuration entries.

Fourteen compiled assignments update descriptor `active` from a predecessor challenge's **signed completion count >0**. Four relevant independently exported story IDs are74/75 (`LVL_IFF_CHALLENGE_1_DONE` / `_2_DONE`) and88/89 (`LVL_IFF_RETURN_CHALLENGE_9_DONE` / `_10_DONE`), integer bits10/11/24/25 in saved BE64 word `5530`. These bits and challenge counters are independent; neither bank is normalized to the other. The supplied save has all four bits clear and all23 physical challenge counter words zero. That establishes saved predicates only, not which trip, script or UI is currently running.

### Native dependencies and the remaining table-installation gap

Named `get_challenge_weapon_reward`, wrapper `316B8 → 273D0`, resolves a menu source index through `110B0 → 2756F8`. It exposes configured `ArenaConfig[nativeID].WpnReward` only when **signed configured weapon ID >0 and raw saved counter `56D8 + 4*nativeID ==0`**; otherwise it returns `-1`. Any nonzero counter hides this first-victory weapon reward, including high-bit values interpreted as negative by signed consumers. This differs from the shipped UI's signed-positive display partition and activation rules. Named bolt reward wrapper `317C8 → 261E0` resolves the same index and delegates to the independently mapped direct-ID reward calculator; runtime config is required for a live quote.

Selection `314E8 → 26088` writes runtime Lua `ARENA_CHALLENGE_DATA.selection`, resolves the native ID into runtime object `+D8`, then requests a runtime phase transition. These are not new save fields. Operation bridge `282AF8` validates actor/type `B9`, clears a runtime member through `39DEA8`, and calls `24F098(thread+48, opcode5,0,0)`; it does **not itself prove installation or aliasing of the supplied list as `ARENA_CHALLENGE_DATA`**. The lower operation dispatcher/UI-loader route is now mapped below; the challenge-table installation/alias remains unresolved.

Consequently, recovered **selector-input indices**, runtime menu source indices, native IDs and display rows are kept distinct. The inspector adds script-list membership, independent saved story bits and the raw-zero weapon-reward qualification to row details without reordering counters or claiming current availability. Script/title localization symbols are not independently recovered English labels.

[Inspect-TodArenaTable.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodArenaTable.py) reproduces223 native guards, six source/compiled fingerprints, three compiled root digests and20 asset guard ranges. Thirteen tests cover list/master reproduction, the unselected literal, activation edges, BE64 flags, signed/raw reward differences, invalid inputs and unchanged source hashes. The native/asset reports are embedded separately as `arena_table` / `arena_table_assets` and visible under Research. No original asset payload or private save is bundled.

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodArenaTable.py --elf "path/to/EBOOT.ELF" --archive "path/to/global_cached.psarc" --save "path/to/plaintext-working-copy.bin"
python -B Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodArenaTable.py --elf "path/to/EBOOT.ELF" --archive "path/to/global_cached.psarc" --save "path/to/plaintext-working-copy.bin" -v
```

## Equipment-history dispatch and qualified bonus effects

This parallel pass separates persisted values from the native operations that consume them. The exact USA executable, detached plaintext snapshot and generated edge cases are inspected read-only. Neither native code nor Lua is executed, and no new editing controls are enabled.

### History is recorded on a qualified state-entry callback

The saved signed item-ID words at `42C`, `430` and `434` are newest-to-oldest history, not three simultaneous equipment slots. Hero initialization installs dispatch table `84A4B8` at hero member `1E00`; its slot `+28` points through descriptor `8666D8` to history updater `1F5570`. The runtime inventory's member `188` supplies the owning hero, whose `1A68` resolves the serialized state.

State step `467228`, call `4674C0`, invokes that callback only for runtime state member `110 == 2` with a nonzero entry argument. Pump `467A30` reads entry latch `118`, converts it to a Boolean, clears it, calls the step, and repeats if the step raises the latch again. The state1-to-state2 transition raises it, allowing history dispatch within the same pump invocation. The callback runs **before** state2's active-object and pending/current-item checks. It can record duplicate or `-1` values; it is not equivalent to every frame or every successful equip.

Request `467908` instead queues runtime pending item `140`, or returns an already-active success under its separate checks. It does not directly update saved history. Runtime reset `1F5DB8 → 1F5C18` clears pending ID `140=-1` and active handle `144=0` without clearing those three serialized words in that function.

| Consumer | Exact reached-path selection rule |
| --- | --- |
| Restore equipment request | Use `42C`, except `-1` or item30 becomes item0; separate ownership/ammo/runtime checks can reject the request |
| Restore recent-history seed | Use `42C`, except zero selects `430`; `-1` becomes item1. Write only if runtime recent count `13C` is zero |
| Menu primary | Use `42C`, except `-1`/zero selects `430`; selected zero becomes `-1` |
| Menu secondary | Use `430`, except `-1`/zero or equality with primary selects `434`; selected zero becomes `-1`. The final fallback is not deduplicated |

The supplied history `15/25/0` therefore selects restore request15 and seed15, while the separate menu consumer selects15/25. These are **request/fallback observations**, not proof of current runtime equipment or accepted equipping. [Inspect-TodEquipmentLifecycle.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodEquipmentLifecycle.py) independently reproduces67 native guards; its bounded synthetic helpers exclude out-of-catalog IDs and retain unknown snapshot words without previewing them.

### Six physical bonus-state consumers

These consumers read direct bytes at `86F8 + native bonus ID`. The four confirmed score gates use **unsigned saved weighted score `8708`**, not `8734` or warning latch `8738`. Native enum names are not recovered localized labels.

| Native bonus | Confirmed local behavior; separate runtime gates still apply |
| --- | --- |
| ID1 `CHEAT_HERO_BIGHEAD` | Score≥50 and nonzero state; states1/2/3 multiply transform basis by2/4/0.5, other nonzero bytes by1 |
| ID3 `CHEAT_ENEMY_BIGHEAD` | Score≥100 and nonzero state; state2 uses0.5, other nonzero bytes2.5; additionally checks a nonnegative bone index |
| ID5 `CHEAT_DEV_COMMENTS` | Score≥200, nonzero state and runtime language selector exactly1 permit qualified runtime dispatch; exact clip and localized language1 label remain unresolved |
| ID7 `CHEAT_WRENCH_REPLACE` | Raw byte indexes a runtime model asset table and changes a64-bit selection mask at runtime `+118`; neither traced local block clamps the index or checks score |
| ID9 `CHEAT_JAMES_ZURKON` | Nonzero state **or a separate runtime override** selects factory pair `C3/657`, otherwise `4B/311`; no local score gate established |
| ID11 `CHEAT_MIRROR_LEVEL` | Score≥500 and nonzero state set runtime latch `10724C10` and context byte `+45` bit0; otherwise both are cleared while unrelated bits remain |

The head consumers' zero/insufficient-score path does not explicitly restore an earlier transform. Unknown wrench state255 remains an unchecked asset index, not a safe replacement option. Missing *local* score checks do not establish that all callers ignore eligibility. Mirror axis/input consequences, runtime asset-table capacity, factory object labels, commentary clips and current activation remain unconfirmed.

Actual snapshot: weighted score750 and all14 bonus-state bytes zero. That alone does not establish the state of every runtime effect: the factory consumer has an independent override, and other consumers require actors/models/call timing absent from the save. [Inspect-TodBonusEffects.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodBonusEffects.py) reproduces98 native guards and six effect rules. Tests preserve raw unsigned scores, state255 fallbacks and original input hashes. The viewer keeps its simple columns, adds these qualifications to selected-row details, and embeds both full reports under Research.

```powershell
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodEquipmentLifecycle.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin"
python -B Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodBonusEffects.py --elf "path/to/EBOOT.ELF" --save "path/to/plaintext-working-copy.bin"
```

## Object-counter lifecycles, quick-select mutation and opaque-tail ownership

This parallel pass strengthens existing storage mappings rather than assigning names to every opaque byte. `inventory_aux` and `final_tail_fields` independently reproduce the exact native reset/restore/consumer relationships. All observations are scoped to the hash-verified USA BCUS98127 v02.00 executable. The program shows the new explanations read-only; no restart, item insertion, skill award or initializer is executed.

### Three object-counter banks: reset is not lifetime accumulation

The already-mapped 23-word banks begin at `304` (signed current count), `360` (unsigned high-water count) and `3BC` (raw positive-addition bits). In selective restart `3CED40`, call `3CEDD0` copies the first `484` bytes from current state into staging **before** the clearing loops. The object loop covers IDs1..22; mask `BFF` preserves IDs1..9 and11, while ID0 is outside that loop and retains its copied words.

| Object IDs | Effect at this reset boundary |
| --- | --- |
| `0..9, 11` | All three copied words preserved |
| `10, 12..22` | Current, high-water and positive-addition words cleared together |

The reached hero-restore assignment block in `1E33C8` separately calls setter `23D970` with count1 for IDs `0,1,2,3,4,9`. The setter writes current1, raises the peak only by unsigned comparison, and does not increment additions. A saved `1/1/0` combination can therefore come from restoration, not a witnessed pickup. Earlier runtime gates and subsequent callbacks still apply; this is not an unconditional specification for every load.

Getter `23D920` returns additions with signed extension. Within the guarded hero-update routine `1E5C28`, calls `1E6038/1E6050` and comparisons `1E6040/1E6058` require **signed additions for `OBJ_SOULS` (ID16) >25 and current Souls count ==0** before the skill path at `1E636C → 122E0 → 35D5D0`. Independent native exports identify skill52 as `SKILLPOINT_SOULS`. High-bit raw additions are not large positive counts for this particular consumer. Other runtime gates apply; the inspector does not predict an award.

The supplied save has Souls current/high-water/additions `0/0/0`, while skill52 is already set. This confirms the saved fields and independent retained skill bit, not a captured award or the cause of those values. Reset counters must not revoke a previously earned skill in the inspector. [Inspect-TodInventoryAux.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodInventoryAux.py) reproduces211 guards and optional bounded snapshot observations; its detached preview helpers exercise generated fixtures only. `TOD_SaveObjectCounterBanks_verified` describes the three banks without automatic application or replacing analyst types.

### Quick-select: duplicate removal and a bounded insertion domain

Saved words `284..304` remain32 signed item-ID slots. Native membership/removal routines `1E22F8/1E22A8` scan all32. Automatic insertion `1E26F0` returns unchanged when the item exists anywhere, including slots24..31; otherwise it searches only the first24 for `-1`. A full first24 cannot use an empty tail slot. Definition lookup and flags `1040` qualify the path; saved ownership is not a separate check here.

Explicit valid insertion into slot0..23 first removes **all** copies of the same item across32 slots, then overwrites the chosen slot without compacting or relocating displaced items. Slot arguments above23 take the automatic branch. The pure fixture model deliberately excludes invalid/negative item IDs rather than inventing their native behavior. A no-slot branch can send message126 and set saved warning latch8738 depending on8734; this does not create an insertion.

The selective restart scans all32 quick-select words, clearing stored IDs `24,26..31` to `-1` while retaining other slot positions. These are physical storage indices, not a reconstructed live wheel order or new editing permission.

### Opaque final word and two unwritten settings bytes

Word `906E4` still has no established gameplay name. Initializer `35E110` stores zero at `35E1B8`; the last of21 grid blocks ends at `906E4` **exclusively**. Every explicit current-state preservation destination in selective restart excludes this word, so the final staging-to-live copy at `3CF158` transfers zero there under the observed separate staging/current-state arrangement. This statement ends at that copy boundary; later destination callbacks are outside its scope.

Snapshot capture `35E710`, initial restore `35E508`, and alternate staging copy `3CF1B8` instead include all `906F0` bytes, transferring the raw word verbatim at their copy boundaries. A bounded aligned-word census finds no embedded absolute pointer to `10280204` in the four file-backed LOAD ranges; this is **not** proof that no computed, indirect, dynamic or relocated consumer exists.

Leaf settings initializer `35EE40` writes exactly46 of48 bytes: members `00..2D`, leaving opaque save bytes `114D6/114D7` untouched. Selective restart's full `30`-byte settings preservation includes both, and its later help-byte clear at `114D0` does not overlap them. Actual word/bytes are allzero, which does not establish padding, unused storage or defaultzero. Technical view now exposes the final word and explains these boundaries without normalizing any input. [Inspect-TodFinalTail.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodFinalTail.py) reproduces37 guards, the decoded write footprint and the bounded copy/pointer census.

### Arena native IDs, source indices and display rows

The native and shipped-UI pass confirms three distinct index spaces:

| Index space | Role | Relationship |
| --- | --- | --- |
| Native challenge ID | Exported `IFF_*` enum / saved win counter | Counter address `56D8 + 4*id` |
| Lua source index | One-based `ARENA_CHALLENGE_DATA` row | `.id` resolves to the native ID; UI preserves this index as `chalNum` |
| Display row | Current position in shipped UI `challengeArray` | Completion-dependent partition; routes selection/images through `chalNum` |

Named `get_num_challenges` chain `31EF8 → 26298 → 13B80 → 275268` reads `ARENA_CHALLENGE_DATA.num`, converted to signed32 by truncation toward zero. This is not literal23, a raw table length or a recovered count of valid saved IDs. Resolver `2756F8` reads the source row's `.id`; consumer `279B8` loads the saved counter and sign-extends it. The resolver's ordinary nonnegative cap23 is not a safe counter bound: only IDs0..22 occupy the bank, and ID23 aliases independent reset category0 at5734. Missing-row result0 and absent lower-bound validation do not authorize arbitrary source indices.

Default chain `31408 → 26048 → 11100 → 275438` starts with a native ID from runtime object `101AEFF8+D8`, **outside the saved block**. The inverse helper scans contiguous source rows from1, returns the first matching truncated `.id`, and stops with-1 at the first non-table. Its caller converts negative results to0. It does not use `.num` as the scan bound.

Original `global_cached.psarc` entry `/built/anark/arenachallenge/built.dat` is103,692 bytes, SHA-256 `3DFD3B6231D06B1C7EE106BD521D263FC4D2B167B3D755280D70E635C38E1BF3`. Embedded Lua `ListUpdater` spans asset offsets `12A7A..15B5C`. Four function digests and20 instruction guards establish that initialization enumerates source indices1..`get_num_challenges()`, preserves each as `chalNum`, and stably partitions **non-positive signed completion counts first, positive counts second**. Source order is retained within each group. Negative counts are not misread as unsigned-large wins or equalzero. `isActive` does not remove a row from the list; selection checks it before passing `row.chalNum` to `select_challenge`. Default selection searches current display rows by `chalNum`, and image lookup also uses `chalNum`, not display position. No Lua is executed.

The runtime source table's actual initializer, index-to-ID values, `.num` and labels remain unrecovered. All23 actual native-ID counters arezero, but that snapshot cannot assign source indices or reconstruct the current menu. The inspector keeps native-ID rows and explains the distinction instead of reordering them or guessing a current default. [Inspect-TodArenaMenu.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodArenaMenu.py) independently reproduces31 native guards, optional `arena_menu_assets`, and bounded plaintext observations. This pass did not establish a new saved segment`+28` consumer or name; that word remains opaque.

## Decryptor state, saved timing aggregates and copied runtime handles

Three parallel tasks added126 native byte guards,17 ELF annotations and three narrow types. The new `adaptation_context`, `tail_aux_fields` and `grid_aux_fields` sections reproduce named Decryptor behavior, four newly typed saved floats and the formerly opaque grid-header word. `grid_aux_assets` embeds only non-private resource fingerprints/descriptor metadata; original binaries and saves are not bundled. All findings are scoped to the exact USA v02.00 ELF and remain read-only.

### Decryptor outcomes and spark-speed scaling

The previously behavior-qualified words now have specific context:

| Save offset | Native meaning | Actual save / caveat |
| --- | --- | --- |
| `8758`, BE32 | Decryptor wins in the traced success path | 0; wrapping native counter, not guaranteed all-time wins |
| `875C`, BE32 | Sixaxis-enabled losses since success | 0; increments only with saved Sixaxis byte`114D3` nonzero, clears on success; not all attempts/deaths |
| `8760`, float32 | Decryptor spark-speed multiplier | 1.0; ordered finite updates bounded0.6..1.0 and success resets1.0, not safe edit limits |

Caller `3B8BF0` dispatches seven numeric runtime states through signed32 relative table `3B8C74`, pointer slot`8A364C`. All targets are decoded inside `3B8BF0..3BA168`, independently of Ghidra's omitted switch body. Native help strings explicitly name Decryptor Sixaxis/stick control and stabilizing the ball with X. Independently exported lookup keys `GEN_TXT_GPLAY_DECRYPTSTART/WIN/LOSE` have IDs`389/38A/38B`; after updater`3B9978`, runtime flag`5381` nonzero selects WIN at`3B99AC`, zero selects LOSE at`3B9C2C`. This names the checked outcome path without claiming a complete lifetime statistic or every cancellation/retry lifecycle. Runtime retry byte`5383` increments with8-bit wrap and is not another saved counter.

Named API `dc_set_spark_speed` at registration`89E688` reaches descriptor`86B688`, wrapper`2A7A28`, native`28E678`, storing runtime base speed`51DC`. Instructions `3B9590..959C` multiply that base by saved`8760` and store runtime`51D8`. This establishes a **specific spark-speed multiplier**, not a generic combat-difficulty setting; physical speed units and every downstream motion effect remain unverified. [Inspect-TodAdaptationContext.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodAdaptationContext.py) reproduces53 guards. The app now shows three clearly named Decryptor rows in the simple player summary, with raw bits and lifecycle qualifications retained in Technical/details. `TOD_SaveDecryptorState_verified` complements the earlier generic type without overwriting it.

### Four saved timing floats and corrected log provenance

Getter `2CDBF8`, TOC`89FF20`, resolves slot`89F07C = 101F8264 = saved base+8744`. These are saved floats, not runtime-only totals:

| Save offset | Role | Actual snapshot |
| --- | --- | --- |
| `8744` | Accumulated adjusted segment scalar | 0.0 |
| `8748` | Accumulated segment configuration reference | 0.0 |
| `874C` | Timing gate A remaining | 10.0 (`41200000`) |
| `8750` | Timing gate B remaining | 300.0 (`43960000`) |

On a valid, unfinished segment's normal finalization path, `2CE328` adds segment`+00` adjusted elapsed to`8744` when ordered finite elapsed is at least reference`+20 × float32(0.1)`; otherwise it adds the reference itself. It adds configuration reference`+20` to`8748`, then copies the updated saved totals into log`+90/+94`. Retained log values need not match current totals. Historical runtime-prefixed field keys/types remain for compatibility, but their comments now state the saved source.

Initializer `35D9A0` clears only these two totals, not explicitly the gate floats. Reset callbacks `2CDC30` / `2CDC00` load runtime configuration`10FCC/10FD0` into the gates; an independently guarded state-machine branch clears both. `2CE620 → 24ECB8 → 69B810` advances them using runtime context`10731DA0+4` and scale1.0. Ordered finite remaining<step writes positivezero and returns1; equality writeszero but returns0. After advancement both gates must be strictly positive before segment elapsed can tick, alongside independent pause/reset/validity conditions. Time units and event names remain unverified: **10/300 are observations, not defaults or seconds**. `2CDFB0 → 2CDC78` consumes the saved totals into a separate runtime scalar, not back into either saved word. [Inspect-TodTailAux.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodTailAux.py) reproduces40 guards. These four technical rows remain out of the simple summary; no timer simulation or edits occur.

### Grid header word is a copied generation/slot handle

Generic definition allocator `64D828` assigns header`+08 = (generation<<16)|slot`: high16 wrapping generation, low16 slot in a512-slot runtime pool. Loaders `64DCF0` / `64DAB0` preserve this value across resource-payload copy and refill geometry pointer`+00` and class`+04`. Resolver `64DC50` uses the low16 slot and requires entire-handle equality against the resolved definition's`+08`; this is not a proven general slot-bounds/null-safety contract. Release `64D9E0` increments generation and clears occupancy; pool reset `64DB68` resets512 entries. The class535 selector copies exactly`C8` bytes into the saved grid block, including these historical handle bits. **Never treat them as stable game-wide IDs, current validity, or pointers to follow from a save.**

All19 ready copied headers match the original shipped class535 candidate bodies at`+0C..C7`; every source first12-byte prefix iszero and refilled at runtime. The bounded in-memory candidate scan records each original `gameplay.dat` fingerprint, descriptor/payload offsets and body hash. It is not a complete resource schema or an inventory of every volume instance. Actual ready handles have generation1 and slots5..76, with duplicate handles across different levels—further reason not to label them global UIDs. [Inspect-TodGridAux.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodGridAux.py) reproduces33 guards and the optional asset comparison. `TOD_RuntimeDefinitionPrefix_verified` supplies the refined12-byte type without replacing the older volume-header type. The app shows the split in grid details only; out-of-range slots/unready values are preserved, not resolved or repaired.

Copied bytes`+0D..0F`, `+1D..1F` and final saved byte`60DB` remain opaque. The initializer writes only seven group flags`60D4..DA`, readiness and encoded length; observed source zeros and lack of a write do not establish padding. Tail`906E4` and unknown option meanings remain unresolved. No new edit safety, full-game reversal or cross-build acceptance is claimed.

## Runtime health and checkpoint ammo: qualifying restoration paths

Three parallel tasks produced the health/checkpoint, auxiliary-word and first-person findings below. This pass adds132 native byte guards,16 annotations and two narrow types. [Inspect-TodHealthPersistence.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodHealthPersistence.py) reproduces61 exact guards in `health_persistence`; all source observations are read-only.

### Health identity and XP-driven refresh

Named `hero_get_health` native `289358` requests float attribute`6C` and reads attribute`+4`. Base hero vtable`84BE30+24` points through descriptor`868D78` to dispatcher`23E368`; subclass`84A3F8+24` points through`8660E0` to `1E3380`, which delegates this attribute to the base. Exact dispatch returns hero`+1780`, making **current health runtime hero`+1784`**. Native `240FF8` adds a float to that value and clamps ordered finite results against hero`+1788`, proving the latter is the health upper bound. This path has no additional zero lower clamp; neither member is a save-file offset.

Hero bind `23E650` sets its saved-state pointer, clears runtime level`1B61` and fractional XP`1B68`, reads saved integer XP`418` and calls `23E090`. On its qualifying changed-level path, progression reads float `table+190+4*new_level` and stores both current health`1784` and capacity`1788`. This proves conditional XP-driven health refresh, not unconditional healing for XPzero/disabled thresholds or a dedicated serialized current-health word. The table root `897B00 → 101B9EE8` is runtime BSS, so the supplied XP2,315,144 cannot establish a numeric current level, health or capacity from the ELF/save alone.

### Checkpoint capture, vendor merge and clamped ammo restoration

Runtime checkpoint `10330610` is outside the serialized state `101EFB20..10280210`: its relative offset`140AF0` exceeds file size`906F0`. Capture `35CF40` copies32 inventory ammo floats per iterated player: `state + player*484 + weapon*14 + 8` into `checkpoint + 50 + player*80 + weapon*4`. These are ammo, not weapon XP or health. The bank is runtime-only and does not make checkpoint positions or valid flags part of GAME.SAV.

Native merge `35D358` selects the higher ordered finite value from current saved ammo and checkpoint ammo using `fsub/fsel`. Qualified successful vendor paths `2D2990`, `2D2B90`, `2D2D38` call it at `2D2AE8`, `2D2CF0`, `2D2E28`; this is not a complete inventory of every refill or every ammo writer. During hero bind, nonzero checkpoint-valid byte`EF` gates a32-slot restore through thunk`13DD0 → 465DC0`. That setter applies the definition/level/modifier-dependent maximum from`463DE0` and a zero fallback, **not a verbatim bit copy**. Thus checkpoint setup can overwrite saved inventory ammo, and qualifying purchases can update the runtime checkpoint bank.

The actual first inventory bank includes Combuster ammo100; no second-player runtime bank, active checkpoint or current health is inferred. Tests retain extreme/nonfinite ammo bits and original hashes, check runtime/save separation and reproduce the bundled native report. The app explains this lifecycle in weapon details and a Research topic, without simulating checkpoint restore or enabling new edits. `TOD_RuntimeHeroHealthAttribute_verified` describes only the12-byte runtime slice; it is not automatically applied to a dynamic hero or to serialized state.

## Three saved auxiliary words: event branch, Sixaxis gate and bounded modifier

The earlier parallel auxiliary pass adds20 native byte guards in `save_aux_fields`, reproduced by [Inspect-TodSaveAux.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSaveAux.py). The later Decryptor pass above now supplies named outcome/spark-speed context; the arithmetic below remains valid and its field labels are refined accordingly.

| Save offset | Type / actual value | Confirmed behavior |
| --- | --- | --- |
| `8758` | BE32 unsigned / 0 | Increments with32-bit wrap when runtime argument byte`5381` is nonzero; its old value contributes to a threshold |
| `875C` | BE32 unsigned / 0 | Clears on that event branch; otherwise increments with32-bit wrap only when saved Sixaxis-enabled byte`114D3` is nonzero |
| `8760` | BE32 float / 1.0 (`3F800000`) | Ordered finite update bounded to stored float32 representations of0.6 and1.0; the event branch ultimately forces1.0 |

Initializer `35E110` passes save`+5528` to `35D9A0`; its inner member`+321C` is save`8744`. Stores at inner`+14/+18/+1C` initialize these three words to0/0/1.0. Update `3B5AB8` resolves saved state through `8A3554 = 101EFB20`; caller `3B8BF0` reaches it at `3B9978`. Runtime bytes`5381/5383` belong to its runtime argument and are **not** new save offsets.

For ordinary old counter values, threshold is `4 - min(old8758,2)`. The report preserves the exact low32-bit sign-mask expression for extreme counters; the shortcut is not a validation rule. With runtime`5381` zero, runtime`5383` above threshold subtracts float32`0.05`, otherwise the adjustment iszero; either path bounds an ordered finite result to0.6..1.0. With runtime`5381` nonzero an intermediate positive adjustment can be computed, but the final store overwrites it with1.0 and clears`875C`. Thus the intermediate `+0.1` constant must not be reported as an independently retained increase.

The later seven-state decoding above identifies the named Decryptor WIN/LOSE paths and spark-speed multiplier. These are not deaths, a combat-help setting or global combat difficulty; the Sixaxis gate still qualifies the since-success loss counter. Native `fsel` is not a NaN-sanitization contract. Fixtures preserve NaN payloads, infinities, out-of-bound floats and large unsigned words without repair; original hashes remain unchanged. The app now includes three named Decryptor summary rows, with raw arithmetic and lifecycle limits retained in details/Research.

## First-person option: entry latch and qualified camera coupling

The parallel option pass adds51 exact native byte guards in `first_person_option`, reproduced by [Inspect-TodFirstPersonOption.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodFirstPersonOption.py). Saved BE32 `114C0` still has no confirmed original option name. This pass establishes what two native update paths do with it rather than guessing a hold/toggle label.

Method tables `84AF18` and `84AF48` associate entries `20F3F0` / `2108D8` with updates `20F598` / `210B80`. Entry reads the saved word and latches a runtime byte at `+24` / `+3F` to1 exactly when the whole word iszero. Update reads that byte, not the saved option again. Zero-derived flag1 skips the mode10 orientation-adjustment paths; flag0 from any nonzero saved word permits them if additional runtime conditions pass. This does not establish that no other lifecycle changes the runtime flag.

Mode lookup `683F0` scans16 runtime records at container`+C0`, stride`200`, comparing numeric mode at record`+64`. The permitted paths call `778C8`, which uses vector/basis products and angular math to update runtime scalar`+F4` and basis`+C0`. This is neither a direct vector copy nor a save-field write. Entry mode requests0F/10 are priority-qualified and can be skipped if already in either mode; a request does not prove the active camera.

The actual word is1 (`00000001`), so its static interpretation permits the qualified mode10 path; it does not report the current camera. Opaque bytes `114D6/114D7` are bothzero and remain uninterpreted. Tests cover zero, ordinary and extreme nonzero words, method-table/branch evidence, malformed plaintext rejection and unchanged input hashes. No activation/release sequence confirms hold/toggle behavior, and generic `AIMMODE` text-tag exports are not evidence tying a menu label to this word. The app keeps the unknown field in Technical view and explains the new behavior in its details and Research topic.

## Saved pack/boot state, ordered segment names and initializer ownership

Three parallel research passes independently traced named APIs, the native asset loader and initializer write boundaries. New sections `hero_aux_fields`, `segment_configuration` and `world_aux_fields` contain66,42 and34 native byte guards respectively. Fingerprinted `segment_configuration_assets` records the ordered reference names from19 original level archives. All observations are read-only; none establishes safe edits or full game/save reversal.

### Three newly named saved words

| Save offset | Meaning | Native evidence |
| --- | --- | --- |
| `438` | Pack dispatch selector | Setter `27A30` stores0 for original argument zero, otherwise1; known consumers compare exactly1 |
| `43C` | Pack type | Named `set_pack_type` / `get_pack_type`, natives `27A30` / `26FB0` |
| `440` | Boot type | Named `get_boot_type` reads through `26FA0`; native setter `26F60` always writes0 |

Lua registrations `88952C/889534/88953C/889544` link `get_pack_type`, `get_boot_type`, `set_pack_type`, `set_boot_type` to wrappers `2FC58/2FBA0/2FAE8/2FA30`. Both setters convert a checked numeric argument through `fctiwz`; this conversion is not emulated for NaN/out-of-range values. Pack setter stores low32 bits while its selector test uses the original64-bit argument. The boot wrapper converts an argument, but its native target ignores it and writeszero. A named API is not permission to enable arbitrary equipment edits.

| ID | Pack enum | Boot enum |
| --- | --- | --- |
| 0 | `PACK_HELI` | `BOOT_NORMAL` |
| 1 | `PACK_THRUSTER` | `BOOT_GRIND` |
| 2 | `PACK_HYDRO` | `BOOT_GRAV` |
| 3 | `PACK_WING` | `BOOT_CHARGE` |

ID4 is `TYPE_COUNT`, not equipment. Actual save words are allzero (`PACK_HELI`, `BOOT_NORMAL`, selector0). This does not establish ownership or runtime availability. Consumers `1F1D58` and `1F2C50` additionally require runtime conditions; exactly-one selects numeric messages `58D`/`58C`, otherwise `58E`/`58B`. No animation/movement names are inferred from those IDs. Stores with matching438/43C/440 displacements in `3D5354` belong to a different monolithic configuration object and are explicitly excluded. `TOD_SavePackBootState_verified` complements prior types without replacing them; player summary now shows pack/boot names with unknown/sentinel IDs retained.

### Ordered segment names from the native loader and real level data

Native loader `39A328` looks up class `25000` at `39A4EC` through `51E260`, registering the resulting metadata pointer via `251458 → 651438`. Getter `651418` supplies that runtime metadata to the segment builder. Its members `+24/+28` provide ordered name pointers/count. Real `gameplay.dat` IGHW directories independently identify metadata class `25000` (44 bytes), pointer array `250C0` and bounded string pool `79C0`. The metadata's name-array reference and every name pointer occur in the relocation table; file-relative offsets become pointers on load. These are **asset offsets and runtime references**, not saved pointers or ELF file offsets.

`2D1A88` filters names with `2D1960` using the case-folded `gameplay_` prefix (`100261D0`). Passing names receive physical ordinals starting1 in loaded-array order. Reverse slot0 is `FFFFFFFF`; it has no named association, **not a padding verdict for saved slot0**. Hashing is case-sensitive over signed bytes with initial5381, wrapping uint32 multiply33/add, modulo49 (empty40). Bucket collisions overwrite earlier entries, and name lookup does not check string equality. No general native overflow guard was established; the bounded research reader rejects excess names rather than reproducing corruption.

Native folder getter `2D0880` uses nineteen pointers at `10062F7C` via TOC `89F154`, independently associating each level ID with its asset folder. The tool reads `/built/levels/<folder>/gameplay.dat` from each sibling `packed/levels/<folder>/level_cached.psarc`. All19 reference assets yielded **56 named saved-slot associations**, at most4 per level, with **zero observed hash collisions**. Each catalog records its SHA-256, logical/physical lengths, directory, string-pool/relocation bounds and save offsets. Examples: level0 `metropolis` slots1/2/3 are `gameplay_enemy`, `gameplay_sidescroll`, `gameplay_traversal`; level17 `meridian city` slots1/2/3 are `gameplay_enemy`, `gameplay_magcycle`, `gameplay_robowings`. Folder `fastoon_return` belongs to native level18, not a guessed alias of level3.

The program displays these as **qualified USA v02.00 reference names**, never names reconstructed from stale log order or stored strings in GAME.SAV. Reserved/unmatched slots and unmapped world19 remain unnamed, with raw data preserved. Runtime/cross-region asset changes remain possible. The actual snapshot's current segment records arezero; these names are native/asset provenance, not proof that a segment is active or completed.

Runtime catalog `101E8E68` (TOC `89F1AC`) is outside serialized state `101EFB20`:50 BE32 loaded-index→slot entries at`+0`,49 hash-bucket→slot entries at`+C8`, prefix initialization byte`+190`, cached prefix length`+198`, ten reverse entries at`+19C`, next ordinal at`+1C4`. `TOD_RuntimeSegmentNameCatalog_verified` and `TOD_GameplayNameMetadata_verified` document these runtime/asset objects without automatically applying types or treating them as save contents.

### Exact world initializer ownership and opaque bytes

Leaf `35DD98` zeroes each saved segment's bytes`00..2C` (45 bytes), including a BE32 store to word`28`, but does not write bytes`2D..2F`. World initializer `35DFA8` initializes ten such records, both256-byte object bitsets, and36 tail bytes`3E0..403`: **998 of1,032 bytes per world**. The remaining34 are ten3-byte segment tails plus four world bytes`404..407`; across20 worlds, **680 bytes are untouched by this initializer**.

Initial full-state snapshot/restore copies `35E710`/`35E508` include all `906F0` bytes and therefore these opaque bytes. This does not prove padding, globally-unused storage or retention from previous live state through every staging/restart lifecycle. Word`28`'s zero-store width does not establish a logical integer/float meaning. Actual200 word-`28` values and all inspected tails arezero; fixtures verify extreme/nonfinite bits and first/last slots are preserved.

The audit also reconciles previously known ownership: world`3C0..3DF` is the final32 bytes of the spawn-suppression bitset, and `3EC` is the **already-confirmed special-bolt collected mask**, not an unknown reward word. The reward report/UI and earlier notes are corrected. `TOD_SaveWorldLayout_combined_verified` combines the known segments, bitsets, reward caches/ladders, collectible mask and four flags, explicitly retaining opaque tail bytes rather than replacing earlier analyst types.

Reproduction (all read-only): [Inspect-TodHeroAux.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodHeroAux.py) and [Inspect-TodWorldAux.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodWorldAux.py) accept `--elf <exact ELF> --save <detached plaintext>`. [Inspect-TodSegmentConfig.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSegmentConfig.py) additionally accepts `--archive <original global_cached.psarc>` and reads sibling level archives in place. Matching tests check independent map/catalog reproduction, malformed directories/relocations/overflow, deliberate collisions, exact byte footprints and unchanged sources. No game code or scripts execute; no binary assets are tracked.

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

Segment members `+1C/+20/+24` cache the same three channels. `2CF4C8` computes totals only when cache-ready iszero, requires loaded `level_transitions`, and filters per-channel absolute-value flags. World `+3EC` is the independently mapped special-bolt collected mask, not reward state; only trailing `+404..407` remains opaque. The added `TOD_SaveWorldRewardState_verified` type is a reward-only view with unlisted members and does not replace prior types or apply itself to globals.

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

The earlier physical-name limitation is now resolved for the56 shipped reference associations above: `2D18C8` hashes nonempty names using33×accumulator modulo49 (empty returns40); `2D1928` reads runtime table memberC8, and `2D1A08` resolves loaded name pointers. The lookup itself does not establish a collision-free static dictionary. The native loader and real level-data proof above now supply56 qualified associations. Retained log order or script symbols still cannot name uncataloged slots or changed runtime assets.

Reproduction tools (all read-only; `--save` accepts the detached plaintext working copy):

- [Inspect-TodRewardChannels.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodRewardChannels.py): `--elf <exact ELF> --save <plaintext>`; matching test covers six checks.
- [Inspect-TodSaveTail.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSaveTail.py): same arguments; seven checks including raw nonfinite values, unsigned wrap, empty-input caveat and unchanged originals.
- [Inspect-TodSegmentBindings.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodSegmentBindings.py): same arguments, optional `--archive <global_cached.psarc>`; six checks including independent exports, hostile list bounds and literal compiled-script relationships.

## Files to use in IDA or Ghidra

- [Shared address map](maps/NativeMap.json): 1337 annotations, 118 imports, evidence, byte signatures and 42 structure definitions.
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

Before snapshot, `35E710 → 250758 → 24EAC8 → 24DAB8 → 12670 → 35C5B8` conditionally flushes the grid source; the first-context owner/subobject identity and active-versus-browsed buffer semantics are now confirmed in [grid lifecycle](#grid-browsing-synchronization-and-restore-trust-boundaries). This does not establish every pre-save dependency or atomic synchronization. Restore first copies the full staging bank, then applies sound-effects volume `114C8`, music volume `114CC`, voice volume `114C4`, and requests saved destination `906E8` through the qualified level-change routine. The setting names are independently registered; destination acceptance and runtime gates remain distinct. See [staging/load admission](#save-staging-and-deferred-load-application).

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

The auxiliary initializer `0x35DC80` clears currency and initializes the 32-word quick-select item-ID list at `0x284`, plus the three 23-word object-counter arrays at `0x304/0x360/0x3BC`: current count, recorded high-water count and positive additions. Later named-API passes establish those roles; initialization alone did not. Their runtime/UI lifecycle still has qualified limits. The restart-style routine `0x3CED40` copies and selectively resets state, including some records, then increments/clamps word `0x906EC`; **native engine replay terminology is now confirmed by the `-replay` CLI store; localized challenge-mode interpretation remains unverified**, not a confirmed editable field. These are analyst descriptions, not imported original function names.

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

These are **physical native slots**, not unconditional menu indices. When runtime getter `5BFE08() != 1`, menu count is 13 instead of 14 and IDs greater than 4 are incremented before storage/definition lookup. Availability has additional threshold-index adjustments for resulting IDs 7, 11 and 14. The runtime getter reads a word through a TOC pointer to `0x100D6478`; its language-selector meaning is now proven by the parser/system-init pass above; its current value is not taken from this save. No current menu availability is inferred in the inspector. Availability compares the saved score unsigned to the adjusted threshold; it does **not** test the saved state byte.

Menu setter `27008` first takes the low eight state bits, then accepts 1–8 or stores zero; raw setter `27A648` also accepts 1–8 or zero without an observed explicit ID bounds check. This global setter range is not each bonus's valid state-name range. Neither routine supplies safe editing permissions. All fourteen state bytes are zero in the supplied save despite score 750; zero alone does not mean locked, and nonzero is not enough to assert an active/on label.

Named `enable_all_cheats` (`2BBC90 → 27A678 → 35D480`) writes **840** to score `0x8708`, changes only zero state bytes to one, and preserves nonzero states. It does not update earned skill bits `0x8710`; therefore it must not be represented as “award all skill points.” New verified types `TOD_BonusDefinition_verified` and `TOD_SaveBonusState_verified` capture only these proven layouts, retaining opaque padding. Simple read-only Blueprints and Bonuses & cheats inspector views retain all raw evidence under Technical/details; unexpected set blueprint bits remain visible.

### Saved equipment history and compressed state blocks

[Inspect-TodStateStorage.py](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Inspect-TodStateStorage.py) reproduces the shared `state_storage` section with 50 byte guards, full ELF hash verification, three historical equipment words and a bounded native-format RLE decoder. [TestTodStateStorage.py](../../../../../Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodStateStorage.py) tests token truncation, native output boundaries, run clipping, malicious lengths, map reproduction and unchanged actual inputs. No decoded payload or game binary is embedded in the application; it computes only live read-only summaries from the session snapshot.

#### Equipment history, not dual-wield slots

Native callback `0x1F5570` reads inventory member `+0x188`, then hero member `+0x1A68` to reach serialized state. Initializer `0x1F5DB8` stores the hero argument at inventory `+0x188`; the already mapped hero initializer links `+0x1A68` to `0x101EFB20`. The callback's descriptor `0x8666D8` is referenced at table slot `0x84A4E0` for indirect dispatch. The [qualified state-entry dispatch](#equipment-history-dispatch-and-qualified-bonus-effects) is now confirmed separately; physical animation timing, all transition causes and gameplay acceptance remain unverified.

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
| `+08`, BE32 | Copied runtime generation/slot handle, independently proven above; not a stable game-wide UID or current validity |
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

Seven geometry checks cover unsigned rectangle extremes/last-group boundaries, nonboolean flags, retained unready fields, mask shape, exact class-source distinction, qualified projection/order and unchanged actual input. Original types remain intact; `TOD_SaveGridRectangleGroup_verified` supplies the refined field names. Later `grid_aux_fields` proves header`+08` is a copied runtime generation/slot handle; only`+0D..0F`, `+1D..1F` and final tail`+60DB` remain unnamed here.

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
| `+90` | BE float32 | Saved `8744` through `2CDBF8` result+0, accumulated adjusted scalar; units unverified |
| `+94` | BE float32 | Saved `8748` through `2CDBF8` result+4, accumulated reference scalar; units unverified |
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

No set bit is promoted to a mission/collectible checklist or completion percentage. Object-specific reset dependencies and controlled in-game before/after behavior remain unresolved. The later reward-channel pass above confirms the third channel reaches weapon XP through the native message consumers; it is not the hero XP balance at `418`. The later segment-configuration pass supplies56 qualified reference slot/name associations, not a catalog of arbitrary runtime objects.

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

Structural maps cover all file bytes, but many are deliberately opaque. Remaining work includes runtime per-world object-slot/name catalogs and object-specific lifecycle meanings, dynamic segment asset changes and uncataloged slots, timer units/reset-event cause, all equipment-state transition causes and gameplay equip acceptance, arena operation-dispatch list alias/current runtime table, player-facing reset-category names and category1 selection, any persisted checkpoint/health dependencies, additional snapshot synchronization, runtime grid geometry/world-axis naming and pixel-specific meanings, unnamed common copied-header bytes and final tail byte60DB. The5734 bank has confirmed initialization/increment mechanics, selectors2..7 and runtime expiration; this still does not make it named challenge failures or prove in-game counter semantics. Direct arena IDs/counters/configuration, object-bitset addressing and qualified load predicates, segment/log scalar provenance, RLE grammar, equipment history, fifteen options and two saved load-selection words are established above. All21 grid slots now have native map-label associations and partially verified volume headers/group flags, not a fully understood planet/mission completion map. Tail `0x906E4`, settings word `114C0` and settings bytes `114D6/114D7` remain semantically unresolved; first-person context is established without guessing an option label or polarity. The final word has native engine replay/restart context; localized game-mode naming and completed-playthrough semantics remain unverified. Runtime checkpoint positions are distinguished from saved fields rather than used to fill unknown save offsets.

One snapshot and a stripped executable cannot establish every script-defined key, valid value combination, reset dependency or in-game acceptance rule. Static code evidence, observed values, structural boundaries and gameplay verification are distinct. No completion percentage is assigned to this research, and no “100% compatibility” or “100% mapped” claim is made. Controlled before/after captures and an isolated runtime test environment are required for the remaining behavioral verification; original saves must be kept untouched.

## Import and reproduce

### Ghidra

Import the matching ELF using `PowerPC:BE:64:64-32addr`. Add `Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/Ghidra` to Script Manager's script directories, run `ImportTodMap.java`, and choose the JSON map. Look for `TOD_` labels and the `/RatchetClank/ToolsOfDestruction` data-type category. The unmapped third TOC base remains in JSON and is skipped as a standalone label.

The live Ghidra checks cover 1336 mapped annotations (the third TOC reference base is unmapped), 42 structure layouts, repeat-import idempotence and preservation of custom labels/comments. The portable suite verifies the original ELF hash, annotation bytes, serialization/configuration/catalog/progression/collectible/world-state/object/mission-list/bonus/state-storage/settings/arena/global-flag/gameplay-segment/world-object-bitset/reset-category/persistent-grid/grid-routing/grid-geometry/save-tail/reward-channel/mission-key/pack-boot/segment-loader/world-footprint/health-checkpoint/auxiliary-word/first-person-coupling/decryptor-context/segment-aggregate-gate/definition-handle/object-lifecycle/final-tail-ownership/arena-menu/equipment-dispatch/bonus-effect/arena-selector/inventory-reset/bonus-language-content/arena-operation-milestone/grid-synchronization/load-selection/segment-consumer/reset-admission/arena-api-boundary/weapon-progression/mission-mutation/snapshot-lifecycle/skill-award/armor-purchase/restart-bank/currency-mutation/object-publication/equipment-mutation instruction guards and ownership/acquisition relationships. Research decoders reproduce their bundled catalogs independently from the original ELF and check the actual USA plaintext snapshot. When research notes change, the importers retain older notes under `Previous ToD map` markers and keep one current note; custom prose is preserved. Shipped pause-menu evidence separately checks asset identity, four Lua function digests and17asset byte guards without executing scripts or treating asset offsets as ELF VAs. The reference-save inspector verifies unchanged hashes for every original file. Comparison-tool checks use generated fixtures, **not in-game captures**.

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
