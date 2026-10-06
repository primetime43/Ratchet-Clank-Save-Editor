using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed class SaveSession : IDisposable
    {
        private readonly TemporaryDirectory working = new();
        private readonly ISaveTools tools;
        private Dictionary<string, byte[]> originalHashes;
        public string Folder { get; }
        public string WorkingFolder => working.Path;
        public SfoMetadata Metadata { get; private set; }
        public SaveProfile Profile { get; private set; }
        public int Bolts { get; private set; }
        public int Raritanium { get; private set; }
        public bool MetadataChanged { get; private set; }
        public string LastBackup { get; private set; }
        public static string BackupRoot => Path.Combine(Environment.GetFolderPath(
            Environment.SpecialFolder.LocalApplicationData), "RatchetClankSaveEditor", "Backups");

        private SaveSession(string folder, ISaveTools tools)
        {
            Folder = Path.GetFullPath(folder);
            this.tools = tools;
        }

        public static SaveSession Open(string folder, ISaveTools tools)
        {
            var session = new SaveSession(folder, tools);
            try
            {
                session.Metadata = SfoMetadata.Read(Path.Combine(session.Folder, "PARAM.SFO"));
                session.Profile = SaveProfile.ForRegion(session.Metadata.Region);
                foreach (string name in new[] { "PARAM.PFD", session.Profile.FileName })
                    if (!File.Exists(Path.Combine(session.Folder, name)))
                        throw new FileNotFoundException($"The save folder is missing {name}.");
                session.originalHashes = HashFiles(session.Folder);
                CopyFiles(session.Folder, session.WorkingFolder);
                session.EnsureUnchanged();
                // Check the copy too: a source file must not change midway through copying.
                if (!SameHashes(session.originalHashes, HashFiles(session.WorkingFolder)))
                    throw new IOException("The save folder changed while it was being opened. Please open it again.");
                var copiedMetadata = SfoMetadata.Read(Path.Combine(session.WorkingFolder, "PARAM.SFO"));
                if (!string.Equals(copiedMetadata.Region, session.Metadata.Region, StringComparison.OrdinalIgnoreCase))
                    throw new IOException("The game region changed while opening the save. Please open it again.");
                session.Metadata = copiedMetadata;
                tools.Decrypt(session.WorkingFolder, session.Metadata.Region, session.Profile.FileName);
                session.ReadValues();
                return session;
            }
            catch { session.Dispose(); throw; }
        }

        private void ReadValues()
        {
            using var stream = File.OpenRead(Path.Combine(WorkingFolder, Profile.FileName));
            Profile.ValidateLength(stream.Length);
            stream.Position = Profile.BoltsOffset;
            Bolts = stream.ReadInt32();
            Raritanium = 0;
            if (Profile.RaritaniumOffset is int offset)
            {
                stream.Position = offset;
                Raritanium = stream.ReadInt32();
            }
            if (Bolts < 0 || Raritanium < 0)
                throw new InvalidDataException("The save contains invalid currency values. Check that decryption succeeded and the game is supported.");
        }

        public string Save(int bolts, int raritanium, string backupRoot = null)
        {
            if (bolts < 0 || raritanium < 0) throw new ArgumentOutOfRangeException(nameof(bolts));
            EnsureUnchanged();
            using var candidate = new TemporaryDirectory();
            CopyFiles(WorkingFolder, candidate.Path);
            using (var stream = File.Open(Path.Combine(candidate.Path, Profile.FileName), FileMode.Open, FileAccess.ReadWrite))
            {
                Profile.ValidateLength(stream.Length);
                stream.Position = Profile.BoltsOffset;
                stream.WriteInt32(bolts);
                if (Profile.RaritaniumOffset is int offset)
                {
                    stream.Position = offset;
                    stream.WriteInt32(raritanium);
                }
            }
            // Encrypt and update integrity in isolation. Failed tools never touch the source.
            tools.Encrypt(candidate.Path, Metadata.Region, Profile.FileName);
            foreach (string name in CommitFiles)
                if (!File.Exists(Path.Combine(candidate.Path, name)))
                    throw new IOException($"Encryption did not produce {name}.");

            // Prepare the next baseline before writing to the source. Once the commit
            // succeeds, no further disk operation can misreport it as a failed save.
            var nextHashes = new Dictionary<string, byte[]>(originalHashes, StringComparer.OrdinalIgnoreCase);
            foreach (string name in CommitFiles)
                nextHashes[name] = SHA256.HashData(File.ReadAllBytes(Path.Combine(candidate.Path, name)));

            string backup = BackUp(backupRoot);
            EnsureUnchanged();
            var replaced = new List<string>();
            try
            {
                foreach (string name in CommitFiles)
                {
                    // File.Replace is atomic for each file; backups also allow recovery
                    // if another file fails, or the machine shuts down between replacements.
                    File.Replace(Path.Combine(candidate.Path, name), Path.Combine(Folder, name), null);
                    replaced.Add(name);
                }
            }
            catch (Exception commitError)
            {
                var errors = new List<Exception> { commitError };
                foreach (string name in replaced)
                {
                    try { File.Copy(Path.Combine(backup, name), Path.Combine(Folder, name), true); }
                    catch (Exception rollbackError) { errors.Add(rollbackError); }
                }
                throw new IOException($"Saving failed. Original files are backed up in:\n{backup}", new AggregateException(errors));
            }
            Bolts = bolts;
            Raritanium = Profile.RaritaniumOffset.HasValue ? raritanium : 0;
            // Future saves overwrite both editable values in a fresh candidate.
            // Keep the decrypted working copy intact; only source files are encrypted.
            MetadataChanged = false;
            originalHashes = nextHashes;
            return backup;
        }

        private string[] CommitFiles => new[] { Profile.FileName, "PARAM.SFO", "PARAM.PFD" };

        public void PatchMetadata()
        {
            using var candidate = new TemporaryDirectory();
            CopyFiles(WorkingFolder, candidate.Path);
            tools.Patch(candidate.Path);
            var metadata = SfoMetadata.Read(Path.Combine(candidate.Path, "PARAM.SFO"));
            if (!string.Equals(metadata.Region, Metadata.Region, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("The metadata patch unexpectedly changed the game region.");
            File.Copy(Path.Combine(candidate.Path, "PARAM.SFO"), Path.Combine(WorkingFolder, "PARAM.SFO"), true);
            Metadata = metadata;
            MetadataChanged = true;
        }

        public void UpdateIntegrity()
        {
            using var candidate = new TemporaryDirectory();
            CopyFiles(WorkingFolder, candidate.Path);
            tools.Update(candidate.Path, Metadata.Region);
            File.Copy(Path.Combine(candidate.Path, "PARAM.PFD"), Path.Combine(WorkingFolder, "PARAM.PFD"), true);
            MetadataChanged = true;
        }

        public string BackUp(string backupRoot = null)
        {
            EnsureUnchanged();
            string destination = Path.Combine(backupRoot ?? BackupRoot, Path.GetFileName(Path.TrimEndingDirectorySeparator(Folder)),
                DateTime.Now.ToString("yyyyMMdd-HHmmss-fff") + "-" + Guid.NewGuid().ToString("N").Substring(0, 8));
            Directory.CreateDirectory(destination);
            CopyFiles(Folder, destination);
            if (!SameHashes(originalHashes, HashFiles(destination)))
                throw new IOException("The save folder changed while backing up. Please open it again.");
            LastBackup = destination;
            return destination;
        }

        private void EnsureUnchanged()
        {
            if (!SameHashes(originalHashes, HashFiles(Folder)))
                throw new IOException("The original save folder changed outside the editor. Open it again before saving.");
        }

        private static bool SameHashes(Dictionary<string, byte[]> a, Dictionary<string, byte[]> b) =>
            a.Count == b.Count && a.All(pair => b.TryGetValue(pair.Key, out var hash) && pair.Value.SequenceEqual(hash));

        private static Dictionary<string, byte[]> HashFiles(string folder) => Directory.GetFiles(folder)
            .ToDictionary(Path.GetFileName, path => SHA256.HashData(File.ReadAllBytes(path)), StringComparer.OrdinalIgnoreCase);

        private static void CopyFiles(string source, string destination)
        {
            foreach (string path in Directory.GetFiles(source))
                File.Copy(path, Path.Combine(destination, Path.GetFileName(path)), true);
        }

        public void Dispose() => working.Dispose();
    }
}
