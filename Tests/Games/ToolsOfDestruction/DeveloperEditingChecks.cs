using System;
using System.Buffers.Binary;
using System.IO;
using System.Linq;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static void DeveloperEditingChecks()
    {
        Check("Native blueprint action preserves unknown bits and every unrelated byte", () =>
        {
            foreach (uint mask in new[] { 0u, 0x80000001u, uint.MaxValue })
            {
                byte[] data = EditableFixture(); BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x86F4, 4), mask);
                byte[] before = data.ToArray(), expected = data.ToArray();
                BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x86F4, 4), mask | 0x0007DEE4);
                True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("dev_all_blueprints", 1)))), "Only the native grant-all mask may be ORed.");
                True(before.SequenceEqual(data), "Source must not change.");
                True(before.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("dev_all_blueprints", 0)))), "Do not run must preserve every byte.");
            }
        });
        Check("Native bonus helper sets840 and only replaces zero states, without skill awards", () =>
        {
            byte[] data = BonusFixture(999), expected = data.ToArray();
            for (int index = 0; index < 14; index++) data[0x86F8 + index] = (byte)(index % 5 == 0 ? 0 : index % 5 == 1 ? 255 : index % 5);
            BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x8710, 8), 0xF123456789ABCDEF);
            byte[] before = data.ToArray(); expected = data.ToArray();
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x8708, 4), 840);
            for (int index = 0; index < 14; index++) if (expected[0x86F8 + index] == 0) expected[0x86F8 + index] = 1;
            True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("dev_unlock_bonuses", 1)))), "This is the native helper, not all skill awards or a score-max operation.");
            True(data.SequenceEqual(before), "Unknown nonzero states and earned bits must remain untouched.");
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x86F4, 4), BinaryPrimitives.ReadUInt32BigEndian(before.AsSpan(0x86F4, 4)) | 0x0007DEE4);
            True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("dev_all_blueprints", 1), ("dev_unlock_bonuses", 1)))), "Both native actions must compose without collateral writes.");
        });
        Check("Developer actions reject invalid values and conflicting bonus selections", () =>
        {
            byte[] data = BonusFixture(), before = data.ToArray();
            foreach (string key in new[] { "dev_all_blueprints", "dev_unlock_bonuses" })
                foreach (decimal value in new[] { -1m, 0.5m, 2m })
                    Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits((key, value))));
            foreach (decimal value in new[] { 0m, 1m })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("dev_unlock_bonuses", 1), ("bonus_hero_head", value))));
            foreach (string key in new[] { "dev_console", "dev_ally_debug", "dev_runtime_ammo" })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits((key, 1))));
            True(data.SequenceEqual(before), "A rejected action must leave the original unchanged.");
        });
    }
}
