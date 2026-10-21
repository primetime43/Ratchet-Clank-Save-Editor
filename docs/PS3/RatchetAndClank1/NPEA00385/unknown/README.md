# NPEA00385 / executable version unknown

[RC1 index](../../README.md) · [Save format](../../SaveFormat.md)

Reference supplied from RPCS3 running the European `BCES01503` trilogy. The launcher identifies the collection disc; the save identifies the first individual game as `NPEA00385`. No executable or version metadata was examined, so this directory does not assert a particular build.

| Item | Observation |
| --- | --- |
| Save directory | `NPEA00385_RC1_SAVEDATA_A` |
| Data file | `USR-DATA`, 720,896 bytes |
| SHA-256 | `89E6BF8B7A9914E72359F8965BAF7747A1503C70DDC638A0AEAA1AF864F6199C` |
| Other files | `PARAM.SFO` (2,852), `ICON0.PNG` (131,072), `PIC1.PNG` (1,037,189 bytes) |
| Encryption | RPCS3 plaintext; no `PARAM.PFD` |
| Metadata location | Kyzil Plateau - Planet Veldin |
| Metadata play time | 00:44 |
| Bolts | 0 in metadata and BE32 at `0x24` |
| Player payload | `0x10..0x1543`, 48 records plus terminator |

The fingerprint identifies this observation without distributing the user's save. The test runner accepts a local path and verifies edits on a copy. Gameplay acceptance, exact executable functions and additional editable fields remain unverified.
