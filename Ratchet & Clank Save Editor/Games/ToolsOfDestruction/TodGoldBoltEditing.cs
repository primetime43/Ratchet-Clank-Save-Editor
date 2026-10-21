using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Numerics;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    internal static class TodGoldBoltEditing
    {
        internal sealed record World(int Id, string Name, int Total, int Offset);
        internal sealed record Plan(IReadOnlyDictionary<int, uint> Masks, int Before, int Collected,
            uint Spent, int ChangedBits, int AddedBits, bool AwardGolden)
        {
            internal int Balance => unchecked((int)((uint)Collected - Spent));
        }
        internal static readonly IReadOnlyList<World> Worlds = ReadWorlds();
        private static readonly HashSet<string> Keys = Worlds.SelectMany(world => Enumerable.Range(0, world.Total)
            .Select(bit => Key(world.Id, bit))).ToHashSet(StringComparer.Ordinal);
        internal static string Key(int world, int bit) => $"gold_bolt_{world}_{bit}";

        private static IReadOnlyList<World> ReadWorlds()
        {
            var worlds = TodResearch.Map.GetProperty("collectibles").GetProperty("special_bolts").GetProperty("catalog")
                .EnumerateArray().Select(row => new World(row.GetProperty("id").GetInt32(),
                    CultureInfo.InvariantCulture.TextInfo.ToTitleCase(row.GetProperty("enum").GetString()["LEVEL_".Length..]
                        .Replace('_', ' ').ToLowerInvariant()), row.GetProperty("total").GetInt32(),
                    TodResearch.Offset(row.GetProperty("mask_offset")))).ToArray();
            if (worlds.Length != 19 || worlds.Sum(world => world.Total) != 32 ||
                worlds.Where((world, index) => world.Id != index || world.Offset != 0x874 + index * 0x408 ||
                    world.Total < 0 || world.Total > 4).Any())
                throw new InvalidDataException("The bundled gold bolt catalog is not the verified nineteen-world table.");
            return Array.AsReadOnly(worlds);
        }

        internal static void AddFields(byte[] data, List<TodEditField> fields)
        {
            int collected = Worlds.Sum(world => BitOperations.PopCount(BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(world.Offset, 4))));
            uint spent = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(0x424, 4));
            if (spent > collected) return; // An invalid wallet stays inspection-only; never repair it implicitly.
            foreach (var world in Worlds)
            {
                uint mask = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(world.Offset, 4));
                // The initializer numbers matching collectors from zero. Limit
                // editing to each shipped total, not all 32 possible native IDs.
                // No physical pickup positions or later runtime layout inferred.
                for (int bit = 0; bit < world.Total; bit++)
                    fields.Add(new(Key(world.Id, bit), $"Bolt {bit + 1} (local ID {bit})", "Gold bolts", world.Offset,
                        TodEditStorage.GoldBoltBit, (mask & (1u << bit)) != 0 ? 1 : 0, 1));
            }
        }

        internal static Plan Preview(byte[] data, IReadOnlyDictionary<string, decimal> edits)
        {
            foreach (string key in edits.Keys.Where(key => key.StartsWith("gold_bolt_", StringComparison.Ordinal)))
                if (!Keys.Contains(key)) throw new InvalidDataException("This gold bolt ID is not editable: " + key);
            var masks = new Dictionary<int, uint>();
            int before = 0, after = 0, changes = 0, additions = 0;
            foreach (var world in Worlds)
            {
                uint original = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(world.Offset, 4)), mask = original;
                for (int bit = 0; bit < world.Total; bit++)
                {
                    if (!edits.TryGetValue(Key(world.Id, bit), out decimal value)) continue;
                    if (value is not (0 or 1)) throw new InvalidDataException("Gold bolt choices must be collected or uncollected.");
                    mask = value == 1 ? mask | (1u << bit) : mask & ~(1u << bit);
                }
                masks[world.Offset] = mask;
                before += BitOperations.PopCount(original); after += BitOperations.PopCount(mask);
                changes += BitOperations.PopCount(mask ^ original);
                additions += BitOperations.PopCount(mask & ~original);
            }
            uint spent = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(0x424, 4));
            if (changes != 0 && (spent > before || spent > after))
                throw new InvalidDataException("Gold bolt edits cannot leave fewer collected bolts than the saved spent amount. Add bolts before removing others; the spent word is never changed.");
            bool complete = Worlds.All(world => BitOperations.PopCount(masks[world.Offset]) >= world.Total);
            // Native OR calls scan all world counts, even for duplicate calls.
            // Editor no-ops deliberately do not repair old award mismatches.
            return new(new ReadOnlyDictionary<int, uint>(masks), before, after, spent, changes, additions, additions != 0 && complete);
        }

        internal static void Apply(byte[] result, Plan plan)
        {
            foreach (var mask in plan.Masks)
                if (BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(mask.Key, 4)) != mask.Value)
                    BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(mask.Key, 4), mask.Value);
        }
    }
}
