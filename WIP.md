# Work In Progress: CrLZH Decompression

## Status: RESOLVED

The CrLZH decompressor is working correctly. Both Python and PL/M versions
produce identical output (verified with binary mode comparison).

## Issue Summary

Initial testing showed "missing CR bytes" when comparing PL/M output against
Python raw output. Investigation revealed this was caused by the cpmemu
emulator's automatic text mode conversion, not a bug in the decompressor.

## Root Cause

cpmemu detects files with text extensions (.MAC, .ASM, .TXT, etc.) and
automatically converts CR+LF to LF when writing to the Unix filesystem.
This is helpful for normal use but caused confusion during testing.

## Resolution

1. Use `default_mode = binary` in cpmemu config for accurate testing
2. Updated test suite with proper EOL handling tests
3. Added documentation in CLAUDE.md and README.md

## Verification

```bash
# With binary mode config, PL/M output matches Python raw exactly:
cpmemu test.cfg TEST.MYC
cmp lzhdef.mac /tmp/py_raw.mac  # Perfect match!
```

## Previous Changes (still valid)

- Fixed `update_tree` loop structure in `src/plm/lzh.plm`
- Changed `init$lzh$tables` loop variable from `byte` to `address`
- Switched to buffered I/O (getbyte/putbyte) for consistency
