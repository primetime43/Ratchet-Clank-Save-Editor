using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed record Rc1PlayerRecord(uint Id, int HeaderOffset, int Offset, int Length, int Padding);

    // PS3 RC1 only. Structural observations and external field definitions are
    // documented in docs/PS3/RatchetAndClank1/SaveFormat.md. Never writes bytes.
    public sealed class Rc1SaveInspection
    {
        private readonly byte[] data;
        public bool Available => data != null;
        public string Message { get; }
        public int Length => data?.Length ?? 0;
        public int PlayerEnd { get; }
        public IReadOnlyList<Rc1PlayerRecord> Records { get; }
        public static bool Supports(string region) => region != null &&
            new[] { "NPEA00385", "NPUA80643", "NPJA40001" }.Contains(region, StringComparer.OrdinalIgnoreCase);

        private Rc1SaveInspection(string message, byte[] bytes = null, int playerEnd = 0,
            IReadOnlyList<Rc1PlayerRecord> records = null)
        {
            Message = message;
            data = bytes;
            PlayerEnd = playerEnd;
            Records = records ?? Array.Empty<Rc1PlayerRecord>();
        }

        public static Rc1SaveInspection Read(byte[] bytes, string region)
        {
            if (!Supports(region)) return new("RC1 inspection requires an individual PS3 Ratchet & Clank save ID.");
            if (bytes == null) return new("No plaintext USR-DATA was supplied.");
            try
            {
                SaveData.Validate(bytes, SaveProfile.ForRegion(region));
                int end = checked(16 + (int)BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(8, 4)));
                int position = 16;
                var records = new List<Rc1PlayerRecord>();
                var ids = new HashSet<uint>();
                bool terminated = false;
                while (position < end)
                {
                    if (end - position < 8) throw new InvalidDataException("Truncated player record header.");
                    uint id = BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(position, 4));
                    uint length = BinaryPrimitives.ReadUInt32BigEndian(bytes.AsSpan(position + 4, 4));
                    long next = position + 8L + ((length + 3L) & ~3L);
                    if (next > end) throw new InvalidDataException("Player record extends beyond its block.");
                    if (id == uint.MaxValue)
                    {
                        if (length != 0 || next != end) throw new InvalidDataException("Invalid player record terminator.");
                        terminated = true;
                        break;
                    }
                    if (!ids.Add(id)) throw new InvalidDataException("Duplicate player record ID.");
                    records.Add(new(id, position, position + 8, (int)length, (int)(next - position - 8 - length)));
                    position = (int)next;
                }
                if (!terminated) throw new InvalidDataException("Missing player record terminator.");
                if (!records.Any(record => record.Id == 1 && record.Offset == 0x24 && record.Length == 4))
                    throw new InvalidDataException("The bolts record does not match the supported RC1 layout.");
                return new("Read-only PS3 RC1 snapshot. Field names use external reference definitions; unknown records and padding are preserved. Pending edits are excluded.",
                    (byte[])bytes.Clone(), end, records.AsReadOnly());
            }
            catch (Exception error) when (error is InvalidDataException or OverflowException)
            {
                return new("RC1 inspection unavailable: " + error.Message + " No research fields were decoded.");
            }
        }

        private uint Word(int offset) => BinaryPrimitives.ReadUInt32BigEndian(data.AsSpan(offset, 4));
        private static string Hex(int offset) => "0x" + offset.ToString("X", CultureInfo.InvariantCulture);
        private Rc1PlayerRecord Record(uint id, int size) => Records.FirstOrDefault(record => record.Id == id && record.Length == size);
        private static InspectionRow Row(params string[] cells) => new(cells, string.Join("\r\n", cells));
        private InspectionTable Status(string message) => new(new[] { "Status" }, new[] { Row(message) });

        public InspectionTable Table(string view, bool technical)
        {
            InspectionTable source = Table(view);
            int[] selected = !technical && Available ? view switch
            {
                "Weapons & gadgets" when source.Columns.Length == 7 => new[] { 0, 1, 3 },
                "Counters & nearby fields" when source.Columns.Length == 4 => new[] { 0, 1 },
                "Quick select" when source.Columns.Length == 3 => new[] { 0, 1 },
                "Save regions" when source.Columns.Length == 4 => new[] { 0, 2, 3 },
                _ => Enumerable.Range(0, source.Columns.Length).ToArray()
            } : Enumerable.Range(0, source.Columns.Length).ToArray();
            return new(selected.Select(index => source.Columns[index]).ToArray(), source.Rows.Select(row =>
                new InspectionRow(selected.Select(index => row.Cells[index]).ToArray(),
                    string.Join("\r\n", source.Columns.Select((column, index) => column + ": " + row.Cells[index])) +
                    "\r\n\r\n" + Message)).ToArray());
        }

        public InspectionTable Table(string view)
        {
            if (!Available) return Status(Message);
            if (view == "Counters & nearby fields")
                return new(new[] { "Information", "Value", "Offset", "Interpretation" }, new[]
                {
                    Row("Game", "Ratchet & Clank (PS3)", "PARAM.SFO", "Trilogy and individual releases resolve through the individual save ID."),
                    Row("Bolts", Word(0x24).ToString(CultureInfo.InvariantCulture), "0x24", "Record 1, big-endian uint32. Editable through Game Save Editing."),
                    Row("Player records", Records.Count.ToString(CultureInfo.InvariantCulture), "0x10", "Excludes the FFFFFFFF / zero-length terminator."),
                    Row("Player block end", Hex(PlayerEnd), "0x8", "Derived from the payload length; later blocks are not decoded."),
                    Row("Stored player checksum", $"0x{Word(12):X8}", "0xC", "Not verified. Currency saves use the existing FFFFFFFF sentinel.")
                });
            if (view == "Save regions")
                return new(new[] { "Section", "Offset", "Bytes", "Interpretation" }, new[]
                {
                    Row("Container prefix", "0x0", "8", "Two big-endian block strides: player and repeated world blocks. The European reference writer emits 0x153C and 0x82A4."),
                    Row("Player block header", "0x8", "8", "Payload length and stored checksum; integrity is not checked by this view."),
                    Row("Player payload", "0x10", (PlayerEnd - 16).ToString(CultureInfo.InvariantCulture), "Tagged records aligned to four bytes, including a terminator."),
                    Row("Remaining save data", Hex(PlayerEnd), (Length - PlayerEnd).ToString(CultureInfo.InvariantCulture), "Opaque retained blocks and reserved storage; not assumed padding or unused.")
                });
            if (view == "Player records")
                return new(new[] { "Record ID", "Header", "Payload", "Bytes", "Alignment bytes", "Raw preview" },
                    Records.Select(record => Row(record.Id.ToString(CultureInfo.InvariantCulture), Hex(record.HeaderOffset), Hex(record.Offset),
                        record.Length.ToString(CultureInfo.InvariantCulture),
                        Convert.ToHexString(data.AsSpan(record.Offset + record.Length, record.Padding)),
                        Convert.ToHexString(data.AsSpan(record.Offset, Math.Min(record.Length, 16))))).ToArray());
            if (view == "Quick select")
            {
                var record = Record(13, 32);
                if (record == null || record.Offset != 0x22C) return Status("Quick-select record does not match the reference layout.");
                return new(new[] { "Stored slot", "Raw item ID", "Offset" }, Enumerable.Range(0, 8)
                    .Select(index => Row((index + 1).ToString(CultureInfo.InvariantCulture), $"0x{Word(record.Offset + index * 4):X8}",
                        Hex(record.Offset + index * 4))).ToArray());
            }
            if (view == "Weapons & gadgets") return Inventory();
            return Status("This view has no RC1 mapping yet. Use Player records or Hex bytes for raw data.");
        }

        private InspectionTable Inventory()
        {
            // These are reference byte/word offsets, gated on the matching record
            // boundaries. Flags and ammo are independent; no runtime availability inferred.
            if (Record(9, 148)?.Offset != 0x11C || Record(10, 37)?.Offset != 0x1B8)
                return Status("Inventory records do not match the reference layout; no item fields were decoded.");
            var items = new (string Name, int Flag, int? Ammo)[]
            {
                ("Bomb Glove", 450, 324), ("Pyrocitor", 456, 348), ("Blaster", 455, 344),
                ("Glove of Doom", 460, null), ("Mine Glove", 457, 352), ("Taunter", 454, null),
                ("Suck Cannon", 449, null), ("Devastator", 451, 328), ("Walloper", 458, null),
                ("Visibomb Gun", 453, 336), ("Decoy Glove", 465, 384), ("Drone Device", 464, 380),
                ("Tesla Claw", 459, 360), ("Morph-o-Ray", 461, null), ("R.Y.N.O.", 463, 376),
                ("Trespasser", 466, null), ("Hydrodisplacer", 462, null), ("Swingshot", 452, null),
                ("Gadgetron PDA", 472, null), ("Metal Detector", 467, null), ("Hologuise", 471, null),
                ("Heli-Pack", 442, null), ("Thruster-Pack", 443, null), ("Hydro-Pack", 444, null),
                ("O2 Mask", 446, null), ("Sonic Summoner", 445, null), ("Pilot's Helmet", 447, null),
                ("Grindboots", 469, null), ("Magneboots", 468, null), ("Hoverboard", 470, null),
                ("Persuader", 475, null), ("Bolt Grabber", 474, null), ("Map-o-matic", 473, null)
            };
            var rows = items.OrderBy(item => item.Name, StringComparer.CurrentCultureIgnoreCase).Select(item =>
            {
                byte flag = data[item.Flag];
                return Row(item.Name, flag == 0 ? "Clear" : "Set", $"0x{flag:X2}",
                    item.Ammo is int ammo ? Word(ammo).ToString(CultureInfo.InvariantCulture) : "Unmapped",
                    Hex(item.Flag), item.Ammo is int offset ? Hex(offset) : "",
                    "RC1 reference item names; native European record table confirms ammo/unlock storage. Saved flags and ammo only; no current availability check.");
            }).ToArray();
            return new(new[] { "Item", "Unlock flag", "Raw flag", "Stored ammo", "Flag offset", "Ammo offset", "Interpretation" }, rows);
        }

        public string HexBytes(int offset, int count = 256)
        {
            if (!Available) return Message;
            if (offset < 0 || offset >= Length || count < 1 || count > 4096) throw new ArgumentOutOfRangeException(nameof(offset));
            int end = (int)Math.Min(Length, (long)offset + count);
            var text = new StringBuilder("USR-DATA plaintext · file offsets\r\n");
            for (int start = offset; start < end; start += 16)
            {
                int size = Math.Min(16, end - start);
                text.Append(start.ToString("X8")).Append("  ");
                for (int index = 0; index < 16; index++) text.Append(index < size ? data[start + index].ToString("X2") + " " : "   ");
                text.Append(' ');
                for (int index = 0; index < size; index++) text.Append(data[start + index] is >= 32 and <= 126 ? (char)data[start + index] : '.');
                text.AppendLine();
            }
            return text.ToString();
        }
    }
}
