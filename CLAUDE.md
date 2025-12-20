# 80un - CP/M LBR Archive Unpacker

## Build Tools

All tools are sister projects in ~/src/:

- **uplm80** - PL/M-80 compiler (in PATH)
- **um80** - Z80/8080 assembler (in PATH)
- **ul80** - Linker (in PATH)
- **cpmemu** - CP/M emulator for Linux (~/src/cpmemu/src/cpmemu)

## Build Instructions

```bash
make          # Build 80un.com
make test     # Test with LBR archive
make test-arc # Test with ARC archive
make clean    # Remove intermediate files
```

## Source Layout

- `src/plm/` - PL/M-80 source files
- `src/un80/` - Python package

## Documentation

- Language references (PDFs) are in sister project directories
- DO NOT read PDFs directly - they cause context loops
- See ~/src/cpmemu/docs/ for CP/M documentation:
  - cpm22_bdos_calls.pdf - BDOS function reference
  - cpm22_fcb_detailed.pdf - FCB structure
  - cpm22_memory_layout.pdf - Memory map

## Target Platform: CP/M 2.2

- Files are 128-byte records
- Text files use ^Z (0x1A) as EOF
- FCB at 005CH, DMA buffer at 0080H
- BDOS entry at 0005H
- TPA (program area) starts at 0100H

## Testing with cpmemu

**IMPORTANT:** cpmemu performs automatic EOL conversion for text files.

By default, cpmemu detects files with text extensions (.MAC, .ASM, .TXT, .BAS, etc.)
and converts CR+LF to LF when writing to the Unix filesystem. This can cause test
failures when comparing PL/M output against Python raw output.

To test with binary mode (no EOL conversion), use a config file:

```bash
# test-binary.cfg
program = 80un.com
default_mode = binary
eol_convert = false
```

Then run: `cpmemu test-binary.cfg TESTFILE.MYC`

When comparing decompressor output:
- Python `uncrlzh()` returns raw bytes with CR+LF (CP/M format)
- Python with `--text` flag converts CR+LF to LF (Unix format)
- PL/M via cpmemu (default) outputs LF only (due to emulator conversion)
- PL/M via cpmemu (binary mode) outputs CR+LF (matches Python raw)
