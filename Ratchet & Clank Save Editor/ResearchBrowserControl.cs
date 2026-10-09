using System;
using System.Collections.Generic;
using System.Globalization;
using System.Drawing;
using System.Linq;
using System.Text.Json;
using System.Windows.Forms;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    public sealed class ResearchBrowserControl : UserControl
    {
        private sealed record Topic(string Name, string Body, List<Topic> Children);
        private readonly List<Topic> topics = new();
        private readonly TreeView tree = new() { Name = "ResearchTopics", Dock = DockStyle.Fill, HideSelection = false };
        private readonly TextBox text = new() { Name = "ResearchDetails", Font = new Font("Consolas", 11F), Dock = DockStyle.Fill, ReadOnly = true, Multiline = true, WordWrap = true, ScrollBars = ScrollBars.Both, MaxLength = 0 };
        private readonly TextBox search = new() { Name = "ResearchSearch", Dock = DockStyle.Top, PlaceholderText = "Search findings, names, or addresses…" };

        public ResearchBrowserControl()
        {
            Dock = DockStyle.Fill;
            AutoScaleDimensions = new SizeF(96, 96);
            AutoScaleMode = AutoScaleMode.Dpi;
            Font = new Font("Segoe UI", 11F);
            Padding = new Padding(10);
            tree.ItemHeight = Font.Height + 10;
            tree.FontChanged += (_, _) => tree.ItemHeight = tree.Font.Height + (10 * tree.DeviceDpi / 96);
            topics.Add(new("Overview", TodResearch.Scope + $"\r\n\r\n32 native inventory IDs; 28 shipped configuration definitions; 204 nodes including 15 starts; 15 grids; 60 skill points; 5 armor IDs; {TodResearch.Map.GetProperty("annotations").GetArrayLength()} ELF annotations and 118 imports.\r\n\r\nSelect a topic or search for a name/address. All content is embedded and read-only; original game files and private saves are not bundled. File offsets, save offsets and ELF virtual addresses must not be interchanged.\r\n\r\nResize the window for more reading space. Ctrl+C copies selected text.", new()));
            topics.Add(JsonTopic("Progression & armor", TodResearch.Map.GetProperty("progression"), 0));
            topics.Add(JsonTopic("Hero XP, collectibles & skins", TodResearch.Map.GetProperty("collectibles"), 0));
            topics.Add(JsonTopic("Saved pack/boot types & exact pack dispatch selector", TodResearch.Map.GetProperty("hero_aux_fields"), 0));
            topics.Add(JsonTopic("World progress & quick select", TodResearch.Map.GetProperty("world_state"), 0));
            topics.Add(JsonTopic("Gameplay segments, timing & retained log", TodResearch.Map.GetProperty("gameplay_segments"), 0));
            topics.Add(JsonTopic("Reward channels, caches & diminishing returns", TodResearch.Map.GetProperty("reward_channels"), 0));
            topics.Add(JsonTopic("Replay/restart lifecycle & retained segment median", TodResearch.Map.GetProperty("save_tail"), 0));
            topics.Add(JsonTopic("Per-world object bits & spawn rules", TodResearch.Map.GetProperty("world_object_flags"), 0));
            topics.Add(JsonTopic("Object counters & equipment", TodResearch.Map.GetProperty("objects"), 0));
            topics.Add(JsonTopic("Mission lists & flags", TodResearch.Map.GetProperty("mission_lists"), 0));
            topics.Add(JsonTopic("Native mission lookup keys & segment naming limits", TodResearch.Map.GetProperty("segment_bindings"), 0));
            topics.Add(JsonTopic("Segment-name configuration loader & hash collisions", TodResearch.Map.GetProperty("segment_configuration"), 0));
            topics.Add(JsonTopic("Shipped reference segment names for 19 worlds", TodResearch.Map.GetProperty("segment_configuration_assets"), 0));
            topics.Add(JsonTopic("World initialization footprint & opaque byte preservation", TodResearch.Map.GetProperty("world_aux_fields"), 0));
            topics.Add(JsonTopic("Blueprints & bonuses", TodResearch.Map.GetProperty("bonuses"), 0));
            topics.Add(JsonTopic("Equipment history & stored state", TodResearch.Map.GetProperty("state_storage"), 0));
            topics.Add(JsonTopic("Persistent grids, map labels & volume headers", TodResearch.Map.GetProperty("persistent_grid"), 0));
            topics.Add(JsonTopic("Map-menu order, images & native grid checks", TodResearch.Map.GetProperty("grid_routing"), 0));
            topics.Add(JsonTopic("Map rectangles, world projection & clearing brush", TodResearch.Map.GetProperty("grid_geometry"), 0));
            topics.Add(JsonTopic("Settings, load destinations & runtime limits", TodResearch.Map.GetProperty("settings"), 0));
            topics.Add(JsonTopic("Shipped pause-menu settings & API dispatch", TodResearch.Map.GetProperty("settings_menu"), 0));
            topics.Add(JsonTopic("Arena challenges, recorded wins & reward rules", TodResearch.Map.GetProperty("arena_challenges"), 0));
            topics.Add(JsonTopic("Reset-event categories & runtime countdown", TodResearch.Map.GetProperty("reset_categories"), 0));
            topics.Add(JsonTopic("Global event flags & native bit addressing", TodResearch.Map.GetProperty("global_flags"), 0));
            topics.Add(new("Weapons & gadgets", TodResearch.Scope, TodResearch.Inventory.Select(item =>
                new Topic(item.GetProperty("id") + " · " + item.GetProperty("config_name"), TodResearch.WeaponDetails(item.GetProperty("id").GetInt32()), new())).ToList()));
            topics.Add(new("Full native research map", TodResearch.Pretty(TodResearch.Map), TodResearch.Map.EnumerateObject().Select(p => JsonTopic(p.Name, p.Value, 0)).ToList()));
            topics.Add(JsonTopic("Shipped weapon / vendor definitions", TodResearch.Configs, 0));
            topics.Add(Document("Executable research notes", TodResearch.ElfNotes));
            topics.Add(Document("Save format / container notes", TodResearch.SaveNotes));
            var split = new SplitContainer { Dock = DockStyle.Fill, Name = "ResearchSplit", FixedPanel = FixedPanel.Panel1, Size = new Size(1050, 620), SplitterDistance = 320, SplitterWidth = 6, Panel1MinSize = 230, Panel2MinSize = 250 };
            split.Panel1.Controls.Add(tree);
            split.Panel2.Controls.Add(text);
            var searchBar = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, ColumnCount = 3, Padding = new Padding(0, 0, 0, 10) };
            searchBar.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            searchBar.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            searchBar.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            searchBar.Controls.Add(new Label { Text = "Search:", AutoSize = true, Dock = DockStyle.Fill, Margin = new Padding(0, 3, 12, 3), TextAlign = ContentAlignment.MiddleLeft }, 0, 0);
            search.Dock = DockStyle.Fill;
            searchBar.Controls.Add(search, 1, 0);
            var wrap = new CheckBox { Name = "ResearchWrapText", Text = "Wrap text", AutoSize = true, Checked = true, Margin = new Padding(12, 5, 0, 3) };
            wrap.CheckedChanged += (_, _) => text.WordWrap = wrap.Checked;
            searchBar.Controls.Add(wrap, 2, 0);
            Controls.Add(split);
            Controls.Add(searchBar);
            tree.AfterSelect += (_, args) => text.Text = ((Topic)args.Node.Tag).Body.Replace("\r\n", "\n").Replace("\n", "\r\n");
            search.TextChanged += (_, _) => Populate();
            Populate();
        }

        private static Topic JsonTopic(string name, JsonElement value, int depth)
        {
            var children = new List<Topic>();
            if (depth < 3)
            {
                if (value.ValueKind == JsonValueKind.Object)
                    children.AddRange(value.EnumerateObject().Where(p => p.Value.ValueKind is JsonValueKind.Object or JsonValueKind.Array).Select(p => JsonTopic(p.Name, p.Value, depth + 1)));
                if (value.ValueKind == JsonValueKind.Array)
                {
                    int index = 0;
                    foreach (var item in value.EnumerateArray())
                    {
                        string title = "[" + index++ + "]";
                        if (item.ValueKind == JsonValueKind.Object)
                        {
                            foreach (string key in new[] { "config_name", "name", "module", "va", "start", "enum", "index", "id" })
                                if (item.TryGetProperty(key, out var label) && label.ValueKind != JsonValueKind.Null) { title = label.ToString(); break; }
                            if (item.TryGetProperty("va", out var va) && !title.StartsWith("0x", StringComparison.Ordinal)) title = va + " · " + title;
                        }
                        children.Add(JsonTopic(title, item, depth + 1));
                    }
                }
            }
            return new(name.Replace('_', ' '), TodResearch.Pretty(value), children);
        }

        private static Topic Document(string name, string body)
        {
            var children = new List<Topic>();
            var lines = body.Replace("\r\n", "\n").Split('\n');
            for (int start = 0; start < lines.Length; start++)
            {
                if (!lines[start].StartsWith("## ", StringComparison.Ordinal) && !lines[start].StartsWith("### ", StringComparison.Ordinal)) continue;
                int end = start + 1;
                while (end < lines.Length && !lines[end].StartsWith("## ", StringComparison.Ordinal) && !lines[end].StartsWith("### ", StringComparison.Ordinal)) end++;
                children.Add(new(lines[start].TrimStart('#', ' '), string.Join("\n", lines[start..end]), new()));
            }
            return new(name, body, children);
        }

        private TreeNode Filter(Topic topic, string query)
        {
            var node = new TreeNode(topic.Name) { Tag = topic };
            foreach (var child in topic.Children)
            {
                var match = Filter(child, query);
                if (match != null) node.Nodes.Add(match);
            }
            return query.Length == 0 || node.Nodes.Count > 0 || topic.Name.Contains(query, StringComparison.OrdinalIgnoreCase) ||
                topic.Body.Contains(query, StringComparison.OrdinalIgnoreCase) ? node : null;
        }

        private void Populate()
        {
            tree.BeginUpdate();
            try
            {
                tree.Nodes.Clear();
                string query = search.Text.Trim();
                foreach (var topic in topics)
                {
                    var node = Filter(topic, query);
                    if (node != null) tree.Nodes.Add(node);
                }
                if (query.Length > 0) tree.ExpandAll();
                if (tree.Nodes.Count > 0) tree.SelectedNode = query.Length == 0 ? tree.Nodes[0] :
                    tree.Nodes.Cast<TreeNode>().Select(node => FirstMatch(node, query)).FirstOrDefault(node => node != null) ?? tree.Nodes[0];
                else text.Text = "No matching findings.";
            }
            finally { tree.EndUpdate(); }
        }

        private static TreeNode FirstMatch(TreeNode node, string query)
        {
            foreach (TreeNode child in node.Nodes)
            {
                var result = FirstMatch(child, query);
                if (result != null) return result;
            }
            var topic = (Topic)node.Tag;
            return topic.Name.Contains(query, StringComparison.OrdinalIgnoreCase) || topic.Body.Contains(query, StringComparison.OrdinalIgnoreCase) ? node : null;
        }

        public void ShowWeapon(int id)
        {
            if (id < 0 || id >= TodResearch.Inventory.Count) throw new ArgumentOutOfRangeException(nameof(id));
            search.Clear();
            var weapons = tree.Nodes.Cast<TreeNode>().Single(node => ((Topic)node.Tag).Name == "Weapons & gadgets");
            weapons.Expand();
            tree.SelectedNode = weapons.Nodes[id];
            tree.SelectedNode.EnsureVisible();
        }
    }
}
