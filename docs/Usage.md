# Save handling and recovery

[Main README](../README.md) · [Supported regions](PS3/Compatibility.md)

## Opening and saving

Encrypted saves need the complete folder, including `PARAM.SFO`, `PARAM.PFD` and game data. Decrypted/RPCS3 saves may omit the PFD; an existing PFD is left unchanged. RPCS3's `RPCS3_BLIST` metadata is recognized automatically.

Use **Open Folder** (`Ctrl+O`) for encrypted saves and **Open Decrypted Folder** (`Ctrl+Shift+O`) for plaintext. Opening does not alter source files. **Save All** (`Ctrl+S`) commits pending changes in the original input format.

Numeric fields use text boxes: currency requires whole numbers; ammo and percentages accept a decimal point. Existing field limits still apply. Invalid entries are highlighted and block saving, including invalid pasted text.

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

**Game Save Editing → Mapped fields** supports the matching Tools of Destruction USA (`BCUS98127`) plaintext layout:

- Fifteen named settings, including volumes, inversion, subtitles, rumble and Sixaxis. Control scheme choices are 0 and 1.
- Ammo for already-owned combat weapons, bounded by shipped level/modifier definitions.
- Ammo for seven already-owned consumables: Zurkon, ConfusionGas, Slinkonator, MiniLeech, MaxiLeech, Morph and Copter. Groovitron and traversal gadgets remain read-only because of linked state.
- Combat weapon levels within the existing 1–5 or 6–10 tier. A change sets XP to that level's reference threshold. Increasing a level refills ammo; decreasing keeps it. The ammo page previews a refill and lets you override it. Inconsistent records stay read-only; this does not buy or grant another tier.
- **Refill supported ammo** and **Max weapon levels (current tier)** stage bulk changes using those same rules. Refills include supported owned consumables, skip uncertain/unowned records and use pending capacity upgrades. Max levels preserve explicit ammo overrides and do not buy Omega tiers. Other staged edits are retained; invalid numeric input blocks bulk actions.
- Missing ordinary ammo-capacity upgrades adjacent to installed nodes. Add-only: no removal or ownership grants. Adding refills to the new capacity; the ammo page allows an override. Raritanium is unchanged, so this is not a simulated purchase. Save and reopen to expose further adjacent nodes. Fully upgraded saves have no additions to offer.
- Ordinary damage, range, blast-radius, speed, duration, bolt/raritanium bonus and spawn-count upgrades follow the same add-only rules. These do not refill ammo or charge raritanium. Signed labels show shipped definitions, not final live stats; special nodes and unnamed effects are excluded.
- **Armor unlocks** and **Skin unlocks** grant missing ownership for the five armor entries and nine skins, including Jailbird. Add-only: owned values are preserved and cannot be removed. Grants do not equip items, spend currency, change armor vendor availability or enable challenge mode. **Appearance** can select existing owned items or ones granted in the same Save All operation; cancelling a grant clears any selection depending on it.
- **Hero XP** accepts whole numbers from **0–989,000** or the 98 shipped reference targets. Targets are zero-based config rows, not confirmed player-facing levels. Only the XP word is changed; level is calculated at runtime and health is not edited. Existing XP above the reference range stays unchanged unless you explicitly choose a bounded value; **Keep saved XP** cancels the edit. The upper limit is editor policy, not a native clamp or guaranteed maximum level. Runtime overrides and unpopulated rows98/99 are not inferred.
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

Fields with nonfinite, out-of-range or unrecognized inputs stay read-only unless a documented bounded replacement is offered. Arbitrary weapon XP or masks, special/unnamed upgrades, weapon/gadget ownership, story flags, unnamed counters and other progress remain inspection-only. Runtime-only space-combat stats cannot be edited from a save.

Changes are staged until **Save All** and use the existing backup/encryption checks. These edits are based on USA v02.00 research; the save layout check cannot identify every executable revision. In-game acceptance and live ammo capacities are not yet validated. Other games and regions keep currency editing only.

## Inventory previews

The **Inventory** tab shows saved Tools of Destruction weapons/gadgets, ownership, ammo, levels and equipped armor/skin. Search or show owned items only; **View details** exposes warnings and raw state. It is read-only and refreshes after Save All, not during staging. Names remain native config names.

**Load game icons…** accepts `PS3_GAME/USRDIR/packed/game/global_cached.psarc` from the researched USA build. Only its two fingerprinted HUD assets are read and cached under `PreviewAssets/PS3/ToolsOfDestruction/BCUS98127/v02.00` beside the executable. **Game UI artwork…** displays all208 decoded textures. **31 item icons** are mapped through compiled pause-menu assignments, named image references and byte-identical texture data; only Wrench remains unmapped. This maps menu artwork, not level-dependent alternate icons, a universal runtime getter or 3D models. Game assets are not bundled or committed.

**Save artwork…** shows available `ICON0.PNG` and `PIC1.PNG`, including for other games. Invalid artwork does not prevent opening a save.

## Inspection

Tools of Destruction Research and Save inspector views remain read-only. They keep raw values and unknown bytes; all pending edits are excluded from the inspection snapshot. Header inspection redacts private bindings and keys, but does not verify signatures or PNG CRCs.

See the [research wiki](README.md) for field definitions and known gaps.
