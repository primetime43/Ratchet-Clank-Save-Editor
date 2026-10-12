using System;
using System.Buffers.Binary;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static byte[] RewardFixture(uint replay = 3, float multiplier = 1)
    {
        byte[] data = EditableFixture();
        BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x906EC, 4), replay);
        BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(0x428, 4), multiplier);
        return data;
    }

    private static void RewardRequestEditingChecks()
    {
        Check("Replay-gated multiplier edits change exactly one bounded float", () =>
        {
            foreach (uint replay in new[] { 1u, 3u, uint.MaxValue })
            {
                byte[] data = RewardFixture(replay), before = data.ToArray();
                var field = TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "bolt_multiplier");
                Equal(1m, field.Minimum); Equal(20m, field.Maximum);
                foreach (decimal value in new[] { 1m, 1.5m, 10m, 20m })
                {
                    byte[] expected = data.ToArray();
                    BinaryPrimitives.WriteSingleBigEndian(expected.AsSpan(0x428, 4), (float)value);
                    True(expected.SequenceEqual(TodSaveEditing.Apply(data, "BCUS98127", Edits((field.Key, value)))), "No replay flag, balances, XP or runtime cache fields may change.");
                }
                True(data.SequenceEqual(before), "Input must remain detached.");
            }
        });
        Check("Multiplier edits cannot enable replay or normalize malformed inputs", () =>
        {
            foreach (byte[] data in new[] { RewardFixture(0), RewardFixture(multiplier: 0), RewardFixture(multiplier: 21),
                RewardFixture(multiplier: float.NaN), RewardFixture(multiplier: float.PositiveInfinity) })
            {
                byte[] before = data.ToArray();
                True(!TodSaveEditing.Fields(data, "BCUS98127").Any(field => field.Key == "bolt_multiplier"), "Unqualified state must remain read-only.");
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("bolt_multiplier", 1))));
                True(data.SequenceEqual(before), "Rejected input must not be repaired or mutated.");
            }
            foreach (decimal invalid in new[] { -1m, 0m, 0.999m, 20.0001m })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(RewardFixture(), "BCUS98127", Edits(("bolt_multiplier", invalid))));
            byte[] fractional = RewardFixture(multiplier: 1.3333334f);
            decimal original = TodSaveEditing.Fields(fractional, "BCUS98127").Single(field => field.Key == "bolt_multiplier").Current;
            True(fractional.SequenceEqual(TodSaveEditing.Apply(fractional, "BCUS98127", Edits(("bolt_multiplier", original)))), "Same-value requests must preserve exact native float bits.");
        });
        Check("Commentary request requires200 points and changes only its canonical physical byte", () =>
        {
            byte[] data = BonusFixture(199);
            Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("bonus_commentary", 1))));
            BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8708, 4), 200);
            byte[] before = data.ToArray(), expected = data.ToArray(); expected[0x86FD] = 1;
            var field = TodSaveEditing.Fields(data, "BCUS98127").Single(field => field.Key == "bonus_commentary");
            Equal(2, field.Options.Count); Equal(0x86FD, field.Offset);
            True(field.Options[1].Label.Contains("supported language"), "Language applicability must be visible in the selector.");
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", Edits(("bonus_commentary", 1)));
            True(expected.SequenceEqual(result), "No language, score, earned bits or adjacent bonuses may change.");
            True(before.SequenceEqual(TodSaveEditing.Apply(result, "BCUS98127", Edits(("bonus_commentary", 0)))), "Off must clear only the saved request.");
            foreach (byte unknown in new byte[] { 2, 255 })
            {
                data[0x86FD] = unknown;
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(data, "BCUS98127", Edits(("bonus_commentary", 0))));
            }
            foreach (decimal invalid in new[] { -1m, 0.5m, 2m })
                Throws<InvalidDataException>(() => TodSaveEditing.Apply(before, "BCUS98127", Edits(("bonus_commentary", invalid))));
            string details = TodSaveInspection.Read(before, "BCUS98127").Table("Bonuses & cheats").Rows[5].Details;
            True(details.Contains("runtime language ID1") && details.Contains("not stored here"), "Inspector must not infer the active language or playback from a saved request.");
        });
    }

    // Full/manual CI only; leave desktop controls out of the lightweight path.
    private static void RewardRequestUiChecks()
    {
        Check("Reward multiplier textbox and commentary selector retain hidden validation", () =>
        {
            byte[] data = RewardFixture(); BinaryPrimitives.WriteUInt32BigEndian(data.AsSpan(0x8708, 4), 200);
            using var form = new Form { ClientSize = new Size(1000, 820), Font = new Font("Segoe UI", 11) };
            using var editor = new TodSaveEditingControl(); form.Controls.Add(editor); editor.LoadSnapshot(data, "BCUS98127"); form.Show();
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            category.SelectedItem = "Rewards";
            var multiplier = editor.Controls.Find("MappedEdit_bolt_multiplier", true).Cast<NumericTextBox>().Single();
            multiplier.Text = "20.1";
            True(editor.HasInvalidInputs, "Multiplier must obey1..20 bounds.");
            category.SelectedItem = "Bonus effects";
            editor.Controls.Find("MappedEdit_bonus_commentary", true).Cast<ComboBox>().Single().SelectedIndex = 1;
            Throws<InvalidOperationException>(() => { var edits = editor.PendingEdits; });
            True(!editor.ValidateInputs(), "Invalid hidden multiplier must block saving.");
            Equal("Rewards", category.SelectedItem?.ToString());
            multiplier = editor.Controls.Find("MappedEdit_bolt_multiplier", true).Cast<NumericTextBox>().Single();
            Equal("20.1", multiplier.Text); multiplier.Text = "10.5";
            True(editor.ValidateInputs(), "Valid fractional multiplier must be accepted.");
            byte[] result = TodSaveEditing.Apply(data, "BCUS98127", editor.PendingEdits);
            Equal(10.5f, BinaryPrimitives.ReadSingleBigEndian(result.AsSpan(0x428, 4))); Equal((byte)1, result[0x86FD]);
        });
    }
}
