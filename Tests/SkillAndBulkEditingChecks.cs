using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static void SkillAndBulkEditingChecks()
    {
        Check("Individual skills add native weighted points and preserve every unrelated byte", () =>
        {
            var catalog = TodResearch.Map.GetProperty("progression").GetProperty("skill_points").GetProperty("catalog");
            foreach (var skill in catalog.EnumerateArray().Take(59))
            {
                int id = skill.GetProperty("id").GetInt32();
                byte[] data = EditableFixture();
                BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8708, 4), 840);
                BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x8710, 8), 0xF000000000000000);
                byte[] before = data.ToArray(), expected = data.ToArray();
                BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x8708, 4), 840 + skill.GetProperty("points").GetUInt32());
                BinaryPrimitives.WriteUInt64BigEndian(expected.AsSpan(0x8710, 8), 0xF000000000000000 | (1UL << id));
                True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("skill_award_" + id, 1)))), "Only score and the selected earned bit may change.");
                True(before.SequenceEqual(data), "Original skill snapshot must remain detached.");
            }
        });
        Check("The last missing ordinary skill awards HARDCORE once regardless of request order", () =>
        {
            const ulong required = (1UL << 59) - 1;
            foreach (int id in new[] { 0, 48, 58 })
            {
                byte[] data = EditableFixture();
                BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x8710, 8), 0xA000000000000000 | (required & ~(1UL << id)));
                BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8708, 4), 900);
                byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("skill_award_" + id, 1)));
                var catalog = TodResearch.Map.GetProperty("progression").GetProperty("skill_points").GetProperty("catalog");
                Equal(900u + catalog[id].GetProperty("points").GetUInt32() + 20, BinaryPrimitives.ReadUInt32BigEndian(result.AsSpan(0x8708, 4)));
                Equal(0xAFFFFFFFFFFFFFFFUL, BinaryPrimitives.ReadUInt64BigEndian(result.AsSpan(0x8710, 8)));
                True(result.SequenceEqual(TodSaveEditing.Apply(result, "BCUS98127", Edits(("skill_award_" + id, 0)))), "A no-op must not award twice.");
            }
            byte[] all = EditableFixture();
            var forward = Enumerable.Range(0, 59).Select(id => ("skill_award_" + id, 1m)).ToArray();
            byte[] earned = TodSaveEditing.Apply(all, "BCUS98127", Edits(forward));
            Equal(750u, BinaryPrimitives.ReadUInt32BigEndian(earned.AsSpan(0x8708, 4)));
            True(earned.SequenceEqual(TodSaveEditing.Apply(all, "BCUS98127", Edits(forward.Reverse().ToArray()))), "Dictionary order must not change batch results.");
        });
        Check("Skills are add-only and never repair mismatches or conflict with the bonus-score helper", () =>
        {
            byte[] data = EditableFixture();
            BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x8710, 8), 1);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8708, 4), 999);
            byte[] before = data.ToArray();
            True(before.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("skill_award_0", 0)))), "Keep unchanged is not remove or recompute.");
            foreach (var edit in new[] { ("skill_award_0", 1m), ("skill_award_1", -1m), ("skill_award_1", 0.5m),
                ("skill_award_1", 2m), ("skill_award_59", 1m), ("skill_award_60", 1m) })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(edit)));
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("skill_award_1", 1), ("dev_unlock_bonuses", 1))));
            BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x8710, 8), (1UL << 59) - 1);
            True(data.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("skill_award_0", 0)))), "Existing missing HARDCORE must not be silently repaired.");
            BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x8710, 8), 0);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8708, 4), uint.MaxValue - 5);
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("skill_award_1", 1))));
        });
        Check("Bulk refill reuses supported capacities and excludes Groovitron, unowned and uncertain records", () =>
        {
            byte[] data = EditableOwnedGadgets(), before = data.ToArray();
            data[19 * 20 + 16] = 1; data[24 * 20 + 16] = 1;
            data[16 * 20 + 16] = 0;
            BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(17 * 20 + 8, 4), float.NaN);
            before = data.ToArray();
            var plan = TodSaveEditing.PlanBulk(data, "BCUS98127", Edits(("subtitles", 1)), TodBulkEdit.RefillSupportedAmmo);
            True(!plan.ContainsKey("ammo_16") && !plan.ContainsKey("ammo_17") && !plan.ContainsKey("ammo_19") && !plan.ContainsKey("ammo_24"), "Bulk editing must not broaden the ammo allowlist.");
            byte[] expected = data.ToArray(); expected[0x114D1] = 1;
            foreach (var field in TodSaveEditing.Fields(data, "BCUS98127").Where(field => field.Category is "Weapon ammo" or "Gadget ammo"))
                BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(field.Offset, 4), (float)field.Maximum);
            True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", plan)), "Refill must preserve all other data and unrelated pending edits.");
            True(data.SequenceEqual(before), "Planning is detached.");
        });
        Check("Bulk levels stay in each existing tier and preserve explicit ammo overrides", () =>
        {
            foreach (int level in new[] { 0, 5 })
            {
                byte[] data = WeaponLevelFixture(level, 0.5f), before = data.ToArray();
                data[2 * 20 + 16] = 0;
                BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(3 * 20 + 4, 4), float.NaN);
                before = data.ToArray();
                var plan = TodSaveEditing.PlanBulk(data, "BCUS98127", Edits(("ammo_1", 0.25m), ("subtitles", 1)), TodBulkEdit.MaximumOwnedWeaponTier);
                True(!plan.ContainsKey("weapon_level_2") && !plan.ContainsKey("weapon_level_3"), "Unowned/inconsistent weapons stay untouched.");
                byte[] expected = data.ToArray(); expected[0x114D1] = 1;
                foreach (var field in TodSaveEditing.Fields(data, "BCUS98127").Where(field => field.Storage == TodEditStorage.WeaponLevel))
                {
                    int id = (field.Offset - 17) / 20, target = level == 0 ? 4 : 9;
                    TodResearch.TryConfig(TodResearch.Inventory[id].GetProperty("config_name").GetString(), out var config);
                    expected[id * 20 + 17] = (byte)target;
                    BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(id * 20 + 4, 4), config.GetProperty("variables").GetProperty("XP")[target].GetSingle());
                    var ammo = TodSaveEditing.Fields(data, "BCUS98127").Single(item => item.Key == "ammo_" + id);
                    BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(id * 20 + 8, 4), id == 1 ? 0.25f : ammo.ReferenceMaximum.Value);
                }
                True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", plan)), "No tier bridge or collateral writes.");
                True(data.SequenceEqual(before), "Bulk level planning must not mutate its input.");
            }
        });
        Check("Bulk refill composes with capacity upgrades and current-tier maxima cancel staged decreases", () =>
        {
            var grenade = TodResearch.Map.GetProperty("upgrade_edit_candidates").GetProperty("catalog").EnumerateArray().Single(item => item.GetProperty("id").GetInt32() == 2);
            int index = grenade.GetProperty("nodes").EnumerateArray().First(node => node.GetProperty("type").GetString() == "MOD_AMMO").GetProperty("index").GetInt32();
            byte[] data = AmmoUpgradeFixture(grenade, index);
            string key = "ammo_upgrade_2_" + index;
            var plan = TodSaveEditing.PlanBulk(data, "BCUS98127", Edits((key, 1), ("ammo_2", 0.25m)), TodBulkEdit.RefillSupportedAmmo);
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", plan);
            Equal((float)plan["ammo_2"], BinaryPrimitives.ReadSingleBigEndian(result.AsSpan(2 * 20 + 8, 4)));
            byte[] max = WeaponLevelFixture(4, 0.5f);
            var cancelled = TodSaveEditing.PlanBulk(max, "BCUS98127", Edits(("weapon_level_1", 0)), TodBulkEdit.MaximumOwnedWeaponTier);
            Equal(0, cancelled.Count);
            True(max.SequenceEqual(TodSaveEditing.Apply(max, "BCUS98127", cancelled)), "Already-max weapons keep their exact XP/ammo bits.");
        });
        Check("Bulk plans reject unsupported regions, malformed layouts and unknown pending edits", () =>
        {
            byte[] data = WeaponLevelFixture();
            foreach (var action in Enum.GetValues<TodBulkEdit>())
            {
                Throws<InvalidDataException>(() => TodSaveEditing.PlanBulk(data, "BCES00052", Edits(), action));
                Throws<InvalidDataException>(() => TodSaveEditing.PlanBulk(data[..^1], "BCUS98127", Edits(), action));
                Throws<InvalidDataException>(() => TodSaveEditing.PlanBulk(data, "BCUS98127", Edits(("unknown", 1)), action));
            }
        });
    }

    private static void SkillAndBulkUiChecks()
    {
        Check("Skill checklist stages add-only awards and automatic HARDCORE across category switches", () =>
        {
            byte[] data = EditableFixture();
            BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x8710, 8), ((1UL << 59) - 1) & ~(1UL << 58));
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8708, 4), 690);
            using var form = new Form { ClientSize = new Size(1100, 850), Font = new Font("Segoe UI", 11) };
            using var editor = new TodSaveEditingControl(); form.Controls.Add(editor); editor.LoadSnapshot(data, "BCUS98127"); form.Show();
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single(); category.SelectedItem = "Skill awards";
            var list = editor.Controls.Find("MappedSkillAwards", true).Cast<CheckedListBox>().Single();
            Equal(60, list.Items.Count); list.SetItemChecked(0, false); True(list.GetItemChecked(0), "Earned skills cannot be removed.");
            list.SetItemChecked(59, true); True(!list.GetItemChecked(59), "HARDCORE cannot be awarded directly.");
            list.SetItemChecked(58, true); True(list.GetItemChecked(59), "Last ordinary award previews HARDCORE.");
            Equal(1m, editor.PendingEdits["skill_award_58"]);
            True(editor.Controls.Find("MappedSkillSummary", true).Cast<Label>().Single().Text.Contains("690 → 750"), "Summary must show both weights.");
            category.SelectedItem = "Game settings"; category.SelectedItem = "Skill awards";
            list = editor.Controls.Find("MappedSkillAwards", true).Cast<CheckedListBox>().Single(); True(list.GetItemChecked(58), "Staging survives category changes.");
            list.SetItemChecked(58, false); True(!list.GetItemChecked(59) && !editor.HasChanges, "Cancelling staged skill must cancel automatic award too.");
            editor.LoadSnapshot(data, "BCES00052"); True(!editor.HasChanges && !category.Items.Contains("Skill awards"), "No USA edit leakage.");
        });
        Check("Bulk UI preserves typed ammo overrides and invalid hidden input blocks bulk actions", () =>
        {
            byte[] data = WeaponLevelFixture(0, 0.5f);
            using var form = new Form { ClientSize = new Size(1100, 850), Font = new Font("Segoe UI", 11) };
            using var editor = new TodSaveEditingControl(); form.Controls.Add(editor); editor.LoadSnapshot(data, "BCUS98127"); form.Show();
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single(); category.SelectedItem = "Weapon ammo";
            var ammo = editor.Controls.Find("MappedEdit_ammo_1", true).Cast<NumericTextBox>().Single(); ammo.Text = "0.50";
            editor.Controls.Find("MappedMaxWeaponTier", true).Cast<Button>().Single().PerformClick();
            Equal(4m, editor.PendingEdits["weapon_level_1"]); Equal(0.5m, editor.PendingEdits["ammo_1"]);
            editor.Controls.Find("MappedRefillAmmo", true).Cast<Button>().Single().PerformClick();
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", editor.PendingEdits);
            Equal(100f, BinaryPrimitives.ReadSingleBigEndian(result.AsSpan(28, 4)));
            category.SelectedItem = "Game settings";
            editor.Controls.Find("MappedEdit_voice_volume", true).Cast<NumericTextBox>().Single().Text = "wrong";
            category.SelectedItem = "Weapon ammo";
            editor.Controls.Find("MappedRefillAmmo", true).Cast<Button>().Single().PerformClick();
            True(editor.HasInvalidInputs && category.SelectedItem?.ToString() == "Game settings", "Invalid input is not silently discarded by a bulk action.");
        });
    }
}
