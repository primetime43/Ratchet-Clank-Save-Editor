using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed record Rc1GadgetDefinition(int Id, string Name, int OwnershipOffset, int AcquisitionFlagOffset, bool QuickSelect);
    public sealed record Rc1GadgetGrant(string Key, Rc1GadgetDefinition Gadget, bool Owned);

    public static class Rc1GadgetEditing
    {
        public static bool IsKey(string key) => key.StartsWith("rc1_gadget_", StringComparison.Ordinal);

        public static IReadOnlyList<Rc1GadgetGrant> Grants(byte[] data, string region)
        {
            if (!Rc1SaveEditing.Supports(data, region)) return Array.Empty<Rc1GadgetGrant>();
            return Rc1Research.Gadgets.Where(item => data[item.OwnershipOffset] == 1 ||
                    data[item.OwnershipOffset] == 0 && data[item.AcquisitionFlagOffset] == 0)
                .OrderBy(item => item.Name, StringComparer.CurrentCultureIgnoreCase)
                .Select(item => new Rc1GadgetGrant("rc1_gadget_" + item.Id, item, data[item.OwnershipOffset] == 1)).ToArray();
        }

        internal static byte[] Apply(byte[] original, byte[] result, string region, IReadOnlyDictionary<string, decimal> edits)
        {
            if (!edits.Keys.Any(IsKey)) return result;
            var fields = Grants(original, region).ToDictionary(field => field.Key, StringComparer.Ordinal);
            var additions = new List<Rc1GadgetDefinition>();
            foreach (var edit in edits.Where(edit => IsKey(edit.Key)))
            {
                if (!fields.TryGetValue(edit.Key, out var field))
                    throw new InvalidDataException("Unsupported RC1 gadget grant or uncertain ownership: " + edit.Key);
                if (edit.Value != 0 && edit.Value != 1 || field.Owned && edit.Value != 1)
                    throw new InvalidDataException("RC1 gadget grants are add-only.");
                if (!field.Owned && edit.Value == 1) additions.Add(field.Gadget);
            }
            // Combat grants and explicit slot assignments already ran. Passive
            // upgrades have no slot; handheld gadgets use remaining empty slots.
            foreach (var item in additions.OrderBy(item => item.Id))
            {
                result[item.OwnershipOffset] = result[item.AcquisitionFlagOffset] = 1;
                if (item.QuickSelect) Rc1WeaponEditing.AssignFirstFreeSlot(result, item.Id);
            }
            return result;
        }
    }
}
