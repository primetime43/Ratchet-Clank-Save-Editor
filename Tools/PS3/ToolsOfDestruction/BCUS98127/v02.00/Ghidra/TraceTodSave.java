// Targeted, read-only database survey for the exact BCUS98127 v02.00 ELF.
// Usage: <fresh-output-directory> f:VA r:VA d:VA:hex-length n:VA:decimal-count i:hex-immediate
// f exports a function; r finds refs/TOC-load leads; d dumps data; n exports nearby functions;
// i scans immediate operands. Leads require assembly verification, especially r2-changing thunks.
// @category RatchetClank
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import ghidra.app.decompiler.*;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.*;
import ghidra.program.model.lang.Register;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.symbol.Reference;

public class TraceTodSave extends GhidraScript {
    private final Map<Long, Long> tocs = new HashMap<>();
    private final Map<Long, List<Long>> descriptors = new HashMap<>();
    private final LinkedHashMap<Long, Function> selected = new LinkedHashMap<>();
    private long hex(String text) { return Long.parseUnsignedLong(text.replaceFirst("^0[xX]", ""), 16); }
    private void select(Address address) {
        Function function = getFunctionContaining(address);
        if (function != null) selected.put(function.getEntryPoint().getOffset(), function);
    }
    @Override public void run() throws Exception {
        if (!"0ee9a8414c8fc182bc19fa2a523e6d050d0be76138b3733ae515798d77d2468c".equalsIgnoreCase(currentProgram.getExecutableSHA256()))
            throw new IllegalStateException("Reference ELF SHA-256 mismatch.");
        String[] args = getScriptArgs();
        if (args.length < 2) throw new IllegalArgumentException("Output directory and query required.");
        for (int index = 1; index < args.length; index++) {
            String[] query = args[index].split(":", -1);
            boolean sized = query[0].equals("d") || query[0].equals("n");
            if (!query[0].matches("f|r|d|n|i") || query.length != (sized ? 3 : 2))
                throw new IllegalArgumentException("Invalid query " + args[index]);
            hex(query[1]);
            if (sized) {
                long amount = query[0].equals("d") ? hex(query[2]) : Integer.parseInt(query[2]);
                if (amount < 1 || amount > (query[0].equals("d") ? 0x100000 : 256))
                    throw new IllegalArgumentException("Query size out of range: " + args[index]);
            }
        }
        Path output = Paths.get(args[0]);
        Files.createDirectory(output); // refuse overwriting prior evidence
        for (long descriptor = 0x859408; descriptor < 0x887f38; descriptor += 8) {
            long code = Integer.toUnsignedLong(getInt(toAddr(descriptor)));
            tocs.put(code, Integer.toUnsignedLong(getInt(toAddr(descriptor + 4))));
            descriptors.computeIfAbsent(code, unused -> new ArrayList<>()).add(descriptor);
        }
        Set<Long> targets = new HashSet<>(), immediates = new HashSet<>();
        try (PrintWriter writer = new PrintWriter(Files.newBufferedWriter(output.resolve("trace.txt"), StandardCharsets.UTF_8))) {
            writer.println("Exact reference ELF; all addresses are original virtual addresses. TOC matches are research leads, not proven runtime r2 values.");
            for (int index = 1; index < args.length; index++) {
                String[] query = args[index].split(":");
                long value = hex(query[1]);
                Address address = toAddr(value);
                writer.println("QUERY " + args[index]);
                switch (query[0]) {
                    case "f": select(address); break;
                    case "r":
                        targets.add(value);
                        for (Reference reference : getReferencesTo(address)) {
                            writer.println("REF " + reference.getFromAddress() + " " + reference.getReferenceType() + " " + getFunctionContaining(reference.getFromAddress()));
                            select(reference.getFromAddress());
                        }
                        break;
                    case "d":
                        int length = (int)hex(query[2]);
                        if (currentProgram.getMemory().getBlock(address) == null || !currentProgram.getMemory().getBlock(address).isInitialized()) {
                            writer.println("UNINITIALIZED_OR_UNMAPPED: runtime bytes unavailable; no data guessed.");
                            break;
                        }
                        // Reject a partial range instead of reporting unread bytes as zero.
                        if (!currentProgram.getMemory().getBlock(address).contains(address.add(length - 1)))
                            throw new IllegalArgumentException("Data query crosses a memory block: " + args[index]);
                        byte[] bytes = new byte[length];
                        if (currentProgram.getMemory().getBytes(address, bytes) != length)
                            throw new IllegalStateException("Incomplete data read at " + address);
                        for (int offset = 0; offset < length; offset += 16)
                            writer.println(address.add(offset) + " " + HexFormat.of().withUpperCase().formatHex(bytes, offset, Math.min(offset + 16, length)));
                        break;
                    case "n":
                        int count = Integer.parseInt(query[2]);
                        Function cursor = getFunctionContaining(address);
                        if (cursor == null) cursor = getFunctionBefore(address);
                        for (int step = 0; step < count / 2 && cursor != null; step++) {
                            Function previous = getFunctionBefore(cursor.getEntryPoint());
                            if (previous == null) break;
                            cursor = previous;
                        }
                        for (int step = 0; step < count && cursor != null; step++) {
                            selected.put(cursor.getEntryPoint().getOffset(), cursor);
                            cursor = getFunctionAfter(cursor.getEntryPoint());
                        }
                        break;
                    case "i": immediates.add(value); break;
                    default: throw new IllegalArgumentException("Unknown query " + args[index]);
                }
            }
            if (!targets.isEmpty() || !immediates.isEmpty()) {
                InstructionIterator iterator = currentProgram.getListing().getInstructions(true);
                while (iterator.hasNext()) {
                    monitor.checkCancelled();
                    Instruction instruction = iterator.next();
                    boolean r2 = false, immediateHit = false;
                    Scalar displacement = null;
                    for (int op = 0; op < instruction.getNumOperands(); op++)
                        for (Object operand : instruction.getOpObjects(op)) {
                            if (op > 0 && operand instanceof Register && ((Register)operand).getName().equals("r2")) r2 = true;
                            if (operand instanceof Scalar) {
                                Scalar scalar = (Scalar)operand;
                                if (op > 0) displacement = scalar;
                                if (immediates.contains(scalar.getUnsignedValue()) || immediates.contains(scalar.getSignedValue())) immediateHit = true;
                            }
                        }
                    Function function = getFunctionContaining(instruction.getAddress());
                    if (immediateHit) writer.println("IMMEDIATE " + instruction.getAddress() + " " + instruction + " " + function);
                    if (!r2 || displacement == null || function == null || !instruction.getMnemonicString().matches("lwz|ld|addi|stw|stb|lfs|stfs")) continue;
                    Long toc = tocs.get(function.getEntryPoint().getOffset());
                    if (toc == null) continue;
                    long slot = toc + (short)displacement.getValue();
                    long pointer = -1;
                    if ((slot & 3) == 0 && currentProgram.getMemory().getBlock(toAddr(slot)) != null &&
                        currentProgram.getMemory().getBlock(toAddr(slot)).isInitialized() &&
                        currentProgram.getMemory().getBlock(toAddr(slot)).contains(toAddr(slot + 3)))
                        pointer = Integer.toUnsignedLong(getInt(toAddr(slot)));
                    if (targets.contains(slot) || targets.contains(pointer)) {
                        writer.printf("TOC_LEAD %s %s function=%s toc=%08x slot=%08x word=%08x%n", instruction.getAddress(), instruction, function, toc, slot, pointer);
                        select(instruction.getAddress());
                    }
                }
            }
            DecompInterface decompiler = new DecompInterface();
            try {
                decompiler.openProgram(currentProgram);
                for (Function function : selected.values()) {
                    monitor.checkCancelled();
                    Address entry = function.getEntryPoint();
                    writer.printf("FUNCTION %s %s TOC=%s DESCRIPTORS=%s%n", entry, function.getName(), tocs.get(entry.getOffset()), descriptors.get(entry.getOffset()));
                    writer.println("CALLERS " + function.getCallingFunctions(monitor));
                    writer.println("CALLEES " + function.getCalledFunctions(monitor));
                    for (Reference reference : getReferencesTo(entry)) writer.println("ENTRY_REF " + reference.getFromAddress() + " " + reference.getReferenceType());
                    DecompileResults result = decompiler.decompileFunction(function, 30, monitor);
                    if (result.decompileCompleted()) Files.writeString(output.resolve(entry + ".c"), result.getDecompiledFunction().getC(), StandardCharsets.UTF_8);
                    else writer.println("DECOMPILER_FAILURE " + result.getErrorMessage());
                    try (PrintWriter assembly = new PrintWriter(Files.newBufferedWriter(output.resolve(entry + ".asm"), StandardCharsets.UTF_8))) {
                        InstructionIterator instructions = currentProgram.getListing().getInstructions(function.getBody(), true);
                        while (instructions.hasNext()) {
                            Instruction instruction = instructions.next();
                            assembly.println(instruction.getAddress() + " " + HexFormat.of().withUpperCase().formatHex(instruction.getBytes()) + " " + instruction);
                        }
                    }
                }
            } finally { decompiler.dispose(); }
        }
        println("Trace exported: " + selected.size() + " functions to " + output);
    }
}
