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
        private readonly Dictionary<string, decimal> pending = new(StringComparer.Ordinal);
        private readonly Dictionary<string, string> numericText = new(StringComparer.Ordinal);
        private readonly Dictionary<string, string> invalidNumbers = new(StringComparer.Ordinal);
        private bool rendering;
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
            fields = TodSaveEditing.Fields(data, region);
            category.Items.Clear();
            bool available = fields.Count > 0;
            notice.Text = available
                ? "Tools of Destruction USA mapped edits · Not yet tested in-game. Ammo/quick-select choices use reference definitions and ownership. Slots are stored indices, not wheel positions; new duplicates are rejected."
                : "Additional mapped edits are available only for the verified Tools of Destruction USA (BCUS98127) layout. Other games keep their currency controls.";
            category.Visible = available;
            foreach (string group in fields.Select(field => field.Category).Distinct()) category.Items.Add(group);
            if (available) category.SelectedIndex = 0;
            else ShowFields();
        }

        private void Stage(TodEditField field, decimal value)
        {
            if (rendering) return;
            if (value == field.Current) pending.Remove(field.Key);
            else pending[field.Key] = value;
            EditsChanged?.Invoke(this, EventArgs.Empty);
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
                    decimal value = pending.TryGetValue(field.Key, out var edited) ? edited : field.Current;
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
                            Minimum = field.Minimum, Maximum = field.Maximum,
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
