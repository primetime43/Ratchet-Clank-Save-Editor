using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    internal static class TodDeveloperEditing
    {
        internal static void AddFields(List<TodEditField> fields)
        {
            var options = new[] { new TodEditOption(0, "Do not run"), new TodEditOption(1, "Run on Save All") };
            fields.Add(new("dev_all_blueprints", "Grant all native blueprints", "Developer helpers", 0x86F4,
                TodEditStorage.DeveloperAction, 0, 1, Options: options));
            fields.Add(new("dev_unlock_bonuses", "Unlock bonuses (native helper)", "Developer helpers", 0x8708,
                TodEditStorage.DeveloperAction, 0, 1, Options: options));
        }

        internal static void Apply(byte[] result, IReadOnlyDictionary<string, decimal> edits,
            IReadOnlyDictionary<string, TodEditField> fields)
        {
            if (edits.TryGetValue("dev_unlock_bonuses", out decimal unlock) && unlock == 1)
            {
                if (edits.Any(edit => fields[edit.Key].Category == "Bonus effects"))
                    throw new InvalidDataException("Run Unlock bonuses separately from bonus selections, then reopen the bonus page after saving.");
                // Faithful35D480: not750 skill points or an earned-bit grant.
                BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(0x8708, 4), 840);
                for (int index = 0; index < 14; index++)
                    if (result[0x86F8 + index] == 0) result[0x86F8 + index] = 1;
            }
            if (edits.TryGetValue("dev_all_blueprints", out decimal blueprints) && blueprints == 1)
            {
                uint current = BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0x86F4, 4));
                BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(0x86F4, 4), current | 0x0007DEE4);
            }
        }
    }
}
