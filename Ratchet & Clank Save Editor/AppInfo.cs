using System.Reflection;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    internal static class AppInfo
    {
        private static readonly Assembly Assembly = typeof(AppInfo).Assembly;
        public static readonly string ProductName = Assembly.GetCustomAttribute<AssemblyProductAttribute>().Product;
        // Keep prerelease identifiers, but omit the SDK's source commit metadata from display text.
        public static readonly string Version = Assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>()
            .InformationalVersion.Split('+')[0];
        public static readonly string WindowTitle = $"{ProductName} v{Version}";
    }
}
