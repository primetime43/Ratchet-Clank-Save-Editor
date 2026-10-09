# Tools of Destruction — PS3 / USA / BCUS98127 / v02.00

## Findings and definitions

- [Executable map and evidence](ElfMap.md): save and non-save findings, import instructions and repeatable commands.
- [Native address/structure map](maps/NativeMap.json): 778 annotations, 118 imports and 21 structure definitions.
- [Weapon/gadget configuration definitions](maps/WeaponConfigs.json)
- [Shared save-format notes](../../SaveFormat.md): includes the supplied encrypted USA save and European plaintext sample, with evidence distinguished.

## Matching tools and tests

- [Research tools](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/README.md): native inspectors and IDA/Ghidra importers.
- [Native map regression tests](../../../../../Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodElfMap.py); neighboring tests cover progression, collectibles, world/object/mission state, bonuses, state storage, settings/load destinations and configurations.

The executable SHA-256 is `0EE9A8414C8FC182BC19FA2A523E6D050D0BE76138B3733AE515798D77D2468C`. Address maps and byte guards apply to that input only. These findings are partial and do not establish in-game edit safety or compatibility with another region/build.
