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
            Equal(425, TodResearch.Map.GetProperty("annotations").GetArrayLength());
            Equal(60, TodResearch.Map.GetProperty("progression").GetProperty("skill_points").GetProperty("catalog").GetArrayLength());
            Equal(5, TodResearch.Map.GetProperty("progression").GetProperty("armor").GetProperty("catalog").GetArrayLength());
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
            True(upgrades.Columns.SequenceEqual(new[] { "Weapon", "Upgrade", "Status", "Raritanium cost" }), "Upgrade view should show only four plain-language columns.");
            var special = upgrades.Rows.Single(row => row.Cells[0] == "Combuster" && row.Details.Contains("Technical details: node 12."));
            Equal("Duration +4 (special)", special.Cells[1]);
            Equal("Enabled", special.Cells[2]);
            Equal("300", special.Cells[3]);
            True(special.Details.Contains("r3 c5") && special.Details.Contains("[1, 5, 13]") &&
                special.Details.Contains("0x00003FFE") && special.Details.Contains("MOD_DURATION"), "Raw research data must remain in Details.");
            Equal("Damage +5%", upgrades.Rows.First(row => row.Cells[0] == "Combuster" && row.Cells[1] == "Damage +5%").Cells[1]);
            Equal("Starting node", upgrades.Rows[0].Cells[2]);
            Equal("—", upgrades.Rows[0].Cells[3]);
            Equal("Not enabled", upgrades.Rows.First(row => row.Cells[0] == "Grenade" && row.Cells[1] != "Starting node").Cells[2]);
            foreach (string view in new[] { "Weapons & gadgets", "Upgrade nodes", "Skill points", "Armor", "Counters & nearby fields", "Gameplay records", "Save regions", "Prefix words" }) inspection.Table(view);
            inspection.HexBytes(0x5754);
            True(original.SequenceEqual(bytes), "Inspection changed the input.");
            bytes[0x26] = 0;
            Equal((ushort)0xABCD, inspection.Inventory[1].UnknownTail);
        });
        Check("Progression inspection preserves BE64 bit order, independent armor flags and unusual values", () =>
        {
            byte[] bytes = ResearchFixture(), original;
            BinaryPrimitives.WriteUInt64BigEndian(bytes.AsSpan(0x8710, 8), (1UL << 63) | (1UL << 59) | 1);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x8708, 4), 9999);
            bytes[0x870C] = 0xAB;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x448, 4), 2);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x458, 4), 99);
            bytes[0x5775] = 0;
            original = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var skills = inspection.Table("Skill points");
            Equal(60, skills.Rows.Count);
            Equal("Yes", skills.Rows[0].Cells[2]);
            Equal("Yes", skills.Rows[59].Cells[2]);
            Equal("No", skills.Rows[1].Cells[2]);
            Equal("0x8717", skills.Rows[0].Cells[6]);
            Equal("0x8710", skills.Rows[59].Cells[6]);
            True(skills.Rows[0].Details.Contains("8000000000000000") && skills.Rows[0].Details.Contains("Mismatch") &&
                skills.Rows[0].Details.Contains("AB000000"), "Unknown bits, score mismatch and alignment bytes must remain visible.");
            var armor = inspection.Table("Armor");
            Equal(5, armor.Rows.Count);
            Equal("Yes", armor.Rows[1].Cells[2]);
            Equal("0x00000002", armor.Rows[1].Cells[3]);
            Equal("0x00", armor.Rows[1].Cells[5]);
            True(armor.Rows.All(row => row.Cells[4] == "No"), "Invalid equipped ID must not be clamped.");
            True(armor.Rows[1].Details.Contains("outside"), "Unknown equipped ID should be explained.");
            True(original.SequenceEqual(bytes), "New inspector views changed input.");
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
        Check("Friendly presentation keeps exact source data, warnings and unknown field boundaries", () =>
        {
            byte[] bytes = ResearchFixture(), original = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            foreach (string view in new[] { "Weapons & gadgets", "Skill points", "Armor", "Counters & nearby fields", "Gameplay records", "Save regions" })
            {
                var raw = inspection.Table(view);
                var rawCells = raw.Rows.Select(row => string.Join("|", row.Cells)).ToArray();
                var friendly = InspectionPresentation.Simplify(view, raw);
                True(friendly.Columns.Length < raw.Columns.Length, "Default views should remove research-only columns.");
                True(friendly.Rows.All(row => row.Cells.Length == friendly.Columns.Length), "Friendly schemas must be consistent.");
                foreach (var row in friendly.Rows)
                    True(row.Details.Contains(raw.Columns[0] + ": "), "Hidden original columns must remain available in details.");
                True(rawCells.SequenceEqual(raw.Rows.Select(row => string.Join("|", row.Cells))), "Presentation changed raw rows.");
            }
            var skills = InspectionPresentation.Simplify("Skill points", inspection.Table("Skill points"));
            True(!skills.Rows[0].Cells[0].StartsWith("SKILLPOINT_"), "Enum prefixes should not be the default skill label.");
            True(skills.Rows[0].Details.Contains("not a recovered localized"), "Friendly enum labels must not claim to be official titles.");
            True(original.SequenceEqual(bytes), "Presentation changed save bytes.");
            BinaryPrimitives.WriteSingleBigEndian(bytes.AsSpan(0x428, 4), 4f);
            var multiplierInspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var player = InspectionPresentation.Simplify("Counters & nearby fields", multiplierInspection.Table("Counters & nearby fields"));
            var multiplier = player.Rows.Single(row => row.Cells[0] == "Bolt multiplier");
            Equal("4×", multiplier.Cells[1]);
            True(multiplier.Details.Contains("uint32 BE: 1082130432"), "Float presentation must retain the original bits, not display them as an integer multiplier.");
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x18, 4), 0x7FC01234);
            bytes[0x25] = 255;
            var unusual = TodSaveInspection.Read(bytes, "BCUS98127");
            var item = InspectionPresentation.Simplify("Weapons & gadgets", unusual.Table("Weapons & gadgets")).Rows[1];
            Equal("Unknown", item.Cells[2]);
            Equal("Invalid value", item.Cells[3]);
            True(item.Details.Contains("Needs review") && item.Details.Contains("7FC01234"), "Simplification must retain anomalies and exact bits.");
            var unavailable = TodSaveInspection.Read(bytes, "BCUS98124").Table("Armor");
            True(ReferenceEquals(unavailable, InspectionPresentation.Simplify("Armor", unavailable)), "Unsupported-game status must remain intact.");
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
            var friendlyFiles = InspectionPresentation.Simplify("Files & headers", table);
            Equal(account.Cells[3], friendlyFiles.Rows.Single(row => row.Cells[1] == "Account (private)").Cells[2]);
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
            var views = Descendants(inspector).OfType<ComboBox>().Single(c => c.Name == "InspectionView");
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
            form.ClientSize = new Size(1900, 970);
            form.PerformLayout();
            True(grid.Columns.Cast<DataGridViewColumn>().All(c => c.AutoSizeMode == DataGridViewAutoSizeColumnMode.NotSet), "Columns should inherit the grid fill mode.");
            Equal(DataGridViewAutoSizeColumnsMode.Fill, grid.AutoSizeColumnsMode);
            int width = grid.Columns.Cast<DataGridViewColumn>().Sum(c => c.Width);
            True(width >= grid.ClientSize.Width - SystemInformation.VerticalScrollBarWidth - 4 && width <= grid.ClientSize.Width,
                "Columns should fill the wide grid without overflowing it.");
            foreach (string header in new[] { "Item", "XP", "Ammo" })
            {
                var column = grid.Columns[header];
                foreach (DataGridViewRow row in grid.Rows)
                    True(column.Width >= TextRenderer.MeasureText(row.Cells[column.Index].Value.ToString(), grid.Font).Width,
                        "Off-screen or numeric data should not be truncated: " + header);
            }
            var technical = Descendants(inspector).OfType<CheckBox>().Single(c => c.Name == "InspectionTechnical");
            Equal(5, grid.Columns.Count);
            Equal("10", grid.Rows[1].Cells[2].Value.ToString());
            technical.Checked = true;
            Equal(10, grid.Columns.Count);
            Equal("9", grid.Rows[1].Cells[3].Value.ToString());
            technical.Checked = false;
            Equal(5, grid.Columns.Count);
            grid.Sort(grid.Columns["Item"], System.ComponentModel.ListSortDirection.Ascending);
            int combusterRow = grid.Rows.Cast<DataGridViewRow>().Single(row => row.Cells[0].Value.ToString() == "Combuster").Index;
            typeof(DataGridView).GetMethod("OnCellDoubleClick", BindingFlags.Instance | BindingFlags.NonPublic)
                .Invoke(grid, new object[] { new DataGridViewCellEventArgs(0, combusterRow) });
            True(text.Text.Contains("Combuster") && text.Text.Contains("Shipped level tables"), "Sorted friendly rows must retain their weapon IDs.");
            tabs.SelectedIndex = 2;
            foreach (var expected in new[] { ("Skill points", 3, 8), ("Armor", 3, 7), ("Player summary", 2, 6),
                ("Saved locations", 2, 4), ("Save layout", 3, 4), ("Files & metadata", 3, 5) })
            {
                views.SelectedItem = expected.Item1;
                Equal(expected.Item2, grid.Columns.Count);
                True(grid.Rows.Count > 0, "Friendly views must contain information.");
                technical.Checked = true;
                Equal(expected.Item3, grid.Columns.Count);
                technical.Checked = false;
                Equal(expected.Item2, grid.Columns.Count);
            }
            views.SelectedItem = "Player summary";
            Equal(6, grid.Rows.Count);
            True(!grid.Rows.Cast<DataGridViewRow>().Any(row => row.Cells[0].Value.ToString().Contains("Unknown")), "Unknown and candidate fields belong in Technical, not the player summary.");
            views.SelectedItem = "Upgrade nodes";
            var weaponFilter = Descendants(inspector).OfType<ComboBox>().Single(c => c.Name == "UpgradeWeaponFilter");
            True(weaponFilter.Visible, "Upgrade weapon filter should be visible.");
            Equal(204, grid.Rows.Count);
            weaponFilter.SelectedItem = "Combuster";
            Equal(14, grid.Rows.Count);
            True(grid.Rows.Cast<DataGridViewRow>().All(row => row.Cells[0].Value.ToString() == "Combuster"), "Filter must exclude other weapons.");
            weaponFilter.SelectedItem = "Grenade";
            Equal(11, grid.Rows.Count);
            weaponFilter.SelectedItem = "All weapons";
            Equal(204, grid.Rows.Count);
            True(grid.Columns.Cast<DataGridViewColumn>().Sum(c => c.Width) >= grid.ClientSize.Width - SystemInformation.VerticalScrollBarWidth - 4,
                "Switching views should preserve width filling.");
            views.SelectedItem = "Weapons & gadgets";
            True(!weaponFilter.Visible, "Upgrade filter must not appear on other views.");
            form.ClientSize = new Size(1050, 650);
            tabs.SelectedIndex = 3;
            tree.Nodes[1].Expand();
            tree.SelectedNode = tree.Nodes[1].Nodes[1];
            Capture(form, Path.GetFullPath("artifacts/ui-research-expanded.png"));
            using var other = SaveSession.Open(Fixture(root, "BCUS98124"), new FakeTools(), backupRoot: Path.Combine(root, "research-ui-backups"));
            inspector.LoadSession(other);
            views.SelectedItem = "Upgrade nodes";
            Equal(1, weaponFilter.Items.Count);
            True(!weaponFilter.Visible, "Other games must clear and hide the upgrade filter.");
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
            var metadata = SfoMetadata.Read(Path.Combine(folder, "PARAM.SFO"));
            bool plaintext = TodSaveInspection.Read(original["GAME.SAV"], metadata.Region).Available;
            using var tools = new Encryption();
            using var session = SaveSession.Open(folder, tools, decrypted: plaintext, backupRoot: Path.Combine(root, "reference-research-backups"));
            Equal(!plaintext && !metadata.IsRpcS3, session.IsEncrypted);
            var inspection = TodSaveInspection.Read(session.ReadInspectionData(), session.Metadata.Region);
            True(inspection.Available, inspection.Message);
            Equal(32, inspection.Inventory.Count);
            Equal("Combuster", inspection.Inventory[1].Name);
            var bytes = session.ReadInspectionData();
            ulong skillBits = BinaryPrimitives.ReadUInt64BigEndian(bytes.AsSpan(0x8710, 8));
            var skills = inspection.Table("Skill points");
            Equal(60, skills.Rows.Count);
            for (int id = 0; id < 60; id++)
                Equal((skillBits & (1UL << id)) != 0 ? "Yes" : "No", skills.Rows[id].Cells[2]);
            var armor = inspection.Table("Armor");
            Equal(5, armor.Rows.Count);
            for (int id = 0; id < 5; id++)
            {
                uint owned = BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(0x444 + id * 4, 4));
                Equal($"0x{owned:X8}", armor.Rows[id].Cells[3]);
                Equal($"0x{bytes[0x5774 + id]:X2}", armor.Rows[id].Cells[5]);
            }
            Equal(BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(0x20, 4)), inspection.Inventory[1].ModifierMask);
            Equal(BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(0x280, 4)), inspection.AcquisitionCounter);
            Equal((uint)session.Bolts, BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(0x41C, 4)));
            Equal((uint)session.Raritanium, BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(0x420, 4)));
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
            form.ClientSize = new Size(1900, 970);
            Equal(session.Profile.Name.Replace("&", "&&"), Field<GroupBox>(form, "AccountInfoGroupBox").Text);
            True(form.Text.Contains(session.Profile.Name), "The loaded game name must appear in the title.");
            Field<TabControl>(form, "TabControl").SelectedIndex = 0;
            Capture(form, Path.GetFullPath("artifacts/ui-save-information-reference.png"));
            Field<TabControl>(form, "TabControl").SelectedIndex = 2;
            Capture(form, Path.GetFullPath("artifacts/ui-inspector-reference.png"));
            var inspectorViews = Descendants(form).OfType<ComboBox>().Single(c => c.Name == "InspectionView");
            inspectorViews.SelectedItem = "Upgrade nodes";
            var weaponFilter = Descendants(form).OfType<ComboBox>().Single(c => c.Name == "UpgradeWeaponFilter");
            weaponFilter.SelectedItem = "Combuster";
            Capture(form, Path.GetFullPath("artifacts/ui-upgrades-simple-reference.png"));
            form.ClientSize = new Size(499, 248);
            Capture(form, Path.GetFullPath("artifacts/ui-upgrades-simple-compact-reference.png"));
            form.ClientSize = new Size(1900, 970);
            foreach (string view in new[] { "Weapons & gadgets", "Skill points", "Armor", "Player summary", "Saved locations", "Save layout", "Files & metadata" })
            {
                inspectorViews.SelectedItem = view;
                Capture(form, Path.GetFullPath("artifacts/ui-" + view.Replace(" ", "-").ToLowerInvariant() + "-reference.png"));
                form.ClientSize = new Size(499, 248);
                Capture(form, Path.GetFullPath("artifacts/ui-" + view.Replace(" ", "-").ToLowerInvariant() + "-compact-reference.png"));
                var friendlyGrid = Descendants(form).OfType<DataGridView>().Single(c => c.Name == "InspectionGrid");
                True(friendlyGrid.Columns.Cast<DataGridViewColumn>().Sum(column => column.Width) <= friendlyGrid.ClientSize.Width,
                    "Friendly views should fit the compact window: " + view);
                form.ClientSize = new Size(1900, 970);
            }
            True(!Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Reference inspection must not dirty the save.");
            Same(original, Snapshot(folder));
            Console.WriteLine($"Reference {session.Metadata.Region}: {(session.IsEncrypted ? "encrypted PS3" : "plaintext")}, 32 records, {inspection.Inventory.Count(i => i.ScriptOwned)} script-owned, acquisition counter {inspection.AcquisitionCounter}. Source unchanged.");
        });
        Check("Actual ToD save decrypt/edit/encrypt/reopen round-trip uses only a disposable copy", () =>
        {
            var original = Snapshot(folder);
            string copyFolder = Path.Combine(root, "actual-tod-roundtrip");
            Directory.CreateDirectory(copyFolder);
            foreach (string path in Directory.GetFiles(folder)) File.Copy(path, Path.Combine(copyFolder, Path.GetFileName(path)));
            var metadata = SfoMetadata.Read(Path.Combine(copyFolder, "PARAM.SFO"));
            bool plaintext = TodSaveInspection.Read(original["GAME.SAV"], metadata.Region).Available;
            using var tools = new Encryption();
            byte[] expected;
            bool encrypted;
            using (var session = SaveSession.Open(copyFolder, tools, decrypted: plaintext, backupRoot: Path.Combine(root, "reference-roundtrip-backups")))
            {
                encrypted = session.IsEncrypted;
                expected = session.ReadInspectionData();
                int bolts = session.Bolts == int.MaxValue ? session.Bolts - 1 : session.Bolts + 1;
                int raritanium = session.Raritanium == int.MaxValue ? session.Raritanium - 1 : session.Raritanium + 1;
                SaveData.Write(expected, session.Profile, new[] { bolts }, raritanium);
                session.Save(bolts, raritanium, Path.Combine(root, "reference-roundtrip-backups"));
            }
            using var reopened = SaveSession.Open(copyFolder, tools, decrypted: plaintext, backupRoot: Path.Combine(root, "reference-roundtrip-backups"));
            True(expected.SequenceEqual(reopened.ReadInspectionData()), "Reopened plaintext must match every expected byte, including unrelated inventory/world state.");
            True(original["PARAM.SFO"].SequenceEqual(File.ReadAllBytes(Path.Combine(copyFolder, "PARAM.SFO"))), "Original metadata must be preserved.");
            if (encrypted)
                True(PfdBinding.SfoHashes(original["PARAM.PFD"]).SequenceEqual(PfdBinding.SfoHashes(File.ReadAllBytes(Path.Combine(copyFolder, "PARAM.PFD")))),
                    "Actual source account/console/disc bindings must be preserved.");
            Same(original, Snapshot(folder));
        });
    }
}
