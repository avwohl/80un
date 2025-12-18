# 80un - CP/M LBR Archive Unpacker

## Build Tools

All tools are sister projects in ~/src/:

- **uplm80** - PL/M-80 compiler (in PATH)
- **um80** - Z80/8080 assembler (in PATH)
- **ul80** - Linker (in PATH)
- **cpmemu** - CP/M emulator for Linux (~/src/cpmemu/src/cpmemu)

## Build Instructions

```bash
uplm80 80un.plm -o 80un.mac
um80 80un.mac -o 80un.rel
ul80 -o 80un.com 80un.rel
```

## Testing

```bash
~/src/cpmemu/src/cpmemu 80un.com test.lbr
```

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
