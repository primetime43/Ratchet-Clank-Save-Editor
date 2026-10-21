using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed record Rc1AmmoField(string Key, string Name, int Id, int Offset, int OwnershipOffset, int Current, int Maximum);
    public sealed record Rc1RecordDefinition(uint Id, int Length, int Offset);

    public static class Rc1Research
    {
        public static IReadOnlyList<Rc1AmmoField> Ammo { get; }
        public static IReadOnlyList<Rc1RecordDefinition> PlayerRecords { get; }

        static Rc1Research()
        {
            using var stream = typeof(Rc1Research).Assembly.GetManifestResourceStream("Research.Rc1.Map.json")
                ?? throw new InvalidDataException("The bundled RC1 reference map is missing.");
            using var document = JsonDocument.Parse(stream);
            Ammo = Array.AsReadOnly(document.RootElement.GetProperty("ammo").EnumerateArray().Select(item =>
                new Rc1AmmoField("rc1_ammo_" + item.GetProperty("id").GetInt32(), item.GetProperty("name").GetString(),
                    item.GetProperty("id").GetInt32(), item.GetProperty("offset").GetInt32(),
                    item.GetProperty("ownership_offset").GetInt32(), 0, item.GetProperty("maximum").GetInt32())).ToArray());
            PlayerRecords = Array.AsReadOnly(document.RootElement.GetProperty("player_records").EnumerateArray().Select(item =>
                new Rc1RecordDefinition(item.GetProperty("id").GetUInt32(), item.GetProperty("length").GetInt32(),
                    item.GetProperty("offset").GetInt32())).ToArray());
        }
    }

    public static class Rc1SaveEditing
    {
        public static bool Supports(byte[] data, string region)
        {
            // Native evidence is from the supplied European trilogy executable.
            if (!string.Equals(region, "NPEA00385", StringComparison.OrdinalIgnoreCase) || data?.Length != 0xB0000 ||
                BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(4)) != 0x82A4) return false;
            var snapshot = Rc1SaveInspection.Read(data, region);
            return snapshot.Available && snapshot.PlayerEnd == 0x1544 &&
                snapshot.Records.Count == Rc1Research.PlayerRecords.Count &&
                snapshot.Records.Zip(Rc1Research.PlayerRecords).All(pair => pair.First.Id == pair.Second.Id &&
                    pair.First.Length == pair.Second.Length && pair.First.Offset == pair.Second.Offset);
        }

        public static IReadOnlyList<Rc1AmmoField> Fields(byte[] data, string region)
        {
            if (!Supports(data, region)) return Array.Empty<Rc1AmmoField>();
            return Rc1Research.Ammo.Where(field => data[field.OwnershipOffset] == 1 &&
                    BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(field.Offset, 4)) <= field.Maximum)
                .Select(field => field with { Current = BinaryPrimitives.ReadInt32BigEndian(data.AsSpan(field.Offset, 4)) })
                .OrderBy(field => field.Name, StringComparer.CurrentCultureIgnoreCase).ToArray();
        }

        public static byte[] Apply(byte[] original, string region, IReadOnlyDictionary<string, decimal> edits)
        {
            ArgumentNullException.ThrowIfNull(original);
            ArgumentNullException.ThrowIfNull(edits);
            if (edits.Count == 0) return (byte[])original.Clone();
            if (!Supports(original, region)) throw new InvalidDataException("RC1 ammo editing requires the verified European NPEA00385 save layout.");
            var fields = Fields(original, region).ToDictionary(field => field.Key, StringComparer.Ordinal);
            // Validate the complete batch before allocating or applying any edits.
            foreach (var edit in edits)
            {
                if (!fields.TryGetValue(edit.Key, out var field))
                    throw new InvalidDataException("Unsupported RC1 edit or unavailable owned weapon: " + edit.Key);
                if (edit.Value != decimal.Truncate(edit.Value) || edit.Value < 0 || edit.Value > field.Maximum)
                    throw new InvalidDataException($"{field.Name} ammo must be a whole number between 0 and {field.Maximum}.");
            }
            byte[] result = (byte[])original.Clone();
            foreach (var edit in edits)
                BinaryPrimitives.WriteInt32BigEndian(result.AsSpan(fields[edit.Key].Offset, 4), (int)edit.Value);
            return result;
        }
    }
}
