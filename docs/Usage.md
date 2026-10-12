# Save handling and recovery

[Main README](../README.md) · [Supported regions](PS3/Compatibility.md)

## Opening and saving

Encrypted saves need the complete folder, including `PARAM.SFO`, `PARAM.PFD` and game data. Decrypted/RPCS3 saves may omit the PFD; an existing PFD is left unchanged. RPCS3's `RPCS3_BLIST` metadata is recognized automatically.

Use **Open Folder** (`Ctrl+O`) for encrypted saves and **Open Decrypted Folder** (`Ctrl+Shift+O`) for plaintext. Opening does not alter source files. **Save All** (`Ctrl+S`) commits pending changes in the original input format.

Manually decrypted console saves must be re-encrypted through their original save-management workflow before console transfer. Do not mix plaintext game data with encrypted metadata.

## Backups and recovery

Opening creates a full backup before decryption; saving creates another before replacement. Each uses a unique directory under `Backups` beside the executable. If the opening backup fails, the editor does not open the save.

**Open Backups** opens that location. **Back Up Save** creates an extra manual backup. To restore, close the editor and copy every file from a chosen backup into the original folder.

Encryption output is checked by decrypting a temporary copy and comparing game data. Failed encryption leaves originals untouched. Failed file replacement attempts rollback, but multi-file replacement is not atomic; keep the backup for interruption recovery.

If another application changes the source folder while it is open, reopen it before saving.

## Metadata actions

**Update Integrity** applies to encrypted saves. **Remove Copy Protection** applies only to decrypted saves. Actions remain pending until Save All.

Changing encrypted metadata needs original signing keys that the editor does not have. Account resigning is not supported.

## Inspection

Tools of Destruction research and save views are read-only. They keep raw values and unknown bytes; pending currency edits are excluded from the inspection snapshot. Header inspection redacts private bindings and keys, but does not verify signatures or PNG CRCs.

See the [research wiki](README.md) for field definitions and known gaps.
