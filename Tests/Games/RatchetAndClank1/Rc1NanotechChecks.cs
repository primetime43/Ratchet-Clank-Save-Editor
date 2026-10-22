using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static byte[] Rc1NanotechFixture(int level = 0)
    {
        byte[] data = Rc1GoldBoltFixture();
        data[0x5C] = (byte)(level > 0 ? 1 : 0); data[0x5D] = (byte)(level == 2 ? 1 : 0);
        BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x254), new[] { 4, 5, 8 }[level]);
        return data;
    }

    private static void Rc1NanotechChecks(string root)
    {
        Check("RC1 nanotech promotions couple both upgrade flags and capacity with exact byte preservation", () =>
        {
            Equal(0x5C, Rc1Research.Nanotech.PremiumOffset); Equal(0x5D, Rc1Research.Nanotech.UltraOffset);
            Equal(0x254, Rc1Research.Nanotech.CapacityOffset);
            for (int baseline = 0; baseline <= 2; baseline++)
            {
                byte[] data = Rc1NanotechFixture(baseline), original = data.ToArray();
                Equal(baseline, Rc1NanotechEditing.State(data, "NPEA00385").Level);
                for (int target = baseline; target <= 2; target++)
                {
                    byte[] expected = data.ToArray();
                    expected[0x5C] = (byte)(target > 0 ? 1 : 0); expected[0x5D] = (byte)(target == 2 ? 1 : 0);
                    BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x254), new[] { 4, 5, 8 }[target]);
                    byte[] edited = Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits((Rc1NanotechEditing.Key, target)));
                    True(expected.SequenceEqual(edited), "Only the two nanotech flags and capacity may change.");
                    True(edited.SequenceEqual(Rc1SaveEditing.Apply(edited, "NPEA00385", Rc1Edits((Rc1NanotechEditing.Key, target)))), "Repeated tiers must be no-ops.");
                }
                True(original.SequenceEqual(data), "Source arrays must remain detached.");
            }
            byte[] source = Rc1NanotechFixture();
            var mixed = Rc1Edits((Rc1NanotechEditing.Key, 2), ("rc1_ammo_10", 40), ("rc1_grant_15", 1),
                ("rc1_gadget_12", 1), ("rc1_equipment_2", 1), ("rc1_gold_10", 1), ("rc1_bolt_1_0", 1));
            byte[] all = Rc1SaveEditing.Apply(source, "NPEA00385", mixed);
            byte[] sequential = Rc1SaveEditing.Apply(source, "NPEA00385", Rc1Edits((Rc1NanotechEditing.Key, 1)));
            foreach (var edit in mixed) sequential = Rc1SaveEditing.Apply(sequential, "NPEA00385", Rc1Edits((edit.Key, edit.Value)));
            True(all.SequenceEqual(sequential), "Direct Ultra and mixed batches must match independent promotions and inventory edits.");
            True(all.SequenceEqual(Rc1SaveEditing.Apply(source, "NPEA00385", mixed.Reverse().ToDictionary(edit => edit.Key, edit => edit.Value))), "Request order must not matter.");
        });
        Check("RC1 nanotech rejects inconsistent saves, unknown tiers and downgrades without blocking other fields", () =>
        {
            byte[] data = Rc1NanotechFixture(), original = data.ToArray();
            foreach (decimal value in new[] { -1m, 0.5m, 1.5m, 3m, decimal.MaxValue })
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits((Rc1NanotechEditing.Key, value))));
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_nanotech_health", 8))));
            for (int baseline = 1; baseline <= 2; baseline++)
                for (int target = 0; target < baseline; target++)
                    Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(Rc1NanotechFixture(baseline), "NPEA00385", Rc1Edits((Rc1NanotechEditing.Key, target))));
            foreach (var mutation in new[] { (0x5C, (byte)2), (0x5D, (byte)0xFF), (0x5D, (byte)1),
                (0x257, (byte)0), (0x257, (byte)3), (0x257, (byte)5), (0x257, (byte)8), (0x254, (byte)0x80) })
            {
                byte[] broken = data.ToArray(); broken[mutation.Item1] = mutation.Item2; byte[] before = broken.ToArray();
                True(Rc1NanotechEditing.State(broken, "NPEA00385") == null, "Unknown/inconsistent nanotech must be unavailable.");
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(broken, "NPEA00385", Rc1Edits(("rc1_ammo_10", 40), (Rc1NanotechEditing.Key, 2))));
                True(before.SequenceEqual(broken), "Invalid mixed batches must leave the source intact.");
                byte[] ammo = Rc1SaveEditing.Apply(broken, "NPEA00385", Rc1Edits(("rc1_ammo_10", 40)));
                before.AsSpan(0x144, 4).CopyTo(ammo.AsSpan(0x144, 4));
                True(before.SequenceEqual(ammo), "Other edits must preserve unrecognized nanotech state.");
            }
            foreach (string region in new[] { "NPUA80643", "NPJA40001" })
            {
                True(Rc1NanotechEditing.State(data, region) == null, "Other regions must stay unavailable.");
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, region, Rc1Edits((Rc1NanotechEditing.Key, 2))));
            }
            byte[] malformed = data.ToArray(); malformed[0x24C] ^= 1;
            True(Rc1NanotechEditing.State(malformed, "NPEA00385") == null, "Changed record framing must be rejected.");
            True(original.SequenceEqual(data), "All rejected requests must preserve the original.");
        });
        Check("RC1 nanotech UI stages, cancels, validates hidden ammo and retains upgrades across saves", () =>
        {
            using var form = new Form { ClientSize = new Size(1000, 680), ShowInTaskbar = false, AutoScroll = true, Font = new Font("Segoe UI", 11F) };
            using var editor = new Rc1SaveEditingControl(); form.Controls.Add(editor);
            byte[] data = Rc1NanotechFixture(); editor.LoadSnapshot(data, "NPEA00385"); form.Show(); Application.DoEvents();
            var category = editor.Controls.Find("Rc1EditCategory", true).Cast<ComboBox>().Single(); Alphabetical(category);
            category.SelectedItem = "Nanotech";
            var tiers = editor.Controls.Find("Rc1Edit_rc1_nanotech_level", true).Cast<ComboBox>().Single(); Equal(3, tiers.Items.Count);
            tiers.SelectedIndex = 1; Equal(1m, editor.PendingEdits[Rc1NanotechEditing.Key]);
            tiers.SelectedIndex = 0; True(!editor.HasChanges, "Returning to the baseline must cancel the promotion.");
            tiers.SelectedIndex = 2; Equal(2m, editor.PendingEdits[Rc1NanotechEditing.Key]);
            category.SelectedItem = "Weapon ammo";
            var ammo = editor.Controls.Find("Rc1Edit_rc1_ammo_10", true).Cast<NumericTextBox>().Single(); ammo.Text = "invalid";
            category.SelectedItem = "Nanotech"; tiers.SelectedIndex = 1;
            Equal(2, tiers.SelectedIndex); True(editor.HasInvalidInputs && !editor.ValidateInputs(), "Hidden invalid ammo must block staging and saving.");
            ammo.Value = 40; category.SelectedItem = "Nanotech"; Equal(2m, editor.PendingEdits[Rc1NanotechEditing.Key]);
            Application.DoEvents();
            string preview = Path.GetFullPath(Path.Combine("artifacts", "rc1-nanotech.png")); Directory.CreateDirectory(Path.GetDirectoryName(preview));
            using (var bitmap = new Bitmap(form.Width, form.Height)) { form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, bitmap.Size)); bitmap.Save(preview); }
            string folder = Fixture(root, "NPEA00385"), backups = Path.Combine(root, "rc1-nanotech-backups");
            File.WriteAllBytes(Path.Combine(folder, "USR-DATA"), data); var original = Snapshot(folder);
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: backups);
            string backup = session.Save(0, 0, backups, editor.PendingEdits); Same(original, Snapshot(backup));
            session.Save(123, 0, backups);
            using var reopened = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: backups);
            Equal(123, reopened.Bolts); Equal(2, Rc1NanotechEditing.State(reopened.ReadInspectionData(), "NPEA00385").Level);
            Equal(40, Rc1SaveEditing.Fields(reopened.ReadInspectionData(), "NPEA00385").Single(field => field.Id == 10).Current);
            editor.LoadSnapshot(reopened.ReadInspectionData(), "NPEA00385");
            tiers = editor.Controls.Find("Rc1Edit_rc1_nanotech_level", true).Cast<ComboBox>().Single();
            Equal(1, tiers.Items.Count); True(!tiers.Enabled && !editor.HasChanges, "Installed Ultra must display without a downgrade option.");
            editor.LoadSnapshot(Rc1NanotechFixture(1), "NPEA00385");
            Equal(2, editor.Controls.Find("Rc1Edit_rc1_nanotech_level", true).Cast<ComboBox>().Single().Items.Count);
            data[0x5D] = 1; editor.LoadSnapshot(data, "NPEA00385");
            True(editor.Controls.Find("Rc1Edit_rc1_nanotech_level", true).Length == 0, "Inconsistent state must have no selector.");
            editor.LoadSnapshot(data, "NPUA80643"); True(!editor.HasChanges, "Changing regions must clear pending state.");
            form.Close();
        });
    }

    private static void Rc1NanotechReferenceChecks(string root, string source)
    {
        Check("Actual RC1 save copy gains Ultra and Premium with exact preservation, backup and reopening", () =>
        {
            var original = Snapshot(source);
            string folder = Path.Combine(root, "RC1 nanotech reference"), backups = Path.Combine(root, "rc1-nanotech-reference-backups"); Directory.CreateDirectory(folder);
            foreach (string path in Directory.GetFiles(source)) File.Copy(path, Path.Combine(folder, Path.GetFileName(path)));
            var tools = new FakeTools { FailDecrypt = true, FailEncrypt = true };
            using var session = SaveSession.Open(folder, tools, backupRoot: backups);
            byte[] expected = original["USR-DATA"].ToArray(); expected[0x5C] = expected[0x5D] = 1;
            BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x254), 8); expected.AsSpan(12, 4).Fill(0xFF);
            string backup = session.Save(session.Bolts, 0, backups, Rc1Edits((Rc1NanotechEditing.Key, 2))); Same(original, Snapshot(backup));
            True(expected.SequenceEqual(File.ReadAllBytes(Path.Combine(folder, "USR-DATA"))), "Only nanotech flags, capacity and player checksum may change.");
            using var reopened = SaveSession.Open(folder, tools, backupRoot: backups);
            Equal(8, Rc1NanotechEditing.State(reopened.ReadInspectionData(), "NPEA00385").Capacity);
            foreach (string name in original.Keys.Where(name => name != "USR-DATA"))
                True(original[name].SequenceEqual(File.ReadAllBytes(Path.Combine(folder, name))), "Unrelated save file changed: " + name);
            Same(original, Snapshot(source)); Equal(0, tools.CryptoCalls);
        });
    }
}
