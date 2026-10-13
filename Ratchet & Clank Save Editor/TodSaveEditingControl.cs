using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.IO;
using System.Numerics;
using System.Windows.Forms;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed class TodSaveEditingControl : UserControl
    {
        private readonly ComboBox category = new() { Name = "MappedEditCategory", DropDownStyle = ComboBoxStyle.DropDownList, Dock = DockStyle.Fill };
        private readonly TableLayoutPanel fieldsPanel = new() { Name = "MappedEditFields", Dock = DockStyle.Top, AutoSize = true, ColumnCount = 2 };
        private readonly Label notice = new() { Name = "MappedEditNotice", AutoSize = true, Dock = DockStyle.Fill };
        private readonly FlowLayoutPanel bulkActions = new() { Name = "MappedBulkActions", Dock = DockStyle.Fill,
            AutoSize = true, WrapContents = true, Margin = new Padding(4, 4, 4, 8) };
        private IReadOnlyList<TodEditField> fields = Array.Empty<TodEditField>();
        private byte[] snapshot;
        private string snapshotRegion;
        private readonly Dictionary<string, decimal> pending = new(StringComparer.Ordinal);
        private readonly Dictionary<string, string> numericText = new(StringComparer.Ordinal);
        private readonly Dictionary<string, string> invalidNumbers = new(StringComparer.Ordinal);
        private bool rendering;
        private string defaultNotice = string.Empty;
        public bool HasChanges => pending.Count > 0 || HasInvalidInputs;
        public bool HasInvalidInputs => invalidNumbers.Count > 0;
        public string ValidationMessage => invalidNumbers.Values.FirstOrDefault() ?? string.Empty;
        public IReadOnlyDictionary<string, decimal> PendingEdits => !HasInvalidInputs
            ? new Dictionary<string, decimal>(pending) : throw new InvalidOperationException(ValidationMessage);
        public event EventHandler EditsChanged;

        public TodSaveEditingControl()
        {
            Name = "MappedSaveEditor";
            Dock = DockStyle.Top;
            AutoSize = true;
            AutoSizeMode = AutoSizeMode.GrowAndShrink;
            var layout = new TableLayoutPanel { Dock = DockStyle.Fill, AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink, ColumnCount = 1, RowCount = 4 };
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            for (int row = 0; row < 4; row++) layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            fieldsPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 230));
            fieldsPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            category.Margin = new Padding(4, 12, 4, 12);
            notice.Margin = new Padding(4, 8, 4, 8);
            layout.Controls.Add(notice, 0, 0);
            layout.Controls.Add(category, 0, 1);
            layout.Controls.Add(bulkActions, 0, 2);
            layout.Controls.Add(fieldsPanel, 0, 3);
            foreach (var action in new[] { (TodBulkEdit.RefillSupportedAmmo, "Refill supported ammo", "MappedRefillAmmo"),
                (TodBulkEdit.MaximumOwnedWeaponTier, "Max weapon levels (current tier)", "MappedMaxWeaponTier") })
            {
                var button = new Button { Name = action.Item3, Text = action.Item2, AutoSize = true,
                    Margin = new Padding(0, 0, 12, 4) };
                button.Click += (_, _) => StageBulk(action.Item1);
                bulkActions.Controls.Add(button);
            }
            Controls.Add(layout);
            category.SelectedIndexChanged += (_, _) => ShowFields();
            LoadSnapshot(null, null);
        }

        public override Size GetPreferredSize(Size proposedSize)
        {
            // Include the complete child table, not the previous viewport height.
            // Font/DPI changes otherwise leave the final row outside the group.
            int width = proposedSize.Width > 0 && proposedSize.Width < int.MaxValue
                ? proposedSize.Width : Math.Max(320, Width);
            int height = notice.GetPreferredSize(new Size(Math.Max(1, width - notice.Margin.Horizontal), 0)).Height +
                notice.Margin.Vertical + fieldsPanel.GetPreferredSize(new Size(width, 0)).Height;
            if (category.Visible) height += category.Height + category.Margin.Vertical;
            if (bulkActions.Visible) height += bulkActions.GetPreferredSize(new Size(width, 0)).Height + bulkActions.Margin.Vertical;
            return new Size(width, height + Padding.Vertical);
        }

        public void LoadSnapshot(byte[] data, string region)
        {
            pending.Clear();
            numericText.Clear();
            invalidNumbers.Clear();
            snapshot = data == null ? null : (byte[])data.Clone();
            snapshotRegion = region;
            fields = TodSaveEditing.Fields(data, region);
            category.Items.Clear();
            bool available = fields.Count > 0;
            defaultNotice = available
                ? "Tools of Destruction USA mapped edits · Not yet tested in-game. Ammo/quick-select choices use reference definitions and ownership. Slots are stored indices, not wheel positions; new duplicates are rejected."
                : "Additional mapped edits are available only for the verified Tools of Destruction USA (BCUS98127) layout. Other games keep their currency controls.";
            notice.Text = defaultNotice;
            category.Visible = available;
            bulkActions.Visible = available;
            foreach (string group in fields.Select(field => field.Category).Distinct()) category.Items.Add(group);
            if (available) category.SelectedIndex = 0;
            else ShowFields();
        }

        private void Stage(TodEditField field, decimal value)
        {
            if (rendering) return;
            if (field.Storage == TodEditStorage.SkillAward || field.Key == "dev_unlock_bonuses")
            {
                var candidate = new Dictionary<string, decimal>(pending, StringComparer.Ordinal);
                if (value == field.Current) candidate.Remove(field.Key);
                else candidate[field.Key] = value;
                TodSkillAwardEditing.Preview(snapshot, candidate); // reject conflicts/overflow before staging
            }
            if (value == EffectiveDefault(field)) pending.Remove(field.Key);
            else pending[field.Key] = value;
            if (TodAppearanceEditing.CancelDependentSelection(field, pending))
                notice.Text = "The staged selection was cleared because its ownership grant was cancelled. The saved selection is unchanged.";
            if (field.Storage is TodEditStorage.WeaponLevel or TodEditStorage.AmmoUpgrade or TodEditStorage.WeaponUpgrade)
            {
                string key = "ammo_" + field.Offset / 20;
                var ammo = fields.Single(item => item.Key == key);
                if (pending.TryGetValue(key, out decimal amount) && amount == EffectiveDefault(ammo)) pending.Remove(key);
                // A reverted upgrade can lower the limit of a hidden ammo entry.
                if (numericText.TryGetValue(key, out string typed))
                {
                    using var input = new NumericTextBox { Minimum = ammo.Minimum, Maximum = EffectiveMaximum(ammo),
                        AllowDecimal = true, FieldName = ammo.Label, Text = typed };
                    if (input.TryGetValue(out decimal parsed))
                    {
                        invalidNumbers.Remove(key);
                        if (parsed == EffectiveDefault(ammo)) pending.Remove(key);
                        else pending[key] = parsed;
                    }
                    else { pending.Remove(key); invalidNumbers[key] = input.ValidationMessage; }
                }
                if (!pending.ContainsKey(key) && !invalidNumbers.ContainsKey(key)) numericText.Remove(key);
            }
            EditsChanged?.Invoke(this, EventArgs.Empty);
        }

        private void StageBulk(TodBulkEdit action)
        {
            if (snapshot == null || !ValidateInputs()) return;
            try
            {
                var existing = new Dictionary<string, decimal>(pending, StringComparer.Ordinal);
                // A typed same-as-original ammo value can be an intentional
                // override of a later level-up refill. Preserve that intent.
                if (action == TodBulkEdit.MaximumOwnedWeaponTier)
                foreach (var field in fields.Where(item => item.Category == "Weapon ammo" && numericText.ContainsKey(item.Key)))
                {
                    using var input = new NumericTextBox { Minimum = field.Minimum, Maximum = EffectiveMaximum(field),
                        AllowDecimal = true, FieldName = field.Label, Text = numericText[field.Key] };
                    if (!input.TryGetValue(out decimal value)) throw new InvalidDataException(input.ValidationMessage);
                    existing[field.Key] = value;
                }
                var plan = TodSaveEditing.PlanBulk(snapshot, snapshotRegion, existing, action);
                pending.Clear();
                foreach (var edit in plan) pending[edit.Key] = edit.Value;
                foreach (var key in pending.Keys.ToArray())
                    if (pending[key] == EffectiveDefault(fields.Single(field => field.Key == key))) pending.Remove(key);
                if (action == TodBulkEdit.RefillSupportedAmmo)
                    foreach (var field in fields.Where(item => item.Category is "Weapon ammo" or "Gadget ammo")) numericText.Remove(field.Key);
                ShowFields();
                EditsChanged?.Invoke(this, EventArgs.Empty);
            }
            catch (InvalidDataException error) { notice.Text = error.Message; }
        }

        private sealed record SkillListItem(TodEditField Field)
        {
            public override string ToString() => Field.Label;
        }

        private void ShowSkillAwards(TodEditField[] selected)
        {
            var summary = new Label { Name = "MappedSkillSummary", AutoSize = true, Dock = DockStyle.Fill,
                Margin = new Padding(4, 8, 4, 12) };
            var list = new CheckedListBox { Name = "MappedSkillAwards", CheckOnClick = true,
                IntegralHeight = false, HorizontalScrollbar = true, Dock = DockStyle.Fill,
                Height = Math.Max(320, Font.Height * 18), Margin = new Padding(4, 4, 4, 8) };
            fieldsPanel.RowCount = 2;
            fieldsPanel.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            fieldsPanel.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            fieldsPanel.Controls.Add(summary, 0, 0); fieldsPanel.SetColumnSpan(summary, 2);
            fieldsPanel.Controls.Add(list, 0, 1); fieldsPanel.SetColumnSpan(list, 2);
            var preview = TodSkillAwardEditing.Preview(snapshot, pending);
            foreach (var field in selected)
                list.Items.Add(new SkillListItem(field), (preview.Bits & (1UL << TodSkillAwardEditing.Id(field))) != 0);
            void RefreshSummary()
            {
                var current = TodSkillAwardEditing.Preview(snapshot, pending);
                uint saved = BinaryPrimitives.ReadUInt32BigEndian(snapshot.AsSpan(0x8708, 4));
                summary.Text = $"Earned after saving: {BitOperations.PopCount(current.Bits & ((1UL << 60) - 1))}/60 · " +
                    $"Weighted points: {saved} → {current.Score} · New awards: {current.NewAwards}";
                int final = Array.FindIndex(selected, field => TodSkillAwardEditing.Id(field) == 59);
                bool wasRendering = rendering; rendering = true;
                try { if (final >= 0) list.SetItemChecked(final, (current.Bits & (1UL << 59)) != 0); }
                finally { rendering = wasRendering; }
            }
            RefreshSummary();
            list.ItemCheck += (_, e) =>
            {
                if (rendering) return;
                var field = ((SkillListItem)list.Items[e.Index]).Field;
                if (field.Maximum == 0) { e.NewValue = e.CurrentValue; return; }
                try
                {
                    Stage(field, e.NewValue == CheckState.Checked ? 1 : 0);
                    RefreshSummary();
                }
                catch (InvalidDataException error) { e.NewValue = e.CurrentValue; notice.Text = error.Message; }
            };
        }

        private decimal EffectiveDefault(TodEditField field)
        {
            if (field.Category == "Weapon ammo")
            {
                string key = "weapon_level_" + field.Key["ammo_".Length..];
                var level = fields.FirstOrDefault(item => item.Key == key);
                if ((level != null && pending.TryGetValue(key, out decimal selected) && selected > level.Current) ||
                    pending.Any(edit => edit.Value == 1 && fields.Any(item => item.Key == edit.Key &&
                        item.Storage == TodEditStorage.AmmoUpgrade && item.Offset / 20 == field.Offset / 20)))
                    return EffectiveMaximum(field);
            }
            return field.Current;
        }

        private decimal EffectiveMaximum(TodEditField field) => field.Category == "Weapon ammo"
            ? TodAmmoUpgradeEditing.Maximum(snapshot, field, pending) : field.Maximum;

        private NumericTextBox NumericInput(TodEditField field, decimal value, decimal? maximum = null)
        {
            var numeric = new NumericTextBox
            {
                Minimum = field.Minimum, Maximum = maximum ?? EffectiveMaximum(field),
                AllowDecimal = field.Storage != TodEditStorage.HeroXp, FieldName = field.Label, Value = value
            };
            // Keep incomplete/invalid text across category changes.
            if (numericText.TryGetValue(field.Key, out string typed)) numeric.Text = typed;
            numeric.ValueChanged += (_, _) =>
            {
                if (rendering) return;
                numericText[field.Key] = numeric.Text;
                if (numeric.TryGetValue(out decimal number))
                {
                    invalidNumbers.Remove(field.Key);
                    Stage(field, number);
                }
                else
                {
                    pending.Remove(field.Key);
                    invalidNumbers[field.Key] = numeric.ValidationMessage;
                    EditsChanged?.Invoke(this, EventArgs.Empty);
                }
            };
            return numeric;
        }

        private void ShowHeroXp(TodEditField field)
        {
            bool keepHigh = field.Current > TodHeroXpEditing.MaximumXp &&
                !pending.ContainsKey(field.Key) && !invalidNumbers.ContainsKey(field.Key);
            decimal initial = pending.TryGetValue(field.Key, out decimal edited) ? edited :
                keepHigh ? field.Current : Math.Min(field.Current, TodHeroXpEditing.MaximumXp);
            var numeric = NumericInput(field, initial, keepHigh ? field.Current : TodHeroXpEditing.MaximumXp);
            numeric.ReadOnly = keepHigh;
            numeric.Name = "MappedEdit_hero_xp"; numeric.Dock = DockStyle.Fill;
            numeric.Margin = new Padding(4, 8, 4, 8);
            var targets = new ComboBox { Name = "MappedHeroXpTarget", DropDownStyle = ComboBoxStyle.DropDownList,
                Dock = DockStyle.Fill, MaxDropDownItems = 12, IntegralHeight = false, Margin = new Padding(4, 8, 4, 8) };
            targets.Items.Add(new TodEditOption(-2, $"Keep saved XP ({field.Current:N0})"));
            targets.Items.Add(new TodEditOption(-1, "Custom XP"));
            foreach (var target in TodHeroXpEditing.Targets)
                targets.Items.Add(new TodEditOption(target.Index, $"Reference row {target.Index} — {target.Xp:N0} XP"));
            var summary = new Label { Name = "MappedHeroXpSummary", AutoSize = true, Dock = DockStyle.Fill,
                Margin = new Padding(4, 8, 4, 8) };
            bool synchronizing = false;
            void Refresh()
            {
                bool valid = numeric.TryGetValue(out decimal xp);
                var exact = valid ? TodHeroXpEditing.Targets.FirstOrDefault(target => target.Xp == xp) : null;
                synchronizing = true;
                int choice = valid && xp == field.Current ? -2 : exact?.Index ?? -1;
                try { targets.SelectedItem = targets.Items.Cast<TodEditOption>().Single(option => option.Value == choice); }
                finally { synchronizing = false; }
                var met = valid ? TodHeroXpEditing.Targets.Last(target => target.Xp <= xp) : null;
                summary.Text = valid && xp > TodHeroXpEditing.MaximumXp
                    ? "Saved XP is outside the reference range and is kept unchanged. Choose a target or Custom XP to set a value from 0–989,000."
                    : valid
                    ? $"Saved XP: {field.Current:N0} → {xp:N0}. At/above reference row {met.Index} (zero-based); not an observed hero level."
                    : "Enter valid whole-number XP or choose a reference target. Save All is blocked until the input is valid.";
            }
            targets.SelectedIndexChanged += (_, _) =>
            {
                if (rendering || synchronizing || targets.SelectedItem is not TodEditOption option) return;
                if (option.Value == -1 && !numeric.ReadOnly) { numeric.Focus(); return; }
                decimal xp = option.Value == -2 ? field.Current : option.Value == -1 ? 0 : TodHeroXpEditing.Targets[(int)option.Value].Xp;
                bool wasRendering = rendering; rendering = true;
                try
                {
                    numeric.ReadOnly = xp == field.Current && xp > TodHeroXpEditing.MaximumXp;
                    numeric.Maximum = numeric.ReadOnly ? field.Current : TodHeroXpEditing.MaximumXp;
                    numeric.Value = xp;
                }
                finally { rendering = wasRendering; }
                numericText[field.Key] = numeric.Text;
                invalidNumbers.Remove(field.Key);
                Stage(field, xp);
                Refresh();
            };
            numeric.ValueChanged += (_, _) => Refresh();
            Refresh();
            fieldsPanel.RowCount = 3;
            for (int row = 0; row < 3; row++) fieldsPanel.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            fieldsPanel.Controls.Add(new Label { Text = "Hero XP", AutoSize = true, Dock = DockStyle.Fill,
                TextAlign = ContentAlignment.MiddleLeft, Margin = new Padding(4, 8, 12, 8) }, 0, 0);
            fieldsPanel.Controls.Add(numeric, 1, 0);
            fieldsPanel.Controls.Add(new Label { Text = "Reference target", AutoSize = true, Dock = DockStyle.Fill,
                TextAlign = ContentAlignment.MiddleLeft, Margin = new Padding(4, 8, 12, 8) }, 0, 1);
            fieldsPanel.Controls.Add(targets, 1, 1);
            fieldsPanel.Controls.Add(summary, 0, 2); fieldsPanel.SetColumnSpan(summary, 2);
        }

        public bool ValidateInputs()
        {
            if (!HasInvalidInputs) return true;
            string key = invalidNumbers.Keys.First();
            category.SelectedItem = fields.Single(field => field.Key == key).Category;
            var input = Controls.Find("MappedEdit_" + key, true).OfType<NumericTextBox>().FirstOrDefault();
            input?.Focus();
            input?.SelectAll();
            return false;
        }

        private void ShowFields()
        {
            notice.Text = category.SelectedItem?.ToString() switch
            {
                "Bonus effects" => "Required skill scores: hero head 50, enemy head 100, commentary 200, James Zurkon 400, mirror 500. Commentary requests playback only in the supported runtime language (not stored here). Zurkon Off cannot override its separate runtime flag. No points or unlocks are granted. Not yet tested in-game.",
                "Rewards" => "Bolt multiplier: 1–20×, only with an existing nonzero replay flag and valid multiplier. This does not enable replay mode. Loading seeds the runtime accumulator; sampled health loss can reset the multiplier to 1×. Fractional values use native float storage. Not yet tested in-game.",
                "Developer helpers" => "One-shot actions on Save All. Blueprints OR the native 13-bit grant mask, preserving other bits. Unlock bonuses SETS score to 840 and changes every zero bonus state to 1, preserving nonzero states; this can request multiple effects. It does not award earned skills. Run it separately from skill awards and bonus selections. Not yet tested in-game.",
                "Gadget ammo" => "Ammo for already-owned consumables only. Groovitron and traversal gadgets stay read-only because of linked state. Values use the native float storage and reference capacities, not a promised use count. Not yet tested in-game.",
                "Ammo upgrades" => "Add missing ordinary capacity nodes next to already-installed nodes. Existing upgrades cannot be removed. Adding a node refills to the new capacity; Weapon ammo previews it and allows an override. Raritanium is unchanged: this is a direct save edit, not a purchase. Special and unnamed effects stay read-only. Not yet tested in-game.",
                "Weapon upgrades" => "Add missing ordinary upgrades next to already-installed nodes. Labels show shipped modifier values, not measured live stats; signed speed/duration values are kept as defined. These nodes do not refill ammo or charge raritanium. Save and reopen to expose further adjacent nodes. No removals, special nodes or unnamed effects. Not yet tested in-game.",
                "Weapon levels" => "Levels stay within the weapon's existing 1–5 or 6–10 tier. A change sets matching XP; increases refill ammo, decreases keep ammo. Weapon ammo shows the planned refill and allows an override. No ownership, upgrades or purchases are granted. Not yet tested in-game.",
                "Skill awards" => "Check missing skills to award them on Save All. Earned skills cannot be removed. New awards add their native point values to the existing score; HARDCORE follows the last missing ordinary skill automatically. Labels are formatted native names. Existing score/bit mismatches and unknown bits are retained. Unlock bonuses must be saved separately. Not yet tested in-game.",
                "Armor unlocks" => "Grant missing armor ownership on Save All. Already-owned entries cannot be removed. Grants do not equip armor, spend bolts, change vendor availability or enable challenge mode. Choose a granted item under Appearance if wanted. Not yet tested in-game.",
                "Skin unlocks" => "Grant missing skin ownership on Save All, including Jailbird. Already-owned entries cannot be removed. No special bolts are spent; grants do not select a skin. Choose a granted item under Appearance if wanted. Not yet tested in-game.",
                "Appearance" => "Select owned armor or skins, including items granted in this Save All operation. Cancelling a grant also clears a selection that depends on it. Selection alone does not grant ownership. Runtime effects are not simulated. Not yet tested in-game.",
                "Hero XP" => "Whole-number XP from 0–989,000, or a shipped reference target. Rows 0–97 are zero-based config indices, not player-facing level labels. This is an editor bound, not a native clamp or guaranteed maximum level. Only saved XP changes; no health, level, challenge mode or runtime callbacks are written. Active config overrides and rows 98/99 are unknown. Not yet tested in-game.",
                _ => defaultNotice
            };
            rendering = true;
            fieldsPanel.SuspendLayout();
            try
            {
                foreach (Control control in fieldsPanel.Controls.Cast<Control>().ToArray()) control.Dispose();
                fieldsPanel.Controls.Clear();
                fieldsPanel.RowStyles.Clear();
                var selected = fields.Where(field => field.Category == category.SelectedItem?.ToString())
                    .Select(field => field with { Options = TodAppearanceEditing.SelectionOptions(field, snapshot, pending) }).ToArray();
                if (category.SelectedItem?.ToString() == "Skill awards") { ShowSkillAwards(selected); return; }
                if (category.SelectedItem?.ToString() == "Hero XP") { ShowHeroXp(selected.Single()); return; }
                fieldsPanel.RowCount = selected.Length;
                for (int row = 0; row < selected.Length; row++)
                {
                    var field = selected[row];
                    decimal value = pending.TryGetValue(field.Key, out var edited) ? edited : EffectiveDefault(field);
                    Control input;
                    if (field.Options != null)
                    {
                        var combo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList,
                            Enabled = field.Storage != TodEditStorage.OwnershipGrant || field.Current == 0 };
                        foreach (var option in field.Options) combo.Items.Add(option);
                        combo.SelectedItem = field.Options.First(option => option.Value == value);
                        combo.SelectedIndexChanged += (_, _) =>
                        {
                            if (combo.SelectedItem is TodEditOption option)
                            {
                                try { Stage(field, option.Value); }
                                catch (InvalidDataException error)
                                {
                                    notice.Text = error.Message;
                                    bool wasRendering = rendering; rendering = true;
                                    try { combo.SelectedItem = field.Options.First(item => item.Value ==
                                        (pending.TryGetValue(field.Key, out decimal kept) ? kept : EffectiveDefault(field))); }
                                    finally { rendering = wasRendering; }
                                }
                            }
                        };
                        input = combo;
                    }
                    else if (field.Storage is TodEditStorage.BooleanByte or TodEditStorage.BooleanWord)
                    {
                        var check = new CheckBox { Checked = value != 0, AutoSize = true, Text = "Enabled" };
                        check.CheckedChanged += (_, _) => Stage(field, check.Checked ? 1 : 0);
                        input = check;
                    }
                    else
                    {
                        input = NumericInput(field, value);
                    }
                    input.Name = "MappedEdit_" + field.Key;
                    input.Dock = DockStyle.Fill;
                    input.Margin = new Padding(4, 8, 4, 8);
                    fieldsPanel.RowStyles.Add(new RowStyle(SizeType.AutoSize));
                    fieldsPanel.Controls.Add(new Label { Text = field.Label, AutoSize = true, Dock = DockStyle.Fill,
                        TextAlign = ContentAlignment.MiddleLeft, Margin = new Padding(4, 8, 12, 8) }, 0, row);
                    fieldsPanel.Controls.Add(input, 1, row);
                }
            }
            finally { fieldsPanel.ResumeLayout(true); rendering = false; }
        }
    }
}
