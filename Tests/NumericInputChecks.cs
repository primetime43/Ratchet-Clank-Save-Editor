using System;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static void NumericInputChecks(string root)
    {
        Check("Currency text boxes accept only bounded whole numbers, including pasted text", () =>
        {
            using var input = new NumericTextBox { FieldName = "Bolts" };
            foreach (string text in new[] { "0", "123", "000123", int.MaxValue.ToString(CultureInfo.InvariantCulture) })
            {
                input.Text = text;
                True(input.TryGetValue(out _), "Valid whole number rejected.");
            }
            foreach (string text in new[] { "", " ", "12 ", " 12", "-1", "+1", "1.5", "1,000", "1e3", "NaN", "Infinity", "12abc", "2147483648", new string('9', 60), "١٢" })
            {
                input.Text = text;
                True(!input.IsValid, "Invalid integer accepted: " + text);
                True(input.ValidationMessage.Contains("Bolts"), "Error must identify the field.");
                if (SystemColors.Window.GetBrightness() >= 0.5f) Equal(Color.MistyRose, input.BackColor);
                else
                {
                    True(input.BackColor != SystemColors.Window, "Invalid dark-mode input must remain highlighted.");
                    True(input.ForeColor.GetBrightness() - input.BackColor.GetBrightness() > 0.5f,
                        "Invalid dark-mode input must retain readable text.");
                }
                Throws<InvalidOperationException>(() => { _ = input.Value; });
            }
            input.Text = "123";
            Equal(123m, input.Value);
            Equal(string.Empty, input.ValidationMessage);
            Equal(SystemColors.Window, input.BackColor);
            input.Maximum = 100;
            True(!input.IsValid, "Changing limits must revalidate existing text.");
        });
        Check("Decimal text accepts fractional ammo and percentages without culture-dependent parsing", () =>
        {
            var previous = CultureInfo.CurrentCulture;
            try
            {
                CultureInfo.CurrentCulture = CultureInfo.GetCultureInfo("fr-FR");
                using var input = new NumericTextBox { AllowDecimal = true, Maximum = 100 };
                foreach (string text in new[] { "0", "12.5", ".5", "50.", "100", "0.000001" })
                {
                    input.Text = text;
                    True(input.IsValid, "Valid decimal rejected: " + text);
                }
                foreach (string text in new[] { ".", "1.2.3", "12,5", "-0.1", "100.0001", "1e-3", "Infinity" })
                {
                    input.Text = text;
                    True(!input.IsValid, "Invalid decimal accepted: " + text);
                }
                input.Value = 12.5m;
                Equal("12.5", input.Text);
            }
            finally { CultureInfo.CurrentCulture = previous; }
        });
        Check("Keyboard filtering rejects unsupported characters but keeps editing shortcuts", () =>
        {
            using var input = new NumericTextBox();
            var method = typeof(NumericTextBox).GetMethod("OnKeyPress", BindingFlags.NonPublic | BindingFlags.Instance);
            foreach (char character in new[] { 'x', '-', '+', '.', ',', 'e' })
            {
                var args = new KeyPressEventArgs(character);
                method.Invoke(input, new object[] { args });
                True(args.Handled, "Integer input should reject " + character);
            }
            foreach (char character in new[] { '0', '9', '\b', '\u0001', '\u0016' })
            {
                var args = new KeyPressEventArgs(character);
                method.Invoke(input, new object[] { args });
                True(!args.Handled, "Numeric input must retain digits and shortcuts.");
            }
            input.AllowDecimal = true;
            input.Text = "1.5";
            input.SelectionStart = input.TextLength;
            var secondPoint = new KeyPressEventArgs('.');
            method.Invoke(input, new object[] { secondPoint });
            True(secondPoint.Handled, "A second decimal point must be rejected.");
        });
        Check("Invalid currency disables Save All and cannot invoke a save transaction", () =>
        {
            using var form = new MainForm();
            string folder = Fixture(root, "BCUS98127");
            File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), EditableFixture());
            var tools = new FakeTools();
            using var session = SaveSession.Open(folder, tools, decrypted: true, backupRoot: Path.Combine(root, "numeric-backups"));
            typeof(MainForm).GetField("session", BindingFlags.NonPublic | BindingFlags.Instance).SetValue(form, session);
            typeof(MainForm).GetMethod("ShowSession", BindingFlags.NonPublic | BindingFlags.Instance).Invoke(form, null);
            var original = Snapshot(folder);
            var bolts = Field<NumericTextBox>(form, "BoltsTextBox");
            True(bolts is TextBox, "Currency input must be a plain TextBox.");
            foreach (string text in new[] { "", "-1", "1.5", "2147483648", "bad paste" })
            {
                bolts.Text = text;
                True(!Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Invalid text must disable Save All.");
                var save = (Task<bool>)typeof(MainForm).GetMethod("SaveChanges", BindingFlags.NonPublic | BindingFlags.Instance).Invoke(form, null);
                True(!save.GetAwaiter().GetResult(), "Programmatic save must also reject invalid text.");
                Same(original, Snapshot(folder));
            }
            bolts.Text = "124";
            True(Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Corrected pending value should enable saving.");
            bolts.Text = "123";
            var raritanium = Field<NumericTextBox>(form, "RaritaniumTextBox");
            raritanium.Text = "-1";
            True(!Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Invalid raritanium must disable saving.");
            raritanium.Text = "45";
            True(!Field<ToolStripMenuItem>(form, "saveAllToolStripMenuItem").Enabled, "Reverting text must clear dirty state.");
            True(!Descendants(form).OfType<NumericUpDown>().Any(), "No numeric spinners should remain.");
        });
        Check("Invalid ammo and percentage text survives category switches and cannot expose pending edits", () =>
        {
            using var editor = new TodSaveEditingControl();
            editor.LoadSnapshot(EditableFixture(), "BCUS98127");
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            var voice = editor.Controls.Find("MappedEdit_voice_volume", true).Cast<NumericTextBox>().Single();
            voice.Text = "25.5";
            Equal(25.5m, editor.PendingEdits["voice_volume"]);
            voice.Text = "invalid paste";
            True(editor.HasInvalidInputs && editor.HasChanges, "Invalid text must not become a no-op.");
            Throws<InvalidOperationException>(() => { _ = editor.PendingEdits; });
            category.SelectedItem = "Weapon ammo";
            True(!editor.ValidateInputs(), "Validation must find invalid fields in hidden categories.");
            Equal("Game settings", category.SelectedItem.ToString());
            Equal("invalid paste", editor.Controls.Find("MappedEdit_voice_volume", true).Cast<NumericTextBox>().Single().Text);
            editor.Controls.Find("MappedEdit_voice_volume", true).Cast<NumericTextBox>().Single().Text = "50";
            True(!editor.HasChanges, "Correcting to the baseline must remove the edit.");
            category.SelectedItem = "Weapon ammo";
            var ammo = editor.Controls.Find("MappedEdit_ammo_1", true).Cast<NumericTextBox>().Single();
            ammo.Text = "100.01";
            True(editor.HasInvalidInputs, "Reference ammo maximum must be enforced.");
            ammo.Text = "12.5";
            True(!editor.HasInvalidInputs, "Fractional ammo inside the limit must be accepted.");
            Equal(12.5m, editor.PendingEdits["ammo_1"]);
            editor.LoadSnapshot(EditableFixture(), "BCUS98124");
            True(!editor.HasChanges && !editor.HasInvalidInputs, "Switching games must clear old numeric text/errors.");
        });
        Check("Invalid character currency stays visible and does not switch or overwrite another character", () =>
        {
            using var form = new MainForm();
            using var session = SaveSession.Open(Fixture(root, "BCUS98175"), new FakeTools(), backupRoot: Path.Combine(root, "numeric-character-backups"));
            typeof(MainForm).GetField("session", BindingFlags.NonPublic | BindingFlags.Instance).SetValue(form, session);
            typeof(MainForm).GetMethod("ShowSession", BindingFlags.NonPublic | BindingFlags.Instance).Invoke(form, null);
            var money = Field<NumericTextBox>(form, "BoltsTextBox");
            money.Text = "500";
            money.Text = "bad";
            var characters = Field<ComboBox>(form, "CharacterComboBox");
            characters.SelectedItem = "Clank";
            Equal("Ratchet", characters.SelectedItem);
            Equal("bad", money.Text);
            money.Text = "500";
            characters.SelectedItem = "Clank";
            Equal(123m, money.Value);
            characters.SelectedItem = "Ratchet";
            Equal(500m, money.Value);
        });
        Check("QForce precision limit remains enforced by the currency text box", () =>
        {
            using var input = new NumericTextBox { Maximum = SaveProfile.ForRegion("BCUS98380").MaximumBolts };
            input.Text = "16777216";
            True(input.IsValid, "QForce maximum should be accepted.");
            input.Text = "16777217";
            True(!input.IsValid, "QForce float precision limit must remain enforced.");
        });
        Check("Hex-offset text box validates hex syntax and snapshot bounds", () =>
        {
            using var input = new NumericTextBox { Hexadecimal = true, Maximum = 0x906EF };
            foreach (string text in new[] { "0", "1A", "0x10", "906EF" })
            {
                input.Text = text;
                True(input.IsValid, "Valid hexadecimal offset rejected.");
            }
            foreach (string text in new[] { "", "0x", "GG", "-1", "1.5", "906F0", "FFFFFFFFF" })
            {
                input.Text = text;
                True(!input.IsValid, "Invalid hexadecimal offset accepted.");
            }
        });
    }
}
