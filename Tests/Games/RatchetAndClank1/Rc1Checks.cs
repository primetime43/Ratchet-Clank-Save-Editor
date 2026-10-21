using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static byte[] Rc1Fixture()
    {
        // Observed player record framing, synthetic values, nonzero alignment
        // bytes and opaque tail. No user save or account metadata is embedded.
        byte[] data = Enumerable.Repeat((byte)0xA5, 0xB0000).ToArray();
        int position = 16;
        var lengths = new (uint Id, int Size)[]
        {
            (0, 4), (1, 4), (2, 4), (3, 4), (4, 8), (5, 128), (7, 12),
            (8, 32), (9, 148), (10, 37), (11, 37), (12, 12), (13, 32),
            (12345, 1), (uint.MaxValue, 0)
        };
        foreach (var (id, size) in lengths)
        {
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(position), id);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(position + 4), (uint)size);
            data.AsSpan(position + 8, size).Clear();
            position += 8 + ((size + 3) & ~3);
        }
        BinaryPrimitives.WriteUInt32BigEndian(data, (uint)(position - 8));
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(8), (uint)(position - 16));
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(12), 0);
        BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(0x24), 123);
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(324), 40);
        data[450] = 1;
        data[442] = 0x7F; // Expose unusual raw flags rather than normalizing them.
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x22C), uint.MaxValue);
        return data;
    }

    private static void Rc1Checks(string root)
    {
        Check("RC1 records preserve alignment, unknown IDs and detached snapshot bytes", () =>
        {
            byte[] data = Rc1Fixture(), original = data.ToArray();
            var snapshot = Rc1SaveInspection.Read(data, "NPEA00385");
            True(snapshot.Available, snapshot.Message);
            Equal(14, snapshot.Records.Count);
            var flags = snapshot.Records.Single(record => record.Id == 10);
            Equal(0x1B8, flags.Offset); Equal(37, flags.Length); Equal(3, flags.Padding);
            Equal("A5A5A5", snapshot.Table("Player records").Rows.Single(row => row.Cells[0] == "10").Cells[4]);
            True(snapshot.Records.Any(record => record.Id == 12345), "Unknown records must remain visible.");
            var inventory = snapshot.Table("Weapons & gadgets");
            Equal("40", inventory.Rows.Single(row => row.Cells[0] == "Bomb Glove").Cells[3]);
            Equal("0x7F", inventory.Rows.Single(row => row.Cells[0] == "Heli-Pack").Cells[2]);
            Equal(3, snapshot.Table("Weapons & gadgets", technical: false).Columns.Length);
            Equal(7, snapshot.Table("Weapons & gadgets", technical: true).Columns.Length);
            True(snapshot.Table("Weapons & gadgets", technical: false).Rows[0].Details.Contains("Flag offset:"), "Readable rows must retain labeled technical details.");
            Equal("0xFFFFFFFF", snapshot.Table("Quick select").Rows[0].Cells[1]);
            True(snapshot.HexBytes(data.Length - 1).Contains("000AFFFF"), "Hex view must handle the last byte.");
            Throws<ArgumentOutOfRangeException>(() => snapshot.HexBytes(data.Length));
            True(original.SequenceEqual(data), "Inspection must leave input bytes intact.");
            data[0x27] = 99;
            Equal("123", snapshot.Table("Counters & nearby fields").Rows.Single(row => row.Cells[0] == "Bolts").Cells[1]);
            foreach (string region in new[] { "npua80643", "NPJA40001" })
                True(Rc1SaveInspection.Read(original, region).Available, "Individual RC1 save IDs must share the inspection path.");
            True(!Rc1SaveInspection.Read(original, "BCES01503").Available, "Collection disc ID alone must not select an individual game.");
            True(!Rc1SaveInspection.Read(original, "NPEA00386").Available, "RC2 must not receive RC1 mappings.");
        });
        Check("Malformed RC1 records fail inspection without breaking currency validation", () =>
        {
            foreach (string fault in new[] { "length", "duplicate", "terminator", "bolts", "short-header", "terminator-length", "terminator-tail" })
            {
                byte[] data = Rc1Fixture();
                int end = 16 + (int)BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(8));
                switch (fault)
                {
                    case "length": BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x1B4), uint.MaxValue); break;
                    case "duplicate": BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x28), 1); break;
                    case "terminator": BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(end - 8), 333); break;
                    case "bolts": BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x1C), 333); break;
                    case "short-header":
                        BinaryPrimitives.WriteUInt32BigEndian(data, (uint)(end - 12));
                        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(8), (uint)(end - 20)); break;
                    case "terminator-length": BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(end - 4), 1); break;
                    case "terminator-tail": BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x28), uint.MaxValue);
                        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x2C), 0); break;
                }
                byte[] original = data.ToArray();
                var snapshot = Rc1SaveInspection.Read(data, "NPEA00385");
                True(!snapshot.Available, "Malformed records must fail: " + fault);
                Equal(0, snapshot.Records.Count);
                Equal(123, SaveData.ReadBolts(data, SaveProfile.ForRegion("NPEA00385"))[0]);
                True(original.SequenceEqual(data), "Failed inspection changed bytes.");
            }
            True(!Rc1SaveInspection.Read(null, "NPEA00385").Available, "Null input must fail safely.");
            True(!Rc1SaveInspection.Read(new byte[40], "NPEA00385").Available, "Invalid block must fail safely.");
            byte[] mismatch = Rc1Fixture();
            BinaryPrimitives.WriteUInt32BigEndian(mismatch.AsSpan(0x1B4), 38);
            var partial = Rc1SaveInspection.Read(mismatch, "NPEA00385");
            True(partial.Available, partial.Message);
            Equal("Status", partial.Table("Weapons & gadgets").Columns[0]);
        });
        Check("RC1 inspector switches game views, displays raw data and keeps native ToD actions isolated", () =>
        {
            string folder = Fixture(root, "NPEA00385");
            File.WriteAllBytes(Path.Combine(folder, "USR-DATA"), Rc1Fixture());
            File.WriteAllBytes(Path.Combine(folder, "PARAM.SFO"), Sfo("NPEA00385", "BCES01503", rpc: true));
            using var session = SaveSession.Open(folder, new FakeTools { FailDecrypt = true }, backupRoot: Path.Combine(root, "rc1-backups"));
            using var form = new Form { ClientSize = new Size(1100, 700) };
            using var inspector = new SaveInspectorControl(); form.Controls.Add(inspector);
            inspector.LoadSession(session); form.Show(); Application.DoEvents();
            True(inspector.HasSnapshot, "RC1 must have an inspection snapshot.");
            var views = inspector.Controls.Find("InspectionView", true).Cast<ComboBox>().Single();
            Alphabetical(views);
            True(views.Items.Contains("Player records") && !views.Items.Contains("Upgrade nodes"), "RC1 should offer mapped views.");
            foreach (string view in views.Items.Cast<string>().ToArray())
            {
                views.SelectedItem = view; Application.DoEvents();
                if (view != "Hex bytes (technical)")
                    True(inspector.Controls.Find("InspectionGrid", true).Cast<DataGridView>().Single().Rows.Count > 0, "RC1 view is empty: " + view);
            }
            views.SelectedItem = "Hex bytes (technical)";
            True(inspector.Controls.Find("HexBytes", true).Cast<TextBox>().Single().Text.StartsWith("USR-DATA plaintext"), "RC1 hex must use USR-DATA.");
            views.SelectedItem = "Weapons & gadgets";
            var grid = inspector.Controls.Find("InspectionGrid", true).Cast<DataGridView>().Single();
            Equal(3, grid.Columns.Count);
            var technical = inspector.Controls.Find("InspectionTechnical", true).Cast<CheckBox>().Single();
            technical.Checked = true; Equal(7, grid.Columns.Count);
            technical.Checked = false; Equal(3, grid.Columns.Count);
            True(inspector.Controls.Find("InspectionDetails", true).Cast<TextBox>().Single().Text.Contains("Flag offset:"), "Readable inspection must retain technical details.");
            using (var bitmap = new Bitmap(form.Width, form.Height))
            {
                form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, bitmap.Size));
                string preview = Path.GetFullPath(Path.Combine("artifacts", "rc1-inspector.png"));
                Directory.CreateDirectory(Path.GetDirectoryName(preview)); bitmap.Save(preview);
            }
            string todFolder = Fixture(root, "BCUS98127");
            File.WriteAllBytes(Path.Combine(todFolder, "GAME.SAV"), EditableFixture());
            using var tod = SaveSession.Open(todFolder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "rc1-backups"));
            inspector.LoadSession(tod);
            True(inspector.HasSnapshot && views.Items.Contains("Upgrade nodes") && !views.Items.Contains("Player records"), "ToD views must return on switching games.");
            inspector.LoadSession(session);
            True(inspector.HasSnapshot && views.Items.Contains("Player records"), "RC1 must reload after ToD.");
            form.Close();
        });
    }

    private static void Rc1ReferenceChecks(string root, string source)
    {
        Check("Actual RC1 trilogy save edits and reopens on a disposable copy with exact byte preservation", () =>
        {
            var original = Snapshot(source);
            string folder = Path.Combine(root, "RC1 reference copy");
            Directory.CreateDirectory(folder);
            foreach (string path in Directory.GetFiles(source)) File.Copy(path, Path.Combine(folder, Path.GetFileName(path)));
            var tools = new FakeTools { FailDecrypt = true, FailEncrypt = true };
            using var session = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-reference-backups"));
            True(Rc1SaveInspection.Supports(session.Metadata.Region), "An RC1 save is required.");
            True(!session.IsEncrypted, "Reference check requires RPCS3 plaintext.");
            var inspection = Rc1SaveInspection.Read(session.ReadInspectionData(), session.Metadata.Region);
            True(inspection.Available, inspection.Message);
            Console.WriteLine($"  {session.Metadata.Region}: {session.Bolts} bolts, {inspection.Length} bytes, {inspection.Records.Count} player records, end 0x{inspection.PlayerEnd:X}.");
            Same(original, Snapshot(session.LastBackup));
            byte[] expected = original["USR-DATA"].ToArray();
            int desired = session.Bolts == 999999 ? 123456 : 999999;
            BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x24), desired);
            BinaryPrimitives.WriteUInt32BigEndian(expected.AsSpan(12), uint.MaxValue);
            string backup = session.Save(desired, 0, Path.Combine(root, "rc1-reference-backups"));
            Same(original, Snapshot(backup));
            True(expected.SequenceEqual(File.ReadAllBytes(Path.Combine(folder, "USR-DATA"))), "Only bolts and the player checksum sentinel may change.");
            using var reopened = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "rc1-reference-backups"));
            Equal(desired, reopened.Bolts); Equal(0, tools.CryptoCalls);
            True(Rc1SaveInspection.Read(reopened.ReadInspectionData(), reopened.Metadata.Region).Available, "Edited save must remain inspectable.");
            foreach (string file in original.Keys.Where(name => name != "USR-DATA"))
                True(original[file].SequenceEqual(File.ReadAllBytes(Path.Combine(folder, file))), "Unrelated file changed: " + file);
            Same(original, Snapshot(source));
        });
    }
}
