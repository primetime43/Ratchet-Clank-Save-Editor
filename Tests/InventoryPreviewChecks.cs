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
