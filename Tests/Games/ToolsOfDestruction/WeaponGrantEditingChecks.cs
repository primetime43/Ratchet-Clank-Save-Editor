using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static byte[] WeaponGrantFixture()
    {
        byte[] data = WeaponLevelFixture();
        for (int id = 1; id <= 15; id++)
        {
            data[id * 20 + 16] = 0;
            data[id * 20 + 18] = 0xA5; data[id * 20 + 19] = 0x5A;
        }
        for (int slot = 0; slot < 32; slot++) BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x284 + 4 * slot, 4), -1);
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x280, 4), 37);
        return data;
    }

    private static void WeaponGrantEditingChecks(string root)
    {
        Check("All fifteen combat grants initialize only the confirmed saved fields and deterministic slots", () =>
        {
            byte[] data = WeaponGrantFixture(), before = data.ToArray(), expected = data.ToArray();
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(24, 4), 0x80000000); before = data.ToArray(); // Native XP store writes +0.
            var edits = Enumerable.Range(1, 15).Reverse().ToDictionary(id => "weapon_grant_" + id, _ => 1m);
            foreach (int id in Enumerable.Range(1, 15))
            {
                expected[id * 20 + 16] = 1;
                BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(id * 20 + 4, 4), 0);
                BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(id * 20 + 8, 4),
                    TodResearch.Map.GetProperty("weapon_grants").GetProperty("starting_ammo_by_id_1_to_15")[id - 1].GetSingle());
                BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x284 + 4 * (id - 1), 4), id);
            }
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x280, 4), 52);
            var result = TodSaveEditing.Apply(data, "BCUS98127", edits);
            True(expected.SequenceEqual(result), "Only ownership, XP, level, starting ammo, acquisition count and inserted slots may change.");
            True(before.SequenceEqual(data), "Grant plans must not mutate input.");
            True(result.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", edits.Reverse().ToDictionary(edit => edit.Key, edit => edit.Value))),
                "Edit dictionary order must not change weapon insertion order.");
            var fields = TodSaveEditing.Fields(result, "BCUS98127");
            Equal(15, fields.Count(field => field.Storage == TodEditStorage.WeaponLevel));
            True(fields.Where(field => field.Category == "Weapon unlocks").All(field => field.Minimum == 1), "Granted weapons must become add-only owned entries.");
        });
        Check("Duplicate/unchanged grants preserve noncanonical owned records and never refill or recount", () =>
        {
            byte[] data = WeaponGrantFixture();
            data[36] = 0xFE; data[37] = 9;
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(24, 4), 0x7FC12345);
            BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(28, 4), 0.5f);
            var result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_1", 1), ("weapon_grant_2", 0)));
            True(data.SequenceEqual(result), "Duplicate/no-op grants must not initialize or normalize any bytes.");
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_1", 0))));
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_1", 2))));
        });
        Check("Uncertain records, unsupported items/regions and acquisition overflow reject new grants", () =>
        {
            foreach (int fault in Enumerable.Range(0, 7))
            {
                byte[] data = WeaponGrantFixture();
                if (fault == 0) data[37] = 1;
                if (fault == 1) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(24, 4), 1);
                if (fault == 2) BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(24, 4), 0x7FC12345);
                if (fault == 3) BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(32, 4), 1);
                if (fault == 4) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(28, 4), -1);
                if (fault == 5) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(28, 4), 101);
                if (fault == 6) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(28, 4), float.PositiveInfinity);
                var field = TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "weapon_grant_1");
                Equal(0m, field.Maximum);
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_1", 1))));
                True(data.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_1", 0)))), "Uncertain no-ops must retain raw bits.");
            }
            byte[] valid = WeaponGrantFixture();
            foreach (int id in new[] { 0, 19, 24, 26, 30, 31, 32 })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(valid, "BCUS98127", Edits(("weapon_grant_" + id, 1))));
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(valid, "BCES00052", Edits(("weapon_grant_1", 1))));
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(valid, "BCUS98127", Edits(("weapon_grant_1", 1.5m))));
            BinaryPrimitives.WriteUInt32BigEndian(valid.AsSpan(0x280, 4), uint.MaxValue - 1);
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(valid, "BCUS98127", Edits(("weapon_grant_1", 1), ("weapon_grant_2", 1))));
            Equal(uint.MaxValue, BinaryPrimitives.ReadUInt32BigEndian(TodSaveEditing.Apply(valid, "BCUS98127", Edits(("weapon_grant_1", 1))).AsSpan(0x280, 4)));
        });
        Check("Grants retain full/unknown/tail slots and respect existing membership across all32", () =>
        {
            byte[] data = WeaponGrantFixture();
            for (int slot = 0; slot < 24; slot++) BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x284 + 4 * slot, 4), 0x100 + slot);
            data[0x8738] = 0x7F; BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8734, 4), 0x12345678);
            var result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_1", 1)));
            True(data.AsSpan(0x284, 128).SequenceEqual(result.AsSpan(0x284, 128)), "Empty tail slots must not be used or occupied slots replaced.");
            True(data.AsSpan(0x8734, 8).SequenceEqual(result.AsSpan(0x8734, 8)), "Runtime warning state must not be synthesized.");
            data = WeaponGrantFixture();
            BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x284 + 31 * 4, 4), 1);
            result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_1", 1)));
            True(data.AsSpan(0x284, 128).SequenceEqual(result.AsSpan(0x284, 128)), "Existing tail membership must prevent another assignment.");
        });
        Check("Same-batch quick-select choices require a grant and explicit assignments precede auto-insertion", () =>
        {
            byte[] data = WeaponGrantFixture();
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("qs_5", 1))));
            var result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_1", 1), ("weapon_grant_2", 1), ("qs_5", 1)));
            Equal(1, BinaryPrimitives.ReadInt32BigEndian(result.AsSpan(0x284 + 5 * 4, 4)));
            Equal(2, BinaryPrimitives.ReadInt32BigEndian(result.AsSpan(0x284, 4)));
            Equal(1, Enumerable.Range(0, 32).Count(slot => BinaryPrimitives.ReadInt32BigEndian(result.AsSpan(0x284 + slot * 4, 4)) == 1));
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_1", 1), ("qs_5", 1), ("qs_6", 1))));
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_1", 0), ("qs_5", 1))));
        });
        Check("Weapon unlock UI stages/cancels dependent slots and rejects counter overflow before saving", () =>
        {
            byte[] data = WeaponGrantFixture();
            using var form = new Form { ClientSize = new Size(1100, 850), Font = new Font("Segoe UI", 13) };
            using var editor = new TodSaveEditingControl(); form.Controls.Add(editor); editor.LoadSnapshot(data, "BCUS98127"); form.Show();
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            ComboBox Input(string key) => editor.Controls.Find("MappedEdit_" + key, true).Cast<ComboBox>().Single();
            void Choose(string key, decimal value) { var input = Input(key); input.SelectedItem = input.Items.Cast<TodEditOption>().Single(option => option.Value == value); }
            category.SelectedItem = "Weapon unlocks"; True(!editor.HasChanges, "Loading grants must not stage edits.");
            Alphabetical(Input("weapon_grant_1")); Choose("weapon_grant_1", 1);
            category.SelectedItem = "Quick select"; Choose("qs_5", 1);
            Equal(1m, editor.PendingEdits["weapon_grant_1"]); Equal(1m, editor.PendingEdits["qs_5"]);
            category.SelectedItem = "Weapon unlocks"; Choose("weapon_grant_1", 0);
            True(!editor.HasChanges, "Cancelling a grant must cancel its staged slot assignments.");
            category.SelectedItem = "Quick select";
            True(!Input("qs_5").Items.Cast<TodEditOption>().Any(option => option.Value == 1), "Cancelled grants must disappear from slot choices.");
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x280, 4), uint.MaxValue);
            editor.LoadSnapshot(data, "BCUS98127"); category.SelectedItem = "Weapon unlocks"; Choose("weapon_grant_1", 1);
            True(!editor.HasChanges && ((TodEditOption)Input("weapon_grant_1").SelectedItem).Value == 0, "Overflow must restore the unchanged UI choice.");
            True(!editor.Controls.Find("MappedBulkActions", true).Single().Visible, "Weapon grants must not show ammo/level bulk buttons.");
        });
        Check("Weapon grants save with a full original backup and become editable owned weapons after reload", () =>
        {
            string folder = Fixture(root, "BCUS98127"); byte[] data = WeaponGrantFixture();
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), data);
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "weapon-grant-backups"));
            var edits = Edits(("weapon_grant_15", 1), ("qs_7", 15));
            string backup = session.Save(session.CharacterBolts, session.Raritanium, mappedEdits: edits);
            True(File.ReadAllBytes(Path.Combine(backup, "GAME.SAV")).SequenceEqual(data), "The original must be recoverable from its backup.");
            var actual = session.ReadInspectionData();
            True(actual.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", edits)), "The save workflow must apply the coupled grant plan exactly.");
            var fields = TodSaveEditing.Fields(actual, "BCUS98127");
            True(fields.Any(field => field.Key == "ammo_15") && fields.Any(field => field.Key == "weapon_level_15"), "The granted Ryno must expose its existing ammo/level editors after saving.");
            True(TodSaveInspection.Read(actual, "BCUS98127").Inventory[15].ScriptOwned, "Inventory inspection must see the saved grant.");
        });
    }

    private static void WeaponGrantsWithSave(string folder, string root)
    {
        var original = Snapshot(folder);
        using var session = SaveSession.Open(folder, new Encryption(), backupRoot: Path.Combine(root, "actual-grant-backup"));
        byte[] data = session.ReadInspectionData();
        var fields = TodSaveEditing.Fields(data, session.Metadata.Region).Where(field => field.Storage == TodEditStorage.WeaponGrant).ToArray();
        var noOps = fields.ToDictionary(field => field.Key, field => field.Current);
        True(data.SequenceEqual(TodSaveEditing.Apply(data, session.Metadata.Region, noOps)), "Actual save duplicate/no-op grants must preserve every byte.");
        // This supplied save already owns every combat weapon. Exercise a missing
        // record on a detached copy, not by altering its original or writing it back.
        byte[] missing = data.ToArray(); missing.AsSpan(24, 14).Clear();
        for (int slot = 0; slot < 32; slot++)
            if (BinaryPrimitives.ReadInt32BigEndian(missing.AsSpan(0x284 + 4 * slot, 4)) == 1)
                BinaryPrimitives.WriteInt32BigEndian(missing.AsSpan(0x284 + 4 * slot, 4), -1);
        byte[] result = TodSaveEditing.Apply(missing, session.Metadata.Region, Edits(("weapon_grant_1", 1)));
        Equal((byte)1, result[36]); Equal(100f, BinaryPrimitives.ReadSingleBigEndian(result.AsSpan(28, 4)));
        True(data.AsSpan(0x5528, 40).SequenceEqual(result.AsSpan(0x5528, 40)), "Global flags must remain unchanged.");
        using (var window = new Form { Text = "Weapon unlocks preview", ClientSize = new Size(1100, 900),
            Font = new Font("Segoe UI", 13), AutoScroll = true })
        using (var editor = new TodSaveEditingControl())
        {
            window.Controls.Add(editor); editor.LoadSnapshot(missing, session.Metadata.Region);
            editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single().SelectedItem = "Weapon unlocks";
            window.Show(); Application.DoEvents();
            using var screenshot = new Bitmap(window.Width, window.Height);
            window.DrawToBitmap(screenshot, new Rectangle(Point.Empty, screenshot.Size));
            Directory.CreateDirectory("artifacts"); screenshot.Save("artifacts/weapon-unlocks-preview.png");
        }
        Same(original, Snapshot(folder));
        Console.WriteLine($"Actual save has {fields.Count(field => field.Category == "Weapon unlocks" && field.Current == 1)}/15 combat weapons already owned; all no-ops preserve bytes. A synthetic missing-Combuster copy grants correctly; original folder unchanged. No in-game test performed.");
    }
}
