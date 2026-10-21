using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed record Rc1GoldBoltField(string Key, int World, string Planet, int Slot, int Offset, bool Collected);
    public sealed record Rc1GoldBoltSummary(int Collected, int Spent, int Available);

    public static class Rc1GoldBoltEditing
    {
        private const int WorldStart = 0x1544, WorldStride = 0x82A4, WorldCount = 20, FlagOffset = 0x8024;
        private static uint Word(byte[] data, int offset) => BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(offset, 4));
        public static bool IsKey(string key) => key.StartsWith("rc1_bolt_", StringComparison.Ordinal);

        public static bool Supports(byte[] data, string region)
        {
            if (!Rc1SaveEditing.Supports(data, region)) return false;
            // Other editors retain opaque world data. Collectible writes require
            // all twenty exact native block layouts, including reserved worlds.
            for (int world = 0; world < WorldCount; world++)
            {
                int start = WorldStart + world * WorldStride;
                if (Word(data, start) != WorldStride - 8) return false;
                foreach (var record in Rc1Research.WorldRecords)
                    if (Word(data, start + record.Offset - 8) != record.Id ||
                        Word(data, start + record.Offset - 4) != record.Length) return false;
                if (Word(data, start + WorldStride - 8) != uint.MaxValue || Word(data, start + WorldStride - 4) != 0) return false;
            }
            return true;
        }

        public static IReadOnlyList<Rc1GoldBoltField> Fields(byte[] data, string region)
        {
            if (!Supports(data, region)) return Array.Empty<Rc1GoldBoltField>();
            return Rc1Research.GoldBolts.Where(field => data[field.Offset] <= 1)
                .Select(field => field with { Collected = data[field.Offset] == 1 }).ToArray();
        }

        public static Rc1GoldBoltSummary Summary(byte[] data, string region)
        {
            if (!Supports(data, region)) return null;
            int collected = 0;
            for (int world = 0; world < WorldCount; world++)
                for (int slot = 0; slot < 4; slot++)
                    if (data[WorldStart + world * WorldStride + FlagOffset + slot] != 0) collected++;
            collected = Math.Min(40, collected);
            int upgrades = 37 - data.AsSpan(Rc1Research.PlayerRecords.Single(record => record.Id == 30).Offset, 37).Count((byte)0);
            int spent = Math.Min(10, upgrades) * 4;
            return new(collected, spent, Math.Clamp(collected - spent, 0, 40));
        }

        internal static byte[] Apply(byte[] original, byte[] result, string region, IReadOnlyDictionary<string, decimal> edits)
        {
            if (!edits.Keys.Any(IsKey)) return result;
            var fields = Fields(original, region).ToDictionary(field => field.Key, StringComparer.Ordinal);
            foreach (var edit in edits.Where(edit => IsKey(edit.Key)))
            {
                if (!fields.TryGetValue(edit.Key, out var field))
                    throw new InvalidDataException("Gold bolts require verified world records and a supported collection flag: " + edit.Key);
                if (edit.Value != 0 && edit.Value != 1 || field.Collected && edit.Value != 1)
                    throw new InvalidDataException("RC1 gold-bolt collection is add-only.");
                if (field.Collected || edit.Value == 0) continue;
                result[field.Offset] = 1;
                // Use the remaster's existing disabled-checksum convention only
                // for world blocks whose flags actually change. No-op preserves it.
                BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(WorldStart + field.World * WorldStride + 4, 4), uint.MaxValue);
            }
            return result;
        }
    }
}
