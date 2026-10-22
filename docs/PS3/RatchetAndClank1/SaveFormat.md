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
| `0x1544` | Next block | End of player payload; first of twenty world blocks |

`USR-DATA` is `0xB0000` (720,896) bytes. A player record has a BE32 ID, BE32 payload length, payload bytes, then alignment bytes up to the next four-byte boundary. IDs are not necessarily contiguous or sorted: record 6 is absent and record 19 precedes record 14. There are 48 non-terminator records in the sample.

Record 10 has 37 bytes followed by three `0F` bytes. These alignment bytes are not assumed zero or disposable. Record 1010 has 150 bytes and two alignment bytes. Unknown records, alignment bytes and the reserved tail are preserved. Gold-bolt edits change only their explicitly mapped world bytes and affected checksum words.

The inspector rejects duplicate IDs, truncated headers, out-of-bounds lengths, missing/invalid terminators and a mismatched bolt record. A recognized structure alone does not authorize additional edits. Optional mapped views also require their reference record lengths and offsets; failure leaves raw structural inspection available.

## Initial field map

| Record | Payload offset | Length | Interpretation |
| --- | --- | --- | --- |
| 1 | `0x24` | 4 | Current bolts; existing editable field |
| 9 | `0x11C` | 148 | Contains reference ammo words |
| 10 | `0x1B8` | 37 | Contains reference weapon/gadget unlock bytes |
| 11 | `0x1E8` | 37 | Per-item flag set by ordinary grants, independently of ownership |
| 12 | `0x218` | 12 | Acquisition entries: flagged item IDs; `FF` marks an empty byte |
| 13 | `0x22C` | 32 | Eight raw quick-select IDs, BE32 |
| 30 | `0x11D8` | 40 | Gold-upgrade bytes indexed by item ID; ten combat entries supported |

The ammo and unlock names/offsets come from [Slim's Editor RC1 definitions](https://github.com/RatchetModding/slimseditor/blob/master/slimseditor/game/rac.json). Its [PS3 backend](https://github.com/RatchetModding/slimseditor/blob/master/slimseditor/backends.py) selects the same RC1 IDs and big-endian decoding. These mappings are external reference evidence, not independently traced executable functions. Values are shown as stored; an unlock flag does not prove current usability, and quick-select IDs are not translated to guessed names. Unmapped ammo remains explicitly unmapped.

The current currency writer changes only BE32 bolts at `0x24` and the player checksum at `0xC` to `FFFFFFFF`, using the existing PS3 disabled-checksum convention. It does not rewrite every block checksum or apply the PS2 checksum routine. The inspector itself performs no checksum validation or writes.

## Native evidence and ammo edits

The supplied `BCES01503` trilogy's decrypted `RC1.ppu.elf` independently confirms all 48 player record descriptors, ammo at runtime `0x96C0AC`, ownership at `0x96C140`, and per-item capacity reads from a 24-byte definition table. The [native map](NPEA00385/unknown/ElfMap.md) records the serializer, loader, ammo consumer addresses and binary fingerprints; the inspector tool reproduces the embedded JSON from the original ELF.

The matching European `NPEA00385` format supports ammo editing/refill for 11 potential weapons. A weapon must already have ownership byte `1` and an existing ammo word inside its recovered reference limit. Writes change only the requested BE32 ammo words; Save All also applies the existing player checksum sentinel. Record 11, quick select, world data, statistics and alignment bytes are retained. Other RC1 regions remain inspection/currency-only for now.

Separate **Weapon unlocks** and **Quick select** categories support all 15 combat grants and edits to the eight stored quick-select words. A new grant sets ownership and the independent record-11 flag, raises ammo to its starting amount, updates the bounded acquisition list when required, and uses a free quick-select slot. Explicit slot edits take precedence. Suck Cannon, Morph-o-Ray and R.Y.N.O. are included after a complete memory-effect audit of their runtime notification path. See the [grant evidence and exact boundaries](NPEA00385/unknown/ElfMap.md#weapon-grants).

**Gold upgrades** adds the ten native vendor upgrades to already-owned weapons by setting only their record-30 bytes. Upgrades are add-only, with canonical flags required; save new weapon grants first. No currency or collectible records are written, but the game derives available gold bolts by subtracting four per upgrade. See [native gold-upgrade evidence](NPEA00385/unknown/ElfMap.md#gold-upgrades).

**Gadget unlocks** grants six handheld gadgets and three passive upgrades using the same ownership/grant banks. Handheld items use a free quick-select word; passive items do not. Ammo and acquisition-list bytes are preserved, including unusual unused ammo values. No mission, movement-equipment or equipped-item state is changed. Quick select offers owned supported handheld gadgets after saving. See [gadget evidence and limits](NPEA00385/unknown/ElfMap.md#gadget-grants).

**Equipment unlocks** grants nine packs/headgear/boots/hoverboard entries using only their ownership and ordinary grant flags. Ammo, acquisition entries, quick select, world state and both saved equipment-selection records are retained. Select a pack in-game after saving/reloading; these grants do not complete associated quests or races. See [equipment evidence and limits](NPEA00385/unknown/ElfMap.md#equipment-grants).

**Gold bolts** adds collection flags for all forty shipped pickups. World record3003 has four reserved bytes at block-relative `0x8024`, indexed by world and pickup slot. All twenty world block layouts must match. Only the forty indices confirmed against the native count table and actual PAL level assets are writable; unused/unknown flags are retained. Individual collection, planet filtering and collect-all requests share staged previews of collected/spent/available gold bolts. Changed world checksum words receive `FFFFFFFF`; no-op/untouched world words remain unchanged. See [gold-bolt evidence](NPEA00385/unknown/ElfMap.md#gold-bolt-collection).

**Nanotech** adds Premium and Ultra upgrades by changing record5 bytes4/5 (save `0x5C`/`0x5D`) and the BE32 capacity in record19 (`0x254`). Supported states are `(0,0,4)`, `(1,0,5)` and `(1,1,8)`; upgrades are add-only and direct Ultra also installs Premium. Unknown/inconsistent states are preserved and disable only nanotech editing. Current runtime health is initialized from this saved capacity and is not independently serialized. Currency, world data, progression and trophy state are preserved. See [nanotech evidence](NPEA00385/unknown/ElfMap.md#nanotech-upgrades).

## Reproducible validation

```powershell
dotnet run --project Tests/SaveEditor.RegressionTests.csproj -c Release -- --rc1
dotnet run --project Tests/SaveEditor.RegressionTests.csproj -c Release -- --rc1-save "path/to/NPEA00385_RC1_SAVEDATA_A"
```

The first command checks framing, alignment preservation, snapshot isolation, malformed data, ammo limits/ownership, grant allowlists/coupled writes, nanotech prerequisites/capacity, acquisition-list bounds, slot moves/swaps, hidden invalid input, game switching, backups and later currency saves retaining committed mapped edits. The second also copies a supplied plaintext RPCS3 save into disposable directories, verifies backups, exercises all mapped categories including Ultra Nanotech, reopens the results, compares every byte against independently expected changes and verifies the source remains unchanged. No user save files are committed to the repository.

Before enabling more edits, validate each field with controlled before/after gameplay saves or the matching RC1 executable. In-game reload testing is still needed for acceptance of edited output.
