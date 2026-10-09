using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed record InspectionRow(string[] Cells, string Details);
    public sealed record InspectionTable(string[] Columns, IReadOnlyList<InspectionRow> Rows);
    public sealed record TodInventoryItem(int Id, string Name, int Offset, uint XpBits, uint AmmoBits,
        uint ModifierMask, byte Ownership, byte StoredLevel, ushort UnknownTail, byte Unlock, string Warning)
    {
        public bool ScriptOwned => Ownership != 0;
        public float Xp => BitConverter.Int32BitsToSingle(unchecked((int)XpBits));
        public float Ammo => BitConverter.Int32BitsToSingle(unchecked((int)AmmoBits));
    }

    // Isolated snapshot, no setters or file writes. Unknown values are never normalized.
    public sealed class TodSaveInspection
    {
        public const int ExpectedSize = 0x906F0;
        private readonly byte[] data;
        public bool Available => data != null;
        public string Message { get; }
        public int Length => data?.Length ?? 0;
        public IReadOnlyList<TodInventoryItem> Inventory { get; }
        public uint AcquisitionCounter => Available ? U32(0x280) : 0;
        private static string Number(uint bits) => BitConverter.Int32BitsToSingle(unchecked((int)bits)).ToString("R", CultureInfo.InvariantCulture);
        private uint U32(int offset) => BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(offset, 4));

        private TodSaveInspection(string message, byte[] bytes = null)
        {
            Message = message;
            data = bytes;
            var items = new List<TodInventoryItem>();
            if (Available)
            {
                foreach (var native in TodResearch.Inventory)
                {
                    int id = native.GetProperty("id").GetInt32(), offset = id * 0x14;
                    string name = native.GetProperty("config_name").GetString();
                    uint xp = U32(offset + 4), ammo = U32(offset + 8), mask = U32(offset + 12);
                    byte level = data[offset + 0x11];
                    var warnings = new List<string>();
                    if (!float.IsFinite(BitConverter.Int32BitsToSingle(unchecked((int)xp))) ||
                        !float.IsFinite(BitConverter.Int32BitsToSingle(unchecked((int)ammo))))
                        warnings.Add("Nonfinite XP/ammo; raw bits preserved.");
                    if (TodResearch.TryConfig(name, out var config))
                    {
                        var variables = config.GetProperty("variables");
                        if (variables.TryGetProperty("XP", out var thresholds) &&
                            (level >= thresholds.GetArrayLength() || thresholds[level].ValueKind == System.Text.Json.JsonValueKind.Null))
                            warnings.Add("Stored level is outside the populated shipped XP table; runtime limits unverified.");
                        uint known = 0;
                        foreach (var mod in config.GetProperty("modifiers").EnumerateArray()) known |= 1u << mod.GetProperty("index").GetInt32();
                        if (known != 0 && (mask & ~known) != 0)
                            warnings.Add("Mask contains bits absent from the shipped node catalog; no repair attempted.");
                    }
                    else warnings.Add("Shipped configuration defaults are unknown.");
                    if (data[offset + 0x10] == 0) warnings.Add("Not script-owned; numeric fields alone do not establish usability.");
                    items.Add(new(id, name, offset, xp, ammo, mask, data[offset + 0x10], level,
                        BinaryPrimitives.ReadUInt16BigEndian(data.AsSpan(offset + 0x12, 2)), data[0x5754 + id], string.Join(" ", warnings)));
                }
            }
            Inventory = items.AsReadOnly();
        }

        public static TodSaveInspection Read(byte[] bytes, string region)
        {
            if (!string.Equals(region, "BCUS98127", StringComparison.OrdinalIgnoreCase) &&
                !string.Equals(region, "BCES00052", StringComparison.OrdinalIgnoreCase))
                return new("Live mapping is limited to BCUS98127 / BCES00052 Tools of Destruction. Bundled reference research remains available on the Research tab.");
            if (bytes == null || bytes.Length != ExpectedSize)
                return new("Unrecognized save size. Expected the observed 0x906F0 Tools of Destruction layout; no research fields were decoded.");
            for (int id = 0; id < 32; id++)
                if (BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(id * 0x14, 4)) != id)
                    return new("Inventory IDs do not match the observed plaintext layout. No research fields were decoded.");
            return new("Read-only plaintext session snapshot; pending currency edits are excluded. USA reference definitions are not proof of regional/runtime compatibility.", (byte[])bytes.Clone());
        }

        private static string MissionLookup(uint id, bool description)
        {
            string idKey = description ? "description_lookup_id" : "title_lookup_id";
            string nameKey = description ? "description_enum" : "title_enum";
            foreach (var pair in TodResearch.Map.GetProperty("segment_bindings").GetProperty("native_mission_lookup_pairs").EnumerateArray())
                if (pair.GetProperty(idKey).GetUInt32() == id)
                    return id.ToString(CultureInfo.InvariantCulture) + " (" + pair.GetProperty(nameKey).GetString() + ")";
            return id.ToString(CultureInfo.InvariantCulture) + " (unmapped)";
        }

        private static string ReferenceSegmentName(int level, int slot, out string provenance)
        {
            provenance = "No reference name association for this physical world/slot; no names guessed from retained log order.";
            foreach (var native in TodResearch.Map.GetProperty("segment_configuration_assets").GetProperty("levels").EnumerateArray())
            {
                if (native.GetProperty("level_id").GetInt32() != level) continue;
                provenance = slot == 0
                    ? "Native name catalog reserves slot0 (reverse lookup FFFFFFFF); this does not make the saved slot padding or prove any completion state."
                    : "No name in the shipped reference catalog for this physical slot; unknown raw data is retained, not assumed unused.";
                foreach (var segment in native.GetProperty("segments").EnumerateArray())
                {
                    if (segment.GetProperty("slot").GetInt32() != slot) continue;
                    string name = segment.GetProperty("name").GetString();
                    provenance = $"USA BCUS98127 v02.00 reference name: {name}; native folder {native.GetProperty("folder").GetString()}, loaded array index {segment.GetProperty("loaded_name_index")}, hash bucket {segment.GetProperty("hash_bucket")}, forward lookup slot {segment.GetProperty("resolved_lookup_slot")}.\r\n" +
                        $"gameplay.dat SHA-256 {native.GetProperty("gameplay_dat_sha256").GetString()}. Native2D1A88 assigns slots from the ordered asset names; this name is not stored in GAME.SAV. Runtime/cross-region assets may differ; no ownership, mission identity or edit safety inferred.";
                    return name;
                }
                return "";
            }
            return "";
        }

        private string WorldRewardDetails(int level)
        {
            int world = 0x488 + level * 0x408;
            var text = new StringBuilder("Saved world reward tracking (not balances or current payouts):\r\n");
            foreach (var field in TodResearch.Map.GetProperty("reward_channels").GetProperty("world_storage").GetProperty("fields").EnumerateArray())
            {
                int offset = world + TodResearch.Offset(field.GetProperty("offset"));
                string kind = field.GetProperty("type").GetString();
                uint bits = kind == "u8" ? data[offset] : U32(offset);
                string value = kind == "f32" ? Number(bits) : bits.ToString(CultureInfo.InvariantCulture);
                text.AppendLine($"{field.GetProperty("name").GetString()}: {value}; raw {bits:X8} at {TodResearch.Hex(offset)}.");
            }
            if (U32(world + 0x3F0) > 4 || U32(world + 0x3F4) > 4)
                text.AppendLine("Reward ladder index outside the verified five-entry table; preserved, not clamped or evaluated.");
            text.AppendLine($"Independent special-bolt collected mask +3EC: {U32(world + 0x3EC):X8}; unknown +404..407: {Convert.ToHexString(data.AsSpan(world + 0x404, 4))}.");
            text.AppendLine("World initializer35DFA8 leaves +404..407 untouched; full snapshot/initial restore copies include them. Not proven padding or retention through every restart lifecycle.");
            text.AppendLine("Cached experience has a confirmed weapon-XP consumer, not a proven hero-XP balance. Bolts/raritanium have separate indices and remainders. Runtime budgets are unavailable; no current reward is calculated. Cache-ready nonzero reuses saved totals.");
            return text.ToString();
        }

        private string MissionDetails(int level)
        {
            var text = new StringBuilder("Saved mission lists (native storage; localized titles not recovered):\r\n");
            foreach (var group in new[] { ("Active", 0x10148), ("Completed", 0x10AF8) })
            {
                int list = group.Item2 + 0x7C * level;
                uint count = U32(list + 0x78);
                text.AppendLine($"{group.Item1}: saved count {count} at {TodResearch.Hex(list + 0x78)}." +
                    (count > 10 ? " Exceeds capacity10; only ten physical entries read, value preserved." : ""));
                for (int slot = 0; slot < Math.Min(count, 10u); slot++)
                {
                    int offset = list + slot * 12;
                    uint flags = U32(offset + 8);
                    text.AppendLine($"  Slot {slot}: title lookup ID {MissionLookup(U32(offset), false)}, description lookup ID {MissionLookup(U32(offset + 4), true)}, " +
                        $"optional {((flags & 1) != 0 ? "Yes" : "No")}, complete {((flags & 2) != 0 ? "Yes" : "No")}, " +
                        $"available {((flags & 2) == 0 ? "Yes" : "No")}; flags0x{flags:X8}, unknown bits0x{flags & ~3u:X8}, offset {TodResearch.Hex(offset)}.");
                }
            }
            text.AppendLine("Available is the inverse of complete, not a separate saved bit. Script indices concatenate active then completed and are one-based; stored slots here are zero-based. Unused entries are not interpreted or cleared.");
            return text.ToString();
        }

        public InspectionTable Table(string view)
        {
            if (!Available) return new(new[] { "Status" }, new[] { new InspectionRow(new[] { Message }, Message) });
            var rows = new List<InspectionRow>();
            if (view == "Weapons & gadgets")
            {
                foreach (var item in Inventory)
                {
                    string bits = string.Join(", ", Enumerable.Range(0, 32).Where(bit => (item.ModifierMask & (1u << bit)) != 0));
                    string details = $"{item.Name} · ID {item.Id} · save offset {TodResearch.Hex(item.Offset)}\r\n" +
                        $"XP bits: 0x{item.XpBits:X8}; ammo bits: 0x{item.AmmoBits:X8}. Stored level is zero-based.\r\n" +
                        $"Ownership byte: 0x{item.Ownership:X2} (nonzero = script-owned, not necessarily usable). Unlock byte: 0x{item.Unlock:X2} at {TodResearch.Hex(0x5754 + item.Id)}.\r\n" +
                        $"Unknown record +0x12/+0x13: {item.UnknownTail:X4}. Set modifier bits: [{bits}]. Start node 0 need not be purchased.\r\n" + item.Warning;
                    rows.Add(new(new[] { item.Id.ToString(), item.Name, item.ScriptOwned ? "Yes" : "No", item.StoredLevel.ToString(),
                        Number(item.XpBits), Number(item.AmmoBits), $"0x{item.ModifierMask:X8}", $"0x{item.Unlock:X2}", TodResearch.Hex(item.Offset), item.Warning }, details));
                }
                return new(new[] { "ID", "Config", "Owned", "Stored level", "XP", "Ammo", "Modifier mask", "Unlock", "Offset", "Notes" }, rows.AsReadOnly());
            }
            if (view == "Counters & nearby fields")
            {
                foreach (var field in new[] { (0x280, "Acquisition/removal counter", "confirmed", "Not asserted equal to the owned-item count."),
                    (0x418, "Hero XP", "code-backed", "Named hero_set_xp chain 2BAED0 -> 28A9B0 -> 252C78 -> 23E090 writes integer XP. Runtime fractional XP and level are not this field; no safe editing range inferred."),
                    (0x41C, "Bolts", "confirmed", "uint32 big endian."), (0x420, "Raritanium", "confirmed", "uint32 big endian."),
                    (0x424, "Special bolts spent", "code-backed", "Owned balance getter 25DB8 subtracts this word from collected bit counts. Skin purchase 27AA0 increments it by the definition cost. Do not normalize it to owned-skin count."),
                    (0x428, "Bolt multiplier", "code-backed", "Float32 BE. Native getter/update 1E2568 / 1E25F0; code clamps updates to 1..20, not a validated edit range."),
                    (0x42C, "Last recorded equipped item", "code-backed", "History updater1F5570 shifts old430 to434, old42C to430, then records native equipped getter11810/466EC0 at42C. Historical snapshot, not necessarily current runtime equipment; no safe editing range inferred."),
                    (0x430, "Previously recorded equipped item", "code-backed", "Previous42C value, not a dual-wield secondary slot. Restore and menu consumers use fallback logic; callback timing and reset behavior remain unverified."),
                    (0x434, "Older recorded equipped item", "code-backed", "Previous430 value; consulted by menu26CE30. Raw item ID and history order retained; unknown IDs are not repaired."),
                    (0x438, "Pack dispatch selector", "code-backed", "set_pack_type native27A30 stores0 for argument0, otherwise1. Known hero action consumers select the alternate message only when this word equals1; malformed nonzero values are not treated as true or repaired."),
                    (0x43C, "Saved pack type", "code-backed", "Named set_pack_type/get_pack_type write/read this BE32 word. Native PACK_HELI/THRUSTER/HYDRO/WING IDs0..3; TYPE_COUNT4 is a sentinel, not a mapped saved selection. Saved selection does not prove current runtime availability."),
                    (0x440, "Saved boot type", "code-backed", "Named get_boot_type reads this BE32 word. Native BOOT_NORMAL/GRIND/GRAV/CHARGE IDs0..3. set_boot_type wrapper converts its argument, but native26F60 ignores it and always writes0. No editing or runtime compatibility inferred."),
                    (0x458, "Equipped armor ID", "code-backed", "Native IDs 0..4; ownership and unlock availability are separate."),
                    (0x480, "Selected skin ID", "code-backed", "Native IDs 0..8. Select 26FC0 requires ownership; purchase 27AA0 also writes this ID."),
                    (0x8708, "Weighted skill-point total", "code-backed", "Not completion count. Native setter adds the shipped definition value for a newly earned bit."),
                    (0x8740, "Next-level selection", "code-backed", "Named set_next_level/get_next_level store/read this word. Not necessarily the current planet; unknown IDs are retained."),
                    (0x8754, "First-restart segment median", "code-backed", "Float32 BE. 3CED40 writes the median of positive finalized segment scalars through3CEB10 only when old906EC is zero. Units unverified; later restarts skip recomputing it in this path. Empty native input reads undefined scratch; this inspector does not recompute it or invent a zero default."),
                    (0x906E8, "Saved load destination", "code-backed", "Named set_save_level stores this word. Restore passes it to the level-change routine; not necessarily the current runtime planet or SFO subtitle."),
                    (0x906EC, "Engine replay/restart word", "code-backed", "Native -replay CLI option writes1; selective restart increments with unsigned wrap then caps at1000. Nonzero gates multiplier, final armor and segment scaling. Not a confirmed localized Challenge Mode label or count of completed playthroughs.") })
                {
                    uint value = U32(field.Item1);
                    rows.Add(new(new[] { TodResearch.Hex(field.Item1), field.Item2, value.ToString(CultureInfo.InvariantCulture), Number(value), $"{value:X8}", field.Item3 }, field.Item4));
                }
                return new(new[] { "Offset", "Field", "uint32 BE", "float32 BE", "Raw bits", "Confidence" }, rows.AsReadOnly());
            }
            if (view == "Global event flags")
            {
                var catalog = TodResearch.Map.GetProperty("global_flags").GetProperty("catalog").EnumerateArray()
                    .ToDictionary(e => e.GetProperty("id").GetInt32());
                for (int id = 0; id < 320; id++)
                {
                    int wordOffset = 0x5528 + id / 64 * 8;
                    int byteOffset = wordOffset + 7 - id % 64 / 8;
                    int byteMask = 1 << (id % 8);
                    ulong word = BinaryPrimitives.ReadUInt64BigEndian(data.AsSpan(wordOffset, 8));
                    bool set = (word & (1UL << (id % 64))) != 0;
                    bool mapped = catalog.TryGetValue(id, out var entry);
                    string name = mapped ? entry.GetProperty("enum").GetString() : "UNMAPPED_BIT_" + id;
                    string category = mapped ? entry.GetProperty("category").GetString() : "Unmapped";
                    string details = "Recorded global event bit, not a per-level record flag or a current story-completion verdict. " +
                        "Readable names are formatted native identifiers, not recovered localized titles. Set/clear polarity and dependencies require individual script/runtime validation.\r\n" +
                        $"ID {id}: BE64 word {TodResearch.Hex(wordOffset)}, integer bit {id % 64}; file byte {TodResearch.Hex(byteOffset)}, mask 0x{byteMask:X2}. Raw word: {word:X16}.\r\n" +
                        "Both named check/set/clear API families target the same bitset. Native leaves do not check the292-name bound; physical bits292–319 remain unknown, not named flags. No flag editing is enabled.\r\n" +
                        (mapped ? TodResearch.Pretty(entry) : "Unknown physical tail bit; GLOBAL_FLAG_COUNT292 is a sentinel, not a flag name.");
                    rows.Add(new(new[] { id.ToString(CultureInfo.InvariantCulture), name, category, set ? "Set" : "Clear",
                        TodResearch.Hex(byteOffset), $"0x{byteMask:X2}", TodResearch.Hex(wordOffset), $"{word:X16}" }, details));
                }
                return new(new[] { "ID", "Native enum", "Group", "Recorded bit", "Byte offset", "Byte mask", "Word offset", "Raw BE64 word" }, rows.AsReadOnly());
            }
            if (view == "Arena challenges")
            {
                var map = TodResearch.Map.GetProperty("arena_challenges");
                for (int id = 0; id < 23; id++)
                {
                    int offset = 0x56D8 + id * 4;
                    uint raw = U32(offset);
                    var entry = map.GetProperty("catalog").EnumerateArray().FirstOrDefault(e => e.GetProperty("id").GetInt32() == id);
                    bool mapped = entry.ValueKind != System.Text.Json.JsonValueKind.Undefined;
                    string name = mapped ? entry.GetProperty("enum").GetString() : "ARENA_CHALLENGE_INVALID";
                    string label = mapped ? entry.GetProperty("shipped").GetProperty("comment").GetString() : "Invalid / reserved ID";
                    string bolts = mapped ? entry.GetProperty("shipped").GetProperty("base_bolts").ToString() : "—";
                    string count = unchecked((int)raw).ToString(CultureInfo.InvariantCulture);
                    string details = "Recorded successes for a direct native ID, not a runtime menu index or completion percentage. " +
                        "The description is a shipped config comment, not a confirmed localized title. Base bolts are not the current payout: repeat wins and weapon rewards affect it.\r\n" +
                        "Counter reads are signed32; raw bits are preserved. Incrementing a counter alone does not grant currency or weapon/quick-select state.\r\n" +
                        "Separate reset-event category counters at 0x5734–0x5754 (not per-challenge failures; category names unknown): " + Convert.ToHexString(data.AsSpan(0x5734, 32)) + "\r\n" +
                        (mapped ? TodResearch.Pretty(entry) : "ID0 is the native INVALID sentinel, not a playable challenge.");
                    rows.Add(new(new[] { id.ToString(CultureInfo.InvariantCulture), name, label, count, bolts,
                        TodResearch.Hex(offset), $"{raw:X8}" }, details));
                }
                return new(new[] { "ID", "Native enum", "Config description", "Recorded wins (signed)", "Base bolts (shipped)", "Offset", "Raw bits" }, rows.AsReadOnly());
            }
            if (view == "Reset-event counters")
            {
                var map = TodResearch.Map.GetProperty("reset_categories");
                foreach (var entry in map.GetProperty("catalog").EnumerateArray())
                {
                    int id = entry.GetProperty("id").GetInt32(), offset = TodResearch.Offset(entry.GetProperty("offset"));
                    uint bits = U32(offset);
                    string details = "Eight separately initialized BE32 counters, not arena wins or per-challenge failures. Category names and exact event cause remain unknown.\r\n" +
                        "The native increment skips ID0 and wraps modulo32. ID1 has no recovered selection source; unusual values are preserved, not repaired.\r\n" +
                        "Category counter increment occurs BEFORE the saved restart-counter gate. Segment counters can remain unchanged; their sum is not a death total.\r\n" +
                        "Runtime category/countdown are outside the saved snapshot. Selection resets countdown to0.25 (units unverified); expiry clears category, not these saved counters.\r\n" +
                        TodResearch.Pretty(entry);
                    rows.Add(new(new[] { id.ToString(CultureInfo.InvariantCulture), bits.ToString(CultureInfo.InvariantCulture),
                        TodResearch.Hex(offset), $"{bits:X8}", entry.GetProperty("evidence").GetString() }, details));
                }
                return new(new[] { "Category ID", "Recorded events (uint32)", "Offset", "Raw bits", "Evidence" }, rows.AsReadOnly());
            }
            if (view == "Game settings")
            {
                var block = TodResearch.Map.GetProperty("settings").GetProperty("block");
                foreach (var field in block.GetProperty("fields").EnumerateArray())
                {
                    string name = field.GetProperty("name").GetString(), type = field.GetProperty("type").GetString();
                    int offset = TodResearch.Offset(field.GetProperty("offset"));
                    int width = type == "bool8" ? 1 : 4;
                    uint bits = width == 1 ? data[offset] : U32(offset);
                    string value;
                    if (type.StartsWith("bool", StringComparison.Ordinal)) value = bits != 0 ? "On" : "Off";
                    else if (type == "f32")
                    {
                        float number = BitConverter.Int32BitsToSingle(unchecked((int)bits));
                        value = float.IsFinite(number) ? number.ToString("0.###", CultureInfo.InvariantCulture) : "Invalid value (raw preserved)";
                        if (name.EndsWith("_volume", StringComparison.Ordinal) && float.IsFinite(number) && number >= 0 && number <= 1)
                            value = (number * 100).ToString("0.#", CultureInfo.InvariantCulture) + "%";
                    }
                    else value = "Index " + bits.ToString(CultureInfo.InvariantCulture);
                    string raw = Convert.ToHexString(data.AsSpan(offset, width));
                    string details = $"Save offset {TodResearch.Hex(offset)}; {type}; raw {raw}.\r\n" +
                        $"Named APIs: {field.GetProperty("get_api").GetString()} / {field.GetProperty("set_api").GetString()}.\r\n" +
                        $"Native getter {field.GetProperty("getter_va").GetString()}, setter {field.GetProperty("setter_va").GetString()}.\r\n" +
                        (type == "f32" ? $"Exact float32: {Number(bits)}. " : $"Raw integer: {bits}. ") +
                        "Boolean getters test nonzero. Float setters clamp ordinary finite inputs to0..1; no safe edit range is asserted. Control-scheme names are not recovered.\r\n" + Message;
                    if (name.EndsWith("_inverted", StringComparison.Ordinal) || name == "control_scheme_index")
                        details += "\r\nShipped pause-menu axis dispatch: scheme 0 selects normal-camera APIs; scheme 1 selects look/first-person APIs for both display and adjustment. This selects an API, not saved-flag polarity. Stored scheme bits: " + $"0x{U32(0x114BC):X8}. Entries for other schemes are not inferred. " + TodResearch.Map.GetProperty("settings_menu").GetProperty("actions").GetProperty("activation_filter").GetString();
                    if (name.EndsWith("_volume", StringComparison.Ordinal) || name == "camera_speed")
                        details += "\r\nShipped menu percentage adjustment divides input delta by 10: +1/-1 requests +0.1/-0.1 before the native setter. Descriptor presence does not establish current menu visibility.";
                    rows.Add(new(new[] { InspectionPresentation.Label(name), value, TodResearch.Hex(offset), type, raw }, details));
                }
                rows.Add(new(new[] { "Unknown settings word", U32(0x114C0).ToString(CultureInfo.InvariantCulture), "0x114C0", "unmapped u32", Convert.ToHexString(data.AsSpan(0x114C0, 4)) },
                    "Initializer writes1. Consumers20F3F0/2108D8 compare with zero and select runtime modes0F/10;20F3F0 sets independently named HERO_FIRST_PERSON bit6. The option name and polarity remain unresolved, including after shipped pause-menu analysis. get_button_layout returns constant0 and set_button_layout is a no-op; this is not a confirmed button-layout word."));
                rows.Add(new(new[] { "Unknown settings tail", Convert.ToHexString(data.AsSpan(0x114D6, 2)), "0x114D6", "unmapped bytes", Convert.ToHexString(data.AsSpan(0x114D6, 2)) },
                    "Two preserved bytes. Not proven padding; not normalized or interpreted."));
                return new(new[] { "Setting", "Value", "Offset", "Storage", "Raw bytes" }, rows.AsReadOnly());
            }
            if (view == "Stored state blocks")
            {
                var definition = TodResearch.Map.GetProperty("state_storage").GetProperty("rle_blocks");
                int baseOffset = TodResearch.Offset(definition.GetProperty("base")), stride = TodResearch.Offset(definition.GetProperty("stride"));
                var routing = TodResearch.Map.GetProperty("grid_routing");
                uint threshold = routing.GetProperty("accumulator_predicate").GetProperty("threshold").GetUInt32();
                int qualifyingCount = Enumerable.Range(0, definition.GetProperty("count").GetInt32()).Count(s => U32(baseOffset + stride * s + 0xC8) >= threshold);
                int requiredCount = routing.GetProperty("accumulator_predicate").GetProperty("count_must_exceed").GetInt32();
                for (int slot = 0; slot < definition.GetProperty("count").GetInt32(); slot++)
                {
                    int offset = baseOffset + stride * slot;
                    uint length = U32(offset + 0x60D0), savedAccumulator = U32(offset + 0xC8);
                    byte ready = data[offset + 0xCC];
                    string decodedSize = "—", status = "Not marked ready; payload not interpreted", result = "";
                    if (ready != 0)
                    {
                        if (length > 0x5FFF) status = "Length exceeds native encoder cap; payload not interpreted";
                        else
                        {
                            try
                            {
                                var decoded = TodRleInspection.Decode(data.AsSpan(offset + 0xCD, (int)length));
                                decodedSize = decoded.DecodedSize.ToString(CultureInfo.InvariantCulture);
                                status = decoded.Complete ? "Decoded to native output cap" : "Short output; no padding or repair";
                                result = $"Decoded SHA-256: {decoded.Sha256}\r\nConsumed {decoded.Consumed} encoded bytes; trailing {decoded.TrailingBytes}; clipped run bytes {decoded.ClippedBytes}.\r\n" +
                                    $"Recomputed encoder accumulator {decoded.EncoderAccumulator}; matches saved: {(savedAccumulator == (uint)decoded.EncoderAccumulator ? "Yes" : "No")}. Not exact zero-byte count or a checksum.\r\n" +
                                    "Decoded byte histogram: " + string.Join(", ", decoded.Histogram.Select(pair => $"0x{pair.Key:X2}: {pair.Value}"));
                            }
                            catch (ArgumentException error) { status = error.Message; }
                        }
                    }
                    var catalog = TodResearch.Map.GetProperty("persistent_grid").GetProperty("slot_catalog")[slot];
                    string level = catalog.GetProperty("internal_level_name").GetString();
                    var header = new StringBuilder($"Copied volume header: class 0x{U32(offset + 4):X}, stored slot {U32(offset + 0x10)}, baked layer {U32(offset + 0x14)}.\r\n");
                    bool matches = U32(offset + 4) == 0x535 && U32(offset + 0x10) == slot;
                    header.AppendLine(matches ? "Header matches native class/slot selection." : "Header does not match class535/physical slot; retained/empty/malformed bytes are not repaired.");
                    header.AppendLine($"Copied runtime geometry pointer bits 0x{U32(offset):X8} (not followed); optional volume reference 0x{U32(offset + 0x18):X8}; coordinate sign byte 0x{data[offset + 0x1C]:X2}.");
                    header.AppendLine($"Definition enabled byte 0x{data[offset + 0xC]:X2}; unknown word +08: {U32(offset + 8):X8}; unknown bytes +0D..0F: {Convert.ToHexString(data.AsSpan(offset + 0xD, 3))}; +1D..1F: {Convert.ToHexString(data.AsSpan(offset + 0x1D, 3))}.");
                    for (int group = 0; group < 7; group++)
                    {
                        int g = offset + 0x20 + group * 0x18;
                        header.AppendLine($"Group {group}: reference 0x{U32(g):X8}; map rectangle origin ({U32(g + 4)}, {U32(g + 8)}), extents ({U32(g + 0xC)}, {U32(g + 0x10)}); image index {U32(g + 0x14)}; saved flag 0x{data[offset + 0x60D4 + group]:X2} at {TodResearch.Hex(offset + 0x60D4 + group)}. Nonzero first extent gates visibility/containment checks, not a standalone activation boolean.");
                    }
                    string details = $"Physical stored block {slot} at {TodResearch.Hex(offset)}; ready byte0x{ready:X2}; declared encoded size {length}; saved accumulator {savedAccumulator}.\r\n" +
                        $"Native map-label level: {level} (ID {catalog.GetProperty("label_level_id")}). Several grid slots may share a level; not the current runtime planet.\r\n" +
                        $"Native map-menu position: {routing.GetProperty("slot_to_browse").GetProperty("values")[slot].GetInt32() + 1} of 21 (zero-based ordinal {routing.GetProperty("slot_to_browse").GetProperty("values")[slot]}); image resource index {routing.GetProperty("slot_to_image").GetProperty("values")[slot]}. Menu navigation skips ready byte 0, not a completion verdict.\r\n" +
                        $"Native accumulator threshold check: this word >= {threshold}: {(savedAccumulator >= threshold ? "Yes" : "No")}; snapshot qualifies {qualifyingCount}/21; function 24E7E8 returns {(qualifyingCount > requiredCount ? 1 : 0)} (requires count > {requiredCount}). Reads all words without a readiness gate. No confirmed trophy/completion caller; not exact cleared-cell count.\r\n" +
                        header + $"Unknown last byte60DB: {data[offset + 0x60DB]:X2}.\r\n" + status + "\r\n" + result + "\r\n" +
                        "Persistent 512×512 byte grid; native index=first coordinate*512+second coordinate. The native 14×14 brush has129 nonzero mask bytes and clears when (center class & brush byte)==candidate class; minimum-edge loops may skip rather than clamp. Projection requires runtime geometry not available from this save. Cells0/1/2 are not interchangeable booleans; unknown values are preserved. " +
                        "Seven group flags record conditional volume containment and affect map image display; the treasure mapper can bypass flag display requirements. They are not mission/collectible completion flags. " +
                        "Readiness is not visit/completion status. Runtime geometry pointer bits are not portable and never dereferenced. Safe decoding bounds both input and output; native final runs may be clipped. Original compressed bytes are never rewritten.";
                    rows.Add(new(new[] { slot.ToString(), ready != 0 ? "Yes" : "No", length.ToString(CultureInfo.InvariantCulture), decodedSize,
                        savedAccumulator.ToString(CultureInfo.InvariantCulture), $"0x{ready:X2}", TodResearch.Hex(offset), status, level }, details));
                }
                return new(new[] { "Slot", "Stored", "Encoded bytes", "Decoded bytes", "Saved accumulator", "Ready byte", "Offset", "Status", "Map-label level" }, rows.AsReadOnly());
            }
            if (view == "Blueprints")
            {
                var definition = TodResearch.Map.GetProperty("bonuses").GetProperty("blueprints");
                int offset = TodResearch.Offset(definition.GetProperty("mask_offset"));
                uint mask = U32(offset), known = Convert.ToUInt32(definition.GetProperty("all_grant_mask").GetString()[2..], 16);
                string summary = $"Native blueprint count: {System.Numerics.BitOperations.PopCount(mask)}; raw mask0x{mask:X8}; outside native all-grant mask0x{mask & ~known:X8}.";
                for (int id = 0; id < 32; id++)
                {
                    uint bit = 1u << id;
                    bool mapped = (known & bit) != 0;
                    string note = mapped ? "ID included in the native all-grant mask." : "ID outside the native all-grant mask; meaning not mapped.";
                    rows.Add(new(new[] { id.ToString(), (mask & bit) != 0 ? "Yes" : "No", mapped ? "Yes" : "No",
                        $"0x{bit:X8}", $"0x{mask:X8}", TodResearch.Hex(offset), note },
                        summary + $"\r\nBlueprint ID {id}: integer bit {id}, file byte {TodResearch.Hex(offset + 3 - id / 8)}, byte mask0x{1 << (id % 8):X2}.\r\n" +
                        note + " Physical pickup/planet names are not confirmed. Native count includes all32 bits; grant-all ORs its mask and preserves other bits. This is read-only inspection, not gameplay-validated editing."));
                }
                return new(new[] { "ID", "Collected", "In all-grant mask", "Bit", "Raw mask", "Offset", "Notes" }, rows.AsReadOnly());
            }
            if (view == "Bonuses & cheats")
            {
                var definition = TodResearch.Map.GetProperty("bonuses").GetProperty("cheats");
                uint score = U32(TodResearch.Offset(definition.GetProperty("score_offset")));
                foreach (var item in definition.GetProperty("catalog").EnumerateArray())
                {
                    int id = item.GetProperty("id").GetInt32(), offset = TodResearch.Offset(item.GetProperty("state_offset"));
                    byte state = data[offset];
                    int stateCount = item.GetProperty("state_count").GetInt32();
                    string note = state >= stateCount ? "Stored state is outside the shipped state-name count; value preserved." : "Physical saved slot, not a remapped menu index.";
                    rows.Add(new(new[] { id.ToString(), item.GetProperty("enum").GetString(), state.ToString(),
                        item.GetProperty("score_requirement").ToString(), stateCount.ToString(), TodResearch.Hex(offset),
                        item.GetProperty("definition_va").GetString(), note },
                        $"Weighted skill-point score: {score}. Physical native bonus ID {id}, stored state0x{state:X2} at {TodResearch.Hex(offset)}.\r\n" +
                        "State0 alone does not mean locked; nonzero is not a confirmed active/on label. Localized state names are not recovered.\r\n" +
                        $"Title lookup ID {item.GetProperty("title_lookup_id")}; description lookup ID {item.GetProperty("description_lookup_id")}. " +
                        $"Shipped state-name lookup IDs: {item.GetProperty("state_name_lookup_ids")}.\r\n" +
                        "Menu indices and unlock thresholds can be remapped by a runtime mode not captured in the save; this table does not assert current menu availability. " +
                        "Enable-all writes score840 and replaces zero states with1, preserving nonzero states and earned skill bits. " + note));
                }
                return new(new[] { "ID", "Bonus", "Stored state", "Shipped score", "State-name count", "State offset", "Definition VA", "Notes" }, rows.AsReadOnly());
            }
            if (view == "Special bolts")
            {
                var definition = TodResearch.Map.GetProperty("collectibles").GetProperty("special_bolts");
                int collected = definition.GetProperty("catalog").EnumerateArray().Sum(level => System.Numerics.BitOperations.PopCount(U32(TodResearch.Offset(level.GetProperty("mask_offset")))));
                uint spent = U32(0x424);
                int balance = unchecked((int)((uint)collected - spent));
                foreach (var level in definition.GetProperty("catalog").EnumerateArray())
                {
                    int id = level.GetProperty("id").GetInt32(), offset = TodResearch.Offset(level.GetProperty("mask_offset"));
                    uint mask = U32(offset);
                    int count = System.Numerics.BitOperations.PopCount(mask), total = level.GetProperty("total").GetInt32();
                    string warning = count > total ? "Count exceeds shipped total; preserved, not repaired." : "";
                    string detail = $"Special bolts: {collected} collected; {spent} spent; remaining balance {balance}.\r\n" +
                        $"Native level {id}; mask 0x{mask:X8} at {TodResearch.Hex(offset)}. Set local IDs: [" +
                        string.Join(", ", Enumerable.Range(0, 32).Where(bit => (mask & (1u << bit)) != 0)) + "].\r\n" +
                        $"BE32 integer bits; bit i is file byte {TodResearch.Hex(offset)} + 3 - i/8, mask 1<<(i%8). {warning}\r\n" +
                        $"Initialized slot19 mask at 0x550C: 0x{U32(0x550C):X8}, uninterpreted and excluded from native totals.\r\n" +
                        "No physical pickup positions or mission completion inferred. Menu can remap native level3 to18; these rows show unremapped storage.\r\n" + TodResearch.Pretty(level);
                    rows.Add(new(new[] { id.ToString(), level.GetProperty("enum").GetString(), count.ToString(), total.ToString(), $"0x{mask:X8}", TodResearch.Hex(offset), warning }, detail));
                }
                return new(new[] { "ID", "Native level", "Collected", "Shipped total", "Mask", "Offset", "Notes" }, rows.AsReadOnly());
            }
            if (view == "Objects & equipment")
            {
                foreach (var obj in TodResearch.Map.GetProperty("objects").GetProperty("catalog").EnumerateArray())
                {
                    int id = obj.GetProperty("id").GetInt32(), currentOffset = TodResearch.Offset(obj.GetProperty("current_offset")),
                        peakOffset = TodResearch.Offset(obj.GetProperty("peak_offset")), addedOffset = TodResearch.Offset(obj.GetProperty("positive_additions_offset"));
                    uint bits = U32(currentOffset);
                    string detail = $"Native object ID {id}; current signed count {unchecked((int)bits)}, bits 0x{bits:X8} at {TodResearch.Hex(currentOffset)}. Nonzero means present, including negative counts.\r\n" +
                        $"Unsigned high-water count {U32(peakOffset)} at {TodResearch.Hex(peakOffset)}; positive additions {U32(addedOffset)} at {TodResearch.Hex(addedOffset)}.\r\n" +
                        "Set writes current and raises the peak by unsigned comparison; it does not change positive additions. Add wraps32 bits, increments additions only for positive signed deltas, then raises peak.\r\n" +
                        "Labels are native object enums, not weapon IDs or localized titles. Timer/arena units and gameplay usability are not established. Positive additions are not unique lifetime pickups; no repair or safe edit range inferred.\r\n" + TodResearch.Pretty(obj);
                    rows.Add(new(new[] { id.ToString(), obj.GetProperty("enum").GetString(), unchecked((int)bits).ToString(CultureInfo.InvariantCulture),
                        U32(peakOffset).ToString(CultureInfo.InvariantCulture), U32(addedOffset).ToString(CultureInfo.InvariantCulture), bits != 0 ? "Yes" : "No",
                        TodResearch.Hex(currentOffset), TodResearch.Hex(peakOffset), TodResearch.Hex(addedOffset) }, detail));
                }
                return new(new[] { "ID", "Native object", "Current count", "Unsigned high-water", "Positive additions", "Present", "Count offset", "Peak offset", "Additions offset" }, rows.AsReadOnly());
            }
            if (view == "World object flags")
            {
                var mapping = TodResearch.Map.GetProperty("world_object_flags");
                var levels = TodResearch.Map.GetProperty("world_state").GetProperty("worlds").GetProperty("catalog").EnumerateArray().ToArray();
                int stride = TodResearch.Offset(mapping.GetProperty("world_stride"));
                int words = mapping.GetProperty("word_count").GetInt32();
                for (int level = 0; level < mapping.GetProperty("initialized_world_slots").GetInt32(); level++)
                {
                    foreach (var band in mapping.GetProperty("bitsets").EnumerateArray())
                    {
                        int offset = TodResearch.Offset(band.GetProperty("offset")) + level * stride;
                        var setSlots = new List<int>();
                        var wordDetails = new StringBuilder();
                        for (int word = 0; word < words; word++)
                        {
                            ulong bits = BinaryPrimitives.ReadUInt64BigEndian(data.AsSpan(offset + word * 8, 8));
                            for (int bit = 0; bit < 64; bit++) if ((bits & (1UL << bit)) != 0) setSlots.Add(word * 64 + bit);
                            wordDetails.AppendLine($"Word {word} at {TodResearch.Hex(offset + word * 8)}: {bits:X16}");
                        }
                        string slots = string.Join(", ", setSlots);
                        string detail = band.GetProperty("meaning").GetString() + "\r\n" +
                            "Physical runtime object-pool slots, not object UIDs, inventory IDs, collectible names or a completion percentage. No object names are recovered for these indices.\r\n" +
                            "Bit ordering: BE64 word offset=base+8*(slot/64), file byte=word+7-(slot%64)/8, mask=1<<(slot%8). Native readers/writers do not establish safe bounds for arbitrary runtime pointers.\r\n" +
                            "Set counts describe stored bits only: zero does not establish that every object is alive, present, uncollected or unfinished. Mode1 spawn suppression is not an unconditional load verdict.\r\n" +
                            $"Set object slots: [{slots}]\r\n" + wordDetails + "\r\n" + TodResearch.Pretty(band);
                        rows.Add(new(new[] { level.ToString(CultureInfo.InvariantCulture), level < levels.Length ? levels[level].GetProperty("enum").GetString() : "Unmapped physical level slot19",
                            band.GetProperty("label").GetString(), setSlots.Count.ToString(CultureInfo.InvariantCulture), TodResearch.Hex(offset),
                            Convert.ToHexString(data.AsSpan(offset, words * 8)), slots }, detail));
                    }
                }
                return new(new[] { "Level ID", "Native level", "Stored object bitset", "Set bits", "Offset", "Raw BE64 bytes", "Set object-slot indices" }, rows.AsReadOnly());
            }
            if (view == "Gameplay segments")
            {
                var mapping = TodResearch.Map.GetProperty("gameplay_segments").GetProperty("segments");
                var levels = TodResearch.Map.GetProperty("world_state").GetProperty("worlds").GetProperty("catalog").EnumerateArray().ToArray();
                for (int level = 0; level < mapping.GetProperty("initialized_world_slots").GetInt32(); level++)
                {
                    for (int slot = 0; slot < mapping.GetProperty("slots_per_world").GetInt32(); slot++)
                    {
                        int offset = TodResearch.Offset(mapping.GetProperty("record_base")) + level * TodResearch.Offset(mapping.GetProperty("world_stride")) + slot * TodResearch.Offset(mapping.GetProperty("record_stride"));
                        byte complete = data[offset + TodResearch.Offset(mapping.GetProperty("complete_offset"))];
                        string referenceName = ReferenceSegmentName(level, slot, out string provenance);
                        string detail = $"Physical segment slot {slot} at {TodResearch.Hex(offset)}; completion byte 0x{complete:X2}. Named complete_segment / is_segment_complete use this byte.\r\n" +
                            provenance + "\r\nNot a mission-list entry or a current completion percentage. Reference names come from verified native loader/asset order, never retained log order. Timer units and exact reset-event cause remain unverified.\r\n" +
                            "Reward accumulators are not wallet balances; cached totals are not current payouts. Experience channel A has a confirmed weapon-XP consumer; cached B/C are bolts/raritanium. Engine replay/restart word nonzero skips segment tick/reset/log finalization; completion can still set the flag without a log append. Localized game-mode terminology remains unverified.\r\n" +
                            string.Join("\r\n", mapping.GetProperty("fields").EnumerateArray().Select(field =>
                            {
                                int address = offset + TodResearch.Offset(field.GetProperty("offset"));
                                uint bits = U32(address);
                                string value = field.GetProperty("type").GetString() == "f32" ? Number(bits) : bits.ToString(CultureInfo.InvariantCulture);
                                string name = TodResearch.Offset(field.GetProperty("offset")) switch
                                {
                                    0x10 => "experience_reward_accumulated (weapon-XP consumer confirmed)",
                                    0x1C => "cached_experience_reward_total", 0x20 => "cached_bolts_reward_total",
                                    0x24 => "cached_raritanium_reward_total", _ => field.GetProperty("name").GetString()
                                };
                                string comment = TodResearch.Offset(field.GetProperty("offset")) is 0x10 or 0x1C or 0x20 or 0x24
                                    ? "Refined by reward_channels native attribute/message consumers; not a wallet balance or current payout."
                                    : TodResearch.Offset(field.GetProperty("offset")) == 0x28
                                    ? "35DD98 zeroes this word using a BE32 store; logical integer/float/flag meaning remains unresolved. Full snapshot/initial restore copies include its raw bits."
                                    : field.GetProperty("comment").GetString();
                                return $"{name}: {value}; bits {bits:X8} at {TodResearch.Hex(address)}. {comment}";
                            })) + $"\r\nUnknown bytes2D..2F: {Convert.ToHexString(data.AsSpan(offset + 0x2D, 3))}; untouched by35DD98, included by full snapshot/initial restore copies, not proven padding or retained through every lifecycle.";
                        rows.Add(new(new[] { level.ToString(CultureInfo.InvariantCulture), level < levels.Length ? levels[level].GetProperty("enum").GetString() : "Unmapped physical level slot19",
                            slot.ToString(CultureInfo.InvariantCulture), complete != 0 ? "Recorded" : "Not recorded", U32(offset + 8).ToString(CultureInfo.InvariantCulture),
                            Number(U32(offset)), Number(U32(offset + 4)), TodResearch.Hex(offset), referenceName }, detail));
                    }
                }
                return new(new[] { "Level ID", "Native level", "Physical segment slot", "Complete flag", "Reset-event count", "Adjusted elapsed (units unverified)", "Current-attempt elapsed", "Offset", "Reference segment name" }, rows.AsReadOnly());
            }
            if (view == "World progress")
            {
                foreach (var level in TodResearch.Map.GetProperty("world_state").GetProperty("worlds").GetProperty("catalog").EnumerateArray())
                {
                    int id = level.GetProperty("id").GetInt32(), unlockedOffset = TodResearch.Offset(level.GetProperty("unlocked_offset")),
                        visitedOffset = TodResearch.Offset(level.GetProperty("visited_offset")), excludedOffset = TodResearch.Offset(level.GetProperty("menu_exclusion_offset")),
                        missionsOffset = TodResearch.Offset(level.GetProperty("missions_completed_offset"));
                    string detail = $"Native level {id}; unlocked byte 0x{data[unlockedOffset]:X2} at {TodResearch.Hex(unlockedOffset)}, visited/seen byte 0x{data[visitedOffset]:X2} at {TodResearch.Hex(visitedOffset)}. Both use nonzero predicates.\r\n" +
                        $"Saved mission counter {U32(missionsOffset)} at {TodResearch.Hex(missionsOffset)}; menu exclusion byte 0x{data[excludedOffset]:X2} at {TodResearch.Hex(excludedOffset)}.\r\n" +
                        "These are saved values, not a completion percentage or current travel eligibility. Your runtime menu may differ. Menu requires a nonzero level ID, unlocked and clear exclusion; level3 is suppressed/remapped when level18 qualifies.\r\n" +
                        "Rows show unremapped native storage; initialized slot19 is excluded. Ten gameplay segment records are available separately.\r\n" +
                        $"Reward-cache ready byte: 0x{data[excludedOffset + 1]:X2} at {TodResearch.Hex(excludedOffset + 1)} (nonzero reuses cached reward totals; not a mission flag). Two256-byte per-world object bitsets are available in World object flags; runtime object names remain unknown.\r\n" + WorldRewardDetails(id) + MissionDetails(id) + TodResearch.Pretty(level);
                    rows.Add(new(new[] { id.ToString(), level.GetProperty("enum").GetString(), data[unlockedOffset] != 0 ? "Yes" : "No",
                        data[visitedOffset] != 0 ? "Yes" : "No", U32(missionsOffset).ToString(CultureInfo.InvariantCulture), $"0x{data[excludedOffset]:X2}",
                        TodResearch.Hex(unlockedOffset), TodResearch.Hex(visitedOffset), TodResearch.Hex(missionsOffset) }, detail));
                }
                return new(new[] { "ID", "Native level", "Unlocked", "Visited / seen", "Saved missions", "Menu exclusion", "Unlock offset", "Visit offset", "Mission offset" }, rows.AsReadOnly());
            }
            if (view == "Quick select")
            {
                for (int slot = 0; slot < 32; slot++)
                {
                    int offset = 0x284 + 4 * slot, id = unchecked((int)U32(offset));
                    string item = id == -1 ? "Empty" : id is >= 0 and < 32 ? Inventory[id].Name : $"Unknown ({id})";
                    string note = id is < -1 or > 31 ? "Outside mapped item IDs; preserved." : "";
                    string detail = $"Stored slot {slot}; signed item ID {id}, bits 0x{U32(offset):X8} at {TodResearch.Hex(offset)}. -1 means empty. {note}\r\n" +
                        "Membership/removal scan all32 words; automatic insertion searches only slots0..23 and filters item configuration flags0x1040.\r\n" +
                        "Stored indices are not a proven physical wheel order. Empty storage does not prove the live menu is empty. Player0 block only; no edit or runtime usability claim.";
                    rows.Add(new(new[] { slot.ToString(), id.ToString(CultureInfo.InvariantCulture), item, slot < 24 ? "Yes" : "No", TodResearch.Hex(offset), note }, detail));
                }
                return new(new[] { "Stored slot", "Item ID", "Item", "Auto insertion", "Offset", "Notes" }, rows.AsReadOnly());
            }
            if (view == "Skins")
            {
                uint selected = U32(0x480);
                foreach (var skin in TodResearch.Map.GetProperty("collectibles").GetProperty("skins").GetProperty("catalog").EnumerateArray())
                {
                    int id = skin.GetProperty("id").GetInt32(), offset = 0x45C + 4 * id;
                    uint owned = U32(offset);
                    string detail = $"Ownership word 0x{owned:X8} at {TodResearch.Hex(offset)}; nonzero predicate. Selected ID {selected} at 0x480" +
                        (selected >= 9 ? " (outside the mapped catalog; preserved)" : "") + ".\r\n" +
                        "Cost is a shipped special-bolt price, not a saved value. Availability is true except Jailbird ID7, which requires ownership. Cost0 does not prove unlock eligibility.\r\n" +
                        "Purchase also increases spent word424 and notifies runtime; selecting requires ownership. This view never performs those operations.\r\n" + TodResearch.Pretty(skin);
                    rows.Add(new(new[] { id.ToString(), skin.GetProperty("enum").GetString(), owned != 0 ? "Yes" : "No",
                        selected == id ? "Yes" : "No", skin.GetProperty("cost").ToString(), $"0x{owned:X8}", TodResearch.Hex(offset) }, detail));
                }
                return new(new[] { "ID", "Native name", "Owned", "Selected", "Shipped cost", "Ownership word", "Offset" }, rows.AsReadOnly());
            }
            if (view == "Skill points")
            {
                ulong bits = BinaryPrimitives.ReadUInt64BigEndian(data.AsSpan(0x8710, 8));
                var definition = TodResearch.Map.GetProperty("progression").GetProperty("skill_points");
                uint expected = 0;
                foreach (var skill in definition.GetProperty("catalog").EnumerateArray())
                    if ((bits & (1UL << skill.GetProperty("id").GetInt32())) != 0)
                        expected += skill.GetProperty("points").GetUInt32();
                foreach (var skill in definition.GetProperty("catalog").EnumerateArray())
                {
                    int id = skill.GetProperty("id").GetInt32(), offset = 0x8710 + 7 - id / 8;
                    bool complete = (bits & (1UL << id)) != 0;
                    string detail = $"Native ID {id}; BE64 integer bit {id}, byte {TodResearch.Hex(offset)} mask 0x{1 << (id % 8):X2}.\r\n" +
                        $"Saved weighted total: {U32(0x8708)}; total from these bits and shipped definitions: {expected}. " +
                        (U32(0x8708) != expected ? "Mismatch preserved; no repair attempted. " : "") +
                        $"Unknown high bits: 0x{bits & 0xF000000000000000UL:X16}. Unknown alignment bytes at 0x870C: {Convert.ToHexString(data, 0x870C, 4)}.\r\n" +
                        "Static meanings are code-backed; no edit or in-game compatibility claim.\r\n" + TodResearch.Pretty(skill);
                    rows.Add(new(new[] { id.ToString(), skill.GetProperty("enum").GetString(), complete ? "Yes" : "No",
                        skill.GetProperty("points").ToString(), skill.GetProperty("name_tag").ToString(),
                        skill.GetProperty("description_tag").ToString(), TodResearch.Hex(offset), $"0x{1 << (id % 8):X2}" }, detail));
                }
                return new(new[] { "ID", "Native name", "Complete", "Points", "Name tag", "Description tag", "Byte offset", "Bit mask" }, rows.AsReadOnly());
            }
            if (view == "Armor")
            {
                uint equipped = U32(0x458);
                foreach (var armor in TodResearch.Map.GetProperty("progression").GetProperty("armor").GetProperty("catalog").EnumerateArray())
                {
                    int id = armor.GetProperty("id").GetInt32(), offset = 0x444 + id * 4;
                    uint owned = U32(offset);
                    byte unlock = data[0x5774 + id];
                    string detail = $"Ownership word: 0x{owned:X8} at {TodResearch.Hex(offset)}; any nonzero value satisfies native ownership.\r\n" +
                        $"Equipped ID: {equipped} at 0x458" + (equipped >= 5 ? " (outside the mapped catalog; retained unchanged)" : "") +
                        $". Independent unlock byte: 0x{unlock:X2} at {TodResearch.Hex(0x5774 + id)}.\r\n" +
                        "Availability's native getter can unlock ID4 when word906EC is nonzero; this inspector only reads the saved bytes.\r\n" +
                        TodResearch.Pretty(armor);
                    rows.Add(new(new[] { id.ToString(), armor.GetProperty("enum").GetString(), owned != 0 ? "Yes" : "No",
                        $"0x{owned:X8}", equipped == id ? "Yes" : "No", $"0x{unlock:X2}", TodResearch.Hex(offset) }, detail));
                }
                return new(new[] { "ID", "Native name", "Owned", "Ownership word", "Equipped", "Unlock byte", "Ownership offset" }, rows.AsReadOnly());
            }
            if (view == "Upgrade nodes")
            {
                var layouts = TodResearch.Map.GetProperty("weapon_configuration").GetProperty("vendor_upgrade_layout");
                foreach (var item in Inventory)
                {
                    if (!TodResearch.TryConfig(item.Name, out var config)) continue;
                    string enumName = TodResearch.Inventory[item.Id].GetProperty("enum").GetString();
                    bool hasGrid = layouts.GetProperty("grids").TryGetProperty(enumName, out var layout);
                    foreach (var mod in config.GetProperty("modifiers").EnumerateArray())
                    {
                        int index = mod.GetProperty("index").GetInt32();
                        string cell = "", neighbors = "";
                        if (hasGrid)
                        {
                            var grid = layout.GetProperty("rows");
                            for (int row = 0; row < 4; row++)
                                for (int col = 0; col < 7; col++)
                                    if (grid[row][col].GetInt32() == index)
                                    {
                                        cell = $"r{row + 1} c{col + 1}";
                                        var adjacent = new List<int>();
                                        foreach (var pos in new[] { (row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1) })
                                            if (pos.Item1 is >= 0 and < 4 && pos.Item2 is >= 0 and < 7 && grid[pos.Item1][pos.Item2].GetInt32() >= 0)
                                                adjacent.Add(grid[pos.Item1][pos.Item2].GetInt32());
                                        neighbors = string.Join(", ", adjacent.OrderBy(n => n));
                                    }
                        }
                        bool special = hasGrid && layout.GetProperty("special_node").GetInt32() == index;
                        string bit = (item.ModifierMask & (1u << index)) != 0 ? "Bit set" : "Bit clear";
                        string purchased = index == 0 ? "Start; " + bit : bit;
                        string value = mod.GetProperty("value").ValueKind == System.Text.Json.JsonValueKind.Null ? "Unspecified" : mod.GetProperty("value").ToString() + (mod.GetProperty("is_percent").GetBoolean() ? "%" : "");
                        string cost = mod.GetProperty("cost").ValueKind == System.Text.Json.JsonValueKind.Null ? "Unspecified" : mod.GetProperty("cost").ToString();
                        string effect = UpgradeEffect(mod.GetProperty("type").GetString(), value);
                        if (special) effect += " (special)";
                        string status = index == 0 ? "Starting node" : (item.ModifierMask & (1u << index)) != 0 ? "Enabled" : "Not enabled";
                        string shownCost = index == 0 ? "—" : cost == "Unspecified" ? "Unknown" : cost;
                        string detail = $"{item.Name} — {effect}. {status}.\r\n" +
                            (index == 0 ? "Starting node; no purchase required.\r\n" : $"Raritanium cost: {shownCost} (game definition). Enabled means the upgrade's saved bit is set.\r\n") +
                            "Read-only. Effects and costs come from game definitions; they are not a purchase-eligibility check.\r\n\r\n" +
                            $"Technical details: node {index}. {purchased}; raw mask 0x{item.ModifierMask:X8}; script-owned: {item.ScriptOwned}.\r\n" +
                            "Type/value/cost/tags are shipped definitions, not captured runtime values or a purchase-eligibility verdict.\r\n" +
                            $"Grid position: {cell}; orthogonal nonnegative neighbors: [{neighbors}]; special node: {special}.\r\n" +
                            TodResearch.Pretty(mod) + "\r\n" + TodResearch.Pretty(layouts.GetProperty("rules"));
                        rows.Add(new(new[] { item.Name, effect, status, shownCost }, detail));
                    }
                }
                return new(new[] { "Weapon", "Upgrade", "Status", "Raritanium cost" }, rows.AsReadOnly());
            }
            if (view == "Gameplay records")
            {
                var mapping = TodResearch.Map.GetProperty("gameplay_segments").GetProperty("log");
                uint count = U32(TodResearch.Offset(mapping.GetProperty("count_offset")));
                int capacity = mapping.GetProperty("bounded_physical_slots").GetInt32();
                for (int index = 0; index < capacity; index++)
                {
                    int offset = TodResearch.Offset(mapping.GetProperty("offset")) + index * TodResearch.Offset(mapping.GetProperty("record_stride"));
                    string location = Text(offset, 64), scenario = Text(offset + 64, 64);
                    bool recognized = location.Length > 0 && location.All(c => c is >= 'a' and <= 'z' or >= '0' and <= '9' or '_' or ' ') &&
                        scenario.StartsWith("gameplay_", StringComparison.Ordinal) && scenario.All(c => c is >= 'a' and <= 'z' or >= '0' and <= '9' or '_');
                    string tail = Convert.ToHexString(data, offset + 0x80, 28);
                    bool nonzero = data.AsSpan(offset, 0x9C).IndexOfAnyExcept((byte)0) >= 0;
                    string status = index < count ? "Within saved count" : nonzero ? "Retained beyond saved count" : "Unused / zero";
                    string detail = $"Physical log slot {index}; {status}. Saved count {count} at0x10144; bounded buffer {capacity} entries." +
                        (count > capacity ? " Count exceeds buffer; reads clipped only, value not repaired." : "") +
                        "\r\nInitialization clears the count without clearing these entries. Retained entries are not active progress. Names do not establish mission completion or checkpoint flags.\r\n" +
                        string.Join("\r\n", mapping.GetProperty("fields").EnumerateArray().Select(field =>
                        {
                            int address = offset + TodResearch.Offset(field.GetProperty("offset"));
                            uint bits = U32(address);
                            string value = field.GetProperty("type").GetString() == "f32" ? Number(bits) : bits.ToString(CultureInfo.InvariantCulture);
                            return $"{field.GetProperty("name").GetString()}: {value}; bits {bits:X8} at {TodResearch.Hex(address)}. {field.GetProperty("comment").GetString()}";
                        }));
                    rows.Add(new(new[] { TodResearch.Hex(offset), recognized ? location : "[unrecognized]", recognized ? scenario : "[unrecognized]", tail, status }, detail));
                }
                return new(new[] { "Offset", "Location", "Scenario", "Numeric fields (raw28 bytes)", "Storage status" }, rows.AsReadOnly());
            }
            if (view == "Save regions")
            {
                foreach (var region in TodResearch.Map.GetProperty("save_regions").EnumerateArray())
                    rows.Add(new(new[] { region.GetProperty("start").GetString(), region.GetProperty("end_exclusive").GetString(),
                        region.GetProperty("confidence").GetString(), region.GetProperty("comment").GetString() }, TodResearch.Pretty(region)));
                return new(new[] { "Start", "End (exclusive)", "Confidence", "Meaning / limitation" }, rows.AsReadOnly());
            }
            if (view == "Prefix words")
            {
                for (int offset = 0; offset < 0x1000; offset += 4)
                {
                    uint value = U32(offset);
                    rows.Add(new(new[] { TodResearch.Hex(offset), $"{value:X8}", value.ToString(CultureInfo.InvariantCulture), Number(value) },
                        "Alternate interpretations of the same four bytes, not field names or inferred edit targets."));
                }
                return new(new[] { "Offset", "Raw bits", "uint32 BE", "float32 BE" }, rows.AsReadOnly());
            }
            throw new ArgumentException("Unknown inspection view.", nameof(view));
        }

        private static string UpgradeEffect(string type, string value)
        {
            string name = type switch
            {
                "MOD_START" => "Starting node",
                "MOD_DAMAGE" => "Damage",
                "MOD_ALT_DAMAGE" => "Alternate damage",
                "MOD_AMMO" => "Ammo capacity",
                "MOD_AOE" => "Area of effect",
                "MOD_BOLTS" => "Bolt bonus",
                "MOD_MINERALS" => "Raritanium bonus",
                "MOD_DURATION" => "Duration",
                "MOD_KNOCKBACK" => "Knockback",
                "MOD_RANGE" => "Range",
                "MOD_SPEED" => "Speed",
                "MOD_SPAWNCOUNT" => "Spawn count",
                "MOD_SPECIAL" => "Special upgrade",
                "MOD_MISC" => "Other upgrade",
                _ => type ?? "Unknown upgrade"
            };
            if (type == "MOD_START" || value == "Unspecified") return name;
            // Native units are not established for every modifier. Keep the
            // shipped number/percentage without inventing seconds or meters.
            return name + " " + (value.StartsWith("-", StringComparison.Ordinal) ? "" : "+") + value;
        }

        private string Text(int offset, int capacity)
        {
            var value = data.AsSpan(offset, capacity);
            int end = value.IndexOf((byte)0);
            return end < 0 ? string.Empty : Encoding.ASCII.GetString(value[..end]);
        }

        public string HexBytes(int offset, int count = 256)
        {
            if (!Available) return Message;
            if (offset < 0 || offset >= data.Length || count < 1 || count > 4096) throw new ArgumentOutOfRangeException(nameof(offset));
            int end = Math.Min(data.Length, offset + count);
            var text = new StringBuilder("GAME.SAV plaintext · file offsets, not ELF virtual addresses\r\n");
            for (int start = offset; start < end; start += 16)
            {
                int size = Math.Min(16, end - start);
                text.Append(start.ToString("X8")).Append("  ");
                for (int i = 0; i < 16; i++) text.Append(i < size ? data[start + i].ToString("X2") + " " : "   ");
                text.Append(" ");
                for (int i = 0; i < size; i++) text.Append(data[start + i] is >= 32 and <= 126 ? (char)data[start + i] : '.');
                text.AppendLine();
            }
            return text.ToString();
        }
    }
}
