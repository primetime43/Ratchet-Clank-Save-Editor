using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static byte[] BonusFixture(uint score = 750)
    {
        byte[] data = EditableFixture();
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8708, 4), score);
        return data;
    }

    private static void BonusEditingChecks(string root)
    {
        Check("Cosmetic bonus fields use physical bytes and definition counts including Off", () =>
        {
            byte[] data = BonusFixture(), before = data.ToArray();
            var fields = TodSaveEditing.Fields(data, "BCUS98127").Where(field => field.Category == "Bonus effects").ToArray();
            Equal(5, fields.Length);
            foreach (var expected in new[] { ("bonus_hero_head", 0x86F9, 4), ("bonus_enemy_head", 0x86FB, 3), ("bonus_commentary", 0x86FD, 2), ("bonus_james_zurkon", 0x8701, 2), ("bonus_mirror", 0x8703, 2) })
            {
                var field = fields.Single(field => field.Key == expected.Item1);
                Equal(expected.Item2, field.Offset);
                Equal(TodEditStorage.ByteChoice, field.Storage);
                Equal(expected.Item3 - 1m, field.Maximum);
                True(field.Options.Select(option => option.Value).SequenceEqual(Enumerable.Range(0, expected.Item3).Select(value => (decimal)value)),
                    "Definition count includes Off; do not offer the count itself as a state.");
                foreach (var option in field.Options)
                {
                    byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits((field.Key, option.Value)));
                    Equal((byte)option.Value, result[field.Offset]);
                    for (int offset = 0; offset < data.Length; offset++)
                        if (offset != field.Offset) Equal(before[offset], result[offset]);
                }
            }
            True(data.SequenceEqual(before), "Bonus planning must be detached from the input.");
        });
        Check("Read-only bonus inspection explains known selections without claiming active effects", () =>
        {
            byte[] data = BonusFixture(100);
            data[0x86F9] = 3;
            data[0x86FB] = 2;
            data[0x8703] = 1;
            var rows = TodSaveInspection.Read(data, "BCUS98127").Table("Bonuses & cheats").Rows;
            True(rows[1].Details.Contains("Requested cosmetic selection: Small (0.5x)") && rows[1].Details.Contains("count includes Off"), "Inspector must explain the known native factor.");
            True(rows[3].Details.Contains("score>=100: met"), "The score prerequisite must stay distinct from current activity.");
            True(rows[11].Details.Contains("not met; editing disabled") && rows[11].Details.Contains("does not prove an active runtime effect"), "A requested mirror state below threshold does not become an active verdict.");
            data[0x86F9] = 255;
            True(TodSaveInspection.Read(data, "BCUS98127").Table("Bonuses & cheats").Rows[1].Details.Contains("state is unrecognized"), "Unknown states must not receive an invented selection label.");
        });
        Check("Cosmetic bonus editing respects existing unsigned score requirements without granting points", () =>
        {
            foreach (uint score in new uint[] { 0, 49, 50, 99, 100, 199, 200, 399, 400, 499, 500, 750, uint.MaxValue })
            {
                byte[] data = BonusFixture(score);
                var fields = TodSaveEditing.Fields(data, "BCUS98127").Where(field => field.Category == "Bonus effects").ToArray();
                Equal(score < 50 ? 0 : score < 100 ? 1 : score < 200 ? 2 : score < 400 ? 3 : score < 500 ? 4 : 5, fields.Length);
                foreach (var (key, minimum) in new[] { ("bonus_hero_head", 50u), ("bonus_enemy_head", 100u), ("bonus_commentary", 200u), ("bonus_james_zurkon", 400u), ("bonus_mirror", 500u) })
                {
                    if (score < minimum) Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits((key, 1))));
                    else
                    {
                        byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits((key, 1)));
                        Equal(score, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0x8708, 4)));
                        True(data.AsSpan(0x8710, 8).SequenceEqual(result.AsSpan(0x8710, 8)), "Earned skill bits must not change.");
                    }
                }
            }
        });
        Check("Unknown cosmetic bonus states and other slots stay read-only; invalid batches fail preflight", () =>
        {
            byte[] data = BonusFixture();
            foreach (var (key, offset, count) in new[] { ("bonus_hero_head", 0x86F9, 4), ("bonus_enemy_head", 0x86FB, 3), ("bonus_commentary", 0x86FD, 2), ("bonus_james_zurkon", 0x8701, 2), ("bonus_mirror", 0x8703, 2) })
            {
                foreach (int unknown in new[] { count, 8, 255 })
                {
                    byte[] unusual = data.ToArray();
                    unusual[offset] = (byte)unknown;
                    True(!TodSaveEditing.Fields(unusual, "BCUS98127").Any(field => field.Key == key), "Unrecognized state must not be silently normalized.");
                    Throws<InvalidDataException>(() => TodSaveEditing.Apply(unusual, "BCUS98127", Edits((key, 0))));
                    True(TodSaveEditing.Apply(unusual, "BCUS98127", Edits(("subtitles", 1))).AsSpan(0x86F8, 14).SequenceEqual(unusual.AsSpan(0x86F8, 14)),
                        "An unrelated edit must retain unknown bonus bytes.");
                }
                foreach (decimal invalid in new[] { -1m, 0.5m, (decimal)count, 8m, 256m })
                    Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("subtitles", 1), (key, invalid))));
            }
            foreach (string forbidden in new[] { "bonus_wrench", "bonus_zurkon", "skill_score" })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits((forbidden, 1))));
            True(data.SequenceEqual(BonusFixture()), "Rejected edit batches must not alter any input byte.");
        });
        Check("Cosmetic bonus UI stages named choices and preserves them across categories", () =>
        {
            using var form = new Form { ClientSize = new Size(900, 500), Font = new Font("Segoe UI", 13) };
            using var editor = new TodSaveEditingControl();
            form.Controls.Add(editor);
            editor.LoadSnapshot(BonusFixture(), "BCUS98127");
            form.Show();
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            category.SelectedItem = "Bonus effects";
            var hero = editor.Controls.Find("MappedEdit_bonus_hero_head", true).Cast<ComboBox>().Single();
            Equal(4, hero.Items.Count);
            hero.SelectedIndex = 2;
            Equal(2m, editor.PendingEdits["bonus_hero_head"]);
            category.SelectedItem = "Game settings";
            category.SelectedItem = "Bonus effects";
            Equal(2, editor.Controls.Find("MappedEdit_bonus_hero_head", true).Cast<ComboBox>().Single().SelectedIndex);
            True(editor.Controls.Find("MappedEditNotice", true).Cast<Label>().Single().Text.Contains("No points or unlocks"), "Show the score/ownership limitation with the choices.");
            Application.DoEvents();
            using var bitmap = new Bitmap(form.Width, form.Height);
            form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, bitmap.Size));
            Directory.CreateDirectory("artifacts");
            bitmap.Save("artifacts/bonus-editor-preview.png");
            editor.LoadSnapshot(BonusFixture(49), "BCUS98127");
            True(!editor.HasChanges && !category.Items.Contains("Bonus effects"), "Insufficient score hides the category and resets staged values.");
        });
        Check("Saving cosmetic bonuses retains all unrelated bytes and earlier committed edits", () =>
        {
            string folder = Fixture(root, "BCUS98127"), backups = Path.Combine(root, "bonus-edit-backups");
            byte[] data = BonusFixture();
            data[0x8704] = 255;
            data[0x8706] = 0xA5;
            BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x8710, 8), 0x8000000000000001);
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), data);
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: backups);
            var edits = Edits(("bonus_hero_head", 3), ("bonus_enemy_head", 2), ("bonus_mirror", 1));
            byte[] expected = TodSaveEditing.Apply(data, "BCUS98127", edits);
            SaveData.Write(expected, session.Profile, new[] { 10 }, 20);
            session.Save(10, 20, backups, edits);
            True(expected.SequenceEqual(session.ReadInspectionData()), "Baseline must update to the committed bonus values.");
            session.Save(11, 21, backups);
            SaveData.Write(expected, session.Profile, new[] { 11 }, 21);
            True(expected.SequenceEqual(File.ReadAllBytes(Path.Combine(folder, "GAME.SAV"))), "Later currency saves must retain cosmetic and unknown bytes.");
        });
    }
}
