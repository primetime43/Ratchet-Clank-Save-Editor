using System;
using System.Collections.Generic;
using System.IO;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed record SaveProfile(string Name, string FileName, int BoltsOffset,
        int? RaritaniumOffset, string Key, bool HasChecksumBlocks = false,
        CurrencyLayout Layout = CurrencyLayout.Integer)
    {
        private static readonly Dictionary<string, SaveProfile> Profiles = CreateProfiles();
        public static IReadOnlyDictionary<string, SaveProfile> SupportedRegions => Profiles;

        public static bool SupportsRegion(string region) => Profiles.ContainsKey(region);
        public int MaximumBolts => Layout == CurrencyLayout.NamedFloat ? 16_777_216 : int.MaxValue;

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
                "BCUS98187", "BLES00301", "BCES00301", "NPUA80145", "NPEA00088");
            Add(new("Ratchet & Clank: Tools of Destruction", "GAME.SAV", 0x41C, 0x420, key),
                "BCUS98127", "BCES00052", "BCKS10016", "BCJS30014", "BCJS70012", "BCKS10054",
                "BCAS20045", "BCJS70004", "NPUA98153", "NPEA90017", "NPJA90035", "NPHA20002", "NPEA00452", "NPUA80965");
            Add(new("Ratchet & Clank", "USR-DATA", 0x24, null, "01020304050607FACB0A0B0C0D0E0F10", true),
                "NPUA80643", "NPEA00385", "NPJA40001");
            Add(new("Ratchet & Clank 2: Going Commando", "USR-DATA", 0x24, 0x28, "C0A3B3641C2AD1EF23153A48A3E12FE8", true),
                "NPUA80644", "NPEA00386", "NPJA40002");
            Add(new("Ratchet & Clank 3: Up Your Arsenal", "USR-DATA", 0x24, null, "C0A3B3641C2AD1EF23153A48A3E12FE7", true),
                "NPUA80645", "NPEA00387", "NPJA40003");
            Add(new("Ratchet: Deadlocked / Gladiator", "USR-DATA", 0x24, null, "0403020105060700000A0B0C0D0E0F10", true),
                "NPUA80646", "NPEA00388", "NPEA00423", "NPJA40004");
            Add(new("Ratchet & Clank: A Crack in Time", "GAME.SAV", 0x588, null, key),
                "BCUS98124", "BCES00142", "BCES00511", "BCES00748", "BCES00726", "BCJS30038", "BCKS10087", "BCAS20098", "NPEA00453", "NPUA80966");
            Add(new("Ratchet & Clank: All 4 One", "GAME.SAV", 0x638, null, key, Layout: CurrencyLayout.Characters),
                "BCUS98175", "BCES01142", "BCES01141", "BCAS20200", "BCJS30081", "NPEA00356", "NPUA80695", "NPEA90105", "NPUA70181");
            Add(new("Ratchet & Clank: Full Frontal Assault / QForce", "GAME.SAV", 0, null, key, Layout: CurrencyLayout.NamedFloat),
                "BCUS98380", "NPUA80642", "BCES01594", "NPEA00378", "XCES00001");
            return profiles;
        }

        public void ValidateLength(long length)
        {
            long required = Math.Max(BoltsOffset, RaritaniumOffset ?? BoltsOffset) + 4L;
            if (length < required)
                throw new InvalidDataException($"{FileName} is truncated: expected at least {required:N0} bytes.");
        }
    }

    public enum CurrencyLayout { Integer, Characters, NamedFloat }
}
