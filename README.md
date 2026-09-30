# 80un

Unpack and decompress archive and compression formats used on the CP/M operating system for Z80 computers.

Two implementations are provided:

| Version | Runs On | Use Case |
|---------|---------|----------|
| **80un.com** | CP/M 2.2+ | Extract archives on vintage hardware or emulators |
| **80un (Python)** | Python 3.8+ | Extract archives on modern systems |

Both support the same formats and produce identical output.

---

## Python Version

### Installation

```bash
pip install 80un
```

Requires Python 3.8 or later. No external dependencies.

## Quick Start

```bash
# Extract an LBR archive
80un archive.lbr

# Extract an ARC archive to a specific directory
80un archive.arc -o extracted/

# List contents of an archive without extracting
80un archive.lbr -l

# Decompress a crunched file
80un document.tzt
```

## Supported Formats

- **LBR** (`.lbr`, `.lqr`, `.lzr`): library archive, similar to tar.
- **ARC** (`.arc`, `.ark`): compressed archive with several compression methods.
- **Squeeze** (`.?q?`): Huffman coding with run-length encoding.
- **Crunch** (`.?z?`): LZW compression.
- **CrLZH** (`.?y?`): LZH compression (Lempel-Ziv + Huffman).
- **MBASIC** tokenized files, through the companion program `80UNBAS.COM`.

## CP/M Version (80un.com)

A native CP/M program written in PL/M-80 runs on real vintage hardware or emulators.
Download `80un.com` from this repository, or build `80un.com` with the [uplm80](https://github.com/avwohl/uplm80) toolchain:

```bash
make            # Build 80un.com
make test       # Test with sample archives
```

```
A>80UN MYLIB.LBR
```

## Documentation

- [Command line usage](https://github.com/avwohl/80un/blob/main/docs/usage.md) - options and examples for the Python `80un` command.
- [Python API](https://github.com/avwohl/80un/blob/main/docs/python_api.md) - extract, decompress, list and detect formats from Python.
- [Supported formats](https://github.com/avwohl/80un/blob/main/docs/formats.md) - format tables, CP/M file naming, ARC methods, CP/M file handling, history.
- [CP/M version](https://github.com/avwohl/80un/blob/main/docs/cpm_version.md) - `80un.com` usage, member names on CP/M, building, source files, memory, `80UNBAS.COM`.
- [Troubleshooting](https://github.com/avwohl/80un/blob/main/docs/troubleshooting.md) - common errors and odd file names.
- [Testing](https://github.com/avwohl/80un/blob/main/docs/testing.md) - sample archives, test coverage, how the CP/M program is tested.
- [CHANGELOG.md](https://github.com/avwohl/80un/blob/main/CHANGELOG.md) - release notes.

## License

GPL v3 License

## Contributing

Bug reports and pull requests welcome at https://github.com/avwohl/80un

## Related Projects

- [cpmdroid](https://github.com/avwohl/cpmdroid) - Z80/CP/M emulator for Android phones and tablets. It emulates the RomWBW HBIOS interface and a VT100 terminal.
- [cpmemu](https://github.com/avwohl/cpmemu) - Z80/CP/M emulator for Linux and Windows, with Z80 and 8080 CPU cores. It translates the BDOS and BIOS calls of CP/M 2.2 programs to the host file system.
- [ioscpm](https://github.com/avwohl/ioscpm) - Z80/CP/M emulator for iOS and macOS. It emulates the RomWBW HBIOS interface and runs CP/M 2.2 and CP/M 3.
- [learn-ada-z80](https://github.com/avwohl/learn-ada-z80) - Collection of more than 90 Ada example programs for uada80, the Ada compiler for the Z80 processor and CP/M.
- [mbasic](https://github.com/avwohl/mbasic) - Python interpreter for MBASIC 5.21, the Microsoft BASIC-80 for CP/M. Two compiler backends compile the programs to CP/M .COM files or to JavaScript.
- [mbasic2025](https://github.com/avwohl/mbasic2025) - Reconstruction of the lost source code of MBASIC 5.21, the Microsoft BASIC-80 for CP/M. The MACRO-80 source code assembles to a binary that matches mbasic.com byte for byte.
- [mbasicc](https://github.com/avwohl/mbasicc) - C++17 interpreter for MBASIC 5.21, the Microsoft BASIC-80 for CP/M. It runs on Linux and macOS.
- [mbasicc_web](https://github.com/avwohl/mbasicc_web) - Web browser interpreter for MBASIC 5.21, the Microsoft BASIC-80 for CP/M. Emscripten compiles the mbasicc interpreter to WebAssembly.
- [mpm2](https://github.com/avwohl/mpm2) - Z80 emulator for MP/M II, the multi-user CP/M operating system. Users connect over SSH, and SFTP clients transfer files.
- [romwbw_emu](https://github.com/avwohl/romwbw_emu) - Hardware-level Z80/CP/M emulator for Linux and macOS. It emulates the RomWBW HBIOS interface and switches banks in 512 KB of ROM and 512 KB of RAM.
- [scelbal](https://github.com/avwohl/scelbal) - Floating-point BASIC interpreter for the 8080 processor and CP/M. A translator converts the original 8008 source code to 8080 source code.
- [uada80](https://github.com/avwohl/uada80) - Ada compiler for the Z80 processor and CP/M 2.2. It compiles a subset of Ada 2012 to CP/M .COM files.
- [uc80](https://github.com/avwohl/uc80) - C compiler for the Z80 processor and CP/M. It optimizes for small code size.
- [ucow](https://github.com/avwohl/ucow) - Cowgol compiler for the Z80 processor and CP/M. It runs on Linux in Python.
- [um80_and_friends](https://github.com/avwohl/um80_and_friends) - Linux toolchain that is compatible with Microsoft MACRO-80. It has an assembler, a linker, a librarian, and a disassembler.
- [upeepz80](https://github.com/avwohl/upeepz80) - Peephole optimizer for Z80 compilers that write lowercase Z80 assembly language. It shortens jumps to jr, builds djnz loops, and removes dead stores.
- [uplm80](https://github.com/avwohl/uplm80) - PL/M-80 compiler for the Z80 processor and CP/M. It writes Intel 8080 and Zilog Z80 assembly language.
- [z80cpmw](https://github.com/avwohl/z80cpmw) - Z80/CP/M emulator for Windows. It emulates the RomWBW HBIOS interface and boots CP/M from disk images.
- [z80fpga](https://github.com/avwohl/z80fpga) - Z80 CPU in SystemVerilog for FPGAs, with RomWBW-compatible banked memory. It boots RomWBW and CP/M 2.2 on a Digilent Nexys A7.

## See Also

- [CP/M information archive](https://www.seasip.info/Cpm/) - CP/M documentation
- [Walnut Creek CP/M CD-ROM](http://www.classiccmp.org/cpmarchives/) - Large CP/M software archive
- [Fred Jan Kraan's PX-8 Archives](https://electrickery.nl/comp/px8/archs.html) - CP/M decompression utilities including CrLZH samples
