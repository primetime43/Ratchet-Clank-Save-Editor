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
                    (0x418, "Unknown", "unknown", "Do not infer a purpose from its value."),
                    (0x41C, "Bolts", "confirmed", "uint32 big endian."), (0x420, "Raritanium", "confirmed", "uint32 big endian."),
                    (0x424, "Unknown", "observed", "Sample value 32 does not establish a count invariant."),
                    (0x428, "Candidate multiplier", "candidate", "Float interpretation is not a verified gameplay meaning."),
                    (0x42C, "Unknown", "unknown", "Unmapped state."), (0x430, "Unknown", "unknown", "Unmapped state.") })
                {
                    uint value = U32(field.Item1);
                    rows.Add(new(new[] { TodResearch.Hex(field.Item1), field.Item2, value.ToString(CultureInfo.InvariantCulture), Number(value), $"{value:X8}", field.Item3 }, field.Item4));
                }
                return new(new[] { "Offset", "Field", "uint32 BE", "float32 BE", "Raw bits", "Confidence" }, rows.AsReadOnly());
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
                        string detail = $"{item.Name} · node {index}. {purchased}; raw mask 0x{item.ModifierMask:X8}; script-owned: {item.ScriptOwned}.\r\n" +
                            "Type/value/cost/tags are shipped definitions, not captured runtime values or a purchase-eligibility verdict.\r\n" +
                            $"Grid position: {cell}; orthogonal nonnegative neighbors: [{neighbors}]; special node: {special}.\r\n" +
                            TodResearch.Pretty(mod) + "\r\n" + TodResearch.Pretty(layouts.GetProperty("rules"));
                        rows.Add(new(new[] { item.Name, index.ToString(), purchased, mod.GetProperty("type").GetString(), value, cost, cell, special ? "Yes" : "No", neighbors }, detail));
                    }
                }
                return new(new[] { "Config", "Node", "Saved bit / start", "Shipped type", "Shipped value", "Shipped cost", "Grid cell", "Special", "Neighbors" }, rows.AsReadOnly());
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
