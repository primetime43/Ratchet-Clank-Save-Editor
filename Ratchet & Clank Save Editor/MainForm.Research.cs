using System.Windows.Forms;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public partial class MainForm
    {
        private SaveInspectorControl saveInspector;
        private TabPage inspectionTab;
        private TabPage researchTab;

        private void InitializeResearchViews()
        {
            saveInspector = new SaveInspectorControl();
            inspectionTab = new TabPage("Save inspector") { Name = "SaveInspectorTab", UseVisualStyleBackColor = true };
            inspectionTab.Controls.Add(saveInspector);
            researchTab = new TabPage("Research") { Name = "ResearchTab", UseVisualStyleBackColor = true };
            var research = new ResearchBrowserControl();
            researchTab.Controls.Add(research);
            saveInspector.WeaponReferenceRequested += id =>
            {
                research.ShowWeapon(id);
                TabControl.SelectedTab = researchTab;
            };
            TabControl.TabPages.Add(inspectionTab);
            TabControl.TabPages.Add(researchTab);
            // Keep the original compact size and controls, with room to enlarge
            // read-only grids and research notes when the user wants it.
            FormBorderStyle = FormBorderStyle.Sizable;
            MaximizeBox = true;
        }
    }
}
