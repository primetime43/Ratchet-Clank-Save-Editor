using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // Shared node plan. Direct add-only file edits, not purchases or live effects.
    internal static class TodAmmoUpgradeEditing
    {
        private static IEnumerable<JsonElement> Catalog => TodResearch.Map.GetProperty("upgrade_edit_candidates").GetProperty("catalog").EnumerateArray();
        private static uint Mask(byte[] data, int id) => BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(id * 20 + 12, 4));
        private static readonly IReadOnlyDictionary<string, string> Effects = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["MOD_DAMAGE"] = "Damage", ["MOD_RANGE"] = "Range", ["MOD_AOE"] = "Blast radius",
            ["MOD_SPEED"] = "Speed modifier", ["MOD_DURATION"] = "Duration modifier",
            ["MOD_BOLTS"] = "Bolts bonus", ["MOD_MINERALS"] = "Raritanium bonus", ["MOD_SPAWNCOUNT"] = "Spawn count",
            ["MOD_KNOCKBACK"] = "Knockback modifier", ["MOD_ALT_DAMAGE"] = "Alternate damage modifier",
            ["MOD_MISC"] = "Weapon-specific parameter"
        };
        private static string FullKey(int id) => "upgrade_all_" + id;
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

        private static bool DefinitionAllowed(int id, JsonElement node)
        {
            if (node.GetProperty("index").GetInt32() == 0 || node.GetProperty("cost").ValueKind != JsonValueKind.Number) return false;
            decimal cost = node.GetProperty("cost").GetDecimal();
            if (cost <= 0 || cost != decimal.Truncate(cost)) return false;
            string type = node.GetProperty("type").GetString();
            if (type == "MOD_SPECIAL")
                // This is a type/mask Boolean predicate, not a numeric modifier.
                // Blank shipped values remain blank, never replaced with zero.
                return node.GetProperty("is_special").GetBoolean() && node.GetProperty("runtime_value").ValueKind == JsonValueKind.Null &&
                    TodResearch.Map.GetProperty("special_modifier_effects").GetProperty("catalog").EnumerateArray().Any(entry =>
                        entry.GetProperty("id").GetInt32() == id && entry.GetProperty("node").GetInt32() == node.GetProperty("index").GetInt32() &&
                        entry.GetProperty("type_id").GetInt32() == 16 && entry.GetProperty("value").ValueKind == JsonValueKind.Null);
            if ((type != "MOD_AMMO" && !Effects.ContainsKey(type)) || !node.GetProperty("definition_qualified").GetBoolean()) return false;
            float value = node.GetProperty("runtime_value").GetSingle();
            bool percentage = node.GetProperty("is_percent").GetBoolean();
            return float.IsFinite(value) && value != 0 && (type == "MOD_AMMO"
                ? !percentage && value > 0 && value == MathF.Truncate(value) : !percentage || value > -1);
        }

        private static bool Ready(JsonElement node, uint mask) => node.GetProperty("is_special").GetBoolean()
            ? node.GetProperty("orthogonal_neighbors").EnumerateArray().Where(neighbor => neighbor.GetInt32() > 0)
                .All(neighbor => (mask & (1u << neighbor.GetInt32())) != 0)
            : node.GetProperty("orthogonal_neighbors").EnumerateArray()
                .Any(neighbor => neighbor.GetInt32() == 0 || (mask & (1u << neighbor.GetInt32())) != 0);

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
                uint complete = (1u << nodes.GetArrayLength()) - 2;
                if (nodes.EnumerateArray().Skip(1).All(node => DefinitionAllowed(id, node)) && Attainable(nodes, mask | complete))
                {
                    bool finished = (mask & complete) == complete;
                    fields.Add(new(FullKey(id), item.GetProperty("config_name").GetString() + " · complete upgrade grid",
                        "Weapon upgrades", id * 20 + 12, TodEditStorage.WeaponUpgradeAll, 0, finished ? 0 : 1,
                        Options: finished ? new[] { new TodEditOption(0, "Already fully upgraded") } :
                            new[] { new TodEditOption(0, "Keep unchanged"), new TodEditOption(1, "Unlock all upgrades") }));
                }
                foreach (var node in nodes.EnumerateArray())
                {
                    int index = node.GetProperty("index").GetInt32();
                    string type = node.GetProperty("type").GetString();
                    bool ammo = type == "MOD_AMMO";
                    if (!DefinitionAllowed(id, node) || (mask & (1u << index)) != 0 || !Ready(node, mask)) continue;
                    bool flag = type == "MOD_SPECIAL";
                    bool percentage = node.GetProperty("is_percent").GetBoolean();
                    string label = "Special behavior switch";
                    if (!flag)
                    {
                        decimal shown = node.GetProperty("runtime_value").GetDecimal() * (percentage ? 100 : 1);
                        string amount = shown.ToString("+0.####;-0.####;0", CultureInfo.InvariantCulture) + (percentage ? "%" : "");
                        label = ammo ? "+" + shown.ToString(CultureInfo.InvariantCulture) + " capacity" : Effects[type] + " " + amount;
                        if (node.GetProperty("is_special").GetBoolean()) label = "Special · " + label;
                    }
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
            if (edits.TryGetValue(FullKey(id), out decimal all) && all == 1)
                mask |= (1u << item.GetProperty("nodes").GetArrayLength()) - 2;
            foreach (var node in item.GetProperty("nodes").EnumerateArray())
                if (edits.TryGetValue(Key(id, node), out decimal value) && value == 1)
                    mask |= 1u << node.GetProperty("index").GetInt32();
            return mask;
        }

        private static float Capacity(byte[] data, int id, uint mask, bool promote = false)
        {
            TodResearch.TryConfig(TodResearch.Inventory[id].GetProperty("config_name").GetString(), out var config);
            float maximum = config.GetProperty("variables").GetProperty("MaxAmmo")[promote ? 5 : data[id * 20 + 17]].GetSingle(), factor = 1;
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

        private static float PlannedCapacity(byte[] data, int id, IReadOnlyDictionary<string, decimal> edits) =>
            Capacity(data, id, PlannedMask(data, id, edits),
                data[id * 20 + 17] == 4 && TodOmegaPromotionEditing.Promotes(id, edits));

        internal static decimal Maximum(byte[] data, TodEditField ammo, IReadOnlyDictionary<string, decimal> edits)
            => (decimal)PlannedCapacity(data, ammo.Offset / 20, edits);

        internal static bool RefillsAmmo(byte[] data, TodEditField ammo, IReadOnlyDictionary<string, decimal> edits) =>
            data[ammo.Offset / 20 * 20 + 17] == 4 && TodOmegaPromotionEditing.Promotes(ammo.Offset / 20, edits) ||
            PlannedCapacity(data, ammo.Offset / 20, edits) != Capacity(data, ammo.Offset / 20, Mask(data, ammo.Offset / 20));

        internal static void Apply(byte[] original, byte[] result, IReadOnlyDictionary<string, TodEditField> fields,
            IReadOnlyDictionary<string, decimal> edits)
        {
            foreach (int id in edits.Where(edit => (fields[edit.Key].Storage is TodEditStorage.AmmoUpgrade or TodEditStorage.WeaponUpgrade or TodEditStorage.WeaponUpgradeAll) && edit.Value == 1)
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
