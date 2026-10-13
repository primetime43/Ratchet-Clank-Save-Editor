using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static Dictionary<string, decimal> Edits(params (string Key, decimal Value)[] values) =>
        values.ToDictionary(value => value.Key, value => value.Value);

    private static byte[] EditableFixture()
    {
        var bytes = ResearchFixture();
        BinaryPrimitives.WriteSingleBigEndian(bytes.AsSpan(0x114B0, 4), 0.5f);
        BinaryPrimitives.WriteSingleBigEndian(bytes.AsSpan(0x114C4, 4), 0.5f);
        BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x444, 4), 1);
        BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x448, 4), 1);
        BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x45C, 4), 1);
        BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x460, 4), 1);
        return bytes;
    }

    private static void MappedEditingChecks(string root)
    {
        DropdownOrderingChecks(root);
        BonusEditingChecks(root);
        WeaponLevelEditingChecks(root);
        NewEditSmokeChecks();
        AmmoUpgradeEditingChecks();
        AmmoUpgradeUiChecks();
        WeaponUpgradeEditingChecks();
        WeaponUpgradeUiChecks();
        RewardRequestEditingChecks();
        RewardRequestUiChecks();
        DeveloperEditingChecks();
        SkillAndBulkEditingChecks();
        SkillAndBulkUiChecks();
        AppearanceOwnershipChecks();
        HeroXpEditingChecks();
        GoldBoltEditingChecks(root);
        InventoryPreviewChecks(root);
        Check("Quick-select choices use native initial flags and ownership, not all inventory IDs", () =>
        {
            byte[] data = EditableFixture();
            data[25 * 20 + 16] = 1;
            data[31 * 20 + 16] = 1;
            var fields = TodSaveEditing.Fields(data, "BCUS98127").Where(field => field.Category == "Quick select").ToArray();
            Equal(24, fields.Length);
            True(fields.All(field => field.Options.Any(option => option.Value == -1)), "Every slot can be explicitly cleared.");
            True(fields[1].Options.Any(option => option.Value == 25), "Owned initially eligible SwingShot should be offered.");
            True(!fields[1].Options.Any(option => option.Value == 31), "Owned Decryptor remains definition-filtered.");
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("qs_1", 31))));
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("qs_24", -1))));
        });
        Check("Quick-select moves and swaps are atomic and reject newly created duplicates across32 slots", () =>
        {
            byte[] data = EditableFixture();
            for (int slot = 0; slot < 32; slot++) BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x284 + slot * 4, 4), -1);
            data[2 * 20 + 16] = 1;
            BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x284, 4), 1);
            BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x288, 4), 2);
            byte[] before = data.ToArray();
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("qs_2", 1))));
            byte[] swapped = TodSaveEditing.Apply(data, "BCUS98127", Edits(("qs_0", 2), ("qs_1", 1)));
            Equal(2, BinaryPrimitives.ReadInt32BigEndian(swapped.AsSpan(0x284, 4)));
            Equal(1, BinaryPrimitives.ReadInt32BigEndian(swapped.AsSpan(0x288, 4)));
            byte[] moved = TodSaveEditing.Apply(data, "BCUS98127", Edits(("qs_0", -1), ("qs_2", 1)));
            Equal(-1, BinaryPrimitives.ReadInt32BigEndian(moved.AsSpan(0x284, 4)));
            Equal(1, BinaryPrimitives.ReadInt32BigEndian(moved.AsSpan(0x28C, 4)));
            True(data.SequenceEqual(before), "Slot planning must not mutate the source.");
            BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x284 + 31 * 4, 4), 1);
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("qs_0", -1), ("qs_2", 1))));
        });
        Check("Quick-select edits preserve last8 words, warning state, ownership and unknown current IDs", () =>
        {
            byte[] data = EditableFixture();
            for (int slot = 0; slot < 32; slot++) BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x284 + slot * 4, 4), -1);
            BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x284, 4), int.MinValue);
            BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x288, 4), int.MaxValue);
            BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x284 + 31 * 4, 4), -123);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8734, 4), uint.MaxValue);
            data[0x8738] = 7;
            True(TodSaveEditing.Apply(data, "BCUS98127", Edits(("qs_0", int.MinValue), ("qs_1", int.MaxValue))).SequenceEqual(data), "Unknown slot IDs must survive no-ops.");
            byte[] changed = TodSaveEditing.Apply(data, "BCUS98127", Edits(("qs_0", 1), ("qs_1", -1)));
            for (int offset = 0; offset < data.Length; offset++)
                if (offset < 0x284 || offset >= 0x28C) Equal(data[offset], changed[offset]);
        });
        Check("Mapped editing is restricted to matching USA plaintext layout", () =>
        {
            byte[] data = EditableFixture();
            True(TodSaveEditing.Supports(data, "BCUS98127"), "USA fixture should admit mapped edits.");
            foreach (string region in new[] { "BCES00052", "BCUS98124", "NPUA80908", null })
            {
                Equal(0, TodSaveEditing.Fields(data, region).Count);
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, region, Edits(("subtitles", 1))));
            }
            True(!TodSaveEditing.Supports(data[..^1], "BCUS98127"), "Truncated data must not admit edits.");
            data[0] = 1;
            True(!TodSaveEditing.Supports(data, "BCUS98127"), "Mismatched IDs must not admit edits.");
        });
        Check("Mapped writes change only explicit allowed bytes and leave the input detached", () =>
        {
            byte[] data = EditableFixture(), before = data.ToArray();
            var fields = TodSaveEditing.Fields(data, "BCUS98127");
            Equal(15, fields.Count(field => field.Category == "Game settings"));
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("voice_volume", 25),
                ("subtitles", 1), ("camera_x", 1), ("ammo_1", 12.5m), ("skin", 1), ("armor", 1)));
            Equal(0.25f, BinaryPrimitives.ReadSingleBigEndian(result.AsSpan(0x114C4, 4)));
            Equal(1u, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0x114A8, 4)));
            Equal(12.5f, BinaryPrimitives.ReadSingleBigEndian(result.AsSpan(0x1C, 4)));
            Equal(1u, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0x480, 4)));
            int[] offsets = { 0x114C4, 0x114D1, 0x114A8, 0x1C, 0x480, 0x458 };
            for (int i = 0; i < data.Length; i++)
                if (!offsets.Any(offset => i >= offset && i < offset + (offset == 0x114D1 ? 1 : 4)))
                    Equal(before[i], result[i]);
            True(data.SequenceEqual(before), "Applying edits must not mutate its input.");
        });
        Check("Invalid, dependent and unowned edits fail preflight without changing input", () =>
        {
            byte[] data = EditableFixture(), before = data.ToArray();
            foreach (var edits in new[]
            {
                Edits(("voice_volume", 101)), Edits(("subtitles", 0.5m)), Edits(("control_scheme", 2)),
                Edits(("ammo_1", -1)), Edits(("ammo_1", 100.01m)), Edits(("skin", 2)), Edits(("armor", 4)),
                Edits(("hero_level", 100)), Edits(("modifier_mask", 1)), Edits(("global_flag_10", 1)),
                Edits(("voice_volume", 25), ("unknown", 1))
            }) Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", edits));
            True(data.SequenceEqual(before), "Invalid batches must leave every source byte unchanged.");
        });
        Check("Unusual raw settings, unknown bytes and unchanged values are preserved", () =>
        {
            byte[] data = EditableFixture();
            data[0x114D1] = 7;
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x114A8, 4), 0x80000000);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x114CC, 4), 0x7FC12345);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x114BC, 4), 255);
            data[0x114D6] = 0xA5;
            var fields = TodSaveEditing.Fields(data, "BCUS98127");
            True(!fields.Any(field => field.Key is "music_volume" or "control_scheme"), "Unknown/nonfinite settings remain read-only.");
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("subtitles", 1), ("camera_x", 1), ("voice_volume", 50)));
            True(result.SequenceEqual(data), "Semantic no-ops must preserve noncanonical flags and float bits.");
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("music_volume", 50))));
        });
        Check("Ammo editor refuses uncertain record inputs and calculates selected modifier limits", () =>
        {
            byte[] data = EditableFixture();
            Equal(100m, TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "ammo_1").Maximum);
            // Independently check one selected ammo modifier from each reference configuration.
            foreach (var item in TodResearch.Inventory.Where(item => item.GetProperty("id").GetInt32() is >= 1 and <= 15))
            {
                int id = item.GetProperty("id").GetInt32();
                if (!TodResearch.TryConfig(item.GetProperty("config_name").GetString(), out var config)) continue;
                foreach (var node in config.GetProperty("modifiers").EnumerateArray())
                {
                    if (node.GetProperty("type").GetString() != "MOD_AMMO") continue;
                    byte[] selected = data.ToArray();
                    int offset = id * 20;
                    selected[offset + 16] = 1;
                    selected[offset + 17] = 0;
                    BinaryPrimitives.WriteSingleBigEndian(selected.AsSpan(offset + 8, 4), 0);
                    BinaryPrimitives.WriteUInt32BigEndian(selected.AsSpan(offset + 12, 4), 1u << node.GetProperty("index").GetInt32());
                    float basis = config.GetProperty("variables").GetProperty("MaxAmmo")[0].GetSingle();
                    float value = node.GetProperty("runtime_value").GetSingle();
                    float limit = node.GetProperty("is_percent").GetBoolean() ? basis * (1f + value) : basis + value;
                    Equal((decimal)limit, TodSaveEditing.Fields(selected, "BCUS98127").Single(field => field.Key == "ammo_" + id).Maximum);
                    break;
                }
            }
            foreach (int fault in Enumerable.Range(0, 5))
            {
                byte[] broken = data.ToArray();
                if (fault == 0) broken[0x24] = 0;
                if (fault == 1) broken[0x25] = 255;
                if (fault == 2) BinaryPrimitives.WriteUInt32BigEndian(broken.AsSpan(0x20, 4), 0x80000000);
                if (fault == 3) BinaryPrimitives.WriteSingleBigEndian(broken.AsSpan(0x1C, 4), float.NaN);
                if (fault == 4) BinaryPrimitives.WriteSingleBigEndian(broken.AsSpan(0x1C, 4), 101);
                True(!TodSaveEditing.Fields(broken, "BCUS98127").Any(field => field.Key == "ammo_1"), "Uncertain ammo inputs must be read-only.");
            }
        });
        Check("Appearance choices preserve unknown selection without granting ownership", () =>
        {
            byte[] data = EditableFixture();
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x480, 4), uint.MaxValue);
            var skin = TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "skin");
            True(skin.Options.Any(option => option.Value == uint.MaxValue), "Current unknown selection must remain visible.");
            True(TodSaveEditing.Apply(data, "BCUS98127", Edits(("skin", uint.MaxValue))).SequenceEqual(data), "Unknown current choice must remain untouched.");
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("skin", 1)));
            True(data.AsSpan(0x45C, 36).SequenceEqual(result.AsSpan(0x45C, 36)), "Selecting must not grant skins.");
        });
        Check("Repeated plaintext saves retain prior mapped edits and inspection baselines", () =>
        {
            string folder = Fixture(root, "BCUS98127"), backups = Path.Combine(root, "mapped-edit-backups");
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), EditableFixture());
            var tools = new FakeTools { FailDecrypt = true };
            using var session = SaveSession.Open(folder, tools, decrypted: true, backupRoot: backups);
            session.Save(124, 46, backups, Edits(("voice_volume", 25), ("ammo_1", 10), ("qs_0", 1)));
            Equal(0.25f, BinaryPrimitives.ReadSingleBigEndian(session.ReadInspectionData().AsSpan(0x114C4, 4)));
            session.Save(125, 47, backups);
            session.Save(126, 48, backups, Edits(("subtitles", 1)));
            using var reopened = SaveSession.Open(folder, tools, decrypted: true, backupRoot: backups);
            Equal(0.25f, BinaryPrimitives.ReadSingleBigEndian(reopened.ReadInspectionData().AsSpan(0x114C4, 4)));
            Equal(10f, BinaryPrimitives.ReadSingleBigEndian(reopened.ReadInspectionData().AsSpan(0x1C, 4)));
            Equal((byte)1, reopened.ReadInspectionData()[0x114D1]);
            Equal(1, BinaryPrimitives.ReadInt32BigEndian(reopened.ReadInspectionData().AsSpan(0x284, 4)));
            Equal(0, tools.CryptoCalls);
        });
        Check("Failed encrypted mapped edits preserve source and session baseline", () =>
        {
            string folder = Fixture(root, "BCUS98127"), backups = Path.Combine(root, "mapped-failure-backups");
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), EditableFixture());
            var source = Snapshot(folder);
            var tools = new FakeTools { FailEncrypt = true };
            using var session = SaveSession.Open(folder, tools, backupRoot: backups);
            byte[] before = session.ReadInspectionData();
            Throws<InvalidOperationException>(() => session.Save(124, 46, backups, Edits(("voice_volume", 25), ("qs_0", 1))));
            Same(source, Snapshot(folder));
            True(before.SequenceEqual(session.ReadInspectionData()), "Failed writes must not commit mapped inspection state.");
            tools.FailEncrypt = false;
            session.Save(124, 46, backups, Edits(("voice_volume", 25), ("qs_0", 1)));
            session.Save(125, 47, backups);
            using var reopened = SaveSession.Open(folder, tools, backupRoot: backups);
            Equal(0.25f, BinaryPrimitives.ReadSingleBigEndian(reopened.ReadInspectionData().AsSpan(0x114C4, 4)));
            Equal(1, BinaryPrimitives.ReadInt32BigEndian(reopened.ReadInspectionData().AsSpan(0x284, 4)));
        });
        Check("Mapped editor stages changes, survives category switches and clears across games", () =>
        {
            using var form = new MainForm();
            string folder = Fixture(root, "BCUS98127");
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), EditableFixture());
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "mapped-ui-backups"));
            typeof(MainForm).GetField("session", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(form, session);
            typeof(MainForm).GetMethod("ShowSession", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(form, null);
            var editor = form.Controls.Find("MappedSaveEditor", true).Cast<TodSaveEditingControl>().Single();
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            var voice = editor.Controls.Find("MappedEdit_voice_volume", true).Cast<NumericTextBox>().Single();
            True(!editor.HasChanges, "Loading fields must not dirty the editor.");
            voice.Value = 25;
            True(Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Mapped-only edits must enable Save All.");
            category.SelectedItem = "Weapon ammo";
            category.SelectedItem = "Quick select";
            var slot = editor.Controls.Find("MappedEdit_qs_0", true).Cast<ComboBox>().Single();
            slot.SelectedItem = slot.Items.Cast<TodEditOption>().Single(option => option.Value == 1);
            Equal(1m, editor.PendingEdits["qs_0"]);
            category.SelectedItem = "Game settings";
            Equal(25m, editor.Controls.Find("MappedEdit_voice_volume", true).Cast<NumericTextBox>().Single().Value);
            Equal(0.5f, BinaryPrimitives.ReadSingleBigEndian(session.ReadInspectionData().AsSpan(0x114C4, 4)));
            editor.Controls.Find("MappedEdit_voice_volume", true).Cast<NumericTextBox>().Single().Value = 50;
            category.SelectedItem = "Quick select";
            slot = editor.Controls.Find("MappedEdit_qs_0", true).Cast<ComboBox>().Single();
            slot.SelectedItem = slot.Items.Cast<TodEditOption>().Single(option => option.Value == 0);
            True(!editor.HasChanges, "Reverting must remove the staged field edit.");
            editor.LoadSnapshot(EditableFixture(), "BCUS98124");
            True(!editor.HasChanges && !category.Visible, "Other games must not retain mapped edits.");
        });
        Check("Mapped editor resizes and renders at normal and larger font scale", () =>
        {
            using var form = new MainForm();
            form.Show();
            var editor = form.Controls.Find("MappedSaveEditor", true).Cast<TodSaveEditingControl>().Single();
            editor.LoadSnapshot(WeaponLevelFixture(9), "BCUS98127");
            Field<TabControl>(form, "TabControl").SelectedTab = Field<TabPage>(form, "GameSaveEditingTabPage");
            Field<TabPage>(form, "GameSaveEditingTabPage").Enabled = true;
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            foreach (var size in new[] { new Size(900, 640), new Size(1120, 740) })
            {
                form.Size = size;
                foreach (string group in new[] { "Game settings", "Weapon ammo", "Weapon levels", "Quick select", "Appearance" })
                {
                    category.SelectedItem = group;
                    Application.DoEvents();
                    foreach (Control input in editor.Controls.Find("MappedEditFields", true).Single().Controls)
                        True(input.Width > 0 && input.Height > 0, "Fields must have usable dimensions.");
                }
            }
            form.Font = new Font("Segoe UI", 13);
            foreach (string group in new[] { "Game settings", "Weapon ammo", "Weapon levels", "Quick select", "Appearance" })
            {
                category.SelectedItem = group;
                Application.DoEvents();
                foreach (Control input in editor.Controls.Find("MappedEditFields", true).Single().Controls)
                {
                    Point bottom = input.PointToScreen(new Point(0, input.Height));
                    True(bottom.Y <= editor.PointToScreen(new Point(0, editor.ClientSize.Height)).Y,
                        "Larger fonts must not clip the final mapped field.");
                }
                if (group == "Quick select")
                {
                    using var preview = new Bitmap(form.Width, form.Height);
                    form.DrawToBitmap(preview, new Rectangle(Point.Empty, preview.Size));
                    Directory.CreateDirectory("artifacts");
                    preview.Save("artifacts/quick-select-editor-preview.png");
                }
            }
            using var bitmap = new Bitmap(form.Width, form.Height);
            form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, bitmap.Size));
            Directory.CreateDirectory("artifacts");
            bitmap.Save("artifacts/mapped-editor-preview.png");
            True(!editor.HasChanges, "Rendering/resizing must not stage edits.");
        });
    }
}
