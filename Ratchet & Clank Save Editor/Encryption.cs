using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Threading;
using System.Threading.Tasks;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public interface ISaveTools
    {
        void Decrypt(string folder, string region, string file);
        void Encrypt(string folder, string region, string file);
        void Update(string folder, string region);
        void Patch(string folder);
    }

    public sealed class Encryption : ISaveTools, IDisposable
    {
        private TemporaryDirectory tools;

        public void Decrypt(string folder, string region, string file) => Transform(folder, region, file, "-d");
        public void Encrypt(string folder, string region, string file) => Transform(folder, region, file, "-e");

        private void Transform(string folder, string region, string file, string command)
        {
            string path = Path.Combine(folder, file);
            byte[] before = SHA256.HashData(File.ReadAllBytes(path));
            Run("pfdtool.exe", "-g", region, command, folder, file);
            if (before.SequenceEqual(SHA256.HashData(File.ReadAllBytes(path))))
                throw new InvalidOperationException($"pfdtool did not transform {file}. Check that PARAM.PFD is valid and the save is encrypted with the correct game key.");
            Verify(folder, region, false, file);
        }
        public void Update(string folder, string region)
        {
            Run("pfdtool.exe", "-g", region, "-p", "-u", folder);
            Verify(folder, region, true, null);
        }

        private void Verify(string folder, string region, bool partial, string file)
        {
            string report = partial
                ? Run("pfdtool.exe", "-g", region, "-p", "-c", folder)
                : Run("pfdtool.exe", "-g", region, "-c", folder);
            // The legacy tool also returns zero when database import/update fails.
            // Require an actual verification report, with no failed integrity hashes.
            if (!report.Contains("[*] Statuses:", StringComparison.Ordinal)
                || report.Contains("FAIL", StringComparison.Ordinal)
                || (file != null && !report.Contains("(" + file + ")", StringComparison.OrdinalIgnoreCase)))
                throw new InvalidOperationException("The save integrity database could not be verified.\n" + report);
        }

        public void Patch(string folder)
        {
            // 'build' requires a separate template. Use the documented patch command.
            string input = Path.Combine(folder, "PARAM.SFO");
            string output = Path.Combine(folder, "patched.sfo");
            Run("sfopatcher.exe", "patch", input, output, "--remove-copy-protection");
            SfoMetadata.Read(output);
            File.Move(output, input, true);
        }

        private string Run(string executable, params string[] arguments)
        {
            EnsureTools();
            var start = new ProcessStartInfo(Path.Combine(tools.Path, executable))
            {
                WorkingDirectory = tools.Path,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };
            foreach (string argument in arguments) start.ArgumentList.Add(argument);
            using var process = new Process { StartInfo = start };
            process.Start();
            Task<string> output = process.StandardOutput.ReadToEndAsync();
            Task<string> error = process.StandardError.ReadToEndAsync();
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(60));
            try { process.WaitForExitAsync(timeout.Token).GetAwaiter().GetResult(); }
            catch (OperationCanceledException)
            {
                process.Kill(true);
                process.WaitForExit();
                throw new TimeoutException($"{executable} did not finish within 60 seconds.");
            }
            string details = (output.GetAwaiter().GetResult() + "\n" + error.GetAwaiter().GetResult()).Trim();
            // pfdtool 0.2.3 reports some failures with exit code zero.
            if (process.ExitCode != 0 || details.Contains("Error:", StringComparison.OrdinalIgnoreCase)
                || details.Contains("[E]", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException($"{executable} failed (exit code {process.ExitCode}).\n{details}");
            return details;
        }

        private void EnsureTools()
        {
            if (tools != null) return;
            var extracted = new TemporaryDirectory();
            try
            {
                File.WriteAllBytes(Path.Combine(extracted.Path, "pfdtool.exe"), Properties.Resources.pfdtool);
                File.WriteAllBytes(Path.Combine(extracted.Path, "sfopatcher.exe"), Properties.Resources.sfopatcher);
                File.WriteAllBytes(Path.Combine(extracted.Path, "games.conf"), Properties.Resources.games);
                File.WriteAllBytes(Path.Combine(extracted.Path, "global.conf"), Properties.Resources.global);
                tools = extracted;
            }
            catch { extracted.Dispose(); throw; }
        }

        public void Dispose() => tools?.Dispose();
    }

    internal sealed class TemporaryDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(),
            "RatchetClankSaveEditor-" + Guid.NewGuid().ToString("N"));

        public TemporaryDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            // This instance owns only its uniquely generated temporary directory.
            try { if (Directory.Exists(Path)) Directory.Delete(Path, true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }
}
