using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // Saved baseline only: no staging, asset execution, game writes or live RAM.
    public sealed class TodInventoryPreviewControl : UserControl
    {
        private readonly Label status = new() { Name = "InventoryPreviewStatus", AutoSize = true, Dock = DockStyle.Fill };
        private readonly CheckBox ownedOnly = new() { Name = "InventoryOwnedOnly", Text = "Owned only", Checked = true, AutoSize = true };
        private readonly TextBox search = new() { Name = "InventorySearch", Width = 200, PlaceholderText = "Find an item…" };
        private readonly Button import = new() { Name = "InventoryImportIcons", Text = "Load game icons…", AutoSize = true };
        private readonly Button gallery = new() { Name = "InventoryHudGallery", Text = "Game UI artwork…", AutoSize = true, Enabled = false };
        private readonly Button artwork = new() { Name = "InventorySaveArtwork", Text = "Save artwork…", AutoSize = true, Enabled = false };
        private readonly FlowLayoutPanel cards = new() { Name = "InventoryCards", Dock = DockStyle.Fill, AutoScroll = true, WrapContents = true };
        private readonly TextBox details = new() { Name = "InventoryItemDetails", Dock = DockStyle.Fill, Multiline = true,
            ReadOnly = true, ScrollBars = ScrollBars.Vertical, Visible = false };
        private readonly ToolTip help = new();
        private readonly TableLayoutPanel layout = new() { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 4 };
        private TodSaveInspection inspection = TodSaveInspection.Read(null, null);
        private byte[] snapshot;
        private TodHudAssets assets;
        private readonly Dictionary<string, Bitmap> saveArtwork = new(StringComparer.Ordinal);
        private string assetMessage = "No game artwork loaded. Use Load game icons to select global_cached.psarc from your game dump.";

        // Literal pause-menu icon assignments -> named image-bank properties ->
        // byte-identical BC3 payloads in the pinned HUD atlas. No visual guesses.
        private static readonly IReadOnlyDictionary<int, int> IconMatches = new Dictionary<int, int>
            (TodResearch.HudIcons.GetProperty("items").EnumerateArray().ToDictionary(
                item => item.GetProperty("id").GetInt32(), item => item.GetProperty("texture_id").GetInt32()));

        public TodInventoryPreviewControl()
        {
            Name = "InventoryPreview"; Dock = DockStyle.Fill; Padding = new Padding(16);
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize)); layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100)); layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 0));
            status.Margin = new Padding(4, 4, 4, 12);
            var toolbar = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, WrapContents = true };
            foreach (Control control in new Control[] { ownedOnly, search, import, gallery, artwork })
            { control.Margin = new Padding(4, 4, 12, 8); toolbar.Controls.Add(control); }
            layout.Controls.Add(status, 0, 0); layout.Controls.Add(toolbar, 0, 1);
            layout.Controls.Add(cards, 0, 2); layout.Controls.Add(details, 0, 3); Controls.Add(layout);
            ownedOnly.CheckedChanged += (_, _) => Render(); search.TextChanged += (_, _) => Render();
            FontChanged += (_, _) => Render();
            import.Click += async (_, _) => await ImportArtwork();
            gallery.Click += (_, _) => ShowHudGallery(); artwork.Click += (_, _) => ShowSaveArtwork();
            if (File.Exists(Path.Combine(TodHudAssets.CacheFolder, "hud.tp")) && File.Exists(Path.Combine(TodHudAssets.CacheFolder, "hud.tph")))
            {
                try { LoadAssets(TodHudAssets.FromCache(TodHudAssets.CacheFolder)); }
                catch (Exception error) when (error is IOException or ArgumentException or UnauthorizedAccessException)
                { assetMessage = "Local artwork cache could not be loaded: " + error.Message; }
            }
            Render();
        }

        public void LoadSnapshot(byte[] data, string region)
        {
            snapshot = data == null ? null : (byte[])data.Clone();
            inspection = TodSaveInspection.Read(snapshot, region);
            details.Text = string.Empty; details.Visible = false; layout.RowStyles[3].Height = 0;
            Render();
        }

        public void LoadSession(SaveSession session)
        {
            foreach (var image in saveArtwork.Values) image.Dispose(); saveArtwork.Clear();
            if (session != null)
                foreach (string name in new[] { "ICON0.PNG", "PIC1.PNG" })
                {
                    try
                    {
                        string path = Path.Combine(session.WorkingFolder, name);
                        if (File.Exists(path)) saveArtwork[name] = ReadPng(path);
                    }
                    catch (Exception error) when (error is IOException or ArgumentException or OutOfMemoryException or UnauthorizedAccessException)
                    { /* Invalid/absent artwork never prevents opening a save. */ }
                }
            artwork.Enabled = saveArtwork.Count != 0;
            LoadSnapshot(session?.ReadInspectionData(), session?.Metadata.Region);
        }

        public void LoadAssets(TodHudAssets source)
        {
            ArgumentNullException.ThrowIfNull(source);
            assets = source; gallery.Enabled = true;
            assetMessage = $"208 verified USA-build HUD textures loaded locally; {IconMatches.Count} item icons matched through named pause-menu assets and identical texture data. Wrench remains unmapped. This does not select level-dependent alternate artwork.";
            Render();
        }

        private async Task ImportArtwork()
        {
            using var dialog = new OpenFileDialog { Title = "Select Tools of Destruction global_cached.psarc",
                Filter = "PSARC archive (*.psarc)|*.psarc", CheckFileExists = true };
            if (dialog.ShowDialog(FindForm()) != DialogResult.OK) return;
            string path = dialog.FileName;
            import.Enabled = false; status.Text = "Reading and verifying the two HUD assets…";
            try
            {
                var loaded = await Task.Run(() =>
                {
                    var source = TodHudAssets.FromArchive(path);
                    source.SaveCache(TodHudAssets.CacheFolder);
                    return source;
                });
                if (!IsDisposed) LoadAssets(loaded);
            }
            catch (Exception error) when (error is IOException or ArgumentException or UnauthorizedAccessException or OverflowException)
            {
                if (!IsDisposed) MessageBox.Show(FindForm(), error.Message, "Game artwork", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            finally { if (!IsDisposed) { import.Enabled = true; Render(); } }
        }

        private void ClearCards()
        {
            foreach (Control card in cards.Controls.Cast<Control>().ToArray())
            {
                foreach (var image in card.Controls.Find("ItemIcon", true).OfType<PictureBox>()) image.Image?.Dispose();
                card.Dispose();
            }
            cards.Controls.Clear();
        }

        private void Render()
        {
            if (IsDisposed) return;
            cards.SuspendLayout();
            try
            {
                ClearCards();
                if (!inspection.Available)
                {
                    status.Text = "Open a mapped Tools of Destruction save for inventory cards. Other games can still show their save artwork.";
                    help.SetToolTip(status, assetMessage);
                    return;
                }
                var items = inspection.Inventory.Where(item => (!ownedOnly.Checked || item.ScriptOwned) &&
                    (search.Text.Length == 0 || item.Name.Contains(search.Text, StringComparison.OrdinalIgnoreCase))).ToArray();
                status.Text = $"{items.Length} shown · {inspection.Inventory.Count(item => item.ScriptOwned)}/32 owned · " + AppearanceSummary() +
                    "\r\nSaved values, not staged edits · " + (assets == null ? "No game icons loaded" : $"208 HUD textures · {IconMatches.Count} asset-backed item icons");
                help.SetToolTip(status, "Names are native config names, not localized labels. " + assetMessage);
                foreach (var item in items) cards.Controls.Add(Card(item));
            }
            finally { cards.ResumeLayout(true); }
        }

        private string AppearanceSummary()
        {
            uint armor = BinaryPrimitives.ReadUInt32BigEndian(snapshot.AsSpan(0x458, 4));
            uint skin = BinaryPrimitives.ReadUInt32BigEndian(snapshot.AsSpan(0x480, 4));
            string Name(string section, string prefix, uint id)
            {
                var catalog = section == "armor" ? TodResearch.Map.GetProperty("progression").GetProperty("armor").GetProperty("catalog") :
                    TodResearch.Map.GetProperty("collectibles").GetProperty("skins").GetProperty("catalog");
                foreach (var entry in catalog.EnumerateArray())
                    if (entry.GetProperty("id").GetUInt32() == id) return CultureInfo.InvariantCulture.TextInfo.ToTitleCase(
                        entry.GetProperty("enum").GetString()[prefix.Length..].Replace('_', ' ').ToLowerInvariant());
                return "unknown ID " + id;
            }
            return "Armor: " + Name("armor", "ARMOR_", armor) + " · Skin: " + Name("skin", "SKIN_", skin);
        }

        private Control Card(TodInventoryItem item)
        {
            float scale = Math.Max(1, Font.Height / 18f);
            var card = new GroupBox { Name = "InventoryCard_" + item.Id, Text = item.Name, Width = (int)(280 * scale),
                Height = (int)(200 * scale), Padding = new Padding(10), Margin = new Padding(6) };
            var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 2 };
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 100 * scale)); layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100)); layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            var picture = new PictureBox { Name = "ItemIcon", Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.Zoom,
                BackColor = Color.FromArgb(38, 44, 52), Margin = new Padding(0, 4, 10, 8) };
            bool matched = assets != null && IconMatches.TryGetValue(item.Id, out int texture);
            if (matched) picture.Image = assets.DecodeTexture(IconMatches[item.Id]);
            else picture.Controls.Add(new Label { AutoSize = false, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter,
                ForeColor = Color.White, Text = assets == null ? "Load game\r\nartwork" : "Icon not\r\nyet mapped" });
            string ammo = float.IsFinite(item.Ammo) && item.Ammo >= 0 ? item.Ammo.ToString("0.###", CultureInfo.InvariantCulture) : "Unknown";
            string level = item.Id is >= 1 and <= 15 && item.StoredLevel < 10 ? "Level " + (item.StoredLevel + 1) : "Stored level: " + item.StoredLevel;
            var summary = new Label { Name = "ItemSummary", Dock = DockStyle.Fill, AutoSize = false,
                Text = (item.ScriptOwned ? "Owned" : "Not owned") + "\r\n" + level + "\r\nAmmo: " + ammo +
                    (matched ? "\r\nGame HUD icon" : "\r\nNo assigned artwork"), Margin = new Padding(0, 4, 0, 4) };
            var button = new Button { Text = "View details", AutoSize = true, Dock = DockStyle.Fill };
            button.Click += (_, _) =>
            {
                details.Visible = true; layout.RowStyles[3].Height = Math.Max(125, Font.Height * 6);
                details.Text = $"{item.Name} · inventory ID {item.Id}\r\n" +
                $"Script ownership: {(item.ScriptOwned ? "Yes" : "No")} (raw byte 0x{item.Ownership:X2}); stored level index: {item.StoredLevel}.\r\n" +
                $"Saved ammo: {item.Ammo:R}; saved XP: {item.Xp:R}; upgrade mask: 0x{item.ModifierMask:X8}.\r\n" +
                (matched ? $"HUD texture {IconMatches[item.Id]}: compiled pause-menu icon name and image-bank reference match this atlas image byte-for-byte. Not a universal runtime icon getter or level-dependent alternate-art selection.\r\n" : "Item artwork association not confirmed.\r\n") +
                item.Warning + "\r\nThese cards do not establish runtime usability or execute game UI code.";
            };
            layout.Controls.Add(picture, 0, 0); layout.Controls.Add(summary, 1, 0);
            layout.Controls.Add(button, 0, 1); layout.SetColumnSpan(button, 2); card.Controls.Add(layout);
            return card;
        }

        private static Bitmap ReadPng(string path)
        {
            if (new FileInfo(path).Length > 8 * 1024 * 1024) throw new InvalidDataException("Oversized save artwork.");
            byte[] bytes = File.ReadAllBytes(path);
            if (bytes.Length < 33 || !bytes.AsSpan(0, 8).SequenceEqual(new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 }))
                throw new InvalidDataException("Invalid save PNG.");
            uint width = BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(16, 4)), height = BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(20, 4));
            if (width == 0 || height == 0 || width > 4096 || height > 4096 || (ulong)width * height > 8 * 1024 * 1024)
                throw new InvalidDataException("Save artwork dimensions exceed preview limits.");
            using var stream = new MemoryStream(bytes, false); using var image = Image.FromStream(stream);
            return new Bitmap(image);
        }

        private void ShowHudGallery()
        {
            if (assets == null) return;
            var images = new Dictionary<string, Bitmap>();
            try
            {
                for (int index = 0; index < TodHudAssets.TextureCount; index++) images["HUD texture " + index] = assets.DecodeTexture(index);
                ShowImages("Tools of Destruction — game UI artwork", images);
            }
            finally { foreach (var image in images.Values) image.Dispose(); }
        }

        private void ShowSaveArtwork() => ShowImages("Save artwork", saveArtwork);
        private void ShowImages(string title, IReadOnlyDictionary<string, Bitmap> images)
        {
            using var window = CreateArtworkWindow(title, images);
            window.ShowDialog(FindForm());
        }

        private Form CreateArtworkWindow(string title, IReadOnlyDictionary<string, Bitmap> images)
        {
            var window = new Form { Text = title, Font = Font, AutoScaleMode = AutoScaleMode.Font,
                Size = new Size(900, 680), MinimumSize = new Size(440, 360), StartPosition = FormStartPosition.CenterParent };
            // Scroll the full, auto-sized content panel, not the wrapping flow itself.
            // FlowLayoutPanel's own scroll extent can omit the bottom row's padding.
            var viewport = new Panel { Name = "ArtworkViewport", Dock = DockStyle.Fill, AutoScroll = true };
            var flow = new FlowLayoutPanel { Name = "ArtworkImages", Dock = DockStyle.Top, AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink, WrapContents = true, Padding = new Padding(12) };
            flow.SuspendLayout();
            foreach (var image in images)
            {
                var group = new GroupBox { Text = image.Key, Width = images.Count > 2 ? 170 : 400, Height = images.Count > 2 ? 190 : 290, Margin = new Padding(6) };
                group.Controls.Add(new PictureBox { Dock = DockStyle.Fill, SizeMode = PictureBoxSizeMode.Zoom, BackColor = Color.FromArgb(38, 44, 52), Image = image.Value });
                flow.Controls.Add(group);
            }
            viewport.Controls.Add(flow); window.Controls.Add(viewport);
            flow.ResumeLayout(true);
            return window;
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing) { ClearCards(); foreach (var image in saveArtwork.Values) image.Dispose(); saveArtwork.Clear(); help.Dispose(); }
            base.Dispose(disposing);
        }
    }
}
