using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static byte[] StatisticsFixture()
    {
        byte[] data = EditableFixture();
        for (int id = 1; id <= 22; id++) BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x56D8 + 4 * id, 4), 1);
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8758, 4), 3);
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x875C, 4), 2);
        BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x8760, 4), 1f);
        return data;
    }

    private static void StatisticsEditingChecks(string root)
    {
        Check("Named stat edits change only the requested words and preserve arena sentinels/rewards", () =>
        {
            byte[] data = StatisticsFixture(), before = data.ToArray(), expected = data.ToArray();
            var edits = Edits(("decryptor_wins", uint.MaxValue), ("decryptor_sixaxis_losses", 0), ("decryptor_spark_speed", 0.6m));
            for (int id = 1; id <= 22; id++)
            {
                edits["arena_wins_" + id] = id == 22 ? int.MaxValue : id + 1;
                BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x56D8 + id * 4, 4), (uint)edits["arena_wins_" + id]);
            }
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x8758, 4), uint.MaxValue);
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x875C, 4), 0);
            BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(0x8760, 4), 0.6f);
            True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", edits)), "No inventory, skills, story flags, reset counters or unrelated bytes may change.");
            True(before.SequenceEqual(data), "The source snapshot must remain unchanged.");
            var fields = TodSaveEditing.Fields(data, "BCUS98127");
            Equal(22, fields.Count(field => field.Category == "Arena challenge stats"));
            Equal(3, fields.Count(field => field.Category == "Decryptor stats"));
        });
        Check("Arena edits cannot create first wins, clear completion or reinterpret negative counts", () =>
        {
            byte[] data = StatisticsFixture();
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x56E8, 4), 0); // Essential first-victory gadget reward.
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x5708, 4), 0xFFFFFFFF);
            var fields = TodSaveEditing.Fields(data, "BCUS98127");
            var unplayed = fields.Single(field => field.Key == "arena_wins_4");
            Equal(0m, unplayed.Minimum); Equal(0m, unplayed.Maximum);
            True(!fields.Any(field => field.Key == "arena_wins_12"), "Signed-negative counts remain inspection-only.");
            foreach (var edit in new[] { ("arena_wins_4", 1m), ("arena_wins_12", 1m), ("arena_wins_1", 0m),
                ("arena_wins_0", 1m), ("arena_wins_23", 1m), ("reset_category_2", 1m) })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(edit)));
            True(data.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("arena_wins_4", 0)))), "An explicit zero no-op must be byte-identical.");
        });
        Check("Stats reject fractional counters, overflow, invalid speed and unsupported layouts", () =>
        {
            byte[] data = StatisticsFixture();
            foreach (var edit in new[] { ("decryptor_wins", -1m), ("decryptor_wins", uint.MaxValue + 1m),
                ("decryptor_sixaxis_losses", 1.5m), ("arena_wins_1", 1.5m), ("arena_wins_1", int.MaxValue + 1m),
                ("decryptor_spark_speed", 0.59m), ("decryptor_spark_speed", 1.01m) })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(edit)));
            foreach (string region in new[] { "BCES00052", "BCUS98124", "" })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, region, Edits(("decryptor_wins", 5))));
            foreach (uint bits in new[] { 0x7FC12345u, 0x7F800000u, 0xBF800000u, 0u, 0x3F800001u })
            {
                BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8760, 4), bits);
                True(!TodSaveEditing.Fields(data, "BCUS98127").Any(field => field.Key == "decryptor_spark_speed"), "Invalid speed must not be normalized into an editable value.");
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("decryptor_spark_speed", 1))));
                var result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("decryptor_wins", 5)));
                Equal(bits, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0x8760, 4)));
            }
        });
        Check("Counter-only wins do not run Decryptor outcome resets and semantic no-ops retain bytes", () =>
        {
            byte[] data = StatisticsFixture();
            BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x8760, 4), 0.8f);
            var result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("decryptor_wins", 6)));
            Equal(2u, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0x875C, 4)));
            Equal(0.8f, BinaryPrimitives.ReadSingleBigEndian(result.AsSpan(0x8760, 4)));
            var noOps = TodSaveEditing.Fields(data, "BCUS98127")
                .Where(field => field.Category is "Decryptor stats" or "Arena challenge stats")
                .ToDictionary(field => field.Key, field => field.Current);
            True(data.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", noOps)), "All stat no-ops must preserve exact raw values.");
        });
        Check("Stat textboxes validate integers, retain hidden input and never expose unrelated bulk actions", () =>
        {
            byte[] data = StatisticsFixture(); BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x56E8, 4), 0);
            using var form = new Form { ClientSize = new Size(1100, 850), Font = new Font("Segoe UI", 13) };
            using var editor = new TodSaveEditingControl(); form.Controls.Add(editor); editor.LoadSnapshot(data, "BCUS98127"); form.Show();
            var categories = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            Alphabetical(categories); categories.SelectedItem = "Decryptor stats";
            var wins = editor.Controls.Find("MappedEdit_decryptor_wins", true).Cast<NumericTextBox>().Single();
            True(!wins.AllowDecimal && !editor.HasChanges, "Counters must load cleanly as whole-number textboxes.");
            wins.Text = "4294967295"; Equal((decimal)uint.MaxValue, editor.PendingEdits["decryptor_wins"]);
            wins.Text = "1.5"; True(editor.HasInvalidInputs, "Fractional counters must block saving.");
            categories.SelectedItem = "Arena challenge stats";
            var unplayed = editor.Controls.Find("MappedEdit_arena_wins_4", true).Cast<NumericTextBox>().Single();
            True(unplayed.ReadOnly, "First-win edits must not be offered by the UI.");
            True(!editor.Controls.Find("MappedBulkActions", true).Single().Visible, "Stats must not show ammo/level actions.");
            True(!editor.ValidateInputs() && categories.SelectedItem.ToString() == "Decryptor stats", "Hidden invalid stat input must be surfaced.");
            wins = editor.Controls.Find("MappedEdit_decryptor_wins", true).Cast<NumericTextBox>().Single();
            Equal("1.5", wins.Text); wins.Text = "3"; True(!editor.HasChanges, "Reverting must clear the invalid/staged stat.");
            categories.SelectedItem = "Arena challenge stats";
            var arena = editor.Controls.Find("MappedEdit_arena_wins_1", true).Cast<NumericTextBox>().Single();
            arena.Text = "0"; True(editor.HasInvalidInputs, "A completed arena challenge cannot be cleared.");
            arena.Text = "2"; Equal(2m, editor.PendingEdits["arena_wins_1"]);
            editor.LoadSnapshot(data, "BCES00052"); True(!editor.HasChanges && categories.Items.Count == 0, "No region or staging leakage.");
        });
        Check("Stats save through the existing backed-up decrypted-save workflow", () =>
        {
            string folder = Fixture(root, "BCUS98127"); byte[] data = StatisticsFixture();
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), data);
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "stat-backups"));
            var edits = Edits(("arena_wins_1", 9), ("decryptor_wins", 12), ("decryptor_spark_speed", 0.75m));
            string backup = session.Save(session.CharacterBolts, session.Raritanium, mappedEdits: edits);
            True(File.ReadAllBytes(Path.Combine(backup, "GAME.SAV")).SequenceEqual(data), "Saving must retain the original data in its backup.");
            True(File.ReadAllBytes(Path.Combine(folder, "GAME.SAV")).SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", edits)),
                "The saved file must contain only the validated requested edits.");
        });
    }

    private static void StatisticsWithSave(string folder, string root)
    {
        var before = Snapshot(folder);
        using var session = SaveSession.Open(folder, new Encryption(), backupRoot: Path.Combine(root, "actual-stat-backup"));
        byte[] data = session.ReadInspectionData();
        var fields = TodSaveEditing.Fields(data, session.Metadata.Region)
            .Where(field => field.Category is "Decryptor stats" or "Arena challenge stats").ToArray();
        foreach (var field in fields)
        {
            decimal target = field.Maximum == field.Minimum ? field.Current :
                field.Current == field.Maximum ? field.Minimum : field.Maximum;
            byte[] changed = TodSaveEditing.Apply(data, session.Metadata.Region, Edits((field.Key, target)));
            True(data.AsSpan(0, field.Offset).SequenceEqual(changed.AsSpan(0, field.Offset)) &&
                data.AsSpan(field.Offset + 4).SequenceEqual(changed.AsSpan(field.Offset + 4)),
                field.Key + " must only affect its four-byte field.");
        }
        Same(before, Snapshot(folder));
        Console.WriteLine($"Actual save: {fields.Length} stat fields, {fields.Count(field => field.Maximum > field.Minimum)} editable. Each change affects only its four-byte field; source folder unchanged.");
    }
}
