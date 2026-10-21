using System;
using System.Collections.Generic;
using System.Security.Cryptography;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed record TodRleSummary(int Consumed, int TrailingBytes, int DecodedSize, int ClippedBytes,
        int EncoderAccumulator, string Sha256, IReadOnlyDictionary<byte, int> Histogram)
    {
        public bool Complete => DecodedSize == 0x40000;
    }

    // Native-format research only; stricter input bounds than the game, no file writes.
    public static class TodRleInspection
    {
        public static TodRleSummary Decode(ReadOnlySpan<byte> encoded)
        {
            if (encoded.Length > 0x5FFF) throw new ArgumentException("Declared length exceeds native encoder cap.");
            var output = new byte[0x40000];
            var histogram = new SortedDictionary<byte, int>();
            int position = 0, written = 0, accumulator = 0, clipped = 0;
            while (position < encoded.Length && written < output.Length)
            {
                byte value = encoded[position];
                int count;
                if (written <= 0x3FFFB && position + 1 < encoded.Length && encoded[position + 1] == value)
                {
                    if (position + 4 > encoded.Length) throw new ArgumentException("Truncated repeated-byte token.");
                    int extra = (encoded[position + 2] << 8) | encoded[position + 3];
                    count = extra + 2;
                    if (value == 0) accumulator += extra;
                    position += 4;
                }
                else
                {
                    count = 1;
                    if (value == 0) accumulator++;
                    position++;
                }
                int take = Math.Min(count, output.Length - written);
                clipped += count - take;
                output.AsSpan(written, take).Fill(value);
                written += take;
                histogram[value] = histogram.GetValueOrDefault(value) + take;
            }
            return new(position, encoded.Length - position, written, clipped, accumulator,
                Convert.ToHexString(SHA256.HashData(output.AsSpan(0, written))),
                new System.Collections.ObjectModel.ReadOnlyDictionary<byte, int>(histogram));
        }
    }
}
