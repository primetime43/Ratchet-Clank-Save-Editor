using System;
using System.Collections.Generic;
using System.IO;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed record SaveProfile(string Name, string FileName, int BoltsOffset,
        int? RaritaniumOffset, string Key)
    {
        private static readonly Dictionary<string, SaveProfile> Profiles = CreateProfiles();

        public static SaveProfile ForRegion(string region)
        {
            if (!Profiles.TryGetValue(region, out var profile))
                throw new InvalidDataException($"The game region '{region}' is not supported. No save files were changed.");
            return profile;
        }

        private static Dictionary<string, SaveProfile> CreateProfiles()
        {
            var profiles = new Dictionary<string, SaveProfile>(StringComparer.OrdinalIgnoreCase);
            void Add(SaveProfile profile, params string[] regions)
            {
                foreach (string region in regions) profiles.Add(region, profile);
            }
            const string key = "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF";
            Add(new("Ratchet & Clank: Nexus", "GAME.SAV", 0x105C, 0x1060, key),
                "NPUA80908", "NPEA00457", "BCUS99245", "BCES01908", "BCES01949", "BCJS30092", "NPJA00101");
            Add(new("Ratchet & Clank: Quest for Booty", "GAME.SAV", 0x274, null, key),
                "BCUS98187", "BLES00301", "NPUA80145", "NPEA00088");
            Add(new("Ratchet & Clank: Tools of Destruction", "GAME.SAV", 0x41C, 0x420, key),
                "BCUS98127", "BCES00052", "BCKS10016", "BCJS30014", "BCJS70012", "BCKS10054",
                "BCAS20045", "BCJS70004", "NPUA98153", "NPEA90017", "NPJA90035", "NPHA20002");
            Add(new("Ratchet & Clank", "USR-DATA", 0x24, null, "01020304050607FACB0A0B0C0D0E0F10"), "NPUA80643");
            return profiles;
        }

        public void ValidateLength(long length)
        {
            long required = Math.Max(BoltsOffset, RaritaniumOffset ?? BoltsOffset) + 4L;
            if (length < required)
                throw new InvalidDataException($"{FileName} is truncated: expected at least {required:N0} bytes.");
        }
    }
}
