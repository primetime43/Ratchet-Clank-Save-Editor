using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public enum TodEditStorage { BooleanByte, BooleanWord, Float, Choice, ByteChoice, WeaponLevel, AmmoUpgrade, WeaponUpgrade, DeveloperAction, SkillAward, OwnershipGrant, HeroXp }
    public enum TodBulkEdit { RefillSupportedAmmo, MaximumOwnedWeaponTier }
    public sealed record TodEditOption(decimal Value, string Label)
    {
        public override string ToString() => Label;
    }
    public sealed record TodEditField(string Key, string Label, string Category, int Offset,
        TodEditStorage Storage, decimal Current, decimal Maximum, decimal Scale = 1,
        IReadOnlyList<TodEditOption> Options = null, decimal Minimum = 0, float? ReferenceMaximum = null);

    // Explicit allowlist, never a generic offset writer or native transaction emulator.
    public static class TodSaveEditing
    {
        public static bool Supports(byte[] data, string region)
        {
            if (!string.Equals(region, "BCUS98127", StringComparison.OrdinalIgnoreCase) ||
                data == null || data.Length != TodSaveInspection.ExpectedSize) return false;
            for (int id = 0; id < 32; id++)
                if (BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(id * 20, 4)) != id) return false;
            return true;
        }

        public static IReadOnlyList<TodEditField> Fields(byte[] data, string region)
        {
            var fields = new List<TodEditField>();
            if (!Supports(data, region)) return fields.AsReadOnly();
            uint Word(int offset) => BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(offset, 4));
            void Boolean(string key, string label, int offset, bool word = false)
            {
                fields.Add(new(key, label, "Game settings", offset,
                    word ? TodEditStorage.BooleanWord : TodEditStorage.BooleanByte,
                    (word ? Word(offset) : data[offset]) == 0 ? 0 : 1, 1));
            }
            void Percent(string key, string label, int offset)
            {
                float value = BinaryPrimitives.ReadSingleBigEndian(data.AsSpan(offset, 4));
                if (float.IsFinite(value) && value >= 0 && value <= 1)
                    fields.Add(new(key, label, "Game settings", offset, TodEditStorage.Float,
                        (decimal)value * 100, 100, 100));
            }
            Boolean("camera_x", "Invert camera X", 0x114A8, true);
            Boolean("camera_y", "Invert camera Y", 0x114AC, true);
            Percent("camera_speed", "Camera speed (%)", 0x114B0);
            Boolean("look_x", "Invert look X", 0x114B4, true);
            Boolean("look_y", "Invert look Y", 0x114B8, true);
            uint scheme = Word(0x114BC);
            if (scheme <= 1)
                fields.Add(new("control_scheme", "Control scheme", "Game settings", 0x114BC,
                    TodEditStorage.Choice, scheme, 1, Options: new[]
                    { new TodEditOption(0, "Scheme 0"), new TodEditOption(1, "Scheme 1") }));
            Percent("voice_volume", "Voice volume (%)", 0x114C4);
            Percent("effects_volume", "Effects volume (%)", 0x114C8);
            Percent("music_volume", "Music volume (%)", 0x114CC);
            Boolean("help_text", "Help text", 0x114D0);
            Boolean("subtitles", "Subtitles", 0x114D1);
            Boolean("quick_select_pause", "Pause during quick select", 0x114D2);
            Boolean("sixaxis", "Sixaxis controls", 0x114D3);
            Boolean("rumble", "Rumble", 0x114D4);
            Boolean("surround", "Surround sound", 0x114D5);

            // The multiplier's runtime cache/countdown are seeded on load, not
            // serialized fields. Do not enable replay mode or repair bad inputs.
            float multiplier = BinaryPrimitives.ReadSingleBigEndian(data.AsSpan(0x428, 4));
            if (Word(0x906EC) != 0 && float.IsFinite(multiplier) && multiplier >= 1 && multiplier <= 20)
                fields.Add(new("bolt_multiplier", "Bolt multiplier (1–20×)", "Rewards", 0x428,
                    TodEditStorage.Float, (decimal)multiplier, 20, Minimum: 1));

            // Only normal owned combat records with complete reference inputs.
            for (int id = 1; id <= 15; id++)
            {
                int offset = id * 20;
                string name = TodResearch.Inventory[id].GetProperty("config_name").GetString();
                if (data[offset + 16] == 0 || !TodResearch.TryConfig(name, out var config)) continue;
                var variables = config.GetProperty("variables");
                if (!variables.TryGetProperty("MaxAmmo", out var amounts)) continue;
                int level = data[offset + 17];
                if (level >= 20 || level >= amounts.GetArrayLength() ||
                    amounts[level].ValueKind != System.Text.Json.JsonValueKind.Number) continue;
                float maximum = amounts[level].GetSingle(), factor = 1;
                uint mask = Word(offset + 12);
                var nodes = config.GetProperty("modifiers");
                int count = nodes.GetArrayLength();
                if (count > 24 || (mask & ~((1u << count) - 1)) != 0) continue;
                bool complete = true;
                foreach (var node in nodes.EnumerateArray())
                {
                    int index = node.GetProperty("index").GetInt32();
                    if (index < 0 || index >= count) { complete = false; break; }
                    if ((mask & (1u << index)) == 0 || node.GetProperty("type").GetString() != "MOD_AMMO") continue;
                    var value = node.GetProperty("runtime_value");
                    if (value.ValueKind != System.Text.Json.JsonValueKind.Number) { complete = false; break; }
                    if (node.GetProperty("is_percent").GetBoolean()) factor += value.GetSingle();
                    else maximum += value.GetSingle();
                }
                maximum *= factor;
                float current = BinaryPrimitives.ReadSingleBigEndian(data.AsSpan(offset + 8, 4));
                if (!complete || !float.IsFinite(maximum) || maximum <= 0 || maximum > 1_000_000 ||
                    !float.IsFinite(current) || current < 0 || current > maximum) continue;
                fields.Add(new("ammo_" + id, name + " ammo", "Weapon ammo", offset + 8,
                    TodEditStorage.Float, (decimal)current, (decimal)maximum, ReferenceMaximum: maximum));
            }

            TodWeaponLevelEditing.AddFields(data, fields);
            TodGadgetAmmoEditing.AddFields(data, fields);
            TodAmmoUpgradeEditing.AddFields(data, fields);
            TodDeveloperEditing.AddFields(fields);
            TodSkillAwardEditing.AddFields(data, fields);
            TodHeroXpEditing.AddFields(data, fields);

            TodAppearanceEditing.AddFields(data, fields);

            // Physical bonus IDs, not language-remapped menu indices. The shipped
            // menu cycles 0..count-1; the generic native setter's 1..8 bound is wider.
            var bonusMap = TodResearch.Map.GetProperty("bonus_selection");
            uint score = Word(TodResearch.Offset(bonusMap.GetProperty("score_offset")));
            foreach (var bonus in bonusMap.GetProperty("catalog").EnumerateArray())
            {
                int offset = TodResearch.Offset(bonus.GetProperty("state_offset"));
                int count = bonus.GetProperty("state_count_including_off").GetInt32();
                if (score < bonus.GetProperty("score_requirement").GetUInt32() || data[offset] >= count) continue;
                var options = bonus.GetProperty("options").EnumerateArray().Select(option =>
                    new TodEditOption(option.GetProperty("value").GetDecimal(), option.GetProperty("label").GetString())).ToArray();
                fields.Add(new(bonus.GetProperty("key").GetString(), bonus.GetProperty("label").GetString(),
                    "Bonus effects", offset, TodEditStorage.ByteChoice, data[offset], count - 1, Options: options));
            }
            var quickChoices = new List<TodEditOption> { new(-1, "Empty") };
            foreach (var item in TodResearch.Map.GetProperty("quick_select_eligibility").GetProperty("catalog").EnumerateArray())
            {
                int id = item.GetProperty("id").GetInt32();
                if (item.GetProperty("quick_select_initially_allowed").GetBoolean() && data[id * 20 + 16] != 0)
                    quickChoices.Add(new(id, item.GetProperty("config_name").GetString()));
            }
            for (int slot = 0; slot < 24; slot++)
            {
                int offset = 0x284 + 4 * slot;
                int current = BinaryPrimitives.ReadInt32BigEndian(data.AsSpan(offset, 4));
                var options = quickChoices.ToList();
                if (!options.Any(option => option.Value == current))
                    options.Add(new(current, "Current: " + current + " (unverified)"));
                fields.Add(new("qs_" + slot, "Stored slot " + slot, "Quick select", offset,
                    TodEditStorage.Choice, current, Math.Max(31, current), Options: options.AsReadOnly(),
                    Minimum: Math.Min(-1, current)));
            }
            return fields.AsReadOnly();
        }

        // Returns a detached, validated plan; never writes the save or grants
        // unsupported records. Explicit bulk actions replace only their targets.
        public static IReadOnlyDictionary<string, decimal> PlanBulk(byte[] original, string region,
            IReadOnlyDictionary<string, decimal> existing, TodBulkEdit action)
        {
            if (!Supports(original, region))
                throw new InvalidDataException("Bulk edits require the verified BCUS98127 Tools of Destruction layout.");
            ArgumentNullException.ThrowIfNull(existing);
            if (!Enum.IsDefined(action)) throw new ArgumentOutOfRangeException(nameof(action));
            var fields = Fields(original, region);
            var plan = new Dictionary<string, decimal>(existing, StringComparer.Ordinal);
            var targets = fields.Where(field => action == TodBulkEdit.RefillSupportedAmmo
                ? field.Category is "Weapon ammo" or "Gadget ammo"
                : field.Storage == TodEditStorage.WeaponLevel);
            foreach (var field in targets)
            {
                decimal value = action == TodBulkEdit.RefillSupportedAmmo && field.Category == "Weapon ammo"
                    ? TodAmmoUpgradeEditing.Maximum(original, field, plan) : field.Maximum;
                if (value == field.Current) plan.Remove(field.Key);
                else plan[field.Key] = value;
            }
            Apply(original, region, plan); // preflight the complete merged batch
            return plan;
        }

        public static byte[] Apply(byte[] original, string region, IReadOnlyDictionary<string, decimal> edits)
        {
            ArgumentNullException.ThrowIfNull(original);
            ArgumentNullException.ThrowIfNull(edits);
            var requested = edits.ToArray();
            if (requested.Length == 0) return (byte[])original.Clone();
            if (!Supports(original, region))
                throw new InvalidDataException("Mapped edits require the verified BCUS98127 Tools of Destruction layout.");
            var fields = Fields(original, region).ToDictionary(field => field.Key, StringComparer.Ordinal);
            foreach (var edit in requested)
            {
                if (!fields.TryGetValue(edit.Key, out var field))
                    throw new InvalidDataException("This field is not editable in the current save: " + edit.Key);
                decimal maximum = field.Category == "Weapon ammo" ? TodAmmoUpgradeEditing.Maximum(original, field, edits) : field.Maximum;
                if (field.Storage == TodEditStorage.HeroXp && edit.Value != field.Current)
                    maximum = TodHeroXpEditing.MaximumXp;
                var options = TodAppearanceEditing.SelectionOptions(field, original, edits);
                if (edit.Value < field.Minimum || edit.Value > maximum ||
                    (field.Storage != TodEditStorage.Float && edit.Value != decimal.Truncate(edit.Value)) ||
                    (options != null && !options.Any(option => option.Value == edit.Value)))
                    throw new InvalidDataException("Invalid value for " + field.Label + ".");
                if (field.Storage == TodEditStorage.Float)
                {
                    float value = (float)(edit.Value / field.Scale);
                    if (!float.IsFinite(value) || value > (float)(maximum / field.Scale))
                        throw new InvalidDataException("Value exceeds the reference limit for " + field.Label + ".");
                }
            }
            byte[] result = (byte[])original.Clone();
            TodSkillAwardEditing.Apply(result, edits);
            var levelChanges = requested.Where(edit => fields[edit.Key].Storage == TodEditStorage.WeaponLevel &&
                edit.Value != fields[edit.Key].Current).ToArray();
            foreach (var edit in levelChanges)
                TodWeaponLevelEditing.Apply(original, result, fields[edit.Key], edit.Value, fields);
            TodAmmoUpgradeEditing.Apply(original, result, fields, edits);
            TodDeveloperEditing.Apply(result, edits, fields);
            foreach (var edit in requested)
            {
                var field = fields[edit.Key];
                if (field.Storage is TodEditStorage.WeaponLevel or TodEditStorage.AmmoUpgrade or TodEditStorage.WeaponUpgrade or TodEditStorage.DeveloperAction or TodEditStorage.SkillAward) continue; // Coupled plans already applied.
                if (edit.Value == field.Current)
                {
                    // Explicit ammo overrides either coupled refill, retaining
                    // the original float bits for a same-value request.
                    if (field.Category == "Weapon ammo")
                        original.AsSpan(field.Offset, 4).CopyTo(result.AsSpan(field.Offset, 4));
                    continue; // Preserve noncanonical flags/raw float bits.
                }
                if (field.Storage is TodEditStorage.BooleanByte or TodEditStorage.ByteChoice) result[field.Offset] = (byte)edit.Value;
                else if (field.Storage == TodEditStorage.Float)
                    BinaryPrimitives.WriteSingleBigEndian(result.AsSpan(field.Offset, 4), (float)(edit.Value / field.Scale));
                else if (field.Category == "Quick select")
                    BinaryPrimitives.WriteInt32BigEndian(result.AsSpan(field.Offset, 4), (int)edit.Value);
                else BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(field.Offset, 4), (uint)edit.Value);
            }
            // Reject only newly assigned duplicates. Existing unusual banks and
            // semantic no-ops stay untouched; batch moves can clear the old slot.
            foreach (var edit in requested)
            {
                var field = fields[edit.Key];
                if (field.Category != "Quick select" || edit.Value == field.Current || edit.Value < 0) continue;
                int matches = 0;
                for (int slot = 0; slot < 32; slot++)
                    if (BinaryPrimitives.ReadInt32BigEndian(result.AsSpan(0x284 + 4 * slot, 4)) == edit.Value) matches++;
                if (matches > 1)
                    throw new InvalidDataException(field.Label + " would duplicate an item. Clear its other slot first, or include that move in the same save.");
            }
            return result;
        }
    }
}
