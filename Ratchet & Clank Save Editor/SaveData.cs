using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // PS3 values are big endian, including the HD remasters (not PS2/Vita saves).
    // Format references and compatibility limitations are documented in README.md.
    public static class SaveData
    {
        public static readonly string[] CharacterNames = { "Ratchet", "Clank", "Qwark", "Nefarious" };
        private static readonly int[] CharacterOffsets = { 0x638, 0x1828, 0x2120, 0xF30 };

        public static int[] ReadBolts(byte[] data, SaveProfile profile)
        {
            Validate(data, profile);
            if (profile.Layout == CurrencyLayout.Characters)
            {
                var values = new int[CharacterOffsets.Length];
                for (int i = 0; i < values.Length; i++) values[i] = ReadInteger(data, CharacterOffsets[i]);
                return values;
            }
            if (profile.Layout == CurrencyLayout.NamedFloat)
            {
                float value = BinaryPrimitives.ReadSingleBigEndian(data.AsSpan(FindPlayerBolts(data), 4));
                if (!float.IsFinite(value) || value < 0 || value > profile.MaximumBolts || value != MathF.Truncate(value))
                    throw new InvalidDataException("The saved bolts value is not a supported whole-number currency value.");
                return new[] { (int)value };
            }
            return new[] { ReadInteger(data, profile.BoltsOffset) };
        }

        public static int ReadRaritanium(byte[] data, SaveProfile profile) =>
            profile.RaritaniumOffset is int offset ? ReadInteger(data, offset) : 0;

        public static void Write(byte[] data, SaveProfile profile, IReadOnlyList<int> bolts, int raritanium)
        {
            Validate(data, profile);
            int required = profile.Layout == CurrencyLayout.Characters ? 4 : 1;
            if (bolts.Count != required) throw new ArgumentException("The currency values do not match this game's layout.", nameof(bolts));
            foreach (int value in bolts)
                if (value < 0 || value > profile.MaximumBolts) throw new ArgumentOutOfRangeException(nameof(bolts));
            if (raritanium < 0) throw new ArgumentOutOfRangeException(nameof(raritanium));

            if (profile.Layout == CurrencyLayout.Characters)
            {
                for (int i = 0; i < required; i++)
                {
                    // A4O's documented currency patch updates these paired counters.
                    int offset = CharacterOffsets[i];
                    int previous = ReadInteger(data, offset);
                    if (previous == bolts[i]) continue;
                    BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(offset, 4), bolts[i]);
                    BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(offset + 4, 4), bolts[i]);
                }
            }
            else if (profile.Layout == CurrencyLayout.NamedFloat)
                BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(FindPlayerBolts(data), 4), bolts[0]);
            else
                BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(profile.BoltsOffset, 4), bolts[0]);
            if (profile.RaritaniumOffset is int raritaniumOffset)
                BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(raritaniumOffset, 4), raritanium);

            if (profile.HasChecksumBlocks)
            {
                // PS3 remasters accept the disabled-checksum sentinel used by Slim's
                // Editor. Only the currency block is changed; other blocks are preserved.
                // Do NOT apply the PS2 little-endian checksum routine to PS3 data.
                BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(12, 4), uint.MaxValue);
            }
        }

        private static int ReadInteger(byte[] data, int offset)
        {
            int value = BinaryPrimitives.ReadInt32BigEndian(data.AsSpan(offset, 4));
            if (value < 0) throw new InvalidDataException("The save contains invalid currency values. Check the selected save format and game region.");
            return value;
        }

        public static void Validate(byte[] data, SaveProfile profile)
        {
            profile.ValidateLength(data.Length);
            if (profile.Layout == CurrencyLayout.Characters && data.Length < CharacterOffsets[2] + 8)
                throw new InvalidDataException("GAME.SAV is truncated: character currency data is missing.");
            if (profile.Layout == CurrencyLayout.NamedFloat) FindPlayerBolts(data);
            if (!profile.HasChecksumBlocks) return;

            // Real PS3 saves reserve a fixed-size area for planet blocks. Unused
            // slots can have stale lengths extending beyond EOF. We edit only the
            // first (player) block, so validate that block and preserve the tail.
            uint size = BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(8, 4));
            long end = 16L + size;
            if (size == 0 || end > data.Length ||
                BinaryPrimitives.ReadUInt32BigEndian(data) != size + 8L ||
                end < Math.Max(profile.BoltsOffset, profile.RaritaniumOffset ?? profile.BoltsOffset) + 4L)
                throw new InvalidDataException("USR-DATA has an invalid or truncated player block. Check that the save is decrypted PS3 data.");
        }

        private static int FindPlayerBolts(byte[] data)
        {
            // QForce/FFA is a named-record format, not a fixed integer offset.
            // The documented cheat searches for "player_bolts\0" and writes a BE
            // float 14 bytes from that record. Reject ambiguous or absent records.
            ReadOnlySpan<byte> marker = "player_bolts\0"u8;
            int match = data.AsSpan().IndexOf(marker);
            if (match < 0)
                throw new InvalidDataException("This save has no player_bolts record. Save on a planet in Full Frontal Assault / QForce before editing.");
            if (data.AsSpan(match + marker.Length).IndexOf(marker) >= 0 || match + 18L > data.Length)
                throw new InvalidDataException("The player_bolts record is ambiguous or truncated; the save was not changed.");
            return match + 14;
        }
    }
}
