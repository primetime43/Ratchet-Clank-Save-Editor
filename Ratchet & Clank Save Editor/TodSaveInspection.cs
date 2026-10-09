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
                    text.AppendLine($"  Slot {slot}: title lookup ID {U32(offset)}, description lookup ID {U32(offset + 4)}, " +
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
                    (0x42C, "Unknown", "unknown", "Unmapped state."), (0x430, "Unknown", "unknown", "Unmapped state."),
                    (0x458, "Equipped armor ID", "code-backed", "Native IDs 0..4; ownership and unlock availability are separate."),
                    (0x480, "Selected skin ID", "code-backed", "Native IDs 0..8. Select 26FC0 requires ownership; purchase 27AA0 also writes this ID."),
                    (0x8708, "Weighted skill-point total", "code-backed", "Not completion count. Native setter adds the shipped definition value for a newly earned bit."),
                    (0x906EC, "Restart/playthrough counter", "candidate", "Nonzero predicate gates multiplier and final armor availability; exact gameplay naming remains candidate.") })
                {
                    uint value = U32(field.Item1);
                    rows.Add(new(new[] { TodResearch.Hex(field.Item1), field.Item2, value.ToString(CultureInfo.InvariantCulture), Number(value), $"{value:X8}", field.Item3 }, field.Item4));
                }
                return new(new[] { "Offset", "Field", "uint32 BE", "float32 BE", "Raw bits", "Confidence" }, rows.AsReadOnly());
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
                        "Rows show unremapped native storage; initialized slot19 is excluded. Other world-record bytes remain unmapped.\r\n" + MissionDetails(id) + TodResearch.Pretty(level);
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
                for (int index = 0; index < 27; index++)
                {
                    int offset = 0x8764 + index * 0x9C;
                    string location = Text(offset, 64), scenario = Text(offset + 64, 64);
                    bool recognized = location.Length > 0 && location.All(c => c is >= 'a' and <= 'z' or >= '0' and <= '9' or '_' or ' ') &&
                        scenario.StartsWith("gameplay_", StringComparison.Ordinal) && scenario.All(c => c is >= 'a' and <= 'z' or >= '0' and <= '9' or '_');
                    string tail = Convert.ToHexString(data, offset + 0x80, 28);
                    string detail = "Observed named-record structure; names do not establish completion or checkpoint flags. Tail semantics are unknown.\r\n" +
                        string.Join("\r\n", Enumerable.Range(0, 7).Select(i => $"{TodResearch.Hex(offset + 0x80 + i * 4)}: {U32(offset + 0x80 + i * 4):X8} · uint {U32(offset + 0x80 + i * 4)} · float {Number(U32(offset + 0x80 + i * 4))}"));
                    rows.Add(new(new[] { TodResearch.Hex(offset), recognized ? location : "[unrecognized]", recognized ? scenario : "[unrecognized]", tail }, detail));
                }
                return new(new[] { "Offset", "Location", "Scenario", "Unknown 28-byte tail" }, rows.AsReadOnly());
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
