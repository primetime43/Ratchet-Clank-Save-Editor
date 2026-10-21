# Save handling and recovery

[Main README](../README.md) · [Supported regions](PS3/Compatibility.md)

Encrypted saves and metadata tools require the **Microsoft Visual C++ 2010 SP1 Redistributable (x86)**, even on 64-bit Windows. Install `vcredist_x86.exe` from [Microsoft](https://www.microsoft.com/en-us/download/details.aspx?id=26999). The release includes the .NET runtime; this native save-tool prerequisite is installed separately.

## Appearance

Use **View → Theme** to choose **System**, **Light**, or **Dark**, then restart the editor to apply the choice. The preference is remembered for your Windows account. The default is **System**, which reads the Windows app color setting at launch; changes to that Windows setting also require restarting the editor. Native dark mode requires Windows 11 and is disabled by Windows contrast themes.

## Opening and saving

Encrypted saves need the complete folder, including `PARAM.SFO`, `PARAM.PFD` and game data. Decrypted/RPCS3 saves may omit the PFD; an existing PFD is left unchanged. RPCS3's `RPCS3_BLIST` metadata is recognized automatically.

Use **Open Folder** (`Ctrl+O`) for encrypted saves and **Open Decrypted Folder** (`Ctrl+Shift+O`) for plaintext. Opening does not alter source files. **Save All** (`Ctrl+S`) commits pending changes in the original input format.

Numeric fields use text boxes: currency and RC1 ammo require whole numbers; Tools of Destruction ammo and percentages accept a decimal point. Existing field limits still apply. Invalid entries are highlighted and block saving, including invalid pasted text.

Manually decrypted console saves must be re-encrypted through their original save-management workflow before console transfer. Do not mix plaintext game data with encrypted metadata.

## Backups and recovery

Opening creates a full backup before decryption; saving creates another before replacement. Each uses a unique directory under `Backups` beside the executable. If the opening backup fails, the editor does not open the save.

**Open Backups** opens that location. **Back Up Save** creates an extra manual backup. To restore, close the editor and copy every file from a chosen backup into the original folder.

Encryption output is checked by decrypting a temporary copy and comparing game data. Failed encryption leaves originals untouched. Failed file replacement attempts rollback, but multi-file replacement is not atomic; keep the backup for interruption recovery.

If another application changes the source folder while it is open, reopen it before saving.

## Metadata actions

**Update Integrity** applies to encrypted saves. **Remove Copy Protection** applies only to decrypted saves. Actions remain pending until Save All.

Changing encrypted metadata needs original signing keys that the editor does not have. Account resigning is not supported.

## Mapped-field edits

For European RC1 (`NPEA00385`), **Game Save Editing → Mapped fields** offers **Weapon ammo**, **Weapon unlocks**, **Gold upgrades**, **Gadget unlocks**, **Equipment unlocks** and **Quick select**. Ammo edits and **Refill owned weapon ammo** use native reference limits. The weapon unlock page supports all 15 combat weapons, including Suck Cannon, Morph-o-Ray and R.Y.N.O.; it fills a free quick-select slot when possible without spending bolts. R.Y.N.O. starts with 25 ammo, with a reference maximum of 50. Suck Cannon and Morph-o-Ray do not receive a manual ammo refill. Existing owned weapons are unchanged. Save a grant before editing that weapon's ammo, adding its gold upgrade or assigning its specific slot.

**Gold upgrades** supports Suck Cannon, Bomb Glove, Devastator, Blaster, Pyrocitor, Mine Glove, Tesla Claw, Glove of Doom, Morph-o-Ray and Decoy Glove. Only already-owned weapons with canonical upgrade flags appear; installed upgrades cannot be removed. Adding an upgrade preserves ordinary bolts, collected gold bolts, ammo and equipment. The game counts four gold bolts spent per upgrade, so its available balance may fall to zero. No currency prerequisite is enforced by the editor. Changes remain staged until Save All.

**Gadget unlocks** grants Swingshot, Hydrodisplacer, Trespasser, Metal Detector, Hologuise, Gadgetron PDA, Map-o-matic, Bolt Grabber and Persuader. The first six use a free quick-select slot; the last three are passive upgrades and do not occupy slots. Grants are add-only and preserve existing owned items. Save first to assign a particular slot. They preserve currency, equipped items and mission state; acquiring a gadget does not mark its associated mission complete.

**Equipment unlocks** grants Heli-Pack, Thruster-Pack, Hydro-Pack, Sonic Summoner, O2 Mask, Pilot's Helmet, Magneboots, Grindboots and Hoverboard. Grants are add-only and preserve currency, ammo, health and current equipment selection. Equipment does not occupy quick-select slots. Choose a pack in-game after saving/reloading. Ownership does not complete the item's associated quest, race or world pickup, and gameplay prerequisites still apply.

RC1 quick-select choices include owned combat weapons, the six supported handheld gadgets and Empty. Clear an item's old slot before assigning it elsewhere; new duplicates are rejected. Unknown current values can be retained or cleared. Pending ammo survives category switches, and invalid text blocks saving and other staging actions. **Save All** commits the complete batch with a backup. Quest/race progress, current equipment selections and statistics are preserved. See the [native evidence and limitations](PS3/RatchetAndClank1/NPEA00385/unknown/ElfMap.md).

**Game Save Editing → Mapped fields** supports the matching Tools of Destruction USA (`BCUS98127`) plaintext layout:

- Fifteen named settings, including volumes, inversion, subtitles, rumble and Sixaxis. Control scheme choices are 0 and 1.
- Ammo for already-owned combat weapons, bounded by shipped level/modifier definitions.
- **Weapon unlocks** grants missing combat weapons (IDs1–15), including Ryno, at level1 with zero XP and starting ammo. Each new grant increments the saved acquisition counter once and adds the weapon to the first empty quick-select slot if it is not already assigned. You can choose a specific slot in the same batch; occupied slots and the last eight slots are preserved. No currency, Omega tier, consumable, story gadget, blueprint, upgrade or skill award is granted. Existing weapons are untouched; uncertain unowned records are read-only. Save first to expose the new weapon's ammo/level editors. Cancelling a grant clears staged slot assignments that depend on it.
- **Consumable unlocks** grants missing Zurkon, ConfusionGas, Slinkonator, MiniLeech, MaxiLeech, Morph and Copter. Adds one ammo unit up to capacity, sets zero XP/level and increments the acquisition counter once; save before editing ammo further. Uses the same quick-select/cancellation rules as combat grants. A new consumable also sets the native **HERO_HAS_TWO_ITEMS** flag when two items in that class are owned (Groovitron counts but cannot be granted here). Existing items are not refilled; no currency or skill award is granted.
- **Equipment unlocks** grants missing **Charge Boots** and **Treasure Mapper**. Writes current count1, raises historical peak if needed and increments positive additions once, rejecting overflow. Existing nonzero counts are retained. No boot-type, weapon counter, quick-select, story flag, skill or world pickup edits; gameplay usability remains untested.
- Ammo for seven already-owned consumables: Zurkon, ConfusionGas, Slinkonator, MiniLeech, MaxiLeech, Morph and Copter. Groovitron and traversal gadgets remain read-only because of linked state.
- Combat weapon levels within the existing 1–5 or 6–10 tier. A change sets XP to that level's reference threshold. Increasing a level refills ammo; decreasing keeps it. The ammo page previews a refill and lets you override it. Inconsistent records stay read-only; this does not buy or grant another tier.
- **Omega promotions** promotes verified, already-owned level-5 combat weapons to **Omega level 6**. Requires an existing nonzero replay/Challenge Mode word; the editor does not enable that mode. Sets the matching XP threshold and refills ammo using the promoted tier and any staged upgrades, including RYNO's different tier capacity. **Weapon ammo** previews the new limit and permits an explicit override. Save the promotion before changing that weapon's level; levels6–10 become available after saving. Currency, ownership, modifier bits, acquisition counters, quick-select slots and replay state are preserved unless separately edited. Already-Omega requests are no-ops; malformed records and weapons below level5 stay unavailable. This applies the researched saved-state bridge without executing vendor payment or runtime callbacks. In-game acceptance remains untested.
- **Promote all eligible weapons to Omega**, on the **Omega promotions** page, stages those same promotions in one action. It skips unowned, already-Omega, uncertain and below-level-5 weapons, and preserves staged level decreases by skipping their weapons. Other staged edits and explicit ammo overrides are retained. Invalid numeric input blocks the action; the button is disabled when no saved weapons qualify. Promotions remain pending until **Save All**.
- **Refill supported ammo** and **Max weapon levels (current tier)** stage bulk changes using those same rules. Refills include supported owned consumables, skip uncertain/unowned records and use pending capacity upgrades. Max levels preserve explicit ammo overrides and do not buy Omega tiers. Other staged edits are retained; invalid numeric input blocks bulk actions.
- Missing ordinary ammo-capacity upgrades adjacent to installed nodes. Add-only: no removal or ownership grants. Adding refills to the new capacity; the ammo page allows an override. Raritanium is unchanged, so this is not a simulated purchase. Save and reopen to expose further adjacent nodes. Fully upgraded saves have no additions to offer.
- **Weapon upgrades** now covers all189 purchasable nodes across fifteen combat weapons, including fourteen designated specials and weapon-specific parameters. Individual ordinary nodes require an installed neighbor; individual specials require all positive neighbors. Blank `MOD_SPECIAL` values are Boolean saved-mask switches, not guessed numeric effects. Signed labels remain shipped references, not final live stats.
- Choose **Unlock all upgrades** beside one weapon's complete grid, or **Unlock all owned weapon upgrades** for all supported owned weapons. Complete grids include prerequisite nodes in one Save All, preserve the start bit and never grant weapon ownership or another level tier. Capacity changes refill ammo; explicit ammo overrides are retained. Raritanium and unrelated progress are unchanged. RYNO's central icon is its implicit starting node, not a purchasable special.
- **Armor unlocks** and **Skin unlocks** grant missing ownership for the five armor entries and nine skins, including Jailbird. Add-only: owned values are preserved and cannot be removed. Grants do not equip items, spend currency, change armor vendor availability or enable challenge mode. **Appearance** can select existing owned items or ones granted in the same Save All operation; cancelling a grant clears any selection depending on it.
- **Hero XP** includes a **Ratchet progression** panel accepting whole numbers from **0–989,000** or the 98 shipped reference targets. Each target shows XP and reference maximum HP; saved and proposed reference rows/HP are shown separately, along with XP remaining to the next reference target. Custom XP between thresholds uses the preceding reference row. Targets are zero-based config rows, not confirmed player-facing levels. HP values come from shipped reference data, not observed current health or verified in-game maximum health. Only the XP word is changed; level is calculated at runtime and health is not edited. Existing XP above the reference range stays unchanged unless you explicitly choose a bounded value; its row/HP preview is unavailable. **Keep saved XP** cancels the edit. The upper limit is editor policy, not a native clamp or guaranteed maximum level. Runtime overrides and unpopulated rows98/99 are not inferred.
- **Gold bolts** offers a planet selector and local-ID checklist. Editing is limited to IDs0–(shipped count−1), not all32 possible native bits; physical pickup locations are not mapped. Unknown bits, zero-total worlds and slot19 are preserved. Spent bolts are never changed: removals cannot make the available balance negative, and an already-invalid spent balance stays inspection-only. Add before removing when staging a swap. A new bolt completing all native planet counts awards **GOLDEN (+40 points)** and, if all ordinary skills are earned, **HARDCORE (+20)**. Earned awards/points remain after removals; no-ops do not repair missing awards. The preview counts unknown bits as the native code does. Save new linked awards separately from **Unlock bonuses**.
- Bolt multiplier from 1–20×, including fractional values, under **Rewards**. Requires an existing nonzero replay/restart word and valid multiplier; it does not enable replay mode. The game can reset it after sampled health loss, so this is not a permanent multiplier lock.
- Hero head size, enemy head size, developer-commentary request, James Zurkon and mirror mode, requiring existing skill scores of 50, 100, 200, 400 and 500 respectively. Commentary also requires the game's supported runtime language, which is not stored here; On does not guarantee playback. Unknown saved states stay read-only; points and earned bits are unchanged. Zurkon Off cannot override its separate runtime flag.
- **Arena challenge stats** edits recorded wins for already-won challenges, from 1–2,147,483,647. Never-won challenges and signed-negative counters remain read-only; first-time victories must happen in-game so gadget rewards and story updates are not skipped. Counts can change repeat payouts and menu ordering. No currency, inventory, story flags or skill awards are granted; names are shipped config descriptions.
- **Decryptor stats** edits the retained win counter and Sixaxis-enabled losses since success as whole numbers from 0–4,294,967,295, plus the valid spark-speed multiplier from 0.6–1. These can affect Decryptor adaptation; wins are not guaranteed lifetime totals, and losses are not all attempts or deaths. Counter edits do not simulate success or reset the other fields. The game can subsequently update/reset these values or wrap the counters.
- Quick-select slots 0–23: Empty or owned items passing the native initial-flags filter. Slots 24–31 and unknown current values are retained; stored indices are not wheel positions. New duplicates are rejected, including duplicates in the last eight slots. Clear the old slot and assign the new one before saving to move an item.
- **Skill awards**: check missing skills to add their earned bits and native weighted points. Earned skills cannot be removed. Adding the last missing skill among IDs0–58 also awards HARDCORE and its20 points. The checklist previews the score and any GOLDEN/HARDCORE awards supplied by staged gold bolts. Labels are formatted native identifiers, not localized achievement names. Existing boosted/mismatched scores and unknown bits are preserved, overflow is rejected, and producer progress/runtime notifications are not simulated. Save separately from **Unlock bonuses**, which replaces the score with840. An unchanged or duplicate award does not repair an existing missing HARDCORE bit.

**Developer helpers** adds two optional one-shot actions, staged until Save All:

- **Grant all native blueprints** ORs the native 13-bit mask, retaining other bits. It does not grant weapons or assign blueprint bits to guessed planets.
- **Unlock bonuses (native helper)** sets the weighted bonus score to **840**, even if it was higher, and replaces each zero bonus state with 1. Nonzero states and earned skill bits are untouched. This can request multiple effects; it is not all skill awards. Run it separately from skill awards and bonus selections, then revisit their page after saving.

These reproduce confirmed saved writes, not live calls into the game; in-game acceptance of these edits remains untested. [Developer research findings](PS3/ToolsOfDestruction/BCUS98127/v02.00/ElfMap.md#developer-helpers-and-lua-debug) are retained, but the experimental runtime tools have been removed. The save editor does not patch the game executable.

Fields with nonfinite, out-of-range or unrecognized inputs stay read-only unless a documented bounded replacement is offered. Arbitrary weapon XP or masks outside the defined upgrade graph, Groovitron variants, story-gadget ownership, story flags, unnamed counters and other progress remain inspection-only. Runtime-only space-combat stats cannot be edited from a save.

Changes are staged until **Save All** and use the existing backup/encryption checks. The Tools of Destruction edits above are based on USA v02.00 research; the save layout check cannot identify every executable revision. In-game acceptance and live ammo capacities are not yet validated. Formats without mapped-edit support keep currency editing.

## Inventory previews

The **Inventory** tab shows saved Tools of Destruction weapons/gadgets, ownership, ammo, levels and equipped armor/skin. Search or show owned items only; **View details** exposes warnings and raw state. It is read-only and refreshes after Save All, not during staging. Names remain native config names.

**Load game icons…** accepts `PS3_GAME/USRDIR/packed/game/global_cached.psarc` from the researched USA build. Only its two fingerprinted HUD assets are read and cached under `PreviewAssets/PS3/ToolsOfDestruction/BCUS98127/v02.00` beside the executable. **Game UI artwork…** displays all208 decoded textures. **31 item icons** are mapped through compiled pause-menu assignments, named image references and byte-identical texture data; only Wrench remains unmapped. This maps menu artwork, not level-dependent alternate icons, a universal runtime getter or 3D models. Game assets are not bundled or committed.

**Save artwork…** shows available `ICON0.PNG` and `PIC1.PNG`, including for other games. Invalid artwork does not prevent opening a save.

## Inspection

Tools of Destruction Research and Save inspector views remain read-only. They keep raw values and unknown bytes; all pending edits are excluded from the inspection snapshot. Header inspection redacts private bindings and keys, but does not verify signatures or PNG CRCs.

See the [research wiki](README.md) for field definitions and known gaps.
