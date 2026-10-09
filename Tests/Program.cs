using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static int passed;

    [STAThread]
    private static int Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
        string root = Path.Combine(Path.GetTempPath(), "RatchetClankSaveEditor-Tests-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            Check("Big endian values round trip, including int.MaxValue", () =>
            {
                using var stream = new MemoryStream();
                stream.WriteInt32(int.MaxValue);
                Equal("7FFFFFFF", Convert.ToHexString(stream.ToArray()));
                stream.Position = 0;
                Equal(int.MaxValue, stream.ReadInt32());
            });
            Check("Partial reads complete, truncated values fail", () =>
            {
                using var partial = new PartialReadStream(new byte[] { 0x12, 0x34, 0x56, 0x78 });
                Equal(0x12345678, partial.ReadInt32());
                using var truncated = new MemoryStream(new byte[] { 1, 2, 3 });
                Throws<EndOfStreamException>(() => truncated.ReadInt32());
            });
            Check("SFO fields can move and Unicode subtitles are preserved", () =>
            {
                string folder = Fixture(root, "NPUA80908");
                var metadata = SfoMetadata.Read(Path.Combine(folder, "PARAM.SFO"));
                Equal("NPUA80908", metadata.Region);
                Equal("0001020304050607", metadata.AccountId);
                Equal("Planète Veldin", metadata.Planet);
                byte[] data = File.ReadAllBytes(Path.Combine(folder, "PARAM.SFO"));
                BinaryPrimitives.WriteUInt32LittleEndian(data.AsSpan(12), uint.MaxValue);
                File.WriteAllBytes(Path.Combine(folder, "PARAM.SFO"), data);
                Throws<InvalidDataException>(() => SfoMetadata.Read(Path.Combine(folder, "PARAM.SFO")));
            });
            Check("Default backups stay beside the executable, independent of working directory", () =>
            {
                string previousDirectory = Environment.CurrentDirectory;
                try
                {
                    Environment.CurrentDirectory = root;
                    Equal(Path.Combine(AppContext.BaseDirectory, "Backups"), SaveSession.BackupRoot);
                    True(!SaveSession.BackupRoot.StartsWith(root, StringComparison.OrdinalIgnoreCase),
                        "Backups must not follow the working directory.");
                }
                finally { Environment.CurrentDirectory = previousDirectory; }
            });
            Check("Opening creates a verified full backup before decryption", () =>
            {
                string folder = Fixture(root, "NPUA80908");
                var original = Snapshot(folder);
                string backupRoot = Path.Combine(root, "before-decryption-backups");
                string backup = null;
                var tools = new FakeTools
                {
                    BeforeDecrypt = () =>
                    {
                        backup = Directory.GetDirectories(Path.Combine(backupRoot, Path.GetFileName(folder))).Single();
                        Same(original, Snapshot(backup));
                        Same(original, Snapshot(folder));
                    }
                };
                using var session = SaveSession.Open(folder, tools, backupRoot: backupRoot);
                Equal(backup, session.LastBackup);
                Same(original, Snapshot(session.LastBackup));
                True(!original["PARAM.PFD"].SequenceEqual(File.ReadAllBytes(Path.Combine(session.WorkingFolder, "PARAM.PFD"))),
                    "The backup must retain the original PFD, not the processed working copy.");
            });
            Check("Reopening keeps separate automatic backups after sessions close", () =>
            {
                string folder = Fixture(root, "NPUA80908");
                var original = Snapshot(folder);
                string firstBackup;
                string secondBackup;
                using (var first = SaveSession.Open(folder, new FakeTools(), backupRoot: Path.Combine(root, "backups")))
                    firstBackup = first.LastBackup;
                using (var second = SaveSession.Open(folder, new FakeTools(), backupRoot: Path.Combine(root, "backups")))
                    secondBackup = second.LastBackup;
                True(firstBackup != secondBackup, "Reopening must never overwrite an earlier backup.");
                Same(original, Snapshot(firstBackup));
                Same(original, Snapshot(secondBackup));
                Same(original, Snapshot(folder));
            });
            Check("Automatic backup failures stop opening without calling decryption", () =>
            {
                string blockedRoot = Path.Combine(root, "backup-root-is-a-file");
                File.WriteAllText(blockedRoot, "Cannot create a backup directory here.");
                foreach (bool decrypted in new[] { false, true })
                {
                    string folder = Fixture(root, "NPUA80908");
                    var original = Snapshot(folder);
                    var tools = new FakeTools();
                    Throws<IOException>(() => SaveSession.Open(folder, tools, decrypted, blockedRoot));
                    Equal(0, tools.CryptoCalls);
                    Same(original, Snapshot(folder));
                }
            });
            Check("A failed decryption retains the untouched automatic backup", () =>
            {
                string folder = Fixture(root, "NPUA80908");
                var original = Snapshot(folder);
                string backupRoot = Path.Combine(root, "failed-decryption-backups");
                Throws<InvalidOperationException>(() => SaveSession.Open(folder, new FakeTools { FailDecrypt = true }, backupRoot: backupRoot));
                string backup = Directory.GetDirectories(Path.Combine(backupRoot, Path.GetFileName(folder))).Single();
                Same(original, Snapshot(backup));
                Same(original, Snapshot(folder));
            });
            foreach (string region in SaveProfile.SupportedRegions.Keys)
                Check($"{region}: correct file, offsets, backups and repeat saves", () =>
                {
                    string folder = Fixture(root, region);
                    var tools = new FakeTools();
                    var original = Snapshot(folder);
                    using var session = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "backups"));
                    Equal(session.Profile.FileName, tools.DecryptedFile);
                    Equal(123, session.Bolts);
                    Equal(session.Profile.RaritaniumOffset.HasValue ? 45 : 0, session.Raritanium);
                    Same(original, Snapshot(folder));
                    string openingBackup = session.LastBackup;
                    Same(original, Snapshot(openingBackup));
                    string backup = session.Save(session.Profile.MaximumBolts, 987, Path.Combine(root, "backups"));
                    True(openingBackup != backup, "Saving must keep the opening backup and create a new one.");
                    Same(original, Snapshot(openingBackup));
                    Same(original, Snapshot(backup));
                    Equal(session.Profile.MaximumBolts, SaveData.ReadBolts(File.ReadAllBytes(Path.Combine(folder, session.Profile.FileName)), session.Profile)[0]);
                    if (session.Profile.RaritaniumOffset is int offset)
                        Equal(987, ReadValue(folder, offset, session.Profile.FileName));
                    Equal(session.Profile.FileName, tools.EncryptedFile);
                    string secondBackup = session.Save(999, 12, Path.Combine(root, "backups"));
                    True(backup != secondBackup, "Backups must be unique.");
                    Equal(999, session.Bolts);
                    Equal(999, SaveData.ReadBolts(File.ReadAllBytes(Path.Combine(folder, session.Profile.FileName)), session.Profile)[0]);
                    var expected = original[session.Profile.FileName].ToArray();
                    SaveData.Write(expected, session.Profile, session.CharacterBolts, 12);
                    True(expected.SequenceEqual(File.ReadAllBytes(Path.Combine(folder, session.Profile.FileName))), "Unrelated bytes changed.");
                });
            Check("Encryption failures never change original files", () =>
            {
                string folder = Fixture(root, "NPUA80908");
                var tools = new FakeTools { FailEncrypt = true };
                var original = Snapshot(folder);
                using var session = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "backups"));
                Throws<InvalidOperationException>(() => session.Save(999, 999, Path.Combine(root, "backups")));
                Same(original, Snapshot(folder));
                Equal(123, session.Bolts);
            });
            CompatibilityChecks(root);
            NativeCryptoChecks(root);
            Check("Missing, unsupported, truncated and invalid saves are rejected", () =>
            {
                string unsupported = Fixture(root, "NPUA80908");
                File.WriteAllBytes(Path.Combine(unsupported, "PARAM.SFO"), Sfo("UNKNOWN01"));
                Throws<InvalidDataException>(() => SaveSession.Open(unsupported, new FakeTools(), backupRoot: Path.Combine(root, "backups")));
                string missing = Fixture(root, "NPUA80643");
                File.Delete(Path.Combine(missing, "USR-DATA"));
                Throws<FileNotFoundException>(() => SaveSession.Open(missing, new FakeTools(), backupRoot: Path.Combine(root, "backups")));
                string truncated = Fixture(root, "NPUA80908");
                File.WriteAllBytes(Path.Combine(truncated, "GAME.SAV"), new byte[10]);
                Throws<InvalidDataException>(() => SaveSession.Open(truncated, new FakeTools(), backupRoot: Path.Combine(root, "backups")));
                string negative = Fixture(root, "NPUA80643");
                using (var file = File.OpenWrite(Path.Combine(negative, "USR-DATA"))) { file.Position = 0x24; file.WriteInt32(-1); }
                Throws<InvalidDataException>(() => SaveSession.Open(negative, new FakeTools(), backupRoot: Path.Combine(root, "backups")));
            });
            Check("External changes block save and backup", () =>
            {
                string folder = Fixture(root, "NPUA80908");
                using var session = SaveSession.Open(folder, new FakeTools(), backupRoot: Path.Combine(root, "backups"));
                File.WriteAllText(Path.Combine(folder, "PARAM.PFD"), "Changed externally");
                var changed = Snapshot(folder);
                Throws<IOException>(() => session.Save(9, 9, Path.Combine(root, "backups")));
                Throws<IOException>(() => session.BackUp(Path.Combine(root, "backups")));
                Same(changed, Snapshot(folder));
            });
            Check("Partial commit rolls back and keeps a full backup", () =>
            {
                string folder = Fixture(root, "NPUA80908");
                var original = Snapshot(folder);
                using var session = SaveSession.Open(folder, new FakeTools(), backupRoot: Path.Combine(root, "backups"));
                // Hold the second file against replacement so the first replacement succeeds then rolls back.
                using var locked = File.Open(Path.Combine(folder, "PARAM.SFO"), FileMode.Open, FileAccess.Read, FileShare.Read);
                Throws<IOException>(() => session.Save(999, 999, Path.Combine(root, "backups")));
                Same(original, Snapshot(folder));
                Same(original, Snapshot(session.LastBackup));
                Equal(123, session.Bolts);
            });
            Check("Metadata actions stay in the working copy until save", () =>
            {
                string folder = Fixture(root, "NPUA80908");
                var original = Snapshot(folder);
                using var session = SaveSession.Open(folder, new FakeTools(), backupRoot: Path.Combine(root, "backups"));
                session.PatchMetadata();
                session.UpdateIntegrity();
                True(session.MetadataChanged, "Metadata should be pending.");
                Same(original, Snapshot(folder));
                session.Save(123, 45, Path.Combine(root, "backups"));
                True(!session.MetadataChanged, "Metadata flag should clear after save.");
            });
            Check("Bundled pfdtool silent failures are detected, including paths with spaces", () =>
            {
                string folder = Fixture(root, "NPUA80643");
                var original = Snapshot(folder);
                using var tools = new Encryption();
                // Deliberately invalid PARAM.PFD: the legacy exe silently returns exit code zero.
                Throws<InvalidOperationException>(() => SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "backups")));
                Throws<InvalidOperationException>(() => tools.Update(folder, "NPUA80643"));
                Same(original, Snapshot(folder));
            });
            ResearchChecks(root);
            Check("Compact UI loads, switches games and renders at higher scale", () => UiChecks(root));
            if (args.Length == 2 && args[0] == "--samples") SampleChecks(root, Path.GetFullPath(args[1]));
            if (args.Length == 2 && args[0] == "--tod-save") ReferenceResearchChecks(root, Path.GetFullPath(args[1]));
            Console.WriteLine($"All {passed} regression checks passed.");
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
        finally { Directory.Delete(root, true); }
    }

    private static void CompatibilityChecks(string root)
    {
        Check("All ten PS3 games have independently documented layouts", () =>
        {
            Equal(10, SaveProfile.SupportedRegions.Values.Distinct().Count());
            foreach (var (region, offset, rare, key) in new[]
            {
                ("NPUA80643", 0x24, (int?)null, "01020304050607FACB0A0B0C0D0E0F10"),
                ("NPEA00386", 0x24, (int?)0x28, "C0A3B3641C2AD1EF23153A48A3E12FE8"),
                ("NPEA00387", 0x24, (int?)null, "C0A3B3641C2AD1EF23153A48A3E12FE7"),
                ("NPUA80646", 0x24, (int?)null, "0403020105060700000A0B0C0D0E0F10"),
                ("BCUS98124", 0x588, (int?)null, "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")
            })
            {
                var profile = SaveProfile.ForRegion(region);
                Equal(offset, profile.BoltsOffset); Equal(rare, profile.RaritaniumOffset); Equal(key, profile.Key);
            }
        });
        Check("Trilogy checksum blocks are bounded and only the currency block changes", () =>
        {
            string folder = Fixture(root, "NPEA00387");
            var profile = SaveProfile.ForRegion("NPEA00387");
            byte[] original = File.ReadAllBytes(Path.Combine(folder, profile.FileName));
            byte[] expected = original.ToArray();
            expected[12] = expected[13] = expected[14] = expected[15] = 0xFF;
            BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x24), 0x123456);
            SaveData.Write(original, profile, new[] { 0x123456 }, 0);
            True(expected.SequenceEqual(original), "Unedited block or unrelated bytes changed.");
            BinaryPrimitives.WriteUInt32BigEndian(original.AsSpan(8), uint.MaxValue);
            Throws<InvalidDataException>(() => SaveData.ReadBolts(original, profile));
            BinaryPrimitives.WriteUInt32BigEndian(original.AsSpan(8), 0);
            Throws<InvalidDataException>(() => SaveData.ReadBolts(original, profile));
            Throws<InvalidDataException>(() => SaveData.ReadBolts(expected[..0x800], profile));
            Equal(0x123456, SaveData.ReadBolts(expected[..^1], profile)[0]);
        });
        Check("Collection title IDs resolve to individual saves; conflicting games are rejected", () =>
        {
            string folder = Fixture(root, "NPEA00387");
            string path = Path.Combine(folder, "PARAM.SFO");
            File.WriteAllBytes(path, Sfo("NPEA00387", "BCES01503"));
            Equal("NPEA00387", SfoMetadata.Read(path).Region);
            File.WriteAllBytes(path, Sfo("NPEA00387", "NPUA80644"));
            Throws<InvalidDataException>(() => SfoMetadata.Read(path));
        });
        Check("Decrypted saves retain their format, optional PFD and full backups", () =>
        {
            foreach (bool hasPfd in new[] { true, false })
            {
                string folder = Fixture(root, "BCUS98124");
                if (!hasPfd) File.Delete(Path.Combine(folder, "PARAM.PFD"));
                var original = Snapshot(folder);
                var tools = new FakeTools { FailDecrypt = true, FailEncrypt = true };
                using var session = SaveSession.Open(folder, tools, decrypted: true, backupRoot: Path.Combine(root, "backups"));
                True(!session.IsEncrypted, "Raw saves must remain raw.");
                Same(original, Snapshot(session.LastBackup));
                Equal(0, tools.CryptoCalls);
                Throws<InvalidOperationException>(session.UpdateIntegrity);
                string backup = session.Save(456789, 0, Path.Combine(root, "backups"));
                Same(original, Snapshot(backup));
                Equal(0, tools.CryptoCalls);
                Equal(456789, ReadValue(folder, 0x588, "GAME.SAV"));
                if (hasPfd) True(original["PARAM.PFD"].SequenceEqual(File.ReadAllBytes(Path.Combine(folder, "PARAM.PFD"))), "Raw PFD changed.");
            }
        });
        Check("RPCS3 metadata selects raw mode; a missing PS3 PFD is not guessed", () =>
        {
            string folder = Fixture(root, "BCES00511");
            File.Delete(Path.Combine(folder, "PARAM.PFD"));
            Throws<FileNotFoundException>(() => SaveSession.Open(folder, new FakeTools(), backupRoot: Path.Combine(root, "backups")));
            File.WriteAllBytes(Path.Combine(folder, "PARAM.SFO"), Sfo("BCES00511", rpc: true));
            using var session = SaveSession.Open(folder, new FakeTools { FailDecrypt = true }, backupRoot: Path.Combine(root, "backups"));
            True(!session.IsEncrypted, "RPCS3 metadata was not recognized.");
        });
        Check("Encryption output must round-trip exactly before originals are written", () =>
        {
            string folder = Fixture(root, "NPUA80908");
            var original = Snapshot(folder);
            using var session = SaveSession.Open(folder, new FakeTools { CorruptEncrypt = true }, backupRoot: Path.Combine(root, "backups"));
            Throws<InvalidDataException>(() => session.Save(999, 99, Path.Combine(root, "backups")));
            Same(original, Snapshot(folder));
            Equal(123, session.Bolts);
        });
        Check("All 4 One edits characters independently and writes both paired counters", () =>
        {
            string folder = Fixture(root, "BCUS98175");
            using var session = SaveSession.Open(folder, new FakeTools(), backupRoot: Path.Combine(root, "backups"));
            byte[] expected = File.ReadAllBytes(Path.Combine(folder, "GAME.SAV"));
            BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x1828), 444);
            BinaryPrimitives.WriteInt32BigEndian(expected.AsSpan(0x182C), 444);
            session.Save(new[] { 123, 444, 123, 123 }, 0, Path.Combine(root, "backups"));
            True(expected.SequenceEqual(File.ReadAllBytes(Path.Combine(folder, "GAME.SAV"))), "Other characters changed.");
            Equal(444, session.CharacterBolts[1]);
            session.Save(new[] { 123, 444, 555, 123 }, 0, Path.Combine(root, "backups"));
            Equal(444, ReadValue(folder, 0x1828, "GAME.SAV"));
            Equal(555, ReadValue(folder, 0x2120, "GAME.SAV"));
        });
        Check("QForce uses its named float record and rejects ambiguous or absent fields", () =>
        {
            string folder = Fixture(root, "BCES01594");
            var profile = SaveProfile.ForRegion("BCES01594");
            byte[] data = File.ReadAllBytes(Path.Combine(folder, "GAME.SAV"));
            byte[] expected = data.ToArray();
            BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(0x12E), 99999);
            SaveData.Write(data, profile, new[] { 99999 }, 0);
            True(data.SequenceEqual(expected), "Wrong QForce field was changed.");
            Throws<ArgumentOutOfRangeException>(() => SaveData.Write(data, profile, new[] { int.MaxValue }, 0));
            BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x12E), float.NaN);
            Throws<InvalidDataException>(() => SaveData.ReadBolts(data, profile));
            "player_bolts\0"u8.CopyTo(data.AsSpan(0x500));
            Throws<InvalidDataException>(() => SaveData.ReadBolts(data, profile));
            Throws<InvalidDataException>(() => SaveData.ReadBolts(new byte[20], profile));
        });
    }

    private static void NativeCryptoChecks(string root)
    {
        foreach (ulong version in new ulong[] { 3, 4 })
            foreach (string region in SaveProfile.SupportedRegions.GroupBy(p => p.Value).Select(g => g.First().Key))
                Check($"PFD v{version} / {region}: real encryption round-trip and original bindings", () =>
                {
                    string folder = Fixture(root, region);
                    var profile = SaveProfile.ForRegion(region);
                    CreatePfd(folder, profile, version);
                    byte[] bindings = PfdBinding.SfoHashes(File.ReadAllBytes(Path.Combine(folder, "PARAM.PFD")));
                    using var tools = new Encryption();
                    tools.Encrypt(folder, region, profile.FileName);
                    using var session = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "backups"));
                    Equal(123, session.Bolts);
                    int[] desired = session.CharacterBolts.Select((v, i) => 123456 + i).ToArray();
                    session.Save(desired, 999, Path.Combine(root, "backups"));
                    True(bindings.SequenceEqual(PfdBinding.SfoHashes(File.ReadAllBytes(Path.Combine(folder, "PARAM.PFD")))), "Owner bindings changed.");
                    using var reopened = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "backups"));
                    True(desired.SequenceEqual(reopened.CharacterBolts), "Currency failed native crypto round-trip.");
                    Equal(profile.RaritaniumOffset.HasValue ? 999 : 0, reopened.Raritanium);
                    var snapshot = Snapshot(folder);
                    Throws<InvalidOperationException>(reopened.PatchMetadata);
                    Same(snapshot, Snapshot(folder));
                    byte[] corrupt = snapshot[profile.FileName].ToArray();
                    corrupt[^1] ^= 1;
                    File.WriteAllBytes(Path.Combine(folder, profile.FileName), corrupt);
                    var tampered = Snapshot(folder);
                    Throws<InvalidOperationException>(() => SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "backups")));
                    Same(tampered, Snapshot(folder));
                });
        Check("Malformed PFD tables and changed SFO bindings are rejected", () =>
        {
            string folder = Fixture(root, "NPUA80908");
            CreatePfd(folder, SaveProfile.ForRegion("NPUA80908"), 4);
            byte[] pfd = File.ReadAllBytes(Path.Combine(folder, "PARAM.PFD"));
            byte[] sfo = File.ReadAllBytes(Path.Combine(folder, "PARAM.SFO"));
            sfo[^1] ^= 1;
            Throws<InvalidDataException>(() => PfdBinding.Preserve(pfd, pfd.ToArray(), sfo));
            BinaryPrimitives.WriteUInt64BigEndian(pfd.AsSpan(96), ulong.MaxValue);
            Throws<InvalidDataException>(() => PfdBinding.SfoHashes(pfd));
            Throws<InvalidDataException>(() => PfdBinding.SfoHashes(new byte[119]));
        });
    }

    // Build a format-valid but synthetic PFD without using native update to sign
    // it. Native pfdtool must independently verify our v3/v4 signature updates.
    private static void CreatePfd(string folder, SaveProfile profile, ulong version)
    {
        const int capacity = 7, entries = 120 + capacity * 8;
        byte[] pfd = new byte[32768];
        BinaryPrimitives.WriteUInt64BigEndian(pfd, 0x50464442);
        BinaryPrimitives.WriteUInt64BigEndian(pfd.AsSpan(8), version);
        BinaryPrimitives.WriteUInt64BigEndian(pfd.AsSpan(96), capacity);
        BinaryPrimitives.WriteUInt64BigEndian(pfd.AsSpan(104), capacity);
        BinaryPrimitives.WriteUInt64BigEndian(pfd.AsSpan(112), 2);
        for (int i = 0; i < capacity; i++) BinaryPrimitives.WriteUInt64BigEndian(pfd.AsSpan(120 + i * 8), ulong.MaxValue);
        byte[] signature = new byte[64];
        for (int i = 0; i < 20; i++) signature[40 + i] = (byte)(i + 31);
        using var aes = Aes.Create();
        aes.Key = Convert.FromHexString("D413B89663E1FE9F75143D3BB4565274");
        aes.EncryptCbc(signature, pfd.AsSpan(16, 16), PaddingMode.None).CopyTo(pfd, 32);
        byte[] secureId = Convert.FromHexString(profile.Key);
        byte[] gameHashKey = new byte[20];
        int idIndex = 0;
        for (int i = 0; i < gameHashKey.Length; i++)
            gameHashKey[i] = i switch { 1 => 11, 2 => 15, 5 => 14, 8 => 10, _ => secureId[idIndex++] };
        for (int i = 0; i < 2; i++)
        {
            string name = i == 0 ? "PARAM.SFO" : profile.FileName;
            int entry = entries + i * 272;
            ulong hash = 0;
            foreach (byte c in Encoding.ASCII.GetBytes(name)) hash = unchecked(hash * 31 + c);
            int bucket = (int)(hash % capacity);
            ulong next = BinaryPrimitives.ReadUInt64BigEndian(pfd.AsSpan(120 + bucket * 8));
            BinaryPrimitives.WriteUInt64BigEndian(pfd.AsSpan(120 + bucket * 8), (ulong)i);
            BinaryPrimitives.WriteUInt64BigEndian(pfd.AsSpan(entry), next);
            Encoding.ASCII.GetBytes(name).CopyTo(pfd, entry + 8);
            byte[] contents = File.ReadAllBytes(Path.Combine(folder, name));
            BinaryPrimitives.WriteUInt64BigEndian(pfd.AsSpan(entry + 264), (ulong)contents.Length);
            byte[] key = i == 0 ? Convert.FromHexString("0C08000E090504040D010F000406020209060D03") : gameHashKey;
            HMACSHA1.HashData(key, contents).CopyTo(pfd, entry + 144);
            if (i == 0)
                for (int j = 0; j < 60; j++) pfd[entry + 164 + j] = (byte)(j + 3);
            else
            {
                byte[] fileKey = Enumerable.Range(0, 64).Select(n => (byte)(n + 1)).ToArray();
                aes.EncryptCbc(fileKey, gameHashKey.AsSpan(0, 16), PaddingMode.None).CopyTo(pfd, entry + 80);
            }
        }
        PfdBinding.Preserve(pfd, pfd, File.ReadAllBytes(Path.Combine(folder, "PARAM.SFO")));
        File.WriteAllBytes(Path.Combine(folder, "PARAM.PFD"), pfd);
    }

    private static void SampleChecks(string root, string samples)
    {
        var samplePaths = Directory.GetFiles(samples, "PARAM.SFO", SearchOption.AllDirectories);
        True(samplePaths.Length > 0, "No sample save folders found.");
        foreach (string sfo in samplePaths)
        {
            string source = Path.GetDirectoryName(sfo);
            var metadata = SfoMetadata.Read(sfo);
            Check("Public sample " + metadata.Region + ": read, save, reopen and byte-preserving round trip", () =>
            {
                var original = Snapshot(source);
                string folder = Path.Combine(root, "Real sample " + metadata.Region + " " + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(folder);
                foreach (string path in Directory.GetFiles(source)) File.Copy(path, Path.Combine(folder, Path.GetFileName(path)));
                using var tools = new Encryption();
                using var session = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "backups"));
                Console.WriteLine($"  {session.Profile.Name}: {session.Bolts} bolts / {session.Raritanium} raritanium, {(session.IsEncrypted ? "encrypted" : "RPCS3")}");
                var profile = session.Profile;
                byte[] expected = File.ReadAllBytes(Path.Combine(session.WorkingFolder, profile.FileName));
                int desired = session.Bolts == 999999 ? 123456 : 999999;
                int rare = profile.RaritaniumOffset.HasValue ? 999 : 0;
                SaveData.Write(expected, profile, new[] { desired }, rare);
                string backup = session.Save(desired, rare, Path.Combine(root, "backups"));
                Same(original, Snapshot(backup));
                if (session.IsEncrypted)
                    True(PfdBinding.SfoHashes(original["PARAM.PFD"]).SequenceEqual(PfdBinding.SfoHashes(File.ReadAllBytes(Path.Combine(folder, "PARAM.PFD")))),
                        "Original console/disc/authentication hashes were overwritten.");
                using var reopened = SaveSession.Open(folder, tools, backupRoot: Path.Combine(root, "backups"));
                Equal(desired, reopened.Bolts); Equal(rare, reopened.Raritanium);
                True(expected.SequenceEqual(File.ReadAllBytes(Path.Combine(reopened.WorkingFolder, profile.FileName))), "Real sample data failed to round-trip.");
                Same(original, Snapshot(source));
            });
        }
    }

    private static void UiChecks(string root)
    {
        using var form = new MainForm();
        string initialTitle = form.Text;
        True(initialTitle.StartsWith("Ratchet & Clank Save Editor v"), "The title should display the app version at startup.");
        var sessionField = typeof(MainForm).GetField("session", BindingFlags.Instance | BindingFlags.NonPublic);
        var show = typeof(MainForm).GetMethod("ShowSession", BindingFlags.Instance | BindingFlags.NonPublic);
        var busy = typeof(MainForm).GetMethod("SetBusy", BindingFlags.Instance | BindingFlags.NonPublic);
        var tabs = Field<TabControl>(form, "TabControl");
        True(!Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Save must be disabled before opening.");
        True(form.ClientSize.Width < 600 && form.ClientSize.Height < 300, "The default window should remain compact.");
        form.StartPosition = FormStartPosition.Manual;
        form.Location = new Point(-20000, -20000);
        form.ShowInTaskbar = false;
        form.Show();
        string artifacts = Path.GetFullPath("artifacts");
        Directory.CreateDirectory(artifacts);
        True(tabs.Visible && tabs.Enabled && !tabs.TabPages[0].Enabled && !tabs.TabPages[1].Enabled,
            "The original save tabs should stay disabled before opening; reference research must remain accessible.");
        True(tabs.TabPages[0].Text == "Game Save Information" && tabs.TabPages[1].Text == "Game Save Editing",
            "Keep the original tab order and names.");
        Capture(form, Path.Combine(artifacts, "ui-compact-empty.png"));
        foreach (string region in new[] { "BLES00301", "NPUA80643", "NPEA00386", "NPEA00387", "NPUA80646",
            "BCUS98127", "BCUS98124", "BCUS98175", "BCES01594", "NPUA80908" })
        {
            (sessionField.GetValue(form) as SaveSession)?.Dispose();
            string folder = Fixture(root, region);
            bool hasArtwork = region == "BLES00301";
            if (hasArtwork)
            {
                using var artwork = new Bitmap(16, 16);
                artwork.Save(Path.Combine(folder, "ICON0.PNG"));
            }
            var session = SaveSession.Open(folder, new FakeTools(), backupRoot: Path.Combine(root, "backups"));
            sessionField.SetValue(form, session);
            show.Invoke(form, null);
            busy.Invoke(form, new object[] { false });
            string loadedTitle = initialTitle + " — " + session.Profile.Name;
            Equal(loadedTitle, form.Text);
            Equal(session.Profile.Name.Replace("&", "&&"), Field<GroupBox>(form, "AccountInfoGroupBox").Text);
            True(Field<Button>(form, "OpenBackupButton").Enabled, "Open Backups should be available immediately after opening.");
            tabs.SelectedIndex = 1;
            True(Field<NumericUpDown>(form, "CasinoChipsNumericUpDown").Visible == session.Profile.RaritaniumOffset.HasValue,
                "Raritanium visibility did not reset on game switch.");
            True(Field<Button>(form, "SaveImageButton").Enabled == hasArtwork, "Artwork should enable export only when present.");
            var characters = Field<ComboBox>(form, "CharacterComboBox");
            bool characterGame = session.Profile.Layout == CurrencyLayout.Characters;
            True(characters.Visible == characterGame, "Character selector visibility did not reset.");
            Equal((decimal)session.Profile.MaximumBolts, Field<NumericUpDown>(form, "MoneyNumericUpDown").Maximum);
            if (characterGame)
            {
                var money = Field<NumericUpDown>(form, "MoneyNumericUpDown");
                money.Value = 111;
                characters.SelectedIndex = 1;
                Equal(123m, money.Value);
                money.Value = 444;
                characters.SelectedIndex = 0;
                Equal(111m, money.Value);
                money.Value = 123;
                characters.SelectedIndex = 1;
                Equal(444m, money.Value);
                money.Value = 123;
                Capture(form, Path.Combine(artifacts, "ui-all4one.png"));
                Equal(loadedTitle, form.Text);
            }
            tabs.SelectedIndex = 1;
            if (hasArtwork)
            {
                using var unlocked = File.Open(Path.Combine(session.WorkingFolder, "ICON0.PNG"), FileMode.Open, FileAccess.ReadWrite, FileShare.None);
            }
            tabs.SelectedIndex = 0;
            True(!Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Save should be disabled without pending edits.");
            var bolts = Field<NumericUpDown>(form, "MoneyNumericUpDown");
            bolts.Value++;
            True(Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Editing currency should enable save.");
            Equal(loadedTitle + " • Unsaved changes", form.Text);
            bolts.Value = session.Bolts;
            True(!Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Reverting an edit should disable save.");
            Equal(loadedTitle, form.Text);
        }
        foreach (var size in new[] { new Size(499, 248) })
        {
            form.ClientSize = size;
            form.PerformLayout();
            for (int i = 0; i < tabs.TabCount; i++)
            {
                tabs.SelectedIndex = i;
                tabs.SelectedTab.CreateControl();
                form.PerformLayout();
                using var image = new Bitmap(form.Width, form.Height);
                form.DrawToBitmap(image, new Rectangle(Point.Empty, image.Size));
                image.Save(Path.Combine(artifacts, $"ui-compact-{i}.png"));
                foreach (var control in Descendants(tabs.SelectedTab).Where(c => c.Visible && c.Parent is not NumericUpDown && c is TextBox or NumericUpDown or Button or ComboBox))
                {
                    True(control.Width >= 50 && control.Height >= 20, $"Clipped control: {control.Name} / {control.Text}");
                    True(control.Parent.ClientRectangle.Contains(control.Bounds), $"Control exceeds its layout: {control.Text}, bounds {control.Bounds}, parent {control.Parent.ClientRectangle}, window {size}");
                }
            }
        }
        tabs.SelectedIndex = 1;
        form.ClientSize = new Size(499, 248);
        Field<NumericUpDown>(form, "MoneyNumericUpDown").Value = int.MaxValue;
        Field<NumericUpDown>(form, "CasinoChipsNumericUpDown").Value = int.MaxValue;
        Capture(form, Path.Combine(artifacts, "ui-compact-edited.png"));
        form.Scale(new SizeF(1.5f, 1.5f));
        Capture(form, Path.Combine(artifacts, "ui-compact-scaled.png"));
        (sessionField.GetValue(form) as SaveSession)?.Dispose();
        sessionField.SetValue(form, null);
    }

    private static void Capture(MainForm form, string path)
    {
        form.PerformLayout();
        using var image = new Bitmap(form.Width, form.Height);
        form.DrawToBitmap(image, new Rectangle(Point.Empty, image.Size));
        image.Save(path);
    }

    private static IEnumerable<Control> Descendants(Control parent)
    {
        foreach (Control child in parent.Controls)
        {
            yield return child;
            foreach (var nested in Descendants(child)) yield return nested;
        }
    }

    private static T Field<T>(MainForm form, string name) => (T)typeof(MainForm).GetField(name, BindingFlags.Instance | BindingFlags.NonPublic).GetValue(form);

    private static string Fixture(string root, string region)
    {
        string folder = Path.Combine(root, "Save with spaces " + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        File.WriteAllBytes(Path.Combine(folder, "PARAM.SFO"), Sfo(region));
        File.WriteAllText(Path.Combine(folder, "PARAM.PFD"), "Test integrity");
        var profile = SaveProfile.ForRegion(region);
        byte[] data = Enumerable.Repeat((byte)0x55, 0x2300).ToArray();
        "IGSD"u8.CopyTo(data);
        if (profile.HasChecksumBlocks)
        {
            BinaryPrimitives.WriteUInt32BigEndian(data, 0x808);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(8), 0x800);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(12), 0x1234);
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x810), (uint)(data.Length - 0x818));
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x814), 0x5678);
        }
        BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(profile.BoltsOffset), 123);
        if (profile.Layout == CurrencyLayout.Characters)
            foreach (int characterOffset in new[] { 0x638, 0x1828, 0x2120, 0xF30 })
            {
                BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(characterOffset), 123);
                BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(characterOffset + 4), 456);
            }
        if (profile.Layout == CurrencyLayout.NamedFloat)
        {
            "player_bolts\0"u8.CopyTo(data.AsSpan(0x120));
            BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x12E), 123);
        }
        if (profile.RaritaniumOffset is int offset) BinaryPrimitives.WriteInt32BigEndian(data.AsSpan(offset), 45);
        File.WriteAllBytes(Path.Combine(folder, profile.FileName), data);
        File.WriteAllText(Path.Combine(folder, "EXTRA.DAT"), "Preserve this too");
        return folder;
    }

    private static byte[] Sfo(string region, string titleId = null, bool rpc = false)
    {
        byte[] parameters = new byte[1024];
        BinaryPrimitives.WriteUInt32LittleEndian(parameters.AsSpan(24), 42);
        Convert.FromHexString("000000010085000F0123456789ABCDEF").CopyTo(parameters, 28);
        var fields = new Dictionary<string, byte[]>
        {
            ["SUB_TITLE"] = Encoding.UTF8.GetBytes("Planète Veldin\0"),
            ["ACCOUNT_ID"] = Encoding.UTF8.GetBytes("0001020304050607\0"),
            ["SAVEDATA_DIRECTORY"] = Encoding.UTF8.GetBytes(region + "-SAVE1\0"),
            ["PARAMS"] = parameters
        };
        if (titleId != null) fields["TITLE_ID"] = Encoding.UTF8.GetBytes(titleId + "\0");
        if (rpc) fields["RPCS3_BLIST"] = Encoding.UTF8.GetBytes("ICON0.PNG/GAME.SAV\0");
        using var keys = new MemoryStream();
        using var values = new MemoryStream();
        using var index = new MemoryStream();
        using var writer = new BinaryWriter(index, Encoding.UTF8, true);
        foreach (var field in fields)
        {
            byte[] value = field.Value;
            writer.Write((ushort)keys.Position);
            writer.Write((ushort)0x0204);
            writer.Write(value.Length);
            writer.Write(value.Length);
            writer.Write((uint)values.Position);
            keys.Write(Encoding.ASCII.GetBytes(field.Key + "\0"));
            values.Write(value);
        }
        using var result = new MemoryStream();
        using var header = new BinaryWriter(result, Encoding.UTF8, true);
        header.Write(0x46535000u);
        header.Write(0x00000101u);
        header.Write((uint)(20 + index.Length + 12));
        header.Write((uint)(20 + index.Length + 12 + keys.Length));
        header.Write((uint)fields.Count);
        result.Write(index.ToArray());
        result.Write(new byte[12]);
        result.Write(keys.ToArray());
        result.Write(values.ToArray());
        return result.ToArray();
    }

    private static int ReadValue(string folder, int offset, string file)
    {
        using var stream = File.OpenRead(Path.Combine(folder, file));
        stream.Position = offset;
        return stream.ReadInt32();
    }

    private static Dictionary<string, byte[]> Snapshot(string folder) => Directory.GetFiles(folder).ToDictionary(Path.GetFileName, File.ReadAllBytes);
    private static void Same(Dictionary<string, byte[]> a, Dictionary<string, byte[]> b) => True(
        a.Count == b.Count && a.All(p => b.TryGetValue(p.Key, out var value) && p.Value.SequenceEqual(value)), "Files changed unexpectedly.");
    private static void Check(string name, Action action) { action(); passed++; Console.WriteLine("PASS " + name); }
    private static void Equal<T>(T expected, T actual) => True(EqualityComparer<T>.Default.Equals(expected, actual), $"Expected {expected}, got {actual}.");
    private static void True(bool condition, string message) { if (!condition) throw new Exception(message); }
    private static void Throws<T>(Action action) where T : Exception
    {
        try { action(); } catch (T) { return; }
        throw new Exception($"Expected {typeof(T).Name}.");
    }

    private sealed class FakeTools : ISaveTools
    {
        public string DecryptedFile;
        public string EncryptedFile;
        public bool FailEncrypt;
        public bool FailDecrypt;
        public bool CorruptEncrypt;
        public int CryptoCalls;
        public Action BeforeDecrypt;
        public void Decrypt(string folder, string region, string file)
        {
            CryptoCalls++;
            BeforeDecrypt?.Invoke();
            if (FailDecrypt) throw new InvalidOperationException("Decryption must not be called for raw saves");
            DecryptedFile = file;
            File.WriteAllText(Path.Combine(folder, "PARAM.PFD"), "Decrypted integrity");
        }
        public void Encrypt(string folder, string region, string file)
        {
            CryptoCalls++;
            EncryptedFile = file;
            File.WriteAllText(Path.Combine(folder, "PARAM.PFD"), "Encrypted integrity");
            if (FailEncrypt) throw new InvalidOperationException("Simulated encryption failure");
            if (CorruptEncrypt)
            {
                byte[] data = File.ReadAllBytes(Path.Combine(folder, file));
                data[^1] ^= 1;
                File.WriteAllBytes(Path.Combine(folder, file), data);
            }
        }
        public void Update(string folder, string region) => File.WriteAllText(Path.Combine(folder, "PARAM.PFD"), "Updated integrity");
        public void Patch(string folder, bool encrypted) => File.WriteAllBytes(Path.Combine(folder, "PARAM.SFO"), Sfo("NPUA80908"));
    }

    private sealed class PartialReadStream : MemoryStream
    {
        public PartialReadStream(byte[] data) : base(data) { }
        public override int Read(Span<byte> buffer) => base.Read(buffer.Slice(0, Math.Min(1, buffer.Length)));
    }
}
