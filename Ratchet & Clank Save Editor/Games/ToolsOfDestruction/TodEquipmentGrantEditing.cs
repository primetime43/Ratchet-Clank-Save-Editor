using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // A single missing equipment object through23D870's saved +1 transaction.
    // No automatic equip, story flag, world-object or pickup callback changes.
    internal static class TodEquipmentGrantEditing
    {
        private const string Prefix = "equipment_grant_";
        internal sealed record Item(int Id, string Name, int Current, int Peak, int Additions);
        internal sealed record Grant(Item Item, uint Peak, uint Additions);
        private static readonly Item[] Items = { new(5, "Charge Boots", 0x318, 0x374, 0x3D0),
            new(6, "Treasure Mapper", 0x31C, 0x378, 0x3D4) };

        internal static void AddFields(byte[] data, List<TodEditField> fields)
        {
            foreach (var item in Items)
            {
                bool owned = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(item.Current, 4)) != 0;
                bool eligible = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(item.Additions, 4)) < uint.MaxValue;
                var options = owned ? new[] { new TodEditOption(1, "Already owned") } : eligible
                    ? new[] { new TodEditOption(0, "Keep unchanged"), new TodEditOption(1, "Grant equipment on Save All") }
                    : new[] { new TodEditOption(0, "Addition counter overflow — preserved") };
                fields.Add(new(Prefix + item.Id, item.Name, "Equipment unlocks", item.Current, TodEditStorage.EquipmentGrant,
                    owned ? 1 : 0, owned || eligible ? 1 : 0, Minimum: owned ? 1 : 0, Options: options));
            }
        }

        internal static IReadOnlyList<Grant> Preview(byte[] data, IReadOnlyDictionary<string, decimal> edits)
        {
            var grants = new List<Grant>();
            foreach (var edit in edits.Where(edit => edit.Key.StartsWith(Prefix, StringComparison.Ordinal)))
            {
                if (!int.TryParse(edit.Key.AsSpan(Prefix.Length), NumberStyles.None, CultureInfo.InvariantCulture, out int id) ||
                    !Items.Any(item => item.Id == id) || edit.Key != Prefix + id || edit.Value is not (0 or 1))
                    throw new InvalidDataException("Invalid equipment grant: " + edit.Key);
                var item = Items.Single(item => item.Id == id);
                if (BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(item.Current, 4)) != 0)
                {
                    if (edit.Value != 1) throw new InvalidDataException("Owned equipment cannot be removed.");
                    continue;
                }
                if (edit.Value == 0) continue;
                uint additions = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(item.Additions, 4));
                if (additions == uint.MaxValue) throw new InvalidDataException(item.Name + " grant would overflow its addition counter.");
                grants.Add(new(item, Math.Max(1u, BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(item.Peak, 4))), additions + 1));
            }
            return grants;
        }

        internal static void Apply(byte[] result, IReadOnlyList<Grant> grants)
        {
            foreach (var grant in grants)
            {
                BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(grant.Item.Current, 4), 1);
                BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(grant.Item.Peak, 4), grant.Peak);
                BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(grant.Item.Additions, 4), grant.Additions);
            }
        }
    }
}
