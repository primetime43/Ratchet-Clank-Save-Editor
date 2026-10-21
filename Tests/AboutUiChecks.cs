using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static void AboutUiChecks()
    {
        var assembly = typeof(MainForm).Assembly;
        string version = assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>().InformationalVersion.Split('+')[0];
        string product = assembly.GetCustomAttribute<AssemblyProductAttribute>().Product;
        Check("Window title, assembly filename and file metadata share the complete version", () =>
        {
            using var form = new MainForm();
            Equal($"{product} v{version}", form.Text);
            Equal(form.Text + ".dll", Path.GetFileName(assembly.Location));
            Equal(version, FileVersionInfo.GetVersionInfo(assembly.Location).ProductVersion.Split('+')[0]);
            Equal(assembly.GetName().Version.ToString(), FileVersionInfo.GetVersionInfo(assembly.Location).FileVersion);
            var aboutMenu = Field<ToolStripMenuItem>(form, "aboutToolStripMenuItem");
            Equal("&About", aboutMenu.Text);
            True(aboutMenu.Enabled, "About should be available before opening a save.");
        });
        Check("About shows the version and credits and renders in the selected theme", () =>
        {
            using var about = new AboutForm
            {
                StartPosition = FormStartPosition.Manual, Location = new Point(-20000, -20000)
            };
            Equal("About " + product, about.Text);
            Equal(product, about.Controls.Find("AboutProduct", true).Single().Text);
            Equal("Version " + version, about.Controls.Find("AboutVersion", true).Single().Text);
            string credits = about.Controls.Find("AboutCredits", true).Single().Text;
            foreach (string contributor in new[] { "primetime43", "Red_EyeX32", "flatz" })
                True(credits.Contains(contributor), "Keep the original contributor credits.");
            Equal(about.AcceptButton, about.CancelButton);
            Equal(DialogResult.OK, ((Button)about.AcceptButton).DialogResult);
            // Render directly offscreen; do not open or automate modal/native dialogs.
            about.Show();
            foreach (var label in Descendants(about).OfType<Label>())
            {
                True(label.Parent.ClientRectangle.Contains(label.Bounds), "About text must fit its layout.");
                True(label.Height >= label.GetPreferredSize(new Size(label.Width, 0)).Height, "About text must not be clipped.");
            }
            string mode = SystemColors.Window.GetBrightness() < 0.5f ? "dark" : "light";
            Directory.CreateDirectory("artifacts");
            using var image = new Bitmap(about.Width, about.Height);
            about.DrawToBitmap(image, new Rectangle(Point.Empty, image.Size));
            image.Save(Path.GetFullPath($"artifacts/ui-about-{mode}.png"));
        });
    }
}
