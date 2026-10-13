using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // Bounded combat-weapon saved writes from466B70 and player0 auto-insertion
    // from1E26F0. Not purchases, runtime callbacks or gadget story transactions.
    internal static class TodWeaponGrantEditing
    {
        private const string Prefix = "weapon_grant_";
        internal sealed record Grant(int Id, float Ammo);
        internal sealed record Plan(IReadOnlyList<Grant> Grants, uint AcquisitionCount);
        private static string Key(int id) => Prefix + id;

        private static bool StartingAmmo(int id, out float ammo)
        {
            ammo = 0;
            if (id is < 1 or > 15) return false;
            var item = TodResearch.Inventory[id];
            var reference = TodResearch.Map.GetProperty("quick_select_eligibility").GetProperty("catalog").EnumerateArray()
                .Single(entry => entry.GetProperty("id").GetInt32() == id);
            uint flags = uint.Parse(reference.GetProperty("initial_flags").GetString().AsSpan(2), NumberStyles.HexNumber,
                CultureInfo.InvariantCulture);
            if (reference.GetProperty("enum").GetString() != item.GetProperty("enum").GetString() ||
                (flags & (0x203u | 0x1040u)) != 0 || !reference.GetProperty("quick_select_initially_allowed").GetBoolean() ||
                !TodResearch.TryConfig(item.GetProperty("config_name").GetString(), out var config) ||
                config.GetProperty("num_levels").GetInt32() != 9) return false;
            var variables = config.GetProperty("variables");
            if (!variables.TryGetProperty("XP", out var xp) || xp.GetArrayLength() != 10 ||
                !variables.TryGetProperty("MaxAmmo", out var amounts) || amounts.GetArrayLength() != 10 ||
                xp[0].ValueKind != JsonValueKind.Number || xp[1].ValueKind != JsonValueKind.Number ||
                amounts[0].ValueKind != JsonValueKind.Number || xp[0].GetSingle() != 0 ||
                !float.IsFinite(xp[1].GetSingle()) || xp[1].GetSingle() <= 0) return false;
            ammo = amounts[0].GetSingle();
            return float.IsFinite(ammo) && ammo > 0 && ammo <= 1_000_000 &&
                ammo == TodResearch.Map.GetProperty("weapon_grants").GetProperty("starting_ammo_by_id_1_to_15")[id - 1].GetSingle();
        }

        private static bool CanGrant(byte[] data, int id, out float ammo)
        {
            if (!StartingAmmo(id, out ammo)) return false;
            int offset = id * 20;
            float xp = BinaryPrimitives.ReadSingleBigEndian(data.AsSpan(offset + 4, 4));
            float savedAmmo = BinaryPrimitives.ReadSingleBigEndian(data.AsSpan(offset + 8, 4));
            return data[offset + 16] == 0 && data[offset + 17] == 0 && float.IsFinite(xp) && xp == 0 &&
                BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(offset + 12, 4)) == 0 &&
                float.IsFinite(savedAmmo) && savedAmmo >= 0 && savedAmmo <= ammo;
        }

        internal static void AddFields(byte[] data, List<TodEditField> fields)
        {
            foreach (int id in Enumerable.Range(1, 15).OrderBy(id => TodResearch.Inventory[id].GetProperty("config_name").GetString(),
                StringComparer.CurrentCultureIgnoreCase))
            {
                bool owned = data[id * 20 + 16] != 0, eligible = CanGrant(data, id, out float ammo);
                string name = TodResearch.Inventory[id].GetProperty("config_name").GetString();
                var options = owned ? new[] { new TodEditOption(1, "Already owned") } : eligible
                    ? new[] { new TodEditOption(0, "Keep unchanged"), new TodEditOption(1, "Grant level 1 on Save All") }
                    : new[] { new TodEditOption(0, "Uncertain record — preserved") };
                fields.Add(new(Key(id), name + (eligible ? $" · {ammo.ToString("0.###", CultureInfo.InvariantCulture)} starting ammo" : ""),
                    "Weapon unlocks", id * 20 + 16, TodEditStorage.WeaponGrant, owned ? 1 : 0,
                    owned || eligible ? 1 : 0, Minimum: owned ? 1 : 0, Options: options));
            }
        }

        internal static Plan Preview(byte[] data, IReadOnlyDictionary<string, decimal> edits)
        {
            var grants = new List<Grant>();
            foreach (var edit in edits.Where(edit => edit.Key.StartsWith(Prefix, StringComparison.Ordinal)).OrderBy(edit => edit.Key, StringComparer.Ordinal))
            {
                if (!int.TryParse(edit.Key.AsSpan(Prefix.Length), NumberStyles.None, CultureInfo.InvariantCulture, out int id) ||
                    id is < 1 or > 15 || edit.Key != Key(id) || edit.Value is not (0 or 1))
                    throw new InvalidDataException("Invalid combat weapon grant: " + edit.Key);
                bool owned = data[id * 20 + 16] != 0;
                if (owned)
                {
                    if (edit.Value != 1) throw new InvalidDataException("Owned weapons cannot be removed.");
                    continue; // No refill, normalization or counter change on duplicates.
                }
                if (edit.Value == 0) continue;
                if (!CanGrant(data, id, out float ammo)) throw new InvalidDataException("This weapon record cannot be granted safely: " + id);
                grants.Add(new(id, ammo));
            }
            ulong count = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(0x280, 4)) + (ulong)grants.Count;
            if (count > uint.MaxValue) throw new InvalidDataException("These weapon grants would overflow the saved acquisition counter.");
            return new(grants.OrderBy(grant => grant.Id).ToArray(), (uint)count);
        }

        internal static IReadOnlyList<TodEditOption> QuickSelectOptions(TodEditField field, byte[] data,
            IReadOnlyDictionary<string, decimal> edits)
        {
            if (field.Category != "Quick select") return field.Options;
            var options = field.Options.ToList();
            for (int id = 1; id <= 15; id++)
                if (edits.TryGetValue(Key(id), out decimal grant) && grant == 1 && CanGrant(data, id, out _) &&
                    !options.Any(option => option.Value == id))
                    options.Add(new(id, TodResearch.Inventory[id].GetProperty("config_name").GetString()));
            return options;
        }

        internal static bool CancelDependentSlots(TodEditField field, IDictionary<string, decimal> edits)
        {
            if (field.Storage != TodEditStorage.WeaponGrant || field.Current != 0 || edits.ContainsKey(field.Key)) return false;
            int id = (field.Offset - 16) / 20;
            var keys = edits.Where(edit => edit.Key.StartsWith("qs_", StringComparison.Ordinal) && edit.Value == id)
                .Select(edit => edit.Key).ToArray();
            foreach (string key in keys) edits.Remove(key);
            return keys.Length != 0;
        }

        internal static void Apply(byte[] result, Plan plan)
        {
            if (plan.Grants.Count == 0) return;
            foreach (var grant in plan.Grants)
            {
                int offset = grant.Id * 20;
                result[offset + 16] = 1;
                BinaryPrimitives.WriteSingleBigEndian(result.AsSpan(offset + 4, 4), 0);
                result[offset + 17] = 0;
                BinaryPrimitives.WriteSingleBigEndian(result.AsSpan(offset + 8, 4), grant.Ammo);
                // Scan all32 for membership, but only first24 for an empty slot.
                // Preserve existing duplicates/tail/unknown words; no full-wheel
                // warning latch is synthesized without executing the game UI.
                bool assigned = Enumerable.Range(0, 32).Any(slot =>
                    BinaryPrimitives.ReadInt32BigEndian(result.AsSpan(0x284 + 4 * slot, 4)) == grant.Id);
                if (assigned) continue;
                for (int slot = 0; slot < 24; slot++)
                    if (BinaryPrimitives.ReadInt32BigEndian(result.AsSpan(0x284 + 4 * slot, 4)) == -1)
                    {
                        BinaryPrimitives.WriteInt32BigEndian(result.AsSpan(0x284 + 4 * slot, 4), grant.Id);
                        break;
                    }
            }
            BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(0x280, 4), plan.AcquisitionCount);
        }
    }
}
