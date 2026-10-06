using System.Buffers.Binary;
using System.IO;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // PS3 values are big endian. Reject truncated files instead of padding with zeroes.
    public static class StreamExtensions
    {
        public static int ReadInt32(this Stream stream)
        {
            System.Span<byte> buffer = stackalloc byte[4];
            stream.ReadExactly(buffer);
            return BinaryPrimitives.ReadInt32BigEndian(buffer);
        }

        public static void WriteInt32(this Stream stream, int value)
        {
            System.Span<byte> buffer = stackalloc byte[4];
            BinaryPrimitives.WriteInt32BigEndian(buffer, value);
            stream.Write(buffer);
        }
    }
}
