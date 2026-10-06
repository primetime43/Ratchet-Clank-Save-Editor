using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed class SfoMetadata
    {
        private readonly Dictionary<string, byte[]> fields = new(StringComparer.Ordinal);
        public string Region { get; private set; }
        public string AccountId => Text("ACCOUNT_ID");
        public string Planet => Text("SUB_TITLE");

        private string Text(string key) => fields.TryGetValue(key, out var value)
            ? Encoding.UTF8.GetString(value).TrimEnd('\0') : string.Empty;

        public static SfoMetadata Read(string path)
        {
            byte[] data = File.ReadAllBytes(path);
            if (data.Length < 20 || BinaryPrimitives.ReadUInt32LittleEndian(data) != 0x46535000)
                throw new InvalidDataException("PARAM.SFO is not a valid PlayStation save metadata file.");
            uint keyStart = BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(8));
            uint valueStart = BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(12));
            uint count = BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(16));
            long indexEnd = 20L + count * 16L;
            if (indexEnd > data.Length || keyStart < indexEnd || valueStart < keyStart || valueStart > data.Length)
                throw new InvalidDataException("PARAM.SFO contains invalid table offsets.");
            var metadata = new SfoMetadata();
            for (int i = 0; i < count; i++)
            {
                var entry = data.AsSpan(20 + i * 16, 16);
                long keyOffset = keyStart + (long)BinaryPrimitives.ReadUInt16LittleEndian(entry);
                uint size = BinaryPrimitives.ReadUInt32LittleEndian(entry.Slice(4));
                uint capacity = BinaryPrimitives.ReadUInt32LittleEndian(entry.Slice(8));
                long valueOffset = valueStart + (long)BinaryPrimitives.ReadUInt32LittleEndian(entry.Slice(12));
                if (keyOffset >= valueStart || size > capacity || valueOffset + capacity > data.Length)
                    throw new InvalidDataException("PARAM.SFO contains an invalid field.");
                int keyEnd = Array.IndexOf(data, (byte)0, (int)keyOffset, (int)(valueStart - keyOffset));
                if (keyEnd < 0) throw new InvalidDataException("PARAM.SFO contains an unterminated field name.");
                string key = Encoding.ASCII.GetString(data, (int)keyOffset, keyEnd - (int)keyOffset);
                if (!metadata.fields.TryAdd(key, data.AsSpan((int)valueOffset, (int)size).ToArray()))
                    throw new InvalidDataException("PARAM.SFO contains duplicate fields.");
            }
            string directory = metadata.Text("SAVEDATA_DIRECTORY");
            string region = metadata.Text("TITLE_ID");
            if (string.IsNullOrEmpty(region) && directory.Length >= 9) region = directory.Substring(0, 9);
            if (region.Length != 9)
                throw new InvalidDataException("PARAM.SFO does not contain a valid game region.");
            metadata.Region = region;
            return metadata;
        }
    }
}
