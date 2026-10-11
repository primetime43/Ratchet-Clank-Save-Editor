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
        Check("Hero progression reference rows stay separate from live level and health", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x418, 4), 2315144);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Hero XP reference");
            Equal(98, table.Rows.Count); Equal(4, table.Columns.Length);
            Equal("989,000", table.Rows[97].Cells[1]); Equal("999", table.Rows[97].Cells[2]);
            True(table.Rows.All(row => row.Cells[3] == "At / above"), "Actual reference XP must be compared without an invented live level.");
            True(table.Rows[97].Details.Contains("not your observed runtime level or current health") && table.Rows[97].Details.Contains("unpopulated") && table.Rows[97].Details.Contains("not a recovered player-facing level"), "Reference scope and unknown runtime entries must remain explicit.");
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x418, 4), 0);
            var low = TodSaveInspection.Read(bytes, "BCUS98127").Table("Hero XP reference");
            Equal("At / above", low.Rows[0].Cells[3]); Equal("Below", low.Rows[1].Cells[3]);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x418, 4), 2315144);
            True(bytes.SequenceEqual(before), "Reference inspection must not modify saved XP or install config values.");
            Equal(74, TodResearch.Map.GetProperty("hero_config").GetProperty("instruction_guards").GetArrayLength());
        });
        Check("Hero XP carry and reload research preserves raw XP without runtime guesses", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x418, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Counters & nearby fields");
            var row = table.Rows.Single(r => r.Cells[1] == "Hero XP");
            True(row.Details.Contains("greater than1, not exactly1") && row.Details.Contains("no carry loop") && row.Details.Contains("original incoming XP"), "Carry and threshold input must remain distinct.");
            True(row.Details.Contains("float32") && row.Details.Contains("cannot be inferred") && row.Details.Contains("raw saved value") && row.Details.Contains("no safe editing range"), "Raw XP must not become inferred runtime health, level or safe bounds.");
            Equal(100, TodResearch.Map.GetProperty("hero_xp_flow").GetProperty("instruction_guards").GetArrayLength());
            True(bytes.SequenceEqual(before), "Viewing XP must not apply a reload preview or normalize large values.");
        });
        Check("Weapon purchase gates and ordered writes remain read-only and runtime-qualified", () =>
        {
            byte[] bytes = ResearchFixture();
            bytes[0x24] = 255; bytes[0x25] = 4;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x906EC, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Weapons & gadgets");
            string details = table.Rows[1].Details;
            True(details.Contains("stored level exactly4") && details.Contains("raw0xFFFFFFFF") && details.Contains("not full purchase eligibility"), "Gate details must distinguish saved prerequisites from runtime definition/caller state.");
            True(details.Contains("without a normal fallback") && details.Contains("before charging bolts") && details.Contains("charge again"), "Routing, publication/payment order and duplicate acquisition must stay qualified.");
            Equal(115, TodResearch.Map.GetProperty("weapon_purchase").GetProperty("instruction_guards").GetArrayLength());
            True(bytes.SequenceEqual(before), "Purchase research must never promote levels, spend bolts, refill ammo or normalize replay state.");
        });
        Check("Blueprint selector provenance does not become current planet or pickup history", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x86F4, 4), uint.MaxValue);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x906E8, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Blueprints");
            Equal(32, table.Rows.Count);
            True(table.Rows[31].Details.Contains("saved level/destination selector") && table.Rows[31].Details.Contains("not proof of the current runtime planet"), "Native selector association must not imply placement or completed pickups.");
            True(table.Rows[2].Details.Contains("LEVEL_STRATUS_CITY") && !table.Rows[31].Details.Contains("Native selector association:"), "Only confirmed selector links should receive native level labels.");
            True(TodResearch.Map.GetProperty("blueprint_producers").GetProperty("instruction_guards").GetArrayLength() > 0, "Blueprint producer evidence must be embedded.");
            True(bytes.SequenceEqual(before), "Blueprint research must preserve unknown bits and selectors.");
        });
        Check("Upgrade purchase ordering remains descriptive and does not spend or refill", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x420, 4), 0x80000000);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Upgrade nodes");
            Equal(4, table.Columns.Length);
            True(table.Rows[1].Details.Contains("signed32 raritanium") && table.Rows[1].Details.Contains("including unordered") && table.Rows[1].Details.Contains("charge again"), "Native admission, ammo side effects and duplicate charging must be qualified separately from vendor rules.");
            True(TodResearch.Map.GetProperty("upgrade_purchase").GetProperty("instruction_guards").GetArrayLength() > 0, "Upgrade transaction evidence must be embedded.");
            True(bytes.SequenceEqual(before), "Upgrade viewing must never invoke a purchase.");
        });
        Check("Skill producer runtime conditions do not become earned-history or eligibility claims", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt64BigEndian(bytes.AsSpan(0x8710, 8), ulong.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Skill points");
            True(table.Rows[24].Details.Contains("not a saved enemy-kill history"), "Pool scan conditions must not imply complete enemy history.");
            True(table.Rows[41].Details.Contains("not explicitly restricted to level13") && table.Rows[41].Details.Contains("menu grouping is not an award eligibility gate"), "Definition groups must not narrow an unguarded native else branch.");
            True(table.Rows[44].Details.Contains("Menu filter group: 19") && table.Rows[44].Details.Contains("not a twentieth playable world"), "Group metadata must not invent another world.");
            True(TodResearch.Map.GetProperty("skill_producers").GetProperty("instruction_guards").GetArrayLength() > 0, "Skill producer evidence must be embedded.");
            True(bytes.SequenceEqual(before), "Skill viewing must preserve high bits and score mismatches.");
        });
        Check("Option exits remain latched, callback-qualified and separate from saved option edits", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x114C0, 4), uint.MaxValue);
            bytes[0x114D6] = 0xAB; bytes[0x114D7] = 0xCD;
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Game settings");
            var word = table.Rows.Single(row => row.Cells[2] == "0x114C0");
            Equal("4294967295", word.Cells[1]);
            True(word.Details.Contains("entry-latched byte") && word.Details.Contains("all16 matching") && word.Details.Contains("after the first callback"), "Exit cleanup must not become a saved-word reread, first-match-only operation or atomic transaction.");
            Equal("ABCD", table.Rows.Single(row => row.Cells[2] == "0x114D6").Cells[1]);
            True(TodResearch.Map.GetProperty("option_producers").GetProperty("instruction_guards").GetArrayLength() > 0, "Exit evidence must be bundled.");
            True(bytes.SequenceEqual(before), "Option inspection must not clean runtime requests or rewrite saved values.");
        });
        Check("Reset selection and dispatch limits never imply saved-counter updates or death causes", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x574C, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Reset-event counters");
            Equal("4294967295", table.Rows[6].Cells[1]);
            True(table.Rows[6].Details.Contains("negative signed state430") && table.Rows[6].Details.Contains("exceeds the20-case") && table.Rows[6].Details.Contains("Selection alone does not increment"), "Caller context bounds must not become a death count or switch eligibility guarantee.");
            True(TodResearch.Map.GetProperty("reset_producers").GetProperty("instruction_guards").GetArrayLength() > 0, "Reset producer evidence must be bundled.");
            True(bytes.SequenceEqual(before), "Reset research must not select categories or increment saved counters.");
        });
        Check("Opaque-field ownership audit preserves unusual bits without claiming unused storage", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x488 + 0x28, 4), 0xDEADBEEF);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Gameplay segments");
            True(table.Rows[0].Details.Contains("DEADBEEF") && table.Rows[0].Details.Contains("not proof this saved word is unused"), "Eliminated immediate-offset matches must not become a no-consumer proof or invented type.");
            Equal(30, TodResearch.Map.GetProperty("segment_opaque").GetProperty("instruction_guards").GetArrayLength());
            True(bytes.SequenceEqual(before), "Opaque audit must not repair or reinterpret saved bytes.");
        });
        Check("Runtime pool setup and slot reuse do not become saved identity or allocation simulation", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt64BigEndian(bytes.AsSpan(0x668, 8), ulong.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("World object flags");
            True(table.Rows[0].Details.Contains("padding slots occupied") && table.Rows[0].Details.Contains("physical slots can be reused") && table.Rows[0].Details.Contains("not additional save data"), "Pool padding, lifecycle and runtime header must stay distinct from saved object identities.");
            Equal(71, TodResearch.Map.GetProperty("pool_lifecycle").GetProperty("instruction_guards").GetArrayLength());
            Equal(8, TodResearch.Map.GetProperty("pool_lifecycle").GetProperty("runtime_header").GetProperty("fields").GetArrayLength());
            True(bytes.SequenceEqual(before), "Pool research must not allocate, release or alter saved object bits.");
        });
        Check("Consumed event flags do not become permanent achievements or runtime Lua counters", () =>
        {
            byte[] bytes = ResearchFixture(), before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Global event flags");
            foreach (int id in new[] { 3, 7, 12, 13, 15, 16, 17 })
                True(table.Rows[id].Details.Contains("Clear does not mean the action never happened"), "A consumed event must not become an action-history verdict.");
            True(!table.Rows[219].Details.Contains("These are event latches"), "A dependency flag must not inherit another flag's reset behavior.");
            True(table.Rows[13].Details.Contains("no confirmed save offset") && table.Rows[12].Details.Contains("not atomic"), "Script counters and mission side effects must stay qualified.");
            Equal("UNMAPPED_BIT_319", table.Rows[319].Cells[1]);
            Equal(510, TodResearch.Map.GetProperty("global_flag_mutation").GetProperty("instruction_guards").GetArrayLength());
            True(bytes.SequenceEqual(before), "Event research must not clear flags, run tutorials or complete missions.");
        });
        Check("Class resource evidence remains separate from saved slots and unnamed opaque payloads", () =>
        {
            var map = TodResearch.Map.GetProperty("object_classes");
            True(map.GetProperty("instruction_guards").GetArrayLength() > 0, "Class producer evidence must be bundled.");
            Equal(19, TodResearch.Map.GetProperty("object_classes_assets").GetProperty("named_world_count").GetInt32());
            Equal(18214, TodResearch.Map.GetProperty("object_classes_assets").GetProperty("definition_count").GetInt32());
            byte[] bytes = ResearchFixture(), before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("World object flags");
            True(table.Rows[0].Details.Contains("No object names are recovered for these indices"), "Class resources must not manufacture names for physical saved slots.");
            True(bytes.SequenceEqual(before), "Class viewing must not execute actor factories or change saves.");
        });
        Check("Object asset catalogs remain reference-only and do not relabel physical saved slots", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt64BigEndian(bytes.AsSpan(0x668, 8), 1UL << 63);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("World object flags");
            Equal("1", table.Rows[0].Cells[3]);
            True(table.Rows[0].Details.Contains("definition ordinal is not a confirmed saved pool slot") && table.Rows[0].Details.Contains("later runtime spawns"), "A reference asset catalog must not become a current saved object identity map.");
            var assets = TodResearch.Map.GetProperty("object_definitions_assets");
            Equal(19, assets.GetProperty("named_world_count").GetInt32());
            Equal(18214, assets.GetProperty("definition_count").GetInt32());
            Equal(69, TodResearch.Map.GetProperty("object_definitions").GetProperty("instruction_guards").GetArrayLength());
            True(bytes.SequenceEqual(before), "Reference object catalogs must not allocate objects, execute scripts or change saved bits.");
        });
        Check("Currency mutation evidence preserves raw balances without applying native caps or cache updates", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x41C, 4), uint.MaxValue);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x420, 4), 0x80000000);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Counters & nearby fields");
            var bolts = table.Rows.Single(row => row.Cells[0] == "0x41C");
            var minerals = table.Rows.Single(row => row.Cells[0] == "0x420");
            Equal("4294967295", bolts.Cells[2]);
            Equal("2147483648", minerals.Cells[2]);
            True(bolts.Details.Contains("not a universal unsigned minimum") && minerals.Details.Contains("not the actual wallet delta"), "Native cap selection and runtime cache bookkeeping must not become a saved-value repair or current reward calculation.");
            True(TodResearch.Map.GetProperty("currency_mutation").GetProperty("instruction_guards").GetArrayLength() > 0, "Currency producer evidence must be bundled.");
            True(bytes.SequenceEqual(before), "Currency research must not mutate balances or invoke reward/purchase paths.");
        });
        Check("Equipment restart filters preserve independent selector, pack and boot values", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x438, 4), 1);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x43C, 4), 0);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x440, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Counters & nearby fields");
            var selector = table.Rows.Single(row => row.Cells[0] == "0x438");
            var pack = table.Rows.Single(row => row.Cells[0] == "0x43C");
            var boot = table.Rows.Single(row => row.Cells[0] == "0x440");
            Equal("1", selector.Cells[2]);
            Equal("0", pack.Cells[2]);
            Equal("4294967295", boot.Cells[2]);
            True(selector.Details.Contains("selector1/type0") && pack.Details.Contains("only when exactly3") && pack.Details.Contains("zero-extends"), "Restart filtering and the wrapper's argument boundary must not become a selector repair, arbitrary native64 payload or equip verdict.");
            True(TodResearch.Map.GetProperty("equipment_mutation").GetProperty("instruction_guards").GetArrayLength() > 0, "Equipment transition evidence must be bundled.");
            True(bytes.SequenceEqual(before), "Equipment viewing must not filter history, clear pack type or change unknown boot values.");
        });
        Check("Object lifecycle explanations keep callbacks and runtime latches separate from saved bits", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt64BigEndian(bytes.AsSpan(0x668, 8), 1UL << 63);
            BinaryPrimitives.WriteUInt64BigEndian(bytes.AsSpan(0x768, 8), ulong.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("World object flags");
            Equal("1", table.Rows[0].Cells[3]);
            Equal("64", table.Rows[1].Cells[3]);
            True(table.Rows[0].Details.Contains("BEFORE the saved bit") && table.Rows[0].Details.Contains("consumes pending1E") && table.Rows[0].Details.Contains("first matching record"), "Stored bits must not imply scheduled callbacks, current-world identity or unique UID records.");
            True(table.Rows[1].Details.Contains("runs on either branch") && table.Rows[1].Details.Contains("does not establish an atomic OR"), "Saved-write admission must not become downstream-helper admission or atomicity.");
            True(TodResearch.Map.GetProperty("object_flag_mutation").GetProperty("instruction_guards").GetArrayLength() > 0, "Object publication evidence must be bundled.");
            True(bytes.SequenceEqual(before), "Object viewing must not execute callbacks, consume latches, resolve handles or alter saved bits.");
        });
        Check("Restart-bank research distinguishes nested mission clearing from retained private log bytes", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x906EC, 4), uint.MaxValue);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x10148 + 8, 4), 0xDEADBEEF);
            byte[] before = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var replay = inspection.Table("Counters & nearby fields").Rows.Single(row => row.Cells[0] == "0x906EC");
            Equal("4294967295", replay.Cells[2]);
            True(replay.Details.Contains("not a proven alias") && replay.Details.Contains("prior private-bank log bytes8764..10144"), "Private captured data must not become current live data or standard manager staging.");
            True(inspection.Table("World progress").Rows[0].Details.Contains("zeroes both entire mission-list groups"), "Constructor loop ownership must not be confused with the final nested zero-fill result.");
            var ownership = TodResearch.Map.GetProperty("restart_execution").GetProperty("nested_initializer_ownership");
            Equal("0x10148", ownership.GetProperty("mission_zero_fills")[0].GetProperty("start").GetString());
            Equal("0x8764", ownership.GetProperty("log").GetProperty("start").GetString());
            True(bytes.SequenceEqual(before), "Research viewing must not capture state, clear missions/logs, increment replay or execute UI choices.");
        });
        Check("Award producer explanations retain inconsistent scores, missing final awards and raw bits", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x8708, 4), uint.MaxValue);
            BinaryPrimitives.WriteUInt64BigEndian(bytes.AsSpan(0x8710, 8), 0xF7FFFFFFFFFFFFFFUL);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Skill points");
            Equal("No", table.Rows[59].Cells[2]);
            True(table.Rows[59].Details.Contains("4294967295") && table.Rows[59].Details.Contains("does not repair score mismatches"), "Duplicate award evidence must not repair a missing final bit or mismatched score.");
            True(table.Rows[46].Details.Contains("even without a new bit") && table.Rows[47].Details.Contains("ORIGINAL request <=1"), "Producer call predicates must not become inferred pickups or clamped-quantity award rules.");
            Equal(47, TodResearch.Map.GetProperty("skill_award").GetProperty("cheapskate_producer").GetProperty("skill_id").GetInt32());
            Equal(3, InspectionPresentation.Simplify("Skill points", table).Columns.Length);
            True(bytes.SequenceEqual(before), "Award viewing must not invoke producers, recompute score or normalize unknown high bits.");
        });
        Check("Armor and skin purchase research preserves independent saved states without runtime queue inference", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x444 + 4 * 4, 4), 0x80000000);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x458, 4), 0);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x480, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var armor = inspection.Table("Armor");
            Equal("Yes", armor.Rows[4].Cells[2]);
            Equal("No", armor.Rows[4].Cells[4]);
            True(armor.Rows[4].Details.Contains("prior equipped ID") && armor.Rows[4].Details.Contains("unordered NaN"), "Queued effect admission must not become an immediate equip or current runtime deadline verdict.");
            var skins = inspection.Table("Skins");
            True(skins.Rows[0].Details.Contains("4294967295") && skins.Rows[0].Details.Contains("does not itself test ownership or availability"), "Leaf purchase evidence must preserve unknown selected IDs and distinguish caller gates.");
            Equal("0x2170", TodResearch.Map.GetProperty("armor_consumer").GetProperty("queued_effect").GetProperty("runtime_hero_member").GetString());
            Equal(3, InspectionPresentation.Simplify("Armor", armor).Columns.Length);
            True(bytes.SequenceEqual(before), "Purchase research must not charge, queue, equip or normalize ownership/selection.");
        });
        Check("Snapshot and load gates do not become a current worker or acceptance verdict", () =>
        {
            byte[] bytes = ResearchFixture();
            bytes[0x484] = 0xAB;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x906E8, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Save regions");
            True(table.Rows[0].Details.Contains("before starting the worker thread") && table.Rows[0].Details.Contains("not live memory"), "The staging snapshot must not be confused with live worker-time state.");
            True(table.Rows[0].Details.Contains("first matching filename") && table.Rows[0].Details.Contains("handle/status/phase5 gates") && table.Rows[0].Details.Contains("existence probe is separate"), "Metadata and worker gates must not become payload validation or a current apply verdict.");
            Equal("0x1029ff18", TodResearch.Map.GetProperty("snapshot_lifecycle").GetProperty("memory_banks").GetProperty("staging_va").GetString());
            True(bytes.SequenceEqual(before), "Lifecycle viewing must not snapshot, restore, issue syscalls or normalize opaque saved bytes.");
        });
        Check("Weapon progression explains pre-update caps without normalizing raw floats", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x18, 4), 0x7FC01234);
            BinaryPrimitives.WriteSingleBigEndian(bytes.AsSpan(0x1C, 4), -10f);
            bytes[0x25] = 255;
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Weapons & gadgets");
            Equal("255", table.Rows[1].Cells[3]);
            Equal("-10", table.Rows[1].Cells[5]);
            True(table.Rows[1].Details.Contains("PRE-UPDATE stored level") && table.Rows[1].Details.Contains("negative existing ammo need not fully refill"), "Stored byte predicates and additive ammo must not become an absolute refill or runtime cap verdict.");
            True(table.Rows[1].Details.Contains("0x7FC01234") && table.Rows[1].Details.Contains("does not clamp its fraction"), "Nonfinite bits and raw threshold lookup must remain visible without guessed progress.");
            Equal("0x465f08", TodResearch.Map.GetProperty("weapon_progression").GetProperty("level_cap").GetProperty("function_va").GetString());
            True(bytes.SequenceEqual(before), "Progression inspection must not recompute levels, clip ammo or execute native code.");
        });
        Check("Mission completion describes destination flags and bounded residual storage", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x10148 + 0x78, 4), uint.MaxValue);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x10148 + 8, 4), 0xABCD1235);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("World progress");
            True(table.Rows[0].Details.Contains("Exceeds capacity10") && table.Rows[0].Details.Contains("unknown bits0xABCD1234"), "Corrupt counts and unknown mission flag bits must remain raw and bounded.");
            True(table.Rows[0].Details.Contains("destination's retained flags") && table.Rows[0].Details.Contains("inactive residual storage"), "Completion flags must not be described as source transfer or residual entries as live missions.");
            Equal(10, TodResearch.Map.GetProperty("mission_mutation").GetProperty("layout").GetProperty("capacity").GetInt32());
            True(bytes.SequenceEqual(before), "Mission inspection must not clear stale bytes, compact lists or emulate native overflow.");
        });
        Check("Arena queue diagnostics do not become a recovered table-taking native binding", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x56D8 + 4, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Arena challenges");
            Equal("-1", table.Rows[1].Cells[3]);
            True(table.Rows[1].Details.Contains("registered as queue_arena_challenge_screen") && table.Rows[1].Details.Contains("diagnostic identifier"), "Diagnostic select text must not become a registered table-taking API.");
            True(table.Rows[1].Details.Contains("does not consume that string as a challenge-list payload") && table.Rows[1].Details.Contains("runtime-only"), "Loader resource words must not become saved fields or a current Lua table.");
            Equal("queue_arena_challenge_screen", TodResearch.Map.GetProperty("arena_binding").GetProperty("queue_binding").GetProperty("name").GetString());
            True(bytes.SequenceEqual(before), "Arena boundary inspection must not execute UI loading or normalize recorded wins.");
        });
        Check("Reset admission and service latches remain runtime-qualified without death-count inference", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x5738, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Reset-event counters");
            Equal(uint.MaxValue.ToString(), table.Rows[1].Cells[1]);
            True(table.Rows[1].Details.Contains("before callback calls return") && table.Rows[1].Details.Contains("not atomically"), "Latch publication must not become a prepublished recording lock.");
            True(table.Rows[1].Details.Contains("only latch==1") && table.Rows[1].Details.Contains("None of this runtime state is read from GAME.SAV"), "Runtime latch semantics must not add saved fields or infer current reset eligibility.");
            Equal("0x101d5c30", TodResearch.Map.GetProperty("reset_context").GetProperty("admission").GetProperty("runtime_owner_va").GetString());
            Equal(3, InspectionPresentation.Simplify("Reset-event counters", table).Columns.Length);
            True(bytes.SequenceEqual(before), "Reset context inspection must not count events, clear latches or clamp unsigned counters.");
        });
        Check("Segment flags remain independent of runtime configuration mapping and reset eligibility", () =>
        {
            byte[] bytes = ResearchFixture();
            bytes[0x488 + 0x2C] = 255;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x488 + 8, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Gameplay segments");
            True(table.Rows[0].Details.Contains("completion byte 0xFF") && table.Rows[0].Details.Contains("configuration getter substitutes the mapped index"), "Saved slots must not be reordered by unavailable runtime configuration metadata.");
            True(table.Rows[0].Details.Contains("reset leaf does not test completion") && table.Rows[0].Details.Contains("not proof that reset is actually called after completion"), "A native eligibility difference must not become a current reset verdict.");
            Equal(5, InspectionPresentation.Simplify("Gameplay segments", table).Columns.Length);
            Equal("0x2cdf40", TodResearch.Map.GetProperty("world_consumers").GetProperty("runtime_mapping").GetProperty("saved_getter_va").GetString());
            True(bytes.SequenceEqual(before), "Segment consumer inspection must not normalize nonzero flags, remap records or append logs.");
        });
        Check("Saved level words do not become runtime queues, sentinels or successful loads", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x906E8, 4), 0x80000000);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x8740, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Counters & nearby fields");
            var next = table.Rows.Single(row => row.Cells[0] == "0x8740");
            var load = table.Rows.Single(row => row.Cells[0] == "0x906E8");
            Equal(uint.MaxValue.ToString(), next.Cells[2]);
            Equal("2147483648", load.Cells[2]);
            True(next.Details.Contains("does not establish sentinel semantics") && load.Details.Contains("not proof of a successful load"), "Queue skip markers and saved assignments are not saved sentinel or load acceptance proof.");
            True(load.Details.Contains("without changing this word") && load.Details.Contains("not every runtime gate"), "Deferral and force have distinct native scope.");
            Equal("0x10063024", TodResearch.Map.GetProperty("load_selection").GetProperty("pending_consumer").GetProperty("runtime_word_va").GetString());
            True(bytes.SequenceEqual(before), "Load-selection inspection must never execute a request or normalize an unknown ID.");
        });
        Check("Language-dependent bonus menu queries do not become physical-state effects", () =>
        {
            byte[] bytes = ResearchFixture();
            bytes[0x86F8] = 255;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x8708, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Bonuses & cheats");
            Equal("255", table.Rows[0].Cells[2]);
            True(table.Rows[0].Details.Contains("rows17") && table.Rows[0].Details.Contains("replay bypass applies only to rows1..16"), "Bonus movies must retain distinct movie-history and replay predicates.");
            True(table.Rows[2].Details.Contains("art indexes1..66") && table.Rows[2].Details.Contains("not necessarily a query of this physical slot"), "Named enum operands must not silently bypass native language remapping.");
            True(table.Rows[5].Details.Contains("language getter5BFE08") && table.Rows[5].Details.Contains("not an asserted English literal"), "Language ID1 is the native fallback, not an invented localized label.");
            var report = TodResearch.Map.GetProperty("bonus_remaining");
            Equal(8, report.GetProperty("effects").GetArrayLength());
            Equal("0x100d6478", report.GetProperty("runtime_language").GetProperty("va").GetString());
            Equal(3, InspectionPresentation.Simplify("Bonuses & cheats", table).Columns.Length);
            True(bytes.SequenceEqual(before), "Menu-query research must not normalize states or execute movie/bonus APIs.");
        });
        Check("Arena milestone writes remain separate from counters and preserve script ordering", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x56D8 + 6 * 4, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Arena challenges");
            Equal("-1", table.Rows[6].Cells[3]);
            True(table.Rows[6].Details.Contains("set_flag(LVL_IFF_RETURN_CHALLENGE_9_DONE) → set_challenge_success(IFF_A_6)") && table.Rows[6].Details.Contains("wait(6) literal"), "Flag-before-counter ordering must not imply an atomic transaction or reconstructed duration.");
            True(table.Rows[12].Details.Contains("challenge10") && table.Rows[12].Details.Contains("native ID12"), "Script filename numbers are not native IDs.");
            Equal(5, TodResearch.Map.GetProperty("arena_dispatch").GetProperty("operation_dispatch").GetProperty("arena_operation").GetInt32());
            True(TodResearch.Map.GetProperty("arena_dispatch").GetProperty("operation_dispatch").GetProperty("alias_gap").GetString().Contains("not installation"), "A loader route must not become a recovered challenge-table alias.");
            True(bytes.SequenceEqual(before), "Milestone details must not repair counters or set story flags.");
        });
        Check("Grid synchronization details distinguish display bytes, retained headers and native trust", () =>
        {
            byte[] bytes = ResearchFixture();
            int offset = 0x114D8;
            bytes[offset + 0xCC] = 255;
            bytes[offset + 0x60DB] = 0xFE;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(offset + 0xC8, 4), 0xDEADBEEF);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Stored state blocks");
            True(table.Rows[0].Details.Contains("ready byte0xFF") && table.Rows[0].Details.Contains("Unknown last byte60DB: FE"), "Raw readiness and opaque tail must remain visible.");
            True(table.Rows[0].Details.Contains("does not recopy the C8-byte header") && table.Rows[0].Details.Contains("does not validate the accumulator") && table.Rows[0].Details.Contains("preexisting output tail"), "Native trust boundaries must not turn into invented validation, zero-filling or header refresh.");
            True(TodResearch.Map.GetProperty("grid_lifecycle").GetProperty("owner_provenance").GetProperty("rule").GetString().Contains("allocation+70+1AF14"), "The first-context subobject identity must remain qualified.");
            Equal(4, InspectionPresentation.Simplify("Stored state blocks", table).Columns.Length);
            True(bytes.SequenceEqual(before), "Grid lifecycle inspection must never re-encode or overwrite retained bytes.");
        });
        Check("Record-reset ownership preserves opaque tails and does not invent prefix-gap defaults", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt16BigEndian(bytes.AsSpan(0x26, 2), 0xABCD);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x484, 4), 0xFE123456);
            byte[] before = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var weapons = inspection.Table("Weapons & gadgets");
            True(weapons.Rows[1].Details.Contains("ABCD") && weapons.Rows[1].Details.Contains("first18 of20") && weapons.Rows[1].Details.Contains("Bulk initialization"), "Record reset and bulk initialization must not imply the same opaque-byte behavior.");
            var raw = inspection.Table("Counters & nearby fields");
            var gap = raw.Rows.Single(r => r.Cells[0] == "0x484");
            Equal("FE123456", gap.Cells[4]);
            True(gap.Details.Contains("not derived as zero"), "Unwritten gap is not an initializer default.");
            True(!InspectionPresentation.Simplify("Counters & nearby fields", raw).Rows.Any(r => r.Cells[0].Contains("prefix gap")), "Unknown bytes should stay in Technical/details, not add raw summary rows.");
            Equal("0x12", TodResearch.Map.GetProperty("inventory_reset").GetProperty("record_reset").GetProperty("written_byte_range").GetProperty("end_exclusive").GetString());
            True(bytes.SequenceEqual(before), "Ownership inspection must never run a reset or change opaque bytes.");
        });
        Check("Equipment history shows qualified dispatch and distinct fallbacks without normalizing raw IDs", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteInt32BigEndian(bytes.AsSpan(0x42C, 4), -1);
            BinaryPrimitives.WriteInt32BigEndian(bytes.AsSpan(0x430, 4), 25);
            BinaryPrimitives.WriteInt32BigEndian(bytes.AsSpan(0x434, 4), int.MinValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Counters & nearby fields");
            var row = table.Rows.Single(r => r.Cells[0] == "0x42C");
            Equal(uint.MaxValue.ToString(), row.Cells[2]);
            True(row.Details.Contains("Raw signed ID -1") && row.Details.Contains("Raw signed ID -2147483648"), "Unknown signed history must remain visible and untouched.");
            True(row.Details.Contains("first restore request") && row.Details.Contains("Secondary uses430") && row.Details.Contains("state110==2"), "Request selection, menu fallback and qualified history callback must be distinct.");
            Equal("0x4674c0", TodResearch.Map.GetProperty("equipment_lifecycle").GetProperty("history_dispatch").GetProperty("call_va").GetString());
            True(bytes.SequenceEqual(before), "Viewing history must not queue equipment or rewrite saved IDs.");
        });
        Check("Bonus consumer explanations preserve raw states and never claim current activity", () =>
        {
            byte[] bytes = ResearchFixture();
            bytes[0x86F9] = 255;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x8708, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Bonuses & cheats");
            Equal(14, table.Rows.Count); Equal("255", table.Rows[1].Cells[2]);
            True(table.Rows[1].Details.Contains("other nonzero bytes choose1.0") && table.Rows[1].Details.Contains("not an active-effect verdict"), "Native unknown-state fallback must not become an active effect or safe edit permission.");
            True(table.Rows[7].Details.Contains("Neither local block checks score8708") && table.Rows[7].Details.Contains("capacity/content"), "Missing local score checks must not imply safe replacement indexing.");
            True(table.Rows[0].Details.Contains("menu unlock-query operand") && table.Rows[0].Details.Contains("not a direct saved-byte effect"), "Menu queries must not become guessed saved-byte effects.");
            Equal(6, TodResearch.Map.GetProperty("bonus_effects").GetProperty("effects").GetArrayLength());
            Equal(3, InspectionPresentation.Simplify("Bonuses & cheats", table).Columns.Length);
            True(bytes.SequenceEqual(before), "Bonus inspection must preserve every raw byte.");
        });
        Check("Arena display research never substitutes source indices or menu order for saved native IDs", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x56D8 + 4, 4), uint.MaxValue);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x5734, 4), 123);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Arena challenges");
            Equal(23, table.Rows.Count); Equal("1", table.Rows[1].Cells[0]); Equal("-1", table.Rows[1].Cells[3]);
            True(table.Rows[1].Details.Contains("non-positive signed counts before positive counts") && table.Rows[1].Details.Contains("does not reconstruct or reorder"), "Shipped partition must not imply a recovered current menu or a zero-only test.");
            var native = TodResearch.Map.GetProperty("arena_menu");
            Equal(3, native.GetProperty("index_spaces").GetArrayLength());
            True(native.GetProperty("id_resolver").GetProperty("bounds_warning").GetString().Contains("ID23 addresses5734"), "Resolver cap must not become a safe 24th arena counter.");
            Equal(20, TodResearch.Map.GetProperty("arena_menu_assets").GetProperty("asset_byte_guards").GetArrayLength());
            True(bytes.SequenceEqual(before), "Arena inspection must not execute scripts, follow runtime IDs, resort storage or change adjacent reset counters.");
        });
        Check("Arena script input lists and independent story bits do not become a current menu verdict", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x56D8 + 4, 4), 0x80000000);
            // Flag74 is bit10 of the second BE64 global word, not byte74 of GAME.SAV.
            BinaryPrimitives.WriteUInt64BigEndian(bytes.AsSpan(0x5530, 8), 1UL << 10);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Arena challenges");
            Equal("-2147483648", table.Rows[1].Cells[3]);
            True(table.Rows[1].Details.Contains("LVL_IFF_CHALLENGE_1_DONE: Set") && table.Rows[1].Details.Contains("LVL_IFF_CHALLENGE_2_DONE: Clear"), "Story-bit observation must use exact BE64 addressing.");
            True(table.Rows[1].Details.Contains("not a live menu reconstruction") && table.Rows[1].Details.Contains("alias") && table.Rows[1].Details.Contains("raw completion counter exactly0"), "Compiled input lists and raw-zero reward gate must retain their distinct scope.");
            var assets = TodResearch.Map.GetProperty("arena_table_assets");
            Equal(6, assets.GetProperty("assets").GetArrayLength());
            Equal(20, assets.GetProperty("master_descriptors").GetArrayLength());
            Equal(4, assets.GetProperty("source_lists").GetArrayLength());
            Equal(18, assets.GetProperty("source_lists")[3].GetProperty("rows").GetArrayLength());
            Equal(3, InspectionPresentation.Simplify("Arena challenges", table).Columns.Length);
            True(bytes.SequenceEqual(before), "Arena viewing must not run scripts, alter flags, grant rewards or rewrite raw counters.");
        });
        Check("Object lifecycle distinguishes reset banks, seeded equipment and signed Souls comparisons", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x304, 4), 7);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x360, 4), uint.MaxValue);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x3BC, 4), 0x80000000);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x344, 4), 0);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x3FC, 4), 0xFFFFFFFF);
            BinaryPrimitives.WriteUInt64BigEndian(bytes.AsSpan(0x8710, 8), 1UL << 52);
            BinaryPrimitives.WriteInt32BigEndian(bytes.AsSpan(0x284 + 31 * 4, 4), 1);
            byte[] before = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var objects = inspection.Table("Objects & equipment");
            Equal("7", objects.Rows[0].Cells[2]); Equal("4294967295", objects.Rows[0].Cells[3]);
            True(objects.Rows[0].Details.Contains("preserves this object's three") && objects.Rows[0].Details.Contains("sets this current count to 1"), "Preserved banks and later seeded assignments must not be conflated.");
            True(objects.Rows[10].Details.Contains("clears this object's current, high-water and positive-additions"), "Reset IDs must distinguish all three banks.");
            True(objects.Rows[16].Details.Contains("signed additions -1") && objects.Rows[16].Details.Contains("Additional runtime gates") && objects.Rows[16].Details.Contains("neither grants nor revokes"), "Unsigned storage must not become an unsigned Souls threshold or a computed award.");
            var quick = inspection.Table("Quick select");
            Equal("1", quick.Rows[31].Cells[1]);
            True(quick.Rows[31].Details.Contains("removes all duplicate occurrences") && quick.Rows[31].Details.Contains("empty tail slots do not help"), "Raw extra slots must retain their qualified insertion/removal behavior.");
            True(bytes.SequenceEqual(before), "Inspection must not perform a restart, object seed, award or quick-select mutation.");
        });
        Check("Opaque settings footprint and final-tail copy rules do not create defaults or execute resets", () =>
        {
            byte[] bytes = ResearchFixture(); bytes[0x114D6] = 0xAB; bytes[0x114D7] = 0xCD;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x906E4, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var tail = inspection.Table("Game settings").Rows.Single(r => r.Cells[2] == "0x114D6");
            Equal("ABCD", tail.Cells[1]);
            True(tail.Details.Contains("46 of 48") && tail.Details.Contains("Not proven padding or default zero"), "Unwritten leaf bytes must not be assigned whole-lifecycle defaults.");
            var word = inspection.Table("Counters & nearby fields").Rows.Single(r => r.Cells[0] == "0x906E4");
            Equal("FFFFFFFF", word.Cells[4]);
            True(word.Details.Contains("ends at 906E4 exclusively") && word.Details.Contains("raw bits verbatim") && word.Details.Contains("Subsequent callbacks"), "Final-tail zeroing must be confined to the selected copy boundary.");
            Equal(46, TodResearch.Map.GetProperty("final_tail_fields").GetProperty("settings_initializer_footprint").GetProperty("covered_byte_count").GetInt32());
            True(bytes.SequenceEqual(before), "Viewing opaque fields must preserve every raw byte.");
        });
        Check("Unknown final tail word stays visible only in Technical and is never repaired", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x906E4, 4), 0xDEADBEEF);
            byte[] before = bytes.ToArray();
            var raw = TodSaveInspection.Read(bytes, "BCUS98127").Table("Counters & nearby fields");
            var word = raw.Rows.Single(r => r.Cells[0] == "0x906E4");
            Equal("3735928559", word.Cells[2]); Equal("DEADBEEF", word.Cells[4]);
            True(word.Details.Contains("meaning remains unresolved") && word.Details.Contains("not proof of padding"), "Copied tail words must remain semantically qualified.");
            var summary = InspectionPresentation.Simplify("Counters & nearby fields", raw);
            Equal(21, summary.Rows.Count);
            True(!summary.Rows.Any(r => r.Cells[0] == "Unknown final tail word"), "Unknown words must stay out of the simple summary.");
            True(bytes.SequenceEqual(before), "Viewing must not reproduce initialization or overwrite the unknown tail word.");
        });
        Check("Decryptor summary uses named outcomes and spark scaling, not generic difficulty or lifetime statistics", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x8758, 4), uint.MaxValue);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x875C, 4), 7);
            BinaryPrimitives.WriteSingleBigEndian(bytes.AsSpan(0x8760, 4), 0.75f);
            byte[] before = bytes.ToArray();
            var raw = TodSaveInspection.Read(bytes, "BCUS98127").Table("Counters & nearby fields");
            var summary = InspectionPresentation.Simplify("Counters & nearby fields", raw);
            Equal("4294967295", summary.Rows.Single(r => r.Cells[0] == "Decryptor wins").Cells[1]);
            Equal("7", summary.Rows.Single(r => r.Cells[0] == "Decryptor Sixaxis losses since success").Cells[1]);
            Equal("0.75×", summary.Rows.Single(r => r.Cells[0] == "Decryptor spark-speed multiplier").Cells[1]);
            True(raw.Rows.Single(r => r.Cells[0] == "0x8760").Details.Contains("dc_set_spark_speed") && raw.Rows.Single(r => r.Cells[0] == "0x8758").Details.Contains("not all-time wins"), "Named native context still needs lifecycle caveats.");
            Equal(7, TodResearch.Map.GetProperty("adaptation_context").GetProperty("seven_state_dispatch").GetProperty("states").GetArrayLength());
            True(bytes.SequenceEqual(before), "Decryptor inspection must not change counter values or speed.");
        });
        Check("Saved aggregate and gate floats stay raw, unit-qualified and independent of retained logs", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x8744, 4), 0x7FC12345);
            BinaryPrimitives.WriteSingleBigEndian(bytes.AsSpan(0x8748, 4), -12.5f);
            BinaryPrimitives.WriteSingleBigEndian(bytes.AsSpan(0x874C, 4), 10f);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x8750, 4), 0x80000000);
            byte[] before = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var table = inspection.Table("Counters & nearby fields");
            Equal("7FC12345", table.Rows.Single(r => r.Cells[0] == "0x8744").Cells[4]);
            Equal("80000000", table.Rows.Single(r => r.Cells[0] == "0x8750").Cells[4]);
            True(table.Rows.Single(r => r.Cells[0] == "0x874C").Details.Contains("snapshots, not defaults or seconds"), "Observed countdowns must not imply units or initialization defaults.");
            True(inspection.Table("Gameplay records").Rows[0].Details.Contains("saved-state+8744") && inspection.Table("Gameplay records").Rows[0].Details.Contains("saved8748"), "Log source provenance must be corrected from runtime-only storage.");
            Equal(21, InspectionPresentation.Simplify("Counters & nearby fields", table).Rows.Count);
            True(bytes.SequenceEqual(before), "Viewing must not decay gates or recompute aggregates from stale records.");
        });
        Check("Copied grid handles split raw generations and slots without following or repairing them", () =>
        {
            byte[] bytes = ResearchFixture(); int block = 0x114D8 + 20 * 0x60DC;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(block + 8, 4), 0xABCDFFFF);
            bytes[block + 0xD] = 0x11; bytes[block + 0x1D] = 0x22; bytes[block + 0x60DB] = 0xCD;
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Stored state blocks");
            string detail = table.Rows[20].Details;
            True(detail.Contains("0xABCDFFFF") && detail.Contains("generation 43981, slot 65535") && detail.Contains("outside that range"), "Raw handle decomposition must retain out-of-pool slots.");
            True(detail.Contains("no handle or pointer is followed") && detail.Contains("not a current runtime-validity test") && detail.Contains("110000") && detail.Contains("220000") && detail.Contains("CD"), "Unready copied handles and opaque bytes must remain informational.");
            Equal(19, TodResearch.Map.GetProperty("grid_aux_assets").GetProperty("definition_candidates").GetArrayLength());
            True(bytes.SequenceEqual(before), "Handle inspection must not resolve runtime pools or normalize copied bytes.");
        });
        Check("Saved auxiliary words retain extreme and nonfinite values without changing the simple summary", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x8758, 4), uint.MaxValue);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x875C, 4), 0x80000000);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x8760, 4), 0x7FC12345);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Counters & nearby fields");
            Equal("4294967295", table.Rows.Single(r => r.Cells[0] == "0x8758").Cells[2]);
            Equal("2147483648", table.Rows.Single(r => r.Cells[0] == "0x875C").Cells[2]);
            Equal("7FC12345", table.Rows.Single(r => r.Cells[0] == "0x8760").Cells[4]);
            True(table.Rows.Single(r => r.Cells[0] == "0x875C").Details.Contains("sixaxis_enabled"), "Saved gate must remain Sixaxis, not combat help.");
            True(table.Rows.Single(r => r.Cells[0] == "0x8760").Details.Contains("not all-time wins, all attempts"), "Named Decryptor context must not become universal statistics.");
            Equal(21, InspectionPresentation.Simplify("Counters & nearby fields", table).Rows.Count);
            True(bytes.SequenceEqual(before), "Viewing new auxiliary words must not sanitize input.");
        });
        Check("Health and checkpoint ammo evidence remains runtime-qualified and read-only", () =>
        {
            var evidence = TodResearch.Map.GetProperty("health_persistence");
            Equal("0x1784", evidence.GetProperty("health").GetProperty("current_health_runtime_offset").GetString());
            Equal("0x1788", evidence.GetProperty("health").GetProperty("capacity_runtime_offset").GetString());
            Equal("0x418", evidence.GetProperty("xp_restore").GetProperty("saved_xp_offset").GetString());
            True(evidence.GetProperty("xp_restore").GetProperty("boundary").GetString().Contains("runtime BSS"), "Save XP alone cannot imply a numeric runtime health value.");
            byte[] bytes = ResearchFixture(); byte[] before = bytes.ToArray();
            string detail = TodSaveInspection.Read(bytes, "BCUS98127").Table("Weapons & gadgets").Rows[1].Details;
            True(detail.Contains("runtime-only checkpoint bank") && detail.Contains("not a verbatim copy") && detail.Contains("definition/level/modifier-dependent"), "Ammo restoration needs checkpoint scope and capacity clamp caveats.");
            True(bytes.SequenceEqual(before), "Checkpoint research must not simulate restoration into the save.");
        });
        Check("Unknown first-person word explains qualified coupling without inventing hold or toggle", () =>
        {
            byte[] bytes = ResearchFixture(); BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x114C0, 4), 0xDEADBEEF);
            byte[] before = bytes.ToArray();
            var raw = TodSaveInspection.Read(bytes, "BCUS98127").Table("Game settings");
            var field = raw.Rows.Single(r => r.Cells[2] == "0x114C0");
            Equal("DEADBEEF", field.Cells[4]);
            True(field.Details.Contains("nonzero saved values permit") && field.Details.Contains("Other runtime conditions") && field.Details.Contains("not a currently active camera or a hold/toggle verdict"), "Entry-latched camera paths must not become unconditional runtime state.");
            True(!InspectionPresentation.Simplify("Game settings", raw).Rows.Any(r => r.Cells[0] == "Unknown settings word"), "Unknown native option remains Technical-only.");
            True(bytes.SequenceEqual(before), "Camera evidence must not normalize saved options.");
        });
        Check("Gameplay names come from fingerprinted reference assets, not stale save log order", () =>
        {
            byte[] bytes = ResearchFixture();
            Encoding.ASCII.GetBytes("gameplay_wrong_log_name").CopyTo(bytes, 0x87A4);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Gameplay segments");
            Equal("gameplay_enemy", table.Rows[1].Cells[8]);
            Equal("gameplay_sidescroll", table.Rows[2].Cells[8]);
            Equal("gameplay_traversal", table.Rows[3].Cells[8]);
            Equal("gameplay_magcycle", table.Rows[172].Cells[8]);
            Equal("gameplay_robowings", table.Rows[173].Cells[8]);
            Equal(56, table.Rows.Count(r => r.Cells[8].Length > 0));
            Equal("", table.Rows[0].Cells[8]); Equal("", table.Rows[199].Cells[8]);
            True(table.Rows[1].Details.Contains("not stored in GAME.SAV") && table.Rows[1].Details.Contains("SHA-256"), "Reference labels need native/asset provenance and applicability caveats.");
            True(table.Rows[0].Details.Contains("does not make the saved slot padding"), "Reserved name catalog slot is not a padding verdict for saved bytes.");
            var simple = InspectionPresentation.Simplify("Gameplay segments", table);
            Equal(5, simple.Columns.Length); Equal("Enemy (slot 1)", simple.Rows[1].Cells[1]);
            True(bytes.SequenceEqual(before), "Reference labeling must not write or normalize saves.");
        });
        Check("World opaque tails show specific initialization and copy caveats without inventing semantics", () =>
        {
            byte[] bytes = ResearchFixture(); int world = 0x488 + 18 * 0x408, segment = world + 9 * 0x30;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(segment + 0x28, 4), 0x7FC12345);
            bytes[segment + 0x2D] = 0x11; bytes[segment + 0x2E] = 0x22; bytes[segment + 0x2F] = 0xAB;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(world + 0x404, 4), 0xDEADBEEF);
            byte[] before = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            string detail = inspection.Table("Gameplay segments").Rows[189].Details;
            True(detail.Contains("7FC12345") && detail.Contains("1122AB") && detail.Contains("logical integer/float/flag meaning remains unresolved") && detail.Contains("untouched by35DD98"), "Uninterpreted segment word/tail need raw bits and exact initializer boundaries.");
            True(inspection.Table("World progress").Rows[18].Details.Contains("DEADBEEF") && inspection.Table("World progress").Rows[18].Details.Contains("initializer35DFA8 leaves +404..407 untouched"), "World tail must not become padding or proven live-state retention.");
            Equal(680, TodResearch.Map.GetProperty("world_aux_fields").GetProperty("world_initializer").GetProperty("untouched_bytes_all_worlds").GetInt32());
            True(bytes.SequenceEqual(before), "Opaque-byte inspection must not mutate or zero values.");
        });
        Check("Saved pack and boot names retain unknown IDs, raw selectors and setter caveats", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x438, 4), 0xAB);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x43C, 4), 1);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x440, 4), 3);
            byte[] before = bytes.ToArray();
            var raw = TodSaveInspection.Read(bytes, "BCUS98127").Table("Counters & nearby fields");
            var summary = InspectionPresentation.Simplify("Counters & nearby fields", raw);
            Equal("Thruster", summary.Rows.Single(r => r.Cells[0] == "Saved pack type").Cells[1]);
            Equal("Charge", summary.Rows.Single(r => r.Cells[0] == "Saved boot type").Cells[1]);
            var selector = raw.Rows.Single(r => r.Cells[0] == "0x438");
            Equal("000000AB", selector.Cells[4]);
            True(selector.Details.Contains("equals1") && !summary.Rows.Any(r => r.Cells[0] == "Pack dispatch selector"), "Raw selector must not become an unconditional boolean in the simple view.");
            True(raw.Rows.Single(r => r.Cells[0] == "0x440").Details.Contains("always writes0"), "Native setter ignores script argument; do not suggest arbitrary editing.");
            True(bytes.SequenceEqual(before), "New hero fields must remain read-only.");
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x43C, 4), 4);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x440, 4), uint.MaxValue);
            var unknown = InspectionPresentation.Simplify("Counters & nearby fields", TodSaveInspection.Read(bytes, "BCUS98127").Table("Counters & nearby fields"));
            Equal("Unmapped ID 4", unknown.Rows.Single(r => r.Cells[0] == "Saved pack type").Cells[1]);
            Equal("Unmapped ID 4294967295", unknown.Rows.Single(r => r.Cells[0] == "Saved boot type").Cells[1]);
        });
        Check("Replay word and retained segment median display independently without recomputing", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteSingleBigEndian(bytes.AsSpan(0x8754, 4), 4.5f);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x906EC, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var raw = TodSaveInspection.Read(bytes, "BCUS98127").Table("Counters & nearby fields");
            var summary = InspectionPresentation.Simplify("Counters & nearby fields", raw);
            Equal("4.5", summary.Rows.Single(r => r.Cells[0] == "First-restart segment median").Cells[1]);
            Equal("4294967295", summary.Rows.Single(r => r.Cells[0] == "Engine replay/restart word").Cells[1]);
            True(raw.Rows.Single(r => r.Cells[0] == "0x8754").Details.Contains("does not recompute"), "Historical aggregate must not be recalculated from empty segments.");
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x8754, 4), 0x7FC12345);
            var nonfinite = TodSaveInspection.Read(bytes, "BCUS98127").Table("Counters & nearby fields");
            Equal("7FC12345", nonfinite.Rows.Single(r => r.Cells[0] == "0x8754").Cells[4]);
            True(before.AsSpan(0x906EC, 4).SequenceEqual(bytes.AsSpan(0x906EC, 4)), "Inspection cannot repair a replay word.");
        });
        Check("World reward details preserve out-of-table indices, unknown words and nonfinite caches", () =>
        {
            byte[] bytes = ResearchFixture(); int world = 0x488 + 18 * 0x408;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(world + 0x3F0, 4), uint.MaxValue);
            BinaryPrimitives.WriteSingleBigEndian(bytes.AsSpan(world + 0x3FC, 4), 12.5f);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(world + 0x3E0, 4), 0x7FC12345);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(world + 0x3EC, 4), 0xDEADBEEF);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("World progress");
            Equal(19, table.Rows.Count); Equal(4, InspectionPresentation.Simplify("World progress", table).Columns.Length);
            string details = table.Rows[18].Details;
            True(details.Contains("4294967295") && details.Contains("outside the verified five-entry table") && details.Contains("12.5"), "Separate reward tiers/remainders must remain raw and unsimulated.");
            True(details.Contains("7FC12345") && details.Contains("DEADBEEF") && details.Contains("not a proven hero-XP") && details.Contains("Independent special-bolt collected mask"), "Raw bits, known collectible mask and weapon/hero XP distinction must survive.");
            True(bytes.SequenceEqual(before), "World reward details must not mutate input.");
        });
        Check("Saved mission lookup IDs resolve native keys while unknown keys remain visible", () =>
        {
            byte[] bytes = ResearchFixture();
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x10148 + 0x78, 4), 2);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x10148, 4), 562);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x1014C, 4), 641);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x10154, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var details = TodSaveInspection.Read(bytes, "BCUS98127").Table("World progress").Rows[0].Details;
            True(details.Contains("L01_LABEL_MISSION_DEFENSECENTER") && details.Contains("L01_DESC_MISSION_DEFENSECENTER"), "Native keys should match dual registration, not invented localized names.");
            True(details.Contains("4294967295 (unmapped)"), "Unknown numeric IDs must stay visible.");
            Equal(81, TodResearch.Map.GetProperty("segment_bindings").GetProperty("native_mission_lookup_pairs").GetArrayLength());
            True(bytes.SequenceEqual(before), "Native key lookup must remain read-only.");
        });
        Check("Shipped settings menu distinguishes axis dispatch, disabled rows and unknown settings", () =>
        {
            var menu = TodResearch.Map.GetProperty("settings_menu");
            Equal(12, menu.GetProperty("descriptors").GetArrayLength());
            Equal(6, menu.GetProperty("visible_descriptor_indices").GetArrayLength());
            Equal("is_x_inverted", menu.GetProperty("axis_dispatch").GetProperty("scheme_0").GetProperty("x_getter").GetString());
            Equal("is_look_x_inverted", menu.GetProperty("axis_dispatch").GetProperty("scheme_1").GetProperty("x_getter").GetString());
            True(!menu.GetProperty("descriptors")[7].GetProperty("enabled_literal").GetBoolean(), "Literal first-person row must not imply visible UI.");
            var settings = TodSaveInspection.Read(ResearchFixture(), "BCUS98127").Table("Game settings");
            True(settings.Rows.Single(r => r.Cells[2] == "0x114A8").Details.Contains("not saved-flag polarity"), "Axis dispatch must not invert the meaning of stored bits.");
            True(settings.Rows.Single(r => r.Cells[2] == "0x114C8").Details.Contains("+0.1/-0.1"), "Percentage action step should come from the shipped script.");
            True(settings.Rows.Single(r => r.Cells[2] == "0x114C0").Details.Contains("option name and polarity remain unresolved"), "Pause-menu metadata does not name the unknown word.");
        });
        Check("Grid browse namespaces and native accumulator predicate stay read-only and unsigned", () =>
        {
            byte[] bytes = ResearchFixture();
            uint threshold = 0x36666;
            for (int slot = 0; slot < 15; slot++) BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x114D8 + slot * 0x60DC + 0xC8, 4), threshold);
            var first = TodSaveInspection.Read(bytes, "BCUS98127").Table("Stored state blocks");
            True(first.Rows[15].Details.Contains("position: 1 of 21") && first.Rows[15].Details.Contains("image resource index 21"), "Menu ordinal, physical slot and image ID must stay distinct.");
            True(first.Rows[0].Details.Contains("snapshot qualifies 15/21; function 24E7E8 returns 0"), "Fifteen does not pass the strict aggregate count comparison.");
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x114D8 + 20 * 0x60DC + 0xC8, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var table = TodSaveInspection.Read(bytes, "BCUS98127").Table("Stored state blocks");
            True(table.Rows[20].Details.Contains("snapshot qualifies 16/21; function 24E7E8 returns 1"), "Unsigned high words qualify even in a not-ready block.");
            True(table.Rows[20].Details.Contains("without a readiness gate") && table.Rows[20].Details.Contains("No confirmed trophy/completion caller"), "The unreferenced predicate must not be called trophy progress.");
            Equal(4, InspectionPresentation.Simplify("Stored state blocks", table).Columns.Length);
            True(bytes.SequenceEqual(before), "Routing inspection must not mutate source.");
        });
        Check("Persistent grid labels, copied headers and seven group flags are bounded and preserved", () =>
        {
            byte[] bytes = ResearchFixture(); int offset = 0x114D8 + 20 * 0x60DC;
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(offset + 4, 4), 0x535);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(offset + 0x10, 4), 20);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(offset, 4), 0xDEADBEEF);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(offset + 0x24 + 6 * 24, 4), uint.MaxValue);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(offset + 0x28 + 6 * 24, 4), 0x80000000);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(offset + 0x2C + 6 * 24, 4), 7);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(offset + 0x30 + 6 * 24, 4), 5);
            bytes[offset + 0x60DA] = 0xAB; bytes[offset + 0x60DB] = 0xCD;
            byte[] before = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var table = inspection.Table("Stored state blocks");
            Equal(21, table.Rows.Count); Equal(9, table.Columns.Length);
            Equal("metropolis", table.Rows[15].Cells[8]); Equal("sargasso", table.Rows[3].Cells[8]);
            True(table.Rows[^1].Details.Contains("DEADBEEF") && table.Rows[^1].Details.Contains("saved flag 0xAB") && table.Rows[^1].Details.Contains("60DB: CD"), "Unknown bits and last-group boundaries must survive.");
            True(table.Rows[^1].Details.Contains("not portable") && table.Rows[^1].Details.Contains("not mission"), "Runtime pointers and group flags must not imply portable progress edits.");
            True(table.Rows[^1].Details.Contains("origin (4294967295, 2147483648), extents (7, 5)") && table.Rows[^1].Details.Contains("14×14 brush"), "Rectangle words must retain unsigned extremes and native brush qualification.");
            Equal(4, InspectionPresentation.Simplify("Stored state blocks", table).Columns.Length);
            True(InspectionPresentation.Simplify("Stored state blocks", table).Rows[15].Cells[0].Contains("Metropolis"), "Native map-label associations should be readable.");
            True(bytes.SequenceEqual(before), "Grid header inspection must not mutate source.");
            Array.Clear(bytes);
            True(inspection.Table("Stored state blocks").Rows[^1].Details.Contains("DEADBEEF"), "Snapshot must be detached.");
        });
        Check("Reset-event category counters retain all eight unsigned words without inferred meanings", () =>
        {
            byte[] bytes = ResearchFixture();
            uint[] values = { uint.MaxValue, 0x80000000, 2, 3, 4, 5, 6, 0x7FFFFFFF };
            for (int id = 0; id < values.Length; id++)
                BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x5734 + id * 4, 4), values[id]);
            bytes[0x5754] = 0xAB;
            byte[] before = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var raw = inspection.Table("Reset-event counters");
            Equal(8, raw.Rows.Count); Equal(5, raw.Columns.Length);
            Equal("4294967295", raw.Rows[0].Cells[1]); Equal("2147483648", raw.Rows[1].Cells[1]);
            Equal("FFFFFFFF", raw.Rows[0].Cells[3]); Equal("0x5750", raw.Rows[^1].Cells[2]);
            True(raw.Rows[0].Details.Contains("BEFORE") && raw.Rows[0].Details.Contains("not a death total"), "Counter/segment gate differences must stay visible.");
            var friendly = InspectionPresentation.Simplify("Reset-event counters", raw);
            Equal(8, friendly.Rows.Count); Equal(3, friendly.Columns.Length);
            True(friendly.Rows[1].Details.Contains("selection remains unresolved"), "Do not invent category names.");
            True(bytes.SequenceEqual(before), "Counter inspection must not mutate the source.");
            Array.Clear(bytes);
            Equal("4294967295", inspection.Table("Reset-event counters").Rows[0].Cells[1]);
        });
        Check("Per-world object bitsets preserve BE64 ordering, distinct bands and all physical slots", () =>
        {
            byte[] bytes = ResearchFixture();
            int[] setSlots = { 0, 7, 8, 63, 64, 127, 1023, 1024, 2047 };
            foreach (int slot in setSlots)
            {
                int offset = 0x668 + slot / 64 * 8;
                ulong bits = BinaryPrimitives.ReadUInt64BigEndian(bytes.AsSpan(offset, 8)) | (1UL << (slot % 64));
                BinaryPrimitives.WriteUInt64BigEndian(bytes.AsSpan(offset, 8), bits);
            }
            BinaryPrimitives.WriteUInt64BigEndian(bytes.AsSpan(0x768, 8), 1UL << 2);
            BinaryPrimitives.WriteUInt64BigEndian(bytes.AsSpan(0x768 + 19 * 0x408 + 31 * 8, 8), 1UL << 63);
            BinaryPrimitives.WriteUInt32BigEndian(bytes.AsSpan(0x5500, 4), uint.MaxValue);
            byte[] before = bytes.ToArray();
            var inspection = TodSaveInspection.Read(bytes, "BCUS98127");
            var raw = inspection.Table("World object flags");
            Equal(40, raw.Rows.Count); Equal(7, raw.Columns.Length);
            Equal("9", raw.Rows[0].Cells[3]);
            Equal("0, 7, 8, 63, 64, 127, 1023, 1024, 2047", raw.Rows[0].Cells[6]);
            Equal("2", raw.Rows[1].Cells[6]); Equal("1", raw.Rows[^1].Cells[3]);
            Equal("2047", raw.Rows[^1].Cells[6]);
            True(raw.Rows[^1].Cells[5].EndsWith("8000000000000000"), "Last bit must retain BE64 byte order.");
            True(raw.Rows[0].Details.Contains("Not universally") && raw.Rows[1].Details.Contains("Other modes"), "Object-bit meanings must retain lifecycle/mode qualifications.");
            var friendly = InspectionPresentation.Simplify("World object flags", raw);
            Equal(38, friendly.Rows.Count); Equal(3, friendly.Columns.Length);
            True(friendly.Rows[0].Details.Contains("not named collectibles"), "Object slots must not become a collectible checklist.");
            True(bytes.SequenceEqual(before), "Object-bit inspection must not mutate input.");
            Array.Clear(bytes);
            Equal("9", inspection.Table("World object flags").Rows[0].Cells[3]);
        });
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
            Equal(9, raw.Columns.Length);
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
            Equal(1385, TodResearch.Map.GetProperty("annotations").GetArrayLength());
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
            True(text.Text.Contains("Combuster", StringComparison.OrdinalIgnoreCase), "Case-insensitive search should visibly identify a matching finding, including title-only matches and native uppercase enums.");
            True(text.Text.StartsWith(tree.SelectedNode.Text + "\r\n\r\n", StringComparison.Ordinal), "Details must identify the selected research title even when the query appears only in the title.");
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
                ("Objects & equipment", 2, 9), ("Blueprints", 2, 7), ("Bonuses & cheats", 3, 8), ("Stored state blocks", 4, 9), ("World progress", 4, 9), ("World object flags", 3, 7), ("Gameplay segments", 5, 9), ("Reset-event counters", 3, 5), ("Quick select", 2, 6), ("Saved locations", 3, 5), ("Save layout", 3, 4), ("Files & metadata", 3, 5) })
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
            Equal(21, grid.Rows.Count);
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
            var objectFlags = inspection.Table("World object flags");
            Equal(40, objectFlags.Rows.Count);
            for (int level = 0; level < 20; level++)
            {
                for (int band = 0; band < 2; band++)
                {
                    int offset = 0x668 + band * 0x100 + level * 0x408;
                    int setCount = 0;
                    for (int word = 0; word < 32; word++)
                        setCount += System.Numerics.BitOperations.PopCount(BinaryPrimitives.ReadUInt64BigEndian(bytes.AsSpan(offset + word * 8, 8)));
                    Equal(setCount.ToString(), objectFlags.Rows[level * 2 + band].Cells[3]);
                    Equal(Convert.ToHexString(bytes.AsSpan(offset, 256)), objectFlags.Rows[level * 2 + band].Cells[5]);
                }
            }
            if (Convert.ToHexString(SHA256.HashData(bytes)) == "F0EB338565943906E3C652C6BF89F1D868DC309DE34B46153D0E57E61BE30463")
            {
                True(objectFlags.Rows.All(r => r.Cells[3] == "0"), "Actual40 object bitsets must match zero source bytes without inferring object availability.");
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
            foreach (string view in new[] { "Weapons & gadgets", "Skill points", "Armor", "Skins", "Special bolts", "Blueprints", "Bonuses & cheats", "Stored state blocks", "Objects & equipment", "World progress", "World object flags", "Gameplay segments", "Global event flags", "Arena challenges", "Reset-event counters", "Quick select", "Player summary", "Game settings", "Saved locations", "Save layout", "Files & metadata" })
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
