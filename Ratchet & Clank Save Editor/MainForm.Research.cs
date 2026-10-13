using System.Windows.Forms;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public partial class MainForm
    {
        private SaveInspectorControl saveInspector;
        private TabPage inspectionTab;
        private TabPage researchTab;
        private TodInventoryPreviewControl inventoryPreview;

        private void InitializeResearchViews()
        {
            saveInspector = new SaveInspectorControl();
            inventoryPreview = new TodInventoryPreviewControl();
            var inventoryTab = new TabPage("Inventory") { Name = "InventoryPreviewTab", UseVisualStyleBackColor = true };
            inventoryTab.Controls.Add(inventoryPreview);
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
            TabControl.TabPages.Add(inventoryTab);
            TabControl.TabPages.Add(inspectionTab);
            TabControl.TabPages.Add(researchTab);
            // All tabs share the readable, resizable main-window layout.
            FormBorderStyle = FormBorderStyle.Sizable;
            MaximizeBox = true;
        }
    }
}
