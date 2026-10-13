using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static readonly int[] ConsumableGrantIds = { 16, 17, 18, 20, 21, 22, 23 };
    private static byte[] EarlyItemFixture()
    {
        byte[] data = WeaponGrantFixture();
        for (int id = 16; id <= 23; id++) data.AsSpan(id * 20 + 4, 14).Clear();
        foreach (int offset in new[] { 0x318, 0x374, 0x3D0, 0x31C, 0x378, 0x3D4 })
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(offset, 4), 0);
        BinaryPrimitives.WriteUInt64BigEndian(data.AsSpan(0x5528, 8), 0x8000000000000001);
        return data;
    }

    private static void EarlyItemGrantChecks(string root)
    {
        Check("Seven consumable grants use +1 ammo and update only confirmed records/count/slots/class flag", () =>
        {
            byte[] data = EarlyItemFixture(), before = data.ToArray(), expected = data.ToArray();
            var edits = ConsumableGrantIds.ToDictionary(id => "weapon_grant_" + id, _ => 1m);
            for (int index = 0; index < ConsumableGrantIds.Length; index++)
            {
                int id = ConsumableGrantIds[index]; expected[id * 20 + 16] = 1;
                BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(id * 20 + 8, 4), 1);
                BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x284 + 4 * index, 4), id);
            }
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x280, 4), 44);
            BinaryPrimitives.WriteUInt64BigEndian(expected.AsSpan(0x5528, 8), 0x8000000000000401);
            var result = TodSaveEditing.Apply(data, "BCUS98127", edits);
            True(expected.SequenceEqual(result) && before.SequenceEqual(data), "Only confirmed saved writes may change; input must be detached.");
            Equal(7, TodSaveEditing.Fields(result, "BCUS98127").Count(field => field.Category == "Gadget ammo"));
            True(result.SequenceEqual(TodSaveEditing.Apply(result, "BCUS98127", edits)), "Duplicate grants must not add another ammo unit or count.");
            BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(16 * 20 + 8, 4), 0.5f);
            result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_16", 1)));
            Equal(1.5f, BinaryPrimitives.ReadSingleBigEndian(result.AsSpan(16 * 20 + 8, 4)));
            BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(16 * 20 + 8, 4), 4f);
            result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_16", 1)));
            Equal(4f, BinaryPrimitives.ReadSingleBigEndian(result.AsSpan(16 * 20 + 8, 4)));
        });
        Check("Two-item flag counts the native consumable class including Groovitron and never repairs no-ops", () =>
        {
            byte[] data = EarlyItemFixture();
            var first = TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_16", 1)));
            Equal(0x8000000000000001UL, BinaryPrimitives.ReadUInt64BigEndian(first.AsSpan(0x5528, 8)));
            var second = TodSaveEditing.Apply(first, "BCUS98127", Edits(("weapon_grant_17", 1)));
            Equal(0x8000000000000401UL, BinaryPrimitives.ReadUInt64BigEndian(second.AsSpan(0x5528, 8)));
            data[19 * 20 + 16] = 0xFE;
            var withGroovitron = TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_16", 1)));
            Equal(0x8000000000000401UL, BinaryPrimitives.ReadUInt64BigEndian(withGroovitron.AsSpan(0x5528, 8)));
            True(data.AsSpan(19 * 20, 20).SequenceEqual(withGroovitron.AsSpan(19 * 20, 20)), "Groovitron must count without being modified.");
            data[16 * 20 + 16] = 1;
            True(data.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_16", 1)))), "Existing ownership does not repair a missing flag.");
        });
        Check("Equipment grants keep all three object counters consistent and preserve unrelated state", () =>
        {
            byte[] data = EarlyItemFixture(), expected = data.ToArray();
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x374, 4), 7);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x3D0, 4), 9); expected = data.ToArray();
            foreach (int offset in new[] { 0x318, 0x31C, 0x378, 0x3D4 })
                BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(offset, 4), 1);
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(0x3D0, 4), 10);
            var edits = Edits(("equipment_grant_5", 1), ("equipment_grant_6", 1));
            var result = TodSaveEditing.Apply(data, "BCUS98127", edits);
            True(expected.SequenceEqual(result), "Only current/peak/addition words may change; peak7 must remain7.");
            True(result.SequenceEqual(TodSaveEditing.Apply(result, "BCUS98127", edits)), "Existing equipment must not be recounted.");
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(result, "BCUS98127", Edits(("equipment_grant_5", 0))));
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x3D0, 4), uint.MaxValue);
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("equipment_grant_5", 1))));
            True(data.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("equipment_grant_5", 0)))), "Overflow/no-op baselines must be preserved.");
        });
        Check("Early grants reject linked/story items, malformed consumables and unsupported equipment", () =>
        {
            byte[] data = EarlyItemFixture();
            foreach (string key in new[] { "weapon_grant_19", "weapon_grant_24", "weapon_grant_27", "weapon_grant_30", "equipment_grant_11", "equipment_grant_16" })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits((key, 1))));
            BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(16 * 20 + 8, 4), float.NaN);
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("weapon_grant_16", 1))));
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(EarlyItemFixture(), "BCES00052", Edits(("equipment_grant_5", 1))));
        });
        Check("Consumable/equipment UI supports staging, dependent-slot cancellation and read-only owned items", () =>
        {
            using var form = new Form { ClientSize = new Size(1100, 850), Font = new Font("Segoe UI", 13) };
            using var editor = new TodSaveEditingControl(); form.Controls.Add(editor); editor.LoadSnapshot(EarlyItemFixture(), "BCUS98127"); form.Show();
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single(); Alphabetical(category);
            ComboBox Input(string key) => editor.Controls.Find("MappedEdit_" + key, true).Cast<ComboBox>().Single();
            void Choose(string key, decimal value) { var input = Input(key); input.SelectedItem = input.Items.Cast<TodEditOption>().Single(option => option.Value == value); }
            category.SelectedItem = "Consumable unlocks"; Choose("weapon_grant_16", 1);
            category.SelectedItem = "Quick select"; Choose("qs_6", 16);
            category.SelectedItem = "Consumable unlocks"; Choose("weapon_grant_16", 0);
            True(!editor.HasChanges, "Cancelling consumable ownership must clear dependent assignments.");
            category.SelectedItem = "Equipment unlocks"; Choose("equipment_grant_5", 1); Choose("equipment_grant_6", 1);
            Equal(2, editor.PendingEdits.Count); True(!editor.Controls.Find("MappedBulkActions", true).Single().Visible, "Unrelated buttons must stay hidden.");
            var saved = TodSaveEditing.Apply(EarlyItemFixture(), "BCUS98127", editor.PendingEdits);
            editor.LoadSnapshot(saved, "BCUS98127"); category.SelectedItem = "Equipment unlocks";
            True(!Input("equipment_grant_5").Enabled && !Input("equipment_grant_6").Enabled && !editor.HasChanges, "Owned equipment must load cleanly and cannot be removed.");
        });
        Check("Mixed combat, consumable and equipment grants save through the existing backed-up workflow", () =>
        {
            string folder = Fixture(root, "BCUS98127"); byte[] data = EarlyItemFixture();
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), data);
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "early-item-backups"));
            var edits = Edits(("weapon_grant_1", 1), ("weapon_grant_16", 1), ("weapon_grant_17", 1), ("equipment_grant_5", 1), ("equipment_grant_6", 1), ("qs_7", 16));
            string backup = session.Save(session.CharacterBolts, session.Raritanium, mappedEdits: edits);
            True(File.ReadAllBytes(Path.Combine(backup, "GAME.SAV")).SequenceEqual(data), "Original data must remain recoverable.");
            True(session.ReadInspectionData().SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", edits)), "Mixed grants must use one validated plan.");
        });
    }
}
