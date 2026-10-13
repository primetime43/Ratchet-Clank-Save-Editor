using System;
using System.Buffers.Binary;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static byte[] GoldBoltFixture(bool complete = false)
    {
        byte[] data = EditableFixture();
        foreach (var world in TodResearch.Map.GetProperty("collectibles").GetProperty("special_bolts").GetProperty("catalog").EnumerateArray())
        {
            int count = world.GetProperty("total").GetInt32();
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(TodResearch.Offset(world.GetProperty("mask_offset")), 4),
                complete ? (1u << count) - 1 : 0);
        }
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x424, 4), 0);
        BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x8710, 8), 0);
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8708, 4), 100);
        return data;
    }

    private static void GoldBoltEditingChecks(string root)
    {
        Check("Gold bolt allowlist contains exactly 32 local bits and each partial change preserves all unrelated bytes", () =>
        {
            byte[] data = GoldBoltFixture(), before = data.ToArray();
            var fields = TodSaveEditing.Fields(data, "BCUS98127").Where(field => field.Storage == TodEditStorage.GoldBoltBit).ToArray();
            Equal(32, fields.Length);
            True(!fields.Any(field => field.Offset is 0x874 or 0x148C or 0x550C), "Zero-total worlds and slot19 have no editable bits.");
            foreach (var field in fields)
            {
                int bit = int.Parse(field.Key.Split('_')[3]);
                byte[] expected = data.ToArray(); BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(field.Offset, 4), 1u << bit);
                byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits((field.Key, 1)));
                True(expected.SequenceEqual(result), "Partial collection writes just its BE32 bit, not currency, flags or awards.");
                True(before.SequenceEqual(data), "The original snapshot stays detached.");
                True(data.SequenceEqual(TodSaveEditing.Apply(result, "BCUS98127", Edits((field.Key, 0)))), "An unspent partial bolt can be removed without touching other bytes.");
            }
        });
        Check("Unknown collectible bits and initialized slot19 survive all edits", () =>
        {
            byte[] data = GoldBoltFixture();
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0xC7C, 4), 0x80000000);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x550C, 4), uint.MaxValue);
            byte[] expected = data.ToArray(); BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0xC7C, 4), 0x80000001);
            True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("gold_bolt_1_0", 1)))), "Unexpected bits and slot19 are preserved, not normalized.");
            foreach (var edit in new[] { ("gold_bolt_1_1", 1m), ("gold_bolt_10_4", 1m), ("gold_bolt_10_31", 1m),
                ("gold_bolt_19_0", 1m), ("gold_bolt_0_0", 1m), ("gold_bolt_3_0", 1m),
                ("gold_bolt_1_0", -1m), ("gold_bolt_1_0", 0.5m), ("gold_bolt_1_0", 2m), ("special_bolts_spent", 0m) })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(edit)));
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCES00052", Edits(("gold_bolt_1_0", 1))));
        });
        Check("Spent balance rejects underflow and accepts balanced swaps independently of request order", () =>
        {
            byte[] data = GoldBoltFixture();
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x1084, 4), 3);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x424, 4), 2);
            byte[] before = data.ToArray();
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("gold_bolt_2_0", 0))));
            True(before.SequenceEqual(data), "A rejected removal must not mutate the snapshot.");
            var swap = new[] { ("gold_bolt_2_0", 0m), ("gold_bolt_1_0", 1m) };
            byte[] expected = data.ToArray();
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x1084, 4), 2);
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0xC7C, 4), 1);
            True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(swap))), "Swapping preserves spent and the final collected balance.");
            True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(swap.Reverse().ToArray()))), "Only the complete batch determines the balance.");
            foreach (uint spent in new uint[] { 3, 0x80000000, uint.MaxValue })
            {
                BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x424, 4), spent);
                True(!TodSaveEditing.Fields(data, "BCUS98127").Any(field => field.Storage == TodEditStorage.GoldBoltBit), "Invalid saved wallets stay inspection-only.");
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("gold_bolt_1_0", 1))));
                byte[] settings = TodSaveEditing.Apply(data, "BCUS98127", Edits(("subtitles", 1)));
                Equal(spent, BinaryPrimitives.ReadUInt32BigEndian(settings.AsSpan(0x424, 4)));
            }
        });
        Check("Final gold bolt awards GOLDEN and HARDCORE once with native weighted points", () =>
        {
            byte[] data = GoldBoltFixture(true);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0xC7C, 4), 0);
            const ulong ordinaryWithoutGolden = ((1UL << 59) - 1) & ~(1UL << 46);
            BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x8710, 8), 0xF000000000000000 | ordinaryWithoutGolden);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8708, 4), 900);
            byte[] expected = data.ToArray();
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0xC7C, 4), 1);
            BinaryPrimitives.WriteUInt64BigEndian(expected.AsSpan(0x8710, 8), 0xFFFFFFFFFFFFFFFF);
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x8708, 4), 960);
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("gold_bolt_1_0", 1)));
            True(expected.SequenceEqual(result), "Only final bit, GOLDEN/HARDCORE bits and their 40+20 points may change.");
            True(result.SequenceEqual(TodSaveEditing.Apply(result, "BCUS98127", Edits(("gold_bolt_1_0", 1)))), "Duplicate collection must not double-count awards.");
            var edits = new[] { ("gold_bolt_1_0", 1m), ("skill_award_46", 1m) };
            True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(edits))), "Explicit and automatic GOLDEN share one publication.");
            True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(edits.Reverse().ToArray()))), "Explicit award order must not matter.");
        });
        Check("Collection removals and no-ops preserve earned awards without repairing old mismatches", () =>
        {
            byte[] data = GoldBoltFixture(true);
            BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x8710, 8), (1UL << 60) - 1);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8708, 4), 750);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x424, 4), 31);
            byte[] expected = data.ToArray(); BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0xC7C, 4), 0);
            True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("gold_bolt_1_0", 0)))), "Removing an unspent bit does not revoke earned skills or points.");
            BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x8710, 8), 0);
            True(data.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("gold_bolt_1_0", 1)))), "No-op does not repair a missing GOLDEN award.");
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0xC7C, 4), 0);
            BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x8710, 8), (1UL << 59) - 1);
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("gold_bolt_1_0", 1)));
            Equal((1UL << 59) - 1, BinaryPrimitives.ReadUInt64BigEndian(result.AsSpan(0x8710, 8)));
            Equal(750u, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0x8708, 4)));
        });
        Check("Completion uses native all-bit counts and excludes slot19", () =>
        {
            byte[] data = GoldBoltFixture(true);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0xC7C, 4), 0x80000000);
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("gold_bolt_1_0", 1)));
            Equal(0x80000001u, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0xC7C, 4)));
            Equal(1UL << 46, BinaryPrimitives.ReadUInt64BigEndian(result.AsSpan(0x8710, 8)));
            Equal(140u, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0x8708, 4)));
            data = GoldBoltFixture();
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x550C, 4), uint.MaxValue);
            result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("gold_bolt_1_0", 1)));
            Equal(0UL, BinaryPrimitives.ReadUInt64BigEndian(result.AsSpan(0x8710, 8)));
        });
        Check("Automatic gold awards reject overflow and bonus-score conflicts before any mask write", () =>
        {
            byte[] data = GoldBoltFixture(true); BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0xC7C, 4), 0);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8708, 4), uint.MaxValue - 39);
            byte[] before = data.ToArray();
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("gold_bolt_1_0", 1))));
            True(before.SequenceEqual(data), "Overflow must not publish a mask or award into the original.");
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8708, 4), 100);
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("gold_bolt_1_0", 1), ("dev_unlock_bonuses", 1))));
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("dev_unlock_bonuses", 1), ("gold_bolt_1_0", 1))));
            var plan = TodSaveEditing.PlanBulk(data, "BCUS98127", Edits(("gold_bolt_1_0", 1)), TodBulkEdit.RefillSupportedAmmo);
            Equal(1m, plan["gold_bolt_1_0"]);
            Equal(140u, BinaryPrimitives.ReadUInt32BigEndian(TodSaveEditing.Apply(data, "BCUS98127", plan).AsSpan(0x8708, 4)));
        });
        Check("Per-planet UI preserves staging and refuses a spent-balance underflow", () =>
        {
            byte[] data = GoldBoltFixture();
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x1084, 4), 3);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x424, 4), 2);
            using var editor = new TodSaveEditingControl(); editor.LoadSnapshot(data, "BCUS98127");
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single(); category.SelectedItem = "Gold bolts";
            CheckedListBox List() => editor.Controls.Find("MappedGoldBoltChecks", true).Cast<CheckedListBox>().Single();
            void Planet(decimal id)
            {
                var planets = editor.Controls.Find("MappedGoldBoltPlanet", true).Cast<ComboBox>().Single();
                planets.SelectedItem = planets.Items.Cast<TodEditOption>().Single(option => option.Value == id);
            }
            Planet(2); List().SetItemChecked(0, false);
            True(List().GetItemChecked(0) && !editor.HasChanges, "A rejected removal must restore its checkbox and clean staging.");
            Planet(1); List().SetItemChecked(0, true); Planet(2); List().SetItemChecked(0, false);
            Equal(1m, editor.PendingEdits["gold_bolt_1_0"]); Equal(0m, editor.PendingEdits["gold_bolt_2_0"]);
            category.SelectedItem = "Game settings"; category.SelectedItem = "Gold bolts";
            True(!List().GetItemChecked(0) && List().GetItemChecked(1), "Planet selection and checked bits survive category changes.");
            Planet(0); True(List().Items.Count == 0 && !List().Enabled, "A zero-total world has no invented pickups.");
            editor.LoadSnapshot(data, "BCES00052"); True(!editor.HasChanges && !category.Items.Contains("Gold bolts"), "No USA staging leaks across games.");
        });
        Check("Linked GOLDEN/HARDCORE preview cannot be unchecked while collection supplies it", () =>
        {
            byte[] data = GoldBoltFixture(true); BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0xC7C, 4), 0);
            BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x8710, 8), ((1UL << 59) - 1) & ~(1UL << 46));
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8708, 4), 690);
            using var editor = new TodSaveEditingControl(); editor.LoadSnapshot(data, "BCUS98127");
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single(); category.SelectedItem = "Gold bolts";
            editor.Controls.Find("MappedGoldBoltChecks", true).Cast<CheckedListBox>().Single().SetItemChecked(0, true);
            category.SelectedItem = "Skill awards";
            var skills = editor.Controls.Find("MappedSkillAwards", true).Cast<CheckedListBox>().Single();
            True(skills.GetItemChecked(46) && skills.GetItemChecked(59), "Both linked awards must preview as earned.");
            skills.SetItemChecked(46, false); skills.SetItemChecked(59, false);
            True(skills.GetItemChecked(46) && skills.GetItemChecked(59), "Collection-supplied awards must not be independently removed.");
            category.SelectedItem = "Gold bolts";
            editor.Controls.Find("MappedGoldBoltChecks", true).Cast<CheckedListBox>().Single().SetItemChecked(0, false);
            category.SelectedItem = "Skill awards";
            skills = editor.Controls.Find("MappedSkillAwards", true).Cast<CheckedListBox>().Single();
            True(!skills.GetItemChecked(46) && !skills.GetItemChecked(59) && !editor.HasChanges, "Cancelling collection removes derived awards, not saved awards.");
        });
        Check("Save All roundtrip retains gold masks, spent balance and linked awards", () =>
        {
            string folder = Fixture(root, "BCUS98127"), backups = Path.Combine(root, "gold-bolt-backups");
            byte[] data = GoldBoltFixture(true); BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0xC7C, 4), 0);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x424, 4), 31);
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), data);
            using (var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: backups))
                session.Save(124, 46, backups, Edits(("gold_bolt_1_0", 1)));
            using var reopened = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: backups);
            byte[] result = reopened.ReadInspectionData();
            Equal(1u, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0xC7C, 4)));
            Equal(31u, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0x424, 4)));
            Equal(1UL << 46, BinaryPrimitives.ReadUInt64BigEndian(result.AsSpan(0x8710, 8)));
            Equal(140u, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0x8708, 4)));
        });
    }
}
