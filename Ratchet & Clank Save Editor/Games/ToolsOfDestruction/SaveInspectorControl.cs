using System;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed class SaveInspectorControl : UserControl
    {
        private readonly ComboBox views = new() { Name = "InspectionView", DropDownStyle = ComboBoxStyle.DropDownList, Width = 270 };
        private readonly ComboBox upgradeWeapon = new() { Name = "UpgradeWeaponFilter", DropDownStyle = ComboBoxStyle.DropDownList, Width = 200, Visible = false };
        private bool updatingWeaponFilter;
        private readonly CheckBox technical = new() { Name = "InspectionTechnical", Text = "Technical", AutoSize = true };
        private readonly NumericTextBox hexOffset = new() { Name = "HexOffset", Hexadecimal = true,
            FieldName = "File offset", Width = 100, Visible = false };
        private readonly DataGridView grid = new()
        {
            Name = "InspectionGrid", Dock = DockStyle.Fill, ReadOnly = true, AllowUserToAddRows = false,
            AllowUserToDeleteRows = false, AllowUserToOrderColumns = true, AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill,
            MultiSelect = false, SelectionMode = DataGridViewSelectionMode.FullRowSelect, RowHeadersVisible = false,
            BackgroundColor = SystemColors.Window, BorderStyle = BorderStyle.FixedSingle
        };
        private readonly TextBox details = new() { Name = "InspectionDetails", Dock = DockStyle.Fill, Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical };
        private readonly TextBox hex = new() { Name = "HexBytes", Font = new Font("Consolas", 11F), Dock = DockStyle.Fill, Multiline = true, ReadOnly = true, WordWrap = false, ScrollBars = ScrollBars.Both, Visible = false };
        private readonly ToolTip tip = new();
        private TodSaveInspection snapshot;
        private Rc1SaveInspection rc1;
        private readonly string[] todViews;
        private InspectionTable containers;
        public bool HasSnapshot => snapshot?.Available == true || rc1?.Available == true;
        private bool HasTodSnapshot => snapshot?.Available == true;
        private string SnapshotMessage => rc1?.Message ?? snapshot?.Message;
        public event Action<int> WeaponReferenceRequested;

        public SaveInspectorControl()
        {
            Dock = DockStyle.Fill;
            AutoScaleDimensions = new SizeF(96, 96);
            AutoScaleMode = AutoScaleMode.Dpi;
            Font = new Font("Segoe UI", 11F);
            Padding = new Padding(10);
            var toolbar = new FlowLayoutPanel
            {
                Name = "InspectionToolbar", Dock = DockStyle.Top, AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink, WrapContents = true,
                Padding = new Padding(0, 0, 0, 8)
            };
            grid.DefaultCellStyle.Padding = new Padding(6, 5, 6, 5);
            grid.ColumnHeadersDefaultCellStyle.Padding = new Padding(6, 6, 6, 6);
            grid.ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.AutoSize;
            grid.GridColor = SystemColors.ControlLight;
            grid.AlternatingRowsDefaultCellStyle.BackColor = SystemColors.Control;
            grid.EnableHeadersVisualStyles = false;
            grid.ColumnHeadersDefaultCellStyle.BackColor = SystemColors.Control;
            grid.ColumnHeadersDefaultCellStyle.ForeColor = SystemColors.ControlText;
            grid.DefaultCellStyle.SelectionForeColor = SystemColors.Window.GetBrightness() < 0.5f
                ? SystemColors.ControlText : SystemColors.HighlightText;
            grid.ColumnHeadersDefaultCellStyle.SelectionBackColor = SystemColors.Control;
            grid.ColumnHeadersDefaultCellStyle.SelectionForeColor = SystemColors.ControlText;
            grid.RowTemplate.MinimumHeight = 32;
            technical.Margin = new Padding(10, 7, 3, 3);
            views.Items.AddRange(new object[] { "Weapons & gadgets", "Upgrade nodes", "Skill points", "Armor", "Skins", "Special bolts", "Blueprints", "Bonuses & cheats", "Objects & equipment", "World progress", "Quick select", "Player summary", "Hero XP reference", "Saved locations", "Save layout", "Prefix words (technical)", "Files & metadata", "Hex bytes (technical)" });
            views.Items.Insert(views.Items.IndexOf("Save layout"), "Stored state blocks");
            views.Items.Insert(views.Items.IndexOf("Skill points") + 1, "Dance progress");
            views.Items.Insert(views.Items.IndexOf("Player summary") + 1, "Game settings");
            views.Items.Insert(views.Items.IndexOf("World progress") + 1, "Arena challenges");
            views.Items.Insert(views.Items.IndexOf("Arena challenges") + 1, "Reset-event counters");
            views.Items.Insert(views.Items.IndexOf("World progress") + 1, "Global event flags");
            views.Items.Insert(views.Items.IndexOf("World progress") + 1, "Gameplay segments");
            views.Items.Insert(views.Items.IndexOf("World progress") + 1, "World object flags");
            views.Sorted = true;
            todViews = views.Items.Cast<string>().ToArray();
            toolbar.Controls.Add(views);
            toolbar.Controls.Add(upgradeWeapon);
            toolbar.Controls.Add(hexOffset);
            toolbar.Controls.Add(technical);
            var split = new SplitContainer
            {
                Name = "InspectionSplit", Dock = DockStyle.Fill, Orientation = Orientation.Horizontal,
                FixedPanel = FixedPanel.Panel2, Size = new Size(1000, 600),
                SplitterWidth = 6, SplitterDistance = 444, Panel1MinSize = 120, Panel2MinSize = 90
            };
            split.Panel1.Controls.Add(grid);
            split.Panel1.Controls.Add(hex);
            split.Panel2.Padding = new Padding(0, 6, 0, 0);
            split.Panel2.Controls.Add(details);
            Controls.Add(split);
            Controls.Add(toolbar);
            tip.SetToolTip(views, "Read-only views of the current plaintext session baseline. Resize the window for more space.");
            tip.SetToolTip(hexOffset, "Save data file offset in hexadecimal; 256 bytes are displayed.");
            tip.SetToolTip(upgradeWeapon, "Show upgrades for one weapon, or all weapons. Select a row for technical details.");
            tip.SetToolTip(technical, "Show original research columns and exact values, including unknown fields. Inspection is always read-only.");
            tip.SetToolTip(grid, "Double-click a weapon to view its native binding, shipped levels, upgrades and vendor grid on the Research tab.");
            grid.CellDoubleClick += (_, args) =>
            {
                if (views.Text == "Weapons & gadgets" && HasTodSnapshot && args.RowIndex >= 0 &&
                    grid.Rows[args.RowIndex].HeaderCell.Tag is int id) WeaponReferenceRequested?.Invoke(id);
            };
            grid.SelectionChanged += (_, _) => details.Text = grid.CurrentRow?.Tag as string ?? SnapshotMessage ?? "Open a save folder to inspect it. Bundled references are on the Research tab.";
            grid.FontChanged += (_, _) => FitColumns();
            grid.SizeChanged += (_, _) =>
            {
                if (!technical.Checked && InspectionPresentation.ViewKey(views.Text) is "Save regions" or "Files & headers") FitColumns();
            };
            views.SelectedIndexChanged += (_, _) => RefreshView();
            technical.CheckedChanged += (_, _) => RefreshView();
            upgradeWeapon.SelectedIndexChanged += (_, _) => { if (!updatingWeaponFilter) RefreshView(); };
            hexOffset.ValueChanged += (_, _) => UpdateHexView();
            views.SelectedItem = "Weapons & gadgets";
        }

        public void LoadSession(SaveSession session)
        {
            byte[] bytes = session.ReadInspectionData();
            snapshot = TodSaveInspection.Read(bytes, session.Metadata.Region);
            rc1 = Rc1SaveInspection.Supports(session.Metadata.Region) ? Rc1SaveInspection.Read(bytes, session.Metadata.Region) : null;
            tip.SetToolTip(grid, rc1 != null
                ? "Select a row for stored values, offsets and mapping limitations. These RC1 views are read-only."
                : "Double-click a weapon to view its native binding, shipped levels, upgrades and vendor grid on the Research tab.");
            updatingWeaponFilter = true;
            try
            {
                string previous = upgradeWeapon.SelectedItem as string;
                upgradeWeapon.Items.Clear();
                upgradeWeapon.Items.Add("All weapons");
                if (HasTodSnapshot)
                    foreach (string weapon in snapshot.Table("Upgrade nodes").Rows.Select(row => row.Cells[0]).Distinct()
                        .Order(StringComparer.CurrentCultureIgnoreCase))
                        upgradeWeapon.Items.Add(weapon);
                upgradeWeapon.SelectedItem = previous != null && upgradeWeapon.Items.Contains(previous) ? previous : "All weapons";
            }
            finally { updatingWeaponFilter = false; }
            containers = SaveContainerInspection.Read(session.WorkingFolder, session.Profile.FileName, bytes);
            hexOffset.Value = 0;
            hexOffset.Maximum = Math.Max(0, (rc1?.Length ?? snapshot.Length) - 1);
            string previousView = views.SelectedItem as string;
            views.BeginUpdate();
            try
            {
                views.Items.Clear();
                views.Items.AddRange(rc1 != null
                    ? new object[] { "Player summary", "Weapons & gadgets", "Quick select", "Player records", "Save layout", "Files & metadata", "Hex bytes (technical)" }
                    : todViews.Cast<object>().ToArray());
                views.SelectedItem = previousView != null && views.Items.Contains(previousView)
                    ? previousView : rc1 != null ? "Player summary" : "Weapons & gadgets";
            }
            finally { views.EndUpdate(); }
            RefreshView();
        }

        private void RefreshView()
        {
            string view = InspectionPresentation.ViewKey(views.Text);
            bool showHex = view == "Hex bytes";
            bool showUpgrades = views.Text == "Upgrade nodes";
            upgradeWeapon.Visible = showUpgrades && HasTodSnapshot;
            grid.Visible = !showHex;
            hex.Visible = showHex;
            hexOffset.Visible = showHex && HasSnapshot;
            details.Text = SnapshotMessage ?? "Open a save folder to inspect it. Bundled references are on the Research tab.";
            if (showHex) { UpdateHexView(); return; }
            grid.Rows.Clear();
            grid.Columns.Clear();
            InspectionTable table = view == "Files & headers" ? containers : rc1 != null ? rc1.Table(view, technical.Checked) : snapshot?.Table(view);
            if (table == null) return;
            if (!technical.Checked && (rc1 == null || view == "Files & headers")) table = InspectionPresentation.Simplify(view, table);
            foreach (string column in table.Columns) grid.Columns.Add(column, column);
            foreach (var row in table.Rows)
            {
                if (showUpgrades && HasTodSnapshot && upgradeWeapon.Text != "All weapons" && row.Cells[0] != upgradeWeapon.Text) continue;
                int index = grid.Rows.Add(row.Cells);
                grid.Rows[index].Tag = row.Details;
                if (view == "Weapons & gadgets" && HasTodSnapshot)
                    grid.Rows[index].HeaderCell.Tag = snapshot.Inventory[index].Id;
            }
            FitColumns();
            if (grid.Rows.Count > 0)
            {
                grid.CurrentCell = grid.Rows[0].Cells[0];
                details.Text = grid.Rows[0].Tag as string;
            }
        }

        private void UpdateHexView()
        {
            hex.Text = !HasSnapshot ? details.Text : hexOffset.TryGetValue(out decimal offset)
                ? rc1 != null ? rc1.HexBytes((int)offset) : snapshot.HexBytes((int)offset) : hexOffset.ValidationMessage;
        }

        private void FitColumns()
        {
            // Measure every loaded row, including off-screen gadgets and unusual
            // float values. Fill expands the columns when the window grows;
            // minimum widths keep key data readable in the compact window.
            int padding = TextRenderer.MeasureText("00", grid.Font).Width;
            foreach (DataGridViewColumn column in grid.Columns)
            {
                int width = TextRenderer.MeasureText(column.HeaderText, grid.Font, Size.Empty,
                    TextFormatFlags.SingleLine | TextFormatFlags.NoPrefix).Width + padding;
                foreach (DataGridViewRow row in grid.Rows)
                    width = Math.Max(width, TextRenderer.MeasureText(row.Cells[column.Index].Value?.ToString() ?? string.Empty,
                        grid.Font, Size.Empty, TextFormatFlags.SingleLine | TextFormatFlags.NoPrefix).Width + padding);
                // Long prose/hash/tail columns wrap instead of demanding a width
                // larger than the screen. Their full values remain in Details.
                int maximum = TextRenderer.MeasureText(new string('M', 48), grid.Font).Width + padding;
                // Friendly descriptions use the remaining window width and wrap;
                // exact technical tables retain their original minimum widths.
                if (!technical.Checked && (column.Name == "Understanding" ||
                    InspectionPresentation.ViewKey(views.Text) == "Files & headers" && column.Name == "Value"))
                {
                    int occupied = grid.Columns.Cast<DataGridViewColumn>().Take(column.Index).Sum(previous => previous.MinimumWidth);
                    maximum = Math.Max(80, grid.ClientSize.Width - SystemInformation.VerticalScrollBarWidth - 4 - occupied);
                }
                column.MinimumWidth = Math.Max(40, Math.Min(width, maximum));
                column.FillWeight = column.MinimumWidth;
                column.DefaultCellStyle.WrapMode = width > maximum ? DataGridViewTriState.True : DataGridViewTriState.False;
            }
            grid.AutoSizeRowsMode = DataGridViewAutoSizeRowsMode.AllCells;
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing) tip.Dispose();
            base.Dispose(disposing);
        }
    }
}
