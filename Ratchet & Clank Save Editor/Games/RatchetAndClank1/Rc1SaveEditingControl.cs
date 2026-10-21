using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.IO;
using System.Windows.Forms;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed class Rc1SaveEditingControl : UserControl
    {
        private readonly TableLayoutPanel layout = new() { Dock = DockStyle.Top, AutoSize = true, ColumnCount = 3 };
        private readonly Dictionary<string, NumericTextBox> inputs = new(StringComparer.Ordinal);
        private readonly Dictionary<string, decimal> pending = new(StringComparer.Ordinal);
        private readonly Dictionary<Control, string> pages = new();
        private ComboBox category;
        private Label notice;
        private byte[] snapshot;
        private string snapshotRegion;
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
                inputs.Clear(); pending.Clear(); pages.Clear();
                snapshot = data == null ? null : (byte[])data.Clone(); snapshotRegion = region;
                bool isRc1 = Rc1SaveInspection.Supports(region);
                Visible = isRc1;
                if (!isRc1) return;
                var fields = Rc1SaveEditing.Fields(data, region);
                bool supported = Rc1SaveEditing.Supports(data, region);
                notice = new Label { Name = "Rc1EditNotice", AutoSize = true, Dock = DockStyle.Fill,
                    Margin = new Padding(4, 8, 4, 12), Text = !supported
                        ? "Mapped edits require the verified European RC1 (NPEA00385) layout."
                        : "RC1 mapped edits · Save All applies staged changes. Save weapon grants before editing their ammo or assigning a specific quick-select slot." };
                AddRow(notice); layout.SetColumnSpan(notice, 3);
                if (!supported) return;
                category = new ComboBox { Name = "Rc1EditCategory", DropDownStyle = ComboBoxStyle.DropDownList,
                    Dock = DockStyle.Fill, Margin = new Padding(4, 4, 4, 12), Sorted = true };
                category.Items.AddRange(new object[] { "Weapon ammo", "Weapon unlocks", "Quick select", "Gold upgrades", "Gadget unlocks" });
                category.SelectedIndexChanged += (_, _) => ShowCategory();
                AddRow(category); layout.SetColumnSpan(category, 3);
                var refill = new Button { Name = "Rc1RefillAmmo", Text = "Refill owned weapon ammo", AutoSize = true,
                    Margin = new Padding(4, 4, 4, 12) };
                refill.Click += (_, _) =>
                {
                    if (!ValidateInputs()) return;
                    foreach (var field in fields) inputs[field.Key].Value = field.Maximum;
                };
                AddPageRow("Weapon ammo", refill); layout.SetColumnSpan(refill, 3);
                refill.Enabled = fields.Count > 0;
                if (fields.Count == 0)
                {
                    var empty = new Label { AutoSize = true, Text = "No owned weapons with supported ammo values are available." };
                    AddPageRow("Weapon ammo", empty); layout.SetColumnSpan(empty, 3);
                }
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
                    AddPageRow("Weapon ammo", label, input, limit);
                }
                foreach (var field in Rc1WeaponEditing.Grants(data, region))
                {
                    var check = new CheckBox { Name = "Rc1Edit_" + field.Key, Text = field.Weapon.Name,
                        Checked = field.Owned, Enabled = !field.Owned, AutoSize = true, Margin = new Padding(4, 6, 4, 6) };
                    check.CheckedChanged += (_, _) =>
                    {
                        if (loading) return;
                        decimal value = check.Checked ? 1 : 0;
                        if (TryStage(field.Key, value, field.Owned ? 1 : 0)) return;
                        loading = true; check.Checked = !check.Checked; loading = false;
                    };
                    AddPageRow("Weapon unlocks", check); layout.SetColumnSpan(check, 3);
                }
                var grantHint = new Label { AutoSize = true, Dock = DockStyle.Fill,
                    Text = "Grants add ownership, starting ammo and related inventory entries without spending bolts. All 15 combat weapons are supported.", Margin = new Padding(4, 10, 4, 8) };
                AddPageRow("Weapon unlocks", grantHint); layout.SetColumnSpan(grantHint, 3);
                foreach (var field in Rc1GadgetEditing.Grants(data, region))
                {
                    var check = new CheckBox { Name = "Rc1Edit_" + field.Key, Text = field.Gadget.Name,
                        Checked = field.Owned, Enabled = !field.Owned, AutoSize = true, Margin = new Padding(4, 6, 4, 6) };
                    check.CheckedChanged += (_, _) =>
                    {
                        if (loading) return;
                        if (TryStage(field.Key, check.Checked ? 1 : 0, field.Owned ? 1 : 0)) return;
                        loading = true; check.Checked = !check.Checked; loading = false;
                    };
                    AddPageRow("Gadget unlocks", check); layout.SetColumnSpan(check, 3);
                }
                var gadgetHint = new Label { AutoSize = true, Dock = DockStyle.Fill,
                    Text = "Grants add six handheld gadgets and three passive upgrades without spending bolts.\r\n" +
                        "Handheld gadgets use a free quick-select slot when available. Save first to choose a specific slot.\r\n" +
                        "Mission progress, movement equipment and the currently equipped item are preserved.",
                    Margin = new Padding(4, 10, 4, 8) };
                AddPageRow("Gadget unlocks", gadgetHint); layout.SetColumnSpan(gadgetHint, 3);
                var goldFields = Rc1GoldUpgradeEditing.Fields(data, region);
                foreach (var field in goldFields)
                {
                    var check = new CheckBox { Name = "Rc1Edit_" + field.Key, Text = "Gold " + field.Name,
                        Checked = field.Upgraded, Enabled = !field.Upgraded, AutoSize = true, Margin = new Padding(4, 6, 4, 6) };
                    check.CheckedChanged += (_, _) =>
                    {
                        if (loading) return;
                        if (TryStage(field.Key, check.Checked ? 1 : 0, field.Upgraded ? 1 : 0)) return;
                        loading = true; check.Checked = !check.Checked; loading = false;
                    };
                    AddPageRow("Gold upgrades", check); layout.SetColumnSpan(check, 3);
                }
                var goldHint = new Label { AutoSize = true, Dock = DockStyle.Fill,
                    Text = (goldFields.Count == 0 ? "No owned weapons with supported gold upgrades are available.\r\n" : "") +
                        "Add gold upgrades to owned weapons. Save a weapon grant first to expose its upgrade.\r\n" +
                        "Ordinary bolts and collected gold bolts are preserved.\r\n" +
                        "The game counts four gold bolts spent per upgrade; the available balance may fall to zero.",
                    Margin = new Padding(4, 10, 4, 8) };
                AddPageRow("Gold upgrades", goldHint); layout.SetColumnSpan(goldHint, 3);
                int slotIndex = 0;
                foreach (var field in Rc1WeaponEditing.QuickSelect(data, region))
                {
                    var label = new Label { Text = "Stored slot " + (++slotIndex), AutoSize = true,
                        Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft, Margin = new Padding(4, 6, 4, 6) };
                    var choices = new ComboBox { Name = "Rc1Edit_" + field.Key, DropDownStyle = ComboBoxStyle.DropDownList,
                        Dock = DockStyle.Fill, Margin = new Padding(4, 6, 4, 6) };
                    choices.Items.AddRange(field.Options.Cast<object>().ToArray());
                    choices.SelectedItem = field.Options.Single(option => option.Value == field.Current);
                    uint selected = field.Current;
                    choices.SelectedIndexChanged += (_, _) =>
                    {
                        if (loading || choices.SelectedItem is not Rc1QuickOption option) return;
                        if (TryStage(field.Key, option.Value, field.Current)) { selected = option.Value; return; }
                        loading = true; choices.SelectedItem = field.Options.Single(item => item.Value == selected); loading = false;
                    };
                    AddPageRow("Quick select", label, choices); layout.SetColumnSpan(choices, 2);
                }
                var slotHint = new Label { AutoSize = true, Dock = DockStyle.Fill,
                    Text = "Choose an owned weapon, supported handheld gadget or Empty.\r\nClear an item's old slot before moving it. Stored slot numbers are not wheel positions.", Margin = new Padding(4, 10, 4, 8) };
                AddPageRow("Quick select", slotHint); layout.SetColumnSpan(slotHint, 3);
                category.SelectedItem = "Weapon ammo";
            }
            finally { loading = false; ResumeLayout(true); }
        }

        private void AddRow(params Control[] controls)
        {
            int row = layout.RowCount++;
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            for (int column = 0; column < controls.Length; column++) layout.Controls.Add(controls[column], column, row);
        }

        private void AddPageRow(string page, params Control[] controls)
        {
            AddRow(controls);
            foreach (var control in controls) pages.Add(control, page);
        }

        private void ShowCategory()
        {
            layout.SuspendLayout();
            foreach (var pair in pages) pair.Key.Visible = pair.Value == category.Text;
            layout.ResumeLayout(true);
        }

        private bool TryStage(string key, decimal value, decimal baseline)
        {
            if (!ValidateInputs()) return false;
            var candidate = new Dictionary<string, decimal>(pending, StringComparer.Ordinal);
            if (value == baseline) candidate.Remove(key); else candidate[key] = value;
            try { Rc1SaveEditing.Apply(snapshot, snapshotRegion, candidate); }
            catch (InvalidDataException error) { notice.Text = error.Message; return false; }
            pending.Clear(); foreach (var edit in candidate) pending.Add(edit.Key, edit.Value);
            notice.Text = "Changes staged · Save All applies them with an original backup.";
            EditsChanged?.Invoke(this, EventArgs.Empty);
            return true;
        }

        public bool ValidateInputs()
        {
            var invalid = inputs.Values.FirstOrDefault(input => !input.IsValid);
            if (invalid == null) return true;
            if (category != null) category.SelectedItem = "Weapon ammo";
            invalid.Focus(); invalid.SelectAll();
            return false;
        }
    }
}
