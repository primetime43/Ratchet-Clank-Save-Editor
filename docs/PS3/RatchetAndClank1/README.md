# Ratchet & Clank (PS3 HD)

[PS3 research](../README.md) · [Compatibility](../Compatibility.md)

The first game in the PS3 Trilogy/Collection saves under its individual game ID. The supplied European BCES01503 trilogy sample uses `NPEA00385_RC1_SAVEDATA_A`, not a BCES01503 save profile. Existing bolt editing applies to this sample.

- [Save format and inspection](SaveFormat.md)
- [European reference sample, executable version unknown](NPEA00385/unknown/README.md)
- [Native save serialization and ammo findings](NPEA00385/unknown/ElfMap.md)

**Game Save Editing → Mapped fields** now offers ammo edits for 11 potential owned weapons in the verified European `NPEA00385` format, plus **Refill owned weapon ammo**. Only canonical owned weapons with existing ammo inside the native reference limit are editable. Changes remain staged until Save All and use the existing backup workflow. Grants, progression and quick-select edits require further research.

The save inspector offers player summary, weapon/gadget unlock flags and ammo, raw quick-select IDs, player records, save layout, metadata and hex bytes. These views are read-only and exclude pending edits. Tools of Destruction mappings do not apply.

The same inspection path recognizes `NPUA80643` and `NPJA40001`, with record-boundary checks before exposing fields. Only the European sample above was supplied for this investigation. RC2 and RC3 retain their existing currency support; this RC1 map does not decode them.
