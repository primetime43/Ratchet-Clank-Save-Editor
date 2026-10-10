# Tools of Destruction — PS3 / USA / BCUS98127 / v02.00

## Findings and definitions

- [Executable map and evidence](ElfMap.md): save and non-save findings, import instructions and repeatable commands.
- [Pack/boot state, reference segment names and opaque-byte ownership](ElfMap.md#saved-packboot-state-ordered-segment-names-and-initializer-ownership): three newly named words,56 asset-backed segment associations across19 worlds and exact initialization/copy boundaries.
- [Native address/structure map](maps/NativeMap.json): 1255 annotations, 118 imports and 38 structure definitions.
- [Health and checkpoint ammo lifecycle](ElfMap.md#runtime-health-and-checkpoint-ammo-qualifying-restoration-paths): runtime health identity/upper bound, conditional XP-driven refresh,32-slot ammo capture, qualified vendor merge and clamped restoration.
- [Saved auxiliary words](ElfMap.md#three-saved-auxiliary-words-event-branch-sixaxis-gate-and-bounded-modifier): three typed words at8758/875C/8760, wrapping counters, Sixaxis gate and native finite modifier bounds; gameplay event names remain unknown.
- [First-person camera coupling](ElfMap.md#first-person-option-entry-latch-and-qualified-camera-coupling): entry-latched option behavior, paired update methods and qualified orientation adjustment; original option name/hold-toggle meaning unresolved.
- [Parallel save research](ElfMap.md#parallel-save-research-rewards-replay-lifecycle-and-mission-keys): weapon experience rewards, per-world diminishing-return indices/remainders, replay lifecycle, historical segment median and81 native mission lookup pairs.
- [Persistent grids and copied headers](ElfMap.md#persistent-grid-volume-headers-map-labels-and-group-flags): 512×512 native grid, all21 physical slot-to-level label associations, copied200-byte volume definitions and seven saved group flags.
- [Menu routing and aggregate predicate](ElfMap.md#map-menu-routing-and-native-accumulator-predicate): inverse browse permutations, shared image IDs, readiness skips and qualified accumulator threshold.
- [Map rectangles and clearing brush](ElfMap.md#copied-map-rectangles-world-projection-and-clearing-brush): all six group-word roles, projection/sign formula and native14×14 class-matching brush.
- [Shipped pause-menu settings](ElfMap.md#shipped-pause-menu-settings-dispatch): asset-backed descriptor filtering, scheme-dependent inversion APIs and adjustment actions; unknown settings remain unnamed.
- [Reset-event category counters](ElfMap.md#reset-event-category-counters-and-temporary-runtime-selection): eight saved counters, six native category selections and temporary runtime expiration; category names unresolved.
- [Per-world object bitsets](ElfMap.md#per-world-object-state-and-spawn-suppression-bitsets): saved object state, mode-qualified spawn suppression and runtime-index limits.
- [Gameplay segment and retained-log evidence](ElfMap.md#gameplay-segments-timers-reward-accumulators-and-retained-log): named completion bindings, integer counters and stale-entry distinction.
- [Weapon/gadget configuration definitions](maps/WeaponConfigs.json)
- [Global event flag evidence](ElfMap.md#global-event-flags-named-story-tutorial-movie-and-equipment-bits): all292 named IDs, BE64 storage and acquisition/story dependencies.
- [Shared save-format notes](../../SaveFormat.md): includes the supplied encrypted USA save and European plaintext sample, with evidence distinguished.

## Matching tools and tests

- [Research tools](../../../../../Tools/PS3/ToolsOfDestruction/BCUS98127/v02.00/README.md): native inspectors and IDA/Ghidra importers.
- [Native map regression tests](../../../../../Tests/PS3/ToolsOfDestruction/BCUS98127/v02.00/TestTodElfMap.py); neighboring tests cover progression, collectibles, world/object/mission state, bonuses, state storage, arena challenges, settings/load destinations and configurations.

The executable SHA-256 is `0EE9A8414C8FC182BC19FA2A523E6D050D0BE76138B3733AE515798D77D2468C`. Address maps and byte guards apply to that input only. These findings are partial and do not establish in-game edit safety or compatibility with another region/build.
