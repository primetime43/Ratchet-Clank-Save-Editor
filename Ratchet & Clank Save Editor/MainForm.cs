using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public partial class MainForm : Form
    {
        private static readonly string WindowTitle = "Ratchet & Clank Save Editor v" +
            typeof(MainForm).Assembly.GetName().Version.ToString(3);
        private readonly Encryption tools = new();
        private SaveSession session;
        private bool busy;
        private bool allowClose;
        private bool Dirty => session != null && (session.MetadataChanged ||
            MoneyNumericUpDown.Value != session.Bolts ||
            (session.Profile.RaritaniumOffset.HasValue && CasinoChipsNumericUpDown.Value != session.Raritanium));

        public MainForm()
        {
            InitializeComponent();
            SetBusy(false);
            UpdateTitle();
        }

        private async void openFolderToolStripMenuItem_Click(object sender, EventArgs e)
        {
            if (busy) return;
            if (Dirty && MessageBox.Show(this, "Discard unsaved edits and open another save?", "Unsaved changes",
                MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
            using var dialog = new FolderBrowserDialog
            {
                Description = "Select a Ratchet & Clank PS3 save folder",
                UseDescriptionForTitle = true, ShowNewFolderButton = false,
                SelectedPath = session?.Folder ?? string.Empty
            };
            if (dialog.ShowDialog(this) != DialogResult.OK) return;
            string selectedFolder = dialog.SelectedPath;
            await RunOperation("Opening and decrypting save…", async () =>
            {
                var loaded = await Task.Run(() => SaveSession.Open(selectedFolder, tools));
                session?.Dispose();
                session = loaded;
                ShowSession();
                StatusLabel.Text = $"Loaded {session.Profile.Name} · Original save preserved";
            });
        }

        private void ShowSession()
        {
            AccountIDTextBox.Text = session.Metadata.AccountId;
            GameVersionTextBox.Text = session.Metadata.Region;
            GameSaveKeyTextBox.Text = session.Profile.Key;
            PlanetTextBox.Text = session.Metadata.Planet;
            MoneyNumericUpDown.Value = session.Bolts;
            CasinoChipsNumericUpDown.Value = session.Raritanium;
            CasinoChipsLabel.Visible = CasinoChipsNumericUpDown.Visible = session.Profile.RaritaniumOffset.HasValue;
            SaveGameImagePictureBox.Image?.Dispose();
            SaveGameImagePictureBox.Image = null;
            string icon = Path.Combine(session.WorkingFolder, "ICON0.PNG");
            if (File.Exists(icon))
            {
                try
                {
                    // Clone into memory so no file remains locked while the save is open.
                    using var image = Image.FromFile(icon);
                    SaveGameImagePictureBox.Image = new Bitmap(image);
                }
                catch (ArgumentException) { }
                catch (IOException) { }
                catch (OutOfMemoryException) { } // GDI+ uses this for invalid image data as well.
            }
            UpdateTitle();
        }

        private async void saveAllToolStripMenuItem_Click(object sender, EventArgs e) => await SaveChanges();

        private async Task<bool> SaveChanges()
        {
            if (session == null || busy) return false;
            ValidateChildren();
            int bolts = decimal.ToInt32(MoneyNumericUpDown.Value);
            int raritanium = decimal.ToInt32(CasinoChipsNumericUpDown.Value);
            return await RunOperation("Encrypting and saving changes…", async () =>
            {
                string backup = await Task.Run(() => session.Save(bolts, raritanium));
                UpdateTitle();
                StatusLabel.Text = "Saved successfully · Original backed up";
                MessageBox.Show(this, $"Your save has been encrypted and saved.\n\nOriginal backup:\n{backup}",
                    "Save complete", MessageBoxButtons.OK, MessageBoxIcon.Information);
            });
        }

        private async Task<bool> RunOperation(string status, Func<Task> action)
        {
            if (busy) return false;
            SetBusy(true);
            StatusLabel.Text = status;
            try { await action(); return true; }
            catch (Exception error)
            {
                StatusLabel.Text = "Operation failed · " + error.Message.Split('\n')[0];
                MessageBox.Show(this, error.Message, "Save editor", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return false;
            }
            finally { SetBusy(false); }
        }

        private void SetBusy(bool value)
        {
            busy = value;
            UseWaitCursor = value;
            openFolderToolStripMenuItem.Enabled = !value;
            BackupButton.Enabled = session != null && !value;
            RefreshSaveActions();
            TabControl.Enabled = session != null && !value;
            SaveImageButton.Enabled = ViewImageButton.Enabled = SaveGameImagePictureBox.Image != null;
            OpenBackupButton.Enabled = session?.LastBackup != null;
        }

        private void ValuesChanged(object sender, EventArgs e)
        {
            if (busy) return;
            UpdateTitle();
            if (Dirty) StatusLabel.Text = "Unsaved changes · Save to apply your edits";
            else if (session != null) StatusLabel.Text = "No pending changes";
        }

        private void RefreshSaveActions()
        {
            saveAllToolStripMenuItem.Enabled = session != null && Dirty && !busy;
        }

        private void UpdateTitle()
        {
            Text = WindowTitle + (Dirty ? " • Unsaved changes" : string.Empty);
            RefreshSaveActions();
        }

        private async void MainForm_FormClosing(object sender, FormClosingEventArgs e)
        {
            if (allowClose) return;
            if (busy) { e.Cancel = true; return; }
            if (!Dirty) return;
            e.Cancel = true;
            var choice = MessageBox.Show(this, "Save your changes before closing?", "Unsaved changes",
                MessageBoxButtons.YesNoCancel, MessageBoxIcon.Question);
            if (choice == DialogResult.Cancel) return;
            if (choice == DialogResult.Yes && !await SaveChanges()) return;
            allowClose = true;
            BeginInvoke(new Action(Close));
        }

        private async void BackUpButton_Click(object sender, EventArgs e)
        {
            if (session == null || busy) return;
            await RunOperation("Backing up original save…", async () =>
            {
                string backup = await Task.Run(() => session.BackUp());
                StatusLabel.Text = "Complete original save backed up";
                MessageBox.Show(this, $"Backup created:\n{backup}", "Backup complete", MessageBoxButtons.OK, MessageBoxIcon.Information);
            });
        }

        private async void PatchPARAMButton_Click(object sender, EventArgs e)
        {
            if (session == null || busy) return;
            await RunOperation("Removing copy protection…", async () =>
            {
                await Task.Run(session.PatchMetadata);
                AccountIDTextBox.Text = session.Metadata.AccountId;
                UpdateTitle();
                StatusLabel.Text = "Copy protection removed from working copy · Save to apply";
            });
        }

        private async void UpdateIntegrityButton_Click(object sender, EventArgs e)
        {
            if (session == null || busy) return;
            await RunOperation("Updating save integrity…", async () =>
            {
                await Task.Run(session.UpdateIntegrity);
                UpdateTitle();
                StatusLabel.Text = "Integrity updated in working copy · Save to apply";
            });
        }

        private void SaveImageButton_Click(object sender, EventArgs e)
        {
            if (session == null || SaveGameImagePictureBox.Image == null) return;
            using var dialog = new SaveFileDialog { FileName = "ICON0.png", Filter = "PNG image (*.png)|*.png", DefaultExt = "png" };
            if (dialog.ShowDialog(this) != DialogResult.OK) return;
            try
            {
                SaveGameImagePictureBox.Image.Save(dialog.FileName, System.Drawing.Imaging.ImageFormat.Png);
                StatusLabel.Text = "Artwork exported";
            }
            catch (Exception error) { MessageBox.Show(this, error.Message, "Export failed", MessageBoxButtons.OK, MessageBoxIcon.Error); }
        }

        private void ViewImageButton_Click(object sender, EventArgs e)
        {
            if (session == null || SaveGameImagePictureBox.Image == null) return;
            OpenWithShell(Path.Combine(session.WorkingFolder, "ICON0.PNG"));
        }

        private void OpenBackupButton_Click(object sender, EventArgs e)
        {
            if (session?.LastBackup != null) OpenWithShell(session.LastBackup);
        }

        private void VerifyVersionButton_Click(object sender, EventArgs e)
        {
            if (session == null || busy) return;
            try
            {
                var metadata = SfoMetadata.Read(Path.Combine(session.Folder, "PARAM.SFO"));
                if (!string.Equals(metadata.Region, session.Metadata.Region, StringComparison.OrdinalIgnoreCase))
                    throw new IOException("The original save's region changed. Please open the folder again.");
                GameVersionTextBox.Text = metadata.Region;
                StatusLabel.Text = "Verified " + metadata.Region;
                MessageBox.Show(this, $"{session.Profile.Name}\nGame region: {metadata.Region}",
                    "Game version", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception error)
            {
                MessageBox.Show(this, error.Message, "Verification failed", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void OpenWithShell(string path)
        {
            try { Process.Start(new ProcessStartInfo(path) { UseShellExecute = true }); }
            catch (Exception error) { MessageBox.Show(this, error.Message, "Could not open file", MessageBoxButtons.OK, MessageBoxIcon.Error); }
        }

        private void creditsToolStripMenuItem_Click(object sender, EventArgs e) => MessageBox.Show(this,
            "Ratchet & Clank Save Editor\n\nCreated by primetime43 with help from Red_EyeX32.\nPS3 save tools by flatz.",
            "Credits", MessageBoxButtons.OK, MessageBoxIcon.Information);
    }
}
