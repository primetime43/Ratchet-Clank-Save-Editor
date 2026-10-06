using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // Independent implementation of the documented PFD v3/v4 table format.
    // Native transforms update every SFO hash using a fallback disc key. Restore
    // the original SFO hashes instead, then sign the changed PFD tables. This is
    // possible without knowing the disc key ONLY while the SFO is unchanged.
    public static class PfdBinding
    {
        private const int EntrySize = 272;
        private static readonly byte[] PortabilityKey = Convert.FromHexString("D413B89663E1FE9F75143D3BB4565274");
        private static readonly byte[] KeygenKey = Convert.FromHexString("6B1ACEA246B745FD8F93763B920594CD53483B82");
        private static readonly byte[] SfoKey = Convert.FromHexString("0C08000E090504040D010F000406020209060D03");

        public static byte[] SfoHashes(byte[] pfd)
        {
            var table = Parse(pfd);
            return pfd.AsSpan(SfoEntry(pfd, table) + 144, 80).ToArray();
        }

        public static void ValidateSfo(byte[] pfd, byte[] sfo)
        {
            if (!CryptographicOperations.FixedTimeEquals(SfoHashes(pfd).AsSpan(0, 20), HMACSHA1.HashData(SfoKey, sfo)))
                throw new InvalidDataException("PARAM.SFO does not match its integrity database. Restore the matching original metadata before editing an encrypted save.");
        }

        public static void Preserve(byte[] original, byte[] transformed, byte[] sfo)
        {
            ValidateSfo(original, sfo);
            var table = Parse(transformed);
            SfoHashes(original).CopyTo(transformed, SfoEntry(transformed, table) + 144);
            Sign(transformed, table);
        }

        private readonly record struct Table(int Capacity, int Reserved, int Used, int Entries, int Signatures);

        private static Table Parse(byte[] data)
        {
            if (data.Length < 120 || data.Length > 32768 || Read64(data, 0) != 0x50464442 || Read64(data, 8) is not (3 or 4))
                throw new InvalidDataException("PARAM.PFD is not a supported PS3 integrity database.");
            ulong capacity = Read64(data, 96), reserved = Read64(data, 104), used = Read64(data, 112);
            if (capacity == 0 || capacity > 4096 || reserved == 0 || reserved > 4096 || used > reserved)
                throw new InvalidDataException("PARAM.PFD has invalid entry counts.");
            long entries = 120L + (long)capacity * 8;
            long signatures = entries + (long)reserved * EntrySize;
            if (signatures + (long)capacity * 20 > data.Length)
                throw new InvalidDataException("PARAM.PFD has truncated tables.");
            return new((int)capacity, (int)reserved, (int)used, (int)entries, (int)signatures);
        }

        private static int SfoEntry(byte[] data, Table table)
        {
            int result = -1;
            for (int i = 0; i < table.Used; i++)
            {
                int offset = table.Entries + i * EntrySize;
                var name = data.AsSpan(offset + 8, 65);
                int end = name.IndexOf((byte)0);
                if (end < 0) throw new InvalidDataException("PARAM.PFD has an unterminated file name.");
                if (!Encoding.ASCII.GetString(name[..end]).Equals("PARAM.SFO", StringComparison.OrdinalIgnoreCase)) continue;
                if (result >= 0) throw new InvalidDataException("PARAM.PFD contains duplicate metadata entries.");
                result = offset;
            }
            if (result < 0) throw new InvalidDataException("PARAM.PFD contains no PARAM.SFO entry.");
            return result;
        }

        private static void Sign(byte[] data, Table table)
        {
            using var aes = Aes.Create();
            aes.Key = PortabilityKey;
            byte[] iv = data.AsSpan(16, 16).ToArray();
            byte[] signature = aes.DecryptCbc(data.AsSpan(32, 64), iv, PaddingMode.None);
            byte[] seed = signature.AsSpan(40, 20).ToArray();
            byte[] key = Read64(data, 8) == 4 ? HMACSHA1.HashData(KeygenKey, seed) : seed;

            for (int bucket = 0; bucket < table.Capacity; bucket++)
            {
                using var hash = IncrementalHash.CreateHMAC(HashAlgorithmName.SHA1, key);
                ulong index = Read64(data, 120 + bucket * 8);
                var visited = new HashSet<ulong>();
                while (index < (ulong)table.Reserved)
                {
                    if (!visited.Add(index)) throw new InvalidDataException("PARAM.PFD has a cyclic hash chain.");
                    int entry = table.Entries + (int)index * EntrySize;
                    hash.AppendData(data.AsSpan(entry + 8, 65));
                    hash.AppendData(data.AsSpan(entry + 80, 192));
                    index = Read64(data, entry);
                }
                hash.GetHashAndReset().CopyTo(data, table.Signatures + bucket * 20);
            }
            HMACSHA1.HashData(key, data.AsSpan(table.Signatures, table.Capacity * 20)).CopyTo(signature, 0);
            HMACSHA1.HashData(key, data.AsSpan(96, 24 + table.Capacity * 8)).CopyTo(signature, 20);
            aes.EncryptCbc(signature, iv, PaddingMode.None).CopyTo(data, 32);
        }

        private static ulong Read64(byte[] data, int offset) => BinaryPrimitives.ReadUInt64BigEndian(data.AsSpan(offset, 8));
    }
}
