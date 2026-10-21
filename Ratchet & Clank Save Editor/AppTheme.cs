using System;
using System.Drawing;
using System.IO;
using System.Security;
using System.Windows.Forms;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    internal static class AppTheme
    {
        private static readonly string SettingsPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "RatchetClankSaveEditor", "theme.txt");

        public static SystemColorMode Preference { get; private set; } = SystemColorMode.System;
        public static Color InvalidInputBackground => SystemColors.Window.GetBrightness() < 0.5f
            ? Color.FromArgb(88, 38, 42) : Color.MistyRose;

        public static void Initialize()
        {
            try
            {
                string saved = File.ReadAllText(SettingsPath).Trim();
                if (Enum.TryParse(saved, out SystemColorMode mode) && Enum.IsDefined(mode)) Preference = mode;
            }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException or SecurityException) { }

            // Native WinForms theming must be selected before any controls are created.
#pragma warning disable WFO5001
            Application.SetColorMode(Preference);
#pragma warning restore WFO5001
        }

        public static void SavePreference(SystemColorMode mode)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(SettingsPath));
            File.WriteAllText(SettingsPath, mode.ToString());
            Preference = mode;
        }
    }
}
