using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static readonly int[] Rc1EquipmentIds = { 2, 3, 4, 5, 6, 7, 28, 29, 30 };

    private static byte[] Rc1EquipmentExpected(byte[] original)
    {
        byte[] expected = original.ToArray();
        foreach (int id in Rc1EquipmentIds)
        {
            if (original[0x1B8 + id] == 1) continue;
            expected[0x1B8 + id] = expected[0x1E8 + id] = 1;
        }
        return expected;
    }

    private static void Rc1EquipmentChecks(string root)
    {
        Check("RC1 nine equipment grants change only ownership and grant flags while preserving selected equipment", () =>
        {
            True(Rc1EquipmentIds.SequenceEqual(Rc1Research.Equipment.Select(item => item.Id).Order()), "Only the nine traced equipment IDs may be granted.");
            byte[] data = Rc1GrantFixture();
            data.AsSpan(0x218, 12).Fill(0xEE); // Full acquisition list.
            data.AsSpan(0x22C, 32).Fill(0xEE); // Opaque quick select; retain its record header.
            data.AsSpan(0x1214, 28).Fill(0x7F); // Saved equipment selections.
            data.AsSpan(0x1184, 4).Fill(0xFF); // Saved Thruster-Pack selection state.
            foreach (int id in Rc1EquipmentIds) BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x11C + id * 4), 0xABCD0000u + (uint)id);
            byte[] original = data.ToArray();
            foreach (int id in Rc1EquipmentIds)
            {
                byte[] expected = data.ToArray(); expected[0x1B8 + id] = expected[0x1E8 + id] = 1;
                byte[] edited = Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_equipment_" + id, 1)));
                True(expected.SequenceEqual(edited), "An equipment grant must change only two flags: " + id);
                True(edited.SequenceEqual(Rc1SaveEditing.Apply(edited, "NPEA00385", Rc1Edits(("rc1_equipment_" + id, 1)))), "A repeated grant must preserve all bytes.");
                edited[0x1E8 + id] = 0x7F;
                True(edited.SequenceEqual(Rc1SaveEditing.Apply(edited, "NPEA00385", Rc1Edits(("rc1_equipment_" + id, 1)))), "An owned item must not have its independent flag repaired.");
            }
            var all = Rc1EquipmentIds.ToDictionary(id => "rc1_equipment_" + id, _ => 1m);
            byte[] batch = Rc1SaveEditing.Apply(data, "NPEA00385", all);
            True(Rc1EquipmentExpected(data).SequenceEqual(batch), "All nine grants must preserve every unrelated byte.");
            True(batch.SequenceEqual(Rc1SaveEditing.Apply(data, "NPEA00385", all.Reverse().ToDictionary(edit => edit.Key, edit => edit.Value))), "Request order must not affect equipment grants.");
            True(original.SequenceEqual(data), "The source array must stay detached.");
        });
        Check("RC1 equipment rejects uncertain ownership, removals, invalid values and unsupported regions atomically", () =>
        {
            byte[] data = Rc1GrantFixture(), original = data.ToArray();
            foreach (int id in new[] { 0, 1, 8, 9, 12, 27, 31, 35, 36, 999 })
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_equipment_" + id, 1))));
            foreach (int id in Rc1EquipmentIds)
            {
                foreach (decimal value in new[] { -1m, 0.5m, 2m, decimal.MaxValue })
                    Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_equipment_" + id, value))));
                foreach (byte flag in new byte[] { 1, 2, 0xFF })
                {
                    byte[] invalid = data.ToArray(); invalid[0x1E8 + id] = flag; byte[] before = invalid.ToArray();
                    var edits = Rc1Edits(("rc1_ammo_10", 40), ("rc1_grant_15", 1), ("rc1_gadget_12", 1), ("rc1_gold_10", 1), ("rc1_equipment_" + id, 1));
                    Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(invalid, "NPEA00385", edits));
                    True(before.SequenceEqual(invalid), "Rejected mixed batches cannot modify the caller's array.");
                }
                byte[] owned = data.ToArray(); owned[0x1B8 + id] = 1;
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(owned, "NPEA00385", Rc1Edits(("rc1_equipment_" + id, 0))));
                foreach (byte flag in new byte[] { 2, 0xFF })
                {
                    owned[0x1B8 + id] = flag;
                    Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(owned, "NPEA00385", Rc1Edits(("rc1_equipment_" + id, 1))));
                }
            }
            foreach (string region in new[] { "NPUA80643", "NPJA40001", "NPEA00386" })
            {
                Equal(0, Rc1EquipmentEditing.Grants(data, region).Count);
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, region, Rc1Edits(("rc1_equipment_2", 1))));
            }
            byte[] malformed = data.ToArray(); malformed[0x120C] ^= 1;
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(malformed, "NPEA00385", Rc1Edits(("rc1_equipment_2", 1))));
            True(original.SequenceEqual(data), "All rejected calls must preserve the original.");
        });
        Check("RC1 equipment composes with other grants without entering quick select or changing progress", () =>
        {
            byte[] data = Rc1GrantFixture();
            var edits = Rc1Edits(("rc1_ammo_10", 40), ("rc1_grant_15", 1), ("rc1_gadget_12", 1), ("rc1_gold_10", 1), ("rc1_quick_0", 0), ("rc1_quick_3", 10));
            byte[] other = Rc1SaveEditing.Apply(data, "NPEA00385", edits);
            foreach (int id in Rc1EquipmentIds) edits.Add("rc1_equipment_" + id, 1);
            byte[] combined = Rc1SaveEditing.Apply(data, "NPEA00385", edits);
            True(Rc1EquipmentExpected(other).SequenceEqual(combined), "Equipment must compose without changing other staged fields.");
            True(combined.SequenceEqual(Rc1SaveEditing.Apply(data, "NPEA00385", edits.Reverse().ToDictionary(edit => edit.Key, edit => edit.Value))), "Mixed request order must not matter.");
            foreach (int id in Rc1EquipmentIds)
            {
                True(!Rc1WeaponEditing.QuickSelect(combined, "NPEA00385")[7].Options.Any(option => option.Value == id), "Equipment is not offered as a new quick-select choice.");
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(combined, "NPEA00385", Rc1Edits(("rc1_quick_7", id))));
            }
            BinaryPrimitives.WriteInt32BigEndian(combined.AsSpan(0x248), 28);
            True(combined.SequenceEqual(Rc1SaveEditing.Apply(combined, "NPEA00385", Rc1Edits(("rc1_quick_7", 28)))), "An existing equipment assignment can be preserved without normalization.");
        });
        Check("RC1 equipment UI stages, cancels and saves add-only grants with backups and failed-commit protection", () =>
        {
            using var form = new Form { ClientSize = new Size(1000, 680), ShowInTaskbar = false, AutoScroll = true, Font = new Font("Segoe UI", 11F) };
            using var editor = new Rc1SaveEditingControl(); form.Controls.Add(editor);
            byte[] data = Rc1GrantFixture(); editor.LoadSnapshot(data, "NPEA00385"); form.Show(); Application.DoEvents();
            var category = editor.Controls.Find("Rc1EditCategory", true).Cast<ComboBox>().Single(); Alphabetical(category); category.SelectedItem = "Equipment unlocks";
            foreach (int id in Rc1EquipmentIds)
            {
                var check = editor.Controls.Find("Rc1Edit_rc1_equipment_" + id, true).Cast<CheckBox>().Single();
                check.Checked = true; Equal(1m, editor.PendingEdits["rc1_equipment_" + id]);
                check.Checked = false; True(!editor.PendingEdits.ContainsKey("rc1_equipment_" + id), "Cancelling must clear the grant.");
            }
            category.SelectedItem = "Weapon ammo";
            var ammo = editor.Controls.Find("Rc1Edit_rc1_ammo_10", true).Cast<NumericTextBox>().Single(); ammo.Text = "bad";
            category.SelectedItem = "Equipment unlocks";
            var first = editor.Controls.Find("Rc1Edit_rc1_equipment_2", true).Cast<CheckBox>().Single(); first.Checked = true;
            True(!first.Checked && editor.HasInvalidInputs && !editor.ValidateInputs(), "Hidden invalid ammo must block staging and saving.");
            ammo.Value = 40; category.SelectedItem = "Equipment unlocks";
            foreach (int id in Rc1EquipmentIds) editor.Controls.Find("Rc1Edit_rc1_equipment_" + id, true).Cast<CheckBox>().Single().Checked = true;
            Application.DoEvents();
            using (var bitmap = new Bitmap(form.Width, form.Height)) { form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, bitmap.Size)); bitmap.Save(Path.GetFullPath("artifacts/rc1-equipment.png")); }
            string folder = Fixture(root, "NPEA00385"); File.WriteAllBytes(Path.Combine(folder, "USR-DATA"), data);
            var original = Snapshot(folder);
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "rc1-equipment-backups"));
            string backup = session.Save(0, 0, Path.Combine(root, "rc1-equipment-backups"), editor.PendingEdits); Same(original, Snapshot(backup));
            session.Save(123, 0, Path.Combine(root, "rc1-equipment-backups"));
            using var reopened = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "rc1-equipment-backups")); Equal(123, reopened.Bolts);
            editor.LoadSnapshot(reopened.ReadInspectionData(), "NPEA00385");
            foreach (int id in Rc1EquipmentIds)
            {
                var check = editor.Controls.Find("Rc1Edit_rc1_equipment_" + id, true).Cast<CheckBox>().Single();
                True(check.Checked && !check.Enabled, "Saved equipment must display as owned and disabled.");
            }
            True(!editor.HasChanges, "Reload must clear staged edits.");
            editor.LoadSnapshot(data, "NPUA80643"); Equal(0, editor.Controls.Find("Rc1Edit_rc1_equipment_2", true).Length); form.Close();
            string failedFolder = Fixture(root, "NPEA00385"); File.WriteAllBytes(Path.Combine(failedFolder, "USR-DATA"), data);
            var failedOriginal = Snapshot(failedFolder);
            using var failed = SaveSession.Open(failedFolder, new FakeTools { FailEncrypt = true }, decrypted: false, backupRoot: Path.Combine(root, "rc1-equipment-failed-backups"));
            Throws<InvalidOperationException>(() => failed.Save(0, 0, Path.Combine(root, "rc1-equipment-failed-backups"), Rc1Edits(("rc1_equipment_2", 1))));
            Same(failedOriginal, Snapshot(failedFolder));
            True(!Rc1EquipmentEditing.Grants(failed.ReadInspectionData(), "NPEA00385").Single(field => field.Equipment.Id == 2).Owned, "Failed saves must retain the old ownership baseline.");
        });
    }

    private static void Rc1EquipmentReferenceChecks(string root, string source)
    {
        Check("Actual RC1 save copy gains nine equipment items with exact preservation, backup and reopening", () =>
        {
            var original = Snapshot(source); string folder = Path.Combine(root, "RC1 equipment reference"); Directory.CreateDirectory(folder);
            foreach (string path in Directory.GetFiles(source)) File.Copy(path, Path.Combine(folder, Path.GetFileName(path)));
            var tools = new FakeTools { FailDecrypt = true, FailEncrypt = true };
            using var session = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-equipment-reference-backups"));
            byte[] expected = Rc1EquipmentExpected(original["USR-DATA"]); expected.AsSpan(12, 4).Fill(0xFF);
            string backup = session.Save(session.Bolts, 0, Path.Combine(root, "rc1-equipment-reference-backups"), Rc1EquipmentIds.ToDictionary(id => "rc1_equipment_" + id, _ => 1m));
            Same(original, Snapshot(backup)); True(expected.SequenceEqual(File.ReadAllBytes(Path.Combine(folder, "USR-DATA"))), "Only the equipment flags and player checksum may change.");
            using var reopened = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-equipment-reference-backups"));
            True(Rc1EquipmentEditing.Grants(reopened.ReadInspectionData(), "NPEA00385").All(field => field.Owned), "Equipment must survive reopening.");
            foreach (string name in original.Keys.Where(name => name != "USR-DATA")) True(original[name].SequenceEqual(File.ReadAllBytes(Path.Combine(folder, name))), "Unrelated file changed: " + name);
            Same(original, Snapshot(source)); Equal(0, tools.CryptoCalls);
        });
    }
}
