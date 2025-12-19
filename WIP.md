# Work In Progress: CrLZH Decompression Bug

## Current Status
CrLZH decompression produces wrong output - missing CR (0x0D) bytes.

## Changes Made
- Fixed `update_tree` loop structure in `src/plm/lzh.plm`:
  - Original: `do while c <> 0` - skips if c starts as 0
  - Fixed: `do while 1; ... if c = 0 then return;`
  - This matches Python's `while True: ... if c == 0: break`
- Changed `init$lzh$tables` loop variable from `byte` to `address`
- Switched to buffered I/O (getbyte/putbyte) for consistency

## Findings
- Python simulation with BOTH buggy and fixed `update_tree` produces identical decode sequences
- No tree divergence found in 1000+ decodes
- TEST.MYC: First 70 bytes correct, byte 71 should be CR but is LF
- This proves the update_tree loop bug is NOT causing the CR-missing issue

## Next Steps
- Bug is elsewhere - possibly:
  - Compiler bug in uplm80 (bit manipulation?)
  - Issue in bit reader implementation
  - Something in output path filtering CRs
- Compare PL/M bit reader more closely with Python
- Check if there's CR filtering in I/O layer
