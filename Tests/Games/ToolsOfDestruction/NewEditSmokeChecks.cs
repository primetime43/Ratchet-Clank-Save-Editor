using System;
using System.Buffers.Binary;
using System.IO;
using System.Linq;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    // In-memory only: no UI, crypto subprocesses or private saves.
    private static void NewEditSmokeChecks()
    {
        Check("Seven consumable ammo edits change only their bounded floats", () =>
        {
            byte[] data = EditableOwnedGadgets(), before = data.ToArray(), expected = data.ToArray();
            int[] ids = { 16, 17, 18, 20, 21, 22, 23 };
            decimal[] caps = { 4, 2, 3, 2, 1, 3, 3 };
            var fields = TodSaveEditing.Fields(data, "BCUS98127").Where(field => field.Category == "Gadget ammo").ToArray();
            Equal(7, fields.Length);
            var edits = ids.Select((id, index) => (Key: "ammo_" + id, Value: caps[index])).ToDictionary(item => item.Key, item => item.Value);
            foreach (var (id, cap) in ids.Zip(caps))
            {
                Equal(cap, fields.Single(field => field.Key == "ammo_" + id).Maximum);
                BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(id * 20 + 8, 4), (float)cap);
            }
            True(TodSaveEditing.Apply(data, "BCUS98127", edits).SequenceEqual(expected), "Only requested ammo floats may change.");
            True(data.SequenceEqual(before), "Input must remain detached.");
            Equal(0.5f, BinaryPrimitives.ReadSingleBigEndian(TodSaveEditing.Apply(data, "BCUS98127", Edits(("ammo_16", 0.5m))).AsSpan(328, 4)));
        });
        Check("Uncertain gadget states and linked/traversal IDs remain read-only", () =>
        {
            foreach (int fault in Enumerable.Range(0, 6))
            {
                byte[] data = EditableOwnedGadgets(); int offset = 16 * 20;
                if (fault == 0) data[offset + 16] = 0;
                if (fault == 1) data[offset + 17] = 1;
                if (fault == 2) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(offset + 4, 4), 1);
                if (fault == 3) BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(offset + 12, 4), 1);
                if (fault == 4) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(offset + 8, 4), 5);
                if (fault == 5) BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(offset + 8, 4), float.NaN);
                True(!TodSaveEditing.Fields(data, "BCUS98127").Any(field => field.Key == "ammo_16"), "Uncertain inputs must not be repaired into editable records.");
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("ammo_16", 1))));
            }
            foreach (int id in new[] { 19, 24, 25, 26, 27, 28, 29, 30, 31 })
            {
                byte[] data = EditableOwnedGadgets(); data[id * 20 + 16] = 1;
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("ammo_" + id, 1))));
            }
            foreach (decimal value in new[] { -1m, 4.01m })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(EditableOwnedGadgets(), "BCUS98127", Edits(("ammo_16", value))));
        });
        Check("James Zurkon selection changes one byte without granting points, ownership or ammo", () =>
        {
            byte[] data = BonusFixture(399);
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("bonus_james_zurkon", 1))));
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8708, 4), 400);
            byte[] expected = data.ToArray(); expected[0x8701] = 1;
            True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits(("bonus_james_zurkon", 1)))), "Only the saved request byte may change.");
            foreach (byte unknown in new byte[] { 2, 255 })
            {
                data[0x8701] = unknown;
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("bonus_james_zurkon", 0))));
            }
            data[0x8701] = 0;
            string detail = TodSaveInspection.Read(data, "BCUS98127").Table("Bonuses & cheats").Rows[9].Details;
            True(detail.Contains("Off clears only the saved request") && detail.Contains("not a local consumer score check"), "Keep the editor gate distinct from the runtime override.");
        });
    }

    private static byte[] EditableOwnedGadgets()
    {
        byte[] data = EditableFixture();
        foreach (int id in new[] { 16, 17, 18, 20, 21, 22, 23 }) data[id * 20 + 16] = 2;
        return data;
    }
}
