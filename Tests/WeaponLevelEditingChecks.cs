using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static byte[] WeaponLevelFixture(int level = 0, float ammo = 0)
    {
        byte[] data = EditableFixture();
        for (int id = 1; id <= 15; id++)
        {
            TodResearch.TryConfig(TodResearch.Inventory[id].GetProperty("config_name").GetString(), out var config);
            int offset = id * 20;
            data[offset + 16] = 1;
            data[offset + 17] = (byte)level;
            BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(offset + 4, 4), config.GetProperty("variables").GetProperty("XP")[level].GetSingle());
            BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(offset + 8, 4), ammo);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(offset + 12, 4), 0);
        }
        return data;
    }

    private static void WeaponLevelEditingChecks(string root)
    {
        Check("All15 combat weapons offer only the existing five-level tier", () =>
        {
            for (int level = 0; level <= 9; level++)
            {
                byte[] data = WeaponLevelFixture(level);
                var fields = TodSaveEditing.Fields(data, "BCUS98127").Where(field => field.Storage == TodEditStorage.WeaponLevel).ToArray();
                Equal(15, fields.Length);
                int first = level > 4 ? 5 : 0;
                foreach (var field in fields)
                {
                    Equal(5, field.Options.Count);
                    True(field.Options.Select(option => option.Value).SequenceEqual(Enumerable.Range(first, 5).Select(value => (decimal)value)), "Never offer an unowned tier bridge.");
                    Equal("Level " + (first + 1), field.Options[0].Label);
                    Equal((decimal)level, field.Current);
                }
            }
        });
        Check("Weapon level changes publish matching XP and only refill on increases", () =>
        {
            foreach (int oldLevel in new[] { 0, 4, 5, 9 })
            {
                byte[] data = WeaponLevelFixture(oldLevel, 0.5f);
                var fields = TodSaveEditing.Fields(data, "BCUS98127");
                foreach (var field in fields.Where(field => field.Storage == TodEditStorage.WeaponLevel))
                {
                    int id = (field.Offset - 17) / 20;
                    TodResearch.TryConfig(TodResearch.Inventory[id].GetProperty("config_name").GetString(), out var config);
                    foreach (var option in field.Options)
                    {
                        byte[] expected = data.ToArray();
                        if (option.Value != oldLevel)
                        {
                            expected[field.Offset] = (byte)option.Value;
                            BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(id * 20 + 4, 4), config.GetProperty("variables").GetProperty("XP")[(int)option.Value].GetSingle());
                            if (option.Value > oldLevel)
                                BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(id * 20 + 8, 4), fields.Single(f => f.Key == "ammo_" + id).ReferenceMaximum.Value);
                        }
                        True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits((field.Key, option.Value)))), "Only level, matching XP and qualified refill bytes may change.");
                    }
                }
            }
        });
        Check("Level-up refills preserve selected modifiers and exact reference float capacity", () =>
        {
            for (int id = 1; id <= 15; id++)
            {
                TodResearch.TryConfig(TodResearch.Inventory[id].GetProperty("config_name").GetString(), out var config);
                var node = config.GetProperty("modifiers").EnumerateArray().FirstOrDefault(item => item.GetProperty("type").GetString() == "MOD_AMMO");
                byte[] data = WeaponLevelFixture();
                if (node.ValueKind != System.Text.Json.JsonValueKind.Undefined)
                    BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(id * 20 + 12, 4), 1u << node.GetProperty("index").GetInt32());
                var maximum = TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "ammo_" + id).ReferenceMaximum.Value;
                byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_level_" + id, 4)));
                Equal(BitConverter.SingleToInt32Bits(maximum), BinaryPrimitives.ReadInt32BigEndian(result.AsSpan(id * 20 + 8, 4)));
                True(data.AsSpan(id * 20 + 12, 4).SequenceEqual(result.AsSpan(id * 20 + 12, 4)), "Modifiers must be preserved, not re-purchased or cleared.");
            }
        });
        Check("Explicit ammo overrides a level-up refill independent of batch ordering", () =>
        {
            byte[] data = WeaponLevelFixture(0, 0.33333334f);
            decimal originalAmmo = TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "ammo_1").Current;
            foreach (decimal ammo in new[] { 0m, 12.5m, originalAmmo })
            {
                byte[] first = TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_level_1", 4), ("ammo_1", ammo)));
                byte[] second = TodSaveEditing.Apply(data, "BCUS98127", Edits(("ammo_1", ammo), ("weapon_level_1", 4)));
                True(first.SequenceEqual(second), "Dictionary order must not affect coupled edits.");
                if (ammo == originalAmmo)
                    True(data.AsSpan(0x1C, 4).SequenceEqual(first.AsSpan(0x1C, 4)), "An explicit original-ammo override must preserve its exact bits.");
                else Equal((float)ammo, BinaryPrimitives.ReadSingleBigEndian(first.AsSpan(0x1C, 4)));
            }
        });
        Check("Unowned, malformed or inconsistent weapon records stay read-only", () =>
        {
            foreach (int fault in Enumerable.Range(0, 11))
            {
                byte[] data = WeaponLevelFixture();
                if (fault == 0) data[0x24] = 0;
                if (fault == 1) data[0x25] = 255;
                if (fault == 2) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x18, 4), float.NaN);
                if (fault == 3) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x18, 4), float.PositiveInfinity);
                if (fault == 4) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x18, 4), -1);
                if (fault == 5) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x18, 4), 1000);
                if (fault == 6) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x1C, 4), 101);
                if (fault == 7) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x1C, 4), float.NaN);
                if (fault == 8) BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x20, 4), 0x80000000);
                if (fault == 9) { data[0x25] = 5; BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x18, 4), 5500 - 1); }
                if (fault == 10) { data[0x25] = 5; BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x18, 4), 20000); }
                True(!TodSaveEditing.Fields(data, "BCUS98127").Any(field => field.Key == "weapon_level_1"), "Unverified state must not be silently repaired by level editing.");
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_level_1", 4))));
            }
        });
        Check("Level no-ops preserve accumulated XP; cross-tier and invalid batches are rejected", () =>
        {
            byte[] data = WeaponLevelFixture(9, 1.5f);
            BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x18, 4), 98637.7421875f);
            data[0x24] = 7;
            byte[] before = data.ToArray();
            True(TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_level_1", 9))).SequenceEqual(before), "Same-level requests must not reset XP or refill ammo.");
            foreach (decimal value in new[] { -1m, 4m, 5.5m, 10m, 255m })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("voice_volume", 25), ("weapon_level_1", value))));
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(WeaponLevelFixture(4), "BCUS98127", Edits(("weapon_level_1", 5))));
            foreach (string key in new[] { "weapon_level_0", "weapon_level_16", "weapon_xp_1", "hero_xp", "modifier_mask" })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits((key, 1))));
            True(data.SequenceEqual(before), "Rejected batches must leave the original completely unchanged.");
        });
        Check("Weapon level UI previews refills, permits original-ammo overrides and preserves invalid input", () =>
        {
            using var form = new Form { ClientSize = new Size(1000, 940), Font = new Font("Segoe UI", 13) };
            using var editor = new TodSaveEditingControl();
            form.Controls.Add(editor);
            byte[] data = WeaponLevelFixture(0, 0.5f);
            editor.LoadSnapshot(data, "BCUS98127");
            form.Show();
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            category.SelectedItem = "Weapon levels";
            editor.Controls.Find("MappedEdit_weapon_level_1", true).Cast<ComboBox>().Single().SelectedIndex = 4;
            category.SelectedItem = "Weapon ammo";
            var ammo = editor.Controls.Find("MappedEdit_ammo_1", true).Cast<NumericTextBox>().Single();
            Equal(100m, ammo.Value);
            ammo.Text = "0.5";
            Equal(0.5m, editor.PendingEdits["ammo_1"]);
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", editor.PendingEdits);
            Equal(0.5f, BinaryPrimitives.ReadSingleBigEndian(result.AsSpan(0x1C, 4)));
            category.SelectedItem = "Weapon levels";
            editor.Controls.Find("MappedEdit_weapon_level_1", true).Cast<ComboBox>().Single().SelectedIndex = 0;
            True(!editor.HasChanges, "Reverting level must remove an ammo override that now equals the original amount.");
            category.SelectedItem = "Weapon ammo";
            editor.Controls.Find("MappedEdit_ammo_1", true).Cast<NumericTextBox>().Single().Text = "invalid";
            category.SelectedItem = "Weapon levels";
            editor.Controls.Find("MappedEdit_weapon_level_1", true).Cast<ComboBox>().Single().SelectedIndex = 4;
            category.SelectedItem = "Weapon ammo";
            Equal("invalid", editor.Controls.Find("MappedEdit_ammo_1", true).Cast<NumericTextBox>().Single().Text);
            True(editor.HasInvalidInputs, "A level change must not clear invalid hidden ammo.");
            Throws<InvalidOperationException>(() => { var edits = editor.PendingEdits; });
            category.SelectedItem = "Weapon levels";
            Application.DoEvents();
            using var preview = new Bitmap(form.Width, form.Height);
            form.DrawToBitmap(preview, new Rectangle(Point.Empty, preview.Size));
            Directory.CreateDirectory("artifacts");
            preview.Save("artifacts/weapon-level-editor-preview.png");
        });
        Check("Failed encrypted level saves preserve source and baseline; later saves retain coupled fields", () =>
        {
            string folder = Fixture(root, "BCUS98127"), backups = Path.Combine(root, "weapon-level-backups");
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), WeaponLevelFixture());
            var tools = new FakeTools { FailEncrypt = true };
            using var session = SaveSession.Open(folder, tools, backupRoot: backups);
            var source = Snapshot(folder);
            byte[] original = session.ReadInspectionData();
            var edits = Edits(("weapon_level_1", 4), ("ammo_1", 12.5m));
            Throws<InvalidOperationException>(() => session.Save(123, 45, backups, edits));
            Same(source, Snapshot(folder));
            True(original.SequenceEqual(session.ReadInspectionData()), "Failure must not commit XP, ammo or level into the session baseline.");
            tools.FailEncrypt = false;
            byte[] expected = TodSaveEditing.Apply(original, "BCUS98127", edits);
            session.Save(123, 45, backups, edits);
            session.Save(124, 46, backups);
            SaveData.Write(expected, session.Profile, new[] { 124 }, 46);
            using var reopened = SaveSession.Open(folder, tools, backupRoot: backups);
            True(expected.SequenceEqual(reopened.ReadInspectionData()), "Later currency edits must not undo level, matching XP or ammo.");
        });
    }
}
