using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // Bounded saved writes from the level-five bridge (465E78), gated by the
    // saved prerequisites of 2D20C8. Does not execute a vendor purchase or callbacks.
    internal static class TodOmegaPromotionEditing
    {
        private static string Key(int id) => "omega_promote_" + id;

        internal static bool Promotes(int id, IReadOnlyDictionary<string, decimal> edits) =>
            edits.TryGetValue(Key(id), out decimal value) && value == 1;

        internal static bool CanBulkPromote(TodEditField field, IReadOnlyDictionary<string, decimal> edits) =>
            field.Storage == TodEditStorage.OmegaPromotion && field.Current == 0 && field.Maximum == 1 &&
            (!edits.TryGetValue("weapon_level_" + field.Offset / 20, out decimal level) || level == 4);

        internal static void AddFields(byte[] data, List<TodEditField> fields)
        {
            bool replay = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(0x906EC, 4)) != 0;
            for (int id = 1; id <= 15; id++)
            {
                // Reuse the verified ownership, flags, XP/level, ammo, modifier
                // and complete ten-row definition checks of the level editor.
                bool verified = fields.Any(field => field.Key == "weapon_level_" + id);
                int level = data[id * 20 + 17];
                bool already = verified && level >= 5;
                bool eligible = verified && level == 4 && replay;
                string state = already ? "Already Omega" : !verified ? "Unowned or uncertain record" :
                    !replay ? "Requires an existing replay / Challenge Mode save" : "Requires weapon level 5";
                var options = eligible
                    ? new[] { new TodEditOption(0, "Keep unchanged"), new TodEditOption(1, "Promote to Omega level 6") }
                    : new[] { new TodEditOption(already ? 1 : 0, state) };
                fields.Add(new(Key(id), TodResearch.Inventory[id].GetProperty("config_name").GetString(),
                    "Omega promotions", id * 20 + 17, TodEditStorage.OmegaPromotion, already ? 1 : 0,
                    already || eligible ? 1 : 0, Minimum: already ? 1 : 0, Options: options));
            }
        }

        internal static void Validate(byte[] original, IReadOnlyList<TodEditField> fields,
            IReadOnlyDictionary<string, decimal> edits)
        {
            foreach (var field in fields.Where(field => field.Storage == TodEditStorage.OmegaPromotion))
            {
                if (!edits.TryGetValue(field.Key, out decimal value) || value == field.Current) continue;
                int id = field.Offset / 20;
                if (value != 1 || field.Maximum != 1 || original[id * 20 + 17] != 4 ||
                    BinaryPrimitives.ReadUInt32BigEndian(original.AsSpan(0x906EC, 4)) == 0)
                    throw new InvalidDataException("This weapon cannot be promoted to Omega in the current save.");
                if (edits.TryGetValue("weapon_level_" + id, out decimal level) && level != 4)
                    throw new InvalidDataException("Save the Omega promotion before changing this weapon's level, or cancel its staged level change.");
            }
        }

        internal static void Apply(byte[] original, byte[] result, IReadOnlyDictionary<string, TodEditField> fields,
            IReadOnlyDictionary<string, decimal> edits)
        {
            foreach (var field in fields.Values.Where(field => field.Storage == TodEditStorage.OmegaPromotion && field.Current == 0))
            {
                int id = field.Offset / 20;
                if (!Promotes(id, edits)) continue;
                TodResearch.TryConfig(TodResearch.Inventory[id].GetProperty("config_name").GetString(), out var config);
                int offset = id * 20;
                result[offset + 17] = 5;
                BinaryPrimitives.WriteSingleBigEndian(result.AsSpan(offset + 4, 4), config.GetProperty("variables").GetProperty("XP")[5].GetSingle());
                BinaryPrimitives.WriteSingleBigEndian(result.AsSpan(offset + 8, 4),
                    (float)TodAmmoUpgradeEditing.Maximum(original, fields["ammo_" + id], edits));
            }
        }
    }
}
