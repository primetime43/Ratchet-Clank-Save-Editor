using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed class TodSaveEditingControl : UserControl
    {
        private readonly ComboBox category = new() { Name = "MappedEditCategory", DropDownStyle = ComboBoxStyle.DropDownList, Dock = DockStyle.Fill };
        private readonly TableLayoutPanel fieldsPanel = new() { Name = "MappedEditFields", Dock = DockStyle.Top, AutoSize = true, ColumnCount = 2 };
        private readonly Label notice = new() { Name = "MappedEditNotice", AutoSize = true, Dock = DockStyle.Fill };
        private IReadOnlyList<TodEditField> fields = Array.Empty<TodEditField>();
        private byte[] snapshot;
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
                AutoSizeMode = AutoSizeMode.GrowAndShrink, ColumnCount = 1, RowCount = 3 };
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            for (int row = 0; row < 3; row++) layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            fieldsPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 230));
            fieldsPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            category.Margin = new Padding(4, 12, 4, 12);
            notice.Margin = new Padding(4, 8, 4, 8);
            layout.Controls.Add(notice, 0, 0);
            layout.Controls.Add(category, 0, 1);
            layout.Controls.Add(fieldsPanel, 0, 2);
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
            return new Size(width, height + Padding.Vertical);
        }

        public void LoadSnapshot(byte[] data, string region)
        {
            pending.Clear();
            numericText.Clear();
            invalidNumbers.Clear();
            snapshot = data == null ? null : (byte[])data.Clone();
            fields = TodSaveEditing.Fields(data, region);
            category.Items.Clear();
            bool available = fields.Count > 0;
            defaultNotice = available
                ? "Tools of Destruction USA mapped edits · Not yet tested in-game. Ammo/quick-select choices use reference definitions and ownership. Slots are stored indices, not wheel positions; new duplicates are rejected."
                : "Additional mapped edits are available only for the verified Tools of Destruction USA (BCUS98127) layout. Other games keep their currency controls.";
            notice.Text = defaultNotice;
            category.Visible = available;
            foreach (string group in fields.Select(field => field.Category).Distinct()) category.Items.Add(group);
            if (available) category.SelectedIndex = 0;
            else ShowFields();
        }

        private void Stage(TodEditField field, decimal value)
        {
            if (rendering) return;
            if (value == EffectiveDefault(field)) pending.Remove(field.Key);
            else pending[field.Key] = value;
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
                "Gadget ammo" => "Ammo for already-owned consumables only. Groovitron and traversal gadgets stay read-only because of linked state. Values use the native float storage and reference capacities, not a promised use count. Not yet tested in-game.",
                "Ammo upgrades" => "Add missing ordinary capacity nodes next to already-installed nodes. Existing upgrades cannot be removed. Adding a node refills to the new capacity; Weapon ammo previews it and allows an override. Raritanium is unchanged: this is a direct save edit, not a purchase. Special and unnamed effects stay read-only. Not yet tested in-game.",
                "Weapon upgrades" => "Add missing ordinary upgrades next to already-installed nodes. Labels show shipped modifier values, not measured live stats; signed speed/duration values are kept as defined. These nodes do not refill ammo or charge raritanium. Save and reopen to expose further adjacent nodes. No removals, special nodes or unnamed effects. Not yet tested in-game.",
                "Weapon levels" => "Levels stay within the weapon's existing 1–5 or 6–10 tier. A change sets matching XP; increases refill ammo, decreases keep ammo. Weapon ammo shows the planned refill and allows an override. No ownership, upgrades or purchases are granted. Not yet tested in-game.",
                _ => defaultNotice
            };
            rendering = true;
            fieldsPanel.SuspendLayout();
            try
            {
                foreach (Control control in fieldsPanel.Controls.Cast<Control>().ToArray()) control.Dispose();
                fieldsPanel.Controls.Clear();
                fieldsPanel.RowStyles.Clear();
                var selected = fields.Where(field => field.Category == category.SelectedItem?.ToString()).ToArray();
                fieldsPanel.RowCount = selected.Length;
                for (int row = 0; row < selected.Length; row++)
                {
                    var field = selected[row];
                    decimal value = pending.TryGetValue(field.Key, out var edited) ? edited : EffectiveDefault(field);
                    Control input;
                    if (field.Options != null)
                    {
                        var combo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList };
                        foreach (var option in field.Options) combo.Items.Add(option);
                        combo.SelectedItem = field.Options.First(option => option.Value == value);
                        combo.SelectedIndexChanged += (_, _) =>
                        {
                            if (combo.SelectedItem is TodEditOption option) Stage(field, option.Value);
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
                        var numeric = new NumericTextBox
                        {
                            Minimum = field.Minimum, Maximum = EffectiveMaximum(field),
                            AllowDecimal = true, FieldName = field.Label, Value = value
                        };
                        // Text survives category changes, including incomplete/invalid input.
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
                        input = numeric;
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
