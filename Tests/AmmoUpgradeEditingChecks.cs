using System;
using System.Buffers.Binary;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    // Small detached fixtures only: no UI, private save, crypto or native execution.
    private static byte[] AmmoUpgradeFixture(JsonElement entry, int target, int level = 0, float ammo = 0.5f)
    {
        byte[] data = WeaponLevelFixture(level, ammo);
        uint mask = 0;
        foreach (var node in entry.GetProperty("synthetic_complete_admission_order").EnumerateArray())
        {
            int index = node.GetInt32();
            if (index == target) break;
            mask |= 1u << index;
        }
        int id = entry.GetProperty("id").GetInt32();
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(id * 20 + 12, 4), mask);
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x420, 4), 12345);
        return data;
    }

    private static void AmmoUpgradeEditingChecks()
    {
        var catalog = TodResearch.Map.GetProperty("upgrade_edit_candidates").GetProperty("catalog");
        var grenade = catalog.EnumerateArray().Single(item => item.GetProperty("id").GetInt32() == 2);

        Check("All38 ordinary ammo upgrades add one bit and refill without changing other bytes", () =>
        {
            int checkedNodes = 0;
            foreach (var entry in catalog.EnumerateArray())
            foreach (var node in entry.GetProperty("nodes").EnumerateArray())
            {
                if (node.GetProperty("type").GetString() != "MOD_AMMO") continue;
                int id = entry.GetProperty("id").GetInt32(), index = node.GetProperty("index").GetInt32();
                string key = $"ammo_upgrade_{id}_{index}";
                byte[] data = AmmoUpgradeFixture(entry, index), before = data.ToArray();
                if ((checkedNodes & 1) != 0) data[id * 20 + 15] |= 1; // Preserve either start-bit state.
                before = data.ToArray();
                var fields = TodSaveEditing.Fields(data, "BCUS98127");
                var field = fields.Single(item => item.Key == key);
                Equal(TodEditStorage.AmmoUpgrade, field.Storage);
                Equal("Ammo upgrades", field.Category);
                True(field.Options.Select(option => option.Value).SequenceEqual(new[] { 0m, 1m }), "Only keep/add choices may be offered.");
                float maximum = fields.Single(item => item.Key == "ammo_" + id).ReferenceMaximum.Value;
                float newMaximum = maximum + node.GetProperty("runtime_value").GetSingle();
                byte[] expected = data.ToArray();
                uint mask = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(id * 20 + 12, 4));
                BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(id * 20 + 12, 4), mask | (1u << index));
                BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(id * 20 + 8, 4), newMaximum);
                byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits((key, 1)));
                True(result.SequenceEqual(expected), "An ammo upgrade may change only its modifier bit and coupled ammo refill.");
                True(data.SequenceEqual(before), "The detached original must remain unchanged.");
                True(TodSaveEditing.Apply(data, "BCUS98127", Edits((key, 0))).SequenceEqual(before), "Keep must preserve every original byte.");
                True(!TodSaveEditing.Fields(result, "BCUS98127").Any(item => item.Key == key), "Installed upgrades must not become removable or re-purchasable.");
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(result, "BCUS98127", Edits((key, 0))));
                checkedNodes++;
            }
            Equal(38, checkedNodes);
        });

        Check("Upgrade frontiers reject unknown, disconnected and unowned dependencies", () =>
        {
            const string key = "ammo_upgrade_2_7";
            foreach (int fault in Enumerable.Range(0, 8))
            {
                byte[] data = AmmoUpgradeFixture(grenade, 7);
                int offset = 2 * 20;
                if (fault == 0) data[offset + 16] = 0;
                if (fault == 1) BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(offset + 12, 4), 0x80000000);
                if (fault == 2) BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(offset + 12, 4), 1u << 6); // Disconnected from start.
                if (fault == 3) data[offset + 17] = 255;
                if (fault == 4) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(offset + 4, 4), float.NaN);
                if (fault == 5) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(offset + 8, 4), float.NaN);
                if (fault == 6) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(offset + 8, 4), -1);
                if (fault == 7) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(offset + 4, 4), 100000);
                byte[] before = data.ToArray();
                True(!TodSaveEditing.Fields(data, "BCUS98127").Any(field => field.Key == key), "Unverified baseline must not be repaired into upgrade eligibility.");
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits((key, 1))));
                True(data.SequenceEqual(before), "Rejected dependency checks must not alter the input.");
            }
            byte[] baseline = AmmoUpgradeFixture(grenade, 7);
            foreach (string invalidKey in new[] { "ammo_upgrade_2_0", "ammo_upgrade_2_1", "ammo_upgrade_2_6", "ammo_upgrade_2_31", "ammo_upgrade_0_1", "ammo_upgrade_16_1" })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(baseline, "BCUS98127", Edits((invalidKey, 1))));
            foreach (decimal value in new[] { -1m, 0.5m, 2m })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(baseline, "BCUS98127", Edits((key, value))));
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(baseline, "BCES00052", Edits((key, 1))));
        });

        Check("Level and capacity upgrades compose before explicit ammo independent of edit order", () =>
        {
            foreach (int oldLevel in new[] { 0, 4, 5, 9 })
            {
                int targetLevel = oldLevel > 4 ? (oldLevel == 5 ? 9 : 5) : (oldLevel == 0 ? 4 : 0);
                byte[] data = AmmoUpgradeFixture(grenade, 7, oldLevel, 0.33333334f);
                var ammoField = TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "ammo_2");
                float finalMaximum = ammoField.ReferenceMaximum.Value + 1;
                foreach (decimal requested in new[] { 0m, 0.5m, ammoField.Current, (decimal)finalMaximum })
                {
                    var edits = Edits(("weapon_level_2", targetLevel), ("ammo_upgrade_2_7", 1), ("ammo_2", requested));
                    byte[] forward = TodSaveEditing.Apply(data, "BCUS98127", edits);
                    byte[] reverse = TodSaveEditing.Apply(data, "BCUS98127", edits.Reverse().ToDictionary(item => item.Key, item => item.Value));
                    True(forward.SequenceEqual(reverse), "Coupled edits must not depend on dictionary order.");
                    Equal((byte)targetLevel, forward[2 * 20 + 17]);
                    if (requested == ammoField.Current)
                        True(data.AsSpan(2 * 20 + 8, 4).SequenceEqual(forward.AsSpan(2 * 20 + 8, 4)), "Same-value explicit ammo must preserve original raw float bits despite both refills.");
                    else Equal((float)requested, BinaryPrimitives.ReadSingleBigEndian(forward.AsSpan(2 * 20 + 8, 4)));
                }
                byte[] refill = TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_level_2", targetLevel), ("ammo_upgrade_2_7", 1)));
                Equal(finalMaximum, BinaryPrimitives.ReadSingleBigEndian(refill.AsSpan(2 * 20 + 8, 4)));
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("ammo_upgrade_2_7", 1), ("ammo_2", (decimal)finalMaximum + 0.01m))));
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("ammo_upgrade_2_7", 0), ("ammo_2", (decimal)finalMaximum))));
            }
        });

        Check("Capacity-only same-value ammo overrides preserve bits and invalid batches remain detached", () =>
        {
            byte[] data = AmmoUpgradeFixture(grenade, 7, ammo: 0.33333334f), before = data.ToArray();
            decimal current = TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "ammo_2").Current;
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("ammo_upgrade_2_7", 1), ("ammo_2", current)));
            True(data.AsSpan(2 * 20 + 8, 4).SequenceEqual(result.AsSpan(2 * 20 + 8, 4)), "A capacity-only refill must also respect explicit unchanged ammo.");
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("ammo_upgrade_2_7", 1), ("voice_volume", 101))));
            True(data.SequenceEqual(before), "Failure and success must leave the input untouched.");
        });
    }

    // CI-only UI coverage; deliberately excluded from the lightweight local path.
    private static void AmmoUpgradeUiChecks()
    {
        Check("Upgrade UI previews refills and retains hidden ammo validation when upgrades are reverted", () =>
        {
            var grenade = TodResearch.Map.GetProperty("upgrade_edit_candidates").GetProperty("catalog")
                .EnumerateArray().Single(item => item.GetProperty("id").GetInt32() == 2);
            byte[] data = AmmoUpgradeFixture(grenade, 7, ammo: 0.33333334f), before = data.ToArray();
            var baselineAmmo = TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "ammo_2");
            decimal upgradedMaximum = baselineAmmo.Maximum + 1, explicitAmmo = baselineAmmo.Maximum + 0.5m;
            using var form = new Form { ClientSize = new Size(1000, 820), Font = new Font("Segoe UI", 11) };
            using var editor = new TodSaveEditingControl();
            form.Controls.Add(editor);
            editor.LoadSnapshot(data, "BCUS98127");
            form.Show();
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            void Upgrade(bool add)
            {
                category.SelectedItem = "Ammo upgrades";
                editor.Controls.Find("MappedEdit_ammo_upgrade_2_7", true).Cast<ComboBox>().Single().SelectedIndex = add ? 1 : 0;
            }
            NumericTextBox Ammo()
            {
                category.SelectedItem = "Weapon ammo";
                return editor.Controls.Find("MappedEdit_ammo_2", true).Cast<NumericTextBox>().Single();
            }

            Upgrade(true);
            var ammo = Ammo();
            Equal(upgradedMaximum, ammo.Maximum);
            Equal(upgradedMaximum, ammo.Value);
            True(!editor.PendingEdits.ContainsKey("ammo_2"), "A previewed automatic refill should not become an explicit ammo edit.");

            ammo.Text = baselineAmmo.Current.ToString(CultureInfo.InvariantCulture);
            Equal(baselineAmmo.Current, editor.PendingEdits["ammo_2"]);
            byte[] overrideResult = TodSaveEditing.Apply(data, "BCUS98127", editor.PendingEdits);
            True(data.AsSpan(2 * 20 + 8, 4).SequenceEqual(overrideResult.AsSpan(2 * 20 + 8, 4)), "Typing the original ammo must override the upgrade refill while retaining its raw bits.");

            ammo.Text = explicitAmmo.ToString(CultureInfo.InvariantCulture);
            Equal(explicitAmmo, editor.PendingEdits["ammo_2"]);
            Upgrade(false); // The hidden input is now above the restored baseline limit.
            True(editor.HasInvalidInputs && editor.HasChanges, "Reverting an upgrade must retain and flag its now-out-of-range hidden ammo.");
            Throws<InvalidOperationException>(() => { var edits = editor.PendingEdits; });
            True(!editor.ValidateInputs(), "Saving must be blocked by hidden invalid ammo.");
            Equal("Weapon ammo", category.SelectedItem?.ToString());
            ammo = Ammo();
            Equal(baselineAmmo.Maximum, ammo.Maximum);
            Equal(explicitAmmo.ToString(CultureInfo.InvariantCulture), ammo.Text);
            True(!ammo.IsValid, "Rebuilding the ammo view must not discard the invalid text.");

            Upgrade(true);
            True(!editor.HasInvalidInputs && editor.ValidateInputs(), "Restaging the capacity upgrade should revalidate the retained text.");
            Equal(explicitAmmo, editor.PendingEdits["ammo_2"]);
            ammo = Ammo();
            Equal(upgradedMaximum, ammo.Maximum);
            Equal(explicitAmmo, ammo.Value);
            byte[] corrected = TodSaveEditing.Apply(data, "BCUS98127", editor.PendingEdits);
            Equal((float)explicitAmmo, BinaryPrimitives.ReadSingleBigEndian(corrected.AsSpan(2 * 20 + 8, 4)));
            True(data.SequenceEqual(before), "UI staging and detached saves must never mutate the baseline fixture.");
            Application.DoEvents();
        });
    }
}
