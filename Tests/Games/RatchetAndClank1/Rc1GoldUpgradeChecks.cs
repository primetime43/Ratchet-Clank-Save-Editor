using System;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static void Rc1GoldUpgradeChecks(string root)
    {
        int[] goldIds = { 9, 10, 11, 15, 16, 17, 19, 20, 21, 25 };
        Check("RC1 gold upgrades follow the ten-item vendor allowlist and change exactly one byte per owned weapon", () =>
        {
            True(goldIds.SequenceEqual(Rc1Research.GoldUpgrades.Select(field => field.Id).Order()), "Only the ten vendor weapons may be upgraded.");
            byte[] data = Rc1GrantFixture();
            foreach (int id in goldIds) data[0x1B8 + id] = 1;
            // Unmapped bytes and collectible records must survive all upgrades.
            data[0x11D8 + 36] = 0x7F;
            byte[] original = data.ToArray();
            var fields = Rc1GoldUpgradeEditing.Fields(data, "NPEA00385"); Equal(10, fields.Count);
            foreach (var field in fields)
            {
                byte[] expected = data.ToArray(); expected[0x11D8 + field.Id] = 1;
                byte[] edited = Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits((field.Key, 1)));
                True(expected.SequenceEqual(edited), "Unexpected bytes changed for Gold " + field.Name);
                True(edited.SequenceEqual(Rc1SaveEditing.Apply(edited, "NPEA00385", Rc1Edits((field.Key, 1)))), "Repeated upgrades must be no-ops.");
            }
            byte[] allExpected = data.ToArray(); foreach (int id in goldIds) allExpected[0x11D8 + id] = 1;
            var requests = fields.ToDictionary(field => field.Key, _ => 1m);
            byte[] all = Rc1SaveEditing.Apply(data, "NPEA00385", requests);
            True(allExpected.SequenceEqual(all), "All ten upgrades must preserve every unrelated byte.");
            True(all.SequenceEqual(Rc1SaveEditing.Apply(data, "NPEA00385", requests.Reverse().ToDictionary(edit => edit.Key, edit => edit.Value))), "Batch order must not matter.");
            True(original.SequenceEqual(data), "Source arrays must remain detached.");
        });
        Check("RC1 gold upgrades reject removals, unsupported IDs, uncertain flags and newly granted weapons atomically", () =>
        {
            byte[] data = Rc1GrantFixture(), original = data.ToArray();
            foreach (int id in new[] { 0, 13, 14, 18, 23, 24, 36, 999 })
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_gold_" + id, 1))));
            foreach (decimal value in new[] { -1m, 0.5m, 2m, decimal.MaxValue })
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_gold_10", value))));
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_ammo_10", 40), ("rc1_grant_15", 1), ("rc1_gold_15", 1))));
            True(original.SequenceEqual(data), "Rejected mixed batches must not touch the input.");
            foreach (byte flag in new byte[] { 2, 0xFF })
            {
                data[0x11E2] = flag; Equal(0, Rc1GoldUpgradeEditing.Fields(data, "NPEA00385").Count);
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_gold_10", 1))));
            }
            data[0x11E2] = 1;
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_gold_10", 0))));
            data[0x11E2] = 0;
            foreach (byte flag in new byte[] { 0, 2, 0xFF })
            {
                data[0x1C2] = flag;
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_gold_10", 1))));
            }
            foreach (string region in new[] { "NPUA80643", "NPJA40001", "NPEA00386" })
                Equal(0, Rc1GoldUpgradeEditing.Fields(original, region).Count);
            byte[] malformed = original.ToArray(); malformed[0x11D0] ^= 1;
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(malformed, "NPEA00385", Rc1Edits(("rc1_gold_10", 1))));
        });
        Check("RC1 gold upgrade UI stages and cancels, blocks hidden invalid ammo, and refreshes after save", () =>
        {
            using var form = new Form { ClientSize = new Size(1000, 680), ShowInTaskbar = false, AutoScroll = true,
                Font = new Font("Segoe UI", 11F) };
            using var editor = new Rc1SaveEditingControl(); form.Controls.Add(editor);
            byte[] data = Rc1GrantFixture();
            foreach (int id in goldIds) data[0x1B8 + id] = 1;
            editor.LoadSnapshot(data, "NPEA00385"); form.Show(); Application.DoEvents();
            var category = editor.Controls.Find("Rc1EditCategory", true).Cast<ComboBox>().Single();
            category.SelectedItem = "Gold upgrades";
            foreach (int id in goldIds)
            {
                var check = editor.Controls.Find("Rc1Edit_rc1_gold_" + id, true).Cast<CheckBox>().Single();
                True(check.Enabled && !check.Checked, "Owned gold-capable weapons must be selectable.");
                check.Checked = true; Equal(1m, editor.PendingEdits["rc1_gold_" + id]);
                check.Checked = false; True(!editor.PendingEdits.ContainsKey("rc1_gold_" + id), "Cancelling must clear the request.");
            }
            var bomb = editor.Controls.Find("Rc1Edit_rc1_gold_10", true).Cast<CheckBox>().Single();
            category.SelectedItem = "Weapon ammo";
            var ammo = editor.Controls.Find("Rc1Edit_rc1_ammo_10", true).Cast<NumericTextBox>().Single();
            ammo.Text = "invalid"; category.SelectedItem = "Gold upgrades"; bomb.Checked = true;
            True(!bomb.Checked && editor.HasInvalidInputs, "Hidden invalid ammo must block upgrade staging.");
            True(!editor.ValidateInputs(), "Invalid ammo must block saving.");
            ammo.Value = 40; category.SelectedItem = "Gold upgrades";
            foreach (int id in goldIds) editor.Controls.Find("Rc1Edit_rc1_gold_" + id, true).Cast<CheckBox>().Single().Checked = true;
            Application.DoEvents();
            string preview = Path.GetFullPath(Path.Combine("artifacts", "rc1-gold-upgrades.png"));
            Directory.CreateDirectory(Path.GetDirectoryName(preview));
            using (var bitmap = new Bitmap(form.Width, form.Height)) { form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, bitmap.Size)); bitmap.Save(preview); }
            string folder = Fixture(root, "NPEA00385"); File.WriteAllBytes(Path.Combine(folder, "USR-DATA"), data);
            var original = Snapshot(folder);
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "rc1-gold-backups"));
            string backup = session.Save(0, 0, Path.Combine(root, "rc1-gold-backups"), editor.PendingEdits); Same(original, Snapshot(backup));
            session.Save(123, 0, Path.Combine(root, "rc1-gold-backups"));
            using var reopened = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "rc1-gold-backups"));
            Equal(123, reopened.Bolts); Equal(40, Rc1SaveEditing.Fields(reopened.ReadInspectionData(), "NPEA00385").Single(field => field.Id == 10).Current);
            editor.LoadSnapshot(reopened.ReadInspectionData(), "NPEA00385");
            foreach (int id in goldIds)
            {
                var check = editor.Controls.Find("Rc1Edit_rc1_gold_" + id, true).Cast<CheckBox>().Single();
                True(check.Checked && !check.Enabled, "Committed upgrades must show installed and disabled.");
            }
            True(!editor.HasChanges, "Reloading must clear staged edits.");
            editor.LoadSnapshot(Rc1GrantFixture(), "NPEA00385");
            True(editor.Controls.Find("Rc1Edit_rc1_gold_15", true).Length == 0, "Unowned weapon must stay unavailable.");
            editor.LoadSnapshot(data, "NPUA80643"); True(editor.Controls.Find("Rc1Edit_rc1_gold_10", true).Length == 0, "Other regions must stay unavailable.");
            form.Close();
        });
    }

    private static void Rc1GoldUpgradeReferenceChecks(string root, string source)
    {
        Check("Actual RC1 save copy gains Gold Bomb Glove with exact preservation, backup and reopening", () =>
        {
            var original = Snapshot(source);
            string folder = Path.Combine(root, "RC1 gold reference"); Directory.CreateDirectory(folder);
            foreach (string path in Directory.GetFiles(source)) File.Copy(path, Path.Combine(folder, Path.GetFileName(path)));
            var tools = new FakeTools { FailDecrypt = true, FailEncrypt = true };
            using var session = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-gold-reference-backups"));
            byte[] expected = original["USR-DATA"].ToArray(); expected[0x11E2] = 1; expected.AsSpan(12, 4).Fill(0xFF);
            string backup = session.Save(session.Bolts, 0, Path.Combine(root, "rc1-gold-reference-backups"), Rc1Edits(("rc1_gold_10", 1)));
            Same(original, Snapshot(backup));
            True(expected.SequenceEqual(File.ReadAllBytes(Path.Combine(folder, "USR-DATA"))), "Only Gold Bomb Glove and player checksum bytes may change.");
            using var reopened = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-gold-reference-backups"));
            True(Rc1GoldUpgradeEditing.Fields(reopened.ReadInspectionData(), "NPEA00385").Single(field => field.Id == 10).Upgraded, "Gold upgrade must survive reopening.");
            foreach (string name in original.Keys.Where(name => name != "USR-DATA"))
                True(original[name].SequenceEqual(File.ReadAllBytes(Path.Combine(folder, name))), "Unrelated file changed: " + name);
            Same(original, Snapshot(source)); Equal(0, tools.CryptoCalls);
        });
    }
}
