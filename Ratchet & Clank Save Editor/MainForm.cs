using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Security;
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
        private bool loadingValues;
        private int selectedCharacter;
        private int[] pendingBolts;
        private TodSaveEditingControl mappedEditor;
        private bool HasInvalidNumericInput => !BoltsTextBox.IsValid ||
            (session?.Profile.RaritaniumOffset.HasValue == true && !RaritaniumTextBox.IsValid) ||
            mappedEditor?.HasInvalidInputs == true;
        private bool Dirty => session != null && (session.MetadataChanged ||
            HasInvalidNumericInput ||
            mappedEditor.HasChanges ||
            (pendingBolts != null && !pendingBolts.SequenceEqual(session.CharacterBolts)) ||
            (session.Profile.RaritaniumOffset.HasValue && RaritaniumTextBox.Value != session.Raritanium));

        public MainForm()
        {
            // Finish building all tabs before the first DPI/layout pass.
            SuspendLayout();
            InitializeComponent();
            InitializeReadableLayout();
            InitializeResearchViews();
            InitializeAppearance();
            ResumeLayout(true);
            SetBusy(false);
            UpdateTitle();
        }

        private void InitializeAppearance()
        {
            foreach (TabPage page in TabControl.TabPages)
            {
                page.UseVisualStyleBackColor = false;
                page.BackColor = SystemColors.Control;
            }
            var view = new ToolStripMenuItem("&View");
            var theme = new ToolStripMenuItem("&Theme (restart to apply)");
            foreach (var (label, mode) in new[]
            {
                ("&System", SystemColorMode.System),
                ("&Light", SystemColorMode.Classic),
                ("&Dark", SystemColorMode.Dark)
            })
            {
                var item = new ToolStripMenuItem(label) { Checked = AppTheme.Preference == mode };
                item.Click += (_, _) =>
                {
                    try
                    {
                        AppTheme.SavePreference(mode);
                        foreach (ToolStripMenuItem choice in theme.DropDownItems) choice.Checked = choice == item;
                        StatusLabel.Text = "Theme saved · Restart the editor to apply";
                    }
                    catch (Exception error) when (error is IOException or UnauthorizedAccessException or SecurityException)
                    {
                        MessageBox.Show(this, "Could not save the theme preference.\n\n" + error.Message,
                            "Theme", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    }
                };
                theme.DropDownItems.Add(item);
            }
            view.DropDownItems.Add(theme);
            MenuStrip.Items.Add(view);
        }

        private async void openFolderToolStripMenuItem_Click(object sender, EventArgs e) => await OpenFolder(false);
        private async void openDecryptedToolStripMenuItem_Click(object sender, EventArgs e) => await OpenFolder(true);

        private async Task OpenFolder(bool decrypted)
        {
            if (busy) return;
            if (Dirty && MessageBox.Show(this, "Discard unsaved edits and open another save?", "Unsaved changes",
                MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
            using var dialog = new FolderBrowserDialog
            {
                Description = "Select a Ratchet & Clank PS3 save folder",
                UseDescriptionForTitle = true,
                ShowNewFolderButton = false,
                SelectedPath = session?.Folder ?? string.Empty
            };
            if (dialog.ShowDialog(this) != DialogResult.OK) return;
            string selectedFolder = dialog.SelectedPath;
            await RunOperation("Backing up and opening save…", async () =>
            {
                var loaded = await Task.Run(() => SaveSession.Open(selectedFolder, tools, decrypted));
                session?.Dispose();
                session = loaded;
                ShowSession();
                StatusLabel.Text = $"{session.Profile.Name} · {(session.IsEncrypted ? "PS3 encrypted" : "Decrypted / RPCS3")}";
            });
        }

        private void ShowSession()
        {
            loadingValues = true;
            try
            {
                pendingBolts = session.CharacterBolts.ToArray();
                selectedCharacter = 0;
                CharacterComboBox.SelectedItem = SaveData.CharacterNames[selectedCharacter];
                CharacterComboBox.Visible = CharacterLabel.Visible = session.Profile.Layout == CurrencyLayout.Characters;
                AccountInfoGroupBox.Text = session.Profile.Name.Replace("&", "&&");
                AccountIDTextBox.Text = session.Metadata.AccountId;
                GameVersionTextBox.Text = session.Metadata.Region;
                GameSaveKeyTextBox.Text = session.Profile.Key;
                PlanetTextBox.Text = session.Metadata.Planet;
                saveInspector.LoadSession(session);
                inventoryPreview.LoadSession(session);
                mappedEditor.LoadSnapshot(session.ReadInspectionData(), session.Metadata.Region);
                BoltsTextBox.Maximum = session.Profile.MaximumBolts;
                BoltsTextBox.Value = session.Bolts;
                RaritaniumTextBox.Value = session.Raritanium;
                CasinoChipsLabel.Visible = RaritaniumTextBox.Visible = session.Profile.RaritaniumOffset.HasValue;
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
            }
            finally { loadingValues = false; }
            UpdateTitle();
        }

        private async void saveAllToolStripMenuItem_Click(object sender, EventArgs e) => await SaveChanges();

        private async Task<bool> SaveChanges()
        {
            if (session == null || busy) return false;
            if (!ValidateNumericInputs()) return false;
            pendingBolts[selectedCharacter] = decimal.ToInt32(BoltsTextBox.Value);
            int[] bolts = pendingBolts.ToArray();
            int raritanium = session.Profile.RaritaniumOffset.HasValue ? decimal.ToInt32(RaritaniumTextBox.Value) : 0;
            var mappedEdits = mappedEditor.PendingEdits;
            return await RunOperation("Verifying and saving changes…", async () =>
            {
                string backup = await Task.Run(() => session.Save(bolts, raritanium, mappedEdits: mappedEdits));
                pendingBolts = session.CharacterBolts.ToArray();
                saveInspector.LoadSession(session);
                inventoryPreview.LoadSession(session);
                mappedEditor.LoadSnapshot(session.ReadInspectionData(), session.Metadata.Region);
                UpdateTitle();
                StatusLabel.Text = "Saved successfully · Original backed up";
                string format = session.IsEncrypted ? "encrypted PS3" : "decrypted/RPCS3";
                MessageBox.Show(this, $"Your changes have been saved in {format} format.\n\nOriginal backup:\n{backup}",
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
            openDecryptedToolStripMenuItem.Enabled = !value;
            UpdateAccountIDButton.Enabled = session?.IsEncrypted == true && !value;
            BackupButton.Enabled = session != null && !value;
            RefreshSaveActions();
            TabControl.Enabled = !value;
            GameSaveInformationTabPage.Enabled = GameSaveEditingTabPage.Enabled = session != null && !value;
            inspectionTab.Enabled = !value;
            researchTab.Enabled = !value;
            SaveImageButton.Enabled = ViewImageButton.Enabled = SaveGameImagePictureBox.Image != null;
            OpenBackupButton.Enabled = session?.LastBackup != null;
        }

        private void ValuesChanged(object sender, EventArgs e)
        {
            if (busy || loadingValues) return;
            if (pendingBolts != null && BoltsTextBox.TryGetValue(out decimal bolts))
                pendingBolts[selectedCharacter] = decimal.ToInt32(bolts);
            UpdateTitle();
            if (HasInvalidNumericInput) StatusLabel.Text = "Invalid number · " + NumericValidationMessage;
            else if (Dirty) StatusLabel.Text = "Unsaved changes · Save to apply your edits";
            else if (session != null) StatusLabel.Text = "No pending changes";
        }

        private void CharacterChanged(object sender, EventArgs e)
        {
            if (loadingValues || busy || session == null || CharacterComboBox.SelectedIndex < 0) return;
            if (!BoltsTextBox.IsValid)
            {
                loadingValues = true;
                try { CharacterComboBox.SelectedItem = SaveData.CharacterNames[selectedCharacter]; }
                finally { loadingValues = false; }
                ValidateNumericInputs();
                return;
            }
            pendingBolts[selectedCharacter] = decimal.ToInt32(BoltsTextBox.Value);
            selectedCharacter = Array.IndexOf(SaveData.CharacterNames, (string)CharacterComboBox.SelectedItem);
            loadingValues = true;
            try { BoltsTextBox.Value = pendingBolts[selectedCharacter]; }
            finally { loadingValues = false; }
            UpdateTitle();
        }

        private void RefreshSaveActions()
        {
            saveAllToolStripMenuItem.Enabled = session != null && Dirty && !busy && !HasInvalidNumericInput;
        }

        private string NumericValidationMessage => !BoltsTextBox.IsValid ? BoltsTextBox.ValidationMessage :
            session?.Profile.RaritaniumOffset.HasValue == true && !RaritaniumTextBox.IsValid
                ? RaritaniumTextBox.ValidationMessage : mappedEditor.ValidationMessage;

        private bool ValidateNumericInputs()
        {
            if (!HasInvalidNumericInput) return true;
            StatusLabel.Text = "Invalid number · " + NumericValidationMessage;
            if (!BoltsTextBox.IsValid) { BoltsTextBox.Focus(); BoltsTextBox.SelectAll(); }
            else if (session.Profile.RaritaniumOffset.HasValue && !RaritaniumTextBox.IsValid)
            { RaritaniumTextBox.Focus(); RaritaniumTextBox.SelectAll(); }
            else mappedEditor.ValidateInputs();
            return false;
        }

        private void UpdateTitle()
        {
            Text = WindowTitle + (session == null ? string.Empty : " — " + session.Profile.Name) +
                (Dirty ? " • Unsaved changes" : string.Empty);
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
                saveInspector.LoadSession(session);
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
                saveInspector.LoadSession(session);
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
