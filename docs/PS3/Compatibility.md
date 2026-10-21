# PS3 compatibility

[Main README](../../README.md) · [Save handling](../Usage.md)

These are the title IDs recognized by the editor. Region recognition and software round trips are not proof of in-game acceptance for every release. Unknown IDs are rejected.

| Game | Data file | Recognized title IDs |
| --- | --- | --- |
| Ratchet & Clank | `USR-DATA` | NPUA80643, NPEA00385, NPJA40001 |
| Going Commando / Locked and Loaded | `USR-DATA` | NPUA80644, NPEA00386, NPJA40002 |
| Up Your Arsenal / Ratchet & Clank 3 | `USR-DATA` | NPUA80645, NPEA00387, NPJA40003 |
| Deadlocked / Gladiator | `USR-DATA` | NPUA80646, NPEA00388, NPEA00423, NPJA40004 |
| Tools of Destruction | `GAME.SAV` | BCUS98127, BCES00052, BCKS10016, BCJS30014, BCJS70012, BCKS10054, BCAS20045, BCJS70004, NPUA98153, NPEA90017, NPJA90035, NPHA20002, NPEA00452, NPUA80965 |
| Quest for Booty | `GAME.SAV` | BCUS98187, BLES00301, BCES00301, NPUA80145, NPEA00088 |
| A Crack in Time | `GAME.SAV` | BCUS98124, BCES00142, BCES00511, BCES00748, BCES00726, BCJS30038, BCKS10087, BCAS20098, NPEA00453, NPUA80966 |
| All 4 One | `GAME.SAV` | BCUS98175, BCES01142, BCES01141, BCAS20200, BCJS30081, NPEA00356, NPUA80695, NPEA90105, NPUA70181 |
| Full Frontal Assault / QForce | `GAME.SAV` | BCUS98380, NPUA80642, BCES01594, NPEA00378, XCES00001 |
| Nexus | `GAME.SAV` | NPUA80908, NPEA00457, BCUS99245, BCES01908, BCES01949, BCJS30092, NPJA00101 |

Disc trilogy collections use the individual game's save-directory ID, not the enclosing collection disc ID. PS2 Classics, PSP and Vita formats are outside this editor's scope.

The European BCES01503 trilogy's supplied RC1 RPCS3 save resolves to `NPEA00385` and matches the existing bolt layout. That matching European format also supports bounded ammo edits/refills, all 15 combat grants and eight-slot quick-select editing, based on native executable research. RC1 inspection remains read-only; see [sample evidence and limitations](RatchetAndClank1/SaveFormat.md). These mapped writes are not enabled for US/Japanese RC1 or RC2/RC3 formats.

## Format notes

- HD remasters use big-endian player blocks. The edited block's checksum is set to the PS3 disabled-checksum sentinel `FFFFFFFF`; other blocks are retained. This is not the PS2 checksum algorithm.
- All 4 One edits each character independently.
- QForce uses a named floating-point `player_bolts` record. Saves without that record, including some hub saves, cannot be edited. Edits are capped at 16,777,216 to avoid integer precision loss.
- PFD v3/v4 handling retains the original SFO binding hashes and re-signs changed tables. Console/disc private-key bindings are preserved, not recreated using fallback keys.

Actual encrypted trilogy samples and a decrypted RPCS3 A Crack in Time sample passed software edit/reopen checks. These tests do not establish acceptance on a console or in RPCS3 gameplay. See [test commands](../Development.md#tests).

## Sources

- [RatchetModding save backends](https://github.com/RatchetModding/slimseditor/blob/master/slimseditor/backends.py) and [game definitions](https://github.com/RatchetModding/slimseditor/tree/master/slimseditor/game)
- [Apollo PS3 patch database](https://github.com/bucanero/apollo-patches/tree/main/PS3)
- [flatz PFD structures](https://github.com/bucanero/pfd_sfo_tools/blob/master/pfdtool/src/pfd_internal.h) and [integrity routines](https://github.com/bucanero/pfd_sfo_tools/blob/master/pfdtool/src/pfd.c)
- [racman region catalog](https://github.com/MichaelRelaxen/racman), [RatchetHax](https://github.com/ParadoxEpoch/RatchetHax) and [RPCS3 digital-release reports](https://github.com/RPCS3/rpcs3/issues/16270)
