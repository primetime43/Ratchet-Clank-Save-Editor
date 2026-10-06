using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static class Program
{
    private static int passed;

    [STAThread]
    private static int Main()
    {
        ApplicationConfiguration.Initialize();
        string root = Path.Combine(Path.GetTempPath(), "RatchetClankSaveEditor-Tests-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            Check("Big endian values round trip, including int.MaxValue", () =>
            {
                using var stream = new MemoryStream();
                stream.WriteInt32(int.MaxValue);
                Equal("7FFFFFFF", Convert.ToHexString(stream.ToArray()));
                stream.Position = 0;
                Equal(int.MaxValue, stream.ReadInt32());
            });
            Check("Partial reads complete, truncated values fail", () =>
            {
                using var partial = new PartialReadStream(new byte[] { 0x12, 0x34, 0x56, 0x78 });
                Equal(0x12345678, partial.ReadInt32());
                using var truncated = new MemoryStream(new byte[] { 1, 2, 3 });
                Throws<EndOfStreamException>(() => truncated.ReadInt32());
            });
            Check("SFO fields can move and Unicode subtitles are preserved", () =>
            {
                string folder = Fixture(root, "NPUA80908");
                var metadata = SfoMetadata.Read(Path.Combine(folder, "PARAM.SFO"));
                Equal("NPUA80908", metadata.Region);
                Equal("0001020304050607", metadata.AccountId);
                Equal("Planète Veldin", metadata.Planet);
                byte[] data = File.ReadAllBytes(Path.Combine(folder, "PARAM.SFO"));
                BinaryPrimitives.WriteUInt32LittleEndian(data.AsSpan(12), uint.MaxValue);
                File.WriteAllBytes(Path.Combine(folder, "PARAM.SFO"), data);
                Throws<InvalidDataException>(() => SfoMetadata.Read(Path.Combine(folder, "PARAM.SFO")));
            });
            foreach (string region in new[] { "NPUA80908", "BLES00301", "BCUS98127", "NPUA80643" })
                Check($"{region}: correct file, offsets, backups and repeat saves", () =>
                {
                    string folder = Fixture(root, region);
                    var tools = new FakeTools();
                    var original = Snapshot(folder);
                    using var session = SaveSession.Open(folder, tools);
                    Equal(session.Profile.FileName, tools.DecryptedFile);
                    Equal(123, session.Bolts);
                    Equal(session.Profile.RaritaniumOffset.HasValue ? 45 : 0, session.Raritanium);
                    Same(original, Snapshot(folder));
                    string backup = session.Save(int.MaxValue, 987, Path.Combine(root, "backups"));
                    Same(original, Snapshot(backup));
                    Equal(int.MaxValue, ReadValue(folder, session.Profile.BoltsOffset, session.Profile.FileName));
                    if (session.Profile.RaritaniumOffset is int offset)
                        Equal(987, ReadValue(folder, offset, session.Profile.FileName));
                    Equal(session.Profile.FileName, tools.EncryptedFile);
                    string secondBackup = session.Save(999, 12, Path.Combine(root, "backups"));
                    True(backup != secondBackup, "Backups must be unique.");
                    Equal(999, session.Bolts);
                    Equal(999, ReadValue(folder, session.Profile.BoltsOffset, session.Profile.FileName));
                    var expected = original[session.Profile.FileName].ToArray();
                    BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(session.Profile.BoltsOffset), 999);
                    if (session.Profile.RaritaniumOffset is int raritanium)
                        BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(raritanium), 12);
                    True(expected.SequenceEqual(File.ReadAllBytes(Path.Combine(folder, session.Profile.FileName))), "Unrelated bytes changed.");
                });
            Check("Encryption failures never change original files", () =>
            {
                string folder = Fixture(root, "NPUA80908");
                var tools = new FakeTools { FailEncrypt = true };
                var original = Snapshot(folder);
                using var session = SaveSession.Open(folder, tools);
                Throws<InvalidOperationException>(() => session.Save(999, 999, Path.Combine(root, "backups")));
                Same(original, Snapshot(folder));
                Equal(123, session.Bolts);
            });
            Check("Missing, unsupported, truncated and invalid saves are rejected", () =>
            {
                string unsupported = Fixture(root, "NPUA80908");
                File.WriteAllBytes(Path.Combine(unsupported, "PARAM.SFO"), Sfo("UNKNOWN01"));
                Throws<InvalidDataException>(() => SaveSession.Open(unsupported, new FakeTools()));
                string missing = Fixture(root, "NPUA80643");
                File.Delete(Path.Combine(missing, "USR-DATA"));
                Throws<FileNotFoundException>(() => SaveSession.Open(missing, new FakeTools()));
                string truncated = Fixture(root, "NPUA80908");
                File.WriteAllBytes(Path.Combine(truncated, "GAME.SAV"), new byte[10]);
                Throws<InvalidDataException>(() => SaveSession.Open(truncated, new FakeTools()));
                string negative = Fixture(root, "NPUA80643");
                using (var file = File.OpenWrite(Path.Combine(negative, "USR-DATA"))) { file.Position = 0x24; file.WriteInt32(-1); }
                Throws<InvalidDataException>(() => SaveSession.Open(negative, new FakeTools()));
            });
            Check("External changes block save and backup", () =>
            {
                string folder = Fixture(root, "NPUA80908");
                using var session = SaveSession.Open(folder, new FakeTools());
                File.WriteAllText(Path.Combine(folder, "PARAM.PFD"), "Changed externally");
                var changed = Snapshot(folder);
                Throws<IOException>(() => session.Save(9, 9, Path.Combine(root, "backups")));
                Throws<IOException>(() => session.BackUp(Path.Combine(root, "backups")));
                Same(changed, Snapshot(folder));
            });
            Check("Partial commit rolls back and keeps a full backup", () =>
            {
                string folder = Fixture(root, "NPUA80908");
                var original = Snapshot(folder);
                using var session = SaveSession.Open(folder, new FakeTools());
                // Hold the second file against replacement so the first replacement succeeds then rolls back.
                using var locked = File.Open(Path.Combine(folder, "PARAM.SFO"), FileMode.Open, FileAccess.Read, FileShare.Read);
                Throws<IOException>(() => session.Save(999, 999, Path.Combine(root, "backups")));
                Same(original, Snapshot(folder));
                Same(original, Snapshot(session.LastBackup));
                Equal(123, session.Bolts);
            });
            Check("Metadata actions stay in the working copy until save", () =>
            {
                string folder = Fixture(root, "NPUA80908");
                var original = Snapshot(folder);
                using var session = SaveSession.Open(folder, new FakeTools());
                session.PatchMetadata();
                session.UpdateIntegrity();
                True(session.MetadataChanged, "Metadata should be pending.");
                Same(original, Snapshot(folder));
                session.Save(123, 45, Path.Combine(root, "backups"));
                True(!session.MetadataChanged, "Metadata flag should clear after save.");
            });
            Check("Bundled pfdtool silent failures are detected, including paths with spaces", () =>
            {
                string folder = Fixture(root, "NPUA80643");
                var original = Snapshot(folder);
                using var tools = new Encryption();
                // Deliberately invalid PARAM.PFD: the legacy exe silently returns exit code zero.
                Throws<InvalidOperationException>(() => SaveSession.Open(folder, tools));
                Throws<InvalidOperationException>(() => tools.Update(folder, "NPUA80643"));
                Same(original, Snapshot(folder));
            });
            Check("Compact UI loads, switches games and renders at higher scale", () => UiChecks(root));
            Console.WriteLine($"All {passed} regression checks passed.");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
        finally { Directory.Delete(root, true); }
    }

    private static void UiChecks(string root)
    {
        using var form = new MainForm();
        string initialTitle = form.Text;
        True(initialTitle.StartsWith("Ratchet & Clank Save Editor v"), "The title should display the app version at startup.");
        var sessionField = typeof(MainForm).GetField("session", BindingFlags.Instance | BindingFlags.NonPublic);
        var show = typeof(MainForm).GetMethod("ShowSession", BindingFlags.Instance | BindingFlags.NonPublic);
        var busy = typeof(MainForm).GetMethod("SetBusy", BindingFlags.Instance | BindingFlags.NonPublic);
        var tabs = Field<TabControl>(form, "TabControl");
        True(!Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Save must be disabled before opening.");
        True(form.ClientSize.Width < 600 && form.ClientSize.Height < 300, "The default window should remain compact.");
        form.StartPosition = FormStartPosition.Manual;
        form.Location = new Point(-20000, -20000);
        form.ShowInTaskbar = false;
        form.Show();
        string artifacts = Path.GetFullPath("artifacts");
        Directory.CreateDirectory(artifacts);
        True(tabs.Visible && !tabs.Enabled, "The original tabs should be visible and disabled until a save is opened.");
        True(tabs.TabPages[0].Text == "Game Save Information" && tabs.TabPages[1].Text == "Game Save Editing",
            "Keep the original tab order and names.");
        Capture(form, Path.Combine(artifacts, "ui-compact-empty.png"));
        foreach (string region in new[] { "BLES00301", "NPUA80908" })
        {
            (sessionField.GetValue(form) as SaveSession)?.Dispose();
            string folder = Fixture(root, region);
            bool hasArtwork = region == "BLES00301";
            if (hasArtwork)
            {
                using var artwork = new Bitmap(16, 16);
                artwork.Save(Path.Combine(folder, "ICON0.PNG"));
            }
            var session = SaveSession.Open(folder, new FakeTools());
            sessionField.SetValue(form, session);
            show.Invoke(form, null);
            busy.Invoke(form, new object[] { false });
            tabs.SelectedIndex = 1;
            True(Field<NumericUpDown>(form, "CasinoChipsNumericUpDown").Visible == session.Profile.RaritaniumOffset.HasValue,
                "Raritanium visibility did not reset on game switch.");
            True(Field<Button>(form, "SaveImageButton").Enabled == hasArtwork, "Artwork should enable export only when present.");
            tabs.SelectedIndex = 1;
            if (hasArtwork)
            {
                using var unlocked = File.Open(Path.Combine(session.WorkingFolder, "ICON0.PNG"), FileMode.Open, FileAccess.ReadWrite, FileShare.None);
            }
            tabs.SelectedIndex = 0;
            True(!Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Save should be disabled without pending edits.");
            var bolts = Field<NumericUpDown>(form, "MoneyNumericUpDown");
            bolts.Value++;
            True(Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Editing currency should enable save.");
            Equal(initialTitle + " • Unsaved changes", form.Text);
            bolts.Value = session.Bolts;
            True(!Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Reverting an edit should disable save.");
            Equal(initialTitle, form.Text);
        }
        foreach (var size in new[] { new Size(499, 248) })
        {
            form.ClientSize = size;
            form.PerformLayout();
            for (int i = 0; i < tabs.TabCount; i++)
            {
                tabs.SelectedIndex = i;
                tabs.SelectedTab.CreateControl();
                form.PerformLayout();
                using var image = new Bitmap(form.Width, form.Height);
                form.DrawToBitmap(image, new Rectangle(Point.Empty, image.Size));
                image.Save(Path.Combine(artifacts, $"ui-compact-{i}.png"));
                foreach (var control in Descendants(tabs.SelectedTab).Where(c => c.Visible && c.Parent is not NumericUpDown && c is TextBox or NumericUpDown or Button))
                {
                    True(control.Width >= 50 && control.Height >= 20, $"Clipped control: {control.Name} / {control.Text}");
                    True(control.Parent.ClientRectangle.Contains(control.Bounds), $"Control exceeds its layout: {control.Text}, bounds {control.Bounds}, parent {control.Parent.ClientRectangle}, window {size}");
                }
            }
        }
        tabs.SelectedIndex = 1;
        form.ClientSize = new Size(499, 248);
        Field<NumericUpDown>(form, "MoneyNumericUpDown").Value = int.MaxValue;
        Field<NumericUpDown>(form, "CasinoChipsNumericUpDown").Value = int.MaxValue;
        Capture(form, Path.Combine(artifacts, "ui-compact-edited.png"));
        form.Scale(new SizeF(1.5f, 1.5f));
        Capture(form, Path.Combine(artifacts, "ui-compact-scaled.png"));
        (sessionField.GetValue(form) as SaveSession)?.Dispose();
        sessionField.SetValue(form, null);
    }

    private static void Capture(MainForm form, string path)
    {
        form.PerformLayout();
        using var image = new Bitmap(form.Width, form.Height);
        form.DrawToBitmap(image, new Rectangle(Point.Empty, image.Size));
        image.Save(path);
    }

    private static IEnumerable<Control> Descendants(Control parent)
    {
        foreach (Control child in parent.Controls)
        {
            yield return child;
            foreach (var nested in Descendants(child)) yield return nested;
        }
    }

    private static T Field<T>(MainForm form, string name) => (T)typeof(MainForm).GetField(name, BindingFlags.Instance | BindingFlags.NonPublic).GetValue(form);

    private static string Fixture(string root, string region)
    {
        string folder = Path.Combine(root, "Save with spaces " + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        File.WriteAllBytes(Path.Combine(folder, "PARAM.SFO"), Sfo(region));
        File.WriteAllText(Path.Combine(folder, "PARAM.PFD"), "Test integrity");
        var profile = SaveProfile.ForRegion(region);
        byte[] data = Enumerable.Repeat((byte)0x55, 0x1100).ToArray();
        BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(profile.BoltsOffset), 123);
        if (profile.RaritaniumOffset is int offset) BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(offset), 45);
        File.WriteAllBytes(Path.Combine(folder, profile.FileName), data);
        File.WriteAllText(Path.Combine(folder, "EXTRA.DAT"), "Preserve this too");
        return folder;
    }

    private static byte[] Sfo(string region)
    {
        var fields = new Dictionary<string, string>
        {
            ["SUB_TITLE"] = "Planète Veldin", ["ACCOUNT_ID"] = "0001020304050607", ["SAVEDATA_DIRECTORY"] = region + "-SAVE1"
        };
        using var keys = new MemoryStream();
        using var values = new MemoryStream();
        using var index = new MemoryStream();
        using var writer = new BinaryWriter(index, Encoding.UTF8, true);
        foreach (var field in fields)
        {
            byte[] value = Encoding.UTF8.GetBytes(field.Value + "\0");
            writer.Write((ushort)keys.Position);
            writer.Write((ushort)0x0204);
            writer.Write(value.Length);
            writer.Write(value.Length);
            writer.Write((uint)values.Position);
            keys.Write(Encoding.ASCII.GetBytes(field.Key + "\0"));
            values.Write(value);
        }
        using var result = new MemoryStream();
        using var header = new BinaryWriter(result, Encoding.UTF8, true);
        header.Write(0x46535000u);
        header.Write(0x00000101u);
        header.Write((uint)(20 + index.Length + 12));
        header.Write((uint)(20 + index.Length + 12 + keys.Length));
        header.Write((uint)fields.Count);
        result.Write(index.ToArray());
        result.Write(new byte[12]);
        result.Write(keys.ToArray());
        result.Write(values.ToArray());
        return result.ToArray();
    }

    private static int ReadValue(string folder, int offset, string file)
    {
        using var stream = File.OpenRead(Path.Combine(folder, file));
        stream.Position = offset;
        return stream.ReadInt32();
    }

    private static Dictionary<string, byte[]> Snapshot(string folder) => Directory.GetFiles(folder).ToDictionary(Path.GetFileName, File.ReadAllBytes);
    private static void Same(Dictionary<string, byte[]> a, Dictionary<string, byte[]> b) => True(
        a.Count == b.Count && a.All(p => b.TryGetValue(p.Key, out var value) && p.Value.SequenceEqual(value)), "Files changed unexpectedly.");
    private static void Check(string name, Action action) { action(); passed++; Console.WriteLine("PASS " + name); }
    private static void Equal<T>(T expected, T actual) => True(EqualityComparer<T>.Default.Equals(expected, actual), $"Expected {expected}, got {actual}.");
    private static void True(bool condition, string message) { if (!condition) throw new Exception(message); }
    private static void Throws<T>(Action action) where T : Exception
    {
        try { action(); } catch (T) { return; }
        throw new Exception($"Expected {typeof(T).Name}.");
    }

    private sealed class FakeTools : ISaveTools
    {
        public string DecryptedFile;
        public string EncryptedFile;
        public bool FailEncrypt;
        public void Decrypt(string folder, string region, string file)
        {
            DecryptedFile = file;
            File.WriteAllText(Path.Combine(folder, "PARAM.PFD"), "Decrypted integrity");
        }
        public void Encrypt(string folder, string region, string file)
        {
            EncryptedFile = file;
            File.WriteAllText(Path.Combine(folder, "PARAM.PFD"), "Encrypted integrity");
            if (FailEncrypt) throw new InvalidOperationException("Simulated encryption failure");
        }
        public void Update(string folder, string region) => File.WriteAllText(Path.Combine(folder, "PARAM.PFD"), "Updated integrity");
        public void Patch(string folder) => File.WriteAllBytes(Path.Combine(folder, "PARAM.SFO"), Sfo("NPUA80908"));
    }

    private sealed class PartialReadStream : MemoryStream
    {
        public PartialReadStream(byte[] data) : base(data) { }
        public override int Read(Span<byte> buffer) => base.Read(buffer.Slice(0, Math.Min(1, buffer.Length)));
    }
}
