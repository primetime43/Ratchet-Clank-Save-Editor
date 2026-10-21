using System;
using System.Buffers.Binary;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static void InventoryPreviewChecks(string root)
    {
        Check("Embedded icon map binds all non-wrench inventory IDs to asset-backed HUD artwork", () =>
        {
            var items = TodResearch.HudIcons.GetProperty("items").EnumerateArray().ToArray();
            Equal(31, items.Length);
            True(items.Select(item => item.GetProperty("id").GetInt32()).SequenceEqual(Enumerable.Range(1, 31)), "Only the Wrench remains unmapped.");
            foreach (var item in items)
            {
                int id = item.GetProperty("id").GetInt32(), texture = item.GetProperty("texture_id").GetInt32();
                Equal(TodResearch.Inventory[id].GetProperty("enum").GetString(), item.GetProperty("enum").GetString());
                Equal(TodResearch.Inventory[id].GetProperty("config_name").GetString(), item.GetProperty("config_name").GetString());
                True(texture >= 0 && texture < TodHudAssets.TextureCount && item.GetProperty("assignment_offsets").GetArrayLength() > 0,
                    "A mapping must have a valid atlas index and compiled assignment evidence.");
                foreach (var node in item.GetProperty("image_nodes").EnumerateArray())
                    True(node.GetProperty("hud_texture_ids").EnumerateArray().Any(value => value.GetInt32() == texture), "All named-node matches must corroborate the selected texture.");
            }
            Equal(84, items.Single(item => item.GetProperty("id").GetInt32() == 16).GetProperty("texture_id").GetInt32());
            Equal(44, items.Single(item => item.GetProperty("id").GetInt32() == 11).GetProperty("texture_id").GetInt32());
        });
        Check("BC3 decoder handles alpha/color palettes, partial blocks and bounded inputs", () =>
        {
            byte[] block = new byte[16]; block[0] = 255; block[1] = 0;
            BinaryPrimitives.WriteUInt16LittleEndian(block.AsSpan(8, 2), 0xF800);
            BinaryPrimitives.WriteUInt16LittleEndian(block.AsSpan(10, 2), 0x001F);
            using var red = TodHudAssets.DecodeBc3(block, 3, 2);
            Equal(Color.FromArgb(255, 255, 0, 0).ToArgb(), red.GetPixel(2, 1).ToArgb());
            block[0] = 0; block[1] = 255; block[2] = 6;
            using var transparent = TodHudAssets.DecodeBc3(block, 4, 4);
            Equal(0, (int)transparent.GetPixel(0, 0).A);
            block[2] = 7;
            using var opaque = TodHudAssets.DecodeBc3(block, 4, 4);
            Equal(255, (int)opaque.GetPixel(0, 0).A);
            Throws<InvalidDataException>(() => TodHudAssets.DecodeBc3(block, 0, 4));
            Throws<InvalidDataException>(() => TodHudAssets.DecodeBc3(block, 1025, 4));
            Throws<InvalidDataException>(() => TodHudAssets.DecodeBc3(block[..15], 4, 4));
        });
        Check("Preview imports reject invalid archive/cache headers without changing input", () =>
        {
            string archive = Path.Combine(root, "bad-preview.psarc");
            byte[] bad = new byte[32]; File.WriteAllBytes(archive, bad);
            Throws<InvalidDataException>(() => TodHudAssets.FromArchive(archive));
            True(bad.SequenceEqual(File.ReadAllBytes(archive)), "Archive import is read-only.");
            string cache = Path.Combine(root, "bad-preview-cache"); Directory.CreateDirectory(cache);
            File.WriteAllBytes(Path.Combine(cache, "hud.tp"), new byte[4]);
            File.WriteAllBytes(Path.Combine(cache, "hud.tph"), new byte[4]);
            Throws<InvalidDataException>(() => TodHudAssets.FromCache(cache));
        });
        Check("Inventory cards filter saved ownership, preserve unknown ammo and clear between games", () =>
        {
            byte[] data = EditableFixture(), before = data.ToArray();
            data[5 * 20 + 16] = 0; before = data.ToArray();
            using var preview = new TodInventoryPreviewControl(); preview.LoadSnapshot(data, "BCUS98127");
            var cards = preview.Controls.Find("InventoryCards", true).Cast<FlowLayoutPanel>().Single();
            int owned = TodSaveInspection.Read(data, "BCUS98127").Inventory.Count(item => item.ScriptOwned);
            Equal(owned, cards.Controls.Count);
            preview.Controls.Find("InventoryOwnedOnly", true).Cast<CheckBox>().Single().Checked = false;
            Equal(32, cards.Controls.Count);
            preview.Controls.Find("InventorySearch", true).Cast<TextBox>().Single().Text = "buzz";
            Equal(1, cards.Controls.Count); Equal("InventoryCard_5", cards.Controls[0].Name);
            preview.Controls.Find("InventorySearch", true).Cast<TextBox>().Single().Text = "";
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(5 * 20 + 8, 4), 0x7FC12345);
            preview.LoadSnapshot(data, "BCUS98127");
            var summary = cards.Controls.Find("InventoryCard_5", false).Single().Controls.Find("ItemSummary", true).Cast<Label>().Single();
            True(summary.Text.Contains("Ammo: Unknown"), "Nonfinite ammo is not replaced by a plausible number.");
            preview.LoadSnapshot(data, "BCUS98124"); Equal(0, cards.Controls.Count);
            True(preview.Controls.Find("InventoryItemDetails", true).Cast<TextBox>().Single().Text.Length == 0, "Old item details must be cleared.");
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(5 * 20 + 8, 4), BinaryPrimitives.ReadUInt32BigEndian(before.AsSpan(5 * 20 + 8, 4)));
            True(before.SequenceEqual(data), "Preview does not mutate any saved bytes.");
        });
        Check("Save artwork previews load detached PNGs and never dirty Save All", () =>
        {
            string folder = Fixture(root, "BCUS98127");
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), EditableFixture());
            using (var png = new Bitmap(16, 16))
            { png.Save(Path.Combine(folder, "ICON0.PNG"), ImageFormat.Png); png.Save(Path.Combine(folder, "PIC1.PNG"), ImageFormat.Png); }
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "inventory-backups"));
            using var form = new MainForm();
            typeof(MainForm).GetField("session", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(form, session);
            typeof(MainForm).GetMethod("ShowSession", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(form, null);
            var preview = form.Controls.Find("InventoryPreview", true).Cast<TodInventoryPreviewControl>().Single();
            True(preview.Controls.Find("InventorySaveArtwork", true).Cast<Button>().Single().Enabled, "Both save PNGs can be viewed.");
            preview.Controls.Find("InventorySearch", true).Cast<TextBox>().Single().Text = "Combuster";
            True(!Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Read-only browsing must not dirty the editor.");
            // Working-copy PNGs are not held open by the inventory picture viewer.
            using var writable = new FileStream(Path.Combine(session.WorkingFolder, "PIC1.PNG"), FileMode.Open, FileAccess.ReadWrite, FileShare.None);
        });
        Check("Artwork gallery can scroll the entire last row into view after resizing and font scaling", () =>
        {
            using var image = new Bitmap(8, 8);
            var images = Enumerable.Range(0, 208).ToDictionary(index => "HUD texture " + index, _ => image);
            using var preview = new TodInventoryPreviewControl();
            foreach (float fontSize in new[] { 9f, 13f, 17f })
            {
                using var font = new Font("Segoe UI", fontSize); preview.Font = font;
                using var window = (Form)typeof(TodInventoryPreviewControl)
                    .GetMethod("CreateArtworkWindow", BindingFlags.Instance | BindingFlags.NonPublic)
                    .Invoke(preview, new object[] { "Artwork scroll check", images });
                var viewport = window.Controls.Find("ArtworkViewport", true).Cast<Panel>().Single();
                var flow = window.Controls.Find("ArtworkImages", true).Cast<FlowLayoutPanel>().Single();
                window.Show(); Application.DoEvents();
                foreach (var size in new[] { new Size(900, 680), new Size(858, 740), new Size(620, 480), new Size(1100, 820) })
                {
                    window.Size = size; Application.DoEvents();
                    viewport.AutoScrollPosition = Point.Empty; Application.DoEvents();
                    viewport.ScrollControlIntoView(flow.Controls[207]);
                    viewport.AutoScrollPosition = new Point(0, viewport.VerticalScroll.Maximum);
                    Application.DoEvents();
                    foreach (Control card in flow.Controls.Cast<Control>().Skip(204))
                    {
                        var bounds = viewport.RectangleToClient(card.RectangleToScreen(card.ClientRectangle));
                        True(bounds.Bottom <= viewport.ClientSize.Height - flow.Padding.Bottom,
                            $"{card.Text} must be fully reachable, including bottom padding ({fontSize}pt, {size}).");
                    }
                    True(!viewport.HorizontalScroll.Visible, "Artwork should wrap without horizontal scrolling.");
                }
                if (fontSize == 13f)
                {
                    using var screenshot = new Bitmap(window.Width, window.Height);
                    window.DrawToBitmap(screenshot, new Rectangle(Point.Empty, screenshot.Size));
                    screenshot.Save(Path.Combine(root, "artwork-gallery-bottom.png"), ImageFormat.Png);
                }
            }
        });
    }

    private static void InventoryPreviewWithGame(string archive, string saveFolder, string root)
    {
        var assets = TodHudAssets.FromArchive(archive); assets.SaveCache(TodHudAssets.CacheFolder);
        var cached = TodHudAssets.FromCache(TodHudAssets.CacheFolder);
        using (var first = assets.DecodeTexture(24)) using (var second = cached.DecodeTexture(24))
            Equal(first.GetPixel(32, 32).ToArgb(), second.GetPixel(32, 32).ToArgb());
        var original = Snapshot(saveFolder);
        using var session = SaveSession.Open(saveFolder, new Encryption(), backupRoot: Path.Combine(root, "actual-preview-backup"));
        using var form = new MainForm();
        typeof(MainForm).GetField("session", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(form, session);
        typeof(MainForm).GetMethod("ShowSession", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(form, null);
        var preview = form.Controls.Find("InventoryPreview", true).Cast<TodInventoryPreviewControl>().Single(); preview.LoadAssets(assets);
        var tabs = Field<TabControl>(form, "TabControl");
        tabs.SelectedTab = tabs.TabPages.Cast<TabPage>().Single(tab => tab.Name == "InventoryPreviewTab");
        preview.Controls.Find("InventoryOwnedOnly", true).Cast<CheckBox>().Single().Checked = false;
        var cards = preview.Controls.Find("InventoryCards", true).Cast<FlowLayoutPanel>().Single();
        foreach (var item in TodResearch.HudIcons.GetProperty("items").EnumerateArray())
        {
            int id = item.GetProperty("id").GetInt32(), texture = item.GetProperty("texture_id").GetInt32();
            var picture = cards.Controls.Find("InventoryCard_" + id, false).Single().Controls.Find("ItemIcon", true).Cast<PictureBox>().Single();
            True(picture.Image != null, "Every mapped card must actually render its real icon.");
            using var expected = assets.DecodeTexture(texture);
            Equal(expected.GetPixel(32, 32).ToArgb(), ((Bitmap)picture.Image).GetPixel(32, 32).ToArgb());
        }
        True(cards.Controls.Find("InventoryCard_0", false).Single().Controls.Find("ItemIcon", true).Cast<PictureBox>().Single().Image == null,
            "Unmapped Wrench must retain its placeholder, not an invented icon.");
        foreach (var scale in new[] { (new Size(1200, 820), 11f, "artifacts/inventory-preview.png"),
            (new Size(900, 700), 13f, "artifacts/inventory-preview-scaled.png") })
        {
            form.Size = scale.Item1; form.Font = new Font("Segoe UI", scale.Item2); form.Show(); Application.DoEvents();
            using var bitmap = new Bitmap(form.Width, form.Height); form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, bitmap.Size));
            bitmap.Save(scale.Item3, ImageFormat.Png);
        }
        Same(original, Snapshot(saveFolder));
        Console.WriteLine("Actual save previewed read-only; both HUD assets cached locally; source save unchanged.");
    }

    private static void HudContactSheet(string archive, string output)
    {
        if (File.Exists(output)) throw new IOException("Contact sheet output already exists.");
        var assets = TodHudAssets.FromArchive(archive);
        using var sheet = new Bitmap(12 * 100, 18 * 110);
        using var graphics = Graphics.FromImage(sheet); graphics.Clear(Color.FromArgb(38, 44, 52));
        using var font = new Font("Segoe UI", 9);
        for (int index = 0; index < TodHudAssets.TextureCount; index++)
        {
            using var image = assets.DecodeTexture(index);
            int x = index % 12 * 100, y = index / 12 * 110;
            graphics.DrawImage(image, new Rectangle(x + 8, y + 5, 84, 84));
            graphics.DrawString($"{index} · {image.Width}×{image.Height}", font, Brushes.White, x + 4, y + 90);
        }
        sheet.Save(output, ImageFormat.Png);
        Console.WriteLine("Decoded all 208 exact-build HUD textures: " + output);
    }
}
