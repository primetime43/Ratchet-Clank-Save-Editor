# RC1 PS3 save format

[Game index](README.md) · [European reference](NPEA00385/unknown/README.md)

## Scope and evidence

The supplied save comes from The Ratchet & Clank Trilogy, European disc `BCES01503`, in RPCS3. `PARAM.SFO` records `SAVEDATA_DIRECTORY=NPEA00385_RC1_SAVEDATA_A`, `TITLE=Ratchet & Clank`, `SUB_TITLE=The Ratchet & Clank Trilogy`, and an `RPCS3_BLIST` entry. No `TITLE_ID` or `PARAM.PFD` is present. Detection uses SFO fields rather than the folder's spelling or the launcher's collection ID.

This sample matches the existing PS3 RC1 currency profile. It establishes software read/edit/reopen compatibility for this save, not universal byte-for-byte equality with every individual PS3 release or in-game acceptance. No PS2/Vita format is inferred.

## Observed container

All offsets below are plaintext `USR-DATA` file offsets. Multi-byte game values are big endian.

| Offset | Sample value | Observation |
| --- | --- | --- |
| `0x0` | `0x153C` | Player payload length + 8 |
| `0x4` | `0x82A4` | Repeated world block stride, confirmed by the native writer/loader |
| `0x8` | `0x1534` | Player payload length |
| `0xC` | `0` | Stored player checksum; not verified by inspection |
| `0x10` | Record ID 0 | Start of player records |
| `0x153C` | `FFFFFFFF 00000000` | Record terminator |
| `0x1544` | Next block | End of player payload; all later bytes retained opaquely |

`USR-DATA` is `0xB0000` (720,896) bytes. A player record has a BE32 ID, BE32 payload length, payload bytes, then alignment bytes up to the next four-byte boundary. IDs are not necessarily contiguous or sorted: record 6 is absent and record 19 precedes record 14. There are 48 non-terminator records in the sample.

Record 10 has 37 bytes followed by three `0F` bytes. These alignment bytes are not assumed zero or disposable. Record 1010 has 150 bytes and two alignment bytes. Unknown records, headers and the complete tail must be preserved.

The inspector rejects duplicate IDs, truncated headers, out-of-bounds lengths, missing/invalid terminators and a mismatched bolt record. A recognized structure alone does not authorize additional edits. Optional mapped views also require their reference record lengths and offsets; failure leaves raw structural inspection available.

## Initial field map

| Record | Payload offset | Length | Interpretation |
| --- | --- | --- | --- |
| 1 | `0x24` | 4 | Current bolts; existing editable field |
| 9 | `0x11C` | 148 | Contains reference ammo words |
| 10 | `0x1B8` | 37 | Contains reference weapon/gadget unlock bytes |
| 11 | `0x1E8` | 37 | Uninterpreted; not treated as the same unlock flags |
| 13 | `0x22C` | 32 | Eight raw quick-select IDs, BE32 |

The ammo and unlock names/offsets come from [Slim's Editor RC1 definitions](https://github.com/RatchetModding/slimseditor/blob/master/slimseditor/game/rac.json). Its [PS3 backend](https://github.com/RatchetModding/slimseditor/blob/master/slimseditor/backends.py) selects the same RC1 IDs and big-endian decoding. These mappings are external reference evidence, not independently traced executable functions. Values are shown as stored; an unlock flag does not prove current usability, and quick-select IDs are not translated to guessed names. Unmapped ammo remains explicitly unmapped.

The current currency writer changes only BE32 bolts at `0x24` and the player checksum at `0xC` to `FFFFFFFF`, using the existing PS3 disabled-checksum convention. It does not rewrite every block checksum or apply the PS2 checksum routine. The inspector itself performs no checksum validation or writes.

## Native evidence and ammo edits

The supplied `BCES01503` trilogy's decrypted `RC1.ppu.elf` independently confirms all 48 player record descriptors, ammo at runtime `0x96C0AC`, ownership at `0x96C140`, and per-item capacity reads from a 24-byte definition table. The [native map](NPEA00385/unknown/ElfMap.md) records the serializer, loader, ammo consumer addresses and binary fingerprints; the inspector tool reproduces the embedded JSON from the original ELF.

The matching European `NPEA00385` format supports ammo editing/refill for 11 potential weapons. A weapon must already have ownership byte `1` and an existing ammo word inside its recovered reference limit. Writes change only the requested BE32 ammo words; Save All also applies the existing player checksum sentinel. Record 11, quick select, world data, statistics and alignment bytes are retained. Other RC1 regions remain inspection/currency-only for now.

## Reproducible validation

```powershell
dotnet run --project Tests/SaveEditor.RegressionTests.csproj -c Release -- --rc1
dotnet run --project Tests/SaveEditor.RegressionTests.csproj -c Release -- --rc1-save "path/to/NPEA00385_RC1_SAVEDATA_A"
```

The first command checks framing, alignment preservation, snapshot isolation, malformed data, optional mapping guards, ammo limits/ownership, invalid-input UI behavior, game switching, backup handling and later currency saves retaining committed ammo. The second also copies a supplied plaintext RPCS3 save into disposable directories, verifies automatic backups, edits bolts and refills eligible ammo, reopens the results, compares every byte against the explicitly allowed changes and verifies the source remains unchanged. No user save files are committed to the repository.

Before enabling more edits, validate each field with controlled before/after gameplay saves or the matching RC1 executable. In-game reload testing is still needed for acceptance of edited output.
