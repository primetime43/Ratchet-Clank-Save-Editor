using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // Shared ordinary-node plan. Direct add-only file edits, not purchases.
    internal static class TodAmmoUpgradeEditing
    {
        private static IEnumerable<JsonElement> Catalog => TodResearch.Map.GetProperty("upgrade_edit_candidates").GetProperty("catalog").EnumerateArray();
        private static uint Mask(byte[] data, int id) => BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(id * 20 + 12, 4));
        private static readonly IReadOnlyDictionary<string, string> Effects = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["MOD_DAMAGE"] = "Damage", ["MOD_RANGE"] = "Range", ["MOD_AOE"] = "Blast radius",
            ["MOD_SPEED"] = "Speed modifier", ["MOD_DURATION"] = "Duration modifier",
            ["MOD_BOLTS"] = "Bolts bonus", ["MOD_MINERALS"] = "Raritanium bonus", ["MOD_SPAWNCOUNT"] = "Spawn count"
        };
        private static string Key(int id, JsonElement node) =>
            $"{(node.GetProperty("type").GetString() == "MOD_AMMO" ? "ammo_upgrade" : "weapon_upgrade")}_{id}_{node.GetProperty("index").GetInt32()}";

        private static bool Attainable(JsonElement nodes, uint mask)
        {
            int count = nodes.GetArrayLength();
            if (count is < 1 or > 24 || (mask & ~((1u << count) - 1)) != 0) return false;
            uint reached = 1, remaining = mask & ~1u;
            while (remaining != 0)
            {
                uint before = remaining;
                foreach (var node in nodes.EnumerateArray())
                {
                    int index = node.GetProperty("index").GetInt32();
                    uint bit = 1u << index;
                    if ((remaining & bit) == 0) continue;
                    var neighbors = node.GetProperty("orthogonal_neighbors").EnumerateArray().Select(value => value.GetInt32());
                    bool admitted = node.GetProperty("is_special").GetBoolean()
                        ? neighbors.Where(value => value > 0).All(value => (reached & (1u << value)) != 0)
                        : neighbors.Any(value => (reached & (1u << value)) != 0);
                    if (admitted) { remaining &= ~bit; reached |= bit; }
                }
                if (remaining == before) return false;
            }
            return true;
        }

        internal static void AddFields(byte[] data, List<TodEditField> fields)
        {
            foreach (var item in Catalog)
            {
                int id = item.GetProperty("id").GetInt32();
                // Reuse the stricter XP/level/tier and ammo dependency checks.
                if (!fields.Any(field => field.Key == "weapon_level_" + id)) continue;
                var nodes = item.GetProperty("nodes");
                uint mask = Mask(data, id);
                if (!Attainable(nodes, mask)) continue;
                foreach (var node in nodes.EnumerateArray())
                {
                    int index = node.GetProperty("index").GetInt32();
                    string type = node.GetProperty("type").GetString();
                    bool ammo = type == "MOD_AMMO";
                    if (index == 0 || node.GetProperty("is_special").GetBoolean() ||
                        (!ammo && !Effects.ContainsKey(type)) ||
                        !node.GetProperty("definition_qualified").GetBoolean() ||
                        (mask & (1u << index)) != 0) continue;
                    float value = node.GetProperty("runtime_value").GetSingle();
                    bool percentage = node.GetProperty("is_percent").GetBoolean();
                    if (!float.IsFinite(value) || value == 0 ||
                        (ammo && (percentage || value <= 0 || value != MathF.Truncate(value))) ||
                        (!ammo && percentage && value <= -1) ||
                        !node.GetProperty("orthogonal_neighbors").EnumerateArray().Any(neighbor =>
                            neighbor.GetInt32() == 0 || (mask & (1u << neighbor.GetInt32())) != 0)) continue;
                    decimal shown = node.GetProperty("runtime_value").GetDecimal() * (percentage ? 100 : 1);
                    string amount = shown.ToString("+0.####;-0.####;0", CultureInfo.InvariantCulture) + (percentage ? "%" : "");
                    string label = ammo ? $"+{value} capacity" : Effects[type] + " " + amount;
                    fields.Add(new(Key(id, node), $"{item.GetProperty("config_name").GetString()} · {label} (node {index})",
                        ammo ? "Ammo upgrades" : "Weapon upgrades", id * 20 + 12,
                        ammo ? TodEditStorage.AmmoUpgrade : TodEditStorage.WeaponUpgrade, 0, 1,
                        Options: new[] { new TodEditOption(0, "Keep unchanged"), new TodEditOption(1, ammo ? "Add capacity upgrade" : "Add upgrade") }));
                }
            }
        }

        private static uint PlannedMask(byte[] data, int id, IReadOnlyDictionary<string, decimal> edits)
        {
            uint mask = Mask(data, id);
            var item = Catalog.Single(entry => entry.GetProperty("id").GetInt32() == id);
            foreach (var node in item.GetProperty("nodes").EnumerateArray())
                if (edits.TryGetValue(Key(id, node), out decimal value) && value == 1)
                    mask |= 1u << node.GetProperty("index").GetInt32();
            return mask;
        }

        private static float Capacity(byte[] data, int id, uint mask)
        {
            TodResearch.TryConfig(TodResearch.Inventory[id].GetProperty("config_name").GetString(), out var config);
            float maximum = config.GetProperty("variables").GetProperty("MaxAmmo")[data[id * 20 + 17]].GetSingle(), factor = 1;
            // Keep native physical-index float32 arithmetic, not decimal sums.
            foreach (var node in config.GetProperty("modifiers").EnumerateArray())
            {
                if ((mask & (1u << node.GetProperty("index").GetInt32())) == 0 || node.GetProperty("type").GetString() != "MOD_AMMO") continue;
                if (node.GetProperty("is_percent").GetBoolean()) factor += node.GetProperty("runtime_value").GetSingle();
                else maximum += node.GetProperty("runtime_value").GetSingle();
            }
            maximum *= factor;
            if (!float.IsFinite(maximum) || maximum <= 0 || maximum > 1_000_000)
                throw new InvalidDataException("Upgrade capacity is outside the verified limits.");
            return maximum;
        }

        internal static decimal Maximum(byte[] data, TodEditField ammo, IReadOnlyDictionary<string, decimal> edits)
            => (decimal)Capacity(data, ammo.Offset / 20, PlannedMask(data, ammo.Offset / 20, edits));

        internal static void Apply(byte[] original, byte[] result, IReadOnlyDictionary<string, TodEditField> fields,
            IReadOnlyDictionary<string, decimal> edits)
        {
            foreach (int id in edits.Where(edit => (fields[edit.Key].Storage is TodEditStorage.AmmoUpgrade or TodEditStorage.WeaponUpgrade) && edit.Value == 1)
                .Select(edit => fields[edit.Key].Offset / 20).Distinct())
            {
                uint mask = PlannedMask(original, id, edits);
                float before = Capacity(original, id, Mask(original, id)), after = Capacity(result, id, mask);
                BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(id * 20 + 12, 4), mask);
                if (before != after) BinaryPrimitives.WriteSingleBigEndian(result.AsSpan(id * 20 + 8, 4), after);
            }
        }
    }
}
