# Ratchet & Clank Save Editor

Windows editor for PS3 Ratchet & Clank saves. Edit currency, back up saves, export artwork and inspect save data. European RC1 supports ammo, weapon/gadget/equipment grants, gold bolts/upgrades and quick-select edits; Tools of Destruction USA supports selected mapped-field edits.

## Use

1. Copy the complete save folder to your PC.
2. Choose **File → Open Folder** for encrypted saves, or **Open Decrypted Folder (RPCS3)** for plaintext saves.
3. Edit currency or supported mapped fields in **Game Save Editing**.
4. Choose **File → Save All**, then transfer the complete folder back.

Backups are created on opening and before saving, under `Backups` beside the executable. Keep the editor in a writable folder. Decrypted console saves must be re-encrypted before transfer; account resigning is not supported.

## Supported games

| Game | Editable currency |
| --- | --- |
| Ratchet & Clank | Bolts |
| Going Commando / Locked and Loaded | Bolts, raritanium |
| Up Your Arsenal / Ratchet & Clank 3 | Bolts |
| Deadlocked / Gladiator | Bolts |
| Tools of Destruction | Bolts, raritanium |
| Quest for Booty | Bolts |
| A Crack in Time | Bolts |
| All 4 One | Bolts for each character |
| Full Frontal Assault / QForce | Bolts; save on a planet first |
| Nexus | Bolts, raritanium |

Support is limited to listed PS3 formats and [regions](docs/PS3/Compatibility.md). It does not cover every save field or guarantee in-game acceptance for every release.

PS3 Trilogy/Collection saves use the individual game's save ID. [RC1 support](docs/PS3/RatchetAndClank1/README.md) includes bolt editing, ammo edits/refills, all 15 combat grants, nine gadget/passive grants, nine equipment grants, forty gold-bolt collection flags, ten gold upgrades and eight-slot quick-select editing for the European `NPEA00385` layout, alongside read-only inspection.

## Documentation

- [Save handling and recovery](docs/Usage.md)
- [Build, publish and test](docs/Development.md)
- [Research wiki](docs/README.md)

## Credits

Originally released in 2013 by primetime43, with help from Red_EyeX32. Bundled `pfdtool` and `sfopatcher` by flatz. [License](LICENSE).
