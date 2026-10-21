using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static byte[] Rc1AmmoFixture()
    {
        byte[] data = Enumerable.Repeat((byte)0xA5, 0xB0000).ToArray();
        int end = 16;
        foreach (var record in Rc1Research.PlayerRecords)
        {
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(record.Offset - 8), record.Id);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(record.Offset - 4), (uint)record.Length);
            data.AsSpan(record.Offset, record.Length).Clear();
            end = record.Offset + ((record.Length + 3) & ~3);
        }
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(end), uint.MaxValue);
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(end + 4), 0);
        BinaryPrimitives.WriteUInt32BigEndian(data, (uint)end);
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(4), 0x82A4);
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(8), (uint)(end - 8));
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(12), 0);
        foreach (var field in Rc1Research.Ammo)
        {
            data[field.OwnershipOffset] = 1;
            BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(field.Offset), field.Maximum / 2);
        }
        return data;
    }

    private static void Rc1AmmoChecks(string root)
    {
        Check("RC1 native record map offers eleven bounded owned-weapon ammo edits with exact byte preservation", () =>
        {
            byte[] data = Rc1AmmoFixture(), original = data.ToArray();
            True(Rc1SaveEditing.Supports(data, "NPEA00385"), "Native layout must be recognized.");
            var fields = Rc1SaveEditing.Fields(data, "NPEA00385"); Equal(11, fields.Count);
            foreach (var field in fields)
            {
                byte[] expected = data.ToArray();
                BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(field.Offset), field.Maximum);
                byte[] edited = Rc1SaveEditing.Apply(data, "NPEA00385", new Dictionary<string, decimal> { [field.Key] = field.Maximum });
                True(expected.SequenceEqual(edited), "Only the requested ammo word may change: " + field.Name);
            }
            var refilled = Rc1SaveEditing.Apply(data, "NPEA00385", fields.ToDictionary(field => field.Key, field => (decimal)field.Maximum));
            foreach (var field in fields) Equal(field.Maximum, BinaryPrimitives.ReadInt32BigEndian(refilled.AsSpan(field.Offset)));
            True(original.SequenceEqual(data), "All edits must leave the caller's original array intact.");
            var noOp = Rc1SaveEditing.Apply(data, "NPEA00385", fields.ToDictionary(field => field.Key, field => (decimal)field.Current));
            True(original.SequenceEqual(noOp), "No-op edits must preserve all bytes.");
        });
        Check("RC1 ammo rejects invalid batches and keeps unowned, noncanonical and excessive ammo read-only", () =>
        {
            byte[] data = Rc1AmmoFixture();
            var first = Rc1Research.Ammo[0]; var second = Rc1Research.Ammo[1];
            foreach (decimal value in new[] { -1m, 0.5m, first.Maximum + 1m, decimal.MaxValue })
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", new Dictionary<string, decimal> { [first.Key] = value }));
            foreach (byte owned in new byte[] { 0, 2, 0xFF })
            {
                data[first.OwnershipOffset] = owned;
                True(!Rc1SaveEditing.Fields(data, "NPEA00385").Any(field => field.Key == first.Key), "Only canonical ownership can expose ammo edits.");
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", new Dictionary<string, decimal> { [first.Key] = 1 }));
            }
            data[first.OwnershipOffset] = 1;
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(first.Offset), uint.MaxValue);
            True(!Rc1SaveEditing.Fields(data, "NPEA00385").Any(field => field.Key == first.Key), "Extreme ammo must remain read-only.");
            byte[] original = data.ToArray();
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", new Dictionary<string, decimal>
                { [second.Key] = 0, [first.Key] = 0 }));
            True(data.SequenceEqual(original), "Failed mixed batch must leave all fields unchanged.");
            foreach (string region in new[] { "NPUA80643", "NPJA40001", "NPEA00386", "BCUS98127" })
            {
                Equal(0, Rc1SaveEditing.Fields(data, region).Count);
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, region, new Dictionary<string, decimal> { [second.Key] = 0 }));
            }
            var malformed = Rc1AmmoFixture(); malformed[0x1F] ^= 1;
            True(!Rc1SaveEditing.Supports(malformed, "NPEA00385"), "A record-ID mismatch must reject mapped edits.");
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(Rc1AmmoFixture(), "NPEA00385", new Dictionary<string, decimal> { ["rc1_grant_999"] = 1 }));
        });
        Check("RC1 UI loads on a hidden tab, stages ammo, blocks invalid bulk input and clears when switching games", () =>
        {
            string folder = Fixture(root, "NPEA00385");
            File.WriteAllBytes(Path.Combine(folder, "USR-DATA"), Rc1AmmoFixture());
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "rc1-ammo-ui-backups"));
            using var form = new MainForm();
            typeof(MainForm).GetField("session", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(form, session);
            typeof(MainForm).GetMethod("ShowSession", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(form, null);
            var editor = Field<Rc1SaveEditingControl>(form, "rc1Editor");
            Equal(11, editor.Controls.Find("Rc1Edit_rc1_ammo_10", true).Length == 1
                ? editor.Controls.OfType<TableLayoutPanel>().Single().Controls.OfType<NumericTextBox>().Count() : 0);
            var input = editor.Controls.Find("Rc1Edit_rc1_ammo_10", true).Cast<NumericTextBox>().Single();
            input.Text = "5"; Equal(5m, editor.PendingEdits["rc1_ammo_10"]);
            input.Text = "5.5"; True(editor.HasInvalidInputs, "Fractional ammo must be invalid.");
            True(!Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Invalid RC1 ammo must disable Save All.");
            Throws<InvalidOperationException>(() => { var ignored = editor.PendingEdits; });
            var tabs = Field<TabControl>(form, "TabControl"); tabs.TabPages[1].Enabled = true; tabs.SelectedTab = tabs.TabPages[1];
            form.Size = new Size(1050, 850); form.ShowInTaskbar = false; form.Show(); Application.DoEvents();
            editor.Controls.Find("Rc1RefillAmmo", true).Cast<Button>().Single().PerformClick();
            Equal("5.5", input.Text);
            input.Text = "5";
            editor.Controls.Find("Rc1RefillAmmo", true).Cast<Button>().Single().PerformClick();
            Equal(40m, editor.PendingEdits["rc1_ammo_10"]); Equal(11, editor.PendingEdits.Count);
            True(Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Valid RC1 ammo must enable Save All.");
            string preview = Path.GetFullPath(Path.Combine("artifacts", "rc1-ammo-editor.png"));
            Directory.CreateDirectory(Path.GetDirectoryName(preview));
            using (var bitmap = new Bitmap(form.Width, form.Height)) { form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, bitmap.Size)); bitmap.Save(preview); }
            input.Value = 20; // restore this field's baseline, then clear all other staged fields
            editor.LoadSnapshot(Rc1AmmoFixture(), "NPEA00385");
            True(!editor.HasChanges, "Reload must clear staged state.");
            editor.LoadSnapshot(EditableFixture(), "BCUS98127");
            True(!editor.Visible && !editor.HasChanges, "Other games must not retain RC1 inputs.");
            form.Close();
        });
        Check("RC1 session saves retain ammo across later currency edits and reject failed encryption without source writes", () =>
        {
            foreach (bool encrypted in new[] { false, true })
            {
                string folder = Fixture(root, "NPEA00385");
                File.WriteAllBytes(Path.Combine(folder, "USR-DATA"), Rc1AmmoFixture());
                var original = Snapshot(folder);
                var tools = new FakeTools { FailEncrypt = encrypted };
                using var session = SaveSession.Open(folder, tools, decrypted: !encrypted, backupRoot: Path.Combine(root, "rc1-ammo-backups"));
                var edits = new Dictionary<string, decimal> { ["rc1_ammo_10"] = 40 };
                if (encrypted)
                {
                    Throws<InvalidOperationException>(() => session.Save(123, 0, Path.Combine(root, "rc1-ammo-backups"), edits));
                    Same(original, Snapshot(folder));
                    Equal(20, Rc1SaveEditing.Fields(session.ReadInspectionData(), "NPEA00385").Single(field => field.Id == 10).Current);
                    continue;
                }
                string backup = session.Save(123, 0, Path.Combine(root, "rc1-ammo-backups"), edits); Same(original, Snapshot(backup));
                session.Save(456, 0, Path.Combine(root, "rc1-ammo-backups"));
                using var reopened = SaveSession.Open(folder, tools, decrypted: true, backupRoot: Path.Combine(root, "rc1-ammo-backups"));
                Equal(456, reopened.Bolts);
                Equal(40, Rc1SaveEditing.Fields(reopened.ReadInspectionData(), "NPEA00385").Single(field => field.Id == 10).Current);
            }
        });
    }

    private static void Rc1AmmoReferenceChecks(string root, string source)
    {
        Check("Actual RC1 save refills owned ammo on a copy, preserves other bytes and retains edits through reopening", () =>
        {
            var original = Snapshot(source);
            string folder = Path.Combine(root, "RC1 actual ammo copy"); Directory.CreateDirectory(folder);
            foreach (string path in Directory.GetFiles(source)) File.Copy(path, Path.Combine(folder, Path.GetFileName(path)));
            var tools = new FakeTools { FailDecrypt = true, FailEncrypt = true };
            using var session = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-actual-ammo-backups"));
            var fields = Rc1SaveEditing.Fields(session.ReadInspectionData(), session.Metadata.Region);
            True(fields.Count > 0, "The supplied save must have eligible owned ammo.");
            var edits = fields.ToDictionary(field => field.Key, field => (decimal)field.Maximum);
            byte[] expected = original["USR-DATA"].ToArray();
            foreach (var field in fields) BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(field.Offset), field.Maximum);
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(12), uint.MaxValue);
            string backup = session.Save(session.Bolts, session.Raritanium, Path.Combine(root, "rc1-actual-ammo-backups"), edits);
            Same(original, Snapshot(backup));
            True(expected.SequenceEqual(File.ReadAllBytes(Path.Combine(folder, "USR-DATA"))), "Only ammo words and the player checksum may change.");
            session.Save(session.Bolts, session.Raritanium, Path.Combine(root, "rc1-actual-ammo-backups"));
            using var reopened = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-actual-ammo-backups"));
            foreach (var field in Rc1SaveEditing.Fields(reopened.ReadInspectionData(), reopened.Metadata.Region)) Equal(field.Maximum, field.Current);
            foreach (string name in original.Keys.Where(name => name != "USR-DATA"))
                True(original[name].SequenceEqual(File.ReadAllBytes(Path.Combine(folder, name))), "Unrelated file changed: " + name);
            Same(original, Snapshot(source)); Equal(0, tools.CryptoCalls);
            Console.WriteLine($"  Refilled {fields.Count} owned weapon(s); original source unchanged.");
        });
    }
}
