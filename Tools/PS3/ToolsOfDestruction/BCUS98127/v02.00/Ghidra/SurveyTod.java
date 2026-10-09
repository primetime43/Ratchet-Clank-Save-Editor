// Export save-related references and selected decompiler/assembly evidence.
// Usage: -postScript SurveyTod.java <output-directory> [function-address ...]
// @category RatchetClank
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.regex.Pattern;
import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.lang.Register;

public class SurveyTod extends GhidraScript {
    private final LinkedHashMap<Address, Function> selected = new LinkedHashMap<>();
    private final Map<Long, Long> functionTocs = new HashMap<>();
    private final Map<Long, List<Address>> tocLoads = new HashMap<>();
    private void indexTocLoads() throws Exception {
        for (long descriptor = 0x859408L; descriptor < 0x887f38L; descriptor += 8)
            functionTocs.put(Integer.toUnsignedLong(getInt(toAddr(descriptor))),
                Integer.toUnsignedLong(getInt(toAddr(descriptor + 4))));
        InstructionIterator instructions = currentProgram.getListing().getInstructions(true);
        while (instructions.hasNext()) {
            Instruction instruction = instructions.next();
            if (!instruction.getMnemonicString().matches("lwz|ld|addi")) continue;
            boolean r2 = false;
            Scalar offset = null;
            // The source address is operand 1 for loads, operands 1/2 for addi.
            for (int op = 1; op < instruction.getNumOperands(); op++)
                for (Object object : instruction.getOpObjects(op)) {
                    if (object instanceof Register && ((Register)object).getName().equals("r2")) r2 = true;
                    if (object instanceof Scalar) offset = (Scalar)object;
                }
            if (!r2 || offset == null) continue;
            Function function = getFunctionContaining(instruction.getAddress());
            if (function == null) continue;
            Long toc = functionTocs.get(function.getEntryPoint().getOffset());
            if (toc == null) continue;
            long slot = toc + (short)offset.getValue();
            tocLoads.computeIfAbsent(slot, unused -> new ArrayList<>()).add(instruction.getAddress());
        }
    }
    private void select(Address from) {
        Function function = getFunctionContaining(from);
        if (function != null && selected.size() < 32) selected.put(function.getEntryPoint(), function);
    }
    @Override public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length == 0) throw new IllegalArgumentException("Output directory required.");
        Path output = Paths.get(args[0]);
        Files.createDirectories(output);
        Pattern interesting = Pattern.compile("(?i)(GAME\\.SAV|save_game|savedata|savegame|weapon.*(?:xp|ammo|level)|bolt|raritan|nanotech|multiplier|serialize|^cell|^sys_|^sys[A-Z]|Lua 5|physics|shader|renderer|thread|allocator|x:/rcf)");
        Pattern save = Pattern.compile("(?i)(GAME\\.SAV|save_game|savedata|savegame|serialize)");
        indexTocLoads();
        try (PrintWriter writer = new PrintWriter(Files.newBufferedWriter(output.resolve("survey.txt"), StandardCharsets.UTF_8))) {
            writer.println("Program: " + currentProgram.getName());
            writer.println("Language: " + currentProgram.getLanguageID());
            writer.println("Compiler: " + currentProgram.getCompilerSpec().getCompilerSpecID());
            writer.println("Functions: " + currentProgram.getFunctionManager().getFunctionCount());
            writer.println("Addresses are virtual addresses in the USA BCUS98127 v02.00 ELF, not file/save offsets.");
            for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
                writer.printf("BLOCK %s %s-%s execute=%s initialized=%s%n", block.getName(), block.getStart(), block.getEnd(), block.isExecute(), block.isInitialized());
                if (!block.isInitialized() || block.getSize() > 64 * 1024 * 1024) continue;
                byte[] bytes = new byte[(int)block.getSize()];
                currentProgram.getMemory().getBytes(block.getStart(), bytes);
                for (int i = 0; i < bytes.length;) {
                    int start = i;
                    while (i < bytes.length && bytes[i] >= 0x20 && bytes[i] <= 0x7e) i++;
                    if (i - start >= 5) {
                        String text = new String(bytes, start, i - start, StandardCharsets.US_ASCII);
                        if (interesting.matcher(text).find()) {
                            Address address = block.getStart().add(start);
                            writer.printf("STRING %s %s%n", address, text);
                            boolean isSave = save.matcher(text).find();
                            for (Reference reference : getReferencesTo(address)) {
                                writer.printf("  REF %s %s function=%s%n", reference.getFromAddress(), reference.getReferenceType(), getFunctionContaining(reference.getFromAddress()));
                                if (isSave) select(reference.getFromAddress());
                                for (Address load : tocLoads.getOrDefault(reference.getFromAddress().getOffset(), Collections.emptyList())) {
                                    writer.printf("    DESCRIPTOR_TOC_LOAD %s %s function=%s%n", load, getInstructionAt(load), getFunctionContaining(load));
                                    if (isSave) select(load);
                                }
                                for (Reference indirect : getReferencesTo(reference.getFromAddress())) {
                                    writer.printf("    VIA %s %s function=%s%n", indirect.getFromAddress(), indirect.getReferenceType(), getFunctionContaining(indirect.getFromAddress()));
                                    if (isSave) select(indirect.getFromAddress());
                                }
                            }
                        }
                    }
                    i++;
                }
            }
            for (int i = 1; i < args.length; i++) {
                Address address = toAddr(Long.parseUnsignedLong(args[i].replaceFirst("^0[xX]", ""), 16));
                Function function = getFunctionAt(address);
                if (function == null) { disassemble(address); function = createFunction(address, null); }
                if (function != null) selected.put(function.getEntryPoint(), function);
            }
            DecompInterface decompiler = new DecompInterface();
            try {
                decompiler.openProgram(currentProgram);
                for (Function function : selected.values()) {
                    monitor.checkCancelled();
                    String filename = function.getEntryPoint().toString();
                    writer.printf("SELECTED %s %s%n", filename, function.getName());
                    writer.println("  CALLERS " + function.getCallingFunctions(monitor));
                    writer.println("  CALLEES " + function.getCalledFunctions(monitor));
                    DecompileResults result = decompiler.decompileFunction(function, 30, monitor);
                    if (result.decompileCompleted())
                        Files.writeString(output.resolve(filename + ".c"), result.getDecompiledFunction().getC(), StandardCharsets.UTF_8);
                    else writer.println("  DECOMPILER FAILURE " + result.getErrorMessage());
                    try (PrintWriter assembly = new PrintWriter(Files.newBufferedWriter(output.resolve(filename + ".asm"), StandardCharsets.UTF_8))) {
                        InstructionIterator instructions = currentProgram.getListing().getInstructions(function.getBody(), true);
                        while (instructions.hasNext()) {
                            Instruction instruction = instructions.next();
                            assembly.println(instruction.getAddress() + " " + instruction);
                        }
                    }
                }
            } finally { decompiler.dispose(); }
        }
        println("Survey exported to " + output + "; " + selected.size() + " selected functions.");
    }
}
