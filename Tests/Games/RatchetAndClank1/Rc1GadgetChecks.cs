using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static readonly int[] Rc1GadgetIds = { 12, 22, 26, 27, 31, 32, 33, 34, 35 };

    private static byte[] Rc1GadgetsExpected(byte[] original, params int[] ids)
    {
        byte[] expected = original.ToArray();
        foreach (int id in ids.Order())
        {
            if (original[0x1B8 + id] == 1) continue;
            expected[0x1B8 + id] = expected[0x1E8 + id] = 1;
            if (id >= 33) continue; // Three passive items do not enter quick select.
            var slots = Enumerable.Range(0, 8).Select(slot => 0x22C + slot * 4).ToArray();
            if (slots.Any(offset => BinaryPrimitives.ReadInt32BigEndian(expected.AsSpan(offset)) == id)) continue;
            int empty = Array.FindIndex(slots, offset => BinaryPrimitives.ReadInt32BigEndian(expected.AsSpan(offset)) == 0);
            if (empty >= 0) BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(slots[empty]), id);
        }
        return expected;
    }

    private static void Rc1GadgetChecks(string root)
    {
        Check("RC1 nine gadget grants preserve ammo and acquisition data and assign only handheld gadgets", () =>
        {
            True(Rc1GadgetIds.SequenceEqual(Rc1Research.Gadgets.Select(item => item.Id).Order()), "Only the nine traced grants may be exposed.");
            byte[] data = Rc1GrantFixture();
            foreach (int id in Rc1GadgetIds) BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x11C + id * 4), 0xABCD0000u + (uint)id);
            data.AsSpan(0x218, 12).Fill(0xEE); // A full acquisition list cannot block these grants.
            byte[] original = data.ToArray();
            foreach (int id in Rc1GadgetIds)
            {
                byte[] expected = data.ToArray(); expected[0x1B8 + id] = expected[0x1E8 + id] = 1;
                if (id < 33) BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x230), id);
                byte[] edited = Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_gadget_" + id, 1)));
                True(expected.SequenceEqual(edited), "Only the two flags and a handheld's first free slot may change: " + id);
                True(edited.SequenceEqual(Rc1SaveEditing.Apply(edited, "NPEA00385", Rc1Edits(("rc1_gadget_" + id, 1)))), "Repeated grants must preserve all bytes.");
            }
            var all = Rc1GadgetIds.ToDictionary(id => "rc1_gadget_" + id, _ => 1m);
            byte[] batch = Rc1SaveEditing.Apply(data, "NPEA00385", all);
            True(Rc1GadgetsExpected(data, Rc1GadgetIds).SequenceEqual(batch), "Combined grants must have exactly the documented writes.");
            True(batch.SequenceEqual(Rc1SaveEditing.Apply(data, "NPEA00385", all.Reverse().ToDictionary(edit => edit.Key, edit => edit.Value))), "Insertion order cannot change slot allocation.");
            True(original.SequenceEqual(data), "Granting must leave the caller's array unchanged.");
            for (int slot = 0; slot < 8; slot++) BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x22C + slot * 4), 900 + slot);
            byte[] full = Rc1SaveEditing.Apply(data, "NPEA00385", all);
            True(data.AsSpan(0x22C, 32).SequenceEqual(full.AsSpan(0x22C, 32)), "A full wheel must remain unchanged.");
            data.AsSpan(0x22C, 32).Clear(); BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x238), 12);
            byte[] retained = Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_gadget_12", 1)));
            True(data.AsSpan(0x22C, 32).SequenceEqual(retained.AsSpan(0x22C, 32)), "A retained matching slot must not be duplicated.");
        });
        Check("RC1 gadget guards reject uncertain ownership, removals and unsupported items atomically", () =>
        {
            byte[] data = Rc1GrantFixture(), original = data.ToArray();
            foreach (int id in new[] { 0, 2, 8, 10, 28, 29, 30, 36, 999 })
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_gadget_" + id, 1))));
            foreach (decimal value in new[] { -1m, 0.5m, 2m, decimal.MaxValue })
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_gadget_12", value))));
            foreach (int id in Rc1GadgetIds)
            {
                foreach (byte flag in new byte[] { 1, 2, 0xFF })
                {
                    byte[] invalid = data.ToArray(); invalid[0x1E8 + id] = flag;
                    Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(invalid, "NPEA00385", Rc1Edits(("rc1_gold_10", 1), ("rc1_ammo_10", 40), ("rc1_grant_15", 1), ("rc1_gadget_" + id, 1))));
                    True(invalid[0x11E2] == 0 && invalid[0x1C7] == 0, "Rejected batches cannot modify other categories.");
                }
                byte[] owned = data.ToArray(); owned[0x1B8 + id] = 1;
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(owned, "NPEA00385", Rc1Edits(("rc1_gadget_" + id, 0))));
                owned[0x1B8 + id] = 2;
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(owned, "NPEA00385", Rc1Edits(("rc1_gadget_" + id, 1))));
            }
            foreach (string region in new[] { "NPUA80643", "NPJA40001", "NPEA00386" })
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, region, Rc1Edits(("rc1_gadget_12", 1))));
            True(original.SequenceEqual(data), "All failure cases must leave the baseline untouched.");
        });
        Check("RC1 handheld gadget quick select composes with combat grants and preserves passive assignments", () =>
        {
            byte[] data = Rc1GrantFixture();
            var edits = Rc1Edits(("rc1_grant_15", 1), ("rc1_gadget_12", 1), ("rc1_gadget_33", 1), ("rc1_ammo_10", 40), ("rc1_gold_10", 1), ("rc1_quick_0", 0), ("rc1_quick_3", 10));
            byte[] combined = Rc1SaveEditing.Apply(data, "NPEA00385", edits);
            Equal(15, BinaryPrimitives.ReadInt32BigEndian(combined.AsSpan(0x22C)));
            Equal(12, BinaryPrimitives.ReadInt32BigEndian(combined.AsSpan(0x230)));
            Equal(10, BinaryPrimitives.ReadInt32BigEndian(combined.AsSpan(0x238)));
            Equal(1, (int)combined[0x11E2]); Equal(40, BinaryPrimitives.ReadInt32BigEndian(combined.AsSpan(0x144)));
            True(combined.SequenceEqual(Rc1SaveEditing.Apply(data, "NPEA00385", edits.Reverse().ToDictionary(edit => edit.Key, edit => edit.Value))), "Mixed batches must be deterministic.");
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_gadget_12", 1), ("rc1_quick_7", 12))));
            byte[] moved = Rc1SaveEditing.Apply(combined, "NPEA00385", Rc1Edits(("rc1_quick_1", 0), ("rc1_quick_7", 12)));
            Equal(12, BinaryPrimitives.ReadInt32BigEndian(moved.AsSpan(0x248)));
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(combined, "NPEA00385", Rc1Edits(("rc1_quick_7", 12))));
            foreach (int id in Rc1GadgetIds)
                True(Rc1WeaponEditing.QuickSelect(Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_gadget_" + id, 1))), "NPEA00385")[7].Options.Any(option => option.Value == id) == (id < 33), "Only the six handheld gadgets may become new choices.");
            BinaryPrimitives.WriteInt32BigEndian(combined.AsSpan(0x234), 33);
            True(combined.SequenceEqual(Rc1SaveEditing.Apply(combined, "NPEA00385", Rc1Edits(("rc1_quick_2", 33)))), "An existing passive assignment can be preserved.");
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(combined, "NPEA00385", Rc1Edits(("rc1_quick_7", 33))));
        });
        Check("RC1 gadget UI stages, cancels and saves nine grants with backups and refreshed slot choices", () =>
        {
            using var form = new Form { ClientSize = new Size(1000, 680), ShowInTaskbar = false, AutoScroll = true, Font = new Font("Segoe UI", 11F) };
            using var editor = new Rc1SaveEditingControl(); form.Controls.Add(editor);
            byte[] data = Rc1GrantFixture(); editor.LoadSnapshot(data, "NPEA00385"); form.Show(); Application.DoEvents();
            var category = editor.Controls.Find("Rc1EditCategory", true).Cast<ComboBox>().Single(); Alphabetical(category);
            category.SelectedItem = "Gadget unlocks";
            foreach (int id in Rc1GadgetIds)
            {
                var check = editor.Controls.Find("Rc1Edit_rc1_gadget_" + id, true).Cast<CheckBox>().Single();
                check.Checked = true; Equal(1m, editor.PendingEdits["rc1_gadget_" + id]);
                check.Checked = false; True(!editor.PendingEdits.ContainsKey("rc1_gadget_" + id), "Cancellation must clear the grant.");
            }
            category.SelectedItem = "Weapon ammo";
            var ammo = editor.Controls.Find("Rc1Edit_rc1_ammo_10", true).Cast<NumericTextBox>().Single(); ammo.Text = "bad";
            category.SelectedItem = "Gadget unlocks";
            var first = editor.Controls.Find("Rc1Edit_rc1_gadget_12", true).Cast<CheckBox>().Single(); first.Checked = true;
            True(!first.Checked && editor.HasInvalidInputs && !editor.ValidateInputs(), "Hidden invalid numeric input must block grants and saving.");
            ammo.Value = 40; category.SelectedItem = "Gadget unlocks";
            foreach (int id in Rc1GadgetIds) editor.Controls.Find("Rc1Edit_rc1_gadget_" + id, true).Cast<CheckBox>().Single().Checked = true;
            Application.DoEvents();
            using (var bitmap = new Bitmap(form.Width, form.Height)) { form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, bitmap.Size)); bitmap.Save(Path.GetFullPath("artifacts/rc1-gadgets.png")); }
            string folder = Fixture(root, "NPEA00385"); File.WriteAllBytes(Path.Combine(folder, "USR-DATA"), data);
            var original = Snapshot(folder);
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "rc1-gadget-backups"));
            string backup = session.Save(0, 0, Path.Combine(root, "rc1-gadget-backups"), editor.PendingEdits); Same(original, Snapshot(backup));
            session.Save(123, 0, Path.Combine(root, "rc1-gadget-backups"));
            using var reopened = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "rc1-gadget-backups")); Equal(123, reopened.Bolts);
            editor.LoadSnapshot(reopened.ReadInspectionData(), "NPEA00385");
            foreach (int id in Rc1GadgetIds)
            {
                var check = editor.Controls.Find("Rc1Edit_rc1_gadget_" + id, true).Cast<CheckBox>().Single();
                True(check.Checked && !check.Enabled, "Committed grants must show owned and disabled.");
            }
            var choices = editor.Controls.Find("Rc1Edit_rc1_quick_7", true).Cast<ComboBox>().Single(); Alphabetical(choices);
            foreach (int id in Rc1GadgetIds) True(choices.Items.Cast<Rc1QuickOption>().Any(option => option.Value == id) == (id < 33), "Only handheld gadget choices should refresh after saving.");
            True(!editor.HasChanges, "Refreshed snapshot must have no staged edits.");
            editor.LoadSnapshot(data, "NPUA80643"); Equal(0, editor.Controls.Find("Rc1Edit_rc1_gadget_12", true).Length);
            form.Close();
            string encryptedFolder = Fixture(root, "NPEA00385"); File.WriteAllBytes(Path.Combine(encryptedFolder, "USR-DATA"), data);
            var encryptedOriginal = Snapshot(encryptedFolder);
            using var failed = SaveSession.Open(encryptedFolder, new FakeTools { FailEncrypt = true }, decrypted: false, backupRoot: Path.Combine(root, "rc1-gadget-failed-backups"));
            Throws<InvalidOperationException>(() => failed.Save(0, 0, Path.Combine(root, "rc1-gadget-failed-backups"), Rc1Edits(("rc1_gadget_12", 1))));
            Same(encryptedOriginal, Snapshot(encryptedFolder));
            True(!Rc1GadgetEditing.Grants(failed.ReadInspectionData(), "NPEA00385").Single(field => field.Gadget.Id == 12).Owned, "Failed saves must retain the session baseline.");
        });
    }

    private static void Rc1GadgetReferenceChecks(string root, string source)
    {
        Check("Actual RC1 save copy gains nine gadgets with exact flags, bounded slots and untouched source", () =>
        {
            var original = Snapshot(source); string folder = Path.Combine(root, "RC1 gadgets reference"); Directory.CreateDirectory(folder);
            foreach (string path in Directory.GetFiles(source)) File.Copy(path, Path.Combine(folder, Path.GetFileName(path)));
            var tools = new FakeTools { FailDecrypt = true, FailEncrypt = true };
            using var session = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-gadgets-reference-backups"));
            byte[] expected = Rc1GadgetsExpected(original["USR-DATA"], Rc1GadgetIds); expected.AsSpan(12, 4).Fill(0xFF);
            string backup = session.Save(session.Bolts, 0, Path.Combine(root, "rc1-gadgets-reference-backups"), Rc1GadgetIds.ToDictionary(id => "rc1_gadget_" + id, _ => 1m));
            Same(original, Snapshot(backup)); True(expected.SequenceEqual(File.ReadAllBytes(Path.Combine(folder, "USR-DATA"))), "Only gadget flags, available quick slots and player checksum may change.");
            using var reopened = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-gadgets-reference-backups"));
            True(Rc1GadgetEditing.Grants(reopened.ReadInspectionData(), "NPEA00385").All(field => field.Owned), "Grants must survive reopening.");
            foreach (string name in original.Keys.Where(name => name != "USR-DATA")) True(original[name].SequenceEqual(File.ReadAllBytes(Path.Combine(folder, name))), "Unrelated file changed: " + name);
            Same(original, Snapshot(source)); Equal(0, tools.CryptoCalls);
        });
    }
}
