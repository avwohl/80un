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

### Archive Formats (contain multiple files)

| Format | Extensions | Description |
|--------|------------|-------------|
| **LBR** | `.lbr`, `.lqr`, `.lzr` | Library archive, similar to tar. Files inside may be compressed individually. |
| **ARC** | `.arc`, `.ark` | Compressed archive supporting multiple compression methods (stored, packed, squeezed, crunched, squashed). |

### Compression Formats (single file)

| Format | Extensions | Magic Bytes | Description |
|--------|------------|-------------|-------------|
| **Squeeze** | `.?q?` | `76 FF` | Huffman coding with run-length encoding. Devised by Richard Greenlaw, 1981. |
| **Crunch** | `.?z?` | `76 FE` | LZW compression similar to Unix compress. More efficient than squeeze. |
| **CrLZH** | `.?y?` | `76 FD` | LZH compression (Lempel-Ziv + Huffman). Most efficient CP/M compression. |

### CP/M File Naming Convention

CP/M used 8.3 filenames. Compressed files indicated their compression by replacing the **middle letter** of the extension:

| Original | Squeezed | Crunched | CrLZH |
|----------|----------|----------|-------|
| `FILE.TXT` | `FILE.TQT` | `FILE.TZT` | `FILE.TYT` |
| `FILE.COM` | `FILE.CQM` | `FILE.CZM` | `FILE.CYM` |
| `FILE.ASM` | `FILE.AQM` | `FILE.AZM` | `FILE.AYM` |
| `FILE.DOC` | `FILE.DQC` | `FILE.DZC` | `FILE.DYC` |

Files with no extension used `.QQQ`, `.ZZZ`, or `.YYY`.

## Command Line Usage

```
usage: 80un [-h] [--version] [-o DIR] [-l] [-t] [-f FORMAT] [-n] file

Unpacker for CP/M compression and packing formats

positional arguments:
  file                  File to extract or decompress

options:
  -h, --help            Show this help message and exit
  --version             Show program's version number and exit
  -o, --output DIR      Output directory for extracted files
  -l, --list            List contents without extracting
  -t, --text            Convert text files (strip ^Z, CR/LF to LF)
  -f, --format FORMAT   Force file format: lbr, arc, squeeze, crunch, crlzh
  -n, --no-clobber      Do not overwrite existing files
```

### Examples

**List contents of an LBR archive:**
```bash
$ 80un myarchive.lbr -l
Filename             Size  Sectors
------------------------------------
README.TZT            512        4
PROGRAM.CZM          8192       64
DATA.DZT             1024        8

3 file(s)
```

**List contents of an ARC archive:**
```bash
$ 80un myarchive.arc -l
Filename           Original  Compressed  Method
------------------------------------------------------
README.TXT             1024         512  crunched LZW
PROGRAM.COM           16384        8192  crunched LZW
DATA.DAT               2048        1024  squeezed

3 file(s)
```

**Extract an archive:**
```bash
$ 80un myarchive.lbr
  README.TXT
  PROGRAM.COM
  DATA.DAT

Extracted 3 file(s)
```

**Extract to a specific directory:**
```bash
$ 80un myarchive.lbr -o output/
  README.TXT
  PROGRAM.COM
  DATA.DAT

Extracted 3 file(s)
```

**Extract and convert text files to Unix format:**
```bash
$ 80un myarchive.lbr -t -o output/
```

This strips the ^Z (Ctrl-Z) end-of-file padding and converts CR/LF line endings to Unix LF.

**Decompress a single crunched file:**
```bash
$ 80un document.tzt
  document.txt (2048 bytes)
```

The original filename is recovered from the compressed file header.

**Force a specific format:**
```bash
$ 80un unknown.dat -f crunch
```

**Extract without overwriting existing files:**
```bash
$ 80un myarchive.lbr -o output/ -n
  README.TXT
  PROGRAM.COM (skipped, already exists)
  DATA.DAT

3 file(s): 2 extracted, 1 skipped
```

The `-n` / `--no-clobber` option is useful when extracting multiple archives to the same directory, or when you want to preserve files you've already modified.

## Python API

### Extracting Archives

```python
from un80 import extract_lbr, extract_arc

# Extract LBR archive
# Returns list of (filename, data) tuples
files = extract_lbr("archive.lbr", "output_dir/")
for filename, data in files:
    print(f"Extracted {filename}: {len(data)} bytes")

# Extract without writing to disk
files = extract_lbr("archive.lbr")  # No output_dir
for filename, data in files:
    process(data)

# Extract with text conversion
files = extract_lbr("archive.lbr", "output/", convert_text=True)

# Extract ARC archive
files = extract_arc("archive.arc", "output_dir/")
```

### Decompressing Single Files

```python
from un80 import unsqueeze, uncrunch, uncrlzh

# Read compressed file
with open("document.tqt", "rb") as f:
    compressed = f.read()

# Decompress based on format
decompressed = unsqueeze(compressed)   # For .?q? files
decompressed = uncrunch(compressed)    # For .?z? files
decompressed = uncrlzh(compressed)     # For .?y? files

# Write decompressed data
with open("document.txt", "wb") as f:
    f.write(decompressed)
```

### Listing Archive Contents

```python
from un80.lbr import list_lbr
from un80.arc import list_arc

# List LBR contents
for entry in list_lbr("archive.lbr"):
    print(f"{entry.filename}: {entry.data_size} bytes")

# List ARC contents
for entry in list_arc("archive.arc"):
    print(f"{entry.filename}: {entry.original_size} bytes ({entry.method_name})")
```

### CP/M Text File Utilities

```python
from un80 import strip_cpm_eof, crlf_to_lf, is_text_file

# Strip ^Z EOF padding from CP/M text file
data = strip_cpm_eof(data)

# Convert CR/LF to Unix LF
data = crlf_to_lf(data)

# Check if file is likely text based on extension
if is_text_file("readme.txt"):
    data = strip_cpm_eof(data)
    data = crlf_to_lf(data)
```

### Format Detection

```python
from un80.cpm import detect_compression

with open("unknown.file", "rb") as f:
    data = f.read()

format_type = detect_compression(data)
# Returns: 'squeeze', 'crunch', 'crlzh', 'arc', 'lbr', or None
```

### Getting Original Filenames

Compressed files store the original filename in their header:

```python
from un80.squeeze import get_squeezed_filename
from un80.crunch import get_crunched_filename
from un80.crlzh import get_crlzh_filename

with open("file.tzt", "rb") as f:
    data = f.read()

original_name = get_crunched_filename(data)
print(f"Original filename: {original_name}")  # e.g., "FILE.TXT"
```

## CP/M File Handling

CP/M files have characteristics that differ from modern systems:

### 128-Byte Records

CP/M measured file sizes in 128-byte records (sectors), not bytes. A file's actual byte length wasn't stored; only the record count. This means:

- Files are always multiples of 128 bytes
- The last record may contain padding

### ^Z End-of-File Marker

Text files that didn't fill their last 128-byte record were padded. The convention was to mark the end of actual content with a Ctrl-Z character (0x1A), with the remainder filled with more ^Z characters or garbage.

Use `--text` or `strip_cpm_eof()` to remove this padding.

### CR/LF Line Endings

CP/M text files used CR/LF (carriage return + line feed, 0x0D 0x0A) line endings, like DOS/Windows. Use `--text` or `crlf_to_lf()` to convert to Unix-style LF endings.

## ARC Compression Methods

ARC archives can contain files compressed with different methods:

| Method | Name | Description |
|--------|------|-------------|
| 1 | Stored (old) | No compression (obsolete) |
| 2 | Stored | No compression |
| 3 | Packed | Run-length encoding only |
| 4 | Squeezed | Huffman coding after RLE |
| 5 | Crunched (old) | 12-bit LZW (obsolete) |
| 6 | Crunched+RLE | 12-bit LZW with RLE (obsolete) |
| 7 | Crunched | LZW with faster hash |
| 8 | Crunched | 9-12 bit LZW (most common) |
| 9 | Squashed | 13-bit LZW (Phil Katz) |

## Troubleshooting

### "Cannot determine format"

The file doesn't have a recognized magic number or extension. Try specifying the format manually:

```bash
80un mystery.dat -f crunch
```

### Garbled output from text files

The file may still have CP/M formatting. Use the `--text` option:

```bash
80un archive.lbr -t
```

### "Invalid magic" or decompression errors

The file may be corrupted, truncated, or not actually in the detected format. Try:

1. Verify the file is complete
2. Try a different format with `-f`
3. Check if it's a different vintage format not yet supported

### CrLZH decompression produces partial or garbled output

CrLZH uses a complex LZSS algorithm with adaptive Huffman coding. If decompression fails, verify the file isn't corrupted or truncated. Both V1.x and V2.0 versions are supported.

### Files extract with wrong names

Some very old archives don't store original filenames. The tool will use the archive member name with the compression indicator removed.

### Duplicate filenames in archive

Some archives contain multiple files with the same name (e.g., from different directories that CP/M flattened). When this happens, 80un automatically renames duplicates by appending `_1`, `_2`, etc.:

```bash
$ 80un archive_with_dupes.lbr
  README.TXT
  README.TXT -> README_1.TXT
  DATA.DAT

3 file(s): 3 extracted
```

## History

These compression formats were developed in the early 1980s for CP/M systems:

- **1981**: Squeeze (SQ/USQ) by Richard Greenlaw - first widely-used CP/M compression
- **1984**: LBR format by Gary P. Novosielski - library/archive format
- **1985**: ARC by System Enhancement Associates - compressed archives
- **1985**: Crunch - LZW compression, more efficient than squeeze
- **1986**: Crunch v2.0 - improved with "metastatic code reassignment"
- **Late 1980s**: CrLZH - LZH compression, most efficient

## License

GPL v3 License

## Contributing

Bug reports and pull requests welcome at https://github.com/avwohl/80un

---

## CP/M Version (80un.com)

A native CP/M program written in PL/M-80 that runs on real vintage hardware or emulators.

### Getting 80un.com

Download `80un.com` directly from this repository, or build from source (see below).

Transfer to your CP/M system via:
- XMODEM/YMODEM from a terminal program
- Write to a disk image and mount it
- Your emulator's file import feature

### Usage on CP/M

Extract an LBR archive:
```
A>80UN MYLIB.LBR

80UN - CP/M Archive Unpacker v2.3

Extracting:
  README.TXT OK
  PROGRAM.COM OK
  SOURCE.ASM OK

3 file(s) extracted
```

Extract an ARC archive:
```
A>80UN SOFTWARE.ARC

80UN - CP/M Archive Unpacker v2.3

Extracting:
  INSTALL.DOC OK
  PROG.COM OK
  CONFIG.DAT OK

3 file(s) extracted
```

Decompress a squeezed file:
```
A>80UN MANUAL.TQT

80UN - CP/M Archive Unpacker v2.3

Extracting:
Creating: MANUAL.TXT OK

1 file(s) extracted
```

Decompress a crunched file:
```
A>80UN SOURCE.AZM

80UN - CP/M Archive Unpacker v2.3

Extracting:
Creating: SOURCE.ASM OK

1 file(s) extracted
```

### Notes

- Files extract to current drive/user area
- Existing files are overwritten without warning
- Original filenames are restored from compressed file headers
- Nested compression is handled (e.g., crunched files inside LBR)

### Building from Source

Requires the [uplm80](https://github.com/avwohl/uplm80) toolchain:

```bash
make            # Build 80un.com
make test       # Test with sample archives
make clean      # Remove build artifacts
```

### Developer Notes: EOL Handling

When testing the PL/M version with [cpmemu](https://github.com/avwohl/cpmemu), be aware that the emulator performs automatic line-ending conversion for text files. Files with extensions like `.MAC`, `.ASM`, `.TXT` are detected as text and have CR+LF converted to LF when written to the Unix filesystem.

To get raw binary output for testing, create a config file with `default_mode = binary` and `eol_convert = false`. See `CLAUDE.md` for details.

The Python and PL/M decompressors produce **identical output** when:
- Python: raw output (no `--text` flag)
- PL/M: via cpmemu with binary mode enabled

### Source Files

PL/M-80 source is in `src/plm/`:

| File | Purpose |
|------|---------|
| `startup.plm` | Entry point |
| `common.plm` | BDOS interface, memory ops |
| `io.plm` | Buffered I/O, bit readers |
| `squeeze.plm` | Huffman decompressor |
| `crunch.plm` | LZW decompressor |
| `lzh.plm` | LZSS decompressor |
| `arc.plm` | ARC archive extractor |
| `lbr.plm` | LBR archive extractor |
| `bas.plm` | MBASIC detokenizer |
| `main.plm` | 80UN main program |
| `basmain.plm` | 80UNBAS main program |
| `heap.asm` | Heap allocation bridge |

### Requirements

- CP/M 2.2 or compatible (MP/M, ZCPR, etc.)
- ~62KB TPA (Transient Program Area) for 80UN.COM
- ~18KB TPA for 80UNBAS.COM
- Z80 processor

### Memory-Constrained Systems

80UN.COM requires approximately 62KB of TPA to support ARC method 9 (squashed) with its 8192-entry LZW dictionary. For systems with limited memory, 80UNBAS.COM is provided as a separate utility for MBASIC detokenization, requiring only ~18KB TPA.

---

## 80UNBAS.COM - MBASIC Detokenizer

A companion utility that converts tokenized MBASIC files to ASCII text.

### Usage

```
A>80UNBAS PROGRAM.BAS

80UNBAS - MBASIC Detokenizer v2.3

Creating: PROGRAM.TXT OK
```

### Supported Formats

| Magic | Type | Description |
|-------|------|-------------|
| `0xFF` | Standard | Normal tokenized MBASIC file |
| `0xFE` | Protected | Protected (encrypted) MBASIC file |

Note: "Protected" files are only lightly scrambled; 80UNBAS fully decrypts and detokenizes them.

### Building

80UNBAS is built alongside 80UN:

```bash
make           # Builds both 80un.com and 80unbas.com
make test-bas  # Test BASIC detokenizer
```

---

## Test Files and Resources

Sample archives for testing can be found at:

- [Zimmers.net CP/M Archivers](https://www.zimmers.net/anonftp/pub/cpm/archivers/) - ARK, LBR, CrLZH tools and archives
- [Chaos Cottage BBS CP/M Files](https://www.chiark.greenend.org.uk/~jacobn/cpm/cpmfiles.html) - Various CP/M archives including ARK and LZH samples

### Test Coverage Gaps

The test suite needs additional sample files to achieve complete coverage:

| Format | What's Tested | What's Missing |
|--------|---------------|----------------|
| **Squeeze** | ✅ Complete | - |
| **Crunch** | ✅ V2.x (siglevel ≥ 0x20) | V1.x samples (fixed 12-bit codes) |
| **CrLZH** | ✅ V1.x and V2.0 | - |
| **ARC** | ✅ Methods 2, 3, 8, 9 | Methods 1, 4-7 (stored old, squeezed, old crunched) |
| **LBR** | ✅ Archive with nested compression | - |
| **MBASIC** | ✅ Standard (0xFF) and Protected (0xFE) | - |

Use `-v` with `-l` to check file versions: `80un file.czm -l -v`

Contributions of test files with missing versions/methods are welcome.
## Related Projects

- [cpmdroid](https://github.com/avwohl/cpmdroid) - Z80/CP/M emulator for Android with RomWBW HBIOS compatibility and VT100 terminal
- [cpmemu](https://github.com/avwohl/cpmemu) - CP/M 2.2 emulator with Z80/8080 CPU emulation and BDOS/BIOS translation to Unix filesystem
- [ioscpm](https://github.com/avwohl/ioscpm) - Z80/CP/M emulator for iOS and macOS with RomWBW HBIOS compatibility
- [learn-ada-z80](https://github.com/avwohl/learn-ada-z80) - Ada programming examples for the uada80 compiler targeting Z80/CP/M
- [mbasic](https://github.com/avwohl/mbasic) - Modern MBASIC 5.21 Interpreter & Compilers
- [mbasic2025](https://github.com/avwohl/mbasic2025) - MBASIC 5.21 source code reconstruction - byte-for-byte match with original binary
- [mbasicc](https://github.com/avwohl/mbasicc) - C++ implementation of MBASIC 5.21
- [mbasicc_web](https://github.com/avwohl/mbasicc_web) - WebAssembly MBASIC 5.21
- [mpm2](https://github.com/avwohl/mpm2) - MP/M II multi-user CP/M emulator with SSH terminal access and SFTP file transfer
- [romwbw_emu](https://github.com/avwohl/romwbw_emu) - Hardware-level Z80 emulator for RomWBW with 512KB ROM + 512KB RAM banking and HBIOS support
- [scelbal](https://github.com/avwohl/scelbal) - SCELBAL BASIC interpreter - 8008 to 8080 translation
- [uada80](https://github.com/avwohl/uada80) - Ada compiler targeting Z80 processor and CP/M 2.2 operating system
- [ucow](https://github.com/avwohl/ucow) - Unix/Linux Cowgol to Z80 compiler
- [um80_and_friends](https://github.com/avwohl/um80_and_friends) - Microsoft MACRO-80 compatible toolchain for Linux: assembler, linker, librarian, disassembler
- [upeepz80](https://github.com/avwohl/upeepz80) - Universal peephole optimizer for Z80 compilers
- [uplm80](https://github.com/avwohl/uplm80) - PL/M-80 compiler targeting Intel 8080 and Zilog Z80 assembly language
- [z80cpmw](https://github.com/avwohl/z80cpmw) - Z80 CP/M emulator for Windows (RomWBW)
- [CP/M information archive](https://www.seasip.info/Cpm/) - CP/M documentation
- [Walnut Creek CP/M CD-ROM](http://www.classiccmp.org/cpmarchives/) - Large CP/M software archive
- [Fred Jan Kraan's PX-8 Archives](https://electrickery.nl/comp/px8/archs.html) - CP/M decompression utilities including CrLZH samples

