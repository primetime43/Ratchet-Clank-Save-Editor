using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed record Rc1NanotechTier(int Level, string Name, int Capacity)
    {
        public override string ToString() => $"{Name} ({Capacity} health)";
    }
    public sealed record Rc1NanotechDefinition(int PremiumOffset, int UltraOffset, int CapacityOffset);

    public static class Rc1NanotechEditing
    {
        public const string Key = "rc1_nanotech_level";
        public static bool IsKey(string key) => key.StartsWith("rc1_nanotech_", StringComparison.Ordinal);

        public static Rc1NanotechTier State(byte[] data, string region)
        {
            if (!Rc1SaveEditing.Supports(data, region)) return null;
            var map = Rc1Research.Nanotech;
            int premium = data[map.PremiumOffset], ultra = data[map.UltraOffset];
            if (premium > 1 || ultra > 1 || ultra > premium) return null;
            var tier = Rc1Research.NanotechTiers.Single(item => item.Level == premium + ultra);
            return BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(map.CapacityOffset, 4)) == tier.Capacity ? tier : null;
        }

        internal static byte[] Apply(byte[] original, byte[] result, string region, IReadOnlyDictionary<string, decimal> edits)
        {
            foreach (var edit in edits.Where(edit => IsKey(edit.Key)))
            {
                var state = State(original, region);
                if (edit.Key != Key || state == null)
                    throw new InvalidDataException("Nanotech upgrades require consistent, supported ownership flags and health capacity.");
                var tier = Rc1Research.NanotechTiers.SingleOrDefault(item => item.Level == edit.Value);
                if (tier == null || tier.Level < state.Level)
                    throw new InvalidDataException("RC1 nanotech upgrades are add-only: choose the current tier, Premium or Ultra.");
                if (tier.Level == state.Level) continue;
                var map = Rc1Research.Nanotech;
                result[map.PremiumOffset] = 1;
                result[map.UltraOffset] = (byte)(tier.Level == 2 ? 1 : 0);
                BinaryPrimitives.WriteInt32BigEndian(result.AsSpan(map.CapacityOffset, 4), tier.Capacity);
            }
            return result;
        }
    }
}
