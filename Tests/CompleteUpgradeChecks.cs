using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static float CompleteCapacity(int id, int level = 0)
    {
        TodResearch.TryConfig(TodResearch.Inventory[id].GetProperty("config_name").GetString(), out var config);
        float result = config.GetProperty("variables").GetProperty("MaxAmmo")[level].GetSingle(), factor = 1;
        foreach (var node in config.GetProperty("modifiers").EnumerateArray())
            if (node.GetProperty("type").GetString() == "MOD_AMMO")
            {
                if (node.GetProperty("is_percent").GetBoolean()) factor += node.GetProperty("runtime_value").GetSingle();
                else result += node.GetProperty("runtime_value").GetSingle();
            }
        return result * factor;
    }

    private static void CompleteUpgradeChecks(string root)
    {
        var catalog = TodResearch.Map.GetProperty("upgrade_edit_candidates").GetProperty("catalog");
        Check("Complete grids cover all189 positive nodes while preserving start bits, levels and unrelated bytes", () =>
        {
            int total = 0;
            foreach (var entry in catalog.EnumerateArray())
            {
                int id = entry.GetProperty("id").GetInt32(), count = entry.GetProperty("nodes").GetArrayLength();
                byte[] data = WeaponLevelFixture(ammo: 0.33333334f);
                uint start = (uint)(id & 1); BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(id * 20 + 12, 4), start);
                byte[] before = data.ToArray(), expected = data.ToArray();
                var field = TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "upgrade_all_" + id);
                Equal(1m, field.Maximum);
                BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(id * 20 + 12, 4), start | ((1u << count) - 2));
                TodResearch.TryConfig(TodResearch.Inventory[id].GetProperty("config_name").GetString(), out var config);
                if (CompleteCapacity(id) != config.GetProperty("variables").GetProperty("MaxAmmo")[0].GetSingle())
                    BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(id * 20 + 8, 4), CompleteCapacity(id));
                var result = TodSaveEditing.Apply(data, "BCUS98127", Edits((field.Key, 1)));
                True(expected.SequenceEqual(result), "Only the positive-node mask and capacity-triggered ammo refill may change.");
                True(before.SequenceEqual(data), "Input must stay detached.");
                var complete = TodSaveEditing.Fields(result, "BCUS98127").Single(candidate => candidate.Key == "upgrade_all_" + id);
                Equal(0m, complete.Maximum);
                True(result.SequenceEqual(TodSaveEditing.Apply(result, "BCUS98127", Edits(("upgrade_all_" + id, 0)))), "Already-complete no-ops must preserve exact bytes.");
                total += count - 1;
            }
            Equal(189, total);
        });
        Check("All fourteen special nodes and five extra ordinary parameters use bounded add-only bits", () =>
        {
            int specials = 0, flags = 0, parameters = 0;
            foreach (var entry in catalog.EnumerateArray())
            foreach (var node in entry.GetProperty("nodes").EnumerateArray().Where(node => node.GetProperty("is_special").GetBoolean() ||
                node.GetProperty("type").GetString() == "MOD_MISC"))
            {
                int id = entry.GetProperty("id").GetInt32(), index = node.GetProperty("index").GetInt32();
                byte[] data = AmmoUpgradeFixture(entry, index, ammo: 0.33333334f), expected = data.ToArray();
                uint mask = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(id * 20 + 12, 4));
                BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(id * 20 + 12, 4), mask | (1u << index));
                string key = $"weapon_upgrade_{id}_{index}";
                True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits((key, 1)))), "These non-ammo additions must change only the mask.");
                if (node.GetProperty("is_special").GetBoolean())
                {
                    specials++;
                    int prerequisite = node.GetProperty("orthogonal_neighbors").EnumerateArray().First(value => value.GetInt32() > 0).GetInt32();
                    BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(id * 20 + 12, 4), mask & ~(1u << prerequisite));
                    Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits((key, 1))));
                }
                else parameters++;
                if (node.GetProperty("type").GetString() == "MOD_SPECIAL")
                {
                    flags++;
                    True(node.GetProperty("runtime_value").ValueKind == System.Text.Json.JsonValueKind.Null, "Blank special values must remain unspecified.");
                }
            }
            Equal(14, specials); Equal(7, flags); Equal(5, parameters);
        });
        Check("Complete grids preserve raw ammo when only non-capacity nodes are missing", () =>
        {
            byte[] data = WeaponLevelFixture(ammo: 0.33333334f);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(15 * 20 + 12, 4), 0x7FFE & ~(1u << 5));
            var result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("upgrade_all_15", 1)));
            Equal(0x7FFEu, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(15 * 20 + 12, 4)));
            True(data.AsSpan(15 * 20 + 8, 4).SequenceEqual(result.AsSpan(15 * 20 + 8, 4)), "No capacity change means no ammo write.");
            var ryno = catalog.EnumerateArray().Single(entry => entry.GetProperty("id").GetInt32() == 15);
            Equal(-3, ryno.GetProperty("special_node").GetInt32());
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_upgrade_15_0", 1))));
        });
        Check("Bulk grids skip unowned/malformed records and compose with levels and explicit ammo", () =>
        {
            byte[] data = WeaponLevelFixture(ammo: 0.33333334f); data[2 * 20 + 16] = 0;
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(3 * 20 + 12, 4), 0x80000000);
            var plan = TodSaveEditing.PlanBulk(data, "BCUS98127", Edits(("ammo_15", 0.25m), ("weapon_level_15", 4)), TodBulkEdit.UnlockOwnedUpgrades);
            True(!plan.ContainsKey("upgrade_all_2") && !plan.ContainsKey("upgrade_all_3"), "Unsafe/unowned records must be skipped.");
            var result = TodSaveEditing.Apply(data, "BCUS98127", plan);
            Equal(0.25f, BinaryPrimitives.ReadSingleBigEndian(result.AsSpan(15 * 20 + 8, 4)));
            Equal((byte)4, result[15 * 20 + 17]);
            True(data.AsSpan(2 * 20, 40).SequenceEqual(result.AsSpan(2 * 20, 40)), "Skipped records must stay byte-identical.");
            True(result.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", plan.Reverse().ToDictionary(edit => edit.Key, edit => edit.Value))), "Edit order cannot change the output.");
            foreach (var request in new[] { ("upgrade_all_2", 1m), ("upgrade_all_3", 1m), ("upgrade_all_15", 2m), ("upgrade_all_15", 0.5m), ("upgrade_all_16", 1m) })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(request)));
        });
        Check("Grid UI previews refills, retains explicit ammo and hides bulk upgrades on unrelated pages", () =>
        {
            using var form = new Form { ClientSize = new Size(1100, 850), Font = new Font("Segoe UI", 13) };
            using var editor = new TodSaveEditingControl(); form.Controls.Add(editor); editor.LoadSnapshot(WeaponLevelFixture(ammo: 0.5f), "BCUS98127"); form.Show();
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            void Full(decimal value)
            {
                category.SelectedItem = "Weapon upgrades";
                var input = editor.Controls.Find("MappedEdit_upgrade_all_15", true).Cast<ComboBox>().Single();
                input.SelectedItem = input.Items.Cast<TodEditOption>().Single(option => option.Value == value);
            }
            NumericTextBox Ammo() { category.SelectedItem = "Weapon ammo"; return editor.Controls.Find("MappedEdit_ammo_15", true).Cast<NumericTextBox>().Single(); }
            Full(1); Equal((decimal)CompleteCapacity(15), Ammo().Value);
            Ammo().Text = "0.25"; Full(0); Equal(0.25m, Ammo().Value);
            Ammo().Text = "0.50";
            category.SelectedItem = "Weapon upgrades";
            var button = editor.Controls.Find("MappedUnlockUpgrades", true).Cast<Button>().Single(); True(button.Visible, "Bulk grid action must appear on its own page.");
            button.PerformClick(); Equal(0.5m, editor.PendingEdits["ammo_15"]);
            category.SelectedItem = "Game settings"; True(!button.Visible, "Bulk upgrades must be hidden on unrelated pages.");
            True(!editor.HasInvalidInputs, "Staging grids must not create invalid numbers.");
        });
        Check("Complete upgrade saves use the existing backup workflow without changing currencies or tiers", () =>
        {
            string folder = Fixture(root, "BCUS98127"); byte[] data = WeaponLevelFixture(ammo: 0.5f);
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), data);
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "complete-grid-backups"));
            var edits = Edits(("upgrade_all_15", 1));
            string backup = session.Save(session.CharacterBolts, session.Raritanium, mappedEdits: edits);
            True(File.ReadAllBytes(Path.Combine(backup, "GAME.SAV")).SequenceEqual(data), "Original must remain recoverable.");
            True(session.ReadInspectionData().SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", edits)), "Only validated saved-mask/capacity changes should commit.");
        });
    }

    private static void CompleteUpgradesWithSave(string folder, string root)
    {
        var original = Snapshot(folder);
        using var session = SaveSession.Open(folder, new Encryption(), backupRoot: Path.Combine(root, "actual-complete-grid-backup"));
        byte[] data = session.ReadInspectionData();
        var plan = TodSaveEditing.PlanBulk(data, session.Metadata.Region, Edits(), TodBulkEdit.UnlockOwnedUpgrades);
        Console.WriteLine($"Actual save has {plan.Count} supported incomplete weapon grids.");
        // The supplied save is already fully upgraded. Make a missing RYNO leaf
        // on a detached copy to validate the UI/bit write, not a gameplay claim.
        byte[] missing = data.ToArray();
        uint mask = BinaryPrimitives.ReadUInt32BigEndian(missing.AsSpan(15 * 20 + 12, 4));
        BinaryPrimitives.WriteUInt32BigEndian(missing.AsSpan(15 * 20 + 12, 4), mask & ~(1u << 5));
        var result = TodSaveEditing.Apply(missing, session.Metadata.Region, Edits(("upgrade_all_15", 1)));
        True(result.SequenceEqual(data), "Restoring the synthetic leaf must reproduce the supplied save exactly, including raw ammo.");
        using var form = new Form { Text = "Complete weapon upgrades", ClientSize = new Size(1100, 900), Font = new Font("Segoe UI", 13), AutoScroll = true };
        using var editor = new TodSaveEditingControl(); form.Controls.Add(editor); editor.LoadSnapshot(missing, session.Metadata.Region);
        editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single().SelectedItem = "Weapon upgrades";
        form.Show(); Application.DoEvents();
        using var bitmap = new Bitmap(form.Width, form.Height); form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, bitmap.Size));
        Directory.CreateDirectory("artifacts"); bitmap.Save("artifacts/complete-upgrades-preview.png");
        Same(original, Snapshot(folder)); Console.WriteLine("Detached RYNO grid restored exactly; original save folder unchanged. No game patch or in-game test.");
    }
}
