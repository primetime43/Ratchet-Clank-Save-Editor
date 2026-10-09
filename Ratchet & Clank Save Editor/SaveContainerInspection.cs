using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // Container structure only: no signing, key export, decryption or source writes.
    public static class SaveContainerInspection
    {
        public static InspectionTable Read(string workingFolder, string gameFile, byte[] plaintext)
        {
            var rows = new List<InspectionRow>();
            foreach (string name in new[] { gameFile, "PARAM.SFO", "PARAM.PFD", "ICON0.PNG", "PIC1.PNG" })
            {
                string path = Path.Combine(workingFolder, name);
                if (!File.Exists(path)) continue;
                try
                {
                    long length = new FileInfo(path).Length;
                    if (length > 16 * 1024 * 1024) throw new InvalidDataException("File exceeds the 16 MiB inspection limit.");
                    byte[] bytes = name == gameFile ? plaintext : File.ReadAllBytes(path);
                    Add(rows, name, 0, "Length", $"{bytes.Length:N0} bytes ({TodResearch.Hex(bytes.Length)})",
                        name == gameFile ? "Current plaintext session baseline, not pending edits or original ciphertext." : "Working-copy file, not necessarily the original source bytes.");
                    Add(rows, name, 0, "SHA-256", Convert.ToHexString(SHA256.HashData(bytes)), "Fingerprint only, not an integrity or in-game acceptance check.");
                    if (name == "PARAM.SFO") Sfo(rows, bytes);
                    if (name == "PARAM.PFD") Pfd(rows, bytes);
                    if (name.EndsWith(".PNG", StringComparison.OrdinalIgnoreCase)) Png(rows, name, bytes);
                }
                catch (Exception error) when (error is IOException or InvalidDataException or UnauthorizedAccessException or ArgumentException)
                {
                    Add(rows, name, 0, "Inspection unavailable", error.Message, "Read-only inspection failure does not change save files or disable the existing currency editor.");
                }
            }
            return new(new[] { "File", "Offset", "Field / entry", "Value", "Interpretation" }, rows.AsReadOnly());
        }

        private static void Add(List<InspectionRow> rows, string file, int offset, string field, string value, string note) =>
            rows.Add(new(new[] { file, TodResearch.Hex(offset), field, value, note }, $"{file} · {TodResearch.Hex(offset)} · {field}\r\n{value}\r\n{note}"));
        private static uint Le32(byte[] data, int offset) => BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(offset, 4));
        private static ulong Be64(byte[] data, int offset) => BinaryPrimitives.ReadUInt64BigEndian(data.AsSpan(offset, 8));
        private static uint Be32(byte[] data, int offset) => BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(offset, 4));
        private static string Text(byte[] data, int offset, int length) => Encoding.UTF8.GetString(data, offset, length).Split('\0')[0];

        private static void Sfo(List<InspectionRow> rows, byte[] data)
        {
            if (data.Length < 20 || Le32(data, 0) != 0x46535000) throw new InvalidDataException("Invalid SFO magic/header.");
            uint keys = Le32(data, 8), values = Le32(data, 12), count = Le32(data, 16);
            if (count > 4096 || 20L + 16L * count > keys || keys > values || values > data.Length)
                throw new InvalidDataException("Invalid SFO table bounds.");
            Add(rows, "PARAM.SFO", 0, "Magic", "00 50 53 46", "PSF metadata; integers are little endian.");
            foreach (var field in new[] { (4, "Version"), (8, "Key table offset"), (12, "Data table offset"), (16, "Field count") })
                Add(rows, "PARAM.SFO", field.Item1, field.Item2, TodResearch.Hex((int)Le32(data, field.Item1)), "Little-endian uint32 header field.");
            var names = new HashSet<string>(StringComparer.Ordinal);
            for (int index = 0; index < count; index++)
            {
                int entry = 20 + 16 * index;
                long key = (long)keys + BinaryPrimitives.ReadUInt16LittleEndian(data.AsSpan(entry, 2));
                long value = (long)values + Le32(data, entry + 12);
                uint length = Le32(data, entry + 4), capacity = Le32(data, entry + 8);
                ushort type = BinaryPrimitives.ReadUInt16LittleEndian(data.AsSpan(entry + 2, 2));
                if (key >= values || length > capacity || value + capacity > data.Length)
                    throw new InvalidDataException("Invalid SFO field bounds.");
                int end = Array.IndexOf(data, (byte)0, (int)key, (int)(values - key));
                if (end < 0) throw new InvalidDataException("Unterminated SFO key.");
                string name = Text(data, (int)key, end - (int)key);
                if (!names.Add(name)) throw new InvalidDataException("Duplicate SFO key.");
                string displayed = name == "ACCOUNT_ID" || type == 4 ? "[redacted ownership / binary data]" :
                    type == 0x0404 && length == 4 ? Le32(data, (int)value).ToString(CultureInfo.InvariantCulture) :
                    type == 0x0204 ? Text(data, (int)value, (int)length) : "[uninterpreted type]";
                Add(rows, "PARAM.SFO", (int)value, name, displayed,
                    $"Index {TodResearch.Hex(entry)}, key {TodResearch.Hex((int)key)}, type 0x{type:X4}, used {length}, capacity {capacity}.");
            }
        }

        private static void Pfd(List<InspectionRow> rows, byte[] data)
        {
            if (data.Length < 120 || Be64(data, 0) != 0x50464442 || Be64(data, 8) is not (3 or 4))
                throw new InvalidDataException("Invalid/unsupported PFD v3/v4 header.");
            ulong buckets = Be64(data, 96), reserved = Be64(data, 104), used = Be64(data, 112);
            if (buckets is 0 or > 4096 || reserved is 0 or > 4096 || used > reserved)
                throw new InvalidDataException("Invalid PFD table counts.");
            int entries = 120 + (int)buckets * 8, signatures = entries + (int)reserved * 272;
            if (signatures + (long)buckets * 20 > data.Length) throw new InvalidDataException("Truncated PFD tables.");
            Add(rows, "PARAM.PFD", 0, "Magic", "0x50464442", "PFD wrapper, not a GAME.SAV header. Big-endian integers; cryptographic integrity is not checked by this view.");
            foreach (var field in new[] { (8, "Version"), (96, "Bucket count"), (104, "Reserved entries"), (112, "Used entries") })
                Add(rows, "PARAM.PFD", field.Item1, field.Item2, Be64(data, field.Item1).ToString(CultureInfo.InvariantCulture), "Big-endian uint64.");
            Add(rows, "PARAM.PFD", 16, "IV", "[redacted]", "16-byte IV; values are not exported.");
            Add(rows, "PARAM.PFD", 32, "Encrypted signature", "[redacted]", "64 bytes; not decrypted by inspection.");
            for (int index = 0; index < (int)buckets; index++)
                Add(rows, "PARAM.PFD", 120 + index * 8, "Bucket " + index, Be64(data, 120 + index * 8).ToString(CultureInfo.InvariantCulture), "Entry-chain index, not a save offset.");
            for (int index = 0; index < (int)used; index++)
            {
                int offset = entries + index * 272;
                if (Array.IndexOf(data, (byte)0, offset + 8, 65) < 0) throw new InvalidDataException("Unterminated PFD filename.");
                Add(rows, "PARAM.PFD", offset, "Entry " + index, Text(data, offset + 8, 65),
                    $"Stride 272; chain {Be64(data, offset)}; stored size {Be64(data, offset + 264)} at {TodResearch.Hex(offset + 264)}. Opaque key at {TodResearch.Hex(offset + 80)}, hashes at {TodResearch.Hex(offset + 144)}; values redacted.");
            }
            Add(rows, "PARAM.PFD", signatures, "Signature table", ((int)buckets * 20) + " bytes", "Hash values redacted; not independently validated.");
            Add(rows, "PARAM.PFD", signatures + (int)buckets * 20, "Trailing bytes", (data.Length - signatures - (int)buckets * 20).ToString(), "Uninterpreted trailing bytes, not disposable padding.");
        }

        private static void Png(List<InspectionRow> rows, string file, byte[] data)
        {
            if (data.Length < 33 || Convert.ToHexString(data, 0, 8) != "89504E470D0A1A0A" || Be32(data, 8) != 13 || Text(data, 12, 4) != "IHDR")
                throw new InvalidDataException("Invalid PNG signature/IHDR.");
            Add(rows, file, 16, "Dimensions", $"{Be32(data, 16)} × {Be32(data, 20)}", $"Depth {data[24]}, color type {data[25]}, compression {data[26]}, filter {data[27]}, interlace {data[28]}. Stored CRCs are not verified.");
            int offset = 8, count = 0;
            bool ended = false;
            while (offset + 12 <= data.Length)
            {
                if (++count > 4096) throw new InvalidDataException("PNG chunk count exceeds inspection limit.");
                uint length = Be32(data, offset);
                if (offset + 12L + length > data.Length) throw new InvalidDataException("Truncated PNG chunk.");
                string type = Text(data, offset + 4, 4);
                int crc = offset + 8 + (int)length;
                Add(rows, file, offset, type, length + " data bytes", $"CRC at {TodResearch.Hex(crc)}: 0x{Be32(data, crc):X8}, not verified.");
                offset += 12 + (int)length;
                if (type == "IEND") { ended = length == 0; break; }
            }
            if (!ended) throw new InvalidDataException("Missing/invalid PNG IEND.");
            Add(rows, file, offset, "Trailing bytes", (data.Length - offset).ToString(), "Uninterpreted bytes after IEND.");
        }
    }
}
