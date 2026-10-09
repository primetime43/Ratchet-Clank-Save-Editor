// Verify a matching database after applying the shared map twice.
// Usage: -scriptPath Tools/Ghidra -postScript TestTodMap.java <map.json>
// @category RatchetClank.Tests
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.*;
import ghidra.program.model.symbol.*;

public class TestTodMap extends GhidraScript {
    private void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
    @Override public void run() throws Exception {
        String[] args = getScriptArgs();
        JsonObject map = JsonParser.parseString(Files.readString(Paths.get(args[0]), StandardCharsets.UTF_8)).getAsJsonObject();
        runScript("ImportTodMap.java", new String[] { args[0] });
        runScript("ImportTodMap.java", new String[] { args[0] });
        int annotations = 0;
        for (JsonElement item : map.getAsJsonArray("annotations")) {
            JsonObject entry = item.getAsJsonObject();
            Address address = toAddr(Long.decode(entry.get("va").getAsString()));
            if (!currentProgram.getMemory().contains(address) && entry.get("kind").getAsString().equals("reference_base")) continue;
            String name = entry.get("name").getAsString();
            check(currentProgram.getSymbolTable().getSymbol(name, address, null) != null, "Missing label " + name);
            String comment = getPlateComment(address);
            String marker = "[ToD map: " + name + ";";
            check(comment != null && comment.contains(marker), "Missing comment " + name);
            check(comment.indexOf(marker) == comment.lastIndexOf(marker), "Duplicate note " + name);
            annotations++;
        }
        int structures = 0;
        for (JsonElement item : map.getAsJsonArray("structures")) {
            JsonObject definition = item.getAsJsonObject();
            DataType type = currentProgram.getDataTypeManager().getDataType(new CategoryPath("/RatchetClank/ToolsOfDestruction"), definition.get("name").getAsString());
            check(type instanceof Structure, "Missing structure " + definition.get("name"));
            check(type.getLength() == Long.decode(definition.get("size").getAsString()), "Wrong type size " + type.getName());
            for (JsonElement member : definition.getAsJsonArray("fields")) {
                JsonObject field = member.getAsJsonObject();
                int offset = Long.decode(field.get("offset").getAsString()).intValue();
                DataTypeComponent component = ((Structure)type).getComponentAt(offset);
                check(component != null && component.getOffset() == offset && field.get("name").getAsString().equals(component.getFieldName()), "Wrong member at " + offset + " in " + type.getName());
            }
            structures++;
        }
        // A custom primary label must survive another import at an annotated address.
        Address address = toAddr(0x10026648);
        Symbol previous = currentProgram.getSymbolTable().getPrimarySymbol(address);
        Symbol custom = currentProgram.getSymbolTable().createLabel(address, "TOD_TEST_custom_existing_name", SourceType.USER_DEFINED);
        custom.setPrimary();
        String oldComment = getPlateComment(address);
        try {
            setPlateComment(address, oldComment + "\nExisting independent research note.");
            runScript("ImportTodMap.java", new String[] { args[0] });
            check(currentProgram.getSymbolTable().getPrimarySymbol(address).equals(custom), "Custom primary name overwritten");
            check(getPlateComment(address).endsWith("Existing independent research note."), "Custom comment overwritten");
        } finally {
            if (previous != null) previous.setPrimary();
            custom.delete();
            setPlateComment(address, oldComment);
        }
        println("PASS: " + annotations + " annotations, " + structures + " structure layouts, repeat-import idempotence and custom-name/comment preservation.");
    }
}
