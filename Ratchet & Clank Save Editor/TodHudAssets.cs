using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // Exact-build local artwork only. Never executes assets or modifies the game.
    public sealed class TodHudAssets
    {
        private const string PackName = "/processed/texpacks/hud.tp", HeaderName = "/processed/texpacks/hud.tph";
        private const string PackHash = "FF662581D84107A7F4D77B83DA3B74277C5E36FDFB333C0CB15029A3FD434D16";
        private const string HeaderHash = "A057E6F0B48DD6968BB72DB33D261952D041B43196C8B262F87684F547A5FBA3";
        private readonly byte[] pack, header;
        public const int TextureCount = 208;
        public static string CacheFolder => Path.Combine(AppContext.BaseDirectory, "PreviewAssets", "PS3", "ToolsOfDestruction", "BCUS98127", "v02.00");

        private TodHudAssets(byte[] pack, byte[] header)
        {
            if (Convert.ToHexString(SHA256.HashData(pack)) != PackHash || Convert.ToHexString(SHA256.HashData(header)) != HeaderHash)
                throw new InvalidDataException("These HUD assets do not match the researched Tools of Destruction USA build.");
            this.pack = pack; this.header = header;
            for (int index = 0; index < TextureCount; index++) Dimensions(index); // preflight every record
        }

        public static TodHudAssets FromArchive(string path)
        {
            var entries = ReadArchive(path, new[] { PackName, HeaderName });
            return new(entries[PackName], entries[HeaderName]);
        }

        public static TodHudAssets FromCache(string folder)
        {
            byte[] Read(string name, int maximum)
            {
                string path = Path.Combine(folder, name);
                if (new FileInfo(path).Length > maximum) throw new InvalidDataException("Oversized preview cache file.");
                return File.ReadAllBytes(path);
            }
            return new(Read("hud.tp", 3 * 1024 * 1024), Read("hud.tph", 8192));
        }

        public void SaveCache(string folder)
        {
            Directory.CreateDirectory(folder);
            // Existing unknown files are not overwritten. A partial cache can
            // be completed on retry because each accepted file is fingerprinted.
            foreach (var entry in new[] { ("hud.tp", pack), ("hud.tph", header) })
            {
                string path = Path.Combine(folder, entry.Item1);
                if (File.Exists(path) && (new FileInfo(path).Length != entry.Item2.Length ||
                    !SHA256.HashData(File.ReadAllBytes(path)).SequenceEqual(SHA256.HashData(entry.Item2))))
                    throw new IOException("An unrecognized preview cache file already exists: " + entry.Item1);
            }
            foreach (var entry in new[] { ("hud.tp", pack), ("hud.tph", header) })
            {
                string path = Path.Combine(folder, entry.Item1);
                if (File.Exists(path)) continue;
                using var target = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None);
                target.Write(entry.Item2);
            }
        }

        private (int Width, int Height, int Offset) Dimensions(int index)
        {
            if (index < 0 || index >= TextureCount) throw new ArgumentOutOfRangeException(nameof(index));
            int record = 0x80 + index * 32;
            int width = BinaryPrimitives.ReadUInt16BigEndian(header.AsSpan(record + 24, 2));
            int height = BinaryPrimitives.ReadUInt16BigEndian(header.AsSpan(record + 26, 2));
            long offset = 0x80L + BinaryPrimitives.ReadUInt32BigEndian(header.AsSpan(record, 4));
            int blocks = ((width + 3) / 4) * ((height + 3) / 4);
            if (width < 1 || height < 1 || width > 1024 || height > 1024 ||
                (header[record + 6] & ~0x20) != 0x88 || offset + 16L * blocks > 0x268800 || offset + 16L * blocks > pack.Length)
                throw new InvalidDataException("Unsupported or out-of-bounds HUD texture record.");
            return (width, height, (int)offset);
        }

        public Bitmap DecodeTexture(int index)
        {
            var size = Dimensions(index);
            int length = ((size.Width + 3) / 4) * ((size.Height + 3) / 4) * 16;
            return DecodeBc3(pack.AsSpan(size.Offset, length), size.Width, size.Height);
        }

        // RSX BC3/DXT5 blocks remain row-major even for format0x88. Descriptor
        // words are BE; compressed block endpoints/indices are little-endian.
        // Reference: RPCS3 Emu/RSX/Common/TextureUtils.cpp (copy_decoded_bc3_block).
        public static Bitmap DecodeBc3(ReadOnlySpan<byte> source, int width, int height)
        {
            if (width < 1 || height < 1 || width > 1024 || height > 1024 ||
                source.Length != ((width + 3) / 4) * ((height + 3) / 4) * 16)
                throw new InvalidDataException("Invalid bounded BC3 image dimensions or payload length.");
            byte[] pixels = new byte[width * height * 4];
            int position = 0;
            Span<int> alpha = stackalloc int[8];
            Span<int> colors = stackalloc int[12];
            for (int by = 0; by < height; by += 4)
            for (int bx = 0; bx < width; bx += 4)
            {
                var block = source.Slice(position, 16); position += 16;
                alpha[0] = block[0]; alpha[1] = block[1];
                if (alpha[0] > alpha[1])
                    for (int i = 2; i < 8; i++) alpha[i] = ((8 - i) * alpha[0] + (i - 1) * alpha[1]) / 7;
                else
                {
                    for (int i = 2; i < 6; i++) alpha[i] = ((6 - i) * alpha[0] + (i - 1) * alpha[1]) / 5;
                    alpha[6] = 0; alpha[7] = 255;
                }
                ulong alphaBits = 0;
                for (int i = 0; i < 6; i++) alphaBits |= (ulong)block[2 + i] << (8 * i);
                for (int c = 0; c < 2; c++)
                {
                    ushort value = BinaryPrimitives.ReadUInt16LittleEndian(block.Slice(8 + c * 2, 2));
                    colors[c * 3] = ((value >> 11) & 31) * 255 / 31;
                    colors[c * 3 + 1] = ((value >> 5) & 63) * 255 / 63;
                    colors[c * 3 + 2] = (value & 31) * 255 / 31;
                }
                for (int channel = 0; channel < 3; channel++)
                {
                    colors[6 + channel] = (2 * colors[channel] + colors[3 + channel]) / 3;
                    colors[9 + channel] = (colors[channel] + 2 * colors[3 + channel]) / 3;
                }
                uint colorBits = BinaryPrimitives.ReadUInt32LittleEndian(block.Slice(12, 4));
                for (int y = 0; y < 4; y++)
                for (int x = 0; x < 4; x++)
                {
                    int pixel = y * 4 + x;
                    if (bx + x >= width || by + y >= height) continue;
                    int destination = ((by + y) * width + bx + x) * 4;
                    int color = (int)((colorBits >> (pixel * 2)) & 3) * 3;
                    pixels[destination] = (byte)colors[color + 2]; pixels[destination + 1] = (byte)colors[color + 1];
                    pixels[destination + 2] = (byte)colors[color]; pixels[destination + 3] = (byte)alpha[(int)((alphaBits >> (pixel * 3)) & 7)];
                }
            }
            var bitmap = new Bitmap(width, height, PixelFormat.Format32bppArgb);
            var locked = bitmap.LockBits(new Rectangle(0, 0, width, height), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
            try { for (int row = 0; row < height; row++) Marshal.Copy(pixels, row * width * 4, locked.Scan0 + row * locked.Stride, width * 4); }
            finally { bitmap.UnlockBits(locked); }
            return bitmap;
        }

        private sealed record Entry(byte[] Digest, int FirstBlock, long Length, long Offset);
        private static Dictionary<string, byte[]> ReadArchive(string path, string[] wanted)
        {
            using var file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
            byte[] head = new byte[32]; file.ReadExactly(head);
            uint Word(int offset) => BinaryPrimitives.ReadUInt32BigEndian(head.AsSpan(offset, 4));
            uint count = Word(20), end = Word(12), version = Word(4);
            if (!head.AsSpan(0, 4).SequenceEqual("PSAR"u8) || version != 0x10002 ||
                !head.AsSpan(8, 4).SequenceEqual("zlib"u8) || Word(16) != 30 || Word(24) != 65536 || Word(28) != 3 ||
                count < 1 || count > 100000 || end < 32 + count * 30 || end > 8 * 1024 * 1024 || end > file.Length ||
                (end - 32 - count * 30) % 2 != 0)
                throw new InvalidDataException("Unsupported or invalid bounded PSARC header.");
            byte[] toc = new byte[end - 32]; file.ReadExactly(toc);
            long Five(ReadOnlySpan<byte> bytes) { long value = 0; foreach (byte b in bytes) value = (value << 8) | b; return value; }
            var entries = new List<Entry>();
            int blockStart = checked((int)count * 30), blockCount = (toc.Length - blockStart) / 2;
            for (int i = 0; i < count; i++)
            {
                var record = toc.AsSpan(i * 30, 30);
                entries.Add(new(record[..16].ToArray(), checked((int)BinaryPrimitives.ReadUInt32BigEndian(record.Slice(16, 4))),
                    Five(record.Slice(20, 5)), Five(record.Slice(25, 5))));
            }
            byte[] Read(int index, int limit)
            {
                var entry = entries[index];
                int blocks = checked((int)((entry.Length + 65535) / 65536));
                if (entry.Length < 0 || entry.Length > limit || entry.FirstBlock < 0 || entry.FirstBlock > blockCount - blocks ||
                    entry.Offset < end || entry.Offset > file.Length)
                    throw new InvalidDataException("PSARC entry exceeds bounded read limits.");
                byte[] result = new byte[checked((int)entry.Length)]; file.Position = entry.Offset;
                for (int block = 0, destination = 0; block < blocks; block++)
                {
                    int expected = Math.Min(65536, result.Length - destination);
                    int stored = BinaryPrimitives.ReadUInt16BigEndian(toc.AsSpan(blockStart + (entry.FirstBlock + block) * 2, 2));
                    int length = stored == 0 ? expected : stored;
                    if (file.Position > file.Length - length) throw new InvalidDataException("Truncated PSARC entry.");
                    byte[] raw = new byte[length]; file.ReadExactly(raw);
                    if (stored == 0 || stored == expected) raw.CopyTo(result, destination);
                    else
                    {
                        using var compressed = new MemoryStream(raw, false);
                        using var inflater = new ZLibStream(compressed, CompressionMode.Decompress);
                        inflater.ReadExactly(result.AsSpan(destination, expected));
                        if (inflater.ReadByte() != -1) throw new InvalidDataException("Oversized PSARC zlib block.");
                    }
                    destination += expected;
                }
                return result;
            }
            string[] names = new UTF8Encoding(false, true).GetString(Read(0, 4 * 1024 * 1024)).TrimEnd('\n', '\r').Split('\n');
            if (names.Length != count - 1) throw new InvalidDataException("PSARC manifest count mismatch.");
            var output = new Dictionary<string, byte[]>(StringComparer.Ordinal);
            foreach (string name in wanted)
            {
                int[] matches = Enumerable.Range(0, names.Length).Where(index => names[index].TrimEnd('\r') == name).ToArray();
                if (matches.Length != 1) throw new InvalidDataException("Missing or ambiguous HUD asset: " + name);
                int index = matches[0] + 1;
                if (!MD5.HashData(Encoding.ASCII.GetBytes(name.ToUpperInvariant())).SequenceEqual(entries[index].Digest))
                    throw new InvalidDataException("HUD asset name digest mismatch.");
                output[name] = Read(index, name == HeaderName ? 8192 : 3 * 1024 * 1024);
            }
            return output;
        }
    }
}
