# 80un

A Python utility to unpack and decompress archive and compression formats used on the CP/M operating system for 8080/Z80 computers.

If you have old CP/M disks, disk images, or downloads from CP/M archives, this tool will help you extract the files within.

## Installation

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

MIT License

## Contributing

Bug reports and pull requests welcome at https://github.com/avwohl/80un

## See Also

- [CP/M information archive](https://www.seasip.info/Cpm/) - CP/M documentation
- [Walnut Creek CP/M CD-ROM](http://www.classiccmp.org/cpmarchives/) - Large CP/M software archive
