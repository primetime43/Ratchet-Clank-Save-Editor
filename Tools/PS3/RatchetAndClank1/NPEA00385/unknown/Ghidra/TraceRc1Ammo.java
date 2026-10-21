// Analyze only the supplied European trilogy RC1 ELF. Never patches game bytes.
// @category RatchetClank
import java.io.PrintWriter;
import java.math.BigInteger;
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

public class TraceRc1Ammo extends GhidraScript {
    public void run() throws Exception {
        if (!"cce4e741c395518dc4374cf87a7a81e6975f573f99cad8ac2b6b3eaafa4bae9a".equalsIgnoreCase(currentProgram.getExecutableSHA256()))
            throw new IllegalStateException("RC1 ELF SHA-256 mismatch.");
        if (!"PowerPC:BE:64:64-32addr".equals(currentProgram.getLanguageID().toString()))
            throw new IllegalStateException("Use PowerPC:BE:64:64-32addr with the default compiler.");
        if (getScriptArgs().length != 1) throw new IllegalArgumentException("Supply a report output path.");
        currentProgram.getProgramContext().setValue(currentProgram.getRegister("r2"),
            toAddr(0x10230), toAddr(0x64ed7f), BigInteger.valueOf(0x722328));
        long[] addresses = {0xe6cd8, 0xe6fe4, 0xe784c, 0xe7984, 0x8e0f4, 0xaa258, 0xaa2e8, 0xeb0f4,
            0x112e18, 0x16cc50, 0x143980, 0x143c30, 0x143cbc};
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        try (PrintWriter output = new PrintWriter(getScriptArgs()[0])) {
            output.println("RC1 native save/ammo/grant/quick-select trace. Generated pseudocode must be checked against instruction bytes.");
            output.println("The grant helper's Cell-vector notification path has unsupported instructions. Only grants with both notification IDs -1 bypass that path; see the pinned native map.");
            for (long value : addresses) {
                monitor.checkCancelled();
                Address entry = toAddr(value);
                disassemble(entry);
                Function function = getFunctionAt(entry);
                if (function == null) function = createFunction(entry, null);
                if (function == null) throw new IllegalStateException("Cannot create function at " + entry);
                DecompileResults result = decompiler.decompileFunction(function, 60, monitor);
                if (!result.decompileCompleted()) throw new IllegalStateException(result.getErrorMessage());
                output.println("\nFUNCTION " + entry);
                output.println(result.getDecompiledFunction().getC());
            }
        } finally { decompiler.dispose(); }
    }
}
