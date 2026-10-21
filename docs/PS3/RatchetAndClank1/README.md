# Ratchet & Clank (PS3 HD)

[PS3 research](../README.md) · [Compatibility](../Compatibility.md)

The first game in the PS3 Trilogy/Collection saves under its individual game ID. The supplied European BCES01503 trilogy sample uses `NPEA00385_RC1_SAVEDATA_A`, not a BCES01503 save profile. Existing bolt editing applies to this sample.

- [Save format and inspection](SaveFormat.md)
- [European reference sample, executable version unknown](NPEA00385/unknown/README.md)

The save inspector offers player summary, weapon/gadget unlock flags and ammo, raw quick-select IDs, player records, save layout, metadata and hex bytes. These views are read-only. Editing beyond bolts requires further validation; Tools of Destruction mappings do not apply.

The same inspection path recognizes `NPUA80643` and `NPJA40001`, with record-boundary checks before exposing fields. Only the European sample above was supplied for this investigation. RC2 and RC3 retain their existing currency support; this RC1 map does not decode them.
