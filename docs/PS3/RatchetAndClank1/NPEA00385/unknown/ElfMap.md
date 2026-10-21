# European trilogy RC1 native save and ammo map

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

The world descriptor table starts at `0x7269A0`. The writer's first prefix word is the complete player block stride `0x153C`; its second is the repeated world block stride `0x82A4`. The player payload begins at save offset `0x10` and ends at `0x1544`; the first complete player block begins at `0x8`. The editor leaves all following world data unchanged.

| Player record | Runtime root | Save payload | Meaning established here |
| --- | --- | --- | --- |
| 9, 148 bytes | `0x96C0AC` | `0x11C` | 37 ammo words, indexed by item ID |
| 10, 37 bytes | `0x96C140` | `0x1B8` | Item ownership/unlock bytes |
| 11, 37 bytes | `0x96C165` | `0x1E8` | Independent per-item state; not changed by this feature |
| 13, 32 bytes | `0x96C1DC` | `0x22C` | Eight stored quick-select IDs; unchanged by ammo edits |

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

Each requested ammo change writes one BE32 at `0x11C + item_id * 4`. The refill action stages the same allowed edits for eligible owned weapons. It does not grant weapons, change quick select, alter record 11 or synthesize ammo-consumption statistics. Unknown keys, fractional/negative/excessive values and malformed layouts reject the complete batch before writes.

Save All uses the existing backup, isolated-candidate and encryption verification workflow, then refreshes the session baseline. Subsequent currency-only saves retain earlier ammo edits. As with existing bolt writes, the player checksum word is set to `FFFFFFFF`. The supplied plaintext sample passed exact software byte comparisons and reopen checks on a disposable copy; gameplay reload acceptance remains unverified.

## Reproduction

The [native inspector](../../../../../Tools/PS3/RatchetAndClank1/NPEA00385/unknown/Inspect-Rc1Native.py) extracts the map directly from the original ELF and rejects mismatched binaries. The [native tests](../../../../../Tests/PS3/RatchetAndClank1/NPEA00385/unknown/TestRc1Native.py) compare it to the bundled JSON and check corrupted-input rejection. The [Ghidra trace script](../../../../../Tools/PS3/RatchetAndClank1/NPEA00385/unknown/Ghidra/TraceRc1Ammo.java) reproduces the selected decompilations with the correct TOC and hash guard.

```powershell
python -B Tools/PS3/RatchetAndClank1/NPEA00385/unknown/Inspect-Rc1Native.py --elf "path/to/RC1.ppu.elf"
python -B Tests/PS3/RatchetAndClank1/NPEA00385/unknown/TestRc1Native.py --elf "path/to/RC1.ppu.elf" -v
dotnet run --project Tests/SaveEditor.RegressionTests.csproj -c Release -- --rc1-save "path/to/RPCS3-save-folder"
```
