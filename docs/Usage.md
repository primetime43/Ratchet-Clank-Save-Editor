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
- Selection of already-owned armor and skins; no ownership is granted.
- Quick-select slots 0–23: Empty or owned items passing the native initial-flags filter. Slots 24–31 and unknown current values are retained; stored indices are not wheel positions. New duplicates are rejected, including duplicates in the last eight slots. Clear the old slot and assign the new one before saving to move an item.

Fields with nonfinite, out-of-range or unrecognized inputs stay read-only. XP/level, upgrade masks, ownership, story flags, counters and progress remain inspection-only because their dependencies are not fully reproduced.

Changes are staged until **Save All** and use the existing backup/encryption checks. These edits are based on USA v02.00 research; the save layout check cannot identify every executable revision. In-game acceptance and live ammo capacities are not yet validated. Other games and regions keep currency editing only.

## Inspection

Tools of Destruction Research and Save inspector views remain read-only. They keep raw values and unknown bytes; all pending edits are excluded from the inspection snapshot. Header inspection redacts private bindings and keys, but does not verify signatures or PNG CRCs.

See the [research wiki](README.md) for field definitions and known gaps.
