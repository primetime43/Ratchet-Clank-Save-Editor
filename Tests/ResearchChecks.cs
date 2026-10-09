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
        Check("Gameplay segments preserve completion bytes, scalar types, unknown tails and physical bounds", () =>
        {
            byte[] bytes = ResearchFixture(), before = bytes.ToArray();
            int offset = 0x488 + 19 * 0x408 + 9 * 0x30;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(offset, 4), 0x7FC12345);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(offset + 8, 4), uint.MaxValue);
            bytes[offset + 0x2C] = 7;
            bytes[offset + 0x2D] = 0xAB;
            bytes[offset + 0x2E] = 0xCD;
            bytes[offset + 0x2F] = 0xEF;
            before = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var raw = inspection.Table("Gameplay segments");
            Equal(200, raw.Rows.Count);
            Equal(8, raw.Columns.Length);
            var last = raw.Rows[^1];
            Equal("19", last.Cells[0]); Equal("9", last.Cells[2]);
            Equal("Recorded", last.Cells[3]); Equal("4294967295", last.Cells[4]);
            True(last.Details.Contains("7FC12345") && last.Details.Contains("ABCDEF"), "Raw nonfinite bits and unknown bytes must survive.");
            var friendly = InspectionPresentation.Simplify("Gameplay segments", raw);
            Equal(190, friendly.Rows.Count); Equal(5, friendly.Columns.Length);
            True(friendly.Rows[0].Details.Contains("not wallet balances"), "Accumulators must not become currency balances.");
            True(bytes.SequenceEqual(before), "Segment inspection modified input.");
            Array.Clear(bytes);
            Equal("4294967295", inspection.Table("Gameplay segments").Rows[^1].Cells[4]);
        });
        Check("Gameplay log distinguishes stale buffer entries, integer reset counts and malformed saved counts", () =>
        {
            byte[] bytes = ResearchFixture();
            int last = 0x8764 + 199 * 0x9C;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(last + 0x98, 4), 2);
            var raw = TodSaveInspection.Read(bytes, "BCUS98127").Table("Gameplay records");
            Equal(200, raw.Rows.Count); Equal(5, raw.Columns.Length);
            Equal("Retained beyond saved count", raw.Rows[0].Cells[4]);
            Equal("Unused / zero", raw.Rows[1].Cells[4]);
            True(raw.Rows[^1].Details.Contains("reset_events: 2; bits 00000002"), "Counter must be an integer, not a denormal float.");
            Equal(2, InspectionPresentation.Simplify("Gameplay records", raw).Rows.Count);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x10144, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            raw = TodSaveInspection.Read(bytes, "BCUS98127").Table("Gameplay records");
            Equal(200, raw.Rows.Count);
            True(raw.Rows[^1].Details.Contains("Count exceeds buffer"), "Malformed count must remain visible while reads are bounded.");
            Equal("Within saved count", raw.Rows[^1].Cells[4]);
            True(bytes.SequenceEqual(before), "Log inspection modified input.");
        });
        Check("Global event flags preserve BE64 ordering, all320 physical bits and detached input", () =>
        {
            byte[] bytes = ResearchFixture();
            int[] set = { 0, 7, 8, 10, 63, 64, 127, 128, 191, 192, 255, 256, 291, 292, 319 };
            foreach (int id in set)
            {
                int offset = 0x5528 + id / 64 * 8;
                ulong word = BinaryPrimitives.ReadUInt64BigEndian(bytes.AsSpan(offset, 8)) | (1UL << (id % 64));
                BinaryPrimitives.WriteUInt64BigEndian(bytes.AsSpan(offset, 8), word);
            }
            Array.Fill(bytes, (byte)255, 0x5550, 8);
            byte[] before = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var raw = inspection.Table("Global event flags");
            Equal(320, raw.Rows.Count);
            Equal(8, raw.Columns.Length);
            for (int id = 0; id < 320; id++) Equal(set.Contains(id) ? "Set" : "Clear", raw.Rows[id].Cells[3]);
            Equal("0x552F", raw.Rows[0].Cells[4]);
            Equal("0x5528", raw.Rows[63].Cells[4]);
            Equal("0x5537", raw.Rows[64].Cells[4]);
            Equal("HERO_HAS_TWO_ITEMS", raw.Rows[10].Cells[1]);
            Equal("UNMAPPED_BIT_292", raw.Rows[292].Cells[1]);
            Equal("8000001800000001", raw.Rows[319].Cells[7]);
            var friendly = InspectionPresentation.Simplify("Global event flags", raw);
            Equal(292, friendly.Rows.Count);
            Equal(3, friendly.Columns.Length);
            Equal("Set", friendly.Rows[10].Cells[2]);
            True(friendly.Rows[10].Details.Contains("not a story-completion checklist"), "Recorded flags must not become an unsupported completion verdict.");
            True(bytes.SequenceEqual(before), "Flag viewing must not modify input.");
            Array.Clear(bytes);
            Equal("Set", inspection.Table("Global event flags").Rows[319].Cells[3]);
        });
        Check("Arena successes use23 direct-ID counters, not24 menu slots, and preserve signed raw values", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x56D8, 4), 0xDEADBEEF);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x56F4, 4), 0x80000000);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x5730, 4), uint.MaxValue);
            for (int i = 0; i < 32; i++) bytes[0x5734 + i] = (byte)i;
            byte[] before = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var raw = inspection.Table("Arena challenges");
            Equal(23, raw.Rows.Count);
            Equal(7, raw.Columns.Length);
            Equal("DEADBEEF", raw.Rows[0].Cells[6]);
            Equal("IFF_A_7", raw.Rows[7].Cells[1]);
            Equal("-2147483648", raw.Rows[7].Cells[3]);
            Equal("0x56F4", raw.Rows[7].Cells[5]);
            Equal("-1", raw.Rows[22].Cells[3]);
            Equal("0x5730", raw.Rows[22].Cells[5]);
            True(raw.Rows[7].Details.Contains(Convert.ToHexString(bytes.AsSpan(0x5734, 32))), "Adjacent unknown bytes must be retained separately.");
            var friendly = InspectionPresentation.Simplify("Arena challenges", raw);
            Equal(22, friendly.Rows.Count);
            Equal(3, friendly.Columns.Length);
            Equal("Whip It Good", friendly.Rows[6].Cells[0]);
            True(friendly.Rows[6].Details.Contains("not a live payout"), "Base rewards must not be presented as current payout.");
            True(bytes.SequenceEqual(before), "Viewing arena counters must not change the save.");
            Array.Clear(bytes);
            Equal("80000000", inspection.Table("Arena challenges").Rows[7].Cells[6]);
        });
        Check("Saved settings preserve raw flags, nonfinite floats, unknown bytes and detached input", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x114A8, 4), 0x80000000);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x114C4, 4), 0x7FC12345);
            BinaryPrimitives.WriteSingleBigEndian(bytes.AsSpan(0x114C8, 4), 0.9f);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x114C0, 4), 0xDEADBEEF);
            bytes[0x114D0] = 255;
            bytes[0x114D6] = 0xAB; bytes[0x114D7] = 0xCD;
            byte[] before = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var raw = inspection.Table("Game settings");
            Equal(17, raw.Rows.Count);
            Equal(5, raw.Columns.Length);
            Equal("On", raw.Rows.Single(r => r.Cells[2] == "0x114A8").Cells[1]);
            Equal("7FC12345", raw.Rows.Single(r => r.Cells[2] == "0x114C4").Cells[4]);
            Equal("90%", raw.Rows.Single(r => r.Cells[2] == "0x114C8").Cells[1]);
            Equal("FF", raw.Rows.Single(r => r.Cells[2] == "0x114D0").Cells[4]);
            Equal("ABCD", raw.Rows.Single(r => r.Cells[2] == "0x114D6").Cells[4]);
            var friendly = InspectionPresentation.Simplify("Game settings", raw);
            Equal(15, friendly.Rows.Count);
            Equal(2, friendly.Columns.Length);
            True(friendly.Rows.Any(r => r.Details.Contains("7FC12345")), "Nonfinite float bits must remain in row details.");
            True(bytes.SequenceEqual(before), "Viewing settings must not modify input bytes.");
            Array.Clear(bytes);
            True(inspection.Table("Game settings").Rows.Select(r => string.Join("|", r.Cells)).SequenceEqual(raw.Rows.Select(r => string.Join("|", r.Cells))), "Settings snapshot must be detached.");
        });
        Check("Load destination and next-level summary use a catalog without guessing the current planet", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x8740, 4), uint.MaxValue);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x906E8, 4), 10);
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var summary = InspectionPresentation.Simplify("Counters & nearby fields", inspection.Table("Counters & nearby fields"));
            Equal("Unmapped ID 4294967295", summary.Rows.Single(r => r.Cells[0] == "Next-level selection").Cells[1]);
            Equal("Sargasso", summary.Rows.Single(r => r.Cells[0] == "Saved load destination").Cells[1]);
            True(!summary.Rows.Any(r => r.Cells[0].Contains("Current planet")), "Load destination is not necessarily the current planet.");
            var settings = TodResearch.Map.GetProperty("settings");
            Equal("0x10330610", settings.GetProperty("runtime_only").GetProperty("checkpoint_va").GetString());
            True(settings.GetProperty("runtime_only").GetProperty("warning").GetString().Contains("no saved health offset"), "Runtime health must not be presented as a saved field.");
        });
        Check("All research is bundled: IDs, configurations, grids, annotations and notes", () =>
        {
            Equal(32, TodResearch.Inventory.Count);
            Equal(28, TodResearch.Configs.GetProperty("weapons").EnumerateObject().Count());
            Equal(204, TodResearch.Configs.GetProperty("modifier_count").GetInt32());
            Equal(1152, TodResearch.Map.GetProperty("annotations").GetArrayLength());
            Equal(292, TodResearch.Map.GetProperty("global_flags").GetProperty("catalog").GetArrayLength());
            Equal(15, TodResearch.Map.GetProperty("settings").GetProperty("block").GetProperty("fields").GetArrayLength());
            Equal(21, TodResearch.Map.GetProperty("state_storage").GetProperty("rle_blocks").GetProperty("count").GetInt32());
            Equal(13, TodResearch.Map.GetProperty("bonuses").GetProperty("blueprints").GetProperty("all_grant_ids").GetArrayLength());
            Equal(14, TodResearch.Map.GetProperty("bonuses").GetProperty("cheats").GetProperty("catalog").GetArrayLength());
            Equal(10, TodResearch.Map.GetProperty("mission_lists").GetProperty("capacity_per_list").GetInt32());
            Equal(23, TodResearch.Map.GetProperty("objects").GetProperty("catalog").GetArrayLength());
            Equal(19, TodResearch.Map.GetProperty("world_state").GetProperty("worlds").GetProperty("catalog").GetArrayLength());
            Equal(19, TodResearch.Map.GetProperty("collectibles").GetProperty("special_bolts").GetProperty("catalog").GetArrayLength());
            Equal(9, TodResearch.Map.GetProperty("collectibles").GetProperty("skins").GetProperty("catalog").GetArrayLength());
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
            Equal(200, inspection.Table("Gameplay records").Rows.Count);
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
        Check("Collectible and skin inspection preserves unusual masks, signed balances and independent selections", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x418, 4), 2315144);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x424, 4), 5);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0xC7C, 4), 0x80000001);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x550C, 4), 0xFFFFFFFF);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x460, 4), 2);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x480, 4), 99);
            byte[] original = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var bolts = inspection.Table("Special bolts");
            Equal(19, bolts.Rows.Count);
            Equal("2", bolts.Rows[1].Cells[2]);
            True(bolts.Rows[1].Details.Contains("balance -3") && bolts.Rows[1].Details.Contains("[0, 31]") &&
                bolts.Rows[1].Details.Contains("FFFFFFFF") && bolts.Rows[1].Cells[6].Contains("exceeds"), "Native count must include bit31 and exclude initialized slot19 without repairing anything.");
            var skins = inspection.Table("Skins");
            Equal(9, skins.Rows.Count);
            Equal("Yes", skins.Rows[1].Cells[2]);
            Equal("6", skins.Rows[1].Cells[4]);
            Equal("0x00000002", skins.Rows[1].Cells[5]);
            True(skins.Rows.All(row => row.Cells[3] == "No") && skins.Rows[1].Details.Contains("outside"), "Invalid selected IDs must remain unchanged.");
            var summary = InspectionPresentation.Simplify("Counters & nearby fields", inspection.Table("Counters & nearby fields"));
            Equal("2315144", summary.Rows.Single(row => row.Cells[0] == "Hero XP").Cells[1]);
            Equal("5", summary.Rows.Single(row => row.Cells[0] == "Special bolts spent").Cells[1]);
            True(original.SequenceEqual(bytes), "New read-only views changed bytes.");
        });
        Check("World and quick-select views preserve nonboolean flags, unsigned counters and unknown signed IDs", () =>
        {
            byte[] bytes = ResearchFixture();
            for (int slot = 0; slot < 32; slot++) BinaryPrimitives.WriteInt32BigEndian(bytes.AsSpan(0x284 + slot * 4, 4), -1);
            bytes[0xC90] = 2;
            bytes[0xC91] = 3;
            bytes[0xC92] = 4;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x10BEC, 4), uint.MaxValue);
            BinaryPrimitives.WriteInt32BigEndian(bytes.AsSpan(0x284, 4), -2);
            BinaryPrimitives.WriteInt32BigEndian(bytes.AsSpan(0x288, 4), 1);
            BinaryPrimitives.WriteInt32BigEndian(bytes.AsSpan(0x300, 4), 99);
            byte[] original = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var worlds = inspection.Table("World progress");
            Equal(19, worlds.Rows.Count);
            Equal("Yes", worlds.Rows[1].Cells[2]);
            Equal("Yes", worlds.Rows[1].Cells[3]);
            Equal("4294967295", worlds.Rows[1].Cells[4]);
            Equal("0x04", worlds.Rows[1].Cells[5]);
            True(worlds.Rows[1].Details.Contains("0x02") && worlds.Rows[1].Details.Contains("not a completion percentage"), "Nonboolean flags and limitations must survive simplification.");
            var quick = inspection.Table("Quick select");
            Equal(32, quick.Rows.Count);
            Equal("Unknown (-2)", quick.Rows[0].Cells[2]);
            Equal("Combuster", quick.Rows[1].Cells[2]);
            Equal("Empty", quick.Rows[2].Cells[2]);
            Equal("Yes", quick.Rows[23].Cells[3]);
            Equal("No", quick.Rows[24].Cells[3]);
            Equal("Unknown (99)", quick.Rows[31].Cells[2]);
            Equal(4, InspectionPresentation.Simplify("World progress", worlds).Columns.Length);
            Equal(2, InspectionPresentation.Simplify("Quick select", quick).Columns.Length);
            True(original.SequenceEqual(bytes), "Read-only views must not normalize unknown flags or IDs.");
        });
        Check("Object inspection preserves signed counts and independent unsigned high-water/addition counters", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteInt32BigEndian(bytes.AsSpan(0x304, 4), -2);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x360, 4), 0xFFFFFFFF);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x3BC, 4), 0x80000000);
            byte[] original = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Objects & equipment");
            Equal(23, table.Rows.Count);
            Equal("OBJ_HELI_PACK", table.Rows[0].Cells[1]);
            Equal("-2", table.Rows[0].Cells[2]);
            Equal("4294967295", table.Rows[0].Cells[3]);
            Equal("2147483648", table.Rows[0].Cells[4]);
            Equal("Yes", table.Rows[0].Cells[5]);
            Equal("0x35C", table.Rows[22].Cells[6]);
            Equal("0x3B8", table.Rows[22].Cells[7]);
            Equal("0x414", table.Rows[22].Cells[8]);
            var friendly = InspectionPresentation.Simplify("Objects & equipment", table);
            Equal(2, friendly.Columns.Length);
            Equal("Heli Pack", friendly.Rows[0].Cells[0]);
            True(friendly.Rows[0].Details.Contains("FFFFFFFE") && friendly.Rows[0].Details.Contains("not unique"), "Raw bits and counter caveats must survive presentation.");
            True(original.SequenceEqual(bytes), "Object inspection changed bytes.");
        });
        Check("Mission details bound malformed list counts and retain unknown flags and lookup IDs", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x101C0, 4), uint.MaxValue);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x10148, 4), 1234);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x1014C, 4), 5678);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x10150, 4), 0x80000003);
            byte[] original = bytes.ToArray();
            string detail = TodSaveInspection.Read(bytes, "BCUS98127").Table("World progress").Rows[0].Details;
            True(detail.Contains("saved count 4294967295") && detail.Contains("Exceeds capacity10"), "Malformed counts must remain visible without unbounded reads.");
            True(detail.Contains("title lookup ID 1234") && detail.Contains("description lookup ID 5678"), "Lookup IDs must not be guessed localized titles.");
            True(detail.Contains("optional Yes, complete Yes, available No") && detail.Contains("unknown bits0x80000000"), "Flag semantics and opaque bits must remain independent.");
            True(detail.Contains("Slot 9:") && !detail.Contains("Slot 10:"), "Do not read beyond the ten physical entries.");
            True(original.SequenceEqual(bytes), "Mission details must never repair counts or clear flags.");
        });
        Check("Blueprint and bonus inspection preserves unknown bits and distinguishes state from unlocks", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x86F4, 4), 0x8007DEE4);
            bytes[0x86F9] = 255;
            bytes[0x8706] = 0xAB;
            byte[] original = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var raw = inspection.Table("Blueprints");
            Equal(32, raw.Rows.Count);
            Equal("Yes", raw.Rows[31].Cells[1]);
            Equal("No", raw.Rows[31].Cells[2]);
            var friendly = InspectionPresentation.Simplify("Blueprints", raw);
            Equal(2, friendly.Columns.Length);
            Equal(14, friendly.Rows.Count);
            True(friendly.Rows.Any(row => row.Cells[0] == "Blueprint ID 31 (unmapped)" && row.Cells[1] == "Yes"), "Unexpected set bits must remain visible.");
            True(raw.Rows[0].Details.Contains("count: 14") && raw.Rows[0].Details.Contains("80000000"), "Native count includes all set bits, not only known IDs.");
            var bonuses = inspection.Table("Bonuses & cheats");
            Equal(14, bonuses.Rows.Count);
            Equal("255", bonuses.Rows[1].Cells[2]);
            True(bonuses.Rows[1].Details.Contains("value preserved") && bonuses.Rows[0].Details.Contains("does not mean locked"), "State bytes must not be normalized or mislabeled as unlocks.");
            Equal(3, InspectionPresentation.Simplify("Bonuses & cheats", bonuses).Columns.Length);
            True(original.SequenceEqual(bytes), "Blueprint/bonus views changed bytes.");
        });
        Check("Native RLE inspection bounds runs and retains equipment history and malformed block headers", () =>
        {
            byte[] stream = Enumerable.Range(0, 4).SelectMany(_ => new byte[] { 0, 0, 255, 255 }).Concat(new byte[] { 5 }).ToArray();
            var decoded = TodRleInspection.Decode(stream);
            Equal(0x40000, decoded.DecodedSize);
            Equal(4, decoded.ClippedBytes);
            Equal(1, decoded.TrailingBytes);
            Equal(4 * 65535, decoded.EncoderAccumulator);
            Equal(0x40000, decoded.Histogram[0]);
            Equal(Convert.ToHexString(SHA256.HashData(new byte[0x40000])), decoded.Sha256);
            foreach (byte[] invalid in new[] { new byte[] { 0, 0 }, new byte[] { 0, 0, 1 }, new byte[0x6000] })
            {
                bool refused = false;
                try { TodRleInspection.Decode(invalid); } catch (ArgumentException) { refused = true; }
                True(refused, "Malformed RLE must be bounded and refused without native overreads.");
            }
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x42C, 4), 15);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x430, 4), uint.MaxValue);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x434, 4), 999);
            bytes[0x114D8 + 0xCC] = 255;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x114D8 + 0x60D0, 4), uint.MaxValue);
            byte[] original = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var table = inspection.Table("Stored state blocks");
            Equal(21, table.Rows.Count);
            Equal("4294967295", table.Rows[0].Cells[2]);
            True(table.Rows[0].Details.Contains("exceeds native"), "Invalid lengths must remain visible without allocating unbounded output.");
            var summary = InspectionPresentation.Simplify("Counters & nearby fields", inspection.Table("Counters & nearby fields"));
            Equal("Ryno", summary.Rows.Single(row => row.Cells[0] == "Last recorded equipped item").Cells[1]);
            Equal("Unspecified (-1)", summary.Rows.Single(row => row.Cells[0] == "Previously recorded equipped item").Cells[1]);
            Equal("Unknown item ID 999", summary.Rows.Single(row => row.Cells[0] == "Older recorded equipped item").Cells[1]);
            True(original.SequenceEqual(bytes), "RLE and history inspection must not rewrite data.");
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
            foreach (string view in new[] { "Weapons & gadgets", "Skill points", "Armor", "Skins", "Special bolts", "World progress", "Quick select", "Counters & nearby fields", "Gameplay records", "Save regions" })
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
            foreach (var expected in new[] { ("Skill points", 3, 8), ("Armor", 3, 7), ("Skins", 4, 7), ("Special bolts", 3, 7), ("Player summary", 2, 6),
                ("Objects & equipment", 2, 9), ("Blueprints", 2, 7), ("Bonuses & cheats", 3, 8), ("Stored state blocks", 4, 8), ("World progress", 4, 9), ("Gameplay segments", 5, 8), ("Quick select", 2, 6), ("Saved locations", 3, 5), ("Save layout", 3, 4), ("Files & metadata", 3, 5) })
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
            Equal(14, grid.Rows.Count);
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
            var specialBolts = inspection.Table("Special bolts");
            Equal(19, specialBolts.Rows.Count);
            for (int id = 0; id < 19; id++)
                Equal(System.Numerics.BitOperations.PopCount(BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(0x874 + id * 0x408, 4))).ToString(), specialBolts.Rows[id].Cells[2]);
            var skins = inspection.Table("Skins");
            Equal(9, skins.Rows.Count);
            for (int id = 0; id < 9; id++)
                Equal($"0x{BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(0x45C + id * 4, 4)):X8}", skins.Rows[id].Cells[5]);
            var worlds = inspection.Table("World progress");
            Equal(19, worlds.Rows.Count);
            for (int id = 0; id < 19; id++)
            {
                Equal(bytes[0x888 + id * 0x408] != 0 ? "Yes" : "No", worlds.Rows[id].Cells[2]);
                Equal(bytes[0x889 + id * 0x408] != 0 ? "Yes" : "No", worlds.Rows[id].Cells[3]);
                Equal(BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(0x10B70 + id * 0x7C, 4)).ToString(), worlds.Rows[id].Cells[4]);
            }
            var quick = inspection.Table("Quick select");
            Equal(32, quick.Rows.Count);
            for (int slot = 0; slot < 32; slot++)
                Equal(BinaryPrimitives.ReadInt32BigEndian(bytes.AsSpan(0x284 + slot * 4, 4)).ToString(), quick.Rows[slot].Cells[1]);
            var blocks = inspection.Table("Stored state blocks");
            Equal(21, blocks.Rows.Count);
            var arena = inspection.Table("Arena challenges");
            Equal(23, arena.Rows.Count);
            for (int id = 0; id < 23; id++)
                Equal(BinaryPrimitives.ReadInt32BigEndian(bytes.AsSpan(0x56D8 + id * 4, 4)).ToString(), arena.Rows[id].Cells[3]);
            var events = inspection.Table("Global event flags");
            Equal(320, events.Rows.Count);
            for (int id = 0; id < 320; id++)
            {
                ulong word = BinaryPrimitives.ReadUInt64BigEndian(bytes.AsSpan(0x5528 + id / 64 * 8, 8));
                Equal((word & (1UL << (id % 64))) != 0 ? "Set" : "Clear", events.Rows[id].Cells[3]);
            }
            var segments = inspection.Table("Gameplay segments");
            Equal(200, segments.Rows.Count);
            for (int level = 0; level < 20; level++)
            {
                for (int slot = 0; slot < 10; slot++)
                {
                    int offset = 0x488 + level * 0x408 + slot * 0x30;
                    Equal(BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(offset + 8, 4)).ToString(), segments.Rows[level * 10 + slot].Cells[4]);
                    Equal(bytes[offset + 0x2C] != 0 ? "Recorded" : "Not recorded", segments.Rows[level * 10 + slot].Cells[3]);
                }
            }
            var logs = inspection.Table("Gameplay records");
            uint logCount = BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(0x10144, 4));
            Equal(200, logs.Rows.Count);
            Equal(Math.Min(logCount, 200u), (uint)logs.Rows.Count(r => r.Cells[4] == "Within saved count"));
            if (Convert.ToHexString(SHA256.HashData(bytes)) == "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
            {
                Equal(0u, logCount);
                Equal(27, logs.Rows.Count(r => r.Cells[4] == "Retained beyond saved count"));
                True(logs.Rows[0].Details.Contains("reset_events: 1; bits 00000001"), "Actual log counter must agree with native integer store.");
                True(segments.Rows.All(r => r.Cells[3] == "Not recorded" && r.Cells[4] == "0"), "Retained logs do not imply populated current segment records.");
                Equal(19, blocks.Rows.Count(row => row.Cells[1] == "Yes"));
                True(blocks.Rows.Where(row => row.Cells[1] == "Yes").All(row => row.Cells[3] == "262144" && row.Details.Contains("matches saved: Yes")), "All populated actual blocks must decode and reproduce encoder accumulators.");
                True(blocks.Rows[0].Details.Contains("2CE4BB0E543C205E2524A6AA309B008F6824695EEAC68040847393F598EF9CD8"), "C# and independent Python decoder must agree on actual output bytes.");
                True(blocks.Rows[11].Details.Contains("9CD7A4BF562AB098D75C0FF51BDFD7625D9F68DADECA96BB9CC6A5D85795004E"), "Decoders must preserve multi-valued state bytes, not coerce to booleans.");
            }
            var blueprints = inspection.Table("Blueprints");
            uint blueprintMask = BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(0x86F4, 4));
            for (int id = 0; id < 32; id++) Equal((blueprintMask & (1u << id)) != 0 ? "Yes" : "No", blueprints.Rows[id].Cells[1]);
            var bonuses = inspection.Table("Bonuses & cheats");
            for (int id = 0; id < 14; id++) Equal(bytes[0x86F8 + id].ToString(), bonuses.Rows[id].Cells[2]);
            var objects = inspection.Table("Objects & equipment");
            Equal(23, objects.Rows.Count);
            for (int id = 0; id < 23; id++)
            {
                Equal(BinaryPrimitives.ReadInt32BigEndian(bytes.AsSpan(0x304 + id * 4, 4)).ToString(), objects.Rows[id].Cells[2]);
                Equal(BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(0x360 + id * 4, 4)).ToString(), objects.Rows[id].Cells[3]);
                Equal(BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(0x3BC + id * 4, 4)).ToString(), objects.Rows[id].Cells[4]);
            }
            var summary = InspectionPresentation.Simplify("Counters & nearby fields", inspection.Table("Counters & nearby fields"));
            Equal(BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(0x418, 4)).ToString(), summary.Rows.Single(row => row.Cells[0] == "Hero XP").Cells[1]);
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
            form.ClientSize = new Size(900, 620);
            Capture(form, Path.GetFullPath("artifacts/ui-upgrades-simple-minimum-reference.png"));
            form.ClientSize = new Size(1900, 970);
            foreach (string view in new[] { "Weapons & gadgets", "Skill points", "Armor", "Skins", "Special bolts", "Blueprints", "Bonuses & cheats", "Stored state blocks", "Objects & equipment", "World progress", "Gameplay segments", "Global event flags", "Arena challenges", "Quick select", "Player summary", "Game settings", "Saved locations", "Save layout", "Files & metadata" })
            {
                inspectorViews.SelectedItem = view;
                Capture(form, Path.GetFullPath("artifacts/ui-" + view.Replace(" ", "-").ToLowerInvariant() + "-reference.png"));
                form.ClientSize = new Size(900, 620);
                Capture(form, Path.GetFullPath("artifacts/ui-" + view.Replace(" ", "-").ToLowerInvariant() + "-minimum-reference.png"));
                var friendlyGrid = Descendants(form).OfType<DataGridView>().Single(c => c.Name == "InspectionGrid");
                True(friendlyGrid.Columns.Cast<DataGridViewColumn>().Sum(column => column.Width) <= friendlyGrid.ClientSize.Width,
                    "Friendly views should fit the minimum window: " + view);
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
