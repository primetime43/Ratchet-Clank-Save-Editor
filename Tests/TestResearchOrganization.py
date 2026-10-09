"""Check research navigation and embedded-resource paths after file moves."""
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "docs/PS3/ToolsOfDestruction/BCUS98127/v02.00"


class ResearchOrganizationTests(unittest.TestCase):
    def test_local_document_links_resolve(self):
        documents = [ROOT / "README.md", *ROOT.glob("docs/**/*.md"),
                     *ROOT.glob("Tools/**/README.md")]
        for document in documents:
            for target in re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", document.read_text(encoding="utf-8")):
                if re.match(r"^[a-zA-Z]+:", target) or target.startswith("#"):
                    continue
                with self.subTest(document=document.relative_to(ROOT), target=target):
                    self.assertTrue((document.parent / target.split("#", 1)[0]).exists())

    def test_embedded_resources_resolve_and_keep_names(self):
        project = ROOT / "Ratchet & Clank Save Editor/Ratchet & Clank Save Editor.csproj"
        resources = {item.attrib["LogicalName"]: project.parent / item.attrib["Include"]
                     for item in ET.parse(project).iter("EmbeddedResource")}
        expected = {
            "Research.Tod.Map.json": BUILD / "maps/NativeMap.json",
            "Research.Tod.Configs.json": BUILD / "maps/WeaponConfigs.json",
            "Research.Tod.ElfNotes.md": BUILD / "ElfMap.md",
            "Research.Tod.SaveNotes.md": BUILD.parent.parent / "SaveFormat.md",
        }
        for name, path in expected.items():
            with self.subTest(resource=name):
                self.assertEqual(resources[name].resolve(), path.resolve())
                self.assertTrue(path.is_file())

    def test_map_report_tools_resolve(self):
        mapping = json.loads((BUILD / "maps/NativeMap.json").read_text(encoding="utf-8"))
        for field in ("report_tool", "native_binding_report_tool"):
            with self.subTest(field=field):
                self.assertTrue((ROOT / mapping["weapon_configuration"][field]).is_file())

    def test_region_version_indexes_are_distinct(self):
        game = BUILD.parent.parent
        self.assertTrue((game / "BCUS98127/v02.00/README.md").is_file())
        self.assertTrue((game / "BCES00052/unknown/README.md").is_file())
        self.assertFalse((game / "BCES00052/v02.00").exists())


if __name__ == "__main__":
    unittest.main()
