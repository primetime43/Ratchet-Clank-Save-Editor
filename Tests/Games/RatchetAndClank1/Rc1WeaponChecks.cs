using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static byte[] Rc1GrantFixture()
    {
        byte[] data = Rc1AmmoFixture();
        data.AsSpan(0x11C, 148).Clear(); data.AsSpan(0x1B8, 37).Clear(); data.AsSpan(0x1E8, 37).Clear();
        data.AsSpan(0x218, 12).Fill(0xFF); data.AsSpan(0x22C, 32).Clear();
        data[0x1B8 + 10] = data[0x1E8 + 10] = 1; data[0x218] = 0x4A;
        BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x11C + 40), 10);
        BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x22C), 10);
        return data;
    }

    private static Dictionary<string, decimal> Rc1Edits(params (string Key, decimal Value)[] values) =>
        values.ToDictionary(value => value.Key, value => value.Value, StringComparer.Ordinal);

    private static void Rc1WeaponChecks(string root)
    {
        Check("RC1 grants reproduce ownership, acquisition flag, starting ammo, bounded inventory list and first free slot", () =>
        {
            foreach (var weapon in Rc1Research.Weapons.Where(weapon => weapon.GrantSupported))
            {
                byte[] data = Rc1GrantFixture();
                data[weapon.OwnershipOffset] = data[weapon.AcquisitionFlagOffset] = 0;
                BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(weapon.AmmoOffset), 0);
                if (weapon.Id == 10) { data[0x218] = 0xFF; data.AsSpan(0x22C, 32).Clear(); }
                byte[] original = data.ToArray(), expected = data.ToArray();
                expected[weapon.OwnershipOffset] = expected[weapon.AcquisitionFlagOffset] = 1;
                BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(weapon.AmmoOffset), weapon.InitialAmmo);
                if (weapon.AcquisitionList) expected[0x219] = (byte)(weapon.Id | 0x40);
                BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(weapon.Id == 10 ? 0x22C : 0x230), weapon.Id);
                byte[] edited = Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_grant_" + weapon.Id, 1)));
                True(expected.SequenceEqual(edited), "Grant changed unexpected bytes: " + weapon.Name);
                True(original.SequenceEqual(data), "A grant must not mutate its source array.");
                byte[] unchanged = Rc1SaveEditing.Apply(edited, "NPEA00385", Rc1Edits(("rc1_grant_" + weapon.Id, 1)));
                True(edited.SequenceEqual(unchanged), "Duplicate grants must not refill or append again.");
            }
            Equal(15, Rc1Research.Weapons.Count(weapon => weapon.GrantSupported));
        });
        Check("RC1 grant batches are deterministic and preserve existing ammo, full slots and unrelated state", () =>
        {
            byte[] data = Rc1GrantFixture();
            var fields = Rc1WeaponEditing.Grants(data, "NPEA00385");
            var requests = fields.ToDictionary(field => field.Key, _ => 1m);
            byte[] one = Rc1SaveEditing.Apply(data, "NPEA00385", requests);
            byte[] reversed = Rc1SaveEditing.Apply(data, "NPEA00385", requests.Reverse().ToDictionary(edit => edit.Key, edit => edit.Value));
            True(one.SequenceEqual(reversed), "Insertion order must not affect combined grants.");
            Equal(10, BinaryPrimitives.ReadInt32BigEndian(one.AsSpan(0x144))); // existing Bomb Glove is not refilled
            Equal(0x4A, (int)one[0x218]); Equal(0, one.AsSpan(0x218, 12).Count((byte)0xFF));
            True(data.AsSpan(0x254).SequenceEqual(one.AsSpan(0x254)), "Progression and later records must be preserved.");
            for (int slot = 0; slot < 8; slot++) BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x22C + slot * 4), 0xA0000000u + (uint)slot);
            byte[] full = Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_grant_15", 1)));
            True(data.AsSpan(0x22C, 32).SequenceEqual(full.AsSpan(0x22C, 32)), "A full slot bank must never be overwritten.");
            BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x158), 150);
            byte[] retained = Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_grant_15", 1)));
            Equal(150, BinaryPrimitives.ReadInt32BigEndian(retained.AsSpan(0x158)));
        });
        Check("RC1 rejects uncertain grants, removals and list overflow without applying any part of a batch", () =>
        {
            byte[] data = Rc1GrantFixture();
            foreach (string key in new[] { "rc1_grant_12", "rc1_grant_999" })
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits((key, 1))));
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_grant_10", 0))));
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_grant_15", 0.5m))));
            foreach (byte flag in new byte[] { 1, 2, 0xFF })
            {
                data[0x1E8 + 15] = flag;
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_ammo_10", 0), ("rc1_grant_15", 1))));
            }
            data[0x1E8 + 15] = 0; data[0x1B8 + 15] = 2;
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_grant_15", 1))));
            data[0x1B8 + 15] = 0; data.AsSpan(0x218, 12).Fill(0xEE); data[0x218] = 0xFF;
            byte[] original = data.ToArray();
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_grant_11", 1), ("rc1_grant_15", 1))));
            True(original.SequenceEqual(data), "Overflow must not partially change the source.");
            foreach (string region in new[] { "NPUA80643", "NPJA40001", "NPEA00386" })
                Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, region, Rc1Edits(("rc1_grant_15", 1))));
        });
        Check("RC1 quick-select edits support atomic moves and swaps while preserving unknown stored IDs", () =>
        {
            byte[] data = Rc1GrantFixture();
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_quick_1", 10))));
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_quick_1", 15))));
            byte[] edited = Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_quick_0", 0), ("rc1_quick_1", 10), ("rc1_grant_15", 1)));
            Equal(15, BinaryPrimitives.ReadInt32BigEndian(edited.AsSpan(0x22C)));
            Equal(10, BinaryPrimitives.ReadInt32BigEndian(edited.AsSpan(0x230)));
            byte[] swapped = Rc1SaveEditing.Apply(edited, "NPEA00385", Rc1Edits(("rc1_quick_0", 10), ("rc1_quick_1", 15)));
            Equal(10, BinaryPrimitives.ReadInt32BigEndian(swapped.AsSpan(0x22C)));
            Equal(15, BinaryPrimitives.ReadInt32BigEndian(swapped.AsSpan(0x230)));
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x234), uint.MaxValue);
            byte[] noOp = Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_quick_2", uint.MaxValue)));
            True(data.SequenceEqual(noOp), "Unknown current IDs must be preserved by a no-op.");
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_quick_3", uint.MaxValue))));
            Throws<InvalidDataException>(() => Rc1SaveEditing.Apply(data, "NPEA00385", Rc1Edits(("rc1_quick_8", 0))));
        });
        Check("RC1 category UI retains ammo, stages and cancels grants, and rejects duplicate slot selections", () =>
        {
            using var form = new Form { ClientSize = new Size(1000, 760), ShowInTaskbar = false, AutoScroll = true };
            using var editor = new Rc1SaveEditingControl(); form.Controls.Add(editor);
            editor.LoadSnapshot(Rc1GrantFixture(), "NPEA00385"); form.Show(); Application.DoEvents();
            var category = editor.Controls.Find("Rc1EditCategory", true).Cast<ComboBox>().Single(); Alphabetical(category);
            var ammo = editor.Controls.Find("Rc1Edit_rc1_ammo_10", true).Cast<NumericTextBox>().Single(); ammo.Text = "5";
            category.SelectedItem = "Weapon unlocks";
            var grant = editor.Controls.Find("Rc1Edit_rc1_grant_15", true).Cast<CheckBox>().Single();
            Equal(1, editor.Controls.Find("Rc1Edit_rc1_grant_23", true).Length);
            grant.Checked = true; Equal(1m, editor.PendingEdits["rc1_grant_15"]); Equal(5m, editor.PendingEdits["rc1_ammo_10"]);
            grant.Checked = false; True(!editor.PendingEdits.ContainsKey("rc1_grant_15"), "Cancelling a grant must clear it.");
            grant.Checked = true;
            foreach (string page in new[] { "Weapon unlocks", "Quick select" })
            {
                category.SelectedItem = page; Application.DoEvents();
                using var bitmap = new Bitmap(form.Width, form.Height); form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, bitmap.Size));
                string output = Path.GetFullPath(Path.Combine("artifacts", page == "Weapon unlocks" ? "rc1-grants.png" : "rc1-quick-select.png"));
                Directory.CreateDirectory(Path.GetDirectoryName(output)); bitmap.Save(output);
            }
            var first = editor.Controls.Find("Rc1Edit_rc1_quick_0", true).Cast<ComboBox>().Single();
            var second = editor.Controls.Find("Rc1Edit_rc1_quick_1", true).Cast<ComboBox>().Single();
            Alphabetical(first); Alphabetical(second);
            True(!second.Items.Cast<Rc1QuickOption>().Any(option => option.Value == 15), "A staged grant must not expose uncommitted slot choices.");
            second.SelectedItem = second.Items.Cast<Rc1QuickOption>().Single(option => option.Value == 10);
            Equal(0u, ((Rc1QuickOption)second.SelectedItem).Value);
            first.SelectedItem = first.Items.Cast<Rc1QuickOption>().Single(option => option.Value == 0);
            second.SelectedItem = second.Items.Cast<Rc1QuickOption>().Single(option => option.Value == 10);
            Equal(10m, editor.PendingEdits["rc1_quick_1"]);
            category.SelectedItem = "Weapon ammo"; Equal("5", ammo.Text); ammo.Text = "bad";
            category.SelectedItem = "Weapon unlocks"; grant.Checked = false;
            True(grant.Checked && editor.HasInvalidInputs, "Hidden invalid ammo must block grant changes without losing input.");
            Throws<InvalidOperationException>(() => { var ignored = editor.PendingEdits; });
            editor.LoadSnapshot(Rc1GrantFixture(), "NPEA00385"); True(!editor.HasChanges, "Reload must clear every category.");
            form.Close();
        });
        Check("RC1 committed grants and slots survive later currency saves and encryption failures retain the source", () =>
        {
            foreach (bool encrypted in new[] { false, true })
            {
                string folder = Fixture(root, "NPEA00385"); File.WriteAllBytes(Path.Combine(folder, "USR-DATA"), Rc1GrantFixture());
                var original = Snapshot(folder); var tools = new FakeTools { FailEncrypt = encrypted };
                using var session = SaveSession.Open(folder, tools, decrypted: !encrypted, backupRoot: Path.Combine(root, "rc1-weapon-backups"));
                var edits = Rc1Edits(("rc1_grant_15", 1), ("rc1_quick_0", 0), ("rc1_quick_1", 10));
                if (encrypted)
                {
                    Throws<InvalidOperationException>(() => session.Save(123, 0, Path.Combine(root, "rc1-weapon-backups"), edits));
                    Same(original, Snapshot(folder));
                    True(!Rc1SaveEditing.Fields(session.ReadInspectionData(), "NPEA00385").Any(field => field.Id == 15), "A failed commit must retain the old ownership baseline.");
                    continue;
                }
                string backup = session.Save(123, 0, Path.Combine(root, "rc1-weapon-backups"), edits); Same(original, Snapshot(backup));
                session.Save(456, 0, Path.Combine(root, "rc1-weapon-backups"));
                using var reopened = SaveSession.Open(folder, tools, decrypted: true, backupRoot: Path.Combine(root, "rc1-weapon-backups"));
                Equal(456, reopened.Bolts);
                Equal(100, Rc1SaveEditing.Fields(reopened.ReadInspectionData(), "NPEA00385").Single(field => field.Id == 15).Current);
                Equal(15u, Rc1WeaponEditing.QuickSelect(reopened.ReadInspectionData(), "NPEA00385")[0].Current);
            }
        });
    }

    private static void Rc1WeaponReferenceChecks(string root, string source)
    {
        Check("Actual RC1 source remains untouched while a copied save gains a Blaster and rearranges quick select", () =>
        {
            var original = Snapshot(source); string folder = Path.Combine(root, "RC1 actual weapon copy"); Directory.CreateDirectory(folder);
            foreach (string path in Directory.GetFiles(source)) File.Copy(path, Path.Combine(folder, Path.GetFileName(path)));
            var tools = new FakeTools { FailEncrypt = true, FailDecrypt = true };
            using var session = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-reference-weapon-backups"));
            var edits = Rc1Edits(("rc1_grant_15", 1), ("rc1_quick_0", 0), ("rc1_quick_1", 10));
            byte[] expected = original["USR-DATA"].ToArray();
            expected[0x1C7] = expected[0x1F7] = 1; expected[0x219] = 0x4F;
            BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x158), 100);
            BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x22C), 15);
            BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x230), 10);
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(12), uint.MaxValue);
            string backup = session.Save(session.Bolts, 0, Path.Combine(root, "rc1-reference-weapon-backups"), edits); Same(original, Snapshot(backup));
            True(expected.SequenceEqual(File.ReadAllBytes(Path.Combine(folder, "USR-DATA"))), "The actual save must change only the mapped grant/slot/checksum bytes.");
            using var reopened = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-reference-weapon-backups"));
            Equal(100, Rc1SaveEditing.Fields(reopened.ReadInspectionData(), "NPEA00385").Single(field => field.Id == 15).Current);
            foreach (string name in original.Keys.Where(name => name != "USR-DATA"))
                True(original[name].SequenceEqual(File.ReadAllBytes(Path.Combine(folder, name))), "Unrelated file changed: " + name);
            Same(original, Snapshot(source)); Equal(0, tools.CryptoCalls);
        });
    }
}
