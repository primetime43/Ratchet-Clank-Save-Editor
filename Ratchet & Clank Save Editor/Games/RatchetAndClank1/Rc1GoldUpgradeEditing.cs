using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed record Rc1GoldUpgradeField(string Key, string Name, int Id, int Offset, int OwnershipOffset, bool Upgraded);

    public static class Rc1GoldUpgradeEditing
    {
        public static bool IsKey(string key) => key.StartsWith("rc1_gold_", StringComparison.Ordinal);

        public static IReadOnlyList<Rc1GoldUpgradeField> Fields(byte[] data, string region)
        {
            if (!Rc1SaveEditing.Supports(data, region)) return Array.Empty<Rc1GoldUpgradeField>();
            return Rc1Research.GoldUpgrades.Where(field => data[field.OwnershipOffset] == 1 && data[field.Offset] <= 1)
                .Select(field => field with { Upgraded = data[field.Offset] == 1 })
                .OrderBy(field => field.Name, StringComparer.CurrentCultureIgnoreCase).ToArray();
        }

        internal static byte[] Apply(byte[] original, byte[] result, string region, IReadOnlyDictionary<string, decimal> edits)
        {
            if (!edits.Keys.Any(IsKey)) return result;
            var fields = Fields(original, region).ToDictionary(field => field.Key, StringComparer.Ordinal);
            foreach (var edit in edits.Where(edit => IsKey(edit.Key)))
            {
                if (!fields.TryGetValue(edit.Key, out var field))
                    throw new InvalidDataException("Gold upgrades require an already-owned supported weapon with a verified upgrade flag: " + edit.Key);
                if (edit.Value != 0 && edit.Value != 1 || field.Upgraded && edit.Value != 1)
                    throw new InvalidDataException("RC1 gold upgrades are add-only.");
                if (edit.Value == 1) result[field.Offset] = 1;
            }
            return result;
        }
    }
}
