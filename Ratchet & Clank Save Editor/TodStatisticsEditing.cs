using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    internal static class TodStatisticsEditing
    {
        internal static void AddFields(byte[] data, List<TodEditField> fields)
        {
            // 3B5AB8 publishes these unsigned counters. This is a stat edit,
            // not DECRYPTWIN/DECRYPTLOSE execution or a lifetime-stat claim.
            foreach (var stat in new[] { ("decryptor_wins", "Recorded Decryptor wins", 0x8758),
                ("decryptor_sixaxis_losses", "Sixaxis losses since last success", 0x875C) })
                fields.Add(new(stat.Item1, stat.Item2, "Decryptor stats", stat.Item3,
                    TodEditStorage.UInt32Counter, BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(stat.Item3, 4)), uint.MaxValue));

            // Native adaptation bounds; this scales spark speed, not overall difficulty.
            float speed = BinaryPrimitives.ReadSingleBigEndian(data.AsSpan(0x8760, 4));
            if (float.IsFinite(speed) && speed >= 0.6f && speed <= 1f)
                fields.Add(new("decryptor_spark_speed", "Spark-speed multiplier (0.6–1)", "Decryptor stats", 0x8760,
                    TodEditStorage.Float, (decimal)speed, 1, Minimum: 0.6m));

            var catalog = TodResearch.Map.GetProperty("arena_challenges").GetProperty("catalog").EnumerateArray().ToArray();
            if (catalog.Length != 22 || catalog.Where((entry, index) => entry.GetProperty("id").GetInt32() != index + 1 ||
                TodResearch.Offset(entry.GetProperty("save_offset")) != 0x56D8 + (index + 1) * 4).Any())
                throw new InvalidDataException("The bundled arena catalog does not match the verified counter bank.");
            foreach (var entry in catalog.OrderBy(entry => entry.GetProperty("shipped").GetProperty("comment").GetString(),
                StringComparer.CurrentCultureIgnoreCase))
            {
                int id = entry.GetProperty("id").GetInt32(), offset = TodResearch.Offset(entry.GetProperty("save_offset"));
                uint wins = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(offset, 4));
                if (wins > int.MaxValue) continue; // Signed-negative baselines remain inspection-only.
                string label = entry.GetProperty("shipped").GetProperty("comment").GetString() + " · wins";
                if (wins == 0) label += " (not won yet; read-only)";
                // Preserve the positive-completion predicate used by the menu.
                // Counter-only edits must not suppress first-victory rewards or
                // reset earned progress; story flags are separate script writes.
                fields.Add(new("arena_wins_" + id, label, "Arena challenge stats", offset,
                    TodEditStorage.UInt32Counter, wins, wins == 0 ? 0 : int.MaxValue, Minimum: wins == 0 ? 0 : 1));
            }
        }
    }
}
