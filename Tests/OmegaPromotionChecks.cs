using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static byte[] OmegaFixture(int level = 4, uint replay = 1)
    {
        byte[] data = WeaponLevelFixture(level, 0.33333334f);
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x906EC, 4), replay);
        return data;
    }

    private static void OmegaPromotionChecks(string root)
    {
        Check("Bulk Omega promotion matches individual promotions and retains staged upgrades and ammo", () =>
        {
            byte[] data = OmegaFixture(), before = data.ToArray();
            var existing = Edits(("subtitles", 1), ("hero_xp", 45000), ("upgrade_all_15", 1), ("ammo_15", 0.25m));
            var originalEdits = existing.ToArray();
            var expected = existing.ToDictionary(edit => edit.Key, edit => edit.Value);
            for (int id = 1; id <= 15; id++) expected["omega_promote_" + id] = 1;
            var plan = TodSaveEditing.PlanBulk(data, "BCUS98127", existing, TodBulkEdit.PromoteEligibleOmegaWeapons);
            Equal(15, plan.Keys.Count(key => key.StartsWith("omega_promote_")));
            True(TodSaveEditing.Apply(data, "BCUS98127", expected).SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", plan)),
                "Bulk promotion must reuse each weapon's coupled XP/level/ammo edits and explicit overrides.");
            True(originalEdits.SequenceEqual(existing) && before.SequenceEqual(data), "Planning must not mutate the baseline or existing edit dictionary.");
            var repeated = TodSaveEditing.PlanBulk(data, "BCUS98127", plan, TodBulkEdit.PromoteEligibleOmegaWeapons);
            True(plan.OrderBy(edit => edit.Key).SequenceEqual(repeated.OrderBy(edit => edit.Key)), "Repeated bulk staging must be idempotent.");
            byte[] saved = TodSaveEditing.Apply(data, "BCUS98127", plan);
            var noOps = TodSaveEditing.PlanBulk(saved, "BCUS98127", Edits(), TodBulkEdit.PromoteEligibleOmegaWeapons);
            Equal(0, noOps.Count);
            True(saved.SequenceEqual(TodSaveEditing.Apply(saved, "BCUS98127", noOps)), "Already-Omega weapons must not be reset or refilled by the bulk action.");
        });
        Check("Bulk Omega promotion skips lower, unowned, already-Omega, malformed and staged-decrease records", () =>
        {
            byte[] data = OmegaFixture();
            WeaponLevelFixture(3).AsSpan(2 * 20, 20).CopyTo(data.AsSpan(2 * 20, 20));
            data[3 * 20 + 16] = 0;
            OmegaFixture(6).AsSpan(4 * 20, 20).CopyTo(data.AsSpan(4 * 20, 20));
            BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(5 * 20 + 8, 4), float.NaN);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(6 * 20 + 12, 4), 0x80000000);
            var existing = Edits(("weapon_level_7", 2), ("weapon_level_8", 4), ("subtitles", 1));
            var plan = TodSaveEditing.PlanBulk(data, "BCUS98127", existing, TodBulkEdit.PromoteEligibleOmegaWeapons);
            int[] eligible = { 1, 8, 9, 10, 11, 12, 13, 14, 15 };
            var expected = existing.ToDictionary(edit => edit.Key, edit => edit.Value);
            foreach (int id in eligible) expected["omega_promote_" + id] = 1;
            Equal(expected.Count, plan.Count);
            True(expected.OrderBy(edit => edit.Key).SequenceEqual(plan.OrderBy(edit => edit.Key)), "Only currently eligible, non-conflicting records should be promoted.");
            True(TodSaveEditing.Apply(data, "BCUS98127", expected).SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", plan)),
                "Skipped records and unrelated pending edits must retain their exact behavior.");
        });
        Check("Bulk Omega promotion is a no-op without eligible saved level-5 weapons or replay state", () =>
        {
            foreach (byte[] data in new[] { OmegaFixture(replay: 0), OmegaFixture(3), OmegaFixture(5) })
            {
                var plan = TodSaveEditing.PlanBulk(data, "BCUS98127", Edits(), TodBulkEdit.PromoteEligibleOmegaWeapons);
                Equal(0, plan.Count);
                True(data.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", plan)), "A no-op must not grant ownership, levels or replay mode.");
            }
            var stagedLevel = TodSaveEditing.PlanBulk(OmegaFixture(3), "BCUS98127", Edits(("weapon_level_1", 4)), TodBulkEdit.PromoteEligibleOmegaWeapons);
            Equal(1, stagedLevel.Count); Equal(4m, stagedLevel["weapon_level_1"]);
        });
        Check("Bulk Omega UI preserves typed ammo, skips staged level changes and blocks hidden invalid input", () =>
        {
            using var form = new Form { ClientSize = new Size(1100, 820), StartPosition = FormStartPosition.Manual,
                Location = new Point(-20000, -20000), ShowInTaskbar = false };
            using var editor = new TodSaveEditingControl(); form.Controls.Add(editor);
            byte[] data = OmegaFixture(); BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(28, 4), 0.5f);
            editor.LoadSnapshot(data, "BCUS98127"); form.Show();
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            var bulk = editor.Controls.Find("MappedPromoteOmega", true).Cast<Button>().Single();
            category.SelectedItem = "Weapon ammo";
            editor.Controls.Find("MappedEdit_ammo_1", true).Cast<NumericTextBox>().Single().Text = "0.50";
            category.SelectedItem = "Weapon levels";
            var level = editor.Controls.Find("MappedEdit_weapon_level_2", true).Cast<ComboBox>().Single();
            level.SelectedItem = level.Items.Cast<TodEditOption>().Single(option => option.Value == 3);
            category.SelectedItem = "Omega promotions"; True(bulk.Visible && bulk.Enabled, "Expose the action on the Omega page when eligible weapons exist.");
            bulk.PerformClick();
            var edits = editor.PendingEdits;
            Equal(14, edits.Keys.Count(key => key.StartsWith("omega_promote_")));
            Equal(3m, edits["weapon_level_2"]); Equal(0.5m, edits["ammo_1"]);
            Equal(0.5f, BinaryPrimitives.ReadSingleBigEndian(TodSaveEditing.Apply(data, "BCUS98127", edits).AsSpan(28, 4)));
            editor.LoadSnapshot(data, "BCUS98127"); category.SelectedItem = "Weapon ammo";
            editor.Controls.Find("MappedEdit_ammo_1", true).Cast<NumericTextBox>().Single().Text = "invalid";
            category.SelectedItem = "Omega promotions"; bulk.PerformClick();
            Equal("Weapon ammo", category.SelectedItem);
            True(editor.HasInvalidInputs, "Hidden invalid input must stop bulk staging.");
            editor.Controls.Find("MappedEdit_ammo_1", true).Cast<NumericTextBox>().Single().Text = "0.5";
            True(!editor.PendingEdits.Keys.Any(key => key.StartsWith("omega_promote_")), "A blocked bulk action must not partially stage promotions.");
            foreach (byte[] unavailable in new[] { OmegaFixture(replay: 0), OmegaFixture(3), OmegaFixture(5) })
            {
                editor.LoadSnapshot(unavailable, "BCUS98127"); category.SelectedItem = "Omega promotions";
                True(bulk.Visible && !bulk.Enabled && !editor.HasChanges, "Disable the button when no weapons qualify.");
            }
            editor.LoadSnapshot(null, null); True(!bulk.Visible, "Hide the action without a supported save.");
        });
        Check("Omega promotion requires verified owned level-5 weapons and existing replay state", () =>
        {
            foreach (int level in Enumerable.Range(0, 10))
            foreach (uint replay in new[] { 0u, 1u, 1000u, 0x80000000u, uint.MaxValue })
            {
                byte[] data = OmegaFixture(level, replay);
                var fields = TodSaveEditing.Fields(data, "BCUS98127").Where(field => field.Storage == TodEditStorage.OmegaPromotion).ToArray();
                Equal(15, fields.Length);
                foreach (var field in fields)
                {
                    Equal(level >= 5 ? 1m : 0m, field.Current);
                    Equal(level >= 5 || level == 4 && replay != 0 ? 1m : 0m, field.Maximum);
                    Equal(level == 4 && replay != 0 ? 2 : 1, field.Options.Count);
                }
            }
        });
        Check("All fifteen promotions change only matching XP, level and promoted-tier ammo", () =>
        {
            for (int id = 1; id <= 15; id++)
            {
                byte[] data = OmegaFixture();
                int offset = id * 20;
                data[offset + 16] = 255; data[offset + 18] = 0xAB; data[offset + 19] = 0xCD;
                byte[] before = data.ToArray(), expected = data.ToArray();
                TodResearch.TryConfig(TodResearch.Inventory[id].GetProperty("config_name").GetString(), out var config);
                var variables = config.GetProperty("variables");
                expected[offset + 17] = 5;
                BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(offset + 4, 4), variables.GetProperty("XP")[5].GetSingle());
                BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(offset + 8, 4), variables.GetProperty("MaxAmmo")[5].GetSingle());
                byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("omega_promote_" + id, 1)));
                True(expected.SequenceEqual(result), "Promotion must preserve ownership, currencies, upgrades, slots, counters, replay and opaque bytes.");
                True(before.SequenceEqual(data), "Promotion must not mutate the supplied baseline.");
                var level = TodSaveEditing.Fields(result, "BCUS98127").Single(field => field.Key == "weapon_level_" + id);
                True(level.Options.Select(option => option.Value).SequenceEqual(Enumerable.Range(5, 5).Select(value => (decimal)value)), "Reload must expose levels 6–10.");
                BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(0x906EC, 4), 0);
                True(result.SequenceEqual(TodSaveEditing.Apply(result, "BCUS98127", Edits(("omega_promote_" + id, 1)))), "Duplicate requests must not reset XP or refill ammo, even outside replay.");
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(result, "BCUS98127", Edits(("omega_promote_" + id, 0))));
            }
        });
        Check("Malformed baselines, unavailable tiers and invalid Omega requests fail without writes", () =>
        {
            foreach (int fault in Enumerable.Range(0, 12))
            {
                byte[] data = OmegaFixture();
                if (fault == 0) data[0x24] = 0;
                if (fault == 1) data[0x25] = 3;
                if (fault == 2) data[0x25] = 255;
                if (fault == 3) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x18, 4), float.NaN);
                if (fault == 4) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x18, 4), float.PositiveInfinity);
                if (fault == 5) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x18, 4), -1);
                if (fault == 6) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x18, 4), 0);
                if (fault == 7) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x1C, 4), -1);
                if (fault == 8) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x1C, 4), float.NaN);
                if (fault == 9) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x1C, 4), 101);
                if (fault == 10) BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x20, 4), 0x80000000);
                if (fault == 11) BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x906EC, 4), 0);
                byte[] before = data.ToArray();
                Equal(0m, TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "omega_promote_1").Maximum);
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("voice_volume", 25), ("omega_promote_1", 1))));
                True(before.SequenceEqual(data), "Rejected batches must preserve every original byte.");
            }
            byte[] valid = OmegaFixture();
            foreach (decimal value in new[] { -1m, 0.5m, 2m, 255m })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(valid, "BCUS98127", Edits(("omega_promote_1", value))));
            foreach (string key in new[] { "omega_promote_0", "omega_promote_16", "omega_promote_01", "omega_promote_19" })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(valid, "BCUS98127", Edits((key, 1))));
            foreach (string region in new[] { "BCES00052", "BCUS98124" })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(valid, region, Edits(("omega_promote_1", 1))));
            True(valid.SequenceEqual(TodSaveEditing.Apply(valid, "BCUS98127", Edits(("omega_promote_1", 0)))), "Cancelled promotions must do nothing.");
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(valid[..^1], "BCUS98127", Edits(("omega_promote_1", 1))));
        });
        Check("Promotions compose with upgrades and explicit ammo in either request order", () =>
        {
            byte[] data = OmegaFixture();
            // Ryno changes base capacity at the tier boundary; an override above
            // its old limit must use the promoted capacity plus staged upgrades.
            var promoted = TodSaveEditing.Apply(data, "BCUS98127", Edits(("omega_promote_15", 1), ("upgrade_all_15", 1)));
            decimal maximum = TodSaveEditing.Fields(promoted, "BCUS98127").Single(field => field.Key == "ammo_15").Maximum;
            True(maximum > TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "ammo_15").Maximum, "Exercise the changing Ryno tier capacity.");
            foreach (decimal ammo in new[] { 0m, 12.5m, maximum })
            {
                var edits = Edits(("omega_promote_15", 1), ("upgrade_all_15", 1), ("ammo_15", ammo), ("weapon_level_1", 3));
                byte[] first = TodSaveEditing.Apply(data, "BCUS98127", edits);
                byte[] second = TodSaveEditing.Apply(data, "BCUS98127", edits.Reverse().ToDictionary(item => item.Key, item => item.Value));
                True(first.SequenceEqual(second), "Promotion, upgrades and ammo must not depend on dictionary order.");
                Equal((float)ammo, BinaryPrimitives.ReadSingleBigEndian(first.AsSpan(15 * 20 + 8, 4)));
            }
            decimal savedAmmo = TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "ammo_15").Current;
            byte[] preserved = TodSaveEditing.Apply(data, "BCUS98127", Edits(("omega_promote_15", 1), ("ammo_15", savedAmmo)));
            True(data.AsSpan(15 * 20 + 8, 4).SequenceEqual(preserved.AsSpan(15 * 20 + 8, 4)), "Explicit original ammo must preserve exact float bits.");
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("omega_promote_15", 1), ("ammo_15", maximum + 1))));
            foreach (var edits in new[] { Edits(("omega_promote_1", 1), ("weapon_level_1", 3)), Edits(("weapon_level_1", 3), ("omega_promote_1", 1)) })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", edits));
            var bulk = TodSaveEditing.PlanBulk(data, "BCUS98127", Edits(("omega_promote_15", 1)), TodBulkEdit.RefillSupportedAmmo);
            Equal(TodSaveEditing.Fields(TodSaveEditing.Apply(data, "BCUS98127", Edits(("omega_promote_15", 1))), "BCUS98127").Single(field => field.Key == "ammo_15").Maximum, bulk["ammo_15"]);
        });
        Check("Omega UI previews tier ammo, keeps invalid overrides and unlocks levels after reload", () =>
        {
            using var form = new Form { ClientSize = new Size(1100, 820), Font = new Font("Segoe UI", 11),
                StartPosition = FormStartPosition.Manual, Location = new Point(-20000, -20000), ShowInTaskbar = false };
            using var editor = new TodSaveEditingControl(); form.Controls.Add(editor);
            byte[] data = OmegaFixture(); editor.LoadSnapshot(data, "BCUS98127"); form.Show();
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            ComboBox Promotion() => editor.Controls.Find("MappedEdit_omega_promote_15", true).Cast<ComboBox>().Single();
            NumericTextBox Ammo() => editor.Controls.Find("MappedEdit_ammo_15", true).Cast<NumericTextBox>().Single();
            void Choose(ComboBox combo, decimal value) => combo.SelectedItem = combo.Items.Cast<TodEditOption>().Single(option => option.Value == value);
            category.SelectedItem = "Omega promotions"; Choose(Promotion(), 1);
            Equal(1m, editor.PendingEdits["omega_promote_15"]);
            using (var preview = new Bitmap(form.Width, form.Height))
            {
                form.DrawToBitmap(preview, new Rectangle(Point.Empty, preview.Size));
                Directory.CreateDirectory("artifacts");
                preview.Save("artifacts/omega-promotions-" + (SystemColors.Window.GetBrightness() < 0.5f ? "dark" : "light") + ".png");
            }
            category.SelectedItem = "Weapon levels";
            var level = editor.Controls.Find("MappedEdit_weapon_level_15", true).Cast<ComboBox>().Single();
            Choose(level, 3); Equal(4m, ((TodEditOption)level.SelectedItem).Value);
            True(!editor.PendingEdits.ContainsKey("weapon_level_15"), "Conflicting level changes must be rejected without losing the promotion.");
            category.SelectedItem = "Weapon ammo";
            decimal omegaCapacity = Ammo().Maximum; Equal(omegaCapacity, Ammo().Value);
            Ammo().Value = omegaCapacity - 0.5m;
            category.SelectedItem = "Omega promotions"; Choose(Promotion(), 0);
            True(editor.HasInvalidInputs, "Cancelling promotion must revalidate ammo against the lower tier limit.");
            Throws<InvalidOperationException>(() => { _ = editor.PendingEdits; });
            Choose(Promotion(), 1); True(!editor.HasInvalidInputs, "Restoring promotion must revalidate the retained ammo override.");
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", editor.PendingEdits);
            editor.LoadSnapshot(result, "BCUS98127"); category.SelectedItem = "Omega promotions";
            True(!Promotion().Enabled, "Already-Omega action must be read-only.");
            category.SelectedItem = "Weapon levels";
            level = editor.Controls.Find("MappedEdit_weapon_level_15", true).Cast<ComboBox>().Single();
            Equal(5m, ((TodEditOption)level.SelectedItem).Value);
            Equal(9m, level.Items.Cast<TodEditOption>().Last().Value);
            editor.LoadSnapshot(OmegaFixture(replay: 0), "BCUS98127"); category.SelectedItem = "Omega promotions";
            True(!Promotion().Enabled, "Promotion must be unavailable outside replay.");
        });
        Check("Omega saves retain original backups and later level edits survive reopen", () =>
        {
            string folder = Fixture(root, "BCUS98127"), backups = Path.Combine(root, "omega-backups");
            byte[] original = OmegaFixture(); File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), original);
            var tools = new FakeTools { FailEncrypt = true };
            using var session = SaveSession.Open(folder, tools, backupRoot: backups);
            var edits = Edits(("omega_promote_15", 1));
            var source = Snapshot(folder);
            Throws<InvalidOperationException>(() => session.Save(session.CharacterBolts, session.Raritanium, backups, edits));
            Same(source, Snapshot(folder));
            True(original.SequenceEqual(session.ReadInspectionData()), "Failed encryption must retain the original session baseline.");
            tools.FailEncrypt = false;
            string backup = session.Save(session.CharacterBolts, session.Raritanium, backups, edits);
            True(original.SequenceEqual(File.ReadAllBytes(Path.Combine(backup, "GAME.SAV"))), "Backup must contain the original tier.");
            byte[] promoted = TodSaveEditing.Apply(original, "BCUS98127", edits);
            True(promoted.SequenceEqual(session.ReadInspectionData()), "Successful save must publish exactly the promotion plan.");
            session.Save(session.CharacterBolts, session.Raritanium, backups, Edits(("weapon_level_15", 9)));
            using var reopened = SaveSession.Open(folder, tools, backupRoot: backups);
            True(TodSaveEditing.Apply(promoted, "BCUS98127", Edits(("weapon_level_15", 9))).SequenceEqual(reopened.ReadInspectionData()), "Omega levels must persist through a later save and reopen.");
        });
    }
}
