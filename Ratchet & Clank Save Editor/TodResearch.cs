using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // Static, embedded research definitions. Never reads/executes game assets.
    public static class TodResearch
    {
        public const string Scope = "Tools of Destruction · BCUS98127 v02.00 research. Read-only; runtime and cross-region acceptance unverified.";
        public static JsonElement Map { get; } = ReadJson("Research.Tod.Map.json");
        public static JsonElement Configs { get; } = ReadJson("Research.Tod.Configs.json");
        public static string ElfNotes { get; } = ReadResource("Research.Tod.ElfNotes.md");
        public static string SaveNotes { get; } = ReadResource("Research.Tod.SaveNotes.md");
        public static IReadOnlyList<JsonElement> Inventory { get; } = Array.AsReadOnly(
            Map.GetProperty("weapon_configuration").GetProperty("inventory_catalog").EnumerateArray()
                .OrderBy(item => item.GetProperty("id").GetInt32()).ToArray());

        private static string ReadResource(string name)
        {
            using var stream = typeof(TodResearch).Assembly.GetManifestResourceStream(name)
                ?? throw new InvalidDataException("Missing bundled research: " + name);
            using var reader = new StreamReader(stream);
            return reader.ReadToEnd();
        }

        private static JsonElement ReadJson(string name)
        {
            using var document = JsonDocument.Parse(ReadResource(name));
            return document.RootElement.Clone();
        }

        public static string Pretty(JsonElement value) => JsonSerializer.Serialize(value,
            new JsonSerializerOptions { WriteIndented = true });

        public static int Offset(JsonElement value) => int.Parse(value.GetString().AsSpan(2),
            NumberStyles.HexNumber, CultureInfo.InvariantCulture);

        public static string Hex(int value) => "0x" + value.ToString("X", CultureInfo.InvariantCulture);

        public static bool TryConfig(string name, out JsonElement config) => Configs.GetProperty("weapons").TryGetProperty(name, out config);

        public static string WeaponDetails(int id)
        {
            var native = Inventory[id];
            string name = native.GetProperty("config_name").GetString();
            var text = new StringBuilder(Scope).AppendLine().AppendLine()
                .AppendLine($"{name} · native ID {id} · save record {native.GetProperty("save_record_offset")}")
                .AppendLine("Names are internal config names, not localized display names.").AppendLine();
            bool hasConfig = TryConfig(name, out var config);
            if (hasConfig)
            {
                var variables = config.GetProperty("variables");
                if (variables.TryGetProperty("XP", out var xp))
                {
                    variables.TryGetProperty("MaxAmmo", out var ammo);
                    text.AppendLine("Shipped level tables (zero-based indices; not runtime edit limits):")
                        .AppendLine("Index              XP     Base ammo");
                    for (int level = 0; level < xp.GetArrayLength(); level++)
                    {
                        string threshold = xp[level].ValueKind == JsonValueKind.Null ? "unspecified" : xp[level].ToString();
                        string capacity = ammo.ValueKind == JsonValueKind.Array && level < ammo.GetArrayLength() && ammo[level].ValueKind != JsonValueKind.Null ? ammo[level].ToString() : "unspecified";
                        text.AppendLine(level.ToString(CultureInfo.InvariantCulture).PadLeft(5) + " " + threshold.PadLeft(15) + " " + capacity.PadLeft(13));
                    }
                    text.AppendLine();
                }
                if (config.GetProperty("vendor").ValueKind != JsonValueKind.Null)
                    text.AppendLine("Shipped vendor definition:").AppendLine(Pretty(config.GetProperty("vendor"))).AppendLine();
            }
            else text.AppendLine("No definition in the extracted configuration tables. Defaults are unknown.");
            var layout = Map.GetProperty("weapon_configuration").GetProperty("vendor_upgrade_layout");
            if (layout.GetProperty("grids").TryGetProperty(native.GetProperty("enum").GetString(), out var grid))
            {
                text.AppendLine().AppendLine("Vendor grid (literal node indices; negative markers remain uninterpreted):");
                foreach (var row in grid.GetProperty("rows").EnumerateArray())
                    text.AppendLine(string.Join(" ", row.EnumerateArray().Select(n => n.GetInt32().ToString(CultureInfo.InvariantCulture).PadLeft(3))));
                text.AppendLine("Special marker: " + grid.GetProperty("special_node"))
                    .AppendLine(Pretty(layout.GetProperty("rules")));
            }
            text.AppendLine().AppendLine("Native inventory binding (ELF virtual addresses and save offsets are distinct):")
                .AppendLine(Pretty(native)).AppendLine();
            if (hasConfig)
                text.AppendLine("Complete shipped configuration / modifiers (not captured runtime values or editable limits):").AppendLine(Pretty(config));
            return text.ToString();
        }
    }
}
