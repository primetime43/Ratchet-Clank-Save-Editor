// Apply the shared Tools of Destruction address map to an imported ELF.
// Usage: -postScript ImportTodMap.java <map.json>, or choose the map in Script Manager.
// Only database labels/comments/types are changed; no executable bytes are patched.
// @category RatchetClank
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.Arrays;
import java.util.regex.Pattern;
import com.google.gson.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class ImportTodMap extends GhidraScript {
    private long number(JsonElement value) { return Long.decode(value.getAsString()); }
    private boolean automatic(Symbol symbol) {
        return symbol == null || symbol.getSource() == SourceType.DEFAULT ||
            symbol.getName().matches("(?:\\.opd\\.)?(?:FUN|DAT|LAB|UNK)_[0-9a-fA-F]+");
    }
    @Override public void run() throws Exception {
        String[] args = getScriptArgs();
        Path path = args.length == 0 ? askFile("Choose the ToD ELF address map", "Import").toPath() : Paths.get(args[0]);
        JsonObject map = JsonParser.parseString(Files.readString(path, StandardCharsets.UTF_8)).getAsJsonObject();
        if (map.get("schema_version").getAsInt() != 1) throw new IllegalArgumentException("Unsupported map schema.");
        JsonObject binary = map.getAsJsonObject("binary");
        if (!binary.get("sha256").getAsString().equalsIgnoreCase(currentProgram.getExecutableSHA256()))
            throw new IllegalStateException("ELF SHA-256 mismatch. No annotations applied.");
        if (!currentProgram.getLanguageID().toString().equals(binary.get("ghidra_language").getAsString()))
            throw new IllegalStateException("Use the map's PowerPC language. No annotations applied.");
        // Preflight every address and supplied byte signature BEFORE changing the database.
        for (JsonElement item : map.getAsJsonArray("annotations")) {
            JsonObject entry = item.getAsJsonObject();
            Address address = toAddr(number(entry.get("va")));
            if (entry.get("kind").getAsString().equals("reference_base") && !currentProgram.getMemory().contains(address)) continue;
            if (!currentProgram.getMemory().contains(address))
                throw new IllegalStateException("Unmapped VA " + address + "; rebased/incorrect import. No annotations applied.");
            if (entry.has("bytes")) {
                byte[] expected = java.util.HexFormat.of().parseHex(entry.get("bytes").getAsString());
                byte[] actual = new byte[expected.length];
                currentProgram.getMemory().getBytes(address, actual);
                if (!Arrays.equals(expected, actual))
                    throw new IllegalStateException("Byte mismatch at " + address + ". No annotations applied.");
            }
        }
        DataTypeManager manager = currentProgram.getDataTypeManager();
        CategoryPath category = new CategoryPath("/RatchetClank/ToolsOfDestruction");
        for (JsonElement item : map.getAsJsonArray("structures")) {
            JsonObject record = item.getAsJsonObject();
            String name = record.get("name").getAsString();
            if (manager.getDataType(category, name) != null) { println("Keeping existing type " + name); continue; }
            StructureDataType structure = new StructureDataType(category, name, (int)number(record.get("size")), manager);
            structure.setDescription(record.get("comment").getAsString());
            for (JsonElement member : record.getAsJsonArray("fields")) {
                JsonObject field = member.getAsJsonObject();
                DataType type;
                switch (field.get("type").getAsString()) {
                    case "u32": type = UnsignedIntegerDataType.dataType; break;
                    case "u16": type = UnsignedShortDataType.dataType; break;
                    case "f32": type = FloatDataType.dataType; break;
                    case "u8": type = ByteDataType.dataType; break;
                    default: throw new IllegalArgumentException("Unsupported field type.");
                }
                int count = field.has("count") ? field.get("count").getAsInt() : 1;
                if (count != 1) type = new ArrayDataType(type, count, type.getLength(), manager);
                structure.replaceAtOffset((int)number(field.get("offset")), type, type.getLength(),
                    field.get("name").getAsString(), field.get("comment").getAsString());
            }
            manager.addDataType(structure, DataTypeConflictHandler.KEEP_HANDLER);
        }
        int count = 0;
        for (JsonElement item : map.getAsJsonArray("annotations")) {
            monitor.checkCancelled();
            JsonObject entry = item.getAsJsonObject();
            Address address = toAddr(number(entry.get("va")));
            if (entry.get("kind").getAsString().equals("reference_base") && !currentProgram.getMemory().contains(address)) {
                println("Unmapped TOC reference base retained in JSON: " + address);
                continue;
            }
            String name = entry.get("name").getAsString();
            Symbol primary = currentProgram.getSymbolTable().getPrimarySymbol(address);
            Symbol label = currentProgram.getSymbolTable().getSymbol(name, address, null);
            if (label == null) label = currentProgram.getSymbolTable().createLabel(address, name, SourceType.USER_DEFINED);
            if (automatic(primary)) label.setPrimary();
            String note = "[ToD map: " + name + "; " + entry.get("confidence").getAsString() + "]\n" +
                entry.get("comment").getAsString() + "\nEvidence: " + entry.get("evidence").getAsString();
            String old = getPlateComment(address);
            String markerPattern = "(?m)^\\[ToD map: " + Pattern.quote(name) + ";";
            if (old == null || !old.contains(note) || Pattern.compile(markerPattern).matcher(old).results().count() > 1) {
                // Preserve older findings and custom prose, only retiring our
                // own marker so there is one current note after an update.
                if (old != null) old = old.replaceAll(markerPattern,
                    "[Previous ToD map: " + name + ";");
                setPlateComment(address, old == null ? note : old + "\n\n" + note);
            }
            // Do not apply save-file structures to ELF memory without verified serialization mapping.
            count++;
        }
        println("Imported " + count + " ToD annotations. Existing custom names/comments/types preserved; no bytes patched.");
    }
}
