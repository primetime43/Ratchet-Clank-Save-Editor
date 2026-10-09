using System;
using System.Globalization;
using System.Linq;
using System.Text.RegularExpressions;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // Presentation only: never changes the decoded snapshot or save bytes.
    public static class InspectionPresentation
    {
        public static string ViewKey(string label) => label switch
        {
            "Player summary" => "Counters & nearby fields",
            "Saved locations" => "Gameplay records",
            "Save layout" => "Save regions",
            "Files & metadata" => "Files & headers",
            "Prefix words (technical)" => "Prefix words",
            "Hex bytes (technical)" => "Hex bytes",
            _ => label
        };

        public static InspectionTable Simplify(string view, InspectionTable source)
        {
            if (source == null || source.Rows.Count == 0) return source;
            // Unsupported/unloaded saves have a status table, not this schema.
            int expected = view switch
            {
                "Weapons & gadgets" => 10, "Skill points" => 8, "Armor" => 7,
                "Counters & nearby fields" => 6, "Gameplay records" => 4,
                "Save regions" => 4, "Files & headers" => 5, "Special bolts" => 7, "Skins" => 7, _ => 0
            };
            if (expected == 0 || source.Columns.Length != expected) return source;

            string[] columns = view switch
            {
                "Weapons & gadgets" => new[] { "Item", "Owned", "Level", "XP", "Ammo" },
                "Skill points" => new[] { "Skill point", "Complete", "Points" },
                "Armor" => new[] { "Armor", "Owned", "Equipped" },
                "Special bolts" => new[] { "Level", "Collected", "Total" },
                "Skins" => new[] { "Skin", "Owned", "Selected", "Bolt cost" },
                "Counters & nearby fields" => new[] { "Information", "Value" },
                "Gameplay records" => new[] { "Location", "Saved record" },
                "Save regions" => new[] { "Section", "Size", "Understanding" },
                _ => new[] { "File", "Information", "Value" }
            };
            var rows = source.Rows.Where(row => Include(view, row.Cells)).Select(row =>
            {
                string[] c = row.Cells;
                string note = view switch
                {
                    "Weapons & gadgets" => "Levels display stored level + 1 for weapon IDs 1–15. XP and ammo are rounded for display only. Select Technical for exact values." +
                        (string.IsNullOrEmpty(c[9]) ? "" : "\r\nNeeds review: " + c[9]),
                    "Skill points" => "This readable label is formatted from the internal identifier, not a recovered localized skill-point title.",
                    "Armor" => "Ownership, equipped ID and the saved unlock byte are independent. Raw flags and native availability caveats are below.",
                    "Special bolts" => "Counts are from native per-level masks; labels are internal level identifiers. Select a row for overall collected/spent balance and exact bits.",
                    "Skins" => "Labels are formatted native identifiers. Shipped prices use special bolts; ownership and selected ID are saved separately.",
                    "Gameplay records" => "These are saved location/scenario identifiers, not proof that a mission is complete. Record tail meanings remain unknown.",
                    "Save regions" => "This is a structural overview. Technical shows the original research map; selected-row details retain its offsets and limitations.",
                    _ => "Technical shows all decoded fields, including unknowns. This view does not validate save integrity."
                };
                string raw = string.Join("\r\n", source.Columns.Select((column, index) => column + ": " + c[index]));
                string[] cells = Cells(view, c);
                string summary = string.Join(" · ", columns.Select((column, index) => column + ": " + cells[index]));
                if (view == "Special bolts") summary = row.Details.Split('\n')[0].TrimEnd('\r') + "\r\n" + summary;
                return new InspectionRow(cells, summary + "\r\n" + note + "\r\n\r\n" + raw + "\r\n\r\n" + row.Details);
            }).ToArray();
            return new InspectionTable(columns, rows);
        }

        private static bool Include(string view, string[] c)
        {
            if (view == "Counters & nearby fields")
                return Offset(c[0]) is 0x280 or 0x418 or 0x41C or 0x420 or 0x424 or 0x428 or 0x458 or 0x480 or 0x8708;
            if (view != "Files & headers") return true;
            return c[2] is "Length" or "Dimensions" or "Inspection unavailable" ||
                (c[0].Equals("PARAM.SFO", StringComparison.OrdinalIgnoreCase) &&
                c[2] is "TITLE" or "SUB_TITLE" or "DETAIL" or "SAVEDATA_DIRECTORY" or "PS3_SYSTEM_VER" or "ACCOUNT_ID") ||
                (c[0].Equals("PARAM.PFD", StringComparison.OrdinalIgnoreCase) && c[2] == "Version");
        }

        private static string[] Cells(string view, string[] c) => view switch
        {
            "Weapons & gadgets" => new[] { c[1], c[2], Level(c), Number(c[4]), Number(c[5]) },
            "Skill points" => new[] { Label(c[1], "SKILLPOINT_"), c[2], c[3] },
            "Armor" => new[] { c[1] == "ARMOR_NONE" ? "No armor" : Label(c[1], "ARMOR_"), c[2], c[4] },
            "Special bolts" => new[] { Label(c[1], "LEVEL_"), c[2], c[3] },
            "Skins" => new[] { c[1] == "SKIN_NONE" ? "Default" : Label(c[1], "SKIN_"), c[2], c[3], c[4] },
            "Counters & nearby fields" => Summary(c),
            "Gameplay records" => new[] { Label(c[1]), Label(c[2], "gameplay_") },
            "Save regions" => Region(c),
            _ => new[] { c[0], MetadataLabel(c[2]), c[2] == "Length" ? c[3].Split(" (0x", StringSplitOptions.None)[0] : c[3] }
        };

        private static string Level(string[] c)
        {
            if (!int.TryParse(c[0], out int id) || id is < 1 or > 15) return "—";
            if (!int.TryParse(c[3], out int level) || !TodResearch.TryConfig(c[1], out var config) ||
                !config.GetProperty("variables").TryGetProperty("XP", out var thresholds) ||
                level < 0 || level >= thresholds.GetArrayLength() ||
                thresholds[level].ValueKind == System.Text.Json.JsonValueKind.Null) return "Unknown";
            return (level + 1).ToString(CultureInfo.InvariantCulture);
        }

        private static string Number(string value) =>
            double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out double number) && double.IsFinite(number)
                ? number.ToString("0.##", CultureInfo.InvariantCulture) : "Invalid value";

        private static string[] Summary(string[] c)
        {
            string name = Offset(c[0]) switch
            {
                0x280 => "Acquisition counter", 0x418 => "Hero XP", 0x41C => "Bolts", 0x420 => "Raritanium", 0x424 => "Special bolts spent",
                0x428 => "Bolt multiplier", 0x458 => "Equipped armor", 0x480 => "Selected skin", 0x8708 => "Skill-point score", _ => c[1]
            };
            string value = c[2];
            // The multiplier is a float32 field, unlike the nearby integer counters.
            if (Offset(c[0]) == 0x428)
                value = Number(c[3]) is var multiplier && multiplier != "Invalid value" ? multiplier + "×" : multiplier;
            if (Offset(c[0]) == 0x458 && uint.TryParse(value, out uint armor) && armor < 5)
                value = new[] { "No armor", "Durafiber", "Hyperplate", "Tetramesh", "Quantonium" }[armor];
            if (Offset(c[0]) == 0x480 && uint.TryParse(value, out uint skin) && skin < 9)
                value = skin == 0 ? "Default" : Label(TodResearch.Map.GetProperty("collectibles").GetProperty("skins").GetProperty("catalog")[(int)skin].GetProperty("enum").GetString(), "SKIN_");
            return new[] { name, value };
        }

        private static string[] Region(string[] c)
        {
            int start = Offset(c[0]), end = Offset(c[1]);
            (string name, string understanding) = start switch
            {
                0 => ("Weapons & gadgets", "Partially mapped"),
                0x280 => ("Acquisition counter", "Mapped counter"),
                0x284 => ("Other player data", "Partially mapped: includes hero XP"),
                0x41C => ("Bolts", "Mapped"), 0x420 => ("Raritanium", "Mapped"),
                0x424 => ("Special bolts spent", "Code-backed field"), 0x428 => ("Bolt multiplier", "Code-backed field"),
                0x42C => ("Other game state", "Partially mapped: armor, skins, collectibles and skill points"),
                0x8764 => ("Saved locations", "Record structure mapped; tail fields unknown"),
                _ => ("World state", "Mostly unknown")
            };
            return new[] { name, (end - start).ToString("N0", CultureInfo.InvariantCulture) + " bytes", understanding };
        }

        private static int Offset(string value) => int.TryParse(value.StartsWith("0x", StringComparison.OrdinalIgnoreCase) ? value[2..] : value,
            NumberStyles.HexNumber, CultureInfo.InvariantCulture, out int result) ? result : -1;

        private static string MetadataLabel(string field) => field switch
        {
            "Length" => "File size", "Dimensions" => "Image size", "TITLE" => "Game title",
            "SUB_TITLE" => "Save title", "DETAIL" => "Save description", "SAVEDATA_DIRECTORY" => "Save folder",
            "PS3_SYSTEM_VER" => "PS3 system version", "ACCOUNT_ID" => "Account (private)",
            "Version" => "Header version", _ => field
        };

        private static string Label(string identifier, string prefix = "")
        {
            string value = identifier.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) ? identifier[prefix.Length..] : identifier;
            return string.Join(" ", value.Split('_', StringSplitOptions.RemoveEmptyEntries).Select(word =>
                Regex.IsMatch(word, @"\d") ? word : CultureInfo.InvariantCulture.TextInfo.ToTitleCase(word.ToLowerInvariant())));
        }
    }
}
