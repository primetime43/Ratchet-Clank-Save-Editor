using System;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Windows.Forms;
using primetime43_Ratchet_Clank_Save_Editor;

internal static partial class Program
{
    private static void Alphabetical(ComboBox combo)
    {
        var labels = combo.Items.Cast<object>().Select(item => item.ToString()).ToArray();
        True(labels.SequenceEqual(labels.Order(StringComparer.CurrentCultureIgnoreCase)),
            combo.Name + " must display names alphabetically.");
    }

    private static void DropdownOrderingChecks(string root)
    {
        Check("Mapped categories and named choices sort without staging edits or changing saved selections", () =>
        {
            byte[] data = BonusFixture();
            var fields = TodSaveEditing.Fields(data, "BCUS98127");
            using var editor = new TodSaveEditingControl(); editor.LoadSnapshot(data, "BCUS98127");
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            Alphabetical(category); Equal("Game settings", category.SelectedItem);
            foreach (string page in category.Items.Cast<string>().ToArray())
            {
                category.SelectedItem = page;
                foreach (var field in fields.Where(field => field.Category == page && field.Options != null))
                {
                    var combo = editor.Controls.Find("MappedEdit_" + field.Key, true).OfType<ComboBox>().SingleOrDefault();
                    if (combo == null) continue; // Skill awards use a checklist.
                    Equal(field.Current, ((TodEditOption)combo.SelectedItem).Value);
                    if (field.Storage == TodEditStorage.WeaponLevel || field.Key == "control_scheme")
                    {
                        var values = combo.Items.Cast<TodEditOption>().Select(option => option.Value).ToArray();
                        True(values.SequenceEqual(values.Order()), "Numeric targets must stay in numeric order.");
                    }
                    else Alphabetical(combo);
                }
            }
            True(!editor.HasChanges, "Sorting and browsing must leave the save clean.");
            category.SelectedItem = "Bonus effects";
            var hero = editor.Controls.Find("MappedEdit_bonus_hero_head", true).Cast<ComboBox>().Single();
            hero.SelectedItem = hero.Items.Cast<TodEditOption>().Single(option => option.Value == 2);
            Equal(2m, editor.PendingEdits["bonus_hero_head"]);
            category.SelectedItem = "Game settings"; category.SelectedItem = "Bonus effects";
            hero = editor.Controls.Find("MappedEdit_bonus_hero_head", true).Cast<ComboBox>().Single();
            Equal(2m, ((TodEditOption)hero.SelectedItem).Value);
        });
        Check("Planet names sort by name while XP reference rows retain numeric order", () =>
        {
            using var editor = new TodSaveEditingControl(); editor.LoadSnapshot(GoldBoltFixture(), "BCUS98127");
            var category = editor.Controls.Find("MappedEditCategory", true).Cast<ComboBox>().Single();
            category.SelectedItem = "Gold bolts";
            var planets = editor.Controls.Find("MappedGoldBoltPlanet", true).Cast<ComboBox>().Single();
            Alphabetical(planets); Equal(1m, ((TodEditOption)planets.SelectedItem).Value);
            var planet = planets.Items.Cast<TodEditOption>().Last(); planets.SelectedItem = planet;
            category.SelectedItem = "Game settings"; category.SelectedItem = "Gold bolts";
            planets = editor.Controls.Find("MappedGoldBoltPlanet", true).Cast<ComboBox>().Single();
            Equal(planet.Value, ((TodEditOption)planets.SelectedItem).Value);
            category.SelectedItem = "Hero XP";
            var targets = editor.Controls.Find("MappedHeroXpTarget", true).Cast<ComboBox>().Single();
            True(targets.Items.Cast<TodEditOption>().Skip(2).Select(option => option.Value)
                .SequenceEqual(Enumerable.Range(0, 98).Select(index => (decimal)index)), "XP rows must not sort lexically.");
            True(!editor.HasChanges, "Browsing planets must not change collectible bits.");
        });
        Check("Inspector views and weapon filter sort while preserving the default and all-weapons sentinel", () =>
        {
            string folder = Fixture(root, "BCUS98127"); File.WriteAllBytes(Path.Combine(folder, "GAME.SAV"), EditableFixture());
            using var session = SaveSession.Open(folder, new FakeTools(), decrypted: true, backupRoot: Path.Combine(root, "dropdown-backups"));
            using var inspector = new SaveInspectorControl(); inspector.LoadSession(session);
            var views = inspector.Controls.Find("InspectionView", true).Cast<ComboBox>().Single();
            Alphabetical(views); Equal("Weapons & gadgets", views.SelectedItem);
            views.SelectedItem = "Upgrade nodes";
            var weapons = inspector.Controls.Find("UpgradeWeaponFilter", true).Cast<ComboBox>().Single();
            Alphabetical(weapons); Equal("All weapons", weapons.SelectedItem);
            var grid = inspector.Controls.Find("InspectionGrid", true).Cast<DataGridView>().Single();
            int allCount = grid.Rows.Count; True(allCount > 0, "The default must still show every upgrade.");
            weapons.SelectedIndex = weapons.Items.Count - 1;
            True(grid.Rows.Count > 0 && grid.Rows.Cast<DataGridViewRow>()
                .All(row => row.Cells[0].Value?.ToString() == weapons.Text), "Sorted weapon selections must filter by name.");
            weapons.SelectedItem = "All weapons"; Equal(allCount, grid.Rows.Count);
        });
        Check("Alphabetical character selection preserves native currency IDs and invalid-input recovery", () =>
        {
            using var session = SaveSession.Open(Fixture(root, "BCUS98175"), new FakeTools(), backupRoot: Path.Combine(root, "character-dropdown-backups"));
            using var form = new MainForm();
            typeof(MainForm).GetField("session", BindingFlags.NonPublic | BindingFlags.Instance).SetValue(form, session);
            typeof(MainForm).GetMethod("ShowSession", BindingFlags.NonPublic | BindingFlags.Instance).Invoke(form, null);
            var characters = Field<ComboBox>(form, "CharacterComboBox"); Alphabetical(characters);
            Equal("Ratchet", characters.SelectedItem);
            var money = Field<NumericTextBox>(form, "BoltsTextBox");
            foreach (string character in characters.Items.Cast<string>().ToArray())
            {
                characters.SelectedItem = character;
                money.Value = 500 + Array.IndexOf(SaveData.CharacterNames, character);
            }
            foreach (string character in characters.Items.Cast<string>().Reverse().ToArray())
            {
                characters.SelectedItem = character;
                Equal((decimal)(500 + Array.IndexOf(SaveData.CharacterNames, character)), money.Value);
            }
            var pending = Field<int[]>(form, "pendingBolts");
            True(pending.SequenceEqual(new[] { 500, 501, 502, 503 }), "Currency values must retain the native Ratchet/Clank/Qwark/Nefarious IDs.");
            characters.SelectedItem = "Ratchet"; money.Text = "bad";
            characters.SelectedItem = "Clank";
            Equal("Ratchet", characters.SelectedItem); Equal("bad", money.Text);
        });
    }
}
