using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Globalization;
using System.IO;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // Add-only saved writes from35D5D0. No runtime notifications, removal,
    // producer-progress changes or reconciliation of old score/bit mismatches.
    internal static class TodSkillAwardEditing
    {
        private const int ScoreOffset = 0x8708, BitsOffset = 0x8710;
        private const ulong Required = (1UL << 59) - 1;
        internal sealed record Plan(ulong Bits, uint Score, int NewAwards);

        internal static int Id(TodEditField field) => int.Parse(field.Key.AsSpan("skill_award_".Length), CultureInfo.InvariantCulture);

        internal static void AddFields(byte[] data, List<TodEditField> fields)
        {
            ulong bits = BinaryPrimitives.ReadUInt64BigEndian(data.AsSpan(BitsOffset, 8));
            foreach (var skill in TodResearch.Map.GetProperty("progression").GetProperty("skill_points").GetProperty("catalog").EnumerateArray())
            {
                int id = skill.GetProperty("id").GetInt32();
                bool automatic = id == 59, earned = (bits & (1UL << id)) != 0;
                string name = skill.GetProperty("enum").GetString()["SKILLPOINT_".Length..].Replace('_', ' ').ToLowerInvariant();
                name = CultureInfo.InvariantCulture.TextInfo.ToTitleCase(name);
                string label = $"{name} · {skill.GetProperty("points").GetUInt32()} points" + (automatic ? " (automatic)" : "");
                var options = earned || automatic
                    ? new[] { new TodEditOption(0, earned ? "Already earned" : "Automatic after all other skills") }
                    : new[] { new TodEditOption(0, "Keep unchanged"), new TodEditOption(1, "Award on Save All") };
                fields.Add(new("skill_award_" + id, label, "Skill awards", BitsOffset,
                    TodEditStorage.SkillAward, 0, earned || automatic ? 0 : 1, Options: options));
            }
        }

        internal static Plan Preview(byte[] data, IReadOnlyDictionary<string, decimal> edits)
        {
            ulong bits = BinaryPrimitives.ReadUInt64BigEndian(data.AsSpan(BitsOffset, 8));
            uint originalScore = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(ScoreOffset, 4));
            ulong score = originalScore;
            int added = 0;
            var catalog = TodResearch.Map.GetProperty("progression").GetProperty("skill_points").GetProperty("catalog");
            foreach (var skill in catalog.EnumerateArray())
            {
                int id = skill.GetProperty("id").GetInt32();
                if (id == 59 || !edits.TryGetValue("skill_award_" + id, out decimal value) || value != 1 ||
                    (bits & (1UL << id)) != 0) continue;
                bits |= 1UL << id;
                score += skill.GetProperty("points").GetUInt32();
                added++;
            }
            if (added != 0)
            {
                if (edits.TryGetValue("dev_unlock_bonuses", out decimal unlock) && unlock == 1)
                    throw new InvalidDataException("Save skill awards separately from Unlock bonuses: that helper replaces the weighted score with 840.");
                // A duplicate/no-op must not repair a missing HARDCORE bit.
                if ((bits & Required) == Required && (bits & (1UL << 59)) == 0)
                {
                    bits |= 1UL << 59;
                    score += catalog[59].GetProperty("points").GetUInt32();
                    added++;
                }
            }
            // The native addition wraps; a save editor should not silently
            // turn an unusual high score into a low one and relock bonuses.
            if (score > uint.MaxValue) throw new InvalidDataException("These skill awards would overflow the saved weighted score.");
            return new(bits, (uint)score, added);
        }

        internal static void Apply(byte[] result, IReadOnlyDictionary<string, decimal> edits)
        {
            var plan = Preview(result, edits);
            if (plan.NewAwards == 0) return;
            BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(ScoreOffset, 4), plan.Score);
            BinaryPrimitives.WriteUInt64BigEndian(result.AsSpan(BitsOffset, 8), plan.Bits);
        }
    }
}
