// Seed PS3 32-bit function descriptors for the supplied BCUS98127 v02.00 ELF.
// Analysis-database changes only; this never patches or exports the executable.
// @category RatchetClank
import java.math.BigInteger;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressRangeIterator;
import ghidra.program.model.address.AddressRange;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.SourceType;

public class PrepareTod extends GhidraScript {
    @Override public void run() throws Exception {
        long first = 0x859408L, end = 0x887f38L, toc = 0x88ff38L;
        if (!currentProgram.getLanguageID().toString().equals("PowerPC:BE:64:64-32addr"))
            throw new IllegalStateException("Use PowerPC:BE:64:64-32addr for this PS3 ELF.");
        if (Integer.toUnsignedLong(getInt(toAddr(first))) != 0x10210L ||
            Integer.toUnsignedLong(getInt(toAddr(first + 4))) != toc ||
            Integer.toUnsignedLong(getInt(toAddr(first + 0x10))) != 0x14360L)
            throw new IllegalStateException("Descriptor signature differs from the reference ELF; refusing fixed-address preparation.");
        if (!"0ee9a8414c8fc182bc19fa2a523e6d050d0be76138b3733ae515798d77d2468c".equalsIgnoreCase(currentProgram.getExecutableSHA256()))
            throw new IllegalStateException("ELF SHA-256 differs from BCUS98127 v02.00; refusing preparation.");
        Register r2 = currentProgram.getLanguage().getRegister("r2");
        currentProgram.getSymbolTable().createLabel(toAddr(toc), "PS3_TOC_0", SourceType.USER_DEFINED);
        currentProgram.getSymbolTable().createLabel(toAddr(0x89ff20), "PS3_TOC_1", SourceType.USER_DEFINED);
        currentProgram.getSymbolTable().createLabel(toAddr(0x8afe5c), "PS3_TOC_2", SourceType.USER_DEFINED);
        int seeded = 0, skipped = 0;
        for (long descriptor = first; descriptor < end; descriptor += 8) {
            monitor.checkCancelled();
            long code = Integer.toUnsignedLong(getInt(toAddr(descriptor)));
            long entryToc = Integer.toUnsignedLong(getInt(toAddr(descriptor + 4)));
            Address address = toAddr(code);
            MemoryBlock block = currentProgram.getMemory().getBlock(address);
            if ((entryToc != toc && entryToc != 0x89ff20L && entryToc != 0x8afe5cL) ||
                (code & 3) != 0 || block == null || !block.isExecute()) { skipped++; continue; }
            currentProgram.getProgramContext().setValue(r2, address, address, BigInteger.valueOf(entryToc));
            Function function = getFunctionAt(address);
            if (function == null) {
                disassemble(address);
                function = createFunction(address, null);
                if (function == null) { skipped++; continue; }
            }
            AddressRangeIterator ranges = function.getBody().getAddressRanges();
            while (ranges.hasNext()) {
                AddressRange range = ranges.next();
                currentProgram.getProgramContext().setValue(r2, range.getMinAddress(), range.getMaxAddress(), BigInteger.valueOf(entryToc));
            }
            seeded++;
            if (seeded % 2000 == 0) println("PS3 descriptors seeded: " + seeded);
        }
        println("PS3 preparation: " + seeded + " descriptors seeded; " + skipped + " skipped; three per-function TOCs.");
    }
}
