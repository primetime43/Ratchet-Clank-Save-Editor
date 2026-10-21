using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Linq;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // Saved ownership writes only. No purchase, currency charge, availability
    // update or runtime armor-effect/notification callback is simulated.
    internal static class TodAppearanceEditing
    {
        private static readonly string[] Armor = { "None", "Durafiber", "Hyperplate", "Tetramesh", "Quantonium" };
        private static readonly string[] Skins = { "None", "Dan", "Snowman", "Cragmite", "Pete", "Cronk", "Zephyr", "Jailbird", "Furioso" };

        internal static void AddFields(byte[] data, List<TodEditField> fields)
        {
            Add("armor", Armor, 0x444, 0x458, "Armor unlocks");
            Add("skin", Skins, 0x45C, 0x480, "Skin unlocks");

            void Add(string key, string[] names, int ownedBase, int selectedOffset, string category)
            {
                uint selected = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(selectedOffset, 4));
                var options = new List<TodEditOption>();
                for (int id = 0; id < names.Length; id++)
                {
                    int offset = ownedBase + 4 * id;
                    bool owned = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(offset, 4)) != 0;
                    if (owned) options.Add(new(id, names[id]));
                    fields.Add(new(key + "_owned_" + id, names[id], category, offset,
                        TodEditStorage.OwnershipGrant, owned ? 1 : 0, 1, Minimum: owned ? 1 : 0,
                        Options: owned ? new[] { new TodEditOption(1, "Already owned") } :
                            new[] { new TodEditOption(0, "Keep unchanged"), new TodEditOption(1, "Grant ownership on Save All") }));
                }
                if (!options.Any(option => option.Value == selected))
                    options.Add(new(selected, "Current: " + selected + " (unverified)"));
                fields.Add(new(key, "Selected " + key, "Appearance", selectedOffset,
                    TodEditStorage.Choice, selected, uint.MaxValue, Options: options.AsReadOnly()));
            }
        }

        internal static IReadOnlyList<TodEditOption> SelectionOptions(TodEditField field, byte[] data,
            IReadOnlyDictionary<string, decimal> edits)
        {
            if (field.Key is not ("armor" or "skin")) return field.Options;
            bool armor = field.Key == "armor";
            string[] names = armor ? Armor : Skins;
            int ownedBase = armor ? 0x444 : 0x45C;
            var options = new List<TodEditOption>();
            for (int id = 0; id < names.Length; id++)
                if (BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(ownedBase + 4 * id, 4)) != 0 ||
                    (edits.TryGetValue(field.Key + "_owned_" + id, out decimal grant) && grant == 1))
                    options.Add(new(id, names[id]));
            if (!options.Any(option => option.Value == field.Current))
                options.Add(field.Options.Single(option => option.Value == field.Current));
            return options.AsReadOnly();
        }

        internal static bool CancelDependentSelection(TodEditField grant, IDictionary<string, decimal> pending)
        {
            if (grant.Storage != TodEditStorage.OwnershipGrant || grant.Current != 0 || pending.ContainsKey(grant.Key)) return false;
            int separator = grant.Key.IndexOf("_owned_", StringComparison.Ordinal);
            string selectionKey = grant.Key[..separator];
            int id = (grant.Offset - (selectionKey == "armor" ? 0x444 : 0x45C)) / 4;
            return pending.TryGetValue(selectionKey, out decimal selection) && selection == id && pending.Remove(selectionKey);
        }
    }
}
