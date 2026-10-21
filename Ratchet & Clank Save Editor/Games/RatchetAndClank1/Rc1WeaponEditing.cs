using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed record Rc1WeaponDefinition(int Id, string Name, int Maximum, int InitialAmmo, bool GrantSupported,
        bool AcquisitionList, int OwnershipOffset, int AcquisitionFlagOffset, int AmmoOffset);
    public sealed record Rc1GrantField(string Key, Rc1WeaponDefinition Weapon, bool Owned);
    public sealed record Rc1QuickOption(uint Value, string Name) { public override string ToString() => Name; }
    public sealed record Rc1QuickField(string Key, int Offset, uint Current, IReadOnlyList<Rc1QuickOption> Options);

    public static class Rc1WeaponEditing
    {
        private const int AcquisitionOffset = 0x218, AcquisitionCount = 12, QuickOffset = 0x22C, QuickCount = 8;
        private static uint Word(byte[] data, int offset) => BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(offset, 4));
        public static bool IsKey(string key) => key.StartsWith("rc1_grant_", StringComparison.Ordinal) || key.StartsWith("rc1_quick_", StringComparison.Ordinal);

        public static IReadOnlyList<Rc1GrantField> Grants(byte[] data, string region)
        {
            if (!Rc1SaveEditing.Supports(data, region)) return Array.Empty<Rc1GrantField>();
            return Rc1Research.Weapons.Where(weapon => weapon.GrantSupported &&
                    (data[weapon.OwnershipOffset] == 1 || CanGrant(data, weapon)))
                .OrderBy(weapon => weapon.Name, StringComparer.CurrentCultureIgnoreCase)
                .Select(weapon => new Rc1GrantField("rc1_grant_" + weapon.Id, weapon, data[weapon.OwnershipOffset] == 1)).ToArray();
        }

        private static bool CanGrant(byte[] data, Rc1WeaponDefinition weapon)
        {
            if (data[weapon.OwnershipOffset] != 0 || data[weapon.AcquisitionFlagOffset] != 0 || Word(data, weapon.AmmoOffset) > weapon.Maximum)
                return false;
            if (!weapon.AcquisitionList) return true;
            var list = data.AsSpan(AcquisitionOffset, AcquisitionCount);
            if (list.IndexOf((byte)0xFF) < 0) return false;
            foreach (byte value in list)
                if (value != 0xFF && (value & 0x3F) == weapon.Id) return false;
            return true;
        }

        public static IReadOnlyList<Rc1QuickField> QuickSelect(byte[] data, string region)
        {
            if (!Rc1SaveEditing.Supports(data, region)) return Array.Empty<Rc1QuickField>();
            var choices = Rc1Research.Weapons.Where(weapon => data[weapon.OwnershipOffset] == 1)
                .Select(weapon => new Rc1QuickOption((uint)weapon.Id, weapon.Name))
                .Append(new(0, "Empty")).ToArray();
            return Enumerable.Range(0, QuickCount).Select(slot =>
            {
                int offset = QuickOffset + slot * 4;
                uint value = Word(data, offset);
                var options = choices.AsEnumerable();
                if (!choices.Any(option => option.Value == value))
                    options = options.Append(new(value, $"Stored item 0x{value:X8} (preserve only)"));
                return new Rc1QuickField("rc1_quick_" + slot, offset, value,
                    options.OrderBy(option => option.Name, StringComparer.CurrentCultureIgnoreCase).ToArray());
            }).ToArray();
        }

        internal static byte[] Apply(byte[] original, byte[] result, string region, IReadOnlyDictionary<string, decimal> edits)
        {
            if (!edits.Keys.Any(IsKey)) return result;
            var grants = Grants(original, region).ToDictionary(field => field.Key, StringComparer.Ordinal);
            var slots = QuickSelect(original, region).ToDictionary(field => field.Key, StringComparer.Ordinal);
            var newGrants = new List<Rc1GrantField>();
            foreach (var edit in edits.Where(edit => IsKey(edit.Key)))
            {
                if (grants.TryGetValue(edit.Key, out var grant))
                {
                    if (edit.Value != 0 && edit.Value != 1 || grant.Owned && edit.Value != 1)
                        throw new InvalidDataException("RC1 weapon grants are add-only.");
                    if (!grant.Owned && edit.Value == 1) newGrants.Add(grant);
                }
                else if (slots.TryGetValue(edit.Key, out var slot))
                {
                    if (edit.Value != decimal.Truncate(edit.Value) || edit.Value < 0 || edit.Value > uint.MaxValue ||
                        !slot.Options.Any(option => option.Value == edit.Value))
                        throw new InvalidDataException("Quick select requires an owned supported weapon, Empty, or the unchanged stored value.");
                    if (edit.Value == slot.Current) continue;
                    BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(slot.Offset, 4), (uint)edit.Value);
                }
                else throw new InvalidDataException("Unsupported RC1 weapon edit or unavailable grant: " + edit.Key);
            }
            // Check final explicit assignments so batch moves/swaps are atomic.
            foreach (var edit in edits.Where(edit => slots.ContainsKey(edit.Key)))
            {
                var slot = slots[edit.Key];
                if (edit.Value == 0 || edit.Value == slot.Current) continue;
                int count = Enumerable.Range(0, QuickCount).Count(index => Word(result, QuickOffset + index * 4) == edit.Value);
                if (count > 1) throw new InvalidDataException("A new quick-select assignment would duplicate an item. Clear its other slot first.");
            }
            // Deterministic grant ordering also makes combined batches independent
            // of dictionary insertion order. Explicit quick-select edits run first.
            foreach (var grant in newGrants.OrderBy(grant => grant.Weapon.Id))
            {
                var weapon = grant.Weapon;
                result[weapon.OwnershipOffset] = result[weapon.AcquisitionFlagOffset] = 1;
                uint ammo = Math.Max(Word(original, weapon.AmmoOffset), (uint)weapon.InitialAmmo);
                BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(weapon.AmmoOffset, 4), ammo);
                if (weapon.AcquisitionList)
                {
                    int empty = result.AsSpan(AcquisitionOffset, AcquisitionCount).IndexOf((byte)0xFF);
                    if (empty < 0) throw new InvalidDataException("The RC1 acquisition list has no free entry. No grant was saved.");
                    result[AcquisitionOffset + empty] = (byte)(weapon.Id | 0x40);
                }
                bool assigned = Enumerable.Range(0, QuickCount).Any(index => Word(result, QuickOffset + index * 4) == weapon.Id);
                if (assigned) continue;
                for (int index = 0; index < QuickCount; index++)
                {
                    int offset = QuickOffset + index * 4;
                    if (Word(result, offset) != 0) continue;
                    BinaryPrimitives.WriteUInt32BigEndian(result.AsSpan(offset, 4), (uint)weapon.Id);
                    break;
                }
            }
            return result;
        }
    }
}
