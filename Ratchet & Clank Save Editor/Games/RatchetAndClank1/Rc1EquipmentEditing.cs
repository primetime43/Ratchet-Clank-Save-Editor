using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed record Rc1EquipmentDefinition(int Id, string Name, int OwnershipOffset, int AcquisitionFlagOffset);
    public sealed record Rc1EquipmentGrant(string Key, Rc1EquipmentDefinition Equipment, bool Owned);

    public static class Rc1EquipmentEditing
    {
        public static bool IsKey(string key) => key.StartsWith("rc1_equipment_", StringComparison.Ordinal);

        public static IReadOnlyList<Rc1EquipmentGrant> Grants(byte[] data, string region)
        {
            if (!Rc1SaveEditing.Supports(data, region)) return Array.Empty<Rc1EquipmentGrant>();
            return Rc1Research.Equipment.Where(item => data[item.OwnershipOffset] == 1 ||
                    data[item.OwnershipOffset] == 0 && data[item.AcquisitionFlagOffset] == 0)
                .OrderBy(item => item.Name, StringComparer.CurrentCultureIgnoreCase)
                .Select(item => new Rc1EquipmentGrant("rc1_equipment_" + item.Id, item, data[item.OwnershipOffset] == 1)).ToArray();
        }

        internal static byte[] Apply(byte[] original, byte[] result, string region, IReadOnlyDictionary<string, decimal> edits)
        {
            if (!edits.Keys.Any(IsKey)) return result;
            var fields = Grants(original, region).ToDictionary(field => field.Key, StringComparer.Ordinal);
            foreach (var edit in edits.Where(edit => IsKey(edit.Key)))
            {
                if (!fields.TryGetValue(edit.Key, out var field))
                    throw new InvalidDataException("Unsupported RC1 equipment grant or uncertain ownership: " + edit.Key);
                if (edit.Value != 0 && edit.Value != 1 || field.Owned && edit.Value != 1)
                    throw new InvalidDataException("RC1 equipment grants are add-only.");
                if (field.Owned || edit.Value == 0) continue;
                // Native item types 1/2/3 bypass quick select and ammo. Grant
                // ownership without requesting an equip or advancing a quest.
                result[field.Equipment.OwnershipOffset] = result[field.Equipment.AcquisitionFlagOffset] = 1;
            }
            return result;
        }
    }
}
