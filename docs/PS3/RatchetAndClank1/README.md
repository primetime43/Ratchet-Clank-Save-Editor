# Ratchet & Clank (PS3 HD)

[PS3 research](../README.md) · [Compatibility](../Compatibility.md)

The first game in the PS3 Trilogy/Collection saves under its individual game ID. The supplied European BCES01503 trilogy sample uses `NPEA00385_RC1_SAVEDATA_A`, not a BCES01503 save profile. Existing bolt editing applies to this sample.

- [Save format and inspection](SaveFormat.md)
- [European reference sample, executable version unknown](NPEA00385/unknown/README.md)
- [Native save serialization and ammo findings](NPEA00385/unknown/ElfMap.md)

**Game Save Editing → Mapped fields** offers six categories for the verified European `NPEA00385` format:

- **Weapon ammo**: edits for 11 potential owned weapons, plus **Refill owned weapon ammo**. Only canonical owned weapons with existing ammo inside the native reference limit are editable.
- **Weapon unlocks**: all 15 combat grants, including Suck Cannon, Morph-o-Ray and R.Y.N.O., with starting ammo where applicable and associated inventory/quick-select entries. Existing weapons are preserved.
- **Gold upgrades**: add the ten supported gold upgrades to already-owned weapons. Ordinary bolts and collectibles are preserved; available gold bolts can decrease because the game derives spending from upgrade flags.
- **Gadget unlocks**: Swingshot, Hydrodisplacer, Trespasser, Metal Detector, Hologuise, Gadgetron PDA, Map-o-matic, Bolt Grabber and Persuader. Handheld gadgets use a free quick-select slot; passive upgrades do not.
- **Equipment unlocks**: Heli-Pack, Thruster-Pack, Hydro-Pack, Sonic Summoner, O2 Mask, Pilot's Helmet, Magneboots, Grindboots and Hoverboard. Grants preserve selected equipment and do not occupy quick-select slots.
- **Quick select**: assign owned combat weapons or the six supported handheld gadgets, or clear any of the eight stored slots. New duplicates are rejected; unknown current IDs can be retained.

Changes remain staged until Save All and use the existing backup workflow. Save grants before editing their ammo, adding a gold upgrade or choosing a specific slot for the new item. Select a pack in-game after saving/reloading. Quest/race progress and equipped-item selection remain outside these edits.

The save inspector offers player summary, weapon/gadget unlock flags and ammo, raw quick-select IDs, player records, save layout, metadata and hex bytes. These views are read-only and exclude pending edits. Tools of Destruction mappings do not apply.

The same inspection path recognizes `NPUA80643` and `NPJA40001`, with record-boundary checks before exposing fields. Only the European sample above was supplied for this investigation. RC2 and RC3 retain their existing currency support; this RC1 map does not decode them.
