using System;
using System.Drawing;
using System.Windows.Forms;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public partial class MainForm
    {
        protected override void OnLoad(EventArgs e)
        {
            base.OnLoad(e);
            if (StartPosition != FormStartPosition.CenterScreen || WindowState != FormWindowState.Normal) return;
            // A high-DPI laptop may have less usable space than the nominal
            // default. Keep the initial window and its minimum on the monitor.
            Rectangle area = Screen.FromControl(this).WorkingArea;
            var available = new Size(Math.Max(1, area.Width - 24), Math.Max(1, area.Height - 24));
            MinimumSize = new Size(Math.Min(MinimumSize.Width, available.Width), Math.Min(MinimumSize.Height, available.Height));
            Size = new Size(Math.Min(Width, available.Width), Math.Min(Height, available.Height));
            Location = new Point(area.Left + (area.Width - Width) / 2, area.Top + (area.Height - Height) / 2);
        }

        private void InitializeReadableLayout()
        {
            SuspendLayout();
            TabControl.Padding = new Point(14, 8);
            GameSaveInformationTabPage.AutoScroll = true;
            GameSaveEditingTabPage.AutoScroll = true;
            GameSaveInformationTabPage.Padding = GameSaveEditingTabPage.Padding = new Padding(16);

            // Reuse the original controls/events inside layouts that grow with
            // the window and DPI instead of relying on fixed pixel coordinates.
            var information = LayoutTable("SaveInformationLayout", 2);
            information.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 240));
            information.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            information.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            GameSaveInformationTabPage.Controls.Clear();
            information.Controls.Add(ImageGroupBox, 0, 0);
            information.Controls.Add(AccountInfoGroupBox, 1, 0);
            GameSaveInformationTabPage.Controls.Add(information);

            ImageGroupBox.Text = "Save artwork";
            PrepareGroup(ImageGroupBox);
            ImageGroupBox.Margin = new Padding(0, 0, 16, 0);
            var artwork = LayoutTable("SaveArtworkLayout", 1, 3);
            artwork.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            SaveGameImagePictureBox.Dock = DockStyle.Fill;
            SaveGameImagePictureBox.MinimumSize = new Size(160, 150);
            SaveGameImagePictureBox.Margin = new Padding(0, 6, 0, 12);
            artwork.Controls.Add(SaveGameImagePictureBox, 0, 0);
            PrepareButton(SaveImageButton);
            PrepareButton(ViewImageButton);
            artwork.Controls.Add(SaveImageButton, 0, 1);
            artwork.Controls.Add(ViewImageButton, 0, 2);
            ImageGroupBox.Controls.Add(artwork);

            PrepareGroup(AccountInfoGroupBox);
            AccountInfoGroupBox.Text = "Save information";
            var fields = LayoutTable("SaveMetadataLayout", 2, 4);
            fields.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 150));
            fields.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            AddField(fields, 0, AccountIDLabel, AccountIDTextBox);
            AddField(fields, 1, GameSaveKeyLabel, GameSaveKeyTextBox);
            var region = LayoutTable("SaveRegionLayout", 2);
            region.Margin = Padding.Empty;
            region.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            region.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 170));
            PrepareInput(GameVersionTextBox);
            PrepareButton(VerifyVersionButton);
            region.Controls.Add(GameVersionTextBox, 0, 0);
            region.Controls.Add(VerifyVersionButton, 1, 0);
            GameVersionLabel.Text = "Region / title ID:";
            AddField(fields, 2, GameVersionLabel, region);
            var actions = LayoutTable("SaveActionsLayout", 2, 2);
            actions.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
            actions.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
            Button[] buttons = { UpdateAccountIDButton, PatchPARAMButton, BackupButton, OpenBackupButton };
            for (int i = 0; i < buttons.Length; i++)
            {
                PrepareButton(buttons[i]);
                actions.Controls.Add(buttons[i], i % 2, i / 2);
            }
            fields.Controls.Add(actions, 0, 3);
            fields.SetColumnSpan(actions, 2);
            AccountInfoGroupBox.Controls.Add(fields);

            var editing = LayoutTable("SaveEditingLayout", 1, 2);
            editing.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            GameSaveEditingTabPage.Controls.Clear();
            PrepareGroup(groupBox3);
            var player = LayoutTable("PlayerDataLayout", 2, 4);
            player.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 180));
            player.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            AddField(player, 0, label1, PlanetTextBox);
            AddField(player, 1, MoneyLabel, MoneyNumericUpDown);
            AddField(player, 2, CasinoChipsLabel, CasinoChipsNumericUpDown);
            AddField(player, 3, CharacterLabel, CharacterComboBox);
            MoneyNumericUpDown.ThousandsSeparator = CasinoChipsNumericUpDown.ThousandsSeparator = true;
            groupBox3.Controls.Add(player);
            editing.Controls.Add(groupBox3, 0, 0);
            editing.Controls.Add(new Label
            {
                Name = "SaveEditingHint", AutoSize = true, Dock = DockStyle.Fill,
                Margin = new Padding(4, 16, 4, 0),
                Text = "Use File → Save All (Ctrl+S) to apply edits. A full original backup is created automatically."
            }, 0, 1);
            GameSaveEditingTabPage.Controls.Add(editing);
            ResumeLayout(true);
        }

        private static TableLayoutPanel LayoutTable(string name, int columns, int rows = 1)
        {
            var table = new TableLayoutPanel
            {
                Name = name, Dock = DockStyle.Top, AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink, ColumnCount = columns, RowCount = rows,
                Size = new Size(200, 0), Margin = Padding.Empty, Padding = Padding.Empty
            };
            for (int row = 0; row < rows; row++) table.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            return table;
        }

        private static void PrepareGroup(GroupBox group)
        {
            group.Controls.Clear();
            group.Dock = DockStyle.Fill;
            group.AutoSize = true;
            group.AutoSizeMode = AutoSizeMode.GrowAndShrink;
            group.Padding = new Padding(12);
            group.Margin = Padding.Empty;
        }

        private static void PrepareButton(Button button)
        {
            button.Dock = DockStyle.Fill;
            button.AutoSize = true;
            button.MinimumSize = new Size(0, 38);
            button.Height = 38;
            button.Margin = new Padding(4, 6, 4, 6);
            button.Padding = new Padding(8, 3, 8, 3);
        }

        private static void PrepareInput(Control input)
        {
            input.Dock = DockStyle.Fill;
            input.Margin = new Padding(4, 8, 4, 8);
        }

        private static void AddField(TableLayoutPanel table, int row, Label label, Control input)
        {
            label.AutoSize = true;
            label.Dock = DockStyle.Fill;
            label.TextAlign = ContentAlignment.MiddleLeft;
            label.Margin = new Padding(4, 8, 8, 8);
            PrepareInput(input);
            table.Controls.Add(label, 0, row);
            table.Controls.Add(input, 1, row);
        }
    }
}
