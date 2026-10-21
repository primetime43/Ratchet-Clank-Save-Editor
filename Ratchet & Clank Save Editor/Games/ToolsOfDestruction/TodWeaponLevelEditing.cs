using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // Coupled file edits only. Never calls native setters or grants another tier.
    internal static class TodWeaponLevelEditing
    {
        internal static void AddFields(byte[] data, List<TodEditField> fields)
        {
            foreach (var item in TodResearch.Map.GetProperty("weapon_level_editing").GetProperty("catalog").EnumerateArray())
            {
                int id = item.GetProperty("id").GetInt32();
                var ammo = fields.FirstOrDefault(field => field.Key == "ammo_" + id);
                if (ammo == null || !TryReference(data, item, out _, out int first)) continue;
                int level = data[id * 20 + 17];
                fields.Add(new("weapon_level_" + id, item.GetProperty("config_name").GetString() + " level",
                    "Weapon levels", id * 20 + 17, TodEditStorage.WeaponLevel, level, first + 4,
                    Options: Enumerable.Range(first, 5).Select(value => new TodEditOption(value, "Level " + (value + 1))).ToArray(),
                    Minimum: first));
            }
        }

        private static bool TryReference(byte[] data, JsonElement item, out float[] thresholds, out int first)
        {
            thresholds = null;
            first = 0;
            int id = item.GetProperty("id").GetInt32();
            if (id is < 1 or > 15 || (item.GetProperty("initial_flags_bits").GetUInt32() & 3) != 0 ||
                data[id * 20 + 16] == 0 || !TodResearch.TryConfig(item.GetProperty("config_name").GetString(), out var config)) return false;
            int level = data[id * 20 + 17];
            float xp = BinaryPrimitives.ReadSingleBigEndian(data.AsSpan(id * 20 + 4, 4));
            if (level > 9 || !float.IsFinite(xp) || xp < 0 || config.GetProperty("num_levels").GetInt32() != 9) return false;
            var variables = config.GetProperty("variables");
            if (!variables.TryGetProperty("XP", out var values) || values.GetArrayLength() != 10 ||
                !variables.TryGetProperty("MaxAmmo", out var amounts) || amounts.GetArrayLength() != 10) return false;
            thresholds = new float[10];
            for (int index = 0; index < 10; index++)
            {
                if (values[index].ValueKind != JsonValueKind.Number || amounts[index].ValueKind != JsonValueKind.Number) return false;
                thresholds[index] = values[index].GetSingle();
                float amount = amounts[index].GetSingle();
                if (!float.IsFinite(thresholds[index]) || thresholds[index] < 0 ||
                    !float.IsFinite(amount) || amount <= 0 || (index > 0 && thresholds[index] <= thresholds[index - 1])) return false;
            }
            if (thresholds[0] != 0) return false;
            // The native cap is sampled using the PRE-UPDATE stored level.
            int cap = level > 4 ? 9 : 4, recomputed = 0;
            while (recomputed < cap && xp >= thresholds[recomputed + 1]) recomputed++;
            if (recomputed != level) return false;
            first = level > 4 ? 5 : 0;
            float currentBase = amounts[level].GetSingle();
            for (int candidate = first; candidate < first + 5; candidate++)
                if (amounts[candidate].GetSingle() != currentBase) return false;
            return true;
        }

        internal static void Apply(byte[] original, byte[] result, TodEditField field, decimal value, IReadOnlyDictionary<string, TodEditField> fields)
        {
            int id = (field.Offset - 17) / 20;
            var reference = TodResearch.Map.GetProperty("weapon_level_editing").GetProperty("catalog").EnumerateArray()
                .Single(item => item.GetProperty("id").GetInt32() == id);
            if (!TryReference(original, reference, out float[] thresholds, out _))
                throw new System.IO.InvalidDataException("Weapon level dependencies are not verified.");
            int offset = id * 20, level = decimal.ToInt32(value);
            BinaryPrimitives.WriteSingleBigEndian(result.AsSpan(offset + 4, 4), thresholds[level]);
            result[offset + 17] = (byte)level;
            if (level > original[offset + 17])
                BinaryPrimitives.WriteSingleBigEndian(result.AsSpan(offset + 8, 4), fields["ammo_" + id].ReferenceMaximum.Value);
        }
    }
}
