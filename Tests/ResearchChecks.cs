using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static byte[] ResearchFixture()
    {
        var bytes = new byte[TodSaveInspection.ExpectedSize];
        for (int id = 0; id < 32; id++) BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(id * 0x14, 4), (uint)id);
        BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x280, 4), 46);
        BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x41C, 4), 123);
        BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x420, 4), 45);
        BinaryPrimitives.WriteSingleBigEndian(bytes.AsSpan(0x18, 4), 83570.79f);
        BinaryPrimitives.WriteSingleBigEndian(bytes.AsSpan(0x1C, 4), 100f);
        BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x20, 4), 0x3FFE);
        bytes[0x24] = 2;
        bytes[0x25] = 9;
        bytes[0x26] = 0xAB;
        bytes[0x27] = 0xCD;
        bytes[0x5755] = 1;
        Encoding.ASCII.GetBytes("metropolis").CopyTo(bytes, 0x8764);
        Encoding.ASCII.GetBytes("gameplay_enemy").CopyTo(bytes, 0x87A4);
        return bytes;
    }

    private static void ResearchChecks(string root)
    {
        Directory.CreateDirectory(Path.GetFullPath("artifacts"));
        Check("All research is bundled: IDs, configurations, grids, annotations and notes", () =>
        {
            Equal(32, TodResearch.Inventory.Count);
            Equal(28, TodResearch.Configs.GetProperty("weapons").EnumerateObject().Count());
            Equal(204, TodResearch.Configs.GetProperty("modifier_count").GetInt32());
            Equal(337, TodResearch.Map.GetProperty("annotations").GetArrayLength());
            var configuration = TodResearch.Map.GetProperty("weapon_configuration");
            Equal(15, configuration.GetProperty("vendor_upgrade_layout").GetProperty("grids").EnumerateObject().Count());
            Equal(24, configuration.GetProperty("native_fields").GetProperty("mods_array_capacity").GetInt32());
            True(TodResearch.ElfNotes.Contains("physics", StringComparison.OrdinalIgnoreCase), "Non-save research is missing.");
            True(TodResearch.SaveNotes.Contains("PARAM SFO"), "Container research is missing.");
            True(TodResearch.WeaponDetails(1).Contains("83570") == false, "Reference save values must not be baked into config definitions.");
            True(TodResearch.WeaponDetails(1).Contains("0x00470378"), "Native binding is missing.");
            True(TodResearch.WeaponDetails(30).Contains("Defaults are unknown"), "Missing gadget defaults must not be invented.");
            for (int id = 0; id < 32; id++) Equal(id, TodResearch.Inventory[id].GetProperty("id").GetInt32());
            foreach (var weapon in TodResearch.Configs.GetProperty("weapons").EnumerateObject())
                True(TodResearch.Inventory.Any(n => n.GetProperty("config_name").GetString() == weapon.Name), "Asset config lacks a native name link.");
        });
        Check("Research decoding uses detached BE values and retains opaque bytes and independent unlocks", () =>
        {
            byte[] bytes = ResearchFixture();
            byte[] original = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCES00052");
            True(inspection.Available, inspection.Message);
            Equal(32, inspection.Inventory.Count);
            var item = inspection.Inventory[1];
            Equal("Combuster", item.Name);
            Equal(83570.79f, item.Xp);
            Equal(100f, item.Ammo);
            Equal(0x3FFEu, item.ModifierMask);
            True(item.ScriptOwned && item.Ownership == 2, "Ownership must test nonzero, not only 1.");
            Equal((byte)9, item.StoredLevel);
            Equal((ushort)0xABCD, item.UnknownTail);
            Equal((byte)1, item.Unlock);
            Equal(46u, inspection.AcquisitionCounter);
            Equal(27, inspection.Table("Gameplay records").Rows.Count);
            Equal("metropolis", inspection.Table("Gameplay records").Rows[0].Cells[1]);
            Equal(1024, inspection.Table("Prefix words").Rows.Count);
            var upgrades = inspection.Table("Upgrade nodes");
            Equal(204, upgrades.Rows.Count);
            var special = upgrades.Rows.Single(row => row.Cells[0] == "Combuster" && row.Cells[1] == "12");
            Equal("Bit set", special.Cells[2]);
            Equal("r3 c5", special.Cells[6]);
            Equal("1, 5, 13", special.Cells[8]);
            foreach (string view in new[] { "Weapons & gadgets", "Upgrade nodes", "Counters & nearby fields", "Gameplay records", "Save regions", "Prefix words" }) inspection.Table(view);
            inspection.HexBytes(0x5754);
            True(original.SequenceEqual(bytes), "Inspection changed the input.");
            bytes[0x26] = 0;
            Equal((ushort)0xABCD, inspection.Inventory[1].UnknownTail);
        });
        Check("Research refuses other games, sizes and mismatched IDs without guessing", () =>
        {
            byte[] bytes = ResearchFixture();
            foreach (string region in new[] { "BCUS98124", "NPUA80908", "NPEA00452", "UNKNOWN01", null })
                True(!TodSaveInspection.Read(bytes, region).Available, "Unverified region must not be decoded.");
            True(!TodSaveInspection.Read(null, "BCUS98127").Available, "Null data must not be decoded.");
            True(!TodSaveInspection.Read(bytes[..^1], "BCUS98127").Available, "Truncated layout must be refused.");
            True(!TodSaveInspection.Read(bytes.Concat(new byte[] { 0 }).ToArray(), "BCUS98127").Available, "Different layout size must be refused.");
            bytes[31 * 0x14 + 3] = 30;
            True(!TodSaveInspection.Read(bytes, "BCUS98127").Available, "All IDs must be checked.");
        });
        Check("Nonfinite floats, bit31 and unusual levels are shown without repair or clamping", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x18, 4), 0x7FC01234);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x1C, 4), 0x7F800000);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x20, 4), 0x80000000);
            bytes[0x25] = 255;
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            Equal(0x7FC01234u, inspection.Inventory[1].XpBits);
            Equal(0x80000000u, inspection.Inventory[1].ModifierMask);
            Equal((byte)255, inspection.Inventory[1].StoredLevel);
            var row = inspection.Table("Weapons & gadgets").Rows[1];
            True(row.Details.Contains("7FC01234") && row.Details.Contains("[31]") && row.Details.Contains("Nonfinite"), "Raw unusual values must be preserved and explained.");
            True(row.Cells[9].Contains("outside") && row.Cells[9].Contains("absent"), "Unexpected values should be flagged, not rewritten.");
        });
        Check("Hex inspection is bounded, including the last byte", () =>
        {
            var inspection = TodSaveInspection.Read(ResearchFixture(), "BCUS98127");
            True(inspection.HexBytes(TodSaveInspection.ExpectedSize - 1).Contains("000906EF"), "Last byte should be readable.");
            Throws<ArgumentOutOfRangeException>(() => inspection.HexBytes(-1));
            Throws<ArgumentOutOfRangeException>(() => inspection.HexBytes(TodSaveInspection.ExpectedSize));
            Throws<ArgumentOutOfRangeException>(() => inspection.HexBytes(0, 4097));
        });
        Check("Container inspection redacts private data, survives malformed headers and leaves files unchanged", () =>
        {
            string folder = Fixture(root, "BCUS98127");
            byte[] game = ResearchFixture();
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), game);
            CreatePfd(folder, SaveProfile.ForRegion("BCUS98127"), 4);
            using (var image = new Bitmap(2, 3)) image.Save(Path.Combine(folder, "ICON0.PNG"));
            var original = Snapshot(folder);
            var table = SaveContainerInspection.Read(folder, "GAME.SAV", game);
            var account = table.Rows.Single(row => row.Cells[2] == "ACCOUNT_ID");
            True(account.Cells[3].Contains("redacted"), "Account bindings must not be exported.");
            True(table.Rows.Any(row => row.Cells[0] == "PARAM.PFD" && row.Cells[2] == "Entry 0"), "PFD entries should be parsed.");
            True(table.Rows.Any(row => row.Cells[0] == "ICON0.PNG" && row.Cells[2] == "IEND"), "PNG chunks should be parsed.");
            Same(original, Snapshot(folder));
            File.WriteAllBytes(Path.Combine(folder, "ICON0.PNG"), new byte[33]);
            File.WriteAllBytes(Path.Combine(folder, "PARAM.PFD"), new byte[120]);
            File.WriteAllBytes(Path.Combine(folder, "PARAM.SFO"), new byte[20]);
            var malformed = Snapshot(folder);
            table = SaveContainerInspection.Read(folder, "GAME.SAV", game);
            Equal(3, table.Rows.Count(row => row.Cells[2] == "Inspection unavailable"));
            Same(malformed, Snapshot(folder));
        });
        Check("Inspection snapshots follow successful commits, exclude pending edits and never expose session buffers", () =>
        {
            string folder = Fixture(root, "BCUS98127");
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), ResearchFixture());
            var original = Snapshot(folder);
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "research-backups"));
            byte[] copy = session.ReadInspectionData();
            copy[0x41F] = 0;
            Equal(123u, BinaryPrimitives.ReadUInt32BigEndian(session.ReadInspectionData().AsSpan(0x41C, 4)));
            TodSaveInspection.Read(session.ReadInspectionData(), session.Metadata.Region);
            Same(original, Snapshot(folder));
            session.Save(999, 987, Path.Combine(root, "research-backups"));
            Equal(999u, BinaryPrimitives.ReadUInt32BigEndian(session.ReadInspectionData().AsSpan(0x41C, 4)));
            Equal(987u, BinaryPrimitives.ReadUInt32BigEndian(session.ReadInspectionData().AsSpan(0x420, 4)));
        });
        Check("Research UI works before opening, stays read-only and resets across games", () =>
        {
            using var form = new MainForm();
            form.StartPosition = FormStartPosition.Manual;
            form.Location = new Point(-20000, -20000);
            form.ShowInTaskbar = false;
            form.Show();
            var tabs = Field<TabControl>(form, "TabControl");
            tabs.SelectedIndex = 3;
            var tree = Descendants(form).OfType<TreeView>().Single();
            var search = Descendants(form).OfType<TextBox>().Single(c => c.Name == "ResearchSearch");
            var text = Descendants(form).OfType<TextBox>().Single(c => c.Name == "ResearchDetails");
            True(tree.Nodes.Count > 0 && text.ReadOnly && tabs.SelectedTab.Enabled, "Embedded research should be usable without a save.");
            search.Text = "Combuster";
            True(tree.Nodes.Count > 0, "Search should find names.");
            True(text.Text.Contains("Combuster"), "Search should select a matching finding, not only a parent section.");
            search.Text = "no-such-research-finding-XYZ";
            Equal(0, tree.Nodes.Count);
            Equal("No matching findings.", text.Text);
            search.Text = "";
            string folder = Fixture(root, "BCUS98127");
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), ResearchFixture());
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "research-ui-backups"));
            typeof(MainForm).GetField("session", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(form, session);
            typeof(MainForm).GetMethod("ShowSession", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(form, null);
            typeof(MainForm).GetMethod("SetBusy", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(form, new object[] { false });
            tabs.SelectedIndex = 2;
            var inspector = Field<SaveInspectorControl>(form, "saveInspector");
            var grid = Descendants(inspector).OfType<DataGridView>().Single();
            var views = Descendants(inspector).OfType<ComboBox>().Single();
            True(grid.ReadOnly && !grid.AllowUserToAddRows && !grid.AllowUserToDeleteRows, "Research must not offer edits.");
            Equal(32, grid.Rows.Count);
            typeof(DataGridView).GetMethod("OnCellDoubleClick", BindingFlags.Instance | BindingFlags.NonPublic)
                .Invoke(grid, new object[] { new DataGridViewCellEventArgs(0, 1) });
            Equal(3, tabs.SelectedIndex);
            True(text.Text.Contains("Combuster") && text.Text.Contains("Shipped level tables"), "Weapon navigation must show the correct embedded definition.");
            tabs.SelectedIndex = 2;
            foreach (string view in views.Items) views.SelectedItem = view;
            views.SelectedIndex = 0;
            True(!Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Browsing research must not dirty the session.");
            Capture(form, Path.GetFullPath("artifacts/ui-research-compact.png"));
            form.ClientSize = new Size(1050, 650);
            Capture(form, Path.GetFullPath("artifacts/ui-inspector-expanded.png"));
            tabs.SelectedIndex = 3;
            tree.Nodes[1].Expand();
            tree.SelectedNode = tree.Nodes[1].Nodes[1];
            Capture(form, Path.GetFullPath("artifacts/ui-research-expanded.png"));
            using var other = SaveSession.Open(Fixture(root, "BCUS98124"), new FakeTools(), backupRoot: Path.Combine(root, "research-ui-backups"));
            inspector.LoadSession(other);
            True(!inspector.HasSnapshot, "Other games must clear the previous ToD inspection.");
            Equal(1, grid.Rows.Count);
            True(!grid.Rows[0].Cells[0].Value.ToString().Contains("Combuster"), "Old weapon rows leaked across games.");
        });
    }

    private static void ReferenceResearchChecks(string root, string folder)
    {
        Check("Original reference ToD save loads in the UI without changing any source file", () =>
        {
            var original = Snapshot(folder);
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "reference-research-backups"));
            var inspection = TodSaveInspection.Read(session.ReadInspectionData(), session.Metadata.Region);
            True(inspection.Available, inspection.Message);
            Equal(32, inspection.Inventory.Count);
            Equal("Combuster", inspection.Inventory[1].Name);
            Equal(0x3FFEu, inspection.Inventory[1].ModifierMask);
            Equal(46u, inspection.AcquisitionCounter);
            var files = SaveContainerInspection.Read(session.WorkingFolder, session.Profile.FileName, session.ReadInspectionData());
            True(!files.Rows.Any(r => r.Cells[2] == "Inspection unavailable"), "Reference headers should parse cleanly.");
            using var form = new MainForm();
            form.Location = new Point(-20000, -20000);
            form.StartPosition = FormStartPosition.Manual;
            form.ShowInTaskbar = false;
            form.Show();
            typeof(MainForm).GetField("session", BindingFlags.Instance | BindingFlags.NonPublic).SetValue(form, session);
            typeof(MainForm).GetMethod("ShowSession", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(form, null);
            typeof(MainForm).GetMethod("SetBusy", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(form, new object[] { false });
            form.ClientSize = new Size(1050, 650);
            Field<TabControl>(form, "TabControl").SelectedIndex = 2;
            Capture(form, Path.GetFullPath("artifacts/ui-inspector-reference.png"));
            True(!Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Reference inspection must not dirty the save.");
            Same(original, Snapshot(folder));
        });
    }
}
