using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // Only serialized integer XP is editable. Runtime level, health and the
    // fractional accumulator are not save fields. Targets are shipped config
    // rows, not confirmed player-facing level numbers or active runtime data.
    internal static class TodHeroXpEditing
    {
        internal sealed record Target(int Index, uint Xp, float MaximumHealth);
        internal static readonly IReadOnlyList<Target> Targets = ReadTargets();
        internal static uint MaximumXp => Targets[Targets.Count - 1].Xp;

        private static IReadOnlyList<Target> ReadTargets()
        {
            var targets = TodResearch.Map.GetProperty("hero_config_assets").GetProperty("rows")
                .EnumerateArray().Select(row => new Target(row.GetProperty("index").GetInt32(),
                    row.GetProperty("xp").GetUInt32(), row.GetProperty("hp").GetSingle())).ToArray();
            if (targets.Length != 98 || targets[0].Xp != 0 || targets[^1].Xp != 989000 ||
                targets.Where((target, index) => target.Index != index || target.Xp > (1u << 24) ||
                    !float.IsFinite(target.MaximumHealth) || target.MaximumHealth <= 0 ||
                    (index > 0 && target.Xp <= targets[index - 1].Xp)).Any())
                throw new InvalidDataException("The bundled hero XP reference table is not the verified 98-row catalog.");
            return Array.AsReadOnly(targets);
        }

        internal static Target ReferenceFor(decimal xp) => xp < 0 || xp > MaximumXp || xp != decimal.Truncate(xp)
            ? null : Targets.Last(target => target.Xp <= xp);

        internal static void AddFields(byte[] data, List<TodEditField> fields)
        {
            uint current = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(0x418, 4));
            // Existing values beyond the reference range can be preserved,
            // but every changed value must satisfy the separate editor bound.
            fields.Add(new("hero_xp", "Hero XP", "Hero XP", 0x418, TodEditStorage.HeroXp,
                current, Math.Max(current, MaximumXp)));
        }
    }
}
