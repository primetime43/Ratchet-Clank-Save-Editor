using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed class Rc1SaveEditingControl : UserControl
    {
        private readonly TableLayoutPanel layout = new() { Dock = DockStyle.Top, AutoSize = true, ColumnCount = 3 };
        private readonly Dictionary<string, NumericTextBox> inputs = new(StringComparer.Ordinal);
        private readonly Dictionary<string, decimal> pending = new(StringComparer.Ordinal);
        private bool loading;
        public bool HasInvalidInputs => inputs.Values.Any(input => !input.IsValid);
        public bool HasChanges => pending.Count > 0 || HasInvalidInputs;
        public string ValidationMessage => inputs.Values.FirstOrDefault(input => !input.IsValid)?.ValidationMessage ?? string.Empty;
        public IReadOnlyDictionary<string, decimal> PendingEdits => !HasInvalidInputs
            ? new Dictionary<string, decimal>(pending) : throw new InvalidOperationException(ValidationMessage);
        public event EventHandler EditsChanged;

        public Rc1SaveEditingControl()
        {
            Name = "Rc1SaveEditor";
            Dock = DockStyle.Top;
            AutoSize = true;
            AutoSizeMode = AutoSizeMode.GrowAndShrink;
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 45));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 35));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 20));
            Controls.Add(layout);
            Visible = false;
        }

        public void LoadSnapshot(byte[] data, string region)
        {
            loading = true;
            SuspendLayout();
            try
            {
                foreach (Control control in layout.Controls.Cast<Control>().ToArray()) control.Dispose();
                layout.Controls.Clear(); layout.RowStyles.Clear(); layout.RowCount = 0;
                inputs.Clear(); pending.Clear();
                bool isRc1 = Rc1SaveInspection.Supports(region);
                Visible = isRc1;
                if (!isRc1) return;
                var fields = Rc1SaveEditing.Fields(data, region);
                bool supported = Rc1SaveEditing.Supports(data, region);
                var notice = new Label { Name = "Rc1EditNotice", AutoSize = true, Dock = DockStyle.Fill,
                    Margin = new Padding(4, 8, 4, 12), Text = !supported
                        ? "Ammo edits require the verified European RC1 (NPEA00385) layout."
                        : fields.Count == 0 ? "No owned weapons with supported ammo values are available in this save."
                        : "RC1 weapon ammo · Edit ammo for owned weapons up to the reference capacity. Apply changes with Save All." };
                AddRow(notice); layout.SetColumnSpan(notice, 3);
                if (fields.Count == 0) return;
                var refill = new Button { Name = "Rc1RefillAmmo", Text = "Refill owned weapon ammo", AutoSize = true,
                    Margin = new Padding(4, 4, 4, 12) };
                refill.Click += (_, _) =>
                {
                    if (!ValidateInputs()) return;
                    foreach (var field in fields) inputs[field.Key].Value = field.Maximum;
                };
                AddRow(refill); layout.SetColumnSpan(refill, 3);
                foreach (var field in fields)
                {
                    var input = new NumericTextBox { Name = "Rc1Edit_" + field.Key, FieldName = field.Name + " ammo",
                        Minimum = 0, Maximum = field.Maximum, Value = field.Current, Dock = DockStyle.Fill,
                        Margin = new Padding(4, 6, 4, 6), AccessibleName = field.Name + " ammo" };
                    inputs.Add(field.Key, input);
                    input.ValueChanged += (_, _) =>
                    {
                        if (loading) return;
                        if (input.TryGetValue(out decimal value))
                        {
                            if (value == field.Current) pending.Remove(field.Key); else pending[field.Key] = value;
                        }
                        else pending.Remove(field.Key);
                        EditsChanged?.Invoke(this, EventArgs.Empty);
                    };
                    var label = new Label { Text = field.Name, AutoSize = true, Dock = DockStyle.Fill,
                        UseMnemonic = false, TextAlign = ContentAlignment.MiddleLeft, Margin = new Padding(4, 6, 4, 6) };
                    var limit = new Label { Text = "Max " + field.Maximum, AutoSize = true, Dock = DockStyle.Fill,
                        TextAlign = ContentAlignment.MiddleLeft, Margin = new Padding(8, 6, 4, 6) };
                    AddRow(label, input, limit);
                }
            }
            finally { loading = false; ResumeLayout(true); }
        }

        private void AddRow(params Control[] controls)
        {
            int row = layout.RowCount++;
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            for (int column = 0; column < controls.Length; column++) layout.Controls.Add(controls[column], column, row);
        }

        public bool ValidateInputs()
        {
            var invalid = inputs.Values.FirstOrDefault(input => !input.IsValid);
            if (invalid == null) return true;
            invalid.Focus(); invalid.SelectAll();
            return false;
        }
    }
}
