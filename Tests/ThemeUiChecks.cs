using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static void ThemeUiChecks(string root)
    {
        Check("Theme menu offers system, light and dark choices without editing saves", () =>
        {
            using var form = new MainForm();
            var view = form.MainMenuStrip.Items.OfType<ToolStripMenuItem>().Single(item => item.Text == "&View");
            var theme = (ToolStripMenuItem)view.DropDownItems[0];
            True(theme.Text.Contains("restart"), "Explain when the theme takes effect.");
            True(theme.DropDownItems.OfType<ToolStripMenuItem>().Select(item => item.Text)
                .SequenceEqual(new[] { "&System", "&Light", "&Dark" }), "All theme preferences must be available.");
            Equal(1, theme.DropDownItems.OfType<ToolStripMenuItem>().Count(item => item.Checked));
            True(!Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Theme setup must not stage save changes.");
            form.StartPosition = FormStartPosition.Manual;
            form.Location = new Point(-20000, -20000);
            form.ShowInTaskbar = false;
            form.Show();
            string mode = SystemColors.Window.GetBrightness() < 0.5f ? "dark" : "light";
            string artifacts = Path.GetFullPath("artifacts");
            Directory.CreateDirectory(artifacts);
            Capture(form, Path.Combine(artifacts, $"ui-theme-{mode}-disabled.png"));
            theme.DropDown.Size = theme.DropDown.GetPreferredSize(Size.Empty);
            theme.DropDown.PerformLayout();
            using (var image = new Bitmap(theme.DropDown.Width, theme.DropDown.Height))
            {
                theme.DropDown.DrawToBitmap(image, new Rectangle(Point.Empty, image.Size));
                image.Save(Path.Combine(artifacts, $"ui-theme-{mode}-menu.png"));
            }
        });
        Check("All tabs render with readable input and inspector colors in the selected theme", () =>
        {
            string folder = Fixture(root, "BCUS98127");
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), ResearchFixture());
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "backups"));
            using var form = new MainForm
            {
                StartPosition = FormStartPosition.Manual, Location = new Point(-20000, -20000),
                ShowInTaskbar = false, ClientSize = new Size(1120, 740)
            };
            typeof(MainForm).GetField("session", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(form, session);
            typeof(MainForm).GetMethod("ShowSession", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(form, null);
            typeof(MainForm).GetMethod("SetBusy", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(form, new object[] { false });
            form.Show();
            var grid = Descendants(form).OfType<DataGridView>().Single();
            Equal(SystemColors.Control, grid.AlternatingRowsDefaultCellStyle.BackColor);
            Equal(SystemColors.Control, grid.ColumnHeadersDefaultCellStyle.BackColor);
            True(System.Math.Abs(grid.DefaultCellStyle.SelectionForeColor.GetBrightness() -
                grid.DefaultCellStyle.SelectionBackColor.GetBrightness()) > 0.35f, "Selected inspector rows must remain readable.");
            var input = Field<NumericTextBox>(form, "BoltsTextBox");
            Equal(SystemColors.Window, input.BackColor);
            True(System.Math.Abs(input.ForeColor.GetBrightness() - input.BackColor.GetBrightness()) > 0.5f,
                "Numeric input must remain readable in the selected theme.");
            var tabs = Field<TabControl>(form, "TabControl");
            string artifacts = Path.GetFullPath("artifacts");
            Directory.CreateDirectory(artifacts);
            string mode = SystemColors.Window.GetBrightness() < 0.5f ? "dark" : "light";
            for (int index = 0; index < tabs.TabCount; index++)
            {
                tabs.SelectedIndex = index;
                Equal(SystemColors.Control, tabs.SelectedTab.BackColor);
                Capture(form, Path.Combine(artifacts, $"ui-theme-{mode}-{index}.png"));
            }
            using var artwork = new Bitmap(32, 32);
            using var artworkWindow = (Form)typeof(TodInventoryPreviewControl)
                .GetMethod("CreateArtworkWindow", BindingFlags.Instance | BindingFlags.NonPublic)
                .Invoke(Descendants(form).OfType<TodInventoryPreviewControl>().Single(),
                    new object[] { "Artwork theme preview", new System.Collections.Generic.Dictionary<string, Bitmap> { ["Save artwork"] = artwork } });
            artworkWindow.StartPosition = FormStartPosition.Manual;
            artworkWindow.Location = form.Location;
            artworkWindow.ShowInTaskbar = false;
            artworkWindow.Show();
            Equal(form.BackColor, artworkWindow.BackColor);
            using var preview = new Bitmap(artworkWindow.Width, artworkWindow.Height);
            artworkWindow.DrawToBitmap(preview, new Rectangle(Point.Empty, preview.Size));
            preview.Save(Path.Combine(artifacts, $"ui-theme-{mode}-artwork.png"));
        });
    }
}
