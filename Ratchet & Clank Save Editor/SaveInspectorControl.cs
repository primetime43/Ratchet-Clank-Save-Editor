using System;
using System.Drawing;
using System.IO;
using System.Windows.Forms;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed class SaveInspectorControl : UserControl
    {
        private readonly ComboBox views = new() { Name = "InspectionView", DropDownStyle = ComboBoxStyle.DropDownList, Width = 195 };
        private readonly NumericUpDown hexOffset = new() { Name = "HexOffset", Hexadecimal = true, Width = 100, Visible = false };
        private readonly DataGridView grid = new()
        {
            Name = "InspectionGrid", Dock = DockStyle.Fill, ReadOnly = true, AllowUserToAddRows = false,
            AllowUserToDeleteRows = false, AllowUserToOrderColumns = true, AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill,
            MultiSelect = false, SelectionMode = DataGridViewSelectionMode.FullRowSelect, RowHeadersVisible = false,
            BackgroundColor = SystemColors.Window, BorderStyle = BorderStyle.FixedSingle
        };
        private readonly TextBox details = new() { Name = "InspectionDetails", Dock = DockStyle.Bottom, Height = 52, Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical };
        private readonly TextBox hex = new() { Name = "HexBytes", Dock = DockStyle.Fill, Multiline = true, ReadOnly = true, WordWrap = false, ScrollBars = ScrollBars.Both, Visible = false };
        private readonly ToolTip tip = new();
        private TodSaveInspection snapshot;
        private InspectionTable containers;
        public bool HasSnapshot => snapshot?.Available == true;
        public event Action<int> WeaponReferenceRequested;

        public SaveInspectorControl()
        {
            Dock = DockStyle.Fill;
            var toolbar = new FlowLayoutPanel { Dock = DockStyle.Top, Height = 29, WrapContents = false };
            views.Items.AddRange(new object[] { "Weapons & gadgets", "Upgrade nodes", "Counters & nearby fields", "Gameplay records", "Save regions", "Prefix words", "Files & headers", "Hex bytes" });
            toolbar.Controls.Add(views);
            toolbar.Controls.Add(hexOffset);
            Controls.Add(grid);
            Controls.Add(hex);
            Controls.Add(details);
            Controls.Add(toolbar);
            tip.SetToolTip(views, "Read-only views of the current plaintext session baseline. Resize the window for more space.");
            tip.SetToolTip(hexOffset, "GAME.SAV file offset in hexadecimal; 256 bytes are displayed.");
            tip.SetToolTip(grid, "Double-click a weapon to view its native binding, shipped levels, upgrades and vendor grid on the Research tab.");
            grid.CellDoubleClick += (_, args) =>
            {
                if (views.Text == "Weapons & gadgets" && HasSnapshot && args.RowIndex >= 0 &&
                    int.TryParse(grid.Rows[args.RowIndex].Cells[0].Value?.ToString(), out int id)) WeaponReferenceRequested?.Invoke(id);
            };
            grid.SelectionChanged += (_, _) => details.Text = grid.CurrentRow?.Tag as string ?? snapshot?.Message ?? "Open a save folder to inspect it. Bundled references are on the Research tab.";
            grid.FontChanged += (_, _) => FitColumns();
            views.SelectedIndexChanged += (_, _) => RefreshView();
            hexOffset.ValueChanged += (_, _) => { if (HasSnapshot) hex.Text = snapshot.HexBytes((int)hexOffset.Value); };
            views.SelectedIndex = 0;
        }

        public void LoadSession(SaveSession session)
        {
            byte[] bytes = session.ReadInspectionData();
            snapshot = TodSaveInspection.Read(bytes, session.Metadata.Region);
            containers = SaveContainerInspection.Read(session.WorkingFolder, session.Profile.FileName, bytes);
            hexOffset.Value = 0;
            hexOffset.Maximum = Math.Max(0, snapshot.Length - 1);
            RefreshView();
        }

        private void RefreshView()
        {
            bool showHex = views.Text == "Hex bytes";
            grid.Visible = !showHex;
            hex.Visible = showHex;
            hexOffset.Visible = showHex && HasSnapshot;
            details.Text = snapshot?.Message ?? "Open a save folder to inspect it. Bundled references are on the Research tab.";
            if (showHex) { hex.Text = snapshot?.HexBytes((int)hexOffset.Value) ?? details.Text; return; }
            grid.Rows.Clear();
            grid.Columns.Clear();
            InspectionTable table = views.Text == "Files & headers" ? containers : snapshot?.Table(views.Text);
            if (table == null) return;
            foreach (string column in table.Columns) grid.Columns.Add(column, column);
            foreach (var row in table.Rows)
            {
                int index = grid.Rows.Add(row.Cells);
                grid.Rows[index].Tag = row.Details;
            }
            FitColumns();
            if (grid.Rows.Count > 0)
            {
                grid.CurrentCell = grid.Rows[0].Cells[0];
                details.Text = grid.Rows[0].Tag as string;
            }
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
