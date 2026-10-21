using System;
using System.Buffers.Binary;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static byte[] UnownedAppearanceFixture()
    {
        byte[] data = EditableFixture();
        data.AsSpan(0x444, 20).Clear();
        data.AsSpan(0x45C, 36).Clear();
        return data;
    }

    private static void AppearanceOwnershipChecks()
    {
        Check("All fourteen appearance grants change only their ownership word", () =>
        {
            byte[] data = UnownedAppearanceFixture(), before = data.ToArray();
            var grants = TodSaveEditing.Fields(data, "BCUS98127")
                .Where(field => field.Storage == TodEditStorage.OwnershipGrant).ToArray();
            Equal(14, grants.Length);
            foreach (var field in grants)
            {
                byte[] expected = data.ToArray();
                BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(field.Offset, 4), 1);
                byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits((field.Key, 1)));
                True(expected.SequenceEqual(result), "Grant must not equip, charge currency or change availability/progress.");
                True(before.SequenceEqual(data), "The input snapshot must stay detached.");
                True(result.SequenceEqual(TodSaveEditing.Apply(result, "BCUS98127", Edits((field.Key, 1)))), "Reapplying a grant is a no-op.");
            }
        });
        Check("Appearance ownership is add-only and preserves noncanonical owned words", () =>
        {
            byte[] data = UnownedAppearanceFixture();
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x454, 4), 0x80000000);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x478, 4), 0xFFFFFFFF);
            True(data.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("armor_owned_4", 1), ("skin_owned_7", 1), ("skin_owned_8", 0)))), "Nonzero owned words must not be normalized.");
            foreach (var edit in new[] { ("armor_owned_4", 0m), ("skin_owned_7", 0m),
                ("skin_owned_8", -1m), ("skin_owned_8", 0.5m), ("skin_owned_8", 2m),
                ("armor_owned_5", 1m), ("skin_owned_9", 1m) })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(edit)));
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCES00052", Edits(("skin_owned_7", 1))));
            byte[] malformed = data.ToArray(); malformed[3] = 99;
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(malformed, "BCUS98127", Edits(("armor_owned_4", 1))));
        });
        Check("Grant and selection compose without depending on dictionary order", () =>
        {
            byte[] data = UnownedAppearanceFixture();
            var edits = new[] { ("skin", 7m), ("armor", 4m), ("skin_owned_7", 1m), ("armor_owned_4", 1m) };
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits(edits));
            byte[] expected = data.ToArray();
            foreach (int offset in new[] { 0x454, 0x478 }) BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(offset, 4), 1);
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x458, 4), 4);
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x480, 4), 7);
            True(expected.SequenceEqual(result), "Only requested ownership and selected IDs may change.");
            True(result.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(edits.Reverse().ToArray()))), "Request order must not matter.");
            foreach (var invalid in new[] { Edits(("skin", 7)), Edits(("armor", 4)),
                Edits(("skin", 7), ("skin_owned_7", 0)), Edits(("armor", 4), ("armor_owned_4", 0.5m)) })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", invalid));
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x480, 4), uint.MaxValue);
            True(data.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("skin", uint.MaxValue)))), "Unknown current selection must still be preservable.");
        });
        Check("Bulk actions retain staged appearance grants and selections", () =>
        {
            byte[] data = UnownedAppearanceFixture();
            var staged = Edits(("skin", 7), ("skin_owned_7", 1), ("armor_owned_4", 1));
            var plan = TodSaveEditing.PlanBulk(data, "BCUS98127", staged, TodBulkEdit.RefillSupportedAmmo);
            foreach (var edit in staged) Equal(edit.Value, plan[edit.Key]);
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", plan);
            Equal(1u, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0x454, 4)));
            Equal(1u, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0x478, 4)));
            Equal(7u, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0x480, 4)));
        });
        Check("Appearance UI stages grants, offers newly owned choices and cancels dependent selections", () =>
        {
            byte[] data = UnownedAppearanceFixture(), before = data.ToArray();
            using var editor = new TodSaveEditingControl();
            editor.LoadSnapshot(data, "BCUS98127");
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            ComboBox Input(string key) => editor.Controls.Find("MappedEdit_" + key, true).Cast<ComboBox>().Single();
            void Choose(string key, decimal value)
            {
                var input = Input(key);
                input.SelectedItem = input.Items.Cast<TodEditOption>().Single(option => option.Value == value);
            }
            category.SelectedItem = "Appearance";
            True(!Input("skin").Items.Cast<TodEditOption>().Any(option => option.Value == 7), "Unowned skin cannot be selected without a grant.");
            category.SelectedItem = "Skin unlocks"; Choose("skin_owned_7", 1);
            category.SelectedItem = "Armor unlocks"; Choose("armor_owned_4", 1);
            category.SelectedItem = "Appearance"; Choose("skin", 7); Choose("armor", 4);
            Equal(7m, editor.PendingEdits["skin"]); Equal(4m, editor.PendingEdits["armor"]);
            category.SelectedItem = "Skin unlocks"; Choose("skin_owned_7", 0);
            True(!editor.PendingEdits.ContainsKey("skin") && !editor.PendingEdits.ContainsKey("skin_owned_7"), "Cancelling a grant must remove its dependent selection.");
            Equal(4m, editor.PendingEdits["armor"]);
            category.SelectedItem = "Appearance";
            True(!Input("skin").Items.Cast<TodEditOption>().Any(option => option.Value == 7), "Cancelled grant must disappear from selection choices.");
            category.SelectedItem = "Armor unlocks"; Choose("armor_owned_4", 0);
            True(!editor.HasChanges && before.SequenceEqual(data), "Cancelling both grants restores clean staging, not source writes.");
            editor.LoadSnapshot(TodSaveEditing.Apply(data, "BCUS98127", Edits(("skin_owned_7", 1))), "BCUS98127");
            category.SelectedItem = "Skin unlocks";
            True(!Input("skin_owned_7").Enabled, "Already-owned grants must be read-only.");
            editor.LoadSnapshot(data, "BCES00052");
            True(!editor.HasChanges && !category.Items.Contains("Skin unlocks"), "Ownership edits must not leak across regions.");
        });
    }
}
