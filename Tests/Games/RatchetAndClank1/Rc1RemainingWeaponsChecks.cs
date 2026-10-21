using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static byte[] Rc1RemainingWeaponsExpected(byte[] original, bool saved = false)
    {
        byte[] expected = original.ToArray();
        // Independent expectations for the supplied start-of-game baseline:
        // two flags per item, RYNO ammo, then first free quick-select slots.
        foreach (int offset in new[] { 0x1C1, 0x1F1, 0x1CD, 0x1FD, 0x1CF, 0x1FF }) expected[offset] = 1;
        BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x178), 25);
        BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x230), 9);
        BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x234), 21);
        BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x238), 23);
        if (saved) BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(12), uint.MaxValue);
        return expected;
    }

    private static void Rc1RemainingWeaponsChecks(string root)
    {
        Check("Suck Cannon, Morph-o-Ray and RYNO grants change only their shared saved-state fields", () =>
        {
            byte[] data = Rc1GrantFixture(), original = data.ToArray();
            var requests = Rc1Edits(("rc1_grant_9", 1), ("rc1_grant_21", 1), ("rc1_grant_23", 1));
            byte[] edited = Rc1SaveEditing.Apply(data, "NPEA00385", requests);
            True(Rc1RemainingWeaponsExpected(data).SequenceEqual(edited), "The new grants must change exactly the independent expected fields.");
            True(data.AsSpan(0x218, 12).SequenceEqual(edited.AsSpan(0x218, 12)), "These three IDs are absent from the acquisition list table.");
            True(original.SequenceEqual(data), "Granting must leave the input untouched.");
            byte[] noOp = Rc1SaveEditing.Apply(edited, "NPEA00385", requests);
            True(edited.SequenceEqual(noOp), "Existing weapons must not be refilled or assigned twice.");
            Equal(25, Rc1SaveEditing.Fields(edited, "NPEA00385").Single(field => field.Id == 23).Current);
            foreach (int id in new[] { 9, 21, 23 })
            {
                byte[] invalid = data.ToArray(); invalid[0x1E8 + id] = 2;
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(invalid, "NPEA00385", requests));
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_grant_" + id, 0.5m))));
                var malformedAmmo = data.ToArray();
                BinaryPrimitives.WriteUInt32BigEndian(malformedAmmo.AsSpan(0x11C + id * 4), uint.MaxValue);
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(malformedAmmo, "NPEA00385", requests));
            }
            // None of these grants needs acquisition-list capacity. A full,
            // opaque list and a full wheel must be preserved without blocking them.
            data.AsSpan(0x218, 12).Fill(0xEE);
            for (int slot = 0; slot < 8; slot++) BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x22C + 4 * slot), 0xFFFF0000u + (uint)slot);
            byte[] full = Rc1SaveEditing.Apply(data, "NPEA00385", requests);
            True(data.AsSpan(0x218, 44).SequenceEqual(full.AsSpan(0x218, 44)), "Full acquisition and quick-select banks must remain intact.");
        });
        Check("All three remaining grants stage, cancel, save and become owned ammo/quick-select choices", () =>
        {
            using var form = new Form { ClientSize = new Size(1050, 920), ShowInTaskbar = false, AutoScroll = true,
                Font = new Font("Segoe UI", 11F) };
            using var editor = new Rc1SaveEditingControl(); form.Controls.Add(editor);
            byte[] data = Rc1GrantFixture(); editor.LoadSnapshot(data, "NPEA00385");
            form.Show(); Application.DoEvents();
            var category = editor.Controls.Find("Rc1EditCategory", true).Cast<ComboBox>().Single(); category.SelectedItem = "Weapon unlocks";
            foreach (int id in new[] { 9, 21, 23 })
            {
                var grant = editor.Controls.Find("Rc1Edit_rc1_grant_" + id, true).Cast<CheckBox>().Single();
                True(grant.Enabled && !grant.Checked, "A new grant must be selectable: " + id);
                grant.Checked = true; Equal(1m, editor.PendingEdits["rc1_grant_" + id]);
                grant.Checked = false; True(!editor.PendingEdits.ContainsKey("rc1_grant_" + id), "Cancelling must clear the request.");
                grant.Checked = true;
            }
            Application.DoEvents();
            string preview = Path.GetFullPath(Path.Combine("artifacts", "rc1-all-weapons.png")); Directory.CreateDirectory(Path.GetDirectoryName(preview));
            using (var bitmap = new Bitmap(form.Width, form.Height)) { form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, bitmap.Size)); bitmap.Save(preview); }
            string folder = Fixture(root, "NPEA00385"); File.WriteAllBytes(Path.Combine(folder, "USR-DATA"), data);
            var original = Snapshot(folder);
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "rc1-remaining-backups"));
            string backup = session.Save(0, 0, Path.Combine(root, "rc1-remaining-backups"), editor.PendingEdits); Same(original, Snapshot(backup));
            session.Save(7, 0, Path.Combine(root, "rc1-remaining-backups"));
            using var reopened = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "rc1-remaining-backups"));
            Equal(7, reopened.Bolts);
            editor.LoadSnapshot(reopened.ReadInspectionData(), "NPEA00385");
            category = editor.Controls.Find("Rc1EditCategory", true).Cast<ComboBox>().Single(); category.SelectedItem = "Weapon unlocks";
            foreach (int id in new[] { 9, 21, 23 })
            {
                var grant = editor.Controls.Find("Rc1Edit_rc1_grant_" + id, true).Cast<CheckBox>().Single();
                True(grant.Checked && !grant.Enabled, "Saved weapons must show owned without re-granting.");
            }
            category.SelectedItem = "Weapon ammo";
            var ryno = editor.Controls.Find("Rc1Edit_rc1_ammo_23", true).Cast<NumericTextBox>().Single();
            Equal(25m, ryno.Value); Equal(50m, ryno.Maximum);
            category.SelectedItem = "Quick select";
            var slots = editor.Controls.Find("Rc1Edit_rc1_quick_7", true).Cast<ComboBox>().Single();
            foreach (uint id in new uint[] { 9, 21, 23 }) True(slots.Items.Cast<Rc1QuickOption>().Any(option => option.Value == id), "Newly owned weapon must be assignable.");
            True(!editor.HasChanges, "Browsing a saved grant must stay clean.");
            form.Close();
        });
    }

    private static void Rc1RemainingWeaponsReferenceChecks(string root, string source)
    {
        Check("Actual RC1 copy gains all three remaining weapons with exact byte preservation and verified reopening", () =>
        {
            var original = Snapshot(source); string folder = Path.Combine(root, "RC1 remaining weapons reference"); Directory.CreateDirectory(folder);
            foreach (string path in Directory.GetFiles(source)) File.Copy(path, Path.Combine(folder, Path.GetFileName(path)));
            var tools = new FakeTools { FailDecrypt = true, FailEncrypt = true };
            using var session = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-remaining-reference-backups"));
            byte[] expected = Rc1RemainingWeaponsExpected(original["USR-DATA"], saved: true);
            string backup = session.Save(session.Bolts, 0, Path.Combine(root, "rc1-remaining-reference-backups"),
                Rc1Edits(("rc1_grant_9", 1), ("rc1_grant_21", 1), ("rc1_grant_23", 1))); Same(original, Snapshot(backup));
            True(expected.SequenceEqual(File.ReadAllBytes(Path.Combine(folder, "USR-DATA"))), "Only the documented grant, slot and checksum bytes may change.");
            using var reopened = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-remaining-reference-backups"));
            foreach (int id in new[] { 9, 21, 23 })
                True(Rc1WeaponEditing.Grants(reopened.ReadInspectionData(), "NPEA00385").Single(field => field.Weapon.Id == id).Owned, "The new weapon must survive reopening.");
            Equal(25, Rc1SaveEditing.Fields(reopened.ReadInspectionData(), "NPEA00385").Single(field => field.Id == 23).Current);
            foreach (string name in original.Keys.Where(name => name != "USR-DATA"))
                True(original[name].SequenceEqual(File.ReadAllBytes(Path.Combine(folder, name))), "Unrelated file changed: " + name);
            Same(original, Snapshot(source)); Equal(0, tools.CryptoCalls);
        });
    }
}
