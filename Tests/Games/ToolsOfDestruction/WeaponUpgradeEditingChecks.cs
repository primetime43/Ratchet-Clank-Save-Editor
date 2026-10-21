using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static void WeaponUpgradeEditingChecks()
    {
        var catalog = TodResearch.Map.GetProperty("upgrade_edit_candidates").GetProperty("catalog");
        string[] types = { "MOD_DAMAGE", "MOD_RANGE", "MOD_AOE", "MOD_SPEED", "MOD_DURATION", "MOD_BOLTS", "MOD_MINERALS", "MOD_SPAWNCOUNT" };
        Check("All132 ordinary non-ammo upgrades change only their add-only modifier bit", () =>
        {
            int count = 0;
            foreach (var entry in catalog.EnumerateArray())
            foreach (var node in entry.GetProperty("nodes").EnumerateArray())
            {
                if (node.GetProperty("is_special").GetBoolean() || !types.Contains(node.GetProperty("type").GetString())) continue;
                int id = entry.GetProperty("id").GetInt32(), index = node.GetProperty("index").GetInt32();
                string key = $"weapon_upgrade_{id}_{index}";
                byte[] data = AmmoUpgradeFixture(entry, index, ammo: 0.33333334f);
                if ((count & 1) != 0) data[id * 20 + 15] |= 1;
                byte[] before = data.ToArray(), expected = data.ToArray();
                var field = TodSaveEditing.Fields(data, "BCUS98127").Single(item => item.Key == key);
                Equal(TodEditStorage.WeaponUpgrade, field.Storage);
                Equal("Weapon upgrades", field.Category);
                if (node.GetProperty("runtime_value").GetSingle() < 0)
                    True(field.Label.Contains("-"), "Signed shipped speed/duration modifiers must not be relabeled as positive boosts.");
                uint mask = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(field.Offset, 4));
                BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(field.Offset, 4), mask | (1u << index));
                byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits((key, 1)));
                True(result.SequenceEqual(expected), "Non-ammo nodes must preserve ammo, XP, wallet, ownership and every unrelated byte.");
                True(data.SequenceEqual(before), "Original input must remain detached.");
                True(TodSaveEditing.Apply(data, "BCUS98127", Edits((key, 0))).SequenceEqual(before), "Keep must be byte-identical.");
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(result, "BCUS98127", Edits((key, 0))));
                count++;
            }
            Equal(132, count);
        });
        Check("Weapon upgrades reject unverified dependencies, unmet special prerequisites and removals", () =>
        {
            foreach (int fault in Enumerable.Range(0, 6))
            {
                byte[] data = WeaponLevelFixture(); int offset = 2 * 20;
                if (fault == 0) data[offset + 16] = 0;
                if (fault == 1) data[offset + 17] = 255;
                if (fault == 2) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(offset + 4, 4), float.NaN);
                if (fault == 3) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(offset + 8, 4), float.PositiveInfinity);
                if (fault == 4) BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(offset + 12, 4), 0x80000000);
                if (fault == 5) BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(offset + 12, 4), 1u << 6);
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_upgrade_2_5", 1))));
            }
            foreach (var entry in catalog.EnumerateArray())
            foreach (var node in entry.GetProperty("nodes").EnumerateArray().Where(node => node.GetProperty("is_special").GetBoolean()))
            {
                int id = entry.GetProperty("id").GetInt32(), index = node.GetProperty("index").GetInt32();
                byte[] data = WeaponLevelFixture();
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(($"weapon_upgrade_{id}_{index}", 1))));
            }
            foreach (decimal value in new[] { -1m, 0.5m, 2m })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(WeaponLevelFixture(), "BCUS98127", Edits(("weapon_upgrade_2_5", value))));
            // New additions cannot supply prerequisites to a previously unavailable field in the same batch.
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(WeaponLevelFixture(), "BCUS98127", Edits(("weapon_upgrade_2_5", 1), ("weapon_upgrade_2_2", 1))));
        });
        Check("Damage, capacity, level and explicit ammo compose without ordering-dependent writes", () =>
        {
            byte[] data = WeaponLevelFixture(ammo: 0.33333334f), before = data.ToArray();
            var ammo = TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "ammo_2");
            foreach (decimal value in new[] { ammo.Current, ammo.Maximum + 1 })
            {
                var edits = Edits(("weapon_upgrade_2_5", 1), ("ammo_upgrade_2_7", 1), ("weapon_level_2", 4), ("ammo_2", value));
                byte[] result = TodSaveEditing.Apply(data, "BCUS98127", edits);
                True(result.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", edits.Reverse().ToDictionary(edit => edit.Key, edit => edit.Value))), "Dictionary order must not affect either node bit or refill override.");
                Equal((1u << 5) | (1u << 7), BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(2 * 20 + 12, 4)));
                if (value == ammo.Current) True(result.AsSpan(2 * 20 + 8, 4).SequenceEqual(before.AsSpan(2 * 20 + 8, 4)), "Same-value override must retain exact original float bits.");
                else Equal((float)value, BinaryPrimitives.ReadSingleBigEndian(result.AsSpan(2 * 20 + 8, 4)));
            }
            True(data.SequenceEqual(before), "Combined edits must not mutate the input.");
        });
    }

    // Full/manual CI suite only; no local window or UI loop in --new-edits.
    private static void WeaponUpgradeUiChecks()
    {
        Check("Non-ammo upgrade UI keeps existing ammo and pending explicit amounts", () =>
        {
            byte[] data = WeaponLevelFixture(ammo: 0.5f);
            using var form = new Form { ClientSize = new Size(1000, 820), Font = new Font("Segoe UI", 11) };
            using var editor = new TodSaveEditingControl(); form.Controls.Add(editor); editor.LoadSnapshot(data, "BCUS98127");
            form.Show();
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            category.SelectedItem = "Weapon upgrades";
            var upgrade = editor.Controls.Find("MappedEdit_weapon_upgrade_2_5", true).Cast<ComboBox>().Single();
            upgrade.SelectedItem = upgrade.Items.Cast<TodEditOption>().Single(option => option.Value == 1);
            category.SelectedItem = "Weapon ammo";
            var ammo = editor.Controls.Find("MappedEdit_ammo_2", true).Cast<NumericTextBox>().Single();
            Equal(0.5m, ammo.Value);
            True(!editor.PendingEdits.ContainsKey("ammo_2"), "Non-ammo additions must not stage or preview a refill.");
            ammo.Text = "0.25";
            category.SelectedItem = "Weapon upgrades";
            upgrade = editor.Controls.Find("MappedEdit_weapon_upgrade_2_5", true).Cast<ComboBox>().Single();
            upgrade.SelectedItem = upgrade.Items.Cast<TodEditOption>().Single(option => option.Value == 0);
            Equal(0.25m, editor.PendingEdits["ammo_2"]);
            True(!editor.PendingEdits.ContainsKey("weapon_upgrade_2_5"), "Reverting an addition must keep unrelated ammo intent.");
        });
    }
}
