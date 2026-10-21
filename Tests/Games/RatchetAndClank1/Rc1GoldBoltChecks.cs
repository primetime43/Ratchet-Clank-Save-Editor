using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static readonly int[] Rc1GoldBoltCounts = { 0, 3, 4, 3, 1, 2, 2, 2, 2, 2, 2, 1, 2, 1, 4, 2, 2, 2, 3 };

    private static byte[] Rc1GoldBoltFixture()
    {
        byte[] data = Rc1GrantFixture();
        for (int world = 0; world < 20; world++)
        {
            int start = 0x1544 + world * 0x82A4;
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(start), 0x829C);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(start + 4), 0);
            foreach (var record in Rc1Research.WorldRecords)
            {
                BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(start + record.Offset - 8), record.Id);
                BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(start + record.Offset - 4), record.Length);
            }
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(start + 0x829C), uint.MaxValue);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(start + 0x82A0), 0);
            data.AsSpan(start + 0x8024, 4).Clear();
        }
        return data;
    }

    private static byte[] Rc1AllGoldBoltsExpected(byte[] original)
    {
        byte[] expected = original.ToArray();
        for (int world = 1; world < 19; world++)
        {
            int start = 0x1544 + world * 0x82A4; bool changed = false;
            for (int slot = 0; slot < Rc1GoldBoltCounts[world]; slot++)
            {
                int offset = start + 0x8024 + slot;
                if (original[offset] != 0) continue;
                expected[offset] = 1; changed = true;
            }
            if (changed) expected.AsSpan(start + 4, 4).Fill(0xFF);
        }
        return expected;
    }

    private static void Rc1GoldBoltChecks(string root)
    {
        Check("RC1 forty gold-bolt flags change only the selected flag and its affected world checksum", () =>
        {
            byte[] data = Rc1GoldBoltFixture(), original = data.ToArray();
            True(Rc1GoldBoltEditing.Supports(data, "NPEA00385"), "All world records must be recognized.");
            var fields = Rc1GoldBoltEditing.Fields(data, "NPEA00385"); Equal(40, fields.Count);
            foreach (var field in fields)
            {
                int start = 0x1544 + field.World * 0x82A4;
                byte[] expected = data.ToArray(); expected[start + 0x8024 + field.Slot] = 1; expected.AsSpan(start + 4, 4).Fill(0xFF);
                byte[] edited = Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits((field.Key, 1)));
                True(expected.SequenceEqual(edited), "Only the selected collection byte and affected world checksum can change: " + field.Key);
                True(edited.SequenceEqual(Rc1SaveEditing.Apply(edited, "NPEA00385", Rc1Edits((field.Key, 1)))), "Repeated collection must not change checksum or other state.");
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(edited, "NPEA00385", Rc1Edits((field.Key, 0))));
            }
            var requests = fields.ToDictionary(field => field.Key, _ => 1m);
            byte[] all = Rc1SaveEditing.Apply(data, "NPEA00385", requests);
            True(Rc1AllGoldBoltsExpected(data).SequenceEqual(all), "All forty flags must preserve all other bytes, including reserved slots and worlds.");
            True(all.SequenceEqual(Rc1SaveEditing.Apply(data, "NPEA00385", requests.Reverse().ToDictionary(edit => edit.Key, edit => edit.Value))), "Request order cannot affect the batch.");
            True(original.SequenceEqual(data), "The input must remain unchanged.");
            data[0x1544 + 0x8024] = 0xEE; // Unused world0 slot.
            byte[] preserved = Rc1SaveEditing.Apply(data, "NPEA00385", requests);
            Equal(0xEE, (int)preserved[0x1544 + 0x8024]);
        });
        Check("RC1 gold-bolt guards reject malformed world blocks and unavailable flags without disabling player-only edits", () =>
        {
            byte[] data = Rc1GoldBoltFixture(), original = data.ToArray();
            foreach (int world in new[] { 0, 1, 18, 19 })
                foreach (int relative in new[] { 0, 8, 0x801C, 0x8020, 0x829C, 0x82A0 })
                {
                    byte[] invalid = data.ToArray(); invalid[0x1544 + world * 0x82A4 + relative] ^= 1; byte[] before = invalid.ToArray();
                    True(!Rc1GoldBoltEditing.Supports(invalid, "NPEA00385"), "World validation must reject altered framing.");
                    True(Rc1SaveEditing.Supports(invalid, "NPEA00385"), "Player-only edits must retain their existing scope.");
                    Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(invalid, "NPEA00385", Rc1Edits(("rc1_ammo_10", 40), ("rc1_bolt_1_0", 1))));
                    True(before.SequenceEqual(invalid), "An invalid world batch must not mutate the caller's bytes.");
                }
            foreach (string key in new[] { "rc1_bolt_0_0", "rc1_bolt_19_0", "rc1_bolt_1_3", "rc1_bolt_2_4", "rc1_bolt_-1_0", "rc1_bolt_99_0" })
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits((key, 1))));
            foreach (decimal value in new[] { -1m, 0.5m, 2m, decimal.MaxValue })
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_bolt_1_0", value))));
            foreach (byte flag in new byte[] { 2, 0xFF })
            {
                byte[] uncertain = data.ToArray(); uncertain[0x1180C] = flag;
                Equal(39, Rc1GoldBoltEditing.Fields(uncertain, "NPEA00385").Count);
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(uncertain, "NPEA00385", Rc1Edits(("rc1_bolt_1_0", 1))));
            }
            foreach (string region in new[] { "NPUA80643", "NPJA40001", "NPEA00386" })
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, region, Rc1Edits(("rc1_bolt_1_0", 1))));
            True(original.SequenceEqual(data), "Rejected calls must preserve the source.");
        });
        Check("RC1 gold-bolt balance follows native collection and gold-upgrade counts and composes with all mapped editors", () =>
        {
            byte[] data = Rc1GoldBoltFixture();
            Equal(new Rc1GoldBoltSummary(0, 0, 0), Rc1GoldBoltEditing.Summary(data, "NPEA00385"));
            var edits = Rc1Edits(("rc1_ammo_10", 40), ("rc1_grant_15", 1), ("rc1_gadget_12", 1), ("rc1_equipment_2", 1), ("rc1_gold_10", 1), ("rc1_bolt_1_0", 1));
            byte[] one = Rc1SaveEditing.Apply(data, "NPEA00385", edits);
            Equal(new Rc1GoldBoltSummary(1, 4, 0), Rc1GoldBoltEditing.Summary(one, "NPEA00385"));
            foreach (var field in Rc1GoldBoltEditing.Fields(data, "NPEA00385")) edits[field.Key] = 1;
            byte[] all = Rc1SaveEditing.Apply(data, "NPEA00385", edits);
            Equal(new Rc1GoldBoltSummary(40, 4, 36), Rc1GoldBoltEditing.Summary(all, "NPEA00385"));
            True(all.SequenceEqual(Rc1SaveEditing.Apply(data, "NPEA00385", edits.Reverse().ToDictionary(edit => edit.Key, edit => edit.Value))), "Mixed order must not affect gold spending or collection.");
            all.AsSpan(0x11D8, 37).Fill(2); // Native counts any nonzero upgrade byte, then clamps to ten.
            Equal(new Rc1GoldBoltSummary(40, 40, 0), Rc1GoldBoltEditing.Summary(all, "NPEA00385"));
        });
        Check("RC1 gold-bolt UI filters planets, stages all supported flags, previews spending and preserves committed world edits", () =>
        {
            using var form = new Form { ClientSize = new Size(1000, 680), ShowInTaskbar = false, AutoScroll = true, Font = new Font("Segoe UI", 11F) };
            using var editor = new Rc1SaveEditingControl(); form.Controls.Add(editor);
            byte[] data = Rc1GoldBoltFixture(); editor.LoadSnapshot(data, "NPEA00385"); form.Show(); Application.DoEvents();
            var category = editor.Controls.Find("Rc1EditCategory", true).Cast<ComboBox>().Single(); category.SelectedItem = "Gold bolts";
            var planets = editor.Controls.Find("Rc1GoldBoltWorld", true).Cast<ComboBox>().Single(); Alphabetical(planets); Equal(18, planets.Items.Count);
            var first = editor.Controls.Find("Rc1Edit_rc1_bolt_1_0", true).Cast<CheckBox>().Single();
            first.Checked = true; Equal(1m, editor.PendingEdits["rc1_bolt_1_0"]); first.Checked = false; True(!editor.HasChanges, "Cancelling must clear the request.");
            first.Checked = true;
            planets.SelectedItem = planets.Items.Cast<object>().Single(item => item.ToString() == "Aridia");
            True(!first.Visible, "Planet filtering must hide other planets without losing edits."); Equal(1m, editor.PendingEdits["rc1_bolt_1_0"]);
            category.SelectedItem = "Gold upgrades";
            editor.Controls.Find("Rc1Edit_rc1_gold_10", true).Cast<CheckBox>().Single().Checked = true;
            var summary = editor.Controls.Find("Rc1GoldBoltSummary", true).Cast<Label>().Single(); True(summary.Text.Contains("Spent on gold upgrades: 4"), "Preview must account for staged upgrades.");
            category.SelectedItem = "Weapon ammo";
            var ammo = editor.Controls.Find("Rc1Edit_rc1_ammo_10", true).Cast<NumericTextBox>().Single(); ammo.Text = "bad";
            category.SelectedItem = "Gold bolts";
            var collectAll = editor.Controls.Find("Rc1CollectGoldBolts", true).Cast<Button>().Single(); collectAll.PerformClick();
            Throws<InvalidOperationException>(() => { var ignored = editor.PendingEdits; });
            True(editor.HasInvalidInputs, "Hidden invalid ammo must block bulk collection."); ammo.Value = 40;
            Equal(1, editor.PendingEdits.Keys.Count(key => key.StartsWith("rc1_bolt_")));
            category.SelectedItem = "Gold bolts"; collectAll.PerformClick(); Equal(40, editor.PendingEdits.Keys.Count(key => key.StartsWith("rc1_bolt_")));
            True(summary.Text.Contains("Available: 36"), "Collect-all must preview the derived balance.");
            Application.DoEvents();
            using (var bitmap = new Bitmap(form.Width, form.Height)) { form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, bitmap.Size)); bitmap.Save(Path.GetFullPath("artifacts/rc1-gold-bolts.png")); }
            string folder = Fixture(root, "NPEA00385"); File.WriteAllBytes(Path.Combine(folder, "USR-DATA"), data); var original = Snapshot(folder);
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "rc1-collect-backups"));
            string backup = session.Save(0, 0, Path.Combine(root, "rc1-collect-backups"), editor.PendingEdits); Same(original, Snapshot(backup));
            session.Save(123, 0, Path.Combine(root, "rc1-collect-backups"));
            using var reopened = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "rc1-collect-backups")); Equal(123, reopened.Bolts);
            Equal(new Rc1GoldBoltSummary(40, 4, 36), Rc1GoldBoltEditing.Summary(reopened.ReadInspectionData(), "NPEA00385"));
            editor.LoadSnapshot(reopened.ReadInspectionData(), "NPEA00385");
            True(!editor.Controls.Find("Rc1CollectGoldBolts", true).Cast<Button>().Single().Enabled && !editor.HasChanges, "All collected flags must show a clean disabled bulk action.");
            editor.LoadSnapshot(Rc1GrantFixture(), "NPEA00385"); Equal(0, editor.Controls.Find("Rc1CollectGoldBolts", true).Length);
            editor.LoadSnapshot(data, "NPUA80643"); Equal(0, editor.Controls.Find("Rc1GoldBoltWorld", true).Length); form.Close();
            string failedFolder = Fixture(root, "NPEA00385"); File.WriteAllBytes(Path.Combine(failedFolder, "USR-DATA"), data);
            var failedOriginal = Snapshot(failedFolder);
            using var failed = SaveSession.Open(failedFolder, new FakeTools { FailEncrypt = true }, decrypted: false, backupRoot: Path.Combine(root, "rc1-gold-bolt-failed-backups"));
            Throws<InvalidOperationException>(() => failed.Save(0, 0, Path.Combine(root, "rc1-gold-bolt-failed-backups"), Rc1Edits(("rc1_bolt_1_0", 1))));
            Same(failedOriginal, Snapshot(failedFolder));
            Equal(0, Rc1GoldBoltEditing.Summary(failed.ReadInspectionData(), "NPEA00385").Collected);
        });
    }

    private static void Rc1GoldBoltReferenceChecks(string root, string source)
    {
        Check("Actual RC1 copy collects forty gold bolts with exact world/checksum changes, backup and source preservation", () =>
        {
            var original = Snapshot(source); string folder = Path.Combine(root, "RC1 gold bolts reference"); Directory.CreateDirectory(folder);
            foreach (string path in Directory.GetFiles(source)) File.Copy(path, Path.Combine(folder, Path.GetFileName(path)));
            var tools = new FakeTools { FailDecrypt = true, FailEncrypt = true };
            using var session = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-gold-bolt-reference-backups"));
            byte[] expected = Rc1AllGoldBoltsExpected(original["USR-DATA"]); expected.AsSpan(12, 4).Fill(0xFF);
            var requests = Rc1GoldBoltEditing.Fields(session.ReadInspectionData(), "NPEA00385").ToDictionary(field => field.Key, _ => 1m); Equal(40, requests.Count);
            string backup = session.Save(session.Bolts, 0, Path.Combine(root, "rc1-gold-bolt-reference-backups"), requests); Same(original, Snapshot(backup));
            True(expected.SequenceEqual(File.ReadAllBytes(Path.Combine(folder, "USR-DATA"))), "Only the forty flags and affected world/player checksum words may change.");
            using var reopened = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-gold-bolt-reference-backups"));
            Equal(40, Rc1GoldBoltEditing.Summary(reopened.ReadInspectionData(), "NPEA00385").Collected);
            foreach (string name in original.Keys.Where(name => name != "USR-DATA")) True(original[name].SequenceEqual(File.ReadAllBytes(Path.Combine(folder, name))), "Unrelated file changed: " + name);
            Same(original, Snapshot(source)); Equal(0, tools.CryptoCalls);
        });
    }
}
