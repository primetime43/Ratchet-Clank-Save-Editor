using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static byte[] HeroXpFixture(uint xp)
    {
        byte[] data = EditableFixture();
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x418, 4), xp);
        return data;
    }

    private static void HeroXpEditingChecks()
    {
        Check("Hero reference targets write only the saved XP word and remain float32 exact", () =>
        {
            byte[] data = HeroXpFixture(123), before = data.ToArray();
            var targets = TodResearch.Map.GetProperty("hero_config_assets").GetProperty("rows");
            Equal(98, targets.GetArrayLength());
            Equal(989000m, TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "hero_xp").Maximum);
            foreach (var target in targets.EnumerateArray())
            {
                uint xp = target.GetProperty("xp").GetUInt32();
                byte[] expected = data.ToArray();
                BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x418, 4), xp);
                byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("hero_xp", xp)));
                True(expected.SequenceEqual(result), "Targets must not write health, a fabricated level, other progression or currency.");
                Equal(xp, (uint)(float)xp);
                True(before.SequenceEqual(data), "Original XP snapshot must stay detached.");
            }
        });
        Check("Hero XP accepts bounded integers but rejects fractions, unpopulated targets and unsupported saves", () =>
        {
            byte[] data = HeroXpFixture(989000);
            foreach (uint xp in new uint[] { 0, 1, 999, 1000, 17543, 988999, 989000 })
                Equal(xp, BinaryPrimitives.ReadUInt32BigEndian(TodSaveEditing.Apply(data, "BCUS98127", Edits(("hero_xp", xp))).AsSpan(0x418, 4)));
            foreach (decimal xp in new decimal[] { -1, 0.5m, 989000.5m, 989001, 1 << 24, uint.MaxValue })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("hero_xp", xp))));
            foreach (string key in new[] { "hero_level", "hero_health", "hero_xp_target_98", "hero_xp_target_99" })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits((key, 1))));
            foreach (string region in new[] { "BCES00052", "BCUS98124", "NPUA80908" })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, region, Edits(("hero_xp", 1000))));
            byte[] malformed = data.ToArray(); malformed[3] = 99;
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(malformed, "BCUS98127", Edits(("hero_xp", 1000))));
        });
        Check("Unusual existing hero XP can be preserved or lowered without extending the edit bound", () =>
        {
            foreach (uint saved in new uint[] { 989001, 2315144, (1u << 24) + 1, uint.MaxValue })
            {
                byte[] data = HeroXpFixture(saved);
                True(data.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("hero_xp", saved)))), "Explicit no-op must preserve high raw XP, not float-round it.");
                byte[] expected = data.ToArray();
                BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x418, 4), 989000);
                True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("hero_xp", 989000)))), "A high existing score can be brought into the reference range.");
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("hero_xp", saved == 989001 ? 989002 : saved - 1))));
            }
        });
        Check("Hero XP composes with staged skills, ownership and bulk edits", () =>
        {
            byte[] data = UnownedAppearanceFixture();
            BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x8710, 8), 0);
            var edits = new[] { ("hero_xp", 45000m), ("skill_award_0", 1m), ("armor_owned_4", 1m), ("armor", 4m) };
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits(edits));
            True(result.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(edits.Reverse().ToArray()))), "XP must not make edit order matter.");
            var plan = TodSaveEditing.PlanBulk(data, "BCUS98127", Edits(edits), TodBulkEdit.RefillSupportedAmmo);
            Equal(45000m, plan["hero_xp"]);
            Equal(45000u, BinaryPrimitives.ReadUInt32BigEndian(TodSaveEditing.Apply(data, "BCUS98127", plan).AsSpan(0x418, 4)));
        });
        Check("Hero XP UI stages reference and custom integers and blocks invalid hidden input", () =>
        {
            byte[] data = HeroXpFixture(123), before = data.ToArray();
            using var editor = new TodSaveEditingControl(); editor.LoadSnapshot(data, "BCUS98127");
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            category.SelectedItem = "Hero XP";
            NumericTextBox Input() => editor.Controls.Find("MappedEdit_hero_xp", true).Cast<NumericTextBox>().Single();
            ComboBox Targets() => editor.Controls.Find("MappedHeroXpTarget", true).Cast<ComboBox>().Single();
            void Choose(decimal value) { var targets = Targets(); targets.SelectedItem = targets.Items.Cast<TodEditOption>().Single(option => option.Value == value); }
            Equal(100, Targets().Items.Count); True(!Input().AllowDecimal && !editor.HasChanges, "Loading must not dirty XP and the textbox is integer-only.");
            Choose(97); Equal(989000m, editor.PendingEdits["hero_xp"]); Equal(989000m, Input().Value);
            category.SelectedItem = "Game settings"; category.SelectedItem = "Hero XP";
            Equal(989000m, Input().Value);
            Input().Text = "17543"; Equal(17543m, editor.PendingEdits["hero_xp"]);
            Equal(-1m, ((TodEditOption)Targets().SelectedItem).Value);
            foreach (string invalid in new[] { "", "1.5", "NaN", "1e3", "-1", "989001" })
            {
                Input().Text = invalid;
                True(editor.HasInvalidInputs, "Invalid XP must block collecting a save batch.");
                Throws<InvalidOperationException>(() => { _ = editor.PendingEdits; });
                category.SelectedItem = "Game settings";
                True(!editor.ValidateInputs() && (string)category.SelectedItem == "Hero XP", "Hidden invalid XP must be surfaced.");
                Equal(invalid, Input().Text);
            }
            Choose(-2); True(!editor.HasChanges && Input().Value == 123, "Keep saved XP must cancel both invalid text and staged XP.");
            True(before.SequenceEqual(data), "UI staging must never mutate the snapshot.");
            editor.LoadSnapshot(data, "BCES00052"); True(!category.Items.Contains("Hero XP") && !editor.HasChanges, "No hero XP controls or staging across regions.");
        });
        Check("Out-of-reference hero XP stays unchanged on load and can be edited with explicit targets", () =>
        {
            using var editor = new TodSaveEditingControl(); editor.LoadSnapshot(HeroXpFixture(uint.MaxValue), "BCUS98127");
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            category.SelectedItem = "Hero XP";
            NumericTextBox Input() => editor.Controls.Find("MappedEdit_hero_xp", true).Cast<NumericTextBox>().Single();
            void Choose(decimal value)
            {
                var targets = editor.Controls.Find("MappedHeroXpTarget", true).Cast<ComboBox>().Single();
                targets.SelectedItem = targets.Items.Cast<TodEditOption>().Single(option => option.Value == value);
            }
            True(Input().ReadOnly && Input().IsValid && !editor.HasChanges, "High XP must not be clamped or mark the initial UI invalid.");
            Choose(1); Equal(1000m, editor.PendingEdits["hero_xp"]); True(!Input().ReadOnly && Input().Maximum == 989000, "Targets switch to bounded editing.");
            Input().Text = "989001";
            category.SelectedItem = "Game settings"; category.SelectedItem = "Hero XP";
            True(!Input().ReadOnly && editor.HasInvalidInputs && Input().Text == "989001", "High baseline must not broaden a restored invalid textbox's bound.");
            Choose(-2); True(Input().ReadOnly && !editor.HasChanges && Input().Value == uint.MaxValue, "Keep restores the raw high value without creating an edit.");
            Choose(-1); Equal(0m, editor.PendingEdits["hero_xp"]); Input().Text = "12345";
            Equal(12345m, editor.PendingEdits["hero_xp"]);
        });
        Check("Progression preview matches all reference HP targets and handles XP threshold boundaries", () =>
        {
            using var editor = new TodSaveEditingControl();
            byte[] data = HeroXpFixture(0), original = data.ToArray(); editor.LoadSnapshot(data, "BCUS98127");
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            category.SelectedItem = "Hero XP";
            var input = editor.Controls.Find("MappedEdit_hero_xp", true).Cast<NumericTextBox>().Single();
            var targets = editor.Controls.Find("MappedHeroXpTarget", true).Cast<ComboBox>().Single();
            Label Label(string name) => editor.Controls.Find(name, true).Cast<Label>().Single();
            var saved = Label("MappedHeroXpSavedReference");
            var proposed = Label("MappedHeroXpProposedReference");
            var next = Label("MappedHeroXpNextReference");
            string savedReference = saved.Text;
            var rows = TodResearch.Map.GetProperty("hero_config_assets").GetProperty("rows").EnumerateArray().ToArray();
            for (int index = 0; index < rows.Length; index++)
            {
                var row = rows[index]; uint xp = row.GetProperty("xp").GetUInt32();
                string health = row.GetProperty("hp").GetSingle().ToString("0.###") + " HP";
                var option = targets.Items.Cast<TodEditOption>().Single(option => option.Value == index);
                True(option.Label.Contains(health), "Each XP target must show its shipped HP reference.");
                targets.SelectedItem = option;
                True(proposed.Text.StartsWith($"Row {index} · {health} ·"), "Exact thresholds must select the matching reference row/HP.");
                Equal(savedReference, saved.Text);
                if (index == rows.Length - 1)
                    True(next.Text.Contains("Highest populated reference"), "Do not fabricate rows beyond the catalog.");
                else
                {
                    uint nextXp = rows[index + 1].GetProperty("xp").GetUInt32();
                    True(next.Text.StartsWith($"Row {index + 1} ·") && next.Text.Contains($"{nextXp - xp:N0} XP remaining"), "Next-target preview must use the following XP threshold.");
                }
                byte[] expected = original.ToArray(); BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x418, 4), xp);
                True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", editor.PendingEdits)), "Reference HP previews must never add a health or level write.");
                if (index > 0)
                {
                    input.Value = xp - 1;
                    True(proposed.Text.StartsWith($"Row {index - 1} ·"), "XP immediately below a threshold must retain the preceding reference row.");
                    True(next.Text.Contains("1 XP remaining"), "The target should be one XP away.");
                }
            }
            category.SelectedItem = "Game settings"; category.SelectedItem = "Hero XP";
            True(Label("MappedHeroXpProposedReference").Text.StartsWith("Row 96 ·"), "Custom XP previews must survive category changes.");
            True(original.SequenceEqual(data), "Progression previews must not mutate the original snapshot.");
        });
        Check("Progression preview never invents HP for invalid XP or values beyond the catalog", () =>
        {
            using var editor = new TodSaveEditingControl(); editor.LoadSnapshot(HeroXpFixture(uint.MaxValue), "BCUS98127");
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single(); category.SelectedItem = "Hero XP";
            var targets = editor.Controls.Find("MappedHeroXpTarget", true).Cast<ComboBox>().Single();
            var input = editor.Controls.Find("MappedEdit_hero_xp", true).Cast<NumericTextBox>().Single();
            Label Label(string name) => editor.Controls.Find(name, true).Cast<Label>().Single();
            var saved = Label("MappedHeroXpSavedReference");
            var proposed = Label("MappedHeroXpProposedReference");
            var next = Label("MappedHeroXpNextReference");
            True(saved.Text.Contains("Outside") && proposed.Text.Contains("Outside") && next.Text.Contains("outside"), "High XP must not be silently mapped to the last HP row.");
            True(!editor.HasChanges && input.ReadOnly, "Unknown high XP must be preserved on load.");
            targets.SelectedItem = targets.Items.Cast<TodEditOption>().Single(option => option.Value == 1);
            True(saved.Text.Contains("Outside") && proposed.Text.Contains("11 HP"), "Keep saved and proposed references separate.");
            input.Text = "1.5";
            True(!proposed.Text.Contains("HP") && next.Text.Contains("until XP is valid") && editor.HasInvalidInputs, "Invalid XP must clear stale proposed HP and block saving.");
            targets.SelectedItem = targets.Items.Cast<TodEditOption>().Single(option => option.Value == -2);
            True(!editor.HasChanges && proposed.Text.Contains("Outside"), "Keep saved XP must restore the unknown reference without an edit.");
        });
        Check("Ratchet progression panel renders at narrow widths and larger fonts", () =>
        {
            using var form = new Form { ClientSize = new Size(900, 700), AutoScroll = true,
                StartPosition = FormStartPosition.Manual, Location = new Point(-20000, -20000), ShowInTaskbar = false };
            using var editor = new TodSaveEditingControl(); form.Controls.Add(editor);
            editor.LoadSnapshot(HeroXpFixture(1500), "BCUS98127");
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single(); category.SelectedItem = "Hero XP";
            editor.Controls.Find("MappedEdit_hero_xp", true).Cast<NumericTextBox>().Single().Value = 2000;
            form.Show();
            foreach (float size in new[] { 11f, 16f })
            {
                using var font = new Font("Segoe UI", size); form.Font = font; form.PerformLayout();
                foreach (var control in Descendants(editor).Where(control => control.Name.StartsWith("MappedHeroXp")))
                    True(control.Parent.ClientRectangle.Contains(control.Bounds), "Progression controls must fit their layout at larger font sizes.");
                using var preview = new Bitmap(form.Width, form.Height);
                form.DrawToBitmap(preview, new Rectangle(Point.Empty, preview.Size));
                Directory.CreateDirectory("artifacts");
                preview.Save($"artifacts/ratchet-progression-{(SystemColors.Window.GetBrightness() < 0.5f ? "dark" : "light")}-{size:0}.png");
            }
        });
    }
}
