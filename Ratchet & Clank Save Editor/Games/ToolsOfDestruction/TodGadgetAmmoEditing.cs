using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Text.Json;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    internal static class TodGadgetAmmoEditing
    {
        internal static void AddFields(byte[] data, List<TodEditField> fields)
        {
            foreach (var item in TodResearch.Map.GetProperty("gadget_ammo_editing").GetProperty("catalog").EnumerateArray())
            {
                int id = item.GetProperty("id").GetInt32(), offset = id * 20;
                string name = item.GetProperty("config_name").GetString();
                if (id is not (16 or 17 or 18 or 20 or 21 or 22 or 23) || data[offset + 16] == 0 || data[offset + 17] != 0 ||
                    BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(offset + 12, 4)) != 0 || !TodResearch.TryConfig(name, out var config)) continue;
                float xp = BinaryPrimitives.ReadSingleBigEndian(data.AsSpan(offset + 4, 4));
                float current = BinaryPrimitives.ReadSingleBigEndian(data.AsSpan(offset + 8, 4));
                if (!float.IsFinite(xp) || xp != 0 || config.GetProperty("num_levels").GetInt32() != 0 ||
                    config.GetProperty("modifiers").GetArrayLength() != 0 ||
                    !config.GetProperty("variables").TryGetProperty("MaxAmmo", out var amounts) ||
                    amounts.GetArrayLength() != 1 || amounts[0].ValueKind != JsonValueKind.Number) continue;
                float maximum = amounts[0].GetSingle();
                if (!float.IsFinite(maximum) || maximum != item.GetProperty("maximum").GetSingle() || maximum <= 0 ||
                    !float.IsFinite(current) || current < 0 || current > maximum) continue;
                fields.Add(new("ammo_" + id, name + " ammo", "Gadget ammo", offset + 8,
                    TodEditStorage.Float, (decimal)current, (decimal)maximum, ReferenceMaximum: maximum));
            }
        }
    }
}
