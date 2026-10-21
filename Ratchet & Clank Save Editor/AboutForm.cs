using System.Drawing;
using System.Windows.Forms;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed class AboutForm : Form
    {
        public AboutForm()
        {
            Text = "About " + AppInfo.ProductName;
            AutoScaleDimensions = new SizeF(96, 96);
            AutoScaleMode = AutoScaleMode.Dpi;
            Font = new Font("Segoe UI", 11);
            FormBorderStyle = FormBorderStyle.FixedDialog;
            StartPosition = FormStartPosition.CenterParent;
            ShowInTaskbar = false;
            MinimizeBox = MaximizeBox = false;
            AutoSize = true;
            AutoSizeMode = AutoSizeMode.GrowAndShrink;

            var content = new TableLayoutPanel
            {
                AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Dock = DockStyle.Fill, ColumnCount = 1, Padding = new Padding(24)
            };
            var heading = AddLabel(content, "AboutProduct", AppInfo.ProductName, 8);
            heading.Font = new Font(Font.FontFamily, 15, FontStyle.Bold);
            AddLabel(content, "AboutVersion", "Version " + AppInfo.Version, 16);
            AddLabel(content, "AboutDescription", "A Windows editor for PlayStation 3 Ratchet & Clank saves.", 20);
            AddLabel(content, "AboutCreditsHeading", "Credits", 8).Font = new Font(Font, FontStyle.Bold);
            AddLabel(content, "AboutCredits", "Created by primetime43 with help from Red_EyeX32.\nPS3 save tools by flatz.\nOriginally released in 2013.", 20);

            var footer = new FlowLayoutPanel
            {
                AutoSize = true, Dock = DockStyle.Fill, FlowDirection = FlowDirection.RightToLeft,
                Margin = Padding.Empty
            };
            var close = new Button
            {
                Name = "AboutClose", Text = "Close", AutoSize = true,
                Padding = new Padding(12, 4, 12, 4), Margin = Padding.Empty,
                DialogResult = DialogResult.OK
            };
            footer.Controls.Add(close);
            content.Controls.Add(footer);
            Controls.Add(content);
            AcceptButton = CancelButton = close;
        }

        private static Label AddLabel(TableLayoutPanel content, string name, string text, int bottomMargin)
        {
            var label = new Label
            {
                Name = name, Text = text, AutoSize = true, MaximumSize = new Size(480, 0),
                UseMnemonic = false, Margin = new Padding(0, 0, 0, bottomMargin)
            };
            content.Controls.Add(label);
            return label;
        }
    }
}
